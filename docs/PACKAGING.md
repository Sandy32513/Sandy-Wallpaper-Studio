# Windows Executable Packaging

## Status and scope

Phase 12 is a **packaging validation track**, not a public release. The current source and latest locally built version is `V1.0.0`. The default configuration builds an unsigned Windows x64 `onedir` bundle with a windowed GUI. There is no installer, public download, or signing certificate; clean-machine acceptance remains open.

The Phase 11 decision remains **PARTIALLY COMPLETE** because real wallpaper application, physical-input/screen-reader review, and Windows 10 verification have not been completed. A successful build does not change that decision.

## Runtime contract

| Item | Contract |
|---|---|
| Build host | Windows x64, Python 3.12 virtual environment |
| Application runtime | Python runtime and declared application dependencies are bundled; end users do not need Python installed |
| Entry point | `app/__main__.py`, equivalent to `python -m app`; the project console entry point is `sandy-wallpaper-studio = app.main:main` |
| Version | `APP_VERSION` in `app/constants.py` and `pyproject.toml` are `V1.0.0`; setuptools normalizes package metadata to `1.0.0` |
| Windows file version | The build script derives the numeric tuple (`1.0.0.0`); the validated bundle reports ProductVersion `V1.0.0`. |
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

The packaging extra pins PyInstaller to `6.22.3`; the runtime and Requests/urllib3 constraints are declared in `pyproject.toml`. The build script validates the repository, 64-bit Python 3.12 venv, application/normalized distribution version agreement, CLI entry points, full test suite, Ruff, mypy, Qt plug-ins, PE version resource, and executable SHA-256. It does not upgrade the environment wholesale or run Git cleanup.

The default spec builds an `onedir` application at:

```text
build\phase 12\dist\SandyWallpaperStudio\SandyWallpaperStudio.exe
```

The space in the output path is intentional and is exercised by the smoke test. Keep the executable beside its `_internal` bundle directory; do not copy out the EXE by itself. The generated build folder is ignored by Git. If it already contains output owned by this build script, the next run preserves that folder under a timestamped sibling before creating a new build. Unmarked existing output is left untouched and causes the script to stop.

## Previous local validation build (`0.7.0-dev`)

The 2026-10-19 Windows 11 x64 validation build completed with Python 3.12.10 and PyInstaller 6.22.3 from clean source commit `7f1ccbc674a66cdbd0d0b9306e50b4253f285197`. ProductVersion is `0.7.0-dev`; FileVersion is `0.7.0.0`. The EXE is 11,263,152 bytes and its SHA-256 is `EE77C3AECDE0ACCC2E52454FA1F4B0393A27C1B7787A0DB7E172D3D208FAE339`; the full `onedir` bundle is 245,950,472 bytes. Local output is at `build\phase 12\dist\SandyWallpaperStudio\SandyWallpaperStudio.exe`; the ignored build manifest records `source_tree_dirty: false`.

The isolated packaged smoke passed `--version`, a supported PNG import through `ImportService`, and a second process that reopened the database and settings and verified the imported file, metadata, SHA-256, pHash, thumbnail, persisted theme, and SQLite integrity. The GUI then opened and closed with that record in its isolated profile. The smoke also checked Qt runtime files, version resources, a path containing spaces, and a sanitized `PATH` without the project venv. The build manifest and `validation-result.json` record the local run. This is local Windows 11 evidence only.

## Previous `V0.1.0` validation build

The 2026-10-19 Windows 11 x64 rebuild used Python 3.12.10 and PyInstaller 6.22.3 from clean source commit `57907841f7d23ec1d97e8d7559584ca429abe7a6`. ProductVersion is `V0.1.0`; FileVersion is `0.1.0.0`. The EXE is 11,263,131 bytes with SHA-256 `7280EA3B4C45E508F536595BA91A36F6C7DDBDB08C05CDFDBC3A2DBB9F33EB05`; the full `onedir` bundle is 245,950,451 bytes. The ignored build manifest records `source_tree_dirty: false`.

The `V0.1.0` isolated smoke passed `--version`, `ImportService` PNG import, fresh-process settings and database verification, GUI startup/shutdown, path-with-spaces and sanitized-PATH checks. Its manifest reports `PASS`, SQLite integrity `ok`, and the window title `Sandy Wallpaper Studio — V0.1.0`. It remains historical local validation output, not a public release.

## Current `V1.0.0` validation build

Built on 2026-10-19 on Windows 11 Enterprise build 26300 with 64-bit Python 3.12.10 and pinned PyInstaller 6.22.3. The clean source commit was `e585a874499ac8b533201fda7e8746d5fbf5dda4`; the build manifest reports `source_tree_dirty: false`. The command was `.\scripts\build_windows.ps1 -PythonPath "$PWD\.venv\Scripts\python.exe" -SkipDependencyInstall`; it exited 0 after the full pytest suite, Ruff, mypy, PyInstaller, version-resource checks, and isolated package smoke.

ProductVersion is `V1.0.0`; FileVersion is `1.0.0.0`. The executable is 11,263,131 bytes with SHA-256 `1D0676E8B152A03D76E9E1D4541004B4C81BC0ADB21F7D21532D4951444E6320`; the full onedir bundle is 245,950,451 bytes. It is at `build\phase 12\dist\SandyWallpaperStudio\SandyWallpaperStudio.exe` with the required `_internal` directory beside it.

The validator reports `PASS`: `--version`, version resources, an `ImportService` PNG import, image metadata, SHA-256, pHash, thumbnail generation, fresh-process settings/database persistence, SQLite integrity `ok`, Qt startup and clean shutdown all succeeded. It ran from a path with spaces and with a sanitized `PATH` in a uniquely isolated temporary profile; the profile was removed after success. The local executable is unsigned validation output only. This procedure is not a separate clean-machine or Windows 10 test.

## Validate the packaged GUI

The build invokes the GUI smoke procedure. To rerun it manually:

```powershell
.\scripts\validate_packaged_windows.ps1 `
  -BundlePath ".\build\phase 12\dist\SandyWallpaperStudio" `
  -RequirePathWithSpaces
```

The smoke test starts the executable with a sanitized `PATH` that excludes the project venv, from the directory whose name contains a space. It sets `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, and temporary directories to a unique disposable profile. A hidden `--prepare-runtime-check` command creates a PNG there, imports it through `ImportService`, and saves a test theme setting. A separate `--validate-runtime` process reloads settings and the database and checks the saved value, imported record and file, Pillow metadata, SHA-256, ImageHash pHash (including SciPy's DCT path), generated thumbnail, and SQLite integrity. The script then launches the GUI, checks its title and first-run files/log, verifies the test setting remains saved, and closes the window. On full success, the script removes only its marked temporary profile; a failed run preserves that profile and writes `validation-result.json` for diagnosis. It does not apply a wallpaper, use the real user's data, or make a provider request.

This local smoke test is not a clean-machine test: it still runs on the developer's Windows 11 installation and its system libraries. Clean Windows 10/11 machine or VM acceptance remains **NOT RUN**.

## Manual Windows desktop and accessibility gates

The native wallpaper acceptance script requires the operator to type a confirmation before changing the current desktop. Physical keyboard and Narrator review require a real interactive session. Follow [Windows Manual Acceptance](WINDOWS_ACCEPTANCE.md); neither check is part of the build or CI.

## Distribution boundary

This build is an internal validation artifact. It is not signed and has not been published. Windows may show a SmartScreen or unknown-publisher prompt. Do not describe the build as an installer or a production release. Phase 13 installer work remains out of scope.

## References

- [PyInstaller Windows and operating-mode documentation](https://pyinstaller.org/en/stable/operating-mode.html)
- [PyInstaller spec-file documentation](https://pyinstaller.org/en/stable/spec-files.html)
- [Pinned PyInstaller release](https://github.com/pyinstaller/pyinstaller/releases/tag/v6.22.3)
