# OPEN-HOLES REGISTRY (seeded 2026-08-16, Marcos: "start the process now")

Machine-parsed by data/holes/holes_sweep.py (nightly 23:30 launchd, after the 23:00 wall grader).
One block per hole. Field lines are `- key: value`. Statuses: OPEN | RUNNING | VERDICT | RAN (auto-run,
verdict line captured, awaiting officer confirmation) | REFUTED | BLOCKED (data not available).
The sweep picks the top-N (HOLES_PER_NIGHT, default 2) OPEN holes IN FILE ORDER whose `test` is
`engine=script` with an existing script and existing `requires` paths. `engine=oos` holes are graded from
data/history/OOS_WALL.md day count (RUNNING with day count until >=5 days, then VERDICT vs bar).
`engine=manual` / `engine=data` holes are never auto-run (listed so nobody re-runs blind / forgets).
Refuted items STAY listed with their verdict + numbers so nobody re-runs them blind.

### H01 · Vertical / rocket regime entries (#48)
- status: RUNNING
- owner: Rocket Rider + Hidden Entry Architect
- hypothesis: crowned/vertical names (40%+ AND halt/fresh-highs) have a tradeable entry that beats the F-control (don't-trade -$4,012 bar); v1 hidden runners were BLUE-SKY regime, not level-proximity
- test: engine=manual | note=anatomy study running as agent 8/16 (rocket sleeve tier-2 with own bar + bleed budget, ledger dbc76d7)
- bar: must beat don't-trade AND 2-slot portfolio bar (mean/median/green%/halves/worst)
- last_run: 2026-08-16 (agent, in progress)
- verdict: -

### H02 · Seam / beginning-entry (#38)
- status: OPEN
- owner: Seam Scientist
- hypothesis: an earlier-than-confirmation trigger on the 5s/10s tape captures the first leg on winners without net-negative filters (8/8 state: pattern real on 5 winners, every simple filter net-negative on the single 5s day)
- test: engine=script | script=data/killtests/ride_seams_week10s_20260807.py | args= | requires=data/universe/bars10s
- bar: >=5 OOS days before ship; per-trade AND portfolio bar
- last_run: 2026-08-07
- verdict: - (pattern real; no shippable filter yet)

### H03 · Day-2 continuation
- status: OPEN
- owner: Handicapper + Seam Scientist
- hypothesis: yesterday's runner (>=+40% close, held >50% of range) continues day-2 above prior-day high / premarket high with positive expectancy under E3
- test: engine=script | script=data/killtests/sunday_afternoon_studies_20260816.py | args=--only day2 | requires=data/killtests/wall_drill_cache_20260815;data/universe/manifest.json | note=script lacks --only today; sweep will mark BLOCKED until a day2 detector exists
- bar: 2-slot portfolio bar
- last_run: -
- verdict: -

### H04 · Ex-hidden names under E3 exits (sweep #1)
- status: RUNNING
- owner: Hidden Entry Architect + Trade Manager
- hypothesis: hidden-v1 entry set re-exited by E3 (bank 1/2 +10%, 10%-off-high trail) beats v1's -$4,012 and the F-control
- test: engine=manual | note=sweep #1 running as agent 8/16
- bar: > F-control (don't-trade) AND positive mean-after-costs
- last_run: 2026-08-16 (agent, in progress)
- verdict: -

### H05 · Eye: relative volume by time-of-day
- status: BLOCKED
- owner: Feed Engineer + Quartermaster
- hypothesis: rel-vol vs same-minute baseline discriminates entries (needs 20-day per-minute volume baseline per name)
- test: engine=data | note=data availability: needs per-name per-minute volume history >=20 days; harvester covers universe days only
- bar: -
- last_run: -
- verdict: -

### H06 · Eye: SPY regime
- status: BLOCKED
- owner: Feed Engineer
- hypothesis: SPY intraday trend/day-type conditions small-cap continuation
- test: engine=data | note=data availability: SPY 10s/1-min bars not in universe cache; needs SIP pull + join
- bar: -
- last_run: -
- verdict: -

### H07 · Eye: ATR extension
- status: BLOCKED
- owner: Systems Quant
- hypothesis: extension in ATR units at trigger predicts capture (prior extension scalars REFUTED as setup-quality; this is the ATR-normalized retest)
- test: engine=data | note=needs daily ATR history per name (14-day); manifest has prev_c only
- bar: -
- last_run: -
- verdict: -

### H08 · Eye: catalyst
- status: BLOCKED
- owner: Handicapper
- hypothesis: catalyst class (news/offering/none) conditions expectancy; probe 8/16 = catalyst_probe_20260816 (news cache partial)
- test: engine=data | note=needs a news source with timestamps for all universe days; catalyst_probe_20260816_news_cache.json is partial
- bar: -
- last_run: 2026-08-16 (probe)
- verdict: - (probe only)

### H09 · Band-pass VWAP reclaim OOS
- status: OPEN
- owner: Reclaim Architect + Side Marshal
- hypothesis: 2-5 min band-pass reclaim (frozen arms A/B/C, 7/29) holds out-of-sample under E3
- test: engine=oos | lane=band-pass | note=not yet a wall lane; graded from OOS_WALL when the shadow grader stamps it
- bar: >=5 OOS days; 2-slot portfolio bar
- last_run: -
- verdict: -

### H10 · Prev-VWAP (yesterday's VWAP as anchor) OOS
- status: OPEN
- owner: Cartographer
- hypothesis: prior-day VWAP acts as a respected level (vwap_anchor_killtest in-sample); OOS respect grade vs random prices
- test: engine=oos | lane=prevwap | note=weekly level-respect grade
- bar: respect rate > random-price control, >=5 days
- last_run: -
- verdict: -

### H11 · v2 calibrated OOS
- status: OPEN
- owner: Hidden Entry Architect
- hypothesis: v2 calibrated (v2_calibration_20260814) is positive OOS as a SEPARATE lane (not in the portfolio number)
- test: engine=oos | lane=v2
- bar: >=5 wall days; must beat don't-trade; wall day 1 (8/14 pre-wall) N=250 $-2943.88
- last_run: 2026-08-14 (wall day 1, pre-wall)
- verdict: -

### H12 · Ignition cell OOS
- status: OPEN
- owner: First Hour
- hypothesis: ignition census 8/14 (open profitable, after-10 bleeds) holds forward; cutoff not shippable until OOS
- test: engine=oos | lane=ignition | note=graded from decisions archive ignition rows by minute bucket
- bar: >=5 days; open-cell positive, after-10 cell not positive
- last_run: 2026-08-14 (census)
- verdict: -

### H13 · PBL trail vs E3
- status: OPEN
- owner: Trade Manager
- hypothesis: prior-bar-low trail after bank captures more than E3's 10%-off-high trail on the same entries
- test: engine=script | script=data/killtests/edge_stresstest_F_20260815.py | args= | requires=data/killtests/wall_drill_cache_20260815 | note=E3 baseline; PBL arm needs adding to the harness (exit variants)
- bar: beat E3 on mean AND median AND worst-day, same entries
- last_run: -
- verdict: -

### H14 · Exhaustion-exit layer (volume climax)
- status: OPEN
- owner: Trade Manager + Convexity Trader
- hypothesis: exiting the runner leg on a volume-climax bar (>=3x rolling 10s vol + upper wick) beats E3 trail on runners
- test: engine=script | script=data/killtests/edge_stresstest_F_20260815.py | args= | requires=data/killtests/wall_drill_cache_20260815 | note=climax arm to be added to exit variants
- bar: beat E3 on runners' captured $ without hurting median
- last_run: -
- verdict: -

### H15 · Afternoon tightening schedule
- status: OPEN
- owner: Trade Manager
- hypothesis: tightening the trail after 12:00 (10%->6%) and after 14:00 (->4%) captures more of open winners than flat 10%
- test: engine=script | script=data/killtests/edge_stresstest_F_20260815.py | args= | requires=data/killtests/wall_drill_cache_20260815 | note=schedule arm to be added
- bar: beat E3 mean/median; power-hour bleed (H17) says 15:00+ is distribution
- last_run: -
- verdict: -

### H16 · No-progress rule (15-min time stop)
- status: REFUTED
- owner: Trade Manager
- hypothesis: exit if no progress at 15 min
- test: engine=script | script=data/killtests/sunday_afternoon_studies_20260816.py | args= | requires=data/killtests/wall_drill_cache_20260815
- bar: -
- last_run: 2026-08-16
- verdict: REFUTED hard. Grinder fired 222/387: rule -$913.27 vs default +$5,835.69 (lane +$10,676 -> +$3,927). Break-attack fired 342/634: rule -$3,221.00 vs default +$11,126.55 (lane +$17,031 -> +$2,683). Slow starters carry the winners; time-stops kill the E3 runner shape. Do NOT re-run.

### H17 · Power hour lane (15:00-16:00)
- status: REFUTED
- owner: First Hour + Momentum Operator
- hypothesis: 15:00-16:00 breakouts as a lane
- test: engine=script | script=data/killtests/sunday_afternoon_studies_20260816.py | args= | requires=data/killtests/wall_drill_cache_20260815
- bar: -
- last_run: 2026-08-16
- verdict: REFUTED as a lane. Worst bucket for every lane (grinder +$7.75/tr 44% win; break-attack -$10.02/tr; band-pass +$0.24/tr; v2cal -$12.90/tr). Only 13.4% of universe days make a new RTH high after 15:00 (~86% do not; article claim reproduced). Distribution window, nothing to build.

### H18 · ORB (15-min opening range breakout)
- status: REFUTED
- owner: First Hour
- hypothesis: ORB-15 with ORL stop as an additive second lane next to break-attack
- test: engine=script | script=data/killtests/orb_vs_ba_20260816.py | args= | requires=data/killtests/wall_drill_cache_20260815
- bar: combined 2-slot > BA-only on mean AND median
- last_run: 2026-08-16
- verdict: REDUNDANT (letter: additive by $0.05/d mean). Solo ORB-15 passes bar (371 tr, 78% win, +$12,114.57, +$32.65/tr) but 51% of signals = the BA break re-confirmed ~100s later; r=+0.623 with BA; green% and worst day degrade at 2 slots; BA dominates at 3 slots. BA keeps the slot. Only ORB-only remainder (no BA within 10 min, +$55/d solo, worst -$283) survives as observe-only hypothesis.

### H19 · Halt retest (10s mechanical)
- status: REFUTED
- owner: Rocket Rider
- hypothesis: patient post-halt retest of the halt level under E3
- test: engine=script | script=data/killtests/sunday_afternoon_studies_20260816.py | args= | requires=data/killtests/wall_drill_cache_20260815
- bar: -
- last_run: 2026-08-16
- verdict: REFUTED at full cache. N=36 (26 up/10 down), 19% win, -$1,078.81 total, -$29.97/tr; up-halts -$855.15, down-halts -$223.66; controls also negative. Halt-lane doctrine (arm-only converts, 5s feed, crowns, half size) untouched.

### H20 · Catalyst inversion OOS
- status: OPEN
- owner: Handicapper
- hypothesis: catalyst_probe_20260816 in-sample inversion (no-catalyst names outperform) holds OOS
- test: engine=oos | lane=catalyst | note=needs catalyst stamps on decision rows (H08 blocks full coverage)
- bar: >=5 days; inversion sign holds
- last_run: 2026-08-16 (probe)
- verdict: -

### H21 · Kev MISSING: day-2 same-stock playbook / character book
- status: OPEN
- owner: Seam Scientist + Handicapper
- hypothesis: prior-day flush depth / base level / reclaim structure pre-identifies day-2 entry zones (Kev 8/14: "Over 1300 in 5 SECONDS")
- test: engine=script | script=data/killtests/sunday_afternoon_studies_20260816.py | args=--only day2 | requires=data/killtests/wall_drill_cache_20260815;data/character_book.json | note=joins H03; script lacks --only today (BLOCKED until day2 detector exists); character_book.json is the store; needs level-respect of prior-day levels on day-2 tape
- bar: prior-day levels respected > random-price control
- last_run: -
- verdict: -

### H22 · Kev MISSING: partial fills at entry, no chasing
- status: OPEN
- owner: Execution Surgeon + Webull Broker Desk
- hypothesis: accept partial fills at the limit, never re-price up in a fast squeeze (Kev 8/14 "230 SQUEEZE")
- test: engine=manual | note=behavior item; needs Webull partial-fill semantics ($5 place+cancel test owed) — priced to Marcos before any change (auditor cannot authorize behavior)
- bar: -
- last_run: -
- verdict: -

### H23 · Kev MISSING: listing-day volume baseline
- status: BLOCKED
- owner: Seam Scientist + Quartermaster
- hypothesis: climactic listing-day volume returning off lows = buy signal (Kev 8/14 SPCX)
- test: engine=data | note=needs listing-day daily volume per name (IPO/direct-listing dates); not in manifest
- bar: -
- last_run: -
- verdict: -

### H24 · Kev MISSING: wedge compression day-2 trigger
- status: OPEN
- owner: Seam Scientist
- hypothesis: tightening wedge into the close/weekend -> day-2 breakout entry (Kev 8/14 "TOP 3 FOR MONDAY")
- test: engine=script | script=data/killtests/sunday_afternoon_studies_20260816.py | args=--only wedge | requires=data/killtests/wall_drill_cache_20260815 | note=wedge detector not written; sweep BLOCKED until it exists
- bar: 2-slot portfolio bar
- last_run: -
- verdict: -

### H25 · Kev MISSING: MACD as context only
- status: OPEN
- owner: Execution Surgeon
- hypothesis: MACD as lagging trend-context filter (never a trigger) adds no expectancy vs EMA90/VWAP side already used — expected REDUNDANT
- test: engine=script | script=data/killtests/edge_stresstest_F_20260815.py | args= | requires=data/killtests/wall_drill_cache_20260815 | note=MACD-context ablation to be added to the harness
- bar: any lift on mean AND median vs baseline
- last_run: -
- verdict: -

### H26 · Min-stop exempt cohort re-grade (weekly)
- status: OPEN
- owner: Execution Surgeon
- hypothesis: the 6% min-stop-width floor's exempt cohort still nets positive as more rows land (8/14 regrade: N per band small)
- test: engine=script | script=data/killtests/killtest_minstop.py | args= | requires=data/killtests/minstop_exempt_regrade_20260814_RESULTS.txt | note=weekly cadence; re-run Fridays
- bar: exempt cohort mean-after-costs >= 0
- last_run: 2026-08-14
- verdict: - (N per band SMALL; room votes)

### H27 · Runway 0.7-1R edge (re-grade after 2 more weeks)
- status: OPEN
- owner: Trade Manager + Statistician
- hypothesis: runway_graded_20260804 0.7-1R edge holds after 2 more weeks of rows
- test: engine=oos | lane=runway | note=re-grade date >= 2026-08-28; runway_wall_live_check.py
- bar: >=10 new trading days; edge sign holds
- last_run: 2026-08-04
- verdict: -
