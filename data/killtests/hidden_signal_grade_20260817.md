# HIDDEN LANE — GRADE THE SIGNAL (8/17/26)

**Analysis only. Nothing shipped, nothing deployed, no bot edits, no live path touched.**
Script `data/killtests/hidden_signal_grade_20260817.py` · run log `_run.txt` · JSON `_out.json`.
Engine chain imported **UNCHANGED**: `flatten_parity_20260816` → `sunday_afternoon_studies_20260816`
→ G → F → C → B → E — the same objects `sequence_mining_pilot_20260817.py` used, so this study and
the champion-lane pilot are graded by one exit model.
Clock: `date` run this turn — **Mon Aug 17 12:52 EDT 2026**.

The 4th blocker on today's runners is `hidden_observe_only`. That is **Marcos's Friday 8/13
decision**, not a defect. This study asks the only question that could reverse it:
**was the −$4,012 the DETECTOR or the BODY?**

---

## VERDICT (one word first): **SIGNAL IS ALSO BAD**

> The eye was never good. **v2 must not be built on the v1 detector.**
>
> Under E3 live-parity exits — the same exits that carry break-attack **+$17,031** and grinder
> **+$10,442** on this identical universe — the hidden v1 detector loses on **all four entry
> constructions**, on **both halves**, in **every window**, with **N = 4,591** graded trades:
>
> | construction | N | win | total | $/tr | halves | green days |
> |---|---|---|---|---|---|---|
> | **A** enter at fire price | 4591 | 33% | **$−24,065.96** | **$−5.24** | $−12,030 / $−12,036 | 24% |
> | **B** limit at anchor (pullback) | 4206 | 31% | $−18,119.12 | $−4.31 | $−8,586 / $−9,533 | 27% |
> | **C** limit fire+0.5% (kevseq parity) | 4588 | 32% | $−34,790.22 | $−7.58 | $−18,427 / $−16,363 | 17% |
> | **C2** limit fire−0.5% (no fictional fill) | 4320 | 33% | $−19,781.75 | $−4.58 | $−10,235 / $−9,546 | 25% |
>
> **There is no construction that rescues it.** The best arm (B, the pullback-to-anchor entry —
> exactly the "anticipation not confirmation" idea) still loses **$4.31 per trade over 4,206
> trades**. That is not an execution problem you can engineer around; a detector with a real edge
> and bad plumbing shows a *positive* arm somewhere in a four-arm construction grid. This one has
> none.
>
> **This is not underpowered.** N=4,591 over 736 name-days and 63 dates, both halves negative by
> ~$12k each, 76% of days red. Underpowered is the one verdict the numbers rule out.

---

## THE DIRECT ANSWER — DETECTOR, NOT BODY

| measurement | cohort | exits | N | $/trade |
|---|---|---|---|---|
| v1 **live baseline** (`hidden_fix_sweep_20260813` VARIANT A) | 131 live fills 7/24–8/13 | v1's own live ladder | 131 | **$−16.46** |
| v1 **F-control** (the −$4,012) | same 131 | none — hold to EOD, −7% catastrophe only | 131 | **$−30.63** |
| v1 best of 7 exit variants (B90, wider stop) | same 131 | wider stop, frozen to tier-2 | 131 | **$−13.68** |
| **this study, ARM-A**, E3 live-parity | 4,591 universe fires | **E3** (bank ½ @+10%, 10%-off trail, stop-first, 15:45 flatten) | 4,591 | **$−5.24** |
| **this study, ARM-B**, best construction | 4,206 universe fires | E3 | 4,206 | **$−4.31** |

**Read it in dollars per trade.** The BODY was worth about **$11–26 per trade** — going from the
no-stop F-control ($−30.63) to v1's live ladder ($−16.46) to best-available E3 exits ($−5.24)
recovers real money. **It never reaches zero.** Seven exit variants on the live cohort and four
entry constructions on the universe cohort all land on the same side of the line.

So the decomposition is:

* **BODY = the whole −$4,012 headline minus about −$800.** The F-control was a *diagnostic with no
  stop at all*; most of its ugliness is the missing stop, not the entry.
* **DETECTOR = a durable −$4 to −$5 per trade**, measured with the best exits we own, on a cohort
  35× larger than the live one, positive in zero windows and zero halves.

**The −$4,012 was mostly the body. The residual is the detector — and the residual is still
negative, which is the only fact that matters for the rebuild question.** Fixing the body was
never going to be enough, and this study is what proves it rather than assuming it.

### What differed between the −$4,012 control and this grade

| dimension | v1 F-control (8/13) | this study |
|---|---|---|
| **exits** | **none** (EOD hold, −7% catastrophe floor only) — explicitly labelled DIAGNOSTIC ONLY, NEVER SHIPPABLE | E3 live-parity: bank ½ at +10%, 10%-off-high trail, stop-first, halt-gap rule, 15:45 flatten |
| **accounting** | the live 131 carried the **fictional-fill bug** (`fictional_fills_census_20260813.md`: 41 fills, **+$284.78 of fake profit** — resting-bank tiers filling on pre-entry tape). The bug made v1 look **BETTER** than it was, so it is not an excuse for the −$4,012 | replay from raw 10s bars; no resting-fill model that can look backwards. Zero fictional fills by construction |
| **sizing** | live sizing chain (risk/notional/volume clamps, half-size crowns, cap bypasses) | flat **$500 clip**, +1% entry chase, −0.5% market-exit slip — uniform and conservative |
| **gates** | full live stack: ext gate 3–10%, daily cap 3 / name cap 2, crown bypass, stale-fire guard, breakside/backside gates, min-stop exemption | **gate stack NOT applied** (`front_side`/`top3`/`blue_sky`/crown are not reconstructible from the 10s cache). This is a **superset** cohort — and the 8/16 sweep already graded the gated variants (ext-gate, cap-2, ext+cap, first-fire-only, in-window): every one negative |
| **cohort** | 131 live fills, 15 trading days | 4,591 graded trades, 736 name-days, 63 dates |

The accounting bug direction is worth stating plainly, because it is the one thing that could have
exonerated the detector and does not: **the fictional fills inflated v1's results.** The true live
record was *worse* than the −$2,155 baseline, not better.

---

## 1. THE ARCHIVE COHORT — N per day (and why it cannot carry the verdict)

`GET /api/decisions_archive?date=…&limit=20000` (header `X-Dashboard-Secret`), pulled this turn.

| date | `hidden_shadow_fire` | `hidden_observe_only` | total |
|---|---|---|---|
| 2026-08-13 | 137 | 0 | 137 |
| 2026-08-14 | 101 | 37 | 138 |
| 2026-08-15 (Sat) | 0 | 0 | 0 |
| 2026-08-16 (Sun) | 0 | 0 | 0 |
| **2026-08-17 (today, partial)** | 207 | 157 | 364 |
| **TOTAL** | **445** | **194** | **639** |

`hidden_observe_only` starts 8/14 (the split shipped that session); 8/13 rows are the pre-split
`hidden_shadow_fire` detection log plus 126 `triggered_hidden_entry`.

Top names by fires: **IPST 165, WETO 90, IVF 77, FGI 66, DFSC 29, DAIC 28, NIVF 26, HCTI 24,
CGTL 14, CDTG 14, BOXL 12, MF 11.** Marcos's observation is confirmed on the rows — the eye is
pointed at the day's actual runners.

**Why the archive cohort cannot decide this:** it is **33 name-days over 3 sessions**, and only
**16 of the 33 (48%)** exist in the 10s bar cache, so a dollar grade of the archive rows alone
would rest on a handful of names on one and a half sessions. **The universe replay is the
load-bearing arm** and the archive cohort is used here for N, drift, and name identity only.
Reporting a P&L off 2 days of shadow rows is exactly the premature-verdict class Marcos has
already been handed today, and this study refuses it.

### Detector replication — HONESTY STATEMENT

**Faithful, with three named omissions.** `det_hidden_v1` in the script is a line-by-line port of
`hidden_entry_step` (`marcos_trading_bot.py:5937–5987`, read **this turn**): ARM on trailing
30-bar close velocity ≥ 25% (latching); FIRE on `l ≤ anchor=max(e90,vwap)` and `c ≥ anchor` and
`c ≥ vwap` and `(c−l)/(h−l) ≥ 0.5` and `c > o×0.995`; anchor-maturity `nbars ≥ 90`; `stop =
min(l−0.01, c×0.95)`. Env defaults verified this turn (`HIDDEN_VEL_PCT=25`, `HIDDEN_VEL_BARS=30`,
`HIDDEN_ANCHOR_MIN_BARS=90`). Fed FULL-day bars (premarket-anchored VWAP + 90EMA warmed from the
first bar = the live deep pass); RTH-only entries (PRE is its own book).

Not modelled, **all three only reduce N**: (1) the stale-fire guard `_bucket_fresh`; (2) the live
`fired is None` one-fire-per-batch clamp (mitigated by the chain's ≤5-min same-name dedup);
(3) daily cap 3 / name cap 2 / crown bypass. The port is byte-identical to the one used in
`open_holes_sweep1_20260816.py` HOLE C, which independently reached the same conclusion — that
prior result and this one are **not independent evidence**, they are the same detector graded
twice, and this study's contribution is the **construction grid and the splits**, not the
re-confirmation.

### DRIFT — the mandate's confirmation, and it holds

All **194/194** `hidden_observe_only` rows carry both `fire_px` and the live `price`.

| metric | this cohort (8/14 + 8/17) | `entry_drift_20260817.md` finding |
|---|---|---|
| median drift | **−0.17%** | −0.06% |
| mean | −0.34% | — |
| p10 / p90 | −3.13% / +2.71% | — |
| min / max | −13.10% / +15.13% | — |

**CONFIRMED: hidden's drift is well-behaved and 100% age-stamped**, and it is *negative* at the
median (the live quote is marginally **better** than the fire price). Hidden does **not** have
kevseq's defect. That matters because it closes the last available excuse: **the drift did not
break this lane.** ARM-A's numbers are the clean-spec numbers.

---

## 2/3. THE FOUR CONSTRUCTIONS — full E3 table

Live parity: **$500 clip, +1% entry chase, −0.5% market-exit slip, stop-first, bank ½ at +10%
then 10%-off-high trail, halt-gap rule, no new entries ≥15:30 ET, all lanes flattened 15:45 ET.**
Universe: 738 files → **736 graded name-days, 63 dates 2026-05-18 .. 2026-08-17.**

| cohort | N | win | total | $/tr | day mean | day median | worst day | halves | green | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| ARM-A fire price | 4591 | 33% | $−24,065.96 | $−5.24 | $−382.00 | $−391.94 | $−2,128.41 | $−12,030 / $−12,036 | 24% | **FAIL** |
| ARM-B limit @ anchor | 4206 | 31% | $−18,119.12 | $−4.31 | $−287.61 | $−251.00 | $−1,746.26 | $−8,586 / $−9,533 | 27% | **FAIL** |
| ARM-C limit fire+0.5% | 4588 | 32% | $−34,790.22 | $−7.58 | $−552.23 | $−529.94 | $−2,431.16 | $−18,427 / $−16,363 | 17% | **FAIL** |
| ARM-C2 limit fire−0.5% | 4320 | 33% | $−19,781.75 | $−4.58 | $−314.00 | $−365.54 | $−1,813.91 | $−10,235 / $−9,546 | 25% | **FAIL** |

Worst single trades: A $−119.59 · B $−101.41 · C $−121.48 · C2 $−117.68 (the $500 clip caps the
per-trade crater; the damage is *frequency*, not tail).
Exit mix (A): **stop 2,866 · trail 1,199 · 15:45-flatten 516 · halt-gap 8**. Roughly two stops for
every trail — a lane whose median outcome is a stop-out.

**On ARM-C's semantics (disclosed, not buried):** for kevseq the fire price was a setup-bar *high*
— a trigger LEVEL — so "limit at fire+0.5%, filled only when a bar's low reaches it" was a genuine
no-fictional-fill test. For hidden the fire price is a **traded close**, so a limit 0.5% *above* it
fills almost immediately and the arm degenerates into "ARM-A, 0.5% worse" — which is exactly what
the table shows ($−7.58 vs $−5.24). **ARM-C2** (limit 0.5% *below* the fire, unfilled = no trade)
is the honest analogue for a close-anchored lane, and it is reported alongside. Neither is
positive. The kevseq rescue does not transfer.

**BEST CONSTRUCTION: ARM-B, limit at the anchor.** It is the least-bad by $0.93/trade and it
discards ~8% of fires as unfilled. It is worth naming for the v2 record — *pullback-to-anchor is a
better entry than chasing the reclaim close* — but it is a **loss-reduction finding, not an edge**.
A lane at $−4.31/trade is not a lane.

---

## 4. THE RUNNER SPLIT — and the finding that runs the other way

Day-gain proxy = (fire close / first cached bar open of the name-day) − 1. **Stated limitation:**
the 10s cache carries no prior close, so this is an intraday-from-first-cached-bar gain. It
**understates gap-up names**, which makes the ≥25% cell a conservative subset and the <25% cell
contaminated with true runners that gapped before the cache started.

| cell | N | win | total | $/tr | halves | green% |
|---|---|---|---|---|---|---|
| **A day-gain ≥25%** | 4111 | 32% | $−29,635.31 | **$−7.21** | $−17,285 / $−12,350 | 13% |
| **A day-gain <25%** | 480 | 46% | $+5,569.34 | **$+11.60** | $+5,255 / $+314 | 53% |
| B day-gain ≥25% | 3775 | 29% | $−23,181.02 | $−6.14 | $−13,498 / $−9,683 | 21% |
| B day-gain <25% | 431 | 42% | $+5,061.90 | $+11.74 | $+4,913 / $+149 | 56% |
| C2 day-gain ≥25% | 3868 | 31% | $−25,023.31 | $−6.47 | $−14,831 / $−10,193 | 16% |
| C2 day-gain <25% | 452 | 44% | $+5,241.56 | $+11.60 | $+4,595 / $+646 | 55% |

**This is the opposite of today's convergent finding, and it does not survive scrutiny.** The
runner cell — where every other lane's edge lives — is hidden's **worst** cell (**$−7.21/tr, 13%
green days**). The only positive cell is the *anti*-runner cell, and I am **not** reporting it as
an edge, for four reasons checked this run:

1. **It dies out-of-sample.** Split at the cohort median date 2026-07-02: first half **$+19.68/tr**
   (N=267), second half **$+1.47/tr** (N=213). A **13× collapse** — the signature of an in-sample
   sliver, not a mechanism.
2. **It is two days.** 2026-06-17 ($+1,167) and 2026-06-11 ($+1,050) are **40% of the $5,569** across
   49 dates.
3. **It is one name.** The top five trades are all **ELTX 2026-06-17** (+$232, +$231, +$230, +$229,
   +$228) — the same name-day firing five times inside the dedup window.
4. **It is 10% of the cohort** (480 of 4,591) and it is defined by a **proxy** whose known bias is
   to misclassify gapped runners into it.

Anyone who reports "hidden works on sub-25% names" off this cell is doing exactly what Marcos was
handed earlier today. **It is reported here so it cannot be rediscovered as news, and it is
refused as a finding.**

### Sizeability — can we even trade it?

* Fire-bar dollar volume: **median $103,222**, p10 $3,297, p90 $643,339.
* Cumulative session dollar volume at fire: **median $140.6M**, p10 $8.6M.
* **12% of fires (567/4,591)** fire on a 10s bar that traded **under $5,000** — a $500 clip is >10%
  of that bar's entire dollar volume.

So **88% of the cohort is sizeable at $500** and liquidity is not the binding constraint. Which
removes the last alternative explanation: hidden does not lose because we cannot fill it.

| cell | N | win | total | $/tr | halves | green% |
|---|---|---|---|---|---|---|
| A fire-bar $vol ≥ median | 2296 | 30% | $−21,505.33 | $−9.37 | $−14,460 / $−7,046 | 14% |
| A fire-bar $vol < median | 2295 | 37% | $−2,560.64 | $−1.12 | $+2,430 / $−4,991 | 37% |

Both negative. The thicker-tape half is the **worse** half — the same inversion as the runner
split, and the same non-finding.

---

## NAMED TRACES (dollars through the real chain, per the drop-dead)

**Best ARM-A fire — NPT 2026-06-08 17:43:20Z** (13:43 ET): bar o 3.0500 h 3.1300 l 3.0100 c 3.1200,
anchor 3.1038, stop 2.9640 (5.0% risk). Fill 3.1512 after the +1% chase = **158.7 shares on a $500
clip**. 17:46:20 bank 0.50 at +10% (3.4663); 18:11:50 trail[off10] close 8.0100 fill 7.9699.
**→ $+407.29.** This is the single best fire in 4,591 — on a name that went 3.15 → 8.01, outside
the first hour, and the lane still loses $24k around it.

**Worst ARM-A fire — EZRA 2026-08-03 13:35:40Z**: stop 3.2050, stopped 13:36:50, **$−119.59** —
70 seconds from fire to stop.

---

## WHAT THE HIDDEN ENTRY ARCHITECT SHOULD TAKE FROM THIS

1. **Do not rebuild a body around the v1 detector.** The wick-reclaim-of-max(90EMA,VWAP) trigger,
   ungated, at ~22 fires/day, is measured negative at N=4,591 under the best exits we own, on both
   halves, in all four constructions, at every liquidity tier and both sides of the runner split.
   The v2 mandate's "anticipation not confirmation" instinct is **vindicated as a critique of v1** —
   ARM-B (anticipate the pullback to the anchor) beats ARM-A (confirm at the reclaim close) by
   $0.93/trade — but it is a better way to lose, not a way to win.
2. **The eye's name-selection is real and is worth keeping; its bar-selection is not.** IPST/IVF/
   FGI/NIVF/CDTG are the right names. That is the *velocity ARM* (25%/5min) doing the work, and the
   ARM is reusable — it is a **roster/attention signal**, not an entry trigger. The FIRE condition
   is what is refuted.
3. **v2 (flush → higher-low → close > prior high) is a different trigger and is untouched by this
   finding**, exactly as `open_holes_sweep1_20260816.md` stated. Nothing here promotes or demotes
   the v2 shadow.
4. **Marcos's Friday `hidden_observe_only` call is CONFIRMED by measurement.** It should not be
   reversed. The 4th blocker on today's runners is the system working.

---

## OFFICERS TOUCHED

**Hidden Entry Architect** — the rebuild question is answered: not on this detector; ARM-B and the
velocity-ARM-as-roster-signal are the two salvageable pieces.
**Wind Tunnel Engineer** — chain imported unchanged, live-parity mode, no engine edits.
**Statistician** — every number here is in `_out.json` and `_run.txt`; nothing unledgered.
**Convexity Trader** — judged on mean-after-costs and tail shape, not win-rate; the tail is capped
by the clip and the mean is negative in every cell that survives scrutiny.
**Strength Ombudsman** — the runner cell was graded, not skipped; hidden's failure on strength is a
*measured* result, not a refused-strength bias. Flagged for the bias ledger: this is the one lane
where strength is the losing cell, which is itself evidence the trigger is wrong for the regime.
**Handicapper / Forward Architect** — the sub-25% and thin-tape cells are registered as REFUTED
slivers so they are not rediscovered.
**Blast Radius Auditor** — clean: analysis only, read-only replay, no live path, no env, no deploy.
**Side Marshal** — clean (side not stamped in this study; the 10s cache cannot reconstruct it).
**Historian** — run 2026-08-17, `date` cited in transcript; supersedes nothing, corroborates
`open_holes_sweep1_20260816.md` HOLE C with the construction grid it lacked.

---

## FAILURE CONDITION (what would make this study wrong)

This verdict is **wrong** if any of the following is later shown:

1. The detector port diverges materially from `hidden_entry_step` in a way that **adds** fires the
   live lane would not take *and* the excluded fires are the profitable ones. (Checked: all three
   unmodelled gates only *reduce* N, and the 8/16 sweep graded five gated variants — all negative.)
2. A construction not in this grid — a materially different stop (not just wider; seven widths were
   already tested on the live cohort), a time-stop, or a different exit family than E3 — turns a
   cell positive on **both halves at material N**. Nothing in nine tested variants suggests it.
3. The universe cache is unrepresentative of the names the live scanner admits. Note the cohort is
   a **superset** (736 name-days incl. everything the scanner ever cached), so this cuts toward
   *understating* selection, not overstating it.

**It is NOT made wrong** by finding a profitable slice of ≤10% of the fires that fails a half —
that class is pre-refused above.
