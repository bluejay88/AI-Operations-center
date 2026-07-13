param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev-laptop", "research-laptop", "business-laptop")]
    [string]$MachineId,

    [string]$BrainHost = "100.70.49.32",
    [string]$BrainUser = "jayla",
    [string]$AgentId = "",
    [string]$Branch = "master",
    [switch]$CommitReport,
    [switch]$SkipDocker,
    [switch]$StartWorker
)

$ErrorActionPreference = "Continue"

function Add-Check {
    param(
        [System.Collections.ArrayList]$Checks,
        [string]$Name,
        [bool]$Ok,
        [string]$Detail = "",
        [string]$Fix = ""
    )
    $status = if ($Ok) { "PASS" } else { "FAIL" }
    [void]$Checks.Add([ordered]@{
        name = $Name
        ok = $Ok
        status = $status
        detail = $Detail
        fix = $Fix
    })
    $color = if ($Ok) { "Green" } else { "Red" }
    Write-Host "[$status] $Name - $Detail" -ForegroundColor $color
    if (-not $Ok -and $Fix) {
        Write-Host "       Fix: $Fix" -ForegroundColor Yellow
    }
}

function Normalize-Host {
    param([string]$Value)
    return ($Value.Trim() -replace "^https?://", "" -split "/")[0] -split ":" | Select-Object -First 1
}

function Invoke-Json {
    param(
        [string]$Method = "GET",
        [string]$Uri,
        [object]$Body = $null,
        [int]$TimeoutSec = 12
    )
    if ($Body -ne $null) {
        return Invoke-RestMethod -Method $Method -Uri $Uri -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8) -TimeoutSec $TimeoutSec
    }
    return Invoke-RestMethod -Method $Method -Uri $Uri -TimeoutSec $TimeoutSec
}

$BrainHost = Normalize-Host $BrainHost
if (-not $AgentId) {
    $AgentId = switch ($MachineId) {
        "dev-laptop" { "programmer" }
        "research-laptop" { "research-lead" }
        "business-laptop" { "business-manager" }
    }
}

$checks = New-Object System.Collections.ArrayList
$startedAt = Get-Date
$repoRoot = (Get-Location).Path
$reportDir = Join-Path $repoRoot "diagnostics\$MachineId"
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

Write-Host "AI Operations Center laptop diagnostics"
Write-Host "MachineId=$MachineId BrainHost=$BrainHost BrainUser=$BrainUser AgentId=$AgentId"
Write-Host "ReportDir=$reportDir"
Write-Host ""

$hostname = $env:COMPUTERNAME
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$os = (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue)
$cpu = (Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue | Select-Object -First 1)
$battery = (Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1)
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction SilentlyContinue

$gitOk = $false
$remote = ""
try {
    $remote = (git remote get-url origin 2>&1) -join "`n"
    $gitOk = $LASTEXITCODE -eq 0 -and $remote
    Add-Check $checks "Git remote" $gitOk $remote "Run: git remote add origin https://github.com/bluejay88/AI-Operations-center.git"
} catch {
    Add-Check $checks "Git remote" $false $_.Exception.Message "Install Git, clone the repo, then run diagnostics from the repo root."
}

$pullOk = $false
if ($gitOk) {
    try {
        git fetch origin $Branch | Out-Host
        git pull --ff-only origin $Branch | Out-Host
        $pullOk = $LASTEXITCODE -eq 0
        Add-Check $checks "Git pull latest" $pullOk "branch=$Branch" "Commit/stash local changes, then run git pull --ff-only origin $Branch."
    } catch {
        Add-Check $checks "Git pull latest" $false $_.Exception.Message "Resolve local Git state, then pull again."
    }
}

$tailscaleIp = ""
try {
    $tailscaleIp = ((tailscale ip -4 2>&1) -join "`n").Trim()
    $tailOk = $LASTEXITCODE -eq 0 -and $tailscaleIp.Length -gt 0
    Add-Check $checks "Tailscale local IP" $tailOk $tailscaleIp "Install/sign into Tailscale and confirm this laptop is on Jayla's tailnet."
} catch {
    $ipconfig = (ipconfig) -join "`n"
    $match = [regex]::Match($ipconfig, "100\.\d+\.\d+\.\d+")
    $tailOk = $match.Success
    $tailscaleIp = if ($tailOk) { $match.Value } else { "" }
    Add-Check $checks "Tailscale local IP" $tailOk "fallback=$tailscaleIp" "Install/sign into Tailscale and confirm a 100.x IP exists."
}

$apiOk = $false
try {
    $health = Invoke-Json -Uri "http://$BrainHost`:8088/health"
    $apiOk = $health.status -eq "ok"
    Add-Check $checks "Brain API health" $apiOk ($health | ConvertTo-Json -Compress) "Confirm Brain API is running: docker compose up -d ai-ops-api"
} catch {
    Add-Check $checks "Brain API health" $false $_.Exception.Message "Confirm BrainHost is $BrainHost and port 8088 is reachable over Tailscale."
}

$listenerOk = $false
try {
    $listenerPayload = @{
        source_type = "machine"
        source_id = $MachineId
        event_type = "diagnostic_report"
        subject = "$MachineId diagnostic started"
        body = "$MachineId is running Git/Tailscale/API/Speaker/Worker diagnostics."
        priority = 88
        metadata = @{ machine_id = $MachineId; hostname = $hostname; user = $currentUser; tailscale_ip = $tailscaleIp }
    }
    $listener = Invoke-Json -Method "POST" -Uri "http://$BrainHost`:8088/listener/events" -Body $listenerPayload
    $listenerOk = $null -ne $listener.event_id
    Add-Check $checks "Brain listener publish" $listenerOk "event_id=$($listener.event_id)" "Fix Brain API reachability or listener endpoint errors."
} catch {
    Add-Check $checks "Brain listener publish" $false $_.Exception.Message "Run docker\check-brain.ps1 -BrainHost $BrainHost and retry."
}

$speakerOk = $false
try {
    $speaker = Invoke-Json -Uri "http://$BrainHost`:8088/speaker/feed/$MachineId"
    $speakerOk = $null -ne $speaker.instructions
    Add-Check $checks "Brain speaker feed" $speakerOk "messages=$($speaker.messages.Count)" "Confirm the Brain API has /speaker/feed/$MachineId and laptop ID is correct."
} catch {
    Add-Check $checks "Brain speaker feed" $false $_.Exception.Message "Check Brain API and machine ID spelling."
}

$localSshServiceOk = $false
try {
    $svc = Get-Service sshd -ErrorAction SilentlyContinue
    $localSshServiceOk = $svc -and $svc.Status -eq "Running"
    Add-Check $checks "Local OpenSSH server" $localSshServiceOk "status=$($svc.Status)" "Run PowerShell as Administrator: docker\setup-worker-openssh-tailscale-admin.ps1 -UserName $env:USERNAME"
} catch {
    Add-Check $checks "Local OpenSSH server" $false $_.Exception.Message "Install OpenSSH Server and start sshd."
}

$firewallOk = $false
try {
    $rules = Get-NetFirewallRule -DisplayName "AI Ops Tailscale SSH*" -ErrorAction SilentlyContinue
    $firewallOk = $null -ne $rules
    Add-Check $checks "Tailscale-only SSH firewall rule" $firewallOk "rules=$($rules.Count)" "Run docker\setup-worker-openssh-tailscale-admin.ps1 as Administrator."
} catch {
    Add-Check $checks "Tailscale-only SSH firewall rule" $false $_.Exception.Message "Run diagnostics in Windows PowerShell with NetSecurity available."
}

$dockerOk = $false
$workerRunning = $false
if (-not $SkipDocker) {
    try {
        $dockerVersion = (docker version --format "{{.Server.Version}}" 2>&1) -join "`n"
        $dockerOk = $LASTEXITCODE -eq 0 -and $dockerVersion
        Add-Check $checks "Docker engine" $dockerOk $dockerVersion "Start Docker Desktop or use Git/PowerShell worker fallback until Docker is repaired."
    } catch {
        Add-Check $checks "Docker engine" $false $_.Exception.Message "Start Docker Desktop, then rerun diagnostics."
    }

    if ($StartWorker -and $dockerOk) {
        try {
            .\docker\configure-worker-env.ps1 -MachineId $MachineId -BrainHost $BrainHost
            docker compose --profile worker up -d --build worker | Out-Host
            $workerRunning = $LASTEXITCODE -eq 0
            Add-Check $checks "Worker start" $workerRunning "docker compose worker requested" "Review docker compose logs worker"
        } catch {
            Add-Check $checks "Worker start" $false $_.Exception.Message "Run docker compose --profile worker up -d --build worker manually and capture logs."
        }
    } else {
        try {
            $ps = (docker compose ps worker 2>&1) -join "`n"
            $workerRunning = $ps -match "running|Up"
            Add-Check $checks "Worker container status" $workerRunning $ps "Run with -StartWorker or docker compose --profile worker up -d --build worker."
        } catch {
            Add-Check $checks "Worker container status" $false $_.Exception.Message "Docker unavailable or compose project not initialized."
        }
    }
}

$nodeConsoleOk = $false
try {
    $packagePath = Join-Path $repoRoot "laptop_packages\$MachineId\index.html"
    $nodeConsoleOk = Test-Path $packagePath
    Add-Check $checks "Node Console package" $nodeConsoleOk $packagePath "Pull latest GitHub master."
} catch {
    Add-Check $checks "Node Console package" $false $_.Exception.Message "Pull latest GitHub master."
}

$telemetryOk = $false
try {
    $telemetry = @{
        machine_id = $MachineId
        device_name = $MachineId
        hostname = $hostname
        operating_system = $os.Caption
        cpu = $cpu.Name
        ram_mb = [math]::Round(($os.TotalVisibleMemorySize / 1024), 0)
        storage_free_mb = if ($disk) { [math]::Round(($disk.FreeSpace / 1MB), 0) } else { $null }
        battery_percent = if ($battery) { $battery.EstimatedChargeRemaining } else { $null }
        current_user = $currentUser
        network_status = if ($tailOk) { "online" } else { "attention" }
        tailscale_status = if ($tailOk) { "online" } else { "missing" }
        current_ai_model = "AI Ops Node Console"
        active_projects = @("AI Operations Center")
        current_tasks = @()
        health_score = if ($apiOk -and $listenerOk -and $speakerOk) { 90 } else { 55 }
        metadata = @{ diagnostic = $true; docker_ok = $dockerOk; worker_running = $workerRunning; local_ssh_service = $localSshServiceOk }
    }
    $telemetryResult = Invoke-Json -Method "POST" -Uri "http://$BrainHost`:8088/ops2/device-telemetry" -Body $telemetry
    $telemetryOk = $null -ne $telemetryResult.telemetry
    Add-Check $checks "Publish telemetry" $telemetryOk "telemetry recorded" "Fix Brain API connectivity and rerun."
} catch {
    Add-Check $checks "Publish telemetry" $false $_.Exception.Message "Fix Brain API connectivity and rerun."
}

$durationMs = [int]((Get-Date) - $startedAt).TotalMilliseconds
$passed = ($checks | Where-Object { $_.ok }).Count
$total = $checks.Count
$overall = if ($passed -eq $total) { "ready" } elseif ($apiOk -and $listenerOk -and $speakerOk) { "partial_worker_ready" } else { "blocked" }

$report = [ordered]@{
    machine_id = $MachineId
    hostname = $hostname
    current_user = $currentUser
    brain_host = $BrainHost
    brain_user = $BrainUser
    agent_id = $AgentId
    started_at = $startedAt.ToString("o")
    completed_at = (Get-Date).ToString("o")
    duration_ms = $durationMs
    overall = $overall
    passed = $passed
    total = $total
    tailscale_ip = $tailscaleIp
    system = @{
        os = $os.Caption
        cpu = $cpu.Name
        ram_mb = if ($os) { [math]::Round(($os.TotalVisibleMemorySize / 1024), 0) } else { $null }
        disk_free_mb = if ($disk) { [math]::Round(($disk.FreeSpace / 1MB), 0) } else { $null }
        battery_percent = if ($battery) { $battery.EstimatedChargeRemaining } else { $null }
    }
    checks = @($checks)
}

$jsonPath = Join-Path $reportDir "latest.json"
$txtPath = Join-Path $reportDir "latest.txt"
$report | ConvertTo-Json -Depth 10 | Set-Content -Path $jsonPath -Encoding UTF8

$lines = New-Object System.Collections.ArrayList
[void]$lines.Add("AI Operations Center Laptop Diagnostic Report")
[void]$lines.Add("Machine: $MachineId")
[void]$lines.Add("Host: $hostname")
[void]$lines.Add("Overall: $overall")
[void]$lines.Add("Passed: $passed / $total")
[void]$lines.Add("Brain: http://$BrainHost`:8088")
[void]$lines.Add("")
foreach ($check in $checks) {
    [void]$lines.Add("[$($check.status)] $($check.name) - $($check.detail)")
    if (-not $check.ok -and $check.fix) {
        [void]$lines.Add("  Fix: $($check.fix)")
    }
}
$lines | Set-Content -Path $txtPath -Encoding UTF8

Write-Host ""
Write-Host "Diagnostic report written:"
Write-Host $jsonPath
Write-Host $txtPath

try {
    $updatePayload = @{
        machine_id = $MachineId
        agent_id = $AgentId
        update_type = "diagnostic_report"
        summary = "$MachineId diagnostic report completed: $overall ($passed/$total)."
        priority = 92
        outcome = $overall
        logs = ($lines -join "`n")
        metrics = @{ passed = $passed; total = $total; duration_ms = $durationMs; docker_ok = $dockerOk; worker_running = $workerRunning; tailscale_ip = $tailscaleIp }
        errors = @($checks | Where-Object { -not $_.ok } | ForEach-Object { $_.name })
        recommendations = @($checks | Where-Object { -not $_.ok } | ForEach-Object { @{ type = "diagnostic_fix"; priority = 90; summary = $_.fix; detail = $_.detail } })
        resource_consumption = @{ duration_ms = $durationMs }
        created_by = "run-laptop-diagnostics.ps1"
    }
    $update = Invoke-Json -Method "POST" -Uri "http://$BrainHost`:8088/ops2/workstation-updates" -Body $updatePayload
    Write-Host "Published diagnostic to Brain: update_id=$($update.update.id)"
} catch {
    Write-Host "Could not publish diagnostic to Brain: $($_.Exception.Message)" -ForegroundColor Yellow
}

if ($CommitReport) {
    try {
        git add "diagnostics/$MachineId/latest.json" "diagnostics/$MachineId/latest.txt"
        git commit -m "Add $MachineId diagnostic report"
        git push origin $Branch
        Add-Check $checks "Commit diagnostic report" ($LASTEXITCODE -eq 0) "pushed branch=$Branch" "If push fails, run git pull --ff-only origin $Branch and retry."
    } catch {
        Write-Host "Could not commit/push diagnostic report: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Next command for this laptop:"
Write-Host "powershell -ExecutionPolicy Bypass -File .\docker\run-laptop-diagnostics.ps1 -MachineId $MachineId -BrainHost $BrainHost -BrainUser $BrainUser -StartWorker -CommitReport"
