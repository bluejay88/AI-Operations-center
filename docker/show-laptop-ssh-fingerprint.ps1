param(
    [string]$IdentityFile = ""
)

$ErrorActionPreference = "Stop"

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

    throw "No ai_ops_brain_ed25519 private key found."
}

$keyPath = Resolve-IdentityFile -RequestedPath $IdentityFile
$pubPath = "$keyPath.pub"

if (!(Test-Path $pubPath)) {
    Write-Host "Public key file missing. Rebuilding it from the private key."
    ssh-keygen -y -f $keyPath | Set-Content -Path $pubPath -Encoding ascii
}

Write-Host "Laptop private key path: $keyPath"
Write-Host "Laptop public key path: $pubPath"
Write-Host ""
Write-Host "Laptop public key fingerprint:"
ssh-keygen -lf $pubPath
Write-Host ""
Write-Host "Laptop public key line to paste into Brain:"
Get-Content -Path $pubPath
