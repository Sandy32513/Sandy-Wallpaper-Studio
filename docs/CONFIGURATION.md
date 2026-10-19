# Configuration

Sandy Wallpaper Studio stores user preferences in `settings.json` under the application data root. By default the root is `%USERPROFILE%\Pictures\SandyWallpaperStudio`; `python -m app --library <folder>` selects a different data root. The Settings page's **Library root** is a separate value: it defines the boundary used by duplicate cleanup and does not move images, reindex database rows, or change the database path.

Settings are global to the application. They are not per-library profiles. JSON is written through a temporary file in the same directory and atomically replaced. A malformed file falls back to defaults; an invalid individual value is ignored while valid settings are retained. Unknown keys are ignored. The current settings schema is version 2. Older files without a schema version are accepted; legacy human-readable rotation intervals are migrated to minutes when they can be parsed. Phase 11 requires no settings or SQLite migration.

## Settings page

| Page | Setting | Default | Validation and effect |
|---|---|---:|---|
| Library | Library root | `<data root>\Library` | Must be an existing directory when saved. Defines the guarded cleanup boundary; changing it never moves or reindexes files. |
| Library | Include subfolders by default | Off | Boolean. Passed to the existing folder import worker; the dialog can still change it for one import. |
| Sources | Wikimedia Commons | Enabled | The only implemented online provider. Disabling it leaves local library, favorites, history, and rotation available offline. |
| Sources | Results per search | 20 | Integer 1-50; caps the source service result request. |
| Sources | Minimum width / height | 1920 / 1080 px | Each integer 0-32768; 0 means no minimum for that dimension. |
| Downloads | Destination | `<data root>\Library` | Must be an existing directory. The `DownloadService.from_config()` factory reads this value. The Downloads screen is still a placeholder. |
| Downloads | Maximum image size | 100 MB | Integer 1-2048. Checked against response size and streamed byte count. |
| Downloads | Request timeout | 30 seconds | Integer 1-300; passed to Wikimedia requests and each download request. |
| Downloads | Retry attempts | 3 | Integer 1-10. Exponential wait is capped at 30 seconds per retry. |
| Downloads | Retry backoff factor | 1.5 | Finite number 1-10. |
| Downloads | Concurrent downloads | 3 | Integer 1-8. A bounded semaphore limits work per downloader instance. |
| Duplicates | Near-match threshold | 10 / 64 bits | Integer 0-64, inclusive pHash Hamming distance. Lower is stricter; higher admits more candidates. The active scan snapshots its value. |
| Thumbnails | Cache enabled | On | Imports create and cards read cached previews; when disabled, cards load the original file. |
| Thumbnails | Width / height | 400 x 225 px | Each dimension 64-1024, with at most 1,048,576 target pixels total. Cache names include dimensions and quality, so old variants are not mistaken for current previews. |
| Thumbnails | JPEG quality | 85 | Integer 50-95. |
| Thumbnails | Cache budget | 500 MB | Integer 50-2048. Oldest JPEG entries inside the application thumbnail cache are evicted to stay within budget. Originals are never part of cache maintenance. |
| Logging | Level | INFO | DEBUG, INFO, WARNING, or ERROR. |
| Logging | File output | On | Rotating file output. Console logging remains available if the log file cannot be opened. |
| Logging | Maximum file size | 5 MB | Integer 1-100. |
| Logging | Retained files | 3 | Integer 1-10. |
| Preferences | Wallpaper style | Fill | One of Center, Tile, Stretch, Fit, Fill, or Span. Used for manual application and automatic rotation. |

The **Rotation** tab preserves Phase 8 controls: enablement, interval (1-10080 minutes), random or library-order selection, category filters, and minimum width/height (0-32768 px). Rotation applies only to indexed local files while the app is running.

The Settings page's Save action validates and persists operational controls as one atomic update. Cancel discards unsaved edits. Reset asks for confirmation and resets the controls shown on the operational tabs; rotation preferences are managed and saved separately in the Rotation tab. Logging changes apply immediately. Source/download factories and imports use the saved values on the next operation; active duplicate scans keep their captured threshold.

Image processing and Qt previews reject source images above 40,000,000 pixels before decoding. This accommodates 8K UHD and DCI images while bounding per-image decode work; it is not a promise that every 40 MP file fits available memory. Downloads require a direct HTTPS URL on the standard port and do not follow redirects. Obvious local hostnames and non-global IP literals are rejected. DNS names are not resolved and pinned to an approved public address, so local-address DNS resolution and DNS rebinding are residual network risks.

## Attribution export

Choose **Export library attribution as CSV** from Logging. The export contains only fields already stored in the local database: title, creator, source, source and license URLs, filename, library path, dimensions, and export time. It does not query a provider or modify images/database rows. Online records missing creator or licensing/source fields are counted as incomplete; local imports are not counted as incomplete attribution. Formula-like spreadsheet cells are prefixed safely. CSV output is UTF-8, written atomically, and the UI confirms before replacing an existing file.

## Retained legacy values

Older settings keys for theme, startup integration, update checks, automatic category organization, preferred aspect ratio, and lazy loading remain readable for compatibility. They are not exposed as working controls in this version. Analytics remains disabled and no telemetry is collected.
