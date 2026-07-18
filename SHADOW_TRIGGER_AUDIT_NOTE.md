# 10-Second Trigger — Shadow Logger — AUDIT NOTE (for Fable)

Built 7/18 (Opus), **shadow-only, NOT deployed, NEVER trades.** File: `shadow_trigger_10s.py`.

## What it is / why it exists
The chart-read design has two halves (see `project_chart_gate` memory):
1. **SELECTION** — the daily read marks a break level per scanner name. VALIDATED: **30/31 winners caught across 3 blind samples including a full out-of-sample week (6/30–7/06)**; knives / do-not-trade get no level = vetoed. Its ONE remaining weakness: **gap-over-fade** (AP −7%, CTNT −5% both gapped over their level and faded; at the daily-close level they're indistinguishable from FXHO +50% which gapped over and ran).
2. **TRIGGER** — the actual entry is a break-**AND-HOLD**-on-**VOLUME** of the *intraday* base that forms after a validated name reclaims its level. Visible ONLY on the 10-second tape (verified 7/17: GLXG runner held+broke on expanding volume; VEEE fader spiked, volume died). **This is exactly what separates FXHO from CTNT/AP** — the daily proxy can't, the 10s hold-on-volume can.

This logger runs the trigger detector **in shadow** on daily-validated names and logs every trigger + real forward MFE/MAE, to **accumulate the 10s dataset needed to tune the thresholds.** The thresholds are UNTUNED (eyeballed from ONE day, 7/17, 3 names — tuning on that = overfit). It measures itself into correctness; it does not trade.

## Architecture (3 pieces)
- `armed_levels()` — GET `/api/kev_watchlist` `_levels`; return `{ticker: break}` EXCLUDING do-not-trade/veto/null. **This is the selection veto** — VEEE excluded HERE, upstream, not by any intraday climax rule (verified: VEEE does not appear in `--once` output). Levels come from the night sheet today; full coverage needs the newcomer VISION reads posted here too (that's Layer 2b — see LAYER2_AUDIT_NOTE.md).
- `detect(bars, daily_level)` — on 10s bars: TIGHT base (range ≤ TIGHT) → close BREAKS base high → break-bar volume ≥ VOLX × base-avg → and HOLDS (next HOLD bars stay ≥ base_high×0.985). Returns triggers with full context (base%, vol_mult, gap_over_daily, seq, prime_window, fwd MFE/MAE).
- main loop — poll every POLL_SECS, dedupe by (ticker,time), append JSONL to iCloud `shadow_triggers_{DAY}.jsonl`. `--once` for cron/test.

## Verified (7/17 backfill; the only day with 10s tape)
- Vetoes VEEE (do-not-trade). Fires on GLXG's REAL breakouts: seq0 09:39 (+22% MFE), seq1 10:45 (+18%), both prime-window; afternoon noise tagged seq2+/prime=False. So the log ALREADY carries the fields to separate signal from noise at tuning time.

## KNOWN LIMITATIONS / open questions for the audit
1. **Thresholds UNTUNED** (BASE_BARS=12, TIGHT=0.05, VOLX=3.0, HOLD=6, COOL=30) — guessed from 1 day. The logger's PURPOSE is to gather data to set them. DO NOT treat any value as validated.
2. **Does hold-on-volume actually filter the gap-over-fade (CTNT/AP)?** This is THE reason the 10s trigger exists. Unverified on those names (no 10s tape for their days). The forward shadow must show it.
3. **10s data is shallow** — exists for 7/17 only right now; recorder banks it daily. So this only produces signal FORWARD.
4. **Noise reduction** — `seq` (0 = first clean setup) + `prime_window` fields let tuning restrict to first-setup / 9:30–11:30. Is that the right noise control, or should the detector itself cap to first-N?
5. **Recorder 10s lag** — bars persist ~90s; fine for SHADOW logging, but a LIVE trigger built on this later must account for the lag (or read the bot's own B12 in-process 10s stream instead of the recorder's published bars).
6. **"Hold" here is bar-based** (lows stay above the level for HOLD bars). Real Kev "hold on volume" may want volume to keep expanding through the hold, not just price to stay up — candidate refinement.

## Deploy discipline
- SHADOW-ONLY. It writes a JSONL; it has no order path, no bot-state mutation. Safe to run alongside the live bot.
- Ships as a standalone process (cron `--once` per minute, or loop) — needs an always-on host during RTH. Does NOT go in the trading bot's process.
- Tune thresholds ONLY after N days of forward triggers; validate the tuned trigger on a held-out set before it ever feeds a live entry.
