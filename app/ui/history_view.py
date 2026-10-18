"""
Sandy Wallpaper Studio — History & Recent View
===============================================
Dedicated view tracking:
1. Desktop Applied History (with direct reapply and restore workflows)
2. Recently Viewed / Inspected Wallpapers
3. Recently Downloaded / Imported Wallpapers
4. Automatic Rotation Events
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.constants import DEFAULT_LIBRARY_DIR_NAME
from app.database.database import Database
from app.database.models import Wallpaper, WallpaperHistory
from app.database.wallpaper_repository import WallpaperRepository
from app.services.history_service import HistoryService
from app.services.wallpaper_service import WindowsWallpaperService
from app.ui import design_system as ds
from app.ui.components.detail_dialog import DetailDialog
from app.ui.components.wallpaper_card import WallpaperCard

logger = logging.getLogger(__name__)

_GRID_COLS = 4


def _format_relative_time(iso_str: str | None) -> str:
    """Format an ISO-8601 string into human-friendly relative time."""
    if not iso_str:
        return "Unknown"
    try:
        # Strip trailing Z or +00:00 for simple parsing if needed
        clean_str = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        diff = now - dt

        seconds = int(diff.total_seconds())
        if seconds < 0:
            return "Just now"
        if seconds < 60:
            return "Just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} min{'s' if minutes != 1 else ''} ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = hours // 24
        if days == 1:
            return f"Yesterday at {dt.strftime('%H:%M')}"
        if days < 7:
            return f"{days} days ago"
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(iso_str)[:19]


class HistoryItemRow(QFrame):
    """A card row representing an applied wallpaper history event."""

    reapply_requested = Signal(int)
    detail_requested = Signal(int)

    def __init__(
        self,
        history: WallpaperHistory,
        wallpaper: Wallpaper | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._history = history
        self._wallpaper = wallpaper

        self.setFixedHeight(84)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ds.BG_SURFACE};
                border: 1px solid {ds.BG_BORDER};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: {ds.ACCENT_PRIMARY};
                background-color: {ds.BG_ELEVATED};
            }}
        """)

        self._build_ui()

    def _build_ui(self) -> None:
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(16)

        # Icon / status badge
        icon_lbl = QLabel("🖥")
        icon_lbl.setStyleSheet(
            f"font-size: 24px; color: {ds.ACCENT_LIGHT}; background: transparent;"
        )
        h.addWidget(icon_lbl)

        # Wallpaper Info Column
        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        info_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title = (
            self._wallpaper.title
            if self._wallpaper and self._wallpaper.title
            else (
                self._wallpaper.filename
                if self._wallpaper
                else f"Wallpaper #{self._history.wallpaper_id}"
            )
        )
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"""
            color: {ds.TEXT_PRIMARY};
            font-size: {ds.FONT_SIZE_MD}px;
            font-weight: 600;
            background: transparent;
        """)
        info_col.addWidget(title_lbl)

        # Meta row: Category, Resolution, Monitor
        meta_parts = []
        if self._wallpaper:
            if self._wallpaper.category:
                meta_parts.append(self._wallpaper.category)
            if self._wallpaper.resolution_label and self._wallpaper.width > 0:
                meta_parts.append(self._wallpaper.resolution_label)
        meta_parts.append("Automatic rotation" if self._history.source == "rotation" else "Manual")
        monitor_str = self._history.monitor or "Primary Display"
        meta_parts.append(f"Monitor: {monitor_str}")
        if not self._history.success and self._history.error_message:
            meta_parts.append(f"Failed: {self._history.error_message[:100]}")

        meta_lbl = QLabel(" • ".join(meta_parts))
        meta_lbl.setToolTip(self._history.error_message)
        meta_lbl.setStyleSheet(
            f"color: {ds.DANGER if not self._history.success else ds.TEXT_SECONDARY}; "
            f"font-size: {ds.FONT_SIZE_SM}px; background: transparent;"
        )
        info_col.addWidget(meta_lbl)

        h.addLayout(info_col, stretch=1)

        # Applied Timestamp Column
        time_col = QVBoxLayout()
        time_col.setSpacing(2)
        time_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        rel_time = _format_relative_time(self._history.set_at)
        rel_lbl = QLabel(rel_time)
        rel_lbl.setStyleSheet(
            f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_SM}px; "
            f"font-weight: 600; background: transparent;"
        )
        rel_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_col.addWidget(rel_lbl)

        exact_str = str(self._history.set_at or "")[:19]
        exact_lbl = QLabel(exact_str)
        exact_lbl.setStyleSheet(
            f"color: {ds.TEXT_DISABLED}; font-size: {ds.FONT_SIZE_XS}px; background: transparent;"
        )
        exact_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_col.addWidget(exact_lbl)

        h.addLayout(time_col)

        # Actions
        btn_details = QPushButton("ℹ  Details")
        btn_details.setFixedHeight(32)
        btn_details.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_details.setStyleSheet(f"""
            QPushButton {{
                background-color: {ds.BG_INPUT};
                color: {ds.TEXT_SECONDARY};
                border: 1px solid {ds.BG_BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: {ds.FONT_SIZE_SM}px;
            }}
            QPushButton:hover {{
                background-color: {ds.BG_BORDER};
                color: {ds.TEXT_PRIMARY};
            }}
        """)
        btn_details.clicked.connect(lambda: self.detail_requested.emit(self._history.wallpaper_id))
        h.addWidget(btn_details)

        btn_reapply = QPushButton("⚡  Reapply")
        btn_reapply.setObjectName("accent")
        btn_reapply.setFixedHeight(32)
        btn_reapply.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reapply.setStyleSheet(f"""
            QPushButton {{
                background-color: {ds.ACCENT_PRIMARY};
                color: {ds.TEXT_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 600;
                font-size: {ds.FONT_SIZE_SM}px;
            }}
            QPushButton:hover {{
                background-color: {ds.ACCENT_LIGHT};
            }}
        """)
        btn_reapply.clicked.connect(lambda: self.reapply_requested.emit(self._history.wallpaper_id))
        h.addWidget(btn_reapply)
        if not self._history.success:
            btn_reapply.hide()


class HistoryView(QWidget):
    """Multi-tab history view for desktop applications, viewed wallpapers, and downloads."""

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
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._wp_service = wallpaper_service
        self._history_service = history_service or HistoryService(
            db=db,
            wallpaper_service=wallpaper_service,
        )
        self._wp_repo = WallpaperRepository(db)

        if cache_dir is None:
            cache_dir = Path.home() / "Pictures" / DEFAULT_LIBRARY_DIR_NAME / "Cache"
        self._cache_dir = cache_dir

        self._active_tab = 0  # Applied, Viewed, Downloaded, Rotation Events
        self._viewed_cards: list[WallpaperCard] = []
        self._downloaded_cards: list[WallpaperCard] = []

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header Bar
        header = self._make_header_bar()
        layout.addWidget(header)

        # Tab Navigation Bar
        tab_bar = self._make_tab_bar()
        layout.addWidget(tab_bar)

        # Stacked Widget for Tab Content
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background-color: {ds.BG_DEEP};")

        # Tab 0: Desktop Applied History (List)
        self._applied_page = self._make_applied_page()
        self._stack.addWidget(self._applied_page)

        # Tab 1: Recently Viewed (Grid)
        self._viewed_page = self._make_viewed_page()
        self._stack.addWidget(self._viewed_page)

        # Tab 2: Recently Downloaded / Imported (Grid)
        self._downloaded_page = self._make_downloaded_page()
        self._stack.addWidget(self._downloaded_page)

        # Tab 3: Automatic Rotation Events
        self._rotation_page = self._make_rotation_page()
        self._stack.addWidget(self._rotation_page)

        layout.addWidget(self._stack, stretch=1)

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

        title_lbl = QLabel("↺  History & Recent")
        title_lbl.setStyleSheet(f"""
            color: {ds.TEXT_PRIMARY};
            font-size: {ds.FONT_SIZE_XL}px;
            font-weight: 700;
            background: transparent;
        """)
        h.addWidget(title_lbl)

        sub_lbl = QLabel("Track desktop background applications, viewed wallpapers, and downloads")
        sub_lbl.setStyleSheet(
            f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px; background: transparent;"
        )
        h.addWidget(sub_lbl)

        h.addStretch()

        # Restore Previous Wallpaper button
        self._btn_restore = QPushButton("↺  Restore Previous Wallpaper")
        self._btn_restore.setFixedHeight(34)
        self._btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_restore.setToolTip(
            "Restore the desktop background applied prior to the current wallpaper"
        )
        self._btn_restore.setStyleSheet(f"""
            QPushButton {{
                background-color: {ds.BG_ELEVATED};
                color: {ds.ACCENT_LIGHT};
                border: 1px solid {ds.ACCENT_PRIMARY};
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 600;
                font-size: {ds.FONT_SIZE_SM}px;
            }}
            QPushButton:hover {{
                background-color: {ds.ACCENT_PRIMARY};
                color: {ds.TEXT_PRIMARY};
            }}
        """)
        self._btn_restore.clicked.connect(self._on_restore_previous)
        h.addWidget(self._btn_restore)

        # Clear History button
        self._btn_clear = QPushButton("🗑  Clear History")
        self._btn_clear.setFixedHeight(34)
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self._btn_clear.clicked.connect(self._on_clear_history)
        h.addWidget(self._btn_clear)

        return bar

    def _make_tab_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(50)
        bar.setStyleSheet(f"""
            QWidget {{
                background-color: {ds.BG_SURFACE};
                border-bottom: 1px solid {ds.BG_BORDER};
            }}
        """)
        h = QHBoxLayout(bar)
        h.setContentsMargins(ds.SPACE_XL, 0, ds.SPACE_XL, 0)
        h.setSpacing(ds.SPACE_MD)

        self._tab_btn_group = QButtonGroup(self)

        self._btn_tab_applied = QPushButton("🖥  Desktop Applied (0)")
        self._btn_tab_viewed = QPushButton("👁  Recently Viewed (0)")
        self._btn_tab_downloaded = QPushButton("⬇  Recently Downloaded (0)")
        self._btn_tab_rotation = QPushButton("↻  Rotation Events (0)")

        tabs = [
            (self._btn_tab_applied, 0),
            (self._btn_tab_viewed, 1),
            (self._btn_tab_downloaded, 2),
            (self._btn_tab_rotation, 3),
        ]

        for btn, idx in tabs:
            btn.setCheckable(True)
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._tab_btn_group.addButton(btn, idx)
            h.addWidget(btn)

        self._tab_btn_group.idClicked.connect(self._switch_tab)
        self._btn_tab_applied.setChecked(True)
        self._update_tab_button_styles()

        h.addStretch()
        return bar

    def _update_tab_button_styles(self) -> None:
        tabs = [
            self._btn_tab_applied,
            self._btn_tab_viewed,
            self._btn_tab_downloaded,
            self._btn_tab_rotation,
        ]
        for idx, btn in enumerate(tabs):
            is_active = idx == self._active_tab
            bg = ds.ACCENT_PRIMARY if is_active else ds.BG_INPUT
            color = ds.TEXT_PRIMARY if is_active else ds.TEXT_SECONDARY
            border = f"1px solid {ds.ACCENT_PRIMARY}" if is_active else f"1px solid {ds.BG_BORDER}"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {color};
                    border: {border};
                    border-radius: 6px;
                    padding: 4px 14px;
                    font-weight: {"700" if is_active else "500"};
                    font-size: {ds.FONT_SIZE_SM}px;
                }}
                QPushButton:hover {{
                    background-color: {ds.ACCENT_DARK if is_active else ds.BG_ELEVATED};
                    color: {ds.TEXT_PRIMARY};
                }}
            """)

    def _make_applied_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {ds.BG_DEEP}; border: none;")

        self._applied_container = QWidget()
        self._applied_container.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        self._applied_layout = QVBoxLayout(self._applied_container)
        self._applied_layout.setContentsMargins(ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL)
        self._applied_layout.setSpacing(ds.SPACE_MD)
        self._applied_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._applied_container)
        return scroll

    def _make_viewed_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {ds.BG_DEEP}; border: none;")

        self._viewed_container = QWidget()
        self._viewed_container.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        self._viewed_layout = QGridLayout(self._viewed_container)
        self._viewed_layout.setContentsMargins(ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL)
        self._viewed_layout.setSpacing(ds.SPACE_LG)
        self._viewed_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self._viewed_container)
        return scroll

    def _make_downloaded_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {ds.BG_DEEP}; border: none;")

        self._downloaded_container = QWidget()
        self._downloaded_container.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        self._downloaded_layout = QGridLayout(self._downloaded_container)
        self._downloaded_layout.setContentsMargins(
            ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL
        )
        self._downloaded_layout.setSpacing(ds.SPACE_LG)
        self._downloaded_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self._downloaded_container)
        return scroll

    def _make_rotation_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {ds.BG_DEEP}; border: none;")

        self._rotation_container = QWidget()
        self._rotation_container.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        self._rotation_layout = QVBoxLayout(self._rotation_container)
        self._rotation_layout.setContentsMargins(
            ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL
        )
        self._rotation_layout.setSpacing(ds.SPACE_MD)
        self._rotation_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._rotation_container)
        return scroll

    # ------------------------------------------------------------------
    # Data Loading & Rendering
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload data for the active tab and update counts."""
        applied_count = self._history_service.count_applied()
        viewed_count = self._history_service.count_distinct_viewed_wallpapers()
        downloaded = self._history_service.get_recently_downloaded(limit=100)
        downloaded_count = len(downloaded)
        rotation_events = self._history_service.get_recent_rotation_events(limit=100)

        self._btn_tab_applied.setText(f"🖥  Desktop Applied ({applied_count})")
        self._btn_tab_viewed.setText(f"👁  Recently Viewed ({viewed_count})")
        self._btn_tab_downloaded.setText(f"⬇  Recently Downloaded ({downloaded_count})")
        self._btn_tab_rotation.setText(f"↻  Rotation Events ({len(rotation_events)})")

        if self._active_tab == 0:
            self._load_applied_tab()
        elif self._active_tab == 1:
            self._load_viewed_tab()
        elif self._active_tab == 2:
            self._load_downloaded_tab(downloaded)
        elif self._active_tab == 3:
            self._load_rotation_tab(rotation_events)

    def _load_applied_tab(self) -> None:
        # Clear layout
        while self._applied_layout.count():
            item = self._applied_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()

        items = self._history_service.get_recently_applied(limit=100)
        if not items:
            self._show_empty_state(
                self._applied_layout,
                icon="🖥",
                title="No wallpaper history yet",
                message=(
                    "When you set wallpapers on your desktop, they will be logged here "
                    "with timestamps and quick reapply shortcuts."
                ),
                button_text="▦  Browse Library",
                button_nav="library",
            )
            return

        for hist, wp in items:
            row = HistoryItemRow(history=hist, wallpaper=wp, parent=self._applied_container)
            row.reapply_requested.connect(self._on_reapply_wallpaper)
            row.detail_requested.connect(self._on_show_detail)
            self._applied_layout.addWidget(row)

    def _load_rotation_tab(
        self, events: list[tuple[WallpaperHistory, Wallpaper | None]]
    ) -> None:
        while self._rotation_layout.count():
            item = self._rotation_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not events:
            self._show_empty_state(
                self._rotation_layout,
                icon="↻",
                title="No automatic rotation events yet",
                message="Successful changes and failed rotation attempts will appear here.",
                button_text="Open Rotation Settings",
                button_nav="settings",
            )
            return
        for history, wallpaper in events:
            row = HistoryItemRow(
                history=history,
                wallpaper=wallpaper,
                parent=self._rotation_container,
            )
            row.reapply_requested.connect(self._on_reapply_wallpaper)
            row.detail_requested.connect(self._on_show_detail)
            self._rotation_layout.addWidget(row)

    def _load_viewed_tab(self) -> None:
        for card in self._viewed_cards:
            card.stop_loader()
        self._viewed_cards.clear()

        while self._viewed_layout.count():
            item = self._viewed_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()

        wallpapers = self._history_service.get_recently_viewed(limit=100)
        if not wallpapers:
            self._show_grid_empty_state(
                self._viewed_layout,
                icon="👁",
                title="No viewed wallpapers yet",
                message=(
                    "Wallpapers you inspect or view in detail will appear here for fast reference."
                ),
            )
            return

        for idx, wp in enumerate(wallpapers):
            card = WallpaperCard(wallpaper=wp, parent=self._viewed_container)
            card.set_wallpaper_requested.connect(self._on_reapply_wallpaper)
            card.detail_requested.connect(self._on_show_detail)
            card.favorite_toggled.connect(self._on_fav_toggle)
            row = idx // _GRID_COLS
            col = idx % _GRID_COLS
            self._viewed_layout.addWidget(card, row, col)
            self._viewed_cards.append(card)

    def _load_downloaded_tab(self, wallpapers: list[Wallpaper] | None = None) -> None:
        for card in self._downloaded_cards:
            card.stop_loader()
        self._downloaded_cards.clear()

        while self._downloaded_layout.count():
            item = self._downloaded_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if wallpapers is None:
            wallpapers = self._history_service.get_recently_downloaded(limit=100)

        if not wallpapers:
            self._show_grid_empty_state(
                self._downloaded_layout,
                icon="⬇",
                title="No downloaded wallpapers yet",
                message=(
                    "Wallpapers downloaded from sources or imported from local folders "
                    "will show up here."
                ),
            )
            return

        for idx, wp in enumerate(wallpapers):
            card = WallpaperCard(wallpaper=wp, parent=self._downloaded_container)
            card.set_wallpaper_requested.connect(self._on_reapply_wallpaper)
            card.detail_requested.connect(self._on_show_detail)
            card.favorite_toggled.connect(self._on_fav_toggle)
            row = idx // _GRID_COLS
            col = idx % _GRID_COLS
            self._downloaded_layout.addWidget(card, row, col)
            self._downloaded_cards.append(card)

    def _show_empty_state(
        self,
        layout: QVBoxLayout,
        icon: str,
        title: str,
        message: str,
        button_text: str,
        button_nav: str,
    ) -> None:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        box = QVBoxLayout(container)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.setSpacing(ds.SPACE_MD)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            f"color: {ds.TEXT_DISABLED}; font-size: 64px; background: transparent;"
        )
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL}px; "
            f"font-weight: 700; background: transparent;"
        )
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(title_lbl)

        sub_lbl = QLabel(message)
        sub_lbl.setStyleSheet(
            f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_MD}px; background: transparent;"
        )
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(sub_lbl)

        btn = QPushButton(button_text)
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
        btn.clicked.connect(lambda: self.navigate_to.emit(button_nav))
        box.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(container)

    def _show_grid_empty_state(
        self,
        layout: QGridLayout,
        icon: str,
        title: str,
        message: str,
    ) -> None:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        box = QVBoxLayout(container)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.setSpacing(ds.SPACE_MD)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            f"color: {ds.TEXT_DISABLED}; font-size: 64px; background: transparent;"
        )
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL}px; "
            f"font-weight: 700; background: transparent;"
        )
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(title_lbl)

        sub_lbl = QLabel(message)
        sub_lbl.setStyleSheet(
            f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_MD}px; background: transparent;"
        )
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(sub_lbl)

        layout.addWidget(container, 0, 0, 1, _GRID_COLS)

    # ------------------------------------------------------------------
    # Actions & Handlers
    # ------------------------------------------------------------------
    def _switch_tab(self, tab_id: int) -> None:
        self._active_tab = tab_id
        self._stack.setCurrentIndex(tab_id)
        self._update_tab_button_styles()
        self.refresh()

    def _on_reapply_wallpaper(self, wallpaper_id: int) -> None:
        try:
            result = self._history_service.reapply_wallpaper(wallpaper_id, style="Fill")
            if result.success:
                wp_title = result.wallpaper.title if result.wallpaper else "Wallpaper"
                self.status_message.emit(f"✓ Reapplied to desktop: {wp_title}")
                self.wallpaper_applied.emit(wallpaper_id)
                self.refresh()
            else:
                self.status_message.emit(f"✕ Could not reapply wallpaper: {result.error}")
        except Exception as exc:
            self.status_message.emit(f"✕ Error reapplying wallpaper: {exc}")

    def _on_restore_previous(self) -> None:
        try:
            result = self._history_service.restore_previous_wallpaper()
            if result.success:
                wp_title = result.wallpaper.title if result.wallpaper else "Previous wallpaper"
                self.status_message.emit(f"↺ Restored previous wallpaper: {wp_title}")
                self.wallpaper_applied.emit(result.wallpaper_id or 0)
                self.refresh()
            else:
                self.status_message.emit(
                    f"✕ Could not restore previous wallpaper: {result.error or result.message}"
                )
        except Exception as exc:
            self.status_message.emit(f"✕ Error restoring previous wallpaper: {exc}")

    def _on_clear_history(self) -> None:
        tab_names = [
            "Desktop Applied History",
            "View History",
            "Downloaded History",
            "Rotation Events",
        ]
        active_name = (
            tab_names[self._active_tab] if self._active_tab < len(tab_names) else "History"
        )

        if self._active_tab == 2:
            self.status_message.emit(
                "Downloaded wallpapers cannot be cleared from this tab (use library manager)."
            )
            return

        msg = (
            f"Are you sure you want to clear your {active_name.lower()}?\n\n"
            "This will not delete any wallpaper files."
        )
        reply = QMessageBox.question(
            self,
            f"Clear {active_name}",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._active_tab == 0:
                cleared = self._history_service.clear_applied_history()
            elif self._active_tab == 3:
                cleared = self._history_service.clear_rotation_events()
            else:
                cleared = self._history_service.clear_view_history()
            self.status_message.emit(f"Cleared {cleared} entries from {active_name.lower()}.")
            self.refresh()

    def _on_show_detail(self, wallpaper_id: int) -> None:
        wp = self._wp_repo.get_by_id(wallpaper_id)
        if wp:
            self._history_service.record_view(wallpaper_id)
            dlg = DetailDialog(wallpaper=wp, parent=self)
            dlg.set_wallpaper_requested.connect(self._on_reapply_wallpaper)
            dlg.favorite_toggled.connect(self._on_fav_toggle)
            dlg.exec()

    def _on_fav_toggle(self, wallpaper_id: int, is_fav: bool) -> None:
        self._history_service.set_favorite(wallpaper_id, is_fav)
        state_str = "favorited" if is_fav else "unfavorited"
        self.status_message.emit(f"{'♥' if is_fav else '♡'} Wallpaper {state_str}.")
        self.refresh()
