"""
Sandy Wallpaper Studio - Hashing Utilities
=============================================
SHA-256 (Level 1) and perceptual hashing (Level 2)
for duplicate detection (Section 8).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import imagehash
from PIL import Image

logger = logging.getLogger(__name__)


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file (Level 1: exact duplicate detection).

    Args:
        file_path: Path to the file.

    Returns:
        Lowercase hex SHA-256 digest string (64 chars).
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_phash(file_path: Path) -> str:
    """Compute perceptual hash of an image (Level 2: near-duplicate detection).

    Uses pHash (DCT-based perceptual hash) from the imagehash library.

    Args:
        file_path: Path to the image file.

    Returns:
        Hex string representation of the perceptual hash.
    """
    try:
        with Image.open(file_path) as img:
            ph = imagehash.phash(img)
            return str(ph)
    except Exception as exc:
        logger.error("Failed to compute pHash for %s: %s", file_path, exc)
        return ""


def compute_dhash(file_path: Path) -> str:
    """Compute difference hash of an image (optional, complementary).

    Args:
        file_path: Path to the image file.

    Returns:
        Hex string representation of the difference hash.
    """
    try:
        with Image.open(file_path) as img:
            dh = imagehash.dhash(img)
            return str(dh)
    except Exception as exc:
        logger.error("Failed to compute dHash for %s: %s", file_path, exc)
        return ""


def compute_ahash(file_path: Path) -> str:
    """Compute average hash of an image (optional, complementary).

    Args:
        file_path: Path to the image file.

    Returns:
        Hex string representation of the average hash.
    """
    try:
        with Image.open(file_path) as img:
            ah = imagehash.average_hash(img)
            return str(ah)
    except Exception as exc:
        logger.error("Failed to compute aHash for %s: %s", file_path, exc)
        return ""


def hamming_distance(hash1: str, hash2: str) -> int:
    """Compute the Hamming distance between two hex hash strings.

    A distance of 0 means the hashes are identical.
    Lower distance = more visually similar.

    Args:
        hash1: First hex hash string.
        hash2: Second hex hash string.

    Returns:
        Hamming distance (number of differing bits).
    """
    if not hash1 or not hash2:
        return -1  # Cannot compare

    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2  # imagehash overloads __sub__ as Hamming distance
    except Exception as exc:
        logger.error("Failed to compute Hamming distance: %s", exc)
        return -1


def similarity_percentage(hash1: str, hash2: str, hash_size: int = 8) -> float:
    """Compute similarity percentage between two perceptual hashes.

    Args:
        hash1: First hex hash string.
        hash2: Second hex hash string.
        hash_size: Hash size (default 8 for pHash = 64 bits).

    Returns:
        Similarity as a percentage (0.0 to 100.0).
        Returns -1.0 if comparison fails.
    """
    dist = hamming_distance(hash1, hash2)
    if dist < 0:
        return -1.0

    max_distance = hash_size * hash_size  # 64 bits for default pHash
    similarity = (1.0 - dist / max_distance) * 100.0
    return round(similarity, 2)
