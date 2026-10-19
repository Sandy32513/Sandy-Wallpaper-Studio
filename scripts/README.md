# Developer Scripts

This directory contains the repository's current benchmark, Windows packaging, and manual acceptance scripts.

| Script | Purpose | Data and safety boundary |
|---|---|---|
| `phase11_benchmark.py` | Runs duplicate-scan measurements against synthetic, temporary libraries. | Does not read or modify the user's wallpaper library. |
| `build_windows.ps1` | Builds and validates an unsigned Windows x64 PyInstaller `onedir` bundle. | Uses a marked `build/phase 12` directory; preserves an existing script-owned output under a timestamped sibling before rebuilding. |
| `validate_packaged_windows.ps1` | Exercises the packaged executable with a temporary profile, path with spaces, and sanitized process `PATH`. | Deletes only its uniquely marked temporary profile after a successful run; preserves it and diagnostics after failure. |
| `manual_wallpaper_acceptance.py` | Opt-in check of the real Windows wallpaper API and restoration path. | Temporarily changes the active desktop wallpaper. Run only after the desktop user explicitly approves and confirms the prompt. |

There is no installer script in this repository. Phase 13 installer work remains planned and out of scope for Phase 12 packaging validation. See [Packaging](../docs/PACKAGING.md) and [Manual Windows Acceptance](../docs/WINDOWS_ACCEPTANCE.md) for exact procedures.
