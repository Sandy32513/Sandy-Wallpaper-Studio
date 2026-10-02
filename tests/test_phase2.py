"""
Sandy Wallpaper Studio — Phase 2 Tests
=========================================
Tests for Wikimedia source, download service, metadata service,
and source service. All network calls are mocked (Rule: no Internet for tests).
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from PIL import Image

from app.services.download_service import DownloadResult, DownloadService
from app.services.metadata_service import (
    ImageMetadata,
    ImageValidationError,
    MetadataService,
)
from app.services.source_service import SourceService
from app.sources.base import WallpaperSearchResult, WallpaperSource
from app.sources.wikimedia import (
    WikimediaSource,
    _is_supported_mime,
    _mime_to_extension,
    _strip_html,
)


# ============================================================
# Helpers
# ============================================================
def _create_test_image(
    path: Path,
    width: int = 3840,
    height: int = 2160,
    fmt: str = "JPEG",
) -> Path:
    """Create a test image file."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(fmt, ".jpg")
    file_path = path / f"test_image{suffix}"
    img.save(file_path, format=fmt)
    return file_path


def _make_wikimedia_api_response(titles: list[str], pages: dict | None = None) -> dict:
    """Build a fake MediaWiki API response."""
    if pages is None:
        pages = {}
        for idx, title in enumerate(titles):
            pages[str(idx + 1)] = {
                "pageid": idx + 1,
                "title": title,
                "index": idx,
                "imageinfo": [
                    {
                        "url": f"https://upload.wikimedia.org/wikipedia/commons/test/{title.replace('File:', '')}",
                        "thumburl": f"https://upload.wikimedia.org/thumb/{title.replace('File:', '')}",
                        "width": 3840,
                        "height": 2160,
                        "size": 5242880,
                        "mime": "image/jpeg",
                        "mediatype": "BITMAP",
                        "extmetadata": {
                            "Artist": {"value": "Test Author"},
                            "LicenseShortName": {"value": "CC-BY-SA-4.0"},
                            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                            "ImageDescription": {"value": "A <b>beautiful</b> test image"},
                            "Categories": {"value": "Nature|Mountains|Landscapes"},
                        },
                    }
                ],
            }
    return {"query": {"pages": pages}}


# ============================================================
# Wikimedia Helper Tests
# ============================================================
class TestWikimediaHelpers:
    def test_supported_mime_jpeg(self) -> None:
        assert _is_supported_mime("image/jpeg") is True

    def test_supported_mime_png(self) -> None:
        assert _is_supported_mime("image/png") is True

    def test_supported_mime_webp(self) -> None:
        assert _is_supported_mime("image/webp") is True

    def test_unsupported_mime_svg(self) -> None:
        assert _is_supported_mime("image/svg+xml") is False

    def test_unsupported_mime_tiff(self) -> None:
        assert _is_supported_mime("image/tiff") is False

    def test_mime_to_extension(self) -> None:
        assert _mime_to_extension("image/jpeg") == "jpg"
        assert _mime_to_extension("image/png") == "png"
        assert _mime_to_extension("image/webp") == "webp"
        assert _mime_to_extension("image/tiff") == ""

    def test_strip_html(self) -> None:
        assert _strip_html("<b>Bold</b> text") == "Bold text"
        assert _strip_html("<a href='url'>Link</a>") == "Link"
        assert _strip_html("") == ""
        assert _strip_html("No HTML") == "No HTML"

    def test_strip_html_collapses_whitespace(self) -> None:
        assert _strip_html("  Multiple   spaces  ") == "Multiple spaces"


# ============================================================
# Wikimedia Source Tests (Mocked)
# ============================================================
class TestWikimediaSource:
    def test_properties(self) -> None:
        source = WikimediaSource()
        assert source.name == "wikimedia"
        assert source.display_name == "Wikimedia Commons"
        assert "commons.wikimedia.org" in source.base_url

    @patch("app.sources.wikimedia.WikimediaSource._search_files")
    @patch("app.sources.wikimedia.WikimediaSource._get_image_info_batch")
    def test_search_success(self, mock_batch, mock_search) -> None:
        mock_search.return_value = ["File:Mountain.jpg"]
        mock_batch.return_value = [
            WallpaperSearchResult(
                source_id="File:Mountain.jpg",
                title="Mountain",
                width=3840,
                height=2160,
                source_name="wikimedia",
            )
        ]
        source = WikimediaSource()
        results = source.search("mountain", min_width=3840)
        assert len(results) == 1
        assert results[0].title == "Mountain"

    @patch("app.sources.wikimedia.WikimediaSource._search_files")
    def test_search_no_results(self, mock_search) -> None:
        mock_search.return_value = []
        source = WikimediaSource()
        results = source.search("xyznonexistent123")
        assert results == []

    @patch("app.sources.wikimedia.WikimediaSource._search_files")
    def test_search_network_error(self, mock_search) -> None:
        import requests
        mock_search.side_effect = requests.ConnectionError("No network")
        source = WikimediaSource()
        results = source.search("mountain")
        assert results == []  # Graceful failure

    @patch("app.sources.wikimedia.WikimediaSource._get_image_info_batch")
    def test_get_image_info(self, mock_batch) -> None:
        mock_batch.return_value = [
            WallpaperSearchResult(
                source_id="File:Test.jpg",
                title="Test",
                download_url="https://example.com/test.jpg",
            )
        ]
        source = WikimediaSource()
        info = source.get_image_info("File:Test.jpg")
        assert info is not None
        assert info.download_url == "https://example.com/test.jpg"

    @patch("app.sources.wikimedia.WikimediaSource._get_image_info_batch")
    def test_get_download_url(self, mock_batch) -> None:
        mock_batch.return_value = [
            WallpaperSearchResult(
                source_id="File:Test.jpg",
                download_url="https://example.com/test.jpg",
            )
        ]
        source = WikimediaSource()
        url = source.get_download_url("File:Test.jpg")
        assert url == "https://example.com/test.jpg"

    def test_repr(self) -> None:
        source = WikimediaSource()
        assert "wikimedia" in repr(source)


# ============================================================
# WallpaperSearchResult Tests
# ============================================================
class TestWallpaperSearchResult:
    def test_resolution_label(self) -> None:
        r = WallpaperSearchResult(width=3840, height=2160)
        assert r.resolution_label == "3840×2160"

    def test_resolution_label_unknown(self) -> None:
        r = WallpaperSearchResult()
        assert r.resolution_label == "Unknown"

    def test_file_size_mb(self) -> None:
        r = WallpaperSearchResult(file_size=10485760)
        assert r.file_size_mb == 10.0


# ============================================================
# MetadataService Tests
# ============================================================
class TestMetadataService:
    def test_extract_jpeg(self, tmp_path: Path) -> None:
        img_path = _create_test_image(tmp_path, 3840, 2160, "JPEG")
        svc = MetadataService()
        meta = svc.extract(img_path)
        assert meta.width == 3840
        assert meta.height == 2160
        assert meta.resolution_class == "4K"
        assert meta.aspect_ratio == "16:9"
        assert meta.file_format == "jpg"
        assert len(meta.sha256) == 64

    def test_extract_png(self, tmp_path: Path) -> None:
        img_path = _create_test_image(tmp_path, 5120, 2880, "PNG")
        svc = MetadataService()
        meta = svc.extract(img_path)
        assert meta.width == 5120
        assert meta.height == 2880
        assert meta.resolution_class == "5K"

    def test_extract_8k(self, tmp_path: Path) -> None:
        img_path = _create_test_image(tmp_path, 7680, 4320, "JPEG")
        svc = MetadataService()
        meta = svc.extract(img_path)
        assert meta.resolution_class == "8K"

    def test_extract_fhd(self, tmp_path: Path) -> None:
        img_path = _create_test_image(tmp_path, 1920, 1080, "JPEG")
        svc = MetadataService()
        meta = svc.extract(img_path)
        assert meta.resolution_class == "FHD"

    def test_extract_hd(self, tmp_path: Path) -> None:
        img_path = _create_test_image(tmp_path, 1280, 720, "JPEG")
        svc = MetadataService()
        meta = svc.extract(img_path)
        assert meta.resolution_class == "HD"

    def test_extract_sd(self, tmp_path: Path) -> None:
        img_path = _create_test_image(tmp_path, 640, 480, "JPEG")
        svc = MetadataService()
        meta = svc.extract(img_path)
        assert meta.resolution_class == "SD"

    def test_file_not_found(self, tmp_path: Path) -> None:
        svc = MetadataService()
        with pytest.raises(ImageValidationError, match="File not found"):
            svc.extract(tmp_path / "nonexistent.jpg")

    def test_unsupported_format(self, tmp_path: Path) -> None:
        bmp_path = tmp_path / "test.bmp"
        img = Image.new("RGB", (100, 100))
        img.save(bmp_path, format="BMP")
        svc = MetadataService()
        with pytest.raises(ImageValidationError, match="Unsupported format"):
            svc.extract(bmp_path)

    def test_corrupt_image(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.jpg"
        corrupt.write_bytes(b"NOT AN IMAGE")
        svc = MetadataService()
        with pytest.raises(ImageValidationError):
            svc.extract(corrupt)

    def test_sha256_consistency(self, tmp_path: Path) -> None:
        img_path = _create_test_image(tmp_path, 100, 100, "JPEG")
        svc = MetadataService()
        h1 = svc.calculate_sha256(img_path)
        h2 = svc.calculate_sha256(img_path)
        assert h1 == h2
        assert len(h1) == 64

    def test_classify_resolution(self) -> None:
        svc = MetadataService()
        assert svc.classify_resolution(7680, 4320) == "8K"
        assert svc.classify_resolution(5120, 2880) == "5K"
        assert svc.classify_resolution(3840, 2160) == "4K"
        assert svc.classify_resolution(2560, 1440) == "QHD"
        assert svc.classify_resolution(1920, 1080) == "FHD"
        assert svc.classify_resolution(1280, 720) == "HD"
        assert svc.classify_resolution(640, 480) == "SD"

    def test_detect_aspect_ratio(self) -> None:
        svc = MetadataService()
        assert svc.detect_aspect_ratio(3840, 2160) == "16:9"
        assert svc.detect_aspect_ratio(2560, 1600) == "16:10"
        assert svc.detect_aspect_ratio(1080, 1920) == "Portrait"

    def test_validate_minimum_resolution(self) -> None:
        svc = MetadataService()
        assert svc.validate_minimum_resolution(3840, 2160) is True
        assert svc.validate_minimum_resolution(1920, 1080) is True
        assert svc.validate_minimum_resolution(800, 600) is False

    def test_is_high_res(self, tmp_path: Path) -> None:
        img_path = _create_test_image(tmp_path, 3840, 2160, "JPEG")
        svc = MetadataService()
        meta = svc.extract(img_path)
        assert meta.is_high_res is True

    def test_is_not_high_res(self, tmp_path: Path) -> None:
        img_path = _create_test_image(tmp_path, 1920, 1080, "JPEG")
        svc = MetadataService()
        meta = svc.extract(img_path)
        assert meta.is_high_res is False


# ============================================================
# DownloadService Tests (Mocked)
# ============================================================
class TestDownloadService:
    def test_sanitize_filename(self, tmp_path: Path) -> None:
        svc = DownloadService(
            download_dir=tmp_path / "dl",
            temp_dir=tmp_path / "tmp",
        )
        result = WallpaperSearchResult(
            title="Mountain Sunset",
            width=3840,
            height=2160,
            file_format="jpg",
        )
        filename = svc._sanitize_filename(result)
        assert filename == "Mountain_Sunset_3840x2160.jpg"

    def test_sanitize_filename_special_chars(self, tmp_path: Path) -> None:
        svc = DownloadService(
            download_dir=tmp_path / "dl",
            temp_dir=tmp_path / "tmp",
        )
        result = WallpaperSearchResult(
            title="File:Héllo/World\\Test<>:.jpg",
            file_format="png",
            width=1920,
            height=1080,
        )
        filename = svc._sanitize_filename(result)
        assert "/" not in filename
        assert "\\" not in filename
        assert "<" not in filename
        assert filename.endswith(".png")

    def test_sanitize_dirname(self, tmp_path: Path) -> None:
        svc = DownloadService(
            download_dir=tmp_path / "dl",
            temp_dir=tmp_path / "tmp",
        )
        assert svc._sanitize_dirname("Nature") == "Nature"
        assert svc._sanitize_dirname("AI / Digital Art") == "AI_Digital_Art"
        assert svc._sanitize_dirname("") == "Uncategorized"

    def test_download_no_url(self, tmp_path: Path) -> None:
        svc = DownloadService(
            download_dir=tmp_path / "dl",
            temp_dir=tmp_path / "tmp",
        )
        result = WallpaperSearchResult(title="No URL")
        dl_result = svc.download(result)
        assert dl_result.success is False
        assert "No download URL" in dl_result.error_message

    def test_download_invalid_scheme(self, tmp_path: Path) -> None:
        svc = DownloadService(
            download_dir=tmp_path / "dl",
            temp_dir=tmp_path / "tmp",
        )
        result = WallpaperSearchResult(
            title="Bad",
            download_url="ftp://evil.com/file.jpg",
            file_format="jpg",
        )
        dl_result = svc.download(result)
        assert dl_result.success is False
        assert "Invalid URL" in dl_result.error_message

    def test_download_file_exists(self, tmp_path: Path) -> None:
        dl_dir = tmp_path / "dl"
        dl_dir.mkdir()
        # Pre-create the target file
        existing = dl_dir / "Existing_3840x2160.jpg"
        existing.write_text("exists")

        svc = DownloadService(
            download_dir=dl_dir,
            temp_dir=tmp_path / "tmp",
        )
        result = WallpaperSearchResult(
            title="Existing",
            download_url="https://example.com/test.jpg",
            width=3840,
            height=2160,
            file_format="jpg",
        )
        dl_result = svc.download(result)
        assert dl_result.success is False
        assert "already exists" in dl_result.error_message

    def test_download_result_repr(self) -> None:
        r = DownloadResult(success=True, file_path=Path("/test.jpg"))
        assert "success=True" in repr(r)
        r2 = DownloadResult(success=False, error_message="fail")
        assert "fail" in repr(r2)


# ============================================================
# SourceService Tests
# ============================================================
class TestSourceService:
    def test_default_registration(self) -> None:
        svc = SourceService()
        assert "wikimedia" in svc.get_names()

    def test_get_source(self) -> None:
        svc = SourceService()
        source = svc.get("wikimedia")
        assert source is not None
        assert source.name == "wikimedia"

    def test_get_unknown_source(self) -> None:
        svc = SourceService()
        assert svc.get("nonexistent") is None

    def test_get_all(self) -> None:
        svc = SourceService()
        sources = svc.get_all()
        assert len(sources) >= 1

    def test_search_unknown_source(self) -> None:
        svc = SourceService()
        results = svc.search("test", source_name="nonexistent")
        assert results == []

    @patch.object(WikimediaSource, "search")
    def test_search_delegates_to_source(self, mock_search) -> None:
        mock_search.return_value = [
            WallpaperSearchResult(title="Test", source_name="wikimedia")
        ]
        svc = SourceService()
        results = svc.search("test", source_name="wikimedia")
        assert len(results) == 1
        mock_search.assert_called_once()

    @patch.object(WikimediaSource, "search")
    def test_search_handles_source_failure(self, mock_search) -> None:
        mock_search.side_effect = Exception("Provider crashed")
        svc = SourceService()
        results = svc.search("test")  # Should not raise
        assert results == []

    def test_register_custom_source(self) -> None:
        svc = SourceService()

        class FakeSource(WallpaperSource):
            @property
            def name(self): return "fake"
            @property
            def display_name(self): return "Fake"
            @property
            def description(self): return "Test"
            @property
            def base_url(self): return "https://fake.com"
            def search(self, **kw): return []
            def get_image_info(self, sid): return None
            def get_download_url(self, sid): return None

        svc.register(FakeSource())
        assert "fake" in svc.get_names()
        assert len(svc.get_all()) >= 2
