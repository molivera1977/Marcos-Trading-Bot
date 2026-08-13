# SPREAD CENSUS (Marcos: "run the era census") — run 2026-08-13 ~01:30 ET on /api/trades
# est_slippage = shares x L1 (ask-bid) at entry = ONE full crossing (pessimistic on maker tier
# exits, optimistic on exit-time spread widening + impact). Half-spread model shown as bracket.
ERA 7/13+ (n=379 stamped): sim -$121.67 | spread $2,987.83 | live-model -$3,109.50
  -> era-wide, sim profit lives in wide books: >1% spread cohort sim +$444.64, live -$2,162.31
CURRENT REGIME 8/04+ (n=127): sim +$1,194.74 | spread $934.83 | live full-crossing +$259.91 / half +$727.33
  refuse >1.0%: refused live +218.76 (KEEPS live profit - too tight, kills BQ-class winners)
  refuse >1.5%: refused live  -44.52 | kept live +304.43 (half +409.88)
  refuse >2.0%: refused live  -31.26 | kept live +291.17 (half +447.29)
THIS WEEK 8/10+ (n=61): sim +$420.61 | live +$87.96 / half +$254.29
  refuse >1.5%: refused live -47.77 | kept +135.73     refuse >2.0%: refused live -25.34 | kept +113.30
TOP SPREAD SINKS era: BQ $104 (live still +$61) | LEDS $88 (live -$41) | HUIZ $78 (live +$265) |
  TGHL $76 (live -$95) | PN $74 (live -$196) | VEEE $64 (live -$148)
VERDICT MATERIAL: a 1.5-2% max-spread entry cap costs ~nothing live in the current regime (refused
cohorts live-negative both windows) while deleting a sim mirage (+$679 sim at >1.5% that is -$45 live).
BEHAVIOR CHANGE = MARCOS'S CALL (8/13 law). Estimator limits stamped above; trial week replaces model w/ truth.
