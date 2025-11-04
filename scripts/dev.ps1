param()

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path $scriptDir
$clientDir = Join-Path $rootDir 'client'

function RequireCommand([string]$command, [string]$message) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        Write-Error $message
    }
}

RequireCommand 'uv' 'uv is required. Run scripts\bootstrap.ps1 first.'
RequireCommand 'npm' 'npm is required to launch the Electron client.'

Write-Host 'Starting API server...'
$apiProcess = Start-Process uv -ArgumentList @('run','--directory', $rootDir, 'python', 'server_api/main.py') -NoNewWindow -PassThru

Write-Host 'Starting PyTC server...'
$pyProcess = Start-Process uv -ArgumentList @('run','--directory', $rootDir, 'python', 'server_pytc/main.py') -NoNewWindow -PassThru

Push-Location $clientDir
try {
    Write-Host 'Launching Electron client...'
    npm run electron
} finally {
    Pop-Location
    if ($apiProcess -and -not $apiProcess.HasExited) {
        $apiProcess.Kill()
    }
    if ($pyProcess -and -not $pyProcess.HasExited) {
        $pyProcess.Kill()
    }
}
