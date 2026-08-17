# SEQ `T B` SIZE-UP CAPACITY CHECK — 8/17/26

**VERDICT: DEGRADES-AT-750 (grinder) · UNMEASURABLE-above-guard (break-attack). The
$500→$750 size-up is NOT supported on the gated cohort as a whole.**

Script: `seq_sizeup_capacity_20260817.py` (raw run: `_run.txt`, `_out.json`).
Cohort = the OOS wall's HOLD-OUT gated `T B` fires ONLY (latest 18 dates
2026-07-22..2026-08-14; break-attack N=18, grinder N=27), rebuilt through the
pilot's machinery unchanged (`sequence_mining_pilot_20260817.py` → flatten_parity
engine chain, E3 live-parity exits).

## FILL-MODEL HONESTY (read first)
The E3 engine's fills do **NOT** degrade with size: shares = POS/entry_px, exits at
model price minus a fixed −0.5% market slip, no partial fills, no price impact.
All size-dependence here comes from round D's pre-registered model, reused EXACTLY
(consistency with the standing 8/14 refutation over a new model):
- signal-bar 10s dollar-volume guard, 5% participation: dv ≥ 20·C → full clip C;
  dv ≥ 10·C → half clip; else skipped-for-size ($0).
- chase entry slip anchored to D's two points ($500→−1.0%, $1,000→−1.5%), linear:
  $750→−1.25%, $1,500→−2.0%. **[CALIBRATION UNKNOWN] above $500 — $750/$1,500 are
  extrapolated assumptions, not measurements** (D's own flag, still unpaid: no live
  fills above $500 exist).
Therefore this check can only **BOUND** the size-up, not prove live capacity. Any
"scales fine" reading below is a model artifact ceiling, not evidence.

## TAPE CONTEXT — the gated fires live on thin tape
| lane | N | fire-bar dv median | min | <$10k fire bars | $750 as % of fire-bar dv (med / worst) | next-3-bar dv med |
|---|---|---|---|---|---|---|
| break-attack | 18 | $6,629 | $8 | **10/18 = 56%** | **11.3% / 9,470%** | $20,687 |
| grinder | 27 | $7,111 | $5 | **17/27 = 63%** | **10.5% / 15,632%** | $5,975 |

The MAJORITY of gated fires print on <$10k bars — the exact thin-tape danger zone
of the 8/14 finding. A $750 clip is ~11% of the median fire bar's traded dollars
(>2× the 5% participation ceiling); worst case it is 95×–156× the bar. The gated
cohort is the SAME thin-tape edge D diagnosed, not an exception to it.

## SIZED RE-SIMS (D-parity guard + slip, per clip)

### break-attack `T B` (N=18)
| clip | full/half/skip | filled | total $ | $/fire (skips=$0) | $/filled |
|---|---|---|---|---|---|
| $500 | 8/1/9 | 9 | +$320.11 | +$17.78 | +$35.57 |
| $750 | 8/1/9 | 9 | +$470.11 | +$26.12 | +$52.23 |
| $1,000 | 8/0/10 | 8 | +$566.19 | +$31.46 | +$70.77 |
| $1,500 | 8/0/10 | 8 | +$810.56 | +$45.03 | +$101.32 |

Wall's own headline (flat $500 chase, NO guard): **+$54.43/fire** — half the fires
behind that number sit on bars the guard says can't absorb even $500 (guard-passing
$500 book: +$17.78/fire). The rising totals at bigger clips are pure linear scaling
of 8 liquid winners under an assumed slip — the engine cannot make them lose to
size. **UNMEASURABLE above the guard: the liquid-8 subset "scaling" is a model
ceiling, not proof; the other 10 fires (56%) are untradeable at ANY of these clips
per the guard.**

### grinder `T B` (N=27)
| clip | full/half/skip | filled | total $ | $/fire (skips=$0) | $/filled |
|---|---|---|---|---|---|
| $500 | 10/6/11 | 16 | +$499.46 | +$18.50 | +$31.22 |
| $750 | 6/6/15 | 12 | **+$439.00** | **+$16.26** | +$36.58 |
| $1,000 | 5/5/17 | 10 | +$340.46 | +$12.61 | +$34.05 |
| $1,500 | 4/2/21 | 6 | +$225.64 | +$8.36 | +$37.61 |

Wall headline (flat $500, no guard): +$45.63/fire. **Monotonic degradation with
clip: total dollars fall $499 → $439 → $340 → $226 as the guard strips the thin
fires the edge actually lives on.** At $750 the book trades only 12/27 of the
gated fires and makes LESS total money than $500 while risking 1.5× per trade —
measurable degradation at the very first step up. This is D's inversion mechanism
reproduced on the gated cohort: sizing up deletes the paying cohort.

## VERDICT (no rounding up)
1. **grinder `T B`: DEGRADES-AT-750.** Total $ and $/fire both fall at $750
   (+$18.50 → +$16.26/fire; +$499 → +$439 total on MORE capital), and keep falling
   monotonically. Do not size the grinder lane up.
2. **break-attack `T B`: UNMEASURABLE with our fill model.** 56% of its fires are
   thin-bar untradeable per the guard at any clip; the remaining 8 liquid fires
   "scale" only because the engine's fills are size-linear under an uncalibrated
   slip assumption. A per-fire liquidity-conditional clip (full size ONLY when
   fire-bar dv ≥ $15k, i.e. $750 ≤ 5%) is the registrable follow-up — but it is a
   NEW behavior and per doctrine goes back to Marcos priced, with live $750 fill
   calibration owed first.
3. **Blanket $500→$750 on `T B` fires: NOT supported.** The gated cohort is
   majority thin-tape (56%/63% <$10k fire bars); the 8/14 thin-tape refutation
   applies to it with full force.
4. Caveat both directions (D's own): the guard reads ONE 10s bar; break-attack's
   next-3-bar dv (median $20.7k) suggests real tradability is somewhat better than
   the single-bar guard shows; grinder's next-3 median ($6.0k) says it is NOT.

## Officers touched
Wind Tunnel Engineer (D-model reuse, guard generalization), Execution Surgeon
(slip-above-$500 [CALIBRATION UNKNOWN] re-flagged; participation ceiling math),
Convexity Trader (verdicts; grinder monotone decay), Systems Quant (cohort N=18/27
reconciled exact to the wall's JSON; same E3 path), Statistician (this entry +
artifacts committed), Momentum Operator (no size-up on noise; bound-only reading
enforced), Feed Engineer (10s dv proxy, single-bar strictness disclosed), Side
Marshal / Crown Steward / Handicapper / Historian / Seam Scientist: clean (raw
gated-lane capacity test, no gate stack or side logic in scope).
