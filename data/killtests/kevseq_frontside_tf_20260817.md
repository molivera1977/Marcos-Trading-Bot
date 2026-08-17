# KEVSEQ FRONT-SIDE — 8/17 — VERDICT: **the 3-MIN premise was FALSE (refuted against HEAD). The real defect is that our two 1-MINUTE sources run on DIFFERENT CLOCKS — traded-minutes vs wall-clock minutes — and on a thin name the caller's "1-minute EMA20" spans up to 9.7 HOURS.**

## 0. FAILURE CONDITION (written FIRST)
This work is WRONG if: (1) a SETUP_TF_MIN value can reach `_ks_ctx["front_side"]`; (2) a kevseq row
can be written without the source stamps (`front_side_src` / `_caller` / `_self` / `_self_n` /
`_3m`); (3) fail-closed moves — a short 1-min history must still give `None` -> `front_side_unknown`
-> refusal, never a fabricated value; (4) the disagree canary stops firing; (5) precedence changes
without Marcos's word. Rig section **TF** (16 pins) tests all five. Full rig exit 0.

## 1. THE PREMISE WAS WRONG — and the record says so first
The task was handed over as: *"the caller computes `_ce9/_ce20` from
`aggregate_bars(cache[t]["full_bars"], SETUP_TF_MIN)` with SETUP_TF_MIN=3, so kevseq has been gated
on a 3-MINUTE front side since 8/16."* **That is false**, verified against HEAD independently by me
and by the coordinator, who issued the correction mid-task. The kevseq context block reads:

```
_ks_1m = (bars or [])[:-1]                      # bars = cache[t]["bars"] = the M1 fetch
if len(_ks_1m) >= EMA20_PERIOD + 2:
    _ks_e9, _ks_e20 = calculate_ema9(_ks_1m), calculate_ema20(_ks_1m)
    _ks_ctx["front_side"] = bool(_ks_e9 > _ks_e20 > 0)
    _ks_fs_src, _ks_fs_n = "caller_1m", len(_ks_1m)      # <- stamped "caller_1m" all along
```
`SETUP_TF_MIN` appears nowhere in kevseq's ctx block. The `_ce9/_ce20` 3-min aggregate sits ~200
lines below and feeds dip_rip / zone_flip / reclaim / flat-top — lanes whose own spec IS the 3-min
setup chart. The claim was a variable-name match, not a read. **There was no timeframe defect and
no timeframe cost.** Consequently **no behaviour switch was shipped** for it.

## 2. THE REAL DIAGNOSIS — same timeframe, different clocks
Reconstructed from the SIP tape for **all 31** canary rows
(`data/killtests/kevseq_frontside_sources_20260817.py`, output `_run.txt`).
Fidelity check first: modelling the caller as *RTH-only, last 50 M1 bars, drop the in-progress one*
reproduces **31/31** logged caller signs — the model is exact.

### 2a. Side-by-side EMAs (specimens; full 31 in the run file)
| time | sym | source | n | window (ET) | EMA9 | EMA20 | front side |
|---|---|---|---|---|---|---|---|
| 13:50 | RPGL | caller | 49 | 12:54–13:47 | 2.1065 | 2.1081 | **False** (−0.08%) |
| | | self | 63 | 12:41–13:48 | 2.1112 | 2.1104 | **True** (+0.04%) |
| 13:50 | IVF | caller | 49 | 13:00–13:48 | 1.7158 | 1.7192 | **False** (−0.19%) |
| | | self | 40 | 13:10–13:49 | 1.7206 | 1.7194 | **True** (+0.07%) |
| 13:50 | TRUG | caller | 49 | 13:00–13:48 | 1.5737 | 1.5738 | **False** (−0.00%) |
| | | self | 41 | 13:09–13:49 | 1.5770 | 1.5756 | **True** (+0.09%) |
| 13:50 | RBNE | caller | 48 | **09:33–13:36 (243 min)** | 2.7606 | 2.7566 | **True** (+0.15%) |
| | | self | 81 | 07:55–13:39 (premarket included) | — | — | **False** |
| 13:58 | PFSA | caller | 49 | 12:56–13:54 | 4.3238 | 4.3676 | **False** (−1.00%) |
| | | self | 69 | 12:37–13:55 | 4.3110 | 4.3553 | (logged True; knife-edge) |

### 2b. THE MECHANISM (the answer)
| sym | SIP 1-min bars, ALL DAY | max `self_n` logged | wall-clock span of the caller's 49-bar window |
|---|---|---|---|
| UUU | 54 | **155** | **584 min = 9.7 hours** |
| RBNE | 67 | 87 | 233–260 min |
| FXHO | 73 | 95 | 183 min |
| PFSA | 240 | 69 | 58 min |
| RPGL | 236 | 64 | 53 min |
| DFSC | 560 | 59 | 52 min |
| CDTG | 347 | 53 | 49 min |
| YYAI | 325 | 53 | 58 min |
| TRUG | 656 | 48 | 48 min |
| IVF | 646 | 40 | 48 min |

- **caller = a TRADED-MINUTE grid.** The M1 REST fetch returns only minutes in which a trade
  printed, capped at 50 bars, RTH-filtered. On a thin name those 49 "1-minute bars" reach back
  **hours**: UUU's window is 9.7 hours of wall clock; RBNE's is ~4 hours. Its "EMA20" is a
  multi-hour trend wearing a 1-minute label — and it is *stale by construction* exactly on the
  quiet names, i.e. it cannot see the last 20 real minutes at all.
- **self = a CONTIGUOUS WALL-CLOCK minute grid.** `kevseq_feed_1m` buckets the fed 10s stream, so
  a quiet minute still produces a bar. Proof: UUU held **155** minute buckets on a day whose entire
  SIP tape contains **54** traded minutes; RBNE 87 vs 67. Those extra buckets are real elapsed
  minutes with no prints. It is also day-wide (premarket included: RBNE's window starts 07:55).
  This is why my SIP-based reconstruction of *self* matches only 11/31 — SIP has no bar to rebuild
  the quiet minutes with. That mismatch **is** the evidence, not a modelling failure.
- **On liquid names the two clocks coincide** (span ≈ bar count: IVF 48/49, TRUG 48/49, CDTG 49).
  There the residual disagreements are pure knife-edge: |EMA9−EMA20| ≤ 0.2% on every such row
  (RPGL −0.08% vs +0.04%, TRUG −0.00% vs +0.09%). Different start bar → different SMA seed →
  sign flips on noise. Not a defect in either source; a coin toss at the crossover.
- Secondary contributor, isolated: **session span**. Every RBNE disagreement has the self window
  opening at 07:55 (premarket) while the caller is RTH-only. Premarket inclusion is a separate
  policy question ([[feedback_rth_official_pre_separate]]).
- Ruled out by the data: partial-bucket handling and the in-progress minute (both sources drop the
  forming bar — caller via `[:-1]`, self by appending only on bucket advance).

### 2c. WHICH SOURCE IS MORE FAITHFUL — and why, with numbers
**The self 10s→1m aggregate is more faithful to a real 1-minute chart**, decisively on the names
this lane exists to trade:
1. A chart's 20-bar EMA covers **20 minutes**. Self's does. The caller's covers 20 *traded* minutes
   = 20 minutes on IVF/TRUG but **~4 hours on RBNE and ~9.7 hours on UUU**. A front-side read that
   lags by hours cannot gate a lane whose whole thesis is a 3-minute B→H/W sequence.
2. The caller is **hard-capped at 50 bars** and therefore cannot be lengthened; the aggregate grows
   with the session (40→155 buckets observed today).
3. The caller is blind for the first ~22 minutes of a fresh board name — the window kevseq exists
   for. That hole is what `KEVSEQ_SELF_FRONTSIDE` (13:49 today) already patched, and it was patched
   *with this same aggregate*: we already trust it as the fallback.
Where the caller is better: it is broker/exchange truth on **priced** bars (no synthetic flat
minutes), and it is RTH-clean. Self's flat carry on quiet minutes biases both EMAs toward the last
print, which compresses the 9/20 spread — visible in the ≤0.2% knife-edge rows.

## 3. PROPOSAL (not shipped — money decision, Marcos's call)
Make **self (10s→1m contiguous aggregate) the primary** front-side source for kevseq, with the
caller M1 as the fallback when the aggregate is short — i.e. exactly today's precedence, inverted.
Grade it before shipping: with both values now stamped on every row, one session of tape answers
whether the flips are concentrated in thin names (where self is right by construction) or in
knife-edge liquid rows (where neither is right and the gate is just noisy). Do **not** ship on
today's 31 rows: on the caller side **27 of 31** rows sit at |EMA9−EMA20| ≤ 0.25% (only the four
PFSA rows exceed it, at ~1.0%) — this is a noise-dominated sample, not an edge sample.
Cheaper variant worth pricing alongside: keep the caller primary but **raise its fetch count** and
**stamp its wall-clock span**, refusing the front-side read when the span exceeds N minutes
(a staleness floor rather than a source swap).

## 4. ARTIFACT-REPLICATION AUDIT — which studies used which front side
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

## 5. TODAY'S COST (8/17 archive, 13,703 rows)
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

## 6. WHAT WAS BUILT — KEPT vs REMOVED (behaviour UNCHANGED)
**KEPT (pure observability, zero behaviour):**
1. `front_side_3m` — the SETUP_TF_MIN counterfactual, computed and stamped, reaching ctx never.
   Kept because it costs nothing and it is now the only way to grade the 3-min question with data
   instead of assertion.
2. `front_side_caller` + `front_side_self` + `front_side_self_n` + `front_side_tf=1` on **every**
   kevseq row (reject, shadow fire, triggered) — both 1-min values side by side, so the source
   decision in §3 can be graded from the archive rather than re-derived from SIP each time.
3. Disagree canary enriched with the 3-min value; `front_side_src` unchanged and always logged.
4. `boot_config` publishes `setup_tf_min`.
5. Corrected spec header at the kevseq block + this doc.
6. `data/killtests/kevseq_frontside_sources_20260817.py` (+ `_run.txt`) — the reconstruction that
   produced §2, re-runnable.

**REMOVED (built during the false premise, deleted once it was refuted):**
- `KEVSEQ_FRONTSIDE_1M` env switch and its 3-min-governing branch. It was a behaviour switch for a
  defect that does not exist = config debt, and a live env var is a standing invitation to arm the
  offline-worse arm by accident. Rig pin **TF-e** now asserts the name is absent from the source.

**Precedence, fail-closed semantics, gates, and every dollar path are byte-identical to HEAD.**

## 7. OTHER-LANE SPEC-vs-IMPLEMENTATION AUDIT (three rings, ring 2 — reported, NOT changed)
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

## 8. Officers
Hidden Entry Architect (lead; kevseq is his lane), Systems Quant (does the code compute what its
name claims — the timeframe allegation did not survive the read; the CLOCK defect did survive it),
Feed Engineer (the M1 REST fetch returns traded minutes only and is count-capped — a vendor
constraint now on the ledger; the second time a bar-source shape has surprised a detector), Blast Radius Auditor (ring 2 lane
census above; no behaviour change to review), Side Marshal (front-side timeframe = his file; 1-min
stamp affirmed), Strength Ombudsman (the 8 front-side-only refusals are logged as a refused-strength
docket, 7 of 8 already closed by the 13:49 fix), Wind Tunnel Engineer (§3: our replays are a
front-side-free superset — fidelity gap named, not papered over), Statistician (all counts from the
8/17 archive pull, N cited), Dashboard Curator (rows now carry `front_side_3m`/`front_side_tf` —
display owed), Historian (run 8/17, `date` cited in-session), Momentum Operator / Pit Crew: clean —
nothing ships, no deploy, no env, no restart (market open, NIVF position live).
**Doctrine-inversion sweep:** (a) "the 3-min context should govern after all" — not refuted by
code, only by `fastchart_2tf_rerun_20260817` (1MIN −$382 vs 3MIN −$1,184), a different detector
family; hence the value is STAMPED so it stays gradeable, but no switch was left behind. (b) "the
caller M1 is the better chart and self is the synthetic imposter" — genuinely arguable on liquid
names (self's flat carry compresses the spread) and it is why §3 is a PROPOSAL, not a ship. (c)
"the gate is just noise and should be dropped" — 27 of 31 disagreements sit inside 0.25%; that
question belongs to the Strength Ombudsman with a graded cohort, not to this commit.
[[feedback_skepticism_needs_verification_too]]: the REFUTED verdict in §1 owed a named check — it
is the HEAD read in §1 plus the 31/31 caller reconstruction in §2.
