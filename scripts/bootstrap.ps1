$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path $scriptDir
$clientDir = Join-Path $rootDir 'client'
$pytcDir = Join-Path $rootDir 'pytorch_connectomics'
$targetCommit = '04c2a35e78a1a7ca1138f83a98fc3ef27097abd4'
$targetRef = 'refs/heads/pytc-client-legacy-runtime'
$pytcRepository = 'https://github.com/PytorchConnectomics/pytorch_connectomics.git'

function RequireCommand([string]$command, [string]$message) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        Write-Error $message
    }
}

RequireCommand 'uv' 'uv is required. Install it from https://docs.astral.sh/uv/.'
RequireCommand 'npm' 'npm is required to run the Electron client.'
RequireCommand 'git' 'git is required to download pytorch_connectomics.'

Write-Host 'Preparing pytorch_connectomics dependency...'
if (Test-Path (Join-Path $pytcDir '.git')) {
    Push-Location $pytcDir
    $currentCommit = (git rev-parse --verify HEAD 2> $null) -replace '\s', ''
    if ($currentCommit -ne $targetCommit) {
        git fetch --depth 1 origin $targetRef
        $fetchedCommit = (git rev-parse FETCH_HEAD) -replace '\s', ''
        if ($fetchedCommit -ne $targetCommit) {
            throw "$targetRef resolved to $fetchedCommit, expected $targetCommit."
        }
        git checkout --detach $targetCommit
    }
    Pop-Location
} else {
    if (Test-Path $pytcDir) {
        if ((Get-ChildItem -Force $pytcDir | Measure-Object).Count -ne 0) {
            throw "$pytcDir exists but is not an empty Git checkout."
        }
        Remove-Item $pytcDir
    }

    New-Item -ItemType Directory -Path $pytcDir | Out-Null
    git -C $pytcDir init --quiet
    git -C $pytcDir remote add origin $pytcRepository
    git -C $pytcDir fetch --depth 1 origin $targetRef
    $fetchedCommit = (git -C $pytcDir rev-parse FETCH_HEAD) -replace '\s', ''
    if ($fetchedCommit -ne $targetCommit) {
        throw "$targetRef resolved to $fetchedCommit, expected $targetCommit."
    }
    git -C $pytcDir checkout --detach $targetCommit
}

Write-Host 'Synchronizing Python environment with uv...'
uv sync --python 3.11 --directory $rootDir

Write-Host 'Installing frontend dependencies...'
Push-Location $clientDir
npm install
Pop-Location

Write-Host 'Bootstrap complete. Use scripts\start.ps1 to launch the app.'
