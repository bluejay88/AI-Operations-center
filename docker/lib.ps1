function Assert-DockerAvailable {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (!$docker -and (Test-Path "C:\Program Files\Docker\Docker\resources\bin\docker.exe")) {
        $dockerBin = "C:\Program Files\Docker\Docker\resources\bin"
        $env:Path = "$dockerBin;$env:Path"
        $docker = Get-Command docker -ErrorAction SilentlyContinue
    }

    if (!$docker) {
        throw "Docker CLI was not found. Install Docker Desktop, start it, then reopen PowerShell and rerun this command."
    }

    $repoDockerConfig = Join-Path (Get-Location) ".docker"
    if (Test-Path $repoDockerConfig) {
        $env:DOCKER_CONFIG = $repoDockerConfig
    }

    try {
        docker info *> $null
    } catch {
        throw "Docker CLI was found, but Docker Desktop is not running or is not ready. Start Docker Desktop and try again."
    }
}

function Get-TailscaleExe {
    $tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($tailscale) {
        return $tailscale.Source
    }

    $programFilesPath = "C:\Program Files\Tailscale\tailscale.exe"
    if (Test-Path $programFilesPath) {
        return $programFilesPath
    }

    return $null
}

function Assert-TailscaleAvailable {
    $tailscaleExe = Get-TailscaleExe
    if (!$tailscaleExe) {
        throw "Tailscale CLI was not found. Install Tailscale and sign in before joining workers."
    }
    return $tailscaleExe
}
