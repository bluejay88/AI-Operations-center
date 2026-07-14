param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("brain-gaming-pc", "dev-laptop", "research-laptop", "business-laptop")]
    [string]$MachineId,
    [Parameter(Mandatory = $true)]
    [string]$HostName,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^SHA256:[A-Za-z0-9+/]{20,}$')]
    [string]$ExpectedFingerprint,
    [string]$KnownHostsFile = (Join-Path $env:USERPROFILE ".ssh\ai_ops_known_hosts")
)

$ErrorActionPreference = "Stop"
$parent = Split-Path -Parent $KnownHostsFile
if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
$temp = Join-Path $env:TEMP "ai-ops-hostkey-$([guid]::NewGuid().ToString('N')).txt"
try {
    $keyLine = (& ssh-keyscan -T 8 -t ed25519 $HostName 2>$null | Where-Object { $_ -and -not $_.StartsWith("#") } | Select-Object -First 1)
    if (-not $keyLine) { throw "No Ed25519 SSH host key was returned by $HostName." }
    Set-Content -LiteralPath $temp -Value $keyLine -Encoding ascii
    $fingerprintOutput = (& ssh-keygen -lf $temp -E sha256 2>&1) -join " "
    if ($fingerprintOutput -notmatch [regex]::Escape($ExpectedFingerprint)) {
        throw "Host-key fingerprint mismatch for $MachineId. Expected $ExpectedFingerprint; enrollment was refused."
    }
    if (-not (Test-Path $KnownHostsFile)) { New-Item -ItemType File -Path $KnownHostsFile | Out-Null }
    & ssh-keygen -R $HostName -f $KnownHostsFile | Out-Null
    Add-Content -LiteralPath $KnownHostsFile -Value $keyLine -Encoding ascii
    icacls $KnownHostsFile /inheritance:r /grant:r "${env:USERNAME}:R" "SYSTEM:F" | Out-Null
    Write-Host "Pinned verified Ed25519 host key for $MachineId ($HostName) in $KnownHostsFile."
} finally {
    Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
}
