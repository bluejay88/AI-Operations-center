$ErrorActionPreference = "Stop"

function Write-Result {
    param([string]$Operation, [string]$Status, [object]$Data)
    [ordered]@{
        schema = "ai-ops.ssh-diagnostic.v1"
        operation = $Operation
        status = $Status
        hostname = $env:COMPUTERNAME
        observed_at = [DateTimeOffset]::UtcNow.ToString("o")
        data = $Data
    } | ConvertTo-Json -Depth 6 -Compress
}

$original = [string]$env:SSH_ORIGINAL_COMMAND
$parts = @($original.Trim() -split '\s+' | Where-Object { $_ })
if ($parts.Count -lt 2 -or $parts[0] -ne "aiops-diagnostic") {
    Write-Result -Operation "rejected" -Status "denied" -Data @{ reason = "Only typed AI Ops diagnostic operations are accepted." }
    exit 64
}

$operation = $parts[1]
$argument = if ($parts.Count -eq 3) { $parts[2] } else { "" }
if ($parts.Count -gt 3 -or $argument -notmatch '^[A-Za-z0-9_.-]{0,64}$') {
    Write-Result -Operation $operation -Status "denied" -Data @{ reason = "Invalid diagnostic arguments." }
    exit 64
}

try {
    switch ($operation) {
        "hostname" {
            Write-Result $operation "ok" @{ hostname = $env:COMPUTERNAME; user = $env:USERNAME }
        }
        "service-status" {
            $allowed = @("sshd", "tailscale", "docker", "com.docker.service")
            if ($argument -notin $allowed) { throw "Service is not in the diagnostic allowlist." }
            $service = Get-Service -Name $argument -ErrorAction Stop
            Write-Result $operation "ok" @{ name = $service.Name; status = [string]$service.Status; start_type = [string]$service.StartType }
        }
        "disk-health" {
            $volumes = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
                @{ device = $_.DeviceID; size_bytes = [int64]$_.Size; free_bytes = [int64]$_.FreeSpace }
            })
            Write-Result $operation "ok" @{ volumes = $volumes }
        }
        "app-version" {
            Write-Result $operation "ok" @{ powershell = $PSVersionTable.PSVersion.ToString(); windows = [Environment]::OSVersion.VersionString }
        }
        "git-status" {
            $repo = Join-Path $env:USERPROFILE "Desktop\AI-Operations-center"
            if (-not (Test-Path (Join-Path $repo ".git"))) { throw "Managed repository was not found." }
            $branch = (& git -C $repo branch --show-current 2>&1) -join "`n"
            $revision = (& git -C $repo rev-parse HEAD 2>&1) -join "`n"
            $dirty = @(& git -C $repo status --porcelain 2>&1).Count
            Write-Result $operation "ok" @{ branch = $branch.Trim(); revision = $revision.Trim(); changed_entries = $dirty }
        }
        "docker-status" {
            $service = Get-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
            Write-Result $operation "ok" @{ installed = [bool]$service; service_status = if ($service) { [string]$service.Status } else { "missing" } }
        }
        "event-log-summary" {
            $cutoff = (Get-Date).AddHours(-2)
            $events = @(Get-WinEvent -FilterHashtable @{ LogName = "System"; Level = 1,2; StartTime = $cutoff } -MaxEvents 25 -ErrorAction SilentlyContinue | ForEach-Object {
                @{ id = $_.Id; provider = $_.ProviderName; level = $_.LevelDisplayName; created_at = $_.TimeCreated.ToUniversalTime().ToString("o") }
            })
            Write-Result $operation "ok" @{ window_hours = 2; events = $events }
        }
        "worker-health" {
            $processes = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
                $_.CommandLine -match 'ai_ops_center\.cli.+worker'
            } | ForEach-Object { @{ process_id = $_.ProcessId; name = $_.Name } })
            Write-Result $operation "ok" @{ worker_processes = $processes; count = $processes.Count }
        }
        default {
            Write-Result $operation "denied" @{ reason = "Unknown diagnostic operation." }
            exit 64
        }
    }
} catch {
    Write-Result $operation "failed" @{ error_type = $_.Exception.GetType().Name; message = $_.Exception.Message }
    exit 1
}
