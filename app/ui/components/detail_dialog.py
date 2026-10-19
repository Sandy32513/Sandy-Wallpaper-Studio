"""
Sandy Wallpaper Studio — Wallpaper Detail Dialog
=================================================
Full-width modal showing large preview, all metadata,
and action buttons: Set Wallpaper, Preview, Favorite, Open File, Open Source, Find Similar.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, override

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
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

from app.database.models import Wallpaper
from app.ui import design_system as ds
from app.ui.components.wallpaper_card import _placeholder_pixmap
from app.utils.image_utils import ImageDimensionLimitError, validate_image_dimensions


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
        self._preview_source: QPixmap | None = None
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        owner_window = parent.window() if parent is not None else None
        screen_width = available.width() if available else 1100
        screen_height = available.height() if available else 700
        parent_width = owner_window.width() if owner_window and owner_window.width() else 900
        parent_height = owner_window.height() if owner_window and owner_window.height() else 600
        target_width = min(1100, screen_width, max(680, parent_width))
        target_height = min(700, screen_height, max(460, parent_height - 8))
        self._compact_actions = target_width < 900

        self.setWindowTitle(f"Sandy Wallpaper Studio — {wallpaper.title or wallpaper.filename}")
        self.setMinimumSize(min(680, target_width), min(460, target_height))
        self.setMaximumSize(target_width, target_height)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ds.BG_DEEP};
            }}
        """)

        self._build_ui()
        self.resize(target_width, target_height)

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ============================================================
        # Left: large preview
        # ============================================================
        preview_panel = QWidget()
        preview_panel.setMinimumWidth(320)
        preview_panel.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        prev_layout = QVBoxLayout(preview_panel)
        prev_layout.setContentsMargins(0, 0, 0, 0)
        prev_layout.setSpacing(0)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._preview_label.setMinimumSize(0, 0)
        self._preview_label.installEventFilter(self)
        self._load_preview_image()
        prev_layout.addWidget(self._preview_label)

        # Action buttons underneath preview
        action_bar = QWidget()
        action_bar.setFixedHeight(96 if self._compact_actions else 54)
        action_bar.setStyleSheet(f"background-color: {ds.BG_SURFACE}; border-top: 1px solid {ds.BG_BORDER};")
        action_layout = QGridLayout(action_bar)
        action_layout.setContentsMargins(12, 6, 12, 6)
        action_layout.setSpacing(8)

        set_btn = QPushButton("Set Wallpaper" if self._compact_actions else "⊞  Set as Wallpaper")
        set_btn.setAccessibleName("Set as wallpaper")
        set_btn.setToolTip("Set this image as the desktop wallpaper")
        set_btn.setObjectName("accent")
        set_btn.setFixedHeight(36)
        set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_btn.clicked.connect(lambda: self.set_wallpaper_requested.emit(self._wallpaper.id or 0))

        self._fav_btn = QPushButton()
        self._fav_btn.setFixedHeight(36)
        self._fav_btn.setFixedWidth(36)
        self._fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fav_btn.setToolTip("Toggle favorite")
        self._fav_btn.clicked.connect(self._on_fav_click)
        self._update_fav_button()

        extra_buttons: list[QPushButton] = []
        if self._wallpaper.path and Path(self._wallpaper.path).exists():
            open_btn = QPushButton("File" if self._compact_actions else "📂  Open File")
            open_btn.setAccessibleName("Open wallpaper file")
            open_btn.setFixedHeight(36)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(self._open_file)
            extra_buttons.append(open_btn)

        if self._wallpaper.source_url:
            src_btn = QPushButton("Source")
            src_btn.setAccessibleName("Open source page")
            src_btn.setFixedHeight(36)
            src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            src_btn.clicked.connect(self._open_source_url)
            extra_buttons.append(src_btn)

        sim_btn = QPushButton("Similar" if self._compact_actions else "≈  Find Similar")
        sim_btn.setAccessibleName("Find similar wallpapers")
        sim_btn.setFixedHeight(36)
        sim_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sim_btn.clicked.connect(lambda: self.find_similar_requested.emit(self._wallpaper.id or 0))
        extra_buttons.append(sim_btn)
        close_btn = QPushButton("✕")
        close_btn.setObjectName("ghost")
        close_btn.setFixedSize(36, 36)
        close_btn.setAccessibleName("Close wallpaper details")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        if self._compact_actions:
            action_layout.addWidget(set_btn, 0, 0)
            action_layout.addWidget(self._fav_btn, 0, 1)
            action_layout.addWidget(close_btn, 0, 2)
            for column, button in enumerate(extra_buttons):
                action_layout.addWidget(button, 1, column)
            action_layout.setColumnStretch(0, 1)
            action_layout.setColumnStretch(1, 1)
            action_layout.setColumnStretch(2, 1)
        else:
            action_layout.addWidget(set_btn, 0, 0)
            action_layout.addWidget(self._fav_btn, 0, 1)
            col = 2
            for button in extra_buttons:
                action_layout.addWidget(button, 0, col)
                col += 1
            action_layout.addWidget(close_btn, 0, col)
            action_layout.setColumnStretch(col + 1, 1)

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
            reader = QImageReader(path)
            size = reader.size()
            try:
                validate_image_dimensions((size.width(), size.height()))
            except ImageDimensionLimitError as exc:
                self._preview_label.setText(f"Preview unavailable: {exc}")
                self._preview_label.setAccessibleName("Image preview unavailable")
                return
            except ValueError:
                self._preview_source = _placeholder_pixmap(500, 400)
                return
            image = reader.read()
            if not image.isNull():
                self._preview_source = QPixmap.fromImage(image)
                return
        self._preview_source = _placeholder_pixmap(500, 400)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._preview_label and event.type() == QEvent.Type.Resize:
            self._update_preview_image()
        return super().eventFilter(watched, event)

    def _update_preview_image(self) -> None:
        if self._preview_source is None:
            return
        target = self._preview_label.size()
        if target.width() <= 0 or target.height() <= 0:
            target = QSize(320, 240)
        self._preview_label.setPixmap(
            self._preview_source.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

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
