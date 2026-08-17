# EXIT-SIDE SEQUENCE GRAMMAR — 8/17/26

Question: is there a DISTRIBUTION grammar — an event sequence AFTER entry that says LEAVE —
that beats mechanical E3 (bank 1/2 at +10%, 10%-off-run-high trail) on the same champion-lane
fires? Motivated by EYES_MATRIX_20260816 finding: **E3 consults ZERO eyes at exit.**

- **Script:** `seq_exit_grammar_20260817.py` · raw run `..._run.txt` · json `..._out.json`
- **Engine:** PILOT fire generators (`sequence_mining_pilot_20260817.py`) + `S.run` E3 control,
  chain unchanged. My E3 clone reproduces `S.run`/`F.sim_var` **to $0.000000** on all 1,021 fires
  (sanity line in the run). $500 clips, +1% chase, −0.5% exit slip, halt rule, grinder 19:59Z
  flatten, same-name dedup ≤5 min.
- **OOS protocol** (`seq_gate_oos_wall_20260817.py`, unviolated): MINE = 44 dates
  2026-05-18..07-21 · HOLD-OUT = 18 dates 2026-07-22..08-14. Winner frozen on MINE only.
- **Pre-registered triggers** (pattern OR E3, whichever first; pattern = sell ALL remaining at
  that 10s close −0.5%; 3-min warmup; per-bar order stop → bank → run-hi → pattern → trail):
  **H1** X→lower-high→lower-low (X = vol≥p90-of-trade & |chg|≤0.3%) · **H2** climax bar
  (vol≥p95 & range≥2× median) exit into strength · **H3** first lower low after the run-high
  (aggressive) · **H4** two consecutive fade-volume pushes · **H5** = E3 control.

## Results (day-mean, $; full tables in `_run.txt`)

### flat_top BREAK-ATTACK (634 fires: 447 MINE / 187 HOLD-OUT)

| variant | MINE day-mean | MINE worst | HOLD-OUT day-mean | avg hold | giveback recovered |
|---|---|---|---|---|---|
| **E3 control** | **$+281.08** | $−121.42 | **$+259.08** | 75–102m | — |
| H1 X-LH-LL | $+24.68 | $−193.68 | $+7.28 | 17m | 40–43% |
| H2 climax | $+64.75 | $−166.89 | $+87.96 | 25m | 46–50% |
| H3 first-LL | $−37.78 | $−181.97 | $−64.46 | 6m | 54–55% |
| H4 fade-pushes | $−1.43 | $−171.51 | $−25.34 | 11m | 50–51% |

### GRINDER (387 fires: 245 MINE / 142 HOLD-OUT)

| variant | MINE day-mean | MINE worst | HOLD-OUT day-mean | avg hold | giveback recovered |
|---|---|---|---|---|---|
| **E3 control** | **$+184.56** | $−175.04 | **$+182.90** | 80–83m | — |
| H1 | $+24.31 | $−78.17 | $+54.29 | 14m | 40–55% |
| H2 | $+70.56 | $−69.24 | $+64.11 | 22–26m | 40–57% |
| H3 | $−4.09 | $−91.48 | $−1.99 | 7m | 50–65% |
| H4 | $+33.85 | $−94.78 | $+41.16 | 11–13m | 49–63% |

## VERDICTS

| lane | verdict | why |
|---|---|---|
| **break-attack** | **NO-LIFT** | best pattern (H2) MINE day-mean $+64.75 vs E3 $+281.08 — nothing to freeze |
| **grinder** | **NO-LIFT** | best pattern (H2) MINE day-mean $+70.56 vs E3 $+184.56 — nothing to freeze |

**No variant reached the freeze step on either lane, so per protocol no HOLD-OUT winner was graded
and the shuffle null was not owed** (it exists only for a winning variant; none won). The hold-out
columns above are shown for transparency and tell the same story (H2 BA $+88 vs E3 $+259).

## Reading (plain words)

1. **The distribution grammars DO what they promise — and it costs a fortune.** Every pattern
   recovers 40–65% of E3's peak-to-exit giveback and cuts hold time from ~80 min to 6–36 min.
   But the giveback IS the price of the tail: the patterns fire on 50–80% of trades, and on this
   tape a volume climax / lower-low / fade-push in the first hour is a **shakeout, not a top** —
   the same physics that refuted V2 VWAP-loss (−$9,579) and no-progress-15 in the EYES matrix.
2. **H3 (first lower low after the run-high) is the worst idea tested** — it turns both champion
   lanes red (avg hold 6–7 min). H2 (exit into the climax) is the least bad everywhere, and still
   forfeits ~2/3 to 3/4 of the lane.
3. **In-sample and out-of-sample agree in direction on every variant** — this is not an
   underpowered result; the patterns are consistently, materially worse.
4. **E3 remains the exit of record.** Third consecutive study (exit_eyes_join V1–V3b, Sunday T6,
   now this) where adding intelligence to the exit side burns money. The champion lanes' P&L
   lives in the runners E3 refuses to leave.

Caveats: patterns tested as full-exit triggers layered on E3 (as pre-registered), not as
partial-exit or trail-tighten signals; 10s-bar volume percentiles are trade-relative (no
time-of-day baseline — rel-vol-TOD is still a TODO eye); X1 flatten-parity caveat (sim 19:59
grinder / last-bar BA vs live 15:45) applies to every E3 dollar here as it does to the whole
F/G/CJ series.

Officers touched: Trade Manager (verdicts), Wind Tunnel (X1 caveat carried), Systems Quant
(E3 clone reconciles to $0.000000), Momentum Operator (no ship on noise — nothing to ship),
Statistician (`_out.json`), Strength Ombudsman (patterns would refuse the strength E3 rides —
priced above), Forward Architect (hypothesis registered and killed same day), Blast Radius
(analysis only, no bot edits), Historian (record of the 8/17 exit-grammar kill).

*Analysis only. No bot edits. Numbers only — the room verifies, Marcos decides.*
