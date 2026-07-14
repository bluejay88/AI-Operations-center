param(
    [int]$Port = 22,
    [string]$AllowedRemoteAddress = "100.70.49.32/32",
    [Parameter(Mandatory = $true)]
    [string]$BrainPublicKey,
    [string]$UserName = "aiops-diagnostic"
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

if ($AllowedRemoteAddress -eq "100.64.0.0/10") {
    throw "The whole-tailnet SSH scope is prohibited. Pass the Brain Tailscale /32 address."
}

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
    Set-SshdConfigDirective -Path $sshdConfig -Name "PasswordAuthentication" -Value "no"
    Set-SshdConfigDirective -Path $sshdConfig -Name "PermitEmptyPasswords" -Value "no"
    Set-SshdConfigDirective -Path $sshdConfig -Name "KbdInteractiveAuthentication" -Value "no"
    Set-SshdConfigDirective -Path $sshdConfig -Name "AuthenticationMethods" -Value "publickey"
    Set-SshdConfigDirective -Path $sshdConfig -Name "MaxAuthTries" -Value "3"
    Set-SshdConfigDirective -Path $sshdConfig -Name "LogLevel" -Value "VERBOSE"
    Set-SshdConfigDirective -Path $sshdConfig -Name "AllowUsers" -Value $UserName
    Set-SshdConfigDirective -Path $sshdConfig -Name "AllowTcpForwarding" -Value "no"
    Set-SshdConfigDirective -Path $sshdConfig -Name "AllowAgentForwarding" -Value "no"
    Set-SshdConfigDirective -Path $sshdConfig -Name "PermitTunnel" -Value "no"
    Set-SshdConfigDirective -Path $sshdConfig -Name "GatewayPorts" -Value "no"
    Set-SshdConfigDirective -Path $sshdConfig -Name "PermitTTY" -Value "no"
    Set-SshdConfigDirective -Path $sshdConfig -Name "PermitUserEnvironment" -Value "no"
}

Restart-Service sshd

if (-not [string]::IsNullOrWhiteSpace($BrainPublicKey)) {
    if ($BrainPublicKey.Trim() -notmatch "^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+)\s+\S+(\s+.*)?$") {
        throw "BrainPublicKey is not a valid OpenSSH public key line."
    }

    $user = Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue
    if (-not $user) {
        $alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%_-"
        $bytes = New-Object byte[] 48
        [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        $randomPassword = -join ($bytes | ForEach-Object { $alphabet[$_ % $alphabet.Length] })
        $securePassword = ConvertTo-SecureString $randomPassword -AsPlainText -Force
        $user = New-LocalUser -Name $UserName -Password $securePassword -AccountNeverExpires -PasswordNeverExpires -UserMayNotChangePassword -Description "AI Operations read-only SSH diagnostics"
        $randomPassword = $null
    }

    $adminMembers = @(Get-LocalGroupMember -Group "Administrators" -ErrorAction Stop)
    if ($adminMembers.Name -match "\\$([regex]::Escape($UserName))$") {
        throw "Diagnostic account '$UserName' must not be a local administrator. Remove it from Administrators before continuing."
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

    $adminAuthorizedKeys = Join-Path $env:ProgramData "ssh\administrators_authorized_keys"
    if (Test-Path $adminAuthorizedKeys) {
        $cleaned = @(Get-Content $adminAuthorizedKeys | Where-Object { $_.Trim() -ne $BrainPublicKey.Trim() })
        Set-Content -Path $adminAuthorizedKeys -Value $cleaned -Encoding ascii
    }

    $brokerRoot = Join-Path $env:ProgramData "AI-Ops"
    $brokerScript = Join-Path $brokerRoot "ssh-diagnostic-command.ps1"
    if (-not (Test-Path $brokerRoot)) { New-Item -ItemType Directory -Path $brokerRoot | Out-Null }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "ssh-diagnostic-command.ps1") -Destination $brokerScript -Force
    icacls $brokerRoot /inheritance:r | Out-Null
    icacls $brokerRoot /grant "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "${UserName}:(OI)(CI)RX" | Out-Null
    Set-SshdConfigDirective -Path $sshdConfig -Name "ForceCommand" -Value "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File C:\ProgramData\AI-Ops\ssh-diagnostic-command.ps1"

    $configTest = & sshd -t -f $sshdConfig 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "sshd_config failed validation:`n$($configTest -join "`n")"
    }

    Restart-Service sshd
    Write-Host "Brain public key installed for $UserName."
}

Write-Host "OpenSSH Server is enabled and restricted to $AllowedRemoteAddress."
Write-Host "PasswordAuthentication=no; account=$UserName; privilege=standard-user; command_mode=allowlisted-only"
Write-Host "On this laptop, get your Tailscale IP with: tailscale ip -4"
Write-Host "From the Brain PC, test with: ssh -i `$env:USERPROFILE\.ssh\ai_ops_brain_to_laptops <LaptopWindowsUsername>@<LaptopTailscaleIP> hostname"
