"""Phase 11 regression coverage for release-hardening boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.constants import MAX_IMAGE_PIXELS
from app.database.models import Wallpaper
from app.services.download_service import DownloadService
from app.services.metadata_service import ImageValidationError, MetadataService
from app.services.wallpaper_service import WallpaperValidationError, WindowsWallpaperService
from app.sources.base import WallpaperSearchResult
from app.ui.components import detail_dialog, image_preview_task, wallpaper_card
from app.utils import hashing
from app.utils.image_utils import (
    ImageDimensionLimitError,
    create_thumbnail,
    validate_image_dimensions,
    validate_image_file,
)


class _HeaderOnlyImage:
    """Pillow-like header whose pixel operations are tracked but never allocated."""

    def __init__(self, size: tuple[int, int]) -> None:
        self.size = size
        self.format = "PNG"
        self.verify_called = False
        self.load_called = False
        self.thumbnail_called = False
        self.convert_called = False

    def __enter__(self) -> _HeaderOnlyImage:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def verify(self) -> None:
        self.verify_called = True

    def load(self) -> None:
        self.load_called = True

    def thumbnail(self, *_args: object, **_kwargs: object) -> None:
        self.thumbnail_called = True

    def convert(self, *_args: object, **_kwargs: object) -> _HeaderOnlyImage:
        self.convert_called = True
        return self


def _patch_image_open(monkeypatch: pytest.MonkeyPatch, size: tuple[int, int]) -> list[_HeaderOnlyImage]:
    opened: list[_HeaderOnlyImage] = []

    def open_header(_path: object) -> _HeaderOnlyImage:
        image = _HeaderOnlyImage(size)
        opened.append(image)
        return image

    monkeypatch.setattr(Image, "open", open_header)
    return opened


def test_pixel_limit_preserves_supported_8k_dimensions() -> None:
    validate_image_dimensions((8192, 4320))
    with pytest.raises(ImageDimensionLimitError, match="40 MP"):
        validate_image_dimensions((MAX_IMAGE_PIXELS + 1, 1))


def test_detail_dialog_rejects_oversized_preview_before_decode(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage

    image_path = tmp_path / "large-header.png"
    image_path.write_bytes(b"image header fixture")

    class HeaderReader:
        def __init__(self, _path: str) -> None:
            return None

        def size(self) -> QSize:
            return QSize(MAX_IMAGE_PIXELS + 1, 1)

        def read(self) -> QImage:
            pytest.fail("oversized image reached the Qt decoder")

    monkeypatch.setattr(detail_dialog, "QImageReader", HeaderReader)
    dialog = detail_dialog.DetailDialog(Wallpaper(path=str(image_path)))
    assert "40 MP" in dialog._preview_label.text()
    assert dialog._preview_source is None
    dialog.close()


def test_async_thumbnail_and_comparison_previews_check_dimensions_before_decode(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage

    class HeaderReader:
        def __init__(self, _path: str) -> None:
            return None

        def size(self) -> QSize:
            return QSize(MAX_IMAGE_PIXELS + 1, 1)

        def setAutoTransform(self, _enabled: bool) -> None:
            return None

        def setScaledSize(self, _size: QSize) -> None:
            return None

        def read(self) -> QImage:
            pytest.fail("oversized image reached the Qt decoder")

    source = tmp_path / "large-preview.png"
    source.write_bytes(b"image header fixture")
    monkeypatch.setattr(wallpaper_card, "QImageReader", HeaderReader)
    thumbnail_results = []
    thumbnail = wallpaper_card.ThumbnailLoader(7, str(source))
    thumbnail.loaded.connect(lambda item_id, pixmap: thumbnail_results.append((item_id, pixmap)))
    thumbnail.run()
    assert thumbnail_results and thumbnail_results[0][0] == 7
    assert not thumbnail_results[0][1].isNull()

    monkeypatch.setattr(image_preview_task, "QImageReader", HeaderReader)
    preview_results = []
    signals = image_preview_task.ImagePreviewSignals()
    signals.loaded.connect(lambda item_id, image: preview_results.append((item_id, image)))
    task = image_preview_task.ImagePreviewTask(8, str(source), QSize(200, 120), signals)
    task.run()
    assert preview_results and preview_results[0][0] == 8
    assert preview_results[0][1].isNull()


def test_image_validation_rejects_large_header_before_verify_or_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "oversized.png"
    path.write_bytes(b"header fixture")
    opened = _patch_image_open(monkeypatch, (MAX_IMAGE_PIXELS + 1, 1))

    valid, message = validate_image_file(path)

    assert not valid
    assert "40 MP" in message
    assert len(opened) == 1
    assert not opened[0].verify_called
    assert not opened[0].load_called


def test_thumbnail_and_perceptual_hash_stop_before_pixel_transforms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "large.png"
    source.write_bytes(b"header fixture")
    opened = _patch_image_open(monkeypatch, (MAX_IMAGE_PIXELS + 1, 1))

    assert not create_thumbnail(source, tmp_path / "cache" / "large.jpg")
    assert not opened[-1].thumbnail_called

    assert hashing.compute_phash(source) == ""
    assert not opened[-1].convert_called


def test_metadata_and_wallpaper_validation_reject_large_dimensions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "oversized.png"
    source.write_bytes(b"header fixture")

    opened = _patch_image_open(monkeypatch, (MAX_IMAGE_PIXELS + 1, 1))
    with pytest.raises(ImageValidationError, match="40 MP"):
        MetadataService().extract(source)
    assert not opened[0].verify_called

    opened = _patch_image_open(monkeypatch, (MAX_IMAGE_PIXELS + 1, 1))
    with pytest.raises(WallpaperValidationError, match="40 MP"):
        WindowsWallpaperService(simulate=True).validate_image_file(source)
    assert not opened[0].verify_called


class _DownloadResponse:
    headers = {"content-length": "1", "content-type": "image/png"}

    def __init__(self) -> None:
        self.closed = False

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        assert chunk_size == 8192
        yield b"x"

    def close(self) -> None:
        self.closed = True


def test_download_requires_public_https_without_credentials_or_local_ip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = DownloadService(tmp_path / "downloads", tmp_path / "temp")
    monkeypatch.setattr(
        service._session,
        "get",
        lambda *_args, **_kwargs: pytest.fail("invalid URL reached the network client"),
    )

    invalid_urls = (
        "http://example.invalid/image.png",
        "https://user:secret@example.invalid/image.png",
        "https://127.0.0.1/image.png",
        "https://example.invalid:8443/image.png",
    )
    for url in invalid_urls:
        result = service.download(WallpaperSearchResult(title="Rejected", download_url=url))
        assert not result.success
        assert "public HTTPS" in result.error_message


def test_download_does_not_follow_redirects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class RedirectResponse(_DownloadResponse):
        is_redirect = True

    service = DownloadService(tmp_path / "downloads", tmp_path / "temp")
    response = RedirectResponse()
    options: dict[str, object] = {}

    def get(*_args: object, **kwargs: object) -> RedirectResponse:
        options.update(kwargs)
        return response

    monkeypatch.setattr(service._session, "get", get)
    result = service.download(
        WallpaperSearchResult(
            title="Redirected",
            file_format="png",
            download_url="https://example.invalid/redirect.png",
        )
    )

    assert not result.success
    assert "Redirected image URLs" in result.error_message
    assert options["allow_redirects"] is False
    assert response.closed


def test_download_rejects_large_image_dimensions_and_cleans_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = DownloadService(tmp_path / "downloads", tmp_path / "temp")
    response = _DownloadResponse()
    monkeypatch.setattr(service._session, "get", lambda *_args, **_kwargs: response)
    opened = _patch_image_open(monkeypatch, (MAX_IMAGE_PIXELS + 1, 1))

    result = service.download(
        WallpaperSearchResult(
            title="Oversized",
            file_format="png",
            download_url="https://example.invalid/oversized.png",
        )
    )

    assert not result.success
    assert "40 MP" in result.error_message
    assert not opened[0].verify_called
    assert response.closed
    assert not list((tmp_path / "downloads").rglob("*.png"))
    assert not list((tmp_path / "temp").glob("*.part"))
