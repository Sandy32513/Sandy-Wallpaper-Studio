# Phase 11 Performance and Large-Library Record

## Method

Revalidation run on 2026-10-19 from the Windows Python 3.12.10 virtual environment
(pytest benchmark worker uses the same virtual-environment interpreter):

```powershell
python scripts/phase11_benchmark.py --sizes 100 500 1000 5000
```

The script creates each dataset beneath a temporary directory and runs each scan in a fresh Python process. A dataset includes byte-identical copies, a one-pixel near variant, a corrupt image, a missing-file record, an 8192x4320 PNG, and deterministic PNG/JPEG/WebP images. The 8K fixture is 35,389,440 pixels and stays below the 40,000,000-pixel application ceiling. Dataset generation time is separate from scan time. Windows peak working set is read from the scanner process; cancellation latency is measured from cancellation request until the scan returns.

## Results

| Records | Valid files | Fixture generation | Scan time | Files/second | Peak working set | Cancel-to-return |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 98 | 1.050 s | 3.350 s | 29.85 | 236.09 MiB | 4.4 ms |
| 500 | 498 | 1.961 s | 11.019 s | 45.38 | 236.17 MiB | 12.2 ms |
| 1,000 | 998 | 3.024 s | 19.957 s | 50.11 | 236.68 MiB | 10.6 ms |
| 5,000 | 4,998 | 18.275 s | 105.946 s | 47.19 | 239.81 MiB | 8.3 ms |

At every size, the expected exact-copy group and near-match group were found; the corrupt image and missing file were reported as issues. The benchmark's correctness checks passed at all four sizes (exit code 0). The 5,000-record scan completed in 105.946 seconds with a 239.81 MiB peak working set on this machine. An earlier Phase 11 run recorded 90.129 seconds for 5,000 records; these single-machine runs are reference measurements, not a controlled before/after comparison or performance guarantee.

## Interpretation and limits

- This is a measured Phase 11 reference run, not a before/after optimization comparison or a promised service-level target.
- Throughput includes sequential file validation and hashing; it depends on CPU, storage, image mix, and cache state.
- Peak working set is the Windows scanner child process measurement. It does not include fixture-generation process memory or other application windows.
- Cancellation latency is a local service measurement. It does not measure how quickly the GUI repaints or how long Windows may take to close an entire application.
- Dataset images are small except for the single 8K fixture; the run is not a worst-case 5,000-image 8K workload.
- Hashing/decoding time was not isolated from total scan time; thumbnail generation, database-query latency, and GUI response time were not separately benchmarked. UI responsiveness was checked through Qt interaction/render tests, not timed under this synthetic scan workload.
- The benchmark does not copy, scan, or alter the user's wallpaper library.
