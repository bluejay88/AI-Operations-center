param([string]$ComputerName = "100.71.82.122")

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this rescue script as Administrator."
}

$trustedPath = "WSMan:\localhost\Client\TrustedHosts"
$previous = (Get-Item -LiteralPath $trustedPath).Value
$session = $null
try {
    # Exact Tailscale /32 only, and restored in finally. This recovery channel
    # is bounded to the already authenticated tailnet node.
    Set-Item -LiteralPath $trustedPath -Value $ComputerName -Force
    $session = New-PSSession -ComputerName $ComputerName
    $result = Invoke-Command -Session $session -ScriptBlock {
        $path = "$env:ProgramData\ssh\sshd_config"
        $names = @(
            "PubkeyAuthentication", "PasswordAuthentication", "PermitEmptyPasswords",
            "KbdInteractiveAuthentication", "AuthenticationMethods", "MaxAuthTries",
            "LogLevel", "AllowUsers", "AllowTcpForwarding", "AllowAgentForwarding",
            "PermitTunnel", "GatewayPorts", "PermitTTY", "PermitUserEnvironment", "ForceCommand"
        )
        $lines = @(Get-Content -LiteralPath $path)
        $insideMatch = $false
        $clean = foreach ($line in $lines) {
            if ($line -match "^\s*Match\s+") { $insideMatch = $true }
            $injected = $false
            if ($insideMatch) {
                foreach ($name in $names) {
                    if ($line -match ("^\s*#?\s*" + [regex]::Escape($name) + "\s+")) {
                        $injected = $true
                        break
                    }
                }
            }
            if (-not $injected) { $line }
        }
        Set-Content -LiteralPath $path -Value $clean -Encoding ascii
        $validation = & sshd -t -f $path 2>&1
        if ($LASTEXITCODE -ne 0) { throw "sshd_config remains invalid: $($validation -join '; ')" }
        Start-Service sshd
        [pscustomobject]@{ machine = $env:COMPUTERNAME; sshd = (Get-Service sshd).Status.ToString() }
    }
    $result | Format-List
} finally {
    if ($session) { Remove-PSSession $session }
    if ([string]::IsNullOrWhiteSpace($previous)) {
        Clear-Item -LiteralPath $trustedPath -Force
    } else {
        Set-Item -LiteralPath $trustedPath -Value $previous -Force
    }
}
