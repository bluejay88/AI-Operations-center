param(
    [Parameter(Mandatory=$true)]
    [string]$Title,

    [Parameter(Mandatory=$true)]
    [string]$Body,

    [string]$BrainHost = "100.70.49.32",
    [string]$Requester = "codex",
    [string[]]$TargetMachines = @("brain-gaming-pc", "dev-laptop"),
    [string[]]$DeliveryMethods = @("dashboard"),
    [string]$ProjectId = "",
    [string]$ThreadKey = "",
    [int]$Priority = 90,
    [switch]$CreatePeerRequests
)

$ErrorActionPreference = "Stop"

function Normalize-Host {
    param([string]$Value)
    return ($Value.Trim() -replace "^https?://", "" -split "/")[0] -split ":" | Select-Object -First 1
}

$BrainHost = Normalize-Host $BrainHost
$payload = @{
    title = $Title
    body = $Body
    requester = $Requester
    target_machines = $TargetMachines
    delivery_methods = $DeliveryMethods
    priority = $Priority
    create_peer_requests = [bool]$CreatePeerRequests
    metadata = @{
        source = "powershell-codex-pipe"
        host = $env:COMPUTERNAME
        user = "$env:USERDOMAIN\$env:USERNAME"
    }
}
if ($ProjectId) { $payload.project_id = $ProjectId }
if ($ThreadKey) { $payload.thread_key = $ThreadKey }

$response = Invoke-RestMethod -Method Post `
    -Uri "http://$BrainHost`:8088/codex/pipeline" `
    -ContentType "application/json" `
    -Body ($payload | ConvertTo-Json -Depth 12) `
    -TimeoutSec 30

$response | ConvertTo-Json -Depth 12
