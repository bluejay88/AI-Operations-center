function Assert-DockerAvailable {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (!$docker -and (Test-Path "C:\Program Files\Docker\Docker\resources\bin\docker.exe")) {
        $dockerBin = "C:\Program Files\Docker\Docker\resources\bin"
        $env:Path = "$dockerBin;$env:Path"
        $docker = Get-Command docker -ErrorAction SilentlyContinue
    }

    if (!$docker) {
        throw "Docker CLI was not found. Install Docker Desktop, start it, then reopen PowerShell and rerun this command."
    }

    $repoDockerConfig = Join-Path (Get-Location) ".docker"
    if (Test-Path $repoDockerConfig) {
        $env:DOCKER_CONFIG = $repoDockerConfig
    }

    try {
        docker info *> $null
    } catch {
        throw "Docker CLI was found, but Docker Desktop is not running or is not ready. Start Docker Desktop and try again."
    }
}

function Get-TailscaleExe {
    $tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($tailscale) {
        return $tailscale.Source
    }

    $programFilesPath = "C:\Program Files\Tailscale\tailscale.exe"
    if (Test-Path $programFilesPath) {
        return $programFilesPath
    }

    return $null
}

function Assert-TailscaleAvailable {
    $tailscaleExe = Get-TailscaleExe
    if (!$tailscaleExe) {
        throw "Tailscale CLI was not found. Install Tailscale and sign in before joining workers."
    }
    return $tailscaleExe
}

function Get-AiOpsSshFailureCode {
    param(
        [string]$Output = "",
        [bool]$PortOpen = $false,
        [bool]$IdentityPresent = $true
    )

    if (-not $IdentityPresent -or $Output -match "Identity file .* not accessible|no such identity") {
        return "SSH_IDENTITY_MISSING"
    }
    if ($Output -match "REMOTE HOST IDENTIFICATION HAS CHANGED|Host key verification failed") {
        return "SSH_HOST_KEY_REJECTED"
    }
    if ($Output -match "Permission denied|Too many authentication failures") {
        return "SSH_PUBLIC_KEY_REJECTED"
    }
    if ($Output -match "Connection refused") {
        return "SSH_SERVICE_NOT_LISTENING"
    }
    if ($Output -match "Could not resolve hostname|Name or service not known|No such host is known") {
        return "SSH_HOST_UNRESOLVED"
    }
    if ($Output -match "timed out|No route to host|Network is unreachable") {
        return "SSH_NETWORK_UNREACHABLE"
    }
    if (-not $PortOpen) {
        return "SSH_PORT_22_BLOCKED"
    }
    return "SSH_HANDSHAKE_FAILED"
}

function Write-AiOpsDiagnosticMarker {
    param(
        [Parameter(Mandatory=$true)][string]$Code,
        [Parameter(Mandatory=$true)][string]$Phase,
        [Parameter(Mandatory=$true)][string]$Status,
        [string]$MachineId = "",
        [string]$Detail = "",
        [string]$SuggestedAction = ""
    )

    $marker = [ordered]@{
        schema = "ai-ops.diagnostic-marker.v1"
        observed_at = (Get-Date).ToUniversalTime().ToString("o")
        code = $Code
        phase = $Phase
        status = $Status
        machine_id = $MachineId
        detail = $Detail
        suggested_action = $SuggestedAction
    }
    Write-Output ("AI_OPS_DIAGNOSTIC=" + ($marker | ConvertTo-Json -Compress))
    return $marker
}

function Start-AiOpsBackgroundProcess {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$true)][string[]]$ArgumentList,
        [string]$Name = "AI Operations background process",
        [switch]$PassThru
    )

    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WindowStyle Hidden -PassThru
    if ($PassThru) {
        return $process
    }
    Write-Host "$Name started in the background. PID: $($process.Id)"
}

function Start-AiOpsVisibleProcess {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$Reason = "human-visible AI Operations action"
    )

    Write-Host "Opening visible window for $Reason."
    if ($ArgumentList.Count -gt 0) {
        Start-Process -FilePath $FilePath -ArgumentList $ArgumentList | Out-Null
    } else {
        Start-Process -FilePath $FilePath | Out-Null
    }
}
