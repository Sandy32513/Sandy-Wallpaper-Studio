"""
Sandy Wallpaper Studio - Filename Utilities
==============================================
Safe filename generation and sanitization (Section 26).
"""

from __future__ import annotations

import re
from pathlib import Path


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Sanitize a string for use as a filename.

    - Removes characters unsafe on Windows (\\/:*?"<>|)
    - Replaces spaces with underscores
    - Truncates to max_length
    - Prevents path traversal (removes .. and /)

    Args:
        name: Raw filename string.
        max_length: Maximum character length.

    Returns:
        Safe filename string.
    """
    if not name:
        return "untitled"

    # Remove path traversal attempts
    name = name.replace("..", "").replace("/", "").replace("\\", "")

    # Remove unsafe characters for Windows
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)

    # Replace spaces with underscores
    name = re.sub(r"\s+", "_", name.strip())

    # Remove leading/trailing dots and underscores
    name = name.strip("._")

    # Truncate
    if len(name) > max_length:
        name = name[:max_length]

    return name or "untitled"


def unique_path(target: Path) -> Path:
    """Generate a unique file path by appending a counter if needed.

    Example: photo.jpg -> photo_2.jpg -> photo_3.jpg

    Args:
        target: Desired file path.

    Returns:
        A path that does not exist yet.
    """
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    counter = 2

    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1
        if counter > 9999:
            raise RuntimeError(f"Too many duplicates for {stem}{suffix}")
