# Changelog

All notable changes to Sandy Wallpaper Studio are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — 2026-10-19

### Phase 9 — Duplicate Manager (partial)

#### Added
- Read-only full-library duplicate scanning on a background Qt worker, with current-file SHA-256 and pHash recomputation, exact byte verification, and BK-tree near-match grouping.
- Searchable, sortable, paginated exact and near-match review with explicit retained-file choice, independent comparison selection, path/metadata display, and scan issue details.
- Side-by-side image and metadata comparison for two to four selected files.
- Revalidated cleanup-plan preview with no file or database changes; database opening in read-only/query-only mode.
- Nineteen focused Phase 9 service, database, cleanup-preview, and UI tests.

#### Safety boundary
- The cleanup action remains disabled because a recoverable Recycle Bin/quarantine workflow has not been implemented or verified. Phase 9 is partial.

#### Verified
- The full regression suite passed 336 / 336; Ruff and configured mypy passed.
- Windows Qt captures were inspected at 1440×820, 1280×800, 1024×768, and the 1024×680 minimum for an 800×600 request. Native Recycle Bin/quarantine behavior remains untested because cleanup is disabled.

### Phase 8 — Automatic Rotation (finalized)

#### Added
- `RotationService` for metadata-filtered category and minimum-dimension selection, local image validation, random or deterministic cycling, repeat avoidance, cancellation, and existing wallpaper-engine application.
- `RotationScheduler` with one Qt timer, pause/resume/stop controls, a worker-owned SQLite connection, and shutdown cleanup.
- Automatic Rotation settings under the existing Settings sidebar destination, including interval, random selection, categories, and minimum width/height controls.
- Additive database migration for rotation source, success status, and safe error details in the existing wallpaper history table.
- A Rotation Events tab that distinguishes successful automatic changes and failed application attempts.
- 31 Phase 8 tests; the full suite passed 317 / 317 on October 19, 2026.
- Zero repository mypy errors after correcting 14 pre-existing type issues across eight files.
- Typed category and control focus order, visible keyboard focus styles, and QTest coverage for navigation, rotation controls, history, and card thumbnail activation.

#### Verified
- Windows rotation worker applied a temporary library image, recorded the rotation event, and restored the prior desktop wallpaper path and style.
- Windows Qt GUI interaction and visually inspected captures at 1280×800, 1024×768, the 1024×680 application minimum for the 800×600 request, and 1440×844 under the 1440×900 request's screen work-area limit. The QA run used temporary app data and a simulated wallpaper service.
- `python -m ruff check .`, `python -m mypy app`, the targeted Phase 8 suite, and the full test suite passed.

#### QA limitation
- The Computer Use native-pipe helper was unavailable. Visible Windows Qt widgets were driven with QTest and captured with `QWidget.grab()`; physical keyboard/mouse spot-check steps are recorded in `docs/PROJECT_STATUS.md`.

## [0.7.0-dev] - 2026-10-18

### Phase 7 — Favorites & History

#### Added
- `WallpaperView` data model and `ViewRepository` for tracking inspected wallpaper events with foreign key cascade deletion
- Dedicated `FavoritesView` (`favorites_view.py`) featuring live category filter dropdown, multi-criteria sorting (Newest, Oldest, Title, Resolution, Usage), quick random favorite desktop application, card-based favorites grid, and safe clear favorites workflow with confirmation
- Comprehensive `HistoryView` (`history_view.py`) with 3 specialized tabs:
  - **Desktop Applied**: Chronological application history cards displaying thumbnail, title, category, resolution, target monitor, exact timestamp, human-readable relative time ("Just now", "X mins ago", "Yesterday at..."), and a direct one-click "Reapply" desktop action
  - **Recently Viewed**: Dynamically updated gallery of inspected wallpapers tracked whenever detail modals are viewed across the application
  - **Recently Downloaded / Imported**: Gallery of newly imported or downloaded wallpapers ordered by date
- Quick "Restore Previous Wallpaper" button restoring prior desktop background with a single click
- Backend `HistoryService` (`history_service.py`) orchestrating all favorites and history business logic with zero direct database coupling in UI layers
- Enhanced `WallpaperRepository` with `toggle_favorite`, `count_favorites`, `get_recently_downloaded`, and `get_recently_applied`
- Enhanced `HistoryRepository` with `get_recent_with_wallpapers` (SQL JOIN) and `get_recent_wallpapers`
- Comprehensive Phase 7 test suite (`test_phase7.py`, 24 tests; 286 total suite tests passing)

### Repository Architecture & Tooling Standardization
- Synchronized canonical application version across `pyproject.toml`, `app/constants.py`, and test assertions (`0.7.0-dev`)
- Added comprehensive developer tooling: `.editorconfig`, `.gitattributes`, `.python-version` (3.12)
- Added automated CI test pipeline (`.github/workflows/tests.yml`) with headless Qt execution
- Added architecture blueprint (`docs/ARCHITECTURE.md`) and developer workflows guide (`docs/DEVELOPMENT.md`)
- Added open-source contributor guide (`CONTRIBUTING.md`) and package asset documentation (`assets/README.md`, `scripts/README.md`)
- Centralized pytest fixtures in `tests/conftest.py` with headless `QT_QPA_PLATFORM=offscreen` support

## [0.6.0-dev] - 2026-10-18

### Phase 6 — Desktop GUI

#### Added
- Modern dark-themed desktop interface using PySide6 (Obsidian theme)
- Design system (`design_system.py`) with curated dark palette, typography metrics, and layout constants
- Responsive `MainWindow` featuring animated sidebar navigation, status bar, and central view stack
- `DashboardView` with library statistics overview, quick-action tiles, and monitor resolution card
- `LibraryView` displaying responsive wallpaper grid with pagination and empty-state handler
- `SearchFilterBar` toolbar with debounced search, category filter, resolution picker, orientation filter, and quick actions
- `WallpaperCard` component with asynchronous background thumbnail loading via `QThread`, favorite toggling, and action buttons
- `ImportProgressDialog` for interactive folder import with live progress bar and completion summary
- `WallpaperDetailDialog` for full wallpaper preview inspection, metadata display, and desktop background application
- Comprehensive Phase 6 test suite (`test_phase6.py`, 9 tests; 262 total suite tests passing)

## [0.5.0-dev] - 2026-10-18

### Phase 5 — Windows Wallpaper Engine

#### Added
- Native Windows wallpaper changing via `SystemParametersInfoW` (no admin rights required)
- Wallpaper style registry configuration supporting `Center`, `Tile`, `Stretch`, `Fit`, `Fill`, and `Span`
- Multi-monitor awareness and detection via `EnumDisplayMonitors` reporting name, resolution, orientation (Landscape/Portrait), primary status, and virtual screen bounds
- `WallpaperApplyResult` structured response with success, applied timestamps, and error diagnostics
- Selected wallpaper application with automatic database usage incrementation (`usage_count`, `last_used`)
- `HistoryRepository` for tracking desktop background applications in the `wallpaper_history` table
- Restore previous wallpaper functionality via history records and in-memory fallback stack
- Random wallpaper selection with category, favorites, min-resolution filters, and repeat avoidance
- Accurate multi-style wallpaper preview generation via Pillow (`preview_wallpaper` & `save_preview`)
- Validation preventing blanking desktop backgrounds with non-existent, corrupt, or unsupported image files
- Comprehensive Phase 5 test suite (33 tests)

## [0.4.0-dev] - 2026-10-16

### Phase 4 — Smart Library

#### Added
- `ImportService` orchestrating folder imports with recursive or flat discovery
- Per-file validation, dimension checking, and metadata extraction
- SHA-256 exact duplicate detection skipping already indexed files
- pHash near-duplicate detection flagging similar wallpapers with warnings
- Cancellation support and progress callbacks reporting during batch imports
- `LibraryService` providing unified search across categories, resolutions, aspect ratios, sources, and formats
- Library statistics aggregation (resolution distribution, format distribution, total size)
- Non-destructive library integrity checking (detecting missing files and orphaned thumbnails)
- Comprehensive Phase 4 test suite (60 tests)

## [0.3.0-dev] - 2026-10-02

### Phase 3 — Image Validation, Hashing & Duplicate Detection
**Commit:** `6434e8c6b71a9fdcca4612a107e1c605a429345c`

#### Added
- SHA-256 hashing
- pHash perceptual hashing
- dHash and aHash utilities
- Hamming distance and similarity percentage
- Exact duplicate detection
- Near-duplicate detection
- Configurable pHash threshold
- Image integrity and format validation
- Full pixel decode validation
- Resolution and aspect-ratio classification
- Thumbnail generation
- Download size protection

#### Design rule
Duplicate detection is non-destructive. Detection does not automatically delete files.

## [0.2.0-dev] - 2026-09-28

### Phase 2 — Wikimedia Source & Download Service
**Commit:** `4beef3af37136cf09d9d10f9c394bdf2631bc576`

#### Added
- Wikimedia Commons provider
- Official MediaWiki API integration
- Wallpaper search
- Minimum-resolution filtering
- Source metadata and license capture
- Source URLs and image URLs
- Streaming downloads
- Retries and exponential backoff
- Cancellation callback
- Temporary-file download flow
- HTTP and content-type validation
- Filename sanitization

## [0.1.0-dev] - 2026-09-25

### Phase 1 — SQLite Database Layer
**Commit:** `c56b7f0f60f5f3434024d475cf3ea72378755f0f`

#### Added
- SQLite database with WAL mode
- Foreign-key enforcement
- Migration tracking
- Wallpaper, Category, DownloadRecord and WallpaperHistory models
- Repository layer
- CRUD, smart search, pagination and statistics
- 44 default categories
- Custom category support
- Database/index tests

## [0.0.1-dev] - 2026-09-20

### Phase 0 — Project Foundation
**Commit:** `9702d2ddd358888f8a922cd1885d0b5c502dea06`

#### Added
- Initial architecture
- Python package structure
- pyproject.toml
- requirements.txt
- Configuration manager
- Constants
- Logging
- Main entry point (`python -m app`)
- CLI argument parsing
- Git ignore rules
- README, CHANGELOG, LICENSE and PRIVACY
- Phase 0 tests
