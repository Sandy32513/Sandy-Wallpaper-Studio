# Project Status — Sandy Wallpaper Studio

**Current development phase: Phase 3 — Complete**  
**Status date: 2026-10-02**

This document is the implementation-status reference for the repository.

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

## Phase 3 Exit Gate
Before Phase 4 is treated as released, verify:
- full pytest suite passes
- Phase 0–3 tests pass together
- database initialization has no regression
- Wikimedia search and download behavior has no regression
- invalid images are rejected
- oversized downloads are rejected
- hashes are deterministic
- duplicate detection does not delete files
- thumbnails are generated
- documentation matches implementation
- a Git milestone tag is created

## Phase 4 Entry Point
Phase 4 turns the existing database, metadata, hashing and download primitives into a complete local library workflow.

Primary objective: **Import, index, search, filter and manage a local wallpaper library without depending on the future GUI.**

Planned capabilities: existing-folder import, recursive discovery, metadata indexing, duplicate-aware import, search, filtering, category assignment, resolution filtering, aspect-ratio filtering, source/license filtering, pagination, statistics and Phase 4 tests.

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

Documentation must be updated whenever implementation changes.