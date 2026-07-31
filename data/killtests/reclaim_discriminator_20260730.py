"""RECLAIM DISCRIMINATOR HUNT (7/30, Marcos: "reclaims work, we just aren't doing something
right" -> "run it").

ESTABLISHED TODAY (all in-transcript):
  - 53.4% of the 784 era reclaim fires NEVER moved +0.5R. Dead on arrival.
  - 21.6% reached +2R and almost all of those finished green. The tail is real (10.2% hit 5R+).
  - Banking 100% at +1R is WORSE (-$6145 vs -$4849): exits are not the leak.
  - All five in-machine constants swept and refuted as fixes (volume/extension/pullback/
    invalidation/confirmation-bars). None separate winners from losers.
So the discriminator, if it exists, is CONTEXT visible BEFORE entry — not grammar.

COHORTS (labelled by what happened after entry, then never used as an input):
    DEAD  = MFE < 0.5R     MOVER = MFE >= 2.0R
Everything between is excluded from the contrast so the two groups are unambiguous.

FEATURES — all computed ONLY from bars at or before the entry bar. No lookahead. Anything that
needs a stamp the era does not reliably carry (day_gain pre-7/28 is tainted per the 7/28 ledger
entry) is computed from the tape instead.

PRE-REGISTERED, written before any number was seen:
  1. TRAIN 07-13..07-24 / TEST 07-27..07-30. Every feature is ranked on TRAIN. The single best
     is then read ONCE on TEST. Features that look good only in TRAIN are reported as refuted.
  2. A feature is a candidate only if it separates DEAD from MOVER by >= 10 percentage points of
     mover-rate between its top and bottom third, on TRAIN n >= 40 per third.
  3. MONOTONE-OR-NOTHING: the middle third must sit between the outer thirds. A U-shape is noise.
  4. DOLLAR TEST: separation in mover-rate is not enough. The candidate must also improve mean
     $/fire when used as a filter, on TEST, or it is refuted.
  5. FAILURE CONDITION: if nothing clears 2-4, the honest finding is that nothing we currently
     record predicts which reclaim goes — the discriminator is off-tape (chart structure), and
     that goes to Fable as the finding rather than another knob.
"""
import json, statistics, collections, pathlib, harness

F = json.load(open(pathlib.Path(__file__).with_name("reclaim_anatomy_20260730.json")))
TRAIN = {"2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17", "2026-07-20",
         "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24"}

def vwap_series(b):
    out, pv, vv = [], 0.0, 0.0
    for k, o, h, l, c, v, hm in b:
        pv += ((h + l + c) / 3.0) * v; vv += v
        out.append(pv / vv if vv > 0 else c)
    return out

rows = []
for f in F:
    b = harness.bars(f["tk"], f["d"])
    if not b:
        continue
    i0 = next((i for i, x in enumerate(b) if x[6] >= f["hm"]), None)
    if i0 is None or i0 < 30:
        continue
    e, s = f["px"], f["stop"]
    rps = e - s
    if rps <= 0:
        continue
    # ---- label: max favourable excursion before the stop was touched
    peak = e
    for x in b[i0:]:
        peak = max(peak, x[2])
        if x[3] <= s:
            break
    mfe = (peak - e) / rps
    if mfe < 0.5:
        lab = "DEAD"
    elif mfe >= 2.0:
        lab = "MOVER"
    else:
        lab = "MID"

    # ---- features, entry bar and earlier ONLY
    vw = vwap_series(b)
    hist = b[:i0 + 1]
    px = e
    day_o = hist[0][1]
    hod = max(x[2] for x in hist)
    lod = min(x[3] for x in hist)
    w5 = hist[-30:]                       # 5 min of 10s bars
    w15 = hist[-90:]
    w30 = hist[-180:]
    vol_day = sum(x[5] for x in hist)
    dollar_vol = sum(x[5] * x[4] for x in hist)
    atr5 = statistics.mean([(x[2] - x[3]) / x[4] for x in w5 if x[4] > 0]) if w5 else 0
    above = sum(1 for i, x in enumerate(hist[-180:], start=max(0, i0 - 179)) if x[4] > vw[i]) / max(len(w30), 1)
    vwslope5 = (vw[i0] - vw[max(0, i0 - 30)]) / vw[max(0, i0 - 30)] if vw[max(0, i0 - 30)] else 0
    vwslope15 = (vw[i0] - vw[max(0, i0 - 90)]) / vw[max(0, i0 - 90)] if vw[max(0, i0 - 90)] else 0
    rows.append({
        "d": f["d"], "tk": f["tk"], "hm": f["hm"], "pnl": f["pnl"], "lab": lab, "mfe": mfe,
        "day_gain":    (px - day_o) / day_o * 100 if day_o else 0,      # gain off the day's first bar
        "from_hod":    (px - hod) / hod * 100 if hod else 0,            # extension below the day high
        "range_pos":   (px - lod) / (hod - lod) * 100 if hod > lod else 50,  # where in the day range
        "vwslope5":    vwslope5 * 100,                                  # VWAP slope, last 5 min
        "vwslope15":   vwslope15 * 100,                                 # VWAP slope, last 15 min
        "pct_above":   above * 100,                                     # % of last 30 min closed > VWAP
        "atr5":        atr5 * 100,                                      # 5-min bar range, % of price
        "dollar_vol":  dollar_vol / 1e6,                                # $M traded so far today
        "vol_burst":   (hist[-1][5] / (vol_day / len(hist))) if vol_day else 0,   # entry bar vs day avg
        "seq":         f["seq"], "w": f["w"], "vwdist": f["vwdist"], "px": px,
    })

D = [r for r in rows if r["lab"] == "DEAD"]
M = [r for r in rows if r["lab"] == "MOVER"]
print(f"cohorts: DEAD (MFE<0.5R) n={len(D)}   MOVER (MFE>=2R) n={len(M)}   "
      f"MID excluded n={sum(1 for r in rows if r['lab']=='MID')}   total={len(rows)}\n")

FEATS = ["day_gain", "from_hod", "range_pos", "vwslope5", "vwslope15", "pct_above", "atr5",
         "dollar_vol", "vol_burst", "seq", "w", "vwdist", "px"]

print("=" * 104)
print("MEDIANS — DEAD vs MOVER (TRAIN only; TEST held back)")
print("=" * 104)
tr = [r for r in rows if r["d"] in TRAIN]
trD = [r for r in tr if r["lab"] == "DEAD"]; trM = [r for r in tr if r["lab"] == "MOVER"]
print(f"{'feature':<14}{'DEAD':>12}{'MOVER':>12}{'gap':>12}")
for k in FEATS:
    a = statistics.median([r[k] for r in trD]) if trD else 0
    b_ = statistics.median([r[k] for r in trM]) if trM else 0
    print(f"{k:<14}{a:>12.2f}{b_:>12.2f}{b_-a:>12.2f}")

print("\n" + "=" * 104)
print("TERCILE TEST (TRAIN) — mover-rate by feature third; gate 2 needs >=10pp spread, gate 3 monotone")
print("=" * 104)
cands = []
for k in FEATS:
    vals = sorted(r[k] for r in tr)
    if len(vals) < 120:
        continue
    q1, q2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    thirds = [[r for r in tr if r[k] < q1],
              [r for r in tr if q1 <= r[k] < q2],
              [r for r in tr if r[k] >= q2]]
    rates, ns = [], []
    for t in thirds:
        cohort = [r for r in t if r["lab"] in ("DEAD", "MOVER")]
        ns.append(len(cohort))
        rates.append(100 * sum(1 for r in cohort if r["lab"] == "MOVER") / len(cohort) if cohort else 0)
    spread = max(rates) - min(rates)
    mono = (rates[0] <= rates[1] <= rates[2]) or (rates[0] >= rates[1] >= rates[2])
    ok = spread >= 10 and mono and min(ns) >= 40
    print(f"{k:<12} low={rates[0]:>5.1f}%(n={ns[0]:>3})  mid={rates[1]:>5.1f}%(n={ns[1]:>3})  "
          f"high={rates[2]:>5.1f}%(n={ns[2]:>3})  spread={spread:>5.1f}pp  "
          f"{'MONOTONE' if mono else 'u-shape':<9}{'  <-- CANDIDATE' if ok else ''}")
    if ok:
        cands.append((spread, k, q1, q2, rates))

print("\n" + "=" * 104)
print("GATE 4 — DOLLAR TEST ON HELD-OUT TEST DAYS (read once)")
print("=" * 104)
te = [r for r in rows if r["d"] not in TRAIN]
if not cands:
    print("  NO CANDIDATE cleared gates 2-3.")
    print("  -> FAILURE CONDITION MET (gate 5): nothing we record predicts which reclaim goes.")
    print("     The discriminator is off-tape — chart structure — and that is the finding.")
for spread, k, q1, q2, rates in sorted(cands, reverse=True):
    keep_high = rates[2] > rates[0]
    kept = [r for r in te if (r[k] >= q2 if keep_high else r[k] < q1)]
    allte = te
    f = lambda rr: (len(rr), sum(x["pnl"] for x in rr) / len(rr) if rr else 0,
                    sum(x["pnl"] for x in rr))
    n1, m1, t1 = f(kept); n0, m0, t0 = f(allte)
    print(f"  {k}: keep {'high' if keep_high else 'low'} third  "
          f"| TEST kept n={n1} mean=${m1:.2f} tot=${t1:.2f}  "
          f"vs ALL n={n0} mean=${m0:.2f} tot=${t0:.2f}  "
          f"-> {'IMPROVES' if m1 > m0 else 'FAILS (no dollar improvement)'}")

json.dump(rows, open(pathlib.Path(__file__).with_name("reclaim_discriminator_20260730.json"), "w"), indent=1)
print("\nrows saved -> reclaim_discriminator_20260730.json")
