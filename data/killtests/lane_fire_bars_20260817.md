# FOUNDATION BATCH G — A FIRE BAR FOR THE LAST THREE LANES, AND A PRICE FOR HIDDEN

Batch G, 2026-08-17. Companions: `lane_fire_age_20260817.md` (batch B, which wired the guard
into v2conv/grinder/bandpass/prevwap and named these three lanes as unreachable),
`breakattack_extraction_20260817.md` (batch D, which gave flat_top its detector),
`harness_lift_remaining_20260817.md` (batch E, which measured hidden's 5.8% price parity).

Rig: `rig/test_batchG_20260817.py`. Gate-5 acceptance: `SPEC_lane_fire_bars_stamped`.

---

## FAILURE CONDITION — WRITTEN FIRST

**This batch is WRONG if any of the following is true:**

1. **Any live decision changes.** Every item here is a row field or a DISARMED guard. If any
   8/18+ session produces a `break_attack`, `triggered_flat_top`, `seam_shadow_fire`,
   `halt_arm`, `hidden_shadow_fire` or `triggered_ma_pullback` row that the pre-batch code
   would not have produced — same lane, same instant, same level, same stop — this batch is a
   behaviour change wearing an observability costume and must be reverted. The guard calls
   added here are inert unless `LANE_FIRE_AGE_GUARD` names the lane, and it is empty by default.
2. **A synthetic bucket is invented.** Every `fire_k` stamped below is a REAL bar epoch taken
   from the series the detector actually read. If any of them is derived from `time.time()`,
   from a row's log time, or from a bar the detector did not consume, the stamp is a fiction
   and is worse than no stamp — it would make tomorrow's age measurement measure the logger.
3. **A stamped age is read as comparable across lanes without its cadence.** These lanes read
   bars of three different widths (flat_top 3-min, crown_seam 5s, halt_ladder 5s-or-10s). Ages
   are stamped from the bar's **CLOSE** (`k + cadence`) precisely so they mean the same thing —
   "seconds since this data could first have been acted on". A study that compares a raw `k`
   across lanes is comparing bar widths.
4. **The flat_top age guard is armed at the default 90s.** See §1.4 — the base bar is 180s
   wide and is re-read every scan cycle, so a bare arm would suppress every fire landing more
   than 90s into a bar, selected by nothing meaningful. Arming `flat_top` requires an explicit
   per-lane threshold (`flat_top:300` or higher) and a measured cost. If anyone arms it bare,
   this doc failed to warn loudly enough.
5. **Any §2 number is quoted as post-fix price parity.** None of them is. §2 reproduces batch
   E's two figures, measures the QUOTE FEED's drift from the fired bar, and reports one weak
   heuristic. The real price parity arrives with 8/18 rows and not before.
6. **`price` stops meaning what it meant.** Today's archive is comparable only if `price` keeps
   carrying the live quote on every row touched here. Nothing below changes `price`.

---

## ITEM G1 — THE THREE LANES WITH NO FIRE BAR: THE FINDING

Batch B's note said flat_top, crown_seam and halt_ladder had *"no detector, no fire dict, no
bucket epoch — their fire price is the live quote."* **That was right about flat_top and WRONG
about the other two.** Read from the source, not from the note:

| lane | does it consume bars? | the bar series | fire bar available? |
|---|---|---|---|
| **flat_top** | yes | `_latest_session(aggregate_bars(full_bars, 3))[:-1]` — completed 3-min session bars | **YES** (since batch D extracted `flat_top_step`; the base is those bars) |
| **crown_seam** | **yes** | `_alp5_feed(t, n=720)` — 5s bars, hot5 primary | **YES** — `_seam5_check` prices off `cl[-1]`, the LAST 5s bar's close |
| **halt_ladder** | **yes** | `_curl_feed(t, n=180)` 10s, or `_alp5_feed(t, n=360)` 5s when `HALT_ARM_5S` | **YES** — `_hl_px = _hl_d10[_hl_ks[-1]]["c"]`, the LAST bar's close |

**Neither crown_seam nor halt_ladder is quote-driven.** Both are pure bar readers whose entry
price IS a bar close (crown_seam converts at `_ss['price']` = `cl[-1]`; halt_ladder converts at
`_hl_px`). The batch-B note conflated "has no `*_step` detector function" with "has no bar".
The first is true, the second is false, and only the second mattered.

**So: nothing in this trio is permanently un-stampable.** All three now carry a fire bar. See the
"WHAT REMAINS PERMANENTLY UN-STAMPABLE" section for what genuinely remains, which is a shorter list than expected and does not
include any of these three lanes.

### 1.1 flat_top

- **Fire bar:** the last COMPLETED 3-min session bar, `_sess3[-1]`, epoch via `_bar_epoch`
  (the batch-C1 helper). Stamped as `fire_k`.
- **Age:** `fire_age_s = now - (fire_k + SETUP_TF_MIN*60)` — from the bar's CLOSE, because
  `_bar_epoch` returns the bar's OPEN and a 3-min bar cannot be acted on until it closes.
- **Drift:** `drift_pct = (price - fire_close) / fire_close * 100`, where `fire_close` is
  `_bar_close(_sess3[-1])`. This is the honest quantity for this lane: flat_top's trigger is
  the LIVE QUOTE crossing `w_high`, so the bar gives it an AGE, not a fire PRICE. There is no
  `fire_px` for flat_top and inventing one would be a fiction — the stamp is
  `fire_bar_close`, named for what it is.
- **Rows stamped:** `break_attack` and `triggered_flat_top`.
- **Guard:** `_lane_fire_stale(t, "flat_top", <close epoch>, price)` on the attack path,
  immediately before the conversion. **DISARMED** (batch B's precedent — never arm an
  unmeasured suppressor).

### 1.2 crown_seam

- **Fire bar:** `_seam5_check` now returns `fire_k` = `_ks5[-1]`, the last 5s bar it read —
  the same bar whose close it already returns as `price`.
- **Age:** `fire_age_s = now - (fire_k + 5)`.
- **Drift:** `drift_pct = (live price - _ss['price']) / _ss['price'] * 100`. Note this lane
  converts AT `_ss['price']`, not at the live quote, so a large drift here is a latency
  measurement, not a slippage measurement. Stated so nobody prices a ticket off it.
- **Rows stamped:** `seam_shadow_fire` (the lane's only fire row) — gains `fire_k`,
  `fire_px`, `fire_age_s`, `drift_pct`.
- **Guard:** `_lane_fire_stale(t, "crown_seam", ...)`, DISARMED.

### 1.3 halt_ladder

- **Fire bar:** `_hl_ks[-1]` — the last bar of whichever feed armed the ladder. The feed can be
  5s or 10s, so the cadence is **measured, not assumed**: `_hl_ks[-1] - _hl_ks[-2]`, and
  `_hl_src` (`"alp5s"` vs the 10s source) is already stamped alongside.
- **Age:** `fire_age_s = now - (fire_k + cadence)`.
- **Drift:** `(price - _hl_px) / _hl_px * 100` — live quote vs the bar the arm priced off.
- **Rows stamped:** `halt_arm` (the convert-deciding row) and `halt_early_arm`.
- **Guard:** `_lane_fire_stale(t, "halt_ladder", ...)`, DISARMED.

### 1.4 ⚠️ THE THRESHOLD WARNING (read before arming anything)

`_lane_fire_stale` measures against `CURL_FIRE_MAX_AGE_SECS`, **90s**, which was calibrated for
10s buckets. Applied to these three lanes bare:

| lane | bar width | age at the instant the bar closes | 90s ceiling verdict |
|---|---|---|---|
| crown_seam | 5s | ~0s + fetch latency | sane |
| halt_ladder | 5s / 10s | ~0s + fetch latency | sane |
| **flat_top** | **180s** | **~0s at close, but the NEXT scan pass sees it aging toward 180s** | **a bare arm kills the lane** |

flat_top's base bar is re-read on every scan cycle until a new 3-min bar completes, so its
stamped age sweeps 0→180s across a bar. A bare `LANE_FIRE_AGE_GUARD=flat_top` would suppress
every fire that lands more than 90s into the bar — roughly half of them, and not a
half selected by anything meaningful. **If flat_top is ever armed it must be armed as
`flat_top:300` or higher, from a measured distribution.** The stamps ship tonight precisely so
that distribution exists tomorrow.

---

## ITEM G2 — HIDDEN'S PRICE STAMP

**The defect (batch E, §"NEW PARITY NUMBERS").** `hidden_shadow_fire` stamps
`price = _hpx = price if price and price > 0 else _he_fire.get("px")` — the LIVE QUOTE at log
time. The detector's own fire price, `_he_fire["px"]` (`round(c, 4)`, the fed 10s bar's close),
was computed and then discarded on the shadow row. Parity therefore scored **86.3% on
stop+time and 5.8% on price**, and the 5.8% was measuring the quote feed.

**Not a whole-lane defect — a one-row defect.** The lane's other two rows already carry it:
`hidden_observe_only` stamps `fire_px=_her.get("px")`, and `triggered_hidden_entry` stamps
`fire_px` + `fire_age_s` + `drift_pct`. Only `hidden_shadow_fire` — the row batch E's parity
run reads — was missing it.

**The fix.** `hidden_shadow_fire` gains `fire_px` (= `_he_fire["px"]`, the detector's output),
`fire_k`, `fire_age_s` and `drift_pct`, matching the convention every other lane uses.
`price` is UNCHANGED and still carries the live quote, so today's archive stays comparable and
the 5.8% figure remains reproducible against it.

### The re-measurement, and exactly what it is worth

**Method (synthetic — say it plainly).** 8/17's rows do not contain `fire_px`; the field ships
tonight. So the post-fix price parity CANNOT be measured on 8/17 and was NOT. What was run, in
`data/killtests/harness_parity_hiddenpx_20260817.py` (→ `..._out.json`), is the batch-E replay
(424 harness fires vs 226 live rows, `_bucket_fresh` clock hook armed) re-derived from scratch,
plus a measurement of the thing the old key was actually scoring.

**Result 1 — batch E reproduces exactly.** stop+time **86.3% (195/226)**; price+stop+time on
the OLD field **5.8% (13/226)**. This artifact therefore stands on its own numbers, not on a
citation.

**Result 2 — the size of the defect, which is the useful finding.** Across the 195 stop+time
matches, the gap between the row's `price` (the quote) and the harness detector's `px` (the
fired bar's close):

| statistic | value |
|---|---|
| median gap | **1.015%** |
| p90 gap | 4.547% |
| max gap | 16.0% |
| **exactly equal** | **13 of 195** |
| within 0.1% | 20 of 195 |

The 13 exactly-equal pairs ARE the 5.8%. So the old price key was not measuring a detector at
all: it was measuring a quote that sits a **median 1% away from the bar the detector fired on**,
and agreed by coincidence 13 times. That is the defect, quantified, and it is what `fire_px`
removes.

**Result 3 — a weak recovery heuristic, reported honestly because it was run.** `stop = min(l -
0.01, c*0.95)`, so where the 5% floor binds the close is `stop/0.95`. This was intended to
isolate a clean invertible subset and **it does not** — `stop/0.95` round-trips for any stop, so
the only real filter left is a ±10% sanity band that admits 192 of the 195 matches. The number
it produces (**90.1%, 173/192, agreeing within half a cent**) is a statement about how often the
5% floor happens to bind, **not** a price-parity measurement. It is recorded rather than deleted
because a result that came out weaker than hoped is still a result.

**What none of this is.** No number above is post-fix price parity. Result 1 is a reproduction,
Result 2 is a measurement of the QUOTE FEED, Result 3 is a heuristic that cannot fail
interestingly. All three carry 8/17's standing caveat: no `fed_k0/fed_k1` provenance, so the two
sides were not provably fed the same bars.

**THE REAL NUMBER ARRIVES WITH 2026-08-18 ROWS.** From tomorrow, `hidden_shadow_fire` carries
`fire_px`, and the parity run can be re-keyed on `price + stop + time` directly with no
recovery, no subset, and no invertibility assumption. Batch E's 5.8% stays in the artifact as
the honest reading of the OLD field, and stays labelled as a measurement of the quote feed.

---

## ITEM G3 — ma_pullback'S MISSING STOP

Batch B flagged that `triggered_ma_pullback` rows log NO stop — which is why the 8/17 exit
study had to invent one, producing 17 phantom "bad stop" fires. Confirmed from source: the row
logged `price`, `ma` and `fire_k` only, while `ma_stop = ma_pb["stop"]` sat three lines above it
and went into `breakouts` as `ema_stop`.

**Fix (observability only).** `triggered_ma_pullback` now stamps `stop=ma_stop` — the exact
value the trade is built with, read from the same variable, so the row and the ticket cannot
disagree. `fire_age_s` is stamped alongside from the existing `fire_k` (the confirmation
candle's epoch, batch C1), using the same close-relative convention as §1.1
(`fire_k + SETUP_TF_MIN*60`).

**No stop is invented and none is recomputed.** Any future exit study that finds a
`triggered_ma_pullback` row without a `stop` is reading a pre-8/17-night row and must say so.

---

## LIMITS & CAVEATS

- **No trading claim is made anywhere in this artifact.** No P&L, no expectancy, no go/no-go,
  no verdict on any lane. Everything here is a row field or a disarmed guard.
- **Nothing here has been measured live.** These stamps produce their first real rows on
  2026-08-18. Every number in §2 is synthetic; every age distribution referenced is future work.
- **§2's 90.1% cannot fail interestingly.** Its admission filter does not isolate anything
  (see Result 3), so it measures how often the 5% risk floor binds, on one day, with 8/17's
  standing no-`fed_k0/fed_k1` caveat. It is not evidence about the detector and is not parity.
- **§2's 1.015% median gap is a QUOTE-FEED property**, measured on 195 matched pairs from one
  day. It explains the 5.8%; it does not predict tomorrow's price parity.
- **The age guard is DISARMED for all three lanes** and its cost is therefore unmeasured — which
  is exactly why it is disarmed. Arming any of them is a separate, priced decision for Marcos.
- **flat_top at the default 90s ceiling would suppress roughly half its fires** (§1.4). This is
  arithmetic from the bar width, not a measurement; the real distribution arrives 8/18.
- **crown_seam / halt_ladder drift is latency, not slippage.** Both lanes convert at the bar
  close they price off, not at the live quote, so `drift_pct` measures how far the quote has
  moved since the bar — useful for diagnosing feed lag, wrong for sizing or for grading fills.
- **halt_ladder's cadence is inferred from the last two bar keys.** A gapped feed (a halt, a
  dropped bucket) makes that inference wide, which biases `fire_age_s` DOWN. `bar_secs` and
  `feed_src` are stamped on the row so any study can see when the inference was unusual.
- **The EG1 matrix flips are property flips, not lane approvals.** (b) and (c) closing means
  the mechanism is present and attributed; it says nothing about whether the lanes are good.
  (a) and (g) remain undecidable for all three and are pinned `None`, not `True`.

## WHAT REMAINS PERMANENTLY UN-STAMPABLE, AND WHY

| thing | status | why |
|---|---|---|
| flat_top `fire_px` | **impossible, by design** | the lane's trigger is the live quote crossing `w_high`; the bar supplies the LEVEL and the AGE, never a fire price. `fire_bar_close` is stamped instead, named for what it is. |
| flat_top's retest arm age | live-only | the arm's clock is `time.time()` against `PULLBACK_TIMEOUT_SECS` and the 1-min tape state machine (batch D, unchanged). The `pb` dict's `ts` is a wall-clock stamp, not a bar. |
| crown_seam / halt_ladder properties (a) and (g) in the EG1 matrix | not decidable | neither lane has a separable `*_step` detector — they are emitted inline by the caller — so the AST property computer cannot decide "fire price is a traded print" or "stop anchored to the fire bar" for them. They stay pinned `None`. This is a limit of the GATE, not a defect in the lanes: both provably price off a bar close (§1.2, §1.3), the computer just cannot prove it from the caller. |
| pre-8/17-night rows for any of these fields | permanently absent | the fields did not exist. No back-fill is possible or attempted. |

## EG1 MATRIX — WHAT FLIPPED

`rig/test_shipset_20260804.py`, `_E1_PIN`:

| lane | property | was | now |
|---|---|---|---|
| flat_top | (b) fire-age guard | `OPEN:...#EG1-b` | **True** |
| flat_top | (c) drift+age stamps | `OPEN:...#EG1-c` | **True** |
| crown_seam | (b) | `OPEN:...#EG1-b` | **True** |
| crown_seam | (c) | `OPEN:...#EG1-c` | **True** |
| halt_ladder | (b) | `OPEN:...#EG1-b` | **True** |
| halt_ladder | (c) | `OPEN:...#EG1-c` | **True** |

Properties (a) and (g) stay `None` for all three (see the table above). To make (b) and (c)
computable for lanes with no separable detector, the property computer was extended in the
direction its own comment already promised (*"detector fn None = ... properties are asserted at
the CALLER instead"*): (b) now also credits a `_lane_fire_stale(t, "<lane>", ...)` call in the
caller when the lane has no detector fn, and (c) is attributed through a fire-var token exactly
as it is for every other lane. **No pin was loosened; three lanes' worth of OPEN pins closed.**

## FILES

| file | change |
|---|---|
| `marcos_trading_bot.py` | G1 flat_top/crown_seam/halt_ladder fire-bar stamps + disarmed guards; G2 `hidden_shadow_fire` gains `fire_px`/`fire_k`/`fire_age_s`/`drift_pct`; G3 `triggered_ma_pullback` gains `stop`/`fire_age_s` |
| `rig/test_batchG_20260817.py` | new — specs incl. the Gate-5 acceptance |
| `rig/test_shipset_20260804.py` | EG1 pins flipped for the three lanes; (b)/(c) computers extended for detector-less lanes; `_E1_LANES` gains their fire-var tokens |
| `data/killtests/harness_parity_hiddenpx_20260817.py` (+ `_out.json`) | the synthetic G2 re-measurement |
| `data/killtests/lane_fire_bars_20260817.md` | this doc |

**Not done, on purpose:** no deploy, no push, no env change, no restart.
