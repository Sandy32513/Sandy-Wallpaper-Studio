# Sandy Wallpaper Studio

> Professional 4K / 5K / 8K wallpaper management for Windows 10/11.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-lightgrey)

---

## Features

| Feature | Status |
|---|---|
| Modern PySide6 dark-mode GUI | 🔜 Phase 6 |
| Wikimedia Commons wallpaper source | 🔜 Phase 2 |
| 4K / 5K / 8K resolution filtering | 🔜 Phase 3 |
| SHA-256 exact duplicate detection | 🔜 Phase 3 |
| Perceptual hash near-duplicate detection | 🔜 Phase 3 |
| Smart search with filters | 🔜 Phase 4 |
| 45+ wallpaper categories | 🔜 Phase 4 |
| Import existing wallpaper folders | 🔜 Phase 4 |
| Windows native wallpaper setting | 🔜 Phase 5 |
| Favorites & history | 🔜 Phase 7 |
| Automatic wallpaper rotation | 🔜 Phase 8 |
| Duplicate Manager UI | 🔜 Phase 9 |
| Multi-monitor awareness | 🔜 Phase 5 |
| License & attribution tracking | 🔜 Phase 2 |
| Offline library support | ✅ Phase 0 |
| CLI support | 🔜 Phase 33 |
| PyInstaller packaging → `.exe` | 🔜 Phase 12 |
| Windows installer | 🔜 Phase 13 |

## Requirements

- **OS**: Windows 10 or Windows 11
- **Python**: 3.12 or later
- **Disk**: ~50 MB for app + space for your wallpaper library

## Quick Start

```powershell
# 1 — Clone / navigate to the project
cd sandy-wallpaper-studio

# 2 — Create a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3 — Install dependencies
pip install -r requirements.txt

# 4 — Run the application
python -m app
```

## Project Structure

```
sandy-wallpaper-studio/
├── app/
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration manager
│   ├── constants.py         # Application constants
│   ├── ui/                  # PySide6 GUI (Phase 6+)
│   │   └── components/
│   ├── services/            # Business logic services
│   ├── sources/             # Wallpaper source providers
│   ├── database/            # SQLite layer
│   ├── utils/               # Helpers (logging, hashing, etc.)
│   └── resources/           # Icons, themes
├── tests/                   # pytest test suite
├── scripts/                 # Build & utility scripts
├── docs/                    # Extended documentation
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── README.md
├── CHANGELOG.md
├── LICENSE
└── PRIVACY.md
```

## Architecture

Sandy Wallpaper Studio follows a **layered modular architecture**:

1. **UI Layer** (`app/ui/`) — PySide6 views and components
2. **Service Layer** (`app/services/`) — wallpaper, download, duplicate, rotation
3. **Source Layer** (`app/sources/`) — pluggable wallpaper providers
4. **Data Layer** (`app/database/`) — SQLite with indexed queries
5. **Utilities** (`app/utils/`) — hashing, image validation, logging

## Supported Sources

| Source | API | License |
|---|---|---|
| Wikimedia Commons | Official MediaWiki API | CC-BY-SA / Public Domain |
| *(More planned)* | — | — |

> Only official APIs and explicitly permitted endpoints are used.
> No scraping. No anti-bot bypass.

## License & Attribution

This application tracks **source, author, license, and URL** for every downloaded wallpaper. Attribution can be exported via Settings → Export Attribution.

## Privacy

Sandy Wallpaper Studio collects **no personal data**. There is no analytics, no tracking, and no uploading of local files. Network requests go only to configured wallpaper providers. See [PRIVACY.md](PRIVACY.md).

## Troubleshooting

| Problem | Solution |
|---|---|
| App won't start | Ensure Python 3.12+ and PySide6 are installed |
| No wallpapers found | Check your Internet connection; verify the source API is reachable |
| Duplicate detection slow | Run the Duplicate Manager in batches; large libraries take time |
| High-DPI scaling issues | The app respects Windows scaling — ensure your display settings are correct |

## Contributing

Contributions are welcome. Please open an issue first to discuss changes.

## License

MIT License — see [LICENSE](LICENSE).
