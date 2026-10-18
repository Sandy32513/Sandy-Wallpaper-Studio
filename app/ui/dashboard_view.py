"""
Sandy Wallpaper Studio — Dashboard View
========================================
Shows at-a-glance library statistics, monitor info, quick action buttons,
and recently used wallpapers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.database.database import Database
from app.database.wallpaper_repository import WallpaperRepository
from app.services.library_service import LibraryService
from app.services.wallpaper_service import WindowsWallpaperService
from app.ui import design_system as ds
from app.ui.components.wallpaper_card import WallpaperCard


class StatCard(QFrame):
    """A small statistics card."""

    def __init__(
        self,
        label: str,
        value: str,
        icon: str = "",
        accent: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(90)
        border_color = ds.ACCENT_PRIMARY if accent else ds.BG_BORDER
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ds.BG_SURFACE};
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        if icon:
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"color: {ds.ACCENT_LIGHT}; font-size: 18px; background: transparent;")
            top.addWidget(icon_lbl)

        label_lbl = QLabel(label)
        label_lbl.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px; background: transparent;")
        top.addWidget(label_lbl)
        top.addStretch()
        layout.addLayout(top)

        val_lbl = QLabel(value)
        val_color = ds.ACCENT_LIGHT if accent else ds.TEXT_PRIMARY
        val_lbl.setStyleSheet(f"color: {val_color}; font-size: {ds.FONT_SIZE_2XL}px; font-weight: 700; background: transparent;")
        layout.addWidget(val_lbl)


class DashboardView(QWidget):
    """Dashboard: overview cards, monitor status, recent wallpapers, quick actions."""

    navigate_to = Signal(str)          # Request navigation to another view
    wallpaper_applied = Signal(int)    # Wallpaper ID just applied
    status_message = Signal(str)

    def __init__(
        self,
        db: Database,
        wallpaper_service: WindowsWallpaperService,
        cache_dir: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._wp_svc = wallpaper_service
        self._wp_repo = WallpaperRepository(db)
        self._lib_service = LibraryService(db, cache_dir=cache_dir)

        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- Title bar ----
        title_bar = QWidget()
        title_bar.setFixedHeight(56)
        title_bar.setStyleSheet(f"background-color: {ds.BG_SURFACE}; border-bottom: 1px solid {ds.BG_BORDER};")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(ds.SPACE_XL, 0, ds.SPACE_XL, 0)
        tb_layout.setSpacing(ds.SPACE_MD)
        title_lbl = QLabel("Dashboard")
        title_lbl.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL}px; font-weight: 700; background: transparent;")
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch()
        outer.addWidget(title_bar)

        # ---- Main scroll area ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {ds.BG_DEEP}; border: none;")

        content = QWidget()
        content.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(ds.SPACE_2XL, ds.SPACE_2XL, ds.SPACE_2XL, ds.SPACE_2XL)
        content_layout.setSpacing(ds.SPACE_2XL)

        # ---- Stats row ----
        stats = self._lib_service.get_statistics()
        monitors = self._wp_svc.detect_monitors()
        current_wallpaper = self._wp_svc.get_current_wallpaper()

        stats_grid = QGridLayout()
        stats_grid.setSpacing(ds.SPACE_MD)
        stat_cards = [
            ("Total Wallpapers", str(stats.total_wallpapers), "▦", True),
            ("Favorites",        str(stats.total_favorites),  "♥", False),
            ("Categories",       str(stats.categories_used),  "◈", False),
            ("Library Size",     f"{stats.total_size_mb:.1f} MB", "◎", False),
            ("Monitors",         str(len(monitors)),           "⊞", False),
            ("Resolution",       monitors[0].resolution if monitors else "—", "⧉", False),
        ]
        for i, (label, value, icon, accent) in enumerate(stat_cards):
            card = StatCard(label=label, value=value, icon=icon, accent=accent)
            stats_grid.addWidget(card, i // 3, i % 3)
        content_layout.addLayout(stats_grid)

        # ---- Quick actions ----
        actions_label = QLabel("Quick Actions")
        actions_label.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px; font-weight: 600; background: transparent;")
        content_layout.addWidget(actions_label)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(ds.SPACE_MD)
        quick_actions = [
            ("⊕  Import Folder",     "library"),
            ("⚄  Random Wallpaper",  "_random"),
            ("↺  Restore Previous",  "_restore"),
            ("▦  Browse Library",    "library"),
        ]
        for label, target in quick_actions:
            btn = QPushButton(label)
            btn.setFixedHeight(42)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if "Random" in label:
                btn.setObjectName("accent")
            btn.clicked.connect(lambda checked, t=target: self._quick_action(t))
            actions_row.addWidget(btn)
        content_layout.addLayout(actions_row)

        # ---- Current wallpaper status ----
        if current_wallpaper:
            cur_section = self._make_section("Current Desktop Wallpaper", current_wallpaper)
            content_layout.addWidget(cur_section)

        # ---- Monitor info ----
        monitor_label = QLabel("Monitors")
        monitor_label.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px; font-weight: 600; background: transparent;")
        content_layout.addWidget(monitor_label)

        mon_row = QHBoxLayout()
        mon_row.setSpacing(ds.SPACE_MD)
        for mon in monitors:
            card = self._make_monitor_card(mon)
            mon_row.addWidget(card)
        mon_row.addStretch()
        content_layout.addLayout(mon_row)

        # ---- Recent wallpapers ----
        recent = self._wp_repo.get_recently_used(limit=8)
        if recent:
            recent_label = QLabel("Recently Used")
            recent_label.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px; font-weight: 600; background: transparent;")
            content_layout.addWidget(recent_label)

            recent_row = QHBoxLayout()
            recent_row.setSpacing(ds.SPACE_MD)
            for wp in recent:
                card = WallpaperCard(wallpaper=wp)
                card.set_wallpaper_requested.connect(self._apply_wallpaper)
                card.detail_requested.connect(self._show_detail)
                card.favorite_toggled.connect(self._on_fav_toggle)
                recent_row.addWidget(card)
            recent_row.addStretch()
            content_layout.addLayout(recent_row)

        content_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _make_section(self, title: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {ds.BG_SURFACE};
                border: 1px solid {ds.BG_BORDER};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px; background: transparent;")
        layout.addWidget(t)
        v = QLabel(value)
        v.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_SM}px; background: transparent;")
        v.setWordWrap(True)
        layout.addWidget(v)
        return frame

    def _make_monitor_card(self, mon) -> QFrame:
        frame = QFrame()
        frame.setFixedSize(200, 110)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {ds.BG_SURFACE};
                border: 1px solid {"" + ds.ACCENT_PRIMARY if mon.is_primary else ds.BG_BORDER};
                border-radius: 8px;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)

        name_lbl = QLabel(mon.name + ("  [Primary]" if mon.is_primary else ""))
        name_lbl.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_SM}px; font-weight: 600; background: transparent;")
        layout.addWidget(name_lbl)

        res_lbl = QLabel(mon.resolution)
        res_lbl.setStyleSheet(f"color: {ds.ACCENT_LIGHT}; font-size: {ds.FONT_SIZE_MD}px; font-weight: 700; background: transparent;")
        layout.addWidget(res_lbl)

        orient_lbl = QLabel(f"{mon.orientation}  ·  {mon.aspect_ratio}")
        orient_lbl.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px; background: transparent;")
        layout.addWidget(orient_lbl)

        return frame

    def _quick_action(self, target: str) -> None:
        if target == "_random":
            result = self._wp_svc.set_random_wallpaper()
            if result.success:
                title = result.wallpaper.title if result.wallpaper else "Unknown"
                self.status_message.emit(f"⚄ Random wallpaper applied: {title}")
                self.wallpaper_applied.emit(result.wallpaper_id or 0)
            else:
                self.status_message.emit(f"⚄ {result.message}")
        elif target == "_restore":
            result = self._wp_svc.restore_previous_wallpaper()
            if result.success:
                self.status_message.emit("↺ Previous wallpaper restored.")
            else:
                self.status_message.emit(f"↺ {result.message}")
        else:
            self.navigate_to.emit(target)

    def _apply_wallpaper(self, wallpaper_id: int) -> None:
        try:
            result = self._wp_svc.set_selected_wallpaper(wallpaper_id, style="Fill")
            if result.success:
                title = result.wallpaper.title if result.wallpaper else "Unknown"
                self.status_message.emit(f"✓ Wallpaper applied: {title}")
                self.wallpaper_applied.emit(wallpaper_id)
            else:
                self.status_message.emit(f"✕ {result.error}")
        except Exception as exc:
            self.status_message.emit(f"✕ {exc}")

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
        from app.database.wallpaper_repository import WallpaperRepository
        self._wp_repo.set_favorite(wallpaper_id, is_fav)
        self.status_message.emit(f"{'♥' if is_fav else '♡'} Wallpaper {'favorited' if is_fav else 'unfavorited'}.")
