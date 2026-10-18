"""Review and confirm one fully revalidated duplicate cleanup plan."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
)

from app.services.duplicate_scan_service import CleanupPreview
from app.ui import design_system as ds


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


class CleanupConfirmationDialog(QDialog):
    """Require review of each kept and targeted path before moving any file."""

    def __init__(self, preview: CleanupPreview, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm duplicate cleanup")
        self.setAccessibleName("Confirm duplicate cleanup")
        self.setMinimumSize(620, 480)
        self.resize(820, 640)

        layout = QVBoxLayout(self)
        heading = QLabel("Review every target before continuing")
        heading.setStyleSheet(
            f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_LG}px; font-weight: 700;"
        )
        layout.addWidget(heading)

        near_count = sum(entry.group_id.startswith("near:") for entry in preview.entries)
        summary = QLabel(
            f"Groups: {len(preview.entries)}   |   Files selected: {preview.files_selected}"
            f"   |   Selected file sizes (estimate): {_format_size(preview.estimated_bytes)}\n"
            "Method: Windows Recycle Bin. The operation has no permanent-delete fallback.\n"
            "The Recycle Bin may continue using disk space until its contents are emptied."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet(f"color: {ds.TEXT_SECONDARY};")
        layout.addWidget(summary)

        warning = QLabel(
            "Near-image similarity does not prove interchangeability. Each listed target is an "
            "individual file selection. A failed file operation stops the remaining targets."
            if near_count
            else "Exact targets were byte-compared with their retained file. A failed file operation "
            "stops the remaining targets."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(f"color: {ds.WARNING};")
        layout.addWidget(warning)

        details = []
        for number, entry in enumerate(preview.entries, start=1):
            group_kind = "near-match" if entry.group_id.startswith("near:") else "exact duplicate"
            details.append(f"Group {number} ({group_kind})")
            details.append(
                f"  Retain: {entry.retained.display_name} | {_format_size(entry.retained.size_bytes)}"
            )
            details.append(f"  {entry.retained.canonical_path}")
            for target in entry.selected_for_removal:
                details.append(
                    f"  Move to Recycle Bin: {target.display_name} | "
                    f"{_format_size(target.size_bytes)}"
                )
                details.append(f"  {target.canonical_path}")
            details.append("")

        file_list = QTextBrowser()
        file_list.setAccessibleName("Retained files and Recycle Bin targets")
        file_list.setOpenExternalLinks(False)
        file_list.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        file_list.setPlainText("\n".join(details).rstrip())
        file_list.setStyleSheet(
            f"background-color: {ds.BG_SURFACE}; color: {ds.TEXT_PRIMARY}; "
            f"border: 1px solid {ds.BG_BORDER}; padding: 8px;"
        )
        layout.addWidget(file_list, stretch=1)

        buttons = QDialogButtonBox(self)
        self.confirm_button = buttons.addButton(
            "Move selected files to Recycle Bin",
            QDialogButtonBox.ButtonRole.DestructiveRole,
        )
        self.confirm_button.setAccessibleName("Move selected files to Recycle Bin")
        self.cancel_button = buttons.addButton(
            QDialogButtonBox.StandardButton.Cancel
        )
        self.cancel_button.setDefault(True)
        self.cancel_button.setFocus()
        self.confirm_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self.setStyleSheet(
            f"QDialog {{ background-color: {ds.BG_DEEP}; }}"
            f"QPushButton:focus {{ border: 2px solid {ds.ACCENT_LIGHT}; }}"
            f"QTextBrowser:focus {{ border: 2px solid {ds.ACCENT_LIGHT}; }}"
        )


__all__ = ["CleanupConfirmationDialog"]
