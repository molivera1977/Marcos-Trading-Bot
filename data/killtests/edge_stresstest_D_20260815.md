# EDGE STRESS-TEST D — THE SIZING TEST (run 8/14/2026 eve, filed 20260815)

**TEST G FAILS 0/5 — median -$41.64/day. Sizing does not repair the median; the
liquidity guard REVEALS that the edge lives in bars too thin to size into.**

Round four, pre-registered fresh. Script: `edge_stresstest_D_20260815.py` —
imports `edge_stresstest_C_20260815.py` (-> B -> engine of record); detectors,
sim, limit mechanics, H2-H4 machinery UNCHANGED. Bar identical and does NOT scale
with size (Marcos's floor): mean AND median > +$50/day, green >= 55%, both date
halves positive, worst > -$300.

## DATA
Same window/cache as round C: **421 in-window files, 36 dates 2026-06-25..2026-08-14**;
survivor signals 419 (flat_top 208, grinder 211), vwap 103 — exact match to B/C.

## SIZING MODEL (pre-registered)
F configuration (grinder chased post-11:00 + flat_top limit-in 9:30-10:30 + vwap
band-pass chased in-window), 2 slots, liquidity guard on the SIGNAL BAR's dollar
volume (close x volume of the 10s bar):
- >= $20,000 -> **$1,000 clip** (our clip <= 5% of that bar's traded dollars)
- >= $10,000 -> **$500 half clip**
- < $10,000 -> **skipped-for-size** (counted)

Chase entry slip: -1% at $500, **-1.5% at $1,000**.
**[CALIBRATION UNKNOWN - needs live $1k fills to verify]** — the -1.5% figure is
an assumption, not a measurement; so is keeping limit-in fills at signal price and
market-exit slip at -0.5% at the larger clip. Nothing here is fill-calibrated
above $500.

---
## TEST G — F CONFIG SIZED

Fill rates (incl. size-skips as misses): flat_top 95/208 = 46% (limit misses +
size skips) · grinder 117/211 = 55% · vwap 75/103 = 73%.

| stage | N | total $ | daily mean $ | worst day $ |
|---|---|---|---|---|
| H1 sized frictions | 287 | -2,174.37 | -60.40 | -372.75 |
| H2 halt exclusion (0 forced) | 287 | -2,174.37 | -60.40 | -372.75 |
| H3 dedup (5 dropped) | 282 | -2,097.30 | -58.26 | -372.75 |
| H4 capacity (70 skipped) | 212 | **-1,749.25** | **-48.59** | -361.68 |

H5: median **-$41.64** · green 9/36 = **25%** · half1 **-$93.56/d** / half2 -$3.62/d ·
worst -$361.68 (7/02) · best 8/11 +$401.31, ex-best mean **-$61.44** ·
flat_top N=68 +$559.76 · grinder N=76 -$374.48 · vwap N=68 -$1,934.52.

**Size census (signal level, per lane):**

| lane | $1,000 (dv>=20k) | $500 half (10-20k) | skipped-for-size (<10k) |
|---|---|---|---|
| flat_top | 94 | 13 | **101** |
| grinder | 92 | 25 | **94** |
| vwap | 68 | 7 | 28 |

Post-H4 fills by size: flat_top 59 full / 9 half · grinder 56 / 20 · vwap 61 / 7.

| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | -$48.59 | **FAIL** |
| daily median | > +$50 | -$41.64 | **FAIL** |
| green days | >= 55% | 25% | **FAIL** |
| both halves positive | yes | -$93.56 / -$3.62 | **FAIL** |
| worst day | > -$300 | -$361.68 | **FAIL** |

**TEST G: FAIL — 0 of 5.** Not a near-miss: every criterion, including the ones F
passed, inverts under the sized model.

### WHY — the decomposition (diagnostic, run at flat $500 under F's own execution;
`stress_D_decomp.log`)

Per-trade $ at flat $500, by liquidity cohort of the signal bar:

| lane | FULL (dv>=$20k) | HALF ($10-20k) | SKIP (dv<$10k) |
|---|---|---|---|
| flat_top | +$1.49 (83 fills) | -$1.49 (12) | **+$3.67 (83)** |
| grinder | **-$2.21 (92)** | +$2.57 (25) | **+$17.47 (94)** |
| vwap | **-$9.40 (68)** | -$0.44 (7) | **+$62.59 (28)** |

**The edge is concentrated almost entirely in the THIN bars (dv<$10k) — exactly
the trades the guard removes — and the liquid-bar cohort is a net LOSER even at
$500 with -1% slip.** The sign flip in G is ~selection, not the extra 0.5% slip:
sizing up trades a losing cohort bigger while deleting the paying one. High
dollar-volume signal bars on these names are climactic prints; the grinder/vwap
edge fires on quiet tape.

**Corollary that outranks this round: the $500 backtests themselves are
[CAPACITY-SUSPECT].** 94 of 211 grinder signals and 101 of 208 flat_top signals
print on bars where even our $500 clip is >5% of the bar's traded dollars. The
+$65.76/day of Test F leans on fills the tape may not have given us at ANY size.
(Honest counter-caveat: the guard reads ONE 10s bar; real tradability includes
neighboring bars' liquidity — the single-bar guard is deliberately strict. A
fairer guard, e.g. rolling 60s dollar volume, is a legitimate next
pre-registration before declaring the $500 book fictional.)

---
## TEST H — SALVAGE: grinder-from-10:30 SOLO

239 signals (C's `det_grinder_1030`, unchanged import).

| test | N (H4) | total $ | mean/d | median/d | green | halves /d | worst | verdict |
|---|---|---|---|---|---|---|---|---|
| H(i) $500 chase | 143 | +1,707.20 | **+$47.42** | **+$47.22** | 78% | +55.73 / +39.12 | -$67.26 | **FAIL 3/5** (mean short $2.58, median short $2.78) |
| H(ii) sized model | 84 | -304.11 | -$8.45 | $0.00 | 33% | -8.64 / -8.26 | -$215.98 | **FAIL 1/5** (worst only) |

H(i) is the closest ANY configuration has come to the bar in four rounds — 3/5
with both dollar criteria short by under $3/day, and by far the healthiest shape
ever recorded (78% green, worst -$67.26, ex-best +$42.41, halves both solidly
positive, 96 slot-skips = 2 slots saturate on this lane alone). H(ii) confirms
the G lesson on the solo lane: sized census full=101 / half=27 / **skip=111**;
the thin cohort is +$17.99/trade at $500, the liquid cohort -$1.89.

---
## HONEST READING
1. **Sizing is refuted as the path to the $50 typical day.** C closed saying the
   choice was "size or a new stream"; G answers: at 2 slots, size through an
   honest single-bar liquidity guard turns the book NEGATIVE (0/5). The dollars
   were never sitting in the liquid trades.
2. **The real finding outranks the test: the edge is a THIN-TAPE edge.** All
   three lanes earn their money on signal bars under $10k traded; the liquid
   cohort loses at $500. This puts a capacity question mark over every prior
   round's dollars — next pre-registration should be a fairer capacity guard
   (rolling 60s dollar volume) on the UNSIZED $500 book before anything else.
3. **Salvage found: grinder-from-10:30 solo at $500 is the best single
   configuration in four rounds** — 3/5, mean +$47.42 / median +$47.22 (each
   under $3 short), 78% green, worst -$67.26. It still does not pass, and per
   the 8/8 doctrine no-pass = smaller + later, never launch-anyway.
4. Slippage-at-size remains **[CALIBRATION UNKNOWN]** — but note G would fail on
   selection alone even at $500 economics (decomposition table); better $1k slip
   assumptions cannot rescue it.

## HAND-TRACE (Sim Integrity)
FCUV 2026-06-25 13:37:30Z vwap, first chased $1,000 trade of Test G: signal bar
close 6.46 x vol 58,719 = $379,324.74 dv -> full clip. Entry 6.46 x 1.015 =
6.5569, sh = 1000/6.5569 = 152.5111, stop 5.80 hit next bar (low 5.75), fill
5.80 x 0.995 = 5.7710: pnl = 152.5111 x (5.7710 - 6.5569) = **-$119.8585** —
engine -$119.8585, exact match. (Limit-fill and chase mechanics themselves =
rounds B/C traces; imported unchanged.)

## Method notes
1. Size stamped per signal from the signal bar's close x volume before the
   pipeline; `exec_sized` dispatches F's mix (flat_top -> B.sim_limit, else
   chase) with E.POS set per trade and chase entry_slip 0.010/0.015 by size;
   size-skips return unfilled and are counted per lane. Pipeline = round B's
   verbatim.
2. Decomposition run is DIAGNOSTIC (post-hoc, flat $500, no capacity stage) —
   used to attribute G's failure, not to grade any configuration.
3. Test H reuses C's `det_grinder_1030` by import; solo lane, same pipeline.
4. Raw outputs committed: `stress_D_out.json`, `stress_D_run.log`,
   `stress_D_decomp.log`.

## Officers touched
Wind Tunnel Engineer (sized execution harness; single-bar guard design),
Execution Surgeon (slip-at-size assumption flagged [CALIBRATION UNKNOWN];
size-census accounting), Convexity Trader (verdicts; H(i)'s tail shape noted as
best-ever), Systems Quant (import chain D->C->B->engine; signal counts 419/103
reconciled exact; FCUV trace to the cent), Statistician (this entry + artifacts),
Momentum Operator (no-ship; thin-tape finding), Feed Engineer (10s bar dollar-vol
as liquidity proxy — single-bar strictness disclosed), Forward Architect (next
registrables: rolling-60s capacity guard on the $500 book; grinder-1030-solo
+ one uncorrelated stream), Quartermaster (cache stable 421, outputs committed),
Seam Scientist (no sweep — one pre-registered sizing model, one diagnostic),
First Hour / Trade Manager (exits unchanged), Side Marshal / Crown Steward /
Handicapper / Historian: clean (raw-lane test, no gate stack in scope).
