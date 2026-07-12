param(
    [Parameter(Mandatory=$false)]
    [string]$BrainHost = "100.70.49.32"
)

$ErrorActionPreference = "Stop"

. ".\docker\lib.ps1"
$tailscaleExe = Assert-TailscaleAvailable

$healthUrl = "http://$BrainHost`:8088/health"
$statusUrl = "http://$BrainHost`:8088/status"

Write-Host "Tailscale:"
& $tailscaleExe status
Write-Host ""

Write-Host "Checking AI Operations brain at $healthUrl"
$health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 10
Write-Host "Health: $($health.status)"

Write-Host "Checking machine status at $statusUrl"
$status = Invoke-RestMethod -Uri $statusUrl -TimeoutSec 10
Write-Host $status.status
