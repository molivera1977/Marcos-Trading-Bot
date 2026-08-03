"""TWO-TIER SIZING BACKTEST (registered 8/3 before results; Marcos: "I like this two-tier idea")

HYPOTHESIS: trades that convert through FAIL-OPEN IGNORANCE (no marked level -> no runway stamp;
nothing blocked them because nothing was KNOWN) should carry HALF risk; full-stack-informed trades
keep full risk. Sizes DOWN on ignorance, never UP on any refuted quality scalar (room/day-gain/
momentum/extension all refuted; runway MAGNITUDE refuted as slope 8/3 — the AMIX autopsy).

METHOD: live trade records 7/28-7/31 (the stamped era). P&L scales linearly with risk
(shares = risk/(e-s)), so half-risk counterfactual = 0.5 x pnl per ignorance trade — exact
modulo share rounding. TRAIN 7/28-29 · TEST 7/30-31, read once.

VERDICT RULES (frozen): ship to the 8/8 sizing table only if ALL of:
  R1. ignorance-cohort mean < 0 AND >= $5/trade worse than informed cohort, on BOTH splits
  R2. two-tier total P&L > actual total on BOTH splits
  R3. R2 survives dropping the single worst (name, day) from the ignorance cohort
Anything less => tiers stay a hypothesis; collect another week of stamps.
"""
import json, urllib.request, collections, pathlib

U = "https://zestful-intuition-production-b16a.up.railway.app"
rows = json.load(urllib.request.urlopen(f"{U}/api/trades", timeout=60))["trades"]
wk = [t for t in rows if "2026-07-28" <= (t.get("date") or "") <= "2026-07-31"]

def rw(t):
    try: return float(t.get("marked_runway_rr"))
    except (TypeError, ValueError): return None

TRAIN = {"2026-07-28", "2026-07-29"}
def split(t): return "TRAIN" if t["date"] in TRAIN else "TEST"

for t in wk:
    t["_pnl"] = float(t.get("pnl") or 0)
    t["_ign"] = rw(t) is None          # fail-open ignorance: no marked level -> no runway stamp

def stats(g):
    n = len(g)
    if not n: return "n=0"
    p = sum(t["_pnl"] for t in g)
    return (f"n={n:>3}  ${p:>8.2f}  mean ${p/n:>7.2f}  "
            f"win {100*sum(1 for t in g if t['_pnl']>0)/n:>3.0f}%")

print("== cohorts ==")
r1 = {}
for sp in ("TRAIN", "TEST"):
    inf = [t for t in wk if split(t) == sp and not t["_ign"]]
    ign = [t for t in wk if split(t) == sp and t["_ign"]]
    mi = sum(t["_pnl"] for t in inf)/len(inf) if inf else 0.0
    mg = sum(t["_pnl"] for t in ign)/len(ign) if ign else 0.0
    print(f"{sp}: informed {stats(inf)}")
    print(f"{sp}: ignorance {stats(ign)}")
    r1[sp] = bool(ign) and mg < 0 and (mi - mg) >= 5.0
print(f"R1 (ignorance negative & >=$5 worse, both splits): TRAIN={r1['TRAIN']} TEST={r1['TEST']}")

print("\n== two-tier counterfactual (ignorance at 0.5x risk) ==")
r2 = {}
for sp in ("TRAIN", "TEST"):
    g = [t for t in wk if split(t) == sp]
    actual = sum(t["_pnl"] for t in g)
    tiered = sum(t["_pnl"] * (0.5 if t["_ign"] else 1.0) for t in g)
    print(f"{sp}: actual ${actual:>8.2f} -> two-tier ${tiered:>8.2f}  (delta ${tiered-actual:+.2f})")
    r2[sp] = tiered > actual
print(f"R2 (two-tier beats actual, both splits): TRAIN={r2['TRAIN']} TEST={r2['TEST']}")

print("\n== R3 robustness: drop the worst ignorance (name, day) ==")
byname = collections.defaultdict(float)
for t in wk:
    if t["_ign"]: byname[(t["ticker"], t["date"])] += t["_pnl"]
worst = min(byname, key=byname.get) if byname else None
print(f"worst ignorance name-day: {worst} ${byname.get(worst, 0):.2f}")
r3 = True
for sp in ("TRAIN", "TEST"):
    g = [t for t in wk if split(t) == sp and not (t["_ign"] and (t["ticker"], t["date"]) == worst)]
    actual = sum(t["_pnl"] for t in g)
    tiered = sum(t["_pnl"] * (0.5 if t["_ign"] else 1.0) for t in g)
    print(f"{sp} ex-worst: delta ${tiered-actual:+.2f}")
    r3 = r3 and (tiered >= actual)

print("\n== per-lane composition of the ignorance cohort (context, not a rule) ==")
for lane, g in sorted(collections.groupby if False else
                      {(l): [t for t in wk if t["_ign"] and t.get("entry_type") == l]
                       for l in sorted(set(t.get("entry_type") or "?" for t in wk if t["_ign"]))}.items()):
    print(f"  {lane:<14} {stats(g)}")

verdict = all(r1.values()) and all(r2.values()) and r3
print(f"\nVERDICT vs frozen rules: {'SHIP TO 8/8 TABLE' if verdict else 'HOLD — stays hypothesis, collect more stamps'}")
print(f"  R1={all(r1.values())} R2={all(r2.values())} R3={r3}")
json.dump({"rows": [{k: t.get(k) for k in ('date','ticker','entry_type','_pnl','_ign')} for t in wk]},
          open(pathlib.Path(__file__).with_name("twotier_rows_20260803.json"), "w"), indent=1)
