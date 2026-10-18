# Sandy Wallpaper Studio — Developer Scripts & Utilities

This directory contains utility and maintenance scripts for developers and maintainers of **Sandy Wallpaper Studio**.

## Guidelines for Utilities in this Directory

1. **Non-Destructive by Default**: Scripts must never modify or delete user libraries, databases, or system settings without explicit flags (such as `--force` or `--apply`) and clear confirmation prompts.
2. **Environment Isolation**: Always use the active virtual environment (`.venv`) when executing utility scripts.
3. **Reproducibility**: Include `--help` documentation and clear logging for every script.

## Categories of Scripts

- **Database Inspection**: Schema dump, migration validation, index integrity verification.
- **Asset Processing**: Icon generation, resolution benchmarking, test wallpaper generation.
- **Packaging & Distribution**: PyInstaller build helpers and installer packaging scripts (Phases 12 & 13).
