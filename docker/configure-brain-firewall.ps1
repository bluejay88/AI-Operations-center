$ErrorActionPreference = "Stop"

$scriptPath = Join-Path (Get-Location) "docker\configure-brain-firewall-admin.ps1"
if (!(Test-Path $scriptPath)) {
    throw "Cannot find $scriptPath. Run this from the AI Operations Center repository root."
}

Write-Host "Launching Administrator firewall configuration for Tailscale worker access."
Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

