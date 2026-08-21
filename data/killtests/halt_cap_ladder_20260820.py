#!/usr/bin/env python3
"""
HALT LANE — THE PER-NAME WALL LADDER (8/20 night, Marcos: "run the ladder")

WHY: halt_arm's 60s throttle is PER NAME, so a crowned name in a live ladder can arm every
minute. Measured in halt_arm_feed_20260820: crowned name-days average 6.4 arms and one
produced 13. LANE_EXPECTANCY already carries the warning — "arm study +$840.93/110 arms, but
no per-trade wall" (marcos_trading_bot.py:4004) — and the 8/10 XHLD directive lets halt_ladder
stack a second position in a name another lane holds. Thirteen half-size slices in one ticker
is one position in disguise: they stop together.

THIS FILE re-books the SAME fills from halt_arm_feed_20260820_out.json (no re-fetch, no
re-walk — identical trades, identical costs) under a per-name-day arm cap N in {1,2,3,4,6,99}.
Reported for the crown-proxy cohort and the full 10s cohort.

Two axes, because dollars alone cannot answer a risk question:
  RETURN  total dollars at $3,000 and $5,000 (the 8/20 law)
  RISK    PEAK SAME-NAME NOTIONAL — the most capital simultaneously live in ONE ticker, i.e.
          what a single ladder-break costs, and CORRELATED-STOP $ — the sum of all
          simultaneously-open slices' risk in that name at the peak.

PRE-REGISTERED (written before the run): a cap is justified iff it holds total dollars
materially flat while cutting peak same-name notional. If the uncapped book pays materially
more, the burst is the edge and the answer is a sizing rule, not a cap. Nothing ships here.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "halt_arm_feed_20260820_out.json")))


def book(fl, bal, cap):
    per = collections.Counter()
    byday = collections.defaultdict(list)
    for f in fl:
        byday[f["d"]].append(f)
    tot = n = 0
    peak_name = 0.0
    peak_desc = ""
    for d, l in byday.items():
        op = []                      # (exit_epoch, notional, ticker)
        for f in sorted(l, key=lambda x: x["ti"]):
            if per[(f["d"], f["tk"])] >= cap:
                continue
            op = [o for o in op if o[0] > f["ti"]]
            if f["n"] > bal - sum(o[1] for o in op):
                continue
            per[(f["d"], f["tk"])] += 1
            op.append((f["tx"], f["n"], f["tk"]))
            same = sum(o[1] for o in op if o[2] == f["tk"])
            if same > peak_name:
                peak_name, peak_desc = same, f"{f['d']} {f['tk']} x{sum(1 for o in op if o[2]==f['tk'])}"
            tot += f["pnl"]
            n += 1
    return tot, n, peak_name, peak_desc


fl10 = D["fills"]["10"]
COHORTS = (("CROWN-PROXY (10s)", [f for f in fl10 if f["logged"]]),
           ("FULL COHORT (10s)", fl10))
for lab, fl in COHORTS:
    print(f"\n{lab}   n_arms={len(fl)}")
    print(f"{'cap':>4s} {'taken':>6s} {'$3,000':>10s} {'$5,000':>10s} {'$/arm':>7s} "
          f"{'peak same-name $':>17s}  worst-case slice stack")
    for cap in (1, 2, 3, 4, 6, 99):
        t3, n3, _, _ = book(fl, 3000.0, cap)
        t5, n5, pk, desc = book(fl, 5000.0, cap)
        print(f"{cap:4d} {n5:6d} {t3:+10.2f} {t5:+10.2f} {(t5/n5 if n5 else 0):+7.2f} "
              f"{pk:17.0f}  {desc}")
print("\nPRE-REGISTERED: a cap is justified iff dollars hold materially flat while peak")
print("same-name notional falls. If uncapped pays materially more, the burst IS the edge and")
print("the answer is a sizing rule, not a cap. Nothing ships from this file.")
