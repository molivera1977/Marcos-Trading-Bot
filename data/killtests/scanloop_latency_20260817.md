# DEFECT 3 — SCAN-LOOP LATENCY / stale_fire_suppressed — 2026-08-17

## FAILURE CONDITION (pre-registered, written FIRST)

The measurement work here is WRONG if:

1. The instrumentation changes ANY trading behaviour — if a single decision, fetch,
   order, or ordering differs with `SCAN_CYCLE_TIMING=1` vs `=0`. It may only add a
   log row.
2. It costs measurable time itself. Per-name bookkeeping is one dict write; if the
   `scan_cycle_timing` rows show the timing overhead is non-trivial, rip it out.
3. The reported diagnosis is not backed by counted call sites. A guess dressed as a
   profile is worse than no profile.

And the DIAGNOSIS below is wrong if the first day of `scan_cycle_timing` rows shows the
tail is NOT in `bars_refresh` + `detect` per-name work — e.g. if `rescan` or `tail`
dominates. **The rows are the arbiter; this doc's hypothesis is falsifiable by tomorrow's
first cycle.**

## THE COST (today)

57 `stale_fire_suppressed` rows on 8/17 — `ignition10s` x23, `vwap_reclaim` x22,
`hidden_entry` x11, `zone_flip` x1. The forensic
(`pre_staleness_forensic_20260817.md`, section E) measured decision bursts at
09:30:50 / 09:32:15 / 09:35:50 / 09:37:41 / 09:40:51 = **85-195s per cycle** while the
feed itself reported `last_bar_age=10-45s`. `CURL_FIRE_MAX_AGE_SECS=90` /
`CURL_FIRE_MAX_AGE_PRE=60` then correctly refuse fires whose bars aged out **inside our
own loop**. The ~+$119 STFS winner was lost to exactly this.

## DIAGNOSIS (counted, not guessed)

The watch loop (`marcos_trading_bot.py` :7898 `while True:`) is **single-threaded and
serial over the roster**, and it makes blocking network calls per name per cycle:

**Phase `bars_refresh`** (the `for t in candidates` at :7960) — per name, every 30s:
- `get_intraday_bars(t, count=50, sessions=...)` — blocking REST
- `get_intraday_bars(t, count=390, sessions=...)` — blocking REST

**Phase `detect`** (the `for t in candidates` at :8045) — per name, every cycle,
**5 `_curl_feed` call sites** at three distinct `n` values (90 / REHYDRATE_BARS / 180).
`_curl_feed` memoises on `(t, n)` for `CURL_FEED_MEMO_SECS=2` — so same-`n` sites share
a call, but the **distinct `n` values do not**, and a 2s memo expires within one name's
own work. Realistically **2-3 more blocking REST calls per name**, plus
`_recorder_tick_vwap` and `get_daily_levels` (the latter is once-per-session cached).

So: **roughly 4-5 blocking REST round-trips per name per cycle, executed strictly one
after another.** At a 40-name roster and 0.4-1.0s per round trip that is **64-200s of
pure serial network wait per cycle** — which is the observed 85-195s, arrived at from
the call sites rather than from the symptom. Nominal sleep is 30s; the sleep is not the
problem, the fan-out is.

Two amplifiers, both already documented elsewhere: the rescan callback (board pull)
runs INSIDE the same thread every `INTRADAY_RESCAN_INTERVAL=60`, and the 09:30
bell-boundary blackout (fixed separately today) made the open's cycles the worst ones.

## HONEST VERDICT: THIS NEEDS AN ARCHITECTURE CHANGE. NOT TONIGHT.

The real fix is to stop doing N serial round-trips in the decision thread — a bounded
thread-pool fan-out for the bar refresh (embarrassingly parallel, no shared state on the
fetch side) and moving the rescan pull off the critical path. That is a rewrite of the
loop's concurrency model, on a live-money week, with a position open, against a
`_curl_memo` / `_shadow_lock` / cursor-state surface that is not thread-audited. Per the
brief and `feedback_hostile_tape_gauntlet`, **no speculative perf change ships.**

The three candidate levers were considered and are recorded, not shipped:
- **aux executor for the bar refresh** — the right answer; needs a thread-safety audit of
  `cache`, `_curl_memo`, `_reclaim_cursor`, `_zf_cursor` and a hostile-tape gauntlet run.
- **cap per-cycle work** — makes the tail shorter by not looking at names. On a
  board-is-the-universe roster that is a silent coverage cut, i.e. a new refusal policy
  wearing a perf costume. Refused.
- **raise fire-age tolerance for top-of-board names** — would convert stale fires into
  trades on stale prices. That is the defect `CURL_FIRE_MAX_AGE_SECS` exists to prevent,
  and it changes what the bot does with money. Marcos's call, and it should be priced
  AFTER the profile exists, not before.

## WHAT SHIPPED: MEASUREMENT ONLY

`_cyc_name` / `_cyc_mark` / `_cyc_emit` (near `_log_stale_fire`) emit **one
`scan_cycle_timing` row per cycle**:

```
total_s, n_candidates, per_name_s, sleep_s,
phases  = {bars_refresh, detect, rescan, tail}
slowest = the 5 names that ate the most wall clock, with seconds
```

Plus a `🐢 SCAN CYCLE …` console line whenever a cycle exceeds 60s.

`_cyc_name` is called at the TOP of each per-name iteration and closes the previous
name's timer — deliberately, because both per-name loops have many `continue` exits and
a bottom-of-loop call would silently under-count exactly the slow paths.

No work is moved, capped, reordered, parallelised, or skipped.

## ENV KILL SWITCH

`SCAN_CYCLE_TIMING` — **default 1**. `=0` makes all three helpers immediate no-ops.
Default ON because this is observe-only, and observe-only rows are always safe
(`feedback_auditor_cannot_authorize_behavior`).

## EXERCISE (ring 1 — executed 2026-08-17)

```
phases : {'bars_refresh': 0.18, 'detect': 0.07, 'tail': 0.0}   (injected 0.05+0.12 / 0.03+0.03)
slowest: [('BBB', 0.13), ('AAA', 0.10), ('CCC', 0.04)]          per-name attribution correct,
                                                                AAA correctly summed ACROSS phases
total  : 0.25   per_name_s: 0.083
kill switch SCAN_CYCLE_TIMING=0 -> 0 rows, cycle dict untouched
None/garbage arguments           -> never raises
```

## NEXT STEP (for Marcos)

Give this one session of live rows. If `phases.bars_refresh` dominates — which the call
count predicts — the executor fan-out is a scoped, testable weekend change with a real
before/after number attached. If it does not, this doc's hypothesis is refuted and the
rows will say where to look instead.
