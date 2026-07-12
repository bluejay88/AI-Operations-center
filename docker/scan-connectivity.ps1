param(
    [string]$BrainApi = "http://localhost:8088",
    [string]$SourceMachineId = "brain-gaming-pc"
)

$ErrorActionPreference = "Continue"

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

    Invoke-RestMethod -Method Post -Uri "$BrainApi/connections" -Body $body -ContentType "application/json" | Out-Null
}

foreach ($target in $targets) {
    $pingStatus = "unknown"
    $latency = $null
    $pingOutput = ""

    if ($tailscalePath) {
        $pingOutput = (& $tailscalePath ping --c 1 $target.Ip 2>&1) -join "`n"
        if ($pingOutput -match "pong") {
            $pingStatus = "online"
        } elseif ($pingOutput -match "timeout|failed|error|no matching peer") {
            $pingStatus = "offline"
        }
        if ($pingOutput -match "time=([0-9.]+)ms") {
            $latency = [double]$Matches[1]
        } elseif ($pingOutput -match "in ([0-9.]+)ms") {
            $latency = [double]$Matches[1]
        }
    } else {
        $reachable = Test-Connection -ComputerName $target.Ip -Count 1 -Quiet
        $pingStatus = if ($reachable) { "online" } else { "offline" }
    }

    Send-Connection `
        -TargetMachineId $target.MachineId `
        -Channel "tailscale-ping" `
        -Status $pingStatus `
        -LatencyMs $latency `
        -Metadata @{ ip = $target.Ip; label = $target.Label; output = $pingOutput }

    $ssh = Test-NetConnection -ComputerName $target.Ip -Port 22 -InformationLevel Quiet
    Send-Connection `
        -TargetMachineId $target.MachineId `
        -Channel "ssh-22" `
        -Status $(if ($ssh) { "online" } else { "blocked" }) `
        -LatencyMs $null `
        -Metadata @{ ip = $target.Ip; label = $target.Label }
}

Invoke-RestMethod "$BrainApi/readiness.json" | ConvertTo-Json -Depth 8
