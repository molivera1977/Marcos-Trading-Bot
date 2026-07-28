# LEVEL AWARENESS — design note (7/27, Marcos's directive)

**The directive (Marcos, 7/27 night):** "We need to include awareness to the levels with these
entries and not just a gate check."

**The measured defect:** every entry lane triggers on bar structure/volume alone (flat_top: 3-min
base break · ignition: volume surge · hidden: velocity+wick · zone/reclaim: 10s flush-curl on
SELF-derived structure · ma_pullback: MA touch). Price-vs-marked-level enters exactly once, as the
chart gate's after-the-fact yes/no — and the tape lanes bypass even that. Consequence, 7/27: early
below levels (BIYA −1min/−18%, DFNS −168min/−25%) and late above them (LVWR +54min/+86%) are the
same location-blindness. Kev, same names, same day: +140% on LVWR from HIS level.

## Integration points (ordered by evidence; each gated on its own test)

### 1. Sheet level as OVERHEAD SUPPLY in compute_room  — awareness as INPUT (doctrine-clean)
When entering BELOW a marked break, that level is a known barrier: feed it into `compute_room` as
a supply candidate so room/R:R sees it. LGHL 7/27: entry 1.975 under the 2.20 break = 11% room to
a mapped wall — room gate never saw it (self-computed supply only).
**Test before ship:** replay era entries w/ level-supply added to room; grade blocked/allowed by
realized dollars. Not run yet.

### 2. BALLPARK (±10%) as an entry MODULATOR — pending the pre-registered Friday 7/31 dollar-grade
Fire-graded evidence (135 fires, 7/23-27): inside ±10% of the level 54% win vs 29% outside; the
far-above cell conflicts with the 7/21 read-staleness DOLLAR verdict (blocking past-map = blocking
momentum) → dollars decide, scored separately, Friday, terms already pinned in the ledger.
If it passes: modulate (size down / skip) outside the ballpark when a FRESH level exists.
Stale/dark reads excluded per Marcos's governance ruling — a stale map yields NO verdict.

### 3. Sheet level as an ARMING ZONE for the curl lanes — PICKS-ONLY, forward-gated
The curl machinery (zone_flip/reclaim: arm at a price, wait for flush→shelf→curl) already exists;
it is aimed only at self-computed structure. Pointing it additionally at `src=kev` levels =
level-first entry. **REFUTED as a blanket lane 7/27** (`killtest_level_first.py`: all sheet names,
−$334 @1-min / −$561 @10s; the sheet is 60-85 names/day incl. vision-SKIPs; Kev trades his top-3
that SET UP). Picks-only variant is UNTESTED (n≈3/day): the 7/28+ sheet carries `src=kev` picks and
every fire stamps `level_gap_pct` → accumulate ≥3-4 weeks of picks-only forward data, then test.

### Named sub-item: the extension-guard anchor
`ignition_ext_live_skip` killed the ONE on-time LVWR fire (1.845, +15.3% from the 1.60 open) —
extension measured from the OPEN guarantees rejection on a name that opens AT its level. Candidate:
anchor extension to max(open, marked level) when a fresh level exists. UNTESTED.

## Acceptance criteria (pre-written so Friday is a wiring job, not a debate)
- #1 ships if level-supply room replay ≥ break-even vs baseline on era dollars AND blocks no
  top-decile winner (the room-inversion class check).
- #2 ships if Friday's ballpark dollar-grade is positive with the far-above cell scored separately
  and not net-negative-vs-momentum.
- #3 ships only picks-only, only after the forward picks sample exists, via its own kill-test.
- Everything logs its counterfactual (what it would have blocked/resized) for its first week.

Standing rules: [[feedback_replay_rig_gate]] · [[feedback_backtest_before_recommend]] ·
[[feedback_review_both_sides]] · chart-gate doctrine (7/26: no absolute vetoes; tape lanes decide
by tape — awareness here is INPUT, not veto).
