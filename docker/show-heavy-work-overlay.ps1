param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId,

    [string]$BrainHost = "100.70.49.32",

    [int]$PollSeconds = 5,

    [int]$IdleSecondsBeforeOverlay = 45,

    [int]$RunningTaskThreshold = 1
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\lib.ps1"
$apiHeaders = Get-AiOpsApiHeaders -MachineId $MachineId

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class IdleTime {
  [StructLayout(LayoutKind.Sequential)]
  public struct LASTINPUTINFO {
    public uint cbSize;
    public uint dwTime;
  }
  [DllImport("user32.dll")]
  public static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);
  public static uint GetIdleMilliseconds() {
    LASTINPUTINFO lii = new LASTINPUTINFO();
    lii.cbSize = (uint)System.Runtime.InteropServices.Marshal.SizeOf(typeof(LASTINPUTINFO));
    GetLastInputInfo(ref lii);
    return ((uint)Environment.TickCount - lii.dwTime);
  }
}
"@

function Get-IdleSeconds {
    try {
        return [math]::Floor([IdleTime]::GetIdleMilliseconds() / 1000)
    } catch {
        return 0
    }
}

function Get-RunningTaskCount {
    try {
        $readiness = Invoke-RestMethod -Uri "http://$BrainHost`:8088/readiness.json" -Headers $apiHeaders -TimeoutSec 8
        $machine = $readiness.machines | Where-Object { $_.id -eq $MachineId } | Select-Object -First 1
        if ($machine -and $machine.task_counts -and $null -ne $machine.task_counts.running) {
            return [int]$machine.task_counts.running
        }
    } catch {}
    return 0
}

function New-OverlayForm {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "AI Operations Center Heavy Work"
    $form.WindowState = "Maximized"
    $form.FormBorderStyle = "None"
    $form.TopMost = $true
    $form.BackColor = [System.Drawing.Color]::FromArgb(8, 12, 18)
    $form.Opacity = 0.94
    $form.ShowInTaskbar = $false

    $panel = New-Object System.Windows.Forms.TableLayoutPanel
    $panel.Dock = "Fill"
    $panel.ColumnCount = 1
    $panel.RowCount = 3
    $panel.BackColor = $form.BackColor
    $panel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 35)))
    $panel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 35)))
    $panel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 30)))

    $title = New-Object System.Windows.Forms.Label
    $title.Text = "Hey, don't use me right now"
    $title.Dock = "Fill"
    $title.TextAlign = "BottomCenter"
    $title.Font = New-Object System.Drawing.Font("Segoe UI", 42, [System.Drawing.FontStyle]::Bold)
    $title.ForeColor = [System.Drawing.Color]::FromArgb(216, 255, 246)

    $body = New-Object System.Windows.Forms.Label
    $body.Name = "BodyLabel"
    $body.Text = "I am doing heavy AI Operations work at the moment."
    $body.Dock = "Fill"
    $body.TextAlign = "MiddleCenter"
    $body.Font = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Regular)
    $body.ForeColor = [System.Drawing.Color]::FromArgb(203, 215, 230)

    $hint = New-Object System.Windows.Forms.Label
    $hint.Text = "This screen hides automatically when work stops or when you start using this laptop."
    $hint.Dock = "Fill"
    $hint.TextAlign = "TopCenter"
    $hint.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Regular)
    $hint.ForeColor = [System.Drawing.Color]::FromArgb(139, 152, 168)

    $panel.Controls.Add($title, 0, 0)
    $panel.Controls.Add($body, 0, 1)
    $panel.Controls.Add($hint, 0, 2)
    $form.Controls.Add($panel)
    return $form
}

$overlay = $null
Write-Host "Watching $MachineId for heavy work. Brain: http://$BrainHost`:8088"
Write-Host "Overlay appears when running tasks >= $RunningTaskThreshold and user idle >= $IdleSecondsBeforeOverlay seconds."

while ($true) {
    $running = Get-RunningTaskCount
    $idle = Get-IdleSeconds
    $shouldShow = ($running -ge $RunningTaskThreshold -and $idle -ge $IdleSecondsBeforeOverlay)

    if ($shouldShow -and $null -eq $overlay) {
        $overlay = New-OverlayForm
        ($overlay.Controls[0].Controls | Where-Object { $_.Name -eq "BodyLabel" }).Text = "$MachineId is running $running AI Operations task(s)."
        $overlay.Show()
    } elseif ($shouldShow -and $null -ne $overlay) {
        ($overlay.Controls[0].Controls | Where-Object { $_.Name -eq "BodyLabel" }).Text = "$MachineId is running $running AI Operations task(s)."
    } elseif (-not $shouldShow -and $null -ne $overlay) {
        $overlay.Close()
        $overlay.Dispose()
        $overlay = $null
    }

    [System.Windows.Forms.Application]::DoEvents()
    Start-Sleep -Seconds $PollSeconds
}
