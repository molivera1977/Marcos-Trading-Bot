"""LEVEL-LADDER EXITS vs R-TIER EXITS (registered 8/4 ~11:40, rules frozen pre-run; Marcos:
"targets being scale points and not walls is huge" -> "run the exit replay now").

This tests the UNBUILT half of SUPPLY_EXIT_DESIGN.md (LOCKED 6/26): rule 3 "trim into strength
at the supply/resistance zones" + rule 4 "trail the stop UP to each cleared level". The built
half (+1R sell half) is KEPT in both engines — it's Kev's risk law.

ENGINE A (current live): 50% off at entry+1R (stop->BE), 25% off at entry+2R, runner trails
prior 1-min low; hard stop; 15:45 close.
ENGINE B (level ladder): 50% off at entry+1R (unchanged), 25% off AT the first map rung above
entry+1R (fallback +2R if no rung), runner stop = highest CLEARED rung (rung counts as cleared
when a 1-min close prints above it) with BE floor; hard stop; 15:45 close.

COHORT: live trades 7/31-8/4 (closed) whose day sheet had >=1 target above entry. SIP 1-min.
FROZEN VERDICT: B ships-candidate iff B_total - A_total >= +$25 AND B wins/ties >=55% of trades
AND max single-trade (A_i - B_i) <= $15. Else -> 8/8 table.
"""
import json, urllib.request, time, datetime, pathlib

V = json.load(open("/tmp/rx.json"))
HDR = {"APCA-API-KEY-ID": V["ALPACA_KEY"], "APCA-API-SECRET-KEY": V["ALPACA_SECRET"]}
U = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-07-31", "2026-08-03", "2026-08-04"]

def sip(url):
    r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=30))
    time.sleep(0.25); return r

_m1 = {}
def min1(tk, day):
    if (tk, day) in _m1: return _m1[(tk, day)]
    try:
        bars = sip(f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min&start={day}T04:00:00-04:00"
                   f"&end={day}T16:00:00-04:00&limit=1000&feed=sip").get("bars") or []
    except Exception: bars = []
    out = [((int(b["t"][11:13])-4)*60+int(b["t"][14:16]), float(b["o"]), float(b["h"]), float(b["l"]), float(b["c"])) for b in bars]
    _m1[(tk, day)] = out; return out

def engine(bars, i0, e, s, sh, rungs, mode):
    """mode A: R-tiers; mode B: level ladder. Returns pnl."""
    R = e - s
    pnl = 0.0; rem = sh; stage = 0; stop = s
    t2 = e + 2*R
    if mode == "B":
        above = [r for r in rungs if r > e + R]
        t2 = above[0] if above else e + 2*R
    cleared = []
    for j in range(i0, len(bars)):
        m, o, h, l, c = bars[j]
        if m >= 15*60+45: break
        if stage == 0 and h >= e + R:
            q = rem // 2; pnl += q * R; rem -= q; stage = 1; stop = e
            continue
        if stage == 1 and h >= t2:
            q = rem // 2; pnl += q * (t2 - e); rem -= q; stage = 2
            continue
        if stage >= 1 and mode in ("B", "H"):
            for r_ in rungs:
                if r_ > e and r_ not in cleared and c > r_:
                    cleared.append(r_)
            if cleared: stop = max(stop, max(cleared))
        if l <= stop:
            return pnl + rem * (stop - e)
        if stage == 2 and mode in ("A", "H") and j > i0:
            stop = max(stop, bars[j-1][3])
    return pnl + (rem * (bars[-1][4] - e) if bars else 0)

trades = [t for t in json.load(urllib.request.urlopen(f"{U}/api/trades", timeout=60))["trades"] if t.get("date") in DAYS]
levels = {d: (json.load(urllib.request.urlopen(f"{U}/api/kev_watchlist?date={d}", timeout=30)).get("levels") or {}) for d in DAYS}
rows = []
for t in trades:
    d, tk = t["date"], t["ticker"]
    e = float(t.get("entry") or 0); s = float(t.get("stop_loss") or 0)
    sh = int(t.get("shares") or 0)
    if not (e > s > 0 and sh > 0): continue
    rec = levels[d].get(tk) or {}
    rungs = sorted(set(float(x) for x in (rec.get("targets") or []) if float(x) > e))
    ns = float(rec.get("next_supply") or 0)
    if ns > e and ns not in rungs: rungs = sorted(set(rungs + [ns]))
    if not rungs: continue
    try:
        dt_ = datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z", "+00:00"))
        fmin = (dt_.hour - 4) * 60 + dt_.minute
    except Exception: continue
    bars = min1(tk, d)
    idx = next((j for j, b in enumerate(bars) if b[0] >= fmin), None)
    if idx is None: continue
    a = engine(bars, idx, e, s, sh, rungs, "A")
    b = engine(bars, idx, e, s, sh, rungs, "B")
    hyb = engine(bars, idx, e, s, sh, rungs, "H")
    rows.append({"d": d, "tk": tk, "lane": t.get("entry_type"), "actual": float(t.get("pnl") or 0),
                 "A": round(a, 2), "B": round(b, 2), "H": round(hyb, 2), "rungs": rungs[:3]})

print(f"trades with map rungs: {len(rows)}\n")
for x in sorted(rows, key=lambda z: (z["d"], z["tk"])):
    tag = "B+" if x["B"] > x["A"] + 0.01 else ("A+" if x["A"] > x["B"] + 0.01 else "==")
    print(f"  {x['d']} {x['tk']:<6} {x['lane']:<13} actual ${x['actual']:>+7.2f} | A ${x['A']:>+8.2f} | B ${x['B']:>+8.2f}  {tag}  rungs {x['rungs']}")
ta = sum(x["A"] for x in rows); tb = sum(x["B"] for x in rows); th = sum(x["H"] for x in rows)
winsH = sum(1 for x in rows if x["H"] >= x["A"] - 0.01)
worstH = max((x["A"] - x["H"] for x in rows), default=0)
print(f"\nENGINE H (hybrid trail): ${th:+.2f}   delta vs A {th-ta:+.2f}   wins/ties {winsH}/{len(rows)} ({100*winsH/len(rows):.0f}%)   worst give-back ${worstH:.2f}")
okH = (th - ta) >= 25 and len(rows) and winsH/len(rows) >= 0.55 and worstH <= 15
print("H vs frozen rule =>", "PASSES (presented for Marcos call — variant #2 disclosure)" if okH else "not met")
wins = sum(1 for x in rows if x["B"] >= x["A"] - 0.01)
worst = max((x["A"] - x["B"] for x in rows), default=0)
print(f"\nENGINE A (R-tiers):     ${ta:+.2f}")
print(f"ENGINE B (level ladder): ${tb:+.2f}   delta {tb-ta:+.2f}")
print(f"B wins/ties: {wins}/{len(rows)} ({100*wins/len(rows):.0f}%)   worst single-trade give-back: ${worst:.2f}")
ok = (tb - ta) >= 25 and len(rows) and wins/len(rows) >= 0.55 and worst <= 15
print("FROZEN VERDICT =>", "SHIP-CANDIDATE tonight (finishes the locked spec)" if ok else "NOT MET — to the 8/8 table")
json.dump(rows, open(pathlib.Path(__file__).with_name("level_exits_rows_20260804.json"), "w"), indent=1)
