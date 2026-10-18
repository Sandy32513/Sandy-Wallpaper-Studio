"""
Sandy Wallpaper Studio - Windows Wallpaper Service
=====================================================
Windows Wallpaper Engine (Section 14, 15, 16):
- Native Windows wallpaper changing via ctypes SystemParametersInfoW & registry
- Multi-monitor awareness & monitor detection via EnumDisplayMonitors
- Selected wallpaper setting with validation & style mapping
- Random wallpaper selection with category/resolution/favorites filters & repeat avoidance
- History tracking & previous wallpaper restoration
- Accurate multi-style wallpaper preview generation (Center, Tile, Stretch, Fit, Fill, Span)
- Non-destructive, graceful fallbacks, and test simulation mode
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import platform
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from PIL import Image

from app.constants import (
    ALL_IMAGE_FORMATS,
    ASPECT_RATIO_TOLERANCE,
    ASPECT_RATIOS,
    RESOLUTION_CLASSES,
    WALLPAPER_STYLES,
)
from app.database.database import Database
from app.database.history_repository import HistoryRepository
from app.database.models import Wallpaper, WallpaperHistory
from app.database.wallpaper_repository import WallpaperRepository

logger = logging.getLogger(__name__)

# Windows API constants
SPI_SETDESKWALLPAPER = 0x0014
SPI_GETDESKWALLPAPER = 0x0073
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

# Registry keys for wallpaper style: (WallpaperStyle, TileWallpaper)
_STYLE_REGISTRY_VALUES: dict[str, tuple[str, str]] = {
    "Center": ("0", "0"),   # WallpaperStyle=0, TileWallpaper=0
    "Tile": ("0", "1"),     # WallpaperStyle=0, TileWallpaper=1
    "Stretch": ("2", "0"),  # WallpaperStyle=2, TileWallpaper=0
    "Fit": ("6", "0"),      # WallpaperStyle=6, TileWallpaper=0
    "Fill": ("10", "0"),    # WallpaperStyle=10, TileWallpaper=0
    "Span": ("22", "0"),    # WallpaperStyle=22, TileWallpaper=0
}


class WallpaperServiceError(Exception):
    """Base exception for wallpaper service errors."""
    pass


class WallpaperNotFoundError(WallpaperServiceError):
    """Raised when an image file or database wallpaper record cannot be found."""
    pass


class WallpaperValidationError(WallpaperServiceError):
    """Raised when an image file fails integrity or decode validation."""
    pass


class MonitorInfo:
    """Information about a connected monitor (Section 15)."""

    def __init__(
        self,
        name: str,
        width: int,
        height: int,
        is_primary: bool,
        left: int = 0,
        top: int = 0,
        device_id: str = "",
    ) -> None:
        self.name = name
        self.width = max(1, width)
        self.height = max(1, height)
        self.is_primary = is_primary
        self.left = left
        self.top = top
        self.device_id = device_id

    @property
    def resolution(self) -> str:
        """Resolution formatted as 'WIDTH×HEIGHT'."""
        return f"{self.width}×{self.height}"

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        """Bounding rectangle (left, top, right, bottom)."""
        return (self.left, self.top, self.left + self.width, self.top + self.height)

    @property
    def orientation(self) -> str:
        """Monitor orientation: 'Landscape' or 'Portrait'."""
        return "Landscape" if self.width >= self.height else "Portrait"

    @property
    def aspect_ratio(self) -> str:
        """Closest standard aspect ratio or fractional string."""
        ratio = self.width / self.height
        for label, val in ASPECT_RATIOS.items():
            if abs(ratio - val) / val <= ASPECT_RATIO_TOLERANCE:
                return label
        return f"{round(ratio, 2)}:1"

    def __repr__(self) -> str:
        primary = " [Primary]" if self.is_primary else ""
        return f"Monitor({self.name}, {self.resolution}{primary}, {self.orientation})"


@dataclass
class WallpaperApplyResult:
    """Structured result of applying a wallpaper."""

    success: bool
    wallpaper_id: Optional[int] = None
    wallpaper: Optional[Wallpaper] = None
    image_path: Optional[Path] = None
    style: str = "Fill"
    monitor: Optional[str] = None
    applied_at: str = ""
    previous_wallpaper_id: Optional[int] = None
    previous_image_path: Optional[Path] = None
    message: str = "Wallpaper applied successfully."
    error: Optional[str] = None


class WindowsWallpaperService:
    """Service for managing and applying desktop wallpapers on Windows.

    Supports:
    - Setting selected wallpapers with style selection
    - Multi-monitor awareness and detection
    - Setting random wallpapers with filters and repeat avoidance
    - Restoring previous wallpaper from history stack
    - Desktop preview generation across all supported styles
    - Test simulation mode for cross-platform validation
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        wallpaper_repo: Optional[WallpaperRepository] = None,
        history_repo: Optional[HistoryRepository] = None,
        simulate: bool = False,
    ) -> None:
        self._is_windows = platform.system() == "Windows"
        self._simulate = simulate or (not self._is_windows)

        self._db = db
        self._wallpaper_repo: WallpaperRepository | None
        if wallpaper_repo is not None:
            self._wallpaper_repo = wallpaper_repo
        elif db is not None:
            self._wallpaper_repo = WallpaperRepository(db)
        else:
            self._wallpaper_repo = None

        self._history_repo: HistoryRepository | None
        if history_repo is not None:
            self._history_repo = history_repo
        elif db is not None:
            self._history_repo = HistoryRepository(db)
        else:
            self._history_repo = None

        # In-memory history stack (paths)
        self._history_stack: list[Path] = []
        self._current_wallpaper_path: Optional[str] = None
        self._current_style: str = "Fill"

        if not self._is_windows and not simulate:
            logger.warning(
                "WindowsWallpaperService: Not running on Windows. Simulation mode enabled."
            )

    @property
    def is_available(self) -> bool:
        """Check if native wallpaper setting is available."""
        return self._is_windows or self._simulate

    @property
    def is_simulated(self) -> bool:
        """Whether the service is running in simulation mode."""
        return self._simulate

    # ------------------------------------------------------------------
    # Image Validation
    # ------------------------------------------------------------------
    def validate_image_file(self, image_path: Path | str) -> Path:
        """Validate that an image exists, has a supported format, and can be decoded."""
        path = Path(image_path).resolve()
        if not path.is_file():
            raise WallpaperNotFoundError(f"Wallpaper image file not found: {path}")

        suffix = path.suffix.lower()
        if suffix not in ALL_IMAGE_FORMATS:
            raise WallpaperValidationError(
                f"Unsupported image format '{suffix}'. Supported: {', '.join(sorted(ALL_IMAGE_FORMATS))}"
            )

        try:
            with Image.open(path) as img:
                img.verify()
        except Exception as exc:
            raise WallpaperValidationError(f"Image decode failed or file is corrupt: {exc}") from exc

        return path

    # ------------------------------------------------------------------
    # Native Setting & Registry
    # ------------------------------------------------------------------
    def set_wallpaper(
        self,
        image_path: Path | str,
        style: str = "Fill",
        monitor: Optional[str] = None,
    ) -> bool:
        """Set the desktop wallpaper directly via Windows API or simulation."""
        path = self.validate_image_file(image_path)

        if style not in WALLPAPER_STYLES:
            logger.warning("Unknown style %r, defaulting to Fill.", style)
            style = "Fill"

        if self._simulate:
            self._current_wallpaper_path = str(path)
            self._current_style = style
            self._history_stack.append(path)
            logger.info("[SIMULATION] Wallpaper set: %s (style=%s)", path.name, style)
            return True

        # Real Windows implementation
        self._set_style_registry(style)

        try:
            result = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
                SPI_SETDESKWALLPAPER,
                0,
                str(path),
                SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
            )
            if not result:
                error_code = ctypes.GetLastError()
                raise WallpaperServiceError(
                    f"SystemParametersInfoW failed with error code: {error_code}"
                )

            self._current_wallpaper_path = str(path)
            self._current_style = style
            self._history_stack.append(path)
            logger.info("Wallpaper set: %s (style=%s, monitor=%s)", path.name, style, monitor or "all")
            return True
        except WallpaperServiceError:
            raise
        except Exception as exc:
            raise WallpaperServiceError(f"Failed to set wallpaper: {exc}") from exc

    def _set_style_registry(self, style: str) -> None:
        """Update wallpaper style registry keys."""
        if self._simulate or not self._is_windows:
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
            logger.debug(
                "Registry updated: WallpaperStyle=%s, TileWallpaper=%s",
                style_val,
                tile_val,
            )
        except Exception as exc:
            logger.warning("Could not set wallpaper style in registry: %s", exc)

    def get_current_wallpaper(self) -> Optional[str]:
        """Get the file path of the currently set wallpaper."""
        if self._simulate:
            return self._current_wallpaper_path

        if not self._is_windows:
            return None

        try:
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
                SPI_GETDESKWALLPAPER,
                len(buf),
                buf,
                0,
            )
            val = buf.value.strip()
            return val if val else self._current_wallpaper_path
        except Exception as exc:
            logger.error("Failed to query current wallpaper: %s", exc)
            return self._current_wallpaper_path

    # ------------------------------------------------------------------
    # Selected Wallpaper Workflow
    # ------------------------------------------------------------------
    def set_selected_wallpaper(
        self,
        wallpaper: Wallpaper | int | Path | str,
        style: str = "Fill",
        monitor: Optional[str] = None,
        source: str = "manual",
    ) -> WallpaperApplyResult:
        """Apply a selected wallpaper, update database usage, and record history."""
        resolved_wallpaper: Optional[Wallpaper] = None
        image_path: Optional[Path] = None

        if isinstance(wallpaper, Wallpaper):
            resolved_wallpaper = wallpaper
            image_path = Path(wallpaper.path)
        elif isinstance(wallpaper, int):
            if self._wallpaper_repo is None:
                raise WallpaperServiceError("Cannot resolve wallpaper by ID without WallpaperRepository.")
            resolved_wallpaper = self._wallpaper_repo.get_by_id(wallpaper)
            if resolved_wallpaper is None:
                raise WallpaperNotFoundError(f"Wallpaper with ID {wallpaper} not found in database.")
            image_path = Path(resolved_wallpaper.path)
        else:
            image_path = Path(wallpaper)
            if self._wallpaper_repo is not None:
                resolved_wallpaper = self._wallpaper_repo.get_by_path(str(image_path))

        # Check prior wallpaper before switching
        prev_image_path: Optional[Path] = None
        prev_wallpaper_id: Optional[int] = None
        if self._history_repo is not None:
            latest_history = self._history_repo.get_latest(monitor=monitor)
            if latest_history:
                prev_wallpaper_id = latest_history.wallpaper_id
                if self._wallpaper_repo:
                    prev_wp = self._wallpaper_repo.get_by_id(latest_history.wallpaper_id)
                    if prev_wp:
                        prev_image_path = Path(prev_wp.path)
        if prev_image_path is None and self._current_wallpaper_path:
            prev_image_path = Path(self._current_wallpaper_path)

        # Apply wallpaper
        self.set_wallpaper(image_path, style=style, monitor=monitor)
        now_iso = datetime.now(UTC).isoformat()

        # Update database metadata & history
        wp_id: Optional[int] = None
        if resolved_wallpaper is not None and resolved_wallpaper.id is not None:
            wp_id = resolved_wallpaper.id
            if self._wallpaper_repo:
                self._wallpaper_repo.record_usage(wp_id, now_iso)
                resolved_wallpaper.last_used = now_iso
                resolved_wallpaper.usage_count += 1
            if self._history_repo:
                self._history_repo.add(
                    WallpaperHistory(
                        wallpaper_id=wp_id,
                        set_at=now_iso,
                        monitor=monitor or "",
                        source=source,
                    )
                )

        return WallpaperApplyResult(
            success=True,
            wallpaper_id=wp_id,
            wallpaper=resolved_wallpaper,
            image_path=image_path,
            style=style,
            monitor=monitor,
            applied_at=now_iso,
            previous_wallpaper_id=prev_wallpaper_id,
            previous_image_path=prev_image_path,
            message="Wallpaper applied successfully.",
        )

    # ------------------------------------------------------------------
    # Random Wallpaper
    # ------------------------------------------------------------------
    def set_random_wallpaper(
        self,
        category: Optional[str] = None,
        favorites_only: bool = False,
        min_resolution: Optional[str] = None,
        style: str = "Fill",
        monitor: Optional[str] = None,
        prevent_repeat: bool = True,
        exclude_ids: Optional[Sequence[int]] = None,
    ) -> WallpaperApplyResult:
        """Pick a random wallpaper matching optional criteria and apply it."""
        if self._wallpaper_repo is None:
            raise WallpaperServiceError("Cannot set random wallpaper without WallpaperRepository.")

        # Determine dimension requirements if min_resolution is provided
        min_w, min_h = 0, 0
        if min_resolution and min_resolution in RESOLUTION_CLASSES:
            min_w = RESOLUTION_CLASSES[min_resolution]["min_width"]
            min_h = RESOLUTION_CLASSES[min_resolution]["min_height"]

        # Fetch candidate wallpapers using repository search
        wallpapers = self._wallpaper_repo.search(
            query="",
            category=category,
            favorites_only=favorites_only,
            min_width=min_w if min_w > 0 else None,
            min_height=min_h if min_h > 0 else None,
            limit=1000,
        )

        excluded: set[int] = set(exclude_ids or [])
        if prevent_repeat and self._history_repo:
            latest = self._history_repo.get_latest(monitor=monitor)
            if latest:
                excluded.add(latest.wallpaper_id)

        candidates: list[Wallpaper] = [
            wp for wp in wallpapers
            if wp.id is not None and wp.id not in excluded
        ]

        # Fallback if exclusion removed all candidates
        if not candidates and excluded and wallpapers:
            candidates = [wp for wp in wallpapers if wp.id is not None]

        if not candidates:
            return WallpaperApplyResult(
                success=False,
                error="NO_CANDIDATES",
                message="No eligible wallpapers found matching the specified criteria.",
            )

        chosen = random.choice(candidates)
        return self.set_selected_wallpaper(chosen, style=style, monitor=monitor)

    # ------------------------------------------------------------------
    # Restore Previous Wallpaper
    # ------------------------------------------------------------------
    def restore_previous_wallpaper(
        self,
        monitor: Optional[str] = None,
    ) -> WallpaperApplyResult:
        """Restore the wallpaper that was active prior to the current one."""
        target_wp: Optional[Wallpaper] = None
        target_path: Optional[Path] = None

        if self._history_repo is not None and self._wallpaper_repo is not None:
            latest = self._history_repo.get_latest(monitor=monitor)
            current_id = latest.wallpaper_id if latest else None
            prev_record = self._history_repo.get_previous(
                monitor=monitor,
                exclude_wallpaper_id=current_id,
            )
            if prev_record:
                target_wp = self._wallpaper_repo.get_by_id(prev_record.wallpaper_id)
                if target_wp:
                    target_path = Path(target_wp.path)

        if target_path is None or not target_path.exists():
            # Fallback to in-memory history stack
            if len(self._history_stack) >= 2:
                # Remove current top
                self._history_stack.pop()
                target_path = self._history_stack[-1]
            elif self._history_stack:
                target_path = self._history_stack[0]

        if target_path is None or not target_path.exists():
            return WallpaperApplyResult(
                success=False,
                error="NO_PREVIOUS_WALLPAPER",
                message="No valid previous wallpaper found in history to restore.",
            )

        to_apply = target_wp if target_wp is not None else target_path
        return self.set_selected_wallpaper(
            to_apply,
            style=self._current_style,
            monitor=monitor,
        )

    # ------------------------------------------------------------------
    # Wallpaper Preview
    # ------------------------------------------------------------------
    def preview_wallpaper(
        self,
        image_path: Path | str,
        target_width: int = 1920,
        target_height: int = 1080,
        style: str = "Fill",
        background_color: tuple[int, int, int] = (0, 0, 0),
    ) -> Image.Image:
        """Generate a simulated desktop preview matching the given display resolution and style."""
        path = self.validate_image_file(image_path)
        tw = max(1, target_width)
        th = max(1, target_height)

        if style not in WALLPAPER_STYLES:
            style = "Fill"

        with Image.open(path) as raw_img:
            img = raw_img.convert("RGB")

        iw, ih = img.size
        canvas = Image.new("RGB", (tw, th), background_color)

        if style == "Stretch":
            return img.resize((tw, th), Image.Resampling.LANCZOS)

        elif style == "Fit":
            scale = min(tw / iw, th / ih)
            nw = max(1, int(iw * scale))
            nh = max(1, int(ih * scale))
            resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
            x = (tw - nw) // 2
            y = (th - nh) // 2
            canvas.paste(resized, (x, y))
            return canvas

        elif style == "Fill" or style == "Span":
            scale = max(tw / iw, th / ih)
            nw = max(1, int(iw * scale))
            nh = max(1, int(ih * scale))
            resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
            left = (nw - tw) // 2
            top = (nh - th) // 2
            return resized.crop((left, top, left + tw, top + th))

        elif style == "Center":
            if iw <= tw and ih <= th:
                x = (tw - iw) // 2
                y = (th - ih) // 2
                canvas.paste(img, (x, y))
                return canvas
            else:
                left = max(0, (iw - tw) // 2)
                top = max(0, (ih - th) // 2)
                cropped = img.crop((left, top, min(iw, left + tw), min(ih, top + th)))
                x = max(0, (tw - cropped.width) // 2)
                y = max(0, (th - cropped.height) // 2)
                canvas.paste(cropped, (x, y))
                return canvas

        elif style == "Tile":
            for x in range(0, tw, iw):
                for y in range(0, th, ih):
                    canvas.paste(img, (x, y))
            return canvas

        return canvas

    def save_preview(
        self,
        image_path: Path | str,
        output_path: Path | str,
        target_width: int = 1920,
        target_height: int = 1080,
        style: str = "Fill",
    ) -> Path:
        """Render a wallpaper preview and save it to a target file path."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        preview_img = self.preview_wallpaper(
            image_path=image_path,
            target_width=target_width,
            target_height=target_height,
            style=style,
        )
        preview_img.save(out, format="JPEG", quality=85)
        return out

    # ------------------------------------------------------------------
    # Multi-Monitor Detection
    # ------------------------------------------------------------------
    def detect_monitors(self) -> list[MonitorInfo]:
        """Detect connected monitors using the Windows API (Section 15)."""
        monitors: list[MonitorInfo] = []

        if not self._is_windows or self._simulate:
            # Fallback / simulated monitor
            monitors.append(
                MonitorInfo(
                    name="Primary Display",
                    width=1920,
                    height=1080,
                    is_primary=True,
                    left=0,
                    top=0,
                    device_id="DISPLAY1",
                )
            )
            return monitors

        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]

            def _monitor_callback(hMonitor, hdcMonitor, lprcMonitor, dwData):  # noqa: ANN001, N802, N803
                rect = lprcMonitor.contents
                left = rect.left
                top = rect.top
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                is_primary = (left == 0 and top == 0)
                name = f"Monitor {len(monitors) + 1}"
                device_id = f"DISPLAY{len(monitors) + 1}"
                monitors.append(
                    MonitorInfo(
                        name=name,
                        width=width,
                        height=height,
                        is_primary=is_primary,
                        left=left,
                        top=top,
                        device_id=device_id,
                    )
                )
                return 1

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
            try:
                user32 = ctypes.windll.user32  # type: ignore[attr-defined]
                w = user32.GetSystemMetrics(0)
                h = user32.GetSystemMetrics(1)
                monitors.append(MonitorInfo("Primary", w, h, True))
            except Exception:
                monitors.append(MonitorInfo("Primary", 1920, 1080, True))

        return monitors

    def get_primary_monitor(self) -> Optional[MonitorInfo]:
        """Get the primary monitor information."""
        monitors = self.detect_monitors()
        for mon in monitors:
            if mon.is_primary:
                return mon
        return monitors[0] if monitors else None

    # ------------------------------------------------------------------
    # History Inspection
    # ------------------------------------------------------------------
    def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        monitor: Optional[str] = None,
    ) -> list[WallpaperHistory]:
        """Fetch history records if history repository is available."""
        if self._history_repo is None:
            return []
        return self._history_repo.get_recent(limit=limit, offset=offset, monitor=monitor)
