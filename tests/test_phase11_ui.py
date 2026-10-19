"""Isolated Windows Qt navigation and screenshot QA for Phase 11."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.config import Config
from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.database.history_repository import HistoryRepository
from app.database.models import Wallpaper, WallpaperHistory
from app.database.view_repository import ViewRepository
from app.database.wallpaper_repository import WallpaperRepository
from app.services.duplicate_scan_service import (
    CleanupPreview,
    CleanupPreviewEntry,
    DuplicateScanService,
)
from app.services.import_service import ImportService
from app.ui.components.cleanup_confirmation_dialog import CleanupConfirmationDialog
from app.ui.components.comparison_dialog import ComparisonDialog
from app.ui.components.detail_dialog import DetailDialog
from app.ui.components.import_dialog import ImportProgressDialog
from app.ui.main_window import MainWindow


def _seed_library(root: Path, db: Database) -> list[Wallpaper]:
    library = root / "Library"
    library.mkdir(parents=True)
    image_path = library / "01-synthetic.png"
    image = Image.new("RGB", (320, 180), (40, 80, 120))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 35, 280, 145), fill=(80, 150, 110))
    image.save(image_path)
    duplicate_path = library / "02-exact-copy.png"
    shutil.copyfile(image_path, duplicate_path)
    other_path = library / "03-synthetic.png"
    Image.new("RGB", (320, 180), (140, 70, 50)).save(other_path)

    repository = WallpaperRepository(db)
    records: list[Wallpaper] = []
    for index, path in enumerate((image_path, duplicate_path, other_path), start=1):
        wallpaper = Wallpaper(
            filename=path.name,
            path=str(path),
            title=f"Synthetic sample {index}",
            category="Nature",
            width=320,
            height=180,
            aspect_ratio="16:9",
            resolution_class="SD",
            file_size=path.stat().st_size,
            source="wikimedia",
            source_url="https://commons.wikimedia.org/wiki/File:QA_sample.png",
            author="Synthetic QA fixture",
            license="CC0",
            favorite=index < 3,
        )
        wallpaper.id = repository.add(wallpaper)
        records.append(wallpaper)

    HistoryRepository(db).add(
        WallpaperHistory(
            wallpaper_id=records[0].id or 0,
            set_at=datetime.now(UTC).isoformat(),
            monitor="Synthetic QA",
            source="manual",
            success=True,
        )
    )
    ViewRepository(db).record_view(records[1].id or 0)
    return records


def test_main_window_pages_and_dialogs_render_at_target_sizes(
    qapp, tmp_path: Path
) -> None:
    data_root = tmp_path / "isolated-app-data"
    config = Config(data_root)
    config.set("library_path", str(data_root / "Library"))
    config.set("download_folder", str(data_root / "Library"))
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    database = Database(config.database_path)
    database.connect()
    CategoryRepository(database).seed_defaults()
    records = _seed_library(data_root, database)
    window = MainWindow(config, database)
    window.show()
    qapp.processEvents()
    QTest.qWait(100)

    duplicates = window._views["duplicates"]
    report = DuplicateScanService(records, threshold=0).scan()
    assert report.completed and report.exact_groups
    duplicates._on_scan_report(report)
    qapp.processEvents()

    capture_dir = tmp_path / "phase11-ui-captures"
    capture_dir.mkdir()
    sizes = ((1280, 800), (1024, 768), (800, 600), (1440, 900))
    available = qapp.primaryScreen().availableGeometry()
    page_keys = ("dashboard", "library", "favorites", "history", "duplicates", "settings")

    actual_sizes = []
    for requested_width, requested_height in sizes:
        window.resize(
            min(requested_width, available.width()),
            min(requested_height, available.height()),
        )
        qapp.processEvents()
        width, height = window.width(), window.height()
        actual_sizes.append((requested_width, requested_height, width, height))
        assert width <= available.width()
        assert height <= available.height()
        library = window._views["library"]
        assert library._grid_columns >= 1
        assert library._search_bar.height() in (52, 92, 132)
        if requested_width == 800:
            assert library._scroll.horizontalScrollBar().maximum() == 0
            favorites = window._views["favorites"]
            assert favorites._scroll.horizontalScrollBar().maximum() == 0
        for key in page_keys:
            button = window._sidebar._buttons[key]
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            qapp.processEvents()
            QTest.qWait(100)
            if key == "favorites":
                QTest.qWait(400)
            assert window._stack.currentWidget() is window._views[key]
            name = f"{width}x{height}-{key}"
            assert window.grab().save(str(capture_dir / f"{name}.png"))
        settings = window._views["settings"]
        settings.tabs.setCurrentIndex(4)
        qapp.processEvents()
        assert window.grab().save(
            str(capture_dir / f"{width}x{height}-settings-rotation.png")
        )
        settings.tabs.setCurrentIndex(0)

    # Keyboard activation follows the visible sidebar navigation control path.
    settings_button = window._sidebar._buttons["settings"]
    settings_button.setFocus()
    QTest.keyClick(settings_button, Qt.Key.Key_Space)
    qapp.processEvents()
    assert window._stack.currentWidget() is window._views["settings"]
    rotation_view = window._views["settings"].tabs.widget(4)
    assert rotation_view._enabled.accessibleName() == "Enable automatic rotation"
    assert rotation_view._apply_button.accessibleName() == "Save or start automatic rotation"

    report = duplicates._report
    assert report is not None and report.completed and report.exact_groups
    exact_group = report.exact_groups[0]
    preview = CleanupPreview(
        entries=(
            CleanupPreviewEntry(
                exact_group.group_id,
                exact_group.members[0],
                (exact_group.members[1],),
            ),
        ),
        files_selected=1,
        estimated_bytes=exact_group.members[1].size_bytes,
    )

    window.resize(800, 600)
    qapp.processEvents()
    detail = DetailDialog(records[0], parent=window)
    detail.show()
    qapp.processEvents()
    detail_size = (detail.width(), detail.height())
    assert detail_size[0] <= window.width()
    assert detail_size[1] <= window.height()
    assert detail.grab().save(str(capture_dir / "dialog-detail.png"))
    detail.close()

    import_dialog = ImportProgressDialog(
        data_root / "synthetic-import",
        ImportService(database, cache_dir=config.cache_dir, config=config),
        category="Nature",
        recursive=True,
        parent=window,
    )
    import_dialog.show()
    qapp.processEvents()
    assert import_dialog.grab().save(str(capture_dir / "dialog-import-progress.png"))
    import_dialog.close()

    comparison = ComparisonDialog(exact_group.members, parent=window)
    comparison.show()
    qapp.processEvents()
    assert comparison.grab().save(str(capture_dir / "dialog-comparison.png"))
    comparison.close()

    confirmation = CleanupConfirmationDialog(preview, parent=window)
    confirmation.show()
    qapp.processEvents()
    assert confirmation.grab().save(str(capture_dir / "dialog-cleanup-confirmation.png"))
    confirmation.close()

    print(f"Requested/actual window sizes: {actual_sizes}")
    print(
        f"Phase 11 UI captures: {capture_dir}; detail dialog size at 800x600 parent: "
        f"{detail_size[0]}x{detail_size[1]}"
    )
    window.close()
    qapp.processEvents()
    database.close()
