"""
Sandy Wallpaper Studio — Library View
======================================
Main content view showing the wallpaper grid with:
- Infinite-scroll-like lazy loading (page-based)
- Filter/search integration
- Wallpaper card grid
- Empty state
- Status bar updates
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, override

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.config import Config
from app.constants import DEFAULT_LIBRARY_DIR_NAME, THUMBNAIL_QUALITY, THUMBNAIL_SIZE
from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.database.models import Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.services.import_service import ImportService
from app.services.library_service import LibraryService
from app.services.wallpaper_service import WindowsWallpaperService
from app.ui import design_system as ds
from app.ui.components.import_dialog import ImportProgressDialog
from app.ui.components.search_bar import SearchFilterBar
from app.ui.components.wallpaper_card import WallpaperCard
from app.utils.image_utils import thumbnail_cache_path

_PAGE_SIZE = 40
_GRID_COLS = 4


class LibraryView(QWidget):
    """Main library view with search bar, wallpaper grid, and pagination.

    Signals:
        status_message: Text to show in main window status bar.
        wallpaper_applied: Emits wallpaper ID when a wallpaper is applied.
    """

    status_message = Signal(str)
    wallpaper_applied = Signal(int)

    def __init__(
        self,
        db: Database,
        wallpaper_service: WindowsWallpaperService,
        cache_dir: Optional[Path] = None,
        parent: Optional[QWidget] = None,
        config: Config | None = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._wp_service = wallpaper_service
        if cache_dir is None:
            cache_dir = Path.home() / "Pictures" / DEFAULT_LIBRARY_DIR_NAME / "Cache"
        self._cache_dir = cache_dir
        self._config = config
        self._thumbnail_size = (
            (config.get("thumbnail_width", THUMBNAIL_SIZE[0]), config.get("thumbnail_height", THUMBNAIL_SIZE[1]))
            if config else THUMBNAIL_SIZE
        )
        self._thumbnail_quality = config.get("thumbnail_quality", THUMBNAIL_QUALITY) if config else THUMBNAIL_QUALITY

        # Repositories
        self._wp_repo = WallpaperRepository(db)
        self._cat_repo = CategoryRepository(db)
        self._lib_service = LibraryService(db, cache_dir=self._cache_dir, config=config)
        self._import_service = ImportService(db, cache_dir=self._cache_dir, config=config)

        # State
        self._current_page = 0
        self._current_filters: dict = {}
        self._current_wallpapers: list[Wallpaper] = []
        self._cards: list[WallpaperCard] = []
        self._grid_columns = _GRID_COLS

        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- Top title bar ----
        title_bar = self._make_title_bar()
        layout.addWidget(title_bar)

        # ---- Search & filter bar ----
        categories = [c.name for c in self._cat_repo.get_all()]
        self._search_bar = SearchFilterBar(categories=categories)
        self._search_bar.search_changed.connect(self._on_filter_change)
        self._search_bar.import_requested.connect(self._on_import_folder)
        self._search_bar.random_requested.connect(self._on_random_wallpaper)
        layout.addWidget(self._search_bar)

        # ---- Scroll area for grid ----
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(f"background-color: {ds.BG_DEEP}; border: none;")
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL)
        self._grid_layout.setSpacing(ds.SPACE_LG)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._scroll.setWidget(self._grid_container)
        layout.addWidget(self._scroll)

        # ---- Bottom status bar ----
        self._status_bar = self._make_status_bar()
        layout.addWidget(self._status_bar)

        # Empty state (shown when no results)
        self._empty_state = self._make_empty_state()
        self._empty_state.hide()
        layout.addWidget(self._empty_state)

    def _make_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"background-color: {ds.BG_SURFACE}; border-bottom: 1px solid {ds.BG_BORDER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(ds.SPACE_XL, 0, ds.SPACE_XL, 0)
        layout.setSpacing(ds.SPACE_MD)

        title = QLabel("Library")
        title.setObjectName("title")
        title.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL}px; font-weight: 700; background: transparent;")
        layout.addWidget(title)

        self._count_badge = QLabel("0 wallpapers")
        self._count_badge.setObjectName("badge")
        layout.addWidget(self._count_badge)

        layout.addStretch()

        stats = self._lib_service.get_statistics()
        total_mb = round(stats.total_size_bytes / (1024 * 1024), 1) if stats.total_size_bytes else 0
        size_lbl = QLabel(f"  {stats.total_wallpapers} wallpapers  ·  {total_mb} MB")
        size_lbl.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px; background: transparent;")
        layout.addWidget(size_lbl)
        return bar

    def _make_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(28)
        bar.setStyleSheet(f"background-color: {ds.BG_SURFACE}; border-top: 1px solid {ds.BG_BORDER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(ds.SPACE_LG, 0, ds.SPACE_LG, 0)
        layout.setSpacing(ds.SPACE_SM)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px; background: transparent;")
        layout.addWidget(self._status_lbl)
        layout.addStretch()

        self._page_lbl = QLabel("")
        self._page_lbl.setStyleSheet(f"color: {ds.TEXT_DISABLED}; font-size: {ds.FONT_SIZE_XS}px; background: transparent;")
        layout.addWidget(self._page_lbl)
        return bar

    def _make_empty_state(self) -> QWidget:
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        widget.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("▦")
        icon_lbl.setStyleSheet(f"color: {ds.TEXT_DISABLED}; font-size: 64px; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        heading = QLabel("No wallpapers found")
        heading.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL}px; font-weight: 700; background: transparent;")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        sub = QLabel("Try a different search or import a folder with wallpapers.")
        sub.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_MD}px; background: transparent;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        import_btn = QPushButton("⊕  Import Folder")
        import_btn.setFixedSize(180, 38)
        import_btn.setObjectName("accent")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._on_import_folder)
        layout.addWidget(import_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return widget

    # ------------------------------------------------------------------
    # Data / Refresh
    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        self._current_page = 0
        self._load_page(reset=True)

    def _load_page(self, reset: bool = False) -> None:
        if self._config:
            self._thumbnail_size = (
                self._config.get("thumbnail_width", THUMBNAIL_SIZE[0]),
                self._config.get("thumbnail_height", THUMBNAIL_SIZE[1]),
            )
            self._thumbnail_quality = self._config.get("thumbnail_quality", THUMBNAIL_QUALITY)
        filters = self._current_filters
        query    = filters.get("query", "")
        category = filters.get("category", "")
        res      = filters.get("resolution", "")
        fav_only = filters.get("favorites_only", False)
        orientation = filters.get("orientation", "")

        min_w = min_h = None
        if orientation == "landscape":
            min_w, min_h = 1920, 1080
        elif orientation == "portrait":
            min_w, min_h = 1080, 1920

        results = self._lib_service.search(
            query=query,
            category=category or None,
            resolution_class=res or None,
            min_width=min_w,
            min_height=min_h,
            favorites_only=fav_only,
            limit=_PAGE_SIZE,
            offset=self._current_page * _PAGE_SIZE,
        )

        if reset:
            self._clear_grid()
            self._current_wallpapers = results
        else:
            self._current_wallpapers.extend(results)

        self._render_cards(results, reset=reset)
        total = self._wp_repo.count()
        shown = len(self._current_wallpapers)

        self._count_badge.setText(f"{shown} wallpapers")
        self._page_lbl.setText(f"Showing {shown} wallpapers")
        self._status_lbl.setText(f"{total} total in library")

        if not self._current_wallpapers:
            self._scroll.hide()
            self._empty_state.show()
        else:
            self._empty_state.hide()
            self._scroll.show()

    def _render_cards(self, wallpapers: list[Wallpaper], reset: bool) -> None:
        start_idx = 0 if reset else len(self._cards)

        for i, wp in enumerate(wallpapers):
            thumb_path = None
            if self._config and self._config.get("thumbnail_enabled", True) and wp.sha256:
                thumb_path = thumbnail_cache_path(
                    self._cache_dir / "thumbnails", wp.sha256,
                    self._thumbnail_size, self._thumbnail_quality,
                )
            card = WallpaperCard(wallpaper=wp, thumbnail_path=thumb_path)
            card.set_wallpaper_requested.connect(self._apply_wallpaper)
            card.detail_requested.connect(self._show_detail)
            card.favorite_toggled.connect(self._on_fav_toggle)

            index = start_idx + i
            row = index // self._grid_columns
            col = index % self._grid_columns
            self._grid_layout.addWidget(card, row, col)
            self._cards.append(card)

    @override
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_grid_columns)

    def _update_grid_columns(self) -> None:
        viewport_width = self._scroll.viewport().width()
        margins = self._grid_layout.contentsMargins()
        usable_width = max(1, viewport_width - margins.left() - margins.right())
        card_width = ds.CARD_WIDTH
        spacing = self._grid_layout.horizontalSpacing()
        columns = max(1, min(_GRID_COLS, (usable_width + spacing) // (card_width + spacing)))
        if columns != self._grid_columns:
            self._grid_columns = columns
            self._reflow_cards()

    def _reflow_cards(self) -> None:
        while self._grid_layout.count():
            self._grid_layout.takeAt(0)
        for index, card in enumerate(self._cards):
            self._grid_layout.addWidget(
                card, index // self._grid_columns, index % self._grid_columns
            )

    def _clear_grid(self) -> None:
        for card in self._cards:
            card.hide()
            card.deleteLater()
        self._cards.clear()
        # Clear layout items
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    # ------------------------------------------------------------------
    # Signals / Event Handlers
    # ------------------------------------------------------------------
    def _on_filter_change(self, filters: dict) -> None:
        self._current_filters = filters
        self._refresh()

    def _on_scroll(self, value: int) -> None:
        """Load next page when near the bottom of the scroll area."""
        scrollbar = self._scroll.verticalScrollBar()
        if value >= scrollbar.maximum() * 0.85 and self._cards:
            self._current_page += 1
            self._load_page(reset=False)

    def _apply_wallpaper(self, wallpaper_id: int) -> None:
        try:
            style = str(self._config.get("wallpaper_style", "Fill")) if self._config else "Fill"
            result = self._wp_service.set_selected_wallpaper(wallpaper_id, style=style)
            if result.success:
                self.status_message.emit(f"✓ Wallpaper applied: {result.wallpaper.title if result.wallpaper else 'Unknown'}")
                self.wallpaper_applied.emit(wallpaper_id)
            else:
                self.status_message.emit(f"✕ Could not apply wallpaper: {result.error}")
        except Exception as exc:
            self.status_message.emit(f"✕ Error: {exc}")

    def _show_detail(self, wallpaper_id: int) -> None:
        wp = self._wp_repo.get_by_id(wallpaper_id)
        if wp:
            from app.database.view_repository import ViewRepository
            ViewRepository(self._db).record_view(wallpaper_id)
            from app.ui.components.detail_dialog import DetailDialog
            dlg = DetailDialog(wallpaper=wp, parent=self)
            dlg.set_wallpaper_requested.connect(self._apply_wallpaper)
            dlg.favorite_toggled.connect(self._on_fav_toggle)
            dlg.exec()

    def _on_fav_toggle(self, wallpaper_id: int, is_fav: bool) -> None:
        self._wp_repo.set_favorite(wallpaper_id, is_fav)
        state = "favorited" if is_fav else "unfavorited"
        self.status_message.emit(f"{'♥' if is_fav else '♡'} Wallpaper {state}.")

    def _on_import_folder(self) -> None:
        if self._config:
            self._import_service = ImportService(
                self._db, cache_dir=self._cache_dir, config=self._config
            )
        initial_directory = (
            self._config.library_path
            if self._config and self._config.library_path.is_dir()
            else Path.home() / "Pictures"
        )
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Import",
            str(initial_directory),
        )
        if not folder:
            return
        dlg = ImportProgressDialog(
            folder_path=Path(folder),
            import_service=self._import_service,
            recursive=bool(self._config.get("recursive_import", False)) if self._config else False,
            parent=self,
        )
        dlg.import_finished.connect(self._on_import_done)
        dlg.exec()
        dlg.start_import()

    def _on_import_done(self, summary: dict) -> None:
        imported = summary.get("imported", 0)
        self.status_message.emit(
            f"✓ Import complete: {imported} wallpapers added."
        )
        self._refresh()

    def _on_random_wallpaper(self) -> None:
        filters = self._current_filters
        result = self._wp_service.set_random_wallpaper(
            category=filters.get("category") or None,
            favorites_only=filters.get("favorites_only", False),
            style=str(self._config.get("wallpaper_style", "Fill")) if self._config else "Fill",
        )
        if result.success:
            title = result.wallpaper.title if result.wallpaper else "Unknown"
            self.status_message.emit(f"⚄ Random wallpaper applied: {title}")
            self.wallpaper_applied.emit(result.wallpaper_id or 0)
        else:
            self.status_message.emit(f"⚄ {result.message}")


# Make QHBoxLayout accessible without importing QHBoxLayout directly in _make_title_bar
from PySide6.QtWidgets import QHBoxLayout as QHBoxLayout  # noqa: E402
