param(
    [int]$Port = 22
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this PowerShell script as Administrator."
    }
}

Assert-Admin

Write-Host "Installing and enabling Windows OpenSSH Server..."
$capability = Get-WindowsCapability -Online | Where-Object Name -like "OpenSSH.Server*"
if ($capability.State -ne "Installed") {
    Add-WindowsCapability -Online -Name $capability.Name
}

Set-Service -Name sshd -StartupType Automatic
Start-Service -Name sshd

if (-not (Get-NetFirewallRule -Name "AI-Ops-OpenSSH-Tailscale" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule `
        -Name "AI-Ops-OpenSSH-Tailscale" `
        -DisplayName "AI Ops OpenSSH over private network" `
        -Enabled True `
        -Direction Inbound `
        -Protocol TCP `
        -Action Allow `
        -LocalPort $Port `
        -Profile Private
}

Write-Host "OpenSSH Server is enabled. Test from the Brain PC over the laptop's Tailscale IP."

