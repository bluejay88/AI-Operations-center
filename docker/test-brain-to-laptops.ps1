param(
    [string]$DevIp = "100.71.82.122",
    [string]$ResearchIp = "100.90.219.88",
    [string]$BusinessIp = "100.112.91.61",
    [string]$LaptopUser = $env:USERNAME,
    [string]$IdentityFile = (Join-Path $env:USERPROFILE ".ssh\ai_ops_brain_to_laptops"),
    [string]$BrainApi = "http://100.70.49.32:8088"
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\lib.ps1"

$targets = @(
    @{ MachineId = "dev-laptop"; Ip = $DevIp },
    @{ MachineId = "research-laptop"; Ip = $ResearchIp },
    @{ MachineId = "business-laptop"; Ip = $BusinessIp }
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
        Invoke-RestMethod -Method Post -Uri "$BrainApi/connections" -ContentType "application/json" -Body $body | Out-Null
    } catch {
        Write-Host "Could not publish connection result for ${MachineId}: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

foreach ($target in $targets) {
    Write-Host ""
    Write-Host "Testing $($target.MachineId) at $($target.Ip)"
    $port = Test-NetConnection -ComputerName $target.Ip -Port 22 -WarningAction SilentlyContinue
    Write-Host "Port22=$($port.TcpTestSucceeded)"
    $latency = $null
    if ($port.PingReplyDetails -and $port.PingReplyDetails.RoundtripTime -ne $null) {
        $latency = [double]$port.PingReplyDetails.RoundtripTime
    }

    $sshArgs = @("-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=8")
    if (-not [string]::IsNullOrWhiteSpace($IdentityFile)) {
        $sshArgs += @("-i", $IdentityFile)
    }
    $sshArgs += @("$LaptopUser@$($target.Ip)", "hostname")
    $output = ssh @sshArgs 2>&1
    $ok = $LASTEXITCODE -eq 0
    Write-Host "SSHKeyLogin=$ok"
    Write-Host ($output -join "`n")

    if ($ok) {
        $markerLineAndObject = Write-AiOpsDiagnosticMarker -Code "SSH_READY" -Phase "brain_to_laptop_ssh" -Status "pass" -MachineId $target.MachineId -Detail "port22=$($port.TcpTestSucceeded)"
        $markerLineAndObject | Where-Object { $_ -is [string] } | ForEach-Object { Write-Host $_ }
        Publish-Connection -MachineId $target.MachineId -Status $(if ($ok) { "online" } else { "auth_failed" }) -LatencyMs $latency -Metadata @{
            ip = $target.Ip
            user = $LaptopUser
            identity_file = $IdentityFile
            port22 = $true
            ssh_key_login = $ok
            command = "hostname"
            output = ($output -join "`n")
        }
    } else {
        $outputText = ($output -join "`n")
        $localKeyInaccessible = $outputText -match "Identity file .* not accessible"
        $reason = Get-AiOpsSshFailureCode -Output $outputText -PortOpen ([bool]$port.TcpTestSucceeded) -IdentityPresent (-not $localKeyInaccessible -and (Test-Path $IdentityFile))
        Write-Host "Reason=$reason"
        $markerAction = switch ($reason) {
            "SSH_IDENTITY_MISSING" { "Restore the approved Brain private key locally and restrict its file permissions; never copy it to telemetry or Git." }
            "SSH_HOST_KEY_REJECTED" { "Verify the laptop host-key fingerprint out of band, then replace only the stale known_hosts entry." }
            "SSH_PUBLIC_KEY_REJECTED" { "Install the approved Brain public key for the intended laptop account and verify authorized_keys ACLs." }
            default { "Run the laptop inbound SSH readiness diagnostic and verify Tailscale reachability and its scoped firewall rule." }
        }
        $markerLineAndObject = Write-AiOpsDiagnosticMarker -Code $reason -Phase "brain_to_laptop_ssh" -Status "fail" -MachineId $target.MachineId -Detail "port22=$($port.TcpTestSucceeded)" -SuggestedAction $markerAction
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
            identity_file = $IdentityFile
            port22 = [bool]$port.TcpTestSucceeded
            ssh_key_login = $false
            result = $reason
            diagnostic_marker = $markerObject
            fix = "Run docker\setup-worker-openssh-tailscale-admin.ps1 on this laptop as Administrator and add the Brain public key."
        }
    }
}
