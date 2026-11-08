"""A4 case book for participants (works without internet): community plan, 3D views of every stage and the full narrative.

Needs the stage images from scripts/render_views.js in output/views/.
Logo: put the official logo at assets/logo-nhco.png (or .svg / .jpg); a labelled empty box is printed until then.
Credits: edit data/credits.json.
Usage: python3 scripts/make_casebook.py <online-map-url>   → output/casebook-A4.pdf
"""
import base64, html, io, json, os, subprocess, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm, patheffects as pe
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle, FancyArrow
from PIL import Image
from scipy import ndimage
import qrcode

URL = sys.argv[1]
e = html.escape
for f in ("Sarabun-Regular", "Sarabun-SemiBold", "Sarabun-Bold"):
    fm.fontManager.addfont(f"fonts/{f}.ttf")
plt.rcParams.update({"font.family": "Sarabun"})
V = json.load(open("data/village.json")); S = json.load(open("data/story.json"))
CR = json.load(open("data/credits.json"))
HH = V["households"]; LV = V["levels"]
T = np.load("data/terrain.npz"); dem, acc = T["dem"], T["acc_km2"]
CELL = V["meta"]["cell_m"]
X0, X1, Y0, Y1 = 128, 383, 165, 370
VIEWS = "output/views"

def uri(path, mime=None):
    mime = mime or {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}[path.rsplit(".", 1)[1].lower()]
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()

def fig_uri(fig, dpi=220):
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=dpi); plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()

# ---------------------------------------------------------------- 2D community plan
KIND = {"hospital": ("#c92a2a", "P"), "school": ("#1971c2", "s"), "childcare": ("#e8590c", "s"), "temple": ("#b8860b", "^"),
        "office": ("#5f3dc4", "p"), "mosque": ("#0b7285", "^"), "water": ("#1098ad", "o"), "market": ("#868e96", "s"), "gauge": ("#2b8a3e", "v")}
VUL = lambda h: h.get("bedridden") or h.get("dialysis") or h.get("pregnant") or h.get("psych") or "ออกซิเจน" in h.get("story", "")

def plan():
    w_mm = 182; h_mm = w_mm * (Y1 - Y0) / (X1 - X0)
    fig = plt.figure(figsize=(w_mm / 25.4, h_mm / 25.4)); ax = fig.add_axes([0, 0, 1, 1])
    base = np.asarray(Image.open("data/base.png")).astype(float) / 255
    ax.imshow(base * .5 + .5, extent=(-.5, dem.shape[1] - .5, dem.shape[0] - .5, -.5), interpolation="bilinear")
    yy, xx = np.mgrid[0:dem.shape[0], 0:dem.shape[1]]
    ci = ax.contour(xx, yy, ndimage.gaussian_filter(dem, 1.2), levels=np.arange(50, 900, 50), colors="#8a6a4a", linewidths=.5, alpha=.7)
    ax.clabel(ci, fmt="%d ม.", fontsize=5)
    fd = T["fd"]; nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    segs, ws = [], []
    for yv, xv in zip(*np.where(acc > 0.4)):
        i = fd[yv, xv]
        if i >= 0:
            segs.append([(xv, yv), (xv + nb[i][1], yv + nb[i][0])]); ws.append(.6 + .9 * np.log10(acc[yv, xv] / .4 + 1) ** 1.3)
    ax.add_collection(LineCollection(segs, linewidths=ws, colors="#2f6fa8", capstyle="round"))
    for r in V["roads"]:
        p = np.array(r["pts"]); w = 2.6 if r["kind"] == "main" else 1.8
        ax.plot(p[:, 0], p[:, 1], color="#5a4a3a", lw=w + 1, solid_capstyle="round"); ax.plot(p[:, 0], p[:, 1], color="#fff3d6", lw=w, solid_capstyle="round")
    halo = [pe.withStroke(linewidth=2, foreground="white")]
    for b in V["bridges"]:
        if X0 <= b["x"] <= X1 and Y0 <= b["y"] <= Y1:
            ax.plot(b["x"], b["y"], "s", ms=3.5, mfc="#333", mec="white", mew=.6)
            ax.text(b["x"] + 1.3, b["y"] - 1.3, b["name"], fontsize=4.6, color="#333", path_effects=halo)
    for h in HH:
        ax.plot(h["x"], h["y"], "s", ms=2.6, mfc="#e8590c" if VUL(h) else "#f4ecd8", mec="#3a2a1a", mew=.4)
    for k, f in enumerate(V["facilities"], 1):
        c, m = KIND[f["kind"]]
        ax.plot(f["x"], f["y"], marker=m, ms=8, mfc=c, mec="white", mew=1)
        ax.text(f["x"] + 2.2, f["y"] + 2.4, str(k), fontsize=7, weight="bold", color="white", ha="center", va="center",
                bbox=dict(boxstyle="circle,pad=.18", fc=c, ec="white", lw=.6))
    for h in HH:
        if h.get("story"):
            ax.annotate(h["story"].split(" ")[0].replace("บ้าน", ""), (h["x"], h["y"]), xytext=(6, 7), textcoords="offset points",
                        fontsize=5.5, color="#7a2e0b", weight="bold", path_effects=halo, arrowprops=dict(arrowstyle="-", color="#7a2e0b", lw=.5))
    for v in V["villages"]:
        hs = [h for h in HH if h["moo"] == v["moo"]]
        cx, cy = np.mean([h["x"] for h in hs]), np.mean([h["y"] for h in hs])
        off = {1: (0, -13), 2: (0, -11), 3: (-17, 0), 4: (10, 15)}[v["moo"]]
        ax.text(cx + off[0], cy + off[1], f"หมู่ {v['moo']}\n{v['name']}", fontsize=10, weight="bold", ha="center", va="center",
                path_effects=[pe.withStroke(linewidth=3, foreground="white")])
    ax.text(270, 204, "คลองฮอนกฮูก", fontsize=7.5, style="italic", color="#2f6fa8", rotation=-8, path_effects=halo)
    ax.text(150, 192, "เทือกเขาหลวง", fontsize=10, color="#2d4a2d", path_effects=halo)
    ax.text(203, 330, "ควนนกฮูก", fontsize=8.5, color="#2d4a2d", path_effects=halo)
    # scale bar 1 km + north arrow
    sx, sy = X0 + 6, Y1 - 6; L = 1000 / CELL
    ax.add_patch(Rectangle((sx, sy - 1.6), L / 2, 1.6, fc="#222")); ax.add_patch(Rectangle((sx + L / 2, sy - 1.6), L / 2, 1.6, fc="white", ec="#222", lw=.6))
    for d, t in ((0, "0"), (L / 2, "500"), (L, "1,000 ม.")):
        ax.text(sx + d, sy - 3, t, fontsize=6, ha="center", path_effects=halo)
    ax.add_patch(FancyArrow(X1 - 8, Y1 - 6, 0, -12, width=1.6, head_width=4.5, head_length=4, color="#222"))
    ax.text(X1 - 8, Y1 - 24, "N", ha="center", fontsize=9, weight="bold", path_effects=halo)
    ax.set_xlim(X0, X1); ax.set_ylim(Y1, Y0); ax.axis("off")
    return fig_uri(fig)

# ---------------------------------------------------------------- page pieces
def logo_html(h_mm):
    for ext in ("svg", "png", "jpg"):
        p = f"assets/logo-nhco.{ext}"
        if os.path.exists(p):
            return f'<img class="logo" src="{uri(p)}" alt="โลโก้ สช." style="height:{h_mm}mm">'
    return f'<div class="logo ph" style="height:{h_mm}mm;width:{h_mm * 1.1}mm">โลโก้<br>สช.</div>'

def qr_uri():
    q = qrcode.QRCode(border=1, box_size=8); q.add_data(URL); q.make()
    b = io.BytesIO(); q.make_image().save(b, format="PNG"); return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()

ALERT = ("ดับ", "ขาด", "ตาย", "จมมิด", "แดง", "เจ็บ")
def facts(s):
    return "".join(f'<div class="fact{" alert" if any(a in v for a in ALERT) else ""}"><small>{e(k)}</small><b>{e(v)}</b></div>' for k, v in s["facts"].items())

CSS = """
@font-face{font-family:Sarabun;src:url(file://FONT/Sarabun-Regular.ttf);font-weight:400}
@font-face{font-family:Sarabun;src:url(file://FONT/Sarabun-SemiBold.ttf);font-weight:600}
@font-face{font-family:Sarabun;src:url(file://FONT/Sarabun-Bold.ttf);font-weight:700}
@page{size:A4;margin:13mm 13mm 15mm 13mm}
*{box-sizing:border-box}
body{font-family:Sarabun,sans-serif;font-size:10.5pt;line-height:1.45;color:#17231d;margin:0}
h1,h2,h3{line-height:1.25;margin:0}
.page{page-break-after:always}.page:last-child{page-break-after:auto}
.eyebrow{font-weight:700;font-size:9.5pt;letter-spacing:.05em;color:#5a6a61}
.logo{display:block}.logo.ph{border:1.2pt dashed #9aa8a0;border-radius:4pt;display:grid;place-items:center;text-align:center;font-size:8pt;color:#5a6a61;line-height:1.2}
.cover{display:flex;flex-direction:column;height:269mm}
.cover .top{display:flex;align-items:center;gap:6mm}
.cover .org{font-size:10pt;color:#3c4a43;line-height:1.4}
.cover h1{font-size:44pt;margin-top:12mm}
.cover h2{font-size:20pt;color:#17607a;margin-top:2mm}
.cover .kind{display:inline-block;margin-top:5mm;background:#17231d;color:#fff;border-radius:3pt;padding:1.5mm 4mm;font-weight:700;font-size:12pt}
.cover .hero{margin-top:8mm;border-radius:4pt;overflow:hidden}
.cover .hero img{width:100%;display:block}
.cover p.intro{margin-top:5mm;font-size:11pt}
.cover .foot{margin-top:auto;display:flex;gap:5mm;align-items:flex-end;justify-content:space-between;font-size:8.5pt;color:#5a6a61;border-top:.8pt solid #d3dcd3;padding-top:3mm}
.band{display:flex;align-items:baseline;gap:4mm;border-bottom:2pt solid #17607a;padding-bottom:1.5mm;margin-bottom:3mm}
.band .no{font-weight:700;font-size:26pt;color:#17607a;line-height:1}
.band .when{font-weight:700;color:#17607a;font-size:11pt}
.band h2{font-size:19pt}
.shot{border-radius:3pt;overflow:hidden;position:relative}
.shot img{width:100%;display:block}
.shot.main img{height:90mm;object-fit:cover}
.cap{font-size:8.5pt;color:#5a6a61;margin-top:1mm}
.row{display:grid;grid-template-columns:1fr 50mm;gap:4mm;margin-top:3mm;align-items:start}
.facts{display:flex;flex-wrap:wrap;gap:2mm}
.fact{background:#eef2ed;border-radius:3pt;padding:1mm 3mm;line-height:1.3}
.fact small{display:block;font-size:8pt;color:#5a6a61}
.fact b{font-size:10.5pt}
.fact.alert{background:#fbe4e1}.fact.alert b{color:#b42318}
.lead{font-size:11pt;font-weight:600;margin:2.5mm 0 1mm}
.cols{column-count:2;column-gap:7mm}
.sec{margin-top:2mm}
.sec h3{break-after:avoid;font-size:11pt;color:#17231d;border-left:3pt solid #17607a;padding-left:2mm;margin-bottom:.5mm}
.sec p{margin:.8mm 0;text-align:left}
.mapnote{margin-top:3mm;background:#e3eff3;border-radius:3pt;padding:2mm 3mm;font-size:9.5pt}
table{border-collapse:collapse;width:100%}th,td{border:.6pt solid #b5c1ba;padding:.8mm 2mm;text-align:left;vertical-align:top;font-size:8.3pt;line-height:1.3}
th{background:#e4ebe4}
.legend{display:grid;grid-template-columns:repeat(3,1fr);gap:1.5mm 5mm;font-size:9pt;margin-top:3mm}
.legend div{display:flex;gap:2mm;align-items:center}
.sw{width:5mm;height:3.5mm;border-radius:1pt;flex:none;display:inline-block}
.num{display:inline-grid;place-items:center;width:4.6mm;height:4.6mm;border-radius:50%;color:#fff;font-weight:700;font-size:8pt;flex:none}
.people{display:grid;grid-template-columns:1fr 1fr;gap:1.5mm 4mm;font-size:8.8pt;line-height:1.35}
.people div{background:#fff1df;border-radius:3pt;padding:1.5mm 2.5mm}
.credits{font-size:10pt}.credits dt{font-weight:700;margin-top:3mm}.credits dd{margin:0}
"""

def doc():
    stages = S["stages"]; pages = []
    pages.append(f"""<section class="page cover">
      <div class="top">{logo_html(20)}<div class="org">{e(CR['organization'])}<br>{e(CR.get('program', ''))}</div></div>
      <h1>ตำบลฮอนกฮูก</h1><h2>{e(S['title'])}</h2>
      <div><span class="kind">เอกสารกรณีศึกษาสำหรับผู้เข้าร่วม</span></div>
      <div class="hero"><img src="{uri(VIEWS + '/stage4-overview.jpg')}"></div>
      <div class="cap">ภาพจำลอง 3 มิติของตำบลฮอนกฮูก ขณะเกิดน้ำป่าไหลหลาก (ช่วงที่ 4) แถบสีน้ำตาลคือกระแสน้ำป่า</div>
      <p class="intro">{e(S['intro'])}</p>
      <div class="foot"><div>{e(CR['short'])}</div><div>ใช้สำหรับการอบรมเท่านั้น</div></div></section>""")
    fac_rows = "".join(f'<div><span class="num" style="background:{KIND[f["kind"]][0]}">{k}</span>{e(f["name"])}</div>' for k, f in enumerate(V["facilities"], 1))
    pages.append(f"""<section class="page"><div class="eyebrow">ผังชุมชน</div><h2 style="font-size:20pt;margin-bottom:3mm">ผังตำบลฮอนกฮูก</h2>
      <div class="shot" style="border:.6pt solid #b5c1ba"><img src="{plan()}"></div>
      <div class="legend">{fac_rows}
        <div><span class="sw" style="background:#f4ecd8;border:.6pt solid #3a2a1a"></span>บ้าน (120 หลัง)</div>
        <div><span class="sw" style="background:#e8590c;border:.6pt solid #3a2a1a"></span>บ้านที่มีกลุ่มเปราะบาง</div>
        <div><span class="sw" style="background:#2f6fa8"></span>คลองและลำห้วย</div>
        <div><span class="sw" style="background:#fff3d6;border:.8pt solid #5a4a3a"></span>ถนน</div>
        <div><span class="sw" style="background:#333"></span>สะพาน</div>
        <div><span class="sw" style="background:#8a6a4a;height:1pt"></span>เส้นชั้นความสูงทุก 50 ม.</div></div>
      <p class="cap" style="margin-top:3mm">ภูมิประเทศเป็นของจริง (ด้านตะวันออกของเทือกเขาหลวง จ.นครศรีธรรมราช) ส่วนหมู่บ้าน อาคาร และผู้คนเป็นเรื่องสมมติ น้ำไหลจากที่สูงทางซ้ายบนลงสู่ทุ่งนาทางขวาล่าง</p>
      <h3 style="margin:3mm 0 1mm">วิธีอ่านภาพ 3 มิติในเอกสารนี้</h3>
      <div class="legend" style="grid-template-columns:repeat(2,1fr)">
        <div><span class="sw" style="background:#f1e9d6;border:.6pt solid #aaa"></span>บ้านทั่วไป</div>
        <div><span class="sw" style="background:#e8590c"></span>บ้านที่มีกลุ่มเปราะบาง (ติดเตียง ฟอกไต ตั้งครรภ์ ใช้ออกซิเจน จิตเวช)</div>
        <div><span class="sw" style="background:#7aa3cf"></span>บ้านที่น้ำเข้าแล้ว</div><div><span class="sw" style="background:#2e1b0e"></span>บ้านที่ถูกดินถล่มทับ</div>
        <div><span class="sw" style="background:#3f79b0"></span>น้ำท่วม (สีเข้ม = ลึก)</div><div><span class="sw" style="background:#8a5d33"></span>กระแสน้ำป่าไหลหลาก</div>
        <div><span class="sw" style="background:#c62828"></span>ลาดชันเสี่ยงดินถล่ม</div><div><span class="sw" style="background:#2f9e44"></span>เส้นประ = เส้นทางอพยพ</div>
        <div><span class="sw" style="background:linear-gradient(to top,#2f7d4f 25%,#d9a21a 25% 50%,#c0392b 50%)"></span>ไม้วัดระดับน้ำมุมซ้ายบน: น้ำสูงกว่าคลองปกติกี่เมตร</div>
        <div><span class="sw" style="background:#b42318"></span>ป้ายแดง = สะพานขาด</div></div>
      <p class="cap">ความสูงของภูเขาในภาพ 3 มิติขยายขึ้นประมาณ 1.8 เท่า เพื่อให้เห็นความลาดชันชัดเจน</p></section>""")
    vrows = ""
    for v in V["villages"]:
        hs = [h for h in HH if h["moo"] == v["moo"]]; s_ = lambda k: sum(h[k] for h in hs)
        vrows += f"<tr><td><b>หมู่ {v['moo']} {e(v['name'])}</b><br>{e(v['desc'])}</td><td>{len(hs)}</td><td>{s_('members')}</td><td>{s_('elderly')}</td><td>{s_('under5')}</td><td>{s_('bedridden')}</td><td>{s_('ncd')}</td></tr>"
    frows = "".join(f"<tr><td><b>{e(f['name'])}</b></td><td>{e(f['info']).replace(' | ', '<br>')}</td></tr>" for f in V["facilities"])
    people = "".join(f"<div><b>{e(h['story'].split(' ')[0].replace('บ้าน', ''))}</b> (บ้าน {h['id']}) {e(' '.join(h['story'].split(' ')[1:]))}</div>" for h in HH if h.get("story"))
    pages.append(f"""<section class="page"><div class="eyebrow">ข้อมูลพื้นฐาน</div><h2 style="font-size:20pt;margin-bottom:3mm">ผู้คนและสถานที่ในตำบล</h2>
      <table><tr><th>หมู่บ้าน</th><th>ครัวเรือน</th><th>คน</th><th>สูงอายุ</th><th>เด็ก &lt;5 ปี</th><th>ติดเตียง</th><th>โรคเรื้อรัง</th></tr>{vrows}</table>
      <h3 style="margin:4mm 0 2mm">คนที่ต้องการความช่วยเหลือเป็นพิเศษในเรื่องนี้</h3><div class="people">{people}</div>
      <h3 style="margin:4mm 0 2mm">สถานที่สำคัญ</h3><table>{frows}</table>
</section>""")
    for i, s in enumerate(stages):
        k = i + 1; ov = f"{VIEWS}/stage{k}-overview.jpg"
        side = f'<div><div class="shot"><img src="{uri(ov)}"></div><div class="cap">ภาพรวมทั้งตำบลในช่วงเดียวกัน</div></div>' if os.path.exists(ov) else "<div></div>"
        secs = "".join(f'<div class="sec"><h3>{e(x["h"])}</h3>{"".join(f"<p>{e(p)}</p>" for p in x["p"])}</div>' for x in s["sections"])
        pages.append(f"""<section class="page"><div class="band"><span class="no">{k}</span><div><div class="when">ช่วงที่ {k} จาก {len(stages)} · {e(s['time'])}</div><h2>{e(s['title'])}</h2></div></div>
          <div class="shot main"><img src="{uri(f'{VIEWS}/stage{k}.jpg')}"></div><div class="cap"><b>ในภาพ:</b> {e(s['map'])}</div>
          <div class="row"><div><div class="facts">{facts(s)}</div><p class="lead">{e(s['lead'])}</p></div>{side}</div>
          <div class="cols">{secs}</div></section>""")
    cr = "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in CR["credits"])
    pages.append(f"""<section class="page"><div class="top" style="display:flex;gap:6mm;align-items:center">{logo_html(16)}<div class="org">{e(CR['organization'])}</div></div>
      <h2 style="font-size:20pt;margin:6mm 0 2mm">เครดิตและข้อมูลอ้างอิง</h2><dl class="credits">{cr}</dl>
      <h3 style="margin:6mm 0 2mm">ข้อควรทราบ</h3><p style="font-size:10pt">{e(CR['disclaimer'])}</p>
      <div style="display:flex;gap:5mm;align-items:center;margin-top:8mm;border:1pt solid #17231d;border-radius:4pt;padding:3mm">
        <img src="{qr_uri()}" style="width:30mm"><div><b>ดูแผนที่ 3 มิติแบบหมุนได้ (เมื่อมีอินเทอร์เน็ต)</b><br>{e(URL)}<br><span class="cap">เปิดได้ทั้งในโทรศัพท์และคอมพิวเตอร์</span></div></div></section>""")
    return f'<!doctype html><html lang="th"><head><meta charset="utf-8"><title>กรณีศึกษาตำบลฮอนกฮูก</title><style>{CSS.replace("FONT", os.path.abspath("fonts"))}</style></head><body>{"".join(pages)}</body></html>'

open("output/casebook.html", "w").write(doc())
footer = ('<div style="font-family:Loma,sans-serif;font-size:7.5pt;color:#6a7a71;width:100%;padding:0 13mm;display:flex;justify-content:space-between">'
          '<span>กรณีศึกษาตำบลฮอนกฮูก · ' + e(CR["short"]) + '</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
js = """const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage();
await p.goto('file://'+process.cwd()+'/output/casebook.html');await p.waitForTimeout(800);
await p.pdf({path:'output/casebook-A4.pdf',format:'A4',printBackground:true,preferCSSPageSize:true,displayHeaderFooter:true,
headerTemplate:'<span></span>',footerTemplate:process.argv[1]});await b.close();})();"""
subprocess.run(["node", "-e", js, footer], check=True)
os.remove("output/casebook.html")
print("casebook ok")
