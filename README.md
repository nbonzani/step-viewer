# STEP Viewer

Deux visionneuses STEP minimalistes : on lance, une fenêtre s'ouvre, on glisse le `.step` / `.stp` dedans.
Couleurs XCAF du fichier (couleurs par corps et par face), affichage ombré avec arêtes, manipulation 3D complète.

| | `html/dist/STEP_Viewer.html` | `qt/step_viewer_qt.py` |
|---|---|---|
| Techno | Fichier HTML unique — three.js + occt-import-js (OpenCASCADE en WebAssembly) | PyQt6 + OpenCASCADE natif (`cadquery-ocp`) |
| Dépendances | Aucune : s'ouvre dans Edge/Chrome, hors ligne | Python 3.12 + `pip install -r requirements.txt` (~600 Mo installés) |
| Taille | 5 Mo | — |
| Arêtes | Frontières de faces recalculées sur le maillage | Vraies arêtes topologiques B-rep |
| Mode « vives » | Angle dièdre > 20° | Continuité ≤ C0 (`FaceBoundaryUpperContinuity`) |
| Lecture | Dans un Web Worker (interface non bloquée) | Synchrone (curseur d'attente) |
| Arborescence | Limitée au niveau des références (voir *Notes techniques*) | Complète (`XCAFPrs_DocumentExplorer`, instances placées) |
| Couleurs de faces | Perdues sur les pièces instanciées dans un assemblage | Conservées |

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
| Arêtes : toutes → vives → aucune | `E` |
| Perspective / orthographique | `P` |
| Ouvrir | `Ctrl+O` |

## Reconstruire le HTML

```bash
python vendor/fetch_vendor.py     # télécharge three.js 0.186, OrbitControls, occt-import-js 0.0.23 (+ licences)
python html/build_html.py         # assemble html/dist/STEP_Viewer.html depuis html/src/viewer.html
```
Le WASM (7,6 Mo) est embarqué gzippé en base64 et décompressé à l'exécution (`DecompressionStream`).
Les bibliothèques sont chargées via des blob URLs : aucun accès réseau, fonctionne en `file://`.

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
- **Hiérarchie HTML** : occt-import-js (0.0.23, `importer-xcaf.cpp`) parcourt les labels TDF, pas la structure
  d'assemblage : une occurrence de sous-ensemble devient un nœud portant directement les solides localisés (affichés
  ici comme lignes filles nommées), et la recherche de couleur XCAF échoue sur les faces localisées → couleurs de faces
  perdues pour les pièces instanciées (la couleur de corps est conservée). Le viewer Qt n'a pas ces limites.
- **Couleurs HTML** : occt-import-js renvoie les `Quantity_Color` d'OCCT, déjà en RGB linéaire — pas de conversion sRGB
  côté three.js (les attributs `color` sont attendus en linéaire).
