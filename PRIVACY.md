# Privacy Policy — Sandy Wallpaper Studio

**Version:** 1.1.0  
**Last updated:** 2026-10-02

## 1. Overview
Sandy Wallpaper Studio is a local-first Windows desktop application.

Wallpaper files, local metadata, settings, logs and thumbnail data are designed to remain on the user's computer unless the user explicitly uses a feature that communicates with an external wallpaper source.

## 2. Personal Data
The current application does not implement analytics, advertising identifiers, user accounts, telemetry or a cloud backend.

The application therefore does not intentionally collect personal information as part of normal local library management.

## 3. Network Requests
The current external wallpaper source is Wikimedia Commons through its official MediaWiki API.

Network requests can include search terms entered by the user, API requests for wallpaper metadata, and requests required to download selected wallpaper files.

The application does not intentionally upload the user's local wallpaper library to Wikimedia Commons.

Future source providers must be documented in this policy before release.

## 4. Local Data
The application may store locally:
- wallpaper images
- SQLite metadata
- wallpaper metadata
- SHA-256 hashes
- perceptual hashes
- categories
- download records
- wallpaper history
- application settings
- logs
- generated thumbnails

## 5. Third-Party Content and Licensing
Downloaded content remains subject to the provider's license and terms. For Wikimedia Commons content, the application records available source, author, license and license URL metadata. Users are responsible for complying with applicable licenses.

## 6. Data Deletion
Duplicate detection must not silently delete wallpaper files. Any future deletion feature should require explicit user action and clearly identify affected files.

## 7. Future Features
Roadmap entries such as cloud synchronization, analytics, crash reporting or additional online providers are not active functionality. This policy must be updated before such functionality is released.

## 8. Contact
Privacy questions can be raised through the project repository: https://github.com/Sandy32513/Sandy-Wallpaper-Studio