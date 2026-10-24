#!/usr/bin/env python3
"""Funnel map mode: one content file in, two .excalidraw funnel maps out.

  A, the spine  (top to bottom): numbered steps -> router -> lanes, with a "what you learn"
                column, a per-segment track list, a roadmap and the client math. Best for
                walking someone through the funnel for the first time.
  B, the router (left to right): traffic -> tool -> segments -> unlock -> router -> swimlanes,
                with the client math as a bar chart. Best for a strategy conversation.

Usage:
  python3 scripts/funnel_map.py content.json [--out diagrams/] [--png]

Content schema: see examples/funnel/funnel.example.json. Zero dependencies; --png renders a
QA preview with headless Chrome if it is installed.
Rules baked in: box size from text, equal-width rows, bound arrows with fixedPoint, color = one
meaning (green free, amber low ticket / needs setup, red high ticket, teal data, red stop).
"""
import argparse
import html
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap

FONT, CW = 6, 0.56  # Nunito on Excalidraw; average character width factor
INK, MUTED, LINE = "#2b211c", "#6e5c50", "#d9cfc6"
BRAND, BRAND_SOFT = "#8c7361", "#f6efe6"
TONES = {"free": ("#3f7d4f", "#e8f3ea"), "low": ("#a0732f", "#fbf1df"), "high": ("#9a3b2a", "#fbe7e2"),
         "data": ("#1f6f78", "#e3f4f5"), "stop": ("#c0392b", "#fdecea"), "brand": (BRAND, BRAND_SOFT),
         "neutral": (LINE, "#ffffff")}
DOT = {"live": "#22c55e", "part": "#f59e0b", "build": "#ef4444"}


class Doc:
    def __init__(self):
        self.els, self.arrows, self._id = [], [], itertools.count()

    def nid(self, p): return f"{p}{next(self._id)}"

    def base(self, t, x, y, w, h, **k):
        e = {"type": t, "id": k.pop("id", self.nid(t[0])), "x": x, "y": y, "width": w, "height": h, "versionNonce": 0,
                 "isDeleted": False, "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid", "roughness": 0,
                 "opacity": 100, "angle": 0, "strokeColor": INK, "backgroundColor": "transparent", "seed": 1, "groupIds": [],
                 "frameId": None, "boundElements": None, "updated": 1, "link": None, "locked": False, "roundness": None}
        e.update(k); return e

    def text(self, x, y, s, fs=15, color=INK, align="left", w=None, group=None, link=None):
        lines = s.split("\n")
        tw = w or max(len(l) for l in lines) * fs * CW
        if align == "center" and w is None: x -= tw / 2
        e = self.base("text", x, y, tw, len(lines) * fs * 1.25, text=s, originalText=s, fontSize=fs,
                      fontFamily=FONT, textAlign=align, verticalAlign="top", containerId=None, autoResize=True,
                      lineHeight=1.25, strokeColor=color, groupIds=[group] if group else [], link=link)
        self.els.append(e); return e

    def rect(self, x, y, w, h, fill="#ffffff", stroke=LINE, sw=1.5, dashed=False, round_=True, group=None):
        e = self.base("rectangle", x, y, w, h, backgroundColor=fill, strokeColor=stroke, strokeWidth=sw,
                      strokeStyle="dashed" if dashed else "solid", roundness={"type": 3} if round_ else None,
                      groupIds=[group] if group else [])
        self.els.append(e); return e

    def dot(self, x, y, status, group=None):
        e = self.base("ellipse", x, y, 10, 10, backgroundColor=DOT[status], strokeColor=DOT[status],
                      strokeWidth=1, groupIds=[group] if group else [])
        self.els.append(e); return e

    def diamond(self, cx, cy, w, h, l1, l2, fill, stroke):
        g = self.nid("g")
        d = self.base("diamond", cx - w / 2, cy - h / 2, w, h, backgroundColor=fill, strokeColor=stroke,
                      strokeWidth=2, groupIds=[g])
        self.els.append(d)
        self.text(cx, cy - 20, l1, 15, stroke, "center", group=g)
        self.text(cx, cy, l2, 12, stroke, "center", group=g)
        return d

    @staticmethod
    def wrap(s, w, fs):
        return textwrap.wrap(s, max(8, int(w / (fs * CW)))) or [""]

    def card(self, x, y, w, title, items, h=None, fill="#ffffff", stroke=LINE, title_fs=17, fs=15,
             title_color=INK, pad=18):
        g = self.nid("g")
        th = len(self.wrap(title, w - 2 * pad, title_fs)) * title_fs * 1.25 if title else 0
        body = sum(len(self.wrap(t, w - 54, fs)) * fs * 1.25 + 8 for t, _ in items)
        h = max(h or 0, pad * 2 + th + (10 if title else 0) + body)
        r = self.rect(x, y, w, h, fill, stroke, group=g)
        cy = y + pad
        if title:
            self.text(x + pad, cy, "\n".join(self.wrap(title, w - 2 * pad, title_fs)), title_fs, title_color, group=g)
            cy += th + 10
        for t, st in items:
            lines = self.wrap(t, w - 54, fs)
            self.dot(x + pad, cy + fs * 0.35, st, group=g)
            self.text(x + pad + 20, cy, "\n".join(lines), fs, INK, group=g)
            cy += len(lines) * fs * 1.25 + 8
        return r

    def arrow(self, a, b, sa, sb, via=None, color=INK, width=2, dashed=False):
        sx, sy = a["x"] + a["width"] * sa[0], a["y"] + a["height"] * sa[1]
        ex, ey = b["x"] + b["width"] * sb[0], b["y"] + b["height"] * sb[1]
        pts = [[0, 0]] + [[px - sx, py - sy] for px, py in (via or [])] + [[ex - sx, ey - sy]]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        e = self.base("arrow", sx + min(xs), sy + min(ys), max(xs) - min(xs), max(ys) - min(ys),
                      points=[[px - min(xs), py - min(ys)] for px, py in pts], startArrowhead=None,
                      endArrowhead="arrow", strokeColor=color, strokeWidth=width,
                      strokeStyle="dashed" if dashed else "solid",
                      startBinding={"elementId": a["id"], "focus": 0, "gap": 4, "fixedPoint": list(sa), "mode": "orbit"},
                      endBinding={"elementId": b["id"], "focus": 0, "gap": 4, "fixedPoint": list(sb), "mode": "orbit"})
        for s in (a, b):
            s["boundElements"] = (s["boundElements"] or []) + [{"id": e["id"], "type": "arrow"}]
        self.arrows.append(e); return e

    def lint(self):
        bad = []
        for t in (e for e in self.els if e["type"] == "text" and e["groupIds"]):
            r = next((e for e in self.els if e["type"] == "rectangle" and e["groupIds"] == t["groupIds"]), None)
            if r and (t["x"] + t["width"] > r["x"] + r["width"] + 1 or t["y"] + t["height"] > r["y"] + r["height"] + 1):
                bad.append(t["text"][:50])
        return bad

    def save(self, path, png=False):
        doc = {"type": "excalidraw", "version": 2, "source": "excalidraw-diagrams/funnel_map",
               "elements": self.els + self.arrows,
               "appState": {"gridSize": None, "viewBackgroundColor": "#fbfafa"}, "files": {}}
        with open(path, "w") as f: json.dump(doc, f, indent=1)
        if png: self.preview(path[:-len(".excalidraw")] + ".png")
        return path

    def preview(self, png):
        chrome = next((p for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                                   shutil.which("google-chrome") or "", shutil.which("chromium") or "") if p and os.path.exists(p)), None)
        if not chrome:
            print("  (no Chrome found, skipped PNG preview)"); return
        els = self.els + self.arrows
        W = max(e["x"] + e["width"] for e in els) + 60
        H = max(e["y"] + e["height"] for e in els) + 60
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" style="background:#fbfafa;font-family:Nunito,Helvetica,Arial">',
             '<defs><marker id="m" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10z" fill="context-stroke"/></marker></defs>']
        for e in els:
            dash = ' stroke-dasharray="8 6"' if e["strokeStyle"] == "dashed" else ""
            if e["type"] == "rectangle":
                o.append(f'<rect x="{e["x"]}" y="{e["y"]}" width="{e["width"]}" height="{e["height"]}" rx="{12 if e["roundness"] else 0}" fill="{e["backgroundColor"]}" stroke="{e["strokeColor"]}" stroke-width="{e["strokeWidth"]}"{dash}/>')
            elif e["type"] == "ellipse":
                o.append(f'<ellipse cx="{e["x"] + e["width"] / 2}" cy="{e["y"] + e["height"] / 2}" rx="{e["width"] / 2}" ry="{e["height"] / 2}" fill="{e["backgroundColor"]}"/>')
            elif e["type"] == "diamond":
                x, y, w, h = e["x"], e["y"], e["width"], e["height"]
                o.append(f'<polygon points="{x + w / 2},{y} {x + w},{y + h / 2} {x + w / 2},{y + h} {x},{y + h / 2}" fill="{e["backgroundColor"]}" stroke="{e["strokeColor"]}" stroke-width="2"/>')
            elif e["type"] == "text":
                anchor = {"left": "start", "center": "middle", "right": "end"}[e["textAlign"]]
                tx = e["x"] + (e["width"] / 2 if anchor == "middle" else 0)
                for i, l in enumerate(e["text"].split("\n")):
                    o.append(f'<text x="{tx}" y="{e["y"] + (i + 0.85) * e["fontSize"] * 1.25}" font-size="{e["fontSize"]}" fill="{e["strokeColor"]}" text-anchor="{anchor}">{html.escape(l)}</text>')
            elif e["type"] == "arrow":
                p = " ".join(f'{e["x"] + a},{e["y"] + b}' for a, b in e["points"])
                o.append(f'<polyline points="{p}" fill="none" stroke="{e["strokeColor"]}" stroke-width="{e["strokeWidth"]}"{dash} marker-end="url(#m)"/>')
        o.append("</svg>")
        svg = png[:-4] + ".svg"
        with open(svg, "w") as f: f.write("\n".join(o))
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={int(W)},{int(H)}",
                        f"--screenshot={os.path.abspath(png)}", "file://" + os.path.abspath(svg)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        os.remove(svg)


# ---------------- helpers shared by both variations ----------------
def items(lst): return [(t, s) for t, s in lst]


def legend(d, C, x, y):
    labels = C.get("legend", {"live": "built", "part": "built, needs setup", "build": "to build"})
    d.text(x, y, "Dots:", 13, MUTED)
    cx = x + 48
    for st in ("live", "part", "build"):
        d.dot(cx, y + 4, st); d.text(cx + 16, y, labels[st], 13, MUTED); cx += 30 + len(labels[st]) * 13 * CW + 16


def backsolve(M):
    steps = M["steps"]
    vals = [M["goal"]]
    for _, r in reversed(steps[1:]):
        vals.append(math.ceil(vals[-1] / r))
    vals = list(reversed(vals))
    return [(steps[i][0], vals[i], steps[i][1]) for i in range(len(steps))]


def money_lines(M, rows):
    out = []
    if M.get("low_price") and M.get("low_buy") and M.get("leads_row") is not None:
        buyers = math.ceil(rows[M["leads_row"]][1] * M["low_buy"])
        out.append(f"Plus about {buyers} buyers of the ${M['low_price']:,} offer a month at {round(M['low_buy'] * 100)}% of leads")
        if M.get("high_price"):
            out.append(f"Revenue: {M['goal']} x ${M['high_price']:,} = ${M['goal'] * M['high_price']:,} in new {M.get('high_term', 'client')} contracts, plus {buyers} x ${M['low_price']:,} = ${buyers * M['low_price']:,}")
    return out


def link_line(d, card, url, label, color):
    if not url: return
    card["link"] = url
    d.text(card["x"], card["y"] + card["height"] + 8, label, 13, color, link=url)


def roadmap(d, C, x, y, total_w):
    d.text(x, y, C.get("roadmap_title", "ROADMAP"), 22, INK)
    y += 40
    R = C["roadmap"]; n, g = len(R), 22
    cw = (total_w - (n - 1) * g) / n
    cards = [d.card(x + i * (cw + g), y, cw, f"{p['when']}  ·  {p['name']}",
                    [(s, "build") for s in p["items"]] + ([(p["watch"], "part")] if p.get("watch") else []),
                    fill="#ffffff", stroke=BRAND, title_fs=16, fs=14) for i, p in enumerate(R)]
    hh = max(c["height"] for c in cards)
    for c in cards: c["height"] = hh
    for a, b in itertools.pairwise(cards): d.arrow(a, b, (1, 0.5), (0, 0.5), color=BRAND)
    return y + hh


# ---------------- A: the spine ----------------
def variation_a(C):
    d = Doc()
    d.text(60, 40, C["title"], 30, INK)
    d.text(60, 84, C.get("subtitle_a", "Variation A, the spine. Every step people take, what they get, what you learn, and where each lane leads."), 15, MUTED)
    legend(d, C, 60, 116)
    X, W, GAP, y = 60, 860, 46, 160
    flow = [("TRAFFIC", C["traffic"], "neutral")] + [(s["title"], s["items"], s.get("tone", "brand")) for s in C["steps"]]
    spine = []
    for i, (title, its, tone) in enumerate(flow, 1):
        stroke, fill = TONES[tone]
        r = d.card(X, y, W, f"{i}  {title}", items(its), fill=fill, stroke=stroke)
        spine.append(r); y = r["y"] + r["height"] + GAP
    for a, b in itertools.pairwise(spine): d.arrow(a, b, (0.5, 1), (0.5, 0))
    tool_i = next((i for i, s in enumerate(C["steps"], 1) if s.get("is_tool")), 1)
    link_line(d, spine[tool_i], C.get("links", {}).get("tool"), "Open it: " + C.get("links", {}).get("tool", ""), BRAND)
    rt = C["router"]
    dm = d.diamond(X + W / 2, y + 70, 360, 140, f"{len(flow) + 1}  {rt['label']}", rt["sub"], BRAND_SOFT, BRAND)
    d.arrow(spine[-1], dm, (0.5, 1), (0.5, 0))
    y = dm["y"] + dm["height"] + 60
    L = C["lanes"]; n, lg = len(L), 26
    lw = (W - (n - 1) * lg) / n
    lanes = []
    for i, ln in enumerate(L):
        col, soft = TONES[ln["tone"]]
        lanes.append(d.card(X + i * (lw + lg), y, lw, ln["name"] + "\n" + ln["who"], items(ln["steps"]),
                            fill=soft, stroke=col, title_fs=15, fs=14, title_color=col))
    h = max(l["height"] for l in lanes)
    for l in lanes: l["height"] = h
    for i, l in enumerate(lanes):
        fx = (i + 0.5) / n
        d.arrow(dm, l, (fx, 1) if abs(fx - 0.5) > 0.01 else (0.5, 1), (0.5, 0), color=TONES[L[i]["tone"]][0],
                via=None if abs(fx - 0.5) < 0.01 else [(dm["x"] + dm["width"] * fx, l["y"] - 28), (l["x"] + l["width"] / 2, l["y"] - 28)])
    ly = y + h + 18
    for i, note in enumerate(C.get("lane_notes", [])):
        d.text(X + 10, ly + i * 20, note, 13, MUTED)
    bottom = ly + 20 * len(C.get("lane_notes", [])) + 40
    RX, RW, ry = X + W + 70, 600, 160
    d.text(RX, ry, C.get("learn_title", "WHAT YOU LEARN"), 13, TONES["data"][0])
    if C.get("links", {}).get("details"):
        d.text(RX + 220, ry, "How it works ->", 13, TONES["data"][0], link=C["links"]["details"])
    ry += 26
    dc = []
    for blk in C["learn"]:
        r = d.card(RX, ry, RW, blk["title"], items(blk["items"]), fill=TONES["data"][1], stroke=TONES["data"][0], title_fs=16, fs=14)
        dc.append(r); ry = r["y"] + r["height"] + 22
    src = [i for i, s in enumerate(C["steps"], 1) if s.get("feeds_learn")]
    for k, si in enumerate(src[:len(dc)]):
        a, b = spine[si], dc[k]
        d.arrow(a, b, (1, 0.5), (0, 0.5), color=TONES["data"][0], dashed=True,
                via=[(X + W + 35, a["y"] + a["height"] / 2), (X + W + 35, b["y"] + b["height"] / 2)])
    if C.get("loop"):
        d.arrow(dc[-1], spine[0], (1, 0.5), (1, 0.25), color=TONES["data"][0], dashed=True,
                via=[(RX + RW + 30, dc[-1]["y"] + dc[-1]["height"] / 2), (RX + RW + 30, 150), (X + W + 18, 150),
                     (X + W + 18, spine[0]["y"] + spine[0]["height"] * 0.25)])
        d.text(RX + 230, 132, "loop: " + C["loop"], 13, TONES["data"][0])
    if C.get("segments"):
        ry += 18
        d.text(RX, ry, C.get("segments_title", "TRACK + TOOL BY SEGMENT"), 13, BRAND); ry += 26
        for sg in C["segments"]:
            r = d.card(RX, ry, RW, f"{sg['name']}  ·  {sg['rule']}", [(f"{sg['track']}  ·  {sg['tool']}", "build")],
                       fill="#ffffff", stroke=LINE, title_fs=15, fs=14, pad=14)
            ry = r["y"] + r["height"] + 12
    y0 = max(bottom, ry + 30)
    tw = RX + RW - 60
    y1 = roadmap(d, C, 60, y0, tw) + 50 if C.get("roadmap") else y0
    if C.get("math"):
        M = C["math"]; rows = backsolve(M)
        lines = [f"{nm}: {v:,}" + (f"  ({round(r * 100)}% of the step above)" if r else "") for nm, v, r in rows] + money_lines(M, rows)
        d.card(60, y1, tw, f"THE MATH TO {M['goal']} {M['goal_label'].upper()}  ·  {M.get('note', 'every rate is a placeholder until you have real numbers')}",
               [(s, "part") for s in lines], fill=TONES["low"][1], stroke=TONES["low"][0], title_fs=16, fs=15)
    return d


# ---------------- B: the router ----------------
def variation_b(C):
    d = Doc()
    d.text(60, 40, C["title"] + ": the router map", 30, INK)
    d.text(60, 84, C.get("subtitle_b", "Variation B, left to right. People sort themselves by segment, then by the help they want. The math at the bottom says how much traffic a client goal needs."), 15, MUTED)
    legend(d, C, 60, 116)
    top = 180
    c1x, c1w = 60, 300
    d.text(c1x, top - 24, "TRAFFIC", 13, BRAND)
    tc, ty = [], top
    for t, st in C["traffic"]:
        r = d.card(c1x, ty, c1w, None, [(t, st)], fill="#ffffff", stroke=LINE, fs=14, pad=14)
        tc.append(r); ty = r["y"] + r["height"] + 14
    tool = next((s for s in C["steps"] if s.get("is_tool")), C["steps"][0])
    c2x, c2w = c1x + c1w + 80, 340
    d.text(c2x, top - 24, tool.get("short", "THE TOOL"), 13, BRAND)
    q = d.card(c2x, top, c2w, tool.get("card_title", tool["title"]), items(tool["items"]), fill=BRAND_SOFT, stroke=BRAND, title_fs=16, fs=14)
    if C.get("links", {}).get("tool"):
        q["link"] = C["links"]["tool"]
        d.text(c2x + c2w - 16 * 13 * CW, top - 24, "Open it ->", 13, BRAND, link=C["links"]["tool"])
    for t in tc:
        d.arrow(t, q, (1, 0.5), (0, 0.5), color=MUTED, via=[(c1x + c1w + 40, t["y"] + t["height"] / 2), (c1x + c1w + 40, q["y"] + q["height"] / 2)])
    low_y = q["y"] + q["height"]
    if C.get("stop"):
        sc, sf = TONES["stop"]
        s = d.card(c2x, low_y + 40, c2w, C["stop"]["title"], items(C["stop"]["items"]), fill=sf, stroke=sc, title_fs=15, fs=13, title_color=sc)
        d.arrow(q, s, (0.5, 1), (0.5, 0), color=sc, dashed=True); low_y = s["y"] + s["height"]
    c3x, c3w = c2x + c2w + 80, 420
    d.text(c3x, top - 24, C.get("segments_title_b", "RESULT  ·  segment, then its track"), 13, BRAND)
    ty, sg = top, []
    for s in C.get("segments", []):
        r = d.card(c3x, ty, c3w, f"{s['name']}  ·  {s['rule']}", [(f"{s['track']}  ·  {s['tool']}", "build")], fill="#ffffff", stroke=LINE, title_fs=15, fs=13, pad=12)
        sg.append(r); ty = r["y"] + r["height"] + 10
    for r in sg:
        d.arrow(q, r, (1, 0.3), (0, 0.5), color=INK, via=[(c3x - 40, q["y"] + q["height"] * 0.3), (c3x - 40, r["y"] + r["height"] / 2)])
    gate = next((s for s in C["steps"] if s.get("is_gate")), None)
    unlock = d.card(c3x, ty + 16, c3w, gate["title"] if gate else "UNLOCK", items(gate["items"] if gate else []), fill=TONES["low"][1], stroke=TONES["low"][0], title_fs=15, fs=13)
    c4x, mid = c3x + c3w + 80, top + 260
    dm = d.diamond(c4x + 130, mid, 260, 150, C["router"]["label"], C["router"]["sub"], BRAND_SOFT, BRAND)
    d.arrow(unlock, dm, (1, 0.5), (0.5, 1), color=INK, via=[(c4x + 130, unlock["y"] + unlock["height"] / 2)])
    c5x, lane_w, ly, lanes = c4x + 300, 980, top - 10, []
    for ln in C["lanes"]:
        col, soft = TONES[ln["tone"]]
        g = d.nid("g")
        steps = ln["steps"]
        sw = (lane_w - 240 - 20 - (len(steps) - 1) * 14) / len(steps)
        inner = max(106, max(Doc.wrap(t, sw - 54, 13).__len__() for t, _ in steps) * 13 * 1.25 + 40)
        lane_h = inner + 44
        bg = d.rect(c5x, ly, lane_w, lane_h, soft, col, group=g)
        d.text(c5x + 18, ly + 14, ln["name"], 17, col, group=g)
        d.text(c5x + 18, ly + 40, "\n".join(Doc.wrap(ln["who"], 200, 13)), 13, MUTED, group=g)
        prev = None
        for i, (t, st) in enumerate(steps):
            r = d.card(c5x + 240 + i * (sw + 14), ly + 22, sw, None, [(t, st)], h=inner, fill="#ffffff", stroke=col, fs=13, pad=12)
            if prev: d.arrow(prev, r, (1, 0.5), (0, 0.5), color=col)
            prev = r
        if ln.get("note"): d.text(c5x + 18, ly + lane_h - 30, ln["note"], 13, col)
        lanes.append(bg); ly += lane_h + 24
    for i, l in enumerate(lanes):
        d.arrow(dm, l, (1, 0.5), (0, 0.5), color=TONES[C["lanes"][i]["tone"]][0], via=[(c5x - 30, mid), (c5x - 30, l["y"] + l["height"] / 2)])
    total_w = c5x + lane_w - 60
    by = max(unlock["y"] + unlock["height"], ly, low_y) + 60
    if C.get("learn"):
        d.text(60, by - 26, C.get("learn_title", "WHAT YOU LEARN"), 13, TONES["data"][0])
        if C.get("links", {}).get("details"):
            d.text(60 + 560, by - 26, "How it works ->", 13, TONES["data"][0], link=C["links"]["details"])
        n, g = len(C["learn"]), 24
        cw = (total_w - (n - 1) * g) / n
        dc = [d.card(60 + i * (cw + g), by, cw, b["title"], items(b["items"]), fill=TONES["data"][1], stroke=TONES["data"][0], title_fs=16, fs=14) for i, b in enumerate(C["learn"])]
        hh = max(r["height"] for r in dc)
        for r in dc: r["height"] = hh
        if C.get("loop"): d.text(60, by + hh + 14, "Loop: " + C["loop"], 13, TONES["data"][0])
        by += hh + 80
    yy = by
    if C.get("math"):
        M = C["math"]; rows = backsolve(M)
        d.text(60, yy, f"THE MATH TO {M['goal']} {M['goal_label'].upper()}", 22, INK)
        d.text(60, yy + 34, M.get("note_b", "Every rate is a placeholder. Replace them with real numbers after 30 days."), 14, TONES["low"][0])
        BAR_X, BAR_MAX = 300, 900
        yy += 74
        top_v = rows[0][1]
        hot = set(M.get("high_rows", []))
        for k, (nm, v, r) in enumerate(rows):
            d.text(60, yy + 2, nm, 15, INK)
            col = TONES["high"][0] if k in hot else (TONES["low"][0] if k == M.get("leads_row") else BRAND)
            d.rect(BAR_X, yy, max(6, BAR_MAX * v / top_v), 24, col, col, round_=False)
            d.text(BAR_X + BAR_MAX + 12, yy + 2, f"{v:,}", 15, INK)
            d.text(BAR_X + BAR_MAX + 100, yy + 2, f"{round(r * 100)}% of the row above" if r else M.get("unit", "per month"), 13, MUTED)
            yy += 36
        for s in money_lines(M, rows):
            d.text(60, yy + 8, s, 15, TONES["low"][0]); yy += 26
        yy += 40
    if C.get("roadmap"): roadmap(d, C, 60, yy, total_w)
    return d


def slugify(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("content"); ap.add_argument("--out", default="diagrams"); ap.add_argument("--png", action="store_true")
    a = ap.parse_args()
    with open(a.content) as f:
        C = json.load(f)
    os.makedirs(a.out, exist_ok=True)
    slug = C.get("slug") or slugify(C["title"])
    for tag, fn in (("A-spine", variation_a), ("B-router", variation_b)):
        d = fn(C)
        p = d.save(os.path.join(a.out, f"{slug}-{tag}.excalidraw"), png=a.png)
        bad = d.lint()
        print(f"{p}  ({len(d.els) + len(d.arrows)} elements){'  LINT: ' + str(bad) if bad else ''}")


if __name__ == "__main__":
    sys.exit(main())
