param(
    [string]$BrainHost = "100.70.49.32"
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path (Split-Path $root -Parent) -Parent
. "$repoRoot\docker\lib.ps1"
$index = Join-Path $root "index.html"
$url = ([System.Uri]$index).AbsoluteUri + "?brain=$BrainHost"
Start-AiOpsVisibleProcess -FilePath $url -Reason "Business Laptop AI Ops Node Console"
Write-Host "Business Laptop AI Ops Node Console opened. BrainHost=$BrainHost"
