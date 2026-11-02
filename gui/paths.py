"""Resolve writable Mod data without machine-specific paths."""

import argparse
import os
import sys
from pathlib import Path


def mod_root():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mod-dir")
    options, _ = parser.parse_known_args()
    if options.mod_dir:
        return Path(options.mod_dir).resolve()
    if os.environ.get("PBZ_HITSTOP_MOD_DIR"):
        return Path(os.environ["PBZ_HITSTOP_MOD_DIR"]).resolve()
    if getattr(sys, "frozen", False):
        folder = Path(sys.executable).resolve().parent.parent
        if (folder / "Scripts").is_dir():
            return folder
        return folder / "ue4ss" / "Mods" / "UnifiedHitstop"
    return Path(__file__).resolve().parents[1] / "mod" / "UnifiedHitstop"
