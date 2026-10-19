"""Unit tests for the opt-in wallpaper test's reversible Windows helpers."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest


def test_registry_restoration_keeps_exact_values_and_registry_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("winreg")
    acceptance = importlib.import_module("scripts.manual_wallpaper_acceptance")

    class FakeKey:
        def __enter__(self) -> FakeKey:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class FakeWinreg:
        HKEY_CURRENT_USER = object()
        KEY_READ = 1
        KEY_SET_VALUE = 2
        REG_SZ = 3
        values = {
            "Wallpaper": (r"C:\Wallpapers\current.jpg", REG_SZ),
            "WallpaperStyle": ("10", REG_SZ),
        }

        @classmethod
        def OpenKey(cls, *_args: object) -> FakeKey:
            return FakeKey()

        @classmethod
        def QueryValueEx(cls, _key: FakeKey, name: str) -> tuple[object, int]:
            if name not in cls.values:
                raise FileNotFoundError(name)
            return cls.values[name]

        @classmethod
        def SetValueEx(
            cls,
            _key: FakeKey,
            name: str,
            _reserved: int,
            value_type: int,
            value: object,
        ) -> None:
            cls.values[name] = (value, value_type)

        @classmethod
        def DeleteValue(cls, _key: FakeKey, name: str) -> None:
            cls.values.pop(name, None)

    original_values = dict(FakeWinreg.values)
    monkeypatch.setattr(acceptance, "winreg", FakeWinreg)

    captured = acceptance._read_registry_state()
    assert captured == {
        "Wallpaper": original_values["Wallpaper"],
        "WallpaperStyle": original_values["WallpaperStyle"],
        "TileWallpaper": None,
    }

    FakeWinreg.values["Wallpaper"] = (r"C:\Wallpapers\temporary-test.png", FakeWinreg.REG_SZ)
    FakeWinreg.values["WallpaperStyle"] = ("6", FakeWinreg.REG_SZ)
    FakeWinreg.values["TileWallpaper"] = ("0", FakeWinreg.REG_SZ)
    acceptance._restore_registry_state(captured)

    assert FakeWinreg.values == original_values


def test_native_wallpaper_path_helper_reads_writes_and_reports_api_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("winreg")
    acceptance = importlib.import_module("scripts.manual_wallpaper_acceptance")

    class FakeUser32:
        def __init__(self) -> None:
            self.path = r"C:\Wallpapers\current.jpg"
            self.result = 1

        def SystemParametersInfoW(
            self,
            action: int,
            _parameter: int,
            value: object,
            _flags: int,
        ) -> int:
            if action == acceptance.SPI_GETDESKWALLPAPER:
                value.value = self.path  # type: ignore[attr-defined]
            elif action == acceptance.SPI_SETDESKWALLPAPER and self.result:
                self.path = str(value)
            return self.result

    user32 = FakeUser32()
    monkeypatch.setattr(acceptance.ctypes, "windll", SimpleNamespace(user32=user32), raising=False)

    assert acceptance._read_native_wallpaper_path() == user32.path
    acceptance._write_native_wallpaper_path(r"C:\Temp\generated-test.png")
    assert acceptance._read_native_wallpaper_path() == r"C:\Temp\generated-test.png"

    user32.result = 0
    error_codes: list[int] = []

    def make_windows_error(code: int) -> OSError:
        error_codes.append(code)
        return OSError("denied")

    monkeypatch.setattr(acceptance.ctypes, "get_last_error", lambda: 5, raising=False)
    monkeypatch.setattr(acceptance.ctypes, "WinError", make_windows_error, raising=False)
    with pytest.raises(OSError, match="denied"):
        acceptance._write_native_wallpaper_path(r"C:\Temp\failed-test.png")
    assert error_codes == [5]
