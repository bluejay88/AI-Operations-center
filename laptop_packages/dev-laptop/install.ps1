param(
    [string]$BrainHost = "100.70.49.32"
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path (Split-Path $root -Parent) -Parent
. "$repoRoot\docker\lib.ps1"
$index = Join-Path $root "index.html"
$python = (Get-Command python -ErrorAction Stop).Source
Start-AiOpsBackgroundProcess -FilePath $python -ArgumentList @("-m", "ai_ops_center.device_gateway", "--machine", "dev-laptop", "--brain-host", $BrainHost, "--port", "8092") -Name "Dev laptop authenticated dashboard gateway"
$url = "http://127.0.0.1:8092/dev-laptop/"
Start-AiOpsVisibleProcess -FilePath $url -Reason "Dev Laptop AI Ops Node Console"
Write-Host "Dev Laptop AI Ops Node Console opened. BrainHost=$BrainHost"
