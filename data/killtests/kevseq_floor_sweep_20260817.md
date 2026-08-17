# KEVSEQ DAY-GAIN FLOOR SWEEP (kill-test) — 2026-08-17

Ordered by Marcos. Analysis only — no code change, no deploy, no env change.
Script: `kevseq_floor_sweep_20260817.py` · run: `_run.txt` · json: `_out.json`

## THE QUESTION

`KEVSEQ_GAIN_MIN` is 20% (`marcos_trading_bot.py:6440`), and the live clause is
`top3 OR day_gain >= GAIN_MIN` (:6589). The burst kill-test
(`burst_saturation_20260817.md`) reported the lane at **−$0.73/tr HOLD-OUT** at the
20% floor but **+$9.34/tr HOLD-OUT (N=174)** on the 100%+ vertical cohort. That split
was DESCRIPTIVE — it sliced *existing* fires by the name-day's eventual max gain, which
is not knowable at fire time. This study tests the floor **as a rule**: the gate uses
`day_gain` measured AT THE FIRE BAR, exactly as live does.

## FAILURE CONDITION (pre-registered)

The "raise the floor" hypothesis is REFUTED if any of:
1. No floor beats 20% on **both** halves of the OOS split (MINE 05-18..07-21 /
   HOLD-OUT 07-22..08-14).
2. The only positive cells have HOLD-OUT **N < 30** (UNDERPOWERED — cannot be a
   recommendation regardless of $/tr).
3. The best material cell's $/tr is not distinguishable from a **random subset of the
   same size** from the current-rule fire-set (permutation p >= 0.05).
4. The $/tr curve is **non-monotone** in the floor — a real cohort effect trends; one
   lucky cell is noise.

## METHOD

Engine + fire generation imported UNCHANGED from `sunday_afternoon_studies_20260816`
(engine of record), same machinery as the burst study. E3 live-parity, $500 sizing,
−0.5% exit slip, stop-first, 15:45 flatten. Universe cache `data/universe/bars10s`.

- Universe: **738 files, 736 graded name-days, 63 dates** (2026-05-18 .. 2026-08-17).
- **FIRE-SET: 1,659** kevseq fires with every live clause applied INCLUDING burst
  (V0 trailing-p75, which the burst study proved is earning its keep) and the day-gain
  floor REMOVED and recorded instead. MINE 1,180 / HOLD-OUT 471. 666 of the 1,659 were
  top-3 gainer at fire time. Per-leg cap (3) applied per-arm in bar order, since a
  different floor consumes the cap differently.
- `top3` replayed as: at the fire bar's clock, is this symbol in the top 3 by
  current day-gain among that date's universe board. (Board proxy — the live board is
  the scanner's, which is not in the replay cache.)
- Entry models: **(a)** quote entry (pre-13:57 behaviour) and **(b)** F3 limit-at-fire
  +0.5% — (b) is the production path since `KEVSEQ_LIMIT_ENTRY=1` was set at ~13:57 ET
  today, so (b) is the decision-relevant column.

---

## GRID — (b) F3 LIMIT-AT-FIRE +0.5% [DECISION-RELEVANT]

### WITH the top3 escape hatch (today's live rule: `top3 OR gain>=floor`)

| floor | MINE N | MINE $/tr | HOLD N | HOLD $/tr | HOLD win | HOLD total | worst | day mean | day med | green-day% | H1 (07-22..08-02) | H2 (08-03..08-14) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **20% (current)** | 918 | −0.63 | **359** | **−0.85** | 38% | −304.44 | −85.86 | −16.91 | −8.76 | 44% | N=155 −6.85 | N=204 +3.73 |
| 30% | 764 | −1.74 | 299 | −2.75 | 37% | −822.11 | −85.86 | −45.67 | −77.89 | 39% | N=134 −8.16 | N=165 +1.64 |
| 40% | 643 | −2.62 | 262 | −5.82 | 35% | −1525.35 | −85.86 | −84.74 | −116.02 | 33% | N=110 −13.57 | N=152 −0.22 |
| 50% | 571 | −4.45 | 222 | −5.16 | 36% | −1144.70 | −85.86 | −63.59 | −62.82 | 44% | N=97 −13.81 | N=125 +1.56 |
| 60% | 526 | −5.35 | 204 | −5.80 | 35% | −1184.13 | −85.86 | −65.79 | −50.24 | 33% | N=93 −13.23 | N=111 +0.42 |
| 80% | 483 | −5.76 | 189 | −6.56 | 33% | −1240.08 | −85.86 | −68.89 | −45.46 | 28% | N=93 −13.23 | N=96 −0.10 |
| 100% | 465 | −5.75 | 185 | −6.79 | 33% | −1255.88 | −85.86 | −69.77 | −45.46 | 28% | N=93 −13.23 | N=92 −0.28 |
| 125% | 459 | −5.55 | 184 | −7.17 | 33% | −1319.54 | −85.86 | −73.31 | −65.22 | 28% | N=93 −13.23 | N=91 −0.98 |
| 150% | 457 | −5.56 | 184 | −7.17 | 33% | −1319.54 | −85.86 | −73.31 | −65.22 | 28% | N=93 −13.23 | N=91 −0.98 |

Coverage: 62/62 era days fire at EVERY floor; median fires/day only falls 20 → 10.

**The top3 escape hatch makes the floor nearly inert.** From 80% upward the fire count
barely moves (189 → 184) and $/tr gets steadily WORSE, not better — because everything
that survives is arriving through `top3`, and top3 is a *relative* rank on the board,
not an intensity condition. Raising the floor while keeping top3 is not a real change.

### WITHOUT the top3 escape hatch (`gain >= floor` only)

| floor | MINE N | MINE $/tr | HOLD N | HOLD $/tr | HOLD win | HOLD total | worst | day mean | day med | green-day% | H1 | H2 | days firing | med fires/day |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20% | 897 | −0.56 | **356** | −0.73 | 38% | −260.78 | −85.86 | −14.49 | −8.76 | 44% | N=152 −6.72 | N=204 +3.73 | 62/62 | 20 |
| 30% | 743 | −2.03 | 281 | −1.51 | 38% | −423.41 | −85.86 | −23.52 | −77.89 | 39% | N=116 −9.35 | N=165 +4.01 | 62/62 | 16 |
| 40% | 586 | −2.75 | 236 | −4.44 | 36% | −1048.46 | −85.86 | −58.25 | −37.43 | 39% | N=94 −13.95 | N=142 +1.85 | 62/62 | 13.5 |
| 50% | 463 | −5.48 | 176 | −2.65 | 38% | −466.54 | −85.86 | −25.92 | −11.44 | 50% | N=66 −13.31 | N=110 +3.75 | 62/62 | 10 |
| 60% | 371 | −6.28 | 138 | −3.32 | 39% | −457.80 | −85.86 | −25.43 | −23.34 | 39% | N=47 −14.65 | N=91 +2.53 | 62/62 | 8 |
| 80% | 245 | −8.62 | 87 | −0.89 | 43% | −77.78 | −85.86 | −4.32 | −20.89 | 44% | N=32 −17.80 | N=55 +8.94 | 61/62 | 5 |
| 100% | 167 | −6.10 | 63 | **+1.37** | 41% | +86.60 | −85.86 | +5.41 | −37.11 | 44% | N=21 −23.39 | N=42 +13.76 | 55/62 | 3 |
| 125% | 114 | −2.82 | 40 | **+2.10** | 42% | +84.08 | −83.72 | +5.61 | −30.29 | 40% | N=13 −22.73 | N=27 +14.06 | 47/62 | 3 |
| 150% | 78 | **+0.41** | **29** ⚠ | +10.71 | 52% | +310.69 | −83.72 | +25.89 | −25.73 | 42% | N=8 −22.55 | N=21 +23.39 | 37/62 | 2 |

⚠ = **UNDERPOWERED** (HOLD-OUT N < 30) — cannot be a recommendation.

## GRID — (a) QUOTE ENTRY (pre-13:57 behaviour), HOLD-OUT $/tr

| floor | WITH top3: MINE / HOLD (N) | NO top3: MINE / HOLD (N) |
|---|---|---|
| 20% | −3.54 / −2.58 (368) | −3.54 / −2.46 (365) |
| 30% | −5.24 / −5.23 (307) | −5.43 / −4.04 (289) |
| 40% | −6.25 / −8.73 (271) | −6.56 / −7.18 (244) |
| 50% | −8.43 / −9.70 (230) | −10.06 / −7.18 (183) |
| 60% | −9.44 / −9.72 (212) | −11.46 / −7.84 (145) |
| 80% | −9.76 / −9.92 (197) | −14.47 / −4.47 (92) |
| 100% | −9.88 / −10.13 (193) | −13.94 / −3.77 (67) |
| 125% | −9.71 / −10.34 (192) | −11.96 / −3.07 (41) |
| 150% | −9.55 / −10.34 (192) | −9.48 / **+3.27** (29 ⚠) |

Under the old entry model the floor is worse everywhere: **not a single cell is
positive on both halves**, and the only positive HOLD-OUT cell is the same N=29 sliver.

---

## MONOTONICITY CHECK — F3, HOLD-OUT $/tr by floor

| floor | WITH top3 N | $/tr | NO top3 N | $/tr |
|---|---|---|---|---|
| 20% | 359 | −0.85 | 356 | −0.73 |
| 30% | 299 | −2.75 | 281 | −1.51 |
| 40% | 262 | −5.82 | 236 | −4.44 |
| 50% | 222 | −5.16 | 176 | −2.65 |
| 60% | 204 | −5.80 | 138 | −3.32 |
| 80% | 189 | −6.56 | 87 | −0.89 |
| 100% | 185 | −6.79 | 63 | +1.37 |
| 125% | 184 | −7.17 | 40 | +2.10 |
| 150% | 184 | −7.17 | 29 ⚠ | +10.71 |

**MONOTONE: NO** — in either arm. The WITH-top3 arm is monotone *downward* (higher
floor = worse). The NO-top3 arm is a **U**: 20% is the second-best powered cell, the
curve craters through 40–60%, then climbs back only as N collapses into slivers. A real
cohort effect would climb from 20% onward; instead raising the floor from 20% to 40%
costs −$3.71/tr with N still at 236. That is the opposite of the hypothesis.

## NULL TEST (permutation, 5,000 shuffles)

Best MATERIAL cell (F3, HOLD-OUT N >= 30): **floor 125% / no-top3, N=40, $/tr +$2.10,
total +$84.08, win 42%.**

Null pool = the current rule's HOLD-OUT fire-set under F3 (floor 20 OR top3): N=359,
mean −$0.85/tr. Drawing 5,000 random 40-trade subsets from that pool:

> **p = 0.3415**

One draw in three of a *random* 40-trade subset of today's fires does at least as well
as the 125% floor. The floor is not selecting a cohort — it is selecting fewer trades.
FC#3 fails.

## DAY COVERAGE (descriptive)

Fraction of the 62 era days producing >= 1 fire, and median fires/day (no-top3 arm):
20% 62/62 (20/day) · 50% 62/62 (10) · 80% 61/62 (5) · 100% 55/62 (89%, 3) ·
125% 47/62 (76%, 3) · **150% 37/62 (60%, 2)**. At the only cells that turn positive the
lane goes dark on a quarter to two-fifths of days.

## WHY THE DESCRIPTIVE +$9.34 DID NOT SURVIVE

The burst study's 100%+ cohort was defined by the name-day's **eventual maximum** gain —
information that does not exist at fire time. As a *rule*, the gate can only see the
gain so far. A name at +100% at 10:05 is a different population from a name that will
*end up* +100%: the rule buys late into the ones already extended and still misses the
early leg of the ones that get there. The H1/H2 split shows the same: every arm is
badly negative in 07-22..08-02 and positive in 08-03..08-14, i.e. what looks like a
floor effect is substantially a **regime** effect.

## VERDICT

> ### NO SHIPPABLE THRESHOLD — the cohort effect does not survive as a rule.

Against the pre-registered failure conditions:
- **FC#1 FAILS** — no floor beats 20% on both halves. Under F3, MINE $/tr is worse than
  the 20% baseline at EVERY floor from 30% to 125%; only 150% is MINE-positive
  (+$0.41, N=78) and its HOLD-OUT N is 29.
- **FC#2 FAILS** — the only strongly positive cells (150% no-top3: +$10.71) are
  UNDERPOWERED (N=29 < 30).
- **FC#3 FAILS** — best material cell p = 0.3415. Indistinguishable from random
  thinning.
- **FC#4 FAILS** — non-monotone in both arms; the WITH-top3 arm trends the wrong way.

**RECOMMENDATION: leave `KEVSEQ_GAIN_MIN` at 20. No env change, no code change.** The
Claude-side hypothesis (raise the floor) is REFUTED, the same way today's burst theory
was. `feedback_auditor_cannot_authorize_behavior`: nothing here changes what the bot
does with money.

**REPORTABLE SIDE-FINDING (not a recommendation, Marcos's to price):** the `top3`
escape hatch is doing real damage under the current entry model — with it, HOLD-OUT
$/tr is −$0.85 vs −$0.73 without it at floor 20, and at every floor above 40% the
top3-admitted fires are the ones dragging the arm to −$5 to −$7/tr while the floor-only
arm improves. That is a separate hypothesis about `top3`, not about the floor, and it
is NOT tested here as its own rule. Registering it, not shipping it.

**And the standing fact remains unchanged:** kevseq under F3 is −$0.73/tr HOLD-OUT on
N=356. The lane is a money-loser and no day-gain floor fixes it.
