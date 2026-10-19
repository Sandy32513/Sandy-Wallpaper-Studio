"""
Sandy Wallpaper Studio — Wallpaper Card Component
===================================================
A thumbnail card displaying wallpaper preview with metadata overlay,
favorite toggle, and action buttons (Set Wallpaper, View Detail).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImageReader, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Wallpaper
from app.ui import design_system as ds
from app.utils.image_utils import validate_image_dimensions


# ============================================================
# Async Thumbnail Loader
# ============================================================
class _ClickableLabel(QLabel):
    """QLabel that exposes left clicks through a typed Qt signal."""

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ThumbnailLoader(QObject):
    """Worker that loads a thumbnail QPixmap off the UI thread."""

    loaded = Signal(int, QPixmap)  # (wallpaper_id, pixmap)

    def __init__(
        self,
        wallpaper_id: int,
        image_path: str,
        width: int = ds.THUMB_GRID_W,
        height: int = ds.THUMB_GRID_H,
    ) -> None:
        super().__init__()
        self._wid = wallpaper_id
        self._path = image_path
        self._width = width
        self._height = height

    def run(self) -> None:
        """Load image, scale to fill, emit result."""
        try:
            reader = QImageReader(self._path)
            source_size = reader.size()
            validate_image_dimensions((source_size.width(), source_size.height()))
            img = reader.read()
            if img.isNull():
                self.loaded.emit(self._wid, _placeholder_pixmap(self._width, self._height, error=True))
                return
            pixmap = QPixmap.fromImage(img).scaled(
                QSize(self._width, self._height),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Crop to exact target size
            x_off = max(0, (pixmap.width() - self._width) // 2)
            y_off = max(0, (pixmap.height() - self._height) // 2)
            pixmap = pixmap.copy(x_off, y_off, self._width, self._height)
            self.loaded.emit(self._wid, pixmap)
        except Exception:
            self.loaded.emit(self._wid, _placeholder_pixmap(self._width, self._height, error=True))


def _placeholder_pixmap(w: int, h: int, error: bool = False) -> QPixmap:
    """Return a placeholder thumbnail pixmap."""
    pixmap = QPixmap(w, h)
    pixmap.fill(QColor(ds.BG_ELEVATED))
    painter = QPainter(pixmap)
    painter.setPen(QColor(ds.TEXT_DISABLED))
    font = QFont(ds.FONT_FAMILY, ds.FONT_SIZE_SM)
    painter.setFont(font)
    msg = "Error" if error else "Loading…"
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, msg)
    painter.end()
    return pixmap


# ============================================================
# Wallpaper Card
# ============================================================
class WallpaperCard(QFrame):
    """A compact wallpaper thumbnail card.

    Signals:
        set_wallpaper_requested: Emits the wallpaper ID when the set button is clicked.
        detail_requested: Emits the wallpaper ID when the card body is clicked.
        favorite_toggled: Emits (wallpaper_id, new_favorite_state).
    """

    set_wallpaper_requested = Signal(int)
    detail_requested = Signal(int)
    favorite_toggled = Signal(int, bool)

    def __init__(
        self,
        wallpaper: Wallpaper,
        parent: Optional[QWidget] = None,
        thumbnail_path: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._wallpaper = wallpaper
        self._thumbnail_path = thumbnail_path
        self._is_fav = wallpaper.favorite
        self._thread: Optional[QThread] = None
        self._loader: Optional[ThumbnailLoader] = None

        self._setup_ui()
        self._schedule_thumbnail_load()

    # ----------------------------------------------------------
    # UI Construction
    # ----------------------------------------------------------
    def _setup_ui(self) -> None:
        self.setFixedSize(ds.CARD_WIDTH, ds.CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ds.BG_SURFACE};
                border-radius: {ds.CARD_RADIUS}px;
                border: 1px solid {ds.BG_BORDER};
            }}
            QFrame:hover {{
                border: 1px solid {ds.ACCENT_PRIMARY};
                background-color: {ds.BG_ELEVATED};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- Thumbnail area ----
        self._thumb_label = _ClickableLabel()
        self._thumb_label.setFixedSize(ds.CARD_WIDTH, ds.CARD_THUMB_H)
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setStyleSheet(f"""
            QLabel {{
                background-color: {ds.BG_DEEP};
                border-top-left-radius: {ds.CARD_RADIUS}px;
                border-top-right-radius: {ds.CARD_RADIUS}px;
                border-bottom: 1px solid {ds.BG_BORDER};
            }}
        """)
        self._thumb_label.setPixmap(_placeholder_pixmap(ds.CARD_WIDTH, ds.CARD_THUMB_H))
        self._thumb_label.clicked.connect(
            lambda: self.detail_requested.emit(self._wallpaper.id or 0)
        )
        layout.addWidget(self._thumb_label)

        # ---- Info area ----
        info = QWidget()
        info.setFixedHeight(ds.CARD_HEIGHT - ds.CARD_THUMB_H)
        info.setStyleSheet("background-color: transparent;")
        info_layout = QHBoxLayout(info)
        info_layout.setContentsMargins(10, 6, 8, 6)
        info_layout.setSpacing(0)

        # Left: title + resolution
        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        # Title (elided)
        title_text = (self._wallpaper.title or self._wallpaper.filename or "Untitled")[:30]
        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_SM}px; font-weight: 600;")
        title_lbl.setWordWrap(False)
        text_col.addWidget(title_lbl)

        # Resolution / category line
        res_text = _make_meta_text(self._wallpaper)
        res_lbl = QLabel(res_text)
        res_lbl.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px;")
        text_col.addWidget(res_lbl)

        info_layout.addLayout(text_col)
        info_layout.addStretch()

        # Right: action buttons column
        btn_col = QVBoxLayout()
        btn_col.setSpacing(2)
        btn_col.setContentsMargins(0, 0, 0, 0)

        # Favorite button
        self._fav_btn = QPushButton("♥")
        self._fav_btn.setFixedSize(24, 24)
        self._fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fav_btn.setToolTip("Toggle favorite")
        self._update_fav_style()
        self._fav_btn.clicked.connect(self._on_fav_clicked)
        btn_col.addWidget(self._fav_btn)

        # Set wallpaper button
        set_btn = QPushButton("⊞")
        set_btn.setFixedSize(24, 24)
        set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_btn.setToolTip("Set as wallpaper")
        set_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {ds.TEXT_SECONDARY};
                font-size: 14px;
            }}
            QPushButton:hover {{
                color: {ds.ACCENT_LIGHT};
            }}
        """)
        set_btn.clicked.connect(lambda: self.set_wallpaper_requested.emit(self._wallpaper.id or 0))
        btn_col.addWidget(set_btn)

        info_layout.addLayout(btn_col)
        layout.addWidget(info)

    # ----------------------------------------------------------
    # Thumbnail Loading
    # ----------------------------------------------------------
    def _schedule_thumbnail_load(self) -> None:
        """Start async thumbnail load with a small delay for batch scheduling."""
        QTimer.singleShot(50, self._start_load)

    def _start_load(self) -> None:
        # Try cached thumbnail path first, then original path
        path = self._get_thumb_path()
        if not path or not Path(path).is_file():
            return  # No image available

        self._thread = QThread()
        self._loader = ThumbnailLoader(
            wallpaper_id=self._wallpaper.id or 0,
            image_path=path,
            width=ds.CARD_WIDTH,
            height=ds.CARD_THUMB_H,
        )
        self._loader.moveToThread(self._thread)
        self._thread.started.connect(self._loader.run)
        self._loader.loaded.connect(self._on_thumbnail_loaded)
        self._loader.loaded.connect(self._thread.quit)
        self._thread.start()

    def _get_thumb_path(self) -> Optional[str]:
        """Return best available image path for thumbnail."""
        if self._thumbnail_path and self._thumbnail_path.is_file():
            return str(self._thumbnail_path)
        if self._wallpaper.path and Path(self._wallpaper.path).is_file():
            return self._wallpaper.path
        return None

    def _on_thumbnail_loaded(self, wallpaper_id: int, pixmap: QPixmap) -> None:
        if wallpaper_id == (self._wallpaper.id or 0):
            self._thumb_label.setPixmap(pixmap)
            self._thumb_label.setScaledContents(False)

    # ----------------------------------------------------------
    # Favorite
    # ----------------------------------------------------------
    def _on_fav_clicked(self) -> None:
        self._is_fav = not self._is_fav
        self._update_fav_style()
        self.favorite_toggled.emit(self._wallpaper.id or 0, self._is_fav)

    def _update_fav_style(self) -> None:
        color = ds.DANGER if self._is_fav else ds.TEXT_DISABLED
        self._fav_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {color};
                font-size: 14px;
            }}
            QPushButton:hover {{
                color: {ds.DANGER};
            }}
        """)

    def wallpaper_id(self) -> int:
        return self._wallpaper.id or 0

    def stop_loader(self) -> None:
        """Stop thumbnail loading thread if running."""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(100)

    def update_wallpaper(self, wallpaper: Wallpaper) -> None:
        """Refresh with updated wallpaper data (e.g. after favorite toggle)."""
        self._wallpaper = wallpaper
        self._is_fav = wallpaper.favorite
        self._update_fav_style()


def _make_meta_text(wp: Wallpaper) -> str:
    parts: list[str] = []
    if wp.resolution_class:
        parts.append(wp.resolution_class)
    elif wp.width and wp.height:
        parts.append(f"{wp.width}×{wp.height}")
    if wp.category:
        parts.append(wp.category[:14])
    return "  ·  ".join(parts) if parts else "Unknown"
