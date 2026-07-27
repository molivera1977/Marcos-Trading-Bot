# KILL-TEST — the true intrabar stop, on real 10s tape (7/27 evening)

**Verdict: REFUTED as specified.** The intrabar stop's positive result is carried entirely by LGHL,
the trade it was written for. Remove that one trade and it loses money **at every fill quality,
including a perfect fill exactly at the stop.** Do not ship item 1 tonight as `INTRABAR_STOP=1`.

Ordered by what actually decides it, not by what was expected.

## Cohort

n=20. Every RTH trade on 7/23, 7/24 and 7/27 that has BOTH 10s tape and a real fill time.
Recorded total −$234.76. 10s bars from the dashboard archive (`~ALP10S` preferred — Alpaca capture,
per "10s outranks 1-min"; `~10S` fallback). Fill times from the decision log's `filled` rows, the
only source of entry times that exists — the trade store still has none.

Everything excluded is named: the 5 PRE rows (quarantined, see the data-integrity finding below).
Days before 7/23 are unreachable — the decision log is capped and holds no `filled` rows for them,
so 10s archives back to 7/15 cannot be anchored to an entry.

**Method — differential, not re-simulation.** The recorded trade is ground truth. An intrabar stop
changes an outcome only if the 10s tape touched the stop before the recorded exit, so that is the
only thing recomputed: partials banked before the touch are kept, the remainder exits at the touch.
This avoids re-implementing the health-trail / topping-tail / velocity-ride engine and the fidelity
error that would carry. Entry is anchored to the **tape**, not the decision row's clock — LGHL's
`filled` row is stamped 04:14:11 while its fill price 1.4903 is the 04:13:00 bar, a ~70s lag that
silently moved the answer when I first used the stamp.

## The result

| | Δ vs recorded |
|---|---|
| Optimistic fill (exactly at the stop) | **+$63.29** |
| Pessimistic fill (at the touching 10s bar's low) | **−$97.95** |

Helped 8 · hurt 7 · unchanged 5. Median trade delta: **+$0.00** optimistic, **−$1.23** pessimistic.

The sign depends on the fill assumption, so neither number alone is an answer. What settles it is
concentration:

| | Δ optimistic | Δ pessimistic |
|---|---|---|
| All 20 trades | +$63.29 | −$97.95 |
| **Ex-LGHL (19 trades)** | **−$25.06** | **−$180.60** |

**LGHL alone is +$88.35.** It is the trade that motivated the change. Without it the mechanism is
negative under both conventions.

### Fill-quality sensitivity — the decisive table

`frac` = how deep into the touching 10s bar you get filled. 0.00 is a perfect fill at the stop;
1.00 is that bar's low.

| frac | all 20, confirm 0s | ex-LGHL, confirm 0s | ex-LGHL, confirm 10s |
|---|---|---|---|
| 0.00 (perfect) | +$63.29 | **−$25.06** | +$24.31 |
| 0.10 | +$47.16 | −$40.62 | +$5.28 |
| 0.20 | +$31.04 | −$56.17 | −$13.75 |
| 0.40 | −$1.21 | −$87.28 | −$51.81 |
| 1.00 (worst) | −$97.95 | −$180.60 | −$166.01 |

Two readings, both load-bearing:

1. **Ex-LGHL, the plain intrabar stop is negative even at a perfect fill.** Fill quality is not the
   problem; the rule is. It converts recoverable dips into realized losses more often than it saves.
2. Whole-cohort break-even sits near **frac ≈ 0.39** — you must capture the top ~60% of the touching
   bar to break even. **There is no resting broker stop** (`place_stop_order` returns None, Webull
   rejects the type), so exits are market orders issued after detection — the wrong end of that
   range on exactly the fast tape where this matters.

### Variant sweep — nothing survives

Every alternative shape, same cohort. Not one is positive under the pessimistic fill:

| rule | Δ opt | Δ cons | ex-LGHL opt |
|---|---|---|---|
| intrabar, confirm 0s (tonight's build) | +$63.29 | −$97.95 | −$25.06 |
| intrabar, confirm 10s | +$112.66 | −$134.66 | +$24.31 |
| intrabar, confirm 20s / 30s | +$112.66 | −$154 / −$160 | +$24.31 |
| intrabar, buffer 0.5% / 1% / 2% below stop | +$27.23 / −$7.55 / −$12.32 | −$121 / −$149 / −$196 | −$58 / −$91 / −$90 |
| crater floor only, 1.5R / 2.0R / 2.5R | −$24.45 / −$52.02 / +$4.89 | −$191 / −$168 / −$87 | −$97 / −$109 / −$36 |

The confirm dial is the only shape that is positive ex-LGHL, and only when fills land in the top
~15% of the touching bar — i.e. it needs the resting broker stop to be real.

## What this changes about the ledger's cost estimate

The 7/27 verdict priced the wick-shakeout cost at **≈$57, n=2, from 1-min bars**. On 10s tape the
cost side is **7 trades / −$105.03 optimistic on three days alone**. The 1-min estimate understated
it by roughly an order of magnitude, exactly as the "10s outranks 1-min" law predicts — 1-min bars
cannot see a dip that touches and recovers inside the minute, which is the entire shakeout class.

The savings side is real and also larger than estimated (8 trades, +$168.30) — the mechanism does
convert blow-throughs into ~1R losses. The two sides are simply much closer than anyone thought,
and which one wins depends on a fill we cannot currently guarantee.

## Separate finding — a data-integrity defect, verified

**All 5 premarket blind-stop exits are OFF-TAPE: priced below the day's low on BOTH independent 10s
feeds.** They total exactly −$624.50.

| ticker | recorded exit | day low (10s) | recorded P&L |
|---|---|---|---|
| BIYA | 1.93 | 2.42 | −$262.89 |
| LGHL | 0.91 | 0.95 | −$166.40 |
| VEEE | 12.97 | 13.70 | −$99.47 |
| MTNB | 0.24 | 0.311 | −$14.26 |
| JZXN | 1.19 | 1.22 | −$81.48 |

All 17 RTH exits are on-tape. So the premarket incident is not only "the bot was bar-blind" — the
**stream price it exited on printed values that never traded**. In DRY_RUN that means −$624.50 of the
book is fiction. It also means `current_price` from the stream is not a trustworthy execution price
premarket, and the blind-stop failsafe writes it straight into the record with no sanity check.

This bears directly on item 1: **the intrabar stop exits on that same stream price.** In RTH the
stream looks sound (17/17 on-tape), and premarket entries are disabled, so the shipped configuration
is not exposed to the observed phantom class today. But the mechanism inherits the exposure the
moment `ENTRY_OPEN_ET` goes back to 04:00.

## Recommendation

1. **Do not ship item 1 tonight.** `INTRABAR_STOP=0`. The kill-test does not support it, and its one
   supporting trade is the one it was designed around.
2. **Un-stub the resting broker stop first** — the handoff already scheduled it for "its own night".
   This test says that is not a sequencing preference, it is the precondition: the intrabar stop's
   entire benefit lives in the top ~40% of the touching bar, which only a resting stop can capture.
   Re-run this kill-test after it lands.
3. Items 2, 4, 5 and 6 are unaffected by this and stay as built.
4. **F1 (BE floor at scale #1) is NOT settled by this test**: C−B is +$2.15 optimistic / −$3.63
   pessimistic across the three days — neutral at this n. On 7/27 alone it was −$12.22 / −$19.59.
   Holding `BE_FLOOR_AFTER_SCALE=2` remains the cheap conservative choice but the data does not
   compel it either way.
5. Sanity-check the blind-stop's exit price against recent tape before recording it — a print below
   the day's low should not be bookable. Not built; recorded as the follow-on defect.

## Honest limits

Three days, n=20, one of which supplies the entire positive result. Both fill conventions are
constructions, not observed fills — the truth lies between them and is unmeasurable without the
broker stop. Partials are placed at the first 10s bar reaching their recorded price (times are not
stored). The pessimistic arm assumes the worst print inside every touching bar, which is harsher
than reality; the optimistic arm assumes a fill no current code path can deliver.

Reproduce: `scratchpad/killtest_v2.py` (arms) and `killtest_sweep.py` (variants + sensitivity).
