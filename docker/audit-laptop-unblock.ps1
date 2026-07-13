param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev-laptop", "research-laptop", "business-laptop")]
    [string]$MachineId,

    [string]$BrainHost = "100.70.49.32",
    [string]$BrainUser = "jayla",
    [string]$AgentId = "orchestrator"
)

$ErrorActionPreference = "Continue"

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
try {
    $sshOutput = ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 "$BrainUser@$BrainHost" hostname 2>&1
    $sshOk = $LASTEXITCODE -eq 0
    $sshAuthState = if ($sshOk) { "noninteractive_ready" } elseif ($portOk) { "interactive_login_required" } else { "blocked" }
    Write-Check "SSH key/noninteractive login" $sshOk ($sshOutput -join "`n")
} catch {
    $sshAuthState = if ($portOk) { "interactive_login_required" } else { "blocked" }
    Write-Check "SSH key/noninteractive login" $false $_.Exception.Message
}

$sendOk = $false
try {
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
            brain_ssh_user = $BrainUser
            tailscale = $tailscaleOk
            git = $gitOk
        }
        recommendations = if ($apiOk -and $portOk -and -not $sshOk) {
            @(
                @{
                    type = "ssh_authentication"
                    priority = 90
                    summary = "$MachineId SSH network is unblocked but noninteractive login is not configured."
                    rationale = "Complete one interactive login or install SSH keys for automation-safe Brain operations."
                    metadata = @{
                        brain_user = $BrainUser
                        ssh_auth_state = $sshAuthState
                    }
                }
            )
        } else {
            @()
        }
    } | ConvertTo-Json -Depth 5
    $result = Invoke-RestMethod -Uri "http://$BrainHost`:8088/ops2/workstation-updates" -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 15
    $sendOk = $null -ne $result.update
    Write-Check "Publish audit to Brain" $sendOk "update_id=$($result.update.id)"
} catch {
    Write-Check "Publish audit to Brain" $false $_.Exception.Message
}

Write-Host ""
Write-Host "Summary:"
Write-Host "Git=$gitOk Tailscale=$tailscaleOk API=$apiOk Port22=$portOk SSHKeyLogin=$sshOk Publish=$sendOk"
Write-Host "SSHAuthState=$sshAuthState"
Write-Host ""
if ($apiOk -and $portOk -and -not $sshOk) {
    Write-Host "SSH network is unblocked, but noninteractive SSH login is not configured yet. Try interactive login:"
    Write-Host "ssh $BrainUser@$BrainHost hostname"
}
if (-not $portOk) {
    Write-Host "Port 22 is blocked from this laptop. Re-run docker\setup-brain-openssh-admin.ps1 on the Brain PC as Administrator."
}
