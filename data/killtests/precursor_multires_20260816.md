# MULTI-RESOLUTION ROCKET PRECURSOR HUNT — 2026-08-16 (raw SIP ticks + NBBO)
**Officers:** Rocket Rider + Hidden Entry Architect (lead), Seam Scientist (registry), Statistician (rows), Wind Tunnel (contrast design), Kev Librarian (his picks = the cohort), Feed Engineer (SIP data), Strength Ombudsman (see "flush" caveat), Historian (Kev hit-rate stamp). Analysis only, no bot edits.
**Scripts:** `data/killtests/precursor_multires_pull_20260816.py` (STEP 1 cache) -> `precursor_multires_20260816.py` (features/rank/OOS; `d` arg = activity-matched contrast + hand-traces) -> `precursor_multires_20260816_RESULTS.txt` (verbatim) + `_rows.json` (every window, every feature). Cache: `data/universe/ticks_precursor/` — **257 MB, gitignored** (raw trades: 100 leg windows + 100 random + 188 matched universe windows; 95 Kev FULL-DAY 07:00-16:00 ET tick files; NBBO quotes for every window).
**Challenge target:** `rocket_anatomy_20260816.md` said liftoff is unreadable 60s ahead at 10s bars with 5 hand-picked precursors. This re-asks the question at 1s/tick with ~60 hypothesis-free features and NBBO, and with Kev's own picks as the primary cohort.

## VERDICT (plain words)
1. **KEV COHORT (primary): his names' liftoffs carry NO readable tape-flow pre-signal either.** Against activity-matched windows on his own names, every flow/NBBO feature Marcos would expect a human to "see" sits at coin-flip: aggressor imbalance AUC 0.57/0.45 (30s/10s), NBBO size imbalance 0.39-0.47, spread trend 0.47, bid stacking 0.54, ask thinning 0.59, consecutive upticks 0.50, micro higher-low 0.53, tick acceleration 0.50-0.56, distance to LULD 0.47. Combined score legs-vs-matched OOS AUC 0.72 (18 test events, weights = quote-rate/large-print COUNTS, i.e. "busy"); legs+pushes OOS 0.55; flow-only (no range/price) OOS **0.44-0.65 = null**.
2. **What his selection DOES change is the character of the tape, not a signal in it:** Kev's legs vs universe legs — spread 62 vs 148 bps (AUC 0.82-0.84 tighter), 30s range 271 vs 932 bps, closer to session high. His names are more liquid, more orderly, and (see 4) they lift off almost exclusively 07:00-10:00 ET. That is name-selection + regime + time-of-day, not a T&S/L2 tell in the last 60s.
3. **UNIVERSE (100 largest legs):** vs random windows the separation looks huge (OOS AUC 0.93-0.95) but it is "busy + volatile" — vs ACTIVITY-MATCHED windows it collapses to what remains: **wider range (0.73), a -2% flush in the last 30s (ret_30 0.69), WIDER spread (0.70, the opposite of Kev's tightening cue), tick accel 0.65**; flow/NBBO imbalance 0.49-0.51. Combined OOS 0.85 with range/price feats, 0.81 flow-only (that 0.81 is spread_60 = volatility). The flush is partly definitional (liftoff bar = the low by construction) and is NOT tradeable ahead: matched windows showing the same "flush + accel" (n=22) go max +242 bps / last -27 bps in the next 60s, 36% reach +3%; on Kev's names the same template (n=33) does +95 / -29 bps, 15% reach +3%.
4. **Kev's picks, stamped:** 95 name-days (32 dates 6/29-8/14), tape present 95/95. **19/95 (20%) produced a >=25%/<=5-min vertical leg** that day; 74/95 produced at least a +10% push. 28 legs total: time-of-day ET 07h:4, 08h:8, 09h:14, 13h:1, 14h:1 — **26 of 28 before 10:00 ET, 15 of 28 premarket**, 12 of 19 leg-days had their FIRST leg premarket. His premarket-pivot claim is supported by his own tape: the vertical moves in his names are a 07:00-10:00 phenomenon.
5. **Halt-resumption contamination in the anatomy top-100:** with silence measured correctly (leading gap included), **20 of 80 usable top-100 universe legs have >=20s of zero prints in the last 60s = LULD resumption**, 32/80 have >=5s. Those "liftoffs" have no pre-tape to read (PAVS 6/9 10:47, ZYBT 8/5 11:34 traces below). Kev legs: 5/28.
6. **So Kev's edge, on this evidence, is (a) which names, (b) when in the day, (c) regime (front-side/near highs) — not a last-60s microstructure read.** The next resolution that could still hide it is full L2 depth (bid stacking beyond NBBO top-of-book, iceberg/refresh behaviour) — which we do not capture; that is a data-plan question for Marcos (Alpaca has no L2; TotalView was declined at $135/mo).

## FEATURE TABLE — top-10 by |AUC|, honest contrast (activity-matched)
Enrichment = event fire-rate / contrast fire-rate at the contrast p90 (or p10) threshold; precision assumes 1:1 priors (real priors are ~1:100+ per 4-min window, so multiply accordingly).

### Kev legs (n=28) vs Kev activity-matched windows (n=376)
| feature | AUC | dir | med event | med contrast | enrich | prec(1:1) |
|---|---|---|---|---|---|---|
| quote_rate_60 | 0.773 | high | 8.18/s | 1.32/s | 4.7x | 83% |
| quote_rate_30 | 0.755 | high | 12.2 | 1.3 | 5.1x | 84% |
| quote_rate_10 | 0.752 | high | 10.1 | 1.3 | 4.4x | 81% |
| gap_max_60 (silence) | 0.743 | low | 1.0s | 4.7s | 4.6x | 82% |
| tick_rate_60 | 0.731 | high | 17.4/s | 2.4/s | 4.6x | 82% |
| tick_rate_30 | 0.722 | high | 23.1 | 2.6 | 4.2x | 81% |
| n_large_60 (>=5x med size) | 0.722 | high | 184 | 23 | 4.6x | 82% |
| tick_rate_10 | 0.720 | high | 23.3 | 2.5 | 5.1x | 84% |
| n_large_10 | 0.720 | high | 40 | 4 | 4.2x | 81% |
| vol_60 | 0.712 | high | 160k | 25k | 4.6x | 82% |
Every one of these is "the tape is busy" (matching by trade-flow sampling was imperfect: legs median 1900 pre-prints vs matched 409). Nothing directional. Kev legs+pushes (n=208) vs matched: best AUC 0.67 (range_60), flow features 0.45-0.57.

### Universe top-100 legs (n=80) vs universe activity-matched (n=188, median pre-prints 2636 vs 2570 = well matched)
| feature | AUC | dir | med event | med contrast | enrich | prec(1:1) |
|---|---|---|---|---|---|---|
| range_30 | 0.735 | high | 932 bps | 417 | 4.7x | 82% |
| range_60 | 0.729 | high | 1230 | 612 | 3.8x | 79% |
| range_10 | 0.723 | high | 602 | 223 | 4.8x | 83% |
| ret_10 | 0.711 | low (flush) | -186 | 0 | 4.2x | 81% |
| dist_sess_hi | 0.702 | low (near high) | 2020 | 6040 | 2.8x | 74% |
| spread_60 | 0.701 | high (WIDER) | 148 | 91 | 3.5x | 78% |
| spread_30 | 0.692 | high | 149 | 90 | 3.1x | 75% |
| ret_30 | 0.690 | low (flush) | -242 | 0 | 3.5x | 78% |
| spread_10 | 0.666 | high | 143 | 90 | 2.7x | 73% |
| px_vs_vwap180 | 0.655 | low | -314 | -21 | 3.3x | 77% |
Flow/NBBO features vs matched: imb_30 0.51, imb_10 0.50, nbbo_imb_30 0.49, nbbo_imb_trend 0.49, spread_trend_30 0.52, bid_stack 0.52, ask_thin 0.48, consec_upticks 0.48, higher_low_30 0.44, t_since_last_print 0.43, quote_accel_30 0.63, tick_accel_30 0.65, dist_luld_up 0.62.

### Universe legs vs RANDOM windows (the naive comparison — reported for completeness, not the verdict)
range_30 0.86, range_60 0.84, range_10 0.83, vol_10 0.78, vol_30 0.77, tick_accel_30 0.75, quote_rate_30 0.75, n_large_10 0.75, tick_rate_10 0.75, quote_rate_10 0.75. Combined OOS 0.94. This is what a study without an activity-matched control would have called "a signal".

## OOS COMBINED SCORES (fit first half of dates, tested on second half)
| cohort / contrast | feats | train ev / test ev | logistic OOS AUC | additive-z OOS AUC | OOS enrich @ contrast-p90 |
|---|---|---|---|---|---|
| Kev legs vs matched | top-12 | 10 / 18 | 0.724 | 0.783 | 3.3x |
| Kev legs+pushes vs matched | top-12 | 89 / 119 | 0.548 | 0.651 | 2.0x |
| Kev legs+pushes vs matched, flow-only | 11 | 89 / 119 | **0.443** | 0.647 | 1.3x |
| Kev legs vs random quiet | top-12 | 10 / 18 | 0.873 | 0.880 | 6.7x |
| Universe vs matched | top-12 | 48 / 32 | 0.854 | 0.884 | 6.6x |
| Universe vs matched, flow+NBBO only (5 feats: spread_60/30/10, tick_accel_60/30) | 5 | 48 / 32 | 0.808 | 0.811 | 5.0x |
| Universe vs matched, ALL 60 feats | 60 | 48 / 32 | 0.839 | 0.785 | 6.6x |
| Universe vs random | top-12 | 48 / 32 | 0.940 | 0.913 | 8.8x |
| Universe-fit score applied to Kev legs vs Kev quiet | 60 | - | 0.750 | - | - |
Reading: the only robust OOS separators are range/volatility, the flush, and (universe) wider spread. Nothing in the order-flow direction survives matching.

## STEP 4 — ECONOMICS (why even the "signal" is not tradeable)
- Field: ~20 names x 97 four-minute slices = ~1,940 windows/day. A template with 10% contrast fire-rate = ~194 false fires/day; the best flow-only universe template at 5x enrichment still fires on 10% of busy windows.
- Universe legs at T: +1% chase, 60s-later mark median +407 bps (max +1012); matched windows median 0 / mean -24. The "flush+accel" template on matched windows (the closest look-alike): n=22, 60s max +242 bps median, 60s last -27 bps, 36% touch +3%. On Kev names: n=33, +95 / -29 bps, 15% touch +3%. With ~1:50-1:100 event:window priors the false-positive cohort dominates; a +1% chase on the template is a bleed, consistent with anatomy's ANTICIPATE (+$8/trade only because it caught bigger structure, 40 real liftoffs in 3539 fires).
- E4-exit dollar sim NOT run because no template cleared the precondition (a directional pre-signal). Registered as a Seam Scientist hypothesis, not a lane.

## HAND-TRACES at tick level (5s buckets, last 60s -> +30s; full tables in RESULTS.txt)
- **INHD 6/8 09:53:00 ET, +46%.** 52 ticks/s the whole minute; last 30s: price 1.90 -> 1.80 (-4.6% flush), spread flat 53-55 bps, bid/ask sizes swing 200-20,400 with no stacking pattern (ask 17,700 at -60s, 400 at -10s, 200 at -5s; bid 1,300 -> 5,600 at -5s), aggressor imb +0.11. T bar: 887 prints/5s, low 1.715, then 1.79/1.84/1.85 within 15s. Read: a violent flush into a bid; nothing in the prior 60s that says "next".
- **PAVS 6/9 10:47:20 ET, +55%.** ZERO prints -60..-45s (LULD resumption at -40s), then 500-1000 prints/5s, price 5.24 -> 4.87 -> 5.16 -> 5.03 -> 5.14, spread 60-170 bps, ask size 100-600 vs bid up to 5,800 at -10s (thin ask, real) — but the same thin-ask reads appear all over the matched set (ask_thin AUC 0.48). Read: halt-resumption chaos; the pre-window IS the halt.
- **ZYBT 8/5 11:34:00 ET, +52%.** ZERO prints -60..-10s (resumption at -10s): 1021 prints/5s at 3.63, then 3.45, T bar low 2.82 (-22% in 5s) then 3.08 -> 3.28. Read: a resumption flush; unreadable ahead by definition.
- **UPC 6/29 08:49:40 ET (Kev pick, premarket), +89%.** 34 ticks/s, spread 24-72 bps (tight, Kev-class), price grinds 8.57 -> 8.24 over 55s (-2%), aggressor imb -0.34 (SELL-dominated into liftoff), bid 100-700 / ask 100-600 no stacking, NBBO imb -0.08. Then 8.35/8.49/8.54/8.61/8.67. Read: the last minute before Kev's biggest premarket rocket was net SELLING on a tight, orderly tape.

## CAVEATS (honest)
- Sample: 80 usable universe legs (20 of them halt resumptions), 28 Kev legs (10 train / 18 test), 180 Kev pushes. Kev per-day hit-rate uses the anatomy leg definition rebuilt from ticks at 10s (>=25% low->high in <=300s on >=3x prior-20-min per-slot volume); premarket included (07:00 ET+), so pre-legs on thin tape can be spread-artifacts.
- SIP timestamps are participant timestamps; NBBO is top-of-book only (no depth, no venue book, no order-add/cancel stream) — the L2 "stacking" Kev describes is literally outside this data.
- Aggressor side = quote-rule (at/above ask = buy, at/below bid = sell) with tick-rule fallback; premarket quotes are sparse.
- LULD distance uses a 3-min mean as reference (rule is 5-min) and tier-2 bands; approximate.
- Activity matching: universe well matched (2636 vs 2570 pre-prints); Kev matching under-shot (409 vs 1900) because contrast T was sampled from a subsampled trade list — Kev "busy" AUCs (0.72-0.77) are therefore UPPER bounds on any tape signal, and they are still just activity.
- Universe = runner-days (survivorship); Kev = his picks (selection). Both cohorts are conditioned on the day having been special.
- The flush feature (ret_10/30 negative) is partly built into the leg definition (liftoff bar = base low); treat as descriptive, not predictive.

## NEXT DATA THAT COULD CHANGE THIS
Full L2 depth (order-book snapshots or add/cancel stream) on the crowned/Kev names during 07:00-10:00 ET, plus a fresh 8/17-8/21 forward capture with events stamped live (Seam Scientist OOS wall). Without depth, further tape resolution is exhausted here: 1s, tick, and NBBO all say the same thing.
