# Phase 11 Acceptance Matrix — Release Hardening

This matrix was opened against the unchanged checkout before Phase 11 implementation.
It records current evidence and states limitations explicitly; a passing test suite alone
does not close a gate.

## Baseline

- Repository: `C:\Users\SANDY_1\Downloads\TEST_V0\sandy-wallpaper-studio`
- Platform/runtime: Windows, Python 3.12.10, 64-bit venv
- Branch/commit: `chore/repository-cleanup`, `12b755003ae8c462eee3b01b60b8c506e76bb8d5`
- Working tree: clean before Phase 11 changes
- `origin/main` and `origin/chore/repository-cleanup`: both resolve to the baseline commit;
  local `main` is stale at `2dac973` and is not the working branch.
- Baseline regression: `377 passed, 2 skipped` (379 collected; 109.23 seconds). The skips
  are the symlink-safety case (unsupported by the profile) and opt-in Windows Recycle Bin integration.
- Baseline Ruff: passed with Ruff 0.17.0.
- Baseline mypy: passed with mypy 2.4.0 after installing the already-declared dev checker
  into the existing ignored `.venv`; no tracked environment files changed.
- Package entry points: `python -m app --version` and the installed console script both
  report `0.7.0-dev`.
- CI workflow: Windows/Python 3.12; installs `.[dev]`, checks both version entry points,
  Ruff, mypy, and pytest. The previously verified baseline Actions run is historical and
  does not certify a Phase 11 commit.

## Acceptance areas

The table below records the original Phase 11 implementation snapshot. The dated follow-up after the table is the current status and supersedes its DNS and packaging statements.

| Area and requirement | Current implementation | Baseline evidence | Gap, risk, and impact | Corrective action and regression test | Final verification evidence |
|---|---|---|---|---|---|
| Regression testing — preserve Phases 0–10 workflows and run current full suite plus static checks. | Phase-based suites through Phase 11; Windows offscreen Qt CI; Ruff and mypy. | Baseline: 377 passed / 2 skipped; Ruff and mypy passed. | First final run found a Phase 2 error-message compatibility assertion after 386 passed and 2 skips; corrected the message without changing URL rejection. | Full rerun after the message correction; current full suite on the repository venv; no assertions were disabled. | Current run: 387 passed, 2 skipped, 0 failed (389 collected, 53.83 s, exit 0); `python -m ruff check .` and `python -m mypy app` pass. The skips are the symlink-creation restriction and opt-in Recycle Bin integration; Phase 11 focused Windows/offscreen runs previously passed (10 tests). |
| Performance testing — measure expensive local work reproducibly without unsupported claims. | Duplicate scan revalidates current files, computes SHA-256/pHash, uses a BK-tree, reports progress, and caps near-match edges. | No historical throughput/memory benchmark was available. | No before/after scanner comparison or promised performance SLA is claimed; hashing/decoding, thumbnail generation, DB latency and GUI responsiveness were not separately timed. | Reproducible temp-library benchmark reports elapsed time, throughput, Windows peak working set, accuracy and cancellation latency. | 100/500/1,000/5,000 records measured again; 5,000 took 105.946 s at 47.19 records/s and 239.81 MiB peak working set. Expected exact/near groups and invalid/missing issues were verified. See [Performance Record](PHASE11_PERFORMANCE.md). |
| Large-library testing — exercise increasing isolated libraries and preserve correctness, cancellation, and controlled results. | Scanner processes records sequentially, reports progress, supports cancellation, pages DB reads and caps near-match edges. | Existing group pagination tests; no pre-Phase-11 scale measurements. | The large run has one 8K image, not 5,000 worst-case 8K files; no broad hardware matrix. | Synthetic exact/near duplicates, mixed PNG/JPEG/WebP, corrupt image, missing path and one 8192x4320 image. | All four requested sizes completed; each found expected exact and near groups and reported invalid/missing records; cancellation returned within 4.4–12.2 ms. |
| Error recovery — expected config, database, file, network, worker, export, and cleanup failures must fail safely. | Atomic settings/export paths; download size/temp-file checks; worker error signals; transaction-aware repositories; guarded Recycle Bin cleanup. | Phase 0–10 regressions include configuration, database, network, export, worker and cleanup paths. | Disk-full and every physical permission/device/API failure combination were not simulated in this pass. Native wallpaper application was not invoked. | Added oversized-header, URL/redirect, partial-download cleanup, UI preview and compact-window regression checks; reran the existing suite. | Full suite passed 387/389. Symlink creation is unavailable under this profile. The Recycle Bin case skipped in the venv suite but its isolated system-Python round-trip passed (1 test); the synthetic target was restored and byte-verified. |
| Security — bound untrusted image/network/filesystem inputs and preserve cleanup boundaries. | 40 MP checks across Pillow and Qt previews; download byte cap, direct HTTPS/no redirects, sanitized names, path containment, parameterized repositories, reparse/hard-link cleanup guards and formula-safe CSV. | Initial code review found image decode had no application pixel ceiling and download URLs had no explicit no-redirect policy. | Moderate residual: DNS hostname resolution is not pinned, so DNS rebinding or private-address resolution is not fully prevented. | Added pre-decode pixel checks and mocked URL/redirect/partial-file tests; audited resolved venv packages with PyPA pip-audit. | No high-severity issue identified in inspected scope. `pip-audit --local` on the project venv reported no known package advisories; local project distribution was skipped because it is not on PyPI. |
| Accessibility and UI/UX — inspect labels, focus, keyboard path, errors, scrolling and responsive layouts. | PySide6 Obsidian theme; accessible names on search/favorite/detail controls; responsive Dashboard, Library, Favorites and detail dialog. | Windows screenshots exposed Library/Favorites horizontal clipping and detail action overflow at 800x600. | Screen-reader support and physical-input spot checks were not available; captures do not certify them. | Applied width-aware grids/toolbars and detail action wrapping; QTest exercises navigation by click/Space, verifies rotation names, captures pages/dialogs. | Windows Qt captures inspected at 1280x800, 1024x768, 800x600 and 1440x844 (1440x900 request clamped by work area); Library/Favorites have no horizontal range at 800x600. |
| Windows compatibility — validate path, Qt, native APIs, cleanup, and runtime behavior on Windows 10/11. | Windows-native wallpaper setting and Recycle Bin APIs; code/CI target Windows. | This phase ran on Windows 11 Enterprise build 26300 with Python 3.12.10 x64. | Native wallpaper change was not run to avoid changing live desktop/theme or per-monitor state; Windows 10 was not separately exercised. `pywin32` is absent from the project venv. | Ran full suite, static checks, Windows Qt UI capture, and the isolated Windows Recycle Bin test with system Python/`pywin32`, without changing the user's wallpaper/library. | Windows 11 runtime and Qt rendering checks passed. The isolated real Recycle Bin round-trip passed and restored/byte-verified the synthetic target; native wallpaper apply remains unverified. |
| Documentation audit — align README, status, roadmap, changelog, configuration, privacy, and CI guidance with verified behavior. | README describes implemented features and placeholder destinations; Phase 11 security/performance docs added; CI Ruff includes scripts. | Phase 10/version/main-branch statements and Phase 11 status were stale. | GitHub Actions was required to verify the pushed implementation commit. | Updated README, changelog, status, roadmap, configuration, privacy and development guide; checked commands and local links/anchors. | All 58 local Markdown links/anchors resolve; both version commands (`0.7.0-dev`), and `git diff --check` pass. [GitHub Actions run 39184857853](https://github.com/Sandy32513/Sandy-Wallpaper-Studio/actions/runs/39184857853) passed for main commit `b2e8474faa26aabab287d222c437af46cbbeaa7a`. |
| Release readiness — promotion and QA are accurate; packaging remains out of scope. | Development workflow; version is `0.7.0-dev`; Phase 12/13 remain planned. | At baseline, local branch and origin/main/origin/chore all pointed to 12b7550; local main was stale. | Moderate DNS and native desktop/accessibility verification limitations remain. | Reviewed diff/secrets/artifacts, reran tests and benchmark, and confirmed exact-SHA CI after the main fast-forward. No package, installer, or release tag was created. | Commits `698f58c` and `b2e8474` are on `origin/main` and the development branch. Exact main SHA `b2e8474faa26aabab287d222c437af46cbbeaa7a` passed [GitHub Actions run 39184857853](https://github.com/Sandy32513/Sandy-Wallpaper-Studio/actions/runs/39184857853). This finalization follow-up remains on `chore/repository-cleanup`; `main` is unchanged. |

## Final phase decision

**Current decision: PARTIALLY COMPLETE.** The follow-up below supersedes the earlier DNS finding: direct HTTPS downloads now reject any non-public DNS answer and pin the socket to a validated public address while retaining the original TLS hostname. Native wallpaper application, physical-input/screen-reader review, Windows 10, and clean-machine acceptance remain open. Phase 12 is packaging validation only; no product release has been created.

## Finalization follow-up — 2026-10-19

This follow-up is recorded on `chore/repository-cleanup` from the then-current `b30acc26867c01b7ddbaa846b7cc4caebbe178e8` baseline. It includes direct-DNS pinning, packaging diagnostics, and documentation. It does not claim a live network download or actual desktop wallpaper change.

| Gate | Evidence and result |
|---|---|
| DNS transport security | 13 tests cover public IPv4/IPv6 selection, private/loopback/link-local/reserved/multicast answers, mixed public/private responses, pinned socket destination, TLS hostname and certificate verification, and a changed-answer rebinding attempt. The adapter fails closed on proxies and disabled TLS verification. No production network request was made. |
| Regression/static/dependency | Latest full local run: 405 passed, 2 skipped (407 collected); Ruff passed; mypy passed for 55 application source files; `pip-audit --local` found no known vulnerabilities in installed packages. Skips: profile cannot create symlinks; real Recycle Bin integration is opt-in. |
| Packaging | Windows 11 x64, Python 3.12.10, PyInstaller 6.22.3. An unsigned `onedir` bundle was built under a path with spaces from clean source commit `7f1ccbc674a66cdbd0d0b9306e50b4253f285197`. Its isolated smoke imports a generated PNG through `ImportService` and, in a fresh process, verifies the saved theme, indexed image/file, metadata, hashes, thumbnail, and SQLite integrity before GUI startup/shutdown. The EXE is 11,263,152 bytes (SHA-256 `EE77C3AECDE0ACCC2E52454FA1F4B0393A27C1B7787A0DB7E172D3D208FAE339`); total bundle 245,950,472 bytes. See [Packaging](PACKAGING.md). |
| Manual acceptance | The actual Windows wallpaper API test was not run. No Narrator/physical-input review, separate Windows 10 run, or clean-machine/VM install was performed. See [Windows Manual Acceptance](WINDOWS_ACCEPTANCE.md). |
| Release state | Version remains `0.7.0-dev`. The local bundle is ignored build output; no installer, signature, tag, or public download was produced. The follow-up is not pushed to `main`. |

The exact follow-up commit, branch push, and its GitHub Actions result are reported in the task completion record; this document keeps the observed manual/CI gates distinct from local results.

## Verification command index

Commands below ran against isolated fixtures or the repository virtual environment unless a row says otherwise. The Windows-rendered UI captures and native-shell cleanup procedure used temporary data.

| Area | Command or procedure | Result |
|---|---|---|
| Regression | PowerShell: set `$env:QT_QPA_PLATFORM = "offscreen"`, then run `python -m pytest` with the project venv active. | Exit 0; 387 passed, 2 skipped (389 collected). |
| Static analysis | With the project venv active, run `python -m ruff check .` and `python -m mypy app`. | Both exit 0; Ruff clean; mypy clean in 55 source files. |
| Scale and performance | With the project venv active, run `python scripts/phase11_benchmark.py --sizes 100 500 1000 5000`. | Exit 0; correctness verified at all four sizes; measurements in [Performance Record](PHASE11_PERFORMANCE.md). |
| Error recovery | Full suite plus `python -m pytest -q -rs tests/test_phase9_cleanup.py` | Full suite passed; targeted run 11 passed and reported environment skips. |
| Security/dependencies | `python -m pytest tests/test_phase11.py -q`; `.venv/Scripts/pip-audit.exe --local` | Phase 11 tests passed earlier; no known dependency advisories. Local project package is not published on PyPI. |
| Accessibility/UI | Windows Qt capture run and QTest keyboard/accessible-name checks; headless UI tests in the full offscreen suite | Captures inspected at 1280x800, 1024x768, 800x600 and 1440x844. Physical-input and screen-reader checks remain open. |
| Windows APIs | PowerShell: set `$env:SWS_RUN_WINDOWS_RECYCLE_INTEGRATION = "1"`, run `python -m pytest -q tests/test_phase9_cleanup.py::test_windows_recycle_bin_round_trip` using a Python environment with `pywin32`, then remove the variable. | Exit 0; 1 passed; unique temporary target restored and bytes verified. Native wallpaper setting was not invoked. |
| Documentation | `git diff --check`; local Markdown link/anchor audit; inspect README commands against `pyproject.toml` and entry points | Diff clean; internal links/anchors resolve; both entry points report `0.7.0-dev`. |
| Git/CI | `git ls-remote origin refs/heads/main refs/heads/chore/repository-cleanup`; `gh run view 39184857853 --json status,conclusion,headSha,url` | At audit start, both remote refs were `b2e8474`; exact main SHA passed Windows/Python 3.12 CI. The follow-up remains on the development branch only. |
