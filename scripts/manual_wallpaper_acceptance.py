"""Opt-in test of the real Windows desktop wallpaper boundary.

This script is intentionally not part of CI. It changes the active desktop after
the operator types an explicit confirmation, then restores the captured wallpaper.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import tempfile
import winreg
from datetime import datetime
from pathlib import Path

from PIL import Image

from app.services.wallpaper_service import (
    _STYLE_REGISTRY_VALUES,
    SPI_GETDESKWALLPAPER,
    SPI_SETDESKWALLPAPER,
    SPIF_SENDCHANGE,
    SPIF_UPDATEINIFILE,
    WindowsWallpaperService,
)

REGISTRY_PATH = r"Control Panel\Desktop"
REGISTRY_NAMES = ("Wallpaper", "WallpaperStyle", "TileWallpaper")
CONFIRMATION = "APPLY TEST WALLPAPER TO MY DESKTOP"


def _read_registry_state() -> dict[str, tuple[object, int] | None]:
    state: dict[str, tuple[object, int] | None] = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ) as key:
        for name in REGISTRY_NAMES:
            try:
                value, value_type = winreg.QueryValueEx(key, name)
                state[name] = (value, value_type)
            except FileNotFoundError:
                state[name] = None
    return state


def _restore_registry_state(state: dict[str, tuple[object, int] | None]) -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        REGISTRY_PATH,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        for name, value_state in state.items():
            if value_state is None:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
            else:
                value, value_type = value_state
                winreg.SetValueEx(key, name, 0, value_type, value)


def _read_native_wallpaper_path() -> str:
    buffer = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
        SPI_GETDESKWALLPAPER,
        len(buffer),
        buffer,
        0,
    )
    if not result or not buffer.value.strip():
        raise RuntimeError("Windows could not report the current desktop wallpaper path.")
    return buffer.value.strip()


def _write_native_wallpaper_path(path: str) -> None:
    ctypes.set_last_error(0)
    result = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
        SPI_SETDESKWALLPAPER,
        0,
        path,
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
    )
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())


def _style_from_registry(state: dict[str, tuple[object, int] | None]) -> str:
    style = state.get("WallpaperStyle")
    tile = state.get("TileWallpaper")
    if style is not None and tile is not None:
        pair = (str(style[0]), str(tile[0]))
        for name, registry_pair in _STYLE_REGISTRY_VALUES.items():
            if registry_pair == pair:
                return name
    return "Fill"


def main() -> int:
    if sys.platform != "win32":
        print("This integration test is available only on Windows.", file=sys.stderr)
        return 2

    report_root = Path(tempfile.mkdtemp(prefix="sws-wallpaper-acceptance-"))
    log_path = report_root / f"wallpaper-acceptance-{datetime.now():%Y%m%d-%H%M%S}.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
    )
    logger = logging.getLogger("sws.manual_wallpaper_acceptance")
    image_path = report_root / "temporary-test-wallpaper.png"
    original_path = ""
    registry_state: dict[str, tuple[object, int] | None] | None = None
    apply_attempted = False
    failure: Exception | None = None
    restore_failure: Exception | None = None

    try:
        original_path = _read_native_wallpaper_path()
        original_file = Path(original_path)
        if not original_file.is_file():
            raise RuntimeError("The active wallpaper path is not a readable file; refusing to change it.")
        registry_state = _read_registry_state()
        original_style = _style_from_registry(registry_state)
        Image.new("RGB", (1920, 1080), (32, 72, 112)).save(image_path, format="PNG")

        print("This test changes the wallpaper on the active Windows desktop for a short time.")
        print("It records the current image path and style values, uses a generated test image,")
        print("and restores the recorded settings in a finally block. Per-monitor layouts may vary.")
        approval = input(f"Type exactly '{CONFIRMATION}' to continue: ")
        if approval != CONFIRMATION:
            logger.info("Operator declined or did not provide the required confirmation.")
            print("No wallpaper change was made.")
            return 1

        logger.info("Captured current wallpaper path and registry style state (%s).", original_style)
        logger.info("Applying generated temporary image with style %s.", "Fill")
        apply_attempted = True
        service = WindowsWallpaperService(simulate=False)
        if not service.set_wallpaper(image_path, style="Fill"):
            raise RuntimeError("WindowsWallpaperService returned false for the test image.")
        logger.info("SystemParametersInfoW accepted the generated test image.")
        print("The test wallpaper is active. Inspect it, then press Enter to restore the original.")
        input()
    except KeyboardInterrupt as exc:
        failure = exc
        logger.warning("Operator interrupted the test; restoration will run.")
    except Exception as exc:
        failure = exc
        logger.exception("Wallpaper integration test failed; restoration will run if needed.")
    finally:
        if apply_attempted and original_path and registry_state is not None:
            try:
                _restore_registry_state(registry_state)
                _write_native_wallpaper_path(original_path)
                restored = _read_native_wallpaper_path()
                if os.path.normcase(os.path.abspath(restored)) != os.path.normcase(os.path.abspath(original_path)):
                    raise RuntimeError("Windows did not report the original wallpaper after restoration.")
                if _read_registry_state() != registry_state:
                    raise RuntimeError("Windows wallpaper style registry values did not restore exactly.")
                logger.info("Restored original wallpaper path and captured registry style values.")
            except Exception as exc:
                restore_failure = exc
                logger.exception("Restoring the original wallpaper or style values failed.")
        if restore_failure is None:
            try:
                image_path.unlink(missing_ok=True)
                logger.info("Removed only the generated temporary wallpaper image.")
            except OSError:
                logger.exception("Could not remove the generated temporary image.")
        else:
            logger.critical("Preserved the generated image at %s so it can be restored manually.", image_path)

    print(f"Local diagnostic log: {log_path}")
    if restore_failure is not None:
        print("ERROR: Restore the original wallpaper manually from Windows Settings.", file=sys.stderr)
        return 2
    if failure is not None:
        print(f"The native integration test failed: {type(failure).__name__}.", file=sys.stderr)
        return 1
    print("The original wallpaper and captured style values were restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
