# Tick Recorder — LOCKED DESIGN + Fable review package (2026-07-15, drafted in Opus)

Draft implementation: `recorder.py` (written, NOT yet run/tested/deployed).
Status: **design locked, awaiting Fable architecture review before any deploy.**

## Purpose
One isolated service fixes two real problems:
1. **Durability** — bot's in-memory 10s collection dies on every deploy; the 8:17pm ferry is app-open-dependent and MISSED tonight (rescued by hand).
2. **Accurate morning VWAP** — needs PREMARKET ticks captured LIVE (morning gapper VWAP is 84–89% premarket-weighted; 1-min-bar seed stays imprecise). Bot's stream starts 8:45am → misses 4am–8:45 premarket.

## LOCKED decisions (from the 7/15 late design session with Marcos)
- **Separate Railway service** (not folded into dashboard). Cost is a wash under Railway's usage-based model; separate wins on ISOLATION (a recorder bug can't touch the trading bot). Confirmed a 2nd Webull stream session coexists (dual-stream test, 7/15).
- **Cost = ~$0.** Hobby plan, $5 included credit, currently using $3.06 → ~$1.94 headroom; recorder ≈ $1/mo running the extended session only → absorbed by the credit, estimated bill stays $0.
- **Runs ~3:30am → 8:00pm ET, weekdays.** Starts 30 min BEFORE the 4:00am premarket open (Marcos: "start a few minutes prior to capture bars as they start") — margin for boot + stream connect (~3s) + scan + subscribe, so zero gap at premarket open. Exits 8pm (no overnight ticks; stays in free credit).
- **Watch universe: broad + refreshed.** Carryover seed at start (yesterday's movers + Kev's overnight watchlist) so KNOWN names are captured from premarket tick-1; then rescan every 3 min to add fresh gappers as premarket volume develops. Price $0.30–$20, up to 120 symbols. Over-capture per "more data is better."
- **Captures:** 10s + 60s OHLC bars (identical bucketing to the bot's proven B12 `_shadow_ingest`) + a running **snapshot-VWAP** (Σ price×Δcumvol / Σ Δcumvol — complete volume via cumvol, frequent price via snapshots → far finer than 1-min bars, meant to match Webull/Kev's chart line).
- **Persistence:** ships to the dashboard's durable `/data` volume via POST /api/bars_bulk (gzipped) every 5 min + on SIGTERM + at session end. iCloud ferry = 2nd copy. (Railway volumes attach to one service, so the recorder can't write the dashboard volume directly — it POSTs.)
- **Isolation:** no trading logic, READ-ONLY w.r.t. trades, fail-silent everywhere. Standalone (does NOT import the trading module) but reuses the PROVEN patterns (stream connect from stream_dual_test.py which ran tonight; `_shadow_ingest` bucketing; `scan_morning_gappers` screener call).
- **Deploy:** START_APP=recorder.py on a new Railway service, cron ~7:30 UTC (=3:30am EDT) weekdays. Env shared: WEBULL_APP_KEY/SECRET/ACCESS_TOKEN, SCREENER_URL, DASHBOARD_SECRET.

## ⚠️ FABLE REVIEW CHECKLIST — scrutinize these (honest known risks)
1. **★ NAMESPACE COLLISION (highest priority).** Both the bot's B12 EOD dump AND the recorder POST `"{ticker}~10s"` to /api/bars_bulk (which OVERWRITES). During RTH both run; the bot's 16:02 dump is RTH-only and would OVERWRITE the recorder's premarket-inclusive series → LOSE premarket. MUST resolve before deploy: distinct namespace for the recorder, OR retire the bot's B12 dump, OR make the dashboard MERGE not overwrite. **Do not deploy until this is decided.**
2. **Snapshot-VWAP cumvol-reset logic.** On cumvol decrease (suspected PRE→RTH counter reset) the code re-baselines `last_cumvol` but KEEPS num/den → intended to yield a continuous PM+RTH VWAP matching the chart. Verify: (a) does Webull cumvol actually reset at 9:30? (b) is the chart's VWAP continuous from 4am? (c) the transition-gap volume is dropped — material? Validates vs a chart screenshot tomorrow AM.
3. **SNAPSHOT ≠ every-tick.** It's a snapshot-stream VWAP (periodic snapshots, complete volume via cumvol), not literally every trade. Good enough to match the chart? Validates tomorrow.
4. **Subscription capacity.** MAX_SUBSCRIBE=120 — is that within Webull's per-session limit? If lower, subscribes past the cap fail. Need the real limit.
5. **Carryover-seed endpoints.** Code GETs /api/kev_watchlist & /api/watchlist — DO THESE EXIST on the dashboard? If not, the pre-4am seed is empty (rescan-only fallback → known names not captured until the first post-4am rescan). Verify or adjust.
6. **Token lifecycle.** Uses env WEBULL_ACCESS_TOKEN, no refresh. 2 sessions share it (dual-stream OK). 14-day expiry → recorder dies when it expires unless refreshed. Also confirm no TOKEN_DIR conflict (separate service = separate FS, should be fine).
7. **Restart policy.** For a recorder, auto-restart-on-crash is desirable (resume capturing). Persist every 5 min → a crash loses ≤5 min of un-persisted bars. Set restartPolicyType accordingly (bot uses "never").
8. **DST / cron.** 3:30am EDT = 7:30 UTC now; EST winter = 8:30 UTC. Cron is UTC. Set for season or handle DST.
9. **NOT YET TESTED.** recorder.py written but not run. Needs: import/syntax check, a live connect test (sparse after-hours ticks tonight prove connection), full validation tomorrow premarket (tick-VWAP vs chart on a gapper).

## What Fable should decide
- Approve/revise the architecture (esp. #1 namespace + #2 VWAP logic).
- Green-light the deploy path (new service creation + env + cron + restart policy).
- Confirm the snapshot-VWAP approach is sound or specify a better one.
Once approved: test (import + live connect) → deploy the new service → verify it's up before 4am → validate the tick-VWAP against a chart tomorrow AM.
