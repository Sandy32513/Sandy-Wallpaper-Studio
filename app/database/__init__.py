"""Sandy Wallpaper Studio — Database package.

Public API:
    Database               - Connection manager
    WallpaperRepository    - Wallpaper CRUD
    CategoryRepository     - Category CRUD
    Wallpaper              - Wallpaper data model
    Category               - Category data model
"""

from app.database.database import Database
from app.database.models import Category, Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.database.category_repository import CategoryRepository

__all__ = [
    "Database",
    "WallpaperRepository",
    "CategoryRepository",
    "Wallpaper",
    "Category",
]
