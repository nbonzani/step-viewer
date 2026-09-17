@echo off
rem Équivalent Windows de build.sh (emsdk attendu dans wasm\build\emsdk, sources dans wasm\build\occt-import-js).
rem Attention : sur un poste avec antivirus temps réel, la compilation (4 800 objets) peut être extrêmement lente ;
rem préférer le workflow GitHub Actions .github/workflows/build-wasm.yml.
set "ROOT=%~dp0"
set "EMSDK=%ROOT%build\emsdk"
set "PATH=%EMSDK%\upstream\emscripten;%EMSDK%\node\24.19.0_64bit\bin;%EMSDK%\python\3.13.3_64bit;%ROOT%..\.venv\Scripts;%PATH%"
set "EMSDK_NODE=%EMSDK%\node\24.19.0_64bit\bin\node.exe"
set "EMSDK_PYTHON=%EMSDK%\python\3.13.3_64bit\python.exe"
copy /y "%ROOT%importer-xcaf.cpp" "%ROOT%build\occt-import-js\occt-import-js\src\importer-xcaf.cpp" >nul
cd /d "%ROOT%build\occt-import-js"
call emcmake.bat cmake -B "%ROOT%build\wasm" -G Ninja -DEMSCRIPTEN=1 -DCMAKE_BUILD_TYPE=Release -DCMAKE_NINJA_FORCE_RESPONSE_FILE=ON . || exit /b 1
cmake --build "%ROOT%build\wasm" -j %NUMBER_OF_PROCESSORS% || exit /b 1
if not exist "%ROOT%out" mkdir "%ROOT%out"
copy /y "%ROOT%build\wasm\Release\occt-import-js.js" "%ROOT%out\" >nul
copy /y "%ROOT%build\wasm\Release\occt-import-js.wasm" "%ROOT%out\" >nul
echo BUILD OK
