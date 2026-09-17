# STEP Viewer

Deux visionneuses STEP minimalistes : on lance, une fenêtre s'ouvre, on glisse le `.step` / `.stp` dedans.
Couleurs XCAF du fichier (couleurs par corps et par face), affichage ombré avec arêtes, manipulation 3D complète.

| | `html/dist/STEP_Viewer.html` | `qt/step_viewer_qt.py` |
|---|---|---|
| Techno | Fichier HTML unique — three.js + occt-import-js *patché* (OpenCASCADE 7.6 en WebAssembly) | PyQt6 + OpenCASCADE natif (`cadquery-ocp`) |
| Dépendances | Aucune : s'ouvre dans Edge/Chrome, hors ligne | Python 3.12 + `pip install -r requirements.txt` (~600 Mo installés) |
| Taille | 5 Mo | — |
| Arêtes | Frontières de faces recalculées sur le maillage | Vraies arêtes topologiques B-rep |
| Mode « vives » | Angle dièdre > 20° | Continuité ≤ C0 (`FaceBoundaryUpperContinuity`) |
| Lecture | Dans un Web Worker (interface non bloquée) | Synchrone (curseur d'attente) |
| Arborescence | Complète (importateur patché, voir `wasm/`) | Complète (`XCAFPrs_DocumentExplorer`, instances placées) |
| Couleurs de faces | Conservées, y compris sur les instances (importateur patché) | Conservées |

## Utilisation

### Viewer HTML
Double-cliquer sur `html/dist/STEP_Viewer.html`, puis glisser un fichier STEP dans la fenêtre (ou **Ouvrir…** / `Ctrl+O`).

### Viewer PyQt6 + OCP
```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python qt\step_viewer_qt.py [fichier.step]
```
Ou `qt\STEP_Viewer.bat` (lance sans console via le `.venv` du projet).
`--dump capture.png` rend le fichier passé en argument puis quitte (captures en lot).

### Commandes (identiques dans les deux viewers)

| Action | Souris / touche |
|---|---|
| Rotation | clic gauche glissé |
| Panoramique | clic droit ou molette enfoncée, glissé |
| Zoom au curseur | molette |
| Ajuster au modèle | `F` ou double-clic |
| Vues (menu **Vue**) | `0` iso · `1` face · `2` arrière · `3` dessus · `4` dessous · `5` gauche · `6` droite |
| Arborescence (panneau gauche) | `T` — une case par pièce / sous-ensemble, masquage en cascade, état partiel sur les parents |
| Sélection | clic dans la vue ou sur une ligne ; `Ctrl` ajoute, `Maj` étend (plage) ; la sélection est synchronisée arborescence ↔ vue 3D |
| Cacher / afficher la sélection | `H` / menu contextuel (clic droit dans la vue ou sur l'arborescence) ; cocher une ligne sélectionnée s'applique à toute la sélection |
| Tout afficher | `Ctrl+H` |
| Arêtes : toutes → vives → aucune | `E` |
| Perspective / orthographique | `P` |
| Ouvrir | `Ctrl+O` |

## Reconstruire le HTML

```bash
python vendor/fetch_vendor.py     # télécharge three.js 0.186, OrbitControls (+ licences, + occt-import-js amont en secours)
python html/build_html.py         # assemble html/dist/STEP_Viewer.html depuis html/src/viewer.html
```
`build_html.py` embarque l'occt-import-js **patché** de `wasm/out/` (sinon la version amont de `vendor/`).
Le WASM (7,6 Mo) est embarqué gzippé en base64 et décompressé à l'exécution (`DecompressionStream`).
Les bibliothèques sont chargées via des blob URLs : aucun accès réseau, fonctionne en `file://`.

### occt-import-js patché (`wasm/`)

`wasm/importer-xcaf.cpp` remplace l'importateur XCAF d'occt-import-js 0.0.23 : la hiérarchie suit la structure
d'assemblage XCAF (composants récursifs, localisation cumulée) et les maillages sont construits sur les *prototypes*
non localisés, ce qui rend les couleurs de faces des pièces instanciées et le nom des occurrences.
Compilation (OCCT 7.6.1 complet + Emscripten 3.1.69, ~4 800 objets) :

- **GitHub Actions** (recommandé) : workflow `build-wasm` (déclenché par un push sur `wasm/**` ou à la main),
  artefact `occt-import-js-patched` → à copier dans `wasm/out/` puis `python html/build_html.py` ;
- Linux : `bash wasm/build.sh` ; Windows : `wasm/build_wasm.cmd` (emsdk dans `wasm/build/emsdk`) — très lent sur un
  poste avec antivirus temps réel (E/S bloquantes sur les ~250 répertoires d'include).

## Tests

```bash
.venv\Scripts\python tests\make_sample.py     # régénère tests/sample.step (2 corps), assembly.step (Ensemble > Sous-ensemble > Plaque, Axe + 2e Axe) et box.step
.venv\Scripts\python tests\qt_smoke.py <dossier>   # viewer Qt : dépôt, rotation, pan, zoom, vues, arêtes, projection → captures
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python tests\html_selftest.py [capture.png]   # viewer HTML sous file:// avec l'Edge installé (Playwright)
```
Ouvrir `STEP_Viewer.html#selftest` charge un STEP embarqué et affiche le verdict dans la barre d'état.

## Notes techniques

- **OCP sous Windows** : `WNT_Window` attend une *capsule* contenant le HWND (`ctypes.pythonapi.PyCapsule_New`).
- **PyQt6** : sans `sys.excepthook` explicite, toute exception dans un slot termine le processus sans message (`qFatal`).
- **Arêtes HTML** : occt-import-js ne fournit pas les arêtes B-rep ; elles sont déduites des `brep_faces`
  (une arête de maillage partagée par deux faces différentes, ou libre, est une arête).
- **Hiérarchie HTML** : l'occt-import-js amont (0.0.23) parcourt les labels TDF et non la structure d'assemblage
  (sous-ensembles instanciés aplatis, couleurs de faces perdues sur les instances) ; corrigé par l'importateur patché
  de `wasm/`. Le viewer garde la simplification « un nœud à plusieurs maillages → une ligne par maillage » pour rester
  compatible avec la version amont.
- **Couleurs HTML** : occt-import-js renvoie les `Quantity_Color` d'OCCT, déjà en RGB linéaire — pas de conversion sRGB
  côté three.js (les attributs `color` sont attendus en linéaire).
