# BLIND-WINDOW LEDGER v1 — First-Hour Autopsy, Wednesday 2026-07-22

_Owner: Opening Bell (17th lens). Task #82. Law: a blind window is a defect with a number._
_Sources: /api/decisions_archive 7/22 (5,713 rows), /api/trades (6 real trades), /api/bars 1-min (strict 7/22-filtered)
+ ~10s series (LABT/ZCMD/ADVB), data/killtests/RESULTS_LEDGER.md, reclaim_replay_20260722.txt (31 fires),
stage1_conversion_20260722.txt, Kev transcripts (Wed 7/22 picks zlCFR8H_XdY, Wed update VEQdAW1Bp5E, Thu 7/23 AnS1I-BEHNE).
Morning Railway logs are gone (old deployment) — archive + bars are the timeline. All times ET._

Day result: 6 real trades, **−$7.68** (SKYQ −25.54, YHC −54.76, SNTG +8.26, MTEN +14.27, ADVB +31.17, PN +18.92).

---

## 1. Minute-level timeline 8:43 → 10:30

Tags: **WORKED** (did its job) / **BLIND** (couldn't see or couldn't act) / **WASTED** (active, effort misdirected).

| Time | Event | Tag | Evidence (figures inline) |
|---|---|---|---|
| ≤8:45 | Bot asleep. LABT ran 1.88→7.72 (+310%) in 27 min, 8:00→8:27, on trial-data news; ADVB 7.32→10.80 (+48%) 7:00→7:30; INLF pre-high 7.39 (+176% @4:21); INM pre-high 5.52 (+177% @7:00) | BLIND | bars: LABT 8:00 close 1.88, 8:27 close 7.11, pre-high 7.72@8:27; structural — boot is 8:45 by design |
| 8:46:15 | Boot: `daily_loaded` × 22 names in one burst (LABT, INLF, INM, ZCMD, MNDR, KUST, ADVB, DCOY, CHNR, JAGX, CRIS, MGIH, SNTG, WCT, CHAI, AEHL, ACCS, LITB, SKYQ, VIDA, OMH, SLGB) | WORKED | selection was right: all 5 of the day's top-5 window movers (ZCMD/ADVB/KUST/INLF/AEHL) were on the boot list; LABT was row 1 |
| 8:46–9:30 | **Zero decision rows for 44 min** (next row is 9:30:35 `_exec_health`). No premarket entry lane; curl lanes wired dead (#89). Meanwhile ZCMD 1.87→2.60 (+39.1%), OMH +15.0%, INLF +14.1% (8:46→9:15) | BLIND | archive row count 8:47–9:29 = 0; replay shows reclaim fires the machine WOULD have taken in this window: INM 9:01:30 (maxR 2.3), SKYQ 9:10:10, KUST 9:25:40 |
| 8:48:50 | Recorder ~10s tape begins for boot names — LABT's first 10s bar is 8:48:50, **22 min after its 7.72 top** | BLIND | LABT~10s first row 08:48:50; n(7/22)=3,324 |
| 9:15–9:16 | Recorder downshift drops top movers (#68): 10s tape stops at 9:16:00 sharp for LABT and ZCMD | BLIND | LABT~10s gap 9:16:00→9:44:10 (28.2 min); ZCMD~10s gap 9:16:00→9:46:30 (30.5 min) |
| 9:15–9:41 | What moved while the top-mover tape was dark: AEHL +35.4% (0.6176→0.8362), ZCMD +23.6%, KUST +22.3%, LABT +18.5% (5.78→6.85), LHSW +16.6%, OMH +16.0% | BLIND | 1-min bars, window 9:15→9:41 |
| 9:30:00 | Open. LABT opens 6.50, prints first-hour high 6.85 in the 9:30 bar, then fades all day (10:30: 3.93) — no long lane needed RTH | WORKED | LABT o930 6.50, fh high 6.85@9:30, 10:30 close 3.93 — skipping LABT RTH was correct |
| 9:30:35 | First `_exec_health` OK: api_429=0, timeouts=0 | WORKED | health telemetry alive from the open; **api_429=0 in every row all day** — the "429 storm" anchor is NOT visible in the archive [UNVERIFIED — it lived in recorder logs, now gone] |
| 9:33:20 | First trigger: OMH ignition @0.3869 → chart_gate_block (Kev level 0.65 not broken) | WORKED | OMH window high 0.41 — never near 0.65; correct skip per Kev's own plan |
| 9:33–10:25 | **12 rescan `daily_loaded` bursts** (9:33, 9:36, 9:39, 9:42, 9:48, 9:54, 10:01, 10:04, 10:12, 10:14, 10:25 + 10:43) ≈ 264 redundant daily loads; each wipes per-ticker state (#81) | WASTED | archive: zero `consolidating`/`watching`/`break_armed` rows exist before **10:37:10** — the pullback/ORB state machines never matured for the entire first hour; only the stateless ignition lane could fire |
| 9:36:15 | KUST ignition trigger @1.2299 → blocked (level 1.27 not yet broken) | WORKED→BLIND | the block was right at 9:36; but KUST then broke 1.27 and ran to 1.85 @10:00 (+46% past the level) with **no re-trigger row in the window** — trigger-once-then-amnesia |
| 9:39:11 | WCT trigger → chart_gate_allow then spread_reject (spread 17.64%); AEHL trigger @0.7966 → blocked (level 1.00) | WORKED | AEHL window high 0.99 — Kev's update demanded ">a dollar"; both guards correct |
| 9:42:36 | **SKYQ ignition FILLED @4.645** — the exact post-entry high; stopped 9:49:41, −$25.54 | WASTED | trade record: entry 4.64, highest 4.645, exit 4.45; ignition bought the top of the spike |
| 9:43:31 | INLF trigger @3.66 → blocked (level 4.75). Reclaim lane would have fired 9:44:10 and 10:08:00 (maxR **7.02**) — lane wired dead (#89) | BLIND | reclaim_replay: INLF 10:08 entry 3.805, maxR 7.02; INLF fh high 4.8599@10:23 (+50.5%) |
| 9:52–9:54 | Rescan wipe (#81 anchor): bursts at 9:48:31 and 9:54:22 flank it; SNTG reclaim replay-fire 9:42:10 (maxR 5.23) also unseen live | BLIND | archive daily_loaded 29 rows @9:48, 25 @9:54 |
| 9:53:27 | INM @2.0999 and SNTG @2.5393 triggers → both blocked (levels 2.50 / 2.55) | WORKED | INM never re-approached 2.50 in window (high 2.33); SNTG block correct at that price |
| 10:02:12 | **SNTG ignition FILLED @2.5901** (level 2.55 broken, entry +1.6% over level) → later +$8.26 HEALTH FOLD | WORKED | the one Kev-grammar entry of the window: at-the-level; post-entry high 2.8549 (+10.2%) |
| 10:05:33 | YHC trigger → **vel5_reject** (entry_vel5 −1.08) | WORKED | vel5 floor doing its job |
| 10:14:34 | ADVB `rocket_armed` @11.87 (vel 29.2) → never triggered. ADVB fh high 13.17 @10:19 — and ADVB~10s has a gap **10:13:50→10:20:00** exactly over the push to high | BLIND | the curl-confirm window had no tape; ADVB finally entered 14:46 via ma_pullback (+$31.17 vs day high 18.26) |
| 10:18:59 | LHSW `rocket_armed` @2.6131 (vel 26.7) → no trigger | BLIND | LHSW fh high 2.80 |
| 10:28:24 | ZCMD `rocket_armed` @6.63 (vel 162.1) — **after** the 2.26→6.63 (+193%) leg completed, and at the local top (10:43 print: 4.97) | BLIND | ZCMD~10s gaps 9:16→9:46→10:16→10:27→10:33: the day's #1 mover was tape-dark for ~72 of the 77 min 9:16–10:33 |
| 10:30:09 | **YHC ignition FILLED @2.185** → −$54.76 (post-entry high 2.2348, +2.3%) | WASTED | second top-tick ignition fill of the morning; the 10:05 vel5 reject had been right |
| Post-window notes | ZCMD armed 9× (10:28→11:29, prices 6.63/6.30/6.24/8.18×5/11.19); single `triggered_rocket` 11:49:59 @8.8461 → **momentum_reject** ("1.9× base, 17% of peak") — fired 21 min AFTER the day high 11.96 @11:28. Day-gain floor's first live reject: 11:01:24 SNTG (day_gain 17.22 < floor 30). First `consolidating` 10:37:10 (AEHL), first `watching`/`break_armed` 10:39:50. | — | archive rows quoted |

Window trades P&L (9:30–10:30 entries): SKYQ −25.54, SNTG +8.26, YHC −54.76 = **−$72.04**.

---

## 2. BLIND-WINDOW LEDGER v1

| # | Window (ET) | Min | Cause | Names affected | What moved during it | Defect | Overnight fix? | Status |
|---|---|---|---|---|---|---|---|---|
| BW-0 | 04:00–8:45 | 285 | **Structural boot blindness** — bot doesn't exist premarket | LABT, ADVB, INLF, INM, everything | LABT 1.74→7.72 (**+343%**, core move 8:00–8:27); ADVB +48% 7:00–7:30 incl. the day's monster reclaim (replay 07:08 fire, maxR **24.3**); INLF +176%; INM +177% | NEW → Opening Bell open-lane gap | **NONE** | **OPEN — the #1 gap** |
| BW-1 | 8:46–9:30 | 44 | Bot awake, **no premarket lane + curl lanes wired dead**; archive has 0 rows 8:47–9:29 | all 22 boot names | ZCMD +39.1%, OMH +15.0%, INLF +14.1% (8:46→9:15); replay reclaim fires INM 9:01 (maxR 2.3), SKYQ 9:10, KUST 9:25 all unseen | #89 | 7a72c83 (curl detectors step unconditionally) — opens the 8:45+ premarket reclaim class | PARTIALLY CLOSED (acceptance = first live/shadow reclaim row) |
| BW-2 | 9:16–9:44 | 28–31 | **Recorder 9:15 downshift dropped top-10 movers** | LABT, ZCMD, INM, CRIS, ADVB (top-10 movers) | AEHL +35.4%, ZCMD +23.6%, KUST +22.3%, LABT +18.5%, LHSW +16.6% (9:15→9:41 bars) | #68 | de31e74 reserve-first reseed, boundary matched to downshift | CLOSED pending Thu acceptance |
| BW-3 | 9:33–10:37 | 64 | **Rescan state amnesia** — 12 daily_loaded bursts wipe per-ticker state; pullback/ORB/reclaim machines never mature | every name | ZCMD +193% (2.26→6.63), KUST +58%, INLF +50% — all with only the stateless ignition lane alive; first `consolidating` row of the DAY: 10:37:10 | #81 | 2efeb7d session_cache survives rescans + 240s budget | CLOSED pending Thu acceptance |
| BW-4 | 9:44–10:33 | ~49 (ZCMD) | **Recorder starvation continued past 9:41 on halt-chain verticals** — ZCMD~10s gaps 9:46→10:16, 10:17→10:27, 10:28→10:33; ADVB gaps 9:31→9:57, 10:13→10:20 | ZCMD, ADVB | ZCMD 2.8→6.63 vertical essentially untaped; ADVB push to 13.17 fell inside its 10:13→10:20 gap (rocket armed 10:14, curl never confirmable) | #68-adjacent, possibly the "429 storm" [UNVERIFIED — api_429=0 in all archive health rows; recorder logs gone] | #68 + #86 partially; not specifically tested against halt-chain load | **OPEN as canary** — watch ZCMD-class tape continuity Thu |
| BW-5 | all day (04:00–close) | — | **Curl-lane feed wiring** — zone-flip/reclaim machines received zero tape ever (arm-wait `continue` starvation) | 21 names, 31 replay fires (6 in 9:30–11:00) | INLF 10:08 maxR 7.0, SNTG 9:42 maxR 5.2, INM 9:01 maxR 2.3, ADVB 07:08 maxR 24.3 | #89 | 7a72c83 | CLOSED pending Fri acceptance (first live/shadow row) |
| BW-6 | forensic | — | **Bars-store eviction** — 11 of 22 boot names return `{"error":"not found"}` from /api/bars, incl. two names we TRADED | SKYQ, YHC, CRIS, WCT, MNDR, CHNR, JAGX, ACCS, LITB, VIDA (+OLOX) | can't reconstruct our own SKYQ −$25.54 / YHC −$54.76 entries from our own bars | **NEW** | none | **OPEN — new defect candidate** (grading blindness, violates Statistician's ledger law) |

**Compound view on the day's #1 mover:** ZCMD was blind in at least one dimension (no lane / no tape / no state) for ~107 of the 110 minutes between 8:43 and 10:33. It ran +193% in that span and finished +736% high-vs-prev-close (1.43→11.96 @11:28).

---

## 3. First-hour capture score (top-5 movers by 9:30-open → 10:30-window-high)

Caveat: ranked from the 18 tickers with retrievable bars; the 11 evicted names (BW-6) can't be ranked, but trade records bound SKYQ (post-entry high = entry) and YHC (+2.3%) well below this table.

| # | Ticker | 9:30 open → fh high | When | Bot action | Verdict |
|---|---|---|---|---|---|
| 1 | ZCMD | 2.26 → 6.63 | **+193.4%** @10:27 | rocket_armed 10:28 @6.63 (at the top, after the move); 9 arms total, 1 trigger 11:49 @8.85 momentum-rejected post-peak; **0 entries** | ARMED-NEVER-ENTERED (amnesia + tape-dark + detector arms retrospectively) |
| 2 | ADVB | 8.32 → 13.17 | **+58.3%** @10:19 | rocket_armed 10:14 @11.87, no trigger (tape gap 10:13→10:20); entered 14:46 ma_pullback +$31.17 (day high 18.26) | MISSED THE FIRST-HOUR LEG |
| 3 | KUST | 1.17 → 1.85 | **+58.1%** @10:00 | ignition trigger 9:36 @1.23 → chart-gate block (level 1.27); level broke minutes later, ran +46% past it, **no re-trigger** | BLOCKED-THEN-FORGOTTEN |
| 4 | INLF | 3.2301 → 4.8599 | **+50.5%** @10:23 | ignition trigger 9:43 @3.66 → blocked (level 4.75); reclaim lane replay-fires 9:44 + 10:08 (maxR 7.02) never reached the machine (#89) | LANE WIRED DEAD |
| 5 | AEHL | 0.7133 → 0.99 | **+38.8%** @9:47 | ignition trigger 9:39 @0.7966 → blocked (Kev level 1.00; high 0.99 never crossed) | CORRECT SKIP (Kev's own plan) |

**Score: 0/5 entered.** What it did enter in the window (SKYQ, SNTG, YHC) netted −$72.04. Selection again beat capture: all 5 were on the 8:46 boot watchlist. One of the five blocks (AEHL) was doctrine-correct; the other four are defect-shaped.

---

## 4. Ranked remaining gaps AFTER the overnight fixes (#68/#81/#84/#86/#89 live)

1. **Pre-8:45 structural blindness + watchlist-seeding latency (BW-0).** LABT's entire +343% happened 8:00–8:27; its first 10s bar is 8:48:50. ADVB's maxR-24.3 reclaim fired 07:08 in replay — premarket reclaims are the monster class (premarket 36% reach-1R, n=14, vs post-11 18%, n=11). No shipped fix touches boot time or premarket subscription. Needs: earlier boot (04:00-ish recorder at minimum), premarket news-gapper seeding, and a premarket reclaim lane (now mechanically possible post-7a72c83).
2. **Rocket detector arms after the move / no halt-chain entry grammar.** ZCMD armed at 6.63 (leg already +193%) and its only trigger came 21 min after the 11.96 top, then momentum-rejected. Amnesia (#81) explains the re-arms, not the late first arm. Halt-chain verticals (ZCMD's flat-bar halt windows) still have no grammar — Rocket Rider's gate-inversion question stands.
3. **Trigger-once-then-forget after chart-gate blocks.** KUST blocked at 1.23 below level 1.27 at 9:36; level broke and price ran to 1.85 with no re-trigger row. Whether #81's cache-survival also fixes gate-block re-evaluation cadence is untested — needs a Thu canary (a gate-blocked name whose level later breaks must re-trigger).
4. **Open-drive / first-3-minutes lane.** First trigger row of the day is 9:33:20; first ORB-machine row of the day is 10:37. AEHL bottomed 0.6176 in the blind 9:15–9:41 stretch and topped +38.8% by 9:47 — an open-native class nothing covers even with all fixes live. RS-at-open #69 is still pass-1 MIXED (7/21 top-3 +624% vs 7/20 FAIL).
5. **Recorder capacity under halt-chain load past the downshift boundary (BW-4).** ZCMD tape-dark to 10:33, ADVB gap exactly under its rocket-arm. Reserve-first (#68) fixes the 9:15 boundary; nothing proves it fixes mid-morning starvation on 150%-vel names. Canary: Thu ZCMD-class 10s continuity.
6. **Bars-store eviction (BW-6, NEW).** 11/22 boot names — including 2 of our 6 trades — are unretrievable same-week. Forensics and capture-grading run on our own archive; eviction makes tomorrow's autopsy blind. Cheap fix candidate: pin traded + boot-watchlist names in the bars store.
7. **[Downgraded] 429 storm.** Not visible anywhere in the archive (api_429=0 in all `_exec_health` rows). Either it lived purely in the dead Railway logs or it was recorder-side. Don't spend on it until it shows a number. [UNVERIFIED]

---

## 5. Kev-LABT grade

**What Kev actually did (transcripts):**
- Wed-night picks for 7/22 (zlCFR8H_XdY): SLGB / OMH / AEHL. **No LABT.**
- Wed premarket update (VEQdAW1Bp5E): drops SLGB, keeps OMH (>0.65) + AEHL (>1.00, main plan >1.39); names the leading gappers as "INM up 95%, INLF up 74%". **Still no LABT** — the update was evidently cut before/early in LABT's 8:00–8:27 vertical.
- Thu-night video (AnS1I-BEHNE, recorded 7/22 evening): LABT is pick #1 as **day-2** — "massive mover in pre-market this morning… ran over 300%… best news we saw out of anything" — plan: strength over 4.20, higher lows over VWAP/3.60, targets 6.50/7.50. **No claim he traded the 7/22 premarket run itself.** DAILY_SCORECARD.md has no 7/22 row yet (last entry 7/14) — no independent trade log either. [Kev-traded-LABT-premarket: UNVERIFIED, and his own transcript implies he didn't.]
- What Kev DID catch live on 7/22: **ZCMD** — "squeeze over 700% on ZCMD and I caught it at the bottom in this morning's live trading stream."

**Grade of our LABT miss: C+, structural not behavioral — and Kev missed it live too.**
- The run was 100% premarket (core move 8:00→8:27, +310% in 27 min; day high 7.72 was the 8:27 PREMARKET print). Bot boots 8:45. Nobody's rules fired: not Kev's night list, not his morning update, not our scanner. This is a shared blind window, not a bot-specific defect.
- RTH LABT was a fade (open 6.50 → 3.93 by 10:30, closed ~3.35): the bot's zero RTH trades on LABT were **correct**. Zero dollars were left on the table after 9:30.
- Where Kev's process beats ours: his pipeline still converted the miss into a structured day-2 plan (4.20 break / 3.60 higher-low / 6.50–7.50 targets) the same evening. Our equivalent (kev_watchlist sweep) held AEHL/OMH/SLGB on 7/22 and must show LABT+PN+INLF for 7/23 — that's the Thursday check.
- The sharper 7/22 grade is **ZCMD, not LABT**: Kev entered at the bottom of a +700% name that was on our boot watchlist from 8:46, armed our rocket detector 9 times, and produced zero entries. LABT we couldn't see; ZCMD we saw and dropped — BW-3/BW-4 made it undecidable, and the detector armed only after the first +193% leg.

---

## Standing acceptance checks this ledger creates (Thu 7/23)
1. First live/shadow reclaim row appears (#89 / BW-5). 2. LABT/top-mover 10s tape continuous through 9:15–9:45 (#68 / BW-2). 3. `consolidating`/`watching` rows exist BEFORE 10:00 (#81 / BW-3). 4. A gate-blocked name whose level later breaks re-triggers (gap 3). 5. ZCMD-class halt-chain name keeps 10s continuity mid-morning (BW-4). 6. kev_watchlist for 7/23 contains LABT/PN/INLF. 7. Bars retrievable for every traded name at EOD (BW-6).
