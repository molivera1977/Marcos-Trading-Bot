# AUDIT COVERAGE — checked by rig section Q under SHIP_CHECK=1
covers: ad3f842461fd
date: 2026-08-13 ~00:45 ET
change: STOP-COHERENCE FLOOR 0.5% (Marcos: "ship the 0.5% floor tonight with the audit protocol")
convening: 17th (pre-ship, agent a0051604f3837bcbf) — BLOCKED first pass (gate missed its own
motivating specimen: BQ incoherence is born POST-FILL in the stop re-derivation), F1-EXTEND
applied (widen-not-refuse + stop_coherence_widened row), re-verified, VERDICT: SHIP.
kill-test: data/killtests/stop_coherence_census_20260813.md (0.5% = 3 trades / −$17.50 pure;
1% refuses 4 winners). Kill switch STOP_COHERENCE_MIN_PCT=0. Friday 8/15 re-grades the rows.

## ROLL CALL (17th convening, all offices)
- Blast Radius Auditor — TOUCHED: found the post-fill twin (the BLOCK), F1-EXTEND verified
- Dashboard Curator — TOUCHED: refused/widened rows not on reject strips yet (queued debt)
- Systems Quant — TOUCHED: gate-predicate vs census-predicate mismatch caught; closed
- Pit Crew Chief — TOUCHED: kill switch real; ship in one batch tonight
- Integrator — TOUCHED: single worker call-site confirmed; converts route through it; no twin left
- Side Marshal — CLEAN: refusal rows get SIDE via suffix match
- Crown Steward — TOUCHED advisory: refused-crown counterfactuals priced Friday
- Feed Engineer — TOUCHED: root cause = 239s-stale fire data; staleness ledger entry owed
- Webull Broker Desk — CLEAN: no order-semantics change
- Quartermaster — CLEAN: no storage surface
- Kev Librarian — CLEAN: rule is Kev-consistent
- First Hour — TOUCHED advisory: refusals cluster at the open; attribute refused-$ in daily brief
- Opening Bell — CLEAN: PRE worker shares the gate
- Seam Scientist — CLEAN: shadow-only lane unaffected
- Strength Ombudsman — TOUCHED advisory: BIAS LEDGER row Friday
- Forward Architect — CLEAN: protocol followed (census attached)
- Momentum Operator — CLEAN: tradeability floor, census-backed, not setup-quality
- Trade Manager — TOUCHED: post-fill stop ownership; widen keeps exit math sane
- Tape Veteran — CLEAN: matches the BQ tape
- Reclaim Architect — CLEAN: behind the 4% minstop
- Execution Surgeon — TOUCHED: planned-R = realized-R restored only WITH F1-EXTEND
- Handicapper — CLEAN: no selection change
- Rocket Rider — CLEAN: 0.5% far below any parabolic stop
- Cartographer — CLEAN: no map surface
- Wind Tunnel Engineer — TOUCHED minor: re-run census with widen semantics before Friday
- Statistician — CLEAN: census ledgered; rows append-path
- Convexity Trader — CLEAN: removes a pure left tail for −$17.50 mean cost
- Curl Mechanic — CLEAN: refusals refund the slot
- Project Manager — TOUCHED: Friday re-grade registered; rows added to EOD scorecard pull

## SUPERSEDING — 18th convening (8/13 ~01:30 ET), covers: 30c9a2642489
MARCOS RULING ("keep how we have it and just fix the coherence floor" / "no widening to 7%"):
the 17th-convening widen remedy is DEAD. Post-fill = observe-only (stop_coherence_observed row,
stop NEVER touched); pre-fill 0.5% refuse unchanged. 18th convening verified: no mutation in the
elif body, F1 untouched, downstream sees the original stop, no live widened reference, rig pins
honest, ALL GREEN. Delta reviewed: Execution Surgeon, Systems Quant, Statistician, Strength
Ombudsman, Pit Crew Chief — all PASS. Full room carried from the 17th roll call above.
VERDICT: SHIP.

## 18th-convening supplement — FREEZE HARDENING (8/13 evening), covers: 84c0d40b93a7
19th convening (agent af8857d8b255ddf55): all 6 items PASS (cross-midnight isoformat verified by
execution; double-clear benign; bot resume latency ~20s worst case; input-space sane incl.
nan/inf probes; XSS clean both paths; widened rig pin intent verified — no other route in window).
Ledger-note: DST fall-back night ±1h clear skew, bounded, accepted. Delta officers: Pit Crew,
Curator (satisfied — display ships WITH mechanism), Feed Engineer, Systems Quant, Ombudsman
(expiry strictly reduces refusal time), Integrator — all clean. Full room carried from tonight's
debrief. VERDICT: SHIP.
- Historian — TOUCHED (first ship on post): the freeze incident, its 13 refused entries, and this
  hardening are chronicled as the 8/13 milestone "the day the kill switch got a clock"; artifact
  trail verified (ledger + OFFICIAL_BOOK current).

## 20th convening — #54 BATCH (8/13 evening), covers: 829aa53bf84a
Agent a3a13889f18c84082: 7/7 PASS incl. the mandatory day-one walkthroughs (SCKT-quiet-at-7:05 and
FGI-new-high-at-8:01 traced end to end, no gaps; the 9:31-on-8:05-map replay dies at
bluesky_ttl_expired as specced). Key verifications: anchor-override ordering beats blue-sky in
BOTH lanes; _ts stamped on every merge branch; full targets-consumer census (runway/exit-rungs/
auto-map/zone all safe on advisory targets); B2 touches only the reader todo filter (merge
untouched); B3 race bounded + self-healing + secret cited; 4 kill switches present.
Fix-nows: #2 doc addendum DONE; #3 rig TTL-parse executed-check DONE (suite ALL GREEN after);
#1 = _effective_map auto-map overlay drops am._ts (crowned blue-sky name w/ stale map + fresh
auto-map gets TTL-expired despite fresh structure — fail-closed crown-privilege leak) = MARCOS'S
CALL, priced one line, queued to him tonight.
Delta officers: Systems Quant, Cartographer (flags #1), Crown Steward (wants #1 ruled), Strength
Ombudsman (approves — batch is a strength-refusal cure), Kev Librarian, Reclaim Architect, Curl
Mechanic, Integrator, Dashboard Curator, Seam Scientist, Pit Crew Chief, Statistician — clean.
Historian — TOUCHED: chronicles the Kev-read inversion discovery (the 8/5 billing-saver was the
true A/B starvation cause, not the liquidity floor). Full room carried from tonight's debrief.
VERDICT: SHIP.

## 20th-convening delta — auto-map _ts fix (Marcos-approved), covers: 8880cba772c2
Delta-verified by the same auditor: stamp scoped to the real-overlay branch only; _freshest_rec
and _map_freshness read RAW stores (no self-laundering loop possible); cache restamps each 20s
rebuild (auto-map age <=20s vs 600s TTL). Known behavior delta, intent-aligned + Friday-graded:
ceiling standdown no longer sticks across rebuilds on a breached crown (re-evaluates on latest
data — Marcos: "I just want the latest data so the bot can make the proper call"). VERDICT: SHIP.

## DOCTRINE-INVERSION SWEEP (retro-applied to tonight's ships, per Marcos "make sure this is
## actually implemented"): the #54 batch FOLLOWS the 8/12 level-primacy doctrine flip. Sweep of
## code encoding the OLD (Kev-rules) doctrine: (1) reader 8/5 skip-if-kev-levels — FOUND+FIXED
## tonight (Build 2 inversion); (2) _kev_sheet_name flip-blindness — found+fixed 8/12 (11th);
## (3) merge vision-first ordering — found+fixed 8/13 (15th); (4) grep tonight of "kev" gating
## sites in bot: daygain exemption/tier-0 sort/label = provenance perks (kev_name honored, doctrine-
## neutral); veto = data-only since f36c1b2. No further old-doctrine encodings found.

## 21st convening — MAX_TRADE_DOLLARS env, covers: 290bc48c6eff
Delta audit: 7 consumers on the module global, no re-hardcode; ambient coupling proportionally
safe (exit coverage constant); rig U upgraded to a real exec pin after the tautology flag.
doctrine-inversion sweep: n/a (pure parametrization). Day-one walkthrough: trial boot at 175
traced through config print, ambient floor $2,625/min, settled-cash, sizing 87sh@$2.
PRICED QUESTION TO MARCOS (not shipped): trial cohort-shift — at $175 the ambient floor admits
thin names full scale will refuse; AMBIENT_DVOL_MULT=86 for the trial would hold today's $15k/min
floor (measure-representative) vs default proportional (learn-wide). His call before Monday.
VERDICT: SHIP. Full room carried from tonight's debrief; Historian chronicles the parametrization.
