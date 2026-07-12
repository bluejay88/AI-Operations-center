param(
    [string]$Branch = "master"
)

$ErrorActionPreference = "Stop"

if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or not on PATH."
}

$origin = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($origin)) {
    throw "No git origin is configured. Run docker\configure-git-remote.ps1 first."
}

$currentBranch = git branch --show-current
if ($currentBranch -ne $Branch) {
    git branch -M $Branch
}

$changes = git status --short
if ($changes) {
    Write-Host "Uncommitted changes are present. Commit them before pushing:"
    git status --short
    exit 1
}

git push -u origin $Branch
Write-Host "Pushed $Branch to origin."
