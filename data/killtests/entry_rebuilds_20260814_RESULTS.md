# ENTRY REBUILDS v1 — BACKTESTS (8/14/2026)
Task-force run per Marcos 8/14 ("all entries rebuilt and rebacktested for next week").
Specs derived from `data/audits/mechanism_audits_20260814.md`. Nothing here goes live
without the room + Marcos. Backtester: session scratchpad `rebuild_bt.py` (walk-forward,
bars in order, no lookahead; stop-first on same-bar conflicts — tie goes AGAINST the trade).

## DATA COVERAGE (the biggest caveat)
- Cache: **39 of 714 runner-days** (5.5%), covering **4 dates only: 2026-08-10..08-13**
  (universe manifest spans 61 dates). Cache is still growing; this is a v1 pass on what exists.
- The planned first-30-dates vs last-31-dates OOS split is **degenerate** — every cached day
  is in the last half. Substitute crude split used: 8/10-8/11 vs 8/12-8/13. This is NOT a real
  OOS wall (Seam Scientist law: >=5 independent days before any ship; we have 4, all recent).
- Bars: tick-reconstructed 10s (time/OHLCV, floats cast). RTH only (13:30-20:00Z = 9:30-16:00 ET).

## FILL / COST ASSUMPTIONS (honest list)
- Entry fill = the completed 10s signal bar's CLOSE (no intra-bar fills, no assumed level fills —
  the audit's "fictional-fill" class deliberately avoided).
- Stop fill = exact stop price (optimistic: no slippage/gap-through modeling).
- Scale fill = exact +4% target when bar high >= target.
- No commissions/borrow/halt modeling. LULD halts NOT modeled — on these names that flatters results.
- $500 position, half scaled at +4%, remainder trails 10s 90-EMA (running-mean seed <90 bars) or EOD;
  stop always live on the remainder.

---
## STRATEGY 1: FLAT_TOP/ORB RETRIAL
Spec: 4x3min base with range <=12% -> 10s close breaks base high -> REAL pullback (10s low AT or
BELOW the level) -> reclaim confirmation (completed 10s bar closing back above level) -> enter at
that bar's close; stop = pullback low. (The era never tested this: PULLBACK_TOL=1% counted price
1% ABOVE the level as a dip and _confirm_reclaim was satisfied by the break bar itself.)

### Hand-trace — AEHL 2026-08-10 (first entry narrated; all 16 fires listed in run log)
- 13:47:40 BREAK: 10s close 6.0300 > base level 5.8405 (4x3min base range <=12%)
- 14:26:20 PULLBACK: low 5.6301 <= level 5.8405 (a real dip, 39 min after break)
- 14:26:30 RECLAIM: close 6.1100 back above level -> ENTER 6.1100, stop 5.6301 (pullback low)
- 14:27:10 SCALE half at +4% (6.3544)
- 14:28:10 TRAIL exit: close 6.0800 < EMA90 6.1566 -> flat. Trade P&L small positive.
(Same day later shows the failure mode: 15:09-16:29 a cluster of shallow re-fires stopped within
seconds — the detector re-arms instantly on each fresh micro-base and churns.)

### Results ($500/position)
| cohort | N | win% | total $ | mean $/trade | worst day |
|---|---|---|---|---|---|
| ALL | 313 | 22% | **-130.28** | -0.42 | 8/10: -335.92 |
| half1 (8/10-11) | 107 | 23% | -229.65 | -2.15 | |
| half2 (8/12-13) | 206 | 22% | +99.37 | +0.48 | |
Daily: 8/10 -335.92 · 8/11 +106.27 · 8/12 -53.32 · 8/13 +152.70. Exit mix: 240 stop / 62 trail / 11 EOD.

### Verdict: **NEEDS-MORE-DATA** (and needs a frequency throttle before any shadow)
The real-pullback design is roughly breakeven (-$0.42/trade over 313) where the era's fake version
lost -$394..-$430 — so the retrial was deserved and the design is not refuted. But 8 fires/day is
churn: most losses are same-minute micro-base re-fires. v1.1 must add a cooldown + minimum
pullback depth before shadow rows. Do not shadow as-is.

---
## STRATEGY 2: VWAP_RECLAIM BAND-PASS (encoding the 7/31 study)
Spec: session VWAP = cum(close*vol)/cum(vol) from 9:30 ET; cross above VWAP; HOLD 12-30
consecutive 10s closes above (2-5 min); then a new minor high above the hold-period high ->
enter at that bar's close; stop = hold-period low. First new-high per cross-episode decides the
cohort: <12 closes = "just-crossed" (the 7/31-condemned band) — counted AND simulated separately
with identical exits, one-at-a-time, to test whether the band-pass matters.

### Hand-trace — STKH 2026-08-10
- 13:42:40: cross-episode has held 13 consecutive 10s closes above VWAP (130s; inside 12-30 band); VWAP 4.4816
- 13:42:40 NEW MINOR HIGH: bar high 5.3800 > hold high 5.0100 -> ENTER at close 5.2060, stop = hold low 3.9500
- 13:42:50 SCALE half at +4% (5.4142)
- 14:01:10 TRAIL exit: close 4.7250 < EMA90 4.7606 -> flat. P&L **-$13.10**.
(Note the trade's own anatomy: hold-low stop 24% away — the band-pass hold on these movers often
starts at a deep low, making the stop structurally wide and the trail the real exit.)

### Results ($500/position)
| cohort | N | win% | total $ | mean $/trade | worst day |
|---|---|---|---|---|---|
| BAND-PASS (12-30) | 23 | 26% | **-325.86** | -14.17 | 8/10: -99.88 |
| just-crossed (<12) | 285 | 33% | +600.43 | +2.11 | 8/13: -330.71 |
Band-pass daily: -99.88 / -88.39 / -65.99 / -71.61 — **negative all 4 days**.
Just-crossed daily: +55.86 / +114.22 / +761.05 / -330.71 (the +$600 is one day, 8/12, doing the work).

### Verdict: **NEEDS-MORE-DATA, leaning REFUTED-as-encoded**
The 7/31 finding did NOT replicate on this window: the band-pass arm lost every day (N=23, small),
and the "worst-trade" just-crossed cohort was net positive (concentrated in one day). Honest read:
on 4 days of very recent tape, this encoding of the band-pass has no support. Do not shadow.
Re-run when the cache crosses ~150 runner-days; if the sign holds, write REFUTED with the
7/31 study formally autopsied (its band-pass was measured on a different signal definition —
that difference must be named before any final verdict).

---
## STRATEGY 3: V2 CONFIRMED-PULLBACK (Hidden Entry Architect's Kev blueprint)
Spec: established runner (whole universe qualifies) -> fast flush (>=3% drop from the 2-min-local
high, which is also the 5-min high, within <=2min) into/near an anchor (session VWAP or a prior
4x3min consolidation high, within 2%) -> buyers step in: first 10s bar with a higher low AND close
above prior bar's high -> enter at that close; stop = flush low. Flush window expires after 3 min.

### Hand-trace — AEHL 2026-08-10
- 13:30:20 FLUSH: -7.1% from 2-min high 5.5000 to 5.1100, flush low within 2% of VWAP 5.0139
- 13:30:50 BUYERS STEP IN: higher low (5.5650 > 5.2960) + close 5.5650 > prior high 5.5600 -> ENTER 5.5650, stop 5.1100
- 13:31:10 SCALE half at +4% (5.7876)
- 13:34:00 TRAIL exit: close 5.5500 < EMA90 5.5627 -> flat. P&L **+$9.33**.

### Results ($500/position)
| cohort | N | win% | total $ | mean $/trade | worst day |
|---|---|---|---|---|---|
| ALL | 486 | 30% | -545.18 | -1.12 | 8/13: -735.37 |
| **IN window 9:30-10:30 ET** | **112** | **41%** | **+994.76** | **+8.88** | 8/13: -193.23 |
| OUT of window | 374 | 27% | -1539.94 | -4.12 | |
In-window daily: 8/10 +120.47 · 8/11 +254.95 · 8/12 +812.56 · 8/13 -193.23 (**3 of 4 days green**).
Half-split (all trades): h1 -261.74 / h2 -283.44. Exit mix: 341 stop / 134 trail / 11 EOD.

### Verdict: **MONDAY-CANDIDATE (shadow, WINDOW-RESTRICTED 9:30-10:30 ET ONLY)**
The first-hour arm is the one positive, doctrine-consistent result in this run: +$994.76 on 112
trades, 41% wr, mean +$8.88, green 3 of 4 days — and the same detector outside the window bleeds
-$1,539.94, which is itself evidence the edge is the WINDOW + flush interaction, exactly Kev's
first-hour thesis and the F-control lesson (must beat don't-trade — in-window it does, on this
sample). 112/39 ≈ 2.9 fires/runner-day is rich but shadow-appropriate. Caveats: 4 days, all
recent, 8/12 carries $812 of the $995; one red day. SHADOW ROWS ONLY — no order flow.

---
## SUMMARY FOR THE ROOM
| entry | verdict | one line |
|---|---|---|
| FLAT_TOP retrial | NEEDS-MORE-DATA | design ~breakeven (era's -$400 was fake-pullback artifact); churns 8/day, needs cooldown + depth floor first |
| VWAP band-pass | NEEDS-MORE-DATA (leaning REFUTED-as-encoded) | lost all 4 days; 7/31 finding did not replicate; just-crossed cohort actually net + (one-day driven) |
| V2 flush (first hour) | **MONDAY-CANDIDATE (shadow)** | +$994.76 / 112 trades / 41% wr in 9:30-10:30; bleeds badly outside the window |

Standing caveats binding all three: 5.5% cache coverage, 4 consecutive recent dates (no real OOS),
optimistic fills, no halt modeling, no gauntlet gates applied (raw detector census — the live
gate stack would cut N substantially). Re-run this exact script as the cache fills.
