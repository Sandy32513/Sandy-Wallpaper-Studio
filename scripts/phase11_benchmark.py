"""Reproducible isolated-library duplicate-scan benchmark for Phase 11.

Run from the repository root with:
    python scripts/phase11_benchmark.py

Only synthetic files under a temporary directory are created. Each scan runs in a
fresh Python process so its reported Windows peak working set is not contaminated
by fixture generation or a previous dataset size.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _make_image(path: Path, seed: int) -> None:
    from PIL import Image

    rng = random.Random(seed)
    image = Image.frombytes("RGB", (64, 64), rng.randbytes(64 * 64 * 3))
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        image.save(path, format="JPEG", quality=90)
    elif suffix == ".webp":
        image.save(path, format="WEBP", quality=90)
    else:
        image.save(path, format="PNG", compress_level=1)


def _make_dataset(directory: Path, count: int) -> float:
    from PIL import Image

    started = time.perf_counter()
    directory.mkdir(parents=True, exist_ok=True)

    base = Image.new("RGB", (64, 64))
    base.putdata(
        [(x * 4, y * 4, (x ^ y) * 4) for y in range(64) for x in range(64)]
    )
    base_path = directory / "00_near_base.png"
    base.save(base_path, format="PNG")
    shutil.copyfile(base_path, directory / "01_exact_copy.png")

    near_variant = base.copy()
    near_variant.putpixel((0, 0), (1, 1, 1))
    near_variant.save(directory / "02_near_variant.png", format="PNG")

    (directory / "03_corrupt.jpg").write_bytes(b"not a decodable image")
    # Record 5 deliberately points to a file that does not exist.
    large_path = directory / "05_eight_k.png"
    Image.new("RGB", (8192, 4320), (12, 28, 44)).save(large_path, format="PNG")

    for index in range(6, count):
        extension = (".jpg", ".webp", ".png")[index % 3]
        _make_image(directory / f"{index:05d}_unique{extension}", index)
    return time.perf_counter() - started


def _peak_working_set_bytes() -> int | None:
    """Read the current process peak working set on Windows; return None elsewhere."""
    if sys.platform != "win32":
        return None

    class _ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    process = ctypes.WinDLL("Kernel32").GetCurrentProcess
    process.restype = ctypes.c_void_p
    get_memory = ctypes.WinDLL("Psapi").GetProcessMemoryInfo
    get_memory.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    get_memory.restype = ctypes.c_int
    if not get_memory(process(), ctypes.byref(counters), counters.cb):
        return None
    return int(counters.PeakWorkingSetSize)


def _scan_worker(directory: Path, count: int) -> dict[str, Any]:
    from app.database.models import Wallpaper
    from app.services.duplicate_scan_service import DuplicateScanService

    records = [
        Wallpaper(
            id=index + 1,
            filename=f"{index:05d}",
            path=str(directory / f"{index:05d}_unique.png"),
        )
        for index in range(count)
    ]
    # Replace seeded paths with their actual synthetic fixture names.
    records[0].path = str(directory / "00_near_base.png")
    records[0].filename = "00_near_base.png"
    records[1].path = str(directory / "01_exact_copy.png")
    records[1].filename = "01_exact_copy.png"
    records[2].path = str(directory / "02_near_variant.png")
    records[2].filename = "02_near_variant.png"
    records[3].path = str(directory / "03_corrupt.jpg")
    records[3].filename = "03_corrupt.jpg"
    records[4].path = str(directory / "04_missing.png")
    records[4].filename = "04_missing.png"
    records[5].path = str(directory / "05_eight_k.png")
    records[5].filename = "05_eight_k.png"
    for index in range(6, count):
        extension = (".jpg", ".webp", ".png")[index % 3]
        records[index].path = str(directory / f"{index:05d}_unique{extension}")
        records[index].filename = Path(records[index].path).name

    scan = DuplicateScanService(records, threshold=0)
    started = time.perf_counter()
    report = scan.scan()
    elapsed = time.perf_counter() - started
    exact_pair_found = any(
        {member.wallpaper_id for member in group.members} == {1, 2}
        for group in report.exact_groups
    )
    near_pair_found = any(
        {1, 3}.issubset({member.wallpaper_id for member in group.members})
        for group in report.near_groups
    )
    issue_codes = sorted({issue.code for issue in report.issues})

    cancel_event = threading.Event()

    def cancel_after_first(done: int, _total: int, _name: str) -> None:
        if done >= 1:
            cancel_event.set()

    cancellation_started = time.perf_counter()
    cancelled_report = scan.scan(cancel_event, cancel_after_first)
    cancellation_elapsed = time.perf_counter() - cancellation_started
    peak_bytes = _peak_working_set_bytes()

    return {
        "records": count,
        "elapsed_seconds": round(elapsed, 3),
        "records_per_second": round(count / elapsed, 2) if elapsed else None,
        "candidate_count": len(report.candidates),
        "exact_groups": len(report.exact_groups),
        "near_groups": len(report.near_groups),
        "near_complete": report.near_complete,
        "issue_codes": issue_codes,
        "exact_pair_found": exact_pair_found,
        "near_pair_found": near_pair_found,
        "completed": report.completed,
        "scanned_records": report.scanned_records,
        "cancelled_after_one_record": cancelled_report.cancelled
        and cancelled_report.scanned_records == 1,
        "cancellation_seconds": round(cancellation_elapsed, 4),
        "peak_working_set_mib": round(peak_bytes / 1024 / 1024, 2)
        if peak_bytes is not None
        else None,
    }


def _run_parent(sizes: list[int]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="sws-phase11-benchmark-") as temp_name:
        root = Path(temp_name)
        for size in sizes:
            directory = root / str(size)
            generation_seconds = _make_dataset(directory, size)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--scan-worker",
                    str(directory),
                    "--count",
                    str(size),
                ],
                cwd=ROOT,
                capture_output=True,
                check=False,
                text=True,
            )
            if completed.returncode:
                raise RuntimeError(
                    f"Benchmark worker failed for {size} records:\n{completed.stderr}"
                )
            result = json.loads(completed.stdout)
            result["fixture_generation_seconds"] = round(generation_seconds, 3)
            if not (
                result["completed"]
                and result["scanned_records"] == size
                and result["candidate_count"] == size - 2
                and result["exact_pair_found"]
                and result["near_pair_found"]
                and result["near_complete"]
                and "invalid" in result["issue_codes"]
                and "missing" in result["issue_codes"]
                and result["cancelled_after_one_record"]
            ):
                raise AssertionError(f"Benchmark correctness check failed: {result}")
            results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 500, 1000, 5000])
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    parser.add_argument("--scan-worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--count", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.scan_worker is not None:
        if args.count is None or args.count < 6:
            parser.error("--scan-worker requires --count >= 6")
        print(json.dumps(_scan_worker(args.scan_worker, args.count), separators=(",", ":")))
        return 0

    if any(size < 6 for size in args.sizes):
        parser.error("every dataset size must be at least 6")
    report = {
        "runtime": sys.version.split()[0],
        "platform": sys.platform,
        "sizes": args.sizes,
        "results": _run_parent(args.sizes),
        "notes": [
            "All fixture files were synthetic and stored in a temporary directory.",
            "Each scan used a fresh child process; peak working set is Windows process data.",
            "A 40 MP 8K fixture, exact byte duplicate, pHash near duplicate, corrupt file, and missing path were included.",
            "The cancellation measurement stops after the first scanned record.",
        ],
    }
    output = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
