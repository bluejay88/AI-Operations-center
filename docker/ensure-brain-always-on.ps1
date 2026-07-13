param(
    [int]$ConnectivityIntervalSeconds = 30,
    [string]$BrainApi = "http://100.70.49.32:8088",
    [switch]$InstallStartupTasks,
    [switch]$StartNow
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path $PSScriptRoot -Parent
$composeFile = Join-Path $repoRoot "docker-compose.yml"
$watchScript = Join-Path $PSScriptRoot "watch-connectivity.ps1"
$startMonitorScript = Join-Path $PSScriptRoot "start-connectivity-monitor.ps1"
$outputRoot = Join-Path $repoRoot "output"

if (!(Test-Path $composeFile)) {
    throw "Cannot find docker-compose.yml at $composeFile"
}
if (!(Test-Path $watchScript)) {
    throw "Cannot find connectivity watcher at $watchScript"
}
if (!(Test-Path $outputRoot)) {
    New-Item -ItemType Directory -Path $outputRoot | Out-Null
}

function Start-BrainServices {
    Push-Location $repoRoot
    try {
        docker compose --profile worker up -d ai-ops-api worker postgres | Tee-Object -FilePath (Join-Path $outputRoot "brain-always-on.log") -Append
    } finally {
        Pop-Location
    }
}

function Start-ConnectivityMonitor {
    & $startMonitorScript -IntervalSeconds $ConnectivityIntervalSeconds
}

function Install-StartupTask {
    param(
        [string]$TaskName,
        [string]$Command
    )

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"$Command`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "AI Operations Center always-on Brain service task." -Force | Out-Null
    Write-Host "Installed startup task: $TaskName"
}

if ($InstallStartupTasks) {
    $quotedRepo = $repoRoot.Replace("'", "''")
    $quotedStartMonitor = $startMonitorScript.Replace("'", "''")
    Install-StartupTask `
        -TaskName "AI Operations Center - Brain Services" `
        -Command "Set-Location '$quotedRepo'; docker compose --profile worker up -d ai-ops-api worker postgres"
    Install-StartupTask `
        -TaskName "AI Operations Center - Connectivity Monitor" `
        -Command "& '$quotedStartMonitor' -IntervalSeconds $ConnectivityIntervalSeconds"
}

if ($StartNow -or !$InstallStartupTasks) {
    Start-BrainServices
    Start-ConnectivityMonitor
}

Write-Host "AI Operations Center always-on configuration complete."
Write-Host "Brain API: $BrainApi"
Write-Host "Dashboard: $BrainApi/dashboard/"
