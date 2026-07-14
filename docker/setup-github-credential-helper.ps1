param(
    [string]$GitHubUserName = "Bluejay88",
    [string]$CommitAuthorName = "Bluejay88",
    [string]$RepositoryUrl = "https://github.com/bluejay88/AI-Operations-center.git"
)

$ErrorActionPreference = "Stop"

if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git for Windows is not installed or is not on PATH."
}

git credential-manager --version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Git Credential Manager is required. Repair Git for Windows and enable Git Credential Manager."
}

# Collapse stale/duplicate global helper entries to one supported GCM value.
git config --global --replace-all credential.helper manager
git config --global credential.https://github.com.username $GitHubUserName
git config --global user.name $CommitAuthorName

if ($LASTEXITCODE -ne 0) {
    throw "Could not persist GitHub defaults in the current Windows user's Git configuration."
}

$remote = git remote get-url origin 2>$null
if (!$remote) {
    git remote add origin $RepositoryUrl
} elseif ($remote -ne $RepositoryUrl) {
    git remote set-url origin $RepositoryUrl
}

Write-Host "Git credential helper is set to Windows Git Credential Manager."
Write-Host "GitHub login hint is $GitHubUserName."
Write-Host "Commit author name is $CommitAuthorName."
Write-Host "Repository origin is $RepositoryUrl"
Write-Host ""
Write-Host "Run this once in an interactive PowerShell window:"
Write-Host "  git push origin master"
Write-Host ""
Write-Host "Approve/sign in as $GitHubUserName when Git Credential Manager opens."
Write-Host "Git Credential Manager stores the resulting OAuth credential in Windows Credential Manager."
Write-Host "No password, personal access token, or OAuth token is written to this repository."
