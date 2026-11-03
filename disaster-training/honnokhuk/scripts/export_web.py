"""Bundle terrain + village + story into one self-contained HTML page (web/honnokhuk-3d.html)."""
import base64, json
import numpy as np
T = np.load("data/terrain.npz"); V = json.load(open("data/village.json")); S = json.load(open("data/story.json"))
dem, hand = T["dem"], T["hand"]
b64 = lambda b: base64.b64encode(b).decode()
uri = lambda p, m: f"data:{m};base64," + b64(open(p, "rb").read())
keep = ("id no moo x y members elderly under5 bedridden disabled pregnant ncd dialysis psych house water job livestock "
        "hand elev flood flash landslide pond story hit").split()
V2 = {"levels": V["levels"], "villages": [{k: v[k] for k in ("moo", "name", "desc")} for v in V["villages"]],
      "facilities": V["facilities"], "bridges": V["bridges"], "evac": V["evac"],
      "households": [{k: h[k] for k in keep if k in h} for h in V["households"]]}
data = {"n": int(dem.shape[0]), "cell": V["meta"]["cell_m"], "zmin": float(dem.min()),
        "elev": b64(np.round(dem * 10).astype("<u2").tobytes()),
        "hand": b64(np.clip(np.round(np.nan_to_num(hand, nan=12.7) * 20), 0, 255).astype(np.uint8).tobytes()),
        "base": uri("data/base_web.jpg", "image/jpeg"), "haz": uri("data/hazard.png", "image/png"),
        "village": V2, "story": S}
html = open("web/template.html").read().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
# artifact build: the publisher adds the document skeleton
open("web/artifact.html", "w").write(html)
# standalone build: open directly in any browser / host anywhere
open("web/honnokhuk-3d.html", "w").write('<!doctype html><html lang="th"><head><meta charset="utf-8">'
  '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body style="margin:0">' + html + "</body></html>")
print(len(html) // 1024, "KB")
