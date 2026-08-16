# ROCKET ANATOMY STUDY — 2026-08-16
**Officers:** Rocket Rider (lead) + Hidden Entry Architect; Wind Tunnel (chain reuse), Statistician (rows JSON), Convexity Trader (mean-after-costs), Strength Ombudsman (see verdict), Historian (SCKT/XHD context). Analysis only — no bot edits.
**Script:** `data/killtests/rocket_anatomy_20260816.py` -> `rocket_anatomy_20260816_RESULTS.txt` + `_rows.json` (every leg, every trade). Runtime ~5 min.
**Chain:** flatten_parity_20260816 (LIVE parity: 15:30 no-entry, 15:45 flatten) -> S -> G -> F -> C -> B -> E, unchanged. E3 exits, +1% chase slip, 0.5% exit market, $500/position, halt_rule on. RTH bars only (PRE separate by doctrine).
**Universe caveat (applies to every number below, same as every study on this chain):** 729 *runner-days* = names that FINISHED as top gainers. Long-side entries on this universe carry survivorship tailwind; the honest bar is relative (vs the O-config champion +$157/day, 89% green) not absolute.

## HEADLINE
- **724 vertical legs** (>=25% in <=5 min on >=3x volume) on 288 of 729 name-days (40%), 60 of 62 dates; median leg +31%, median 220s, median 10x volume. **45% are followed by a LULD halt within 10 min**; 101 legs START on a halt-resumption bar; 0 legs contain a halt gap inside (halts end legs, they do not build them in this cache).
- **The 60 seconds before: mostly nothing.** 78% of pure-tape rockets show none of the tested precursors. Best enrichment = `f_at_new_high` (window broke the pre-window session high, close within 2% of it) at **2.79x** base rate — precision still only 4.7% (1 fire in 21 becomes a leg). Coil (0.21x) and volume-prelude (0.17x) are ANTI-signals: rockets do not launch from quiet coils here.
- **(i) ANTICIPATE (buy the new-high fire, structure stop):** 3539 fires, 42% win, **+$8.41/trade**, 2-slot portfolio **+$127.82/date, 37/62 green, OOS +$206 / +$49**, worst date -$705. Positive but a decaying second half and a heavy tail; the "rocket" it catches is incidental (40 of 3539 fires are real liftoffs).
- **(ii) FIRST-PULLBACK after the leg (v2-style):** 456 trades, **22% win, -$11.59/trade, -$85/date, 12/60 green, both OOS halves red.** REFUTED as specified. Its only positive pocket is the halted names (Part 4).
- **(iii) DAY-2 RELOAD:** only 30 of 288 rocket names have a day-2 in the cache (universe = runner-days, so day-2 must itself be a runner); 24 trades, 29% win, +$4/trade, +$1.71/date; control template on all day-2+ name-days +$8/date. Under-powered, flat, not a lane.
- **Halt interaction inverts Kev's caution for THIS entry:** pullback trades on halted legs +$3/trade (N=122); the 36 trades held ACROSS a halt made +$60/trade (28 trail exits — the halt was UP); the 334 pullback trades on non-halted legs lost -$17/trade. In this cache "stop trading the halts" would have removed the only profitable slice of the pullback lane. (Halt gaps here are >=4-min zero-trade gaps on the tape, not exchange LULD stamps — resolution caveat.)

## FULL RESULTS (verbatim run output)

# ROCKET ANATOMY STUDY — 2026-08-16 (Rocket Rider + Hidden Entry Architect)
universe: 729 files, 729 RTH day-files (>=60 bars), 62 dates 2026-05-18..2026-08-14; RTH only; chain FP->S->G->F->C->B->E unchanged, E3, +1% entry slip, 0.5% exit mkt, $500, LIVE flatten 15:45, halt_rule on
leg def: >=25% low->high within <=300s (30x10s) AND leg per-slot volume >= 3x prior-20-min per-slot avg; liftoff = earliest bar whose low is the base with no lower low inside the leg; one leg per top.

## PART 1 — CENSUS: 724 vertical legs on 288 name-days of 729 (40%), across 60 of 62 dates
leg size: median +31%, p90 +47%, max +109%; median duration 220s; median vol-multiple 10.1x

### legs per date
| date | legs | names |
|---|---|---|
| 2026-05-18 | 2 | GOVX, RPGL |
| 2026-05-19 | 6 | CNEY, CODX, PHOE, WNW |
| 2026-05-20 | 9 | HCWB, JUNS, RKDA, UZX |
| 2026-05-22 | 8 | PCLA, QTEX, RYOJ |
| 2026-05-26 | 5 | AIMD, BRAI, UZX |
| 2026-05-27 | 4 | ASTC, GNTA, RCT, RYOJ |
| 2026-05-28 | 9 | AKTX, MASK, NTCL, TOPP |
| 2026-05-29 | 9 | CDT, EEIQ, IOTR, NEXR, YMAT |
| 2026-06-01 | 9 | ABTS, ANY, DBGI, FOFO, JZXN |
| 2026-06-02 | 4 | DXST, LASE, STAK |
| 2026-06-03 | 10 | ATPC, HTCO, HUBC, JLHL, LASE, WCT |
| 2026-06-04 | 12 | EDHL, FOXX, INDP, NEXR, SDOT, STI, VERU |
| 2026-06-05 | 19 | BCDA, BGMS, RMSG, SPHL, STAK, SUGP, VVOS, YXT |
| 2026-06-08 | 65 | BYAH, IFBD, INHD, MTEN, NPT, PAVS, PN, RYET, SMTK, SUNE |
| 2026-06-09 | 62 | AHMA, AZI, ELPW, EPSM, GLE, MTEN, PAVS, RGNT, SLGB, YOUL |
| 2026-06-10 | 37 | CHOW, CIIT, CPOP, DSY, FLD, GCDT, GLE, KMRK, SDOT, VSME, WCT |
| 2026-06-11 | 29 | ADIL, CCHH, FXHO, GELS, GLXG, ONEG, PPCB, QH, RUBI |
| 2026-06-12 | 16 | BYAH, CAST, CDTG, CIIT, CUPR, ONEG, RUBI |
| 2026-06-15 | 17 | CUPR, GELS, GLXG, HQWWW, HUBC, MTEN, PRFX, RGNT, WLDS |
| 2026-06-16 | 11 | CCTG, CRE, CRVO, FTHM, IVDA, NIVF, SUGP |
| 2026-06-17 | 11 | EHGO, HQWWW, ICCM, VRM, YMAT |
| 2026-06-18 | 9 | ATPC, CDT, LNKS, THH, WKSP |
| 2026-06-22 | 4 | EHGO, ENTX, KMRK, SKYQ |
| 2026-06-23 | 10 | CGTL, FCUV, GITS, HSCS, RDGT, XCH |
| 2026-06-24 | 5 | EHGO, SCAG, STFS |
| 2026-06-25 | 11 | ILLR, PRFX, TNON, VNTG, XCH |
| 2026-06-26 | 13 | CNEY, IVF, LICN, LVWR, RYOJ, SDOT, WSHP, ZCMD |
| 2026-06-29 | 10 | AZI, JEM, LGCL, ZCMD |
| 2026-06-30 | 9 | CELZ, CIGL, LGCL, PAVS |
| 2026-07-01 | 5 | DXF, EHGO, JEM, LHAI, TC |
| 2026-07-02 | 3 | CCTG, GMEX |
| 2026-07-06 | 7 | BJDX, FXHO, KIDZ, TDTH, ZCMD |
| 2026-07-07 | 1 | NPT |
| 2026-07-08 | 2 | BIYA |
| 2026-07-10 | 7 | CPHI, HAO, JZXN, YMAT |
| 2026-07-13 | 3 | SOBR |
| 2026-07-14 | 5 | CNEY, HODO, LEDS, TGHL, VEEE |
| 2026-07-15 | 5 | CPHI, SOBR |
| 2026-07-16 | 2 | STAK |
| 2026-07-17 | 2 | GIPR, TRUG |
| 2026-07-20 | 3 | YOUL |
| 2026-07-21 | 28 | CCTG, CPHI, DFNS, IPW, JZXN, SLGB, VIVK |
| 2026-07-22 | 7 | INLF, MTEN, ZCMD |
| 2026-07-23 | 8 | CJMB, EHGO, PAVS, SORA, VIVK, WLDS |
| 2026-07-24 | 15 | CJMB, CNET, STAK, TC, WLDS |
| 2026-07-27 | 9 | BIYA, FIEE, LVWR, MTNB |
| 2026-07-28 | 15 | AMSS, EGG, LGHL, STKH |
| 2026-07-29 | 10 | AIXI, AMIX, FIEE, GWAV, MSS |
| 2026-07-30 | 3 | STKH, YAAS |
| 2026-07-31 | 18 | CIGL, CUPR, FCHL, FCUV, LFS, MSGY, ZEO |
| 2026-08-03 | 12 | EZRA, FUSE, LNAI, SDST, STKH, TAOP |
| 2026-08-04 | 3 | ADGM |
| 2026-08-05 | 10 | ASTC, YXT, ZCMD, ZYBT |
| 2026-08-06 | 14 | AZI, BYAH, ENSC, PN, WLDS, WYHG, XHLD |
| 2026-08-07 | 34 | ATGL, HUIZ, LZMH, WAFU, WFF, WWR, YJ |
| 2026-08-10 | 19 | ARTW, BCARU, MTEN, PCLA, RDGT, STKH, XHLD |
| 2026-08-11 | 3 | GLE, HXHX |
| 2026-08-12 | 21 | BIVI, BOXL, BQ, CHOW, SBEV, VBIO, WCT |
| 2026-08-13 | 23 | BBBY.WS, BGIN, BYSI, DFSC, HCTI, INHD, PSQH, XHG |
| 2026-08-14 | 2 | GIPR |

### legs per name (top 15)
| name-day | legs | biggest | halted after |
|---|---|---|---|
| CPHI 2026-07-21 | 19 | +58% | 16 |
| PAVS 2026-06-09 | 16 | +68% | 11 |
| NPT 2026-06-08 | 13 | +92% | 5 |
| BYAH 2026-06-08 | 12 | +95% | 8 |
| MTEN 2026-06-09 | 12 | +73% | 8 |
| AHMA 2026-06-09 | 11 | +58% | 7 |
| HUIZ 2026-08-07 | 11 | +50% | 7 |
| BBBY.WS 2026-08-13 | 10 | +109% | 0 |
| MTEN 2026-06-08 | 10 | +52% | 8 |
| GELS 2026-06-11 | 9 | +34% | 3 |
| WFF 2026-08-07 | 9 | +52% | 8 |
| STAK 2026-07-24 | 8 | +45% | 5 |
| CIGL 2026-07-31 | 7 | +52% | 4 |
| INHD 2026-06-08 | 7 | +46% | 4 |
| AZI 2026-06-09 | 6 | +55% | 2 |

### time-of-day (ET)
| window | legs | share |
|---|---|---|
| 09:30-09:45 | 121 | 17% |
| 09:45-10:00 | 57 | 8% |
| 10:00-10:30 | 84 | 12% |
| 10:30-11:30 | 120 | 17% |
| 11:30-13:00 | 132 | 18% |
| 13:00-15:00 | 155 | 21% |
| 15:00-16:00 | 55 | 8% |

### day-1 vs day-2+ (name in manifest on a prior date within 5 days)
day-1 name-days 606: 628 legs (1.04/name-day) | day-2+ name-days 123: 96 legs (0.78/name-day)

### halt-built legs: 101 of 724 legs START on a halt-resumption bar (prior bar >=4 min earlier); 0 legs contain a >=4-min gap INSIDE the leg (the 'instant squeeze' = mostly a halt gap-up); 623 legs are pure-tape (no gap at start or inside)

### halts: 324 of 724 legs (45%) followed by a >=4-min zero-trade gap within 10 min of the leg high
of legs >=+50% (59): 28 halted (47%)

## PART 2 — THE 60 SECONDS BEFORE (6 bars preceding liftoff) vs base rate over ALL comparable RTH bars
rockets with a comparable 6-bar window: 526 (sparse-tape/too-early excluded: 198); comparable base bars: 1382549
| precursor | among rockets | base rate (all bars) | enrichment | fires -> leg starts within 5 min (precision) |
|---|---|---|---|---|
| a_coil | 20 (3.8%) | 248855 (18.0%) | 0.21x | 504/248855 (0.20%) |
| b_vwap_hold | 33 (6.3%) | 42127 (3.0%) | 2.06x | 954/42127 (2.26%) |
| c_prior_high_test | 47 (8.9%) | 56468 (4.1%) | 2.19x | 1355/56468 (2.40%) |
| d_vol_prelude | 5 (1.0%) | 75383 (5.5%) | 0.17x | 172/75383 (0.23%) |
| f_at_new_high | 33 (6.3%) | 31084 (2.2%) | 2.79x | 1462/31084 (4.70%) |
| e_none | 409 (77.8%) | 995193 (72.0%) | 1.08x | 9107/995193 (0.92%) |
best (by enrichment, e_none excluded): f_at_new_high at 2.79x, precision 4.70%

## PART 3 — THREE ENTRY PHILOSOPHIES (E3, +1% chase slip, LIVE flatten, halt_rule on, $500)
| philosophy | N | wins | total $ | $/trade | $/date (62 dates) | OOS $/date first-31 / last-31 | worst date |
|---|---|---|---|---|---|---|---|
| (i) ANTICIPATE on f_at_new_high (all fires) | 3539 | 1492 (42%) | $+29754.56 | $+8.41 | $+479.91 (43/62 trade-days green) | $+597.34 / $+362.48 | $-732.78 |
|     ..of which fired at a real liftoff (foresight, NOT tradeable) | 40 | 31 (78%) | $+2171.19 | $+54.28 | $+35.02 (21/24 trade-days green) | $+35.15 / $+34.89 | $-172.65 |
|     (i) 2-SLOT portfolio (first-fill-wins, capacity 2) | 1215 | 531 (44%) | $+7924.54 | $+6.52 | $+127.82 (37/62 trade-days green) | $+206.33 / $+49.30 | $-705.08 |
| (ii) FIRST-PULLBACK after leg (>=3% dip, higher-low bar, <=3 min) | 456 | 99 (22%) | $-5286.40 | $-11.59 | $-85.26 (12/60 trade-days green) | $-108.23 / $-62.30 | $-752.24 |
|     (ii) 2-SLOT portfolio | 455 | 98 (22%) | $-5335.72 | $-11.73 | $-86.06 (12/60 trade-days green) | $-109.82 / $-62.30 | $-752.24 |
  pullback found on 529 of 724 legs (195 legs: no qualifying pullback within 3 min = kept running/halted/faded straight)
| (iii) DAY-2 RELOAD (>=5% push, VWAP-holding pullback, 9:30-10:30) | 24 | 7 (29%) | $+106.16 | $+4.42 | $+1.71 (5/18 trade-days green) | $+6.87 / $-3.44 | $-33.58 |
  rocket name-days 288: next-day bars in cache for 30 (day-2 not in the runner universe: 258); setup found 24, no setup 6
|     control: same template on ALL day-2+ name-days | 100 | 31 (31%) | $+512.26 | $+5.12 | $+8.26 (22/47 trade-days green) | $+3.84 / $+12.69 | $-80.34 |

## PART 4 — HALT INTERACTION (first-pullback philosophy)
legs followed by halt: 324; pullback entry taken on 122; entered BEFORE the halt and still in across it (trapped): 36
pullback trades on halted legs: N=122 total $+380.58, mean $+3.12, wins 45
trapped-across-halt: N=36 total $+2169.62, mean $+60.27, wins 28; exits: {'stop': 8, 'trail': 28}
pullback trades on NON-halted legs: N=334 total $-5666.98, mean $-16.97, wins 54
pullback trades on halted legs on SERIAL-halt days (>=2 gaps): N=109 total $+459.64, mean $+4.22

## HAND TRACES (one per philosophy; sim log verbatim)
SCKT in cache: [('SCKT', '2026-08-10')]; SCKT legs found: 0; XHD in cache: []

rocket: NPT 2026-06-08 liftoff 15:40:00 base 2.2900 -> top 3.5800 at 15:44:00 (+56% in 240s, 3.6x vol), halt after: False, precursors: ['e_none']
  6 bars before liftoff (t o h l c v):
    15:39:00 2.4100 2.4200 2.2600 2.2600 152451
    15:39:10 2.2750 2.3700 2.2600 2.3300 136515
    15:39:20 2.3100 2.3600 2.3000 2.3001 59905
    15:39:30 2.3100 2.3500 2.2800 2.3350 74987
    15:39:40 2.3400 2.3800 2.3200 2.3651 47391
    15:39:50 2.3523 2.3800 2.3000 2.3100 53330
    15:40:00 2.3200 2.3500 2.2900 2.3400 46710

### (ii) FIRST-PULLBACK: NPT 2026-06-08 entry bar 15:44:20 sig 3.3800 (fill 3.4138) stop 3.2900 -> $-20.54 [stop@15:46:10]
  15:46:10 STOP 3.2900 fill 3.2736 (low 3.2700)

### (i) ANTICIPATE: NPT 2026-06-08 entry bar 14:31:50 sig 1.6000 (fill 1.6160) stop 1.3600 -> $-81.31 [stop@14:34:40]
  14:34:40 STOP 1.3600 fill 1.3532 (low 1.3100)

### (iii) DAY-2 RELOAD: RUBI 2026-06-12 entry bar 13:53:10 sig 0.7300 (fill 0.7373) stop 0.7212 -> $+87.11 [trail@14:15:20]
  14:05:50 BANK 0.50 at +10% (0.8110)
  14:15:20 TRAIL[off10] close 0.9251 fill 0.9205

## VERDICT
**No philosophy is a rocket lane.** Rockets in this cache are 78% precursor-less at 10s resolution; the "60 seconds before" is not readable with these five tests. What can be done "besides wait": nothing that ANTICIPATES the leg itself.

- **(ii) FIRST-PULLBACK: REFUTED** (22% win, -$85/date, both halves red). Do not build as specified. Only slice green = pullbacks on legs that then halted UP; that is a bet on continuation-into-halt, i.e. the arm-only halt lane already settled 8/8, not a new lane.
- **(iii) DAY-2 RELOAD: UNDER-POWERED** (N=24, +$1.71/date; control +$8/date). Needs day-2 bars for all 288 rocket names (Quartermaster: ferry D+1 for every leg name — most day-2s are NOT runner-days and so are absent). Registered hypothesis for the Seam Scientist, not a shadow candidate yet.
- **(i) ANTICIPATE on `f_at_new_high` = SHADOW-CANDIDATE (observe-only), NOT a ship.** It is really a "buy the fresh session-high break with a 6-bar-low stop" momentum lane; 2-slot +$128/date, 37/62 green, but OOS decays 4x ($206 -> $49), worst date -$705, and it lives on the runner-universe tailwind. Fails the 5/5 bar on worst-day (> -$300) and second-half strength; passes mean/median/green. Strength Ombudsman note: this is the strength-buying entry the bias ledger keeps saying we refuse — its P&L is real in-sample; its risk is the tail.

**Shadow spec (data-only rows, no orders):**
- trigger: last 6 RTH 10s bars span <=180s, no >60s gap before the current bar; 6-bar high > session high set BEFORE the window; last close >= 0.98 x 6-bar high; prior-20-min avg slot volume available (>=6 bars).
- entry stamp: current bar close (+1% slip in grading); stop = 6-bar low (2% floor if degenerate); dedup same name 5 min; no entries >= 15:30 ET; E3 exits.
- rows: `anticipate_shadow` with sym, t, entry, stop, session_hi, 6-bar range, vol multiple, halted-within-10min flag; nightly grade vs this study's population numbers (+$8.41/trade, 42% win) as the reference; kill if 10-day shadow mean < $0/trade or worst-day < -$300.
- promotion needs: >=10 forward days, positive both halves, worst day > -$300, plus a non-runner-universe re-grade (Quartermaster: ferry 10s bars for the whole scanner board, not just finishers) to remove the survivorship tailwind before any real-money proposal to Marcos.

**Officers touched:** Rocket Rider, Hidden Entry Architect, Wind Tunnel (clean: chain unchanged), Statistician (rows ledgered), Convexity Trader (tail flagged), Strength Ombudsman (strength entry logged), Quartermaster (day-2 + non-runner ferry asks), Seam Scientist (day-2 hypothesis), Historian (SCKT 8/10 in cache shows 0 RTH legs — its +230% squeeze is not in RTH bars; XHD not in cache), Halt lane (Part 4 note), Blast Radius Auditor (nothing shipped).
