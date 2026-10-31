"""Check packaged paths, checksum manifest, native proxy and frozen GUI."""

import ctypes as C
import ctypes.wintypes as W
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def verify_native(dll):
    proxy = C.WinDLL(str(dll.resolve()))
    kernel = C.WinDLL("kernel32", use_last_error=True)
    kernel.GetProcAddress.argtypes = [W.HMODULE, C.c_void_p]
    kernel.GetProcAddress.restype = C.c_void_p
    kernel.GetModuleHandleW.argtypes = [W.LPCWSTR]
    kernel.GetModuleHandleW.restype = W.HMODULE
    for item in json.loads((ROOT / "src/dwmapi_exports.json").read_text())["exports"]:
        assert kernel.GetProcAddress(proxy._handle, item["ordinal"]), item
        if item["name"]:
            name = C.create_string_buffer(item["name"].encode("ascii"))
            assert kernel.GetProcAddress(proxy._handle, C.cast(name, C.c_void_p)), item
    enabled = W.BOOL()
    call = proxy.DwmIsCompositionEnabled
    call.argtypes = [C.POINTER(W.BOOL)]
    call.restype = C.c_long
    actual = call(C.byref(enabled))
    original = C.WinDLL(str(Path(__import__("os").environ["WINDIR"]) / "System32/dwmapi.dll"))
    expected_enabled = W.BOOL()
    reference = original.DwmIsCompositionEnabled
    reference.argtypes = [C.POINTER(W.BOOL)]
    reference.restype = C.c_long
    assert actual == reference(C.byref(expected_enabled))
    if actual == 0:
        assert enabled.value == expected_enabled.value
    color = W.DWORD()
    opaque = W.BOOL()
    call = proxy.DwmGetColorizationColor
    call.argtypes = [C.POINTER(W.DWORD), C.POINTER(W.BOOL)]
    call.restype = C.c_long
    actual = call(C.byref(color), C.byref(opaque))
    expected_color, expected_opaque = W.DWORD(), W.BOOL()
    reference = original.DwmGetColorizationColor
    reference.argtypes = [C.POINTER(W.DWORD), C.POINTER(W.BOOL)]
    reference.restype = C.c_long
    assert actual == reference(C.byref(expected_color), C.byref(expected_opaque))
    state = proxy.PBZHitEnhanceStatus
    state.restype = W.DWORD
    end = time.monotonic() + 10
    while state() == 0 and time.monotonic() < end:
        time.sleep(0.025)
    assert state() == 2, "Non-game host should skip bootstrap"
    assert not kernel.GetModuleHandleW("UE4SS.dll"), "Test host must not load UE4SS"
    print("Native export forwarding and host guard passed")


def main():
    package = Path(sys.argv[1]).resolve()
    data = package / "PBZHitEnhance"
    manifest = json.loads((data / "package_manifest.json").read_text())
    for name, expected in manifest.items():
        path = package / name
        assert path.is_file(), name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    assert not list(package.rglob("ui_settings.json")), "Personal hotkey preferences must not ship"
    assert not list(package.rglob("runtime.log")), "Live logs must not ship"
    verify_native(package / "dwmapi.dll")
    output = ROOT / "build/panel-self-test.json"
    panel = data / "panel/HitstopPanel.exe"
    completed = subprocess.run(
        [
            str(panel),
            "--self-test",
            str(output),
            "--mod-dir",
            str(data / "ue4ss/Mods/UnifiedHitstop"),
        ],
        check=False,
        timeout=60,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert completed.returncode == 0, report
    assert report["config_valid"] and report["hotkey_valid"] and report["tk_window_created"]
    print("Packaged panel and all file checksums passed")


if __name__ == "__main__":
    main()
