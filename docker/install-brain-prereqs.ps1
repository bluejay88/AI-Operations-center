$ErrorActionPreference = "Stop"

$scriptPath = Join-Path (Get-Location) "docker\install-brain-prereqs-admin.ps1"
if (!(Test-Path $scriptPath)) {
    throw "Cannot find $scriptPath. Run this from the AI Operations Center repository root."
}

Write-Host "Launching Administrator installer. Approve the Windows UAC prompt."
Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

