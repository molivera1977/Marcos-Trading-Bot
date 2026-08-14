# ENTRY REBUILDS — FULL-CACHE RE-RUN (8/14/2026 PM)
Third pass on the three rebuilt entries, at the current universe cache. Engines
UNCHANGED from the prior passes (scratchpad `rebuild_bt.py` for v2-flush + vwap
band-pass; `flattop_v2.py` for flat_top — the `flattop_retrial_v2_20260814.md`
spec of record: **>=1% pullback depth + 15-min per-name cooldown**). Method laws
identical: bars walked in order, no lookahead, $500/position, half scaled +4%,
remainder trails 10s EMA90 (running-mean seed), stop-first on same-bar ties,
EOD flatten. Optimistic fills, no slippage/halts/commissions — same caveats as
both prior passes.

## DATA
- Cache at run time: **327 files (name-days) across 29 distinct dates, 2026-07-06..2026-08-13**
  (v1 pass: 39 files/4 dates; v2 pass: 95/8). First real multi-week sample.
- Date split: **half1 = 7/06-7/23 (14 dates) vs half2 = 7/24-8/13 (15 dates)** — a genuine
  earlier-vs-later wall this time, not the degenerate split of the v1 pass.
- In-window = 9:30-10:30 ET (13:30-14:30Z, EDT).

---
## 1. FLAT_TOP real-retest (>=1% depth + 15-min cooldown — the retrial-v2 spec)
| cohort | N | win% | total $ | mean $/trade |
|---|---|---|---|---|
| ALL | 1009 | 38% | +2026.58 | +2.01 |
| **IN 9:30-10:30** | **171** | **44%** | **+2035.06** | **+11.90** |
| OUT | 838 | 36% | -8.49 | -0.01 |
| half1 (7/06-7/23) ALL | 466 | 40% | -211.28 | -0.45 |
| half2 (7/24-8/13) ALL | 543 | 36% | +2237.85 | +4.12 |
| IN half1 | 81 | 47% | +164.30 | +2.03 |
| IN half2 | 90 | 42% | +1870.77 | +20.79 |
Exit mix 603 stop / 337 trail / 69 eod. Worst day 8/03 -306.99.
Outlier: YJ 8/07 13:51:50 +$1,102.20 again in the totals. IN ex-YJ: 170 tr, 44%, **+$932.86** (+5.49).

### Hand-trace — ZCMD 2026-07-06 (first in-window fire of the run)
14:05:40 RECLAIM -> ENTER 2.2816, stop 2.2500 (pullback low) · 14:05:50 bar low
2.2300 <= stop -> STOP, exit 219.1 sh, P&L **-$6.92**. (Stop-first law applied.)

### Verdict vs prior pass: **HOLDS in-window / WEAKENS on full day**
In-window is positive in BOTH halves (+$164 / +$1,871) and survives the YJ excision
(+$933 on 170) — same sign+shape as the 8-date pass (which was +$1,535 IN / -$307 OUT).
Per-trade mean came down (+$31.97 -> +$11.90) as the sample tripled — expected shrinkage,
not a flip. Full-day ALL is half2-carried (half1 -$211): the unwindowed book stays
NEEDS-MORE-DATA. The window-restricted shadow-candidate call stands, now on 29 dates.

---
## 2. VWAP_RECLAIM band-pass (12-30 closes hold, new minor high entry)
| cohort | N | win% | total $ | mean $/trade |
|---|---|---|---|---|
| ALL | 176 | 48% | +1344.83 | +7.64 |
| **IN 9:30-10:30** | **73** | **58%** | **+1619.61** | **+22.19** |
| OUT | 103 | 42% | -274.79 | -2.67 |
| half1 ALL | 81 | 51% | +341.22 | +4.21 |
| half2 ALL | 95 | 46% | +1003.61 | +10.56 |
| IN half1 | 32 | 59% | +311.71 | +9.74 |
| IN half2 | 41 | 56% | +1307.90 | +31.90 |
Exit mix 77 stop / 96 trail / 3 eod (trail-dominant — healthiest exit mix of the three).
Worst day 7/27 -174.57. Outlier: YJ 8/07 +$1,039.07. IN ex-YJ: 72 tr, 56%, **+$580.54** (+8.06).
Control cohort (just-crossed <12, simulated identically): 2576 tr, 29%, +$5,074.79 (+1.97);
IN +$3,808 (+3.59) — positive but at ~1/6 the per-trade mean of the band-pass arm.

### Hand-trace — ABTC 2026-07-06
13:53:40 hold streak 14 closes above VWAP, new minor high -> ENTER 7.9700, stop 7.7000
(hold low) · 13:54:30 SCALE half +4% (8.2888) · 14:05:20 TRAIL exit close 8.0400 <
EMA90 8.0767 -> flat. P&L **+$12.20**.

### Verdict vs prior pass: **FLIPS (in the entry's favor)**
The 4-date pass lost every day (-$325.86, N=23, "leaning REFUTED-as-encoded"). On 29
dates the band-pass is positive in BOTH halves, both windows-in, 48-58% wr, and survives
the YJ excision. The v1 sample was simply too small and its 4 days were unrepresentative.
REFUTED must NOT be written from the v1 pass. Note the honest wrinkle: the just-crossed
control is also net positive here, so the band-pass's claim is now "higher quality per
trade" (+$22 vs +$3.6 mean in-window), not "the band is the only edge" — the 7/31 study's
condemnation of just-crossed did not replicate either.

---
## 3. V2 CONFIRMED-PULLBACK flush (Hidden Entry Architect blueprint)
| cohort | N | win% | total $ | mean $/trade |
|---|---|---|---|---|
| ALL | 4029 | 33% | -2033.86 | -0.50 |
| **IN 9:30-10:30** | **938** | **40%** | **+2847.83** | **+3.04** |
| OUT | 3091 | 31% | -4881.69 | -1.58 |
| half1 ALL | 1762 | 36% | -1526.21 | -0.87 |
| half2 ALL | 2267 | 31% | -507.65 | -0.22 |
| IN half1 | 450 | 41% | +547.89 | +1.22 |
| IN half2 | 488 | 39% | +2299.93 | +4.71 |
Exit mix 2709 stop / 1211 trail / 109 eod. Worst day 8/13 -735.33.
Outlier: YJ 8/07 (2 in-window trades) +$1,211.44. IN ex-YJ: 936 tr, 40%, **+$1,636.39** (+1.75).

### Hand-trace — ZCMD 2026-07-06
13:30:50 flush + buyers step in (higher low, close > prior high) -> ENTER 2.5100, stop
2.4300 (flush low) · 13:31:20 SCALE half +4% (2.6104) · 13:32:50 TRAIL exit close
2.6300 < EMA90 2.6557 -> flat. P&L **+$21.95**.

### Verdict vs prior pass: **HOLDS (in-window edge), with an honest haircut**
Same shape as the 4-date pass on 7x the data: in-window positive in BOTH halves,
out-of-window bleeds heavily in both. But the mean compressed hard: +$8.88 -> +$3.04
(+$1.75 ex-YJ), and 938 fires/29 days ≈ 32/day across the universe is far too many for
5-8/day doctrine — the raw detector needs the gate stack / selection layer before its
shadow numbers mean anything at live frequency. Window restriction remains mandatory.

---
## COMBINED IN-WINDOW PORTFOLIO (all three entries, 9:30-10:30 trades summed/day)
29 days: **total +$6,502.51 · daily mean +$224.22 · worst day 8/13 -$214.82 ·
best day 8/07 +$3,125.61 · green 16/29 (55%)**.
Ex the whole 8/07 day (YJ carried all three entries): total +$3,376.90, **daily mean
+$120.60**, worst day unchanged -$214.82, green 15/28.
Daily tape: 7/06 -69 · 7/07 -25 · 7/08 -68 · 7/09 +352 · 7/10 -58 · 7/13 +136 ·
7/14 -15 · 7/15 -22 · 7/16 -16 · 7/17 -13 · 7/20 -14 · 7/21 +18 · 7/22 +511 ·
7/23 +305 · 7/24 +4 · 7/27 -73 · 7/28 +285 · 7/29 +499 · 7/30 +176 · 7/31 +360 ·
8/03 -50 · 8/04 +58 · 8/05 +63 · 8/06 -51 · 8/07 +3126 · 8/10 +64 · 8/11 +498 ·
8/12 +734 · 8/13 -215.
The Monday-menu number: mean ~$120-224/day at $500/position sizing, worst observed
day -$215 — but this is 3 detectors firing simultaneously with no capital constraint,
no overlap dedup (all three took YJ 8/07 within 20 min of each other), and raw-census
frequency. Treat as an upper bound on the shape, not a P&L forecast.

## SUMMARY
| entry | prior verdict | full-cache verdict |
|---|---|---|
| FLAT_TOP >=1%+cooldown | SHADOW-CANDIDATE (windowed) | **HOLDS** in-window (green both halves, survives outlier); full-day WEAKENS |
| VWAP band-pass | leaning REFUTED-as-encoded | **FLIPS positive** — v1's 4 days were unrepresentative; do not write REFUTED |
| V2 flush | MONDAY-CANDIDATE (windowed shadow) | **HOLDS** shape; mean haircut to +$3.04 (+$1.75 ex-YJ); needs gate stack before live-frequency claims |

Standing caveats: one cache, optimistic close/exact fills, no halt/slippage/commission
modeling, no gate stack, YJ 8/07 is a shared outlier across all three (excisions shown),
in-window overlap between entries is real and undeduplicated. Nothing here authorizes
behavior — shadow rows go to Marcos priced (Auditor-Cannot-Authorize).
