"""#27 RUNWAY GRADED-THRESHOLD KILL-TEST (registered 8/4 EOD, rules frozen pre-run;
Marcos: "scale points are not walls but they are levels of resistance until crossed" +
priors 0.5R-to-rung / 1R-to-major; "let the kill test give us guidance").

DOCTRINE UNDER TEST: a mapped level is resistance until crossed. The current gate treats ANY
level inside 1R as a wall (reject). The graded gate takes the trade iff road-to-next-level
>= T, sweeping T; separately, classify each reject's blocking level as MAJOR (break,
next_supply, or within 1c of a whole/half dollar) vs RUNG (intermediate target) and grade the
two classes at their own thresholds (priors: rung 0.5R, major 1.0R).

COHORT: every runway_reject with a priced ticket since the gate shipped (7/31-8/4). SIP 1-min.
SIM: taken at reject price — width-band risk ($20/<5%,$25/5-6%,$30/>=6%), half at +1R
(stop->BE), runner prev-1min-low trail, 15:45 close.
FROZEN VERDICT: a threshold T ships-candidate iff cohort-at-T net >= +$50 vs the gate's $0
AND no single taken trade loses > $35 (one bad fill from a band-priced $30 risk) AND >= 8
trades priced. The rung/major split is REPORTED for Marcos's call (his override stands
regardless — tomorrow experiments either way).
"""
import json, urllib.request, time, datetime, pathlib

V = json.load(open("/tmp/rw.json"))
HDR = {"APCA-API-KEY-ID": V["ALPACA_KEY"], "APCA-API-SECRET-KEY": V["ALPACA_SECRET"]}
U = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-07-31", "2026-08-01", "2026-08-03", "2026-08-04"]

def sip(u):
    r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=HDR), timeout=30))
    time.sleep(0.25); return r

_m = {}
def min1(tk, d):
    if (tk, d) in _m: return _m[(tk, d)]
    try:
        bars = sip(f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min&start={d}T04:00:00-04:00"
                   f"&end={d}T16:00:00-04:00&limit=1000&feed=sip").get("bars") or []
    except Exception: bars = []
    _m[(tk, d)] = [((int(b["t"][11:13])-4)*60+int(b["t"][14:16]), float(b["o"]), float(b["h"]),
                    float(b["l"]), float(b["c"])) for b in bars]
    return _m[(tk, d)]

def replay(bars, i0, e, s):
    w = 100*(e-s)/e; risk = 20 if w < 5 else (25 if w < 6 else 30)
    sh = risk/(e-s); pnl = 0.0; rem = 1.0; sc = False; tr = s
    for j in range(i0, len(bars)):
        m, o, h, l, c = bars[j]
        if m >= 15*60+45: break
        if not sc and h >= e+(e-s): pnl += 0.5*sh*(e-s); rem = 0.5; sc = True; tr = e; continue
        lvl = tr if sc else s
        if l <= lvl: return pnl + rem*sh*(lvl-e)
        if sc and j > i0: tr = max(tr, bars[j-1][3])
    return pnl + (rem*sh*(bars[-1][4]-e) if bars else 0)

levels = {d: (json.load(urllib.request.urlopen(f"{U}/api/kev_watchlist?date={d}", timeout=30)).get("levels") or {}) for d in DAYS}

def classify(tk, d, target):
    """MAJOR = break/next_supply match, or whole/half-dollar within 1c. Else RUNG."""
    rec = levels[d].get(tk) or {}
    for k in ("break", "next_supply"):
        v = rec.get(k)
        try:
            if v is not None and abs(float(v)-target) < 0.005: return "MAJOR"
        except Exception: pass
    frac = target - int(target)
    if min(abs(frac-0.0), abs(frac-0.5), abs(frac-1.0)) < 0.011: return "MAJOR"
    return "RUNG"

rows = []
for d in DAYS:
    try:
        ra = json.load(urllib.request.urlopen(f"{U}/api/decisions_archive?date={d}&limit=50000", timeout=60)).get("rows") or []
    except Exception: continue
    for r in ra:
        if r.get("status") != "runway_reject": continue
        tk = r["ticker"]; e = float(r.get("price") or 0); s = float(r.get("stop") or 0)
        tgt = float(r.get("target") or 0); rr = float(r.get("runway_rr") or 0)
        if not (e > s > 0 and tgt > 0): continue
        t = str(r.get("time") or "")
        try:
            dt_ = datetime.datetime.strptime(t[:8], "%I:%M:%S")
            hh = dt_.hour % 12 + (12 if t.endswith("PM") else 0)
        except Exception: continue
        bars = min1(tk, d)
        idx = next((j for j, b in enumerate(bars) if b[0] >= hh*60+dt_.minute), None)
        if idx is None: continue
        pnl = replay(bars, idx, e, s)
        rows.append({"d": d, "t": f"{hh:02d}:{dt_.minute:02d}", "tk": tk, "lane": r.get("machine"),
                     "rr": round(rr, 2), "cls": classify(tk, d, tgt), "target": tgt, "pnl": round(pnl, 2)})

print(f"priced runway rejects since gate shipped: {len(rows)}\n")
for x in sorted(rows, key=lambda z: (z["d"], z["t"])):
    print(f"  {x['d']} {x['t']} {x['tk']:<6} {str(x['lane']):<13} road {x['rr']:>4.2f}R to ${x['target']:<7} {x['cls']:<5} ${x['pnl']:>+8.2f}")

print("\n== THRESHOLD SWEEP (take iff roadR >= T; gate today = take none = $0) ==")
for T in (0.2, 0.3, 0.4, 0.5, 0.6, 0.75):
    g = [x for x in rows if x["rr"] >= T]
    p = sum(x["pnl"] for x in g); w = sum(1 for x in g if x["pnl"] > 0)
    worst = min((x["pnl"] for x in g), default=0)
    print(f"  T={T:<5} takes {len(g):>2}  ${p:>+8.2f}  win {100*w/len(g) if g else 0:.0f}%  worst ${worst:+.2f}")

print("\n== RUNG vs MAJOR at Marcos's priors (rung>=0.5R, major>=1.0R... majors all rejected here) ==")
for cls in ("RUNG", "MAJOR"):
    g = [x for x in rows if x["cls"] == cls]
    p = sum(x["pnl"] for x in g)
    print(f"  {cls}: n={len(g)}  all-taken ${p:+.2f}  | taken at prior "
          f"({0.5 if cls=='RUNG' else 1.0}R): ${sum(x['pnl'] for x in g if x['rr'] >= (0.5 if cls=='RUNG' else 1.0)):+.2f} "
          f"(n={sum(1 for x in g if x['rr'] >= (0.5 if cls=='RUNG' else 1.0))})")

best = None
for T in (0.2, 0.3, 0.4, 0.5, 0.6, 0.75):
    g = [x for x in rows if x["rr"] >= T]
    p = sum(x["pnl"] for x in g); worst = min((x["pnl"] for x in g), default=0)
    ok = p >= 50 and worst >= -35 and len(rows) >= 8
    if ok and (best is None or p > best[1]): best = (T, p)
print(f"\nFROZEN VERDICT: {'SHIP-CANDIDATE T='+str(best[0])+f' (${best[1]:+.2f})' if best else 'NOT MET on frozen rules'} "
      f"— Marcos override for tomorrow stands either way (his call, on record)")
json.dump(rows, open(pathlib.Path(__file__).with_name("runway_graded_rows_20260804.json"), "w"), indent=1)
