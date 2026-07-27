# OUTCOME PASS SPEC — retro-apply of the 7/26 reviews (Fable-authored 7/27)

**Purpose.** The nine 7/26 contradiction reviews ran the CONSISTENCY half only. This spec is the
OUTCOME half: replay the era's REAL trades through each mechanism and grade the result in dollars.
Authored by Fable in-session 7/27; executed by Opus; verdicts rendered by Fable in ONE session over
the finished evidence doc.

## Rules for the executing session (Opus) — binding

1. **Numbers and traces only. NO verdicts.** No "we should," no ranked fixes, no recommendations.
   Any conclusion that forms is written as `HYPOTHESIS:` + the query that would test it. The
   deliverable format has no slot for a kill or a ship.
2. **Every finding carries ONE named trade traced end-to-end** (ticker, date, entry/exit prices,
   the mechanism's decision at each step, dollar result). A finding without its trace is
   incomplete — Fable will bounce it. (feedback_dollars_not_r, feedback_sim_integrity)
3. **Dollars, not R,** through the real sizing chain. Report R only alongside dollars.
4. **Era discipline:** strategy queries use 7/13+ only; lane-level queries 7/14+ (entry_type stamp).
   Apply the runner-leg correction ledger `pnl_runner_leg_correction_20260726.json` to any P&L
   drawn from stored records ≤7/20. 7/27 PRE trades (−$624.50) are QUARANTINED — infrastructure
   losses, excluded from every mechanism grade; report them only in Q9.
5. **10s outranks 1-min** wherever both exist (feedback_lean_on_10s_data). A verdict-relevant
   sequencing fact derived from 1-min only gets tagged `resolution-limited`.
6. **Cohort honesty:** every query reports its n, its excluded rows, and WHY excluded. No silent
   cohort trimming. If a query is uncomputable from stored data, say so — an honest "uncomputable"
   is a finding (it feeds the recorder queue), not a failure.
7. Write everything to `data/killtests/OUTCOME_PASS_20260727.md`. Append raw per-row outputs as
   companion `.txt` files. Ledger the doc when done.

## Data sources
- Trade store via dashboard `/api/trades` (203 rows as of 7/27 10:49) + correction ledger.
- Decision log via `/api/decisions?ticker=X&limit=N` (8000 rows) — statuses include
  `filled`, `daygain_reject`, `chart_gate_allow`/`_deny`, `*_shadow_fire`, `triggered_*`,
  `premarket_shadow_entry`, `reentry_eligible`, `stale_price_fix`, `broke_not_flat`.
- 10s bars: Alpaca capture archive; 1-min bars: local + Railway ferry (2,792 ferried 7/27).
- Fields available on modern trade rows: `entry_type, planned_risk, risk_per_share, stop_loss,
  highest, partial_fills, size_clamp, day_gain_at_entry, entry_session, est_slippage,
  entry_vs_kev_level_pct, kev_level, entry_l1_spread, reclaim_subtype`.

---

## Q1 — EXITS (stop integrity)
**Q1a Blow-through census.** Every era trade with `stop_loss` + "Stop loss" exit: realized loss vs
planned_risk. Distribution of (realized−planned) in dollars; total excess; worst 5 named.
Split by entry_session and by lane. (Known partial answer: 33 trades / $442 — recompute, cite, extend.)
**Q1b Sub-3-min crater anatomy.** For the worst 10 blow-throughs, walk the 10s bars from stop-breach
to exit fill: how many seconds/dollars between "stop price touched" and "3-min close evaluated"?
This is the design input for the intrabar-floor fix — the crater speed profile.
**Q1c Wick-shakeout counterfactual (the other side).** Same era cohort: trades where price TOUCHED
the stop intrabar (10s low ≤ stop) but the 3-min close held above it — i.e., trades a naive
intrabar stop would have killed. What did they go on to do, in dollars? This is the cost side of
fix #1; without it the crater evidence is half a case.
**Q1d Banked-then-red census.** All era trades with non-empty partial_fills finishing net red:
n, dollars surrendered after first bank, per-lane. (Known: 4 / $63.75 — recompute + trace one.)
**Q1e Unbanked-peak census.** Era trades where `highest` implies ≥ +2R MFE with zero partials:
n, peak dollars unbanked, by lane and exit ladder. VEEE is the known specimen; find the class.
**Q1f Ladder-fit table.** For each lane × its ASSIGNED exit ladder: median MFE in R and in % —
does the ladder's first trigger sit below the lane's median peak? (hidden→%-ladder mismatch is
the known instance; measure every pairing, not just the known-bad one.)

## Q2 — SIZING & RISK
**Q2a Clamp-binding census.** Group era trades by `size_clamp` (risk / notional / volume /
min_1_share / volguard): n, total P&L, median realized risk-$ per group. The question the table
answers: which sizer is actually running the book, and does the binding clamp correlate with outcome?
**Q2b Tight-stop pathology.** Trades where risk_per_share < 1% of entry price (KIDZ class: stop
inside the noise): n, win rate, dollars. Include `entry_l1_spread / entry price` alongside —
HYPOTHESIS to test: stops tighter than the spread are structurally unfillable.
**Q2c Slippage tax.** Sum and distribution of est_slippage vs pnl, era-wide and per-lane. Name the
5 trades where slippage exceeded planned_risk.

## Q3 — ENTRY LANES (fast: ignition-10s, hidden_entry, vwap_reclaim, zone_flip)
**Q3a Lane P&L table 7/14+**, corrected dollars, n, median MFE/MAE, by entry_session. vwap_reclaim
rows 7/14–7/17 are pre-VWAP-fix: report but FLAG as invalid-cohort (settled 7/26).
**Q3b Day-gain-at-entry vs outcome, tape lanes.** Scatter/bucket `day_gain_at_entry` (bins:
>+15, +15..0, 0..−20, −20..−40, <−40) vs P&L for the floor-EXEMPT lanes. This is the KIDZ
question: does the exemption's admitted cohort have a cliff? SOBR (−23%, +$93.56) and KIDZ
(−64%, −$36.71) are the poles — fill in the middle. Also report `entry_vs_kev_level_pct` per bin.
**Q3c Ignition-10s early acceptance.** All ignition fills since 10s port (7/26+): fill-vs-peak
timing on 10s bars, dollars. Small n expected — report n honestly, no verdict.

## Q4 — ENTRY LANES (slow: flat_top, orb, ma_pullback)
**Q4a Fire-rate reality.** Fires vs fills vs P&L per lane 7/14+, corrected dollars. Which gate
eats each lane's fires (from decision-log reject statuses, counted per gate per lane)?
**Q4b Day-gain floor forward cohort.** Since 30→15 (7/26): fires admitted in the 15–30 band that
old floor would have blocked — n, outcomes so far. (Extends the n=17 canary cohort with real fills.)

## Q5 — GATES (chart gate + survivors)
**Q5a Chart-gate scorecard.** Era `chart_gate_allow` vs `chart_gate_deny` from the decision log:
for ALLOWED → realized P&L; for DENIED → counterfactual MFE from bars (mark resolution). The gate
is the only selection layer left — this is its report card in dollars.
**Q5b Bypass audit.** All `chart_gate_allow` rows with `reason: live_structure`, split by
`src: none` vs a real read. KIDZ exposed src:none = allowed-with-no-chart; count the class, P&L
of its fills, trace one besides KIDZ.
**Q5c Gate-purge counterfactual.** Since the 7/26 momentum/extension/daily-veto relaxations: fills
that the OLD gates would have blocked — n, dollars. The purge was doctrine (DRY_RUN learning);
this measures what the learning is costing/earning. Numbers only.

## Q6 — DISCOVERY (scanner / watchlist / read-list)
**Q6a Capital-priority audit.** Since `_entry_priority` shipped: when >1 candidate queued in the
same cycle, did the fill go to the Kev-sheet/Move% winner? Any displaced candidate's counterfactual.
**Q6b Read-spend audit.** Reads consumed by names below the 10k/bar liquidity gate (DCOY/DBGI/TGL
class): count per day since Alpaca migration — the dollar-free cost table for fix #0.
**Q6c Watchlist hit-rate.** Of era watchlist adds, how many produced a fill, and what did
non-watchlist fills (if any path exists) do? Uncomputable-if-unstamped is an acceptable answer.

## Q7 — RECORDER / DATA CAPTURE
**Q7a Field-completeness table** for the verdict-critical fields (stop_loss, planned_risk, highest,
partial_fills, day_gain_at_entry, entry_session) per week of the era. Every "uncomputable" from
Q1–Q6 lands here as a named recorder defect.
**Q7b Capture-gap census.** 10s archive: per-day per-symbol gap minutes during holdings. A gap
overlapping an open position is the blind-monitoring precondition (7/27's class) — count near-misses.

## Q8 — DASHBOARD / REPORTING
**Q8a Truth audit.** For 10 random era trades: dashboard-displayed P&L vs corrected-ledger P&L vs
raw store. Any row where the three disagree beyond rounding is a named finding.
(No outcome dollars to grade here beyond truthfulness — if Q8a is clean, say "clean, n=10" and stop.)

## Q9 — PREMARKET (quarantined; context only)
**Q9a** The 5 PRE trades: entry logic grade ONLY (was the reclaim signal valid on the bars that
existed?) separated from the custody loss. This tells us whether 04:00 entries are worth re-enabling
once sessions= is fixed, or whether PRE reclaims were bad trades anyway. Numbers + traces only.

---

## Deliverable shape (per finding)
```
FINDING <Qn.x>: <one-line factual statement>
  n=, cohort=, excluded= (and why)
  dollars: <total / median / worst>
  trace: <TICKER date> — <entry→mechanism decision→exit, step by step, $>
  resolution: <10s | 1-min | store-only>
  HYPOTHESIS (optional): <testable statement> + <the query/kill-test that would test it>
```
Fable renders all verdicts in one session over the finished doc. Nothing ships from this pass
directly; tonight's change-set is assembled AFTER verdicts.
