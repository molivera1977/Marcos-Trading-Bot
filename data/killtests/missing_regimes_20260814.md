# MISSING-REGIMES KILL-TESTS — 2026-08-14

Marcos 8/14: "let's start with the missing pieces." Two never-tested regimes: **#37 halt-resumption lane** and **#48 vertical-regime (grinder) lane**. Read-only on bot code; simulation script archived at scratchpad `missing_regimes.py` (logic reproduced in the specs below).

## Coverage

- **108 files** in `data/universe/bars10s/` — 12 symbols/day × **9 dates, 2026-08-03 → 2026-08-13** (8/8, 8/9 weekend gap; no 8/14 yet).
- Tick-reconstructed 10s bars; a bar exists only where trades printed (timestamp gaps = zero-trade intervals).
- Specimens present: **DFNS (8/03 file — the 7/27 halt day itself is NOT in the store)**, **INHD 8/13**, **PLAG 8/11**. **MF (today, 8/14) NOT in the store yet.** So two of the four named specimens are absent — this run cannot confirm/refute against them directly.

## Method (both tests)

- Bars walked strictly in time order; entries at bar close only, using only same-bar-or-earlier data (no lookahead).
- $500/position (fractional shares — see caveats).
- Uniform exits: half off at +4% (filled at target when bar high ≥ target), remainder trails the 10s EMA90 of closes (exit at close of first bar closing below it, active after the half); stop = full-size exit at stop price on bar low ≤ stop; **stop-first on ties**; stop moves to breakeven after the half. Flatten 15:59 ET.
- Splits reported: 9:30-10:30 ET vs rest; first-half vs second-half of dates (mid = 2026-08-07).

---

## KILL-TEST 1 — HALT-RESUMPTION LANE (#37)

**Halt detection heuristic** (NOT a real LULD feed): zero-trade gap ≥ 4 min between consecutive 10s bars, gap starting 9:30-15:45 ET, **both** bracketing bars ≥ 5× the day's median bar volume. Gaps 2-4 min with the same volume signature flagged 'suspect' and **excluded**: only **2 suspects** found. **135 halts detected** across the 9 days (feels high — see caveats; the volume-bracket test on thin names likely admits some dead-tape spells that aren't real LULD halts).

Variants — resumption bar = first bar after the gap; up-halt = resumption close > pre-halt last close:
- **(a) gap-up-go**: enter resumption-bar close if bar is green AND close > pre-halt price. Stop = resumption bar low. (All entries are up-halts by construction.)
- **(b) resumption retest**: within 10 min, first pullback whose lows hold above the resumption bar open; enter on the reclaim bar (close > prior bar high after the dip). Stop = pullback low.
- **(c) control**: enter every resumption at its close, stop = resumption bar low (skipped when low == close; 115 of 135 entered).

### (a) gap-up-go
| split | N | win% | total $ | mean $ |
|---|---|---|---|---|
| ALL | 53 | 45% | -654.20 | -12.34 |
| 09:30-10:30 ET | 8 | 38% | -179.03 | -22.38 |
| rest of day | 45 | 47% | -475.16 | -10.56 |
| first-half dates | 14 | 36% | -230.67 | -16.48 |
| second-half dates | 39 | 49% | -423.53 | -10.86 |
| up-halts | 53 | 45% | -654.20 | -12.34 |
| down-halts | 0 | — | — | — |

### (b) resumption retest
| split | N | win% | total $ | mean $ |
|---|---|---|---|---|
| ALL | 15 | 53% | +3.47 | +0.23 |
| 09:30-10:30 ET | 1 | 100% | +10.00 | +10.00 |
| rest of day | 14 | 50% | -6.53 | -0.47 |
| first-half dates | 4 | 25% | -95.33 | -23.83 |
| second-half dates | 11 | 64% | +98.80 | +8.98 |
| up-halts | 12 | 50% | -16.52 | -1.38 |
| down-halts | 3 | 67% | +19.99 | +6.66 |

### (c) control — every resumption
| split | N | win% | total $ | mean $ |
|---|---|---|---|---|
| ALL | 115 | 43% | -534.36 | -4.65 |
| 09:30-10:30 ET | 29 | 45% | -89.51 | -3.09 |
| rest of day | 86 | 42% | -444.85 | -5.17 |
| first-half dates | 29 | 45% | -75.87 | -2.62 |
| second-half dates | 86 | 42% | -458.49 | -5.33 |
| up-halts | 65 | 48% | -519.61 | -7.99 |
| down-halts | 50 | 36% | -14.75 | -0.29 |

### Hand-traces (one per variant, exact bars)
- **(a)** INLF 2026-08-05: green resumption 11:25:00 close 8.9350 > pre-halt 8.3200; ENTER at 8.9350, stop 8.3214 → 11:25:10 STOP hit (bar low 8.3200), full exit. **-$34.32** (6.9% stop distance — resumption-bar-low stops are wide AND still get run).
- **(b)** NEXR 2026-08-03: resumption 14:44:40 open 2.9000; pullback low 2.9000 held; reclaim bar 14:45:50 close 3.0000 > prior high 2.9920; ENTER 3.0000, stop 2.9000 → 14:47:30 STOP hit. **-$16.67**
- **(c)** NEXR 2026-08-03: gap ended 14:07:00, pre-halt 4.5000, resumption bar O4.1100 H4.1500 L3.8500 C4.0010; ENTER 125.0sh at 4.0010, stop 3.8500 → 14:07:30 STOP hit (low 3.8000). **-$18.88**

### KT1 verdicts
- **(a) gap-up-go: REFUTED** — -$654 on 53 entries, loses in every split. The green-and-above-pre-halt filter is *worse* than the unconditional control on a per-trade basis (-$12.34 vs -$4.65 mean): chasing the up-resumption close with a resumption-bar-low stop is the worst combination (wide stop, top-of-bar entry).
- **(b) resumption retest: NEEDS-MORE-DATA** — breakeven overall (+$3.47/15), but the only structurally patient variant, positive on second-half dates (+$98.80/11) and the only one not bleeding. N=15 is far below verdict grade. If #37 ships anywhere, THIS shape is the candidate to shadow — but not on this evidence.
- **(c) control: REFUTED as a lane** (that's its job — it prices "trade every resumption" at -$534) — and it confirms the pre-8/8 doctrine: resumptions are not free money; **up-halt resumptions bled harder than down-halts** (-$7.99 vs -$0.29 mean) under these exits.

---

## KILL-TEST 2 — VERTICAL-REGIME / GRINDER LANE (#48)

**Candidate signature** (checked at each new-session-high print after 11:00 ET, RTH bars only): last 30 min net-up (close > close 30 min ago) AND close > session VWAP (typical-price VWAP from 9:30) AND no ≥3% pullback from running high in the last 15 min. **517 candidate prints** found (10s new highs cluster; 15-min per-symbol entry cooldown applied).

- **(a) breakout**: enter at the new-high bar close; stop = last-15-min low.
- **(b) micro-dip**: after a qualifying new high, wait for a 1-2% dip (>2% or >15 min voids it), enter on the first higher-low bar close; stop = dip low.

### (a) breakout
| split | N | win% | total $ | mean $ |
|---|---|---|---|---|
| ALL | 64 | 67% | +815.68 | +12.74 |
| 09:30-10:30 ET | 0 | — | — | — |
| rest of day | 64 | 67% | +815.68 | +12.74 |
| first-half dates | 25 | 72% | +293.38 | +11.74 |
| second-half dates | 39 | 64% | +522.30 | +13.39 |

### (b) micro-dip higher-low
| split | N | win% | total $ | mean $ |
|---|---|---|---|---|
| ALL | 33 | 30% | +182.09 | +5.52 |
| 09:30-10:30 ET | 0 | — | — | — |
| rest of day | 33 | 30% | +182.09 | +5.52 |
| first-half dates | 11 | 27% | +33.59 | +3.05 |
| second-half dates | 22 | 32% | +148.50 | +6.75 |

(9:30-10:30 rows are structurally empty — the signature requires post-11:00 ET, by design.)

### Hand-traces
- **(a)** NEXR 2026-08-03: new session high 3.8600 at 13:22:20 (prev 3.8500); 30m net-up, above VWAP 3.4922, max 15m pullback 1.82%; ENTER close 3.8600, stop 15m-low 3.7700 → 13:31:00 +4% target 4.0144 hit (bar high 4.0300), half off, stop→breakeven → 14:07:00 breakeven stop on remainder. **+$10.00**
- **(b)** NEXR 2026-08-03: new high 3.8700, micro-dip to 3.8156 (1.41%); higher-low bar 13:24:00 low 3.8700 > prior 3.8156; ENTER 3.8700, stop 3.8156 → 13:24:10 STOP hit. **-$7.03**

### KT2 verdicts
- **(a) breakout: SHADOW-CANDIDATE** — +$815.68 on 64 entries, 67% win, positive in BOTH date halves (+$293/+$522) with consistent means (~+$12-13/trade on $500). This is exactly the PLAG-shaped hole: the post-11:00 grinder above VWAP with a tight tape. Consistent across the era split; the only variant in this whole report with a clean two-sided profile. **Shadow rows first — data-only stamping; Marcos prices any live behavior (auditor cannot authorize).**
- **(b) micro-dip: NEEDS-MORE-DATA** — net positive (+$182/33) but 30% win with a tail-carried mean; a 10s "higher-low bar" is a noise-scale trigger and the tight dip-low stop gets tagged constantly. Positive both halves, but the shape is fragile. Do not prefer it over (a).

---

## Honest caveats (both tests)

1. **Optimistic fills**: entries at bar close, +4% half at exact target price, stops at exact stop price — no slippage, no spread, no partial-fill reality. On halt resumptions especially, real fills are materially worse (spreads blow out); KT1's negatives would be MORE negative live, and KT2(a)'s +$12.74 mean has room to shrink.
2. **No live gates**: none of the bot's real selection/back-side/crown/liquidity gates applied — these are raw-lane counterfactuals, not bot P&L predictions.
3. **Halt detection is a heuristic, not the LULD feed**: 4-min zero-trade gap + 5×-median-volume brackets. 135 "halts" in 9 days is almost certainly over-inclusive on thin names (dead-tape spells with coincident volume). A real halt feed is the honest prerequisite before any KT1 verdict hardens. The 2 'suspect' 2-4min gaps were excluded per spec.
4. **Coverage is 9 days, 12 curated names/day, universe = 40%+ runner-days only** — survivorship-selected tape; both lanes are being graded on the friendliest possible universe. DFNS 7/27 and MF 8/14 specimens absent from the store.
5. **Fractional shares** used ($500/price exactly); whole-share sizing adds small rounding drag on low-priced names.
6. **10s EMA90 trail** activates only after the +4% half — full-size runners never trail; the stop/target does all the work before the half. This is one exit spec, not the bot's exit stack.
7. **KT2 cooldown (15 min/symbol) is an untested invented threshold** → belongs in the Translation & Calibration Registry if this advances.

## Verdict summary

| Test | Variant | Verdict |
|---|---|---|
| #37 halt-resumption | (a) gap-up-go | **REFUTED** (-$654.20 / 53) |
| #37 halt-resumption | (b) resumption retest | **NEEDS-MORE-DATA** (+$3.47 / 15; only non-bleeding shape) |
| #37 halt-resumption | (c) control | **REFUTED** as lane (-$534.36 / 115; prices "trade every resumption") |
| #48 vertical-regime | (a) breakout | **SHADOW-CANDIDATE** (+$815.68 / 64, 67% win, both halves positive) |
| #48 vertical-regime | (b) micro-dip | **NEEDS-MORE-DATA** (+$182.09 / 33, 30% win, tail-carried) |

Officers touched: Rocket Rider (halt regime — refutation matches doctrine that resumptions aren't free), Side Marshal (up/down-halt split recorded), Seam Scientist (one-era humility — 9 days, no OOS wall crossed), Crown Steward (#48 is the crowned-grinder hole; shadow-candidate addresses the PLAG docket item), Strength Ombudsman (KT2(a) is a strength-following lane scoring positive — no refusal bias here), Wind Tunnel Engineer (fill optimism cataloged), Statistician (this file = the ledger artifact), Quartermaster (MF 8/14 + DFNS 7/27 missing from bars10s store — ferry gap), Blast Radius Auditor: clean (no code shipped, observe-only artifact).
