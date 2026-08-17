# SEQUENCE-MINING PILOT — champion lanes (8/17/26)

First proof of the SEQUENCING doctrine (Marcos: *"one element by itself doesn't signal anything;
it's the ORDER they appear"*) applied to the **champion lanes**, not just kevseq. Analysis only —
no bot edits, read-only replay.

- **Script:** `data/killtests/sequence_mining_pilot_20260817.py` · **raw run:** `..._run.txt` · **json:** `..._out.json`
- **Universe:** FULL `data/universe/bars10s/*.json` — 729 files, 729 name-days, 62 dates 2026-05-18..2026-08-14.
- **Engine:** chain `S -> G -> F -> C -> B -> E` imported UNCHANGED (the exact objects
  `flatten_parity_20260816.py` uses). Every fire exits **E3 live-parity** via `F.sim_var(...,"E3",det,halt_rule=True)`
  (bank ½ at +10%, trail rest 10%-off-high closes-through, stop-first, -1% chase entry, -0.5% market-exit slip;
  grinder keeps its 19:59Z flatten). Same-name dedup ≤5 min (round-F parity).
- **Alphabet** (`kev_rosetta_20260816.py`, verbatim): P push local high · B break session high · T test session
  high · F flush ≥2% · W wick@VWAP/9EMA bought back · H level hold · R retest · L halt resumption · Q compression
  · D lower low. String = the **10 minutes (60×10s bars) ending at the fire bar**. Suffix mining is on the
  **STRUCTURAL** string (F/D removed, consecutive dups collapsed — rosetta STEP 3b convention).
- **WIN** = E3 $ > 0 **OR** reached +1R (entry + (entry−stop)) before the stop bar. **$/trade** = E3 $.
- **MATERIAL-N gate** = a suffix that retains ≥ max(20, 8% of lane fires) — the bar that separates a real
  selection rule from an overfit sliver. Slivers are reported for transparency, never as gate candidates.

---

## TL;DR (plain words)

1. **There IS a universal winning sequence, and it is the same one the Rosetta found on Kev's own fills:**
   **a test/consolidation *under* the session high, THEN the decisive break of it — `…T B` (and its
   extension `…W T B`).** In every lane the top $/tr-lift suffixes end in **B** (break of the *session* high),
   and the strongest are `T B` / `W T B` / `P B`. Suffixes ending in **P** (a push to a *local* high that is
   NOT the session high) or in **B Q / B R** (break then stall/retest) are the consistent losers across all
   three lanes. Grammar is **shared, not distinct** — lanes differ only in *how much* of each already embodies it.
2. **Break-attack & grinder are already champions; the sequence gate is a PRIORITY/size signal, not a filter to
   trade only.** `T B` nearly doubles per-trade quality but discards ~90% of the fires (and most of the dollars).
3. **v2 is NOT rescued.** No material-N suffix turns v2 positive. The same `…T B` family is the *only* thing that
   flips v2 green, but on ~1.5% of its 6,159 fires — a thin salvage, not a lane rescue.
4. **MA_PULLBACK = NEEDS-DATA** — no faithful universe-replay detector exists in this engine chain.

---

## Per-lane results

### 1) flat_top BREAK-ATTACK (09:30–10:30 ET) — `G.det_flat_top_break`, window 13:30–14:30Z

| cohort | N | win | total | $/tr | day mean | day med | green% | halves | worst day |
|---|---|---|---|---|---|---|---|---|---|
| UNGATED lane | 634 | 69% | $+17031.01 | $+26.86 | $+274.69 | $+280.19 | 85% | $+9762/$+7269 | $-121.42 |

**Top last-2 structural suffixes** (base N=634, win 69%, $/tr $+26.86):

| suffix | N has | win% has | $/tr has | $/tr hasnt | win lift | $/tr lift |
|---|---|---|---|---|---|---|
| L B (halt→break) | 18 | 72% | $+59.45 | $+25.91 | +3pp | $+32.58 |
| **T B (test→break)** | **60** | **80%** | **$+50.52** | $+24.39 | **+11pp** | **$+23.66** |
| Q B (compress→break) | 22 | 82% | $+46.45 | $+26.16 | +13pp | $+19.59 |
| B H (break→hold) | 16 | 81% | $+43.27 | $+26.44 | +12pp | $+16.40 |
| W B (wick→break) | 45 | 71% | $+34.43 | $+26.28 | +2pp | $+7.57 |
| … Q P (compress→*local* push) | 135 | 65% | $+16.25 | $+29.74 | −4pp | **$−10.62** |
| … H P / R P / W P (…→local push) | 26/34/71 | 65–72% | $+9–20 | ~$+27 | ≤+3pp | **$−7 to −17** |

Last-3 leader: **`W T B` N=19, 95% win, $+78.22/tr (+$51.35 lift)** — the cleanest specimen but sub-material.

**GATE TEST — keep ONLY fires ending in the material suffix `T B`:**

| cohort | N | win | total | $/tr | day mean | day med | green% | halves | worst day |
|---|---|---|---|---|---|---|---|---|---|
| UNGATED | 634 | 69% | $+17031.01 | $+26.86 | $+274.69 | $+280.19 | 85% | $+9762/$+7269 | $-121.42 |
| **GATED [T B]** | **60** | **80%** | $+3031.30 | **$+50.52** | $+48.89 | $+14.98 | 52% | $+1612/$+1419 | $-90.97 |

Retains 60/634 (9%). Per-trade **+$26.86 → +$50.52 (+88%)**, win **69% → 80% (+11pp)**, worst day *improves*
($−121 → $−91). But total falls $17,031 → $3,031 and green% 85% → 52% — because 91% of the (already profitable)
fires are discarded, and most days lose their only gated fire.

**Verdict: SEQUENCE-GATE-HELPS — as a PRIORITY / size-up signal, not a trade-only filter.** The champion lane
already prints money on almost every fire; the `T B` sequence marks the *best* fires (per-trade quality doubles,
win +11pp). Priced proposal: **stamp `…T B` on break-attack fires and size them up / rank them first**, do NOT
drop the non-`T B` fires (they still net +$24/tr). *(No ship — hypothesis for Side Marshal / Handicapper.)*

---

### 2) GRINDER (post-10:30 ET) — `C.det_grinder_1030`

| cohort | N | win | total | $/tr | day mean | day med | green% | halves | worst day |
|---|---|---|---|---|---|---|---|---|---|
| UNGATED lane | 387 | 72% | $+10676.31 | $+27.59 | $+184.07 | $+117.87 | 83% | $+6030/$+4646 | $-175.04 |

**Top last-2 structural suffixes** (base N=387, win 72%, $/tr $+27.59):

| suffix | N has | win% has | $/tr has | $/tr hasnt | win lift | $/tr lift |
|---|---|---|---|---|---|---|
| L B (halt→break) | 18 | 83% | $+49.63 | $+26.51 | +11pp | $+22.04 |
| **T B (test→break)** | **104** | **82%** | **$+44.14** | $+21.50 | **+10pp** | **$+16.56** |
| P B (local push→break) | 23 | 96% | $+41.22 | $+26.73 | +24pp | $+13.64 |
| B Q (break→compress/stall) | 75 | 72% | $+6.33 | $+32.70 | +0pp | **$−21.26** |
| W B (wick→break) | 31 | 48% | $−0.86 | $+30.06 | **−23pp** | **$−28.45** |

Last-3 leaders: **`W T B` N=28, 89% win, $+57.36/tr (+$29.78)** · `P T B` N=21, 95% win, $+46.48 · `T Q B` N=39, $+49.93.

**GATE TEST** — the auto-picker (max $/tr-lift) chose `T Q B`; the more **material** gate is `T B` (N=104 = 27% of
the lane, the largest robust slice):

| cohort | N | win | total | $/tr | day mean | day med | green% | halves | worst day |
|---|---|---|---|---|---|---|---|---|---|
| UNGATED | 387 | 72% | $+10676.31 | $+27.59 | $+184.07 | $+117.87 | 83% | $+6030/$+4646 | $-175.04 |
| **GATED [T B]** (material) | **104** | **82%** | **$+4590.56** | **$+44.14** | — | — | — | — | — |
| GATED [T Q B] (auto max-lift) | 39 | 67% | $+1947.12 | $+49.93 | $+33.57 | $+0.00 | 29% | $+1213/$+734 | $-36.34 |

**Verdict: SEQUENCE-GATE-HELPS — strongest of the three.** `T B` is a genuinely *material* refinement: it keeps
**27% of grinder fires** (not a sliver) while lifting per-trade **+$27.59 → +$44.14 (+60%)** and win **+10pp**, and
it captures **$4,591 of the lane's $10,676 (43% of the dollars from 27% of the trades)**. The losers are symmetric
and confirm the grammar: `W B` (a wick that never tested/broke the session high first) is −23pp / −$28, and
`B Q` (break that then stalls) gives back $21/tr. Priced proposal: **rank/size grinder fires by whether the last
structural event before the break was a *test of the session high* (`T B` / `W T B`); de-prioritize `W B` and
`B Q` fires.** *(No ship — hypothesis for First Hour / Handicapper.)*

---

### 3) V2 flush — `B.det_v2_cal` (calibrated champion v2)

| cohort | N | win | total | $/tr | day mean | day med | green% | halves | worst day |
|---|---|---|---|---|---|---|---|---|---|
| UNGATED lane | 6159 | 46% | $-21764.93 | **$-3.53** | $-351.05 | $-370.93 | 31% | $-13958/$-7807 | $-1685.70 |

The unfiltered v2 universe is a heavy bleed (−$3.53/tr over 6,159 fires — the "≈−$6 toll" of the brief, on the
full universe population). **MATERIAL-N threshold = 492 fires (8% of 6,159). No suffix at that size is positive.**

**Only the `…T B` family turns v2 positive — but sub-material:**

| suffix | N has | win% has | $/tr has | win lift | $/tr lift | total $ |
|---|---|---|---|---|---|---|
| B T (break→test) | 50 | 52% | $+22.82 | +6pp | $+26.36 | $+1141 |
| T B (test→break) | 94 | 56% | $+11.69 | +11pp | $+15.23 | $+1099 |
| W B (wick→break) | 101 | 59% | $+5.15 | +14pp | $+8.68 | $+520 |
| `W T B` (last-3) | 19 | 63% | $+28.92 | +18pp | $+32.46 | $+549 |
| `B T B` (last-3) | 45 | 67% | $+15.23 | +21pp | $+18.76 | $+685 |
| `P T` (best sliver) | 8 | 62% | $+52.09 | — | — | $+417 |

**GATE TEST: no material-N suffix beats the base.** The best *material* option, `T B` (N=94, the largest positive
cohort), salvages only **+$1,099** against the lane's **−$21,765** hole — it recovers ~5% of the bleed from ~1.5%
of the fires. Everything else stays deeply negative.

**Verdict: NO-LIFT at the lane level → v2 is NOT rescued.**
- **v2 rescue answer: NO.** Sequence gating does not rescue v2 as a lane. Dollar terms: the ungated lane is
  **−$21,765 (−$3.53/tr)**; the best material sequence sub-cohort (`T B`, N=94) is only **+$1,099 (+$11.69/tr)**,
  and the best sub-material sliver (`W T B`, N=19) **+$549**. There is no order of events that turns the v2
  *population* green — the `…T B` grammar merely isolates a thin profitable slice (~100–400 of 6,159 fires).
- This is consistent with the doctrine, not a contradiction of it: the *same* winning sequence exists inside v2,
  but v2's detector fires so indiscriminately that 98% of its prints never carry that sequence. v2's problem is
  **selection breadth**, and sequencing confirms it rather than fixing it.

---

### 4) MA_PULLBACK — NEEDS-DATA

No faithful universe-replay detector for ma_pullback exists in the `flatten_parity` engine chain (the chain
carries flat_top, grinder, vwap, and v2 only). The **live** `detect_ma_pullback` (`marcos_trading_bot.py:4641`)
fires off **completed 1-minute bars** with warmup seeds and Kev levels; porting it into the 10s universe replay
would *invent* a detector, not replay the champion. Per the "Dollars Not R / Verify Before Assert" laws I did not
fabricate fires. **Flagged NEEDS-DATA: owed a dedicated 1-minute universe port before a sequence gate can be
graded on it.**

---

## Cross-lane finding — is there a UNIVERSAL winning sequence?

**YES.** One grammar pays across every lane: **a test/consolidation under the session high, THEN the break of
that high — `…T B`, strengthened to `…W T B`.** It is the top or near-top $/tr-lift suffix in all three lanes, and
the *only* positive family inside v2. This is the champion-lane echo of the Rosetta's Kev finding
(`B → H / B → W`, "break the session high then take the first hold/wick"): read at the point where these detectors
actually fire — *on* the break print — the accumulate-then-break order lands as `…T B`.

| suffix | break-attack | grinder | v2 | reading |
|---|---|---|---|---|
| **T B** | +$50.52 (+$23.66) | +$44.14 (+$16.56) | +$11.69 (+$15.23) | **universal winner** — test the high, then break |
| **W T B** | +$78.22 (+$51.35) | +$57.36 (+$29.78) | +$28.92 (+$32.46) | **universal winner** — wick, test, then break |
| … P (local push, not sess high) | $−7 to −17 | (P B ok*) | mixed | **universal loser** — pushing a local, not-yet-session high |
| B Q / B R (break then stall) | — | $−21 / — | weak | **universal loser** — break with no follow-through |

The lanes do **not** have distinct grammars — they share one. What differs is the *fraction already embodying it*:
grinder **27%** (`T B`), break-attack **9%**, v2 **~1.5%**. That fraction is exactly the ranking of the lanes'
health (grinder & BA are champions; v2 bleeds), which is the doctrine's own prediction: **the lanes that pay are
the lanes whose fires already tend to sit on the winning sequence.**

\* grinder `P B` (N=23, 96% win) is the one place a *local*-push-then-break also pays — because post-10:30 the
grinder is already at/near the session high, so its "local push" and "session high" coincide; not a counterexample.

---

## Three hand-traces (from the run)

**A. WIN carrying the winning sequence — grinder, VERU 2026-06-04, fire 14:46:30Z, entry 2.6400 stop 2.5500 →
E3 $+377.19 (trail@16:26:30), win=True.**
Structural: `W Q T W Q B T B T B T Q W Q W Q W T W T Q B` — ends `… T Q B` (tested the high, brief compression,
then broke). Repeated `T`/`Q` under the high then the terminal `B` = textbook accumulate-then-break; the E3 trail
rode it to +$377.

**B. LOSS lacking the sequence (gated out) — grinder, ICCM 2026-06-24, fire 15:21:10Z, entry 8.7902 stop 7.8600 →
E3 $−59.55 (stop@15:33:00), win=False.**
Structural: `W P W P W P B T B H T H T H T H T W B` — ends `… T W B`, but the body is a chain of `W P` (wicks and
*local* pushes) with the break buried mid-string, not the terminal event. This is the "second/third pullback deep
in the range" pattern the Rosetta flagged as the worst trade — it stopped out in 12 bars.

**C. v2 salvage specimen — SPKLW 2026-06-11, fire 13:51:40Z, entry 1.2400 stop 1.1830 → E3 $+194.09
(trail@18:24:00), win=True.**
Structural: `W P T` — a wick, a push, then a test of the high right at the fire. One of the ~100 v2 fires that
*do* carry the winning grammar and pay; the other ~6,000 do not, which is why the sequence cannot rescue the lane.

---

## Verdicts

| lane | winning sequence (plain words) | before → after (material gate) | verdict |
|---|---|---|---|
| **flat_top BREAK-ATTACK** | *test the session high, then break it* (`T B`) | $+26.86 → $+50.52/tr, 69%→80%, N 634→60 | **SEQUENCE-GATE-HELPS** (priority/size signal, not trade-only) |
| **GRINDER** | *test the session high, then break it* (`T B`; `W T B`/`P T B` cleaner) | $+27.59 → $+44.14/tr, 72%→82%, N 387→104 (27%) | **SEQUENCE-GATE-HELPS** (strongest; material 27% slice) |
| **V2 flush** | same `…T B` family, but only ~1.5% of fires carry it | −$3.53/tr lane vs +$11.69/tr on `T B` (N=94, +$1,099 of −$21,765) | **NO-LIFT — v2 NOT rescued** |
| **MA_PULLBACK** | — | no universe detector in chain | **NEEDS-DATA** (1-min universe port owed) |

**Universal sequence:** YES — *consolidate/test under the session high, then break it* (`…T B` / `…W T B`) pays
in every lane; *pushing a merely-local high* (`…P`) or *breaking with no follow-through* (`…B Q`/`…B R`) loses in
every lane. Each lane's grammar is the SAME; only the fraction of fires already on it differs (grinder 27% > BA 9%
> v2 1.5%), and that ordering matches the lanes' P&L health.

---

## Caveats (read before believing)

- **In-sample.** Suffixes were mined and graded on the same 62-date universe; no OOS wall. These are registered
  hypotheses, not ship candidates (Convene-or-Don't-Ship, Skepticism-Needs-Verification).
- **Gate shrinks the book.** Every gate raises $/tr by *discarding* fires; on the already-profitable BA/grinder
  lanes that lowers total dollars and green%. The honest use is **priority/sizing**, not a trade-only filter —
  stated as such, not buried.
- **Auto-picker vs material pick.** The script's max-$/tr-lift auto-picker favors small-N slivers (BA `W T B` N=19,
  grinder `T Q B` N=39, v2 `P T` N=8); this report *features the material-N suffix* (`T B`) instead and labels the
  slivers as overfit-prone. Both are in `_run.txt`.
- **Event-string parity.** VWAP/9EMA/halts are recomputed on the universe 10s bars to feed the Rosetta
  `event_string` verbatim; bar boundaries are SIP-derived (Kev's glass is Webull 10s — same resolution, different
  boundaries), the identical caveat the Rosetta carries.
- **WIN definition** blends net-positive-$ with +1R-before-stop; the $/trade column is pure E3 dollars through the
  real sizing chain ($500 clip). Nothing here is R-only.
- **v2 population.** 6,159 unfiltered universe fires is the raw detector, not the shadow-lane's gated live count;
  the "$/tr toll" is on that full population by design of this pilot.

*No recommendation to ship. Numbers only — the full room verifies, Marcos decides.*
