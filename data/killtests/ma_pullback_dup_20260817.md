# ma_pullback WITHIN-PROCESS DUPLICATION — diagnosis, failure condition, fix

FOUNDATION BATCH C, item C1. Written 2026-08-17 (night). Failure condition written BEFORE the fix.

## VERDICT
CONFIRMED as a STATE defect (the lane re-attempted the trade, it did not merely re-log) — but the
count correction is a single-day, upper-bound estimate ONLY, and no dollar claim is made or
implied: ma_pullback had zero fills on 8/17. See LIMITS below before citing any number here.

## LIMITS / CAVEATS
- Single day of archive evidence (2026-08-17 only). The mechanism is read from CODE, not inferred
  from the row spacing alone; the row spacing only CONFIRMS the code read. Earlier days are
  presumed affected by the same code path but are NOT measured here.
- The corrected counts below are DISTINCT-SETUP counts derived by collapsing rows on
  (ticker, price, ma). That is an upper bound on true distinct fires: two genuinely separate
  setups on the same name that happen to fire at the same printed price and the same MA collapse
  into one. It is a much better estimate than the raw row count, not a measured ground truth.
- 8/17 straddles FIVE deploys (see C2, config_epochs). These counts are MIXED-EPOCH.
- No P&L claim is made here. ma_pullback had ZERO fills on 8/17, so there is no dollar figure to
  attribute either way. This is a COUNTS defect, not a money defect — on this day.

## THE DEFECT

`triggered_ma_pullback` logged **210 rows** on 2026-08-17. At most **123** are distinct
(ticker, price, ma) combinations. Two names dominate:

| ticker | rows | window | distinct prices |
|---|---|---|---|
| YDES | 40 | 12:53:02 – 13:27:14 | 1 (`$3.2933`) |
| GRNQ | 36 | 13:17:15 – 15:22:47 | 3 (`8.94`, `8.98`, `9.44`) |

YDES inter-row gaps: `50, 60, 50, 65, 50, 65, 50, 30, 56, 70, 55, 60, 60, 35, …` seconds.
That is the scan-loop cadence, not a market event. **Forty rows, one price, thirty-four minutes.**

This is NOT the cross-restart replay defect that `_fire_once` fixes — it repeats WITHIN one
process life, on a cadence that matches `VWAP_BAR_CACHE_SECS`.

## ROOT CAUSE (read from code, `marcos_trading_bot.py`)

`detect_ma_pullback` is a **pure function of the bar slice**. Entry type 2 in the scan loop calls
it every cycle, and on a hit it (a) appends a full trade candidate to `breakouts` and (b) logs
`triggered_ma_pullback`. **Nothing marks the setup consumed.** The confirmation candle is
`completed[-1]`; while that same bar remains the last completed bar — and while the price still
satisfies `price > ccl` — the detector re-returns the identical fire on every pass.

Every other converting lane guards its emission with `_fire_once(lane, sym, k)` keyed on the fire
bar's bucket epoch (v2/grinder/bandpass/kevseq/prevwap all do this). ma_pullback has no `k` at all,
which is also why the archive alone could not diagnose it: the rows carry no bucket stamp.

The same pure-function-per-cycle shape drives the PULLBACK_FIRST pre-pass, which logged
`pullback_first_suppress` **210 times** — the identical count, from the identical cause.

## SCOPE — STATE, NOT LOGGING-ONLY

This is the more serious of the two possibilities. Each duplicate pass does not merely log: it
pushes a fresh candidate into `breakouts`, which then runs the **entire** downstream gate and
trade path (vel5 floor, day-gain floor, back-side, extension, chart gate, momentum, sizing).
The lane genuinely re-attempts the trade every cycle. Nothing in the ma_pullback path itself
stops a second entry; the only reason YDES did not trade forty times is that a downstream gate
rejected it forty times — and those rejections are themselves duplicated in the archive
(`ma_daily_bad` 105, `ma_low_room_soft` 178).

**Did any duplicate reach a fill?** No. 8/17 had exactly 4 `filled` rows — FIEE (ignition),
DFSC (ignition), NIVF (grinder), WFF (kevseq). **Zero ma_pullback fills.** So on this day the
defect cost counts, not dollars. That is luck, not design: had a gate flipped green mid-window,
the lane would have re-entered the same setup on the next cycle with nothing to stop it.

## THE FIX

Give the detector the bucket it never had, and gate the fire on it exactly as every other lane does.

1. `_bar_epoch(b)` — integer epoch seconds from a bar's ISO-UTC `time` field.
2. `_detect_ma_pullback` returns `"k": _bar_epoch(conf)` — the CONFIRMATION CANDLE's epoch.
   The confirmation candle IS the consumable unit: one buyer stepped in, once.
3. Entry type 2 gates on `_fire_once("ma_pullback", t, k)`. A blocked pass logs
   `ma_pullback_dup_suppressed` (the counterfactual stays visible, exactly as
   `replay_fire_suppressed` and `stale_fire_suppressed` do) and does NOT append to `breakouts`.
4. The PULLBACK_FIRST pre-pass row is gated by a NON-CONSUMING `_fire_seen()` peek, so the
   pre-pass cannot eat the mark that the real fire needs. `_ma_first_fire`'s flat_top-suppressing
   behaviour is left EXACTLY as it was — the pre-pass gates the ROW, never the control flow.

Kill switch: **`MA_PULLBACK_DEDUPE=0`** restores the pre-fix behaviour. `DEDUPE_FIRES=0` also
disables it (via `_fire_once`).

## FAILURE CONDITION (pre-registered — this fix is WRONG if…)

1. …a genuine SECOND ma_pullback setup on the same name and the same confirmation bar is
   legitimately tradeable. It is not: the detector returns at most one fire per call, and a new
   buyer stepping in prints a NEW confirmation candle with a strictly greater epoch, which
   `_fire_once`'s monotonic high-water mark admits.
2. …`_bar_epoch` returns 0 for the live bar format. `_fire_once` treats `k<=0` as UNKNOWN and
   **never blocks** — so a parse failure degrades to today's behaviour, never to a missed trade.
3. …`ma_pullback_dup_suppressed` rows show suppression at a price MATERIALLY different from the
   admitted fire's price on the same confirmation bar. That would mean the setup moved enough to
   be a different trade and the bar is the wrong bucket. Grade this from the suppression rows —
   they exist precisely so this is falsifiable from data rather than argued.
4. …ma_pullback's DISTINCT fire count drops. It must not: the fix removes repeats of an already-
   emitted bucket, never a first emission.

## CORRECTED 8/17 COUNTS

- `triggered_ma_pullback`: **210 rows → at most 123 distinct** (35 distinct tickers).
  YDES 40→1, GRNQ 36→3 by (price, ma).
- `pullback_first_suppress`: 210 rows, same inflation, same cause.
- Duplication factor: **210 / 123 = 1.71×**.
- Study population impact — stated with its discrepancy, not smoothed over: the 592-fire study
  counted ma_pullback at **193**, while the archive query used here returns **210** for the same
  day and status. The 17-row difference is UNEXPLAINED (different filter or different pull time);
  it is recorded rather than reconciled, because either number carries the same 1.71× inflation.
  Applying the measured factor: ma_pullback's **193 → ~113 distinct**, and the study total
  **592 → ~512 distinct** triggers. That is ~13.5% of the whole population being one lane
  re-logging itself. Any per-lane share computed on raw row counts over-weights ma_pullback by
  that much, and `pullback_first_suppress` (210 rows) carries the identical inflation.
