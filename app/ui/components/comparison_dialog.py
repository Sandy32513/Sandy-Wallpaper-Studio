"""Read-only side-by-side wallpaper comparison dialog."""

from __future__ import annotations

from collections.abc import Collection
from itertools import combinations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImageReader, QPixmap
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
        image.setPixmap(self._load_preview(candidate.canonical_path.as_posix()))
        layout.addWidget(image, alignment=Qt.AlignmentFlag.AlignHCenter)

        roles = []
        if candidate.wallpaper_id in self._keep_ids:
            roles.append("Keep candidate")
        if candidate.wallpaper_id in self._preview_ids:
            roles.append("Selected for cleanup preview")
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

    @staticmethod
    def _load_preview(path: str) -> QPixmap:
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        source_size = reader.size()
        if source_size.isValid():
            reader.setScaledSize(source_size.scaled(QSize(600, 380), Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        if image.isNull():
            return QPixmap()
        return QPixmap.fromImage(image).scaled(
            QSize(300, 190),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

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
