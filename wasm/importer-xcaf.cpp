#include "importer-xcaf.hpp"
#include "importer-utils.hpp"

#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <TopoDS_Face.hxx>
#include <TopLoc_Location.hxx>
#include <TDF_LabelSequence.hxx>
#include <TDocStd_Document.hxx>
#include <TDataStd_Name.hxx>
#include <Quantity_Color.hxx>
#include <BRep_Tool.hxx>
#include <XCAFDoc_DocumentTool.hxx>

// Patched importer (STEP Viewer, nbonzani/step-viewer):
//  - the hierarchy follows the XCAF assembly structure (components of assemblies, recursively),
//    with the cumulated location of every occurrence, instead of the raw TDF label tree;
//  - meshes are built from the *prototype* shapes (unlocated), so XCAF colour look-ups on
//    sub-shapes (face colours) succeed for instantiated parts; the occurrence location is
//    applied when the vertices are emitted.

static std::string GetLabelNameNoRef (const TDF_Label& label)
{
    Handle (TDataStd_Name) nameAttribute = new TDataStd_Name ();
    if (!label.FindAttribute (nameAttribute->GetID (), nameAttribute)) {
        return std::string ();
    }

    Standard_Integer utf8NameLength = nameAttribute->Get ().LengthOfCString ();
    char* nameBuf = new char[utf8NameLength + 1];
    nameAttribute->Get ().ToUTF8CString (nameBuf);
    std::string name (nameBuf, utf8NameLength);
    delete[] nameBuf;
    return name;
}

static TDF_Label GetReferredLabel (const TDF_Label& label, const Handle (XCAFDoc_ShapeTool)& shapeTool)
{
    if (XCAFDoc_ShapeTool::IsReference (label)) {
        TDF_Label referredShapeLabel;
        shapeTool->GetReferredShape (label, referredShapeLabel);
        return referredShapeLabel;
    }
    return label;
}

// Occurrence name when it carries a real one (the STEP reader names anonymous instances "=>[0:1:1:2]"),
// otherwise the name of the referred prototype.
static std::string GetOccurrenceName (const TDF_Label& label, const Handle (XCAFDoc_ShapeTool)& shapeTool)
{
    std::string name = GetLabelNameNoRef (label);
    if (!name.empty () && name.rfind ("=>", 0) != 0) {
        return name;
    }
    TDF_Label referred = GetReferredLabel (label, shapeTool);
    if (referred != label) {
        return GetLabelNameNoRef (referred);
    }
    return name;
}

static std::string GetShapeName (const TopoDS_Shape& shape, const Handle (XCAFDoc_ShapeTool)& shapeTool)
{
    TDF_Label shapeLabel;
    if (!shapeTool->Search (shape, shapeLabel)) {
        return std::string ();
    }
    return GetLabelNameNoRef (GetReferredLabel (shapeLabel, shapeTool));
}

static bool GetLabelColorNoRef (const TDF_Label& label, const Handle (XCAFDoc_ColorTool)& colorTool, Color& color)
{
    static const std::vector<XCAFDoc_ColorType> colorTypes = {
        XCAFDoc_ColorSurf,
        XCAFDoc_ColorCurv,
        XCAFDoc_ColorGen
    };

    Quantity_Color qColor;
    for (XCAFDoc_ColorType colorType : colorTypes) {
        if (colorTool->GetColor (label, colorType, qColor)) {
            color = Color (qColor.Red (), qColor.Green (), qColor.Blue ());
            return true;
        }
    }

    return false;
}

static bool GetLabelColor (const TDF_Label& label, const Handle (XCAFDoc_ShapeTool)& shapeTool, const Handle (XCAFDoc_ColorTool)& colorTool, Color& color)
{
    if (GetLabelColorNoRef (label, colorTool, color)) {
        return true;
    }

    if (XCAFDoc_ShapeTool::IsReference (label)) {
        TDF_Label referredShape;
        shapeTool->GetReferredShape (label, referredShape);
        return GetLabelColor (referredShape, shapeTool, colorTool, color);
    }

    return false;
}

static bool GetShapeColor (const TopoDS_Shape& shape, const Handle (XCAFDoc_ShapeTool)& shapeTool, const Handle (XCAFDoc_ColorTool)& colorTool, Color& color)
{
    TDF_Label shapeLabel;
    if (!shapeTool->Search (shape, shapeLabel)) {
        return false;
    }
    return GetLabelColor (shapeLabel, shapeTool, colorTool, color);
}

// Face of a prototype shape, emitted at the location of the occurrence
class XcafFace : public OcctFace
{
public:
    XcafFace (const TopoDS_Face& face, const TopLoc_Location& occurrenceLocation, const Handle (XCAFDoc_ShapeTool)& shapeTool, const Handle (XCAFDoc_ColorTool)& colorTool) :
        OcctFace (face),
        shapeTool (shapeTool),
        colorTool (colorTool)
    {
        location = occurrenceLocation * location;
    }

    virtual bool GetColor (Color& color) const override
    {
        return GetShapeColor ((const TopoDS_Shape&) face, shapeTool, colorTool, color);
    }

private:
    const Handle (XCAFDoc_ShapeTool)& shapeTool;
    const Handle (XCAFDoc_ColorTool)& colorTool;
};

class XcafShapeMesh : public Mesh
{
public:
    XcafShapeMesh (const TopoDS_Shape& shape, const TopLoc_Location& location, const std::string& fallbackName, const Color* fallbackColor,
                   const Handle (XCAFDoc_ShapeTool)& shapeTool, const Handle (XCAFDoc_ColorTool)& colorTool) :
        Mesh (),
        shape (shape),
        location (location),
        fallbackName (fallbackName),
        fallbackColor (fallbackColor),
        shapeTool (shapeTool),
        colorTool (colorTool)
    {

    }

    virtual std::string GetName () const override
    {
        std::string name = GetShapeName (shape, shapeTool);
        return name.empty () ? fallbackName : name;
    }

    virtual bool GetColor (Color& color) const override
    {
        if (GetShapeColor (shape, shapeTool, colorTool, color)) {
            return true;
        }
        if (fallbackColor != nullptr) {
            color = *fallbackColor;
            return true;
        }
        return false;
    }

    virtual void EnumerateFaces (const std::function<void (const Face& face)>& onFace) const override
    {
        for (TopExp_Explorer ex (shape, TopAbs_FACE); ex.More (); ex.Next ()) {
            const TopoDS_Face& face = TopoDS::Face (ex.Current ());
            XcafFace outputFace (face, location, shapeTool, colorTool);
            onFace (outputFace);
        }
    }

private:
    TopoDS_Shape shape;
    TopLoc_Location location;
    std::string fallbackName;
    const Color* fallbackColor;
    const Handle (XCAFDoc_ShapeTool)& shapeTool;
    const Handle (XCAFDoc_ColorTool)& colorTool;
};

class XcafStandaloneFacesMesh : public Mesh
{
public:
    XcafStandaloneFacesMesh (const TopoDS_Shape& shape, const TopLoc_Location& location, const std::string& fallbackName, const Color* fallbackColor,
                             const Handle (XCAFDoc_ShapeTool)& shapeTool, const Handle (XCAFDoc_ColorTool)& colorTool) :
        Mesh (),
        shape (shape),
        location (location),
        fallbackName (fallbackName),
        fallbackColor (fallbackColor),
        shapeTool (shapeTool),
        colorTool (colorTool)
    {

    }

    bool HasFaces () const
    {
        TopExp_Explorer ex (shape, TopAbs_FACE, TopAbs_SHELL);
        return ex.More ();
    }

    virtual std::string GetName () const override
    {
        return fallbackName;
    }

    virtual bool GetColor (Color& color) const override
    {
        if (fallbackColor != nullptr) {
            color = *fallbackColor;
            return true;
        }
        return false;
    }

    virtual void EnumerateFaces (const std::function<void (const Face& face)>& onFace) const override
    {
        for (TopExp_Explorer ex (shape, TopAbs_FACE, TopAbs_SHELL); ex.More (); ex.Next ()) {
            const TopoDS_Face& face = TopoDS::Face (ex.Current ());
            XcafFace outputFace (face, location, shapeTool, colorTool);
            onFace (outputFace);
        }
    }

private:
    TopoDS_Shape shape;
    TopLoc_Location location;
    std::string fallbackName;
    const Color* fallbackColor;
    const Handle (XCAFDoc_ShapeTool)& shapeTool;
    const Handle (XCAFDoc_ColorTool)& colorTool;
};

// One occurrence of a shape: a free shape, or a component (reference) of an assembly
class XcafOccurrenceNode : public Node
{
public:
    XcafOccurrenceNode (const TDF_Label& label, const TopLoc_Location& parentLocation, const Handle (XCAFDoc_ShapeTool)& shapeTool, const Handle (XCAFDoc_ColorTool)& colorTool) :
        label (label),
        refLabel (GetReferredLabel (label, shapeTool)),
        location (parentLocation * shapeTool->GetLocation (label)),
        shapeTool (shapeTool),
        colorTool (colorTool)
    {

    }

    virtual std::string GetName () const override
    {
        return GetOccurrenceName (label, shapeTool);
    }

    virtual std::vector<NodePtr> GetChildren () const override
    {
        std::vector<NodePtr> children;
        if (IsMeshNode ()) {
            return children;
        }

        TDF_LabelSequence components;
        shapeTool->GetComponents (refLabel, components);
        for (Standard_Integer i = 1; i <= components.Length (); i++) {
            children.push_back (std::make_shared<const XcafOccurrenceNode> (
                components.Value (i), location, shapeTool, colorTool
            ));
        }
        return children;
    }

    virtual bool IsMeshNode () const override
    {
        return !shapeTool->IsAssembly (refLabel);
    }

    virtual void EnumerateMeshes (const std::function<void (const Mesh&)>& onMesh) const override
    {
        if (!IsMeshNode ()) {
            return;
        }

        // prototype shape, unlocated: XCAF sub-shape look-ups (face colours) work on it
        TopoDS_Shape shape = shapeTool->GetShape (refLabel);
        std::string name = GetName ();
        Color occurrenceColor;
        const Color* fallbackColor = GetLabelColor (label, shapeTool, colorTool, occurrenceColor) ? &occurrenceColor : nullptr;

        // Enumerate solids
        for (TopExp_Explorer ex (shape, TopAbs_SOLID); ex.More (); ex.Next ()) {
            XcafShapeMesh outputShapeMesh (ex.Current (), location, name, fallbackColor, shapeTool, colorTool);
            onMesh (outputShapeMesh);
        }

        // Enumerate shells that are not part of a solid
        for (TopExp_Explorer ex (shape, TopAbs_SHELL, TopAbs_SOLID); ex.More (); ex.Next ()) {
            XcafShapeMesh outputShapeMesh (ex.Current (), location, name, fallbackColor, shapeTool, colorTool);
            onMesh (outputShapeMesh);
        }

        // Create a mesh from faces that are not part of a shell
        XcafStandaloneFacesMesh standaloneFacesMesh (shape, location, name, fallbackColor, shapeTool, colorTool);
        if (standaloneFacesMesh.HasFaces ()) {
            onMesh (standaloneFacesMesh);
        }
    }

private:
    TDF_Label label;
    TDF_Label refLabel;
    TopLoc_Location location;
    const Handle (XCAFDoc_ShapeTool)& shapeTool;
    const Handle (XCAFDoc_ColorTool)& colorTool;
};

class XcafRootNode : public Node
{
public:
    XcafRootNode (const Handle (XCAFDoc_ShapeTool)& shapeTool, const Handle (XCAFDoc_ColorTool)& colorTool, const ImportParams& params) :
        shapeTool (shapeTool),
        colorTool (colorTool),
        params (params)
    {

    }

    virtual std::string GetName () const override
    {
        return std::string ();
    }

    virtual std::vector<NodePtr> GetChildren () const override
    {
        std::vector<NodePtr> children;
        TDF_LabelSequence freeShapes;
        shapeTool->GetFreeShapes (freeShapes);
        for (Standard_Integer i = 1; i <= freeShapes.Length (); i++) {
            const TDF_Label& label = freeShapes.Value (i);
            // triangulation is stored on the shared TShapes: prototypes and all their instances get it
            TopoDS_Shape shape = shapeTool->GetShape (label);
            if (!TriangulateShape (shape, params)) {
                continue;
            }
            children.push_back (std::make_shared<const XcafOccurrenceNode> (
                label, TopLoc_Location (), shapeTool, colorTool
            ));
        }
        return children;
    }

    virtual bool IsMeshNode () const override
    {
        return false;
    }

    virtual void EnumerateMeshes (const std::function<void (const Mesh&)>&) const override
    {

    }

private:
    const Handle (XCAFDoc_ShapeTool)& shapeTool;
    const Handle (XCAFDoc_ColorTool)& colorTool;
    const ImportParams& params;
};

ImporterXcaf::ImporterXcaf () :
    Importer (),
    document (nullptr),
    shapeTool (nullptr),
    colorTool (nullptr),
    rootNode (nullptr)
{

}

Importer::Result ImporterXcaf::LoadFile (const std::vector<std::uint8_t>& fileContent, const ImportParams& params)
{
    document = new TDocStd_Document ("XmlXCAF");

    UnitsMethods_LengthUnit lengthUnit = LinearUnitToLengthUnit (params.linearUnit);
    XCAFDoc_DocumentTool::SetLengthUnit (document, 1.0, lengthUnit);

    if (!TransferToDocument (fileContent)) {
        return Importer::Result::ImportFailed;
    }

    TDF_Label mainLabel = document->Main ();
    shapeTool = XCAFDoc_DocumentTool::ShapeTool (mainLabel);
    colorTool = XCAFDoc_DocumentTool::ColorTool (mainLabel);

    TDF_LabelSequence labels;
    shapeTool->GetFreeShapes (labels);
    if (labels.IsEmpty ()) {
        return Importer::Result::ImportFailed;
    }

    rootNode = std::make_shared<const XcafRootNode> (shapeTool, colorTool, params);
    return Importer::Result::Success;
}

NodePtr ImporterXcaf::GetRootNode () const
{
    return rootNode;
}
