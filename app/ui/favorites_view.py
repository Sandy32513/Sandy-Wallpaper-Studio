"""
Sandy Wallpaper Studio — Favorites View
========================================
Dedicated view displaying and managing favorite wallpapers.
Supports category filtering, sorting, one-click desktop application,
random favorite selection, and detail inspection.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.config import Config
from app.constants import DEFAULT_LIBRARY_DIR_NAME
from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.database.models import Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.services.history_service import HistoryService
from app.services.wallpaper_service import WindowsWallpaperService
from app.ui import design_system as ds
from app.ui.components.detail_dialog import DetailDialog
from app.ui.components.wallpaper_card import WallpaperCard
from app.utils.image_utils import thumbnail_cache_path

logger = logging.getLogger(__name__)

_GRID_COLS = 4


class FavoritesView(QWidget):
    """Favorites gallery view with quick filtering, sorting, and actions."""

    status_message = Signal(str)
    wallpaper_applied = Signal(int)
    navigate_to = Signal(str)

    def __init__(
        self,
        db: Database,
        wallpaper_service: WindowsWallpaperService,
        history_service: HistoryService | None = None,
        cache_dir: Path | None = None,
        parent: QWidget | None = None,
        config: Config | None = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._config = config
        self._wp_service = wallpaper_service
        self._history_service = history_service or HistoryService(
            db=db,
            wallpaper_service=wallpaper_service,
        )
        self._wp_repo = WallpaperRepository(db)
        self._cat_repo = CategoryRepository(db)

        if cache_dir is None:
            cache_dir = Path.home() / "Pictures" / DEFAULT_LIBRARY_DIR_NAME / "Cache"
        self._cache_dir = cache_dir

        self._cards: list[WallpaperCard] = []
        self._current_wallpapers: list[Wallpaper] = []

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- Header / Controls Bar ----
        header_bar = self._make_header_bar()
        layout.addWidget(header_bar)

        # ---- Scroll area for grid ----
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(f"background-color: {ds.BG_DEEP}; border: none;")

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL)
        self._grid_layout.setSpacing(ds.SPACE_LG)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._scroll.setWidget(self._grid_container)
        layout.addWidget(self._scroll, stretch=1)

    def _make_header_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(64)
        bar.setStyleSheet(f"""
            QWidget {{
                background-color: {ds.BG_SURFACE};
                border-bottom: 1px solid {ds.BG_BORDER};
            }}
        """)
        h = QHBoxLayout(bar)
        h.setContentsMargins(ds.SPACE_XL, 0, ds.SPACE_XL, 0)
        h.setSpacing(ds.SPACE_MD)

        # Title
        title_lbl = QLabel("♥  Favorites")
        title_lbl.setStyleSheet(f"""
            color: {ds.TEXT_PRIMARY};
            font-size: {ds.FONT_SIZE_XL}px;
            font-weight: 700;
            background: transparent;
        """)
        h.addWidget(title_lbl)

        # Count badge
        self._count_badge = QLabel("0")
        self._count_badge.setStyleSheet(f"""
            background-color: {ds.BG_ELEVATED};
            color: {ds.ACCENT_LIGHT};
            font-size: {ds.FONT_SIZE_XS}px;
            font-weight: 600;
            border-radius: 10px;
            padding: 2px 10px;
            border: 1px solid {ds.BG_BORDER};
        """)
        h.addWidget(self._count_badge)

        h.addStretch()

        # Category filter combo
        cat_lbl = QLabel("Category:")
        cat_lbl.setStyleSheet(
            f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px; background: transparent;"
        )
        h.addWidget(cat_lbl)

        self._cat_combo = QComboBox()
        self._cat_combo.setFixedHeight(34)
        self._cat_combo.setMinimumWidth(140)
        self._cat_combo.addItem("All Categories", "")
        for cat in self._cat_repo.get_all():
            self._cat_combo.addItem(cat.name, cat.name)
        self._cat_combo.currentIndexChanged.connect(self._on_filter_changed)
        h.addWidget(self._cat_combo)

        # Sort order combo
        sort_lbl = QLabel("Sort:")
        sort_lbl.setStyleSheet(
            f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px; background: transparent;"
        )
        h.addWidget(sort_lbl)

        self._sort_combo = QComboBox()
        self._sort_combo.setFixedHeight(34)
        self._sort_combo.setMinimumWidth(150)
        self._sort_combo.addItem("Newest Added", "download_date DESC")
        self._sort_combo.addItem("Oldest Added", "download_date ASC")
        self._sort_combo.addItem("Title (A–Z)", "title ASC")
        self._sort_combo.addItem("Resolution (High-Low)", "width DESC")
        self._sort_combo.addItem("Most Used", "usage_count DESC")
        self._sort_combo.currentIndexChanged.connect(self._on_filter_changed)
        h.addWidget(self._sort_combo)

        # Random favorite button
        self._btn_random = QPushButton("⚄  Random Favorite")
        self._btn_random.setObjectName("accent")
        self._btn_random.setFixedHeight(34)
        self._btn_random.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_random.setToolTip("Apply a random wallpaper from your favorites to the desktop")
        self._btn_random.clicked.connect(self._on_random_favorite)
        h.addWidget(self._btn_random)

        # Clear all favorites button
        self._btn_clear = QPushButton("🗑  Clear Favorites")
        self._btn_clear.setFixedHeight(34)
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear.setToolTip("Remove all wallpapers from favorites")
        self._btn_clear.setStyleSheet(f"""
            QPushButton {{
                background-color: {ds.BG_ELEVATED};
                color: {ds.DANGER};
                border: 1px solid {ds.BG_BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: {ds.FONT_SIZE_SM}px;
            }}
            QPushButton:hover {{
                background-color: {ds.BG_BORDER};
                border-color: {ds.DANGER};
            }}
        """)
        self._btn_clear.clicked.connect(self._on_clear_favorites)
        h.addWidget(self._btn_clear)

        return bar

    # ------------------------------------------------------------------
    # Data Loading & Rendering
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload favorite wallpapers based on active filters."""
        category = self._cat_combo.currentData() or None
        order_by = self._sort_combo.currentData() or "download_date DESC"

        self._current_wallpapers = self._history_service.get_favorites(
            category=category,
            order_by=order_by,
            limit=200,
        )

        total_favs = self._history_service.count_favorites()
        current_favs = len(self._current_wallpapers)
        if category:
            self._count_badge.setText(f"{current_favs} of {total_favs}")
        else:
            self._count_badge.setText(f"{total_favs}")

        self._render_grid(self._current_wallpapers)

    def _render_grid(self, wallpapers: list[Wallpaper]) -> None:
        # Clear existing cards and layout items
        for card in self._cards:
            card.stop_loader()
        self._cards.clear()

        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        if not wallpapers:
            self._show_empty_state()
            return

        for idx, wp in enumerate(wallpapers):
            card = WallpaperCard(
                wallpaper=wp,
                parent=self._grid_container,
                thumbnail_path=self._thumbnail_path(wp),
            )
            card.set_wallpaper_requested.connect(self._on_apply_wallpaper)
            card.detail_requested.connect(self._on_show_detail)
            card.favorite_toggled.connect(self._on_fav_toggle)
            row = idx // _GRID_COLS
            col = idx % _GRID_COLS
            self._grid_layout.addWidget(card, row, col)
            self._cards.append(card)

    def _show_empty_state(self) -> None:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        box = QVBoxLayout(container)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.setSpacing(ds.SPACE_MD)

        icon = QLabel("♥")
        icon.setStyleSheet(f"color: {ds.TEXT_DISABLED}; font-size: 64px; background: transparent;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(icon)

        title = QLabel("No favorite wallpapers yet")
        title.setStyleSheet(
            f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL}px; font-weight: 700; background: transparent;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(title)

        sub = QLabel(
            "Click the heart icon on any wallpaper in the Library to save it here for fast access."
        )
        sub.setStyleSheet(
            f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_MD}px; background: transparent;"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(sub)

        btn = QPushButton("▦  Explore Library")
        btn.setObjectName("accent")
        btn.setFixedHeight(38)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ds.ACCENT_PRIMARY};
                color: {ds.TEXT_PRIMARY};
                border-radius: 8px;
                padding: 8px 24px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ds.ACCENT_LIGHT};
            }}
        """)
        btn.clicked.connect(lambda: self.navigate_to.emit("library"))
        box.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._grid_layout.addWidget(container, 0, 0, 1, _GRID_COLS)

    # ------------------------------------------------------------------
    # Actions & Signal Handlers
    # ------------------------------------------------------------------
    def _on_filter_changed(self) -> None:
        self.refresh()

    def _on_fav_toggle(self, wallpaper_id: int, is_fav: bool) -> None:
        self._history_service.set_favorite(wallpaper_id, is_fav)
        state_str = "added to" if is_fav else "removed from"
        self.status_message.emit(f"Wallpaper {state_str} favorites.")
        # Reload grid to reflect change
        self.refresh()

    def _on_show_detail(self, wallpaper_id: int) -> None:
        wp = self._wp_repo.get_by_id(wallpaper_id)
        if wp:
            # Track inspection in history
            self._history_service.record_view(wallpaper_id)
            dlg = DetailDialog(wallpaper=wp, parent=self)
            dlg.set_wallpaper_requested.connect(self._on_apply_wallpaper)
            dlg.favorite_toggled.connect(self._on_fav_toggle)
            dlg.exec()

    def _wallpaper_style(self) -> str:
        return str(self._config.get("wallpaper_style", "Fill")) if self._config else "Fill"

    def _thumbnail_path(self, wallpaper: Wallpaper) -> Path | None:
        if not self._config or not self._config.get("thumbnail_enabled", True) or not wallpaper.sha256:
            return None
        size = (self._config.get("thumbnail_width", 400), self._config.get("thumbnail_height", 225))
        quality = self._config.get("thumbnail_quality", 85)
        return thumbnail_cache_path(self._cache_dir / "thumbnails", wallpaper.sha256, size, quality)

    def _on_apply_wallpaper(self, wallpaper_id: int) -> None:
        try:
            result = self._wp_service.set_selected_wallpaper(wallpaper_id, style=self._wallpaper_style())
            if result.success:
                wp_title = result.wallpaper.title if result.wallpaper else "Wallpaper"
                self.status_message.emit(f"✓ Applied to desktop: {wp_title}")
                self.wallpaper_applied.emit(wallpaper_id)
            else:
                self.status_message.emit(f"✕ Could not apply wallpaper: {result.error}")
        except Exception as exc:
            self.status_message.emit(f"✕ Error applying wallpaper: {exc}")

    def _on_random_favorite(self) -> None:
        category = self._cat_combo.currentData() or None
        result = self._wp_service.set_random_wallpaper(
            category=category,
            favorites_only=True,
            style=self._wallpaper_style(),
        )
        if result.success:
            wp_title = result.wallpaper.title if result.wallpaper else "Unknown"
            self.status_message.emit(f"⚄ Random favorite applied: {wp_title}")
            self.wallpaper_applied.emit(result.wallpaper_id or 0)
        else:
            self.status_message.emit(f"⚄ {result.message}")

    def _on_clear_favorites(self) -> None:
        total = self._history_service.count_favorites()
        if total == 0:
            self.status_message.emit("Favorites is already empty.")
            return

        reply = QMessageBox.question(
            self,
            "Clear Favorites",
            f"Are you sure you want to remove all {total} wallpaper(s) from your favorites?\n\nThis will not delete any files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cleared = self._history_service.clear_all_favorites()
            self.status_message.emit(f"Cleared {cleared} wallpaper(s) from favorites.")
            self.refresh()
