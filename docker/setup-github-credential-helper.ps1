param(
    [string]$GitUserName = "bluejay88",
    [string]$RepositoryUrl = "https://github.com/bluejay88/AI-Operations-center.git"
)

$ErrorActionPreference = "Stop"

git config --global credential.helper manager
git config --global user.name $GitUserName

$remote = git remote get-url origin 2>$null
if (!$remote) {
    git remote add origin $RepositoryUrl
} elseif ($remote -ne $RepositoryUrl) {
    git remote set-url origin $RepositoryUrl
}

Write-Host "Git credential helper is set to Windows Git Credential Manager."
Write-Host "Repository origin is $RepositoryUrl"
Write-Host ""
Write-Host "Run this once in an interactive PowerShell window:"
Write-Host "  git push origin master"
Write-Host ""
Write-Host "Approve/sign in as Bluejay88 when Git Credential Manager opens."
Write-Host "After that, Brain update scripts can use the stored credential without asking again."
