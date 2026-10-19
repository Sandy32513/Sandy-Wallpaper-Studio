# Roadmap — Sandy Wallpaper Studio

The roadmap is sequential. Each phase must pass its validation gate before the next phase begins.

## Phase 0 — Foundation
**Complete**
Configuration, logging, package structure, CLI entry point and development foundation.

## Phase 1 — Database
**Complete**
SQLite schema, migrations, repositories, models, indexes and categories.

## Phase 2 — Source & Download
**Complete**
Wikimedia Commons integration, metadata retrieval and safe downloading.

## Phase 3 — Image Intelligence
**Complete**
Validation, SHA-256, perceptual hashing, duplicate detection and thumbnails.

## Phase 4 — Smart Library
**Complete**
Import existing folders, recursive/flat discovery, metadata indexing, duplicate-aware import, search, filtering, pagination and library statistics.

## Phase 5 — Windows Wallpaper Engine
**Complete**
Native Windows wallpaper setting via `SystemParametersInfoW` & registry styles, multi-monitor detection & orientation awareness, selected wallpaper application with database usage updates, random wallpaper with filters and repeat avoidance, previous wallpaper restoration, multi-style preview generation, and history tracking.

## Phase 6 — Desktop GUI
**Complete**
Professional dark-themed PySide6 desktop interface connecting directly to tested backend services. Responsive main window, animated sidebar, dashboard view, library grid view with pagination, debounced search & filter bar, async thumbnail loading wallpaper cards, import progress dialog, and detail dialog with wallpaper application.

## Phase 7 — Favorites & History
**Complete**
Favorites management with category filtering, sorting, and random favorite desktop application; Desktop Applied history timeline with relative timestamps, monitor tags, and direct reapply action; Recently Viewed tracking and Recently Downloaded/Imported views; backend `HistoryService` and single-click "Restore Previous Wallpaper" workflow.

# Phase 8 — Automatic Rotation
**COMPLETE**
In-process Qt scheduling, interval configuration, category/resolution-aware filtering, random or library-order rotation, pause/resume, and audited rotation events are implemented. The 31-test Phase 8 suite and 317-test full suite pass; Ruff and configured mypy pass. Windows Qt interaction and visually inspected captures cover the requested viewport targets subject to the application minimum and screen work area. See [Project Status](PROJECT_STATUS.md) for test results, screenshot paths, and QA limitations.

# Phase 9 - Duplicate Manager
**COMPLETE**
Read-only exact and near-match scans, explicit retained-file and cleanup-target selection, comparison, bounded near-match reporting, and confirmed Windows Recycle Bin cleanup are implemented. Cleanup revalidates every target, has no permanent-delete fallback, stops on failures, and preserves database rows. Focused tests, the full regression suite, Ruff, mypy, a real temporary-file Recycle Bin round trip, and isolated Windows GUI review passed. See [Project Status](PROJECT_STATUS.md) for detailed evidence and limitations.

# Phase 10 — Settings & Operational Features
**COMPLETE**
Validated, atomic JSON preferences; operational Settings tabs for library/import, Wikimedia, downloads, duplicate thresholds, thumbnails, logging, display style, and rotation; background integrity and cancellable thumbnail maintenance; safe attribution CSV export. Phase 10 acceptance and regression evidence are recorded in [Project Status](PROJECT_STATUS.md), and the settings schema is documented in [Configuration](CONFIGURATION.md).

# Phase 11 — Release Hardening
**PARTIALLY COMPLETE — evidence and remaining limitations are recorded in [Phase 11 Acceptance](PHASE11_ACCEPTANCE.md) and [Project Status](PROJECT_STATUS.md).**

Regression, synthetic scale, error-path, dependency, and Windows-rendered Qt checks have been run. The Phase 11 commits are present on `origin/main` and `origin/chore/repository-cleanup`, but this is not a versioned product release. The application remains `0.7.0-dev`; DNS address pinning, native wallpaper application, and screen-reader/physical-input review remain unverified in the current environment. The isolated Recycle Bin round-trip passed with a temporary file under system Python; the project venv lacks the optional `pywin32` helper.

# Phase 12 — Executable Packaging
PyInstaller build, Windows executable, version metadata, build validation and clean-machine testing.

# Phase 13 — Windows Installer
Installer, uninstaller, shortcuts, application-data handling, upgrade path, clean installation testing and release documentation.

## Milestone Rule
A phase is not complete because code exists. Completion requires implementation + automated tests + manual QA + documentation + Git commit + milestone tag.
