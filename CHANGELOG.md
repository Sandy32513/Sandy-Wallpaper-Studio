# Changelog

All notable changes to Sandy Wallpaper Studio are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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