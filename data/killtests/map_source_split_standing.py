#!/usr/bin/env python3
"""STANDING TRACKER — true map-source split (vision reads vs Kev's actual levels).

Marcos 8/12: "I want to see if these numbers continue."
Baseline that night (8/04-8/12 store-mapped trades, split by wl['_levels'][day][tk]['src']):
    vision 107 | +$1,197.44 | +$11.19/tr | 61% W
    sheet   13 |    +$23.25 |  +$1.79/tr | 46% W

Rerun any evening: python3 map_source_split_standing.py
NOTE the 8/13 flip: from 2026-08-13 Kev-sheet names are vision-GOVERNED (kev_name=True,
his numbers verbatim in kev_shadow). Post-flip rows therefore appear in a third cohort —
"kev-name under chart governance" — which is exactly the Friday A/B realized book.
Kev's counterfactual book comes from the prereg replay, not this script.
"""
import json, urllib.request

U = "https://zestful-intuition-production-b16a.up.railway.app"
FLIP_DAY = "2026-08-13"

def get(path):
    return json.load(urllib.request.urlopen(U + path, timeout=30))

wl = get("/api/kev_watchlist")
levels_by_day = wl.get("_levels", {})
trades = get("/api/trades").get("trades") or []

pre, post = {}, {"kev_name(chart-governed)": [], "vision(non-kev)": [], "no-store-row": []}
for t in trades:
    day = t.get("date") or ""
    if day < "2026-08-04" or t.get("entry_vs_kev_level_pct") is None:
        continue
    rec = (levels_by_day.get(day) or {}).get(t.get("ticker")) or {}
    pnl = float(t.get("pnl") or 0)
    if day < FLIP_DAY:
        pre.setdefault(rec.get("src") or "no-store-row", []).append(pnl)
    else:
        if rec.get("kev_name") or rec.get("kev_shadow"):
            post["kev_name(chart-governed)"].append(pnl)
        elif rec:
            post["vision(non-kev)"].append(pnl)
        else:
            post["no-store-row"].append(pnl)

def show(title, d):
    print(title)
    for k, v in sorted(d.items(), key=lambda x: -sum(x[1])):
        if not v: continue
        print(f"  {k:26s} n={len(v):3d} net ${sum(v):+9.2f} "
              f"(${sum(v)/len(v):+.2f}/tr, {100*sum(1 for x in v if x>0)/len(v):.0f}% W)")

show(f"PRE-FLIP (8/04..{FLIP_DAY} excl) by TRUE map source:", pre)
print()
show(f"POST-FLIP ({FLIP_DAY}+) realized book:", post)
print("\n(Kev counterfactual book for the post-flip cohort = prereg first-touch replay,")
print(" level_primacy_ab_PREREG_20260812.md — this script tracks the realized side only.)")
