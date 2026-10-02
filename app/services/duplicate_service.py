"""
Sandy Wallpaper Studio - Duplicate Detection Service
=======================================================
Two-level duplicate detection (Section 8):
  Level 1: SHA-256 exact duplicate detection
  Level 2: Perceptual hash near-duplicate detection

Never automatically deletes duplicates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.constants import DEFAULT_PHASH_THRESHOLD
from app.database.database import Database
from app.database.wallpaper_repository import WallpaperRepository
from app.database.models import Wallpaper
from app.utils.hashing import (
    compute_sha256,
    compute_phash,
    hamming_distance,
    similarity_percentage,
)

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMatch:
    """Represents a detected duplicate pair."""

    original: Wallpaper
    duplicate: Wallpaper
    match_type: str  # "exact" or "near"
    distance: int  # Hamming distance (0 for exact)
    similarity: float  # Percentage (100.0 for exact)

    @property
    def is_exact(self) -> bool:
        return self.match_type == "exact"

    def __repr__(self) -> str:
        return (
            f"DuplicateMatch({self.match_type}, "
            f"similarity={self.similarity}%, "
            f"original_id={self.original.id}, "
            f"duplicate_id={self.duplicate.id})"
        )


class DuplicateService:
    """Service for detecting duplicate wallpapers.

    Provides both exact (SHA-256) and near-duplicate (pHash) detection.
    """

    def __init__(
        self,
        db: Database,
        threshold: int = DEFAULT_PHASH_THRESHOLD,
    ) -> None:
        self._repo = WallpaperRepository(db)
        self._threshold = threshold

    @property
    def threshold(self) -> int:
        return self._threshold

    @threshold.setter
    def threshold(self, value: int) -> None:
        """Update the similarity threshold (configurable per Section 8)."""
        if value < 0:
            value = 0
        self._threshold = value
        logger.info("Duplicate threshold updated to %d.", value)

    # ----------------------------------------------------------
    # Level 1: Exact Duplicate Detection (SHA-256)
    # ----------------------------------------------------------
    def check_exact_duplicate(self, sha256: str) -> Optional[Wallpaper]:
        """Check if a wallpaper with the given SHA-256 already exists.

        Args:
            sha256: The SHA-256 hash to check.

        Returns:
            The existing Wallpaper if found, or None.
        """
        if not sha256:
            return None
        return self._repo.get_by_sha256(sha256)

    def check_exact_duplicate_file(self, file_path: Path) -> Optional[Wallpaper]:
        """Check if a file is an exact duplicate of something in the library.

        Args:
            file_path: Path to the image file.

        Returns:
            The existing Wallpaper if found, or None.
        """
        sha256 = compute_sha256(file_path)
        return self.check_exact_duplicate(sha256)

    # ----------------------------------------------------------
    # Level 2: Near-Duplicate Detection (pHash)
    # ----------------------------------------------------------
    def find_near_duplicates(
        self,
        phash: str,
        exclude_id: Optional[int] = None,
    ) -> list[DuplicateMatch]:
        """Find wallpapers that are visually similar to the given pHash.

        Args:
            phash: The perceptual hash to compare against.
            exclude_id: Wallpaper ID to exclude from results (self).

        Returns:
            List of DuplicateMatch objects, sorted by similarity (highest first).
        """
        if not phash:
            return []

        all_hashes = self._repo.get_all_phashes()
        matches: list[DuplicateMatch] = []

        for wp_id, existing_phash in all_hashes:
            if wp_id == exclude_id:
                continue
            if not existing_phash:
                continue

            dist = hamming_distance(phash, existing_phash)
            if dist < 0:
                continue

            if dist <= self._threshold:
                sim = similarity_percentage(phash, existing_phash)
                existing_wp = self._repo.get_by_id(wp_id)
                if existing_wp is None:
                    continue

                # Create a placeholder for the "duplicate" side
                # (caller will fill in the actual wallpaper)
                match_type = "exact" if dist == 0 else "near"
                matches.append(DuplicateMatch(
                    original=existing_wp,
                    duplicate=Wallpaper(),  # Placeholder
                    match_type=match_type,
                    distance=dist,
                    similarity=sim,
                ))

        # Sort by similarity (highest first)
        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches

    def find_near_duplicates_for_file(
        self,
        file_path: Path,
        exclude_id: Optional[int] = None,
    ) -> list[DuplicateMatch]:
        """Find near-duplicates for an image file.

        Args:
            file_path: Path to the image file.
            exclude_id: Wallpaper ID to exclude.

        Returns:
            List of DuplicateMatch objects.
        """
        phash = compute_phash(file_path)
        return self.find_near_duplicates(phash, exclude_id=exclude_id)

    # ----------------------------------------------------------
    # Full Library Scan
    # ----------------------------------------------------------
    def scan_all_duplicates(self) -> list[list[DuplicateMatch]]:
        """Scan the entire library for duplicate groups.

        Returns groups of duplicates. Each group is a list of
        DuplicateMatch objects sharing a common "original".

        This is an O(n²) operation — use with caution on large libraries.
        """
        all_hashes = self._repo.get_all_phashes()
        processed: set[int] = set()
        groups: list[list[DuplicateMatch]] = []

        for i, (id_a, hash_a) in enumerate(all_hashes):
            if id_a in processed or not hash_a:
                continue

            group_matches: list[DuplicateMatch] = []

            for j in range(i + 1, len(all_hashes)):
                id_b, hash_b = all_hashes[j]
                if id_b in processed or not hash_b:
                    continue

                dist = hamming_distance(hash_a, hash_b)
                if dist < 0:
                    continue
                if dist > self._threshold:
                    continue

                sim = similarity_percentage(hash_a, hash_b)
                wp_a = self._repo.get_by_id(id_a)
                wp_b = self._repo.get_by_id(id_b)

                if wp_a and wp_b:
                    match_type = "exact" if dist == 0 else "near"
                    group_matches.append(DuplicateMatch(
                        original=wp_a,
                        duplicate=wp_b,
                        match_type=match_type,
                        distance=dist,
                        similarity=sim,
                    ))
                    processed.add(id_b)

            if group_matches:
                processed.add(id_a)
                groups.append(group_matches)

        logger.info(
            "Duplicate scan: found %d group(s) across %d wallpapers.",
            len(groups), len(all_hashes),
        )
        return groups
