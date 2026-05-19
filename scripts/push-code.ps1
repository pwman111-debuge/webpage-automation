# scripts/push-code.ps1
# Push code/workflow changes to webpage-automation via .git-code separate git dir.
# Usage: powershell -File scripts/push-code.ps1 -Message "feat: workflow X update"

param(
    [Parameter(Mandatory = $true)]
    [string]$Message
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Set-Location $workspace

$gitDir = '.git-code'

if (-not (Test-Path $gitDir)) {
    Write-Error "$gitDir not found. Dual git structure is not initialized."
}

$pending = git --git-dir=$gitDir status --porcelain
if (-not $pending) {
    Write-Host "No changes to push."
    exit 0
}

Write-Host "=== Changes to push to webpage-automation ==="
git --git-dir=$gitDir status --short
Write-Host ""

git --git-dir=$gitDir add .
git --git-dir=$gitDir commit -m $Message
git --git-dir=$gitDir push origin main

Write-Host ""
Write-Host "Done: webpage-automation main"
git --git-dir=$gitDir log --oneline -1
