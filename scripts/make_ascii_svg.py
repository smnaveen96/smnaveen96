"""
Convert a portrait photo into a CLEAN, monochrome ASCII-art SVG (Andrew6rant
style: one light-gray color, subject isolated on a dark background) that "types"
itself in like a terminal, then holds.

Monochrome is deliberate -- per-character rainbow color is what makes ASCII
portraits look noisy. One fill color + a good density ramp + high contrast (so a
busy background washes out to blank) reads as neat and legible.

GitHub renders SVGs embedded via <img> and runs their SMIL animations there (JS
does not run). Each row is revealed with a left-to-right clip wipe plus a small
block cursor riding the wipe edge, staggered top -> bottom, so the whole
portrait prints once. Then it hands off to a slow 3D sway: the portrait is
pre-rendered at a few turn angles (see portrait3d.py) and SMIL steps through
them on an eased loop, so it reads as the head gently turning side to side.
"""
import html
import math
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portrait3d  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# defaults to the prepped grayscale image (see prep_photo.py), which already has
# the background removed + local contrast applied.
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-prepped.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "Naveen-ascii.svg")

# more columns = more detail (eyes need ~6+ chars across to read). the art
# stays ART_W px wide either way; cells shrink, keeping a ~1:1.875 char aspect.
COLS = int(os.environ.get("COLS", 180))
ART_W_TARGET = 800
CELL_W = ART_W_TARGET / COLS
CELL_H = CELL_W * 15 / 8
ROWS = round(COLS * 8 / 15)
RAMP = " .`:-=+*cs#%@"  # bright(sparse) -> dark(dense); leading space clears bg

# the prepped image already has bg removed + CLAHE local contrast, so only
# light global tuning is needed here.
CONTRAST = 1.05
BRIGHTNESS = 1.0
GAMMA = 0.95          # >1 brightens mids -> face lands in sparser chars
WHITE_FLOOR = 0.92    # luminance above this is forced to blank (space)

PAD = 20
TITLEBAR_H = 30
STATUS_H = 30
ART_W = COLS * CELL_W
ART_H = ROWS * CELL_H
CANVAS_W = ART_W + PAD * 2
CANVAS_H = TITLEBAR_H + ART_H + STATUS_H + PAD

BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
TITLE_TEXT = "#7d8590"
INK = "#c9d1d9"      # the single ascii color (matches Andrew6rant)
CURSOR = "#c9d1d9"

# ---- reveal timing (one-shot; a cursor rasters top -> bottom) -------------
ROW_DUR = 5.8 / ROWS  # whole portrait prints in ~6s at any resolution
STAGGER = ROW_DUR       # == ROW_DUR -> a single cursor sweeping down

# ---- 3d sway (loops after the reveal) ---------------------------------------
TURN_MAX = 12         # degrees each way
TURN_FRAMES = 11      # distinct pre-rendered angles (odd -> includes straight-on)
SWAY_PERIOD = 8.0     # seconds for one left -> right -> left sway
SWAY_STEPS = 56       # frame slots per period, eased by a sine
SWAY_BEGIN = ROWS * STAGGER + 1.2

# ---- 1. render each turn angle into a COLS x ROWS character grid ----------
WORK = COLS * 3                                   # working resolution for the turn
gray, mask = portrait3d.load(WORK, prepped=SRC)
gray = np.clip(((gray - 0.5) * CONTRAST + 0.5) * BRIGHTNESS, 0, 1)
z = portrait3d.depth(mask)


def ascii_rows(img):
    small = cv2.resize(img, (COLS, ROWS), interpolation=cv2.INTER_AREA)
    lum = np.power(np.clip(small, 0, 1), GAMMA)
    idx = np.clip(((1.0 - lum) * (len(RAMP) - 1) + 0.5).astype(int), 0, len(RAMP) - 1)
    return ["".join(" " if lum[y, x] >= WHITE_FLOOR else RAMP[idx[y, x]] for x in range(COLS))
            for y in range(ROWS)]


angles = np.linspace(-TURN_MAX, TURN_MAX, TURN_FRAMES)
frames = [ascii_rows(portrait3d.project(gray, mask, z, math.radians(a))) for a in angles]
CENTER = TURN_FRAMES // 2

STATIC = bool(os.environ.get("STATIC"))  # emit frozen state for previews
if os.environ.get("STATIC_FRAME"):       # preview a specific turn angle
    CENTER = int(os.environ["STATIC_FRAME"])
rows_txt = frames[CENTER]

art_top = TITLEBAR_H + PAD * 0.35

# ---- 2. assemble SVG ------------------------------------------------------
parts = []
parts.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
    f'viewBox="0 0 {CANVAS_W} {CANVAS_H}" font-family="ui-monospace, SFMono-Regular, '
    f'Menlo, Consolas, monospace">'
)
parts.append('<defs>'
             f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
             f'</linearGradient></defs>')

parts.append(f'<rect width="{CANVAS_W}" height="{CANVAS_H}" rx="12" fill="url(#bg)"/>')
parts.append(f'<rect x="0.5" y="0.5" width="{CANVAS_W-1}" height="{CANVAS_H-1}" rx="12" '
             f'fill="none" stroke="{FRAME}" stroke-width="1"/>')

parts.append(f'<line x1="0" y1="{TITLEBAR_H}" x2="{CANVAS_W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>')
for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
    parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
parts.append(f'<text x="{CANVAS_W/2}" y="{TITLEBAR_H/2 + 4}" fill="{TITLE_TEXT}" font-size="12" '
             f'text-anchor="middle">smnaveen96@github: ~$ ./portrait.sh</text>')

# one <text> per row (single color -> no per-char markup, tiny file)
font_size = CELL_H * 0.86


def row_text(ry, line):
    y = art_top + ry * CELL_H + CELL_H * 0.74
    return (f'<text xml:space="preserve" x="{PAD}" y="{y:.1f}" fill="{INK}" '
            f'font-size="{font_size:.1f}" textLength="{ART_W}" lengthAdjust="spacing">{html.escape(line)}</text>')


# the typed reveal (straight-on frame); hidden once the sway takes over
parts.append('<g>' if STATIC else f'<g><set attributeName="opacity" to="0" begin="{SWAY_BEGIN:.3f}s"/>')
for ry, line in enumerate(rows_txt):
    row_y = art_top + ry * CELL_H
    delay = ry * STAGGER
    text = row_text(ry, line)

    if STATIC:
        parts.append(text)
        continue

    parts.append(
        f'<clipPath id="r{ry}"><rect x="{PAD}" y="{row_y:.1f}" height="{CELL_H}" width="0">'
        f'<animate attributeName="width" from="0" to="{ART_W}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/></rect></clipPath>'
    )
    parts.append(f'<g clip-path="url(#r{ry})">{text}</g>')
    parts.append(
        f'<rect y="{row_y+1:.1f}" width="{CELL_W}" height="{CELL_H-2}" fill="{CURSOR}" opacity="0">'
        f'<animate attributeName="x" from="{PAD}" to="{PAD+ART_W}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/>'
        f'<set attributeName="opacity" to="0.85" begin="{delay:.3f}s"/>'
        f'<set attributeName="opacity" to="0" begin="{delay+ROW_DUR:.3f}s"/></rect>'
    )
parts.append('</g>')

# the sway: every angle as its own layer, shown one at a time on an eased loop
# (sine through the angles, so it slows at each end like a real turn)
if not STATIC:
    seq = [round((math.sin(2 * math.pi * i / SWAY_STEPS) + 1) / 2 * (TURN_FRAMES - 1))
           for i in range(SWAY_STEPS)]
    key_times = ";".join(f"{i / SWAY_STEPS:.4f}" for i in range(SWAY_STEPS))
    for k, rows in enumerate(frames):
        values = ";".join("1" if f == k else "0" for f in seq)
        parts.append(f'<g opacity="0"><animate attributeName="opacity" values="{values}" '
                     f'keyTimes="{key_times}" calcMode="discrete" dur="{SWAY_PERIOD}s" '
                     f'begin="{SWAY_BEGIN:.3f}s" repeatCount="indefinite"/>')
        parts.extend(row_text(ry, line) for ry, line in enumerate(rows) if line.strip())
        parts.append('</g>')

# status bar with a steady blinking cursor
status_line_y = TITLEBAR_H + ART_H + PAD * 0.35
status_y = status_line_y + 19
parts.append(f'<line x1="0" y1="{status_line_y:.1f}" x2="{CANVAS_W}" y2="{status_line_y:.1f}" stroke="{FRAME}"/>')
parts.append(f'<text x="{PAD}" y="{status_y:.1f}" fill="{TITLE_TEXT}" font-size="13">'
             f'smnaveen96@github:~$ whoami <tspan fill="{INK}">Naveen</tspan></text>')
status_chars = len("smnaveen96@github:~$ whoami Naveen ")   # cursor sits after the name
parts.append(f'<rect x="{PAD + status_chars * 13 * 0.6:.1f}" y="{status_y-12:.1f}" width="8" height="14" fill="{INK}">'
             f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
             f'dur="1s" repeatCount="indefinite"/></rect>')

parts.append("</svg>")
svg = "".join(parts)
with open(OUT, "w") as f:
    f.write(svg)
print("wrote", OUT, len(svg), "bytes;", CANVAS_W, "x", CANVAS_H)
