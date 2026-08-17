# IGNITION GUIDANCE KILL-TEST — 8/17/26

Marcos directive 8/17 after two below-VWAP ignition entries on morning fades:
**"ignition needs to have guidance."** Specimens: FIEE filled 09:38:46 @ $5.6962 (fire px 5.765,
VWAP ~$6.05 per Marcos), DFSC filled 09:41:01 @ $2.90 (VWAP ~$3.21 per Marcos, seq "P D D").
Analysis only — no bot edits, no deploys. Officers convened: Momentum Operator, Systems Quant,
Side Marshal (VWAP-side owner, #18), Seam Scientist (beginning-vs-extension), Statistician,
Wind Tunnel Engineer, Strength Ombudsman (cost-of-refusal priced), Blast Radius Auditor (n/a — no
ship), Tape Veteran; clean: Crown Steward, Quartermaster, Historian.

- **Script:** `ignition_guidance_20260817.py` · run: `..._run.txt` · json: `..._out.json`
- **Universe:** bars10s cache, 729 name-days, 62 dates 05-18..08-14. Detector = ignition-10s
  replica (bot :6316 `ignition_10s_step` conditions + `IGNITION_CONVERT_MULT=4.5` as the fire
  bar): base = prior 24×10s bars, first 90 min RTH, v≥4.5× base avg, v≥5000/6, green, close in
  top 50% of range, close ≥ max base close, ext ∈ [−5%,+15%]; entry = fire close, stop =
  base_lo×0.997. Exits E3 live-parity (`F.sim_var`, halt_rule, dedup ≤5min, $500 clip).
  1,686 raw fires → **1,071 graded** (MINE 804 / HOLD-OUT 267).
- **OOS wall discipline:** MINE 05-18..07-21, frozen HOLD-OUT 07-22..08-14 (18 dates), null =
  5,000 label shuffles on the hold-out (reused from `seq_gate_oos_wall_20260817.md`).
- **Era rows:** 695 `triggered_ignition` fires (decisions_archive 6/29–8/17) + 118 ignition
  trade records (/api/trades). **Join: only 45/695 fires (6%) match a trade within 3 min** —
  most fires are shadow/blocked/duplicate rows, so era joins are directional at best.
- Prior evidence reused: `seq_gate_oos_wall_20260817.md` (T B survives for break-attack/grinder);
  `ignition_census_20260814_RESULTS.txt` + `_v2_` (VWAP-side flip raw→timing-corrected);
  RESULTS_LEDGER 8/8 #18 VWAP-side grade (below VWAP +$1,431/53tr ALL-lane era — the standing
  counter-frame); RESULTS_LEDGER 8/7 (DSY skips below 4.5× convert), :1869 (detector HONEST).
  The "8/8 fighting-the-tape STAK 09:32 grading" as a distinct artifact was NOT found; the 8/8
  #18 grade at RESULTS_LEDGER:495-503 is the closest match and is used.

---

## FAILURE CONDITIONS (written first)

- **G1 is wrong if** the universe's below-VWAP losses are an artifact of runner-day selection +
  E3 exits, and live below-VWAP ignition is actually the EARLY class — exactly what the 8/8 #18
  all-lane grade (+$1,431 below) and the raw 8/14 census claim. If the next 2 weeks of stamped
  live ignition rows show below-VWAP ≥ above-VWAP $/tr, G1 is refuted for this lane.
- **G2 is wrong if** T B needs its lane context (a break lane waiting at the high) — a vol-surge
  fire that already carries T B adds nothing. (That is what the numbers say.)
- **G3 is wrong if** "near session high" merely re-labels "not a morning fade" (double-counting
  G1) or if fresh-high fires are unfillable at size (D-guard answers: they fill).
- **G4 is wrong if** the veto can't fire by construction: the ignition bar is green with a strong
  close, so the string *ending at the fire bar* almost never ends D/F. (Sim: 1/1071. DFSC's
  "P D D" was the pre-surge string — a lookback-shifted veto is a DIFFERENT, untested gate.)
- **G5 is wrong if** stale maps (FIEE map_age 262 min today) make level-side a coin flip, or if
  the 25-fire joined sample is noise.

---

## Per-gate results (universe sim; MINE → frozen HOLD-OUT → null)

Base: MINE 804 fires, 67% win, $+21.21/tr · HOLD-OUT 267 fires, 63% win, $+22.77/tr.

| gate | MINE keep vs drop ($/tr) | HOLD-OUT keep vs drop ($/tr) | HOLD keep N | null p | **verdict** |
|---|---|---|---|---|---|
| **G1 ≥ VWAP** | +25.04 vs +8.91 | **+29.30 vs −8.59** (win 67% vs 43%) | 221/267 | **0.000** | **GUIDES** (sim) — but see era tension |
| **G2 suffix T B** | +29.16 vs +18.69 | +23.21 vs +22.61 | 71/267 | 0.469 | **NO-SPLIT** — T B is a break-lane signal, not an ignition signal |
| **G3 ≤3% off session high** | +31.55 vs +10.66 | **+39.30 vs +0.91** (far-side >5%: −$2.26/tr, N=82) | 152/267 | **0.000** | **GUIDES** |
| **G4 suffix D/F veto** | drop N=1 | drop N=0 | — | n/a | **UNDERPOWERED / STRUCTURALLY EMPTY** at the fire bar (see failure condition) |
| **G5 kev-level respect** | era only | era only | — | n/a | **UNDERPOWERED** — joined fires N=25: shadow-gate **allow +$18.05/tr (5)** vs **block −$4.36/tr (20)**; right direction, tiny N |

G2 note vs the wall: `T B` SURVIVES for break-attack (+$29.49 lift) and grinder (+$23.74) —
it does **not** transfer to the ignition lane (p=0.47). Consistent, not contradictory: the wall
graded lanes that live at the high; ignition fires off a quiet base anywhere.

## Era realized rows (the honesty section)

118 era ignition trade records (book total −$34.73 over 23 active days = **−$1.51/day**):
- G1 era: above-VWAP N=53 −$1.67/tr (47% win) vs below N=37 **+$1.18/tr** (59% win), 28 unstamped
  — **direction OPPOSES the sim**, echoing 8/8 #18 (all-lane) and the raw 8/14 census; the
  timing-corrected census v2 flipped below-VWAP back to negative (−$45..−$7). Three artifacts,
  three answers, all N≤53: the era book is **UNDERPOWERED and store-caveated**; the 1,071-fire
  OOS-walled sim is the only powered measurement in the room.
- G3 era: not measurable — no distance-to-session-high stamp on ignition rows (`entry_dd_pct` is
  populated on 22/118 and is not the high-distance eye). Dashboard Curator debt: stamp
  `hi_dist_pct` + `vwap_side` + `seq_str` on every `triggered_ignition` row.
- G5 era: at/above level +$1.02/tr (22) vs below −— wait, below-level +$2.17/tr (43) — no split
  on stamps; the joined shadow-gate cut above (allow > block) is the cleaner read. UNDERPOWERED.

## Hand-trace: today's specimens through each gate

| gate | FIEE 09:37:41 (px 5.765→fill 5.6962) | DFSC 09:40:51 (px 2.90) |
|---|---|---|
| G1 ≥ VWAP | **REFUSE** — px 5.77 < VWAP ~6.05 (Marcos; premarket archive VWAP 6.47-6.66 agrees on side) | **REFUSE** — 2.90 < ~3.21 |
| G2 T B suffix | **REFUSE** — string all pushes/flushes, no T B | **REFUSE** — "P D D" |
| G3 ≤3% of high | **REFUSE** — ext_pct −3.8% (below the OPEN, so ≥3.8% below session high; fade) | **REFUSE [UNVERIFIED margin]** — lower-lows string into fire; exact high-distance unstamped |
| G4 D/F veto | no veto (fire bar green) — as specced, misses it | **would only catch it lookback-shifted** ("P D D" precedes the surge bar) |
| G5 level respect | **REFUSE** — shadow_gate block, level 6.00, "no_break_below_level" | **REFUSE** — block, level 3.19 |

Every gate except G4-as-specced refuses both of today's entries; G1 alone kills both.

## The stack, priced

| stack (MINE-chosen, frozen) | HOLD N | HOLD $/tr | p | winners forfeited (HOLD) | D-guard total (18 d) |
|---|---|---|---|---|---|
| UNGATED | 267 | +22.77 | — | — | $+4,276.91 (+$237.60/day) |
| **G1 only** | 221 | +29.30 | 0.000 | 12/149 ($658) | **$+4,800.46 (+$266.69/day)** |
| G3 only / G1+G3 | 152 | **+39.30** | 0.000 | 49/149 ($2,286) | $+4,515.01 (+$250.83/day) |
| G1+G2 | 63 | +27.11 | 0.267 | 110/149 ($7,694) | — |

**RECOMMENDED: G1 as the primary guidance** — on the frozen hold-out it deletes a genuinely
NEGATIVE cohort (46 fires, −$395 raw, 43% win), lifts $/tr +$6.53, is the *only* config whose
D-guard dollars beat ungated (+$523 over 18 days ≈ **+$29/day** on the universe book), forfeits
only 12/149 winners, and refuses BOTH of today's specimens. **G3 as the optional quality tier**
(biggest $/tr, 89%-of-max guard dollars, but forfeits 49 winners/$2,286 — a per-trade-quality
vs total-dollars trade Marcos must price). G2/G4/G5: no ship-candidate; G4 re-spec (pre-surge
lookback veto) and G5 go to the hypothesis registry with stamps first.

**Era-book pricing caveat (dollars-not-R):** the live era ignition book is −$1.51/day; on its own
stamps G1 would have REMOVED the −$88.52 above-VWAP... no — kept it and removed the +$43.48
below-VWAP cohort, i.e. era stamps price G1 at ≈ **−$1.9/day** (N=90, contradicting the sim's
+$22-29/day). The recommendation therefore rests on the OOS-walled sim; per
[[feedback_auditor_cannot_authorize_behavior]] and the G1 failure condition, the honest ship
shape is **stamp/shadow-first**: stamp `vwap_side` on every ignition fire, run G1 as a shadow
verdict for the proving week, enforce only on Marcos's call. **NO SHIP — Marcos decides.**
