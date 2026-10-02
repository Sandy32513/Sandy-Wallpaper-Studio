"""
Sandy Wallpaper Studio - Image Utilities
===========================================
Image validation and processing utilities (Section 9).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from app.constants import SUPPORTED_FORMATS

logger = logging.getLogger(__name__)


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
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            # Save as JPEG for consistent thumbnails
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output_path, format="JPEG", quality=quality, optimize=True)
        logger.debug("Created thumbnail: %s", output_path.name)
        return True
    except Exception as exc:
        logger.error("Failed to create thumbnail for %s: %s", source_path, exc)
        return False
