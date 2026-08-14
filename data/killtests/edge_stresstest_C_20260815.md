# EDGE STRESS-TEST C — THE MEDIAN ATTACK (run 8/14/2026 eve, filed 20260815)

**NO CONFIGURATION PASSES ALL 5. Closest: TEST F — 4/5, failing only MEDIAN at
+$25.82/day vs the +$50 bar (short by $24.18/day).**

Round three, pre-registered fresh before the run (per B's Forward Architect note:
median-repair via execution mix / frequency / third stream). Script:
`edge_stresstest_C_20260815.py` — imports `edge_stresstest_B_20260815.py` (which
imports the engine of record `edge_stresstest_20260815.py`); detectors, sim, limit
mechanics, H2-H4 machinery and laws UNCHANGED. Bar identical and pre-registered:
mean AND median > +$50/day, green >= 55%, both date halves positive, worst > -$300.
Context: B(i) grinder+flat_top chased = 4/5, failing only median (+$7.11).

## DATA
**421 cache files in-window, 36 dates 2026-06-25..2026-08-14** — same file set as
round B (no further ferry drift; survivor signals 419 = exact match to B: flat_top
208, grinder 211; vwap 103 exact match). Days with zero trades = $0 days,
36-day denominator throughout.

---
## TEST D — PER-LANE EXECUTION MIX (grinder CHASE + flat_top LIMIT-IN)

Fill rates: grinder 211/211 = 100% (chase) · flat_top 178/208 = 86% (limit-in).

| stage | N | total $ | daily mean $ | worst day $ |
|---|---|---|---|---|
| H1 mixed frictions | 389 | +1,912.64 | +53.13 | -115.70 |
| H2 halt exclusion (0 forced) | 389 | +1,912.64 | +53.13 | -115.70 |
| H3 dedup (0 dropped) | 389 | +1,912.64 | +53.13 | -115.70 |
| H4 capacity (116 skipped) | 273 | **+1,540.08** | **+42.78** | -94.79 |

H5: median **+$33.95** · green 24/36 = **67%** · half1 +$39.52/d / half2 +$46.04/d ·
worst -$94.79 (7/02) · best 8/11 +$301.44, ex-best mean **+$35.39** ·
flat_top N=148 +$166.09 · grinder N=125 +$1,373.99.

| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$42.78 | **FAIL** (short $7.22) |
| daily median | > +$50 | +$33.95 | **FAIL** (short $16.05) |
| green days | >= 55% | 67% | PASS |
| both halves positive | yes | +$39.52 / +$46.04 | PASS |
| worst day | > -$300 | -$94.79 | PASS |

**TEST D: FAIL — 3 of 5.** The mix DOES repair the median's shape (+$7.11 -> +$33.95,
green 56% -> 67%, ex-best +$32.31 -> +$35.39 — a far flatter, healthier book than
B(i)) but at the cost of the mean (+$60.14 -> +$42.78): flat_top under limit-in
earns +$166 vs +$867 chased. The B(ii) lesson generalizes — flat_top's re-break
entry behaves like a breakout at the fill moment; its 14% misses are
disproportionately the winners. "Pullback lane -> limit-in" was the wrong
class assignment for THIS detector (entry = close back above the level, not the
retest low).

---
## TEST E — WIDEN THE PAYING WINDOWS (single pre-registered widening, no sweep)

Grinder post-10:30 ET (was post-11:00) + flat_top 9:30-11:00 ET (was 9:30-10:30),
under D's mix. Widened signals: 562 (flat_top 323, grinder 239); 145 in the added
windows. Fill: flat_top 88%, grinder 100%.

| stage | N | total $ | daily mean $ | worst day $ |
|---|---|---|---|---|
| H1 mixed frictions | 523 | +1,881.51 | +52.26 | -173.49 |
| H2 (0 forced) | 523 | +1,881.51 | +52.26 | -173.49 |
| H3 dedup (4 dropped) | 519 | +1,903.25 | +52.87 | -173.49 |
| H4 capacity (165 skipped) | 354 | **+1,572.23** | **+43.67** | -171.26 |

H5: median **+$22.85** · green 24/36 = 67% · half1 +$40.98/d / half2 +$46.36/d ·
worst -$171.26 (7/22) · best 8/11 +$255.12, ex-best +$37.63 ·
flat_top N=214 +$36.89 · grinder N=140 +$1,535.35.

**MARGINAL COHORT (post-H4 trades in the ADDED windows, graded on its own dollars):
N=84, +$113.43 total, +$1.35/trade** — grinder 10:30-11:00 N=18 **+$242.63**
(+$13.48/trade, in line with its core +$10.60) · flat_top 10:30-11:00 N=66
**-$129.20** (the added hour is a net LOSER for flat_top). Core (orig windows)
N=270 +$1,458.81, +$5.40/trade.

| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$43.67 | **FAIL** (short $6.33) |
| daily median | > +$50 | +$22.85 | **FAIL** (short $27.15) |
| green days | >= 55% | 67% | PASS |
| both halves positive | yes | yes | PASS |
| worst day | > -$300 | -$171.26 | PASS |

**TEST E: FAIL — 3 of 5. The frequency attack does NOT fatten the median — it
THINS it** (+$33.95 -> +$22.85): the added flat_top flow is -$129 on its own
dollars AND its fills crowd the 2 slots (165 skips vs 116), displacing paying core
trades. The one keeper inside the widening: **grinder 10:30-11:00 is real**
(+$242.63 on 18, same per-trade quality as post-11:00). Grinder's edge is not a
clock artifact; flat_top's window was already right.
(Disclosed: grinder's earlier start shifts a handful of post-11:00 signals via the
15-min cooldown chain — core grinder N=122/+$1,292.72 here vs D's 125/+$1,373.99;
second-order.)

---
## TEST F — PORTFOLIO OF D + vwap BAND-PASS (chased, in-window)

vwap 103 signals, 100% fill (chase). Mix: grinder+vwap chased, flat_top limit-in.

| stage | N | total $ | daily mean $ | worst day $ |
|---|---|---|---|---|
| H1 mixed frictions | 492 | +3,022.86 | +83.97 | -130.52 |
| H2 (0 forced) | 492 | +3,022.86 | +83.97 | -130.52 |
| H3 dedup (8 dropped) | 484 | +2,978.71 | +82.74 | -116.71 |
| H4 capacity (174 skipped) | 310 | **+2,367.42** | **+65.76** | -137.97 |

H5: median **+$25.82** · green 22/36 = **61%** · half1 **+$50.56/d** / half2 +$80.96/d ·
worst -$137.97 (7/15) · best 8/07 **+$1,035.78**, ex-best mean **+$38.05** ·
flat_top N=100 +$198.61 · grinder N=123 +$1,319.11 · vwap N=87 +$849.70.

| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$65.76 | PASS |
| daily median | > +$50 | +$25.82 | **FAIL** (short $24.18) |
| green days | >= 55% | 61% | PASS |
| both halves positive | yes | +$50.56 / +$80.96 | PASS |
| worst day | > -$300 | -$137.97 | PASS |

**TEST F: FAIL — 4 of 5, failing only MEDIAN (+$25.82, short $24.18/day).** The
third stream lifts the median vs B(i) (+$7.11 -> +$25.82) and the mean clears with
room — but the vwap lane's +$850 is still 8/07-heavy (best day +$1,036; ex-best
mean +$38.05, itself below the bar), and vwap's slot demand pushes flat_top from
148 to 100 fills. A typical day is ~$26, not $50.

---
## HONEST READING
1. **The median has moved three rounds running — +$7.11 (B(i)) -> +$33.95 (D) ->
   +$25.82 (F) — and never reached $50.** The bar's mean+median pair is exposing
   the same truth each time: the book's typical day is $25-40 at $500/position and
   2 slots; the $50+ days are concentration (8/07, 8/11).
2. **Closest overall = F (4/5, median short $24.18). Healthiest shape = D**
   (67% green, worst -$94.79, ex-best +$35.39 — nothing above criterion but
   nothing rotten either).
3. **Execution-mix lesson: flat_top is NOT a limit-in lane.** Its entry prints on
   the re-break (strength), not the retest low; limit-in costs it ~$700 vs chase.
   The pullback-class limit-in hypothesis survives only for entries that trigger
   AT weakness (v2-class), where B already showed it (+$2,311 swing on v2 in
   Test A vs chase).
4. **Widening refuted as a median repair** — added flow was thin (+$1.35/trade),
   negative for flat_top, and crowded the slots. One salvage: grinder 10:30-11:00
   is the same-quality edge as post-11:00 (+$242.63/18) — a legitimate future
   pre-registration is grinder-from-10:30 WITHOUT the flat_top extension.
5. Per the 8/8 doctrine: no pass = smaller + later, never launch-anyway. The
   honest frame for Marcos: the surviving book (grinder core + flat_top chased +
   maybe vwap) is a real but SMALL edge — roughly +$40-65/day mean, +$25-35/day
   typical, worst days well-contained — under $500/position sizing. Reaching a
   $50 TYPICAL day needs either size (risk decision, Marcos's alone) or a new
   uncorrelated stream, not another re-mix of these three.

## HAND-TRACE (Sim Integrity)
NEXR 2026-06-25 14:00:20Z flat_top, first limit-in signal of Test D: bid 0.8907
(signal close), stop 0.8710. Fill requires a subsequent 10s bar within 180s with
low <= 0.8897; the tape runs 0.8908/0.9107/0.9156/0.9137/0.9138... — never
touches. Engine: MISS. Hand math matches. (Filled-path trace = round B's QTTB
7/13 trace; `sim_limit`/`limit_fill_bar` imported unchanged, verified same file
hash by import — no reimplementation this round.)

## Method notes
1. Execution mix implemented as per-signal dispatch: det in {flat_top} -> B.sim_limit,
   else B.sim_chase. All H2/H3/H4 machinery = round B's pipeline verbatim (fill-time
   dedup/slot chronology; chase fill time = signal time).
2. Test E grinder variant: `det_grinder_1030` = engine-of-record `det_grinder` with
   the single constant 15:00:00Z -> 14:30:00Z (diffable). flat_top widening is
   window-filter-only (detector already runs full-day). Marginal flag stamped at
   signal time: grinder t < 15:00Z, flat_top t > 14:30Z.
3. Single pre-registered widening only — no other windows were run (no sweep).
4. Raw outputs: `stress_C_out.json` (daily tapes + H5 + verdicts for D/E/F),
   run log `stress_C_run.log` — both committed with the run per Quartermaster's
   round-B manifest-retention note.

## Officers touched
Wind Tunnel Engineer (mix dispatch harness), Execution Surgeon (per-lane execution
assignment; flat_top misclassification finding), Convexity Trader (median verdicts —
his criterion is the sole failure in F and the reason nothing ships), Systems Quant
(import-reuse chain C->B->engine, signal-count reconciliation 419/103 exact),
Statistician (this entry, artifacts committed), Momentum Operator (no-ship reading),
First Hour (flat_top 10:30-11:00 hour graded negative on its own dollars), Seam
Scientist (window-widening = his one-day-humility law honored: pre-registered,
single, marginal-cohort-graded), Quartermaster (cache stable 421, outputs committed),
Forward Architect (next registrable, if any: grinder-from-10:30 solo widening;
sizing-not-mixing as the honest path to a $50 typical day — a Marcos risk decision,
not an auditor's), Trade Manager (exits unchanged), Side Marshal / Crown Steward /
Handicapper / Historian: clean (raw-lane test, no gate stack in scope).
