# FLATTEN PARITY 8/16 — X1 (Wind Tunnel): sim 15:59/last-bar flatten vs LIVE 15:45 flatten + 15:30 entry cutoff

**VERDICT: NO NOMINEE FLIPS. All four configs keep their 5-criterion result (O-config PASS, round-F baseline PASS, ORB-15 PASS solo+2-slot, grinder solo PASS). The flatten change costs $0.6-2.6% of total P&L per lane; the O-config portfolio is unchanged (+$156.64 -> +$156.76/day).**

Script: `data/killtests/flatten_parity_20260816.py` (+ `_run.txt`, `_out.json`). Engine chain S(Sunday) -> G -> F -> C -> B -> engine of record, imported UNCHANGED, one instance; OLD = original `F.sim_var`, NEW = same function with the flatten line changed to ALL lanes at the first bar >= 19:44:50Z (the 10s bar completing at 15:45:00 ET; fill = close x (1-0.5%)) and signals >= 19:30:00Z dropped as new entries. Ran 8/16 11:2x EDT, 70s.

## LIVE rule (read this run, marcos_trading_bot.py)
- `:513-514 VWAP_ENTRY_TIMEOUT=15 / _MIN=30` -> **no new entries at/after 15:30 ET** (enforced :7190, :11145, :12416-12448).
- `:516-517 TRADE_WINDOW_END_HOUR=15 / _MIN=45` -> **force-close ALL positions at/after 15:45 ET** (:9495-9496).
- Sim was: grinder flatten 19:59Z, every other lane held to the last RTH bar (20:00:00Z). Both later than production.

## Reconciliation (OLD path, to the cent vs round G / Sunday)
grinder1030 solo N=239 +$5,483.15; flat_top retest N=208 +$1,279.62; BA N=384 +$9,220.01; round-F baseline portfolio N=238 mean +$94.96 med +$62.09; O-config N=156 mean +$156.64 med +$134.44 green 32/36 worst -$109.55; ORB-15 ORL solo N=371 +$12,114.57; ORB-15 2-slot N=180 mean +$114.59 med +$125.57 worst -$174.35. All match.

## OLD (15:59/last bar) vs NEW (15:45 flatten + 15:30 cut)

### Portfolios (2-slot H1-H4, B.pipeline verdict: mean>50, median>50, green>=55%, both halves>0, worst>-300)
| config | N | day mean | day median | green | halves $/d | worst | verdict |
|---|---|---|---|---|---|---|---|
| OLD round-F E3 baseline (grinder1030+retest, 36d) | 238 | +$94.96 | +$62.09 | 29/36 (81%) | +$81.03/+$108.90 | -$115.00 | PASS 5/5 |
| NEW round-F E3 baseline | 235 | +$93.29 | +$74.38 | 29/36 (81%) | +$80.45/+$106.13 | -$115.00 | PASS 5/5 |
| OLD round-G O-config (BA+grinder re-attack, 36d) | 156 | +$156.64 | +$134.44 | 32/36 (89%) | +$167.62/+$145.66 | -$109.55 | PASS 5/5 |
| NEW round-G O-config | 154 | +$156.76 | +$130.35 | 33/36 (92%) | +$169.15/+$144.36 | -$109.55 | PASS 5/5 |
| OLD ORB 15-min ORL 2-slot (62d) | 180 | +$114.59 | +$125.57 | 46/62 (74%) | +$128.06/+$101.70 | -$174.35 | PASS 5/5 |
| NEW ORB 15-min ORL 2-slot | 180 | +$112.53 | +$128.09 | 46/62 (74%) | +$123.35/+$101.70 | -$244.93 | PASS 5/5 |

### Solo lanes (dedup, no capacity; Sunday `stats(bar=True)` same 5 criteria)
| lane | N | win | total | day mean | day median | worst | green | halves | verdict |
|---|---|---|---|---|---|---|---|---|---|
| OLD grinder1030 (36d) | 239 | 56% | +$5,483.15 | +$152.31 | +$108.09 | -$73.21 | 83% | +$2,374/+$3,109 | PASS |
| NEW grinder1030 | 231 | 56% | +$5,345.47 | +$148.49 | +$108.09 | -$75.38 | 81% | +$2,379/+$2,966 | PASS |
| OLD flat_top BREAK-attack (36d) | 384 | 61% | +$9,220.01 | +$256.11 | +$254.49 | -$119.26 | 81% | +$4,556/+$4,664 | PASS |
| NEW flat_top BREAK-attack | 384 | 62% | +$9,055.71 | +$251.55 | +$237.46 | -$130.96 | 81% | +$4,489/+$4,567 | PASS |
| OLD flat_top retest (36d) | 208 | 37% | +$1,279.62 | +$35.54 | +$37.79 | -$164.39 | 67% | +$338/+$942 | FAIL (was FAIL) |
| NEW flat_top retest | 208 | 37% | +$1,217.52 | +$33.82 | +$33.84 | -$164.39 | 67% | +$346/+$871 | FAIL |
| OLD ORB 15-min ORL solo (62d) | 371 | 78% | +$12,114.57 | +$195.40 | +$145.30 | -$160.57 | 82% | +$7,109/+$5,005 | PASS |
| NEW ORB 15-min ORL solo | 371 | 78% | +$11,798.00 | +$190.29 | +$141.57 | -$168.05 | 82% | +$6,870/+$4,928 | PASS |

## Affected cohort (trades open at 15:45 in OLD) — old vs new P&L, delta attributed to the flatten alone
| config | open@15:45 | of N | OLD $ | NEW $ | delta | entries >=15:30 dropped |
|---|---|---|---|---|---|---|
| grinder1030 solo | 75 | 239 | +$1,615.28 | +$1,477.60 (67 matched) | -$137.68 (8 late entries removed = -$0 to -$137.68 mixed; see below) | 8 |
| flat_top BREAK-attack solo | 35 | 384 | +$1,579.10 | +$1,414.80 | -$164.30 | 0 |
| flat_top retest solo | 9 | 208 | +$458.28 | +$396.18 | -$62.10 | 0 |
| round-F baseline H4 | 22 | 238 | +$790.67 | +$730.33 (19 matched) | -$60.34 | 3 |
| O-config H4 | 22 | 156 | +$827.65 | +$831.83 (20 matched) | +$4.18 (slot walk re-fills; flat_top -$48.22, grinder +$52.41) | 2 |
| ORB-15 solo | 41 | 371 | +$157.73 | -$158.84 | -$316.57 | 0 |
| ORB-15 2-slot H4 | 15 | 180 | +$528.72 | +$400.55 | -$128.17 | 0 |
Grinder solo total delta = -$137.68 of which the 8 signals fired >=15:30 ET are simply removed (they were open at 15:45 by construction); the 15:30 cutoff and the 15:45 flatten are not separable for those 8 — both live rules remove them.

Direction: the last 15 minutes were net POSITIVE for holders in every lane (the flatten costs money everywhere except the O-config walk, where freed slots refill). Largest single-lane hit: ORB-15 solo cohort -$316.57 (41 trades, ~-$7.72/trade), still 2.6% of lane total.

## Hand-trace (largest |delta| in O-config H4 open-at-15:45 cohort)
DXST 2026-07-16 flat_top BA, entry-bar 13:42:00Z, sig 2.6890 stop 2.4900: OLD +$46.57 (BANK 1/2 at 19:53:00Z, EOD 20:00:00Z at 2.9502) -> NEW +$22.07 (FLATTEN 19:44:50Z at 2.8357, before the +10% bank ever printed).

## Officers
Wind Tunnel (this run — X1 closed: sim now has a LIVE-parity flatten path in `sim_var_live`, disclosed monkey-patch, chain unchanged); Statistician (`flatten_parity_20260816_out.json`); Trade Manager (E3 verdicts unchanged; the 15:45 flatten costs ~1-3%/lane, no eye earned); Momentum Operator (deltas are noise vs the bars); Systems Quant (OLD reconciles to the cent, all 7 rows); Blast Radius (analysis only, no live change); Historian (record: 15:45-parity numbers supersede round F/G/Sunday figures for live-vs-sim grading Monday); Forward Architect (open question, hypothesis only: hold-to-15:59 was worth +$137 to +$316/lane over the window — a "power-hour hold" is NOT a wire, it contradicts Sunday T1's power-hour finding and Marcos's 15:45 rule stands). Dashboard Curator, Feed Engineer, Side Marshal, Crown Steward: clean.
