"""IGNITION ENTRY QUALITY (7/30, Marcos: "run it"). Same treatment hidden got.
Every ignition fire 7/27-7/30 (converted + blocked), REAL detector stops reconstructed by replaying
ignition_10s_step over the archived tape, then priced through the honest harness on ignition's
actual ladder (kev25: 50%@1R, 25%@2R, BE after scale 2, 3-min-low trail).
Cuts: extension from open (stamped), LEG-REMAINING (distance below the day's high at entry — the
KSCP/LESL signature), volume surge, room, front-side, time of day."""
import json, urllib.request, sys, pathlib, collections
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
import harness
bot = load_bot()
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9
ET = timezone(timedelta(hours=-4))
DAYS = ("2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30")

# 1) collect stamped fires
stamped = []
for d in DAYS:
    rows = (json.load(urllib.request.urlopen(
        f"{harness.U}/api/decisions_archive?date={d}&limit=50000", timeout=30)).get("rows") or [])
    for r in rows:
        if r.get("status") == "triggered_ignition":
            stamped.append({"d": d, "tk": r.get("ticker"), "t": str(r.get("recorded_at"))[11:19],
                            "px": r.get("price"), "ext": r.get("ext_pct"), "volx": r.get("volx"),
                            "room": r.get("room_rr"), "front": r.get("front_side")})
print(f"stamped ignition fires: {len(stamped)}")

# 2) replay the detector per (ticker, day) once; index its fires by time
det = {}
for key in {(f["tk"], f["d"]) for f in stamped}:
    tk, d = key
    b = harness.bars(tk, d)
    if not b: continue
    bot._ig10_st.pop(tk, None)
    out = []
    for i, bar in enumerate(b):
        fire = bot.ignition_10s_step(tk, [bar[:6]])
        if fire:
            out.append((bar[6], i, fire))
    det[key] = out

# 3) match, grade
res = []
for f in stamped:
    cand = det.get((f["tk"], f["d"])) or []
    best = None
    for hm, i, fire in cand:
        dt = abs((datetime.strptime(hm, "%H:%M:%S") - datetime.strptime(f["t"], "%H:%M:%S")).total_seconds())
        if best is None or dt < best[0]: best = (dt, i, fire)
    if not best or best[0] > 180: continue
    _, i0, fire = best
    b = harness.bars(f["tk"], f["d"])
    e, s = fire["px"], fire["stop"]
    if not (e and s and e > s): continue
    rep = harness.replay(f["tk"], f["d"], e, s, i0=i0)
    if not rep or rep.get("refused"): continue
    # leg-remaining: how far below the RTH high-so-far did we buy?
    rth = [x for x in b[:i0 + 1] if x[6] >= "09:30:00"]
    hi = max((x[2] for x in rth), default=e)
    f.update({"pnl": rep["pnl"], "below_hi": 100 * (e - hi) / hi if hi else 0,
              "width": 100 * (e - s) / e, "hm": int(f["t"][:2]) * 60 + int(f["t"][3:5])})
    res.append(f)

print(f"graded: {len(res)}   TOTAL ${sum(f['pnl'] for f in res):+.2f}   ${sum(f['pnl'] for f in res)/max(len(res),1):+.2f}/fire\n")

def cut(name, keyfn, edges):
    print(f"== {name}")
    print(f"   {'bucket':14}{'n':>5}{'total $':>11}{'$/fire':>9}{'wins':>7}")
    for lo, hi, lbl in edges:
        g = [f for f in res if keyfn(f) is not None and lo <= keyfn(f) < hi]
        if len(g) < 4: continue
        t = sum(f["pnl"] for f in g)
        print(f"   {lbl:14}{len(g):5}{t:11.2f}{t/len(g):9.2f}{sum(1 for f in g if f['pnl']>0):7}")
    print()

cut("LEG REMAINING — how far BELOW the day's high we bought",
    lambda f: f.get("below_hi"),
    [(-999,-10,"<-10%"),(-10,-5,"-10..-5%"),(-5,-2,"-5..-2%"),(-2,-1,"-2..-1%"),(-1,-0.3,"-1..-0.3%"),(-0.3,99,"at the high")])
cut("EXTENSION from the session open (ext_pct)",
    lambda f: f.get("ext"),
    [(-999,0,"<0%"),(0,3,"0-3%"),(3,6,"3-6%"),(6,10,"6-10%"),(10,999,"10%+")])
cut("VOLUME SURGE (volx)",
    lambda f: f.get("volx"),
    [(0,3,"<3x"),(3,5,"3-5x"),(5,10,"5-10x"),(10,999,"10x+")])
cut("ROOM (room_rr)",
    lambda f: f.get("room"),
    [(0,0.5,"<0.5"),(0.5,1,"0.5-1"),(1,2,"1-2"),(2,999,"2+")])
cut("TIME OF DAY",
    lambda f: f.get("hm"),
    [(0,570,"pre-9:30"),(570,585,"9:30-9:45"),(585,600,"9:45-10:00"),(600,660,"10:00-11:00"),(660,960,"11:00+")])
