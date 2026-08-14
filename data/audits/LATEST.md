# SHIP CONVENING — 2026-08-14 (late) v2 shadow calibration C1-C5 (env-gated V2_CALIBRATED, default ON)
covers: 8c40c8ab423c  (one code commit; audited against `git show 8c40c8a` line-by-line this session; worktree verified clean and identical to the commit)
Chair: Blast Radius Auditor. Separate-context convening under elevated-error-day skepticism: every claim below is from a read or execution run THIS session — nothing carried on trust from the authoring session.

## SHIP DESCRIPTION + AUTHORIZATION
Calibrates the v2 confirmed-pullback SHADOW detector (shipped e59a2eb, audited earlier tonight) per the Hidden Entry Architect's live 250-fire diagnosis (`data/killtests/v2_calibration_20260814.md`): the first live afternoon fired ~10x looser than the backtest cohort. Five gates, all inside the shadow-only detector:
- **C1** anchor proximity: flush low within 2.0% of session VWAP (consolidation-high anchor stays STAMPED-not-gated behind TODO(C1b) until the 4x3min base tracker exists — VWAP-only is the conservative subset, per spec).
- **C2** confirmation must land ≤120s from the push; the legacy expiry-ratchet (`fl["k"] = k` on deepening) is killed — arm life = 180s from FIRST arm.
- **C3** per-name 300s cooldown after any fire (`cool_k` set only on an actual fire).
- **C4** push maturity: push high sourced from a 5-min window (legacy 2-min). Spec asked "2-min high must equal the 5-min high"; implementation is the single 5-min window — VERIFIED EQUIVALENT: arming still requires `k - push_k <= 120s`, so the 5-min max must sit inside the last ~2 min, which is exactly the spec's condition.
- **C5** stop-degeneracy floor: reject fires with (close − flush_low)/close < 0.5% (today's live min was 0.0%).
`V2_CALIBRATED` default **"1"**; `V2_CALIBRATED=0` restores the legacy predicate (ratchet, 2-min window, no gates) for comparison runs — executed in rig Z-e, the exact tape that is CUT calibrated FIRES legacy with `calib="legacy"`.
Authorization: shadow-row-writer behavior only — nothing the bot does with MONEY changes under any env value (auditor-cannot-authorize satisfied by construction; the Architect's spec section 3 is the calibration authority, and the calibration target is bringing the shadow evidence into the backtested cohort's definition before Marcos is ever asked to convert anything).

## FINDINGS (each verified by direct read/execution this session)
1. **Default ON + legacy intact** — VERIFIED. `:5683 V2_CALIBRATED = os.environ.get("V2_CALIBRATED", "1") == "1"`; rig Z-a executes empty-env → True, Z-e executes "0" → False with `V2_PUSH_WIN` 300→120. Legacy ratchet preserved verbatim behind `if not V2_CALIBRATED`.
2. **Gates implemented as specced** — VERIFIED by read of :5723-5741 against the calibration doc's section 3: C1 2%, C2 120s, C3 300s, C4 5-min (equivalence argued above), C5 0.5%. Rig Z-b and Z-c EXECUTE C2 and C3 on synthetic tapes through the real exec'd segment; Z-a executes a pass-through-all-five fire.
3. **Zero conversion path, re-verified from scratch** — detector block (:5691-5752) and caller block (:7231-7250) grepped this session: no `breakouts.append`, no `execute_trade`, no order call of any kind; caller logs `v2_shadow_fire` and STOPS, try/except-walled. Rig Z-d pins both regions.
4. **Row schema unchanged + `calib` added** — VERIFIED at the call site (:7247): all ten prior fields intact (price, flush_low, flush_depth, secs_from_push, vwap, near_vwap, in_window, would_stop, seq, time_hm); one new field `calib` ("C1-C5"/"legacy") — Monday's grader can slice or ignore it; `_v2f.get("calib", "legacy")` tolerates a stale detector dict.
5. **One behavior nuance, on the record** — a confirmation-shaped bar that FAILS a gate now CONSUMES the armed flush (`st["flush"] = None` moved above the gate stack). Intentional per spec L2 ("confirmation = FIRST 10s higher-low + close>prior-high bar"): the first confirmation is the specimen, pass or cut — no second-chance confirmations on the same flush. In legacy mode `_ok` is unconditionally True, so legacy outcomes are unchanged. Non-blocking; noted so Monday's counts aren't misread.
6. **Cooldown edge cases** — `cool_k` read via `st.get` (absent on fresh state = no cooldown, correct); day rollover rebuilds state so the cooldown does not survive overnight (correct — it is churn control, not doctrine). VWAP absent/0 → C1 cuts the fire (conservative, matches spec's VWAP-only subset).
7. **Rig** — `python3 rig/test_shipset_20260804.py` run MYSELF this session: **ALL GREEN, exit 0**, sections A..Y all pass plus all five Z pins (Z-a..Z-e) with EXECUTED synthetic tapes through both the calibrated and legacy exec'd namespaces (not string-matching — `_z_make` exec's the live segment with a controlled environ).

FIX-NOW LIST: none blocking. Owed (non-blocking, tracked): (a) TODO(C1b) consolidation-high anchor — Hidden Entry Architect's queue; (b) exit-grading of the 21-survivor 8/14 cohort blocked on the 8/14 bars10s ferry — Quartermaster; (c) named dashboard strip label for v2_shadow_fire (carried from the e59a2eb convening) — Dashboard Curator.

## DAY-ONE WALKTHROUGH (Monday, default env)
V2_SHADOW=1, V2_CALIBRATED=1. Trace: a runner in the reclaim watch prints a ≥3% flush off its 5-min push high inside 120s → arms with the flush low → within 180s of the ARM (never reset by deepening) a 10s bar prints higher low + close > prior high → gates run in order C2, C1, C5, C3 → survivors log a **`v2_shadow_fire` row stamped `calib="C1-C5"`** → dashboard decision strip shows it. Expected shape vs last session: **far fewer rows** — 8/14 afternoon produced 250 legacy fires of which only 21 survive C1+C2+C3 (~92% cut); Monday's full day should land in the low tens across the watch set, not hundreds. Every row stamped calib=C1-C5 (a `calib="legacy"` row under default env = defect, pull the cord). The 9:30–10:30 `in_window=true` cohort is the graded slice and should match the backtest cohort anatomy: depth ~3-8%, secs_from_push ≤120, all near_vwap=true, would_stop ≥0.5% below price, ≥300s between same-name rows. Trace ends: the row has a named producer; nothing stops it.

## DOCTRINE-INVERSION SWEEP
doctrine-inversion sweep: **n/a** — no doctrine touched. Chart-as-gate governs TRADES; these are gates on a shadow ROW WRITER (evidence curation, not trade selection — nothing here can refuse a trade because nothing here takes trades). Maps-describe honored: the C1 anchor is session VWAP, a computed structural anchor, not an invented rung; the consolidation anchor correctly stays stamped-only until its tracker exists. Verified no OLD-premise code strands: the only legacy encoding (`fl["k"]=k` ratchet, 2-min window) lives behind the explicit `V2_CALIBRATED=0` switch by design, labeled LEGACY in-line.

## ROLL CALL (every ROSTER.txt office)
- **Blast Radius Auditor** (chair): finding — diff read line-by-line, worktree-vs-commit verified clean, rig executed twice (plain + SHIP_CHECK); the flush-consumed-on-cut nuance and C4 equivalence argued on the record.
- **Dashboard Curator**: finding — `calib` field rides the generic decision strip; the owed named strip label now matters more (row counts drop ~92%, a quiet strip must read as calibration working, not the detector dead).
- **Systems Quant**: finding — code computes what its names claim: each Cn constant maps to exactly one gate; C4's name ("push = 5-min high") verified equivalent to spec's 2-min==5-min condition via the 120s arm constraint.
- **Pit Crew Chief**: finding — kill switch env (`V2_CALIBRATED=0`), default matches the Architect's call; failure domain unchanged (same try/except wall); deploy still owes flat-book-verified-in-turn at push time.
- **Integrator**: clean — single call site, no parallel v2 logic, zero new fetches; `calib` threaded detector→row with a `.get` default.
- **Side Marshal**: clean — no side term; rows keep time_hm for joins.
- **Crown Steward**: finding — watch: C3's 300s cooldown applies to crowned names too; on a violent crowned tape it suppresses evidence rows (rows only, no privilege touched) — if Monday's crown shows starved v2 evidence, the cooldown is the first suspect.
- **Feed Engineer**: clean — zero new fetches; same fed 10s bars + session VWAP.
- **Webull Broker Desk**: clean — no order path within a mile of this diff; his $5-test docket unchanged.
- **Quartermaster**: finding — the 8/14 bars10s gap (cache ends 8/13) blocks exit-grading the 21-survivor cohort; ferry 8/14 = his queue item, prerequisite for the Architect's re-grade.
- **Kev Librarian**: clean — calibration tightens TOWARD Kev's flush-into-structure anatomy; no corpus contradiction.
- **First Hour**: finding — his slice sharpens: Monday grades in_window AND calib=C1-C5; live 8/14 had 0 in-window rows (afternoon deploy), so Monday is the FIRST in-window calibrated evidence.
- **Opening Bell**: clean — no pre-open path; day-rollover state reset intact.
- **Seam Scientist**: finding — one-day-humility on the calibration itself: C1-C3 cuts derive from ONE afternoon (250 rows); legacy comparison preserved via the env switch is exactly the right hedge; OOS wall (≥5 days) still governs any conversion talk.
- **Strength Ombudsman**: finding — gates on a shadow row writer refuse no strength by construction; noted for his ledger anyway: C1 (VWAP proximity) is the kind of gate that, if ever promoted to a TRADE gate, gets a refused-strength hearing first.
- **Forward Architect**: clean — calibrate-then-grade is his registered-hypothesis template; nothing new to docket.
- **Momentum Operator**: finding — nothing ships on noise: the cut set was derived from measured live distributions (197/250 fail C1 alone), and the survivor anatomy matches the backtest cohort before any ship of behavior.
- **Trade Manager**: clean — no exit or capture path touched.
- **Tape Veteran**: hypothesis — an afternoon tape is compositionally unlike the open; C1-C3 calibrated on 14:00-15:13 churn may over-cut at 9:30 when real flushes are fast and VWAP is young — Monday's in-window count answers it (recorded, no action).
- **Reclaim Architect**: clean — reclaim block untouched; rider unchanged except the `calib` kwarg.
- **Execution Surgeon**: clean — no execution path; C5's 0.5% floor mirrors his live stop-coherence floor (consistent doctrine, shadow-side).
- **Handicapper**: clean — no selection change; L4 cohort residual stays [UNVERIFIED] per the spec doc, stamped for later.
- **Rocket Rider**: finding — his e59a2eb concern (parabolic arms constantly) is exactly what C3+C4 answer: MF's seq-34 churn day cuts to one-per-5-min; endorse.
- **Cartographer**: clean — VWAP anchor is a computed line, not a map rung; consolidation anchor correctly deferred.
- **Wind Tunnel Engineer**: finding — fidelity check passed: each gate constant traces to the backtest spec (entry_rebuilds Strategy 3) via the calibration doc's predicate diff table; rig Z tapes execute the spec boundaries (130s cut vs 30s pass; 200s cooldown cut vs 400s pass).
- **Statistician**: finding — Monday's grade must count from ROWS (calib=C1-C5, in_window=true), never from the 21-survivor retro-projection; this ledger entry rides the bookkeeping commit.
- **Convexity Trader**: clean — no P&L claim in this ship; exit re-grade owed post-ferry before any dollar figure attaches to the calibrated cohort.
- **Curl Mechanic**: finding — fire-count acceptance band updated: expect low-tens/day calibrated (vs 250/afternoon legacy); a Monday count near legacy levels = gates not executing, pull the cord.
- **Project Manager**: finding — tags: rig ALL GREEN incl. Z [VERIFIED this session ×2]; diff read + worktree clean [VERIFIED]; C4 equivalence [VERIFIED by argument from executed constraints]; 8/14 exit re-grade [BLOCKED on ferry]; Monday calibrated grade [SCHEDULED].
- **Historian**: finding — for the record: the Architect's office diagnosed its own detector's looseness from live evidence and shipped the calibration the same day, legacy behavior preserved under an env switch — the observe-then-gate doctrine executed textbook.
- **Hidden Entry Architect** (owner): finding — his spec sections 2-3 implemented gate-for-gate; C1b consolidation anchor is his named next item; the F-control bar (−$4,012 must-beat) still governs the eventual conversion question, which this commit does not raise.

## VERDICT
Room vote on "8c40c8a is ship-clean as audited (shadow-only calibration, legacy path intact behind V2_CALIBRATED=0)": **31-0 APPROVE**. 0 blocking findings. Owed items (non-blocking, tracked): 8/14 bars ferry + 21-survivor exit re-grade; TODO(C1b) consolidation anchor; v2_shadow_fire strip label; flat-book verification in-turn at deploy; Monday grade counts calibrated in-window rows vs the backtest cohort anatomy.

— Convening closed 2026-08-14. Blast Radius Auditor, chair.
