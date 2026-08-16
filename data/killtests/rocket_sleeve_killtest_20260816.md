# ROCKET SLEEVE KILL-TEST — 2026-08-16 (H-VERT + H-HALT as ONE regime lane; Rocket Rider / Hidden Entry Architect)

Script: `data/killtests/rocket_sleeve_killtest_20260816.py` (chain FP -> S -> G -> F -> C -> B -> E imported unchanged for bars/gaps/VWAP/3-min agg; live parity: +1% chase, 0.5% mkt exit, 15:30 no-entry, 15:45 flatten; $500 clip). Raw transcript: `rocket_sleeve_killtest_20260816_run.txt` / `_out.md`; best-variant trades: `_trades.json`; post-hoc cap sensitivity: `_capsens.py` / `_capsens.txt`. Universe 729 name-days, 62 dates 2026-05-18..2026-08-14, RTH only. Analysis only — no bot edits.

**Spec as tested (pre-registered):** in-regime = day-gain from RTH open >= +100% (also +60%), close > session VWAP, NO 4x3-min base (<=12% range) completing in the last 30 min, >=1 halt resumption (>=4-min zero-print gap) in the last 60 min. Entry = pullback low 10-30% below the session high, then first 10s bar with a higher low AND close > prior bar's high; fill = close+1%; stop = pullback low. Cooldown 20 min/name, cap 2/name-day, one open position per name. Halt-in-trade: `exit` = resumption opens below stop -> fill open-0.5% (honest gap-through); `hold` = ignore the intrabar low on the resumption bar, exit only if it CLOSES below stop (fill close-0.5%). Exits: E3, E4 (10%-off-high never-bank), E4W (20%-off-high), STRUCT (1/3 at the session high standing at entry, 1/3 at the next new high after a >=10% dip, rest on the resumption-low ratchet), EOD flatten always. Windows: all-day vs post-11:00 ET.

## VERDICT: **REFUTED as specified.** Best pre-registered variant (+100% post-11:00, E4, hold-through) passes 2/4 graded convexity items (worst trade -$87 PASS, max DD $998 PASS) and FAILS both halves (-$560 / -$187) and home runs (1 of the 5 required). ALL 32 pre-registered variants are net-negative (range -$82 to -$3,603). The only positive pocket is POST-HOC (cap removed, see below) and is carried by the three in-sample C3 specimens -> NEEDS-DATA behind the OOS wall, not a shadow-candidate.

## 1. Regime census
| gain bar | window | name-days ever in-regime | in-regime minutes (sum) | name-days w/ >=1 trigger | raw triggers | trigger name-days that are top-60 big rides |
|---|---|---|---|---|---|---|
| >= +100% | all-day | 96 | 2614 | 72 | 1093 | 36 |
| >= +100% | post-11:00 | 82 | 2114 | 59 | 818 | 31 |
| >= +60% | all-day | 149 | 4214 | 115 | 1926 | 41 |
| >= +60% | post-11:00 | 120 | 3185 | 85 | 1351 | 35 |

Flag funnel (+100%, all-day): 139 name-days reach +100% from the RTH open at some bar; 139 of those are above VWAP at some such bar; 109 also have a halt in the prior 60 min; 96 also lack a 4x3-min base in the prior 30 min. The regime is REAL and common: half of the trigger name-days are top-60 big rides (36/72) — the regime finds the rides; the trigger/exit does not monetize them.

## 2. Variant tables (entry x exit x halt-mode; cap 2/name-day; sequential, no slot cap)
premium = sum of losing trades per 21-trading-day window (3 windows: 21/21/20 dates).

| entry | exit | halt | N | wins | total $ | first-31 / last-31 | HR >=+$250 | worst | max DD | premium /21d | median day | gap-thru fills | big-ride tr N/$ | non-big tr N/$ | mean $risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| +100% all | E3 | exit | 98 | 39 (40%) | -1425 | -1190 / -235 | 0 | -110 | 1805 | -1557 / -604 / -1019 | 0 | 1 | 49/-750 | 49/-676 | 57 |
| +100% all | E3 | hold | 98 | 39 (40%) | -1526 | -1245 / -281 | 0 | -146 | 1821 | -1607 / -604 / -1048 | 0 | 1 | 49/-814 | 49/-712 | 57 |
| +100% all | E4 | exit | 99 | 22 (22%) | -1150 | -829 / -322 | 0 | -93 | 1749 | -1230 / -576 / -1079 | -20 | 1 | 49/-491 | 50/-659 | 57 |
| +100% all | E4 | hold | 99 | 23 (23%) | -1083 | -859 / -224 | 0 | -92 | 1696 | -1249 / -576 / -1053 | -18 | 1 | 49/-393 | 50/-690 | 57 |
| +100% all | E4W | exit | 98 | 17 (17%) | -1682 | -1074 / -608 | 2 | -108 | 1828 | -1653 / -884 / -1484 | -21 | 1 | 49/-215 | 49/-1466 | 57 |
| +100% all | E4W | hold | 96 | 18 (19%) | -1375 | -1172 / -203 | 3 | -146 | 1757 | -1702 / -888 / -1464 | -4 | 1 | 47/+168 | 49/-1543 | 57 |
| +100% all | STRUCT | exit | 97 | 19 (20%) | -2304 | -1247 / -1057 | 0 | -110 | 2304 | -1424 / -579 / -1239 | -18 | 1 | 49/-1389 | 48/-915 | 57 |
| +100% all | STRUCT | hold | 97 | 25 (26%) | -1358 | -935 / -424 | 0 | -110 | 1616 | -1419 / -579 / -1089 | 0 | 1 | 49/-593 | 48/-766 | 57 |
| +100% post11 | E3 | exit | 78 | 33 (42%) | -983 | -855 / -128 | 0 | -110 | 1192 | -1201 / -467 / -714 | 0 | 1 | 42/-590 | 36/-393 | 54 |
| +100% post11 | E3 | hold | 78 | 33 (42%) | -1013 | -910 / -103 | 0 | -110 | 1208 | -1250 / -467 / -701 | 0 | 1 | 42/-584 | 36/-429 | 54 |
| +100% post11 | E4 | exit | 79 | 19 (24%) | -808 | -529 / -278 | 1 | -93 | 1046 | -926 / -404 / -770 | 0 | 1 | 42/-361 | 37/-446 | 55 |
| **+100% post11** | **E4** | **hold** | 79 | 20 (25%) | **-746** | -560 / -187 | 1 | -87 | 998 | -945 / -404 / -750 | 0 | 1 | 42/-270 | 37/-476 | 55 |
| +100% post11 | E4W | exit | 77 | 13 (17%) | -431 | -303 / -127 | 3 | -108 | 1204 | -1382 / -716 / -1042 | 0 | 1 | 41/+740 | 36/-1171 | 55 |
| +100% post11 | E4W | hold | 75 | 14 (19%) | -82 | -401 / +319 | 4 | -110 | 1272 | -1431 / -721 / -979 | 0 | 1 | 39/+1166 | 36/-1247 | 55 |
| +100% post11 | STRUCT | exit | 77 | 18 (23%) | -1259 | -573 / -686 | 1 | -110 | 1259 | -1156 / -430 / -899 | 0 | 1 | 42/-620 | 35/-639 | 55 |
| +100% post11 | STRUCT | hold | 77 | 21 (27%) | -830 | -573 / -257 | 1 | -110 | 1135 | -1156 / -430 / -798 | 0 | 1 | 42/-203 | 35/-628 | 55 |
| +60% all | E3 | exit | 163 | 65 (40%) | -1792 | -1580 / -212 | 0 | -129 | 2333 | -2126 / -1170 / -1624 | -23 | 2 | 58/-420 | 105/-1372 | 54 |
| +60% all | E3 | hold | 163 | 65 (40%) | -1904 | -1635 / -269 | 0 | -146 | 2352 | -2175 / -1161 / -1653 | -23 | 1 | 58/-503 | 105/-1400 | 54 |
| +60% all | E4 | exit | 163 | 37 (23%) | -1337 | -1156 / -181 | 1 | -93 | 2435 | -1772 / -1022 / -1663 | -41 | 1 | 58/+147 | 105/-1484 | 54 |
| +60% all | E4 | hold | 163 | 38 (23%) | -1308 | -1187 / -121 | 1 | -92 | 2404 | -1791 / -1022 / -1660 | -41 | 1 | 58/+207 | 105/-1514 | 54 |
| +60% all | E4W | exit | 158 | 26 (16%) | -3603 | -2127 / -1476 | 2 | -104 | 3784 | -2484 / -1413 / -2240 | -66 | 2 | 58/-633 | 100/-2970 | 54 |
| +60% all | E4W | hold | 156 | 27 (17%) | -3382 | -2227 / -1155 | 3 | -146 | 3478 | -2539 / -1404 / -2250 | -67 | 1 | 56/-351 | 100/-3031 | 54 |
| +60% all | STRUCT | exit | 158 | 43 (27%) | -2870 | -1640 / -1230 | 0 | -129 | 2878 | -1962 / -1098 / -1777 | -30 | 2 | 57/-1304 | 101/-1566 | 54 |
| +60% all | STRUCT | hold | 158 | 47 (30%) | -1517 | -1271 / -246 | 0 | -129 | 2040 | -1931 / -1056 / -1653 | -24 | 1 | 57/-283 | 101/-1234 | 54 |
| +60% post11 | E3 | exit | 121 | 53 (44%) | -864 | -958 / +94 | 0 | -97 | 1417 | -1491 / -602 / -1177 | 0 | 2 | 50/-287 | 71/-577 | 52 |
| +60% post11 | E3 | hold | 121 | 53 (44%) | -904 | -1012 / +108 | 0 | -110 | 1436 | -1541 / -594 / -1165 | 0 | 1 | 50/-299 | 71/-605 | 52 |
| +60% post11 | E4 | exit | 121 | 30 (25%) | -742 | -809 / +68 | 2 | -93 | 1492 | -1279 / -572 / -1199 | -18 | 1 | 50/+139 | 71/-881 | 52 |
| +60% post11 | E4 | hold | 121 | 31 (26%) | -718 | -840 / +122 | 2 | -87 | 1467 | -1298 / -572 / -1202 | -21 | 1 | 50/+193 | 71/-911 | 52 |
| +60% post11 | E4W | exit | 115 | 18 (16%) | -1718 | -687 / -1031 | 3 | -97 | 1930 | -1869 / -846 / -1695 | -43 | 2 | 49/+205 | 66/-1923 | 51 |
| +60% post11 | E4W | hold | 113 | 19 (17%) | -1362 | -787 / -575 | 4 | -110 | 1661 | -1925 / -838 / -1632 | -45 | 1 | 47/+621 | 66/-1983 | 51 |
| +60% post11 | STRUCT | exit | 118 | 34 (29%) | -1490 | -751 / -739 | 1 | -97 | 1498 | -1482 / -639 / -1337 | -4 | 2 | 49/-633 | 69/-858 | 52 |
| +60% post11 | STRUCT | hold | 118 | 36 (31%) | -624 | -727 / +103 | 1 | -97 | 1303 | -1474 / -603 / -1256 | 0 | 1 | 49/+46 | 69/-670 | 52 |

Reading: (a) hold-through beats exit-on-resumption in 13 of 16 pairs but by tens of dollars — the halt-mode is not the lever; only ONE gap-through fill occurred in most variants (the stops are 10-30% under a vertical, resumption gaps rarely reach them). (b) Wider trail = more home runs, more bleed: E4W finds 3-4 HRs but its non-big fires lose -$1.2k..-$3.0k. (c) STRUCT (sell into structure + ratchet) is the WORST family: the 1/3 sold at the standing session high caps the winners while the un-ratcheted rest still eats the stop. (d) +60% widens N by 60% and only adds losers. (e) Non-big fires are net-negative in ALL 32 variants (-$393 to -$3,031); big-ride fires are positive only under E4/E4W post-11.

## 3. Convexity bar — best pre-registered variant: +100% post-11:00, E4 (10%-off-high never-bank), hold-through
| # | criterion | value | pass |
|---|---|---|---|
| 1 | total P&L positive in BOTH halves (first-31 / last-31 dates) | -$560 / -$187 | FAIL |
| 2 | >= 5 trades >= +$250 | 1 | FAIL |
| 3 | worst single trade > -$150 | -$87.00 (no gap-through in this variant's worst; 1 gap-through fill lane-wide) | PASS |
| 4 | max drawdown of the lane's equity curve < $1,000 | $998 (on the line) | PASS |
| 5 | PREMIUM (sum of losers per 21-day window) — priced by Marcos, no pass/fail | -$945 / -$404 / -$750 (~-$700/month; = a $700/mo insurance premium that bought ONE +$250 payout in 3 months) | info |
| info | median day (not a criterion) | $0.00 (lane idle most days: 36 trade-days of 62; 8 green) | - |
| info | N 79, wins 20 (25%), total -$746, mean -$9/trade, mean $risk $55 (11% of clip) | | |
Best variant scores 2/4. Base-rate honesty: 42 fires on top-60 big-ride name-days = -$270 (13 wins); 37 fires on NON-big name-days = -$476 (7 wins, mean -$13). Even where the regime found the ride, the trigger did not pay.

### Why the ride is missed (mechanism, from the traces): the cap of 2 entries/name-day is spent EARLY. INHD 6/08 (RTH open 1.11 -> high 43.37): in-regime from 09:49 ET; both bullets fired at 11:00 (+$265) and 11:46 (+$21, chopped by the 10%-off-high trail); the C3 ride starts 13:19 with 0 bullets left — the lane is IN-REGIME at 13:19 (gain +847%, above VWAP, no base, halt-60 True) and cannot enter. ZYBT 7/20: bullets at 13:09 (-$45, stopped on the second resumption low) and 13:32 (+$9); ride starts 14:00, in-regime, no bullet. PAVS 6/09: bullets at 11:08 (+$33) and 11:32 (-$7); the C3 start (10:46) is NOT in-regime because PAVS was BELOW session VWAP then (as big_rides already flagged: below-VWAP). Second mechanism: the 10%-off-high trail exits INSIDE the vertical (INHD 11:17 trail out at 6.17 vs the 43 high; ZYBT 13:55 trail out at 3.03 vs the 8.40 high) — this is v1's autopsy again: confirmation-then-tight-trail sells the rocket at the first shake.

## 4. Post-hoc sensitivity (NOT pre-registered; information only): remove the 2/name-day cap (cooldown 20 min + one open position still enforced), +100% post-11:00
| cap | exit | halt | N | total | halves | HR | worst | max DD | premium | big N/$ | non-big N/$ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 (spec) | E4W | hold | 75 | -82 | -401/+319 | 4 | -110 | 1272 | -1431/-721/-979 | 39/+1166 | 36/-1247 |
| 4 | E4 | hold | 95 | -502 | -831/+329 | 2 | -87 | 1185 | -1132/-589/-824 | 49/+309 | 46/-811 |
| 4 | E4W | hold | 84 | -343 | -652/+309 | 4 | -110 | 1459 | -1682/-766/-1026 | 44/+1062 | 40/-1405 |
| none | E4 | hold | 98 | +192 | -137/+329 | 3 | -87 | 1014 | -1186/-589/-824 | 51/+1054 | 47/-862 |
| none | E4 | exit | 98 | +213 | -107/+320 | 3 | -93 | 984 | -1166/-589/-843 | 51/+1044 | 47/-832 |
| **none** | **E4W** | **hold** | 85 | **+404** | **+95/+309** | **5** | -110 | **1459** | -1682/-766/-1026 | 45/+1810 | 40/-1405 |
| none | STRUCT | hold | 92 | -539 | -311/-228 | 2 | -110 | 1106 | -1428/-531/-911 | 50/+359 | 42/-898 |
Uncapped E4W-hold would score 3/4 (fails max DD $1,459) — BUT its 5 home runs are INHD 6/08 13:33 ET (+$747, held to the 15:45 flatten), PAVS 6/09 11:08 (+$765), ZYBT 7/20 13:32 (+$719) + 2 more: the in-sample C3 specimens the spec was written FROM. Strip the three specimens and the pocket is -$1,827. Its non-big fires lose -$1,405 on 40 trades (-$35/tr): the premium is ~$1,150/month for a payout that in-sample was 3 named names. This is exactly the Seam Scientist rule: 8 of 9 specimens in-sample -> the pocket cannot be graded until >=5 new dates. Cap-2 vs uncapped is also a real design fork Marcos owns (more bullets on a running crowned name = the Leader Meritocracy sticky-crown x3 slots idea, not a lane parameter).

## 5. Hostile-halt gauntlet — 10 name-days with the most halt gaps (best variant E4-hold post-11; twin = exit-on-resumption)
| name-day | halts | lane tr | lane P&L | worst tr | its exit | gap-through mechanics | twin P&L | whole-date lane P&L |
|---|---|---|---|---|---|---|---|---|
| ZYBT 2026-07-20 | 37 | 2 | -$36 | -$45 | stop@13:20 ET | resume 13:14 open 2.98 (stop 2.67, held); resume 13:20 open 2.68 close 2.70 -> next bar low 2.67 = stop, fill 2.6566 (no gap-through) | -$36 | -$36 |
| CCTG 2026-06-09 | 36 | 0 | 0 | - | - | no lane entry | 0 | +$25 |
| BYAH 2026-06-08 | 32 | 0 | 0 | - | - | no lane entry (below VWAP at its ride, per big_rides) | 0 | +$343 |
| BRUNW 2026-07-30 | 32 | 0 | 0 | - | - | no lane entry | 0 | 0 |
| CDTG 2026-06-04 | 31 | 1 | -$37 | -$37 | trail@11:37 | resume 11:37 open 13.97 close 14.00, stop 11.69 held; trailed out on the resumption bar's own close | -$37 | -$175 |
| YXT 2026-08-05 | 30 | 2 | +$226 | +$68 | trail@14:47 | resume 14:47 open 23.81 close 21.43 (stop 17.24 held), trail on close | +$226 | +$311 |
| PLAG 2026-08-11 | 29 | 2 | +$71 | -$72 | resumeclose@12:24 | resume 12:24 open 2.90 < stop 3.15 (GAP-THROUGH), close 3.05 < stop -> hold-through fill 3.0347 = -3.7% below stop; exit-twin fills open 2.8855 = -8.4% below stop | +$50 | +$71 |
| LZMH 2026-08-07 | 28 | 0 | 0 | - | - | no lane entry | 0 | +$5 |
| MTEN 2026-06-08 | 27 | 0 | 0 | - | - | no lane entry | 0 | +$343 |
| XCH 2026-06-23 | 27 | 0 | 0 | - | - | no lane entry | 0 | -$47 |
Gauntlet worst day: CDTG 6/04 whole-date -$175 (lane); worst single gap-through: PLAG 8/11 12:24 ET, resumption open 8.4% through the stop (exit-mode fill) — the -$150 floor held on every gauntlet day (worst trade lane-wide -$87 in this variant; -$146 in the E3/E4W-hold variants where a hold-through resumption close sat 12% under the stop). Gap-through is RARE here (1-2 fills of ~80-160 trades per variant) because the pullback stops sit 10-30% under a vertical; halts in these names mostly resolved UP or flat vs the stop.

## 6. Hand-traces (best pre-registered variant, E4-hold post-11; UTC-4 = ET)
**INHD 2026-06-08** (RTH open 1.11, high 43.37, close 32.00; 8 halt gaps): in-regime 154 min from 09:49 ET. 57 raw triggers. Trade 1 11:00:00 ET entry 3.9934 fill 4.0333 stop 3.4201 (risk $76) day-gain +260%, -13% from hi 4.60 -> 11:17:20 TRAIL 10%-off-high close 6.20 fill 6.169 = **+$264.75** (the day's one home run at $500... exited with the name at $6 on a $43 day). Trade 2 11:46:20 entry 7.9582 fill 8.0378 stop 7.28 (risk $47) -> 11:49:10 trail close 8.42 fill 8.378 = +$21.15. C3 ride start 13:19 @ 10.515: gain +847%, above VWAP, no base, halt-60 -> IN-REGIME but cap spent. (Uncapped E4W: 13:33 entry 15.56 -> 15:45 flatten = +$747.)
**PAVS 2026-06-09** (open 1.55, high 26.69, close 1.04; 17 gaps): in-regime 98 min 09:45-12:35 ET. 13 raw triggers. Trade 1 11:08 entry 7.695 fill 7.772 stop 6.62 (risk $74) +396% day -> 11:11:30 trail close 8.32 fill 8.278 = +$32.58. Trade 2 11:32:20 entry 11.74 fill 11.857 stop 10.80 -> 11:32:50 trail close 11.7414 fill 11.683 = -$7.37 (10%-off-high fired 30s after entry off a 13.62 print — 10s-bar noise on a $12 name). C3 start 10:46 @ 4.865: +214%, BELOW VWAP -> not in-regime (by spec; the VWAP leg of the regime is what excludes PAVS's ride, exactly the below-VWAP tag big_rides gave it). Note the day CLOSED at 1.04 from a 26.69 high: an EOD hold here would have been the -$150 breach the bar fears; every variant was out by 11:33.
**ZYBT 2026-07-20** (open 1.27, high 8.40, close 7.30; 37 gaps): in-regime only 21 min from 12:58 ET. 21 raw triggers. Trade 1 13:09 entry 2.89 fill 2.919 stop 2.67 (risk $43) -> two resumptions (13:14 open 2.98; 13:20 open 2.68) then 13:20:30 STOP 2.67 fill 2.6566 = -$44.92 (hold-through: the 13:20 resumption bar closed 2.70 >= stop so the intrabar 2.68 was ignored; the NEXT bar's low 2.67 hit). Trade 2 13:32:40 entry 2.95 fill 2.9795 stop 2.60 -> resumptions 13:38 (o 3.04), 13:44 (o 3.15), 13:49 (o 3.40), 13:55 (o 3.20 c 3.05) -> 13:55:30 trail close 3.05 fill 3.035 = +$9.27; the name went to 8.40. C3 start 14:00 @ 2.94: in-regime, cap spent. (Uncapped E4W: 13:32 entry, ridden through the halt ladder to the 15:45 flatten = +$719.)

## 7. What this means (officers)
- **Convexity Trader:** the lane as specified is negative-mean AND has no tail: 0-1 home runs at $500 in 62 dates in every E3/E4/STRUCT variant. Insurance that never pays is not insurance. REFUTED.
- **Rocket Rider / Hidden Entry Architect:** the regime detector is worth keeping as a DESCRIPTOR (half its trigger name-days are top-60 rides). The trigger (HL + close > prior high inside a 10-30% pullback) is a confirmation entry with a tight trail — v1's autopsy shape. Two open forks are Marcos's, not the auditor's: (i) bullets per crowned name (cap 2 vs uncapped: sticky-crown x3 slots doctrine), (ii) trail width inside a halt ladder (10% is noise on a $12 name at 10s resolution). Neither is graded here; the uncapped E4W pocket goes behind the OOS wall (>=5 new dates) as a registered hypothesis: "uncapped rocket-sleeve E4W-hold post-11 mean/trade > $0 out-of-sample with non-big fires > -$25/tr".
- **Halt lane / Side Marshal:** hold-through vs exit-on-resumption is a wash here (+/- tens of dollars, 1-2 gap-throughs per variant); rocket_anatomy's "+$60/tr held across halts" does not transfer to a mid-range pullback entry — those trades were entered BEFORE the halt at the leg's first pullback, this lane enters AFTER halts on a deeper pullback.
- **Statistician:** every number above is from `rocket_sleeve_killtest_20260816_run.txt` (pre-registered) and `_capsens.txt` (post-hoc, labeled). Median day = $0 in the best variant (36 trade-days of 62).
- **Strength Ombudsman:** the VWAP leg of the regime refused PAVS's C3 ride (below VWAP at 10:46, +174% after) — a refused-strength case for the ledger, priced: uncapped E4 entered PAVS 11:08 above VWAP for +$765 later anyway.
- **Wind Tunnel:** chain unchanged; new exit engine `sim_sleeve` is lane-specific (halt modes + STRUCT) and reconciles to F.sim_var semantics for stop/trail/flatten (same fills: stop-0.5%, close-0.5%, 15:45 flatten). Not rig-tested against the live engine (analysis only).
- **Blast Radius Auditor:** nothing shipped; no bot edits.

## Caveats (honesty)
- Day-gain measured from the RTH OPEN (spec: "from open"); big_rides' "+901% at start" style figures were vs the prior reference, so the +100% bar here is STRICTER on gap-up names and LOOSER on premarket runners.
- Halts = >=4-min zero-print gaps on the 10s tape (not exchange LULD stamps). Session VWAP = RTH-anchored (premarket excluded), per the "session VWAP" wording; big_rides used premarket-anchored VWAP.
- STRUCT's "each new session high" was operationalized as: level 1 = the session high standing at entry, level 2 = the next new high after a >=10% dip; other operationalizations exist.
- No slot cap across names (lane graded standalone); a 2-slot portfolio would only remove trades.
- 8 of 9 C3/C1 specimens are in-sample: no positive pocket here can count as evidence until >=5 new dates (Seam Scientist wall).

## RAW OUTPUT
# ROCKET SLEEVE KILL-TEST — 2026-08-16 (H-VERT + H-HALT as one regime lane)
universe: 729 files, 729 RTH day-files, 62 dates 2026-05-18..2026-08-14; RTH bars only; chain FP->S->G->F->C->B->E (data/gaps/VWAP/3-min agg reused unchanged); LIVE parity: +1% chase, 0.5% mkt exit, 15:30 no-entry, 15:45 flatten, $500 clip
regime: day-gain from RTH open >= G, close > session VWAP, no 4x3-min base (<=12% range) completing in last 30 min, >=1 halt resumption (>=4-min zero-print gap) in last 60 min. entry: pullback low 10-30% under session high, first bar HL + close > prior high; stop = pullback low; cooldown 20 min; cap 2/name-day; one open position per name.

## 1. REGIME CENSUS
| gain bar | window | name-days ever in-regime | in-regime bar-minutes (sum) | name-days w/ >=1 trigger | raw triggers | of which big-ride (top-60) name-days |
|---|---|---|---|---|---|---|
| >= +100% | all-day | 96 | 2614 | 72 | 1093 | 36 |
| >= +100% | post-11:00 | 82 | 2114 | 59 | 818 | 31 |
| >= +60% | all-day | 149 | 4214 | 115 | 1926 | 41 |
| >= +60% | post-11:00 | 120 | 3185 | 85 | 1351 | 35 |
flag funnel (all-day, +100%): name-days with day-gain>=+100% at some bar: 139; with a halt: 385; gain&VWAP: 139; gain&VWAP&halt-in-60: 109

## 2. VARIANT TABLES (entry variant x exit variant), all trades sequential (no slot cap), $500 clip
| entry variant | exit | halt | N | wins | total $ | first-31 / last-31 dates | home runs >=+$250 | worst trade | max DD | premium per 21-day window (sum of losers) | median day | trade-days green | gap-through fills | big-ride tr (N/$) | non-big tr (N/$) | mean $risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| +100% all | E3 | exit | 98 | 39 (40%) | $-1425 | $-1190 / $-235 | 0 | $-110 | $1805 | $-1557 / $-604 / $-1019 | $+0 | 16/42 | 1 | 49/$-750 | 49/$-676 | $57 |
| +100% all | E3 | hold | 98 | 39 (40%) | $-1526 | $-1245 / $-281 | 0 | $-146 | $1821 | $-1607 / $-604 / $-1048 | $+0 | 16/42 | 1 | 49/$-814 | 49/$-712 | $57 |
| +100% all | E4 | exit | 99 | 22 (22%) | $-1150 | $-829 / $-322 | 0 | $-93 | $1749 | $-1230 / $-576 / $-1079 | $-20 | 9/42 | 1 | 49/$-491 | 50/$-659 | $57 |
| +100% all | E4 | hold | 99 | 23 (23%) | $-1083 | $-859 / $-224 | 0 | $-92 | $1696 | $-1249 / $-576 / $-1053 | $-18 | 9/42 | 1 | 49/$-393 | 50/$-690 | $57 |
| +100% all | E4W | exit | 98 | 17 (17%) | $-1682 | $-1074 / $-608 | 2 | $-108 | $1828 | $-1653 / $-884 / $-1484 | $-21 | 9/42 | 1 | 49/$-215 | 49/$-1466 | $57 |
| +100% all | E4W | hold | 96 | 18 (19%) | $-1375 | $-1172 / $-203 | 3 | $-146 | $1757 | $-1702 / $-888 / $-1464 | $-4 | 11/42 | 1 | 47/$+168 | 49/$-1543 | $57 |
| +100% all | STRUCT | exit | 97 | 19 (20%) | $-2304 | $-1247 / $-1057 | 0 | $-110 | $2304 | $-1424 / $-579 / $-1239 | $-18 | 8/42 | 1 | 49/$-1389 | 48/$-915 | $57 |
| +100% all | STRUCT | hold | 97 | 25 (26%) | $-1358 | $-935 / $-424 | 0 | $-110 | $1616 | $-1419 / $-579 / $-1089 | $+0 | 13/42 | 1 | 49/$-593 | 48/$-766 | $57 |
| +100% post11 | E3 | exit | 78 | 33 (42%) | $-983 | $-855 / $-128 | 0 | $-110 | $1192 | $-1201 / $-467 / $-714 | $+0 | 12/36 | 1 | 42/$-590 | 36/$-393 | $54 |
| +100% post11 | E3 | hold | 78 | 33 (42%) | $-1013 | $-910 / $-103 | 0 | $-110 | $1208 | $-1250 / $-467 / $-701 | $+0 | 12/36 | 1 | 42/$-584 | 36/$-429 | $54 |
| +100% post11 | E4 | exit | 79 | 19 (24%) | $-808 | $-529 / $-278 | 1 | $-93 | $1046 | $-926 / $-404 / $-770 | $+0 | 7/36 | 1 | 42/$-361 | 37/$-446 | $55 |
| +100% post11 | E4 | hold | 79 | 20 (25%) | $-746 | $-560 / $-187 | 1 | $-87 | $998 | $-945 / $-404 / $-750 | $+0 | 8/36 | 1 | 42/$-270 | 37/$-476 | $55 |
| +100% post11 | E4W | exit | 77 | 13 (17%) | $-431 | $-303 / $-127 | 3 | $-108 | $1204 | $-1382 / $-716 / $-1042 | $+0 | 8/36 | 1 | 41/$+740 | 36/$-1171 | $55 |
| +100% post11 | E4W | hold | 75 | 14 (19%) | $-82 | $-401 / $+319 | 4 | $-110 | $1272 | $-1431 / $-721 / $-979 | $+0 | 9/36 | 1 | 39/$+1166 | 36/$-1247 | $55 |
| +100% post11 | STRUCT | exit | 77 | 18 (23%) | $-1259 | $-573 / $-686 | 1 | $-110 | $1259 | $-1156 / $-430 / $-899 | $+0 | 9/36 | 1 | 42/$-620 | 35/$-639 | $55 |
| +100% post11 | STRUCT | hold | 77 | 21 (27%) | $-830 | $-573 / $-257 | 1 | $-110 | $1135 | $-1156 / $-430 / $-798 | $+0 | 12/36 | 1 | 42/$-203 | 35/$-628 | $55 |
| +60% all | E3 | exit | 163 | 65 (40%) | $-1792 | $-1580 / $-212 | 0 | $-129 | $2333 | $-2126 / $-1170 / $-1624 | $-23 | 16/52 | 2 | 58/$-420 | 105/$-1372 | $54 |
| +60% all | E3 | hold | 163 | 65 (40%) | $-1904 | $-1635 / $-269 | 0 | $-146 | $2352 | $-2175 / $-1161 / $-1653 | $-23 | 15/52 | 1 | 58/$-503 | 105/$-1400 | $54 |
| +60% all | E4 | exit | 163 | 37 (23%) | $-1337 | $-1156 / $-181 | 1 | $-93 | $2435 | $-1772 / $-1022 / $-1663 | $-41 | 11/52 | 1 | 58/$+147 | 105/$-1484 | $54 |
| +60% all | E4 | hold | 163 | 38 (23%) | $-1308 | $-1187 / $-121 | 1 | $-92 | $2404 | $-1791 / $-1022 / $-1660 | $-41 | 11/52 | 1 | 58/$+207 | 105/$-1514 | $54 |
| +60% all | E4W | exit | 158 | 26 (16%) | $-3603 | $-2127 / $-1476 | 2 | $-104 | $3784 | $-2484 / $-1413 / $-2240 | $-66 | 9/52 | 2 | 58/$-633 | 100/$-2970 | $54 |
| +60% all | E4W | hold | 156 | 27 (17%) | $-3382 | $-2227 / $-1155 | 3 | $-146 | $3478 | $-2539 / $-1404 / $-2250 | $-67 | 10/52 | 1 | 56/$-351 | 100/$-3031 | $54 |
| +60% all | STRUCT | exit | 158 | 43 (27%) | $-2870 | $-1640 / $-1230 | 0 | $-129 | $2878 | $-1962 / $-1098 / $-1777 | $-30 | 13/52 | 2 | 57/$-1304 | 101/$-1566 | $54 |
| +60% all | STRUCT | hold | 158 | 47 (30%) | $-1517 | $-1271 / $-246 | 0 | $-129 | $2040 | $-1931 / $-1056 / $-1653 | $-24 | 17/52 | 1 | 57/$-283 | 101/$-1234 | $54 |
| +60% post11 | E3 | exit | 121 | 53 (44%) | $-864 | $-958 / $+94 | 0 | $-97 | $1417 | $-1491 / $-602 / $-1177 | $+0 | 17/46 | 2 | 50/$-287 | 71/$-577 | $52 |
| +60% post11 | E3 | hold | 121 | 53 (44%) | $-904 | $-1012 / $+108 | 0 | $-110 | $1436 | $-1541 / $-594 / $-1165 | $+0 | 17/46 | 1 | 50/$-299 | 71/$-605 | $52 |
| +60% post11 | E4 | exit | 121 | 30 (25%) | $-742 | $-809 / $+68 | 2 | $-93 | $1492 | $-1279 / $-572 / $-1199 | $-18 | 11/46 | 1 | 50/$+139 | 71/$-881 | $52 |
| +60% post11 | E4 | hold | 121 | 31 (26%) | $-718 | $-840 / $+122 | 2 | $-87 | $1467 | $-1298 / $-572 / $-1202 | $-21 | 11/46 | 1 | 50/$+193 | 71/$-911 | $52 |
| +60% post11 | E4W | exit | 115 | 18 (16%) | $-1718 | $-687 / $-1031 | 3 | $-97 | $1930 | $-1869 / $-846 / $-1695 | $-43 | 8/46 | 2 | 49/$+205 | 66/$-1923 | $51 |
| +60% post11 | E4W | hold | 113 | 19 (17%) | $-1362 | $-787 / $-575 | 4 | $-110 | $1661 | $-1925 / $-838 / $-1632 | $-45 | 9/46 | 1 | 47/$+621 | 66/$-1983 | $51 |
| +60% post11 | STRUCT | exit | 118 | 34 (29%) | $-1490 | $-751 / $-739 | 1 | $-97 | $1498 | $-1482 / $-639 / $-1337 | $-4 | 15/46 | 2 | 49/$-633 | 69/$-858 | $52 |
| +60% post11 | STRUCT | hold | 118 | 36 (31%) | $-624 | $-727 / $+103 | 1 | $-97 | $1303 | $-1474 / $-603 / $-1256 | $+0 | 17/46 | 1 | 49/$+46 | 69/$-670 | $52 |

## 3. CONVEXITY BAR — best variant: entry +100% post-11, exit E4, halt-hold
| # | criterion | value | pass |
|---|---|---|---|
| 1 | total P&L positive in BOTH halves (first-31 / last-31 dates) | $-560 / $-187 | FAIL |
| 2 | >= 5 trades >= +$250 | 1 | FAIL |
| 3 | worst single trade > -$150 | $-87.00 | PASS |
| 4 | max drawdown of lane equity < $1,000 | $998 | PASS |
| 5 | PREMIUM: sum of losing trades per 21-day window (no pass/fail) | $-945 / $-404 / $-750 | (priced by Marcos) |
| info | median day (not a criterion) | $+0.00 | - |
| info | N 79, wins 20, total $-746, mean $-9/trade |  |  |
passed 2/4 graded items

### best-variant trade list (all)
| date | sym | t(UTC) | entry | stop | risk$ | day-gain@entry | %from hi | exit | pnl | halts in trade | gap-thru | big-ride? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-22 | RYOJ | 16:28:30 | 7.3200 | 6.7100 | 46 | +201% | -9% | trail@16:37:00 | $-33.71 | 0 |  | Y |
| 2026-05-22 | RYOJ | 16:49:20 | 7.2710 | 6.7400 | 41 | +199% | -10% | stop@16:52:40 | $-43.40 | 0 |  | Y |
| 2026-05-26 | BRAI | 15:01:50 | 17.2799 | 15.6500 | 52 | +100% | -7% | trail@15:09:00 | $-44.48 | 0 |  |  |
| 2026-05-27 | ASTC | 15:50:30 | 16.4801 | 15.4200 | 37 | +122% | -4% | trail@15:57:30 | $+12.60 | 0 |  |  |
| 2026-05-27 | ASTC | 16:12:00 | 15.3700 | 14.8600 | 21 | +107% | -22% | stop@16:12:40 | $-23.77 | 0 |  |  |
| 2026-05-28 | MASK | 15:03:00 | 4.5202 | 4.1800 | 42 | +142% | -12% | trail@15:04:30 | $-39.06 | 0 |  |  |
| 2026-05-28 | MASK | 15:25:00 | 4.2100 | 3.8800 | 44 | +126% | -18% | trail@15:39:00 | $-3.93 | 0 |  |  |
| 2026-05-29 | CDT | 17:25:20 | 2.5550 | 2.5300 | 10 | +137% | -12% | stop@17:25:30 | $-12.25 | 0 |  |  |
| 2026-05-29 | YMAT | 17:32:30 | 2.2800 | 1.9300 | 81 | +128% | -12% | trail@17:34:10 | $-52.79 | 0 |  | Y |
| 2026-06-01 | AIM | 16:35:30 | 1.1500 | 0.9102 | 108 | +107% | -8% | trail@16:41:10 | $-55.01 | 0 |  | Y |
| 2026-06-03 | TJGC | 17:12:30 | 6.7900 | 6.3200 | 39 | +166% | -4% | stop@17:46:30 | $-41.52 | 0 |  | Y |
| 2026-06-04 | WXM | 15:04:10 | 9.6000 | 8.6400 | 54 | +116% | -3% | stop@15:10:30 | $-56.68 | 1 |  |  |
| 2026-06-04 | CDTG | 15:32:30 | 13.7200 | 11.6900 | 78 | +110% | -1% | trail@15:37:50 | $-36.70 | 1 |  | Y |
| 2026-06-04 | VERU | 16:26:00 | 6.8600 | 6.5600 | 27 | +216% | -6% | stop@16:26:30 | $-28.97 | 0 |  | Y |
| 2026-06-04 | SDOT | 18:10:10 | 13.1500 | 12.1401 | 43 | +109% | -6% | trail@18:18:10 | $-42.64 | 0 |  |  |
| 2026-06-04 | SDOT | 18:39:00 | 13.1650 | 11.2300 | 78 | +109% | -6% | trail@18:44:40 | $-9.86 | 0 |  |  |
| 2026-06-08 | INHD | 15:00:00 | 3.9934 | 3.4201 | 76 | +260% | -13% | trail@15:17:20 | $+264.75 | 0 |  | Y |
| 2026-06-08 | INHD | 15:46:20 | 7.9582 | 7.2800 | 47 | +617% | -10% | trail@15:49:10 | $+21.15 | 0 |  | Y |
| 2026-06-08 | NPT | 18:12:00 | 8.5897 | 7.9500 | 42 | +556% | -5% | stop@18:14:00 | $-44.11 | 0 |  | Y |
| 2026-06-08 | SUNE | 18:46:30 | 6.2899 | 6.1000 | 20 | +111% | -8% | trail@18:57:10 | $+106.92 | 0 |  |  |
| 2026-06-08 | SUNE | 19:08:30 | 7.4000 | 7.1100 | 24 | +148% | -22% | trail@19:16:20 | $-5.43 | 0 |  |  |
| 2026-06-09 | PAVS | 15:08:00 | 7.6950 | 6.6200 | 74 | +396% | -10% | trail@15:11:30 | $+32.58 | 0 |  | Y |
| 2026-06-09 | PAVS | 15:32:20 | 11.7400 | 10.8000 | 45 | +657% | -12% | trail@15:32:50 | $-7.37 | 0 |  | Y |
| 2026-06-10 | SDOT | 17:02:50 | 30.0000 | 26.5000 | 63 | +110% | -18% | trail@17:20:10 | $-13.17 | 0 |  |  |
| 2026-06-10 | CPOP | 17:20:00 | 2.4800 | 2.1800 | 65 | +386% | -3% | stop@17:20:20 | $-67.01 | 0 |  | Y |
| 2026-06-11 | GELS | 16:10:30 | 1.7800 | 1.5450 | 70 | +249% | -11% | trail@16:12:10 | $-60.59 | 0 |  | Y |
| 2026-06-11 | ADIL | 16:30:10 | 4.4500 | 4.0100 | 54 | +107% | -5% | stop@16:30:20 | $-56.13 | 0 |  |  |
| 2026-06-12 | CAST | 15:07:30 | 1.3500 | 1.2500 | 42 | +126% | -9% | trail@15:23:40 | $+109.33 | 2 |  |  |
| 2026-06-12 | CAST | 15:34:30 | 1.5300 | 1.3700 | 57 | +156% | -22% | resumeclose@15:45:30 | $-78.22 | 2 |  |  |
| 2026-06-15 | RGNT | 16:43:50 | 7.6000 | 6.8000 | 57 | +347% | -2% | trail@16:45:30 | $-8.72 | 0 |  |  |
| 2026-06-15 | RGNT | 18:02:00 | 12.6800 | 11.5000 | 51 | +646% | -15% | trail@18:07:40 | $-17.53 | 0 |  |  |
| 2026-06-15 | PRFX | 19:12:50 | 3.5000 | 2.8600 | 95 | +157% | -11% | trail@19:15:50 | $-62.43 | 0 |  | Y |
| 2026-06-23 | FCUV | 15:10:50 | 6.7900 | 6.2500 | 44 | +211% | -8% | stop@15:12:10 | $-46.60 | 0 |  |  |
| 2026-06-24 | BOXL | 15:14:10 | 7.6600 | 6.0800 | 107 | +102% | -1% | trail@15:20:40 | $-16.43 | 1 |  |  |
| 2026-06-24 | BOXL | 15:56:00 | 7.6000 | 6.3200 | 88 | +100% | -9% | trail@16:07:20 | $-9.45 | 0 |  |  |
| 2026-06-24 | SCAG | 17:46:00 | 0.8200 | 0.7840 | 27 | +123% | -7% | stop@17:46:30 | $-29.05 | 0 |  |  |
| 2026-06-25 | VNTG | 15:52:10 | 1.3400 | 1.1300 | 83 | +103% | -8% | trail@16:00:50 | $-29.48 | 1 |  |  |
| 2026-06-30 | LGCL | 16:03:50 | 1.8999 | 1.7000 | 57 | +100% | -12% | trail@16:07:50 | $+31.49 | 0 |  |  |
| 2026-06-30 | LGCL | 16:24:10 | 2.1799 | 2.0500 | 34 | +130% | -10% | stop@16:29:50 | $-36.78 | 0 |  |  |
| 2026-06-30 | CIGL | 18:25:00 | 0.9942 | 0.9585 | 23 | +161% | -10% | stop@18:25:30 | $-25.11 | 0 |  | Y |
| 2026-07-02 | CLRO | 17:39:20 | 8.3700 | 8.0300 | 25 | +132% | -13% | stop@17:40:10 | $-27.43 | 0 |  |  |
| 2026-07-09 | JLHL | 19:05:50 | 10.5300 | 10.0600 | 27 | +182% | -6% | stop@19:08:30 | $-29.41 | 0 |  |  |
| 2026-07-13 | VEEE | 15:18:30 | 24.6000 | 23.2200 | 33 | +102% | -16% | stop@15:19:10 | $-35.06 | 0 |  | Y |
| 2026-07-13 | SOBR | 16:06:30 | 1.0898 | 0.9652 | 62 | +105% | -8% | trail@16:13:20 | $-5.08 | 0 |  |  |
| 2026-07-13 | VEEE | 17:07:00 | 30.0300 | 28.9600 | 23 | +146% | -9% | trail@17:16:20 | $+2.50 | 0 |  | Y |
| 2026-07-13 | SOBR | 17:55:00 | 1.4000 | 1.2200 | 69 | +163% | -3% | trail@18:02:00 | $-10.94 | 0 |  |  |
| 2026-07-14 | VEEE | 15:00:30 | 38.8400 | 37.0100 | 28 | +102% | -13% | trail@15:12:10 | $-5.40 | 0 |  | Y |
| 2026-07-14 | VEEE | 15:28:50 | 38.6600 | 35.0200 | 52 | +101% | -14% | trail@15:58:40 | $-32.91 | 0 |  | Y |
| 2026-07-15 | CPHI | 15:10:50 | 1.5400 | 1.3300 | 72 | +158% | -1% | trail@15:11:10 | $-65.00 | 0 |  | Y |
| 2026-07-20 | ZYBT | 17:09:00 | 2.8900 | 2.6700 | 43 | +128% | -14% | stop@17:20:30 | $-44.92 | 2 |  | Y |
| 2026-07-20 | ZYBT | 17:32:40 | 2.9500 | 2.6000 | 64 | +132% | -12% | trail@17:55:30 | $+9.27 | 4 |  | Y |
| 2026-07-21 | CPHI | 17:18:50 | 8.5950 | 7.6700 | 58 | +899% | -9% | trail@17:33:40 | $+70.80 | 1 |  | Y |
| 2026-07-21 | CPHI | 17:44:40 | 16.7200 | 15.3000 | 47 | +1844% | -2% | stop@17:46:00 | $-49.26 | 0 |  | Y |
| 2026-07-22 | ZCMD | 15:29:50 | 11.0800 | 10.1500 | 47 | +390% | -7% | stop@15:30:00 | $-48.77 | 0 |  | Y |
| 2026-07-22 | ADVB | 17:32:30 | 16.8215 | 14.5500 | 72 | +102% | -3% | trail@17:50:30 | $-9.52 | 0 |  |  |
| 2026-07-22 | PN | 19:04:20 | 8.0244 | 6.8800 | 76 | +101% | -2% | trail@19:29:30 | $+24.22 | 0 |  | Y |
| 2026-07-24 | STAK | 17:41:20 | 3.6000 | 3.3700 | 37 | +193% | -6% | stop@17:41:40 | $-38.90 | 0 |  | Y |
| 2026-07-24 | STAK | 18:01:30 | 4.1500 | 3.9000 | 35 | +237% | -7% | stop@18:02:50 | $-37.10 | 0 |  | Y |
| 2026-07-27 | FIEE | 16:04:40 | 9.3200 | 8.0200 | 74 | +224% | -12% | trail@16:08:20 | $-49.18 | 0 |  | Y |
| 2026-08-04 | AMIX | 16:19:20 | 11.1700 | 10.7400 | 24 | +107% | -10% | stop@16:21:20 | $-26.39 | 0 |  | Y |
| 2026-08-04 | AMIX | 17:10:40 | 20.0900 | 18.8000 | 37 | +272% | -8% | trail@17:14:40 | $-30.47 | 0 |  | Y |
| 2026-08-05 | JLHL | 15:07:30 | 14.1450 | 13.1000 | 42 | +102% | -8% | trail@15:14:40 | $+5.29 | 0 |  |  |
| 2026-08-05 | ZYBT | 15:34:20 | 3.2815 | 2.8200 | 75 | +160% | -15% | trail@15:36:40 | $+79.41 | 0 |  | Y |
| 2026-08-05 | YXT | 18:30:10 | 18.5801 | 17.2400 | 41 | +154% | -19% | trail@18:47:40 | $+68.13 | 1 |  | Y |
| 2026-08-05 | YXT | 18:58:00 | 20.8800 | 18.6300 | 58 | +185% | -17% | trail@19:21:40 | $+157.95 | 3 |  | Y |
| 2026-08-06 | WYHG | 15:05:20 | 16.6500 | 14.9800 | 55 | +100% | -16% | trail@15:21:50 | $+82.51 | 1 |  |  |
| 2026-08-06 | WYHG | 15:38:40 | 23.5300 | 22.2200 | 33 | +183% | -10% | stop@15:41:10 | $-34.85 | 0 |  |  |
| 2026-08-06 | LBGJ | 17:28:40 | 7.0100 | 6.3400 | 52 | +100% | -9% | stop@17:30:00 | $-54.50 | 0 |  | Y |
| 2026-08-07 | YJ | 15:05:30 | 5.8901 | 4.5500 | 118 | +327% | -8% | trail@15:11:50 | $+89.57 | 1 |  | Y |
| 2026-08-07 | YJ | 15:25:30 | 7.3194 | 6.0100 | 94 | +430% | -11% | trail@15:30:10 | $+26.26 | 0 |  | Y |
| 2026-08-07 | ATGL | 16:07:20 | 22.1000 | 18.9100 | 76 | +180% | -18% | resumeclose@16:12:30 | $-87.00 | 1 |  | Y |
| 2026-08-07 | WFF | 18:15:20 | 8.5000 | 6.7000 | 110 | +212% | -7% | trail@18:21:10 | $-23.94 | 1 |  | Y |
| 2026-08-10 | WYHG | 15:58:10 | 10.7000 | 9.1400 | 77 | +102% | -11% | trail@16:10:10 | $+16.05 | 1 |  |  |
| 2026-08-10 | RDGT | 16:55:40 | 1.5000 | 1.2200 | 97 | +111% | -7% | trail@17:00:10 | $-0.83 | 0 |  |  |
| 2026-08-11 | PLAG | 16:13:30 | 3.5100 | 3.1500 | 56 | +228% | -9% | resumeclose@16:24:00 | $-71.98 | 1 | Y | Y |
| 2026-08-11 | PLAG | 18:57:40 | 4.8201 | 4.5500 | 33 | +350% | -24% | trail@19:39:40 | $+142.79 | 4 |  | Y |
| 2026-08-12 | BQ | 15:14:50 | 1.9599 | 1.8513 | 32 | +118% | -7% | stop@15:15:00 | $-34.72 | 0 |  |  |
| 2026-08-13 | FGI | 16:44:20 | 18.7700 | 17.8000 | 31 | +121% | -6% | stop@16:46:50 | $-32.88 | 0 |  |  |
| 2026-08-13 | INHD | 19:19:00 | 13.3000 | 11.0400 | 89 | +104% | -10% | trail@19:25:20 | $-75.20 | 0 |  |  |

### base-rate honesty (best variant): entries on name-days that are NOT top-60 big rides
non-big: N=37 total $-476 mean $-13 wins 7; big-ride name-days: N=42 total $-270 mean $-6 wins 13
across ALL variants (non-big N / $  ||  big N / $):
- +100% all E3 exit: 49/$-676 || 49/$-750
- +100% all E3 hold: 49/$-712 || 49/$-814
- +100% all E4 exit: 50/$-659 || 49/$-491
- +100% all E4 hold: 50/$-690 || 49/$-393
- +100% all E4W exit: 49/$-1466 || 49/$-215
- +100% all E4W hold: 49/$-1543 || 47/$+168
- +100% all STRUCT exit: 48/$-915 || 49/$-1389
- +100% all STRUCT hold: 48/$-766 || 49/$-593
- +100% post11 E3 exit: 36/$-393 || 42/$-590
- +100% post11 E3 hold: 36/$-429 || 42/$-584
- +100% post11 E4 exit: 37/$-446 || 42/$-361
- +100% post11 E4 hold: 37/$-476 || 42/$-270
- +100% post11 E4W exit: 36/$-1171 || 41/$+740
- +100% post11 E4W hold: 36/$-1247 || 39/$+1166
- +100% post11 STRUCT exit: 35/$-639 || 42/$-620
- +100% post11 STRUCT hold: 35/$-628 || 42/$-203
- +60% all E3 exit: 105/$-1372 || 58/$-420
- +60% all E3 hold: 105/$-1400 || 58/$-503
- +60% all E4 exit: 105/$-1484 || 58/$+147
- +60% all E4 hold: 105/$-1514 || 58/$+207
- +60% all E4W exit: 100/$-2970 || 58/$-633
- +60% all E4W hold: 100/$-3031 || 56/$-351
- +60% all STRUCT exit: 101/$-1566 || 57/$-1304
- +60% all STRUCT hold: 101/$-1234 || 57/$-283
- +60% post11 E3 exit: 71/$-577 || 50/$-287
- +60% post11 E3 hold: 71/$-605 || 50/$-299
- +60% post11 E4 exit: 71/$-881 || 50/$+139
- +60% post11 E4 hold: 71/$-911 || 50/$+193
- +60% post11 E4W exit: 66/$-1923 || 49/$+205
- +60% post11 E4W hold: 66/$-1983 || 47/$+621
- +60% post11 STRUCT exit: 69/$-858 || 49/$-633
- +60% post11 STRUCT hold: 69/$-670 || 49/$+46

## 4. HOSTILE-HALT GAUNTLET — 10 name-days with the most halt gaps (best variant, plus exit-vs-hold twin)
| name-day | halts | lane trades | lane P&L (best) | worst trade | its exit | gap-through mechanics | twin (other halt mode) P&L | whole-date lane P&L |
|---|---|---|---|---|---|---|---|---|
| ZYBT 2026-07-20 | 37 | 2 | $-36 | $-45 | stop@17:20:30 | 17:14:50 HALT-RESUME (gap 300s) open 2.9800 close 3.0600 stop 2.6700 ; 17:20:20 HALT-RESUME (gap 300s) open 2.6800 close 2.7000 stop 2.6700 | $-36 | $-36 |
| CCTG 2026-06-09 | 36 | 0 | $0 | - | - | no lane entry | $+0 | $+25 |
| BYAH 2026-06-08 | 32 | 0 | $0 | - | - | no lane entry | $+0 | $+343 |
| BRUNW 2026-07-30 | 32 | 0 | $0 | - | - | no lane entry | $+0 | $+0 |
| CDTG 2026-06-04 | 31 | 1 | $-37 | $-37 | trail@15:37:50 | 15:37:40 HALT-RESUME (gap 300s) open 13.9700 close 14.0000 stop 11.6900 | $-37 | $-175 |
| YXT 2026-08-05 | 30 | 2 | $+226 | $+68 | trail@18:47:40 | 18:47:30 HALT-RESUME (gap 600s) open 23.8100 close 21.4300 stop 17.2400 | $+226 | $+311 |
| PLAG 2026-08-11 | 29 | 2 | $+71 | $-72 | resumeclose@16:24:00 | 16:24:00 HALT-RESUME (gap 600s) open 2.9000 close 3.0500 stop 3.1500 ; 16:24:00 HOLD-THROUGH exit: resumption CLOSE 3.0500 < stop 3.1500 fill 3.0347 | $+50 | $+71 |
| LZMH 2026-08-07 | 28 | 0 | $0 | - | - | no lane entry | $+0 | $+5 |
| MTEN 2026-06-08 | 27 | 0 | $0 | - | - | no lane entry | $+0 | $+343 |
| XCH 2026-06-23 | 27 | 0 | $0 | - | - | no lane entry | $+0 | $-47 |

## 5. HAND-TRACES (C3 specimens) — best variant; every trigger on the name-day (cap/cooldown noted)
### INHD 2026-06-08: RTH open 1.1100, session high 43.3700, close 32.0000, halt gaps 8 at ['13:44:00', '13:49:30', '14:00:00', '15:45:40', '17:05:50', '17:12:10', '19:49:00', '20:00:00']
in-regime bars: 927 (154 min), first 13:49:30 last 20:00:00 (UTC)
raw triggers: 57 at ['15:00:00', '15:46:20', '15:46:30', '15:46:40', '15:46:50', '15:49:50', '15:50:00', '15:52:30', '15:52:40', '15:52:50']; trades taken: 2
- TRADE 15:00:00 entry 3.9934 (+1% fill 4.0333) stop 3.4201 risk $76 day-gain +260% -13% from hi 4.6000 -> exit trail@15:17:20 pnl $+264.75
    15:17:20 TRAIL off10 close 6.2000 fill 6.1690 (hi 6.9400)
- TRADE 15:46:20 entry 7.9582 (+1% fill 8.0378) stop 7.2800 risk $47 day-gain +617% -10% from hi 8.8000 -> exit trail@15:49:10 pnl $+21.15
    15:49:10 TRAIL off10 close 8.4199 fill 8.3778 (hi 9.5000)
  C3 ride start 17:19:10 @ 10.515: gain +847% vwap-above True no-base True halt-60 True -> in-regime True
### PAVS 2026-06-09: RTH open 1.5500, session high 26.6900, close 1.0400, halt gaps 17 at ['13:37:20', '13:43:30', '13:58:50', '14:46:40', '15:32:00', '15:41:50', '15:49:00', '16:01:30', '16:12:10', '16:22:40', '16:33:40', '16:46:00']
in-regime bars: 588 (98 min), first 13:45:40 last 16:35:30 (UTC)
raw triggers: 13 at ['15:08:00', '15:15:10', '15:17:00', '15:17:40', '15:18:10', '15:18:20', '15:18:50', '15:19:00', '15:19:10', '15:32:20']; trades taken: 2
- TRADE 15:08:00 entry 7.6950 (+1% fill 7.7720) stop 6.6200 risk $74 day-gain +396% -10% from hi 8.5200 -> exit trail@15:11:30 pnl $+32.58
    15:11:30 TRAIL off10 close 8.3200 fill 8.2784 (hi 9.4900)
- TRADE 15:32:20 entry 11.7400 (+1% fill 11.8574) stop 10.8000 risk $45 day-gain +657% -12% from hi 13.3550 -> exit trail@15:32:50 pnl $-7.37
    15:32:50 TRAIL off10 close 11.7414 fill 11.6827 (hi 13.6200)
  C3 ride start 14:46:50 @ 4.865: gain +214% vwap-above False no-base True halt-60 True -> in-regime False
### ZYBT 2026-07-20: RTH open 1.2700, session high 8.4000, close 7.3000, halt gaps 37 at ['13:38:40', '13:44:00', '13:49:40', '13:56:00', '14:19:20', '14:26:20', '14:35:10', '15:15:20', '15:25:20', '15:31:00', '15:36:40', '15:42:10']
in-regime bars: 125 (21 min), first 16:58:00 last 20:00:00 (UTC)
raw triggers: 21 at ['17:09:00', '17:09:30', '17:14:50', '17:23:20', '17:23:50', '17:24:50', '17:25:00', '17:25:30', '17:26:00', '17:26:30']; trades taken: 2
- TRADE 17:09:00 entry 2.8900 (+1% fill 2.9189) stop 2.6700 risk $43 day-gain +128% -14% from hi 3.3700 -> exit stop@17:20:30 pnl $-44.92
    17:14:50 HALT-RESUME (gap 300s) open 2.9800 close 3.0600 stop 2.6700
    17:20:20 HALT-RESUME (gap 300s) open 2.6800 close 2.7000 stop 2.6700
    17:20:30 STOP 2.6700 fill 2.6566 (low 2.6700)
- TRADE 17:32:40 entry 2.9500 (+1% fill 2.9795) stop 2.6000 risk $64 day-gain +132% -12% from hi 3.3700 -> exit trail@17:55:30 pnl $+9.27
    17:38:00 HALT-RESUME (gap 300s) open 3.0400 close 2.9158 stop 2.6000
    17:44:00 HALT-RESUME (gap 300s) open 3.1500 close 3.1534 stop 2.6000
    17:49:40 HALT-RESUME (gap 300s) open 3.4000 close 3.4700 stop 2.6000
    17:55:20 HALT-RESUME (gap 300s) open 3.2000 close 3.0500 stop 2.6000
    17:55:30 TRAIL off10 close 3.0500 fill 3.0347 (hi 3.5000)
  C3 ride start 18:00:40 @ 2.9401: gain +132% vwap-above True no-base True halt-60 True -> in-regime True

## 6. VERDICT
best variant passes 2/4 graded convexity items on N=79 trades; total $-746; VERDICT: REFUTED (as specified)

## RAW OUTPUT — post-hoc cap sensitivity (`_capsens.py`)

    cap=2 E4 exit post11=True: N=79 tot=-808 halves -529/-278 HR=1 worst=-93 mdd=1046 prem=[-926, -404, -770] big 42/-361 nonbig 37/-446
    cap=2 E4 hold post11=True: N=79 tot=-746 halves -560/-187 HR=1 worst=-87 mdd=998 prem=[-945, -404, -750] big 42/-270 nonbig 37/-476
    cap=2 E4W exit post11=True: N=77 tot=-431 halves -303/-127 HR=3 worst=-108 mdd=1204 prem=[-1382, -716, -1042] big 41/+740 nonbig 36/-1171
    cap=2 E4W hold post11=True: N=75 tot=-82 halves -401/+319 HR=4 worst=-110 mdd=1272 prem=[-1431, -721, -979] big 39/+1166 nonbig 36/-1247
    cap=2 STRUCT exit post11=True: N=77 tot=-1259 halves -573/-686 HR=1 worst=-110 mdd=1259 prem=[-1156, -430, -899] big 42/-620 nonbig 35/-639
    cap=2 STRUCT hold post11=True: N=77 tot=-830 halves -573/-257 HR=1 worst=-110 mdd=1135 prem=[-1156, -430, -798] big 42/-203 nonbig 35/-628
    cap=4 E4 exit post11=True: N=95 tot=-481 halves -801/+320 HR=2 worst=-93 mdd=1155 prem=[-1113, -589, -843] big 49/+300 nonbig 46/-781
    cap=4 E4 hold post11=True: N=95 tot=-502 halves -831/+329 HR=2 worst=-87 mdd=1185 prem=[-1132, -589, -824] big 49/+309 nonbig 46/-811
    cap=4 E4W exit post11=True: N=86 tot=-705 halves -566/-140 HR=3 worst=-108 mdd=1403 prem=[-1644, -762, -1089] big 46/+635 nonbig 40/-1340
    cap=4 E4W hold post11=True: N=84 tot=-343 halves -652/+309 HR=4 worst=-110 mdd=1459 prem=[-1682, -766, -1026] big 44/+1062 nonbig 40/-1405
    cap=4 STRUCT exit post11=True: N=91 tot=-1543 halves -784/-759 HR=1 worst=-110 mdd=1543 prem=[-1396, -531, -1012] big 49/-665 nonbig 42/-878
    cap=4 STRUCT hold post11=True: N=90 tot=-975 halves -746/-228 HR=1 worst=-110 mdd=1213 prem=[-1359, -531, -911] big 49/-145 nonbig 41/-829
    cap=99 E4 exit post11=True: N=98 tot=+213 halves -107/+320 HR=3 worst=-93 mdd=984 prem=[-1166, -589, -843] big 51/+1044 nonbig 47/-832
    cap=99 E4 hold post11=True: N=98 tot=+192 halves -137/+329 HR=3 worst=-87 mdd=1014 prem=[-1186, -589, -824] big 51/+1054 nonbig 47/-862
    cap=99 E4W exit post11=True: N=87 tot=+42 halves +182/-140 HR=4 worst=-108 mdd=1403 prem=[-1644, -762, -1089] big 47/+1382 nonbig 40/-1340
    cap=99 E4W hold post11=True: N=85 tot=+404 halves +95/+309 HR=5 worst=-110 mdd=1459 prem=[-1682, -766, -1026] big 45/+1810 nonbig 40/-1405
    cap=99 STRUCT exit post11=True: N=93 tot=-1107 halves -348/-759 HR=2 worst=-110 mdd=1410 prem=[-1465, -531, -1012] big 50/-161 nonbig 43/-947
    cap=99 STRUCT hold post11=True: N=92 tot=-539 halves -311/-228 HR=2 worst=-110 mdd=1106 prem=[-1428, -531, -911] big 50/+359 nonbig 42/-898
    cap=99 E4W hold post11=True: N=85 tot=+404 halves +95/+309 HR=5 worst=-110 mdd=1459 prem=[-1682, -766, -1026] big 45/+1810 nonbig 40/-1405
    INHD 15:00:00 3.993 trail@15:52:10 414
    INHD 15:52:30 7.78 stop@15:53:30 -34
    INHD 16:22:30 7.38 stop@16:35:40 -49
    INHD 17:12:50 12.155 trail@17:18:40 -61
    INHD 17:33:00 15.559 eod1545 747
    PAVS 15:08:00 7.695 trail@15:49:50 765
    ZYBT 17:09:00 2.89 stop@17:20:30 -45
    ZYBT 17:32:40 2.95 eod1545 719
