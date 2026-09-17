"""STEP Viewer — PyQt6 + OpenCASCADE natif (cadquery-ocp).

Lancement :  python step_viewer_qt.py [fichier.step]
Capture :    python step_viewer_qt.py fichier.step --dump sortie.png   (rendu hors interaction, puis sortie)

Interaction : clic gauche = rotation, clic droit / molette enfoncée = panoramique, molette = zoom au curseur,
              double-clic = ajuster. Raccourcis : F ajuster, E arêtes (toutes/vives/aucune), P perspective/ortho,
              T arborescence, 0 iso, 1 face, 2 arrière, 3 dessus, 4 dessous, 5 gauche, 6 droite, Ctrl+O ouvrir.
Arborescence : dock à gauche, une case à cocher par pièce / sous-ensemble (masquage en cascade).
"""
from __future__ import annotations

import ctypes
import sys
import time
import traceback
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QDockWidget, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QStackedLayout,
    QToolBar, QToolButton, QTreeWidget, QTreeWidgetItem, QWidget,
)

from OCP.AIS import AIS_InteractiveContext, AIS_Shaded
from OCP.Aspect import Aspect_DisplayConnection, Aspect_GradientFillMethod, Aspect_TypeOfTriedronPosition
from OCP.GeomAbs import GeomAbs_C0, GeomAbs_CN
from OCP.Graphic3d import Graphic3d_Camera
from OCP.IFSelect import IFSelect_RetDone
from OCP.OpenGl import OpenGl_GraphicDriver
from OCP.Quantity import Quantity_Color, Quantity_NOC_BLACK, Quantity_NOC_WHITE, Quantity_TOC_sRGB
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.V3d import V3d_AmbientLight, V3d_DirectionalLight, V3d_TypeOfOrientation, V3d_TypeOfVisualization, V3d_Viewer
from OCP.gp import gp_Dir
from OCP.WNT import WNT_Window
from OCP.XCAFPrs import XCAFPrs_AISObject, XCAFPrs_DocumentExplorer, XCAFPrs_DocumentExplorerFlags_None

STEP_EXT = (".step", ".stp")

VIEWS = {
    "iso": V3d_TypeOfOrientation.V3d_XposYnegZpos,
    "front": V3d_TypeOfOrientation.V3d_Yneg,
    "back": V3d_TypeOfOrientation.V3d_Ypos,
    "top": V3d_TypeOfOrientation.V3d_Zpos,
    "bottom": V3d_TypeOfOrientation.V3d_Zneg,
    "left": V3d_TypeOfOrientation.V3d_Xneg,
    "right": V3d_TypeOfOrientation.V3d_Xpos,
}
VIEW_LABELS = (("0", "Isométrique", "iso"), ("1", "Face", "front"), ("2", "Arrière", "back"), ("3", "Dessus", "top"),
               ("4", "Dessous", "bottom"), ("5", "Gauche", "left"), ("6", "Droite", "right"))
EDGE_MODES = ("all", "sharp", "none")
EDGE_LABELS = {"all": "Arêtes : toutes", "sharp": "Arêtes : vives", "none": "Arêtes : aucune"}


def hwnd_capsule(hwnd: int):
    """Encapsule un HWND dans une PyCapsule, format attendu par WNT_Window (OCP)."""
    new = ctypes.pythonapi.PyCapsule_New
    new.restype = ctypes.py_object
    new.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    return new(hwnd, None, None)


def srgb(r: float, g: float, b: float) -> Quantity_Color:
    return Quantity_Color(r, g, b, Quantity_TOC_sRGB)


# ---------------------------------------------------------------------------
# Lecture STEP (XCAF : couleurs, noms, assemblages)
# ---------------------------------------------------------------------------
def label_name(label) -> str:
    attr = TDataStd_Name()
    return attr.Get().ToExtString().strip() if label.FindAttribute(TDataStd_Name.GetID_s(), attr) else ""


def node_name(node) -> str:
    """Nom de l'occurrence, sinon du prototype (le lecteur STEP nomme les instances « =>[0:1:1:2] »)."""
    name = label_name(node.Label)
    if not name or name.startswith("=>"):
        name = label_name(node.RefLabel)
    return name or "Sans nom"


class TreeNode:
    """Nœud de l'arborescence d'assemblage : une occurrence XCAF (feuille = objet AIS affichable)."""

    def __init__(self, name: str, is_assembly: bool):
        self.name = name
        self.is_assembly = is_assembly
        self.children: list[TreeNode] = []
        self.ais: XCAFPrs_AISObject | None = None


def explore(doc: TDocStd_Document) -> TreeNode:
    """Parcourt le document XCAF (occurrences avec localisation cumulée) et crée un objet AIS par feuille."""
    root = TreeNode("", True)
    stack = [root]                       # stack[d] = parent des nœuds de profondeur d
    explorer = XCAFPrs_DocumentExplorer(doc, XCAFPrs_DocumentExplorerFlags_None)
    while explorer.More():
        n = explorer.Current()
        depth = explorer.CurrentDepth()
        node = TreeNode(node_name(n), n.IsAssembly)
        if not n.IsAssembly:
            node.ais = XCAFPrs_AISObject(n.RefLabel)      # prototype (couleurs, sous-formes) …
            node.ais.SetLocalTransformation(n.Location.Transformation())   # … placé par la localisation cumulée
        del stack[depth + 1:]
        stack[depth].children.append(node)
        stack.append(node)
        explorer.Next()
    if not any(True for _ in iter_leaves(root)):
        raise ValueError("aucune forme dans le fichier")
    return root


def iter_leaves(node: TreeNode):
    if node.ais is not None:
        yield node
    for c in node.children:
        yield from iter_leaves(c)


def read_step(path: str) -> TDocStd_Document:
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(True)
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise ValueError("fichier STEP illisible ou invalide")
    if not reader.Transfer(doc):
        raise ValueError("transfert STEP → XCAF échoué")
    return doc


# ---------------------------------------------------------------------------
# Widget de vue OpenCASCADE
# ---------------------------------------------------------------------------
class OccView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(320, 240)
        self._ready = False
        self._last = QPoint()
        self._mode = None            # 'rotate' | 'pan'
        self.doc = None              # conserve le document XCAF (les AIS y font référence)
        self.tree: TreeNode | None = None
        self.objects: list[XCAFPrs_AISObject] = []
        self.edge_mode = "all"
        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(0)
        self._redraw_timer.timeout.connect(lambda: self.view.Redraw())

    def paintEngine(self):
        return None

    # --- initialisation différée : nécessite un HWND valide --------------------
    def _init(self):
        self.driver = OpenGl_GraphicDriver(Aspect_DisplayConnection(), False)
        self.viewer = V3d_Viewer(self.driver)
        # éclairage : ambiance + projecteur solidaire de la caméra, légèrement en haut à gauche
        ambient = V3d_AmbientLight(Quantity_Color(Quantity_NOC_WHITE))
        ambient.SetIntensity(0.35)
        head = V3d_DirectionalLight(gp_Dir(-0.3, -0.5, -1.0), Quantity_Color(Quantity_NOC_WHITE), True)
        head.SetIntensity(1.1)
        self.viewer.AddLight(ambient)
        self.viewer.AddLight(head)
        self.viewer.SetLightOn()
        self.view = self.viewer.CreateView()
        self.window = WNT_Window(hwnd_capsule(int(self.winId())))
        self.view.SetWindow(self.window)
        if not self.window.IsMapped():
            self.window.Map()
        self.view.SetBgGradientColors(srgb(0.87, 0.90, 0.93), srgb(0.55, 0.60, 0.66),
                                      Aspect_GradientFillMethod.Aspect_GradientFillMethod_Vertical, False)
        self.view.TriedronDisplay(Aspect_TypeOfTriedronPosition.Aspect_TOTP_RIGHT_LOWER,
                                  Quantity_Color(Quantity_NOC_BLACK), 0.08, V3d_TypeOfVisualization.V3d_ZBUFFER)
        params = self.view.ChangeRenderingParams()
        params.NbMsaaSamples = 4
        params.IsAntialiasingEnabled = True
        params.RenderResolutionScale = 1.0

        self.ctx = AIS_InteractiveContext(self.viewer)
        self.ctx.SetDisplayMode(AIS_Shaded, False)
        self.ctx.SetDeviationCoefficient(0.0003)     # finesse de tessellation
        drawer = self.ctx.DefaultDrawer()
        drawer.SetFaceBoundaryDraw(True)
        drawer.FaceBoundaryAspect().SetColor(srgb(0.10, 0.12, 0.15))
        drawer.FaceBoundaryAspect().SetWidth(1.0)
        self.view.SetProj(VIEWS["iso"])
        self._ready = True

    # --- événements Qt ---------------------------------------------------------
    def showEvent(self, e):
        if not self._ready:
            self._init()
        super().showEvent(e)

    def paintEvent(self, e):
        if self._ready:
            self.view.Redraw()

    def resizeEvent(self, e):
        if self._ready:
            self.view.MustBeResized()

    def mousePressEvent(self, e):
        self._last = e.position().toPoint()
        b = e.button()
        if b == Qt.MouseButton.LeftButton:
            self._mode = "rotate"
            self.view.StartRotation(self._last.x(), self._last.y())
        elif b in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._mode = "pan"
        self.setFocus()

    def mouseReleaseEvent(self, e):
        self._mode = None

    def mouseMoveEvent(self, e):
        if not self._mode:
            return
        p = e.position().toPoint()
        if self._mode == "rotate":
            self.view.Rotation(p.x(), p.y())
        else:
            self.view.Pan(p.x() - self._last.x(), self._last.y() - p.y(), 1.0, True)
        self._last = p

    def wheelEvent(self, e):
        p = e.position().toPoint()
        steps = e.angleDelta().y() / 120.0
        if steps == 0:
            return
        # ZoomAtPoint applique un facteur 1 + |d|/100 (d = déplacement souris en px) : on synthétise d
        factor = 1.15 ** abs(steps)
        d = int(round((factor - 1.0) * 100.0)) * (1 if steps > 0 else -1)
        self.view.StartZoomAtPoint(p.x(), p.y())
        self.view.ZoomAtPoint(0, 0, d, 0)
        self.view.Redraw()

    def mouseDoubleClickEvent(self, e):
        self.fit_all()

    # --- commandes ---------------------------------------------------------------
    def fit_all(self):
        self.view.FitAll(0.02, False)
        self.view.Redraw()

    def set_view(self, name: str):
        self.view.SetProj(VIEWS[name])
        self.fit_all()

    def set_edge_mode(self, mode: str):
        self.edge_mode = mode
        drawer = self.ctx.DefaultDrawer()
        drawer.SetFaceBoundaryDraw(mode != "none")
        drawer.SetFaceBoundaryUpperContinuity(GeomAbs_C0 if mode == "sharp" else GeomAbs_CN)
        for obj in self.objects:
            self.ctx.Redisplay(obj, False)
        self.view.Redraw()

    def toggle_projection(self) -> bool:
        cam = self.view.Camera()
        proj = Graphic3d_Camera.Projection_e
        ortho = cam.ProjectionType() == proj.Projection_Orthographic
        cam.SetProjectionType(proj.Projection_Perspective if ortho else proj.Projection_Orthographic)
        self.view.Redraw()
        return not ortho          # True si désormais perspective

    def load(self, path: str) -> dict:
        t0 = time.perf_counter()
        doc = read_step(path)
        root = explore(doc)
        self.ctx.RemoveAll(False)
        self.objects.clear()
        self.doc = doc
        self.tree = root
        for leaf in iter_leaves(root):
            self.ctx.Display(leaf.ais, AIS_Shaded, -1, False)
            self.objects.append(leaf.ais)
        self.set_view("iso")
        return {"bodies": len(self.objects), "seconds": time.perf_counter() - t0}

    def set_visible(self, ais: XCAFPrs_AISObject, visible: bool):
        if visible:
            self.ctx.Display(ais, AIS_Shaded, -1, False)
        else:
            self.ctx.Erase(ais, False)
        self._redraw_timer.start()          # regroupe les rafraîchissements (cascade de cases à cocher)

    def dump(self, out: str) -> bool:
        return self.view.Dump(out)


# ---------------------------------------------------------------------------
# Fenêtre principale
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("STEP Viewer")
        self.resize(1100, 750)
        self.setAcceptDrops(True)

        self.occ = OccView(self)
        self.hint = QLabel("Glissez un fichier STEP ici\n\n.step / .stp — rotation : clic gauche · "
                           "panoramique : clic droit · zoom : molette", self)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet("background: rgba(255,255,255,0.85); border: 2px dashed #888; border-radius: 12px;"
                                "padding: 28px; font-size: 15px; color: #1d2530;")
        self.hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        container = QWidget(self)
        layout = QStackedLayout(container)
        layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        layout.addWidget(self.hint)
        layout.addWidget(self.occ)
        self.setCentralWidget(container)

        tb = QToolBar("Outils", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        def act(text, slot, key=None, tip=None):
            a = QAction(text, self)
            if key:
                a.setShortcut(QKeySequence(key))
            a.setToolTip(tip or text)
            a.triggered.connect(slot)
            tb.addAction(a)
            self.addAction(a)
            return a

        act("Ouvrir…", self.open_dialog, "Ctrl+O")
        act("Ajuster", self.occ.fit_all, "F")
        tb.addSeparator()
        view_menu = QMenu("Vue", self)
        for key, label, name in VIEW_LABELS:
            a = QAction(label, self)
            a.setShortcut(QKeySequence(key))
            a.triggered.connect(lambda _=False, n=name: self.occ.set_view(n))
            view_menu.addAction(a)
            self.addAction(a)                    # raccourci actif même menu fermé
        view_button = QToolButton(self)
        view_button.setText("Vue")
        view_button.setMenu(view_menu)
        view_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        view_button.setToolTip("Vues standard (0-6)")
        tb.addWidget(view_button)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.itemChanged.connect(self._tree_item_changed)
        self.dock = QDockWidget("Arborescence", self)
        self.dock.setWidget(self.tree)
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)
        self.dock.hide()
        tree_action = self.dock.toggleViewAction()
        tree_action.setText("Arborescence")
        tree_action.setShortcut(QKeySequence("T"))
        tree_action.setToolTip("Afficher / masquer l'arborescence (T)")
        tb.addAction(tree_action)
        self.addAction(tree_action)
        tb.addSeparator()
        self.edge_action = act(EDGE_LABELS["all"], self.cycle_edges, "E", "Arêtes : toutes → vives → aucune (E)")
        self.proj_action = act("Perspective", self.toggle_projection, "P", "Perspective / orthographique (P)")

        self.statusBar().showMessage("Aucun fichier chargé")

    # --- glisser-déposer ---------------------------------------------------------
    def dragEnterEvent(self, e):
        if any(u.toLocalFile().lower().endswith(STEP_EXT) for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p.lower().endswith(STEP_EXT):
                self.load(p)
                break

    # --- actions -------------------------------------------------------------------
    def open_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, "Ouvrir un fichier STEP", "", "STEP (*.step *.stp);;Tous (*)")
        if p:
            self.load(p)

    def load(self, path: str):
        self.statusBar().showMessage(f"Lecture de {Path(path).name}…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            info = self.occ.load(path)
        except Exception as err:  # noqa: BLE001 — remontée utilisateur
            QMessageBox.critical(self, "Erreur", f"Impossible de lire {Path(path).name} :\n{err}")
            self.statusBar().showMessage("Erreur de lecture")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.hint.hide()
        self._fill_tree(self.occ.tree)
        self.setWindowTitle(f"{Path(path).name} — STEP Viewer")
        seconds = f"{info['seconds']:.1f}".replace(".", ",")
        self.statusBar().showMessage(f"{path} — {info['bodies']} corps, {seconds} s")

    # --- arborescence --------------------------------------------------------------
    def _fill_tree(self, root: TreeNode):
        self.tree.blockSignals(True)
        self.tree.clear()

        def add(parent, node: TreeNode):
            item = QTreeWidgetItem(parent, [node.name])
            flags = item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            if node.children:
                flags |= Qt.ItemFlag.ItemIsAutoTristate      # coche/décoche en cascade, état partiel automatique
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
            item.setFlags(flags)
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setData(0, Qt.ItemDataRole.UserRole, node)
            for c in node.children:
                add(item, c)
            return item

        # la racine synthétique n'est pas affichée ; ses enfants sont les formes libres
        for c in root.children:
            add(self.tree, c)
        self.tree.expandAll()
        self.tree.blockSignals(False)
        self.dock.show()

    def _tree_item_changed(self, item: QTreeWidgetItem, column: int):
        node: TreeNode = item.data(0, Qt.ItemDataRole.UserRole)
        if node is not None and node.ais is not None:
            self.occ.set_visible(node.ais, item.checkState(0) == Qt.CheckState.Checked)

    def cycle_edges(self):
        mode = EDGE_MODES[(EDGE_MODES.index(self.occ.edge_mode) + 1) % len(EDGE_MODES)]
        self.occ.set_edge_mode(mode)
        self.edge_action.setText(EDGE_LABELS[mode])

    def toggle_projection(self):
        persp = self.occ.toggle_projection()
        self.proj_action.setText("Perspective" if persp else "Orthographique")


def main():
    # sans excepthook explicite, PyQt6 abandonne le processus (qFatal) sur toute exception dans un slot
    sys.excepthook = lambda *exc: traceback.print_exception(*exc)
    args = sys.argv[1:]
    dump = None
    if "--dump" in args:
        i = args.index("--dump")
        dump = args[i + 1]
        del args[i:i + 2]
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    if args:
        QTimer.singleShot(0, lambda: win.load(args[0]))
    if dump:
        def do_dump():
            ok = win.occ.dump(dump)
            print(f"Capture {'écrite' if ok else 'ÉCHOUÉE'} : {dump}")
            app.quit()
        QTimer.singleShot(1500, do_dump)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
