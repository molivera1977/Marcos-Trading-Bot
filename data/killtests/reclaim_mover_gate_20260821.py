#!/usr/bin/env python3
"""
VWAP_RECLAIM — THE MOVER-GATE KILL-TEST (8/21, Marcos: "do it")

THE HYPOTHESIS BEING TESTED (from tonight's reconciliation): reclaim's opening-hour edge is
real on movers at real costs (+$9.86/fill, n=24, cache-membership split) and negative off them
(-$11.27/fill, n=77); junk fires outnumber mover fires ~3:1, so the lane drowns. If true, the
retool is a UNIVERSE GATE, not a stop/exit/firevol change.

THE HINDSIGHT PROBLEM, NAMED: "in the 10s cache" is NOT a live-decidable gate — names get
ferried BECAUSE they moved. A gate the live bot could actually apply must be computable at the
fire minute from the tape. This file tests one: PRIOR-5-MINUTE DOLLAR VOLUME at the fire,
computed from the same SIP trades tape the walks use. Cache membership is reported once as the
hindsight REFERENCE line, clearly labeled, never as a candidate gate.

METHOD
  Fills+P&L   reused AS-IS from reclaim_full_20260821_out.json (same walks, same real NBBO
              spreads, same 1% floor / k=1 filters). Nothing is re-walked — this file only adds
              a per-fire gate variable and re-books cohorts.
  Gate var    dvol5 = sum(price x size) over [fire-300s, fire) from a fresh trades fetch per
              name-day (window: 10 min before first fire -> last fire). nprints5 kept as a
              secondary stamp.
  Ladder      dvol5 >= {0 (baseline), 50k, 100k, 250k, 500k, 1M}.
  Cuts        ALL takeable / RTH / PRE / opening hour. Exits: E3 (house) and VWAP (tonight's
              least-bad) — both shown; no other exits, to cap the comparison count.
  Books       $5,000 primary (go-live), $3,000 echoed on the verdict line.

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  P1 PRIMARY CELL: RTH cut, E3 exit. A threshold T earns "gate found" iff at T: total positive
     at BOTH books AND both halves (even/odd dates) positive AND drop-best positive.
  P2 MULTIPLICITY: 5 thresholds are tried; a single passing threshold with red neighbors is a
     lucky slice, NOT a gate — passing must be broadly monotone (the thresholds above it stay
     positive too, allowing n to shrink).
  P3 The hindsight cache line is a CEILING reference only. If dvol5 cannot recover most of the
     cache split's separation, the mover signal is not liquidity and other live gates (day gain,
     crown) are the next candidates — that would be reported as NOT FOUND, not stretched.
  P4 Nothing ships from this file.
"""
import collections
import datetime as dt
import glob
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sp = importlib.util.spec_from_file_location("HF", os.path.join(HERE, "halt_arm_feed_20260820.py"))
HF = importlib.util.module_from_spec(sp)
sp.loader.exec_module(HF)

ROWS = json.load(open(os.path.join(HERE, "reclaim_full_20260821_out.json")))
CACHE = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(HERE, "..", "universe", "bars10s", "*.json"))}
LADDER = (0, 50_000, 100_000, 250_000, 500_000, 1_000_000)
BOOKS = (3000.0, 5000.0)

live = [r for r in ROWS if r.get("today_ok") and "pnl_E3" in r and r.get("ti")]
bynd = collections.defaultdict(list)
for r in live:
    bynd[(r["d"], r["tk"])].append(r)
print(f"fires to stamp: {len(live)} across {len(bynd)} name-days\n")

for i, ((d, tk), l) in enumerate(sorted(bynd.items()), 1):
    t0 = min(x["ts"] for x in l)
    lo = (dt.datetime.fromisoformat(f"{d}T{t0}") - dt.timedelta(minutes=10)).strftime("%H:%M:%S")
    hi = max(x["ts"] for x in l)
    tr = HF.trades(tk, d, lo, hi)
    print(f"  [{i}/{len(bynd)}] {d} {tk} fires={len(l)} trades={len(tr)}", flush=True)
    for f in l:
        # fire epoch: ts is ET wall clock; trades() epochs are true UTC. ET+4h = UTC.
        ep = dt.datetime.fromisoformat(f"{d}T{f['ts']}+00:00").timestamp() + 4 * 3600
        w = [(p, s) for (t, p, s) in tr if ep - 300 <= t < ep]
        f["dvol5"] = sum(p * s for p, s in w)
        f["nprints5"] = len(w)

def book(fl, bal, key):
    byday = collections.defaultdict(list)
    for f in fl:
        byday[f["d"]].append(f)
    tot = n = 0
    for d, l in byday.items():
        op = []
        for f in sorted(l, key=lambda x: x["ti"]):
            op = [o for o in op if o[0] > f["ti"]]
            if f["n"] > bal - sum(o[1] for o in op):
                continue
            op.append((f["tx"], f["n"]))
            tot += f[key]
            n += 1
    return tot, n

def line(fl, key):
    t5, n5 = book(fl, 5000.0, key)
    t3, _ = book(fl, 3000.0, key)
    tr_ = sum(r[key] for r in fl if int(r["d"][-2:]) % 2 == 0)
    oo = sum(r[key] for r in fl if int(r["d"][-2:]) % 2 == 1)
    p = sorted((r[key] for r in fl), reverse=True)
    return t5, t3, n5, tr_, oo, (t5 - (p[0] if p else 0)), \
        (100 * sum(1 for x in p if x > 0) / len(p)) if p else 0

CUTS = (("RTH (PRIMARY)", lambda r: r["sess"] == "RTH"),
        ("opening hour", lambda r: r["sess"] == "RTH" and "09:30" <= r["hhmm"] < "10:30"),
        ("PRE", lambda r: r["sess"] == "PRE"),
        ("ALL", lambda r: True))
for lab, sel in CUTS:
    print(f"\n=== {lab} ===")
    for key in ("pnl_E3", "pnl_VWAP"):
        print(f"  [{key[4:]}] {'dvol5>=':>9s} {'n':>4s} {'$5,000':>10s} {'$3,000':>10s} "
              f"{'TRAIN':>9s} {'OOS':>9s} {'w/o best':>9s} {'win%':>5s}")
        for T in LADDER:
            fl = [r for r in live if sel(r) and r["dvol5"] >= T]
            if not fl:
                continue
            t5, t3, n5, tr_, oo, wb, win = line(fl, key)
            print(f"  {'':6s}{T:>9,} {len(fl):4d} {t5:+10.2f} {t3:+10.2f} "
                  f"{tr_:+9.2f} {oo:+9.2f} {wb:+9.2f} {win:4.0f}%")
    ref = [r for r in live if sel(r) and f"{r['d']}_{r['tk']}" in CACHE]
    if ref:
        t5, t3, n5, tr_, oo, wb, win = line(ref, "pnl_E3")
        print(f"  [HINDSIGHT REFERENCE — cache membership, NOT a live gate] "
              f"n={len(ref)} $5k={t5:+.2f} TRAIN={tr_:+.2f} OOS={oo:+.2f} w/o best={wb:+.2f}")

json.dump(live, open(os.path.join(HERE, "reclaim_mover_gate_20260821_out.json"), "w"), default=str)
print("\nPRE-REGISTERED: P1 primary = RTH/E3, needs BOTH books + BOTH halves + drop-best")
print("positive. P2 one passing threshold with red neighbors = lucky slice, not a gate.")
print("P3 if dvol5 can't recover the cache split, verdict = NOT FOUND. P4 nothing ships.")
