"""
Sandy Wallpaper Studio - Image Utilities
===========================================
Image validation and processing utilities (Section 9).
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path

from PIL import Image

from app.constants import SUPPORTED_FORMATS

logger = logging.getLogger(__name__)


def thumbnail_cache_path(
    thumbnail_dir: Path, sha256: str, size: tuple[int, int], quality: int
) -> Path:
    """Return a versioned cache path so changed settings never reuse stale previews."""
    safe_hash = re.sub(r"[^0-9a-fA-F]", "", sha256)[:16] or "unknown"
    return thumbnail_dir / f"{safe_hash}-{size[0]}x{size[1]}-q{quality}.jpg"


def enforce_thumbnail_cache_limit(
    thumbnail_dir: Path, max_size_mb: int, preserve: Path | None = None
) -> int:
    """Evict oldest regular cache files until the application cache is within budget."""
    if type(max_size_mb) is not int or max_size_mb < 1:
        raise ValueError("Thumbnail cache limit must be a positive integer.")
    if not thumbnail_dir.is_dir():
        return 0
    files = [
        path for path in thumbnail_dir.glob("*.jpg")
        if path.is_file() and not path.is_symlink()
    ]
    total = sum(path.stat().st_size for path in files)
    removed = 0
    for path in sorted(files, key=lambda item: item.stat().st_atime_ns):
        if total <= max_size_mb * 1024 * 1024:
            break
        if preserve is not None and path == preserve:
            continue
        size = path.stat().st_size
        path.unlink()
        total -= size
        removed += 1
    return removed


def validate_image_file(file_path: Path) -> tuple[bool, str]:
    """Run the full image validation pipeline (Section 9).

    Checks:
    1. File exists and is a file
    2. Supported format (.jpg, .jpeg, .png, .webp)
    3. File integrity (can be opened and decoded)
    4. Not zero-length

    Args:
        file_path: Path to the image file.

    Returns:
        (is_valid, error_message). If valid, error_message is empty.
    """
    path = Path(file_path)

    # 1. Existence
    if not path.exists():
        return False, f"File not found: {path.name}"

    if not path.is_file():
        return False, f"Not a file: {path.name}"

    # 2. Format
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        return False, f"Unsupported format: {suffix}"

    # 3. Non-zero size
    if path.stat().st_size == 0:
        return False, "File is empty (0 bytes)"

    # 4. Image integrity
    try:
        with Image.open(path) as img:
            img.verify()
    except Exception as exc:
        return False, f"Corrupt or invalid image: {exc}"

    # 5. Can actually read pixels
    try:
        with Image.open(path) as img:
            img.load()  # Forces full decode
            width, height = img.size
            if width <= 0 or height <= 0:
                return False, f"Invalid dimensions: {width}×{height}"
    except Exception as exc:
        return False, f"Cannot decode image: {exc}"

    return True, ""


def get_image_dimensions(file_path: Path) -> tuple[int, int]:
    """Get image dimensions without fully loading into memory.

    Returns:
        (width, height) tuple. Returns (0, 0) on failure.
    """
    try:
        with Image.open(file_path) as img:
            return img.size
    except Exception:
        return (0, 0)


def create_thumbnail(
    source_path: Path,
    output_path: Path,
    size: tuple[int, int] = (400, 225),
    quality: int = 85,
) -> bool:
    """Create a thumbnail for a wallpaper image.

    Uses high-quality downsampling (LANCZOS).

    Args:
        source_path: Path to the original image.
        output_path: Where to save the thumbnail.
        size: Target thumbnail size (width, height).
        quality: JPEG quality (1-100).

    Returns:
        True if thumbnail was created successfully.
    """
    if (
        len(size) != 2
        or any(type(dimension) is not int or not 64 <= dimension <= 1024 for dimension in size)
        or size[0] * size[1] > 1_048_576
    ):
        raise ValueError("Thumbnail dimensions must be 64–1024 pixels with at most 1,048,576 pixels total.")
    if type(quality) is not int or not 1 <= quality <= 95:
        raise ValueError("Thumbnail JPEG quality must be an integer from 1 to 95.")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source_path) as img:
            thumbnail: Image.Image = img
            thumbnail.thumbnail(size, Image.Resampling.LANCZOS)
            # Save as JPEG for consistent thumbnails
            if thumbnail.mode in ("RGBA", "P"):
                thumbnail = thumbnail.convert("RGB")
            with tempfile.NamedTemporaryFile(
                dir=output_path.parent, prefix=".thumb-", suffix=".tmp", delete=False
            ) as temp_file:
                temporary_path = Path(temp_file.name)
            try:
                thumbnail.save(temporary_path, format="JPEG", quality=quality, optimize=True)
                os.replace(temporary_path, output_path)
            finally:
                temporary_path.unlink(missing_ok=True)
        logger.debug("Created thumbnail: %s", output_path.name)
        return True
    except Exception as exc:
        logger.warning("Failed to create thumbnail for an image (%s).", type(exc).__name__)
        return False
