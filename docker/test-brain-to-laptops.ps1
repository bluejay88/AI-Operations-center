param(
    [string]$DevIp = "100.71.82.122",
    [string]$ResearchIp = "100.90.219.88",
    [string]$BusinessIp = "100.112.91.61",
    [string]$LaptopUser = $env:USERNAME
)

$ErrorActionPreference = "Continue"

$targets = @(
    @{ MachineId = "dev-laptop"; Ip = $DevIp },
    @{ MachineId = "research-laptop"; Ip = $ResearchIp },
    @{ MachineId = "business-laptop"; Ip = $BusinessIp }
)

foreach ($target in $targets) {
    Write-Host ""
    Write-Host "Testing $($target.MachineId) at $($target.Ip)"
    $port = Test-NetConnection -ComputerName $target.Ip -Port 22 -WarningAction SilentlyContinue
    Write-Host "Port22=$($port.TcpTestSucceeded)"
    if ($port.TcpTestSucceeded) {
        $output = ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 "$LaptopUser@$($target.Ip)" hostname 2>&1
        $ok = $LASTEXITCODE -eq 0
        Write-Host "SSHKeyLogin=$ok"
        Write-Host ($output -join "`n")
    }
}
