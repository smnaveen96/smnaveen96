"""
Prepare the dp (a real photo, cut out sticker-style with a yellow outline on a
flat blue backdrop) for clean ASCII conversion:
  1. isolate the subject: key out the saturated blue backdrop and the yellow
     outline, keep the largest remaining region
  2. CLAHE local contrast so the face reads against the hair/beard, plus a light
     bilateral pass so shirt stripes and skin texture don't turn into noise
  3. stretch tones so skin lands near white and hair/beard stay dark
  4. gently darken edges (difference-of-gaussians) -- eye, nose and mouth lines
     wash out at ascii resolution otherwise
  5. fade the shirt out toward the bottom, composite onto white, crop square

Output: source-prepped.png (grayscale), consumed by make_ascii_svg.py.

    python scripts/prep_photo.py <input.png> [output.png]
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-photo.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

LINE_WEIGHT = 0.45    # how hard edges are pushed toward black
FADE_FROM = 0.80      # start fading the shirt out at this fraction of the height

# 1. cut out the subject
rgb = np.array(Image.open(INP).convert("RGB"))
hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
h, w = rgb.shape[:2]
yellow = cv2.inRange(hsv, (15, 70, 120), (40, 255, 255))
yellow = cv2.dilate(yellow, np.ones((5, 5), np.uint8))

backdrop = cv2.inRange(hsv, (100, 170, 20), (130, 255, 255))     # saturated blue; the shirt is greyish
keep = ((backdrop == 0) & (yellow == 0)).astype(np.uint8)
n, regions, stats, _ = cv2.connectedComponentsWithStats(keep, connectivity=4)
biggest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
alpha = np.where(regions == biggest, 255, 0).astype(np.uint8)
alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

# 2. local contrast + smooth texture, keep edges
gray = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(6, 6)).apply(gray)
smooth = gray
for _ in range(4):
    smooth = cv2.bilateralFilter(smooth, 11, 30, 11)

# 3. tone stretch over the subject only
lo, hi = np.percentile(smooth[alpha > 128], [4, 97])
tone = np.clip((smooth.astype(np.float32) - lo) / (hi - lo), 0, 1)

# 4. dark-on-light ridges -> darken
fine = cv2.GaussianBlur(smooth, (0, 0), 1.5).astype(np.float32)
coarse = cv2.GaussianBlur(smooth, (0, 0), 6).astype(np.float32)
lines = np.clip((coarse - fine) / 40.0, 0, 1)
out = np.clip(tone - LINE_WEIGHT * lines, 0, 1)

# the striped shirt (blue-grey, unlike skin/hair) becomes a soft, light,
# low-contrast silhouette so it doesn't fight the face for attention
shirt = cv2.inRange(hsv, (100, 40, 90), (130, 255, 255))         # hair is the same hue but darker
shirt[: int(h * 0.5)] = 0
shirt = cv2.morphologyEx(shirt, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
shirt = cv2.morphologyEx(shirt, cv2.MORPH_CLOSE, np.ones((71, 71), np.uint8))
shirt = cv2.GaussianBlur(shirt.astype(np.float32) / 255.0, (0, 0), 6) * (alpha / 255.0)
soft = cv2.GaussianBlur(out, (0, 0), 5)
out = (out * (1 - shirt) + (0.50 + 0.35 * soft) * shirt) * 255

# 5. fade the bottom, paste onto white (feathered to avoid a halo), square crop
mask = cv2.GaussianBlur(alpha.astype(np.float32) / 255.0, (0, 0), 1.5)
ramp = np.clip((np.arange(h) / h - FADE_FROM) / (1 - FADE_FROM), 0, 1)[:, None]
mask = mask * (1 - ramp ** 1.5)
out = out * mask + 255.0 * (1.0 - mask)

ys, xs = np.where(alpha > 20)
side = max(xs.max() - xs.min(), ys.max() - ys.min()) + 60
cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
canvas = np.full((side, side), 255, np.uint8)
x0, y0 = cx - side // 2, cy - side // 2
sx0, sy0 = max(x0, 0), max(y0, 0)
sx1, sy1 = min(x0 + side, out.shape[1]), min(y0 + side, out.shape[0])
canvas[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = out[sy0:sy1, sx0:sx1].astype(np.uint8)
# the cut-out silhouette on the same crop -- portrait3d.py inflates it into depth
silhouette = np.zeros((side, side), np.uint8)
silhouette[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = alpha[sy0:sy1, sx0:sx1]

Image.fromarray(canvas).save(OUT)
MASK_OUT = os.path.join(os.path.dirname(OUT), "source-mask.png")
Image.fromarray(silhouette).save(MASK_OUT)
print("wrote", OUT, "and", MASK_OUT, canvas.shape)
