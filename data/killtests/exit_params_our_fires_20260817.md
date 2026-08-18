# STOP / TRAIL SWEEP ON OUR OWN REAL FIRES — 2026-08-17

**VERDICT QUALIFIER (LIMITS, added 2026-08-17):** IN-SAMPLE on a SINGLE DAY's own fires, and the sweep's best cell is UNDERPOWERED — n=46 filled of 592 fires, with named cells as thin as n=3. The 67.1% stopped-then-recovered phenomenon is a robust description of today's tape; the winning stop/trail/bank triple is a one-day in-sample optimum and must not be shipped off this doc.

**Analysis only. No code changed, nothing deployed, no env touched.**

Marcos's objection to `runner_model_test_20260817.md` was correct: that study entered on a
CLOCK (fixed times on today's movers) and concluded a plain 10%-stop-and-hold beat E3 by
$732. Those are not our entries. This study replaces the clock with the machine's ACTUAL
fire points and varies **only the exit**.

Script: `data/killtests/exit_params_our_fires_20260817.py` · raw:
`exit_params_our_fires_20260817_out.json` · fire source archived to
`exit_params_our_fires_20260817_arch.json`.

---

## 0. CONSTRAINT CORRECTION (read this before any number)

The original brief specified a **2-slot** governor. That is **WRONG** — it came from the
weekend stress-test's test parameters, not from the machine. `marcos_trading_bot.py` has
**no concurrency cap**. The only limiter is **capital**: `:13193
if settled_remaining < _reserved: no_capital_skip`, against `SIM_ACCOUNT_BALANCE = 3000.0`
(`:7971`, DRY_RUN). Concurrency is therefore *emergent*.

Every cell below reports **three** totals:

- **(a) CAPITAL-CONSTRAINED @ $3,000 — THE DECISION-RELEVANT NUMBER.** Chronological
  ledger; a fire fills only if unreserved capital covers its position; the reservation
  releases at exit; balance compounds with realized P&L. Sizing replicates the bot chain:
  `pos_size = min(bal*0.70, $1,000)` → risk-based shares `int(_scaled_risk/(entry−stop))`
  with `RISK_PER_TRADE=30`, `RISK_PROP_REF=0.06` → notional cap → **5%-of-recent-1-min-volume
  cap** (`MAX_POS_VOL_PCT`, the cap that made NIVF $101 today). One position per ticker.
- **(b) UNCONSTRAINED** — every fire taken, flat $500 clip.
- **(c) 2-SLOT** — labelled `slot2_total_WRONG_CONSTRAINT` in the JSON. Retained only for
  comparability with the earlier counterfactual. **Do not re-cite it as the machine's book.**

*Sizing omission, stated:* the 8/8 VWAP-side half-sizing (`VWAP_SIDE_SIZING=0.5`, field
entries above session VWAP) is **not** modelled — it needs live VWAP + crown state per fire.
Fail-open = full size, so (a) is if anything slightly generous on field entries.

---

## 1. THE FIRE SET

Source: `/api/decisions_archive?date=2026-08-17` (15,253 rows). Every `triggered_*` row across
all lanes **plus** `hidden_shadow_fire`. **627 raw fires → 592 usable.**

| lane | fires used | stop source |
|---|---:|---|
| hidden_shadow | 217 | logged `stop` |
| ma_pullback | 193 | **derived**: confirmation-bar low × (1−1%) — bot uses `min(ma, candle low)×(1−MA_PULLBACK_STOP_BUFFER)`; the wick low is ~always the min |
| flat_top | 74 | **derived**: `max(w_low×(1−0.003), price×0.93)` over the 4-bar 3-min window; `break_attack` rows = `w_low` exact (bot `:9240`) |
| ignition | 31 | **derived**: `base_lo×(1−0.003)` over the 5 prior 3-min bars (bot `:7008`) |
| kevseq | 21 | logged `stop` |
| v2conv | 19 | logged `stop` |
| vwap_reclaim | 13 | **derived**: `min(bar close, logged vwap)×0.99` (bot `:6825`) |
| grinder | 10 | logged `stop` |
| orb | 7 | **derived**: `max(OR-low×(1−0.003), price×0.93)`, OR = 09:30–09:35 from tape (bot `:9359`) |
| prevwap | 3 | logged `stop` |
| dip_rip | 3 | logged `stop` |
| bounce | 1 | **derived**: bar low × 0.99 (bot `:4964`) |
| **TOTAL** | **592** | |

**Excluded: 35 fires**, all for `bad_stop` (derived/logged stop ≥ entry price, i.e. the stop
was already breached at the fire — no tradeable ticket): hidden_shadow 9, ma_pullback 17,
grinder 5, kevseq 2, v2conv 1, dip_rip 1. No lane was excluded wholesale. Realized structural
stop widths: p25 3.83% / median 5.71% / p75 7.34%.

Tape: today's SIP 10s bars rebuilt from `/v2/stocks/trades` (feed=sip), 08:00–20:00Z, 56
tickers — same builder as `runner_model_test_20260817.py`, window widened to cover premarket
fires. Engine: entry slip +1%, −0.5% market-exit slip, **intrabar stop FIRST** (ties against
the trade), 15:45 flatten.

---

## 2. A — STOP WIDTH (trail 10%, bank ½@+10%). N=592 fires every cell.

| stop | CAP $ (a) | CAP N | worst | CAP maxDD | peak conc / deployed | cap-skips | unconstr (b) | 2-slot (c, wrong) | stopped | stopped→recovered | med time-to-stop |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| **×1.0 (today)** | **−1,092.16** | 139 | −32.24 | −1,092.16 | 10 / $2,447 | 137 | −5,841.12 | −164.25 | 404 | **271 (67%)** | 384 s |
| ×1.25 | −772.47 | 121 | −31.92 | −865.28 | 12 / $2,453 | 141 | −5,636.70 | −106.82 | 357 | 232 (65%) | 506 s |
| ×1.5 | −544.03 | 96 | −32.11 | −612.14 | 16 / $2,536 | 147 | −5,937.60 | −131.45 | 323 | 203 (63%) | 644 s |
| ×2.0 | −625.05 | 93 | −32.21 | −636.75 | 20 / $2,708 | 129 | −6,964.63 | −184.71 | 272 | 168 (62%) | 970 s |
| ×2.5 | −316.85 | 84 | −31.64 | −326.50 | 26 / $2,873 | 65 | −5,793.38 | +2.72 | 210 | 116 (55%) | 1,368 s |
| **×3.0** | **−226.77** | 85 | −31.32 | −278.52 | **31 / $2,940** | 67 | −5,804.01 | +74.13 | 162 | 84 (52%) | 1,968 s |
| floor max(struct,10%) | −724.35 | 85 | −31.35 | −730.31 | 18 / $2,598 | 189 | −5,383.72 | −70.17 | 236 | 151 (64%) | 868 s |

**Honesty item (iii) — do wider stops just convert small losses into big ones?** On the
capital book, **no**, and the reason is structural: risk-based sizing shrinks the position as
the stop widens, so `worst single trade` is pinned at ≈−$32 across every stop width (−32.24 at
×1.0, −31.32 at ×3.0). The cost shows up instead as **capital occupancy** — peak concurrent
positions goes 10 → 31 and peak deployed goes $2,447 → $2,940 of a $3,000 account. That is the
interaction the coordinator flagged, and it is real: **the wide-stop cell only wins because it
is allowed to hold 31 names at once against $3k.** It is running the account at 98% deployed.
On the *unconstrained* $500-clip book — where sizing can't shrink — the wide stop is **worse**
(−$5,841 at ×1.0 vs −$6,965 at ×2.0). Wider stops are not free; they are being paid for by
position-size shrinkage.

---

## 3. B — TRAIL WIDTH (stop ×1.0, bank ½@+10%). N=592.

| trail | CAP $ (a) | CAP N | worst | CAP maxDD | peak conc / deployed | unconstr (b) | 2-slot (c, wrong) | stopped |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| **10% (today)** | **−1,092.16** | 139 | −32.24 | −1,092.16 | 10 / $2,447 | −5,841.12 | −164.25 | 404 |
| 15% | −877.47 | 117 | −32.24 | −983.48 | 12 / $2,401 | −6,659.43 | −321.75 | 428 |
| 20% | −688.51 | 106 | −32.11 | −836.61 | 11 / $2,512 | −6,445.53 | −724.09 | 447 |
| 25% | −739.88 | 105 | −32.11 | −866.92 | 13 / $2,575 | −7,150.84 | −688.71 | 472 |
| **none (hold to flatten)** | **−373.55** | 76 | −32.11 | −822.64 | 13 / $2,495 | **−8,668.24** | −611.93 | 501 |

Note the sign flip between books: removing the trail is the *best* capital cell and the
*worst* unconstrained cell (−$8,668). Loosening the trail makes the structural stop do all the
work — stops rise 404 → 501 — and the capital book only looks better because the losers are
size-shrunk and the ledger fills fewer of them.

## 4. C — BANK POINT (stop ×1.0, trail 10%). N=592.

| bank | CAP $ (a) | CAP N | worst | CAP maxDD | unconstr (b) | 2-slot (c, wrong) |
|---|---:|---:|---:|---:|---:|---:|
| **½ @ +10% (today)** | **−1,092.16** | 139 | −32.24 | −1,092.16 | −5,841.12 | −164.25 |
| ½ @ +20% | −1,076.04 | 131 | −32.27 | −1,087.29 | −6,463.45 | −642.92 |
| ½ @ +30% | −863.97 | 112 | −32.21 | −949.38 | −8,814.90 | −775.05 |
| no bank (full ride) | −817.94 | 142 | −32.05 | −896.66 | −7,129.44 | −494.68 |

Bank point is the weakest of the three levers — the whole column spans $274 on the capital
book, versus $865 for stop width.

---

## 5. D — 2×2×2 CORNERS (best individual = stop ×3.0, trail none, bank none)

| cell | CAP $ (a) | CAP N | worst | CAP maxDD | peak conc / $ | unconstr (b) | 2-slot (c, wrong) |
|---|---:|---:|---:|---:|---|---:|---:|
| stop today / trail today / bank today | −1,092.16 | 139 | −32.24 | −1,092.16 | 10 / $2,447 | −5,841.12 | −164.25 |
| stop today / trail today / bank best | −817.94 | 142 | −32.05 | −896.66 | 11 / $2,388 | −7,129.44 | −494.68 |
| stop today / trail best / bank today | −373.55 | 76 | −32.11 | −822.64 | 13 / $2,495 | −8,668.24 | −611.93 |
| stop today / trail best / bank best | −261.89 | 75 | −32.11 | −1,038.57 | 13 / $2,443 | −13,021.47 | −775.05 |
| stop best / trail today / bank today | −226.77 | 85 | −31.32 | −278.52 | 31 / $2,940 | −5,804.01 | +74.13 |
| stop best / trail today / bank best | −513.87 | 132 | −32.15 | −578.17 | 20 / $2,683 | −6,764.69 | −444.58 |
| **stop best / trail best / bank today** | **−187.56** | **46** | **−31.32** | −341.22 | **33 / $2,877** | −10,919.35 | −13.02 |
| stop best / trail best / bank best | −201.51 | 44 | −31.32 | −420.01 | 33 / $2,822 | −17,195.14 | −57.38 |

**Interactions are real and non-additive.** Wide stop alone = −$227; no-trail alone = −$374;
both = −$188 — nowhere near the sum of the improvements. And the widen-everything corner (last
row) is *worse* than the best cell. Wider stop + wider trail is not additive, exactly as the
brief anticipated.

**Best cell: stop ×3.0 / no trail / bank ½@+10%. N=46 filled (of 592 fires). −$187.56
capital-constrained. Worst trade −$31.32. Peak 33 concurrent, $2,877 of $3,000 deployed.**

---

## 6. STOPPED-THEN-RECOVERED ON OUR FIRES

The clock study's headline was 7/7 stopped-then-recovered. On OUR fires at today's settings:
**271 of 404 stops recovered (67.1%), median time-to-stop 384 s.** So the *phenomenon* does
transfer — two thirds of our stop-outs see price trade back through the entry before 15:45,
and they do it fast (median 6½ minutes). Widening the stop reduces both the count and the rate
(×3.0: 84/162 = 52%), i.e. the wide stop absorbs the shakeouts it was supposed to absorb.

**But the recovery does not turn into money**, which is the finding that matters — see §8.

---

## 7. PER-LANE ATTRIBUTION (unconstrained $500 clip, so lanes are comparable)

Today's settings:

| lane | n | total $ | stopped | trailed | flattened | median MFE capture* |
|---|---:|---:|---:|---:|---:|---:|
| hidden_shadow | 217 | −2,630.90 | 150 | 59 | 8 | −0.610 |
| ma_pullback | 193 | −1,994.37 | 136 | 39 | 18 | −0.434 |
| v2conv | 19 ⚠️ | −467.35 | 18 | 1 | 0 | −0.495 |
| ignition | 31 | −249.21 | 18 | 8 | 5 | −0.183 |
| vwap_reclaim | 13 ⚠️ | −235.30 | 11 | 2 | 0 | −0.634 |
| flat_top | 74 | −202.71 | 46 | 21 | 7 | −0.172 |
| grinder | 10 ⚠️ | −165.71 | 9 | 1 | 0 | −0.301 |
| orb | 7 ⚠️ | −119.97 | 2 | 1 | 4 | +0.410 |
| bounce | 1 ⚠️ | −24.88 | 1 | 0 | 0 | −1.434 |
| prevwap | 3 ⚠️ | +34.91 | 1 | 2 | 0 | +0.420 |
| dip_rip | 3 ⚠️ | +91.01 | 1 | 2 | 0 | +0.563 |
| kevseq | 21 | +123.35 | 11 | 9 | 1 | +0.003 |

\* median capture over fires that actually reached ≥+2% MFE (the raw mean is unusable — when
MFE ≈ entry the denominator explodes; the JSON's `mfe_capture` field is that unstable mean and
should be ignored in favour of this column).

**Which lever is killing which lane:** `v2conv` (18/19 stopped), `vwap_reclaim` (11/13),
`grinder` (9/10) are **stop-killed** — they essentially never reach the trail. `hidden_shadow`
and `ma_pullback` are killed by both, but they are also 69% of the fire set and 79% of the
loss; they dominate every cell. At the best cell the stop-killed lanes improve
(vwap_reclaim −$235 → −$10, grinder −$166 → −$115, prevwap +$35 → +$357 ⚠️n=3), while
`kevseq` **inverts** (+$123 → −$782) and `hidden_shadow` gets much worse (−$2,631 → −$7,040):
the no-trail arm gives back everything hidden's runners made. **There is no single exit
setting that is right for all lanes today** — the best cell is a compromise that helps the
stop-killed minority and hurts the two lanes that carry the volume.

Median MFE capture is **negative in 9 of 12 lanes at today's settings** — the median fire
exits below its entry despite having been ≥2% green at some point. That is an exit problem,
but it is a *small* one next to the fact that the fire set as a whole loses money.

---

## 8. ENTRY-SLIP SENSITIVITY (best cell)

| entry slip | CAP $ (a) | CAP N | unconstrained (b) |
|---|---:|---:|---:|
| +1% (today's model) | −187.56 | 46 | −10,919.35 |
| 0% | −45.11 | 40 | −7,697.34 |

Removing the fill assumption entirely recovers ~$142 on the capital book and ~$3,222
unconstrained — i.e. **a material slice of the "exit" gap is actually a fill assumption, not an
exit setting.** The best cell is still negative at zero slip.

---

## 9. HONESTY BLOCK

**(i) N.** N = 592 fires in every A/B/C/D cell (the exit varies, the fire set does not). The
*filled* counts differ by cell and are stated everywhere (`CAP N` 44–142). **Cells with
CAP N < 20: none.** **Lanes with n < 20 are flagged ⚠️ UNDERPOWERED** in §7: v2conv (19),
vwap_reclaim (13), grinder (10), orb (7), prevwap (3), dip_rip (3), bounce (1). Any per-lane
claim about those seven is a hypothesis, not a result.

**(ii) IN-SAMPLE, ONE SESSION.** Every number here is 2026-08-17 only, and the winning cell was
selected on the same day it was measured. **This licenses no ship.** The only legitimate next
step is to run the best cell against the OOS universe (prior era days, 7/13+) before anyone
proposes an env change. Note also that the fire set is 592 fires while the machine actually
filled **4** trades today — this book is two orders of magnitude more active than the real
machine, because shadow/observe fires and repeat fires on the same name are all included. It
measures *the exit rule*, not today's realized P&L.

**(iii) Loss conversion.** Addressed in §2: on the capital book, wider stops do NOT enlarge the
worst trade (risk-based sizing shrinks the position), but they DO consume capital far longer —
peak concurrency 10 → 33 and peak deployment $2,447 → $2,940 against $3,000. On the fixed-clip
unconstrained book, where sizing can't compensate, wide stops are clearly worse. Neither fact
is hidden in the average.

**(iv) The result Marcos most needs.** Stated plainly below.

---

## 10. VERDICT

> **THE CLOCK-ENTRY FINDING DOES NOT TRANSFER.**
> **Today's exit settings are the WORST cell in the sweep (−$1,092.16 capital-constrained,
> N=139) — but EVERY cell in the sweep is negative, and the best is only −$187.56 (N=46,
> worst trade −$31.32, peak 33 concurrent / $2,877 deployed).**

So: our exits cost us **$904.60** today versus the best cell (−$1,092.16 → −$187.56,
capital-constrained @ $3,000) — but that $904.60 is **loss reduction, not forgone profit**.
The runner_model_test's headline (plain 10%-stop-and-hold = **+$878**) **does not reproduce on
our own fires**: the closest analogue here, no-trail-hold-to-flatten, is **−$373.55**
capital-constrained and **−$8,668** unconstrained. The clock study's profit came from *where it
entered*, not from *how it exited*.

**The problem today is the fire set, not the exit rule.** No stop width, trail width, bank
point, or corner combination in this sweep turns 2026-08-17's fires positive — the best cell in
a 3-lever, 8-corner sweep still loses money on 46 filled trades. Tuning exits on this day would
be tuning the wrong parameter. 67% stopped-then-recovered is real and looks like an exit
signal, but §5 shows that recovery cannot be monetised by any exit setting tested: the wide-stop
arms capture the shakeouts and still finish red.

Not underpowered on the aggregate (N=592 fires, 46–142 fills per cell), but **in-sample on one
session**. Candidate for OOS testing only: **stop ×3.0 / no trail**, and it must be tested with
the capital ledger in the loop, because it only wins by running 33 concurrent positions against
a $3,000 account — a capacity claim that has never been validated live.
