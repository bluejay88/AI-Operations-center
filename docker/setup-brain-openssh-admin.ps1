param(
    [int]$Port = 22
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

Write-Host "Installing and enabling Windows OpenSSH Server on the Brain PC..."
$capability = Get-WindowsCapability -Online | Where-Object Name -like "OpenSSH.Server*"
if (-not $capability) {
    throw "OpenSSH.Server Windows capability was not found on this system."
}

if ($capability.State -ne "Installed") {
    Add-WindowsCapability -Online -Name $capability.Name
}

Set-Service -Name sshd -StartupType Automatic
Start-Service -Name sshd

$service = Get-Service -Name sshd
Write-Host "sshd service status: $($service.Status)"

$ruleName = "AI-Ops-Brain-OpenSSH-Tailscale"
$existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Set-NetFirewallRule -Name $ruleName -Enabled True -Direction Inbound -Action Allow -Profile Any
    Set-NetFirewallAddressFilter -AssociatedNetFirewallRule $existing -RemoteAddress "100.64.0.0/10"
    Set-NetFirewallPortFilter -AssociatedNetFirewallRule $existing -Protocol TCP -LocalPort $Port
    Write-Host "Updated firewall rule: $ruleName"
} else {
    New-NetFirewallRule `
        -Name $ruleName `
        -DisplayName "AI Ops Brain OpenSSH over Tailscale" `
        -Enabled True `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $Port `
        -RemoteAddress "100.64.0.0/10" `
        -Profile Any | Out-Null
    Write-Host "Created firewall rule: $ruleName on TCP $Port for Tailscale CGNAT only."
}

Write-Host "Brain OpenSSH setup complete."
Write-Host "Test from a laptop with: ssh $env:USERNAME@100.70.49.32 hostname"

