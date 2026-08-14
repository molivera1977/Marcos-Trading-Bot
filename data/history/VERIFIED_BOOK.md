# THE VERIFIED BOOK — era 2026-07-13 onward (built 2026-08-13)

**Headline uses CHARITABLE (fiction fills re-booked at best provable price); STRICT (fiction fills exit at recorded exit) is the floor.**

## Assumptions
See header of `data/killtests/verified_book_20260813.py` — trade pnl as rendered (correction applied) = raw; union of 10S+ALP10S tape; entry ±3min/0.5%; fill touch = bar high >= px*0.999; exit ±1%; NO smoothing or interpolation; no-bars trades excluded from verified totals and listed below; 162 trades lack entry_ts_utc (whole-day window, flagged).

## RTH era book
- trades verified: 307  |  no-bars (excluded): 65 (raw $+281.92)
- RAW: $+497.10   CHARITABLE: $+191.71   STRICT: $-189.68

## PRE era book
- trades verified: 40  |  no-bars (excluded): 0 (raw $+0.00)
- RAW: $-683.24   CHARITABLE: $-683.24   STRICT: $-683.24

## Per-day (verified trades only; no-bars raw $ shown separately)
| date | sess | n | raw | charitable | strict | delta(char-raw) | no-bars n | no-bars raw$ |
|---|---|---|---|---|---|---|---|---|
| 2026-07-13 | RTH | 0 | +0.00 | +0.00 | +0.00 | +0.00 | 26 | +234.15 |
| 2026-07-14 | RTH | 0 | +0.00 | +0.00 | +0.00 | +0.00 | 23 | -1.12 |
| 2026-07-15 | RTH | 23 | -112.46 | -112.46 | -112.46 | +0.00 | 7 | +20.08 |
| 2026-07-16 | RTH | 17 | -10.06 | -34.81 | -18.59 | -24.75 | 3 | +37.28 |
| 2026-07-17 | RTH | 16 | -196.41 | -242.73 | -238.55 | -46.32 | 5 | -4.21 |
| 2026-07-20 | RTH | 4 | +123.91 | +123.91 | +123.91 | +0.00 | 0 | +0.00 |
| 2026-07-21 | RTH | 3 | -36.19 | -36.19 | -36.19 | +0.00 | 1 | -4.26 |
| 2026-07-22 | RTH | 6 | -7.68 | -7.68 | -7.68 | +0.00 | 0 | +0.00 |
| 2026-07-23 | RTH | 3 | -55.78 | -55.78 | -55.78 | +0.00 | 0 | +0.00 |
| 2026-07-24 | RTH | 2 | -26.64 | -26.64 | -26.64 | +0.00 | 0 | +0.00 |
| 2026-07-27 | RTH | 17 | -153.72 | -153.72 | -153.72 | +0.00 | 0 | +0.00 |
| 2026-07-27 | PRE | 5 | -624.50 | -624.50 | -624.50 | +0.00 | 0 | +0.00 |
| 2026-07-28 | RTH | 13 | -63.54 | -63.54 | -63.54 | +0.00 | 0 | +0.00 |
| 2026-07-29 | RTH | 18 | -214.49 | -214.49 | -214.49 | +0.00 | 0 | +0.00 |
| 2026-07-29 | PRE | 3 | -104.45 | -104.45 | -104.45 | +0.00 | 0 | +0.00 |
| 2026-07-30 | RTH | 22 | -114.93 | -114.93 | -114.93 | +0.00 | 0 | +0.00 |
| 2026-07-30 | PRE | 5 | +0.93 | +0.93 | +0.93 | +0.00 | 0 | +0.00 |
| 2026-07-31 | RTH | 20 | +18.08 | +2.95 | -24.27 | -15.13 | 0 | +0.00 |
| 2026-07-31 | PRE | 4 | -5.88 | -5.88 | -5.88 | +0.00 | 0 | +0.00 |
| 2026-08-03 | RTH | 11 | -40.32 | -54.59 | -78.28 | -14.27 | 0 | +0.00 |
| 2026-08-03 | PRE | 3 | +9.49 | +9.49 | +9.49 | +0.00 | 0 | +0.00 |
| 2026-08-04 | RTH | 6 | +385.78 | +385.78 | +385.78 | +0.00 | 0 | +0.00 |
| 2026-08-04 | PRE | 5 | -45.73 | -45.73 | -45.73 | +0.00 | 0 | +0.00 |
| 2026-08-05 | RTH | 13 | -133.10 | -133.10 | -133.10 | +0.00 | 0 | +0.00 |
| 2026-08-06 | RTH | 19 | +24.84 | +0.01 | -44.38 | -24.83 | 0 | +0.00 |
| 2026-08-06 | PRE | 1 | +22.39 | +22.39 | +22.39 | +0.00 | 0 | +0.00 |
| 2026-08-07 | RTH | 24 | +530.65 | +412.62 | +175.84 | -118.03 | 0 | +0.00 |
| 2026-08-10 | RTH | 13 | +57.28 | +43.89 | +29.09 | -13.39 | 0 | +0.00 |
| 2026-08-10 | PRE | 1 | -0.35 | -0.35 | -0.35 | +0.00 | 0 | +0.00 |
| 2026-08-11 | RTH | 24 | +58.36 | +49.35 | +38.96 | -9.01 | 0 | +0.00 |
| 2026-08-11 | PRE | 5 | +46.26 | +46.26 | +46.26 | +0.00 | 0 | +0.00 |
| 2026-08-12 | RTH | 15 | +254.99 | +216.15 | +178.09 | -38.84 | 0 | +0.00 |
| 2026-08-12 | PRE | 6 | +29.18 | +29.18 | +29.18 | +0.00 | 0 | +0.00 |
| 2026-08-13 | RTH | 18 | +208.53 | +207.71 | +201.25 | -0.82 | 0 | +0.00 |
| 2026-08-13 | PRE | 2 | -10.58 | -10.58 | -10.58 | +0.00 | 0 | +0.00 |

## Per-lane
| lane | n | raw | charitable | strict | fiction $ (char delta) |
|---|---|---|---|---|---|
| dip_rip | 1 | +16.49 | +16.49 | +16.49 | +0.00 |
| flat_top | 36 | -311.15 | -357.47 | -353.29 | -46.32 |
| halt_ladder | 1 | +34.34 | +34.34 | +34.34 | +0.00 |
| hidden_entry | 131 | +880.99 | +686.96 | +347.65 | -194.03 |
| ignition | 97 | +19.90 | -36.64 | -61.48 | -56.54 |
| ma_pullback | 22 | +443.26 | +443.26 | +443.26 | +0.00 |
| orb | 5 | -54.15 | -62.65 | -84.07 | -8.50 |
| vwap_reclaim | 48 | -992.34 | -992.34 | -992.34 | +0.00 |
| zone_flip | 6 | -223.48 | -223.48 | -223.48 | +0.00 |

## Best days re-ranked (RTH, CHARITABLE)
- 2026-08-07: charitable $+412.62 (raw $+530.65)
- 2026-08-04: charitable $+385.78 (raw $+385.78)
- 2026-08-12: charitable $+216.15 (raw $+254.99)
- 2026-08-13: charitable $+207.71 (raw $+208.53)
- 2026-07-20: charitable $+123.91 (raw $+123.91)
- 2026-08-11: charitable $+49.35 (raw $+58.36)
- 2026-08-10: charitable $+43.89 (raw $+57.28)
- 2026-07-31: charitable $+2.95 (raw $+18.08)

## Component stats (verified-cohort)
- entries verified: 333/347 (96.0%)  [99 lacked entry_ts_utc — whole-day window]
- fills verified_strict: 182/292 (62.3%)
- fills verified_generous_only: 72/292 (24.7%)
- fills FICTION: 38/292 (13.0%)
- exits verified: 335/347 (96.5%)

## Unverifiable (no bars on either feed)
Total: 65 trades, raw $+281.92 — NOT in verified totals.
- 2026-07-13 GMM RTH unknown raw $+14.90 (3623b9a6)
- 2026-07-13 SKYQ RTH unknown raw $+15.55 (15afb86a)
- 2026-07-13 TDTH RTH unknown raw $-5.31 (630a4519)
- 2026-07-13 INBS RTH unknown raw $-12.17 (79ae517e)
- 2026-07-13 EHGO RTH unknown raw $+16.12 (2e0c9497)
- 2026-07-13 SOBR RTH unknown raw $+93.56 (9ddedc25)
- 2026-07-13 EHGO RTH unknown raw $+15.75 (74f96bec)
- 2026-07-13 EHGO RTH unknown raw $+15.15 (6c13ffad)
- 2026-07-13 CRMT RTH unknown raw $-8.17 (d59d5ece)
- 2026-07-13 INUV RTH unknown raw $+0.46 (d3f55847)
- 2026-07-13 FTRK RTH unknown raw $+18.96 (df20bee5)
- 2026-07-13 MIMI RTH unknown raw $+14.49 (c000f1bd)
- 2026-07-13 CPHI RTH unknown raw $+4.26 (21cdf652)
- 2026-07-13 TRNR RTH unknown raw $+4.32 (cfb985f4)
- 2026-07-13 FTRK RTH unknown raw $-32.41 (f95b4b61)
- 2026-07-13 MTVA RTH unknown raw $+30.56 (7be610d0)
- 2026-07-13 MIMI RTH unknown raw $-45.70 (873e714f)
- 2026-07-13 CPHI RTH unknown raw $-5.39 (96eefaa3)
- 2026-07-13 FTRK RTH unknown raw $+46.20 (0fff0c17)
- 2026-07-13 TRNR RTH unknown raw $+16.22 (45e3c2fd)
- 2026-07-13 VMAR RTH unknown raw $+15.58 (9f66c046)
- 2026-07-13 NVVE RTH unknown raw $+31.25 (c1de9a8c)
- 2026-07-13 QTTB RTH unknown raw $+7.92 (cd9242a7)
- 2026-07-13 CPHI RTH unknown raw $-28.39 (6d8acc8f)
- 2026-07-13 UCAR RTH unknown raw $+6.16 (93ec5294)
- 2026-07-13 PED RTH unknown raw $+4.28 (f0b86eda)
- 2026-07-14 SUNE RTH vwap_reclaim raw $-38.85 (82386fcd)
- 2026-07-14 NVVE RTH vwap_reclaim raw $-33.47 (aeaae774)
- 2026-07-14 TRNR RTH vwap_reclaim raw $+26.07 (6722375c)
- 2026-07-14 MIMI RTH ignition raw $-2.46 (4d8caa77)
- 2026-07-14 LEDS RTH ignition raw $+21.85 (2a9d67f4)
- 2026-07-14 BJDX RTH vwap_reclaim raw $-36.54 (d01274d8)
- 2026-07-14 SOBR RTH ignition raw $+30.24 (e100e965)
- 2026-07-14 SDOT RTH vwap_reclaim raw $+12.81 (e7b41a6c)
- 2026-07-14 SOBR RTH ignition raw $-41.11 (9890527a)
- 2026-07-14 RDGT RTH ignition raw $+2.37 (ca32abdd)
- 2026-07-14 YYGH RTH ignition raw $+39.12 (62765eaa)
- 2026-07-14 MGIH RTH ignition raw $-39.01 (04486544)
- 2026-07-14 IVF RTH ignition raw $+2.96 (0df035dd)
- 2026-07-14 HODO RTH vwap_reclaim raw $+21.72 (f5208588)
- 2026-07-14 CNEY RTH ma_pullback raw $+27.02 (4a33f360)
- 2026-07-14 UONEK RTH ignition raw $+14.12 (82783bd0)
- 2026-07-14 ELWT RTH ignition raw $+6.56 (ac118020)
- 2026-07-14 PDC RTH vwap_reclaim raw $+11.76 (696feeba)
- 2026-07-14 PCSC RTH ignition raw $-21.95 (c757f6d3)
- 2026-07-14 ERNA RTH vwap_reclaim raw $-6.65 (dc05861b)
- 2026-07-14 VS RTH flat_top raw $+7.01 (a60175be)
- 2026-07-14 BNZI RTH ma_pullback raw $+0.62 (8712640f)
- 2026-07-14 LEDS RTH vwap_reclaim raw $-5.31 (a16d46f1)
- 2026-07-15 ACXP RTH ignition raw $-22.68 (ee4c4e08)
- 2026-07-15 ZSTK RTH ignition raw $+2.08 (573bb206)
- 2026-07-15 INDP RTH vwap_reclaim raw $+4.74 (b171f7b9)
- 2026-07-15 BIVI RTH vwap_reclaim raw $+7.68 (de70e4db)
- 2026-07-15 TJGC RTH vwap_reclaim raw $+4.92 (e1e5e646)
- 2026-07-15 OPAD RTH vwap_reclaim raw $+16.66 (a18e456e)
- 2026-07-15 YYAI RTH vwap_reclaim raw $+6.68 (8f49c522)
- 2026-07-16 TVRD RTH flat_top raw $+31.36 (41cc5af4)
- 2026-07-16 QNCX RTH vwap_reclaim raw $-15.07 (e4acef0d)
- 2026-07-16 NYC RTH vwap_reclaim raw $+20.99 (731cb7c3)
- 2026-07-17 TRUG RTH ignition raw $+11.68 (70ecd4a4)
- 2026-07-17 AMST RTH ignition raw $+5.00 (c1912c95)
- 2026-07-17 HUBC RTH ignition raw $+0.81 (1dec584d)
- 2026-07-17 TVRD RTH ignition raw $-22.08 (b6bebbce)
- 2026-07-17 NTRP RTH vwap_reclaim raw $+0.38 (e8f05ec4)
- 2026-07-21 NCRA RTH ignition raw $-4.26 (93d514a4)

## ROOM CORRECTIONS (full-room verification panel, 8/13 ~23:00 — applied as annotations; nightly job recomputes)
1. LEDS 7/17 RECLASSIFIED fiction -> unverifiable (28-bar disjoint tape fragment, no overlap with
   the trade's price range — "no usable tape" is not "proven fiction"). Effect: flat_top fiction
   -> $0.00; RTH CHARITABLE +$191.71 -> ~+$238; 66 unverifiable.
2. MD count fix: 164 trades lack entry_ts_utc store-wide (99 in the verified cohort — that figure
   was correct). 3. Footnote: 4 trades show strict>charitable (~+$9 net; exit price itself
   unprinted) — aggregate ordering intact, per-trade floor caveat noted.
VERIFIED-TO-THE-CENT: every headline reproduces from VERIFIED_BOOK.json; store cross-foots at
era-total $95.78 exactly; 5/5 tape spot-checks hold; 7/13-7/14 tape genuinely absent (pre-capture).
HEADLINE OF RECORD (Historian): CHARITABLE, RTH and PRE separate; strict beside it as floor.
