# Phase 11 Performance and Large-Library Record

## Method

Run on 2026-10-19 from the Windows Python 3.12.10 virtual environment:

```powershell
python scripts/phase11_benchmark.py --sizes 100 500 1000 5000
```

The script creates each dataset beneath a temporary directory and runs each scan in a fresh Python process. A dataset includes byte-identical copies, a one-pixel near variant, a corrupt image, a missing-file record, an 8192x4320 PNG, and deterministic PNG/JPEG/WebP images. The 8K fixture is 35,389,440 pixels and stays below the 40,000,000-pixel application ceiling. Dataset generation time is separate from scan time. Windows peak working set is read from the scanner process; cancellation latency is measured from cancellation request until the scan returns.

## Results

| Records | Valid files | Scan time | Files/second | Peak working set | Cancel-to-return |
|---:|---:|---:|---:|---:|---:|
| 100 | 98 | 6.802 s | 14.70 | 235.85 MiB | 10.7 ms |
| 500 | 498 | 10.379 s | 48.17 | 235.82 MiB | 23.2 ms |
| 1,000 | 998 | 20.793 s | 48.09 | 236.15 MiB | 6.6 ms |
| 5,000 | 4,998 | 90.129 s | 55.48 | 239.05 MiB | 6.6 ms |

At every size, the expected exact-copy group and near-match group were found; the corrupt image and missing file were reported as issues. The benchmark's correctness checks passed at all four sizes. The 5,000-record scan completed in 90.129 seconds with a 239.05 MiB peak working set on this machine.

## Interpretation and limits

- This is a measured Phase 11 reference run, not a before/after optimization comparison or a promised service-level target.
- Throughput includes sequential file validation and hashing; it depends on CPU, storage, image mix, and cache state.
- Peak working set is the Windows scanner child process measurement. It does not include fixture-generation process memory or other application windows.
- Cancellation latency is a local service measurement. It does not measure how quickly the GUI repaints or how long Windows may take to close an entire application.
- Dataset images are small except for the single 8K fixture; the run is not a worst-case 5,000-image 8K workload.
- The benchmark does not copy, scan, or alter the user's wallpaper library.
