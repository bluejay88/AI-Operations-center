param(
    [string]$BrainHost = "100.70.49.32"
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$index = Join-Path $root "index.html"
$url = ([System.Uri]$index).AbsoluteUri + "?brain=$BrainHost"
Start-Process $url
Write-Host "Research Laptop AI Ops Node Console opened. BrainHost=$BrainHost"
