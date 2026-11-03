"""Terrain analysis for the fictional Honnokhuk subdistrict.
Input: real DEM (AWS Terrain Tiles / terrarium, z13, Khao Luang east slope, Nakhon Si Thammarat).
Outputs (data/): dem.npy, filled, slope, flow accumulation, HAND, ponding depth, landslide score."""
import numpy as np, heapq, sys, json
from scipy import ndimage
src, out = sys.argv[1], sys.argv[2]
full = np.load(src)
Y0, X0, N = 330, 200, 384           # crop window in the z13 mosaic (tiles x6365-6368, y3902-3905)
dem = full[Y0:Y0+N, X0:X0+N].astype(np.float64)
dem = ndimage.gaussian_filter(dem, 0.8)
CELL = 156543.03392 * np.cos(np.radians(8.43)) / 2**13   # metres per pixel ≈ 18.9
# slope
gy, gx = np.gradient(dem, CELL); slope = np.degrees(np.arctan(np.hypot(gx, gy)))
# priority-flood depression filling (+epsilon so flats drain)
H, W = dem.shape; filled = np.full_like(dem, np.inf); done = np.zeros(dem.shape, bool); pq = []
for y in range(H):
    for x in range(W):
        if y in (0, H-1) or x in (0, W-1):
            filled[y, x] = dem[y, x]; done[y, x] = True; heapq.heappush(pq, (dem[y, x], y, x))
nb = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
while pq:
    z, y, x = heapq.heappop(pq)
    for dy, dx in nb:
        yy, xx = y+dy, x+dx
        if 0 <= yy < H and 0 <= xx < W and not done[yy, xx]:
            done[yy, xx] = True; filled[yy, xx] = max(dem[yy, xx], z + 1e-4)
            heapq.heappush(pq, (filled[yy, xx], yy, xx))
pond = filled - dem
# D8 flow direction
fd = np.full((H, W), -1, int)
for y in range(H):
    for x in range(W):
        best, bi = 0, -1
        for i, (dy, dx) in enumerate(nb):
            yy, xx = y+dy, x+dx
            if 0 <= yy < H and 0 <= xx < W:
                s = (filled[y, x] - filled[yy, xx]) / (1.414 if dy and dx else 1)
                if s > best: best, bi = s, i
        fd[y, x] = bi
# accumulation (process high → low)
acc = np.ones((H, W)); order = np.argsort(-filled, axis=None)
for k in order:
    y, x = divmod(k, W); i = fd[y, x]
    if i >= 0: acc[y+nb[i][0], x+nb[i][1]] += acc[y, x]
area_km2 = acc * CELL**2 / 1e6
stream = area_km2 > 0.4
# HAND: height above nearest drainage along flow path
hand = np.full((H, W), np.nan)
def drain_elev(y, x):
    path = []
    while not stream[y, x] and fd[y, x] >= 0 and np.isnan(hand[y, x]):
        path.append((y, x)); y, x = y+nb[fd[y, x]][0], x+nb[fd[y, x]][1]
    base = filled[y, x] - (0 if stream[y, x] or fd[y, x] < 0 else hand[y, x])
    if stream[y, x]: hand[y, x] = 0
    for (py, px) in path: hand[py, px] = filled[py, px] - base
for y in range(H):
    for x in range(W):
        if np.isnan(hand[y, x]): drain_elev(y, x)
hand = np.clip(hand, 0, None)
# landslide susceptibility 0..1: slope (dominant) + convergence (hollows) + soil-on-granite steep zone
curv = ndimage.laplace(ndimage.gaussian_filter(dem, 2))   # >0 = concave (hollow)
s = np.clip((slope - 15) / 20, 0, 1)
c = np.clip(curv / 2.0, 0, 1)
ls = np.clip(0.75 * s + 0.25 * c * (slope > 15), 0, 1)
np.savez_compressed(f"{out}/terrain.npz", dem=dem, filled=filled, slope=slope, acc_km2=area_km2,
                    hand=hand, pond=pond, landslide=ls, fd=fd)
json.dump({"cell_m": CELL, "size": N, "crop": [Y0, X0], "zmin": float(dem.min()), "zmax": float(dem.max()),
           "source": "AWS Terrain Tiles (terrarium, z13: x6365-6368, y3902-3905) — SRTM-derived",
           "area": "เทือกเขาหลวงด้านตะวันออก จ.นครศรีธรรมราช (ภูมิประเทศจริง, ชุมชนสมมติ)"},
          open(f"{out}/meta.json", "w"), ensure_ascii=False, indent=1)
print("done", dem.min(), dem.max(), CELL, stream.sum(), (pond > 0.5).sum())
