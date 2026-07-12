$ErrorActionPreference = "Continue"

$targets = @(
    @{ Name = "dev-laptop"; Ip = "100.71.82.122" },
    @{ Name = "research-agent-candidate"; Ip = "100.90.219.88" },
    @{ Name = "business-agent-candidate"; Ip = "100.112.91.61" }
)

$tailscale = "C:\Program Files\Tailscale\tailscale.exe"

foreach ($target in $targets) {
    Write-Host "Testing $($target.Name) at $($target.Ip)"
    if (Test-Path $tailscale) {
        & $tailscale ping --c 3 $target.Ip
    }
    Test-NetConnection -ComputerName $target.Ip -Port 8088 | Select-Object ComputerName,RemotePort,TcpTestSucceeded
    Write-Host ""
}

