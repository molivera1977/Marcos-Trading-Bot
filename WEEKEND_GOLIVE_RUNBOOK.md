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

## SAT–SUN — BAKE-OFF (~$0.35 per model pass, estimate) — NO key handling needed
AUTONOMY DECISION (Marcos 7/18): reads run on their own — reader = the 4TH RAILWAY SERVICE
(cron each weekday 9:05 ET, exits 15:30, `railway.reader.toml`). ANTHROPIC_API_KEY VERIFIED
already on Railway → the bake-off runs via `railway run` (key injected, never on disk/screen):
```bash
cd ~/Desktop/Marcos-Trading-Bot

# pass 1 — current model (sonnet-4-6, same as evening_scan)
NEWCOMER_DAY=2026-07-17 railway run --service Marcos-Trading-Bot \
  python3 newcomer_vision_reader.py --dry --once --out /tmp/reads_s46.json

# pass 2 — Sonnet 5
NEWCOMER_DAY=2026-07-17 NEWCOMER_VISION_MODEL=claude-sonnet-5 railway run --service Marcos-Trading-Bot \
  python3 newcomer_vision_reader.py --dry --once --out /tmp/reads_s5.json

# grade both against 7/17's real outcomes
python3 grade_bakeoff.py 2026-07-17 /tmp/reads_s46.json /tmp/reads_s5.json
```
- The bake-off doubles as the LIVE VISION-CALL PROOF (first-ever run of the real pipeline).
- Pick the winner (most CATCH, fewest BAD). If ~tied → sonnet-4-6 (already proven 14/15 in chat tests).
- Hand-check a few reads vs the actual charts before Monday trusts them.
- GO/NO-GO: if BOTH models produce garbage levels on the live call → the reader service stays OFF
  Monday; gate still enforces on the night sheet only (fail-closed = No Read No Trade = the spec).

## SUN — CREATE THE READER SERVICE (Railway UI, ~3 minutes)
1. Project striking-appreciation → New Service → GitHub repo (same repo as the bot)
2. Service Settings → Config-as-code → `railway.reader.toml`
3. Service Variables: `START_APP=newcomer_vision_reader.py`, `ANTHROPIC_API_KEY` (copy from bot
   service), `SCREENER_URL` (copy from bot), `NEWCOMER_VISION_MODEL=<bake-off winner>`
4. After the push below, confirm one boot log: `[vision-reader] day=... key=set`

## SUN — DEPLOY (flat window) — TWO sets, one push, rig-tested together
Set 1 = chart gate (`ad93b43` + `d27424a`). Set 2 = **429-kill** (REST 3s cache, ServerException→
gauge, webull.* loggers→CRITICAL in bot+recorder+screener). Rig covers both: **43/43.**
NOTE: recorder + dashboard services redeploy too (silencer touched them) — weekend = safe.
- [ ] Rig green (`python3 rig/test_defects.py` → must print 0 failed)
- [ ] Commits ready on main; **push origin main**
- [ ] Verify Railway picked the commit (`railway status`), boot log clean
- [ ] Railway → bot service → Variables → **`CHART_GATE_ENFORCE=1`**
      (+ `NEWCOMER_VISION_MODEL=<bake-off winner>` noted for the local reader)
- [ ] Night-sheet session: mark levels for Monday's carry-over watchlist, POST to
      `/api/kev_watchlist` (date=2026-07-20) — same ritual as 7/17
- [ ] **VERIFY AFTER POST** (audit finding: POST REPLACES the day's store, last-writer-wins; the
      7/17 store ended at 3 names, not the full sheet): `curl -s "$SCREENER_URL/api/kev_watchlist?date=2026-07-20"`
      and confirm every sheet name + level came back. Post the sheet BEFORE 9:00 Monday; the reader
      merges around it after that (reader = the ONLY automated writer; recorder only GETs — verified).

## MON — WHAT THE LOGS SHOULD LOOK LIKE (429-kill verification)
- No `ServerException occurred... x-access-token` dumps anywhere (bot/recorder/dashboard).
- `EXEC HEALTH` 429 gauge NON-zero if Webull actually throttles (it was structurally 0 before) —
  a real number here is the fix WORKING, not a new problem.
- At most one `Webull ServerException` print per 30s from the bot.
- REST call volume: quiet names refresh ≤1/3s each (was 2×/sec each). If 429s persist at that
  reduced rate, the account-level quota itself is the story — that's a data-plan decision, not code.

## THE STANDING DAILY WORKFLOW (Marcos's spec, 7/18 — "Nothing will ever get traded
## unless a chart and read has been done")
- **NIGHT** — Marcos gives the Kev list + HIS levels in chat → posted to the store → verify GET-back.
  Kev's levels are CANONICAL for the gate (Kev is the Bible).
- **8:50 ET** — reader cron fires. Wave 1: SHADOW-reads every sheet name — our automated read of
  Kev's own charts, stored beside his levels (`vision_shadow`, never touching his) = the daily
  reading exam. Wave 2: the bot's morning scanner batch (watching list) read before the open.
- **All day** — wave 3: every new ticker joining the scanner triggers a chart+read (~90s poll).
- **Always** — the ENFORCE gate: no level, no break of it → no trade. No Read, No Trade.
- **EOD** — `python3 grade_reads_eod.py` → THE KEV EXAM (our level vs his vs the outcome, distance
  + agreement) + newcomer forward grades; appends to iCloud `read_grades.jsonl` (the capability
  track record). Volume: up to ~85 reads/day ≈ $0.50/day ≈ $11/mo (estimate).

## MON 7/20 — the reads run THEMSELVES
- 8:50 ET: reader service cron-fires on Railway — check its logs show `key=set` + the shadow pass.
  NO terminal, NO key handling: sheet exam → morning batch → all-day trickle, all autonomous.
- Terminal (10s trigger only, shadow JSONL, stays local — writes to iCloud):
  `python3 shadow_trigger_10s.py`
- Watch Railway bot logs for `CHART-GATE [ENFORCE]` lines: allow / block / skip per entry.
- If the reader service dies mid-day: it stays down until tomorrow's cron (restart=never) — the
  bot is UNAFFECTED and fails closed to already-marked names. Manual re-arm if wanted:
  `railway run --service Marcos-Trading-Bot python3 newcomer_vision_reader.py`

## MON EOD — SCORECARD (before trusting anything)
- `python3 grade_reads_eod.py` — the Kev exam + newcomer forward grades (automated)
- Gate: every `chart_gate_*` decision vs what the name actually did (allow→outcome, block→saved?)
- Reader: hand-grade a few posted levels vs the actual charts (spot-check the automated grade)
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
