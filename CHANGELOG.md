# Changelog

All notable changes to Sandy Wallpaper Studio are documented here.

## Unreleased
Future work is tracked in docs/ROADMAP.md.

## Phase 3 — Image Validation, Hashing & Duplicate Detection
**Commit:** 6434e8c6b71a9fdcca4612a107e1c605a429345c

### Added
- SHA-256 hashing
- pHash perceptual hashing
- dHash and aHash utilities
- Hamming distance and similarity percentage
- exact duplicate detection
- near-duplicate detection
- configurable pHash threshold
- image integrity and format validation
- full pixel decode validation
- resolution and aspect-ratio classification
- thumbnail generation
- download-time SHA-256
- download size protection

### Design rule
Duplicate detection is non-destructive. Detection does not automatically delete files.

## Phase 2 — Wikimedia Source & Download Service
**Commit:** 4beef3af37136cf09d9d10f9c394bdf2631bc576

### Added
- Wikimedia Commons provider
- official MediaWiki API integration
- wallpaper search
- minimum-resolution filtering
- source metadata and license capture
- source URLs and image URLs
- streaming downloads
- retries and exponential backoff
- cancellation callback
- temporary-file download flow
- HTTP and content-type validation
- filename sanitization

## Phase 1 — SQLite Database Layer
**Commit:** c56b7f0f60f5f3434024d475cf3ea72378755f0f

### Added
- SQLite database with WAL mode
- foreign-key enforcement
- migration tracking
- Wallpaper, Category, DownloadRecord and WallpaperHistory models
- repository layer
- CRUD, smart search, pagination and statistics
- 44 default categories
- custom category support
- database/index tests

## Phase 0 — Project Foundation
**Commit:** 9702d2ddd358888f8a922cd1885d0b5c502dea06

### Added
- initial architecture
- Python package structure
- pyproject.toml
- requirements.txt
- configuration manager
- constants
- logging
- main entry point
- python -m app support
- CLI argument parsing
- Git ignore rules
- README, CHANGELOG, LICENSE and PRIVACY
- Phase 0 tests

## Versioning Policy
The package metadata currently reports version 1.0.0. Development phase milestones are tracked separately so implementation progress is not confused with a production release.

Future production releases use semantic versioning: MAJOR.MINOR.PATCH.