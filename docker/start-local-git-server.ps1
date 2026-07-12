param(
    [string]$ListenAddress = "100.70.49.32",
    [int]$Port = 9418
)

$ErrorActionPreference = "Stop"

$gitCommand = Get-Command git -ErrorAction SilentlyContinue
if (!$gitCommand) {
    throw "Git is not installed or not on PATH."
}

$repoRoot = (Resolve-Path ".").Path
$serverRoot = Join-Path $repoRoot "git-server"

if (!(Test-Path (Join-Path $serverRoot "ai-operations-center.git"))) {
    throw "Local Git repo was not published yet. Run docker\publish-local-git-server.ps1 first."
}

$gitExecPath = (git --exec-path)
$gitDaemonPath = Join-Path $gitExecPath "git-daemon.exe"
if (!(Test-Path $gitDaemonPath)) {
    throw "Cannot find git-daemon.exe at $gitDaemonPath."
}

$args = @(
    "--verbose",
    "--reuseaddr",
    "--export-all",
    "--base-path=$serverRoot",
    "--listen=$ListenAddress",
    "--port=$Port",
    $serverRoot
)

Start-Process -FilePath $gitDaemonPath -ArgumentList $args -WindowStyle Hidden
Write-Host "Started read-only Git server on git://$ListenAddress`:$Port/"
Write-Host "Laptop clone URL:"
Write-Host "  git clone git://$ListenAddress/ai-operations-center.git"
