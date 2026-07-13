param(
    [int]$Port = 22,
    [string]$AllowedRemoteAddress = "100.64.0.0/10",
    [string]$BrainPublicKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBoby+MkyYxc2aeEgz2npB31pDw5ICYhKhNmpDc3V9dm brain-pc-ai-ops",
    [string]$UserName = $env:USERNAME,
    [switch]$AllowPasswordAuthentication
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

function Set-SshdConfigDirective {
    param(
        [string]$Path,
        [string]$Name,
        [string]$Value
    )

    $lines = @()
    if (Test-Path $Path) {
        $lines = @(Get-Content -Path $Path)
    }

    $pattern = "^\s*#?\s*$([regex]::Escape($Name))\s+"
    $updated = $false
    $newLines = foreach ($line in $lines) {
        if ($line -match $pattern) {
            if (-not $updated) {
                "$Name $Value"
                $updated = $true
            }
        } else {
            $line
        }
    }

    if (-not $updated) {
        $newLines += "$Name $Value"
    }

    Set-Content -Path $Path -Value $newLines -Encoding ascii
}

Write-Host "Installing and enabling Windows OpenSSH Server..."
$capability = Get-WindowsCapability -Online | Where-Object Name -like "OpenSSH.Server*"
if (-not $capability) {
    throw "OpenSSH.Server Windows capability was not found on this system."
}
if ($capability.State -ne "Installed") {
    Add-WindowsCapability -Online -Name $capability.Name
}

Set-Service -Name sshd -StartupType Automatic
Start-Service -Name sshd

Write-Host "Removing older broad AI Ops OpenSSH firewall rule if present..."
Get-NetFirewallRule -Name "AI-Ops-OpenSSH-Tailscale" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
Get-NetFirewallRule -Name "AI-Ops-Worker-OpenSSH-Tailscale-Only" -ErrorAction SilentlyContinue | Remove-NetFirewallRule

Write-Host "Creating Tailscale-only inbound SSH firewall rule..."
New-NetFirewallRule `
    -Name "AI-Ops-Worker-OpenSSH-Tailscale-Only" `
    -DisplayName "AI Ops Worker OpenSSH - Tailscale Only" `
    -Enabled True `
    -Direction Inbound `
    -Protocol TCP `
    -Action Allow `
    -LocalPort $Port `
    -RemoteAddress $AllowedRemoteAddress `
    -Profile Any | Out-Null

$sshdConfig = "$env:ProgramData\ssh\sshd_config"
if (Test-Path $sshdConfig) {
    Set-SshdConfigDirective -Path $sshdConfig -Name "PubkeyAuthentication" -Value "yes"
    Set-SshdConfigDirective -Path $sshdConfig -Name "PasswordAuthentication" -Value $(if ($AllowPasswordAuthentication) { "yes" } else { "no" })
    Set-SshdConfigDirective -Path $sshdConfig -Name "PermitEmptyPasswords" -Value "no"
    Set-SshdConfigDirective -Path $sshdConfig -Name "KbdInteractiveAuthentication" -Value "no"
    Set-SshdConfigDirective -Path $sshdConfig -Name "MaxAuthTries" -Value "3"
    Set-SshdConfigDirective -Path $sshdConfig -Name "LogLevel" -Value "VERBOSE"
}

Restart-Service sshd

if (-not [string]::IsNullOrWhiteSpace($BrainPublicKey)) {
    if ($BrainPublicKey.Trim() -notmatch "^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+)\s+\S+(\s+.*)?$") {
        throw "BrainPublicKey is not a valid OpenSSH public key line."
    }

    $user = Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue
    if (-not $user) {
        throw "Local user '$UserName' was not found. Run whoami and pass -UserName with the local username portion."
    }

    $profileRoot = Join-Path "C:\Users" $UserName
    $sshDir = Join-Path $profileRoot ".ssh"
    $authorizedKeys = Join-Path $sshDir "authorized_keys"

    if (-not (Test-Path $sshDir)) {
        New-Item -ItemType Directory -Path $sshDir | Out-Null
    }
    if (-not (Test-Path $authorizedKeys)) {
        New-Item -ItemType File -Path $authorizedKeys | Out-Null
    }

    $existingKeys = Get-Content -Path $authorizedKeys -ErrorAction SilentlyContinue
    if (-not ($existingKeys -contains $BrainPublicKey.Trim())) {
        Add-Content -Path $authorizedKeys -Value $BrainPublicKey.Trim()
    }

    icacls $sshDir /inheritance:r | Out-Null
    icacls $sshDir /grant "${UserName}:(OI)(CI)F" "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
    icacls $authorizedKeys /inheritance:r | Out-Null
    icacls $authorizedKeys /grant "${UserName}:F" "Administrators:F" "SYSTEM:F" | Out-Null

    $isAdminUser = $false
    try {
        $adminMembers = Get-LocalGroupMember -Group "Administrators" -ErrorAction Stop
        $isAdminUser = $adminMembers.Name -match "\\$UserName$|^$UserName$"
    } catch {
        $isAdminUser = $false
    }

    if ($isAdminUser) {
        $programDataSsh = Join-Path $env:ProgramData "ssh"
        $adminAuthorizedKeys = Join-Path $programDataSsh "administrators_authorized_keys"
        if (-not (Test-Path $programDataSsh)) {
            New-Item -ItemType Directory -Path $programDataSsh | Out-Null
        }
        if (-not (Test-Path $adminAuthorizedKeys)) {
            New-Item -ItemType File -Path $adminAuthorizedKeys | Out-Null
        }
        $adminKeys = Get-Content -Path $adminAuthorizedKeys -ErrorAction SilentlyContinue
        if (-not ($adminKeys -contains $BrainPublicKey.Trim())) {
            Add-Content -Path $adminAuthorizedKeys -Value $BrainPublicKey.Trim()
        }
        icacls $adminAuthorizedKeys /inheritance:r | Out-Null
        icacls $adminAuthorizedKeys /grant "Administrators:F" "SYSTEM:F" | Out-Null
    }

    $configTest = & sshd -t -f $sshdConfig 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "sshd_config failed validation:`n$($configTest -join "`n")"
    }

    Restart-Service sshd
    Write-Host "Brain public key installed for $UserName."
}

Write-Host "OpenSSH Server is enabled and restricted to $AllowedRemoteAddress."
Write-Host "PasswordAuthentication=$($(if ($AllowPasswordAuthentication) { 'yes' } else { 'no' }))"
Write-Host "On this laptop, get your Tailscale IP with: tailscale ip -4"
Write-Host "From the Brain PC, test with: ssh -i `$env:USERPROFILE\.ssh\ai_ops_brain_to_laptops <LaptopWindowsUsername>@<LaptopTailscaleIP> hostname"
