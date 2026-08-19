# CONVENING ARTIFACT — 2026-08-18 evening ship

**HEAD:** `92d9a3662a6d` (code) — IGNITION STACK GATE WAS INERT: premarket warm-up + blindness stamp
**Service:** Marcos-Trading-Bot · **Window:** 18:5x ET, market closed · **Book:** FLAT (0 open
positions, queried in-turn) · **DRY_RUN:** true

## WHAT CHANGES (one behaviour change, one observability change)

1. **Ignition's 3-min stack EMAs are seeded with TODAY'S PREMARKET closes.** The gate
   (`_e9 > 0 and _e20 > 0 and _e9 < _e20`) read EMAs off `full_bars`, which is RTH-ONLY, needing
   66 minutes of RTH — so before ~10:36 ET the EMAs were 0.0 and the gate FAILED OPEN, every day,
   in the window ignition lives in. Seed comes from the PRE+RTH fetch already in hand
   (`ENTRY_VWAP_PREMARKET=True`), cached under its own key.
2. **`stack_src` (warmed|rth_only|unevaluable) + `stack_seed_n` stamped on all 3 ignition
   decision rows.** No behaviour, pure visibility.

**Kill:** `IGNITION_STACK_WARMUP=0` restores the RTH-only (inert) gate exactly.

## EVIDENCE

* Live book, era 7/13+: **79 of 114** stamped ignition fills (**69%**) fired with `ema9==ema20==0.0`.
* `data/killtests/ignition_stack_warmup_20260818.py` — 1,002 detector fires, hold-out 19 unseen dates:

| arm | N=6 $/day | N=8 $/day | $/tr |
|---|---|---|---|
| LIVE_NOW (shipped) | $207.58 | $288.99 | +$31.49 |
| NOSTACK (no gate) | **$207.58** | **$288.99** | +$31.64 |
| WARMED | **$230.78** | **$322.85** | +$40.51 |
| FAILCLOSED | $27.05 | $27.05 | +$36.71 |

LIVE_NOW and NOSTACK are **identical to the cent** — the shipped gate does nothing. WARMED is
+$23.20/day at N=6 and +$33.86 at N=8. FAILCLOSED (−$180.53/day) is why the gate still fails open
when blind: that is a MEASURED choice, not an oversight, and gate 13 pins it.

## BLAST RADIUS

* **Seed isolation:** cached as `ig_pm_closes`, never assigned into `full_bars`/`bars` (gate 13 B2).
  `_ig_comp` is still built from `full_bars` untouched (C1) — the seed feeds EMA MATH ONLY (C2).
  Every other detector (room, setups, candles, volume) sees byte-identical inputs.
* **Consumers of `_e9/_e20/_e90` at this site:** the stack gate and the `_front` print. `_e90` now
  computes only when ≥92 closes exist, else 0.0 — same falsy contract as before.
* **No new API call.** The PRE+RTH fetch already runs on its own TTL for VWAP.
* **Upstream/downstream:** no change to sizing, stops, exits, slots, crowns, or any other lane.
* **Restart:** seed is cache-resident and rebuilt on the next VWAP refresh; a cold boot degrades to
  `rth_only`/`unevaluable` (the old behaviour) and self-heals. No durable state added.

## RIG

Full rig green: `test_shipset_20260804` · gate 10 (extension blindness) · gate 11 (refusal
attribution) · gate 12 (duty watch) · **gate 13 NEW** (`rig/test_stack_warmup_20260818.py`) —
pins the CLASS per `feedback_kill_the_class_not_instance`: kill switch + default, seed isolation,
EMA-math-only, the stamp on all three rows, all three states named, and the deliberate fail-open.

## CORRECTIONS ON THE RECORD

* The **9/20-vs-9/90 verdict reported earlier tonight** ("+$2–3/tr, keep 9≥20") was measured on
  EMAs computed from full tape — a gate that always evaluates. The live gate evaluated 31% of the
  time. **That verdict did not describe the shipped system.** Under the fix the question is
  **UNRESOLVED**: 9/90 wins at N=6 ($249.37 vs $230.78), loses at N=8 ($319.03 vs $322.85). Not called.
* The **lane-reorder verdict** printed earlier is VOID for the CLEAN block (only one lane clears
  90% parity, so every arm is identical by construction). The FULL block finding stands as
  direction only: the live order sits at p18 of a 200-shuffle null.

## OPEN / NOT SHIPPED

* **UNRECONCILED:** this study says 92% of detector *fires* were unevaluable; the live book says
  69% of *fills*. Different populations (fires vs fills; fills skew later). Two measurements, not
  a range. Not reconciled.
* `DEFECT_20260818_cdtg_double_fill.md` — same-second double-fill + 52% VWAP stamp disagreement.
  OPEN, cause unknown, VWAP unadjudicated (no 8/18 SIP cache).
* Marcos's **ignition+9/90-first lane reorder** is MEASURED (best arm: $102.50/day N=6, $161.27
  N=8, +$0.61/tr) but **NOT BUILT** — the two lanes are not adjacent in the source and ema9x90
  needs its own feed hoisted. Nothing shipped for it here.
* `LANE_EXPECTANCY_SORT=0` (Marcos's instruction) not yet applied.

## LIMITS

Detector-only counterfactual; the live funnel (board membership, slots, capital, chart gate,
crowns, priority sort) is NOT modelled, so absolute levels overstate live — the ARMS are the
finding, never the levels. **Ignition's harness parity is UNMEASURED** (no entry in
`harness_parity.json`), so no live-comparable claim is made about its fire counts.

## DOCTRINE-INVERSION SWEEP

Asked of this ship: *what settled belief would have to be WRONG for this to be a mistake?*

* **"A gate that cannot see must not refuse silently"** (the relvol fail-open doctrine) is the
  reason ignition's stack fails open. This ship KEEPS that doctrine but attacks its premise — the
  right answer to a blind gate is to GIVE IT EYES, not to argue about which way it should fail.
  FAILCLOSED was measured (−$180.53/day) rather than assumed, so the doctrine survives on evidence.
* **"Official = RTH"** (`feedback_rth_official_pre_separate`) governs REPORTING. This ship uses
  premarket bars as INPUT to an indicator. Those are different claims and the ship does not blur
  them: no P&L here is premarket-inclusive, and `full_bars` stays RTH-only for everything else.
* **Inversion that would sink this:** if premarket 3-min closes are systematically unrepresentative
  (thin, wide, gappy) the seeded EMAs could be worse than no EMAs. The hold-out numbers say
  otherwise on 1,002 fires, but this is the assumption to watch, and `stack_src` now makes it
  auditable per fire.

## ROLL CALL

* **Blast Radius Auditor** — seed isolation verified three ways (own cache key; never written into
  `full_bars`/`bars`; `_ig_comp` untouched). Consumers of `_e9/_e20/_e90` at this site enumerated:
  the stack gate and the `_front` print. No sizing/stop/exit/slot path touched. CLEAN.
* **Systems Quant** — LIVE_NOW ≡ NOSTACK to the cent is itself the proof the gate was inert;
  reproduced across N=4/6/8. Hold-out is chronological, 19 unseen dates. CLEAN.
* **Statistician** — no grid search; arms pre-registered before the run. FLAG (disclosed): 92%
  (fires) vs 69% (fills) blindness rates are UNRECONCILED and must not be quoted as a range.
* **Wind Tunnel Engineer** — study uses `F.sim_var` E3 verbatim, stop-first intrabar, −1%/−0.5%
  slips; identical across arms so the comparison isolates the gate. CLEAN.
* **Trade Manager** — exits untouched. CLEAN.
* **Execution Surgeon** — no order-path change. CLEAN.
* **Pit Crew Chief** — no new API call (rides the existing PRE+RTH VWAP fetch TTL). CLEAN.
* **Integrator** — one behaviour change + one stamp, single commit, kill switch present. CLEAN.
* **Feed Engineer** — premarket bars come from the same vendor fetch already trusted for the
  session VWAP line; no new vendor surface. CLEAN.
* **Webull Broker Desk** — no broker/account/token change. CLEAN.
* **Quartermaster** — no durable state added; seed is cache-resident and self-heals after restart.
  CLEAN.
* **Dashboard Curator** — `stack_src`/`stack_seed_n` are new row fields; dashboard renders unknown
  fields harmlessly. No cockpit change shipped. CLEAN.
* **Historian** — records that the 9/20-vs-9/90 verdict from earlier tonight is SUPERSEDED and the
  question is reopened, and that the lane-reorder CLEAN-block verdict is VOID. Both written above.
* **First Hour / Opening Bell** — this ship's entire value lands in 09:30–10:36, the window the
  gate could never see. FLAG: it makes the open hour MORE selective; watch tomorrow's fire count.
* **Side Marshal** — EJH was stamped `back_side` and bought anyway; that hole is NOT closed here
  and is logged in the CDTG defect doc as a separate open item.
* **Crown Steward** — crowns untouched; EJH was crowned since 09:37 and still traded badly, which
  is a crown-privilege question this ship does not answer. OPEN.
* **Strength Ombudsman** — the change REFUSES more fires (206 vs 256 hold-out). Interrogated for
  weakness-bias: it raised $/day, so selectivity here is earning, not hiding. CLEAN.
* **Momentum Operator** — nothing shipped on noise; N=1,002 fires. CLEAN.
* **Tape Veteran / Handicapper / Rocket Rider / Convexity Trader / Curl Mechanic** — no change to
  their surfaces (curl feed, hidden, halt ladder, tiers). CLEAN.
* **Reclaim Architect** — reclaim untouched. Notes Marcos's distrust of "VWAP reclaim" was aimed at
  trades that were NOT reclaim fires (kevseq/ma_pullback); reclaim's record is unchanged.
* **Hidden Entry Architect** — hidden untouched here; its failed wall and its top-of-block position
  remain OPEN in the reorder work.
* **Seam Scientist** — no seam change. CLEAN.
* **Cartographer** — no map/level change; EJH's `break_dist_pct −19.51%` is evidence for the
  runway/map question, not addressed here. OPEN.
* **Kev Librarian** — the 9-over-20 stack is Kev doctrine; this ship makes it actually enforceable
  rather than nominal. CLEAN.
* **Forward Architect** — unasked improvement surfaced: the SAME `_e9 > 0`-style guard pattern may
  silently disable OTHER gates. Gate 13 pins the ignition instance; a source-wide census of
  fail-open-when-zero guards is QUEUED, not done.
* **Project Manager** — scope held to the measured fix. The lane reorder Marcos priced is NOT in
  this ship and is called out as unbuilt above.

---

## ADDENDUM — 2026-08-18 second ship, HEAD `1c604923c5a6`

*(sha corrected: an earlier draft of this line carried a MISTYPED sha — read from memory, not from `git rev-parse`. The interlock rejected it. Recorded because a fabricated identifier in an audit trail is worse than a missing one.)*

**PREMARKET IGNITION (07:00-09:25) + THE 9/90 GAP-FILLED WARM-UP** (Marcos: "ignition for both
pre and RTH, have 9/90 running in pre but not trade until 9:30").

**Changes:** (1) ignition's hand-written `m < 570` premarket skip removed, gated by IGNITION_PRE
with a 07:00-09:25 window, its own premarket open anchor, and a >=50% tape-coverage eligibility
rule; (2) the 9/90 accumulates a gap-filled 1-min series from premarket (warm at the bell on 93%
of name-days vs 69%) and still fires only from EMA9X90_OPEN 09:30; (3) its session window is now
judged from the BAR clock, not `datetime.now()`.

**Evidence (hold-out, 19 unseen dates; PRE on its own line, never summed with RTH):** ignition
07:00 +$10.58/tr green 58% PASSES vs 08:00 -$10.22/tr green 12% FAILS; coverage split >=50%
+$14.52/tr vs <50% -$8.56/tr; 9/90 gap-filled +$14.68/tr green 61% vs cold +$11.75/61%->56%, and
the 9/90 IN premarket measured -$4.49/tr green 26% and is therefore REFUSED (warm-up only).

**Kill switches:** `IGNITION_PRE=0`, `EMA9X90_WARMUP=0` — each restores prior behaviour exactly.

**Blast radius:** premarket branch is additive and gated; the RTH open anchor, `st["openp"]`, and
every RTH path are untouched (gate 14 A6). The 9/90's warm-up feeds EMA math only; its fire
conditions are unchanged. No sizing/stop/exit/slot change. No new API call.

**Two defects found by EXERCISING, not reading:** the coverage ratio exceeded 100% (median 101%,
off-by-one in elapsed minutes) and the 9/90's window read wall-clock, firing 30x pre-09:30 and at
18h/19h under replay. Both fixed and pinned.

**Harness:** `ema9x90_step` was not in the isolated namespace — the lane shipped 8/18 12:43 and
was NOT liftable/exercisable/parity-measurable at all. Now registered.

**RIG:** gate 14 `rig/test_pre_lanes_20260818.py`, 19 pins. Full rig green (shipset + 10/11/12/
13/14 + gates 5-9).

**ROLL CALL (addendum):** Blast Radius Auditor — additive/gated, RTH untouched, CLEAN. Systems
Quant — both bugs reproduced and fixed, CLEAN. Statistician — FLAG: premarket P&L came from a
STUDY REIMPLEMENTATION; the shipped detector's premarket output is NOT yet re-measured. First
Hour/Opening Bell — the 9/90 is now live AT the bell (12 first-fires in the 09h bucket vs
earliest 10:59 before). Feed Engineer — premarket bars ride the existing PRE+RTH fetch. Trade
Manager/Execution Surgeon — exits and order path untouched, CLEAN. Wind Tunnel Engineer — lane
now liftable, so it can finally be tested. Historian — records that the 9/90's wall-clock window
was live and unexercised for one session. Quartermaster — no durable state. Dashboard Curator —
new row fields (sess, pre_cov, warm_pre, warm_src) render harmlessly. Side Marshal, Crown
Steward, Kev Librarian, Seam Scientist, Strength Ombudsman, Momentum Operator, Tape Veteran,
Handicapper, Rocket Rider, Cartographer, Convexity Trader, Curl Mechanic, Reclaim Architect,
Hidden Entry Architect, Webull Broker Desk, Pit Crew Chief, Integrator, Forward Architect,
Project Manager — no surface touched, CLEAN.

**DOCTRINE-INVERSION (addendum):** "Official = RTH" governs REPORTING; premarket P&L here stays
on its own line and is never summed. The inversion that would sink this: if premarket prints are
too thin/wide to fill, the measured edge is fiction — which is exactly why the coverage floor is
an eligibility rule and why the RTH slip model applied to premarket is disclosed as FLATTERING.

**OPEN:** the shipped detector's premarket numbers are NOT re-verified through the real function
(owed). Ignition harness parity still UNMEASURED. The 92%-vs-69% blindness reconciliation still
open. CDTG double-fill defect still open.


---

## ADDENDUM 2 — 2026-08-18 third ship, HEAD `9319f91abf16`

**THE VWAP INTEGRITY BATCH.** Three commits: `b67f5df` (coverage guard), `3091986` (watchdog +
provenance stamps + nightly wiring), `9319f91abf16` (skip split to observe-only).

**Why it ships tonight and not tomorrow:** the running bot already has premarket ignition and the
9/90 warm-up, but NOT this. `hidden_entry` and `kevseq` — the two lanes carrying 55 of the 60
measured VWAP breaches — trade tomorrow morning with the broken adjudication intact.

### What changes
1. **`_vwap_coverage_min` / `_vwap_bar_trusted`** — a bar line is authoritative only if it starts
   at/near the open (<=09:31) or spans >= `VWAP_MIN_SPAN_MIN` (20) minutes. Premarket exempt.
2. **`_tick_vwap_ok(..., bar_trusted)`** — when the reference FAILS its own coverage test,
   divergence from it is evidence FOR the tick line, not against it. The catastrophe band vs
   price still applies unconditionally.
3. **Provenance on every trade record**: `entry_vwap_span_min`, `entry_vwap_first_hm`,
   `entry_vwap_trusted`.
4. **Nightly watchdog** (`data/killtests/vwap_audit.py`) wired AHEAD of the ledger verification.

### Evidence
Adjudicated against 310,022 harvested SIP ticks (CDTG 8/18 14:16:43): the true session VWAP was
**$4.6719** (PRE+RTH anchor, matching ma_pullback's stamp to 4dp); kevseq stamped **$7.11**,
matching no anchor — a ~2.5-minute rolling average (it sits between the 2-min $7.2673 and 3-min
$7.0244 windows). Through the bot's own functions: truncated set (span 2.0m) -> untrusted -> the
correct tick line SURVIVES -> the gate reads **+66.53%** instead of +9.42%. Session-spanning set
(span 399m) -> trusted -> the 5% clamp still fires (no-op control).

**Watchdog first run, era 7/13+, 178 of 261 stampable rows graded (68% coverage):
60 BREACHES** — hidden_entry 52/112, kevseq 3/3, ma_pullback 1/15; ignition 0/20, flat_top 0/15,
vwap_reclaim 0/7 clean. Severity: 60 at 3% tolerance, 37 at 10%, **20 at 20%**; median miss 13.6%.

### Risk split (the reason this is safe to ship at 23:00)
The guard's MEASURED half (prefer the tick line when the bar fails coverage) is **ON**. The
UNMEASURED half (skip the ticker when both lines are unusable) ships **OBSERVE-ONLY**
(`VWAP_UNTRUSTED_SKIP=0`): the row is logged with span/first/need/enforced and the ticker still
trades. Its live frequency is unknown, and on a proving-week morning an uncounted skip could
sideline real names. Gate 15 pins that the measured half is ON and the unmeasured half is OFF.

**Kill switches:** `VWAP_COVERAGE_GUARD=0` (whole guard), `VWAP_UNTRUSTED_SKIP=1` (enable the
skip once counted).

### Blast radius
Additive. `_tick_vwap_ok` keeps a default `bar_trusted=True`, so any un-migrated caller behaves
exactly as before (pinned). Coverage is stamped at both compute sites and read via `.get()`, so a
missing key degrades to "unmeasurable -> trust", never to stricter behaviour. No sizing, stop,
exit, slot or lane-logic change. The clean lanes (ignition/flat_top/vwap_reclaim) are unaffected
by construction — they never went through the `_vr_sv` path.

### RIG
Gate 15 (`rig/test_vwap_coverage_20260818.py`), 18 pins incl. both no-op controls, the
catastrophe band, the default-arg legacy path, and the observe-only default. Full rig green:
shipset + gates 10/11/12/13/14/15 + gates 5-9. The VWAP chain is now registered in the harness
namespace — it was NOT liftable before, so this class was untestable.

### ROLL CALL (addendum 2)
**Blast Radius Auditor** — additive, default-arg preserves legacy, clean lanes untouched, CLEAN.
**Systems Quant** — adjudication verified on the real values both ways (fix + no-op), CLEAN.
**Statistician** — FLAG: the 3% tolerance conflates tick-vs-bar timing noise with corruption; the
defensible core is the 20 rows breaching at 20%. Coverage (68%) printed on every run.
**Feed Engineer** — the recorder tick series held the CORRECT value throughout; this stops the
system discarding it. CLEAN. **Wind Tunnel Engineer** — the class is testable for the first time.
**Historian** — records that "1 event in 437 rows" described the DOUBLE-FILL; the wrong VWAP is 60
events, and the earlier statement is corrected. **Quartermaster** — FLAG: the 10s cache is not
auto-maintained (harvester.py is a one-shot backfill); `harvest_day.py` added, nightly harvest
still FAILS under launchd for want of credentials — an OPEN scheduler gap, not fixed here.
**Trade Manager / Execution Surgeon / Pit Crew Chief / Integrator / Dashboard Curator / Webull
Broker Desk / Side Marshal / Crown Steward / Kev Librarian / First Hour / Opening Bell / Seam
Scientist / Strength Ombudsman / Momentum Operator / Tape Veteran / Handicapper / Rocket Rider /
Cartographer / Convexity Trader / Curl Mechanic / Reclaim Architect / Hidden Entry Architect /
Forward Architect / Project Manager** — no surface touched, CLEAN. **Hidden Entry Architect**
additionally FLAGS that hidden's wall verdict read 52 breached rows and is now SUSPECT.

### DOCTRINE-INVERSION
"A gate that cannot see must not refuse silently" (the relvol fail-open doctrine) argued for
trusting whatever line exists. This inverts it for a REFERENCE: a line that cannot prove it spans
the session must not be treated as authoritative. Both survive because they answer different
questions — one is about refusing trades, the other about ranking sources.
**What would sink this:** if `vwap_span_min` is frequently unmeasurable, the guard degrades to
"trust" and does nothing. That is the failure mode to watch, and the reason provenance is now
stamped on every row.

### OPEN
Nightly harvest credentials (launchd); the CAUSE of truncated bar sets; the 60 historical rows
are uncorrected and every study reading them inherits the values — **hidden's failed wall
specifically must be re-graded**; the CDTG double-fill cause; the 92%-vs-69% reconciliation.


### CORRECTION (23:0x, post-ship) — hidden's wall was NOT contaminated

Addendum 2's roll call recorded: *"Hidden Entry Architect additionally FLAGS that hidden's wall
verdict read 52 breached rows and is now SUSPECT."* **That flag was WRONG.**
`hidden_wall_20260818.py` reads NO live rows (grep: api/trades / entry_session_vwap / dashboard
= 0 hits) and builds its VWAP from tape. The 60 bad stamps never entered it. I asserted
contamination without checking the study's own VWAP source — and committed it into an audit doc.

A REAL but smaller defect did surface: the wall anchored VWAP at 09:30 (RTH-only) while the live
bot anchors at 04:00 (ENTRY_VWAP_PREMARKET=True). Hidden's gate is VWAP-relative, so the study
was not modelling the bot. Regraded on both lines
(`data/killtests/hidden_wall_regrade_20260818.py`, hold-out 20 unseen dates):
    RTH anchor  -$9.59/tr  n=1719   |   PRE+RTH anchor (live)  -$10.55/tr  n=1917
**VERDICT STANDS** — correcting the anchor makes it slightly WORSE. Hidden loses money on the
line the bot actually uses.

Reconciliation: the original wall reported -$10.21/tr on the RTH arm; this run shows -$9.59
because tonight's harvest grew the universe from 736 name-days/63 dates to 935/64. Same
direction, same verdict, different denominator.


---

## ADDENDUM 3 — 2026-08-18 dashboard ship, HEAD `caa199834aac`

**THE ACCOUNTING FIX.** Marcos: *"your accounting for today is still not adjusted from what you
said earlier."* He was right. This morning's SXTC correction (two tier banks lost on a resumed
monitor, both verified on SIP tape) went into `RESULTS_LEDGER.md` and NOWHERE the system reads.
The store held `pnl -7.62`; the dashboard and the nightly log both still showed RTH **-$18.00**.
A correction that lives only in a markdown file is a note about a correction, not one.

**Service:** `dashboard/ scanner` · market CLOSED (23:1x ET) · book FLAT, verified in-turn.

**Change:** one entry appended to the P&L correction ledger
(`data/killtests/pnl_runner_leg_correction_20260726.json`), which `screener_app.py:163` merges
**AT RENDER, store untouched** — the 7/26 precedent.
`trade_id 335b694af972410fa0653dea25ec0ab1` SXTC 2026-08-18, stored `-7.62` -> corrected
`+21.89` (delta `+29.51`), class `TIER_BANKS_LOST_ON_RESUME`.

**AFTER-STATE, written before running (7/24 wipe law) then verified against the live book:**
file 193 -> 194 entries, nothing removed or overwritten · RTH n=11 **-$18.00 -> +$11.51** ·
PRE n=1 **-$13.29 unchanged** · the stored row keeps `pnl -7.62`, no trade record mutated ·
PRE and RTH stay on separate lines and are never summed.

**Blast radius:** render-only. No trade record, no bot code, no lane logic, no sizing/stop/exit.
The bot service is not redeployed by this. If the ledger file fails to load, `screener_app`
already degrades to STORED pnl with a printed warning (pre-existing behaviour, unchanged).

**ROLL CALL (addendum 3).** **Historian** — the official 8/18 day record is RTH +$11.51 / PRE
-$13.29, and it now renders that way rather than only asserting it in a doc. **Blast Radius
Auditor** — render-only, store untouched, CLEAN. **Systems Quant** — AFTER-state pre-declared and
then verified against the live book, CLEAN. **Statistician** — one record, no sampling claim.
**Quartermaster** — the correction ledger ships with the image; store integrity preserved by
construction. **Dashboard Curator** — the cockpit now matches the verified record. **Trade
Manager** — FLAG: the CAUSE is unfixed (a resumed monitor does not rebuild `partial_fills` from
durable `tier_fill` rows; era sweep 2/188 fills, 1 day of 27). **Execution Surgeon / Pit Crew
Chief / Integrator / Feed Engineer / Webull Broker Desk / Side Marshal / Crown Steward / Kev
Librarian / First Hour / Opening Bell / Seam Scientist / Strength Ombudsman / Forward Architect /
Momentum Operator / Tape Veteran / Handicapper / Rocket Rider / Cartographer / Convexity Trader /
Curl Mechanic / Reclaim Architect / Hidden Entry Architect / Project Manager** — no surface
touched, CLEAN.

**DOCTRINE-INVERSION.** "STORED P&L IS WRONG — use the ledger" says corrections live in a file
and the store is never rewritten. That doctrine is KEPT here — but tonight exposed its failure
mode: a ledger nobody wires up is invisible. The inversion that would sink this is if
render-time correction lets stored data rot untracked; the answer is that the CAUSE stays open on
the punch list, and the correction carries its own `why` and class in the record.

**OPEN:** the resumed-monitor `partial_fills` rebuild (the actual defect); the nightly ledger line
still prints a MERGED figure (`"12 trades raw $-31.29"`), violating the PRE/RTH separation into a
durable log every night — found tonight, NOT fixed.


### ADDENDUM 3b — build-bump so the correction actually ships, HEAD `5cb1005c4df9`

Addendum 3's deploy did NOT reach the service. Railway returned **SKIPPED** — *"No changes to
watched files"* — because the correction is a JSON under `data/`, not a watched path; then
`railway redeploy` re-ran the **01:16** image. The boot log kept printing *"P&L display
correction loaded: 36"* (my entry makes it 37), so RTH stayed at -$18.00 through three deploy
attempts and eight polls.

**Change:** one comment appended to `screener_app.py` (a watched file) to trigger the build —
the same mechanism the existing 7/26b bump comment was written for. No behaviour change; the
file is otherwise untouched.

**Blast radius:** a comment. Render-only correction path unchanged, store untouched, no bot
service involved.

**DEFECT LOGGED (not fixed):** `ship.sh` prints "✅ shipped" whenever `railway up` exits 0 and
never checks the deployment STATUS — so a SKIPPED build reports as a successful ship. That is
how the 23:11 dashboard ship was reported green while nothing was built. It would do the same
for the bot. Fix belongs on the ship path, not here.

**ROLL CALL (3b).** Blast Radius Auditor — comment-only, CLEAN. Integrator — FLAG: the ship path
cannot distinguish SKIPPED from SUCCESS. Dashboard Curator — the glass still shows the stale
figure until this lands; verification is `pnl_correction_applied == 37` and RTH == +$11.51.
Pit Crew Chief — three wasted deploys traced to watchPattern scope. Historian — records that a
data-only correction requires a watched-file touch in this project. All other officers: no
surface touched, CLEAN.

**DOCTRINE-INVERSION:** "verify before speak" applied to DEPLOYS as well as claims — an exit code
is not evidence that a deploy happened. Tonight it was not.


### ADDENDUM 3c — the correction was HALF applied, HEAD `fa2dcf78879f`

Marcos, reading the corrected row on the dashboard: SXTC rendered **"+$21.89 / -1.5%"** — a row
that contradicts itself. The render-time correction patched `pnl` and left `pnl_pct` derived from
the stored entry->exit legs (4.60 -> 4.53 = -1.52%). Dollars from the tape-verified ledger,
percent from the corrupted legs, on the official day record.

**Change:** when a row is corrected, `pnl_pct` is recomputed on the same basis every other row
uses — `pnl / position_size` (PFSA 48.76/175.50 = +27.8%, matches the glass). SXTC becomes
**+4.37%**. Prior value preserved as `pnl_pct_stored`. Store still untouched; render-time only.

**How it was found:** not by any check of mine. I verified the DOLLAR total reconciled to
+$11.51 and stopped. A correction is not verified by its headline agreeing — every field it
touches, and every field DERIVED from what it touches, has to agree too.

**Blast radius:** the `pnl_corrected` branch only, which today matches 37 records. Rows without a
correction are byte-identical. Guarded on `position_size > 0`.

**ROLL CALL (3c).** Blast Radius Auditor — one branch, guarded, CLEAN. Dashboard Curator — the
glass no longer shows a self-contradicting row; verify SXTC reads +$21.89 / +4.37%. Statistician
— FLAG: this makes the percent basis explicit (P&L over position size, not entry->exit move);
the two differ whenever partial fills exist, which is exactly the SXTC case. Historian — the
official 8/18 record is RTH +$11.51 / PRE -$13.29 with SXTC +$21.89 / +4.37%. All other
officers: no surface touched, CLEAN.

**DOCTRINE-INVERSION:** "the store is never rewritten, corrections live at render" is kept — but
tonight showed its failure mode twice: a ledger nobody wired up (3), and a correction that
patched one field while a derived field kept the old story (3c). A render-time correction must
carry every field the corrected value implies.


---

## ADDENDUM 4 — the SXTC defect, fixed at the cause. HEAD `2c408adc7c22`

Marcos identified it: *"wasnt it the restart?"* Confirmed — `trade_resumed SXTC` at **10:07:42**,
one of four resumes triggered by the **10:05 intraday deploy**.

**Defect:** the resume path trusted `resume_state["partial_fills"]` alone. Empty snapshot -> two
banked legs gone -> the whole 109sh marked out at the final exit: **-$7.63** recorded against a
true **+$21.89**. $29.51 on one trade; the day's headline read -$18.00 instead of +$11.51.

**The legs were never lost** — verified against the live ledger this turn:
`tier_fill 10:28:56 qty=54 price=4.8207` and `tier_fill 10:30:58 qty=27 price=5.0415`. Durable,
carrying qty AND price, independently confirmed on SIP tape. Nothing read them back.

**Fix:** `_tier_fills_from_ledger(ticker)` (modelled on the proven `_leader_rehydrate`). On
resume, if the LEDGER knows about more legs than the snapshot, the ledger wins and
remaining_shares / tier_idx / partial_taken are recomputed. One-directional by design: a snapshot
AHEAD of the ledger is kept (a ledger post may be in flight). Read failure -> `[]`, never
invented legs. `trade_resumed` now stamps `tier_rehydrated` / `ledger_legs` / `banked`.

**Verified by replaying the ACTUAL failure** through the fix's code path with the real rows:
snapshot 0 legs, ledger 2 -> rebuilt -> remaining 28/109 -> banked +$23.84 + runner -$1.96 =
**+$21.88** vs tape-verified **+$21.89**. The unfixed path reproduces **-$7.63**.

**Blast radius:** the resume branch only. A fresh trade never calls it. One HTTP GET, guarded, on
resume only — no scan-loop cost. Kill: `TIER_REHYDRATE=0`.

**RIG:** gate 16, 15 pins. Full rig green (shipset + 10-16 + gates 5-9).

**ROLL CALL (4).** Blast Radius Auditor — resume-only, guarded, CLEAN. Systems Quant — the real
failure replays to the correct number both ways, CLEAN. Trade Manager — the banked-leg accounting
is now recoverable; FLAG: the CAUSE of the empty snapshot is still untested. Execution Surgeon —
no order path change. Quartermaster — the durable ledger is now actually load-bearing, as it was
always meant to be. Historian — records that SXTC's true P&L is +$21.89 and the mechanism is a
restart artifact, not a lane fault. Pit Crew Chief — FLAG: three of four restarts today were
INTRADAY DEPLOYS; the cheapest prevention is not shipping mid-session. Dashboard Curator — new
stamps render harmlessly. Statistician — n=1 instance, class-level fix; no sampling claim. All
other officers — no surface touched, CLEAN.

**DOCTRINE-INVERSION:** "painless restarts" (#35) assumed the saved snapshot was sufficient state.
Tonight showed it is one source, not the truth. The inversion that would sink this fix: if the
ledger itself can be wrong or late, adopting it could corrupt a good snapshot — which is exactly
why the rule is one-directional and only ever ADDS legs the snapshot lacks.

**OPEN:** why the snapshot came back empty; the CDTG double-fill (NOT a restart — last restart
12:47, 90 min before, and the name traded normally at 12:59 after it); ship.sh SKIPPED-vs-SUCCESS;
the merged nightly ledger line.
