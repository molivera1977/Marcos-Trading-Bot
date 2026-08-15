# CONTEXT JOINS — VWAP-FIRST + RUNWAY COUNTERFACTUALS (run 8/14 eve, filed 20260815)

**FIRST LINE: (1) No VWAP clause earns proposal-grade on either champion lane —
dollars concentrate above-VWAP/rising but no champion cell bleeds materially;
the one real bleeder is on the UNSHIPPED v2cal lane (above-VWAP + falling VWAP:
-$1,042 over 234 trades). (2) The runway gate is NOT inverted: the 51 refused
fires of 8/11-8/14 replay to a NET -$195.70 — it saved money this week — but
ALL of the saving lives in the <0.3R band (-$271.66); the 0.7-1R refusals
would have MADE +$74.57.**

Pre-registered tonight (Marcos: VWAP and runway graded as context for every
entry). Script: `context_joins_20260815.py` — imports
`edge_stresstest_G_20260815.py` (-> F -> C -> B -> engine of record). Raw cells:
`context_joins_out.json`. Same 421 in-window files, 36 dates
2026-06-25..2026-08-14; ALL exits E3 (bank 1/2 at +10%, trail rest 10%-off-high
closes-through, stop-first, -1% chase entry slip, -0.5% market-exit slip);
H2 halt + H3 dedup, no capacity (context grading keeps N constant — round F/G
convention). Lane totals reconcile to round F/G to the cent: grinder-1030 N=239
+$5,483.15, flat_top BREAK N=384 +$9,220.01 (engine agreement).

VWAP definition: session typical-price cumulative over RTH 10s bars
(RTH-anchored — matches the grinder detector's internal vwap). The LIVE ~vwap
is premarket-anchored (settled doctrine); this join's VWAP is therefore a
sibling, not the production value. Slope = VWAP now vs 30 bars (5 min) back;
flat = |change| < 0.1%.

## JOIN 1 — VWAP CONTEXT AT FIRE (E3 exits)

### grinder post-10:30 (N=239, +$5,483.15)
Side is NOT gradeable on this lane: the detector already REQUIRES above-VWAP
(its own filter), so 239/239 fire above. Distance + slope only:

| cell | N | win% | total $ | mean/tr |
|---|---|---|---|---|
| above 0-1% | 2 | 100% | +182.50 | +91.25 |
| above 1-3% | 25 | 56% | +1,058.72 | +42.35 |
| above 3%+ | 212 | 56% | +4,241.93 | +20.01 |
| slope rising | 175 | 61% | +4,810.45 | +27.49 |
| slope flat | 63 | 43% | +624.92 | +9.92 |
| slope falling | 1 | 100% | +47.78 | +47.78 |

**Verdict: LEAVE ALONE.** Every cell is green. Rising-VWAP fires earn 2.8x per
trade vs flat (+$27.49 vs +$9.92), but the flat cell still makes +$625 — a
slope clause would cut profitable volume for a quality ratio nobody asked for.
Distance bands are monotone the WRONG way for a "close to VWAP is better"
story at meaningful N (the 0-1% cell is N=2 decoration). Ignition precedent
respected: above-VWAP graded WORSE there; here side can't even be measured
because the filter bakes it in.

### flat_top BREAK-attack in-window (N=384, +$9,220.01)
| cell | N | win% | total $ | mean/tr |
|---|---|---|---|---|
| ABOVE (all) | 304 | 65% | +8,781.70 | +28.89 |
| BELOW (all) | 80 | 48% | +438.31 | +5.48 |
| above 0-1% | 30 | 47% | +425.87 | +14.20 |
| above 1-3% | 93 | 74% | +4,108.68 | +44.18 |
| above 3%+ | 181 | 64% | +4,247.15 | +23.46 |
| below 0-1% | 17 | 65% | +439.19 | +25.83 |
| below 1-3% | 19 | 37% | +69.31 | +3.65 |
| below 3%+ | 44 | 45% | -70.19 | -1.60 |
| slope rising (all above-side) | 184 | 70% | +6,376.99 | +34.66 |
| slope falling | 125 | 53% | +1,795.06 | +14.36 |

95% of the lane's dollars are above-VWAP, and the sweet spot is above+1-3%
(win 74%, +$44.18/tr). But the ONLY red cell is below+3%+ at -$70.19 over 44
trades — noise-sized. A hard "above-VWAP only" clause would forfeit +$438.31
(the below side is net GREEN, carried by below-0-1% at +$439.19 — breaks
launched from just under VWAP that reclaim it are fine trades).
**Verdict: NO CLAUSE — leave alone.** VWAP side/distance goes on the row as
CONTEXT (data-only stamp, Side Marshal material); nothing here pays for a veto.
Note: zero below+rising fires exist (a falling/flat VWAP is nearly implied by
being below it mid-morning) — the below cohort is structurally the weaker tape,
and E3 already handles it (worst cell bleed $1.60/trade).

### calibrated v2 (in-window, N=1259, +$2,615.84 — NOT a shipped lane)
| cell | N | win% | total $ | mean/tr |
|---|---|---|---|---|
| ABOVE (all) | 964 | 30% | +1,311.63 | +1.36 |
| BELOW (all) | 295 | 25% | +1,304.21 | +4.42 |
| **above + falling slope** | **234** | **26%** | **-1,042.31** | **-4.45** |
| above + rising slope | 601 | 32% | +2,183.25 | +3.63 |
| below + falling slope | 153 | 27% | +1,173.85 | +7.67 |
| above 0-1% | 193 | 22% | -248.25 | -1.29 |
| below 0-1% | 134 | 24% | +935.49 | +6.98 |

The ignition counter-example REPEATS here: below-VWAP fires earn 3.2x per
trade vs above (+$4.42 vs +$1.36), and below+0-1% (the flush that undercuts
VWAP itself — the C1 anchor doing its job) is the lane's best cell. The one
real bleeder anywhere in JOIN 1: **above-VWAP + falling 5-min VWAP = -$1,042
over 234 trades** (buying a flush-reclaim while the day's average is rolling
over, extended above it). **Verdict: proposal-grade cell exists (cut
above+falling), BUT the lane itself is unshipped and thin-margin (+$2.08/tr
overall, win 28%) — filed as v2-rebuild input for the Hidden Entry Architect /
Seam Scientist, NOT a live proposal.** Nothing to change on the bot.

## JOIN 2 — RUNWAY-REJECT COUNTERFACTUALS (8/11-8/14, 51 rows, 51 replayed)

Source: dashboard decisions archive `status=runway_reject` (X-Dashboard-Secret
pull, 8/11: 5, 8/12: 13, 8/13: 11, 8/14: 22 — the BANL x7, DFSC, HAO x2 day).
Replay: entry = the refused signal price chased (-1%), stop = the row's stop,
E3 exits on the day's 10s bars — universe cache where ferried (25 rows), the
dashboard `/api/bars` ALP10S archive for the other 26 (3 of those flagged
PARTIAL-TAPE: tape ends before a modeled exit — their cf dollars are small:
-$7.22, -$19.80, -$7.44).

**HEADLINE: counterfactual total -$195.70.** Would-be winners +$712.68 vs
losses prevented -$908.38. **Pre-registered failure condition NOT met — the
gate is NOT inverted; it saved ~$196 this week** (~$49/day-scale on the 4
days, real money at the $50/day mission bar).

### By R-of-road band (the pre-registered split)
| band | N | win% | cf total $ | reading |
|---|---|---|---|---|
| <0.3R | 30 | 37% | **-271.66** | ALL the gate's earnings live here |
| 0.3-0.7R | 14 | 36% | +1.39 | dead even — gate neutral |
| 0.7-1R | 7 | 43% | **+74.57** | refusals here COST money |

The gate's dollars are earned exactly where its logic says they should be:
tiny-road fires (<0.3R) replay to -$272. The near-miss band (0.7-1R, N=7 —
five of them the BANL cluster) would have made +$74.57; the middle band is a
coin flip. The gradient is the RIGHT direction for the mechanism (worse road
= worse counterfactual), which is what a healthy gate looks like.

### By lane
| lane | N | win% | cf total $ |
|---|---|---|---|
| ma_pullback | 14 | 50% | -115.94 |
| dip_rip | 4 | 0% | -74.30 |
| flat_top | 14 | 29% | -41.54 |
| ignition | 3 | 33% | -12.02 |
| orb | 2 | 50% | -7.11 |
| hidden_entry | 14 | 43% | **+55.21** |

Gate saves money on five of six lanes. The one positive: hidden_entry (+$55),
driven by the 8/14 BANL cluster — 7 refused fires on ONE name, first three
would have won (+$47.55/+$51.08/+$39.05, all riding the same move to EOD),
last four all stop out at the same 17:10 bar (-$125). Even granting all seven
as independent (they are NOT — one slot could hold at most ~2), BANL nets
roughly +$12. The "BANL x7 refusals" that motivated this join were, in
dollars, a wash — not a starved winner.

### Per-day
8/11: -$74.25 · 8/12: +$26.78 · 8/13: +$60.17 · 8/14: -$208.40. The gate's
whole week was earned on Friday 8/14 (NEXR x2 -$96, HAO -$72 ignition chases,
LFS/HHS -$50) — exactly the <0.3R chop it was built for.

**VERDICT: runway gate KEEPS ITS JOB — not inverted, net saver, and the band
gradient runs the right way. One priced observation for Marcos (not a
proposal): the 0.7-1R band refused +$74.57 of counterfactual profit on N=7.
If anything is ever loosened it is THAT edge of the band, and only via a
re-grade with more weeks of rows — N=7 with a 5-row same-name cluster is not
evidence, it is an anecdote with a receipt.**

## HONEST CAVEATS
1. **Fills optimistic everywhere**: -1% chase / -0.5% market-exit slip modeled;
   refused fires are often refused in thin moments — real slippage on the
   counterfactuals could be worse than modeled (cuts BOTH ways: would-be
   winners smaller, would-be losers bigger).
2. **Counterfactual exits are MODELED (E3)**, not the live exit stack (no
   breakeven, no live trail nuances, no halt-arm interactions). The live bot
   would not have managed these trades identically.
3. **JOIN 2 assumes every refused fire had a free slot** — 51 independent
   $500 clips. Slot pressure (esp. the BANL 7-cluster and EROC x5) means the
   real forgone/saved dollars are smaller in magnitude than every number above.
4. **26/51 replays ride dashboard-archive tapes** (name-days the ferry never
   cached); 3 are partial. Archive bars are the same ALP10S stream but thinner
   coverage — treated as adequate for dollar-scale, not to-the-cent, claims.
5. **JOIN 1 is round EIGHT on the same 36 days** — these cells inherit the full
   garden-of-forking-paths caveat from round G. That is exactly why both
   verdicts are "leave alone / data-only stamp": context stamps are free;
   clauses are not. OOS wall (8/17+) grades everything.
6. **VWAP anchor mismatch disclosed**: joins use RTH-anchored typical-price
   VWAP; live ~vwap is premarket-anchored. Cells could shift under the live
   anchor, one more reason side/distance ships as a STAMP first.
7. Week = 4 days, and 8/11-8/13 rows are sparse (5/13/11). One week of runway
   rows is a pilot reading, not a grade; the weekly re-grade should re-pull
   with this script as rows accumulate.

Officers touched: Momentum Operator (verdicts on noise-vs-clause), Side
Marshal (VWAP/side stamps = his registry), Strength Ombudsman (0.7-1R refused
strength priced: +$74.57/N=7), Crown Steward (clean — no crowned name in the
reject set), Systems Quant (reconcile-to-the-cent vs F/G), Wind Tunnel
(counterfactual fidelity caveats 1-4), Statistician (cells in
context_joins_out.json), Historian (8/14 = the gate's whole week in one day).
