$ErrorActionPreference = "Stop"

. ".\docker\lib.ps1"
Assert-DockerAvailable

if (!(Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

docker compose up -d postgres
Start-Sleep -Seconds 8
docker compose up --build -d ai-ops-api
docker compose run --rm ai-ops-api python -m ai_ops_center.cli init-db
docker compose run --rm ai-ops-api python -m ai_ops_center.cli seed
docker compose run --rm ai-ops-api python -m ai_ops_center.cli daily-priorities

Write-Host "AI Operations Center is starting."
Write-Host "API: http://localhost:8088"
Write-Host "Core brain services are started."
Write-Host "Optional AI tools: docker compose --profile ai-tools up --build -d"
Write-Host "Optional automation tools: docker compose --profile automation-tools up --build -d"
