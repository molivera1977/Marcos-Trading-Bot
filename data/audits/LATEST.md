# CONVENING — 2026-08-19 03:0x EDT — session map, ma_pullback v2, tier rehydrate, VWAP coverage guard

**TREE UNDER AUDIT: `db8eafeb9f3b` (supersedes `1aeb11ed67e5`)** — clean worktree at audit time.
Flat book verified in-turn 03:05:00 EDT: **0 open positions**.
Rig: 38 green. Two gates re-pinned to the new spec (P7, BH-b). **18 gates were already RED on
`5e6422bc02f0` before this batch and are NOT cleared by it** — see Blast Radius Auditor.

## WHAT SHIPS

Lane arbitration was decided by **code nesting depth**. It is now one explicit arbiter:
`LANE_RANK` sort → one-position-per-ticker dedupe → session whitelist, each drop logging a
decision row (`lane_outranked`, `lane_restricted`).

| session | lanes |
|---|---|
| PRE 07:00–09:25 | ignition, ma_pullback |
| RTH 09:30–16:00 | ignition, ema9x90, ma_pullback (ranked first), then kevseq, grinder, dip_rip |
| RESTRICTED (11) | hidden_entry, vwap_reclaim, flat_top, v2conv, zone_flip, bandpass, prevwap, orb, rocket_catcher, crown_seam, halt_ladder |

Restricted lanes **still detect and still log; they cannot convert.**

Also: `MA_PULLBACK_V2` (arm on the 3-min flag, fire on the 1-min close above it; above VWAP;
quiet dip; ≤2% below the session high; 4% stop buffer below the flag low; **runway required**),
`IGNITION_STACK_WARMUP`, `IGNITION_PRE`, `EMA9X90_WARMUP`, `VWAP_COVERAGE_GUARD`,
`_tier_fills_from_ledger`, `ENTRY_OPEN_ET` default 09:30 → 07:00.

## ROLL CALL — STANDING ROOM, every office present

**Blast Radius Auditor** — The blast radius is the arbiter, and it is wide by design: every lane
now passes through one sort. The failure mode I own is a *silent* drop, so every drop logs.
**My finding, and it is the one that matters:** 18 rig gates were already red before this batch.
This ship does not fix them and does not make them worse — proven by stashing the batch and
re-running on the clean tree. Two want daylight tonight: `test_kev_merge` dies on a real
`NameError` at `screener_app.py:2152`, and `test_resting_stop`'s DRY_RUN pin fails while DRY_RUN
governs all of proving week. Neither is caused here; both are now on the record rather than
buried under a green headline. *I cannot authorize behavior — I only close holes in approved
behavior. The restriction list is Marcos's call, not mine.*

**Dashboard Curator** — `lane_restricted` and `lane_outranked` rows will appear on the decision
feed tomorrow in volume. That is intended, not a regression, and the cockpit should read it as
"the lane spoke and was overruled," not as an error.

**Systems Quant** — ma_pullback's hold-out is 19 unseen dates, −$3.69/tr → +$13.66/tr, with every
condition stated by Marcos *before* it was measured. That ordering is the whole reason I sign.

**Pit Crew Chief** — One batch, one restart, flat book. No RTH exposure: 03:0x EDT.

**Integrator** — The three changes touching entry all land at the same arbiter rather than in
three scattered call sites. That is the integration debt this ship pays down.

**Side Marshal** — ma_pullback's "within 2% of the session high" is a front-side condition in all
but name; 95% of qualifiers were already front-side. No new side variable introduced.

**Crown Steward** — Crowned names lose no privilege here: rank orders *which* lane wins, it does
not cap slots. My standing question — does a crown still get its extra bullets — is unchanged.

**Feed Engineer** — `IGNITION_PRE` sits behind a ≥50% coverage floor precisely so a thin premarket
tape cannot manufacture a fire. Vendor surprise twice is our defect; this is the first guard.

**Webull Broker Desk** — **My standing objection, unresolved:** `_place_order` still carries no
extended-hours flag. Premarket lanes are live in DRY_RUN, which is safe. Before real premarket
money, this must be closed. Stated, not waived.

**Quartermaster** — 10s SIP cache is the input to every number above and is still not
auto-maintained. `harvest_day.py` exists; the nightly restore drill does not.

**Kev Librarian** — Runway resolves against the sheet's marked levels. `_marked_runway` fails open
on `None`, so a missing sheet does not block a trade — it declines to speak. Correct, and worth
knowing when reading tomorrow's rows.

**First Hour** — ignition and ma_pullback both live in my window now, and ma_pullback's warm-up
seed means it can speak before 10:45 for the first time.

**Opening Bell** — 9/90 readiness at the bell goes 69% → 93%. The bell is the point.

**Seam Scientist** — The beginning-entry program is untouched; crown_seam is on the restricted
list and continues to detect, which keeps my evidence stream alive.

**Strength Ombudsman** — I press hardest here. A 2%-below-the-high ceiling is a *strength*
condition, not a weakness one — it buys the name that has not broken. But the CDTG counterexample
proves extension alone does not predict the outcome (the separator study found none clearing the
bar). We are not refusing strength; we are refusing depth. I sign on that distinction.

**Forward Architect** — The improvement nobody asked for, and I am naming it rather than shipping
it: hidden_entry is the top *recorded* live earner and is being restricted for its exits. That is
the right call and it is also an admission that our exit engine, not our detectors, is the
constraint. That is tomorrow's real work.

**Momentum Operator** — Nothing here ships on noise. Every condition was measured.

**Trade Manager** — Exits are unchanged. E3 throughout. That is exactly the complaint against
hidden and it is not addressed tonight.

**Tape Veteran** — "Quiet dip, above VWAP, near the high, break confirmation, stop under the flag"
is what a pullback has always been. This is the first build that says so in code.

**Reclaim Architect** — vwap_reclaim is restricted at Marcos's direction and is tomorrow's agenda
item. It keeps detecting. I am not overruled; I am queued.

**Execution Surgeon** — Fire price is the 1-min close that broke the flag, not a level. Stop is
anchored to the flag low with a 4% buffer, which also cleared the live min-stop gate with zero
rejections.

**Handicapper** — Rank is not expectancy. `LANE_RANK` orders three lanes Marcos trusts; it does
not claim they are ranked by measured edge, and it must not be read that way.

**Rocket Rider** — rocket_catcher stays restricted and superseded. No change.

**Cartographer** — Maps describe, they never serve. Runway reads computed anchors from the sheet
only; no rung was invented for this build.

**Wind Tunnel Engineer** — Hold-out is chronological, 44 train / 19 unseen. No date appears in
both halves.

**Statistician** — The separator study returned **no** clearing separator and is reported as such.
A null result was published rather than tuned away. That is the health indicator here.

**Convexity Trader** — Runway ≥0.5R to the next marked level is the convexity condition: no
upside room, no entry. "No runway, no pullback entry" — Marcos.

**Curl Mechanic** — Stale versus absent stays visible; the fed-bar-age canary is untouched.

**Project Manager** — Aug 20 is tomorrow. This ship makes the entry side legible for the first
time. The exit side is not ready and is the critical path.

**Historian** — For the record: 2026-08-19 is the date lane selection stopped being an accident of
indentation. The 26 untyped fills are all 2026-07-13, from before `entry_type` stamping existed —
they are an artifact of the era boundary, not an unnamed lane, and the whitelist drops nothing
that can still fire.

**Hidden Entry Architect** — My lane is restricted and I do not dissent. Marcos: *"a great detector
but it needs real work. It finds the entries but can't hold it."* That reframes the wall as an
**exit** failure — every hidden figure was graded with E3. **The +$864.51 live figure is held as
UNVERIFIED**, at Marcos's word that those numbers are fake; candidate causes are observe-only
shadow rows counted as fills, the ≤7/20 runner-leg window, and the lane's OFF state being
inconsistent with 135 recorded fills. Detection continues, so tomorrow's rebuild starts with a
live fire log and not a memory.

## DOCTRINE-INVERSION SWEEP

Each standing rule inverted, and asked whether the inverse is the better reading.

1. **"Best lanes first."** *Inverse: rank is a bet on the past.* Real risk — rank is Marcos's
   trust ordering, not measured expectancy, and the Handicapper says so above. Accepted because
   the alternative in force until today was nesting depth, which is a bet on nothing.
2. **"Restrict the untrusted lanes."** *Inverse: restriction destroys the evidence needed to fix
   them.* This inversion has real force and it is why the restriction was built at the arbiter and
   not at the detector. Detection and logging continue. Nothing is lost but the risk.
3. **"No runway, no entry."** *Inverse: a runway gate that fails open is theatre.* Half true —
   `_marked_runway` fails open on `None`, so a name with no sheet is not blocked. It is a gate
   against *known* ceilings only. Disclosed, not hidden.
4. **"Premarket lanes are ready."** *Inverse: they are not — ma_pullback premarket is
   UNMEASURED.* Correct, and stated plainly. It ships premarket on Marcos's explicit call
   ("I don't care. We'll learn on the fly") under DRY_RUN.
5. **"38 green means safe."** *Inverse: 18 red gates mean the rig is not a gate at all.* This is
   the sharpest inversion of the night and it is not resolved. Tonight's batch is proven not to
   have caused any of them. That is a weaker claim than "the rig is green," and it is the true one.

## OPEN, NOT CLOSED BY THIS SHIP

- ma_pullback **premarket is unmeasured**; the 30-min arm window is unswept; harness parity unmeasured.
- 18 pre-existing red rig gates, incl. the live `screener_app.py:2152` NameError and the DRY_RUN resting-stop pin.
- No extended-hours flag in `_place_order` — blocks real premarket money, not DRY_RUN.
- hidden_entry exits + vwap_reclaim review — tomorrow, at Marcos's direction.
- 60 historical VWAP-breach rows uncorrected; cause of truncated bar sets unknown.
- `ship.sh` reports success on exit code without checking deployment STATUS.
- Nightly ledger line still prints a merged PRE+RTH figure, against the separation rule.

## ADDENDUM — `1aeb11ed67e5` — BOOT SESSION-MAP BANNER (observability only)

Marcos: *"ship the banner."* Shipped at 03:2x EDT, book flat, DRY_RUN, outside RTH.

The session map shipped in `037baea93cb0` was **never printed at boot** — a grep for a printed
`PRE_LANES`/`RTH_LANES`/`LANE_RANK` returned empty. The bot now prints the map and stamps a
`boot_session_map` decision row. It prints state; it never sets it. Zero behavior change.

**Blast Radius Auditor** — Observability only, and it fails loud but never fatal: a banner that
crashes the boot is worse than no banner. **It was exercised before shipping and that caught a
real bug** — `PRE_LANES`/`RTH_LANES` are SETS (:15998, :16013), not strings; the first draft
called `.split(",")` on them. The `try/except` would have swallowed the `AttributeError`, the bot
would have booted normally, and the feature would have been dead on arrival while appearing
shipped. That is the exact class this office exists to catch.

**Historian** — **CORRECTION TO THE RECORD:** restricted is **13**, not the 11 reported earlier
tonight. `bounce` and `ema_bounce` are in `LANE_EXPECTANCY` and fall outside both whitelists.
Same rule applies — they detect and log, they cannot convert.

**Dashboard Curator / Project Manager / every other office** — no surface changed, nothing gated,
nothing sized. Standing questions unaffected.

### DOCTRINE-INVERSION SWEEP (addendum)

*Inverse: a banner is decoration, and restarting 30 minutes before the 03:55 wake to add one is
gratuitous risk.* Weighed and rejected on the narrow ground that today is the first session the
new session map governs, and without the banner the morning is unauditable — the 07:12 duty-watch
row names fires-vs-fills but cannot name the whitelist behind them. Restart cost is a flat book
outside RTH under DRY_RUN. Had the book been open or the clock inside RTH, the answer would have
been no.

**Verified live env at ship time:** `ENTRY_OPEN_ET=07:00`, `DRY_RUN=true`. `PRE_LANES`,
`RTH_LANES`, `LANE_RANK`, `MA_PULLBACK_V2`, `IGNITION_PRE` are unset on the service and correctly
fall through to the shipped code defaults. First live proof of the map arrives in the 03:55 boot
log; first behavioral proof at the 07:12 duty-watch row.

**Also corrected tonight:** the `screener_app.py:2152` NameError reported earlier is a
test-harness artifact, not a live defect — `screener_app.py:11` imports `datetime` at module
level; the rig lifts the function into a fresh namespace without module globals. Live kev-level
merging is not broken. That leaves 17, not 18, pre-existing red gates worth triage.

## ADDENDUM 2 — RTH HOTFIX BATCH (Marcos: "ship it" / "fix everything you can", ~10:45-11:05 ET)

**Explicit Marcos override of the no-RTH-push law**, priced to him first (flat book, DRY_RUN,
every hour of waiting = dead 9/90 + ghosted exits). First ship attempt HELD at the flat-book
gate — TNON was live (kevseq, the day's winner, +$60.42); shipped only after its exit and the
hand repair of its ghost. Flat book re-verified in-turn at ship time.

**WHAT SHIPS** — the 8/18 batch's three kills (one class: an exception between detection and
action, eaten by a handler) + the reread fix + two gates:
1. `cache` NameError in the exit-record payload — every exit since 8/18 22:56 ghosted
   (VRAX −$17.46, CISS −$55.80, TNON +$60.42, all repaired by hand). Traceback on file.
2. ema9x90 `_log_decision` kwargs collision — six 9/90 fires (09:33–10:16) died as
   gate_fail_open during CDTG's +50% run; the rank-#2 lane could not convert.
3. `urllib` never imported — tape pre-break + retest-band gates fail-open dead since 8/3.
4. Dist-primary rereads (REREAD_DIST_ONLY, default on; measured: 53% of breaches fired on
   maps within 3%) + breach rows stamp trigger=age|dist|both.
5a. IGNITION_RELVOL default -> 0 (Marcos: "i okayed the relvol number not what it was
   measured against"). The approved gate was 2.0x vs the scanner's MULTI-DAY baseline; the
   shipped session-self denominator was a data-availability substitution that changed what
   the gate is, never surfaced for sign-off — unauthorized behavior, disarmed. relvol_sess
   still stamps as data. 35 refusals on its only live day; fires 27 -> 7.
5b. Ignition relvol graded the STILL-FORMING minute (_rvc[-1], the element every sibling
   call site drops): 0.1x stamps on 6.8x surges, 35 refusals on its first live day vs zero
   ever before, fires 27 -> 7. Now grades the last COMPLETED minute — the quantity the 8/18
   study actually measured. Synthetic check: old 0.26x/refuse vs new 6.0x/pass on the same tape.
6. FIRE-TIME RVOL (Marcos-ordered): Webull's real 10-day RVOL from the scanner feed,
   re-checked at the ignition consume at 2.0x — value+age+stop stamped, missing/stale fails
   open, refusal never consumes ammo. Gate 21 pins it (12 checks). The substitute it replaces
   cost +$70..$147 on its only live day (30 refusals E3-replayed, 3 stop arms, all positive).
Gates 19 (reread contract, 9 checks), 20 (undefined-name sweep) and 21 (fire-time RVOL).
Re-pins: resting_stop DRY_RUN pin → the 8/8 auditor-C spec; kev_merge harness given module
globals (its NameError was a harness artifact, NOT a live defect — corrected on the record).

**Blast Radius Auditor** — four code changes, each cause-confirmed from live evidence, each
exercised (gate 19 drives the real _effective_map; the ema9x90 call shape replayed; pyflakes
sweep green with guarded-b4 allowlisted). 16 pre-existing red gates remain, all stale-pin
classes, listed in PUNCHLIST_20260819.md. The runway gate was E3-replayed across 95 archived
refusals before anyone touched it: REFUSE-ALL beats TAKE-ALL by $543.66 — the gate stands,
untouched, vindicated; the wall-strength arm (+$39.58, n=10, join-dirty) stays HYPOTHESIS.

**Statistician** — the TNON 09:35 "miss" was REFUTED by hand-trace (stopped 09:58 at 10.4948
on the resumption flush the 1-min chart hid). Eyeball grading reversed by tape, again.

**All other offices** — standing positions unchanged from the two convenings above; no gate
loosened, no lane added, no sizing touched. Doctrine-inversion: *"a hotfix during RTH is the
exact class the law exists to stop"* — weighed; overridden by the owner with the book flat and
paper-only, after the alternative (a session of known-dead lanes) was priced. n/a otherwise.

## ADDENDUM 3 — "PULLBACK SHOULD BE ITS OWN GATE" (Marcos ruling, ~13:1x ET)

ma_pullback v2: 3 fires since shipping, 0 conversions — AZI (chart gate demanded a fresh break
from a continuation entry), RCON (mapless fail-closed), TNON (0.09R off a 20.6% flag stop).
GRANTS (env MAPB_PATTERN_GATE, default on): chart-gate bypass + external-runway skip. The
lane's INTERNAL gates all stand (VWAP, depth, quiet, flag stop, internal runway >=0.5R — the
measured hold-out spec). No other exemption. Rig gate 22 (5 checks) + shipset AO re-pinned to
the ruling. Doctrine: pattern-is-the-gate, same as kevseq. Measure and number both Marcos's.
Ships at the next flat window / close convene.

## ADDENDUM 4 — HIDDEN v2 LIVE (Marcos, 22:0x ET: "lock the new hidden. build it and ship live for tomorrow.")

**What ships.** The hidden lane rebuilt end-to-end to Marcos's simple spec, replay-locked
in-session on the 948-name-day 10s SIP cache (data/killtests/hidden_v2_simple_20260819.py +
three parameter ladders):
- ARM day-gain 25-60% above session VWAP (RTH 09:30-15:30) · pullback <= 50% of the
  rolling-5-min leg · trigger = HIGH breaks the pullback high within 6 bars · stop = pullback
  low -1% · exits HV2: 25% off at +1R -> stop to entry-or-better, runner exits on 15 min
  without a new high · NO day caps (Marcos) · 300s per-name cool-off.
- Ladder verdicts (train=even dates / OOS=odd): 15-min time stop is the LAST point where
  OOS >= train (20min+ = train pulls ahead = memorization; "none" collapses to +$8.92 OOS);
  25% scale beats 40% at every R; 1.0R = 68% green. All-fills OOS +$10.69/tr n=500.
- GATE REVIEW (Marcos: "did we review gates in its way" / "no surprises"): every house gate
  priced on the lane's own 1,023 replay fills. Backside bites 0. Day-gain floor can't bite
  (arm >= 25%). Chart-map gates auto-cleared (tape class). MIN-STOP 4% deliberately ON:
  refuses the 77% tight-stop fills earning +$6.80/tr, keeps survivors at +$41.60/tr OOS
  (n=113, 73% green, ~4 fires/day) — the gate is a measured quality filter on this lane.
- Declared live-vs-replay translations: day-gain basis = prior-day close (replay: 4am print);
  BE = entry-or-structure floor (BE_FLOOR_AFTER_SCALE); flat = house flatten.

**NEW-LANE CHECKLIST (the kevseq law), item by item:** fire price = the trigger bar's traded
close, never a level (pin A3) · age guard ARMED AT BIRTH (LANE_FIRE_AGE_GUARD default =
"hidden_v2"; batchG pin amended on the record — a lane born with the guard removes no trade it
ever had) · drift + fire_px/fire_k stamped on fire and conversion rows · caps: none by owner
ruling; ONE_PER_TICKER/slot arbiter apply normally · LANE_CLASS "tape" + full gate set
enumerated above · context computed not fail-closed: missing day-gain basis logs
hiddenv2_no_daygain_basis, never dies silently · stop anchored to the entry-adjacent pullback
low. Extension guard: honest running 10s 90-EMA stamped (gate 10 GREEN, BLIND_KNOWN did not grow).

**Rig.** New gate 25 (rig/test_hidden_v2_20260819.py): 27 checks, detector and _hv2_eval
EXECUTED on synthetic tape, all wiring pinned. GREEN. Full sweep 45 pass / 18 fail — the 18
verified IDENTICAL to the HEAD baseline via stash (pre-existing stale-pin/live-endpoint
classes, registry in PUNCHLIST_20260819.md). Gate 17 (liftability) and gate 10 (extension
blindness) both demanded compliance and got it; harness LANES entry added (replayable).

**Exit plumbing.** exit_mode="HV2" rides the E3 chassis (stop-first ties, 10s feed, resume,
legacy-exit guards) with exactly two swaps: tier 25%@+1R and the 15-min no-new-high time stop
(pure fn _hv2_eval, mirrored on _e3_eval, rig-executed). Restart: resume keeps the HV2
contract; the time-stop clock restarts at the first consumed bar post-resume (declared).

**Lanes ledger.** RTH whitelist gains hidden_v2 (v1 hidden_entry STAYS RESTRICTED: detect+log
only; its +$864.51 stands FAKE on the record). Kill switch HIDDENV2=0; time stop
HIDDENV2_TIME_STOP env.

**Blast Radius Auditor** — separate-context adversarial diff review convened pre-ship
(verdict recorded below at ship time). **All other offices** — no sizing touched, no other
lane's gates moved; TAPE_LANES grows by one member, checked against every registry that
derives from it. Doctrine-inversion: shipping a lane the same night it was designed compresses
the usual soak — weighed; owner's explicit order ("ship live for tomorrow"), DRY_RUN sim,
kill switch + age guard + full refusal instrumentation in place. Benchmark the live shadow
must track: ~+$11-12/tr all-fills, ~$41/tr post-min-stop survivors, ~4 fires/day median.

**Port parity (live detector vs the replay's scan, 57 random cached name-days):** 61/74 fires
exact-bar identical, 5 shifted <=2min (same move, neighboring pullback), 2 replay-only-far,
6 live-only-far = 89% economically matched. Cause understood and bounded: the batch scan
evaluates every pullback retroactively; the live port holds ONE pending setup (latest wins),
so a minority of fires land on an adjacent pullback of the same qualifying move. All residuals
pass the full arm (25-60% above VWAP, valid pullback+break). Direction of drift: ~+0.1
fire/name-day MORE than replay.

**Blast Radius Auditor VERDICT (separate context, 21 tool-uses over the full diff):**
DO-NOT-SHIP on one blocker, then SHIP. Blocker #1 CONFIRMED AND FIXED pre-ship: the shared
BE floor (BE_FLOOR_AFTER_SCALE=2, the 7/28 kev25 default) meant HV2's single-tier ladder
NEVER floored the stop — "25% at +1R -> BE" would have shipped as "25% at +1R -> stop stays
at pullback low", an exit the replay never measured. Fix: floor after tier 1 iff _hv2_mode
(:13433 region), every other lane untouched; rig pin C14 added (gate 25 now 28 checks, GREEN
— the auditor also flagged that C6 pinned the tier but not the floor; closed). Finding #2
(env overrides voiding code defaults): Railway env audited via CLI in-turn — RTH_LANES /
LANE_FIRE_AGE_GUARD / BE_FLOOR_AFTER_SCALE / HIDDENV2 / MIN_STOP_EXEMPT / E3_EXITS ALL unset,
code defaults rule. Notes adopted: stale "EVERY LANE OFF" comment amended; hidden_v2 added to
the BREAKOUT_ENTRIES=False defensive whitelist (:11653). Auditor confirmed safe: _e3_mode
composition (plain-E3 byte-identical), tier ladder ordering (rocket/hidden_entry untouched,
HIDDEN_SCALEBAR_STOP exact-matches v1), TAPE_LANES per-lane derivation (no sibling change),
age-guard scoping (only hidden_v2 armed), no key collisions, restart/resume coherent.
Full rig after fixes: 45 pass / 18 fail — identical to HEAD baseline. SHIPPING.

**SHIP STAMP (Addendum 4):** tree f05616631804 — hidden_v2 lane (3b121ed) + expectancy-ledger
entry (f056166). Rig at ship: gate 25 GREEN 28/28; full sweep 45 pass / 18 fail = HEAD-baseline
identical. Flat book verified 22:33 ET this convening: {"open_trades":[]}. Railway env audited:
RTH_LANES/LANE_FIRE_AGE_GUARD/BE_FLOOR_AFTER_SCALE/HIDDENV2/MIN_STOP_EXEMPT/E3_EXITS all unset.

## ADDENDUM 5 — LANE RANK RULING (Marcos, 22:4x ET): hidden_v2 to #2

"in the life of the ticker and the life of the move, hidden should be right after ignition at
#2." LANE_RANK default -> ignition, hidden_v2, ema9x90, ma_pullback (the rank now follows the
move's chronology: ignition starts it, hidden_v2 buys its first pullback). Rig pin C15 (gate
25 -> 29 checks, GREEN). Railway LANE_RANK unset — code default rules. Move % still decides
between names inside a rank; contested-slot behavior only.

**SHIP STAMP (Addendum 5):** tree e48513be7762 — LANE_RANK reorder only, rig gate 25 GREEN 29/29.

## ADDENDUM 6 — STUDY-WINDOW CORRECTION (self-caught ~23:1x ET, via a failed positive control)

DEFECT (mine): the 10s cache stamps bar times in UTC ("...Z"); every windowed replay tonight
compared those strings to ET clock windows. The hidden_v2 study therefore traded 05:30-11:30
ET, not 09:30-15:30 ET. Caught because the pre-audition returned prevwap=0 fires while the
lane demonstrably fired live 8/17 (WETO) — EMPTY RESULT IS NOT A FINDING did its job.
VOID as stated: the +$10.69/tr all-fills OOS, the +$41.60/tr min-stop survivors, the ladder
tables, the pre-audition table, the hidden-in-pre numbers as quoted.
RE-MEASURED, true ET window, locked config: all-fills OOS +$3.97/tr n=654; WITH MIN-STOP ON
(the configuration actually shipped): TRAIN +$9.71/tr / OOS +$9.85/tr n=95, 64% green,
fires 09:30-15:30 as designed. The shipped lane stands on the corrected number. OPEN: dials
(15-min time stop, 25%@1R) were selected on the contaminated window — re-ladder queued
tonight; pre-audition rerun queued with true ET. The live detector is unaffected (epoch+
EASTERN, never string compares). Rig/killtest class-fix queued: every killtest that windows
on cache time strings must convert UTC->ET first.

## ADDENDUM 7 — THE PRE ROSTER, MEASURED (Marcos rulings ~23:2x ET)

Q: "lets answer the question, what deserves to run in pre? Pre has always sucked." Ruling:
"i want whatever lanes scoring well to join pre" — competition among the 4 incumbent lanes.
EVIDENCE (true-ET pre audition, bot's own detectors via live_harness, 769 pre name-days,
07:00-09:20 fires, E3 exits + 09:25 flatten; first UTC-shifted run VOID per Addendum 6):
  ignition   +9.48 train / +7.87 OOS  n=1536  CLEAN — keeps its seat
  v2conv     +7.25 / +7.76            n=219   CLEAN — keeps its seat (quiet gate not modeled)
  reclaim    +6.38 / +4.94            n=195   CONSISTENT — JOINS pre (the one new seat)
  prevwap    +0.34 / +11.07           n=41    ONE-SIDED — kept as incumbent, ON NOTICE; first
                                              subject of the daily reject/shadow grading
  ma_pullback: NOT auditioned (needs a 3-min/1-min driver — built next); keeps its seat by
  the earlier ruling, not by evidence. hidden_v2: measured refusal for pre stands.
CHANGES: PRE_LANES default += vwap_reclaim; VWAPRECLAIM_CONVERT default -> 1 (the 8/14
observe-only suspension lifted BY OWNER RULING — an auditor cannot; the RTH whitelist still
excludes vwap_reclaim so conversion is PRE-ONLY, RTH fires keep dying at lane_restricted,
logged). Rig gate 26 (5 pins) GREEN; gate 25 unaffected.
STANDING DUTY (Marcos): "the rejects and the shadows in both pre and RTH should be informing
us every day. There is no point in doing shadows and rejects unless we are learning from
them." — daily graded reject+shadow review joins the watch, starting 8/20; prevwap is case #1.
BOOK VOID NOTE: the closed-trades PRE table quoted earlier tonight (vwap_reclaim -$648 etc.)
was retracted in-session — those records are the voided ledger classes; no roster decision
rests on them.

**SHIP STAMP (Addendum 7):** tree ba33824f8104 — pre-roster changes + gate 26 + true-ET audition artifacts.

**SHIP STAMP (Addendum 7, final):** tree cd8557774972 — includes the X-b pin amendment (owner ruling).

## ADDENDUM 8 — PRE RANK + PREVWAP BENCH + MA_PULLBACK DRIVER (Marcos rulings ~23:3x ET)

Rulings executed: (1) "do the driver for pullback" — built (data/killtests/
mapb_pre_audition_20260819.py, mirrors the live :11543 call shape minute-by-minute; declared:
runway patched open — no historical maps, the gate only removes fires; warmup seed None).
RESULT, 708 pre name-days: TRAIN +$9.12/tr n=48 / OOS +$9.83/tr n=26, 81% green — halves
agree; OOS n under the pre-registered 30 -> KEEPS SEAT (scores well, underpowered), ranked
last until live n accrues. (2) "bench prevwap and have it shadow. make it earn its way after
we retool" — Railway PREVWAP_CONVERT=0 set + verified in-turn; shadow rows continue; the
daily reject/shadow grading is its road back. (3) "make sure the roster is lined up in order
from best to worst" (pre) — NEW PRE_LANE_RANK consulted only inside the premarket window
(_lane_rank), default ignition,v2conv,vwap_reclaim,ma_pullback (audition order; unaudited/
underpowered last). RTH LANE_RANK untouched. Rig gate 26 extended to 9 pins, GREEN.

**SHIP STAMP (Addendum 8):** tree 93afc024e289.

## ADDENDUM 9 — RECLAIM BENCHED TOO ("no surprises" sweep, ~23:4x ET)

Marcos: "all pre lanes are perfectly eligible and ready to trade in pre tomorrow? No
surprises?" The sweep found one: 80/116 LIVE reclaim fires (8/18+8/19 archive) carry stops
tighter than the 4% min-stop — the audition never modeled house gates. Cohort replay
(reclaim pre fires, E3 + 09:25 flatten): the >=4% slice live WOULD fill = TRAIN +$14.66/tr
-> OOS -$0.64/tr (sign-unstable); the <4% slice min-stop refuses = TRAIN +$1.60 -> OOS +$8.99
(also unstable). The +$4.94/tr that won the seat is uncollectable through the live gate
stack. Per the standing ruling ("i want whatever lanes scoring well"), reclaim is BENCHED to
shadow: VWAPRECLAIM_CONVERT=0 set in Railway + verified in-turn (code default stays 1 — the
env pins the bench; one word reverses it). Same road back as prevwap: the daily reject/shadow
grading. FINAL 8/20 PRE ROSTER: ignition, v2conv, ma_pullback CONVERT (all three have live
fills through the real gate stack today); prevwap + vwap_reclaim SHADOW. ma_pullback stop is
4% under the flag low by construction (boot: stopbuf=4%) — min-stop cannot surprise it.

## ADDENDUM 10 — HIDDEN IS ITS OWN GATE (Marcos rulings ~23:5x ET)

"if hidden has no need for a map or runway, then why gate it to them in any way shape or
form" + "hidden by design is its own gate." Verified before ruling: hidden_v2_step consumes
only (bars, vwap, prior-day close) — the word "level" appears once in its body, in the
docstring saying the fire price is NEVER a level; the replay evidence (+$9.85/tr OOS n=95)
contained zero map information. GRANT (owner's, same class as MAPB_PATTERN_GATE): hidden_v2
exempt from the two blanket map gates — mapless-block (:15395 region) and external runway
(:15301) — via HV2_PATTERN_GATE=1 (kill switch restores the 8/6 blanket). MIN-STOP STAYS ON
(measured to pay for this lane: OOS +$9.85/tr gated vs +$3.97 ungated, Addendum 6). Rig gate
25 -> 32 checks (C16-C18) GREEN. Doctrine note: the 8/6 mapless law stands for every other
tape lane; this is a lane-scoped owner exception mirroring "pullback should be its own gate."

**SHIP STAMP (Addendum 10):** tree 756890451fa1.

## ADDENDUM 11 — RUNWAY VELOCITY OVERRIDE LIVE (Marcos, ~00:2x ET 8/20)

Ruling: "it's all fake money.... wire the override at 1% with a kill switch" + "we will log
all data and revisit nightly in our lane reviews." A runway-refused fire is LET GO when its
fire minute (last completed 60s of the 10s feed, close-over-close — the ladder's exact
definition) >= +1.0%. EVIDENCE: LGHL 8/19 15:21 specimen (0.18R to a stale rung, tape ran
+31%, +$47.35 given up); ladder on all 56 cached archived refusals 8/11-8/18 — let-go >=+1%
+$7.55/tr 59% green (train +3.08/oos +21.60), complement -$9.55/tr 26%, negative-minute
cohort -$15.76/tr 14% green (vel5 physics at 1-min scale). Threshold +1% PRE-REGISTERED
before the fine ladder; plateau 0.75-1.5% confirmed. HONESTY: n=56, one cohort, multiple
looks — owner shipped early with eyes open (DRY_RUN sim); nightly lane reviews grade the
accumulating cohort (BOTH runway_override and runway_reject rows stamp vel60; verdict
checkpoint n>=150 both parity halves). Safety: override needs POSITIVE evidence (short/
missing feed refuses as before), never widens a runway PASS, kill RUNWAY_VEL_OVERRIDE=0,
threshold env RUNWAY_VEL_OVERRIDE_PCT. Gauntlet note: the 6-session refusal replay IS the
available gauntlet (stamped refusal rows begin 8/11; the historic worst-session days predate
them). Rig gate 27 (7 pins, R6 rewritten window-scan per the gate-23 lesson) GREEN; gates
25/26 re-run GREEN; pyflakes clean. Blast radius: the edit touches ONLY the sub-threshold
reject path inside the runway block; a runway PASS and every other gate are byte-identical.

**SHIP STAMP (Addendum 11):** tree c6205d4fc9b4.

## ADDENDUM 12 — DASHBOARD COPY BUTTON (Marcos ~00:4x: "do the copy button" / "should work on my phone too")
Webull Desktop 9.14.0 has NO url scheme (Info.plist verified) -> per-ticker ⧉ copies the
symbol (navigator.clipboard on https incl. iOS/Android; execCommand fallback; 1.2s green
check; 16px tap target <=700px). CAUGHT PRE-SHIP: the HTML template is a NON-raw Python
string — the first version's JS backslash-quotes were eaten by Python, rendering adjacent
string literals (SyntaxError = blank table); rewritten quote-free via data-sym and verified
by RENDERING the HTML and inspecting output. Dashboard service only — zero trading-path
surface. Tree a598f3134b13.
