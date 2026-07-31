"""HIDDEN ENTRY QUALITY (7/30, Marcos: "I dont care about frequency, i care more about quality of each").
Every hidden fire in the archive — converted OR shadow — graded against what the tape did NEXT.
Outcome = did price reach +1R BEFORE the fire's own stop (sequence respected, the mistake I made
on the 9-trade cut). Then: which entry-time stamp separates the winners?"""
import json, urllib.request, statistics as st, collections
from datetime import datetime, timedelta, timezone
import harness
ET = timezone(timedelta(hours=-4))
DAYS = ("2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30")

fires = []
for d in DAYS:
    rows = (json.load(urllib.request.urlopen(
        f"{harness.U}/api/decisions_archive?date={d}&limit=50000", timeout=30)).get("rows") or [])
    for r in rows:
        if r.get("status") != "hidden_shadow_fire":
            continue
        px, stop = r.get("price"), r.get("stop")
        if not (px and stop and px > stop):
            continue
        fires.append({"d": d, "tk": r.get("ticker"), "t": str(r.get("recorded_at"))[11:19],
                      "px": float(px), "stop": float(stop), "ext": r.get("ext_vwap"),
                      "anchor": r.get("anchor"), "seq": r.get("seq")})
print(f"fires collected: {len(fires)}")

graded = []
for f in fires:
    b = harness.bars(f["tk"], f["d"])
    i0 = next((i for i, x in enumerate(b) if x[6] >= f["t"]), None)
    if i0 is None:
        continue
    R = f["px"] - f["stop"]; t1 = f["px"] + R; t2 = f["px"] + 2 * R
    hit1 = hit2 = False; res = "died"
    for j in range(i0, len(b)):
        k, o, h, l, c, v, hm = b[j]
        if hm >= "15:45:00": break
        if l <= f["stop"]:
            break
        if h >= t2: hit2 = True; hit1 = True; res = "2R+"; break
        if h >= t1 and not hit1: hit1 = True; res = "1R"
    f["res"] = res; f["hit1"] = hit1; f["hit2"] = hit2
    f["width"] = 100 * R / f["px"]
    graded.append(f)

n = len(graded); w1 = sum(1 for f in graded if f["hit1"]); w2 = sum(1 for f in graded if f["hit2"])
print(f"graded: {n}   reached 1R before stop: {w1} ({100*w1/max(n,1):.0f}%)   reached 2R: {w2} ({100*w2/max(n,1):.0f}%)\n")

def cut(name, keyfn, edges):
    print(f"== by {name}")
    print(f"   {'bucket':16}{'n':>5}{'hit 1R':>9}{'hit 2R':>9}")
    for lo, hi in edges:
        g = [f for f in graded if keyfn(f) is not None and lo <= keyfn(f) < hi]
        if len(g) < 5: continue
        a = sum(1 for f in g if f["hit1"]); b2 = sum(1 for f in g if f["hit2"])
        print(f"   {f'{lo} to {hi}':16}{len(g):5}{100*a/len(g):8.0f}%{100*b2/len(g):8.0f}%")
    print()

cut("EXTENSION above VWAP at entry (ext_vwap %)", lambda f: f.get("ext"),
    [(-99, 0), (0, 1), (1, 2), (2, 3), (3, 5), (5, 10), (10, 999)])
cut("STOP WIDTH %", lambda f: f.get("width"),
    [(0, 4), (4, 5), (5, 6), (6, 8), (8, 15), (15, 999)])
cut("SEQ (which fire on that name that day)", lambda f: f.get("seq"),
    [(0, 1), (1, 2), (2, 3), (3, 6), (6, 99)])
def hhmm(f):
    try: return int(f["t"][:2]) * 60 + int(f["t"][3:5])
    except Exception: return None
cut("TIME OF DAY (minutes past midnight ET)", hhmm,
    [(0, 570), (570, 585), (585, 600), (600, 630), (630, 720), (720, 960)])
