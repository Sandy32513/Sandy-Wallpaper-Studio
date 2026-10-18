# Project Status — Sandy Wallpaper Studio

**Current development phase: Phase 9 — PARTIALLY COMPLETE**
**Status date: 2026-10-19**
**Latest full test run: 336 passing / 0 failing**
**Branch: `chore/repository-cleanup`**
**Phase 9 starting baseline: `625611c` (`origin/main`)**

This document is the implementation-status reference for the repository.

The Phase 8 finalization is included in the `origin/main` baseline at `625611c`. Phase 9 development is being completed on `chore/repository-cleanup`; this work is local and has not been pushed.

## Phase 0 — Foundation
**Status: COMPLETE**
Python package structure, configuration, constants, logging, CLI entry point, package metadata, dependency declarations, tests and documentation foundation.

Milestone: 9702d2ddd358888f8a922cd1885d0b5c502dea06

## Phase 1 — Database
**Status: COMPLETE**
SQLite, WAL, foreign keys, migrations, models, repositories, indexes, CRUD, search, pagination, statistics, 44 default categories and custom categories.

Milestone: c56b7f0f60f5f3434024d475cf3ea72378755f0f

## Phase 2 — Source & Download
**Status: COMPLETE**
Wikimedia Commons provider, official MediaWiki API, search, resolution filtering, metadata, license fields, source URLs, thumbnails, full-resolution URLs, streaming download, retry/backoff, cancellation, size protection, content-type validation and filename sanitization.

Milestone: 4beef3af37136cf09d9d10f9c394bdf2631bc576

## Phase 3 — Image Processing & Duplicate Detection
**Status: COMPLETE**
SHA-256, pHash, dHash, aHash, Hamming distance, similarity percentage, exact and near duplicate detection, configurable pHash threshold, image integrity validation, format validation, decode validation, resolution classification, aspect-ratio detection and thumbnail generation.

Milestone: 6434e8c6b71a9fdcca4612a107e1c605a429345c

## Phase 4 — Smart Library
**Status: COMPLETE**
Import existing folders, recursive/flat discovery, metadata indexing, per-file validation, SHA-256 and pHash duplicate-aware import, category assignment, multi-dimensional search, filtering, pagination, library statistics, import history and error reporting.

Milestone: 5741e023d36fddc0c68d79c659e6ac45aecc499d

## Phase 5 — Windows Wallpaper Engine
**Status: COMPLETE**
Native Windows wallpaper setting via `SystemParametersInfoW` with style registry mapping (`Center`, `Tile`, `Stretch`, `Fit`, `Fill`, `Span`), multi-monitor detection & bounds awareness via `EnumDisplayMonitors`, random wallpaper selection with category/favorite/resolution filters and repeat avoidance, previous wallpaper restoration, multi-style desktop preview generation, and `HistoryRepository` for desktop application tracking.

## Phase 5 Exit Gate Verification
- [x] Full pytest suite passes (253 / 253 tests pass)
- [x] Phases 0–5 pass together without regressions
- [x] Wallpaper setting supports Center, Tile, Stretch, Fit, Fill, Span
- [x] Multi-monitor detection reports resolution, bounds, orientation, primary status
- [x] Random wallpaper supports category, favorites, min-resolution filters and repeat prevention
- [x] Restore previous wallpaper operates via history stack and database records
- [x] Wallpaper preview generation accurately renders all 6 desktop styles
- [x] Image integrity validation rejects missing, corrupt, and unsupported formats
- [x] Non-destructive operation preserves user files
- [x] Simulation mode provides clean, deterministic testing across platforms

## Phase 6 — Desktop GUI
**Status: COMPLETE**
Modern dark-themed PySide6 interface (Obsidian palette), responsive `MainWindow` with animated sidebar navigation and status bar, `DashboardView` with library statistics and monitor display, `LibraryView` with wallpaper grid and pagination, `SearchFilterBar` toolbar with live debounced search and filtering, `WallpaperCard` with async `QThread` thumbnail loading and favorite toggling, interactive `ImportProgressDialog`, `WallpaperDetailDialog` with desktop wallpaper setting, and graceful console mode fallback.

## Phase 6 Exit Gate Verification
- [x] Full pytest suite passes (262 / 262 tests pass)
- [x] Phases 0–6 pass together without regressions
- [x] Desktop GUI initializes with PySide6 dark design system
- [x] Main window provides sidebar navigation and responsive view stack
- [x] Dashboard and Library views wire to underlying database and wallpaper services
- [x] Search, filter, category, and resolution controls emit structured queries
- [x] Asynchronous thumbnail loading operates smoothly via worker threads
- [x] Import progress dialog coordinates with ImportService
- [x] Headless Qt testing passes in CI/test environments via offscreen platform

## Phase 7 — Favorites & History
**Status: COMPLETE**
Dedicated `FavoritesView` with live category filtering, multi-criteria sorting, quick random favorite desktop application, card-based favorites grid, and safe clear favorites workflow. Comprehensive `HistoryView` featuring 3 specialized tabs: Desktop Applied history (with relative timestamps, monitor tags, details modal, and instant reapply action), Recently Viewed wallpapers (tracked via `ViewRepository` whenever wallpapers are inspected), and Recently Downloaded/Imported wallpapers. Backend `HistoryService` orchestrating all favorite and history operations with zero UI-database coupling, plus one-click "Restore Previous Wallpaper" workflow.

## Phase 7 Exit Gate Verification
- [x] Full pytest suite passes (286 / 286 tests pass)
- [x] Phases 0–7 pass together without regressions
- [x] FavoritesView provides category filtering, multi-criteria sorting, card grid, and empty state
- [x] Random favorite selection directly applies wallpaper to desktop
- [x] Clear favorites operates safely with user confirmation dialog
- [x] HistoryView provides Desktop Applied, Recently Viewed, and Recently Downloaded tabs
- [x] Applied history displays formatted relative timestamps, monitor metadata, and direct Reapply action
- [x] Restore previous wallpaper re-applies previous background with single click
- [x] Wallpaper inspections record to ViewRepository and populate Recently Viewed
- [x] Foreign key cascade deletion preserves database integrity when wallpapers are removed

## Phase 8 — Automatic Rotation
**Status: COMPLETE**

Automatic rotation uses a dedicated `RotationService`, a single-shot Qt timer, and a worker thread with its own SQLite connection. Rotation preferences are stored in the existing JSON configuration. The Settings sidebar destination now exposes enable/apply, pause, resume, stop, interval, random or library-order selection, category, and minimum-dimension controls. The first rotation occurs after a full interval, and the app does not apply a wallpaper immediately on startup. Rotation events are marked in applied history; failures are retained as unsuccessful rotation events and excluded from applied history, previous-wallpaper restoration, and repeat avoidance.

### Phase 8 Exit Gate Verification
- [x] Rotation disabled by default; enabled-on-start schedules a full interval without an immediate wallpaper change
- [x] Start/configure, pause, resume, stop, repeated-start, cancellation, and shutdown scheduling behavior covered
- [x] Category and minimum width/height filters query library metadata and retain strict criteria at boundaries
- [x] Missing, corrupt, and unsupported image candidates are skipped; empty and unmatched libraries report an error
- [x] Random ordering is injectable for deterministic tests; library-order cycling and immediate-repeat avoidance are covered
- [x] Successful and failed rotation history is distinguishable; failed attempts do not count as applied wallpapers
- [x] Version 2 migration preserves existing applied-history rows and supplies manual/success defaults
- [x] Settings persistence, invalid configuration fallback, GUI controls, history view, and Qt thread delivery covered
- [x] Targeted Phase 8 suite passes (31 / 31; `python -m pytest tests/test_phase8.py`)
- [x] Full pytest suite passes (317 / 317; `python -m pytest`)
- [x] Ruff passes (`python -m ruff check .`)
- [x] Full configured mypy check passes with zero errors (`python -m mypy app`, 46 source files)
- [x] QTest-driven interactive Windows Qt run covered startup, Settings navigation, disabled/enabled status, interval and filters, empty-filter error, start/pause/resume/stop, next-rotation text, Rotation Events tab, and shutdown while active
- [x] Captured and visually inspected the four requested viewport targets; see the viewport record below for actual sizes, constraints, and screenshot paths
- [x] Keyboard focus order includes rotation controls and category filters; QTest coverage and visible focus styling/screenshots were verified
- [x] Native Windows rotation worker applied a temporary library image, recorded one rotation event, then restored the original wallpaper path and style in a separate isolated integration check
- [x] GUI QA used a temporary configuration/database and a simulated wallpaper service; no wallpaper was changed during the interactive run

The first streamed full-suite invocation displayed `317 passed` but its execution session reported exit code 1 without a failure summary. An immediate rerun captured to `%TEMP%\sws-pytest-full.log` displayed `317 passed in 32.47s` and exit code 0. The targeted Phase 8 run also exited 0 (`31 passed in 6.57s`); Ruff and mypy each exited 0.

### Typing baseline and fixes

The first baseline on the reverted checkout reported 21 errors across 12 files, including seven diagnostics from the in-tree revert state. After restoring the original Phase 8 source and documentation from local Git history, a repeatable baseline reported the 14 pre-existing errors across 8 files listed below; none originated in Phase 8. The full outputs are saved outside the repository at `%TEMP%\sws-mypy-baseline.txt` and `%TEMP%\sws-mypy-restored.txt`. The fixes add `types-requests` to the development extras, add narrow types and value narrowing, and correct optional Qt values, variable reuse, callback wiring, and the CLI return path. Mypy strictness and configured error codes were not weakened.

| Baseline location | Error code | Root cause and correction | Origin |
|---|---|---|---|
| `app/sources/wikimedia.py:21`; `app/services/download_service.py:23` | `import-untyped` | Requests lacked stubs; added the `types-requests` development dependency. | Pre-existing |
| `app/sources/wikimedia.py:159` | `no-any-return` | Untyped Requests response made the success value `Any`; stubs now provide the declared response type. | Pre-existing |
| `app/sources/wikimedia.py:322` | `no-any-return` | API mapping values were untyped; narrowed the text field from `Mapping[str, object]`. | Pre-existing |
| `app/utils/image_utils.py:110` | `assignment` | A converted Pillow `Image` reused a variable inferred as `ImageFile`; now uses a separately typed thumbnail. | Pre-existing |
| `app/ui/components/wallpaper_card.py:148` | `method-assign` | A mouse handler was assigned dynamically; replaced it with a typed clickable label and signal. | Pre-existing |
| `app/ui/dashboard_view.py:184, 199–202` | `assignment`, `attr-defined` | A local inferred as `StatCard` was reused for unrelated widgets; gave each widget its own variable. | Pre-existing |
| `app/ui/library_view.py:282` | `union-attr` | `QLayoutItem.widget()` can return `None`; added a guard. | Pre-existing |
| `app/ui/favorites_view.py:243` | `union-attr` | `takeAt()` can return `None`; added a guard before accessing the widget. | Pre-existing |
| `app/main.py:74` | `return` | Fallback flow did not guarantee a return value; made the path explicit. | Pre-existing |

### Interactive GUI viewport record

The capture alternative was a visible Windows Qt platform session driven with `QTest`, with client-window captures from `QWidget.grab()` at 125% display scaling. The screen was 1536×864 and the application minimum was 1024×680. Sidebar labels and active state remained visible; Settings showed the disabled status, interval, selection and dimension controls, category list, and action buttons. At the constrained minimum, action buttons are below the initial fold and are reachable by vertical scrolling. No horizontal overflow or clipped widgets were seen at the achieved client sizes. The QA harness used temporary app data and a simulated wallpaper service; it did not change the desktop wallpaper.

| Requested client size | Actual client size | Screenshot | Result |
|---|---:|---|---|
| 1280×800 | 1280×800 | `%TEMP%\sws_phase8_gui_qa_eux_p3dx\screenshots\settings_1280x800.png` | Sidebar, settings, filters and controls visible; no clipping observed. |
| 1024×768 | 1024×768 | `%TEMP%\sws_phase8_gui_qa_eux_p3dx\screenshots\settings_1024x768.png` | Compact layout remained readable; controls remained reachable. |
| 800×600 | 1024×680 | `%TEMP%\sws_phase8_gui_qa_eux_p3dx\screenshots\settings_800x600.png`; actions after scrolling: `%TEMP%\sws_phase8_gui_qa_eux_p3dx\screenshots\settings_800x600_scrolled.png` | The request was constrained by the app minimum; vertical page scroll exposes the action buttons. |
| 1440×900 | 1440×844 | `%TEMP%\sws_phase8_gui_qa_eux_p3dx\screenshots\settings_1440x900.png` | Height was constrained by the screen work area; layout remained readable with no clipping observed. |

Additional captures in the same temporary folder: `startup.png`, `settings_keyboard_focus.png`, `settings_keyboard_focus_category.png`, `settings_empty_filter_error.png`, `settings_running.png`, `settings_paused.png`, and `history_rotation_events.png`. QTest exercised sidebar navigation and return to Settings, the category and minimum-dimension filters, error messaging, start/pause/resume/stop and next-rotation status, and the Rotation Events tab. Start showed the scheduled next rotation and left history empty before the interval elapsed. Closing with rotation active stopped the scheduler and timer. A dedicated Qt test also covers small-window scrolling, widget navigation, the card thumbnail click signal, and the focus chain.

The Computer Use native-pipe helper remained unavailable; the alternative above used real application widgets, Qt event delivery, and inspected captures, but did not simulate a human using a physical keyboard or mouse. For a physical-input spot check, launch the app in a disposable Windows profile/library, visit Settings, tab through Enable → interval → random → dimensions → categories → actions, verify the focus outline, set a one-minute interval, start then pause/resume/stop rotation before it expires, open History → Rotation Events, then close the app while rotation is active and confirm it exits cleanly. Use an isolated profile/library so this check does not use personal wallpaper files.

The first pytest attempt, before dependency installation, could not collect six test modules because Pillow and PySide6 were absent. After installing the declared development dependencies, the suite completed. The initial migration assertion was updated from schema version 1 to version 2 to reflect the new additive migration; existing assertions and workflows were retained. User wallpaper and style were restored after the separate Windows integration check; the user's library/database were not used by either isolated GUI check.

### Phase 8 Design Notes
- A Qt timer owns the schedule; no Windows service or Task Scheduler job is installed.
- The worker queries a fresh metadata-filtered candidate list and validates candidates as needed, keeping file checks off the UI thread.
- Each worker creates and closes its own database connection. Shutdown stops the timer, requests cancellation before application, and joins the worker.
- Pause state is runtime-only. If rotation remains enabled, restart schedules the next change after a full interval.
- Failed attempts share the existing `wallpaper_history` table via additive `source`, `success`, and `error_message` columns. Applied-history queries filter to successes.
- No files are moved or deleted. No external network calls are made by rotation.

## Phase 9 — Duplicate Manager
**Status: PARTIALLY COMPLETE**

The Duplicate Manager is available from the sidebar on the project's supported Windows 10/11 desktop target. It scans a read-only SQLite snapshot on a background thread, recomputes SHA-256 and 64-bit pHash from current `.jpg`, `.jpeg`, `.png`, and `.webp` files, verifies byte identity for exact groups, and indexes near matches with a BK-tree and connected components. The user-configurable pHash Hamming-distance threshold is inclusive and limited to 0–64. The UI includes exact/near tabs, search, sort, pagination, image metadata, independent compare and preview selections, issue details, and side-by-side comparison.

Cleanup plans require a complete scan, an explicit retained file per selected group, and current file identity, content hash, image decode, and exact-byte checks. Preview runs off the UI thread and reports a plan without changing files or database rows. The actual cleanup button is intentionally disabled: the application has no verified recoverable Recycle Bin or quarantine implementation. Phase 9 remains partial until recoverable cleanup and its failure/recovery behavior are implemented and validated.

No Phase 9 database migration or persistent scan result was added. The scan database connection opens with SQLite `mode=ro` and `query_only`; the database is read in a short snapshot transaction, then closed before image files are processed. Scans make no network requests and report filenames without logging absolute paths.

### Phase 9 Validation Record
- [x] Exact groups are SHA-256 matched and byte-compared; estimated redundant bytes include exact copies only
- [x] Near matches use pHash Hamming distance, an inclusive threshold, a BK-tree, and direct edge scores; scores are not probabilities
- [x] Scan cancellation and file-change checks discard incomplete groups and stale records
- [x] Invalid, missing, unsupported, duplicate-path and unreadable library records are surfaced as issues
- [x] Cleanup preview requires an explicit retained item and revalidates selected files; no file or row is modified
- [x] Read-only database mode rejects writes, performs no migrations, and does not create a missing database
- [x] Sidebar navigation, disabled cleanup state, and compact-window UI are covered by Qt tests
- [x] Targeted Phase 9 tests pass (19 / 19; `python -m pytest tests/test_phase9.py`)
- [x] Ruff passes (`python -m ruff check .`)
- [x] Configured mypy passes with zero errors (`python -m mypy app`, 50 source files)
- [x] Full regression suite passes (336 / 336; `python -m pytest`)
- [x] Windows Qt window was exercised with QTest and inspected captures from a temporary database and image set; no user's library or wallpaper files were used
- [x] Exact and near tabs, comparison dialog roles, scan completion, and the compact scrolled view were captured and inspected at multiple client sizes; see the record below
- [ ] Recoverable Recycle Bin/quarantine cleanup, deletion failure recovery, and their tests remain outstanding
- [ ] Native Recycle Bin or quarantine behavior was not exercised because no cleanup mechanism is implemented and the file action remains disabled

The Computer Use native pipe was unavailable after its retry and reset workflow. The available fallback used the real Windows Qt platform, QTest event delivery, and `QWidget.grab()` captures; this covered the in-app controls and layout but not physical mouse/keyboard use.

### Phase 9 GUI viewport record

Captures are in `%TEMP%\\sws_phase9_gui_qa_1d3a518af9654edc8a04933d50a78347\\screenshots`. The isolated QA library contained three synthetic images (two byte-identical and one re-encoded visual variant) and a temporary SQLite database. The main window minimum is 1024×680.

| Requested client size | Actual client size | Capture | Result |
|---|---:|---|---|
| 1440×820 | 1440×820 | `duplicate_manager_1440x820.png` | Exact group, selection controls, toolbar, and disabled cleanup state fit. |
| 1280×800 | 1280×800 | `duplicate_manager_1280x800.png` | Group browser and actions fit without horizontal clipping. |
| 1024×768 | 1024×768 | `duplicate_manager_1024x768.png` | Compact layout remains readable; duplicate results scroll vertically. |
| 800×600 | 1024×680 | `duplicate_manager_800x600_minimum.png`, `duplicate_manager_minimum_scrolled.png` | Request is constrained by app minimum; the group member choices are reachable by scrolling. |
| Near tab and compare dialog | 1440×820 | `duplicate_manager_near_1440x820.png`, `comparison_dialog_1440x820.png` | Direct pHash score and selected Keep/preview roles are visible. |

The small viewport review found horizontal clipping in the first layout. The toolbar now wraps into separate rows, member choices stack vertically, and the compact result pane scrolls; the revised captures show these controls reachable. No deletion, file movement, database reconciliation, physical-input spot check, or large-library performance benchmark was run. No speed claim is made.

## Development Discipline
Design → Implement → Test → Audit → Document → Commit → Tag → Next Phase

## Source of Truth
When documentation conflicts with implementation, use this order:
1. Current implementation
2. Passing tests
3. Git history
4. Project status
5. README
6. Older planning documents
