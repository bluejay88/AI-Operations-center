param(
    [string]$EnvFile = (Join-Path (Split-Path -Parent $PSScriptRoot) ".env")
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\lib.ps1"
Assert-DockerAvailable
if (-not (Test-Path $EnvFile)) { throw ".env does not exist." }

$buffer = New-Object byte[] 36
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
$newPassword = [Convert]::ToBase64String($buffer).TrimEnd('=').Replace('+','-').Replace('/','_')

$escaped = $newPassword.Replace("'", "''")
$sql = "alter role aiops with password '$escaped';"
$containerId = (docker ps --filter "label=com.docker.compose.service=postgres" --format "{{.ID}}" | Select-Object -First 1)
if (-not $containerId) { throw "The running AI Operations PostgreSQL container was not found." }
$sql | docker exec -i $containerId psql -v ON_ERROR_STOP=1 -U aiops -d aiops | Out-Null
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL rejected the credential rotation; .env was not changed." }

$lines = [System.Collections.Generic.List[string]]::new()
Get-Content -LiteralPath $EnvFile | ForEach-Object { $lines.Add($_) }
function Set-EnvValue([string]$Name, [string]$Value) {
    $prefix = "$Name="
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].StartsWith($prefix, [StringComparison]::Ordinal)) { $lines[$i] = "$prefix$Value"; return }
    }
    $lines.Add("$prefix$Value")
}
Set-EnvValue "POSTGRES_PASSWORD" $newPassword
Set-EnvValue "DATABASE_URL" "postgresql://aiops:$newPassword@postgres:5432/aiops"
Set-EnvValue "LOCAL_DATABASE_URL" "postgresql://aiops:$newPassword@localhost:5432/aiops"
Set-Content -LiteralPath $EnvFile -Value $lines -Encoding utf8
$newPassword = $null
Write-Host "Rotated the aiops PostgreSQL role and updated local .env without displaying the credential."



