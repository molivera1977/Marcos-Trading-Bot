# Continuous-Scan Loop + Living Watch List + Re-entry — Design Spec (DRAFT 2026-06-27)

**Status:** design, not built. Execute AFTER Monday 6/29 (validate the current pipeline + the new exits
on real `/api/decisions` data first). This is a core-trade-flow change → design → backtest on the
`backtest/` harness → independent audit → DRY_RUN → verify on the decision log → only then LIVE.

## Why (the problems this solves)
1. **`th.join()` serializes the bot.** The main loop enters a batch of breakouts, then BLOCKS until they
   all close before scanning again. So it can't enter ticker B while A is open, and can't re-enter A.
   This is the #1 reason we **scalp first-legs instead of slugging runners** — proven 6/26 on real Webull
   bars: even with the fixed exits we caught only SDOT +3.5% of its +60% move, because after the +1R
   scale → break-even → pullback stop, we don't re-enter the continuation. (`SUPPLY_EXIT_DESIGN.md`, backtest.)
2. **The watch list only GROWS.** The intraday rescan only *adds* names; nothing ever removes a stale one.
   By afternoon the bot watches a bloated pile of dead gappers — diluting focus and the decision log.

## Part A — Continuous-scan loop (replace the blocking batch model)
The main loop becomes a **continuous hunter**. Each cycle:
1. Refresh the watch list (add new movers, re-rank, prune dead — Part C).
2. Detect setups across all watched names (flat-top / MA-pullback / future rally-base-rally).
3. For each valid setup: if the **settled-cash budget** allows AND the ticker's **state** allows
   (Part B), launch `_trade_worker` as a BACKGROUND daemon thread — **do NOT join.**
4. Positions self-monitor in their own threads (the watchdog already tracks them as a per-ticker dict).
- **Session end:** stop NEW entries at 3:30pm (existing cutoff); then `join()` all open monitors ONCE at
  the end of the session (not per-batch); 3:45pm force-flat (existing).
- The settled-budget guard (each trade pulls $100 from the settled pool, stop when <$100) already makes
  this GFV-safe — verify it holds atomically across concurrent threads.

## Part B — Watch-list STATE MACHINE (replaces the blanket `traded_tickers` exclusion)
Per ticker, a state instead of "watching vs traded-and-excluded":
| State | Meaning | Scan looks for |
|---|---|---|
| **WATCHING** | gapper, never traded | a first entry |
| **OPEN** | currently holding (≥1 position) | an ADD on the next break, if under per-ticker max size |
| **RE-ENTRY** | exited / scaled out | a FRESH setup → re-enter ("keep going back") |
| **PRUNED** | truly dead (Part C) | nothing — removed from active watch |
Today's `traded_tickers` permanently excludes after one trade — that's the re-entry blocker; it's replaced
by this state. Re-entry is THE home-run key (6/26 proof).

## Part C — Dynamic watch list (ADD / RANK / PRUNE)
- **ADD** new gappers via the intraday rescan (exists).
- **RANK** by the Kev-weighted score (exists: gap/float × HTB × rvol).
- **PRUNE the *truly dead* — KEEP the basers (the hard, critical part).**
  - ⚠️ DANGER, proven 6/26: SDOT/IVF/ZDAI all CHOPPED/FADED in the morning then RAN midday — IVF based at
    VWAP for **4 hours** before +$3.08. Aggressive pruning would have dropped the day's winners.
  - **PRUNE** (truly out): hard backside/downtrend (lower highs AND lower lows over N bars) + dead volume +
    far below VWAP for > T minutes; illiquid (avg shares/min < floor — CHNR); confirmed gap-and-crap
    (faded > X% off the open high with no recovery + volume gone).
  - **KEEP** (could still set up): consolidating / coiling, higher-lows, volume present, near/above VWAP —
    the bases that become runners.
  - The **decision log is the tool**: define pruning on REAL behavior (the per-name status timeline), and
    BACKTEST the rule on Monday's data — "would this have pruned SDOT before its run?" — before it goes live.

## Key decisions (recommended defaults — refine before building)
1. **Max concurrent positions:** start at **3** (budget allows ~5, but a focused book + correlated-small-cap
   risk argues lower; Kev stays picky). Tunable.
2. **Per-ticker max $ over the day:** ~**2–3× MAX_TRADE_DOLLARS** (allow one re-add/re-entry), so re-entries
   don't over-concentrate one name.
3. **Re-entry rules:** require a FRESH setup (new flat-top/MA-pullback); a **cooldown after a stop-out** (don't
   revenge-trade — N min or until new structure); prefer re-entry after a **scale-out/win**, not a fresh stop.
4. **Sequence — re-entry FIRST, adds second.** Re-entry (RE-ENTRY state → fresh setup) is the proven win and
   simpler; pyramiding into an OPEN winner (adds) is the follow-on.
5. **Active-watch cap:** keep ≤ ~10–15 names actively watched (focus), but NEVER prune a baser to make room.

## Concurrency safety (this is where bugs will hide)
- Shared state touched by the main loop + N `_trade_worker` threads: `settled_remaining`, the watch-list
  state map, per-ticker size/count. ALL must be under locks (`trade_lock` exists — extend it / add a
  watchlist lock). The budget decrement/refund must be atomic.
- Durable open-trade state + the watchdog are already per-ticker (dict-keyed) — concurrency-friendly. Verify
  recovery/record works with multiple simultaneously-open trades (today it's effectively one at a time).

## Validation plan
1. **Backtest re-entry on the harness** (real Webull bars): does re-entering on the next breakout capture the
   SDOT/IVF runners vs the +3.5% first-leg-only? Quantify the lift.
2. **Validate pruning on Monday's decision log:** confirm the rules would NOT have dropped any name that later ran.
3. **Independent audit** — core-flow + concurrency = high blast radius.
4. Ship DRY_RUN; verify on `/api/decisions` (multiple concurrent decisions, re-entries firing) before LIVE.

## Risks
- Concurrency races on the shared budget/state → locks + audit.
- Over-concurrency (N correlated thin small-caps at once) → the max-concurrent cap.
- Pruning the winners → careful KEEP-the-basers criteria + backtest on real data.
- Core-flow rewrite (removing `th.join`) is high blast radius → audit + DRY_RUN + decision-log verify.
- GFV: all entries (concurrent + re-entry) draw the settled budget — the existing guard handles it; verify atomic across threads.

## Build order
1. Watch-list state machine + dynamic prune (replace `traded_tickers` exclusion; add pruning).
2. Continuous-scan loop (remove `th.join`; background threads; session-end join).
3. Re-entry (RE-ENTRY → fresh setup → re-enter, with cooldown).
4. Adds / pyramiding (OPEN → add on break).
5. Max-concurrent + per-ticker size caps.
Each step: design → backtest on `backtest/` → audit → DRY_RUN → decision-log verify.
