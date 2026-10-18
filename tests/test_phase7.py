"""
Sandy Wallpaper Studio — Phase 7 Tests
=========================================
Comprehensive tests for Favorites & History workflows:
- WallpaperView model and ViewRepository
- WallpaperRepository Phase 7 methods (favorites, recents, toggle)
- HistoryRepository Phase 7 join and recents methods
- HistoryService orchestration (favorites, applied, viewed, downloaded, restore, reapply)
- FavoritesView GUI component (rendering, empty state, filtering, random favorite)
- HistoryView GUI component (tabs, applied rows, reapply, restore, clear)
- MainWindow navigation integration
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from app.config import Config
from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.database.history_repository import HistoryRepository
from app.database.models import Wallpaper, WallpaperHistory, WallpaperView
from app.database.view_repository import ViewRepository
from app.database.wallpaper_repository import WallpaperRepository
from app.services.history_service import HistoryService
from app.services.wallpaper_service import WindowsWallpaperService
from app.ui.favorites_view import FavoritesView
from app.ui.history_view import HistoryView, _format_relative_time
from app.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a headless QApplication instance exists."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def test_db(tmp_path):
    """Provide a fresh connected test database."""
    db_path = tmp_path / "test_phase7.db"
    db = Database(db_path)
    db.connect()
    cat_repo = CategoryRepository(db)
    cat_repo.seed_defaults()
    yield db
    db.close()


@pytest.fixture
def test_config(tmp_path):
    """Provide a test Config."""
    cfg = Config(config_dir=tmp_path / "app_config")
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def _create_test_image(
    path: Path,
    width: int = 1920,
    height: int = 1080,
    color: tuple = (70, 130, 180),
) -> Path:
    """Create a minimal real test image on disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color=color)
    img.save(str(path), format="JPEG")
    return path


def _create_sample_wallpapers(
    db: Database,
    count: int = 5,
    tmp_path: Path | None = None,
) -> list[Wallpaper]:
    """Helper to insert sample wallpapers for testing."""
    repo = WallpaperRepository(db)
    created = []
    categories = ["Nature", "Space", "Anime", "Architecture", "Minimal"]
    for i in range(1, count + 1):
        if tmp_path is not None:
            img_file = tmp_path / "wallpapers" / f"wallpaper_{i}.jpg"
            _create_test_image(img_file)
            file_path = str(img_file)
        else:
            file_path = f"C:/wallpapers/wallpaper_{i}.jpg"

        wp = Wallpaper(
            filename=f"wallpaper_{i}.jpg",
            path=file_path,
            title=f"Sample Wallpaper {i}",
            category=categories[(i - 1) % len(categories)],
            width=3840 if i % 2 == 0 else 1920,
            height=2160 if i % 2 == 0 else 1080,
            resolution_class="4K" if i % 2 == 0 else "1080p",
            download_date=f"2026-10-18T10:0{i}:00Z",
            favorite=(i <= 2),
            last_used=f"2026-10-18T12:0{i}:00Z" if i <= 3 else None,
            usage_count=i if i <= 3 else 0,
        )
        wid = repo.add(wp)
        wp.id = wid
        created.append(wp)
    return created


# ======================================================================
# 1. WallpaperView Model Tests
# ======================================================================
class TestWallpaperViewModel:
    def test_default_values(self):
        view = WallpaperView()
        assert view.id is None
        assert view.wallpaper_id == 0
        assert view.viewed_at is None

    def test_to_dict(self):
        view = WallpaperView(id=1, wallpaper_id=42, viewed_at="2026-10-18T12:00:00Z")
        d = view.to_dict()
        assert d["wallpaper_id"] == 42
        assert d["viewed_at"] == "2026-10-18T12:00:00Z"
        assert "id" not in d


# ======================================================================
# 2. ViewRepository Tests
# ======================================================================
class TestViewRepository:
    def test_add_and_get(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 2)
        repo = ViewRepository(test_db)

        v_id = repo.add(
            WallpaperView(wallpaper_id=wallpapers[0].id, viewed_at="2026-10-18T10:00:00Z")
        )
        assert v_id > 0

        fetched = repo.get_by_id(v_id)
        assert fetched is not None
        assert fetched.id == v_id
        assert fetched.wallpaper_id == wallpapers[0].id
        assert fetched.viewed_at == "2026-10-18T10:00:00Z"

    def test_record_view_convenience(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 1)
        repo = ViewRepository(test_db)

        v_id = repo.record_view(wallpapers[0].id)
        assert v_id > 0
        fetched = repo.get_by_id(v_id)
        assert fetched is not None
        assert fetched.viewed_at is not None

    def test_get_recent_and_distinct(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 3)
        repo = ViewRepository(test_db)

        repo.record_view(wallpapers[0].id, timestamp="2026-10-18T10:00:00Z")
        repo.record_view(wallpapers[1].id, timestamp="2026-10-18T10:05:00Z")
        repo.record_view(wallpapers[0].id, timestamp="2026-10-18T10:10:00Z")

        recent_views = repo.get_recent(limit=10)
        assert len(recent_views) == 3

        recent_ids = repo.get_recent_wallpaper_ids(limit=10)
        assert recent_ids == [wallpapers[0].id, wallpapers[1].id]

        recent_wallpapers = repo.get_recent_wallpapers(limit=10)
        assert len(recent_wallpapers) == 2
        assert recent_wallpapers[0].id == wallpapers[0].id
        assert recent_wallpapers[1].id == wallpapers[1].id

    def test_count_and_clear(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 2)
        repo = ViewRepository(test_db)

        repo.record_view(wallpapers[0].id)
        repo.record_view(wallpapers[1].id)

        assert repo.count() == 2
        assert repo.count_distinct_wallpapers() == 2

        cleared = repo.clear()
        assert cleared == 2
        assert repo.count() == 0

    def test_delete_for_wallpaper_and_cascade(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 2)
        wp_repo = WallpaperRepository(test_db)
        repo = ViewRepository(test_db)

        repo.record_view(wallpapers[0].id)
        repo.record_view(wallpapers[0].id)
        repo.record_view(wallpapers[1].id)

        deleted = repo.delete_for_wallpaper(wallpapers[0].id)
        assert deleted == 2
        assert repo.count() == 1

        # Test foreign key cascade delete
        repo.record_view(wallpapers[1].id)
        wp_repo.delete(wallpapers[1].id)
        assert repo.count() == 0


# ======================================================================
# 3. WallpaperRepository Phase 7 Tests
# ======================================================================
class TestWallpaperRepositoryPhase7:
    def test_toggle_favorite(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 1)
        repo = WallpaperRepository(test_db)
        wid = wallpapers[0].id

        # Initial state in helper is True
        assert repo.get_by_id(wid).favorite is True

        new_state = repo.toggle_favorite(wid)
        assert new_state is False
        assert repo.get_by_id(wid).favorite is False

        new_state = repo.toggle_favorite(wid)
        assert new_state is True
        assert repo.get_by_id(wid).favorite is True

    def test_count_favorites_and_category_filter(self, test_db):
        _create_sample_wallpapers(test_db, 5)
        repo = WallpaperRepository(test_db)

        # 2 out of 5 were created as favorite (Nature, Space)
        total_favs = repo.count_favorites()
        assert total_favs == 2

        nature_favs = repo.count_favorites(category="Nature")
        assert nature_favs == 1

        anime_favs = repo.count_favorites(category="Anime")
        assert anime_favs == 0

    def test_get_favorites_with_options(self, test_db):
        _create_sample_wallpapers(test_db, 5)
        repo = WallpaperRepository(test_db)

        favs = repo.get_favorites(category="Nature")
        assert len(favs) == 1
        assert favs[0].category == "Nature"

        sorted_favs = repo.get_favorites(order_by="title ASC")
        assert len(sorted_favs) == 2
        assert sorted_favs[0].title <= sorted_favs[1].title

    def test_get_recently_downloaded_and_applied(self, test_db):
        _create_sample_wallpapers(test_db, 5)
        repo = WallpaperRepository(test_db)

        downloaded = repo.get_recently_downloaded(limit=3)
        assert len(downloaded) == 3
        # Should be newest download_date first
        assert downloaded[0].download_date >= downloaded[1].download_date

        applied = repo.get_recently_applied(limit=3)
        assert len(applied) == 3
        # Should be newest last_used first
        assert applied[0].last_used >= applied[1].last_used


# ======================================================================
# 4. HistoryRepository Phase 7 Tests
# ======================================================================
class TestHistoryRepositoryPhase7:
    def test_get_recent_with_wallpapers(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 3)
        h_repo = HistoryRepository(test_db)

        h_repo.add(
            WallpaperHistory(
                wallpaper_id=wallpapers[0].id, set_at="2026-10-18T14:00:00Z", monitor="primary"
            )
        )
        h_repo.add(
            WallpaperHistory(
                wallpaper_id=wallpapers[1].id, set_at="2026-10-18T15:00:00Z", monitor="secondary"
            )
        )

        results = h_repo.get_recent_with_wallpapers(limit=10)
        assert len(results) == 2

        hist0, wp0 = results[0]
        assert hist0.wallpaper_id == wallpapers[1].id
        assert wp0 is not None
        assert wp0.id == wallpapers[1].id
        assert hist0.monitor == "secondary"

        hist1, wp1 = results[1]
        assert hist1.wallpaper_id == wallpapers[0].id
        assert wp1 is not None
        assert wp1.id == wallpapers[0].id

    def test_get_recent_wallpapers_deduplicated(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 3)
        h_repo = HistoryRepository(test_db)

        h_repo.add(WallpaperHistory(wallpaper_id=wallpapers[0].id, set_at="2026-10-18T14:00:00Z"))
        h_repo.add(WallpaperHistory(wallpaper_id=wallpapers[1].id, set_at="2026-10-18T15:00:00Z"))
        h_repo.add(WallpaperHistory(wallpaper_id=wallpapers[0].id, set_at="2026-10-18T16:00:00Z"))

        recent_wps = h_repo.get_recent_wallpapers(limit=10)
        assert len(recent_wps) == 2
        assert recent_wps[0].id == wallpapers[0].id
        assert recent_wps[1].id == wallpapers[1].id


# ======================================================================
# 5. HistoryService Workflows Tests
# ======================================================================
class TestHistoryService:
    def test_favorites_workflows(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 4)
        svc = HistoryService(db=test_db)

        # Count and get
        assert svc.count_favorites() == 2
        favs = svc.get_favorites()
        assert len(favs) == 2

        # Toggle favorite
        wid = wallpapers[2].id  # Initially favorite is False
        new_state = svc.toggle_favorite(wid)
        assert new_state is True
        assert svc.count_favorites() == 3

        # Set favorite explicit
        svc.set_favorite(wid, False)
        assert svc.count_favorites() == 2

        # Clear all favorites
        cleared = svc.clear_all_favorites()
        assert cleared == 2
        assert svc.count_favorites() == 0

    def test_applied_and_restore_workflows(self, test_db, tmp_path):
        wallpapers = _create_sample_wallpapers(test_db, tmp_path=tmp_path, count=3)
        wp_repo = WallpaperRepository(test_db)
        h_repo = HistoryRepository(test_db)
        wp_svc = WindowsWallpaperService(
            db=test_db, wallpaper_repo=wp_repo, history_repo=h_repo, simulate=True
        )
        svc = HistoryService(
            db=test_db, wallpaper_service=wp_svc, history_repo=h_repo, wallpaper_repo=wp_repo
        )

        # Apply two wallpapers
        res1 = svc.reapply_wallpaper(wallpapers[0].id)
        assert res1.success is True
        assert svc.count_applied() == 1

        res2 = svc.reapply_wallpaper(wallpapers[1].id)
        assert res2.success is True
        assert svc.count_applied() == 2

        applied = svc.get_recently_applied(limit=10)
        assert len(applied) == 2
        assert applied[0][0].wallpaper_id == wallpapers[1].id

        # Restore previous
        res_restore = svc.restore_previous_wallpaper()
        assert res_restore.success is True
        assert res_restore.wallpaper_id == wallpapers[0].id

        # Clear history
        cleared = svc.clear_applied_history()
        assert cleared >= 2
        assert svc.count_applied() == 0

    def test_viewed_and_downloaded_workflows(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 3)
        svc = HistoryService(db=test_db)

        # Record views
        svc.record_view(wallpapers[0].id)
        svc.record_view(wallpapers[1].id)

        assert svc.count_viewed() == 2
        assert svc.count_distinct_viewed_wallpapers() == 2

        viewed = svc.get_recently_viewed(limit=5)
        assert len(viewed) == 2

        # Downloaded
        downloaded = svc.get_recently_downloaded(limit=5)
        assert len(downloaded) == 3

        # Clear views
        cleared = svc.clear_view_history()
        assert cleared == 2
        assert svc.count_viewed() == 0

    def test_history_summary(self, test_db):
        wallpapers = _create_sample_wallpapers(test_db, 3)
        svc = HistoryService(db=test_db)

        svc.record_view(wallpapers[0].id)
        summary = svc.get_history_summary()

        assert "favorites_count" in summary
        assert "applied_count" in summary
        assert "viewed_count" in summary
        assert summary["favorites_count"] == 2
        assert summary["viewed_count"] == 1


# ======================================================================
# 6. FavoritesView GUI Component Tests
# ======================================================================
class TestFavoritesView:
    def test_construction_and_empty_state(self, qapp, test_db, test_config):
        wp_repo = WallpaperRepository(test_db)
        wp_svc = WindowsWallpaperService(db=test_db, wallpaper_repo=wp_repo, simulate=True)
        view = FavoritesView(
            db=test_db,
            wallpaper_service=wp_svc,
            cache_dir=test_config.cache_dir,
        )
        assert view is not None
        assert view._count_badge.text() == "0"
        assert len(view._cards) == 0

    def test_populate_favorites_and_filters(self, qapp, test_db, test_config, tmp_path):
        _create_sample_wallpapers(test_db, tmp_path=tmp_path, count=4)  # 2 are favorites
        wp_repo = WallpaperRepository(test_db)
        wp_svc = WindowsWallpaperService(db=test_db, wallpaper_repo=wp_repo, simulate=True)
        view = FavoritesView(
            db=test_db,
            wallpaper_service=wp_svc,
            cache_dir=test_config.cache_dir,
        )

        assert len(view._cards) == 2
        assert view._count_badge.text() == "2"

        # Change category filter
        idx = view._cat_combo.findText("Nature")
        if idx >= 0:
            view._cat_combo.setCurrentIndex(idx)
            assert len(view._cards) == 1

    def test_random_favorite_button(self, qapp, test_db, test_config, tmp_path):
        _create_sample_wallpapers(test_db, tmp_path=tmp_path, count=4)
        wp_repo = WallpaperRepository(test_db)
        wp_svc = WindowsWallpaperService(db=test_db, wallpaper_repo=wp_repo, simulate=True)
        view = FavoritesView(
            db=test_db,
            wallpaper_service=wp_svc,
            cache_dir=test_config.cache_dir,
        )

        emitted_applied = []
        view.wallpaper_applied.connect(lambda wid: emitted_applied.append(wid))

        view._on_random_favorite()
        assert len(emitted_applied) == 1
        assert emitted_applied[0] > 0


# ======================================================================
# 7. HistoryView GUI Component Tests
# ======================================================================
class TestHistoryView:
    def test_construction_and_tabs(self, qapp, test_db, test_config):
        wp_repo = WallpaperRepository(test_db)
        wp_svc = WindowsWallpaperService(db=test_db, wallpaper_repo=wp_repo, simulate=True)
        view = HistoryView(
            db=test_db,
            wallpaper_service=wp_svc,
            cache_dir=test_config.cache_dir,
        )
        assert view is not None
        assert view._active_tab == 0

        # Switch to tab 1 (Recently Viewed)
        view._switch_tab(1)
        assert view._active_tab == 1
        assert view._stack.currentIndex() == 1

        # Switch to tab 2 (Recently Downloaded)
        view._switch_tab(2)
        assert view._active_tab == 2
        assert view._stack.currentIndex() == 2

    def test_refresh_hides_previous_applied_empty_state_before_replacement(
        self, qapp, test_db, test_config
    ):
        wp_repo = WallpaperRepository(test_db)
        wp_svc = WindowsWallpaperService(db=test_db, wallpaper_repo=wp_repo, simulate=True)
        view = HistoryView(
            db=test_db,
            wallpaper_service=wp_svc,
            cache_dir=test_config.cache_dir,
        )
        view.show()
        qapp.processEvents()
        old_state = view._applied_layout.itemAt(0).widget()

        view.refresh()

        new_state = view._applied_layout.itemAt(0).widget()
        assert view._applied_layout.count() == 1
        assert old_state is not new_state
        assert old_state.isHidden()
        view.close()

    def test_applied_tab_reapply_and_restore(self, qapp, test_db, test_config, tmp_path):
        wallpapers = _create_sample_wallpapers(test_db, tmp_path=tmp_path, count=3)
        wp_repo = WallpaperRepository(test_db)
        h_repo = HistoryRepository(test_db)
        h_repo.add(WallpaperHistory(wallpaper_id=wallpapers[0].id, set_at="2026-10-18T10:00:00Z"))
        h_repo.add(WallpaperHistory(wallpaper_id=wallpapers[1].id, set_at="2026-10-18T11:00:00Z"))

        wp_svc = WindowsWallpaperService(
            db=test_db, wallpaper_repo=wp_repo, history_repo=h_repo, simulate=True
        )
        view = HistoryView(
            db=test_db,
            wallpaper_service=wp_svc,
            cache_dir=test_config.cache_dir,
        )

        emitted = []
        view.wallpaper_applied.connect(lambda wid: emitted.append(wid))

        # Test reapply
        view._on_reapply_wallpaper(wallpapers[0].id)
        assert len(emitted) == 1
        assert emitted[0] == wallpapers[0].id

        # Test restore previous
        view._on_restore_previous()
        assert len(emitted) == 2

    def test_relative_time_formatter(self):
        assert _format_relative_time(None) == "Unknown"
        assert _format_relative_time("") == "Unknown"
        assert "ago" in _format_relative_time(
            "2026-10-10T00:00:00Z"
        ) or "-" in _format_relative_time("2026-10-10T00:00:00Z")


# ======================================================================
# 8. MainWindow Integration Tests
# ======================================================================
class TestMainWindowPhase7:
    def test_views_registered_and_navigable(self, qapp, test_db, test_config):
        win = MainWindow(config=test_config, db=test_db)
        assert "favorites" in win._views
        assert "history" in win._views
        assert isinstance(win._views["favorites"], FavoritesView)
        assert isinstance(win._views["history"], HistoryView)

        # Navigate to favorites
        win._navigate_to("favorites")
        assert win._stack.currentWidget() == win._views["favorites"]

        # Navigate to history
        win._navigate_to("history")
        assert win._stack.currentWidget() == win._views["history"]

        win.close()
