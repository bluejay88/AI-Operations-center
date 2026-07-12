param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId,

    [Parameter(Mandatory=$false)]
    [string]$BrainHost = "100.70.49.32"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path ".env.example")) {
    throw "Run this from the AI Operations Center repository root."
}

$envContent = Get-Content ".env.example"
$envContent = $envContent -replace "^DATABASE_URL=.*", "DATABASE_URL=postgresql://aiops:aiops@$BrainHost`:5432/aiops"
$envContent = $envContent -replace "^LOCAL_DATABASE_URL=.*", "LOCAL_DATABASE_URL=postgresql://aiops:aiops@$BrainHost`:5432/aiops"
$envContent = $envContent -replace "^WORKER_MACHINE_ID=.*", "WORKER_MACHINE_ID=$MachineId"
$envContent = $envContent -replace "^TAILSCALE_HOSTNAME=.*", "TAILSCALE_HOSTNAME=$MachineId"
$envContent = $envContent -replace "^BRAIN_HOST=.*", "BRAIN_HOST=$BrainHost"
$envContent | Set-Content ".env"

Write-Host "Configured .env for $MachineId"
Write-Host "Brain host: $BrainHost"
Write-Host "Next: docker\worker-bootstrap.ps1 -MachineId $MachineId"
