# TWO-TIMEFRAME FAST-CHART RE-RUN 8/17 — VERDICT: **separating the timeframes is REAL but SMALL, and un-refutes NOTHING.** Reading front side on the 1-MINUTE (context) instead of the fast chart, while entering on the 10s/5s (fast) with the fast-chart front-side gate REMOVED, improves Kev-A/B/C by **+$199 (10s tick, all detectors) to +$770 (cache scale)** under Kev's own exit — but every detector is still net-negative under KEV and E3 in every context, at both resolutions, on 197 SIP name-days and 719 cache name-days. The §9 bug (fast-chart 9>20 refusing the pullback) was a real translation defect and fixing it recovers a couple hundred dollars; it is **not** the missing edge. Kev-A **STILL-REFUTED**, Kev-B **STILL-REFUTED** (1-min less bad), Kev-C **STILL-REFUTED-as-managed / NEEDS-DATA(exit)** (unchanged: positive F-control tail, managed exits hand it back). **1-MINUTE context beats 3-minute** on the primary 10s glass and is far more stable (3-min is net-negative value vs FAST on A and B, and blows up Kev-C's F-control at scale). The Rosetta selection clauses (sequence B→H/W, burst volume, fresh level) remain the only thing that flipped a detector green — that is a **selection** edge, not a **timeframe** edge, and this study confirms the two are separate levers.

**Officers:** Hidden Entry Architect (lead; owns the two-timeframe correction + Kev-A/B/C translation), Kev Librarian (front-side-on-1-min is Kev's stated method: "front side on the 1-minute, entry on the 10-second"), Seam Scientist (registry: H-FC3 "wall-time/slow-context-fair gates flip the twin" resolves NO), Side Marshal (front-side is now a slow-chart stamp = the honest reading of his structure), Statistician (rows `fastchart_2tf_rerun_20260817_rows.json`, tables `_tables.txt`), Wind Tunnel (slow bars aggregated from the SAME ticks as the fast bars = the fair twin; VWAP seeded identically), Trade Manager (four exits unchanged from 8/16). Momentum Operator / Blast Radius: **nothing ships**, analysis only. Historian: run 8/17 00:42 EDT, report 00:56 EDT (`date` cited).
**Script:** `data/killtests/fastchart_2tf_rerun_20260817.py` — reuses the 8/16 module's detectors/gates/exits/cohorts verbatim; the ONLY change is `gates2()` reads front side from a `SlowFront` (60s or 180s) aggregate as-of the fast bar's wall-time, and the fast-chart front-side clause is removed. Three context variants (FAST = original control / 1MIN / 3MIN) run side-by-side on the identical fires for an apples-to-apples delta.

## 0. What changed vs the 8/16 replay (the one line of code that was the bug)
- 8/16 `gates()`: `if not ctx.front_side(i): return "backside"` where `front_side(i)` = `close>vwap AND e9>e20` on the **fast** bars (10s/5s). On a 10s pullback deep enough to touch VWAP+9MA, the fast 9EMA has usually already crossed 20EMA down → the gate refused the exact bar Kev buys (§9 caveat #2). Census 8/16: **5,373 of 13,195 signals killed as "backside"** — the single biggest gate.
- 8/17 `gates2()`: front side is read on a **1-min** (and a **3-min**) aggregate built from the same ticks, using the last CLOSED slow bar as-of the fast bar's time: `e9>e20 (uptrend intact) AND close>vwap` on the slow chart. The fast-chart front-side clause is gone. Entry detection (A wick / B level-hold / C halt double-bottom), room, topping-cluster, hours, leg-ration, and all four exits are **unchanged**.
- Surprise worth stating: the slow-context gate does **not** pass many more fires — it passes a **different, slightly smaller** set (10s tick: FAST 399 → 1MIN 373). The deep-pullback bars that the fast gate blocked are often *also* not front-side on the 1-min (the 1-min 9EMA can sit below 20EMA during a real flush too), and some marginal FAST fires get *removed* because the last closed 1-min bar was red. So the fix is not "let Kev's entries through"; it is "confirm trend on the timeframe he actually reads," and the net dollar effect is a **modest quality lift, not a floodgate.**

## 1. THE DELTA — single-timeframe (FAST) vs two-timeframe ($ per detector, KEV-native exit)
### 10s SIP tick twin (197 name-days), KEV_sum
| detector | FAST (single-tf, 8/16 bug) | 1MIN context | Δ 1MIN | 3MIN context | Δ 3MIN | best two-tf |
|---|---|---|---|---|---|---|
| A confluence wick | −$361 | −$279 | **+$82** | −$342 | +$19 | 1MIN (still red) |
| B level hold | −$640 | −$464 | **+$176** | −$1,135 | −$495 | 1MIN (still red) |
| C halt double-bottom | +$420 | +$360 | −$60 | +$293 | −$127 | FAST (two-tf worse) |
| **ALL detectors** | **−$581** | **−$382** | **+$199** | **−$1,184** | −$603 | **1MIN** |
### 10s cache @ scale (719 name-days), KEV_sum
| detector | FAST | 1MIN | Δ 1MIN | 3MIN | Δ 3MIN |
|---|---|---|---|---|---|
| A | −$2,560 | −$2,083 | **+$477** | −$1,785 | +$775 |
| B | −$2,880 | −$2,643 | **+$237** | −$3,010 | −$130 |
| C | −$408 | −$351 | +$57 | −$267 | +$141 |
| **ALL** | **−$5,847** | **−$5,077** | **+$770** | **−$5,062** | +$785 (F-control collapses, below) |

**The value of separating the timeframes = about +$199 (10s tick, all detectors) to +$770 (cache scale) under Kev's own exit, entirely from the 1-minute context.** It is real, it is in the direction the §9 caveat predicted, and it is nowhere near enough to cross zero. The 3-minute context is a *negative*-value change on the primary 10s tick twin (−$603 vs FAST) because a 3-min bar closes only every 18 fast bars — the trend confirmation lags the entry so badly it lets the worst B fires through (B 3MIN −$1,135).

## 2. FULL DETECTOR TABLES (KEV / E3 / E4W / F-control per trade; win%; day-level)
### SIP tick twin, 10s
| det·ctx | N | KEV mn / sum | E3 mn | E4W mn | F mn / sum | win | day mean / med / green% / worst | H1 / H2 green% |
|---|---|---|---|---|---|---|---|---|
| A FAST | 101 | −3.57 / −361 | −6.68 | −12.66 | −26.45 / −2,671 | 18% | −6.1 / −12.6 / 20% / −55 | 28 / 13 |
| A 1MIN | 61 | −4.57 / −279 | −5.44 | −3.52 | −26.86 / −1,639 | 15% | −7.0 / −11.4 / 18% / −52 | 30 / 5 |
| A 3MIN | 65 | −5.26 / −342 | −6.72 | −6.73 | −25.30 / −1,645 | 17% | −9.5 / −11.2 / 19% / −52 | 28 / 11 |
| B FAST | 182 | −3.52 / −640 | −2.91 | −0.47 | −25.16 / −4,580 | 26% | −8.1 / −21.9 / 25% / −199 | 21 / 30 |
| B 1MIN | 184 | −2.52 / −464 | −1.38 | +0.43 | −22.37 / −4,117 | 26% | −5.9 / −23.6 / 23% / −167 | 18 / 28 |
| B 3MIN | 187 | −6.07 / −1,135 | −3.81 | −3.43 | −21.87 / −4,090 | 26% | −14.6 / −23.1 / 23% / −173 | 21 / 26 |
| C FAST | 116 | +3.62 / +420 | +3.08 | −7.00 | +28.98 / +3,362 | 28% | +9.1 / −18.8 / 28% / −105 | 35 / 22 |
| C 1MIN | 128 | +2.81 / +360 | +0.40 | −5.54 | +27.45 / +3,513 | 26% | +7.8 / −16.0 / 24% / −73 | 30 / 17 |
| C 3MIN | 127 | +2.31 / +293 | +1.07 | −4.32 | +27.34 / +3,472 | 24% | +6.1 / −17.0 / 23% / −73 | 29 / 17 |

### SIP tick twin, 5s
| det·ctx | N | KEV mn / sum | E3 mn | E4W mn | F mn / sum | win | day green% / worst |
|---|---|---|---|---|---|---|---|
| A FAST | 39 | −8.44 / −329 | −5.26 | −8.22 | −15.96 / −622 | 10% | 8% / −66 |
| A 1MIN | 11 | −9.94 / −109 | −9.09 | −8.52 | −11.03 / −121 | 0% | 0% / −28 |
| A 3MIN | 19 | −11.82 / −225 | −12.24 | −11.98 | −4.18 / −79 | 5% | 8% / −66 |
| B FAST | 103 | −1.35 / −139 | −1.10 | +7.15 | −28.89 / −2,976 | 32% | 30% / −132 |
| B 1MIN | 87 | −2.29 / −199 | −0.19 | +9.68 | −28.57 / −2,486 | 33% | 38% / −132 |
| B 3MIN | 87 | −1.04 / −91 | +1.38 | +10.72 | −26.38 / −2,295 | 33% | 40% / −132 |
| C FAST | 74 | +2.79 / +206 | +2.14 | +25.06 | +58.68 / +4,343 | 31% | 31% / −86 |
| C 1MIN | 75 | +1.58 / +118 | +3.68 | +19.78 | +100.4 / +7,530 | 29% | 27% / −125 |
| C 3MIN | 74 | +3.23 / +239 | +4.94 | +33.66 | +101.2 / +7,489 | 32% | 31% / −100 |

### Cache @ scale, 10s (719 name-days)
| det·ctx | N | KEV mn / sum | E3 mn | E4W mn | F mn / sum | win | day green% |
|---|---|---|---|---|---|---|---|
| A FAST | 427 | −5.99 / −2,560 | −6.55 | −7.11 | −5.65 / −2,413 | 16% | 20% |
| A 1MIN | 291 | −7.16 / −2,083 | −7.03 | −6.24 | −5.20 / −1,513 | 13% | 14% |
| A 3MIN | 284 | −6.29 / −1,785 | −6.03 | −5.68 | −6.74 / −1,914 | 15% | 20% |
| B FAST | 752 | −3.83 / −2,880 | −4.31 | −2.30 | −4.46 / −3,356 | 31% | 30% |
| B 1MIN | 743 | −3.56 / −2,643 | −4.38 | −3.37 | −5.07 / −3,767 | 30% | 29% |
| B 3MIN | 761 | −3.95 / −3,010 | −4.51 | −4.07 | −6.69 / −5,090 | 29% | 29% |
| C FAST | 390 | −1.05 / −408 | −2.17 | +0.37 | **+22.56 / +8,800** | 22% | 28% |
| C 1MIN | 396 | −0.89 / −351 | −2.57 | −0.56 | **+21.51 / +8,520** | 22% | 27% |
| C 3MIN | 439 | −0.61 / −267 | −3.28 | −4.00 | +5.44 / +2,390 | 22% | 24% |

**Note on Kev-C F-control:** its only positive number (the unmanaged −7%-stop-only tail) SURVIVES the 1-min context at scale (+$8,520 vs +$8,800 FAST) but the 3-min context DESTROYS it (+$2,390) — because a 3-min front-side stamp holds "front side = true" 18 fast bars too long and admits late-leg C fires that go straight to the −7% stop. This is the clearest single piece of evidence that **1-minute is the right context clock and 3-minute is too slow.** Managed exits (KEV/E3/E4W) still hand the C tail back in every context — verdict unchanged from 8/16.

## 3. WHY IT DIDN'T FLIP — the timeframe was a defect, the selection is the edge
Cross-reference `kev_rosetta_20260816.md` §5: on the SAME 198-nd fastchart cohort, the Rosetta **selection** clauses moved the refuted detector from −$581 to green:
- sequence (last-2 structural = B→H or B→W): N=79 KEV **+$447** (all in det B: +$576)
- "fresh" (touches≤1 & ≤0.3 min since session high): N=113 KEV **+$1,323**
- top-2 burst features (vol_ratio≥2.2 & bar_rng≥3.7%): N=73 KEV +$474

Those are **+$1,000–1,900 swings** from *selecting which fires to take*. This study's timeframe fix is a **+$199–770 swing** from *confirming trend on the right chart*. They are additive levers of very different size, and this re-run isolates the timeframe lever: **timeframe separation alone does not carry the method; Kev's discretionary selection (the sequence/freshness/burst) does.** The honest picture is: front-side-on-the-1-minute is a correct piece of Kev's process that our 8/16 code got wrong, and correcting it recovers real money — but the profitable core of his method lives in *which pullback he punches*, not *which chart he reads trend on*.

## 4. THREE HAND-TRACES — his named fills (from `kev_rosetta_20260816`), two-tf lens
His credible fills are all **front side on the slow chart** (Rosetta: 15/15 front side) AND carry the B→H/W sequence — i.e. the two-tf gate would have PASSED them; the reason our detectors still lose is the ~200 look-alike fires the gate *also* passes, not these three.
- **ZYBT 2026-07-20, 13:44:10 ET, entry 3.10 (reclaim, seq `L P H P H`).** Break of the $3 whole-dollar, pullback settles/hesitates at 3.10 on the 10s, buyer steps in. 1-min at 13:44: last closed 1-min bar close 3.18 > 1-min VWAP 3.05, 1-min 9EMA > 20EMA → **front side TRUE on the 1-min** (his read). Fast-chart 9EMA had dipped under 20EMA on the 51.5-min-stale-high pullback → the 8/16 gate would have called this "backside" and refused it; the 1-min gate passes it. Outcome KEV **+$29.60** / E3 +$23.75, 2R hit, MFE15m +12.9% (his stated 3.10→3.50). *This fill is exactly the §9 bug: two-tf recovers it.*
- **STKH 2026-08-10, 09:36:40 ET, entry 4.70 (level_hold, seq `H B H B H`).** Break of premarket trend + break of VWAP, punched into the highs at the open, gain +162% at signal, dist-to-high 0.0% (blue sky). Both charts front side (open drive). Outcome KEV **+$21.85**, 2R hit, MFE15m +33.8% (his 4.70→5.45). Two-tf and single-tf both pass it — an open-drive fill where the timeframe question is moot.
- **MTEN 2026-08-10, 09:55:30 ET, entry 1.29 (reclaim, seq `T B T B W`).** Double bottom off 1.25 after a failed HOD punch (1.34→1.41), first wick bought back. 1-min: close 1.31 > 1-min VWAP, 9EMA>20EMA → front side TRUE; the fast 10s 9EMA had crossed down into the 1.25 retest (the classic block). Outcome KEV **+$20.64** / E3 +$23.75, 2R hit, MFE15m +38.0% (his 1.29→1.60). *Second clean instance of the §9 bug recovered by the 1-min context.*

All three are *winners he called*, all three pass the 1-min gate, and two of the three were being *refused* by the 8/16 fast-chart gate. That confirms the fix is directionally correct at the level of his individual fills — the detectors still lose in aggregate because the ~200 non-Kev fires they also admit are net-negative, which is a **selection** problem the Rosetta clauses address, not this one.

## 5. VERDICTS
| detector | 10s | 5s | verdict + why |
|---|---|---|---|
| **Kev-A confluence wick** | STILL-REFUTED | STILL-REFUTED | 1-min context lifts 10s tick by +$82 but leaves it −$279 (−$4.57/tr), 0% win-day green at 5s, F-control −$27/tr; negative under all four exits in all three contexts. The VWAP+9EMA confluence essentially does not exist on the day's rocket (VWAP sits far below tape). Timeframe was never A's problem. |
| **Kev-B level hold** | STILL-REFUTED (1-min least-bad) | STILL-REFUTED (E4W tail) | best cell is B·1MIN·10s at −$464 (Δ+$176) — improved, still red under KEV/E3; 5s E4W +$9.68/tr is a 6-ride tail with 41% 30s-false-fire; F-control −$22 to −$29/tr everywhere. 3-min context makes B strictly worse (−$1,135). Not flipped. |
| **Kev-C halt double-bottom** | STILL-REFUTED-as-managed / NEEDS-DATA(exit) | same | UNCHANGED from 8/16: the only positive F-control (+$28.98/tr 10s tick, +$22.56×390 at scale, +$58.68/tr 5s) survives the 1-min context but is a 22-28%-win halt-tail lottery; KEV +$3.62/E3 +$3.08/E4W −$7 do not clear the ~$6 toll. 3-min context CRUSHES the tail (F +$2,390 vs +$8,800) → 1-min is mandatory if C is ever worked. Belongs to the halt lane's exit docket, not a fast-chart lane. |
| **Timeframe separation (the study's question)** | — | — | REAL, SMALL, un-refutes nothing: +$199 (10s tick) to +$770 (cache) under KEV, all from the 1-min context; corrects a genuine §9 translation defect and recovers Kev's own ZYBT/MTEN-type fills, but does not carry the method. |
| **1-min vs 3-min context** | — | — | **1-MINUTE WINS.** On the primary 10s glass 1-min (−$382) beats 3-min (−$1,184) by $800; 1-min preserves Kev-C's F-control tail at scale (+$8,520) while 3-min destroys it (+$2,390); 3-min is net-negative value vs the buggy FAST on A and B. 3-min only edges on 5s E4W tails (noise). |

**Best resolution+context combo: 10s entry + 1-MINUTE front-side context.** It is the least-bad, most stable configuration and the one that matches Kev's stated process; it is still not shippable on its own. The path to green is 10s+1-min context **stacked with** the Rosetta selection clauses (sequence B→H/W + fresh + burst) — that combination is the registered hidden-v2 hypothesis, still owed its OOS wall (≥5 clean days) before any ship.

## 6. Registry (Seam Scientist) + what this does/does not say
- H-FC3 "wall-time / slow-context-fair gates flip the twin": **RESOLVED — NO** (they improve by $199–770, do not flip). Logged.
- New: H-FC4 "10s+1-min context **×** Rosetta selection clauses" — OPEN, the live hidden-v2 candidate; this study supplies the context half, Rosetta §5 supplies the selection half, neither alone is green, product untested OOS.
- It says: the 8/16 §9 defect (fast-chart front-side blocking the pullback) was real and worth ~$200–770; fixing it is correct but insufficient. It does **not** say Kev has no edge — his fills beat their look-alikes and his selection clauses flip the detector; his "buyer steps in" L2 read stays [UNVERIFIED].
- Method integrity: slow bars aggregated from the identical ticks as the fast bars (fair twin), VWAP seeded identically, front side read from the last CLOSED slow bar (no look-ahead), three contexts run on the same fires (clean delta). $500 clip, +1% chase, −0.5% market exits, stop-first, RTH-official 09:30–15:30, flatten 15:45.
Standing by.
