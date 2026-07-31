"""ABSOLUTE PER-BAR DOLLAR FLOOR ON THE RECLAIM FIRE (7/30, Marcos: "run it").

WHY (established in-transcript today):
  Every gate in the reclaim lane is RELATIVE to the name's own recent tape, so a dead stock
  passes them all. Median DEAD fire: entry bar traded 100 shares / $401, and cleared the 2x
  volume gate at a 4.96x multiple — HIGHER than the movers' 4.81x. 85.1% of dead fires triggered
  on a sub-5,000-share bar. There is no absolute liquidity floor anywhere in the detector.

THE TEST: require the FIRING BAR to have traded at least $X. Nothing else changes — same
grammar, same stops, same ladder, same sizing chain. This is a TRADEABILITY floor (the same
class as the 6% min-stop-width and the 10k/bar read-list floor), not a setup-quality scalar.

PRE-REGISTERED, written before any number was seen:
  1. FIDELITY: floor=$0 must reproduce the anatomy population (n~784, ~-$4849), or VOID.
  2. OOS: TRAIN 07-13..07-24 ranks; TEST 07-27..07-30 read ONCE afterwards.
  3. PLATEAU: the winning floor needs winning neighbours. A lone spike is overfit.
  4. MIN n: TEST n < 30 is not eligible — a floor that leaves no trades is not a fix.
  5. THE HONEST BAR: cutting 51.6% of MOVERS is the known cost. The floor must improve mean
     $/fire on TEST *and* not destroy the tail: report kept-tail (fires reaching >=2R MFE)
     alongside dollars. A floor that turns the lane positive by removing all convexity is a
     different, worse lane.
  6. FAILURE CONDITION: if no floor is positive on TEST at n>=30, the absolute-liquidity
     hypothesis is REFUTED and goes to Fable as refuted — not softened, not re-cut.
"""
import json, pathlib, statistics, collections, harness

F = json.load(open(pathlib.Path(__file__).with_name("reclaim_anatomy_20260730.json")))
TRAIN = {"2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17", "2026-07-20",
         "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24"}

rows = []
for f in F:
    b = harness.bars(f["tk"], f["d"])
    if not b:
        continue
    i0 = next((i for i, x in enumerate(b) if x[6] >= f["hm"]), None)
    if i0 is None:
        continue
    e, s = f["px"], f["stop"]
    rps = e - s
    if rps <= 0:
        continue
    peak = e
    for x in b[i0:]:
        peak = max(peak, x[2])
        if x[3] <= s:
            break
    rows.append({**f, "bar_dollars": b[i0][5] * b[i0][4], "bar_shares": b[i0][5],
                 "mfe": (peak - e) / rps})

def agg(rs):
    n = len(rs)
    if not n:
        return 0, 0.0, 0.0, 0.0, 0
    p = sum(r["pnl"] for r in rs)
    return n, p, p / n, 100 * sum(1 for r in rs if r["pnl"] > 0) / n, sum(1 for r in rs if r["mfe"] >= 2)

n0, t0, m0, w0, tail0 = agg(rows)
print(f"FIDELITY floor=$0: n={n0} total=${t0:.2f} mean=${m0:.2f} win={w0:.1f}% "
      f"tail(>=2R MFE)={tail0}\n")

FLOORS = (0, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000)
print("=" * 118)
print("PER-BAR DOLLAR FLOOR ON THE FIRING BAR")
print("=" * 118)
print(f"{'floor $':>10} | {'TRAIN n':>8}{'mean $':>9}{'win%':>7}{'total $':>10} "
      f"| {'TEST n':>7}{'mean $':>9}{'win%':>7}{'total $':>10}{'tail':>6}{'tail kept%':>11}")
best = []
for fl in FLOORS:
    kept = [r for r in rows if r["bar_dollars"] >= fl]
    tr = [r for r in kept if r["d"] in TRAIN]
    te = [r for r in kept if r["d"] not in TRAIN]
    ntr, ttr, mtr, wtr, _ = agg(tr)
    nte, tte, mte, wte, tail = agg(te)
    te_all_tail = sum(1 for r in rows if r["d"] not in TRAIN and r["mfe"] >= 2)
    tag = ""
    if mte > 0 and nte >= 30:
        tag = "  <-- POSITIVE OOS"
    print(f"{fl:>10,} | {ntr:>8}{mtr:>9.2f}{wtr:>7.1f}{ttr:>10.2f} "
          f"| {nte:>7}{mte:>9.2f}{wte:>7.1f}{tte:>10.2f}{tail:>6}"
          f"{(100*tail/te_all_tail if te_all_tail else 0):>10.1f}%{tag}")
    best.append((mtr, fl, mte, nte))

print("\n" + "=" * 118)
print("VERDICT AGAINST THE PRE-REGISTERED GATES")
print("=" * 118)
pos = [(mtr, fl, mte, nte) for mtr, fl, mte, nte in best if mte > 0 and nte >= 30]
if not pos:
    print("  NO floor is positive on TEST at n>=30.")
    print("  -> FAILURE CONDITION MET (gate 6): the absolute-liquidity floor is REFUTED as a fix.")
    print("     It cuts dead fires harder than movers, but not hard enough to cross zero.")
else:
    for mtr, fl, mte, nte in sorted(pos, key=lambda x: -x[2]):
        print(f"  floor ${fl:,}: TEST mean=${mte:.2f} n={nte}  (TRAIN mean=${mtr:.2f})")

json.dump(rows, open(pathlib.Path(__file__).with_name("reclaim_barfloor_20260730.json"), "w"), indent=1)
print("\nrows saved -> reclaim_barfloor_20260730.json")
