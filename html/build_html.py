"""Assemble html/dist/STEP_Viewer.html : fichier HTML unique, sans dépendance réseau.

Embarque three.js (bundle ESM), OrbitControls, occt-import-js et son WASM (gzip + base64).
Les sources sont lues dans ../vendor (python vendor/fetch_vendor.py pour les récupérer).
"""
import base64
import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
SRC = ROOT / "html" / "src" / "viewer.html"
OUT = ROOT / "html" / "dist" / "STEP_Viewer.html"

ASSETS = {
    "THREE": VENDOR / "three.esm.js",
    "ORBIT": VENDOR / "OrbitControls.js",
    "OCCT": VENDOR / "occt-import-js.js",
}
WASM = VENDOR / "occt-import-js.wasm"
SELFTEST_STEP = ROOT / "tests" / "box.step"


def main():
    html = SRC.read_text(encoding="utf-8")
    for key, path in ASSETS.items():
        text = path.read_text(encoding="utf-8")
        if "</script" in text.lower():
            sys.exit(f"{path.name} contient '</script' : impossible de l'inliner tel quel.")
        html = html.replace("{{" + key + "}}", text)
    wasm_b64 = base64.b64encode(gzip.compress(WASM.read_bytes(), 9)).decode("ascii")
    html = html.replace("{{WASM_B64}}", wasm_b64)
    html = html.replace("{{SELFTEST_B64}}", base64.b64encode(gzip.compress(SELFTEST_STEP.read_bytes(), 9)).decode("ascii"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"Écrit : {OUT} ({OUT.stat().st_size / 1e6:.1f} Mo)")


if __name__ == "__main__":
    main()
