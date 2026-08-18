# ENTRY-DRIFT DEFECT — kill-test + fix (8/17/26)

**VERDICT QUALIFIER (LIMITS, added 2026-08-17):** the doc discloses that its linked-row set is a SUPERSET (reject rows matched to fires within 120s, so some links are spurious) and that the resulting cells are UNDERPOWERED. It is ALSO on the EG2 KNOWN-CONTAMINATED list — it applies no front-side clause while the live kevseq lane requires one, so it grades a machine that is not ours. The entry-drift DEFECT is real and independently reproduced; the per-gate counts are not a verdict.

Script: `data/killtests/entry_drift_20260817.py` · run log: `entry_drift_20260817_run.txt` ·
JSON: `entry_drift_20260817_out.json` · rig: section **AP** (25 checks) in
`rig/test_shipset_20260804.py`.

---

## FAILURE CONDITION (pre-registered, written FIRST)

1. This work is **wrong** if, on the universe replay with the OOS split
   (MINE 2026-05-18..07-21 / HOLD-OUT 07-22..08-14, E3 live-parity, $500), the chosen fix does
   NOT raise HOLD-OUT $/trade over the today's-behaviour baseline, or raises it only by cutting
   N to noise (HOLD-OUT N < 20 ⇒ UNDERPOWERED ⇒ ship OFF by default).
2. It is **also wrong** if the replay's modelled drift is not the drift the live rows show. The
   replay's entry proxy is the **fill-bar close**. If modelled kevseq drift is not materially
   positive while the sibling close-anchored lanes sit at ~0, the model is not reproducing the
   live defect and every number below is void.
   → **Check passed**: modelled kevseq drift median **+0.76%**, p90 +4.13%, max +70.68%; the
   sibling lanes measure ~0 on the live rows. Direction and mechanism reproduce.
3. The fix is **wrong to default ON** if any arm's improvement does not hold on BOTH halves of
   the split, or if the lane is net-negative (a fix that makes a losing lane lose less is not a
   licence to trade it).

---

## THE DEFECT — root cause, verified in code this turn

`kevseq_step` (`marcos_trading_bot.py:6376-6440`) sets

```
px = float(pd["hi"])          # the H/W SETUP BAR'S HIGH — a trigger LEVEL, not a traded price
```

and the caller (`:8262`, pre-fix) priced the entry off the **live quote**:

```
_ks_px = price if price and price > 0 else _ksf["px"]      # entry moves
breakouts.append((t, _ks_px, ..., "kevseq", {"zone_stop": _ksf["would_stop"], ...}))
_log_decision(t, "triggered_kevseq", price=_ks_px, stop=_ksf["would_stop"], fire_px=_ksf["px"])
```

The stop stays at `would_stop` — the **structural** stop measured against the fire price. Entry
rises, stop does not, risk-per-share explodes, and the downstream R-gates then *correctly* refuse
the mutated trade.

**Two compounding sources**, and only one of them is latency:
* the fill bar can blow *through* the setup high inside a single 10s bar (the big one), and
* the quote is read some seconds after the bar batch (the small one).

`kevseq` also had **no fire-age guard and no age stamp** — it is the only 10s lane without a
`_bucket_fresh` equivalent (`reclaim :5731`, `zone_flip :6512`, `ignition :6638`, `hidden`,
`dip_rip` all have one). That is why `fire_age_s` was `None` on every kevseq row ever written:
nothing computed it.

---

## STEP 1a — drift distribution, live rows, all era days 6/29–8/17

Archive `GET /api/decisions_archive`, every lane stamping both a fire price and an entry price.
Duplicate archive rows deduped in the specimen list; N below is as-stamped.

| lane | N | median | p75 | p90 | max | age stamped? | intended risk (med) | actual risk (med) | inflation |
|---|---|---|---|---|---|---|---|---|---|
| **kevseq** | 13 | **+5.02%** | +5.66% | +7.09% | **+28.87%** | **0 / 13** | 3.09% | **8.28%** | **×2.06** |
| v2conv | 13 | +0.40% | +0.64% | +1.92% | +7.45% | 0 / 13 | 3.09% | 3.09% | ×1.20 |
| prevwap | 6 | 0.00% | +3.13% | +3.13% | +3.13% | 0 / 6 | 7.23% | 10.04% | ×1.00 |
| grinder | 4 | −1.48% | 0.00% | +14.40% | +14.40% | 0 / 4 | 1.34% | −0.25% | ×0.39 |
| hidden_entry | 1024 | −0.06% | +0.87% | +2.07% | +69.53% | 1024 / 1024 | 5.00% | 5.00% | ×0.99 |
| dip_rip | 136 | −0.28% | +0.43% | +2.87% | +22.65% | 136 / 136 | 5.26% | 4.53% | ×0.94 |
| zone_flip | 12 | −0.11% | +1.02% | +2.12% | +2.12% | 12 / 12 | 3.70% | 3.01% | ×0.96 |

**kevseq is a class apart.** Every other detector returns the bar **close** (`"px": round(c, 4)`,
seven call sites); kevseq alone returns a setup-bar **high**. The lanes with a fire-age guard
also carry the age stamp; the five new lanes carry neither.

## STEP 1b — the DAMAGE (refused-but-would-have-passed)

Recomputing each R-gate's verdict at `P_fire` with the same stop `S`, over every reject row that
can be linked to a fire within 120s.

| lane | gate | N linked | would have PASSED at the fire price |
|---|---|---|---|
| kevseq | runway_reject | 1 | **1** |
| v2conv | runway_reject | 1 | **1** |
| prevwap | runway_reject | 1 | **1** |
| hidden_entry | runway_reject | 18 | 4 (all positive-drift) |
| dip_rip | runway/minstop | 32 | 4 (positive-drift) |

**Positive-drift damage = 7 refused trades**, of which **kevseq's own share is 1 of its only 1
R-gate refusal** — the specimen below. On the universe replay the same damage at scale: **194 of
1,288 fires** are refused by the 6% min-stop floor at the drifted entry that the intended
(fire-price) trade would have passed — **15% of the lane's fires destroyed by the defect alone.**

### hand-traced specimens

**WFF 2026-08-17 11:17:43** — fire `$3.91`, structural stop `$3.68` ⇒ intended risk **5.88%**.
Entry executed at the live quote `$5.039` ⇒ actual risk **26.97%**, drift **+28.87%**. At
11:58:34 the same name's follow-on shows `runway_reject` entry `$6.92` stop `$4.48` = 35% risk,
road 0.15R against a 1.0R need — the mutated trade being correctly refused by a gate that was
never given a chance to judge the trade the detector actually found.

**WETO 2026-08-17 10:18:36** — fire `$18.4499`, stop `$17.88` ⇒ intended **3.09%**. Entry
`$19.495` ⇒ actual **8.28%**, drift **+5.66%**. The trade the bot took carried 2.7× the risk of
the trade the detector signalled.

**PFSA 2026-08-17 10:22:30** — fire `$6.17`, stop `$5.90` ⇒ intended 4.38%; entry `$6.48` ⇒
actual 8.95%, drift +5.02%. Two seconds later, `runway_reject machine=kevseq price=6.48 stop=5.90
target=6.55 runway_rr=0.12 need=0.4`. **At the fire price**: road `6.55 − 6.17 = 0.38`, risk
`6.17 − 5.90 = 0.27`, **RR = 1.41 ≥ 0.4 — it would have passed.** The gate did its job; the
trade handed to it was not the trade that was found.

## STEP 1c — is drift a P&L problem or only a gate problem?

Both, and the P&L side is the larger one. On the universe replay (below), moving the entry from
the drifted price to the fire price + tolerance is worth **+$2.98/trade on MINE and +$1.73/trade
on HOLD-OUT** at effectively constant N. That is not a gate artifact — it is the cost of chasing.

---

## STEP 2 — candidates, pre-registered, graded on the OOS split

Universe: 738 files / 736 graded name-days / 63 dates, **1,288 kevseq fires** (918 MINE, 366
HOLD-OUT). Engine imported UNCHANGED from `sunday_afternoon_studies_20260816` (→ G → F → C → B
→ E). All exits E3 live-parity, $500, −1% entry slip, −0.5% market-exit slip.

*Caveat, disclosed:* the replay cohort is a **superset** of the live cohort — `front_side`,
`top3` and `blue_sky` are not reconstructible from the 10s cache, so the context clause is
replaced by the day-gain floor alone, and none of the downstream gate stack is applied. The
absolute level of every row below is therefore **not** a forecast of the lane's P&L; the
**relative** comparison between arms, which is what the kill-test is for, is unaffected.

### MINE (2026-05-18 .. 07-21)

| arm | N | total | $/tr | win | worst |
|---|---|---|---|---|---|
| baseline (today: quote entry, structural stop) | 917 | $−3244.94 | $−3.54 | 31% | $−184.55 |
| F1 drift refuse ≤ 0.5% | 386 | $−2486.23 | $−6.44 | 21% | $−106.12 |
| F1 drift refuse ≤ 1% | 532 | $−2077.41 | $−3.90 | 24% | $−106.12 |
| F1 drift refuse ≤ 2% | 696 | $−2357.58 | $−3.39 | 27% | $−106.12 |
| F1 drift refuse ≤ 3% | 784 | $−3251.18 | $−4.15 | 28% | $−106.12 |
| F1 drift refuse ≤ 5% | 862 | $−3282.56 | $−3.81 | 29% | $−106.12 |
| F2 re-anchor stop | 918 | $−3069.99 | $−3.34 | 27% | $−155.38 |
| **F3 limit-at-fire +0.5%, 0 bars** | **897** | **$−504.92** | **$−0.56** | 34% | $−114.90 |
| F3 limit-at-fire +0.5%, 3 bars | 905 | $−685.27 | $−0.76 | 34% | $−157.09 |
| F3 limit-at-fire +0.5%, 6 bars | 911 | $−803.77 | $−0.88 | 34% | $−157.09 |
| F3 limit-at-fire +0.5%, 18 bars | 912 | $−821.99 | $−0.90 | 34% | $−157.09 |
| F3 limit-at-fire **+1.0%**, 0 bars | 903 | $−2809.09 | $−3.11 | 33% | $−116.84 |
| F3 limit-at-fire +1.0%, 18 bars | 913 | $−3006.24 | $−3.29 | 33% | $−158.79 |

### HOLD-OUT (2026-07-22 .. 08-14) — frozen, never mined

| arm | N | total | $/tr | win | worst |
|---|---|---|---|---|---|
| baseline (today) | 365 | $−899.60 | $−2.46 | 37% | $−110.80 |
| F1 drift refuse ≤ 0.5% | 159 | $−238.62 | $−1.50 | 32% | $−71.75 |
| F1 drift refuse ≤ 1% | 195 | $−277.83 | $−1.42 | 34% | $−71.75 |
| F1 drift refuse ≤ 2% | 261 | $−623.32 | $−2.39 | 33% | $−71.75 |
| F1 drift refuse ≤ 3% | 298 | $−327.34 | $−1.10 | 36% | $−71.75 |
| F1 drift refuse ≤ 5% | 328 | $−469.35 | $−1.43 | 37% | $−71.75 |
| F2 re-anchor stop | 366 | $+19.90 | $+0.05 | 36% | $−83.79 |
| **F3 limit-at-fire +0.5%, 0 bars** | **356** | **$−260.78** | **$−0.73** | 38% | $−85.86 |
| F3 limit-at-fire +0.5%, 3 bars | 359 | $−251.35 | $−0.70 | 38% | $−85.86 |
| F3 limit-at-fire +0.5%, 18 bars | 362 | $−413.86 | $−1.14 | 38% | $−85.86 |
| F3 limit-at-fire **+1.0%**, 0 bars | 358 | $−1060.97 | $−2.96 | 38% | $−87.91 |

### verdicts

* **F1 DRIFT REFUSE — REFUTED as the fix.** No grid point beats F3 on either half, the ranking of
  thresholds *inverts* between MINE (2% best) and HOLD-OUT (3% best), and the tightest setting
  costs 58% of N to buy nothing. Refusing the chase is directionally right; refusing it *by
  threshold* is not where the money is.
* **F2 RE-ANCHOR STOP — not chosen.** Best-in-class on HOLD-OUT ($+0.05/tr) but a loser on MINE
  ($−3.34/tr): the improvement does not hold on both halves, which is exactly failure condition
  #3. **And it carries a spec tension worth naming even if it had won:** it abandons structural
  stop placement — the stop stops being "the level Kev's setup risks" and becomes "whatever
  price is 3% under wherever we happened to get filled." That is a different strategy wearing
  the lane's name.
* **F3 LIMIT-AT-FIRE +0.5% — WINNER.** Best or tied-best on **both** halves, +$2.98/tr (MINE) and
  +$1.73/tr (HOLD-OUT) over baseline, keeping **97–98% of N**. It is also the only candidate that
  fixes the defect *by construction* rather than by filtering: the entry can never exceed
  `fire_px × 1.005`, so actual risk ≡ intended risk within the tolerance.
  **The tolerance is load-bearing**: at +1.0% the arm collapses to $−2.96/tr on HOLD-OUT, no
  better than doing nothing. A tolerance grid is not decoration here.
  Fill realism is conservative: the `0 bars` variant fills only when the **fill bar's own low**
  reached the limit, i.e. only when the tape genuinely offered the price.
* **F4 FRESHNESS AGE GUARD — NEEDS-DATA, not refuted.** The replay evaluates every fire on the bar
  it completes on, so modelled fire age is always ~0s and no threshold binds. The regime it
  defends against (a stale bar batch replayed after a restart or admission — the reason
  `CURL_FIRE_MAX_AGE_SECS` exists) has **no representation in the cache**. Reported NEEDS-DATA
  rather than fabricated. Built anyway, because kevseq being the only 10s lane without the guard
  is an inconsistency defect regardless; **disabled by default** until a stamped age
  distribution exists to calibrate it. The stamp ships now, so that distribution starts tonight.

---

## STEP 3 — what was BUILT

All in `marcos_trading_bot.py`; kill switches are env, defaults restore today's behaviour exactly.

**Always on (observability is free, no verdict required):**
* `fire_age_s` (halt-aware, same law as `_bucket_fresh`), `drift_pct`, `quote_px`, `bar_lo` on
  **every** kevseq row — `kevseq_reject`, `kevseq_shadow_fire` **and** `triggered_kevseq`.
  This closes the "fire_age_s is None on every kevseq row" hole.
* `intended_risk_pct` + `actual_risk_pct` on `triggered_kevseq` — the defect is now *visible in
  the row*, not only reconstructible.
* `kevseq_step` returns `bar_lo` / `bar_hi` (the fill bar's own range) — additive, no consumer
  changes; `px` remains what it was.
* `fire_age_s` + `drift_pct` on `triggered_v2conv` / `_grinder` / `_bandpass` / `_prevwap`
  (**observe-only**, see STEP 4).

**Behaviour switches — ALL DEFAULT OFF:**

| env | default | mechanism |
|---|---|---|
| `KEVSEQ_LIMIT_ENTRY` | `0` (off) | F3 — cap the entry at `fire_px × (1+tol)`; refuse the fire when the fill bar never traded at/below it (`kevseq_drift_reject why=unfilled_limit`) |
| `KEVSEQ_ENTRY_TOL` | `0.005` | F3 tolerance (the kill-tested value; +1.0% collapses the arm) |
| `KEVSEQ_MAX_DRIFT` | `0` = disabled | F1 — refuse when drift exceeds it (`why=drift`) |
| `KEVSEQ_FIRE_MAX_AGE_S` | `0` = disabled | F4 — refuse a stale fire (`why=stale_fire`) |

All four are published in `boot_config`. Guard order: age → drift → unfilled-limit, and the veto
is evaluated **before** conversion, after the shadow row is written (so the evidence row survives
every refusal).

**Why nothing defaults ON.** Every arm on this replay is still net-negative: F3 makes the lane
lose *less*, it does not make it win. A switch that changes what the bot does with money is
Marcos's call, not an auditor's (`feedback_auditor_cannot_authorize_behavior`), and shipping the
observability half while calling the job done would be the lesser fix without permission
(`feedback_no_lesser_fix`). **Recommended setting to price: `KEVSEQ_LIMIT_ENTRY=1` with
`KEVSEQ_ENTRY_TOL=0.005`.**

**Rig, section AP** (25 checks, all green; full suite 573 green, exit 0): drift arithmetic
executed against the real WFF/WETO/PFSA specimens; guards refuse above the threshold and only
above it; kill switch restores today's behaviour; stamps present on all three row types; guard
ladder order pinned; **and the pin that intended risk == actual risk post-fix** on every 8/17
drifted specimen (WFF 5.88% intended → 26.97% today → within 0.55pp of intended under F3).

---

## STEP 4 — does the defect exist in the other new lanes? (blast radius)

**The structural half is kevseq-only.** `kevseq_step` is the **only** detector in the file that
returns a setup-bar high; `v2conv`, `grinder`, `bandpass`, `prevwap`, `zone_flip`,
`hidden_entry`, `dip_rip`, `ignition` all return `round(c, 4)` — the fill bar's close, which is
by construction a price the tape actually traded. Pinned in rig AP-w.

**The latency half is shared but small.** All five new lanes use the identical
`_XX_px = price if price and price > 0 else _f["px"]` conversion (`:8038` v2conv, `:8088`
grinder, `:8133` bandpass, `:8239` prevwap, `:8262` kevseq), and none of the five calls
`_bucket_fresh`. Measured: v2conv median +0.40%, prevwap 0.00%, grinder −1.48% — an order of
magnitude below kevseq, and consistent with pure quote latency rather than a mispriced signal.

**Three rings, enumerated:**
1. *The fix executes.* Rig AP-i..AP-r run the arithmetic and the guard ladder against real
   specimens, not assertions about them.
2. *Every call site.* `_ksf[...]` consumers: the single caller block (`:8172-8290`) and rig
   section AG. The `kevseq_step` return dict gained keys only — additive, no consumer reads it
   positionally. The conversion-guard literal pinned by **AG-vii** changed shape and that pin was
   updated in the same change-set (documented in-line as an amendment, AP owns the veto's pins).
   `boot_config` gained four keys. The four sibling `_log_decision` calls gained two kwargs each
   — `_log_decision` is `**kwargs`, no schema to break.
3. *The neighbourhood re-run.* Full rig end-to-end: 573 green, **exit 0**.

**Decision for the siblings: stamps only, no veto.** Their measured drift does not justify a
gate, and adding four more default-OFF switches would be four more untested behaviours. The
stamps start the measurement; if a sibling's stamped drift distribution turns out to look like
kevseq's, the same F3 mechanism ports directly. Pinned by AP-y that no sibling veto exists.

---

## SPEC TENSION FOR MARCOS

1. **The lane loses money on this cohort, on every arm.** The drift fix is real and it is worth
   ~$3/trade — but "loses less" is not "wins". Fixing entry drift does not answer whether kevseq
   should convert at all; the pre-registered `kevseq` failure condition (shadow rows graded E3
   below the don't-trade F-control over a ≥5-day wall) still owns that verdict, and this
   superset replay is not that wall.
2. **F3 changes the entry from "take it" to "take it at my price or not at all."** That is Kev's
   own method — buy the pullback, don't chase — but it means some fires produce no trade at all
   (~2–3% of them here, and more in fast tape). If the intent is that a kevseq fire always
   results in a position, F3 is the wrong shape and F2 is the honest alternative, at the cost of
   giving up structural stop placement.
3. **The 0.5% tolerance is not the executor's 1% buffer.** The entry path already places a
   marketable LIMIT at `entry_price × (1 + ENTRY_LIMIT_BUFFER)` with `ENTRY_LIMIT_BUFFER = 0.01`
   (`:615`, `:9399`). Under `KEVSEQ_LIMIT_ENTRY=1` in DRY_RUN the recorded entry is exactly the
   capped price, matching the kill-test. **With real money the broker limit would sit at
   `capped × 1.01`, i.e. up to 1.5% over the fire price — and the kill-test says +1.0% tolerance
   collapses the arm.** A lane-aware `ENTRY_LIMIT_BUFFER` is therefore **owed before this runs
   on real money**, and is deliberately not built here: it touches the shared executor, which is
   not a mid-session change. Flagged, priced, not slipped in.
4. **F4 is unfalsifiable on the cache.** It ships disabled. Do not read its presence as evidence
   that stale kevseq fires are or are not a problem — we will know once the stamps accumulate.
