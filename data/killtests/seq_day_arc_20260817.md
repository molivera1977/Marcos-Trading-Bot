# DAY-ARC SEQUENCE STUDY — the day as one string (8/17/26)

Does the MORNING's arc predict which fires pay later — the setup-not-clock version of the
windows finding (expansion morning / survival afternoon)? Analysis only, no bot edits.

- **Script:** `data/killtests/seq_day_arc_20260817.py` · raw: `..._run.txt` · json: `..._out.json`
- **Universe:** FULL bars10s — 729 files/name-days, 62 dates 2026-05-18..2026-08-14.
- **Day string:** one letter per 15-min phase, 07:00-16:00 ET (36 phases), precedence
  **B** (new session high in phase) > **F** (new post-09:30 session low) > **V** (range≥4%, |net|<1%)
  > **U** (net>+1%) > **D** (net<−1%) > **R** (|net|<1%; coarse fallback). Session VWAP =
  premarket-anchored (settled doctrine), phase "above" = phase-end close > VWAP.
- **Fires/exits:** break-attack (634) + grinder (387) + v2 (6,159) from the pilot generators
  (`sequence_mining_pilot_20260817.py`), **E3 $500 live-parity, imported UNCHANGED**.
- **Protocol (pre-registered):** OOS wall split — MINE 05-18..07-21 (44 dates) / HOLD-OUT
  07-22..08-14 (18 dates). Freeze a cell only if both sides N≥15 AND MINE $/tr gap ≥ $10 in the
  hypothesized direction; verify frozen on HOLD-OUT; null = 5,000× name-day condition-label
  permutation (one-sided).

---

## TL;DR

**One hypothesis survives the wall: H1 — the coil-then-break morning.** Fires on days whose
pre-10:30 arc shows **R→B (range phase, then the break phase)** beat gap-and-go days in the
break-attack lane **on MINE (+$10.08/tr) AND on HOLD-OUT (+$21.74/tr, $+34.14 vs $+12.40,
win 72% vs 50%, N 82/36, p=0.043)**. The morning that *coils first* is the morning whose
breaks pay; the day that opens already breaking (gap-and-go) pays a third as much per trade.
H2 (VWAP-held morning → afternoon fires) found nothing. H3 (flush-then-rip) and H4 (quiet
open) looked right on MINE but are too thin on HOLD-OUT to judge.

## Verdicts (one line each)

| hyp | condition | MINE split (TRUE vs FALSE $/tr) | HOLD-OUT split | p | VERDICT |
|---|---|---|---|---|---|
| **H1** | pre-10:30 arc has R→B vs gap-and-go (BA lane) | **+$36.82 (N163) vs +$26.74 (N74), gap +$10.08** | **+$34.14 (N82) vs +$12.40 (N36), gap +$21.74** | **0.043** | **ARC-PREDICTS** |
| H2 | afternoon fires, morning ≥75% phases above VWAP (grinder) | +$11.89 (N64) vs +$18.79 (N71), gap −$6.90 — wrong direction | not frozen | — | **NO-SPLIT** |
| H3 | pre-10:00 F then B vs no-flush (grinder) | +$48.16 (N20) vs +$29.67 (N223), gap +$18.49 → frozen | +$29.45 (**N=8**) vs +$21.45 (N134), gap +$8.00 | 0.324 | **UNDERPOWERED** (hold-out N=8) |
| H4 | first two phases R R (grinder = the registered lane) | +$18.40 (**N=12**) vs +$25.31 (N121) — under N floor | not frozen | — | **UNDERPOWERED** |

Per-lane detail for every cell (12 cells) is in `_run.txt`; non-judged lanes in brief:
- H1 grinder gap −$4.10 (MINE, no freeze) and v2 −$1.17 — the coil-then-break split is a
  **break-attack** phenomenon, consistent with it being about the *morning break* itself.
- H2 break-attack has 0 afternoon fires by construction (09:30-10:30 window); v2 afternoon
  gap +$1.61 — noise. The "held-above-VWAP morning" idea earns nothing anywhere.
- H3 v2 gap −$0.37; H3 break-attack +$3.94 — flush-then-rip is grinder-only and thin.
- H4 break-attack MINE was striking (+$72.69 vs +$21.53, N 27/319 — the joint_door
  quiet-tape echo) **but did not survive**: HOLD-OUT +$30.18 vs +$27.10 on N=7, p=0.437.
  Registered as the same selection direction joint_door found, still unproven at day-arc grain.

## Reading H1 honestly (caveats before believing)

1. **Partial circularity.** Break-attack fires ARE session-high breaks inside 09:30-10:30; a
   pre-10:30 R→B phase pair can be *the fire's own phase*. So H1 partly restates "breaks out
   of a coil beat breaks out of a gap" — which is exactly the pilot's `T B` (test-then-break)
   finding at day grain, not an independent new signal. The two should be treated as ONE
   doctrine: **accumulate/coil under the high, then break** pays; break-without-coil doesn't.
2. **p=0.043 with 12 cells tested.** One-sided, marginal; a Bonferroni-minded reader calls it
   suggestive. It is the only cell that was frozen on MINE and confirmed direction AND size
   on HOLD-OUT — that chronology (mine→freeze→future) is the real defense, not the p alone.
3. **Gap-and-go days are still GREEN** (+$12.40/tr hold-out). H1 is a priority/size split,
   not a do-not-trade filter — same honest use as the pilot's `T B` gate.
4. Day-gain reference/premarket VWAP anchored at the file's first bar (08:00Z); no prior
   close in the cache (standing caveat). ET=UTC-4 all summer.

**Not a ship. Registered hypothesis for Side Marshal / First Hour / Handicapper:** stamp the
morning arc (data-only row) live; H1 joins the `T B` suffix as two grains of the same
coil-then-break doctrine. Marcos decides anything that touches money.

*Officers touched: Side Marshal (day-side context — H1 owner), First Hour (H1/H2 windows),
Seam Scientist (hypothesis registry), Statistician (splits/null), Wind Tunnel (E3 parity —
clean, engine imported unchanged), Historian (clean). No behavior change proposed.*
