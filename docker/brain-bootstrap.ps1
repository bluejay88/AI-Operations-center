$ErrorActionPreference = "Stop"

. ".\docker\lib.ps1"
Assert-DockerAvailable

if (!(Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

docker compose up --build -d postgres
Start-Sleep -Seconds 8
docker compose run --rm ai-ops-api python -m ai_ops_center.cli init-db
docker compose run --rm ai-ops-api python -m ai_ops_center.cli seed
docker compose run --rm ai-ops-api python -m ai_ops_center.cli daily-priorities
docker compose up --build -d

Write-Host "AI Operations Center is starting."
Write-Host "API: http://localhost:8088"
Write-Host "Open WebUI: http://localhost:3000"
Write-Host "n8n: http://localhost:5678"
Write-Host "Flowise: http://localhost:3001"
