# Sandy Wallpaper Studio

> A Windows desktop application for building, organizing, validating, downloading, and managing high-resolution wallpapers.

![Package Version](https://img.shields.io/badge/package-1.0.0-blue)
![Development Phase](https://img.shields.io/badge/development-Phase%203-orange)
![Python](https://img.shields.io/badge/python-3.12%2B-green)
![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-lightgrey)
![License](https://img.shields.io/badge/license-MIT-black)

**Repository:** https://github.com/Sandy32513/Sandy-Wallpaper-Studio

---

## Project Status

Sandy Wallpaper Studio is being developed as a controlled, phase-by-phase Windows application.

The repository is currently at **Phase 3**.

The implementation currently covers the project foundation, SQLite persistence, wallpaper-source integration, downloading, image validation, metadata extraction, thumbnails, and duplicate-detection primitives.

> **Important:** The PySide6 desktop GUI is not yet the current application surface. GUI work is planned for a later phase. The current entry point initializes application configuration and the database and reports the initialized state.

### Phase completion

| Phase | Scope | Status |
|---|---|---|
| Phase 0 | Foundation, configuration, logging, package structure, CLI entry point | Complete |
| Phase 1 | SQLite database, models, migrations, repositories, categories | Complete |
| Phase 2 | Wikimedia Commons source, metadata, download service | Complete |
| Phase 3 | SHA-256, pHash, duplicate detection, image validation, thumbnails | Complete |
| Phase 4 | Smart library, import pipeline, search/filter integration | Next |
| Phase 5 | Windows wallpaper engine and multi-monitor support | Planned |
| Phase 6 | PySide6 desktop GUI | Planned |
| Phase 7 | Favorites and history workflows | Planned |
| Phase 8 | Automatic wallpaper rotation | Planned |
| Phase 9 | Duplicate Manager UI | Planned |
| Phase 10 | Settings, attribution export and operational polish | Planned |
| Phase 11 | Full QA and release hardening | Planned |
| Phase 12 | PyInstaller packaging | Planned |
| Phase 13 | Windows installer | Planned |

The authoritative project status is maintained in docs/PROJECT_STATUS.md.

---

## What Works Today

### Foundation
- Python 3.12+ project configuration
- pyproject.toml package metadata
- requirements.txt dependency installation
- python -m app entry point
- JSON-based configuration
- centralized application constants
- rotating console/file logging
- Windows-oriented application structure

### Database
- SQLite database
- WAL mode and foreign-key enforcement
- schema migration tracking
- Wallpaper, Category, DownloadRecord and WallpaperHistory models
- indexed lookup fields
- WallpaperRepository CRUD, search, pagination and statistics
- CategoryRepository
- 44 default categories
- custom categories

### Wallpaper source and downloading
- Wikimedia Commons through the official MediaWiki API
- search-result normalization
- image metadata extraction
- source URL, author and license capture
- full-resolution download URLs
- streaming downloads
- temporary-file download flow
- download size protection
- HTTP and content-type validation
- retry and exponential backoff
- cancellation callback
- filename and directory sanitization
- SHA-256 calculation during downloads

### Image processing and duplicate detection
- supported-format validation
- corruption and integrity validation
- pixel decoding validation
- dimension validation
- resolution classification
- aspect-ratio detection
- SHA-256 exact duplicate detection
- pHash near-duplicate detection
- configurable pHash threshold
- dHash and aHash utilities
- Hamming-distance calculation
- similarity percentage calculation
- thumbnail generation

### Safety principle
Duplicate detection is detection only. The application does not automatically delete a wallpaper merely because it matches another image.

---

## Architecture

The project uses a layered architecture so data and business logic can be tested independently from the future desktop UI.

```text
Sandy Wallpaper Studio
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── constants.py
│   ├── database/
│   ├── sources/
│   ├── services/
│   ├── utils/
│   └── ui/
│
├── tests/
│   ├── test_phase0.py
│   ├── test_phase1.py
│   ├── test_phase2.py
│   └── test_phase3.py
│
├── docs/
│   ├── PROJECT_STATUS.md
│   └── ROADMAP.md
│
├── pyproject.toml
├── requirements.txt
├── CHANGELOG.md
├── PRIVACY.md
├── LICENSE
└── README.md
```

### Data flow
```text
Wallpaper Source
      ↓
Search Result
      ↓
Download to Temporary File
      ↓
Image Validation
      ↓
Metadata Extraction
      ├── SHA-256
      ├── pHash
      ├── resolution
      ├── aspect ratio
      └── format
      ↓
Duplicate Detection
      ↓
Thumbnail Generation
      ↓
Database Record
      ↓
Permanent Library
```

Phase 4 will connect these existing primitives into a complete library/import workflow.

---

## Supported Source

### Wikimedia Commons
The current external source is Wikimedia Commons through the official MediaWiki API.

Captured metadata can include title, description, author, license, license URL, source URL, categories, dimensions, file size, format, full-resolution URL and thumbnail URL.

The application does not use web scraping or anti-bot bypass techniques.

---

## Requirements
- Windows 10 or Windows 11
- Python 3.12 or later
- Internet access for external-source search/download features
- Disk space for the wallpaper library

Core dependencies: PySide6, Pillow, ImageHash and requests.

Development dependencies: pytest, pytest-cov, ruff, mypy and PyInstaller.

---

## Quick Start

### 1. Clone
```powershell
git clone https://github.com/Sandy32513/Sandy-Wallpaper-Studio.git
cd Sandy-Wallpaper-Studio
```

### 2. Virtual environment
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run
```powershell
python -m app
```

Optional current entry-point arguments include --version, --debug and --library. Other CLI switches are placeholders until their corresponding phases are implemented.

---

## Testing
```powershell
pytest
pytest --cov=app --cov-report=term-missing
```

Each completed phase has its own test suite. A later phase must not silently replace incomplete earlier functionality.

---

## Development Rules
1. One phase at a time.
2. Complete and test a phase before starting the next.
3. Preserve earlier functionality.
4. Prefer small, reviewable commits.
5. Keep GUI code separate from business logic.
6. Use official APIs or explicitly permitted endpoints.
7. Never silently delete user wallpaper files.
8. Keep duplicate detection separate from deletion.
9. Validate downloads before permanent storage.
10. Keep source providers behind a common interface.
11. Update documentation when implementation status changes.
12. Run tests before milestone tags.

---

## Next Milestone: Phase 4
- Import existing wallpaper folders
- Recursive image discovery
- Validation during import
- Metadata indexing
- SHA-256 and pHash indexing
- Duplicate-aware import
- Search and filtering
- Category assignment
- Resolution and aspect-ratio filters
- Source and license filters
- Pagination and statistics
- Phase 4 automated tests

The goal is to complete the data/library workflow before building the full desktop UI.

---

## Documentation
- Project status: docs/PROJECT_STATUS.md
- Roadmap: docs/ROADMAP.md
- Changelog: CHANGELOG.md
- Privacy: PRIVACY.md
- License: LICENSE

## License
MIT License.