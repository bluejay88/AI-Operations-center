param(
    [string]$UserName = "aiopsbrain",
    [string]$SourceAuthorizedKeys = ""
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this PowerShell script as Administrator."
    }
}

function Read-PublicKeys {
    param([string[]]$Paths)

    $keys = New-Object System.Collections.Generic.List[string]
    foreach ($path in $Paths) {
        if (-not $path -or -not (Test-Path $path)) {
            continue
        }

        foreach ($line in Get-Content -Path $path -ErrorAction SilentlyContinue) {
            $trimmed = $line.Trim()
            if ($trimmed -match "^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+)\s+\S+(\s+.*)?$") {
                if (-not $keys.Contains($trimmed)) {
                    $keys.Add($trimmed)
                }
            }
        }
    }

    return $keys
}

Assert-Admin

$user = Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue
if (-not $user) {
    throw "Local user '$UserName' does not exist. Run docker\create-brain-ssh-user-admin.ps1 first."
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
if (!(Test-Path $userAuthorizedKeys)) {
    New-Item -ItemType File -Path $userAuthorizedKeys | Out-Null
}
if (!(Test-Path $adminAuthorizedKeys)) {
    New-Item -ItemType File -Path $adminAuthorizedKeys | Out-Null
}

$candidatePaths = @($userAuthorizedKeys, $adminAuthorizedKeys)
if ($SourceAuthorizedKeys) {
    $candidatePaths += $SourceAuthorizedKeys
}

$keys = Read-PublicKeys -Paths $candidatePaths
if ($keys.Count -eq 0) {
    throw "No valid public keys found. Paste laptop .pub lines into $userAuthorizedKeys or pass -SourceAuthorizedKeys."
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

Write-Host "Repaired Brain SSH public key files."
Write-Host "User authorized_keys: $userAuthorizedKeys"
Write-Host "Admin authorized_keys: $adminAuthorizedKeys"
Write-Host "Valid public keys installed: $($keys.Count)"
Write-Host ""
Write-Host "Now test from each laptop:"
Write-Host "ssh -vvv -i `"`$env:USERPROFILE\.ssh\ai_ops_brain_ed25519`" $UserName@100.70.49.32 hostname"
