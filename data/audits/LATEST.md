covers: 3ad5c50
# SHIP CONVENING — 2026-08-17 (Mon 02:44 ET) — seq doctrine build #0: canonical `seq_str` event-string stamp on every eyes block (OBSERVE-ONLY) + rig section AI

covers: 3ad5c5030773 "seq doctrine build #0: canonical seq_str event-string stamp on every eyes block (observe-only) + rig AI" — ONE commit, two files: marcos_trading_bot.py (+91: `_seq_events(d10,vwap)` pure helper + 7 SEQ_* constants + `snap["seq_str"]` stamp in `_eyes_snapshot` + "seq_str" in `_EYES_KEYS` + "seq" in `_eyes_compact`), rig/test_shipset_20260804.py (+41: new section AI, 8 checks). Prior audited code: 197ed0d (two PRE convert paths, archived LATEST). HEAD == the ship (3ad5c50). Working tree: one stray EMPTY untracked file `data/killtests/seq_err.txt` (0 lines, not part of the commit, no code delta) — noted, ignored.
Chair: Blast Radius Auditor. Separate-context convening. Every claim below is from a `git show`/file read or an execution run THIS session. Clock: `date` run this turn = Mon Aug 17 02:44:47 EDT 2026 (Monday premarket boot ~03:55 ET; ~1h10m runway). No push, no deploy, no env flip from this convening.

## SHIP DESCRIPTION + AUTHORIZATION
Stamps a causal 10s-bar EVENT-STRING (alphabet B/T/P/F/W/H/R/D/L/Q, one event per bar by priority, up to 14 trailing events over a 10-min lookback) onto EVERY lane's eyes snapshot at BOTH entry and exit. It is the live-tape record the per-lane sequence-mining reads; it mirrors the offline miner so live and backtest strings compare.
Authorization class: **OBSERVE-ONLY, write-only field.** No env, no gate, no conversion, no sizing, no exit change. Nothing the bot DOES with money changes. Under auditor-cannot-authorize (8/13) this class is always safe to ship without a Marcos money-decision — a stamp that no code path consumes for a decision needs no behavior authorization. GREEN by class, verified below not assumed.

## FINDINGS (each verified by direct read/execution this session)
1. **Truly observe-only — the new `seq_str` is WRITTEN, never READ by any gate/convert/sizing/exit.** `grep -n seq_str marcos_trading_bot.py` = 9 hits. Three belong to the NEW canonical stamp: `_EYES_KEYS` tuple (:9579, registration), the snapshot write `snap["seq_str"] = _seq_events(...)` (:9872), and the compact carry `"seq": snap.get("seq_str")` (:9890 — a DISPLAY dict, not a decision). The `snap.get("seq_str")` at :9890 is the ONLY read of the canonical field and it only copies the string into the compact eyes block for the record. No `if snap.get("seq_str")`, no comparison, no branch. The remaining hits (:6130, :7900, :7918, :7924, :7929) are the PRE-EXISTING KEVSEQ lane-row `seq_str` (`"B " + pd["kind"]`, the kevseq fire dict / kevseq_shadow rows) — a distinct, older mechanism on its own lane; untouched by this diff and distinguished by name (`_ksf`, `kevseq`, `pd[...]`).
2. **No SEQ_CONVERT / SEQ_GATE symbol exists.** `grep "SEQ_"` returns only the new module constants (SEQ_MAX_EVENTS/LOOKBACK_S/FLUSH_PCT/TEST_BAND/Q_PCT/Q_BARS/HALT_GAP) and the pre-existing `KEVSEQ_*` family (KEVSEQ_CONVERT etc., word-boundary distinct). Rig AI asserts `not \bSEQ_CONVERT\b and not \bSEQ_GATE\b` — GREEN. There is no behavior symbol; the alphabet constants only shape the string.
3. **Double fail-soft — `_eyes_snapshot` cannot raise from this stamp.** `_seq_events` (:9640) is `try/except Exception: return ""` around its whole body (empty/None/short tape → early `""`). Independently, the call site (:9871-9874) is itself wrapped: `try: snap["seq_str"] = _seq_events(...) or None / except Exception: snap["seq_str"] = None`. Two independent guards; a raise inside `_seq_events` still lands as `snap["seq_str"]=None`. `_eyes_snapshot` therefore never raises on account of this ship — the invariant that entry/exit records depend on holds. Rig AI: `seq({})==""` and `seq(None)==""` GREEN.
4. **No upstream charge — reuses the already-fetched `d10`.** The stamp passes `d10` (built at :9734/:9738 earlier in `_eyes_snapshot`) into `_seq_events`; it opens no new feed pull, no HTTP GET, no bar fetch. `vwap` is read from the snap already computed. Latency = a pure loop over ≤60 in-memory bars. Zero feed-side blast.
5. **Twin covered — the compact eyes path carries it.** The second eyes surface, `_eyes_compact` (:9878), was extended to `"seq": snap.get("seq_str")` (:9890). Every one of the 7 `_eyes_compact(_eyes_snapshot(...))` call sites (:7730/7789/7838/7914/7947/8251/8826) therefore surfaces the field on the recorded compact block. No eyes path left stale.
6. **Whole sandwich — entry AND exit both stamp.** `seq_str` is stamped unconditionally inside `_eyes_snapshot`, which is the single choke point for BOTH `when="entry"` and exit snapshots. Because it lives in the shared body (not in a when-branch), every entry record and every exit record gets the field. Commit body's "entry AND exit" claim confirmed by construction.
7. **Restart / schema tolerant.** `seq_str` is one more optional key in the eyes dict — a `str` or `None`. It does not enter the open-trade state, the rehydrate/resume path, or any trade-record required-field set; consumers read the eyes block as a loose dict (`.get`), so an added key breaks no rehydrate of an in-flight trade and no schema. Restart semantics unchanged.
8. **Strength/weakness bias: n/a** — a descriptive event-string stamp makes no admit/refuse decision, so it cannot bias toward or against strength.
9. **Rig executed MYSELF**: `python3 rig/test_shipset_20260804.py` → **ALL GREEN, exit 0**, incl. the new **section AI** (8/8 green: fail-soft empty/None → "", break-of-session-high emits B, ≥60s gap emits L, seq_str in _EYES_KEYS, snapshot stamps it, compact carries it, no NEW behavior symbol, canonical footprint ≤4 write-only code sites). Standing pin sections all green; section Q flags HEAD "NOT yet audited" — this artifact closes that interlock.

FIX-NOW LIST: none.

## DAY-ONE WALKTHROUGH (Monday 8/17, unchanged env, DRY_RUN=true)
- **Boot ~03:55 ET**: no new env, no banner change (observe-only ship registers no config flag). All lanes arm exactly as before.
- **First PRE fire (any lane — hidden_entry / vwap_reclaim / a converted PRE lane)**: at the fire, the lane calls `_eyes_compact(_eyes_snapshot(t, px, "entry", extra))`. Inside `_eyes_snapshot`, `d10` (already built for the other eyes) is handed to `_seq_events`; on a real premarket break-and-hold specimen the loop emits e.g. `"... P T B H"` and `snap["seq_str"]` = that string; the compact block carries `"seq": "... P T B H"`. The entry record persists it as a first-class eyes key. On too-little tape (cold open, <6 bars) it is `None` — the record still writes, nothing stops it.
- **Exit of that same trade**: the exit snapshot runs the identical stamp → the exit eyes block carries its own `seq_str`. Both legs of the sandwich populated.
- **What consumes it**: only the recorder (writes the key) and any offline sequence-miner reading rows later. No live consumer branches on it. If `_seq_events` had thrown, the field is `None` and the trade records exactly as it would have pre-ship. The promised row (an eyes block with a populated `seq` on a real fire) is produced; nothing downstream is intolerant of the new key because every consumer reads the eyes dict via `.get`.

## DOCTRINE-INVERSION SWEEP
The sequencing doctrine ("one element alone signals nothing; it's the ORDER") is newly ledgered, and this ship FOLLOWS that doctrine — so the sweep is mandatory. Result: this ship changes **no** who-rules / what-gates / what's-exempt. It adds a descriptive field and consumes nothing for a decision. There is therefore no OLD-doctrine code path made stale by it: no gate was repealed, no lane's authority moved, no exempt set changed (grep of MIN_STOP_EXEMPT/BACKSIDE_EXEMPT/VRIDE_EXEMPT/_STALE_EXEMPT shows no `seq`-keyed member — it is a field, not a lane). The pre-existing KEVSEQ lane and its `KEVSEQ_CONVERT` flag are untouched and remain the ONLY place a sequence idea reaches money, still env-OFF; this build does not promote the canonical string into that decision. **doctrine-inversion sweep: additive-only, no stale old-doctrine path — build #0 lays the observation substrate; any future gate that reads `seq_str` for a decision is a SEPARATE ship that returns to Marcos priced.** The string "doctrine-inversion" is present as required.

## ROLL CALL (every office on ROSTER.txt)
- **Blast Radius Auditor** — TOUCHED, chair. Verified write-only, double fail-soft, twin+sandwich+restart clean. Finding: none blocking. GREEN.
- **Dashboard Curator** — TOUCHED (finding, non-blocking): `seq` now rides the compact eyes block; the cockpit does not yet render it. Display of the new field is queued, not owed for this observe-only ship.
- **Systems Quant** — TOUCHED: confirmed `_seq_events` computes what its name claims (causal single-pass, one event/bar by priority B>F>W>T>R>H>P>D, trailing Q, L on gap); pure, no lookahead beyond the current bar. Clean.
- **Pit Crew Chief** — clean: no deploy-safety surface — no env, no new failure domain; the only new raise-path is contained by two try/excepts.
- **Integrator** — TOUCHED: both eyes seams (full snapshot + compact) wired; all 7 compact call-sites carry the key. No orphaned seam. Clean.
- **Side Marshal** — clean: front/back-side classifier untouched; the string records events, does not re-decide side.
- **Crown Steward** — clean: crown privileges untouched.
- **Feed Engineer** — TOUCHED: confirmed NO new feed call — reuses the already-fetched `d10`. Zero vendor charge. Clean.
- **Webull Broker Desk** — clean: no order semantics, no BP, no token surface.
- **Quartermaster** — clean: no new persisted store; `seq_str` rides the existing eyes/record schema, backup path unchanged.
- **Kev Librarian** — TOUCHED (finding, non-blocking): the alphabet mirrors kev_rosetta_20260816.md and the offline miner; the two MUST stay in lockstep or live/backtest strings diverge. Flagged to keep the miner refactored to call THIS helper (commit says "to be refactored to call THIS").
- **First Hour** — clean: no 9:30-10:30 P&L behavior change.
- **Opening Bell** — clean: pre-open path unchanged; the stamp just records what the lead-up looked like.
- **Seam Scientist** — TOUCHED (positive): this substrate directly feeds the beginning-entry research program — the exact live event-string the seam study needs. Observation only, no premature gate.
- **Strength Ombudsman** — clean: no admit/refuse decision, no bias surface.
- **Forward Architect** — clean: registered as build #0 of a hypothesis line; the kill-test (does a sequence gate beat don't-trade) is a FUTURE ship, not this one.
- **Momentum Operator** — clean: nothing ships on noise; this ships on nothing at all (observe-only).
- **Trade Manager** — clean: exits unchanged; exit eyes merely also stamp the field.
- **Tape Veteran** — clean: outside-auditor hypotheses only; no objection to a descriptive record.
- **Reclaim Architect** — clean: reclaim lane entry logic untouched; it merely stamps seq_str via the shared snapshot.
- **Execution Surgeon** — clean: planned-R = realized-R untouched; no sizing/stop path reads the field.
- **Handicapper** — clean: selection/character-book untouched.
- **Rocket Rider** — clean: parabolic regime handling untouched.
- **Cartographer** — clean: map quality untouched (`_EYES_MAP_KEYS` unchanged).
- **Wind Tunnel Engineer** — TOUCHED (finding, non-blocking): backtest fidelity depends on the offline miner emitting the SAME alphabet as `_seq_events`; same lockstep flag as Kev Librarian. No fidelity break in THIS ship (no backtest path changed).
- **Statistician** — clean: no results-ledger write; the field is raw observation, not a computed result claim.
- **Convexity Trader** — clean: no P&L/tail-shape surface.
- **Curl Mechanic** — clean: reclaim/zone-flip fire-count acceptance untouched.
- **Project Manager** — TOUCHED: this convening + rig-green is the [VERIFIED] artifact for the ship; observe-only, no scorecard impact.
- **Historian** — TOUCHED: recorded as "seq doctrine build #0 — canonical live event-string substrate, observe-only, 3ad5c50, rig-green".
- **Hidden Entry Architect** — TOUCHED (positive): the v2 rebuild's anticipation-not-confirmation work gains a per-bar event record for anatomy; observation only, no v2 behavior change here.

## VERDICT
**GREEN — safe to deploy.** The ship is genuinely observe-only: the new canonical `seq_str` is written in the shared eyes choke point and read in exactly one place (the compact display copy), never by a gate, conversion, sizing, or exit path; no SEQ_CONVERT/SEQ_GATE symbol exists; `_eyes_snapshot` cannot raise from it (two independent try/excepts); no new feed call, both twins and both sandwich legs covered, restart/schema tolerant. Rig section AI 8/8 green, full suite exit 0. No blocking finding. No push/deploy/env change performed by this convening — the main session ships.
