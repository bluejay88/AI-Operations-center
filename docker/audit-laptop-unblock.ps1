param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev-laptop", "research-laptop", "business-laptop")]
    [string]$MachineId,

    [string]$BrainHost = "100.70.49.32",
    [string]$BrainUser = "jayla",
    [string]$AgentId = "orchestrator",
    [string]$IdentityFile = "",
    [string]$KnownHostsFile = (Join-Path $env:USERPROFILE ".ssh\ai_ops_known_hosts")
)

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\lib.ps1"
$apiHeaders = Get-AiOpsApiHeaders -MachineId $MachineId
$diagnosticMarkers = New-Object System.Collections.ArrayList

function Write-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail
    )
    $status = if ($Ok) { "PASS" } else { "FAIL" }
    $color = if ($Ok) { "Green" } else { "Red" }
    Write-Host "[$status] $Name - $Detail" -ForegroundColor $color
}

Write-Host "AI Operations Center laptop unblock audit"
Write-Host "MachineId=$MachineId BrainHost=$BrainHost BrainUser=$BrainUser AgentId=$AgentId"
Write-Host ""

function Resolve-IdentityFile {
    param([string]$RequestedPath)

    if ($RequestedPath -and (Test-Path $RequestedPath)) {
        return (Resolve-Path $RequestedPath).Path
    }

    $candidates = @(
        (Join-Path $env:USERPROFILE ".ssh\ai_ops_brain_ed25519"),
        (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "AI-Ops-SSH\ai_ops_brain_ed25519"),
        (Join-Path $env:LOCALAPPDATA "AI-Ops-SSH\ai_ops_brain_ed25519"),
        (Join-Path $env:TEMP "AI-Ops-SSH\ai_ops_brain_ed25519")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    return ""
}

$resolvedIdentityFile = Resolve-IdentityFile -RequestedPath $IdentityFile
if ($resolvedIdentityFile) {
    Write-Check "SSH identity file" $true $resolvedIdentityFile
} else {
    Write-Check "SSH identity file" $false "No ai_ops_brain_ed25519 key found in .ssh, Documents, LocalAppData, or Temp fallback folders."
}

$gitOk = $false
try {
    $remote = git remote get-url origin 2>&1
    $gitOk = $LASTEXITCODE -eq 0
    Write-Check "Git repository" $gitOk ($remote -join "`n")
} catch {
    Write-Check "Git repository" $false $_.Exception.Message
}

$tailscaleOk = $false
try {
    $tailIp = tailscale ip -4 2>&1
    $tailscaleOk = $LASTEXITCODE -eq 0 -and ($tailIp -join "").Trim().Length -gt 0
    if (-not $tailscaleOk) {
        $ipConfig = ipconfig
        $fallbackIp = $ipConfig | Select-String -Pattern "100\.\d+\.\d+\.\d+" | Select-Object -First 1
        $tailscaleOk = $null -ne $fallbackIp
        $detail = if ($tailscaleOk) { "ipconfig fallback found $($fallbackIp.Matches[0].Value)" } else { $tailIp -join "`n" }
        Write-Check "Tailscale local IP" $tailscaleOk $detail
    } else {
        Write-Check "Tailscale local IP" $tailscaleOk ($tailIp -join "`n")
    }
} catch {
    $ipConfig = ipconfig
    $fallbackIp = $ipConfig | Select-String -Pattern "100\.\d+\.\d+\.\d+" | Select-Object -First 1
    $tailscaleOk = $null -ne $fallbackIp
    $detail = if ($tailscaleOk) { "ipconfig fallback found $($fallbackIp.Matches[0].Value)" } else { $_.Exception.Message }
    Write-Check "Tailscale local IP" $tailscaleOk $detail
}

$apiOk = $false
try {
    $health = Invoke-RestMethod -Uri "http://$BrainHost`:8088/health" -TimeoutSec 10
    $apiOk = $health.status -eq "ok"
    Write-Check "Brain API" $apiOk ($health | ConvertTo-Json -Compress)
} catch {
    Write-Check "Brain API" $false $_.Exception.Message
}

$portOk = $false
try {
    $port = Test-NetConnection -ComputerName $BrainHost -Port 22 -WarningAction SilentlyContinue
    $portOk = [bool]$port.TcpTestSucceeded
    Write-Check "Brain SSH port" $portOk "TcpTestSucceeded=$($port.TcpTestSucceeded)"
} catch {
    Write-Check "Brain SSH port" $false $_.Exception.Message
}

$sshOk = $false
$sshAuthState = "unknown"
$sshFailureCode = "SSH_NOT_TESTED"
try {
    $sshArgs = @("-F", "NUL", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=$KnownHostsFile", "-o", "IdentitiesOnly=yes", "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=8")
    if ($resolvedIdentityFile) {
        $sshArgs += @("-i", $resolvedIdentityFile)
    }
    $sshArgs += @("$BrainUser@$BrainHost", "aiops-diagnostic hostname")
    $sshOutput = ssh @sshArgs 2>&1
    $sshOk = $LASTEXITCODE -eq 0
    $sshAuthState = if ($sshOk) { "noninteractive_ready" } elseif ($portOk) { "interactive_login_required" } else { "blocked" }
    $sshFailureCode = if ($sshOk) { "SSH_READY" } else { Get-AiOpsSshFailureCode -Output ($sshOutput -join "`n") -PortOpen $portOk -IdentityPresent ([bool]$resolvedIdentityFile) }
    Write-Check "SSH key/noninteractive login" $sshOk ($sshOutput -join "`n")
} catch {
    $sshAuthState = if ($portOk) { "interactive_login_required" } else { "blocked" }
    $sshFailureCode = Get-AiOpsSshFailureCode -Output $_.Exception.Message -PortOpen $portOk -IdentityPresent ([bool]$resolvedIdentityFile)
    Write-Check "SSH key/noninteractive login" $false $_.Exception.Message
}

$markerStatus = if ($sshOk) { "pass" } else { "fail" }
$markerAction = if ($sshOk) { "" } elseif ($sshFailureCode -eq "SSH_HOST_KEY_REJECTED") {
    "Verify the Brain host-key fingerprint out of band, then remove only the stale matching known_hosts entry."
} elseif ($sshFailureCode -eq "SSH_PUBLIC_KEY_REJECTED") {
    "Install the laptop public key on the Brain for the intended account; do not copy private keys."
} elseif ($sshFailureCode -eq "SSH_IDENTITY_MISSING") {
    "Create or securely transfer the approved laptop private key and restrict its file permissions."
} else {
    "Check Tailscale reachability, the Brain sshd service, and the Tailscale-scoped firewall rule."
}
$markerLineAndObject = Write-AiOpsDiagnosticMarker -Code $sshFailureCode -Phase "brain_ssh_noninteractive" -Status $markerStatus -MachineId $MachineId -Detail "port22=$portOk; auth_state=$sshAuthState" -SuggestedAction $markerAction
$markerLineAndObject | ForEach-Object {
    if ($_ -is [string]) { Write-Host $_ } else { [void]$diagnosticMarkers.Add($_) }
}

$sendOk = $false
try {
    $recommendations = New-Object System.Collections.ArrayList
    if ($apiOk -and $portOk -and -not $sshOk) {
        [void]$recommendations.Add(@{
            type = "ssh_authentication"
            priority = 90
            summary = "$MachineId SSH network is unblocked but noninteractive login is not configured."
            rationale = "Complete one interactive login or install SSH keys for automation-safe Brain operations."
            metadata = @{
                brain_user = $BrainUser
                ssh_auth_state = $sshAuthState
            }
        })
    }

    $payload = @{
        machine_id = $MachineId
        agent_id = $AgentId
        update_type = "laptop_unblock_audit"
        summary = "$MachineId completed laptop unblock audit."
        priority = 85
        outcome = if ($apiOk -and $portOk) { "connectivity_passed" } else { "connectivity_partial" }
        metrics = @{
            brain_api = $apiOk
            brain_ssh_port = $portOk
            ssh_noninteractive = $sshOk
            ssh_auth_state = $sshAuthState
            ssh_failure_code = $sshFailureCode
            brain_ssh_user = $BrainUser
            tailscale = $tailscaleOk
            git = $gitOk
        }
        diagnostic_markers = @($diagnosticMarkers)
        recommendations = @($recommendations)
    } | ConvertTo-Json -Depth 5
    $result = Invoke-RestMethod -Uri "http://$BrainHost`:8088/ops2/workstation-updates" -Method Post -Headers $apiHeaders -ContentType "application/json" -Body $payload -TimeoutSec 15
    $sendOk = $null -ne $result.update
    Write-Check "Publish audit to Brain" $sendOk "update_id=$($result.update.id)"
} catch {
    $detail = $_.Exception.Message
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
        $detail = "$detail`n$($_.ErrorDetails.Message)"
    }
    Write-Check "Publish audit to Brain" $false $detail
}

Write-Host ""
Write-Host "Summary:"
Write-Host "Git=$gitOk Tailscale=$tailscaleOk API=$apiOk Port22=$portOk SSHKeyLogin=$sshOk Publish=$sendOk"
Write-Host "SSHAuthState=$sshAuthState"
Write-Host "SSHFailureCode=$sshFailureCode"
Write-Host ""
if ($apiOk -and $portOk -and -not $sshOk) {
    Write-Host "SSH network is unblocked, but noninteractive SSH login is not configured yet. Try interactive login:"
    if ($resolvedIdentityFile) {
        Write-Host "ssh -i `"$resolvedIdentityFile`" $BrainUser@$BrainHost hostname"
    } else {
        Write-Host "ssh $BrainUser@$BrainHost hostname"
    }
}
if (-not $portOk) {
    Write-Host "Port 22 is blocked from this laptop. Re-run docker\setup-brain-openssh-admin.ps1 on the Brain PC as Administrator."
}
