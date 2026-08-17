covers: 5d58e42894e1
# BLAST RADIUS CONVENING — 8/17 BATCH 2 (tape-lane scalar exemption + crown visibility)
Auditor: Blast Radius Auditor (separate context). Tree audited: 5d58e42 (tip) = e5f59fe (batch-1,
audited GREEN in the prior convening, preserved below) + 173d8f1 (batch2-A) + cdbe7d4 (batch2-B)
+ 5d58e42 (scope-doc append, docs-only). Scope: PENDING_CONVENE_20260817.md items A/B. Context
read: scalar_veto_tape_lanes_20260817.md, crown_pipeline_forensic_20260817.md. Full rig executed
THIS convening: EXIT 0, ALL GREEN, 498 green checks; sections AL and AM present AND executed
(per-check lines observed; judged by exit code). SHIP_CHECK=1 pre-artifact: RED on section Q
only (tip 5d58e42 not yet covered — the designed interlock); post-commit rerun appended at
bottom.

## VERDICT: GREEN — deploy may proceed on Marcos's word (book-flat rule + no-RTH-push law
still govern the ship itself). No code blockers. One doctrine finding (B2-F1, extension gate)
and the standing pricing items go to Marcos first — his call under auditor-cannot-authorize.

## MONEY-BEHAVIOR STATEMENT (batch 2's only money change = TAPE_LANE_SCALAR_EXEMPT)
**What it can now let through:** a kevseq / v2conv / grinder / bandpass / prevwap fire that
reaches the worker momentum gate and fails ONLY the refuted "no momentum build" expansion /
peak-relative scalar now proceeds to entry instead of dying at momentum_reject. Evidence is
N=1 (WETO 8/17 10:18:37 kevseq @ $19.495; E3 live-parity counterfactual +$25.14) — the weight
is doctrinal: settled 7/26 law (tape lanes trade through; every setup-quality scalar refuted)
plus the ignition/vel5 resolution-mismatch precedent (a 10s-proven fire re-judged at 1-min
resolution). N=1 thinness is flagged honestly in the kill-test; Friday grades the actual
scalar_veto_bypassed rows.
**What still stops a bad tape-lane fire (verified in the shipped source this convening):**
(1) the lane's own burst/context/day-gain LANE CONDITIONS (lane-spec entry conditions, not
vetoes — a kevseq that never sequences never fires); (2) inside check_momentum, the illiquid
share floor (:4126) and thin-ambient dollar floor (:4139) — tradeability, both still hard
FALSE returns whose reasons ("illiquid —", "thin ambient tape —") can NEVER match the
bypass's startswith("no momentum build") test; (3) the topping-tail Kev candle rule (:4207,
reason "topping tail on last bar") — same, unbypassable; (4) the universal ambient exit-floor
gate upstream of check_momentum (:12641, its own else-branch — the exemption sits INSIDE the
else, so the universal gate is untouched); (5) min-stop tradeability floor :12227 (kevseq etc.
NOT in MIN_STOP_EXEMPT); (6) backside gate :8975 (tape lanes NOT in BACKSIDE_EXEMPT — see
B2-F2); (7) capital/slot governors and the stop chain — stop_loss computation, intrabar stop,
monitors, `_verify_exit_px` all read nothing new (grep: neither commit touches any exit path).
Worst case on a wrong bypass: one normal stop-out at current clamps (~$30), identical to any
other admitted entry. Kill switch TAPE_LANE_SCALAR_EXEMPT=0 restores 8/17 behavior exactly
(rig AL pin).

## 1. Item A (173d8f1) — exemption scope VERIFIED
- **Bypasses ONLY the refuted scalar:** condition (:12665-12667) = not mom_ok AND env on AND
  entry_type in {kevseq,v2conv,grinder,bandpass,prevwap} AND reason startswith "no momentum
  build". I read check_momentum end-to-end (:4078-4226): its four hard-reject reasons are
  "illiquid —…", "thin ambient tape —…", "no momentum build —…", "topping tail on last bar…".
  Only the third matches. Floors and topping-tail keep their veto — also rig-executed (AL:
  illiquid still vetoes, ambient still vetoes a tape lane).
- **Chart lanes unchanged:** the momentum exempt tuple is untouched; dip_rip/rocket_catcher/
  unlisted lanes still fully gated (rig AL: dip_rip still vetoed, no bypass row). vel5 gate
  applies-to set stays chart-only (rig-pinned; archive N=0 structural).
- **Every bypass logs:** `_log_decision(ticker, "scalar_veto_bypassed", price, lane, gate=
  "momentum", reason)` :12668-12670 — Friday's counterfactual row exists on every bypass, and
  mom_details carries {"exempt": "tape_scalar:<lane>"} so the trade row is distinguishable.
- **Three-rings:** single momentum call site (grep: one check_momentum call, one def);
  exemption env defs :5099-5101 single definition; no other consumer of the two new envs.

## 2. Item B (cdbe7d4) — CROWN_FIX_0817 write-only VERIFIED
- The "crowned" row is written at ONE site (:5018, inside _leader_qualify's existing
  try/except, guarded by CROWN_FIX_0817=1). Grep of the whole tree for readers: the rehydrate
  query (:5266) still requests `status=leader_armed,halt_suspect` — "crowned" is NOT in it;
  the only other "crowned" tokens are the eyes-snapshot dict KEY (:9953/:9956/:10032, derived
  from rec["since"], pre-existing, not the decision row). Nothing reads the new row back.
  Rig AM executes the WETO frozen-clock sequence on the real source: no crown pre-halt, no
  crown at +39.4% halt violence, crown on the first post-halt probe, 'crowned' row post-fix
  only, byte-identical behavior with CROWN_FIX_0817=0, observe-only pin.
- **Status-collision check (scope item):** "crowned" is a brand-new status string — no prior
  writer, no dashboard/rehydrate consumer keys on it (no dashboard files in this repo consume
  by_status="crowned"; the store just gains a new group). Clean.
- Forensic verdict accepted: WETO WAS crowned 09:47:07; leader_armed always was the crown
  row; defect = observability. The three flags (dual prior-close sources 137.17 vs 124.45;
  40%-crossed-inside-a-halt delays crown to resumption+1 cycle; scan-cycle latency) are
  correctly routed to Marcos as behavior calls, not slipped into code.

## 3. DOCTRINE-INVERSION SWEEP (item A ENFORCES settled 7/26 — sweep for misses)
Question: do OTHER setup-quality scalar gates still veto tape lanes past the exemption?
- **momentum ("no momentum build")** — the exemption. Covered.
- **vel5** — chart-only applies-to set {flat_top, ma_pullback, orb, ema_bounce} (:8916s),
  rig-pinned; no tape lane reaches it. Covered structurally.
- **B2-F1 (to Marcos, not a blocker): EXTENSION gate still vetoes the five tape lanes.**
  kevseq fires append to `breakouts` (:8013; v2conv/grinder/bandpass/prevwap same pattern)
  inside wait_for_flat_top_entry, and the extension guard (:8991-9008, EXTENSION_MAX_PCT=0.25
  hard-coded :402) runs on that same list. Its exempt tuple (:8995) = rocket_catcher,
  hidden_entry, flat_top, orb, ma_pullback, vwap_reclaim, zone_flip — NONE of the five new
  tape lanes. Extension is on the 7/26 refuted-scalar list, so a tape-lane fire >25% above
  the 90-EMA (the natural habitat of a kevseq runner) dies at extension_reject — the same
  inversion class item A just repaired, one gate over. Archive N to date: not measured this
  convening (the lanes have been conversion-live for ~1 day) — but WETO-class names live
  >25% over their 90-EMA routinely. RECOMMENDATION: price a follow-up (add the five lanes to
  the extension exempt tuple OR log-only first) — Marcos's call; do NOT slip it into this
  ship.
- **B2-F2 (noted, doctrine-consistent): BACKSIDE gate applies to tape lanes** (:8981,
  BACKSIDE_EXEMPT={dip_rip} only). Backside is NOT a refuted setup-quality scalar — it is
  Marcos's own 8/5 settled gate with era pricing (−$147 in-band bleed) and its own Friday
  re-grade. Not an inversion; recorded so nobody "discovers" it later.
- **Day-gain:** tape-lane day-gain appears only as LANE-SPEC entry conditions (kevseq ctx /
  conversion criteria), i.e. what makes the lane fire — not a post-fire veto. Distinguished
  per scope; no inversion. Room/runway+ceiling gates: map-structure gates (chart-gate family,
  with their own lane bypasses), not the refuted scalar class; unchanged by this batch.
- **8/12 our-numbers primacy / 8/6 freshest-data:** untouched by batch 2 (no map/kev_shadow
  code in either commit). Batch-1 sweep findings stand (preserved below).

## 4. DAY-ONE WALKTHROUGH — tomorrow's kevseq fire without momentum-build
09:5x, KEVSEQ_CONVERT on: kevseq_step sequences B→H on the fed 10s bars, context gates pass
→ kevseq_shadow_fire + triggered_kevseq rows; fire appends to breakouts (lane "kevseq",
stop=would_stop) :8013. Backside gate: entry near highs → not in the 15-30%-below band →
kept. Extension guard: IF >25% over 90-EMA → extension_reject (B2-F1 — today's reality;
walkthrough continues for the under-25% case). Worker: chart gate — kevseq rides the
live-structure bypass path (kill-test :3349 family) or passes; entry_zone ok; min-stop:
would_stop width vs 4% floor (tradeability, stands); universal ambient exit-floor gate
passes → else-branch calls check_momentum → floors pass, expansion 0.9× base fails →
mom_ok False, reason "no momentum build — …" → exemption condition TRUE →
scalar_veto_bypassed row (lane=kevseq, gate=momentum, price) + 🟢 print → mom_ok=True,
details={"exempt": "tape_scalar:kevseq"} → runway/ceiling/slots/capital as any entry →
order places with the UNCHANGED stop chain → fill → monitor_trade runs normally (intrabar
stop, off-tape exit guard, E3 exit mode per the kevseq conversion spec: bank ½ +10%, trail).
Every promised row exists; nothing downstream reads "exempt" as anything but a detail stamp
(grep: no consumer branches on it). If the fire was bad: stop-out ~−$30, identical to today.

## 5. RIG (run BY THIS CONVENING)
Full rig: EXIT 0, ALL GREEN, 498 green checks. AL executed (9 checks: pass-through on the
WETO pin, bypass row shape, dip_rip still vetoed, kill-switch restore, illiquid + ambient
floors still veto, lane-set coverage, vel5 chart-only, artifact filed). AM executed (9
checks: WETO frozen-clock sequence, no pre-halt/halt-violence crown, post-halt crown,
'crowned' row post-fix only, observe-only pin, kill-switch byte-identity, artifact filed).
SHIP_CHECK=1 pre-artifact: RED on section Q only (tip uncovered — the interlock working as
designed). Post-commit rerun below.

## 6. ROLL CALL (data/audits/ROSTER.txt, all 31)
- **Blast Radius Auditor** — this convening; findings B2-F1/B2-F2; money statement above.
- **Momentum Operator** — touched: the momentum scalar's refutation is now ENFORCED for tape
  lanes; the scalar still runs and logs (bypass rows preserve the counterfactual). Standing
  question satisfied: nothing ships on noise — doctrine + priced specimen, Friday grade set.
- **Systems Quant** — touched: verified the bypass condition matches exactly one reason
  string among check_momentum's four hard rejects; verified "crowned" row = write-only.
- **Wind Tunnel Engineer** — touched: rig AL/AM execute the REAL shipped source (loader
  byte-parity); spec-not-impl respected; exit code judged.
- **Statistician** — touched: +$25.14 N=1 dollar trace is ledgered in the kill-test with the
  named trade (WETO 10:18:37); scalar_veto_bypassed = new ledger-ready row type; B2-F1's
  extension N explicitly UNMEASURED — recorded as such, not asserted.
- **Crown Steward** — touched: the 8/5 promise's visibility repaired; crown latency + halt-
  crossing delay + dual prior-close flags on the Steward's docket for Marcos.
- **Pit Crew Chief** — touched: three new envs (TAPE_LANE_SCALAR_EXEMPT, TAPE_SCALAR_
  EXEMPT_LANES, CROWN_FIX_0817) all default-on with kill switches; batch NOT deployed;
  book-flat + no-RTH-push laws bind the eventual ship.
- **Trade Manager** — touched-with-verification: exits/stops/monitors read nothing new;
  admission-only change; E3 exit note from the kill-test (trail gave back the WETO run) is
  an EXIT finding routed to the Manager's queue, not acted on here.
- **First Hour** — touched: WETO specimen fired 10:18; bypass rows land in the First Hour
  attribution window; grade offered-vs-captured on them Friday.
- **Tape Veteran** — touched: hypothesis on record — bypassed fires may still be the tired
  late continuation the scalar meant to catch; Friday's rows decide, not the doctrine.
- **Strength Ombudsman** — touched: exemption is PRO-strength (a proven 10s fire no longer
  killed by a 1-min re-judgment); no weakness free-pass — floors/topping-tail stand. B2-F1
  logged as refused-strength exposure (extension can still refuse a runner).
- **Side Marshal** — touched: backside gate's reach over tape lanes confirmed intentional
  (B2-F2); band edges unchanged; no side logic touched.
- **Convexity Trader** — touched: the bypassed class is tail-shaped by construction (10s
  momentum fires); mean-after-costs to be graded, never assumed from N=1.
- **Curl Mechanic** — touched: grinder/bandpass in the exempt lane set; fire-count acceptance
  unaffected (lane conditions untouched).
- **Hidden Entry Architect** — clean: hidden_entry already in the momentum exempt tuple;
  v2conv (the v2 conversion lane) gains the exemption — consistent with the v2 gate-stack
  design (its own gates lead).
- **Reclaim Architect** — clean: vwap_reclaim/zone_flip already exempt; untouched.
- **Rocket Rider** — clean-with-note: rocket_catcher deliberately stays fully momentum-gated
  (the gate's retained purpose); unchanged.
- **Kev Librarian** — touched: topping-tail (Kev candle rule) explicitly preserved — the
  bypass cannot match its reason string; corpus grounding intact.
- **Cartographer** — clean: no map/overlay code in batch 2.
- **Feed Engineer** — clean: no fetch-path change; check_momentum's bar diet unchanged.
- **Webull Broker Desk** — clean: no order semantics touched; rig 401 token probe noted
  (laptop-side, non-fatal, exit code judges).
- **Quartermaster** — touched: WETO 10s bars cached to data/universe/bars10s/ (dir
  gitignored, file on disk) — ferry/backup sweep should pick the file up.
- **Dashboard Curator** — touched: two new statuses (scalar_veto_bypassed, crowned) will
  appear in by_status censuses — display additions queued; no collision (new strings).
- **Integrator** — touched: exemption sits inside the existing else-branch seam; single
  call site verified; no parallel momentum logic created.
- **Execution Surgeon** — clean: planned-R chain untouched.
- **Handicapper** — clean: selection/scanner untouched.
- **Seam Scientist** — clean: no beginning-entry logic; notes bypass rows enrich seam joins.
- **Opening Bell** — clean: no pre-open window change in batch 2.
- **Forward Architect** — touched: B2-F1 (extension exempt for tape lanes) registered as the
  priced follow-up hypothesis; E3-trail exit finding queued.
- **Project Manager** — touched: Friday grade list gains scalar_veto_bypassed rows + B2-F1
  decision; morning brief carries [VERIFIED] batch-2 audited GREEN, NOT deployed.
- **Historian** — touched: record that 8/17 batch2-A is the ENFORCEMENT of settled 7/26 law
  (first tape lane ever to reach check_momentum was 8/17 — the veto class was new traffic);
  and that the "WETO never crowned" claim is officially corrected: crowned 09:47:07.

## SHIP_CHECK
Pre-artifact: RED on section Q only (tip 5d58e42 not covered) — the designed interlock.
POST-COMMIT: appended below by the convening runner after this artifact commits.

---
# PRIOR CONVENING (batch 1, tree e5f59fe) — GREEN; preserved for the record
(Verdict, KEV_ROAD price statement, findings F1-F5, walkthroughs, and roll call are in git
history at 83ab088:data/audits/LATEST.md. Summary: GREEN; KEV_ROAD = batch-1's only money
change, priced at ~−$5/tr EV assumption until Friday, loss bounded by the unchanged stop;
F1 veto observe-only + F2 zero-rung road surfaced to Marcos.)
