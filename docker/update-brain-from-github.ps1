param(
    [string]$Branch = "master",
    [string]$Remote = "origin",
    [switch]$SkipBuild,
    [switch]$SkipAudit,
    [switch]$NoPush,
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

Push-Location $repoRoot
try {
    $before = git rev-parse HEAD
    Log-Step "Current commit: $before"

    if (!$NoPush) {
        Run-Step "push local commits" { git push $Remote $Branch }
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

    Run-Step "syntax check migrations" { python -m py_compile ai_ops_center\migrations.py ai_ops_center\api.py ai_ops_center\cli.py }

    if (!$SkipBuild) {
        Run-Step "rebuild brain services" { docker compose --profile worker up -d --build ai-ops-api worker postgres }
    } else {
        Run-Step "restart brain services" { docker compose --profile worker up -d ai-ops-api worker postgres }
    }

    Run-Step "apply database migrations" { docker compose exec -T ai-ops-api python -m ai_ops_center.cli migrate }
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
