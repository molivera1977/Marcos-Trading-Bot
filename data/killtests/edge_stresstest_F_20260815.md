# EDGE STRESS-TEST F — THE EXIT SWEEP (run 8/14/2026 eve, filed 20260815)

**E3 (bank 1/2 at +10%, trail rest 10%-off-high) PASSES ALL 5 CRITERIA — the first
full pass in six rounds: mean +$94.96/d, MEDIAN +$62.09/d, green 81%, halves
+$81.03/+$108.90, worst -$115.00.** Marcos was right: every prior round graded the
entries through the timid uniform exit; the runners were being amputated at +4%.

Round six, pre-registered fresh. Script: `edge_stresstest_F_20260815.py` —
imports `edge_stresstest_C_20260815.py` (-> B -> engine of record); detectors,
chase mechanics, H2-H4 machinery UNCHANGED. Same 421 in-window files, 36 dates
2026-06-25..2026-08-14, same bar: mean AND median > +$50/day, green >= 55%,
both halves positive, worst > -$300.

## FIXED ENTRIES (no entry changes, both chased at $500, -1% entry slip)
- **grinder-solo post-10:30** (round D TEST H spec, `C.det_grinder_1030`) — 239 signals
- **flat_top real-retest in-window 9:30-10:30 ET**, chased — 208 signals

## EXIT VARIANTS (stop ALWAYS live, stop-first ties, -0.5% on all market exits;
bank tiers = resting limits, exact; grinder keeps its 19:59Z flatten in all variants)
- **E1** baseline control: bank 1/2 at +4%, trail EMA90 (grinder breakeven kept — engine of record verbatim)
- **E2** runner-first: bank 1/4 at +4%, trail 3/4 EMA90
- **E3** let-it-breathe: bank 1/2 at +10%, trail rest 10%-off-high (closes-through), no breakeven
- **E4** no-bank pure trail: 100% on 10%-off-high from entry, EOD flatten, no breakeven
- **E5** breakeven-runner: bank 1/2 at +4%, stop -> breakeven, hold rest to EOD

**RECONCILE (control):** grinder-solo E1 through the full H1-H4 pipeline:
N=143, total **+$1,707.20**, mean +$47.42, median +$47.22, worst -$67.26 —
**exact match to round D TEST H(i) to the cent.**

## PER-ENTRY x VARIANT (post-H2 halt + H3 dedup; NO capacity stage so N is constant
across variants — hold length changes slot occupancy, graded only in the portfolio)

### grinder-1030 solo (N=239 all variants)
| var | win% | total $ | mean/trade | daily mean | daily MEDIAN | worst day | best trade |
|---|---|---|---|---|---|---|---|
| E1 | 62% | +1,938.02 | +8.11 | +53.83 | +55.44 | -73.21 | +250.40 (CIGL 6/30) |
| E2 | 62% | +2,331.41 | +9.75 | +64.76 | +56.85 | -93.38 | +365.61 (CIGL 6/30) |
| E3 | 56% | **+5,483.15** | +22.94 | +152.31 | **+108.09** | -73.21 | +163.75 (LGHL 7/28) |
| E4 | 54% | **+6,919.05** | **+28.95** | **+192.20** | +109.77 | -89.67 | +277.49 (LGHL 7/28) |
| E5 | 62% | +2,444.43 | +10.23 | +67.90 | +54.50 | -91.52 | +251.55 (CIGL 6/30) |

### flat_top in-window chased (N=208 all variants)
| var | win% | total $ | mean/trade | daily mean | daily MEDIAN | worst day | best trade |
|---|---|---|---|---|---|---|---|
| E1 | 43% | +989.12 | +4.76 | +27.48 | -12.24 | -164.39 | **+1,082.27** (YJ 8/07) |
| E2 | 37% | +1,841.42 | +8.85 | +51.15 | -17.69 | -164.39 | **+1,613.40** (YJ 8/07) |
| E3 | 37% | +1,279.62 | +6.15 | +35.54 | **+37.79** | -164.39 | +210.75 (YJ 8/07) |
| E4 | 29% | +1,929.76 | +9.28 | +53.60 | **+41.61** | -164.39 | +371.49 (YJ 8/07) |
| E5 | 46% | -57.91 | -0.28 | -1.61 | -7.50 | -164.39 | +216.74 (SDOT 6/29) |

The exit sweep TRIPLES the grinder lane's dollars (E1 +$1,938 -> E4 +$6,919) with
zero entry changes — the lane keeps grinding higher after +4% and the EMA90 trail
was selling the middle of the move. flat_top's daily MEDIAN flips positive only
under the off-high trails (E3/E4): win% falls (29-37%) but losers stay stop-sized
while winners get paid — Convexity Trader's exact prescription.

## PORTFOLIO (grinder + flat_top, 2 slots, full H1-H4 walk, 36 days)

| var | N(H4) | total $ | mean/d | MEDIAN/d | green | halves /d | worst | ex-best | verdict |
|---|---|---|---|---|---|---|---|---|---|
| E1 | 298 | +2,334.46 | +64.85 | +17.74 | 61% | +25.61/+104.08 | -100.35 | +37.15 | FAIL 4/5 (median) |
| E2 | 298 | +3,363.21 | +93.42 | +23.71 | 56% | +36.67/+150.18 | -109.04 | +51.52 | FAIL 4/5 (median) |
| **E3** | 238 | **+3,418.71** | **+94.96** | **+62.09** | **81%** | **+81.03/+108.90** | **-115.00** | **+86.20** | **PASS 5/5** |
| E4 | 241 | +4,266.85 | +118.52 | +44.50 | 69% | +102.71/+134.34 | -134.06 | +105.24 | FAIL 4/5 (median) |
| E5 | 242 | +1,102.23 | +30.62 | +22.56 | 58% | +45.67/+15.56 | -132.02 | +23.26 | FAIL 3/5 |

| criterion | bar | E3 actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$94.96 | **PASS** |
| daily median | > +$50 | +$62.09 | **PASS** |
| green days | >= 55% | 81% (29/36) | **PASS** |
| both halves positive | yes | +$81.03/d, +$108.90/d | **PASS** |
| worst day | > -$300 | -$115.00 (8/14) | **PASS** |

**FIRST LINE ANSWER: YES — E3 (bank 1/2 at +10%, 10%-off-high trail on the rest)
carries the grinder+flat_top 2-slot portfolio past ALL FIVE criteria.** It is also
the healthiest shape ever recorded: 81% green, ex-best +$86.20/d (not one-day-
driven), both halves comfortably positive, per-entry E3 contribution flat_top
N=156 +$629.39 / grinder N=82 +$2,789.31. E4 makes more total money (+$4,266.85,
mean +$118.52) but its median ($44.50) fails — no bank means whole red days when
nothing trends.

## HONEST READING
1. **This is a best-of-5 sweep — selection risk is real.** E3 was one of five
   pre-registered variants; the pass margin on median is +$12.09/day. Doctrine:
   this does NOT green-light go-live by itself; it nominates E3 for the OOS wall
   (forward days 8/17+ under paper) before any live switch. 8/8 law stands:
   smaller + later, never launch-anyway.
2. **The [CAPACITY-SUSPECT] flag from round D still applies to these dollars.**
   Same $500 book, same thin signal bars; the exit sweep does not answer the
   liquidity question — it changes only where we SELL. Wider trails also mean
   exits later, on different (sometimes thinner) bars.
3. **Slippage disclosure: wider trails eat more slippage.** Every trail/stop/EOD
   exit is a market exit at -0.5%; E3/E4 exit further from the signal print and
   the -0.5% flat assumption is least trustworthy exactly there (fast tape,
   10% off a spike high). The YJ trace below shows E3 exiting into a -12%
   pullback bar — real fills there could be worse than modeled.
4. **The two trails serve different regimes.** EMA90 captured the YJ 8x rocket
   best (+$1,613 on E2) because it never looks back at the high; the 10%-off-high
   trail banked early on YJ but wins the PORTFOLIO because most winners are
   grinders, not 8-baggers. The median is made by E3; the tail is made by EMA.
   A regime-aware trail is Forward Architect material, NOT licensed by this round.
5. E5 (free-roll) is refuted as a runner vehicle: breakeven-after-bank churns
   winners back to $0 (YJ trace: stopped at BE 10 seconds after banking, +$8.75
   on an 8-bagger day) and flat_top goes net NEGATIVE.

## HAND-TRACE (Sim Integrity) — YJ 2026-08-07, THE rocket day
Requested YJ 8/07 grinder: **no grinder-1030 signal fired on YJ that day** (it
never printed a qualifying quiet-pullback new high post-14:30Z); per
pre-registration, traced the biggest E4 winner instead = **YJ 8/07 flat_top**,
signal 13:51:50Z, sig 1.6391, chase entry 1.6555 (+1%), stop 1.4900, 302.03 sh.
YJ ran 1.64 -> 13.98 intraday (the 8x rocket).
- **E1**: bank 151.01 sh at 1.7217 (13:52:20); EMA90 trail rides the FULL rocket,
  exit close 8.80 < EMA90 9.1393 at 16:04:50, fill 8.7560 -> **+$1,082.27**
- **E2**: same path, 3/4 rides -> **+$1,613.40** (best single trade of the round)
- **E3**: bank half at +10% = 1.8210 (13:54:30); runhi 3.30 by 14:21:10, close
  2.90 < 2.97 (10% off) -> trail out 2.8855 -> **+$210.75** (sells the rocket at
  $2.90; it went to $13.98)
- **E4**: no bank; same 14:21:10 off-high trail, full size -> **+$371.49**
- **E5**: bank at +4% 13:52:20, stop->BE; very next bar low 1.6500 <= 1.6555
  stops the runner at breakeven -> **+$8.75**
Engine agreement: each figure above is the engine's own pnl (log lines printed
from inside the sim); E1's +$1,082.27 equals the flat_top E1 best-trade cell.

## Method notes
1. `sim_var` mirrors the engine of record's bar loop exactly (flatten -> haltgap ->
   stop -> bank(continue) -> run-high update -> trail check); E1 reconciled to the
   cent against round D H(i) through the full pipeline before anything else ran.
2. run_high starts at the ENTRY price and updates from post-entry bar highs only —
   no lookahead; off-high trail fires on close < 0.90*run_high; bank tiers fill
   at the limit exactly (b.h >= target), stop checked before bank on every bar.
3. Per-entry tables graded at H3 (halt rule ON, dedup ON, no capacity) so N is
   identical across variants; the H4 slot walk is applied in the portfolio runs
   (E3 slot-skips 209 vs E1's 149 — longer holds occupy slots longer, disclosed).
4. Raw outputs committed: `stress_F_out.json`, `stress_F_run.log`.

## Officers touched
Trade Manager (LEAD — the exit was the defect; E3 nominated), Convexity Trader
(median-by-trail confirmed; E5 free-roll refuted; tail-vs-median split named),
Wind Tunnel Engineer (sim_var harness; closes-through trail law; no-lookahead
run-high), Systems Quant (E1 reconciled to the cent, N=143/+$1,707.20; YJ trace
engine-log verified), Execution Surgeon (-0.5% flat exit slip flagged least
trustworthy on off-high exits into fast tape), Statistician (this entry +
artifacts), Momentum Operator (no-ship: 5/5 nominates E3 for the OOS wall, does
not launch it), Seam Scientist (best-of-5 selection risk logged; OOS >= 5 forward
days required), Forward Architect (regime-aware trail registered as hypothesis
only), Strength Ombudsman (E5's BE-stop churning an 8-bagger to +$8.75 = the
strength-refusing bias in exit form, on the record), First Hour (flat_top window
unchanged; YJ 8/07 open attribution), Quartermaster (cache stable 421; outputs
committed), Historian (first 5/5 in program history, so stamped), Side Marshal /
Crown Steward / Handicapper / Feed Engineer / Kev Librarian: clean (no gate
stack, no feed, no corpus change in scope).
