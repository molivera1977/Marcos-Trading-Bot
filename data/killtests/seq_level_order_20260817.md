# LEVEL-INTERACTION SEQUENCE STUDY — 8/17/26

**Question:** the chart-gate doctrine treats levels as *static gates*; the sequencing doctrine says the
**ORDER** of level interactions matters. Does the order in which a name takes its levels predict the
champion lanes' fires?

- **Script:** `data/killtests/seq_level_order_20260817.py` · **raw run:** `..._run.txt` · **json:** `..._out.json`
- **Analysis only. No bot edits. Read-only replay.**
- **Universe:** FULL `data/universe/bars10s/*.json` — 729 files, 729 name-days, 62 dates 2026-05-18..2026-08-14.
- **Engine:** chain `S -> G -> F -> C -> B -> E` imported UNCHANGED from
  `sequence_mining_pilot_20260817.py`. Every fire exits **E3 live-parity** ($500 clip, bank ½ at +10%,
  trail rest 10%-off-high closes-through, stop-first, −1% chase entry, −0.5% market-exit slip).
- **Fires:** break-attack (`G.det_flat_top_break`, 09:30–10:30 ET) **634** · grinder (`C.det_grinder_1030`) **387**.
- **OOS protocol** identical to `seq_gate_oos_wall_20260817.py`: chronological split
  **MINE = 2026-05-18..2026-07-21 (44 dates)** / **HOLD-OUT = 2026-07-22..2026-08-14 (18 dates)**.
  Measure on MINE (material = **both sides N≥15**), FREEZE the direction, verify on HOLD-OUT,
  permutation null **5000×** relabelings of the level-token feature across hold-out fires within lane.

## Levels and the event alphabet (offline, no Kev maps)

Per name-day, computed from the 10s RTH tape only:

| class | level |
|---|---|
| **V** | session VWAP (recomputed on the 10s bars) |
| **W** | whole dollars |
| **F** | half dollars (x.50) |
| **M** | premarket high / day high before 09:30 ET |
| **O** | 09:30 opening price (first RTH bar open) |

Tokens per level class: **t** first-touch · **r** reclaim (close through from below after ≥5 min = 30 bars
closing below) · **j** rejection (touch from below, close ≥0.5% away under it) · **h** hold (3 consecutive
closes at/above after a reclaim).

## Results

### H1 LADDER-UP — VWAP-reclaim THEN whole-dollar-hold, in that order, within 10 min

| lane | MINE with / without $/tr | HOLD-OUT | p | verdict |
|---|---|---|---|---|
| break-attack | **N=1** $+40.96 / N=446 $+27.64 | — | — | **UNDERPOWERED** |
| grinder | **N=2** $+58.11 / N=243 $+30.66 | — | — | **UNDERPOWERED** |

The ordered ladder essentially **never happens** before a champion fire: 1 of 447 break-attack MINE fires
and 2 of 245 grinder MINE fires carry it. Both directions point the hypothesis' way (+$13/+$27) and both
are meaningless at that N. Not a refutation — a **frequency** finding: the rung pair is far too rare in the
10-minute pre-fire window to gate or size on. Not tested on hold-out (the freeze rule bars mining a 1–2-fire
cohort).

### H2 PMH-FIRST — premarket high reclaimed before the fire's break

| lane | MINE with / without $/tr | HOLD-OUT with / without | p | verdict |
|---|---|---|---|---|
| break-attack | N=56 $+15.26 / N=391 $+29.44 (diff **$−14.19**) | N=11 $+4.96 / N=176 $+26.19 | — | **UNDERPOWERED** (hold-out with-side N=11) |
| grinder | N=104 $+25.18 / N=141 $+35.10 (diff **$−9.92**) | N=50 $+32.36 / N=92 $+16.21 (diff **$+16.15**) | — | **NO-SPLIT** |

**MINE OPPOSES the pre-registered direction in both lanes** — fires that came *after* a PMH reclaim did
*worse*, not better. That inversion then **did not hold out**: on grinder the sign flipped (+$16.15 the other
way, i.e. back toward the hypothesis), and break-attack's with-side collapsed to 11 fires. A signal that
inverts between train and test is noise, so no direction is claimed either way. Kev's "through the premarket
high" tell is **not measurable as an ordering advantage on these lanes' fires** by this construction — most
plausibly because these detectors fire *on* the session-high break, which by then is usually already above
the PMH, so the ordering carries no fresh information.

### H3 REJECTION-SCAR — a whole-dollar rejection within 10 min BEFORE the fire

| lane | MINE with / without $/tr | HOLD-OUT with / without | p | verdict |
|---|---|---|---|---|
| break-attack | N=86 $+5.93 / N=361 $+32.85 (diff **$−26.91**) | N=34 $+19.69 / N=153 $+26.11 (diff **$−6.42**) | **0.304** | **NO-SPLIT** |
| grinder | N=22 $−3.46 / N=223 $+34.27 (diff **$−37.73**) | N=10 $+41.84 / N=132 $+20.39 (diff **$+21.45**) | — | **UNDERPOWERED** (hold-out with-side N=10) |

**The most interesting near-miss.** On MINE this is by far the strongest effect in the study and it *agrees*
with the pre-registration: a fresh overhead whole-dollar rejection in the 10 minutes before the fire cost
**−$26.91/tr on break-attack** (a 5× per-trade haircut: $+32.85 → $+5.93) and **−$37.73/tr on grinder**
(the scarred cohort was outright negative, $−3.46/tr).

On HOLD-OUT the break-attack direction **held but shrank to −$6.42/tr**, and the permutation null says that
residual is ordinary: **p = 0.304**, i.e. random relabelings of which 34 hold-out fires are "scarred" beat the
observed gap ~30% of the time. Grinder's hold-out cohort (10 fires) is too thin and flipped sign anyway.
**Verdict NO-SPLIT** — the in-sample scar effect is not distinguishable from chance out of sample. This is
exactly the shape of an in-sample-only finding, and it is written REFUTED-adjacent on purpose rather than
rounded up.

### H4 CLEAN-LADDER — distinct level classes reclaimed-and-held in the prior 30 min

**break-attack**

| bucket | MINE N | MINE $/tr | HOLD N | HOLD $/tr |
|---|---|---|---|---|
| 0 | 289 | $+28.69 | 134 | $+30.45 |
| 1 | 101 | $+29.00 | 41 | $+18.16 |
| 2 | 42 | $+23.24 | 8 | $−19.28 |
| 3+ | 15 | $+11.45 | 4 | $−1.63 |

**grinder**

| bucket | MINE N | MINE $/tr | HOLD N | HOLD $/tr |
|---|---|---|---|---|
| 0 | 127 | $+36.47 | 88 | $+21.32 |
| 1 | 77 | $+32.62 | 42 | $+17.28 |
| 2 | 36 | $+7.91 | 10 | $+36.73 |
| 3+ | 5 | $+27.78 | 2 | $+69.77 |

- **break-attack: NO-SPLIT** — MINE is not monotone across the four material buckets (0→1 rises, then falls),
  so nothing was frozen. Note the *drift* is downward, the **opposite** of the pre-registered "cleaner ladder
  is better" intuition.
- **grinder: NO-SPLIT** — MINE *is* monotone across its material buckets (0,1,2), but **decreasing**
  ($+36.47 → $+32.62 → $+7.91): more level classes reclaimed-and-held in the prior 30 min meant *worse*
  trades. Frozen and carried to hold-out, the decreasing direction technically reproduced, but
  corr(bucket, $) = **+0.090, permutation p = 0.286** — inside the noise, and the two richest hold-out
  buckets (N=10, N=2) point the other way.

**Reading:** if anything, a busy ladder is a mild *negative* — consistent with the pilot's finding that the
paying grammar is a **tight test-then-break under the session high**, not a name that has spent 30 minutes
grinding through many levels. But this is a direction, not a result; it does not clear the null.

## Verdicts

| hypothesis | MINE split | HOLD-OUT split | p | VERDICT |
|---|---|---|---|---|
| **H1 LADDER-UP** | BA $+40.96 (N=1) / $+27.64 (N=446) · GR $+58.11 (N=2) / $+30.66 (N=243) | not reached | — | **UNDERPOWERED** (both lanes — the ordered rung pair occurs ~0.5% of fires) |
| **H2 PMH-FIRST** | BA $+15.26 (56) / $+29.44 (391) · GR $+25.18 (104) / $+35.10 (141) — both **OPPOSE** | BA $+4.96 (11) / $+26.19 (176) · GR $+32.36 (50) / $+16.21 (92) — **sign flips** | — | **UNDERPOWERED** (break-attack) · **NO-SPLIT** (grinder) |
| **H3 REJECTION-SCAR** | BA $+5.93 (86) / $+32.85 (361) = **−$26.91** · GR $−3.46 (22) / $+34.27 (223) = **−$37.73** (agrees) | BA $+19.69 (34) / $+26.11 (153) = −$6.42 · GR $+41.84 (10) / $+20.39 (132) = +$21.45 | **0.304** (BA) | **NO-SPLIT** (break-attack) · **UNDERPOWERED** (grinder) |
| **H4 CLEAN-LADDER** | BA non-monotone · GR monotone **decreasing** $+36.47/$+32.62/$+7.91 | BA $+30.45/$+18.16/−$19.28/−$1.63 · GR $+21.32/$+17.28/$+36.73/$+69.77 | **0.286** (GR) | **NO-SPLIT** (both lanes) |

**Headline: ZERO of the four pre-registered level-ORDER hypotheses reached ORDER-MATTERS.** Not one survived
the OOS wall. The doctrine's ordering claim, as operationalized on these five offline level classes and this
four-token alphabet, is **not supported on the champion lanes' fires**.

This does **not** refute the sequencing doctrine generally — the pilot's *price-structure* grammar (`…T B` /
`…W T B`, test-the-session-high-then-break) is a different alphabet and already passed its own OOS test in
`seq_gate_oos_wall_20260817.py`. What this study says is narrower and useful: **the order in which a name
takes VWAP / round numbers / PMH / the open carries no out-of-sample edge for these fires**, while the order
of *session-high structure events* does. If ordering pays, it pays on the high, not on the ladder.

## Caveats (read before believing)

- **PMH collapse.** The bars10s cache starts at 08:00Z (04:00 ET) with no prior session, so "premarket high"
  and "prior-session day high before 09:30" are the **same level** here; they were collapsed into one class
  **M**. A true prior-session high would need a second-day join this cache does not carry.
- **Detector timing confound (the main one).** Both lanes fire *on* a session-high break. By construction most
  of the level ladder (VWAP, PMH, the open, the nearest dollar) is already *below* the fire price, so
  pre-fire ordering has little room to discriminate. A lane that fires *before* the high (v2 flush,
  hidden/reclaim) is the fairer venue for H1/H2 and is **not** tested here.
- **Threshold choices are homegrown**: ≥5 min below for a reclaim, 3 bars for a hold, 0.5% for a rejection,
  10-min / 30-min windows. All were pre-registered in the prompt, none were tuned — but none are calibrated
  to Kev either.
- **Rejections are per-bar, deduped only by "first level that qualifies"** — a wide bar spanning two whole
  dollars emits one `j`, not two.
- **Dollars, not R.** Every figure is E3 dollars through the real $500-clip sizing chain.
- **Permutation nulls were run only on survivors** (the frozen-direction cases): H3 break-attack and H4
  grinder. Underpowered arms were never null-tested by design — a null on N=1 is theater.
- **In-sample MINE numbers are not evidence.** H3's −$26.91 / −$37.73 look impressive and are exactly the
  kind of number that should not reach a decision without the wall it just failed.

*No recommendation to ship. Nothing here changes bot behavior. Numbers only — the full room verifies,
Marcos decides.*
