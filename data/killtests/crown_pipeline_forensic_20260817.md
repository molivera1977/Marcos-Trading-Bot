# CROWN PIPELINE FORENSIC — WETO 8/17 ("leader_armed 09:47 but no crown row all day")

**Verdict: the crown pipeline WORKED, essentially optimally. The premise is a naming illusion:
`leader_armed` IS the crown row — there has never been any other. WETO was crowned 09:47:07,
77 seconds after the first tradeable print that satisfied the 8/5 spec, and every eyes stamp
from 10:05 on carries `crown: True`.** The proven defect is OBSERVABILITY: the promotion event's
only row reads as "armed" (pre-crown), so auditors — including today's report — search for a
crown row and conclude the crown never happened. Fixed observe-only (CROWN_FIX_0817).

## Code anatomy (why leader_armed = crowned)
- `_leader_qualify` (:5003): `rec["since"] is None and rec["gain"] and rec["viol"]` → sets
  `rec["since"]` = the crown itself → logs **`leader_armed`**. There is NO later promotion step,
  NO other row type. `_is_leader` (:5248) returns `bool(rec["since"])` — the same field.
- Inputs: `_leader_gain` (:5013, gain ≥ LEADER_GAIN_MIN=40, sticky) fed by `_leader_high_probe`
  (:5036) off `_pdc_map` (prior close, loaded at daily preload :7560) on EVERY `_curl_feed` read
  (:1165); `_leader_violence` (:5024) fed by halt_suspect detection (:1176); fresh_highs viol from
  ≥3 fresh-high minutes in a rolling 10 (:5057). Rehydrate replays `leader_armed` rows (:5264).
- Suspects from the tasking, each DEAD:
  - "armed→crown promotion never wired for fresh_highs" — DEAD: there is no armed→crown
    conversion to wire; qualify = crown, and it fired.
  - "crown conversion requiring a condition the halted tape never satisfied" — DEAD: nothing
    beyond gain+viol is required; the halt DELAYED gain-proof (no prints = no gain reading),
    which is correct behavior, not a defect.
  - "day-gain off a wrong prior_close" — DEAD as a crown-blocker (crown used pdc 8.22 and fired);
    ALIVE as a data inconsistency, flagged below.

## WETO timeline (archive rows + SIP 10s tape, all ET)
- 03:55:13 `daily_loaded` → `_pdc_map["WETO"] = 8.22` (verified: 04:06 row dg 21.05 @ px 9.95
  ⇒ pdc 9.95/1.2105 = 8.22).
- Premarket→open: dg 19–25% — gain arm FALSE (< 40). Fresh-high marks accumulate; viol =
  "fresh_highs" armed from the tape's climb (rows 04:06→09:08 show steady highs).
- 09:33–09:35:40: $10.05 → $11.46 (SIP closes). **+39.4% at the last pre-halt print — 0.6 points
  under the 40 line when the tape went dark.**
- 09:35:40–09:45:50: LULD halt (zero prints, 610s gap in SIP 10s bars).
- 09:40:50 `halt_suspect` (gap 300.5s) → `_leader_violence("halt")` fired mid-halt; still no
  crown — CORRECT: gain unprovable at +39.4%, no tape.
- 09:45:50: resumption print $13.05 = **+58.8% — the FIRST bar that satisfies gain ≥ 40%.**
- **09:47:07 `leader_armed` why=fresh_highs = THE CROWN** — 77s after first possible = one
  scan-loop cycle (the open-window cycle latency is a separate known open item, 8/17 forensic).
- 10:05:49 / 10:11:24 `hidden_observe_only` + 10:18:36 `kevseq_shadow_fire`: eyes `crown: True`
  — `_is_leader` live and TRUE at decision time. (Hidden fires observed-only by the 8/14
  suspension = by design; kevseq conversion died to momentum_reject = batch2 item A.)
- Post-crown halt_suspects (09:51/10:21/10:26/10:32, gaps 141–164s) are thin-tape suspects, not
  the 610s real halt; halt-lane arm rows require prox/vel thresholds at read time — no defect
  provable there today.

## The fix (minimal, observe-only, per auditor-cannot-authorize-behavior)
`_leader_qualify` now ALSO logs an explicit **`crowned`** row (why + since) alongside
`leader_armed` when `CROWN_FIX_0817=1` (default). No behavior touched: `_is_leader`,
rehydrate, every privilege gate unchanged; the status is written once and never read back
(rig-pinned). Kill: `CROWN_FIX_0817=0` restores byte-identical rows.

## Rig
Section **AM**: real shipped source exec'd under a frozen clock reproducing WETO's exact
sequence — pre-halt probes (viol=fresh_highs, gain false, no crown), halt violence at +39.4%
(still no crown), first post-halt probe +58.8% → crown, since=09:47; `crowned` row present
post-fix, ABSENT with CROWN_FIX_0817=0; observe-only pin. Judged by exit code.

## Flags for Marcos (unresolved, no code)
1. **Two day-gain sources disagree**: 10:18:36 kevseq row `day_gain 137.17` (pdc ≈ 7.78) vs
   eyes `dg 124.45` (pdc 8.22) — the kevseq path (:7979 area) computes its own pdc fallback.
   No crown impact today (both ≥ 40) but the 8/14 split-adjustment class says pin ONE source.
2. **Crown latency during halts is structural**: a name that crosses 40% INSIDE a halt cannot
   crown until resumption print + one scan cycle. If Marcos wants halt-time crowning (e.g.
   indicative-price or arm-at-39%+halt), that is a BEHAVIOR change — priced separately, his call.
3. Scan-loop cycle latency at the open (85–195s) bounds crown latency too — already an open
   item from the 8/17 bell-boundary forensic; not re-opened here.

Officers: Crown Steward (privilege-delivery audit — delivered), Systems Quant (qualify = crown
proof), Historian (timeline of record), Statistician (pdc arithmetic), Side Marshal (halt tape
read), Blast Radius Auditor (single write site, no readers). Clean: Webull Broker Desk,
Kev Librarian, Feed Engineer (SIP tape healthy through the halt window).
