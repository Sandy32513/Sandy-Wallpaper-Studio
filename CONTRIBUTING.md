# Contributing to Sandy Wallpaper Studio

Thank you for your interest in contributing to **Sandy Wallpaper Studio**! This project is a desktop application built with Python 3.12 and PySide6, designed to manage high-resolution wallpaper libraries on Windows 10 and 11.

---

## 1. Code of Conduct and Principles

- **Respect and Professionalism**: Treat all collaborators and community members with courtesy.
- **Data Safety First**: The core design principle of Sandy Wallpaper Studio is non-destructive operation. Code must never silently delete user files, overwrite user collections, or destroy databases.
- **Privacy by Design**: Never commit private wallpaper files, machine-specific paths, credentials, access tokens, or sensitive user environment data.

---

## 2. Setting Up Your Development Environment

### Prerequisites

- **Operating System**: Windows 10 or Windows 11 (Linux/macOS supported for non-Windows tests using simulation mode)
- **Python**: Version 3.12 or newer (`python --version`)
- **Git**: Version 2.30 or newer

### Local Setup Steps

1. **Clone the repository**:
   ```powershell
   git clone https://github.com/Sandy32513/Sandy-Wallpaper-Studio.git
   cd Sandy-Wallpaper-Studio
   ```

2. **Create and activate a virtual environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   *(If PowerShell execution policy prevents activation, run commands directly through `.\.venv\Scripts\python.exe`)*

3. **Install the project in editable mode with development dependencies**:
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"
   ```

4. **Verify installation**:
   ```powershell
   python -m app --version
   python -m pytest -v
   ```

---

## 3. Development Workflow & Branching Policy

- Always branch from `main`:
  ```powershell
  git checkout main
  git pull origin main
  git checkout -b <type>/<short-description>
  ```
- Use standardized branch prefixes:
  - `feat/` for new features and capabilities
  - `fix/` for bug fixes and error handling
  - `docs/` for documentation updates
  - `chore/` for tooling, configuration, and dependencies
  - `test/` for testing additions and refactoring

- Keep pull requests focused on a single concern. Avoid bundling unrelated refactoring into functional changes.

---

## 4. Architecture and Coding Standards

### Layer Boundaries

- **Presentation (`app/ui/`)**: PySide6 widgets, dialogs, and views. The UI must invoke backend services (`app/services/`) and must **never** perform direct database queries or raw filesystem manipulations.
- **Services (`app/services/`)**: High-level application and business logic orchestrating repositories, image processing, downloads, and wallpaper engine operations.
- **Database (`app/database/`)**: Data models, migrations, and repository classes. SQLite operations must run within transactions and utilize parameters to prevent injection.
- **Sources (`app/sources/`)**: Wallpaper providers conforming to `WallpaperSource`.
- **Utilities (`app/utils/`)**: Pure functions for hashing, filename sanitization, image decoding, and logging.

### Formatting and Linting

We use **Ruff** for linting:
```powershell
python -m ruff check app tests
```

To automatically format imports and fix safe issues:
```powershell
python -m ruff check --fix app tests
```

---

## 5. Testing Requirements

- Every functional change or bugfix must be accompanied by automated tests.
- Tests are located in the `tests/` directory.
- Run the full test suite before submitting a pull request:
  ```powershell
  python -m pytest -v
  ```
- For headless GUI test execution (standard in CI):
  ```powershell
  $env:QT_QPA_PLATFORM = "offscreen"
  python -m pytest tests/test_phase6.py tests/test_phase7.py
  ```

---

## 6. Pull Request Submission Checklist

Before submitting a PR, confirm:

- [ ] All automated tests pass (`python -m pytest -v`).
- [ ] Ruff checks pass with zero errors (`python -m ruff check app tests`).
- [ ] Application entry points operate correctly (`python -m app --help`).
- [ ] Documentation (`README.md`, `CHANGELOG.md`, `docs/`) has been updated to reflect any changes.
- [ ] No temporary files, `.db` files, logs, or secrets are tracked or committed.
- [ ] Changes maintain backwards compatibility with existing databases and configurations.
