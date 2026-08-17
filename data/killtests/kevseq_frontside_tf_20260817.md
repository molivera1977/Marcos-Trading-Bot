# KEVSEQ FRONT-SIDE TIMEFRAME — 8/17 — VERDICT: **the alleged 3-MIN defect is REFUTED IN CODE; the real finding is that NO offline study ever replicated the live front-side gate at all.**

## 0. FAILURE CONDITION (written FIRST)
This work is WRONG if any of the following is true:
1. A SETUP_TF_MIN (3-min) value can reach `_ks_ctx["front_side"]` while `KEVSEQ_FRONTSIDE_1M=1`.
2. A kevseq row can be written without `front_side_src` / `front_side_3m` / `front_side_tf`.
3. The fail-closed semantics move: a genuinely short 1-min history must still produce
   `front_side=None` and a `front_side_unknown` refusal — never a fabricated value.
4. `SETUP_TF_MIN` can be changed and silently re-time kevseq's gate.
5. The disagree canary stops firing.
Rig section **TF** (15 pins, `rig/test_shipset_20260804.py`) tests all five. Full rig exit 0.

## 1. THE ALLEGED DEFECT — REFUTED
Claim as handed over: *"the caller computes `_ce9/_ce20` from `aggregate_bars(cache[t]["full_bars"], SETUP_TF_MIN)` and SETUP_TF_MIN=3, so kevseq has been gated on a 3-MINUTE front side since 8/16."*

**Not true.** Read in code this turn:
- The kevseq caller reads `_ks_1m = (bars or [])[:-1]`, and `bars = cache[t]["bars"]` (assigned once
  per candidate in the detect loop, never rebound before the kevseq block). `cache[t]["bars"]` is
  filled from the **M1** broker/Alpaca fetch — 1-minute bars. Confirmed: `get_intraday_bars` sends
  `timespan: "M1"`.
- The `_ce9/_ce20 = aggregate_bars(..., SETUP_TF_MIN)` block sits ~200 lines **below** the kevseq
  block and feeds **dip_rip / zone_flip / vwap-reclaim / flat-top** — lanes whose own spec IS the
  3-min setup chart (SETUP_TF_MIN doctrine, "setups come from the three minute"). It never touches
  kevseq's ctx.

So kevseq's spec ("front side on the 1-MIN aggregate") and its implementation **agree on timeframe**.

## 2. WHAT THE CANARY ACTUALLY CAUGHT — two different 1-MIN sources
31 `kevseq_frontside_disagree` rows on 8/17, all between 13:50 and 13:58 (the
`KEVSEQ_SELF_FRONTSIDE` fix went live 13:49; before that no row carries `front_side_src`).
Both sides are 1-minute; they differ in **history depth and session span**:

| side | source | bars on the disagree rows |
|---|---|---|
| caller | broker M1 REST, RTH-only, fetch capped ~50 | `caller_n` = 39–49 (49 on 27 of 31 rows — the cap) |
| self | our own aggregate of the fed 10s bars, day-wide, uncapped | `self_n` = 40–155 |

Different seed length (and premarket inclusion) → different EMA9/EMA20 → near-crossover flips.
Direction is both ways: caller=True/self=False ×22, caller=False/self=True ×9. Named rows include
RBNE (caller True 49 / self False 81–87, 8 consecutive cycles), FXHO (True 49 / False 92–95),
UUU 13:56:50 (True 39 / False 155), PFSA (False 49 / True 68–69), TRUG, RPGL, DFSC, CDTG, YYAI, IVF.

**Which 1-min source should govern is a money decision and is NOT decided here** — it is Marcos's
call (feedback_auditor_cannot_authorize_behavior). Default behaviour is unchanged by this commit.

## 3. ARTIFACT-REPLICATION AUDIT — which studies used which front side
| artifact | front-side in its replication | matches live? |
|---|---|---|
| `kev_rosetta_20260816` | **FAST chart (10s bars)**: `px > vwap AND e9 > e20` on the tick bars | NO — wrong timeframe *and* an extra VWAP clause live does not have |
| `fastchart_2tf_rerun_20260817` | ran **FAST / 1MIN / 3MIN** side-by-side; front side = `e9>e20 AND close>vwap` on the slow aggregate | PARTIAL — the 1MIN arm is the closest thing that exists, but adds the `close>vwap` clause and is built from ticks, not the broker M1 |
| `kevseq_reconciliation_20260817` | **none** — front_side not reconstructible on the 10s cache, clause dropped | NO |
| `burst_saturation_20260817` | **none** (same engine, day-gain floor only) | NO |
| `kevseq_floor_sweep_20260817` | **none** | NO |
| `entry_drift_20260817` | **none** — disclosed in its own docstring: "front_side/top3/blue_sky are NOT reconstructible on the 10s cache … the context clause is replaced by the day-gain floor alone" | NO |

**THE HEADLINE: live has never been the lane we backtested — but not for the reason alleged.**
Four of the six studies applied **no front-side gate at all** (an explicitly disclosed *superset*
cohort); one applied a **10-second** front side; one benchmarked 1-min-vs-3-min slow context with a
VWAP clause the live gate does not carry. **Zero** studies replicated the live gate as shipped
(broker-M1 9EMA>20EMA, no VWAP clause, ~49-bar history, fail-closed on unknown).
The nearest evidence we do own points the same way as the spec: in `fastchart_2tf_rerun_20260817`,
1-MIN context beat 3-MIN across the board on the primary 10s tick twin (all detectors:
1MIN −$382 vs 3MIN −$1,184; det B 1MIN −$464 vs 3MIN −$1,135). So a 3-min kevseq gate would have
been the *worse* lane — which is why the 3-min arm here ships default-OFF.

## 4. TODAY'S COST (8/17 archive, 13,703 rows)
kevseq rows: 133 `kevseq_reject`, 19 `kevseq_shadow_fire`, 19 `triggered_kevseq`, 31 disagree.
Refusal `why` census: day_gain 89, no_burst 68, **front_side_unknown 58, front_side_off 11**
(69 rows total mention front_side), burst_unmeasured 19, no_room 6, degenerate_stop 2.

**front_side as the SOLE blocker — the rows the gate alone cost us — N = 8:**

| time (ET) | ticker | fire px | why |
|---|---|---|---|
| 04:05:12 | IPST | 3.89 | front_side_unknown |
| 09:45:43 | PFSA | 4.77 | front_side_unknown |
| 09:47:09 | PFSA | 4.98 | front_side_unknown |
| 09:50:15 | WETO | 13.43 | front_side_unknown |
| 09:50:15 | CDTG | 2.6892 | front_side_unknown |
| 09:51:32 | CDTG | 2.73 | front_side_unknown |
| 10:02:31 | STFS | 6.63 | front_side_unknown |
| 11:58:33 | WETO | 17.60 | front_side_off |

All 8 predate the 13:49 self-frontside fix; 7 of the 8 are the `unknown` class that fix closes.

**Cost of the alleged 3-min-vs-1-min defect: $0 / N=0.** No row was blocked by a front-side value
of the wrong timeframe, because no row ever carried one. The two post-fix `front_side_off` rows
with a governing source stamped (TRUG 13:50:04 $1.61, AIOS 13:56:50 $13.34) each carried an
*additional* blocker (`no_burst`, `burst_unmeasured,day_gain`), so even flipping the front side
would not have produced a fire. **Direct cost today: zero fires unblocked.**
The 1m-vs-3m counterfactual cannot be computed retroactively — no row before this commit carries a
3-min stamp. That is exactly the hole `front_side_3m` now fills, from tomorrow's tape forward.

## 5. WHAT WAS BUILT (behaviour-neutral by default)
1. **`KEVSEQ_FRONTSIDE_1M`, default `1`** — pins kevseq's governing front side to a **1-MINUTE**
   source, structurally: with it on, the only 3-min assignment in the block is unreachable, so no
   future edit (or change to `SETUP_TF_MIN`) can silently re-time the gate. `0` arms the 3-min
   setup-chart context — the offline-worse arm — for testability only.
2. **`front_side_3m` + `front_side_tf` stamped on every kevseq row** (reject, shadow fire,
   triggered) and on the disagree canary. Observability is free; the 1m-vs-3m counterfactual
   becomes an archive query.
3. **`front_side_src` unchanged and always logged** (`caller_1m` / `self_10s_agg` /
   `unknown_short_agg` / `setup_3m` / `unknown_short_3m`).
4. **Fail-closed unchanged**: a 1-min aggregate shorter than `EMA20_PERIOD+2` still yields
   `None` → `front_side_unknown` → refusal.
5. **boot_config** now publishes `kevseq_frontside_1m` and `setup_tf_min`.
6. Spec header at the kevseq block corrected to say the timeframe is 1-min and is *not* the
   SETUP_TF_MIN chart, with a pointer to this doc.

**Nothing about what the bot does with money changed.** Default `KEVSEQ_FRONTSIDE_1M=1` reproduces
today's live behaviour exactly.

## 6. OTHER-LANE SPEC-vs-IMPLEMENTATION AUDIT (three rings, ring 2 — reported, NOT changed)
Every consumer of a front-side value was enumerated (`grep front_side|_ce9|_ce20`):

| lane | spec comment says | implementation reads | match? |
|---|---|---|---|
| kevseq | 1-MIN aggregate, caller-supplied, not the fast chart | broker M1 `cache[t]["bars"]` (+ 10s→1m fallback) | **YES** (this commit pins it) |
| dip_rip | 3-min setup chart (SETUP_TF_MIN doctrine) | `_ce9/_ce20` from `aggregate_bars(full_bars, 3)` | YES — and it is a **stamp**, not a gate |
| zone_flip | same | same `_ce9/_ce20` stamp | YES |
| vwap-reclaim / reclaim | "front-side / MA-pullback levels all read the timeframe Kev actually trades" | 3-min aggregate (`_re9/_re20`, `_rk_comp`) | YES |
| flat_top / ORB / break-attack | "front-side = 9>20 EMA (Kev #006). OBSERVE-not-gate on the flat-top breakout" | 3-min `ema9/ema20`, stamped | YES (observe-only) |
| ignition (hidden/10s) | 3-min composite `_ig_comp` | `aggregate_bars(full_bars, 3)` | YES |
| MA-pullback | "pullback is 9>20-gated" on the setup chart | 3-min | YES |
| v2conv / grinder / bandpass / prevwap | no front-side clause in their specs | consume none | n/a |

**No other lane has a front-side spec/implementation timeframe mismatch.** kevseq is the only lane
whose spec names the 1-minute chart, and it is the only lane reading M1 — correctly.

## 7. Officers
Hidden Entry Architect (lead; kevseq is his lane), Systems Quant (does the code compute what its
name claims — it does, the allegation did not survive the read), Blast Radius Auditor (ring 2 lane
census above; no behaviour change to review), Side Marshal (front-side timeframe = his file; 1-min
stamp affirmed), Strength Ombudsman (the 8 front-side-only refusals are logged as a refused-strength
docket, 7 of 8 already closed by the 13:49 fix), Wind Tunnel Engineer (§3: our replays are a
front-side-free superset — fidelity gap named, not papered over), Statistician (all counts from the
8/17 archive pull, N cited), Dashboard Curator (rows now carry `front_side_3m`/`front_side_tf` —
display owed), Historian (run 8/17, `date` cited in-session), Momentum Operator / Pit Crew: clean —
nothing ships, no deploy, no env, no restart (market open, NIVF position live).
**Doctrine-inversion sweep:** the inverted claim — "the 1-min value is the wrong one and the 3-min
context should govern" — is *not* refuted by code, only by `fastchart_2tf_rerun_20260817`
(1MIN −$382 vs 3MIN −$1,184 on the tick twin), which is a different detector family; hence the
3-min arm was built as a switch rather than deleted. The second inversion — "the self 10s aggregate
is the better 1-min chart than the broker M1" — is **open**, 31 disagreements say the two are not
interchangeable, and it is Marcos's call, not an auditor's.
