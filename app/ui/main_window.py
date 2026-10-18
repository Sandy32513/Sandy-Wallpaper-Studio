"""
Sandy Wallpaper Studio — Main Window
======================================
The top-level QMainWindow that hosts:
- Sidebar navigation
- QStackedWidget switching between views
- Global status bar
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from app.config import Config
from app.constants import APP_NAME, APP_VERSION, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT
from app.database.database import Database
from app.database.wallpaper_repository import WallpaperRepository
from app.database.category_repository import CategoryRepository
from app.database.history_repository import HistoryRepository
from app.services.history_service import HistoryService
from app.services.wallpaper_service import WindowsWallpaperService
from app.ui import design_system as ds
from app.ui.components.sidebar import Sidebar
from app.ui.dashboard_view import DashboardView
from app.ui.favorites_view import FavoritesView
from app.ui.history_view import HistoryView
from app.ui.library_view import LibraryView


class PlaceholderView(QWidget):
    """Generic placeholder for views not yet fully implemented."""

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QVBoxLayout, QLabel
        self.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("⊘")
        icon.setStyleSheet(f"color: {ds.TEXT_DISABLED}; font-size: 64px; background: transparent;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL}px; font-weight: 700; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        sub = QLabel("Coming in a future phase.")
        sub.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_MD}px; background: transparent;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)


class MainWindow(QMainWindow):
    """Sandy Wallpaper Studio main application window."""

    def __init__(
        self,
        config: Config,
        db: Database,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._db = db

        # Services
        self._wp_repo = WallpaperRepository(db)
        self._cat_repo = CategoryRepository(db)
        self._history_repo = HistoryRepository(db)
        self._wp_service = WindowsWallpaperService(
            db=db,
            wallpaper_repo=self._wp_repo,
            history_repo=self._history_repo,
        )
        self._history_service = HistoryService(
            db=db,
            wallpaper_service=self._wp_service,
            wallpaper_repo=self._wp_repo,
            history_repo=self._history_repo,
        )

        self._setup_window()
        self._build_ui()
        self._navigate_to("dashboard")

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------
    def _setup_window(self) -> None:
        self.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.resize(1280, 800)
        self.setStyleSheet(ds.build_stylesheet())

        # Try to set monospace-fallback for technical metadata
        self.setFont(QFont(ds.FONT_FAMILY, ds.FONT_SIZE_MD))

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        central.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---- Sidebar ----
        self._sidebar = Sidebar()
        self._sidebar.nav_changed.connect(self._navigate_to)
        root_layout.addWidget(self._sidebar)

        # ---- Content stack ----
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        root_layout.addWidget(self._stack, stretch=1)

        # Register views
        self._views: dict[str, QWidget] = {}
        self._register_views()

        # ---- Status bar ----
        self._statusbar = QStatusBar()
        self._statusbar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {ds.BG_SURFACE};
                color: {ds.TEXT_SECONDARY};
                border-top: 1px solid {ds.BG_BORDER};
                font-size: {ds.FONT_SIZE_SM}px;
                padding: 2px 12px;
            }}
        """)
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage(f"{APP_NAME} {APP_VERSION} — Ready")

    def _register_views(self) -> None:
        cache_dir = self._config.cache_dir

        # Dashboard
        dashboard = DashboardView(
            db=self._db,
            wallpaper_service=self._wp_service,
            cache_dir=cache_dir,
        )
        dashboard.navigate_to.connect(self._navigate_to)
        dashboard.status_message.connect(self._show_status)
        dashboard.wallpaper_applied.connect(self._on_wallpaper_applied)
        self._add_view("dashboard", dashboard)

        # Library
        library = LibraryView(
            db=self._db,
            wallpaper_service=self._wp_service,
            cache_dir=cache_dir,
        )
        library.status_message.connect(self._show_status)
        library.wallpaper_applied.connect(self._on_wallpaper_applied)
        self._add_view("library", library)

        # Favorites (Phase 7)
        favorites = FavoritesView(
            db=self._db,
            wallpaper_service=self._wp_service,
            history_service=self._history_service,
            cache_dir=cache_dir,
        )
        favorites.navigate_to.connect(self._navigate_to)
        favorites.status_message.connect(self._show_status)
        favorites.wallpaper_applied.connect(self._on_wallpaper_applied)
        self._add_view("favorites", favorites)

        # History (Phase 7)
        history = HistoryView(
            db=self._db,
            wallpaper_service=self._wp_service,
            history_service=self._history_service,
            cache_dir=cache_dir,
        )
        history.navigate_to.connect(self._navigate_to)
        history.status_message.connect(self._show_status)
        history.wallpaper_applied.connect(self._on_wallpaper_applied)
        self._add_view("history", history)

        # Placeholder views for future phases
        placeholders = {
            "discover":   "Discover",
            "categories": "Categories",
            "duplicates": "Duplicate Manager",
            "downloads":  "Downloads",
            "settings":   "Settings",
        }
        for key, label in placeholders.items():
            self._add_view(key, PlaceholderView(label))

    def _add_view(self, key: str, widget: QWidget) -> None:
        self._views[key] = widget
        self._stack.addWidget(widget)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _navigate_to(self, key: str) -> None:
        view = self._views.get(key)
        if view:
            if hasattr(view, "refresh"):
                try:
                    view.refresh()
                except Exception:
                    pass
            self._stack.setCurrentWidget(view)
            self._sidebar.navigate_to(key)
            self._show_status(f"Navigated to: {key.capitalize()}")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _show_status(self, message: str) -> None:
        self._statusbar.showMessage(message)

    def _on_wallpaper_applied(self, wallpaper_id: int) -> None:
        self._show_status(f"✓ Wallpaper #{wallpaper_id} applied.")

    # ------------------------------------------------------------------
    # Close event
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        self._db.close()
        super().closeEvent(event)
