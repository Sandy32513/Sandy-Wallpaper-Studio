"""Sandy Wallpaper Studio — Database package.

Public API:
    Database               - Connection manager
    WallpaperRepository    - Wallpaper CRUD
    CategoryRepository     - Category CRUD
    HistoryRepository      - Wallpaper history CRUD
    Wallpaper              - Wallpaper data model
    Category               - Category data model
    WallpaperHistory       - Wallpaper history data model
"""

from app.database.database import Database
from app.database.models import Category, Wallpaper, WallpaperHistory
from app.database.wallpaper_repository import WallpaperRepository
from app.database.category_repository import CategoryRepository
from app.database.history_repository import HistoryRepository

__all__ = [
    "Database",
    "WallpaperRepository",
    "CategoryRepository",
    "HistoryRepository",
    "Wallpaper",
    "Category",
    "WallpaperHistory",
]
