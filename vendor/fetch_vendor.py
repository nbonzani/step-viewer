"""Télécharge les bibliothèques web embarquées dans le viewer HTML (three.js, OrbitControls, occt-import-js)."""
import urllib.request
from pathlib import Path

THREE = "0.186.0"
OCCT = "0.0.23"
FILES = {
    "three.esm.js": f"https://cdn.jsdelivr.net/npm/three@{THREE}/+esm",
    "OrbitControls.js": f"https://cdn.jsdelivr.net/npm/three@{THREE}/examples/jsm/controls/OrbitControls.js",
    "occt-import-js.js": f"https://cdn.jsdelivr.net/npm/occt-import-js@{OCCT}/dist/occt-import-js.js",
    "occt-import-js.wasm": f"https://cdn.jsdelivr.net/npm/occt-import-js@{OCCT}/dist/occt-import-js.wasm",
    "LICENSE.three.txt": f"https://cdn.jsdelivr.net/npm/three@{THREE}/LICENSE",
    "LICENSE.occt-import-js.txt": f"https://cdn.jsdelivr.net/npm/occt-import-js@{OCCT}/dist/license.occt-import-js.txt",
    "LICENSE.occt.txt": f"https://cdn.jsdelivr.net/npm/occt-import-js@{OCCT}/dist/license.occt.txt",
}

here = Path(__file__).resolve().parent
for name, url in FILES.items():
    dest = here / name
    print(f"{name:32s} <- {url}")
    urllib.request.urlretrieve(url, dest)
    print(f"{'':32s}    {dest.stat().st_size / 1e6:.2f} Mo")
