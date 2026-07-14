param(
    [string]$EnvFile = (Join-Path (Split-Path -Parent $PSScriptRoot) ".env")
)

$ErrorActionPreference = "Stop"

function New-Secret([int]$Bytes = 48) {
    $buffer = New-Object byte[] $Bytes
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
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

function Get-PostgresPasswordFromUrl([string]$Url) {
    if ([string]::IsNullOrWhiteSpace($Url)) { return "" }
    try {
        $uri = [Uri]$Url
        if ([string]::IsNullOrWhiteSpace($uri.UserInfo) -or -not $uri.UserInfo.Contains(":")) { return "" }
        $password = $uri.UserInfo.Substring($uri.UserInfo.IndexOf(":") + 1)
        return [Uri]::UnescapeDataString($password)
    } catch {
        return ""
    }
}

function New-PasswordHash([string]$Password) {
    $salt = New-Object byte[] 16
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($salt) } finally { $rng.Dispose() }
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
Set-EnvValue $lines "BRAIN_BIND_ADDRESS" "100.70.49.32"

$postgresPassword = Get-EnvValue $lines "POSTGRES_PASSWORD"
if ([string]::IsNullOrWhiteSpace($postgresPassword)) {
    $postgresPassword = Get-PostgresPasswordFromUrl (Get-EnvValue $lines "DATABASE_URL")
    if ([string]::IsNullOrWhiteSpace($postgresPassword)) {
        $postgresPassword = New-Secret
        Set-EnvValue $lines "DATABASE_URL" "postgresql://aiops:$postgresPassword@postgres:5432/aiops"
        Set-EnvValue $lines "LOCAL_DATABASE_URL" "postgresql://aiops:$postgresPassword@localhost:5432/aiops"
    }
    Set-EnvValue $lines "POSTGRES_PASSWORD" $postgresPassword
}

foreach ($name in @("API_CONTROL_TOKEN", "DASHBOARD_SESSION_SECRET", "BRAIN_INSTRUCTION_SECRET")) {
    if ([string]::IsNullOrWhiteSpace((Get-EnvValue $lines $name))) { Set-EnvValue $lines $name (New-Secret) }
}
$n8nKey = Get-EnvValue $lines "N8N_ENCRYPTION_KEY"
if ([string]::IsNullOrWhiteSpace($n8nKey) -or $n8nKey -eq "replace-with-a-long-random-secret") {
    Set-EnvValue $lines "N8N_ENCRYPTION_KEY" (New-Secret)
}

Set-EnvValue $lines "PET_KEY_REGISTRY_REQUIRED" "true"
if ([string]::IsNullOrWhiteSpace((Get-EnvValue $lines "PET_BROWSER_ALLOWED_SCHEMES"))) {
    Set-EnvValue $lines "PET_BROWSER_ALLOWED_SCHEMES" "https"
}
if ([string]::IsNullOrWhiteSpace((Get-EnvValue $lines "PET_BROWSER_ALLOWED_DOMAINS"))) {
    Set-EnvValue $lines "PET_BROWSER_ALLOWED_DOMAINS" "chatgpt.com,openai.com,youtube.com"
}

$petGeneration = "v" + [DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
foreach ($machineId in @("brain-gaming-pc", "dev-laptop", "research-laptop", "business-laptop")) {
    $suffix = $machineId.ToUpperInvariant().Replace("-", "_")
    if ([string]::IsNullOrWhiteSpace((Get-EnvValue $lines "PET_DISPATCH_KEY_ID_$suffix"))) {
        Set-EnvValue $lines "PET_DISPATCH_KEY_ID_$suffix" "dispatch:${machineId}:$petGeneration"
    }
    if ([string]::IsNullOrWhiteSpace((Get-EnvValue $lines "PET_RECEIPT_KEY_ID_$suffix"))) {
        Set-EnvValue $lines "PET_RECEIPT_KEY_ID_$suffix" "receipt:${machineId}:$petGeneration"
    }
    $dispatchSecret = Get-EnvValue $lines "PET_DISPATCH_SIGNING_KEY_$suffix"
    if ([string]::IsNullOrWhiteSpace($dispatchSecret)) { $dispatchSecret = New-Secret }
    Set-EnvValue $lines "PET_DISPATCH_SIGNING_KEY_$suffix" $dispatchSecret
    Set-EnvValue $lines "PET_DISPATCH_VERIFY_KEY_$suffix" $dispatchSecret

    $receiptSecret = Get-EnvValue $lines "PET_RECEIPT_SIGNING_KEY_$suffix"
    if ([string]::IsNullOrWhiteSpace($receiptSecret)) { $receiptSecret = New-Secret }
    Set-EnvValue $lines "PET_RECEIPT_SIGNING_KEY_$suffix" $receiptSecret
    Set-EnvValue $lines "PET_RECEIPT_VERIFY_KEY_$suffix" $receiptSecret
}

$credentialRoot = Join-Path (Split-Path -Parent $EnvFile) "state"
if (-not (Test-Path $credentialRoot)) { New-Item -ItemType Directory -Path $credentialRoot | Out-Null }
$passwordFile = Join-Path $credentialRoot "dashboard-bootstrap-password.txt"
if ([string]::IsNullOrWhiteSpace((Get-EnvValue $lines "DASHBOARD_PASSWORD_HASH"))) {
    $dashboardPassword = New-Secret 24
    Set-EnvValue $lines "DASHBOARD_PASSWORD_HASH" ("'" + (New-PasswordHash $dashboardPassword) + "'")
    Set-Content -LiteralPath $passwordFile -Value $dashboardPassword -Encoding ascii
    $currentUser = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
    icacls $passwordFile /inheritance:r /grant:r "${currentUser}:R" "SYSTEM:F" | Out-Null
    $dashboardPassword = $null
}
$storedPasswordHash = Get-EnvValue $lines "DASHBOARD_PASSWORD_HASH"
if ($storedPasswordHash -and -not $storedPasswordHash.StartsWith("'")) {
    Set-EnvValue $lines "DASHBOARD_PASSWORD_HASH" ("'" + $storedPasswordHash.Trim("'", '"') + "'")
}

$existingDeviceTokens = Get-EnvValue $lines "DEVICE_API_TOKENS_JSON"
if ([string]::IsNullOrWhiteSpace($existingDeviceTokens) -or $existingDeviceTokens -eq "{}") {
    $deviceTokens = [ordered]@{}
    foreach ($machineId in @("dev-laptop", "research-laptop", "business-laptop")) { $deviceTokens[$machineId] = New-Secret }
    Set-EnvValue $lines "DEVICE_API_TOKENS_JSON" ($deviceTokens | ConvertTo-Json -Compress)
}

$existingBrokerKeys = Get-EnvValue $lines "SSH_BROKER_ENVELOPE_KEYS_JSON"
if ([string]::IsNullOrWhiteSpace($existingBrokerKeys) -or $existingBrokerKeys -eq "{}") {
    $brokerKeys = [ordered]@{}
    foreach ($machineId in @("dev-laptop", "research-laptop", "business-laptop")) { $brokerKeys[$machineId] = New-Secret }
    Set-EnvValue $lines "SSH_BROKER_ENVELOPE_KEYS_JSON" ($brokerKeys | ConvertTo-Json -Compress)
}

Set-Content -LiteralPath $EnvFile -Value $lines -Encoding utf8
Write-Host "Control-plane security initialized in $EnvFile."
Write-Host "The dashboard bootstrap password is stored locally at $passwordFile with restricted ACLs."
Write-Host "Device tokens remain only in .env until installed out-of-band on each matching managed node."
Write-Host "PET directional secrets were provisioned without displaying them."
