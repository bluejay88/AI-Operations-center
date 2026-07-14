param(
    [string]$Branch = "master",
    [string]$Remote = "origin",
    [switch]$SkipBuild,
    [switch]$SkipAudit,
    [switch]$PushApproved,
    [string]$BrainApprovalId = "",
    # Retained for compatibility. Pushes are disabled by default.
    [switch]$NoPush,
    [int]$HealthTimeoutSeconds = 120,
    [int]$ConnectivityIntervalSeconds = 30
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path $PSScriptRoot -Parent
$outputRoot = Join-Path $repoRoot "output"
if (!(Test-Path $outputRoot)) {
    New-Item -ItemType Directory -Path $outputRoot | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $outputRoot "brain-update-$timestamp.log"

function Log-Step {
    param([string]$Message)
    $line = "[$(Get-Date -Format o)] $Message"
    $line | Tee-Object -FilePath $logPath -Append
}

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Script
    )
    Log-Step "START $Name"
    & $Script 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE. See $logPath"
    }
    Log-Step "DONE $Name"
}

function Wait-ServiceHealthy {
    param(
        [string]$Service,
        [int]$TimeoutSeconds = 120
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $status = docker compose ps $Service --format json 2>$null | ConvertFrom-Json
        if ($status -and ($status.Health -eq "healthy" -or ($status.State -eq "running" -and [string]::IsNullOrWhiteSpace($status.Health)))) {
            Log-Step "$Service is healthy/running."
            return
        }
        Start-Sleep -Seconds 3
    }
    docker compose ps | Tee-Object -FilePath $logPath -Append
    throw "$Service did not become healthy within $TimeoutSeconds seconds."
}

Push-Location $repoRoot
try {
    $before = git rev-parse HEAD
    Log-Step "Current commit: $before"

    if ($PushApproved -and $NoPush) {
        throw "Use either -PushApproved or -NoPush, not both."
    }
    if ($PushApproved -and [string]::IsNullOrWhiteSpace($BrainApprovalId)) {
        throw "-PushApproved requires -BrainApprovalId so the publish is tied to a Brain/human review record."
    }
    if ($PushApproved) {
        $pendingPush = git log --oneline "$Remote/$Branch..HEAD" 2>$null
        if (!$pendingPush) {
            Log-Step "No local commits are pending publication. Approval=$BrainApprovalId"
        } else {
            Log-Step "Publishing reviewed commits. Approval=$BrainApprovalId"
            $pendingPush | Tee-Object -FilePath $logPath -Append
        }
        Run-Step "push local commits" { git push $Remote $Branch }
    } else {
        Log-Step "Local publication disabled. Use -PushApproved -BrainApprovalId <review-id> after Brain/human review."
    }

    Run-Step "fetch updates" { git fetch $Remote $Branch }
    $remoteHead = git rev-parse "$Remote/$Branch"
    Log-Step "Remote commit: $remoteHead"

    $dirty = git status --porcelain
    if ($dirty) {
        Log-Step "Working tree has local changes; update will continue only if pull can fast-forward without overwriting."
    }

    Run-Step "pull latest" { git pull --ff-only $Remote $Branch }
    $afterPull = git rev-parse HEAD
    Log-Step "Post-pull commit: $afterPull"

    Run-Step "syntax check migrations" { python -m py_compile ai_ops_center\migrations.py ai_ops_center\api.py ai_ops_center\cli.py ai_ops_center\worker.py }

    if (!$SkipBuild) {
        Run-Step "build new brain images without stopping current services" { docker compose --profile worker build ai-ops-api worker }
    } else {
        Log-Step "Skipping image build by request."
    }

    Run-Step "ensure database is online" { docker compose up -d postgres }
    Wait-ServiceHealthy -Service "postgres" -TimeoutSeconds $HealthTimeoutSeconds

    Run-Step "apply database migrations with one-shot updated image" { docker compose --profile worker run --rm --no-deps ai-ops-api python -m ai_ops_center.cli migrate }

    Run-Step "restart api after migrations" { docker compose up -d --no-deps ai-ops-api }
    Wait-ServiceHealthy -Service "ai-ops-api" -TimeoutSeconds $HealthTimeoutSeconds

    Run-Step "restart worker after api is healthy" { docker compose --profile worker up -d --no-deps worker }
    Wait-ServiceHealthy -Service "worker" -TimeoutSeconds $HealthTimeoutSeconds

    Run-Step "seed registry" { docker compose exec -T ai-ops-api python -m ai_ops_center.cli seed }

    if (!$SkipAudit) {
        Run-Step "release audit" { docker compose exec -T ai-ops-api python -m ai_ops_center.audit50 }
    }

    Run-Step "start connectivity monitor" { powershell -ExecutionPolicy Bypass -File .\docker\start-connectivity-monitor.ps1 -IntervalSeconds $ConnectivityIntervalSeconds }

    $final = git rev-parse HEAD
    Log-Step "SUCCESS Brain updated from $before to $final"
    Write-Host "AI Operations Center update complete. Log: $logPath"
} catch {
    Log-Step "FAILED $($_.Exception.Message)"
    Write-Error $_
    exit 1
} finally {
    Pop-Location
}
