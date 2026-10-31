"""Atomic configuration updates; does not access game memory."""

import argparse, math, os
from paths import mod_root

ROOT = mod_root()
PATH = ROOT / "config.ini"
KEYS = ("Enabled", "Mode", "Scale", "AddFrames", "FixedFrames", "MaxFrames")


def read():
    c = {}
    for line in PATH.read_text(encoding="utf-8-sig").splitlines():
        line = line.split(";", 1)[0].split("#", 1)[0].strip()
        if line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k in c:
                raise ValueError("Duplicate key: " + k)
            c[k] = v
    return c


def validate(c):
    if set(c) != set(KEYS):
        raise ValueError("Unexpected or missing config keys")
    if c["Enabled"] not in ("true", "false"):
        raise ValueError("Invalid Enabled")
    if c["Mode"] not in ("scale", "add", "fixed"):
        raise ValueError("Invalid Mode")
    for k, lo, hi, integer in [
        ("Scale", 0, 4, False),
        ("AddFrames", -30, 30, True),
        ("FixedFrames", 0, 30, True),
        ("MaxFrames", 0, 30, True),
    ]:
        n = float(c[k])
        if not math.isfinite(n) or not lo <= n <= hi or (integer and n != int(n)):
            raise ValueError("Invalid " + k)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--enabled", choices=["true", "false"])
    p.add_argument("--mode", choices=["scale", "add", "fixed"])
    p.add_argument("--scale", type=float)
    p.add_argument("--add-frames", type=int)
    p.add_argument("--fixed-frames", type=int)
    p.add_argument("--max-frames", type=int)
    p.add_argument("--reset", action="store_true")
    a = p.parse_args()
    c = (
        {
            "Enabled": "true",
            "Mode": "scale",
            "Scale": "1",
            "AddFrames": "1",
            "FixedFrames": "5",
            "MaxFrames": "30",
        }
        if a.reset
        else read()
    )
    change = a.reset
    for arg, key in [
        ("enabled", "Enabled"),
        ("mode", "Mode"),
        ("scale", "Scale"),
        ("add_frames", "AddFrames"),
        ("fixed_frames", "FixedFrames"),
        ("max_frames", "MaxFrames"),
    ]:
        v = getattr(a, arg)
        if v is not None:
            c[key] = str(v)
            change = True
    validate(c)
    if change:
        tmp = ROOT / f"config.{os.getpid()}.tmp"
        try:
            tmp.write_text(
                "; UnifiedHitstop. Hot reload ~1 second. See README.md.\n"
                + "\n".join(k + "=" + c[k] for k in KEYS)
                + "\n",
                encoding="utf-8",
            )
            os.replace(tmp, PATH)
        finally:
            if tmp.exists():
                tmp.unlink()
    print("\n".join(k + "=" + c[k] for k in KEYS))
    print(
        "Configuration saved; running Mod applies it on its next poll."
        if change
        else "Configuration only. This does not prove the Mod is loaded."
    )


if __name__ == "__main__":
    main()
