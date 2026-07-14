param(
    [int]$Seconds = 10
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\lib.ps1"
$machineId = if ($env:COMPUTERNAME -match '(?i)^dev-laptop$') { "dev-laptop" } elseif ($env:COMPUTERNAME -match '(?i)^research-laptop$') { "research-laptop" } elseif ($env:COMPUTERNAME -match '(?i)^business-laptop$') { "business-laptop" } else { "brain-gaming-pc" }
$apiHeaders = Get-AiOpsApiHeaders -MachineId $machineId

while ($true) {
    Clear-Host
    Write-Host "AI Operations worker status"
    Write-Host ""
    try {
        $response = Invoke-RestMethod -Uri "http://100.70.49.32:8088/status" -Headers $apiHeaders -TimeoutSec 10
        Write-Host $response.status
    } catch {
        Write-Host "Could not reach brain API: $($_.Exception.Message)"
    }
    Start-Sleep -Seconds $Seconds
}
