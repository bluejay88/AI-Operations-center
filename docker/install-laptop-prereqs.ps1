param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId
)

$ErrorActionPreference = "Stop"

$winget = Get-Command winget -ErrorAction SilentlyContinue
if (!$winget) {
    Write-Host "winget was not found. Install these manually:"
    Write-Host "- Tailscale: https://tailscale.com/download/windows"
    Write-Host "- Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Write-Host "- Git for Windows: https://git-scm.com/download/win"
    Write-Host "- VS Code: https://code.visualstudio.com/"
    Write-Host "- Chrome: https://www.google.com/chrome/"
    if ($MachineId -eq "dev-laptop") {
        Write-Host "- Python 3.12: https://www.python.org/downloads/windows/"
        Write-Host "- Node.js LTS: https://nodejs.org/"
    }
    exit 1
}

winget install --id Git.Git --silent --accept-package-agreements --accept-source-agreements
winget install --id Docker.DockerDesktop --silent --accept-package-agreements --accept-source-agreements
winget install --id Microsoft.VisualStudioCode --silent --accept-package-agreements --accept-source-agreements
winget install --id Google.Chrome --silent --accept-package-agreements --accept-source-agreements

if ($MachineId -eq "dev-laptop") {
    winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    winget install --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
}

Write-Host "Prerequisite install commands finished for $MachineId."
Write-Host "Restart the laptop if Docker Desktop or WSL requests it."

