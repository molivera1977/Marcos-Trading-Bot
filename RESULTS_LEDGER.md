
## 8/2 (Sat) — FLOOR WAS OFF IN PRODUCTION 7/29–7/31; FIXED
- **Finding:** Railway env `MIN_STOP_PCT=0` overrode the code floor. Gate fired 11× on 7/28, then ZERO on 7/29–7/31 (decisions archives). MGRX 7/31 07:46 (3.09% stop, pure-function verdict = reject under 6%) traded because the floor was off — NOT a premarket hole. Who/when set to 0: unknown (no var history; window = 7/28 close → 7/29 open, the emergency morning).
- **Contaminates:** the 5v6 grade's Wed–Fri cells (trades read as exemptions were floor-off) and the claim "6% all week" — true only Mon–Tue.
- **Fix (8/2 22:27 ET):** book flat verified in-turn (`/api/open_trades` = []), `MIN_STOP_PCT=4` set, redeploy `6d91bcd9` SUCCESS on commit `6455ab4` = local HEAD (Friday ship-set confirmed deployed; earlier SKIPPED rows were superseded builds). Banner check pending Monday 03:55 wake.
- **Intrabar trace (same session):** `INTRABAR_STOP=1` is intentional (code comment :325, Marcos 3×; blow-through $441.54 vs shakeout ≈$105 at 10s). BUT `place_stop_order` (:6917) still returns None — no resting broker stop; benign in DRY_RUN, **go-live blocker** (retry STOP_LOSS enum spelling). Memory updated.
