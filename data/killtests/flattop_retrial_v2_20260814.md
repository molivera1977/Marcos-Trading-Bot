# FLAT_TOP RETRIAL v2 — COOLDOWN + PULLBACK-DEPTH SWEEP (8/14/2026)

**VERDICT QUALIFIER (LIMITS, added 2026-08-17):** the doc discloses LOOKAHEAD in the scratch backtester it runs on. The cooldown/pullback-depth sweep is a parameter search over one construction with no OOS wall; its ranking is a hypothesis, not a verdict.
Follow-up to `entry_rebuilds_20260814_RESULTS.md` Strategy 1, whose verdict was
"churns 8 fires/day; needs a cooldown + minimum pullback depth before even shadow."
Backtester: scratchpad `flattop_v2.py` (v1 detector unchanged; walk-forward, bars in
order, no lookahead; stop-first on same-bar conflicts — tie goes AGAINST the trade).

## WHAT CHANGED vs v1
- (a) **Per-name cooldown**: 15 min after ANY fire before another entry on that name.
- (b) **Minimum pullback depth**: touch low must be >=1% / >=2% / >=3% below the break
  level (three variants). v1 accepted any low <= level, hence same-minute micro-refires.
- (c) 9:30-10:30 ET window split kept.
- Exits identical to v1: $500/position, half at +4%, remainder trails 10s EMA90
  (running-mean seed <90 bars), stop = pullback low, stop-first ties, EOD flatten.

## DATA
- Cache at run time: **95 files** (name-days) across **8 dates: 2026-08-04..08-13**
  (vs 39 files / 4 dates in v1 — the cache more than doubled, so v1 and v2 numbers are
  NOT same-sample comparable; the throttle effect is read from fires/day, not total $).
- Bars: tick-reconstructed 10s, RTH only (13:30-20:00Z). Same optimistic-fill caveats as
  v1 (close fills, exact stop/target fills, no slippage/halts/commissions).

## HAND-TRACE — ADGM 2026-08-04 (>=1% variant; vetoes shown working)
- 15:39:20 BREAK: close 0.8498 > base level 0.8475
- 15:39:30 PULLBACK: low 0.8400 <= level
- 15:48:50 RECLAIM: close 0.8498, depth 5.60% >= 1% -> ENTER 0.8498, stop 0.8000
- 16:10:20 SCALE half +4% (0.8838); 16:27:30 TRAIL exit 0.9232 < EMA90 0.9297
- 17:18:30 reclaim depth 0.30% < 1% -> VETO · 17:49:10 depth 0.35% -> VETO
- 17:50:20 RECLAIM depth 1.59% -> ENTER 0.9204 (125 min after prior fire — cooldown clear)
- 18:31:20 depth 0.43% -> VETO · 19:34:40 depth 0.98% -> VETO
Four of six raw fires vetoed on this name-day; both surviving trades won.

## RESULTS ($500/position, 95 name-days)
| variant | cohort | N | win% | total $ | mean $/trade |
|---|---|---|---|---|---|
| >=1% | ALL | 269 | 38% | **+1227.30** | +4.56 |
| >=1% | IN 9:30-10:30 | 48 | 44% | **+1534.72** | +31.97 |
| >=1% | OUT | 221 | 36% | -307.41 | -1.39 |
| >=2% | ALL | 163 | 45% | +912.89 | +5.60 |
| >=2% | IN 9:30-10:30 | 29 | 48% | +1185.80 | +40.89 |
| >=2% | OUT | 134 | 44% | -272.90 | -2.04 |
| >=3% | ALL | 105 | 55% | -112.92 | -1.08 |
| >=3% | IN 9:30-10:30 | 17 | 59% | +88.54 | +5.21 |
| >=3% | OUT | 88 | 55% | -201.45 | -2.29 |

Fires/name-day: v1 8.0 -> v2 2.8 (>=1%), 1.7 (>=2%), 1.1 (>=3%). The churn is dead.
Exit mix (>=1%): 158 stop / 91 trail / 20 eod (v1 was 77% stops; now 59%).

### THE OUTLIER — mandatory honesty pass
One trade, **YJ 2026-08-07 13:51:50, +$1,102.20**, sits in all three headline totals
(it passes 1% and 2% depth; its own variant rows above include it). Ex-YJ:
| variant | ALL ex-YJ | IN-window ex-YJ | OUT ex-YJ |
|---|---|---|---|
| >=1% | 267 tr, 37%, **+$132.35** (+0.50) | 47 tr, 43%, **+$432.52** (+9.20) | 220 tr, -$300.17 |
| >=2% | 161 tr, 44%, -$208.09 | 28 tr, 46%, +$83.60 | 133 tr, -$291.69 |
| >=3% | 104 tr, 55%, -$131.70 | 17 tr, 59%, +$88.54 | 87 tr, -$220.24 |
>=1% in-window ex-YJ daily: +28.29 / -62.35 / +11.22 / -72.15 / +144.84 / +298.71 /
+2.45 / +81.52 — **green 6 of 8 days**, and positive without the outlier.

## READ
1. **The v1 prescription worked.** Cooldown + a 1% depth floor turned -$0.42/trade
   (313) into +$4.56/trade (269) headline, +$0.50 ex-outlier — churn removal alone
   moved the whole book above water.
2. **The edge is in the first hour again** (same shape as the V2-flush finding):
   >=1% in-window is +$9.20/trade ex-outlier, green 6/8 days; every OUT-of-window
   cohort in every variant is negative.
3. **Depth sweep verdict: 1% is the floor, 3% is too strict.** Win% rises with depth
   (38->45->55%) but total $ falls — deeper pullbacks select safer but smaller
   reclaims and vetoes the big winners; >=3% is net negative overall.
4. Not a real OOS wall: 8 consecutive recent dates, one cache, optimistic fills, no
   halt modeling, raw detector (no live gate stack).

## VERDICT: **SHADOW-CANDIDATE — >=1% depth + 15-min cooldown, WINDOW-RESTRICTED 9:30-10:30 ET, shadow rows only**
In-window >=1% survives the outlier excision (+$432.52 ex-YJ, 47 trades, green 6/8
days) and the sample is now 8 dates / 95 name-days — past the Seam Scientist >=5-day
floor, though all recent and from one cache. Full-day (unwindowed) remains
NEEDS-MORE-DATA: ex-outlier +$132 on 267 trades is noise. Nothing here authorizes
behavior — shadow rows go to Marcos priced, per Auditor-Cannot-Authorize.
