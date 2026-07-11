param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId
)

$ErrorActionPreference = "Stop"

if (!(Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

(Get-Content ".env") -replace "^WORKER_MACHINE_ID=.*", "WORKER_MACHINE_ID=$MachineId" | Set-Content ".env"
docker compose --profile worker up --build worker

