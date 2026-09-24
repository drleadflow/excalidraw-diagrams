---
name: excalidraw-diagrams
description: "Generate clean, readable .excalidraw diagrams (flowcharts, process maps, runbooks, architecture diagrams, state machines, funnel/forensics maps, visual explainers) as complete JSON files with deliberate layout discipline: box size computed from text, fixed-width columns, grid-aligned cards, explicitly bound arrows. Triggers on 'diagram', 'flowchart', 'map this out', 'visualize this process', 'make this dummy-proof', 'excalidraw'. Includes a Python builder library, a PNG renderer/linter for layout QA, and an optional push to an Excalidraw+ workspace as a live editable scene. For charts of numeric data, use a charting skill instead."
metadata:
  version: 1.0.0
  license: MIT
---

# Excalidraw Diagrams

Generate `.excalidraw` JSON files that read cleanly on first glance: no overlapping text, no eyeballed spacing, no paragraph crammed into a box sized for a sentence.

The naive approach (place a box, guess its size, place the next box nearby) reliably produces overlapping, unreadable diagrams. Every rule below closes a specific failure mode seen in practice.

## Workflow

1. **Pick the layout archetype before placing anything** (see "Choose the archetype"). The most common failure is a generic boxes-and-arrows layout for content that is not a flow.
2. **Generate elements with a script, never by hand.** Use `scripts/excalidraw_builder.py` (import it or copy it next to your generator). It computes box size from real text, keeps a running cursor, binds arrows correctly, and regenerates cleanly on every revision.
3. **Compute box size from content, not the other way around.** Never pick a box size first and hope the text fits.
4. **Render and lint before you show it.** `python3 scripts/render_excalidraw_png.py <file>` rasterises the board with real font metrics and prints violations (overflowing text, dead bindings, type under 14px). Look at the PNG. Fix root causes, regenerate, re-render.
5. **Save** to `./diagrams/<descriptive-name>.excalidraw` (create the dir). Tell the user the path; it opens in VS Code/Cursor with the Excalidraw extension or by drag-drop onto excalidraw.com.
6. **Optional live push.** If `EXCALIDRAW_API_KEY` is set, `scripts/push_excalidraw.py` pushes the file into an Excalidraw+ scene. See `references/excalidraw-plus-api.md`.
7. **If the user says it looks messy**, do not nudge coordinates. Find which rule was violated (usually 1 or 2), fix the generator, regenerate the whole file.

## Layout discipline rules (priority order)

### 1. Compute box width from the actual text
```
width  ≈ longest_line_chars × fontSize × 0.62
height ≈ line_count × fontSize × 1.25
```
Add 16-24px internal padding. The builder's `text_box()` does this for you. This one rule removes most overflow and overlap bugs.

### 2. Fixed-column layout for anything with variable-length bars or labels
For bar charts, ranked lists, or any row where an element's length depends on data, never place the label right after the bar. A long bar collides with the next label. Put every label at one fixed x that clears the longest possible bar.

### 3. Asides get their own boxes with real clearance
Governing rules, footnotes, warnings and callouts must not be squeezed between two flow elements. Give them a dedicated bordered box with at least 40-50px clearance, connected by an arrow only if it references a specific element.

### 4. Consistent grid: identical width and gap within a row
N cards in a row all get the same width and gap: `cardWidth = (rowWidth - (N-1) × gap) / N`. Pad content; never let card width vary by content.

### 5. Less text per box, more boxes
More than 5-6 short lines means it is two boxes. Diagrams are scanned, not read. Prefer terse checklist lines ("☐ Publish v0.0.21") over prose.

### 6. Bind arrows explicitly with a fixed anchor point
Every arrow needs `startBinding`/`endBinding` with `elementId`, `fixedPoint` and `mode: "orbit"`, and must be listed in both shapes' `boundElements`. Without `fixedPoint`, the Excalidraw+ API rejects the element with a 400, and even locally the arrow snaps to an ambiguous point. The builder's `arrow()` handles this.

### 7. Z-order is array position
Background zones first, then shapes with labels, then arrows on top. If you compute a zone's size after building its cards, `insert()` the zone rect at a reserved index before the cards rather than appending it, or it renders on top and hides everything. The builder's `zone()` reserves a slot for you.

### 8. Choose the archetype deliberately
- **Step-by-step process** (runbook, checklist, rollout plan): top-to-bottom sections, each a self-contained card with checkbox lines, converging at milestone bars ("LAUNCHED"). Reads as instructions.
- **Comparison or forensics map** (multiple sources, stats, findings): grid of summary cards on top, a bar/funnel visualization below, callout cards for conclusions at the bottom. Reads as an argument.
- **State machine or conversation flow**: strict left-to-right (or top-to-bottom) chain of equal-sized state boxes with example content; side branches (retry loops, hesitation) drawn below or beside with clear separation, never inline.
- **Architecture diagram**: group boxes by system/service inside zone backgrounds, arrows show data-flow direction, label every arrow with what flows.

Pick one. Do not blend a data table into a flowchart cell.

## Typography and sizing

- `fontFamily: 3` (Comic Sans / hand-drawn look) for all text. Never `1` (Virgil) since it renders inconsistently outside the web app.
- Title 24-30, section/card headers 16-19, body 13.5-15, fine print 11-13. Never below 11.
- Minimum labeled shape: 120×60. Gaps: 30-50px between elements, 40-50px for asides.
- Fewer, larger, well-spaced elements beat many tiny ones.

## Color palette (use color with meaning)

| Fill | Hex | Use |
|---|---|---|
| Light Blue | `#a5d8ff` | input, sources, primary |
| Light Green | `#b2f2bb` | success, output, done |
| Light Orange | `#ffd8a8` | warning, pending |
| Light Purple | `#d0bfff` | processing, special |
| Light Red | `#ffc9c9` | error, critical, blocker |
| Light Yellow | `#fff3bf` | notes, decisions, watch-items |
| Light Teal | `#c3fae8` | storage, data |
| Light Pink | `#eebefa` | analytics |

Strokes/accents: Blue `#4a9eed` · Green `#22c55e` · Amber `#f59e0b` · Red `#ef4444` · Purple `#8b5cf6` · Cyan `#06b6d4`. Default stroke `#1e1e1e`.

A reader should infer severity from color before reading a word: red = blocker, green = done, amber = watch, blue = informational.

## File format essentials

See `references/element-schema.md` for the full element reference. The builder emits all of this; you only need it when hand-patching.

```json
{ "type": "excalidraw", "version": 2, "source": "excalidraw-diagrams-skill",
  "elements": [], "appState": { "gridSize": null, "viewBackgroundColor": "#ffffff" }, "files": {} }
```

## Using the builder

```python
import sys; sys.path.insert(0, "<skill dir>/scripts")
from excalidraw_builder import Board

b = Board()
z = b.zone(40, 40, "Intake")                       # reserves z-order slot, sized later
a = b.text_box(80, 100, "Lead submits form", fill="#a5d8ff")
c = b.text_box(a.right + 60, 100, "Setter calls\nwithin 5 min", fill="#b2f2bb")
b.arrow(a, c, label="webhook")                     # bound, fixedPoint right→left
b.fit_zone(z, [a, c], pad=30)                      # now size the zone around its cards
b.save("diagrams/speed-to-lead.excalidraw")
```

Then:
```bash
python3 scripts/render_excalidraw_png.py diagrams/speed-to-lead.excalidraw
```

See `examples/runbook_example.py` for a complete generator following the runbook archetype.

## After writing

Tell the user the file path. If pushed to Excalidraw+, give the live URL and note that re-pushing to the same scene keeps the URL stable. Only create a new scene for a genuinely new diagram.
