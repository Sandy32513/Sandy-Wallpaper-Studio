"""Sandy Wallpaper Studio — Database package.

Public API:
    Database               - Connection manager
    WallpaperRepository    - Wallpaper CRUD
    CategoryRepository     - Category CRUD
    HistoryRepository      - Wallpaper history CRUD
    Wallpaper              - Wallpaper data model
    Category               - Category data model
    WallpaperHistory       - Wallpaper history data model
    WallpaperView          - Wallpaper view tracking data model
    ViewRepository         - Wallpaper view tracking CRUD
"""

from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.database.history_repository import HistoryRepository
from app.database.models import Category, Wallpaper, WallpaperHistory, WallpaperView
from app.database.view_repository import ViewRepository
from app.database.wallpaper_repository import WallpaperRepository

__all__ = [
    "Database",
    "WallpaperRepository",
    "CategoryRepository",
    "HistoryRepository",
    "ViewRepository",
    "Wallpaper",
    "Category",
    "WallpaperHistory",
    "WallpaperView",
]
