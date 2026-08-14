# THE CHRONICLE — era record, 7/13/2026 → 8/13/2026
Maintained by the Historian (12th office, chartered 8/13). Append-only. Every claim carries a
citation: a RESULTS_LEDGER.md heading (root ledger = 8/2+; data/killtests/RESULTS_LEDGER.md =
7/23–8/1), a killtests artifact filename, or a MEMORY.md index entry. Anything uncitable is
tagged [UNCITED — needs verification]. RTH headline / PRE separate, always (8/4 ruling).

Citation key: [L root <heading>] = /Users/marcosolivera/Desktop/Marcos-Trading-Bot/RESULTS_LEDGER.md ·
[L kt <heading>] = data/killtests/RESULTS_LEDGER.md · [KT <file>] = data/killtests/<file> ·
[MEM <entry>] = MEMORY.md index entry.

---

## ERA FOUNDATION

**2026-07-13 — THE ERA BOUNDARY.** Line in the sand: all strategy analysis and kill-tests use
7/13+ only; book totals before it accepted as-is. 7/13 itself posts RTH +$234.15 — the era
record for three weeks. [MEM feedback_era_boundary_0713; OFFICIAL_BOOK.md 2026-07-13]
Correction eras that govern the record: stored P&L wrong ≤7/20 (runner-leg bug, 37 records,
apply pnl_runner_leg_correction_20260726.json); 80 pre-7/14 records uncorrectable.
[MEM project_pnl_correction_ledger]

**2026-07-17 — DOCTRINE: CHART-AS-GATE SETTLED.** The chart read GATES trades; scalars are
inputs only. Every setup-quality scalar tested since has been refuted (room, day-gain selector,
momentum, extension, and later min-stop's spread form). [MEM project_chart_gate]

**2026-07-20 — VWAP anchor settled (premarket); accumulator math had been fixed 7/18.**
[MEM project_vwap_measured_error]

**2026-07-22 — Ticker Character Book live (data-only).** [MEM project_character_book]

**2026-07-23 — Alpaca migration build + vendor completeness verdict (the migration gate,
MEASURED, 2 runs stable).** [L kt 7/23 #97; L kt 7/23 #83]

**2026-07-24 — hidden_entry lane live (Kev's 10s rocket playbook), rocket_catcher superseded.**
[MEM project_hidden_entry_lane] Same date: the wipe law — write the AFTER-state before any live
state-changing action; merge-only on replace endpoints. [MEM feedback_replace_endpoint_merge_only]

**2026-07-26 — DOCTRINE: chart-gate refinement + the gate purge.** Marcos: "no absolute
never-trade — let the chart and tape decide": do-not-trade blocks CHART lanes only; tape lanes
trade through by design. Nine contradiction reviews shipped fixes across entries/exits/sizing/
discovery/capture/dashboard the same weekend. [MEM project_chart_gate; L kt 7/26 review entries]
Era VOIDED as a strategy measurement the same day (47 uncomputable, no clean day).
[MEM project_new_era_baseline; KT FABLE_REVIEW_20260726_pnl.md]

## THE DISASTERS AND THEIR FIXES

**2026-07-27 — THE PREMARKET BLACKOUT, −$624.50 PRE.** 5 premarket vwap_reclaim entries
04:14–07:06 all exited blind-stop failsafe (BIYA −262.89, LGHL −166.40, VEEE −99.47, MTNB
−14.26, JZXN −81.48) — custody losses, not strategy losses. Root cause: `_alpaca_intraday_bars`
RTH-only filter returned [] premarket; all 8 monitor/scan call sites omitted `sessions=`.
Follow-on defect: all 5 exits were OFF-TAPE (priced below the day's low on both 10s feeds) —
−$624.50 of the book is fiction. [L kt 7/27 MORNING INCIDENT; L kt 7/27 DATA-INTEGRITY DEFECT]
FIXES: same night `sessions=["PRE","RTH"]` + DST fix rig-green; off-tape exit guard
`_verify_exit_px` shipped item 8 (rig 23/23, catches 4 of 5 incident exits; JZXN-class named
uncatchable gap). [L kt 7/27 ITEM 8 SHIPPED] PRE entries fully restored 8/10 (07:00–09:25,
9:25 flatten). [MEM project_premarket_bars_blackout, superseded note 8/10]
Same day: the REVIEW-BOTH-SIDES law (consistency-only review missed three coherent bad designs;
cost $732). [L kt 7/27 LAW; MEM feedback_review_both_sides] Intrabar-stop kill-test REFUTED as
specified — Marcos overrode, INTRABAR_STOP=1 live. [KT KILLTEST_20260727_intrabar_stop.md;
MEM project_intrabar_stop_refuted] Min-stop-width: my refutation reversed after permutation
p=0.0047 + OOS +$385.16; 6% gate shipped on Marcos's management call.
[L kt 7/27 REVERSAL; L kt 7/27 SHIPPED (management decision)]

**2026-07-28 — Premarket price = yesterday's close (found by Marcos from the dashboard);
session-aware price fix A shipped premarket. Halt-awareness gap discovered live ("we buy the
top of a halt???" — LGHL filled at the exact HOD, halted immediately after; zero halt detection
in code).** [L kt 7/28 06:5x P0; L kt 7/28 11:0x NEW GAP]

**2026-07-29 — THE RESTART FORCE-CLOSE.** Restart with 3 open positions after a "book is flat"
claim; `_recover_orphaned_trades` force-closed STFS (−$27.84) and YYGH (+$14.18). Law:
flat book verified in-turn before any deploy/env-change/restart.
[MEM feedback_flat_book_verified_in_turn] Also 7/29: hostile-tape-gauntlet law after 3 ruined
opens in 3 sessions. [MEM feedback_hostile_tape_gauntlet] Live P0s shipped premarket
(stale-fire guard suppression fix, monitor bar-price fallback). [L kt 7/29 07:45; 7/29 08:25]

**2026-08-02 (Sat) — Floor was OFF in production 7/29–7/31, fixed; resting broker stop SOLVED
at the code level (STOP_LOSS + stop_price, preview-proven HTTP 200 — June had spelling AND
field wrong).** [L root 8/2 both entries; MEM project_intrabar_stop_refuted]

**2026-08-06 — The sym=t crash-loop ruined the open during WYHG/ENSC halts → the THREE RINGS ×2
law (unverified blast radius is the sin).** [MEM feedback_execution_proof_every_change]
Same day midday: "the day the offense showed up" (+$54.97 RTH as of ~12:15); night: the five
builds; the Friday-sheet bug pair and Marcos's NAMI/CLRO correction. [L root 8/6 entries]

**2026-08-10 — The _he_day crash loop: 13 boots by 10:04.** My #35 rebuild cleared `_he_day` at
boot → KeyError → process death → Railway restart loop, degrading monitors with 3 open
positions on halt-heavy tape. Emergency RTH push on Marcos's explicit call; fix reseeded the
dict + defensive .get. Silver lining: #35 painless-restarts passed its live gauntlet
involuntarily. [L root 2026-08-10 ~10:2x EMERGENCY RTH PUSH]

**2026-08-13 — THE FREEZE INCIDENT.** Freeze = unindicated non-expiring kill lever; cost
re-verified on the corrected clock: 13 refused fires in the window (real, not zero).
[L root 2026-08-13 ~16:15 THURSDAY DEBRIEF] The "28-minute" duration figure:
[UNCITED — needs verification; not in the ledger entries reviewed]. Freeze hardening slotted
second in tonight's resequenced build order. [same entry]

## DOCTRINE RULINGS (the spine)

- **7/17** Chart-as-gate settled. [MEM project_chart_gate]
- **7/26** Refinement: no absolute never-trade; tape lanes trade through. Gate purge weekend.
  [MEM project_chart_gate; L kt 7/26 entries]
- **7/27** Review both sides (outcome AND consistency). [L kt 7/27 LAW]
- **8/4** Official = RTH, PRE separate [MEM feedback_rth_official_pre_separate]; dollars-not-R
  [MEM feedback_dollars_not_r]; maps describe, never serve [MEM feedback_maps_describe_not_serve];
  edge over mechanisms [MEM feedback_edge_over_mechanisms]. ENTRY_OPEN_ET 04:00→07:00
  (aligned to Kev's stream). [L root 8/4 08:32]
- **8/5** Leader meritocracy live ("to the winners go the extra bullets": sticky crown →
  ignition×3, slots×3, hidden uncapped, 60s reads) + back-side gate live. [L root 2026-08-05
  LEADER DAY; MEM project_leader_meritocracy; MEM project_backside_gate]
- **8/6** Freshest-data rules (CELZ specimen, ~$150): gates consult the most current structure
  regardless of source. [MEM feedback_freshest_data_rules]
- **8/7** "Let the chart and tape decide" — veto/mapless collision fixed; "I have never given
  Kev veto power" — veto stripped. Halt lane + seam lane born; freshness contract ordered.
  [L root 8/7 09:2x + ADDENDUM; 8/7 11:5x; 8/7 12:0x]
- **8/8** Halt-lane settlement: arm-only converts Monday, 5s feed, crowns, half size;
  breathless-tape confirm demoted to stamp; verdicts moved to Tuesday night. Margin decision:
  live trial runs on margin. [L root 8/8 20:5x; 2026-08-08 latest CONFIRM DEMOTED;
  2026-08-08 close of research; 2026-08-08 night ACCOUNT DECISION]
- **8/10** Scanner = discovery source of record; the board is the universe; "Webull bottleneck"
  was a browser timer. [L root 2026-08-10 ROSTER ARCHITECTURE ORDER; 2026-08-10 BROWSER TIMER;
  MEM feedback_scanner_source_of_record]
- **8/12** Level primacy: OUR chart levels govern Kev's tickers, pure A/B, prereg frozen
  (level_primacy_ab_PREREG_20260812.md); officers' panel 8–3 with three dissents on permanent
  record. NO-VETO encoded: "the chart and tape decide. No one has veto power" — re-grade first
  (branch fired zero times era-wide), skip branch removed, veto language data-only.
  [L root 2026-08-12 ~21:15 LEADER DECISION; 2026-08-12 ~21:30 DOCTRINE ENCODED]
- **8/13** Manual-override-first (surface the no-code levers intraday and ASK)
  [MEM feedback_manual_override_first; L root 2026-08-13 ~11:40]; auditor-cannot-authorize
  (the widen-to-7% slid into the ship; "keep how we have it" — behavior changes go back to
  Marcos priced) [L root 2026-08-13 ~01:20]; no-widening ruling encoded, post-fill observe-only.
  [same entry]

## FIRSTS

- **First crown day: 8/5** ("LEADER DAY: crowns, 0.4 rung, back-side gate").
  [L root 2026-08-05 LEADER DAY] The specific first crowned ticker:
  [UNCITED — needs verification].
- **PRE lane live intraday 07:00–09:25: shipped by 8/10 era of sessions fixes**
  [MEM project_premarket_bars_blackout superseded-8/10 note]. The task brief's "PRE lane live
  7/25" date: [UNCITED — the ledger shows premarket entries were live BEFORE 7/27 (the incident
  presupposes them, enabled by "Saturday's reclaim-window fix", i.e. 7/25/26 weekend)
  — L kt 7/27 MORNING INCIDENT root-cause note].
- **First deploy through ship.sh: 8/13 00:56 ET** (stop-coherence floor; all three gates
  exercised live). [L root 2026-08-13 ~01:00]
- **First manual crowbar: 8/13 11:11** (manual map POST for FGI; fire 33s later; reader
  self-posted a proper summit map 11:13 = bootstrap proof). [L root 2026-08-13 ~11:40]
- **First convening under the convene-or-don't-ship law: 8/10 ~11:4x** (Blast Radius Auditor on
  the 16:05 batch; 9 findings on a rig-passed batch). [L root 2026-08-10 ~11:4x]
- **Historian chartered: 8/13** — 12th office; founding exhibits: mis-ranked 8/13 from memory
  (5th, not 2nd) and mixed PRE into the RTH book, both caught by Marcos.
  [persona_historian.md]

## THE OFFICES AS CHARTERED (dated where citable)

Standing lenses (Momentum Operator, Trade Manager, Systems Quant, Tape Veteran, Feed Engineer,
Reclaim Architect, Execution Surgeon, Handicapper, Pit Crew Chief, Rocket Rider, Integrator,
Cartographer, Wind Tunnel, Statistician, Convexity, Opening Bell, Curl Mechanic, Project
Manager) predate the numbered-charter era. [MEM Personas section — charter dates uncited]
- **8/7**: Blast Radius Auditor (mandatory pre-ship), Crown Steward, Side Marshal, Strength
  Ombudsman. [MEM persona entries, Marcos 8/7]
- **8/8**: Seam Scientist, Dashboard Curator, Forward Architect ("SEVENTH OFFICE," Marcos's
  charter). [L root 2026-08-08 SEVENTH OFFICE; MEM persona entries]
- **8/9**: Webull Broker Desk (8th), First Hour (9th, Opening Bell rescoped to the lead-up),
  Kev Librarian (10th). [L root 2026-08-09 EIGHTH/NINTH OFFICE; 2026-08-09 late TENTH OFFICE]
- **8/12**: Quartermaster (11th; first audit executed same night; books backup live 22:30).
  [L root 2026-08-12 ~00:25; ~00:35; ~00:30 PARACHUTE]
- **8/13**: The Historian (12th). [persona_historian.md]
- Standing-room law (everyone present at all times, roll-call outputs): 8/10.
  [MEM feedback_convene_or_dont_ship]

## THE WEEK OF 8/10–8/13 (day-level)

**Mon 8/10 — RTH +$57.28 / PRE −$0.35, 14 trades.** [OFFICIAL_BOOK.md]
Margin transfer landed 00:0x; PDT protection off ~09:15. The _he_day crash loop (above) →
emergency RTH push. XHLD $50 lesson → halt-stack directive ("two different animals, two
entries"). Full-warm boot ordered ("Restarts should not affect anything"). First auditor
convening under the law. The composition docket: WYHG (death by a thousand correct refusals),
TNON, RDGT (crown-anchor hole + the missed ride = the bench hole), THH (mapless newcomer) —
unified diagnosis: "This latency issue is stealing money from us." Scanner ruled source of
record; the 5-min "Webull bottleneck" exposed as a browser timer. Restart-proof batch 16:3x,
evening batch 2 (~18:0x, 4th audit of the day), restart drill PASS 19:17. Night: Duty Officer
Portal shipped (task #44), iOS light-mode fix.
[L root 2026-08-10 entries, 00:0x through night]

**Tue 8/11 — RTH +$58.36 / PRE +$46.26, 29 trades.** [OFFICIAL_BOOK.md]
~00:45 real light theme shipped. ~01:35 late Tuesday sheet recovered from TikTok; ~01:50–02:00
four Kev TikTok lessons (SCKT 5-second vertical among them) — heavy doctrine night. Marcos on
the road from 10:00. 16:15 ghost open-trades fixed (task #46). EOD miss audit (194 reject rows
vs post-reject tape). Evening replays run on era SIP tape. 23:40 TikTok sheet backstop shipped
(#45). Tuesday sitting: backside amendment withdrawn (my correction), red-to-green exemption
refuted (two kill-tests, no ship), summit sanity shipped (PLAG stale-map defect), all verdicts
rendered ("agree on all"). [L root 2026-08-11 entries]

**Wed 8/12 — RTH +$254.99 / PRE +$29.18, 21 trades — 3rd-best RTH day of the era.**
[OFFICIAL_BOOK.md] Quartermaster chartered + first audit + books-backup parachute live. Email
tiering shipped; crown pin in 1s roster; burst hypothesis refuted (v2 — "could be huge" — it
isn't). Wednesday sitting + batch (9th convening, 9/9). Reader start 07:00 shipped. Stale-cap
review; map-value grading. 21:15 LEVEL PRIMACY decision (8–3 panel, dissents recorded, prereg
frozen); 21:30 NO-VETO encoded. PRE-10 + crown session-cap exemption (auditor caught a real
refund leak). 23:00 premarket board RTH parity. 23:55 convene-or-don't-ship INTERLOCK after
the ship-census answer. [L root 2026-08-12 entries]

**Thu 8/13 — RTH +$208.53 / PRE −$10.58, 20 trades — 5th-best RTH day. THE CAGE-AND-CROWBAR
DAY.** [OFFICIAL_BOOK.md; L root 2026-08-13 ~16:15]
- Overnight: full live-state audit ("GO for 03:55"); 01:00 stop-coherence floor 0.5% = FIRST
  ship.sh deploy (00:56); 01:20 Marcos catches the unconsented widen-to-7% → no-widening ruling
  + auditor-cannot-authorize law; 02:00 predetermined resting sells ratified for go-live
  (task #53; spread-cap deferred to Friday). [L root 2026-08-13 00:10–02:15]
- Morning: FGI caged by the first-read blue-sky deadlock (blue-sky output exists only in the
  reread lane; reread lane reachable only with an existing map). Crowned name ran +60% while
  caged ~4.5h–6h [MEM feedback_manual_override_first says 6hrs; debrief says 4.5h caged — the
  4.5h figure is the in-ledger number]. [L root ~11:40; ~16:15]
- 11:11 THE CROWBAR: Marcos — "why didn't we just make FGI a map" — manual map posted; fire 33s
  later; reader self-posts a summit map 11:13 (bootstrap proof). XHG protective map = the
  counter-face (cage saved 5 fires into a −37% collapse) → fix = information, not removal.
  Batch NIVF/WAFU/CMND/PTN/PLRZ 11:35; 58 mapped, zero fired-actives blind. 12:58 SECOND batch
  (nine new fired-and-mapless: LEXX, MSGY 12 fires, INHD, TOPS, JUNS, SHPH, ARTW, EXOD, UPLD);
  68 total. Twice in one session = auto-read (Build 3) is a requirement, not an improvement.
  FGI blue-sky rereads self-updated as it climbed (summit 16.50 → 18.45). [L root ~11:40]
- Result: FGI +$155.75 net across 8 trades. Freeze incident cost 13 refused fires (re-verified
  clean clock). INHD exited 11.90 before the 10.90 halt-down. One trade = 40% of RTH — the
  caged names WERE the missing tail (Convexity). [L root ~16:15]
- 16:15 Thursday full-room debrief, 30/30 offices including the Historian's day one. Top-5 by
  Monday impact: blue-sky deadlock; freeze lever; refused-strength pile-on (HCTI 5 gates);
  the 12-hour time-filter bug (all prior time-windowed censuses suspect); manual-map ceiling
  amendment. [L root ~16:15]
- Night (resequenced by dependency): (1) censuses on the clean clock — DONE: census_lib.py
  shipped, v1 gate-cost artifact VOID-stamped, PRE gate-cost v2 official (staleness ceiling
  25 refusals +$59.03 left on table; firevol floor −$21.60 saved, vindicated; net +$37.43/wk).
  [L root 2026-08-13 evening NIGHT ITEM 1] Remaining slate: freeze hardening, #54 builds
  (blue-sky first reads + auto-read + manual-map amendment), MAX_TRADE_DOLLARS, staleness
  review, four-arm rerun, Historian backfill (this document), drill re-verify. Ships beyond
  item 1 not yet in the ledger at this writing — [UNCITED until their entries land].

## STANDING CORRECTION NOTES (folklore vs ledger)

1. "8/13 was the second-best day" — FALSE; 5th (+$208.53). [OFFICIAL_BOOK.md; persona_historian.md]
2. "Webull rejects stop orders" — was a malformed request, never a platform limit; solved 8/2.
   [L kt 7/27 CORRECTION; L root 8/2]
3. "Frozen-price exit monitor" (7/28) — RETRACTED same day; monitor was correct.
   [L kt 2026-07-28 RETRACTION; MEM project_halt_awareness]
4. "Min-stop width refuted" — the %-of-entry form is SUPPORTED (p=0.0047, OOS +$385.16); only
   the spread-relative form is refuted. [L kt 7/27 REVERSAL]
5. "The 5-min scanner refresh is a Webull limit" — busted; it was a browser timer.
   [L root 2026-08-10 BROWSER TIMER]
6. "MIN_STOP_PCT=6" — stale; the standing setting is 4 (8/3 ruling), and the floor was OFF
   Wed–Fri of the 7/28 week for data purity. [L root 2026-08-13 ~00:10; L kt 7/28 09:5x]
7. Era P&L as strategy evidence — VOID as a measurement since 7/26; best-available only.
   [KT FABLE_REVIEW_20260726_pnl.md; MEM project_new_era_baseline]
