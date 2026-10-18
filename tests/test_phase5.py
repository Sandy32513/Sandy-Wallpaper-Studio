"""
Sandy Wallpaper Studio — Phase 5 Tests
=========================================
Tests for Windows Wallpaper Engine:
- Native Windows wallpaper setting & simulation mode
- Monitor detection & Multi-monitor awareness (Section 15)
- Selected wallpaper setting with database update & history recording (Section 14)
- Random wallpaper selection with category/favorite/resolution filters & repeat avoidance (Section 16)
- Previous wallpaper restoration from history
- Wallpaper preview generation across all styles (Center, Tile, Stretch, Fit, Fill, Span)
- HistoryRepository CRUD & cascade operations
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest
from PIL import Image

from app.constants import WALLPAPER_STYLES
from app.database.database import Database
from app.database.history_repository import HistoryRepository
from app.database.models import Wallpaper, WallpaperHistory
from app.database.wallpaper_repository import WallpaperRepository
from app.services.wallpaper_service import (
    MonitorInfo,
    WallpaperApplyResult,
    WallpaperNotFoundError,
    WallpaperServiceError,
    WallpaperValidationError,
    WindowsWallpaperService,
)


# ============================================================
# Helpers & Fixtures
# ============================================================

def _create_test_image(
    path: Path,
    width: int = 1920,
    height: int = 1080,
    color: tuple[int, int, int] = (100, 150, 200),
) -> Path:
    """Helper to create a solid RGB test image."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color)
    img.save(path, format="JPEG", quality=90)
    return path


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a fresh temporary database."""
    db_path = tmp_path / "test_engine.db"
    database = Database(db_path)
    database.connect()
    yield database
    database.close()


@pytest.fixture
def wallpaper_repo(db: Database) -> WallpaperRepository:
    return WallpaperRepository(db)


@pytest.fixture
def history_repo(db: Database) -> HistoryRepository:
    return HistoryRepository(db)


@pytest.fixture
def engine(db: Database, wallpaper_repo: WallpaperRepository, history_repo: HistoryRepository) -> WindowsWallpaperService:
    """WindowsWallpaperService initialized in simulated mode for reliable testing."""
    return WindowsWallpaperService(
        db=db,
        wallpaper_repo=wallpaper_repo,
        history_repo=history_repo,
        simulate=True,
    )


# ============================================================
# Monitor Detection & MonitorInfo Tests
# ============================================================

class TestMonitorInfo:
    def test_landscape_monitor(self) -> None:
        mon = MonitorInfo(
            name="Primary Display",
            width=3840,
            height=2160,
            is_primary=True,
            left=0,
            top=0,
            device_id="DISPLAY1",
        )
        assert mon.resolution == "3840×2160"
        assert mon.orientation == "Landscape"
        assert mon.aspect_ratio == "16:9"
        assert mon.bounds == (0, 0, 3840, 2160)
        assert mon.is_primary is True
        assert "Primary" in repr(mon)

    def test_portrait_monitor(self) -> None:
        mon = MonitorInfo(
            name="Secondary Display",
            width=1080,
            height=1920,
            is_primary=False,
            left=3840,
            top=0,
            device_id="DISPLAY2",
        )
        assert mon.resolution == "1080×1920"
        assert mon.orientation == "Portrait"
        assert mon.bounds == (3840, 0, 4920, 1920)
        assert mon.is_primary is False
        assert "[Primary]" not in repr(mon)

    def test_ultrawide_monitor(self) -> None:
        mon = MonitorInfo(
            name="Ultrawide",
            width=3440,
            height=1440,
            is_primary=True,
        )
        assert mon.aspect_ratio == "21:9"
        assert mon.orientation == "Landscape"


class TestMonitorDetection:
    def test_detect_monitors(self, engine: WindowsWallpaperService) -> None:
        monitors = engine.detect_monitors()
        assert len(monitors) >= 1
        for mon in monitors:
            assert mon.width > 0
            assert mon.height > 0
            assert mon.name != ""

    def test_get_primary_monitor(self, engine: WindowsWallpaperService) -> None:
        primary = engine.get_primary_monitor()
        assert primary is not None
        assert primary.width > 0
        assert primary.height > 0


# ============================================================
# Validation Tests
# ============================================================

class TestWallpaperValidation:
    def test_nonexistent_file_raises_not_found(self, engine: WindowsWallpaperService, tmp_path: Path) -> None:
        fake_path = tmp_path / "does_not_exist.jpg"
        with pytest.raises(WallpaperNotFoundError, match="not found"):
            engine.validate_image_file(fake_path)

    def test_unsupported_format_raises_validation_error(self, engine: WindowsWallpaperService, tmp_path: Path) -> None:
        bad_file = tmp_path / "script.py"
        bad_file.write_text("print('hello')", encoding="utf-8")
        with pytest.raises(WallpaperValidationError, match="Unsupported image format"):
            engine.validate_image_file(bad_file)

    def test_corrupt_image_raises_validation_error(self, engine: WindowsWallpaperService, tmp_path: Path) -> None:
        corrupt_jpg = tmp_path / "corrupt.jpg"
        corrupt_jpg.write_text("This is not a real JPEG file content.", encoding="utf-8")
        with pytest.raises(WallpaperValidationError, match="decode failed"):
            engine.validate_image_file(corrupt_jpg)

    def test_valid_image_passes_validation(self, engine: WindowsWallpaperService, tmp_path: Path) -> None:
        img_path = _create_test_image(tmp_path / "valid.jpg")
        resolved = engine.validate_image_file(img_path)
        assert resolved == img_path.resolve()


# ============================================================
# Set Wallpaper Direct / Low-Level
# ============================================================

class TestSetWallpaperDirect:
    def test_set_wallpaper_simulated(self, engine: WindowsWallpaperService, tmp_path: Path) -> None:
        img = _create_test_image(tmp_path / "wall.jpg")
        success = engine.set_wallpaper(img, style="Fill")
        assert success is True
        assert engine.get_current_wallpaper() == str(img.resolve())

    def test_set_wallpaper_all_supported_styles(self, engine: WindowsWallpaperService, tmp_path: Path) -> None:
        img = _create_test_image(tmp_path / "wall.jpg")
        for style in WALLPAPER_STYLES:
            assert engine.set_wallpaper(img, style=style) is True

    def test_unknown_style_defaults_to_fill(self, engine: WindowsWallpaperService, tmp_path: Path) -> None:
        img = _create_test_image(tmp_path / "wall.jpg")
        assert engine.set_wallpaper(img, style="NonExistentStyle") is True
        assert engine._current_style == "Fill"


# ============================================================
# Set Selected Wallpaper Workflow
# ============================================================

class TestSetSelectedWallpaper:
    def test_apply_by_wallpaper_dataclass(
        self,
        engine: WindowsWallpaperService,
        wallpaper_repo: WallpaperRepository,
        history_repo: HistoryRepository,
        tmp_path: Path,
    ) -> None:
        img = _create_test_image(tmp_path / "img1.jpg")
        wp = Wallpaper(
            filename="img1.jpg",
            path=str(img.resolve()),
            title="Alpine Sunrise",
            category="Mountains",
            width=3840,
            height=2160,
            resolution_class="4K",
        )
        wp_id = wallpaper_repo.add(wp)
        wp.id = wp_id

        result = engine.set_selected_wallpaper(wp, style="Fit", monitor="DISPLAY1")

        assert result.success is True
        assert result.wallpaper_id == wp_id
        assert result.style == "Fit"
        assert result.monitor == "DISPLAY1"
        assert result.message == "Wallpaper applied successfully."
        assert result.applied_at != ""

        # Verify database usage was updated
        updated_wp = wallpaper_repo.get_by_id(wp_id)
        assert updated_wp is not None
        assert updated_wp.usage_count == 1
        assert updated_wp.last_used == result.applied_at

        # Verify history was recorded
        history_entries = history_repo.get_recent()
        assert len(history_entries) == 1
        assert history_entries[0].wallpaper_id == wp_id
        assert history_entries[0].monitor == "DISPLAY1"

    def test_apply_by_wallpaper_id(
        self,
        engine: WindowsWallpaperService,
        wallpaper_repo: WallpaperRepository,
        tmp_path: Path,
    ) -> None:
        img = _create_test_image(tmp_path / "img2.jpg")
        wp = Wallpaper(
            filename="img2.jpg",
            path=str(img.resolve()),
            title="Deep Space",
            category="Space",
            width=5120,
            height=2880,
            resolution_class="5K",
        )
        wp_id = wallpaper_repo.add(wp)

        result = engine.set_selected_wallpaper(wp_id, style="Fill")
        assert result.success is True
        assert result.wallpaper_id == wp_id
        assert result.wallpaper is not None
        assert result.wallpaper.title == "Deep Space"

    def test_apply_nonexistent_id_raises_error(self, engine: WindowsWallpaperService) -> None:
        with pytest.raises(WallpaperNotFoundError, match="not found in database"):
            engine.set_selected_wallpaper(99999)

    def test_apply_by_file_path(
        self,
        engine: WindowsWallpaperService,
        tmp_path: Path,
    ) -> None:
        img = _create_test_image(tmp_path / "direct.jpg")
        result = engine.set_selected_wallpaper(img, style="Center")
        assert result.success is True
        assert result.image_path == img.resolve()
        assert result.style == "Center"


# ============================================================
# Random Wallpaper Selection
# ============================================================

class TestRandomWallpaper:
    def test_random_wallpaper_basic(
        self,
        engine: WindowsWallpaperService,
        wallpaper_repo: WallpaperRepository,
        tmp_path: Path,
    ) -> None:
        ids: list[int] = []
        for i in range(3):
            img = _create_test_image(tmp_path / f"rand_{i}.jpg")
            wp_id = wallpaper_repo.add(
                Wallpaper(
                    filename=f"rand_{i}.jpg",
                    path=str(img.resolve()),
                    title=f"Random {i}",
                    category="Nature",
                    width=3840,
                    height=2160,
                )
            )
            ids.append(wp_id)

        result = engine.set_random_wallpaper()
        assert result.success is True
        assert result.wallpaper_id in ids
        assert result.message == "Wallpaper applied successfully."

    def test_random_wallpaper_category_filter(
        self,
        engine: WindowsWallpaperService,
        wallpaper_repo: WallpaperRepository,
        tmp_path: Path,
    ) -> None:
        img_nature = _create_test_image(tmp_path / "nat.jpg")
        img_space = _create_test_image(tmp_path / "space.jpg")

        wallpaper_repo.add(
            Wallpaper(filename="nat.jpg", path=str(img_nature.resolve()), category="Nature", width=1920, height=1080)
        )
        space_id = wallpaper_repo.add(
            Wallpaper(filename="space.jpg", path=str(img_space.resolve()), category="Space", width=1920, height=1080)
        )

        result = engine.set_random_wallpaper(category="Space")
        assert result.success is True
        assert result.wallpaper_id == space_id

    def test_random_wallpaper_favorites_filter(
        self,
        engine: WindowsWallpaperService,
        wallpaper_repo: WallpaperRepository,
        tmp_path: Path,
    ) -> None:
        img1 = _create_test_image(tmp_path / "f1.jpg")
        img2 = _create_test_image(tmp_path / "f2.jpg")

        wallpaper_repo.add(
            Wallpaper(filename="f1.jpg", path=str(img1.resolve()), favorite=False, width=1920, height=1080)
        )
        fav_id = wallpaper_repo.add(
            Wallpaper(filename="f2.jpg", path=str(img2.resolve()), favorite=True, width=1920, height=1080)
        )

        result = engine.set_random_wallpaper(favorites_only=True)
        assert result.success is True
        assert result.wallpaper_id == fav_id

    def test_random_wallpaper_min_resolution_filter(
        self,
        engine: WindowsWallpaperService,
        wallpaper_repo: WallpaperRepository,
        tmp_path: Path,
    ) -> None:
        img_fhd = _create_test_image(tmp_path / "fhd.jpg", 1920, 1080)
        img_4k = _create_test_image(tmp_path / "4k.jpg", 3840, 2160)

        wallpaper_repo.add(
            Wallpaper(filename="fhd.jpg", path=str(img_fhd.resolve()), width=1920, height=1080)
        )
        id_4k = wallpaper_repo.add(
            Wallpaper(filename="4k.jpg", path=str(img_4k.resolve()), width=3840, height=2160)
        )

        result = engine.set_random_wallpaper(min_resolution="4K")
        assert result.success is True
        assert result.wallpaper_id == id_4k

    def test_random_wallpaper_prevent_repeat(
        self,
        engine: WindowsWallpaperService,
        wallpaper_repo: WallpaperRepository,
        tmp_path: Path,
    ) -> None:
        img1 = _create_test_image(tmp_path / "rep1.jpg")
        img2 = _create_test_image(tmp_path / "rep2.jpg")

        id1 = wallpaper_repo.add(Wallpaper(filename="rep1.jpg", path=str(img1.resolve()), width=1920, height=1080))
        id2 = wallpaper_repo.add(Wallpaper(filename="rep2.jpg", path=str(img2.resolve()), width=1920, height=1080))

        # First apply id1
        engine.set_selected_wallpaper(id1)

        # Next random wallpaper with prevent_repeat=True MUST pick id2
        result = engine.set_random_wallpaper(prevent_repeat=True)
        assert result.success is True
        assert result.wallpaper_id == id2

    def test_random_wallpaper_no_candidates(
        self,
        engine: WindowsWallpaperService,
    ) -> None:
        result = engine.set_random_wallpaper(category="NonExistentCategory")
        assert result.success is False
        assert result.error == "NO_CANDIDATES"


# ============================================================
# Previous Wallpaper Restoration
# ============================================================

class TestRestorePreviousWallpaper:
    def test_restore_previous_success(
        self,
        engine: WindowsWallpaperService,
        wallpaper_repo: WallpaperRepository,
        tmp_path: Path,
    ) -> None:
        imgA = _create_test_image(tmp_path / "wp_A.jpg", color=(255, 0, 0))
        imgB = _create_test_image(tmp_path / "wp_B.jpg", color=(0, 255, 0))

        idA = wallpaper_repo.add(Wallpaper(filename="wp_A.jpg", path=str(imgA.resolve()), width=1920, height=1080))
        idB = wallpaper_repo.add(Wallpaper(filename="wp_B.jpg", path=str(imgB.resolve()), width=1920, height=1080))

        # Apply A, then apply B
        engine.set_selected_wallpaper(idA)
        engine.set_selected_wallpaper(idB)
        assert engine.get_current_wallpaper() == str(imgB.resolve())

        # Restore previous
        res = engine.restore_previous_wallpaper()
        assert res.success is True
        assert res.wallpaper_id == idA
        assert engine.get_current_wallpaper() == str(imgA.resolve())

    def test_restore_no_history_fails_gracefully(
        self,
        engine: WindowsWallpaperService,
    ) -> None:
        res = engine.restore_previous_wallpaper()
        assert res.success is False
        assert res.error == "NO_PREVIOUS_WALLPAPER"


# ============================================================
# Wallpaper Preview Generation Tests
# ============================================================

class TestWallpaperPreview:
    @pytest.fixture
    def test_img(self, tmp_path: Path) -> Path:
        return _create_test_image(tmp_path / "preview_src.jpg", width=2000, height=1000)

    def test_preview_fill(self, engine: WindowsWallpaperService, test_img: Path) -> None:
        preview = engine.preview_wallpaper(test_img, target_width=1920, target_height=1080, style="Fill")
        assert isinstance(preview, Image.Image)
        assert preview.size == (1920, 1080)

    def test_preview_fit(self, engine: WindowsWallpaperService, test_img: Path) -> None:
        preview = engine.preview_wallpaper(test_img, target_width=1920, target_height=1080, style="Fit")
        assert preview.size == (1920, 1080)

    def test_preview_stretch(self, engine: WindowsWallpaperService, test_img: Path) -> None:
        preview = engine.preview_wallpaper(test_img, target_width=1280, target_height=720, style="Stretch")
        assert preview.size == (1280, 720)

    def test_preview_center(self, engine: WindowsWallpaperService, test_img: Path) -> None:
        preview = engine.preview_wallpaper(test_img, target_width=2560, target_height=1440, style="Center")
        assert preview.size == (2560, 1440)

    def test_preview_tile(self, engine: WindowsWallpaperService, test_img: Path) -> None:
        small_img = _create_test_image(test_img.parent / "tile_src.jpg", 100, 100)
        preview = engine.preview_wallpaper(small_img, target_width=500, target_height=500, style="Tile")
        assert preview.size == (500, 500)

    def test_preview_span(self, engine: WindowsWallpaperService, test_img: Path) -> None:
        preview = engine.preview_wallpaper(test_img, target_width=3840, target_height=1080, style="Span")
        assert preview.size == (3840, 1080)

    def test_save_preview(self, engine: WindowsWallpaperService, test_img: Path, tmp_path: Path) -> None:
        out_file = tmp_path / "cache" / "preview.jpg"
        saved = engine.save_preview(test_img, out_file, target_width=800, target_height=450)
        assert saved.exists()
        assert saved.stat().st_size > 0
        with Image.open(saved) as img:
            assert img.size == (800, 450)


# ============================================================
# History Repository Tests
# ============================================================

class TestHistoryRepository:
    def test_crud_and_counts(
        self,
        history_repo: HistoryRepository,
        wallpaper_repo: WallpaperRepository,
        tmp_path: Path,
    ) -> None:
        img = _create_test_image(tmp_path / "hist.jpg")
        wp_id = wallpaper_repo.add(Wallpaper(filename="hist.jpg", path=str(img), width=1920, height=1080))

        # Add history entries
        h1 = history_repo.add(WallpaperHistory(wallpaper_id=wp_id, set_at="2026-10-18T10:00:00Z", monitor="DISPLAY1"))
        h2 = history_repo.add(WallpaperHistory(wallpaper_id=wp_id, set_at="2026-10-18T12:00:00Z", monitor="DISPLAY1"))

        assert history_repo.count() == 2
        assert history_repo.count("DISPLAY1") == 2
        assert history_repo.count("DISPLAY2") == 0

        # Query single
        entry = history_repo.get_by_id(h1)
        assert entry is not None
        assert entry.wallpaper_id == wp_id
        assert entry.monitor == "DISPLAY1"

        # Latest
        latest = history_repo.get_latest("DISPLAY1")
        assert latest is not None
        assert latest.id == h2

        # Recent
        recent = history_repo.get_recent(limit=10)
        assert len(recent) == 2
        assert recent[0].id == h2  # Newest first

        # Clear
        cleared = history_repo.clear()
        assert cleared == 2
        assert history_repo.count() == 0

    def test_cascade_delete_wallpaper(
        self,
        db: Database,
        wallpaper_repo: WallpaperRepository,
        history_repo: HistoryRepository,
        tmp_path: Path,
    ) -> None:
        img = _create_test_image(tmp_path / "casc.jpg")
        wp_id = wallpaper_repo.add(Wallpaper(filename="casc.jpg", path=str(img), width=1920, height=1080))
        history_repo.add(WallpaperHistory(wallpaper_id=wp_id, set_at="2026-10-18T10:00:00Z", monitor="DISPLAY1"))

        assert history_repo.count() == 1
        # Deleting wallpaper should delete history entries
        wallpaper_repo.delete(wp_id)
        assert history_repo.count() == 0
