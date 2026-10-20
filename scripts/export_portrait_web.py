#!/usr/bin/env python3
"""
Export the portrait (gray + inflated depth, see portrait3d.py) for the
interactive 3D page at docs/index.html, which turns it into ascii live in the
browser as you drag / move the pointer.

    python scripts/export_portrait_web.py [size]
"""
import base64
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portrait3d  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "portrait.json")
SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 220


def b64(a):
    return base64.b64encode(np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8).tobytes()).decode()


gray, mask = portrait3d.load(SIZE)
z = portrait3d.depth(mask)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump({"size": SIZE, "relief": portrait3d.DEPTH,
               "gray": b64(gray), "depth": b64(z), "mask": b64(mask)}, f)
print("wrote", OUT, os.path.getsize(OUT), "bytes")
