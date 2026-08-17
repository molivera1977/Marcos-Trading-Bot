# SHIP CONVENING — 2026-08-16 (Sunday, 23:33 ET) KEV SEQUENCE lane "kevseq" (shadow ON, KEVSEQ_CONVERT env-OFF) + rig AG · nightly Kev lessons report + tile · nightly open-holes sweep + tile · proving drills · killtest/audit data commits
covers: 5e7799366f1a "build: kevseq lane" (marcos_trading_bot.py +250, data/killtests/nightly_shadow_grade.py +13/-5, rig/test_shipset_20260804.py +109) · ae965ad "nightly Kev lessons report + tile" (data/kev/kev_lessons.py, kev_sweep_server.py +11, screener_app.py +31) · b4f8ccd (lessons bootstrap data) · ec9eadd "nightly open-holes sweep + registry" (data/holes/*, screener_app.py +31) · 6f79263 "proving drills" (scripts + DRILLS_20260816.md) · plus data-only commits since 4daeb86 (last audited): aecb899 dbc76d7 6f89f09 0d062dd f0130da ecc167a 14caba0 9d7a9ab e1e42e0 8484ceb eb0d53e 49922fd 06d40d2 d910882 5470232 6bca362 (ledger/killtests only) · 3b3e432 (chore: untrack stray Word lock file, no code). Prior audited code: 7ead311 (bookkeeping 4daeb86); prior convening archived to SESSION_20260816_bandpass.md.
Chair: Blast Radius Auditor. Separate-context convening: every claim below is from a `git show`/file read or an execution run THIS session. Clock: `date` run this turn = Sun Aug 16 23:33:35 EDT 2026. No push, no deploy from this convening.

## SHIP DESCRIPTION + AUTHORIZATION
- kevseq envs (:5998-6001): `KEVSEQ_SHADOW` default "1", `KEVSEQ_CONVERT` default "0", `KEVSEQ_LEG_MAX` 3, `KEVSEQ_N_BARS` 18; constants HOLD_N 3, BURST_PCT 75 (look 30, min 10 bars), MAX_TOUCH 1, MAX_PULL 2, LEG_PB 3%, GAIN_MIN 20%, ROOM 3%/300s, TOUCH_BAND 0.5% (:6002-6012). State map `_ks_st` (:6013). Detector `kevseq_step(sym, new_bars, vwap, ctx)` (:6016-6142). Caller inside the reclaim block of `wait_for_flat_top_entry` (:7767-7828), after the bandpass RTH block and BEFORE the PREVWAP block. Grader: `kevseq_shadow_fire`/`triggered_kevseq` added to the archive query (rig AG-xi). Boot banner + `boot_config` row (:11418, :11453-11454). Rig section AG (a, i-xii).
- Kev lessons: `data/kev/kev_lessons.py` (report writer, `run_safe()` never raises), hooked at the END of the kev sweep in kev_sweep_server.py (:626-637) AFTER `post_sheet` (:602-616), wrapped in try/except; `/api/kev_lessons` GET + tile in screener_app.py (read-only, file-backed, returns `{"top":[]...}` on any error).
- Holes: `data/holes/holes_sweep.py` (nightly 23:30 launchd `com.marcos.tradingbot.holessweep`, loaded — `launchctl list` shows it), runs registry killtest scripts via subprocess (timeout 3600) and writes HOLES.md/holes_latest.json/SWEEP_LOG.md; `/api/holes` GET + tile (read-only). Runs on the Mac, never on Railway, never touches the bot.
- Drills: `rig/test_stop_coherence_drill.py`, `data/killtests/kill_under_fire_drill.py` (has a `post` helper, argparse `--dry`, only runs when invoked by hand), `runway_wall_live_check.py`, `kev_reads_0715_check.py` — scripts only; nothing imports them; nothing executes at deploy.
Authorization class: shadow rows default-on = observe-only (always safe). The kevseq conversion path is a behavior change WITH MONEY and ships DEFAULT OFF; flipping `KEVSEQ_CONVERT=1` is Marcos's call and NOT covered by this vote.

## FINDINGS (each verified by direct read/execution this session)
1. **KEVSEQ_CONVERT default "0"; zero reachable appends with it off.** `os.environ.get("KEVSEQ_CONVERT", "0") == "1"` (:5999). grep `"kevseq"` = 4 hits, the ONLY `breakouts.append(... "kevseq" ...)` is :7820, under `if KEVSEQ_CONVERT and _ksf["would_stop"] < _ksf["px"]:` (:7814), under `else:` (ok fire) under `if KEVSEQ_SHADOW:`. Rig AG-vii (guard precedes append), AG-viii (detector segment has no append/execute_trade), AG-ix (executed guard, `_bo == []`). Rig run by me: ALL GREEN, exit 0.
2. **Detector vs Rosetta spec (read :6016-6142; rig AG-i..vi executed on synthetic tapes):** (B) new session-high bar sets `b_level` = prior session high, or the whole-dollar closed through if higher (:6098-6104), arms; (H) `hold_n` counts consecutive bars with `l >= lvl` (reset on any breach), setup at 3, hi = running high, stop = level (:6113-6118); (W) bar low within 0.5% of the higher of VWAP/9EMA(10s) reached, close above both, stop = wick low, confluence STAMPED not required (:6120-6127); FIRST H/W after B only (`armed=False` on setup :6129); window = 18 bars (:6109); fresh: `touch_n` = prior touches of the stop within 0.5% BEFORE this B (:6132-6134), > 1 -> skip; `pull_n` > 2 in the leg -> skip; fire = later bar `h > pd["hi"]` (:6048), setup dies if `l < stop` first (:6046); burst = fill-bar vol >= p75 of prior 30 (min 10 bars, else `burst_unmeasured` refuse) (:6035-6040, :6051-6055); front side from CALLER on the 1-MIN aggregate (`calculate_ema9/20` on `bars[:-1]` :7780-7783; None -> `front_side_unknown` refuse); day-gain >= 20% vs prior close OR top-3 of the scanner `_move_pct` map (:7784-7793, :6064); room: session high within 3% overhead AND >= 300s stale AND not blue-sky -> `no_room` (:6066-6071); per-ticker-per-LEG cap `leg_n >= 3` -> `leg_cap`, leg increments on a new session high after a >= 3% pullback and resets leg_n/pull_n/leg_lows (:6091-6094). AG-v proves cap binds inside a leg and resets on leg 2.
3. **kevseq_reject rows carry `why`** (:7812: `why=",".join(_ksf["why"])`) with the full row (seq_str, burst_ratio, front_side, day_gain, top3, blue_sky, would_stop, leg/leg_n) — the refused-strength evidence row. Rejects do NOT consume leg_n (`leg_n += 1` only when ok :6083-6085) — correct: a refused fire is not a bullet spent.
4. **Placement / PRE invariant (AF-i).** The kevseq caller sits between the bandpass RTH block and the `if PREVWAP_SHADOW:` block (:7830); rig AF-i re-executed against the current tree still finds zero append/execute/triggered in the PRE segment — GREEN. Note: the reclaim block itself runs whenever `_vr_sv > 0` (PRE and RTH), so kevseq_shadow_fire/kevseq_reject rows CAN appear 07:00-09:25 (rows only; day_gain/top3 context is the same). With CONVERT=0 that is evidence, not exposure. If CONVERT is ever flipped, a PRE kevseq fire would append like an RTH one — the existing PRE session gates downstream apply; flag for the Marcos-priced list, not a Monday concern.
5. **Not in any exempt set.** `MIN_STOP_EXEMPT` (:7307), `BACKSIDE_EXEMPT={"dip_rip"}` (:7027), `VRIDE_EXEMPT` (:492), `_STALE_EXEMPT` (:3274) — none contain "kevseq" (rig AG-x). Converted fires walk the standard gate stack; stop delivered as `zone_stop` = would_stop like grinder/bandpass.
6. **Hot path: zero new fetches.** `kevseq_step(t, _nb, _vr_sv, ctx)` rides the one `_nb`/`_vr_sv` built per name; ctx uses in-memory `bars`, `_pdc_map`, `cache[t]["daily"]`, `_move_pct` — dict/EMA work only. Whole block in try/except (:7777, :7827). Kill switch `KEVSEQ_SHADOW=0`.
7. **Lessons: read-only + fail-soft.** kev_sweep_server hook (:626-637) is after the sheet post and inside its own try; `run_safe()` catches everything and returns 1. `/api/kev_lessons` only reads a JSON file. No bot code touched.
8. **Holes: local nightly, read-only vs the bot.** All registry scripts that touch the network in HOLES.md were grepped: only `ride_seams_week10s_20260807.py` and it is GET-only (`urlopen`). Sweep is subprocess'd from the Mac (plist :7 argv), timeout 3600, writes only under data/holes/. First real (non --dry) run = tonight 23:30 (two 13:12 DRY log lines exist). launchctl last-exit "2" is from the earlier dry/manual invocations, not blocking.
9. **Drills: scripts only.** Not imported by marcos_trading_bot.py/screener_app.py (grep of the four filenames = zero hits outside their own files and DRILLS_20260816.md). `kill_under_fire_drill.py` can POST but only under `__main__` with explicit args — nothing runs at deploy.
10. **Grader** (`nightly_shadow_grade.py`): AG-xi — kevseq statuses in the query, E3 only, reads `stop`; existing lanes unchanged; not executed live (shape-only, [UNVERIFIED] until Monday's 23:00 line).
11. **Rig executed MYSELF**: `python3 rig/test_shipset_20260804.py` -> ALL GREEN, exit 0, A..AG all green (AG-a..xii). SHIP_CHECK=1 result at the foot.

## SPEC TENSIONS (builder-flagged; Marcos-priced items, NOT blockers)
- T1: **W relaxed from strict confluence** — the Rosetta spec described a VWAP/9EMA confluence wick; shipped W = the higher of the two lines within 0.5%, confluence only STAMPED (`confluence` bool on the row). Rationale in the header (:5980-5982): VWAP sits far below a fresh session high, strict confluence ~never exists. Priced by rows: the nightly grade can split confluence true/false from day one.
- T2: **leg cap (3 fires/leg) vs max-2-pullbacks** — Kev's "third pullback = skip" (`KEVSEQ_MAX_PULL=2`) already limits pullback entries to 2 per leg, so a 3rd fire in a leg can only come from a fresh B whose FIRST H/W is a new pullback count... in practice pull_n binds before leg_n (AG-iv shows pull_n 3 -> no setup). `KEVSEQ_LEG_MAX` is Marcos's stated per-ticker-per-leg ration; both are env/const, priced from rows.
- (chair's add) T3: PRE-hours kevseq rows exist (finding 4) — decide, before any CONVERT flip, whether kevseq converts in PRE.

FIX-NOW LIST: none.

## DAY-ONE WALKTHROUGH (Monday 8/17, default env, DRY_RUN=true)
- **Boot**: banner `KEVSEQ_SHADOW=1 KEVSEQ_CONVERT=0(leg cap 3)`; `boot_config` row carries kevseq_shadow/kevseq_convert/kevseq_leg_max.
- **07:00-16:00**: `kevseq_shadow_fire` rows on movers with `seq_str` ("B H"/"B W"), `leg`, `leg_n`, `burst_ratio`, `fresh_touch_n`, `would_stop`, `front_side`, `day_gain`, `top3`, `blue_sky`, `confluence`, `eyes`, `convert_on:false`; `kevseq_reject` rows with `why` in {no_burst, burst_unmeasured, leg_cap, front_side_off, front_side_unknown, day_gain, no_room, degenerate_stop}. Expect early-session `burst_unmeasured` rejects (needs 10 prior 10s bars).
- **Zero `triggered_kevseq` rows** all day while CONVERT=0 — one such row = guard regressed, pull the cord.
- **Dashboard**: Kev Lessons tile populated (bootstrap b4f8ccd, 58 sources) and Holes tile populated (holes_latest.json from tonight's 23:30 sweep; if the tile says "no sweep yet" on the Railway copy, the volume/data path is the question, not the code).
- **Tonight 23:30**: first non-dry SWEEP_LOG.md line (`picked=[...] ran=[...]`) + `data/holes/runs/*.txt`; check `holessweep_launchd.log` Monday morning.
- **23:00 nightly**: wall line gains a kevseq column (N=0 valid).

## DOCTRINE-INVERSION SWEEP
doctrine-inversion sweep: n/a for the shipped default — kevseq inverts nothing; it is shadow rows (observe-only) with the conversion path env-OFF, non-exempt, and inside the normal gate stack if ever converted. Lessons/holes/drills change no bot behavior. No gate/exempt/sizing rule touched.

## ROLL CALL (every ROSTER.txt office, 31)
- **Blast Radius Auditor** (chair): finding — single-sited env-guarded append (F1); detector executed vs spec (F2); PRE-hours rows nuance (F4/T3); rig ALL GREEN incl. AG run here.
- **Dashboard Curator**: finding — two new tiles (Kev Lessons, Holes) both file-backed read-only, panel-isolated try/catch, error text rendered not thrown; kevseq has no tile yet (shadow-lanes board queue stands).
- **Systems Quant**: finding — `kevseq_step` computes what its name claims: B (session-high break) -> first H/W -> break of setup high; burst = fill bar vs p75; leg boundary = 3% pullback then new high. `bars_since_b` and `seq` stamped for replay parity.
- **Pit Crew Chief**: finding — kill switches KEVSEQ_SHADOW=0 / CONVERT already off; block wrapped in try; state process-memory (restart forgets legs — day key resets); no deploy here; flat-book-in-turn owed at deploy; holes sweep is Mac-local launchd, not a Railway process.
- **Integrator**: finding — one call site (:7796); ctx built from existing in-memory structures; consumers of new statuses = grader only; lessons hook = one call site at sweep end; both endpoints file-only.
- **Side Marshal**: finding — front side is computed on the 1-MIN aggregate here (not the fast chart) per the replay caveat; stamped on every row (True/False/None) — joinable to his side ledger.
- **Crown Steward**: clean — no crown privilege interaction; crowned names produce rows like any other.
- **Feed Engineer**: finding — zero new bar/quote fetches from kevseq; holes sweep scripts hit Alpaca/local data on the Mac at 23:30 only.
- **Webull Broker Desk**: clean — no order semantics touched.
- **Quartermaster**: finding — new persistent artifacts under data/holes/ and data/kev/LESSONS_*.md; both in-repo, ride the existing backup plists.
- **Kev Librarian**: finding — the lessons report is his instrument (58 sources bootstrapped); Rosetta corpus (6bca362) is the kevseq source; catalyst still null on prevwap.
- **First Hour**: finding — kevseq rows carry time_hm; attribution by minute available Monday.
- **Opening Bell**: finding — kevseq rows will appear premarket too (F4); rows only.
- **Seam Scientist**: finding — kevseq is a beginning-entry lane on the fast chart; registered as OOS wall (header: "this lane IS the OOS wall"); one-day humility applies.
- **Strength Ombudsman**: finding — kevseq_reject rows with `why` are the refused-strength evidence he asked for; rejects don't burn leg bullets (F3).
- **Forward Architect**: finding — H2 open holes sweep is his engine now (registry counts RUNNING 8 / OPEN 10 / BLOCKED 5 / REFUTED 4 at the dry run).
- **Momentum Operator**: clean — nothing ships on noise; conversion off.
- **Trade Manager**: finding — on convert: E3, stop = level (H) or wick low (W); unchanged exit machinery.
- **Tape Veteran**: hypothesis — H stop = the broken level exactly (no buffer); a wick to the level by one tick kills the setup (`l < stop`) — replay used the same; recorded, rows will show.
- **Reclaim Architect**: clean — separate state from kev_reclaim_step; same fed bars.
- **Execution Surgeon**: clean — no order path change while CONVERT=0.
- **Handicapper**: finding — day-gain >= 20% or top-3 is a selection floor inside the detector; blue-sky exempts the room test.
- **Rocket Rider**: finding — leg definition (3% pullback -> new high) is his regime vocabulary; leg index stamped.
- **Cartographer**: clean — stops are structural (level/wick), no rungs.
- **Wind Tunnel Engineer**: finding — grader statuses added, E3 only; live shape unexecuted [UNVERIFIED].
- **Statistician**: finding — 16 data-only commits since 4daeb86 ride this cover; ledger entries (f0130da, d910882, 49922fd, dbc76d7, aecb899) append-only.
- **Convexity Trader**: clean — grading by $ mean via E3, unchanged.
- **Curl Mechanic**: finding — fire-count acceptance for kevseq starts Monday from rows; expect burst_unmeasured early rejects.
- **Project Manager**: finding — tags: rig ALL GREEN incl. AG [VERIFIED]; lessons/holes wiring [VERIFIED by read + launchctl]; grader live [UNVERIFIED]; CONVERT flip = Marcos's call, not taken; T1/T2/T3 = Marcos-priced.
- **Historian**: finding — for the record: first lane whose caller runs in PRE and RTH from one site with the same detector; kevseq = first per-leg-capped lane.
- **Hidden Entry Architect**: finding — kevseq is a sibling of v2 (anticipation on the fast chart); v2 shadow untouched; both share `_nb`/`_vr_sv`.

## VERDICT
Room vote on "5e77993 (+ ae965ad/b4f8ccd/ec9eadd/6f79263 + data commits) is ship-clean as audited (kevseq shadow default-on = observe-only; KEVSEQ_CONVERT default OFF with the single append env-guarded, per-leg capped, non-exempt; detector matches the Rosetta spec as shipped with T1/T2 recorded; kevseq_reject carries why; lessons/holes read-only + fail-soft + launchd loaded; drills inert at deploy; rig ALL GREEN incl. AG; no push/deploy from this convening)": **31-0 APPROVE, 0 blocking**. Flat-book-verified-in-turn owed at the moment of deploy. Turning KEVSEQ_CONVERT on is not covered by this vote.

SHIP_CHECK result (run after the bookkeeping commit): see the chair's return message.

— Convening closed 2026-08-16 (clock cited above). Blast Radius Auditor, chair.
