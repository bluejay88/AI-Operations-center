param(
    [int]$IntervalSeconds = 30,
    [string]$BrainApi = "http://localhost:8088",
    [string]$SourceMachineId = "brain-gaming-pc"
)

$ErrorActionPreference = "Continue"
$scannerPath = Join-Path $PSScriptRoot "scan-connectivity.ps1"
$outputRoot = Join-Path (Split-Path $PSScriptRoot -Parent) "output"
if (!(Test-Path $outputRoot)) {
    New-Item -ItemType Directory -Path $outputRoot | Out-Null
}
Start-Transcript -Path (Join-Path $outputRoot "connectivity-monitor.log") -Append | Out-Null

while ($true) {
    $timestamp = Get-Date -Format o
    Write-Host "[$timestamp] Scanning AI Operations laptop connectivity..."
    & $scannerPath -BrainApi $BrainApi -SourceMachineId $SourceMachineId | Out-Host
    Start-Sleep -Seconds $IntervalSeconds
}
