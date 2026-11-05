"""Build two independent distributions from one verified set of binaries."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODES = ("with-UE4SS", "mod-only")


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def obtain_runtime():
    dep = json.loads((ROOT / "dependencies.json").read_text())["ue4ss"]
    folder = ROOT / "build/dependencies"
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "ue4ss.zip"
    if not archive.exists() or digest(archive) != dep["archive_sha256"]:
        request = urllib.request.Request(dep["url"], headers={"User-Agent": "PBZHitEnhance-build"})
        with urllib.request.urlopen(request, timeout=120) as source, archive.open("wb") as target:
            shutil.copyfileobj(source, target)
    if digest(archive) != dep["archive_sha256"]:
        raise RuntimeError("UE4SS archive checksum mismatch")
    return archive, dep


def main():
    version = (ROOT / "VERSION").read_text().strip()
    base = ROOT / "build/package"
    if base.exists():
        raise RuntimeError("Package directory already exists; use a clean build/package directory")
    panel = ROOT / "build/panel/HitstopPanel"
    if not (panel / "HitstopPanel.exe").is_file():
        raise RuntimeError("Standalone panel has not been built")
    metadata = json.loads((ROOT / "dependencies.json").read_text())
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    sums = []
    for mode in MODES:
        package = base / mode
        package.mkdir(parents=True)
        if mode == "with-UE4SS":
            data = package / "PBZHitEnhance"
            runtime = data / "ue4ss"
            runtime.mkdir(parents=True)
            archive, dep = obtain_runtime()
            with zipfile.ZipFile(archive) as source:
                for name in [
                    "UE4SS.dll",
                    "MemberVariableLayout.ini",
                    "UE4SS_Signatures/GNatives.lua",
                    "UE4SS_Signatures/GUObjectArray.lua",
                    "LICENSE",
                ]:
                    target = runtime / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.read("ue4ss/" + name))
            if digest(runtime / "UE4SS.dll") != dep["dll_sha256"]:
                raise RuntimeError("UE4SS DLL checksum mismatch")
            shutil.copy2(ROOT / "runtime-settings.ini", runtime / "UE4SS-settings.ini")
            mod = runtime / "Mods/UnifiedHitstop"
            (runtime / "Mods").mkdir(exist_ok=True)
            (runtime / "Mods/mods.txt").write_text("UnifiedHitstop : 1\n", encoding="utf-8")
            (data / "logs").mkdir()
            (data / "temp").mkdir()
            shutil.copy2(ROOT / "build/native/Release/dwmapi.dll", package / "dwmapi.dll")
        else:
            mod = package / "UnifiedHitstop"
        shutil.copytree(ROOT / "mod/UnifiedHitstop", mod)
        shutil.copytree(panel, mod / "panel")
        shutil.copy2(
            ROOT / "build/native/Release/PBZBootstrap.dll", mod / "Scripts/PBZBootstrap.dll"
        )
        shutil.copy2(ROOT / "dependencies.json", mod / "dependencies.json")
        (mod / "install-mode.txt").write_text(mode + "\n", encoding="utf-8")
        (mod / "temp").mkdir()
        (package / "package.json").write_text(
            json.dumps(
                {"mode": mode, "version": version, "game_hash": metadata["game"]["exe_sha256"]},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        for name in ["LICENSE", "THIRD_PARTY_NOTICES.md"]:
            shutil.copy2(ROOT / name, package / name)
        (package / "README.md").write_text(
            (ROOT / "docs" / ("INSTALL_" + mode + ".md")).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        licenses = mod / "licenses"
        licenses.mkdir()
        python = Path(sys.base_prefix)
        if (python / "LICENSE.txt").exists():
            shutil.copy2(python / "LICENSE.txt", licenses / "Python-LICENSE.txt")
        for name in ["tcl", "tk"]:
            for source in (python / "tcl").glob(name + "*/license.terms"):
                shutil.copy2(source, licenses / (source.parent.name + "-license.terms"))
        manifest = {
            p.relative_to(package).as_posix(): digest(p)
            for p in sorted(package.rglob("*"))
            if p.is_file()
        }
        forbidden = {".ps1", ".bat", ".cmd", ".py", ".pdb", ".lib", ".exp", ".zip"}
        # PyInstaller's standard-library archive is required by the panel runtime.
        runtime_zip = (mod / "panel/_internal/base_library.zip").relative_to(package).as_posix()
        unexpected = [
            name
            for name in manifest
            if Path(name).suffix.lower() in forbidden and name != runtime_zip
        ]
        if unexpected:
            raise RuntimeError("Non-runtime files in package: " + repr(unexpected))
        (package / "package_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        target = destination / f"PBZHitEnhance-v{version}-{mode}-windows-x64.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as output:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    output.write(path, path.relative_to(package).as_posix())
        sums.append(digest(target) + "  " + target.name)
        print("Release archive:", target)
    (destination / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
