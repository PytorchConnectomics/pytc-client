$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path $scriptDir
$clientDir = Join-Path $rootDir 'client'

function RequireCommand([string]$command, [string]$message) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        Write-Error $message
    }
}

RequireCommand 'uv' 'uv is required. Install it from https://docs.astral.sh/uv/.'
RequireCommand 'npm' 'npm is required to run the Electron client.'

Write-Host 'Starting data server...'
$dataProcess = Start-Process uv -ArgumentList @('run','--directory', $rootDir, 'python', 'server_api/scripts/serve_data.py') -NoNewWindow -PassThru

Write-Host 'Starting API server...'
$apiProcess = Start-Process uv -ArgumentList @('run','--directory', $rootDir, 'python', '-m', 'server_api.main') -NoNewWindow -PassThru

Write-Host 'Starting PyTC server...'
$pyProcess = Start-Process uv -ArgumentList @('run','--directory', $rootDir, 'python', '-m', 'server_pytc.main') -NoNewWindow -PassThru

function Wait-ForReact {
    param(
        [int]$MaxAttempts = 60
    )
    $attempt = 1
    while ($attempt -le $MaxAttempts) {
        try {
            $response = Invoke-WebRequest 'http://localhost:3000' -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host 'React is ready'
                return $true
            }
        } catch {
            # Ignore and retry
        }
        Write-Host "Waiting for React (attempt $attempt/$MaxAttempts)..."
        $attempt++
        Start-Sleep -Seconds 1
    }
    Write-Error "ERROR: React server failed to start within $MaxAttempts seconds"
    return $false
}

Push-Location $clientDir
Write-Host 'Starting React server...'
$env:BROWSER = 'none'
$reactProcess = Start-Process npm -ArgumentList 'start' -NoNewWindow -PassThru -RedirectStandardOutput $null -RedirectStandardError $null
if (Wait-ForReact) {
    Write-Host 'Starting Electron client...'
    $env:ENVIRONMENT = 'development'
    npm run electron
} else {
    throw 'Failed to start React server'
}
