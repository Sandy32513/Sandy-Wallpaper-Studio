"""
Sandy Wallpaper Studio - Database Models
==========================================
Data classes representing the database schema.
These are plain Python dataclasses — not ORM models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Wallpaper:
    """Represents a single wallpaper in the library.

    All 22 fields from the plan (Section 10).
    """

    id: Optional[int] = None
    filename: str = ""
    path: str = ""
    title: str = ""
    description: str = ""
    category: str = ""
    tags: str = ""  # Comma-separated tag list
    width: int = 0
    height: int = 0
    aspect_ratio: str = ""  # e.g. "16:9"
    resolution_class: str = ""  # e.g. "4K", "5K", "8K"
    file_size: int = 0  # bytes
    sha256: str = ""
    phash: str = ""
    source: str = ""  # Provider name, e.g. "wikimedia"
    source_url: str = ""
    author: str = ""
    license: str = ""
    license_url: str = ""
    download_date: Optional[str] = None  # ISO 8601 string
    favorite: bool = False
    last_used: Optional[str] = None  # ISO 8601 string
    usage_count: int = 0

    @property
    def resolution_label(self) -> str:
        """Human-readable resolution string, e.g. '3840 × 2160'."""
        return f"{self.width} × {self.height}"

    @property
    def file_size_mb(self) -> float:
        """File size in megabytes."""
        return round(self.file_size / (1024 * 1024), 2) if self.file_size else 0.0

    @property
    def tag_list(self) -> list[str]:
        """Tags as a list."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def to_dict(self) -> dict:
        """Convert to a dictionary for database insertion."""
        return {
            "filename": self.filename,
            "path": self.path,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "resolution_class": self.resolution_class,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "phash": self.phash,
            "source": self.source,
            "source_url": self.source_url,
            "author": self.author,
            "license": self.license,
            "license_url": self.license_url,
            "download_date": self.download_date,
            "favorite": 1 if self.favorite else 0,
            "last_used": self.last_used,
            "usage_count": self.usage_count,
        }


@dataclass
class Category:
    """Represents a wallpaper category.

    Categories are database-driven and users can create custom ones.
    """

    id: Optional[int] = None
    name: str = ""
    is_default: bool = True  # True = shipped with app; False = user-created
    icon: str = ""  # Optional icon identifier
    sort_order: int = 0

    def to_dict(self) -> dict:
        """Convert to a dictionary for database insertion."""
        return {
            "name": self.name,
            "is_default": 1 if self.is_default else 0,
            "icon": self.icon,
            "sort_order": self.sort_order,
        }


@dataclass
class DownloadRecord:
    """Tracks a download attempt (completed, failed, or in-progress)."""

    id: Optional[int] = None
    wallpaper_id: Optional[int] = None
    source: str = ""
    source_url: str = ""
    status: str = "pending"  # pending | downloading | completed | failed
    error_message: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    file_size: int = 0

    def to_dict(self) -> dict:
        return {
            "wallpaper_id": self.wallpaper_id,
            "source": self.source,
            "source_url": self.source_url,
            "status": self.status,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "file_size": self.file_size,
        }


@dataclass
class WallpaperHistory:
    """Tracks when a wallpaper was set as the desktop background."""

    id: Optional[int] = None
    wallpaper_id: int = 0
    set_at: Optional[str] = None  # ISO 8601 string
    monitor: str = ""  # Monitor identifier (e.g. "primary", "\\.\DISPLAY1")
