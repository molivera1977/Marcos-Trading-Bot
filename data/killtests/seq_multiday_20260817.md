# MULTI-DAY SEQUENCE STUDY — day-1 character vs day-2 fires (8/17/26)

**Question:** does day-1's character predict day-2's fires (break-attack + grinder, E3 $500)?
**Answer: CANNOT BE ANSWERED YET — a DATA-COVERAGE finding, not a verdict.** Every hypothesis is
**UNDERPOWERED** at the OOS-cell level. Numbers below are descriptive only.

- **Script:** `data/killtests/seq_multiday_20260817.py` · raw run `..._run.txt` · json `..._out.json`
- **Engine:** fires from `sequence_mining_pilot_20260817.py` (`gen_lane`/`grade`), the unchanged
  `S -> G -> F -> C -> B -> E` flatten-parity chain; every fire exits **E3 live-parity, $500 clip**.
- **OOS protocol** (from `seq_gate_oos_wall_20260817.py`): split BY DAY-2 DATE — MINE
  2026-05-18..2026-07-21, HOLD-OUT 2026-07-22..2026-08-14; a pair belongs to the split of its day-2 date.
- Analysis only. No bot edits.

---

## PAIR INVENTORY (the headline finding)

- Universe: 729 files / 729 name-days / 62 dates 2026-05-18..2026-08-14 (`data/universe/bars10s`).
- **68 pairs** — (ticker, d1, d1+next-trading-day) with BOTH days in the loaded universe — across
  53 distinct tickers. Split: **MINE 49 pairs / HOLD-OUT 19 pairs**.
- 68 >= the 30-pair floor, so the study proceeded — but the binding constraint turned out to be
  **fires**, not pairs: of 1,021 total BA+grinder fires, only **80 land on a pair's day-2 tape**
  (58 BA / 22 grinder), **62 MINE / 18 HOLD-OUT**. Once split by any day-1 label, every HOLD-OUT
  cell falls under the 15-fire floor (one cell is N=0). **The universe is built of mostly
  one-day-wonder captures** — same-name consecutive-day coverage is the scarce resource.

### Label prevalence (68 pairs)
| label | pairs |
|---|---|
| H1 day-1 strong close (top 25% of RTH range) | 10 |
| H2 day-1 halt-ladder (>=2 zero-trade gaps >=60s in 10s tape) | 38 |
| day-2 gapped above day-1 high | 30 (held first 15 min: 22 · failed: 8) |
| H4 day-1 quiet tape (median 10s range < universe median 0.766%) | 30 |

---

## Per-hypothesis descriptive stats (E3 $/trade; NOT verdicts)

| hyp | cohort | A | B | $/tr diff (A−B) |
|---|---|---|---|---|
| **H1 CONTINUATION** | MINE | strong-close N=18, 78%, $+24.71/tr | weak-close N=44, 61%, $+12.44/tr | $+12.26 |
| | HOLD-OUT | strong-close **N=0** | weak-close N=18, 72%, $+42.84/tr | — |
| **H2 DAY-2 FADE** (two-sided) | MINE | halt-ladder N=27, 70%, $+21.98/tr | no-ladder N=35, 63%, $+11.39/tr | $+10.59 |
| | HOLD-OUT | halt-ladder N=7, 71%, $+6.71/tr | no-ladder N=11, 73%, $+65.82/tr | $−59.11 (sign flips) |
| **H3 GAP-HOLD** | MINE | gap-hold N=23, 57%, $−1.58/tr | gap-fail N=5, 20%, $−31.02/tr | $+29.44 |
| | HOLD-OUT | gap-hold N=2 | gap-fail N=3 | $−6.10 (cells of 2 and 3) |
| **H4 QUIET-THEN-LOUD** | MINE | quiet N=39, 67%, $+10.70/tr | loud N=23, 65%, $+25.00/tr | $−14.29 |
| | HOLD-OUT | quiet N=6, 50%, $+22.81/tr | loud N=12, 83%, $+52.85/tr | $−30.04 |

Permutation nulls (5000x day-1 label shuffles across pairs) were pre-wired but never reached — no
hypothesis cleared the cell-size floor to earn one.

### Descriptive reads (hypotheses for a re-run, nothing more)
- **H4 runs AGAINST its registration in BOTH halves**: loud day-1 tapes precede the better day-2
  fires ($−14 MINE, $−30 HOLD-OUT). Consistent sign, but N too thin to call. If anything survives a
  better-powered re-run, it may be **LOUD-then-loud**, not quiet-then-loud — worth flagging to the
  `joint_door_20260816.md` thread as a directional surprise.
- H1 and H2 both flip sign between MINE and HOLD-OUT — no stable read.
- H3's MINE direction (gap-hold >> gap-fail, $+29/tr) matches intuition but HOLD-OUT has 5 fires total.

---

## VERDICTS

| hypothesis | verdict | why |
|---|---|---|
| H1 CONTINUATION | **UNDERPOWERED** | HOLD-OUT strong-close cell N=0 (MINE 18/44) |
| H2 DAY-2 FADE | **UNDERPOWERED** | HOLD-OUT cells 7/11 fires — under the 15 floor |
| H3 GAP-HOLD | **UNDERPOWERED** | MINE gap-fail N=5; HOLD-OUT 2/3 |
| H4 QUIET-THEN-LOUD | **UNDERPOWERED** | HOLD-OUT cells 6/12; direction opposite registration (descriptive) |

**The data-coverage finding:** the bars10s universe rarely carries the SAME name on consecutive
dates (68 pairs / 729 name-days ≈ 9%). Any multi-day study needs the capture service to deliberately
**re-capture yesterday's names** (day-2 follow-through tapes), or a historical SIP backfill of d+1
for the existing 729 name-days — a Quartermaster item, not a mining item.

## Caveats
- Day-1 "range/close" is RTH bars only (13:30–20:00Z); day-2 "open" = first RTH bar's open, so H3's
  "gap" is measured RTH-open vs day-1 RTH high (no premarket in the pair labels).
- Universe selection is momentum-biased both days (a name is only IN the cache because it moved);
  pair labels are conditioned on that survivorship.
- WIN blends E3 $>0 with +1R-before-stop (pilot convention); $/tr is pure E3 dollars, $500 clip.

*No recommendation. UNDERPOWERED across the board — the deliverable is the inventory number and the
re-capture requirement. Officers touched: Quartermaster (coverage gap), Seam Scientist / Forward
Architect (H4 directional surprise registered as hypothesis), Statistician (run artifacts saved),
Side Marshal (clean), Wind Tunnel (clean).*
