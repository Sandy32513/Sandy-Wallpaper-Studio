"""
Sandy Wallpaper Studio - Wallpaper Source Base Interface
==========================================================
Abstract interface that all wallpaper providers must implement.
This enables a pluggable provider architecture (Section 4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WallpaperSearchResult:
    """Represents a single search result from a wallpaper source.

    This is the standardized format returned by all providers
    before a wallpaper is downloaded and added to the library.
    """

    source_id: str = ""          # Provider-specific unique ID
    title: str = ""
    description: str = ""
    thumbnail_url: str = ""
    download_url: str = ""       # Full-resolution image URL
    width: int = 0
    height: int = 0
    file_size: int = 0           # bytes (if known; 0 = unknown)
    file_format: str = ""        # e.g. "jpg", "png", "webp"
    source_name: str = ""        # e.g. "wikimedia"
    source_url: str = ""         # URL of the source page
    author: str = ""
    license: str = ""
    license_url: str = ""
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def resolution_label(self) -> str:
        if self.width and self.height:
            return f"{self.width}×{self.height}"
        return "Unknown"

    @property
    def file_size_mb(self) -> float:
        return round(self.file_size / (1024 * 1024), 2) if self.file_size else 0.0


class WallpaperSource(ABC):
    """Abstract base class for wallpaper source providers.

    Each provider (Wikimedia, Unsplash, etc.) implements this interface.
    The GUI and service layer interact with providers only through
    this API — never directly.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique short name of this source (e.g. 'wikimedia')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name (e.g. 'Wikimedia Commons')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of this source."""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL of the service."""
        ...

    @abstractmethod
    def search(
        self,
        query: str,
        category: Optional[str] = None,
        min_width: int = 0,
        min_height: int = 0,
        limit: int = 20,
        offset: int = 0,
    ) -> list[WallpaperSearchResult]:
        """Search for wallpapers matching the query and filters.

        Args:
            query: Search keywords.
            category: Optional category filter.
            min_width: Minimum image width.
            min_height: Minimum image height.
            limit: Max results to return.
            offset: Pagination offset.

        Returns:
            List of WallpaperSearchResult objects.
        """
        ...

    @abstractmethod
    def get_image_info(self, source_id: str) -> Optional[WallpaperSearchResult]:
        """Fetch detailed metadata for a specific image.

        Args:
            source_id: Provider-specific unique identifier.

        Returns:
            WallpaperSearchResult with full metadata, or None.
        """
        ...

    @abstractmethod
    def get_download_url(self, source_id: str) -> Optional[str]:
        """Get the direct download URL for the full-resolution image.

        Args:
            source_id: Provider-specific unique identifier.

        Returns:
            Direct URL string, or None.
        """
        ...

    def is_available(self) -> bool:
        """Check if this source is currently reachable.

        Default implementation returns True. Override for
        sources that need connectivity checks.
        """
        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
