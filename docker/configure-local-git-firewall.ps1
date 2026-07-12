param(
    [int]$Port = 9418
)

$ErrorActionPreference = "Stop"

$ruleName = "AI Operations Local Git over Tailscale"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if ($existing) {
    Set-NetFirewallRule -DisplayName $ruleName -Enabled True
    Set-NetFirewallPortFilter -AssociatedNetFirewallRule $existing -Protocol TCP -LocalPort $Port
} else {
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $Port `
        -RemoteAddress "100.64.0.0/10" | Out-Null
}

Write-Host "Firewall allows Tailscale clients to reach local Git on TCP $Port."
