"""DEAD-ZONE KILL-TEST (registered 8/3 evening, rules frozen pre-run; Marcos: "we need to do
something about this today").

ZONES at entry, when the day's sheet has a map (break B, last target T) for the ticker:
  pre_break   : entry < B and day-high-before-entry < B   (UPC 8/3 class — the wall not yet broken)
  retest      : entry < B and day-high-before-entry >= B  (protected class: joint grade +$12.67/e)
  in_range    : B <= entry <= T
  past_targets: entry > T                                  (FUSE 8/3 class — road already spent)
  no_map      : no break on sheet (fail-open doctrine, not tested)

VERDICT RULES (frozen): for each of {chart lanes: flat_top/ma_pullback/orb/ema_bounce/dip_rip},
{ignition}, {hidden/reclaim/zone_flip}: a zone BLOCKS tonight for that group iff its bucket is
net negative AND mean <= -$5/trade AND n >= 8. retest NEVER blocks (measured winner). Anything
short of the bar -> Friday with more data.
"""
import json, urllib.request, collections, datetime

U = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31", "2026-08-03"]
CHART = {"flat_top", "ma_pullback", "orb", "ema_bounce", "dip_rip"}
TAPE  = {"hidden_entry", "vwap_reclaim", "zone_flip"}

def get(u): return json.load(urllib.request.urlopen(u, timeout=60))

levels = {d: (get(f"{U}/api/kev_watchlist?date={d}").get("levels") or {}) for d in DAYS}
trades = [t for t in get(f"{U}/api/trades")["trades"] if t.get("date") in DAYS]
print(f"trades in window: {len(trades)}")

barcache = {}
def high_before(d, tk, hm):
    key = (d, tk)
    if key not in barcache:
        try: barcache[key] = get(f"{U}/api/bars?date={d}&ticker={tk}~ALP10S").get("bars") or []
        except Exception: barcache[key] = []
    hs = [float(b.get("high") or b.get("h") or 0) for b in barcache[key]
          if str(b.get("time") or b.get("t") or "")[11:19] < hm]
    return max(hs) if hs else None

rows = []
skip = collections.Counter()
for t in trades:
    d, tk = t["date"], t["ticker"]
    rec = levels[d].get(tk) or {}
    try: B = float(rec.get("break") or 0)
    except Exception: B = 0.0
    tg = []
    try: tg = [float(x) for x in (rec.get("targets") or []) if float(x) > 0]
    except Exception: pass
    e = float(t.get("entry") or 0)
    if e <= 0: skip["no_entry"] += 1; continue
    if B <= 0:
        zone = "no_map"
    else:
        T = max(tg) if tg else None
        try:
            dt_ = datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z", "+00:00"))
            hm = (dt_ - datetime.timedelta(hours=4)).strftime("%H:%M:%S")
        except Exception:
            skip["no_entry_time"] += 1; continue
        if e < B:
            hb = high_before(d, tk, hm)
            zone = "retest" if (hb is not None and hb >= B) else ("pre_break" if hb is not None else "pre_break_nobars")
        elif T is not None and e > T:
            zone = "past_targets"
        else:
            zone = "in_range"
    lane = t.get("entry_type") or "?"
    grp = "chart" if lane in CHART else ("ignition" if lane == "ignition" else "tape")
    rows.append({"d": d, "tk": tk, "lane": lane, "grp": grp, "zone": zone,
                 "pnl": float(t.get("pnl") or 0)})

print(f"bucketed: {len(rows)}  skipped: {dict(skip)}\n")
def agg(g, lab):
    n = len(g)
    if not n: return
    p = sum(x["pnl"] for x in g)
    print(f"  {lab:<28} n={n:>3}  ${p:>8.2f}  mean ${p/n:>7.2f}  win {100*sum(1 for x in g if x['pnl']>0)/n:>3.0f}%")

print("== by zone (all lanes) ==")
for z in ("pre_break", "retest", "in_range", "past_targets", "no_map", "pre_break_nobars"):
    agg([x for x in rows if x["zone"] == z], z)
print("\n== zone x lane-group ==")
verdicts = []
for grp in ("chart", "ignition", "tape"):
    print(f" {grp}:")
    for z in ("pre_break", "retest", "in_range", "past_targets"):
        g = [x for x in rows if x["grp"] == grp and x["zone"] == z]
        agg(g, f"   {z}")
        if z in ("pre_break", "past_targets") and g:
            p = sum(x["pnl"] for x in g); n = len(g)
            if p < 0 and p / n <= -5 and n >= 8:
                verdicts.append((grp, z, n, round(p, 2)))
print("\n== FROZEN-RULE VERDICTS (block tonight) ==")
print(verdicts if verdicts else "NONE meet the bar — goes to Friday")
print("\nper-trade detail (dead zones only):")
for x in rows:
    if x["zone"] in ("pre_break", "past_targets"):
        print(f"  {x['d']} {x['tk']:<6} {x['lane']:<13} {x['zone']:<12} ${x['pnl']:>+8.2f}")
