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

# Phase 4 — Smart Library
**NEXT**

### Objective
Build a complete local wallpaper library workflow using the existing database and image-processing services.

### Scope
- import existing folders
- recursive image discovery
- file validation during import
- metadata extraction
- SHA-256 and pHash indexing
- exact and near duplicate detection
- category assignment
- search
- filtering
- pagination
- statistics
- import history
- error reporting

### Exit gate
Automated tests pass, earlier phases remain intact, imported files are validated, duplicates are identified without automatic deletion, database records remain consistent and documentation is updated.

# Phase 5 — Windows Wallpaper Engine
Set selected wallpaper, random wallpaper, preview, restore previous wallpaper, multi-monitor awareness and monitor-specific selection.

# Phase 6 — Desktop GUI
Build the PySide6 desktop interface over tested services. Planned areas: dashboard, library, search, filters, preview, categories, downloads, favorites, duplicate manager, settings and history.

# Phase 7 — Favorites & History
Favorites, recently viewed, recently downloaded, recently applied, filtering and restore/reapply workflows.

# Phase 8 — Automatic Rotation
Scheduled rotation, interval configuration, category/resolution-aware rotation, random rotation, pause/resume and rotation history.

# Phase 9 — Duplicate Manager
Exact duplicate groups, near-duplicate groups, similarity display, side-by-side comparison, user-confirmed cleanup and safe deletion/recycle-bin workflow.

# Phase 10 — Settings & Operational Features
Library settings, source settings, download limits, duplicate thresholds, thumbnail settings, logging settings, attribution export and preferences.

# Phase 11 — Release Hardening
Regression testing, performance testing, large-library testing, error recovery, security review, accessibility review, Windows compatibility and documentation audit.

# Phase 12 — Executable Packaging
PyInstaller build, Windows executable, version metadata, build validation and clean-machine testing.

# Phase 13 — Windows Installer
Installer, uninstaller, shortcuts, application-data handling, upgrade path, clean installation testing and release documentation.

## Milestone Rule
A phase is not complete because code exists. Completion requires implementation + automated tests + manual QA + documentation + Git commit + milestone tag.
