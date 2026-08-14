# FULL-ROOM DECISION SESSION — 2026-08-14 (early; Marcos: "run tonight's session now", ~12:45 PM ET)
Chair: Blast Radius Auditor. DELIBERATION artifact — read-only, NO edits, NO deploys.
Ships (if approved) get their own LATEST.md convening against the actual diff.
Evidence base: mechanism_audits_20260814.md · all_lanes_census_20260814 · ignition_census_v2_20260814 ·
minstop_exempt_regrade_20260814 · core_lanes_sequence_check_20260814 · fictional_fills_census_20260813 ·
RESULTS_LEDGER 8/14 entries · live decisions_archive pulled 12:0x ET this session.

LIVE-TAPE UPDATE (pulled this session, curl 12:0x ET): freshness_breach now 28 rows / 8 tickers
(HAO + LFS new since the audit's 26/8, latest 11:50:07) — zero auto_map remediation on any.
No new hidden conversions after the 4 (last triggered_hidden_entry 11:17 ONFO; last fill 10:33 MF).
No verdict below changes; item 1 evidence strengthens intraday.

---
## THE DOCKET

### 1. Tuple-unpack fixes (:8373 _auto_map, :8461 RUNWAY_WALL) + freshness-breach-without-remediation alarm
VERDICT: **recommend-ship-tonight** (room unanimous; Systems Quant lead).
- These are not behavior CHANGES — they are restorations of behavior Marcos already approved
  (8/7 freshness contract, 8/8 runway wall) that has been silently inert since ship. Auditor-
  cannot-authorize note: restoring approved behavior still changes what the bot DOES tonight
  (maps will refresh; spent rungs will demote) — hence it is on this menu, priced, for his yes.
- Evidence: len((d10,src))=2<30 → _auto_map returns None every call since 8/7; tuple.values()
  AttributeError swallowed → _whi=0.0, wall inert since 8/8. ONFO 11 stale rejects (6-49% past a
  70-min-old break), DFSC 0.14R refusal, 26→28 silent breaches today. Same class as the 8/8
  _side_state unpack (precedent at comment :8316) — third strike on one signature.
- PRICE: build ~30 min (2 two-line unpacks + alarm row on 3 consecutive freshness_breach without
  auto_map_used). Risk LOW-MED: auto_map writing fresh maps changes gate inputs live — mitigated
  by rig case + ONFO/DFSC replay (both must flip to the correct read) + kill switches
  (AUTO_MAP_REFRESH=0, RUNWAY_WALL=0, BREACH_ALARM=0). Expected $: ONFO-class refusals alone
  cost double-digit-$ opportunities daily; DFSC-class 0.14R refusals block valid entries.
- FAILURE CONDITION (pre-registered): wrong if, post-fix, auto_map_used=true rows appear but
  stale_swap_refused rate does NOT fall on breach tickers within 2 sessions, or any map refresh
  writes a level with no computed structural anchor (maps-describe law).

### 2. ma_pullback warmup-wall fix (seed 3-min EMAs from the existing multi-day fetch)
VERDICT: **recommend-ship-with-conditions** — conditions: hostile-tape gauntlet replay vs the
worst-sessions set BEFORE deploy + env kill (MA_WARMUP_SEED=0) + fire-count acceptance window.
- Evidence: the only verified-green lane (era raw +$487; sequence-honest +$356..$460 — green in
  BOTH brackets, only lane that is) is structurally blind until ~10:36-10:47 ET; EMA50/90
  nonexistent until 12:05/14:00. The open — Kev's richest window — invisible. Fix = wire the
  already-fetched 7-day bars past _fresh_session for EMA seeding only.
- IN-SAMPLE HONESTY (Statistician): the lane's green is concentrated (AMIX+CYCU = majority,
  ex-top-2 ~flat) and its "10:30-12 best cell" is partly this wall's artifact. Opening the open
  is a Kev-faithfulness argument, NOT a measured-at-the-open edge — the open cohort has n=0 by
  construction. That is exactly why the gauntlet + acceptance window are conditions, not decor.
- PRICE: build ~1-2 hrs + gauntlet replay (same night). Risk MED: changes what the lane SEES;
  new cohort at the open is unmeasured. Expected $: unknown-positive if the lane's edge
  transfers to the open; bounded by slot caps + all 11 throttles still in force.
- FAILURE CONDITION: wrong if week-1 open-window (9:30-10:30) ma_pullback cohort is net negative
  strict-bracket, or fire count >3x era daily rate (throttle failure).
- Curl Mechanic condition: acceptance = fire-count band pre-registered (era ~1/day → accept 1-4/day).

### 3. The #57 bundle (stale-reject auto-read · born-exhausted blue-sky reroute · counter-rebuild
NameError fix · exit_ts_utc stamping · HIDDEN_CONVERT in boot banner · retest fills at real prints not assumed _rt_lvl :10955)
VERDICT: **recommend-ship-tonight** for the defect/telemetry members; **with-conditions** for the
one behavior member.
- NameError fix, exit_ts_utc stamping, boot-banner HIDDEN_CONVERT: pure defect/telemetry, no
  money-behavior change. Ship.
- Retest fills at real prints (:10955): fictional-fill class on the ENTRY side, still live — same
  disease the 8/13 exit-side fix cured. Booking entries at ASSUMED _rt_lvl fabricates the book.
  Ship (honesty fix; makes recorded entries match tape). Kill: RETEST_REAL_PRINT=0.
- Stale-reject auto-read + born-exhausted blue-sky reroute: BEHAVIOR members (change what gets
  read/routed with money). Condition: rig case each + observe-first stamps where feasible +
  each named separately in the ship convening diff. Kill switches per member.
- PRICE: build ~2-3 hrs total. Risk LOW (defect members) / MED (behavior members). Expected $:
  entry-print honesty is worth more than dollars — it is the proving week's integrity precondition.
- FAILURE CONDITION: wrong if any post-fix retest entry price deviates from a verified tape print,
  or auto-read produces a map row with no computed anchor.

### 4. Census-cell gates: ignition converts only dg<40% AND before 10:30 ET (env-gated, default per
Marcos's word); flat_top + vwap_reclaim to observe-only pending retrials
VERDICT: **recommend-ship-with-conditions** — REQUIRED CONDITION stated aloud: thresholds fitted
in-sample on ~50 trades; the proving week + harvester universe = the OOS test; env-gated with
Marcos choosing the default (IGNITION_CELL_GATE=0 observe-stamp-only vs =1 enforcing).
- Ignition evidence (timing-corrected v2): lane total honest -$185..-$120; COMBO dg<40 & early
  TRUE cell +$105..+$159 (N=20, 16 raw winners) vs FALSE -$290..-$278 (N=30). The detector is
  honest; the DESIGN admits the bleeding cohort (high-dg, late, below-open back-side) and every
  remaining gate is blind to it by construction (chart gate bypassed by lane design).
- Convexity Trader caveat: the split is a fitted threshold on ~50 trades; dg=40/10:30 are round
  numbers chosen after looking. If enforced, pre-register: cell definition FROZEN, graded on
  proving-week OOS only, no mid-week re-tuning.
- flat_top + vwap_reclaim → observe-only: their era books graded CODE-DEFECTS, not designs
  (flat_top/orb bought the break print in a retest costume via the vacuous 1%-above dip test;
  vwap_reclaim as coded = the just-crossed band the 7/31 study already refuted, while the 2-5min
  band-pass that PASSED was never encoded). Observe-only is not a death sentence — it is the
  honest state pending retrials of the actual designs. Autopsy-refutations law satisfied: both
  refutations here are autopsied to mechanism, not outcome.
- PRICE: build ~1-2 hrs (env gate + observe flips). Risk LOW (observe flips) / MED (ignition
  enforce — cuts a lane cohort on in-sample evidence). Expected $: era says cut cohort cost
  -$298..-$310; if the cell replicates OOS, ~$50-75/wk saved bleed. Kill: env per lane.
- FAILURE CONDITION: wrong if proving-week OOS shows the FALSE cell net positive strict-bracket,
  or the TRUE cell negative — either voids the split, gate reverts to observe.

### 5. Day-gain basis integrity (adjustment=split or prev-close cross-check)
VERDICT: **recommend-ship-tonight** — explicitly flagged as MARCOS'S CALL because it feeds crown
qualification (:7842), and crowns are his doctrine.
- Evidence: DFNS day_gain_at_entry 5152.57% (raw-adjustment prior_day_close on a split name).
  Corrupts: day-gain floor (vacuous/inverted), census day-gain cells, AND crown qualification —
  a split name can be crowned (privileges ×3) on a fictitious 5000% "gain".
- PRICE: build ~1 hr (adjustment=split on the fetch OR prev-close cross-check with reject-on-
  disagreement, fail toward the smaller gain). Risk LOW: pure input-integrity; changes which
  names qualify for floors/crowns only when the current number is fabricated. Kill:
  DAYGAIN_SPLIT_ADJ=0. Expected $: prevents one bad crown from spending 3x bullets on a
  split-artifact name — tail-risk insurance, not daily P&L.
- FAILURE CONDITION: wrong if any legitimately-crowned name loses its crown under the
  cross-check (Crown Steward audits the first week's crown roster before/after).

### 6. Contaminated-verdicts re-grade (#56) — did fake dollars vote?
Method: each verdict's claimed cohort checked against fictional_fills_census_20260813 (41 fills,
+$284.78 fake, HUIZ 8/7 $105.20 the largest; hidden v1 additionally condemned wholesale by
F-control -$4,012) and the sequence-honest brackets. Per-verdict:

- **8/12 cap raise (hidden 3→5, +$257 claimed)** → **FALLS (moot) + NEEDS-RERUN if hidden v2 revives.**
  The +$257 era offer was hidden-lane counterfactual dollars; the hidden v1 era book was struck
  8/13 (fictional fills + F-control -$4,012, 13% win). Contaminated dollars: the entire hidden
  era offer including BQ 8/12 $31.12-class fills inside the cap-cohort window. With hidden at
  observe (proving-week default), the cap is inert; do NOT carry the 3→5 verdict into v2 —
  v2 re-earns its own cap from honest rows. (PRE 6→8 half of the same sitting: PRE is a separate
  book by law and PRE conversions were reclaim/hidden-PRE — flag NEEDS-RERUN on strict PRE rows;
  First Hour + Opening Bell own it Friday.)
- **8/6 crown ext-bypass (+$641.87 claimed)** → **FALLS as priced; NEEDS-RERUN before any v2 carryover.**
  The +$641.87/26 crown-split was hidden-lane refused-fires-forward counterfactual — same struck
  evidence class (and 8/6 itself contains FVN $10.92 + WYHG/FBLG fictional fills). The bypass is
  currently inert (hidden observing). The DESIGN question (crowns exempt from the ext band) stays
  open for v2 with fresh honest evidence.
- **8/5 leader meritocracy (+$635 claimed)** → **NEEDS-RERUN (verdict conditionally stands; dollars unproven).**
  Privileges span lanes (ignition×3, slots×3, uncapped hidden, 60s reads) and the doctrine is
  Marcos's word ("to the winners go the extra bullets") — the doctrine stands on his authority.
  But the +$635 starved-setup evidence predates the fictional-fill strike and the timing
  correction; the era window (8/5+) contains struck names (HUIZ 8/7, DSY 8/7, FBLG 8/6). Re-run
  the starved-setup cohort on the verified book; until then quote the doctrine, not the dollars.
- **7/30 A1 ext-band (the +$1,472 "paying cell")** → **FALLS.** The paying cell was hidden v1's
  ext-band cohort; hidden v1's era profitability is struck wholesale (F-control -$4,012). The
  +$1,472 figure must not be cited again for anything. The ext-band QUESTION transfers to the
  Hidden Entry Architect's v2 program (whose first anatomy already found winners were BLUE-SKY
  regime — consistent with an ext-band effect, so the hypothesis re-registers, at $0 claimed).
- **7/26 exit doctrine** → **NEEDS-RERUN (partially survives).** Core-lanes sequence check: August
  core raw +$204.85 vs honest bracket -$140..-$65; timing fiction $270-$345; 11-21 fiction fills
  across 9 trades (MGRX, WYHG, FCUV, DSY, SPRC, YJ, CYCU, FBLG specimens). Any exit-doctrine
  sub-verdict that leaned on scale-fill prices is suspect. The doctrine's structure (scales +
  runner) is not refuted — its claimed dollars are. Trade Manager re-runs the 7/26 comparison on
  the strict bracket before Friday's go/no-go math uses it.

VERDICT: **no-action tonight beyond the two re-runs** (meritocracy cohort, exit-doctrine
comparison — both query-only, Statistician + Trade Manager, ledgered before Friday).

### 7. Hidden lane disposition after today's live test
VERDICT: **recommend HIDDEN_CONVERT back to 0 (observe-only) for the proving week.**
- Today's evidence, both ways, stated honestly:
  FOR keeping live: 4 conversions (+12.90, +5.04, -15.13, -19.29 = net -$16.48), ACCOUNTING
  CLEAN — fills matched tape under the fictional-fill fix; the test Marcos posed (are honest
  fills real when watched live) PASSED. No blowup; caps held; no fills after 10:33.
  FOR observe: net negative, and n=4 arbitrates the ACCOUNTING dispute only — by the 09:52
  pre-registered terms, "one green or red day does NOT settle expectancy." The expectancy
  evidence remains F-control -$4,012 / 13% win on the era. A small red day is exactly what the
  F-control predicts; nothing today rehabilitates the v1 entry signal. MF today is also the
  min-stop exemption specimen (3.11% stop, stopped in ~10s, ran to 15.38 then 18.26 post-halt) —
  v1's stop geometry losing money in miniature.
- Pre-registered term (2) said honest PROFIT reopens the era hearing; today was a loss — term
  fires in the direction of the standing condemnation. Reverting is not a new decision; it is
  the 8/14 01:39 observe ruling resuming after a one-day arbitration that resolved in its favor.
- PRICE: env flip only (HIDDEN_CONVERT=0), after-hours, flat-book verified in-turn at the flip.
  Risk of reverting: forgo any hidden profits next week (F-control says these are negative in
  expectation). Risk of keeping: re-exposing the proving week's honest book to a refuted signal.
- FAILURE CONDITION for the observe ruling: wrong if the shadow stream (hidden_observe_only rows,
  33 today) shows a would-have-been net-positive strict-bracket proving week — that is the v2
  Architect's evidence to bring, not a reason to pre-empt.
- Dissent recorded (Strength Ombudsman) — see Dissents.

---
## ROLL CALL (every office; finding or clean)

- **Blast Radius Auditor** (chair): the tuple-unpack pair is the third missing-unpack on the
  _curl_feed signature (8/8 _side_state precedent :8316) — Three-Rings was violated at ship time
  on items 1's bugs; any tonight-ship must enumerate ALL _curl_feed call sites, not just the two
  known. Session artifact ≠ ship convening; each approved item returns to LATEST.md vs the diff.
- **Dashboard Curator**: finding — every shipped item owes its display: breach alarm needs a
  dashboard chip; HIDDEN_CONVERT state belongs on the cockpit not just the boot banner (#57
  member endorsed); census-cell gate needs a stamped-cell column.
- **Systems Quant**: finding — author of all 4 audits; stands behind the smoking gun and the
  "detector honest / design admits the bleed" ignition attribution; confirms sample verification
  (DFNS, AMIX to the tick; LBGJ/AKAN/BOXL walked the coded path).
- **Pit Crew Chief**: finding — no deploys intraday (law held today except Marcos's explicit
  09:52 override); tonight's ships sequence: item 1 first (restores approved behavior), then
  #57 defect members, then behavior members, one change-set, rig between; flat-book check
  in-turn at every restart.
- **Integrator**: finding — item 1 is a wiring-seam defect class; demands a parallel-logic sweep
  of every _curl_feed consumer + a rig question pinning the tuple contract so a fourth instance
  cannot ship.
- **Side Marshal**: finding — ignition has NO side term (D3, MIN_EXT=-5% admits below-open
  back-side, BOXL specimen); endorses the census-cell gate and asks the side stamp ride along
  observe-first on ignition rows.
- **Crown Steward**: finding — day-gain corruption feeds crown qualification (:7842, DFNS 5152%
  class); endorses item 5 with the before/after crown-roster audit as his condition; notes the
  8/6 crown ext-bypass dollars falling does not touch crown doctrine itself.
- **Feed Engineer**: finding — _curl_feed's tuple return changed its contract without all
  consumers updated: that is OUR defect class (vendor-surprise-twice rule applied internally);
  item 1's fix must include the contract pinned in a rig case.
- **Webull Broker Desk**: clean on the docket — no order-semantics changes proposed; standing
  reminder: the ~8/23 token re-mint lands in trial week; the $5 place+cancel test still owed.
- **Quartermaster**: finding — 7 untracked bars10s files for 8/12 (BIVI, BOXL, BQ, CHOW, RMCF,
  SBEV, WCT) sit uncommitted in the working tree; ferry them under the normal bars pipeline
  (not this artifact's commit).
- **Kev Librarian**: clean on the docket — no Kev-corpus contradictions in any item; notes item
  2 is Kev-faithfulness-positive (the open is his window) and the kev-sheet day-gain exemption
  is unaffected by item 4.
- **First Hour**: finding — endorses items 2 and 4 jointly: they concentrate fire in 9:30-10:30
  where ignition's paying cell lives and open the window to the only green lane; asks the
  offered-vs-captured open audit be re-based once item 2 lands.
- **Opening Bell**: finding — item 2 changes the 9:30 handoff (lane armed at the bell for the
  first time); pre-open warmup must complete before 09:30 or fail loud, not fire on a partial
  seed — add to the gauntlet checklist.
- **Seam Scientist**: finding — the ma_pullback anticipation-shadow proposal (audit proposal 3)
  is his method exactly; endorses as observe-only rows, no ship needed, prices the confirmation
  premium for v2.
- **Strength Ombudsman**: DISSENT on item 7 (see Dissents); on item 4, warns the ignition cell
  gate refuses strength late in the day — demands the refused-strength hearing (dollars of
  refused fires that then ran) be part of the weekly bias ledger from day one of enforcement.
- **Forward Architect**: finding — registers two hypotheses from this session: (a) ignition side
  term as a designed feature not just a gate patch; (b) vwap_reclaim band-pass (2-5min hold)
  harvester retrial — both to the post-freeze backlog with kill-tests attached.
- **Momentum Operator**: finding — nothing on this docket ships on noise EXCEPT item 4's
  enforce-mode (fitted ~50 trades); his signature goes on observe/stamp mode freely, on enforce
  only with the OOS condition pre-registered. Items 1, 3, 5 are not noise questions (defects).
- **Trade Manager**: finding — owns the 7/26 exit-doctrine re-run (item 6, strict bracket);
  notes the fiction-removed August core (-$140..-$65) means exit-capture claims are currently
  unpriced; nothing in tonight's ships touches exits except entry-print honesty (:10955), which
  he endorses.
- **Tape Veteran**: hypothesis (not verdict) — ONFO's 11 refusals while 6-49% past a stale break
  smell like the bot fighting yesterday's map all morning; expects item 1 to visibly change the
  tape interaction on breach names within days; watch for over-eager refreshed-map chasing as
  the new failure mode.
- **Reclaim Architect**: finding — concurs the coded vwap_reclaim is the refuted just-crossed
  band, NOT his design; the 7/31 band-pass (2-5min held) never stood trial; observe-only is
  correct and the retrial build belongs to him + Forward Architect via the harvester.
- **Execution Surgeon**: finding — :10955 assumed-price retest fills are a planned-R vs
  realized-R lie at the entry; strongest possible endorse of that #57 member; MF's 3.11% stop
  (exemption class) shows planned risk ≠ tradeable risk on thin names.
- **Handicapper**: finding — day-gain is a selection input; item 5 cleans his primary variable;
  character book gains a split-flag field (data-only) when item 5 lands.
- **Rocket Rider**: clean on the docket — no parabolic-regime item; notes MF's post-halt 18.26
  resume is vertical-regime evidence for the named open hole (vertical-regime entries), which
  stays with the meritocracy docket, not tonight.
- **Cartographer**: finding — item 1 restores his freshness contract from the dead; condition:
  every auto-map refresh must write computed structural anchors only (maps-describe law), and
  the alarm row is his requested tripwire — endorse both.
- **Wind Tunnel Engineer**: finding — the timing-corrected brackets (trail..flat) are the
  correct fidelity frame; warns item 2's gauntlet must replay the WORST sessions (7/27, 7/29,
  8/6 class) with the seeded EMAs, not average days; TRAIL variant is a strictness bound, not
  the lanes' true replay (caveat 2 carried).
- **Statistician**: finding — owns the item 6 re-runs; rules the following figures RETIRED from
  citation: +$1,472 (A1 ext-band), +$641.87 (crown bypass), +$257 (cap raise), +$635 (pending
  re-run); the ledger keeps them with strike annotations, never as live evidence. In-sample
  warning stamped on item 4 at his insistence.
- **Convexity Trader**: finding — judges item 4 by mean-after-costs + tail shape: the cut cohort
  is mean-negative with fat left tail (late high-dg entries); supports enforce ONLY with the
  frozen-cell OOS condition; win-rate arguments (16/20 raw winners) explicitly disallowed as
  the basis.
- **Curl Mechanic**: finding — fire-count acceptance bands owed on items 2 and 4 (registered in
  their prices); reclaim/zone_flip acceptance unchanged (zone_flip stays shadowed under its
  pre-registered re-arm).
- **Project Manager**: finding — tags for the record: today's hidden result [VERIFIED] (tape-
  verified fills, net -$16.48); freshness 28/8 [VERIFIED this session]; +$635 meritocracy
  dollars [UNVERIFIED pending re-run]; morning brief tomorrow carries the decision menu status.
- **Historian**: finding — for the record: today = the day the freshness contract was discovered
  never to have run (8/7-8/14, seven calendar days inert); the 09:52 override is logged as a
  one-day arbitration under Marcos's explicit word, not a doctrine change; official RTH day
  ranking unaffected by hidden's -$16.48 pending tonight's close.
- **Hidden Entry Architect**: finding — claims today's 4 conversions + 33 hidden_observe_only
  rows + the MF stop anatomy as v2 syllabus; endorses item 7 revert (v1 signal stays refuted;
  today arbitrated accounting, and accounting won — that VALIDATES the measurement rig his v2
  will be judged by); the ext-band and cap questions re-register under v2 at $0 claimed.

---
## DOCTRINE-INVERSION SWEEP
Checked each docket item against standing doctrine for silent inversions:
1. **Chart-as-gate (LOCKED)**: item 4's ignition cell gate adds a scalar gate to a TAPE lane that
   bypasses the chart gate by design. This is a lane-scoped tradeability/cohort cut, not a
   setup-quality scalar revival — but it RHYMES with the refuted scalar-selection class. Named
   aloud; the OOS condition is the containment. No inversion in items 1/3/5 (defect/integrity).
2. **"No absolute never-trade"**: flat_top/vwap_reclaim observe-only is lane suspension on
   code-defect grounds with retrials attached — not a never-trade doctrine inversion. Zone_flip
   stays under its pre-registered re-arm.
3. **Leader meritocracy**: item 6 strikes its DOLLARS not its doctrine — Marcos's word stands;
   privileges continue; only the +$635 citation is suspended pending re-run. Not an inversion.
4. **Freshest-data rules**: item 1 RESTORES this doctrine (gates consult current structure);
   the alarm row enforces it. Item 3's auto-read likewise. Aligned.
5. **Maps describe, never serve**: auto-map refresh must emit computed anchors only —
   Cartographer's condition binds any ship. Aligned if honored.
6. **Official = RTH; PRE separate**: PRE cap 6→8 re-run flagged (item 6) keeps the books split.
7. **Intentional inversions carried (unchanged, by Marcos's prior order)**: leader-meritocracy
   privilege stack; 7/24 convert-at-detection. Nothing tonight touches them.

## DISSENTS
- **Strength Ombudsman on item 7**: today's honest tape was net -$16.48 on n=4 with accounting
  CLEAN — the accounting dispute resolved in the bot's favor, and reverting to observe the same
  day the measurement was vindicated is the strength-refusing reflex he is chartered to
  prosecute. He would keep HIDDEN_CONVERT=1 at half size through the proving week and let the
  verified book speak. ROOM RESPONSE: the 09:52 pre-registered terms said profit reopens the
  hearing, loss does not — honoring pre-registration outranks the bias concern here; his
  refused-strength hearing on hidden shadow rows is granted weekly. Dissent recorded, not
  adopted.
- No other office dissents from the docket verdicts as conditioned.

---
## DECISION MENU FOR MARCOS (yes/no per line)

| # | Item | Recommendation | Price | If YES | If NO |
|---|------|----------------|-------|--------|-------|
| 1 | Tuple-unpack pair (:8373, :8461) + breach alarm | SHIP TONIGHT | ~30 min; risk LOW-MED; kills AUTO_MAP_REFRESH=0 / RUNWAY_WALL=0 / BREACH_ALARM=0 | The 8/7 freshness contract + 8/8 runway wall run for the first time; ONFO/DFSC-class refusals end; 3 silent breaches = alarm | Maps stay frozen at first read (28 breaches/day and counting); wall stays inert; both approved-by-you features remain fiction |
| 2 | ma_pullback warmup-wall fix (seed EMAs) | SHIP WITH CONDITIONS (gauntlet replay first; MA_WARMUP_SEED=0 kill; fire-band 1-4/day) | ~1-2 hrs + same-night gauntlet; risk MED (unmeasured open cohort) | Your only green lane sees the open Monday; week-1 open cohort graded strict | Green lane stays blind until ~10:40; open stays Kev's window in doctrine only |
| 3 | #57 bundle (auto-read, blue-sky reroute, NameError, exit_ts, boot banner, real-print retest fills) | SHIP TONIGHT (defect/honesty members); behavior members each named + killed separately | ~2-3 hrs; risk LOW/MED | Entry prints become tape-honest (proving-week integrity); known defects closed | :10955 keeps booking assumed entry prices — the entry-side fictional-fill class stays live into the proving week |
| 4 | Ignition cell gate (dg<40 & <10:30) env-gated + flat_top/vwap_reclaim observe-only | SHIP WITH CONDITIONS — you pick default: observe-stamp (=0) or enforce (=1); cell FROZEN, OOS = proving week | ~1-2 hrs; risk LOW (observe) / MED (enforce; fitted on ~50 trades) | Bleeding cohort cut (era says ~-$300 avoided) or stamped for OOS proof; two defect-graded lanes stop trading their broken era code | Ignition keeps buying the late high-dg back-side cohort every gate is blind to; flat_top/vwap_reclaim keep trading refuted code paths |
| 5 | Day-gain basis integrity (split-adjust / cross-check) | SHIP TONIGHT (your call — touches crown qualification) | ~1 hr; risk LOW; kill DAYGAIN_SPLIT_ADJ=0; crown-roster before/after audit | DFNS-5152%-class corruption ends; crowns can't be won on split artifacts | A split name can be crowned and get 3x bullets on a fictitious gain |
| 6 | Contaminated-verdicts re-grade | NO SHIP — two query-only re-runs (meritocracy cohort; 7/26 exit comparison), figures +$1,472 / +$641.87 / +$257 retired, +$635 suspended | ~1 hr queries; risk none | Friday's go/no-go math runs on strict numbers only | Struck dollars keep voting in doctrine you'll bet real money on |
| 7 | Hidden lane | REVERT HIDDEN_CONVERT=0 for the proving week (after-hours flip, flat-book verified in-turn) | env flip; risk = forgo F-control-negative expectancy | v1 observes; shadow stream feeds v2; accounting rig stands vindicated | Refuted v1 signal keeps trading the proving week's honest book (Ombudsman dissent: keep at half size — recorded) |

Standing constraints on any YES: each ship gets its own LATEST.md convening vs the actual diff,
rig green, after-hours deploy, flat-book verified in-turn, one change-set per night ordering per
Pit Crew Chief. Nothing here is shipped by this artifact.

— Session closed 2026-08-14 early sitting. Blast Radius Auditor, chair.
