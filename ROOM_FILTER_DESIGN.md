# Room-to-Next-Supply: Design Spec

**Goal:** give the bot the one thing Kev uses to separate wins from losses — *room*. Detect the
nearest overhead **supply** from the intraday bars, compute **room** and **room ÷ risk**, and use it
to (1) measure entry quality, then (2) gate entries that have no room, then (3) prefer high-room
candidates in selection.

**Why:** across 11 Kev videos, his two losing trades were both clean reclaims taken *into overhead
supply with no room* (TDIC, SDOT). The bot currently enters on a VWAP/flat-top break with **no room
check at all** — almost certainly what put it in the IQST chop (entered $1.595 into a range with
supply right above, went nowhere). "Room" is also the correct frame for the EMA-bounce path (the
VWAP-extension cap was the wrong proxy).

---

## The one primitive: `find_next_supply()`

From the 1-min bars already in `cache[t]["bars"]` (no extra fetch), find overhead resistance levels
— the price levels where sellers have shown / are likely to show. Sources, most→least reliable:

1. **Premarket high** — the single most-cited level in every video. (We have premarket bars.)
2. **Prior-day high** — if available from the daily/history.
3. **Intraday swing highs (pivot highs)** — a bar `i` whose `high[i]` is the max of `high[i-k .. i+k]`
   (`k = PIVOT_WINDOW`, ~3). These are levels where price topped and reversed = supply.
4. **Topping-tail bars** — bars with a large upper wick (reuse `TOPPING_TAIL_RATIO`); the high got
   rejected = sellers stepped in.
5. *(optional v2)* round-number / psychological levels ($5.00, etc.).

```
def find_next_supply(bars, current_price, premarket_high=None, prior_day_high=None):
    levels = []
    if premarket_high and premarket_high > current_price: levels.append((premarket_high, "pm_high"))
    if prior_day_high and prior_day_high > current_price: levels.append((prior_day_high, "pd_high"))
    levels += [(h, "pivot") for h in pivot_highs(bars, PIVOT_WINDOW) if h > current_price]
    levels += [(h, "tail")  for h in topping_tail_highs(bars)        if h > current_price]
    if not levels:
        return None, "open"          # NEW HIGH OF DAY — no overhead supply = open room (good)
    # cluster levels within SUPPLY_CLUSTER_PCT, take the NEAREST cluster above price
    return nearest_clustered(levels, current_price, SUPPLY_CLUSTER_PCT)
```

**Key behavior — new high of day:** if nothing is overhead, supply is `None` = **open room**. This is
exactly the breakout-to-new-highs case Kev loves; it must PASS, not get blocked.

---

## Room + risk calc: `compute_room()`

```
support   = stop_loss            # the level we risk off (pullback low / EMA / VWAP — already computed)
risk      = entry_price - support
supply, src = find_next_supply(bars, entry_price, pm_high, pd_high)
room      = (supply - entry_price) if supply else None        # None = open
room_pct  = room / entry_price        if room else None
rr        = room / risk               if (room and risk > 0) else (INF if supply is None else 0)
```

`rr` = potential reward (to the next supply) ÷ risk. Open room (new HOD) → `rr = ∞` (passes).

---

## Rollout — the GATE is gospel (Kev's ≥2:1 room rule); we verify our IMPLEMENTATION, not his strategy

Per [[feedback_kev_is_the_bible]]: Kev gates on room ≥2:1 — that's proven over 9 years, not a hypothesis.
So we **implement the gate**; we do NOT wait for our own trade data to "decide whether to gate." The
verification here is *implementation fidelity* — does our code see the supply/demand the way Kev sees it
by eye — done via charts + audit, BEFORE shipping.

**Step A — build + chart-test the primitive (this IS the validation):**
- `find_next_supply()` + `compute_room()`.
- Unit-test on real charts where we KNOW the answer: confirm it flags **IQST** as "no room" (supply right
  overhead), and that on Kev's own examples (MASK room-to-330, GOVX, PMAX) it identifies the supply level
  he named. If our code sees what Kev saw, it's correct. Tune `PIVOT_WINDOW` / clustering until it does.
- Independent audit of the detection + math.

**Step B — ship the gate AND instrument together:**
- Gate: reject an entry if `rr_to_supply < MIN_ROOM_RR` (2.0, Kev's stated minimum). Open room (new HOD)
  always passes. **Fail-OPEN on detection failure** — if bars are missing / supply can't be computed, take
  the trade and log `room=unknown`; a code glitch must never silently halt trading.
- Instrument (NOT to decide the gate — to VERIFY the implementation in the wild and catch drift): stamp
  `room_pct`, `rr_to_supply`, `next_supply`, `supply_src` on every trade + every rejection
  (`post_to_dashboard` + durable + screener), and expose `GET /api/room_stats`. This lets us confirm the
  detector is behaving on live charts and audit any rejection, without re-litigating Kev's rule.

**Step C — selection (next):** rank the watchlist by room to next supply; prefer the PMAX-style "only one
with room" candidate. Also gospel (Kev selects on room) — implement once the primitive is trusted.

---

## Where it plugs in

- New helpers near the other entry logic: `pivot_highs()`, `topping_tail_highs()`, `find_next_supply()`,
  `compute_room()`.
- Called at the entry decision in BOTH paths: flat-top breakout (~2470, before `breakouts.append`)
  and EMA-bounce (~2428). Uses `cache[t]["bars"]` — already in hand.
- Phase 1: attach `room_*` to the trade dicts; add screener fields + `/api/room_stats`.
- This same primitive **corrects the EMA-bounce skip-study**: log a pullback the VWAP cap rejected
  that had `rr_to_supply ≥ 2` = a *wrongly-killed good trade*. (Replaces "% above VWAP" as the signal.)

---

## Parameters (initial)

| Param | Value | Note |
|---|---|---|
| `PIVOT_WINDOW` | 3 bars/side | swing-high sensitivity; tune on data |
| `SUPPLY_CLUSTER_PCT` | 0.01 (1%) | merge nearby levels into one zone |
| `MIN_ROOM_RR` | 2.0 | Phase-2 gate threshold (Kev's stated min) |
| `MIN_ROOM_PCT` | optional | floor on absolute reward; off in v1 |

---

## Risks / to verify in the audit

1. **Pivot quality** — 1-min pivot highs are noisy. Premarket high is the most reliable anchor; lean on
   it + clustered pivots, not every micro-pivot. Tune `PIVOT_WINDOW`.
2. **New-HOD handling** — must read as open room (pass), not "no supply found → block."
3. **Fail-open on the gate** — detection glitch must never halt trading; log `unknown` and take it.
4. **No regression** — Phase 1 changes nothing about what trades; verify trade counts identical pre/post.
5. **Interaction** — once Phase 2 is on, watch for over-rejection (it shrinks trade count); the Phase-1
   data tells us where to set `MIN_ROOM_RR` before we ever turn it on.
6. **Premarket-high availability** — confirm we actually have premarket bars at entry time (the
   gapper scan fetches them; verify the high is reachable in the monitor loop).

---

## Build order

1. ✅ **DONE** — `find_next_supply()` + `compute_room()` + `_pivot_highs`/`_topping_tail_highs`/HOD,
   chart-validated (marcos_trading_bot.py). Tests: IQST → no room (rr 0.04, REJECT) ✓; new HOD → open
   (rr ∞) ✓; far wall → caught via HOD (rr 20) ✓; no bars → fail-open ✓; MASK breakout → cap = pm_high
   3.30 (rr 5.4) ✓. Pure/dormant — wired into nothing yet, changes no behavior.
2. Phase 1 instrumentation (bot + screener + `/api/room_stats`). Ship — blocks nothing.
3. Reframe the EMA-bounce skip-study around `rr_to_supply`.
4. Independent audit.
5. After data accrues: Phase 2 gate at the `MIN_ROOM_RR` the data supports.
