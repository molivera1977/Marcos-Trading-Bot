
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
