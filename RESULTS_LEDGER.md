
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
