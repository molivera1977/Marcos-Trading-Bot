# OPEN DEFECT — 2026-08-18 — CDTG 14:16:43: two lanes filled one name in the same second

Opened by Marcos ("open the defect") after he asked how a CDTG trade "counted as a reclaim".
It did not: `reclaim_subtype` is None on all three CDTG RTH rows and the reclaim lane never
fired. The question surfaced two different, real defects instead.

## THE ROWS (verified, live trade records, 2026-08-18)

| entry | time ET | entry_type | reclaim_subtype | stamped session_vwap | vs VWAP | P&L |
|---|---|---|---|---|---|---|
| $5.53 | 12:59:39 | kevseq | None | 5.49 | +0.68% | +$18.23 |
| $7.76 | 14:16:43 | kevseq | None | **7.11** | +9.12% | −$32.87 |
| $7.78 | 14:16:43 | ma_pullback | None | **4.6719** | **+66.53%** | −$26.76 |

Both 14:16:43 fills also carry `day_gain_at_entry` 177%, and ma_pullback stamped
`entry_vs_ema90_pct = 94.29` — it bought ~94% above the 90-EMA.

## D1 — SAME-NAME CONCURRENT FILL (no per-name mutual exclusion at the fire site)

kevseq and ma_pullback both filled CDTG at 14:16:43. Two positions, two stops, two risk
allocations on one ticker. Combined **−$59.63**; the overlapping (second) leg alone **−$26.76**.

SCOPE — MEASURED, NOT ASSUMED (era 7/13+, 437 rows, both censuses run 8/18 ~18:5x ET):
  * same ticker + same entry second, different lane: **1 event** (this one).
  * position B entering before position A exits, same name, any gap: **1 event** (this one).
    B entered 0s after A and 326s before A exited.

So this is ISOLATED, not endemic. An earlier statement in-session that it was a broad
arbitration hole was WRONG on scale and is corrected here: the CDTG pair is the entire
known population.

WHY IT STILL MATTERS: the bot's slot/capital accounting and every lane-contention study run
this session (`lane_reorder_20260818.py`) assume ONE position per name at a time — the study
models a name as "busy" until its exit bar. If the live path can double-fill even rarely, the
arbitration being tuned is not the arbitration being run.

NOT YET DETERMINED: why the two lanes did not see each other. Candidates NOT tested —
(a) `found_entry`/traded suppression is keyed per-lane rather than per-ticker, (b) the two
fire sites sit in different branches of the scan block (kevseq at :9740 inside the nested
chain, ma_pullback outside it), (c) a slot check that reads state written after both fired.
No cause is claimed until a check runs.

## D2 — VWAP STAMP DISAGREEMENT, 52%, SAME TICKER AND SAME SECOND

kevseq stamped `session_vwap = 7.11`; ma_pullback stamped `4.6719`. Same name, same second.
Spread **52.2%**. At least one is wrong, and BOTH fed live gate decisions — the extension
check ma_pullback passed reads "+66.53% above VWAP" off the lower number.

SCOPE: 1 event in the era census (it can only be detected where two rows share a timestamp,
so the census CANNOT bound how often a single lane stamps a wrong VWAP with no second row to
disagree with it — that is a real blind spot in this measurement, stated rather than papered
over).

CANNOT ADJUDICATE YET: the 10s SIP universe cache has no `2026-08-18_CDTG.json` (cache runs
through 8/17; today's tape is not ferried). Computing the true session VWAP for 14:16:43 ET
is the deciding check and it HAS NOT RUN. Neither number is claimed correct.

## D3 (observation, not yet a defect) — EXTENSION

ma_pullback bought a name up 177% on the day, ~94% above its EMA90, at (by its own stamp)
66.5% above VWAP. Whether the extension guard was blind here or was passed a bad VWAP is
exactly what D2 blocks answering.

## NEXT CHECKS (none of these have run)

1. Ferry 8/18 tape, compute CDTG session VWAP at 14:16:43 ET, decide which stamp is corrupt.
2. Trace both 14:16:43 fires through the fire sites: what per-ticker guard should have stopped
   the second, and why it did not.
3. Rig: no gate anywhere pins "one open position per ticker". Add it as a class-killer once
   the cause is known (per `feedback_kill_the_class_not_instance` — the pin goes on the class,
   not on CDTG).
4. Bound D2 honestly: audit single-lane VWAP stamps against the tape for a full day, since the
   same-second census structurally cannot see them.

## STATUS

OPEN. Nothing shipped, nothing committed against this. Cost to date: −$59.63 (the pair),
of which −$26.76 is the overlapping leg that per-name exclusion would have prevented.
