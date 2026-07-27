# OUTCOME PASS — evidence doc (Opus, 7/27, 11:09–11:40 EDT)

Executed per `OUTCOME_PASS_SPEC_20260727.md`. **Evidence only — no verdicts.** Every conclusion
that formed is written as `HYPOTHESIS` + the query that would test it. Raw outputs in companion
files `outcome_pass_20260727_q*.txt`. No writes to any live service; read-only throughout.

## Cohort & provenance (established first, applies to everything below)

- **`/api/trades` already serves CORRECTED P&L.** Verified against the runner-leg ledger: all 36
  materially-corrected rows match `corrected`, **zero** match `stored`. Re-applying the ledger is a
  no-op — and would be a double-correction if done naively. (n=193 ledger entries, 36 material,
  all dated 7/14–7/20.)
- **Era 7/13+ ex-PRE: n=144, −$205.34.** 7/27 PRE cohort quarantined: n=5, −$624.50 (matches the
  known incident figure exactly). Full book n=203, −$788.20.
- **Decision log is capped at 8000 rows = 7/23 → 7/27 only (5 sessions).** Everything in Q4/Q5/Q6
  is that window, not the era. Earlier decision rows are not retrievable from this endpoint.
- **10s bars are unreachable from this machine.** Alpaca REST rejects `10Sec`/`30Sec`; the 10s
  archive lives only on the capture service at `ALP_CAPTURE_URL = http://alapaca-…` (private
  Railway network). All bar work below is **1-min, tagged `resolution-limited`** per spec rule 5.
- Verified in passing: `ENTRY_OPEN_ET = 09:30` on Railway (premarket entries disabled, as recorded).

---

## Q1 — EXITS

### FINDING Q1a: 71% of era stop-exits exited below their stop price.
- n=51 (era 7/13+, ex-PRE, `exit_reason='Stop loss'`, has `stop_loss`+`planned_risk`). Excluded: 0.
- **36/51 = 71% exited below the stop price.** Price-excess `(stop−exit)×shares` = **$441.54**.
- **37/51 = 73% realized a loss worse than `planned_risk`.** Dollars beyond plan = **$440.84**.
- **Median realized loss on the stop cohort = 1.26R** (plan is 1.00R).
- By lane (n / blew / $ beyond plan): ignition 29/22/$186.61 · vwap_reclaim 10/7/$102.79 ·
  zone_flip 1/1/$89.78 · unstamped 6/4/$26.76 · ma_pullback 1/1/$25.53 · hidden_entry 1/1/$9.37 ·
  **flat_top 3/0/$0.00**.
- Note: the previously-circulated "25%" figure was a share of *all* era trades; as a share of the
  cohort the mechanism actually governs, it is 71%.

**trace — LGHL 2026-07-27 zone_flip:** entry $1.9800, stop $1.8700, planned risk $29.92 (285 sh).
Exit $1.5500 → realized **−$119.70 = 4.00R on a 1R plan**, $89.78 beyond plan. Worst single row.

### FINDING Q1b: exit lag is measurable only for 8 trades, and only at 1-min resolution.
- The trade store has **no entry timestamp** (see Q7a). Entry time is recoverable only from the
  decision log's `filled` rows → 7/23–7/27, n=10 after joining, of which 2 are join-contaminated.
- Lag from first 1-min bar breaching the stop to the recorded exit, for the clean rows:
  LVWR(7/24) 7 min · JEM(7/24) 4 min · DFNS 20 min · LVWR(7/27) 19 min · KIDZ 6 min.
- BIYA and LGHL rows are **contaminated**: both tickers traded twice on 7/27 (a PRE leg and an RTH
  leg) and my `(date,ticker)` join collapsed them. Those two rows are void; see the join audit file.

### FINDING Q1c: the wick-shakeout counterfactual is n=2 and worth −$2.55 — at 1-min resolution.
The cost side of an intrabar stop. Trades whose 1-min low touched the stop but which did **not**
exit on the stop:
- **LVWR 2026-07-24 flat_top** — stop $1.5019 touched 15:51Z (low $1.4800) → actual exit HEALTH FOLD, **−$0.26**
- **DFNS 2026-07-27 zone_flip** — stop $6.4400 touched 13:36Z (low $6.2600) → actual exit Trailing stop, **−$2.29**
- Rejected from the count: BIYA/JZXN (join-contaminated or quarantined PRE).
- **`resolution-limited` and cohort-limited (n=2 from a 5-day window).** This is the query the
  stop-fix design most needs and it is currently the weakest-powered query in the pass.

**HYPOTHESIS Q1c-H1:** an intrabar stop's shakeout cost is small relative to its crater saving.
**Test:** re-run Q1c over the full era at 10s resolution — requires (a) entry timestamps stamped
on trade rows and (b) capture-service bar access from the analysis host. Both are blockers, not
work items.

### FINDING Q1d: banked-then-red is n=4 / −$7.98 net — but peak-to-realized surrender across all banked trades is $2,083.42.
- Cohort n=112 (era ex-PRE with `partial_fills` present; 32 pre-field rows excluded).
- 50 trades banked ≥1 partial. **4 finished net red, totalling −$7.98**: CLRO(−$0.31),
  JLHL(−$5.12), LVWR(−$0.26), DFNS(−$2.29). *The previously-circulated $63.75 is not reproduced by
  this query; it appears to have measured something else.*
- **Peak-to-realized surrender across all 50 banked trades: $2,083.42.** Top: ZYBT $346.42 ·
  CPHI $289.46 · BIYA $115.87 · JLHL $103.38 · YYGH $84.29 · ADVB $82.71 · VEEE $77.10 · LEDS $76.58.

**trace — DFNS 2026-07-27 zone_flip:** entry $6.7100, high $7.1899, banked 55 sh @ $7.04, exit
$6.3400 on trailing stop → net **−$2.29**. Banked once, still finished red.

### FINDING Q1e: the "peaked ≥2R with zero banked" class is EMPTY in closed era trades.
- n=**0** at ≥2R. Relaxed: n=1 at ≥1.5R (LVWR 7/27 hidden_entry, peak +$48.60 = 1.62R → realized
  −$39.29); n=2 at ≥1.0R (adds VRAX 7/16, peak +$8.38 → −$10.00).
- The VEEE specimen cited earlier is **not** in this class: VEEE 7/27 is a *quarantined PRE* trade
  (vwap_reclaim, −$99.47). Any still-open VEEE position is by definition not in the closed store.
- Mechanically consistent with the ladder banking at 1R — a trade reaching 2R generally banks first.

### FINDING Q1f: not computed. Requires MFE-vs-ladder-trigger per lane, which needs entry timestamps
(Q7a) to reconstruct the intra-trade path. Recorded as blocked, not as clean.

---

## Q2 — SIZING & RISK

### FINDING Q2a: `size_clamp` exists on 5 of 144 era rows — the census is not yet possible.
- Field shipped 7/26. All 5 rows are 7/27: `risk` n=4 (−$129.24), `notional` n=1 (KIDZ, −$36.71).
- No inference available at this n. Recorded so the field is known to be live and accruing.

### FINDING Q2b: 23 era trades set a stop TIGHTER than the L1 spread.
- Cohort n=138 (has `risk_per_share`+`entry`).
- `risk_per_share < entry_l1_spread`: **n=23, −$95.33, 12/23 winners.** Worst: HPAI(−$91.26),
  KIDZ(−$36.71), VMAR(−$23.25), QNCX(−$15.07), INBS(−$12.17).
- Stricter cut `risk_per_share < 1% of entry`: only n=2 (VMAR, INUV).
- Note the 12/23 win rate — this cohort is **not** uniformly bad; the dollar loss is concentrated
  in HPAI and KIDZ.

**trace — KIDZ 2026-07-27 vwap_reclaim:** entry $0.5400, stop $0.5245, `risk_per_share` $0.0146
against an L1 spread of $0.0276 — **the stop was inside the spread**. Risk sizing wanted more than
$1,000 of stock, so `size_clamp='notional'` set the size: 1,854 sh / $999.49. `est_slippage`
$51.17 vs `planned_risk` $27.07. Exit $0.5200 (below the $0.5245 stop) → **−$36.71 = 1.36R**.

### FINDING Q2c: est_slippage across the era is $1,206.19 — 5.9× the era's net P&L of −$205.34.
- n=138. **23 trades where slippage exceeded planned_risk**: KIDZ $51.17 vs $27.07 · HPAI $40.85 vs
  $29.99 · VTAK $34.10 vs $29.97 · SMX $34.00 vs $29.30 · LEDS $33.52 vs $29.96 · NYC $33.35 vs
  $19.03 · TJGC $29.52 vs $19.48 · INDP $25.28 vs $12.67.
- Several of those are *winners* (VTAK +$21.83, LEDS +$27.21, NYC +$20.99) — slippage magnitude
  does not by itself predict outcome in this cohort.

**HYPOTHESIS Q2c-H1:** `est_slippage` is an estimator, not a realized fill cost, so this total may
overstate. **Test:** compare `est_slippage` against (fill price − signal price) for the 10 trades
where the decision log records a `filled` price and the trade row records `entry`. Not yet run.

---

## Q3 — FAST LANES

### FINDING Q3a: lane P&L, 7/14+, stamped, ex-PRE (n=118, corrected dollars)
| lane | n | P&L | win | median | best | worst |
|---|---|---|---|---|---|---|
| flat_top | 9 | **+$98.04** | 5/9 | +$7.01 | +$62.89 | −$26.38 |
| ma_pullback | 7 | −$16.11 | 5/7 | +$6.20 | +$31.17 | −$54.40 |
| hidden_entry | 1 | −$39.29 | 0/1 | — | — | −$39.29 |
| ignition | 66 | −$94.50 | 34/66 | +$1.54 | +$164.79 | −$54.76 |
| zone_flip | 2 | −$121.99 | 0/2 | — | −$2.29 | −$119.70 |
| vwap_reclaim | 33 | −$265.64 | 15/33 | −$0.31 | +$50.18 | −$91.26 |

### FINDING Q3a-b: vwap_reclaim has essentially NO valid measured history.
- 32 of its 33 era trades are dated 7/14–7/17 = **pre-VWAP-fix, invalid cohort** (settled 7/26).
- **Post-fix valid cohort: n=1** — KIDZ 7/27, −$36.71. That is the entire evidentiary base for the
  lane, and it is the trade under review.

### FINDING Q3b: the day-gain cliff question is NOT ANSWERABLE.
- `day_gain_at_entry` is stamped on **10 of 144** era rows (field shipped recently).
- Bins: `>+15` n=8 (−$180.91, 2/8 win) · `0..+15` n=0 · `−20..0` n=1 (PN, −$30.75) ·
  `−40..−20` n=0 · `<−40` **n=1 (KIDZ, −$36.71)**.
- **There is exactly one observation below −20%.** No cliff can be located, in either direction.
- Quarantined PRE rows carry the field and are shown for context only (BIYA +534.84% → −$262.89;
  MTNB −28.49% → −$14.26).
- Incidental: the `>+15` bin is 2/8 winners and −$180.91 — i.e. the *high* day-gain cohort is the
  loser in this small sample, which is the opposite of the floor's premise. n=8; no weight claimed.

### FINDING Q3c: ignition-10s post-port acceptance — not computed (needs 10s bars; blocked as above).

---

## Q4 — SLOW LANES & THE DAY-GAIN FLOOR

### FINDING Q4a: the day-gain floor rejected 78 fires in 5 sessions.
- By machine: flat_top 29 · ma_pullback 25 · ignition 22 · orb 2. By date: 7/23 n=10 · 7/24 n=49 ·
  7/27 n=19.
- Blocked `day_gain` distribution: min −64.8 · p25 −7.6 · **med +7.5** · p75 +12.3 · max +21.6.
- **44 of 78 blocks were in the 0…+15 band** — the range floor=15 still refuses.
- **24 blocks had a negative day gain.**

### FINDING Q4b: in 5 sessions, the floor and its exemption collided exactly once — on KIDZ.
Cross-referencing every day-gain-rejected (date,ticker) against trades actually filled that day:
- **KIDZ 7/27 (dg −64.77%, rejected for `ignition` at 09:33) is the ONLY name that was subsequently
  traded by a floor-exempt lane** (vwap_reclaim, 10:40, −$36.71).
- The other 14 worst-rejected names (BIRD −54.6, JLHL −48.4, QH −46.0, GOVX −42.2, AEHL −39.7,
  BNAI −38.0, VGAS −32.9, DCOY −30.2, HCAI −29.6, HTCR −26.7, HTCO −17.1, SLXN −13.6, NCTY −7.6,
  OCG −5.7) were **not** picked up by any exempt lane.

**trace — KIDZ 2026-07-27, full chain (decision log + trade store):**
`07:28 reclaim_shadow_fire` → `07:28 premarket_shadow_entry (premkt_capped, dg −65.11)` →
`08:06/08:07 hidden_shadow_fire ×2 (premkt_capped)` → **`09:33:19 triggered_ignition`** →
**`09:33:23 daygain_reject, machine=ignition, dg −64.77, floor 15.0`** → `10:40:10 broke_not_flat`
(flat-top lane refused) → `10:40:54 chart_gate_allow, reason=live_structure, src=none, enforced=true,
dg −63.82` → **`10:40:55 filled, vwap_reclaim @ $0.5391`** → `10:46:55 Stop loss @ $0.5200`,
**−$36.71**. Peak after entry: $0.5482 (+1.7%). `entry_vs_kev_level_pct −17.85`.

---

## Q5 — CHART GATE

### FINDING Q5a: gate activity, 7/23–7/27 window
`chart_gate_allow` n=48 (27 tickers) · `chart_gate_blocked_trade` n=28 (21) · `chart_gate_block`
n=21 (15) · `chart_gate_skip` n=7 (7). Block reasons are entirely `no_break_below_level` and
`no_marked_level`. Allowed→filled and present in store: n=10 distinct, **−$387.80** (includes PRE).
Denied-side counterfactual MFE **not computed** — needs bars per denied name (blocked as above).

### FINDING Q5b: the `live_structure` / `src=none` bypass fired 26 times, ALL of them on 7/27.
- `chart_gate_allow` splits cleanly into exactly two modes: `('live_structure','none')` n=26 and
  `('broke_level','sheet')` n=22.
- **Bypass fires by date: 7/27 → 26. 7/23, 7/24, 7/26 → 0.**
- Sheet-based allows by date: 7/23 → 3, 7/24 → 16, 7/27 → 3.
- Deduped: 21 distinct (date,ticker) bypass allows; 8 found in the trade store; **−$361.16 total**,
  of which PRE (quarantined) n=3 −$195.21 and **RTH n=5 −$165.95** — BIYA +$32.04, DFNS −$2.29,
  KIDZ −$36.71, LGHL −$119.70, LVWR −$39.29.
- `enforced=true` on all 26 — i.e. the gate was on, and the bypass is the path through it.
- Every 7/27 RTH fill in the store came through this bypass.

**HYPOTHESIS Q5b-H1:** the bypass's 0→26 step change on 7/27 is a consequence of a 7/26 change,
not of market conditions. **Test:** diff the chart-gate call sites between the 7/25 and 7/27
deploys and check whether `src='none'` was previously a skip rather than an allow. Not yet run —
this is a code-provenance question, and the spec forbids me converting it into a verdict.

---

## Q6 — DISCOVERY
Not computed this pass. Q6a/Q6c need fill-time candidate queues that are not in the decision log's
retrievable window; Q6b (read-spend below the liquidity floor) needs reader logs rather than the
decision log. Recorded as not-run, not as clean.

---

## Q7 — RECORDER DEFECTS (every "uncomputable" above lands here)

### FINDING Q7a: field completeness on era rows (n=149 incl. PRE)
| field | present | blocks |
|---|---|---|
| `exit_reason`, `shares`, `entry`, `exit`, `pnl` | 149/149 | — |
| `stop_loss`, `planned_risk`, `risk_per_share`, `est_slippage` | 143/149 | — |
| `entry_type`, `highest`, `partial_fills` | 123/149 | lane splits pre-7/14 |
| **`day_gain_at_entry`** | **15/149** | **Q3b entirely** |
| **`entry_session`** | **10/149** | PRE/RTH separation pre-7/26 |
| **`size_clamp`** | **10/149** | Q2a entirely |
| **entry timestamp** | **0/149 — FIELD DOES NOT EXIST** | **Q1b, Q1c, Q1f, all bar replay** |

**The single highest-leverage recorder gap is the missing entry timestamp.** `recorded_at` is the
*exit* time. Without an entry stamp, no trade outside the 5-day decision-log window can be replayed
against bars at any resolution — which is why Q1c, the query that would price the stop fix's cost
side, has n=2.

### FINDING Q7b: capture-gap census not computed — requires capture-service bar access from the
analysis host (`ALP_CAPTURE_URL` is a private Railway address).

---

## Q8 — DASHBOARD TRUTH AUDIT
Partially answered as a side-effect of the provenance check: `/api/trades` P&L matched the
correction ledger's `corrected` value on **36/36** materially-corrected rows, 0/36 matched raw.
No disagreement found. Full 10-row three-way audit (dashboard vs ledger vs raw store) not run.

---

## Q9 — PREMARKET (quarantined, context only)
The 5 PRE trades, all `vwap_reclaim`, all exited `BLIND-STOP FAILSAFE`: BIYA −$262.89 (dg +534.84%),
LGHL −$166.40 (+140.53%), VEEE −$99.47 (+188.22%), JZXN −$81.48 (+8.89%), MTNB −$14.26 (−28.49%).
All 5 came through the `live_structure`/`src=none` chart-gate bypass (04:12–07:03). Entry-signal
grade separated from custody loss **not computed** — needs premarket bars, the same blocker the
incident itself is about.

---

## Analyst's note on this pass's own limits
Three of the spec's queries returned "not answerable" (Q3b, Q1f, Q6) and two more returned
n≤2 (Q1c, Q2a). That is itself the pass's largest finding: **the outcome half of a review is
currently rate-limited by the recorder, not by analysis effort.** Two joins in my own work were
defective and are marked void rather than reported (Q1b BIYA/LGHL). Fable renders verdicts; nothing
here ships.
