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

function Write-Check {
    param([string]$Name, [bool]$Ok, [string]$Detail = "")
    $status = if ($Ok) { "PASS" } else { "FAIL" }
    $color = if ($Ok) { "Green" } else { "Red" }
    Write-Host "[$status] $Name $Detail" -ForegroundColor $color
}

function Get-ValidKeyCount {
    param([string]$Path)
    if (!(Test-Path $Path)) {
        return 0
    }

    $count = 0
    foreach ($line in Get-Content -Path $Path -ErrorAction SilentlyContinue) {
        if ($line.Trim() -match "^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+)\s+\S+(\s+.*)?$") {
            $count += 1
        }
    }
    return $count
}

Assert-Admin

$user = Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue
if (-not $user) {
    throw "Local user '$UserName' does not exist. Run docker\create-brain-ssh-user-admin.ps1 first."
}

if (-not $user.Enabled) {
    Enable-LocalUser -Name $UserName
}
Write-Check "Local user enabled" ((Get-LocalUser -Name $UserName).Enabled) $UserName

$programDataSsh = Join-Path $env:ProgramData "ssh"
$sshdConfig = Join-Path $programDataSsh "sshd_config"
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

$userKeyCount = Get-ValidKeyCount -Path $userAuthorizedKeys
$adminKeyCount = Get-ValidKeyCount -Path $adminAuthorizedKeys
Write-Check "User authorized_keys valid keys" ($userKeyCount -gt 0) "$userAuthorizedKeys count=$userKeyCount"
Write-Check "Admin authorized_keys valid keys" ($adminKeyCount -gt 0) "$adminAuthorizedKeys count=$adminKeyCount"

$isAdmin = $false
try {
    $isAdmin = [bool](Get-LocalGroupMember -Group "Administrators" -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match "\\$([regex]::Escape($UserName))$" -or $_.Name -eq $UserName
    })
} catch {
    $isAdmin = $false
}
Write-Check "Administrator group check" $true "is_admin=$isAdmin"

if (!(Test-Path $sshdConfig)) {
    New-Item -ItemType File -Path $sshdConfig | Out-Null
}

$configText = Get-Content -Path $sshdConfig -Raw -ErrorAction SilentlyContinue
if ($configText -notmatch "(?im)^\s*PubkeyAuthentication\s+yes\s*$") {
    Add-Content -Path $sshdConfig -Value "`r`nPubkeyAuthentication yes"
}
if ($configText -notmatch "(?im)^\s*AuthorizedKeysFile\s+\.ssh/authorized_keys\s*$") {
    Add-Content -Path $sshdConfig -Value "AuthorizedKeysFile .ssh/authorized_keys"
}
if ($configText -notmatch "(?is)Match\s+Group\s+administrators.*?AuthorizedKeysFile\s+__PROGRAMDATA__/ssh/administrators_authorized_keys") {
    Add-Content -Path $sshdConfig -Value @"

Match Group administrators
       AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys
"@
}

icacls $sshDir /inheritance:r | Out-Null
icacls $sshDir /grant "${UserName}:(OI)(CI)F" "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
icacls $userAuthorizedKeys /inheritance:r | Out-Null
icacls $userAuthorizedKeys /grant "${UserName}:F" "Administrators:F" "SYSTEM:F" | Out-Null
icacls $adminAuthorizedKeys /inheritance:r | Out-Null
icacls $adminAuthorizedKeys /grant "Administrators:F" "SYSTEM:F" | Out-Null
icacls $sshdConfig /inheritance:r | Out-Null
icacls $sshdConfig /grant "Administrators:F" "SYSTEM:F" | Out-Null

$configTest = & sshd -t -f $sshdConfig 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "sshd_config failed validation:`n$($configTest -join "`n")"
}
Write-Check "sshd_config validation" $true $sshdConfig

Restart-Service sshd
$service = Get-Service sshd
Write-Check "sshd service" ($service.Status -eq "Running") "status=$($service.Status)"

Write-Host ""
Write-Host "Brain SSH config repaired. Test from laptop:"
Write-Host "ssh -vvv -i `"`$env:USERPROFILE\.ssh\ai_ops_brain_ed25519`" $UserName@100.70.49.32 hostname"
