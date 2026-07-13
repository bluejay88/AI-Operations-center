param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId,

    [Parameter(Mandatory=$false)]
    [string]$BrainHost = "100.70.49.32",

    [switch]$RenameTailscale
)

$ErrorActionPreference = "Stop"

if ($RenameTailscale) {
    .\docker\rename-this-pc.ps1 -Hostname $MachineId
}

.\docker\configure-worker-env.ps1 -MachineId $MachineId -BrainHost $BrainHost
.\docker\check-brain.ps1 -BrainHost $BrainHost

$consoleInstaller = ".\laptop_packages\$MachineId\install.ps1"
if (Test-Path $consoleInstaller) {
    powershell -ExecutionPolicy Bypass -File $consoleInstaller -BrainHost $BrainHost
}

.\docker\worker-bootstrap.ps1 -MachineId $MachineId
