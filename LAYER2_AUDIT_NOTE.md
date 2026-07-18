# Layer 2 — "No Break, No Trade" chart gate — AUDIT NOTE (for Fable)

Built 7/17 (Opus), NOT deployed (positions were open; deploy is the killer). Shadow-default.

## What it is
Kev's core rule (Marcos, settled 7/17): **enter only when price has broken the MARKED level from the chart read.** The bot had no "wait for the break" concept — it fired ignition on any intraday base pop regardless of the level.

## What was built (2 edits in `marcos_trading_bot.py`)
1. `_chart_break_gate(ticker, entry_price)` (after `_fetch_kev_levels`, ~line 2084) → returns `(verdict, reason, level, source)`, never raises. Verdicts:
   - `skip` / `veto_do_not_trade` — sheet note says do-not-trade (e.g. VEEE)
   - `skip` / `no_marked_level` — no read/level for this ticker
   - `block` / `no_break_below_level` — entry BELOW the marked break level
   - `allow` / `broke_level` — entry ≥ marked break level
2. Shadow call at top of `_trade_worker` (~line 6046): logs `chart_gate_<verdict>` via `_log_decision` on EVERY trade + prints a `📐 CHART-GATE` line. Enforces (skips the trade) ONLY if `CHART_GATE_ENFORCE=1`. Default (unset) = shadow, changes nothing.

## Validation (dry-run vs 7/17's 21 entries + real night-sheet levels)
Gate logic replicated and run against actual entries:
- **4/4 correct on sheet names:** TGHL (entry 1.40 vs break 1.95 → BLOCK, actual −1.53R); VEEE ×3 (→ veto_do_not_trade, actual +1.77/−1.12/+0.50R).
- **17/21 were `no_marked_level`** — newcomers with no sheet entry. The winner GLXG (+2.21R) is one of them.

## KNOWN LIMITATION — must fix before enforce (Layer 2b)
Level source is currently the **night sheet only** (`_fetch_kev_levels()` → ~3 names/day). Newcomers have no level, so:
- In ENFORCE mode as-built, the gate would skip the whole scanner incl. legit newcomer breakouts (GLXG). **Do NOT set CHART_GATE_ENFORCE=1 until Layer 2b lands.**
- **Layer 2b:** post the newcomer VISUAL reads (marked launch/break level per name) to the dashboard store so `_chart_break_gate` can look them up alongside the sheet. The visual read is the level source; the gate is the enforcement.

## Open questions for the audit
1. Confirm level (`break`) semantics vs `confirm`: should the gate require price ≥ `break` only, or also hold `confirm`? v1 uses `break` alone.
2. Gappers: for a newcomer that gaps far above a stale prior-day high, the "meaningful" break is intraday (opening-range/consolidation high), NOT PDH. The visual read must supply the meaningful level; a raw PDH would false-`allow`. (7/17: SLND/PMAX "broke" stale levels and lost.)
3. In enforce mode, a `block`/`skip` currently returns from `_trade_worker` AFTER the ticker was marked traded (line ~6029) — so it won't retry on a later real break. Should a blocked entry stay eligible for a subsequent break? (Kev would re-enter on the actual break.)
4. `_fetch_kev_levels()` is memoized per-day; confirm freshness if the sheet is updated intraday.

## Layer 2b — AUTONOMOUS newcomer vision reader (`newcomer_vision_reader.py`, built 7/17)
Marcos's spec: "As soon as newcomers are added to the scanner, that needs to trigger a chart read, then those notes added to the instructions automatically. No read, no trade." This is the LEVEL SOURCE that feeds the gate for newcomers (the gate itself needs no change).
Pipeline: (1) TRIGGER poll `/api/decisions_archive` for new ACTIVE newcomers (reached break_armed/consolidating/triggered/filled — not raw flickers); (2) RENDER daily chart → PNG; (3) READ via Claude VISION (`client.messages.create` with an image block, same key/SDK as evening_scan.py; model `NEWCOMER_VISION_MODEL`, default `claude-sonnet-4-6`); (4) WRITE — MERGE the read into `/api/kev_watchlist` `_levels` (TAKE → real break level; SKIP/MARGINAL → do-not-trade note so the EXISTING gate veto path skips it); (5) ENFORCE — the bot's `_chart_break_gate` (already built).
- **Cost:** ~55 reads/day (verified 7/17) × ~1,100 in + 300 out tok ≈ **$9/mo on Sonnet** (Haiku ~$2, Opus ~$45). Prices APPROXIMATE — confirm current rates. Dedup: each name read once/day (`src:"vision"` marker); only active newcomers billed.
- **VALIDATED (plumbing):** compiles; roster=55; render OK (22KB PNG, correct levels); dedup + post-merge logic. **NOT validated: the vision call itself** (needs ANTHROPIC_API_KEY — on Railway, not local). MUST run a live `--once` read (key present) and eyeball the JSON verdicts vs a human read before any reliance.
- **Deployment home (open):** needs an always-on host with the key. Bot is cron (not always-on); recorder is always-on but may lack the key; options = recorder service / dashboard thread / new small Railway worker. DECISION PENDING.
- **SHADOW-SAFE:** the reader only WRITES levels; it never trades. With `CHART_GATE_ENFORCE` unset, a bad read cannot cause a trade — worst case it posts a wrong level that the (still-shadow) gate only logs.

### Read RELIABILITY (Marcos: "how do we guarantee the chart is read properly + lists the levels")
Not guaranteed by prompt alone — engineered 4 ways + MEASURED by the grader:
1. **Grounded persona/instructions** — the prompt IS the Momentum Operator reading per the canonical Kev spec (daily-room = the differentiator, reject overhead supply, A+ shapes only, no-break-no-trade, definable-risk), NOT a generic "day trader".
2. **Precise candidate levels as DATA** — `_candidate_levels()` computes PDH/PDC/PDL, month hi/lo, swing/reaction highs, round numbers; passed as text so the model SELECTS exact prices, never eyeballs pixels. (KLRS test: PDH 4.77, monthHi 4.915, reactions [4.68,4.80,4.915], rounds [5.0,5.5,6.0].)
3. **Strict schema + sanity validation** (`validate_read`) — required level set {break, confirm, next_supply, stop, targets}; rejects TAKE-without-break, break far-below-price (stale), stop≥break. Rejected read → NOT posted → no-read = no-trade (fails safe). Tested: rejects all 3 bad shapes, accepts good TAKE + SKIP.
4. **Confidence gating** — LOW confidence → rejected (no-trade).
THE REAL GUARANTEE = the frozen grader scores every posted read vs outcomes; bad reads show up in the scorecard → fix prompt/model. We measure read quality, not assume it.

### Audit questions for the vision reader
5. Prompt/verdict quality: does the vision read reliably distinguish base-breakout from falling-knife on real charts? (The whole edge rests here — needs a live sample graded vs human reads.)
6. MARGINAL handling: currently treated as do-not-trade (conservative). Right, or should MARGINAL post the level and let the break decide?
7. Meaningful-level correctness for gappers: does the model return the intraday/recent structure high, not a stale PDH? (Prompt instructs it; verify on live gappers.)
8. Model choice: Sonnet default — is a live read good enough, or is Opus worth 5× for the hardest reads?

## Deploy discipline
- Ships at a FLAT window through the replay rig, shadow-first. Validate the shadow log (`chart_gate_*` decisions) against live trades for N days, THEN flip `CHART_GATE_ENFORCE=1`.
- Test parity: what's tested must equal what's pushed (no local/prod value drift).
- Vision reader: run a live `--once` with the key, hand-grade the verdicts, BEFORE trusting it as the gate's level source.
