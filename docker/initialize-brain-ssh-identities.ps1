param(
    [string]$SshDirectory = (Join-Path $env:USERPROFILE ".ssh")
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command ssh-keygen -ErrorAction SilentlyContinue)) {
    throw "ssh-keygen is required. Install the Windows OpenSSH Client capability."
}
if (-not (Test-Path $SshDirectory)) { New-Item -ItemType Directory -Path $SshDirectory | Out-Null }

$machines = @("dev-laptop", "research-laptop", "business-laptop")
foreach ($machineId in $machines) {
    $safeId = $machineId -replace "-", "_"
    $privateKey = Join-Path $SshDirectory "ai_ops_brain_to_$safeId"
    if (-not (Test-Path $privateKey)) {
        # Native Windows argument binding drops a bare empty string. Passing a
        # quoted empty value preserves the intended non-interactive -N value.
        & ssh-keygen -q -t ed25519 -a 100 -N '""' -C "brain-to-$machineId-ai-ops" -f $privateKey
        if ($LASTEXITCODE -ne 0) { throw "Could not generate the identity for $machineId." }
    }
    icacls $privateKey /inheritance:r /grant:r "${env:USERNAME}:R" "SYSTEM:F" | Out-Null
    icacls "$privateKey.pub" /inheritance:r /grant:r "${env:USERNAME}:R" "SYSTEM:F" | Out-Null
    $fingerprint = (& ssh-keygen -lf "$privateKey.pub" 2>&1) -join " "
    Write-Host "$machineId public key: $privateKey.pub"
    Write-Host "$machineId fingerprint: $fingerprint"
}

Write-Host "Unique Brain-to-node identities are ready. Distribute only each matching .pub file to its target node."
