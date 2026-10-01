"""
Sandy Wallpaper Studio — Phase 1 Tests
=========================================
Tests for database, models, migrations, and repositories.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.constants import DEFAULT_CATEGORIES
from app.database.database import Database
from app.database.models import Category, Wallpaper, DownloadRecord, WallpaperHistory
from app.database.migrations import get_current_version, run_migrations
from app.database.wallpaper_repository import WallpaperRepository
from app.database.category_repository import CategoryRepository


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a fresh in-memory-like database for each test."""
    db_path = tmp_path / "test_wallpapers.db"
    database = Database(db_path)
    database.connect()
    yield database
    database.close()


@pytest.fixture
def wallpaper_repo(db: Database) -> WallpaperRepository:
    return WallpaperRepository(db)


@pytest.fixture
def category_repo(db: Database) -> CategoryRepository:
    return CategoryRepository(db)


def _make_wallpaper(**overrides) -> Wallpaper:
    """Helper to create a test wallpaper with sensible defaults."""
    defaults = {
        "filename": "test_wallpaper.jpg",
        "path": "/library/Nature/test_wallpaper.jpg",
        "title": "Mountain Sunset",
        "description": "A beautiful mountain sunset",
        "category": "Nature",
        "tags": "mountain,sunset,nature",
        "width": 3840,
        "height": 2160,
        "aspect_ratio": "16:9",
        "resolution_class": "4K",
        "file_size": 5_242_880,  # 5 MB
        "sha256": "abc123def456" * 5,
        "phash": "fedcba987654",
        "source": "wikimedia",
        "source_url": "https://commons.wikimedia.org/wiki/File:Test.jpg",
        "author": "Test Author",
        "license": "CC-BY-SA-4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "download_date": datetime.now(timezone.utc).isoformat(),
        "favorite": False,
        "last_used": None,
        "usage_count": 0,
    }
    defaults.update(overrides)
    return Wallpaper(**defaults)


# ============================================================
# Model Tests
# ============================================================
class TestWallpaperModel:
    def test_resolution_label(self) -> None:
        w = Wallpaper(width=3840, height=2160)
        assert w.resolution_label == "3840 × 2160"

    def test_file_size_mb(self) -> None:
        w = Wallpaper(file_size=5_242_880)
        assert w.file_size_mb == 5.0

    def test_file_size_mb_zero(self) -> None:
        w = Wallpaper()
        assert w.file_size_mb == 0.0

    def test_tag_list(self) -> None:
        w = Wallpaper(tags="mountain, sunset, nature")
        assert w.tag_list == ["mountain", "sunset", "nature"]

    def test_tag_list_empty(self) -> None:
        w = Wallpaper(tags="")
        assert w.tag_list == []

    def test_to_dict(self) -> None:
        w = _make_wallpaper()
        d = w.to_dict()
        assert d["filename"] == "test_wallpaper.jpg"
        assert d["width"] == 3840
        assert d["favorite"] == 0  # bool -> int for SQLite

    def test_to_dict_favorite_true(self) -> None:
        w = _make_wallpaper(favorite=True)
        d = w.to_dict()
        assert d["favorite"] == 1


class TestCategoryModel:
    def test_to_dict(self) -> None:
        c = Category(name="Nature", is_default=True, icon="🏔️", sort_order=0)
        d = c.to_dict()
        assert d["name"] == "Nature"
        assert d["is_default"] == 1

    def test_custom_category(self) -> None:
        c = Category(name="My Collection", is_default=False)
        d = c.to_dict()
        assert d["is_default"] == 0


class TestDownloadRecordModel:
    def test_to_dict(self) -> None:
        r = DownloadRecord(source="wikimedia", status="completed")
        d = r.to_dict()
        assert d["source"] == "wikimedia"
        assert d["status"] == "completed"


# ============================================================
# Migration Tests
# ============================================================
class TestMigrations:
    def test_initial_migration(self, db: Database) -> None:
        """Schema version should be 1 after initial migration."""
        cursor = db.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        assert row[0] == 1

    def test_tables_created(self, db: Database) -> None:
        """All expected tables should exist."""
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        expected = {"wallpapers", "categories", "download_records",
                    "wallpaper_history", "schema_version"}
        assert expected.issubset(tables)

    def test_indexes_created(self, db: Database) -> None:
        """Key indexes should exist."""
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = {row["name"] for row in cursor.fetchall()}
        assert "idx_wallpapers_sha256" in indexes
        assert "idx_wallpapers_phash" in indexes
        assert "idx_wallpapers_category" in indexes
        assert "idx_wallpapers_resolution_class" in indexes
        assert "idx_wallpapers_favorite" in indexes
        assert "idx_wallpapers_download_date" in indexes

    def test_idempotent_migrations(self, db: Database) -> None:
        """Running migrations again should not fail or change version."""
        v1 = get_current_version(db.connection.cursor())
        run_migrations(db.connection)
        v2 = get_current_version(db.connection.cursor())
        assert v1 == v2

    def test_wal_mode(self, db: Database) -> None:
        """WAL mode should be enabled."""
        cursor = db.execute("PRAGMA journal_mode")
        row = cursor.fetchone()
        assert row[0] == "wal"

    def test_foreign_keys_enabled(self, db: Database) -> None:
        cursor = db.execute("PRAGMA foreign_keys")
        row = cursor.fetchone()
        assert row[0] == 1


# ============================================================
# Database Manager Tests
# ============================================================
class TestDatabase:
    def test_context_manager(self, tmp_path: Path) -> None:
        db_path = tmp_path / "ctx_test.db"
        with Database(db_path) as database:
            cursor = database.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1

    def test_double_connect_warning(self, db: Database) -> None:
        """Connecting again should warn, not crash."""
        db.connect()  # Should just log a warning

    def test_repr(self, db: Database) -> None:
        r = repr(db)
        assert "connected" in r


# ============================================================
# Wallpaper Repository Tests
# ============================================================
class TestWallpaperRepository:
    def test_add_and_get(self, wallpaper_repo: WallpaperRepository) -> None:
        w = _make_wallpaper()
        new_id = wallpaper_repo.add(w)
        assert new_id is not None and new_id > 0

        fetched = wallpaper_repo.get_by_id(new_id)
        assert fetched is not None
        assert fetched.filename == "test_wallpaper.jpg"
        assert fetched.width == 3840
        assert fetched.resolution_class == "4K"

    def test_get_by_sha256(self, wallpaper_repo: WallpaperRepository) -> None:
        w = _make_wallpaper(sha256="unique_hash_12345")
        wallpaper_repo.add(w)
        found = wallpaper_repo.get_by_sha256("unique_hash_12345")
        assert found is not None
        assert found.sha256 == "unique_hash_12345"

    def test_get_by_sha256_not_found(self, wallpaper_repo: WallpaperRepository) -> None:
        assert wallpaper_repo.get_by_sha256("nonexistent") is None

    def test_get_by_path(self, wallpaper_repo: WallpaperRepository) -> None:
        w = _make_wallpaper(path="/test/path.jpg")
        wallpaper_repo.add(w)
        found = wallpaper_repo.get_by_path("/test/path.jpg")
        assert found is not None

    def test_add_many(self, wallpaper_repo: WallpaperRepository) -> None:
        wallpapers = [
            _make_wallpaper(filename=f"wp_{i}.jpg", sha256=f"hash_{i}", path=f"/p/{i}.jpg")
            for i in range(5)
        ]
        count = wallpaper_repo.add_many(wallpapers)
        assert count == 5
        assert wallpaper_repo.count() == 5

    def test_get_all_pagination(self, wallpaper_repo: WallpaperRepository) -> None:
        for i in range(10):
            wallpaper_repo.add(
                _make_wallpaper(filename=f"wp_{i}.jpg", sha256=f"h_{i}", path=f"/p/{i}.jpg")
            )
        page1 = wallpaper_repo.get_all(limit=5, offset=0)
        page2 = wallpaper_repo.get_all(limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5

    def test_get_by_category(self, wallpaper_repo: WallpaperRepository) -> None:
        wallpaper_repo.add(_make_wallpaper(category="Space", sha256="s1", path="/s/1.jpg"))
        wallpaper_repo.add(_make_wallpaper(category="Nature", sha256="n1", path="/n/1.jpg"))
        space = wallpaper_repo.get_by_category("Space")
        assert len(space) == 1
        assert space[0].category == "Space"

    def test_get_by_resolution_class(self, wallpaper_repo: WallpaperRepository) -> None:
        wallpaper_repo.add(_make_wallpaper(resolution_class="8K", sha256="r1", path="/r/1.jpg"))
        wallpaper_repo.add(_make_wallpaper(resolution_class="4K", sha256="r2", path="/r/2.jpg"))
        result = wallpaper_repo.get_by_resolution_class("8K")
        assert len(result) == 1

    def test_favorites(self, wallpaper_repo: WallpaperRepository) -> None:
        wid = wallpaper_repo.add(_make_wallpaper(sha256="fav1", path="/fav/1.jpg"))
        wallpaper_repo.set_favorite(wid, True)
        favs = wallpaper_repo.get_favorites()
        assert len(favs) == 1
        assert favs[0].favorite is True

    def test_set_favorite_toggle(self, wallpaper_repo: WallpaperRepository) -> None:
        wid = wallpaper_repo.add(_make_wallpaper(sha256="ft1", path="/ft/1.jpg"))
        wallpaper_repo.set_favorite(wid, True)
        wallpaper_repo.set_favorite(wid, False)
        w = wallpaper_repo.get_by_id(wid)
        assert w is not None and w.favorite is False

    def test_record_usage(self, wallpaper_repo: WallpaperRepository) -> None:
        wid = wallpaper_repo.add(_make_wallpaper(sha256="u1", path="/u/1.jpg"))
        ts = datetime.now(timezone.utc).isoformat()
        wallpaper_repo.record_usage(wid, ts)
        w = wallpaper_repo.get_by_id(wid)
        assert w is not None
        assert w.usage_count == 1
        assert w.last_used == ts

    def test_get_recently_used(self, wallpaper_repo: WallpaperRepository) -> None:
        wid = wallpaper_repo.add(_make_wallpaper(sha256="ru1", path="/ru/1.jpg"))
        wallpaper_repo.record_usage(wid, datetime.now(timezone.utc).isoformat())
        recent = wallpaper_repo.get_recently_used()
        assert len(recent) == 1

    def test_get_never_used(self, wallpaper_repo: WallpaperRepository) -> None:
        wallpaper_repo.add(_make_wallpaper(sha256="nu1", path="/nu/1.jpg"))
        never = wallpaper_repo.get_never_used()
        assert len(never) == 1

    def test_search_by_query(self, wallpaper_repo: WallpaperRepository) -> None:
        wallpaper_repo.add(_make_wallpaper(title="Alpine Sunrise", sha256="s1", path="/s/1.jpg"))
        wallpaper_repo.add(_make_wallpaper(title="Ocean Wave", sha256="s2", path="/s/2.jpg"))
        results = wallpaper_repo.search("Alpine")
        assert len(results) == 1
        assert results[0].title == "Alpine Sunrise"

    def test_search_with_filters(self, wallpaper_repo: WallpaperRepository) -> None:
        wallpaper_repo.add(
            _make_wallpaper(title="Space Nebula", category="Space",
                           resolution_class="8K", width=7680, height=4320,
                           sha256="sf1", path="/sf/1.jpg")
        )
        wallpaper_repo.add(
            _make_wallpaper(title="Space Station", category="Space",
                           resolution_class="4K", width=3840, height=2160,
                           sha256="sf2", path="/sf/2.jpg")
        )
        results = wallpaper_repo.search(
            query="Space",
            resolution_class="8K",
            min_width=5000,
        )
        assert len(results) == 1
        assert results[0].title == "Space Nebula"

    def test_search_favorites_only(self, wallpaper_repo: WallpaperRepository) -> None:
        wid = wallpaper_repo.add(_make_wallpaper(sha256="sfo1", path="/sfo/1.jpg"))
        wallpaper_repo.add(_make_wallpaper(sha256="sfo2", path="/sfo/2.jpg"))
        wallpaper_repo.set_favorite(wid, True)
        results = wallpaper_repo.search("", favorites_only=True)
        assert len(results) == 1

    def test_count(self, wallpaper_repo: WallpaperRepository) -> None:
        assert wallpaper_repo.count() == 0
        wallpaper_repo.add(_make_wallpaper(sha256="c1", path="/c/1.jpg"))
        assert wallpaper_repo.count() == 1

    def test_count_by_category(self, wallpaper_repo: WallpaperRepository) -> None:
        wallpaper_repo.add(_make_wallpaper(category="Nature", sha256="cc1", path="/cc/1.jpg"))
        wallpaper_repo.add(_make_wallpaper(category="Space", sha256="cc2", path="/cc/2.jpg"))
        assert wallpaper_repo.count(category="Nature") == 1

    def test_update(self, wallpaper_repo: WallpaperRepository) -> None:
        wid = wallpaper_repo.add(_make_wallpaper(sha256="up1", path="/up/1.jpg"))
        w = wallpaper_repo.get_by_id(wid)
        assert w is not None
        w.title = "Updated Title"
        assert wallpaper_repo.update(w)
        updated = wallpaper_repo.get_by_id(wid)
        assert updated is not None and updated.title == "Updated Title"

    def test_update_category(self, wallpaper_repo: WallpaperRepository) -> None:
        wid = wallpaper_repo.add(_make_wallpaper(category="Nature", sha256="uc1", path="/uc/1.jpg"))
        wallpaper_repo.update_category(wid, "Space")
        w = wallpaper_repo.get_by_id(wid)
        assert w is not None and w.category == "Space"

    def test_delete(self, wallpaper_repo: WallpaperRepository) -> None:
        wid = wallpaper_repo.add(_make_wallpaper(sha256="d1", path="/d/1.jpg"))
        assert wallpaper_repo.delete(wid)
        assert wallpaper_repo.get_by_id(wid) is None

    def test_delete_nonexistent(self, wallpaper_repo: WallpaperRepository) -> None:
        assert wallpaper_repo.delete(99999) is False

    def test_get_all_phashes(self, wallpaper_repo: WallpaperRepository) -> None:
        wallpaper_repo.add(_make_wallpaper(phash="ph1", sha256="ap1", path="/ap/1.jpg"))
        wallpaper_repo.add(_make_wallpaper(phash="ph2", sha256="ap2", path="/ap/2.jpg"))
        wallpaper_repo.add(_make_wallpaper(phash="", sha256="ap3", path="/ap/3.jpg"))  # Empty phash
        phashes = wallpaper_repo.get_all_phashes()
        assert len(phashes) == 2

    def test_get_statistics(self, wallpaper_repo: WallpaperRepository) -> None:
        wallpaper_repo.add(_make_wallpaper(
            category="Nature", resolution_class="4K",
            file_size=1000, sha256="st1", path="/st/1.jpg"
        ))
        wallpaper_repo.add(_make_wallpaper(
            category="Space", resolution_class="8K",
            file_size=2000, favorite=True, sha256="st2", path="/st/2.jpg"
        ))
        stats = wallpaper_repo.get_statistics()
        assert stats["total"] == 2
        assert stats["favorites"] == 1
        assert stats["total_size_bytes"] == 3000
        assert stats["categories_used"] == 2
        assert "4K" in stats["by_resolution"]
        assert "8K" in stats["by_resolution"]

    def test_order_by_injection_prevention(self, wallpaper_repo: WallpaperRepository) -> None:
        """Invalid order_by should fall back to default."""
        wallpaper_repo.add(_make_wallpaper(sha256="oi1", path="/oi/1.jpg"))
        # This should not raise — it falls back to "download_date DESC"
        results = wallpaper_repo.get_all(order_by="DROP TABLE wallpapers")
        assert len(results) == 1


# ============================================================
# Category Repository Tests
# ============================================================
class TestCategoryRepository:
    def test_seed_defaults(self, category_repo: CategoryRepository) -> None:
        category_repo.seed_defaults()
        all_cats = category_repo.get_all()
        assert len(all_cats) == len(DEFAULT_CATEGORIES)

    def test_seed_defaults_idempotent(self, category_repo: CategoryRepository) -> None:
        category_repo.seed_defaults()
        category_repo.seed_defaults()
        assert category_repo.count() == len(DEFAULT_CATEGORIES)

    def test_add_custom_category(self, category_repo: CategoryRepository) -> None:
        cat = Category(name="My Custom", is_default=False, sort_order=100)
        new_id = category_repo.add(cat)
        assert new_id > 0
        fetched = category_repo.get_by_id(new_id)
        assert fetched is not None and fetched.name == "My Custom"
        assert fetched.is_default is False

    def test_get_by_name(self, category_repo: CategoryRepository) -> None:
        category_repo.seed_defaults()
        cat = category_repo.get_by_name("Nature")
        assert cat is not None
        assert cat.name == "Nature"

    def test_get_by_name_not_found(self, category_repo: CategoryRepository) -> None:
        assert category_repo.get_by_name("NonExistent") is None

    def test_get_defaults(self, category_repo: CategoryRepository) -> None:
        category_repo.seed_defaults()
        category_repo.add(Category(name="Custom1", is_default=False))
        defaults = category_repo.get_defaults()
        customs = category_repo.get_custom()
        assert len(defaults) == len(DEFAULT_CATEGORIES)
        assert len(customs) == 1

    def test_rename(self, category_repo: CategoryRepository) -> None:
        new_id = category_repo.add(Category(name="Old Name", is_default=False))
        assert category_repo.rename(new_id, "New Name")
        cat = category_repo.get_by_id(new_id)
        assert cat is not None and cat.name == "New Name"

    def test_update_sort_order(self, category_repo: CategoryRepository) -> None:
        new_id = category_repo.add(Category(name="SortTest", sort_order=0))
        category_repo.update_sort_order(new_id, 50)
        cat = category_repo.get_by_id(new_id)
        assert cat is not None and cat.sort_order == 50

    def test_delete(self, category_repo: CategoryRepository) -> None:
        new_id = category_repo.add(Category(name="ToDelete"))
        assert category_repo.delete(new_id)
        assert category_repo.get_by_id(new_id) is None

    def test_count(self, category_repo: CategoryRepository) -> None:
        assert category_repo.count() == 0
        category_repo.seed_defaults()
        assert category_repo.count() == len(DEFAULT_CATEGORIES)
