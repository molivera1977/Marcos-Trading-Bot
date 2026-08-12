
## 8/2 (Sat) — FLOOR WAS OFF IN PRODUCTION 7/29–7/31; FIXED
- **Finding:** Railway env `MIN_STOP_PCT=0` overrode the code floor. Gate fired 11× on 7/28, then ZERO on 7/29–7/31 (decisions archives). MGRX 7/31 07:46 (3.09% stop, pure-function verdict = reject under 6%) traded because the floor was off — NOT a premarket hole. Who/when set to 0: unknown (no var history; window = 7/28 close → 7/29 open, the emergency morning).
- **Contaminates:** the 5v6 grade's Wed–Fri cells (trades read as exemptions were floor-off) and the claim "6% all week" — true only Mon–Tue.
- **Fix (8/2 22:27 ET):** book flat verified in-turn (`/api/open_trades` = []), `MIN_STOP_PCT=4` set, redeploy `6d91bcd9` SUCCESS on commit `6455ab4` = local HEAD (Friday ship-set confirmed deployed; earlier SKIPPED rows were superseded builds). Banner check pending Monday 03:55 wake.
- **Intrabar trace (same session):** `INTRABAR_STOP=1` is intentional (code comment :325, Marcos 3×; blow-through $441.54 vs shakeout ≈$105 at 10s). BUT `place_stop_order` (:6917) still returns None — no resting broker stop; benign in DRY_RUN, **go-live blocker** (retry STOP_LOSS enum spelling). Memory updated.

## 8/2 (Sat) — RESTING BROKER STOP: SOLVED (go-live blocker cleared at the code level)
- **Probe (preview_order, places nothing):** `order_type=STOP_LOSS` + `stop_price` → HTTP 200 with cost estimate. `aux_price` → 417 PARAM_ERR ("invalid stop_price"). `STP` → 417 ("invalid order_type"). June failed on BOTH spelling and field name at once; "Webull rejects stop orders" docstring refuted by the server.
- **Shipped `4a8d727`:** `_place_order` maps stop→`stop_price`; `place_stop_order` un-stubbed (SELL STOP_LOSS via the working order_v2 path); `RESTING_STOP` env kill switch (default 1); inert under DRY_RUN. Rig: test_resting_stop.py 7 pins + full sweep green by exit code.
- **NOT yet proven:** an actual placed-and-cancelled stop on the live account (preview ≠ placement), and the double-sell race (exchange stop fills while software stop also market-sells) — both are go-live-week checklist items, to exercise on a $5 position before 8/18.

## 8/3 — TWO-TIER SIZING (half-risk on fail-open ignorance): HOLD (all 3 frozen rules failed)
- Registered rules R1/R2/R3 in `data/killtests/twotier_sizing_20260803.py`; graded as written.
- Ignorance cohort BEAT informed on both splits (TRAIN −$8.81 vs −$14.74; TEST +$3.53 vs −$3.18); two-tier delta +$88.07 TRAIN / −$15.89 TEST.
- Known cohort flaw (noted post-grade, verdict unchanged): "informed" included pre-gate sub-1R trades the runway gate now blocks — clean re-run REGISTERED for 8/8 on post-gate trades only (informed = stack-passers; ignorance = `ungated_entry` converts), same rules.
- Watch-item (no claim): ignorance hidden_entry −$25.20/t vs ignorance vwap_reclaim +$5.50/t.
- Runway-band + >=4R autopsy same session (observational): <1R −$492/19t (gate now blocks); 1-3R +$280/14t; >=4R losses = AMIX 7/29 pile-up (−$149.96/4t, one name) + floor-off artifacts; ratio-inflation trap (tiny stop inflates rw) noted for any future runway-magnitude use.

## 8/3 evening — HIDDEN CAP MERIT-EXCEPTION: REFUTED 0-for-24 (cap VALIDATED)
- Registered rule (mean>=+$5, n>=10) in `data/killtests/hidden_cap_merit_20260803.py`; cohort = capped fires w/ ballpark=in + gates-pass + empty slot, 7/28-8/3.
- Result: n=24, $-543.04, mean $-22.63, WIN RATE 0% at optimistic pricing (perfect stop fills). TEST slice (8/3): 2 fires, both stopped.
- 20/24 = FCUV Friday (Kev's do-not-trade day) — capped fires are the shakeout TAIL of names that already ran, not late-arriving quality; the cap accidentally enforced the veto on a veto-exempt lane.
- HIDDEN_CAP_MERIT does NOT ship. Cap stays at 3/day. Marcos's question answered with dollars: the cap saved ~$543 this week on exactly the cohort suspected of being "ignored quality."
- FUSE 8/3 miss remains real but its fix is map freshness (#25), not the cap.

## 8/3 late — ZONE STAMP + TAPE PRE-BREAK GATE SHIPPED (Marcos live-ship override)
- Dead-zone kill-test (deadzone_20260803.py): raw tape-pre-break met frozen bar (n=12 −$143.89); era-decontamination (same flaw class as two-tier cohorts) left n=7 −$161.52 mean −$23.07 — ONE SHORT of n>=8. Marcos: "ship it live tonight and shadow the alternative." Recorded as his override, precedent = 6% floor.
- Gate: tape lanes only (hidden/reclaim/zone_flip); blocks entry BELOW a break the tape has NEVER touched today; retest (any depth) passes; ignition/chart excluded (their pre-break POSITIVE: +$67/+$126 — CYCU curl, GCTK, LFS); fail-open on no-map/unknown-day-high; env TAPE_PREBREAK_GATE.
- Zone stamp on EVERY conversion (entry_zone row: zone/break/lastT/day-high/retest-depth) — "I refuse to let trades go forth blind."
- Also found: in_range −$651 decomposes to −$432 already-blocked (pre-gate era) + −$154 Tuesday 7/29 + hidden-in-mid-range residual (−$163/6t, Friday question). Zone-gate conclusions beyond tape-pre-break NOT supported this week.
- Friday 8/8 grades: prebreak_reject counterfactuals, retest-depth curve, hidden-mid-range, ceiling/wall runway (#27).

## 8/3 late-2 — CHART CEILING GATE SHIPPED (Marcos override #2)
- Cohort n=5 -$50.75 mean -$10.15 (under frozen n>=8); Marcos: "ship the chart lane block, shadow the alternative" after the FUSE -$64 pair. Override recorded, same structure as the prebreak ship.
- Gate: CHART lanes only (flat_top/ma_pullback/orb/ema_bounce/dip_rip) blocked ABOVE the map's last target; SELF-RELEASING — a fresh re-read with higher targets returns the name to in_range (this is #28's stand-down in its narrow form, shipped via the zone mechanism). Tape lanes untouched (blue-sky bimodal, ZYBT class). ceiling_reject full tickets = daily counterfactual. Env CHART_CEILING_GATE.
- TODAY REPLAYED under both overrides: blocks FUSE flat_top -$30.66 + ma_pullback -$33.53 (saves $64.19), also blocks FUSE dip_rip +$16.49 and PRZO x2 +$8.14 (costs $24.63) -> today lands ~-$0.76 vs actual -$40.32.
- Friday 8/8 grades both overrides on their reject counterfactuals; either flips off by env if the shadows convict them.

## 8/4 ~01:30 — PREBREAK GATE OFF + RETEST SHALLOW-ZONE GATE ON (Marcos override #3, final spec)
- SIP-complete zone reclassification (zone_reclass_sip_20260803.py, audit JSON persisted, independently rerun to verify): tape pre-break n=16 +$0.12/t 62% win (earlier -$23/7t was a missing-bars artifact — winners MGRX +23.31/SPRC/FCUV sat unclassifiable); ALL pre-break +$14.31/28t vs ALL retest -$9.95/24t. Named trace: MGRX 7/31 07:46 e=0.56 brk=0.70 dayhi 0.6918 -> PRE_BREAK -> gate would block -> +$23.31. Pre-registered failure condition met before first live fire -> TAPE_PREBREAK_GATE=0 (env, flat book, market closed).
- Depth cut of the 24 retests INVERTED the shallow-good theory: <=5% deep = -$13.66/t 31% win (chart lanes buying just under the sell wall); 5-12% -$2.33; >12% mixed w/ curls (CYCU +29.89, 67% win). "Battle zone around the level" hypothesis registered for Friday.
- SHIPPED: RETEST_BAND_GATE — retests <5% under a fired break blocked (Marcos: "only block the 1,2,3,4% levels to make it a meaningful retest"), 5%+ allowed (curl class kept), FINE DEPTH BANDS (<1,1-2,2-3,3-4,4-5,5-8,8-12,>12) stamped on EVERY retest + reject ("keep tabs and data on all the bands"); full-ticket shallow shadows; all lanes; env RETEST_BAND_GATE/LO/HI. n=13 basis = override, graded Friday vs its own shadows.
- Kev reconciliation on record: tape pre-break entries obey "no break no trade" at 10s scale (micro-breaks); shallow "retests" under a fired break = entering the unfinished battle zone, not Kev's shallow-hold retest. The daily-level binary was the wrong ruler, not the bible.

## 8/4 ~03:00 — #29 MIGRATION SHIPPED (laptop out of the trading day)
- CAPTURE: discovery now EXTERNAL (Alpaca most-actives screener + our scanner Move% list, 3-min TTL) — the circular archived-volume ranking (EZRA joined 12:35 root cause) removed. Join-backfill now PERSISTS the full SIP 1-min day history as {SYM}~ALP1M (was fetched-and-discarded after VWAP seeding); reader charts + bot day-high checks fall back to ~ALP1M.
- HEALTH: bot-side 09:05 ET thread writes a durable preopen_health decision row (kev/vision map counts, screams on stale sheet). Replaces dead laptop task.
- KEV SWEEP: server-side on the dashboard service (kev_sweep_server.py): 20:06 + 09:02 ET weekdays, retry-until-clean (max 5 — Marcos's multi-pass rule), transcripts to /data/kev/, TOP-3 parsed by Claude API, merge-only POST src=kev, kev_sweep decision row every run, fail-soft. PROXY_*/ANTHROPIC_API_KEY set on dashboard env.
- Laptop scheduled tasks kev-sweep-night/morning, bot-preopen-health-check, postah-bars-backfill DISABLED deliberately (all silently dead since 7/26-27) with RETIRED notes.
- CAVEAT (honest): the server sweep + external discovery + backfill are rig-pinned (section 17) but NOT yet exercised end-to-end live — first real runs: capture discovery within minutes of deploy, morning sweep 09:02, night sweep 20:06 today. I will verify each at its first firing; manual sweep remains the fallback until each proves itself once.

## 8/4 08:32 — ENTRY_OPEN_ET 04:00 -> 07:00 (Marcos's call, aligned to Kev's 7am stream start)
- Evidence: 4-6am cohort n=6 −$87.15 17% win since feed-fix (incl. today's DXST −$39.68 stale-fire/stale-swap defect, 4-sec −1.38R); 5-6am AND 6-7am hours have ZERO trades ever — no measured upside surrendered.
- 04:00-06:59 fires now SHADOW with stops (auto-counterfactual, Friday-gradeable); slots not consumed; RTH mathematically untouched (all 6 code usages audited: bracketed <09:30 or >= comparisons).
- Book flat-verified in-turn; env-only; restart ~58 min pre-open.
- TONIGHT (registered): DXST price-path surgery — swap-proof drift guard (chosen-vs-OTHER-source), PRE fires >60s re-verify vs live 10s store, session-split fire-age ceiling. Fixtures: DXST 04:14 + IPW 04:09 8/4. RTH fire-age tail note: converts up to 2465s old — Friday question.

## 2026-08-04 EVENING BATCH (#31 + #27) — shipped 18:2x ET, flat book verified in-turn, rigs ALL GREEN (exit 0)
- OFFICIAL DAY (new convention, Marcos): RTH +$385.78 (6 trades, era-best day) · PRE −$45.73 reported separately. AMIX +$291.41 = era-best trade (6 halts, 3:45 time stop out at ~20.70, above the ratchet's would-be 20.50 floor).
- CLASS-AWARE RUNWAY LIVE (Marcos override + kill-test runway_graded_20260804): RUNWAY_MIN_RR_RUNG=0.5 / RUNWAY_MIN_RR_MAJOR=1.0; MAJOR=break/next_supply/whole-half-dollar. Evidence: rungs>=0.5R +$91.01 plateau; majors all-taken −$148.67; flat T=0.3 (+$117.65) stamped for Friday head-to-head via continuous road_rr+class+band on EVERY pass & reject (runway_pass rows new).
- RUNG RATCHET LIVE (override #4, level_exits H replay 92% wins/ties worst $5.24): runner floor = highest 1-min-close-cleared rung; complements health fold; RUNG_RATCHET=0 kills.
- READER: UTC->ET rebuild fix (the 8/4 noon-freeze that refused 3 AMIX re-reads — rig-pinned); held-name UNCAPPED re-reads; confidence anchors both prompts (416 reads/0 HIGH); anchor_check log-only (maps-describe law).
- DXST SURGERY: swap needs cross-source agreement (SWAP_XSRC_MAX_PCT=3) + PRE fire-age ceiling CURL_FIRE_MAX_AGE_PRE=60.
- SWEEP SERVER: TOP-3 posts FIRST (8/4 finished 09:34 — after bell); _symbol_real Alpaca guard (EASY/FUS class); EASY/FUS purged via new tickers_remove (explicit-only; merge-only stands).
- DASHBOARD: reject strip -> archive w/ comma-status (was 6/36 rows via 4k cap); +ceiling gate; breakside shows break_level (was $None); tale shows rung/major road class.
- ZEO AUTOPSY CLOSED: NO floor defect — 95,230-sh flush 0.568->0.5211 in ONE 10s bucket; BE floor never printable. −$8.18 = honest gap-through slippage. (Marcos called the loser live.)
- TIMEOUT KILL-TEST (moved-vs-stalled, M×N grid, 49 trades): best AMIX-safe cell +$11.81 total — immaterial, PARKED (trail already handles most dead money).
- Boot row with new knobs appears at Wed 03:55 ET session start (container verified up 18:2x).

## 2026-08-05 (Wed) — LEADER DAY: crowns, 0.4 rung, back-side gate
- OFFICIAL: RTH −$133.10 (13 trades, 23% WR) · PRE $0 (first clean premarket of the era). Two-day new-stack net +$252.68.
- LEADER AMMO shipped 11:54 ET intraday (Marcos order after YXT 6→16 & JLHL 7.66→15 ran on spent ammo). Counterfactual leader_ammo 27 starved setups = +$634.96; formula-v2 sticky backlabel armed 26/27 (+$624.96). DAY-ONE live: only 2 true relief tickets, −$10.44. CROWN-FROM-OPEN counterfactual for 8/5 alone ≈ +$307 day (+$440 swing), dominated by YXT 10:33 hidden +$221 and JLHL 9:41 reclaim +$178; JDZG's −$54.93 cluster correctly EXCLUDED by the 40% gain floor.
- Crowns live: YXT 12:07:26 (first ever), BJDX 12:27, INLF/ASTC/VRM later. Rehydrate (leader_armed + halt_suspect rows) proven on the 12:45 restart: "2 leaders restored, 63 flags re-armed".
- RUNWAY_MIN_RR_RUNG 0.5→0.4 (Marcos order 12:45; sweep had 0.4=+$99 vs 0.5=+$57 pre-registered; the 12:33 YXT 0.44R reject was the live specimen). Replayed honestly: that trade LOSES $29.83 (fell to 11.55 first, THEN ran to 32.14).
- BACKSIDE_GATE shipped post-close (kill-test backside_20260805: 15-30% below a ≥20-min-stale high = −$147 era bleed at −$8/trade mean, ~no in-band winners; >30% flush cohort n=4 held up → band-block 15-30, stale≥20m, dip_rip exempt, BACKSIDE_GATE=0 kills; dd/stale stamped on every candidate + trade). Frozen verdict technically NOT MET (X=30 flips) — shipped on Marcos's call with band edges held loosely for Friday.
- BIGGEST OPEN HOLE, named with specimens: the VERTICAL REGIME. YXT's 12:51:58 hidden fire at 15.65 (stop 14.89, 2.03R road, chart+runway PASSED) was breakside-rejected at +0.97% over the 15.50 break — then the name ran to 32.14 with ZERO detector fires after 13:30 (halt-ladder tape defeats fire-age/patterns). Two Friday questions: breakside tolerance on crowned reclaims; dip_rip conversion rate (armed repeatedly, traded once).
- Also: crowned-name reader priority shipped (60s probe + uncapped re-reads, leader set from durable rows); PRE fire-age ceiling 60→90s (option B); first-ever HIGH confidence read (JLHL v4 SKIP/HIGH — anchors working, used on a clean NO); 5 morning defects fixed pre-10am (stale-image restart, AMIX $1.40 sweep cross-wire + keyless guards, YXT prior-close false-reject, HYM ghost, reader HYM stall).
- Parked by their own tests today: stalled-name timeout (+$11.81 immaterial), wall piece (−$8.38 at 1R, end-of-day-map caveat), stop-confirm sweep (touch stands; patience pays ONLY on monsters — leader-regime thread).

## 2026-08-05 LATE BATCH (the "Thursday set", shipped Wed ~21:30 — Thursday changes NOTHING)
- HALT-AWARE CLOCKS: halted minutes (completed >120s bar gaps, tracked per-symbol) no longer count against fire-age (all 4 detector sites) or the dip_rip resumption window. Evidence: YXT watch expired MID-HALT twice; mid-ladder fire killed at "240.6s" with 200+ halted. Unit-pinned (400s gap -> 390s credit).
- BATCH READ VALIDATION vs LIVE 10s price (YXT +239% false-reject class killed).
- AMMO-LEDGER REHYDRATE: spent curl/hidden tickets rebuilt from today's trades on boot (restart amnesty closed). AH label session-aware on Kev-pinned rows.
- EXACT-PRICE ENFORCEMENT (Marcos: "actual numbers from the chart read"): anchor_check ENFORCED at all read paths, round-number exemption DELETED, intraday candidate generator built (swing highs/lows/VWAP/day-H-L — 49 exact prices on the YXT test), both prompts mandate verbatim candidates. Round-number CLASSIFIER untouched by Marcos's ruling — Friday's level-respect test votes on the whole question at once.
- RIDE PROTOCOL STUDY (16 real monster entries): ALL capture concentrates in the one true ride (AMIX 8/4): touch-trail +$24 vs health-fold +$483 vs map-ratchet +$533 (P3 carries end-of-day-map lookahead; P2 clean). VERDICT: the live exits (health fold + HB ratchet) ARE the answer; touch-trail correctly not the runner protocol. Remaining edge: the 15:45 time stop exited into a down-halt (~$190 vs sim) — weekend design; and BREAKSIDE_MAX_PCT=0.0 (zero tolerance) is the precise Friday question from the 12:51 YXT 0.97% rejection.
- DIP_RIP STRANGLED-FIRES COUNTERFACTUAL: 27 killed fires replay to −$210.76 — the gates were RIGHT; unstrangling REFUTED. (Skepticism-needs-verification win: the check ran before the "fix".)
- All 3 services redeployed + containers confirmed; boot row with full stack (backside included) stamps Thu 03:55.

## 2026-08-05 night — PRE-SCALE STOP KILL TEST (hold-planned-stop vs live scale-bar trail): REFUTED
- Question: does holding the planned stop until the +1R scale (instead of the 10s scale-bar trail) capture the monsters the hidden lane got shaken out of (INLF 10:20 7s hold → +54%; YXT 13:09/13:12/13:22 → +126-139%)?
- Cohort: all 32 closed hidden_entry trades since 7/24 with 10s coverage (25 crowned by day_gain>=40 proxy). Engine: identical post-scale arms; only pre-scale stop differs. data/killtests/prescale_stop_20260805.py (+rows json).
- VERDICT: NOT MET, both arms. A(live) -$30.04 | B_all -$88.49 (delta -$58.45) | B_crown -$30.23 (delta -$0.19, wins 22/32, worst degradation $38.42 > $35 cap).
- The frozen WRONG-WHEN fired: hidden names routinely flush THROUGH the full planned stop before running — today's YXT/INLF specimens stop out at the full planned stop in arm B too (deeper loss, same miss). The scale-bar trail is protection, not the hole.
- Reframe: capturing those legs is a RE-ENTRY problem (the lane did re-fire YXT 3x via leader slots; all pre-run) — not a stop-holding problem. Routes to the weekend ride/re-entry design; nothing ships from this test.

## 2026-08-05 night — CROWN RE-ENTRY RAIL: DOLLARS NOT COUNT (SHIPPED, Marcos's order)
- Root cause of the YXT afternoon lockout: reentry_givenup at 13:23:57 (attempts=4, consec_loss=3) — the count-of-3 rail banned the day's strongest crown over $14.37 of shakeouts; YXT then ran $13.17 -> $32.14 (+144%) with the bot banned from the name.
- Era scan (all 5 consec-loss lockouts 7/24-8/5): the 4 legitimate bans had bled $93-$124; YXT $14.37. Dollar rail separates 5-for-5. All five names were crown-class (day_gain 74-447% at entry) — so scoping the new rail to CROWNS changes no historical outcome and leaves ordinary names on the tight count leash.
- SHIPPED: _reentry_rail_giveup() — crowned names ban on consecutive-loss DOLLARS >= REENTRY_CROWN_LOSS_DOLLARS ($75 = 2.5 risk units; Marcos: "a risk level I'm willing to live with... these crown names are the whales we are living to find and milk"). Env-tunable; 0 = kill switch to count. Uncrowned unchanged. Topping-tail giveup untouched. Rows now stamp consec_loss_usd + crowned; boot row stamps reentry_crown_usd.
- Rig: 6 new pins ALL GREEN (YXT $14.37 no-ban / $76 ban / win-resets / uncrowned count intact / stamps). Flat book verified in-turn (open_trades [] @ 23:50 ET). Deployed.
- Honest caveats stamped: n=5, $75 sits in a wide ($15-$93) separating gap — Friday re-grades from the new consec_loss_usd stamps; capture of the missed leg is a ceiling, not a promise (re-fire after 13:24 unproven — the name went dark post-ban).
- 8/6 00:05 Marcos on the reset-vs-net question: "I do kind of like the net dollars way but I'm willing to try the system as it is." → RESET version live; NET-DOLLARS parked as a liked alternative. The consec_loss_usd stamps + pnl rows are sufficient to replay both variants head-to-head — add to the Friday table. Deploy be28b8f9 SUCCESS 23:51 ET; crown_usd=75 boot-row confirmation due at the 03:55 pre-open stamp.
- 8/6 ~00:45 CROWN GAIN REFERENCE — DECIDED: keep PRIOR-CLOSE (matches the scanner's Move % column; Marcos: "if it matches the Move % column then that's fine with me"). The premarket-open alternative + its kill-test numbers (old-only crown class 22 trades -$271.90 mean -$12.36; new-only class n=0 unmeasured; data/killtests/crown_gain_ref_20260806.py) stay ON THE FRIDAY TABLE as evidence, not a pending change. Day-two names (YXT 8/6 class) remain crownable only via the full +40%-vs-prior-close bar by design.

## 2026-08-06 midday — THE DAY THE OFFENSE SHOWED UP (+$54.97 RTH as of ~12:15) + 3-change batch
- WYHG +$91.92 (hidden 16.60 -> 22.22 trail; mapped by the 10:39 reader fix, full gates, partials banked) — biggest single capture of the era, on a +400% halt-ladder whale. CELZ +$59.65 via RUNG RATCHET at Kev's 1.50 floor (Monday's ratchet + morning's relayed update). PRE separate: WYHG +$22.39.
- Morning cost: sym=t crash-loop 9:30-9:39 (MY defect; execution-proof law + three-rings law written to permanent memory in Marcos's words), PAVS/MGRX/first-ENSC stops -$70.68, all three exits beat holding (autopsy in-ledger).
- BATCH STAGED (deploy on double-checked flat book; both rigs GREEN; all three-ring-executed):
  1. HIDDEN_EXT_CROWN_BYPASS=1 — crowns bypass the 3-10% band. Pre-registered failure clause FIRED: refused fires forward +$561.58/32 (crown-split: crowns +$641.87/26, non-crown negative). July flat-band protection kept for ordinary names. Kill=0.
  2. MAPLESS_BLOCK=1 — tape lanes fail CLOSED on names with zero levels (FVN/SUGP ungated_entry class). Partial maps trade. Kill=0. mapless_reject rows keep the refused cohort gradeable.
  3. AMBIENT_DVOL_MULT=15.0 — median $vol of prior 10 completed 1-min bars must cover 15x the position cap (execution-safety floor; kill test showed paper P&L can't see slippage — data/killtests/ambient_liquidity_20260806.py; 15x blocks both 8/6 specimens at zero winner cost vs 10x; era cohort under floor 25 trades -$66.95). Applies to ALL lanes incl. ignition (quiet-base carve-out had confused quiet with illiquid). Kill=0. HOMEGROWN 15x -> translation registry; Friday re-grades from stamps.
- Also live since ~10:39: reader TODAY_INTRADAY anchors + explicit halt ladders on maps (Marcos: "why aren't the halt gaps explicitly stated on the maps???") — proven by WYHG v2/v3 reads -> the +$91.92 entry.
- Friday adds: tape-fires-vs-SKIP-reads grade (AZI specimen), crown latency + cap economics (PN 10:44), LEADER_GAIN_MIN bar study, ambient floor re-grade, ignition fill-quality (#12).
- 8/6 ~12:45 STANDING ORDER for the EOD scorecard (Marcos: "I want to see what our end of day P+L would be if you didn't fuck this trade up"): report BOTH lines — actual day P&L, and the counterfactual with the KILLED WYHG trade (12:28:29 entry $17.48, 23 shares, force-closed $18.26 +$23.24 by the af52-adjacent restart at 12:31:20) replayed un-killed on the real 10s tape through its own exit scaffold (tiers 33/55/75%-style rungs as stamped, stop as stamped, halt-aware) to its natural exit or the close. The gap between the two lines = the price of the deploy-race, mine.
- 8/6 ~15:45 BLUE-SKY DOCTRINE SETTLED (Marcos): (1) TRADING blue sky = OFF, his leeriness is the default — data (#28 era grade) must beat it, never the reverse. (2) "add it": blue-sky reads POST as SKIP-with-comeback-map (flagged blue_sky; the high = target, pullback shelf = hold, reclaim = confirm) — the validator stops discarding honest summit maps. Entries at the summit stay impossible by RUNWAY ARITHMETIC (~0 road), and self-activate on pullback when road to the old high opens. "Map the summit as the target, not the entry." Ships in tonight's freshest-gates build, kill-switched.
- TONIGHT'S WINDOW (final, in order, each three-ringed): 1) deploy-freeze protocol 2) freshest-structure gates + blue-sky SKIP posting 3) detector rehydrate 4) retest entry (1%) 5) audio transcription.

## 2026-08-06 night — THE FIVE BUILDS (4 shipped, 1 blocked on an STT decision)
ALL under the three-rings law (each changed path EXECUTED, both rig suites green after every change; full-suite pins added per build):
1. DEPLOY-FREEZE PROTOCOL (SHIPPED + first real run): dashboard /api/pause_entries (authed) + bot client (10s cache, FAIL-OPEN on outage) + entry refusal w/ slot refund + session-init auto-clear. Kill: PAUSE_ENTRIES_RESPECT=0. First live run: flag set 19:40:42 -> verified -> flat verified -> bot built with entries frozen the whole window (the 12:28 WYHG kill class now impossible). LEARNED: auto-clear fires at SESSION INIT (03:5x), not container start — flag manually cleared 20:54 post-deploy; 03:55 clear becomes a verifiable no-op. Ring1: live stub server, 4 states.
2. FRESHEST-STRUCTURE GATES + BLUE-SKY COMEBACK MAPS (SHIPPED): server stamps _ts on every levels write (kev slot never clobbered — vision_shadow was already the side slot); reader now PROBES kev-src names (CELZ $1.05 freeze class dead); _freshest_rec() picks newest-by-timestamp for breakside/runway/zone-ceiling (3 sites); blue-sky exhausted-rejects now POST as SKIP+blue_sky comeback maps ("map the summit as the target, not the entry") — entries at summit stay blocked by runway arithmetic. Kills: NEWCOMER_BLUESKY=0; freshest is fail-safe to kev record. Ring1: merge/freshest/branch all executed.
3. DETECTOR REHYDRATE (SHIPPED): REHYDRATE_BARS=240 deep backfill on each name's FIRST detector pass (reclaim/hidden + ignition; zoneflip already 720) — anchors mature in-pass (real hidden_entry_step executed: 100-bar single pass -> nbars=100, zero immature). The ENSC 9:40 restart-blindness class dead. Kill: REHYDRATE_BARS=90.
4. RETEST ENTRY (SHIPPED): breakout lanes (flat_top/ignition/orb) wait up to 900s for fire_px*(1-1.0%) touch; enter AT the level; expiry -> retest_expired + slot refund; deploy-freeze cancels pending waits. Evidence: break-print cohort -$395.09/56 era trades vs retest-1%% +$142 better, 12%% missed (SHIP-CANDIDATE by pre-registered rule). Kill: RETEST_ENTRY=0. Ring1: touch/expire/freeze all executed.
5. AUDIO TRANSCRIPTION (BLOCKED, honest): needs an STT credential/dependency (Whisper API ~$0.006/min or whisper.cpp on the image) — Marcos's call tomorrow; caption-lag retries + his terminal pipeline remain the interim.
Deploys: dashboard ebb6ae84 + reader 9a3aac6c + bot 3c1ff12d (SUCCESS 19:40) — bot deployed behind the freeze, flat book verified in-turn. Morning verification owed: 03:55 boot row (deploy 3c1ff12d stamps + freeze no-op clear + rehydrate/retest knobs).
- 8/6 ~21:50 5-SECOND CAPTURE SHIPPED (Marcos: "i want 5 second bars saved for tomorrow's trading day" — his WYHG 5s-vs-10s chart observation): alpaca_capture now dual-buckets every print into ~ALP5S alongside ~ALP10S (own watermark, commit-on-200, kill CAPTURE_5S=0). RECORD-ONLY — rig pin asserts no bot/reader consumer. Ring1: synthetic prints proved the payoff (a 10.5-pop + 9.8-flush pair of 5s buckets that merge into one shapeless 10s bar arrive intact). FRIDAY EVENING JOB: replay Friday's fires/trades on both feeds, count+price divergent fires, decide which detectors (if any) earn 5s eyes. Storage ~80MB/day vs the new 20GB volume (Pro plan upgraded by Marcos tonight; volume grown 5->20GB, verified 2393/20000MB).
- 8/6 ~22:0x KEV TRANSCRIPT ROOT CAUSE FOUND + FIXED (Marcos shared his terminal command): "caption lag" was mostly YOUTUBE IP-BLOCKING — his tool succeeds via Webshare rotating residential proxies. Server's transcript fetch was ALREADY proxied (PROXY_USER/PASS set + matching) but the yt-dlp LISTING step went out on Railway's datacenter IP -> challenged -> "no videos" -> read as caption lag. FIX: listing now routed through the same gateway (_proxy_url; fail-open w/o creds) + transcript fetch fail-soft for env-less local runs. RING1 LIVE: 8 videos listed + 10,932-char transcript fetched through the proxy from a fresh IP. Audio/STT build NO LONGER NEEDED (closed). Deployed (dashboard 41633202). Tonight's 20:06-23:45 night sweep = first true hands-free test on Friday's sheet.

## 8/6 late night — Friday sheet: two bugs, then a hands-free post (23:11:33)
- Kev's "TOP 3 STOCKS FRIDAY 8/7" short WAS found hands-free (85s into the night pass) but the
  sheet posted EMPTY: hallucination guard probed the LIVE assets host with PAPER keys → 401 on
  every symbol → blanket `except → drop` blanked all three real names (NMI/CLRO/DSY all active,
  verified on paper host with our keys).
- Fix 1: `_symbol_real` now probes paper-api host; drops ONLY on 404; 401/5xx/network fail OPEN.
  4 rig pins (401→open, 404→drop, active→keep, paper-host asserted); both suites exit-0 GREEN.
- Fix 2 (the fix couldn't ship): dashboard `watchPatterns` lacked kev_sweep_server.py — two
  deploys silently SKIPPED ("No changes to watched files", the 7/20 trap). File added; deploy
  SUCCESS 23:0x; fresh boot re-ran the night sweep (in-memory done-set) and POSTED at 23:11:33.
- Sheet: DSY break 8.21 / confirm 7.30 / targets 10, 15 (78% AH gapper) · NMI break 7.00 /
  confirm 6.50 off VWAP / targets 10, 13. CLRO dropped by the cross-wire guard ("levels never
  appear near its mention", AMIX-$1.40 class) — drop NOT independently verified (local transcript
  fetch 429-walled); morning 09:02 sweep re-parses.

## 8/6 23:28 — Marcos corrected the Friday sheet: NAMI (not NMI) + CLRO restored
- Marcos: "NAMI, CLRO, DSY". Captions garbled NAMI->NMI; the reality guard PASSED the wrong-but-real
  ticker (NMI = Nuveen muni, $10.80 — nothing like "110% AH Chinese gapper" at $7). NAMI (Jinxin,
  $7.06 SIP) fits Kev's $7/$6.50 plan exactly. Full transcript pulled off the volume via railway ssh.
- CLRO cross-wire drop was a FALSE DROP — his levels ARE in the transcript ("defend 1275... back to
  1650 and 20 bucks"). Autopsy WHY the guard missed them = Friday-grading item (do NOT hotfix in the
  8/7 freeze). Sheet fixed merge-only (tickers_remove/levels_remove NMI; NAMI+CLRO posted, DSY kept).
- Final sheet: NAMI 7.00/6.50 -> 10, 13 · CLRO defend 12.75 (PULLBACK watch) -> 16.50, 20 ·
  DSY 8.21/7.30 -> 10, 15. Verified by GET after POST.
- Lesson for the guard stack: "real listing" is not "right listing" — a garbled ticker can collide
  with a REAL symbol and sail through; the price-fingerprint (3x rule) missed it because NMI $10.80
  vs break 7.00 is within 3x. Candidate tightening = Friday item, kill-test first.

## 8/6 ~23:45 — APPROVED for weekend build: frame-vision check on the TOP-3 short (task #32)
- Marcos's screenshot = the specimen: giant "NAMI" on screen + drawn lines at 13.00/10.00 while
  captions said "NMI" / "the Chinese name". Current caption track re-verified tonight (no-proxy
  fetch, home IP): STILL says NMI — captions were never right; the SCREEN is Kev's ground truth.
- Design (hypothesis until kill-tested): yt-dlp short download → ffmpeg frames q3-4s → vision reads
  on-screen tickers in order + drawn levels → reconcile: screen ticker wins, lines cross-check
  levels, unreadable → caption-only flagged. Ship criteria pre-written: fixes ticker-garble class
  on archive specimens (EASY/FUS/HYM/AMIX/NAMI/CLRO) with ZERO overrides of correct parses.

## 8/7 00:2x — WEEK 8/3-8/6 REPLAYED UNDER TONIGHT'S STACK (week_under_new_stack_20260807)
ACTUAL +$223.35 (58 trades) -> WITH-STACK +$462.75 (Δ +$239.40). Per day: 8/3 −$30.83→−$9.89 ·
8/4 +$340.05→+$291.55 · 8/5 −$133.10→−$18.58 · 8/6 +$47.23→+$199.66.
Itemized: AMBIENT floor 9 blocks net +$59.48 (kills SUGP −$30.45, JDZG −$30.75; costs FUSE +$16.49).
BACKSIDE on 8/3-8/4: 9 blocks net −$29.98 on those two days (saves FUSE −$64.19; costs ADGM +$77.87
— ADGM = dip-class winner the band caught; Friday re-grade watches exactly this). RETEST-1% on 10
lane trades +$143.98, ZERO missed this week (BJDX −$32.52→+$23.90 the star). CROWN-EXT-ADD: PN
11:55 entry +$68.92 (hand-traced penny-exact; sized at $1000 cap = CONSERVATIVE, crown sizing is 3x).
NOT SCORED (listed in artifact): mapless block (no map-state history), freshest gates (CELZ ~$150
8/6 estimate separate), rehydrate/priority latency, WYHG deploy-kill (+$1.81 real-engine), blue-sky
(OFF = no delta). Caveat: gates composed in real order; sim engine = frozen killtest engine, not
the live code path (task #12 stands).

## 8/7 00:3x — BACKSIDE PRIOR-RUN EXEMPTION: REFUTED (backside_prior_run_20260807)
Marcos ordered the era re-grade after ADGM (3 in-band wins +$77.87 on 8/4). Frozen criterion:
credentialed in-band subgroup >= +$75 AND n>=8. RESULT = the OPPOSITE of the ADGM story:
- All in-band (15-30% below >=20min-stale high, RTH, non-dip_rip, era): 33 trades −$115.34.
- ALREADY-RAN-40%+ names in-band: 23 trades −$145.26 (10/23 win) — the bleed is CONCENTRATED here.
- run25 variant: 26 trades −$174.02. NOT MET both variants.
- Names that had NOT run hard: 10 trades +$29.92 (8/10) — small n, not actionable.
Autopsy of the refutation: ADGM was 3 lucky specimens of a class that era-wide is the WORST part
of the band — a big runner 20% off its high is the blow-off backside, exactly Kev's do-not-touch.
The band's cost this week (−$77.87 ADGM) is the PRICE of blocking a −$145 era class. GATE STANDS
AS-IS; no exemption ships. ADGM-style re-entries belong to dip_rip/tape lanes if anywhere.

## 8/7 00:4x — Friday-table additions (Marcos): gate fail-open items (task #33)
From the fail-open audit (code cited in-session): (1) deploy-freeze _entries_paused fails OPEN on
API error (bot:4620) — the deploy-safety tool vanishes exactly when the dashboard is unhealthy;
(2) entry gates (backside/runway/ambient/read-list) have no fail-open counter — exec paths count
(_exec_health), entry gates are silent. Friday = evidence + design; changes post-8/8 via rig.

## 8/7 09:2x — Marcos: "let the chart and tape decide" — veto/mapless collision FIXED (data-only)
Morning veto posted with break=None -> mapless gate closed TAPE lanes on NAMI/CLRO = total lockout,
violating the settled 7/26 doctrine (veto blocks chart lanes ONLY). Marcos: "do it" -> restored
Kev's 8/6-night numbers UNDER the standing veto via merge POST (no code, no restart). Verified by
GET: NAMI 7.00/6.50->10/13 veto=True · CLRO 12.75->16.50/20 veto=True · DSY untouched.
TONIGHT'S BATCH (#31/#34) addendum: sweep parser must KEEP prior numbers when posting a veto
(veto = a flag on the map, never an eraser of it) so this manual patch is never needed again.

## 8/7 09:2x ADDENDUM — Marcos: "I have never given Kev veto power" — VETO STRIPPED
veto=False posted for NAMI/CLRO (verified in POST response). Kev's stand-down opinion preserved in
the note as INFORMATION. Doctrine refined beyond 7/26: Kev's word = freshest MAP data, never a
command; no lane is blocked by his opinion — chart gate and tape decide, always. TONIGHT (#31/#34):
sweep parser must stop emitting veto:true entirely — map his do-not-trade language into the note
field only.

## 8/7 09:3x — NAMI read killed by the 8/5 bug's TWIN; fix deferred to close (my call, Marcos: "do what you think")
Reread path (newcomer_vision_reader.py:683) still falls back to prior_day_close when the price
lookup misses — the 8/5 "never prior close" fix patched only the batch site (:596). NAMI 09:09
read (break 10.23, story visible: reader renders session hi/lo) was killed as level_scale_insane
vs live "2.91" = YESTERDAY. Decision: NO mid-session reader push — evidence-day integrity, reader
restart amnesia, NAMI covered (tape lanes + backside + Kev-called top). TONIGHT (#34 batch):
:683 -> _live_px_10s + ring-2 sweep of every validate_read call-site + rig pin per site (NAMI
specimen: 2.91-vs-10.23 must PASS). CLRO counter-proof the reader sees the story: 09:09 SKIP
"gapped violently to 17.50 then fade" — system's own eyes reached Kev's conclusion, no veto used.

## 8/7 09:4x — Open scorecard + halt lane to docket (#37, Marcos's call)
First 15 min: FOUR correct refusals, $0 risked — NAMI 9.00 breakside-reject off the marcos-map
(faded to 7.68 in 6 min, ~$57 saved) · MB inverted-stop skip (stale 19.75 map, bad_stop_skip
held) · CLRO "topping tail at the high" momentum reject · DSY 6.23→5.32 whipsaw untouched
(ignition below 4.5x convert both pushes). MB then delivered the day's move WITHOUT us: 12.18 →
VWAP reclaim 13.63 → HALT UP → 15.95 resumption; bot's only row = halt_suspect 09:42:11. Second
halt-lane specimen in two days (WYHG 8/6). #37 = halt-resumption lane, weekend, kill-test first.
Reclaim-detector silence on the 13.63 reclaim = tonight's post-mortem (hypothesis: halt gaps
shred consecutive-bar patterns).

## 8/7 11:1x — HALT INVENTORY, era-wide, ANALYSIS-ONLY (halt_inventory_20260807 + rows json)
Marcos: "halts happen all around us and we just watch" -> inventory ran intraday (read-only).
Naive pass +$6,987/87 halts REJECTED by own checks (fake halts on thin tape + hindsight-low fills).
HONEST rules (LULD 4.5-20min, $5k tape both sides, entry = pre-halt pullback CLOSE, half-size $500,
half out on resumption, trail rest): 49 up-halts, +$1,322.94, 67% W, mean +$27/halt (~4/day).
WYHG 8/6 alone: +$150/+$145/+$117. Worst single: −$61.60. OPEN QUESTION for #37: the live TRIGGER
(replay knows which pullback preceded the halt; live we don't — Kev's wick-buyback on verticals is
the candidate, kill-test on 5s tape). No recommendation beyond running #37 from this table.

## 8/7 11:2x — HALT TRIGGER FOUND (halt_trigger_study_20260807, analysis-only)
Marcos: "analyze the possible triggers. look at the bars." LULD BAND-PROXIMITY is the signal:
(px/ref5min−1)/band — pre-halt median 0.83 vs 0.26 on equally-fast controls. Candidate trigger
prox>=0.7 + vel1m>=5%: catches 33/58 halts; 34 control fires are fast verticals (not junk).
KEV-WICK IS ANTI-CORRELATED with halt-bound moves (7/58 vs 30% of controls) — halt ladders don't
pull back; this is WHY the wick-shaped lanes watched WYHG/MB all week. Remaining before ship (#37):
price the control fires (lane expectancy = ladders − fades), 5s refinement, sizing/stops, auditor.

## 8/7 11:4x — 5s CONFIRM STAGE added to halt lane (#37, Marcos's call) + MB stop-fill specimen
5s study (halt_trigger_5s_20260807, first-ever 5s day): up-halt final-60s signature = uptick-ratio
>=0.8 + max-retrace <=1% ("tape stops breathing"; MB 1.0/0%, YJ 0.83-0.89) vs ~2% retrace on
normal verticals — the thing 10s bars average away. Lane trigger = 10s band-prox ARM + 5s CONFIRM.
n=5 specimens (one day) — accumulates daily; kill-test at build.
MB 14:58 EXIT SPECIMEN: ratcheted stop 13.37 breached 14:58:10, fill 12.88 ~35s later (−50c
through the stop, 30k-vol flush) — the resting-stop-refresh-on-ratchet gap from the go-live
checklist, now with a live cost (~$18). Tonight's list.

## 8/7 11:5x — 5s RIDE-SEAM LANE born (#38, Marcos: "be IN the stocks that got halted on the way up")
Seam = 5s micro-pullback >=1.5% + reclaim close, FRONT SIDE only (>=90% of session high), stop at
trough, half at +1R, 12-bar 5s trail. 8/7 runners: 6 seams, 5/6 W, +$206.67 — YJ 09:37 $1.52
+$95.56 (18 min BEFORE its first halt = the ride entry), ZYBT 09:49 +$113.40. Raw/no-front-filter
NAMI −$153 = the fade-side failure mode; front filter added POST-HOC → 8/7 counts as DESIGN day,
rules now frozen, kill-test on accumulating 5s days. MB-class no-breathe ladders = zero seams →
halt lane #37 is the complement. Seams are sub-resolution for 10s/1-min — only 5s shows them.

## 8/7 12:1x — SEAM LANE WEEK REPLAY: broad REFUTED, crown inconclusive (Marcos: "run it for the week")
10s lower-bound, honest universe (all engaged movers 8/3-8/6): 582 seams −$6,036.02, 34% W —
death by chop cuts. 8/7's +$206/6 = SURVIVORSHIP (universe was the day's known ladder names).
Crown-scoped: 31 seams +$89.46 45% over the only 2 crown-era days (−$464 then +$553) = noise.
DISPOSITION (#38): ship bar pre-written — crown-scoped 5s-NATIVE must clear positive expectancy,
n>=30, >=5 accumulated 5s days, worst day > −$100. Files: ride_seams_week10s_20260807.py.
The check that saved us: same-day backtest-before-recommend on the full universe, per law.

## 8/7 ~11:4x — THE CALL: STILL UNDER CONSTRUCTION (Marcos, pre-empting the 8/8 gate)
No launch 8/20, no small trial. Build continues readiness-gated. The floor is proven; the engine
is not. Smaller+later applied at its limit: zero, until earned.

## 8/7 12:0x — THE FRESHNESS CONTRACT ordered (Marcos: "fucking do it!!!") — #36 is now weekend ROCK #1
8 recurrences of the same wound (crown 60s reads, cap lift, validator px, freshest gates, priority
queue, blue-sky maps, NAMI hand-map — and YJ STILL ran +545% on maps one-full-map behind; trigger
past_map = reactive by a whole map, reader:1040). THE CONTRACT: crowned map never > N min old AND
never > X% from price. Enforcement: auto-map tape floor + velocity-aware reread trigger. Proof:
freshness meter on every gate row + freshness_breach alerts + EOD worst-case report. Acceptance:
replay YJ/CELZ/NAMI — live map at every gate decision on the day's #1 runner, or it's not done.

## 8/7 17:2x — NIGHT BATCH DEPLOYED (all 4 services SUCCESS; freeze on->off around the push; book flat verified 17:15)
SHIPPED: FRESHNESS CONTRACT bot-side (auto-map floor, effective-map at runway/breakside/mapless/
zone/CHART GATE, breach rows + meter, 20s memo, kill FRESHNESS_CONTRACT=0) + reader read-ahead
trigger (near_map_exhaust @80% of lastT, once per map version) + reader live-px twin fix (:683)
+ parser can never mint veto / never erase numbers + kev-over-kev FIELD-WISE merge (veto survives
sweeps; only Marcos's explicit POST sets it) + #34 counter economy (ticket-at-execution w/ race
check; refunds at momentum/l2/balance/wide-stop/chart-gate/order-failed; conservation invariant
pin = found 5 unknown leaks in one night) + #12 honest-R floor (effR, hoisted per auditor) + #17
PRE tile reset + entry_session on live state + #39 1s capture (record-only, hot-15 roster).
BLAST RADIUS AUDITOR (first run, separate context): 3 BLOCKERS + 7 WARNs found post-green-suite —
all fixed or explicitly flagged (one-sided dist arm + legacy-timestamp DST = flagged, unchanged).
Suites: 177 checks ALL GREEN + 20260730 green (cache-aware). OPEN halves, stated loudly: gate
PERIMETER refactor (weekend rock), non-crown wall (#27 remainder), resting-stop refresh (MB 2×
specimens), EOD freshness report, YJ/CELZ/NAMI acceptance replay (weekend).

## 8/8 — FRESHNESS CONTRACT ACCEPTANCE: PASSED core criterion (freshness_acceptance_20260808)
Shipped code vs recorded YJ 8/7: live break within 3% of px at ALL five gate moments (never a
dead map); the 10:23 $3.96 fire (stale-map REJECT, +$213 in the crown replay) now PASSES on a
computed current map. FINDING: at fresh highs auto-map gap≈0 -> breakside structurally open for
sprinting crowns — the blow-off guard must be the READ made sticky, not the stale-map accident.
#28 promoted to weekend MUST-SHIP as that guard. Harness caveat: forced-stale timestamps = the
auto-map path exercised throughout; fresh-path discrimination covered by rig pins.

## 8/8 (Fri eve) — WEEKEND SESSION 1 SHIPPED (bot redeploy, book flat 17:58, market closed)
1. FRESHNESS ACCEPTANCE passed (separate entry above) — finding drove #28's promotion.
2. #28 STICKY STAND-DOWN built+pinned+shipped: ceiling fire binds the ticker's chart lanes to
   that read's _ts; fresh read lifts; standdown_active rows; kill STANDDOWN_STICKY=0. Specimen
   verified from recorded rows: YJ 11:44 ceiling -> 11:51 top-buy would have been BLOCKED (no
   new read arrived). Tape lanes unaffected (7/26 doctrine).
3. PERIMETER METER shipped (observability before the wall): every fill logs covered/uncovered
   gate lists for its lane (perimeter_stamp rows) + loud warning on mostly-ungated lanes.
   The one-wall refactor = Saturday's rock, verified BY this meter after it lands.
Suites green both (incl. 5 new #28 pins). Remaining weekend queue: perimeter wall, #35 restarts,
#37 halt lane, #32 vision sweep, classifier head-to-head (Marshal), EOD freshness+crown reports,
resting-stop refresh, breakside tolerance re-grade (Ombudsman), 5s-vs-10s + PRE-bill analyses.

## 8/8 — WEEKEND SESSION 2: PERIMETER WALL + OMBUDSMAN HEARING #1 (deployed, book flat, mkt closed)
1. PERIMETER WALL pt 1: execute_trade demands a per-thread token granted ONLY at the gate-chain
   end (+ explicit startup-test bless); pathless orders -> perimeter_refused (+kill switch
   PERIMETER_ENFORCE=0). Side-door closed: ma_pullback + ema_bounce join BREAKSIDE_LANES (YJ
   $10.95 specimen; thin-beyond-one-day evidence flagged). Dormant 2-of-3 unpack crash in the
   TEST_TRADE path fixed. 7 pins; 7/31 lane pin consciously superseded.
2. OMBUDSMAN HEARING #1 — BREAKSIDE TOLERANCE (breakside_tolerance_20260808, frozen rule): 36
   era rejects priced. tol 1% = +$581.70/4 admits, worst −$48.19 -> SHIP-CANDIDATE met; SHIPPED
   0.0% -> 1.0%. CAVEAT: half the gain = YJ 8/7 x2 (concentration); >1% chase-refusal stands.
3. INFRA DEFECT found+worked around: /api/decisions_archive default limit=5000 EVICTS the morning
   from analysis views on busy days (YJ's exhibit invisible until &limit=50000). All analysis
   scripts must pass explicit limit; dashboards already do. Noted for the Friday audit list.
Suites green x2. Deployed to bot service (sleeping until Mon 03:55).

## 8/8 — WEEKEND SESSION 3: PAINLESS RESTARTS SHIPPED (#35 core; deploy SUCCESS 18:26, book flat)
Discovery first (settled-first law): resume_monitoring_if_open() EXISTED since early build but
keys off the BROKER position (always flat in DRY_RUN) and restarts monitors stateless — why 7/29
force-closed everything. Built the real thing:
1. monitor_trade(resume_state=): restores partials/tier_idx/highest/remaining; stop resumes at
   the RATCHET (never lower); R from ORIGINAL risk_ps (auditor blocker: ratcheted-R collapsed
   tiers -> resumed trades would have OVERSOLD).
2. _recover_orphaned_trades: same-day intraday orphans RESUME (registered with the watchdog
   pre-start — auditor blocker: unregistered = frozen-invisible; crash-fallback wrapper closes+
   records if a resumed monitor dies). Overnight orphans still close. Kill: RESUME_OPEN_TRADES=0.
3. _rebuild_counters_from_today: event-sourced boot rehydrate of PRE tickets/hidden caps/curl
   slots/held from the day's own records; once-per-day sentinel + zero-first (auditor blocker:
   per-rescan double-add would have starved lanes by midday); recovery records now carry
   entry_session; trade_id dedupe.
4. Stand-down hardening (auditor): never binds on ts-less maps; ts-unknown holds max 30 min.
   Perimeter grant moved below the last reject (thread-reuse future-proof).
AUDITOR round 2: 3 blockers + 3 warns found post-green — all fixed, pins updated consciously.
Suites: 199 checks ALL GREEN + 7/30 green. REMAINDER STATED (whole-sandwich): live restart drill
(kill mid-DRY_RUN-trade) = Monday's real gauntlet; EOD freshness/crown reports still open (#36).

## 8/8 — WEEKEND SESSION 4: CROWN/FRESHNESS EOD REPORTS SHIPPED (#36 CLOSED WHOLE; dashboard SUCCESS)
crown_eod_report.py daemon (kev_sweep pattern, 16:20 ET weekdays): per crown, ONE decision row —
offered_pct (post-crown session high vs crown-time px, from stored bars) vs captured_usd (that
ticker's closed trades) + refusals_post_crown + freshness breach worst-case; plus a freshness_eod
summary row. The Steward's shame metric, automated. Functional smoke GREEN in-session (synthetic
YJ: offered 262.9% vs captured −$4.56, refusals 1, breaches 1 — computed correctly). run_now_day
test hook; CROWN_EOD_REPORT=0 kill; added to dashboard watchPatterns (the 7/20 trap, pinned).
#35 and #36 both CLOSED. Rock scoreboard: Freshness Contract ✓ · #28 ✓ · Perimeter wall pt1 ✓ ·
Restarts ✓ · EOD reports ✓ · Ombudsman hearing #1 shipped ✓. REMAINING for the 8/14 freeze:
#37 halt lane (rock) · #32 vision sweep · classifier head-to-head (Marshal) · #27 non-crown wall ·
resting-stop refresh · #16/#18/#30/#33/#11 graded leftovers · Monday live restart drill.

## 8/8 — WEEKEND SESSION 5: HALT-LADDER LANE SHIPPED SHADOW-FIRST (#37; deploy SUCCESS, book flat)
PRE-BUILD KILL-TEST (halt_lane_expectancy_20260808, frozen verdict): full trigger priced era-wide
INCLUDING false fires — 110 arms, +$840.93, 55% W, mean +$7.64, worst day −$145.16 -> BUILD.
Honest flag: replay universe = names-that-halted (hindsight); live scope = CROWNS (matched the
halting set all week). BUILT: two-stage detector in the 10s loop — ARM prox>=0.7 + vel>=5%/m
(crowns, RTH) -> 5s CONFIRM (uptick>=0.8, retrace<=1%, FAIL-CLOSED) -> halt_arm shadow row always;
conversion (half-size, entry_type halt_ladder) behind HALT_LANE_CONVERT=0. Monday = live shadow
day; convert flips only if shadow rows validate the replay. FIRST 5s CONSUMER: record-only pin
consciously retired -> new pin asserts _halt5_confirm is the ONLY reader. 208 checks ALL GREEN.

## 8/8 20:5x — MARCOS'S CALL: HALT LANE CONVERTS MONDAY ("we're trading with fake money, go live Monday")
HALT_LANE_CONVERT=1 set on Railway (verified). Rationale: DRY_RUN book = paper; live conversion IS
the strongest validation. Lane trades Monday: crowns only, arm prox>=0.7 + vel>=5%/m, 5s confirm
fail-closed, HALF size, entry_type halt_ladder, every arm still logs its full halt_arm row (the
shadow ledger rides along regardless). Monday EOD: arms-vs-replay comparison + first live lane P&L.

## 8/8 — FRONT/BACK ARMS: UNGRADEABLE AS FROZEN (fidelity gate ABORT, working as designed)
frontside_oos_grade_20260731.py ran for the first time: reconstruction matched the saved 136-row
artifact only 64.8% (<95% mandate) — the original /tmp scorer is unrecoverable. Per its own §F
clause: NO scoring on an unvalidated reimplementation. The 7/29 A/B/C registration is closed as
UNGRADEABLE, not refuted. Marshal's path: SIDE variable ships data-only next week with frozen-in-
CODE definitions; graded on a week of live stamps. (Lesson already law: artifacts in data/, never /tmp.)

## 8/8 — 5s-vs-10s EXIT REPLAY (Marcos's standing order) + THE ENGINE GAP (tape_5s_vs_10s_20260808)
(1) Exits: 23/24 Friday trades IDENTICAL at same wall-time windows; the one diff (WFF) = 5s trail
cut the +68% ride $38 EARLIER. Resolution's edge = entries/detection, NOT exits. (2) THE FINDING:
live machinery +$530.65 vs frozen killtest engine −$9.46 on the SAME entries — the sim engine is
~$540/day PESSIMISTIC vs the real exits (HUIZ: six live +$40-65 wins sim as −$30 losers). ALL
engine-priced studies carry this caveat (fair arm-vs-arm, unreliable in absolute $, biased vs
actuals). #12 real-path replay harness ELEVATED with a measured error bar. Evidence hierarchy now:
actual trades > live shadow rows > engine studies.

## 8/8 late — REAL-PATH HARNESS (#12) BUILT, WIP AT 15/24 FIDELITY (harness_real.py)
Marcos: "let's upgrade our sim machine." Built the real thing: monitor_trade ITSELF replayed on a
virtual clock (patched time/datetime/stream/quotes/bars; true M1 aggregation; 5s print feed for
sub-bar sequencing). Fidelity vs Friday's 24 actual trades: −$348 -> −$264 -> +$15.52 total
(actual +$530.65) across three iterations; 15/24 sign-match; HUIZ +61.87 EXACT, three more within
$1-4. FROZEN BAR (±$100, >=18 signs) NOT MET -> old engine stays deprecated-with-caveat, harness
is WIP not standard. Remaining gap = 4 trades ($518, WFF's 80-min ride = $165): next lever is
diffing harness stop-evolution vs the LIVE custody_heartbeat rows (the real monitor's recorded
stops) on WFF — precision debugging, no guessing. Saturday continues.

## 8/8 midday — HARNESS CONVERGED TO ITS 8/7-TAPE LIMIT (harness_real.py v1)
Iterations: −$348 -> −$264 -> +$16 -> +$96 -> +$192 (actual +$531). Root causes found+fixed with
evidence each time: epoch-vs-seconds keys; result capture; TRUE M1 aggregation (was feeding 10s
as minutes); 5s print feed; forming-minute semantics (live's [:-1] drops the forming 3-min bucket
— a completed-only feed made it drop a REAL one -> phantom pre-entry health-folds; WFF fold traced
to a stale $3.40 bucket). RESULT: WFF 80-min ride +$227.69 vs +$215.59 actual (within $12); QNME
$1; MB/VATE/YJ $3; HUIZ 3/6 within $4 incl one EXACT. RESIDUAL $338 = spike-entry grinders where
survival hinges on sub-5s print order (my risk%%-class hypothesis FAILED its own check — 23/24
trades are normal-risk; the class is whipsaw-at-entry, no clean record-level classifier). 
DISPOSITION: harness = STANDARD ENGINE for counterfactuals with the miss-class documented; frozen
±$100 bar NOT met so the claim stays scoped; 1s tape (live Monday) is the closing instrument.

## 8/8 12:2x — SEAM LANE LIVE-CONVERTS MONDAY (Marcos x3: real live test / shadow optional / CROWNS ONLY)
Marcos overrode shadow-first for #38 (paper book = the kill-test): crown_seam lane CONVERTS by
default (SEAM_CONVERT=0 restores shadow), crowns only, frozen 8/7 seam rules (front side >=90% of
session-window high, up-phase, pull >=1.5%, 5s reclaim close; stop = trough). Every fire still
logs seam_shadow_fire evidence rows. PLUS halt_early_arm shadow meter (prox 0.4-0.7 band) to
grade the even-earlier boarding point. 5s reader doctrine pin now enumerates exactly TWO readers.
A silent-replace no-op (early-arm anchor mismatch) was caught by the rig and re-applied with
asserts — Monday runs THREE new evidence streams: halt lane (converting), seam lane (converting),
early-arm (shadow). All crowns-only. Deploys SUCCESS.

## 8/8 — SEAM LANE: REMOVED FROM CONVERSION (Marcos); H2 REGISTERED; revisit AFTER TUESDAY
Sequence, all same-day (Seam Scientist chartered mid-stream): as-shipped crown-seam kill-test
(run AFTER conversion — my process failure, owned): 9 fires −$390 -> Marcos: "remove it now. But
an alternative needs to be worked and ready." SEAM_CONVERT=0 (verified; HALT_LANE_CONVERT=1
untouched). RESEARCH TRAIL (registry, all frozen-before-grade):
- Eligibility A crowns-only: −$390/9 (post-crown = the refuted prior-run class; beginnings PRECEDE
  crowns — YJ's winning seam was 41 min pre-crown).
- Eligibility B daygain>=25 AM: −$120/7 (PCLA chop).
- Eligibility C impulse-within-10min: −$1,520/100 (impulses ubiquitous on this tape).
- SPECIMEN ANATOMY (5 winners vs 5 worst losers): discriminators = mins-since-fresh-high <=5,
  runup30m 5-35%, <=60% off day low.
- H1 (anatomy composite), full-day validation: −$470/57 — but failure shape = repeat-spam
  (BYAH x12, XHLD x12; replays lacked per-name caps).
- H1 + one-fire-per-name: −$165/19. + morning-first-fire-only: **−$2.72/13 = BREAKEVEN** with the
  right winners (XHLD +92, YJ +96, ZYBT, SUGP, ENSC) and a sub-$3-chop loser cohort.
**H2 REGISTERED (frozen 8/8): fresh-high seam (mins-since-high<=5, runup30m 5-35%, <=60% off day
low) + ONE fire per name + morning window (<11:00).** Breakeven on formation day; ships NOTHING
until positive on Mon+Tue UNSEEN shadow tape (seam_shadow_fire rows keep logging, convert stays 0).
If positive both days -> convert Wednesday w/ circuit breaker (lane -$100/day -> auto-shadow).
One-day variant-hunting STOPPED at H2 per the Scientist's charter — the next filter found on the
same 57 fires would be a fitted ghost. MONDAY LIVE SET: halt lane CONVERTING (era +$840 evidence),
seam SHADOW (H2 grading), early-arm SHADOW (prox 0.4-0.7 meter), 1s capture begins.

## 8/8 — #32 FRAME-VISION CHECK: KILL-TESTED AND SHIPPED (dashboard SUCCESS)
Kill-test on the NAMI/NMI specimen video (9cZI9zIlV_g): dense 2s frames + vision OCR read the
on-screen tickers EXACTLY — NAMI, CLRO, DSY in order (captions had garbled NAMI->NMI) — and the
extracted drawn-price lines contained EVERY real Kev level (NAMI 13/10 · CLRO 20/16.5/12.77/10.5
· DSY 15/8.21/7.30). SHIPPED v1 in kev_sweep_server: after each TOP-3 parse, download (yt-dlp
android-client + proxy) -> frames (imageio-ffmpeg bundled binary) -> ticker OCR in 30-frame
batches -> SCREEN OVERRIDES caption tickers (edit-distance<=2 pairing, order preserved; unpaired
screen tickers post with note; caption-only names survive). Fail-soft at every step (captions
stand); kill KEV_VISION_CHECK=0; ~4 vision calls/video. The Friday-night ticker-garble class
(EASY/FUS/HYM/NMI) now has a machine answer. 7 pins; suites green; deployed.

## 8/8 — PROXY BUDGET: Webshare 3GB->10GB (Marcos) + vision download CACHE shipped
Usage math: transcripts/listings = KBs; vision video downloads = ~12MB x 2/day ~ 500MB/mo normal
BUT sweep retries re-downloaded the SAME video (stubborn night = 5-10x -> ~7GB/mo, near the cap).
Fixed: _vision_cache per video id — one download per vid per day, retries reuse OCR hits;
_apply_screen_tickers refactored out for the cached path. Deployed.

## 8/8 afternoon — RESTING-STOP SYNC + RUNWAY WALL SHIPPED (#27 CLOSED WHOLE; deploy SUCCESS 14:33)
RESTING-STOP SYNC: the software stop's every ratchet now re-places the broker resting order
(>=0.25% climbs, 20s cadence, raise-only). Auditor round 4 caught 2 blockers pre-ship: (A) my
sync sat INSIDE the 60s heartbeat throttle (20s cadence was an illusion); (B) cancel-before-place
would strip protection on a broker rejection AND self-disable forever -> now PLACE-THEN-CANCEL
with retry. + (C) DRY_RUN returns a fake stop id (parity: repeated syncs exercisable on paper);
(E) runway "one truth per trade" — gate-time value reused at card+record (retest fills were about
to show ~0.2R fiction). RUNWAY WALL (#27 completion, Marcos's 8/4 directive whole at last):
spent rungs demoted, session high = the road's end when it stands between entry and ink; behavioral
exec-eval pins incl. the MB-150R ghost case; breakout-at-high and retest-gate flows UNCHANGED
(verified in audit E). Suites green x2. #27 marked complete: rung-classified (8/4) + effective-map
(8/7) + wall/spent-rungs (8/8) = the whole directive.

## 8/8 — #33 SHIPPED (gate fail-open counter + freeze 10-min last-known tolerance)
Every silent entry-gate fail-open (ambient <5-bars/exception, backside exception, runway
exception, freeze API errors) now logs a gate_fail_open row (60s cadence/gate) — the meter the
8/7 audit found missing. Freeze client keeps LAST-KNOWN pause state through <=10 min of dashboard
API failure (a frozen bot stays frozen through a mid-deploy blip), failing open loudly only after.
PROCESS SLIP owned: one deploy went out while the suite was red (an exec-eval namespace crash,
not a code defect — the deployed code was green; the rig namespace needed the counter stub).
Rule reinforced: suite exit-0 BEFORE railway up, no exceptions, even for "obviously test-side" reds.

## 8/8 — #18 DELIVERED: VWAP-side grade (vwap_side_grade_20260808, 146/146 era RTH trades)
BELOW session VWAP at entry: 53 tr +$1,431.03 (81% win) · ABOVE: 93 tr −$1,038.06 (30% win).
Slope leg degenerate (cumulative VWAP ~never falls on gap-up days). READING: on runner days
cumulative VWAP = "how much of the move already happened" — below = EARLY (the WFF/HUIZ class),
above = EXTENDED (the 30%-win chase class). Same beginning-vs-extension law as the seam research
and the prior-run refutation, now in the era's own trades. DISPOSITION: data-only — feeds the
Marshal's SIDE variable + Ombudsman bias ledger; challenges the "below VWAP = fighting the tape"
frame but ships NO gate change (below cohort includes the knife-catches; winner-dominated cells).
#16 closed as superseded (orb covered by the 8/6 retest study + shipped lane).

## 8/8 — LEFTOVERS CLEARED; BUILD BOARD CLEAN BEFORE THE 8/14 FREEZE
#33 shipped (fail-open meter + freeze tolerance) · #18 delivered (VWAP-side grade) · #16 closed
(superseded by the shipped retest lane) · #11 closed (evidence expired; class now observable via
heartbeats/off-tape guard/fine tape) · #31 closed (absorbed) · #30 recommended CUT to post-freeze
backlog (new-lane design vs the scope rule — Marcos can veto). OPEN on the board: #37 halt lane
(Monday = first converting day) · #38 seam H2 (Mon+Tue grading, revisit after Tuesday). Everything
else COMPLETE. Monday's checklist: 03:55 boot (all new knobs stamp), first vision-checked sweeps
(tonight 20:06 + 09:02), halt lane's first arms, H2 shadow rows, 1s capture first day, live restart
drill (kill mid-DRY_RUN-trade), EOD: crown report auto-fires 16:20 + lane verdicts.

## 8/8 — VWAP-SIDE SIZING SHIPPED, CROWN-EXEMPT (Marcos: "Go with B" + "Will this affect the crowns?")
Kill-test (vwap_sizing_20260808, frozen): B half-above +$912 vs actual +$393 (+$519); inverse
control −$323 (directional sanity); dose D +$1,172 (declined — one conservative step on 2-week
evidence). CROWN QUESTION answered with data: above/CROWN −$90 flat (35tr) vs above/field −$948
(58tr) — the bleed is the FIELD's. SHIPPED: field entries above session VWAP take HALF size
(VWAP_SIDE_SIZING=0.5, kill=1.0); CROWNS EXEMPT (every bullet kept, ~$45 era cost = doctrine
insurance); fail-open full size when VWAP unknown; vwap_side_sized rows. CAVEATS ledgered:
~ALPVWAP coverage = 2 weeks only; week-32 edge thin (+$72); graded live from Monday. 4 pins;
suites green; deploy SUCCESS.

## 8/8 — VWAP-SIDE SIZING -> 0.25 (Marcos went with the updated recommendation)
Field-only dose table (crowns exempt): 0.25 = +$1,103.63 era vs +$867 at 0.5, positive BOTH weeks
at every dose. 26%-win cohort gets quarter capital; f=0 declined (refusal = Ombudsman line).
Env flip verified; scope confirmed: ONLY non-crown entries above session VWAP at fire time.

## 8/8 — WICK-SCALP DISPOSITION + H3 REGISTERED (Marcos: "register it")
The 8/3 study's own verdict surfaced: v1 REFUTED on its frozen universe arm (605 fires −$2,098.63,
43%; "either fails -> nothing ships"). Lane #30 stays cut. The live mechanic (Kev's pierce-and-
instant-buyback) is a SEAM-family pattern -> registered as H3 in the Seam Scientist's registry:
H2 + liquidity-grab qualifier (trough pierces a visible prior low, reclaim closes upper-half).
Frozen 8/8 pre-grading; graded on Mon/Tue shadow rows + accumulating 5s days; standard OOS wall.

## 8/8 eve — MARCOS'S TWO VERIFICATIONS + THE SIDE VARIABLE DELIVERED (deploy SUCCESS)
(2) RUNG/LEVEL/SKY: verified DONE site-by-site — rung/MAJOR thresholds, classifier on the
effective map, rung ratchet, wall+spent-rungs, sticky ceiling, blue-sky both ways, breakside.
(1) FRONT/BACK: guards were live (backside gate, stand-down, topping-tail, reader narrations)
but the Marshal's UNIFIED SIDE VARIABLE was chartered-not-coded — the gap Marcos's verification
caught. BUILT tonight: _side_state (front_side / back_side / basing / reclaim_attempt / unknown)
from live tape (hi staleness + dd + 3-min compression/mean), stamped on every fill's
perimeter_stamp and every custody_heartbeat, DATA-ONLY (consumed by nothing until a week of
stamps grades side-vs-outcome in dollars). 5 behavioral pins; suites green; deployed.

## 8/8 eve — DAILY SIDE REVIEW RITUAL SET (Marcos) + rejects now carry SIDE (deploy SUCCESS)
Machinery-completeness pass found the grading gap immediately: refusal rows lacked the SIDE stamp
(can't grade "did we refuse front-side strength?" without it). Fixed centrally in _log_decision:
every *_reject/*_capped/*_skip row stamps side (20s memo per name). EOD ritual from Monday: SIDE
master table + completeness check + consumer-ladder verdicts, daily, with Marcos.

## 2026-08-08 (Sat eve) — SHADOW-LANES BOARD shipped (Dashboard Curator's first build)
- New dashboard section "Shadow Lanes": today's halt_arm / halt_early_arm / seam_shadow_fire
  rows, newest-first, with price, SIDE, lane detail (prox/vel/5s-confirm or pull/stop), and
  converted-vs-shadow flag. Clone of the gate-rejects strip; &limit=50000 (the 8/8 eviction
  lesson applied at birth).
- Companion bot fix: _log_decision side stamp extended to the three shadow statuses (they
  don't match the _reject/_capped/_skip suffixes — would have shown "—" all H2 grading week;
  SIDE is a registered candidate seam feature).
- Rig: 5 new pins; full suite exit-0 ALL GREEN before push. Flat book verified in-turn
  (Alpaca positions [] @ 17:10 ET Sat). Both services deployed (bot + dashboard/ scanner).

## 2026-08-08 — SEVENTH OFFICE: Forward Architect (Marcos's charter)
- "office of quality control and forward thinking... constantly thinking of ways to improve
  the bot... entries, exits, new personas, anything." Chartered with hard bindings: every
  idea = registered HYPOTHESIS with kill-test attached, never a recommendation; feeds the
  post-freeze backlog only; one best idea per weekend review; grades its own hit rate in $.
- Seed registry (all HYPOTHESIS): exit offered-vs-captured science, sector sympathy,
  time-of-day exit curve, re-entry doctrine (WFF class), overnight/gap book.

## 2026-08-08 late — HALT LANE: full-day 5s forensics + ARM-ON-5S SHIPPED (Marcos: "go with 1")
- PARTIAL-DAY CALIBRATION DEFECT FOUND: the 8/7 5s confirm study ran at 11:40 AM and was never
  re-run on the full session — "n=5 accumulates daily" was a promise with no mechanism. Full-day
  tape: 86 zero-print gaps / ~29 dense-tape LULD halts (MB 15, YJ 13, ZYBT 1); thin-name gaps
  (SPHL/PETZ, ~1 print/min) are illiquidity, not halts. NEW LAW: intraday-calibrated thresholds
  get a mandatory same-night full-day re-grade before gating live trades.
- STRICT 5s CONFIRM REFUTED AS A GATE (halt_confirm_regrade_20260808): full Friday, live-like
  sim — STRICT 1 entry −$48.78 (0/1; its only pass was a pre-fade top; refused YJ 09:54 +$399).
  Confirm stays as a DATA STAMP on halt_arm rows (still gating conversion per Marcos — he took
  leg 1 only; the stamp keeps grading on unseen days). LOOSE (up>=0.6,pull<=5) = +$403/12 but
  IN-SAMPLE — registered hypothesis only.
- SIM-CONVENTION CONTRADICTION, owned: two scripts (regrade vs resolution head-to-head) used
  different re-arm conventions and I quoted both. VOID: +$8.13/+$129.53/+$226.95 overlapping-arm
  figures. CANONICAL (arm_resolution_reconciled_20260808, one live-like convention, one open
  position per name): Friday 10S-ARM 18 fires −$13.91 | 5S-ARM 18 fires +$216.35 (9/18). Era
  +$840.93 (10s, 110 arms) stands — different days/universe; one day never outvotes an era.
  Also: earlier "10s never armed YJ" WRONG — halt inventory universe for Friday was [MB] only
  (inventory built intraday too, same disease); with full universe 10s arms YJ 09:54 fine.
- SHIPPED: (1) HALT_ARM_5S=1 — arm computes prox/vel on the 5s feed via new _alp5_feed()
  (sec-keyed c/l/h, fail-soft {}), >=24-bar density gate, 10s fallback fail-open, kill=0.
  (2) TWO DEAD-ON-ARRIVAL TUPLE-UNPACK BUGS fixed: detector `_hl_d10 = _curl_feed(...)` ate the
  (bars,src) tuple -> sorted() TypeError swallowed -> ZERO arms ever (Monday's converting lane
  was silently dead); _side_state same miss -> every SIDE stamp "unknown" (grading week wasted).
  Caught by EXECUTED checks, not pattern pins — rig pins upgraded to exec-eval for both
  (side_state returns real side; _alp5_feed shape test). 5s-reader doctrine pin now THREE
  enumerated readers. Suite exit-0 captured directly (not through a pipe). Flat book verified
  in-turn (positions [] @ 18:29 ET). Bot deployed; boot verification pending in-session.

## 2026-08-08 latest — CONFIRM DEMOTED TO STAMP (Marcos: "Fix the confirm")
- HALT_CONFIRM_GATE=0 default: arm converts (era-priced + Friday 5s +$216.35); confirm logs
  ok/up/pull on every halt_arm row, blocks nothing; =1 re-arms the old gate. Executed truth-table
  pins (4 cases) + suite exit-0; flat book [] @ 18:44 ET; bot redeployed. Monday: 5s arm fires
  convert for crowns at half size; board's ✅/❌ column grades the demoted confirm on unseen tape.

## 2026-08-08 night — ARM ANATOMY: Friday's 18 arms, winners vs losers (arm_anatomy_20260808)
- Marcos: "i can't fathom that we can't figure something out with all that data." He was right —
  the anatomy pass found two hard splits the refuted tape-texture confirm never touched:
  (1) HALT-H1 POST-RESUMPTION COOLDOWN: the 4 worst losers armed 2.2-9.9 min after a resumption
  (YJ 12:28 −$106, MB 12:19 −$79, YJ 11:20 −$63, YJ 13:45 −$49); winners armed 10-35+ min after.
  In-sample: skipping <10-min arms = Friday +$484 vs +$216. REGISTERED HYPOTHESIS — stamp first.
  (2) HALT-H2 SIDE ALIGNMENT: winners median 20.7% off day high, losers 52.1%; worst losers had
  −27/−44% 30-min runs (bounces inside collapses). Live backside gate does NOT catch these —
  its band ends at 30% below high; the losers sat 51-75% below (the known loose-edge hole).
  SIDE stamp on arm rows grades this automatically from Monday.
- SHIPPED (data-only): mins_since_halt stamped on every halt_arm row (gap scan of the arm feed);
  feed deepened to 30 min (10s n=180 / 5s n=360 — arm math unchanged, stamp needs the depth).
  Executed rig pins (gap-math check); suite exit-0; flat book [] @ 18:5x ET; bot redeployed.
- Wednesday-with-seams: H1/H2 verdicts from Mon+Tue unseen rows; gates only on evidence.

## 2026-08-08 close of research — MARCOS ACCEPTS LANE CONFIG; VERDICTS MOVED TO TUESDAY NIGHT
- "ok, I can live with this. We will debrief at each day and discuss Tuesday night." Daily
  debriefs Mon+Tue (rolled into the SIDE review ritual); H1/H2/confirm/early-arm + seam H2/H3
  all rule TUESDAY NIGHT 8/11 (was Wednesday). Halt-lane research CLOSED until then.

## 2026-08-08 — CROWN STAMP on trade records (Marcos: "add the crown stamp")
- entry_crown stamped on every breakout candidate pre-gates (sticky _is_leader state at entry,
  fail-soft None) and carried onto the trade record. Born from the Friday what-if: crown set had
  to be rebuilt from leader_armed rows. 3 pins; suite exit-0; flat book [] verified; deployed.
- Friday what-if (composed, in-ledger for the debrief): actual +$530.65; + halt lane crown-scoped
  +$179.32 ceiling (17/18 canonical arms on crowns; ZYBT not crowned; position-conflict trim
  unpriced); VWAP 0.25 field sizing −$21.19 (QNME shrunk, AIXI helped) => ~+$690 composed.

## 2026-08-08 night — WEEKEND SWEEP GAP FOUND + FIXED (the Sunday TOP-3 hole)
- Tonight's 20:06 verification found the scheduler gated `weekday() < 5`: NO sweep ever ran
  Sat/Sun. Kev posts Monday's TOP-3 SUNDAY evening; Friday's night sweep (which targets Monday)
  runs before it exists, and Monday 09:02 hunts the UPDATE — Monday's sheet would have been
  EMPTY at the open. The pending "Sunday hands-free" item was impossible as built.
- FIX: night sweep window + hourly retry now run EVERY day (run_once already aims weekend
  nights at Monday's sheet; Saturday runs find nothing and retire). Morning pass stays
  weekdays. 4 pins; suite exit-0; dashboard service redeployed (Sat night, market closed).
- REAL verification is tomorrow: Sunday ~20:06 the sweep should fetch Kev's video and post
  Monday's sheet hands-free — vision check included. Watcher to be armed Sunday evening.

## 2026-08-08 night — ACCOUNT DECISION: LIVE TRIAL RUNS ON MARGIN (Marcos moved the funds)
- PDT rule ELIMINATED eff. 6/4/2026 (SEC/FINRA verified via web) and CONFIRMED IMPLEMENTED on
  Marcos's Webull margin account (API: day_trades_left=UNLIMITED). Old "never margin" rule was
  a PDT-era artifact — retired DELIBERATELY with its reason.
- Why margin is required for our style: paper cycled $5.3k-$10.8k bought notional/day last week
  (24 trades Fri) vs $578 settled cash — a cash account caps daily buying at account size.
  Margin = immediate proceeds reuse; concurrent exposure is the binding limit instead.
- Marcos transferred cash->margin 8/8 night (in-flight: cash settled/BP $0.00, margin $0.00);
  watcher armed to capture the margin account's REAL day_buying_power when it lands.
- PRE-TRIAL BUILD QUEUE (blocked on funds landing): WEBULL_ACCOUNT_ID flip; settled-cash budget
  -> real-time buying-power governor; concurrent-slot cap vs live BP; token re-mint (expires
  ~8/23 — trial week); checklist re-run vs funded account. Each kill-tested, Auditor-reviewed.

## 2026-08-09 — EIGHTH OFFICE: Webull Broker Desk (Marcos: "an expert in all things webull")
- Chartered as go-live approaches: owns accounts/money (PDT-gone verified, Reg-T floor, BP
  governor doctrine), tokens/auth (re-mint ~8/23 = trial week), order semantics (resting-stop
  place-then-cancel, $5 test owed), the API-quirks ledger (bites-twice = our defect), and the
  daily broker-truth reconciliation ritual for the live trial. Feed Engineer's brokerage twin.

## 2026-08-09 — NINTH OFFICE: FIRST HOUR + Opening Bell rescoped (Marcos's structure)
- Marcos: new officer owns the opening hour (efficiency + profit); "The opening bell persona can
  be in charge of the lead up to it." FIRST HOUR = 9:30-10:30 in dollars (daily $ attribution,
  offered-vs-captured, capital-cycling audit, window hypothesis registry, first-hour blind
  minutes). OPENING BELL = premarket prep -> the bell + the 9:30 handoff. Evidence base: era
  ignition (open profitable, after-10 bleeds), H2 morning window, Friday's morning-led +$530.65.

## 2026-08-09 22:2x — MONDAY SHEET RECOVERY (Marcos caught it: "the monday tickers didn't all get saved")
- First-ever weekend sweep RAN (20:13, the weekday-gate fix proven) but posted 1/3 names: parser
  emitted ZJYLL + ZNA (caption garble), listing guard correctly dropped both, and the VISION
  check failed to download server-side ("download failed — captions stand") with NO retry — the
  exact case it was built for. Local run w/ same proxy+android client downloaded fine (transient
  rate-wall suspected, UNVERIFIED).
- MANUAL VISION RECOVERY: frames read + captions decoded + tape-verified: ZJYL (Kev #1, Chinese,
  96% AH Fri; break 4.77/confirm 4.40/targets 7-8.50-10; Alpaca paper tradable=FALSE — paper bot
  likely watch-only) and ZENA (+20% Fri 1.38->1.65 exact; break 1.70/confirm 1.65/targets 2.00,
  2.50). Posted with X-Dashboard-Secret, merge-only; sheet now HUDI+ZENA+ZJYL, verified by GET.
- QUEUED FIX (maintenance window, not tonight): vision download retry+backoff; guard-dropped
  names -> edit-distance<=2 search vs active listings + price-consistency as caption-only rescue.

## 2026-08-09 ~22:45 — SWEEP RESCUE SHIPPED TONIGHT (Marcos: "when will this get fixed" -> now;
## the 09:02 Monday morning sweep runs the same path)
- (1) Vision download: 3 attempts w/ 20s/60s backoff (single transient failure had orphaned 2/3
  of Monday's picks). (2) Caption-only rescue: guard-dropped symbol -> unique edit-distance-1
  active listing; ambiguous set (ZNA -> {ZENA,ZNB}) broken by Kev's own break price (live px
  within 2x); still ambiguous -> conservative drop. Downstream price fingerprint + cross-wire
  fail-open validate every rescue. EXECUTED pins (ZJYLL->ZJYL, ZNA+1.70->ZENA, no-price->None,
  garbage->None); suite exit-0; dashboard redeployed ~22:45 Sun (market closed, no positions).

## 2026-08-09 ~23:1x — SWEEP DEDUP BLEED FOUND+FIXED (Marcos: "why so many new ones?")
- Sweep history rows: EVERY run for days refetched 22-43 "new" transcripts (five runs 8/7 night
  ~40 each, an hour apart) — but /data/kev persists fine (71+34 files, disk 12%). Root cause:
  dedup key filename.split("_")[0] truncates YouTube ids CONTAINING underscores (EJxD_4mUiTA ->
  "EJxD") -> ~8 videos refetched every pass x5 passes x every sweep, on Marcos's proxy budget.
- FIX: ids are always 11 chars — have = {f.name[:11]}. Pins + suite exit-0; dashboard
  redeployed. Residual: errors_final~5/run = a few caption-less videos retried each pass
  (caption-lag doctrine says don't permanently skip); watch next sweeps for new~0 errors~5.

## 2026-08-09 late — PREMARKET ON THE TUESDAY AGENDA + TENTH OFFICE: Kev Librarian (Marcos)
- Premarket question added to Tuesday-night sitting: Kev's halt answer IS premarket (no LULD);
  ours is disabled pending the sessions= fix. Decide: prioritize fix + PRE re-enable plan vs
  defer past trial. Halt-lane grade must pull every through-halt outcome (reopen vs stop) + a
  spread-gate hypothesis (Kev's JLHL exit).
- KEV LIBRARIAN chartered: corpus completeness (listing-vs-store diff audits, 11-char ids),
  pipeline health (sweep schedule/vision/rescue/guards/proxy budget), same-night lesson
  chronicling with flags to owning officers, grounding audits. Born from tonight's finds:
  refetch bleed, silent vision failure, unmined halt-epidemic video.

## 2026-08-10 00:0x — MARGIN TRANSFER LANDED (watcher caught it)
- Margin C5J4BAA...: $578.37 total; day_buying_power $578.37 (1:1 — Reg-T no-leverage tier
  confirmed live below $2k); day_trades_left UNLIMITED on the FUNDED account; overnight_bp
  $578.37; no margin calls. Governor ground truth: at this tier BP == equity; concurrent wall =
  live cash number; proceeds-reuse active. Account-flip build can proceed on real numbers
  (still gated on its own kill-test + Auditor before any live order).

## 2026-08-10 ~09:15 — WEBULL PDT PROTECTION TOGGLED OFF (Marcos, in-app) + probe sharpened
- App had shipped legacy PDT UI: "3 day trades left" + PDT Protection ON (would BLOCK 4th
  opening transaction under $25k) — conflicting with API day_trades_left=UNLIMITED and the
  6/4/26 rule elimination. Marcos disabled the toggle; post-toggle text = no blocking, but
  stale copy still recites flag/EM-call under $25k.
- BROKER DESK PRE-TRIAL PROBE (hardened): live day one, BEFORE size: 4+ tiny round trips,
  then 24h watch for any flag/EM-call notice. Optional belt+suspenders: Marcos may ask Webull
  support in writing whether sub-$25k PDT flagging survives post-6/4. Never trust UI or API
  over an executed order.

## 2026-08-10 09:06 — morning automation check (all green + 1 new fail-soft defect)
- Sweep DEDUP FIX PROVEN LIVE: morning run new=0 (was ~35/run for days); errors_final=1 = the
  known no-caption short; UPDATE video not yet posted (retry loop hunting until 11:00).
- Reader producing (EPOW TAKE 09:05 posted); capture healthy (304 series, 126 trade subs,
  vwap seeded); bot stable since 07:54, 26 watched incl. all 3 Kev names.
- NEW DEFECT (post-close fix): Alpaca Data actives screener NameError '_ureq' not defined —
  fail-soft (scanner source carries discovery); redundant leg down.

## 2026-08-10 ~09:22 — WEBULL SUPPORT INQUIRY SENT (Marcos)
- Three-part written question submitted to Webull re: margin CUV5U3M6 post-6/4 PDT status:
  (1) any day-trade limit under $25k with protection toggle off? (2) any flag/EM-call/
  restriction on a 4th day trade? (3) is the "3 day trades left" UI stale? Their written answer
  = authoritative record for the Broker Desk; day-one 4-trade probe stays on the checklist
  regardless (executed orders outrank support reps).

## 2026-08-10 ~10:2x — EMERGENCY RTH PUSH (Marcos: "push it") — the _he_day crash loop
- 13 boots by 10:04 (03:56 clean, 07:19-07:54 x8, 09:31, 09:59, 10:01, 10:04). ROOT CAUSE: MY
  #35 rebuild calls _he_day.clear() at boot; with no hidden fills to replay the dict stays EMPTY;
  first hidden-lane fire evaluation hits _he_day["d"] -> KeyError -> process death -> Railway
  restart -> clear again. First exposed by premarket window (07:00) running the hidden path.
- Crash cycles were degrading monitors (INHD quote thread "cannot schedule new futures after
  shutdown" -> bar-close fallback) with 3 open positions on halt-heavy tape.
- FIX: reseed {"d":None,"PRE":0,"RTH":0} after clear + defensive .get at the fire site. 3
  executed pins; suite exit-0. PUSH WITH OPEN POSITIONS on Marcos's explicit call — rationale:
  restarts already occurring every few min; resume path proven ~10x live today (trade_resumed
  rows, zero orphans/force-closes). Silver lining: #35 painless-restarts received its live
  gauntlet involuntarily and PASSED every cycle.

## 2026-08-10 ~11:00 — HALT-STACK DIRECTIVE (Marcos) + the XHLD $50 lesson
- XHLD = the day's mission-sized runner (~$50 offered on the caught trade): tiers banked ~+$25,
  resumption spike to 4.68 unbanked (3-min trail vs a 3-min spike — 5s crown-runner trail goes
  to tonight's docket with this number attached), remainder shredded by restart churn.
- Marcos directive verbatim: halt entry ≠ ignition entry — two different animals, two entries,
  "double exposure be damned." Cross-lane halt_ladder stacking becomes legal AFTER tonight's
  per-trade-id plumbing (registry/records/stops/store) — today proved ticker-keyed slots corrupt
  books when two positions share a name. Same-lane dupes stay banned; live BP wall still rules.

## 2026-08-10 ~11:05 — FULL-WARM BOOT ordered (Marcos: "Restarts should not affect anything")
- The data always existed: capture services never restart with the bot; every 5s/10s/1m bar is
  on the volume. The bot boots/adopts COLD anyway (3-min warmups, immature anchors, stale
  suppression). 8/6's deep-first-pass rehydrate covered only vwap_reclaim/ignition — half a
  sandwich; flat_top aggregates, hidden anchor, session highs, velocity state still amnesiac.
- TONIGHT (4th pillar of the plumbing batch): seed EVERY consumer from the archive at boot AND
  at roster-add. ACCEPTANCE (trial gate, with kill-under-fire): mid-session kill in paper ->
  within one cycle, every machine fire-eligible with correct state; same for a 10am add.

## 2026-08-10 ~11:4x — FIRST CONVENING UNDER THE LAW: Blast Radius Auditor on the 16:05 batch
- ARTIFACT (subagent, separate context): 9 findings — 3 BLOCKER / 3 WARN / 3 NOTE — on a batch
  the rig had already passed. Proof of Marcos's order in one sitting.
- F1 BLOCKER perimeter-token leak on dupe reject -> token now consumed FIRST. F2 BLOCKER both
  layers fail-open on the same dependency (screener) that caused the incident -> probe failure
  INSIDE the race window now fail-CLOSED + dup_probe_failed row. F4 WARN window anchored to
  _BOOT_TS -> now anchored to recovery COMPLETION (_RECOVERY_DONE_TS). F5 WARN _he_day direct
  indexes hardened to .get. F8 WARN barrier fail-open now writes a durable barrier_failopen row.
- F3 BLOCKER (standing order): HALT-STACK does NOT ship until per-trade-id keying lands —
  ticker-keyed registry/store would corrupt books BY DESIGN under an intentional second position.
  F9 NOTE: the resumed-monitor freeze (dead quote executor) has NO fix in the 16:05 batch — it
  is tonight's pillar, and the 16:05 deploy is NOT billed as fixing it.
- Fixes applied + pins updated to audited design; suite exit-0. 16:05 batch is now AUDITED.

## 2026-08-10 ~12:2x — REGISTERED FOR TUESDAY-NIGHT DISCUSSION (Marcos: "log this"):
## THE WYHG COMPOSITION PROBLEM — death by a thousand correct refusals
- WYHG = the day's biggest sustained runner (5.90 -> ~12.70, +115% while watched) and the bot
  took ZERO trades. Five separate, individually-defensible refusals stacked: flat_top
  "broke_not_flat" (true — it was vertical); ORB pullback timeout (true); crown arrived
  11:09:24 = mid-vertical (meritocracy rule working as designed); halt arm DEAD on lagged 5s
  store (my defect, flipped to 10s at 12:14); break-side reject 11:26 @ $9.98 (+3.96% above
  the $9.60 mark, the 1% tolerance shipped Friday) — after which it ran +27.3% (with a -8.4%
  flush first — entry would have had to survive $9.14).
- SYSTEM-LEVEL refused-strength case for the Ombudsman: every officer correct, the COMPOSITION
  blind. REGISTERED QUESTION (not a proposal — needs the era replay first): does the stack need
  a "board-leader override" — a name up 100%+ with proven violence gets the tape lanes' full
  attention regardless of gate composition ("fresher eyes not blindfolds" applied to gate
  STACKS, not just maps)?
- Context prices for the sitting: RDGT same-gate reject same hour = clean save (-20.6%); the
  break-side gate is not simply wrong — the composition question is the discussion.

## 2026-08-10 addendum — WYHG: the CHARTS' half of the composition case (Cartographer)
- Reader cadence was GOOD: v6 11:22 (brk 9.60) -> v7/v8 11:27/28 (9.98) -> v9 11:36 (11.99) ->
  v10 11:38 — 2-6 min re-reads; PCLA's 16-min latency did NOT repeat.
- Every read = BLUE-SKY summit map, verdict SKIP: "structureless parabola, no shelf" — the
  charts voted stand-aside BY DOCTRINE (maps-describe law: no invented rungs on no structure).
- The 11:26:48 break-side reject (entry 9.98 vs brk 9.60) lost a 62-SECOND race to v7's 9.98
  update — freshness contract behaved as tuned (4-min/4% = fresh) yet was 1 min slow for this
  tape. Data point, not defect claim.
- REFRAME for Tuesday: chart lanes correctly stood aside; the TAPE lanes (which trade through
  chart verdicts by the 7/26 design) were supposed to carry blue-sky names — and the one tape
  lane built for this exact vertical (halt arm) was dead on lagged data. The composition may
  have been sound with a single dead component. Both readings on the table.

## 2026-08-10 addendum 2 — TNON: the matched pair (Marcos: "TNON too")
- TNON mirror case: reads 10:47/10:51/10:54/10:56 (3-4 min cadence), summit map 6.13, exhausted
  10:46; ceiling refused the 10:53 dip_rip fire @ 6.47 (past all targets) -> price collapsed
  -25% to 4.85, chopping ~5.1-5.26 since. SAME chart posture as WYHG, opposite outcome.
- THE CONTROLLED PAIR for Tuesday: charts+ceiling identical; the distinguishing variable =
  WYHG's proven VIOLENCE (halts/crown/+100%) — tape-lane credentials — vs TNON's none. Argues
  the 7/26 design split (chart lanes defer to structure; tape lanes carry violence) is sound
  and the hole was ONE dead component (the lagged arm), not the philosophy. Discussion framed.

## 2026-08-10 addendum 3 — RDGT: the CROWN-ANCHOR hole (third composition specimen)
- RDGT: prior close ~1.15 -> collapsed to 0.73 -> ripped +64% off the session low through TWO
  upward halts (1.20) — but day-gain vs PRIOR CLOSE reads +4%, so it can never crown, so the
  crowns-only halt arm was blind BY DESIGN (the "vertical-regime entries = named open hole"
  from the 8/5 leader charter, now priced live). Chart lane fired 2x, ceiling correctly stood
  down on a 35-min-stale exhausted map (reader owes re-read — PCLA latency class again).
  diprip_armed on the halt = resumption boarding still possible via tape lane.
- TUESDAY EXHIBIT SET complete: WYHG (sound composition, one dead component), TNON (correct
  refusal, saved -25%), RDGT (crown anchor measures gain from the wrong reference — session-low
  run + halt evidence invisible to prior-close day-gain). QUESTION REGISTERED: should crown
  credentials accept session-low-anchored runs + halt violence, not just prior-close day-gain?

## 2026-08-10 addendum 4 — RDGT'S RIDE (Marcos: "we missed this ride up!!!!"): the BENCH hole
- RDGT known at 03:56 (daily_loaded) then ZERO rows 07:12->12:02. The ride 0.73->1.21 (+64%)
  ran 11:49-12:10 with the name OFF-ROSTER (premarket -33% = rank-benched); re-admission at
  12:02 delivered it 80% done at 1.03 -> gates correctly judged a chase (breakside +6.5%,
  ceiling). The ride was UNSEEN, not refused.
- CONTRIBUTING DEFECT PROMOTED: Alpaca actives screener leg down since boot (NameError '_ureq')
  — the discovery-by-activity redundancy that surfaces benched names when they start printing.
  My 09:06 'fail-soft, not urgent' triage undercharged it; tonight's list, priced by this miss.
- FOUR-HOLE MISS LEDGER for Tuesday (Handicapper): SCKT never premarket-scanned; WYHG on-roster
  w/ dead arm; RDGT ride benched + discovery leg down; RDGT halt = crown anchor. One sentence:
  the day's violence kept happening on names the RANKING filed as uninteresting. CANDIDATE FIX
  (registered, kill-test first): velocity fast-track to roster — ±X% in Y min = watched now.

## 2026-08-10 — THE UNIFIED DIAGNOSIS (Marcos: "This latency issue is stealing money from us")
- Every miss today = a latency, priced: discovery->roster (RDGT benched thru +64%; SCKT till
  9:31), exhaustion->re-read (PCLA 16min; RDGT 35min stale thru halts; WYHG proves 2-6min is
  achievable), feed age (5s store 90-180s lag = dead arm all morning — costliest), boot->warm
  (minutes x17 restarts), violence->crown (WYHG crowned mid-vertical).
- STANDING DOCTRINE: every pipeline gets a LATENCY BUDGET + stamp + alarm. Feed max-age
  assertions (tonight); boot-to-warm = 0 via rehydration (tonight); discovery fast-track +
  actives-leg repair (tonight/Tuesday); re-read priority for stood-down names; crown latency
  graded (Steward, 3 specimens); Curator latency TILE — budgets watched like P&L, because they
  are P&L.

## 2026-08-10 — "BUT OUR SCANNER HAS IT!!!!" (Marcos) — the 6/23 two-scanner drift bills us
- The dashboard scanner (always-on, 5-min refresh, live move% rank) HAD RDGT on the board during
  the +64% ride while the bot's own internal scan kept it benched. Two independent scanners,
  drift flagged 6/23, "one shared definition" deferred since. Today it priced itself.
- TONIGHT (top of discovery section): bot CONSUMES the dashboard scanner board as a roster
  source — union into candidates every cycle, never replacement. The discovery redundancy
  already exists and already ranked every missed name today; it was never wired to the trader.
- Integrator's day-theme: 4th money-costing SEAM today (capture<->arm, recovery<->entries,
  resume<->records, scanner<->roster). Components pass tests; wiring fails days. Tonight = a
  wiring batch.

## 2026-08-10 — ROSTER ARCHITECTURE ORDER (Marcos): THE BOARD IS THE UNIVERSE
- Not union: candidate roster = dashboard Webull scanner board (Kev-standard filters) +
  Kev-sheet force-adds, PERIOD. Bot-internal scan retired as a name source (logged cross-check
  at most). "We find the winners yet you confuse the bot with these other names that don't
  fit profile." Tonight's wiring implements THIS; ship carries a same-night counterfactual:
  today's board-admitted vs internal-scan-admitted names, graded against what actually ran
  (board purity vs internal noise, in dollars where tradeable).

## 2026-08-10 — THE "WEBULL BOTTLENECK" WAS A BROWSER TIMER (Marcos ordered reinvestigation)
- Measured (code-verified): the 5-min scanner refresh = client-side JS auto-refresh (screener_app
  :928). /api/scan is on-demand; one scan ≈ 2 Webull screener calls (gainers + most_active)
  = ~1% of the 300/min REST budget at 30s cadence. NOT a vendor wall — an inherited UI setting
  treated as physics. Feed Engineer ledger: assumed wall, now demolished.
- [UNVERIFIED until live]: screener endpoints' own rate limits — only 429s answer.
- TONIGHT'S DESIGN: bot pulls scan server-side every 60s (discovery floor 5min -> ~60-90s);
  server caches ~30s (browser+bot never double-spend); 429 counters watch screener calls;
  cadence AUTO-BACKS-OFF on any 429 (can never compromise the system — self-throttles + logs).
  Clean day at 60s -> grade 30s. Board-is-the-universe wiring rides the same cadence.

## 2026-08-10 — WEBULL WRITTEN CONFIRMATION (Broker Desk artifact, via Marcos)
- Webull Support (Chase), in writing: "your account is not subject to Pattern Day Trader
  rules." The stale "3 day trades left" UI + legacy PDT text = OLD APP VERSION; updating the
  app surfaces the new margin framework. Closes the PDT question authoritatively: unlimited
  day trades on margin CUV5U3M6 at any equity. Day-one micro-probe (4+ tiny round trips)
  stays on the checklist as executed-order confirmation, now a formality not an investigation.
- Marcos action item (his side): update the Webull app to see the new margin framework.

## 2026-08-10 ~13:1x — SCKT 13:06 halt MISSED by the live arm: MODEL mismatch (not plumbing)
- Post-flip arm on live 10s watched crowned SCKT grind 1.42->1.98 into a 13:06 halt; our prox
  math (20% nominal band, 5-min mean-of-closes ref) scored ~0.3 at the halt moment. The
  exchange's real tripwire disagreed with our replica. EVENING ITEM: calibrate band/threshold
  EMPIRICALLY against today's 8+ observed halts w/ full tape (rulebook tiers -> fitted values,
  kill-tested). Era rulebook recall was 57%; live today = worse.
- FAIL-SOFT CORPSE #2 (re-verification specimen): reader's ZZREADERBEAT aliveness row used
  `requests` — never imported — NameError swallowed EVERY cycle since ship. The alive-check was
  dead. Fixed to native _post. (Corpse #1 = actives screener '_ureq'.)

## 2026-08-10 ~13:15 — RESCAN WASTE QUANTIFIED (Marcos: "wasted time looking at huge floats")
- Internal rescan: ~98 candidates x ~0.6s SEQUENTIAL float checks = ~60s of every 5-min cycle
  interrogating names the board's filters would never admit; STKH "3863M float" units-bug lie
  visible live again. Board-is-the-universe funnel RETIRES the whole path (float checks incl.).
- EVENING VERIFICATION (before the funnel ships): does the DASHBOARD scanner share the float
  source/units bug? If STKH reads 3.86B there too, that's why it never made Marcos's board —
  the source of record itself is corrupted. Scanner float for STKH vs truth, tonight, first.

## 2026-08-10 ~14:0x — SECOND AUDIT ARTIFACT: 14 findings on the 16:05 batch, ALL BLOCKERS FIXED
- The Auditor found 6 BLOCKERS in code I had suite-green: (F1) backfill timezone wrong — archive
  bars would land 4h in the FUTURE, poisoning staleness/halt-suspect math on every merged feed;
  (F2) reader passive section dead on arrival (NameError -> the whole freshness trigger never
  ran); (F3) clears were ticker-wide — first exit would wipe a same-name sibling's recovery row;
  (F4) abort channel still ticker-keyed — watchdog on trade A would strand same-name trade B;
  (F5) fail-closed dupe probe was dead code (loader can't return None); (F6) funnel would have
  blinded the reader for non-Kev names (read-list never posted) + degraded ranking.
- WARNs fixed too: resume-record clears only on confirmed post (F8); id minted for id-less
  orphans (F9); crash-fallback id-keyed + popped (F10); pool wedge detector — 6 consecutive
  timeouts rebuilds (F11); abort-set sweep (F12); past_map per-map-version dedup (F13); funnel
  8s timeout + last-good cache (F14). ACCEPTED LOSS documented (F7): easy_to_borrow/HTB weighting
  not on the board feed — ranking simplifies until the scanner exports it (queued).
- Suite ALL GREEN (exit-0) on the audited design. Artifact = this entry + the subagent report.
  Two audits today = 20 findings, 9 blockers, all pre-ship. The standing room pays.

## 2026-08-10 ~14:2x — ARM CALIBRATION STUDY (arm_calibration_20260810 + era re-run at 0.6)
- Classifier lesson first: half of today's "up-halts" were DOWN-halts reopening higher (negative
  vel into the gap) — filtered to 9 TRUE up-halts.
- Live recall: prox>=0.7 catches 6/9; >=0.6 catches 8/9 (WYHG 11:19 @0.65, RDGT 12:28 @0.69 just
  under the bar). SCKT grind-halts (prox 0.33) = likely unarmable class -> dip_rip's job.
- Era kill-test at 0.6: 143 arms +$632.52 mean +$4.42 worst -$143.93 (passes BUILD bar) vs 0.7's
  110/+$840.93/+$7.64. Trade-off: +22pts recall, -$208 era, marginal arms -$6.30 avg.
- NO CHANGE TONIGHT: the 0.6-0.7 cohort is ALREADY measured live by the early-arm shadow band
  (0.4-0.7). TUESDAY decides from study + era + 2 days of unseen shadow rows. (The confirm-gate
  lesson applied: thresholds move on unseen evidence, not warm studies.)

## 2026-08-10 ~14:45 — FLOAT BUG DIAGNOSED: vendor stale data, not our units
- Ground truth run: yfinance STKH floatShares=3,862,661,795 vs sharesOutstanding=591,689 —
  PRE-reverse-split float served beside POST-split outstanding. Both services trusted
  floatShares primary -> filtered on a number ~6,500x too large. True float ~0.59M = ULTRA
  small — the best possible profile match, rejected as its opposite.
- TONIGHT'S FIX (both services): float = min(floatShares, sharesOutstanding) when both present
  (float > outstanding is a data impossibility); flag float_src="so-capped"; STKH = executed
  test case. Ships in the post-close mini-batch with its own audit.
- XHLD correction entry POSTED (+$25.43, full provenance). Honest day book: +$58.90 recorded.

## 2026-08-10 ~15:1x — MISS #5: THH (mapless newcomer class)
- THH crowned + watched; flat_top fired 2x (13:35 @2.68, 15:04 @3.80 post-halt); BOTH blocked by
  chart gate "no_marked_level" — the reader NEVER read it (outside top-20 move% until the
  vertical). One-candle vertical 2.70->3.80 into a 14:59 halt = too fast for pre-halt arming;
  dip_rip couldn't board (non-sheet name).
- Fixes ALREADY STAGED tonight: board-funnel read-list + 60s cadence + reader priority = a
  mapped THH at 13:35. REGISTERED QUESTION (Tuesday): resumption boarding for one-candle
  verticals on NON-sheet names (dip_rip scope).
- MISS TAXONOMY today, complete: (1) SCKT premarket-scan hole, (2) WYHG dead arm, (3) RDGT
  bench+discovery, (4) RDGT crown anchor, (5) THH mapless newcomer. Five causes, five named
  fixes/questions — the day's tuition itemized.

## 2026-08-10 16:3x — THE RESTART-PROOF BATCH SHIPPED (all four services, flat book verified)
- Shipped after THREE audit passes (2 full + 1 focused = 24 findings, 10 blockers, all fixed
  pre-ship): Pillar A self-healing quote plumbing (capped init, dead-pool rebuild, wedge
  detector); Pillar B archive-backfill warm boots (UTC-corrected); Pillar C per-trade-id books
  (registry/store/records/aborts/clears) + resumed-exit recording; boot barrier + fail-closed
  dupe guard (store outage = refuse in window); reader latency fixes (60s probes, stood-down
  uncapped + past_map dedup, 3-min reread_overdue alarm, live ZZREADERBEAT); BOARD FUNNEL (the
  board is the universe, legacy-shape, read-list + move% preserved, last-good cache, kill
  switch); float sanity caps x3 sites; _ureq alias; crown stamps live end-to-end; PRE header
  ET-scoped. Suite ALL GREEN at ship.
- Mini-audit artifact: crown-stamp fix was DEAD CODE as first written (sources never populated)
  — third audit catch of the day. All three source dicts now carry entry_crown.
- REMAINING TONIGHT: hot-5s endpoint (capture service) for arm/seam/confirm consumers; scanner
  60s server-side pull cadence + cache; kill-under-fire + warm-boot drills THIS WEEK = trial
  gates; officers' debrief.

## 2026-08-10 ~18:0x — EVENING BATCH 2 SHIPPED (hot-5s + cadence), 4th audit of the day
- Audit #4: NO blockers (first clean-design pass) + 3 WARNs fixed pre-ship: scan-cache TTL
  30->90s (30s never served the 60s bot cadence — would have tripled Webull scan load), hot5
  per-symbol 60s backoff (dead capture must not stack 2.5s timeouts into every cycle), rescan
  re-add setdefault (#81 amnesia class). Seam's 90% gate stamped hi_window=60m (drift documented
  for Friday grading).
- LIVE NOW: /hot5 on capture (in-memory 5s, closed buckets); _alp5_feed hot-primary w/ loud
  archive fallback + backoff; confirm/seam/arm all through ONE choke point; 60s rescans; 90s
  scan cache. The seam program's instrument is finally honest — H2 grading restarts tomorrow
  on live tape.
- Day's audit total: 4 convenings, 27 findings, 10 blockers, zero shipped.

## 2026-08-10 19:17 — EVENING RESTART DRILL: PASS (boot half)
- Deliberate kill on the rebuilt system: new container 19:17:06 ET, clean boot, no traceback,
  no recovery_store_unreachable, no barrier_failopen, flat book untouched, correct sleep-until-
  wake. Boot half of "restart loses nothing" PROVEN. Note: evening boots write no boot_config
  row (stamp lives on the trading path) — durable boot evidence is trading-hours-only.
- REMAINING PROOF: tomorrow's mid-session kill-under-fire drill (live DRY position + fires
  landing) = the full claim + trial gate. Warm-boot acceptance graded on the same drill.

## 2026-08-10 eve — TUESDAY 8/11 PLAN (Marcos on the road from 10:00, laptop bagged)
- Marcos: dashboard-only monitoring from the phone; no road decisions needed. This session
  works the MORNING SHIFT (03:55 boot verify, 09:02 sweep check, open watch, status brief
  before 10:00), then sleeps with the laptop. Trading runs fully autonomous on Railway all day
  (evidence day 2: halt lane, first live day of hot-5s seam/arm, board funnel, 60s rescans).
- Mid-session KILL-UNDER-FIRE drill: run before 10:00 only if a DRY position + hot tape align;
  otherwise WEDNESDAY (no cost to waiting). Verdict sitting stays TUESDAY NIGHT when he's back
  at this thread — one thread, one set of books, as ordered.

## 2026-08-10 night — SHIP: DUTY OFFICER PORTAL (task #44)
- /duty on the dashboard: phone chat; Claude (sonnet-4-6) answers from live books (open trades,
  today's trades w/ $ net, today's decision rows, ledger tail). READ-ONLY v1 — no actions; anything
  decision-shaped tagged [FOR THE EVENING SITTING]. Every exchange -> /data/duty_log.jsonl,
  ingested into the main thread each evening (books-first: same books, different door).
- Auth: DUTY_SECRET env (strong random, set tonight); key entered once on phone, kept in
  localStorage. Auditor convening (Blast Radius, separate context): 3 BLOCKERS found+fixed pre-ship
  (trade-store keys date/entry/exit not timestamp; decision rows forwarded w/ real writer keys
  incl. status; DASHBOARD_SECRET unset -> guessable default, cured by DUTY_SECRET). Warnings noted:
  ledger tail frozen at deploy time; duty_log durable on /data (volume verified).
- Officers touched: Blast Radius Auditor (convened, artifact = audit report), Dashboard Curator
  (portal + header link), Pit Crew Chief (after-hours deploy, flat book verified in-turn: open_trades=[]).
- LIVE VERIFY (22:02 ET): /duty 200; wrong-key 401; real question answered from the store
  ("+$56.93 | 14 trades" — the store's own numbers, cited); exchange landed in /data/duty_log.jsonl.
  SHIPPED + PROVEN. Note: store net $56.93 vs main-thread true book $58.90 = $1.97 runner-leg
  display-correction delta (correction layer lives in the main thread, not the raw store) — known,
  acceptable for road answers.
- CORRECTION to the note above: no display-correction delta. Reconciled against /api/trades:
  14 rows sum EXACTLY $56.93 (incl. XHLD +$25.43 correction entry). The main thread's "+$58.90"
  was a mid-afternoon figure; two later THH trades (+$3.60, -$5.57) net -$1.97. Monday final
  book = +$56.93. The Duty Officer's first live answer was RIGHT and the main thread was stale.

## 2026-08-10 night — FIX: iOS light mode "scroll part stays dark"
- Cause: light mode = invert filter on the root; iOS Safari composites touch-scroll containers
  (.table-wrap dashboard+scanner, .tw premarket) and the sticky header into separate layers the
  root filter never reaches -> exactly the scrolling tables stayed dark on the phone.
- Fix (THEME_SNIPPET, central to all pages): @supports(-webkit-touch-callout:none) — iOS-only —
  gives each composited layer its own invert filter; sticky header demoted to normal flow in
  light mode. Desktop verified unaffected post-deploy (screenshot, full invert, no double-invert).
- Deployed after hours, book flat (open_trades=[] in-turn). REMAINING CHECK: Marcos's phone —
  I cannot run real iOS Safari from here; his eyes are the verification.
- iOS light-mode PASS 2 (Marcos's phone screenshot: filtered container only covered the
  initially-visible slice; scrolled-in columns dark): filter moved onto the TABLES (full scroll
  width); .table-wrap/.tw containers get literal light colors; #rejectStrip/#shadowStrip (bare
  divs whose wide tables panned the page) made scroll containers + same table filter. Deployed
  (book flat in-turn), served CSS verified live; desktop light mode re-checked (top + mid-page
  render correct; browser-pane blank-after-scroll screenshots occurred in BOTH themes incl.
  pre-pass-2 = pane renderer flake, not a regression). Final verify = Marcos's phone.
- iOS light-mode PASS 3 (retreat to verified state): phone screenshot 2 proved Safari's root
  filter reaches SOME tables (.table-wrap trade history — my extra filter double-inverted it
  dark) and not others (rejects strip — my filter fixed it) on the SAME page = compositing
  heuristics, not a rule. Pass 3: strips keep their own filter (both proven improved), .table-wrap
  tables returned to root-filter handling (undo regression). Shadow-lanes header row stays a
  dark band on iOS — readable, unfixed tonight. PROPER FIX registered for the Curator queue:
  real literal light theme (CSS variables), no invert-filter hack — daytime build, not 23:40.

## 2026-08-11 ~00:45 ET — SHIP: real light theme (CSS variables), invert-filter hack retired
- The Curator-queue item from 8/10 pass 3. THEME_SNIPPET now defines the full dark palette as
  CSS custom properties on :root (exact old hexes — dark mode is byte-identical) with a light
  override under html[data-theme=light]; color-scheme swaps with the theme. The invert(.93)
  hue-rotate filter and the whole iOS @supports patch stack are DELETED — no filter anywhere,
  so iOS compositing heuristics can no longer split the page into light and dark layers.
- Sweep: 283 hex literals -> var(--x) across / (HTML), /dashboard, /day2, /premarket builder,
  the Tale page, Python-side gate_color/bcol, and JS-built innerHTML (loadRejects/loadShadow,
  live badge, trade panel). DUTY_HTML untouched (unthemed). Chart.js canvas can't take var():
  colors resolve via getComputedStyle at render time; toggle dispatches 'mtheme-change' and the
  equity chart re-renders. Toggle button + localStorage 'mtheme' unchanged.
- Blast Radius Auditor (separate context) on the diff: verdict SHIP-WITH-FIXES, zero
  trading-logic impact (gate/veto logic byte-identical, no route/data changes, Jinja clean,
  node --check passed on all inline scripts). Both findings fixed pre-ship: (1) #d2992255
  alpha hex became invalid var(--yellow)55 -> color-mix(); (2) deleted iOS block was the only
  overflow-x:auto on #rejectStrip/#shadowStrip -> restored in base CSS.
- Deploy gates: 00:29-00:35 ET (outside RTH), open_trades=[] curled in-turn before AND after
  deploy. railway up (dashboard/ scanner); new CSS live ~80s later. Verified live: all 4 pages
  200 with var(--) served and zero invert() remnants; /dashboard light mode eyeballed with real
  data (balance banner, stat cards, P&L calendar tints, chart axis re-render, ledger table).
- Commits 55a572d + 7165205 (main fast-forwarded from claude/funny-bell-adf49d).
- REMAINING CHECK: Marcos's phone — but there is no filter left to composite, so the iOS
  failure mode from 8/10 is structurally gone, not patched around.

## 2026-08-11 ~01:35 — LATE TUESDAY SHEET RECOVERED FROM TIKTOK (Marcos's link)
- Kev posted the TOP-3 LATE (new-car night) and on TIKTOK (@momentum.official video
  7672612324519333133, ~00:30 ET) — a platform the sweep does NOT watch (YouTube-only).
  Without Marcos's link, tonight's sheet would have been missed entirely (09:02 sweep included).
- Extraction: yt-dlp pulled the video's own captions (full transcript, saved to
  data/kev/tiktok/7672612324519333133_TOP3_TUESDAY_20260811.vtt); hand-parsed levels posted
  through post_sheet() itself so ALL guards ran (symbol-real, price fingerprint, merge-only).
  POSTED 3 names, store verified live: SCKT 2.50/2.20 -> 4,5 · WAFU 2.10 day-2 -> 3,4,5 ·
  MTEN 1.78/1.60 -> 2,3,4,5 (his "most explosive"; SCKT = his 230% Mon squeeze, MTEN his +30%).
- PIPELINE HOLE (Feed Engineer + Kev Librarian): Kev cross-posts to TikTok; late/one-off sheets
  may exist ONLY there. Fix candidate for the queue: add TikTok tab to the sweep (yt-dlp handles
  captions cleanly, proven tonight). Officers touched: Kev Librarian (recovery+corpus), Feed
  Engineer (vendor-surface gap), Handicapper (three fresh names for the open).

## 2026-08-11 ~01:50 — KEV LESSON: SCKT 5-second vertical (TikTok war story, Marcos's link)
- Kev's Monday SCKT trade, his words: entry $1.20 on "a simple pullback off of VWAP," watching
  "the break of the high of the day"; then $1.20 -> $3.97 in ~2-5 SECONDS ("that's not a glitch");
  he SOLD NOTHING into the spike (thought it was fake) and traded out to ~$2.50; "people were up
  five grand in seconds. 21R day in seconds"; closing doctrine: "whenever the opportunity is
  there you take your shot."
- What this feeds (officers): [Reclaim Architect] entry archetype = VWAP-pullback + HOD-break
  watch, his canonical shape, again. [Rocket Rider / Tuesday sitting] the VERTICAL-REGIME entry
  hole is not hypothetical — the month's biggest trade WAS a 5s vertical; our 5s/1s capture and
  halt/seam lanes hunt exactly this. [Trade Manager / Execution Surgeon] even KEV captured only
  ~$1.30 of the $2.77 offered — offered-vs-captured on verticals is the frontier, not a bot
  defect. [REGISTERED QUESTION — Execution Surgeon]: our off-tape exit guard (_verify_exit_px)
  would a REAL 2-second 3.97 print pass it, or would we refuse a legitimate vertical exit?
  Needs a replay check against Monday's SCKT 5s/1s tape before the trial.
- Transcript archived: data/kev/tiktok/7672424505150606605_SCKT_war_story_20260810.vtt

## 2026-08-11 ~02:00 — THREE MORE KEV TIKTOK LESSONS (Marcos's links) — heavy doctrine night
1) SCKT FULL BREAKDOWN (7672464964568796430): timeline = AUD 8:00am VWAP-pullback base hit ->
   LRHC small bases -> 9:00am SCKT squeeze .30->1.00 on APPLE-scanner distribution NEWS -> waited
   for "a one minute pullback to VWAP," punched 1.24 for HOD-break over 1.34 -> 1.20->3.97 vertical
   in <5s -> managed by "raising stops to 1-minute lows," rode to ~2.50; exited all "before the
   bell because I don't want to get stuck in the halty mess"; after the open the name "turned into
   a disaster." ==> [PREMARKET EVIDENCE for Tuesday's PRE sitting]: Kev's biggest trade of the
   month was ENTIRELY premarket (8:00-9:25 arc), and he deliberately FLATTENED BEFORE 9:30 —
   matching our PRE 07:00-9:25-flatten shape exactly. Also: NEWS was the fuel (catalyst awareness
   = named open hole). [Reclaim Architect] entry = 1-min VWAP pullback + HOD break, again.
2) MTEN HALT-BAND PLAY (7672469812320242957): his live halt-lane doctrine in sequence — "need to
   see the halt band get RAISED," "1.41/1.48 are the new halt levels. WE HAVE DISTANCE NOW. That
   is KEY," HALF SIZE for the break, re-entry off VWAP pullback, full exit on "topping tail
   rejection off the high" before the reversal. ==> [Halt lane/Tuesday]: distance-to-halt-band as
   an entry CONDITION and band-raise as the arm trigger — direct spec language for our arm; our
   half-size crown-lane sizing matches his; topping-tail = an exit trigger we don't model.
3) SCKT LIVE CLIP (7672476799023992077): "I got a lot filled at 1.60, but I got NOTHING FILLED
   at 2 or 3 or 4" during the vertical. ==> [Wind Tunnel/Execution Surgeon — TRIAL-CRITICAL]:
   in a real 5s vertical, sell orders through the move DON'T FILL; DRY_RUN's fill assumptions on
   verticals are optimistic by construction. Before the $1,000 trial: stress the sim's fill model
   against Monday's SCKT 1s/5s tape; expect capture-rate haircut on vertical exits.
- All transcripts archived under data/kev/tiktok/. Officers touched: Kev Librarian, Reclaim
  Architect, Rocket Rider, Halt lane owners, Wind Tunnel, Execution Surgeon, Opening Bell (PRE).

## 2026-08-11 ~16:15 — GHOST OPEN-TRADES: FIXED, CLEANED, PINNED (task #46)
- Marcos flagged "dead open trades blocking business." Truth: 8 GHOST store rows (trades closed
  + recorded; rows never cleared). Trading was NOT blocked today — bot book "positions now 0
  (peak 4)", 29 trades, re-entered the ghost tickers repeatedly. Display + boot-risk defect only.
- ROOT CAUSE (my Sunday per-trade-id ship, incomplete): monitor-loop _save_open_trade lacked
  trade_id -> second ticker-keyed row per trade; id-bearing exit clear removed only the id row.
  FIX: trade_id stamped on monitor posts + clear endpoint falls back to id-LESS same-ticker rows
  (sibling-safe). 4 rig pins, suite ALL GREEN exit 0. Auditor convened: GO, no blockers.
- SEQUENCING ERROR (mine, owned): deployed the BOT before purging; its boot force-recorded all
  8 ghosts as "RECOVERED after restart" = 8 duplicate P&L records (book briefly 37/+$137.52;
  WAFU dupe +$7.44 = frozen mid-trade state, NOT its real +$16.51 exit — deleted-records payload
  is untrustworthy as audit copies, per auditor warning). Auditor W2 predicted exactly this.
- CLEANUP: new POST /api/trades/delete (predicate + expect-abort + returns records; 3 pins;
  second auditor pass GO w/ conditions honored: store verified EMPTY pre-delete, delete belted
  with all 8 tickers + expect=8). Deleted exactly 8. FINAL BOOK: 29 trades net +$104.62
  (1-cent float-rounding vs bot's session print +$104.63). Zero RECOVERED-today records remain.
- Follow-ups queued: #47 vacuous id-clear verify (the silent hole that let ghosts accumulate);
  auditor W1 (orphan re-key strands old ticker row) noted in #47.
- Officers: Blast Radius Auditor (2 convenings, verdicts in-transcript), Pit Crew Chief,
  Systems Quant, Statistician (book corrected + traced).
- BOOK SPLIT CORRECTION (Marcos's catch — RTH official, PRE separate, per 8/4 law):
  Tuesday 8/11 OFFICIAL RTH: +$58.36 on 24 trades. PRE (own line): +$46.26 on 5 trades
  (PLAG +2.38; WXM +26.84/-1.03/+1.76/+16.31 incl. 9:25 flatten). All 29 records
  entry_session-stamped, zero unstamped. The +$104.62 figure = blended, not the headline.

## 2026-08-11 EOD — MISS AUDIT (all 194 reject rows vs post-reject tape, timing-verified)
- GATE MISSES (real blocks that ran): PLAG backside_reject 12:39 @2.83 -> +141% to 6.81 (15:35);
  stale map compounding ("ORB pullback to $1.17", base-not-flat) — vertical-regime + stale-anchor
  class (RDGT cousin); morning legs banked +$62 so partial-catch. STKH daygain_reject 06:48 @3.13
  -> +51% to 4.75 (14:30), no lane fired all day. Daygain-refused runner pile: GRI +31%, TDIC +27%,
  VEEE +27% — Ombudsman hearing (morning-snapshot bias: floor refuses pre-proof).
- TRIGGER MISSES (never blocked, never fired): QMCO +34%, JWEL +30%, XHLD +29% — lane coverage Q.
- NOT misses: room_soft rows = log-only (refuted 7/26, verified at :7559/:7671); WXM = partial
  capture (+$44 PRE). Dollar frame at clip size: PLAG pm leg ~$60-120 forgone; STKH ~$30-60.
- To the TUESDAY SITTING: backside-gate re-grade (Friday item, now with the 2.83->6.81 exhibit),
  daygain-floor hearing (Ombudsman), stale-map re-read trigger for afternoon leaders (Cartographer),
  vertical-regime entry hole (standing).

## 2026-08-11 eve — REPLAYS RUN (Marcos: "run replays") — both gates re-graded on era SIP tape
Script: data/killtests/backside_daygain_regrade_20260811.py (+_RESULTS.txt). Era 8/5-8/11,
first-reject per ticker-day, 15:30-capped offers, coarse $ model ($200 clip, 35% capture of
>=8% offers, <4% = -$6 stop) — ranking tool, not a P&L promise.
- BACKSIDE (10 first-rejects): modeled +$155.53 forgone total. THE SPLIT: rejects whose name
  later RECLAIMED the reference high: n=2 (PLAG +124%, MSGY +42%), +$116 of the forgone;
  never-reclaimed: n=8, median offer +9.9%. AMENDMENT CANDIDATE (principled + surgical): the
  block's premise EXPIRES on reclaim of the stamped high — keeps all 8 saves, re-admits the 2
  runners at reclaim price. CAVEAT: n=2, both this hot week. Sitting decides.
- DAYGAIN (106 first-rejects): modeled +$582 forgone, 46/106 offered >=8%. STRUCTURAL FINDING —
  the floor is BLIND TO RED-TO-GREEN DAY-2: dg measured vs prior close stays NEGATIVE all day on
  a day-2 name even as it leads intraday (STKH dg=-27 -> +51%; XHLD dg=-34 -> +92%; YJ -25 ->
  +66%; AZI -10 -> +53%). Split: dg<0 pile n=25 = +$350 modeled (+$14.00/name, 20/25 offered
  >=8%) vs dg>=0 below-floor pile n=81 = +$232 (+$2.87/name). The dg<0 refusals are 5x richer
  per name — and it's EXACTLY Kev's WAFU day-2-confirm shape. AMENDMENT CANDIDATE: day-2
  red-to-green exemption (dg<0 + intraday leadership proof, e.g. VWAP reclaim / % off session
  low) — needs precise trigger spec + kill-test before ship. Board-exemption variant NOT
  historically testable (no dated board archive) -> START ARCHIVING the board daily (Curator).
- Crown question ANSWERED: PLAG WAS crowned (leader_armed 08:20). The afternoon failure was the
  MAP: 9 freshness_breach + 9 stale_swap_refused rows — freshness contract detected staleness
  all afternoon but no clean re-read landed. Cartographer + reader docket for the sitting.
- Officers: Strength Ombudsman (hearing evidence), Side Marshal (backside amendment), Wind
  Tunnel (model coarseness caveat), Cartographer (stale-map), Statistician (results ledgered).

## 2026-08-11 ~23:40 — SHIPPED: TIKTOK SHEET BACKSTOP (task #45)
- Sweep now has a TikTok leg (@momentum.official, his only account): SHORTS-FIRST semantics —
  YouTube stays primary; tiktok_pass runs ONLY when the YouTube pass finds no sheet (auditor W2:
  zero added latency on good nights); find_top3 checks shorts/ before tiktok/ (auditor BLOCKER:
  a caption-less TikTok stub could otherwise out-mtime and SHADOW the real YouTube sheet all
  night); caption-less posts stubbed after one retry (never re-error, never outrank); TikTok-id
  sheets skip the YouTube frame-vision check loudly (auditor W1). Covers night TOP-3 AND morning
  UPDATE (both run_once kinds).
- Proof chain: end-to-end EXECUTED locally (real listing 1.8s; captions via CLI-equivalent
  download path — bare extract_info returns EMPTY subs for TikTok, discovered + fixed; two
  passes converge 0/0; find_top3 matched the REAL Wednesday 8/12 TikTok sheet). Rig: pins incl.
  stub-shadowing + digit-guard, suite ALL GREEN exit 0. Auditor: 1 blocker + 3 warnings -> all
  addressed -> conditional GO satisfied. Deployed (book flat in-turn); IN-CONTAINER probe
  (/api/kev_tiktok_probe): ok=true, 6 titles from Railway's network, Wednesday sheet on top.
- Tonight's sheets: YouTube 20:06 sweep already posted Wednesday BOXL/DRMA/SCKT (posted=3);
  TikTok copy independently names the same three (grep cross-check) — two-source agreement.
- Officers: Kev Librarian + Feed Engineer (owners), Blast Radius Auditor (convened, blocker
  caught pre-ship), Pit Crew Chief (deploy), Integrator (find_top3 seam pinned).

## 2026-08-11 ~23:55 — SITTING, ITEM #1: BACKSIDE AMENDMENT WITHDRAWN (correction, mine)
- Code + rows check (PLAG: exactly 2 backside_rejects 12:39-12:40 @2.83/2.95 dd 26.5/23.4, then
  ZERO up the entire run; MSGY same shape): the gate's reference high is LIVE — dd shrinks as
  price climbs, block releases below dd=15, and at/above the reclaimed high dd<=0 can never
  block. "Expire on reclaim" is ALREADY the gate's behavior. My replay modeled entry-at-reject-
  price and OVERATTRIBUTED the runs to the gate; true gate cost today = the two blocked in-band
  tickets each on PLAG/MSGY. The 3.30->6.81 PLAG region was un-blocked and un-fired = stale map
  + trigger coverage (item #3), where the real dollars died.
- VERDICT: no ship on #1 (would have been a no-op). Friday band re-grade stands, now with the
  first real in-band forfeits on record vs the original -$8/trade bleed evidence.
- Law honored the hard way: check FIRST, ship second — the almost-shipped amendment died on a
  two-minute rows query. [[feedback_verify_before_asserting]]

## 2026-08-12 ~00:30 — SITTING ITEM #2: RED-TO-GREEN EXEMPTION REFUTED (two kill-tests, NO SHIP)
- v1 (exempt at refusal moment): refuted — refusals stamp EARLY, before intraday leadership can
  exist; at 15% off-low only 1/25 passes and every big winner sits still-blocked. No discrimination.
- v2 (standing exemption, entry at first qualifying minute — what a shipped gate would DO):
  refuted harder — 14 qualified, 10 STOPPED, 2 winners, NET -$71.20 (-$5.09/name); 10% bar:
  -$22.79. AUTOPSY: first-crossing of VWAP+off-low buys the local top of the early pop and eats
  the -6% stop; the pile's big offers (STKH's +51% came at 14:30, entry fired 06:57 -> stopped)
  are not capturable by this trigger. The $350 "forgone" was real OFFER, mirage CAPTURE.
- VERDICT: day-gain floor STAYS as-is. The day-2 red-to-green shape remains real (Kev's WAFU
  language) but the key is STRUCTURE (pullback-confirm, higher-low over VWAP — his actual
  entry), not a floor exemption at first crossing. Registered as a post-freeze lane-design
  hypothesis (Seam-Scientist-style specimen work), NOT a gate knob.
- Discipline note: idea survived one coarse offer-model, died on two capture-model kill-tests
  BEFORE touching live config. Files: daygain_red2green[_v2]_20260812.py + _RESULTS.
- Officers: Strength Ombudsman (hearing closed: floor acquitted on capturability), Wind Tunnel
  (model escalation coarse->bracket), Convexity Trader (mean-after-costs verdict), Statistician.

## 2026-08-11 ~23:55 — SITTING ITEM #3A SHIPPED: SUMMIT SANITY (the PLAG stale-map defect)
- DIAGNOSIS (rows + reader logs): re-reads v2/v3/v4 FIRED correctly on PLAG; vision returned the
  stale morning level (break 1.62, targets [1.62]) on a $3-6 tape; the 8/6 blue-sky branch
  posted the garbage 3x (assumed "exhausted" implies "target ~= summit", never verified) ->
  chart lanes read a $1.62 ceiling on a $4.50 stock and stood down through the +141% afternoon.
  NOTE my earlier misread, corrected: stale_swap_refused rows = the PRICE-source arbitration
  guard (rth_quote_trusted), NOT map re-reads; and the freshness_breach rows were MORNING rows.
- FIX (reader): _summit_sane — a blue-sky summit map posts only if max target >= 0.9x the live
  10s print (auditor-verified geometry: inside the branch tmax<=live always, so this rejects
  ONLY maps materially BELOW the tape — a true summit read during a pullback passes trivially);
  auditor W2 folded in: blue-sky now demands a REAL 10s print (no stale-chart meta fallback).
  Discards are loud, burn no budget, leave the map honestly sparse. Pinned; suite ALL GREEN;
  auditor GO (4th convening tonight); reader deployed (asleep until 08:50).
- FOLLOW-UPS ledgered: W1 — sanity-discard can hot-loop the 60s uncapped reread tier on an
  hours-stale vision (per-name backoff after N discards = candidate, tomorrow's window);
  #3B = vertical-regime lane hole registered as task #48 (specimen anatomy first, post-freeze).
- Officers: Cartographer (map truth), Systems Quant (branch geometry), Blast Radius Auditor
  (GO + 2 warnings, W2 shipped in-batch), Wind Tunnel n/a, Pit Crew Chief (reader-only deploy).

## 2026-08-11 ~23:50 — TUESDAY SITTING CLOSED: ALL VERDICTS RENDERED (Marcos: "agree on all")
1. HALT LANE: KEEP as configured (arm-only converts, crowns, half size, hot-5s). Evidence: MSGY
   11:28 arm prox 1.25 converted inside the crowned cluster; era +$840.93.
2. CONFIRM = STAMP, PERMANENT. Today's only convert stamped confirm5s=False — the refuted gate
   would have blocked it.
3. H1 COOLDOWN + H2 SIDE: probation EXTENDED TO FRIDAY (zero occurrences in 2 days, n=0).
4. EARLY-ARM: 0.7 stays live; 0.4-0.7 shadow band runs to FRIDAY re-grade (3 specimens today
   incl. PLAG 0.65 front_side 10:12 — 2.5h before its monster).
5. SEAM: shadow extended THROUGH FRIDAY; if Wednesday = 0 fires again, detector-liveness check
   required before market-didn't-offer is assumed.
6. PRE: 7:00-9:25 window KEPT AS-IS through trial week (Mon -$0.35, Tue +$46.26 + Kev's own
   premarket monster w/ pre-bell flatten; cap-6 + 9:25 flatten price the risk; PRE-KEV-only
   narrowing declined — would have refused today's WXM money). Revisit with full week's split.
7. DRILL: Wednesday ~13:30 ET kill-under-fire, mid-trade if a DRY position is open. Trial gate.
- Tomorrow's maintenance window queue: halt-convert entry_type stamp (attribution defect found
  tonight), W3 vacuous clear verify (#47), W1 reread backoff. No config changes tonight — all
  verdicts are keeps/extends.
- Sitting tally, full night: #1 withdrawn (gate already correct), #2 refuted (2 kill-tests),
  #3A shipped (summit sanity), #3B registered (#48), halt/seam/PRE/drill verdicts above.
  Officers: all standing rooms touched; 4 Auditor convenings tonight, artifacts in-transcript.

## 2026-08-12 ~00:20 — SHIPPED: REREAD LATENCY STAMPS (Marcos: "add the stamps")
- Every posted re-read now writes a durable reread_latency row: detect->posted secs (first-
  detect-wins across probe cycles, so cap-wait + queue time are IN the number), queue_pos,
  queue_len, trigger. Latency doctrine complete for the reader: budget question now answerable
  from rows forever, immune to log rotation. Read behavior byte-identical (bookkeeping only).
- Auditor GO (5th convening of the night): growth bounded + wiped by daily execv; re-fire
  semantics correct per map-version episode; nothing new can raise in the fire loop. Ledger
  note (auditor): queue_pos/len count pre-dedup entries — slight congestion overstatement,
  fine for distributions, don't use raw for Friday's parallel-reads case math.
- FRIDAY: grade the week's stamp distribution; if the single-file queue costs real minutes on
  busy tape, that row-set is the case for parallel reads. Pinned; suite ALL GREEN.

## 2026-08-12 00:15 — TUESDAY OFFICERS' DEBRIEF DELIVERED (full room, per standing law)
- Attribution: PRE +$46.26 (5) · First Hour +$58.91 (16) · 10:30+ -$0.55 (8). Lanes: hidden
  +$67.55/22, ignition +$43.05/6, flat_top -$5.98/1. Afternoon = non-participation not losses
  (#48 specimen). Crown stamps proven live (entry_crown=True on all 6 MSGY records). Full
  per-office reports in-transcript; flags: fill-model stress vs SCKT 1s tape owed this week,
  token re-mint ~8/23, seam liveness check if Wednesday=0, vision stale-chart source question.

## 2026-08-12 ~00:25 — OFFICE CHARTERED: THE QUARTERMASTER (11th; Marcos: "charter it")
- Sole custodian of all bars (1s/5s/10s/1m/daily), the ferry/warehouse, and backup+restore.
  Five duties: daily completeness vs roster; ferry integrity by counts+checksums; backup with
  scheduled RESTORE DRILLS (first act: audit the existing iCloud TradingBot folder — contents
  currently unverified); retention tiers w/ rotation-proof evidence; daily debrief line.
  Founded on the scars: premarket blackout -$624.50, 5s persist-lag, P&L store corruption,
  tonight's log-rotation evidence loss. Audits first; builds queue behind trial-critical work.

## 2026-08-12 ~00:35 — QUARTERMASTER FIRST AUDIT (executed; Marcos: "run the first audit")
- F1 HEADLINE: NO LIVE BACKUP EXISTS. iCloud TradingBot = frozen laptop mirror (bars stop 8/1,
  shorts 8/6, decisions 7/14; 1.6GB); laptop ferry cleanly retired (no cron/launchd). Trade
  records + decisions + kev store + character book live SOLELY on the Railway volume. Single
  point of failure for the entire evidentiary record.
- F2: resolution sampling (8/11, SCKT/PLAG/MSGY): 10S rich (2.6-4.7k bars), 1S rich (7-15.5k),
  ~ALP1M nearly empty (0/24/2) — design-or-defect check queued (backfill-seeded by design?).
- F3: hot5 probe 404 = wrong service URL (dashboard vs capture), corrected, no defect.
- RECOMMENDATION queued (build, post-trial-critical): nightly books-export off-volume to iCloud
  + monthly restore drill. Until shipped: the books have no parachute.

## 2026-08-12 ~00:30 — THE PARACHUTE: BOOKS BACKUP LIVE (Marcos: "shouldn't it be done now?" — yes)
- /api/books_export shipped (books tier: all /data json/jsonl + kev corpus; bars excluded as
  Alpaca-SIP-recoverable; secret-gated, read-only; auditor GO — 6th convening, 6/6 tonight,
  glob-verified vs real layout, no tokens exportable, atomic-write consistency confirmed).
- FIRST BACKUP PULLED: books_20260812_0028.tar.gz -> iCloud/TradingBot/books_backups (157
  files, 3.6MB). RESTORE DRILL EXECUTED AND PASSED: 41 json/jsonl parse clean, trade records
  backup=425 == live=425 EXACT, kev store restores w/ Wednesday sheet, 116 corpus transcripts.
- Nightly launchd agent LOADED (22:30 ET daily, header auth per auditor note 3, tarball
  integrity check, file-count tripwire vs prior night, 14-day retention, fires on wake if
  missed). The single-point-of-failure found in the Quartermaster's first audit is closed
  same-night. Remaining on #50: monthly drill cadence + ~ALP1M design-or-defect check.

## 2026-08-12 ~00:50 — SHIPPED: EMAIL TIERING (Marcos: "ship it now"; 80/100 quota by noon)
- Per-trade emails (~3/trade, 87 on Tuesday) were burning the 100/day Resend quota and would
  eventually CAP-SILENCE the critical tier (token failing, watchdog, stalls — which email even
  in DRY_RUN). Trade tier (plan/entry/partial/per-exit-summary) now defaults OFF in DRY_RUN;
  EMAIL_TRADE_ALERTS=1 restores at go-live (the $5 place+cancel test will email its fill ✓).
  Morning watchlist deliberately left on (1/day, Marcos reads it) — boundary, not omission.
- Auditor GO (7th convening, 7/7 tonight): no side effects skipped (pure email funcs, no
  consumers of returns), CSV logging lives outside the email path, DRY_RUN load-order safe.
  Pinned (4 gates + critical ungated + env semantics), suite ALL GREEN. Bot deployed asleep,
  book flat in-turn; boots 03:55 quota-safe.

## 2026-08-12 ~01:10 — SHIPPED: CROWN PIN IN 1S ROSTER (Marcos: "pin the crowned names ... now")
- Cause (Quartermaster 1s first-look): live-watching ranking rotated crowned PLAG OUT of the
  15-name 1s set for its entire +141% afternoon (~295 sparse bars). Fix: capture fetches today's
  leader_armed rows each 5-min roster refresh and pins crowns FIRST in _hot1; crowns also added
  to the subscription union; fail-open = prior behavior. Auditor GO (8th convening, 8/8): held
  names un-evictable (order-verified), 01:00 deploy = zero-loss window (capture idle, 04:00 boot
  rehydrates), limit belt taken (50000, tail-slice would drop MORNING crowns — PLAG shape).
  Ledger notes: cap-pressure crown-subscription edge (move add earlier if _cap_eff ever trims);
  all-crown >15 case accepted by doctrine ("resolution is a leader privilege"). Pinned, ALL GREEN.
- Leader meritocracy now extends to data capture: the winners keep their glasses.
