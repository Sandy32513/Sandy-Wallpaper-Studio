"""
Sandy Wallpaper Studio - Metadata Service
============================================
Extracts and validates image metadata from files.
Handles resolution classification, aspect ratio detection,
and image integrity validation (Section 9).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from PIL import Image

from app.constants import (
    ASPECT_RATIO_TOLERANCE,
    ASPECT_RATIOS,
    MIN_ACCEPTED_HEIGHT,
    MIN_ACCEPTED_WIDTH,
    RESOLUTION_CLASSES,
    SUPPORTED_FORMATS,
)

logger = logging.getLogger(__name__)


class ImageValidationError(Exception):
    """Raised when an image fails validation."""
    pass


class ImageMetadata:
    """Extracted metadata for a single image file."""

    def __init__(
        self,
        path: Path,
        width: int,
        height: int,
        file_size: int,
        file_format: str,
        sha256: str,
        aspect_ratio: str,
        resolution_class: str,
    ) -> None:
        self.path = path
        self.width = width
        self.height = height
        self.file_size = file_size
        self.file_format = file_format
        self.sha256 = sha256
        self.aspect_ratio = aspect_ratio
        self.resolution_class = resolution_class

    @property
    def is_high_res(self) -> bool:
        """True if the image meets minimum 4K dimensions."""
        return (
            self.width >= RESOLUTION_CLASSES["4K"]["min_width"]
            and self.height >= RESOLUTION_CLASSES["4K"]["min_height"]
        )

    def __repr__(self) -> str:
        return (
            f"ImageMetadata({self.width}×{self.height}, "
            f"{self.resolution_class}, {self.aspect_ratio})"
        )


class MetadataService:
    """Service for extracting and validating image metadata."""

    def extract(self, file_path: Path) -> ImageMetadata:
        """Extract full metadata from an image file.

        Performs all validation steps from Section 9:
        1. File existence
        2. Supported format
        3. File integrity / decode validation
        4. Dimension extraction
        5. SHA-256 hash calculation
        6. Resolution classification
        7. Aspect ratio detection

        Args:
            file_path: Path to the image file.

        Returns:
            ImageMetadata with all extracted information.

        Raises:
            ImageValidationError: If the image fails any validation step.
        """
        path = Path(file_path)

        # 1. File exists
        if not path.exists():
            raise ImageValidationError(f"File not found: {path}")

        if not path.is_file():
            raise ImageValidationError(f"Not a file: {path}")

        # 2. Supported format
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            raise ImageValidationError(
                f"Unsupported format: {suffix}. "
                f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )

        # 3. File integrity + decode validation
        try:
            with Image.open(path) as img:
                img.verify()  # Checks for corruption
        except Exception as exc:
            raise ImageValidationError(f"Corrupt or invalid image: {exc}") from exc

        # Re-open after verify() (verify closes the file)
        try:
            with Image.open(path) as img:
                width, height = img.size
                img_format = img.format or ""
        except Exception as exc:
            raise ImageValidationError(f"Cannot read image dimensions: {exc}") from exc

        # 4. Validate dimensions
        if width <= 0 or height <= 0:
            raise ImageValidationError(f"Invalid dimensions: {width}×{height}")

        # 5. File size
        file_size = path.stat().st_size

        # 6. SHA-256
        sha256 = self.calculate_sha256(path)

        # 7. Resolution class
        resolution_class = self.classify_resolution(width, height)

        # 8. Aspect ratio
        aspect_ratio = self.detect_aspect_ratio(width, height)

        # 9. File format string
        file_format = suffix.lstrip(".")

        metadata = ImageMetadata(
            path=path,
            width=width,
            height=height,
            file_size=file_size,
            file_format=file_format,
            sha256=sha256,
            aspect_ratio=aspect_ratio,
            resolution_class=resolution_class,
        )

        logger.debug("Extracted metadata: %s", metadata)
        return metadata

    def validate_minimum_resolution(
        self,
        width: int,
        height: int,
        min_width: int = MIN_ACCEPTED_WIDTH,
        min_height: int = MIN_ACCEPTED_HEIGHT,
    ) -> bool:
        """Check if dimensions meet the minimum resolution threshold."""
        return width >= min_width and height >= min_height

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Calculate SHA-256 hash of a file (Level 1 duplicate detection)."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def classify_resolution(width: int, height: int) -> str:
        """Classify image resolution into a named class.

        Checks in order: 8K > 5K > 4K > UW-5K > UW-QHD > QHD > FHD.
        Returns the highest matching class, or "HD" / "SD" / "Other".

        Never upscales: classification is based on actual pixels only.
        """
        # Check in descending order of resolution
        for cls_name in ("8K", "5K", "4K", "UW-5K", "UW-QHD", "QHD", "FHD"):
            cls = RESOLUTION_CLASSES[cls_name]
            if width >= cls["min_width"] and height >= cls["min_height"]:
                return cls_name

        # Below FHD
        if width >= 1280 and height >= 720:
            return "HD"

        return "SD"

    @staticmethod
    def detect_aspect_ratio(width: int, height: int) -> str:
        """Detect the closest standard aspect ratio.

        Returns a string like "16:9", "21:9", or "Portrait".
        """
        if width <= 0 or height <= 0:
            return "Unknown"

        ratio = width / height

        # Check portrait orientation
        if ratio < 1.0:
            return "Portrait"

        # Match against known ratios
        closest_name = "Other"
        closest_diff = float("inf")

        for name, target_ratio in ASPECT_RATIOS.items():
            diff = abs(ratio - target_ratio)
            if diff < closest_diff:
                closest_diff = diff
                closest_name = name

        # Only return a named ratio if within tolerance
        if closest_diff <= ASPECT_RATIO_TOLERANCE:
            return closest_name

        return "Other"
