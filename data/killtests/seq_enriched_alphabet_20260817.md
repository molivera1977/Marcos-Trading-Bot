# ENRICHED-ALPHABET SEQUENCE MINING — 8/17/26

Marcos: *"types of sequences that haven't been considered — velocity, volume."* Question: does
enriching the price-structure alphabet with VOLUME STATE and VELOCITY split the OOS-proven `T B`
suffix into a good half and a bad half? **Answer: NO — nothing survives. 18/20 pre-registered
cells UNDERPOWERED, 2 NO-SPLIT, 0 ENRICHMENT-PAYS.** The `T B` parent cohorts are simply too
small out-of-sample (18 BA / 27 grinder hold-out fires) for any subtype to be judged, and the
subtypes that looked strong on MINE **flipped sign on HOLD-OUT** — the overfit signature.

- **Script:** `seq_enriched_alphabet_20260817.py` · raw `..._run.txt` · json `..._out.json`
- **Split (wall parity, asserted in-code):** MINE 2026-05-18..07-21 (44d) | HOLD-OUT 07-22..08-14 (18d)
- **Engine:** pilot chain unchanged, E3 live-parity $500; guard grading = D-guard
  (dv≥20C full / ≥10C half / skip, extrapolated slip — same [CALIBRATION UNKNOWN] as before).
- **Nulls:** 5000-relabel permutation **within the hold-out `T B` parent cohort** — the null is
  the subtype question, not the already-proven `T B` question.

## Enriched alphabet spec (v2 candidate)

Window = same 60×10s bars ending at the fire bar; base B/T/P/W/H/R/L/Q walk copied verbatim.

| channel | tokens | definition |
|---|---|---|
| volume case | `B!`/`b`, `T!`/`t`, … | price event's bar vol ≥ p75 of prior 30 → UPPER+`!`; else lowercase |
| pure volume | `U` | 3 consecutive down/sideways bars, monotonically shrinking volume (dry-up) |
| | `X` | vol ≥ p90 and \|close chg\| ≤ 0.3% (climax w/o progress) |
| velocity | `>` / `<` | mean bar range last 3 ≥ 1.5× prior 6 / ≤ 0.6× |
| seq velocity | FAST/SLOW | bars between last `T` and terminal `B`: ≤6 vs >6 |
| effort/result | `A` | vol ≥ p75, \|close chg\| ≤ 0.2% (absorption) |
| | `V` | close chg ≥ +1% on vol ≤ p25 (vacuum) |

Structural convention preserved (F/D variants dropped, consecutive dups collapsed).

## Pre-registered hypotheses — full results (within `T B` parent cohort)

### break-attack — MINE `T B` N=42 ($+48.85/tr), HOLD-OUT N=18 ($+54.43/tr raw, $+17.78 guard)

| hypothesis | MINE lift | HOLD-OUT lift | guard lift | null p | verdict |
|---|---|---|---|---|---|
| H1 `t B!` quiet test→burst break | −$29.48 (12/30) | +$23.51 (4/14) | +$19.75 | 0.239 | UNDERPOWERED |
| H2 `T! b` burst test→fade break | −$27.79 (5/37) | n/a (0/18) | — | — | UNDERPOWERED |
| H3 `T! B!` both burst | **+$39.00** (21/21) | **−$71.88** (7/11) | −$15.65 | 0.998 | UNDERPOWERED (sign FLIP) |
| H4 `t b` both quiet | −$9.52 (4/38) | +$54.78 (7/11) | +$1.28 | 0.045 | UNDERPOWERED (sign flip; guard kills it) |
| H5 FAST ≤6 bars T→B | +$42.71 (40/2) | degenerate (18/0) | — | — | UNDERPOWERED (no SLOW population) |
| H6 U dry-up before B | +$26.65 (36/6) | −$115.97 (16/2) | −$9.84 | 0.954 | UNDERPOWERED (sign FLIP) |
| H7 A absorption before B | +$48.33 (38/4) | +$11.09 (17/1) | +$18.83 | 0.395 | UNDERPOWERED (near-saturated) |
| H8 `>` pace-expansion into B | +$44.61 (25/17) | −$19.17 (7/11) | −$7.13 | 0.691 | UNDERPOWERED (sign flip) |
| H9 X climax before B | +$41.72 (32/10) | −$7.27 (14/4) | −$15.95 | 0.626 | UNDERPOWERED |
| H10 V vacuum before B | **+$63.53** (29/13) | −$30.14 (10/8) | +$3.96 | 0.799 | UNDERPOWERED (sign FLIP) |

### grinder — MINE `T B` N=77 ($+43.62/tr), HOLD-OUT N=27 ($+45.63/tr raw, $+18.50 guard)

| hypothesis | MINE lift | HOLD-OUT lift | guard lift | null p | verdict |
|---|---|---|---|---|---|
| H1 `t B!` | +$16.03 (17/60) | +$38.63 (4/23) | −$3.64 | 0.096 | UNDERPOWERED (raw/guard disagree) |
| H2 `T! b` | +$5.95 (7/70) | −$28.14 (6/21) | −$33.88 | 0.853 | UNDERPOWERED |
| H3 `T! B!` | −$15.65 (45/32) | +$3.68 (16/11) | +$29.00 | 0.430 | **NO-SPLIT** |
| H4 `t b` | +$5.92 (8/69) | −$25.26 (1/26) | −$19.21 | 0.777 | UNDERPOWERED |
| H5 FAST ≤6 bars | −$47.81 (75/2) | +$7.40 (25/2) | −$10.39 | 0.388 | UNDERPOWERED (no SLOW population) |
| H6 U dry-up before B | +$33.90 (70/7) | −$13.69 (26/1) | +$19.21 | 0.706 | UNDERPOWERED (near-saturated) |
| H7 A absorption before B | $0.00 (77/0) | −$17.12 (26/1) | +$19.21 | 0.755 | UNDERPOWERED (**saturated 77/0**) |
| H8 `>` into B | −$4.45 (43/34) | +$11.36 (20/7) | −$5.08 | 0.333 | UNDERPOWERED (sign flip) |
| H9 X climax before B | $0.00 (77/0) | −$102.44 (26/1) | −$56.18 | 0.955 | UNDERPOWERED (**saturated 77/0**) |
| H10 V vacuum before B | +$32.77 (34/43) | +$11.38 (16/11) | +$8.36 | 0.301 | **NO-SPLIT** (same direction, null p=0.30 — not distinguishable from random) |

## Open enriched-suffix mining (material-N = max(15, 6% of MINE fires))

- **break-attack:** best `B! >` (burst break + pace expansion) — MINE N=54, lift +$6.28;
  frozen on HOLD-OUT: N=14, raw lift +$10.71, guard $+14.85 vs $+4.84 ungated, **null p=0.240**.
  Same direction in-and-out of sample but indistinguishable from a random 14-fire draw.
- **grinder:** best `Q B!` (compression → burst break) — MINE N=15, lift +$16.54; frozen on
  HOLD-OUT: N=7, raw lift +$2.48, **under guard NEGATIVE** ($−0.13 vs $+6.16), null p=0.425. Dead.

## Findings (nulls are findings)

1. **VELOCITY DOESN'T SPLIT `T B` — and mostly CAN'T.** The FAST/SLOW T→B split is degenerate:
   at 10s resolution with dup-collapse, 95%+ of `T B` fires are FAST (≤6 bars) — BA 40/2 MINE,
   18/0 HOLD; grinder 75/2, 25/2. There is no SLOW population to trade against. Pace tokens
   (`>`/`<`) flipped sign MINE→HOLD in both lanes. **Velocity, as defined here, adds nothing.**
2. **VOLUME-CASE subtypes are overfit at this N.** BA `T! B!` went +$39.00 MINE → −$71.88 HOLD
   (null p=0.998 — the observed subtype is WORSE than 99.8% of random splits). U-before-B went
   +$26.65 → −$115.97. When half the strong MINE cells flip sign out-of-sample, the honest read
   is noise on a 42-fire cohort, not signal.
3. **A and X are broken detectors on this tape, not hypotheses.** In grinder they saturate
   (77/77 and 77/77 of `T B` fires carry them) — near the session high on a runner, p75/p90
   volume thresholds over the prior 30×10s bars are nearly always met. They need stricter
   definitions (e.g. vs full-session distribution) before they can ever discriminate.
4. **The `T B` parent is the binding constraint.** 18 (BA) and 27 (grinder) hold-out parent
   fires cannot power ANY binary subtype test at MIN_N=10 both sides. Re-testing is owed only
   after the hold-out window grows (more trading days), not by relaxing thresholds.
5. **The only candidate with consistent direction:** `B! >` on break-attack (positive MINE and
   HOLD-OUT, raw and guard) — but null p=0.240. **Candidate for alphabet v2 stamping
   (observe-only), not for any behavior.**

## VERDICT

**NO ENRICHMENT-PAYS. `T B` stays as-is; the enriched channels are not ship candidates.**
If the live `seq_str` stamp ever grows an alphabet v2, the single strongest candidate is the
**volume-case on the break itself (`B!` vs `b`) plus the trailing `>`** — the only enrichment
positive in both samples under both fill models — stamped **data-only** so a real-N verdict can
accumulate. A/X definitions must be rebuilt before reuse. Everything else: refuted or
underpowered, per the tables above.

*Analysis only. No bot edits. Officers touched: Side Marshal (owns subtype registry — the
frozen hypotheses land in his docket), Seam Scientist (one-day-humility protocol honored via
OOS wall), Statistician (this file = the ledgered artifact), Systems Quant (saturated A/X
detectors flagged), Wind Tunnel (guard slip still [CALIBRATION UNKNOWN] above $500 — clean
otherwise). Marcos decides.*
