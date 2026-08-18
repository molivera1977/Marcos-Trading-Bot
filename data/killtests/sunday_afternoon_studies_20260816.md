# Sunday Afternoon Studies — 2026-08-16 (agenda item 3 + registry quick-checks)

**VERDICT QUALIFIER (LIMITS, added 2026-08-17):** a mixed-power sweep — the T2/T3/T4 refutations rest on N=36 to N=1356, but named survivor cells fall to n=2. The refutations stand; the survivor-precondition and power-hour figures are descriptive of a 62-date cache with no out-of-sample wall.

Analysis only; no bot code touched. Script: `data/killtests/sunday_afternoon_studies_20260816.py`
(imports edge_stresstest_G -> F -> C -> B -> engine of record, unchanged). Raw run log:
`sunday_afternoon_studies_20260816_run.txt` (all tables below are copied from it).

**Universe:** FULL cache, 729 files in `data/universe/bars10s`, 729 usable RTH days, **62 dates 2026-05-18..2026-08-14**
(8-15 files/date). Denominator for day-mean/median = 62 dates. Halves split at date 31.
**Exits:** all E3 (bank 1/2 at +10%, trail rest 10%-off-high closes-through, stop-first ties, -1% chase entry, -0.5% market-exit slip; grinder keeps 19:59Z flatten, other lanes exit at last RTH bar). $500 clip.
**Bar** (portfolio-shaped rows): mean AND median > $50/day, green >= 55%, both halves positive, worst > -$300.
Per-trade tables are graded post-dedup (same name <=5 min), NO capacity unless labeled "portfolio".
Detector parity checks: annotated band-pass = engine (414=414); annotated flat_top_break = G (4452=4452); `sim_e3_rule(None)` vs `F.sim_var E3` abs diff 0.000000.

## FIRST-LINE VERDICTS
- **T1 POWER-HOUR: REFUTED as a lane, claim CONFIRMED-DIRECTIONALLY.** 15:00-16:00 is the worst bucket for every lane (grinder +$7.75/tr 44% win; break-attack -$10.02/tr; band-pass +$0.24/tr; v2cal -$12.90/tr). Only **13.4% of universe days make a new RTH high after 15:00 ET** (14.1% of >=+20% runner-days, 18.9% of strong closers) -> the "80-85% no new high" article claim holds on our tape (~86%).
- **T2 HALT RETEST (KT1b): REFUTED at full cache.** N=36 (26 up / 10 down), 19% win, -$1,078.81 total, -$29.97/tr; up-halts -$855.15 (-$32.89/tr), down-halts -$223.66. Both halves negative. The 8/14 "needs-more-data / only non-bleeding shape" is now bleeding with 2.4x the N. Controls (a) -$2,073.52/108, (c) -$3,569.01/296 also negative.
- **T3 MIDDAY BREAK-ATTACK: REFUTED outside the open.** 13:00-15:00 cell -$7,483.94 / 1356 (36% win, -$120.71/day). Survivor precondition (held above VWAP 11:30-13:00 AND >=+20%) turns the cell from -$5.52/tr to **+$1.66/tr (N=99, +$164 total, median day $0)** — filter is real (survivor vs non-survivor gap $7.74/tr) but the residual is breakeven, not an edge. Break-attack edge lives 09:30-10:30 only (+$26.86/tr, 62% win, +$16,978/632).
- **T4 AFTERNOON RECLAIM leaders-only: REFUTED (and the leader restriction inverts).** Unrestricted 12:00-14:30 reclaim +$219/95 (+$2.31/tr, breakeven); leaders-only **-$265.77/24 (21% win)**; non-leaders +$484.81/71. Chop exclusion + two-bars-below leaves N=2 (-$34.73) — cell too thin to grade, no edge visible.
- **T5 ORB FAIR RE-RUN: 15-min ORB PASSES the bar (per-trade AND 2-slot portfolio); 5-min passes per-trade, fails portfolio on worst day.** 15-min ORL: 371 trades, 78% win, +$12,114.57, +$32.65/tr, day mean +$195.40 / median +$145.30, green 82%, worst -$160.57; portfolio N=180 mean +$114.59 / median +$125.57 / green 46/62 / halves +$128/+$101 / worst -$174.35 -> PASS. 5-min ORL: per-trade +$13,436.54/454 (73% win) PASS; portfolio mean +$82.86 median +$81.28 worst **-$344.25** -> FAIL (worst). Stop=MID is worse in every cell. **CAVEAT: ORB triggers overlap the champion break-attack window 09:30-10:30 (same names, same minutes) — this is a competing selection of the same open, not an additive lane; head-to-head vs break-attack in the same slots is the required next test before any registry promotion.**
- **T6 REGISTRY QUICK-CHECKS: all three REFUTED.** (a) failed-break exit fires 219/634 break-attacks: rule -$4,716.58 vs default +$1,787.13 on those trades; lane drops from +$17,031 to +$10,527. (b) no-progress-15: grinder +$10,676 -> +$3,927 (fired 222/387: -$913 vs +$5,836 default); break-attack +$17,031 -> +$2,683 (fired 342/634: -$3,221 vs +$11,127). Slow starters are where the winners are. (c) volume clause: >=1.5x cohort +$24.66/tr (62% win, N=487) vs <1.5x +$34.17/tr (64% win, N=147) — no discrimination; the low-volume cohort is per-trade BETTER. Do not add.

---
## T1 — Power-hour join (per lane, signal-time buckets, E3, no capacity)
### grinder (post-10:30 by spec; N=387)
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| 10:30-12:00 | 157 | 69% | $+7070.56 | $+45.04 | $+114.04 | $+73.20 | $-93.85 |
| 12:00-13:00 | 91 | 55% | $+1843.48 | $+20.26 | $+29.73 | $+0.00 | $-121.95 |
| 13:00-15:00 | 107 | 48% | $+1514.11 | $+14.15 | $+24.42 | $+0.00 | $-82.09 |
| 15:00-16:00 | 32 | 44% | $+248.16 | $+7.75 | $+4.00 | $+0.00 | $-57.24 |
| ALL | 387 | 58% | $+10676.31 | $+27.59 | $+172.20 | $+101.77 | $-175.04 |

### flat_top break-attack (unwindowed; N=4452)
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| 09:30-10:30 | 632 | 62% | $+16978.32 | $+26.86 | $+273.84 | $+280.19 | $-121.42 |
| 10:30-12:00 | 1019 | 44% | $+5080.00 | $+4.99 | $+81.94 | $+11.97 | $-460.06 |
| 12:00-13:00 | 696 | 39% | $-1327.97 | $-1.91 | $-21.42 | $-31.14 | $-313.47 |
| 13:00-15:00 | 1356 | 36% | $-7483.94 | $-5.52 | $-120.71 | $-109.23 | $-639.76 |
| 15:00-16:00 | 749 | 30% | $-7502.11 | $-10.02 | $-121.00 | $-108.31 | $-366.13 |
| ALL | 4452 | 41% | $+5744.30 | $+1.29 | $+92.65 | $+120.17 | $-1046.99 |

### band-pass VWAP reclaim (N=412)
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| 09:30-10:30 | 182 | 53% | $+2248.46 | $+12.35 | $+36.27 | $+8.21 | $-293.37 |
| 10:30-12:00 | 95 | 44% | $+474.42 | $+4.99 | $+7.65 | $+0.00 | $-145.96 |
| 12:00-13:00 | 44 | 32% | $-113.38 | $-2.58 | $-1.83 | $+0.00 | $-156.36 |
| 13:00-15:00 | 65 | 37% | $+374.30 | $+5.76 | $+6.04 | $+0.00 | $-193.79 |
| 15:00-16:00 | 26 | 27% | $+6.29 | $+0.24 | $+0.10 | $+0.00 | $-58.85 |
| ALL | 412 | 44% | $+2990.09 | $+7.26 | $+48.23 | $+10.97 | $-338.36 |

### v2 calibrated (N=6159)
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| 09:30-10:30 | 2206 | 29% | $+3095.52 | $+1.40 | $+49.93 | $-33.00 | $-435.68 |
| 10:30-12:00 | 1545 | 23% | $-3019.93 | $-1.95 | $-48.71 | $-59.66 | $-683.65 |
| 12:00-13:00 | 647 | 17% | $-5346.34 | $-8.26 | $-86.23 | $-74.00 | $-656.19 |
| 13:00-15:00 | 1178 | 18% | $-8974.02 | $-7.62 | $-144.74 | $-126.46 | $-679.13 |
| 15:00-16:00 | 583 | 14% | $-7520.17 | $-12.90 | $-121.29 | $-107.95 | $-441.78 |
| ALL | 6159 | 23% | $-21764.93 | $-3.53 | $-351.05 | $-370.93 | $-1685.70 |

### "No new high after 15:00" — direct test
| cohort | days | new RTH high after 15:00 | % | new high incl. premarket | % |
|---|---|---|---|---|---|
| all universe days | 729 | 98 | 13.4% | 82 | 11.2% |
| runner-days (RTH high >= +20% vs file-open ref) | 661 | 93 | 14.1% | 80 | 12.1% |
| runner-days (>= +50%) | 541 | 71 | 13.1% | 64 | 11.8% |
| closed >= +20% (strong close) | 449 | 85 | 18.9% | 74 | 16.5% |

Verdict: ~86% of runner-days make NO new high after 15:00 ET -> the article's 80-85% claim is reproduced. Power hour is a distribution/rotation window on this tape, not a breakout window. Nothing to build; the grinder's 15:59 flatten and the 15:00 bleed in every lane agree.

Hand-trace (largest |pnl| power-hour grinder): VIDA 2026-06-02 sig 19:04:30Z entry 4.5000 stop 4.2500 -> +$99.56 eod: 19:45:50 BANK 1/2 at 4.9995; 20:00:00 FLATTEN at 5.9004. (The one that worked — a 15:00-16:00 name still making highs; 31 others averaged -$5.)

## T2 — Halt-resumption retest (KT1b) at full cache
Halt = zero-trade gap >= 240s in RTH (pre-bar 13:30-19:45Z) with pre AND post bar volume >= 5x day-median 10s volume (KT1 definition, ported to the E-engine bar format). Up-halt = resumption close > pre-halt close. Retest = within 10 min, first pullback holding above the resumption bar open, enter on reclaim close > prior bar high, stop = pullback low. **351 halts detected; 36 retest entries (26 up / 10 down)** (8/14 run: 15).
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| (b) resumption retest ALL | 36 | 19% | $-1078.81 | $-29.97 | $-17.40 | $+0.00 | $-232.64 | green 6% halves $-691/$-388 -> FAIL |
| (b) up-halts | 26 | 19% | $-855.15 | $-32.89 | $-13.79 | $+0.00 | $-193.61 |
| (b) down-halts | 10 | 20% | $-223.66 | $-22.37 | $-3.61 | $+0.00 | $-51.83 |
| (a) gap-up-go (reference) | 108 | 22% | $-19.20/tr | | $-33.44 | $-14.22 | $-266.28 |
| (c) control every resumption (reference) | 296 | 21% | $-3569.01 | $-12.06 | $-57.56 | $-44.94 | $-398.27 |

Verdict: REFUTED. Under E3 (not the 8/14 +4%/EMA90 exit) and 2.4x the sample, the "patient" shape bleeds like the others: 19% win, -$30/tr; up-halts worse than down-halts. Halt-lane doctrine (arm-only converts on the 5s feed, crowns, half size — memory 8/8) is untouched by this; this is the 10s-bar mechanical retest only.
Caveat: 10s-bar halt detection is a proxy (gap>=4 min + heavy volume); LULD tape flags not in cache. E3's -1% chase on a resumption reclaim print is generous to the trade if anything.

Hand-trace (largest |pnl|): RPGL 2026-06-04 resumption 14:10:30Z open 4.0300; reclaim bar 14:21:20Z close 5.4700 > prior high 4.8700; stop 4.4200 -> -$101.98 STOP 14:36:50 (low 4.0500, fill 4.3979). Chased +35% above resumption open into a 4.42 stop that was 19% wide — the reclaim came at the top.

## T3 — Midday range breakout (flat_top break-attack, unwindowed)
Per-window table = the flat_top_break table under T1 (identical numbers). ALL windows: +$5,744.30/4452, day mean +$92.65 / median +$120.17, green 58%, halves +$5,360/+$384, worst -$1,046.99 -> FAIL (worst; and the whole edge is the open).

### 13:00-15:00 lunch-consolidation cell + survivor precondition
Survivor = every 10s close > session VWAP through 11:30-13:00 ET (15:30-17:00Z) AND price at signal >= +20% vs file-open ref.
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| cell, no precondition | 1356 | 36% | $-7483.94 | $-5.52 | $-120.71 | $-109.23 | $-639.76 | green 24% -> FAIL |
| SURVIVOR (100% closes > VWAP, gain>=+20%) | 99 | 41% | $+164.41 | $+1.66 | $+2.65 | $+0.00 | $-198.25 | green 21% halves $+199/$-35 -> FAIL |
| survivor loose (>=90% closes > VWAP) | 183 | 44% | $+206.83 | $+1.13 | $+3.34 | $+0.00 | $-147.22 |
| NON-survivor | 1257 | 35% | $-7648.35 | $-6.08 | $-123.36 | $-137.52 | $-639.76 |
| survivor, all signals >= 13:00 (incl. 15:00+) | 152 | 37% | $-425.95 | $-2.80 | $-6.87 | $+0.00 | $-288.00 |

Verdict: REFUTED as a cell; survivor precondition is a real discriminator (moves -$5.52 -> +$1.66/tr, absorbs almost none of the losers' N) but the survivor residual is a $0-median breakeven, and it goes negative once 15:00+ signals are admitted. Not shippable, not worth a shadow lane at N=99/+$164.
Caveat: "held above VWAP" at 100% strictness is harsh on thin names (one print below kills survivorship); the 90% variant is reported and agrees.

Hand-trace (best 13:00-15:00 break-attack): NPT 2026-06-08 sig 17:47:10Z level 3.5000 entry 3.5900 stop 3.1300 survivor=False -> +$324.52: 17:51:10 BANK 1/2 at 3.9885; 18:11:50 TRAIL close 8.0100 (runhi 9.0300) fill 7.9699. (The cell's best trade was a NON-survivor: it was a fresh afternoon rocket, not a lunch consolidator.)

## T4 — Afternoon VWAP reclaim, leaders-only cell (band-pass 12-30 bars, 12:00-14:30 ET)
Leader = >= +40% at 10:30 ET (14:30Z close vs file-open ref) OR top-3 gain-at-10:30 among that date's files (252 of 729 name-days qualify). Chop = >=3 VWAP side-flips in prior 120 bars -> skip. Two-bars-below = >=2 consecutive closes below VWAP before the reclaim episode.
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| unrestricted afternoon reclaim 12:00-14:30 | 95 | 33% | $+219.04 | $+2.31 | $+3.53 | $+0.00 | $-220.16 | green 29% halves $+685/$-466 -> FAIL |
| leaders-only | 24 | 21% | $-265.77 | $-11.07 | $-4.29 | $+0.00 | $-66.24 | green 6% -> FAIL |
| leaders + chop exclusion | 2 | 0% | $-34.73 | $-17.37 | $-0.56 | $+0.00 | $-21.11 | FAIL |
| leaders + chop excl + two-bars-below | 2 | 0% | $-34.73 | $-17.37 | $-0.56 | $+0.00 | $-21.11 | FAIL |
| unrestricted + chop excl + two-bars-below | 3 | 0% | $-43.54 | $-14.51 | $-0.70 | $+0.00 | $-21.11 |
| non-leaders | 71 | 37% | $+484.81 | $+6.83 | $+7.82 | $+0.00 | $-182.25 |

Verdict: REFUTED. Leaders-only INVERTS (leaders -$11/tr vs non-leaders +$7/tr) — morning leaders that lose VWAP in the afternoon are on the back side, and their reclaims are the ones that fail. The chop exclusion removes 22 of 24 leader signals: a band-pass reclaim on a leader is almost always preceded by VWAP chop, so the exclusion and the setup are nearly mutually exclusive on this tape. N=2 residual is ungradeable.
Caveat: day-gain reference is the file's first premarket bar open (no prior close in cache) — "+40% by 10:30" is measured vs ~08:00 premarket, which understates true gap-day gains and can misclassify a name that gapped before 08:00.

Hand-trace: SLND 2026-07-17 sig 17:59:00Z entry 1.0800 stop 1.0500 (gain@10:30 +51%, crosses20=2, bars_below=4) -> -$21.11 STOP 18:15:20 (low 1.0500 = stop, tie against the trade).

## T5 — ORB fair re-run (5-min and 15-min ranges, SEPARATE tests)
Trigger = first completed 1-min bar (6x10s, minute-keyed) after the OR with close > ORH AND 1-min volume >= 1.5x OR per-minute average volume AND close > RTH VWAP; window through 10:30 ET; stop = ORL (also mid-range variant); one attempt/name/day; -1% chase; E3.
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| ORB 5-min, stop=ORL | 454 | 73% | $+13436.54 | $+29.60 | $+216.72 | $+179.45 | $-227.46 | green 85% halves $+8195/$+5242 -> PASS |
| ORB 5-min, stop=MID | 454 | 61% | $+10328.01 | $+22.75 | $+166.58 | $+167.25 | $-315.23 | FAIL (worst) |
| ORB 15-min, stop=ORL | 371 | 78% | $+12114.57 | $+32.65 | $+195.40 | $+145.30 | $-160.57 | green 82% halves $+7109/$+5005 -> PASS |
| ORB 15-min, stop=MID | 371 | 67% | $+9492.15 | $+25.59 | $+153.10 | $+124.98 | $-172.16 | green 82% -> PASS |

2-slot H1-H4 portfolio walk (B.pipeline, chased E3):
- ORB 5-min ORL: N=220 (234 slot-skipped) mean +$82.86 median +$81.28 green 46/62 halves +$97.25/+$68.47/d worst **-$344.25** -> FAIL (worst only)
- ORB 15-min ORL: N=180 (191 slot-skipped) mean +$114.59 median +$125.57 green 46/62 halves +$128.06/+$101.12/d worst -$174.35 -> **PASS 5/5**

Verdict: 15-min ORB with ORL stop passes the bar both per-trade and through the 2-slot portfolio; 5-min passes per-trade and fails the portfolio only on worst-day. First ORB variant in this program to clear the bar (previous ORB runs failed on 1-min data / different triggers). BUT: this fires in the same 09:35-10:30 window, on the same names, often on the same minutes as the champion flat_top break-attack (+$16,978/632 in-window, 62%). It is a competing selection of the same open, not additive P&L. Required before any registry promotion: (1) head-to-head vs break-attack in the same 2 slots (overlap count, marginal dollars when both fire); (2) 6/25+ era-only re-grade (this table is 62 dates from 5/18); (3) volume-clause and VWAP-clause ablations (does the "fair" trigger matter or is it "buy the first push above the 15-min high on a runner"?). Registry item, not a ship.
Caveat: OR volume average uses total OR volume / minutes; the RTH VWAP is from 13:30Z (no premarket weight); 1-min bars are minute-keyed aggregates of 10s bars, minutes with missing 10s bars are thinner than a true 1-min bar.

Hand-trace (5-min ORL, largest |pnl|): PCLA 2026-06-26 OR 13:30-13:35Z; trigger minute closing 13:37:30Z entry 3.2600 stop 3.0100 -> +$556.92: 13:50:10 BANK 1/2 at 3.6219; 16:02:30 TRAIL close 10.3500 (runhi 11.5700) fill 10.2982. A +200% runner caught 2 min after the OR; one such trade per ~30 is the shape of this lane (73% win, mean $30, best $557).

## T6 — Registry quick-checks on champion signals (grinder-1030 + flat_top break-attack in-window 9:30-10:30 ET, as round G)
### (a) failed-break exit
First COMPLETED 3-min bar starting after the entry bar closes back below the base high -> market exit at that bar's last 10s close (unless already stopped/banked before it).
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| break-attack E3 default | 634 | 62% | $+17031.01 | $+26.86 | $+274.69 | $+280.19 | $-121.42 |
| break-attack + failed-break exit | 634 | 46% | $+10527.31 | $+16.60 | $+169.80 | $+167.30 | $-247.09 |
Rule fired 219/634; on those trades rule -$4,716.58 vs default +$1,787.13. REFUTED: the first 3-min bar dipping back under the base is a shakeout on this tape more often than a failure; E3's stop at base low already handles the real failures.
Hand-trace (first firing): HIVE 2026-05-18 sig 13:45:50Z level 3.8100 entry 3.8350 stop 3.5000 -> rule -$18.33 fbexit@13:50:50 (close 3.7501 < 3.81, fill 3.7313) vs default -$50.45 stop@14:18:10. (This one the rule saved $32; the cohort lost $6,504.)

### (b) no-progress rule (exit at 15 min if run-high < entry + 1R and not yet banked)
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| grinder E3 default | 387 | 58% | $+10676.31 | $+27.59 | $+172.20 | $+101.77 | $-175.04 |
| grinder + no-progress-15 | 387 | 41% | $+3927.35 | $+10.15 | $+63.34 | $+25.55 | $-96.21 |
| break-attack E3 default | 634 | 62% | $+17031.01 | $+26.86 | $+274.69 | $+280.19 | $-121.42 |
| break-attack + no-progress-15 | 634 | 40% | $+2683.47 | $+4.23 | $+43.28 | $+42.07 | $-191.48 |
Grinder: fired 222/387, those trades rule -$913.27 vs default +$5,835.69. Break-attack: fired 342/634, rule -$3,221.00 vs default +$11,126.55. REFUTED hard: >half of both lanes' trades are "no progress" at 15 min and they carry the majority of the lane's dollars. Time-stops kill the E3 runner shape.

### (c) break-attack volume clause (signal-bar $vol vs prior-10-bar median $vol)
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
| >=1.5x prior-10 median $vol | 487 | 62% | $+12008.69 | $+24.66 | $+193.69 | $+202.64 | $-220.23 |
| <1.5x | 147 | 64% | $+5022.33 | $+34.17 | $+81.01 | $+73.22 | $-155.50 |
REFUTED: no discrimination (win 62% vs 64%; per-trade the low-volume cohort is better). Do not add a volume clause to break-attack.

## Global caveats
- 62-date full cache includes 5/18-6/24 pre-window dates; prior rounds used 36 dates 6/25-8/14. Rows here are NOT reconcilable one-for-one with rounds F/G (different denominator); the engine, exits and detectors are byte-identical (parity checks pass).
- Per-trade tables have no capacity; only the T5 portfolio rows walked H1-H4 with 2 slots.
- Universe = scanner runners only (survivorship: every file is a name that ran); day-gain refs are vs ~08:00Z premarket open, not prior close.
- 10s bars: halts are gap-proxied; entries fill at close+1%, which is generous on thin prints.
- Everything here is a per-signal grade; nothing was convened, nothing ships. T5 (15-min ORB) is the only new registry candidate and carries the overlap-with-break-attack question as its blocking pre-test.
