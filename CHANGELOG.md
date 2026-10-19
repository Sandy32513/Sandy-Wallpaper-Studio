# Changelog

All notable changes to Sandy Wallpaper Studio are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-10-19

### Phase 11 - Release Hardening (QA recorded)

#### Added
- A 40,000,000-pixel image ceiling enforced before Pillow decode/hash/thumbnail work and before Qt detail, card, and comparison previews decode source images. Valid 8K UHD/DCI dimensions remain within the ceiling.
- Direct HTTPS download URL validation, rejection of URL credentials, nonstandard explicit ports, known local targets, and redirects.
- DNS rebinding defense for downloads: resolve and reject any non-global DNS answer, connect to a vetted IP address, and retain the original hostname for TLS SNI/certificate validation and HTTP Host; environment proxies are disabled.
- Reproducible synthetic duplicate-scan benchmark results at 100, 500, 1,000, and 5,000 records, with elapsed time, throughput, peak Windows working set, classification correctness, and cancellation latency recorded in `docs/PHASE11_PERFORMANCE.md`.
- Phase 11 security, UI, Windows, documentation, and release-readiness evidence in `docs/PHASE11_ACCEPTANCE.md` and `docs/PROJECT_STATUS.md`.

#### Fixed
- Responsive search/filter controls and wallpaper grids in Library and Favorites, plus Dashboard statistic/action cards, to prevent clipping and horizontal overflow at 800x600.
- Wallpaper detail dialogs now fit the host window/work area, wrap actions at compact sizes, resize previews to the available viewport, and show an accessible message for images exceeding the pixel ceiling.
- Added accessible names for filter controls and detail-dialog actions.

#### Verified
- Full regression: 387 passed, 2 skipped (389 collected); Ruff and mypy passed. Project-venv `pip-audit --local` found no known advisories in installed packages (the local project package is not on PyPI). Benchmark results and inspected Windows Qt sizes are in `docs/PHASE11_PERFORMANCE.md` and `docs/PROJECT_STATUS.md`.
- At the Phase 11 checkpoint, the project version was `0.7.0-dev`; Phase 11 commits are on `main`, but no Phase 11 release tag, installer, or product release was created.

#### Remaining acceptance gates
- Real desktop wallpaper application, physical keyboard/Narrator review, Windows 10, and clean-machine acceptance have not been completed.

### Phase 12 - Packaging validation (not a release)

#### Added
- Reproducible unsigned Windows x64 PyInstaller `onedir` build, isolated path-with-spaces smoke test, version-resource checks, and a packaged PNG import/settings-persistence check across separate processes before GUI startup/shutdown.
- Packaging and interactive Windows acceptance procedures in `docs/PACKAGING.md` and `docs/WINDOWS_ACCEPTANCE.md`.

#### Scope
- The initial local bundle used `0.7.0-dev`; `V0.1.0` is a previous validation build. The current source and latest local validation bundle are `V1.0.0`. No installer, signing, release tag, or public download has been produced. Clean-machine and Windows 10 acceptance remain open.

### Previous version identifier update (`V0.1.0`)
- Synchronized the application version string and Python project metadata to `V0.1.0`.
- Setuptools normalizes distribution metadata to `0.1.0`; Windows file-version metadata uses `0.1.0.0`, while the product version retains the requested `V` prefix.
- Rebuilt and smoke-tested the unsigned Windows bundle at `V0.1.0`; artifact details are in `docs/PACKAGING.md`.
- This version change does not create a Git tag or publish a release.

### Version identifier update (`V1.0.0`)
- Synchronized the application version string and Python project metadata to `V1.0.0`.
- Setuptools normalizes distribution metadata to `1.0.0`; the Windows build script derives file-version metadata `1.0.0.0` and preserves the `V` product-version prefix.
- Built and smoke-tested an unsigned Windows x64 `onedir` validation bundle at `V1.0.0`; exact source commit and artifact evidence are in `docs/PACKAGING.md`.
- The local validation bundle is not signed or published. No Git tag, installer, or public release was created.

### Phase 10 - Settings & Operational Features

#### Added
- Integrated Settings tabs for library/import behavior, Wikimedia enablement and query limits, download safeguards, duplicate threshold, thumbnail cache, logging, wallpaper style, and preserved automatic rotation.
- Schema-v2 JSON configuration with independent validation, legacy rotation interval migration, same-directory atomic writes, and rollback of in-memory values after persistence failures.
- Config-backed `SourceService` and `DownloadService`; downloads enforce size, timeout, bounded retry/backoff and concurrency settings, validate image bytes, and only publish complete supported images.
- Versioned thumbnail cache keys, cache-budget eviction limited to the app cache, cache consumption across wallpaper-card views, and cancellable background thumbnail regeneration.
- Background library integrity checking and atomic UTF-8 attribution CSV export with spreadsheet-formula neutralization and overwrite confirmation.
- Phase 10 isolated configuration/service/export/UI tests and inspected Settings captures at four window sizes.

#### Safety and scope
- Library-root changes do not move images, reindex rows, or relocate SQLite. Local browsing and rotation remain offline-capable.
- Attribution export uses persisted metadata only; missing online attribution is counted and not inferred. No live provider request was made by tests.
- Discover, Categories, and Downloads remain placeholder destinations; this release adds configuration and backend enforcement, not those workflows.

#### Verified
- Focused Phase 10 suite: 25 passed; full regression: 377 passed, 2 skipped (379 collected). Ruff, mypy, and `git diff --check` passed. Details and UI capture sizes are recorded in `docs/PROJECT_STATUS.md`.

### Phase 9 - Duplicate Manager (complete)

#### Added
- Read-only full-library duplicate scans on a background Qt worker. Exact matches use current-file SHA-256 plus byte comparison; near matches use 64-bit pHash Hamming distance, a BK-tree, and direct pair scores.
- Search, sort, pagination, explicit retained-file and cleanup-target choices, scan issue details, and asynchronous side-by-side comparison.
- Windows cleanup confirmation with current path and size review, per-target revalidation, exclusive-open checks, and the Windows Recycle Bin through IFileOperation with FOFX_RECYCLEONDELETE. There is no permanent-delete fallback.
- Per-file cleanup results, cancellation, stop-on-failure behavior, and a forced rescan after cleanup. Library and history database records are retained.
- A near-match edge cap with an explicit incomplete scan result rather than presenting partial groups as complete.
- Windows CI type checking with python -m mypy app.

#### Safety boundary
- Cleanup is available only on Windows and only within the configured library. Linked/reparse-point files, hard links, files outside the library, changed files, locked files, and targets without an explicit retained peer are rejected.
- Cleanup does not alter SQLite rows. A subsequent scan reports a recycled file as missing until it is restored or reimported.

#### Verified
- Phase 9 focused suite: 34 passed, 2 skipped (python -m pytest tests/test_phase9.py tests/test_phase9_cleanup.py tests/test_phase9_workflow.py -q).
- Full regression suite: 352 passed, 2 skipped (python -m pytest -q). The optional real Windows Recycle Bin round trip was also run separately and passed; its synthetic fixture was restored and verified.
- Ruff and mypy passed (python -m ruff check .; python -m mypy app). Both CLI version entry points report 0.7.0-dev.
- An isolated synthetic-library scan found one exact group, one near group, and one corrupt-file issue; schema version 2 and SQLite foreign-key integrity were confirmed.
- Qt captures were reviewed at multiple window sizes, including Duplicate Manager exact/near results, empty and issue states, comparison and cleanup confirmation dialogs, Settings, and History. No production library or desktop wallpaper was used.
- The Computer Use native pipe was unavailable after its prescribed retry and reset. The fallback used a real Windows Qt window, QTest event delivery, and inspected QWidget.grab() captures; physical-input testing was not performed. See docs/PROJECT_STATUS.md.

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
