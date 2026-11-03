"""Place the fictional community of ตำบลฮอนกฮูก on the real terrain and derive each feature's hazard exposure.

Everything here (names, people, buildings, roads) is invented for training. Only the terrain is real.
Coordinates are DEM pixels (x = column, y = row) of the 384x384 crop, 1 px ≈ 18.9 m.
Output: data/village.json
"""
import json, heapq, random, math
import numpy as np
from scipy import ndimage

T = np.load("data/terrain.npz")
DEM, HAND, SLOPE, POND, LS, ACC = (T[k] for k in ("dem", "hand", "slope", "pond", "landslide", "acc_km2"))
META = json.load(open("data/meta.json"))
N = DEM.shape[0]
LSNEAR = ndimage.maximum_filter(LS, 9)           # landslide source within ~85 m uphill/around
STREAM = ACC > 0.4
# flash-flood corridor: big upstream catchment coming out of the mountain valley, low HAND
FLASH = (ACC > 3) & (HAND < 3)
FLASH = ndimage.binary_dilation(FLASH, iterations=3) & (HAND < 3.5)

# Flood scenario levels (m above nearest drainage) – used by maps, 3D and worksheets
LEVELS = {"yearly": 1.5, "heavy": 3.0, "extreme": 5.0}

rng = random.Random(2568)


def find_site(ax, ay, r, ok):
    best = None
    for y in range(max(0, ay - r), min(N, ay + r + 1)):
        for x in range(max(0, ax - r), min(N, ax + r + 1)):
            if ok(x, y):
                d = (x - ax) ** 2 + (y - ay) ** 2
                if best is None or d < best[0]:
                    best = (d, x, y)
    if best is None:
        raise SystemExit(f"no site near {ax},{ay}")
    return best[1], best[2]


def flat(x, y, s=6):
    return SLOPE[y, x] < s and not STREAM[y, x]


# ---------------------------------------------------------------- roads (least-cost paths on terrain)
def route(pts, water_pen=60):
    cost = 1 + (SLOPE / 4) ** 2 + np.where(STREAM, water_pen, 0) + np.where(HAND < 1, 3, 0)
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dist = {(x0, y0): 0}; prev = {}; pq = [(0, x0, y0)]
        while pq:
            d, x, y = heapq.heappop(pq)
            if (x, y) == (x1, y1):
                break
            if d > dist[(x, y)]:
                continue
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == dy == 0:
                        continue
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < N and 0 <= yy < N:
                        nd = d + cost[yy, xx] * (1.414 if dx and dy else 1)
                        if nd < dist.get((xx, yy), 1e18):
                            dist[(xx, yy)] = nd; prev[(xx, yy)] = (x, y); heapq.heappush(pq, (nd, xx, yy))
        seg = [(x1, y1)]
        while seg[-1] != (x0, y0):
            seg.append(prev[seg[-1]])
        seg.reverse()
        out += seg if not out else seg[1:]
    # thin to every 2nd point and smooth slightly
    pts2 = out[::2] + [out[-1]]
    sm = [pts2[0]] + [((a[0] + 2 * b[0] + c[0]) / 4, (a[1] + 2 * b[1] + c[1]) / 4) for a, b, c in zip(pts2, pts2[1:], pts2[2:])] + [pts2[-1]]
    return [[round(x, 1), round(y, 1)] for x, y in sm]


ROADS = [
    {"id": "R1", "name": "ถนนสายหลัก (ทางหลวงชนบท)", "kind": "main", "pts": route([(372, 383), (330, 300), (300, 255), (290, 215), (300, 150), (330, 121)])},
    {"id": "R2", "name": "ถนนเข้าหุบ (หมู่ 2)", "kind": "local", "pts": route([(292, 245), (255, 243), (215, 238), (175, 236), (140, 226)])},
    {"id": "R3", "name": "ถนนเลียบควน (หมู่ 3)", "kind": "local", "pts": route([(300, 262), (272, 280), (257, 300), (253, 328), (257, 352)])},
    {"id": "R4", "name": "ถนนทุ่งเสม็ด (หมู่ 4)", "kind": "local", "pts": route([(325, 292), (350, 300), (365, 330)])},
    {"id": "R5", "name": "ถนนขึ้นที่ทำการ อบต.", "kind": "local", "pts": route([(300, 240), (345, 238)])},
]


def road_cells():
    m = np.zeros((N, N), bool)
    for r in ROADS:
        for (x, y), (x2, y2) in zip(r["pts"], r["pts"][1:]):
            for t in np.linspace(0, 1, 6):
                m[int(round(y + (y2 - y) * t)), int(round(x + (x2 - x) * t))] = True
    return m


RC = road_cells()
NEAR_ROAD = ndimage.binary_dilation(RC, iterations=4) & ~RC

# bridges = road crossing a stream with a large catchment
BRIDGES = []
for r in ROADS:
    for x, y in r["pts"]:
        xi, yi = int(round(x)), int(round(y))
        if (ACC[max(0, yi - 1):yi + 2, max(0, xi - 1):xi + 2] > 0.8).any() and all((xi - b["x"]) ** 2 + (yi - b["y"]) ** 2 > 400 for b in BRIDGES):
            BRIDGES.append({"x": xi, "y": yi, "road": r["id"], "catch_km2": round(float(ACC[max(0, yi - 1):yi + 2, max(0, xi - 1):xi + 2].max()), 1)})

BRIDGE_NAMES = ["สะพานทุ่งใต้", "สะพานปากห้วย", "สะพานคลองเหนือ", "สะพานประปา", "สะพานในหุบ", "สะพานหัวหุบ", "สะพานทุ่งเสม็ด 1", "สะพานทุ่งเสม็ด 2"]
for i, b in enumerate(BRIDGES):
    b["id"] = f"B{i + 1}"; b["name"] = BRIDGE_NAMES[i] if i < len(BRIDGE_NAMES) else f"สะพาน {i + 1}"

# ---------------------------------------------------------------- facilities
def fac(id_, kind, name, anchor, r, ok, **kw):
    x, y = find_site(*anchor, r, ok)
    return {"id": id_, "kind": kind, "name": name, "x": x, "y": y, **kw}


FAC = [
    fac("F1", "hospital", "รพ.สต.ฮอนกฮูก", (288, 268), 14, lambda x, y: flat(x, y) and 3.2 <= HAND[y, x] <= 4.6 and LSNEAR[y, x] < .4,
        info="เจ้าหน้าที่ 5 คน (พยาบาลวิชาชีพ 2, นักวิชาการสาธารณสุข 2, แพทย์แผนไทย 1) | ตู้เย็นวัคซีน 1 ตู้ ไม่มีเครื่องปั่นไฟ | รถกู้ชีพ อบต. 1 คัน | ยาและเวชภัณฑ์เก็บไว้ชั้นล่าง"),
    fac("F2", "school", "โรงเรียนบ้านปากห้วย", (276, 252), 12, lambda x, y: flat(x, y) and 2.0 <= HAND[y, x] <= 2.9,
        info="นักเรียนอนุบาล–ป.6 จำนวน 142 คน ครู 9 คน | อาคารเรียนชั้นเดียว 1 หลัง, อาคาร 2 ชั้น 1 หลัง | มีห้องน้ำ 12 ห้อง, ถังเก็บน้ำฝน"),
    fac("F3", "childcare", "ศูนย์พัฒนาเด็กเล็ก อบต.ฮอนกฮูก", (258, 256), 12, lambda x, y: flat(x, y) and 0.5 <= HAND[y, x] <= 1.4,
        info="เด็กอายุ 2–5 ปี 38 คน ครูผู้ดูแล 3 คน | อาคารชั้นเดียวติดพื้น | ท่วมเกือบทุกปี ต้องปิดศูนย์ 1–3 สัปดาห์"),
    fac("F4", "temple", "วัดควนนกฮูก (ศูนย์อพยพหลัก)", (296, 280), 14, lambda x, y: flat(x, y, 5) and HAND[y, x] > 7 and LSNEAR[y, x] < .3,
        info="ศาลาการเปรียญ รับคนได้ ~250 คน | ห้องน้ำ 8 ห้อง | บ่อน้ำตื้น 1 บ่อ | ไม่มีห้องแยกสำหรับผู้ป่วย/แม่และเด็ก"),
    fac("F5", "office", "ที่ทำการ อบต.ฮอนกฮูก / ศาลาอเนกประสงค์ (ศูนย์อพยพสำรอง)", (345, 238), 14, lambda x, y: flat(x, y, 5) and HAND[y, x] > 7,
        info="ศูนย์บัญชาการเหตุการณ์ (EOC) ของตำบล | ศาลารับคนได้ ~120 คน | มีเครื่องปั่นไฟ 1 เครื่อง | เรือท้องแบน 2 ลำ"),
    fac("F6", "mosque", "มัสยิดนูรุลฮูดา (บาลาเซาะ)", (345, 305), 12, lambda x, y: flat(x, y) and 1.6 <= HAND[y, x] <= 2.8,
        info="ศูนย์รวมชาวบ้านหมู่ 4 | อาคารยกพื้นเล็กน้อย | ใช้เป็นจุดพักคอยชั่วคราวได้ ~60 คน"),
    fac("F7", "water", "ประปาหมู่บ้าน (หอถังสูง + บ่อสูบ)", (266, 240), 10, lambda x, y: flat(x, y) and HAND[y, x] <= 1.2,
        info="สูบน้ำจากคลองฮอนกฮูก ผ่านถังกรองทราย จ่าย หมู่ 1, 2, 4 | ตู้ควบคุมไฟฟ้าอยู่ระดับพื้นดิน"),
    fac("F8", "market", "ตลาดนัด / ร้านค้าชุมชน", (296, 236), 10, lambda x, y: flat(x, y) and 1.0 <= HAND[y, x] <= 2.5,
        info="ร้านค้า 6 ร้าน ตลาดนัดวันพุธ–เสาร์ | ร้านขายยา 1 ร้าน"),
    fac("F9", "gauge", "จุดวัดระดับน้ำ / หอกระจายข่าว", (252, 242), 8, lambda x, y: HAND[y, x] <= 1 and SLOPE[y, x] < 10,
        info="ไม้วัดระดับน้ำ 3 สี (เขียว/เหลือง/แดง) + หอกระจายข่าว | เครื่องวัดฝนอาสาสมัคร (มิสเตอร์เตือนภัย) อยู่บ้านหมู่ 2"),
]

# ---------------------------------------------------------------- households
VILLAGES = [
    {"moo": 1, "name": "บ้านปากห้วย", "n": 34, "box": (240, 228, 300, 262), "desc": "ชุมชนปากหุบ ตรงจุดที่คลองไหลออกจากภูเขา เป็นศูนย์กลางตำบล มีทั้งตลาด โรงเรียน ประปา"},
    {"moo": 2, "name": "บ้านในหุบ", "n": 26, "box": (140, 222, 238, 252), "desc": "บ้านเรียงตามคลองในหุบเขา ทำสวนยาง สวนผลไม้บนเนิน ทางเข้าออกมีเส้นเดียว"},
    {"moo": 3, "name": "บ้านเชิงควน", "n": 24, "box": (244, 268, 272, 352), "desc": "บ้านเรียงตามเชิงควน (เนินเขาเตี้ย) ด้านหลังเป็นสวนยางบนลาดชัน"},
    {"moo": 4, "name": "บ้านทุ่งเสม็ด", "n": 36, "box": (305, 268, 372, 340), "desc": "ทุ่งนาและที่ลุ่ม น้ำท่วมขังนาน ชาวไทยพุทธและมุสลิมอยู่ร่วมกัน เลี้ยงวัว เป็ด"},
]

taken = np.zeros((N, N), bool)
for f in FAC:
    taken[max(0, f["y"] - 2):f["y"] + 3, max(0, f["x"] - 2):f["x"] + 3] = True

HH = []
for v in VILLAGES:
    x0, y0, x1, y1 = v["box"]
    cand = [(x, y) for y in range(y0, y1) for x in range(x0, x1)
            if NEAR_ROAD[y, x] and SLOPE[y, x] < 16 and not STREAM[y, x] and not taken[y, x] and POND[y, x] < 1.5]
    rng.shuffle(cand)
    k = 0
    for x, y in cand:
        if k >= v["n"]:
            break
        if taken[y, x]:
            continue
        taken[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = True
        k += 1
        HH.append({"moo": v["moo"], "x": x, "y": y})
    v["placed"] = k

# ---------------------------------------------------------------- household attributes (seeded, fictional)
HOUSE = ["บ้านชั้นเดียวติดดิน", "บ้านยกใต้ถุนสูง", "บ้านสองชั้น (ล่างปูน บนไม้)", "บ้านไม้ชั้นเดียว"]
WATER = ["ประปาหมู่บ้าน", "บ่อน้ำตื้น", "น้ำฝน + ประปา", "บ่อบาดาล"]
JOB = ["สวนยาง", "สวนผลไม้", "ทำนา", "รับจ้างทั่วไป", "ค้าขาย", "เลี้ยงสัตว์"]
for i, h in enumerate(sorted(HH, key=lambda h: (h["moo"], h["y"], h["x"]))):
    x, y = h["x"], h["y"]
    h["id"] = f"{h['moo']}-{i + 1:03d}"
    h["no"] = f"{rng.randint(1, 160)}/{h['moo']}"
    size = rng.choice([1, 2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 7])
    elderly = sum(rng.random() < .28 for _ in range(size))
    kids = sum(rng.random() < .1 for _ in range(size))
    h.update(members=size, elderly=elderly, under5=kids,
             bedridden=int(elderly > 0 and rng.random() < .12), disabled=int(rng.random() < .07),
             pregnant=int(size > 1 and rng.random() < .05), ncd=sum(rng.random() < .22 for _ in range(min(size, elderly + 1))),
             dialysis=0, psych=int(rng.random() < .03), house=rng.choice(HOUSE), water=rng.choice(WATER), job=rng.choice(JOB),
             livestock=rng.random() < (.45 if h["moo"] == 4 else .15))
    # hazard exposure from real terrain
    h["hand"] = round(float(HAND[y, x]), 1)
    h["elev"] = round(float(DEM[y, x]), 1)
    h["flood"] = next((k for k, L in LEVELS.items() if HAND[y, x] <= L), "none")
    h["flash"] = bool(FLASH[max(0, y - 2):y + 3, max(0, x - 2):x + 3].any())
    h["landslide"] = round(float(LSNEAR[y, x]), 2)
    h["pond"] = round(float(POND[y, x]), 1)

# story characters: pin key vulnerable people onto households with matching exposure
def pick(pred, **attrs):
    c = [h for h in HH if pred(h) and "story" not in h]
    h = max(c, key=lambda h: h["landslide"]) if attrs.get("_by") == "ls" else rng.choice(c)
    attrs.pop("_by", None)
    h.update(attrs); return h

pick(lambda h: h["moo"] == 2 and h["flash"], story="ยายเอียด อายุ 84 ปี ติดเตียง อยู่กับหลานชายวัย 14 ปี บ้านไม้ชั้นเดียวริมคลอง", elderly=1, bedridden=1, members=2, house="บ้านไม้ชั้นเดียว")
pick(lambda h: h["moo"] == 3, _by="ls", story="บ้านน้องฝ้าย หญิงตั้งครรภ์ 37 สัปดาห์ (ครรภ์แรก) สามีกรีดยางกลางคืน บ้านอยู่ชิดเชิงควนหลังสวนยาง", pregnant=1, members=3)
pick(lambda h: h["moo"] == 4 and h["flood"] == "yearly", story="ลุงเพิ่ม อายุ 66 ปี ไตวายเรื้อรัง ฟอกเลือดที่ รพ.อำเภอ สัปดาห์ละ 2 ครั้ง (อังคาร–ศุกร์) และเป็นเบาหวาน", dialysis=1, ncd=2, elderly=1)
pick(lambda h: h["moo"] == 4 and h["flood"] in ("yearly", "heavy"), story="บังหมาด อายุ 58 ปี เบาหวานฉีดอินซูลิน ตู้เย็นที่บ้านอยู่ชั้นล่าง เลี้ยงวัว 6 ตัว", ncd=1, livestock=True)
pick(lambda h: h["moo"] == 1 and h["flood"] in ("yearly", "heavy"), story="ป้าจวง อายุ 71 ปี ใช้เครื่องผลิตออกซิเจน (ปอดอุดกั้นเรื้อรัง) ต้องใช้ไฟฟ้าตลอด", elderly=1, ncd=1)
pick(lambda h: h["moo"] == 2, story="นายเดช อายุ 45 ปี ผู้ป่วยจิตเวช (โรคจิตเภท) รับยาฉีดทุกเดือนที่ รพ.สต. อาศัยกับแม่อายุ 76 ปี", psych=1, elderly=1)
pick(lambda h: h["moo"] == 1, story="บ้านอสม.ศรี (ประธาน อสม.ตำบล) มีวิทยุสื่อสาร รู้จักทุกบ้านที่มีคนป่วยติดเตียง", members=4)
pick(lambda h: h["moo"] == 2 and not h["flash"], story="บ้านลุงหมี มิสเตอร์เตือนภัย (อาสาวัดปริมาณฝน) มีเครื่องวัดฝนหน้าบ้าน", members=3)

# story stage 5: the landslide hits the three Moo 3 houses closest to the steepest hollows (not the story households)
for h in sorted((h for h in HH if h["moo"] == 3 and "story" not in h), key=lambda h: -h["landslide"])[:3]:
    h["hit"] = True

# ---------------------------------------------------------------- evacuation routes (to temple / อบต.)
TEMPLE, OFFICE = FAC[3], FAC[4]
EVAC = [
    {"from": "หมู่ 2", "to": "F4", "pts": route([(190, 238), (255, 243), (292, 250), (TEMPLE["x"], TEMPLE["y"])], water_pen=200)},
    {"from": "หมู่ 1", "to": "F5", "pts": route([(270, 248), (300, 240), (OFFICE["x"], OFFICE["y"])], water_pen=200)},
    {"from": "หมู่ 3", "to": "F4", "pts": route([(264, 330), (270, 300), (TEMPLE["x"], TEMPLE["y"])], water_pen=200)},
    {"from": "หมู่ 4", "to": "F4", "pts": route([(345, 315), (325, 292), (TEMPLE["x"], TEMPLE["y"])], water_pen=200)},
]

# facility exposure
for f in FAC:
    x, y = f["x"], f["y"]
    f["hand"] = round(float(HAND[y, x]), 1); f["elev"] = round(float(DEM[y, x]), 1)
    f["flood"] = next((k for k, L in LEVELS.items() if HAND[y, x] <= L), "none")
    f["flash"] = bool(FLASH[max(0, y - 2):y + 3, max(0, x - 2):x + 3].any())
    f["landslide"] = round(float(LSNEAR[y, x]), 2)

out = {"meta": META, "levels": LEVELS, "villages": VILLAGES, "facilities": FAC, "households": HH,
       "roads": ROADS, "bridges": BRIDGES, "evac": EVAC}
json.dump(out, open("data/village.json", "w"), ensure_ascii=False, indent=1, default=lambda o: bool(o) if isinstance(o, np.bool_) else float(o))
np.save("data/flash.npy", FLASH)
print({v["name"]: v["placed"] for v in VILLAGES}, "bridges", BRIDGES)
for f in FAC:
    print(f["id"], f["name"][:20], f["x"], f["y"], f["hand"], f["flood"], f["flash"], f["landslide"])
import collections
print(collections.Counter((h["moo"], h["flood"]) for h in HH))
print("flash", sum(h["flash"] for h in HH), "ls>.6", sum(h["landslide"] > .6 for h in HH))
