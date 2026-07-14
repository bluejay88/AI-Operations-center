param(
    [int]$Runs = 25,
    [string]$BrainHost = "100.70.49.32"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\lib.ps1"
$apiHeaders = Get-AiOpsApiHeaders -MachineId "brain-gaming-pc"
$results = @()

for ($i = 1; $i -le $Runs; $i++) {
    Write-Host "Security audit run $i / $Runs"
    $guardian = Invoke-RestMethod "http://$BrainHost`:8088/security/guardian" -Headers $apiHeaders
    $health = Invoke-RestMethod "http://$BrainHost`:8088/health"
    $readiness = Invoke-RestMethod "http://$BrainHost`:8088/readiness.json" -Headers $apiHeaders
    $results += [pscustomobject]@{
        run = $i
        guardian_passed = $guardian.passed
        guardian_total = $guardian.total
        health = $health.status
        machines = @($readiness.machines).Count
        generated_at = $guardian.generated_at
    }
    if ($guardian.passed -lt $guardian.total) {
        throw "Security guardian failed on run $i with $($guardian.passed)/$($guardian.total)."
    }
}

$results | Format-Table -AutoSize
Write-Host "Completed $Runs security guardian audits successfully."
