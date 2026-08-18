# B2 — FIRE-AGE GUARDS ON THE UNCOVERED LANES (EG1-b) — 2026-08-17

## FAILURE CONDITION (written FIRST)

This mechanism is **WRONG** if:

1. A stale bar is not, in fact, a stale signal — i.e. a fire off a 38-minute-old bucket
   performs no worse than a fire off a 20-second one. Falsified by: grading the
   `stale_fire_suppressed` rows an armed guard produces against the tape they refused, over
   ≥5 sessions, and finding the refused set profitable.
2. `_bucket_fresh`'s clock is measuring something other than signal age — e.g. the bucket
   epochs handed to a detector are systematically back-dated by the feed, in which case the
   guard would refuse fresh signals. (`_bucket_fresh` is already halt-aware; a feed-side
   back-date would be a separate, larger defect.)
3. Arming a lane changes any behaviour other than refusing a fire and writing a canary row.
4. `LANE_FIRE_AGE_GUARD=""` (the default) is not a perfect no-op.

## LIMITS / CAVEATS — READ BEFORE THE DEFAULTS

**The cost of this guard is UNQUANTIFIABLE today for six of the seven lanes, and that is
the reason every lane ships DISARMED.** `fire_age_s` is stamped on only a fraction of fires:

| lane | fires today | fires carrying `fire_age_s` | of those, >90s | cost if armed at 90s |
|---|---|---|---|---|
| grinder | 15 converted (66 shadow) | **5** | **4** (median **2264.8s = 38 min**) | ≥4 of 15 refused; the true number is unknown for the 10 unstamped |
| v2conv | 20 converted (164 shadow) | 0 | — | **UNKNOWN** |
| bandpass | 0 converted (9 shadow) | 0 | — | **UNKNOWN** (and n=0 converted, so untestable today) |
| prevwap | 3 converted | 0 | — | **UNKNOWN** |
| flat_top | 74 | 0 | — | **UNKNOWN — and NOT BUILT, see below** |
| crown_seam | 4 shadow / 7 beats | 0 | — | **UNKNOWN — NOT BUILT** |
| halt_ladder | 1 arm | 0 | — | **UNKNOWN — NOT BUILT** |

An age guard **REMOVES TRADES**. Arming one whose cost cannot be measured is a silent
tightening, which is exactly what the batch brief forbids. So: the **mechanism** ships (it is
the missing property, and it cannot be armed later if it does not exist), **armed on nothing**.

Also stated plainly: today's 5 stamped grinder ages are ONE session and a **selected** subset
(the fires that happened to pass through the 8/17 drift-stamp path), so even the grinder number
is not a clean rate.

## ROOT CAUSE

`_log_stale_fire` — the `CURL_FIRE_MAX_AGE_SECS` suppressor — was called from four detectors
(`kev_reclaim_step`, `hidden_entry_step`, `kev_zoneflip_step`, `ignition_10s_step`) and from
nowhere else. `v2_pullback_step`, `grinder_shadow_step` and `bandpass_step` (which serves both
bandpass and prevwap) had **no staleness mechanism at all**, so a bucket replayed after a
restart or handed over late by a slow scan cycle fired as if it were live.

The archive convicts the design, not a hypothesis: **4 of the 5 stamped grinder fires today
were on bars older than 90 seconds, median 38 minutes.** And the day's second-worst kevseq
entry drift (WETO 13:50, +9.94%) sits on a bar `fire_age_s`=2284.8s, while the *next* WETO fire
four minutes later (`fire_age_s`=18.0s) drifted +0.95%. **Entry drift is largely a staleness
symptom** — which is why B1 and B2 were found in the same rows.

## WHAT CHANGED — THE SAME MECHANISM, NOT A NEW ONE

`marcos_trading_bot.py`:
- `_parse_lane_age_guard(spec)` — parses `LANE_FIRE_AGE_GUARD`, a comma list. A bare lane name
  uses the shared `CURL_FIRE_MAX_AGE_SECS`; `lane:secs` overrides it for that lane.
- `_lane_fire_stale(sym, lane, k, px)` — returns True only when the lane is **armed** *and*
  the shared `_bucket_fresh(k, sym=sym)` (halt-aware) says the bucket is too old, and then
  emits the **same** `_log_stale_fire` → `stale_fire_suppressed` canary row the four covered
  lanes emit. Wrapped in try/except returning False: a bookkeeping bug must never stop a fire.
- wired at the fire site of `v2_pullback_step` ("v2conv"), `grinder_shadow_step` ("grinder")
  and `bandpass_step` (lane **parameter**). On suppression the setup is **consumed** — `st["n"]`
  advances and the cooldown starts — mirroring exactly what the covered lanes do, so a
  suppressed fire cannot be re-emitted on the next call.
- `bandpass_step` gained a `lane="bandpass"` parameter; the two call sites pass
  `lane="bandpass"` and `lane="prevwap"` so a suppressed prevwap row is attributed to prevwap.
- `_LANE_AGE_GUARD` is parsed **lazily** on first call rather than at import. This is not
  style: the isolation rig lifts bot symbols by replaying module-level assignments *before*
  function definitions, so an import-time assign that calls a module-level function makes every
  10s detector un-liftable (rig BH-c). Found by the rig, fixed at the source.

### ONE SHARED ENV, NOT SEVEN — justification

The lanes share one mechanism and one threshold source (`CURL_FIRE_MAX_AGE_SECS`), and the
decision being made is the same decision for all of them: *is this bucket old enough that the
signal is fiction?* Seven envs would be seven places to forget. The `lane:secs` form exists for
the day a lane earns its own number, so per-lane control is available without per-lane envs.

## DEFAULT: **DISARMED FOR EVERY LANE** (`LANE_FIRE_AGE_GUARD=""`)

Per-lane reasoning, as required:

- **grinder** — the only lane with evidence, and the evidence is bad (4/5 stamped fires >90s,
  median 38 min). It is also therefore the lane where arming removes the most trades, and 10 of
  its 15 fires have no age at all. **Recommended first to arm** once one session of stamped
  rows exists; not armed tonight because "≥4 of 15" is a floor, not a cost.
- **v2conv** — 20 converted fires, zero ages. No basis. OFF.
- **bandpass** — zero converted fires today. Nothing to measure. OFF.
- **prevwap** — 3 converted fires, zero ages. n too small to argue either way. OFF.
- **flat_top / crown_seam / halt_ladder** — **NOT BUILT** (see below). Pins stay OPEN.

## WHAT WAS **NOT** BUILT, AND WHY

`flat_top`, `crown_seam` and `halt_ladder` have **no separable detector and no fire dict** —
the caller appends to `breakouts` inline, and the fire price is the **live quote**, not a bar
close. There is no bucket epoch `k` at those sites to age. Giving them a real age guard means
first giving them a fire-bar identity (item **B3**, the drift/age stamps), and B3 is not shipped
either. Porting "the same mechanism" to a lane that has no bar to measure would mean inventing a
different mechanism and calling it the same one — refused. **EG1-b and EG1-c stay OPEN for these
three, with this document as the reason.**

## ACCEPTANCE

- `rig/test_batchB_20260817.py::SPEC_lane_fire_age_mechanism` — the guard is present in each of
  the three detectors, naming its own lane, with `lane` a parameter in `bandpass_step` and both
  call sites passing their lane.
- `rig/test_batchB_20260817.py::SPEC_lane_fire_age_suppresses` — **executes** the shipped
  helper: armed+stale → True, armed+fresh → False, disarmed+stale → False. A guard that is
  wired but inert cannot pass.
- EG1 pins `v2conv.b`, `grinder.b`, `bandpass.b`, `prevwap.b` flip `OPEN` → `True`; the EG1
  property computer now recognises `_lane_fire_stale` as the shared form of the same mechanism.
- Rig `test_shipset_20260804.py` halt-aware pin updated 4 → 5 `_bucket_fresh(k, sym=)` sites
  (4 in-detector + the shared helper).
