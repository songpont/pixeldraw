"""Paper maps (A1 landscape, 1:10,000) for the workshop.

output/map-1-base.pdf   แผนที่ฐาน – no hazard layers; groups draw their own risk areas on it
output/map-2-risk.pdf   แผนที่ความเสี่ยง – facilitator's answer key with all hazard layers
(+ PNG previews). Usage: python3 scripts/make_maps.py <3D-page-url>
"""
import json, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm, patheffects as pe
from matplotlib.patches import Rectangle, FancyArrow, Patch
from matplotlib.lines import Line2D
from PIL import Image
from scipy import ndimage
import qrcode

FONT_DIR = sys.argv[2] if len(sys.argv) > 2 else "fonts"
for f in ("Sarabun-Regular", "Sarabun-SemiBold", "Sarabun-Bold"):
    fm.fontManager.addfont(f"{FONT_DIR}/{f}.ttf")
plt.rcParams.update({"font.family": "Sarabun", "pdf.fonttype": 42})
URL = sys.argv[1]

T = np.load("data/terrain.npz"); V = json.load(open("data/village.json")); S = json.load(open("data/story.json"))
dem, hand, pond, ls, acc = T["dem"], T["hand"], T["pond"], T["landslide"], T["acc_km2"]
flash = np.load("data/flash.npy")
CELL = V["meta"]["cell_m"]; LV = V["levels"]
X0, X1, Y0, Y1 = 128, 383, 150, 383          # map window in DEM px
base = np.asarray(Image.open("data/base.png")).astype(float) / 255
SCALE = 10000
mm = lambda px: px * CELL / SCALE * 1000         # DEM px → mm on paper
MAPW, MAPH = mm(X1 - X0), mm(Y1 - Y0)
PAGE = (841, 594)
inch = lambda v: v / 25.4

KIND = {"hospital": ("รพ.สต.", "#c92a2a", "P"), "school": ("ร.ร.", "#1971c2", "s"), "childcare": ("ศพด.", "#e8590c", "s"),
        "temple": ("วัด", "#b8860b", "^"), "office": ("อบต.", "#5f3dc4", "p"), "mosque": ("มัสยิด", "#0b7285", "^"),
        "water": ("ประปา", "#1098ad", "o"), "market": ("ตลาด", "#868e96", "s"), "gauge": ("วัดน้ำ", "#2b8a3e", "v")}
halo = [pe.withStroke(linewidth=2.2, foreground="white")]
VUL = lambda h: h.get("bedridden") or h.get("dialysis") or h.get("pregnant") or h.get("psych") or "ออกซิเจน" in h.get("story", "")


def draw(kind):
    fig = plt.figure(figsize=(inch(PAGE[0]), inch(PAGE[1])))
    L, B = 18, (PAGE[1] - MAPH) / 2
    ax = fig.add_axes([L / PAGE[0], B / PAGE[1], MAPW / PAGE[0], MAPH / PAGE[1]])
    ext = (-.5, dem.shape[1] - .5, dem.shape[0] - .5, -.5)
    img = base * 0.62 + 0.38 if kind == "risk" else base * 0.45 + 0.55      # base map lighter so groups can draw on it
    ax.imshow(img, extent=ext, interpolation="bilinear")
    # contours: 10 m, index every 50 m
    yy, xx = np.mgrid[0:dem.shape[0], 0:dem.shape[1]]
    lv = np.arange(30, 900, 10)
    ax.contour(xx, yy, ndimage.gaussian_filter(dem, 1), levels=lv, colors="#7a5a3a", linewidths=0.25, alpha=.6)
    ci = ax.contour(xx, yy, ndimage.gaussian_filter(dem, 1), levels=np.arange(50, 900, 50), colors="#7a5a3a", linewidths=0.6, alpha=.8)
    ax.clabel(ci, fmt="%d ม.", fontsize=6, inline_spacing=2)
    if kind == "risk":
        hs_ = ndimage.gaussian_filter(np.nan_to_num(hand, nan=99), .9)
        for lvv, c in ((LV["extreme"], "#a7c9ef"), (LV["heavy"], "#4f8fd6"), (LV["yearly"], "#1e4f9c")):
            ax.contourf(xx, yy, hs_, levels=[-1, lvv], colors=[c], alpha=.55)
        ax.contourf(xx, yy, ndimage.gaussian_filter(ls, .6), levels=[.6, 2], colors=["#c62828"], alpha=.38)
        pm = ndimage.gaussian_filter(pond, .6) > 1.2
        lab, n = ndimage.label(pm); sizes = ndimage.sum(pm, lab, range(1, n + 1))
        pm = np.isin(lab, 1 + np.where(sizes >= 8)[0]).astype(float)
        ax.contourf(xx, yy, pm, levels=[.5, 2], colors="none", hatches=["...."])
        ax.contour(xx, yy, pm, levels=[.5], colors="#8b3fa6", linewidths=.7)
        ax.contourf(xx, yy, ndimage.gaussian_filter(flash.astype(float), .8), levels=[.45, 2], colors=["#f08a24"], alpha=.55)
        for r in V["evac"]:
            p = np.array(r["pts"]); ax.plot(p[:, 0], p[:, 1], color="#2f9e44", lw=2.2, ls=(0, (4, 2)), zorder=6)
            ax.annotate("", xy=p[-1], xytext=p[-4], arrowprops=dict(arrowstyle="-|>", color="#2f9e44", lw=2), zorder=6)
    # streams
    from matplotlib.collections import LineCollection
    fd = T["fd"]; nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    segs, ws = [], []
    for yv, xv in zip(*np.where(acc > 0.4)):
        i = fd[yv, xv]
        if i >= 0:
            segs.append([(xv, yv), (xv + nb[i][1], yv + nb[i][0])]); ws.append(0.8 + 1.1 * np.log10(acc[yv, xv] / 0.4 + 1) ** 1.3)
    ax.add_collection(LineCollection(segs, linewidths=ws, colors="#2f6fa8", capstyle="round", joinstyle="round", zorder=4))
    # roads
    for r in V["roads"]:
        p = np.array(r["pts"]); w = 3.4 if r["kind"] == "main" else 2.4
        ax.plot(p[:, 0], p[:, 1], color="#5a4a3a", lw=w + 1.2, solid_capstyle="round", zorder=5)
        ax.plot(p[:, 0], p[:, 1], color="#fff3d6" if r["kind"] == "main" else "white", lw=w, solid_capstyle="round", zorder=5)
    for b in V["bridges"]:
        if X0 <= b["x"] <= X1 and Y0 <= b["y"] <= Y1:
            risky = flash[max(0, b["y"] - 3):b["y"] + 4, max(0, b["x"] - 3):b["x"] + 4].any()
            ax.plot(b["x"], b["y"], marker="s", ms=5, mfc="#333" if not (kind == "risk" and risky) else "#c62828", mec="white", mew=.8, zorder=7)
            ax.text(b["x"] + 1.5, b["y"] - 1.5, b["name"], fontsize=5.5, color="#333", path_effects=halo, zorder=8)
    # households
    for h in V["households"]:
        vul = kind == "risk" and VUL(h)
        ax.plot(h["x"], h["y"], marker="s", ms=4.2 if vul else 3.4, mfc="#e8590c" if vul else "#f4ecd8", mec="#3a2a1a", mew=.6, zorder=8)
        if kind == "risk" and h.get("hit"):
            ax.plot(h["x"], h["y"], marker="x", ms=6, mec="#111", mew=1.4, zorder=9)
        ax.text(h["x"] + .9, h["y"] + .2, h["id"].split("-")[1].lstrip("0"), fontsize=4.2, color="#3a2a1a", path_effects=halo, zorder=9, va="center")
    # facilities
    for f in V["facilities"]:
        t, c, m = KIND[f["kind"]]
        ax.plot(f["x"], f["y"], marker=m, ms=11, mfc=c, mec="white", mew=1.2, zorder=10)
        ax.text(f["x"], f["y"] - 3.2, f["name"].split(" (")[0].split(" / ")[0], fontsize=7.5, weight="bold", color=c, ha="center", path_effects=halo, zorder=11)
    # story people (risk map only)
    if kind == "risk":
        for h in V["households"]:
            if "story" in h:
                ax.annotate(h["story"].split(" ")[0].replace("บ้าน", ""), (h["x"], h["y"]), xytext=(8, 10), textcoords="offset points",
                            fontsize=6.5, color="#7a2e0b", weight="bold", path_effects=halo, zorder=12,
                            arrowprops=dict(arrowstyle="-", color="#7a2e0b", lw=.6))
    # village names
    for v in V["villages"]:
        hs = [h for h in V["households"] if h["moo"] == v["moo"]]
        cx, cy = np.mean([h["x"] for h in hs]), np.mean([h["y"] for h in hs])
        off = {1: (0, -12), 2: (0, -10), 3: (-16, 0), 4: (8, 14)}[v["moo"]]
        ax.text(cx + off[0], cy + off[1], f"หมู่ {v['moo']}\n{v['name']}", fontsize=13, weight="bold", ha="center", va="center",
                color="#1d2a24", path_effects=[pe.withStroke(linewidth=3.5, foreground="white")], zorder=12)
    ax.text(268, 205, "คลองฮอนกฮูก", fontsize=9, style="italic", color="#2f6fa8", rotation=-8, path_effects=halo, zorder=7)
    ax.text(150, 180, "เทือกเขาหลวง", fontsize=12, color="#2d4a2d", alpha=.8, path_effects=halo)
    ax.text(205, 330, "ควนนกฮูก", fontsize=10, color="#2d4a2d", path_effects=halo)
    # grid 500 m: columns A.., rows 1..
    step = 500 / CELL
    xs = np.arange(X0, X1, step); ys = np.arange(Y0, Y1, step)
    for i, x in enumerate(xs):
        ax.axvline(x, color="#222", lw=.35, alpha=.5)
        ax.text(x + step / 2, Y0 - 1.2, "ABCDEFGHIJKLMN"[i], ha="center", va="bottom", fontsize=10, weight="bold", clip_on=False)
        ax.text(x + step / 2, Y1 + 1.2, "ABCDEFGHIJKLMN"[i], ha="center", va="top", fontsize=10, weight="bold", clip_on=False)
    for j, y in enumerate(ys):
        ax.axhline(y, color="#222", lw=.35, alpha=.5)
        ax.text(X0 - 1.2, y + step / 2, str(j + 1), ha="right", va="center", fontsize=10, weight="bold", clip_on=False)
        ax.text(X1 + 1.2, y + step / 2, str(j + 1), ha="left", va="center", fontsize=10, weight="bold", clip_on=False)
    ax.set_xlim(X0, X1); ax.set_ylim(Y1, Y0); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_linewidth(1.5)

    # ---------------- side panel
    px = (L + MAPW + 22) / PAGE[0]
    fig.text(px, .93, "ตำบลฮอนกฮูก", fontsize=40, weight="bold", color="#1d2a24")
    fig.text(px, .895, "แผนที่ฐานสำหรับระดมความคิด" if kind == "base" else "แผนที่ความเสี่ยงภัย (ฉบับวิทยากร)", fontsize=20, weight="bold",
             color="#1f6f8b" if kind == "base" else "#b42318")
    fig.text(px, .872, "ชุมชนจำลองเพื่อการอบรมแผนรับมือภัยพิบัติ · ภูมิประเทศจริง เทือกเขาหลวงด้านตะวันออก จ.นครศรีธรรมราช", fontsize=9, color="#444")
    y = .835
    def sec(t):
        nonlocal y
        fig.text(px, y, t, fontsize=12, weight="bold"); y -= .022
    def row(handle, t):
        nonlocal y
        lax = fig.add_axes([px, y - .006, .022, .016]); lax.set_xlim(0, 1); lax.set_ylim(0, 1); lax.axis("off"); handle(lax)
        fig.text(px + .028, y - .002, t, fontsize=9, va="center"); y -= .021
    sec("สัญลักษณ์")
    for k, (t, c, m) in KIND.items():
        name = next(f["name"] for f in V["facilities"] if f["kind"] == k)
        row(lambda a, c=c, m=m: a.plot(.5, .5, marker=m, ms=9, mfc=c, mec="white"), name)
    row(lambda a: a.plot(.5, .5, marker="s", ms=5, mfc="#f4ecd8", mec="#3a2a1a"), "ครัวเรือน (ตัวเลข = ลำดับบ้านในทะเบียน)")
    row(lambda a: (a.plot([0, 1], [.5, .5], color="#5a4a3a", lw=5), a.plot([0, 1], [.5, .5], color="#fff3d6", lw=3.5)), "ถนนสายหลัก / ถนนในหมู่บ้าน")
    row(lambda a: a.plot([0, 1], [.5, .5], color="#2f6fa8", lw=2), "คลองและลำห้วย")
    row(lambda a: a.plot(.5, .5, marker="s", ms=5, mfc="#333", mec="white"), "สะพาน")
    row(lambda a: a.plot([0, 1], [.3, .7], color="#7a5a3a", lw=.8), "เส้นชั้นความสูง ทุก 10 ม. (เส้นหนาทุก 50 ม.)")
    if kind == "risk":
        y -= .006; sec("ความเสี่ยงภัย")
        for c, t in (("#1e4f9c", f"น้ำท่วมเกือบทุกปี (สูงจากคลองไม่เกิน {LV['yearly']} ม.)"), ("#4f8fd6", f"น้ำท่วมในปีน้ำมาก (ไม่เกิน {LV['heavy']:.0f} ม.)"),
                     ("#a7c9ef", f"น้ำท่วมในปีวิกฤต (ไม่เกิน {LV['extreme']:.0f} ม.)"), ("#f08a24", "เส้นทางน้ำป่าไหลหลาก"), ("#c62828", "ลาดชันเสี่ยงดินถล่ม")):
            row(lambda a, c=c: a.add_patch(Rectangle((0, .1), 1, .8, color=c, alpha=.7)), t)
        row(lambda a: (a.add_patch(Rectangle((0, .1), 1, .8, fill=False, hatch="....", ec="#8b3fa6"))), "แอ่งน้ำขังนานหลังน้ำลด")
        row(lambda a: a.plot(.5, .5, marker="s", ms=6, mfc="#e8590c", mec="#3a2a1a"), "ครัวเรือนกลุ่มเปราะบาง (ติดเตียง ฟอกไต ตั้งครรภ์ ฯลฯ)")
        row(lambda a: a.plot(.5, .5, marker="x", ms=7, mec="#111", mew=1.5), "บ้านที่ถูกดินถล่มทับในเรื่องเล่า")
        row(lambda a: a.plot(.5, .5, marker="s", ms=5, mfc="#c62828", mec="white"), "สะพานบนเส้นทางน้ำป่า (เสี่ยงขาด)")
        row(lambda a: a.plot([0, 1], [.5, .5], color="#2f9e44", lw=2, ls=(0, (4, 2))), "เส้นทางอพยพไปที่ดอน")
    else:
        y -= .006; sec("กิจกรรมกลุ่ม: ระบายสีลงบนแผนที่")
        for t in ("1. สีน้ำเงิน: บริเวณที่น้ำท่วมทุกปี / ท่วมในปีน้ำมาก",
                  "2. สีส้ม: เส้นทางที่น้ำป่าไหลมาแรงและเร็ว",
                  "3. สีแดง: ลาดชันที่อาจเกิดดินถล่ม",
                  "4. วงกลมสีแดง: บ้านที่มีคนช่วยตัวเองไม่ได้",
                  "5. สีเขียว: จุดปลอดภัยและเส้นทางอพยพ",
                  "6. เขียนชื่อ: ทรัพยากรในชุมชน (เรือ เครื่องปั่นไฟ คนมีทักษะ)"):
            fig.text(px, y, t, fontsize=10); y -= .021
        y -= .004
        fig.text(px, y, "เคล็ดลับ: น้ำไหลจากเส้นชั้นความสูงตัวเลขมากไปตัวเลขน้อย", fontsize=9, color="#555", style="italic"); y -= .02
    # scale bar + north arrow
    sx = px; sy = .135
    sb = fig.add_axes([sx, sy, 100 / PAGE[0], .03]); sb.axis("off")
    sb.set_xlim(0, 1000); sb.set_ylim(0, 1)
    for i in range(4):
        sb.add_patch(Rectangle((i * 250, .45), 250, .25, color="#222" if i % 2 == 0 else "white", ec="#222"))
    for v in (0, 500, 1000):
        sb.text(v, .05, f"{v} ม.", ha="center", fontsize=8)
    fig.text(sx, sy + .038, f"มาตราส่วน 1 : {SCALE:,} (เมื่อพิมพ์ขนาด A1)  ·  ตารางกริด 500 × 500 ม.", fontsize=9)
    na = fig.add_axes([px + .17, .13, .03, .06]); na.axis("off"); na.set_xlim(-1, 1); na.set_ylim(-1, 1.6)
    na.add_patch(FancyArrow(0, -.8, 0, 1.6, width=.35, head_width=1, head_length=.7, color="#222")); na.text(0, 1.45, "N", ha="center", fontsize=14, weight="bold")
    # QR
    q = qrcode.QRCode(border=1, box_size=10); q.add_data(URL); q.make()
    qa = fig.add_axes([PAGE[0] - 18 - 62, 14, 62, 62] / np.array([PAGE[0], PAGE[1], PAGE[0], PAGE[1]]))
    qa.imshow(np.array(q.make_image(fill_color="black", back_color="white").convert("L")), cmap="gray"); qa.axis("off")
    fig.text((PAGE[0] - 18 - 66) / PAGE[0], (14 + 31) / PAGE[1], "สแกนเพื่อดู\nแผนที่ 3 มิติ\nและเรื่องเล่า\nในโทรศัพท์", fontsize=10, ha="right", va="center", weight="bold")
    fig.text(px, .045, "ข้อมูลความสูง: SRTM ผ่าน AWS Terrain Tiles · ชุมชน ผู้คน และเหตุการณ์เป็นเรื่องสมมติ\n"
             "พื้นที่เสี่ยงคำนวณอย่างง่ายจากความสูงเหนือทางน้ำ ความชัน และพื้นที่รับน้ำ ใช้เพื่อการเรียนรู้ ไม่ใช่การพยากรณ์จริง", fontsize=7.5, color="#555")
    return fig


for kind, name in (("base", "map-1-base"), ("risk", "map-2-risk")):
    fig = draw(kind)
    fig.savefig(f"output/{name}-A1.pdf")
    fig.savefig(f"output/{name}-preview.png", dpi=60)
    plt.close(fig)
print("maps ok", MAPW, MAPH)
