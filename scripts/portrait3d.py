"""
Pseudo-3D for the ascii portrait. The photo has no depth, so the cut-out
silhouette (source-mask.png, written by prep_photo.py) is "inflated" into a
height field: a rounded rim (steep at the outline, flat inside) plus a broad
dome, so the head and shoulders read as solid forms when turned a few degrees.

Used by make_ascii_svg.py (pre-rendered turning frames for the README) and
export_portrait_web.py (data for the interactive page in docs/).
"""
import math
import os

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PREPPED = os.path.join(HERE, "..", "source-prepped.png")
MASK = os.path.join(HERE, "..", "source-mask.png")

RIM = 0.10       # rim rounding width, as a fraction of the image side
DOME = 0.55      # weight of the broad dome vs the rim profile
DEPTH = 0.30     # total relief, as a fraction of the image side


def load(size, prepped=PREPPED, mask=MASK):
    """(gray, mask) as float32 0..1 arrays, size x size. gray is white-backed."""
    g = Image.open(prepped).convert("L").resize((size, size), Image.LANCZOS)
    m = Image.open(mask).convert("L").resize((size, size), Image.BILINEAR)
    return np.asarray(g, np.float32) / 255.0, np.asarray(m, np.float32) / 255.0


def depth(mask):
    """Height field 0..1 (1 = nearest the viewer) inflated from the silhouette."""
    size = mask.shape[0]
    dt = cv2.distanceTransform((mask > 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    rim = np.clip(dt / (RIM * size), 0, 1)
    rim = np.sqrt(1 - (1 - rim) ** 2)                      # quarter-circle edge
    dome = np.sqrt(dt / max(dt.max(), 1))
    z = (1 - DOME) * rim + DOME * dome
    return cv2.GaussianBlur(z, (0, 0), size * 0.012)


def project(gray, mask, z, yaw):
    """Render the height field turned `yaw` radians about the vertical axis
    (orthographic, z-buffered). Returns a white-backed gray image, same size."""
    size = gray.shape[0]
    c = (size - 1) / 2
    ys, xs = np.nonzero(mask > 0.02)
    X = xs - c
    Z = (z[ys, xs] - 0.5) * DEPTH * size
    ca, sa = math.cos(yaw), math.sin(yaw)
    xr = X * ca + Z * sa
    zr = -X * sa + Z * ca
    px = np.rint(xr + c).astype(np.int32)
    order = np.argsort(zr)                                  # far -> near, near wins
    px, py, src = px[order], ys[order], (ys[order], xs[order])
    out = np.ones_like(gray)
    for dx in (1, 0):                                       # +1 splat closes stretch gaps
        q = np.clip(px + dx, 0, size - 1)
        out[py, q] = gray[src]
    return out
