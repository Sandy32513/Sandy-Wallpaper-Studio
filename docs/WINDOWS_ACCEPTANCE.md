# Windows Manual Acceptance Checklist

These checks are separate from CI. A green automated suite or a Windows-rendered Qt capture does not complete the manual desktop or accessibility checks.

## Native wallpaper API — opt-in

**Status: PASS — native API apply/restore, 2026-10-20.** The opt-in procedure below was run after explicit user approval on Microsoft Windows 11 Enterprise, version 10.0.26300 (build 26300), with Python 3.12.10.

`.\.venv\Scripts\python.exe scripts/manual_wallpaper_acceptance.py` exited 0. Windows accepted the generated test image through `SystemParametersInfoW`; the test observed its path as the active wallpaper. The script restored the original wallpaper path and exact captured registry values/types, verified both, and removed the generated PNG. Its diagnostic log remains in the local `%TEMP%\sws-wallpaper-acceptance-*` directory.

This verifies the Windows API call and restoration path. No visual screenshot was captured, and independent per-monitor assignment was not exercised. Rerunning the procedure changes the active desktop briefly and still requires explicit approval.

From the repository root, using the project Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe scripts/manual_wallpaper_acceptance.py
```

The script:

1. Reads the active wallpaper path with `SPI_GETDESKWALLPAPER` and captures the wallpaper registry values and their original types.
2. Refuses to proceed if Windows cannot report an existing wallpaper file.
3. Generates a temporary 1920x1080 PNG under a unique OS temporary directory; it does not copy over the original wallpaper.
4. Requires the operator to type `APPLY TEST WALLPAPER TO MY DESKTOP` before calling the real `SystemParametersInfoW` setter.
5. Waits for the operator to inspect the desktop. Enter or Ctrl+C starts restoration.
6. Restores the captured registry values and original wallpaper path in a `finally` block, then verifies both the path Windows reports and the exact registry values/types.
7. Removes only the generated image after restoration succeeds. If restoration fails, it keeps the generated image so it can be selected manually and prints the local diagnostic-log path.

The system wallpaper API changes the desktop wallpaper and style for the current Windows user. This does not verify independent per-monitor assignment. The script does not update the application's SQLite history because it calls the low-level service method directly.

Automated mock tests verify successful API handling, error-code reporting, and that failed calls do not add in-memory application history. They do not verify Windows Shell behavior or actual display rendering.

## Keyboard and screen-reader review

**Status: NOT RUN with physical input or Narrator.** Previously inspected Qt captures and QTest event delivery are automated evidence only.

On Windows 11, use a disposable library with synthetic images and record the Windows build, screen scaling, window size, and screen-reader version. Review each at 1280x800, 1024x768, and 800x600; request 1440x900 and record any work-area clamp.

- Start the app and navigate every sidebar destination using Tab, Shift+Tab, Enter, and Space. Confirm focus is visible and the focused page changes as expected.
- Use Narrator to inspect the window title, sidebar labels, search and filter controls, image cards, favorite actions, dialog names, and status/error messages.
- Import a synthetic image, open and close its detail dialog, favorite it, and navigate the History view. Confirm focus returns to a useful control after each dialog.
- Inspect Settings and Duplicate Manager controls, including progress, cancellation, confirmation, and validation errors. Do not approve cleanup against a real library.
- Check text scaling and contrast at the user's selected Windows scaling. Record clipped text, missing accessible names, focus traps, and any control that cannot be reached without a pointer.

Do not report full screen-reader compatibility based on object names, screenshots, or QTest alone.

## Platform boundary

Phase 11 and Phase 12 local validation ran on Windows 11. Windows 10 compatibility and clean-machine installation remain unverified. The Phase 12 temporary-profile executable smoke test does not substitute for a separate Windows installation or VM.
