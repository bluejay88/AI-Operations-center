param(
    [string]$Message = "Bleujay Brain is now connected",
    [string]$Title = "AI Operations Center"
)

$ErrorActionPreference = "Continue"

try {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($Message, $Title, "OK", "Information") | Out-Null
    exit 0
} catch {
    Write-Host "Windows message box failed, trying msg.exe fallback..."
}

$sessionName = $env:SESSIONNAME
if ([string]::IsNullOrWhiteSpace($sessionName)) {
    $sessionName = "*"
}

try {
    msg.exe $sessionName /TIME:30 "$Title - $Message"
} catch {
    Write-Host "$Title - $Message"
}
