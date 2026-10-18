"""Integrated operational preferences, attribution and library maintenance UI."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import Config
from app.database.database import Database
from app.database.wallpaper_repository import WallpaperRepository
from app.services.attribution_export_service import AttributionExportReport, export_attributions
from app.services.library_service import LibraryService
from app.services.rotation_scheduler import RotationScheduler
from app.ui import design_system as ds
from app.ui.rotation_view import RotationSettingsView
from app.utils.image_utils import (
    create_thumbnail,
    enforce_thumbnail_cache_limit,
    thumbnail_cache_path,
)
from app.utils.logging_config import setup_logging


class _MaintenanceWorker(QThread):
    progress = Signal(int, int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, operation: str, config: Config, database_path: Path) -> None:
        super().__init__()
        self.operation = operation
        self.config = config
        self.database_path = database_path
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        db = Database(self.database_path, read_only=True)
        try:
            db.connect()
            if self.operation == "integrity":
                report = LibraryService(db, self.config.cache_dir, self.config).check_integrity()
                self.completed.emit(
                    f"Integrity check complete: {report.total_records} records, "
                    f"{report.files_missing} missing files, {report.stale_thumbnails} missing thumbnails."
                )
                return

            repository = WallpaperRepository(db)
            offset = total = rebuilt = failed = 0
            size = (self.config.get("thumbnail_width", 400), self.config.get("thumbnail_height", 225))
            quality = self.config.get("thumbnail_quality", 85)
            while True:
                batch = repository.get_all(limit=100, offset=offset, order_by="id ASC")
                if not batch:
                    break
                total += len(batch)
                for wallpaper in batch:
                    if self.cancel_event.is_set():
                        self.completed.emit(f"Thumbnail rebuild cancelled after {rebuilt} rebuilt, {failed} failed.")
                        return
                    if wallpaper.path and wallpaper.sha256 and Path(wallpaper.path).is_file():
                        target = thumbnail_cache_path(
                            self.config.cache_dir / "thumbnails", wallpaper.sha256, size, quality
                        )
                        if create_thumbnail(Path(wallpaper.path), target, size=size, quality=quality):
                            rebuilt += 1
                            enforce_thumbnail_cache_limit(
                                self.config.cache_dir / "thumbnails",
                                self.config.get("thumbnail_cache_size_mb", 500),
                                preserve=target,
                            )
                        else:
                            failed += 1
                    else:
                        failed += 1
                    self.progress.emit(offset + 1, max(total, offset + 1))
                    offset += 1
            self.completed.emit(f"Thumbnail rebuild complete: {rebuilt} created, {failed} unavailable or failed.")
        except Exception as exc:
            self.failed.emit(f"Maintenance failed ({type(exc).__name__}).")
        finally:
            db.close()


class _ExportWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, database_path: Path, destination: Path, overwrite: bool) -> None:
        super().__init__()
        self.database_path = database_path
        self.destination = destination
        self.overwrite = overwrite

    def run(self) -> None:
        db = Database(self.database_path, read_only=True)
        try:
            db.connect()
            repo = WallpaperRepository(db)
            wallpapers = []
            offset = 0
            while True:
                batch = repo.get_all(limit=500, offset=offset, order_by="id ASC")
                if not batch:
                    break
                wallpapers.extend(batch)
                offset += len(batch)
            report = export_attributions(wallpapers, self.destination, overwrite=self.overwrite)
            self.completed.emit(report)
        except Exception as exc:
            self.failed.emit(f"Attribution export failed: {exc}")
        finally:
            db.close()


class SettingsView(QWidget):
    """Global preferences page. Service settings apply to new operations immediately."""

    status_message = Signal(str)

    def __init__(
        self,
        config: Config,
        db: Database,
        scheduler: RotationScheduler,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.db = db
        self.scheduler = scheduler
        self._worker: QThread | None = None
        self._loading = False
        self._widgets: dict[str, QWidget] = {}
        self._build_ui()
        self._connect_dirty_state()
        self._load_values()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(ds.SPACE_XL, ds.SPACE_LG, ds.SPACE_XL, ds.SPACE_LG)
        title = QLabel("Settings")
        title.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL + 4}px; font-weight: 700;")
        outer.addWidget(title)
        intro = QLabel("Changes apply to the next operation. Library and database files are never moved by settings.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {ds.TEXT_SECONDARY};")
        outer.addWidget(intro)

        self.tabs = QTabWidget()
        self.tabs.tabBar().setStyleSheet("QTabBar::tab { padding: 5px 6px; min-width: 42px; }")
        outer.addWidget(self.tabs, 1)
        self.tabs.addTab(self._library_tab(), "Library")
        self.tabs.addTab(self._sources_downloads_tab(), "Sources")
        self.tabs.addTab(self._duplicate_thumbnail_tab(), "Duplicates")
        self.tabs.addTab(self._logging_preferences_tab(), "Logging")
        self.tabs.addTab(RotationSettingsView(self.config, self.db, self.scheduler), "Rotation")

        self.status = QLabel("All settings saved.")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_button = QPushButton("Cancel changes")
        self.cancel_button.clicked.connect(self._load_values)
        actions.addWidget(self.cancel_button)
        self.reset_button = QPushButton("Reset to defaults")
        self.reset_button.clicked.connect(self._reset_defaults)
        actions.addWidget(self.reset_button)
        self.save_button = QPushButton("Save settings")
        self.save_button.setObjectName("accent")
        self.save_button.clicked.connect(self._save)
        actions.addWidget(self.save_button)
        self.cancel_worker_button = QPushButton("Cancel maintenance")
        self.cancel_worker_button.setEnabled(False)
        self.cancel_worker_button.clicked.connect(self._cancel_worker)
        actions.addWidget(self.cancel_worker_button)
        outer.addLayout(actions)

    def _scroll_tab(self, title: str, description: str) -> tuple[QWidget, QFormLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(ds.SPACE_LG, ds.SPACE_LG, ds.SPACE_LG, ds.SPACE_LG)
        note = QLabel(description)
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {ds.TEXT_SECONDARY};")
        layout.addWidget(note)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(ds.SPACE_LG)
        form.setVerticalSpacing(ds.SPACE_MD)
        layout.addLayout(form)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        scroll.setAccessibleName(title)
        return scroll, form

    def _path_field(self, key: str, label: str, *, directory_must_exist: bool = True) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        edit.setAccessibleName(label)
        browse = QPushButton("Browse…")

        def choose() -> None:
            selected = QFileDialog.getExistingDirectory(self, f"Select {label}", edit.text())
            if selected:
                edit.setText(selected)

        browse.clicked.connect(choose)
        layout.addWidget(edit, 1)
        layout.addWidget(browse)
        self._widgets[key] = edit
        edit.setProperty("directory_must_exist", directory_must_exist)
        return row

    def _spin(self, key: str, low: int, high: int, suffix: str = "") -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(low, high)
        widget.setSuffix(suffix)
        self._widgets[key] = widget
        return widget

    def _check(self, key: str, label: str) -> QCheckBox:
        widget = QCheckBox(label)
        self._widgets[key] = widget
        return widget

    def _library_tab(self) -> QWidget:
        page, form = self._scroll_tab(
            "Library settings",
            "The library root defines the folder boundary used by guarded duplicate cleanup. Changing it does not move, import, or reindex existing images; the database and cache stay in the application data folder.",
        )
        form.addRow("Library root", self._path_field("library_path", "Library root"))
        form.addRow("Import behavior", self._check("recursive_import", "Include subfolders by default"))
        form.addRow("Integrity", self._action_button("Check files and thumbnail cache", self._check_integrity))
        return page

    def _sources_downloads_tab(self) -> QWidget:
        page, form = self._scroll_tab(
            "Source and download settings",
            "Wikimedia Commons is the only remote source currently supported. Local browsing and rotation continue to work offline. Download controls are applied by DownloadService.from_config().",
        )
        form.addRow("Remote source", self._check("wikimedia_enabled", "Enable Wikimedia Commons"))
        form.addRow("Search results", self._spin("source_result_limit", 1, 50, " per search"))
        form.addRow("Minimum source width", self._spin("min_resolution_width", 0, 32768, " px"))
        form.addRow("Minimum source height", self._spin("min_resolution_height", 0, 32768, " px"))
        form.addRow("Download folder", self._path_field("download_folder", "Download folder"))
        form.addRow("Maximum image size", self._spin("max_download_size_mb", 1, 2048, " MB"))
        form.addRow("Request timeout", self._spin("timeout_seconds", 1, 300, " seconds"))
        form.addRow("Retry attempts", self._spin("max_retries", 1, 10))
        backoff = QDoubleSpinBox()
        backoff.setRange(1, 10)
        backoff.setSingleStep(0.5)
        backoff.setSuffix("× backoff factor")
        self._widgets["retry_backoff_factor"] = backoff
        form.addRow("Retry backoff", backoff)
        form.addRow("Concurrent downloads", self._spin("max_simultaneous_downloads", 1, 8))
        return page

    def _duplicate_thumbnail_tab(self) -> QWidget:
        page, form = self._scroll_tab(
            "Duplicate and thumbnail settings",
            "Near matches use 64-bit perceptual-hash Hamming distance: 0 is strict and 64 is loose. Exact duplicates still require matching SHA-256 and byte-for-byte content. A scan snapshots the threshold when it starts.",
        )
        form.addRow("Near-match threshold", self._spin("phash_threshold", 0, 64, " / 64 bits"))
        form.addRow("Thumbnail cache", self._check("thumbnail_enabled", "Generate and use cached thumbnails"))
        form.addRow("Thumbnail width", self._spin("thumbnail_width", 64, 1024, " px"))
        form.addRow("Thumbnail height", self._spin("thumbnail_height", 64, 1024, " px"))
        form.addRow("JPEG quality", self._spin("thumbnail_quality", 50, 95, " / 95"))
        form.addRow("Maximum cache size", self._spin("thumbnail_cache_size_mb", 50, 2048, " MB"))
        form.addRow("Cache maintenance", self._action_button("Rebuild thumbnails in background", self._rebuild_thumbnails))
        return page

    def _logging_preferences_tab(self) -> QWidget:
        page, form = self._scroll_tab(
            "Logging and user preferences",
            f"Logs are stored under {self.config.logs_dir}. File output can fail independently; the application keeps console logging available.",
        )
        level = QComboBox()
        level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._widgets["log_level"] = level
        form.addRow("Log level", level)
        form.addRow("File output", self._check("file_logging_enabled", "Write rotating log files"))
        form.addRow("Maximum log size", self._spin("log_max_size_mb", 1, 100, " MB"))
        form.addRow("Retained log files", self._spin("log_backup_count", 1, 10))
        style = QComboBox()
        style.addItems(["Center", "Tile", "Stretch", "Fit", "Fill", "Span"])
        self._widgets["wallpaper_style"] = style
        form.addRow("Wallpaper display style", style)
        form.addRow("Attribution", self._action_button("Export library attribution as CSV…", self._export_attributions))
        return page

    @staticmethod
    def _action_button(label: str, action) -> QPushButton:
        button = QPushButton(label)
        button.clicked.connect(action)
        return button

    def _load_values(self) -> None:
        self._loading = True
        for key, widget in self._widgets.items():
            if key == "wikimedia_enabled":
                assert isinstance(widget, QCheckBox)
                value = "wikimedia" in self.config.get("enabled_sources", ["wikimedia"])
            else:
                value = self.config.get(key)
            if isinstance(widget, QLineEdit):
                widget.setText(str(value or ""))
                widget.setCursorPosition(0)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                index = widget.findText(str(value))
                widget.setCurrentIndex(max(0, index))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value))
        self.status.setText("All settings saved.")
        self._loading = False
        self.save_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

    def _connect_dirty_state(self) -> None:
        for widget in self._widgets.values():
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._mark_dirty)
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(self._mark_dirty)
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._mark_dirty)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self._mark_dirty)

    def _mark_dirty(self, *_args: object) -> None:
        if self._loading:
            return
        self.status.setText("Unsaved changes")
        self.save_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

    def _collect(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for key, widget in self._widgets.items():
            if key == "wikimedia_enabled":
                assert isinstance(widget, QCheckBox)
                values["enabled_sources"] = ["wikimedia"] if widget.isChecked() else []
            elif isinstance(widget, QLineEdit):
                path = Path(widget.text()).expanduser()
                if not path.is_dir():
                    raise ValueError(f"{key.replace('_', ' ').capitalize()} must be an existing folder.")
                values[key] = str(path)
            elif isinstance(widget, QCheckBox):
                values[key] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                values[key] = widget.currentText()
            elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                values[key] = widget.value()
        width_widget = self._widgets["thumbnail_width"]
        height_widget = self._widgets["thumbnail_height"]
        assert isinstance(width_widget, QSpinBox) and isinstance(height_widget, QSpinBox)
        width = width_widget.value()
        height = height_widget.value()
        if width * height > 1_048_576:
            raise ValueError("Thumbnail dimensions may not exceed 1,048,576 pixels in total.")
        return values

    def _save(self) -> None:
        try:
            values = self._collect()
            self.config.apply_settings(values)
        except (ValueError, OSError, KeyError) as exc:
            self.status.setText(f"Settings were not saved: {exc}")
            return
        setup_logging(
            self.config.logs_dir,
            level_name=self.config.get("log_level", "INFO"),
            file_enabled=self.config.get("file_logging_enabled", True),
            max_size_mb=self.config.get("log_max_size_mb", 5),
            backup_count=self.config.get("log_backup_count", 3),
        )
        if self.scheduler.state in {"running", "paused"}:
            self.scheduler.configure(
                self.config.rotation_preferences,
                style=str(self.config.get("wallpaper_style", "Fill")),
            )
        self._load_values()
        self.status.setText("Settings saved. Changes apply to new downloads, imports and scans.")
        self.status_message.emit("Settings saved.")

    def _reset_defaults(self) -> None:
        answer = QMessageBox.question(
            self, "Reset settings", "Reset operational preferences to their defaults? This does not change images or database records.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        defaults = Config(self.config.config_dir)
        for key, widget in self._widgets.items():
            if key == "wikimedia_enabled":
                value = "wikimedia" in defaults.get("enabled_sources", ["wikimedia"])
            else:
                value = defaults.get(key)
            if isinstance(widget, QLineEdit):
                widget.setText(str(value or ""))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(value)
        self._save()

    def _start_worker(self, worker: QThread) -> bool:
        if self._worker and self._worker.isRunning():
            self.status.setText("Another maintenance operation is already running.")
            return False
        self._worker = worker
        worker.finished.connect(self._worker_finished)
        if isinstance(worker, _MaintenanceWorker) and worker.operation == "thumbnails":
            self.cancel_worker_button.setEnabled(True)
        worker.start()
        return True

    def _cancel_worker(self) -> None:
        if isinstance(self._worker, _MaintenanceWorker):
            self._worker.cancel()
            self.cancel_worker_button.setEnabled(False)
            self.status.setText("Cancelling thumbnail rebuild after the current image…")

    def _worker_finished(self) -> None:
        self._worker = None
        self.cancel_worker_button.setEnabled(False)

    def _check_integrity(self) -> None:
        worker = _MaintenanceWorker("integrity", self.config, self.db.path)
        worker.completed.connect(self.status.setText)
        worker.failed.connect(self.status.setText)
        if self._start_worker(worker):
            self.status.setText("Checking library files and configured thumbnail cache…")

    def _rebuild_thumbnails(self) -> None:
        if not self.config.get("thumbnail_enabled", True):
            self.status.setText("Enable the thumbnail cache and save settings before rebuilding.")
            return
        worker = _MaintenanceWorker("thumbnails", self.config, self.db.path)
        worker.completed.connect(self.status.setText)
        worker.failed.connect(self.status.setText)
        worker.progress.connect(lambda done, total: self.status.setText(f"Rebuilding thumbnails: {done} processed…"))
        if self._start_worker(worker):
            self.status.setText("Rebuilding thumbnails in the background…")

    def _export_attributions(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export attribution", str(self.config.exports_dir / "attribution.csv"), "CSV files (*.csv)"
        )
        if not filename:
            return
        destination = Path(filename)
        overwrite = False
        if destination.exists():
            answer = QMessageBox.question(
                self, "Replace export?", f"Replace {destination.name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        worker = _ExportWorker(self.db.path, destination, overwrite)
        worker.completed.connect(self._on_export_complete)
        worker.failed.connect(self.status.setText)
        if self._start_worker(worker):
            self.status.setText("Exporting attribution fields from the local database…")

    def _on_export_complete(self, report: AttributionExportReport) -> None:
        self.status.setText(
            f"Exported {report.rows_exported} rows to {report.destination.name}; "
            f"{report.rows_with_incomplete_attribution} online rows have incomplete attribution."
        )
