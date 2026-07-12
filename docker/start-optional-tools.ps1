param(
    [switch]$AiTools,
    [switch]$AutomationTools,
    [switch]$All
)

$ErrorActionPreference = "Stop"

. ".\docker\lib.ps1"
Assert-DockerAvailable

if ($All -or $AiTools) {
    Write-Host "Starting Ollama and Open WebUI..."
    docker compose --profile ai-tools up --build -d
}

if ($All -or $AutomationTools) {
    Write-Host "Starting local n8n and local Flowise..."
    docker compose --profile automation-tools up --build -d
}

if (!$All -and !$AiTools -and !$AutomationTools) {
    Write-Host "Choose -AiTools, -AutomationTools, or -All."
}

