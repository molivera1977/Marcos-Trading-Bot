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
