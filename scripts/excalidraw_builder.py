#!/usr/bin/env python3
"""Tiny builder for .excalidraw files with layout discipline baked in.

Rules it enforces:
  * box size is computed from the text (never guessed)
  * arrows are bound on both ends with fixedPoint + mode="orbit"
  * zones reserve a z-order slot so backgrounds never cover their cards
  * all text uses fontFamily 3 (hand-drawn Comic Sans look)

Usage:
    from excalidraw_builder import Board
    b = Board()
    a = b.text_box(100, 100, "Step 1\nDo the thing", fill="#a5d8ff")
    c = b.text_box(a.right + 60, 100, "Step 2", fill="#b2f2bb")
    b.arrow(a, c, label="then")
    b.save("diagrams/example.excalidraw")

No third-party dependencies.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field

FONT_FAMILY = 3            # Comic Sans / hand-drawn
CHAR_W = 0.62              # avg glyph width as a fraction of fontSize
LINE_H = 1.25              # line height as a fraction of fontSize
PAD = 20                   # default internal padding for text boxes
MIN_W, MIN_H = 120, 60     # minimum labeled-shape size
STROKE = "#1e1e1e"

BASE = {
    "versionNonce": 0, "isDeleted": False, "fillStyle": "solid", "strokeWidth": 2,
    "strokeStyle": "solid", "roughness": 1, "opacity": 100, "angle": 0,
    "strokeColor": STROKE, "backgroundColor": "transparent", "seed": 1,
    "groupIds": [], "frameId": None, "boundElements": None, "updated": 1,
    "link": None, "locked": False, "version": 1, "roundness": None,
}

SIDES = {"top": [0.5, 0], "bottom": [0.5, 1], "left": [0, 0.5], "right": [1, 0.5]}


def _id() -> str:
    return uuid.uuid4().hex[:12]


def measure(text: str, font_size: float) -> tuple[float, float]:
    """Approximate rendered width/height of a text block (Rule 1)."""
    lines = text.split("\n") or [""]
    w = max(len(ln) for ln in lines) * font_size * CHAR_W
    h = len(lines) * font_size * LINE_H
    return w, h


@dataclass
class Shape:
    """Handle returned by Board methods; carries geometry for chaining."""
    id: str
    x: float
    y: float
    width: float
    height: float
    el: dict = field(repr=False)

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2


class Board:
    def __init__(self, background: str = "#ffffff"):
        self.elements: list[dict] = []
        self.background = background

    # ---- primitives -------------------------------------------------------

    def _add(self, el: dict, at: int | None = None) -> dict:
        el = {**BASE, **el}
        if at is None:
            self.elements.append(el)
        else:
            self.elements[at] = el
        return el

    def rect(self, x, y, w, h, fill="transparent", stroke=STROKE, rounded=True,
             stroke_width=2, opacity=100, dashed=False, at=None) -> Shape:
        el = self._add({
            "type": "rectangle", "id": _id(), "x": x, "y": y, "width": w, "height": h,
            "backgroundColor": fill, "strokeColor": stroke, "strokeWidth": stroke_width,
            "opacity": opacity, "strokeStyle": "dashed" if dashed else "solid",
            "roundness": {"type": 3} if rounded else None, "boundElements": [],
        }, at)
        return Shape(el["id"], x, y, w, h, el)

    def text(self, x, y, content, size=15, color=STROKE, align="left",
             container: Shape | None = None) -> Shape:
        w, h = measure(content, size)
        el = self._add({
            "type": "text", "id": _id(), "x": x, "y": y, "width": w, "height": h,
            "text": content, "originalText": content, "fontSize": size,
            "fontFamily": FONT_FAMILY, "textAlign": align, "verticalAlign": "top",
            "containerId": container.id if container else None, "autoResize": True,
            "lineHeight": LINE_H, "strokeColor": color,
        })
        if container:
            container.el["boundElements"].append({"id": el["id"], "type": "text"})
        return Shape(el["id"], x, y, w, h, el)

    # ---- composites ---------------------------------------------------------

    def text_box(self, x, y, content, size=15, fill="#ffffff", stroke=STROKE,
                 min_w=MIN_W, min_h=MIN_H, pad=PAD, width=None, align="center") -> Shape:
        """Rectangle sized from its text (Rule 1). Pass width= to force a grid column (Rule 4)."""
        tw, th = measure(content, size)
        w = width if width is not None else max(min_w, tw + 2 * pad)
        h = max(min_h, th + 2 * pad)
        box = self.rect(x, y, w, h, fill=fill, stroke=stroke)
        tx = x + pad if align == "left" else x + (w - tw) / 2
        self.text(tx, y + (h - th) / 2, content, size=size, align=align, container=box)
        return box

    def zone(self, x, y, title, fill="#f8f9fa", stroke="#adb5bd", size=17) -> Shape:
        """Reserve a z-order slot for a background zone; size it later with fit_zone (Rule 7)."""
        self.elements.append(None)  # placeholder keeps the zone under its cards
        idx = len(self.elements) - 1
        z = self.rect(x, y, MIN_W, MIN_H, fill=fill, stroke=stroke, dashed=True, at=idx)
        z.el["_zone_title"] = (title, size)
        return z

    def fit_zone(self, z: Shape, items: list[Shape], pad=30, title_gap=34) -> Shape:
        title, size = z.el.pop("_zone_title", ("", 17))
        x0 = min(i.x for i in items) - pad
        y0 = min(i.y for i in items) - pad - title_gap
        x1 = max(i.right for i in items) + pad
        y1 = max(i.bottom for i in items) + pad
        z.el.update(x=x0, y=y0, width=x1 - x0, height=y1 - y0)
        z.x, z.y, z.width, z.height = x0, y0, x1 - x0, y1 - y0
        if title:
            self.text(x0 + pad, y0 + 10, title, size=size, color="#495057")
        return z

    def row(self, x, y, labels, total_width, gap=40, size=15, fills=None, pad=PAD) -> list[Shape]:
        """N equal-width cards across total_width (Rule 4)."""
        n = len(labels)
        cw = (total_width - (n - 1) * gap) / n
        out = []
        for i, txt in enumerate(labels):
            fill = fills[i] if fills else "#ffffff"
            out.append(self.text_box(x + i * (cw + gap), y, txt, size=size, fill=fill, width=cw, pad=pad))
        h = max(s.height for s in out)
        for s in out:  # equalize height within the row
            s.el["height"] = h
            s.height = h
        return out

    def arrow(self, a: Shape, b: Shape, label: str | None = None, start="auto", end="auto",
              color=STROKE, dashed=False) -> dict:
        """Bound arrow a -> b with explicit fixedPoint on both ends (Rule 6)."""
        if start == "auto" or end == "auto":
            start, end = _auto_sides(a, b)
        sx, sy = a.x + SIDES[start][0] * a.width, a.y + SIDES[start][1] * a.height
        ex, ey = b.x + SIDES[end][0] * b.width, b.y + SIDES[end][1] * b.height
        el = self._add({
            "type": "arrow", "id": _id(), "x": sx, "y": sy, "width": ex - sx, "height": ey - sy,
            "points": [[0, 0], [ex - sx, ey - sy]], "strokeColor": color,
            "strokeStyle": "dashed" if dashed else "solid",
            "startArrowhead": None, "endArrowhead": "arrow", "elbowed": False,
            "lastCommittedPoint": None, "boundElements": [],
            "startBinding": {"elementId": a.id, "focus": 0, "gap": 4, "fixedPoint": SIDES[start], "mode": "orbit"},
            "endBinding": {"elementId": b.id, "focus": 0, "gap": 4, "fixedPoint": SIDES[end], "mode": "orbit"},
        })
        for s in (a, b):
            s.el["boundElements"].append({"id": el["id"], "type": "arrow"})
        if label:
            tw, th = measure(label, 12)
            self.text((sx + ex) / 2 - tw / 2, (sy + ey) / 2 - th - 4, label, size=12, color="#495057")
        return el

    def title(self, x, y, content, size=28) -> Shape:
        return self.text(x, y, content, size=size)

    def milestone_bar(self, x, y, w, content, fill="#b2f2bb", size=19) -> Shape:
        return self.text_box(x, y, content, size=size, fill=fill, width=w, min_h=50, pad=14)

    # ---- output ---------------------------------------------------------------

    def doc(self) -> dict:
        els = []
        for i, e in enumerate(self.elements):
            if e is None:
                raise ValueError(f"zone at index {i} was never sized; call fit_zone()")
            e = dict(e)
            e.pop("_zone_title", None)
            e["index"] = f"a{i:04d}"
            els.append(e)
        return {"type": "excalidraw", "version": 2, "source": "excalidraw-diagrams-skill",
                "elements": els,
                "appState": {"gridSize": None, "viewBackgroundColor": self.background},
                "files": {}}

    def save(self, path: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.doc(), f, indent=1)
        return path


def _auto_sides(a: Shape, b: Shape) -> tuple[str, str]:
    dx, dy = b.cx - a.cx, b.cy - a.cy
    if abs(dx) >= abs(dy):
        return ("right", "left") if dx > 0 else ("left", "right")
    return ("bottom", "top") if dy > 0 else ("top", "bottom")
