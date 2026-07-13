param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId,

    [string]$Branch = "master",
    [string]$BrainHost = "100.70.49.32",
    [switch]$SkipBenchmark
)

$ErrorActionPreference = "Stop"

if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or not on PATH."
}

if (!(Test-Path ".git")) {
    throw "Run this from the AI Operations Center repository folder."
}

$origin = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($origin)) {
    throw "No git origin is configured on this laptop. Clone from GitHub or run git remote add origin <url>."
}

git fetch origin $Branch
git checkout $Branch
git pull --ff-only origin $Branch

.\docker\configure-worker-env.ps1 -MachineId $MachineId -BrainHost $BrainHost
.\docker\check-brain.ps1 -BrainHost $BrainHost

$consoleInstaller = ".\laptop_packages\$MachineId\install.ps1"
if (Test-Path $consoleInstaller) {
    powershell -ExecutionPolicy Bypass -File $consoleInstaller -BrainHost $BrainHost
}

docker compose up -d worker

if (!$SkipBenchmark) {
    .\docker\run-benchmark.ps1 -MachineId $MachineId -BrainHost $BrainHost
}

Write-Host "Worker updated and running for $MachineId."
Write-Host "Brain status: http://$BrainHost`:8088/status"
