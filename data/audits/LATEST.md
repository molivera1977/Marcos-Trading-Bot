# CONVENING ARTIFACT — 8/18 AFTERNOON: THE 9/90 LANE + CAPITAL-PRIORITY REWRITE

covers: 39247f1e70f1

## What ships
1. **ema9x90 — a NEW CONVERTING LANE** (Marcos's signal, refined by him through six studies in
   one session). Entry: 1-min 9/90 up-cross at/above session VWAP, RTH only. Stop: 5-min swing
   low. Exit: lose session VWAP. Half size, no daily cap, no shadow mode. Kill: EMA9X90=0.
2. **Lane expectancy in the capital sort** — measured lanes first (flat_top +24.94 / ema9x90
   +22.33 / grinder +21.90), unmeasured neutral with written reasons, hidden_entry carried at
   its measured −$10.21. Kill: LANE_EXPECTANCY_SORT=0.
3. **Move % supersedes the 7/26 Kev tier** (Marcos, twice, with AUUD-vs-PFSA as specimen).
   Kev tier survives as tiebreaker; the day-gain-floor exemption is untouched. Ledgered
   (`move_pct_over_kev_tier_0818`, 11/11 HOLD). Kill: KEV_TIER_FIRST=1.

## Evidence, stated with its limits
656 fires / 63 dates / 736 name-days. Above VWAP +$22.33/tr (n=319, green 54%); below VWAP
−$10.27 (n=337) with FIVE rescue attempts dead (distance/slope/stack: no separation; velocity &
volume: INVERTED; reclaim: −$10.29 n=90; crowns-only: structurally zero fires). Two fresh splits
both positive; permutation null p=0.0005 (0/2000). **The pre-registered bar FAILED condition (b)
— hold-out n=55 < 100** — because a 13-date split cannot seat 100 fires at ~0.9/day. Marcos
ruled it live to earn the sample forward; that ruling, not the wall, is what converts this lane.
MIXED-EPOCH note: config hashes moved intraday today (cap 99 at 10:07, ignition gate at 11:29).

## Findings during the build (the rig earning its keep)
- Missing RTH window: the detector fired 18:59/19:59 ET on 8/10 tape — a window its evidence
  never covered. Caught by exercising on real tape; fixed (EMA9X90_OPEN/CLOSE 09:30–15:45).
- My first EG1 pin for (d) was None — wrong; the explicit no-op refund branch makes it
  decidable and True. Corrected with the reason in the pin.
- MAX_STOP 12%→20%: the cap was refusing legitimate fires (JWEL: the one surviving cross).
- Exercised on TODAY'S tape: fires PFSA $12.44 (the recovery leg), IPST $7.50, XOS $4.74;
  refuses EJH (day's worst loser) and AIXC. Three fires ≠ proof; it shows placement.

## DOCTRINE-INVERSION SWEEP
The 7/26 "every Kev name first" premise is REPEALED in the capital sort. Swept for other
encodings of it: the day-gain-floor exemption (:10869 class) reads Kev-ness for a DIFFERENT
purpose (never blocked for sitting flat) and is deliberately kept; the *KEV console label is
display-only; `_entry_priority` was the only ranking consumer. No orphaned encodings found.

## ROLL CALL
- **Blast Radius Auditor** — TOUCHED. EG1 checklist enforced all seven properties on the new
  lane; caught the unregistered CONVERT env and the 18th exit path before ship.
- **Momentum Operator / Strength Ombudsman** — TOUCHED. The lane trades strength by
  construction (above-VWAP cross); the priority rewrite ends flat-Kev-name queue-jumping.
- **Handicapper** — TOUCHED. Half size at birth; sizing chain unchanged; no-cap is deliberate
  (capital + $30 risk are the limits).
- **Trade Manager / Convexity Trader** — TOUCHED. Lose-VWAP exit is the measured winner
  (+$60.10 hold-out); every faster trail cut the tail and lost. 18th exit path pinned.
- **Execution Surgeon** — TOUCHED. Detector is O(1) per bar on the fed stream; no new fetches.
- **Statistician** — TOUCHED, standing objection RECORDED: n=55 hold-out failed the
  pre-registered bar; the lane ships on Marcos's ruling, not on statistical sufficiency. The
  forward sample is the remedy and the lane's rows are fully stamped for it.
- **Wind Tunnel Engineer** — TOUCHED. 11/11 rigs green; two negative controls on the new pins.
- **Kev Librarian** — TOUCHED. Both lane rules are Kev doctrine (at/above VWAP; lose VWAP =
  done). The 9/90 cross itself is Marcos's observation, not corpus-sourced.
- **Historian** — records: first lane ever born through the full checklist with its wall,
  its failure honestly stated, and a capital-priority supersession the same hour.
- **Cartographer / Side Marshal / Crown Steward / Feed Engineer / Webull Broker Desk /
  Quartermaster / Dashboard Curator / Systems Quant / Pit Crew Chief / Integrator /
  First Hour / Opening Bell / Seam Scientist / Forward Architect / Tape Veteran / Reclaim Architect /
  Rocket Rider / Curl Mechanic / Project Manager / Hidden Entry Architect** — CLEAN: no map,
  side, crown, feed, broker, storage, dashboard, parity, latency, merge, open-window, seam,
  tape-doctrine, reclaim-lane, rocket, curl, schedule or hidden-lane path touched. Hidden
  Entry Architect notes the −$10.21 now rides the sort as a warning label.

## DAY-ONE WALKTHROUGH
Next 1-min 9/90 up-cross above VWAP on a fed name → `ema9x90_fire` row (px/stop/fire_k/age/
drift stamped) → console ⚡ line → breakouts.append half_size → priority sort seats it by
(band 0, move%) → worker: chart gate (tape-class bypass, counterfactual stamped), Kev gate
N/A (not ignition), sizing at half → fill → monitor holds until swing stop or a 1-min close
below session VWAP ("9/90 LANE: lost VWAP") or the 15:45 flatten. Every stop on the path has
a named kill switch. The 15:52 duty-watch checkpoint will show the lane's fires vs fills.

doctrine-inversion sweep: recorded above.
