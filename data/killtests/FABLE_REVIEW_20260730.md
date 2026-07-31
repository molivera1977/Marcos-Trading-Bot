# FABLE REVIEW — 7/30 · EXIT ARCHITECTURE + HIDDEN LANE

Marcos: *"build it for Fable to review."* Nothing below is implemented. Every number was produced
today on the honest harness (`data/killtests/harness.py`, acceptance-passed 7/29: 13 real trades
replayed, median error $4.03, sign agreement 13/13). Scripts are re-runnable:
`hidden_exit_configs_20260730.py` · `hidden_quality_20260730.py` · `hidden_quality_dollars_20260730.py`.

Live state: DRY_RUN. Two positions open at time of writing (CMCO, KSCP) — no deploy has occurred
and none may occur until the book is flat ([[feedback_flat_book_verified_in_turn]]).

---

## A · THE HEADLINE — hidden flips sign, but only with BOTH changes

190 hidden fires (7/27–7/30, converted + shadow), each priced through the real sizing chain
(risk ÷ stop, $1,000 cap, 5%-of-tape volume guard) and calibrated slippage (1.477% of entry).

| configuration | n | total | $/fire |
|---|---|---|---|
| **live today** (33%@1R, ×1.50, ×2.00; no protection until ×1.50) | 190 | **−$2,148.87** | −$11.31 |
| entry gate only (refuse 3–10% extension) | 121 | −$207.13 | −$1.71 |
| exit fix only (stop → scale-bar low after first scale) | 190 | −$645.83 | −$3.40 |
| **entry gate + exit fix** | **121** | **+$569.87** | **+$4.71** |

Neither change alone saves the lane. Together they move it +$2,719 on the same fires.

### A1 · The entry finding — extension above VWAP is BIMODAL

| ext_vwap at entry | n | hit 1R | hit 2R | $/fire (live) | $/fire (fixed exit) |
|---|---|---|---|---|---|
| 0–1% | 45 | 58% | 42% | −13.57 | −4.99 |
| 1–2% | 23 | 48% | 30% | −24.21 | −9.35 |
| 2–3% | 22 | 45% | 18% | −23.27 | −2.78 |
| **3–5%** | 29 | **28%** | 14% | **−30.50** | −21.16 |
| **5–10%** | 40 | **32%** | **5%** | **−26.43** | −15.05 |
| **10%+** | 31 | **84%** | **58%** | **+47.49** | **+34.54** |

Two good zones, one dead zone. Right at VWAP (0–1%) = the clean dip-buy. **10%+ = the entire
business** (+$1,472 live on 31 fires) — the deep wick inside a genuine vertical, which is what the
lane was designed for. The 3–10% band is no-man's-land: −$1,942 across 69 fires, and it survives
BOTH exit configurations, so it is an entry property, not an exit artifact.

NOT the refuted room gate: room measured distance to overhead supply and punished momentum (7/21
kill-test: it would have blocked ZYBT +$164.79 and BIYA +$34.40). This measures how far PAST VWAP we
buy — Kev's "buying into past supply" as a number — and it KEEPS the momentum cell (10%+ is the
best cohort on the board).

### A2 · The exit finding — three stacked defects, all verified in code

1. **`VELOCITY_RIDE` suppresses every scale on this lane.** `_vride_defer` (:6785) skips the scale
   when price gained ≥12% over 5 one-minute bars. A hidden entry is BY DEFINITION a ≥25%/5min
   rocket — so the deferral fires exactly when the tier is reached. Result: **1 of 11 hidden trades
   ever banked a partial**, while 8 of 11 peaked at ≥2R (two above 10R). WLDS had ELEVEN 3-min
   closes above its 1R target and banked nothing. Shipped as a DRY_RUN experiment 7/5, never graded.
2. **Tier 2 at ×1.50 (+50%) is unreachable** for the moves this lane catches — 8 of 11 trades never
   came close.
3. **`BE_FLOOR_AFTER_SCALE=2` therefore never engages**, so the runner rides the ORIGINAL stop
   through the whole round trip. NUWE 7/30: peaked **+4.25R**, closed **−0.25R**.

### A3 · Protection configs, walked bar-by-bar (Marcos: *"try different configurations before
implementing BE and losing on those wiggles"*)

| post-first-scale protection | total | $/trade | wins | shaken out |
|---|---|---|---|---|
| A none (live) | −$163.58 | −18.18 | 1 | 3 |
| B breakeven at entry | −$112.08 | −12.45 | 4 | 4 |
| C entry − 0.25R | −$130.73 | −14.53 | 4 | 4 |
| D entry − 0.50R | −$149.39 | −16.60 | 0 | 4 |
| E entry − 0.75R | −$149.95 | −16.66 | 1 | 3 |
| **F stop → scale-bar low** | **−$96.04** | **−10.67** | 4 | 4 |

Marcos's wiggle concern is REAL and measured: 4 of 9 get shaken out and trade higher afterward.
F wins anyway. **Every config still loses on the 9 converted trades** — which is why the entry gate
(A1) is the necessary other half.

**RETRACTION on the record:** I first estimated BE-after-1 at +$84 to +$130 using arithmetic that
assumed the remainder exits AT breakeven and that "9 of 9 reached 1R." Walking the tape in order
showed only **4 of 9 reached 1R before their stop** — the other five stopped out first and the stock
ran afterward. Those figures are VOID. Marcos's instruction to test configurations before
implementing is what caught it.

---

## B · THE RESTING-ORDER ARCHITECTURE (Marcos: *"all of our banking numbers should be limit orders waiting"*)

**Defect it removes:** every exit decision currently depends on software noticing something in time.
PN 7/30 (ignition, kev25 ladder): 1R target $21.73, price traded **$22.36** — and the ladder banked
NOTHING, because the scale is evaluated on the 3-min close and that candle closed at $19.31. Full
round trip to the stop, −$31.80, `partial_fills` empty.

Marcos: *"why are we waiting on a merry go round to stop when we should jump off"* — and the
asymmetry is already in our own code: `INTRABAR_STOP=1` makes LOSSES jump immediately, while GAINS
wait for a candle. We made losses fast and gains slow.

**Spec.** On fill, place the full exit scaffold at the broker: resting **stop** at the structural
level (already doctrine per the 7/27 kill-test) PLUS a resting **limit sell at every banking rung**.
Software's job shrinks to adjustment only — cancel/replace on trail ratchet, move the stop after a
scale fills, force-flat at 15:45.

**Wrong when X:** limits fill on wicks, so a runner that would have gone to 3R gets trimmed at 1R on
a spike. Measurable on tape; the replay prices it. Second X: an order-management bug double-sells
(stop and tier filling the same shares) — needs over-sell protection and post-restart reconciliation.

**DRY_RUN honesty requirement:** no broker exists, so the resting fill must be SIMULATED
conservatively — require the print, respect the volume guard, no fill on a single-tick wick through
thin size. Done carelessly this manufactures fake wins, which is worse than the current miss.

---

## E · IGNITION — the volume threshold is set at its worst tested value

Scripts: `ignition_quality_20260730.py` · `ignition_sweep_20260730.py` ·
`ignition_fine_sweep_20260730.py` · `ignition_gate_redundancy_20260730.py`.
Population = FIRST ignition fire per ticker per day (the live once-per-ticker cap), real detector
stops (replayed `ignition_10s_step`), honest harness, kev25 ladder. Downstream gates NOT applied
except where stated.

### E1 · Fine sweep with a PRE-REGISTERED out-of-sample split
Rule written before results: fit on 7/27–7/28, verify on 7/29–7/30; a threshold is credible only
if it beats the live 2.0× on BOTH halves.

| `IGNITION_VOL_MULT` | in-sample $/fire | out-of-sample $/fire | passes |
|---|---|---|---|
| **2.0 (LIVE)** | +1.60 | +1.98 | baseline |
| 2.5 | +1.39 | +1.93 | no |
| 3.0 | +0.57 | +0.86 | no |
| 3.5 | +0.12 | +4.65 | no |
| **4.0** | +3.09 | +5.65 | ✓ |
| **4.5** | +5.51 | +5.61 | ✓ |
| **5.0** | **+8.76** | **+5.73** | ✓ |
| **6.0** | +7.46 | +2.82 | ✓ |
| 7.0 | +6.58 | +1.39 | no |

Four thresholds survive and they form a CONTIGUOUS PLATEAU (4.0–6.0). An overfit is a lone lucky
cell; a plateau that holds on unseen data is the signature of a real threshold. **Proposed value
4.5×**, not the 5.0× peak: its halves are nearly identical (+5.51 / +5.61), it sits mid-plateau
rather than at an edge, and it keeps 42–43 fires vs 38. The live 2.0× is the worst setting tested
at or above it.

Other knobs swept, for the record: `IGNITION_MAX_EXT` +10%/+8% barely moves it (+1.36 → +1.18);
`IGNITION_MIN_ABS_VOL` back to 10k is WORSE (the earlier halving was right); combined
5.0×/+10%/10k is worse than 5.0× alone. **Volume is the only lever that pays.**
UNTESTED: `IGNITION_BASE_LOOKBACK` (4 min — defines what the multiple is measured against),
`IGNITION_BASE_MIN`, `IGNITION_STRONG`, `IGNITION_MIN_EXT`, `IGNITION_WINDOW_MIN`, stop construction.

### E2 · The once-per-ticker cap is doing enormous work
Same detector, same params, 7/27–7/30: **606 raw fires = −$1,759** · **first-fire-only = +$129**.
Every repeat fire on a name after the first destroys value in aggregate. The existing caps earn
their keep — this is evidence AGAINST loosening them.

### E3 · The chart gate appears INVERTED on ignition (doctrine question, not a recommendation)
Verified with the REAL `_chart_break_gate` at 5.0×, 81 fires:
- **CURRENT (ignition chart-gated): 5 fires trade → −$24.37**
- **BYPASS (ignition treated as a live-structure lane): all 81 trade → +$575.41**

Mechanism: ignition fires on a volume surge off a QUIET BASE — i.e. BELOW Kev's marked break,
before price reaches his level. "Price broke the marked level" is, for this lane, a LATENESS
detector. Same conclusion as the one-step curse and the late-entry thesis, from a third direction.

DOCTRINE MISMATCH: Marcos 7/26 — *"chart gates chart-trades, tape gates tape-trades."* The
live-structure bypass at :2857 contains `hidden_entry, vwap_reclaim, zone_flip`. **Ignition is not
in it**, yet it detects on 10s tape off a live base. The exclusion looks like a pre-7/26 oversight
rather than a decision.

CAVEATS, held firmly: the allow-cell is n=5; no day-gain/spread/min-stop applied; ignition-only —
says nothing about flat_top/ORB/ma_pullback, where the code records the gate grading −0.17R/trade
IN FAVOUR of gating. This contradicts a gate Marcos settled on 7/17 and therefore needs adversarial
review, not action.

### E4 · MARCOS'S MECHANISM — "the volume multiplier does what the chart gate is asked to do"
His words (7/30): *"filter out slow movers that have a better chance of wiggling and knifing."*
Two testable predictions. Script: `volume_vs_gate_20260730.py`. IGNITION ONLY.

**Prediction 1 — higher volume ⇒ fewer fast knives. CONFIRMED, but weakly:**

| vol | n | knife <2min | knife <5min | never stopped | median time-to-stop |
|---|---|---|---|---|---|
| 2.0 | 95 | 2% | 11% | 31% | 29.0m |
| 4.0 | 87 | 2% | 13% | 31% | 30.3m |
| 4.5 | 85 | 4% | 9% | 35% | 35.0m |
| 6.0 | 77 | 3% | **6%** | **36%** | **36.2m** |

Trades do survive longer at higher thresholds (5-min knife 11%→6%, never-stopped 31%→36%), but the
effect is modest — this is NOT the main channel by which 4.5× makes money.

**Prediction 2 — the gate is redundant on top of volume. CONFIRMED, and stronger than expected:**

| vol | gate OFF (all fires) | gate ON (allow only) | gate adds |
|---|---|---|---|
| 2.0 | +$144.76 | +$27.01 (n=8) | **−$117.75** |
| 3.0 | +$35.75 | −$35.65 (n=6) | −$71.40 |
| 4.0 | +$378.50 | −$1.26 (n=4) | −$379.76 |
| **4.5** | **+$482.51** | −$19.80 (n=5) | **−$502.31** |
| 5.0 | +$589.92 | −$21.34 (n=5) | −$611.26 |
| 6.0 | +$389.95 | −$35.71 (n=5) | −$425.66 |

The gate's cost RISES MONOTONICALLY as the volume filter improves ($118 → $502 → $611). That is the
signature of two filters aimed at the same target where one is strictly better: once volume has
selected for real participation, the gate's remaining function is to discard the survivors.

**Refinement to the mechanism (mine, offered as interpretation not fact):** the knife numbers are
small, so the channel looks less like "volume filters wigglers" and more like **volume selects for
genuine participation while the chart gate selects for LATENESS** — it admits only fires where price
has ALREADY cleared Kev's marked level, which on a surge-off-a-quiet-base lane means the move began
without us. Consistent with the one-step curse and the late-entry thesis.

CAVEATS: gate-ON cells are n=4–8; no day-gain/spread/min-stop modeled; 4 days; ignition only —
Marcos explicitly scoped this claim to ignition and made no claim about the other lanes.

RETRACTED: an earlier hand-written gate simulation reported 12 allow-fires / −$152 and a
"+$716.93 blocked" bucket. The real gate passes only 5 (it also SKIPS no-level names entirely).
Those simulated splits are void; the two verified figures above are the claim.

---

## C · QUESTIONS FOR FABLE

1. **Ship A1+A2 together or separately?** They only work together (each alone still loses). But
   that is 2 behavior changes in one set on one lane — acceptable, or split with the gate first?
2. **Exit config F (stop → scale-bar low) vs B (breakeven):** F wins by $16 on n=9. Is that enough
   to choose, or does F need the 190-fire population before it ships?
3. **Extension gate thresholds:** refuse 3–10% exactly, or keep a margin (e.g. 3–12%) given the
   10%+ cell is carrying the whole lane and the boundary is estimated from 4 days?
4. **`VELOCITY_RIDE`:** kill globally, or scope off for hidden only? It is a 7/5 DRY_RUN experiment
   that has never been graded on ANY lane — the same "untested experiment left live" class as the
   7/25 price swap.
5. **Resting orders (B):** ship the DRY_RUN simulation now, or wait until go-live when real resting
   orders exist? Simulating fills is the part most likely to manufacture fiction.
6. **Ignition `VOL_MULT`: ship 4.5× (mid-plateau) or 5.0× (peak)?** Both pass the pre-registered
   out-of-sample rule. Or hold for a 5th day of tape first?
7. **Should ignition join the live-structure bypass** per Marcos's own 7/26 rule — and if so, does
   that decision need its own out-of-sample split before touching settled doctrine?
8. **Does the kev25 verdict need re-opening?** Tuesday's runner A/B and scale-less tests returned
   null — but they never modeled the 3-min evaluation clock, which PN shows can miss a target
   entirely. Two of today's three big give-backs (PN, DGNX) were kev25 lanes, not hidden.

---

## D · CARRIED, UNRESOLVED

- **#18 fighting-the-tape arms** (VWAP slope / side-change / confirmation clock / leg-remaining),
  with the acceptance condition that ZYBT and BIYA must still pass.
- **Confirmation clock** (Marcos: *"entry in seconds but confirmation should be longer"*) — detection
  stays 10s, fire waits for a 1-min close. Today's five open-window losers are the labeled cases.
- **#11 bar-vs-stream divergence**, **#16 ORB break-vs-retest**, **#17 entry_session + PRE card**
  (built, awaiting a flat book), ferry scheduler trace, ticket-geometry ruling.
- **Instrumentation gap:** `ext_vwap` and `anchor` never reach the trade record — the two fields
  that define hidden entry quality are only in decision rows. One-line persistence fix.

---

## F · FRIDAY 7/31 — FRONT/BACK CLASSIFIER (Marcos: "to be tested and discussed Friday")

**⚠️ CORRECTION 7/30 (Marcos produced the transcript). EVERYTHING BELOW THE LINE IN THIS
SECTION'S ORIGINAL DRAFT WAS WRONG ON PROVENANCE.** I wrote that this idea "reached no file" and
"had to be re-derived from scratch." **FALSE.** It is fully ledgered — `RESULTS_LEDGER.md`
~L520-645, run by Fable on the nights of 7/28 and 7/29, Marcos-driven throughout. My grep missed
it because the ledger uses HH/HL, "streak", "defenses" and "maturity" — never the phrase
"higher highs, higher lows." A wording miss, not an absence. The G9 process item that cited this
as evidence is WITHDRAWN.

**WHAT IS ACTUALLY REGISTERED FOR FRIDAY — three frozen arms, no threshold moves, min 8
qualified OOS fires, scored on Wed+Thu fires:**
  A: 3-min streak>=6 AND defenses>=2   (13 fires, +$0.31/e)
  B: 3-min Kev triple >=2              (5 fires, +$10.28/e)
  C: 5-min streak>=3 AND defenses>=2   (26 fires, +$1.72/e — largest positive cohort)
  Winner takes the live front-side health gate. Stacking extra filters on top is FORBIDDEN in
  the grade (named as the p-hacking trap). 2-min and 4-min enter as ROBUSTNESS COLUMNS: the
  winning arm must show the SAME SIGN on neighbouring clocks or the win is suspect.

**THE ESTABLISHED SHAPE (Fable, 7/29, 136 fires):** quality rises with trend MATURITY. The
just-crossed reclaim is the WORST trade in the lane — streak 1 = −$10.88/e, the fresh-cross
chase — bending positive by streak 3 (−$2.20, 50% win) and going positive at streak 9+
(+$8.99/e). Multiple-comparisons warning pinned by Fable: the claim is THE SHAPE, not the cells.

**THE TIMEFRAME BAND-PASS (six clocks, all Marcos-driven):**
  1-min NULL/INVERTED (jitter) | 2/3/4/5-min ALIVE (plateau) | 10-min DEAD
Gate A's frozen definition is positive on 2, 3 AND 4-min with no retuning — parameter stability
across four clocks, which Fable called the strongest cheap anti-overfit evidence available.

**HOW THIS RECONCILES WITH MY 7/30 WORK — and why my structure run found nothing:**
My swing-structure attempt measured pivots on **10-SECOND bars**. The ledger already established
that **1-min is null/inverted and the signal lives at 3-5 min**. I ran the test an order of
magnitude BELOW the band where the effect exists. That, not the absence of an effect, is the
most likely reason it returned nothing — on top of the two coding defects (`wick_higher_low`
always 0; buckets capped at 4). **That run is void twice over and must not be cited.**
My independent 7/30 findings are CONSISTENT with the ledger's shape: 53.4% of fires dead on
arrival matches "the just-crossed reclaim is the worst trade in the lane."

**WHAT FRIDAY ACTUALLY RUNS (the registration is already frozen — do NOT redesign it):**
1. Score arms A/B/C on Wed+Thu fires using the SAVED script. **RECOVERY RISK:** the rows lived at
   `/tmp/frontside_rows.json` and `/tmp/frontside_{1,2,4,5,10}min_rows.json` — `/tmp` is volatile.
   FIRST ACTION FRIDAY: confirm those artifacts still exist; if gone, the metrics must be
   recomputed to the ledger's exact frozen definitions before any grading.
2. Robustness columns on 2-min and 4-min for whichever arm wins.
3. Grade = sign and $/entry of the qualified cohort at ~2x the discovery n. No threshold moves.
4. Any NEW feature (e.g. the wick-higher-low question, which remains genuinely untested) is a
   SEPARATE study run AFTER the head-to-head — stacking it into the grade is the forbidden move.
5. Pre-registered gates, same as every 7/30 study: TRAIN 07-13..24 / TEST 07-27..30 read once;
   >=10pp mover-rate spread at n>=40; monotone; DOLLAR test on TEST (mover-rate alone is not
   enough — `atr5` had the best separation of the day at 24.6pp and LOST $4.76/fire); TAIL test
   (>=70% of >=2R fires kept — the trap that killed the absolute floor).
5. Assert non-empty coverage per day. Two 7/30 runs produced silent-empty results; the chart-gate
   run reported n=29 where n=559 was real.

**Also for Friday, now CONFIRMED out of sample (rerun clean, TEST n=559, coverage 96-99%):**
the chart gate is INVERTED for reclaim. ALLOW -$10.34/fire keeping 27 of 175 movers; BLOCK
-$4.16/fire keeping 108. TRAIN -$10.53 / TEST -$10.20, tail kept 16.1% / 15.1%. Enabling the gate
for this lane would keep the losers and discard 85% of the tail. Marcos's 7/24 bypass call is
VINDICATED BY MEASUREMENT, and this is the third independent line of evidence (7/27 ballpark study
and the 7/30 band cut agree). Rows: `reclaim_chartgate_20260730.json`.

---

## G · OPUS'S DOCKET FOR FABLE (7/30 close, Marcos: "first make your list of what fable needs
## to review")

Ordered by what a ruling UNBLOCKS. Verification status is marked on every item — nothing here is
a recommendation, and every "refuted" below was refuted against pre-registered gates written
before the numbers existed.

### SHIP / KILL RULINGS

**G1 · zone_flip — KILL or SHADOW. (My pick for the easiest call on the board; open all day.)**
Era 6 trades / 1 win / **−$223.48**; today 0-for-2 / −$57.46 (−$28.73 per trade, worst on the
board). Arm window swept 8 cells (15-min → all-day): every cell loses, win rate pinned 31–36%
across 72→621 fires. Stop width, seq, and zone source all fail to separate. [VERIFIED —
`zoneflip_window_20260730.py`, rows in the matching .json]
The structural problem is not the setup, it is measurability: Z1 arms only 09:30–09:45, so the
lane fires ~3×/day and cannot accumulate evidence fast enough to study while it bleeds.

**G2 · reclaim — what it IS now, pending §F.**
Bimodal, and the tail is real: 53.4% of 784 era fires never moved +0.5R; 21.6% reached +2R;
10.2% reached 5R+. Payoff ratio 1.33 ⇒ breakeven needs **42.9%** win rate; delivered **23.1%**.
Median loser **−1.54R** (54.4% of losers worse than −1.5R). [VERIFIED — `reclaim_anatomy`]
Everything tested and refuted as a fix today: 5 grammar constants, arm window, 13 tape-context
features, absolute per-bar dollar floor, fire-bar volume re-check, chart gate.
**RULING NEEDED:** does reclaim keep converting live at ≈−$6/fire while §F is built, or shadow?

**G3 · CLOSE the chart-gate question for the tape lanes.**
Bypass replayed through the REAL `_chart_break_gate` (not a hand copy — that error voided the
7/29 study). Clean rerun, TEST n=559, coverage 96–99%:
  ALLOW −$10.34/fire keeping **27 of 175** movers · BLOCK −$4.16 keeping **108**
  TRAIN −$10.53 / TEST −$10.20; tail kept 16.1% / 15.1% — stable across both blocks.
[VERIFIED — `reclaim_chartgate_20260730.py`] Marcos's 7/24 bypass call is **vindicated by
measurement**; third independent agreement (7/27 ballpark study, 7/30 band cut). Asked for a
formal close so it stops being re-litigated.

### DESIGN RULINGS

**G4 · §F front/back classifier — tonight or Friday.** Design already ruled by Fable in-session
(6-feature vocabulary, singles-then-pairs, dollar + tail gates). Un-park condition **MET** (14 era
days vs the 6/29 "needs trending days" park). See §F. [VERIFIED: `classify_side` absent repo-wide]

**G5 · Fire-bar volume re-check — shelve, or fold into §F?**
Refuted as a fix (never crosses zero) BUT it is the only mechanism today that improves the mean in
**both** halves while keeping **70%** of the tail (TEST −$6.28 → −$4.31). [VERIFIED —
`reclaim_firevol_20260730.py`] The gap it closes is real and structural: the 2× participation test
fires in PHASE 1 (the cross) and is **never re-checked**; entry lands up to 90s later on whatever
bar happens to close above the wick. All five of today's reclaim losers fired BELOW 2×
(0.1×, 0.8×, 1.8×, 1.5×, 0.1×) — YHC bought a **150-share / $296** bar; SKYQ **142 shares / $670**.

**G6 · Slippage-vs-width reframes Friday's band question.**
The only relationship that survived every test today, monotone across 5 buckets:
  w 0–2%: slip **1.11R**, median loser −1.97R  →  w 6%+: slip **0.21R**, median loser −1.21R
Calibrated slippage (1.477% of entry) eats **0.67R median** of every reclaim stop; on **27.2%** of
fires it exceeds the entire stop distance. Median actual risk on the lane is **$7.45**, not $30.
[VERIFIED — `reclaim_anatomy`] ⇒ Friday's 5%-vs-6% shadow-band grade is a **survivability floor**
question, not setup quality. Recommend Fable frame it that way in the grade.

### LIVE-MONEY DEFECT, UNDIAGNOSED — I rank this FIRST

**G7 · Blow-through stops.** Today's realized stop-outs: −1.81R, −1.57R, −1.41R, −1.39R, −1.33R,
−1.25R, −1.18R, −1.14R, −1.10R. The TRUE INTRABAR STOP shipped 7/27 **specifically to end this**.
[VERIFIED that it is happening — dashboard + trade store. **UNVERIFIED why.**]
Three candidate causes, three different fixes, no diagnosis yet: (a) intrabar stop not firing,
(b) firing but filling badly, (c) stops so tight that no fill can hit them cleanly (G6 says this is
at least a contributor). **The only item on this docket bleeding real money right now.**
Proposed check: pull the 10s tape at each of today's 9 blow-through exits and establish which.

### PROCESS — Fable ruling requested

**G8 · Make coverage + non-degeneracy asserts MANDATORY in every killtest.** Two of my runs today
produced silent-empty results that would have become ledger entries: the chart-gate run reported
**n=29 where n=559 was real** (harness.bars swallows fetch errors and caches []), and
`reclaim_structure_20260730.py` silently zeroed its key feature (`wick_higher_low` — the anatomy
JSON never recorded `wick_low`) and printed a **fake "FAILURE CONDITION MET"**. Both caught and
VOIDED, not reported. The asserts are now written into §F; asking that they become standard.

**G9 · WITHDRAWN — I was wrong.** I claimed the front/back work "reached no file" and had to be
re-derived. It is fully ledgered (`RESULTS_LEDGER.md` ~L520-645, Fable 7/28-7/29) with three
frozen Friday arms. My grep missed it on WORDING (the ledger says HH/HL, "streak", "defenses",
"maturity" — never "higher highs, higher lows"). Marcos produced the transcript that corrected me.
The real lesson, and the one worth a rule: **search the ledger by MECHANISM, not by the phrase the
user just used.** Also — my 7/30 structure run measured 10-SECOND pivots when the ledger had
already established the signal lives at 3-5 min and 1-min is null; it was testing an order of
magnitude below the band. Void twice over.
**G9' (replacement) · Recovery risk:** the frozen Friday artifacts live in `/tmp`
(`frontside_rows.json`, `frontside_{1,2,4,5,10}min_rows.json`). `/tmp` is volatile. Recommend
Fable's first Friday action = confirm they exist, and that killtest rows never again land in
`/tmp` rather than `data/killtests/`.

### CARRIED, UNCHANGED
#11 bar-vs-stream divergence · #16 ORB break-vs-retest · #17 entry_session + PRE card (BUILT,
awaiting a flat book) · #18 fighting-the-tape · ferry scheduler trace · ticket-geometry ruling ·
**dashboard secret `marcos2026` → real secret BEFORE go-live** · the 8 questions in §C.

### MY RECOMMENDED ORDER
**G7** (real money, no diagnosis) → **G1** (easy kill) → **G3** (close it) → **G4** (the one live
hypothesis left) → the rest.

### STATE AT WRITING
Nothing from this review is implemented or deployed. `git diff` = `screener_app.py` only (the PRE
card, #17). `marcos_trading_bot.py` UNTOUCHED — every study today patched the source IN MEMORY and
printed its substitutions at run time for audit. 7/30 RTH is final (checked 18:39 EDT); the
after-hours tape was still accumulating, so 7/30 is cut at 16:00 in every study that includes it.

---

## H · FIRE-AGE LATENCY — MEASURED AND PROPOSED CLOSED (7/31 AM, Marcos: "add this to the list")

**QUESTION:** `fire_age_s` on converted curl fires runs 60–114s (KUST 113.8s this morning). Yesterday's
G7 autopsy found the exit-side twin (WICK-MISS: 5 stops 1.3–58 min late). Is entry latency costing us,
and does it justify architectural work?

**WHAT `fire_age_s` MEASURES** (:6126): `time.time() - k`, where k = the 10s BUCKET EPOCH = when the
fire bar OPENED. So ~10s of it is structural (the bar must close before it can be evaluated) and the
metric is ~10s pessimistic by construction. Guard = `CURL_FIRE_MAX_AGE_SECS`, raised 90→240 by Fable
on 7/29 (the old 90s ceiling silently suppressed 17 sparse premarket fires).

**MEASUREMENT 1 — where the latency lives (n=76 fires, 7/27–7/31):**
    median 58.8s · mean 115.9s · min 13.1s · max 2108.7s
    0-15s 2.6% | 15-30s 17.1% | 30-60s 32.9% | 60-90s 17.1% | 90-120s 7.9% | 120+s 22.4%
    by lane (median): reclaim 60.0s (n=41) · hidden 56.0s (n=21) · zone_flip 35.4s (n=6) · dip_rip 188.4s (n=8)
**The 13.1s MINIMUM is the diagnostic:** bar closed, reached the feed, and converted in ~3s. The feed
is NOT the bottleneck. The 13s→2108s spread is SCAN-CYCLE position — curl fires convert inside the
ticker's own turn in a 100–160-name loop. dip_rip's 188s median fits (rarest lane, least likely to be
front-of-queue). VERDICT: scan-cycle latency, not feed latency.

**MEASUREMENT 2 — does it cost money? (n=68 conversions carrying BOTH age and drift):**
    overall drift: median +0.00% · mean +0.05%   (positive = we paid UP vs the fire price)
    0-30s   n=14  median +0.00%  mean −0.20%   |  60-120s  n=19  median +0.00%  mean −0.12%
    30-60s  n=23  median +0.00%  mean +0.01%   |  120s+    n=12  median +0.00%  mean +0.70%
    corr(age, drift) = +0.230
**Median drift is ZERO in EVERY age bucket.** Waiting 90s is as often a discount as a tax (CYCU today:
81.5s late, filled 1.4% BELOW the fire price). The weak +0.23 correlation is carried almost entirely
by the n=12 120s+ cell.

**OPUS RECOMMENDATION — CLOSE IT, DO NOT BUILD THE FAST LANE.**
The architectural fix (a dedicated concurrent loop stepping only the 10s machines, which need just 10s
bars + VWAP — not the 3-min EMAs/room/daily the chart lanes require) is the LARGEST-RISK change
available: new threading in the trade path, three weeks from go-live, to recover a cost measured at
≈$0. Fails its own cost/benefit test. Compare the actual bleed: friction −$1,650 vs gross strategy
−$586 (dashboard, era) — friction is ~3× the strategy loss and fire-age drift is a rounding error
beside it.

**THE ONE NARROW ITEM (free, config-only):** the 120s+ cell is the only one showing cost (+0.70%), and
`CURL_FIRE_MAX_AGE_SECS=240` was set to fix a SUPPRESSION problem, never tuned against OUTCOMES. ASK
FOR FRIDAY: add one cut — do 120s+ conversions underperform in dollars? YES ⇒ lower the ceiling toward
120s (config change, no architecture). NO ⇒ fire age is closed permanently.

**CAVEATS HELD:** n=68 for the drift test and n=12 in the decisive tail cell; `k`=bar-open makes the
metric ~10s pessimistic; premarket sparse tape is over-represented in the long ages. This closes the
question at CURRENT scale — if the watch list grows materially, scan-cycle position gets worse and the
measurement must be re-run, not assumed.

**FOR FABLE:** ruling requested on (a) close fire-age as a non-issue, (b) the Friday 120s+ dollar cut,
(c) confirm the fast-lane rebuild stays OFF the runway (it is currently not on any docket).

---

## I · RE-ENTRY & ADDS — THE MISSING MECHANIC (7/31, Marcos: "Kev frequently goes back to the
## well. If the setup is good, who cares what ticker it is. The quality of setup should always
## decide." + "kev adds frequently even in the same leg")

**THE DOCTRINE (Marcos's ruling, corpus-backed):** entry eligibility should be decided by SETUP
QUALITY, not by ticker identity or a per-name counter. Kev's own words: *"Once front side, KEEP
ATTACKING it — pullback after pullback, re-enter relentlessly"* (system spec §5). And the money
line: *"The BIG money often comes from the RE-ENTRY, not the first leg"* (`project_kev_system_spec.md:116`).

### I1 · TWO SEPARATE GAPS — do not conflate them
**GAP A — RE-ENTRY IS CAPPED.** Verified counts, 7/30 NUWE (the same name we traded 3× for −$22.83):
Kev took **at least SIX entries on one ticker in one day** — 4.97 (premkt wick), 5.60 (attempted,
limit skipped), 5.82, 5.44, 5.88, 5.67, plus runners at 6.13. OUR LIMITS on that same name:
`HIDDEN_NAME_CAP=2`/day, `HIDDEN_DAILY_CAP=3`/day, and the curl lanes allow **ONE slot per name
per SESSION** (`_curl_rth_slot`). Six versus one-or-two is not a tuning delta — it is a different
method. LIVE COST TODAY (MGRX 7/31): after our 09:32 entry at 0.79 was stopped at 0.65, hidden
fired FIVE more times while the name ran 0.75 -> 0.90 — 09:46 `hidden_capped` 0.7472 · 09:53
`hidden_ext_reject` 0.7609 · 09:55 `hidden_capped` 0.7970 · 09:58 `hidden_capped` 0.7825 · 10:00
`hidden_capped` 0.8251. FOUR of the five were the DAILY CAP — not a quality judgment. The lane was
out of tickets by 09:46 AM.

**GAP B — THERE IS NO ADD PATH AT ALL. [VERIFIED: zero matches repo-wide for scale_in / pyramid /
add_to / re_add]** Our position sizing is ONE-SHOT: we enter once and thereafter can only SELL.
Kev's spec, in our own corpus, never built: *"Adds/pyramiding mechanic: trim some into strength,
then RE-ADD on the pullback to the demand level / 20 EMA (bottoming tail)"* (`spec:118`). He did it
live on NUWE 7/30: trimmed into 6.00, then *"I grabbed runners at 613 for the squeeze over 630."*
CONSEQUENCE: a shakeout is TERMINAL for us (stop + cap + no add all point the same way) while for
him it is a re-entry opportunity. It also reframes §K6 sizing: his *"greatest expected value, most
size"* is not only an entry-time decision — SIZE ACCUMULATES THROUGH THE MOVE as the setup keeps
proving itself. Our `_scaled_risk` picks a number once and never revisits it.

### I2 · THE TENSION THAT MUST BE RESOLVED BEFORE ANY CAP CHANGE
Measured evidence points BOTH ways and both are real:
  - FOR caps: ignition 7/27-7/30 — **606 raw fires = −$1,759** vs **first-fire-only = +$129** (§E2).
    Repeat conversions destroyed value in aggregate.
  - AGAINST caps: Kev's 6-entry NUWE day; today's MGRX lockout; the corpus doctrine above.
**THE LIKELY RECONCILIATION (hypothesis, untested):** Kev's repeats are each a NEW SETUP — fresh
pullback, fresh wick, fresh defended level, risk re-defined off THAT candle's low. Our repeats may
be the SAME setup re-firing as the machine re-arms on unchanged structure. Nobody has ever labelled
them. "Attacking the front side" and "a detector stuck in a loop" produce identical row counts.

### I3 · THE TEST THAT SHOULD PRECEDE ANY BUILD (cheap, archived data, no behavior change)
Label EVERY repeat fire in the era as **NEW-SETUP** (materially different price / fresh wick /
different level or MA held / structure changed since the prior fire) vs **RE-ARM** (same structure,
same level, minutes apart). Price both cohorts through the honest harness WITH today's shipped
quality gates applied (ext gate, 4.5x convert, fire-bar volume) — the caps were set when the lanes
had NO selection filters, so they may now be paying twice for the same protection.
  - If NEW-SETUP repeats pay and RE-ARMS bleed ⇒ **the fix is not a bigger number. It is a
    STRUCTURE-CHANGE REQUIREMENT**: a repeat converts only when the setup is genuinely new. That is
    Kev's rule expressed mechanically, and it satisfies Marcos's doctrine exactly (quality decides).
  - If both bleed ⇒ caps stay, and the MGRX case is filed as variance.
Standard gates apply: TRAIN 07-13..24 / TEST 07-27..31 read once, dollar test, tail test,
coverage + non-degeneracy asserts (§G8 law).

### I4 · WHAT AN ADD MECHANIC WOULD ACTUALLY REQUIRE (scope honesty for the ruling)
This is the LARGEST architectural change on any docket. The monitor currently assumes a position
that only SHRINKS. Adds break that assumption in five places: (1) average entry price and therefore
R itself; (2) the blended stop — Kev risks each tranche off ITS OWN candle low, so either we track
per-tranche risk or accept a blended stop that is wrong for both; (3) the resting-order rungs
shipped 7/30, which were sized against the ORIGINAL share count and would need re-scaffolding on
every add; (4) the volume guard and notional cap, which were computed once at entry; (5) recovery /
reconciliation after a restart, which currently rebuilds a single-entry position.
AGAINST doing it now: 15 trading days to 8/20; nine switches shipped 7/30 and ungraded; it touches
the live trade path at its most delicate point. FOR doing it: it is the mechanic behind most of
Kev's money, it is fully specified in our corpus, and every day without it means shakeouts are
terminal.

**RULINGS REQUESTED:** (a) run the I3 new-setup-vs-re-arm study Friday; (b) is the add mechanic W2
work, W3, or explicitly POST-LAUNCH; (c) interim — does anything change about the caps BEFORE I3
returns, or do they hold as-is; (d) if adds are post-launch, should re-entry (Gap A) ship first as
the cheaper half, since it needs no position-management changes at all.

---

## J · PINNED SPECIMEN — MGRX 7/31: SAME LANE, SAME NAME, SAME DAY, OPPOSITE OUTCOMES
### (Marcos: "pin that pairing")

The cleanest natural experiment we have on LEVEL PROXIMITY. Both trades are `vwap_reclaim`, both
on MGRX, 105 minutes apart, both under the SAME shipped code (7/30 change-set + RECLAIM_FIREVOL).
The only material difference is WHERE the entry sat relative to Kev's marked level.

**KEV'S LEVEL (his 7/31 09:36 morning update, video SBO7Zueg-mI):** *"If price can break trend back
to the upside, buyers step in back over **70 cents**. We look for pullbacks to confirm some higher
lows over VWAP, **over 60 cents**. Range back to a dollar."* (Merged to the sheet `src=kev` at
~09:38 — AFTER trade B fired, so it influenced neither.)

| | **A — 07:46:52 PRE** | **B — 09:32:41 RTH** |
|---|---|---|
| entry | **$0.56** | **$0.79** |
| vs Kev's 0.70 break | **−20%** (at his 0.60 confirm) | **+13% ABOVE** |
| stop | 0.546 | 0.651 |
| **stop width** | **3.09%** | **17.59%** |
| shares / size | 887 / $499.74 | 215 / $169.85 |
| partials | **2 banked** (443@0.5808, 222@0.5982) | **NONE** |
| exit | trailing stop 0.60 | **stop loss 0.65** |
| **P&L** | **+$23.31 (+4.67%)** | **−$30.16 (−17.76%, −1.01R)** |

**WHAT THIS ISOLATES (and what it does NOT):**
- NOT the detector — same lane, same grammar, same day.
- NOT participation — the new fire-bar gate REFUSED an earlier MGRX fire at 06:44 (volmult 1.49)
  and PASSED both A and B. Volume was real on the loser.
- NOT stop width — B had a **17.59%** stop, nearly 6× A's, and still got taken. Yesterday's lesson
  was tight stops get knifed; this is the inverse and it still failed. **Width was not the defect.**
- NOT the exit ladder — A banked twice on a 4.67% move; B never reached tier 1.
- **WHAT'S LEFT: entry price relative to the marked level.** A entered at Kev's confirm zone and
  compounded; B chased 13% above his break, two minutes after the bell, and round-tripped.

**CORROBORATION ALREADY ON FILE:** §G3's chart-gate replay (OOS n=559) found entries ABOVE the
marked break are reclaim's worst cohort (ALLOW −$10.34/fire, keeping only 27 of 175 movers) while
BELOW-level entries hold 108 of them at −$4.16. The 7/30 band cut found four consecutive negative
cells above the level (n=71). The 7/27 ballpark study found inside-±10% wins 54% vs 29% outside.
**MGRX is the same finding at n=2, but with every other variable held constant** — which is what
makes it worth pinning rather than averaging away.

**THE SHAKEOUT DETAIL (why B is not merely 'a loss'):** B's stop at 0.65 was taken on the 09:41
flush that bottomed at **0.604 with a bottoming wick on VWAP** — i.e. the stop-out price WAS Kev's
stated entry (*"higher lows over VWAP, over 60 cents"*). We supplied the liquidity for the setup he
described. Then four `hidden_capped` blocks (§I1) locked the lane out while MGRX ran 0.75 → 0.90.

**FOR FRIDAY:** this pairing is the motivating case for the ±10% ballpark dollar-grade (already
registered) — recommend the grade report the ABOVE-level cohort SEPARATELY rather than folding it
into a single band statistic, since every study to date says the sign flips at the level.
