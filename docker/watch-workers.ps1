param(
    [int]$Seconds = 10
)

$ErrorActionPreference = "Stop"

while ($true) {
    Clear-Host
    Write-Host "AI Operations worker status"
    Write-Host ""
    try {
        $response = Invoke-RestMethod -Uri "http://100.70.49.32:8088/status" -TimeoutSec 10
        Write-Host $response.status
    } catch {
        Write-Host "Could not reach brain API: $($_.Exception.Message)"
    }
    Start-Sleep -Seconds $Seconds
}

