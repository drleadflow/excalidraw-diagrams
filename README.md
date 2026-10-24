# excalidraw-diagrams

A Claude Code / agent skill for generating clean `.excalidraw` diagrams programmatically, with layout rules that stop the usual overlapping-text mess, a renderer for visual QA, and an optional push into an Excalidraw+ workspace as a live editable scene.

## Install

Copy this folder to your skills directory:

```bash
cp -r excalidraw-diagrams ~/.claude/skills/          # global
# or
cp -r excalidraw-diagrams <project>/.claude/skills/  # per project
```

Optional dependency for the PNG renderer:

```bash
pip install pillow
```

Optional Excalidraw+ push: `export EXCALIDRAW_API_KEY=...` (see `references/excalidraw-plus-api.md`).

## Contents

| Path | Purpose |
|---|---|
| `SKILL.md` | The rules the agent follows: archetypes, layout discipline, palette, typography |
| `scripts/excalidraw_builder.py` | Zero-dependency builder: text-sized boxes, equal-width rows, zones with correct z-order, bound arrows |
| `scripts/render_excalidraw_png.py` | Rasterises a board with real font metrics and prints layout violations |
| `scripts/push_excalidraw.py` | Creates/replaces an Excalidraw+ scene, handling every known API quirk |
| `references/element-schema.md` | Element JSON reference |
| `references/excalidraw-plus-api.md` | API setup, quirks, and safety conventions |
| `examples/runbook_example.py` | Complete generator for the runbook archetype |
| `scripts/funnel_map.py` | Funnel map mode: one JSON content file in, two funnel maps out (a top-to-bottom spine and a left-to-right router, with roadmap and client math) |
| `examples/funnel/` | Example content file and both generated maps with previews |

## Quick start

Funnel maps, from one content file:

```bash
python3 scripts/funnel_map.py examples/funnel/funnel.example.json --out diagrams --png
open diagrams/example-quiz-funnel-A-spine.png
```

Any other diagram:

```bash
python3 examples/runbook_example.py
python3 scripts/render_excalidraw_png.py diagrams/launch-runbook.excalidraw
open diagrams/launch-runbook.png
```

The renderer is a QA tool, not an exporter: it draws the element subset the builder emits and shows glyphs missing from the local font (like ☐) as boxes. Excalidraw itself renders them fine.

Open the `.excalidraw` file in VS Code (Excalidraw extension) or drag it onto excalidraw.com.

## License

MIT
