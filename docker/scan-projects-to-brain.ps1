param(
    [string]$BrainHost = "100.70.49.32",
    [string]$MachineId = $env:COMPUTERNAME,
    [string[]]$Roots = @(),
    [string]$RootList = "",
    [int]$MaxProjects = 40,
    [int]$MaxFilesPerProject = 350,
    [switch]$IncludeDesktop,
    [switch]$PostToBrain
)

$ErrorActionPreference = "Stop"

function Normalize-Host {
    param([string]$Value)
    $hostValue = (($Value.Trim() -replace "^https?://", "" -split "/")[0] -split ":" | Select-Object -First 1)
    if ($hostValue -match "^[A-Za-z]$") {
        throw "BrainHost resolved to '$hostValue'. Pass -BrainHost 100.70.49.32 and pass project paths with -RootList or -Roots."
    }
    return $hostValue
}

function Get-CodexRoots {
    param([string[]]$SelectedRoots = @())
    $roots = New-Object System.Collections.Generic.List[string]
    $allSelectedRoots = New-Object System.Collections.Generic.List[string]
    foreach ($root in $SelectedRoots) {
        if ($root) { $allSelectedRoots.Add($root) }
    }
    if ($RootList) { $allSelectedRoots.Add($RootList) }
    foreach ($root in $allSelectedRoots) {
        if (-not $root) { continue }
        foreach ($candidate in ($root -split "[,;]")) {
            $clean = $candidate.Trim().Trim('"').Trim("'")
            if ($clean) { $roots.Add($clean) }
        }
    }
    if ($roots.Count -gt 0) {
        @($roots.ToArray()) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique | Select-Object -First $MaxProjects
        return
    }

    $statePath = Join-Path $env:USERPROFILE ".codex\.codex-global-state.json"
    if (Test-Path -LiteralPath $statePath) {
        try {
            $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
            foreach ($item in @($state.'electron-persisted-atom-state'.'electron-saved-workspace-roots')) {
                if ($item) { $roots.Add([string]$item) }
            }
            foreach ($item in @($state.'electron-persisted-atom-state'.'active-workspace-roots')) {
                if ($item) { $roots.Add([string]$item) }
            }
        } catch {
            Write-Warning "Could not parse Codex workspace state: $($_.Exception.Message)"
        }
    }
    if ($IncludeDesktop) {
        $desktop = Join-Path $env:USERPROFILE "OneDrive\Desktop"
        if (Test-Path -LiteralPath $desktop) {
            Get-ChildItem -LiteralPath $desktop -Directory -ErrorAction SilentlyContinue | ForEach-Object { $roots.Add($_.FullName) }
        }
    }
    if ($roots.Count -eq 0 -and (Get-Location)) {
        $roots.Add((Get-Location).Path)
    }
    @($roots.ToArray()) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique | Select-Object -First $MaxProjects
}

function Get-ProjectKind {
    param([string]$Path)
    if (Test-Path -LiteralPath (Join-Path $Path "package.json")) { return "javascript" }
    if ((Test-Path -LiteralPath (Join-Path $Path "pyproject.toml")) -or (Get-ChildItem -LiteralPath $Path -File -Filter *.py -ErrorAction SilentlyContinue | Select-Object -First 1)) { return "python" }
    if (Get-ChildItem -LiteralPath $Path -File -Filter *.html -ErrorAction SilentlyContinue | Select-Object -First 1) { return "web" }
    return "folder"
}

function Scan-Project {
    param([string]$Path)
    $excluded = @(".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".next", "dist", "build")
    $files = New-Object System.Collections.Generic.List[object]
    $suffixCounts = @{}
    $flags = @{
        secret_named_files = 0
        large_files = 0
        todo_or_security_markers = 0
    }
    $buildFiles = New-Object System.Collections.Generic.List[string]
    $docs = New-Object System.Collections.Generic.List[string]
    $recent = New-Object System.Collections.Generic.List[object]
    $queue = New-Object System.Collections.Queue
    $queue.Enqueue((Get-Item -LiteralPath $Path))

    while ($queue.Count -gt 0 -and $files.Count -lt $MaxFilesPerProject) {
        $dir = $queue.Dequeue()
        Get-ChildItem -LiteralPath $dir.FullName -Force -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.PSIsContainer) {
                if ($excluded -notcontains $_.Name) { $queue.Enqueue($_) }
                return
            }
            if ($files.Count -ge $MaxFilesPerProject) { return }
            $rel = Resolve-Path -LiteralPath $_.FullName -Relative
            $rel = $rel -replace "^\.\\", ""
            $files.Add($rel)
            $suffix = if ($_.Extension) { $_.Extension.ToLowerInvariant() } else { "<none>" }
            $suffixCounts[$suffix] = 1 + [int]($suffixCounts[$suffix])
            if (@("package.json", "pyproject.toml", "requirements.txt", "Dockerfile", "docker-compose.yml") -contains $_.Name) { $buildFiles.Add($rel) }
            if (@(".md", ".txt") -contains $_.Extension.ToLowerInvariant()) { $docs.Add($rel) }
            if ($_.Name -match "(?i)(secret|token|apikey|api_key|key|password|^\.env)") { $flags.secret_named_files++ }
            if ($_.Length -gt 5000000) { $flags.large_files++ }
            if (@(".md", ".txt", ".json", ".py", ".js", ".ts", ".tsx", ".html", ".css") -contains $_.Extension.ToLowerInvariant() -and $_.Length -lt 400000) {
                try {
                    $text = Get-Content -LiteralPath $_.FullName -Raw -ErrorAction Stop
                    if ($text -match "(?i)\b(TODO|FIXME|SECURITY|placeholder|mock|blocked_external_secret)\b") { $flags.todo_or_security_markers++ }
                } catch {}
            }
            $recent.Add([pscustomobject]@{ path = $rel; ticks = $_.LastWriteTimeUtc.Ticks })
        }
    }

    [pscustomobject]@{
        name = Split-Path -Leaf $Path
        path = $Path
        kind = Get-ProjectKind $Path
        status = "scanned"
        file_count_sampled = $files.Count
        scan_limited = ($files.Count -ge $MaxFilesPerProject)
        suffix_counts = $suffixCounts
        flag_counts = $flags
        build_files = @($buildFiles | Select-Object -First 20)
        docs = @($docs | Select-Object -First 20)
        recent_files = @($recent | Sort-Object ticks -Descending | Select-Object -First 12 -ExpandProperty path)
    }
}

$BrainHost = Normalize-Host $BrainHost
$projects = @(Get-CodexRoots -SelectedRoots $Roots | ForEach-Object { Scan-Project $_ })
$payload = [pscustomobject]@{
    source = "codex-project-scanner"
    machine_id = $MachineId
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    projects = $projects
}

if ($PostToBrain) {
    Invoke-RestMethod -Method Post `
        -Uri "http://$BrainHost`:8088/project-intake/import-scan" `
        -ContentType "application/json" `
        -Body ($payload | ConvertTo-Json -Depth 20) `
        -TimeoutSec 45 | ConvertTo-Json -Depth 12
} else {
    $payload | ConvertTo-Json -Depth 20
}
