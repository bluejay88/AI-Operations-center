$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logDir = Join-Path $repoRoot "logs"
$logPath = Join-Path $logDir "brain-install.log"

if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

Start-Transcript -Path $logPath -Append

Write-Host "Installing AI Operations Center brain prerequisites..."
Write-Host "Log: $logPath"

Write-Host "Enabling WSL optional feature..."
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

Write-Host "Enabling Virtual Machine Platform optional feature..."
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

$installerPath = Join-Path $env:TEMP "DockerDesktopInstaller.exe"
Write-Host "Downloading Docker Desktop installer..."
curl.exe -L "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" -o $installerPath

Write-Host "Installing Docker Desktop..."
Start-Process -FilePath $installerPath -ArgumentList "install --quiet --accept-license" -Wait

Write-Host "Docker Desktop installer finished."
Write-Host "A Windows restart may be required before Docker works. After restart, launch Docker Desktop once to finish WSL setup."

Stop-Transcript
