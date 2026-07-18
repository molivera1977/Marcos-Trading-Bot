# CHART GATE — WEEKEND GO-LIVE RUNBOOK (Mon 7/20)

Decision (Marcos, 7/18): **the Chart Gate goes in for Monday.** This is Kev's nightly ritual, executed
by the system. This runbook is the path from audited code → enforced gate at Monday's open.
Bot is DRY_RUN (paper). Deploys only while flat — weekend qualifies.

## SAT 7/18 — DONE by the Fable audit session
- [x] Full audit of both builds + gate wiring — 4 defects found, all fixed:
  1. per-day levels cache blinded the gate to intraday vision posts → **90s TTL** + last-known-good serve
  2. reader's tickers post polluted the bot's force-watch list every rescan → **tickers passthrough**
  3. hardcoded 7/17 sheet names → **dynamic exclusion** (any name already marked today)
  4. blind post on GET failure would wipe the day's levels → **abort, never post blind**
  - guards: 3-attempts/name/day cost cap, 2s pacing, ≥2-day history (recent IPOs), veto-phrase scrub
- [x] Rig extended: **T8a–T8h** lock the gate contract + TTL pin + stale-serve. **36/36 green.**
- [x] `--dry` / `--out` modes on the reader (bake-off + live-proof without posting)
- [x] `grade_bakeoff.py` (levels-only break-and-hold grading, side-by-side per model)
- [x] No-key dry plumbing pass on the 7/17 roster (roster/exclusion/render path)

## SAT–SUN — MARCOS (needs the key; ~$0.35 per model pass, estimate)
The model bake-off doubles as the LIVE VISION-CALL PROOF. Terminal:
```bash
cd ~/Desktop/Marcos-Trading-Bot
export ANTHROPIC_API_KEY=<paste-key>     # env only, never saved to disk

# pass 1 — current model (sonnet-4-6, same as evening_scan)
NEWCOMER_DAY=2026-07-17 python3 newcomer_vision_reader.py --dry --out /tmp/reads_s46.json

# pass 2 — Sonnet 5
NEWCOMER_DAY=2026-07-17 NEWCOMER_VISION_MODEL=claude-sonnet-5 \
  python3 newcomer_vision_reader.py --dry --out /tmp/reads_s5.json

# grade both against 7/17's real outcomes
python3 grade_bakeoff.py 2026-07-17 /tmp/reads_s46.json /tmp/reads_s5.json
```
- Pick the winner (most CATCH, fewest BAD). If ~tied → sonnet-4-6 (already proven 14/15 in chat tests).
- Paste the grade output into the session — reads get a hand-check before Monday trusts them.
- GO/NO-GO: if BOTH models produce garbage levels on the live call → reader does NOT run Monday;
  gate still enforces on the night sheet only (fail-closed = No Read No Trade, which is the spec).

## SUN — DEPLOY (flat window)
- [ ] Rig green (`python3 rig/test_defects.py` → must print 0 failed)
- [ ] `git add` bot + rig + reader + trigger + runbook/READMEs; commit; **push origin main**
- [ ] Verify Railway picked the commit (`railway status`), boot log clean
- [ ] Railway → bot service → Variables → **`CHART_GATE_ENFORCE=1`**
      (+ `NEWCOMER_VISION_MODEL=<bake-off winner>` noted for the local reader)
- [ ] Night-sheet session: mark levels for Monday's carry-over watchlist, POST to
      `/api/kev_watchlist` (date=2026-07-20) — same ritual as 7/17
- [ ] **VERIFY AFTER POST** (audit finding: POST REPLACES the day's store, last-writer-wins; the
      7/17 store ended at 3 names, not the full sheet): `curl -s "$SCREENER_URL/api/kev_watchlist?date=2026-07-20"`
      and confirm every sheet name + level came back. Post the sheet BEFORE 9:00 Monday; the reader
      merges around it after that (reader = the ONLY automated writer; recorder only GETs — verified).

## MON 7/20 — 9:15–9:25 ET
- Terminal A (reader, live posts):
  `export ANTHROPIC_API_KEY=<key>; NEWCOMER_VISION_MODEL=<winner> python3 newcomer_vision_reader.py`
- Terminal B (10s trigger, shadow JSONL only):
  `python3 shadow_trigger_10s.py`
- Watch Railway bot logs for `CHART-GATE [ENFORCE]` lines: allow / block / skip per entry.
- If the reader dies mid-day: bot fails CLOSED to sheet-only names (by design). Restart terminal A.

## MON EOD — SCORECARD (before trusting anything)
- Gate: every `chart_gate_*` decision vs what the name actually did (allow→outcome, block→saved?)
- Reader: hand-grade every posted level vs the chart
- Trigger: review `shadow_triggers_2026-07-20.jsonl` (fwd MFE/MAE per trigger)
- First live day = DATA, not proof. The scorecard accrues; nothing scales until it proves out.

## ACCEPTED RISKS (documented, not blockers — paper account)
1. **Gap-over-fade passes the daily gate** (AP/CTNT class) — the 10s trigger exists to close this;
   it accumulates in shadow until tuned.
2. **First-minutes window**: a newcomer that triggers before its read posts is blocked (skip).
   No read, no trade — per spec. Cost: missed first-seconds entries on brand-new names.
3. **Block ≠ re-arm**: a blocked below-level entry only becomes a trade if the bot's own trigger
   re-fires after price breaks the level. 7/17 evidence: no-break entries netted −1.68R vs +0.75R
   for break entries — blocking is positive-expectancy even when the re-fire never comes.
4. **Model-read quality is day-one live** — that's what the EOD hand-grade is for.
