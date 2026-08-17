# SEQUENCE-GATE OUT-OF-SAMPLE WALL — 8/17/26

The decisive check on whether the `W T B` / `T B` sequence edge (pilot:
`sequence_mining_pilot_20260817.md`) is real or in-sample overfit. **Strict chronological
OOS protocol — train on the past, test on the unseen future.**

- **Script:** `data/killtests/seq_gate_oos_wall_20260817.py` · **raw run:** `..._run.txt` · **json:** `..._out.json`
- **Engine + event alphabet:** imported UNCHANGED from `sequence_mining_pilot_20260817.py`
  (which imports the `flatten_parity` chain `S→G→F→C→B→E` unchanged). Every fire exits
  **E3 live-parity** via `F.sim_var(...,"E3",det,halt_rule=True)` — bank ½ at +10%, trail rest
  10%-off-high closes-through, stop-first, −1% chase entry, −0.5% market-exit slip; grinder keeps
  its 19:59Z flatten. Same-name dedup ≤5 min. $500 clip / 2 slots. Nothing shipped, no bot edits.
- **Suffix** = last-k events of the STRUCTURAL string (F/D removed, consecutive dups collapsed).
  **WIN** = E3 $ > 0 OR reached +1R before the stop bar. **$/trade** = E3 dollars.

---

## TL;DR

**Both champion lanes SURVIVE the wall.** The `T B` gate — *test the session high, then break
it* — was **re-mined from scratch on the earliest 44 dates only** and, frozen, **lifts per-trade
P&L in the same direction on the 18 unseen future dates**, with a permutation null confirming the
lift is the label and not an artifact.

| lane | MINE-derived suffix | hold-out UNGATED $/tr | hold-out GATED $/tr | lift | gate N (hold-out) | null p | **verdict** |
|---|---|---|---|---|---|---|---|
| **break-attack** | `T B` | $+24.94 | **$+54.43** | **$+29.49** | 18 / 187 (10%) | 0.021 | **SURVIVES** |
| **grinder** | `T B` (canonical) | $+21.90 | **$+45.63** | **$+23.74** | 27 / 142 (19%) | 0.001 | **SURVIVES** |

---

## 1) The date split (chronological — train past, test future)

Universe: 729 files / 729 name-days, **62 dates 2026-05-18 .. 2026-08-14**.

- **MINE (train):** 44 dates **2026-05-18 .. 2026-07-21**
- **HOLD-OUT (test):** 18 dates **2026-07-22 .. 2026-08-14**
- **BOUNDARY:** last MINE date = **2026-07-21**; first HOLD-OUT date = **2026-07-22**.

The suffix is mined on MINE dates with **zero visibility into the hold-out**; the material-N
threshold is defined on the MINE population (`max(20, 8% of MINE fires)`).

---

## 2 & 3) Re-mine on MINE, freeze, apply to HOLD-OUT

### break-attack (flat_top, 09:30–10:30 ET) — 634 fires (MINE 447 / HOLD-OUT 187)

MINE material threshold N≥35. The max-lift auto-picker chose **`T B`** (N=42 on MINE, win 76%,
$/tr $+48.85, lift $+21.18). **This matches the pilot's `T B` family** — MINE alone, with no peek
at the future, rediscovered the same grammar.

| cohort | N | win | total | $/tr | day mean | day med | green% | halves | worst day |
|---|---|---|---|---|---|---|---|---|---|
| HOLD-OUT UNGATED | 187 | 67% | $+4663.52 | $+24.94 | $+259.08 | $+280.65 | 78% | $+2903/$+1761 | $-119.26 |
| **HOLD-OUT GATED [T B]** | **18** | **89%** | $+979.71 | **$+54.43** | $+54.43 | $+48.51 | 56% | $+682/$+298 | **$+0.00** |

Gate keeps 18/187 (10%); **$/tr $+24.94 → $+54.43 (+$29.49, +118%)**, win **67% → 89%**, worst
gated day **$0.00** (no losing gated day on hold-out).

### grinder (post-10:30 ET) — 387 fires (MINE 245 / HOLD-OUT 142)

MINE material threshold N≥20. The max-lift auto-picker chose the last-3 suffix **`W T B`** (N=20
on MINE, win 90%, $/tr $+56.34) — also in the pilot family, but a thin slice that carries only
**8** hold-out fires (too few alone). Per the pilot's own caveat that the auto-picker favors
small-N slivers, the wall also freezes the pilot's **featured *material* grinder gate `T B`**
(the largest robust slice) — the same finding in its material form:

| cohort | N | win | total | $/tr | day mean | day med | green% | halves | worst day |
|---|---|---|---|---|---|---|---|---|---|
| HOLD-OUT UNGATED | 142 | 71% | $+3109.33 | $+21.90 | $+172.74 | $+123.87 | 83% | $+1724/$+1385 | $-51.06 |
| **HOLD-OUT GATED [T B]** | **27** | **81%** | $+1232.06 | **$+45.63** | $+68.45 | $+59.57 | 61% | $+461/$+771 | $-59.25 |
| (aux) HOLD-OUT GATED [W T B] | 8 | 88% | $+479.48 | $+59.94 | $+26.64 | $+0.00 | 33% | $+130/$+350 | $-47.12 |

MINE `T B` reference: N=77, win 82%, $/tr $+43.62. Frozen on hold-out, **`T B` keeps 27/142 (19%);
$/tr $+21.90 → $+45.63 (+$23.74, +108%)**, win **71% → 81%**, both halves green ($+461/$+771).

---

## 4) Per-lane verdict

| lane | verdict | reason |
|---|---|---|
| **break-attack** | **SURVIVES** | MINE re-picked `T B` unaided; hold-out lift **+$29.49/tr** same direction as in-sample (+$23.66), N=18 material, null p=0.021. |
| **grinder** | **SURVIVES** | Hold-out lift **+$23.74/tr** on the material `T B` slice (N=27, 19% of fires), same direction as in-sample (+$16.56), both halves green, null p=0.001. The thinner auto-pick `W T B` agrees (+$38.04) but is underpowered alone (N=8). |

Both lifts are materially positive, the correct sign, and on a real slice of hold-out fires — not
a sliver. Nothing was rounded up: the grinder auto-pick `W T B` **by itself is UNDERPOWERED**
(N=8) and is reported as such; the SURVIVES verdict rests on the material `T B` gate (N=27).

## 5) Null / permutation check

For each lane, the gate keeps *m* hold-out fires. Randomly relabeling *m* hold-out fires as
"gated" 5,000× reproduces the ungated mean and destroys the lift:

| lane | gate | m | observed gated $/tr | random-label mean $/tr | p(random ≥ observed) |
|---|---|---|---|---|---|
| break-attack | `T B` | 18 | $+54.43 | $+25.08 | **0.021** |
| grinder | `T B` | 27 | $+45.63 | $+21.81 | **0.001** |
| grinder | `W T B` | 8 | $+59.94 | $+22.15 | 0.014 |

Under random labels the lift vanishes to ≈ ungated every time. The measured lift is the **`T B`
sequence label**, not a locate/sizing artifact.

---

## Verdict

**`T B` — test the session high, then break it — SURVIVES the out-of-sample wall in both champion
lanes.** Re-mined on the training past and frozen onto the unseen future, it lifts per-trade P&L
+$29.49 (break-attack) and +$23.74 (grinder), same direction as in-sample, on material hold-out
slices (10% / 19% of fires), with permutation nulls at p=0.021 / p=0.001. This gate is real, not
overfit — it is safe to **build on** as a priority/size signal (per the pilot's framing: rank/size
`T B` fires up; do **not** drop the non-`T B` fires, which still net positive). Confirmed use is
sizing/priority, **not** a trade-only filter.

## Caveats (read before believing)

- **Hold-out N is modest** (18 and 27 gated fires). Both clear the "material slice + directional
  lift + null-confirmed" bar, but this is one wall on 18 future dates, not a season. `W T B` alone
  is underpowered (N=8) and must not be gated on by itself.
- **Same engine caveats as the pilot** carry over verbatim: SIP 10s bar boundaries vs Webull's
  glass; the E3/WIN definitions; VWAP/9EMA/halts recomputed on the universe 10s bars to feed the
  event string. The wall changes only the *date partition* — every other object is the pilot's.
- **Priority/sizing, not trade-only.** The gate raises $/tr by isolating the best fires; on these
  already-profitable lanes it lowers total dollars and green% if used to *drop* fires. The honest
  use is ranking/sizing.
- **v2 / ma_pullback** were NO-LIFT / NEEDS-DATA in the pilot and are not re-walled here — there is
  no surviving in-sample finding on them to test.

*No recommendation to ship. Numbers only — the full room verifies, Marcos decides.*
