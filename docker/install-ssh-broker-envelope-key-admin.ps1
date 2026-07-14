param(
    [Parameter(Mandatory=$true)][ValidateSet("dev-laptop", "research-laptop", "business-laptop")][string]$MachineId,
    [switch]$KeyFromStdin
)
$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw "Run as Administrator." }
if (-not $KeyFromStdin) { throw "The key must be supplied through standard input." }
$key = [Console]::In.ReadToEnd().Trim()
if ($key.Length -lt 32) { throw "Broker envelope key is too short." }
$root = Join-Path $env:ProgramData "AI-Ops"
if (-not (Test-Path $root)) { New-Item -ItemType Directory -Path $root | Out-Null }
$keyPath = Join-Path $root "ssh-broker-envelope-key"
$machinePath = Join-Path $root "machine-id"
Set-Content -LiteralPath $keyPath -Value $key -Encoding ascii -NoNewline
Set-Content -LiteralPath $machinePath -Value $MachineId -Encoding ascii -NoNewline
$grants = @("Administrators:F", "SYSTEM:F")
if (Get-LocalUser -Name "aiops-diagnostic" -ErrorAction SilentlyContinue) { $grants += "aiops-diagnostic:R" }
icacls $keyPath /inheritance:r /grant:r $grants | Out-Null
icacls $machinePath /inheritance:r /grant:r $grants | Out-Null
$key = $null
Write-Host "Installed the target-bound SSH broker authority for $MachineId without displaying it."
