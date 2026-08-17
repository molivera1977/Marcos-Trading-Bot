# FORENSIC: "PRE-session 1-min staleness blackout" — Mon 8/17
**Verdict: PROVEN root cause for the roster-wide blackout — and it was NOT a PRE defect. It was the 09:30 BELL-BOUNDARY.**
Analysis + local prep only. Fix coded + rig-pinned, NOT deployed (2 positions open, RTH).

## Failure condition (written first)
**This fix is wrong if** tomorrow (or any day with RTH_HANDOFF_MIN=5 live) the read-list guard still
prints roster-wide `no fresh bars` skips in the 09:30–09:35 window for names with fresh SIP tape, OR
if any 09:30–09:35 entry/VWAP decision is shown to have been made on PRIOR-DAY bars (the hand-off
must widen which of TODAY's bars are visible, never admit yesterday — `_fresh_session`'s today+900s
standard is untouched and remains the arbiter). Also wrong if PRE-period (pre-09:30) skips of
genuinely-printing names recur — the evidence below says those did NOT happen today, so if they
appear, a second, different defect exists that this fix does not address.

## Root cause — the exact line
`marcos_trading_bot.py:1254` (pre-fix): `_live_sessions()` → `return ["PRE","RTH"] if is_premkt else None`
with `is_premkt = now_ET < "09:30"`.

At 09:30:00 sharp the session list flips to `None` = **RTH-only** — but the first RTH 1-min bar
(13:30 UTC) cannot exist until ~09:31+ (bar completion + SIP write). For roughly 09:30:00–09:32,
`_alpaca_intraday_bars` (`:1257`, session filter at `:1277-1283`) drops every one of today's PRE bars
— *seconds old, perfectly fresh* — and returns only **prior-day RTH bars**. `_fresh_session` (`:4284`)
correctly rejects those (date ≠ today) → `[]` → the read-list guard (`:3098-3107`) takes its
fail-CLOSED branch: `no fresh bars (last print stale)` — for the ENTIRE roster at once. The guard's
3-min probe cache (`:3086`, bucket = minute−minute%3, so 09:30–09:32 is one bucket) pins the False
verdict, and thin names need a few RTH prints before `count=6` (`MOMENTUM_BARS+3`, `:540`) yields a
fresh tail — stretching visible skips to ~09:35 and full recovery to ~09:36–09:41. Exactly the
observed self-clear.

Blast radius of the same boundary (all `_live_sessions()` call sites): read-list guard `:3090`,
scan-loop bar/full_bars refresh `:7555/:7559` (cache freezes at the open), velocity `:9299`,
`:12382`, `:12467`, and position monitors via `:10382` (`_entered_premkt or None`).

## Per-hypothesis evidence
- **A (Alpaca path failing on Railway → Webull stale fallback): DEAD.** Railway env verified this
  turn: `BARS_SOURCE=alpaca`, `ALPACA_KEY/SECRET` set; the BOT's own key (prefix PKC6…) queried
  recent SIP from this laptop at 09:52 ET → HTTP 200, WETO bars fresh to 13:48Z. EXEC HEALTH lines
  across the whole window (logs 12:55–13:45Z): `429=0 api_err=0 timeouts=0 fail_open=0` every cycle.
  No `alp_429`/`alp_rest_err` evidence anywhere. The Alpaca path was healthy; no Webull fallback was
  needed for it to fail — the session FILTER discarded the fresh bars.
- **B (thin-name PRE gaps, guard working as designed): CONFIRMED for the PRE period — not a defect.**
  Log census 11:00–12:55Z (~223 skips): SQFT×27, AKTX×27, IBG×21, PLUR×19, BCAB×17, BKYI×15… —
  and SIP shows SQFT/AKTX/IBG had **0/0/0** 1-min bars in the whole 11:00–13:30Z window. Those names
  genuinely never printed; `max_stale_secs=900` refused them correctly. **WETO/FIEE/DFSC appear in NO
  pre-09:30 skip.** Their SIP tape 11:00–13:30Z: 149/146/150 bars, max gap 120/120/60s — always fresh.
- **C (`_et_session_of_utc` DST/boundary bug): DEAD as a filter bug, ALIVE as the mechanism's tool.**
  The function (`:1194`) is tz-database-correct; rig pins exercise it on real timestamps. The defect
  is not mislabeling — it's that the RTH-only *request* is unanswerable at 09:30-09:32.
- **D (3-min cache + boundary): CONFIRMED as the amplifier.** One bad probe at 09:30:xx pins False
  for the whole (9:30–9:32) bucket; log windows show the skip burst 13:30–13:35Z (22 skips incl.
  WETO/FIEE/DFSC exactly once each) and **zero** skips from 13:35Z on.
- **E (stale_swap_refused 46 / stale_fire_suppressed 24 — common ancestor?): NO — three separate
  guards; only the boundary one is a defect.**
  - `stale_swap_refused` (`:8032/:8332` via `_swap_price_ok`): stream-quote vs 10s-fire-bar
    divergence. Rows run 04:28→09:47 with `why=tick_fresh/xsrc_divergence`. **It does not block the
    entry** — the trade proceeds on the stream price (only the price-swap is refused). Not 1-min, not
    a blackout.
  - `stale_fire_suppressed` (`:4904` via `_bucket_fresh` `:4882`, `CURL_FIRE_MAX_AGE_PRE=90` /
    `CURL_FIRE_MAX_AGE_SECS=240`): 10s fire-bucket age at CONSUMPTION. Rows show ages 92–400s while
    the alp-hot feed itself printed `last_bar_age=10-45s` — the gap is **scan-loop cycle latency**
    (decision bursts at 09:30:50, 09:32:15, 09:35:50, 09:37:41, 09:40:51 = 85–195s/cycle) plus
    "replay after restart/admission" replays of fires detected while a name was outside admission.
    The guard did its job on fires that WERE old by the time the loop got to them. This is a real,
    SEPARATE finding (loop capacity at the open), logged below as an open item — it is not the 1-min
    pipeline and the boundary fix does not claim it.

## Timeline (log + decisions-archive, all ET)
- 03:55 boot (dry_run=True, entry_open 07:00). 04:20 first `freshness_breach` (map-age canary, MYSZ).
- 04:28 first `stale_swap_refused` (MYSZ); 04:40 first `stale_fire_suppressed` (SLE, 150.7s).
- 07:00–09:25: read-list skips ONLY on zero-print names (SQFT/AKTX/IBG/PLUR/BCAB/BKYI…), ~10-30 per
  10-min window — correct refusals. Roster leaders traded/watched normally (WETO ma_pullback trigger
  09:26:33 + premarket_shadow_entry).
- **09:30:00 the flip.** 13:30–13:35Z window: 22 `no fresh bars` skips — WETO, FIEE, DFSC, MYSZ,
  SLE, IVF, IPST, TRUG, JLHL, XPON, WOK, UCL, STFS, PFSA, UPLD, YYAI, CRIS + thin stragglers = the
  "23/26" roster blackout.
- 09:35+ zero further skips. FIEE `entry_zone` 09:37:41 → `filled` 09:38:46; DFSC `triggered_ignition`
  09:40:51 → `filled` 09:41:01. Matches the reported 09:36–09:41 self-clear.

## Counterfactual dollar cost (bounded, honest)
The boundary blackout's direct provable cost is SMALL today. During 09:30–09:35 the trigger engines
still fired (flat_top triggers at 09:30:50; the read-list blackout's channel is the vision-reader
roster → map freshness → chart-gate/mapless effects, plus frozen 1-min cache refresh). The refused
conversions in the window were the `stale_fire_suppressed` set (separate guard, above). Marking each
suppressed fire to +10 min on today's SIP at the real sizing (~$400/slot, DFSC precedent 137sh@$2.90):
STFS +$119 (4.38→5.69, high 6.45), SVRE $0, SLE −$29, FGI −$67/−$64, JLHL −$16, WOK +$17, NIVF +$6
→ **net −$34 had ALL suppressed fires converted; the only real forgone winner was STFS ≈ +$119
(fire 09:26:51 PRE, consumed 324s late — the loop-latency finding, NOT the boundary defect).**
Traced trade (dollars law): STFS vwap_reclaim fire px $4.38, 91 shares = $398.58 notional; +10-min
close $5.69 → +$119.21 before exits/slippage; E3 trail would have kept most of a 30% move. The
boundary defect's own cost today ≈ $0 directly measurable — its cost is RISK: 5 dark minutes at the
open, roster-wide, every day, on the week we prove the machine. That is why it gets fixed anyway.

## The fix (coded locally, committed, NOT deployed)
`_live_sessions` (`:1247`): after the bell, keep `["PRE","RTH"]` for the first `RTH_HANDOFF_MIN`
minutes (default 5), then `None` (RTH-only) exactly as before. `_fresh_session`'s today+900s
staleness standard is unchanged — the hand-off widens WHICH of today's bars are visible, never HOW
stale. Explicit `is_premkt` argument path untouched (position-stamped calls unchanged).
**Kill switch: `RTH_HANDOFF_MIN=0`** restores the old hard flip.

## Rig
Section **"R) 8/17 bell-boundary hand-off"** in `rig/test_shipset_20260804.py`: frozen-clock exec of
the REAL `_live_sessions` segment (09:29 / 09:31 / 09:34 / 09:36 / 10:00 / kill-switch) + composed
pipeline pin (the real `_et_session_of_utc` + the exact `_alpaca_intraday_bars` filter loop +
`_fresh_session` over the 8/17 payload shape: fresh PRE bar + prior-day RTH bars). **Verified: rig
exits 1 on the pre-fix code (segment absent/09:31→None), exits 0 post-fix.** Judged by exit code.

## Open items (separate defects, NOT covered by this fix)
1. **Scan-loop cycle latency at the open (85–195s/cycle)** starves `CURL_FIRE_MAX_AGE_PRE=90` —
   fires structurally stale at consumption (STFS +$119 the priced example). Needs its own diagnosis
   (per-cycle timing instrumentation) before any limit change — do NOT just widen the age caps.
2. Fire **replay-after-admission** replays consume setups already stale; consider stamping replayed
   fires distinctly so suppression stats separate "loop was slow" from "replay was late".

Officers touched: Systems Quant (root cause), Feed Engineer (vendor exoneration), First Hour (open
window cost), Blast Radius Auditor (call-site enumeration), Statistician (dollar trace), Execution
Surgeon (loop-latency open item). Clean: Webull Broker Desk, Kev Librarian.
