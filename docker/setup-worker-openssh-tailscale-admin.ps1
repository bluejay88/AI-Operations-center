param(
    [int]$Port = 22,
    [string]$AllowedRemoteAddress = "100.64.0.0/10"
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
    $config = Get-Content $sshdConfig
    if (-not ($config | Select-String -Pattern "^\s*PubkeyAuthentication\s+yes" -Quiet)) {
        Add-Content $sshdConfig "PubkeyAuthentication yes"
    }
    if (-not ($config | Select-String -Pattern "^\s*PasswordAuthentication\s+yes" -Quiet)) {
        Add-Content $sshdConfig "PasswordAuthentication yes"
    }
}

Restart-Service sshd

Write-Host "OpenSSH Server is enabled and restricted to $AllowedRemoteAddress."
Write-Host "On this laptop, get your Tailscale IP with: tailscale ip -4"
Write-Host "From the Brain PC, test with: ssh <LaptopWindowsUsername>@<LaptopTailscaleIP> hostname"
