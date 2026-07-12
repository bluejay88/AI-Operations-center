$ErrorActionPreference = "Stop"

. ".\docker\lib.ps1"

Write-Host "AI Operations Center brain recovery"
Write-Host ""
Write-Host "This starts only the core stack: Postgres + AI Operations API."
Write-Host "It does not start Ollama, Open WebUI, local n8n, or local Flowise."
Write-Host ""

$dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $dockerDesktop) {
    Write-Host "Opening Docker Desktop..."
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    Start-Sleep -Seconds 20
}

try {
    Assert-DockerAvailable
} catch {
    Write-Host $_.Exception.Message
    Write-Host ""
    Write-Host "Open Docker Desktop > Troubleshoot."
    Write-Host "Try Restart Docker Desktop first."
    Write-Host "If Docker still says it cannot start, use Clean / Purge data or Reset to factory defaults."
    Write-Host "This is safe for this fresh Docker setup, but it removes Docker images/containers/volumes."
    throw
}

Write-Host "Docker is ready. Starting core brain services..."
docker compose up -d postgres
docker compose up --build -d ai-ops-api

Write-Host "Initializing database and agents..."
docker compose run --rm ai-ops-api python -m ai_ops_center.cli init-db
docker compose run --rm ai-ops-api python -m ai_ops_center.cli seed
docker compose run --rm ai-ops-api python -m ai_ops_center.cli daily-priorities

Write-Host "Core brain status:"
docker compose run --rm ai-ops-api python -m ai_ops_center.cli status

