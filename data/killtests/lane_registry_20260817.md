# LANE CLASSIFICATION REGISTRY — 8/17 (Marcos: "build it now")

## ⚠️ READ THIS FIRST — THE COUNTERFACTUAL IS NET NEGATIVE

The era-wide (7/13+) counterfactual on the lanes this change newly exempts is **−$64.25 over
N=13, −$4.94/trade, 31% win**. The build shipped anyway because the doctrine is SETTLED (7/24 +
7/26) and Marcos ordered it — but **the number is negative and Marcos decides whether to keep
`LANE_REGISTRY_EXEMPT=1`.** Flip it to `0` and every gate falls back to its pre-8/17 hardcoded
tuple exactly, no deploy required.

Three things materially qualify that number, and none of them rescue it on their own:
- **`rocket_catcher` (default OFF since 7/24) supplies −$108.65 of the −$64.25.** Excluding a
  lane that cannot fire, the set is **+$44.40 over N=10**.
- **Today's 8/17 rows are TRUNCATED at 11:34 ET (`date` run in-turn).** Four of them exit "eod"
  at the last printed bar — those are marks-to-now, not exits. Per the halt-lane rule, a
  partial-tape calibration owes a **same-night full-day re-grade**; this one does.
- **`kevseq`, the lane this task exists for, is +$32.58 on its single specimen** (WFF, below).

## FAILURE CONDITION — this is WRONG if:

1. The chart-derived break level is genuinely predictive **for tape lanes too**, i.e. the newly
   exempted lanes' blocked cohort grades NEGATIVE on ≥8 gradeable full-day fires. The −$64.25
   above is the first evidence, and it leans that way — it is under the n≥8-per-lane bar and
   contaminated by a dead lane and a truncated tape, but it is not nothing.
2. `lane_exempt_applied` rows accumulate with no correspondingly better outcome than the
   `chart_gate_blocked_trade` cohort they replaced (Friday's grade).
3. A lane classified "tape" here actually triggers off a chart-derived level (misclassification).
   The registry's classification is a CLAIM about each detector; if a detector changes what it
   reads, its class must move with it.
4. Guard rail false-green: a new lane is emitted through a call shape section AO cannot read. AO
   walks the AST for `breakouts.append((...))` and takes tuple element [3], and it goes RED if that
   element is anything but a plain string literal — so a computed lane name fails loudly rather
   than slipping through. Negative control run this turn: renaming one emitted lane to an
   unclassified name reproduces the RED.

## THE DEFECT

The SETTLED doctrine — *live-structure/TAPE lanes trade through chart-derived and setup-quality
vetoes; only tradeability floors and their own lane conditions gate them* (7/24 Marcos "switch the
reclaim and zone flip", 7/26 "no absolute never-trade — let the chart and tape decide") — was
implemented as **copy-pasted hardcoded string tuples inside each gate**. A lane born after a gate
was written silently defaults to the WRONG side.

Cost, proven today, three instances:
- **(a) `_chart_break_gate`** — `_bypass = ("hidden_entry","vwap_reclaim","zone_flip") + ignition?`.
  WFF 11:17:43 kevseq fired $5.039, `chart_gate_block` one second later, on a name that ran
  $1.61 → $6.00 (+307%).
- **(b) extension gate (25% over EMA90)** — auditor B2-F1: the exempt tuple omitted all five tape
  lanes; kevseq fires append into the same `breakouts` list.
- **(c) `check_momentum`** — already fixed at noon (`173d8f1`, `TAPE_LANE_SCALAR_EXEMPT`). Now
  reads from the registry instead of a hand-typed default; **behavior unchanged**.

## THE REGISTRY (`marcos_trading_bot.py`, near the top — single source of truth)

Derived from every `breakouts.append` call site, not invented.

| entry_type | class | why |
|---|---|---|
| `hidden_entry` | tape | Kev 10s rocket wick off the anchor |
| `vwap_reclaim` | tape | session-VWAP 3-gate reclaim |
| `zone_flip` | tape | flush → bottoming wick → curl |
| `rocket_catcher` | tape | 1-min 20-EMA parabola catch (SUPERSEDED 7/24, `ROCKET_CATCHER=0`) |
| `kevseq` | tape | 8/16 Kev sequence lane ← **the lane that was missing everywhere** |
| `v2conv` | tape | hidden v2 flush-entry convert |
| `grinder` | tape | slow-build 10s grind |
| `bandpass` | tape | 2–5 min band-pass reclaim |
| `prevwap` | tape | premarket VWAP reclaim convert |
| `crown_seam` | tape | 5s seam pull on a crowned name (`SEAM_CONVERT`) |
| `halt_ladder` | tape | LULD halt-ladder arm on a crowned name (`HALT_LANE_CONVERT`) |
| `flat_top` | chart | base break off the chart |
| `ma_pullback` | chart | pullback to a charted MA |
| `orb` | chart | opening-range break |
| `ema_bounce` | chart | EMA9 bounce |
| `bounce` | chart | observe-only; filtered before the order path |
| `dip_rip` | chart | dip **to a marked level** — the level IS the trigger |
| `ignition` | hybrid | chart-classed by history, chart-BYPASSED only under `IGNITION_CHART_BYPASS` (7/30 Fable ship, measured) — semantics preserved byte-for-byte |

Helpers: `TAPE_LANES` / `CHART_LANES` frozensets, `_is_tape_lane(entry_type)` (unknown → False,
fail-safe: an unclassified lane keeps the conservative gated behavior and rig AO goes RED).

## GATES ENUMERATED (three-rings: every lane-name tuple in the file was found and dispositioned)

### REWIRED to derive from the registry
| gate | line | old literal | now |
|---|---|---|---|
| `_chart_break_gate` `_bypass` | ~3437 | `("hidden_entry","vwap_reclaim","zone_flip") + ignition?` | `_chart_bypass_lanes()` = `TAPE_LANES` + ignition (unchanged env-conditional) |
| extension guard (25% > EMA90) | ~9160 | `("rocket_catcher","hidden_entry","flat_top","orb","ma_pullback","vwap_reclaim","zone_flip")` | `_ext_exempt_lanes()` = `TAPE_LANES` + `_EXT_SLOW_RETEST_EXEMPT{flat_top,orb,ma_pullback}` |
| `_STALE_EXEMPT` (read-exhausted) | ~3430 | `("rocket_catcher","vwap_reclaim","zone_flip","hidden_entry")` | `TAPE_LANES` — **observe-only branch** (the hard skip was refuted 7/21), so no money delta |
| `TAPE_SCALAR_EXEMPT_LANES` default | ~5210 | hand-typed `"kevseq,v2conv,grinder,bandpass,prevwap"` | LITERAL kept (see note below), but rig-AO-pinned equal to `_momentum_exempt_lanes() - _MOMENTUM_LEGACY_EXEMPT` |
| `check_momentum` exempt tuple | ~12830 | inline 8-tuple | `_MOMENTUM_LEGACY_EXEMPT` constant at the top — **membership unchanged** |

`TAPE_SCALAR_EXEMPT_LANES`'s default stays a LITERAL at `:5210` on purpose: rig section AL
exec-evaluates that exact block in an isolated namespace (only `os` bound), so a call into the
registry there breaks the kill-switch-honesty fixture. Its single-source guarantee is enforced by
rig AO instead, which asserts it equals `_momentum_exempt_lanes() - _MOMENTUM_LEGACY_EXEMPT` and
goes RED the moment a new tape lane makes the two drift apart.

Rig pins **amended** (not merely added): `AF-l`, `AG-x`, `AH-x` asserted that `bandpass` / `kevseq`
/ `v2conv` were ABSENT from `_STALE_EXEMPT` — those assertions encoded the defect. They now pin
only the tradeability (`MIN_STOP_EXEMPT`) and side (`BACKSIDE_EXEMPT`, `VRIDE_EXEMPT`) sets, which
are unchanged. An auditor should confirm that rewrite is legitimate and not self-green-washing.

### AUDITED, deliberately NOT rewired (with the reason)
| list | line | why untouched |
|---|---|---|
| `BREAKSIDE_LANES` | ~7318 | INCLUSION list (which lanes the back-side gate applies to). Deriving it would newly **block** tape lanes — more restrictive, not ordered. |
| `TAPE_PREBREAK_LANES` | ~7332 | Same: inclusion list of gated tape lanes. Missing kevseq/v2conv/grinder/bandpass/prevwap → **OPEN HOLE, flagged for Marcos** (closing it removes money, so it's his call, not an auditor's). |
| `CHART_CEILING_LANES` | ~7337 | Chart-lane inclusion list; equals `CHART_LANES − {bounce}`. Left literal to avoid a no-op behavior change on a dead lane. |
| `BACKSIDE_EXEMPT = {"dip_rip"}` | ~7242 | Back-side gate deliberately DOES bind tape lanes (settled 8/5, era −$147 in-band bleed). |
| `MIN_STOP_EXEMPT` | ~7522 | Tradeability floor — doctrine keeps tape lanes subject. |
| `DAYGAIN_LEGACY` | ~6460 | Chart lanes + ignition; not cleanly derivable, and deriving would change membership. |
| vel5 floor tuple | ~9103 | `("flat_top","ma_pullback","orb","ema_bounce")` — deriving `CHART_LANES` would newly gate `dip_rip`/`bounce` (more restrictive). |
| `PRE_LANES` / `RETEST_LANES` | ~13295 / ~5097 | Env-single-source inclusion lists, no copy-paste twin. |
| `_MOMENTUM_TAPE_HOLDOUT` | registry | `rocket_catcher`, `crown_seam`, `halt_ladder` stay SUBJECT to the momentum scalar so `check_momentum` behavior is unchanged. **SPEC TENSION** — doctrine says they should be exempt; Marcos's call. |

## BEHAVIOR DELTAS (exhaustive)

With `LANE_REGISTRY_EXEMPT=1` (default):
1. **Chart gate** — newly bypassed: `kevseq`, `v2conv`, `grinder`, `bandpass`, `prevwap`,
   `crown_seam`, `halt_ladder`, `rocket_catcher` (OFF).
2. **Extension guard** — newly exempt: the same eight lanes.
3. **`_STALE_EXEMPT`** — the same eight lanes now skip the `read_exhausted_observed` stamp.
   **Observe-only; no money.**
4. **Nothing else.** No lane loses an exemption. No chart lane gains one. `ignition` unchanged.
   `check_momentum` unchanged. Every newly-granted bypass logs
   `lane_exempt_applied(lane, gate, price)` — Friday grades those rows.

With `LANE_REGISTRY_EXEMPT=0`: every rewired gate returns to its pre-8/17 literal exactly
(rig-pinned, including "kevseq is GATED again").

## COUNTERFACTUAL (`lane_registry_20260817.py`)

Archive 6/29–8/17 (era 7/13+ only), `chart_gate_blocked_trade` / `extension_reject` rows joined
to a lane by nearest same-ticker row within ±20s (**limitation: neither row type carries a lane
stamp** — a stamp is worth adding). E3 live-parity on `data/universe/bars10s`: $500, +1% slip,
bank ½ at +10%, trail 10%-off-run-high on closes, intrabar stop first, −0.5% on market exits.

- Newly-exempt-lane gate rejects, era 7/13+: **N=14** (all `chart_gate_blocked_trade`;
  **zero `extension_reject`** — these lanes die at the chart gate before the extension guard).
- Simulable: **N=13** (BRNX 08:23 prevwap has no bars).
- **TOTAL −$64.25 · $/tr −$4.94 · win 31%.**

| lane | N | total |
|---|---|---|
| `halt_ladder` | 3 | **+$93.93** |
| `kevseq` | 1 | **+$32.58** |
| `v2conv` | 2 | −$17.20 |
| `grinder` | 4 | −$64.91 |
| `rocket_catcher` (OFF) | 3 | −$108.65 |
| **excl. `rocket_catcher`** | **10** | **+$44.40** |

## WFF HAND-TRACE (dollars, not R)

`2026-08-17 WFF kevseq 11:17:44 ET` — `chart_gate_blocked_trade`, reason `no_break_below_level`,
signal $5.039. SIP 10s tape (trades → 10s bars, conditions-filtered, pulled this turn):

- Fill $5.0894 (signal +1% slip) → **98 sh = $500.00** at risk. Stop $4.67 (the fire's 60s low).
- `15:17:50Z` (11:17:50 ET) **bank ½ at $5.5983** (+10% resting limit, exact).
- Run high **$6.38**.
- `15:18:30Z` **trail exit, close $5.27** (10% off the run high) → **+$32.58**.

The gate blocked it at 11:17:44 on a name that printed $6.38 within a minute.

## VERDICT

Built and rig-pinned as ordered. **The counterfactual is net negative and says so at the top.**
Owed: a full-day re-grade of the 8/17 rows tonight, a lane stamp on `chart_gate_blocked_trade`
and `extension_reject` rows (so this join stops being a heuristic), and Marcos's call on both
`LANE_REGISTRY_EXEMPT` and the `TAPE_PREBREAK_LANES` / `_MOMENTUM_TAPE_HOLDOUT` tensions.
