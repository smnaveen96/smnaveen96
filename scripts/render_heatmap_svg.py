#!/usr/bin/env python3
"""
Render data/contributions.json (produced by fetch_contributions.py) as a proper
GitHub-style contribution heatmap SVG: a grid of rounded, colored BOXES in the
classic 53-week x 7-day calendar on a soft green field, revealed once with a
diagonal pop-in wave (CSS keyframes, plays on load then freezes) that lights
the name NAVEEN into the grid as it passes (where it stays), then a sparse,
slow glitter of a few boxes that plays twice and settles, a Less->More legend, and a real stats footer.

Run by .github/workflows/update-profile-art.yml after fetch_contributions.py.
"""
import datetime
import json
import os
import random

HERE = os.path.dirname(__file__)
IN_PATH = os.path.join(HERE, "..", "data", "contributions.json")
OUT_PATH = os.path.join(HERE, "..", "contrib-heatmap.svg")

# GitHub-ish green ramp: empty -> brightest. Level 5 is a brighter neon top end.
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

CELL = 12
GAP = 3
STEP = CELL + GAP
PAD = 22
LEFT_LABEL_W = 30
TOP_LABEL_H = 20
TITLEBAR_H = 30

BG = "#0a0e14"
BG2 = "#0d1420"
FRAME = "#1f6feb"
MUTED = "#7d8590"
TEXT = "#e6edf3"
ACCENT = "#22d3ee"
GREEN = "#39d353"
GOLD = "#f2cc60"

# reveal timing (one-shot)
COL_T = 0.03    # per-column delay contribution (left -> right sweep)
ROW_T = 0.045   # per-row delay contribution (top -> bottom cascade)
CELL_DUR = 0.5

# empty days get a soft, varied dark-green texture instead of black, so the
# name sits in a field of green rather than shouting off a black grid
FIELD_GREENS = ["#0d3a22", "#0e4429", "#0e4429", "#104a2d", "#12532f", "#145c33"]

# the name, drawn into the grid in a 5x7 pixel font. its cells pop in with the
# reveal wave itself (slight bounce, no flash), a soft shine runs across the
# word once the wave has passed, and it stays lit.
NAME = "NAVEEN"
LETTER_GAP = 2
POP_DUR = 0.55
SHINE_BAND = 225      # px width of the soft sheen band that sweeps across the word
SHINE_SPEED = 375     # px / s
SHINE_FILL = "#b4f5c0"
SHINE_PEAK = 0.35
NAME_GREENS = ["#2cb34d", "#30c452", "#28ad48"]   # a few steps above the field: readable, not loud

# after the reveal, a handful of boxes glint now and then -- each on its own
# slow, offset cycle so only a scattered few are lit at once. each glint is a
# short chain of SMIL <set> steps (dim -> bright -> dim) rather than a CSS
# keyframe: discrete steps let the browser redraw only when a glint changes.
# it stops after GLITTER_PASSES cycles: even stepped, an endless loop kept a
# phone's main thread ~15% busy for as long as the profile stayed open.
GLITTER_FIELD = 44        # field boxes that glint (the name itself stays calm)
GLITTER_MIN, GLITTER_MAX = 7.0, 13.0   # cycle length range, seconds
GLITTER_PASSES = 2        # glints per box, then the graph goes still
GLITTER_STEPS = [(0.45, 0.35), (1.0, 0.6), (0.45, 0.35)]   # (opacity, seconds)
FONT = {
    "N": ["#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "V": ["#...#", "#...#", "#...#", "#...#", ".#.#.", ".#.#.", "..#.."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
}


def name_cells(n_cols):
    """(col, row, delay) for each cell spelling NAME, centred horizontally."""
    pitch = 5 + LETTER_GAP
    left = (n_cols - (len(NAME) * pitch - LETTER_GAP)) // 2
    cells = []
    for li, ch in enumerate(NAME):
        for ri, line in enumerate(FONT[ch]):
            for ci, px in enumerate(line):
                if px == "#":
                    col = left + li * pitch + ci
                    cells.append((col, ri, col * COL_T + ri * ROW_T))
    return cells


def level_for(count):
    if count == 0:
        return 0
    if count <= 5:
        return 1
    if count <= 15:
        return 2
    if count <= 30:
        return 3
    if count <= 50:
        return 4
    return 5


def build_grid(days):
    first = datetime.date.fromisoformat(days[0]["date"])
    lead_pad = (first.weekday() + 1) % 7  # sunday=0
    grid = []
    col = [None] * lead_pad
    for d in days:
        date = datetime.date.fromisoformat(d["date"])
        weekday = (date.weekday() + 1) % 7
        while len(col) < weekday:
            col.append(None)
        col.append((d["date"], d["count"], level_for(d["count"])))
        if len(col) == 7:
            grid.append(col)
            col = []
    if col:
        while len(col) < 7:
            col.append(None)
        grid.append(col)
    return grid


def render(data):
    days = data["days"]
    grid = build_grid(days)
    n_cols = len(grid)
    art_w = n_cols * STEP
    art_h = 7 * STEP

    month_labels = []
    seen_months = set()
    for ci, column in enumerate(grid):
        for cell in column:
            if cell is None:
                continue
            date = datetime.date.fromisoformat(cell[0])
            key = (date.year, date.month)
            if key not in seen_months and date.day <= 7:
                seen_months.add(key)
                month_labels.append((ci, date.strftime("%b")))
            break

    canvas_w = PAD + LEFT_LABEL_W + art_w + PAD
    stats_h = 88
    canvas_h = TITLEBAR_H + TOP_LABEL_H + art_h + stats_h + PAD

    css = f"""
@keyframes cell {{
  0%   {{ opacity: 0; transform: scale(.3); }}
  65%  {{ opacity: 1; transform: scale(1.08); }}
  100% {{ opacity: 1; transform: scale(1); }}
}}
.c {{ opacity: 0; transform-box: fill-box; transform-origin: center;
      animation: cell {CELL_DUR:.2f}s cubic-bezier(.2,.8,.2,1) both; }}
@keyframes lit {{
  0%   {{ opacity: 0; transform: scale(.2); }}
  55%  {{ opacity: 1; transform: scale(1.22); }}
  100% {{ opacity: 1; transform: scale(1); }}
}}
.n {{ opacity: 0; transform-box: fill-box; transform-origin: center;
      animation: lit {POP_DUR:.2f}s cubic-bezier(.3,1.4,.5,1) both; }}
@media (prefers-reduced-motion: reduce) {{ .c, .n {{ opacity: 1; transform: none; animation: none; }} .g, .s {{ display: none; }} }}
""".strip()

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        f'<style>{css}</style>',
        '<defs>'
        f'<linearGradient id="hbg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient>'
        '</defs>',
        f'<rect width="{canvas_w}" height="{canvas_h}" rx="12" fill="url(#hbg)"/>',
        f'<rect x="0.5" y="0.5" width="{canvas_w-1}" height="{canvas_h-1}" rx="12" '
        f'fill="none" stroke="{FRAME}" stroke-width="1" stroke-opacity="0.55"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{canvas_w}" y2="{TITLEBAR_H}" stroke="{FRAME}" stroke-opacity="0.35"/>',
    ]
    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
    parts.append(f'<text x="{canvas_w/2}" y="{TITLEBAR_H/2 + 4}" fill="{MUTED}" font-size="12" '
                 f'text-anchor="middle">smnaveen96@github: ~/contributions --graph</text>')

    grid_top = TITLEBAR_H + TOP_LABEL_H
    grid_left = PAD + LEFT_LABEL_W

    for ci, label in month_labels:
        x = grid_left + ci * STEP
        parts.append(f'<text x="{x}" y="{TITLEBAR_H + 14}" fill="{MUTED}" font-size="10">{label}</text>')

    for wi, wname in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = grid_top + wi * STEP + CELL * 0.78
        parts.append(f'<text x="{PAD}" y="{y:.1f}" fill="{MUTED}" font-size="9">{wname}</text>')

    occupied = {(ci, ri) for ci, column in enumerate(grid) for ri, cell in enumerate(column) if cell}
    cells = [c for c in name_cells(n_cols) if c[:2] in occupied]
    name_pos = {c[:2] for c in cells}

    # the boxes -- each a rounded rect, diagonal pop-in reveal (once, freeze).
    # boxes under the name are skipped: the name's own boxes cover them.
    # (no <title> tooltips -- an svg shown as an <img> never gets hover)
    for ci, column in enumerate(grid):
        gx = grid_left + ci * STEP
        for ri, cell in enumerate(column):
            if cell is None or (ci, ri) in name_pos:
                continue
            date_s, count, lvl = cell
            gy = grid_top + ri * STEP
            delay = ci * COL_T + ri * ROW_T
            fill = PALETTE[lvl] if lvl else random.Random(date_s).choice(FIELD_GREENS)
            parts.append(
                f'<rect class="c" x="{gx}" y="{gy}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{fill}" style="animation-delay:{delay:.3f}s"/>'
            )

    # the name -- its own boxes, popping in with the wave; they light up once and stay
    name_rects = []
    for ci, ri, delay in cells:
        xy = f'x="{grid_left + ci * STEP}" y="{grid_top + ri * STEP}" width="{CELL}" height="{CELL}" rx="2.5"'
        name_rects.append(f'<rect {xy}/>')
        parts.append(f'<rect class="n" {xy} fill="{NAME_GREENS[(ci * 7 + ri) % 3]}" '
                     f'style="animation-delay:{delay:.3f}s"/>')

    # sheen: one soft gradient band, clipped to the name's boxes, swept across once
    shine_start = max(d for _, _, d in cells) + POP_DUR
    name_l = grid_left + min(c[0] for c in cells) * STEP
    name_r = grid_left + (max(c[0] for c in cells) + 1) * STEP
    sweep = (name_r - name_l + SHINE_BAND) / SHINE_SPEED
    parts.append(
        f'<defs><clipPath id="nm">{"".join(name_rects)}</clipPath>'
        f'<linearGradient id="sh"><stop offset="0" stop-color="{SHINE_FILL}" stop-opacity="0"/>'
        f'<stop offset=".6" stop-color="{SHINE_FILL}" stop-opacity="{SHINE_PEAK}"/>'
        f'<stop offset="1" stop-color="{SHINE_FILL}" stop-opacity="0"/></linearGradient></defs>'
        f'<rect class="s" x="{name_l - SHINE_BAND}" y="{grid_top}" width="{SHINE_BAND}" height="{7 * STEP}" '
        f'fill="url(#sh)" clip-path="url(#nm)">'
        f'<animate attributeName="x" from="{name_l - SHINE_BAND}" to="{name_r}" begin="{shine_start:.2f}s" '
        f'dur="{sweep:.2f}s" fill="freeze"/></rect>'
    )

    # glitter -- fixed seed so the daily refresh doesn't reshuffle it
    rng = random.Random("glitter")
    field_pos = sorted(occupied - name_pos)
    settle = shine_start + sweep
    for gi, (ci, ri) in enumerate(rng.sample(field_pos, GLITTER_FIELD)):
        cycle = rng.uniform(GLITTER_MIN, GLITTER_MAX)
        first = settle + rng.uniform(0, cycle)
        starts = ";".join(f"{first + k * cycle:.2f}s" for k in range(GLITTER_PASSES))
        sets = []
        for si, (op, t) in enumerate(GLITTER_STEPS):
            begin = starts if si == 0 else f"g{gi}s{si - 1}.end"
            sets.append(f'<set id="g{gi}s{si}" attributeName="opacity" to="{op}" begin="{begin}" dur="{t}s"/>')
        parts.append(
            f'<rect class="g" x="{grid_left + ci * STEP}" y="{grid_top + ri * STEP}" width="{CELL}" '
            f'height="{CELL}" rx="2.5" fill="#6ee07f" opacity="0">{"".join(sets)}</rect>'
        )

    # legend: Less [][][][][] More (bottom-right of the grid)
    leg_y = grid_top + art_h + 6
    leg_x = canvas_w - PAD - (len(PALETTE) * (CELL - 1) + 70)
    parts.append(f'<text x="{leg_x}" y="{leg_y + CELL*0.8:.1f}" fill="{MUTED}" font-size="10" text-anchor="end">Less</text>')
    lx = leg_x + 8
    for lvl, color in enumerate(PALETTE):
        parts.append(f'<rect x="{lx}" y="{leg_y}" width="{CELL-1}" height="{CELL-1}" rx="2.2" fill="{color}"/>')
        lx += CELL
    parts.append(f'<text x="{lx + 4}" y="{leg_y + CELL*0.8:.1f}" fill="{MUTED}" font-size="10">More</text>')

    sep_y = leg_y + CELL + 14
    parts.append(f'<line x1="0" y1="{sep_y}" x2="{canvas_w}" y2="{sep_y}" stroke="{FRAME}" stroke-opacity="0.25"/>')

    cs = data["current_streak"]["length"]
    ls = data["longest_streak"]["length"]
    total = data["total_contributions"]
    best = data["best_day"]
    rng = data["range"]

    ly = sep_y + 24
    # left column: big highlighted numbers; right column: context in muted
    parts.append(f'<text x="{PAD}" y="{ly}" font-size="13" fill="{GREEN}">'
                 f'<tspan font-weight="700">{total:,}</tspan>'
                 f'<tspan fill="{MUTED}"> contributions in the last year</tspan></text>')
    parts.append(f'<text x="{canvas_w - PAD}" y="{ly}" font-size="12" fill="{MUTED}" text-anchor="end">'
                 f'{rng["start"]} &#8594; {rng["end"]}</text>')
    ly += 24
    parts.append(f'<text x="{PAD}" y="{ly}" font-size="13" fill="{MUTED}">current streak '
                 f'<tspan fill="{ACCENT}" font-weight="700">{cs} day{"s" if cs != 1 else ""}</tspan>'
                 f'<tspan fill="{MUTED}">   &#183;   longest </tspan>'
                 f'<tspan fill="{ACCENT}" font-weight="700">{ls} day{"s" if ls != 1 else ""}</tspan></text>')
    parts.append(f'<text x="{canvas_w - PAD}" y="{ly}" font-size="12" fill="{MUTED}" text-anchor="end">'
                 f'best day <tspan fill="{GOLD}" font-weight="700">{best["count"]}</tspan> on {best["date"]}</text>')

    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    data = json.load(open(IN_PATH))
    svg = render(data)
    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"wrote {OUT_PATH} ({len(svg)} bytes)")
