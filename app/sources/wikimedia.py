"""
Sandy Wallpaper Studio - Wikimedia Commons Provider
======================================================
Uses the official MediaWiki API to search for and retrieve
high-resolution, legally reusable images from Wikimedia Commons.

API docs: https://www.mediawiki.org/wiki/API:Main_page
Endpoint: https://commons.wikimedia.org/w/api.php

License: Images on Wikimedia Commons are available under
various free licenses (CC-BY, CC-BY-SA, CC0, Public Domain, etc.).
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import quote

import requests

from app.constants import DEFAULT_TIMEOUT_SECONDS
from app.sources.base import WallpaperSearchResult, WallpaperSource

logger = logging.getLogger(__name__)

API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "SandyWallpaperStudio/1.0 (https://github.com/Sandy32513/Sandy-Wallpaper-Studio)"

# Map common categories to Wikimedia Commons search terms
_CATEGORY_SEARCH_HINTS: dict[str, str] = {
    "Nature": "nature landscape",
    "Mountains": "mountain landscape",
    "Ocean": "ocean sea",
    "Beach": "beach coast",
    "Forest": "forest trees",
    "Waterfalls": "waterfall",
    "Space": "outer space nebula",
    "Galaxy": "galaxy astronomy",
    "Astronomy": "astronomy stars",
    "Sunset": "sunset",
    "Sunrise": "sunrise",
    "City": "cityscape skyline",
    "Architecture": "architecture building",
    "Technology": "technology",
    "Cars": "car automobile",
    "Animals": "animal wildlife",
    "Wildlife": "wildlife",
    "Birds": "bird",
    "Flowers": "flower",
    "Minimal": "minimalist",
    "Abstract": "abstract art",
    "Dark": "dark moody",
    "Aerial": "aerial view",
}


class WikimediaSource(WallpaperSource):
    """Wikimedia Commons wallpaper source.

    Uses the official MediaWiki API. No scraping.
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})

    # ----------------------------------------------------------
    # WallpaperSource interface
    # ----------------------------------------------------------
    @property
    def name(self) -> str:
        return "wikimedia"

    @property
    def display_name(self) -> str:
        return "Wikimedia Commons"

    @property
    def description(self) -> str:
        return "Free, high-resolution images from Wikimedia Commons (CC / Public Domain)."

    @property
    def base_url(self) -> str:
        return "https://commons.wikimedia.org"

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        min_width: int = 0,
        min_height: int = 0,
        limit: int = 20,
        offset: int = 0,
    ) -> list[WallpaperSearchResult]:
        """Search Wikimedia Commons for images.

        Uses the MediaWiki search API, then fetches image info
        for each result to get dimensions and metadata.
        """
        # Build search query
        search_terms = query.strip()
        if category and category in _CATEGORY_SEARCH_HINTS:
            search_terms = f"{_CATEGORY_SEARCH_HINTS[category]} {search_terms}".strip()
        elif category:
            search_terms = f"{category} {search_terms}".strip()

        if not search_terms:
            search_terms = "landscape wallpaper"

        # Add wallpaper/high-resolution hints
        search_terms = f"{search_terms} wallpaper"

        logger.info("Wikimedia search: %r (limit=%d, offset=%d)", search_terms, limit, offset)

        try:
            # Step 1: Search for file pages
            titles = self._search_files(search_terms, limit=limit, offset=offset)
            if not titles:
                logger.info("No results found for: %r", search_terms)
                return []

            # Step 2: Get image info (dimensions, URL, metadata) for all results
            results = self._get_image_info_batch(titles, min_width, min_height)
            logger.info("Wikimedia returned %d results after filtering.", len(results))
            return results

        except requests.RequestException as exc:
            logger.error("Wikimedia API request failed: %s", exc)
            return []
        except Exception as exc:
            logger.error("Unexpected error in Wikimedia search: %s", exc)
            return []

    def get_image_info(self, source_id: str) -> Optional[WallpaperSearchResult]:
        """Get detailed info for a single Wikimedia file.

        Args:
            source_id: The file title (e.g. "File:Example.jpg").
        """
        results = self._get_image_info_batch([source_id], min_width=0, min_height=0)
        return results[0] if results else None

    def get_download_url(self, source_id: str) -> Optional[str]:
        """Get the direct download URL for a Wikimedia file."""
        info = self.get_image_info(source_id)
        return info.download_url if info else None

    def is_available(self) -> bool:
        """Check if Wikimedia Commons API is reachable."""
        try:
            resp = self._session.get(
                API_ENDPOINT,
                params={"action": "query", "meta": "siteinfo", "format": "json"},
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # ----------------------------------------------------------
    # Internal API calls
    # ----------------------------------------------------------
    def _search_files(self, query: str, limit: int, offset: int) -> list[str]:
        """Search for file pages on Wikimedia Commons.

        Returns a list of file titles (e.g. ["File:Mountain.jpg", ...]).
        """
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": "6",   # File namespace
            "gsrsearch": query,
            "gsrlimit": min(limit, 50),  # API max is 50
            "gsroffset": offset,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": "400",   # Get thumbnail URL at 400px
        }

        resp = self._session.get(API_ENDPOINT, params=params, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return []

        # Return titles sorted by page index (relevance)
        sorted_pages = sorted(pages.values(), key=lambda p: p.get("index", 0))
        return [p["title"] for p in sorted_pages if "title" in p]

    def _get_image_info_batch(
        self,
        titles: list[str],
        min_width: int,
        min_height: int,
    ) -> list[WallpaperSearchResult]:
        """Fetch image info for a batch of file titles.

        Filters by minimum resolution and supported formats.
        """
        if not titles:
            return []

        # MediaWiki API accepts up to 50 titles per request
        params = {
            "action": "query",
            "format": "json",
            "titles": "|".join(titles[:50]),
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata|mediatype",
            "iiurlwidth": "400",
        }

        resp = self._session.get(API_ENDPOINT, params=params, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()

        pages = data.get("query", {}).get("pages", {})
        results: list[WallpaperSearchResult] = []

        for page in pages.values():
            page_id = page.get("pageid", 0)
            title = page.get("title", "")
            imageinfo = page.get("imageinfo", [])

            if not imageinfo:
                continue

            info = imageinfo[0]
            width = info.get("width", 0)
            height = info.get("height", 0)
            mime = info.get("mime", "")

            # Filter: must be a raster image
            media_type = info.get("mediatype", "")
            if media_type not in ("BITMAP", ""):
                continue

            # Filter: supported formats only
            if not _is_supported_mime(mime):
                continue

            # Filter: minimum resolution
            if min_width and width < min_width:
                continue
            if min_height and height < min_height:
                continue

            # Extract metadata
            extmeta = info.get("extmetadata", {})
            author = _extract_text(extmeta.get("Artist", {}))
            license_name = _extract_text(extmeta.get("LicenseShortName", {}))
            license_url = _extract_text(extmeta.get("LicenseUrl", {}))
            description = _extract_text(extmeta.get("ImageDescription", {}))
            categories_raw = _extract_text(extmeta.get("Categories", {}))

            # Build download URL (full resolution)
            download_url = info.get("url", "")
            # Thumbnail URL
            thumb_url = info.get("thumburl", "")

            # File format from mime
            file_format = _mime_to_extension(mime)

            # Clean title for display
            display_title = title.replace("File:", "").rsplit(".", 1)[0]
            display_title = display_title.replace("_", " ")

            # Parse categories
            categories = [c.strip() for c in categories_raw.split("|") if c.strip()] if categories_raw else []

            result = WallpaperSearchResult(
                source_id=title,
                title=display_title,
                description=_strip_html(description),
                thumbnail_url=thumb_url,
                download_url=download_url,
                width=width,
                height=height,
                file_size=info.get("size", 0),
                file_format=file_format,
                source_name="wikimedia",
                source_url=f"https://commons.wikimedia.org/wiki/{quote(title, safe='/:@')}",
                author=_strip_html(author),
                license=license_name,
                license_url=license_url,
                categories=categories,
                tags=[],
            )
            results.append(result)

        return results


# ============================================================
# Helpers
# ============================================================
def _is_supported_mime(mime: str) -> bool:
    """Check if the MIME type is a supported image format."""
    supported = {"image/jpeg", "image/png", "image/webp"}
    return mime in supported


def _mime_to_extension(mime: str) -> str:
    """Convert MIME type to file extension."""
    mapping = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    return mapping.get(mime, "")


def _extract_text(field: dict) -> str:
    """Extract text value from a MediaWiki extmetadata field."""
    if not field:
        return ""
    return field.get("value", "")


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean
