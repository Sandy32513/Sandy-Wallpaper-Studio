"""
Sandy Wallpaper Studio — Sidebar Navigation Component
======================================================
The left navigation panel with icon + label menu items
and a collapsible/expandable state.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.constants import APP_VERSION
from app.ui import design_system as ds


class SidebarItem(QPushButton):
    """A single sidebar navigation item (icon emoji + label)."""

    def __init__(
        self,
        icon: str,
        label: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._icon = icon
        self._label = label
        self._active = False

        self.setCheckable(False)
        self.setFixedHeight(ds.SIDEBAR_ITEM_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(active=False)

    def _apply_style(self, active: bool) -> None:
        if active:
            bg = ds.SIDEBAR_ACTIVE
            color = ds.TEXT_PRIMARY
            left_border = f"border-left: 3px solid {ds.ACCENT_PRIMARY};"
        else:
            bg = "transparent"
            color = ds.TEXT_SECONDARY
            left_border = "border-left: 3px solid transparent;"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: none;
                {left_border}
                border-radius: 0px;
                padding: 0px;
                text-align: left;
                font-size: {ds.FONT_SIZE_MD}px;
            }}
            QPushButton:hover {{
                background-color: {ds.SIDEBAR_HOVER};
                color: {ds.TEXT_PRIMARY};
                border-left: 3px solid {ds.ACCENT_PRIMARY};
            }}
        """)
        self.setText(f"  {self._icon}  {self._label}")
        self._active = active

    def set_active(self, active: bool) -> None:
        self._apply_style(active)


class Sidebar(QFrame):
    """Left navigation sidebar."""

    # Emits the navigation key (e.g. "library", "search") when clicked
    nav_changed = Signal(str)

    _ITEMS: list[tuple[str, str, str]] = [
        ("dashboard", "⊞",  "Dashboard"),
        ("discover",  "⊕",  "Discover"),
        ("library",   "▦",  "Library"),
        ("categories","◈",  "Categories"),
        ("favorites", "♥",  "Favorites"),
        ("history",   "↺",  "History"),
        ("duplicates","⊘",  "Duplicates"),
        ("downloads", "⬇",  "Downloads"),
        ("settings",  "⚙",  "Settings"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(ds.SIDEBAR_WIDTH)
        self.setObjectName("Sidebar")
        self.setStyleSheet(f"""
            QFrame#Sidebar {{
                background-color: {ds.SIDEBAR_BG};
                border-right: 1px solid {ds.BG_BORDER};
            }}
        """)

        self._current_key = "dashboard"
        self._buttons: dict[str, SidebarItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # App logo area
        logo = QLabel()
        logo.setFixedHeight(64)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setText("Sandy")
        logo.setStyleSheet(f"""
            QLabel {{
                color: {ds.ACCENT_PRIMARY};
                font-size: {ds.FONT_SIZE_XL}px;
                font-weight: 800;
                border-bottom: 1px solid {ds.BG_BORDER};
                background-color: {ds.SIDEBAR_BG};
                letter-spacing: 1px;
            }}
        """)
        layout.addWidget(logo)

        # Nav items
        for key, icon, label in self._ITEMS:
            btn = SidebarItem(icon=icon, label=label)
            btn.clicked.connect(lambda checked, k=key: self._on_click(k))
            layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addStretch()

        # Version label at the bottom
        ver = QLabel(APP_VERSION)
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(f"color: {ds.TEXT_DISABLED}; font-size: {ds.FONT_SIZE_XS}px; padding: 8px;")
        layout.addWidget(ver)

        # Activate default
        self._buttons[self._current_key].set_active(True)

    def _on_click(self, key: str) -> None:
        if key == self._current_key:
            return
        self._buttons[self._current_key].set_active(False)
        self._current_key = key
        self._buttons[key].set_active(True)
        self.nav_changed.emit(key)

    def navigate_to(self, key: str) -> None:
        """Programmatically switch the active item."""
        self._on_click(key)
