# EDGE STRESS-TEST E — FAIR CAPACITY + THE PRE STREAM (run 8/14 eve, filed 20260815)

**NEITHER TEST-I ARM PASSES (I(i) 0/5 median -$42.25; I(ii) 1/5 median $0.00),
and TEST K FAILS 3/5 — mean +$28.01, median +$34.24, both dollar criteria short.
The PRE stream as detected SUBTRACTS: K is worse in dollars than grinder-solo
alone (D's H(i) +$47.42/+$47.22).**

Round five, pre-registered fresh. Script: `edge_stresstest_E_20260815.py` —
imports `edge_stresstest_D_20260815.py` (-> C -> B -> engine of record);
detectors, sim, limit mechanics, H2-H4 machinery UNCHANGED. Same bar (does not
scale): mean AND median > +$50/day, green >= 55%, both halves positive,
worst > -$300.

## DATA
Same window/cache: **421 in-window files, 36 dates 2026-06-25..2026-08-14**;
survivor signals 419 (flat_top 208, grinder 211), vwap 103, grinder-1030 solo
239 — exact match to C/D.

### PRE COVERAGE DISCLOSURE (per-file detail: `stress_E_coverage.json`)
- 421 files: **416 have >=1 premarket bar** (5 have none — first bar 13:30Z).
- First-bar time: min/median 08:00:00Z (**04:00 ET — confirmed**), max 13:30Z;
  **350/421 files start at 04:00 ET**.
- 07:00-09:25 ET window bars (max 872 10s bars): min 0, median 455, mean 449,
  max 871 — premarket 10s coverage is real but ~half-dense (thin names print
  sparse premarket bars).
- **310/421 files clear the same 60-bar minimum the RTH engine uses** and enter
  TEST J; the rest are excluded (disclosed, same law as RTH).

---
## TEST I — FAIR CAPACITY GUARD (rolling-60s)

Guard: sum of dollar volume over the 6 bars starting at the signal bar
(i..i+5): >= $40,000 -> $1,000 clip (<=2.5% of the minute's dollars);
>= $20,000 -> $500 half; else skip. Slippage schedule = round D's (-1% at
$500, -1.5% at $1,000) **[CALIBRATION UNKNOWN]**. Disclosed: the window reads
bars i+1..i+5 — legitimate as a would-the-minute-have-absorbed-us capacity
assessment, but NOT a live-tradeable filter as written (live needs trailing
volume).

### I(i) — F config sized (re-run of D's TEST G under the fair guard)
Fill rates (misses incl. size-skips): flat_top 55% · grinder 63% · vwap 82%.

| stage | N | total $ | daily mean $ | worst day $ |
|---|---|---|---|---|
| H1 sized frictions | 331 | -1,062.93 | -29.53 | -431.97 |
| H2 halt exclusion (0 forced) | 331 | -1,062.93 | -29.53 | -431.97 |
| H3 dedup (5 dropped) | 326 | -969.31 | -26.93 | -431.97 |
| H4 capacity (91 skipped) | 235 | **-553.75** | **-15.38** | -361.68 |

H5: median **-$42.25** · green 12/36 = 33% · halves -$84.98/d / +$54.21/d ·
worst -$361.68 (7/02) · best 8/07 +$1,157.57, ex-best **-$48.89** ·
flat_top N=78 +$692.03 · grinder N=82 -$200.16 · vwap N=75 -$1,045.62.

Size census (signal level): flat_top full=116/half=14/skip=78 · grinder
117/16/78 · vwap 76/8/19. Post-H4 fills: flat_top 70/8 · grinder 73/9 ·
vwap 67/8.

| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | -$15.38 | **FAIL** |
| daily median | > +$50 | -$42.25 | **FAIL** |
| green days | >= 55% | 33% | **FAIL** |
| both halves positive | yes | -$84.98 / +$54.21 | **FAIL** |
| worst day | > -$300 | -$361.68 | **FAIL** |

**I(i): FAIL 0/5.** The fair guard softens G (total -$554 vs -$1,749; ~30 more
signals sized up) but the sign does not flip: the sized F book stays negative
and the median is nearly unchanged (-$42.25 vs G's -$41.64). D's thin-tape
finding survives the fairness objection — the strict single-bar guard was NOT
what failed G.

### I(ii) — grinder-1030 solo sized (fair guard; D's H(ii) re-run)
Census: full=128 / half=19 / **skip=92** (D's single-bar guard: 101/27/111 —
the fair guard promotes ~20 signals, the skip cohort barely moves).

| stage | N | total $ | mean/d | median/d | green | halves /d | worst |
|---|---|---|---|---|---|---|---|
| H4 (52 slot-skips) | 95 | **+$76.15** | +$2.12 | $0.00 | 42% | -15.69 / +19.92 | -$257.57 |

| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$2.12 | **FAIL** |
| daily median | > +$50 | $0.00 | **FAIL** |
| green days | >= 55% | 42% | **FAIL** |
| both halves positive | yes | -$15.69 / +$19.92 | **FAIL** |
| worst day | > -$300 | -$257.57 | **PASS** |

**I(ii): FAIL 1/5** (vs D's H(ii) 1/5 at -$8.45/d — fair guard flips the total
barely positive, +$0.80/trade, still nowhere near the bar).

**TEST I verdict: the "deliberately harsh" objection is answered — a 60s
rolling guard at 2.5%-of-minute participation does NOT rescue sizing. Neither
arm passes; the edge remains a thin-tape edge that cannot absorb $1,000 clips.**

---
## TEST J — THE PRE STREAM (solo)

flat_top + vwap band-pass on the 07:00-09:25 ET premarket window; $500 chased
-1%; uniform exits with truncation at 09:25 (final-bar EOD exit = the bot's
PRE flatten, -0.5% mkt slip). 409 signals (pre_flat_top 311, pre_vwap 98);
fill rate 100% (chase).

| stage | N | total $ | mean/d | worst |
|---|---|---|---|---|
| H1 | 409 | -923.37 | -25.65 | -331.46 |
| H2 (1 halt-gap forced) | 409 | -954.81 | -26.52 | -331.46 |
| H3 (10 dropped) | 399 | -1,028.68 | -28.57 | -300.76 |
| H4 (96 slot-skips) | 303 | **-698.82** | **-19.41** | -281.25 |

**J solo: N=303 · winners 113 = win% 37% · total -$698.82 · mean -$19.41/day ·
median -$29.16/day** · green 15/36 = 42% · halves -$53.41/+$14.58 · worst
-$281.25 (7/17). Split: **pre_flat_top N=230 -$1,251.00 (the loser) ·
pre_vwap N=73 +$552.18 (positive)**. FAIL 1/5 (worst only).

---
## TEST K — grinder-1030 solo ($500 chase, D's exact spec) + PRE stream, 2 slots

| stage | N | total $ | mean/d | worst |
|---|---|---|---|---|
| H1 | 648 | +1,014.65 | +28.18 | -305.07 |
| H2 (1 forced) | 648 | +983.20 | +27.31 | -305.07 |
| H3 (10 dropped) | 638 | +909.34 | +25.26 | -274.38 |
| H4 (192 slot-skips) | 446 | **+1,008.38** | **+28.01** | -254.86 |

H5: mean **+$28.01** · median **+$34.24** · green 22/36 = **61%** · halves
+$2.32/d / +$53.70/d · worst -$254.86 (7/17) · best 8/10 +$361.98 · ex-best
+$18.47 · grinder N=143 +$1,707.20 (identical to D's H(i) — no time overlap
with PRE, so the streams never contest slots) · pre_flat_top N=230 -$1,251.00
· pre_vwap N=73 +$552.18.

| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$28.01 | **FAIL** |
| daily median | > +$50 | +$34.24 | **FAIL** |
| green days | >= 55% | 61% | **PASS** |
| both halves positive | yes | +$2.32 / +$53.70 | **PASS** |
| worst day | > -$300 | -$254.86 | **PASS** |

**TEST K: FAIL 3/5.** Same count as D's H(i) but WORSE where it matters: the
PRE stream added -$698.82, dragging mean from +$47.42 to +$28.01, median
+$47.22 -> +$34.24, and green days from 78% down to 61% (red PRE mornings
turn formerly-green grinder days red). The combined book is not an
improvement on grinder-solo; it is grinder-solo minus $700 of PRE bleed.

## HONEST READING
1. **The fair-capacity objection is closed.** Rolling-60s at 2.5% participation
   promotes ~30 F-config signals and ~20 grinder signals to full clips, halves
   G's losses — and still fails 0/5 with the same median. Sizing through ANY
   honest guard has now failed twice; the thin-tape finding stands.
2. **The PRE stream, as these detectors read it, is not the second stream.**
   Premarket flat_top is the worst cohort tested in five rounds (-$5.44/trade,
   N=230). The one positive: **pre_vwap band-pass (+$552.18, N=73,
   +$7.56/trade)** — a registrable candidate for a future round SOLO, but
   per the sweep laws it was not pre-registered alone tonight and gets no
   verdict here.
3. **grinder-1030 solo at $500 (D's H(i), 3/5, short <$3/day on both dollar
   bars) remains the best configuration in five rounds.** Nothing tonight beat
   it; K diluted it. Per the 8/8 doctrine: no pass = smaller + later, never
   launch-anyway.
4. Slippage at size remains **[CALIBRATION UNKNOWN]**; premarket chase slip at
   -1% on thin 04:00-tape names is likewise an assumption, flagged the same.

## HAND-TRACES (Sim Integrity)
**PRE trade** — KUST 2026-06-25 11:36:00Z pre_vwap, entry_sig 2.4000 stop
1.6500: entry 2.4000x1.01=2.4240, sh=500/2.4240=206.2706; half scale at
2.4240x1.04=2.5210 -> +$10.0000; trail exit 11:53:20Z close 2.75 < EMA90
2.7611, fill 2.75x0.995=2.73625: 103.1353x(2.73625-2.4240)=+$32.2040; total
**+$42.2040** — engine +$42.2040, exact. (The 09:25-flatten mechanic = the
truncated array's EOD exit; exercised by the N=... eod exits, e.g. GIPR 7/17
13:04:00Z exit=eod at the 13:25Z bar.)
**K day** — 2026-07-17 (worst day): 20 post-H4 trades listed in
`stress_E_run.log` (12 PRE incl. GIPR eod-flatten, 8 grinder), hand-sum
-$254.86 = daily table -$254.86, exact.

## Method notes
1. TEST I re-stamps sizes with the rolling-60s guard and reuses D's
   `exec_sized` verbatim (dispatch, slip schedule, census). Forward-looking
   window (i..i+5) disclosed as capacity-assessment-only, not live-tradeable.
2. PRE days registered in E.DAYS under ("PRE:"+sym, date) with bars truncated
   at 13:25Z; pipeline (H1-H4), dedup and 2-slot capacity walk = round B's
   verbatim, keys chronological across PRE (11:00-13:25Z) and RTH (14:30Z+).
   PRE detectors = engine's det_flat_top/det_vwap unchanged, window-local
   VWAP/EMA (no RTH contamination, no lookahead).
3. K's grinder arm = C's det_grinder_1030 import, $500 B.sim_chase — byte-for-
   byte D's H(i) spec; reconciles exactly (N=143, +$1,707.20).
4. Raw outputs committed: `stress_E_out.json`, `stress_E_coverage.json`,
   `stress_E_run.log`.

## Officers touched
Wind Tunnel Engineer (rolling-60s guard design + forward-window disclosure;
PRE truncation-as-flatten mechanic), Feed Engineer (premarket 10s coverage
audit: 416/421 files, 350 at 04:00 ET, median 455 window bars), Execution
Surgeon (slip-at-size and premarket-slip both [CALIBRATION UNKNOWN]),
Convexity Trader (verdicts; K's dilution of H(i) called), Systems Quant
(import chain E->D->C->B->engine; grinder arm reconciled to the cent vs D;
KUST trace + 7/17 day-sum exact), Statistician (this entry + artifacts),
Momentum Operator (no-ship; pre_vwap flagged as hypothesis only), Forward
Architect (registrable next: pre_vwap SOLO pre-registered; live trailing-
volume capacity guard), Seam Scientist (no sweep — guard thresholds and PRE
window pre-registered in the prompt), Opening Bell (PRE window 07:00-09:25 +
09:25 flatten = the bot's rule, honored), Quartermaster (cache stable 421;
outputs committed), First Hour / Trade Manager (exits unchanged), Side
Marshal / Crown Steward / Handicapper / Historian: clean (raw-lane test, no
gate stack in scope).
