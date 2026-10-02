"""Sandy Wallpaper Studio — Wallpaper Sources package.

Public API:
    WallpaperSource        - Abstract base class
    WallpaperSearchResult  - Standardized search result
    WikimediaSource        - Wikimedia Commons provider
"""

from app.sources.base import WallpaperSearchResult, WallpaperSource
from app.sources.wikimedia import WikimediaSource

__all__ = [
    "WallpaperSource",
    "WallpaperSearchResult",
    "WikimediaSource",
]
