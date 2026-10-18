"""
Sandy Wallpaper Studio — Search & Filter Toolbar Component
===========================================================
A horizontal toolbar providing: text search input, category filter,
resolution filter, orientation filter, source filter, and a favorites toggle.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
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
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            QFrame#SearchFilterBar {{
                background-color: {ds.BG_SURFACE};
                border-bottom: 1px solid {ds.BG_BORDER};
                border-top: 1px solid {ds.BG_BORDER};
            }}
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(ds.SPACE_LG, 0, ds.SPACE_LG, 0)
        layout.setSpacing(ds.SPACE_SM)

        # ---- Search input ----
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("  🔍  Search wallpapers…")
        self._search_input.setFixedHeight(34)
        self._search_input.setMinimumWidth(240)
        self._search_input.textChanged.connect(lambda: self._debounce.start())
        layout.addWidget(self._search_input)

        layout.addSpacing(ds.SPACE_SM)

        # ---- Category filter ----
        layout.addWidget(self._make_label("Category"))
        self._cat_combo = self._make_combo(
            [("All Categories", "")]
            + [(c, c) for c in self._categories]
        )
        self._cat_combo.currentIndexChanged.connect(self._emit_search)
        layout.addWidget(self._cat_combo)

        # ---- Resolution filter ----
        layout.addWidget(self._make_label("Resolution"))
        self._res_combo = self._make_combo(self._RESOLUTION_OPTIONS)
        self._res_combo.currentIndexChanged.connect(self._emit_search)
        layout.addWidget(self._res_combo)

        # ---- Orientation filter ----
        layout.addWidget(self._make_label("Orientation"))
        self._orient_combo = self._make_combo([
            ("Any", ""),
            ("Landscape", "landscape"),
            ("Portrait", "portrait"),
        ])
        self._orient_combo.currentIndexChanged.connect(self._emit_search)
        layout.addWidget(self._orient_combo)

        # ---- Sort ----
        layout.addWidget(self._make_label("Sort"))
        self._sort_combo = self._make_combo(self._SORT_OPTIONS)
        self._sort_combo.currentIndexChanged.connect(self._emit_search)
        layout.addWidget(self._sort_combo)

        layout.addStretch()

        # ---- Favorites toggle ----
        self._fav_btn = QPushButton("♥  Favorites")
        self._fav_btn.setCheckable(True)
        self._fav_btn.setFixedHeight(34)
        self._fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fav_btn.setStyleSheet(self._fav_off_style())
        self._fav_btn.clicked.connect(self._on_fav_toggle)
        layout.addWidget(self._fav_btn)

        # ---- Random ----
        rand_btn = QPushButton("⚄  Random")
        rand_btn.setFixedHeight(34)
        rand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rand_btn.setToolTip("Apply a random wallpaper from the library")
        rand_btn.clicked.connect(self.random_requested.emit)
        layout.addWidget(rand_btn)

        # ---- Import ----
        import_btn = QPushButton("⊕  Import Folder")
        import_btn.setFixedHeight(34)
        import_btn.setObjectName("accent")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self.import_requested.emit)
        layout.addWidget(import_btn)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_XS}px;")
        return lbl

    def _make_combo(self, items: list[tuple[str, str]]) -> QComboBox:
        combo = QComboBox()
        combo.setFixedHeight(34)
        for label, data in items:
            combo.addItem(label, userData=data)
        return combo

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
