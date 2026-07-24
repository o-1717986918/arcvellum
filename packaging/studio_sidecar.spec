# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPECPATH).parent
datas = collect_data_files("literary_engineering_studio")
datas += collect_data_files("literary_engineering_studio_engine")
hiddenimports = collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("literary_engineering_studio")
hiddenimports += collect_submodules("literary_engineering_studio_engine")

analysis = Analysis(
    [str(ROOT / "packaging" / "studio_sidecar.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="literary-engineering-studio-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # Uvicorn requires valid standard streams during startup.  On Windows the
    # Tauri shell starts this sidecar with CREATE_NO_WINDOW, so retaining the
    # console subsystem keeps Uvicorn reliable without exposing a terminal.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
