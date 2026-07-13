param(
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

function Normalize-PublicKey {
    param([string]$Line)

    $trimmed = $Line.Trim()
    if ($trimmed -match "^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+)\s+\S+(\s+.*)?$") {
        return $trimmed
    }

    return ""
}

Assert-Admin

$user = Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue
if (-not $user) {
    throw "Local user '$UserName' does not exist. Run docker\create-brain-ssh-user-admin.ps1 first."
}

Write-Host "Paste each laptop PUBLIC key, one at a time."
Write-Host "A valid public key starts with ssh-ed25519, ssh-rsa, or ecdsa-sha2."
Write-Host "Do not paste private keys that start with -----BEGIN OPENSSH PRIVATE KEY-----."
Write-Host "Press Enter on a blank line when finished."
Write-Host ""

$keys = New-Object System.Collections.Generic.List[string]
while ($true) {
    $line = Read-Host "Public key"
    if ([string]::IsNullOrWhiteSpace($line)) {
        break
    }

    $key = Normalize-PublicKey -Line $line
    if (-not $key) {
        Write-Host "Skipped invalid line. It must start with ssh-ed25519, ssh-rsa, or ecdsa-sha2." -ForegroundColor Yellow
        continue
    }

    if (-not $keys.Contains($key)) {
        $keys.Add($key)
        Write-Host "Accepted key $($keys.Count)." -ForegroundColor Green
    } else {
        Write-Host "Duplicate key skipped." -ForegroundColor Yellow
    }
}

if ($keys.Count -eq 0) {
    throw "No valid public keys were pasted."
}

$programDataSsh = Join-Path $env:ProgramData "ssh"
$adminAuthorizedKeys = Join-Path $programDataSsh "administrators_authorized_keys"
$profileRoot = Join-Path "C:\Users" $UserName
$sshDir = Join-Path $profileRoot ".ssh"
$userAuthorizedKeys = Join-Path $sshDir "authorized_keys"

if (!(Test-Path $programDataSsh)) {
    New-Item -ItemType Directory -Path $programDataSsh | Out-Null
}
if (!(Test-Path $profileRoot)) {
    New-Item -ItemType Directory -Path $profileRoot | Out-Null
}
if (!(Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir | Out-Null
}

Set-Content -Path $userAuthorizedKeys -Value $keys -Encoding ascii
Set-Content -Path $adminAuthorizedKeys -Value $keys -Encoding ascii

icacls $sshDir /inheritance:r | Out-Null
icacls $sshDir /grant "${UserName}:(OI)(CI)F" "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
icacls $userAuthorizedKeys /inheritance:r | Out-Null
icacls $userAuthorizedKeys /grant "${UserName}:F" "Administrators:F" "SYSTEM:F" | Out-Null
icacls $adminAuthorizedKeys /inheritance:r | Out-Null
icacls $adminAuthorizedKeys /grant "Administrators:F" "SYSTEM:F" | Out-Null

Restart-Service sshd

Write-Host ""
Write-Host "Installed $($keys.Count) public key(s) for $UserName." -ForegroundColor Green
Write-Host "User authorized_keys: $userAuthorizedKeys"
Write-Host "Admin authorized_keys: $adminAuthorizedKeys"
Write-Host ""
Write-Host "Test from each laptop:"
Write-Host "ssh -i `"`$env:USERPROFILE\.ssh\ai_ops_brain_ed25519`" $UserName@100.70.49.32 hostname"
