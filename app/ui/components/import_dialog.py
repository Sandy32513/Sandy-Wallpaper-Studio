"""
Sandy Wallpaper Studio — Import Progress Dialog
=================================================
Shows real-time progress of a folder import operation,
with cancel support and a summary report.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui import design_system as ds


class ImportWorkerSignals(QObject):
    progress = Signal(int, int, str)  # (done, total, filename)
    finished = Signal(dict)           # ImportReport.summary_dict
    error = Signal(str)


class ImportWorker(QThread):
    """Runs ImportService.import_folder in a background thread."""

    def __init__(
        self,
        import_service,
        folder_path: Path,
        category: str = "",
    ) -> None:
        super().__init__()
        self._service = import_service
        self._folder = folder_path
        self._category = category
        self._cancelled = False
        self.signals = ImportWorkerSignals()

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        def _progress(done: int, total: int, path: str) -> bool:
            self.signals.progress.emit(done, total, Path(path).name)
            return not self._cancelled

        try:
            report = self._service.import_folder(
                folder_path=self._folder,
                category=self._category,
                progress_callback=_progress,
            )
            self.signals.finished.emit(report.summary_dict)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class ImportProgressDialog(QDialog):
    """Modal dialog showing import progress with cancel and close-on-finish."""

    import_finished = Signal(dict)  # report summary

    def __init__(
        self,
        folder_path: Path,
        import_service,
        category: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._folder = folder_path
        self._service = import_service
        self._category = category
        self._worker: Optional[ImportWorker] = None

        self.setWindowTitle("Importing Wallpapers…")
        self.setFixedSize(480, 300)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {ds.BG_SURFACE}; }}")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(ds.SPACE_LG)

        # Heading
        heading = QLabel("Scanning & importing wallpapers…")
        heading.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_LG}px; font-weight: 700;")
        layout.addWidget(heading)

        # Folder label
        folder_lbl = QLabel(str(self._folder))
        folder_lbl.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px;")
        folder_lbl.setWordWrap(True)
        layout.addWidget(folder_lbl)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # Indeterminate at start
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        # Current file label
        self._file_lbl = QLabel("Scanning…")
        self._file_lbl.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px;")
        self._file_lbl.setWordWrap(True)
        layout.addWidget(self._file_lbl)

        # Stats row
        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px;")
        layout.addWidget(self._stats_lbl)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(ds.SPACE_SM)
        btn_row.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedHeight(34)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(self._cancel_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.setFixedHeight(34)
        self._close_btn.setObjectName("accent")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setVisible(False)
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)

        layout.addLayout(btn_row)

    def start_import(self) -> None:
        self._worker = ImportWorker(
            import_service=self._service,
            folder_path=self._folder,
            category=self._category,
        )
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.signals.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, done: int, total: int, filename: str) -> None:
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(done)
            self._stats_lbl.setText(f"{done} / {total} files processed")
        self._file_lbl.setText(f"↳  {filename}")

    def _on_finished(self, summary: dict) -> None:
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(1)
        imported = summary.get("imported", 0)
        skipped = summary.get("skipped", 0)
        failed = summary.get("failed", 0)
        self._file_lbl.setText("Import complete.")
        self._stats_lbl.setText(
            f"✓ {imported} imported   ◷ {skipped} skipped   ✕ {failed} failed"
        )
        self._cancel_btn.setVisible(False)
        self._close_btn.setVisible(True)
        self.import_finished.emit(summary)

    def _on_error(self, message: str) -> None:
        self._file_lbl.setText(f"Error: {message}")
        self._cancel_btn.setVisible(False)
        self._close_btn.setVisible(True)

    def _cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
        self._file_lbl.setText("Cancelling…")
        self._cancel_btn.setEnabled(False)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._cancel()
        super().closeEvent(event)
