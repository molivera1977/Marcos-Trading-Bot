# STOP-COHERENCE FLOOR — era census (run 2026-08-13 ~00:18 ET, /api/trades, era 7/13+, n=379 stamped)
Rule: refuse execution when (entry-stop)/entry < floor. ALL lanes (family: liquidity floor).
| floor | caught | refused P&L |
| 0.25% | 1 | -$8.65 |
| 0.50% | 3 | -$17.50 (2L: BQ 8/12 -8.65 @0.074%, MB 8/7 -9.31 @0.290%; 1 scratch: INUV 7/13 +0.46 @0.297%) |
| 1.00% | 6 | +$51.54 (4 WINNERS refused - too wide) |
| 2.00% | 27 | -$316.72 (min-stop floor territory, NOT this rule) |
SHIPPED at 0.5% (Marcos 8/13 ~00:20: "ship the 0.5% floor tonight with the audit protocol and
we'll revisit Friday after close"). Kill switch STOP_COHERENCE_MIN_PCT=0. Friday: grade the
stop_coherence_refused rows + re-run this census with the week's tape. Caveat: n=3, thin — the
ship is defensive (blocks thesis-less trades), not expectancy-positive by proof.
