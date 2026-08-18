#!/usr/bin/env python3
"""
THE 1-MIN 9/90 LANE — THE WALL (8/18)

Marcos found this signal by reading charts ("every time the 9 crosses the 90, it's going up"),
and every refinement in it is his: the 1-minute frame, the VWAP condition, and the challenge
that killed my exits ("so what are your exits, they didn't look good" — they were giving back
77% of the edge).

THE CANDIDATE, frozen before this run:
  entry : 1-minute EMA9 crosses UP through EMA90; execute on the 10s bar closing that minute
  filter: price >= session VWAP at the cross   (below-VWAP tested to destruction — see below)
  stop  : two arms only, both pre-declared — flat 4%, and the 5-min swing low
  exit  : NONE. Stop, or the close. Every exit rule tested cost money on top of the stop.

WHY THIS NEEDS A WALL AND NOT JUST A NUMBER
  The +$28.32/tr (4% stop) and +$14.52/tr (swing stop) figures came out of a GRID I searched:
  6 exit rules x 3 stops x 2 frames x a VWAP split. Finding the best cell of a grid and then
  quoting it is exactly how a backtest lies. So this run does three independent things the
  grid did not:
    1. A DIFFERENT SPLIT (50/13, not the 44/19 the candidate was found on).
    2. AN INTERLEAVED SPLIT (odd vs even dates) — kills the "one regime carried it" story.
    3. A PERMUTATION NULL on the VWAP label (2,000 shuffles): if randomly relabelling which
       fires count as "above VWAP" reproduces the edge, the edge is not the VWAP condition.

PRE-REGISTERED BAR (written before the run — all four must hold):
  (a) positive $/trade in BOTH new splits' hold-out halves
  (b) hold-out N >= 100 in the 50/13 split
  (c) permutation null p <= 0.05 on the VWAP label
  (d) the below-VWAP cohort stays negative (the condition is doing real work)
  Anything less: NOT ESTABLISHED, the lane stays shadow-only regardless of the grid number.

Below-VWAP was already tested to destruction on 1,492 fires (13% win): distance, VWAP slope,
9/20 stack, 1-min and 3-min velocity, volume surge and 9-EMA slope ALL failed to separate the
195 winners from the 1,297 losers — velocity INVERTED (harder cross = worse: -$20 to -$27).
That is why the VWAP condition is in the candidate rather than a tunable.

Engine: pilot chain (S->G->F->C->B->E), 10s SIP universe cache, 63 dates / ~736 name-days.
Entry slip -1%, exit slip -0.5%, stop-first INTRABAR. Nothing ships from this script.
"""
import importlib.util
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


P = _load("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
S, E = P.S, P.E
MKT, SLIP = 0.005, 0.01
OUT = []


def W(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def ema(v, n):
    k = 2.0 / (n + 1)
    e = None
    o = []
    for x in v:
        e = x if e is None else (x - e) * k + e
        o.append(e)
    return o


def agg(bars, n):
    c, idx = [], []
    for a in range(0, len(bars) - n + 1, n):
        w = bars[a:a + n]
        c.append(w[-1]["c"]); idx.append(a + n - 1)
    return c, idx


def fires_for(bars):
    c1, i1 = agg(bars, 6)
    e9, e90 = ema(c1, 9), ema(c1, 90)
    cpv = cv = 0.0
    vw = []
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
        vw.append(cpv / cv if cv else b["c"])
    out = []
    busy = -1
    for a in range(1, len(i1)):
        i = i1[a]
        if i <= busy or i < 95 or i >= len(bars) - 3:
            continue
        if not (e9[a - 1] <= e90[a - 1] and e9[a] > e90[a]):
            continue
        if not ("13:30:00" <= E.hhmm_b(bars[i]) < "20:00:00"):
            continue
        entry = bars[i]["c"] * (1 + SLIP)
        sh = E.POS / entry
        rec = {"i": i, "above": bars[i]["c"] >= vw[i]}
        for nm, stop in (("pct4", bars[i]["c"] * 0.96),
                         ("swing", min(b["l"] for b in bars[max(0, i - 30):i + 1]))):
            if stop >= entry:
                rec[nm] = None; continue
            hit = None
            for k in range(i + 1, len(bars)):
                if bars[k]["l"] <= stop:
                    hit = k; break
            rec[nm] = (sh * (stop * (1 - MKT) - entry) if hit is not None
                       else sh * (bars[-1]["c"] * (1 - MKT) - entry))
        # hold the position until it stops or the day ends -> one at a time
        busy = len(bars)
        out.append(rec)
    return out


def stat(rs, arm):
    v = [r[arm] for r in rs if r.get(arm) is not None]
    if not v:
        return None
    d = defaultdict(float)
    for r in rs:
        if r.get(arm) is not None:
            d[r["date"]] += r[arm]
    return {"n": len(v), "tot": sum(v), "per": sum(v) / len(v),
            "win": 100.0 * sum(1 for x in v if x > 0) / len(v),
            "green": 100.0 * sum(1 for x in d.values() if x > 0) / max(len(d), 1)}


def line(lbl, s):
    if not s:
        W(f"    {lbl:26s} -"); return
    W(f"    {lbl:26s} n={s['n']:5d}  total=${s['tot']:+10.2f}  $/tr={s['per']:+7.2f}  "
      f"win={s['win']:4.0f}%  green={s['green']:3.0f}%")


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    rows = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for r in fires_for(bars):
            r["sym"], r["date"] = sym, date
            rows.append(r)
    ab = [r for r in rows if r["above"]]
    be = [r for r in rows if not r["above"]]
    W("=" * 96)
    W("THE 1-MIN 9/90 LANE — THE WALL   (entry 1m cross, above VWAP, STOP ONLY, no exit rule)")
    W("=" * 96)
    W(f"universe {len(E.DAYS)} name-days / {len(dates)} dates. fires: {len(rows)} "
      f"({len(ab)} above vwap, {len(be)} below)\n")

    W("FULL SAMPLE — above VWAP")
    for a in ("pct4", "swing"):
        line(f"stop {a}", stat(ab, a))
    W("  full sample — BELOW VWAP (must stay negative)")
    for a in ("pct4", "swing"):
        line(f"stop {a}", stat(be, a))

    results = {}
    for lbl, tr, ho in [
        ("SPLIT A 50/13 (fresh)", set(dates[:50]), set(dates[50:])),
        ("SPLIT B interleaved", set(dates[::2]), set(dates[1::2])),
    ]:
        W(f"\n{lbl}   train {len(tr)} dates | HOLD-OUT {len(ho)} dates")
        for a in ("pct4", "swing"):
            s = stat([r for r in ab if r["date"] in ho], a)
            line(f"HOLD-OUT stop {a}", s)
            results[(lbl, a)] = s

    W("\n" + "=" * 96)
    W("PERMUTATION NULL — shuffle the above/below-VWAP label 2,000x (pct4 stop, full sample)")
    W("=" * 96)
    obs = stat(ab, "pct4")
    pool = [r for r in rows if r.get("pct4") is not None]
    k = sum(1 for r in pool if r["above"])
    rnd = random.Random(20260818)
    hits = 0
    N = 2000
    for _ in range(N):
        samp = rnd.sample(pool, k)
        m = sum(r["pct4"] for r in samp) / len(samp)
        if m >= obs["per"]:
            hits += 1
    p = (hits + 1) / (N + 1)
    W(f"  observed above-VWAP $/tr ${obs['per']:+.2f}   random-label mean beats it "
      f"{hits}/{N}   p = {p:.4f}")

    W("\n" + "=" * 96)
    W("PRE-REGISTERED BAR")
    W("=" * 96)
    a1 = results[("SPLIT A 50/13 (fresh)", "pct4")]
    a2 = results[("SPLIT B interleaved", "pct4")]
    s1 = results[("SPLIT A 50/13 (fresh)", "swing")]
    s2 = results[("SPLIT B interleaved", "swing")]
    bel = stat(be, "pct4")
    c_a = bool(a1 and a2 and a1["per"] > 0 and a2["per"] > 0)
    c_b = bool(a1 and a1["n"] >= 100)
    c_c = p <= 0.05
    c_d = bool(bel and bel["per"] < 0)
    for ok, lbl, val in [
        (c_a, "(a) positive in BOTH fresh splits",
         f"A ${a1['per']:+.2f} / B ${a2['per']:+.2f}" if a1 and a2 else "-"),
        (c_b, "(b) hold-out N >= 100 (split A)", f"n={a1['n']}" if a1 else "-"),
        (c_c, "(c) permutation null p <= 0.05", f"p={p:.4f}"),
        (c_d, "(d) below-VWAP stays negative", f"${bel['per']:+.2f}" if bel else "-"),
    ]:
        W(f"  {'PASS' if ok else 'FAIL'}  {lbl:38s} {val}")
    W("")
    if c_a and c_b and c_c and c_d:
        W("  VERDICT: the 1-min 9/90 above-VWAP entry with a STOP AND NO EXIT RULE clears the")
        W("           pre-registered bar on two fresh splits and a permutation null.")
        W("           It is a CANDIDATE LANE. Shadow-first is still the ship discipline.")
    else:
        W("  VERDICT: NOT ESTABLISHED on this bar. The grid number does not survive; the lane")
        W("           stays shadow-only and nothing converts on it.")
    if s1 and s2:
        W(f"\n  swing-stop arm for comparison: A ${s1['per']:+.2f} / B ${s2['per']:+.2f}")
    W("\nLIMITS: detector-only, no funnel (board membership, slots, caps sit upstream and are")
    W("not modelled). One position per name-day. Fixed E.POS sizing. RTH only.")
    json.dump({"out": OUT}, open(HERE + "/ema9x90_wall_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
