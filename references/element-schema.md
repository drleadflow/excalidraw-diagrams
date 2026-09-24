# Excalidraw element schema (the subset this skill uses)

## Document
```json
{ "type": "excalidraw", "version": 2, "source": "excalidraw-diagrams-skill",
  "elements": [], "appState": { "gridSize": null, "viewBackgroundColor": "#ffffff" }, "files": {} }
```

## Required on every element
`type`, `id` (unique string), `x`, `y`, `width`, `height`, plus these defaults:
```json
{ "versionNonce": 0, "isDeleted": false, "fillStyle": "solid", "strokeWidth": 2,
  "strokeStyle": "solid", "roughness": 1, "opacity": 100, "angle": 0,
  "strokeColor": "#1e1e1e", "backgroundColor": "transparent", "seed": 1,
  "groupIds": [], "frameId": null, "boundElements": null, "updated": 1,
  "link": null, "locked": false, "version": 1, "roundness": null }
```

## Rectangle
```json
{ "type": "rectangle", "id": "r1", "x": 100, "y": 100, "width": 200, "height": 100,
  "roundness": { "type": 3 }, "backgroundColor": "#a5d8ff" }
```
Ellipse and diamond are identical with `"type": "ellipse"` / `"diamond"`.

## Text (standalone)
```json
{ "type": "text", "id": "t1", "x": 150, "y": 138, "width": 100, "height": 25,
  "text": "Hello", "originalText": "Hello", "fontSize": 20, "fontFamily": 3,
  "textAlign": "left", "verticalAlign": "top", "containerId": null,
  "autoResize": true, "lineHeight": 1.25 }
```
Width ≈ longest line chars × fontSize × 0.62. Height ≈ lines × fontSize × 1.25.

## Text bound to a container
- Text element: `"containerId": "<shape-id>"`
- Shape: `"boundElements": [{ "id": "<text-id>", "type": "text" }]`
- Center: `x = shape.x + (shape.width - text.width) / 2`, same for y.

## Arrow (always with fixedPoint)
```json
{ "type": "arrow", "id": "a1", "x": 300, "y": 150, "width": 200, "height": 0,
  "points": [[0,0],[200,0]], "startArrowhead": null, "endArrowhead": "arrow",
  "elbowed": false, "lastCommittedPoint": null,
  "startBinding": { "elementId": "r1", "focus": 0, "gap": 4, "fixedPoint": [1, 0.5], "mode": "orbit" },
  "endBinding":   { "elementId": "r2", "focus": 0, "gap": 4, "fixedPoint": [0, 0.5], "mode": "orbit" } }
```
`fixedPoint`: top `[0.5,0]`, bottom `[0.5,1]`, left `[0,0.5]`, right `[1,0.5]`; fractions along an edge for offsets (`[0.3,1]` = 30% along the bottom). Add the arrow to both shapes' `boundElements` as `{ "id": "a1", "type": "arrow" }`.

## Z-order
Array position. Backgrounds first, shapes and labels next, arrows last.
