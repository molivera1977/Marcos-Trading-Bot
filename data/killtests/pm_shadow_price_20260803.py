"""PREMARKET SHADOW STUDY (registered 8/3, verdict rules frozen BEFORE results):
price every premarket_shadow_entry 7/28-7/31 under today's stack.

Model (declared): enter at fire price at the first 10s bar at/after fire time; exit at the STOP
level on the first bar whose low touches it (perfect fill — optimistic side), else forced flat at
the last bar before 09:25 (the PRE_FLAT_HHMM rule). No partials/trailing (live PRE trades do
scale — this prices the ENTRY DECISION, not the full exit engine). No spread cost modeled
(task #12) — premarket spreads are the worst case, so POSITIVE results here are UPPER BOUNDS.
Today's floor applied: governed lanes (not zone_flip/hidden_entry/flat_top) with width <4% would
not trade today -> cohort "floor_blocked_anyway". Sizing chain: width 4-5% -> $20 risk,
5-6% -> $25, >=6% -> $30 (exempt lanes <4% -> $20).

VERDICT RULES: lane_not_premkt mean>=+$5/trade @ n>=15 & cheap fails -> shadow-to-live grade
candidate; premkt_thin mean>=+$5 @ n>=10 -> floor recalibration candidate; else limits stand.
"""
import json, pathlib, collections, sys, datetime
import harness

rows = json.load(open("/private/tmp/claude-501/-Users-marcosolivera-Desktop-website-data/add2ac85-fd80-47f7-b583-bda802f0544d/scratchpad/pm_shadow.json"))
EXEMPT = {"zone_flip", "hidden_entry", "flat_top"}
PRE_LANES = {"hidden_entry", "vwap_reclaim"}

def reason(r):
    w = r.get("why") or r.get("_pm_why")
    if w: return w
    # 7/28 rows predate the reason stamp — re-derive: lane whitelist is the only gate that
    # applied to a logged shadow then (thin/cap stamped separately once added)
    return "lane_not_premkt" if r.get("entry_type") not in PRE_LANES else "unknown"

def risk_for(w):
    if w < 5: return 20.0
    if w < 6: return 25.0
    return 30.0

priced, skipped = [], collections.Counter()
for r in rows:
    tk, d = r["ticker"], r["_d"]
    e, s = r.get("price"), r.get("stop")
    if not (e and s and e > s > 0):
        skipped["no_ticket"] += 1; continue
    w = 100 * (e - s) / e
    lane = r.get("entry_type")
    if lane not in EXEMPT and w < 4.0:
        skipped["floor_blocked_anyway"] += 1; continue
    hm = (r.get("time_hm") or "") + ":00"
    b = harness.bars(tk, d)
    if not b:
        skipped["no_bars"] += 1; continue
    walk = [x for x in b if hm <= x[6] < "09:25:00"]
    if len(walk) < 3:
        skipped["no_walk_bars"] += 1; continue
    shares = int(risk_for(w) / (e - s))
    if shares < 1:
        skipped["zero_shares"] += 1; continue
    exit_px, why = None, "flat_0925"
    for x in walk[1:]:
        if x[3] <= s:                      # bar low touches stop
            exit_px, why = s, "stop"; break
    if exit_px is None:
        exit_px = walk[-1][4]
    pnl = round((exit_px - e) * shares, 2)
    priced.append({"d": d, "tk": tk, "lane": lane, "reason": reason(r), "hm": hm[:5],
                   "w": round(w, 2), "shares": shares, "pnl": pnl, "why_exit": why})

print(f"priced={len(priced)} skipped={dict(skipped)}\n")

def agg(g, lab):
    n = len(g)
    if not n: print(f"  {lab:<28} n=0"); return
    p = sum(x["pnl"] for x in g)
    losers = [x["pnl"] for x in g if x["pnl"] < 0]
    cfa = sum(losers) / len(losers) if losers else 0.0
    print(f"  {lab:<28} n={n:>3}  ${p:>8.2f}  mean ${p/n:>6.2f}  win {100*sum(1 for x in g if x['pnl']>0)/n:>3.0f}%  cost/fail ${cfa:>6.2f}")

for reas in ("lane_not_premkt", "premkt_thin", "premkt_capped", "premkt_flatten_window", "unknown"):
    g = [x for x in priced if x["reason"] == reas]
    agg(g, reas)
    for lane, sub in sorted(collections.Counter((x["lane"] for x in g)).items()):
        agg([x for x in g if x["lane"] == lane], f"   {lane}")

json.dump(priced, open(pathlib.Path(__file__).with_name("pm_shadow_priced_20260803.json"), "w"), indent=1)
print("\nrows -> pm_shadow_priced_20260803.json")
