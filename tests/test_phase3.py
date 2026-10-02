"""
Sandy Wallpaper Studio — Phase 3 Tests
=========================================
Tests for hashing, duplicate detection, image validation,
and filename sanitization.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.database.database import Database
from app.database.models import Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.services.duplicate_service import DuplicateMatch, DuplicateService
from app.services.metadata_service import MetadataService
from app.utils.filename import sanitize_filename, unique_path
from app.utils.hashing import (
    compute_ahash,
    compute_dhash,
    compute_phash,
    compute_sha256,
    hamming_distance,
    similarity_percentage,
)
from app.utils.image_utils import create_thumbnail, get_image_dimensions, validate_image_file


# ============================================================
# Helpers
# ============================================================
def _create_image(path: Path, width: int, height: int, color=(100, 150, 200), fmt="JPEG") -> Path:
    suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(fmt, ".jpg")
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / f"img_{width}x{height}{suffix}"
    img = Image.new("RGB", (width, height), color=color)
    img.save(file_path, format=fmt)
    return file_path


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    database.connect()
    yield database
    database.close()


# ============================================================
# SHA-256 Hashing Tests
# ============================================================
class TestSHA256:
    def test_compute_sha256(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 100, 100)
        h = compute_sha256(img)
        assert len(h) == 64  # 256-bit hex

    def test_identical_files_same_hash(self, tmp_path: Path) -> None:
        img1 = _create_image(tmp_path, 100, 100, color=(255, 0, 0))
        h1 = compute_sha256(img1)
        h2 = compute_sha256(img1)
        assert h1 == h2

    def test_different_files_different_hash(self, tmp_path: Path) -> None:
        img1 = _create_image(tmp_path / "a", 100, 100, color=(255, 0, 0))
        img2 = _create_image(tmp_path / "b", 100, 100, color=(0, 255, 0))
        assert compute_sha256(img1) != compute_sha256(img2)


# ============================================================
# Perceptual Hashing Tests
# ============================================================
class TestPerceptualHashing:
    def test_compute_phash(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 200, 200)
        h = compute_phash(img)
        assert isinstance(h, str)
        assert len(h) > 0

    def test_compute_dhash(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 200, 200)
        h = compute_dhash(img)
        assert isinstance(h, str)
        assert len(h) > 0

    def test_compute_ahash(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 200, 200)
        h = compute_ahash(img)
        assert isinstance(h, str)
        assert len(h) > 0

    def test_identical_images_same_phash(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 200, 200)
        h1 = compute_phash(img)
        h2 = compute_phash(img)
        assert h1 == h2

    def test_similar_images_close_phash(self, tmp_path: Path) -> None:
        # Same structure, slightly different color
        img1 = _create_image(tmp_path / "s1", 200, 200, color=(100, 100, 100))
        img2 = _create_image(tmp_path / "s2", 200, 200, color=(105, 105, 105))
        h1 = compute_phash(img1)
        h2 = compute_phash(img2)
        dist = hamming_distance(h1, h2)
        # Very similar solid colors should have low distance
        assert dist >= 0
        assert dist <= 15  # Relaxed for solid color test

    def test_hamming_distance_identical(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 100, 100)
        h = compute_phash(img)
        assert hamming_distance(h, h) == 0

    def test_hamming_distance_empty(self) -> None:
        assert hamming_distance("", "abc") == -1
        assert hamming_distance("abc", "") == -1

    def test_similarity_percentage(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 100, 100)
        h = compute_phash(img)
        assert similarity_percentage(h, h) == 100.0

    def test_similarity_percentage_empty(self) -> None:
        assert similarity_percentage("", "abc") == -1.0

    def test_phash_invalid_file(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.txt"
        bad.write_text("not an image")
        h = compute_phash(bad)
        assert h == ""


# ============================================================
# Image Validation Tests
# ============================================================
class TestImageValidation:
    def test_valid_jpeg(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 1920, 1080, fmt="JPEG")
        valid, err = validate_image_file(img)
        assert valid is True
        assert err == ""

    def test_valid_png(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 1920, 1080, fmt="PNG")
        valid, err = validate_image_file(img)
        assert valid is True

    def test_file_not_found(self, tmp_path: Path) -> None:
        valid, err = validate_image_file(tmp_path / "nope.jpg")
        assert valid is False
        assert "not found" in err.lower()

    def test_unsupported_format(self, tmp_path: Path) -> None:
        bmp = tmp_path / "test.bmp"
        Image.new("RGB", (100, 100)).save(bmp, format="BMP")
        valid, err = validate_image_file(bmp)
        assert valid is False
        assert "Unsupported" in err

    def test_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.jpg"
        empty.write_bytes(b"")
        valid, err = validate_image_file(empty)
        assert valid is False
        assert "empty" in err.lower()

    def test_corrupt_file(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.jpg"
        corrupt.write_bytes(b"NOT AN IMAGE AT ALL")
        valid, err = validate_image_file(corrupt)
        assert valid is False

    def test_get_dimensions(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 3840, 2160)
        w, h = get_image_dimensions(img)
        assert w == 3840
        assert h == 2160

    def test_get_dimensions_invalid(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.jpg"
        bad.write_text("not image")
        w, h = get_image_dimensions(bad)
        assert w == 0 and h == 0


# ============================================================
# Thumbnail Tests
# ============================================================
class TestThumbnail:
    def test_create_thumbnail(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 3840, 2160)
        thumb_path = tmp_path / "thumbnails" / "thumb.jpg"
        success = create_thumbnail(img, thumb_path)
        assert success is True
        assert thumb_path.exists()
        # Verify thumbnail dimensions
        w, h = get_image_dimensions(thumb_path)
        assert w <= 400
        assert h <= 225

    def test_create_thumbnail_png_source(self, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 1920, 1080, fmt="PNG")
        thumb = tmp_path / "thumb.jpg"
        assert create_thumbnail(img, thumb) is True
        assert thumb.exists()


# ============================================================
# Filename Sanitization Tests
# ============================================================
class TestFilenameSanitization:
    def test_basic(self) -> None:
        assert sanitize_filename("Mountain Sunset") == "Mountain_Sunset"

    def test_special_chars(self) -> None:
        result = sanitize_filename('File:Hello<>:"/\\|?*World')
        assert "<" not in result
        assert ">" not in result
        assert "\\" not in result
        assert "/" not in result
        assert ":" not in result

    def test_path_traversal(self) -> None:
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_empty(self) -> None:
        assert sanitize_filename("") == "untitled"

    def test_max_length(self) -> None:
        long_name = "A" * 300
        result = sanitize_filename(long_name, max_length=100)
        assert len(result) <= 100

    def test_unique_path(self, tmp_path: Path) -> None:
        file1 = tmp_path / "photo.jpg"
        file1.write_text("test")
        unique = unique_path(file1)
        assert unique.name == "photo_2.jpg"

    def test_unique_path_no_conflict(self, tmp_path: Path) -> None:
        target = tmp_path / "new.jpg"
        assert unique_path(target) == target

    def test_unique_path_multiple(self, tmp_path: Path) -> None:
        for i in range(1, 4):
            suffix = f"_{i}" if i > 1 else ""
            (tmp_path / f"photo{suffix}.jpg").write_text(f"v{i}")
        (tmp_path / "photo.jpg").write_text("v1")
        result = unique_path(tmp_path / "photo.jpg")
        assert result.name == "photo_4.jpg"


# ============================================================
# Duplicate Service Tests
# ============================================================
class TestDuplicateService:
    def test_check_exact_duplicate_found(self, db: Database, tmp_path: Path) -> None:
        repo = WallpaperRepository(db)
        img = _create_image(tmp_path, 100, 100)
        sha = compute_sha256(img)
        repo.add(Wallpaper(filename="orig.jpg", sha256=sha, path="/orig.jpg"))

        svc = DuplicateService(db)
        result = svc.check_exact_duplicate(sha)
        assert result is not None
        assert result.sha256 == sha

    def test_check_exact_duplicate_not_found(self, db: Database) -> None:
        svc = DuplicateService(db)
        assert svc.check_exact_duplicate("nonexistent_hash") is None

    def test_check_exact_duplicate_file(self, db: Database, tmp_path: Path) -> None:
        img = _create_image(tmp_path, 100, 100)
        sha = compute_sha256(img)
        repo = WallpaperRepository(db)
        repo.add(Wallpaper(filename="orig.jpg", sha256=sha, path="/orig.jpg"))

        svc = DuplicateService(db)
        result = svc.check_exact_duplicate_file(img)
        assert result is not None

    def test_threshold_property(self, db: Database) -> None:
        svc = DuplicateService(db, threshold=15)
        assert svc.threshold == 15
        svc.threshold = 20
        assert svc.threshold == 20
        svc.threshold = -1
        assert svc.threshold == 0

    def test_find_near_duplicates_empty_library(self, db: Database) -> None:
        svc = DuplicateService(db)
        matches = svc.find_near_duplicates("abcdef1234")
        assert matches == []

    def test_scan_all_empty(self, db: Database) -> None:
        svc = DuplicateService(db)
        groups = svc.scan_all_duplicates()
        assert groups == []

    def test_duplicate_match_repr(self) -> None:
        m = DuplicateMatch(
            original=Wallpaper(id=1),
            duplicate=Wallpaper(id=2),
            match_type="near",
            distance=5,
            similarity=92.19,
        )
        assert "near" in repr(m)
        assert "92.19" in repr(m)
        assert m.is_exact is False

    def test_exact_match_is_exact(self) -> None:
        m = DuplicateMatch(
            original=Wallpaper(id=1),
            duplicate=Wallpaper(id=2),
            match_type="exact",
            distance=0,
            similarity=100.0,
        )
        assert m.is_exact is True
