param(
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path (Get-Location) "docker\watch-connectivity.ps1"
if (!(Test-Path $scriptPath)) {
    throw "Cannot find $scriptPath. Run this from the AI Operations Center repository root."
}

Start-Process powershell.exe `
    -WindowStyle Hidden `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -IntervalSeconds $IntervalSeconds"

Write-Host "Started AI Operations connectivity monitor. Interval: $IntervalSeconds seconds."
