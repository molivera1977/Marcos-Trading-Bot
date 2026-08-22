# KIMI K3 BUILD PACKAGE — 8/21 night (the full 8-lane response to Dossier Batch v2)
# STATUS: HYPOTHESES. Every dial is a kill-test candidate with its sweep range attached.
# Kimi's own framing: "every number is a hypothesis with a kill-test date."
# NOTHING here ships without: pre-registered kill-test (both halves, drop-best, n-floor,
# real NBBO costs) + NEW LANE CHECKLIST diff + Blast Radius + Marcos's word.

## THE PACKAGE VERDICT LINE (Kimi):
"eight lanes, three survivors-by-design (ignition with confirmation, flat_top with
reachability, reclaim with a universe gate), two regime-gated (grinder, hidden_v2), two
rebuilt (ema9x90, kevseq), one killed into a sensor (v2conv)."

## CROSS-CUTTING INVARIANTS (ship-class, not sweep-class)
1. emit_stop(): stop validity asserted AT EMISSION everywhere — min_w = max(1% entry,
   1x spread); degrade to floor, never >= entry. Kills the bad_stop_skip class structurally.
2. Every gate stamps entry + would-be stop + its own input at refuse time (already our law;
   Kimi ratifies).
3. Every dial ships with sweep range + pre-registered kill criterion incl. "remove this".

## IGNITION
- Regime-conditional DIALS: HOT(2.0x, ext -5/+15, no confirm) · NORMAL(2.5x, -3/+10) ·
  DEAD(3.0x, -2/+8, CONFIRM BAR: next bar must break ignition high without giving back its
  midpoint). Sweep DEAD vol {2.5,3.0,3.5}.
- Universe pre-filter: $vol5m>250k · spread5m<1% px · day gain>15% · float<50M · not halted;
  rank by $vol x gain. [ADAPTATION NEEDED: float data is 'N/A' in our records — substitute or drop]
- EMA persistence FINAL: EMA9>EMA20 on 3 of last 5 COMPLETED 1-min bars, recomputed at 1-min
  close only (kills the $0.0068 boundary-flicker class).
- PRE rule: fires iff regime!=DEAD AND pm $vol>$2M AND gap>20%; convert mult 3.0x; hard end
  09:20. Pre-registered kill: full-universe PRE negative under these => PRE silent.

## GRINDER
- Failure-keyed cooldown (full state machine: STOPPED->5-min reset; OPEN/BANKED->needs new
  15-min high; halt resume DELETES state; EOD clear; partial fill counts as fill).
- Design answer: HOT-ONLY + funded-grind condition ($vol15m>500k). One NORMAL candidate
  (higher-low, dd<2%, net-up 15min) ships ONLY as kill-test; expected to die.
- Width-capped stop: stop=max(lo15, entry*(1-CAP)) CAP sweep {3,4,5}%; floor max(1% entry,
  1x spread).

## EMA9X90 (rebuild)
- Replacement confirmation (1-MIN series): ema9>ema20 AND ema20 rising vs 3 bars ago AND
  close>ema9 AND close>vwap; entry = break of confirm bar high within 3 bars else expire;
  invalidate on completed close<ema20. Confirms ~2-3 min, not 15.
- Leadership gate: score=0.6*z(day_gain)+0.4*z(day_$vol), top-3, 60s refresh, hysteresis
  (hold seat until rank>5). SHARED function with kevseq.
- OPEN-only: 09:35-11:00; morning exits bank 1/2 @+7%, trail 8%. Kill-test {E3, morning-E3}.
- Stop: struct=min(low, last 3 completed 1-min); floor max(1.5% entry, 2x spread);
  REJECT if structure >6% away (late-entry tell).

## KEVSEQ (rebuild — buy the pullback after the burst, never the burst)
- Phase 1 BURST (vol>=3x base, range>=2x base, green) -> record only, NO ENTRY.
- Phase 2 PULLBACK (2-6 bars): retrace 20-50% of burst range on declining vol.
- Phase 3 TRIGGER: close > pullback_high, vol>=1.5x pullback avg.
- INVALIDATE: retrace>60% or low<burst_base_low.
- Stop: pullback_low - 0.5x spread; floor max(1.5% entry, 2x spread); no Phase-2 = no trade.
- Universe: leadership gate AND day_gain>40%.
- Exit: 50%@+1R->BE, 25%@+2R, trail 25% @15% off high; time stop 5min no-new-high -> half out.
- Bars-only front_side: close>vwap AND close>session_open AND day_gain>20% AND
  (close-day_low)/(day_high-day_low)>=0.70.

## HIDDEN_V2
- Universe: $vol>2M · spread5m<0.75% px · trades5m>100 · gap>15% · px>$1.
- DEAD arm: band 15-40% (from 25-60) + pullback<=40% of leg + trigger vol>=2x + leaders-only;
  if nothing gained 15%, SILENCE IS CORRECT (posture, not defect).
- Trigger: <=4 bars (from 6), close top-40% of range, vol>=1.5x pullback mean.
- Exit: 40%@+1R->BE, 30%@+2R, trail 30% @20% off high; 10-min time stop.

## V2CONV — NO BUILD (Kimi's call: thesis = buying weakness in a momentum system; zero
  positive cells anywhere incl. hot tape). DETECTOR-ONLY role:
- Suppressor input: v2conv fired on X in last 10 min => ignition/kevseq may not fire on X.
  KILL-TEST: does that suppression improve the chase lanes?
- Its flush sensor (>=3% in 120s) consumable by pullback lanes as the flush leg.
- If any entry role ever revisited: $vol5m>=150k, spread<=0.6% px, k=2 not k=1.

## FLAT_TOP
- PM bars in the base LEGITIMIZED conditionally: pm $vol in window>500k AND pm spread<=0.75%
  of base_low; else session-only base (first fire ~09:42). Converts "allowed?" into "was the
  PM base REAL?" — kill-testable.
- Arbitration interface: computed contest, no fixed priority — ft_score=(0.12-rng)/0.12 vs
  ma_pullback's pullback_quality, z-scored; per-pair gradable (matched pairs design exists).
- Stop FINAL: base_low - 0.5x spread; floor max(1% entry, 2x spread); base_low>=entry
  (halt artifact) => REJECT the fire, never repair the stop.
- Base width: rng_cap = min(0.12, max(0.06, 4*spread/base_low)).

## KEVSPEC-RECLAIM (Kimi's own lane)
- PRE-COMMITTED fallback order for a curated-vs-full gap: (1) universe gate ($vol>2M,
  spread<0.75%, px>$1) -> (2) vol_mult 1.5->2.0 -> (3) dip 0.5->0.75%. NEVER tune stop/exits
  in response to the universe verdict.
- MID: EXCLUDED (bound 11:30). Afternoon reclaim = a different lane; do not build it here.
- STOP DOCTRINE (system-wide ruling material): fixed-distance stops
  (max(abs_floor, 2% px, 2x spread); abs_floor .10/<$3, .15/<=$10, .25/>$10) for PATTERN
  lanes without clean structure (reclaim, sequence entries). STRUCTURAL stops stay for lanes
  where the level means invalidation (flat_top base-low, grinder lo15). "Structural where the
  pattern defines invalidation, fixed-distance where it doesn't."
