"""Generate x64 forwarding stubs from a reviewed export list."""

import argparse
import json
from pathlib import Path


def generate(reference, destination):
    exports = json.loads(reference.read_text(encoding="utf-8"))["exports"]
    destination.mkdir(parents=True, exist_ok=True)
    lines = ["LIBRARY dwmapi", "EXPORTS"]
    asm = [".code", "extern mProcs:QWORD"]
    assign = []
    for i, item in enumerate(exports):
        stub = f"Forward_{i}"
        entry = f"{item['name']}={stub}" if item["name"] else stub
        line = f"    {entry} @{item['ordinal']}"
        if not item["name"]:
            line += " NONAME"
        if item["name"] in ("DllCanUnloadNow", "DllGetClassObject"):
            line += " PRIVATE"
        lines.append(line)
        asm.extend([f"{stub} proc", f"    jmp mProcs[8*{i}]", f"{stub} endp"])
        getter = (
            '"' + item["name"] + '"' if item["name"] else f"MAKEINTRESOURCEA({item['ordinal']})"
        )
        assign.append(
            f"    mProcs[{i}]=reinterpret_cast<uintptr_t>(GetProcAddress(original,{getter}));\n    if (!mProcs[{i}]) mProcs[{i}]=reinterpret_cast<uintptr_t>(&missing_export);"
        )
    asm.append("end")
    (destination / "dwmapi.def").write_text("\n".join(lines) + "\n", encoding="ascii")
    (destination / "forward.asm").write_text("\n".join(asm) + "\n", encoding="ascii")
    (destination / "exports.inc").write_text(
        'extern "C" { uintptr_t mProcs['
        + str(len(exports))
        + "]={}; }\nstatic void bind_exports(HMODULE original) {\n"
        + "\n".join(assign)
        + "\n}\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("reference", type=Path)
    p.add_argument("destination", type=Path)
    args = p.parse_args()
    generate(args.reference, args.destination)
