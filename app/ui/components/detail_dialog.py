"""
Sandy Wallpaper Studio — Wallpaper Detail Dialog
=================================================
Full-width modal showing large preview, all metadata,
and action buttons: Set Wallpaper, Preview, Favorite, Open File, Open Source, Find Similar.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Wallpaper
from app.ui import design_system as ds
from app.ui.components.wallpaper_card import _placeholder_pixmap


class DetailDialog(QDialog):
    """Full wallpaper detail modal.

    Signals:
        set_wallpaper_requested: Emits wallpaper ID when Set Wallpaper is clicked.
        favorite_toggled: Emits (wallpaper_id, new_state).
        find_similar_requested: Emits wallpaper ID to find similar images.
    """

    set_wallpaper_requested = Signal(int)
    favorite_toggled = Signal(int, bool)
    find_similar_requested = Signal(int)

    def __init__(
        self,
        wallpaper: Wallpaper,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._wallpaper = wallpaper
        self._is_fav = wallpaper.favorite

        self.setWindowTitle(f"Sandy Wallpaper Studio — {wallpaper.title or wallpaper.filename}")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ds.BG_DEEP};
            }}
        """)

        self._build_ui()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ============================================================
        # Left: large preview
        # ============================================================
        preview_panel = QWidget()
        preview_panel.setMinimumWidth(500)
        preview_panel.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        prev_layout = QVBoxLayout(preview_panel)
        prev_layout.setContentsMargins(0, 0, 0, 0)
        prev_layout.setSpacing(0)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._load_preview_image()
        prev_layout.addWidget(self._preview_label)

        # Action buttons underneath preview
        action_bar = QWidget()
        action_bar.setFixedHeight(54)
        action_bar.setStyleSheet(f"background-color: {ds.BG_SURFACE}; border-top: 1px solid {ds.BG_BORDER};")
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(16, 0, 16, 0)
        action_layout.setSpacing(8)

        set_btn = QPushButton("⊞  Set as Wallpaper")
        set_btn.setObjectName("accent")
        set_btn.setFixedHeight(36)
        set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_btn.clicked.connect(lambda: self.set_wallpaper_requested.emit(self._wallpaper.id or 0))
        action_layout.addWidget(set_btn)

        self._fav_btn = QPushButton()
        self._fav_btn.setFixedHeight(36)
        self._fav_btn.setFixedWidth(36)
        self._fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fav_btn.setToolTip("Toggle favorite")
        self._fav_btn.clicked.connect(self._on_fav_click)
        self._update_fav_button()
        action_layout.addWidget(self._fav_btn)

        if self._wallpaper.path and Path(self._wallpaper.path).exists():
            open_btn = QPushButton("📂  Open File")
            open_btn.setFixedHeight(36)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(self._open_file)
            action_layout.addWidget(open_btn)

        if self._wallpaper.source_url:
            src_btn = QPushButton("🌐  Source")
            src_btn.setFixedHeight(36)
            src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            src_btn.clicked.connect(self._open_source_url)
            action_layout.addWidget(src_btn)

        sim_btn = QPushButton("≈  Find Similar")
        sim_btn.setFixedHeight(36)
        sim_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sim_btn.clicked.connect(lambda: self.find_similar_requested.emit(self._wallpaper.id or 0))
        action_layout.addWidget(sim_btn)

        action_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("ghost")
        close_btn.setFixedSize(36, 36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        action_layout.addWidget(close_btn)

        prev_layout.addWidget(action_bar)
        outer.addWidget(preview_panel, stretch=3)

        # ============================================================
        # Right: metadata panel
        # ============================================================
        meta_panel = QWidget()
        meta_panel.setFixedWidth(340)
        meta_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {ds.BG_SURFACE};
                border-left: 1px solid {ds.BG_BORDER};
            }}
        """)
        meta_outer = QVBoxLayout(meta_panel)
        meta_outer.setContentsMargins(0, 0, 0, 0)
        meta_outer.setSpacing(0)

        # Title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet(f"background-color: {ds.BG_ELEVATED}; border-bottom: 1px solid {ds.BG_BORDER};")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(16, 0, 16, 0)

        title_lbl = QLabel(self._wallpaper.title or self._wallpaper.filename or "Untitled")
        title_lbl.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_LG}px; font-weight: 700;")
        title_lbl.setWordWrap(True)
        tb_layout.addWidget(title_lbl)

        meta_outer.addWidget(title_bar)

        # Scrollable metadata fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {ds.BG_SURFACE}; border: none;")

        fields_widget = QWidget()
        fields_widget.setStyleSheet(f"background-color: {ds.BG_SURFACE};")
        fields_layout = QVBoxLayout(fields_widget)
        fields_layout.setContentsMargins(16, 16, 16, 16)
        fields_layout.setSpacing(2)

        wp = self._wallpaper
        rows = [
            ("Resolution", f"{wp.width} × {wp.height}" if wp.width else "—"),
            ("Class", wp.resolution_class or "—"),
            ("Aspect Ratio", wp.aspect_ratio or "—"),
            ("Format", Path(wp.filename).suffix.upper().lstrip(".") if wp.filename else "—"),
            ("File Size", f"{wp.file_size_mb:.1f} MB" if wp.file_size else "—"),
            ("Category", wp.category or "—"),
            ("Tags", wp.tags or "—"),
            ("Source", wp.source or "—"),
            ("Author", wp.author or "—"),
            ("License", wp.license or "—"),
            ("Downloaded", _fmt_date(wp.download_date)),
            ("Last Used", _fmt_date(wp.last_used)),
            ("Usage Count", str(wp.usage_count)),
            ("Favorite", "Yes" if wp.favorite else "No"),
            ("SHA-256", (wp.sha256[:16] + "…") if wp.sha256 else "—"),
            ("pHash", wp.phash or "—"),
        ]
        for key, value in rows:
            fields_layout.addWidget(self._make_row(key, value))
        fields_layout.addStretch()

        scroll.setWidget(fields_widget)
        meta_outer.addWidget(scroll)
        outer.addWidget(meta_panel, stretch=0)

    def _load_preview_image(self) -> None:
        path = self._wallpaper.path
        if path and Path(path).is_file():
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self._preview_label.setPixmap(
                    pixmap.scaled(
                        QSize(900, 600),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self._preview_label.setPixmap(_placeholder_pixmap(500, 400))

    def _make_row(self, key: str, value: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background-color: transparent;")
        row.setFixedHeight(30)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        key_lbl = QLabel(key)
        key_lbl.setFixedWidth(110)
        key_lbl.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px;")
        layout.addWidget(key_lbl)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_SM}px;")
        val_lbl.setWordWrap(False)
        layout.addWidget(val_lbl)
        layout.addStretch()
        return row

    def _on_fav_click(self) -> None:
        self._is_fav = not self._is_fav
        self._update_fav_button()
        self.favorite_toggled.emit(self._wallpaper.id or 0, self._is_fav)

    def _update_fav_button(self) -> None:
        if self._is_fav:
            self._fav_btn.setText("♥")
            self._fav_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(239, 68, 68, 0.15);
                    border: 1px solid {ds.DANGER};
                    color: {ds.DANGER};
                    border-radius: 6px;
                }}
                QPushButton:hover {{ background-color: {ds.DANGER}; color: white; }}
            """)
        else:
            self._fav_btn.setText("♡")
            self._fav_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {ds.BG_BORDER};
                    color: {ds.TEXT_SECONDARY};
                    border-radius: 6px;
                }}
                QPushButton:hover {{ border-color: {ds.DANGER}; color: {ds.DANGER}; }}
            """)

    def _open_file(self) -> None:
        if self._wallpaper.path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._wallpaper.path).parent)))

    def _open_source_url(self) -> None:
        if self._wallpaper.source_url:
            QDesktopServices.openUrl(QUrl(self._wallpaper.source_url))


def _fmt_date(raw: Optional[str]) -> str:
    if not raw:
        return "—"
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw[:16] if len(raw) > 16 else raw
