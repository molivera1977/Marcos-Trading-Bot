"""BREAK-PRINT vs RETEST ENTRY (8/6 ~12:2x, rules frozen pre-run; Marcos: "run the test now";
task #16). Q: breakout lanes (flat_top / ignition / orb) buy the break PRINT — top-of-bar by
construction (PAVS 9:44, MGRX 9:45, CELZ 12:14 specimens). Would entering on the FIRST RETEST
(price pulling back D% below the actual fill) pay better after the misses it causes?
ARMS per real era trade: A = actual recorded P&L. R(D) for D in {0.5%, 1.0%, 1.5%}: wait up
to 15 min after the real entry for a 10s bar LOW <= fill*(1-D); enter there, SAME stop
(entry - risk_per_share, i.e. the original stop price), SAME engine (half at +1R of the
ORIGINAL risk, stop->BE, rolling prev-minute-low trail); if no retest within 15 min the trade
is MISSED (P&L 0 — the cost of patience). Dollars with the record's real share count.
FROZEN VERDICT: a depth ships-candidate iff total beats A by >= $75 AND misses <= 30% of
trades AND its worst single-trade degradation <= $40. Else -> Friday table as evidence.
"""
import json, urllib.request, urllib.parse, datetime, pathlib
U = "https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u, timeout=60))
_b = {}
def bars10(tk, d):
    if (tk, d) in _b: return _b[(tk, d)]
    try:
        r = get(f"{U}/api/bars?date={d}&ticker={urllib.parse.quote(tk)}~ALP10S").get("bars") or []
    except Exception:
        r = []
    out = []
    for x in r:
        try:
            ts = str(x.get("time"))[11:19]
            sec = int(ts[:2]) * 3600 + int(ts[3:5]) * 60 + int(ts[6:8])
            out.append((sec, float(x.get("high") or 0), float(x.get("low") or 0), float(x.get("close") or 0)))
        except Exception: continue
    _b[(tk, d)] = out
    return out
def sim(B, i0, e, stop0, r1):
    pnl = 0.0; rem = 1.0; sc = False; stop = stop0; lows = []
    for j in range(i0, len(B)):
        _, h, l, c = B[j]
        if not sc and h >= e + r1:
            pnl += 0.5 * r1; rem = 0.5; sc = True; stop = e; continue
        if sc:
            lows.append(l)
            if len(lows) > 6: lows.pop(0)
            if len(lows) == 6: stop = max(stop, min(lows))
        if l <= stop:
            return pnl + rem * (max(stop, l) - e)
    return pnl + (rem * (B[-1][3] - e) if B else 0)
trades = [t for t in get(U + "/api/trades")["trades"]
          if str(t.get("date") or "") >= "2026-07-14" and t.get("entry_ts_utc")
          and t.get("entry_session") != "PRE"
          and str(t.get("entry_type")) in ("flat_top", "ignition", "orb")]
DEPTHS = (0.005, 0.01, 0.015)
tot = {"A": 0.0}; miss = {d: 0 for d in DEPTHS}
for d_ in DEPTHS: tot[d_] = 0.0
n = 0; worst = {d: 0.0 for d in DEPTHS}
for t in trades:
    d = t["date"]; tk = t["ticker"]
    e = float(t.get("entry") or 0); rps = float(t.get("risk_per_share") or 0); sh = int(t.get("shares") or 0)
    if not (e > 0 and rps > 0 and sh > 0): continue
    dt_ = datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z", "+00:00"))
    es = dt_.hour * 3600 + dt_.minute * 60 + dt_.second
    B = bars10(tk, d)
    i0 = next((j for j, x in enumerate(B) if x[0] >= es), None)
    if i0 is None or len(B) < 30: continue
    n += 1
    a = float(t.get("pnl") or 0)
    tot["A"] += a
    for D in DEPTHS:
        lvl = e * (1 - D)
        ir = next((j for j in range(i0, len(B)) if B[j][0] <= es + 900 and B[j][2] <= lvl), None)
        if ir is None:
            miss[D] += 1; continue
        p = sim(B, ir, lvl, e - rps, rps) * sh   # same stop PRICE (e-rps), 1R = original rps
        tot[D] += p
        worst[D] = max(worst[D], a - p)
print(f"breakout-lane era trades replayed: {n}\n")
print(f"ACTUAL (break print): ${tot['A']:+9.2f}")
for D in DEPTHS:
    ok = (tot[D] - tot["A"]) >= 75 and miss[D] / max(n, 1) <= 0.30 and worst[D] <= 40
    print(f"RETEST {D*100:.1f}%: ${tot[D]:+9.2f}  (missed {miss[D]}/{n} = {100*miss[D]/max(n,1):.0f}%)  "
          f"worst-single-degradation ${worst[D]:.2f}  {'SHIP-CANDIDATE' if ok else 'NOT MET'}")
