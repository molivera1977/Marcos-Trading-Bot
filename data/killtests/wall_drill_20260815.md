# WALL PROVING DRILL — 8/15 (replay of 8/14 tape)

Wall fix (bot :8953 tuple-unpack, shipped 8/14 12:53) replayed against real specimens.
Wall block replicated verbatim from marcos_trading_bot.py:8951-8962 (see wall_drill_20260815.py).
**Status: PROVEN(replay). Live-tape proof still lands Monday — no production demotion has fired yet.**

HEADLINE: the DFSC 10:55 refusal (0.14R to rung 2.89) was against a SPENT rung — DFSC's 10s tape
traded through 2.89 at 10:16-10:22 ET and again 10:51-10:54 (window high 2.95 at the gate moment).
Post-fix the honest road is 0.55R to the 2.95 wall, which CLEARS the 0.40 need: the fixed wall
flips this refusal to a pass. Fidelity check: the pre-fix replay reproduces the archived live
numbers exactly (0.14R/2.89 and 0.11R/2.96).

## Specimen A: DFSC @ 10:55:34 ET
- entry 2.87 / stop 2.725 / map rungs [2.89] / next_supply 3.0  [rungs RECONSTRUCTED from the gate row]
- pre-fix (wall inert): road **0.14R** to 2.89 — 0.14R to rung 2.89 (need 0.4) — the 10:55 refusal
- 2h wall window (~ALP10S, 720 bars): session-window high **2.9500**
- spent rungs demoted: [2.89] | wall inserted at 2.9500
- post-fix: road **0.55R** to 2.95
- VERDICT: wall CHANGED the road

## Specimen B: DFSC @ 14:44:08 ET
- entry 2.94 / stop 2.7523 / map rungs [2.96] / next_supply 3.0  [rungs RECONSTRUCTED from the gate row]
- pre-fix (wall inert): road **0.11R** to 2.96 — 0.11R to rung 2.96
- 2h wall window (~ALP10S, 720 bars): session-window high **2.9700**
- spent rungs demoted: [2.96] | wall inserted at 2.9700
- post-fix: road **0.16R** to 2.97
- VERDICT: wall CHANGED the road

## Specimen C (insertion): ONFO @ 09:35:14 ET
- entry 2.935 / stop 2.6819 / map rungs [3.0]  [rungs RECONSTRUCTED from the gate row]
- pre-fix (wall inert): road **0.26R** to 3.0 — road ran to the ink at 3.0
- 2h wall window (~ALP10S, 720 bars): session-window high **2.9500**
- spent rungs demoted: none | wall inserted at 2.9500
- post-fix: road **0.06R** to 2.95
- high 2.9500 rejected **21x** before the gate (>=60s-spaced tags within 0.5%, no 10s close above) — the wall belonged in this road
- VERDICT: wall CHANGED the road

---
Drill: data/killtests/wall_drill_20260815.py · tape cache: data/killtests/wall_drill_cache_20260815/
Replay proof only. The fixed wall has still never demoted a rung in PRODUCTION — Monday's live tape is the real proof.
