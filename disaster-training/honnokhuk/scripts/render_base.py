"""Render the shared base-map raster (land use + hillshade) and the hazard-overlay data image.

data/base.png        land use × hillshade, 4 px per DEM cell (no roads) – used by paper maps
data/base_web.jpg    same + roads + streams drawn in – used as the 3D drape
data/hazard.png      R = landslide susceptibility, G = flash-flood corridor, B = ponding depth (data, not colours)
"""
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

S = 4
T = np.load("data/terrain.npz")
V = json.load(open("data/village.json"))
dem, slope, hand, acc, pond, ls = (T[k] for k in ("dem", "slope", "hand", "acc_km2", "pond", "landslide"))
N = dem.shape[0]
up = lambda a, o=1: ndimage.zoom(a, S, order=o)
D = up(dem, 3); SL = up(slope); H = up(hand); A = up(np.log10(acc + 1e-3)); P = up(pond)
cell = 18.9 / S
gy, gx = np.gradient(D, cell)
az, alt = np.radians(315), np.radians(40)
hs = np.sin(alt) / np.sqrt(1 + gx**2 + gy**2) + np.cos(alt) * (-gx * np.sin(az) + gy * np.cos(az)) / np.sqrt(1 + gx**2 + gy**2) * -1
hs = np.clip(hs, 0, 1)
hs = 0.55 + 0.6 * (hs - hs.mean())

rng = np.random.default_rng(7)
noise = ndimage.gaussian_filter(rng.standard_normal(D.shape), 3) * 0.08
yy, xx = np.mgrid[0:N * S, 0:N * S]

col = np.zeros(D.shape + (3,))
forest = (D > 260) | (SL > 32)
rubber = ~forest & (SL > 7)
paddy = ~forest & ~rubber & (H < 4.5)
garden = ~forest & ~rubber & ~paddy
col[forest] = (0.20, 0.38, 0.22)
col[rubber] = (0.38, 0.55, 0.30)
# rubber rows: subtle stripes
rows = ((xx + yy) % 10 < 3)
col[rubber & rows] *= 0.9
col[paddy] = (0.72, 0.80, 0.50)
bund = ((xx % 36) < 1) | ((yy % 28) < 1)
col[paddy & bund] = (0.60, 0.66, 0.42)
col[garden] = (0.52, 0.64, 0.38)
col *= (1 + noise)[..., None]
# settlements: tan patches around houses
settle = np.zeros((N, N), bool)
for h in V["households"]:
    settle[h["y"], h["x"]] = True
for f in V["facilities"]:
    settle[f["y"], f["x"]] = True
settle = up(ndimage.binary_dilation(settle, iterations=2).astype(float), 1) > 0.5
col[settle] = col[settle] * 0.25 + np.array((0.86, 0.80, 0.64)) * 0.75
# streams
stream_w = np.clip((A - np.log10(0.4)) / 1.2, 0, 1)
sm = lambda m, s: ndimage.gaussian_filter(m.astype(float), s) > 0.3
water = sm(up((acc > 0.4).astype(float), 1) > 0.5, 2.2) | sm(up((acc > 4).astype(float), 1) > 0.5, 4)
col[water] = (0.32, 0.55, 0.75)
rgb = np.clip(col * hs[..., None], 0, 1)
Image.fromarray((rgb * 255).astype(np.uint8)).save("data/base.png", optimize=True)

# web drape: add roads
img = Image.fromarray((rgb * 255).astype(np.uint8))
dr = ImageDraw.Draw(img)
for r in V["roads"]:
    pts = [(x * S + S / 2, y * S + S / 2) for x, y in r["pts"]]
    w = 9 if r["kind"] == "main" else 6
    dr.line(pts, fill=(90, 80, 70), width=w + 3, joint="curve")
    dr.line(pts, fill=(238, 228, 205) if r["kind"] == "main" else (225, 215, 190), width=w, joint="curve")
img = img.resize((1536, 1536), Image.LANCZOS)
img.save("data/base_web.jpg", quality=82, optimize=True)

# hazard data image at 2 px per cell
h2 = lambda a: ndimage.zoom(a, 2, order=1)
fl = np.load("data/flash.npy").astype(float)
haz = np.dstack([np.clip(h2(ls), 0, 1) * 255, np.clip(h2(ndimage.gaussian_filter(fl, .7)), 0, 1) * 255,
                 np.clip(h2(pond) / 3, 0, 1) * 255]).astype(np.uint8)
Image.fromarray(haz).save("data/hazard.png", optimize=True)
print("ok")
