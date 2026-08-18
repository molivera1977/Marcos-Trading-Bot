# KEVSEQ RECONCILIATION — 8/16 "+$340" vs 8/17 "−$3.54" (8/17/26)

**VERDICT QUALIFIER (LIMITS, added 2026-08-17):** IN-SAMPLE across two single days, on a SUPERSET linkage. It is also on the EG2 KNOWN-CONTAMINATED list — it consumes the fires of three front-side-free studies and inherits their contamination. The drift-vs-cohort attribution is a mechanism story that reproduces; the dollar split between the two is not a measured quantity. kevseq harness parity is 30.4%, far below the 90% floor (data/killtests/harness_parity.json).

**Analysis only. Nothing shipped, nothing deployed, no bot edits.**
Script `data/killtests/kevseq_reconciliation_20260817.py` · run log `_run.txt` · JSON `_out.json`.
Engine imported **unchanged** from `sunday_afternoon_studies_20260816` (→ G → F → C → B → E) —
the same engine `entry_drift_20260817.py` used, so both studies are now graded by one exit model.
Historian: run 2026-08-17, `date` cited in transcript.

Marcos caught a contradiction between two numbers I reported and he was right to. Claude reported
(B) as "kevseq is net-negative" without reconciling against (A). This document is the reconciliation.

---

## VERDICT (one word first): **BOTH — and they own different things.**

> **DRIFT owns the SIGN. COHORT owns the SIZE.**
>
> * The entry-drift defect is 100% of the sign flip. On the identical universe fire-set and the
>   identical exit model, entering at the detector's **fire price** gives **+$2.46/tr MINE and
>   +$3.23/tr HOLD-OUT**; entering at the **drifted** price gives **−$3.54 / −$2.46**. Study (B)
>   never ran the clean-spec arm, so it reported a broken implementation as if it were the lane.
>   **kevseq's original finding — that the sequence clause is worth trading — survives; the
>   implementation broke it.**
> * Cohort selection is ~93% of the *magnitude*. On study (A)'s own fast-chart name-days the same
>   clean arm is **+$13.52/tr**; on the non-fast-chart complement it is **+$0.96/tr**, and
>   **−$2.81/tr on the non-fast-chart HOLD-OUT**. The "+$340-class" number is a runner-cohort
>   number. The edge is real but it is roughly an order of magnitude smaller off the pre-selected
>   names, and it does not survive out-of-sample there at all.
> * **Physically realizable version:** ARM-F3 (limit at fire+0.5%, unfilled = no trade) is the
>   only arm that never assumes a fill the tape did not offer. It is **positive only on the
>   fast-chart cohort** (+$12.77 MINE / +$10.58 HOLD-OUT) and **slightly negative on the universe**
>   (−$0.56 / −$0.73). So: fix the drift AND keep the lane on runner-grade names, or it is flat.

Neither prior verdict was right on its own. (A) was not wrong about direction, it was reported at
a magnitude only its cohort supports. (B) was not wrong about the numbers it ran, it was wrong to
call the lane negative when the arm that isolates the defect was never graded.

---

## 1. DIFFERENCES TABLE — the two studies were never measuring the same thing

| dimension | STUDY (A) — rosetta / fast-chart 8/16 | STUDY (B) — entry-drift 8/17 | comparable? |
|---|---|---|---|
| **what fired** | Kev-**A/B/C** fast-chart detectors (confluence wick / level-hold / halt double-bottom), then **post-hoc filtered** by the sequence clause | the **live `kevseq` detector** (B→H/W + burst + fresh + leg cap), one detector | **NO — different detectors.** kevseq was *inspired by* A's clause; it is not A's arm |
| **cohort** | 197–198 SIP tick name-days: crown roster 8/5–8/14 + Kev-pick days + top-30 rocket name-days | universe `bars10s` cache, **736 graded name-days**, 738 files | **NO** |
| **cohort character** | **pre-selected runners** (crowns + rockets + names Kev himself named) | everything the scanner ever cached | **NO — this is the selection term** |
| **name-day overlap** | — | — | **109 of A's 197 name-days (55%) exist in B's cache; 15% of B's cohort** |
| **date range** | 39 dates, 2026-05-20 .. 08-14 | 63 dates, 2026-05-18 .. 08-17; all 39 of A's dates are inside B's | dates overlap; names do not |
| **OOS split** | **none** — A says so itself: "light in-sample, no OOS wall" | MINE 05-18..07-21 / HOLD-OUT 07-22..08-14, frozen | **NO** |
| **arm selection** | ~8 clauses reported, thresholds taken from Kev's own 23 fills, best ones highlighted → multiple-comparison exposure | 4 pre-registered mechanisms + grid, failure condition written first | **NO** |
| **N** | SEQ arm **79** fires (det-B subset **59**) over 198 nd = **0.30–0.40 fires/nd** | **1,288** fires over 736 nd = **1.75 fires/nd** | **NO — A's arm is ~5× more selective** |
| **entry price** | **the detector's fire price** (+1% chase) — the clean spec | **the drifted live-quote proxy** = fill-bar close (+1% chase) | **NO — this is the drift term** |
| **stop** | structural (level / wick low) | structural (same) | yes |
| **exit model** | four exits reported: KEV-native, E3, E4W, F-control. The **+$447 headline is KEV-native**; its E3 was **−$31**. The **+$340 is E3 on the det-B subset only** | **E3 live-parity only** | partial — the headline cited most often (+$447) is a *different exit* from B's |
| **clip / slippage** | $500, +1% entry chase, −0.5% market exits, stop-first | identical ($500, +1%, −0.5%, stop-first) | **yes** |
| **gate stack** | Kev's context gates applied (mover ≥+20%, front side, room, topping-cluster, leg ration) | **gate stack NOT applied** — `front_side`/`top3`/`blue_sky` are not reconstructible from the 10s cache, replaced by day-gain floor alone (B discloses this: "superset cohort") | **NO — B is a looser fire-set by construction** |
| **hours** | RTH 09:30–15:30, flatten 15:45 | same | yes |

**Does the differences table alone explain the gap? No — it explains *most of the magnitude* but
not the sign.** Two of these rows are load-bearing and separable, so we tested them.

---

## 2. THE COMMON-BASIS RE-RUN — one fire-set, one exit model, three arms

One cohort definition (the live kevseq detector's fires from the universe cache), one exit model
(**E3 live-parity, $500, +1% entry chase, −0.5% market exit, stop-first**), three arms:

* **ARM-SPEC** — entry at the detector's intended **fire price**, structural stop. *What study (A) assumed.*
* **ARM-LIVE** — entry at the **drifted** price, same structural stop. *What the code actually did.*
* **ARM-F3** — resting **limit at fire_px × 1.005**; fill only when a bar's own **low** reached it; unfilled = no trade.

**Drift source (stated, per the mandate):** the replay uses the **modelled** drift — the fill-bar
close as the live-quote proxy — because the archive carries only **13 stamped kevseq fires**
(all 8/17), far too few to grade. Modelled drift: **median +0.76%, p90 +4.13%, max +70.68%**
vs live-stamped **+5.02% / +7.09% / +28.87%**. The model's median is **6.6× smaller** than live,
so **every SPEC-vs-LIVE gap below is a LOWER BOUND on the real drift damage.**

### THE FOUR-CELL GRID (six cells reported; the four mandated are the first two blocks)

| cohort × period | arm | N | total | $/tr | win | worst |
|---|---|---|---|---|---|---|
| **UNIVERSE · MINE** (05-18..07-21) | ARM-SPEC | 918 | **$+2,255.50** | **$+2.46** | 36% | $−155.38 |
| | ARM-LIVE | 917 | $−3,244.94 | $−3.54 | 31% | $−184.55 |
| | ARM-F3 | 897 | $−504.92 | $−0.56 | 34% | $−114.90 |
| **UNIVERSE · HOLD-OUT** (07-22..08-14) | ARM-SPEC | 366 | **$+1,181.73** | **$+3.23** | 40% | $−83.79 |
| | ARM-LIVE | 365 | $−899.60 | $−2.46 | 37% | $−110.80 |
| | ARM-F3 | 356 | $−260.78 | $−0.73 | 38% | $−85.86 |
| **FAST-CHART COHORT · MINE** | ARM-SPEC | 52 | **$+713.34** | **$+13.72** | 52% | $−155.38 |
| | ARM-LIVE | 52 | $+252.68 | $+4.86 | 40% | $−184.55 |
| | ARM-F3 | 49 | $+625.49 | $+12.77 | 51% | $−114.90 |
| **FAST-CHART COHORT · HOLD-OUT** | ARM-SPEC | 136 | **$+1,828.50** | **$+13.44** | 48% | $−69.00 |
| | ARM-LIVE | 136 | $+701.86 | $+5.16 | 43% | $−110.80 |
| | ARM-F3 | 132 | $+1,396.10 | $+10.58 | 46% | $−71.14 |
| **FAST-CHART COHORT · ALL** | ARM-SPEC | 188 | $+2,541.84 | $+13.52 | 49% | $−155.38 |
| | ARM-LIVE | 188 | $+954.54 | $+5.08 | 43% | $−184.55 |
| | ARM-F3 | 181 | $+2,021.59 | $+11.17 | 48% | $−114.90 |

### THE SELECTION CONTROL — same arms, **non**-fast-chart name-days

| cohort × period | arm | N | total | $/tr | win | worst |
|---|---|---|---|---|---|---|
| **NON-FAST-CHART · MINE** | ARM-SPEC | 866 | $+1,542.15 | **$+1.78** | 35% | $−105.76 |
| | ARM-LIVE | 865 | $−3,497.62 | $−4.04 | 30% | $−111.13 |
| | ARM-F3 | 848 | $−1,130.41 | $−1.33 | 33% | $−107.72 |
| **NON-FAST-CHART · HOLD-OUT** | ARM-SPEC | 230 | $−646.77 | **$−2.81** | 36% | $−83.79 |
| | ARM-LIVE | 229 | $−1,601.46 | $−6.99 | 34% | $−107.92 |
| | ARM-F3 | 224 | $−1,656.88 | $−7.40 | 34% | $−85.86 |
| **NON-FAST-CHART · ALL** | ARM-SPEC | 1,100 | $+1,050.60 | $+0.96 | 35% | $−105.76 |
| | ARM-LIVE | 1,098 | $−4,816.67 | $−4.39 | 31% | $−111.13 |
| | ARM-F3 | 1,076 | $−2,637.32 | $−2.45 | 33% | $−107.72 |

Fire density is **not** the difference: fast-chart 1.72 fires/nd vs non-fast-chart 1.75 fires/nd.
The lane fires at the same rate on both; the fires are simply worth more on runner-grade names.
(Study A's own SEQ arm was far more selective still: 0.40 fires/nd — an additional filter this
reconciliation does **not** credit kevseq with.)

### FILLABILITY CHECK (Sim Integrity — is ARM-SPEC a fill that existed?)

ARM-SPEC assumes a fill at `fire_px × 1.01` on a bar that traded *through* the trigger. On a
violent fill bar (STFS 7/28 closed +70.7% above the fire price) that fill is fantasy. Restricting
ARM-SPEC to fires whose **fill bar's own low ≤ fire_px** (i.e. the tape genuinely offered it):

| cell | ARM-SPEC all | ARM-SPEC fillable-only |
|---|---|---|
| UNIVERSE MINE | $+2.46 (N=918) | **$+1.63** (N=890, 97%) |
| UNIVERSE HOLD-OUT | $+3.23 (N=366) | **$+0.84** (N=351, 96%) |
| FAST-CHART MINE | $+13.72 (N=52) | **$+14.63** (N=49, 94%) |
| FAST-CHART HOLD-OUT | $+13.44 (N=136) | **$+11.70** (N=129, 95%) |
| NON-FC MINE | $+1.78 | $+0.87 |
| NON-FC HOLD-OUT | $−2.81 | **$−5.46** |

ARM-SPEC is optimistic by **$0.8–2.4/tr on the universe** (the ~4% unfillable fires are the
runaway winners) and **not** optimistic on the fast-chart cohort. The conclusions hold under the
stricter measure: universe SPEC still positive on both halves, non-FC HOLD-OUT still negative.

### HAND-TRACES (three named fires, both arms, same bars)

| fire | fire px | drifted entry | drift | stop | SPEC pnl | LIVE pnl | exit |
|---|---|---|---|---|---|---|---|
| **STFS 2026-07-28** | $3.99 | $6.81 | +70.7% | $3.85 | **+$179.31** | +$11.88 | both TRAIL 16:47:50 @6.5172 |
| **HUIZ 2026-08-07** | $1.96 | $2.38 | +21.4% | $1.7999 | **+$62.75** | +$11.97 | both TRAIL 17:07:50 @2.2786 |
| **VSA 2026-08-07** | $5.28 | $6.19 | +17.2% | $4.96 | **+$93.12** | +$46.35 | both TRAIL 16:47:50 @6.7859 |

Same bars, same exit bar, same exit price — **only the entry differs**, and on STFS the drift ate
$167.43 of a $179 trade. Note the direction: on *winners* the drift caps the upside; on *losers*
it widens realized risk (worst trade LIVE $−184.55 vs SPEC $−155.38, and win% falls 36%→31% MINE,
40%→37% HOLD-OUT). The defect costs on both tails.

---

## 3. THE FOUR DIRECT ANSWERS

**Q1 — Does ARM-SPEC reproduce study (A)'s +$340-class result on (A)'s own cohort?**
**YES, comfortably.** On the 109 of A's name-days present in the cache: ARM-SPEC **N=188,
$+2,541.84 total, +$13.52/tr, 49% win** — and on the frozen HOLD-OUT half alone **N=136,
$+1,828.50, +$13.44/tr**. A's cited cell was N=59 E3 $+340 = $+5.76/tr. Same sign, same order,
larger. **Study (A) does not have a reproduction problem.**

**Q2 — Is the SPEC-vs-LIVE gap ≈ the drift damage? Quantify.**
**YES, and it is the whole sign flip.** SPEC − LIVE = **+$6.00/tr on MINE** ($+2.46 vs $−3.54,
+$5,500 total over 918 fires) and **+$5.69/tr on HOLD-OUT** ($+3.23 vs $−2.46, +$2,081 over 366).
That gap is larger than the entire absolute value of B's headline, i.e. drift accounts for
**169% of MINE's** and **231% of HOLD-OUT's** reported deficit — it does not merely erode the
edge, it inverts it. And this is measured on **modelled** drift with a median 6.6× smaller than
the live-stamped drift, so the real damage is larger still.

**Q3 — On the common basis, is kevseq positive or negative, and where?**
**Positive at the clean spec on every universe cell; positive and large on runner names; negative
off them out-of-sample; and only marginally negative as physically realizable at universe scale.**
Precisely: ARM-SPEC **+$2.46 MINE / +$3.23 HOLD-OUT** (universe, both halves positive, N=918/366);
ARM-SPEC **+$13.72 / +$13.44** on the fast-chart cohort; ARM-SPEC **+$1.78 MINE but −$2.81
HOLD-OUT** on non-fast-chart names. ARM-F3, the only arm that never assumes an unoffered fill:
**−$0.56 / −$0.73 universe, +$12.77 / +$10.58 fast-chart.**

**Q4 — Is the +$340 explained by cohort selection rather than edge?**
**Partly — cohort explains the SIZE, not the existence.** Graded on the same arms, the
non-fast-chart control keeps only **$+0.96/tr** of the fast-chart cohort's **$+13.52/tr** —
**~93% of the per-trade magnitude is cohort**, and the residual $0.96 does not survive the split
(MINE +$1.78, HOLD-OUT **−$2.81**). So the fast-chart headline is genuinely selection-inflated;
but the edge is not *created* by selection, because the universe-wide ARM-SPEC is positive on
**both** halves of the OOS split at N=918/366. Read it as: **a real but small effect, concentrated
almost entirely in runner-grade names.**

---

## 4. WHAT THIS CORRECTS IN THE RECORD

* **`entry_drift_20260817.md` STEP 3 / SPEC-TENSION #1 is wrong as written.** It says "every arm
  on this replay is still net-negative" and "the lane loses money on this cohort, on every arm."
  It never graded entry-at-fire-price. On the identical fire-set that arm is **+$2.46/+$3.23**.
  The correct statement is: *every arm the study ran was negative; the arm it did not run — the
  detector's own spec — is positive on both halves.*
* **The F3 ship posture is unchanged and still correct.** F3 remains the honest buildable arm and
  it remains sub-zero on the universe superset. Nothing in this reconciliation authorizes turning
  a switch on; that is Marcos's call, priced
  (`feedback_auditor_cannot_authorize_behavior`, `feedback_no_lesser_fix`).
* **What it *does* change is the ranking of the open questions.** "Should kevseq convert at all?"
  is no longer the same question as "is the drift fix worth it." The drift fix is worth
  **~$6/trade** — bigger than every other lever measured on this lane — and the surviving open
  question is a **selection** question: kevseq off runner-grade names is a coin-flip that fails
  out-of-sample, and the fast-chart cohort's +$13/tr is not a universe number.

## 5. CAVEATS — read before believing any figure above

1. **Gate stack absent.** B's cohort is a superset: `front_side`, `top3`, `blue_sky` are not
   reconstructible from the 10s cache and none of the downstream gate stack is applied. Absolute
   levels are not a forecast of live P&L. **Relative arm comparison — the point of this
   document — is unaffected**, since all three arms see the identical fire-set.
2. **Modelled drift, not real drift.** 13 stamped live fires is not a distribution. The fill-bar
   close understates live drift 6.6× at the median. All SPEC-vs-LIVE gaps are lower bounds. The
   8/17 stamps start the real distribution tonight.
3. **ARM-SPEC is a spec, not an order type.** No live order guarantees a fill at the trigger. The
   fillability table bounds the optimism; F3 is the buildable proxy, and under
   `ENTRY_LIMIT_BUFFER = 0.01` the broker limit sits at `capped × 1.01` — the lane-aware buffer
   flagged in `entry_drift_20260817.md` §3 is still owed before real money.
4. **The fast-chart cohort is only 55% intersected** (109 of 197 name-days in the cache); the
   fast-chart cells are N=52/136, not large.
5. **Study (A) is still in-sample with no OOS wall of its own**, its arms were chosen post-hoc
   from ~8 candidates on 399 fires, and its detectors are Kev-A/B/C — **not** kevseq. What this
   document reproduces is (A)'s *finding class* on (A)'s cohort with kevseq's fires, not (A)'s
   literal arm.
6. **kevseq's own pre-registered failure condition still owns the ship verdict**: shadow rows
   graded E3 below the don't-trade F-control over a ≥5-day wall. This reconciliation is not that
   wall, and F-control was not re-run here.

**Officers touched:** Hidden Entry Architect (owns kevseq/v2, the lane under test), Statistician
(rows + run log ledgered), Wind Tunnel (one engine, one exit model, identical fire-set across
arms), Execution Surgeon (planned-R vs realized-R — the entire defect), Seam Scientist (the
selection-vs-implementation split is now a registered distinction), Handicapper (the cohort term),
Sim Integrity (three hand-traces, fillability check). Blast Radius / Pit Crew: **nothing ships,
no code changed, no deploy.**
