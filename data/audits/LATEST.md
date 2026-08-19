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
