"""
Sandy Wallpaper Studio — GUI Design System
==========================================
Central palette, typography, spacing, and reusable style constants
for the dark-first PySide6 interface.
"""
from __future__ import annotations

# ============================================================
# Color Palette — Obsidian Dark Theme
# ============================================================
# Backgrounds
BG_DEEP        = "#0d0f14"    # Deepest background (window bg)
BG_SURFACE     = "#13161e"    # Panel / card surface
BG_ELEVATED    = "#1a1d27"    # Hover / elevated card
BG_BORDER      = "#252836"    # Border / separator
BG_INPUT       = "#1e2130"    # Input field background

# Sidebar
SIDEBAR_BG     = "#0f1119"
SIDEBAR_HOVER  = "#181c28"
SIDEBAR_ACTIVE = "#1e2540"

# Accent — electric indigo / violet
ACCENT_PRIMARY = "#6c63ff"    # Primary accent: buttons, active, links
ACCENT_LIGHT   = "#9b94ff"    # Light accent: icons on dark
ACCENT_DARK    = "#4a43c8"    # Pressed / deep accent
ACCENT_GLOW    = "rgba(108, 99, 255, 0.20)"  # Soft glow on selection

# Semantic colors
SUCCESS        = "#22c55e"
WARNING        = "#f59e0b"
DANGER         = "#ef4444"
INFO           = "#38bdf8"

# Text
TEXT_PRIMARY   = "#e8eaf0"    # Main text
TEXT_SECONDARY = "#8a90a8"    # Muted text, labels
TEXT_DISABLED  = "#4a4e62"    # Disabled state
TEXT_LINK      = ACCENT_LIGHT

# Thumbnail / card overlay
OVERLAY_DARK   = "rgba(13, 15, 20, 0.78)"
BADGE_BG       = "rgba(26, 29, 39, 0.88)"

# ============================================================
# Typography (loaded via QFontDatabase in main window)
# ============================================================
FONT_FAMILY    = "Inter"
FONT_FALLBACK  = "Segoe UI"

FONT_SIZE_XS   = 10
FONT_SIZE_SM   = 11
FONT_SIZE_MD   = 13
FONT_SIZE_LG   = 15
FONT_SIZE_XL   = 18
FONT_SIZE_2XL  = 22
FONT_SIZE_3XL  = 28

# ============================================================
# Spacing (px)
# ============================================================
SPACE_XS   = 4
SPACE_SM   = 8
SPACE_MD   = 12
SPACE_LG   = 16
SPACE_XL   = 24
SPACE_2XL  = 32
SPACE_3XL  = 48

# ============================================================
# Card Dimensions
# ============================================================
CARD_WIDTH    = 280
CARD_HEIGHT   = 200
CARD_THUMB_H  = 157       # ~16:9 thumbnail inside card
CARD_RADIUS   = 10        # border-radius px

# Thumbnail display size in the grid (pixels)
THUMB_GRID_W  = 280
THUMB_GRID_H  = 157

# ============================================================
# Sidebar Dimensions
# ============================================================
SIDEBAR_WIDTH         = 210
SIDEBAR_ICON_SIZE     = 18
SIDEBAR_ITEM_HEIGHT   = 40

# ============================================================
# Animation Timings (ms)
# ============================================================
ANIM_FAST   = 120
ANIM_NORMAL = 200
ANIM_SLOW   = 350

# ============================================================
# Global Application Stylesheet
# ============================================================
def build_stylesheet() -> str:
    """Return the global QSS stylesheet for the application."""
    return f"""
/* ============================================================
   Global Reset
   ============================================================ */
* {{
    font-family: "{FONT_FAMILY}", "{FONT_FALLBACK}", sans-serif;
    font-size: {FONT_SIZE_MD}px;
    color: {TEXT_PRIMARY};
    outline: none;
}}

QMainWindow, QDialog {{
    background-color: {BG_DEEP};
}}

/* ============================================================
   ScrollBar — thin, dark, modern
   ============================================================ */
QScrollBar:vertical {{
    background: {BG_SURFACE};
    width: 7px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BG_BORDER};
    min-height: 30px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_PRIMARY};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: {BG_SURFACE};
    height: 7px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {BG_BORDER};
    min-width: 30px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {ACCENT_PRIMARY};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ============================================================
   Tooltip
   ============================================================ */
QToolTip {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_BORDER};
    padding: 5px 8px;
    border-radius: 4px;
    font-size: {FONT_SIZE_SM}px;
}}

/* ============================================================
   Push Buttons — Primary
   ============================================================ */
QPushButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    font-size: {FONT_SIZE_MD}px;
}}
QPushButton:hover {{
    background-color: {BG_BORDER};
    border-color: {ACCENT_PRIMARY};
}}
QPushButton:pressed {{
    background-color: {ACCENT_DARK};
    border-color: {ACCENT_PRIMARY};
}}
QPushButton:disabled {{
    color: {TEXT_DISABLED};
    border-color: {BG_BORDER};
    background-color: {BG_SURFACE};
}}
QPushButton#accent {{
    background-color: {ACCENT_PRIMARY};
    border-color: {ACCENT_PRIMARY};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#accent:hover {{
    background-color: {ACCENT_LIGHT};
    border-color: {ACCENT_LIGHT};
}}
QPushButton#accent:pressed {{
    background-color: {ACCENT_DARK};
    border-color: {ACCENT_DARK};
}}
QPushButton#danger {{
    background-color: transparent;
    border-color: {DANGER};
    color: {DANGER};
}}
QPushButton#danger:hover {{
    background-color: {DANGER};
    color: #ffffff;
}}
QPushButton#ghost {{
    background-color: transparent;
    border-color: transparent;
    color: {TEXT_SECONDARY};
}}
QPushButton#ghost:hover {{
    color: {TEXT_PRIMARY};
    background-color: {BG_ELEVATED};
}}

/* ============================================================
   Line Edit / Search
   ============================================================ */
QLineEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_BORDER};
    border-radius: 6px;
    padding: 7px 12px;
    font-size: {FONT_SIZE_MD}px;
    selection-background-color: {ACCENT_PRIMARY};
}}
QLineEdit:focus {{
    border-color: {ACCENT_PRIMARY};
    background-color: {BG_ELEVATED};
}}
QLineEdit::placeholder {{
    color: {TEXT_DISABLED};
}}

/* ============================================================
   ComboBox
   ============================================================ */
QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    min-width: 110px;
}}
QComboBox:hover {{
    border-color: {ACCENT_PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_BORDER};
    selection-background-color: {ACCENT_PRIMARY};
    padding: 4px;
}}

/* ============================================================
   Labels
   ============================================================ */
QLabel {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
}}
QLabel#title {{
    font-size: {FONT_SIZE_XL}px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
QLabel#subtitle {{
    font-size: {FONT_SIZE_MD}px;
    color: {TEXT_SECONDARY};
}}
QLabel#badge {{
    background-color: {BG_BORDER};
    color: {TEXT_SECONDARY};
    border-radius: 4px;
    padding: 2px 7px;
    font-size: {FONT_SIZE_SM}px;
}}
QLabel#accent_badge {{
    background-color: {ACCENT_GLOW};
    color: {ACCENT_LIGHT};
    border: 1px solid {ACCENT_PRIMARY};
    border-radius: 4px;
    padding: 2px 7px;
    font-size: {FONT_SIZE_SM}px;
}}

/* ============================================================
   CheckBox
   ============================================================ */
QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BG_BORDER};
    background-color: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT_PRIMARY};
    border-color: {ACCENT_PRIMARY};
}}

/* ============================================================
   Slider
   ============================================================ */
QSlider::groove:horizontal {{
    height: 4px;
    background: {BG_BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    background: {ACCENT_PRIMARY};
    border-radius: 7px;
    margin: -5px 0;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT_PRIMARY};
    border-radius: 2px;
}}

/* ============================================================
   Progress Bar
   ============================================================ */
QProgressBar {{
    background-color: {BG_BORDER};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    font-size: {FONT_SIZE_XS}px;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {ACCENT_PRIMARY};
    border-radius: 4px;
}}

/* ============================================================
   Splitter
   ============================================================ */
QSplitter::handle {{
    background-color: {BG_BORDER};
    width: 1px;
    height: 1px;
}}

/* ============================================================
   Tab Widget
   ============================================================ */
QTabWidget::pane {{
    border: 1px solid {BG_BORDER};
    border-radius: 6px;
    background-color: {BG_SURFACE};
}}
QTabBar::tab {{
    background-color: {BG_ELEVATED};
    color: {TEXT_SECONDARY};
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    min-width: 80px;
}}
QTabBar::tab:selected {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border-bottom: 2px solid {ACCENT_PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    background-color: {BG_BORDER};
    color: {TEXT_PRIMARY};
}}

/* ============================================================
   Status Bar
   ============================================================ */
QStatusBar {{
    background-color: {BG_SURFACE};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BG_BORDER};
    font-size: {FONT_SIZE_SM}px;
    padding: 2px 8px;
}}
"""
