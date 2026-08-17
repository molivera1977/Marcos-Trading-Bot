# LIQUIDITY-CONDITIONAL SIZE-UP KILL-TEST — `T B` — 8/17/26

**VERDICT: grinder LIFT-SURVIVES-GUARD (+$12.34/fire, p=0.007) · break-attack
LIFT-NOT-CONFIRMED under guard (+$12.94/fire but p=0.075 — indistinguishable from
relabeling at N=18). CONDITIONAL UPSIZE: NO-LIFT — no grid cell beats flat-$500
total with same-or-better worst-case; every extra dollar in every cell is bought
with a worse worst fire, under [CALIBRATION UNKNOWN] slip.**

Script: `seq_conditional_size_20260817.py` (raw: `_run.txt`, `_out.json`).
Machinery = `seq_sizeup_capacity_20260817.py` reused EXACTLY (pilot chain, E3
live-parity exits, D guard dv≥20C full / ≥10C half / else skip $0, slip anchored
$500→−1.0% / $1,000→−1.5% linear — **[CALIBRATION UNKNOWN] above $500**, no live
fills above $500 exist). Cohorts = the wall's hold-out (18 dates 2026-07-22..
2026-08-14): FULL books 187 BA / 142 grinder; gated `T B` 18 / 27.

## 1) THE MISSING CELL — does the `T B` lift survive the liquidity guard?

Both books re-run under the D guard at flat $500 (skips = $0, counted):

| lane | ungated-under-guard $/fire (N) | gated-under-guard $/fire (N) | lift under guard | no-guard wall lift | perm p (5000 relabels, under guard) |
|---|---|---|---|---|---|
| break-attack | +$4.84 (187) | +$17.78 (18) | **+$12.94** | +$29.49 | **0.075** |
| grinder | +$6.16 (142) | +$18.50 (27) | **+$12.34** | +$23.74 | **0.007** |

- **Grinder: LIFT-SURVIVES-GUARD.** +$12.34/fire at realistic fills, null p=0.007.
  The sequence edge is not a thin-bar illusion in this lane — attenuated (~half
  the no-guard lift) but real under the guard.
- **Break-attack: LIFT-NOT-CONFIRMED.** The point lift is +$12.94 but the
  permutation null under the guard gives p=0.075 — at N=18 with half the cohort
  guard-skipped to $0, random relabels reach this lift 7.5% of the time. The
  no-guard p=0.021 was carried substantially by thin-bar fires the guard says
  can't fill. Not refuted — under-N and directionally right — but the BA lift is
  NOT proven at realistic fills. Half-verdict: **LIFT-EQUALIZED-toward-null** for
  BA, pending more hold-out dates.
- Note the guard also collapses the ABSOLUTE books: ungated $/fire falls
  +$24.94→+$4.84 (BA) and +$21.90→+$6.16 (grinder). The wall's headline dollars
  were majority thin-tape at ANY size — consistent with the 8/14 refutation.

## 2) CONDITIONAL SIZING — clip=$750 when fire-bar dv ≥ $15k, else $500

Gated cohorts, guard applied at each fire's own clip. Flat-$500 baselines:
BA +$320.11 total / +$17.78/fire / worst fire −$46.83 (8/1/9 full/half/skip);
grinder +$499.46 / +$18.50 / worst −$47.12 (10/6/11).

Base policy ($15k/$750): BA +$458.37 total (+$138.26 over flat, 8 upsized) but
worst fire −$71.92; grinder +$562.86 (+$63.40, 6 upsized) but worst −$54.47.
**Both buy the extra total by worsening the worst case.**

## 3) SWEEP — dv floor × upsize (full matrix in `_run.txt`)

break-attack: ALL EIGHT CELLS IDENTICAL per upsize level — the floors don't bind
because the cohort is bimodal: 8 liquid fires (all ≥$30k dv, upsized everywhere)
and 10 thin fires the guard skips at any clip. Every cell is just "scale the
liquid 8 linearly under assumed slip": $750→+$138.26 over flat, worst −$71.92;
$1,000→+$270.06, worst −$98.12. This is the capacity doc's model-ceiling artifact
verbatim — the engine cannot make a winner lose to size.

grinder (best cells): 15k/$750 → +$63.40 over flat, worst −$54.47 (6 upsized);
15k-30k/$1,000 → +$68.33, worst −$74.91 (4-6 upsized; the 30k floor drops it to
+$24.39). 10k floors add HALF-clip thin fires and do worse than 15k.

**Flag check: ZERO cells beat flat-$500 total with same-or-better worst-case.**
Every positive-delta cell degrades the worst fire (that is arithmetic: upsizing a
fire that loses loses more, and the model can't offset it with size-degraded
winners). No BEATS-FLAT cell exists to cherry-pick; upsized-N runs 4-10, so even
the deltas rest on a handful of fires under extrapolated slip.

## VERDICT (conservative)

1. **#1 answer: grinder `T B` = LIFT-SURVIVES-GUARD** (+$12.34/fire under guard,
   p=0.007). **break-attack = LIFT-EQUALIZED** for proof purposes (+$12.94 point
   lift, p=0.075, n.s. at N=18 — the no-guard significance was thin-tape-carried).
2. **Conditional upsize: NO-LIFT** under the pre-registered criterion (beat flat
   total with same-or-better worst-case). Best raw cell = grinder $15k/$1,000
   at +$68.33 total (N=6 upsized) — but worst fire −$74.91 vs −$47.12, and all
   $750/$1,000 fills are [CALIBRATION UNKNOWN]. BA cells' larger deltas are the
   liquid-8 model ceiling, not evidence.
3. Standing position unchanged: `T B` is a real LABEL (now guard-proven in the
   grinder lane), blanket AND conditional size-ups both unsupported. The only
   path to a supported upsize is live $750 fill calibration first (the unpaid
   flag from D), then re-run this exact grid with measured slip.

## Officers touched
Wind Tunnel Engineer (guard/model reuse, permutation-under-guard design),
Execution Surgeon ([CALIBRATION UNKNOWN] enforced on every upsize cell),
Convexity Trader (worst-case criterion; no cell qualifies), Statistician (5000
relabels seeded, artifacts committed), Systems Quant (cohort N reconciled to the
wall's JSON, same E3 path, resim cache verified vs capacity doc's $500 rows:
+$320.11/+$499.46 match exactly), Momentum Operator (no upsize on noise),
Strength Ombudsman (BA lift reported as under-N, not killed), Feed Engineer
(single-10s-bar dv proxy caveat carries over), Side Marshal / Crown Steward /
Handicapper / Historian / Seam Scientist / Kev Librarian: clean (no gate stack,
side logic, or corpus in scope).
