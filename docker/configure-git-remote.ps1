param(
    [Parameter(Mandatory=$true)]
    [string]$RemoteUrl,

    [string]$Branch = "master"
)

$ErrorActionPreference = "Stop"

if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or not on PATH. Install Git for Windows first."
}

$currentBranch = git branch --show-current
if ([string]::IsNullOrWhiteSpace($currentBranch)) {
    throw "This repository is not on a named branch."
}

if ($currentBranch -ne $Branch) {
    git branch -M $Branch
}

$existingOrigin = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0 -and ![string]::IsNullOrWhiteSpace($existingOrigin)) {
    git remote set-url origin $RemoteUrl
} else {
    git remote add origin $RemoteUrl
}

Write-Host "Configured origin:"
git remote -v
Write-Host ""
Write-Host "Next push the brain source of truth with:"
Write-Host "  git push -u origin $Branch"
