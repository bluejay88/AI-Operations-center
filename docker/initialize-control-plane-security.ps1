param(
    [string]$EnvFile = (Join-Path (Split-Path -Parent $PSScriptRoot) ".env")
)

$ErrorActionPreference = "Stop"

function New-Secret([int]$Bytes = 48) {
    $buffer = New-Object byte[] $Bytes
    [Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return [Convert]::ToBase64String($buffer).TrimEnd('=').Replace('+','-').Replace('/','_')
}

function Set-EnvValue([System.Collections.Generic.List[string]]$Lines, [string]$Name, [string]$Value) {
    $prefix = "$Name="
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i].StartsWith($prefix, [StringComparison]::Ordinal)) {
            $Lines[$i] = "$prefix$Value"
            return
        }
    }
    $Lines.Add("$prefix$Value")
}

function Get-EnvValue([System.Collections.Generic.List[string]]$Lines, [string]$Name) {
    $prefix = "$Name="
    $line = $Lines | Where-Object { $_.StartsWith($prefix, [StringComparison]::Ordinal) } | Select-Object -Last 1
    if (-not $line) { return "" }
    return $line.Substring($prefix.Length).Trim()
}

function New-PasswordHash([string]$Password) {
    $salt = New-Object byte[] 16
    [Security.Cryptography.RandomNumberGenerator]::Fill($salt)
    $iterations = 600000
    $derive = [Security.Cryptography.Rfc2898DeriveBytes]::new($Password, $salt, $iterations, [Security.Cryptography.HashAlgorithmName]::SHA256)
    try { $digest = $derive.GetBytes(32) } finally { $derive.Dispose() }
    $saltText = [Convert]::ToBase64String($salt).TrimEnd('=').Replace('+','-').Replace('/','_')
    $digestText = [Convert]::ToBase64String($digest).TrimEnd('=').Replace('+','-').Replace('/','_')
    return "pbkdf2_sha256`$$iterations`$$saltText`$$digestText"
}

$lines = [System.Collections.Generic.List[string]]::new()
if (Test-Path $EnvFile) { Get-Content -LiteralPath $EnvFile | ForEach-Object { $lines.Add($_) } }
Set-EnvValue $lines "APP_ENV" "production"
Set-EnvValue $lines "API_AUTH_REQUIRED" "true"
foreach ($name in @("API_CONTROL_TOKEN", "DASHBOARD_SESSION_SECRET", "BRAIN_INSTRUCTION_SECRET")) {
    if ([string]::IsNullOrWhiteSpace((Get-EnvValue $lines $name))) { Set-EnvValue $lines $name (New-Secret) }
}

$credentialRoot = Join-Path (Split-Path -Parent $EnvFile) "state"
if (-not (Test-Path $credentialRoot)) { New-Item -ItemType Directory -Path $credentialRoot | Out-Null }
$passwordFile = Join-Path $credentialRoot "dashboard-bootstrap-password.txt"
if ([string]::IsNullOrWhiteSpace((Get-EnvValue $lines "DASHBOARD_PASSWORD_HASH"))) {
    $dashboardPassword = New-Secret 24
    Set-EnvValue $lines "DASHBOARD_PASSWORD_HASH" (New-PasswordHash $dashboardPassword)
    Set-Content -LiteralPath $passwordFile -Value $dashboardPassword -Encoding ascii
    icacls $passwordFile /inheritance:r /grant:r "${env:USERNAME}:R" "SYSTEM:F" | Out-Null
    $dashboardPassword = $null
}

$existingDeviceTokens = Get-EnvValue $lines "DEVICE_API_TOKENS_JSON"
if ([string]::IsNullOrWhiteSpace($existingDeviceTokens) -or $existingDeviceTokens -eq "{}") {
    $deviceTokens = [ordered]@{}
    foreach ($machineId in @("dev-laptop", "research-laptop", "business-laptop")) { $deviceTokens[$machineId] = New-Secret }
    Set-EnvValue $lines "DEVICE_API_TOKENS_JSON" ($deviceTokens | ConvertTo-Json -Compress)
}

Set-Content -LiteralPath $EnvFile -Value $lines -Encoding utf8
Write-Host "Control-plane security initialized in $EnvFile."
Write-Host "The dashboard bootstrap password is stored locally at $passwordFile with restricted ACLs."
Write-Host "Device tokens remain only in .env until installed out-of-band on each matching managed node."
