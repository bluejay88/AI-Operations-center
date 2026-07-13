param(
    [string]$UserName = "aiopsbrain",
    [switch]$Admin
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this PowerShell script as Administrator."
    }
}

Assert-Admin

Write-Host "Creating or updating local SSH user: $UserName"
Write-Host "You will be prompted for a password. No characters will appear while typing."

$existing = Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue
if (-not $existing) {
    net user $UserName * /add
} else {
    net user $UserName *
}

net user $UserName /active:yes | Out-Null
net localgroup "Remote Management Users" $UserName /add 2>$null | Out-Null

if ($Admin) {
    net localgroup Administrators $UserName /add 2>$null | Out-Null
    Write-Host "$UserName was added to Administrators. Use this only for trusted AI Ops management."
} else {
    Write-Host "$UserName was added to Remote Management Users. Re-run with -Admin only if remote admin operations are required."
}

Write-Host "Local SSH user is ready."
Write-Host "Test from a laptop with: ssh $UserName@100.70.49.32 hostname"
