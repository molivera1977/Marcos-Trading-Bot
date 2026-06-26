# 90 EMA as an Entry Signal — Design Spec

**Goal:** promote the 90 EMA from *data-only* to an actual **pullback-entry trigger** — the single
most-repeated setup across the 11 Kev videos. Catch the deep-pullback re-entries the bot currently
misses (price pulls back past the 9/20 down to the rising 90 EMA, a buyer steps in, it rips again).

**Why (the bible — [[project_kev_lessons]]):** the 90 EMA is an entry level in ~5 videos, always the
same shape:
- ILLR: "it curls off the **90 MA**, I punch it at 340."
- PIII (his cleanest): "dip-and-rip off VWAP and the **90 MA** — break over highs, pull back, **wick off
  the low off the 90 = my confirmation candle** → entry 770s→850s."
- BIYA: "micro pullback off the **90 EMA** → break through highs."
- HCWB / JZXN / GOVX: "pullback off the 90 MA," "risking off the **90 EMA**."

The pattern is invariant: **uptrend → pull back to the 90 → a candle wicks off the low and gets bought
back up (a buyer steps in) → enter, risk just below the 90, target the next supply, ≥2:1.** The bot's
existing EMA-bounce only fires on a *shallow* pullback to the EMA9; this adds the *deep* pullback to the 90.

---

## The setup (entry type 3: "ema90_pullback")

All on the completed 1-min bars + the live price. Fires only when ALL hold:

1. **Uptrend context:** `ema9 > ema20` (stacked up) AND `price > ema90` (the 90 is below, acting as
   support) AND the 90 is rising (`ema90_now > ema90_a_few_bars_ago`). No downtrends.
2. **Pulled back to the 90:** the confirmation candle (`completed[-1]`) dipped to the 90 —
   `low <= ema90 * (1 + EMA90_TOUCH_TOL)`.
3. **Wick-off-low confirmation (THE Kev trigger):** that same candle **closed back above the 90**
   (`close > ema90`) AND has a real lower wick — buyers rejected the low:
   `(min(open,close) - low) / (high - low) >= BOTTOM_TAIL_RATIO`. = "it wicked off the low, a buyer stepped in."
4. **Weak pullback, buyers returning:** the pullback was low-volume relative to the prior up-move
   (`pullback_vol <= prior_up_vol`), and the live `price > completed[-1].close` (continuing up off the
   confirmation). (Kev: "a nice weak pullback... buyers swarm back in.")
5. **ROOM ≥ 2:1** (reuse `compute_room`): risk off the 90, reward to the next supply. Already built;
   this entry just calls it like the other two paths.

**Risk / stop:** just below the 90 / the confirmation low — `stop = min(ema90, conf_low) * (1 - EMA90_STOP_BUFFER)`.
Kev risks "off the 90 EMA." This stop is also what `compute_room` uses and what `_trade_worker` places
(test-push parity, like the EMA-bounce path).

**Entry price:** current price as it confirms up (same limit mechanics as the existing entries).

---

## Where it plugs in

`wait_for_flat_top_entry()`, as **entry type 3**, after the EMA9-bounce block, guarded by
`if not found_entry`. Order: flat-top breakout → EMA9 bounce (shallow) → **90-EMA pullback (deep)**.
Appends `(t, price, vwap, "ema90_pullback", {"ema_stop": stop, "room": room, "ema90": ema90, ...})`.
`_trade_worker` already handles `extra["ema_stop"]` for non-flat-top types — reuse that path.

Mutually exclusive with the EMA9 bounce in practice (price can't sit on both the 9 and the 90 at once),
so no double-fire. Room gate + failed-breakout exit + tiers/trail all apply unchanged.

---

## Parameters (initial — tune on charts, not by guess)

| Param | Value | From |
|---|---|---|
| `EMA90_TOUCH_TOL` | 0.005 (0.5%) | how close the low must come to the 90 to count as "to the 90" |
| `BOTTOM_TAIL_RATIO` | 0.40 | lower-wick share of range = "wicked off the low, buyer stepped in" (mirror of TOPPING_TAIL_RATIO) |
| `EMA90_STOP_BUFFER` | 0.01 (1%) | stop just below the 90 / confirmation low |
| `EMA90_RISING_LOOKBACK` | 5 bars | the 90 must be rising over this many bars (uptrend) |
| (reused) `MIN_ROOM_RR` | 2.0 | Kev's room minimum |

---

## Validation plan (verify our CODE sees what Kev sees — same doctrine as the room filter)

1. Chart-test `detect_ema90_pullback()` on synthetic shapes where we know the answer:
   - PIII-like: deep pullback to a rising 90, wick-off-low, close back above → FIRES, room to next supply.
   - downtrend (ema9<ema20) → NO fire.
   - pullback to 90 but closes BELOW it (no buyer) → NO fire.
   - touched 90, closed above, but NO lower wick (just drifted through) → NO fire (no confirmation).
   - confirmed but no room (supply right above) → room gate REJECTS.
2. Independent audit (it generates entries → must not false-fire, must not crash the scan, room/stop parity).
3. Ship; instrument like the others (the trade record already carries `entry_supply_src`/`room`; add
   `entry_type="ema90_pullback"` so we can see in `/api/room_stats` how these perform).

---

## DECISIONS — RESOLVED: "closest to identical to Kev's approach"

Kev doesn't pick one MA — he enters off **whichever rising MA the pullback holds.** So:
1. **Scope = generalized 20/50/90** (not 90-only). New entry type "ma_pullback" checks the MAs
   shallowest→deepest and fires off the **first one the confirmation candle CLOSED BACK ABOVE** (= the
   support level held). The existing EMA9-bounce keeps covering the shallow 9; together = 9/20/50/90,
   exactly Kev's set. ("Risk off the level it held" — Kev.)
2. **Strict wick-off-low confirmation** (dipped to the MA, closed back above it, real lower wick =
   "a buyer stepped in"). The faithful choice.
3. **Include the weak-pullback volume filter** (Kev: "a nice weak pullback... buyers swarm back in").

So the detector is `detect_ma_pullback(completed, price)` over levels [20, 50, 90].

Build order: `detect_ma_pullback()` + chart-tests → wire as entry type 3 (room gate + failed-breakout
exit apply) → audit → ship.

## STATUS — ✅ BUILT, AUDITED (PASS), shipped
- `detect_ma_pullback` (try/except → None) over [20,50,90], shallowest-first, fires off the level the
  confirmation candle CLOSED back above; chart-tested 6 cases (fires on the Kev pattern; rejects
  downtrend / no-wick / closed-below / not-continuing-up / buyers-didn't-return).
- Wired as entry type 3 in `wait_for_flat_top_entry` (above-VWAP, room gate ≥2:1, `_trade_worker` uses
  the MA stop via the generalized `if "ema_stop" in extra`). Failed-breakout exit + tiers + durable +
  watchdog all apply.
- Independent audit: PASS — faithful detection, EXACT stop parity, no regression (flat-top still 7%
  stop), cannot crash the scan. Tag label fixed (was printing "FLAT TOP" for ma_pullback).
- Open: extend to the **9 path** (unify the EMA9-bounce to the same wick-off-low) and **add 50** is
  already in (MA_PULLBACK_LEVELS=[20,50,90]). v1 done.
