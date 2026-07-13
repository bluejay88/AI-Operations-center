param(
    [string]$BrainHost = "100.70.49.32",
    [string]$BrainUser = $env:USERNAME,
    [ValidateSet("dev-laptop", "research-laptop", "business-laptop")]
    [string]$MachineId = "dev-laptop",
    [string]$AgentId = "orchestrator"
)

$ErrorActionPreference = "Continue"

function Write-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail
    )
    $status = if ($Ok) { "PASS" } else { "FAIL" }
    Write-Host "[$status] $Name - $Detail"
}

Write-Host "Testing Brain connectivity from $MachineId to $BrainHost"

$apiOk = $false
try {
    $health = Invoke-RestMethod -Uri "http://$BrainHost`:8088/health" -TimeoutSec 10
    $apiOk = $health.status -eq "ok"
    Write-Check "Brain API" $apiOk ($health | ConvertTo-Json -Compress)
} catch {
    Write-Check "Brain API" $false $_.Exception.Message
}

$listenerOk = $false
try {
    $payload = @{
        source_type = "machine"
        source_id = $MachineId
        event_type = "workload_update"
        subject = "$MachineId connectivity test"
        body = "$MachineId can reach the Brain listener endpoint and is testing send/receive flow."
        priority = 70
        metadata = @{
            machine_id = $MachineId
            agent_id = $AgentId
            test = "ssh-api-connectivity"
        }
    } | ConvertTo-Json -Depth 5
    $listener = Invoke-RestMethod -Method Post -Uri "http://$BrainHost`:8088/listener/events" -ContentType "application/json" -Body $payload -TimeoutSec 15
    $listenerOk = $null -ne $listener.event_id
    Write-Check "Listener send" $listenerOk ($listener | ConvertTo-Json -Compress)
} catch {
    Write-Check "Listener send" $false $_.Exception.Message
}

$speakerOk = $false
try {
    $feed = Invoke-RestMethod -Uri "http://$BrainHost`:8088/speaker/feed/$MachineId" -TimeoutSec 15
    $speakerOk = $null -ne $feed.instructions
    Write-Check "Speaker receive" $speakerOk ("messages=$($feed.messages.Count); instructionsLength=$($feed.instructions.Length)")
} catch {
    Write-Check "Speaker receive" $false $_.Exception.Message
}

$sshOk = $false
try {
    $sshOutput = ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 "$BrainUser@$BrainHost" hostname 2>&1
    $sshOk = $LASTEXITCODE -eq 0
    Write-Check "SSH to Brain" $sshOk ($sshOutput -join "`n")
} catch {
    Write-Check "SSH to Brain" $false $_.Exception.Message
}

Write-Host ""
Write-Host "Summary:"
Write-Host "API=$apiOk Listener=$listenerOk Speaker=$speakerOk SSH=$sshOk"
if (-not $sshOk) {
    Write-Host "If SSH fails but API passes, run docker\setup-brain-openssh.ps1 on the Brain PC and sign in with the Brain Windows username/password or set up SSH keys."
}
