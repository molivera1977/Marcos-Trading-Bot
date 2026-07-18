# Chart-Gate System — AUDIT ENTRY POINT

Two builds, ONE system. Built 7/17–7/18 (Opus). **AUDITED 7/18 (Fable) — see results at bottom.**
Go-live decision (Marcos 7/18): gate ENFORCES Monday 7/20 — see `WEEKEND_GOLIVE_RUNBOOK.md`.

## The system (why it exists)
The bot's core failure: it chased extended/weak names (ignition on VEEE/PMAX/AP) and bled. The fix is a two-part chart gate:
1. **SELECTION** — a daily chart read marks a break LEVEL for every scanner name; the DECISION is the level, not a TAKE/SKIP verdict (verdict scored 1/7, levels scored 7/7). Build: **`newcomer_vision_reader.py`**.
2. **TRIGGER** — the entry is a break-**AND-HOLD-on-VOLUME** of the intraday base, visible only on the **10-second tape**. Build: **`shadow_trigger_10s.py`**.

## Validation (the evidence — see `project_chart_gate` memory for full detail)
Blind tests, sealed outcomes, graded levels-only + break-and-hold, on small-cap momentum gappers (the target universe):
- **30 / 31 winners caught across 3 independent samples INCLUDING a full out-of-sample week (6/30–7/06).**
- The ONLY 2 failures were both **gap-over-FADE** (AP −7%, CTNT −5%): gapped over their level and faded. At the daily-close level they're indistinguishable from FXHO (+50%, gapped over and RAN). **This is exactly what the 10s trigger (build 2) exists to separate** — the daily proxy can't, the intraday hold-on-volume can.

## Build 1 — `newcomer_vision_reader.py` (level marking)  [audit note: none separate; described here + inline]
Poll scanner newcomers → render TIGHT daily chart (6d, `NEWCOMER_RECENT_DAYS=6`) → Claude VISION read → **post a MANDATORY break_level for every name** to `/api/kev_watchlist` `_levels` (levels-only: `post_level` posts for ALL verdicts; `validate_read` requires a numeric break_level for every read). ONLY `setup:"parabolic"` → do-not-trade veto (no armed level).
- **Reliability levers (verified):** grounded prompt, precise candidate levels passed as data (model selects, not eyeballs), strict validation, tight recent render.
- **NOT validated: the live vision CALL** — needs `ANTHROPIC_API_KEY` (on Railway, not local). Plumbing tested; the actual Sonnet read must be run + hand-graded. Extends the bot's existing Anthropic integration (evening_scan.py). ~$9/mo Sonnet.
- Updated 7/18 from the OLD verdict-gated version → levels-only/mandatory/tight (the old version was pre-findings).

## Build 2 — `shadow_trigger_10s.py` (10s entry trigger)  [audit note: `SHADOW_TRIGGER_AUDIT_NOTE.md`]
On daily-validated names (armed_levels = build-1's posted levels minus do-not-trade), watch recorder 10s bars for: tight base → break high → volume ≥ VOLX×base-avg → HOLD. Log every trigger + forward MFE/MAE to a JSONL. **NEVER trades.** Verified 7/17: vetoes VEEE, catches GLXG's real breakouts, tags noise.
- **Thresholds UNTUNED** (1 day of 10s data) — the logger's PURPOSE is to accumulate forward data to tune them.

## How they connect
`newcomer_vision_reader` posts the mandatory levels → `shadow_trigger_10s.armed_levels()` reads them → the 10s detector fires on the break-and-hold → JSONL log. Reader = "which names + what level"; trigger = "when to pull it." The reader's weakness (gap-over-fade at the daily level) is precisely the trigger's job.

## What Fable should scrutinize
1. **Build 1's vision read is unproven live** — audit the prompt/validation/veto logic; the actual read quality needs a live `--once` + hand-grade.
2. **Build 2's thresholds are guessed** — audit the mechanism + the accumulate-then-tune discipline, NOT for a tuned edge.
3. **Does hold-on-volume actually separate gap-over-run (FXHO) from gap-over-fade (AP/CTNT)?** The whole system hinges on this; unproven (no 10s tape for those days). Only the forward shadow settles it.
4. **Arming every non-parabolic name** (levels-only) removes the read-based veto — is the intraday filter enough, or does it over-arm? (validated 30/31 on close-proxy; live intraday unproven.)
5. **Data:** 10s tape is 1 day deep; recorder banks daily. Both builds only produce live signal FORWARD.

## Deploy discipline
- Gate enforcement is env-gated (CHART_GATE_ENFORCE); trigger stays a shadow JSONL with no order path.
- Needs: always-on RTH host for the trigger; ANTHROPIC_API_KEY for the reader. Tune the trigger only after N forward days; run a live vision read + hand-grade before trusting build 1.

## AUDIT RESULTS (Fable, 7/18) — 4 defects found, ALL FIXED + rig-locked
1. **BLOCKER — per-day levels cache** (`_fetch_kev_levels`): the first fetch of the morning froze the
   day's levels; intraday vision posts were invisible to the gate → in ENFORCE every newcomer stayed
   blocked all day. FIX: 90s TTL (`KEV_LEVELS_TTL_SECS`) + same-day last-known-good on refresh failure
   (never a fail-closed {} spike); a different-day cache is never served. Rig: T8g/T8h.
2. **BLOCKER — watchlist pollution**: reader posted `tickers=sorted(cur.keys())`; the endpoint REPLACES
   the day's tickers; the bot re-reads that list every rescan and force-adds to the stream
   (bot ~line 6038) → every read name would permanently grow stream/scan load (the rate-limit flood).
   FIX: tickers passed through UNCHANGED.
3. **Stale hardcoded SHEET_NAMES** (7/17's sheet frozen into the reader). FIX: dynamic exclusion —
   any name already having a level today (sheet or vision) is never re-read/overwritten.
4. **Blind-post wipe**: on a transient GET failure `post_level` posted a near-empty store → would WIPE
   the day's levels (endpoint replaces). FIX: abort on GET failure; never post blind.
Guards added: 3-attempts/name/day cost cap, 2s pacing, ≥2-day min history (recent IPOs are core
universe), veto-phrase scrub of model reason text. Rig T8a–T8h lock the gate contract; 36/36 green.
Sonnet read quality: validated pre-audit — batch3 levels 14/15 winners on break-and-hold
(`grade_batch3.py` re-run 7/18), blind 5/6, mixed AARD caught; final live-call bake-off per runbook.
