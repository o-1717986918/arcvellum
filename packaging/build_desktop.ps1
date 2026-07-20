param(
    [switch]$SkipPythonInstall,
    [switch]$SkipNodeInstall
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TargetTriple = "x86_64-pc-windows-msvc"
$TauriRoot = Join-Path $Root "desktop\src-tauri"
$BinaryDir = Join-Path $TauriRoot "binaries"
$ResourceDir = Join-Path $TauriRoot "resources"
$SidecarSource = Join-Path $Root "dist\literary-engineering-studio-sidecar.exe"
$SidecarTarget = Join-Path $BinaryDir "literary-engineering-studio-sidecar-$TargetTriple.exe"
$OpenCodeSource = Join-Path $Root "build\vendor\opencode-v1.18.3\expanded\opencode.exe"

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

Push-Location $Root
try {
    if (-not $SkipPythonInstall) {
        python -m pip install -e ".[api,test]"
        Assert-NativeSuccess "Studio dependency installation"
        python -m pip install "pyinstaller==6.21.0"
        Assert-NativeSuccess "PyInstaller installation"
    }
    if (-not $SkipNodeInstall -or -not (Test-Path (Join-Path $Root "node_modules"))) {
        cmd /c npm install
        Assert-NativeSuccess "Node dependency installation"
    }
    if (-not (Test-Path $OpenCodeSource)) {
        python -m literary_engineering_studio opencode-install --destination (Split-Path $OpenCodeSource)
        Assert-NativeSuccess "OpenCode installation"
    }

    python -m PyInstaller --noconfirm --clean (Join-Path $Root "packaging\studio_sidecar.spec")
    Assert-NativeSuccess "Python sidecar build"
    New-Item -ItemType Directory -Force -Path $BinaryDir, $ResourceDir | Out-Null
    Copy-Item -Force -LiteralPath $SidecarSource -Destination $SidecarTarget
    Copy-Item -Force -LiteralPath $OpenCodeSource -Destination (Join-Path $ResourceDir "opencode.exe")
    Copy-Item -Force -LiteralPath (Join-Path $Root "src\literary_engineering_studio\vendor\OPENCODE-NOTICE.md") -Destination (Join-Path $ResourceDir "OPENCODE-NOTICE.md")
    Copy-Item -Force -LiteralPath (Join-Path $Root "src\literary_engineering_studio\vendor\OPENCODE-LICENSE.txt") -Destination (Join-Path $ResourceDir "OPENCODE-LICENSE.txt")

    cmd /c npm run desktop:icons
    Assert-NativeSuccess "Desktop icon generation"
    $env:PATH = "$HOME\.cargo\bin;$env:PATH"
    cmd /c npm run desktop:build
    Assert-NativeSuccess "Tauri desktop build"
} finally {
    Pop-Location
}
