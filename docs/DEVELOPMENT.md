# Development Guide — Sandy Wallpaper Studio

This guide provides instructions for engineers developing, testing, and debugging **Sandy Wallpaper Studio**.

---

## 1. Prerequisites and Environment Setup

- **Python**: 3.12.x or higher (`python --version`)
- **OS**: Windows 10 or Windows 11 recommended (Linux/macOS supported for non-GUI/simulated tests)
- **Git**: 2.30+

### Recommended Setup

```powershell
# 1. Clone repository
git clone https://github.com/Sandy32513/Sandy-Wallpaper-Studio.git
cd Sandy-Wallpaper-Studio

# 2. Create isolated virtual environment
python -m venv .venv

# 3. Activate virtual environment
.\.venv\Scripts\Activate.ps1
# (or execute commands directly with .\.venv\Scripts\python.exe)

# 4. Install dependencies in editable development mode
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

---

## 2. Launching the Application

### Normal GUI Launch
```powershell
python -m app
```

### Debug Logging
Enables verbose DEBUG logging to both the console and `%USERPROFILE%\Pictures\SandyWallpaperStudio\Logs\app.log`:
```powershell
python -m app --debug
```

### Custom Library Path
Override default directory for testing:
```powershell
python -m app --library "C:\TestLibrary"
```

### Version and Help
```powershell
python -m app --version
python -m app --help
```

---

## 3. Testing Workflows

The suite covers Phases 0 through 10. Use the latest test count recorded in [Project Status](PROJECT_STATUS.md); milestone counts change as regression coverage grows.

### Running All Tests
```powershell
python -m pytest -v
```

### Running Specific Milestone Tests
```powershell
python -m pytest tests/test_phase0.py  # Phase 0: Foundation & Config
python -m pytest tests/test_phase1.py  # Phase 1: Database & Migrations
python -m pytest tests/test_phase2.py  # Phase 2: Wikimedia & Downloads
python -m pytest tests/test_phase3.py  # Phase 3: Image Processing & Hashing
python -m pytest tests/test_phase4.py  # Phase 4: Smart Library & Import
python -m pytest tests/test_phase5.py  # Phase 5: Windows Wallpaper Engine
python -m pytest tests/test_phase6.py  # Phase 6: Desktop PySide6 GUI
python -m pytest tests/test_phase7.py  # Phase 7: Favorites & History
python -m pytest tests/test_phase8.py  # Phase 8: Automatic Rotation
python -m pytest tests/test_phase9.py tests/test_phase9_cleanup.py tests/test_phase9_workflow.py  # Phase 9: Duplicate Manager
python -m pytest tests/test_phase10.py  # Phase 10: Settings & Operational Features
```

### Running in Headless Mode (CI Simulation)
PySide6 tests require an offscreen display platform when running without a physical monitor:
```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -v
```

### Test Coverage Reporting
```powershell
python -m pytest --cov=app --cov-report=term-missing
```

---

## 4. Linting and Code Quality

### Ruff Linting
Check code quality against configured standards:
```powershell
python -m ruff check app tests
```

To automatically resolve import ordering and safe fixes:
```powershell
python -m ruff check --fix app tests
```

---

## 5. Database Management & Schema Migrations

The database engine is SQLite with WAL mode enabled.

### Database Location
Default local path:
```
%USERPROFILE%\Pictures\SandyWallpaperStudio\wallpapers.db
```

### Adding a Migration
1. Open `app/database/migrations.py`.
2. Define a new migration function:
   ```python
   def _migration_003_new_feature(cursor: sqlite3.Cursor) -> None:
       cursor.execute("ALTER TABLE ...")
   ```
3. Register the migration in `MIGRATIONS`:
   ```python
   MIGRATIONS: list[tuple[int, str, MigrationFn]] = [
       (1, "Initial schema", _migration_001_initial_schema),
       (3, "New feature description", _migration_003_new_feature),
   ]
   ```
4. All migrations are applied sequentially and idempotently on application startup.

---

## 6. Logging and Diagnostics

Application logs are rotated automatically (5 MB max per file, 3 backups kept):
```
%USERPROFILE%\Pictures\SandyWallpaperStudio\Logs\app.log
```

Log entry format:
```
2026-10-19 01:00:00,123 [INFO] app.main: Library directory structure verified at ...
```
