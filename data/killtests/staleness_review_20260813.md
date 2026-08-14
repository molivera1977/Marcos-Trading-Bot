# STALENESS-CEILING REVIEW (Marcos 8/13 morning: "we'll review this later today") — ANALYSIS ONLY
# Data: pre_gate_cost_v2 (clean clock). No change ships without Marcos's priced word.

## The gate & why it exists
CURL_FIRE_MAX_AGE_PRE=90s: a fire whose bar is >90s old in PRE is suppressed (8/4 DXST surgery —
stale-replay fires after restarts/admissions were buying dead setups). RTH ceiling = 240s.

## What the week's rows say (staleness gate only, modeled)
- Whole week: 25 first-refusals, +$59.03 net left on table (the leak).
- The leak's big rows are EARLY + FAST MOVERS: itemized winners forfeited: RMCF 7:03 +$85, FGI
  7:16 +$18, WXM 7:22 +$18, DFSC 9:18 +$18 (fast mover, mid-PRE), CHOW 8:10 +$16, YXT 8:04 +$14,
  PLAG 8:36 +$14. The sub-$8 residual rows NET -$47 — the gate genuinely SAVES money on the
  small/slow stuff; it bleeds only on runners.
- Time-cut census: pre-08:00 refusals = +$69.61 of the leak (9 rows); post-08:15 = +$31.22 (2 big
  rows: PLAG 8:36, DFSC 9:18 — both fast movers, both would ALSO be caught by option D).

## OPTIONS (each = HYPOTHESIS, kill-test on full 10s bars before ship)
A. KEEP 90s everywhere. Cost ~ +$59/wk modeled; safest; DXST protection intact.
B. EARLY WINDOW 07:00-08:00 -> 240s (RTH parity), 90s after. Captures ~$70/wk of the leak; the
   07:00 tape is structurally slower (fires age past 90s between thin prints); DXST's scar was an
   ADMISSION replay, which option E also covers.
C. FLAT 180s all PRE. Captures more, weakens the 8:30-9:25 rush protection — NOT recommended.
D. FAST-MOVER CARVE-OUT: crowned names get 240s in PRE (crown privilege; DFSC/PLAG/YXT class).
   Captures ~$45/wk incl. the post-8:15 leak; smallest surface.
E. ROOT-CAUSE RIDER (either option): suppress only fires whose bar is stale AND price has drifted
   >2% from fire px (the DXST harm was price-drift, not age per se) — needs its own census.
RECOMMENDATION SHAPE (not a ship): B + D together cover ~$100/wk of modeled leak while keeping
90s exactly where DXST bled (mid-PRE slow names). Friday's full-bars kill-test prices B, D, B+D,
and E against the DXST-class specimens before any word goes to code.
