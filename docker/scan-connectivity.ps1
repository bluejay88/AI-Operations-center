param(
    [string]$BrainApi = "http://localhost:8088",
    [string]$SourceMachineId = "brain-gaming-pc"
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\lib.ps1"
$apiHeaders = Get-AiOpsApiHeaders -MachineId $SourceMachineId

$targets = @(
    @{ MachineId = "dev-laptop"; Ip = "100.71.82.122"; Label = "Dev Agent" },
    @{ MachineId = "research-laptop"; Ip = "100.90.219.88"; Label = "Research Agent" },
    @{ MachineId = "business-laptop"; Ip = "100.112.91.61"; Label = "Business Agent" }
)

$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if (!$tailscale -and (Test-Path "C:\Program Files\Tailscale\tailscale.exe")) {
    $tailscalePath = "C:\Program Files\Tailscale\tailscale.exe"
} elseif ($tailscale) {
    $tailscalePath = $tailscale.Source
} else {
    $tailscalePath = $null
}

function Send-Connection {
    param(
        [string]$TargetMachineId,
        [string]$Channel,
        [string]$Status,
        [Nullable[double]]$LatencyMs,
        [hashtable]$Metadata
    )

    $body = @{
        source_machine_id = $SourceMachineId
        target_machine_id = $TargetMachineId
        channel = $Channel
        status = $Status
        latency_ms = $LatencyMs
        metadata = $Metadata
    } | ConvertTo-Json -Depth 8

    Invoke-RestMethod -Method Post -Uri "$BrainApi/connections" -Headers $apiHeaders -Body $body -ContentType "application/json" | Out-Null
}

foreach ($target in $targets) {
    $pingStatus = "unknown"
    $latency = $null
    $pingOutput = ""
    $probeMethod = "icmp"

    if ($tailscalePath) {
        $probeMethod = "tailscale-cli"
        $pingOutput = (& $tailscalePath ping --c 1 --timeout 3s $target.Ip 2>&1) -join "`n"
        if ($pingOutput -match "pong") {
            $pingStatus = "online"
        } elseif ($pingOutput -match "Access is denied|failed to connect to local tailscaled|localapi") {
            $probeMethod = "icmp-fallback"
            $fallbackOutput = (& ping.exe -n 1 -w 1500 $target.Ip 2>&1) -join "`n"
            $reachable = $LASTEXITCODE -eq 0 -and $fallbackOutput -match "TTL="
            $pingOutput = "$pingOutput`nFallback ICMP:`n$fallbackOutput"
            $pingStatus = if ($reachable) { "online" } else { "unknown" }
        } elseif ($pingOutput -match "timeout|failed|error|no matching peer|no reply") {
            $probeMethod = "icmp-fallback-after-tailscale"
            $fallbackOutput = (& ping.exe -n 1 -w 1500 $target.Ip 2>&1) -join "`n"
            $reachable = $LASTEXITCODE -eq 0 -and $fallbackOutput -match "TTL="
            $pingOutput = "$pingOutput`nFallback ICMP:`n$fallbackOutput"
            $pingStatus = if ($reachable) { "online" } else { "offline" }
        }
        if ($pingOutput -match "time=([0-9.]+)ms") {
            $latency = [double]$Matches[1]
        } elseif ($pingOutput -match "in ([0-9.]+)ms") {
            $latency = [double]$Matches[1]
        }
    } else {
        $pingOutput = (& ping.exe -n 1 -w 1500 $target.Ip 2>&1) -join "`n"
        $reachable = $LASTEXITCODE -eq 0 -and $pingOutput -match "TTL="
        $pingStatus = if ($reachable) { "online" } else { "unknown" }
    }

    Send-Connection `
        -TargetMachineId $target.MachineId `
        -Channel "tailscale-ping" `
        -Status $pingStatus `
        -LatencyMs $latency `
        -Metadata @{ ip = $target.Ip; label = $target.Label; output = $pingOutput; probe_method = $probeMethod }

    $tcpClient = [System.Net.Sockets.TcpClient]::new()
    try {
        $connectTask = $tcpClient.ConnectAsync($target.Ip, 22)
        $ssh = $connectTask.Wait(2000) -and $tcpClient.Connected
    } catch {
        $ssh = $false
    } finally {
        $tcpClient.Dispose()
    }
    Send-Connection `
        -TargetMachineId $target.MachineId `
        -Channel "ssh-22" `
        -Status $(if ($ssh) { "online" } else { "blocked" }) `
        -LatencyMs $null `
        -Metadata @{ ip = $target.Ip; label = $target.Label }
}

Invoke-RestMethod "$BrainApi/readiness.json" -Headers $apiHeaders | ConvertTo-Json -Depth 8
