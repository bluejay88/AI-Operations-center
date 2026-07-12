param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("brain-gaming-pc", "business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId,

    [Parameter(Mandatory=$false)]
    [string]$BrainHost = "100.70.49.32"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path ".env")) {
    .\docker\configure-worker-env.ps1 -MachineId $MachineId -BrainHost $BrainHost
}

docker compose run --rm worker python -m ai_ops_center.cli benchmark --machine $MachineId --brain-host $BrainHost

