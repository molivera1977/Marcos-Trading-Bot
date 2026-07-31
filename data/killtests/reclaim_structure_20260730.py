"""RECLAIM: SWING STRUCTURE BEFORE THE CROSS (7/30 — Marcos: "patterns of higher highs, higher
lows; similar ideas to understand the rising trend prior to the vwap crossing").

THE GAP THIS FILLS: the discriminator hunt tested 13 features and NONE measured sequence. vwslope
and pct_above are AVERAGES — they cannot tell a stair-stepping uptrend from a name that spiked
once and drifted. Higher-highs/higher-lows is a SEQUENCE property. And structurally, phase 1 of
kev_reclaim_step fires on any volume-backed cross with ZERO memory of what came before it.

FEATURES (all computed strictly BEFORE the cross bar — cross index = fire index - st["bars"],
recorded live by the anatomy instrumentation, so there is no lookahead):
  hh15/hl15, hh30/hl30   count of higher swing highs / higher swing lows in the 15 and 30 min
                         before the CROSS (fractal pivots, 3 bars either side)
  seq_intact             1 if the last 2 swing highs AND last 2 swing lows are both rising
  wick_higher_low        THE KEY ONE: is the retest wick low HIGHER than the last swing low
                         before the cross? The machine never checks this — it only asks that the
                         wick dipped near VWAP and closed in the top half of its range. A reclaim
                         that makes a LOWER low is, structurally, not a reclaim.
  bars_since_low         bars from the pre-cross swing low to the cross (how young the leg is)
  leg_pct                % rise from that swing low to the cross

COHORTS (labelled by outcome, never used as an input): DEAD = MFE < 0.5R, MOVER = MFE >= 2.0R.

PRE-REGISTERED, before any number was seen:
  1. TRAIN 07-13..07-24 ranks; TEST 07-27..07-30 read ONCE, after. 07-30 is CUT AT 16:00 — the
     RTH session is final (18:39 EDT) but the after-hours tape is still accumulating.
  2. A feature is a candidate only if mover-rate spread >= 10pp between its extreme groups on
     TRAIN with n >= 40 per group, and the ordering is monotone.
  3. DOLLAR TEST: must improve mean $/fire on TEST. Mover-rate alone is not enough — atr5 had the
     best separation in the whole study today (24.6pp) and LOST $4.76/fire when used as a filter.
  4. TAIL TEST: report >=2R fires kept. A filter that crosses zero by deleting the tail is
     rejected (killed the absolute liquidity floor earlier today).
  5. FAILURE CONDITION: if nothing clears 2-4, swing structure does not predict which reclaim
     goes either, and that is reported as the finding — no re-cutting until something passes.
"""
import json, pathlib, statistics, collections, harness

F = json.load(open(pathlib.Path(__file__).with_name("reclaim_anatomy_20260730.json")))
TRAIN = {"2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17", "2026-07-20",
         "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24"}

def pivots(bars, k=3):
    """fractal swing points: high[i] strictly greatest of its +/-k neighbours (and low likewise)."""
    hi, lo = [], []
    for i in range(k, len(bars) - k):
        w = bars[i - k:i + k + 1]
        if bars[i][2] == max(x[2] for x in w) and bars[i][2] > bars[i - 1][2]:
            hi.append((i, bars[i][2]))
        if bars[i][3] == min(x[3] for x in w) and bars[i][3] < bars[i - 1][3]:
            lo.append((i, bars[i][3]))
    return hi, lo

rows = []
for f in F:
    if f["d"] == "2026-07-30" and f["hm"] >= "16:00:00":
        continue                                   # gate 1: after-hours 7/30 is still accumulating
    b = harness.bars(f["tk"], f["d"])
    if not b:
        continue
    i0 = next((i for i, x in enumerate(b) if x[6] >= f["hm"]), None)
    nb = f.get("bars")
    if i0 is None or nb is None:
        continue
    ic = i0 - int(nb)                              # the CROSS bar, recorded live
    if ic < 60:
        continue
    e, s = f["px"], f["stop"]
    if e <= s:
        continue
    peak = e
    for x in b[i0:]:
        peak = max(peak, x[2])
        if x[3] <= s:
            break
    mfe = (peak - e) / (e - s)
    lab = "DEAD" if mfe < 0.5 else ("MOVER" if mfe >= 2.0 else "MID")

    def count(win):
        seg = b[max(0, ic - win):ic]               # strictly BEFORE the cross
        hi, lo = pivots(seg)
        hh = sum(1 for a, z in zip(hi, hi[1:]) if z[1] > a[1])
        hl = sum(1 for a, z in zip(lo, lo[1:]) if z[1] > a[1])
        return hh, hl, hi, lo

    hh15, hl15, _, _ = count(90)                   # 15 min of 10s bars
    hh30, hl30, hi30, lo30 = count(180)
    seq_intact = int(len(hi30) >= 2 and len(lo30) >= 2
                     and hi30[-1][1] > hi30[-2][1] and lo30[-1][1] > lo30[-2][1])
    last_low = lo30[-1][1] if lo30 else None
    wick_low = f.get("wick_low")
    rows.append({
        "d": f["d"], "tk": f["tk"], "hm": f["hm"], "pnl": f["pnl"], "mfe": mfe, "lab": lab,
        "hh15": hh15, "hl15": hl15, "hh30": hh30, "hl30": hl30, "seq_intact": seq_intact,
        "wick_higher_low": (1 if (wick_low is not None and last_low is not None
                                  and wick_low > last_low) else 0),
        "bars_since_low": (ic - lo30[-1][0]) if lo30 else -1,
        "leg_pct": ((b[ic][4] - last_low) / last_low * 100) if last_low else 0,
        "hh_plus_hl": hh30 + hl30,
    })

D = [r for r in rows if r["lab"] == "DEAD"]; M = [r for r in rows if r["lab"] == "MOVER"]
print(f"n={len(rows)}  DEAD={len(D)}  MOVER={len(M)}  MID={len(rows)-len(D)-len(M)}"
      f"   (7/30 cut at 16:00)\n")

FEATS = ["hh15", "hl15", "hh30", "hl30", "hh_plus_hl", "seq_intact", "wick_higher_low",
         "bars_since_low", "leg_pct"]
tr = [r for r in rows if r["d"] in TRAIN]
trD = [r for r in tr if r["lab"] == "DEAD"]; trM = [r for r in tr if r["lab"] == "MOVER"]
print("=" * 100)
print("MEDIANS — DEAD vs MOVER (TRAIN only)")
print("=" * 100)
print(f"{'feature':<18}{'DEAD':>12}{'MOVER':>12}{'gap':>12}")
for k in FEATS:
    a = statistics.median([r[k] for r in trD]) if trD else 0
    z = statistics.median([r[k] for r in trM]) if trM else 0
    print(f"{k:<18}{a:>12.2f}{z:>12.2f}{z-a:>12.2f}")

print("\n" + "=" * 100)
print("BINARY FEATURES — mover-rate when TRUE vs FALSE (TRAIN)")
print("=" * 100)
te = [r for r in rows if r["d"] not in TRAIN]
def mover_rate(rs):
    c = [r for r in rs if r["lab"] in ("DEAD", "MOVER")]
    return (100 * sum(1 for r in c if r["lab"] == "MOVER") / len(c)) if c else 0, len(c)
cands = []
for k in ("seq_intact", "wick_higher_low"):
    for v in (1, 0):
        r_, n_ = mover_rate([r for r in tr if r[k] == v])
        print(f"  {k}={v}: mover-rate {r_:>5.1f}%  (n={n_})")
    r1, n1 = mover_rate([r for r in tr if r[k] == 1])
    r0, n0 = mover_rate([r for r in tr if r[k] == 0])
    if abs(r1 - r0) >= 10 and min(n1, n0) >= 40:
        cands.append((k, 1 if r1 > r0 else 0, abs(r1 - r0)))
        print(f"     -> spread {abs(r1-r0):.1f}pp  CANDIDATE")
    print()

print("=" * 100)
print("COUNT FEATURES — mover-rate by value (TRAIN)")
print("=" * 100)
for k in ("hh15", "hl15", "hh30", "hl30", "hh_plus_hl"):
    g = collections.defaultdict(list)
    for r in tr:
        g[min(r[k], 4)].append(r)
    line = f"  {k:<12}"
    rates = []
    for v in sorted(g):
        rt, n_ = mover_rate(g[v])
        rates.append((v, rt, n_))
        line += f"  {v}:{rt:>5.1f}%(n={n_:>3})"
    print(line)
    big = [x for x in rates if x[2] >= 40]
    if len(big) >= 2:
        sp = max(x[1] for x in big) - min(x[1] for x in big)
        mono = all(a[1] <= b[1] for a, b in zip(big, big[1:])) or \
               all(a[1] >= b[1] for a, b in zip(big, big[1:]))
        if sp >= 10 and mono:
            thr = max(big, key=lambda x: x[1])[0]
            cands.append((k, thr, sp))
            print(f"     -> spread {sp:.1f}pp monotone  CANDIDATE (best at {k}>={thr})")

print("\n" + "=" * 100)
print("GATES 3+4 — DOLLAR AND TAIL TEST ON HELD-OUT TEST DAYS (read once)")
print("=" * 100)
def agg(rs):
    n = len(rs)
    if not n:
        return 0, 0.0, 0, 0.0
    p = sum(r["pnl"] for r in rs)
    return n, p / n, sum(1 for r in rs if r["mfe"] >= 2), 100 * sum(1 for r in rs if r["pnl"] > 0) / n
nU, mU, tailU, wU = agg(te)
print(f"  UNGATED TEST: n={nU} mean=${mU:.2f} win={wU:.1f}% tail={tailU}\n")
if not cands:
    print("  NO CANDIDATE cleared gate 2.")
    print("  -> FAILURE CONDITION MET (gate 5): swing structure does not separate these cohorts.")
for k, thr, sp in cands:
    kept = [r for r in te if (r[k] == thr if k in ("seq_intact", "wick_higher_low") else r[k] >= thr)]
    n1, m1, t1, w1 = agg(kept)
    ok = m1 > mU and n1 >= 30
    tail_kept = 100 * t1 / tailU if tailU else 0
    print(f"  {k} (keep {'==' if k in ('seq_intact','wick_higher_low') else '>='}{thr}): "
          f"TEST n={n1} mean=${m1:.2f} win={w1:.1f}% tail kept={tail_kept:.1f}%  "
          f"-> {'IMPROVES' if ok else 'FAILS'}"
          + ("  [tail destroyed]" if ok and tail_kept < 70 else ""))

json.dump(rows, open(pathlib.Path(__file__).with_name("reclaim_structure_20260730.json"), "w"), indent=1)
print("\nrows saved -> reclaim_structure_20260730.json")
