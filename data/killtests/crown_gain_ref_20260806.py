"""CROWN GAIN REFERENCE KILL TEST (registered 8/6 ~00:2x ET, rules frozen pre-run; Marcos:
"the 40% jump should be from the open of pre-market... let's see a kill test").
QUESTION: should the crown's gain leg measure day gain vs PRIOR OFFICIAL CLOSE (live def —
blind to after-hours repricing; day-two YXT needs $32.80 while trading $13.50) or vs the
PREMARKET OPEN (first 4am SIP print — Marcos's mental model)?
METHOD: every era trade (7/14+ entry stamps) gets BOTH gains at its entry:
  old = stamped day_gain_at_entry (vs prior close, as traded)
  new = 100*(entry / first-premarket-print - 1)  [first 1-min SIP bar >= 04:00 that day;
        names with no premarket tape fall back to old (no premarket = no repricing signal)]
Quadrant the trades by (old>=40, new>=40) and report count + total/mean ACTUAL P&L per
quadrant. The interesting cells are the DISAGREEMENTS: names only the new def would crown
(did they give?) and names only the old def crowns (were they duds?).
FROZEN VERDICT: the premarket-open reference is ship-candidate iff BOTH disagreement cells
point its way: new-only mean P&L > 0 AND old-only mean P&L <= 0, each with n >= 3. Any other
pattern -> park on the Friday table with the numbers. WRONG-WHEN: new def is wrong if
gap-down bounce names (new-only crowns) are net losers — that's the bull-trap regime.
CAVEAT: this grades the gain DEFINITION as a selector on real trades; it cannot replay the
ammo×3 counterfactual (what extra fires a crown would have enabled).
"""
import json, urllib.request, urllib.parse, time, datetime, pathlib
V = json.load(open("/tmp/rrp.json"))
HDR = {"APCA-API-KEY-ID": V["ALPACA_KEY"], "APCA-API-SECRET-KEY": V["ALPACA_SECRET"]}
U = "https://zestful-intuition-production-b16a.up.railway.app"
def sip(u):
    r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=HDR), timeout=30)); time.sleep(0.12); return r
_pm = {}
def pm_open(tk, d):
    if (tk, d) in _pm: return _pm[(tk, d)]
    px = None
    try:
        b = sip(f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min&start={d}T04:00:00-04:00&end={d}T09:30:00-04:00&limit=3&feed=sip").get("bars") or []
        if b: px = float(b[0]["o"])
    except Exception:
        px = None
    _pm[(tk, d)] = px
    return px
trades = [t for t in json.load(urllib.request.urlopen(U + "/api/trades", timeout=60))["trades"]
          if str(t.get("date") or "") >= "2026-07-14" and t.get("entry_ts_utc")
          and t.get("day_gain_at_entry") is not None]
quad = {}
rows = []
for t in trades:
    d = t["date"]; tk = t["ticker"]; e = float(t.get("entry") or 0)
    old = float(t.get("day_gain_at_entry") or 0)
    p = pm_open(tk, d)
    new = 100 * (e / p - 1) if (p and p > 0 and e > 0) else old
    q = (old >= 40, new >= 40)
    quad.setdefault(q, []).append(float(t.get("pnl") or 0))
    _qlbl = ("oldY" if q[0] else "oldN") + "/" + ("newY" if q[1] else "newN")
    rows.append({"d": d, "tk": tk, "e": e, "pm_open": p, "old": round(old, 1), "new": round(new, 1),
                 "pnl": float(t.get("pnl") or 0), "quad": _qlbl})
print(f"era trades graded: {len(rows)}\n")
for q, lbl in [((True, True), "BOTH crown (agree)"), ((False, False), "NEITHER (agree)"),
               ((False, True), "NEW-ONLY crown (gap-down bounce class)"), ((True, False), "OLD-ONLY crown (AH-faded class)")]:
    v = quad.get(q, [])
    if v:
        print(f"{lbl:<42} n={len(v):>3}  total ${sum(v):+9.2f}  mean ${sum(v)/len(v):+7.2f}")
    else:
        print(f"{lbl:<42} n=  0")
print("\nDISAGREEMENT trades:")
for x in sorted(rows, key=lambda z: (z["d"], z["tk"])):
    if x["quad"] in ("oldN/newY", "oldY/newN"):
        print(f"  {x['d']} {x['tk']:<6} entry {x['e']:>7.2f} pm_open {str(x['pm_open']):>8} old {x['old']:>7.1f}% new {x['new']:>7.1f}%  pnl {x['pnl']:>+8.2f}  [{x['quad']}]")
no_pm = sum(1 for x in rows if x["pm_open"] is None)
print(f"\nnames with no premarket tape (fell back to old): {no_pm}")
new_only = quad.get((False, True), []); old_only = quad.get((True, False), [])
ok = (len(new_only) >= 3 and sum(new_only)/len(new_only) > 0
      and len(old_only) >= 3 and sum(old_only)/len(old_only) <= 0)
print(f"\nFROZEN VERDICT: {'SHIP-CANDIDATE (premarket-open reference)' if ok else 'NOT MET -> Friday table'}")
json.dump(rows, open(pathlib.Path(__file__).with_name("crown_gain_ref_rows_20260806.json"), "w"), indent=1)
