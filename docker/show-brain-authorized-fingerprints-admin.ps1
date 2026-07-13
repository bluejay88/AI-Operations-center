param(
    [string]$UserName = "aiopsbrain"
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this PowerShell script as Administrator."
    }
}

function Show-KeyFile {
    param([string]$Path)

    Write-Host ""
    Write-Host "Checking: $Path"
    if (!(Test-Path $Path)) {
        Write-Host "Missing."
        return
    }

    $valid = @()
    foreach ($line in Get-Content -Path $Path -ErrorAction SilentlyContinue) {
        $trimmed = $line.Trim()
        if ($trimmed -match "^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+)\s+\S+(\s+.*)?$") {
            $valid += $trimmed
        }
    }

    if ($valid.Count -eq 0) {
        Write-Host "No valid public keys found in this file."
        return
    }

    $temp = Join-Path $env:TEMP ("aiops-authorized-" + [guid]::NewGuid().ToString() + ".pub")
    try {
        $index = 1
        foreach ($key in $valid) {
            Set-Content -Path $temp -Value $key -Encoding ascii
            Write-Host "Key $index fingerprint:"
            ssh-keygen -lf $temp
            $index += 1
        }
    } finally {
        Remove-Item -Path $temp -Force -ErrorAction SilentlyContinue
    }
}

Assert-Admin

$profileRoot = Join-Path "C:\Users" $UserName
$userAuthorizedKeys = Join-Path $profileRoot ".ssh\authorized_keys"
$adminAuthorizedKeys = Join-Path $env:ProgramData "ssh\administrators_authorized_keys"

Write-Host "Brain authorized SSH key fingerprints for $UserName"
Show-KeyFile -Path $userAuthorizedKeys
Show-KeyFile -Path $adminAuthorizedKeys
