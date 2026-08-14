# EDGE STRESS-TEST B — LIMIT-IN / SURVIVORS / CALIBRATED-V2 (run 8/14/2026 ~18:50-19:05 ET, filed 20260815)

FOLLOW-UP registered fresh by Forward Architect in `edge_stresstest_20260815.md`
("limit-in entry friction model + grinder+flat_top-only portfolio — BOTH require
fresh pre-registration"). NOT a re-grade of tonight's FAIL. Script:
`edge_stresstest_B_20260815.py` — imports `edge_stresstest_20260815.py` and reuses
its detectors, sim engine, haircut machinery and laws UNCHANGED. Bar identical and
pre-registered before the run: mean AND median > +$50/day, green >= 55%, both date
halves positive, worst > -$300. Applies to Tests A and B(ii).

## DATA / DEVIATION DISCLOSED
- Denominator: **36 dates, 2026-06-25..2026-08-14** (per registration). The live
  cache grew 419 -> 448 files during the evening ferry; **421 files** fall in-window
  (2 ferry-added files landed inside the window after tonight's committed run; the
  exact 419 manifest is not recoverable — bars10s is not git-tracked and tonight's
  stress_out.json was not retained). Reconciliation: in-scope signals 1,756 vs
  tonight's 1,753 — flat_top 208, vwap 103, grinder 211 EXACT match; v2 1,234 vs
  1,231 (+3 from the 2 added files). Second-order vs every result below.

## LIMIT-IN EXECUTION MODEL (Test A / B(ii) / C-limit)
Signal places a resting bid AT the signal price. Fill ONLY if a subsequent 10s bar
within 180s prints low <= bid - $0.01 (tape trades THROUGH the bid — conservative);
else MISSED. Fill-bar stop check applies (stop-first, tie against the trade — a bar
that fills the bid and breaks the stop is an immediate stop-out). Exits unchanged:
market exits slip -0.5%, +4% tier resting/exact. H2 halt, H3 dedup (5-min, keyed to
fill time = trade time), H4 capacity (2 slots, fill-time chronology, tie = occupied)
identical to tonight's machinery.

---
## TEST A — ALL 4 LANES, LIMIT-IN (the hinge test)

**Fill rates (the cost of patience): v2 87% (1074/1234) · flat_top 86% (178/208) ·
vwap 83% (85/103) · grinder 71% (149/211).** 270 of 1,756 signals never fill.

| stage | N | total $ | daily mean $ | worst day $ |
|---|---|---|---|---|
| H1 limit-in frictions | 1486 | +464.87 | +12.91 | -591.79 |
| H2 halt exclusion (2 forced) | 1486 | +452.09 | +12.56 | -591.79 |
| H3 dedup (360 dropped) | 1126 | -222.58 | -6.18 | -284.76 |
| H4 capacity (539 skipped) | 587 | **+1,427.45** | **+39.65** | -202.64 |

H5: median **+$11.10** · green 19/36 = **53%** · half1 **-$11.84/d** / half2 +$91.14/d ·
worst -$202.64 (8/13) · best 8/07 +$897.21, ex-best mean **+$15.15** ·
per-entry: v2 N=411 **-$1,093.71** · flat_top N=49 +$502.77 · vwap N=26 +$1,396.30 (one-day
concentrated: 8/07) · grinder N=101 +$622.09.

| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$39.65 | **FAIL** |
| daily median | > +$50 | +$11.10 | **FAIL** |
| green days | >= 55% | 53% | **FAIL** |
| both halves positive | yes | half1 -$11.84/d | **FAIL** |
| worst day | > -$300 | -$202.64 | **PASS** |

**TEST A: FAIL — 1 of 5.** Limit-in DOES move the H1 hinge (+$12.91/d vs tonight's
-$19.91/d at the same stage — a ~$33/day swing from execution alone, at an 85%
blended fill rate) but the portfolio still cannot clear the bar: v2's -$1,094 drag
and the 8/07-concentrated vwap contribution remain.

---
## TEST B — SURVIVORS ONLY (grinder + flat_top)

### B(i) market-chase friction (tonight's model)
| stage | N | total $ | daily mean $ | worst day $ |
|---|---|---|---|---|
| H1 (-1% entry, -0.5% mkt exits) | 419 | +2,491.78 | +69.22 | -130.13 |
| H2 (1 forced) | 419 | +2,491.66 | +69.21 | -130.13 |
| H3 (0 dropped) | 419 | +2,491.66 | +69.21 | -130.13 |
| H4 (135 skipped) | 284 | **+2,165.07** | **+60.14** | -109.10 |

H5: median **+$7.11** · green 20/36 = 56% · half1 +$21.05/d / half2 +$99.23/d ·
best 8/07 +$1,034.33, **ex-best mean +$32.31** · flat_top N=163 +$867.47 · grinder N=121 +$1,297.59.

| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$60.14 | PASS |
| daily median | > +$50 | **+$7.11** | **FAIL** |
| green days | >= 55% | 56% | PASS |
| both halves positive | yes | +$21.05 / +$99.23 | PASS |
| worst day | > -$300 | -$109.10 | PASS |

**B(i): FAIL — 4 of 5. The failing criterion: MEDIAN.** Mean clears only on
concentration — 8/07 alone is +$1,034 of the +$2,165 total; the typical day is +$7.

### B(ii) limit-in (fill: flat_top 86%, grinder 71%)
| stage | N | total $ | daily mean $ | worst day $ |
|---|---|---|---|---|
| H1 limit-in | 327 | +1,286.31 | +35.73 | -123.66 |
| H2 (0 forced) | 327 | +1,286.31 | +35.73 | -123.66 |
| H3 (0 dropped) | 327 | +1,286.31 | +35.73 | -123.66 |
| H4 (79 skipped) | 248 | **+742.30** | **+20.62** | -123.66 |

H5: median +$10.06 · green 18/36 = 50% · half1 +$12.75/d / half2 +$28.49/d ·
worst -$123.66 (7/07) · best 8/11 +$273.74, ex-best +$13.39 ·
flat_top N=148 +$166.09 · grinder N=100 +$576.21.

| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$20.62 | **FAIL** |
| daily median | > +$50 | +$10.06 | **FAIL** |
| green days | >= 55% | 50% | **FAIL** |
| both halves positive | yes | yes | PASS |
| worst day | > -$300 | -$123.66 | PASS |

**B(ii): FAIL — 2 of 5.** The patience tax is real for the survivors: limit-in
LOWERS the survivor portfolio vs chase (+$20.62/d vs +$60.14/d) — the 29% of
grinder signals that never pull back $0.01 below the breakout are disproportionately
the winners (breakouts that run). Chase's -1% toll is cheaper than missing them.

---
## TEST C — CALIBRATED v2 (C1 anchor within 2% of VWAP · C2 confirm <=120s ·
C3 300s cooldown · C4 push = 5-min high · C5 stop >= 0.5%), in-window

**N = 1,259** — NOT far fewer than 1,231. The C1-C5 gates as specified do not
reduce frequency: C4's 5-min push (without the source's 2-min == 5-min high
equality condition) ADMITS setups the raw v2 rejected, roughly offsetting what
C1/C5 remove.

| model | N filled | total $ | per-trade mean $ |
|---|---|---|---|
| H0 gross (no friction) | 1259 | +3,411.92 | +2.71 |
| market-chase | 1259 | **-4,465.41** | -3.55 |
| limit-in (fill 87%, 167 missed) | 1092 | **-2,154.32** | -1.97 |

**TEST C: NO — the calibrated cohort's gross edge (+$2.71/trade) does NOT exceed
the toll under either model.** Calibration as specified is not a selection layer;
it is a re-parameterization at the same frequency and the same sub-toll edge. The
gate stack the Hidden Entry Architect blueprint calls for still does not exist in
tested form.

---
## HONEST READING
1. **Execution model is worth ~$33/day at H1 but does not rescue the book.** The
   -1% chase assumption was the hinge; replacing it moves every portfolio up and
   still fails the bar everywhere.
2. **The closest pass is B(i) — survivors under CHASE, 4/5, failing only median
   (+$7.11 vs +$50).** The survivors' edge is real but thin and concentrated
   (8/07 = 48% of the H4 total). At $500/position these two lanes are a
   +$30-60/day book on the mean and a +$7/day book on the typical day.
3. **Limit-in HURTS the survivors** (B(ii) < B(i)): grinder misses 29% of fills
   and the misses are the runners. If limit-in ships anywhere, it is for v2-class
   pullback entries, not breakout entries.
4. **v2 remains refuted as a raw lane under any tested execution** and the C1-C5
   calibration does not change that. Sub-toll edge at 1,200+ trades.
5. No tested configuration clears the pre-registered bar. Per the 8/8 doctrine:
   muddy = smaller + later, never launch-anyway.

## HAND-TRACE (Sim Integrity) — QTTB 2026-07-13, first v2 signal
Signal 13:30:30Z, bid 17.81, stop 17.28. Next bar 13:30:40 low 17.63 <= 17.80 ->
FILL at 17.81 (10s later). 13:31:10 half at 18.5224 (+4% of 17.81, resting/exact,
+$10.00 on 14.0371 sh). 13:31:30 trail: close 17.7099 < EMA90 18.0026, fill
17.6214 (x0.995), -$2.65 -> trade +$7.35. Hand math matches engine output exactly.
(Chase variant of the same signal: entry 17.9881, exits 13:35:00, +$16.27 —
matches tonight's trace line; path divergence is legitimate: different entry bar,
different scale timing.)

## Method notes
1. Fill-time (not signal-time) used as the trade's timestamp for H3 dedup ordering
   and H4 slot chronology — the moment capital is committed. Signals that never
   fill consume nothing.
2. Fill-bar stop check added (conservative): **202 of 1,486 Test-A fills (14%)**
   stop out on the very bar that filled them (bar traded through both bid and
   stop; stop-first law). Counted by a verification pass this session.
3. Detector sequencing unchanged (baseline engine open_until), same as engines of
   record; per-trade P&L re-simulated under each model.
4. Test C detector: C4 implemented as push = max high of trailing 30 bars (5 min),
   replacing the source's 12-bar==30-bar equality; C2 as 12-bar confirm window
   (source: 18); C1 filters the anchor list to within 2% of VWAP; C5 rejects
   stop width < 0.5%; C3 300s per-name cooldown post-signal.
5. Days with zero trades = $0 days; 36-day denominator throughout.
6. Raw outputs: `stress_B_out.json` (daily tapes + H5 for A, B(i), B(ii)).

## Officers touched
Wind Tunnel Engineer (limit-fill model + harness), Execution Surgeon (trade-through
fill rule, fill-bar stop conservatism), Systems Quant (import-reuse of the engine of
record, signal-count reconciliation 1,756 vs 1,753), Statistician (this entry),
Convexity Trader (median verdicts — B(i)'s mean-passes/median-fails is his exact
warning), Momentum Operator (no-ship reading), Quartermaster (cache drift 419->448
mid-evening; manifest retention defect noted — killtest outputs should be committed
with the run), Hidden Entry Architect (C1-C5 result: calibration-as-specified is
not the gate stack; blueprint still owes a selection layer), Trade Manager (exits
unchanged), Side Marshal / Crown Steward / Handicapper: clean (raw-lane test, no
gate stack in scope). Forward Architect: next registrable hypothesis, if any —
survivors-under-chase with a median-repair mechanism (position sizing or a third
uncorrelated lane), and limit-in restricted to pullback-class entries only.
