#!/usr/bin/env bash
# Compile occt-import-js avec l'importateur XCAF patché (wasm/importer-xcaf.cpp) en WebAssembly.
# Prérequis : emsdk activé (emcc dans le PATH), cmake, ninja, git. Sortie : wasm/out/occt-import-js.{js,wasm}
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OCCT_IMPORT_JS_COMMIT="${OCCT_IMPORT_JS_COMMIT:-41e4708}"      # occt-import-js 0.0.23
OCCT_COMMIT="d2abb6d844231cb8f29be6894440874a4700e4a5"          # OCCT 7.6.1, submodule épinglé par occt-import-js
SRC="$HERE/build/occt-import-js"
mkdir -p "$HERE/build"
if [ ! -d "$SRC" ]; then
  git clone --depth 1 https://github.com/kovacsv/occt-import-js.git "$SRC"
  git -C "$SRC" checkout -q "$OCCT_IMPORT_JS_COMMIT" || true
  git -C "$SRC/occt" init -q
  git -C "$SRC/occt" remote add origin https://github.com/Open-Cascade-SAS/OCCT.git
  git -C "$SRC/occt" fetch -q --depth 1 origin "$OCCT_COMMIT"
  git -C "$SRC/occt" checkout -q FETCH_HEAD
fi
cp "$HERE/importer-xcaf.cpp" "$SRC/occt-import-js/src/importer-xcaf.cpp"
emcmake cmake -S "$SRC" -B "$HERE/build/wasm" -G Ninja -DEMSCRIPTEN=1 -DCMAKE_BUILD_TYPE=Release
cmake --build "$HERE/build/wasm" -j "$(nproc)"
mkdir -p "$HERE/out"
cp "$HERE/build/wasm/Release/occt-import-js.js" "$HERE/build/wasm/Release/occt-import-js.wasm" "$HERE/out/"
ls -la "$HERE/out"
