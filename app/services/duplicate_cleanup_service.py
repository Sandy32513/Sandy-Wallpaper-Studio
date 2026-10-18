"""Explicit, fail-closed cleanup of reviewed duplicates through the Windows shell."""

from __future__ import annotations

import ctypes
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.services.duplicate_scan_service import (
    CleanupPreview,
    CleanupPreviewEntry,
    DuplicateCandidate,
    DuplicateScanReport,
    build_cleanup_preview,
)


class CleanupSafetyError(RuntimeError):
    """A target failed a cleanup safety check or the Recycle Bin operation."""


@dataclass(frozen=True)
class CleanupFileResult:
    """Result for one explicitly selected file."""

    group_id: str
    wallpaper_id: int
    path: Path
    size_bytes: int
    status: Literal["recycled", "failed", "cancelled", "skipped"]
    message: str


@dataclass(frozen=True)
class CleanupOperationReport:
    """Per-file cleanup outcomes; database records are intentionally retained."""

    results: tuple[CleanupFileResult, ...]
    cancelled: bool

    @property
    def recycled_count(self) -> int:
        return sum(result.status == "recycled" for result in self.results)

    @property
    def failed_count(self) -> int:
        return sum(result.status == "failed" for result in self.results)

    @property
    def recycled_bytes(self) -> int:
        return sum(
            result.size_bytes for result in self.results if result.status == "recycled"
        )


CleanupProgress = Callable[[int, int, str], None]
RecycleFile = Callable[[Path], None]
LockCheck = Callable[[Path], None]

_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_IFILEOP_SET_OPERATION_FLAGS = 5
_IFILEOP_DELETE_ITEM = 18
_IFILEOP_PERFORM_OPERATIONS = 21
_IFILEOP_GET_ANY_OPERATIONS_ABORTED = 22


def windows_recycle_bin_available() -> bool:
    """Return whether this process is on Windows, where the shell API exists."""
    return os.name == "nt"


def _ensure_not_in_use(path: Path) -> None:
    """Require an exclusive, delete-capable Windows file handle, then close it."""
    if os.name != "nt":
        raise CleanupSafetyError("Recycle Bin cleanup is supported on Windows only.")

    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.restype = wintypes.HANDLE
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    close_handle = kernel32.CloseHandle
    close_handle.restype = wintypes.BOOL
    close_handle.argtypes = [wintypes.HANDLE]

    generic_read = 0x80000000
    delete_access = 0x00010000
    open_existing = 3
    file_attribute_normal = 0x80
    handle = create_file(
        str(path),
        generic_read | delete_access,
        0,
        None,
        open_existing,
        file_attribute_normal,
        None,
    )
    handle_value = handle if isinstance(handle, int) else getattr(handle, "value", None)
    if handle_value in (None, _INVALID_HANDLE_VALUE):
        raise CleanupSafetyError(
            "The file is in use or cannot be opened with exclusive delete access."
        )
    if not close_handle(handle):
        raise CleanupSafetyError("The exclusive safety-check handle could not be closed.")


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, value: str) -> _GUID:
        import uuid

        raw = uuid.UUID(value).bytes_le
        return cls(
            int.from_bytes(raw[0:4], "little"),
            int.from_bytes(raw[4:6], "little"),
            int.from_bytes(raw[6:8], "little"),
            (ctypes.c_ubyte * 8).from_buffer_copy(raw[8:16]),
        )


def _interface_method(interface: ctypes.c_void_p, index: int, *argtypes):
    vtable = ctypes.cast(
        interface, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    prototype = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
    return prototype(ctypes.c_long, ctypes.c_void_p, *argtypes)(vtable[index])


def _recycle_with_windows_shell(path: Path) -> None:
    """Move one full-path file to Recycle Bin using IFileOperation.

    FOFX_RECYCLEONDELETE is explicit: there is no permanent-delete fallback.
    A failed or aborted shell operation is reported as failure.
    """
    if os.name != "nt":
        raise CleanupSafetyError("Recycle Bin cleanup is supported on Windows only.")

    from ctypes import wintypes

    clsid_file_operation = _GUID.parse("3ad05575-8857-4850-9277-11b85bdb8e09")
    iid_file_operation = _GUID.parse("947aab5f-0a5c-4c13-b4d6-4bf7836fc9f8")
    iid_shell_item = _GUID.parse("43826d1e-e718-42ee-bc55-a1e261c37bfe")
    operation = ctypes.c_void_p()
    shell_item = ctypes.c_void_p()

    # IFileOperation flags: explicit Recycle Bin routing, no fallback delete.
    fof_allow_undo = 0x0040
    fof_silent = 0x0004
    fof_no_confirmation = 0x0010
    fof_no_error_ui = 0x0400
    fofx_recycle_on_delete = 0x00080000
    flags = (
        fof_allow_undo
        | fof_silent
        | fof_no_confirmation
        | fof_no_error_ui
        | fofx_recycle_on_delete
    )

    ole32 = ctypes.OleDLL("ole32")
    shell32 = ctypes.OleDLL("shell32")
    co_initialize = ole32.CoInitializeEx
    co_initialize.restype = ctypes.c_long
    co_initialize.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    co_uninitialize = ole32.CoUninitialize
    co_uninitialize.restype = None
    co_create = ole32.CoCreateInstance
    co_create.restype = ctypes.c_long
    co_create.argtypes = [
        ctypes.POINTER(_GUID),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    create_shell_item = shell32.SHCreateItemFromParsingName
    create_shell_item.restype = ctypes.c_long
    create_shell_item.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]

    initialized_here = False
    try:
        init_result = int(co_initialize(None, 0x2))  # COINIT_APARTMENTTHREADED
        if init_result >= 0:
            initialized_here = True
        elif init_result != -2147417850:  # RPC_E_CHANGED_MODE: already initialized.
            raise CleanupSafetyError("Windows Shell could not initialize safely.")

        _check_hresult(
            co_create(
                ctypes.byref(clsid_file_operation),
                None,
                0x1,  # CLSCTX_INPROC_SERVER
                ctypes.byref(iid_file_operation),
                ctypes.byref(operation),
            ),
            "Windows Recycle Bin operation is unavailable.",
        )
        _check_hresult(
            create_shell_item(
                str(path),
                None,
                ctypes.byref(iid_shell_item),
                ctypes.byref(shell_item),
            ),
            "Windows could not open the reviewed file for recycling.",
        )
        _check_hresult(
            _interface_method(
                operation, _IFILEOP_SET_OPERATION_FLAGS, wintypes.DWORD
            )(operation, flags),
            "Windows could not set the Recycle Bin operation mode.",
        )
        _check_hresult(
            _interface_method(
                operation,
                _IFILEOP_DELETE_ITEM,
                ctypes.c_void_p,
                ctypes.c_void_p,
            )(
                operation, shell_item, None
            ),
            "Windows rejected the Recycle Bin operation.",
        )
        perform_result = _interface_method(operation, _IFILEOP_PERFORM_OPERATIONS)(
            operation
        )
        aborted = ctypes.c_int(0)
        aborted_result = _interface_method(
            operation,
            _IFILEOP_GET_ANY_OPERATIONS_ABORTED,
            ctypes.POINTER(ctypes.c_int),
        )(operation, ctypes.byref(aborted))
        _check_hresult(perform_result, "Windows Recycle Bin operation failed.")
        _check_hresult(
            aborted_result,
            "Windows could not confirm the Recycle Bin operation result.",
        )
        if aborted.value:
            raise CleanupSafetyError("Windows aborted the Recycle Bin operation.")
        if path.exists():
            raise CleanupSafetyError("Windows reported success, but the file remains in place.")
    except CleanupSafetyError:
        raise
    except Exception as exc:
        raise CleanupSafetyError(
            f"Windows Recycle Bin operation failed ({type(exc).__name__})."
        ) from None
    finally:
        _release_interface(shell_item)
        _release_interface(operation)
        if initialized_here:
            co_uninitialize()


def _check_hresult(result: int, message: str) -> None:
    if result < 0:
        raise CleanupSafetyError(f"{message} (HRESULT 0x{result & 0xFFFFFFFF:08X}).")


def _release_interface(interface: ctypes.c_void_p) -> None:
    if interface:
        try:
            _interface_method(interface, 2)(interface)
        except Exception:
            pass


def execute_cleanup(
    report: DuplicateScanReport,
    preview: CleanupPreview,
    allowed_root: Path,
    cancel_event: threading.Event | None = None,
    progress: CleanupProgress | None = None,
    recycler: RecycleFile | None = None,
    lock_check: LockCheck | None = None,
) -> CleanupOperationReport:
    """Revalidate and recycle each explicitly approved file, stopping on error.

    The database is intentionally untouched. Its wallpaper rows remain present
    so favorite, history, and view references remain valid and the scan can
    report the recycled path as missing until the item is restored or reimported.
    """
    if not windows_recycle_bin_available() and recycler is None:
        raise CleanupSafetyError("Recycle Bin cleanup is supported on Windows only.")
    cancel = cancel_event or threading.Event()
    callback = progress or (lambda _done, _total, _name: None)
    move_to_recycle_bin = recycler or _recycle_with_windows_shell
    verify_not_in_use = lock_check or _ensure_not_in_use
    targets = [
        (entry, candidate)
        for entry in preview.entries
        for candidate in entry.selected_for_removal
    ]
    if not targets:
        raise CleanupSafetyError("The cleanup plan contains no selected files.")

    results: list[CleanupFileResult] = []
    total = len(targets)
    stopped_after_failure = False
    for index, (entry, target) in enumerate(targets, start=1):
        if cancel.is_set():
            results.extend(
                _pending_result(pair, "cancelled", "Not started; operation was cancelled.")
                for pair in targets[index - 1 :]
            )
            callback(index - 1, total, target.display_name)
            return CleanupOperationReport(tuple(results), cancelled=True)
        if stopped_after_failure:
            results.append(
                CleanupFileResult(
                    entry.group_id,
                    target.wallpaper_id,
                    target.canonical_path,
                    target.size_bytes,
                    "skipped",
                    "Not attempted after an earlier cleanup failure.",
                )
            )
            callback(index, total, target.display_name)
            continue

        try:
            build_cleanup_preview(
                report,
                {entry.group_id: {target.wallpaper_id}},
                {entry.group_id: entry.retained.wallpaper_id},
                cancel,
                allowed_root=allowed_root,
            )
            verify_not_in_use(target.canonical_path)
            # Recheck the scope and file identity directly after the lock probe.
            build_cleanup_preview(
                report,
                {entry.group_id: {target.wallpaper_id}},
                {entry.group_id: entry.retained.wallpaper_id},
                cancel,
                allowed_root=allowed_root,
            )
            move_to_recycle_bin(target.canonical_path)
            try:
                target.canonical_path.lstat()
            except FileNotFoundError:
                pass
            except OSError:
                raise CleanupSafetyError(
                    "Windows returned success, but the file's final location could not be verified."
                ) from None
            else:
                raise CleanupSafetyError("The file remains in place after the Recycle Bin request.")
        except Exception as exc:
            if cancel.is_set():
                results.extend(
                    _pending_result(pair, "cancelled", "Not started; operation was cancelled.")
                    for pair in targets[index - 1 :]
                )
                callback(index - 1, total, target.display_name)
                return CleanupOperationReport(tuple(results), cancelled=True)
            message = (
                str(exc)
                if isinstance(exc, CleanupSafetyError)
                else type(exc).__name__
            )
            results.append(
                CleanupFileResult(
                    entry.group_id,
                    target.wallpaper_id,
                    target.canonical_path,
                    target.size_bytes,
                    "failed",
                    message,
                )
            )
            stopped_after_failure = True
        else:
            results.append(
                CleanupFileResult(
                    entry.group_id,
                    target.wallpaper_id,
                    target.canonical_path,
                    target.size_bytes,
                    "recycled",
                    "Moved to the Windows Recycle Bin.",
                )
            )
        callback(index, total, target.display_name)

    return CleanupOperationReport(tuple(results), cancelled=False)


def _pending_result(
    pair: tuple[CleanupPreviewEntry, DuplicateCandidate],
    status: Literal["cancelled", "skipped"],
    message: str,
) -> CleanupFileResult:
    entry, target = pair
    return CleanupFileResult(
        entry.group_id,
        target.wallpaper_id,
        target.canonical_path,
        target.size_bytes,
        status,
        message,
    )


__all__ = [
    "CleanupFileResult",
    "CleanupOperationReport",
    "CleanupSafetyError",
    "execute_cleanup",
    "windows_recycle_bin_available",
]
