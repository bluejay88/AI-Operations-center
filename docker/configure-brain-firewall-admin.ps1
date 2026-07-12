$ErrorActionPreference = "Stop"

$rules = @(
    @{
        Name = "AI Operations API over Tailscale"
        Port = 8088
    },
    @{
        Name = "AI Operations Postgres over Tailscale"
        Port = 5432
    }
)

foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Firewall rule already exists: $($rule.Name)"
        continue
    }

    New-NetFirewallRule `
        -DisplayName $rule.Name `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $rule.Port `
        -RemoteAddress "100.64.0.0/10" `
        -Profile Any | Out-Null

    Write-Host "Created firewall rule: $($rule.Name) on TCP $($rule.Port)"
}

