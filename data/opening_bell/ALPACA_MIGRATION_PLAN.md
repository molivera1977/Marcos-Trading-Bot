# ALPACA DATA MIGRATION — Plan for Fable Review
_Drafted 7/23 (RTH, bot flat). Author: Opus (execution loop). Reviewer: Fable._
_Standing rule that shaped this doc: Fable has approved things this week that shipped broken (premarket-mode DOA, "curl lanes ALL LIVE" mis-verification). So every claim below is tagged **[VERIFIED]** (a check ran — cited) or **[UNVERIFIED]** (assumption / open question). The review's job is to attack the [UNVERIFIED] ones before any code is written._

---

## 0. Decision (Marcos, 7/23) — NOT under review, this is the mandate
> "Switch it all in terms of data and decision-making lines to Alpaca. Leave Webull for trade execution."

Plus two constraints Marcos added in the same conversation:
- **Execution stays Webull — SETTLED.** Rationale is not "Webull is fine" (untested) — it's that **Webull is Kev-proven to trade our exact universe** (sub-$5 low-float gappers; Kev trades them daily). Alpaca execution would gamble on Alpaca's low-price/low-float tradability restrictions [UNVERIFIED and now moot — we're not moving execution]. This kills the "full Alpaca" fork.
- **VWAP line = Alpaca is PENDING a Kev-fidelity check.** Kev's VWAP/charts/fills are Webull's. Alpaca SIP VWAP may be *more accurate* but the goal is *matching Kev's reference line*, not accuracy. Must validate Alpaca-VWAP vs Webull-VWAP vs Kev screenshots before trusting it. `DATA_PRIMARY=webull` env already reverts it (#87).

---

## 1. Root cause this migration fixes (why we're doing it) — [VERIFIED]
One root under a week of "thousand cuts": **the bot leans on its OWN private Webull streaming session for detection data, and that session is unreliable.**
- Curl lanes fired 0× for days → curl forensic 7/23 [VERIFIED, data/opening_bell/curl_forensic_20260723.txt]: machines fire 21×/3× in replay on Alpaca ~ALP10S but 0× live because the bot's in-memory `_shadow_bars` (fed only by the bot's Webull snapshot stream) is empty/volume-less during RTH.
- Recorder churn (#93), ghost-session 417s (#86), open-drive misses (#94) — all the same root: a fragile private Webull stream.
- Alpaca A/B same window 7/23 [VERIFIED]: Alpaca 1 disconnect all day, 5-10k msgs/min; Webull recorder churned every 3-5 min.

**The architecture principle that follows:** ONE Alpaca connection (the existing `alpaca_capture` service), all consumers read its dashboard-persisted `~ALP*` series. Do NOT open a second Alpaca websocket in the bot — that recreates the exact session-competition trap (#93) on Alpaca (ATP = one websocket per key pair) [VERIFIED: #83 memo].

---

## 2. Touchpoint map — every Webull data-read in the bot [VERIFIED via grep 7/23]

| # | Touchpoint (code) | Current source | Target | Risk |
|---|---|---|---|---|
| T1 | `get_price` / `_get_price_rest` (:996/:2457) — live price for stops, monitoring | Webull stream + REST | **Alpaca**: last `~ALP10S` bar close, or Alpaca latest-trade REST | latency of dashboard round-trip vs direct; halt handling |
| T2 | `_shadow_bars[10]` → curl machines (:747/:748/:960) | Bot's own Webull stream | **Alpaca `~ALP10S`** pulled per-name each loop (replaces `_shadow_ingest`) | THE curl fix. Cursor/dedup; latency |
| T3 | `get_intraday_bars` 1-min (:2945, 9 call sites) → flat-top/ignition/EMA machines | Webull REST bars | **Alpaca 1-min**: aggregate `~ALP10S`→1m, OR Alpaca bars REST | biggest surface; EMA fidelity; premarket coverage |
| T4 | VWAP line `_recorder_tick_vwap` / `_TICKVWAP_SUFFIXES` (:4328) | Alpaca-first already (#87) | **Alpaca `~ALPVWAP`** — KEEP, but **validate vs Kev's Webull line** | Kev-fidelity [UNVERIFIED] |
| T5 | `scan_morning_gappers` (:1350) — premarket gapper screener | Webull `get_gainers_losers`/`get_most_active` | **OPEN QUESTION** — see §4 | Alpaca has no premarket %-gainer screener [UNVERIFIED] |
| T6 | `get_daily_levels` (:3264) incl. `prior_day_close` (day-gain floor ref) | Webull daily bars | **Alpaca daily bars** REST, or dashboard-stored | low-risk; daily bars are standard |
| T7 | Open-drive detection (NEW, #94) | — (doesn't exist) | **Alpaca `~ALP10S` velocity trigger** | calibration (EHGO mis-fire); subscription breadth (VIVK gap) |

### Stays Webull — execution only [SETTLED]
`get_account_balance` (:2357), `_place_order` (:5180/order_v2), `check_position`/holdings (:6370). Kev-proven tradability.

---

## 3. Architecture (proposed) — [design, for review]
```
Alpaca SIP ──(ONE websocket)──> alpaca_capture service ──> dashboard ~ALP10S / ~ALPVWAP / (new) ~ALP1M, ~ALPDAILY
                                                                    │
Webull screener REST (T5?) ──> watchlist ─────────────────────────┤ (discovery: what to subscribe)
                                                                    ▼
                                          BOT reads ~ALP* from dashboard per loop:
                                          T1 price · T2 curl 10s · T3 1-min · T4 VWAP · T6 daily · T7 open-drive
                                                                    │
                                                                    ▼
                                          Decision → Webull trade API (execution only)
```
- **alpaca_capture becomes the single market-data hub.** It already writes ~ALP10S/~ALPVWAP; add ~ALP1M (fold 10s→1m) and ~ALPDAILY (prior close) so T3/T6 have Alpaca sources.
- **Bot's own WebullStream (`_on_msg`/`_shadow_ingest`) is RETIRED for detection** — the fragile private stream that caused everything. Bot keeps the Webull *trade* client only.
- **Per-line env reverts** (extend the `DATA_PRIMARY` pattern): each touchpoint gets an independent `<LINE>_SOURCE=alpaca|webull` so any single line rolls back without touching the others. Kill-switch granularity = one line, not the whole migration.

---

## 4. THE HARD OPEN QUESTION — the scanner / DISCOVERY (T5) [UNVERIFIED — do not assume]
**Correction (7/23, Marcos challenged the earlier wording):** Two separate things were conflated:
- **Alpaca WATCHES premarket data — [VERIFIED].** ~ALP10S bars exist from ~4am (EHGO 04:35, CJMB 05:12). Streaming premarket is NOT a gap.
- **DISCOVERY (which names to subscribe) — [UNVERIFIED, must test].** Alpaca only streams what you *subscribe*, so something must surface "EHGO just gapped 30%." Alpaca DOES have a movers/screener endpoint (likely `/v1beta1/screener/stocks/movers`) — my earlier "no screener" was an overstatement. What is genuinely unverified: does Alpaca's movers screener cover **premarket ranking + sub-$5 low-float small-caps** as well as Webull's `get_gainers_losers(PRE_MARKET)`?
- **TEST RUN 7/23 15:52 [VERIFIED] (scratchpad/alpaca_screener_test.py via `railway run`):**
  - Alpaca `/v1beta1/screener/stocks/movers` returned HTTP 200, **50 gainers + 50 losers**. A working screener exists — earlier "no screener" fully retracted.
  - **Universe coverage — the real worry — PASSES:** the list natively includes sub-$1 / low-float / warrant names: BGLWW $0.08 (+122%), AEHL $0.96 (+73%), WBUY $1.05, GSUN $0.34, LGCL $1.55. NOT large-cap-only.
  - **6/13** of our known movers in top-50 (EHGO, NVVE, JEM, WBUY, LGCL, AEHL). The **7 misses are all faders** — proven by their own snapshots: ADVB opened 15.15 → now 13.69; LABT 3.55 → 3.00 (red on day); SXTC 0.41 → 0.32 (red); PN/CJMB/VIVK/NIKI faded off highs. A 3:52pm %-from-close ranking correctly deranks a name that gave it back — a point-in-time artifact, not a coverage hole.
  - **Snapshot coverage = 13/13:** every ground-truth name has full Alpaca dayO/dayH/minuteBar data even when off the movers list. Alpaca HAS the data on all of them; discovery is purely a ranking question.
- **RESOLVED FROM ALPACA DOCS 7/23 [VERIFIED] — no premarket screener:** Alpaca docs (docs.alpaca.markets/reference/movers-1), verbatim: *"For stocks, the endpoint resets at market open. Until then, it shows the previous market day's movers."* And `percent_change` is computed **close-to-close**, not intraday. So before 9:30 the movers endpoint returns YESTERDAY's list — it structurally **cannot discover today's premarket gappers**. The one load-bearing question is answered without waiting for an 8am run.

### T5 DECISION — SETTLED by evidence (was "the #1 open question")
- **Premarket discovery (4:00–9:30) STAYS on Webull** `get_gainers_losers(PRE_MARKET)`. Alpaca has no premarket-ranking equivalent — documented, not assumed. This is the discovery source for the morning prep + open, which is exactly where our edge lives.
- **Intraday discovery (post-9:30):** Alpaca's movers DOES work and covers our cheap/low-float universe (7/23 test: surfaced sub-$1 names, faders correctly deranked). OPTIONAL supplement to Webull's intraday screener — not required, decide later.
- **Data/stream unaffected:** Alpaca still *watches* premarket (4:35am bars, per-symbol snapshots verified). It can't *rank/discover* premarket; it can *stream* any name you already know. Split holds: **discovery = Webull; streaming decision-data = Alpaca.**
- **Net:** Webull's role = execution + premarket-discovery screener (both reliable REST/trade APIs, both Kev-aligned). Alpaca owns all streaming decision data. This is option (a)/(c) below, now on documented footing.

Options that WERE on the table (kept for the record; T5 above settles it):
- **(a) Keep the scanner on Webull REST.** The screener is a low-frequency *REST* call — NOT the unreliable streaming. Reliable, Kev-aligned, zero migration risk. Webull then does: execution + discovery. Cleanest, lowest-risk. **← recommended pending review**
- **(b) Build an Alpaca-native scanner** from a broad `~ALP10S` universe ranked by intraday %+vol. Problem: Alpaca only streams what it *subscribes* → can't discover NEW names (circular). Needs an external universe feed. Higher risk.
- **(c) Hybrid**: Webull screener for discovery, Alpaca for all downstream data + open-drive detection on the subscribed set.

**This is the #1 thing to settle in review.** My lean: (a)/(c) — Webull stays for discovery + execution (both reliable REST/trade APIs, both Kev-aligned); Alpaca owns all the *streaming decision data*.

---

## 5. Verification plan (this is what makes the review meaningful — vs "panel signed off")
Every moved line ships with a **fail-without-fix** proof, not a code-order pin (the #89 trap):
- **T2 curl (the flagship):** acceptance = a live `reclaim_shadow_fire`/`triggered_*` row in the archive, AND a per-loop canary logging `len(fed_bars)`, source, last-bar-vol>0. NOT "the code reads ~ALP10S" — an actual fire. (Curl Mechanic law: fire-count is the only acceptance.)
- **T1/T3/T4:** reconciliation gate — Alpaca-sourced price/bars/VWAP vs the Webull value on the same name/minute, deltas explained (Wind Tunnel law 2). T4 specifically vs Kev screenshots (the fidelity gate).
- **Rig:** functional tests with synthetic data proving each consumer reads the Alpaca series and produces a decision (behavioral, synthetic-clock where time-gated — Wind Tunnel 4b / no-feature-ships-unexercised).
- **Grid/threshold changes (open-drive T7):** fine sweep, structural stop, halt-aware (the voided-P&L lesson from today).

---

## 6. Deploy plan
- **Sequence (one line per change-set, through the rig):** T4 VWAP fidelity-check FIRST (already live, validate or revert) → T2 curl feed (the flagship fix, its own acceptance) → T1 price → T3 1-min → T6 daily → T7 open-drive lane (last; biggest new surface, needs the calibration kill-test) → T5 scanner decision (likely no-op if (a)).
- **Timing:** through the rig, deploy at a **flat window** (bot flat; ideally post-close so the next session runs it clean). NOT a rushed mid-RTH push — every rush today (premarket DOA, 429 churn, recorder churn) broke. This is the biggest change of the week; it earns the safe window.
- **Rollback:** per-line `<LINE>_SOURCE=webull` env; the whole thing reverts to today's behavior with env flips, no redeploy.
- **Gate:** tonight's Alpaca full-day 4:00-20:00 ≥98% completeness verdict (#83) — if Alpaca's own capture isn't complete enough, the migration waits (don't move decisions onto an incomplete feed).

---

## 7. Open questions for Fable (attack these)
1. ~~**Scanner (T5):** keep Webull REST for discovery, or build Alpaca-native?~~ **RESOLVED 7/23 (§4):** Alpaca docs — movers endpoint shows prior-day's list until market open, so no premarket discovery. Webull keeps premarket discovery; Alpaca optional for intraday. Fable: confirm you agree Webull-execution + Webull-premarket-screener + Alpaca-streaming-data is the right split, or challenge it.
2. **T4 VWAP fidelity:** is Alpaca SIP VWAP close enough to Kev's Webull line? Needs the screenshot comparison BEFORE trusting. If it drifts, VWAP stays Webull-REST even as bars move.
3. **T1 price latency:** dashboard round-trip (~ALP10S last close) vs direct Alpaca latest-trade REST in the bot — is the round-trip fast enough for stop checks? (stops are the risk-critical path.)
4. **T3 1-min source:** aggregate ~ALP10S→1m (no new data, but depends on 10s completeness) vs Alpaca bars REST (authoritative but another call)?
5. **Completeness dependency:** the whole migration rests on Alpaca ≥98% capture (tonight's #83 verdict). If it's, say, 92%, do we proceed on the reliable-but-incomplete feed, or fix capture first?
6. **Does retiring the bot's WebullStream break anything ELSE** that quietly depended on `_shadow_bars` (the SIGTERM flush, the day-2 observer, archives)? Integrator touchpoint sweep needed before removal.

---

## 8. FABLE REVIEW — 7/23 12:03 ET (checks executed in-transcript, not prose)
**VERDICT: APPROVE DIRECTION — BLOCK T1-as-speced and T2-latency-as-speced. Three amendments required before build.**
Architecture split confirmed (Webull execution + premarket discovery / Alpaca streaming data / one websocket). Root cause verified. But the plan promotes an ARCHIVE pipeline (90s persist, forensics-grade) to LIVE decision duty without a freshness redesign:

| # | Finding | Evidence (executed 7/23) | Amendment |
|---|---|---|---|
| F1 | Dashboard round-trip = 0–90s+ staleness jitter on the hot path | `PERSIST_SECS=90` (alpaca_capture.py:61); live NVVE~ALP10S read measured last bar **389s** behind wall clock (thin-name gaps + persist cycle), fresh on re-read | **A1:** hot-path freshness design — hot-subset cadence (~10–15s) OR bot polls capture's in-memory bars over HTTP (single-connection rule binds the websocket, not REST) OR latency explicitly accepted + measured in DRY_RUN. Decide before build. |
| F2 | Stops on 90s-stale trade prints; capture is **trades-only, no quotes** (:194) — thin-name last-trade can be minutes old while the bid collapses | subscribe payload grep; staleness measurement above | **A2:** stop/monitor price path stays Webull REST/snapshot, or Alpaca REST latest-quote (rate-limit headroom [UNVERIFIED — check first]). NEVER the dashboard round-trip. |
| F3 | Intraday emergers start blind: **NVVE (today's actual trade) first Alpaca bar 11:35 ET, 133 bars** vs EHGO/ADVB 2,624/1,957 from 4:35am. ~ALPVWAP would anchor at subscribe-time = wrong VWAP on every intraday add | /api/bars first/last per name, executed in review | **A3:** on every new subscription, REST-backfill full-day bars + re-anchor VWAP from backfill. T4 fidelity check MUST include an intraday-add case. |

§7 answers: **Q4** = Alpaca REST 1-min (authoritative; same mechanism A3 needs; 10s-aggregation inherits capture gaps). **Q5** = hold ≥98% gate (EHGO computes ~97.8% of theoretical slots — at the line; tonight's verdict decides). **Q6** = blast radius mapped: `_shadow_flush_payload`/`_shadow_dump_eod`/divergence sampler (:766/:827/:1942) become no-ops; Webull `~10s` archive production stops → kill-test harnesses repoint to `~ALP10S`; no hidden trading-path dependency beyond the curl consumers already being repointed. **Q2 (VWAP fidelity)** remains open — screenshot comparison still required, now including an intraday-add name.

_Build may begin once A1's option is chosen (Marcos's call), honoring A2/A3. Per-line env reverts + flat-window deploy + fire-count acceptance stand as written._
