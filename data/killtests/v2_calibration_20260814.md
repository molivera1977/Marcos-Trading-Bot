# V2 SHADOW CALIBRATION — 8/14/2026 (first live afternoon)

**VERDICT QUALIFIER (LIMITS, added 2026-08-17):** first-afternoon calibration on a partial session — in_window is 0/250 by construction (the lane deployed after the window), so the window-restricted backtest verdict is NOT re-tested here. The L4 cohort assumption is marked [UNVERIFIED] in the doc's own table. This is a distribution snapshot, not a grade. v2 harness parity is 51.2%, below the 90% floor (data/killtests/harness_parity.json).
Hidden Entry Architect. ANALYSIS ONLY — no code edits. Live rows: 250 v2_shadow_fire
(14:02–15:13 ET, 29 tickers) vs backtest census ~12.5 fires/runner-day all-session
(~2.9/day in-window) — live is roughly an order of magnitude looser.
Sources: /api/decisions 2026-08-14 v2_shadow_fire (250 rows, matched=250);
`entry_rebuilds_20260814_RESULTS.md` (Strategy 3 spec); live `v2_pullback_step`
(marcos_trading_bot.py :5682–5720, call site :7203–7218).

## 1. LIVE DISTRIBUTIONS (250 rows)
- flush_depth: all >=3% (env floor 3.0 works; median ~4.4; 6 rows >=10%). Depth is NOT a looseness.
- secs_from_push: 143/250 (57%) fired >120s after the push; 57/250 >180s; 6 >=300s.
- near_vwap (flush low within 2% of VWAP): TRUE only 53/250 (21%).
- in_window: 0/250 (deployed in the afternoon — by design shadow logs all day; backtest verdict was window-restricted).
- per-ticker: MF 35, YDES 22, DFSC 18, CGTL 16, BANL 16, XHG 15, WETO 14, AEHL 13, HAO 12 … (29 names; max seq 34 on MF — churn re-fires, 10 fires within 60s of a prior same-name fire).
- would_stop distance: median 2.44% below price (min 0.0% — degenerate stops exist), max 12.1%.

## 2. PREDICATE DIFF — live vs backtest spec
| # | Backtest spec | Live code (:5682) | Looseness |
|---|---|---|---|
| L1 | Flush must land INTO/NEAR an anchor: session VWAP **or** prior 4x3min consolidation high, within 2% | Anchor is STAMPED (`near_vwap`) and never gated; consolidation anchor not implemented at all | **Biggest cut: 197/250 rows fail even the VWAP half** |
| L2 | Flush completes within <=120s of the push; armed flush dies 180s later; confirmation = FIRST 10s higher-low + close>prior-high bar | Ratchet `fl["k"]=k` on every deepening low RESETS the expiry clock (armed life is unbounded); confirmation accepted on ANY qualifying bar while armed, arbitrarily far from the push | 143/250 fired >120s from the push; 57 beyond even 180s |
| L3 | Push = 2-min local high that is ALSO the 5-min high (an established push on a 40%+ runner) | Push = max of a rolling 2-min window only — every 3% micro-oscillation on a churny name arms a "flush" | Not measurable from rows directly; visible as per-name churn (MF seq→34); no cooldown either side, but backtest structure held churn to ~12.5/name-day |
| L4 | Cohort = 40%+ day-gain runner universe | Call site iterates the live candidates board (scanner-driven, gain floor of the board, not re-checked at the detector) | [UNVERIFIED] residual; likely small vs L1/L2 |
| L5 | Verdict window 9:30–10:30 ET | Shadow logs all day (in_window stamped) | By design — keep; grade in-window only |

## 3. CALIBRATION SET (each change + live rows it cuts today, from the 250)
| cal | change | rows cut (cumulative survivors) |
|---|---|---|
| C1 | GATE anchor proximity: flush_low within 2% of VWAP (add the consolidation-high anchor when coded; until then VWAP-only is the conservative subset) | −197 → 53 |
| C2 | Kill the expiry ratchet: `fl["k"]` = ARM time, never reset on deepening; require `secs_from_push <= 120` at fire | C1+C2 → **28** |
| C3 | Per-name cooldown 300s after any fire | C1+C2+C3 → **21** |
| C4 | Push maturity: 2-min high must equal the 5-min high (needs a 5-min window in state; cut not computable from today's rows — expected to trim the churny names further) | n/a from rows |
| C5 | Stop-degeneracy floor: reject fires with (price−flush_low)/price < ~0.5% (today's min was 0.0%) | trims ~1–2 of the 21 |
- V2_FLUSH_PCT=3.0 confirmed correct (0 rows under 3%): no change.

## 4. CALIBRATED SUBSET vs BACKTEST COHORT
21 survivors over ~2h / 29 names ≈ 2.3/name-day-equivalent — at or BELOW the backtest's
12.5/name-day all-session census (consistent: backtest universe was strictly 40%+ runners and
included the richer open). Survivor anatomy matches the backtest cohort: median depth 4.2%
(spec >=3), all secs_from_push 30–120s, all near-VWAP, median stop distance 2.7%, one-per-name
per 5 min (e.g. DFSC 14:02 d5.0/100s, WETO 14:12 d5.9/50s, PRHI 15:12 d7.7/60s). Verdict:
**yes — C1+C2+C3 brings live behavior into the backtested cohort's definition**; C4/C5 are
refinements to code alongside.

## 5. EXIT GRADING — SKIPPED (honest)
data/universe/bars10s has ZERO 2026-08-14 files (cache spans through 8/13 only). Today's fires
cannot be graded with the backtest exits until the harvester ferries 8/14. Queue: re-grade the
21-survivor cohort with the rebuild_bt exit stack once 8/14 bars land.

## OFFICERS TOUCHED
Hidden Entry Architect (owner) · Seam Scientist (one-day humility: today = 1 afternoon, no ship)
· Blast Radius Auditor (calibration = behavior change to a shadow row writer only; still diff-review
before ship) · Quartermaster (8/14 bars gap blocks grading) · Statistician (counts above from the
250-row pull, script in session scratchpad). ANALYSIS ONLY — nothing deployed.
