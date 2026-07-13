param(
    [Parameter(Mandatory=$true)]
    [string]$PublicKey,

    [string]$UserName = "aiopsbrain"
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

$user = Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue
if (-not $user) {
    throw "Local user '$UserName' does not exist. Run docker\create-brain-ssh-user-admin.ps1 first."
}

$profileRoot = Join-Path "C:\Users" $UserName
$sshDir = Join-Path $profileRoot ".ssh"
$authorizedKeys = Join-Path $sshDir "authorized_keys"

if (!(Test-Path $profileRoot)) {
    New-Item -ItemType Directory -Path $profileRoot | Out-Null
}
if (!(Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir | Out-Null
}
if (!(Test-Path $authorizedKeys)) {
    New-Item -ItemType File -Path $authorizedKeys | Out-Null
}

$existing = Get-Content -Path $authorizedKeys -ErrorAction SilentlyContinue
if ($existing -notcontains $PublicKey) {
    Add-Content -Path $authorizedKeys -Value $PublicKey
    Write-Host "Added public key to $authorizedKeys"
} else {
    Write-Host "Public key already exists in $authorizedKeys"
}

icacls $sshDir /inheritance:r | Out-Null
icacls $sshDir /grant "${UserName}:(OI)(CI)F" "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
icacls $authorizedKeys /inheritance:r | Out-Null
icacls $authorizedKeys /grant "${UserName}:F" "Administrators:F" "SYSTEM:F" | Out-Null

Restart-Service sshd

Write-Host "Authorized key installed for $UserName."
Write-Host "Test from the laptop with: ssh -i `$env:USERPROFILE\.ssh\ai_ops_brain_ed25519 $UserName@100.70.49.32 hostname"
