"""A4 printables: participant workbook + facilitator guide (HTML → PDF via Playwright/Chromium).

output/workbook.pdf     คู่มือผู้เข้าอบรม: ข้อมูลตำบล เรื่องเล่า ใบงาน 1–5 ทะเบียนครัวเรือน
output/facilitator.pdf  คู่มือวิทยากร: กำหนดการ วิธีใช้สื่อ เฉลยห่วงโซ่ผลกระทบ ตารางผลต่อสุขภาพ
Usage: python3 scripts/make_docs.py <3D-page-url>
"""
import json, sys, base64, io, os, subprocess, html
import qrcode

URL = sys.argv[1]
V = json.load(open("data/village.json")); S = json.load(open("data/story.json"))
HH = V["households"]; FAC = {f["id"]: f for f in V["facilities"]}; LV = V["levels"]
e = html.escape
FONT = os.path.abspath("fonts")

def qr_uri():
    q = qrcode.QRCode(border=1, box_size=8); q.add_data(URL); q.make()
    b = io.BytesIO(); q.make_image().save(b, format="PNG"); return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()
QR = qr_uri()
FLOOD = {"yearly": "ทุกปี", "heavy": "ปีน้ำมาก", "extreme": "ปีวิกฤต", "none": "–"}

CSS = f"""
@font-face{{font-family:Sarabun;src:url(file://{FONT}/Sarabun-Regular.ttf);font-weight:400}}
@font-face{{font-family:Sarabun;src:url(file://{FONT}/Sarabun-SemiBold.ttf);font-weight:600}}
@font-face{{font-family:Sarabun;src:url(file://{FONT}/Sarabun-Bold.ttf);font-weight:700}}
@page{{size:A4;margin:16mm 15mm 16mm 15mm}}
*{{box-sizing:border-box}}
body{{font-family:Sarabun,sans-serif;font-size:12.5pt;line-height:1.5;color:#1d2a24;margin:0}}
h1{{font-size:26pt;margin:0 0 4pt;line-height:1.2}} h2{{font-size:17pt;margin:0 0 6pt;color:#1f6f8b;line-height:1.25}}
h3{{font-size:13.5pt;margin:10pt 0 4pt}}
.page{{page-break-after:always}} .page:last-child{{page-break-after:auto}}
.eyebrow{{font-weight:700;font-size:10pt;letter-spacing:.06em;color:#5b6b62}}
.box{{border:1.2pt solid #1d2a24;border-radius:6pt;padding:6pt 9pt}}
.muted{{color:#5b6b62}} .small{{font-size:10pt}}
table{{border-collapse:collapse;width:100%}} th,td{{border:.8pt solid #9aa8a0;padding:3pt 5pt;vertical-align:top;text-align:left}}
th{{background:#e4ebe4;font-weight:700}} td:first-child{{white-space:nowrap}}
.reg td,.reg th{{font-size:8.6pt;padding:1.5pt 3pt;line-height:1.25}} .reg td.n{{text-align:center}}
.write td{{height:34pt}} .write.tall td{{height:56pt}}
.stage{{border-left:4pt solid #1f6f8b;padding:2pt 0 2pt 10pt;margin:0 0 12pt}}
.stage .when{{font-weight:700;color:#1f6f8b;font-size:11pt}}
.stage p{{margin:2pt 0}}
.ask{{background:#eef3ee;border-radius:5pt;padding:4pt 8pt;margin-top:4pt;font-size:11.5pt}}
.ask ol{{margin:0;padding-left:16pt}}
.chain{{display:grid;grid-template-columns:repeat(6,1fr);gap:4pt;margin:6pt 0 10pt}}
.chain div{{border:1.2pt solid #1d2a24;border-radius:5pt;min-height:92pt;padding:3pt 5pt;font-size:9.5pt;position:relative}}
.chain div b{{display:block;font-size:9.5pt;color:#fff;background:#1d2a24;margin:-3pt -5pt 4pt;padding:2pt 5pt;border-radius:3pt 3pt 0 0}}
.chain div:not(:last-child)::after{{content:"▶";position:absolute;right:-9pt;top:40%;font-size:10pt}}
.chain.ex div{{min-height:0;font-size:9.5pt}}
.c1 b{{background:#1f6f8b!important}} .c2 b{{background:#2f7d4f!important}} .c3 b{{background:#c2410c!important}}
.c4 b{{background:#7a2e0b!important}} .c5 b{{background:#b42318!important}} .c6 b{{background:#5f3dc4!important}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:10pt}}
.tag{{display:inline-block;border-radius:8pt;padding:0 6pt;font-size:9pt;font-weight:700;background:#e4ebe4}}
.tag.r{{background:#b42318;color:#fff}} .tag.o{{background:#c2410c;color:#fff}} .tag.b{{background:#1f6f8b;color:#fff}}
.cover{{display:flex;flex-direction:column;justify-content:space-between;height:255mm}}
.qr{{display:flex;gap:10pt;align-items:center}} .qr img{{width:34mm;height:34mm}}
ul{{margin:2pt 0;padding-left:16pt}}
"""

def doc(title, pages):
    return f'<!doctype html><html lang="th"><head><meta charset="utf-8"><title>{e(title)}</title><style>{CSS}</style></head><body>{"".join(pages)}</body></html>'

def tags(o):
    t = []
    if o["flood"] != "none": t.append(f'<span class="tag b">ท่วม{FLOOD[o["flood"]]}</span>')
    if o["flash"]: t.append('<span class="tag r">ทางน้ำป่า</span>')
    if o["landslide"] > .6: t.append('<span class="tag r">ดินถล่ม</span>')
    elif o["landslide"] > .4: t.append('<span class="tag o">ใกล้ลาดชัน</span>')
    return " ".join(t) or '<span class="muted">ที่ดอน</span>'

def vul_text(h):
    t = []
    if h["bedridden"]: t.append("ติดเตียง")
    if h["dialysis"]: t.append("ฟอกไต")
    if h["pregnant"]: t.append("ตั้งครรภ์")
    if h["psych"]: t.append("จิตเวช")
    if h["disabled"]: t.append("พิการ")
    if "ออกซิเจน" in h.get("story", ""): t.append("ใช้ออกซิเจน")
    if h["under5"]: t.append(f"เด็กเล็ก {h['under5']}")
    if h["elderly"]: t.append(f"สูงอายุ {h['elderly']}")
    if h["ncd"]: t.append(f"NCD {h['ncd']}")
    return ", ".join(t)

# ---------------------------------------------------------------- shared pieces
def cover(kind):
    sub = "คู่มือผู้เข้าอบรม" if kind == "w" else "คู่มือวิทยากร"
    return f"""<section class="page cover"><div>
      <div class="eyebrow">ชุดฝึกการวางแผนรับมือภัยพิบัติโดยชุมชน</div>
      <h1 style="font-size:40pt;margin-top:20pt">ตำบลฮอนกฮูก</h1>
      <h2 style="font-size:22pt">{e(S['title'])}</h2>
      <p style="font-size:15pt">{sub} · ฝึกวิเคราะห์ห่วงโซ่ผลกระทบ (impact chain) และผลต่อสุขภาพ (health outcome) จากน้ำท่วม น้ำป่า และดินถล่ม</p>
      <p class="muted">{e(S['intro'])}</p></div>
      <div class="box qr"><img src="{QR}" alt="QR"><div><b style="font-size:14pt">สแกนเพื่อเปิดแผนที่ 3 มิติในโทรศัพท์</b><br>
      หมุนดูภูเขา หุบ และทุ่งนา เลื่อนเรื่องเล่าทีละช่วง ดูน้ำท่วมสูงขึ้น และแตะบ้านแต่ละหลังเพื่อดูว่าใครอยู่ในบ้าน<br>
      <span class="small muted">ใช้ร่วมกับแผนที่กระดาษ A1: แผ่นที่ 1 แผนที่ฐาน (ใช้ระบายสี) และแผ่นที่ 2 แผนที่ความเสี่ยง (ฉบับเฉลย)</span></div></div>
    </section>"""

def village_page():
    rows = ""
    for v in V["villages"]:
        hs = [h for h in HH if h["moo"] == v["moo"]]
        s = lambda k: sum(h[k] for h in hs)
        wet = sum(h["flood"] != "none" for h in hs)
        rows += f"<tr><td><b>หมู่ {v['moo']} {e(v['name'])}</b><br><span class='small'>{e(v['desc'])}</span></td><td>{len(hs)}</td><td>{s('members')}</td><td>{s('elderly')}</td><td>{s('under5')}</td><td>{s('bedridden')}</td><td>{s('pregnant')}</td><td>{s('ncd')}</td><td>{wet}</td></tr>"
    fac = "".join(f"<tr><td><b>{e(f['name'])}</b></td><td class='small'>{e(f['info']).replace(' | ', '<br>')}</td></tr>" for f in V["facilities"])
    return f"""<section class="page"><div class="eyebrow">ข้อมูลพื้นฐาน</div><h2>รู้จักตำบลฮอนกฮูก</h2>
    <table class="small"><tr><th>หมู่บ้าน</th><th>ครัวเรือน</th><th>คน</th><th>สูงอายุ</th><th>เด็ก &lt;5 ปี</th><th>ติดเตียง</th><th>ตั้งครรภ์</th><th>โรคเรื้อรัง</th><th>บ้านในเขตน้ำท่วม*</th></tr>{rows}</table>
    <p class="small muted">* บ้านที่อยู่ในพื้นที่น้ำท่วมระดับใดระดับหนึ่ง (ทุกปี / ปีน้ำมาก / ปีวิกฤต) ตามแผนที่ความเสี่ยง</p>
    <h3>สถานที่สำคัญและทรัพยากร</h3><table class="small">{fac}</table>
    <h3>ทรัพยากรอื่นของตำบล</h3><ul class="small"><li>อสม. 14 คน, อปพร. 9 คน, วิทยุสื่อสาร 4 เครื่อง</li><li>เรือท้องแบน 2 ลำ (อบต.) และเรือหางยาวของชาวบ้าน 3 ลำ (หมู่ 4)</li>
    <li>รถกระบะยกสูงของชาวบ้าน 6 คัน, รถกู้ชีพ อบต. 1 คัน, โรงพยาบาลอำเภออยู่ห่างไปทางเหนือ 18 กม. (ต้องข้ามสะพานปากห้วย)</li>
    <li>กลุ่มไลน์ของหมู่บ้านมีสมาชิกประมาณ 40% ของครัวเรือน ผู้สูงอายุส่วนใหญ่ไม่ได้ใช้</li></ul></section>"""

def story_pages(with_notes=False):
    out = [f'<section class="page"><div class="eyebrow">เรื่องเล่า</div><h2>{e(S["title"])}</h2><p class="muted small">อ่านทีละช่วงตามลำดับเวลา เปิดแผนที่ 3 มิติไปที่ช่วงเดียวกันเพื่อดูระดับน้ำและเหตุการณ์ประกอบ</p>']
    for i, s in enumerate(S["stages"]):
        notes = f'<div class="ask small"><b>วิทยากร:</b> {NOTES[i]}</div>' if with_notes else ""
        facts = " · ".join(f"<b>{e(k)}</b> {e(v)}" for k, v in s["facts"].items())
        secs = "".join(f'<p style="margin-top:4pt"><b>{e(x["h"])}</b></p>' + "".join(f"<p>{e(t)}</p>" for t in x["p"]) for x in s["sections"])
        out.append(f'<div class="stage"><div class="when">ช่วงที่ {i + 1} · {e(s["time"])}</div><h3 style="margin:0 0 2pt">{e(s["title"])}</h3>'
                   f'<div class="small muted" style="margin-bottom:3pt">{facts}</div><p><i>{e(s["lead"])}</i></p>{secs}{notes}</div>')
    out.append("</section>")
    return out

CH_HEAD = ["1. ภัย", "2. อะไร/ใครถูกกระทบ", "3. ทำไมจึงเปราะบาง", "4. ผลกระทบที่ตามมา", "5. ผลต่อสุขภาพ", "6. ตัดห่วงโซ่ตรงไหน"]
def chain(cells=None, ex=False):
    cells = cells or [""] * 6
    return f'<div class="chain{" ex" if ex else ""}">' + "".join(f'<div class="c{i + 1}"><b>{CH_HEAD[i]}</b>{c}</div>' for i, c in enumerate(cells)) + "</div>"

EX_CHAIN = ["ฝนตกหนักต่อเนื่อง น้ำท่วมที่ลุ่ม 3–5 วัน", "ลุงเพิ่ม ผู้ป่วยฟอกไต หมู่ 4", "ต้องฟอกเลือดสัปดาห์ละ 2 ครั้ง บ้านอยู่ที่ลุ่ม สะพานปากห้วยขาด ไม่มีรถ",
            "ขาดนัดฟอกเลือด น้ำและเกลือแร่คั่ง", "บวม หอบเหนื่อย โพแทสเซียมสูง เสี่ยงหัวใจหยุดเต้นและเสียชีวิต",
            "ทำทะเบียนผู้ฟอกไต · ย้ายไปพักใกล้ รพ. ก่อนน้ำมา · เลื่อนนัดฟอกให้เร็วขึ้น · คุมอาหารเค็มและผลไม้ช่วงรอ"]

def worksheets():
    p = []
    p.append(f"""<section class="page"><div class="eyebrow">ใบงานที่ 1 · 40 นาที · ทำเป็นกลุ่มบนแผนที่ฐาน A1</div><h2>อ่านแผนที่และระบายพื้นที่เสี่ยง</h2>
    <p>ใช้แผนที่แผ่นที่ 1 (แผนที่ฐาน) กับปากกาเมจิก 5 สี แล้วช่วยกันระบายลงบนแผนที่ อ้างตำแหน่งด้วยตารางกริด เช่น “F4” <b>ห้ามดูแผนที่ความเสี่ยงก่อนทำเสร็จ</b></p>
    <table class="write"><tr><th style="width:22%">สี</th><th>ระบายอะไร</th><th style="width:30%">กลุ่มเราเห็นว่าอยู่ช่องไหนบ้าง</th></tr>
    <tr><td>น้ำเงินเข้ม / อ่อน</td><td>พื้นที่ที่น้ำท่วมทุกปี / น้ำท่วมเฉพาะปีน้ำมาก</td><td></td></tr>
    <tr><td>ส้ม</td><td>เส้นทางที่น้ำป่าไหลมาเร็วและแรง</td><td></td></tr>
    <tr><td>แดง</td><td>ลาดชันที่อาจเกิดดินถล่ม</td><td></td></tr>
    <tr><td>วงกลมแดง</td><td>บ้านที่มีคนช่วยตัวเองไม่ได้ (ดูทะเบียนท้ายเล่ม)</td><td></td></tr>
    <tr><td>เขียว</td><td>จุดปลอดภัย และเส้นทางอพยพจากแต่ละหมู่</td><td></td></tr></table>
    <h3>คำถามหลังระบายสีเสร็จ</h3><table class="write"><tr><td style="width:50%">1. สถานที่สำคัญแห่งไหนอยู่ในพื้นที่น้ำท่วม (รพ.สต. โรงเรียน ศพด. ประปา)</td><td></td></tr>
    <tr><td>2. ถ้าสะพานปากห้วยขาด หมู่ไหนจะไปถึง รพ.สต. และโรงพยาบาลอำเภอไม่ได้</td><td></td></tr>
    <tr><td>3. วิธีดูเส้นชั้นความสูง: น้ำจะไหลจากเลขมากไปเลขน้อย ลองหาว่าน้ำจากภูเขาจะผ่านบ้านเลขที่เท่าไรก่อน</td><td></td></tr>
    <tr><td>4. เทียบกับแผนที่ความเสี่ยง (แผ่นที่ 2) แล้วตอบว่ากลุ่มเรามองข้ามจุดไหนไป</td><td></td></tr></table></section>""")
    p.append(f"""<section class="page"><div class="eyebrow">ใบงานที่ 2 · 60 นาที</div><h2>ห่วงโซ่ผลกระทบ (Impact chain)</h2>
    <p>ภัยหนึ่งครั้งทำให้เกิดผลกระทบต่อกันเป็นทอด ๆ เหมือนโดมิโน เลือกเหตุการณ์จากเรื่องเล่ามา 1 เรื่อง แล้วไล่ทีละช่อง จากภัยไปจนถึงผลต่อสุขภาพ
    ช่องสุดท้ายให้ตอบว่า <b>ถ้าจะหยุดโดมิโน ชุมชนต้องดึงตัวไหนออก</b> และต้องทำตอนไหน (ก่อน ระหว่าง หรือหลังภัย)</p>
    <h3>ตัวอย่าง</h3>{chain(EX_CHAIN, ex=True)}
    <h3>กลุ่มของเรา: เหตุการณ์ ............................................................</h3>{chain()}
    <h3>เหตุการณ์ ............................................................</h3>{chain()}
    <p class="small muted">แนวเหตุการณ์ให้เลือก: ยายเอียดติดเตียงกับน้ำป่า · ประปาจม · น้องฝ้ายเจ็บท้องคลอดเมื่อถนนขาด · รพ.สต. น้ำท่วม · ศูนย์อพยพแออัด · เครื่องผลิตออกซิเจนของป้าจวง · บังหมาดกับอินซูลิน · นายเดชขาดยาจิตเวช · ชาวนาลุยโคลน · บ้านใต้ลาดชันหมู่ 3</p></section>""")
    p.append(f"""<section class="page"><div class="eyebrow">ใบงานที่ 3 · 45 นาที</div><h2>ผลต่อสุขภาพตามช่วงเวลา</h2>
    <p>แต่ละช่วงของภัยทำให้เกิดปัญหาสุขภาพต่างกัน เติมในตารางว่าแต่ละช่วงเกิดโรคหรือการบาดเจ็บอะไร ใครเสี่ยงที่สุด และชุมชนทำอะไรได้</p>
    <table class="write tall"><tr><th style="width:18%">ช่วงเวลา</th><th>เกิดโรค / บาดเจ็บอะไร</th><th style="width:22%">ใครเสี่ยงที่สุด</th><th style="width:28%">ชุมชนทำอะไรได้</th></tr>
    <tr><td><b>ก่อนเกิดภัย</b><br><span class="small">ช่วงเตือนภัย</span></td><td></td><td></td><td></td></tr>
    <tr><td><b>ขณะเกิดภัย</b><br><span class="small">ชั่วโมงแรก ๆ</span></td><td></td><td></td><td></td></tr>
    <tr><td><b>ในศูนย์อพยพ</b><br><span class="small">วันที่ 1–7</span></td><td></td><td></td><td></td></tr>
    <tr><td><b>น้ำลด</b><br><span class="small">สัปดาห์ที่ 2–4</span></td><td></td><td></td><td></td></tr>
    <tr><td><b>ฟื้นฟู</b><br><span class="small">1–6 เดือน</span></td><td></td><td></td><td></td></tr></table>
    <p class="small muted">คำใบ้: คิดให้ครบทั้ง “ร่างกาย” (จมน้ำ บาดเจ็บ ไฟดูด ติดเชื้อ) “โรคเดิมกำเริบ” (เบาหวาน ความดัน ไต หอบ จิตเวช) “แม่และเด็ก” และ “จิตใจ”</p></section>""")
    vul = [h for h in HH if h["bedridden"] or h["dialysis"] or h["pregnant"] or h["psych"] or h["disabled"] or "ออกซิเจน" in h.get("story", "")]
    rows = "".join(f"<tr><td>{h['id']}</td><td>{h['no']}</td><td>{e(vul_text(h))}{'<br><i class=small>' + e(h['story']) + '</i>' if h.get('story') else ''}</td><td>{tags(h)}</td><td></td><td></td><td></td></tr>" for h in vul)
    p.append(f"""<section class="page"><div class="eyebrow">ใบงานที่ 4 · 45 นาที</div><h2>ทะเบียนกลุ่มเปราะบางและระบบคู่หู</h2>
    <p>รายชื่อครัวเรือนที่มีคนช่วยตัวเองไม่ได้ ให้ช่วยกันจัดลำดับว่าต้องช่วยใครก่อน (เขียน 1, 2, 3…) ใครเป็น “คู่หู” ที่จะไปช่วย และต้องไปตอนไหน</p>
    <table class="small"><tr><th>รหัส</th><th>บ้านเลขที่</th><th>ใครต้องการความช่วยเหลือ</th><th>ความเสี่ยงของบ้าน</th><th style="width:7%">ลำดับ</th><th style="width:15%">คู่หู (ใคร)</th><th style="width:15%">ไปช่วยเมื่อ / ไปที่ไหน</th></tr>{rows}</table>
    <p class="small muted">รหัสบ้านตรงกับตัวเลขข้างบ้านบนแผนที่กระดาษ เช่น 2-052 คือบ้านหมายเลข 52 ในหมู่ 2</p></section>""")
    p.append("""<section class="page"><div class="eyebrow">ใบงานที่ 5 · 60 นาที</div><h2>ร่างแผนรับมือของตำบลฮอนกฮูก</h2>
    <p>ใช้สิ่งที่ได้จากใบงานที่ 1–4 มาร่างแผน กำหนด “สัญญาณ” ที่จะใช้เริ่มลงมือแต่ละขั้น เช่น ปริมาณฝน ระดับน้ำที่ไม้วัด หรือประกาศเตือน</p>
    <table class="write tall"><tr><th style="width:17%">ขั้น</th><th style="width:20%">สัญญาณเริ่ม</th><th>ทำอะไร</th><th style="width:18%">ใครรับผิดชอบ</th><th style="width:16%">ใช้อะไร</th></tr>
    <tr><td><b>เฝ้าระวัง</b><br><span class="small">สีเขียว</span></td><td class="small muted">เช่น ฝน 24 ชม. เกิน 100 มม.</td><td></td><td></td><td></td></tr>
    <tr><td><b>เตรียมพร้อม</b><br><span class="small">สีเหลือง</span></td><td></td><td></td><td></td><td></td></tr>
    <tr><td><b>อพยพ</b><br><span class="small">สีแดง</span></td><td></td><td></td><td></td><td></td></tr>
    <tr><td><b>ช่วงอยู่ศูนย์อพยพ</b></td><td></td><td></td><td></td><td></td></tr>
    <tr><td><b>กลับบ้าน / ฟื้นฟู</b></td><td></td><td></td><td></td><td></td></tr></table>
    <h3>รายการที่ต้องมีในแผน (ติ๊กเมื่อกลุ่มคุยแล้ว)</h3>
    <div class="two small"><div>☐ ช่องทางเตือนภัยที่ถึงทุกบ้าน รวมคนไม่ใช้ไลน์<br>☐ คนตัดสินใจสั่งอพยพ และคนสำรอง<br>☐ ทะเบียนกลุ่มเปราะบางที่ทันสมัย + คู่หู<br>☐ จุดอพยพ + เส้นทาง ที่ไม่ข้ามสะพานเสี่ยง<br>☐ ยาโรคเรื้อรังสำรอง 2 สัปดาห์ / ถุงยาประจำตัว</div>
    <div>☐ ไฟสำรองสำหรับผู้ใช้อุปกรณ์การแพทย์และตู้เย็นวัคซีน<br>☐ ย้ายยาและเวชภัณฑ์ของ รพ.สต. ขึ้นที่สูง<br>☐ น้ำดื่ม ส้วม ขยะ ในศูนย์อพยพ<br>☐ เฝ้าระวังโรคหลังน้ำลด (ฉี่หนู ท้องเสีย ไข้เลือดออก)<br>☐ ดูแลจิตใจ และติดตามบ้านใต้ลาดชัน</div></div></section>""")
    return p

def register():
    rows = "".join(f"<tr><td>{h['id']}</td><td>{h['no']}</td><td class='n'>{h['members']}</td><td class='n'>{h['elderly'] or ''}</td><td class='n'>{h['under5'] or ''}</td>"
                   f"<td>{e(vul_text(h).replace('สูงอายุ', 'สอ.').replace('เด็กเล็ก', 'ด.'))}</td><td>{e(h['house'])}</td><td>{e(h['water'])}</td><td>{FLOOD[h['flood']]}{' · น้ำป่า' if h['flash'] else ''}{' · ดินถล่ม' if h['landslide'] > .6 else ''}</td></tr>" for h in HH)
    return [f"""<section class="page"><div class="eyebrow">ภาคผนวก</div><h2>ทะเบียนครัวเรือน 120 หลัง (ข้อมูลสมมติ)</h2>
    <table class="reg"><tr><th>รหัส</th><th>เลขที่</th><th>คน</th><th>สูงอายุ</th><th>&lt;5 ปี</th><th>กลุ่มเปราะบาง / โรค</th><th>ลักษณะบ้าน</th><th>น้ำใช้</th><th>ความเสี่ยง</th></tr>{rows}</table></section>"""]

# ---------------------------------------------------------------- facilitator content
NOTES = [
 "ให้กลุ่มหมุนแผนที่ 3 มิติ หรือดูเส้นชั้นความสูงบนแผนที่ฐาน แล้วชี้ว่าน้ำจะไหลจากหุบไปทุ่ง ประเด็นที่ควรได้: รพ.สต. อยู่คนละฝั่งสะพานกับหมู่ 1–2, ศพด. และประปาอยู่ที่ต่ำ, หมู่ 2 มีทางออกเส้นเดียว",
 "ประเด็น: คำเตือนมาถึงแต่ไม่ถึงทุกคน (ไลน์ไม่ครอบคลุม) ควรมีเกณฑ์ฝนชัดเจน (เช่น ฝน 24 ชม. มากกว่า 100 มม. ให้เตรียมพร้อม เกิน 150–200 มม. หรือฝนตกหนักต่อเนื่องให้อพยพคนในหุบและใต้ลาดชัน) ย้ายผู้ป่วยติดเตียง ผู้ฟอกไต และหญิงใกล้คลอดก่อนเกิดเหตุ",
 "ประเด็น: น้ำท่วมทุกปีทำให้ชินจนประมาท ประปาจมคือจุดเริ่มของโรคทางน้ำ เด็กจมน้ำเป็นสาเหตุการตายอันดับต้นของเด็กไทยช่วงน้ำท่วม ต้องมีคนเฝ้าเด็ก ห้ามเล่นน้ำ และเก็บยาหรืออินซูลินขึ้นที่สูง",
 "ประเด็น: น้ำป่ามาเร็วกว่าน้ำท่วมมาก (40 นาที) จึงต้องอพยพก่อน ไม่ใช่รอให้เห็นน้ำ ผู้ชายวัยทำงานเสียชีวิตจากการลงไปเก็บทรัพย์สินบ่อย มิสเตอร์เตือนภัยต้องมีช่องทางแจ้งสำรอง เช่น วิทยุสื่อสาร ไซเรน หรือเคาะเกราะ",
 "ประเด็น: สัญญาณเตือนดินถล่ม (น้ำในห้วยขุ่นข้นแล้วลดลงทันที มีรอยแยก ต้นไม้เอียง ได้ยินเสียงดังในเขา) ฝึกการคัดแยกผู้บาดเจ็บ (triage): ผู้ถูกทับช่วงอกและหญิงเจ็บครรภ์ต้องส่งต่อด่วน แจ้ง 1669 ขอเรือหรือเฮลิคอปเตอร์ผ่านอำเภอ รพ.สต. ต้องย้ายยาและวัคซีนขึ้นที่สูงตั้งแต่ช่วงที่ 2",
 "ประเด็น: มาตรฐานศูนย์อพยพ (น้ำดื่มอย่างน้อย 15 ลิตรต่อคนต่อวัน, ส้วม 1 ห้องต่อ 20 คน, แยกโซนผู้ป่วย แม่และเด็ก) การคัดกรองโรคเรื้อรังตั้งแต่วันแรก ผู้ฟอกไตส่งต่อไม่ช้ากว่า 3 วันหลังนัด ห้ามติดเครื่องปั่นไฟในที่ปิดเพราะพิษคาร์บอนมอนอกไซด์",
 "ประเด็น: โรคฉี่หนู (ไข้สูง ปวดน่อง ตาแดง หลังลุยน้ำ 2–30 วัน ต้องรีบพบแพทย์), อุจจาระร่วง, บาดทะยักจากแผล, ไฟดูด, งูกัด, ไข้เลือดออกหลังน้ำลด 2–4 สัปดาห์ ควรสวมรองเท้าบูท ตัดไฟก่อนเข้าบ้าน และคลอรีนบ่อน้ำ",
 "ประเด็น: ผลระยะยาวกระทบรายได้ สุขภาพจิต และการควบคุมโรคเรื้อรัง บ้านใต้ลาดชันเป็นเรื่องที่ต้องตัดสินใจร่วมกันระหว่างย้ายออกหรืออยู่ต่อพร้อมระบบเตือน ปิดท้ายด้วยใบงานที่ 5",
]

ANSWERS = [
 ["น้ำป่าไหลหลากตอนตี 2", "ยายเอียดติดเตียง หมู่ 2", "เคลื่อนไหวเองไม่ได้ บ้านไม้ชั้นเดียวริมคลอง อยู่กับหลานเด็ก ทางออกเส้นเดียว", "น้ำขึ้นเร็วจนหนีไม่ทัน ไม่มีใครรู้ว่าต้องไปช่วย", "จมน้ำ/เสียชีวิต, ปอดอักเสบจากสำลักน้ำ, แผลกดทับ", "ระบบคู่หู + ทะเบียนติดเตียง · ย้ายก่อนเมื่อฝนถึงเกณฑ์"],
 ["น้ำท่วมตู้ควบคุมประปา", "ประปาหมู่บ้าน → หมู่ 1, 2, 4", "ตู้ไฟอยู่ระดับพื้น สูบน้ำจากคลอง", "ใช้น้ำบ่อตื้นหรือน้ำท่วม ล้างมือไม่ได้", "อุจจาระร่วง บิด ไทฟอยด์ ตับอักเสบเอ โรคผิวหนัง ตาแดง", "ยกตู้ไฟขึ้นสูง · สำรองน้ำดื่ม · แจกคลอรีน · ต้มน้ำ"],
 ["ดินถล่ม + ถนนขาด", "น้องฝ้าย ตั้งครรภ์ 37 สัปดาห์ หมู่ 3", "ครรภ์แรก บ้านอยู่ใต้ลาดชัน สามีไม่อยู่ ถนนไป รพ. ขาด", "คลอดนอกโรงพยาบาลโดยไม่มีผู้ทำคลอด", "ตกเลือดหลังคลอด คลอดยาก ทารกขาดออกซิเจน ติดเชื้อ", "ทะเบียนหญิงใกล้คลอด · ย้ายไปพักใกล้ รพ. ก่อนฤดูน้ำ · ชุดทำคลอดฉุกเฉินที่ รพ.สต."],
 ["น้ำท่วม รพ.สต. + ไฟดับ", "ยา วัคซีน บริการสุขภาพ", "เก็บยาชั้นล่าง ไม่มีเครื่องปั่นไฟ", "ยาเสียหาย วัคซีนเสื่อม บริการหยุด", "โรคเรื้อรังกำเริบ ขาดวัคซีน ผู้บาดเจ็บไม่ได้รักษา", "ย้ายยาขึ้นที่สูง · ตู้เย็นพร้อมไฟสำรอง · หน่วยบริการเคลื่อนที่ที่วัด"],
 ["ไฟดับหลายวัน", "ป้าจวง ใช้เครื่องผลิตออกซิเจน", "อุปกรณ์ต้องใช้ไฟฟ้า แบตเตอรี่สำรองน้อย", "ขาดออกซิเจน", "หอบเหนื่อย ระดับออกซิเจนต่ำ เสียชีวิต", "ทะเบียนผู้ใช้อุปกรณ์ไฟฟ้า · ย้ายไปจุดที่มีไฟสำรองก่อน · ถังออกซิเจนสำรอง"],
 ["ศูนย์อพยพแออัด", "คน 310 คนที่วัด", "ส้วมไม่พอ น้ำดื่มไม่พอ ไม่มีโซนผู้ป่วย", "สุขาภิบาลแย่ ยุงชุม เครียด", "อุจจาระร่วง ทางเดินหายใจ ไข้เลือดออก ความขัดแย้ง ความรุนแรง", "จัดศูนย์สำรองที่ อบต. · ส้วมเคลื่อนที่ · คัดกรองรายวัน · จิตอาสาดูแล"],
 ["ลุยน้ำและโคลนหลังน้ำลด", "ชาวนาและคนกรีดยาง", "มีแผลที่เท้า ไม่มีรองเท้าบูท ต้องรีบกลับไปทำงาน", "สัมผัสน้ำปนเปื้อนฉี่หนู", "โรคฉี่หนู (เลปโตสไปโรซิส) ไตวาย เสียชีวิต", "แจกรองเท้าบูท · ให้ความรู้อาการ · อสม. ติดตามคนมีไข้ · ส่งต่อเร็ว"],
 ["เครื่องปั่นไฟในห้องปิด", "ครอบครัวหมู่ 4", "ไม่รู้อันตรายของไอเสีย", "สูดก๊าซคาร์บอนมอนอกไซด์", "ปวดหัว คลื่นไส้ หมดสติ เสียชีวิต", "ตั้งเครื่องนอกบ้าน · ให้ความรู้ผ่านหอกระจายข่าว"],
]

HEALTH = [
 ("ขณะเกิดภัย", "จมน้ำ, บาดเจ็บจากของที่ลอยมาหรือถูกดินทับ, ไฟดูด, ภาวะตัวเย็นเกิน", "เด็ก, ผู้ชายวัยทำงาน (ลงไปเก็บของ), ผู้ติดเตียง, คนพิการ"),
 ("ช่วงอพยพ (1–7 วัน)", "อุจจาระร่วง, ไข้หวัดหรือปอดอักเสบ, โรคเรื้อรังกำเริบเพราะขาดยา (เบาหวาน ความดัน ไต หอบหืด จิตเวช), พิษคาร์บอนมอนอกไซด์, คลอดฉุกเฉิน", "ผู้ป่วยโรคเรื้อรัง ผู้ฟอกไต ผู้ใช้ออกซิเจน หญิงตั้งครรภ์ เด็กเล็ก"),
 ("หลังน้ำลด (2–4 สัปดาห์)", "โรคฉี่หนู, ผิวหนังติดเชื้อหรือน้ำกัดเท้า, ตาแดง, บาดทะยัก, ไฟดูดตอนเปิดไฟ, งูกัด, ไข้เลือดออก", "ชาวนา คนกรีดยาง คนทำความสะอาดบ้าน เด็ก"),
 ("ระยะยาว (1–6 เดือน)", "เครียด ซึมเศร้า โรคเครียดหลังเหตุการณ์ร้ายแรง (PTSD), ดื่มสุรามากขึ้น, โรคเรื้อรังคุมไม่ได้, ภาวะทุพโภชนาการ, การเรียนของเด็กหยุดชะงัก", "ครอบครัวผู้เสียชีวิต ผู้สูญเสียรายได้ ผู้สูงอายุ เด็ก"),
]

def facilitator():
    p = [cover("f")]
    p.append(f"""<section class="page"><div class="eyebrow">สำหรับวิทยากร</div><h2>ภาพรวมการอบรม (1 วัน)</h2>
    <table><tr><th style="width:18%">เวลา</th><th>กิจกรรม</th><th style="width:28%">สื่อ</th></tr>
    <tr><td>09:00–09:30</td><td>เปิดการอบรม ให้แต่ละคนเล่าภัยที่เคยเจอในชุมชนตัวเอง</td><td>–</td></tr>
    <tr><td>09:30–10:10</td><td>ใบงานที่ 1 อ่านแผนที่และระบายพื้นที่เสี่ยง (กลุ่มละ 6–8 คน)</td><td>แผนที่ฐาน A1 กลุ่มละ 1 แผ่น ปากกาเมจิก 5 สี</td></tr>
    <tr><td>10:10–10:30</td><td>เฉลยด้วยแผนที่ความเสี่ยง เปิดแผนที่ 3 มิติให้ทุกคนสแกน</td><td>แผนที่ความเสี่ยง A1, QR</td></tr>
    <tr><td>10:30–12:00</td><td>อ่านเรื่องเล่าช่วงที่ 1–5 หยุดคุยทีละช่วง เลื่อนแผนที่ 3 มิติตาม</td><td>เรื่องเล่า, โทรศัพท์</td></tr>
    <tr><td>13:00–14:00</td><td>ใบงานที่ 2 ห่วงโซ่ผลกระทบ แต่ละกลุ่มเลือกเหตุการณ์คนละเรื่อง</td><td>ใบงาน 2 หรือกระดาษฟลิปชาร์ต</td></tr>
    <tr><td>14:00–14:45</td><td>เรื่องเล่าช่วงที่ 6–8 + ใบงานที่ 3 ผลต่อสุขภาพตามช่วงเวลา</td><td>ใบงาน 3</td></tr>
    <tr><td>14:45–15:30</td><td>ใบงานที่ 4 ทะเบียนกลุ่มเปราะบางและระบบคู่หู</td><td>ใบงาน 4</td></tr>
    <tr><td>15:30–16:30</td><td>ใบงานที่ 5 ร่างแผนรับมือ นำเสนอ แล้วเชื่อมกลับไปที่ตำบลจริงของผู้เข้าอบรม</td><td>ใบงาน 5</td></tr></table>
    <h3>การเตรียมตัว</h3><ul><li>พิมพ์แผนที่ฐาน A1 กลุ่มละ 1 แผ่น และแผนที่ความเสี่ยง A1 จำนวน 1–2 แผ่น (ถ้าพิมพ์ A1 ไม่ได้ พิมพ์ A3 ได้ แต่มาตราส่วนจะเป็น 1:20,000)</li>
    <li>ทดลองเปิด QR ล่วงหน้า แผนที่ 3 มิติต้องใช้อินเทอร์เน็ตตอนเปิดครั้งแรก (ประมาณ 2 MB) หลังจากนั้นใช้งานได้ต่อเนื่อง</li>
    <li>แผนที่ 3 มิติจะเปิดที่ช่วงเดียวกับที่ผู้ใช้ดูไว้ล่าสุด ให้กดปุ่ม ‹ ย้อนกลับไปช่วงที่ 1 ก่อนเริ่ม</li></ul>
    <h3>ข้อจำกัดที่ควรบอกผู้เข้าอบรม</h3><ul class="small"><li>ภูมิประเทศเป็นของจริง (ข้อมูลความสูงจากดาวเทียม SRTM ความละเอียดประมาณ 19–30 เมตร) แต่ชุมชน คน และเหตุการณ์เป็นเรื่องสมมติ</li>
    <li>พื้นที่น้ำท่วมคำนวณจาก “ความสูงเหนือทางน้ำที่ใกล้ที่สุด” ({LV['yearly']} / {LV['heavy']:.0f} / {LV['extreme']:.0f} เมตร) ไม่ได้คำนวณปริมาณน้ำจริง ส่วนความเสี่ยงดินถล่มคำนวณจากความชันและร่องรับน้ำ ไม่รวมชนิดดินและหิน</li>
    <li>ในพื้นที่จริงต้องใช้ข้อมูลจากชุมชนเอง (ระดับน้ำที่เคยท่วม รอยดินแยก) ร่วมกับแผนที่ของกรมทรัพยากรธรณีและ ปภ.</li></ul></section>""")
    p += story_pages(with_notes=True)
    p.append('<section class="page"><div class="eyebrow">เฉลยใบงานที่ 2</div><h2>ตัวอย่างห่วงโซ่ผลกระทบจากเรื่องเล่า</h2><p class="small">ไม่มีคำตอบเดียวที่ถูก ให้ชมกลุ่มที่ไล่ได้หลายทอดและหาจุดตัดห่วงโซ่ได้ตั้งแต่ “ก่อนเกิดภัย”</p>'
             + "".join(chain(a, ex=True) for a in ANSWERS[:5]) + "</section>")
    p.append('<section class="page"><div class="eyebrow">เฉลยใบงานที่ 2 (ต่อ) และใบงานที่ 3</div><h2>ผลต่อสุขภาพตามช่วงเวลา</h2>' + "".join(chain(a, ex=True) for a in ANSWERS[5:])
             + '<table class="small"><tr><th style="width:20%">ช่วงเวลา</th><th>ผลต่อสุขภาพที่พบบ่อย</th><th style="width:30%">กลุ่มเสี่ยง</th></tr>'
             + "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td></tr>" for a, b, c in HEALTH) + "</table>"
             + """<h3>อาการที่ อสม. ต้องรีบส่งต่อ</h3><ul class="small"><li>ไข้สูงหลังลุยน้ำ ปวดน่องมาก ตาแดง ตาเหลือง ปัสสาวะน้อย (สงสัยโรคฉี่หนู)</li>
             <li>ท้องเสียในเด็กเล็กหรือผู้สูงอายุร่วมกับซึม ปัสสาวะน้อย (ขาดน้ำ)</li><li>ผู้ฟอกไตที่บวม หอบ นอนราบไม่ได้ · ผู้ป่วยเบาหวานซึม สับสน</li>
             <li>ปวดหัว คลื่นไส้หลายคนในบ้านเดียวกันที่ใช้เครื่องปั่นไฟ (พิษคาร์บอนมอนอกไซด์)</li><li>หญิงตั้งครรภ์มีเลือดออก น้ำเดิน หรือเจ็บครรภ์ถี่</li></ul></section>""")
    vul = [h for h in HH if h.get("story") or h["bedridden"] or h["dialysis"] or h["pregnant"]]
    exp = "".join(f"<tr><td>{h['id']}</td><td>{e(vul_text(h))}</td><td>{tags(h)}</td><td class='small'>{e(h.get('story', ''))}</td></tr>" for h in vul)
    fac = "".join(f"<tr><td>{e(f['name'])}</td><td>{tags(f)}</td><td>{f['hand']:.1f} ม.</td></tr>" for f in V["facilities"])
    p.append(f"""<section class="page"><div class="eyebrow">เฉลยใบงานที่ 1 และ 4</div><h2>ความเสี่ยงของสถานที่และกลุ่มเปราะบาง</h2>
    <table class="small"><tr><th>สถานที่</th><th>ความเสี่ยง</th><th>สูงเหนือทางน้ำ</th></tr>{fac}</table>
    <p class="small">ประเด็นสำคัญ: ศูนย์อพยพหลัก (วัด) และ รพ.สต. อยู่ฝั่งใต้ของสะพานปากห้วย ถ้าสะพานขาด คนหมู่ 1 ฝั่งเหนือและหมู่ 2 ต้องไปที่ อบต. แทน ส่วนหมู่ 2 ไม่มีที่ดอนที่ปลอดภัยจากดินถล่มบนเส้นทางออก จึงต้องอพยพก่อนสะพานในหุบขาด</p>
    <h3>ครัวเรือนที่ต้องช่วยก่อน</h3><table class="small"><tr><th>รหัส</th><th>ผู้ต้องการความช่วยเหลือ</th><th>ความเสี่ยง</th><th>ในเรื่องเล่า</th></tr>{exp}</table></section>""")
    return p

os.makedirs("output", exist_ok=True)
open("output/workbook.html", "w").write(doc("คู่มือผู้เข้าอบรม ตำบลฮอนกฮูก", [cover("w"), village_page()] + story_pages() + worksheets() + register()))
open("output/facilitator.html", "w").write(doc("คู่มือวิทยากร ตำบลฮอนกฮูก", facilitator()))
js = """const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage();
for (const n of ['workbook','facilitator']){await p.goto('file://'+process.cwd()+'/output/'+n+'.html');await p.waitForTimeout(500);
await p.pdf({path:'output/'+n+'.pdf',format:'A4',printBackground:true,preferCSSPageSize:true});}await b.close();})();"""
subprocess.run(["node", "-e", js], check=True)
for n in ("workbook", "facilitator"):
    os.remove(f"output/{n}.html")
print("docs ok")
