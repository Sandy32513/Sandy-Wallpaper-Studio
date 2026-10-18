"""Duplicate Manager: review exact and visually similar wallpaper groups."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import Config
from app.constants import DEFAULT_PHASH_THRESHOLD
from app.services.duplicate_scan_service import (
    CleanupPreview,
    DuplicateCandidate,
    DuplicateGroup,
    DuplicateScanReport,
    validate_threshold,
)
from app.services.duplicate_scan_worker import CleanupPreviewWorker, DuplicateScanWorker
from app.ui import design_system as ds
from app.ui.components.comparison_dialog import ComparisonDialog

GROUPS_PER_PAGE = 8


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def _small_preview(path: Path) -> QPixmap:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    source_size = reader.size()
    if source_size.isValid():
        from PySide6.QtCore import QSize

        reader.setScaledSize(source_size.scaled(QSize(112, 74), Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    return QPixmap.fromImage(image) if not image.isNull() else QPixmap()


class MemberChoice(QWidget):
    """One duplicate group member with explicit keep and remove controls."""

    choice_changed = Signal(str, int, bool, bool)
    compare_changed = Signal(int, bool)

    def __init__(
        self,
        group_id: str,
        candidate: DuplicateCandidate,
        remove_checked: bool,
        keep_checked: bool,
        compare_checked: bool,
        button_group: QButtonGroup,
        similarity_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._group_id = group_id
        self._candidate = candidate
        self.setStyleSheet(
            f"background-color: {ds.BG_DEEP}; border: 1px solid {ds.BG_BORDER}; border-radius: 6px;"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(ds.SPACE_SM, ds.SPACE_SM, ds.SPACE_SM, ds.SPACE_SM)
        row.setSpacing(ds.SPACE_SM)

        thumbnail = QLabel()
        thumbnail.setFixedSize(84, 60)
        thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail.setStyleSheet("background: transparent; border: none;")
        pixmap = _small_preview(candidate.canonical_path)
        if not pixmap.isNull():
            thumbnail.setPixmap(
                pixmap.scaled(84, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        row.addWidget(thumbnail)

        details = QVBoxLayout()
        details.setSpacing(2)
        name = QLabel(candidate.display_name)
        name.setWordWrap(True)
        name.setMinimumWidth(0)
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        name.setToolTip(str(candidate.canonical_path))
        name.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-weight: 600; border: none;")
        details.addWidget(name)
        metadata = QLabel(
            f"{candidate.width:,} × {candidate.height:,} · {candidate.image_format} · "
            f"{_format_size(candidate.size_bytes)} · {similarity_text or ('SHA ' + candidate.sha256[:12])}"
        )
        metadata.setWordWrap(True)
        metadata.setMinimumWidth(0)
        metadata.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        metadata.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px; border: none;")
        details.addWidget(metadata)
        path = QLabel(candidate.canonical_path.as_posix())
        path.setWordWrap(True)
        path.setToolTip(str(candidate.canonical_path))
        path.setMinimumWidth(0)
        path.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path.setStyleSheet(f"color: {ds.TEXT_DISABLED}; font-size: {ds.FONT_SIZE_XS}px; border: none;")
        details.addWidget(path)
        detail_widget = QWidget()
        detail_widget.setMinimumWidth(0)
        detail_widget.setLayout(details)
        detail_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(detail_widget, stretch=1)

        choices = QWidget()
        choices_layout = QVBoxLayout(choices)
        choices_layout.setContentsMargins(0, 0, 0, 0)
        choices_layout.setSpacing(2)
        self.keep_radio = QRadioButton("Keep")
        self.keep_radio.setToolTip("Explicitly mark this file as the retained copy for this group.")
        self.keep_radio.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; border: none;")
        button_group.addButton(self.keep_radio, candidate.wallpaper_id)
        self.keep_radio.setChecked(keep_checked)
        choices_layout.addWidget(self.keep_radio)

        self.remove_check = QCheckBox("Preview")
        self.remove_check.setToolTip("Select this file for the read-only cleanup preview.")
        self.remove_check.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; border: none;")
        self.remove_check.setChecked(remove_checked)
        choices_layout.addWidget(self.remove_check)

        self.keep_radio.toggled.connect(self._emit_choice)
        self.remove_check.toggled.connect(self._emit_choice)

        self.compare_check = QCheckBox("Compare")
        self.compare_check.setToolTip("Add this file to the side-by-side comparison selection.")
        self.compare_check.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; border: none;")
        self.compare_check.setChecked(compare_checked)
        choices_layout.addWidget(self.compare_check)
        row.addWidget(choices)
        self.compare_check.toggled.connect(
            lambda checked: self.compare_changed.emit(candidate.wallpaper_id, checked)
        )

    def _emit_choice(self, _checked: bool = False) -> None:
        if self.keep_radio.isChecked() and self.remove_check.isChecked():
            self.remove_check.blockSignals(True)
            self.remove_check.setChecked(False)
            self.remove_check.blockSignals(False)
        self.choice_changed.emit(
            self._group_id,
            self._candidate.wallpaper_id,
            self.remove_check.isChecked(),
            self.keep_radio.isChecked(),
        )


class DuplicateGroupCard(QFrame):
    """Compact review card for a single exact or near-match group."""

    choice_changed = Signal(str, int, bool, bool)
    compare_changed = Signal(int, bool)
    bulk_choice = Signal(str, object, str)

    def __init__(
        self,
        group: DuplicateGroup,
        index: int,
        removals: set[int],
        keep_id: int | None,
        compare_ids: set[int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.group = group
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"QFrame {{ background-color: {ds.BG_SURFACE}; border: 1px solid {ds.BG_BORDER}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.SPACE_MD, ds.SPACE_MD, ds.SPACE_MD, ds.SPACE_MD)
        layout.setSpacing(ds.SPACE_SM)

        header = QVBoxLayout()
        title = QLabel(f"Group {index} · {len(group.members)} files")
        title.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-weight: 700; font-size: {ds.FONT_SIZE_MD}px; border: none;")
        header.addWidget(title)
        if group.kind == "exact":
            summary = f"Byte-identical · {_format_size(group.exact_redundant_bytes)} redundant bytes"
        else:
            summary = (
                f"Near matches · strongest direct similarity {group.highest_similarity:.2f}% · "
                f"{len(group.edges)} direct links"
            )
        summary_label = QLabel(summary)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; border: none;")
        header.addWidget(summary_label)
        layout.addLayout(header)

        action_row = QHBoxLayout()
        action_row.addStretch()
        select_all = QPushButton("Select all except retained")
        select_all.setEnabled(True)
        select_all.clicked.connect(
            lambda: self.bulk_choice.emit(group.group_id, {member.wallpaper_id for member in group.members}, "all")
        )
        clear = QPushButton("Clear choices")
        clear.clicked.connect(
            lambda: self.bulk_choice.emit(
                group.group_id,
                {member.wallpaper_id for member in group.members},
                "clear",
            )
        )
        action_row.addWidget(select_all)
        action_row.addWidget(clear)
        layout.addLayout(action_row)

        similarity_by_id: dict[int, str] = {}
        if group.kind == "near":
            best: dict[int, tuple[int, float]] = {}
            for edge in group.edges:
                for candidate_id in (edge.first_id, edge.second_id):
                    prior = best.get(candidate_id)
                    if prior is None or edge.hamming_distance < prior[0]:
                        best[candidate_id] = (edge.hamming_distance, edge.similarity_percent)
            similarity_by_id = {
                candidate_id: f"nearest direct pHash {distance}/64 · {score:.2f}%"
                for candidate_id, (distance, score) in best.items()
            }

        button_group = QButtonGroup(self)
        button_group.setExclusive(True)
        for candidate in group.members:
            member = MemberChoice(
                group.group_id,
                candidate,
                candidate.wallpaper_id in removals,
                candidate.wallpaper_id == keep_id,
                candidate.wallpaper_id in compare_ids,
                button_group,
                similarity_by_id.get(candidate.wallpaper_id, ""),
            )
            member.choice_changed.connect(self.choice_changed)
            member.compare_changed.connect(self.compare_changed)
            layout.addWidget(member)


class GroupResultsTab(QWidget):
    """Searchable, sortable, paginated list of duplicate groups."""

    choice_changed = Signal(str, int, bool, bool)
    compare_changed = Signal(int, bool)
    bulk_choice = Signal(str, object, str)

    def __init__(
        self,
        kind: str,
        removals: dict[str, set[int]],
        keeps: dict[str, int],
        compare_ids: set[int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._removals = removals
        self._keeps = keeps
        self._compare_ids = compare_ids
        self._groups: tuple[DuplicateGroup, ...] = ()
        self._page = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.SPACE_LG, ds.SPACE_MD, ds.SPACE_LG, ds.SPACE_LG)
        layout.setSpacing(ds.SPACE_SM)

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search filename or full path…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search)
        controls.addWidget(self.search, stretch=1)
        self.sort = QComboBox()
        if kind == "exact":
            self.sort.addItems(["Largest group", "Most redundant bytes", "Name A–Z"])
        else:
            self.sort.addItems(["Highest similarity", "Largest group", "Name A–Z"])
        self.sort.currentIndexChanged.connect(lambda _index: self._render())
        controls.addWidget(self.sort)
        layout.addLayout(controls)

        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.results_scroll.setStyleSheet(f"background: {ds.BG_DEEP}; border: none;")
        self.contents = QWidget()
        self.cards_layout = QVBoxLayout(self.contents)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(ds.SPACE_MD)
        self.results_scroll.setWidget(self.contents)
        layout.addWidget(self.results_scroll, stretch=1)

        footer = QHBoxLayout()
        self.page_label = QLabel("No groups")
        self.page_label.setStyleSheet(f"color: {ds.TEXT_SECONDARY};")
        footer.addWidget(self.page_label)
        footer.addStretch()
        self.previous = QPushButton("← Previous")
        self.previous.clicked.connect(self._previous_page)
        self.next = QPushButton("Next →")
        self.next.clicked.connect(self._next_page)
        footer.addWidget(self.previous)
        footer.addWidget(self.next)
        layout.addLayout(footer)

        self.empty_state = QLabel("Run a scan to look for duplicate groups.")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setWordWrap(True)
        self.empty_state.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; padding: 28px;")
        layout.addWidget(self.empty_state)
        self.empty_state.hide()

    def set_groups(self, groups: tuple[DuplicateGroup, ...]) -> None:
        self._groups = groups
        self._page = 0
        self._render()

    def refresh_choices(self) -> None:
        self._render()

    def _on_search(self, _text: str) -> None:
        self._page = 0
        self._render()

    def _filtered_groups(self) -> list[DuplicateGroup]:
        query = self.search.text().strip().casefold()
        groups = [
            group
            for group in self._groups
            if not query
            or any(
                query in member.display_name.casefold()
                or query in str(member.canonical_path).casefold()
                for member in group.members
            )
        ]
        choice = self.sort.currentText()
        if choice == "Most redundant bytes":
            groups.sort(key=lambda group: (-group.exact_redundant_bytes, group.group_id))
        elif choice == "Highest similarity":
            groups.sort(key=lambda group: (-group.highest_similarity, group.group_id))
        elif choice == "Name A–Z":
            groups.sort(key=lambda group: (group.members[0].display_name.casefold(), group.group_id))
        else:
            groups.sort(key=lambda group: (-len(group.members), group.group_id))
        return groups

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

    def _render(self) -> None:
        self._clear_cards()
        groups = self._filtered_groups()
        total_pages = max(1, math.ceil(len(groups) / GROUPS_PER_PAGE))
        self._page = min(self._page, total_pages - 1)
        start = self._page * GROUPS_PER_PAGE
        visible = groups[start : start + GROUPS_PER_PAGE]
        for offset, group in enumerate(visible, start=start + 1):
            card = DuplicateGroupCard(
                group,
                offset,
                self._removals.get(group.group_id, set()),
                self._keeps.get(group.group_id),
                self._compare_ids,
            )
            card.choice_changed.connect(self.choice_changed)
            card.compare_changed.connect(self.compare_changed)
            card.bulk_choice.connect(self.bulk_choice)
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch()
        has_groups = bool(groups)
        self.results_scroll.setVisible(has_groups)
        self.empty_state.setVisible(not has_groups)
        if not self._groups:
            self.empty_state.setText("Run a scan to look for duplicate groups.")
        else:
            self.empty_state.setText("No groups match this search.")
        self.page_label.setText(
            f"Page {self._page + 1} of {total_pages} · {len(groups)} groups"
            if groups
            else "No matching groups"
        )
        self.previous.setEnabled(bool(groups) and self._page > 0)
        self.next.setEnabled(bool(groups) and self._page + 1 < total_pages)

    def _previous_page(self) -> None:
        self._page = max(0, self._page - 1)
        self._render()

    def _next_page(self) -> None:
        self._page += 1
        self._render()


class DuplicateManagerView(QWidget):
    """Review duplicates with a read-only scan and plan preview."""

    status_message = Signal(str)

    def __init__(
        self,
        database_path: Path,
        config: Config,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._config = config
        self._scan_worker: DuplicateScanWorker | None = None
        self._preview_worker: CleanupPreviewWorker | None = None
        self._report: DuplicateScanReport | None = None
        self._removals: dict[str, set[int]] = {}
        self._keeps: dict[str, int] = {}
        self._compare_ids: set[int] = set()
        self._candidate_by_id: dict[int, DuplicateCandidate] = {}
        self._build_ui()
        self._refresh_selection_summary()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        heading = QWidget()
        heading.setStyleSheet(f"background-color: {ds.BG_SURFACE}; border-bottom: 1px solid {ds.BG_BORDER};")
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(ds.SPACE_XL, ds.SPACE_LG, ds.SPACE_XL, ds.SPACE_LG)
        title = QLabel("Duplicate Manager")
        title.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL}px; font-weight: 700; background: transparent; border: none;")
        heading_layout.addWidget(title)
        description = QLabel(
            "Review byte-identical and visually similar images. Scans verify current files and never modify the library."
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; background: transparent; border: none;")
        heading_layout.addWidget(description)
        root.addWidget(heading)

        content = QWidget()
        content.setStyleSheet(f"background-color: {ds.BG_DEEP};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(ds.SPACE_LG, ds.SPACE_MD, ds.SPACE_LG, ds.SPACE_LG)
        layout.setSpacing(ds.SPACE_SM)

        self.kpi_label = QLabel("Exact groups: 0   ·   Near groups: 0   ·   Candidate files: 0   ·   Exact-only redundant bytes: 0 B")
        self.kpi_label.setWordWrap(True)
        self.kpi_label.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-weight: 600; padding: 8px 10px; background: {ds.BG_SURFACE}; border: 1px solid {ds.BG_BORDER}; border-radius: 6px;")
        layout.addWidget(self.kpi_label)

        controls = QVBoxLayout()
        controls.setSpacing(ds.SPACE_SM)
        scan_controls = QHBoxLayout()
        scan_controls.setSpacing(ds.SPACE_SM)
        self.scan_button = QPushButton("Scan library")
        self.scan_button.setObjectName("accent")
        self.scan_button.clicked.connect(self.start_scan)
        scan_controls.addWidget(self.scan_button)
        self.cancel_button = QPushButton("Cancel scan")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_active_task)
        scan_controls.addWidget(self.cancel_button)
        threshold_label = QLabel("Near-match threshold (pHash distance):")
        scan_controls.addWidget(threshold_label)
        self.threshold = QSpinBox()
        self.threshold.setRange(0, 64)
        self.threshold.setValue(self._read_threshold())
        self.threshold.setToolTip("Maximum 64-bit pHash Hamming distance. Lower values are stricter; this score is not a probability.")
        self.threshold.valueChanged.connect(self._save_threshold)
        scan_controls.addWidget(self.threshold)
        scan_controls.addStretch()
        controls.addLayout(scan_controls)

        actions = QHBoxLayout()
        actions.addStretch()
        self.compare_button = QPushButton("Compare selected (2–4)")
        self.compare_button.setEnabled(False)
        self.compare_button.clicked.connect(self.compare_selected)
        actions.addWidget(self.compare_button)
        self.preview_button = QPushButton("Preview selected plan")
        self.preview_button.clicked.connect(self.preview_selected)
        actions.addWidget(self.preview_button)
        self.delete_button = QPushButton("Clean up files")
        self.delete_button.setEnabled(False)
        self.delete_button.setToolTip("Disabled because this app does not yet have a verified recoverable Recycle Bin or quarantine workflow.")
        actions.addWidget(self.delete_button)
        controls.addLayout(actions)
        layout.addLayout(controls)

        self.threshold_note = QLabel(
            "pHash similarity = (64 − Hamming distance) ÷ 64 × 100. Near groups may form chains; each displayed score is a direct pair comparison. File removal is disabled until a verified recoverable Recycle Bin or quarantine workflow is available."
        )
        self.threshold_note.setWordWrap(True)
        self.threshold_note.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px;")
        layout.addWidget(self.threshold_note)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Ready")
        layout.addWidget(self.progress)

        self.selection_summary = QLabel("No files selected for preview.")
        self.selection_summary.setWordWrap(True)
        self.selection_summary.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px;")
        layout.addWidget(self.selection_summary)

        self.tabs = QTabWidget()
        self.exact_tab = GroupResultsTab("exact", self._removals, self._keeps, self._compare_ids)
        self.near_tab = GroupResultsTab("near", self._removals, self._keeps, self._compare_ids)
        for tab in (self.exact_tab, self.near_tab):
            tab.choice_changed.connect(self._on_choice_changed)
            tab.compare_changed.connect(self._on_compare_choice_changed)
            tab.bulk_choice.connect(self._on_bulk_choice)
        self.tabs.addTab(self.exact_tab, "Exact duplicates")
        self.tabs.addTab(self.near_tab, "Near matches")
        layout.addWidget(self.tabs, stretch=1)

        summary_row = QHBoxLayout()
        self.scan_summary = QLabel("No scan has run yet.")
        self.scan_summary.setWordWrap(True)
        self.scan_summary.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px;")
        summary_row.addWidget(self.scan_summary, stretch=1)
        self.issues_button = QPushButton("View issues")
        self.issues_button.setEnabled(False)
        self.issues_button.clicked.connect(self._show_issues)
        summary_row.addWidget(self.issues_button)
        layout.addLayout(summary_row)
        root.addWidget(content, stretch=1)

    def _read_threshold(self) -> int:
        value = self._config.get("phash_threshold", DEFAULT_PHASH_THRESHOLD)
        try:
            return validate_threshold(value)
        except ValueError:
            return DEFAULT_PHASH_THRESHOLD

    def _save_threshold(self, value: int) -> None:
        self._config.set("phash_threshold", value)
        self._config.save()

    def refresh(self) -> None:
        self._render_report()

    def start_scan(self) -> None:
        if self._task_running():
            return
        try:
            threshold = validate_threshold(self.threshold.value())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid threshold", str(exc))
            return
        self._report = None
        self._candidate_by_id.clear()
        self._removals.clear()
        self._keeps.clear()
        self._compare_ids.clear()
        self._render_report()
        self.progress.setRange(0, 0)
        self.progress.setFormat("Reading library snapshot…")
        self.scan_summary.setText("Scanning current library files. Cancel discards any incomplete result.")
        self.scan_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        worker = DuplicateScanWorker(self._database_path, threshold, self)
        worker.progress.connect(self._on_scan_progress)
        worker.report_ready.connect(self._on_scan_report)
        worker.failed.connect(self._on_task_failed)
        worker.finished.connect(self._on_worker_finished)
        self._scan_worker = worker
        worker.start()
        self.status_message.emit("Duplicate scan started.")

    def cancel_active_task(self) -> None:
        if self._scan_worker is not None and self._scan_worker.isRunning():
            self._scan_worker.cancel()
            self.progress.setFormat("Cancelling scan…")
            return
        if self._preview_worker is not None and self._preview_worker.isRunning():
            self._preview_worker.cancel()
            self.progress.setFormat("Cancelling preview…")

    def _on_scan_progress(self, done: int, total: int, status: str) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        self.progress.setFormat(f"{status}: {done}/{total}")

    def _on_scan_report(self, report: object) -> None:
        if report is None:
            self._report = None
            self.scan_summary.setText("Scan cancelled before a complete library snapshot was read; partial results were discarded.")
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setFormat("Cancelled")
            self._render_report()
            return
        if not isinstance(report, DuplicateScanReport):
            self._on_task_failed("Duplicate scan returned an invalid result.")
            return
        if report.cancelled or not report.completed:
            self._report = None
            self.scan_summary.setText("Scan cancelled; partial results were discarded.")
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setFormat("Cancelled")
            self._render_report()
            self.status_message.emit("Duplicate scan cancelled; no partial groups were kept.")
            return
        self._report = report
        self._candidate_by_id = {candidate.wallpaper_id: candidate for candidate in report.candidates}
        self.issues_button.setEnabled(bool(report.issues))
        exact_count = len(report.exact_groups)
        near_count = len(report.near_groups)
        issue_count = len(report.issues)
        finished = datetime.fromisoformat(report.finished_at).astimezone().strftime("%Y-%m-%d %H:%M")
        self.scan_summary.setText(
            f"Completed {finished} · checked {report.scanned_records}/{report.total_records} records · "
            f"{issue_count} file/record issues. Near similarity scores use Hamming distance, not probability."
        )
        self.progress.setRange(0, max(report.total_records, 1))
        self.progress.setValue(report.scanned_records)
        self.progress.setFormat("Scan complete")
        self._render_report()
        self.status_message.emit(f"Duplicate scan complete: {exact_count} exact groups, {near_count} near groups.")

    def _render_report(self) -> None:
        if self._report is None:
            self.exact_tab.set_groups(())
            self.near_tab.set_groups(())
            self.kpi_label.setText("Exact groups: 0   ·   Near groups: 0   ·   Candidate files: 0   ·   Exact-only redundant bytes: 0 B")
            self.preview_button.setEnabled(False)
            self.compare_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.issues_button.setEnabled(False)
            self._refresh_selection_summary()
            return
        report = self._report
        self.exact_tab.set_groups(report.exact_groups)
        self.near_tab.set_groups(report.near_groups)
        self.kpi_label.setText(
            f"Exact groups: {len(report.exact_groups)}   ·   Near groups: {len(report.near_groups)}   ·   "
            f"Candidate files: {report.candidate_count}   ·   Exact-only redundant bytes: "
            f"{_format_size(report.exact_redundant_bytes_estimate)}"
        )
        self.preview_button.setEnabled(True)
        self.compare_button.setEnabled(2 <= len(self._compare_ids) <= 4)
        self.delete_button.setEnabled(False)
        self._refresh_selection_summary()

    def _on_choice_changed(self, group_id: str, item_id: int, remove: bool, keep: bool) -> None:
        if keep:
            self._keeps[group_id] = item_id
            self._removals.setdefault(group_id, set()).discard(item_id)
        elif self._keeps.get(group_id) == item_id:
            self._keeps.pop(group_id, None)
        if remove and self._keeps.get(group_id) != item_id:
            self._removals.setdefault(group_id, set()).add(item_id)
        else:
            self._removals.setdefault(group_id, set()).discard(item_id)
        self._refresh_selection_summary()
        self.status_message.emit("Duplicate review choices updated.")

    def _on_bulk_choice(self, group_id: str, item_ids: object, action: str) -> None:
        ids = set(item_ids) if isinstance(item_ids, (set, frozenset)) else set()
        if action == "clear":
            self._removals.pop(group_id, None)
            self._keeps.pop(group_id, None)
            self._compare_ids.difference_update(ids)
        elif action == "all":
            keep_id = self._keeps.get(group_id)
            if keep_id is None:
                self.status_message.emit("Choose a Keep file in this group first.")
                return
            self._removals[group_id] = ids - {keep_id}
        self.exact_tab.refresh_choices()
        self.near_tab.refresh_choices()
        self._refresh_selection_summary()

    def _on_compare_choice_changed(self, item_id: int, checked: bool) -> None:
        if checked:
            self._compare_ids.add(item_id)
        else:
            self._compare_ids.discard(item_id)
        self.compare_button.setEnabled(2 <= len(self._compare_ids) <= 4)
        self.status_message.emit(f"Comparison selection: {len(self._compare_ids)} file(s).")

    def compare_selected(self) -> None:
        selected = tuple(
            self._candidate_by_id[item_id]
            for item_id in sorted(self._compare_ids)
            if item_id in self._candidate_by_id
        )
        if not 2 <= len(selected) <= 4:
            QMessageBox.information(self, "Choose files to compare", "Select between two and four files with the Remove checkboxes, then compare them.")
            return
        preview_ids = {
            item_id
            for group_ids in self._removals.values()
            for item_id in group_ids
        }
        dialog = ComparisonDialog(
            selected,
            self,
            keep_ids=set(self._keeps.values()),
            preview_ids=preview_ids,
        )
        dialog.exec()

    def preview_selected(self) -> None:
        if self._report is None:
            return
        removals = {group_id: set(ids) for group_id, ids in self._removals.items() if ids}
        if not removals:
            QMessageBox.information(self, "No files selected", "Select at least one candidate for a preview, and explicitly choose a retained file in each selected group.")
            return
        missing_keeps = [group_id for group_id in removals if group_id not in self._keeps]
        if missing_keeps:
            QMessageBox.warning(self, "Choose a retained file", "Choose one explicit Keep file in every group that has removal selections.")
            return
        self.preview_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Rechecking selected files…")
        worker = CleanupPreviewWorker(self._report, removals, self._keeps, self)
        worker.preview_ready.connect(self._show_preview)
        worker.failed.connect(self._on_preview_failed)
        worker.finished.connect(self._on_worker_finished)
        self._preview_worker = worker
        worker.start()

    def _show_preview(self, preview: object) -> None:
        if not isinstance(preview, CleanupPreview):
            self._on_preview_failed("Preview returned an invalid result.")
            return
        details = ["Selected files would be paired with these retained files:"]
        for entry in preview.entries:
            details.append(
                f"\nKeep: {entry.retained.display_name} — {entry.retained.canonical_path.as_posix()}"
            )
            for candidate in entry.selected_for_removal:
                details.append(
                    f"Preview only: {candidate.display_name} — {candidate.canonical_path.as_posix()} "
                    f"({_format_size(candidate.size_bytes)})"
                )
        message = QMessageBox(self)
        message.setWindowTitle("Read-only cleanup preview")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText("Cleanup plan revalidated")
        message.setInformativeText(
            f"Selected files: {preview.files_selected}\n"
            f"Potential bytes selected: {_format_size(preview.estimated_bytes)}\n\n"
            "This preview changed no files and no database rows. File removal is disabled until a "
            "verified recoverable Recycle Bin or quarantine workflow is available."
        )
        message.setDetailedText("\n".join(details))
        message.setStandardButtons(QMessageBox.StandardButton.Ok)
        message.exec()
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat("Preview complete · no changes made")

    def _on_preview_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Preview could not be created", message)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Preview not created")

    def _show_issues(self) -> None:
        if self._report is None or not self._report.issues:
            return
        visible = self._report.issues[:100]
        lines = [f"{issue.filename} — {issue.message}" for issue in visible]
        if len(self._report.issues) > len(visible):
            lines.append(f"…and {len(self._report.issues) - len(visible)} more.")
        QMessageBox.information(
            self,
            "Scan issues",
            "\n".join(lines),
        )

    def _on_task_failed(self, message: str) -> None:
        self._report = None
        self.issues_button.setEnabled(False)
        self._render_report()
        self.scan_summary.setText(message)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Task failed")
        self.status_message.emit(message)

    def _on_worker_finished(self) -> None:
        self.scan_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.preview_button.setEnabled(self._report is not None)
        self.compare_button.setEnabled(2 <= len(self._compare_ids) <= 4)
        self._scan_worker = None
        self._preview_worker = None

    def _task_running(self) -> bool:
        return bool(
            (self._scan_worker is not None and self._scan_worker.isRunning())
            or (self._preview_worker is not None and self._preview_worker.isRunning())
        )

    def _refresh_selection_summary(self) -> None:
        files = sum(len(ids) for ids in self._removals.values())
        groups = sum(bool(ids) for ids in self._removals.values())
        if files == 0:
            self.selection_summary.setText("No files selected for preview. Choose a Keep file before using “Select all except retained”.")
        else:
            missing = sum(group_id not in self._keeps for group_id, ids in self._removals.items() if ids)
            self.selection_summary.setText(
                f"Preview selection: {files} file(s) across {groups} group(s) · "
                f"explicit retained choice missing in {missing} group(s)."
            )

    def shutdown(self) -> None:
        """Cancel and join workers before the main window closes its database."""
        for worker in (self._scan_worker, self._preview_worker):
            if worker is not None and worker.isRunning():
                worker.cancel()
                worker.wait()
