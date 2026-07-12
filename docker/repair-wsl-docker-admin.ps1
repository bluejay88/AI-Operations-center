$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logDir = Join-Path $repoRoot "logs"
$logPath = Join-Path $logDir "wsl-docker-repair.log"

if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

Start-Transcript -Path $logPath -Append

Write-Host "Repairing WSL and Docker Desktop setup..."
Write-Host "Log: $logPath"

Write-Host "Ensuring WSL optional feature is enabled..."
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

Write-Host "Ensuring Virtual Machine Platform optional feature is enabled..."
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

Write-Host "Installing WSL package without a default Linux distribution..."
wsl.exe --install --no-distribution --web-download

Write-Host "Updating WSL package..."
wsl.exe --update --web-download

$installerPath = Join-Path $env:TEMP "DockerDesktopInstaller.exe"
if (!(Test-Path $installerPath)) {
    Write-Host "Downloading Docker Desktop installer..."
    curl.exe -L "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" -o $installerPath
}

Write-Host "Installing Docker Desktop..."
Start-Process -FilePath $installerPath -ArgumentList "install --quiet --accept-license" -Wait

Write-Host "Repair completed. Restart Windows if WSL or Docker requests it."
Stop-Transcript

