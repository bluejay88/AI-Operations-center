$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw "Run as Administrator on the affected laptop." }

$path = "$env:ProgramData\ssh\sshd_config"
$backup = "$path.pre-aiops-local-rescue"
Copy-Item -LiteralPath $path -Destination $backup -Force
$names = @(
    "PubkeyAuthentication", "PasswordAuthentication", "PermitEmptyPasswords",
    "KbdInteractiveAuthentication", "AuthenticationMethods", "MaxAuthTries",
    "LogLevel", "AllowUsers", "AllowTcpForwarding", "AllowAgentForwarding",
    "PermitTunnel", "GatewayPorts", "PermitTTY", "PermitUserEnvironment", "ForceCommand"
)
$insideMatch = $false
$clean = foreach ($line in @(Get-Content -LiteralPath $path)) {
    if ($line -match "^\s*Match\s+") { $insideMatch = $true }
    $injected = $false
    if ($insideMatch) {
        foreach ($name in $names) {
            if ($line -match ("^\s*#?\s*" + [regex]::Escape($name) + "\s+")) { $injected = $true; break }
        }
    }
    if (-not $injected) { $line }
}
Set-Content -LiteralPath $path -Value $clean -Encoding ascii
$validation = & sshd -t -f $path 2>&1
if ($LASTEXITCODE -ne 0) {
    Copy-Item -LiteralPath $backup -Destination $path -Force
    throw "sshd_config validation failed; original restored: $($validation -join '; ')"
}
Start-Service sshd
Write-Host "OpenSSH recovered locally. Service=$((Get-Service sshd).Status). Continue with the fixed hardened installer from the Brain."
