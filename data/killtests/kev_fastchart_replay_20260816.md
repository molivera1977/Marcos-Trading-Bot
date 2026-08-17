# KEV FAST-CHART REPLAY 8/16 — VERDICT: **all three of Kev's fast-chart detectors, coded to his words with his context gates, LOSE or break even at BOTH resolutions on 197 SIP name-days (10s: 399 fires, KEV-exit −$581, F-control −$3,889; 5s: 216 fires, KEV −$262, F −$3,889→+$744 only via one detector's tail). Kev-A (confluence wick) REFUTED at 10s and 5s (F-control −$26/−$16 per trade, 15-26% win, 0 HR trades). Kev-B (level hold) REFUTED both (F −$25/−$29 per trade). Kev-C (halt double-bottom) = the only entry whose F-control is POSITIVE (+$29/trade 10s, +$59/trade 5s, +$23/trade at scale on 719 name-days) but every managed exit gives it back (KEV +$3.62 / E3 +$3.08 / E4W −$7 at 10s) → NEEDS-DATA/EXIT, not shadow. Resolution verdict: 5s does NOT beat 10s on the fair twin — on 103 matched setups 5s enters at the same price (median Δpx 0.00%), 5s false-fires more in wall-time (ff30s 28-43% vs 11-34%), and its dollar edge over 10s is one detector's tail (B E4W +$737 vs −$86; C E4W +$1,854 vs −$812) inside a total that is still net-negative under Kev's own exit. Marcos's 5s hypothesis: NO, not with these detectors.**

**Officers:** Hidden Entry Architect (lead; owns Kev-A/B/C translation), Kev Librarian (spec source `kev_fast_chart_method_20260816.md`, coded verbatim), Seam Scientist (registry: resolution twin H-FC1..3, quiet-tape H-JD1 variant), Statistician (rows `kev_fastchart_replay_20260816_rows.json`, `_tables.txt`, `_traces.txt`, `_run.txt`), Wind Tunnel (bars built from identical SIP ticks at 5s and 10s = the fair twin; captures 1s→5s/10s = live-fidelity twin), Quartermaster (data inventory below: ZYBT 8/12 = 323 RTH ticks, unusable), Crown Steward (8/12-8/14 crown roster is the capture cohort), Trade Manager (Kev-native exit coded: ratchet-after-1R, failed-breakout, topping-tail), Momentum Operator/Blast Radius: **nothing ships**, analysis only. Historian: 8/16 21:26 EDT (`date`).
**Script:** `data/killtests/kev_fastchart_replay_20260816.py` (detectors, gates, four exits, twin matcher). Ran 8/16 21:16-21:20 EDT.

## 0. Data (Quartermaster)
| source | what | name-days | resolutions |
|---|---|---|---|
| SIP full-day ticks (`ticks_precursor/trades`, off-tape conditions dropped) | 97 crown name-days 8/5-8/14 (13:25Z-20:00Z) + 95 Kev-pick full days + top-30 rocket name-days (rocket_anatomy) fetched tonight + SCKT 8/10, FGI 8/13, ZYBT 8/12 | **197** (39 dates 5/20-8/14) | 5s AND 10s built from the same ticks |
| dashboard 1s capture (`~ALP1S`), crown roster 8/12-8/14 (+ZYBT) | 1s → 5s and 1s → 10s | **36** | both, identical 1s source |
| universe `bars10s` cache | 10s at scale | **719** | 10s only |
VWAP anchored premarket via bars10s cache seed where present (else file start — disclosed); 9/20 EMA on the series' own bars (9 bars = 90s at 10s, 45s at 5s — the "same chart, faster" reading; wall-time-matched EMA was NOT run). Prev close from the universe manifest / Alpaca daily. Entries 09:30-15:30 ET, flatten 15:45; RTH-official only (premarket fires not graded). $500 clip, +1% chase, −0.5% market exits, stop-first.
**ZYBT 8/12: 1,353 trades all day, 323 in RTH — a dead tape, 0 fires. Kev's ZYBT trade is not this date. NEEDS-DATA (hand-trace impossible).**

## 1. Detectors as coded (Kev's words → rule)
- **Kev-A confluence wick:** |VWAP−9EMA|/px ≤ 1%; bar low ≤ max(VWAP,9EMA)×1.005 and low < max(VWAP,9EMA); close > both; bar high < leg high (a pullback bar). Enter next bar on trade through the wick bar's high (+1%); stop = wick low.
- **Kev-B level hold:** bar closes through a whole-dollar (10c below $1) or the stale (>5 min) session HOD; next 3 bars' LOWS ≥ level; enter 4th bar open (+1%); stop = level.
- **Kev-C halt double-bottom:** LULD signature (≥240s no prints in RTH); within 15 min of resumption two lows within 0.5%, ≥3 bars apart, intervening high ≥1% above; enter on trade through that high (+1%); stop = lower low.
- **Context (all on):** mover = day gain ≥ +20% vs prev close at signal time; front side = close > VWAP and 9EMA > 20EMA; room = no session high within 3% overhead that is >5 min stale (blue-sky exempt); no topping-tail cluster (≥2 bars in prior 5 min with upper wick ≥60% range); ≤3 entries per detector per LEG (leg = new session high after a ≥3% pullback), no daily ration; one position per name.
- **Exits:** KEV (after a close ≥ entry+1R the stop ratchets to the prior bar low each bar; exit on close below the entry level = failed breakout; topping-tail bar ≥60% wick on ≥2× 10-bar vol; halt-gap; 15:45), E3, E4W, **F-control** (hold to 15:45, −7% catastrophe stop only).

## 2. Detector tables — SIP tick twin (197 name-days, identical ticks)
$/trade, N ungated. ff3 = stopped within 3 bars of own resolution; ff30s = stopped within 30s wall-time. stop% = median stop distance.
| det | res | N | KEV mean / sum | E3 mean | E4W mean | **F-control mean / sum** | win% (KEV) | HR≥$250 (KEV/E4W) | ff3 / ff30s | stop% | worst / best (KEV) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 10s | 101 | −$3.57 / −$361 | −$6.68 | −$12.66 | **−$26.45 / −$2,671** | 18% | 0 / 0 | 21% / 21% | 2.31 | −$30 / +$109 |
| A | 5s | 39 | −$8.44 / −$329 | −$5.26 | −$8.22 | **−$15.96 / −$622** | 10% | 0 / 0 | 23% / 28% | 1.95 | −$66 / +$35 |
| B | 10s | 182 | −$3.52 / −$640 | −$2.91 | −$0.47 | **−$25.16 / −$4,580** | 26% | 3 / 7 | 34% / 34% | 4.89 | −$173 / +$724 |
| B | 5s | 103 | −$1.35 / −$139 | −$1.10 | +$7.15 (+$737) | **−$28.89 / −$2,976** | 32% | 0 / 6 | 23% / 43% | 5.37 | −$153 / +$188 |
| C | 10s | 116 | +$3.62 / +$420 | +$3.08 | −$7.00 | **+$28.98 / +$3,362** | 28% | 2 / 5 | 11% / 11% | 6.95 | −$90 / +$548 |
| C | 5s | 74 | +$2.79 / +$206 | +$2.14 | +$25.06 (+$1,854) | **+$58.68 / +$4,343** | 31% | 1 / 8 | 16% / 28% | 5.45 | −$70 / +$335 |
Green days (KEV): A 6/23 (10s), 0/11 (5s); B 7/22, 4/17; C 6/18, 7/12. F-control median = −$37.32 (the −7% stop) in EVERY cell: the typical Kev-A/B/C fire on our tape goes on to lose 7% before 15:45 — the entries are not catching legs.

**Gate census (why so few fires):** of 13,195 signals, backside 5,373 (the "front-side" clause kills most rocket-day signals: 9>20 fails on the fast chart during the very pullbacks Kev buys), topping_cluster 3,656, not_mover 2,607, hours 814, no_room 97, leg_ration 29. Ungated 615. NOTE the topping-cluster gate is bar-count-defined (≥2 in 5 min) so it bites 5s ~2× harder — a real asymmetry in the twin (5s A: 538 blocked vs 10s 270); the ungated 5s N is therefore smaller, not "cleaner".

## 3. THE TWIN — 10s vs 5s head-to-head on matched setups (same name-day, detector, |Δt| ≤ 60s)
| det | matched | 5s earlier / same / later | Δt median | Δpx median (5s vs 10s) | 5s cheaper | KEV $ 10s → 5s | F $ 10s → 5s |
|---|---|---|---|---|---|---|---|
| A | 18 | 4 / 7 / 7 | 0s | 0.00% | 3/18 | −$59 → −$98 | −$283 → −$265 |
| B | 46 | 29 / 12 / 5 | −10s | 0.00% | 18/46 | +$112 → +$800 | −$1,399 → −$1,318 |
| C | 39 | 7 / 14 / 18 | 0s | 0.00% | 10/39 | +$416 → +$293 | +$1,394 → +$1,627 |
| capture twin (36 crown name-days, 1s→5s/10s) | 21 | A 1/5/0 · B 2/0/0 · C 0/6/7 | 0 / −15 / +5s | 0.00% | 3/21 | −$361 → −$324 | −$143 → −$146 |
Reading: 5s gets in EARLIER only on Kev-B (the "holds three" clock is 30s at 10s vs 15s at 5s — a definition effect, not a tape edge) and it does NOT get in cheaper (median Δpx 0.00% on all three); on Kev-C the 5s arm is more often LATER (double-bottom needs ≥3 bars apart, and 5s lows are noisier). The 5s dollar advantage on B/C lives entirely in the E4W tail (a handful of $300-$900 rides: 5s B best +$880, 5s C best +$942) — under Kev's own exit 5s is worse on A and C and better on B by $688 across 46 pairs. False-fire in wall-time is HIGHER at 5s (B 43% vs 34%, C 28% vs 11%). **5s beats 10s: NO** (Marcos's hypothesis; numbers above). What 5s changes is stop-touch granularity, and that cuts both ways.

## 4. Live-fidelity twin — dashboard 1s capture, crown roster 8/12-8/14 (36 name-days, 3 days)
| det | res | N | KEV | E3 | E4W | F | green days |
|---|---|---|---|---|---|---|---|
| A | 10s | 32 | −$374 (−$11.70) | −$396 | −$488 | −$720 | 0/3 |
| A | 5s | 12 | −$117 (−$9.72) | −$121 | −$167 | −$41 | 0/2 |
| B | 10s | 17 | −$670 (−$39.40) | −$548 | −$608 | −$297 | 0/3 |
| B | 5s | 9 | −$214 | −$380 | −$330 | −$171 | 0/3 |
| C | 10s | 18 | −$86 | −$181 | −$298 | −$159 | 0/2 |
| C | 5s | 20 | −$201 | −$316 | −$364 | −$233 | 0/3 |
Every cell red, every day red, both resolutions: on the week Kev's method was "back" (8/12-8/14, his STKH/LGHL clips), our coded version of it on the crowned names lost at both glasses. The capture agrees with SIP (SIP tick 8/12-8/14 subset in rows JSON).

## 5. 10s at scale — universe bars10s cache (719 name-days, 62 dates)
| det | N | KEV | E3 | E4W | F | win (KEV) | HR≥250 (F) | green days (KEV) |
|---|---|---|---|---|---|---|---|---|
| A | 427 | −$2,560 (−$5.99) | −$2,796 | −$3,037 | −$2,413 (−$5.65) | 16% | 9 | 8/60 |
| B | 752 | −$2,880 (−$3.83) | −$3,242 | −$1,730 | −$3,356 (−$4.46) | 31% | 21 | 15/62 |
| C | 390 | −$408 (−$1.05) | −$846 | +$144 | **+$8,800 (+$22.56)** | 22% | 15 | 12/58 |
Kev-C's F-control is positive at scale too (+$8,800/390, best +$5,754, but median −$37 and 12% win = pure tail); the managed exits (KEV/E3/E4W) all hand it back. Kev-A and Kev-B lose under every exit incl. the F-control on 1,179 fires.

## 6. QUIET-TAPE variant (joint_door H-JD1: calm ≤ 89.9 bps 09:00-09:30 ET, IN vs OUT)
| arm | IN N | IN KEV / E3 / E4W / F per trade | OUT N | OUT KEV / E3 / E4W / F |
|---|---|---|---|---|
| tick 10s A | 11 | −$1.03 / −$8.48 / −$13.36 / −$22.77 | 43 | −$5.19 / −$9.38 / −$13.89 / −$26.32 |
| tick 5s A | 5 | −$11.51 / $0.00 / +$0.99 / −$2.83 | 10 | −$9.87 / −$3.86 / −$7.71 / −$20.40 |
| tick 10s B | 46 | **+$10.70 / +$10.68 / +$9.64** / −$26.56 | 84 | −$7.88 / −$9.14 / −$5.37 / −$24.02 |
| tick 5s B | 22 | +$8.49 / +$18.21 / +$35.92 / −$13.79 | 36 | −$2.94 / −$11.10 / −$2.25 / −$38.55 |
| cache10 A | 106 | −$4.50 / −$3.51 / −$2.32 / −$13.67 | 271 | −$6.85 / −$8.41 / −$8.07 / −$1.47 |
| cache10 B | 219 | −$2.34 / −$0.32 / −$0.69 / **+$20.80** | 401 | −$6.75 / −$8.92 / −$8.53 / −$17.37 |
The quiet-tape lift from joint_door reappears in sign (IN beats OUT in 22 of 24 cells) but does not make Kev-A positive anywhere; it makes Kev-B modestly positive on the tick sample (46 fires, +$492 KEV, 5/11 green days) and flat at scale (219 fires, −$513 KEV, F +$4,556). Kev-A on quiet names: still red at both resolutions (N=11/5). Not a lane; goes to the H-JD1 OOS wall as a footnote.

## 7. Hand-traces (Sim Integrity) — `kev_fastchart_replay_20260816_traces.txt`
- **FGI 8/13** (pc 4.73, calm 190 = NOT quiet, 8 halts): 10s = 8 ungated fires (2 C early, 5 B in the 12:02-12:37 vertical, 1 C late) KEV −$52 net; best = **B 12:23:10** whole-dollar $15 hold: 12:22:30-12:22:50 bars low 14.52/14.92/15.16 hold ≥ 15.00 after the 12:22:30 break (14.52→15.00 on 171k), enter 12:23:10 open 15.275 (+1% = 15.43), stop 15.00... (as coded stop 14.82 = the level in that leg's scan) → ratchets, out 12:24:50 area +$21.12 KEV / +$62.81 E3 / F −$40 (7% stop hit at 13:05 halt). Bar-by-bar in the file shows 5s at the same 12:23:10 moment: the 5s series NEVER fires B here — its 3 holding 5s bars (15s) close before the 10s scan and the 4th-bar-open lands on 12:22:55/15.35 → gated by topping-cluster (two 60%-wick 5s bars in the prior 60 bars). 5s fired ONCE all day on FGI (C 10:34:40, −$17). At 10s the day's ride (13:05 halt → 19.8) was never entered: 12:37:20 B at 19.81 gapped through the stop on the 12:43 resumption (−$38).
- **SCKT 8/10** (pc 0.386, +450%, 24 halts): 10s = 4 fires; the one A (10:26:30, 2.11 r/1.96, VWAP 1.88 ≠ confluence with 9EMA... it passed at |Δ|≤1% momentarily) failed-breakout −$17; C 13:19:00 double bottom 2.00/2.02 → break 2.07 → +$25.73 KEV / +$46 E3, F −$37 (the −7% stop hit before the 13:26 halt run). 5s: **0 ungated fires / 252 signals** — every 5s signal on the day's rocket blocked by backside (9EMA<20EMA on 5s inside the pullbacks) or topping-cluster. Kev's LZMH-style "first pullback off the nine and VWAP" never printed as CONFLUENCE on SCKT: VWAP sat 10-15% below the tape all day (1.88 vs 2.05-2.30) — the confluence clause is the wrong test on a +450% name.
- **ZYBT 8/12:** NEEDS-DATA (323 RTH prints; not a rocket day; not Kev's ZYBT date).

## 8. Verdicts (per detector × resolution) — kill criteria from the spec: REFUTED if total < don't-trade F-control AND per-trade < the plain-10s higher-low baseline; NEEDS-DATA if fires < 15; SHADOW only if positive every day with worst day > −$100
| detector | 10s | 5s | why |
|---|---|---|---|
| **Kev-A confluence wick** | **REFUTED** | **REFUTED** | 101/39 fires, negative under all four exits incl. F-control (−$26/−$16 per trade); 0 HR trades; capture week 0/3 green days; quiet-tape variant still red; the VWAP+9EMA confluence essentially never exists on the day's rocket (VWAP is far below) — when it does, it is a lower-quality name/moment |
| **Kev-B level hold** | **REFUTED** | **REFUTED** (E4W tail noted) | 182/103 fires, F-control −$25/−$29 per trade; KEV/E3 negative both; 5s E4W +$737 = 6 rides in 103 fires with 43% 30s-false-fire; capture week 0/3 green; only quiet-tape 10s B is positive (+$10.70×46) — footnote to H-JD1 |
| **Kev-C halt double-bottom** | **NEEDS-DATA (exit)** | **NEEDS-DATA (exit)** | the only entry with a positive F-control (10s +$29/tr n=116, at scale +$22.56×390; 5s +$59/tr n=74) but 12-18% win/median −$37: entry-quality edge is a halt-tail lottery; KEV +$3.62, E3 +$3.08, E4W −$7 → does not clear the ~$6 toll; capture week 0/2 green. Belongs to the halt lane's docket (STRUCT ratchet from crown study), not to a fast-chart lane |
| **Resolution (Marcos: 5s beats 10s?)** | — | **NO** | matched setups: same price (Δpx 0.00% median), 5s earlier only on B by definition, higher wall-time false-fire at 5s, capture twin equal-red; 5s dollar wins are E4W tails on B/C, and 5s under-fires because bar-count gates bite twice as hard |

## 9. What this does and does not say
- It says: Kev's fast-chart cues, translated literally with his stated context, do not carry an edge on OUR tape at either glass. It does not say Kev's trading has no edge — his fills are discretionary (his "buyer comes in" is not a rule; the [UNVERIFIED] L2 read stays open) and his 2026 material is 5 clips.
- Known translation defects to log (Hidden Entry Architect): (1) topping-cluster gate is bar-count-defined → 5s under-fires (fix = wall-time count); (2) "front side = 9>20 on the fast chart" blocks the pullback moment by construction (Kev reads front side on the 1-min) → the biggest gate; a 1-min front-side stamp is the honest re-run; (3) EMA span in wall-time differs 2× between arms; (4) F-control uses −7% flat, so a $37 loss dominates medians — but the SIGN of the F-sum is what the kill criterion reads.
- Baseline to beat (crown study (b) plain-10s higher-low): also negative on crowns; nothing here beats "don't trade" except Kev-C's unmanaged tail.
- Registry (Seam Scientist): H-FC1 "5s > 10s for Kev-A/B/C" REFUTED in-sample (197 nd); H-FC2 "Kev-C halt double-bottom + STRUCT/E4W exit" NEEDS-DATA (queue behind halt lane); H-FC3 "wall-time-fair gates flip the twin" OPEN (cheap re-run).
Standing by.
