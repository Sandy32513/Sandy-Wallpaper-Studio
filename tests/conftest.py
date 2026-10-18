"""Sandy Wallpaper Studio — Pytest Configuration & Global Fixtures.
==================================================================
Centralized fixtures and configuration for all test suites.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest

# Ensure headless Qt operation in test environments
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """Ensure a headless QApplication instance exists for GUI tests."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def isolated_pictures_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary directory structure mimicking user Pictures folder."""
    pictures_root = tmp_path / "Pictures" / "SandyWallpaperStudio"
    pictures_root.mkdir(parents=True, exist_ok=True)
    yield pictures_root
