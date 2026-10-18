"""
Sandy Wallpaper Studio - Library Service
==========================================
Phase 4: Smart Library — Library Management & Statistics

Provides a high-level facade for library operations:
- Library statistics (total, by category, by resolution, filesystem integrity)
- Search and filtering with pagination
- Category management integration
- Integrity checks (missing files, stale records)
- Library health reporting

This service coordinates between the WallpaperRepository,
CategoryRepository, and filesystem operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.config import Config
from app.constants import THUMBNAIL_QUALITY, THUMBNAIL_SIZE
from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.database.models import Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.utils.image_utils import thumbnail_cache_path

logger = logging.getLogger(__name__)


# ============================================================
# Library Statistics
# ============================================================
@dataclass
class LibraryStats:
    """Comprehensive library statistics."""
    total_wallpapers: int = 0
    total_favorites: int = 0
    total_size_bytes: int = 0
    categories_used: int = 0
    total_categories: int = 0
    sources_used: int = 0
    resolution_distribution: dict[str, int] = field(default_factory=dict)
    category_distribution: dict[str, int] = field(default_factory=dict)
    format_distribution: dict[str, int] = field(default_factory=dict)

    @property
    def total_size_mb(self) -> float:
        return round(self.total_size_bytes / (1024 * 1024), 2) if self.total_size_bytes else 0.0

    @property
    def total_size_gb(self) -> float:
        return round(self.total_size_bytes / (1024 * 1024 * 1024), 2) if self.total_size_bytes else 0.0

    def to_dict(self) -> dict:
        return {
            "total_wallpapers": self.total_wallpapers,
            "total_favorites": self.total_favorites,
            "total_size_bytes": self.total_size_bytes,
            "total_size_mb": self.total_size_mb,
            "total_size_gb": self.total_size_gb,
            "categories_used": self.categories_used,
            "total_categories": self.total_categories,
            "sources_used": self.sources_used,
            "resolution_distribution": self.resolution_distribution,
            "category_distribution": self.category_distribution,
            "format_distribution": self.format_distribution,
        }


@dataclass
class IntegrityReport:
    """Results of a library integrity check."""
    total_records: int = 0
    files_present: int = 0
    files_missing: int = 0
    stale_thumbnails: int = 0
    missing_file_ids: list[int] = field(default_factory=list)
    missing_file_paths: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.files_missing == 0 and self.stale_thumbnails == 0


class LibraryService:
    """High-level library management service.

    Provides search, statistics, category management,
    and integrity checking for the wallpaper library.
    """

    def __init__(
        self,
        db: Database,
        cache_dir: Optional[Path] = None,
        config: Config | None = None,
    ) -> None:
        self._db = db
        self._wallpaper_repo = WallpaperRepository(db)
        self._category_repo = CategoryRepository(db)
        self._cache_dir = cache_dir
        self._thumbnail_dir = cache_dir / "thumbnails" if cache_dir else None
        self._thumbnail_enabled = bool(config.get("thumbnail_enabled", True)) if config else True
        self._thumbnail_size = (
            (config.get("thumbnail_width", THUMBNAIL_SIZE[0]), config.get("thumbnail_height", THUMBNAIL_SIZE[1]))
            if config else THUMBNAIL_SIZE
        )
        self._thumbnail_quality = config.get("thumbnail_quality", THUMBNAIL_QUALITY) if config else THUMBNAIL_QUALITY

    # ----------------------------------------------------------
    # Search & Filtering
    # ----------------------------------------------------------
    def search(
        self,
        query: str = "",
        category: Optional[str] = None,
        resolution_class: Optional[str] = None,
        min_width: Optional[int] = None,
        min_height: Optional[int] = None,
        aspect_ratio: Optional[str] = None,
        file_format: Optional[str] = None,
        source: Optional[str] = None,
        license_filter: Optional[str] = None,
        favorites_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Wallpaper]:
        """Search indexed wallpapers with comprehensive filters.

        Args:
            query: Text search across title, description, tags, category, author.
            category: Filter by exact category name.
            resolution_class: Filter by resolution class (e.g. "4K", "8K").
            min_width: Minimum width in pixels.
            min_height: Minimum height in pixels.
            aspect_ratio: Filter by aspect ratio string (e.g. "16:9").
            file_format: Filter by file format (e.g. "jpg", "png").
            source: Filter by source provider name.
            license_filter: Filter by license string.
            favorites_only: If True, only return favorites.
            limit: Maximum results to return.
            offset: Pagination offset.

        Returns:
            List of matching Wallpaper objects.
        """
        # Validate pagination
        if limit < 0:
            limit = 0
        if limit > 1000:
            limit = 1000
        if offset < 0:
            offset = 0

        # Use the repository's search for the base filters
        results = self._wallpaper_repo.search(
            query=query,
            category=category,
            resolution_class=resolution_class,
            min_width=min_width,
            min_height=min_height,
            source=source,
            favorites_only=favorites_only,
            limit=limit,
            offset=offset,
        )

        # Apply additional filters not supported by the base search
        if aspect_ratio:
            results = [w for w in results if w.aspect_ratio == aspect_ratio]

        if file_format:
            fmt = file_format.lower().lstrip(".")
            results = [
                w for w in results
                if w.filename.lower().endswith(f".{fmt}")
            ]

        if license_filter:
            results = [
                w for w in results
                if license_filter.lower() in w.license.lower()
            ]

        return results

    def count(self, category: Optional[str] = None) -> int:
        """Count wallpapers, optionally filtered by category."""
        return self._wallpaper_repo.count(category=category)

    def get_page(
        self,
        page: int = 1,
        page_size: int = 50,
        order_by: str = "download_date DESC",
    ) -> tuple[list[Wallpaper], int]:
        """Get a page of wallpapers with total count.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
            order_by: Sort order.

        Returns:
            Tuple of (wallpapers, total_count).
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 1
        if page_size > 500:
            page_size = 500

        offset = (page - 1) * page_size
        wallpapers = self._wallpaper_repo.get_all(
            limit=page_size, offset=offset, order_by=order_by
        )
        total = self._wallpaper_repo.count()
        return wallpapers, total

    # ----------------------------------------------------------
    # Category Management
    # ----------------------------------------------------------
    def assign_category(
        self,
        wallpaper_id: int,
        category_name: str,
    ) -> bool:
        """Assign a category to a wallpaper with validation.

        Args:
            wallpaper_id: ID of the wallpaper to update.
            category_name: Name of the category.

        Returns:
            True if the category was assigned successfully.
        """
        # Verify wallpaper exists
        wallpaper = self._wallpaper_repo.get_by_id(wallpaper_id)
        if wallpaper is None:
            logger.warning("Cannot assign category: wallpaper id=%d not found.", wallpaper_id)
            return False

        # Verify category exists (if non-empty)
        if category_name:
            cat = self._category_repo.get_by_name(category_name)
            if cat is None:
                logger.warning(
                    "Category '%s' not found in database. "
                    "Assigning anyway (category string is freeform).",
                    category_name,
                )

        return self._wallpaper_repo.update_category(wallpaper_id, category_name)

    def get_categories(self) -> list[str]:
        """Get all category names from the database."""
        cats = self._category_repo.get_all()
        return [c.name for c in cats]

    # ----------------------------------------------------------
    # Statistics
    # ----------------------------------------------------------
    def get_statistics(self) -> LibraryStats:
        """Get comprehensive library statistics."""
        base_stats = self._wallpaper_repo.get_statistics()
        total_categories = self._category_repo.count()

        # Get category distribution
        category_dist: dict[str, int] = {}
        for cat in self._category_repo.get_all():
            count = self._wallpaper_repo.count(category=cat.name)
            if count > 0:
                category_dist[cat.name] = count

        # Get format distribution
        format_dist: dict[str, int] = {}
        try:
            cursor = self._db.execute(
                "SELECT "
                "  LOWER(SUBSTR(filename, INSTR(filename, '.') + 1)) as fmt, "
                "  COUNT(*) as cnt "
                "FROM wallpapers "
                "WHERE filename LIKE '%.%' "
                "GROUP BY fmt "
                "ORDER BY cnt DESC"
            )
            for row in cursor.fetchall():
                if row["fmt"]:
                    format_dist[row["fmt"]] = row["cnt"]
        except Exception as exc:
            logger.warning("Could not compute format distribution: %s", exc)

        return LibraryStats(
            total_wallpapers=base_stats["total"],
            total_favorites=base_stats["favorites"],
            total_size_bytes=base_stats["total_size_bytes"],
            categories_used=base_stats["categories_used"],
            total_categories=total_categories,
            sources_used=base_stats["sources_used"],
            resolution_distribution=base_stats.get("by_resolution", {}),
            category_distribution=category_dist,
            format_distribution=format_dist,
        )

    # ----------------------------------------------------------
    # Integrity Checks
    # ----------------------------------------------------------
    def check_integrity(self) -> IntegrityReport:
        """Check library integrity without destructive operations.

        Verifies that:
        - Each database record points to an existing file on disk
        - Thumbnails exist for indexed wallpapers

        Does NOT delete or modify any files or records.

        Returns:
            IntegrityReport with findings.
        """
        report = IntegrityReport()

        # Check all wallpaper records
        offset = 0
        batch_size = 100

        while True:
            wallpapers = self._wallpaper_repo.get_all(
                limit=batch_size, offset=offset, order_by="id ASC"
            )
            if not wallpapers:
                break

            for wp in wallpapers:
                report.total_records += 1
                file_path = Path(wp.path) if wp.path else None

                if file_path and file_path.exists():
                    report.files_present += 1
                else:
                    report.files_missing += 1
                    if wp.id is not None:
                        report.missing_file_ids.append(wp.id)
                    report.missing_file_paths.append(wp.path)

                # Check thumbnail
                if self._thumbnail_dir and self._thumbnail_enabled and wp.sha256:
                    thumb_path = thumbnail_cache_path(
                        self._thumbnail_dir, wp.sha256, self._thumbnail_size, self._thumbnail_quality
                    )
                    if not thumb_path.exists():
                        report.stale_thumbnails += 1

            offset += batch_size

        logger.info(
            "Integrity check: %d records, %d present, %d missing, %d stale thumbnails.",
            report.total_records, report.files_present,
            report.files_missing, report.stale_thumbnails,
        )
        return report
