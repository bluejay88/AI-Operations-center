param(
    [string]$KeyName = "ai_ops_brain_ed25519",
    [string]$Comment = "$env:COMPUTERNAME-ai-ops"
)

$ErrorActionPreference = "Stop"

function Get-WritableSshDir {
    $candidates = @(
        (Join-Path $env:USERPROFILE ".ssh"),
        (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "AI-Ops-SSH"),
        (Join-Path $env:LOCALAPPDATA "AI-Ops-SSH"),
        (Join-Path $env:TEMP "AI-Ops-SSH")
    )

    foreach ($candidate in $candidates) {
        try {
            if (!(Test-Path $candidate)) {
                New-Item -ItemType Directory -Path $candidate -Force | Out-Null
            }
            $probe = Join-Path $candidate ".write-test"
            Set-Content -Path $probe -Value "ok" -Force
            Remove-Item -Path $probe -Force
            return $candidate
        } catch {
            Write-Host "Cannot write SSH key folder candidate: $candidate"
        }
    }

    throw "No writable SSH key folder was found."
}

$sshDir = Get-WritableSshDir
if ($sshDir -ne (Join-Path $env:USERPROFILE ".ssh")) {
    Write-Host "Default .ssh folder was not writable. Using fallback folder: $sshDir"
}

$keyPath = Join-Path $sshDir $KeyName
$pubPath = "$keyPath.pub"

if ((Test-Path $keyPath) -and !(Test-Path $pubPath)) {
    Remove-Item -Path $keyPath -Force
}

if (!(Test-Path $keyPath)) {
    Write-Host "When ssh-keygen asks for a passphrase, press Enter twice for no passphrase."
    $sshKeygenArgs = @("-t", "ed25519", "-f", $keyPath, "-C", $Comment)
    & ssh-keygen @sshKeygenArgs
    if ($LASTEXITCODE -ne 0) {
        throw "ssh-keygen failed with exit code $LASTEXITCODE"
    }
    Write-Host "Created SSH key: $keyPath"
} else {
    Write-Host "SSH key already exists: $keyPath"
}

Write-Host ""
Write-Host "PUBLIC KEY - copy everything below this line to the Brain PC:"
Get-Content -Path $pubPath
Write-Host ""
Write-Host "After the Brain installs this key, test with:"
Write-Host "ssh -i `"$keyPath`" aiopsbrain@100.70.49.32 hostname"
