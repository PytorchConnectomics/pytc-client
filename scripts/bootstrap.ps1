$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path $scriptDir
$clientDir = Join-Path $rootDir 'client'
$pytcDir = Join-Path $rootDir 'pytorch_connectomics'

function RequireCommand([string]$command, [string]$message) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        Write-Error $message
    }
}

RequireCommand 'uv' 'uv is required. Install it from https://docs.astral.sh/uv/.'
RequireCommand 'npm' 'npm is required to run the Electron client.'
RequireCommand 'git' 'git is required to download pytorch_connectomics.'

Write-Host 'Synchronizing Python environment with uv...'
uv sync --python 3.11 --directory $rootDir

Write-Host 'Preparing pytorch_connectomics dependency...'
if (Test-Path (Join-Path $pytcDir '.git')) {
    Push-Location $pytcDir
    git fetch origin *> $null
    $currentCommit = (git rev-parse HEAD) -replace '\s', ''
    $targetCommit = '20ccfde'
    if ($currentCommit -ne $targetCommit) {
        git checkout $targetCommit
    }
    Pop-Location
} else {
    git clone 'https://github.com/zudi-lin/pytorch_connectomics.git' $pytcDir
    Push-Location $pytcDir
    git checkout '20ccfde'
    Pop-Location
}

Write-Host 'Installing frontend dependencies...'
Push-Location $clientDir
npm install
Pop-Location

Write-Host 'Bootstrap complete. Use scripts\start.ps1 to launch the app.'
