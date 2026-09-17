"""Génère tests/sample.step : assemblage de 2 corps avec couleurs corps et couleurs faces (XCAF).

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
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
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
    return BRepAlgoAPI_Cut(plate, bore).Shape()


def make_pin():
    pin = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(15, 0, 5), gp_Dir(0, 0, 1)), 4.9, 45).Shape()
    ch = BRepFilletAPI_MakeChamfer(pin)
    for e in edges(pin):
        ch.Add(1.0, e)
    return ch.Shape()


def main():
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    plate = make_plate()
    pin = make_pin()

    lab_plate = shape_tool.AddShape(plate, False)
    TDataStd_Name.Set_s(lab_plate, TCollection_ExtendedString("Plaque"))
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

    lab_pin = shape_tool.AddShape(pin, False)
    TDataStd_Name.Set_s(lab_pin, TCollection_ExtendedString("Axe"))
    color_tool.SetColor(lab_pin, color(0.75, 0.75, 0.78), XCAFDoc_ColorSurf)
    for f in faces(pin):
        surf = BRepAdaptor_Surface(f)
        if surf.GetType() == GeomAbs_Plane and surf.Plane().Location().Z() > 40:
            color_tool.SetColor(f, color(0.15, 0.70, 0.30), XCAFDoc_ColorSurf)

    out = Path(__file__).with_name("sample.step")
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_AsIs)
    status = writer.Write(str(out))
    assert status == IFSelect_RetDone, status
    print(f"Écrit : {out} ({out.stat().st_size} octets)")

    # petit parallélépipède sans couleur, embarqué dans le viewer HTML pour son auto-test (#selftest)
    box = Path(__file__).with_name("box.step")
    w = STEPControl_Writer()
    w.Transfer(BRepPrimAPI_MakeBox(20, 10, 5).Shape(), STEPControl_AsIs)
    assert w.Write(str(box)) == IFSelect_RetDone
    print(f"Écrit : {box} ({box.stat().st_size} octets)")


if __name__ == "__main__":
    main()
