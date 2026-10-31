"""Assemble a portable release using the pinned UE4SS runtime archive."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obtain_runtime():
    dep = json.loads((ROOT / "dependencies.json").read_text())["ue4ss"]
    cache = ROOT / "build/dependencies"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "ue4ss.zip"
    if not archive.exists() or digest(archive) != dep["archive_sha256"]:
        request = urllib.request.Request(dep["url"], headers={"User-Agent": "PBZHitEnhance-build"})
        with (
            urllib.request.urlopen(request, timeout=120) as response,
            archive.open("wb") as out,
        ):
            shutil.copyfileobj(response, out)
    if digest(archive) != dep["archive_sha256"]:
        raise RuntimeError("UE4SS archive checksum mismatch")
    return archive, dep


def main():
    version = (ROOT / "VERSION").read_text().strip()
    package = ROOT / "build/package"
    if package.exists():
        raise RuntimeError("Package directory already exists. Use a clean build/package directory.")
    package.mkdir(parents=True)
    data = package / "PBZHitEnhance"
    runtime = data / "ue4ss"
    runtime.mkdir(parents=True)
    panel = ROOT / "build/panel/HitstopPanel"
    if not (panel / "HitstopPanel.exe").is_file():
        raise RuntimeError("Standalone panel has not been built")
    shutil.copytree(panel, data / "panel")
    shutil.copy2(ROOT / "build/native/Release/dwmapi.dll", package / "dwmapi.dll")
    archive, dep = obtain_runtime()
    names = [
        "UE4SS.dll",
        "MemberVariableLayout.ini",
        "UE4SS_Signatures/GNatives.lua",
        "UE4SS_Signatures/GUObjectArray.lua",
        "LICENSE",
    ]
    with zipfile.ZipFile(archive) as source:
        for name in names:
            target = runtime / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read("ue4ss/" + name))
    if digest(runtime / "UE4SS.dll") != dep["dll_sha256"]:
        raise RuntimeError("UE4SS DLL checksum mismatch")
    shutil.copy2(ROOT / "runtime-settings.ini", runtime / "UE4SS-settings.ini")
    shutil.copytree(ROOT / "mod", runtime / "Mods")
    (runtime / "Mods/mods.txt").write_text("UnifiedHitstop : 1\n", encoding="utf-8")
    (data / "logs").mkdir()
    (data / "temp").mkdir()
    (data / "dependencies.json").write_bytes((ROOT / "dependencies.json").read_bytes())
    shutil.copy2(ROOT / "README.md", package / "README.md")
    shutil.copy2(ROOT / "LICENSE", package / "LICENSE")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", package / "THIRD_PARTY_NOTICES.md")
    shutil.copy2(ROOT / "tools/Uninstall.ps1", package / "Uninstall.ps1")
    licenses = data / "licenses"
    licenses.mkdir()
    base = Path(sys.base_prefix)
    if (base / "LICENSE.txt").exists():
        shutil.copy2(base / "LICENSE.txt", licenses / "Python-LICENSE.txt")
    for name in ("tcl", "tk"):
        for path in (base / "tcl").glob(name + "*/license.terms"):
            shutil.copy2(path, licenses / (path.parent.name + "-license.terms"))
    manifest = {
        p.relative_to(package).as_posix(): digest(p)
        for p in sorted(package.rglob("*"))
        if p.is_file()
    }
    (data / "package_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    target = destination / f"PBZHitEnhance-v{version}-windows-x64.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as output:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(package).as_posix())
    (destination / "SHA256SUMS.txt").write_text(
        digest(target) + "  " + target.name + "\n", encoding="ascii"
    )
    print("Release archive:", target)


if __name__ == "__main__":
    main()
