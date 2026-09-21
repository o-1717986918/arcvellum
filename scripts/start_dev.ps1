[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$ApiPort = 8791,

    [ValidateRange(1, 65535)]
    [int]$ClientPort = 5173
)

$ErrorActionPreference = "Stop"
$Repository = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Repository ".venv\Scripts\python.exe"
$PackageJson = Join-Path $Repository "package.json"

function Assert-PortAvailable {
    param(
        [int]$Port,
        [string]$Label
    )

    $Listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $Listener) {
        throw "$Label port $Port is already in use (PID $($Listener.OwningProcess)). Choose another port; this script will not stop an existing process."
    }
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "ArcVellum's repository virtual environment is missing: $Python"
}

Assert-PortAvailable -Port $ApiPort -Label "API"
Assert-PortAvailable -Port $ClientPort -Label "Client"

$PreviousPythonPath = $env:PYTHONPATH
$PreviousApiOrigin = $env:ARCVELLUM_API_ORIGIN
$PreviousClientPort = $env:ARCVELLUM_CLIENT_PORT
$ApiProcess = $null

try {
    $env:PYTHONPATH = Join-Path $Repository "src"
    $env:ARCVELLUM_API_ORIGIN = "http://127.0.0.1:$ApiPort"
    $env:ARCVELLUM_CLIENT_PORT = "$ClientPort"

    & $Python (Join-Path $Repository "scripts\verify_checkout_import.py")
    if ($LASTEXITCODE -ne 0) {
        throw "The Python import check did not resolve to this checkout."
    }

    & $Python (Join-Path $Repository "scripts\verify_version_sync.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Public version declarations are not synchronized."
    }

    $ApiLogDirectory = Join-Path $Repository "work\dev-runtime"
    New-Item -ItemType Directory -Path $ApiLogDirectory -Force | Out-Null
    $ApiStdout = Join-Path $ApiLogDirectory "api-$ApiPort.stdout.log"
    $ApiStderr = Join-Path $ApiLogDirectory "api-$ApiPort.stderr.log"
    $ApiProcess = Start-Process `
        -FilePath $Python `
        -ArgumentList @("-m", "literary_engineering_studio", "serve", "--port", "$ApiPort") `
        -WorkingDirectory $Repository `
        -RedirectStandardOutput $ApiStdout `
        -RedirectStandardError $ApiStderr `
        -WindowStyle Hidden `
        -PassThru

    $ExpectedVersion = (Get-Content -LiteralPath $PackageJson -Raw | ConvertFrom-Json).version
    $HealthUri = "http://127.0.0.1:$ApiPort/health"
    $Health = $null
    for ($Attempt = 0; $Attempt -lt 60; $Attempt += 1) {
        if ($ApiProcess.HasExited) {
            $Detail = if (Test-Path -LiteralPath $ApiStderr) {
                (Get-Content -LiteralPath $ApiStderr -Tail 20) -join [Environment]::NewLine
            } else {
                "No API error log was produced."
            }
            throw "The API exited before becoming ready.$([Environment]::NewLine)$Detail"
        }
        try {
            $Health = Invoke-RestMethod -Uri $HealthUri -TimeoutSec 1
            if ($Health.ok) {
                break
            }
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }

    if ($null -eq $Health -or -not $Health.ok) {
        throw "The API did not become healthy at $HealthUri."
    }
    if ($Health.version -ne $ExpectedVersion) {
        throw "Version mismatch: checkout is $ExpectedVersion but API reports $($Health.version)."
    }

    Write-Host "ArcVellum $ExpectedVersion API is ready at $HealthUri"
    Write-Host "Opening the development client at http://127.0.0.1:$ClientPort/ui/"
    & npm run client:dev -- --port $ClientPort
} finally {
    if ($null -ne $ApiProcess -and -not $ApiProcess.HasExited) {
        Stop-Process -Id $ApiProcess.Id -ErrorAction SilentlyContinue
        $ApiProcess.WaitForExit(5000)
    }
    $env:PYTHONPATH = $PreviousPythonPath
    $env:ARCVELLUM_API_ORIGIN = $PreviousApiOrigin
    $env:ARCVELLUM_CLIENT_PORT = $PreviousClientPort
}
