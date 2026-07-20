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

function Assert-BundleTargetsAvailable {
    $BundleDir = Join-Path $TauriRoot "target\release\bundle\nsis"
    if (-not (Test-Path -LiteralPath $BundleDir)) { return }
    Get-ChildItem -LiteralPath $BundleDir -Filter "ArcVellum_*-setup.exe*" -File | ForEach-Object {
        try {
            $Stream = [System.IO.File]::Open($_.FullName, 'Open', 'ReadWrite', 'None')
            $Stream.Dispose()
        } catch {
            throw "Release bundle is in use: $($_.FullName). Close the installer or signing process, then retry."
        }
    }
}

function Assert-FileTargetAvailable([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    try {
        $Stream = [System.IO.File]::Open($Path, 'Open', 'ReadWrite', 'None')
        $Stream.Dispose()
    } catch {
        throw "$Label is in use: $Path. Close the running ArcVellum smoke-test or build process, then retry."
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

    cmd /c npm run client:build
    Assert-NativeSuccess "Vue client production build"

    Assert-FileTargetAvailable $SidecarSource "Frozen Python sidecar"
    Assert-FileTargetAvailable $SidecarTarget "Tauri Python sidecar"
    python -m PyInstaller --noconfirm --clean (Join-Path $Root "packaging\studio_sidecar.spec")
    Assert-NativeSuccess "Python sidecar build"
    New-Item -ItemType Directory -Force -Path $BinaryDir, $ResourceDir | Out-Null
    Copy-Item -Force -LiteralPath $SidecarSource -Destination $SidecarTarget
    Copy-Item -Force -LiteralPath $OpenCodeSource -Destination (Join-Path $ResourceDir "opencode.exe")
    Copy-Item -Force -LiteralPath (Join-Path $Root "src\literary_engineering_studio\vendor\OPENCODE-NOTICE.md") -Destination (Join-Path $ResourceDir "OPENCODE-NOTICE.md")
    Copy-Item -Force -LiteralPath (Join-Path $Root "src\literary_engineering_studio\vendor\OPENCODE-LICENSE.txt") -Destination (Join-Path $ResourceDir "OPENCODE-LICENSE.txt")

    cmd /c npm run desktop:icons
    Assert-NativeSuccess "Desktop icon generation"
    if (-not $env:TAURI_SIGNING_PRIVATE_KEY) {
        $LocalKey = Join-Path $HOME ".tauri\arcvellum.key"
        $LocalPassword = Join-Path $HOME ".tauri\arcvellum.key.password.dpapi"
        if (-not (Test-Path -LiteralPath $LocalKey) -or -not (Test-Path -LiteralPath $LocalPassword)) {
            throw "Signed updater key is missing. Configure TAURI_SIGNING_PRIVATE_KEY or initialize the local ArcVellum release key."
        }
        # Tauri v2 expects the private-key payload, not a path to the key file.
        # Keep the secret in this child process environment only and never print it.
        $env:TAURI_SIGNING_PRIVATE_KEY = Get-Content -LiteralPath $LocalKey -Raw
        $SecurePassword = Get-Content -LiteralPath $LocalPassword | ConvertTo-SecureString
        $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = [System.Net.NetworkCredential]::new("", $SecurePassword).Password
    }
    $env:PATH = "$HOME\.cargo\bin;$env:PATH"
    Assert-BundleTargetsAvailable
    cmd /c npm run desktop:build
    Assert-NativeSuccess "Tauri desktop build"
    $StudioVersion = python -c "from literary_engineering_studio import __version__; print(__version__)"
    Assert-NativeSuccess "Read Studio version"
    python (Join-Path $Root "packaging\build_update_manifest.py") `
        --bundle-dir (Join-Path $TauriRoot "target\release\bundle") `
        --output-dir (Join-Path $Root "dist\release") `
        --version $StudioVersion.Trim() `
        --base-url "https://github.com/o-1717986918/arcvellum/releases/latest/download" `
        --notes "ArcVellum Reader, Advisor and Narrative Observatory release."
    Assert-NativeSuccess "Signed updater manifest"
} finally {
    Pop-Location
}
