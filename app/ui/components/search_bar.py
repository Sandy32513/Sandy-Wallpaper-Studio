"""
Sandy Wallpaper Studio — Search & Filter Toolbar Component
===========================================================
A horizontal toolbar providing: text search input, category filter,
resolution filter, orientation filter, source filter, and a favorites toggle.
"""
from __future__ import annotations

from typing import Optional, override

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.ui import design_system as ds


class SearchFilterBar(QFrame):
    """Horizontal search and filter toolbar.

    Signals:
        search_changed: Emits (query, filters_dict) whenever any filter changes.
        import_requested: User clicked the Import Folder button.
        random_requested: User clicked the Random Wallpaper button.
    """

    search_changed = Signal(dict)
    import_requested = Signal()
    random_requested = Signal()

    _RESOLUTION_OPTIONS = [
        ("Any Resolution", ""),
        ("FHD (1080p)", "FHD"),
        ("QHD (1440p)", "QHD"),
        ("4K", "4K"),
        ("5K", "5K"),
        ("8K", "8K"),
        ("Ultrawide QHD", "UW-QHD"),
        ("Ultrawide 5K", "UW-5K"),
    ]

    _SORT_OPTIONS = [
        ("Newest First", "download_date DESC"),
        ("Oldest First", "download_date ASC"),
        ("Most Used", "usage_count DESC"),
        ("By Title", "title ASC"),
        ("Largest", "file_size DESC"),
    ]

    def __init__(
        self,
        categories: Optional[list[str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._categories = categories or []
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self._emit_search)

        self.setObjectName("SearchFilterBar")
        self._layout_mode = ""
        self.setStyleSheet(f"""
            QFrame#SearchFilterBar {{
                background-color: {ds.BG_SURFACE};
                border-bottom: 1px solid {ds.BG_BORDER};
                border-top: 1px solid {ds.BG_BORDER};
            }}
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(ds.SPACE_LG, ds.SPACE_SM, ds.SPACE_LG, ds.SPACE_SM)
        self._layout.setHorizontalSpacing(ds.SPACE_SM)
        self._layout.setVerticalSpacing(ds.SPACE_SM)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search wallpapers…")
        self._search_input.setAccessibleName("Search wallpapers")
        self._search_input.setToolTip("Search wallpaper titles, filenames, and metadata")
        self._search_input.setFixedHeight(34)
        self._search_input.setMinimumWidth(160)
        self._search_input.textChanged.connect(lambda: self._debounce.start())
        self._cat_combo = self._make_combo(
            [("All Categories", "")]
            + [(c, c) for c in self._categories]
        )
        self._cat_combo.setAccessibleName("Filter by category")
        self._cat_combo.setToolTip("Filter by category")
        self._cat_combo.currentIndexChanged.connect(self._emit_search)
        self._res_combo = self._make_combo(self._RESOLUTION_OPTIONS)
        self._res_combo.setAccessibleName("Filter by resolution")
        self._res_combo.setToolTip("Filter by resolution")
        self._res_combo.currentIndexChanged.connect(self._emit_search)
        self._orient_combo = self._make_combo([
            ("Any", ""),
            ("Landscape", "landscape"),
            ("Portrait", "portrait"),
        ])
        self._orient_combo.setAccessibleName("Filter by orientation")
        self._orient_combo.setToolTip("Filter by orientation")
        self._orient_combo.currentIndexChanged.connect(self._emit_search)
        self._sort_combo = self._make_combo(self._SORT_OPTIONS)
        self._sort_combo.setAccessibleName("Sort wallpapers")
        self._sort_combo.setToolTip("Sort wallpapers")
        self._sort_combo.currentIndexChanged.connect(self._emit_search)
        self._fav_btn = QPushButton("♥  Favorites")
        self._fav_btn.setCheckable(True)
        self._fav_btn.setAccessibleName("Show favorite wallpapers only")
        self._fav_btn.setFixedHeight(34)
        self._fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fav_btn.setStyleSheet(self._fav_off_style())
        self._fav_btn.clicked.connect(self._on_fav_toggle)
        self._random_btn = QPushButton("⚄  Random")
        self._random_btn.setAccessibleName("Apply a random wallpaper")
        self._random_btn.setFixedHeight(34)
        self._random_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._random_btn.setToolTip("Apply a random wallpaper from the library")
        self._random_btn.clicked.connect(self.random_requested.emit)
        self._import_btn = QPushButton("⊕  Import Folder")
        self._import_btn.setAccessibleName("Import a wallpaper folder")
        self._import_btn.setFixedHeight(34)
        self._import_btn.setObjectName("accent")
        self._import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_btn.clicked.connect(self.import_requested.emit)
        self._apply_layout_mode()

    def _make_combo(self, items: list[tuple[str, str]]) -> QComboBox:
        combo = QComboBox()
        combo.setFixedHeight(34)
        for label, data in items:
            combo.addItem(label, userData=data)
        return combo

    @override
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_layout_mode()

    def _apply_layout_mode(self) -> None:
        width = self.width()
        mode = "wide" if width >= 1200 else "medium" if width >= 760 else "compact"
        if mode == self._layout_mode:
            return
        self._layout_mode = mode
        while self._layout.count():
            self._layout.takeAt(0)
        controls = (
            self._search_input, self._cat_combo, self._res_combo,
            self._orient_combo, self._sort_combo, self._fav_btn,
            self._random_btn, self._import_btn,
        )
        for control in controls:
            control.setMinimumWidth(0 if control is not self._search_input else 160)

        if mode == "wide":
            self.setFixedHeight(52)
            self._layout.addWidget(self._search_input, 0, 0, 1, 2)
            for col, combo in enumerate(controls[1:5], start=2):
                self._layout.addWidget(combo, 0, col)
            for col, button in enumerate(controls[5:], start=6):
                self._layout.addWidget(button, 0, col)
            self._layout.setColumnStretch(0, 1)
            self._layout.setColumnStretch(1, 1)
        elif mode == "medium":
            self.setFixedHeight(92)
            self._layout.addWidget(self._search_input, 0, 0, 1, 2)
            for col, button in enumerate(controls[5:], start=2):
                self._layout.addWidget(button, 0, col)
            for col, combo in enumerate(controls[1:5]):
                self._layout.addWidget(combo, 1, col)
            self._layout.setColumnStretch(0, 1)
            self._layout.setColumnStretch(1, 1)
        else:
            self.setFixedHeight(132)
            self._layout.addWidget(self._search_input, 0, 0, 1, 3)
            self._layout.addWidget(self._fav_btn, 0, 3)
            for col, widget in enumerate(controls[1:4]):
                self._layout.addWidget(widget, 1, col)
            self._layout.addWidget(self._sort_combo, 2, 0, 1, 2)
            self._layout.addWidget(self._random_btn, 2, 2)
            self._layout.addWidget(self._import_btn, 2, 3)
            self._layout.setColumnStretch(0, 1)
            self._layout.setColumnStretch(1, 1)
            self._layout.setColumnStretch(2, 1)
            self._layout.setColumnStretch(3, 1)

    def _on_fav_toggle(self) -> None:
        if self._fav_btn.isChecked():
            self._fav_btn.setStyleSheet(self._fav_on_style())
        else:
            self._fav_btn.setStyleSheet(self._fav_off_style())
        self._emit_search()

    def _fav_off_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {ds.BG_BORDER};
                color: {ds.TEXT_SECONDARY};
                border-radius: 6px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                border-color: {ds.DANGER};
                color: {ds.DANGER};
            }}
        """

    def _fav_on_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: rgba(239, 68, 68, 0.15);
                border: 1px solid {ds.DANGER};
                color: {ds.DANGER};
                border-radius: 6px;
                padding: 0 12px;
            }}
        """

    def _emit_search(self) -> None:
        filters = {
            "query":         self._search_input.text().strip(),
            "category":      self._cat_combo.currentData() or "",
            "resolution":    self._res_combo.currentData() or "",
            "orientation":   self._orient_combo.currentData() or "",
            "order_by":      self._sort_combo.currentData() or "download_date DESC",
            "favorites_only": self._fav_btn.isChecked(),
        }
        self.search_changed.emit(filters)

    def update_categories(self, categories: list[str]) -> None:
        """Refresh category options."""
        self._cat_combo.blockSignals(True)
        self._cat_combo.clear()
        self._cat_combo.addItem("All Categories", userData="")
        for c in categories:
            self._cat_combo.addItem(c, userData=c)
        self._cat_combo.blockSignals(False)

    @property
    def current_filters(self) -> dict:
        return {
            "query":         self._search_input.text().strip(),
            "category":      self._cat_combo.currentData() or "",
            "resolution":    self._res_combo.currentData() or "",
            "orientation":   self._orient_combo.currentData() or "",
            "order_by":      self._sort_combo.currentData() or "download_date DESC",
            "favorites_only": self._fav_btn.isChecked(),
        }
