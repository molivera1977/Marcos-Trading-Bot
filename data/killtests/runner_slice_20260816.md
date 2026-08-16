# RUNNER SLICE 8/16 — pre-registered exit-only test on O-config entries

Marcos: "i want the consistency but we have to hit home runs every once in a while to help add insurance."
Analysis only. Script `runner_slice_20260816.py` -> `_run.txt` / `_out.json` (all numbers below are copied from that run).
Chain: `flatten_parity_20260816.py` (LIVE parity: -1% chase entry, -0.5% market-exit slip, no new entries >= 15:30 ET,
everything flat at the 15:45 ET bar) -> S -> G -> F -> C -> B -> engine, imported UNCHANGED. $500 clip, 2-slot H1-H4 pipeline.
Entries frozen = O-config (flat_top BREAK-attack 13:30-14:30Z + grinder-1030 re-attack <=3, cooldown timed under S0).
Universes: 36 pre-registered dates (2026-06-25..08-14) and the 62-date full cache (2026-05-18..08-14).

**Reconcile:** S0 on 36 dates = N=154, mean +$156.76, median +$130.35, green 33/36, worst -$109.55, PASS — matches flatten_parity NEW O-config to the cent.

## Variants (exit only, identical entries)
- S0 E3: bank 50% at +10%, trail 50% at 10%-off-high (closes-through), trail arms after the bank.
- S1 70/30: bank 50%, 20% on the E3 trail, 30% runner on an E4 trail (never banks, 10%-off-high from entry). S2 = 80/20 (30% E3-trail / 20% runner). S3 = 60/40 (10% / 40%).
- S4 70/30 with the runner trail 15%-off-high. S5 70/30 with the runner trail arming only after high >= +20% (stop-only until then).
- Stop / halt-gap closes every leg; slot is held until the LAST leg exits (runner-held slots displace later entries -> priced in H4).
- Slice contribution per trade = variant trade $ minus S0 $ on the same entry (only the runner leg differs). Home run = contribution >= $100 / $250 / $500.
- Premium = S0 median minus variant median (positive = the slice COST median).

## Structural finding (before the table)
After the +10% bank, E3's un-banked half already trails 10%-off-high — it IS an E4 runner. So S1/S2/S3 as specified differ from S0
only BEFORE the bank: the E4 trail is live from entry, so the runner slice gets shaken out on a 10% pullback before +10% is reached,
i.e. it behaves as a tighter stop on 20-40% of the position. Its "top contributions" are all LOSING trades where it lost less than the stop
(OESX 8/05 +$11.67 slice on a -$58 S0 trade, etc.). It never adds upside. Only S4 (wider trail) and S5 (late-arming trail) change the ride.

## 36-date universe (pre-registered), O-config signals N=483
| variant | N | day mean | day MEDIAN | green | halves $/d | worst | 5-crit | HR >=100/250/500 | slice total | premium (median vs S0) | max slice bleed streak |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S0 E3 baseline | 154 | +$156.76 | +$130.35 | 33/36 (92%) | +$169.15/+$144.36 | -$109.55 | PASS | 0/0/0 | $0 | $0 | 0d |
| S1 70/30 E4-runner | 154 | +$153.91 | +$132.18 | 33/36 | +$163.47/+$144.36 | -$107.16 | PASS | 0/0/0 | -$102.43 | -$1.82/d (median UP) | 2d (11 neg / 17 pos days) |
| S2 80/20 | 154 | +$154.86 | +$131.20 | 33/36 | +$165.36/+$144.36 | -$107.96 | PASS | 0/0/0 | -$68.29 | -$0.84/d | 2d (10/15) |
| S3 60/40 | 154 | +$152.96 | +$133.16 | 33/36 | +$161.57/+$144.35 | -$106.36 | PASS | 0/0/0 | -$136.58 | -$2.80/d | 2d (7/21) |
| S4 70/30, runner 15%-off-high | 142 | +$146.02 | +$140.66 | 32/36 (89%) | +$122.28/+$169.76 | -$109.55 | PASS | 2/0/0 | +$373.00 | -$10.31/d (median UP) | 6d (21 neg / 13 pos) |
| S5 70/30, runner arms after +20% | 143 | +$163.32 | +$134.72 | 34/36 (94%) | +$165.78/+$160.86 | -$109.55 | PASS | 1/0/0 | +$527.88 | -$4.37/d (median UP) | 3d (7 neg / 20 pos) |

Top slice contributions, 36 dates: S4 = CIGL 6/30 grinder +$183.55 (trade $231.33 vs S0 $47.78), STFS 7/28 grinder +$156.37 ($182.06 vs $25.70), WYHG 8/10 +$73.37, DGNX 6/29 +$60.89, GWAV 7/29 +$59.76. S5 = STFS 7/28 +$156.37, GWAV 7/29 +$76.56, TC 7/24 +$54.61, BRAI 7/13 +$54.47, SORA 7/23 +$48.00.

## 62-date full cache, O-config signals N=806
| variant | N | day mean | day MEDIAN | green | halves $/d | worst | 5-crit | HR >=100/250/500 | slice total | premium | max slice bleed streak |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S0 E3 baseline | 277 | +$153.51 | +$126.03 | 53/62 (85%) | +$168.78/+$138.25 | -$109.55 | PASS | 0/0/0 | $0 | $0 | 0d |
| S1 70/30 | 277 | +$148.45 | +$129.56 | 53/62 | +$161.29/+$135.62 | -$112.49 | PASS | 0/0/0 | -$313.69 | -$3.53/d | 2d (18/31) |
| S2 80/20 | 277 | +$150.14 | +$128.38 | 53/62 | +$163.78/+$136.50 | -$109.37 | PASS | 0/0/0 | -$209.13 | -$2.35/d | 2d (17/29) |
| S3 60/40 | 277 | +$146.77 | +$130.73 | 53/62 | +$158.79/+$134.75 | -$115.61 | PASS | 0/0/0 | -$418.25 | -$4.70/d | 2d (13/39) |
| S4 runner 15%-off | 255 | +$165.54 | +$160.79 | 55/62 (89%) | +$195.69/+$135.39 | -$112.43 | PASS | 7/0/0 | +$1,330.31 | -$34.76/d (median UP) | 6d (31 neg / 28 pos) |
| S5 runner arms +20% | 256 | +$164.58 | +$145.79 | 56/62 (90%) | +$185.24/+$143.93 | -$109.55 | PASS | 4/0/0 | +$846.24 | -$19.76/d (median UP) | 3d (11 neg / 34 pos) |

Top S4 slices, 62 dates: MTEN 6/08 grinder +$238.52 (trade $325.98 vs S0 $87.45), CIGL 6/30 +$183.55, PRFX 6/15 +$163.62, STFS 7/28 +$156.37, PAVS 6/08 +$154.64. S5: STFS +$156.37, ELTX 6/17 +$125.01, WCT 6/10 +$79.48, GWAV +$76.56, TC +$54.61.

Home-run dollars per dollar of median given up: undefined — no variant costs median (every premium is <= 0). S4/S5 raise mean AND median in both universes.

## Caveats (Wind Tunnel / Statistician)
- ZERO trades reach the $250 or $500 "home run" bar in either universe under any slice. On a $500 clip the runner leg is $100-$200 of stock; a $250 slice contribution needs the runner to ride ~+170% past where E3's trail would have sold. That did not happen once in 62 dates. Insurance-grade tail (>=$250) does not exist at this clip size — it would require a bigger runner leg or a bigger clip, both of which are sizing changes (sizing refuted 8/14) and out of this test's scope.
- S4/S5's N drops (154->142/143; 277->255/256): runner-held slots displaced later entries. Part of the mean/median lift comes from the displaced trades being net losers, not only from the runner ride — this is a slot-occupancy effect and would move with slot count. Not separated here.
- 36-date S4 halves flip (first half +$122 vs S0 +$169; second half +$170 vs +$144): the wide trail bleeds in the first half. S4's slice was net-negative on 21 of 36 days with a 6-day bleed streak — the variant Marcos would FEEL most.
- All slice sample sizes are small; the differences between S1-S3 and S0 (<=$5/day) are within noise.

## Hand-trace YJ 2026-08-07 (the +$1,102 rocket day of the F/G ledgers)
YJ's O-config signal is the flat_top BREAK-attack at 13:48:10Z (sig 1.5800, chase fill 1.5958, 313.3 sh, stop 1.4300). It is NOT in the H4 set (both slots occupied at 13:48 in every variant), so this is a standalone trace of that signal:
- S0: 13:53:30 BANK 50% at 1.7554; 14:21:10 TRAIL close 2.9000 fill 2.8855 (156.7 sh) -> **+$227.05**.
- S1/S2/S3/S5: identical fills (bank 1.7554, both remaining legs out 14:21:10 at 2.8855; runner hi 3.3000) -> **+$227.05**, slice $0.
- S4 (best slice): bank 1.7554; 14:21:10 E3-trail 62.7 sh at 2.8855; runner 94.0 sh rides to hi 3.9700, 14:27:00 close 3.1800 fill 3.1641 -> **+$253.23** (slice +$26.18). Even the wide trail caught only 26 dollars of YJ's move; the +$1,102 in the ledger came from the retest-lane entry, not from any exit rule on this entry.

## Verdict
- All six variants keep the 5/5 PASS on both universes. S1/S2/S3 (the literal "E4 runner slice") add no tail at all: after the bank they are E3; before it they are a tighter stop. Do not ship them — they are E3 with extra plumbing.
- The only slices with measurable tail are S4 (runner trail 15%-off-high) and S5 (runner trail arms after +20%): 36 dates HR>=$100 = 2 / 1, slice totals +$373 / +$528, medians +$140.66 / +$134.72 vs +$130.35; 62 dates HR>=$100 = 7 / 4, slice totals +$1,330 / +$846, medians +$160.79 / +$145.79 vs +$126.03. Both raise mean and median — the premium is negative, so there is no ratio to price.
- Nothing catches >= 3 home runs at the $250 bar (0 in sample) — the "insurance" Marcos described is not reachable through exits alone at a $500 clip. Cheapest premium that catches >= 3 slices >= $100: S5 on 62 dates (4 hits, premium -$19.76/d, i.e. free, bleed streak 3d, 11 negative days of 62); S4 has more hits (7) and a bigger median lift but bleeds on half its days (31 of 62) with a 6-day streak and a flipped 36-date first half.
- Recommendation for Marcos to price: S5 (70/30, runner arms after +20%, 10%-off-high) as the candidate insurance layer — mild, positive in both universes, mildest bleed. It is exit-behavior change on real money -> Marcos's call, priced above; not an auditor ship. If shipped it needs the standard gauntlet (env kill switch, hostile-tape replay, rig) and the slot-displacement effect isolated first.

Officers touched: Wind Tunnel Engineer (chain reuse, reconcile), Trade Manager (exit design), Statistician (numbers from `_run.txt`), Convexity Trader (tail shape: no >=$250 tail exists at this clip), Blast Radius Auditor (not convened — analysis only, nothing ships).
