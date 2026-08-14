# EDGE STRESS-TEST — PRE-REGISTERED HAIRCUT WATERFALL (run 8/14/2026 ~18:40-19:00 ET, filed as 20260815)

Marcos: "we are not exiting this weekend without finding the fucking edge." The bar was
pre-registered BEFORE the run; haircuts applied cumulatively, in order, no softening,
no cohort trimming. Script archived alongside: `edge_stresstest_20260815.py`
(engines ported unchanged from scratchpad `rebuild_bt.py` / `flattop_v2.py` /
`missing_regimes.py` — the engines of record from `entry_rebuilds_v2_fullcache_20260814.md`
and `missing_regimes_20260814.md` KT2a).

## DATA
- **419 files (name-days), 36 dates, 2026-06-25 .. 2026-08-14** — includes 8/14 and the
  full 7/27 halt day. (Cache was still being ferried during the session: 398 → 411 → 419
  across ~25 min; the committed numbers are the 419-file run. Quartermaster should note.)
- 10s tick-reconstructed bars; bar timestamp gaps = zero-trade intervals (halt detection uses this).

## THE FOUR ENTRIES (as pre-registered)
1. **v2 flush** (confirmed-pullback, Hidden Entry Architect blueprint) — in-window 9:30-10:30 ET only.
2. **flat_top real-retest** (>=1% pullback depth + 15-min per-name cooldown) — in-window only.
3. **vwap band-pass** (12-30 closes hold above VWAP, new-minor-high entry, rejected-arm
   bookkeeping reproduced exactly from the source engine) — in-window only.
4. **vertical grinder breakout** (KT2a: post-11:00 ET new session high, 30m net-up, above
   VWAP, no >=3% pullback in 15m, 15-min cooldown; breakeven-after-half + 15:59 flatten
   per its own spec) — post-11:00 only.

Exits per engine of record: half at +4% (resting limit), remainder trails 10s EMA90,
structural stop, stop-first on same-bar ties, EOD flatten. $500/position.
In-scope signals: **1,753** (v2 1,231 · flat_top 208 · vwap 103 · grinder 211).

---
## H0 -> H4 WATERFALL (portfolio $, all 36 dates; days with no trade = $0)

| stage | N trades | total $ | daily mean $ | worst day $ | delta vs prior stage |
|---|---|---|---|---|---|
| **H0** baseline (windowed, $500/pos) | 1753 | **+9,829.68** | **+273.05** | -156.73 | — |
| **H1** frictions (entry -1%, market exits -0.5%, limits exact) | 1753 | **-716.85** | **-19.91** | -629.40 | **-$10,546.53** |
| **H2** halt exclusion (8 forced resumption-open exits) | 1753 | -816.87 | -22.69 | -629.40 | -$100.02 |
| **H3** overlap dedup (same name <=5 min, first wins; 423 dropped) | 1330 | -852.98 | -23.69 | -367.99 | -$36.11 |
| **H4** capital constraint (max 2 concurrent; 785 skipped) | 545 | **+134.04** | **+3.72** | -155.11 | +$987.02 |

**THE BREAK IS H1.** Before frictions: +$273.05/day. After: -$19.91/day — a
-$10,547 swing, ~$6.02 average friction per trade against a +$5.61 average gross
edge per trade. Every stage after H1 is fighting over the corpse. (H4 "improves"
the total only because capacity-rationing randomly sheds mostly-negative v2 flow.)

## H5 ROBUSTNESS (post-H4 portfolio, 36 days)
| metric | value |
|---|---|
| daily mean | **+$3.72** |
| MEDIAN day | **-$48.52** |
| worst day | -$155.11 (7/27, the halt day) |
| green days | 15/36 = **42%** |
| half1 (6/25-7/21, 18d) | +$533.83 (+$29.66/d) |
| half2 (7/22-8/14, 18d) | -$399.79 (-$22.21/d) |
| best day | 6/25 +$335.11 · ex-best-day mean **-$5.74** |
| per-entry contribution | v2: N=350 **-$1,570.30** · flat_top: N=47 **+$426.08** · vwap: N=24 -$85.75 · grinder: N=124 **+$1,364.01** |

Daily tape (post-H4): 6/25 +335 · 6/26 +323 · 6/29 -71 · 6/30 +47 · 7/01 -83 ·
7/02 -154 · 7/06 +123 · 7/07 -50 · 7/08 -47 · 7/09 +87 · 7/10 -37 · 7/13 +243 ·
7/14 -52 · 7/15 -97 · 7/16 +5 · 7/17 -91 · 7/20 -74 · 7/21 +128 · 7/22 +287 ·
7/23 -68 · 7/24 -149 · 7/27 -155 · 7/28 -119 · 7/29 -45 · 7/30 +62 · 7/31 +119 ·
8/03 +40 · 8/04 -63 · 8/05 +112 · 8/06 -133 · 8/07 -123 · 8/10 -86 · 8/11 +110 ·
8/12 +54 · 8/13 -147 · 8/14 -96.

Note 8/07, the YJ +$3,126 hero day of the un-haircut report, is **-$123.42** here —
the outlier day was a friction/dedup/capacity artifact, exactly what this test existed to expose.

---
## VERDICT vs THE PRE-REGISTERED BAR (post-H4)
| criterion | bar | actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$3.72 | **FAIL** |
| daily median | > +$50 | -$48.52 | **FAIL** |
| green days | >= 55% | 42% | **FAIL** |
| both date halves positive | yes | half2 -$22.21/d | **FAIL** |
| worst day | > -$300 | -$155.11 | **PASS** |

**OVERALL: FAIL — 1 of 5.** The haircut that broke it: **H1 frictions**
(+$273.05/day -> -$19.91/day). H2/H3 were near-neutral; H4 partially recovered by
shedding v2's negative flow but nowhere near the bar.

## What survives the gauntlet (honest reading, not softening)
- **Grinder breakout: +$1,364.01 on 124 post-H4 trades (+$11.00/trade) WITH full
  frictions/halts/dedup/capacity.** The only entry whose per-trade mean survives -1%/-0.5%
  slippage. It also has the only breakeven-after-half exit — part of its friction armor.
- **flat_top: +$426.08 on 47** — thin but positive under full haircuts.
- **v2 flush: -$1,570.30 on 350 post-H4** — at raw frequency the flush's +$3.04 gross mean
  is eaten whole by ~$6 friction. Confirms the 8/14 report's own warning: needs the
  gate stack / selection layer before live-frequency claims. Refuted AS A RAW LANE at
  realistic frictions; not refuted as a gated concept (untested here).
- vwap band-pass: N=24 post-H4, -$85.75 — too small to grade after rationing; its slot
  losses come mostly from capacity crowding with v2 (same names, minutes apart).
- The -1% entry slippage assumption is the entire hinge: at these prices ($0.32-$19 names)
  1% is 1-3 spreads. If real entry slippage is materially better (limit-in entries), the
  verdict could move — but that is a NEW pre-registration for a new test, not a re-grade
  of this one.

## HAND-TRACE — 2026-07-13 (a day with overlap dedups AND slot skips; day total +$243.07)
Chronological walk, post-H4 portfolio (TAKEN / DEDUP-DROP / SLOT-SKIP), abridged to the
load-bearing sequence — full row dump in `edge_stresstest_20260815_trace.txt`:
- 13:30:30Z QTTB v2 TAKEN (slot 1) entry 17.81 stop 17.28 -> trail exit 13:35:00, +$16.27
- 13:31:00Z FTRK v2 TAKEN (slot 2) entry 0.51 stop 0.5024 -> STOP 13:31:20, -$14.77
- 13:31:00Z MIMI v2 **SLOT-SKIP** (2 open) · 13:31:20Z EHGO, LGPS **SLOT-SKIP**
- 13:31:30Z BRAI v2 TAKEN — FTRK's stop at 13:31:20 freed the slot -> trail 13:53:20, +$22.94
- 13:32:00Z QTTB v2 **DEDUP-DROP** (QTTB fired 90s earlier — first signal wins)
- 13:56:00Z BRAI flat_top TAKEN +$17.02; 13:56:10Z BRAI v2 **DEDUP-DROP** (10s behind flat_top)
- 14:15:10Z VEEE v2 TAKEN +$114.61 (trail 14:47:20); 14:18:30Z VEEE vwap **DEDUP-DROP**
- 15:34:40Z EHGO grinder TAKEN +$19.85 · 15:46:00Z FTRK grinder TAKEN +$28.87
Slot accounting verified by hand: at no timestamp do 3 positions coexist; every TAKEN
follows a stop/trail exit that freed a slot; ties (exit second == signal second) count
the slot as still occupied — against the portfolio, per the law.

## Method notes / deviations disclosed
1. Engines ported to one harness (UTC-string timestamps, epoch-second math). EMA90 uses
   the rebuild running-mean seed for ALL four (grinder's source used first-close seed);
   grinder EMA computed over RTH bars only (source included premarket). Both are
   second-order vs a $10.5k friction swing.
2. H2 halt rule exactly as pre-registered: entry within 2 min BEFORE a >=4-min zero-trade
   gap + resumption open < stop -> filled at resumption open (with H1 market slippage).
   8 firings. Gaps NOT volume-qualified here (any >=4-min zero-trade gap) — stricter than
   the KT1 heuristic, per the pre-registration's wording.
3. H3 dedup keyed to last KEPT signal per name (chains of signals each <5 min apart
   collapse to the first).
4. Detector sequencing (open_until / cooldowns) uses the baseline exit engine, as in the
   engines of record; H1+ P&L re-simulated per trade. vwap rejected-arm (<12 streak)
   bookkeeping reproduced exactly — first port missed it and undercounted the band arm
   9 vs 103; caught by reconciling against `rebuild_bt.strat_vwap` on the same files.
5. Days with zero trades count as $0 days in all daily stats (36-day denominator).
6. Signals are windowed post-hoc (detectors run full-day; out-of-window fires still occupy
   their name's open_until) — same convention as the 8/14 full-cache report.

## Officers touched
Wind Tunnel Engineer (harness + fidelity), Systems Quant (port reconciliation, vwap
undercount catch), Statistician (this ledger entry), Momentum Operator (verdict framing),
Convexity Trader (median/tail read: median day -$48.52 is the headline), Execution
Surgeon (H1 friction model), Trade Manager (exit engines unchanged), Side Marshal /
Crown Steward / Handicapper: clean (no gate stack in scope — raw-lane test by design).
Forward Architect: next registered hypothesis = grinder+flat_top-only portfolio, and
limit-in entry friction model — BOTH require fresh pre-registration; do not re-grade
this run's cohort.
