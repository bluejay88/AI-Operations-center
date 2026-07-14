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

function Deny([string]$Reason, [string]$Operation = "rejected") {
    Write-Result -Operation $Operation -Status "denied" -Data @{ reason = $Reason }
    exit 64
}

$parts = @(([string]$env:SSH_ORIGINAL_COMMAND).Trim() -split '\s+' | Where-Object { $_ })
if ($parts.Count -ne 3 -or $parts[0] -ne "aiops-diagnostic-v1") { Deny "A signed diagnostic envelope is required." }
$encoded = $parts[1]
$suppliedSignature = $parts[2]
if ($encoded -notmatch '^[A-Za-z0-9_-]{40,4096}$' -or $suppliedSignature -notmatch '^[0-9a-f]{64}$') {
    Deny "The signed envelope encoding is invalid."
}

$root = Join-Path $env:ProgramData "AI-Ops"
$keyPath = Join-Path $root "ssh-broker-envelope-key"
$machinePath = Join-Path $root "machine-id"
if (-not (Test-Path -LiteralPath $keyPath) -or -not (Test-Path -LiteralPath $machinePath)) { Deny "Broker authority is not provisioned." }
$key = (Get-Content -LiteralPath $keyPath -Raw).Trim()
$machineId = (Get-Content -LiteralPath $machinePath -Raw).Trim()
if ($key.Length -lt 32) { Deny "Broker authority is invalid." }

$hmac = [Security.Cryptography.HMACSHA256]::new([Text.Encoding]::UTF8.GetBytes($key))
try { $actualBytes = $hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes($encoded)) } finally { $hmac.Dispose() }
try {
    $suppliedBytes = [byte[]]::new(32)
    for ($i = 0; $i -lt 32; $i++) { $suppliedBytes[$i] = [Convert]::ToByte($suppliedSignature.Substring($i * 2, 2), 16) }
} catch { Deny "The signature is malformed." }
$signatureDifference = 0
for ($i = 0; $i -lt 32; $i++) { $signatureDifference = $signatureDifference -bor ($actualBytes[$i] -bxor $suppliedBytes[$i]) }
if ($signatureDifference -ne 0) { Deny "The envelope signature is invalid." }

try {
    $padded = $encoded.Replace('-', '+').Replace('_', '/') + ('=' * ((4 - $encoded.Length % 4) % 4))
    $envelope = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($padded)) | ConvertFrom-Json
} catch { Deny "The envelope payload is malformed." }
$operation = [string]$envelope.command_id
$now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
if ($envelope.schema -ne "ai-ops.ssh-envelope.v1" -or $envelope.target_machine_id -ne $machineId) { Deny "The envelope target is invalid." $operation }
if ([long]$envelope.issued_at -gt ($now + 60) -or [long]$envelope.expires_at -le $now -or ([long]$envelope.expires_at - [long]$envelope.issued_at) -gt 300) {
    Deny "The envelope is expired or has an invalid lifetime." $operation
}
if ([string]$envelope.nonce -notmatch '^ssh-nonce-[0-9a-f-]{36}$') { Deny "The envelope nonce is invalid." $operation }

# Atomically consume the nonce on the target. The bounded ledger survives
# worker/SSH restarts and rejects concurrent replays.
$replayPath = Join-Path $root "ssh-broker-replay.jsonl"
$stream = [IO.File]::Open($replayPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
try {
    $reader = [IO.StreamReader]::new($stream, [Text.Encoding]::UTF8, $true, 1024, $true)
    try { $content = $reader.ReadToEnd() } finally { $reader.Dispose() }
    $active = @()
    foreach ($line in @($content -split "`r?`n" | Where-Object { $_ })) {
        try { $item = $line | ConvertFrom-Json } catch { continue }
        if ([long]$item.expires_at -gt $now) {
            if ($item.nonce -eq $envelope.nonce) { Deny "The envelope nonce was already consumed." $operation }
            $active += $item
        }
    }
    $active += [pscustomobject]@{ nonce = [string]$envelope.nonce; expires_at = [long]$envelope.expires_at }
    $stream.SetLength(0); $stream.Position = 0
    $writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false), 1024, $true)
    try { foreach ($item in $active) { $writer.WriteLine(($item | ConvertTo-Json -Compress)) }; $writer.Flush(); $stream.Flush($true) } finally { $writer.Dispose() }
} finally { $stream.Dispose() }

$arguments = @($envelope.arguments)
if ($arguments.Count -gt 1 -or ($arguments | Where-Object { [string]$_ -notmatch '^[A-Za-z0-9_.-]{1,64}$' })) {
    Deny "The typed arguments are invalid." $operation
}
$argument = if ($arguments.Count -eq 1) { [string]$arguments[0] } else { "" }

try {
    switch ($operation) {
        "hostname" { Write-Result $operation "ok" @{ hostname = $env:COMPUTERNAME; user = $env:USERNAME } }
        "service-status" {
            if ($argument -notin @("sshd", "tailscale", "docker", "com.docker.service")) { throw "Service is not in the diagnostic allowlist." }
            $service = Get-Service -Name $argument -ErrorAction Stop
            Write-Result $operation "ok" @{ name = $service.Name; status = [string]$service.Status; start_type = [string]$service.StartType }
        }
        "disk-health" {
            $volumes = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object { @{ device = $_.DeviceID; size_bytes = [int64]$_.Size; free_bytes = [int64]$_.FreeSpace } })
            Write-Result $operation "ok" @{ volumes = $volumes }
        }
        "app-version" { Write-Result $operation "ok" @{ powershell = $PSVersionTable.PSVersion.ToString(); windows = [Environment]::OSVersion.VersionString } }
        "git-status" {
            $repo = Join-Path $env:USERPROFILE "Desktop\AI-Operations-center"
            if (-not (Test-Path (Join-Path $repo ".git"))) { throw "Managed repository was not found." }
            $branch = (& git -C $repo branch --show-current 2>&1) -join "`n"; $revision = (& git -C $repo rev-parse HEAD 2>&1) -join "`n"; $dirty = @(& git -C $repo status --porcelain 2>&1).Count
            Write-Result $operation "ok" @{ branch = $branch.Trim(); revision = $revision.Trim(); changed_entries = $dirty }
        }
        "docker-status" { $service = Get-Service -Name "com.docker.service" -ErrorAction SilentlyContinue; Write-Result $operation "ok" @{ installed = [bool]$service; service_status = if ($service) { [string]$service.Status } else { "missing" } } }
        "event-log-summary" {
            $events = @(Get-WinEvent -FilterHashtable @{ LogName = "System"; Level = 1,2; StartTime = (Get-Date).AddHours(-2) } -MaxEvents 25 -ErrorAction SilentlyContinue | ForEach-Object { @{ id = $_.Id; provider = $_.ProviderName; level = $_.LevelDisplayName; created_at = $_.TimeCreated.ToUniversalTime().ToString("o") } })
            Write-Result $operation "ok" @{ window_hours = 2; events = $events }
        }
        "worker-health" {
            $processes = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'ai_ops_center\.cli.+worker' } | ForEach-Object { @{ process_id = $_.ProcessId; name = $_.Name } })
            Write-Result $operation "ok" @{ worker_processes = $processes; count = $processes.Count }
        }
        default { Deny "Unknown diagnostic operation." $operation }
    }
} catch {
    Write-Result $operation "failed" @{ error_type = $_.Exception.GetType().Name; message = $_.Exception.Message }
    exit 1
}
