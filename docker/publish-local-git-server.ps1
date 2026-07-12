param(
    [string]$Branch = "master"
)

$ErrorActionPreference = "Stop"

if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or not on PATH."
}

$repoRoot = (Resolve-Path ".").Path
$serverRoot = Join-Path $repoRoot "git-server"
$bareRepo = Join-Path $serverRoot "ai-operations-center.git"

if (!(Test-Path $serverRoot)) {
    New-Item -ItemType Directory -Path $serverRoot | Out-Null
}

if (!(Test-Path $bareRepo)) {
    git init --bare $bareRepo
}

$exportMarker = Join-Path $bareRepo "git-daemon-export-ok"
if (!(Test-Path $exportMarker)) {
    New-Item -ItemType File -Path $exportMarker | Out-Null
}

$changes = git status --short
if ($changes) {
    Write-Host "Uncommitted changes are present. Commit them before publishing:"
    git status --short
    exit 1
}

git push $bareRepo "$Branch`:$Branch"
git --git-dir=$bareRepo symbolic-ref HEAD "refs/heads/$Branch"
git --git-dir=$bareRepo update-server-info

Write-Host "Published $Branch to local Tailscale Git repo:"
Write-Host "  $bareRepo"
Write-Host ""
Write-Host "Laptop clone URL:"
Write-Host "  git clone git://100.70.49.32/ai-operations-center.git"
