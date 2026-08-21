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

## ADDENDUM 13 — THE 8/20 PREMARKET BATCH (Marcos's rulings; Fable review + rebuild, evening)

**Rulings executed (Marcos, in his words):** "I dont want a cap on pre if it can make money.
I am never for a cap" · "all three pre decisions finalized" · "yes, keep v2conv in pre and
record the ruling" · "go with what the data says."

**SHIPS: the three premarket rulings.**
1. PRE cap REMOVED (default 0 = unlimited; all three enforcement sites honour 0; the stale
   Railway PRE_MAX_TRADES=10 override — which would have silently voided the ruling — found
   by CLI audit and cleared). cap_raise_slot bounded to its defined 6-7 marginal cohort.
2. PRE_MIN_DVOL measure FIXED (true session-cumulative by bucket key, deep-seeded, kill
   PM_DVOL_CUMULATIVE=0) and threshold 250k -> 50k. Evidence: the 15-min-window defect
   (8 of 8/20's 15 refusals cleared $250k on the intended measure) + the session-cumulative
   ladder ($0 +$6,071 / $50k +$5,954 / $250k +$4,894 / $1M +$3,725).
3. Premarket MIN-STOP floor 4% -> 1% (PRE_MIN_STOP_PCT; PRE-ness from the _pre_convert
   conversion stamp per the :15208 doctrine, NEVER the wall clock; reject rows stamp
   floor= and pre= so the band cohorts stay gradeable). RTH floor UNTOUCHED.
   DISCLOSED (Fable, net-new): the 762-fill ladder cohort is v2+hidden_v2-spec detector
   PROXIES; the governed population is ignition/ma_pullback/v2conv. Direction corroborated
   on the real population (the 8/20 refusal walk, ignition fires included).

**DOES NOT SHIP: the v2conv RTH seat — SUSPENDED by Fable review.** The seat's evidence ran
at a 1% stop floor; RTH runs 4%. Re-measured AT 4%: no-floor n=572 +$7,078 (train +$10.74/tr,
OOS +$14.22/tr, clean) vs 4%-floor n=153 +$2,003 (train +$2.64 vs OOS +$25.48 — one half
carries everything), 419 fills/+$5,075 (72% of value) refused. Seating it under conditions its
evidence never saw is the day's own "approved number, unexamined measure" disease. The window
+ time-block-roster MECHANISMS ship INERT (defaults ""), fully built, EXECUTED in rig gate 28
(A6a-A7c), ready to arm the day the RTH floor is settled. Blast Radius #4 (unmeasured
kevseq/grinder/dip_rip demotion) is thereby moot tonight; the arming recipe in the code
places the trio ABOVE v2conv deliberately.

**Blast Radius Auditor:** DO-NOT-SHIP verdict on the staged tree, 4 blockers + 5 fixes — ALL
adopted: #1 seeded-set cleared on rollover (the fix would have silently died on day 2);
#2 failed seeds retryable; #3 all six knobs in the boot banner + boot_config row, Railway
audited; #4/#5 resolved by the suspension; #6 conversion-stamp PRE-ness (auditor's TGHL flip
specimen); #7 truthful floor on reject print+row; #8 cap_raise bound; #9 gate 28 rewritten
with EXECUTED pins (the string-match version was green while a swallowed NameError kept the
branch from ever running); #10 clock-failure counter; #14 heartbeat cap=None; #18 stale
comments. #20: test_minstop_gate RED at baseline — root-caused (two pins on the pre-#6 caller
string + a 700-char window the 8/17 provenance comment outgrew; the gate-23 lesson, third
appearance) and GREEN before this min-stop change ships.

**Fable verdict on the day's reasoning:** the three reversals (premarket min-stop, RTH
min-stop caveat, hidden_v2's gate justification) share ONE root cause — verdict rules
pre-registered the SPLIT (train/OOS) but never the METRIC. New standing law, memorialized:
expectancy verdicts are rendered in TOTAL DOLLARS under the live capital model; $/trade is
diagnostic only. RTH min-stop is a LIVE OPEN QUESTION on Marcos's own observation ("we are
never really maxed out during RTH" — verified: peak 3 concurrent positions, ~$1,500 of
$3,000, median 14 trades/day): the RTH ladder reads 0% +$44,866 / 1% +$42,310 / 4% +$31,816
with capital never binding live. Not changed tonight; it is the headline of the next session
with the v2conv seat waiting on it.

Rig at ship: 49 pass / 17 fail — ONE BETTER than baseline (minstop gate reclaimed); gate 28
green with executed pins. Flat book + clean tree verified by ship.sh in-run.

**SHIP STAMP (Addendum 13):** tree 123bbed4c9c0.

**SHIP STAMP (Addendum 13, final):** tree 90e23c5218c9 — includes the shipset crown/cap pin
amendments (the SHIP_CHECK-only sections caught three pins on the pre-ruling literals plus a
comment tripping the BH-b one-way-dependency grep; all amended dated, crown semantics
verified unchanged, the unlimited case now EXERCISED in the executed model).

## ADDENDUM 14 — RTH FLOOR 1% + THE OPENING-HOUR COMPETITION (Marcos rulings, ~20:0x ET)

Rulings: "drop it to 1% if the data supports it. Which then means v2conv moves in to the
first RTH hour. Did we run a roster competition to let the data decide who should go and in
what order."

1. RTH MIN-STOP 4% -> 1%. The ladder (capital-aware $3,000, no cap, all replayable lanes,
   09:30-15:30): 0% +$44,866 / 1% +$42,310 / 2% +$40,424 / 4% +$31,816 / 6% +$18,581 — the
   4% floor cost $10,494 vs 1%, and capital NEVER binds live (peak 3 concurrent ~$1,500 of
   $3,000, median 14 trades/day). 1% not 0%: sub-1% stops sit inside the spread. Code default
   AND the Railway MIN_STOP_PCT=4 override both set to 1. Reject rows stamp floor= so the
   nightly review grades from day one. CAVEATS (disclosed): cohort = 4 detector proxies at
   ~55 fills/day vs ~14 live; the sim skips chart/backside/momentum/runway. Rig: the six
   8/1-era 4%-floor pins re-drawn at the 1% boundary, dated; bands unchanged so the shadow
   cohorts keep their cells; minstop gate GREEN.
2. v2conv WINDOW SEAT ARMED (09:30-10:30) — the suspension's named condition (RTH floor
   settled at 1%) is met; at that floor its evidence is clean: n=456 +$5,881, TRAIN
   +$13.16/fill / OOS +$12.65/fill.
3. THE COMPETITION (run at the 1% floor / capital-aware / total dollars — the block's live
   conditions; every lane both-halves positive): ignition n=1350 +$25,182 (+$18.65/fill) >
   v2conv +$12.90 > kevseq +$12.31 > hidden_v2 +$10.88. OPEN_LANE_RANK set to that order;
   unreplayable ema9x90/ma_pullback follow the measured four (no block score, no block
   privilege); grinder cannot fire pre-10:30 by construction; hidden_v2 keeps all-day #2.
   NOTED FOR THE RECLAIM AGENDA: reclaim scored #2 (+$17.20/fill, halves agree) and is
   benched — evidence filed, not acted on.
4. HYGIENE: LANE_EXPECTANCY's hidden_v2 entry still cited the VOIDED UTC-shifted +$41.60 —
   corrected to the true-ET +$9.85 (n=95) with the void named in the source string.

**SHIP STAMP (Addendum 14):** tree c1b439ed80ad.

## ADDENDUM 15 — THE MID-DAY BLOCK + HARNESS DEBT NAMED (Marcos, ~20:1x ET)

Q: "how about 10:30 onward? Also and first thing to discuss, are those last three not fully
harnessed?"

1. THE 10:30-15:30 COMPETITION (same conditions — 1% floor, capital-aware, total dollars;
   every lane both-halves positive):
     grinder n=229 +$8,009 (+$34.98/fill, halves 32.81/38.14 — the field's STRONGEST
     agreement; the lane's design is literally post-10:30) > ignition n=552 +$12,051
     (+$21.83) > hidden_v2 n=618 +$6,359 (+$10.29; halves 14.56/6.11, both +) > kevseq
     n=1026 +$8,929 (+$8.70; NEUTRAL-ctx proxy — live front-side gates not modeled).
     v2conv +$2.20/fill — independent validation of its 10:30 seat cutoff. reclaim +$8.14,
     benched. MID_LANE_RANK wired to that order (BOLD PART STATED: grinder ABOVE ignition
     mid-day), unreplayables follow, kill MID_LANE_RANK="". Gate 28 A10 executes the branch
     (0-based-rank expectation caught by probing, fixed in the pin).
2. HARNESS DEBT, answered precisely: all three LIFT (symbols registered); the gap is LANES
   entries/drivers. ema9x90 = a five-line LANES entry (plain 10s lane; gate 17's own note:
   "tracked, not gated") — CLOSABLE. ma_pullback = the two-timeframe driver ALREADY EXISTS
   (mapb_pre_audition_20260819.py, built for the pre audition); RTH extension is small —
   CLOSABLE. dip_rip = dips to a MARKED LEVEL and no historical map archive exists —
   STRUCTURALLY BLOCKED, same root gap as runway replays; map archiving is now a
   Quartermaster item with TWO consumers waiting. Debt queued: both closable items land
   before the next roster competition so the field is complete.

**SHIP STAMP (Addendum 15):** tree 01807ddb43e2.

## ADDENDUM 16 — THE COMPLETE FIELD (Marcos: "so what is missing from 9/90 and pullback? we
spend a lot of time on them" — ~20:2x ET)

ANSWER: nothing was missing from the LANES; they were missing from the MEASUREMENT. The
harness debt was two small pieces — ema9x90 lacked a 5-line LANES entry (symbols lifted
since 8/18; gate 17's note said exactly this), ma_pullback's two-timeframe driver existed
since the 8/19 pre-audition and had never been pointed at RTH. Both paid tonight; the
ema9x90 arm positive-controlled on synthetic tape (its live fires exist only 8/19-8/20,
not yet ferried to the cache — DISCLOSED); ma_pullback ran runway-open (no historical maps
— DISCLOSED, the standing Quartermaster gap).

COMPLETE-FIELD RERUN (7 lanes, both blocks, 1% floor / capital-aware / total dollars, every
row both-halves positive):
  09:30-10:30: ema9x90 n=191 +$6,832 (+$35.77/fill, 32.47/39.32) > ma_pullback n=108 +$2,362
    (+$21.87, 22.27/21.25) > ignition +$18.65 > [reclaim +$17.20 benched] > v2conv +$12.90 >
    kevseq +$12.31 > hidden_v2 +$10.88. THE TWO LANES MARCOS INVESTED IN LEAD THE BLOCK.
  10:30-15:30: grinder +$34.98 (holds #1) > ignition +$21.83 > ma_pullback +$15.30 >
    ema9x90 +$10.80 > hidden_v2 +$10.29 > kevseq +$8.70; v2conv +$2.20 stays unranked.
ROSTERS RE-SET to the complete-field orders (OPEN: ema9x90, ma_pullback, ignition, v2conv,
kevseq, hidden_v2 · MID: grinder, ignition, ma_pullback, ema9x90, hidden_v2, kevseq) under
the standing ruling "let the data decide who should go and in what order". Gate 28 pins
updated and EXECUTED against the new orders; GREEN. dip_rip remains the one lane that cannot
compete (marked-level dependency; map archiving = Quartermaster, two consumers).
DOCTRINE (for the checklist): a lane is not DONE until it can COMPETE — the harness entry is
part of shipping, not an afterthought; 9/90 sat unmeasurable through two roster decisions.

**SHIP STAMP (Addendum 16):** tree f37f7a2ddd66.

## ADDENDUM 17 — READ-BUDGET MATERIAL-CHANGE GATE (built by Opus on Marcos's order, FABLE
audited same evening; ~22:4x ET)

Marcos: "i dont mind rereads but if we are printing the same info then what's the point.
Come up with a solution, reasoning, and build and i will have fable audit it."

MEASURED FIRST (8/20 reader log, 52 parsed rereads): 12 (23%) identical to the prior read of
the same name; 43 (83%) verdict SKIP; 2/23 reread markers followed by a fill within 30 min.
Spend context: $33.83 month-to-date = ~$1.69/day; rereads = 73 of ~139 vision calls today.

ROOT CAUSES: (D1) every trigger dedups on the MAP VERSION and a reread POSTS a new map —
self-defeating by construction (`_nme_fired[tk] != lastT`; HUIZ v6-v13 wobbled
2.29/2.25/2.29/2.22/2.11/2.22/2.22 and re-armed itself each time). (D2) the stale-chart
guard printed "no budget burned" AFTER client.messages.create() — the call was already paid.

THE FIX: one pre-call gate at the single spend point, keyed on the WORLD as of our last read
(external map edit / new high >0.5% / price move >=3%), fail-OPEN on every uncertainty, kill
RR_MATERIAL_GATE=0. Thresholds = the measured knee (8/20 sensitivity sweep: 3.0/0.5 saves
~19% while the day's only-TAKE runner keeps 10/11 reads incl. the TAKE read; 5.0/1.0 saves
37% but starves the runner to 5/11 — deliberately conservative: a missed runner read costs a
trade, a wasted read costs ~2 cents). Stale-chart guard MOVED above the render and the call.

FABLE AUDIT FINDING (blocker, fixed in-audit): the recorded fingerprint used the STORED map
keys (break/stop) on the RAW read (break_level/stop_level, translated only later by
post_level :542) — every stored fingerprint was (None,None,targets), every compare flagged
"map_changed_externally", and the gate would have PASSED EVERY READ while showing green. The
builder's replay missed it by reconstructing maps from log lines in the stored shape. Fixed
(_map_fp normalizes both shapes); pinned by EXECUTING the exact cross-shape compare that
failed (gate 29 B8b/B8c). Also verified in-audit: day-rollover safe by architecture (reader
os.execv's fresh at :1428); skipped reads cost zero API (guard precedes render+call); marker
refire on skip is log-noise only (triggers dedup at detection). DISCLOSED RESIDUALS:
structure-change on <3% drift stays unread until it moves; calibration used approximated
read times; skips are reader-log-only (grading must pull the log before Railway truncation).
Rig gate 29: 15 pins, ALL EXECUTED. GREEN.

**SHIP STAMP (Addendum 17):** tree a97e64a0ea92 — reader service deploy.

## ADDENDUM 18 — SPREAD-RELATIVE STOP GUARD, k=1 (Marcos: "ship the k=1 guard"; ~23:3x ET)

THE QUESTION THAT FOUND IT: Marcos, "does a lower min stop affect spread?" — the spread is
per-share while risk-sizing loads MORE shares onto tighter stops, so RT spread dollars ~=
$60 x (spread/stop-width) per $30 risk; a stop inside the spread pays >100% of its risk unit
before the trade starts (UUU 8/20: 0.44% stop, 11.4% spread = 382%).

EVIDENCE: spread_floor_20260820.py — 12,630 fills across the cache, 11,979 REAL NBBO quote
samples (2 gaps), REAL spreads charged into the walks: k=0 +$20,913 · k=1 +$24,265 (TRAIN
+$11,572 / OOS +$12,693 — beats no-guard on BOTH halves, drops only 104 structurally-dead
fills) · k=2 +$23,674 · k=3 +$20,253 · k=6 +$8,081. k=1 = the pre-registered winner. NOTE
the one-day 8/20 replay had said k=3 — the chop-day anecdote was WRONG at scale ("i want to
see the numbers before deciding" vindicated). Companion finding for Friday: the REAL edge is
~half paper (+$8.65/fill zero-cost vs +$4.41/fill real at k=1, per-fill basis — the
DRY_RUN-fiction haircut every proving-week number carries). Spread sampling = SIGNAL-minute
median (disclosed: live fills land seconds later where spreads on movers run slightly wider,
so real costs are, if anything, a touch worse — the LIVE guard reads the actual pre-fill
quote, exact where the study approximated).

BUILD: guard at the worker's existing quote fetch, AFTER the absolute 6% cap; refuses when
(entry - stop) < SPREAD_STOP_K x spread$; fail-OPEN on missing quotes; refusal row
spread_stop_reject stamps spread/stop_width/k/spread_pct for the nightly grading. Kill:
SPREAD_STOP_K=0. BUILD DEFECT CAUGHT IN READ-BACK: the first paste landed the orphaned
refund/return at the OUTER if level — every quoted trade would have been refunded+returned
(a silent full-book kill behind green logs). Fixed; rig gate 30 pins the containment by AST
(S3), the arithmetic executed (S6), 6 pins GREEN. Sweep 51 pass / 17 fail (baseline).

**SHIP STAMP (Addendum 18):** tree 38cec8bcc057.

## ADDENDUM 19 — DIP_RIP RESTRICTED (Marcos: "restrict it", 8/21 00:3x ET)

THE FUNNEL (live archive 7/28-8/20, run 8/20 night): 252 diprip_armed -> 121 diprip_tag ->
83 triggered_dip_rip -> 1 FILL. The lane was never starved; it was stopped at the door 82 times.
Docket line "44 triggers/8 days, 2 fills" was WRONG and is corrected here.

WHAT KILLED THE 83: minstop 25 (30%) · momentum/illiquid 14 · unknown 13 · runway 12 · spread 7
· freshness 5 · chart_gate 4 · restricted/outranked 2 · FILL 1. Stop width at trigger: median
4.44%, only 10 of 83 under 1% but 34 under 4% — i.e. the biggest killer was the 4% floor, which
became 1% the same day (Addendum 14). That looked like an unlock. It was not.

GRADED IN DOLLARS (diprip_refusals_20260820; 80 walked, 54 takeable under TODAY's gates, real
NBBO spreads, E3, $30 risk, $5,000): TOTAL -$597.93 / -$11.07 per trade. EVERY refusing gate is
a net saver — runway -$288.67 refused (the most valuable gate on this lane), minstop -$75.44,
momentum -$48.45, spread -$66.94. The floor ruling's own band [1%,4%) = -$270.73 (-$346.87
without its best). My earlier "~15 triggers re-open" HYPOTHESIS is REFUTED in the losing
direction and is retired here per REFUTATIONS-MUST-REACH-THE-LEDGER.

IS IT THE LANE OR THE EXIT (diprip_exits_20260820; same 54, same tape/costs, exit swept):
E3 -$597.93 (baseline reproduced to the cent = the sweep's own positive control) · POP5 -$551.05
· POP8 -$330.60 (best of seven) · HALF5 -$643.02 · T10 -$498.74 · T20 -$745.24 · LVL -$918.52
at a 19% win rate. LVL is the PURE THESIS arm — stop at the level, ride it — and it is the WORST.
E3 was flattering the lane, not hiding it. Marcos's "bank a win and re-enter" does help (POP8
best, win% 31->35) but improving a loser is not rescuing one. Pre-registration required positive
AND drop-best-positive; nothing came close.

RULING: dip_rip removed from the RTH_LANES default. It still DETECTS and LOGS (arm/tag/trigger
rows keep grading nightly) — it just cannot take capital. Restriction is a CAPITAL rule, not a
spec edit: the detector, BACKSIDE_EXEMPT and CHART_CEILING_LANES membership are untouched.
Kill: put dip_rip back in RTH_LANES (env). Rig gate 31 pins all of it, 7 pins GREEN.
FLAT BOOK VERIFIED THIS TURN: /api/open_trades -> {"open_trades":[]} at 00:34:43 ET, market closed.
CAVEATS ON THE RECORD: 54 trades / 24 days; 10 triggers had unattributable kills; a DIFFERENT
entry on the same setup (require the reclaim to prove above the level first) is untested and is
a different lane, not this one.

**SHIP STAMP (Addendum 19):** tree a2fae605768b.

## ADDENDUM 20 — REAL-COST ROSTERS SHIPPED + v2conv BENCHED FROM PRE (Marcos 8/21 ~03:0x ET:
## "roster according to this last competition and ship. Who's getting benched.")

THE COMPETITION (block_competition_real_20260821): the 8/20 field re-run with ONLY the costs
changed — real fire-minute NBBO spreads instead of paper slips. 15,041 fills, 14,958 quotes,
0 gaps, shared per-day capital pool across lanes, 1% floor + k=1 guard, totals at $5,000.

WHO'S BENCHED: **v2conv, from PRE.** -$1,559.31 with BOTH halves negative (TRAIN -$1,022.27 /
OOS -$537.04); its 8/19 seat evidence (+$7.76/fill) was paper and inverts to -$7.06 real. The
spread physics named it in advance (pre-registered R3): tightest stops, thinnest tape ->
haircuts +92%/+191%/+443% across blocks, the largest in the field. Mechanism: NEW switch
V2_PRE (default 0) — the bench could NOT ride V2_CONVERT=0 because that would also kill the
OPEN window seat, which SURVIVES R2 (+$208.43, both halves positive). V2_PRE=1 restores.
vwap_reclaim's stale PRE_LANE_RANK entry removed (benched 8/19; tonight graded negative in
every live-fire cut — see the reclaim forensics run set).

ROSTERS RE-SET by TOTAL DOLLARS at $5,000 (the 8/20 metric law):
  PRE   ignition (+$4,961.61, the only positive seat) > ma_pullback (unmeasured — not
        harness-replayable, the standing debt; keeps its seat behind the measured)
  OPEN  ignition +$21,866.17 (halves 10,942/10,924) > ema9x90 +$2,234.56 (+$24.03/fill, best
        per-fill in block) > kevseq +$909.09 (beat v2conv in BOTH halves — the R1 inversion) >
        hidden_v2 +$485.09 (OOS -$94.23 FLAGGED) > v2conv +$208.43 > ma_pullback (unmeasured)
  MID   ignition +$10,319.04 > grinder +$7,376.68 (best $/fill anywhere +$46.69, only negative
        haircut -33%; the flip vs the shipped order is TRAIN-driven — OOS narrowly favors
        grinder 3,795/3,611, DISCLOSED) > hidden_v2 +$1,596.15 (OOS -$904.58 FLAGGED) >
        ema9x90 +$1,456.30 > kevseq +$772.41 > ma_pullback; v2conv (-$3,844.46) stays out.

STANDING FLAG: hidden_v2 is OOS-negative in BOTH RTH blocks — no seat action under R2 (halves
mixed, not both-negative), but it is the lane today's 16:37 review watches hardest.

RIG: gate 32 (test_realcost_roster_20260821) — executed pins incl. T5 running _lane_rank at
pre/open/mid clocks against the shipped defaults (first run caught the scratch-ns missing
ENTRY_OPEN_ET — the fallback-to-LANE_RANK fired exactly as designed; scaffold fixed, bot
untouched). Gates 28 (A7c) and pre-roster P6 amended: their paper-order pins retired WITH
their evidence class, history preserved in comments. All three GREEN + gate 31 GREEN.
FLAT BOOK VERIFIED IN-TURN: {"open_trades":[]} at 02:57:57 ET.
DEFERRED TO TOMORROW (Marcos): reclaim revisit with the external-AI spec (walked tonight:
PRE +$9,929/OPEN +$12,293 passing K1, density/touch/hostile checks still unrun — NOT shipped).

**SHIP STAMP (Addendum 20):** tree d8384f6e93ab.

## CONVENING ARTIFACT — REAL-COST ROSTER SHIP (8/21 ~03:1x ET)
covers: 6fd3cc0c522d

FINDINGS + FIX-NOW: (1) SHIP_CHECK AH-ix correctly RED'd the first attempt — its pin froze the
single-gate V2_CONVERT wiring this ship deliberately splits; amended to the dual gate WITH the
ruling cited, not deleted. (2) Gate 32's T5 first run caught the scratch-ns missing
ENTRY_OPEN_ET — the LANE_RANK fallback fired exactly as designed; scaffold fixed, bot untouched.
(3) No other finding: the diff is three rank-list defaults, one membership gate, rig pins, and
bookkeeping. No sizing, exit, feed, or gate-stack code touched.

DAY-ONE WALKTHROUGH (next session, TODAY 8/21): 07:00 a PRE candidate fires v2conv -> V2_CONVERT
still converts the FIRE, but v2conv is absent from PRE_LANES (V2_PRE=0 default) -> the premarket
whitelist shadows it -> row logged, no capital; ignition on the same tape converts and books.
09:31 v2conv fires -> _lane_window_ok passes (LANE_WINDOWS unchanged) -> converts inside the
window, ranked LAST of the measured five by _lane_rank("v2conv","09:31")=4. 10:31 v2conv fire ->
window closed, RTH_LANES excludes it -> shadowed. 12:00 contested slot ignition-vs-grinder ->
_lane_rank returns 0 vs 1 -> ignition takes it. The 16:37 review grades every one of these rows
including the two FLAGGED hidden_v2 OOS cells.

doctrine-inversion sweep: the DOCTRINE changed tonight — "paper-cost evidence can seat a lane"
is repealed; seats now require real-NBBO-cost evidence. Old-doctrine encodings found and
handled: AH-ix (amended, above); gate-28 A7c + pre-roster P6 (amended with the evidence class
named); PRE_LANE_RANK comment block at :3835 still NARRATES the paper audition as history —
kept deliberately as provenance, marked by the 8/21 ruling comment above it; LANE_EXPECTANCY
per-lane notes still carry paper-era dollar figures as SOURCE strings (data, not gates — flagged
for the lane-dossier pass Marcos ordered for tomorrow, where each lane gets paper AND real side
by side). No other encoding of the repealed premise found in RTH_LANES/PRE_LANES/LANE_WINDOWS/
rank consumers.

ROLL CALL — Blast Radius Auditor: touched (this artifact; AH-ix catch is its process working).
Systems Quant: touched (the competition run + total-dollars ranking is its work product).
Statistician: touched (R1 both-halves rule applied; grinder/ignition OOS nuance disclosed, not
buried). Momentum Operator: touched (ignition #1 everywhere at real costs — no objection).
Trade Manager: clean (exits untouched). Reclaim Architect: touched (reclaim rank entry removed;
external-AI spec walk filed for tomorrow's revisit, NOT shipped). Hidden Entry Architect:
touched (hidden_v2 OOS flags stand; seats kept under R2). First Hour / Opening Bell: touched
(OPEN order re-set; window mechanics unchanged). Side Marshal: clean (no side logic). Crown
Steward: clean (crown privileges untouched). Feed Engineer: clean (no feed change; halt-lane
HALT_ARM_5S contradiction remains OPEN on the docket, not part of this ship). Webull Broker
Desk: clean (no broker surface). Quartermaster: touched (ma_pullback unmeasured-at-real-costs
is its standing harness/cache debt, named in the rosters). Kev Librarian: clean (no corpus
change). Seam Scientist: clean. Strength Ombudsman: touched (v2conv bench is a WEAKNESS
prosecution at real costs, not a strength refusal — evidence attached). Forward Architect:
touched (tomorrow's lane-dossier + adversarial-AI audit program recorded on the docket). Tape
Veteran: clean. Execution Surgeon: touched (spread physics R3 validated in-field). Handicapper:
touched (rank = total dollars at $5,000). Rocket Rider: clean (halt lanes untouched tonight
beyond the standing restriction). Cartographer: clean (no map logic). Wind Tunnel Engineer:
clean with reason: re-rank of existing lanes, no new mechanism to gauntlet; the kevspec
candidate is NOT in this ship and faces the full gauntlet before any convert. Convexity Trader:
clean. Curl Mechanic: clean (curl feed untouched). Pit Crew Chief: touched (deploy + boot
verify below). Integrator: touched (three gates GREEN post-amend; parse check run). Dashboard
Curator: clean with reason: boot_config row carries the new defaults automatically. Project
Manager: touched (docket updated — reclaim revisit + lane dossiers tomorrow). Historian:
touched (paper-era orders retired with provenance preserved in comments and this file).

## ADDENDUM 21 — SIM FRAME -> $5,000 (Marcos 8/21: "change it after the close")

RULING: SIM_ACCOUNT_BALANCE 3000.0 -> 5000.0 so the DRY_RUN sim models the go-live funding of
margin acct …9AGA. BLAST RADIUS TRACED BEFORE THE RULING and re-pinned in rig gate 33:
risk/trade UNCHANGED (RISK_PER_TRADE=30.0 is a flat constant, not a % of balance) · position
size UNCHANGED (clamp = min(70% x balance, MAX_TRADE_DOLLARS=$1000); gate 33 B3c EXECUTES the
arithmetic and shows the $1,000 cap binds at BOTH $3k and $5k) · the ONLY behavioural change is
CONCURRENT CAPACITY 3000 -> 5000, and measured live peak is 3 concurrent ~$1,500. NOT included,
needs its own ruling + kill-test: R=$30 is 1% of $3,000 but 0.6% of $5,000; 1% of the real
account is R=$50, a BEHAVIOUR change. No published study number is invalidated — every
real-cost run this week reported BOTH books. Gate 33: 8 pins GREEN.
FLAT BOOK VERIFIED IN-TURN: {"open_trades":[]} at 18:21:52 ET, market closed.

## THE 16:37 GRADING — 8/21 (standing duty; 719 refused/shadow rows walked at $30 risk, E3)

DAY: -$13.67 on 14 trades. PRE +$4.78 (XOS +1.89, VIVK +2.89, both 09:25 flats) /
RTH -$18.45. kevseq carried the book (+$28.39 on 5 trades incl. SDOT +18.57, LSTA +19.81);
v2conv went 0-for-3 at -$18.23, every fill a stop; grinder ANY -$22.08 was the day's worst.

PRE refusals: counterfactual **-$1,192.16** over 225 rows — the premarket gates SAVED money
today, decisively. Biggest savers: pullback_first_suppress -$412.80 (n=69), v2conv fires
-$241.63 (n=16, the bench earning its keep on day one), hidden_observe_only -$232.95,
reclaim_shadow -$212.95, lane_restricted -$126.81.
  THE ONE COST: flat_top_observe_only **+$398.53 over 29 rows** — HOWL 05:39 +$143.13, BTCT
  05:43 +$110.85, BTCT 06:04 +$103.19. NOTE THE FRAME (v2 study, same day): flat_top's PRE cell
  grades +$3.96/fill and DIES at +1 tick (+$0.31) with 59% top-5 concentration. Today's premarket
  flat_top money is the REGIME-DEPENDENT cell paying off on one tape — evidence for the
  retrial's PRE question, NOT evidence to unrestrict.

RTH refusals: counterfactual **+$626.10** over 494 rows — the RTH gates COST money today.
  COSTS: pullback_first_suppress +$534.08 (n=130 — the single biggest line either way),
  dip_rip +$179.24 (n=4, restricted last night), lane_restricted +$168.78, grinder +$145.18,
  flat_top_observe_only +$131.76.
  SAVERS: hidden_observe_only -$670.72 (n=45 — hidden v1 restricted, still the best refusal on
  the board), v2conv -$220.20 (n=28), reclaim_shadow -$203.55.
  Biggest single misses: EXYN 12:14 +$139.19 (v2conv fire AND lane_restricted, same bar),
  JUNS 09:57 hidden_observe_only +$125.69.

THE HEADLINE FOR THE WEEKEND: pullback_first_suppress is on BOTH lists and is the largest line
on each — it SAVED $412.80 in premarket and COST $534.08 in RTH, on 199 rows. That is a
session-dependent gate nobody has ever graded. It goes to the top of the edge-widening list
above flat_top, because it is bigger than flat_top in both directions.
CAVEAT ON EVERY NUMBER ABOVE: one day, n=719 counterfactuals, flat-slip walks (no NBBO charged
— the real-cost haircut runs ~50%), and refused trades never competed for capital against the
trades actually taken. Directional, not bankable.

**SHIP STAMP (Addendum 21):** tree 0a67fd14a1b1.
