"""
Sandy Wallpaper Studio - Application Constants
================================================
Central location for all application-wide constants.
"""

from pathlib import Path

# ============================================================
# Application Identity
# ============================================================
APP_NAME = "Sandy Wallpaper Studio"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Sandy"
APP_DESCRIPTION = "Professional 4K/5K/8K Wallpaper Management for Windows"

# ============================================================
# Resolution Definitions
# ============================================================
# Minimum pixel dimensions for each resolution class.
# An image must meet BOTH width AND height thresholds.
RESOLUTION_CLASSES = {
    "8K": {"min_width": 7680, "min_height": 4320},
    "5K": {"min_width": 5120, "min_height": 2880},
    "4K": {"min_width": 3840, "min_height": 2160},
    "UW-5K": {"min_width": 5120, "min_height": 2160},
    "UW-QHD": {"min_width": 3440, "min_height": 1440},
    "QHD": {"min_width": 2560, "min_height": 1440},
    "FHD": {"min_width": 1920, "min_height": 1080},
}

# Minimum resolution accepted into the library
# Images below this are rejected
MIN_ACCEPTED_WIDTH = 1920
MIN_ACCEPTED_HEIGHT = 1080

# ============================================================
# Aspect Ratios
# ============================================================
ASPECT_RATIOS = {
    "16:9": 16 / 9,
    "16:10": 16 / 10,
    "21:9": 21 / 9,
    "32:9": 32 / 9,
    "4:3": 4 / 3,
    "3:2": 3 / 2,
    "1:1": 1.0,
}

# Tolerance for aspect ratio matching (e.g., 0.05 = 5%)
ASPECT_RATIO_TOLERANCE = 0.05

# ============================================================
# Supported Image Formats
# ============================================================
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}
OPTIONAL_FORMATS = {".avif"}
ALL_IMAGE_FORMATS = SUPPORTED_FORMATS | OPTIONAL_FORMATS

# ============================================================
# Default Library Paths (relative to user's Pictures folder)
# ============================================================
DEFAULT_LIBRARY_DIR_NAME = "SandyWallpaperStudio"
DEFAULT_SUBDIRS = [
    "Library",
    "Metadata",
    "Cache",
    "Temp",
    "Logs",
    "Exports",
    "Duplicates",
]

# Database
DATABASE_FILENAME = "wallpapers.db"

# ============================================================
# Default Categories
# ============================================================
DEFAULT_CATEGORIES = [
    "Nature",
    "Mountains",
    "Ocean",
    "Beach",
    "Forest",
    "Waterfalls",
    "Space",
    "Galaxy",
    "Astronomy",
    "Sunset",
    "Sunrise",
    "City",
    "Architecture",
    "Technology",
    "AI / Digital Art",
    "Cars",
    "Motorcycles",
    "Animals",
    "Wildlife",
    "Birds",
    "Flowers",
    "Minimal",
    "Abstract",
    "Dark",
    "Gaming",
    "Anime",
    "Travel",
    "India",
    "Indian Architecture",
    "Black & White",
    "Photography",
    "Macro",
    "Aerial",
    "Luxury",
    "Sports",
    "Automotive",
    "Science",
    "Industrial",
    "Manufacturing",
    "Office",
    "Programming",
    "Cybersecurity",
    "Cloud",
    "Networking",
]

# ============================================================
# Network Defaults
# ============================================================
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_FACTOR = 1.5
DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS = 3
DEFAULT_MAX_DOWNLOAD_SIZE_MB = 100  # Max single file size

# ============================================================
# Duplicate Detection
# ============================================================
DEFAULT_PHASH_THRESHOLD = 10  # Hamming distance; <=10 = near-duplicate

# ============================================================
# Rotation Intervals (in seconds)
# ============================================================
ROTATION_INTERVALS = {
    "5 minutes": 300,
    "15 minutes": 900,
    "30 minutes": 1800,
    "1 hour": 3600,
    "2 hours": 7200,
    "6 hours": 21600,
    "12 hours": 43200,
    "Daily": 86400,
}

# ============================================================
# Windows Wallpaper Styles
# ============================================================
# Maps to the IDesktopWallpaper / SystemParametersInfo wallpaper styles
WALLPAPER_STYLES = {
    "Center": 0,
    "Tile": 1,
    "Stretch": 2,
    "Fit": 6,
    "Fill": 10,
}

# ============================================================
# Logging
# ============================================================
LOG_FILENAME = "app.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per log file
LOG_BACKUP_COUNT = 3

# ============================================================
# Thumbnail / Cache
# ============================================================
THUMBNAIL_SIZE = (400, 225)  # 16:9 thumbnail
THUMBNAIL_QUALITY = 85
CACHE_MAX_SIZE_MB = 500

# ============================================================
# UI Constants
# ============================================================
GRID_SPACING = 8  # 8px spacing grid
CARD_WIDTH = 320
CARD_HEIGHT = 240
MIN_WINDOW_WIDTH = 1024
MIN_WINDOW_HEIGHT = 680
