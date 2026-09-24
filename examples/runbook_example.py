#!/usr/bin/env python3
"""Runbook archetype: top-to-bottom phase cards converging on a milestone bar.

    python3 examples/runbook_example.py   ->  diagrams/launch-runbook.excalidraw
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from excalidraw_builder import Board  # noqa: E402

b = Board()
X, W = 60, 900
b.title(X, 30, "Campaign Launch Runbook")

phases = [
    ("1. Pre-flight", "☐ Pixel + CAPI verified\n☐ Landing page loads < 2s\n☐ Lead form posts to CRM\n☐ Naming convention applied", "#a5d8ff"),
    ("2. Build", "☐ Campaign + 2 ad sets\n☐ 4 creatives per ad set\n☐ Budget set to daily cap\n☐ Ads in review", "#d0bfff"),
    ("3. Go live", "☐ Ads approved\n☐ Speed-to-lead SMS armed\n☐ First 3 leads spot-checked", "#ffd8a8"),
]
y = 90
cards = []
for header, body, fill in phases:
    z = b.zone(X, y, header)
    card = b.text_box(X + 30, y + 50, body, fill=fill, width=W - 60, align="left")
    b.fit_zone(z, [card], pad=30)
    if cards:
        b.arrow(cards[-1], card)
    cards.append(card)
    y = z.bottom + 50

bar = b.milestone_bar(X, y, W, "LAUNCHED  ·  monitor CPL for 72h before touching anything")
b.arrow(cards[-1], bar)

aside = b.text_box(X + W + 60, 140, "Governing rule\nNever edit a live ad set\nin its learning phase.\nDuplicate instead.",
                   fill="#fff3bf", align="left")
b.arrow(aside, cards[1], dashed=True)

print(b.save(os.path.join("diagrams", "launch-runbook.excalidraw")))
