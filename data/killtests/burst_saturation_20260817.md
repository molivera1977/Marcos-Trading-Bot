# DEFECT 1a — KEVSEQ BURST SATURATION (kill-test) — 2026-08-17

## FAILURE CONDITION (pre-registered, written BEFORE the run)

This work is WRONG if any of the following hold:

1. **The saturation claim is not reproduced.** If, on the universe replay, the
   `no_burst` refusal rate on the RUNNER cohort (name-day max gain >= 25%) is
   NOT materially higher than on the rest, the "self-defeating on exactly the
   names it exists to catch" story is a narrative, not a defect, and every
   variant below is a solution to nothing. State it and stop.
2. **No variant beats baseline on BOTH halves of the OOS split**
   (MINE 2026-05-18..07-21 / HOLD-OUT 07-22..08-14, E3 live-parity, $500).
   A variant that wins on MINE and loses on HOLD-OUT is REFUTED, not "promising".
3. **The extra fires are junk.** A variant that raises N but lowers $/trade on
   HOLD-OUT is buying volume with money. Refuted.
4. **HOLD-OUT N < 20** for the chosen arm => UNDERPOWERED => ship OFF regardless
   of sign.
5. Runner-cohort split not reported => the deliverable is incomplete.

## DEFAULT POSTURE (stated before the numbers)

Burst is a **money-changing gate**. Per `feedback_auditor_cannot_authorize_behavior`,
nothing here ships ON unless the kill-test is positive on BOTH halves; otherwise the
env switch ships with the value **0 (today's behaviour)** and the number is stated
for Marcos to price.

## THE DEFECT

`kevseq_step` (marcos_trading_bot.py :6396-6417) requires fill-bar volume >= the
75th percentile of the **trailing** 30 bars. On a sustained vertical runner every
bar is heavy, so the trailing baseline rises with the move and no bar can clear it.
Live proof (8/17 decisions archive): WFF refused 8 times `no_burst`/`burst_unmeasured`
at $2.99 / $3.34 / $3.91 / $3.63 / $5.74 / $6.94 / $7.73 / $10.15 while the name ran
$1.61 -> $10.15 (+530%). Same class as the A/X detector saturation in
`seq_enriched_alphabet_20260817.md`.

## VARIANTS (pre-registered)

- **V0 baseline** — v >= p75(trailing 30). Today.
- **V1 pre-run** — p75 computed on the 30 bars BEFORE the current leg's first B bar.
- **V2 OR-floor** — V0 OR v >= X * median(session bars so far), X in {1.5, 2, 3}.
- **V3 dollar-volume** — the same trailing p75 but on v*close.
- **V4 no burst** — clause dropped entirely (the Rosetta had burst 78% vs 55% control:
  real, but the SEQUENCE was the discriminator).

Each graded on ALL / MINE / HOLD-OUT, and separately on RUNNER (name-day max gain
>= 25%) vs REST, under BOTH entry models (baseline quote entry, and the F3
limit-at-fire entry that `entry_drift_20260817` chose).

## RESULTS (run: burst_saturation_20260817_run.txt / _out.json)

Universe 738 files / 736 graded name-days / 63 dates (2026-05-18 .. 2026-08-17).
2,251 kevseq candidate fills (all live clauses applied EXCEPT burst and the leg cap;
the leg cap is applied per-variant, in bar order, because a looser variant burns it faster).

### FC#1 — is burst saturating? PARTLY CONFIRMED, and the split as specified is degenerate

The RUNNER(>=25%) / REST split carries **no information**: kevseq's own day-gain>=20%
floor already pre-selects runners, so REST holds 1 candidate out of 2,251. Reported
honestly rather than dressed up. The claim is really about run INTENSITY, so:

| name-day max gain | candidates | pass burst | no_burst rate |
|---|---|---|---|
| 20-50%   | 186 | 110 | 40.9% |
| 50-100%  | 841 | 528 | 37.2% |
| 100-200% | 757 | 415 | 45.2% |
| 200%+    | 467 | 235 | **49.7%** |

Refusal DOES rise with run intensity (37% -> 50%). The mechanism described in the
ticket is real: on a sustained vertical the trailing p75 baseline climbs with the move.

### FC#2/#3 — but every loosening LOSES MONEY. All variants REFUTED.

$/trade, E3 live-parity $500. Baseline entry (today's quote) and F3 limit-at-fire.

| variant | MINE | HOLD-OUT | MINE (F3) | HOLD-OUT (F3) |
|---|---|---|---|---|
| **V0 baseline (trailing p75)** | **-3.54** | **-2.46** | **-0.56** | **-0.73** |
| V1 pre-run p75 | -3.21 | -2.95 | -0.97 | -1.38 |
| V2 OR sess-median x1.5 | -4.16 | -4.12 | -3.55 | -3.33 |
| V2 OR sess-median x2 | -4.06 | -3.96 | -3.14 | -3.02 |
| V2 OR sess-median x3 | -3.98 | -3.61 | -2.85 | -2.74 |
| V3 dollar-volume p75 | -3.57 | -3.17 | -0.94 | -1.34 |
| V4 no burst at all | -4.64 | -3.83 | -4.08 | -3.66 |

**Zero variants pass FC#2.** Not one beats baseline on both halves; most lose on both.
V1 (the ticket's preferred candidate (i)) buys +11% N and pays for it: HOLD-OUT
-2.95 vs -2.46, and -1.38 vs -0.73 under F3. V4 (drop burst) is the worst arm tested
on every cohort — the Rosetta's 78%-vs-55% signal is real and burst is **earning it**.

### RUNNER-COHORT SPLIT (the critical ask) — and the actual discovery

| cohort (F3 limit entry) | V0 N | V0 $/tr | V4 no-burst N | V4 $/tr |
|---|---|---|---|---|
| ALL | 1257 | -0.49 | 2190 | -3.83 |
| VERTICAL 100%+ | 628 | **+10.00** | 1182 | +2.52 |
| VERTICAL 100%+ / HOLD-OUT | 174 | **+9.34** | 320 | +3.58 |

**Burst is not blocking the runners — it is what makes the runner cohort profitable.**
On the 100%+ vertical cohort the strictest variant is the BEST variant, out of sample,
N=174 (powered). Loosening burst there costs -$5.76/trade.

The real finding is not about burst at all: **kevseq's entire edge lives in the 100%+
vertical cohort** (+$9.34/tr HOLD-OUT) while the lane is net-negative everywhere else
(-$0.73/tr ALL). That is a runner-conditional APPLICATION question — a day-gain floor
far above the current 20% — and it changes what the bot does with money, so it is
Marcos's to price, not an auditor's to ship
(`feedback_auditor_cannot_authorize_behavior`).

## VERDICT

**DEFECT 1a REFUTED as a money defect.** The saturation is measurable and the
mechanism is exactly as described, but every fix candidate (i)-(iv) is net-negative
on both halves of the OOS split. **NO CODE CHANGE SHIPPED for 1a.** Shipping a
"fix" here would have cost money on the very cohort it was meant to help.

Kill-switch/env: none added — there is nothing to switch. Adding a dead env knob for
a refuted mechanism is config debt.

**FOR MARCOS (spec tension, unresolved):** kevseq at KEVSEQ_GAIN_MIN=20 is a
money-loser in aggregate; kevseq restricted to 100%+ verticals is +$9.34/tr out of
sample on N=174. Raising the floor is a behaviour change. Priced and waiting.

