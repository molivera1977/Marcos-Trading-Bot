# JOINT DOOR 8/16 — VERDICT: **NO JOINT DOOR as specified (Kev fingerprint spec = 3% of the field, 0/37 of his picks, sees rockets at 0.24x the dud rate; every cell fails both bars). SELECTION LIFT REAL BUT IT IS NOT KEV'S FINGERPRINT — a post-hoc "quiet premarket tape" filter (calm <= 90 bps 1-min range, no gain clause; 34% of the field) lifts every pullback entry in his window (v2 flush +$19.90/trade, BA +$26.24/trade, both 0/200 in a label-shuffle null, monotone in threshold, both halves +), and BA 09:30-10:30 on those names with E4W clears BOTH bars at 2 slots (+$212.56/+$196.00 per day, 62 dates) — but it beats the O-config only through the E4W exit; on the O-config's own E3 exit it is +$115.67/+$124.37 (PASS, does not beat).**

**Officers:** Hidden Entry Architect (lead: the v2 toll), Seam Scientist (registry: window/selection hypotheses), Kev Librarian (his picks = calibration only, per Marcos 8/16 correction), Statistician (`joint_door_20260816_out.json`, `_run.txt`, `_b_run.txt`), Wind Tunnel (engine chain X->S->G->F->C->B->E imported unchanged; ONE local exit sim reconciled to X.sim_var_live to the cent on 9,254 RTH trades, max diff $0.0000), Momentum Operator (nothing ships on this — see caveats), Strength Ombudsman (the filter that wins is a WEAKNESS-avoid filter: it excludes the heavy-premarket-volume, already-run names), Side Marshal (front-side reading below), Historian (Kev picks list = `ticks_precursor/kev_watchlist.json`, 34 dates), Blast Radius / Trade Manager (E4W = behavior change on real money -> Marcos prices it; NOT an auditor ship). Rocket Rider, Crown Steward, Dashboard Curator, Feed Engineer: clean.
**Scripts:** `data/killtests/joint_door_20260816.py` (all layers, 3 selection definitions, 176 cells, portfolios, traces) + `joint_door_20260816_b.py` (robustness: component isolation, threshold sweep, bucket character, shuffle null, E3-exit portfolios). Universe = full bars10s cache, 729 name-days, 62 dates 2026-05-18..2026-08-14. Ran 8/16 ~20:50 EDT (`date` 20:58:34 EDT).

## 0. Marcos's correction applied (8/16): the fingerprint is a FIELD FILTER, not his pick list
Every one of the 729 name-days is stamped; his 37 in-cache picks are only the honesty check. Lead finding, as asked — **does the fingerprint SEE the field's rockets?**

| selection definition | qualifies | Kev picks pass | top-60 big rides seen | 724 vertical legs on passing names | ROCKET name-days seen | DUD name-days seen | **ENRICHMENT rockets/duds** |
|---|---|---|---|---|---|---|---|
| **A_spec** (pre-registered): spread<=80 bps & calm<=X & gain>=+20% by 09:30 (or 08:00) | 20/729 (3%) | 0/37 (0%) | 1/60 (2%) | 3/724 (0%) | 3/306 (1.0%) | 17/423 (4.0%) | **0.24x** |
| B_tape (post-hoc): spread<=80 & calm<=X, no gain clause | 246/729 (34%) | 9/37 (24%, 0.72x) | 22/60 (37%) | 237/724 (33%) | 92/306 (30.1%) | 154/423 (36.4%) | **0.83x** |
| C_liquid_runner (post-hoc): spread<=80 & gain>=+20%, no calm | 113/729 (16%) | 2/37 (5%, 0.35x) | 3/60 (5%) | 49/724 (7%) | 29/306 (9.5%) | 84/423 (19.9%) | **0.48x** |
| component: gain>=+20% by 09:30 alone | 258/599 stamped | - | - | - | 88/306 (29%) | 170/423 (40%) | 0.72x |
| component: spread<=80 & calm alone | 180/599 | - | - | - | 69/306 (23%) | 108/423 (26%) | 0.88x |

**Reading:** no version of the fingerprint puts the field's rockets on his screen at better than chance — every enrichment ratio is BELOW 1.0. Rocket name-days are the ones that are already busy/volatile/extended before the open (see census component: "gain>=20% by 09:30" is 0.72x because 288 of the 306 rocket name-days make their leg AFTER 09:30 and most have not run yet at the stamp — 26/28 of Kev's own legs are before 10:00, the field's are not). The precursor study's Kev fingerprint (tighter spread, calmer range) described HIS legs vs the field's legs at liftoff; as a 09:30/08:00 scanner it does not find the field's movers. Marcos's instinct is confirmed in the other direction: he "scans for movers not on his list" — nothing in the tape shape at 09:30 tells you which quiet name becomes one.

## 1. LAYER 1 — the stamp (how it was built)
- Spread proxy = median 10s-bar range/close (bps) over the prior 30 min (NBBO not cached for stamp windows; disclosed). Calm = median 1-min range/close (bps). Gain ref = first bar of the file (04:00 ET open) — the cache carries no prior close (disclosed; same as every prior study on this cache).
- Calm X calibrated at the 30th percentile of the 09:30 stamp: **89.9 bps** (n=599 stamped). Spread<=80 passes 405/599; calm<=X 180/599; gain>=20% 258/599. Their CONJUNCTION passes only 17 at 09:30 + 6 at 08:00 = 20 name-days: calm/tight names are, at 09:30, mostly the ones that have NOT run yet (IN bucket median gain +4% vs OUT +15%). The spec's expectation of 20-35% was wrong about the joint distribution, not the parts.
- 08:00 stamp needs >=10 traded bars 07:30-08:00 ET: available on 488/729.

## 2. Selection lift table ($/trade under E3, Kev-shaped vs NOT; best exit for the shaped cell)
### A_spec (pre-registered) — the honest cells (N is tiny)
| window | entry | KEV N | KEV $/tr | NOT N | NOT $/tr | lift | best exit | best $/tr |
|---|---|---|---|---|---|---|---|---|
| 07:00-10:00 | v2 flush (C1-C5) | 39 | +$7.13 | 1358 | +$2.95 | +$4.18 | E4W | +$17.36 |
| 07:00-10:00 | band-pass reclaim (2-below) | 1 | -$84.64 | 45 | +$12.26 | -$96.90 | E4 | -$56.68 |
| 07:00-10:00 | premarket reclaim (07:00-09:25, flat 09:25) | 4 | +$34.07 | 92 | +$10.78 | +$23.29 | E4 | +$57.62 |
| 07:00-10:00 | flat-top break-attack | 8 | +$13.81 | 258 | +$37.96 | -$24.15 | E4 | +$29.16 |
| 09:30-10:30 | v2 flush | 57 | +$6.79 | 2149 | +$1.22 | +$5.58 | E4 | +$16.85 |
| 09:30-10:30 | band-pass | 1 | -$84.64 | 73 | +$6.21 | -$90.85 | E4 | -$56.68 |
| 09:30-10:30 | flat-top BA | 21 | +$2.30 | 611 | +$27.40 | -$25.10 | E4 | +$15.20 |
All 60 A_spec cells FAIL both bars (day medians $0 — the bucket trades on ~6 of 62 days). Portfolio (best per window, 2-slot, live parity): W1 v2cal/E4W +$9.58/$0.00 per day, W2 v2cal/E4 +$15.08/$0.00, JOINT +$18.53/$0.00 — FAIL, does not beat O-config.

### B_tape (post-hoc, 34% bucket) — where the lift lives
| window | entry | IN N | IN $/tr (E3) | OUT N | OUT $/tr (E3) | lift | IN best exit | best $/tr | best day mean |
|---|---|---|---|---|---|---|---|---|---|
| 07:00-10:00 | v2 flush | 493 | **+$15.95** | 904 | -$3.95 | **+$19.90** | E4W | +$37.29 | +$296.49 |
| 07:00-10:00 | band-pass | 24 | +$17.46 | 22 | +$2.19 | +$15.27 | E4W | +$86.99 | +$33.68 |
| 07:00-10:00 | premarket reclaim | 30 | +$4.05 | 66 | +$15.25 | -$11.20 | E4 | +$8.59 | +$4.16 |
| 07:00-10:00 | flat-top BA | 124 | **+$52.09** | 142 | +$24.26 | +$27.83 | E4W | +$96.22 | +$192.45 |
| 09:30-10:30 | v2 flush | 767 | +$12.03 | 1439 | -$4.33 | +$16.36 | E4W | +$27.10 | +$335.21 |
| 09:30-10:30 | band-pass | 33 | +$5.52 | 41 | +$4.55 | +$0.97 | E4W | +$74.86 | +$39.85 |
| 09:30-10:30 | flat-top BA | 239 | **+$42.88** | 393 | +$16.64 | **+$26.24** | E4W | +$84.65 | +$326.29 |
Cells clearing bars (B_tape, solo dedup, no capacity — full 176-cell grid in `_run.txt`): v2 flush IN W1 clears BOTH bars under all four exits (E3: 42/62 green, day mean/median +$126.79/+$100.30, worst day -$286, worst trade -$87, 5 HR>=$250, DD $349); BA IN W1 and W2 clear consistency under all exits and convexity under E4/E4W (BA IN W2 E4W: 61% win, +$84.65/tr, +$326/+$269 per day, 54/62 green, 26 HR, worst day -$134, DD $134). Band-pass, premarket reclaim: N too small, fail. C_liquid_runner: NEGATIVE lift everywhere (v2 -$12.82, BA -$34.50) — the gain clause is the poison.

### Robustness of the B_tape lift (`_b_run.txt`)
| selector | passes | v2 W1 IN $/tr | OUT | BA W2 IN $/tr | OUT |
|---|---|---|---|---|---|
| calm<=p30 & spread<=80 (B_tape) | 246 | +$15.95 (493) | -$3.95 (904) | +$42.88 (239) | +$16.64 (393) |
| calm<=p30 only | 248 | +$15.90 | -$4.00 | +$42.57 | +$16.70 |
| spread<=80 only | 469 | +$5.60 | -$2.81 | +$28.01 | +$23.23 |
| calm<=p20 & spread | 189 | +$17.87 | -$2.22 | +$49.36 | +$17.70 |
| calm<=p40 & spread | 314 | +$11.77 | -$4.38 | +$38.56 | +$15.31 |
| calm<=p50 & spread | 372 | +$9.08 | -$4.14 | +$33.72 | +$17.09 |
- The whole lift is the CALM clause; the spread proxy adds nothing. Monotone: tighter calm -> bigger lift.
- Label-shuffle null (200 draws, same IN count): v2 W1 real +$19.90 vs null p99 +$6.65 / max +$8.11 (0/200); BA W2 real +$26.24 vs null p99 +$15.24 / max +$16.35 (0/200).
- **What the bucket IS (medians at 09:30):** IN = price $2.31, premarket volume 540k, +4% vs the 04:00 open, only 78/180 ten-second bars traded 09:00-09:30; OUT = $2.62, 13.1M premarket volume, +15%, 180/180 bars traded. "Calm" = THIN, UNDISCOVERED, NOT-YET-RUN premarket tape. Rocket-day rate IN 92/246 (37%) vs OUT 214/483 (44%). This is a front-side / not-extended filter (Side Marshal, back-side gate family), NOT the busy-liquid tape the precursor study found on Kev's names — the honesty check agrees (his picks 0.72x).

## 3. THE v2 TOLL — yes or no, with the number
On the pre-registered Kev fingerprint (A_spec) in his window (07:00-10:00 = RTH 09:30-10:00, calibrated v2 flush C1-C5): **N=39, +$7.13/trade under E3 (28% win) — technically above the ~$6 toll by $1.13 on 39 trades, i.e. NOT a real answer** (E4 +$15.60, E4W +$17.36, S5 +$8.32; day median $0.00, trades on 6 of 62 days).
On the quiet-tape bucket (B_tape) in the same window: **N=493, +$15.95/trade E3 = 2.7x the toll (E4W +$37.29)**; the same entry on the OUT names is -$3.95/trade. So the answer Marcos keeps asking for is: **YES — the pullback entry's per-trade edge exceeds its toll on QUIET-TAPE names in the first half hour (+$15.95 vs ~$6), and NO on the busy/extended names (-$3.95); it is a selection statement, not a Kev-fingerprint statement.** 36-date subset 2-slot v2 W1 E3 IN: +$82.05/+$38.30 per day, 21/36 green -> FAILS the consistency bar on the go-live window (median $38 < $50); 62 dates PASS (+$79.56/+$53.01, 41/62).

## 4. PORTFOLIO — 2 slots, live parity (15:45 flatten, 15:30 cutoff), B.pipeline H1-H4
O-config baseline (flatten-parity 8/16): +$156.76 mean / +$130.35 median, 33/36 green, worst -$109.55 (36 dates).
| config | dates | N | day mean | day median | green | halves $/d | worst day | 5-crit | HR>=250 | worst tr | maxDD | beats O? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_spec best W1 v2cal/E4W KEV-only | 62d | 36 | +$9.58 | $0.00 | 5/62 | +$20/-$1 | -$104.58 | FAIL | 2 | -$37 | $194 | no |
| A_spec JOINT (pre_reclaim + W1 + W2) | 62d | 53 | +$18.53 | $0.00 | 7/62 | +$37/+$0 | -$120.60 | FAIL | 4 | -$37 | $263 | no |
| **B_tape BA W2 E4W IN-only** | 62d | 130 | **+$212.56** | **+$196.00** | 50/62 (81%) | +$224.86/+$200.27 | -$129.11 | PASS | 19 | -$66 | $259 | **BEATS (both bars)** |
| B_tape BA W2 E4W IN-only | 36d | 76 | +$185.16 | +$163.28 | 30/36 (83%) | +$123.44/+$246.89 | -$129.11 | PASS | 8 | -$61 | $129 | BEATS |
| B_tape BA W2 **E3** IN-only (O-config's exit) | 62d | 135 | +$115.67 | +$124.37 | 53/62 (85%) | +$107.00/+$124.33 | -$125.07 | PASS | 2 | -$66 | $196 | no (mean/median below) |
| B_tape BA W2 E3 IN-only | 36d | 80 | +$118.14 | +$124.37 | 32/36 (89%) | +$113.88/+$122.39 | -$103.05 | PASS | 1 | -$61 | $103 | no |
| BA W2 E4W ALL names (no selection) | 62d | 178 | +$194.87 | +$156.80 | 51/62 | +$241.47/+$148.27 | -$152.89 | PASS | 19 | -$72 | $213 | (exit alone beats on 62d; 36d +$156.10/+$110.55 = no) |
| BA W2 E3 ALL names | 62d | 196 | +$108.52 | +$86.77 | 48/62 | +$130.11/+$86.93 | -$109.55 | PASS | 2 | -$72 | $178 | no |
| BA W2 E3 OUT-only | 62d | 206 | +$55.40 | +$59.30 | 41/62 | +$84.43/+$26.37 | -$161.75 | PASS | 2 | -$72 | $396 | no |
| B_tape v2cal W1 E4W IN-only | 62d | 269 | +$158.45 | +$122.64 | 40/62 | +$182.30/+$134.59 | -$239.13 | PASS | 17 | -$70 | $415 | no (median) |
| B_tape v2cal W2 E4W IN-only | 62d | 348 | +$182.32 | +$127.03 | 45/62 | +$194.18/+$170.45 | -$276.41 | PASS | 19 | -$70 | $348 | no (median) |
| B_tape JOINT (pre_reclaim E3 + v2cal/E4W W1 + BA/E4W W2) IN-only | 62d | 307 | +$239.77 | +$190.67 | 47/62 (76%) | +$291.98/+$187.56 | -$167.13 | PASS | 24 | -$161 | $278 | BEATS (both bars) |
Decomposition of the "beat": selection on E3 adds +$7 mean / +$38 median to BA W2 (ALL -> IN); the exit E4W adds +$86 mean / +$70 median; the O-config's mean is beaten only when E4W is in the sandwich. E4W (never-bank, 20%-off-high trail) is a behavior change on real money — priced here, not an auditor ship; and it lowers win% (71% -> 61%) and raises the worst day (-$125 -> -$129) while adding 17 more $250+ trades.

## 5. Hand-traces — three Kev-pick name-days (B_tape shaped; A_spec traces UPC/AZI/BTCT in `_run.txt` lines 88-120)
- **AZI 6/29** (Kev pick) ref 1.90; 09:30 stamp spread 0 / calm 56 / gain -2% -> IN. v2cal 13:33:10Z entry 2.1100 (fill 2.1311) stop 2.0500 -> BANK 1/2 at 2.3442 13:34:50, TRAIL rest 13:46:10 at 2.7960 (hi 3.2099) = **+$103.01**. Band-pass 13:37:20Z 2.5550/2.1000 -> +$45.88 same exit bar. Later v2cal 14:18:10 -$18.68, 14:24:10 -$20.93 (stopped 1 bar later each). Read: the quiet name that ran +50% inside 15 minutes; the two later flushes were the top.
- **SURG 7/02** (Kev pick) ref 0.6686; 08:00 stamp 35/90/-10% PASS, 09:30 stamp 28/74/-13% PASS -> IN. v2cal 13:31:00Z 0.5795/0.5517 -> STOP 13:32:50 = -$31.06 (the -$6 toll shape: 854 sh x 3.6c). BA 14:01:40Z 0.5415/0.5115 -> BANK 14:18:00 at 0.6016, TRAIL 14:54:20 at 0.6071 (hi 0.6792) = +$52.53; v2cal 14:06:50 +$40.99 and 14:14:40 +$43.70 rode the same leg. Read: down -13% at 09:30 vs the 04:00 open, quiet, then a +25% grind — 3 doors, 3 rides.
- **CLRO 7/07** (Kev pick) ref 6.98; 08:00 stamp spread 0 / calm 34 / gain -1% PASS; 09:30 stamp 156/367/+37% FAIL -> IN via the 08:00 stamp only. v2cal 13:49:50Z 9.1201 (fill 9.2113) stop 8.6994 -> BANK 13:55:10 at 10.1324, TRAIL 14:30:10 at 11.0510 (hi 12.43) = **+$74.93**. Read: the 08:00 stamp saw a quiet name; by 09:30 it was already +37% and "loud" — and the pullback still paid because the leg continued to 12.43. Note the 09:30-only version of the filter would have excluded it.

## 6. Bars, caveats, what this is NOT
- Consistency bar = day mean AND median > $50, green >= 55%, both halves > 0, worst day > -$300. Convexity bar = both halves > 0, >= 5 trades >= $250, worst trade > -$150, max drawdown of cumulative daily P&L < $1,000, premium (sum of HR trades) reported. Solo cells are dedup (same name <= 5 min), no capacity; portfolios are B.pipeline H1-H4 (2 slots, halt-gap rule, chronological fills), exits live-parity (15:45 flatten; pre_reclaim flattens 09:25 on the premarket slice, VWAP anchored 07:00 ET, slot key = fill time since it is flat before any RTH fill — disclosed).
- **B_tape is POST-HOC**: A_spec was the pre-registered fingerprint; B and C were added after A qualified 3% and passed 0/37 Kev picks. B's lift survives halves, threshold sweep and a shuffle null, but it is ONE of three definitions tried on the same 62 dates — treat as a registered hypothesis for the Seam Scientist's OOS wall (>= 5 forward days), not a nominee. The mechanism it captures (thin, not-yet-run premarket tape) is a cousin of the back-side gate and of anatomy's "front-side / near highs" finding, which is why it is plausible; it is NOT Kev's liquid-busy fingerprint.
- Fingerprint proxies: bar-range spread proxy != NBBO spread; "spread 0" = single-print bars (thinness), which is exactly why the spread clause carries nothing. Gain ref = 04:00 open (no prior close in cache) — the +20% clause is against the premarket open, which is part of why A_spec/C fail: names already gapped at 04:00 read as +4%.
- E4W: never-bank 20%-off-high — the same exit that lifted every big-rides/crown study; on this test it converts a PASS-but-not-beat (E3) into a beat. Trade Manager: this is the exit question Marcos owns; not settled here.
- The premarket reclaim (c) is sim-only on a 07:00-anchored VWAP; N=30/66, day medians $0 — no verdict possible.

## 7. Registry entries (Seam Scientist)
- H-JD1: "quiet-premarket-tape filter (1-min range/close median <= ~90 bps in 09:00-09:30 ET, or 07:30-08:00) x pullback doors x 09:30-10:30" — kill-test above (in-sample, post-hoc); OOS forward: stamp the live board daily at 09:30 with the calm value (data-only row), grade after >= 5 days.
- H-JD2: "any 09:30/08:00 tape-shape scanner enriches the field's rockets" — REFUTED at name-day level for all three shapes (enrichment 0.24x / 0.83x / 0.48x).
- H-JD3: "v2 flush clears its toll on quiet names" — supported in-sample (+$15.95 vs -$3.95, null 0/200); 36-date 2-slot median $38 fails the consistency bar; not a lane.
