"""
Sandy Wallpaper Studio - Source Service
=========================================
Manages wallpaper source providers.
Acts as a registry and coordinator between the UI
and individual WallpaperSource implementations.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.sources.base import WallpaperSearchResult, WallpaperSource
from app.sources.wikimedia import WikimediaSource

logger = logging.getLogger(__name__)


class SourceService:
    """Registry and coordinator for wallpaper source providers."""

    def __init__(self) -> None:
        self._sources: dict[str, WallpaperSource] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register the built-in source providers."""
        self.register(WikimediaSource())

    def register(self, source: WallpaperSource) -> None:
        """Register a new wallpaper source provider."""
        self._sources[source.name] = source
        logger.info("Registered source: %s (%s)", source.name, source.display_name)

    def get(self, name: str) -> Optional[WallpaperSource]:
        """Get a source by name."""
        return self._sources.get(name)

    def get_all(self) -> list[WallpaperSource]:
        """Get all registered sources."""
        return list(self._sources.values())

    def get_names(self) -> list[str]:
        """Get the names of all registered sources."""
        return list(self._sources.keys())

    def search(
        self,
        query: str,
        source_name: Optional[str] = None,
        category: Optional[str] = None,
        min_width: int = 0,
        min_height: int = 0,
        limit: int = 20,
        offset: int = 0,
    ) -> list[WallpaperSearchResult]:
        """Search across one or all sources.

        Args:
            query: Search keywords.
            source_name: If specified, search only this source.
            category: Optional category filter.
            min_width: Minimum width filter.
            min_height: Minimum height filter.
            limit: Max results per source.
            offset: Pagination offset.

        Returns:
            Combined list of WallpaperSearchResult objects.
        """
        results: list[WallpaperSearchResult] = []

        if source_name:
            source = self._sources.get(source_name)
            if source is None:
                logger.warning("Unknown source: %s", source_name)
                return []
            sources_to_search = [source]
        else:
            sources_to_search = list(self._sources.values())

        for source in sources_to_search:
            try:
                source_results = source.search(
                    query=query,
                    category=category,
                    min_width=min_width,
                    min_height=min_height,
                    limit=limit,
                    offset=offset,
                )
                results.extend(source_results)
                logger.info(
                    "Source %s returned %d results for %r",
                    source.name, len(source_results), query,
                )
            except Exception as exc:
                # Never crash because a provider is unavailable (Rule 21)
                logger.error("Source %s failed: %s", source.name, exc)

        return results

    def check_availability(self) -> dict[str, bool]:
        """Check which sources are currently available."""
        status: dict[str, bool] = {}
        for name, source in self._sources.items():
            try:
                status[name] = source.is_available()
            except Exception:
                status[name] = False
        return status
