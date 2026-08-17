# CROSS-TICKER SEQUENCE STUDY — 8/17/26 (the board as the instrument)

Question: Kev watches the BOARD — does the ORDER of events ACROSS names carry signal?
Four pre-registered hypotheses, all graded on break-attack + grinder fires (pooled,
1,021 E3-graded deduped fires), $500 E3 live-parity exits, engine chain imported
UNCHANGED via `sequence_mining_pilot_20260817.py`. Analysis only. No bot edits.

Script: `seq_cross_ticker_20260817.py` · full run: `seq_cross_ticker_20260817_run.txt` ·
machine verdicts: `seq_cross_ticker_20260817_out.json`.

## HONEST CAVEAT (read first)

The universe is **gain>=40% runners only — NOT the full live board**. LEADER,
SECOND-MOVER, BOARD-HEAT, and SOLE-RUNNER are **within-universe proxies** for what
Kev's board would actually show; a name that "leads" this cohort may have been a
follower of a non-universe mover, and "sole runner" only means sole among survivors
that themselves ran 40%+. Findings are conditional on that proxy. A live replication
needs the dashboard scanner board (the discovery source of record) as the instrument.

## Pre-registered definitions

- Session-high baseline = max premarket high from the FULL file (bars before 13:30Z);
  NEW SESSION HIGH = RTH 10s bar whose high exceeds the running session high.
- BURST volume = bar volume >= 3x mean of the prior 30 bars (>=12 prior bars required).
- LEADER = first name that date to print a burst-volume new session high after 09:30 ET.
- SECOND-MOVER = next distinct name to burst-break within 30 min of the leader.
- OOS wall (same protocol as `seq_gate_oos_wall_20260817.py`): chronological —
  MINE = 44 dates 2026-05-18..2026-07-21, HOLD-OUT = 18 dates 2026-07-22..2026-08-14.
  Split mined on MINE only (material = both sides N>=15); winning side FROZEN; verified
  on HOLD-OUT. NULL: within each date, shuffle the (sym, time) board-context across that
  date's hold-out fires 5000x (pnl stays with the fire); p = P(random gated $/tr >= observed).
- Board coverage: 62/62 dates have >=3 universe names and a burst leader; 60/62 have a
  second-mover within 30 min.

## SUMMARY

| hypothesis | MINE N (T/F) | MINE $/tr lift | HOLD-OUT lift | null p | VERDICT |
|---|---|---|---|---|---|
| H1 LEADER-FOLLOWER (sympathy window) | 228/464 | $+5.95 | **$+25.39** | **0.001** | **BOARD-SIGNAL** |
| H2 SECOND-MOVER (vs leader's fires) | 58/51 | $+0.13 | $-23.47 | - | NO-SPLIT |
| H3 BOARD-HEAT 2+ (vs 0-1) | 463/229 | $+9.48 | $+14.85 | 0.077 | NO-SPLIT |
| H4 SOLE-RUNNER (vs crowded) | 40/652 | $+0.76 | $+14.77 (N=8) | - | UNDERPOWERED |

## H1 LEADER-FOLLOWER — BOARD-SIGNAL

Fires on OTHER names inside the 30-min sympathy window after the leader's burst break
beat fires outside it, and the effect got STRONGER out of sample:

| cohort | N | win | $/tr | total |
|---|---|---|---|---|
| MINE sympathy | 228 | 71% | $+32.80 | $+7,477.67 |
| MINE outside | 464 | 70% | $+26.85 | $+12,456.80 |
| HOLD-OUT sympathy (frozen) | 101 | 79% | $+41.22 | $+4,163.07 |
| HOLD-OUT outside | 228 | 64% | $+15.83 | $+3,609.78 |

Null (5000x within-date board-context shuffle): observed $+41.22 vs random-mean $+26.56,
p=0.001. The Kev hypothesis "sympathy runs are weaker" is REFUTED in this cohort — a
fire arriving while the board's leader has just broken is the BETTER fire. Direction:
confirmation, not crowding. (Data-only observation; any live gate/sizing use goes to
Marcos priced, per auditor-cannot-authorize.)

## H2 SECOND-MOVER — NO-SPLIT

Second-mover-name fires vs leader-name fires: MINE dead even ($+30.05 vs $+29.92/tr,
lift $+0.13 — immaterial). Hold-out actually favored the leader ($+29.45 vs $+5.98).
Neither Kev's "sympathy runs are weaker" nor the counter-hypothesis earns a split at
the name level; H1 says the WINDOW matters, not which ordinal name you're on.

## H3 BOARD-HEAT — NO-SPLIT (direction noted, fails the null)

Heat monotone on MINE (heat0 $+20.61, heat1 $+23.42, heat2+ $+31.94/tr) and hold-out
direction held ($+27.82 vs $+12.97, lift $+14.85) — but the within-date shuffle null
gives p=0.077: heat 2+ is not separable from "this was simply a hot date" at the 0.05
bar. NOT graded a signal. Worth a re-look with the real scanner board (more names, more
within-date contrast) — registered as a hypothesis, nothing more.

## H4 SOLE-RUNNER — UNDERPOWERED

"Only game in town" fires are rare in this cohort (universe dates almost always have
multiple 40% runners — the caveat biting exactly as predicted): MINE 40 vs 652, hold-out
frozen side carries only 8 fires (100% win, $+38.04/tr — small-N curiosity, not
evidence). No verdict possible on the quiet-tape tie-in from this universe; the real
test needs full-board data where sole-runner days actually exist.

## Officers touched

Side Marshal (board-context stamps), Seam Scientist (hypothesis registry + OOS wall),
Statistician (ledgered run artifacts), First Hour / Momentum Operator (sympathy-window
finding sits mostly in their windows), Strength Ombudsman (clean — no strength refused),
Handicapper (selection implication of H1), Blast Radius Auditor (n/a — analysis only,
no live-path change).
