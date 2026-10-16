"""
Sandy Wallpaper Studio - Windows Wallpaper Service
=====================================================
Native Windows wallpaper changing via ctypes (Section 14).
Does NOT require administrator privileges.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.constants import WALLPAPER_STYLES

logger = logging.getLogger(__name__)

# Windows API constants
SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

# Registry keys for wallpaper style
_STYLE_REGISTRY_VALUES = {
    "Center": ("0", "0"),   # WallpaperStyle=0, TileWallpaper=0
    "Tile": ("0", "1"),     # WallpaperStyle=0, TileWallpaper=1
    "Stretch": ("2", "0"),  # WallpaperStyle=2, TileWallpaper=0
    "Fit": ("6", "0"),      # WallpaperStyle=6, TileWallpaper=0
    "Fill": ("10", "0"),    # WallpaperStyle=10, TileWallpaper=0
}


class WallpaperServiceError(Exception):
    """Raised when a wallpaper operation fails."""
    pass


class MonitorInfo:
    """Information about a connected monitor."""

    def __init__(
        self,
        name: str,
        width: int,
        height: int,
        is_primary: bool,
        left: int = 0,
        top: int = 0,
    ) -> None:
        self.name = name
        self.width = width
        self.height = height
        self.is_primary = is_primary
        self.left = left
        self.top = top

    @property
    def resolution(self) -> str:
        return f"{self.width}×{self.height}"

    def __repr__(self) -> str:
        primary = " [Primary]" if self.is_primary else ""
        return f"Monitor({self.name}, {self.resolution}{primary})"


class WindowsWallpaperService:
    """Service for setting the Windows desktop wallpaper.

    Uses ctypes to call SystemParametersInfoW (no admin required).
    Multi-monitor detection via EnumDisplayMonitors.
    """

    def __init__(self) -> None:
        self._is_windows = platform.system() == "Windows"
        if not self._is_windows:
            logger.warning("WindowsWallpaperService: Not running on Windows.")

    @property
    def is_available(self) -> bool:
        """Check if wallpaper setting is available."""
        return self._is_windows

    def set_wallpaper(
        self,
        image_path: Path,
        style: str = "Fill",
    ) -> bool:
        """Set the desktop wallpaper.

        Args:
            image_path: Path to the image file (must be BMP, JPG, or PNG).
            style: One of "Center", "Tile", "Stretch", "Fit", "Fill".

        Returns:
            True if successful.

        Raises:
            WallpaperServiceError: On failure.
        """
        if not self._is_windows:
            raise WallpaperServiceError("Wallpaper setting is only available on Windows.")

        path = Path(image_path).resolve()
        if not path.exists():
            raise WallpaperServiceError(f"Image file not found: {path}")

        if style not in WALLPAPER_STYLES:
            logger.warning("Unknown style %r, defaulting to Fill.", style)
            style = "Fill"

        # Set the wallpaper style in the registry
        self._set_style_registry(style)

        # Call SystemParametersInfoW to set the wallpaper
        try:
            result = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
                SPI_SETDESKWALLPAPER,
                0,
                str(path),
                SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
            )
            if result:
                logger.info("Wallpaper set: %s (style=%s)", path.name, style)
                return True
            else:
                error_code = ctypes.GetLastError()
                raise WallpaperServiceError(
                    f"SystemParametersInfoW failed (error code: {error_code})"
                )
        except WallpaperServiceError:
            raise
        except Exception as exc:
            raise WallpaperServiceError(f"Failed to set wallpaper: {exc}") from exc

    def _set_style_registry(self, style: str) -> None:
        """Set the wallpaper style and tile values in the registry."""
        if not self._is_windows:
            return

        try:
            import winreg

            style_val, tile_val = _STYLE_REGISTRY_VALUES.get(style, ("10", "0"))
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Control Panel\Desktop",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, style_val)
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile_val)
            winreg.CloseKey(key)
            logger.debug("Registry updated: WallpaperStyle=%s, TileWallpaper=%s", style_val, tile_val)
        except Exception as exc:
            logger.warning("Could not set wallpaper style in registry: %s", exc)
            # Non-fatal: the wallpaper will still be set, just with the current style

    def get_current_wallpaper(self) -> Optional[str]:
        """Get the path of the currently set wallpaper."""
        if not self._is_windows:
            return None

        try:
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
                0x0073,  # SPI_GETDESKWALLPAPER
                len(buf),
                buf,
                0,
            )
            return buf.value if buf.value else None
        except Exception as exc:
            logger.error("Failed to get current wallpaper: %s", exc)
            return None

    def detect_monitors(self) -> list[MonitorInfo]:
        """Detect connected monitors using the Windows API (Section 15).

        Returns:
            List of MonitorInfo objects.
        """
        if not self._is_windows:
            return []

        monitors: list[MonitorInfo] = []

        try:
            # Use EnumDisplayMonitors
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]

            # Get virtual screen info for primary detection
            SM_CXSCREEN = 0
            SM_CYSCREEN = 1
            primary_w = user32.GetSystemMetrics(SM_CXSCREEN)
            primary_h = user32.GetSystemMetrics(SM_CYSCREEN)

            def _monitor_callback(hMonitor, hdcMonitor, lprcMonitor, dwData):  # noqa: ANN001, N802
                rect = lprcMonitor.contents
                left = rect.left
                top = rect.top
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                is_primary = (left == 0 and top == 0)
                name = f"Monitor {len(monitors) + 1}"
                monitors.append(MonitorInfo(
                    name=name,
                    width=width,
                    height=height,
                    is_primary=is_primary,
                    left=left,
                    top=top,
                ))
                return 1  # Continue enumeration

            MonitorEnumProc = ctypes.WINFUNCTYPE(  # noqa: N806
                ctypes.c_int,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.wintypes.RECT),
                ctypes.c_double,
            )
            callback = MonitorEnumProc(_monitor_callback)
            user32.EnumDisplayMonitors(None, None, callback, 0)

            logger.info("Detected %d monitor(s).", len(monitors))

        except Exception as exc:
            logger.error("Monitor detection failed: %s", exc)
            # Fallback: return a single "primary" monitor with screen metrics
            try:
                user32 = ctypes.windll.user32  # type: ignore[attr-defined]
                w = user32.GetSystemMetrics(0)
                h = user32.GetSystemMetrics(1)
                monitors.append(MonitorInfo("Primary", w, h, True))
            except Exception:
                pass

        return monitors
