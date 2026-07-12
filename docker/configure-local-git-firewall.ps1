$ErrorActionPreference = "Stop"

$scriptPath = Join-Path (Get-Location) "docker\configure-local-git-firewall-admin.ps1"
if (!(Test-Path $scriptPath)) {
    throw "Cannot find $scriptPath. Run this from the AI Operations Center repository root."
}

Write-Host "Launching Administrator firewall configuration for local Git over Tailscale."
Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
