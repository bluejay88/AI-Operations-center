param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev-laptop", "research-laptop", "business-laptop")]
    [string]$MachineId,

    [string]$BrainHost = "100.70.49.32",
    [string]$Branch = "master",
    [string]$RepoUrl = "https://github.com/bluejay88/AI-Operations-center.git",
    [string]$BrainPublicKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBoby+MkyYxc2aeEgz2npB31pDw5ICYhKhNmpDc3V9dm brain-pc-ai-ops",
    [string]$ExpectedBrainKeyFingerprint = "",
    [switch]$UpdateCode,
    [switch]$RepairSsh,
    [switch]$StartWorker,
    [switch]$InstallStartupTask,
    [switch]$QueueProbe,
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\lib.ps1"

function Normalize-Host {
    param([string]$Value)
    return ($Value.Trim() -replace "^https?://", "" -split "/")[0] -split ":" | Select-Object -First 1
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-Json {
    param(
        [string]$Method = "GET",
        [string]$Uri,
        [object]$Body = $null,
        [int]$TimeoutSec = 15
    )
    if ($Body -ne $null) {
        return Invoke-RestMethod -Method $Method -Uri $Uri -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 10) -TimeoutSec $TimeoutSec
    }
    return Invoke-RestMethod -Method $Method -Uri $Uri -TimeoutSec $TimeoutSec
}

function Resolve-AgentId {
    param([string]$Id)
    switch ($Id) {
        "dev-laptop" { "programmer" }
        "research-laptop" { "research-lead" }
        "business-laptop" { "business-manager" }
    }
}

$BrainHost = Normalize-Host $BrainHost
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    Write-Host "AI Operations Center Laptop Recovery Bundle"
    Write-Host "MachineId=$MachineId BrainHost=$BrainHost Branch=$Branch"

    if (-not (Test-Path ".git")) {
        throw "This script must run from the AI-Operations-center repo. Clone with: git clone $RepoUrl"
    }

    if ($UpdateCode) {
        Write-Host "Pulling latest GitHub bundle..."
        git fetch origin $Branch | Out-Host
        git pull --ff-only origin $Branch | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "Git update failed. Commit/stash local changes, then rerun."
        }
    }

    $health = Invoke-Json -Uri "http://$BrainHost`:8088/health"
    if ($health.status -ne "ok") {
        throw "Brain API did not return ok."
    }
    Write-Host "Brain API is reachable."

    $contractDir = Join-Path $repoRoot "runtime\node-contracts"
    New-Item -ItemType Directory -Force -Path $contractDir | Out-Null
    Write-Host "Downloading machine-specific AI node contract and prompt..."
    $contract = Invoke-Json -Uri "http://$BrainHost`:8088/laptop-agents/$MachineId/contract?brain_host=$BrainHost"
    $contract | ConvertTo-Json -Depth 20 | Set-Content -Path (Join-Path $contractDir "$MachineId.contract.json") -Encoding UTF8
    $prompt = Invoke-Json -Uri "http://$BrainHost`:8088/laptop-agents/$MachineId/prompt?brain_host=$BrainHost"
    $prompt.prompt | Set-Content -Path (Join-Path $contractDir "$MachineId.prompt.txt") -Encoding UTF8
    Invoke-Json -Method "POST" -Uri "http://$BrainHost`:8088/team-chat/post" -Body @{
        channel = "operations"
        thread_key = "laptop-recovery"
        actor_type = "machine"
        actor_id = $MachineId
        machine_id = $MachineId
        message_type = "update"
        priority = 88
        subject = "$MachineId downloaded AI node contract"
        body = "$MachineId downloaded its contract and prompt, including team room, speaker/listener, peer request, and LLM mesh instructions."
        metadata = @{ machine_id = $MachineId; contract_path = "runtime\node-contracts\$MachineId.contract.json"; prompt_path = "runtime\node-contracts\$MachineId.prompt.txt" }
    } | Out-Null

    if ($RepairSsh) {
        if (-not (Test-Admin)) {
            throw "SSH repair needs Administrator PowerShell. Rerun as Administrator or omit -RepairSsh."
        }
        Write-Host "Repairing OpenSSH as Tailscale-only with Brain public key..."
        powershell -ExecutionPolicy Bypass -File ".\docker\setup-worker-openssh-tailscale-admin.ps1" `
            -UserName $env:USERNAME `
            -BrainPublicKey $BrainPublicKey
    }

    Write-Host "Running diagnostics..."
    $diagArgs = @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\docker\run-laptop-diagnostics.ps1",
        "-MachineId", $MachineId,
        "-BrainHost", $BrainHost,
        "-Branch", $Branch,
        "-ExpectedBrainKeyFingerprint", $ExpectedBrainKeyFingerprint
    )
    if ($UpdateCode) { $diagArgs += "-UpdateCode" }
    if ($StartWorker) { $diagArgs += "-StartWorker" }
    if ($SkipDocker) { $diagArgs += "-SkipDocker" }
    powershell @diagArgs

    if ($StartWorker) {
        Write-Host "Starting listener/speaker/worker loop..."
        if ($SkipDocker) {
            .\docker\configure-worker-env.ps1 -MachineId $MachineId -BrainHost $BrainHost
            $workerArgs = @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                "python -m ai_ops_center.cli worker --machine $MachineId --sleep-seconds 10 --work-seconds 2"
            )
            Start-AiOpsBackgroundProcess -FilePath "powershell.exe" -ArgumentList $workerArgs -Name "$MachineId local worker loop"
        } else {
            powershell -ExecutionPolicy Bypass -File ".\docker\start-laptop-operations.ps1" -MachineId $MachineId -BrainHost $BrainHost -WorkSeconds 2
        }
    }

    if ($InstallStartupTask) {
        $taskName = "AI Operations Center - $MachineId Worker Recovery"
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$repoRoot\docker\laptop-recovery-bundle.ps1`" -MachineId $MachineId -BrainHost $BrainHost -StartWorker"
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Force | Out-Null
        Write-Host "Installed startup task: $taskName"
    }

    if ($QueueProbe) {
        $agentId = Resolve-AgentId $MachineId
        $category = switch ($MachineId) {
            "dev-laptop" { "development" }
            "research-laptop" { "research" }
            "business-laptop" { "business" }
        }
        $probe = @{
            title = "$MachineId recovery workload probe"
            agent_id = $agentId
            category = $category
            description = "$MachineId recovery bundle queued this connectivity probe. Worker must claim it and return real machine evidence."
            priority = 100
            metadata = @{ executor = "connectivity_probe"; recovery_bundle = $true; queued_by = $MachineId }
        }
        $created = Invoke-Json -Method "POST" -Uri "http://$BrainHost`:8088/tasks" -Body $probe
        Write-Host "Queued probe task: $($created.task_id)"
    }

    $pulse = @{
        source_type = "machine"
        source_id = $MachineId
        event_type = "recovery_bundle_complete"
        subject = "$MachineId recovery bundle completed"
        body = "$MachineId completed recovery bundle. SSH repair requested=$RepairSsh; worker start requested=$StartWorker; probe queued=$QueueProbe."
        priority = 95
        metadata = @{
            machine_id = $MachineId
            brain_host = $BrainHost
            update_code = [bool]$UpdateCode
            repair_ssh = [bool]$RepairSsh
            start_worker = [bool]$StartWorker
            install_startup_task = [bool]$InstallStartupTask
            skip_docker = [bool]$SkipDocker
        }
    }
    Invoke-Json -Method "POST" -Uri "http://$BrainHost`:8088/listener/events" -Body $pulse | Out-Null
    Write-Host "Recovery bundle complete."
} finally {
    Pop-Location
}
