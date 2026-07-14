param(
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\lib.ps1"

$repoRoot = Split-Path $PSScriptRoot -Parent
$scriptPath = Join-Path $PSScriptRoot "watch-connectivity.ps1"
if (!(Test-Path $scriptPath)) {
    throw "Cannot find $scriptPath."
}
$outputRoot = Join-Path $repoRoot "output"
if (!(Test-Path $outputRoot)) {
    New-Item -ItemType Directory -Path $outputRoot | Out-Null
}
$process = Start-AiOpsBackgroundProcess `
    -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "& '$scriptPath' -IntervalSeconds $IntervalSeconds") `
    -Name "AI Operations connectivity monitor" `
    -PassThru

Write-Host "Started AI Operations connectivity monitor. PID: $($process.Id). Interval: $IntervalSeconds seconds."
Write-Host "Logs: $(Join-Path $outputRoot 'connectivity-monitor.log')"
