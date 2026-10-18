# Architecture Blueprint — Sandy Wallpaper Studio

Sandy Wallpaper Studio is a local-first Windows desktop application built with Python 3.12 and PySide6 (Qt for Python). It provides cataloging, intelligent image validation, perceptual duplicate detection, and native desktop wallpaper management for high-resolution displays (4K, 5K, 8K, and Ultrawide formats).

---

## 1. Architectural Layers & Separation of Concerns

The codebase enforces strict unidirectional dependencies from presentation down to data storage. Presentation components never execute database queries directly; all interaction flows through cohesive domain services.

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│                         (app.ui)                            │
│  MainWindow, Views (Dashboard, Library, Favorites, History) │
│  Components (Sidebar, SearchFilterBar, WallpaperCard, etc.) │
└──────────────────────────────┬──────────────────────────────┘
                               │ calls
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                          │
│                      (app.services)                         │
│  WindowsWallpaperService, HistoryService, LibraryService,   │
│  ImportService, DuplicateService, DownloadService           │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
┌─────────────────────────────┐ ┌─────────────────────────────┐
│        Data Access          │ │       External Sources      │
│       (app.database)        │ │        (app.sources)        │
│  Database, Repositories,    │ │  WikimediaSource,           │
│  Migrations, Models         │ │  WallpaperSource ABC        │
└──────────────┬──────────────┘ └─────────────────────────────┘
               │
               ▼
┌─────────────────────────────┐
│       SQLite Database       │
│      (wallpapers.db)        │
│  WAL Mode, Foreign Keys ON  │
└─────────────────────────────┘
```

---

## 2. Component Decomposition

### 2.1 Configuration and Constants (`app.config`, `app.constants`)
- **`Config`**: Manages validated, versioned JSON settings (`settings.json`) in the application data root (`%USERPROFILE%\Pictures\SandyWallpaperStudio` by default). Writes atomically; library root and database/cache paths remain distinct.
- **`constants.py`**: Central repository for application constants:
  - Resolution thresholds (8K: 7680x4320, 5K: 5120x2880, 4K: 3840x2160, QHD: 2560x1440, FHD: 1920x1080).
  - Import formats (`.jpg`, `.jpeg`, `.png`, `.webp`); AVIF is optional and not accepted by every processing path.
  - Native Windows wallpaper styles (`Center`, `Tile`, `Stretch`, `Fit`, `Fill`, `Span`).
  - Default wallpaper categories and network timeouts.

### 2.2 Database Layer (`app.database`)
- **`Database`**: SQLite connection wrapper. Configures `PRAGMA journal_mode = WAL` for concurrent read performance and `PRAGMA foreign_keys = ON` for relational integrity.
- **`migrations.py`**: Ordered migration runner recording applied versions in the `schema_migrations` table.
- **Models (`models.py`)**: Structured `@dataclass` representations:
  - `Wallpaper`: File path, dimensions, aspect ratio, resolution class, SHA-256, pHash, source, tags, and usage statistics.
  - `Category`: Categories for grouping wallpapers with sorting rules.
  - `DownloadRecord`: History and status of remote source downloads.
  - `WallpaperHistory`: Historical log of wallpapers applied to the desktop with target monitor tags and timestamps.
  - `WallpaperView`: Audit trail of wallpapers inspected in detail modals.
- **Repositories**: Encapsulated data-access objects:
  - `WallpaperRepository`: Parameterized CRUD, multi-criteria filtering, pagination, and SQL injection prevention via whitelisted order keys.
  - `CategoryRepository`: Default category seeding, user category management, and display sorting.
  - `HistoryRepository`: Tracking wallpaper application events with SQL joins and cascading cleanup.
  - `ViewRepository`: Event-based tracking for recently inspected items.

### 2.3 Sources Layer (`app.sources`)
- **`WallpaperSource`**: Abstract base class defining provider contracts: `search()`, `get_details()`, `get_download_url()`.
- **`WikimediaSource`**: Production implementation integrating with the MediaWiki Action API. Extracts resolution, MIME type, licensing information, and direct download links.

### 2.4 Service Layer (`app.services`)
- **`WindowsWallpaperService`**:
  - Interacts with native Windows APIs (`SystemParametersInfoW` with `SPI_SETDESKWALLPAPER`).
  - Configures desktop styles via Windows Registry (`Control Panel\Desktop`).
  - Enumerates physical display monitors (`EnumDisplayMonitors`), detecting resolution, primary status, and orientation.
  - Provides Pillow-based simulated preview rendering for desktop styles (`Center`, `Tile`, `Stretch`, `Fit`, `Fill`, `Span`).
  - Includes a simulation mode (`simulated=True`) to enable 100% deterministic testing on any platform.
- **`HistoryService`**: High-level orchestrator for desktop application history, favorites management, recently viewed items, and instant desktop restoration.
- **`ImportService`**: Batched local folder scanning, metadata extraction, dimension validation, and duplicate-aware importing.
- **`DuplicateService`**: Cryptographic exact matching (SHA-256) and perceptual near-duplicate detection (pHash, dHash, aHash). All duplicate detection is strictly **non-destructive**.
- **`LibraryService`**: Unified search queries, statistics aggregation (resolution distribution, storage usage), and non-destructive library integrity checking.
- **`DownloadService`**: Configurable size and timeout limits, bounded retries/backoff and concurrency, streaming temporary files, cancellation, content-type and Pillow integrity checks, and exclusive target finalization.
- **`SourceService`**: Builds the enabled Wikimedia provider with saved request timeout, minimum dimensions, and result cap. No other remote provider is registered.
- **`AttributionExportService`**: Exports stored licensing and creator metadata to formula-safe UTF-8 CSV through atomic replacement.

### 2.5 Presentation Layer (`app.ui`)
- **Design System (`design_system.py`)**: Curated "Obsidian" dark palette (`#0B0E14` base, `#121824` surface, `#4E75F6` primary accent, `#8257E5` secondary accent), typography scale, and layout spacing tokens.
- **`MainWindow`**: Root desktop window containing an animated `Sidebar`, `QStackedWidget` for view switching, and status bar.
- **Views**:
  - `DashboardView`: Key library metrics (counts, resolutions, monitor info, quick actions).
  - `LibraryView`: Infinite-scroll / paginated grid of wallpapers with live search and filtering.
  - `FavoritesView`: Dedicated favorites showcase with live category dropdown, multi-criteria sorting, and quick random favorite desktop application.
  - `HistoryView`: Three specialized tabs: Desktop Applied history (with relative timestamps and reapply), Recently Viewed, and Recently Downloaded.
  - `DuplicateManagerView`: Exact/near review and guarded Windows Recycle Bin cleanup.
  - `SettingsView`: Library/source/download/duplicate/thumbnail/logging preferences, background maintenance, attribution export, and the existing Rotation tab.
  - Placeholder destinations: Discover, Categories, and Downloads.
- **Components (`app.ui.components`)**:
  - `SearchFilterBar`: Debounced search input, category dropdown, resolution selector, and orientation filters.
  - `WallpaperCard`: Interactive card widget featuring asynchronous background thumbnail loading (`QThread`), star favorite toggle, and resolution tags.
  - `ImportProgressDialog`: Live folder import status, progress bar, and summary modal.
  - `WallpaperDetailDialog`: High-resolution preview, complete image metadata, and instant desktop application button.

### 2.6 Utility Layer (`app.utils`)
- **`hashing.py`**: SHA-256, pHash, dHash, and aHash generation with Hamming distance calculation.
- **`filename.py`**: Windows-safe filename sanitization, character escaping, and collision-free path resolution.
- **`image_utils.py`**: Safe image decoding, corrupted file detection, orientation normalization, and thumbnail rendering via Pillow.
- **`logging_config.py`**: Rotating file logging (`app.log`) and console output formatting.

---

## 3. Concurrency & Threading Model

To ensure a responsive GUI running at 60 FPS on Windows:

1. **GUI Main Thread**: Handles all Qt event loops, user clicks, and widget layout updates. Direct long-running file I/O or network requests on this thread are prohibited.
2. **Thumbnail Generation Worker (`QThread`)**: `WallpaperCard` requests image thumbnails asynchronously. The worker thread opens the file, validates pixels, generates the scaled thumbnail, and emits a `QPixmap` back to the main thread via Qt Signals.
3. **Batch Import Processing**: `ImportService` supports cancellation callbacks and periodic progress notifications (`ProgressCallback`) allowing smooth UI progress updates during large folder scans.

---

## 4. Data Safety & Non-Destructive Design Principles

1. **Zero Silent Deletions**: Duplicate detection never deletes or renames files without explicit confirmation.
2. **Transaction Integrity**: All database updates run inside explicit SQLite transactions. If a file fails validation during import, the partial record is discarded.
3. **Safe File Handling**: Remote downloads stream into temporary `.part` files and are published only after response, size, image-format, and decode checks. Existing destination files are never silently replaced.
4. **Isolated Test Fixtures**: All automated tests operate inside isolated temporary directories (`tmp_path`). Tests never read or modify the active developer's real wallpaper library.
