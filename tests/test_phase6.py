"""
Sandy Wallpaper Studio — Phase 6 Tests
=========================================
Tests for Desktop GUI:
- Design system color tokens and typography constants
- Qt application headless initialization
- MainWindow construction and view registry
- DashboardView and LibraryView instantiation
- SearchFilterBar signal wiring
- WallpaperCard rendering with Wallpaper data model
"""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

from app.config import Config
from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.database.models import Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.services.wallpaper_service import WindowsWallpaperService
from app.ui import design_system as ds
from app.ui.components.search_bar import SearchFilterBar
from app.ui.components.wallpaper_card import WallpaperCard
from app.ui.dashboard_view import DashboardView
from app.ui.library_view import LibraryView
from app.ui.main_window import MainWindow, PlaceholderView


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
    db_path = tmp_path / "test_gui.db"
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


class TestDesignSystem:
    def test_colors_defined(self):
        assert ds.BG_DEEP.startswith("#")
        assert ds.BG_SURFACE.startswith("#")
        assert ds.ACCENT_PRIMARY.startswith("#")
        assert ds.TEXT_PRIMARY.startswith("#")
        assert ds.TEXT_SECONDARY.startswith("#")

    def test_typography_metrics(self):
        assert ds.FONT_SIZE_SM > 0
        assert ds.FONT_SIZE_MD > ds.FONT_SIZE_SM
        assert ds.FONT_SIZE_XL > ds.FONT_SIZE_MD

    def test_layout_tokens(self):
        assert ds.CARD_RADIUS > 0
        assert ds.SPACE_MD > 0


class TestUIComponents:
    def test_search_filter_bar_signals(self, qapp):
        bar = SearchFilterBar(categories=["Nature", "Space"])
        emitted = []
        bar.search_changed.connect(lambda f: emitted.append(f))

        bar._cat_combo.setCurrentIndex(1)
        assert len(emitted) > 0
        assert emitted[-1]["category"] == "Nature"

    def test_wallpaper_card(self, qapp):
        wp = Wallpaper(
            filename="mountain.jpg",
            path="C:/wallpapers/mountain.jpg",
            width=3840,
            height=2160,
            resolution_class="4K",
            category="Nature",
            favorite=True,
        )
        card = WallpaperCard(wallpaper=wp)
        assert card._wallpaper.category == "Nature"
        assert card._is_fav is True

    def test_placeholder_view(self, qapp):
        pv = PlaceholderView("Discover")
        assert pv is not None


class TestViewsAndMainWindow:
    def test_dashboard_view_construction(self, qapp, test_db, test_config):
        wp_repo = WallpaperRepository(test_db)
        wp_svc = WindowsWallpaperService(db=test_db, wallpaper_repo=wp_repo, simulate=True)
        view = DashboardView(db=test_db, wallpaper_service=wp_svc, cache_dir=test_config.cache_dir)
        assert view is not None

    def test_library_view_construction(self, qapp, test_db, test_config):
        wp_repo = WallpaperRepository(test_db)
        wp_svc = WindowsWallpaperService(db=test_db, wallpaper_repo=wp_repo, simulate=True)
        # Verify it works both with explicit cache_dir and with default (None)
        view1 = LibraryView(db=test_db, wallpaper_service=wp_svc, cache_dir=test_config.cache_dir)
        assert view1 is not None

        view2 = LibraryView(db=test_db, wallpaper_service=wp_svc, cache_dir=None)
        assert view2 is not None

    def test_main_window_construction(self, qapp, test_db, test_config):
        win = MainWindow(config=test_config, db=test_db)
        assert win is not None
        assert "dashboard" in win._views
        assert "library" in win._views
        win.close()
