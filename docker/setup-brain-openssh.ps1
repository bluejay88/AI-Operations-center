$ErrorActionPreference = "Stop"

$scriptPath = Join-Path (Get-Location) "docker\setup-brain-openssh-admin.ps1"
if (!(Test-Path $scriptPath)) {
    throw "Cannot find $scriptPath. Run this from the AI Operations Center repository root."
}

Write-Host "Launching Administrator OpenSSH setup for the Brain PC."
Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

