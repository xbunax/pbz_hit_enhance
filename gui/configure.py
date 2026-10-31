"""Atomic configuration updates; does not access game memory."""

import argparse, math, os
from paths import mod_root

ROOT = mod_root()
PATH = ROOT / "config.ini"
BASE_KEYS = ("Enabled", "Mode", "Scale", "AddFrames", "FixedFrames", "MaxFrames")
PROFILES = ("Blade", "DoubleBlade", "GreatBlade")
PROFILE_KEYS = ("Override", "Mode", "Scale", "AddFrames", "FixedFrames", "MaxFrames")
KEYS = (*BASE_KEYS, "ObserveOnly", *(p + "." + k for p in PROFILES for k in PROFILE_KEYS))
BASE_DEFAULT = dict(zip(BASE_KEYS, ("true", "scale", "1", "1", "5", "30")))


def defaults():
    c = dict(BASE_DEFAULT, ObserveOnly="false")
    for profile in PROFILES:
        for key in PROFILE_KEYS:
            c[profile + "." + key] = "false" if key == "Override" else BASE_DEFAULT[key]
    return c


def parse(raw):
    c = {}
    for line in raw.lstrip("\ufeff").splitlines():
        line = line.split(";", 1)[0].split("#", 1)[0].strip()
        if line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in c:
                raise ValueError("Duplicate key: " + k)
            c[k] = v
    validate(c)
    return defaults() | c


def read():
    return parse(PATH.read_text(encoding="utf-8-sig"))


def validate_values(c):
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


def validate(c):
    if not set(BASE_KEYS) <= set(c) or not set(c) <= set(KEYS):
        raise ValueError("Unexpected or missing config keys")
    if c["Enabled"] not in ("true", "false") or c.get("ObserveOnly", "false") not in (
        "true",
        "false",
    ):
        raise ValueError("Invalid enable/observation setting")
    validate_values(c)
    for profile in PROFILES:
        values = {k: c[profile + "." + k] for k in PROFILE_KEYS if profile + "." + k in c}
        if not values:
            continue
        if set(values) != set(PROFILE_KEYS):
            raise ValueError("Incomplete profile: " + profile)
        if values["Override"] not in ("true", "false"):
            raise ValueError("Invalid profile override: " + profile)
        validate_values(values)


def serialize(c):
    validate(c)
    c = defaults() | c
    return (
        "; UnifiedHitstop. Hot reload ~1 second.\n" + "\n".join(k + "=" + c[k] for k in KEYS) + "\n"
    )


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
    c = defaults() if a.reset else read()
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
            tmp.write_text(serialize(c), encoding="utf-8")
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
