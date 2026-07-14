param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId,

    [string]$Branch = "master",
    [string]$BrainHost = "100.70.49.32",
    [Parameter(Mandatory=$true)]
    [ValidatePattern("^[0-9a-fA-F]{7,40}$")]
    [string]$ApprovedCommit,
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$BrainApprovalId,
    [switch]$SkipBenchmark
)

$ErrorActionPreference = "Stop"

if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or not on PATH."
}

if (!(Test-Path ".git")) {
    throw "Run this from the AI Operations Center repository folder."
}

$origin = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($origin)) {
    throw "No git origin is configured on this laptop. Clone from GitHub or run git remote add origin <url>."
}

$dirty = git status --porcelain
if ($dirty) {
    throw "Working tree has local changes. Preserve or commit them before applying an approved update. No reset was performed."
}

git fetch origin $Branch
if ($LASTEXITCODE -ne 0) { throw "Could not fetch origin/$Branch." }

$resolvedApproved = git rev-parse "$ApprovedCommit^{commit}" 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($resolvedApproved)) {
    throw "Approved commit '$ApprovedCommit' is not available from the fetched repository."
}
$resolvedRemote = git rev-parse "origin/$Branch^{commit}" 2>$null
if ($resolvedApproved -ne $resolvedRemote) {
    throw "Approved commit $resolvedApproved does not match origin/$Branch ($resolvedRemote). Brain must approve the exact deployed branch head."
}

git checkout $Branch
if ($LASTEXITCODE -ne 0) { throw "Could not check out $Branch." }
git merge --ff-only $resolvedApproved
if ($LASTEXITCODE -ne 0) { throw "Update is not a fast-forward. No reset or force operation was attempted." }

Write-Host "Applying Brain-approved commit $resolvedApproved (approval $BrainApprovalId)."

.\docker\configure-worker-env.ps1 -MachineId $MachineId -BrainHost $BrainHost
.\docker\check-brain.ps1 -BrainHost $BrainHost

$consoleInstaller = ".\laptop_packages\$MachineId\install.ps1"
if (Test-Path $consoleInstaller) {
    powershell -ExecutionPolicy Bypass -File $consoleInstaller -BrainHost $BrainHost
}

docker compose up -d worker

if (!$SkipBenchmark) {
    .\docker\run-benchmark.ps1 -MachineId $MachineId -BrainHost $BrainHost
}

Write-Host "Worker updated and running for $MachineId."
Write-Host "Brain status: http://$BrainHost`:8088/status"
