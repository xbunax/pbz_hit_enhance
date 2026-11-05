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


def verify_package(package):
    metadata = json.loads((package / "package.json").read_text())
    mode = metadata["mode"]
    assert mode in ("with-UE4SS", "mod-only"), mode
    manifest = json.loads((package / "package_manifest.json").read_text())
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    forbidden = {".ps1", ".bat", ".cmd", ".py", ".pdb", ".lib", ".exp", ".zip"}
    mod_prefix = (
        "PBZHitEnhance/ue4ss/Mods/UnifiedHitstop" if mode == "with-UE4SS" else "UnifiedHitstop"
    )
    runtime_zip = mod_prefix + "/panel/_internal/base_library.zip"
    assert not any(Path(n).suffix.lower() in forbidden and n != runtime_zip for n in actual), (
        "Non-runtime files"
    )
    assert not (package / "docs").exists(), "Developer and duplicate documents must not ship"
    assert actual == set(manifest) | {"package_manifest.json"}, "Unlisted package files"
    for name, expected in manifest.items():
        path = (package / name).resolve()
        assert path.is_relative_to(package) and path.is_file(), name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    assert not any(package.rglob("ui_settings.json")), "Personal preferences must not ship"
    for name in (
        "runtime.log",
        "status.ini",
        "bootstrap.ini",
        "startup.log",
        "pbz_job_fixture.exe",
    ):
        assert not any(package.rglob(name)), name
    if mode == "with-UE4SS":
        mod = package / "PBZHitEnhance/ue4ss/Mods/UnifiedHitstop"
        dependency = json.loads((ROOT / "dependencies.json").read_text())["ue4ss"]
        runtime = package / "PBZHitEnhance/ue4ss/UE4SS.dll"
        assert hashlib.sha256(runtime.read_bytes()).hexdigest() == dependency["dll_sha256"]
        verify_native(package / "dwmapi.dll")
    else:
        mod = package / "UnifiedHitstop"
        for name in ("UE4SS.dll", "dwmapi.dll", "UE4SS-settings.ini", "MemberVariableLayout.ini"):
            assert not any(package.rglob(name)), "Runtime leaked into mod-only: " + name
        assert not (package / "PBZHitEnhance").exists()
    assert (mod / "Scripts/PBZBootstrap.dll").is_file()
    assert (mod / "dependencies.json").is_file()
    assert (mod / "install-mode.txt").read_text().strip() == mode
    library = C.WinDLL(str((mod / "Scripts/PBZBootstrap.dll").resolve()))
    # Resolve only: invoking the entry point belongs to the live-game smoke test.
    assert library.luaopen_pbz_bootstrap
    output = ROOT / ("build/panel-self-test-" + mode + ".json")
    completed = subprocess.run(
        [str(mod / "panel/HitstopPanel.exe"), "--self-test", str(output), "--mod-dir", str(mod)],
        check=False,
        timeout=60,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert completed.returncode == 0, report
    assert report["config_valid"] and report["hotkey_valid"] and report["tk_window_created"]
    print(mode + ": checksums, distribution boundaries and frozen panel passed")


def main():
    base = Path(sys.argv[1]).resolve()
    if (base / "package.json").is_file():
        verify_package(base)
    else:
        for mode in ("with-UE4SS", "mod-only"):
            verify_package(base / mode)
        sums = (ROOT / "dist/SHA256SUMS.txt").read_text().splitlines()
        assert len(sums) == 2
        for line in sums:
            checksum, name = line.split()
            assert hashlib.sha256((ROOT / "dist" / name).read_bytes()).hexdigest() == checksum


if __name__ == "__main__":
    main()
