param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("brain-gaming-pc", "business-laptop", "research-laptop", "dev-laptop")]
    [string]$Hostname
)

$ErrorActionPreference = "Stop"

. ".\docker\lib.ps1"
$tailscaleExe = Assert-TailscaleAvailable

Write-Host "Renaming this Tailscale device to $Hostname"
& $tailscaleExe set --hostname=$Hostname
Write-Host "Updated Tailscale status:"
& $tailscaleExe status

