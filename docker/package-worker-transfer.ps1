$ErrorActionPreference = "Stop"

$repoRoot = Get-Location
$exportDir = Join-Path $repoRoot "exports"
$zipPath = Join-Path $exportDir "ai-operations-center-worker.zip"
$stagingDir = Join-Path $exportDir "worker-package"

if (!(Test-Path $exportDir)) {
    New-Item -ItemType Directory -Path $exportDir | Out-Null
}

if (Test-Path $stagingDir) {
    Remove-Item -LiteralPath $stagingDir -Recurse -Force
}

New-Item -ItemType Directory -Path $stagingDir | Out-Null

$items = @(
    ".dockerignore",
    ".env.example",
    ".gitignore",
    "Dockerfile",
    "README.md",
    "ai_ops_center",
    "config",
    "docker",
    "docs",
    "pyproject.toml",
    "sql",
    "tests",
    "workflows",
    "docker-compose.yml"
)

foreach ($item in $items) {
    $source = Join-Path $repoRoot $item
    if (Test-Path $source) {
        Copy-Item -LiteralPath $source -Destination $stagingDir -Recurse
    }
}

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath
Write-Host "Created worker transfer package:"
Write-Host $zipPath
Write-Host ""
Write-Host "Do not include .env, flowcheck.py, logs, or .docker secrets in laptop copies."

