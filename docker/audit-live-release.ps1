param(
    [string]$BaseUrl = "http://127.0.0.1:8088",
    [int]$TimeoutSec = 15
)

$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.Trim().TrimEnd("/")
$script:Passed = 0
$script:Failed = 0
$script:Warnings = 0
. "$PSScriptRoot\lib.ps1"
$script:ApiHeaders = Get-AiOpsApiHeaders -MachineId "brain-gaming-pc"

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Invoke-JsonGet {
    param([string]$Path)
    return Invoke-RestMethod -Method Get -Uri "$BaseUrl$Path" -TimeoutSec $TimeoutSec -Headers ($script:ApiHeaders + @{ "Cache-Control" = "no-cache" })
}

function Test-Invariants {
    param([object]$Invariants, [string]$Label)
    Assert-True ($null -ne $Invariants) "$Label invariants are missing"
    $properties = @($Invariants.PSObject.Properties)
    Assert-True ($properties.Count -gt 0) "$Label invariants are empty"
    foreach ($property in $properties) {
        Assert-True ([bool]$property.Value) "$Label invariant failed: $($property.Name)"
    }
}

function Test-Step {
    param([string]$Name, [scriptblock]$Check)
    try {
        $evidence = & $Check
        $script:Passed++
        Write-Host "[PASS] $Name - $evidence" -ForegroundColor Green
    } catch {
        $script:Failed++
        Write-Host "[FAIL] $Name - $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Test-Warning {
    param([string]$Name, [scriptblock]$Check)
    try {
        $evidence = & $Check
        Write-Host "[PASS] $Name - $evidence" -ForegroundColor Green
    } catch {
        $script:Warnings++
        Write-Host "[WARN] $Name - $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Test-Page {
    param([string]$Path, [string]$ExpectedMachineId)
    $response = Invoke-WebRequest -Method Get -Uri "$BaseUrl$Path" -TimeoutSec $TimeoutSec -UseBasicParsing -Headers @{ "Cache-Control" = "no-cache" }
    Assert-True ($response.StatusCode -eq 200) "$Path returned HTTP $($response.StatusCode)"
    $csp = [string]$response.Headers["Content-Security-Policy"]
    Assert-True ($csp -match "script-src 'self'") "$Path CSP does not restrict scripts to self"
    Assert-True ($csp -notmatch "unsafe-inline") "$Path CSP permits unsafe-inline"
    Assert-True ($response.Content -notmatch '(?i)<script(?![^>]*\bsrc\s*=)[^>]*>') "$Path contains an inline script blocked by CSP"
    Assert-True ($response.Content -notmatch '(?i)\son[a-z]+\s*=') "$Path contains an inline event handler blocked by CSP"

    if ($ExpectedMachineId) {
        Assert-True ($ExpectedMachineId -match '^[a-z0-9]+(?:-[a-z0-9]+)*$') "Unsafe expected machine identity: $ExpectedMachineId"
        $identityMatch = [regex]::Match($response.Content, 'data-machine-id\s*=\s*[''"]([^''"]+)[''"]', 'IgnoreCase')
        Assert-True ($identityMatch.Success) "$Path has no data-machine-id identity"
        $actualMachineId = $identityMatch.Groups[1].Value
        Assert-True ($actualMachineId -eq $ExpectedMachineId) "$Path identity is '$actualMachineId', expected '$ExpectedMachineId'"
        Assert-True ($actualMachineId -match '^[a-z0-9]+(?:-[a-z0-9]+)*$') "$Path exposes an unsafe machine identity"
        return "HTTP 200; machine=$actualMachineId; CSP=self-only"
    }
    return "HTTP 200; CSP=self-only"
}

Write-Host "Read-only AI Operations Center release audit: $BaseUrl"

Test-Step "Health" {
    $health = Invoke-JsonGet "/health"
    Assert-True ($health.status -eq "ok") "health status is '$($health.status)'"
    "status=ok"
}

$script:Tasks = $null
Test-Step "Lifetime task accounting" {
    $script:Tasks = Invoke-JsonGet "/tasks?limit=3"
    Assert-True ($script:Tasks.list.limit -eq 3) "task list did not honor limit=3"
    Assert-True ($script:Tasks.tasks.Count -le 3) "task list returned more than 3 rows"
    Assert-True ($script:Tasks.task_summary.contract.scope -eq "lifetime") "task summary is not lifetime scoped"
    Assert-True ([bool]$script:Tasks.task_summary.contract.recent_list_independent) "task total depends on limited rows"
    Assert-True ($script:Tasks.task_accounting_audit.status -eq "passed") "task accounting audit did not pass"
    Test-Invariants $script:Tasks.task_summary.contract.invariants "task accounting"
    $machineCompleted = 0L
    foreach ($machine in $script:Tasks.task_summary.by_machine.PSObject.Properties) {
        $machineCompleted += [long]$machine.Value.completed
    }
    Assert-True ($machineCompleted -eq [long]$script:Tasks.task_summary.completed_total) "global completed total does not equal per-machine sum"
    "completed=$($script:Tasks.task_summary.completed_total); recent=$($script:Tasks.tasks.Count); machineSum=$machineCompleted"
}

$script:Readiness = $null
Test-Step "Readiness accounting parity" {
    Assert-True ($null -ne $script:Tasks) "task accounting prerequisite failed"
    $script:Readiness = Invoke-JsonGet "/readiness.json"
    Assert-True ([long]$script:Readiness.task_summary.completed_total -eq [long]$script:Tasks.task_summary.completed_total) "readiness completed total differs from /tasks"
    Assert-True ([bool]$script:Readiness.task_summary.contract.completed_equals_machine_sum) "readiness per-machine reconciliation failed"
    "completed=$($script:Readiness.task_summary.completed_total); machines=$($script:Readiness.machines.Count)"
}

Test-Warning "Laptop worker activity" {
    Assert-True ($null -ne $script:Readiness) "readiness prerequisite failed"
    $summary = $script:Readiness.summary
    Assert-True ([int]$summary.registered_laptops -gt 0) "no laptops are registered"
    Assert-True ([int]$summary.active_laptops -eq [int]$summary.registered_laptops) "only $($summary.active_laptops)/$($summary.registered_laptops) registered laptop workers are active"
    "$($summary.active_laptops)/$($summary.registered_laptops) registered laptop workers active"
}

Test-Step "NOC accounting and connectivity parity" {
    Assert-True ($null -ne $script:Tasks) "task accounting prerequisite failed"
    $noc = Invoke-JsonGet "/ops2/noc"
    Assert-True ([long]$noc.ai_workforce.completed_jobs -eq [long]$script:Tasks.task_summary.completed_total) "NOC completed_jobs differs from /tasks"
    Assert-True ([long]$noc.ai_workforce.task_summary.completed_total -eq [long]$script:Tasks.task_summary.completed_total) "NOC task summary differs from /tasks"
    Assert-True ($noc.ai_workforce.task_accounting_audit.status -eq "passed") "NOC task accounting audit did not pass"
    Test-Invariants $noc.infrastructure.machine_summary.contract.invariants "NOC connectivity"
    "completed=$($noc.ai_workforce.completed_jobs); activeLaptops=$($noc.infrastructure.machine_summary.active_laptops); connected=$($noc.infrastructure.machine_summary.connected_laptops)"
}

Test-Step "Connection freshness invariants" {
    $script:Connections = Invoke-JsonGet "/connections"
    Test-Invariants $script:Connections.connection_summary.contract.invariants "connection freshness"
    Test-Invariants $script:Connections.connection_summary.availability.rubric "connection availability"
    Assert-True ($script:Connections.connection_summary.availability.status -eq "passed") "connection availability is '$($script:Connections.connection_summary.availability.status)'"
    "records=$($script:Connections.connection_summary.records); online=$($script:Connections.connection_summary.online_records); targets=$($script:Connections.connection_summary.online_targets); stale=$($script:Connections.connection_summary.stale_records)"
}

Test-Warning "Laptop network reachability" {
    Assert-True ($null -ne $script:Readiness) "readiness prerequisite failed"
    Assert-True ($null -ne $script:Connections) "connections prerequisite failed"
    $laptopIds = @($script:Readiness.machines | Where-Object { $_.role -ne "brain" } | ForEach-Object { $_.id })
    $reachableIds = @($script:Connections.connections | Where-Object { $_.is_online -and -not $_.is_stale -and $laptopIds -contains $_.target_machine_id } | ForEach-Object { $_.target_machine_id } | Sort-Object -Unique)
    Assert-True ($reachableIds.Count -eq $laptopIds.Count) "only $($reachableIds.Count)/$($laptopIds.Count) laptop network targets are currently reachable"
    "$($reachableIds.Count)/$($laptopIds.Count) laptop network targets reachable"
}

Test-Warning "Direct laptop SSH control" {
    Assert-True ($null -ne $script:Readiness) "readiness prerequisite failed"
    $laptops = @($script:Readiness.machines | Where-Object { $_.role -ne "brain" })
    $ready = @($laptops | Where-Object {
        @($_.connections | Where-Object { $_.channel -eq "ssh-22-brain-to-laptop" -and $_.is_online -and -not $_.is_stale }).Count -gt 0
    })
    Assert-True ($ready.Count -eq $laptops.Count) "only $($ready.Count)/$($laptops.Count) direct SSH paths are ready; laptop administrator setup is required"
    "$($ready.Count)/$($laptops.Count) direct SSH paths ready"
}

Test-Step "Main dashboard page" { Test-Page "/dashboard/" "" }
Test-Step "Dev mini dashboard identity" { Test-Page "/laptop-packages/dev-laptop/" "dev-laptop" }
Test-Step "Research mini dashboard identity" { Test-Page "/laptop-packages/research-laptop/" "research-laptop" }
Test-Step "Business mini dashboard identity" { Test-Page "/laptop-packages/business-laptop/" "business-laptop" }

Write-Host "Audit result: PASS=$script:Passed FAIL=$script:Failed WARN=$script:Warnings"
if ($script:Failed -gt 0) { exit 1 }
exit 0
