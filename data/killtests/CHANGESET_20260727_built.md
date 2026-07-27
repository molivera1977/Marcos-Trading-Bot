# TONIGHT'S CHANGE-SET — BUILT (7/27, post-close). Rig-green, NOT pushed.

Built to `HANDOFF_20260727_tonight.md`. All six approved items are in; nothing outside the set
shipped. Verdict on ship/no-ship is at the bottom. Every number below was produced by a command run
in this session — nothing carried over from a prior context.

**State at build time (verified):** clock 16:31 EDT (after the 16:00 close, `date`).
`/api/open_trades` = `[]` — FLAT. Day book `/api/trades`: 22 rows dated 2026-07-27, **−$778.22**,
and **0 of 22 carry an entry timestamp** — item 5's premise re-confirmed against live data.

## Rig

`rig/test_tonight_20260727.py` — new, 46 checks, **exit 0**. Full sweep: **21/21 suites exit 0**
(judged by exit code, per the 7/26 lesson that pattern-matching missed a crashed suite).

The new suite drives the REAL `monitor_trade` over scripted price paths with I/O stubbed and a
frozen session clock, so each replay measures the mechanism it names. Fail-without-fix checks are
included for the two items where "it passes" would otherwise prove nothing (1d, 4e).

## The six items

1. **TRUE INTRABAR STOP** (`INTRABAR_STOP`, default on) — a stream/10s print at or below the stop
   exits immediately; 3-min structural exits above the stop are untouched. **CRATER FLOOR**
   (`CRATER_FLOOR_R`, 2.0R) sits beneath it — see F2 below: it is a backstop for the intrabar stop
   being off/killed, NOT the broken-feed failsafe the handoff called it.
   - LGHL 7/27 replay (entry 1.975 / stop 1.87): exits at the stop, **−1.00R** vs the live −3.3R.
   - JZXN replay: capped at the stop instead of −2.17R.
   - Accepted cost, stated not hidden: LVWR 7/24 and DFNS 7/27 wick-shakeouts now stop at ~−1R
     (live −$0.26 / −$2.29). Measured class ≈ $57 against $441.54 blow-through excess.
   - Boundary pinned in the rig (1e2): a tape that GAPS through the stop still books worse than
     −1R. This caps decision lag, not gaps. Exact −1R needs the resting broker stop — its own night.
2. **sessions=["PRE","RTH"] + DST** — new `_et_session_of_utc` converts through the tz database, so
   PRE/RTH/ATH are correct in EST as well as EDT (the old hardcoded `13:30–20:00` UTC window was
   EDT-only and would have shifted an hour in November). `_live_sessions()` threads the session list
   into the monitor's bar fetch (PRE-stamped position or pre-bell clock) and into six scan/entry
   fetches. `ENTRY_OPEN_ET` deliberately NOT reverted — rig pin 2j enforces that.
3. **BE_FLOOR_AFTER_SCALE 2 → 1** — a banked trade can no longer finish red. Measured harm of the
   old behavior was −$7.98 over 4 trades (not the previously-circulated $63.75).
4. **HIDDEN R-TRIM** — `hidden_entry` ladder becomes `+1R @33% → ×1.50 @55% → ×2.00 @75%`, runner
   ~25%. The inherited ×1.50-first trigger sat above BOTH closed peaks; rig 4e pins that at the old
   ladder LVWR banks nothing. Ladder is sorted and cumulative-monotone by construction.
5. **ENTRY TIMESTAMP** — `entry_ts_utc` stamped once at the fill and carried through durable state,
   the watchdog force-record, and the restart-recovery record. The dashboard's 7/22 pass-through
   loop means it lands without a dashboard change (pinned, 5d).
6. **READ-LIST LIQUIDITY FLOOR** — `_post_read_list` now walks Move%-ranked candidates and posts the
   first 20 that clear the same floor the entry gate enforces. **Fail-OPEN** when the fetch tells us
   nothing (miss / 429 / error, pinned 6c/6d, and logged); **EXCLUDE** when the fetch succeeds but
   returns no fresh bars — that is the thin-name signature itself (F3, pinned 6a2). Cached per name
   per 3-min bucket, probes on the AUX executor. The scanner's wide net is unchanged — that's the
   counterfactual log.

## One named trade, traced end-to-end in dollars

**VEEE 2026-07-27 hidden_entry** — entry $17.30, stop $16.43, R = $0.87/sh, 100 sh, planned risk $87.

    ladder  33% @ $18.17  →  55% @ $25.95  →  75% @ $34.60
    fill    33 sh @ $19.50            (first print above the +1R trigger)
    stop    floored at ENTRY $17.30 after that first partial   (item 3)
    exit    67 sh @ $17.20 — INTRABAR trailing stop            (item 1)
    P&L     +$65.90  =  +0.76R

Live, the same trade peaked at 6.9R, banked nothing, and closed **−$25.33**. Items 1, 3 and 4
compose correctly: the trim fires, the floor arrives, the runner leaves at break-even.

## The one thing that argues against item 1 — surfaced, not buried

There is a **prior measured refutation of this exact mechanism** living in the code and NOT in the
ledger: the accidental "breach-mode" that ran live 7/14 — B11 firing intrabar on a **20s-sustained**
stream breach — cost **−2.08R net**, and the note at `_blind_stop_should_fire` says hair-trigger
stops "kill the YYGH-class winners." Tonight's version is *more* aggressive than the thing that was
refuted: it fires on the first print, with no sustain at all.

The 7/27 verdict was rendered without this on the table. It does not obviously overturn the verdict —
the 7/27 evidence is newer and larger ($441.54 of blow-through across 36 trades vs a −2.08R replay),
Marcos has reaffirmed the intrabar stop three times, and the two known shakeout trades cost ≈$57.
But it is the strongest counter-evidence on record and belongs in the ledger.

Mitigation armed, inert by default: **`INTRABAR_CONFIRM_SECS`, default 0** = fire on the first print,
exactly as approved. Raising it (e.g. 3) requires the breach to persist that long. If Tuesday shows
shakeouts, the answer is one env var, not a redeploy of new logic. Rig pins it inert (1i2) and pins
that it actually gates when raised (1i3).

## Independent adversarial review (separate context, both halves) — 7 findings, 5 fixed

Per `feedback_signoff_requires_artifact` a separate-context reviewer attacked the diff on
consistency AND outcome. It cleared the areas I most expected to break (entry-timestamp
reachability on all three exit paths; intrabar firing on the entry bar or before the fill;
same-iteration self-trigger via the BE ratchet; ordering vs the blind-stop failsafe, premarket
flatten, watchdog and 3:45 close; the pytz DST conversion; the Webull fallback contract). It also
found real defects. I verified each myself before acting.

**Fixed tonight:**
- **F3 (blocking, outcome) — item 6 did not exclude the names it was written for.** DCOY/DBGI/TGL
  printed 20/6/7 bars in 30h, so their newest bar is hours stale; `_fresh_session` blanks it, and my
  first cut routed "no fresh bars" to fail-open. The three motivating names sailed through. Now
  split: **fetch returned nothing** (miss / 429 cooldown / error) → fail-open *and log it*, so a
  silent no-op during a 429 storm can't masquerade as "everything is liquid"; **fetch succeeded but
  no fresh session bars** → thin, exclude. Same staleness standard the entry path already applies,
  so nothing is refused here that would have been allowed to trade. New rig check 6a2 covers the
  DCOY shape — the old 6a/6c passed while the behavior was wrong.
- **F5** — a stop wider than half the entry price reordered the hidden ladder into two tiers sharing
  a cumulative; the second sold `max(1, 0)` = **one share**, a real order with real slippage. Tiers
  with no incremental share are now dropped. Rig 4g.
- **F6** — honoring `sessions` made archive callers passing `["RTH","PRE","ATH"]` lose overnight
  bars. A request naming all three sessions now means "the whole extended day", unfiltered. Rig 2f2.
- **F7** — the confirm dial read `_below_since`, which is set on a *strict* breach, so a price
  resting exactly AT the stop would never accumulate confirm time. It now has its own `<=` ledger.
- **F4** — the fail-open path now logs, per above.

**Not fixed, documented instead — F2: the crater floor is unreachable in the shipped config.**
`entry − 2R` is always below both the structure stop (`entry − R`) and the BE stop (`entry`), and
the intrabar branch is checked first and breaks. Verified arithmetically. It is therefore a backstop
for the intrabar stop being **off or killed** — *not* a broken-feed failsafe, because every feed
condition that blanks one blanks the other (both read the same `current_price`). The handoff sells
it as a broken-feed failsafe; it isn't one. The comment now says so. A real feed-independent
failsafe would key off `last_good_price` age or an independent REST quote — not built tonight, and
not claimed.

## ⚠️ F1 — THE ONE OPEN DECISION, and it is Marcos's

**Items 1 and 3 were each measured alone; their product was never replayed** — the same shape as the
failure the review-both-sides law was written from.

The BE-floor harm of −$7.98 was measured on history where the BE stop was only evaluable on a **3-min
close**. Item 1 converts that same stop to tick-level. So after the first partial, **any wick that
touches entry now ends the trade** — and that is precisely the behavior the 7/19 kill-test refuted
(12 BE-scratches → 0 when the floor moved to scale #2). Under intrabar rules the scratch count can
only be higher than 12. It also cuts against the largest number in the evidence pass: Q1d's
**$2,083.42 peak-to-realized surrender across 50 banked trades** — this plausibly increases it.

My own VEEE trace shows the mechanism doing exactly this: the runner was killed at break-even by a
pullback, banking +$65.90 out of a 6.9R peak. Better than the live −$25.33, worse than riding.

It cannot be measured tonight: era replay needs the entry timestamps that only start accruing with
this very deploy.

**Shipped as approved (`BE_FLOOR_AFTER_SCALE=1`)**, because Marcos approved it as law-compliance and
I will not quietly ship the lesser fix. But it is now an **env var**, so the isolation costs a
restart rather than a deploy:

    BE_FLOOR_AFTER_SCALE=2     # one session with item 1 isolated, item 3 held

Recommendation: take it. One session of intrabar-only data is worth more than the −$7.98 the floor
change is defending, and the two are independently revertible.

## Not done, deliberately

Broker-stop un-stub (its own night). No gate changes — the KIDZ canary stands. No slippage action.
`ENTRY_OPEN_ET` stays 09:30. The correction ledger was NOT re-applied (`/api/trades` already serves
corrected P&L).

## Four rig pins were updated, each because tonight's set changed the spec they pinned

Not loosened — repointed, with the reason in-file: `test_defects` T10c (BE floor 2→1),
`test_fastlane_gates` C3 (record-field adjacency), `test_read_list` P2 (top-20 slice → liquidity
walk), `test_alpaca_migration` M8b (`sessions` is now HONORED rather than "keep everything" —
["RTH","PRE"] now drops after-hours; archive callers passing ["RTH","PRE","ATH"] are unaffected,
and two new checks M8b2/M8b3 cover both). **M8b is a real behavior change beyond the literal fix
text** and is declared here rather than absorbed silently.
