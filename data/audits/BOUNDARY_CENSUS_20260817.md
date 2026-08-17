# BOUNDARY CENSUS — 8/17/2026 (kill the class, per [[feedback_kill_the_class_not_instance]])

Every call site of `get_intraday_bars` / `_alpaca_intraday_bars` / `_fresh_session` /
`_live_sessions` / `_latest_session` in `marcos_trading_bot.py` @ commit e2ef254 (line numbers
that tree). The 09:30 sharp RTH-only flip (fixed 2a8951a: `_live_sessions` PRE hand-off,
`RTH_HANDOFF_MIN=5`, kill=0) is the CLASS this census + rig section AK pins: at every instant
the session list requested must be able to contain a completed 1-min bar.

Session windows (ET): PRE 04:00–09:30 · RTH 09:30–16:00 · ATH 16:00–20:00.
`sessions=None` in the fetcher = RTH-only filter (Webull default semantics).

## Pattern P1 — `sessions=_live_sessions()` (the hand-off class; `_fresh_session` fail-CLOSED)

| consumer | line | sessions arg | on empty |
|---|---|---|---|
| momentum/velocity feed | 3159 | `_live_sessions()` | fail-closed (no momentum row) |
| eyes/decision-gate fetch (count=390 + `_fresh_session`) | 4089–4090 | `_live_sessions()` | fail-closed (gate sees no fresh bars) |
| scan cache refresh (EMA bounce lookback) | 7624–7625 | `_live_sessions()` | fail-closed (skip name this cycle) |
| scan cache refresh (full_bars 390) | 7628–7629 | `_live_sessions()` | fail-closed (skip name this cycle) |
| velocity gate (`VELO_BARS`) | 9372 | `_live_sessions()` | fail-closed (velocity unknown) |
| entry-path fresh-bar guard (count=6) | 12517 | `_live_sessions()` | fail-closed (reject fire) |
| entry-path fresh-bar guard (count=30) | 12602 | `_live_sessions()` | fail-closed (reject fire) |

These seven are THE 8/17 blackout victims — all fed through `_fresh_session` (today+900s),
all fail-closed. Post-fix `_live_sessions()` keeps PRE visible through 09:30+RTH_HANDOFF_MIN.

## Pattern P2 — `sessions=_live_sessions(is_premkt)` (PRE-stamped position monitor)

| consumer | line | sessions arg | on empty |
|---|---|---|---|
| monitor_trade bar fetch | 10504–10505 | `_live_sessions(_entered_premkt or None)` | fail-closed after staleness watchdog (blind-stop protection path) |

## Pattern P3 — explicit `sessions=["PRE","RTH"]` (session VWAP — always boundary-safe)

| consumer | line | sessions arg | on empty |
|---|---|---|---|
| scan session-VWAP fetch | 7655–7656 | `["PRE","RTH"]` | fail-open (falls back to quote/rolling vwap) |
| monitor session-VWAP fetch | 10685–10686 | `["PRE","RTH"]` | fail-open (falls back to rolling-45 vwap) |

## Pattern P4 — archive `sessions=["RTH","PRE","ATH"]` (unfiltered full extended day)

| consumer | line | sessions arg | on empty |
|---|---|---|---|
| EOD bar archiver (kev watchlist) | 2527–2528 | `["RTH","PRE","ATH"]` | fail-open (name skipped, retry list) |
| EOD bar archiver (movers) | 2581–2582 | `["RTH","PRE","ATH"]` | fail-open (retry loop) |
| EOD bar archiver (retry pass) | 2601–2602 | `["RTH","PRE","ATH"]` | fail-open (reported still-failed) |

## Pattern P5 — sessions OMITTED (None → RTH-only default; auxiliaries, all fail-OPEN)

| consumer | line | sessions arg | on empty |
|---|---|---|---|
| 1s-shadow parity probe | 2666 | omitted (RTH-only) + `_fresh_session` | fail-open (observation skipped) |
| scanner VWAP fallback | 3458 | omitted (RTH-only) + `_fresh_session` | fail-open (vwap=0, hi=price) |
| token LIVE-PROBE (SPY) | 10898 | omitted (RTH-only) | fail-open (weekend-aware warning only) |

RULE (rig-enforced): a NEW `get_intraday_bars` call without a `sessions=` kwarg is a new
RTH-only sharp-flip instance — rig AK pins the bare-call count at exactly these 3. Any
behavior-relevant consumer must pass `_live_sessions()` (or an explicit session list).

## Session-utility consumers (no fetch; date/session trim over already-fetched bars)

| consumer | line | notes |
|---|---|---|
| `_fresh_session` defn (choke point) | 4353 | today-only + 900s staleness; date-blind `_latest_session` wrapped |
| `_latest_session` defn | 4333 | date-blind trim — every direct use is over an in-loop cache already session-filtered at fetch |
| direct `_latest_session` uses | 2666(B16 wrap), 6479, 6575(`_fresh_session`), 8404, 8441, 8471, 8564, 8704, 8836, 10674 | operate on `cache[t].full_bars`/monitor bars — inherit the fetch's session set (P1/P2) |
| warmup seed comment | 371 | doc reference only |
| `get_intraday_bars_full` | 4301 | separate full-day path (archive semantics) |

## Frozen-clock matrix (rig AK executes the real `_live_sessions`)

| instant (ET) | `_live_sessions()` returns | completed bar possible? |
|---|---|---|
| 04:00:30 | ["PRE","RTH"] | PRE forming; first completed PRE bar 04:01 — list CONTAINS the session that will hold it |
| 07:00:30 | ["PRE","RTH"] | yes (PRE) |
| 09:29:30 | ["PRE","RTH"] | yes (PRE) |
| **09:30:30** | **["PRE","RTH"]** (hand-off — THE pin; pre-fix: None → blackout) | yes (PRE) |
| 09:31:30 | ["PRE","RTH"] (inside 5-min hand-off) | yes (PRE) |
| 15:59:30 | None (RTH-only) | yes (RTH) |
| 16:00:30 | None (RTH-only) | yes (completed RTH bars all exist) |

Rig section AK goes RED if: (a) any of the above instants yields a session list that cannot
contain a completed bar; (b) the hand-off branch or its default (`RTH_HANDOFF_MIN`, "5") is
removed; (c) a new bare (sessions-omitted) `get_intraday_bars` call appears.
