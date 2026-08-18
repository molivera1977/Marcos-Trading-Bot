# REGRESSION FIXTURE INDEX — the permanent memory of what has already bitten us

**Why this file exists.** The session-boundary defect kept coming back in new consumers because
nothing pinned it. A defect that is diagnosed, fixed and then forgotten is a defect with a return
date. Every fixture below carries REAL numbers from the artifact that found it, a one-line
statement of what it prevents, and a NEGATIVE CONTROL that demonstrably fails on the pre-fix
behaviour — because a regression test that cannot go red is decoration.

**Rules for this corpus.**
1. Real numbers only. If a fixture's real numbers cannot be recovered from an artifact, the
   fixture is not built — it is not invented. Each file names its `_source` and, where it came
   from a decisions archive, the `_repro` query that reproduces it.
2. Every fixture has a negative control. Where the pre-fix code is reachable in git the control
   is `git show <sha>:<file>`. Where it is not, the defective behaviour is SIMULATED EXPLICITLY
   and the fixture and the rig both say so at the point of use.
3. Fixtures are append-only. A fixture is retired only by Marcos, never by the agent whose ship
   it inconveniences.

**Runners.**
- `python3 rig/test_gates_20260817.py` — gate 8 drives fixtures 1-5.
- `python3 rig/test_regression_corpus_20260817.py` — sections I1-I8 drive fixtures 6-13.
Both are judged by EXIT CODE.

---

## The corpus

| # | Defect it prevents | Found | Artifact | Fixture | Rig | Negative control |
|---|---|---|---|---|---|---|
| 1 | M1 "50 bars" is a TRADED-minute count, so a thin name's 1-min window spans 243 min (RBNE: 48 bars) | 2026-08-17 | `data/killtests/m1_wallclock_20260817.md` | `rbne_m1_window_20260817.json` | G8-a | PASS — `M1_WALLCLOCK=0` / `window_min=0` keeps all 48 bars |
| 2 | kevseq converted at the live quote ($8.20) instead of a limit off the fire price ($5.1329) — 6.49% stated risk vs 41.46% real | 2026-08-17 | `exit_params_our_fires_20260817_arch.json` + `today_counterfactual_20260817.md` | `kevseq_drift_wff_20260817.json` | G8-b | PASS — pre-fix arithmetic reproduces the real −$6.88 trade; `KEVSEQ_LIMIT_ENTRY` default OFF |
| 3 | The 09:30 bell flipped sessions to RTH-only before any completed RTH bar existed — 23 of 26 names skipped 09:30-09:35 | 2026-08-17 | `data/killtests/pre_staleness_forensic_20260817.md` | `bell_boundary_20260817.json` | G8-c | PASS — `RTH_HANDOFF_MIN=0` returns RTH-only at 09:30:30 |
| 4 | Five non-fill v2conv triggers exhausted `V2_DAILY_CAP=5` before 04:36, killing the lane for the day (39 later refusals) | 2026-08-17 | `data/killtests/ghost_cap_20260817.md` | `ghost_cap_v2conv_20260817.json` | G8-d | PASS — refunds off reproduces used=5, lane dead |
| 5 | A stale $10.15 rendered as "AH" beside the live $26.20 at 15:38 ET (WETO) | 2026-08-17 | commit `fb92556` + Marcos's 15:38 screenshot | `stale_ah_display_20260817.json` | G8-e | PASS — `git show fb92556^:screener_app.py` has an UNGATED render site |
| 6 | A restart wipes the 10s cursors; deep-rehydrate re-feeds the day and detectors RE-EMIT historical fires — and conversion lanes CONVERTED them (RBNE grinder 5x at seq=0 behind 5 boot_config rows) | 2026-08-17 | `RESULTS_LEDGER.md` 8/17 restart-replay correction + archive | `restart_replay_20260817.json` | I1 | PASS — `DEDUPE_FIRES=0` emits 5 times, reproducing the five seq=0 rows |
| 7 | `detect_ma_pullback` is a pure function with nothing marking the setup consumed, so the lane pushed a fresh candidate through the whole trade path every scan pass (YDES 40 rows, one price, 34 min) | 2026-08-17 | `data/killtests/ma_pullback_dup_20260817.md` | `ma_pullback_reattempt_20260817.json` | I2 | PASS — dedupe off emits on all 40 passes, the exact YDES row count |
| 8 | `kevseq_step` returned the setup bar's HIGH — a LEVEL, not a traded price — handing sizing a fictitious risk-per-share (WFF: 6.49% told, 41.46% paid, 6.4× the intended risk) | 2026-08-17 | `data/killtests/kevseq_fire_price_20260817.md` (`2d0a6cb`) | `kevseq_level_price_20260817.json` | I3 | PASS — `git show 2d0a6cb^` has the unconditional level and NO kill switch |
| 9 | Two 1-MINUTE front-side sources on DIFFERENT CLOCKS — traded-minute grid vs contiguous wall-clock grid; 31 disagreements, RBNE's "1-min EMA20" spanning 243 min, UUU's 584 | 2026-08-17 | `data/killtests/kevseq_frontside_tf_20260817.md` + `kevseq_frontside_disagree_20260817.json` | `frontside_clock_20260817.json` | I4 | PASS — unwindowed, the caller keeps 48 bars over 243 min (4.0 hours of "EMA20") |
| 10 | A detector invoked without a required ctx field silently DEFAULTS — the hole that made four studies grade a front-side-FREE kevseq | 2026-08-17 | `data/killtests/live_harness.py` + `kevseq_frontside_tf_20260817.md` §4 | `harness_ctx_refusal_20260817.json` | I5 | PASS — **SIMULATED** (no pre-fix commit: the old scripts had no ctx contract at all). A permissive `missing key -> None` checker returns a ctx with `front_side` silently None where the strict one refuses by name |
| 11 | `_bucket_fresh` compares the bucket to `time.time()`, so replay ate 100% of fires and two lanes were unstudiable (hidden: 0 fires / 13 names disarmed, 424 armed) | 2026-08-17 | `data/killtests/harness_lift_remaining_20260817.md` LANE 1 | `bucket_fresh_replay_clock_20260817.json` | I6 | PASS — hook disarmed, all 13 names' 8/17 buckets are stale → 0 |
| 12 | Kill-test scripts re-implemented the detectors they were grading; replicas drift, always in the flattering direction | 2026-08-17 | gate EG2 in `rig/test_shipset_20260804.py` + `live_harness.py` | `study_replica_20260817.json` | I7 | PASS — the hand-rolled script trips, its `live_harness`-importing twin is clean |
| 13 | 8/17 was FIVE machines; one produced 51% of the fire rows and 5 of the 7 fills, and nothing in any aggregate said so | 2026-08-17 | `data/audits/config_hash_20260817.md` (`config_epochs.py`) | `config_epoch_20260817.json` | I8 | PASS — a range doc with no declaration, or one placed outside LIMITS, FLAGS |

---

## Not built (and why)

Nothing from the assigned Batch-I list was skipped: all eight had recoverable real numbers.
One correction is carried in fixture 9 rather than silently dropped — the **3-minute front-side
timeframe** premise the task was handed over with was REFUTED against HEAD
(`SETUP_TF_MIN` never reaches `_ks_ctx["front_side"]`; measured cost **$0 / N = 0**). No fixture
pins a timeframe defect, because there was none. What fixture 9 pins is the CLOCK defect that the
investigation actually found. Pinning the refutation alongside the defect is deliberate: the 7/27
lesson is that a refutation living only in a comment is one the next verdict will not see.

## Adding a fixture

1. Write the `_defect` line first — one sentence, mechanism not symptom.
2. Pull the numbers from the artifact programmatically where the archive allows it, and record
   the `_repro` query in the fixture. Never retype a number you can query.
3. Write the negative control BEFORE the assertion, and watch it go red.
4. Add a row here. A fixture that is not in this table does not exist as institutional memory.
