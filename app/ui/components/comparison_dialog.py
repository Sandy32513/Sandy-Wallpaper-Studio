"""Read-only side-by-side wallpaper comparison dialog."""

from __future__ import annotations

from collections.abc import Collection
from itertools import combinations

from PySide6.QtCore import QSize, Qt, QThreadPool
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.duplicate_scan_service import DuplicateCandidate
from app.ui import design_system as ds
from app.ui.components.image_preview_task import ImagePreviewSignals, ImagePreviewTask


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


class ComparisonDialog(QDialog):
    """Compare two to four candidate wallpapers without writing files."""

    def __init__(
        self,
        candidates: tuple[DuplicateCandidate, ...],
        parent=None,
        *,
        keep_ids: Collection[int] = (),
        preview_ids: Collection[int] = (),
    ) -> None:
        super().__init__(parent)
        self._candidates = candidates
        self._keep_ids = set(keep_ids)
        self._preview_ids = set(preview_ids)
        self._preview_pool = QThreadPool(self)
        self._preview_pool.setMaxThreadCount(4)
        self._preview_labels: dict[int, QLabel] = {}
        self._preview_signals = ImagePreviewSignals()
        self._preview_signals.loaded.connect(self._on_preview_loaded)
        self.setWindowTitle("Compare wallpapers")
        self.resize(1080, 660)
        self.setMinimumSize(720, 480)
        self.setStyleSheet(f"background-color: {ds.BG_DEEP}; color: {ds.TEXT_PRIMARY};")

        root = QVBoxLayout(self)
        root.setContentsMargins(ds.SPACE_LG, ds.SPACE_LG, ds.SPACE_LG, ds.SPACE_LG)
        root.setSpacing(ds.SPACE_MD)

        heading = QLabel("Side-by-side comparison")
        heading.setStyleSheet(
            f"font-size: {ds.FONT_SIZE_XL}px; font-weight: 700; color: {ds.TEXT_PRIMARY};"
        )
        root.addWidget(heading)

        note = QLabel(
            "Similarity is derived from 64-bit pHash Hamming distance; it is a visual signal, not a probability."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {ds.TEXT_SECONDARY};")
        root.addWidget(note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        row = QHBoxLayout(body)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(ds.SPACE_MD)
        for candidate in candidates:
            row.addWidget(self._make_candidate_card(candidate))
        row.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        root.addWidget(self._make_pairwise_summary())
        footer = QHBoxLayout()
        footer.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        root.addLayout(footer)

    def _make_candidate_card(self, candidate: DuplicateCandidate) -> QWidget:
        card = QWidget()
        card.setMinimumWidth(250)
        card.setMaximumWidth(360)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        card.setStyleSheet(
            f"background-color: {ds.BG_SURFACE}; border: 1px solid {ds.BG_BORDER}; border-radius: 8px;"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(ds.SPACE_MD, ds.SPACE_MD, ds.SPACE_MD, ds.SPACE_MD)
        layout.setSpacing(ds.SPACE_SM)

        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setFixedSize(300, 190)
        image.setStyleSheet(f"background-color: {ds.BG_DEEP}; border-radius: 4px;")
        image.setText("Loading preview…")
        self._preview_labels[candidate.wallpaper_id] = image
        self._preview_pool.start(
            ImagePreviewTask(
                candidate.wallpaper_id,
                str(candidate.canonical_path),
                QSize(600, 380),
                self._preview_signals,
            )
        )
        layout.addWidget(image, alignment=Qt.AlignmentFlag.AlignHCenter)

        roles = []
        if candidate.wallpaper_id in self._keep_ids:
            roles.append("Keep candidate")
        if candidate.wallpaper_id in self._preview_ids:
            roles.append("Selected for Recycle Bin")
        role = QLabel(" · ".join(roles) if roles else "Comparison only")
        role.setWordWrap(True)
        role.setStyleSheet(f"color: {ds.ACCENT_PRIMARY}; font-weight: 600; border: none;")
        layout.addWidget(role)

        title = QLabel(candidate.display_name)
        title.setWordWrap(True)
        title.setToolTip(str(candidate.canonical_path))
        title.setStyleSheet(f"font-weight: 700; color: {ds.TEXT_PRIMARY}; border: none;")
        layout.addWidget(title)

        metadata = QLabel(
            f"{candidate.width:,} × {candidate.height:,}  ·  {candidate.image_format}  ·  "
            f"{_format_size(candidate.size_bytes)}\n"
            f"SHA-256  {candidate.sha256[:16]}…\n"
            f"pHash  {candidate.phash}"
        )
        metadata.setWordWrap(True)
        metadata.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        metadata.setStyleSheet(f"font-size: {ds.FONT_SIZE_XS}px; color: {ds.TEXT_SECONDARY}; border: none;")
        layout.addWidget(metadata)

        path = QLabel(candidate.canonical_path.as_posix())
        path.setWordWrap(True)
        path.setToolTip(str(candidate.canonical_path))
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path.setStyleSheet(f"font-size: {ds.FONT_SIZE_XS}px; color: {ds.TEXT_DISABLED}; border: none;")
        layout.addWidget(path)
        return card

    def _on_preview_loaded(self, item_id: int, image: QImage) -> None:
        label = self._preview_labels.get(item_id)
        if label is None:
            return
        if image.isNull():
            label.setText("Preview unavailable")
            return
        label.setText("")
        label.setPixmap(QPixmap.fromImage(image).scaled(
            label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def closeEvent(self, event) -> None:  # noqa: N802
        self._preview_pool.clear()
        self._preview_pool.waitForDone()
        super().closeEvent(event)

    def _make_pairwise_summary(self) -> QLabel:
        lines = ["Pairwise match details:"]
        for first, second in combinations(self._candidates, 2):
            distance = (int(first.phash, 16) ^ int(second.phash, 16)).bit_count()
            score = (64 - distance) * 100 / 64
            relation = "same SHA-256" if first.sha256 == second.sha256 else "different SHA-256"
            lines.append(
                f"{first.display_name} ↔ {second.display_name}: {relation}; "
                f"pHash distance {distance}/64; similarity {score:.2f}%"
            )
        summary = QLabel("\n".join(lines))
        summary.setWordWrap(True)
        summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary.setStyleSheet(
            f"background-color: {ds.BG_SURFACE}; color: {ds.TEXT_SECONDARY}; padding: 10px;"
        )
        return summary
