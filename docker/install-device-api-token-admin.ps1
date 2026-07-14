param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev-laptop", "research-laptop", "business-laptop")]
    [string]$MachineId,
    [Parameter(Mandatory=$true)]
    [string]$DeviceToken
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw "Run as Administrator." }
if ($DeviceToken.Length -lt 32) { throw "Device token is too short." }
$root = Join-Path $env:ProgramData "AI-Ops"
if (-not (Test-Path $root)) { New-Item -ItemType Directory -Path $root | Out-Null }
$path = Join-Path $root "device-api-token"
Set-Content -LiteralPath $path -Value $DeviceToken -Encoding ascii -NoNewline
icacls $root /inheritance:r /grant:r "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Users:(OI)(CI)RX" | Out-Null
icacls $path /inheritance:r /grant:r "Administrators:F" "SYSTEM:F" "Users:R" | Out-Null
Set-Content -LiteralPath (Join-Path $root "machine-id") -Value $MachineId -Encoding ascii -NoNewline
Write-Host "Installed the scoped API credential for $MachineId. The token value was not displayed."
