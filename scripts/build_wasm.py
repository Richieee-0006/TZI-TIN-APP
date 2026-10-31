#!/usr/bin/env python3
"""
Skript pro sestavení WebAssembly modulu (wasm/quiz_core.ts -> ui/quiz.wasm).
Deklarace využití AI: Vytvořeno s pomocí AI asistenta.
"""
import base64
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "wasm" / "quiz_core.ts"
OUT = ROOT / "ui" / "quiz.wasm"


def build_wasm() -> bytes:
    cmd = [
        "npx.cmd" if sys.platform == "win32" else "npx",
        "-p", "assemblyscript",
        "asc",
        str(SRC),
        "-o", str(OUT),
        "--optimize",
        "--runtime", "stub",
        "--initialMemory", "1",
    ]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"WASM build failed:\n{res.stdout}\n{res.stderr}")
    data = OUT.read_bytes()
    print(f"[WASM] Sestaveno {OUT.name} ({len(data)} bajtů), base64 délka: {len(base64.b64encode(data))}")
    return data


if __name__ == "__main__":
    build_wasm()
