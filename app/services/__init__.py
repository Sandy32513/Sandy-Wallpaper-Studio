"""Sandy Wallpaper Studio — Services package.

Public API:
    DownloadService         - File download orchestrator
    DuplicateService        - Exact and near-duplicate detection
    HistoryService          - Favorites and history workflows
    ImportService           - Smart folder import engine
    LibraryService          - Unified search, filtering, and stats
    MetadataService         - Image metadata extractor
    SourceService           - Image providers coordinator
    WindowsWallpaperService - Windows desktop wallpaper manager
"""

from app.services.download_service import DownloadService
from app.services.duplicate_service import DuplicateService
from app.services.history_service import HistoryService
from app.services.import_service import ImportService
from app.services.library_service import LibraryService
from app.services.metadata_service import MetadataService
from app.services.source_service import SourceService
from app.services.wallpaper_service import WindowsWallpaperService

__all__ = [
    "DownloadService",
    "DuplicateService",
    "HistoryService",
    "ImportService",
    "LibraryService",
    "MetadataService",
    "SourceService",
    "WindowsWallpaperService",
]
