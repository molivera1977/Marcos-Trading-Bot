# DEFECT 1b — kevseq `front_side_unknown` fails CLOSED on fresh board names — 2026-08-17

## FAILURE CONDITION (pre-registered, written FIRST)

This fix is WRONG if any of:

1. **Disagreement.** On rows where BOTH the caller's 1-min `bars` value and the
   self-computed aggregate value exist, they disagree. That would mean the 10s->1min
   aggregate is not reproducing the 1-min chart, and every value it supplies is fiction.
   A live canary row `kevseq_frontside_disagree` is emitted on every such row —
   **if that row ever appears, set KEVSEQ_SELF_FRONTSIDE=0 and re-open this doc.**
2. **Fabricated confidence.** A front_side value produced from fewer than
   `EMA20_PERIOD+2` (22) completed 1-min bars. The code returns None below that.
3. **Silent substitution.** A row where front_side is set but `front_side_src` is not
   stamped, i.e. an unauditable value.
4. **Scope creep.** Any change to what front_side MEANS (9EMA>20EMA on 1-min). This
   fix changes only WHERE the inputs come from, never the test.

## ROOT CAUSE (confirmed)

`marcos_trading_bot.py` (kevseq ctx block, ~:8195): front_side is computed only from
`(bars or [])[:-1]`, the caller's 1-MIN list, and only when it holds >= 22 completed
bars. `kevseq_step` (:6422) then appends `front_side_unknown` and refuses whenever the
ctx value is not exactly True.

The 22-bar requirement is 22 MINUTES of 1-min history. A name that just hit the board —
which is every name kevseq is built for — does not have it. So the lane fails closed
for precisely the first ~22 minutes of the run it exists to catch. **~50 of today's 97
kevseq refusals were this**, on a day when the seven top board runners produced 39
triggers and zero fills.

The data was never missing: the same call already feeds kevseq 10s bars, and six 10s
bars are one minute.

## THE FIX (shipped)

- `kevseq_feed_1m(sym, new_bars)` — folds the fed 10s bars into a per-symbol, per-day
  1-min aggregate (module-level, survives rescans; 240-bar ring). Zero new fetches.
- `kevseq_front_side(sym, new_bars)` — EMA9 vs EMA20 over that aggregate. Returns
  `None` (still fail-closed) when < 22 completed minute bars exist.
- Caller: the aggregate is fed on EVERY call (before any branch) so it never has holes;
  the self value is used ONLY when the caller's 1-min path produced nothing.
- Stamps on every kevseq row (reject, shadow fire, triggered): `front_side_src`
  (`caller_1m` / `self_10s_agg` / `unknown_short_agg`) and `front_side_1m_n`.
- Canary: `kevseq_frontside_disagree` row whenever both sources exist and differ.

## ENV KILL SWITCH

`KEVSEQ_SELF_FRONTSIDE` — **default 1**. `=0` restores today's behaviour exactly
(the fallback branch is skipped; the aggregate is not even built).

## DEFAULT ON — WHY THIS IS NOT AN AUTHORIZED BEHAVIOUR CHANGE

`KEVSEQ_CONVERT` defaults to **0** in code, so kevseq is a SHADOW lane: this fix
changes which rows get logged, not what the bot does with money. Under
`feedback_auditor_cannot_authorize_behavior` observe-only rows are always safe, so
default-ON is correct and gives the OOS wall real evidence instead of
`front_side_unknown` noise.

**FLAGGED FOR MARCOS:** if `KEVSEQ_CONVERT=1` is set in the live Railway env, this
becomes a money-changing default and should be re-priced. I have not read the live env
this turn (no deploy/env access permitted during the session), so I am NOT claiming
what it is — `[UNVERIFIED]` by design.

## EXERCISE (ring 1 — executed 2026-08-17)

Block extracted from the live source and executed with stub EMAs:

```
rising  10s tape (200 bars)      -> (True, 33)     front side
falling 10s tape (200 bars)      -> (False, 33)    back side
short   10s tape (60 bars = 10m) -> (None, 9)      still fail-closed, correct
incremental feed in 7-bar chunks -> (True, 33)     IDENTICAL to one-shot
malformed bar tuple              -> (None, 0)      never raises
```

Incremental-equals-one-shot is the load-bearing check: the live path feeds a handful of
new bars per cycle, not the whole day.
