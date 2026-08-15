# SHIP CONVENING — 2026-08-14 (night) E3 OOS-wall machinery: grinder-1030 shadow detector + nightly shadow grader
covers: aa3ff9ff669c (the code commit, audited against `git show aa3ff9f` line-by-line this session) and f2abaaabc471 (post-audit bookkeeping: RESULTS_LEDGER entry + the pre-registered stress-G research script, data/killtests only, no live-path code).
Chair: Blast Radius Auditor. Separate-context convening: every claim below is from a read or an execution run THIS session — nothing carried on trust from the authoring session.

## SHIP DESCRIPTION + AUTHORIZATION
Two builds, no deploy, no push. BUILD 1: `grinder_shadow_step` (#48 vertical-regime lane, E3 OOS-wall nominee per edge_stresstest_F PASS 5/5) behind `GRINDER_SHADOW` default **"1"** — shadow-only detector riding the reclaim block's fed 10s bars (zero new fetches, exactly the v2-shadow pattern); logs `grinder_shadow_fire` rows and nothing else. BUILD 2: `data/killtests/nightly_shadow_grade.py` grades the day's shadow rows (grinder + flat_top_observe_only + v2_shadow_fire) through the E3 exit model and appends one line/day to `data/history/OOS_WALL.md`; launchd 23:00 ET daily (`com.marcos.tradingbot.shadowgrade.plist`).
Authorization: shadow-row-writer + offline grader only — nothing the bot does with MONEY changes under any env value (auditor-cannot-authorize satisfied by construction). The OOS wall is exactly the >=5-day evidence gate Marcos's 8/8 law demands before any conversion talk.

## FINDINGS (each verified by direct read/execution this session)
1. **GRINDER_SHADOW default ON** — VERIFIED: `os.environ.get("GRINDER_SHADOW", "1") == "1"`; rig AA-a EXECUTES the exec'd segment with empty environ -> True.
2. **Detector matches KT2a/TEST-H spec** — VERIFIED by read: candidate = a NEW session-high print (`new_hi and prev_hi is not None`) after 10:30 ET (`hour*60+minute < 630` skip); gates = last-30-min net-up (`c > w30[0][3]`), `c > vwap` (vwap absent/0 = no fire, conservative), max drawdown-from-running-high over the 15-min window `< 0.03`, 900s per-name cooldown (`cool_k` set only on fire), would_stop = 15-min low with degenerate-stop guard (`lo15 < c`). Day rollover rebuilds state. Rig AA-a executes fire/stop/cooldown/VWAP-gate on a synthetic tape and pins px/session_hi/would_stop/mins_since_1030/seq.
3. **ZERO conversion path, scanned from scratch** — detector block and the caller block inside `wait_for_flat_top_entry` grepped this session: no `breakouts.append`, no `execute_trade`, no order call; caller logs the row and STOPS, try/except-walled. Rig AA-b pins both regions plus the full row schema (price, session_hi, vwap, mins_since_1030, would_stop, in_lane, seq, time_hm).
4. **Grader sims E3 exactly** — VERIFIED by read of `sim_e3` against the stress-F method notes: chase entry +1%, $500 fractional; per-bar order = 15:59 flatten -> stop-first (fills stop*0.995) -> bank 1/2 at the +10% limit EXACTLY (consumes the bar, engine order) -> run-high update from post-entry highs only (run_hi starts at ENTRY) -> trail on close < 0.90*run_hi (fills c*0.995); tape-end flatten at last close; NO breakeven; NO lookahead (only bars strictly after the fire timestamp). Haltgap omitted and DISCLOSED in both the script docstring and the wall header.
5. **WETO hand-trace reconciled INDEPENDENTLY this session** — I re-ran the spot-check myself (not trusting the authoring session's number): WETO v2 fire 2026-08-14 14:03:03 ET, px 7.935, stop 7.77 -> entry 8.01435, 62.3881 sh; bank at 18:03:10Z (h 9.38 >= 8.8158), trail exit at 18:16:50Z (c 8.73 < 0.90*9.94) -> **$+45.9624**; my bar-by-bar hand replication and the grader's `sim_e3` match to full float precision.
6. **Wall proof line honest** — OOS_WALL.md day-1 line is explicitly labeled PRE-WALL PROOF RUN (grinder N=0 expected, detector not deployed; v2 N=250 -$2,943.88 matches the calibration doc's legacy-fire count; flat_top oow N=21 -$192.98); wall proper starts Mon 8/17. v2 is a separate lane, NOT in the portfolio number — header says so.
7. **Plist exists + LOADED** — VERIFIED this session: `~/Library/LaunchAgents/com.marcos.tradingbot.shadowgrade.plist` on disk (832B, 8/14 20:01) AND `launchctl list` shows `com.marcos.tradingbot.shadowgrade` (exit status 0). Rig AA-d pins the file + `<integer>23</integer>`.
8. **Boot visibility** — GRINDER_SHADOW rides both the boot banner and the durable boot_config row (#26 doctrine).
9. **Rig** — `python3 rig/test_shipset_20260804.py` run MYSELF: **ALL GREEN, exit 0**, sections A..Z plus AA-a..AA-d. The broader sweep's 11 reds are documented pre-existing at baseline (stash bisect, per the commit message) — not this ship's to fix.

FIX-NOW LIST: none blocking. Owed (non-blocking, tracked): (a) grader depends on the Railway decisions/bars API at 23:00 — a Railway outage that night = a missing brick; the grader takes a date argv so a manual backfill run is the recovery (Quartermaster/Pit Crew note); (b) haltgap-free sim optimistic on halt days — disclosed, Side Marshal/Historian to flag halt days on the wall when they occur; (c) grinder dashboard strip label — Dashboard Curator queue, alongside the owed v2 label.

## DAY-ONE WALKTHROUGH (Monday 8/17, default env)
GRINDER_SHADOW=1, V2_SHADOW=1, V2_CALIBRATED=1. Trace: a runner in the reclaim watch prints a new session high after 10:30 ET -> net-up + above-VWAP + quiet-pullback (<3% dd, 15 min) gates run -> survivor logs a **`grinder_shadow_fire` row** (price, session_hi, vwap, mins_since_1030, would_stop, in_lane, seq) — post-10:30 rows ONLY, a pre-10:30 grinder row = defect, pull the cord. Calibrated v2 rows land in the LOW TENS (250/afternoon legacy -> ~21-survivor anatomy), all calib=C1-C5. At 23:00 launchd runs the grader: OOS_WALL.md gains exactly ONE line — wall day 2, grinder N>0 for the first time, E3 PORTFOLIO = grinder + in-window flat_top. Every row has a named producer; nothing converts, nothing orders.

## DOCTRINE-INVERSION SWEEP
doctrine-inversion sweep: **n/a** — no doctrine touched. Chart-as-gate governs TRADES; this is a shadow row writer + an offline grader (evidence machinery, no trade path). Maps-describe honored: session high, VWAP, and the 15-min low are computed structural anchors, not invented rungs. Edge-over-mechanisms honored in the right direction: this ship IS the expectancy-evidence pipeline. 8/8 law encoded in the wall header itself (">=5 forward days before any live talk; smaller + later, never launch-anyway"). No OLD-premise strands: grinder is net-new, gated by one env switch, default per the F-nomination.

## ROLL CALL (every ROSTER.txt office)
- **Blast Radius Auditor** (chair): finding — diff read line-by-line; zero-conversion re-scanned; WETO reconciled independently; rig executed plain + SHIP_CHECK; the dirty-tree stray (pre-registered stress-G script) committed as bookkeeping f2abaaa, not left to rot.
- **Dashboard Curator**: finding — grinder_shadow_fire rides the generic decision strip; named strip label owed (queue, with the v2 label).
- **Systems Quant**: finding — code computes what its names claim: each constant maps to one KT2/TEST-H clause; sim_e3's bar order matches the stress-F engine order clause-for-clause including bank-consumes-the-bar.
- **Pit Crew Chief**: finding — kill switch env (GRINDER_SHADOW=0); launchd job verified LOADED not just written; failure domain = try/except-walled shadow block + an offline script; deploy still owes flat-book-verified-in-turn at push time.
- **Integrator**: finding — single call site inside the reclaim block's fed-bars loop, zero new fetches, no parallel grinder logic; grader is standalone (imports nothing from the bot).
- **Side Marshal**: finding — grinder has no side term by design (a post-10:30 new session high IS front-side behavior); halt days on the wall are his to flag (haltgap-free sim disclosed).
- **Crown Steward**: finding — watch: the 900s cooldown applies to crowned names too; a violent crowned grind will under-log evidence rows (rows only, no privilege touched) — if the wall's grinder N looks starved on a crown day, cooldown is the first suspect.
- **Feed Engineer**: clean — zero new market-data fetches live; grader pulls the union of both 10s feeds (verified-book standard) offline at 23:00.
- **Webull Broker Desk**: clean — no order path within a mile of this diff; $5 place+cancel docket unchanged.
- **Quartermaster**: finding — grader reads bars from the Railway API, not the local cache, so the 8/14 local-bars gap does NOT block it; missed-night recovery = manual `nightly_shadow_grade.py YYYY-MM-DD` backfill, his runbook.
- **Kev Librarian**: clean — grinder-1030 is our KT2 discovery, not a Kev mechanism; no corpus contradiction (Kev trades strength continuation; this observes it).
- **First Hour**: finding — grinder starts where his window ends (post-10:30); the E3 portfolio's flat_top half is IN-WINDOW 9:30-10:30 — his slice feeds the wall's other lane.
- **Opening Bell**: clean — no pre-open path; detector skips everything before 10:30 by construction.
- **Seam Scientist**: finding — the OOS wall IS his >=5-day doctrine made physical; one-day humility encoded (day-1 line labeled proof-run, wall proper starts 8/17).
- **Strength Ombudsman**: finding — a detector that fires ONLY on new session highs is structurally strength-seeking; nothing here refuses strength; noted approvingly in his ledger.
- **Forward Architect**: finding — his registered-hypothesis template executed end-to-end: KT2a -> TEST-H -> stress-F PASS 5/5 -> nominated -> OOS wall. The template for every future nominee.
- **Momentum Operator**: finding — nothing ships on noise: five-round stress lineage behind the nomination, and this commit ships MEASUREMENT, not behavior.
- **Trade Manager**: finding — the E3 exit model (bank 1/2 +10%, 10%-off-high closes-through trail) is graded in shadow before he's ever asked to run it live; correct order.
- **Tape Veteran**: hypothesis — grinder fires cluster on trend days; a chop week could show a misleadingly quiet wall (small N, not small edge) — read the wall's N alongside its dollars (recorded, no action).
- **Reclaim Architect**: clean — reclaim block untouched except the appended shadow rider, same pattern as v2's.
- **Execution Surgeon**: finding — the -0.5% flat slip + exact-limit bank fill are the sim's two optimistic assumptions on fast tape; both disclosed in the wall header; live-fill reconciliation is his job IF this ever converts.
- **Handicapper**: clean — no selection change; the detector iterates the existing candidates board.
- **Rocket Rider**: finding — grinder is the measured answer to his named open hole (vertical-regime entries, #48 lane); endorse the shadow-first route.
- **Cartographer**: clean — session high/VWAP/15-min low are computed lines, not map rungs.
- **Wind Tunnel Engineer**: finding — fidelity verified: sim_e3 traces to stress-F's method notes term-for-term; no-lookahead boundary (strictly-after-fire bars) and stop-first tie rule both present; rig AA executes the detector's spec boundaries.
- **Statistician**: finding — the wall is append-only, one line/day, with N and skip counts on every line; this convening's numbers ride the bookkeeping commit's RESULTS_LEDGER entry (f2abaaa).
- **Convexity Trader**: finding — E3 was selected on mean AND median AND worst-day, not win-rate; the wall line preserves per-lane dollars so tail shape stays visible day by day.
- **Curl Mechanic**: finding — fire-count acceptance: KT2a saw 64 fires over the backtest window (~2-4/day in-lane); a Monday grinder count in the hundreds = gates not executing, pull the cord.
- **Project Manager**: finding — tags: rig ALL GREEN incl. AA [VERIFIED this session x2]; WETO reconciliation [VERIFIED independently]; plist loaded [VERIFIED via launchctl]; 11 sweep reds [PRE-EXISTING, documented]; wall day 2 [SCHEDULED Mon 8/17 23:00].
- **Historian**: finding — for the record: first time a nominated edge gets a physical, automated, append-only OOS wall before anyone is asked to risk a dollar on it; the official record of E3's forward test starts Monday.
- **Hidden Entry Architect**: clean — v2 lane graded on the same page but firewalled out of the portfolio number; his F-control bar (-$4,012 must-beat) governs his lane's eventual question, untouched tonight.

## VERDICT
Room vote on "aa3ff9f is ship-clean as audited (shadow detector + offline grader, zero money-path change, no deploy)": **31-0 APPROVE**. 0 blocking findings. Owed items (non-blocking, tracked): missed-night backfill runbook note; halt-day flags on the wall; grinder + v2 dashboard strip labels; flat-book verification in-turn at eventual deploy.

— Convening closed 2026-08-14. Blast Radius Auditor, chair.
