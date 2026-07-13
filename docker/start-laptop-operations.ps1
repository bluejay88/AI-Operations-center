param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId,

    [string]$BrainHost = "100.70.49.32",

    [int]$WorkSeconds = 8,

    [int]$IdleSecondsBeforeOverlay = 45
)

$ErrorActionPreference = "Stop"

Write-Host "Starting AI Operations worker and heavy-work overlay for $MachineId"

.\docker\configure-worker-env.ps1 -MachineId $MachineId -BrainHost $BrainHost

$consoleInstaller = ".\laptop_packages\$MachineId\install.ps1"
if (Test-Path $consoleInstaller) {
    powershell -ExecutionPolicy Bypass -File $consoleInstaller -BrainHost $BrainHost
}

if (Test-Path ".env") {
    $envText = Get-Content ".env" -Raw
    if ($envText -match "(?m)^WORKER_WORK_SECONDS=") {
        $envText = $envText -replace "(?m)^WORKER_WORK_SECONDS=.*", "WORKER_WORK_SECONDS=$WorkSeconds"
    } else {
        $envText = $envText.TrimEnd() + "`r`nWORKER_WORK_SECONDS=$WorkSeconds`r`n"
    }
    Set-Content ".env" $envText
}

$overlayArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", ".\docker\show-heavy-work-overlay.ps1",
    "-MachineId", $MachineId,
    "-BrainHost", $BrainHost,
    "-IdleSecondsBeforeOverlay", $IdleSecondsBeforeOverlay
)

Start-Process powershell -ArgumentList $overlayArgs -WindowStyle Hidden

docker compose --profile worker up -d --build worker

Write-Host "Worker started for $MachineId."
Write-Host "Overlay monitor started. It appears only during active heavy work and hides when you use the laptop."
