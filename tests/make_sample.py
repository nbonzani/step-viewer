"""Génère les fichiers STEP de test (XCAF : couleurs corps et faces, noms, assemblages).

sample.step   : 2 corps libres (sans structure d'assemblage).
assembly.step : « Ensemble » = « Sous-ensemble » (Plaque + Axe) + 2e instance de l'Axe déplacée.
box.step      : parallélépipède nu, embarqué dans le viewer HTML pour son auto-test.

Corps 1 : plaque avec congés, perçage traversant, bossage cylindrique — bleu, face du dessus jaune,
          faces du perçage rouges.
Corps 2 : axe cylindrique avec chanfrein — gris clair, extrémité verte.
"""
from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.BRep import BRep_Builder
from OCP.TopLoc import TopLoc_Location
from OCP.gp import gp_Trsf, gp_Vec
from OCP.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane


def color(r, g, b):
    return Quantity_Color(r, g, b, Quantity_TOC_RGB)


def faces(shape):
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        yield TopoDS.Face(exp.Current())
        exp.Next()


def edges(shape):
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        yield TopoDS.Edge(exp.Current())
        exp.Next()


def first_solid(shape):
    """Les opérations booléennes renvoient un compound : on en extrait le solide (comme un export CAO)."""
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    assert exp.More()
    return TopoDS.Solid(exp.Current())


def make_plate():
    plate = BRepPrimAPI_MakeBox(gp_Pnt(-40, -25, 0), 80, 50, 10).Shape()
    fil = BRepFilletAPI_MakeFillet(plate)
    for e in edges(plate):
        fil.Add(4.0, e)
    plate = fil.Shape()
    boss = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(15, 0, 10), gp_Dir(0, 0, 1)), 12, 15).Shape()
    plate = BRepAlgoAPI_Fuse(plate, boss).Shape()
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(-20, 0, -1), gp_Dir(0, 0, 1)), 6, 30).Shape()
    plate = BRepAlgoAPI_Cut(plate, hole).Shape()
    bore = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(15, 0, -1), gp_Dir(0, 0, 1)), 5, 40).Shape()
    return first_solid(BRepAlgoAPI_Cut(plate, bore).Shape())


def make_pin():
    pin = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(15, 0, 5), gp_Dir(0, 0, 1)), 4.9, 45).Shape()
    ch = BRepFilletAPI_MakeChamfer(pin)
    for e in edges(pin):
        ch.Add(1.0, e)
    return first_solid(ch.Shape())


def set_name(label, name):
    TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))


def write_doc(doc, out):
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_AsIs)
    status = writer.Write(str(out))
    assert status == IFSelect_RetDone, status
    print(f"Écrit : {out} ({out.stat().st_size} octets)")


def colorize(color_tool, lab_plate, plate, lab_pin, pin):
    color_tool.SetColor(lab_plate, color(0.20, 0.45, 0.85), XCAFDoc_ColorSurf)
    for f in faces(plate):
        surf = BRepAdaptor_Surface(f)
        if surf.GetType() == GeomAbs_Plane:
            p = surf.Plane()
            if abs(p.Axis().Direction().Z()) > 0.99 and abs(p.Location().Z() - 10) < 1e-6:
                color_tool.SetColor(f, color(0.95, 0.80, 0.15), XCAFDoc_ColorSurf)
        elif surf.GetType() == GeomAbs_Cylinder:
            c = surf.Cylinder()
            if 4.5 < c.Radius() < 6.5:  # perçage et alésage (les congés font R4)
                color_tool.SetColor(f, color(0.85, 0.15, 0.15), XCAFDoc_ColorSurf)

    color_tool.SetColor(lab_pin, color(0.75, 0.75, 0.78), XCAFDoc_ColorSurf)
    for f in faces(pin):
        surf = BRepAdaptor_Surface(f)
        if surf.GetType() == GeomAbs_Plane and surf.Plane().Location().Z() > 40:
            color_tool.SetColor(f, color(0.15, 0.70, 0.30), XCAFDoc_ColorSurf)


def main():
    plate = make_plate()
    pin = make_pin()

    # --- sample.step : deux corps libres ---------------------------------------
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    lab_plate = shape_tool.AddShape(plate, False)
    set_name(lab_plate, "Plaque")
    lab_pin = shape_tool.AddShape(pin, False)
    set_name(lab_pin, "Axe")
    colorize(color_tool, lab_plate, plate, lab_pin, pin)
    write_doc(doc, Path(__file__).with_name("sample.step"))

    # --- assembly.step : Ensemble > (Sous-ensemble > Plaque, Axe), Axe (2e instance) ---
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    b = BRep_Builder()
    sub = TopoDS_Compound()
    b.MakeCompound(sub)
    b.Add(sub, plate)
    b.Add(sub, pin)
    tr = gp_Trsf()
    tr.SetTranslation(gp_Vec(-35, 0, 0))          # 2e axe dans le perçage de gauche
    top = TopoDS_Compound()
    b.MakeCompound(top)
    b.Add(top, sub)
    b.Add(top, pin.Moved(TopLoc_Location(tr)))
    lab_top = shape_tool.AddShape(top, True)     # True : crée la structure d'assemblage
    lab_sub = shape_tool.FindShape(sub, False)
    lab_plate = shape_tool.FindShape(plate, False)
    lab_pin = shape_tool.FindShape(pin, False)
    set_name(lab_top, "Ensemble")
    set_name(lab_sub, "Sous-ensemble")
    set_name(lab_plate, "Plaque")
    set_name(lab_pin, "Axe")
    colorize(color_tool, lab_plate, plate, lab_pin, pin)
    shape_tool.UpdateAssemblies()
    write_doc(doc, Path(__file__).with_name("assembly.step"))

    # petit parallélépipède sans couleur, embarqué dans le viewer HTML pour son auto-test (#selftest)
    box = Path(__file__).with_name("box.step")
    w = STEPControl_Writer()
    w.Transfer(BRepPrimAPI_MakeBox(20, 10, 5).Shape(), STEPControl_AsIs)
    assert w.Write(str(box)) == IFSelect_RetDone
    print(f"Écrit : {box} ({box.stat().st_size} octets)")


if __name__ == "__main__":
    main()
