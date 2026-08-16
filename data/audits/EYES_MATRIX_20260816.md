# ENTRY × EYES and EXIT × EYES MATRIX — 2026-08-16 (Sunday, run 11:11-12:00 ET)

Mandates (Marcos): "each entry PROPERLY utilizes the EYES" and "the exits need to use the EYES as well."
Scope: analysis + document only. No bot code touched. Audit of record for the Sunday matrix.
Sources: `marcos_trading_bot.py` (12,538 lines, read this session by two separate-context code auditors + spot-checks by me), `EYES_AUDIT_20260815.md`, `mechanism_audits_20260814.md`, `context_joins_20260815.md`, `sunday_afternoon_studies_20260816.md`, `edge_stresstest_F/G_20260815.md`.
Part 3 join: `data/killtests/exit_eyes_join_20260816.py` (+ `_run.txt`, `_out.json`), engine chain CJ -> G -> F -> C -> B -> engine of record; baseline reconciles to context_joins/round G to the cent.

Legend: **G** = GATE (blocks entry / modifies size, stop, exit) with line · **S** = STAMP-ONLY (computed and written to a row/record, no behavior change) · **N** = NOT-CONSULTED · **NA** = not applicable · **G(U)** = universal `_trade_worker` gauntlet (:11351+) applied to every lane that converts.
Env caveat: cells reflect CODE DEFAULTS read today. Railway env may differ (known from production rows: `CHART_GATE_ENFORCE` shows `enforced:true` ×52 on 8/14 though the code default is "0"; `TAPE_PREBREAK_GATE=0` in Railway since 8/4 though the code default is "1"). Claims about the deployed value of any env = read that service's Railway env that turn [UNVERIFIED here].

---
## PART 1A — ENTRY × EYES (from code)

Architecture (verified): Stage A = watch loop `wait_for_flat_top_entry` (:7100-8438): detectors fire, lane conversions/caps, then an in-loop tail gauntlet on the `breakouts` list (:8228-8390: vel5 :8314-8327, day-gain :8329-8346, crown stamp :8349-8353, back-side :8355-8368, extension :8375-8380). Stage B = `_trade_worker` (:11351+): chart gate :11388-11403 -> min-stop :11453-11466 -> runway+wall :11469-11497 -> break-side/mapless :11507-11577 -> retest band :11633-11646 -> ceiling/stand-down :11650-11683 -> tape pre-break :11685-11697 -> stop-coherence -> sizing incl. VWAP-side halving :11738-11745 -> spread :11800-11808 -> topping-tail :11846-11848 -> ambient :11858-11875 -> retest-wait :11884-11890. Every breakout fired before `ENTRY_OPEN_ET` (:12391 default "09:30") goes to `premarket_shadow_entry` (:11331-11348) — PRE conversions depend on the Railway value.

Lane state by code default: flat_top BREAK-attack LIVE (`FLATTOP_BREAK_ATTACK` :5621 "1"; plain flat_top observe-only :8283-8298) · grinder LIVE (`GRINDER_CONVERT` :5622 "1", cap 3) · ma_pullback LIVE (`PULLBACK_FIRST` :370) · ignition LIVE (`IGNITION_CONVERT_MULT` 4.5 :425; `IGNITION_CELL_GATE` "0" = stamp) · dip_rip LIVE (`DIP_RIP` :625) · orb LIVE (:8101-8162, no kill switch) · seam H2 LIVE for crowns (`SEAM_CONVERT` :6876 "1") · halt-arm SHADOW/arm-only by code (`HALT_LANE_CONVERT` :6867 "0" — memory says Monday config = convert; Railway value [UNVERIFIED]) · hidden v1 OBSERVE (`HIDDEN_CONVERT` :5594 "0") · v2 calibrated SHADOW-only (`V2_SHADOW` :5727; no conversion path exists) · vwap_reclaim observe-only (`VWAPRECLAIM_CONVERT` :5606 "0") · zone_flip SHADOW (`ZONEFLIP_CONVERT` :5489 "0") · rocket_catcher OFF · band-pass reclaim / pre-vwap = UNBUILT (no code; rows below are the spec-only placeholder).

| # | Eye | flat_top BA | grinder | ma_pullback | ignition | dip_rip | halt-arm | hidden v1 | v2 cal | vwap_reclaim | zone_flip | orb | seam H2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | VWAP side | G :8064-8067 + G(U) size-halve :11738-11745 | G detector :5846 (c>vwap) + G(U) size | G :8164 + G(U) size | N detector / G(U) size | N / G(U) size | N / G(U) size | G detector :5676,:5693 | G detector (near-VWAP anchor :5783-5785) | G detector (reclaim by construction :5415) | N | G :8103 + G(U) size | N / G(U) size |
| 2 | VWAP distance | S (eyes :9142) | S | S | S | S | S | G ext band :7735-7737 (3-10% rejected unless crown) | S | S | S | S | S |
| 3 | VWAP slope | S :9155 | S | S | S | S | S | S | S | S | S | S | S |
| 4 | SIDE stamp | S :9160, :12003 | S | S | S | S | S | S | S | S | S | S | S |
| 5 | break-side gate | NA (not in `BREAKSIDE_LANES` :6830) | NA | G(U) :11507-11534 | G(U) | NA | NA | G(U) | NA | G(U) | NA | NA | NA |
| 6 | back-side gate | G :8355-8368 | G | G | G | S (exempt :6755) | G | G | N | G | G | G | G |
| 7 | chart map / zone / mapless | S (`CHART_GATE_ENFORCE` code default "0"; Railway shows enforced — see caveat) | S | S + G(U) mapless :11541-11577 | S (bypass :3278 `IGNITION_CHART_BYPASS`) + G(U) mapless | S | S | S bypass + G(U) mapless | N | S bypass + G(U) mapless | S bypass | S | S |
| 8 | runway + wall | G(U) :11469-11497 (`MIN_RUNWAY_RR` 1.0; wall `RUNWAY_WALL` "1" :9016) | G(U) | G(U) | G(U) | G(U) | G(U) | G(U) | N | G(U) | G(U) | G(U) | G(U) |
| 9 | freshness / auto-map | G-input (`_effective_map` :8936 substitutes the auto-map into eyes 5/7/8/16; `freshness_breach` row :8957) | G-input | G-input | G-input | G-input | G-input | G-input | N | G-input | G-input | G-input | G-input |
| 10 | crown / leader | S `entry_crown` :8349-8353 + G size (crown exempt from VWAP halving :11739) | same | same | G `LEADER_IGNITION_CAP` :7788-7789 + same | same + curl slots :5233 | G lane runs only if `_is_leader` :7647 | G cap bypass :7731, ext bypass :7737 | N | G curl slots | G curl slots | same | G leader-only :7625 |
| 11 | lens | S (ordering only, `_lens_pass` :5372) | S | S | S | S | S | S | S | S | S | S | S |
| 12 | day-gain floor | G :8329-8346 (`DAYGAIN_LEGACY` :5973; kev-sheet exempt) | NA | G | G | NA | NA | NA | N | NA | NA | G | NA |
| 13 | ambient $ floor | G(U) :11858-11875 (`AMBIENT_DVOL_MULT` 15 :3979) | G(U) via `check_momentum` :4067-4076 | G(U) | G(U) (:11858 even with liquidity waived :11851) | G(U) | G(U) | G(U) | N | G(U) | G(U) | G(U) | G(U) |
| 14 | min-stop | S (exempt `MIN_STOP_EXEMPT` :7035-7036) | G(U) :11453-11466 (4%) | G(U) | G(U) | G(U) | G(U) | S exempt | N | G(U) | S exempt | G(U) | G(U) |
| 15 | extension guard (90-EMA 25%) | S exempt :8375-8377 | G :8378 but fail-open (no ema90 in extra -> `_e90=0`) | S exempt | G :8378 + own `IGNITION_MAX_EXT` 0.15 :7793-7797 | G :8378 | G fail-open | S exempt | N | S exempt | S exempt | S exempt | G fail-open |
| 16 | ceiling / sticky stand-down | G(U) :11650-11683 (`CHART_CEILING_LANES` :6849) | NA | G(U) | NA | G(U) | NA | NA | N | NA | NA | G(U) | NA |
| 17 | halt distance / LULD | S :9233 | S | S | S | S | G arm `_hl_prox>=HALT_ARM_PROX` :7677 | S | S | S | S | S | S |
| 18 | spread | G(U) :11800-11808 | G(U) | G(U) | G(U) | G(U) | G(U) | G(U) | N | G(U) | G(U) | G(U) | G(U) |
| 19 | retest band | G(U) :11633-11646 (zone=="retest") | G(U) | G(U) | G(U) | G(U) | G(U) | G(U) | N | G(U) | G(U) | G(U) | G(U) |
| 20 | topping-tail | G(U) :11846-11848 | G(U) via check_momentum | G(U) | G(U) | G(U) | G(U) | G(U) | N | G(U) | G(U) | G(U) | G(U) |
| 21 | tape pre-break | NA (`TAPE_PREBREAK_LANES` :6840) | NA | NA | NA | NA | NA | G(U) :11685-11697 by code default; OFF in Railway per 8/4 verdict | N | G(U)/OFF | G(U)/OFF | NA | NA |
| 22 | vel5 | G :8314-8327 | S :8236-8244 | G | S | S | S | S | N | S | S | G | S |
| 23 | rel-vol-TOD | N (`EYES_TODO` :9049) | N | N | N | N | N | N | N | N | N | N | N |
| 24 | SPY regime | N (EYES_TODO) | N | N | N | N | N | N | N | N | N | N | N |
| 25 | catalyst / news | N (EYES_TODO; `get_news_catalyst` :1799 exists, no entry consumer traced [UNVERIFIED]) | N | N | N | N | N | N | N | N | N | N | N |

Unbuilt spec rows: **band-pass reclaim (2-5 min held)** and **pre-VWAP** lane — no code, every cell N/A until built; the harvester grades them (T1 band-pass +$2,990/412 unwindowed; 09:30-10:30 +$2,248/182).

### Per-lane counts (25 eyes)
| Lane | GATE | STAMP-ONLY | NOT-CONSULTED | N/A |
|---|---|---|---|---|
| flat_top BREAK-attack (live) | 12 | 8 | 3 | 2 |
| grinder (live) | 11 | 7 | 3 | 4 |
| ma_pullback (live) | 15 | 5 | 3 | 2 |
| ignition (live) | 14 | 6 | 3 | 2 |
| dip_rip (live) | 11 | 8 | 3 | 3 |
| halt-arm (arm-only by code) | 12 | 6 | 3 | 4 |
| hidden v1 (observe) | 13 | 7 | 3 | 2 |
| v2 calibrated (shadow) | 1 | 5 | 18 | 1 |
| vwap_reclaim (observe) | 13 | 7 | 3 | 2 |
| zone_flip (shadow) | 9 | 9 | 4 | 3 |
| orb (live) | 13 | 7 | 3 | 2 |
| seam H2 (live, crowns) | 11 | 7 | 3 | 4 |
The 3 NOT-CONSULTED cells common to every live lane are the three TODO eyes (rel-vol-TOD, SPY, catalyst). VWAP slope, SIDE, lens, halt-distance and VWAP-distance are stamp-only on every live lane.

### Code findings surfaced by the matrix (not proposals — defects/notes for the owning officers)
- E1 (Halt lane): `half_size` set :7706 is never consumed anywhere in the file — the "half size" privilege is a dead flag [Blast Radius / Webull Desk]. Halt-arm also fail-opens the extension guard (no ema90 in extra) and is NOT min-stop exempt (4% floor vs a 2-min-low stop).
- E2 (grinder / halt / seam): extension guard `EXTENSION_MAX_PCT` 0.25 is on but these lanes carry no `ema90` -> `_e90=0` -> fail-open at :8380. Effectively ungated.
- E3 (break-side branch): flat_top, grinder, dip_rip, halt_ladder, crown_seam, orb, zone_flip are outside `BREAKSIDE_LANES` and so get neither `breakside_reject` nor `mapless_reject` rows.
- E4: `_trade_worker` never runs before `ENTRY_OPEN_ET`; in-loop gates (backside, daygain, vel5, extension) DO run on PRE fires.
- E5: EYES_AUDIT dead-suspects (stand-down rows zero, ambient rows zero, crown_pre_exempt zero) are cells marked G here BY CODE; production has not yet proven them binding. Code reading counts for nothing until a row lands.

---
## PART 1B — EXIT × EYES (from code)

Verified this session: `_e3_eval` (:9281-9292) is PURE price — args `(current_stop, runhi, bar_close, bar_high)`; stop-first, run-high update, `bar_close < 0.90*runhi` -> trail. The E3 block in `monitor_trade` (:9973-10000) reads only `_curl_feed(ticker, n=12)` 10s bars (c/h), calls `_e3_eval`, `_safety_close`. E3 bank tier = `[(entry_price*1.10, 0.50)]` (:9401). E3 lanes explicitly skip instant-exit / prev-bar-low / topping-tail / rung ratchet / health fold via `not _e3_mode` guards (:9835, :9850, :9870, :9897, :9928). **E3 consults ZERO eyes at exit — confirmed.**

| Mechanism (line) | Live? | VWAP | SIDE | brk-side | back-side | map levels | runway/wall | freshness | crown | lens | day-gain | ambient | min-stop | ext | ceiling | halt/LULD | spread | relvol | SPY | catalyst |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E3 bank 1/2 @+10% (:9401; fill :9673-9760) | LIVE `E3_EXITS`=1 :5624 | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N |
| E3 trail 10%-off-high (:9973-10000, `_e3_eval` :9281) | LIVE | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N |
| Kev tier ladder (`SCALE_TIERS` R-grid :9424; hidden %-ladder :9412) | LIVE non-E3 lanes | N | N | N | N | G only in dead default branch :9427 (`next_supply`, unreachable while SCALE_TIERS set :458/461) | N | N | N | N | N | N | N | N | N | N | N | N | N | N |
| Rung ratchet (:9897-9926) | LIVE `RUNG_RATCHET`=1 :6777, non-E3 | N | N | N | N | **G** :9899-9909 targets/next_supply/break from raw `_fetch_kev_levels()`; exit :9917 | N | **N** (raw Kev store, not `_effective_map`) | N | N | N | N | N | N | N | N | N | N | N | N |
| Health fold (:9928-9965) | LIVE `RUNNER_HEALTH_EXIT`=True :349, non-E3 | **G** :9959 3-min close < EMA9 AND session VWAP | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N |
| Breakeven move (:9740 `BE_FLOOR_AFTER_SCALE`; hidden scale-bar-low :9746-9750) | LIVE non-E3 | N ×19 |
| 3-min close stop (:9811-9829) | LIVE | N ×19 (stop set at entry, never re-read against map) |
| Intrabar stop (:10044-10058) | LIVE `INTRABAR_STOP`=1 :333 | N ×19 |
| Resting broker stop (place :8648, sync :9600-9617, resize :9751) | LIVE `RESTING_STOP`=1 :334 (DRY_RUN fake ids; $5 place+cancel still owed) | N ×19 |
| Crater floor (:10060-10068) `CRATER_FLOOR_R` 2.0 | LIVE | N ×19 |
| Blind-stop failsafe (:10011-10031) | LIVE | N ×19 (feed-liveness only) |
| Resting-limit sell ladder `_place_sell_ladder` (:8690) | OFF `RESTING_SELLS`=0 :511 | N ×19 (rung prices = kev_tiers R-multiples) |
| Legacy trailing stop / prev-bar-low :9850 / instant-exit :9835 | DEAD by default (`not RUNNER_HEALTH_EXIT`) | N ×19 |
| Topping-tail exit (:9870-9878) | DEAD by default | N ×19 |
| Software %-stop :10073 / failed-breakout :9546 / early VWAP fade :9560 | DEAD (`not EXITS_ON_3MIN`, True :313) | early-fade would be G on VWAP; otherwise N |
| PRE 9:25 flatten (:9464-9474, `PRE_FLAT_HHMM` :12399) | LIVE | NA (clock) |
| RTH flatten 15:45 (:9477-9487, `TRADE_WINDOW_END_HOUR/MIN` :516-517) | LIVE | NA (clock) |
| Grinder 15:59 flatten | **NOT IN CODE** — see X1 | — |
| Off-tape exit guard `_verify_exit_px` (:1213; applied :10084-10099) | LIVE | NA — booking guard, not a decision |
| Halt handling in monitor | none — only STALE FEED exit :9522 + bar-price fallback :9494 (feed-liveness) | NA |
| `_eyes_snapshot(...,"exit")` (:9098; called :12226, :10230) | build #0 | S ×~10 (vwap/side/map/crown/lens/day_gain/ext/halt_dist/spread/ambient) |

Precedence per loop iteration (:9448-10082): watchdog -> PRE flatten -> 15:45 flatten -> price/stale-feed -> resting-stop sync -> tier fill -> bar section (~60s): 3-min close stop -> (dead) -> rung ratchet -> health fold -> E3 block (E3 lanes, 10s) -> blind-stop -> intrabar stop -> crater floor. First-in-order wins (`remaining_shares>0` guards).

Per-mechanism counts: every exit mechanism = 0 GATE eyes except **health fold (1: VWAP, non-E3 lanes only)** and **rung ratchet (1: map levels, non-E3 lanes only)**; **E3 = 0 GATE / 0 STAMP inside the loop**; the only exit-side stamps are the custody heartbeat SIDE (:9626) and the build #0 exit snapshot.

Exit-side findings:
- X1 (Wind Tunnel parity, IMPORTANT): the sim (F/G/CJ/Sunday) flattens grinder at 15:59 ET and holds break-attack to the last RTH bar; the LIVE bot flattens ALL positions at 15:45 (:516-517). Every E3 dollar figure since round F assumes a later flatten than production runs. Needs a parity re-run (E3 with 15:45 flatten) before the wall grades live vs sim — one line, same chain.
- X2: rung ratchet reads raw `_fetch_kev_levels()`, not `_effective_map` — the freshness/auto-map eye never reaches the exit side, even on non-E3 lanes.
- X3: on E3 lanes the crown changes nothing at exit (no crown hold, no wider trail); the "let it breathe" is uniform.

---
## PART 2 — JOIN-BACKED VERDICTS ON NOT-CONSULTED / STAMP-ONLY CELLS

Already-run joins (numbers from the cited files):
| Cell | Join | Number | Verdict |
|---|---|---|---|
| grinder × VWAP slope/dist | context_joins J1 | rising +$27.49/tr (175) vs flat +$9.92 (63); flat cell still +$625; side unmeasurable (filter bakes it in) | **LEAVE-ALONE** (stamp) |
| flat_top BA × VWAP side | context_joins J1 | above +$8,782/304 vs below +$438/80 (below net GREEN, below 0-1% +$439); worst cell below 3%+ -$70/44 | **LEAVE-ALONE** (stamp) |
| flat_top BA × VWAP slope | context_joins J1 | rising +$34.66/tr vs falling +$14.36/tr, both green | **LEAVE-ALONE** |
| v2 cal × VWAP side+slope | context_joins J1 | above+falling **-$1,042/234**; below 0-1% +$935/134 | **WIRE into the v2 REBUILD spec only** (lane unshipped, +$2.08/tr overall) — not a live proposal |
| all lanes × runway | context_joins J2 | 51 refusals replay -$195.70; <0.3R -$272 (30), 0.7-1R +$74.57 (7) | **LEAVE-ALONE** (gate keeps its job; 0.7-1R band = re-grade item, N=7) |
| ignition × VWAP side | mechanism_audits D3 + prior ignition census | above-VWAP graded WORSE on ignition; census cell dg<40 & <10:30 era +$123..+$164 vs cut -$298..-$310 | **census-cell gate stays STAMP** (`IGNITION_CELL_GATE`=0) — Marcos-priced item already open, no new evidence |
| flat_top BA × volume clause | Sunday T6c | >=1.5x +$24.66/tr (487) vs <1.5x +$34.17/tr (147) | **REFUTED** — do not add |
| flat_top BA × failed-break EXIT | Sunday T6a | rule -$4,717 vs default +$1,787 on 219 fired; lane +$17,031 -> +$10,527 | **REFUTED** |
| grinder / BA × no-progress-15 EXIT | Sunday T6b | grinder +$10,676 -> +$3,927; BA +$17,031 -> +$2,683 | **REFUTED** |
| midday BA × VWAP-survivor precondition | Sunday T3 | -$5.52/tr -> +$1.66/tr (N=99, +$164, median day $0) | **REFUTED as a lane / breakeven** — no wire |
| afternoon reclaim × crown (leaders-only) | Sunday T4 | leaders -$265.77/24 vs non-leaders +$484.81/71 | **REFUTED / inverts** |
| any lane × power hour | Sunday T1 | 15:00-16:00 worst bucket every lane; 86% of runner-days no new high after 15:00 | **CONFIRMED-DIRECTIONALLY**; nothing to wire (15:45 flatten already earlier) |
| halt retest lane × halt distance | Sunday T2 | -$1,078.81/36, 19% win | **REFUTED** (10s mechanical retest only; halt-arm doctrine untouched) |
| E3 × VWAP-loss exit | **Part 3 below** | grinder -$76 (V1) / -$1,272 (V2); BA -$1,040 (V1) / -$9,579 (V2) | **LEAVE-ALONE (V1) / REFUTED (V2)** |
| E3 × halt-distance tighten | **Part 3 below** | grinder +$107 (11 fires); BA -$313 (34 fires) | **LEAVE-ALONE** |

Join queue — NOT-CONSULTED / STAMP-ONLY cells with NO join yet (one line each; nothing wired without one):
1. flat_top BA × SIDE stamp (front/back/reclaim/basing): grade F/G BA trades by the Side Marshal's fused side at fire — is the back-side band's 15-30% edge right for the attack lane? (Side Marshal; rows from 8/8 stamps + sim proxy).
2. grinder × SIDE stamp: same join on the 239 grinder fires (grinder is above-VWAP by construction; side may still split).
3. dip_rip × back-side (exempt today): replay dip_rip era fires with the band applied — does the exemption pay? (Strength Ombudsman hearing, dollars).
4. grinder / halt / seam × extension guard (fail-open today): count how many era fires were >25% over EMA90 and their P&L — is the fail-open costing or saving?
5. halt-arm × min-stop 4% (not exempt): count arm converts refused by min-stop on a 2-min-low stop; replay them.
6. all lanes × lens (ordering only): does the lens_focus set at fire time predict per-trade $ (focused vs unfocused fires)? Rows exist since 7/27.
7. all lanes × halt distance at ENTRY: replay F/G champion fires bucketed by proximity to the upper LULD band (0-3% / 3-10% / >10%) — the entry twin of Part 3 V3.
8. all lanes × spread state: bucket era trades by spread% at fill (rows carry it) — is the spread gate threshold at the right place?
9. flat_top BA × day-gain (gated today, kev exempt): re-grade with the 8/14 split-adjust corruption removed (DFNS 5152% class) before trusting the floor.
10. rel-vol-TOD (TODO eye): needs the time-of-day volume baseline table first (Quartermaster owns bars); then a join per lane. No wire.
11. SPY regime (TODO): needs SPY 10s/1m tape in the cache; then bucket champion trades by SPY 5-min slope. No wire.
12. catalyst (TODO): needs Marcos's word to enter the build queue (EYES_AUDIT never-built #6); no data source ferried yet.
13. Exit-side × map levels for E3 lanes: does adding a rung-ratchet floor (E3 + ratchet on cleared majors) beat plain E3? Reuse chain; needs level anchors ferried into the universe cache (only sim-derived flat-top levels exist today).
14. Exit-side × crown: E3 with a wider trail (15%) on crowned names vs 10% — needs crown flags joined to the universe cache (crown rows exist from 8/5).
15. Exit-side × 15:45 flatten parity (X1): E3 baseline re-run with a 15:45 flatten on all lanes — a correction to every number above, run before Monday's wall.

---
## PART 3 — EXIT × EYES JOIN (run 8/16 11:3x ET; `exit_eyes_join_20260816.py`)

Universe: 421 files, 36 dates 2026-06-25..2026-08-14; champion lanes grinder-1030 (C.det_grinder_1030) + flat_top BREAK-attack in-window (G.det_flat_top_break, 09:30-10:30 ET); E3 baseline (bank 1/2 +10%, trail 10%-off-high closes-through, stop-first, -1% chase, -0.5% market slip), H2 halt + H3 dedup, no capacity (N constant). **Baseline reconciles to context_joins/round G to the cent: grinder N=239 +$5,483.15; BA N=384 +$9,220.01.**
VWAP = RTH-anchored typical-price cumulative (sibling of the premarket-anchored live ~vwap — disclosed). LULD proxy = 5-min mean close × (1+band), band 10% >=$3 / 20% $0.75-3 / 75% <$0.75, doubled 09:30-09:45 and 15:45-16:00.

Variants: **V1** VWAP-loss exit AFTER bank (banked, then a completed 10s close < VWAP -> exit rest) · **V2** VWAP-loss ANYTIME after entry (close < VWAP -> exit all remaining) · **V3** halt-distance tighten (within 3% of upper band -> post-bank trail 5% instead of 10%) · **V3b** same + pre-bank 5% tight.

| Lane | Variant | N | win | total $ | delta vs E3 | mean/tr | day mean | day median | green | worst | rule fired | rule $ on fired vs E3 $ on same |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| grinder | **E3 baseline** | 239 | 56% | +5,483.15 | — | +22.94 | +152.31 | +108.09 | 83% | -73.21 | — | — |
| grinder | V1 VWAP-loss after bank | 239 | 56% | +5,406.81 | **-76.34** | +22.62 | +150.19 | +117.39 | 83% | -73.21 | 29 | +1,541.50 vs +1,617.83 |
| grinder | V2 VWAP-loss anytime | 239 | 51% | +4,211.26 | **-1,271.89** | +17.62 | +116.98 | +88.65 | 75% | -73.21 | 52 | +1,043.24 vs +2,315.13 |
| grinder | V3 halt tighten (post-bank) | 239 | 56% | +5,590.38 | **+107.23** | +23.39 | +155.29 | +120.06 | 83% | -73.21 | 11 | +1,211.19 vs +1,103.96 |
| grinder | V3b (+pre-bank) | 239 | 56% | +5,590.38 | +107.23 | +23.39 | +155.29 | +120.06 | 83% | -73.21 | 11 | identical to V3 (pre-bank never fired) |
| break-attack | **E3 baseline** | 384 | 61% | +9,220.01 | — | +24.01 | +256.11 | +254.49 | 81% | -119.26 | — | — |
| break-attack | V1 VWAP-loss after bank | 384 | 61% | +8,180.07 | **-1,039.94** | +21.30 | +227.22 | +227.39 | 83% | -109.93 | 108 | +4,522.34 vs +5,562.28 |
| break-attack | V2 VWAP-loss anytime | 384 | 27% | -359.03 | **-9,579.04** | -0.93 | -9.97 | -16.53 | 47% | -193.59 | 320 | -2,565.21 vs +7,013.83 |
| break-attack | V3 halt tighten (post-bank) | 384 | 61% | +8,907.39 | **-312.63** | +23.20 | +247.43 | +254.49 | 83% | -119.26 | 34 | +3,834.89 vs +4,147.51 |
| break-attack | V3b (+pre-bank) | 384 | 61% | +8,833.74 | -386.27 | +23.00 | +245.38 | +254.49 | 83% | -119.26 | 36 | +3,825.65 vs +4,211.92 |

Hand-traces (largest |delta| trade):
- V2 PCLA 2026-06-26 sig 09:50:10 ET entry 3.5350 stop 3.0100: VWAP-loss at 09:51:00 (close 3.3450 < vwap 3.3738) -$33.90 vs E3 +$496.10 (bank 10:03:40, trail 12:02:30 from run-high 11.57). The break dipped under VWAP 50 seconds after entry and then ran +200%.
- V2 AARD 2026-07-10 grinder sig 10:46:30 entry 5.3300: VWAP-loss 10 seconds later (5.2000 < 5.2068) -$19.44 vs E3 +$117.63 (eod).
- V3 PSQH 2026-07-28 grinder: tight trail at 14:13:40 (close 4.4992, runhi 4.75) +$131.30 vs E3 +$105.14 — the one that paid.
- V3 PCLA 2026-06-26 BA: tight trail at 11:06:40 (close 5.94, runhi 6.60) +$188.85 vs E3 +$496.10 — the near-band tighten sold the middle of a rocket.

**Verdicts:**
- **V1 (VWAP-loss after bank): LEAVE-ALONE.** Negative on both lanes (-$76 grinder / -$1,040 BA); on the fired trades E3 out-earns the rule every time. Losing VWAP after banking is a shakeout on this tape more often than a top.
- **V2 (VWAP-loss anytime): REFUTED hard.** -$1,272 grinder / -$9,579 BA (BA lane goes to a loss; 320/384 fires). Breaks launch from at/under VWAP and dip through it in the first minute — the eye is exactly wrong on the entry-side pattern the lane exists for.
- **V3/V3b (halt-distance tighten): LEAVE-ALONE.** +$107 on 11 grinder fires (noise-sized, N=11) vs -$313 / -$386 on BA (34-36 fires); net across the champion book -$205 / -$279. LULD proximity does not mark the top on 10s bars; the tighten sells the middle of the halt-and-go rockets (PCLA). Caveat: LULD band is a 5-min-mean proxy, no exchange reference price; still, no direction to chase.
- Combined: E3 remains the exit of record; **no exit-side eye earned a wire today**. What the exits DO owe is X1 (15:45 flatten parity) — a fidelity correction, not an eye.

Officers touched: Trade Manager (exit verdicts), Wind Tunnel (X1 flatten parity; LULD proxy caveat), Systems Quant (baseline reconciles to the cent; two separate-context code auditors), Side Marshal (SIDE = stamp-only everywhere; joins 1-2 queued), Strength Ombudsman (V2 would have refused +$7,014 of E3 strength; dip_rip exemption hearing queued), Crown Steward (crown consulted at NO exit; join 14 queued), Halt lane / Webull Desk (dead `half_size` flag E1), Momentum Operator (all four exit variants = noise or worse), Statistician (`exit_eyes_join_20260816_out.json`), Blast Radius (E1-E5, X1-X3 = observe-only findings), Historian (first full matrix of record 8/16), Cartographer (rung ratchet reads raw Kev store, X2), Forward Architect (join queue = the registry seed), Dashboard Curator (clean — snapshot renders exist), Hidden Architect (v2 above+falling cell = rebuild input), Feed Engineer (clean).

---
## DECISION LIST FOR MARCOS (one page)

**Nothing on this list changes what the bot does with money without your word. Every WIRE below is a priced ask; every LEAVE-ALONE has its number.**

PROPOSALS (priced):
1. **v2 rebuild spec: cut above-VWAP + falling-VWAP fires** — -$1,042 over 234 sim trades (context_joins J1). Applies to the UNSHIPPED v2 only; goes to the Hidden Entry Architect's spec, no live change. Price: $0 live; +$1,042 on the shadow book.
2. **Wind Tunnel parity fix (X1): re-run E3 rounds F/G/CJ/Sunday with the LIVE 15:45 flatten** (sim uses 15:59 grinder / last-bar BA). Price: analysis only, ~1 hour; may move every E3 dollar figure. Ask: run before Monday's OOS wall grades live-vs-sim.
3. **Fix the dead `half_size` flag on halt-arm converts (E1)** — the "half size" privilege in the 8/8 halt-lane doctrine is never consumed (:7706, single occurrence). Behavior change to sizing = your call: implement half size as ordered, or strike it from the doctrine. Price: sizing only on halt converts (arm-only by code default today).
4. **Extension guard fail-open on grinder/halt/seam (E2)**: today it never binds on those lanes (no ema90 in extra). Options: (a) leave and record as "no extension guard on these lanes" (honest), or (b) feed ema90 and let the 25% guard bind. Needs join #4 first — no wire yet.
5. **Stamp-only promotions — none.** VWAP slope, SIDE, lens, halt-distance and VWAP-distance stay STAMP on every lane; the joins say the clauses cost money or are noise.

LEAVE-ALONES (with reasons):
- E3 exits stay eye-blind: VWAP-loss after bank -$76/-$1,040; VWAP-loss anytime -$1,272/-$9,579; halt-distance tighten +$107/-$313. No exit-side eye pays (Part 3).
- Grinder VWAP slope clause: rising 2.8x per trade vs flat, but flat still +$625 — quality ratio nobody asked for (J1).
- Break-attack "above-VWAP only": forfeits +$438 (below side net green) (J1).
- Runway gate: keeps its job, -$195.70 saved on 51 refusals; only the 0.7-1R band (+$74.57, N=7) is a re-grade item, never a loosen-now (J2).
- Break-attack volume clause / failed-break exit / no-progress-15 / midday survivor / leaders-only reclaim / power-hour lane / halt-retest lane: all REFUTED Sunday (T1-T6). Do not add.
- Ignition census-cell gate: stays STAMP (`IGNITION_CELL_GATE`=0) — your priced item from 8/14 is unchanged; nothing new today.
- Chart-gate enforcement, back-side, break-side, min-stop, ceiling: no join today argues for movement; the EYES_AUDIT dead-suspects (stand-down rows, ambient rows, crown_pre_exempt rows) still need their production drills, not code faith.

JOIN QUEUE (no wiring until run): 15 items in Part 2 — top three by value: (#15) 15:45 flatten parity, (#1/#2) SIDE stamp × champion lanes, (#7) halt distance at ENTRY on champion fires.

Standing by.
