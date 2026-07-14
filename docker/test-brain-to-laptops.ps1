param(
    [string]$DevIp = "100.71.82.122",
    [string]$ResearchIp = "100.90.219.88",
    [string]$BusinessIp = "100.112.91.61",
    [string]$LaptopUser = "aiops-diagnostic",
    [string]$KnownHostsFile = (Join-Path $env:USERPROFILE ".ssh\ai_ops_known_hosts"),
    [string]$BrainApi = "http://100.70.49.32:8088"
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\lib.ps1"
$apiHeaders = Get-AiOpsApiHeaders -MachineId "brain-gaming-pc"

$targets = @(
    @{ MachineId = "dev-laptop"; Ip = $DevIp; IdentityFile = (Join-Path $env:USERPROFILE ".ssh\ai_ops_brain_to_dev_laptop") },
    @{ MachineId = "research-laptop"; Ip = $ResearchIp; IdentityFile = (Join-Path $env:USERPROFILE ".ssh\ai_ops_brain_to_research_laptop") },
    @{ MachineId = "business-laptop"; Ip = $BusinessIp; IdentityFile = (Join-Path $env:USERPROFILE ".ssh\ai_ops_brain_to_business_laptop") }
)

function Publish-Connection {
    param(
        [string]$MachineId,
        [string]$Status,
        [object]$LatencyMs,
        [hashtable]$Metadata
    )

    if ([string]::IsNullOrWhiteSpace($BrainApi)) {
        return
    }

    $body = @{
        source_machine_id = "brain-gaming-pc"
        target_machine_id = $MachineId
        channel = "ssh-22-brain-to-laptop"
        status = $Status
        latency_ms = $LatencyMs
        metadata = $Metadata
    } | ConvertTo-Json -Depth 6

    try {
        Invoke-RestMethod -Method Post -Uri "$BrainApi/connections" -Headers $apiHeaders -ContentType "application/json" -Body $body | Out-Null
    } catch {
        Write-Host "Could not publish connection result for ${MachineId}: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Test-TcpPort {
    param([string]$HostName, [int]$Port = 22, [int]$TimeoutMs = 2500)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $pending = $client.ConnectAsync($HostName, $Port)
        return $pending.Wait($TimeoutMs) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Get-PresentedHostKeyFingerprint {
    param([string]$HostName)

    # Discovery only. This does not add the key to known_hosts or grant trust.
    $scan = (& ssh-keyscan -T 5 -t ed25519 $HostName 2>$null) -join "`n"
    $keyLine = $scan -split "`r?`n" | Where-Object { $_ -match "^[^#].*\s+ssh-ed25519\s+" } | Select-Object -First 1
    if (-not $keyLine) { return $null }
    $fingerprint = ($keyLine | ssh-keygen -lf - -E sha256 2>$null) -join "`n"
    if ($fingerprint -match "(SHA256:[A-Za-z0-9+/=]+)") { return $Matches[1] }
    return $null
}

foreach ($target in $targets) {
    Write-Host ""
    Write-Host "Testing $($target.MachineId) at $($target.Ip)"
    $portOpen = Test-TcpPort -HostName $target.Ip
    Write-Host "Port22=$portOpen"
    $latency = $null

    $identityFile = [string]$target.IdentityFile
    $sshArgs = @(
        "-F", "NUL", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "UserKnownHostsFile=$KnownHostsFile", "-o", "IdentitiesOnly=yes",
        "-o", "ClearAllForwardings=yes", "-o", "ConnectionAttempts=1", "-o", "ConnectTimeout=8",
        "-i", $identityFile, "$LaptopUser@$($target.Ip)", "aiops-auth-probe"
    )
    $output = ssh @sshArgs 2>&1
    $outputText = ($output -join "`n")
    # A successful authentication reaches ForceCommand, which intentionally
    # rejects this unsigned probe with the diagnostic JSON schema.
    $ok = $outputText -match 'ai-ops\.ssh-diagnostic\.v1' -and $outputText -match 'signed diagnostic envelope is required'
    Write-Host "SSHRestrictedBrokerReached=$ok"
    Write-Host ($output -join "`n")

    if ($ok) {
        $markerLineAndObject = Write-AiOpsDiagnosticMarker -Code "SSH_READY" -Phase "brain_to_laptop_ssh" -Status "pass" -MachineId $target.MachineId -Detail "port22=$portOpen; host_key_trusted=true"
        $markerLineAndObject | Where-Object { $_ -is [string] } | ForEach-Object { Write-Host $_ }
        Publish-Connection -MachineId $target.MachineId -Status $(if ($ok) { "online" } else { "auth_failed" }) -LatencyMs $latency -Metadata @{
            ip = $target.Ip
            user = $LaptopUser
            port22 = $portOpen
            ssh_restricted_broker_reached = $ok
            host_key_trusted = $true
            command = "unsigned authentication probe (expected denial)"
            output = ($output -join "`n")
        }
    } else {
        $localKeyInaccessible = $outputText -match "Identity file .* not accessible"
        $reason = Get-AiOpsSshFailureCode -Output $outputText -PortOpen $portOpen -IdentityPresent (-not $localKeyInaccessible -and (Test-Path $identityFile))
        $presentedFingerprint = if ($reason -eq "SSH_HOST_KEY_UNVERIFIED") { Get-PresentedHostKeyFingerprint -HostName $target.Ip } else { $null }
        Write-Host "Reason=$reason"
        $markerAction = switch ($reason) {
            "SSH_IDENTITY_MISSING" { "Restore the approved Brain private key locally and restrict its file permissions; never copy it to telemetry or Git." }
            "SSH_HOST_KEY_UNVERIFIED" { "Compare the presented fingerprint with the laptop console out of band. Add it to known_hosts only after an exact match." }
            "SSH_HOST_KEY_REJECTED" { "Verify the laptop host-key fingerprint out of band, then replace only the stale known_hosts entry." }
            "SSH_PUBLIC_KEY_REJECTED" { "Install the approved Brain public key for the intended laptop account and verify authorized_keys ACLs." }
            default { "Run the laptop inbound SSH readiness diagnostic and verify Tailscale reachability and its scoped firewall rule." }
        }
        $markerLineAndObject = Write-AiOpsDiagnosticMarker -Code $reason -Phase "brain_to_laptop_ssh" -Status "fail" -MachineId $target.MachineId -Detail "port22=$portOpen; presented_fingerprint=$presentedFingerprint" -SuggestedAction $markerAction
        $markerObject = $null
        $markerLineAndObject | ForEach-Object {
            if ($_ -is [string]) { Write-Host $_ } else { $markerObject = $_ }
        }
        if ($localKeyInaccessible) {
            Write-Host "Skipping Brain connection publish because the local identity file could not be read by this shell." -ForegroundColor Yellow
            continue
        }
        Publish-Connection -MachineId $target.MachineId -Status "blocked" -LatencyMs $latency -Metadata @{
            ip = $target.Ip
            user = $LaptopUser
            port22 = $portOpen
            ssh_key_login = $false
            host_key_trusted = $false
            presented_host_key_fingerprint = $presentedFingerprint
            result = $reason
            diagnostic_marker = $markerObject
            fix = "Run docker\setup-worker-openssh-tailscale-admin.ps1 on this laptop as Administrator and add the Brain public key."
        }
    }
}
