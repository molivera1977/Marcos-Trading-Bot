# KEV ROSETTA STUDY — his named fills at tick level vs the look-alikes he did NOT take (8/16/26)

Analysis only. Nothing ships. Script: `data/killtests/kev_rosetta_20260816.py` (pull / recon / gen); fills: `kev_rosetta_20260816_fills.json`; per-fill rows incl. every look-alike bar: `kev_rosetta_20260816_rows.json`; ticks (SIP trades+NBBO, 211 MB) under `data/universe/ticks_kev_fills/` (gitignored). Harvest run 21:39–23:xx ET 8/16 (`date` cited in transcript).

## TL;DR (plain words)
- 34 named fills harvested (ticker + entry price; 24 with a defensible date), **23 reconstructed** on SIP 10s bars, 15 of them "credible" (day-gain >=20%, fill within 15% of session high — the rest are probably mis-dated: NAMI/XHLD/ILLR/VRAX/CCHH/JEM/GOVX/QUCY land on a wrong-looking day).
- **The honest headline: after a random-price CONTROL, almost every "his bar is at an extreme" feature is an artifact of HOW the fill bar is located** (a bar that contains a given price is a big bar). What survives the control:
  1. **The SEQUENCE: break of the session high, THEN a hold/wick (B->H or B->W on the 10s) — 60% of credible fills (9/15) vs 8% of same-day look-alikes vs 20% of the random-price control.** In words: he does not buy the pullback in the middle of a leg; he buys the FIRST hold/wick right after the tape has just printed a new session high (the pullback that comes right after the breakout, not the second or third pullback inside the range).
  2. **Burst volume on the fill bar** (vol/median-of-30 at 82nd pct vs 72nd control; 78% of fills >=75th pct vs 55% control) — his bar is the bar where the volume arrives, i.e. he punches AS the buyer shows up, not on the quiet retest.
  3. **Fresh level**: first or second touch of the low he risks (touches<=1 in 8/15 credible; 7/15 also within 1 min of the session high; look-alikes 5% both) — but the control shows the locate method produces the same "freshness", so treat this as CONFIRMED-CONSISTENT-WITH, not DISCRIMINATING.
- Front side 15/15 credible fills (look-alikes ~70% front side) — necessary, not sufficient.
- **His outcomes from his own fills** (KEV-native exit, $500 clip): 23 fills +$321 (11 wins), E3 +$338, 2R-before-stop 14/23 (12/15 credible); look-alikes on the same name-days: KEV mean −$1.92/trade, 2R rate 30%. His bars are better than the look-alikes (mean +$13.96 vs −$1.92) — the reconstruction found real bars, but the difference is small in $ at our sizing.
- **Generalization (Kev-A/B/C fast-chart detectors, 198 SIP name-days, 10s):** BEFORE N=399 KEV −$581 / E3 −$847 / F −$3,889. Sequence clause (last two structural events = B->H or B->W) alone: N=79 KEV **+$447** / E3 −$31 / E4W +$356 / F −$2,927 (all of it in detector B: N=59 KEV +$576, E3 +$340, E4W +$877, 37% win). Top-2 features (vol_ratio>=2.2 & bar_rng>=3.7%): N=73 KEV +$474 / E3 +$268. "Fresh" (touches<=1 & <=0.3 min since session high — his p75s): N=113 KEV **+$1,323** / E3 +$1,162 / E4W +$997 / F −$2,807. Top2+SEQ: N=19 KEV +$588. Top2+fresh: N=26 KEV +$805. All clauses turn the refuted detector from red to green **at N=19–113 fires over ~60 trading days**, thresholds taken from his fills (light in-sample), F-control still negative (so the edge is the exit/selection, not the names). NOT shippable on this; it is a registered hypothesis for the seam/hidden-v2 owners.

## STEP 1 — the fills (harvest; source quotes in `scratchpad kev_fills.json` -> fills json `quote` field)
| # | Sym | Date used (resolution) | Sess | Entry | Stop | His stated result | Cue (his words, short) | Source | Conf |
|---|---|---|---|---|---|---|---|---|---|
| 1 | LGHL | 2026-07-14 (stated 2026-07-27 range 0.95-2.06 excludes 3.5; nearest in-range day 2) | PRE  | 3.5 | 3.3 | 2:1 hit to 3.90, then rode toward ~5 | 10s pullback to VWAP+90MA, wick low, buyer steps in, break b | k27fptelI8Y (short) + yMADpV8kOhQ (main) | high |
| 2 | ZYBT | 2026-07-20 (stated date, price in range) | RTH  | 3.1 | 3.0 | 3.10 to 3.50 | break of $3 level, pullback settles/hesitates at 3.10 on 10s | xZJaq78FcN4 (short) + VhH6-u9POsk (main) | high |
| 3 | LZMH | 2026-08-10 (stated date, price in range) | PRE 09:15 | 1.83 | — | 184 to about 212 | first 10s pullback to 9EMA+VWAP on the only mover | ulOfwyRAs1o | high |
| 4 | MASK | 2026-05-28 (stated date, price in range) | unknown  | 3.04 | 3.02 | 304 to 329 | 10s bottoming tails off 3.02, break higher | 0Kvr3TWLllo | high |
| 5 | MSPR | UNRESOLVED (no in-range day found) | RTH 09:35 | 0.66 | — | 66 to ~72 cents, first leg captured | break of premarket flat top, next pullback to VWAP+90MA conf | 9KRu7LcUGhA (main, line ~58408) | med |
| 6 | MSPR | UNRESOLVED (no in-range day found) | RTH  | 0.66 | 0.64 | 65.90 to about 72 | EMA pullback | rmtMgj9upos | med |
| 7 | SCKT | 2026-08-10 (stated date, PRE, price near range) | PRE 09:00 | 1.2 | — | squeezed 1.20 to 3.97 in seconds; he sold 1.20->2.50, filled 1.60 part | 1-min pullback to VWAP after 0.30->1.00 squeeze, break of HO | tiktok 7672476799023992077 + 76724649645 | high |
| 8 | MTEN | 2026-08-10 (stated date, price in range) | RTH  | 1.29 | 1.25 | 1.30 to 1.60 | double bottom off 1.25 after failed HOD punch (1.34->1.41);  | ulOfwyRAs1o + tiktok 7672469812320242957 | high |
| 9 | STKH | 2026-08-10 (stated date, price in range) | RTH 09:35 | 4.7 | — | 470 to about 545, sized down and stepped away | break of premarket trend + break of VWAP, punched into the h | ulOfwyRAs1o | high |
| 10 | VIVK | 2026-07-21 (stated date, price in range) | unknown  | 7.5 | 7.2 | 'Another nice win' | pullback under $8 to 20EMA, 90EMA beneath past high | 3COX2eVGGBY | med |
| 11 | WYHG | 2026-08-10 (stated 2026-08-06 range 7.7101-26.17 excludes 6.7; nearest in-range da) | unknown  | 6.7 | 6.45 | +0.30/share quickly, half off at $7 | 1-min candle breaks prior low, instantly bought back (wick), | AIKDZG5v-ns (all_transcripts ~11689) | med |
| 12 | SPRC | UNRESOLVED (no/unknown date; in-range days ['2026-05-05', '2026-05-06', '2026-05-0) | PRE  | 6.95 | 6.4 | ~15% win premarket; stop later adjusted to 6.30 | premarket, range to $8/$9, support at 6.30 | 3OKv2Hh_8m0 (all_transcripts ~92878) | med |
| 13 | NAMI | 2026-08-07 (stated date, price in range) | unknown  | 6.8 | 6.6 | small; missed the big move | breakout over VWAP | a0Enm3rRzxs | med |
| 14 | XHLD | 2026-08-07 (stated 2026-08-12 range 3.93-6.26 excludes 2.2; nearest in-range day 2) | unknown  | 2.2 | 1.8 | >100% move captured | flush from highs back to 90EMA+VWAP, double wick low | AWCqE5Lwkxs | med |
| 15 | HSCS | 2026-06-23 (stated date, price in range) | PRE  | 2.65 | 2.58 |  | premarket strength, VWAP as risk | 6cejulubGIk | med |
| 16 | ICCM | 2026-06-17 (stated date, price in range) | unknown  | 5.7 | 5.3 | base hits, halt up | pullback, break of $6 | z7pYYrqOPlg | med |
| 17 | CCHH | 2026-06-11 (stated date, price in range) | unknown  | 0.64 | 0.62 | quarter left into 0.675 | pullback, top-stock live | LDPqpQQeD0M | med |
| 18 | YAAS | UNRESOLVED (stated 2026-07-30 range 1.9-4.98 excludes 1.38; no in-range day +-14d) | unknown  | 1.38 | 1.32 |  | higher low confirmed off VWAP | wvnmd6Dkm28 | low |
| 19 | GOVX | 2026-05-18 (stated date, price in range) | unknown  | 3.5 | 3.3 | day back to new highs | pullback, half size | LgP55m3R6q8 | med |
| 20 | HCAI | 2026-05-18 (stated date, price in range) | unknown  | 13.0 | 12.2 |  | halt play, continuation over 13.40 high | zNTlZQ8pizU | med |
| 21 | ILLR | 2026-07-06 (stated 2026-06-25 range 2.54-5.3 excludes 2.03; nearest in-range day 2) | unknown  | 2.03 | — | quick 35c move; later to $4 | leading gapper on scanner, pullback | 0KQTNxhZW68 + jjB7KbS6_hM | med |
| 22 | ELAB | UNRESOLVED (stated 2026-07-10 range 1.03-1.56 excludes 1.6; no in-range day +-14d) | unknown  | 1.6 | 1.5 |  | confirming candle, risk bottom of candle | main 'Today was not the day' (per kev_fa | med |
| 23 | VRAX | 2026-07-10 (stated 2026-07-09 range 5.8632-13.19 excludes 4.4; nearest in-range da) | unknown  | 4.4 | 4.25 |  | 10s break of trend, retest VWAP+90MA, bought back up | zuLxsnc0UVo | high |
| 24 | QUCY | 2026-05-20 (stated date, price in range) | unknown  | 2.54 | — | 254 to 277 | 10s double bottom out of a 2.38 halt, curl | o3iUmTvPaL8 | med |
| 25 | LNAI | UNRESOLVED (no in-range day found) | unknown  | 1.24 | 1.17 | half sold 1.36 | short squeeze, half size | 1j6hf6ZqwVk | med |
| 26 | AZI | 2026-06-29 (no/unknown date; in-range days ['2026-06-09', '2026-06-10', '2026-06-2) | unknown  | 2.88 | — | multiple wins out of halt | dip out of a halt | dBNnFoEDhW4 | med |
| 27 | JEM | 2026-07-02 (no/unknown date; in-range days ['2026-06-30', '2026-07-01', '2026-07-0) | unknown  | 3.2 | — | quarter left 3.45 | 1.3M float squeezer, pullback | QtJqVWh5qf4 | low |
| 28 | PJDX | UNRESOLVED (no in-range day found) | unknown  | 1.69 | — | title: almost knifed, gave back | over 1.60, break of 1.75 | CYYprsXmrD0 | low |
| 29 | MGRX | 2026-07-31 (no/unknown date; in-range days ['2026-07-31']) | RTH  | 0.92 | 0.88 | ~0.92 to 1.20 | break over 0.95 supply, pullback retests prior highs, buyer  | sdB--7-WvcM | med |
| 30 | ZEC | UNRESOLVED (no in-range day found) | unknown  | 2.22 | 2.16 |  | range to prior highs, lower high | vEJx4W8io_A | low |
| 31 | HKD | UNRESOLVED (no in-range day found) | unknown  | 2.67 | 2.55 |  | liquidity grab under VWAP, nailed the entry | 2ifUl04zDtg | med |
| 32 | SPRC | UNRESOLVED (no/unknown date; in-range days ['2026-05-05', '2026-05-06', '2026-05-0) | unknown  | 6.8 | 6.6 | back to green on the morning | pullback, small size | VWWlIPzb3Pk | med |
| 33 | PAVS | 2026-06-09 (no/unknown date; in-range days ['2026-06-09']) | unknown  | 2.72 | 2.65 | 'Perfect play' | double bottom off VWAP | l4O39mFldaU | med |
| 34 | WLDS | 2026-07-23 (no/unknown date; in-range days ['2026-07-23']) | unknown  | 2.2 | 2.12 |  | pullback | liY-SyWB6Uk | med |


Excluded from reconstruction: MSPR x2 (no in-range day in SIP daily May–Aug), SPRC x2 (15+ in-range days, undatable), YAAS/ELAB (stated day's range excludes the price, no day within +-14d), LNAI/PJDX/ZEC/HKD (no date), 4 UNKNOWN-ticker fills. SCKT 8/10 $1.20 not locatable: SIP shows the 0.39->3.97 squeeze at 09:25–09:31 ET with NO 10s bar containing 1.20 within 1.2% (gapped through it) — his "1:20" is inside a vertical bar; not reconstructible at 10s.

## STEP 2 — tick reconstruction (10s bars from SIP trades, VWAP anchored 04:00, 9/20 EMA, 90 SMA; NBBO spread + aggressor split from SIP quotes)
Fill bar = first 10s bar in the stated session/time window that trades through his price with a pullback context (prior 3-min high > price+1%); "SESSION MISMATCH" = his stated session did not contain the price, whole day used. `class` = which surface pattern his bar satisfies (reclaim = wick/undercut bought back at VWAP/9EMA; level_hold = whole/half-dollar break held 3 bars; neither = pattern not machine-recognisable at 10s).

| Sym date | Fill bar (ET) | locate | class | min open | gain% | dist hi% | min since hi | pb depth% | bar rng% | vol x | touches@low | vwap% | spread bps | buy frac | halt min | struct seq (last 5) | KEV $ | E3 $ | E4W $ | F $ | 2R? | MFE15m% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LGHL 2026-07-14 | 09:53:40 | pb-through +SESSION MISMATCH | level_hold | 23.7 | 1413.4 | 1.09 | 0.0 | 8.8 | 8.17 | 14.32 | 1 | 13.37 | 54.5 | 0.64 | None | H T H B H | 27.35 | 89.85 | 135.38 | -37.32 | True | 65.42 |
| ZYBT 2026-07-20 | 13:44:10 | pb-through | reclaim | 254.2 | 366.9 | 3.41 | 51.5 | 8.31 | 7.67 | 2.57 | 9 | 69.14 | 92.7 | 0.56 | 0.2 | L P H P H | 29.6 | 23.75 | -26.57 | -37.32 | True | 12.9 |
| LZMH 2026-08-10 | 10:22:40 | pb-through +SESSION MISMATCH | neither | 52.7 | 54.1 | 5.96 | 0.2 | 9.65 | 9.33 | 34.34 | 0 | 6.55 | 54.2 | 0.57 | 18.7 | T H T B T | -2.66 | 23.75 | -14.05 | -37.32 | True | 18.03 |
| MASK 2026-05-28 | 10:40:00 | pb-through | neither | 70.0 | 121.7 | 8.82 | 2.5 | 3.93 | 3.92 | 0.97 | 1 | 19.32 | 32.6 | 0.52 | None | H B H B W | -5.77 | -5.77 | -5.77 | 164.42 | False | 59.87 |
| SCKT 2026-08-10 | NOT LOCATED (no touch anywhere) | | | | | | | | | | | | | | | | | | | | | |
| MTEN 2026-08-10 | 09:55:30 | pb-through | reclaim | 25.5 | 47.5 | 3.08 | 0.3 | 10.17 | 9.23 | 28.02 | 4 | 5.93 | 155.0 | 0.5 | None | T B T B W | 20.64 | 23.75 | -17.93 | -37.33 | True | 37.98 |
| STKH 2026-08-10 | 09:36:40 | pb-through | level_hold | 6.7 | 162.2 | 0.0 | 0.0 | 5.12 | 4.87 | 3.91 | 0 | 16.6 | 20.3 | 0.53 | None | H B H B H | 21.85 | -3.56 | -3.56 | -37.33 | True | 33.83 |
| VIVK 2026-07-21 | 09:51:30 | pb-through | neither | 21.5 | 341.6 | 4.45 | 3.8 | 3.48 | 3.4 | 2.27 | 3 | 16.17 | 39.3 | 0.63 | None | W H W H W | 50.57 | 30.35 | -22.4 | -37.32 | True | 28.4 |
| WYHG 2026-08-10 | 10:55:50 | pb-through | level_hold | 85.8 | 58.0 | 5.71 | 0.0 | 10.12 | 9.71 | 37.43 | 0 | 19.19 | 85.6 | 0.62 | 0.2 | L B H B H | 159.37 | 83.9 | 188.33 | -37.32 | True | 32.54 |
| NAMI 2026-08-07 | 09:52:30 | pb-through | neither | 22.5 | 140.9 | 35.09 | 20.3 | 14.2 | 13.41 | 12.55 | 0 | -14.27 | 99.6 | 0.22 | None | P H R P R | -17.13 | -17.13 | -17.13 | -37.33 | False | 4.26 |
| XHLD 2026-08-07 | 09:58:00 | pb-through | neither | 28.0 | -21.6 | 9.45 | 1.3 | 4.12 | 4.08 | 4.34 | 8 | 4.66 | 90.5 | 0.49 | None | T B T B W | -7.0 | 23.75 | 137.7 | -37.32 | True | 10.0 |
| HSCS 2026-06-23 | 09:30:10 | pb-through +SESSION MISMATCH | neither | 0.2 | 56.2 | 0.18 | 0.0 | 5.32 | 5.06 | 0.86 | 232 | 2.78 | 36.2 | 0.41 | None | B | 9.7 | -15.64 | -15.64 | 10.64 | True | 30.57 |
| ICCM 2026-06-17 | 09:39:20 | pb-through | reclaim | 9.3 | 170.9 | 1.91 | 2.2 | 9.64 | 8.84 | 0.89 | 9 | 13.27 | 51.9 | 0.67 | None | W B T B W | 40.28 | 23.75 | -37.41 | -37.33 | False | 13.33 |
| CCHH 2026-06-11 | 12:08:10 | pb-through | neither | 158.2 | 85.9 | 58.58 | 158.2 | 2.09 | 2.05 | 2.32 | 1 | -22.03 | 117.3 | 0.71 | None | Q | -8.02 | -18.05 | -18.05 | -37.32 | False | 0.52 |
| GOVX 2026-05-18 | 09:42:00 | pb-through | neither | 12.0 | 186.3 | 20.97 | 3.8 | 8.58 | 8.5 | 2.22 | 1 | -4.78 | 28.2 | 0.26 | None | B W B H W | -3.92 | 23.75 | -30.93 | -37.32 | True | 18.0 |
| HCAI 2026-05-18 | 12:49:30 | pb-through | level_hold | 199.5 | 158.0 | 1.08 | 0.0 | 12.1 | 10.91 | 78.93 | 0 | 52.73 | 7.0 | 0.85 | 0.2 | L B H B H | 22.0 | 23.75 | 10.89 | -37.32 | True | 24.69 |
| ILLR 2026-07-06 | 14:58:50 | pb-through | neither | 328.8 | -20.0 | 21.63 | 282.8 | 1.97 | 1.97 | 24.7 | 0 | -12.15 | 243.3 | 0.1 | 112.0 | Q P Q | -2.5 | -2.5 | -2.5 | -37.32 | False | 0.99 |
| VRAX 2026-07-10 | 10:24:40 | pb-through | neither | 54.7 | -30.8 | 12.73 | 54.3 | 0.68 | 0.68 | 3.67 | 0 | -5.33 | 68.0 | 0.41 | None | Q R Q R Q | -14.94 | -19.46 | -19.46 | -37.32 | False | 1.82 |
| QUCY 2026-05-20 | 09:33:40 | pb-through | reclaim | 3.7 | 1.4 | 0.97 | 0.2 | 1.57 | 1.17 | 1.76 | 1 | 5.58 | 117.4 | 0.83 | None | B W B H W | -2.5 | -2.5 | -2.5 | 169.86 | False | 11.02 |
| AZI 2026-06-29 | 09:45:50 | pb-through | neither | 15.8 | 55.9 | 10.69 | 0.3 | 4.56 | 4.48 | 5.85 | 1 | 6.87 | 34.7 | 0.51 | 0.3 | B T L B H | -7.68 | -7.68 | -7.68 | -37.33 | True | 5.21 |
| JEM 2026-07-02 | 09:38:00 | pb-through | neither | 8.0 | 0.0 | 10.9 | 8.0 | 3.75 | 3.74 | 4.13 | 0 | -6.63 | 31.2 | 0.17 | None | T W T R T | -2.5 | -2.5 | -2.5 | -37.32 | False | 1.87 |
| MGRX 2026-07-31 | 10:08:40 | pb-through | neither | 38.7 | 214.0 | 1.96 | 0.2 | 4.8 | 4.65 | 1.98 | 3 | 17.35 | 13.0 | 0.6 | None | H W H W B | 19.13 | 58.9 | 16.64 | -37.33 | True | 35.87 |
| PAVS 2026-06-09 | 09:38:10 | pb-through | neither | 8.2 | 227.5 | 0.0 | 0.2 | 13.65 | 12.01 | 5.24 | 2 | 24.56 | 32.4 | 0.36 | 0.8 | T H T B T | 8.47 | 23.75 | -15.3 | -37.32 | True | 51.84 |
| WLDS 2026-07-23 | 10:36:30 | pb-through | level_hold | 66.5 | 50.0 | 5.42 | 0.2 | 4.69 | 4.5 | 27.33 | 0 | 19.46 | 135.4 | 0.58 | None | P B T B H | -13.17 | -20.59 | -20.59 | -37.32 | False | 17.27 |

Note F = hold-to-15:45 with a −7% catastrophe stop; on these names it is −$37 (stop hit) on 20/23 → his fills are on names that DO trade 7% below his price later in the day; his edge, if any, is the ride/exit, not the hold.

## STEP 3 — the look-alikes (THE FINDING)
Look-alikes = every 10s bar on the same name-day (08:00–15:45 ET) matching the same surface pattern (reclaim OR level_hold), excluding +-2 bars of his: 6,150 bars, median 242 per name-day. His bar's percentile within its own look-alikes, then a CONTROL: 15 random RTH prices per name-day located with the identical method (344 control bars).

| feature | his mean pct (n=23) | control mean pct | his >=75th | control >=75th | verdict |
|---|---|---|---|---|---|
| bar range % | 0.94 | 0.85 | 100% | 81% | mostly locate artifact; small residual |
| pullback depth % | 0.94 | 0.86 | 100% | 81% | same |
| **vol ratio (bar/median30)** | 0.82 | 0.72 | **78%** | **55%** | RESIDUAL — burst-volume bar |
| vol 30s / ticks 30s | 0.89 / 0.88 | 0.82 / 0.81 | 87% / 83% | 76% / 73% | small residual (activity) |
| prior touches at his low (LOW side) | 0.11 | 0.11 | <=25th: 96% | 90% | artifact-equal |
| min since session high (LOW) | 0.16 | 0.17 | 83% | 76% | artifact-equal |
| dist to session high (LOW) | 0.21 | 0.26 | 74% | 65% | weak |
| min since open (LOW) | 0.22 | 0.28 | 65% | 57% | weak |
| spread / buy-fraction / whole-dollar proximity / consolidation length / VWAP-9EMA gap | ~0.4–0.6 | — | — | — | NOT discriminating |

Ranking on the 15 credible fills only: bar_rng 0.97, pb_depth 0.96, ma90_dist 0.93, ticks/vol 0.91, min_since_sess_hi 0.11, dist_sess_hi 0.10, touches 0.15 — same shape; same artifact caveat.

## STEP 3b — SEQUENCE MINING (Marcos: "sequences of these instances")
Alphabet over the 10 minutes before his bar (10s): P push to local high, B break of session high, T test of session high, F flush >=2% (3-bar high->low), W wick at VWAP/9EMA bought back, H hold above whole/half level >=3 bars after break, R retest of a level broken in last 5 min, L halt resumption, Q compression, D lower low. F/D fire almost every bar on these names, so suffixes are read on the STRUCTURAL string (F/D removed, duplicates collapsed).

His strings (last 5 structural events, ending at his bar): LGHL `H T H B H` · ZYBT `L P H P H` · LZMH `T H T B T` · MASK `H B H B W` · MTEN `T B T B W` · STKH `H B H B H` · VIVK `W H W H W` · WYHG `L B H B H` · HSCS `B` · ICCM `W B T B W` · HCAI `L B H B H` · AZI `B T L B H` · MGRX `H W H W B` · PAVS `T H T B T` · WLDS `P B T B H` (mis-dated ones: NAMI `P H R P R`, XHLD `T B T B W`, GOVX `B W B H W`, QUCY `B W B H W`, CCHH `Q`, ILLR `Q P Q`, VRAX `Q R Q R Q`, JEM `T W T R T`).

| suffix (last 2 structural) | his fills (23) | credible (15) | look-alikes (6,150) | control (344) |
|---|---|---|---|---|
| **B H** (break session high -> hold level) | 6 (26%) | 6 (40%) | 3.3% | 15% |
| **B W** (break session high -> wick bought back) | 4 (17%) | 3 (20%) | 3.8% | 5% |
| **B -> H or W** | 10 (43%) | **9 (60%)** | **8.1%** | **20%** |
| any B in last 3 | 16 (70%) | — | 12% | 64% (artifact) |
| k=3 leaders | `H B H` 4, `T B W` 3, `T B T` 2, `B H W` 2 | | 1.5% / 1.3% / 0.1% / 1.7% | |

In plain words: **new session high, THEN the first hold-or-wick — trigger.** The pattern before the B is a test/hold (`T B`, `H B`) i.e. the tape tested/held under the high, broke it, and he takes the first pullback that holds. Never a second/third pullback deep in the range (that is what the look-alikes mostly are: `H W H W`, `P H P H`). This is 3x the control rate and 7x the look-alike rate on the credible set, so it clears the >=60% bar (9/15) and was added as a clause.

## STEP 4 — outcomes from his exact fills
23 fills: KEV-native +$321 (11/23 win), E3 +$338 (12), E4W +$209 (5), F −$402. 2R-before-stop 14/23 (credible 12/15). Where he stated a target it was reachable from the reconstructed bar in 12 of 15 credible cases (LGHL 3.50->3.90: MFE15m 65%; ZYBT 3.10->3.50: 12.9%; LZMH 1.83->2.12: 18%; MTEN 1.29->1.60: 38%; STKH 4.70->5.45: 34%; MASK 3.04->3.29: 60% but a 10s stop-out first (KEV −$5.77) — his 3.02 stop was 0.7% and 10s noise took it in sim). Look-alikes on the same days: KEV mean −$1.92, 2R 30% → his bars are better bars, modestly.

## STEP 5 — generalization on the fastchart replay cohort (198 SIP name-days, 10s, KEV-A/B/C fires, $500 clip, same slippage)
| clause | N | KEV $ | E3 $ | E4W $ | F $ | KEV win |
|---|---|---|---|---|---|---|
| BEFORE (as replayed 8/16) | 399 | −581 | −847 | −2,176 | −3,889 | 25% |
| top-1: vol_ratio >= 2.2 (his p25) | 149 | +838 | +329 | −737 | −4,165 | 29% |
| top-2: + bar_rng >= 3.7% (his p25) | 73 | +474 | +268 | −11 | −2,119 | 32% |
| SEQ only: last-2 structural in {B H, B W} | 79 | +447 | −31 | +356 | −2,927 | 33% (det B: N=59 +576/+340/+877, 37%) |
| top-2 + SEQ | 19 | +588 | +294 | +601 | −712 | 32% |
| "fresh": touches<=1 & <=0.3 min since session high (his p75) | 113 | **+1,323** | +1,162 | +997 | −2,807 | 34% |
| top-2 + fresh | 26 | +805 | +618 | +760 | −814 | 38% |

Every clause flips the detector green vs its own F-control by $2–4k; N is small (19–113 over ~60 days = 0.3–1.9/day); thresholds come from his fills (light in-sample; the cohort overlaps his fills on ZYBT 7/20, LZMH/STKH/MTEN 8/10 only). Detector B (level hold) carries the sequence edge; A dies under the sequence clause (N=0–12).

## Caveats (read before believing)
- n=23 located / 15 credible; dates for 9 fills were RESOLVED by price-in-daily-range (his stated day did not contain the price: LGHL "7/27" -> 7/14; WYHG "8/6" -> 8/10; XHLD "8/12" -> 8/7; ILLR/VRAX likewise) — the 8 non-credible fills probably sit on the wrong day and are kept only for transparency.
- Price-time ambiguity: he rounds ("310", "183"); the fill bar is the FIRST pullback-through of that price in the stated window — if he entered on a later touch, the features move. 3 fills needed the whole day (his stated PRE/RTH session did not contain the price at all: LGHL, LZMH, HSCS).
- **Length-biased sampling: a bar that contains a given price is disproportionately a big bar** — the random-price control was run precisely for this and it explains most of the raw ranking. Only vol-ratio and the B->H/W sequence beat the control by a margin worth reporting.
- 10s from SIP; his glass is 10s (Webull) — same resolution, different bar boundaries; NBBO spread/aggressor computed but not discriminating.
- The generalization uses post-hoc clauses on the 8/16 replay fires (identical fires, filtered), his-fill thresholds, and no OOS wall. Registered hypothesis, not a ship candidate.
