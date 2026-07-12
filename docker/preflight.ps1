$ErrorActionPreference = "Continue"

. ".\docker\lib.ps1"

Write-Host "AI Operations Center preflight"
Write-Host ""

$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    Write-Host "Docker CLI: found at $($docker.Source)"
    docker --version
} else {
    Write-Host "Docker CLI: not found on PATH"
    Write-Host "Install Docker Desktop, then reopen PowerShell."
}

Write-Host ""

$tailscalePath = Get-TailscaleExe
if ($tailscalePath) {
    Write-Host "Tailscale CLI: found at $tailscalePath"
    try {
        & $tailscalePath status
    } catch {
        Write-Host "Tailscale status needs elevated PowerShell on this PC."
    }
} else {
    Write-Host "Tailscale CLI: not found"
    Write-Host "Install Tailscale and sign in."
}

Write-Host ""
Write-Host "Expected brain host for workers: 100.70.49.32"
