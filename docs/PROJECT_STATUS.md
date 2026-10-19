# Project Status — Sandy Wallpaper Studio

**Current development phase: Phase 12 - PACKAGING VALIDATION ONLY; Phase 11 remains PARTIALLY COMPLETE**
**Status date: 2026-10-19**
**Latest full test run: 405 passed / 2 skipped / 0 failed (407 collected; exit 0)**
**Remote main at this follow-up start: `b30acc26867c01b7ddbaa846b7cc4caebbe178e8`**
**Working branch: chore/repository-cleanup**
**Phase 11 starting baseline: 12b755003ae8c462eee3b01b60b8c506e76bb8d5**

This document is the implementation-status reference for the repository. The Phase 11/12 follow-up below supersedes older test counts and the DNS residual finding in the historical Phase 11 record.

Phases 0-10 are complete. Historical Phase 11 results are recorded below. The current finalization follow-up began with `origin/main` and `origin/chore/repository-cleanup` at `b30acc26867c01b7ddbaa846b7cc4caebbe178e8`; work remains on `chore/repository-cleanup`, not `main`. The application version is now `V0.1.0`; earlier 0.7.0-dev build and acceptance records are historical.

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

## Phase 9 - Duplicate Manager
**Status: COMPLETE**

The Duplicate Manager scans a read-only SQLite snapshot on a background thread, recomputes SHA-256 and 64-bit pHash from the current supported image files, byte-compares exact matches, and reports near-match groups using the inclusive 0-64 Hamming-distance threshold. The UI provides exact and near tabs, search and sorting, group/member pagination, explicit Keep and Remove choices, comparison selection, scan issue details, and asynchronous image previews. A completed scan is required before cleanup. Near-match discovery is bounded at 50,000 direct edges; if the cap is reached, the result is marked incomplete and partial near groups are not presented as complete.

Cleanup is Windows-only. The user reviews the exact targets, retained files, full paths, sizes, count, and method before confirming. Each target and retained file is revalidated immediately before use. The service rejects paths outside the configured library, links/reparse points, hard-linked files, changed content or identity, unreadable images, and files that cannot be opened exclusively. It requests the Windows Recycle Bin through IFileOperation and FOFX_RECYCLEONDELETE; it has no permanent-delete fallback. A failed operation stops the remaining targets, cancellation is reported per file, and the UI refreshes the scan after the operation. SQLite wallpaper, favorites, history, and view rows are deliberately retained; a subsequent scan reports the missing path.

No Phase 9 database migration or persistent scan result was added. The scan opens the database with SQLite mode=ro and query_only, reads a snapshot, and closes it before processing image files. Scan and cleanup tests use isolated temporary data and make no network requests.

### Phase 9 Completion Matrix

| Requirement | Implementation | Evidence | Gap or limitation | Test coverage |
|---|---|---|---|---|
| Exact duplicate detection | Recompute SHA-256, then compare file bytes before reporting exact identity; redundant-byte estimate counts exact copies only. | Synthetic scan produced one exact group and the expected byte estimate. | The estimate is informational; database rows are not reconciled during cleanup. | Exact scan, changed-file and byte-comparison tests. |
| Near-match detection | 64-bit pHash, inclusive threshold 0-64, BK-tree candidates, direct pair scores and connected groups. | Synthetic re-encoded fixture appeared in the near results; score help text explains Hamming distance. | Perceptual hashes do not prove visual interchangeability; groups can contain chains. A 50,000-edge cap yields an explicit incomplete result. | Threshold boundary, representative, dense-edge cap, and 64-member star-shape tests. |
| Review and comparison UI | Search, sorting, group/member pagination, explicit Keep/Remove choice, independent comparison selection, issue dialog, asynchronous previews. | Exact, near, empty, issue, comparison, and compact-window captures were inspected. | Main window minimum is 1024x680 logical pixels. | Qt workflow, pagination, comparison, issue, keyboard focus, and navigation tests. |
| Cleanup confirmation | Modal confirmation lists every target and retained file, full path, estimated size, total count, and Recycle Bin method; Cancel is the default action. | Isolated confirmation capture inspected; approval and cancellation paths exercised. | Recycle Bin storage is reclaimed only when the user empties it. | Confirmation content, cancel, and approved injected-recycler tests. |
| File safety | Scope and link checks, hard-link rejection, exclusive-open lock probe, and immediate identity/hash/decode/byte revalidation. | Temporary locked, changed, linked, out-of-scope, and valid targets exercised. | Cleanup is unavailable off Windows; only configured-library targets qualify. | Path-scope, symbolic-link, hard-link, lock, changed-file, and stop-on-failure tests. |
| Database integrity | Cleanup moves files only; wallpaper, favorites, history, and view relationships remain untouched. No Phase 9 migration. | Isolated database reported schema version 2 and zero foreign-key violations after cleanup workflow. | Recycled paths are surfaced as missing by a later scan; restoration/reimport is user-driven. | Row preservation and foreign-key integrity tests. |
| Cancellation and partial failure | Per-file result reporting, cancellation between files, stop remaining operations after a failed item, then rescan. | Worker and workflow paths exercised with temporary fixtures. | The Windows shell owns Recycle Bin presentation and later restore behavior. | Cancel, worker result, partial failure, and stop-on-failure tests. |
| Windows integration and delivery | Native IFileOperation Recycle Bin integration; Ruff/mypy in local validation and CI. | Opt-in Windows round trip passed; its unique temporary item was restored and bytes verified. Ruff, mypy, all tests, and both CLI version checks passed. | No GitHub Actions run for this completion commit is claimed here. | Full regression and focused Phase 9 results below. |

### Phase 9 Validation Record

- [x] Focused Phase 9 suite: 34 passed, 2 skipped (python -m pytest tests/test_phase9.py tests/test_phase9_cleanup.py tests/test_phase9_workflow.py -q). The skips cover optional Windows link/integration conditions; the real Recycle Bin integration was enabled and run separately.
- [x] Full suite: 352 passed, 2 skipped, 0 failed (354 collected; python -m pytest -q).
- [x] Real Windows Recycle Bin round trip: 1 passed (SWS_RUN_WINDOWS_RECYCLE_INTEGRATION=1 python -m pytest tests/test_phase9_cleanup.py::test_windows_recycle_bin_round_trip -q); the synthetic fixture was restored and its bytes verified.
- [x] Ruff: python -m ruff check . passed.
- [x] Mypy: python -m mypy app passed with no issues in 53 source files.
- [x] python -m app --version and sandy-wallpaper-studio --version both report 0.7.0-dev.
- [x] Fresh isolated app startup reported database schema version 2; PRAGMA foreign_key_check returned no rows.
- [x] A synthetic-library scan found one exact group, one near group, and one corrupt-image issue; scan and near-match results completed.
- [x] A fresh main-window workflow navigated all nine sidebar destinations. A Phase 7 regression found during visual review was fixed: stale History empty-state widgets are hidden before removal, with a regression test.
- [x] No user's library, database, wallpaper files, or desktop wallpaper were used or changed. GUI and filesystem integration fixtures were synthetic and temporary.

### Phase 9 GUI review

Captures are in C:\Users\Public\Documents\SandyWallpaperStudio_Phase9_QA_20261019_042122\screenshots. The isolated library held synthetic duplicate/re-encoded images and one corrupt image. The physical screen work area was 1536x864 at 125% scaling. Requested/actual logical main-window sizes were 1440x900/1440x844 (screen work-area limit), 1280x800/1280x800, 1024x768/1024x768, and 800x600/1024x680 (application minimum). The 1280x800 captures include exact and near results, the empty state, and History; other captures include the comparison dialog, cleanup confirmation, issue details, keyboard focus, and Rotation Settings. The result scan reported one exact group, one near group, and one issue. The QA harness removed the temporary database and image library after capture; the screenshots remain outside the repository.

The Computer Use native pipe was unavailable after the documented wait, retry, and runtime reset/retry. The fallback used the visible Windows Qt application, QTest event delivery, and QWidget.grab() captures, which were visually inspected. Physical keyboard/mouse spot checks were not performed. The QA harness used an isolated database and a simulated wallpaper service; it did not change the desktop wallpaper.

## Phase 10 - Settings & Operational Features
**Status: COMPLETE**

Phase 10 adds schema-versioned, per-value validated JSON settings with atomic replacement and no database migration. The Settings page exposes the supported operations and keeps the existing Rotation tab. Source and download factories consume saved controls; imports read the latest recursive-import and thumbnail preferences; wallpaper application uses the saved style. Library integrity checks and thumbnail rebuilds run in a background worker, and rebuild cancellation stops after the current image. Attribution export reads stored database fields only and writes formula-safe UTF-8 CSV atomically with overwrite confirmation in the UI.

Changing the configured library root does not move or reindex image files and does not change the database location. Thumbnail cache names include the selected dimensions and quality; the configured cache budget evicts only app-owned cache entries. Discover, Categories, and Downloads remain placeholder screens; the remote source and download controls configure backend services but do not claim those screens are complete.

### Phase 10 completion matrix

| Requirement | Implementation | Acceptance evidence | Known limit |
|---|---|---|---|
| Library settings | Existing directory validation, cleanup root boundary, default recursive import, background integrity check. | Settings save test; existing import/integrity regression tests; isolated read-only integrity worker. | No automatic reindex or file relocation is performed. |
| Source settings | Wikimedia enablement, timeout, result cap, minimum dimensions through `SourceService.from_config()`. | Factory tests for disablement, timeout, result cap; network boundary is not called. | Wikimedia is the only provider; Discover remains a placeholder. |
| Download limits | Configurable destination, image-size cap, timeout, retries/backoff, and per-instance concurrency gate. Streams to a temporary file, verifies Pillow image integrity, and finalizes exclusively. | Mocked successful, corrupt, oversized, and retry downloads; invalid constructor limits rejected. | The Downloads screen remains a placeholder; no live-provider download was performed. |
| Duplicate threshold | Persisted inclusive pHash Hamming threshold 0-64; scan start snapshots the value. pHash matches are always near candidates; exact scan requires SHA-256 and byte comparison. | Threshold-boundary service test plus Phase 9 exact/near scanner tests. | pHash is not a probability or proof of interchangeable images. |
| Thumbnail controls | Enablement, dimensions, quality, cache budget; versioned cache paths; current cache is used by Dashboard, Library, Favorites, and History cards. Rebuild and cancellation run in a `QThread`. | Dimension/cache/original-preservation tests and isolated rebuild/cancel worker test. | Cache budget evicts old app cache files only; the original image is not resized or changed. |
| Logging settings | Dynamic level/file output/rotation; only application-owned handlers are replaced; console remains active on file failure. | Repeated-setup handler-count and file-failure tests. | `--debug` can override the configured level for that process. |
| Attribution export | UTF-8 CSV from stored fields, formula neutralization, atomic output, explicit overwrite confirmation, incomplete online-row count. | Unicode/formula/overwrite/local-import export tests. | Missing source metadata is reported, never inferred or fetched. |
| User preferences and config migration | Global settings schema v2, independent validation, legacy rotation interval conversion, atomic save rollback. Existing rotation control is retained. | Invalid-value fallback, atomic-write failure, snapshot, and integrated UI persistence tests. | Old no-op keys remain readable but are documented as legacy, not working controls. |

### Phase 10 validation record

- Focused Phase 10 tests: 25 passed (`python -m pytest tests/test_phase10.py -q`, exit code 0).
- Phase 8 + Phase 10 focused regression: 56 passed (`python -m pytest tests/test_phase8.py tests/test_phase10.py -q`, exit code 0).
- Full regression: 377 passed, 2 skipped, 0 failed (379 collected; `python -m pytest -q`, exit code 0). The skips were the symlink-safety case (unavailable under this profile) and the opt-in Windows Recycle Bin integration.
- During finalization, an earlier full run printed all tests as passing but Windows returned `0xC0000409` during process shutdown. Isolation traced it to changing the rotation Stop checkbox before a simulated settings-save failure. The control now changes only after persistence succeeds; the final full run exited 0.
- Ruff: passed (`python -m ruff check .`, exit code 0).
- Mypy: passed with no issues in 55 source files (`python -m mypy app`, exit code 0).
- Whitespace/conflict-marker check: passed (`git diff --check`, exit code 0; Git printed informational CRLF-to-LF notices for existing Windows-format files).
- Startup smoke: `python -m app --library <temporary-directory>` completed with exit code 0 using an isolated temporary data root and a 1.2-second Qt auto-close hook. It created only the temporary settings and database, initialized the GUI, and logged no GUI launch failure. The first hook variant had an incorrect Python binding and was rejected by the smoke assertion; the corrected hook passed. The temporary root was removed afterward.
- README link check: 65 links checked; no missing local files or heading anchors.
- No unit test made a network request. Download and source boundaries use mocked responses; the README screenshot uses synthetic data and public placeholder paths.
- Windows Qt captures were saved under `docs/images/phase10/` and visually inspected. At 125% Windows scaling, requested and achieved logical window sizes and rendered PNG sizes were:

  | Requested logical | Achieved logical | PNG dimensions |
  |---|---|---|
  | 1280 x 800 | 1280 x 800 | 1600 x 1000 |
  | 1024 x 768 | 1024 x 768 | 1280 x 960 |
  | 800 x 600 | 800 x 600 | 1000 x 750 |
  | 1440 x 900 | 1440 x 900 | 1800 x 1125 |

  These are Qt widget captures, not physical keyboard/mouse testing. The functional Qt tests exercised Settings tab navigation, save, cancel, invalid-path recovery, reset confirmation, and preservation of rotation preferences.
- No production database, user wallpaper, credentials, personal logs, or live desktop wallpaper were used for Phase 10 tests or captures.

## Phase 11 - Release Hardening
**Status: PARTIALLY COMPLETE — detailed gate evidence is in [Phase 11 Acceptance](PHASE11_ACCEPTANCE.md).**

Phase 11 established an application-wide 40,000,000-pixel image ceiling and applied it before image decoding in the Pillow validation/hash/thumbnail paths and the Qt detail, card, and comparison preview paths. The ceiling accepts 8192x4320 (8K UHD/DCI) dimensions. In the finalization follow-up, downloads require direct HTTPS on port 443, reject credentials, known local hostnames and non-global IP literals, and do not follow redirects. Every DNS answer is vetted and the socket connects to the pinned public address; the original hostname remains the TLS SNI/certificate identity and HTTP Host. Proxy environment settings are ignored, and explicit proxies are rejected.

Windows-rendered screenshots exposed clipping in the Library toolbar/grid, Favorites header/grid, Dashboard cards/actions, and detail dialog. These layouts now adapt to available width; detail actions wrap, its preview scales to the viewport, and image dimensions are checked before Qt decodes them. Screenshots were captured and inspected from an isolated synthetic library and are retained only in pytest's temporary folder.

### Phase 11 historical validation record (before finalization follow-up)

- Baseline on the unchanged checkout: 377 passed, 2 skipped (379 collected); Ruff and mypy passed.
- A preliminary `python -m pytest` resolved to system Python instead of the project venv and was intentionally interrupted during collection (exit 1); it was not treated as a failed test run. The completed venv run below is the authoritative result.
- Latest full suite: 387 passed, 2 skipped, 0 failed (389 collected; 53.83 seconds; exit code 0; project `.venv`, Python 3.12.10, pytest 9.1.1; PowerShell set `$env:QT_QPA_PLATFORM = "offscreen"`, then run `python -m pytest`). The symlink-safety test skipped because this Windows profile disallows symlink creation; the real Recycle Bin round-trip is opt-in and was skipped in the full suite. A focused cleanup run passed 11 tests and confirmed both skip reasons (exit 0).
- The project-venv opt-in Recycle Bin test skipped because `pywin32` is not installed there. Re-running the isolated test with system Python 3.12.10, pytest 9.0.3 and available `pywin32` passed (1 passed, exit 0); the unique temporary target was restored and its bytes verified.
- Focused Phase 11 regression and Windows Qt capture tests: 10 passed. The tests reject oversized headers before decode, enforce direct HTTPS/no redirects, verify partial-download cleanup, exercise sidebar keyboard activation and accessible names, and assert that Library/Favorites have no horizontal scroll at 800x600.
- Windows-rendered Qt capture sizes requested/achieved: 1280x800 / 1280x800; 1024x768 / 1024x768; 800x600 / 800x600; 1440x900 / 1440x844 (the screen work area constrained the last height). Dialog captures include detail (800x592 client), import progress, comparison, and Recycle Bin confirmation. The QTest path activates Settings by Space and checks rotation control accessible names. Physical mouse/keyboard spot checks and screen-reader testing were unavailable.
- Large-library and performance measurements: 100, 500, 1,000 and 5,000 synthetic records completed with correctness checks and exit code 0. At 5,000, the latest scan took 105.946 seconds, processed 47.19 records/second, peaked at 239.81 MiB working set, and returned from cancellation in 8.3 ms. Prior single-run results varied; no performance SLA or optimization claim is made. See [Phase 11 Performance](PHASE11_PERFORMANCE.md).
- Platform: Microsoft Windows 11 Enterprise, build 26300, Python 3.12.10 x64. The app was launched against temporary test data. No live wallpaper change, live provider request, or real user library operation was performed. Native wallpaper application was therefore not revalidated in this phase. The optional Recycle Bin case skipped in the venv full suite, but its separate system-Python round-trip passed and restored the synthetic target.
- Ruff 0.17.0 (`python -m ruff check .`) passed; mypy 2.4.0 (`python -m mypy app`) passed for 55 application source files. `.venv\Scripts\pip-audit.exe --local` reported no known advisories in installed project dependencies; the local project distribution is not on PyPI and could not be audited as a published package. A separate earlier global-Python audit reported advisories in unrelated global-environment packages; those packages were not modified.
- `git diff --check` passed. README/docs link validation checked 58 local Markdown links and heading anchors; all resolved. Both CLI version entry points still report `0.7.0-dev`.
- Phase 11 implementation commit `698f58c2ae19d2efe04d68cc50d852ee59606522` and documentation commit `b2e8474faa26aabab287d222c437af46cbbeaa7a` are present on `origin/main` and the development branch. [GitHub Actions run 39184857853](https://github.com/Sandy32513/Sandy-Wallpaper-Studio/actions/runs/39184857853) passed for the exact main SHA `b2e8474faa26aabab287d222c437af46cbbeaa7a` on Windows/Python 3.12 at that checkpoint. Later main history reached `b30acc26867c01b7ddbaa846b7cc4caebbe178e8`, the baseline for the Phase 11/12 follow-up. The follow-up work remains on `chore/repository-cleanup`; it does not update `main`. No pull request was created. These changes did not create a versioned release, tag, or installer.

### Security and release limitations

- **Low — manual desktop/platform evidence:** no native wallpaper change or physical-input/screen-reader run was performed; Windows 10 and clean-machine acceptance remain unverified. At this Phase 11 checkpoint the app was version `0.7.0-dev`; the current `V0.1.0` build is still not a public release.

## Phase 12 — Windows executable packaging
**Status: PARTIALLY COMPLETE — local packaging validation only.** The reproducible PyInstaller 6.22.3 Windows x64 `onedir` bundle is built to an ignored output path and smoke-tested on Windows 11 in a temporary profile whose path contains spaces. The packaged smoke imports a generated supported PNG through `ImportService`, then uses a fresh process to verify the image record/file, metadata, SHA-256, pHash/SciPy, generated thumbnail, saved setting, and SQLite integrity. It also checks version resources, Qt GUI startup/title/shutdown, sanitized PATH, first-run files, and temporary-profile cleanup. Exact artifact size, package versions, and smoke manifest are recorded in [Packaging](PACKAGING.md).

No installer, signing, release tag, or public distribution was created. Clean Windows 10/11 machine or VM acceptance remains **NOT RUN**. Native wallpaper, physical-input, and Narrator checks remain **NOT RUN** as recorded in [Windows Manual Acceptance](WINDOWS_ACCEPTANCE.md).

## Phase 12 packaging follow-up — 2026-10-19

The packaged import and fresh-process persistence checks are in commit `7f1ccbc674a66cdbd0d0b9306e50b4253f285197`; the evidence/documentation update is commit `30c02804daf5e0a6910f157eeb466f7383c26d46`. Both were pushed to `origin/chore/repository-cleanup`. [GitHub Actions run 39292154877](https://github.com/Sandy32513/Sandy-Wallpaper-Studio/actions/runs/39292154877) passed for the exact `30c02804daf5e0a6910f157eeb466f7383c26d46` SHA on Windows/Python 3.12: 406 passed, 1 skipped; entry points, Ruff, mypy, and pytest all passed. `origin/main` remains at `b30acc26867c01b7ddbaa846b7cc4caebbe178e8`; no Phase 12 changes were pushed there.

## Version identifier update — 2026-10-19

The application and package version sources are synchronized to `V0.1.0`. This updates the application version identifier; it does not create a Git tag or publish a release. The existing `0.7.0-dev` executable record in [Packaging](PACKAGING.md) predates the version change.

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
