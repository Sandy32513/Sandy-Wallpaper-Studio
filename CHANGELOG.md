# Changelog

All notable changes to Sandy Wallpaper Studio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Phase 0 — Project Foundation
- Initialized project architecture and directory structure
- Created `pyproject.toml` with all dependency declarations
- Created `requirements.txt` for reproducible installs
- Implemented `Config` — JSON-based configuration manager with defaults
- Implemented `constants.py` — centralized application constants
- Implemented rotating file + console logging (`logging_config.py`)
- Created main entry point (`main.py`) with CLI argument parsing
- Added `python -m app` support
- Created `.gitignore` for Python, IDE, OS, and app data files
- Created project documentation: README, CHANGELOG, LICENSE, PRIVACY
- Initialized Git repository

### Phase 1 — Database Layer
- Created SQLite database with WAL mode and foreign keys
- Implemented `Wallpaper` model (22 fields), `Category`, `DownloadRecord`, `WallpaperHistory` models
- Built migration system with version tracking (Migration 001: initial schema)
- Created indexes on sha256, phash, category, resolution_class, favorite, download_date
- Implemented `WallpaperRepository` — full CRUD, smart search, pagination, statistics
- Implemented `CategoryRepository` — default seeding (44 categories), custom categories
- Database auto-initializes and seeds on first launch
- 73 tests passing (19 Phase 0 + 54 Phase 1)

