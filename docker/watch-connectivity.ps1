param(
    [int]$IntervalSeconds = 30,
    [string]$BrainApi = "http://localhost:8088",
    [string]$SourceMachineId = "brain-gaming-pc"
)

$ErrorActionPreference = "Continue"

while ($true) {
    $timestamp = Get-Date -Format o
    Write-Host "[$timestamp] Scanning AI Operations laptop connectivity..."
    .\docker\scan-connectivity.ps1 -BrainApi $BrainApi -SourceMachineId $SourceMachineId | Out-Host
    Start-Sleep -Seconds $IntervalSeconds
}
