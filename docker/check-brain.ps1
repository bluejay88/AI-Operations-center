param(
    [Parameter(Mandatory=$false)]
    [string]$BrainHost = "100.70.49.32",
    [string]$MachineId = "brain-gaming-pc"
)

$ErrorActionPreference = "Stop"
$BrainHost = $BrainHost.Trim().Trim('"').Trim("'")
$BrainHost = $BrainHost -replace "^https?://", ""
$BrainHost = ($BrainHost -split "/")[0]
$BrainHost = ($BrainHost -split ":")[0]
$BrainHost = $BrainHost.TrimEnd("\")

. ".\docker\lib.ps1"
$apiHeaders = Get-AiOpsApiHeaders -MachineId $MachineId
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
$status = Invoke-RestMethod -Uri $statusUrl -Headers $apiHeaders -TimeoutSec 10
Write-Host $status.status
