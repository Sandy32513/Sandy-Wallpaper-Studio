"""Service and offscreen UI tests for category management."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Generator
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox, QLineEdit, QListWidget, QPushButton

from app.config import Config
from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.database.models import Category, Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.services.category_service import CategoryService, CategoryServiceError
from app.ui.categories_view import CategoriesView
from app.ui.main_window import MainWindow


@pytest.fixture
def category_setup(tmp_path: Path) -> Generator[tuple[Database, Config, CategoryRepository, CategoryService], None, None]:
    data_root = tmp_path / "profile"
    data_root.mkdir()
    database = Database(data_root / "wallpapers.db")
    database.connect()
    repository = CategoryRepository(database)
    repository.seed_defaults()
    config = Config(data_root)
    config.load()
    service = CategoryService(repository, config)
    yield database, config, repository, service
    database.close()


def _add_wallpaper(db: Database, name: str, category: str, path: Path | None = None) -> Wallpaper:
    if path is None:
        path = Path("synthetic") / f"{name}.png"
    wallpaper = Wallpaper(
        filename=path.name,
        path=str(path),
        title=name,
        category=category,
        width=32,
        height=24,
        file_size=10,
        sha256=f"{name:0<64}"[:64],
    )
    wallpaper.id = WallpaperRepository(db).add(wallpaper)
    return wallpaper


def _custom_id(repository: CategoryRepository, name: str) -> int:
    category = repository.get_by_name(name)
    assert category is not None and category.id is not None
    return category.id


def test_category_add_trim_casefold_duplicates_and_grouped_counts(category_setup) -> None:
    database, _config, repository, service = category_setup
    category = service.add("  Star Trails  ")
    assert category.name == "Star Trails"
    with pytest.raises(CategoryServiceError, match="Enter a category name"):
        service.add(" \t ")
    with pytest.raises(CategoryServiceError, match="already exists"):
        service.add("star trails")

    _add_wallpaper(database, "one", "Star Trails")
    _add_wallpaper(database, "two", "Star Trails")
    statements: list[str] = []
    database.connection.set_trace_callback(statements.append)
    summaries = service.list_categories()
    database.connection.set_trace_callback(None)
    match = next(summary for summary in summaries if summary.category.name == "Star Trails")
    assert match.wallpaper_count == 2
    count_queries = [statement for statement in statements if "FROM categories AS c" in statement]
    assert len(count_queries) == 1
    assert "GROUP BY c.id" in count_queries[0]
    assert summaries == sorted(
        summaries, key=lambda summary: (summary.category.sort_order, summary.category.name)
    )


def test_category_rename_updates_labels_and_rotation_and_compensates_save_failure(
    category_setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, config, repository, service = category_setup
    category = service.add("Night Sky")
    wallpaper = _add_wallpaper(database, "stars", "Night Sky")
    config.set("rotation_categories", ["Night Sky", "Nature"])

    renamed = service.rename(category.id or 0, "  Celestial  ")
    assert renamed.name == "Celestial"
    assert WallpaperRepository(database).get_by_id(wallpaper.id or 0).category == "Celestial"
    assert config.get("rotation_categories") == ["Celestial", "Nature"]

    config.set("rotation_categories", ["Celestial"])

    def fail_save(_values: dict[str, object]) -> None:
        raise OSError("synthetic settings disk failure")

    monkeypatch.setattr(config, "apply_settings", fail_save)
    with pytest.raises(CategoryServiceError, match="were restored to \"Celestial\".*unchanged"):
        service.rename(category.id or 0, "Orbit")
    assert repository.get_by_id(category.id or 0).name == "Celestial"
    assert WallpaperRepository(database).get_by_id(wallpaper.id or 0).category == "Celestial"
    assert config.get("rotation_categories") == ["Celestial"]

    def fail_database_rename(_category_id: int, _name: str) -> bool:
        raise OSError("synthetic database failure")

    monkeypatch.setattr(repository, "rename", fail_database_rename)
    with pytest.raises(CategoryServiceError, match="was not renamed.*remain unchanged"):
        service.rename(category.id or 0, "Orbit")
    assert repository.get_by_id(category.id or 0).name == "Celestial"
    assert config.get("rotation_categories") == ["Celestial"]


def test_category_rename_collision_rolls_back_category_and_wallpaper_labels(category_setup) -> None:
    database, _config, repository, _service = category_setup
    source = repository.add(Category(name="Source", is_default=False))
    repository.add(Category(name="Target", is_default=False))
    wallpaper = _add_wallpaper(database, "source-image", "Source")
    with pytest.raises(sqlite3.IntegrityError):
        repository.rename(source, "Target")
    assert repository.get_by_id(source).name == "Source"
    assert WallpaperRepository(database).get_by_id(wallpaper.id or 0).category == "Source"


def test_category_delete_keeps_wallpaper_and_file_and_cleans_rotation(category_setup, tmp_path: Path) -> None:
    database, config, repository, service = category_setup
    category = service.add("Storms")
    image_path = tmp_path / "storm.png"
    Image.new("RGB", (24, 16), (40, 60, 90)).save(image_path)
    wallpaper = _add_wallpaper(database, "storm", "Storms", image_path)
    config.set("rotation_categories", ["Storms", "Nature"])

    deletion = service.delete(category.id or 0)
    assert (deletion.name, deletion.wallpaper_count) == ("Storms", 1)
    assert config.get("rotation_categories") == ["Nature"]
    assert repository.get_by_id(category.id or 0) is None
    stored = WallpaperRepository(database).get_by_id(wallpaper.id or 0)
    assert stored is not None and stored.category == "Storms"
    assert image_path.read_bytes().startswith(b"\x89PNG")

    default = repository.get_by_name("Nature")
    assert default is not None and default.id is not None
    with pytest.raises(CategoryServiceError, match="Built-in categories"):
        service.delete(default.id)
    with pytest.raises(CategoryServiceError, match="Built-in categories"):
        service.rename(default.id, "Outdoors")


def test_category_reorder_and_open_in_library(category_setup) -> None:
    _database, _config, repository, service = category_setup
    first = service.add("A custom")
    second = service.add("B custom")
    ids = [category.id for category in repository.get_all()]
    ids.remove(second.id)
    ids.insert(ids.index(first.id), second.id)
    service.reorder(ids)
    persisted_ids = [category.id for category in repository.get_all()]
    assert persisted_ids == ids
    assert service.open_in_library(first.id or 0) == "A custom"
    with pytest.raises(CategoryServiceError, match="no longer exists"):
        service.open_in_library(999999)


def test_categories_view_crud_cancel_error_and_accessibility(qapp, category_setup, monkeypatch) -> None:
    database, _config, repository, service = category_setup
    confirmations: list[tuple[str, int]] = []
    view = CategoriesView(
        service,
        confirm_delete=lambda name, count: confirmations.append((name, count)) or False,
    )
    view.show()
    qapp.processEvents()
    assert view._empty_label.isVisible()
    assert view.add_category("  Comets ")
    category_id = _custom_id(repository, "Comets")
    assert not view._empty_label.isVisible()
    assert view.rename_category(category_id, "Meteor Showers")
    _add_wallpaper(database, "meteor", "Meteor Showers")
    view.refresh()
    assert not view.delete_category(category_id)
    assert confirmations == [("Meteor Showers", 1)]
    assert repository.get_by_id(category_id) is not None
    assert "cancelled" in view._status_label.text().lower()

    category_row = next(
        view._list.itemWidget(view._list.item(index))
        for index in range(view._list.count())
        if view._list.item(index).data(Qt.ItemDataRole.UserRole) == category_id
    )
    assert category_row.rename_button.isEnabled()
    assert category_row.delete_button.isEnabled()
    nature_item = next(
        view._list.item(index)
        for index in range(view._list.count())
        if view._list.item(index).text() == "Nature"
    )
    nature_row = view._list.itemWidget(nature_item)
    assert not nature_row.rename_button.isEnabled()
    assert not nature_row.delete_button.isEnabled()
    assert "Built-in categories" in nature_row.rename_button.toolTip()

    controls = (
        view.findChildren(QPushButton)
        + view.findChildren(QLineEdit)
        + view.findChildren(QListWidget)
    )
    assert controls and all(control.accessibleName() for control in controls)
    view._name_input.setFocus()
    QTest.keyClick(view._name_input, Qt.Key.Key_Tab)
    assert view._add_button.hasFocus()
    QTest.keyClick(view._add_button, Qt.Key.Key_Tab)
    assert nature_row.open_button.hasFocus()
    QTest.keyClick(view._name_input, Qt.Key.Key_Return)
    assert repository.get_by_name("Meteor Showers") is not None

    assert view.add_category("Solar Winds")
    category_row = next(
        view._list.itemWidget(view._list.item(index))
        for index in range(view._list.count())
        if view._list.item(index).data(Qt.ItemDataRole.UserRole) == category_id
    )
    category_item = next(
        view._list.item(index)
        for index in range(view._list.count())
        if view._list.item(index).data(Qt.ItemDataRole.UserRole) == category_id
    )
    view._list.scrollToItem(category_item)
    qapp.processEvents()
    category_row.down_button.setFocus()
    QTest.keyClick(category_row.down_button, Qt.Key.Key_Space)
    assert repository.get_all()[-1].name == "Meteor Showers"

    monkeypatch.setattr(service, "list_categories", lambda: (_ for _ in ()).throw(OSError("database unavailable")))
    view.refresh()
    assert view._error_label.isVisible()
    assert "database unavailable" in view._error_label.text()
    assert view._retry_button.isVisible()


def test_category_delete_confirmation_explains_preservation_and_defaults_to_cancel(
    qapp, monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def inspect_dialog(dialog: QMessageBox) -> int:
        observed["text"] = dialog.text()
        observed["default"] = dialog.standardButton(dialog.defaultButton())
        return int(QMessageBox.StandardButton.Cancel)

    monkeypatch.setattr(QMessageBox, "exec", inspect_dialog)
    assert not CategoriesView._show_delete_confirmation("Clouds", 2)
    assert "2 wallpapers" in str(observed["text"])
    assert "keep the text label" in str(observed["text"])
    assert "become uncategorized" in str(observed["text"])
    assert "No wallpaper or file will be deleted" in str(observed["text"])
    assert observed["default"] == QMessageBox.StandardButton.Cancel


def test_categories_view_layout_captures_and_library_wiring(qapp, tmp_path: Path) -> None:
    system_font = Path(r"C:\Windows\Fonts\segoeui.ttf")
    if system_font.is_file() and not QFontDatabase.families():
        QFontDatabase.addApplicationFont(str(system_font))

    data_root = tmp_path / "main-window-data"
    data_root.mkdir()
    config = Config(data_root)
    config.set("library_path", str(data_root / "Library"))
    config.set("download_folder", str(data_root / "Library"))
    database = Database(config.database_path)
    database.connect()
    categories = CategoryRepository(database)
    categories.seed_defaults()
    custom = categories.add(Category(name="Captured Category", is_default=False))
    _add_wallpaper(database, "captured", "Captured Category")
    window = MainWindow(config, database)
    window.show()
    qapp.processEvents()
    view = window._views["categories"]
    assert isinstance(view, CategoriesView)
    window._navigate_to("categories")
    qapp.processEvents()

    capture_root = os.environ.get("SWS_QA_CAPTURE_DIR")
    capture_dir = Path(capture_root) if capture_root else tmp_path / "captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    for state in ("populated", "empty"):
        if state == "empty":
            service = window._category_service
            service.delete(custom)
            view.refresh()
            assert view._empty_label.isVisible()
        else:
            assert not view._empty_label.isVisible()
        for requested_width, requested_height in ((1280, 800), (1024, 768), (800, 600), (1440, 900)):
            actual_request = (
                (1024, 680)
                if (requested_width, requested_height) == (800, 600)
                else (requested_width, requested_height)
            )
            window.resize(*actual_request)
            qapp.processEvents()
            assert view._list.horizontalScrollBar().maximum() == 0
            assert view._scroll.horizontalScrollBar().maximum() == 0
            for index in range(view._list.count()):
                row = view._list.itemWidget(view._list.item(index))
                if row is not None:
                    assert row.width() <= view._list.viewport().width()
                    for button in row.findChildren(QPushButton):
                        assert button.geometry().right() <= row.width()
            actual_width, actual_height = window.width(), window.height()
            capture_path = capture_dir / f"categories-{state}-{requested_width}x{requested_height}-actual-{actual_width}x{actual_height}.png"
            assert window.grab().save(str(capture_path))
    window._navigate_to("categories")
    view.open_category(categories.get_by_name("Nature").id)
    qapp.processEvents()
    library = window._views["library"]
    assert library._search_bar.current_filters["category"] == "Nature"
    assert window._stack.currentWidget() is library
    window.close()
    qapp.processEvents()


