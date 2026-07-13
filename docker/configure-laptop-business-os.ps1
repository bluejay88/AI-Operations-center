param(
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId,
    [string]$BrainHost = "100.70.49.32"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

Write-Host "Updating AI Operations Center repo..."
git pull origin master

Write-Host "Opening laptop Mini Phoenix package..."
powershell -ExecutionPolicy Bypass -File ".\laptop_packages\$MachineId\install.ps1" -BrainHost $BrainHost

Write-Host "Testing Brain API/listener/speaker..."
$agent = switch ($MachineId) {
    "dev-laptop" { "programmer" }
    "research-laptop" { "research-lead" }
    "business-laptop" { "business-manager" }
}

powershell -ExecutionPolicy Bypass -File ".\docker\test-brain-ssh-and-api.ps1" -MachineId $MachineId -BrainHost $BrainHost -BrainUser aiopsbrain -AgentId $agent

Write-Host "Publishing setup completion event..."
$payload = @{
    source_type = "machine"
    source_id = $MachineId
    event_type = "workload_update"
    subject = "$MachineId Business OS setup complete"
    body = "Pulled GitHub, opened Mini Phoenix package, tested Brain API/listener/speaker, and is ready for Business OS tasks."
    priority = 92
    metadata = @{
        machine_id = $MachineId
        agent_id = $agent
        setup = "business_os"
    }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post "http://$BrainHost`:8088/listener/events" -ContentType "application/json" -Body $payload

Write-Host "Business OS laptop configuration complete for $MachineId."
