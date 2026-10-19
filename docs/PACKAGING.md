# Windows Executable Packaging

## Status and scope

Phase 12 is a **packaging validation track**, not a public release. The application is still `0.7.0-dev`. The default configuration builds an unsigned Windows x64 `onedir` bundle with a windowed GUI. There is no installer, release tag, public download, or signing certificate in this phase.

The Phase 11 decision remains **PARTIALLY COMPLETE** because real wallpaper application, physical-input/screen-reader review, and Windows 10 verification have not been completed. A successful build does not change that decision.

## Runtime contract

| Item | Contract |
|---|---|
| Build host | Windows x64, Python 3.12 virtual environment |
| Application runtime | Python runtime and declared application dependencies are bundled; end users do not need Python installed |
| Entry point | `app/__main__.py`, equivalent to `python -m app`; the project console entry point is `sandy-wallpaper-studio = app.main:main` |
| Version | `APP_VERSION` in `app/constants.py`, checked against `pyproject.toml`; currently `0.7.0-dev` |
| Windows file version | Numeric tuple derived from the product version; development suffix stays in the ProductVersion string |
| GUI / Qt | PySide6, with the Qt Windows platform plug-in included by the PyInstaller Qt hook and checked by the build script |
| Image handling | Pillow, ImageHash, and their declared dependencies; the application uses runtime image validation rather than bundled wallpaper data |
| SQLite | Python's SQLite runtime initializes the existing schema in the user's app-data root on first launch and applies the application's existing migrations to an existing database |
| Writable data | `%USERPROFILE%\Pictures\SandyWallpaperStudio` by default, or the existing `--library` override; this contains settings, `wallpapers.db`, Library, Cache, Temp, Logs, Exports, and Duplicates |
| Bundle directory | Read-only at runtime; user settings, databases, images, caches, exports, and logs are not packaged into the executable directory |
| First launch | Writes default settings, creates the app-data directories and database, runs migrations, seeds default categories, and opens the GUI |
| Network | Wikimedia requests use HTTPS. Image downloads resolve and vet every DNS answer, connect to a pinned public IP, and retain the hostname for TLS SNI/certificate checks and the HTTP Host header. Download proxy environment variables are ignored and proxies are rejected for this security boundary. |
| Branding | The repository has no application `.ico`; the build uses no project icon. The executable is unsigned. |

The app continues to use the same `Config`, schema, database, and local-data behavior when packaged. Do not move or delete an existing profile when installing or replacing a bundle. Existing database migrations remain application behavior and are not changed by packaging.

## Reproduce the Windows build

From a fresh checkout on Windows x64 with Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,packaging]"
.\scripts\build_windows.ps1
```

The packaging extra pins PyInstaller to `6.22.3`; the runtime and Requests/urllib3 constraints are declared in `pyproject.toml`. The build script validates the repository, 64-bit Python 3.12 venv, package/version agreement, CLI entry points, full test suite, Ruff, mypy, Qt plug-ins and PE version resource. It does not upgrade the environment wholesale or run Git cleanup.

The default spec builds an `onedir` application at:

```text
build\phase 12\dist\SandyWallpaperStudio\SandyWallpaperStudio.exe
```

The space in the output path is intentional and is exercised by the smoke test. Keep the executable beside its `_internal` bundle directory; do not copy out the EXE by itself. The generated build folder is ignored by Git. If it already contains output owned by this build script, the next run preserves that folder under a timestamped sibling before creating a new build. Unmarked existing output is left untouched and causes the script to stop.

## Observed local validation build

The 2026-10-19 Windows 11 x64 validation build completed with Python 3.12.10 and PyInstaller 6.22.3. ProductVersion is `0.7.0-dev`; FileVersion is `0.7.0.0`. The EXE is 11,262,095 bytes and its SHA-256 is `AE46FD110514FC4EF8548D0CA6EDC063E24653FFF1F1F15F6EA6DF9E24A3557E`; the full `onedir` bundle is 245,949,415 bytes. Local output is at `build\phase 12\dist\SandyWallpaperStudio\SandyWallpaperStudio.exe`; the ignored build manifest records source HEAD `b30acc26867c01b7ddbaa846b7cc4caebbe178e8` and marks `source_tree_dirty: true` because the finalization changes were not yet committed at build time.

The isolated packaged smoke passed `--version`, runtime validation (PNG metadata, SHA-256, pHash, thumbnail, settings schema, and SQLite integrity), GUI first-run initialization and shutdown, Qt runtime checks, and path-with-spaces/sanitized-PATH checks. This is local Windows 11 evidence only.

## Validate the packaged GUI

The build invokes the GUI smoke procedure. To rerun it manually:

```powershell
.\scripts\validate_packaged_windows.ps1 `
  -BundlePath ".\build\phase 12\dist\SandyWallpaperStudio" `
  -RequirePathWithSpaces
```

The smoke test starts the executable with a sanitized `PATH` that excludes the project venv, from the directory whose name contains a space. It sets `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, and temporary directories to a unique disposable profile; verifies the app version metadata and main-window title; checks first-run settings, directories, log output, and SQLite integrity; and closes the GUI. Before that first-run GUI check, a hidden `--validate-runtime` diagnostic creates only a temporary PNG and cache thumbnail in the isolated profile, then exercises Pillow metadata extraction, SHA-256, ImageHash pHash (including SciPy's DCT path), thumbnail generation, persisted settings schema, and SQLite integrity. It removes only its generated image and thumbnail. The smoke script removes only its marked temporary profile after full success. A failed run preserves its test profile and writes `validation-result.json` for diagnosis. It does not change wallpaper settings, use the real user's data, or make a provider request.

This local smoke test is not a clean-machine test: it still runs on the developer's Windows 11 installation and its system libraries. Clean Windows 10/11 machine or VM acceptance remains **NOT RUN**.

## Manual Windows desktop and accessibility gates

The native wallpaper acceptance script requires the operator to type a confirmation before changing the current desktop. Physical keyboard and Narrator review require a real interactive session. Follow [Windows Manual Acceptance](WINDOWS_ACCEPTANCE.md); neither check is part of the build or CI.

## Distribution boundary

This build is an internal validation artifact. It is not signed and has not been published. Windows may show a SmartScreen or unknown-publisher prompt. Do not describe the build as an installer or a production release. Phase 13 installer work remains out of scope.

## References

- [PyInstaller Windows and operating-mode documentation](https://pyinstaller.org/en/stable/operating-mode.html)
- [PyInstaller spec-file documentation](https://pyinstaller.org/en/stable/spec-files.html)
- [Pinned PyInstaller release](https://github.com/pyinstaller/pyinstaller/releases/tag/v6.22.3)
