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
import ipaddress
import logging
import math
import os
import socket
import tempfile
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import urlsplit

import requests
from PIL import Image
from requests.adapters import HTTPAdapter
from requests.utils import select_proxy

from app.config import Config
from app.constants import (
    DEFAULT_MAX_DOWNLOAD_SIZE_MB,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF_FACTOR,
    DEFAULT_TIMEOUT_SECONDS,
    SUPPORTED_FORMATS,
)
from app.sources.base import WallpaperSearchResult
from app.utils.image_utils import ImageDimensionLimitError, validate_image_dimensions

logger = logging.getLogger(__name__)

# Callback type: (bytes_downloaded, total_bytes) -> None
ProgressCallback = Callable[[int, int], None]


def _is_safe_download_url(url: str) -> bool:
    """Accept direct HTTPS URLs without credentials or obvious local targets."""
    if not isinstance(url, str) or any(ord(char) < 32 or char.isspace() for char in url):
        return False
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        return False

    normalized_host = hostname.rstrip(".").lower()
    if normalized_host == "localhost" or normalized_host.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError:
        return True
    return address.is_global


class DownloadError(Exception):
    """Raised when a download fails after all retries."""
    pass


def _resolve_public_address(hostname: str, port: int) -> str:
    """Resolve once and select a globally routable address for the pinned socket."""
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None

    if literal is not None:
        addresses = [literal]
    else:
        try:
            records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
            address_texts = [record[4][0] for record in records]
            if any(not isinstance(address, str) for address in address_texts):
                raise ValueError("Resolver returned a non-text address.")
            addresses = [
                ipaddress.ip_address(address.split("%", 1)[0])
                for address in address_texts
                if isinstance(address, str)
            ]
        except (OSError, IndexError, TypeError, ValueError) as exc:
            raise DownloadError("The download host could not be resolved safely.") from exc

    if not addresses or any(
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
        for address in addresses
    ):
        raise DownloadError("The download host resolved to a non-public network address.")

    first = addresses[0]
    if isinstance(first, ipaddress.IPv6Address) and first.ipv4_mapped is not None:
        first = first.ipv4_mapped
    return first.compressed


class PublicAddressHTTPSAdapter(HTTPAdapter):
    """Bind HTTPS sockets to vetted DNS answers while retaining hostname TLS checks."""

    def get_connection_with_tls_context(
        self,
        request: requests.PreparedRequest,
        verify: bool | str | None,
        proxies: Mapping[str, str] | None = None,
        cert: tuple[str, str] | str | None = None,
    ):
        url = request.url
        if not url:
            raise DownloadError("Invalid URL: a direct public HTTPS URL is required.")
        proxy = select_proxy(url, proxies)
        if proxy:
            raise DownloadError("HTTPS proxies are not supported for pinned image downloads.")
        if verify is False:
            raise DownloadError("TLS certificate verification cannot be disabled.")

        parsed = urlsplit(url)
        hostname_value = parsed.hostname
        if not isinstance(hostname_value, str) or not hostname_value:
            raise DownloadError("Invalid URL: a direct public HTTPS URL is required.")
        hostname = hostname_value
        port = parsed.port or 443
        if not _is_safe_download_url(url):
            raise DownloadError("Invalid URL: a direct public HTTPS URL is required.")

        pinned_address = _resolve_public_address(hostname, port)
        tls_hostname = hostname.rstrip(".").encode("idna").decode("ascii").lower()
        host_header = f"[{hostname}]" if ":" in hostname else hostname
        if port != 443:
            host_header = f"{host_header}:{port}"
        request.headers["Host"] = host_header

        verify_setting = True if verify is None else verify
        host_params, pool_kwargs = self.build_connection_pool_key_attributes(
            request,
            verify_setting,
            cert,
        )
        host_params["host"] = pinned_address
        host_params["port"] = port
        extended_pool_kwargs = cast(dict[str, Any], dict(pool_kwargs))
        extended_pool_kwargs["server_hostname"] = tls_hostname
        extended_pool_kwargs["assert_hostname"] = tls_hostname
        return self.poolmanager.connection_from_host(
            **host_params,
            pool_kwargs=extended_pool_kwargs,
        )


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
        max_concurrent: int = 3,
    ) -> None:
        if type(timeout) is not int or not 1 <= timeout <= 300:
            raise ValueError("Download timeout must be between 1 and 300 seconds.")
        if type(max_retries) is not int or not 1 <= max_retries <= 10:
            raise ValueError("Retry count must be between 1 and 10.")
        if type(backoff_factor) not in (int, float) or not math.isfinite(backoff_factor) or not 1 <= backoff_factor <= 10:
            raise ValueError("Retry backoff must be a finite value from 1 to 10.")
        if type(max_size_mb) is not int or not 1 <= max_size_mb <= 2048:
            raise ValueError("Maximum image size must be from 1 to 2048 MB.")
        if type(max_concurrent) is not int or not 1 <= max_concurrent <= 8:
            raise ValueError("Concurrent download limit must be from 1 to 8.")
        self._download_dir = download_dir
        self._temp_dir = temp_dir
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._max_concurrent = max_concurrent
        self._semaphore = threading.BoundedSemaphore(max_concurrent)
        self._session = requests.Session()
        # Environment proxies can resolve the hostname on a different machine, defeating pinning.
        self._session.trust_env = False
        self._session.mount("https://", PublicAddressHTTPSAdapter())
        self._session.headers.update({
            "User-Agent": "SandyWallpaperStudio/1.0",
        })

        # Ensure directories exist
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_config(cls, config: Config) -> DownloadService:
        return cls(
            download_dir=Path(config.get("download_folder", str(config.library_path))),
            temp_dir=config.temp_dir,
            timeout=config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
            max_retries=config.get("max_retries", DEFAULT_MAX_RETRIES),
            backoff_factor=config.get("retry_backoff_factor", DEFAULT_RETRY_BACKOFF_FACTOR),
            max_size_mb=config.get("max_download_size_mb", DEFAULT_MAX_DOWNLOAD_SIZE_MB),
            max_concurrent=config.get("max_simultaneous_downloads", 3),
        )

    def download(
        self,
        result: WallpaperSearchResult,
        target_subdir: str = "",
        progress_callback: Optional[ProgressCallback] = None,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> DownloadResult:
        if not self._semaphore.acquire(timeout=self._timeout):
            return DownloadResult(success=False, error_message="Download queue is full; try again shortly.")
        try:
            return self._download_unlocked(result, target_subdir, progress_callback, cancelled)
        finally:
            self._semaphore.release()

    def _download_unlocked(
        self,
        result: WallpaperSearchResult,
        target_subdir: str,
        progress_callback: Optional[ProgressCallback],
        cancelled: Optional[Callable[[], bool]],
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

        if not _is_safe_download_url(url):
            return DownloadResult(
                success=False,
                error_message="Invalid URL: a direct public HTTPS URL is required.",
            )

        # Determine target filename
        filename = self._sanitize_filename(result)
        if target_subdir:
            target_dir = self._download_dir / self._sanitize_dirname(target_subdir)
        else:
            target_dir = self._download_dir
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return DownloadResult(success=False, error_message="Download destination is unavailable.")
        try:
            if not target_dir.resolve().is_relative_to(self._download_dir.resolve()):
                return DownloadResult(success=False, error_message="Download destination is outside the configured folder.")
        except OSError:
            return DownloadResult(success=False, error_message="Download destination is unavailable.")
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
            except requests.ConnectionError:
                last_error = f"Connection error (attempt {attempt})"
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
            except requests.RequestException as exc:
                last_error = f"Request failed ({type(exc).__name__}, attempt {attempt})"
                logger.warning(last_error)
            except DownloadError as exc:
                return DownloadResult(success=False, error_message=str(exc))
            except OSError:
                return DownloadResult(success=False, error_message="Download could not be written to the configured folder.")

            # Exponential backoff
            if attempt < self._max_retries:
                import time
                wait = min(30.0, self._backoff_factor ** attempt)
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
        resp = self._session.get(
            url,
            stream=True,
            timeout=self._timeout,
            allow_redirects=False,
        )
        tmp_path: Path | None = None
        try:
            if getattr(resp, "is_redirect", False):
                raise DownloadError("Redirected image URLs are not accepted; use the direct HTTPS URL.")
            resp.raise_for_status()
            try:
                content_length = int(resp.headers.get("content-length", 0))
            except (TypeError, ValueError) as exc:
                raise DownloadError("Invalid content length.") from exc
            if content_length < 0 or content_length > self._max_size_bytes:
                raise DownloadError("Image exceeds the configured maximum size.")

            content_type = resp.headers.get("content-type", "").split(";", 1)[0].lower()
            if not content_type.startswith("image/"):
                raise DownloadError("Response is not an image.")

            hasher = hashlib.sha256()
            downloaded = 0
            temp_root = self._temp_dir
            if self._temp_dir.stat().st_dev != target_path.parent.stat().st_dev:
                temp_root = target_path.parent
            with tempfile.NamedTemporaryFile(
                dir=str(temp_root), delete=False, suffix=".part"
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
                for chunk in resp.iter_content(chunk_size=8192):
                    if cancelled and cancelled():
                        return DownloadResult(success=False, error_message="Download cancelled.")
                    if not chunk:
                        continue
                    tmp_file.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    if downloaded > self._max_size_bytes:
                        raise DownloadError("Image exceeds the configured maximum size.")
                    if progress_callback:
                        progress_callback(downloaded, content_length or downloaded)

            if downloaded == 0:
                raise DownloadError("Downloaded image is empty.")
            try:
                with Image.open(tmp_path) as image:
                    if image.format and image.format.lower() not in {"jpeg", "png", "webp"}:
                        raise DownloadError("Downloaded image format is not supported.")
                    try:
                        validate_image_dimensions(image.size)
                    except ImageDimensionLimitError as exc:
                        raise DownloadError(str(exc)) from exc
                    image.verify()
            except DownloadError:
                raise
            except Exception as exc:
                raise DownloadError("Downloaded file is not a valid image.") from exc

            try:
                # link() fails if the target appears concurrently; never overwrite it.
                os.link(tmp_path, target_path)
                tmp_path.unlink()
                tmp_path = None
            except FileExistsError as exc:
                raise DownloadError("A file with this name already exists.") from exc
            except OSError as exc:
                raise DownloadError("Failed to save downloaded image.") from exc
        finally:
            close = getattr(resp, "close", None)
            if callable(close):
                close()
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        sha256 = hasher.hexdigest()
        logger.info("Downloaded %s (%d bytes, sha256=%s)", target_path.name, downloaded, sha256[:16])

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
