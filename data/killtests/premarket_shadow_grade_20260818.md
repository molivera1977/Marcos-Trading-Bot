# PREMARKET SHADOW BOOK — GRADED (8/18)

**Marcos: *"what's the point if we dont collect any data."*** We do collect it. 544
`premarket_shadow_entry` rows over 10 sessions (8/04–8/17), every one carrying ticker, entry
price, stop and timestamp. **Nobody had ever graded them.** This closes that.

- Script: `premarket_shadow_grade_20260818.py` · raw: `..._run.txt` · rows: `..._out.json`

## What a shadow row is

A lane fired in premarket, passed its own detector, and was refused conversion **purely because
it is not in `PRE_LANES`**. The row records the trade the bot *would* have taken — a clean
counterfactual with no gate opinion and no lookahead.

## Result

| | |
|---|---|
| gradable trades | **230** (of 544; 293 skipped — name not in the curated bar cache, 20 fired after 09:25) |
| **TOTAL** | **−$1,236.40** |
| per trade | −$5.38 |
| win rate | 95/230 (**41%**) |
| green days | **3 of 10** |

**By lane — every one negative:**

| lane | n | total | $/trade |
|---|---|---|---|
| ma_pullback | 144 | −$537.31 | −$3.73 |
| flat_top | 62 | −$438.87 | −$7.08 |
| hidden_entry | 22 | −$199.99 | −$9.09 |
| vwap_reclaim | 2 | −$60.23 | −$30.12 |

**By day:** 8/04 −63 · 8/05 **+138** · 8/06 −53 · 8/07 −245 · 8/10 **−682** · 8/11 +56 ·
8/12 −71 · 8/13 −344 · 8/14 +62 · 8/17 −36

**Exits:** stop 100 · trail 85 · flatten_0925 45.

## Pre-registered checks (written before the run)

- **N ≥ 100 — PASS** (230)
- **total dollars positive — FAIL** (−$1,236.40). The pre-registered consequence: *premarket
  stays shut on this evidence.*
- **not concentrated — PASS** (largest single name-day is INLF 8/05 at 33% of |total|)

## Verdict — CONTAMINATED COHORT, DIRECTIONAL ONLY

**Epochs: this spans 8/04-8/17, MULTIPLE config epochs (v2/grinder/kevseq conversion flags and the
8/17 batch all moved inside the window) and 42% coverage. Treat as directional, not a clean
measurement.**

**Opening premarket to the currently-shadowed lanes would have LOST money** — about −$1,236
across ten sessions, on a 41% win rate, red on 7 of 10 days. **The `PRE_LANES` whitelist is not
a bug. It is doing its job**, and the instinct to "reopen premarket because it's being wasted"
is refuted for these lanes.

## LIMITS — read before believing

- **LOW-PARITY LANES IN THIS COHORT (EG2b disclosure).** The graded set includes lanes whose
  harness parity is below the 90% trust floor: **v2 = 51.2%**, **grinder = 9.1%** (measured
  2026-08-17, `data/killtests/harness_parity.json`). Their rows are a small share of the total
  (v2conv 5 of 544; grinder does not appear), but the disclosure is required and the number is
  stated rather than buried: no claim in this document about those two lanes is trustworthy.
- **EPOCH DECLARATION — MIXED-EPOCH.** 2026-08-04..2026-08-17 spans multiple config hashes — v2/kevseq/grinder
  conversion flags and the entire 8/17 foundation batch moved inside the window. Per-epoch splits
  were not computed. Directional only.

- **42% coverage.** 293 of 544 rows could not be graded because the name is absent from the
  curated 10s cache. That cache is a top-mover roster, so the excluded names are **not a random
  subset** — this is a biased sample, not a census. The direction is consistent across every
  lane and 7 of 10 days, which is what makes it worth acting on, but it is not a full book.
- **KNOWN OPTIMISM: no halt-gap rule.** This cache carries no gaps table, so a premarket halt
  that gapped through a stop is modelled as a clean stop fill. Reality would be **worse**, not
  better.
- **Says NOTHING about the whitelisted lanes.** `hidden_entry` (22 rows) and `vwap_reclaim` (2)
  appear only incidentally. The question "should hidden/vwap_reclaim be switched back on for
  premarket" is untouched here — those lanes' own PRE record (35 non-defect trades, −$58.74,
  57% win) is a different population and remains unresolved.
- **E3 exits are a PORT, not an import**, from `edge_stresstest_F::sim_var`. Rules reproduced in
  the script docstring so the port is checkable. Flatten moved 19:59Z → 09:25 ET (session rule).
- **Method error found and fixed mid-run:** the first execution reported `no_bars_in_cache` for
  543 of 544 rows and "NOTHING GRADABLE." That was a **path bug** — `ROOT` used two `dirname`s
  instead of three, pointing at `data/data/universe/`. A path bug wearing the costume of a data
  gap. The script now asserts the cache directory exists and refuses to report an empty result
  from a bad path. Recorded because this is exactly how a false "we have no data" conclusion
  gets made.

*No recommendation. Numbers only — Marcos decides.*

**EPOCH DECLARATION:** 2026-08-04..2026-08-17 spans more than one config epoch; per-epoch
splits were NOT computed, so no single-config claim is made here.
