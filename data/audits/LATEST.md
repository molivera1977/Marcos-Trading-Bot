covers: e5f59fed90b6
# BLAST RADIUS CONVENING — 8/17 reads/maps + bell-boundary batch (separate context)
Auditor: Blast Radius Auditor. Tree audited: e5f59fe (tip) = 2a8951a + c4550d8 + a4fc25c +
b1711f9 + e2ef254 + fb90194 + e5f59fe. Scope doc: PENDING_CONVENE_20260817.md. Context read:
BOUNDARY_CENSUS_20260817.md, pre_staleness_forensic_20260817.md. Full rig executed THIS
convening: exit 0, 480 green checks, sections R (bell-boundary), AJ, AJ2, AJ3, AJ4, AK all
present AND executed (headers + per-check lines observed in output, judged by exit code).
SHIP_CHECK=1 pre-artifact: RED only on section Q coverage interlock (expected until this
artifact commits) — rerun after commit recorded at bottom.

## VERDICT: GREEN — deploy may proceed on Marcos's word, with the KEV_ROAD price statement
below and findings F1/F2 surfaced to him first (neither is a code blocker; both are
doctrine/pricing items that are his call under auditor-cannot-authorize).

## 1. Marcos's rulings — verified honored
- **"Kev's picks, OUR map numbers ruling" (8/12, REAFFIRMED 8/17):** VERIFIED. Grep of the
  whole tree: `kev_shadow` is consumed ONLY in `_kev_shadow_overlay` (:9426, called from both
  `_freshest_rec` return paths :9420/:9421). It writes exactly two things: `veto`/`veto_src`
  and `kev_road_max`. NO code path promotes kev_shadow break/confirm/stop/targets into the
  effective record; the original freshest-timestamp-promotion spec was corrected mid-build and
  is absent from the tree. The vision_shadow promotion (:9414-9419) is OUR source, unchanged.
- **Three spec-tension defaults:** confirmed built as specced and logged for Marcos, not
  resolved in code: (a) dual read-request lanes at ceiling_reject kept (reader marker 10-min
  cap :3049 AND `_request_auto_read` 30-min throttle :12397 both fire); (b) G1 stamps ride
  ONLY the proceeding fire row (triggered_ignition :8455 + breakout extra :8440) — daily_bad /
  below_convert refusals unstamped; (c) starvation roster = the levels sheet (`len(lv)` in
  reader :1259) — nearest in-process truth, not the bot's watch roster.
- **KEV_ROAD is the batch's only money-behavior change:** VERIFIED. item2 = read-side spend
  only (a reader vision read; no gate outcome changes). item3 = one observe row per 15-min
  window. item4 = stamps only; rig AJ4 asserts g1_shadow is never read back by any condition;
  I confirmed no consumer of `g1_shadow`/`vwap_side` exists outside the stamp + writers.
  item5 = docs + rig. 2a8951a changes WHICH of today's bars are visible (money-adjacent but
  restores intended behavior; `_fresh_session` today+900s staleness arbiter untouched).
  KEV_VETO_READ — see F1: it is effectively observe-only in this tree.

## KEV_ROAD PRICE (dollars, per the dollars-not-R law)
What it can flip: a `runway_reject` (road < need) becomes a PASS when (a) our own
targets/next_supply above entry are exhausted AND (b) kev_shadow carries a max target above
our ceiling and above entry. Trace (the named trade, from the c4550d8 hand-trace + today's
row): WETO 8/17 07:10 — entry above vision's 9.5/10 rungs, rungs exhausted, kev_road_max 20
-> road extends to $20 -> reject flips to pass. Era evidence (runway_graded_rows_20260804.json,
n=23 graded runway_rejects had they all fired): net −$115.11 (8 winners +$217.61, 15 losers at
the ~−$30 stop clamp). KEV_ROAD admits only the rung-exhausted-with-Kev-ceiling SUBSET of that
class, which is untested as its own cohort — assume ~−$5/trade EV until Friday grades the
actual KEV_ROAD passes. Worst case if Kev's round-number target is wrong: the road is
OVERSTATED, the entry proceeds that should not have — and the loss is bounded by THE STOP,
WHICH IS UNCHANGED (KEV_ROAD touches only the (rr, tgt) return of `_marked_runway` :9670-9676;
stop_loss is computed upstream and never reads kev_road_max). Explicitly: a wrong Kev target
costs one normal stop-out (~$30 at current clamps), never an unbounded ride — monitors,
intrabar stop, and off-tape exit guard all run normally on these entries.

## 2. Findings + fix-now list
- **F1 (to Marcos, not a blocker): "His veto rules the row" is overstated — veto is
  observe-only in this tree.** The ONLY veto consumer is the chart gate :3367, which since the
  8/12 doctrine ("the chart and tape decide. No one has veto power") logs
  `veto_noted_not_gating` and blocks nothing. So KEV_VETO_READ propagates the flag onto rows
  (good: the Friday A/B now sees Kev's shadow vetoes) but no entry is refused by it. If Marcos
  intends Kev's veto to BLOCK, that is a separate priced behavior change — do not slip it in.
- **F2 (to Marcos, not a blocker): KEV_ROAD zero-rung edge.** `_kev_shadow_overlay` stamps
  kev_road_max when our targets list is EMPTY too (:9454 `not _otgts`), so on a target-less map
  the entire road is Kev-derived. "Rungs exhausted" arguably includes zero rungs, and our
  numbers still aren't overridden (there are none) — but Marcos should know the road can be
  100% Kev's number on sparse maps. Sparse-map-is-valid-information law cuts both ways here.
- **F3 (accepted, noted): `_freshest_rec` exception fallback (:9422) returns the raw record
  WITHOUT the overlay** — on that path no veto stamp, no kev_road_max. Fail-safe direction
  (less behavior, not more); acceptable.
- **F4 (verified coherent): auto-map interaction.** Overlay runs inside `_freshest_rec`, so
  kev_road_max/veto ride into `_effective_map`'s auto-map overlay via `eff = dict(rec)`
  (:9622) — the swap replaces only break/confirm/targets. kev_road_max is computed against the
  PRE-auto-map targets; after a swap the auto-map's surviving targets (if any) win `_tgt`
  first, and KEV_ROAD is consulted only when none exist. Coherent with primacy.
- **F5 (verified): overlay rides the 20s `_effmap_cache`** — veto/kev_road_max cached with the
  rec; no consumer caches a pre-overlay rec elsewhere (all gate sites go through
  `_effective_map`; the direct `_fetch_kev_levels()` sites :1183/:3323/:5351/:5381/:10636/
  :12954/:13268 are display/scoring/archive reads, none a structure gate — swept).

## STANDARD CHECKS
- **Upstream charges:** reread-on-reject adds NO new HTTP GETs in the bot (a `_log_decision`
  row is the marker); the cost is reader-side vision reads, bounded by 1/ticker/10min
  (`_reread_reject_t`) AND the reader's existing `_capped` governor, which still rules.
  item2's staleness probe at runway_reject calls `_effective_map` again — 20s TTL cache, no
  extra fetch. Starvation counter: zero fetches. G1 stamp: reuses in-hand bars
  (`cache[t].full_bars`), zero fetches. Bell-boundary fix: same fetch count, wider session arg.
- **Twins:** eyes compact vs full — G1 stamps enter via the breakout extra dict and the
  decision row with the SAME keys (no collision: vwap_side/hi_dist_pct/g1_shadow are new
  everywhere; grep confirms no prior writer). Decisions row vs trade record: triggered_ignition
  carries the stamps; the trade record is untouched (observe-first — Friday joins on the
  decision row). VWAP twin NAMED per the scope doc: the fire-site `vwap` = `cache[t]["vwap"]`
  = scan session VWAP (pre+RTH fetch :7655 under ENTRY_VWAP_PREMARKET, else RTH full_bars
  line, possibly tick-VWAP overlay :7690) — the monitor's separate ["PRE","RTH"] fetch (:10685)
  is the same anchor family; the guidance's G1 was simmed on session VWAP, so the stamp
  matches intent. If tick-VWAP overlay is active the stamp uses the tick line — same line the
  gates use, which is the honest one to grade.
- **Whole sandwich:** entry path — runway/ceiling/backside gates read the overlaid rec; exits —
  monitors, stops, `_verify_exit_px` read NONE of the new fields (grep: kev_road_max/g1_shadow
  absent from monitor_trade and exit paths). Exit side untouched.
- **Restart semantics:** `_reread_reject_t`, `_starv`, `_effmap_cache`, reader
  `seen_markers` all in-memory — restart resets caps. Worst case: one extra reread marker per
  ticker and one early/late starvation window per restart. Bounded, no money path. ACCEPTED.
  `seen_markers` growth: dedup key includes recorded_at so it grows with rows, but is bounded
  by the day's decision-row volume and process lifetime — acceptable, reader restarts nightly.
- **Strength/weakness bias:** reread-on-reject fires on REFUSALS of stale structure — it spends
  reads re-examining names the bot just refused, i.e. it gives refused strength a fresh look
  instead of letting a stale map keep saying no. Ombudsman's direction: PRO-strength. No new
  weakness free-pass introduced.
- **Rig:** full rig run BY THIS CONVENING, exit 0, 480 checks; R/AJ/AJ2/AJ3/AJ4/AK all
  executed (not just present). AK bare-call pin ==3 matches the census; frozen-clock matrix
  matches BOUNDARY_CENSUS_20260817.md including the 09:30:30 pin. Note: rig output contains a
  Webull 401 (token probe from this laptop) — non-fatal by design, exit code is the judge.

## 3. DAY-ONE WALKTHROUGH
**(a) Tomorrow 09:29 -> 09:36, hand-off live (RTH_HANDOFF_MIN=5):** 09:29:30 —
`_live_sessions()` = ["PRE","RTH"]; read-list guard sees fresh PRE bars, roster passes as
today. 09:30:00-09:34:59 — hm >= "09:30" but < "09:35": hand-off branch returns ["PRE","RTH"];
the seven P1 fail-closed consumers (guard :3098, cache refresh, velocity, entry fresh-bar
guards) keep seeing seconds-old PRE tape; `_fresh_session` still enforces today+900s, so no
prior-day bar can leak. The 3-min probe cache's 09:30-09:32 bucket now pins TRUE, not False —
the 23/26-name blackout class is dead. ~09:31+ first completed RTH bars arrive and simply join
the same list. 09:35:00 — hand-off ends, list = None (RTH-only), 5 minutes of RTH bars exist:
no gap. Roster survives the flip end-to-end; promised row = normal reads/entries in the
09:30-09:35 window instead of `no fresh bars` skips. Failure condition (forensic, written
first) stands: roster-wide skips 09:30-09:35 on fresh-tape names tomorrow = fix wrong.
**(b) WETO-class 07:10 fire with KEV_ROAD:** PRE window, `_live_sessions()` = ["PRE","RTH"].
Entry candidate at ~$10.4, vision map rungs 9.5/10 both below entry -> `_tgts` empty, `_ns`
none above -> `_tgt` None -> KEV_ROAD branch: kev_road_max 20 > entry -> returns
(rr=(20-entry)/rps, tgt=20) -> runway PASSES; `runway_pass` row carries the Kev-ceiling
target (record-side coherent — tgt is stamped as the road's target, src evident from
kev_road_max on the rec). Entry proceeds through the remaining gates unchanged; stop_loss
computed exactly as today (KEV_ROAD never touches it); monitor, intrabar stop, exit guard
all normal. If $20 is a fantasy: one standard stop-out, ~−$30 at current clamps. Promised row
produced; nothing stops the trace.

## 4. DOCTRINE-INVERSION SWEEP
The batch FOLLOWS a doctrine event: 8/12 our-numbers primacy REAFFIRMED by Marcos 8/17
("Kev's picks but OUR map numbers ruling"). Sweep for residual kev-numbers-first encodings:
- grep KEV_PRIMACY: zero hits — no such switch exists in the tree.
- kev-level exemptions / sheet-governs-before-first-read: the `_bypass` live-structure lanes
  (:3350) exempt lanes from the MAP gate entirely (chart-gate doctrine, not kev-primacy) —
  intentional, not an inversion. The no-map skip (:3380 `no_marked_level`) gates on the
  EFFECTIVE (vision-primary) record — before the first vision read the record IS the sheet;
  that pre-first-read window is the intentional exception (sheet = only data in existence,
  freshest-data law) and inverts nothing once a read lands, because vision_shadow promotion
  (:9414) takes over on timestamp.
- `_freshest_rec` (:9400): promotes VISION over the sheet — the 8/12 direction, correct.
- `_auto_map` (:9561) reads the STORED sheet's targets as survivors above the tape high —
  targets-only, above-our-computed-break: consistent with "Kev may say where road is, never
  what our levels are". Same shape as kev_road_max. Not an inversion; noted.
- doctrine-inversion verdict: NO residual kev-numbers-first path found; the one code path that
  reads Kev structure for gating-adjacent purposes (`_auto_map` survivors) predates the batch,
  is above-our-anchor by construction, and is flagged here for the record. F1 (veto
  observe-only) is the only place the 8/17 words and the tree diverge — surfaced to Marcos.

## 5. ROLL CALL (data/audits/ROSTER.txt, all 31)
- **Blast Radius Auditor** — this convening; findings F1-F5.
- **Dashboard Curator** — touched: read_starvation rows post under ticker SYSTEM; dashboard
  consumers that assume ticker=symbol will show a SYSTEM row (item3 scope doc flagged it) —
  display-only, queue a filter; hi_dist_pct stamp closes the Curator's G3 measurement debt.
- **Systems Quant** — touched: verified each function computes what its name claims;
  `_ignition_g1_stamp` hi_dist_pct = pct below session high (matches guidance definition);
  `_starvation_tick` window arithmetic checked (900s, void outside 07:00-16:00).
- **Pit Crew Chief** — touched: five new envs all default-on with kill switches
  (KEV_VETO_READ/KEV_ROAD/REREAD_ON_REJECT/READ_STARVATION/IGNITION_G1_SHADOW, plus
  RTH_HANDOFF_MIN=0 kill); restart semantics accepted above; no RTH deploy (batch NOT deployed).
- **Integrator** — touched: reader marker-status set extension (:1187) is the single seam;
  wiring verified end-to-end (bot row -> reader queue -> reread_one -> starvation counter).
- **Side Marshal** — clean: no side/band logic touched; backside gate reads the overlaid rec
  but consumes no new field.
- **Crown Steward** — touched: freshness contract (crowns-only) now also fires
  reread-on-reject at breach — crowned names get the fastest rereads; privilege-coherent.
- **Feed Engineer** — touched: bell-boundary fix is a session-filter semantics fix on the
  Alpaca/Webull fetch path; census P1-P5 tables verified against the tree; bare-call pin 3.
- **Webull Broker Desk** — clean: no order/account semantics touched; rig's 401 token probe
  noted (laptop-side, non-fatal).
- **Quartermaster** — clean: no bars storage/ferry change; EOD archiver untouched (P4).
- **Kev Librarian** — touched: kev_shadow read-side is the corpus's first live read since the
  8/12 re-shelving; storage never written (source-protection law verified: overlay is
  read-side dict copies only).
- **First Hour** — touched: the 09:30-09:35 blackout was First Hour's window; fix restores
  read coverage at the bell; grade tomorrow's window vs the forensic's failure condition.
- **Opening Bell** — touched: hand-off spans the bell; PRE-period behavior unchanged
  (zero-print skips were correct and remain).
- **Seam Scientist** — clean: no beginning-entry logic touched; notes G1 stamps enrich future
  seam joins.
- **Strength Ombudsman** — touched: reread-on-reject = pro-strength (refused names get fresh
  reads); no weakness free-pass added.
- **Forward Architect** — clean: no new hypotheses shipped; KEV_ROAD Friday grade registered.
- **Momentum Operator** — clean: no momentum thresholds touched; velocity gate only gains
  boundary-safe sessions.
- **Trade Manager** — touched-with-verification: exits/stops read NONE of the new fields;
  KEV_ROAD changes entry admission only; stop unchanged (the price statement's bound).
- **Tape Veteran** — touched: hypothesis on record — KEV_ROAD passes may inherit the
  runway_reject class's −$5/tr EV; Friday grades the subset.
- **Reclaim Architect** — clean: reclaim lanes are `_bypass` live-structure; map overlay
  irrelevant to them.
- **Execution Surgeon** — clean: planned-R chain untouched; rr from KEV_ROAD is reporting the
  same arithmetic on a farther target.
- **Handicapper** — clean: selection/scanner untouched.
- **Rocket Rider** — clean: hidden/ignition conversion behavior unchanged (stamps only).
- **Cartographer** — touched: breach alarm now co-fires a reread marker (:9598) — remediation
  loop tightened; auto-map/kev_road_max interaction verified coherent (F4).
- **Wind Tunnel Engineer** — touched: rig AJ4 asserts non-enforcement; AK frozen-clock matrix
  executes the REAL `_live_sessions`; spec-not-impl respected (checks assert Marcos's words).
- **Statistician** — touched: new row types (reread_on_reject, read_starvation, g1 stamps,
  runway_pass with Kev-ceiling target) are ledger-ready; unledgered-number law satisfied by
  the graded-rows citation above.
- **Convexity Trader** — touched: KEV_ROAD admits farther-target trades — tail-shape friendly,
  mean-after-costs to be graded, not assumed.
- **Curl Mechanic** — clean: 10s fire paths untouched (stale_fire_suppressed forensic finding
  is scan-cycle latency, out of this batch's scope, already ledgered).
- **Project Manager** — touched: morning brief should carry [VERIFIED] hand-off live +
  KEV_ROAD watch items; Friday grade list: KEV_ROAD passes, G1 shadow, starvation rows.
- **Historian** — touched: record the 8/17 reaffirmation ("Kev's picks, OUR map numbers
  ruling") alongside the 8/12 flip; the corrected-mid-build promotion spec is part of the
  official record (PENDING doc preserved in-tree).
- **Hidden Entry Architect** — clean: v2 untouched; notes G1/vwap_side stamps will serve the
  v2 gate-stack evidence base.

## SHIP_CHECK
Pre-artifact: RED on section Q only (HEAD e5f59fe not covered) — the designed interlock.
Post-commit rerun result appended below by the convening runner.
POST-COMMIT: SHIP_CHECK=1 rerun after this artifact's commit — section Q GREEN (bookkeeping
exemption covers the artifact commit); full rig exit 0.
