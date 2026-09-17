"""Test de fumée du viewer Qt : simule glisser-déposer, souris, molette, raccourcis ; écrit des captures.

Usage : python tests/qt_smoke.py [dossier_de_sortie]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "qt"))

from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import step_viewer_qt as sv

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SAMPLE = str(Path(__file__).with_name("sample.step"))


def main():
    app = QApplication(sys.argv)
    win = sv.MainWindow()
    win.show()
    app.processEvents()
    steps = []

    def shot(name):
        app.processEvents()
        assert win.occ.dump(str(OUT / f"smoke_{name}.png")), name
        steps.append(name)

    # 1. glisser-déposer
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(SAMPLE)])
    enter = QDragEnterEvent(QPoint(300, 300), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
    win.dragEnterEvent(enter)
    assert enter.isAccepted(), "dragEnterEvent devrait accepter un .step"
    ev = QDropEvent(QPointF(300, 300), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier)
    win.dropEvent(ev)
    assert not win.hint.isVisible(), "l'invite de dépôt devrait être masquée"
    assert win.occ.objects, "aucun objet affiché après dépôt"
    shot("01_drop")

    v = win.occ
    # 2. rotation (clic gauche glissé)
    QTest.mousePress(v, Qt.MouseButton.LeftButton, pos=QPoint(400, 300))
    QTest.mouseMove(v, QPoint(480, 260))
    QTest.mouseMove(v, QPoint(520, 240))
    QTest.mouseRelease(v, Qt.MouseButton.LeftButton, pos=QPoint(520, 240))
    shot("02_rotate")

    # 3. panoramique (clic droit glissé)
    QTest.mousePress(v, Qt.MouseButton.RightButton, pos=QPoint(400, 300))
    QTest.mouseMove(v, QPoint(500, 350))
    QTest.mouseRelease(v, Qt.MouseButton.RightButton, pos=QPoint(500, 350))
    shot("03_pan")

    # 4. zoom molette au curseur
    for _ in range(3):
        we = QWheelEvent(QPointF(450, 320), QPointF(450, 320), QPoint(0, 0), QPoint(0, 120),
                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        app.sendEvent(v, we)
    shot("04_zoom")

    # 5. raccourcis : ajuster, vues, arêtes, projection
    QTest.keyClick(win, Qt.Key.Key_F)
    shot("05_fit")
    QTest.keyClick(win, Qt.Key.Key_3)
    shot("06_top")
    QTest.keyClick(win, Qt.Key.Key_E)
    assert v.edge_mode == "sharp"
    QTest.keyClick(win, Qt.Key.Key_0)
    shot("07_iso_sharp")
    QTest.keyClick(win, Qt.Key.Key_E)
    assert v.edge_mode == "none"
    shot("08_noedges")
    QTest.keyClick(win, Qt.Key.Key_E)
    assert v.edge_mode == "all"
    QTest.keyClick(win, Qt.Key.Key_P)
    assert win.proj_action.text() == "Orthographique"
    shot("09_ortho")
    QTest.keyClick(win, Qt.Key.Key_P)

    # 6. rechargement (remplacement du modèle)
    win.load(SAMPLE)
    assert len(v.objects) == 2
    shot("10_reload")

    print("OK :", ", ".join(steps))
    QTimer.singleShot(0, app.quit)
    app.exec()


if __name__ == "__main__":
    main()
