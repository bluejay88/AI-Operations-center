param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("business-laptop", "research-laptop", "dev-laptop")]
    [string]$MachineId,

    [Parameter(Mandatory=$false)]
    [string]$BrainHost = "100.70.49.32",

    [switch]$RenameTailscale,
    [switch]$SkipPrereqs,
    [switch]$SkipChatGPT,
    [switch]$SkipBenchmark
)

$ErrorActionPreference = "Stop"

function Test-CommandExists {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-ChatGPTInstalled {
    $appx = Get-AppxPackage -Name "*ChatGPT*" -ErrorAction SilentlyContinue
    if ($appx) {
        return $true
    }

    if (Test-CommandExists winget) {
        $listOutput = winget list --name ChatGPT --accept-source-agreements 2>$null
        if ($LASTEXITCODE -eq 0 -and ($listOutput -match "ChatGPT")) {
            return $true
        }
    }

    return $false
}

function Install-ChatGPT {
    if (Test-ChatGPTInstalled) {
        Write-Host "ChatGPT appears to already be installed."
        return
    }

    if (Test-CommandExists winget) {
        Write-Host "Installing ChatGPT from Microsoft Store via winget..."
        winget install --id 9PLM9XGG6VKS --source msstore --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) {
            Write-Host "ChatGPT install command finished."
            return
        }

        Write-Host "winget could not complete the ChatGPT install. Opening the official ChatGPT download page."
    } else {
        Write-Host "winget was not found. Opening the official ChatGPT download page."
    }

    Start-Process "https://chatgpt.com/download"
}

Write-Host "Starting AI Operations Center onboarding for $MachineId..."

.\docker\show-connected-message.ps1

if (!$SkipPrereqs) {
    .\docker\install-laptop-prereqs.ps1 -MachineId $MachineId
}

if (!$SkipChatGPT) {
    Install-ChatGPT
}

.\docker\join-worker.ps1 -MachineId $MachineId -BrainHost $BrainHost -RenameTailscale:$RenameTailscale

if (!$SkipBenchmark) {
    .\docker\run-benchmark.ps1 -MachineId $MachineId -BrainHost $BrainHost
}

Write-Host "Onboarding complete for $MachineId."
Write-Host "The Bleujay Brain worker should now report online to http://$BrainHost`:8088/status."
