# CROWN-ON-HALT KILL-TEST — 2026-08-17

**Hypothesis (pre-registered):** an upward LULD halt with day-gain already >=35% should crown the name IMMEDIATELY (mid-halt) instead of waiting for the first resumption print to cross 40%, so the machine reopens already wearing crown privileges (60s reads, ignition cap x3, curl slots x3, hidden uncapped, freshness contract coverage). Specimen: WETO 8/17, halted at +39.4% ($11.46), crowned 09:47:07 on the resumption leg.

**FAILURE CONDITION (written first):** crown-on-halt is wrong if (a) names halting up in the 35-40% band frequently reopen WEAK (sticky crown wastes privileges on faders), or (b) early crowning would have changed nothing material (privileges never bind in the halt→resume window).

**VERDICT: UNDERPOWERED (band N=1) — and on the one specimen, NO-BIND ($0 counterfactual).**

---

## Method

- **Halt detection:** era (6/29-8/17, 38 sessions) universe 10s cache (`data/universe/bars10s`, 730 name-days = the day's runners). RTH bar gap >= 250s AND active tape both sides (pre-halt 2-min volume >= 20k shares, >= 15 bars in the prior 5 min) — the LULD signature, filtering thin-tape feed gaps (raw gap events 1,492 → strict halts 436). Cross-checked against `halt_suspect` archive rows (WETO 8/17 has 5).
- **Upward:** rising into the halt (last pre-halt close > close ~2 min earlier) and day-gain at halt > 5%.
- **Prior-close source (stated honestly):** derived from the bot's own archive rows — every row carrying both `day_gain` and `price` implies prev_close = price/(1+gain); per name-day I take the median implied value. CAVEAT: this inherits the bot's daily-source split-adjustment defect (marcos_trading_bot.py:1318 comment; DFNS shows +13,112% "day gain" = split-corrupted prior close). But the crown gate consults exactly this number, so band membership is measured in the units the gate actually uses — the right units for this counterfactual. Split-corrupted names all land far above 40% and never contaminate the 30-40 band.
- **Decisions archive:** GET /api/decisions_archive for all 38 era sessions (7/3 holiday empty), cached; refusal rows scanned per cohort name in halt→resume+10min.

## Cohort: upward halts, day-gain at halt in [30%, 40%)

**N = 1.** In 38 sessions of era tape, exactly one upward halt occurred inside the band where crown-on-halt changes the outcome — WETO, today.

| date | sym | halt (ET) | halt px | gain@halt | resume px | re-open | +5min | +15min | +30min |
|---|---|---|---|---|---|---|---|---|---|
| 8/17 | WETO | 09:35:40 | 11.46 | +39.4% | 13.14 | **+14.7%** | 14.88 (+29.8%) | 15.84 (+38.2%) | 18.05 (+57.5%) |

(One other near-band event era-wide: PN 8/6 at +22.8% reopened −0.5% — below-band, listed for context only.)

## WETO 8/17 hand-trace (10s tape + archive rows)

- 09:35:40 last pre-halt print $11.46; implied prev_close $8.22 → **+39.4% at halt** (matches the specimen claim). Rising into halt; 2-min pre-halt volume 278,793 sh. Gap 610s.
- 09:35:49 (9s into the halt): `ignition_below_convert` — volx 2.2 < need 4.5, price 11.46.
- 09:40:50 `diprip_armed` level 9.5 (mid-halt).
- 09:45:50 resumption $13.05/$13.14 (**+14.7% above halt price**).
- 09:46:23 `lens_focus` (dist 14.6%, zone confirm 10.0).
- 09:47:07 `leader_armed` why=fresh_highs — **the actual crown**, one cycle after the resumption print crossed 40%.
- 09:47:40-50: first 10s bar where the halt-ladder arm conditions (prox >= 0.7 of the 10% band AND vel1m >= 5%) are met ($14.60, prox 0.92, vel 15.7) — **33-43 seconds AFTER the actual crown**.
- 09:50:15 `kevseq_reject` at $13.43 (W after B, blue-sky) — sequence gate, no crown bypass.
- Path: +5min $14.88, +15min $15.84, +30min $18.05.

## Would early privileges have bound? (the counterfactual, priced)

Every WETO archive row in 09:35:40–09:55:50 was scanned (11 rows): watching x3, halt_suspect x2, ignition_below_convert, diprip_armed, lens_focus, leader_armed, lens_unfocus, kevseq_reject.

- `ignition_below_convert` (09:35:49): IGNITION_CONVERT_MULT is a volume-multiple gate (marcos_trading_bot.py:8433) with **no crown bypass** — crown privileges are the ignition COUNT cap (:8073/:8405 `ignition_n < LEADER_IGNITION_CAP`), not the convert threshold. Crown-on-halt does not flip this refusal.
- Halt-ladder lane (:8259) IS crowns-only (`HALT_LANE and _is_leader(t)`) — the one structural privilege genuinely OFF during the halt and the first 77s post-resumption. Simulated per the code's own arm math on the 10s tape: prox/vel first satisfy the arm at **09:47:40**, after the 09:47:07 crown. The crowns-only gate cost zero armed fires today.
- No `freshness_breach`, `stale_fire_suppressed`, slot/cap refusals, or hidden-cap refusals on WETO in the window. Lens focus arrived 09:46:23 uncrowned anyway.
- **Priced counterfactual: 0 refused fires flipped, $0.**
- [OBSERVATION, flagged not fixed] despite arm conditions being met on the 10s tape 09:47:40+ (crowned by then), the archive shows ZERO `halt_arm`/`halt_early_arm` rows for WETO on 8/17 (vs 3 halt_arm rows 8/14). The live detector runs on the 5s feed (HALT_ARM_5S) with cooldowns; possible lane silence worth a Halt-Lane-officer look — outside this kill-test's scope.

## Base rate: ALL era upward halts (doctrine context)

Strict upward halts N = **63** (17 names). Reopen HIGHER than halt price: **42/63 = 66.7%**; median first-print move **+1.8%**. By band: >=40% gain-at-halt N=55, 35 higher (63.6%), median +1.8%; the tail is fat both ways (WETO 8/14 +13.5%, HUIZ 8/7 +22.4% vs XHG 8/13 −17.0%, DFSC 8/13 −10.4%). Upward halts reopening higher two times out of three supports the halt doctrine generally, but the 30-40 band itself has one observation — halts in that exact band are rare because names that fast usually blow through 40% before the tape can halt them.

Full per-name upward-halt trace table: `data/killtests/crown_on_halt_20260817_traces.json`.

## Verdict

**UNDERPOWERED, leaning NO-BIND.** N=1 in the band. The failure condition's "reopens weak" arm is NOT triggered (the one specimen reopened +14.7% and ran +57% in 30 min — sticky crown would have been earned honestly), but the "changed nothing material" arm IS: the actual crown pipeline landed 09:47:07 and the first privilege-bound moment (halt-ladder arm) came 09:47:40 — crown-on-halt would have moved the crown up ~12 min and changed zero fires and $0. No refused row in the window flips under crown. Recommendation: do NOT ship crown-on-halt on this evidence; log the 35-40 upward-halt pattern as a standing observation and re-run when the band has N>=5. (Auditor-cannot-authorize: any future ship of crown-on-halt is a behavior change and goes to Marcos priced.)

Officers touched: Crown Steward (crown latency — 12 min, cost $0 today), Side Marshal (clean), Halt Lane (the 8/17 arm-silence observation), Statistician (base rate ledgered here), Historian (WETO 8/17 trace), Blast Radius (no ship — analysis only).
