# AUDIT COVERAGE — written by the convening, checked by rig section Q under SHIP_CHECK=1
covers: ec5564bb9f10
date: 2026-08-12 ~23:50 ET
convenings tonight: 13th (premarket parity batch 1 — BLOCKED, 3 fixes), 14th (batch 2 post-ship
— 1 fix: calendar date guard), 15th (reader-07:00 + veto removal post-ship — BLOCKED, vision-first
merge branch + honest veto display + executed gate pin). All demanded fixes landed and re-verified
(poison renders 200, executed pins green, rig ALL GREEN). The interlock commit itself is covered:
it adds only the rig section the 15th convening's process finding demanded.
scope: screener_app.py /premarket + _merge_kev_levels vision-first branch + veto display;
marcos_trading_bot.py veto row (f36c1b2, audited 15th); rig sections O/P/Q.
