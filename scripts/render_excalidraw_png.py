#!/usr/bin/env python3
"""Rasterise .excalidraw boards to PNG for layout QA, and flag geometry violations.

Requires Pillow:  pip install pillow

This is a verification tool, not an exporter — it renders the element subset the
generators emit (rectangle, text, line, frame) with real Comic Sans metrics, so
text that overflows its container is visible rather than assumed away.

  python3 scripts/render_excalidraw_png.py <file.excalidraw> [...]  -> <name>.png
  python3 scripts/render_excalidraw_png.py --sheet <out.jpg> <file> [...]
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

def _first(*paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None

_COMIC = _first(os.environ.get("EXCALIDRAW_FONT_HAND"),
                "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
                "/usr/share/fonts/truetype/msttcorefonts/Comic_Sans_MS.ttf",
                "C:/Windows/Fonts/comic.ttf")
_SANS = _first(os.environ.get("EXCALIDRAW_FONT_SANS"),
               "/System/Library/Fonts/Supplemental/Arial.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
               "C:/Windows/Fonts/arial.ttf")
FONTS = {2: _SANS or _COMIC, 3: _COMIC or _SANS}
FONT_PATH = FONTS[3]
if FONT_PATH is None:
    sys.exit("No TrueType font found. Set EXCALIDRAW_FONT_HAND=/path/to/font.ttf")
BOARD_W, BOARD_H = 1920, 1080
MARGIN = 20          # content must stay this far inside the board
_font_cache = {}


def font(size, family=3):
    k = (max(6, int(round(size))), family)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(FONTS.get(family, FONT_PATH), k[0])
    return _font_cache[k]


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def blend(hexcol, opacity, bg="#ffffff"):
    """Dim toward the board background — on a dark board, dimming is not lightening."""
    if opacity >= 100 or not hexcol or hexcol == "transparent":
        return hexcol
    r, g, b = _rgb(hexcol)
    br, bg_, bb = _rgb(bg)
    a = opacity / 100.0
    return "#%02x%02x%02x" % tuple(int(c * a + d * (1 - a))
                                   for c, d in ((r, br), (g, bg_), (b, bb)))


def violations(els, bw=BOARD_W, bh=BOARD_H):
    """Geometry problems that a picture makes you squint for."""
    out = []
    for e in els:
        if e.get("type") == "frame":
            continue
        x, y = e.get("x", 0), e.get("y", 0)
        w, h = e.get("width", 0), e.get("height", 0)
        if x <= 0 and y <= 0 and w >= bw and h >= bh:
            continue          # full-bleed background plate, not content
        if x < MARGIN or y < MARGIN:
            out.append(f"off top/left: {e['type']} {e['id']} at ({x:.0f},{y:.0f})")
        if x + w > bw - MARGIN:
            out.append(f"overflows right: {e['type']} {e['id']} ends at x={x + w:.0f}")
        if y + h > bh - MARGIN:
            out.append(f"overflows bottom: {e['type']} {e['id']} ends at y={y + h:.0f}")
    # bound text wider/taller than its container
    by_id = {e["id"]: e for e in els}
    for e in els:
        cid = e.get("containerId")
        if cid and cid in by_id:
            c = by_id[cid]
            if e["width"] > c["width"] - 4 or e["height"] > c["height"] - 4:
                out.append(f"text spills container: {e['id']} in {cid}")

    # a standalone label sitting on top of a box it isn't bound to
    def rect(e):
        return (e["x"], e["y"], e["x"] + e["width"], e["y"] + e["height"])

    boxes = [e for e in els if e.get("type") == "rectangle"
             and not (e["x"] <= 0 and e["y"] <= 0
                      and e["width"] >= bw and e["height"] >= bh)]
    for i, a in enumerate(boxes):
        ax0, ay0, ax1, ay1 = rect(a)
        for b in boxes[i + 1:]:
            bx0, by0, bx1, by1 = rect(b)
            ox = min(ax1, bx1) - max(ax0, bx0)
            oy = min(ay1, by1) - max(ay0, by0)
            if ox <= 1 or oy <= 1:
                continue
            # a chip nested wholly inside its card is intentional; a partial
            # overlap between two peers is the bug we are hunting
            nested = ((ax0 >= bx0 - 2 and ax1 <= bx1 + 2 and ay0 >= by0 - 2 and ay1 <= by1 + 2)
                      or (bx0 >= ax0 - 2 and bx1 <= ax1 + 2 and by0 >= ay0 - 2 and by1 <= ay1 + 2))
            if not nested:
                out.append(f"boxes overlap: {a['id']} / {b['id']} "
                           f"by {ox:.0f}x{oy:.0f}px")
    # two standalone labels occupying the same space — usually a double-draw
    labels = [e for e in els if e.get("type") == "text" and not e.get("containerId")]
    for i, a in enumerate(labels):
        ax0, ay0, ax1, ay1 = rect(a)
        for b in labels[i + 1:]:
            bx0, by0, bx1, by1 = rect(b)
            ox = min(ax1, bx1) - max(ax0, bx0)
            oy = min(ay1, by1) - max(ay0, by0)
            if ox > 2 and oy > 2:
                out.append(f"labels overlap: {a['id']} ({a['text'].splitlines()[0][:24]!r}) "
                           f"/ {b['id']} ({b['text'].splitlines()[0][:24]!r})")

    for t in els:
        if t.get("type") != "text" or t.get("containerId"):
            continue
        ax0, ay0, ax1, ay1 = rect(t)
        for b in boxes:
            bx0, by0, bx1, by1 = rect(b)
            if not (ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0):
                continue
            inside = ax0 >= bx0 - 2 and ax1 <= bx1 + 2 and ay0 >= by0 - 2 and ay1 <= by1 + 2
            if not inside:
                out.append(f"label crosses box edge: text {t['id']} "
                           f"({t['text'].splitlines()[0][:40]!r}) vs {b['id']}")
    return out


def render(els, w=BOARD_W, h=BOARD_H, ox=0, oy=0, scale=1.0, bg="white"):
    img = Image.new("RGB", (int(w * scale), int(h * scale)), bg)
    d = ImageDraw.Draw(img)

    def T(v):
        return v * scale

    order = {"frame": 0, "rectangle": 1, "line": 2, "arrow": 2, "text": 3}
    for e in sorted(els, key=lambda e: order.get(e.get("type"), 2)):
        t = e.get("type")
        op = e.get("opacity", 100)
        x, y = (e.get("x", 0) - ox), (e.get("y", 0) - oy)
        ew, eh = e.get("width", 0), e.get("height", 0)
        stroke = blend(e.get("strokeColor", "#1e1e1e"), op, bg)
        if t == "frame":
            d.rectangle([T(x), T(y), T(x + ew), T(y + eh)], outline="#dcdcdc",
                        width=max(1, int(2 * scale)))
            d.text((T(x), T(y) - 22 * scale), e.get("name", ""),
                   font=font(16 * scale), fill="#999")
        elif t == "rectangle":
            fill = e.get("backgroundColor", "transparent")
            fill = None if fill in (None, "transparent") else blend(fill, op, bg)
            d.rounded_rectangle([T(x), T(y), T(x + ew), T(y + eh)],
                                radius=max(2, int(10 * scale)), fill=fill,
                                outline=stroke, width=max(1, int(2 * scale)))
        elif t in ("line", "arrow"):
            pts = [(T(x + px), T(y + py)) for px, py in e.get("points", [])]
            if len(pts) > 1:
                d.line(pts, fill=stroke, width=max(1, int(2 * scale)))
        elif t == "text":
            fs = e.get("fontSize", 14)
            f = font(fs * scale, e.get("fontFamily", 3))
            lines = e.get("text", "").split("\n")
            lh = fs * 1.25 * scale
            cy = T(y)
            for ln in lines:
                if e.get("textAlign") == "center":
                    lw = d.textlength(ln, font=f)
                    d.text((T(x + ew / 2) - lw / 2, cy), ln, font=f, fill=stroke)
                else:
                    d.text((T(x), cy), ln, font=f, fill=stroke)
                cy += lh
    return img


def load(p):
    return json.load(open(p))["elements"]


def background(p):
    return json.load(open(p)).get("appState", {}).get("viewBackgroundColor", "white")


def board_size(els):
    """A rect at the origin is the plate and defines the board. Otherwise 16:9."""
    for e in els:
        if e.get("type") == "rectangle" and e["x"] == 0 and e["y"] == 0:
            return int(e["width"]), int(e["height"])
    x1 = max((e["x"] + e.get("width", 0) for e in els), default=BOARD_W)
    y1 = max((e["y"] + e.get("height", 0) for e in els), default=BOARD_H)
    return (BOARD_W, BOARD_H) if x1 <= BOARD_W and y1 <= BOARD_H else (int(x1) + 40, int(y1) + 40)


def bbox(els):
    xs = [e["x"] for e in els] + [e["x"] + e.get("width", 0) for e in els]
    ys = [e["y"] for e in els] + [e["y"] + e.get("height", 0) for e in els]
    return min(xs), min(ys), max(xs), max(ys)


if __name__ == "__main__":
    args = sys.argv[1:]
    sheet_out = None
    if args and args[0] == "--sheet":
        sheet_out, args = args[1], args[2:]

    imgs, bad = [], 0
    for p in args:
        els = load(p)
        name = os.path.basename(p)
        bg = background(p)
        is_map = any(e.get("type") == "frame" for e in els)
        if is_map:
            x0, y0, x1, y1 = bbox(els)
            img = render(els, x1 - x0 + 120, y1 - y0 + 120, x0 - 60, y0 - 60, 0.28, bg)
        else:
            bw, bh = board_size(els)
            v = violations(els, bw, bh)
            if v:
                bad += 1
                print(f"  {name}")
                for msg in v:
                    print(f"      {msg}")
            img = render(els, bw, bh, bg=bg)
        imgs.append((name, img))
        if not sheet_out:
            out = os.path.splitext(p)[0] + ".png"
            img.save(out)
            print(f"  -> {out}")

    if sheet_out:
        cols = 3
        tw_, th_ = 640, 360
        rows = (len(imgs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw_, rows * (th_ + 26)), "#0d0d0d")
        d = ImageDraw.Draw(sheet)
        for i, (name, im) in enumerate(imgs):
            cx, cy = (i % cols) * tw_, (i // cols) * (th_ + 26)
            d.text((cx + 8, cy + 4), name, font=font(15), fill="#bbb")
            sheet.paste(im.resize((tw_ - 8, th_ - 8)), (cx + 4, cy + 24))
        sheet.save(sheet_out, quality=88)
        print(f"  -> {sheet_out}")

    print(f"\n  {len(args)} boards, {bad} with geometry violations")
