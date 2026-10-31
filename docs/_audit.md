# Repo Audit — Sandy Wallpaper Studio

**Branch:** `chore/repo-polish` | **Date:** 2026-10-31

## Stack

| Item | Value |
|---|---|
| Language | Python 3.12 |
| GUI | PySide6 6.6+ |
| Build backend | setuptools 68+ |
| Version | V1.0.0 (verified: constants.py + pyproject.toml match) |
| DB | SQLite WAL + FK enforcement |
| OS target | Windows 10 / Windows 11 |
| Entry points | python -m app; sandy-wallpaper-studio console script |
| Lint | Ruff 0.3+ |
| Types | mypy 1.8+ |
| Tests | pytest 8+, 21 files, phases 0-12 |
| CI | .github/workflows/tests.yml, Windows/Python 3.12 |

## Key Verified Facts

1. Categories screen EXISTS (app/ui/categories_view.py, 19 KB, registered in main_window.py line 192)
2. Discover and Downloads are PlaceholderView (main_window.py lines 240-245)
3. Version V1.0.0 matches in constants.py and pyproject.toml
4. No installer (Phase 13, planned)
5. No tracked build outputs, .env, or secrets found
6. Wikimedia is public/unauthenticated API - no secrets needed

## Missing Files to Create

- .github/ISSUE_TEMPLATE/bug_report.md
- .github/ISSUE_TEMPLATE/feature_request.md
- .github/PULL_REQUEST_TEMPLATE.md
- .github/CODEOWNERS
- .github/dependabot.yml
- CODE_OF_CONDUCT.md
- SECURITY.md
- docs/assets/ (hero image placeholder)

## CI Gaps

- tests.yml does not trigger on chore/repo-polish branch

## Secrets Scan

CLEAN - no tracked .env, no key/token patterns in filenames or source.
