"""Safe CSV export of attribution fields already stored in the local library."""

from __future__ import annotations

import csv
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.database.models import Wallpaper


@dataclass(frozen=True)
class AttributionExportReport:
    destination: Path
    rows_exported: int
    rows_with_incomplete_attribution: int


_FIELDS = (
    "title", "creator", "source", "source_url", "license", "license_url",
    "filename", "library_path", "width", "height", "exported_at",
)


def _spreadsheet_safe(value: object) -> str:
    text = "" if value is None else str(value)
    probe = text.lstrip(" \t\r\n\x00")
    if probe.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def export_attributions(
    wallpapers: Iterable[Wallpaper], destination: Path, *, overwrite: bool = False
) -> AttributionExportReport:
    """Write a UTF-8 CSV atomically; source metadata is never inferred or fetched."""
    destination = Path(destination)
    if destination.suffix.lower() != ".csv":
        raise ValueError("Attribution export destination must be a .csv file.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError("The selected export file already exists.")

    records = list(wallpapers)
    temporary_path: Path | None = None
    incomplete = 0
    exported_at = datetime.now(UTC).isoformat()
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=destination.parent,
            prefix=".attribution-", suffix=".tmp", delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for wallpaper in records:
                if wallpaper.source and wallpaper.source != "local_import" and any(
                    not value for value in (wallpaper.author, wallpaper.source_url, wallpaper.license, wallpaper.license_url)
                ):
                    incomplete += 1
                writer.writerow({
                    "title": _spreadsheet_safe(wallpaper.title),
                    "creator": _spreadsheet_safe(wallpaper.author),
                    "source": _spreadsheet_safe(wallpaper.source),
                    "source_url": _spreadsheet_safe(wallpaper.source_url),
                    "license": _spreadsheet_safe(wallpaper.license),
                    "license_url": _spreadsheet_safe(wallpaper.license_url),
                    "filename": _spreadsheet_safe(wallpaper.filename),
                    "library_path": _spreadsheet_safe(wallpaper.path),
                    "width": wallpaper.width,
                    "height": wallpaper.height,
                    "exported_at": exported_at,
                })
            stream.flush()
            os.fsync(stream.fileno())

        if overwrite:
            os.replace(temporary_path, destination)
        else:
            # Hard-link creation is exclusive and prevents a concurrent overwrite race.
            os.link(temporary_path, destination)
            temporary_path.unlink()
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return AttributionExportReport(destination, len(records), incomplete)
