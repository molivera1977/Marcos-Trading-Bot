# RESULTS LEDGER — canonical archive of every kill-test/backtest verdict
_Owner: The Statistician (16th lens, born 7/22). One row per test: verdict, n, dates, caveats,
evidence file. A number not in this ledger is a rumor. Append-only; never edit a past row —
supersede it with a new one._

| date | test | verdict | headline numbers | n / span | caveats | evidence |
|---|---|---|---|---|---|---|
| 7/21 | Rocket chase-entry (Fable +32% pkg) | REFUTED (look-ahead) | true profile +10-13% mean, MEDIAN NEGATIVE, 1/5 winners | 5-6 tapes, 2 days | order-independence artifact in scaleout_from | memory: project_rocket_catcher_package |
| 7/21 | Kev-spec rocket (arm→20EMA→curl) | SHIPPED (DRY_RUN) | shipped-replay 7/21: 5 fires, mean +50%, median +32%, win 60% | 1 day, ~100 names | entry-at-close sim; halt fills unmodeled | shipped_replay in package memory |
| 7/21 | Vel5 floor (<0 blocks legacy) | SHIPPED | vel<0: −$172.8 @30% win vs vel≥0 +$60.4 | n=56 real trades 7/13-7/21 | 0.0-vel artifacts on sparse bars | vel5_history.py |
| 7/21 | Read-staleness HARD skip | REFUTED (inversion) | would block ZYBT +$164.79/BIYA +$34.40 to save SKYQ −$41 → net ≈ −$160 | 2 enforce days | past-map names ARE movers | read_staleness_killtest_results.txt |
| 7/22 | ORB trailing-20EMA anchor (#73) | REFUTED | static +0.51R/58% (n=99) vs trailing +0.38R/56% (n=118); movers ≥40%: +1.09R vs +0.72R | 156 name-days, 2 days | outliers BGDE +16.25R/HUHU +8R in BOTH arms; ex-outliers +0.27 vs +0.18 (verdict holds) | orb_anchor_killtest_fullrows.txt |
| 7/22 | Wick-aware dip fix (#73) | SHIPPED 56d585d | live bug: DFNS/GMM wicked levels, dipped=False all day; fix validated by static arm above | hand-traced vs raw prints | live acceptance pending 7/22 tape | orb_anchor_killtest.py + rig T18 |
| 7/22 | Full-panel as-deployed replay 7/20-21 | RECONCILED | sim +455.37/−115.17 vs live +134.62/−40.45; VMAR anchor-match −23.13 vs −23.25 | 2 days, all machines | ZYBT +$86 halt-gap optimism; EOD-level time-travel blocked CPHI rocket; reclaim/zone-flip excluded (10s data) | full_panel_replay_results.txt |
| 7/22 | Rocket cap-burn fix | REFUTED (no-op) | zero P&L delta both level scenarios; all capped rockets were gate-doomed (no level) | n=5 curls, 2 days | retest if rocket_capped ever hits a name WITH a level | cap_killtest_results.txt |
| 7/22 | Rank-reserved capital | REFUTED (noise) | $1000/top-3: −$62 (blocked AGPU +$85); $500/top-3: +$45; 7/21 unaffected in all configs | 2 days | sign flips on composition; rank-at-entry LAGS (AGPU mid-list at trigger) | cap_killtest_results.txt (rr_* runs) |
| 7/22 | RS-at-open ranker pass 1 | MIXED (hypothesis) | 7/21: top-3 potential +624% vs rest +14% (CPHI #3 at 9:40!); 7/20: top-3 +6.9% vs rest +12.7% (FAIL) | 2 mornings | one-name dominated (CPHI); GMM-class invisible at open; ZYBT unscoreable (halt bars) = inverted exclusion | rs_at_open_pass1_results.txt |
| 7/22 | Dead-cat entries hurt us (Marcos claim) | REFUTED (3rd inversion) | >25% off pre-entry high: +$204.86, 78% win (BEST bucket); mid-fade 10-25%: −$147.45 (WORST) | 165/182 trades matched | entry-minute heuristic; bucket conflates dead-cats w/ runner pullbacks; map-relative A-1 still owed | deadcat_check.txt |

| 7/22 | VWAP anchor: PM vs RTH in disagreement band | DOCTRINE CONFIRMED | IN-BAND (PM front/RTH back): +1.16% mean fwd30, 60.9% win — BEST cohort; inv-band weakest (53.0%) — PM anchor right both directions | 9,393 samples / 195 name-days / 7/14-17 | in-band n=133; up-tape baseline (read ranking not absolutes); 295 pairs lacked PM tape; harness caught 2 own bugs pre-result | vwap_anchor_killtest_results.txt |
| 7/22 | Machine-scoped day-gain floor | SHIPPED ed73f8d | sweep +$122-165 all T in [10,40]; ex-ZYBT intact; same-day: all 3 losers floor-blockable | 124 matched trades | era-mixed; T=30 homegrown | daygain_floor_killtest.txt |

| 7/22 | Alpaca preview grade (PARTIAL window) | PIPELINE PROVEN — no verdict | alp median 11.1%/mean 14.0% vs wb 15.5%/40.8% (n=35 matched) — BOTH denominators are full-day /api/daily volume; SIP only ran 15:28→AH, wb had its #68-degraded day | 35 names, ~32min RTH + AH | numbers are window artifacts, NOT vendor quality; formal ≥98% gate = 7/23 full-day 4:00-20:00 capture | vendor_test_grade.py run 7/22 19:10 |
| 7/22 | Evening build (5 change-sets + hardening) | ALL SHIPPED | #68 de31e74 reserve-first reseed; #81 2efeb7d amnesia+rescan budget; whitelist class killer 75fe99b; #84 5beab99 re-read isolation; #86 8255dd5 stream ghost-session self-heal; #87 76b913d ALP-primary VWAP chain; alp 405-trim/fuse 220dfdf | rigs: defects 61/61, rocket 31/31, recorder 11/11, reader 6/6, alp 28/28 | each has a named Thu acceptance check; bot verified sleeping-till-8:45 post-rebuild | git log 7/22 evening |

## Standing stat-hygiene flags (check before quoting any row)
- n<10 → directional only, never a ship verdict alone.
- Mean vs median divergence → report both; find the outlier rows.
- Bucket definitions → state the boundary and what it conflates.
- Scratchpad is EPHEMERAL — results die with the session unless copied here.
