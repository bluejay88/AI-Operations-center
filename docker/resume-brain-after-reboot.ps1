$ErrorActionPreference = "Stop"

. ".\docker\lib.ps1"

Write-Host "Checking Docker after reboot..."
Assert-DockerAvailable

Write-Host "Docker is ready. Starting AI Operations Center brain stack..."
.\docker\brain-bootstrap.ps1

Write-Host "Brain stack started. Checking status..."
docker compose run --rm ai-ops-api python -m ai_ops_center.cli status

