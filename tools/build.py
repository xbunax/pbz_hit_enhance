"""Build the native loader, standalone panel, and release archive on Windows."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-only", action="store_true")
    args = parser.parse_args()
    temporary = ROOT / "build/temp"
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(temporary)
    os.environ["TMP"] = str(temporary)
    run(
        "cmake",
        "-S",
        ROOT,
        "-B",
        ROOT / "build/native",
        "-G",
        "Visual Studio 17 2022",
        "-A",
        "x64",
        f"-DPython3_EXECUTABLE={sys.executable}",
    )
    run("cmake", "--build", ROOT / "build/native", "--config", "Release", "--parallel")
    if args.native_only:
        return
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "HitstopPanel",
        "--distpath",
        ROOT / "build/panel",
        "--workpath",
        ROOT / "build/pyinstaller",
        "--specpath",
        ROOT / "build",
        "--paths",
        ROOT / "gui",
        ROOT / "gui/panel.py",
    )
    run(sys.executable, ROOT / "tools/package_release.py")
    run(sys.executable, ROOT / "tools/verify_release.py", ROOT / "build/package")


if __name__ == "__main__":
    main()
