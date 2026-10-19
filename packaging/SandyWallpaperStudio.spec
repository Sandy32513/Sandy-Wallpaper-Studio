"""PyInstaller onedir spec for the Sandy Wallpaper Studio GUI."""

import os
from pathlib import Path

project_root = Path(SPECPATH).resolve().parent
version_info = Path(os.environ.get("SWS_VERSION_FILE", "")).resolve()
if not version_info.is_file():
    raise RuntimeError("Build scripts must provide SWS_VERSION_FILE with generated version metadata.")

analysis = Analysis(
    [str(project_root / "app" / "__main__.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff", "mypy", "pip_audit", "PyInstaller"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="SandyWallpaperStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="NONE",
    version=str(version_info),
)
bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="SandyWallpaperStudio",
)
