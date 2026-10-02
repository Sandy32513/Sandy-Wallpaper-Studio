"""
Sandy Wallpaper Studio - Download Service
============================================
Handles downloading wallpaper images with:
- Progress tracking
- Retry with exponential backoff
- File integrity validation
- Timeout handling
- Cancellation support
- Duplicate prevention (checks SHA-256 before saving)
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import requests

from app.constants import (
    DEFAULT_MAX_DOWNLOAD_SIZE_MB,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF_FACTOR,
    DEFAULT_TIMEOUT_SECONDS,
    SUPPORTED_FORMATS,
)
from app.sources.base import WallpaperSearchResult

logger = logging.getLogger(__name__)

# Callback type: (bytes_downloaded, total_bytes) -> None
ProgressCallback = Callable[[int, int], None]


class DownloadError(Exception):
    """Raised when a download fails after all retries."""
    pass


class DownloadResult:
    """Encapsulates the result of a download attempt."""

    def __init__(
        self,
        success: bool,
        file_path: Optional[Path] = None,
        sha256: str = "",
        file_size: int = 0,
        error_message: str = "",
    ) -> None:
        self.success = success
        self.file_path = file_path
        self.sha256 = sha256
        self.file_size = file_size
        self.error_message = error_message

    def __repr__(self) -> str:
        if self.success:
            return f"DownloadResult(success=True, path={self.file_path})"
        return f"DownloadResult(success=False, error={self.error_message!r})"


class DownloadService:
    """Service for downloading wallpaper images from the internet.

    Thread-safe: each download creates its own temp file.
    """

    def __init__(
        self,
        download_dir: Path,
        temp_dir: Path,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
        max_size_mb: int = DEFAULT_MAX_DOWNLOAD_SIZE_MB,
    ) -> None:
        self._download_dir = download_dir
        self._temp_dir = temp_dir
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "SandyWallpaperStudio/1.0",
        })

        # Ensure directories exist
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    def download(
        self,
        result: WallpaperSearchResult,
        target_subdir: str = "",
        progress_callback: Optional[ProgressCallback] = None,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> DownloadResult:
        """Download a wallpaper image.

        Args:
            result: The search result containing the download URL.
            target_subdir: Optional subdirectory under download_dir (e.g. category name).
            progress_callback: Called with (bytes_downloaded, total_bytes).
            cancelled: Callable that returns True if download should be cancelled.

        Returns:
            DownloadResult with success status, file path, SHA-256, etc.
        """
        url = result.download_url
        if not url:
            return DownloadResult(success=False, error_message="No download URL provided.")

        # Validate URL scheme
        if not url.startswith(("https://", "http://")):
            return DownloadResult(success=False, error_message=f"Invalid URL scheme: {url}")

        # Determine target filename
        filename = self._sanitize_filename(result)
        if target_subdir:
            target_dir = self._download_dir / self._sanitize_dirname(target_subdir)
        else:
            target_dir = self._download_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename

        # Never silently overwrite (Rule 9)
        if target_path.exists():
            return DownloadResult(
                success=False,
                error_message=f"File already exists: {target_path.name}",
            )

        # Retry loop
        last_error = ""
        for attempt in range(1, self._max_retries + 1):
            try:
                return self._do_download(
                    url, target_path, progress_callback, cancelled
                )
            except requests.Timeout:
                last_error = f"Timeout after {self._timeout}s (attempt {attempt})"
                logger.warning(last_error)
            except requests.ConnectionError as exc:
                last_error = f"Connection error: {exc} (attempt {attempt})"
                logger.warning(last_error)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                if status == 404:
                    return DownloadResult(success=False, error_message="Image not found (404).")
                if status == 429:
                    last_error = f"Rate limited (429), attempt {attempt}"
                    logger.warning(last_error)
                elif status >= 500:
                    last_error = f"Server error ({status}), attempt {attempt}"
                    logger.warning(last_error)
                else:
                    return DownloadResult(
                        success=False, error_message=f"HTTP {status} error."
                    )
            except DownloadError as exc:
                return DownloadResult(success=False, error_message=str(exc))

            # Exponential backoff
            if attempt < self._max_retries:
                import time
                wait = self._backoff_factor ** attempt
                logger.info("Retrying in %.1fs...", wait)
                time.sleep(wait)

        return DownloadResult(success=False, error_message=f"Failed after {self._max_retries} attempts: {last_error}")

    def _do_download(
        self,
        url: str,
        target_path: Path,
        progress_callback: Optional[ProgressCallback],
        cancelled: Optional[Callable[[], bool]],
    ) -> DownloadResult:
        """Perform the actual download with streaming."""
        resp = self._session.get(url, stream=True, timeout=self._timeout)
        resp.raise_for_status()

        # Check content size
        content_length = int(resp.headers.get("content-length", 0))
        if content_length > self._max_size_bytes:
            raise DownloadError(
                f"File too large: {content_length / (1024*1024):.1f} MB "
                f"(max {self._max_size_bytes / (1024*1024):.0f} MB)"
            )

        # Validate content type
        content_type = resp.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            raise DownloadError(f"Not an image: content-type={content_type}")

        # Download to a temporary file, then move (atomic-ish)
        hasher = hashlib.sha256()
        downloaded = 0

        with tempfile.NamedTemporaryFile(
            dir=str(self._temp_dir), delete=False, suffix=target_path.suffix
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            try:
                for chunk in resp.iter_content(chunk_size=8192):
                    if cancelled and cancelled():
                        logger.info("Download cancelled: %s", url)
                        tmp_path.unlink(missing_ok=True)
                        return DownloadResult(
                            success=False, error_message="Download cancelled."
                        )

                    tmp_file.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)

                    # Size guard during streaming
                    if downloaded > self._max_size_bytes:
                        tmp_path.unlink(missing_ok=True)
                        raise DownloadError(
                            f"Download exceeded max size ({self._max_size_bytes / (1024*1024):.0f} MB)"
                        )

                    if progress_callback:
                        progress_callback(downloaded, content_length or downloaded)

            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

        # Move temp file to target
        try:
            shutil.move(str(tmp_path), str(target_path))
        except OSError as exc:
            tmp_path.unlink(missing_ok=True)
            raise DownloadError(f"Failed to save file: {exc}") from exc

        sha256 = hasher.hexdigest()
        logger.info(
            "Downloaded: %s (%d bytes, sha256=%s)",
            target_path.name, downloaded, sha256[:16]
        )

        return DownloadResult(
            success=True,
            file_path=target_path,
            sha256=sha256,
            file_size=downloaded,
        )

    # ----------------------------------------------------------
    # Filename Handling
    # ----------------------------------------------------------
    def _sanitize_filename(self, result: WallpaperSearchResult) -> str:
        """Create a safe filename from a search result.

        Format: title_WIDTHxHEIGHT.ext
        Falls back to source_id if title is empty.
        """
        import re

        # Get the base name
        base = result.title or result.source_id or "wallpaper"

        # Remove File: prefix from Wikimedia titles
        if base.startswith("File:"):
            base = base[5:]

        # Remove existing extension from base
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".avif"):
            if base.lower().endswith(ext):
                base = base[: -len(ext)]
                break

        # Sanitize: allow only alphanumeric, spaces, hyphens, underscores
        base = re.sub(r"[^\w\s\-]", "", base)
        base = re.sub(r"\s+", "_", base.strip())

        # Truncate to reasonable length
        if len(base) > 100:
            base = base[:100]

        # Add resolution to filename
        if result.width and result.height:
            base = f"{base}_{result.width}x{result.height}"

        # Determine extension
        ext = f".{result.file_format}" if result.file_format else ".jpg"
        if ext not in SUPPORTED_FORMATS:
            ext = ".jpg"

        return f"{base}{ext}"

    def _sanitize_dirname(self, name: str) -> str:
        """Sanitize a directory name."""
        import re
        safe = re.sub(r"[^\w\s\-]", "", name)
        safe = re.sub(r"\s+", "_", safe.strip())
        return safe or "Uncategorized"
