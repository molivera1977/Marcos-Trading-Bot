# EDGE STRESS-TEST G — KEV'S AGGRESSION (run 8/14/2026 eve, filed 20260815)

**FIRST LINE: AGGRESSION BEATS THE E3 BASELINE — the Kev-aggression portfolio
(flat_top BREAK-attack + grinder full-clip re-attack, all E3 exits) passes 5/5
at mean +$156.64/d and MEDIAN +$134.44/d vs E3's +$94.96/+$62.09; green 89%
(32/36) vs 81%, halves +$167.62/+$145.66, worst -$109.55 (vs -$115.00),
ex-best +$141.50/d.** Marcos's read was right on the entry side too: the era
accidentally traded the break print, and the break print grades BETTER than the
retest under the proven exit.

Round seven, pre-registered fresh (Marcos: "how about Kev's taking multiple
chunks and attacking the break-side"). Script: `edge_stresstest_G_20260815.py`
— imports `edge_stresstest_F_20260815.py` (-> C -> B -> engine of record);
E3 exits (bank 1/2 at +10%, trail rest 10%-off-high closes-through, stop-first,
-1% chase entry, -0.5% market-exit slip) in EVERY variant. Same 421 in-window
files, 36 dates 2026-06-25..2026-08-14, same bar: mean AND median > +$50/day,
green >= 55%, both halves positive, worst > -$300.

**RECONCILE (control):** grinder-1030 solo E3 N=239 total +$5,483.15 and
flat_top retest E3 N=208 total +$1,279.62 — both exact matches to the round F
cells; the baseline portfolio re-run reproduces F's E3 pass to the cent
(mean +$94.96, median +$62.09, worst -$115.00).

## TEST L — BREAK-ATTACK vs RETEST (solo lanes, E3 exits, H2 halt + H3 dedup)

| lane | N | win% | total $ | mean/trade | daily mean | daily MEDIAN | worst day |
|---|---|---|---|---|---|---|---|
| flat_top RETEST (current spec) | 208 | 37% | +1,279.62 | +6.15 | +35.54 | +37.79 | -164.39 |
| **flat_top BREAK-attack** | **384** | **61%** | **+9,220.01** | **+24.01** | **+256.11** | **+254.49** | **-119.26** |
| grinder session-high (current spec) | 239 | 56% | +5,483.15 | +22.94 | +152.31 | +108.09 | -73.21 |
| grinder EARLY (close > prior 15-min high) | 652 | 41% | +7,040.93 | +10.80 | +195.58 | +96.74 | -212.37 |

Break-attack detection: base logic UNCHANGED (4x3min range <=12% -> level);
entry at the FIRST 10s close above the base high, stop = base low, in-window
13:30-14:30Z, chased. It is better on EVERY column vs the retest: 7x the
dollars, win% 61 vs 37, worst day shallower. The retest requirement was
filtering OUT winners (many breaks never pull back — the ones that run) while
keeping the failures that do. **flat_top arm for TEST O = BREAK.**
Grinder early-attack makes more total (+$7,041 on 2.7x the trades) but degrades
per-trade quality (win 41%, mean/trade +$10.80 vs +$22.94, worst -$212 vs -$73,
median below the current spec) — reported, NOT selected (L pre-registered the
break-vs-retest choice for flat_top only).

## TEST M — MULTI-CHUNK vs FULL-CLIP (grinder, E3 exits)

| arm | N | win% | total $ | mean/trade | daily mean | daily MEDIAN | worst day |
|---|---|---|---|---|---|---|---|
| **full-clip at signal** | 239 | 56% | **+5,483.15** | **+22.94** | **+152.31** | **+108.09** | -73.21 |
| multi-chunk (1/2 + confirm add) | 239 | 56% | +5,129.15 | +21.46 | +142.48 | +104.26 | **-61.61** |

Confirmation adds fired on 196/239 (82%); the rest rode the half. Multi-chunk
LOSES -$354 total: the confirmation is nearly always there (82%), so the add
usually fills — just HIGHER (chased at the confirm close), raising the blended
basis with no offsetting selection benefit. The only gain is a slightly
shallower worst day (-$61.61, half-size on unconfirmed losers). On THIS lane
the signal already carries the confirmation (a grinder new-high print IS the
confirmation). **Grinder exec for TEST O = FULL-CLIP.** Refutation autopsy: the
chunking idea isn't wrong in Kev's hands — it buys protection when entries are
anticipatory; our grinder entry is already late-confirmed, so the second chunk
only pays up.

## TEST N — RE-ATTACK (grinder, up to 3/name/day, 15-min post-exit cooldown, E3)

| cohort | N | win% | total $ | mean/trade | daily mean | daily MEDIAN | worst day |
|---|---|---|---|---|---|---|---|
| one-and-done (1st attacks) | 88 | 74% | +3,376.61 | +38.37 | +93.79 | +85.65 | -25.95 |
| **MARGINAL (2nd/3rd attacks)** | 14 | 43% | **+160.43** | +11.46 | +4.46 | 0.00 | -36.15 |
| combined re-attack lane | 102 | 70% | +3,537.04 | +34.68 | +98.25 | +88.65 | -25.95 |

Attacks: 1st=88, 2nd=10, 3rd=4. The marginal cohort is POSITIVE (+$160.43) but
thin: N=14, win 43%, daily median $0.00 — a small net add, not an edge on its
own. Per pre-registration (marginal > 0) the re-attack lane feeds TEST O.
DISCLOSED: the re-attack lane (N=102) is SMALLER than the status-quo F-round
grinder set (N=239) because re-attack imposes sequential discipline (next
signal only 15 min AFTER the prior E3 exit) that the raw 900s signal spacing
never had — re-attack here is an aggression RULE, not more volume.

## TEST O — KEV-AGGRESSION PORTFOLIO vs E3 BASELINE (2 slots, full H1-H4, 36 days)

Arms: flat_top BREAK + grinder FULL-CLIP RE-ATTACK(<=3), all E3 exits.

| portfolio | N(H4) | total $ | mean/d | MEDIAN/d | green | halves /d | worst | ex-best | verdict |
|---|---|---|---|---|---|---|---|---|---|
| **O Kev-aggression** | 156 | **+5,639.03** | **+156.64** | **+134.44** | **89%** (32/36) | **+167.62/+145.66** | **-109.55** | **+141.50** | **PASS 5/5** |
| E3 baseline (round F) | 238 | +3,418.71 | +94.96 | +62.09 | 81% (29/36) | +81.03/+108.90 | -115.00 | +86.20 | PASS 5/5 |

| criterion | bar | O actual | verdict |
|---|---|---|---|
| daily mean | > +$50 | +$156.64 | **PASS** |
| daily median | > +$50 | +$134.44 | **PASS** |
| green days | >= 55% | 89% (32/36) | **PASS** |
| both halves positive | yes | +$167.62/d, +$145.66/d | **PASS** |
| worst day | > -$300 | -$109.55 (8/14) | **PASS** |

Per-entry H4 contribution: flat_top BREAK N=107 +$3,931.30, grinder N=49
+$1,707.73. Slot pressure is real: 328 slot-skips (vs baseline's 209) — the
break lane fires 384 signals into 2 slots; the H4 walk is doing heavy selection
and these dollars are the SLOTTED subset, not the lane totals. Red days: only
6/30 -$27.30, 7/02 -$59.90, 7/06 -$4.09, 8/14 -$109.55.

## HONEST READING (selection risk — round SEVEN)
1. **This is the seventh round of variants graded on the SAME 36 days.** The
   cumulative garden of forking paths is now: 4 entry lanes x execution models
   x windows x 5 exits x this round's aggression arms. E3 was already best-of-5;
   O is best-of-(L arms x M arms x N). The in-sample bar CANNOT distinguish
   skill from selection at this depth — the OOS wall (>= 5 forward days, 8/17+
   paper) grades whatever wins, and O's margins are big enough that a real
   effect should survive shrinkage. Doctrine: this nominates O for the OOS
   wall; it green-lights NOTHING live. 8/8 law: smaller + later, never
   launch-anyway.
2. **The break-attack result is large enough to be suspicious on its own** —
   win% RISING (37->61) while entering earlier is the signature of either a
   real mechanism (retest filters out the strongest breaks — consistent with
   the era's accidental break fills making money, and with Kev attacking the
   break side) or a lookahead/level bug. Wind Tunnel check run: the armed level
   comes only from COMPLETED 3-min bars (`end_t < b["t"]`), entry is the
   close that crosses it, stop = base low of the same completed window — no
   lookahead found. Independent re-derivation by a separate context is still
   owed before this ships anywhere.
3. **[CAPACITY-SUSPECT] carries, amplified.** 384 break signals + a 61% win
   lane at $500 clips on thin names; the -1%/-0.5% slip model is least
   trustworthy at the exact moment of a break print (everyone's order is there).
   Break entries fill INTO the momentum print — real chase slippage on breaks
   can exceed -1%.
4. **M's refutation is scoped to the grinder lane** (entry already confirmed).
   Multi-chunk on an ANTICIPATORY entry (hidden v2, flush entries) is untested
   and remains Hidden Entry Architect material.
5. **N's marginal cohort (N=14, median $0) is decoration, not edge.** It rode
   into O on a +$160 technicality; if OOS shows the 2nd/3rd attacks bleeding,
   cut them without ceremony — O's pass does not depend on them.

## HAND-TRACES (Sim Integrity)
**Multi-chunk — LGHL 2026-07-28 14:31:00Z** (biggest multichunk winner with an
add): sig 1.0200, stop 0.9650. Enter 242.67 sh at 1.0302; 14:34:20 confirm bar
high 1.0296 > entry-bar high 1.0200 -> ADD 240.41 sh at 1.0399, blended basis
1.0350, bank tier 1.1385; 14:48:10 BANK 1/2 at +10%; 15:02:50 TRAIL close
1.6100 (runhi 1.8000) fill 1.6019 -> **+$161.93**. Same signal FULL-CLIP E3:
**+$163.75** (the round F best-trade cell, engine agreement) — the add bought
the same trade at a worse basis. M's verdict in one trade.

**Re-attack — ASTC 2026-08-05** (2 attacks): #1 sig 15:29:00 entry 7.66 stop
7.47 -> bank +10% 15:37:20, trail out 15:46:10 at 8.2883 = **+$42.83**; next
attack eligible from 16:01:10. #2 sig 17:36:30 (fresh grinder signal, 95 min
later) entry 10.02 stop 9.61 -> bank 17:39:50, trail 17:44:50 at 11.4645 =
**+$58.21**. The name kept grinding after the first exit; one-and-done leaves
the second leg on the table. Cooldown law verified: attack #2's signal
(17:36:30) > #1 exit (15:46:10) + 15 min.

## Method notes
1. All variants share F's `sim_var` E3 path verbatim; multi-chunk uses a
   dedicated sim mirroring the same bar order (flatten -> haltgap -> stop ->
   add -> bank -> run-high -> trail), blended basis exact, stop = signal
   would_stop throughout, add chased at confirm close +1%.
2. Solo tables graded post-H2(halt)+H3(dedup), no capacity (N constant);
   portfolios get the full H1-H4 walk + H5.
3. Re-attack selection is sequential per name/day: each next signal must print
   >= 15 min after the prior attack's E3 exit bar; cap 3.
4. First run killed at 10 min: my det_grinder_early was O(n^2) (full-array
   scan per bar); rewritten with a sliding-window max + bisect, logic
   unchanged, then rerun clean (EXIT=0). Disclosed per stop-the-line law.
5. Raw outputs: `stress_G_out.json` committed; `stress_G_run.log` on disk
   (run logs are gitignored, same as rounds A-F).

## Officers touched
Momentum Operator (LEAD — entry aggression graded; O nominated, no-ship),
Reclaim Architect (retest REFUTED as a filter on flat_top under E3 — the
break IS the entry; owns the mechanism autopsy), Seam Scientist (round-seven
selection-risk ledger; OOS wall >= 5 forward days holds the verdict),
Wind Tunnel Engineer (no-lookahead check on break levels; O(n^2) rewrite
disclosed; multichunk sim bar-order law), Systems Quant (reconcile to the cent
vs round F on both solo lanes AND the baseline portfolio; hand-traces
engine-log verified), Execution Surgeon (break-print chase slip flagged — -1%
least trustworthy exactly at the break; owed a fill study), Convexity Trader
(break lane = higher win% AND fatter tail, rare; M refuted as paying up for
confirmation already in the signal), Trade Manager (E3 exits held fixed by
design), Strength Ombudsman (retest-waiting = strength-refusing bias in entry
form, priced: -$7,940 vs break on the same base), Crown Steward / Side Marshal
(no gate stack in scope — but 384-signal break lane will meet the back-side
gate live; flagged), First Hour (break lane is 9:30-10:30 — capital cycling
under 328 slot-skips is its docket), Handicapper (652-signal early-grinder
cohort archived for character work), Statistician (this entry + artifacts),
Quartermaster (cache stable 421), Historian (second consecutive 5/5, first
head-to-head where aggression beat the incumbent), Blast Radius Auditor (no
live-path change — kill-test only), Forward Architect (early-grinder volume
lane + anticipatory-entry chunking registered as hypotheses), Kev Librarian
(grounding: break-side attack and multiple chunks are Kev's words — one
graded IN, one graded OUT; chronicled).
