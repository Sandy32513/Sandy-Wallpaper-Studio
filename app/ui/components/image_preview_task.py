"""Load scaled read-only image previews outside the Qt GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, Signal
from PySide6.QtGui import QImage, QImageReader

from app.utils.image_utils import validate_image_dimensions


class ImagePreviewSignals(QObject):
    loaded = Signal(int, QImage)


class ImagePreviewTask(QRunnable):
    """Decode one image at a bounded preview size, returning a GUI-safe QImage."""

    def __init__(
        self,
        item_id: int,
        path: str,
        max_size: QSize,
        signals: ImagePreviewSignals,
    ) -> None:
        super().__init__()
        self._item_id = item_id
        self._path = path
        self._max_size = max_size
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        reader = QImageReader(self._path)
        reader.setAutoTransform(True)
        source_size = reader.size()
        try:
            validate_image_dimensions((source_size.width(), source_size.height()))
            if source_size.isValid():
                reader.setScaledSize(
                    source_size.scaled(
                        self._max_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                    )
                )
            image = reader.read()
        except (OSError, ValueError):
            image = QImage()
        self._signals.loaded.emit(self._item_id, image)
