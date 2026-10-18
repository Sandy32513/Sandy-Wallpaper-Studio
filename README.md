# Sandy Wallpaper Studio

> A Windows desktop application for building, organizing, validating, downloading, and managing high-resolution wallpapers.

![Package Version](https://img.shields.io/badge/package-0.5.0--dev-blue)
![Development Phase](https://img.shields.io/badge/development-Phase%205-orange)
![Python](https://img.shields.io/badge/python-3.12%2B-green)
![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-lightgrey)
![License](https://img.shields.io/badge/license-MIT-black)

**Repository:** https://github.com/Sandy32513/Sandy-Wallpaper-Studio

---

## Project Status

Sandy Wallpaper Studio is developed under a strict, phase-by-phase engineering discipline.

The repository is currently at **Phase 5 — Windows Wallpaper Engine** complete.

The implementation currently covers the project foundation, SQLite persistence, Wikimedia Commons wallpaper source & downloading, image intelligence & duplicate detection, smart library importing & searching, and native Windows wallpaper setting, multi-monitor detection, random wallpaper selection, preview generation, and history tracking.

> **Important:** The PySide6 desktop GUI is planned for Phase 6. The current entry point initializes application configuration, database, services, and reports the initialized state and connected monitors.

### Phase Completion Matrix

| Phase | Scope | Status | Tests |
|---|---|---|---|
| Phase 0 | Foundation, configuration, logging, package structure, CLI entry point | Complete | 19 passing |
| Phase 1 | SQLite database, models, migrations, repositories, categories | Complete | 54 passing |
| Phase 2 | Wikimedia Commons source, metadata, streaming download service | Complete | 48 passing |
| Phase 3 | SHA-256, pHash, duplicate detection, image validation, thumbnails | Complete | 39 passing |
| Phase 4 | Smart library, import pipeline, search/filter, stats, integrity | Complete | 60 passing |
| Phase 5 | Windows wallpaper engine, multi-monitor, random, restore, preview | Complete | 33 passing |
| Phase 6 | PySide6 desktop GUI | Complete | 9 passing |
| Phase 7 | Favorites and history workflows | Complete | 24 passing |
| Phase 8 | Automatic wallpaper rotation | Next | Planned |
| Phase 9 | Duplicate Manager UI | Planned | Planned |
| Phase 10 | Settings, attribution export and operational polish | Planned | Planned |
| Phase 11 | Full QA and release hardening | Planned | Planned |
| Phase 12 | PyInstaller packaging | Planned | Planned |
| Phase 13 | Windows installer | Planned | Planned |

Total automated test suite: **286 passing / 0 failing**.

The authoritative project status is maintained in `docs/PROJECT_STATUS.md`.

---

## What Works Today

### Foundation (Phase 0)
- Python 3.12+ project configuration with strict typing
- `pyproject.toml` package metadata and dependency configuration
- `python -m app` CLI entry point with status report
- JSON-based configuration management
- Centralized application constants (resolutions, aspect ratios, formats, styles)
- Rotating console and file logging

### Database (Phase 1)
- SQLite database with WAL mode and foreign-key enforcement
- Schema migration tracking (`schema_version`)
- `Wallpaper`, `Category`, `DownloadRecord`, and `WallpaperHistory` dataclass models
- `WallpaperRepository` CRUD, search, pagination, and statistics
- `CategoryRepository` with 44 seeded default categories and custom category creation
- Performance indexes on hashes, categories, resolutions, favorites, and dates

### Wallpaper Source & Download (Phase 2)
- Official MediaWiki API integration for Wikimedia Commons
- Structured metadata extraction (author, license, license URL, source URL, resolution)
- Safe streaming download to temporary files before validation
- File size protection (max 100MB default) and HTTP status/content-type validation
- Exponential backoff retry and cancellation callbacks
- Filename sanitization protecting Windows filesystems

### Image Intelligence & Duplicate Detection (Phase 3)
- Multi-format validation: JPG, PNG, WEBP, and AVIF
- Corruption, truncation, and decode integrity checks
- Resolution classification (4K, 5K, 8K, UW-QHD, UW-5K, QHD, FHD)
- Aspect-ratio detection with tolerance matching
- SHA-256 exact duplicate detection
- Perceptual hashing (pHash, dHash, aHash) with configurable Hamming threshold
- Thumbnail generation and cache management

### Smart Library (Phase 4)
- Existing folder import orchestration (`ImportService`)
- Recursive and flat discovery of image files
- Duplicate-aware importing (skips exact duplicates, flags near duplicates)
- Cancellation and progress callback reporting
- Multi-dimensional library search (`LibraryService`) across title, category, resolution, aspect ratio, source, and license
- Library statistics and non-destructive integrity audits

### Windows Wallpaper Engine (Phase 5)
- Native Windows wallpaper changing via `SystemParametersInfoW` without admin rights
- Desktop wallpaper styles: `Center`, `Tile`, `Stretch`, `Fit`, `Fill`, and `Span`
- Multi-monitor awareness via `EnumDisplayMonitors` (resolution, bounds, primary, orientation)
- Selected wallpaper setting with database usage tracking (`usage_count`, `last_used`)
- `HistoryRepository` for recording wallpaper application history
- Previous wallpaper restoration from history
- Random wallpaper selection with category, favorites, min-resolution filters and repeat avoidance
- Accurate desktop preview generation for all 6 styles using Pillow
- Test simulation mode for deterministic cross-platform validation

---

## Architecture

```text
Sandy Wallpaper Studio
│
├── app/
│   ├── main.py                     # Entry point & startup banner
│   ├── config.py                   # Configuration management
│   ├── constants.py                # Resolutions, styles, categories, formats
│   ├── database/
│   │   ├── database.py             # SQLite connection & WAL management
│   │   ├── models.py               # Wallpaper, Category, History dataclasses
│   │   ├── migrations.py           # Schema migrations
│   │   ├── wallpaper_repository.py # Wallpaper CRUD & smart search
│   │   ├── category_repository.py  # Category management
│   │   └── history_repository.py   # Wallpaper application history
│   ├── sources/
│   │   ├── base.py                 # WallpaperSource interface
│   │   └── wikimedia.py            # Wikimedia Commons API provider
│   ├── services/
│   │   ├── download_service.py     # Safe streaming downloader
│   │   ├── metadata_service.py     # Metadata extraction
│   │   ├── duplicate_service.py    # SHA-256 & pHash duplicate detection
│   │   ├── import_service.py       # Folder import pipeline
│   │   ├── library_service.py      # Library facade & statistics
│   │   └── wallpaper_service.py    # Windows wallpaper engine & preview
│   └── utils/
│       ├── hashing.py              # Cryptographic & perceptual hashing
│       ├── image_utils.py          # Format, decode, & resolution validation
│       ├── filename.py             # Filename sanitization
│       └── logging_config.py       # Rotating logging setup
│
├── tests/
│   ├── test_phase0.py              # Foundation tests (19 passed)
│   ├── test_phase1.py              # Database & repository tests (54 passed)
│   ├── test_phase2.py              # Wikimedia & download tests (48 passed)
│   ├── test_phase3.py              # Image hashing & duplicate tests (39 passed)
│   ├── test_phase4.py              # Smart library & import tests (60 passed)
│   └── test_phase5.py              # Wallpaper engine & preview tests (33 passed)
│
├── docs/
│   ├── PROJECT_STATUS.md           # Authoritative phase status
│   └── ROADMAP.md                  # Sequential roadmap & deliverables
│
├── pyproject.toml
├── requirements.txt
├── CHANGELOG.md
├── PRIVACY.md
├── LICENSE
└── README.md
```

---

## Requirements
- Windows 10 or Windows 11 (tested on Windows 11)
- Python 3.12 or later
- Internet access for Wikimedia Commons download features
- Disk space for the wallpaper library

Core dependencies: Pillow, ImageHash, requests, PySide6.

---

## Quick Start

### 1. Clone
```powershell
git clone https://github.com/Sandy32513/Sandy-Wallpaper-Studio.git
cd Sandy-Wallpaper-Studio
```

### 2. Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run
```powershell
python -m app
```

---

## Testing

Run the complete 253-test suite:
```powershell
pytest -v
```

Run test suite for a specific phase:
```powershell
pytest tests/test_phase5.py -v
```

---

## Next Milestone: Phase 6 — Desktop GUI
- Modern dark-themed PySide6 desktop interface
- Sidebar navigation: Dashboard, Discover, Categories, Favorites, History, Library, Duplicates, Settings
- Wallpaper grid with lazy-loaded thumbnail rendering
- Wallpaper detail dialog with full metadata and action buttons
- "Set Wallpaper", "Restore Previous", "Random Wallpaper" UI triggers
- Advanced filter toolbar (resolution, aspect ratio, orientation, category)

---

## License
MIT License.