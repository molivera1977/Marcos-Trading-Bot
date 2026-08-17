covers: 4cc24ea99420
# BLAST RADIUS CONVENING — 8/17 BATCH 3 (manual close-position control + lane classification registry)
Auditor: Blast Radius Auditor (separate context, urgent convening under a held deploy window).
Tree audited: 4cc24ea (tip) = e6f8bb3 (item C, manual close) + 4cc24ea (lane registry).
Prior tip 5d58e42 was audited GREEN in the batch-2 convening (4ace952); that verdict is
unchanged and is not re-litigated here. Scope: PENDING_CONVENE_20260817.md batch-3 items.
Context read this turn: `data/killtests/manual_close_20260817.md`,
`data/killtests/lane_registry_20260817.md`, `git show` of both commits, and the shipped source
in context. Working tree clean at audit time (`git status --porcelain` empty).

Full rig EXECUTED this convening with `SHIP_CHECK=1`: **548 green, one RED — section Q only**
(`HEAD 4cc24ea99420 not covered by data/audits/LATEST.md`), which is the designed interlock
firing because this artifact did not yet exist. Sections **AN (21 checks) and AO (30 checks)
are both present AND executed**, all green, in the same run. Post-commit rerun appended at the
bottom.

## VERDICT: GREEN — no blocker. Deploy may proceed on Marcos's word.

The book-flat rule, the no-RTH-push law, and auditor-cannot-authorize still govern the ship
itself. Two items go to Marcos BEFORE the env is set, not to an auditor:
**(1) `LANE_REGISTRY_EXEMPT` — the counterfactual is NET NEGATIVE (−$64.25/N=13)** and the
kill-test says so at the top; **(2) the extension-gate half of the change is UNMEASURED (N=0)**
— see F-1. Neither is a code defect. Both are his call.

---

## 1. LANE-REGISTRY BEHAVIOR EQUIVALENCE FOR PRE-EXISTING LANES — **VERIFIED, no delta**

Checked by reading the derivation in source (`marcos_trading_bot.py:410-465`) and hand-computing
each derived set against the legacy literal pinned at `:429-437`, then confirming the rig pins it
with literals (AO: "chart-gate bypass is a SUPERSET of the old tuple", "extension exempt is a
SUPERSET", "no CHART lane newly bypasses", "check_momentum behavior UNCHANGED", plus four
KILL-SWITCH pins in the reverse direction).

| set | legacy literal | derived (`LANE_REGISTRY_EXEMPT=1`) | pre-existing lanes |
|---|---|---|---|
| `_chart_break_gate._bypass` (`:3453`) | `hidden_entry, vwap_reclaim, zone_flip` (+`ignition` iff env) | `TAPE_LANES` (+`ignition` iff env) | all 3 retained, ⊃ superset — **no loss** |
| extension exempt (`:9182`) | `rocket_catcher, hidden_entry, flat_top, orb, ma_pullback, vwap_reclaim, zone_flip` | `TAPE_LANES ∪ {flat_top, orb, ma_pullback}` | all 7 retained (`rocket_catcher/hidden_entry/vwap_reclaim/zone_flip` ∈ TAPE; the 3 chart lanes via `_EXT_SLOW_RETEST_EXEMPT`) — **no loss** |
| `_STALE_EXEMPT` (`:3443`) | `rocket_catcher, vwap_reclaim, zone_flip, hidden_entry` | `TAPE_LANES` | all 4 retained — **no loss**; observe-only branch |
| `check_momentum` exempt (`:12839`) | inline 8-tuple | `_MOMENTUM_LEGACY_EXEMPT` const, **same 8 names, same order** | identical — **membership unchanged** |
| `TAPE_SCALAR_EXEMPT_LANES` (`:5215`) | env default `kevseq,v2conv,grinder,bandpass,prevwap` | LITERAL kept, rig-AO-pinned `== _momentum_exempt_lanes() − _MOMENTUM_LEGACY_EXEMPT` | identical |
| `VRIDE_EXEMPT` (`:492`), `BREAKSIDE_LANES` (`:7318`), `BACKSIDE_EXEMPT` (`:7242`), `MIN_STOP_EXEMPT` (`:7522`), `TAPE_PREBREAK_LANES` (`:7332`), `CHART_CEILING_LANES` (`:7337`), `PRE_LANES` (`:13295`), `RETEST_LANES` (`:5097`), `DAYGAIN_LEGACY` (`:6575`), vel5 tuple (`:9122`) | — | **UNTOUCHED by this commit** (verified in the diff: none of these lines appear) | unchanged |

I independently re-derived the AO equality claim rather than trusting it:
`_momentum_exempt_lanes() − _MOMENTUM_LEGACY_EXEMPT` = `(LEGACY ∪ (TAPE − HOLDOUT)) − LEGACY`
= `TAPE − {rocket_catcher, crown_seam, halt_ladder} − {hidden_entry, vwap_reclaim, zone_flip}`
= `{kevseq, v2conv, grinder, bandpass, prevwap}` = the `:5215` literal exactly. ✔

**No unintended behavior delta for any pre-existing lane. Not RED.**

### On the amended pins (the self-green-washing question the build asked us to answer)
`AF-l` / `AG-x` / `AH-x` previously asserted `bandpass` / `kevseq` / `v2conv` were **absent** from
`_STALE_EXEMPT`. Those assertions pinned the DEFECT as if it were the spec — they encoded a
copy-paste omission, never a decision, and `_STALE_EXEMPT` gates an observe-only stamp with no
money path (the hard skip was refuted 7/21). Rewriting them to pin the *tradeability* and *side*
sets (`MIN_STOP_EXEMPT`, `BACKSIDE_EXEMPT`, `VRIDE_EXEMPT`) — which are unchanged and are the
sets doctrine says must keep binding — is **legitimate**, not green-washing. The rewrite is
also net-stronger: AO adds explicit reverse-direction kill-switch pins the old ones lacked.

## 2. THE INTENDED DELTAS — EXACT ENUMERATION

With `LANE_REGISTRY_EXEMPT=1` (default). Nothing else changes; no lane loses an exemption; no
chart lane gains one; `ignition` unchanged; `check_momentum` unchanged.

**(a) Chart-break gate — 8 lanes newly bypass** (`_cg_verdict` forced to `allow/live_structure`):
`kevseq`, `v2conv`, `grinder`, `bandpass`, `prevwap`, `crown_seam`, `halt_ladder`,
`rocket_catcher` *(inert — `ROCKET_CATCHER=0` since 7/24)*. Effectively **7 live lanes.**

**(b) Extension guard (25% over EMA90) — 7 lanes newly exempt**: `kevseq`, `v2conv`, `grinder`,
`bandpass`, `prevwap`, `crown_seam`, `halt_ladder`. *(`rocket_catcher` was ALREADY in
`_LEGACY_EXT_EXEMPT` — it is not a delta here.)*

**(c) `_STALE_EXEMPT` — the same 7 newly skip the `read_exhausted_observed` STAMP.**
Observe-only branch, **no money.**

> **F-3 (doc accuracy, YELLOW):** `lane_registry_20260817.md` states "the same eight lanes" for
> both (b) and (c). It is **seven** in each — `rocket_catcher` was already exempt in the legacy
> extension and stale tuples. The CODE is correct; the doc's delta count is off by one in two
> places. No behavior consequence; fix the doc.

**Kill switch — `LANE_REGISTRY_EXEMPT=0` restores the old tuples exactly.** Verified in source:
each helper returns `frozenset(_LEGACY_*)` on the false branch, and `_STALE_EXEMPT` falls back
to `frozenset(_LEGACY_STALE_EXEMPT)`. The containers change from `tuple` to `frozenset` but every
use is an `in` membership test — semantics identical. Rig AO pins all four directions including
"kevseq is GATED again with the registry off". ✔
**Stated so nobody assumes otherwise:** `LANE_REGISTRY_EXEMPT=0` does **NOT** revert batch-2's
scalar exemption — that is a separate switch (`TAPE_LANE_SCALAR_EXEMPT`), by design. Two switches.

## 3. IGNITION SEMANTICS — **PRESERVED, verified**

Old: `("hidden_entry","vwap_reclaim","zone_flip") + (("ignition",) if IGNITION_CHART_BYPASS else ())`.
New (`:446-451`): `TAPE_LANES | (frozenset(("ignition",)) if IGNITION_CHART_BYPASS else frozenset())`.
`ignition` is classed `"hybrid"`, so it is in **neither** `TAPE_LANES` nor `CHART_LANES` — its ONLY
route into the bypass is the same env conditional as before. Membership is identical in both env
states. `IGNITION_CHART_BYPASS` is defined at `:527`, *after* the helper at `:446`, but it is
resolved as a module global at CALL time, not definition time — no NameError, no ordering hazard
(and the rig executes `_chart_break_gate` for real, which would have caught it). Extension guard:
`ignition` was not in `_LEGACY_EXT_EXEMPT` and is not in the derived set — still bound. ✔

## 4. MANUAL CLOSE — all seven pre-written failure conditions ADDRESSED

Audited in a separate context against the shipped source; every item PASSES with cited evidence.

- **Fail-CLOSED** (`:5281-5288`): one `except Exception` covering fetch *and* parse sets
  `_mclose_cache["pending"] = []`. Timeout=3s, 401/non-200, malformed JSON, non-dict body all
  land there; the cache is **overwritten**, never replayed. Rig proves it against an unreachable
  host. ✔
- **Stale guard**: both sides stamp the *same* naive `"%Y-%m-%dT%H:%M:%S"` UTC string
  (`screener_app.py:2263`, `marcos_trading_bot.py:10301`); the match does a lexicographic
  `at <= entry_ts → continue` on `[:19]`. **No datetime object is constructed anywhere**, so the
  naive/aware mismatch class cannot occur. Untimestamped request → ignored. Server TTL 600s,
  pruned on every read. A stale request reaching a LATER position in the same name is blocked
  **twice**. ✔
- **Idempotency**: `_mclose_fired = True` at `:10469`, **before** `_safety_close` at `:10477`,
  then `break` at `:10481`. Ack failure is post-sell and cannot re-enter. Per-monitor, not
  global. ✔
- **No parallel exit path**: exactly one exit call, `_safety_close` — the #53 choke point
  (`_cancel_sell_ladder` → `cancel_order(stop)` → `close_position`). No `close_position(` /
  `_place_order(` / `cancel_order(` in the block; the `break` falls into the normal record path
  ending at `_clear_open_trade(ticker, trade_id=trade_id)` — trade_id-keyed, per the 8/11 ghost
  fix. New `_exit_layer` bucket `"manual"` keeps operator exits out of stop/eod statistics. ✔
- **`MANUAL_CLOSE=0`**: short-circuits in two places (`:5275`, `:10466`) — no poll, no close.
  Import-time read, so it needs a restart, not a code change. ✔
- **Auth**: `POST` 401s via `_endpoint_authed()` **before** any mutation or JSON parse
  (`screener_app.py:2242-2244`); `GET` is read-only. ✔
- **Merge-only**: `_pending_closes[key] = rec` — one key touched; removal only via explicit clear
  or expiry. Two names queue simultaneously (rig-proven). 7/24 wipe law honored. ✔
- **Call-site placement**: inside `monitor_trade`'s `while True:` after the 15:45 flatten and
  **before** `stream.get_price()`, so it still fires during a quote-dead stretch. `monitor_trade`
  is only invoked after the entry fills and the durable row is saved — it cannot run pre-fill. ✔

## 5. INTERACTION BETWEEN THE TWO COMMITS — no merge damage

Disjoint regions of `marcos_trading_bot.py` (e6f8bb3: `:5266-5310`, `:9937`, `:10409`,
`:10466-10481`; 4cc24ea: `:367-465`, `:3443/3453`, `:9182`, `:12839`) and disjoint rig sections.
Neither reverts the other. **AN and AO both present and both executed in the same green run**
(21 + 30 per-check lines observed). `screener_app.py` untouched by 4cc24ea. Y-b funnel count
16 → 17 held. Judged by EXIT CODE, not pattern-matching.

## 6. DOCTRINE-INVERSION SWEEP — the registry ENFORCES the settled rulings

The 7/24 live-structure ruling ("switch the reclaim and zone flip") and the 7/26 tape-lane
doctrine ("no absolute never-trade — let the chart and tape decide"; every setup-quality scalar
REFUTED) are **enforced, not inverted**, by this change. The 8/12 our-numbers primacy and the
8/5 back-side ruling are untouched (`BACKSIDE_EXEMPT` unchanged — the back-side gate still binds
tape lanes, as settled).

Full source sweep for lane-name tuples the registry did NOT absorb. **None contradicts settled
doctrine; all are findings, not blockers:**

| # | site | line | status |
|---|---|---|---|
| S-1 | `TAPE_PREBREAK_LANES` | 7332 | **OPEN HOLE, mirror-image** — gates only `hidden_entry/vwap_reclaim/zone_flip`, so the 7 new tape lanes ESCAPE the 8/3 dead-zone block. Closing it REMOVES money → correctly left to Marcos. |
| S-2 | `_MOMENTUM_TAPE_HOLDOUT` (`rocket_catcher`, `crown_seam`, `halt_ladder`) | 444 | Named, documented spec tension; keeps `check_momentum` byte-identical. Doctrine says they should be exempt — Marcos's call. |
| S-3 | `BREAKOUT_ENTRIES` enable tuple | 9034 | `("ma_pullback","vwap_reclaim","ignition","zone_flip","rocket_catcher","hidden_entry")` — would drop all 7 new tape lanes if `BREAKOUT_ENTRIES` were false. **Currently INERT**: `BREAKOUT_ENTRIES = True` hardcoded at `:356` (not env-driven). Informational. |
| S-4 | vel5 floor tuple | 9122 | Chart-only inclusion list; deriving `CHART_LANES` would newly gate `dip_rip`/`bounce` (more restrictive). Correctly untouched. |
| S-5 | `DAYGAIN_LEGACY` | 6575 | Chart + ignition; deriving changes membership. Correctly untouched. |
| S-6 | `CHART_CEILING_LANES`, `BREAKSIDE_LANES`, `PRE_LANES`, `RETEST_LANES`, `MIN_STOP_EXEMPT`, `BACKSIDE_EXEMPT`, `VRIDE_EXEMPT` | various | Inclusion lists or tradeability/side floors doctrine keeps binding. Correctly untouched. |
| S-7 | `entry_type or "flat_top"` defaults | 2844, 2999, 3012, 10249, 12358 | Default-argument fallbacks, not exemption sets. No lane-class implication. |

The build's own enumeration (16 items) is accurate; this sweep found no tuple it missed.

## FINDINGS

**F-1 (YELLOW — the one Marcos should hear before setting the env).** *The extension-gate half of
this change is entirely UNMEASURED, and the kill-test's stated reason for that is wrong.* The
doc explains the zero `extension_reject` rows as "these lanes die at the chart gate before the
extension guard." **Call order is the opposite**: the extension filter runs at `:9182` inside
`wait_for_flat_top_entry`, on the `breakouts` list *before* it is returned; `_chart_break_gate`
runs later at `:12376` inside `_trade_worker`. The extension guard is UPSTREAM. So N=0 is not
explained by the chart gate — the true reason is unestablished (most likely these lanes simply
never printed >25% over EMA90 in the era, or `EXTENSION_MAX_PCT < 9` gated the block). Net: the
−$64.25 counterfactual covers **only** delta (a); delta (b) ships on doctrine with **zero**
measured evidence in either direction. Not a code defect. Worth a line in tonight's re-grade.

**F-2 (YELLOW — operational trap, manual close).** `_entry_ts_utc` is stamped
`datetime.now(timezone.utc)` **unconditionally** at `:10301`, and the `resume_state` rehydrate at
`:10306+` does **not** restore it. After a painless restart, a close request posted *before* the
restart is silently ignored — its `at_utc` now pre-dates the "entry." **Fails in the safe
direction** (a missed close, never a wrong one), but the operator gets no signal: the button
appears to work and nothing happens until the 10-minute expiry. Recommend a `close_ignored_stale`
observe-only row so the failure is visible. Observe-only → auditor-safe to propose, still Marcos's
to schedule.

**F-3 (YELLOW — doc accuracy).** Delta counts: seven, not eight, for the extension and stale sets.
See §2.

**F-4 (YELLOW — mitigating, favorable).** The kill-test calls its lane attribution "a ±20s ticker
join" because `chart_gate_blocked_trade` carries no lane. True — **but the immediately preceding
`chart_gate_<verdict>` row at `:12377-12380` DOES carry `entry_type`**, same ticker, same instant.
The join is therefore far better grounded than the doc claims for the chart-gate cohort (it
remains a genuine gap for `extension_reject`). This *strengthens* the −$64.25 number rather than
weakening it — it should not be discounted as heuristic. Adding the stamp is still worth doing.

**F-5 (YELLOW — concurrency, manual close).** `_mclose_cache` is unlocked and `["t"] = now` is set
*before* the 3s HTTP call, so a second monitor thread entering mid-flight reads the previous
poll's list. Benign — the value is ≤5s old and both the entry_ts and TTL guards still apply — but
"the cache is cleared on failure" holds only for the thread that observes the failure; a
concurrent thread can act on a success for up to 3s after the dashboard goes away.

**F-6 (YELLOW — unstated dependency).** The stale guard compares timestamps stamped by **two
different Railway processes**. Cross-process clock skew widens or narrows the guard window; only
the 600s TTL bounds it. Belongs in the doc's "Known limits."

**F-7 (YELLOW — auth surface).** The Close button sends the dashboard secret in `?key=` (pre-existing
`_endpoint_authed` pattern, not introduced here), so the secret lands in access logs and referrers
on a now money-capable endpoint. Already flagged as a spec tension in the scope doc; noted here so
it reaches the ledger.

**F-8 (informational).** `_momentum_exempt_lanes()` is called **only by the rig** — the live
momentum path still reads the `:12839` literal and the `:5215` env literal. The "single source of
truth" for momentum is a rig-enforced equality pin, not a code-path derivation. This is stated
honestly in the doc and is the correct trade (rig AL exec-evals that block in an isolated
namespace); recorded so no one later assumes the registry governs momentum at runtime.

**No RED. No blocker.**

---

## MONEY STATEMENT

### What can happen now that could not before

**A. `kevseq` (and 6 other tape lanes) can enter on chart-gate-blocked and unmapped names.**
The bypass returns `allow/live_structure` — which means these lanes now escape **every**
non-allow verdict, not just `no_break_below_level`: also `no_marked_level` (no read at all),
`read_exhausted`, and `gate_error`. On an unmapped intraday runner, a kevseq fire that previously
returned before sizing now proceeds to a ticket. Sized at `min(balance × MAX_POSITION_SIZE,
MAX_TRADE_DOLLARS)`.
*Priced:* the era 7/13+ counterfactual on the newly-exempt cohort is **−$64.25 over N=13,
−$4.94/trade, 31% win** (E3 live-parity, $500). Excluding `rocket_catcher` (cannot fire):
**+$44.40 / N=10**. `kevseq` alone **+$32.58 / N=1** (WFF, hand-traced below). `halt_ladder`
**+$93.93 / N=3**; `grinder` **−$64.91 / N=4** is the worst contributor that can actually fire.
The 8/17 rows are truncated at 11:34 ET and owe a same-night full-day re-grade.

**B. The same 7 lanes can enter while >25% over the 90-EMA.** Unmeasured — see F-1.

**C. An operator can close any single open position from the dashboard**, at any point the
monitor thread is alive, at market, through the same choke point the stop uses. Worst case is a
deliberate operator exit at an unfavorable price; there is no autonomous path to it — the bot
never originates a close request.

### What still bounds a bad outcome (verified in the shipped source this convening)

- **The stop is unchanged.** Every one of these lanes still gets its structural stop, the
  `STOP_MAX_PCT` clamp, the `stop >= entry` unsizeable-skip, the resting stop order, and the
  intrabar stop. Nothing in either commit touches the stop path.
- **Tradeability floors still bind all 7 lanes**: `MIN_STOP_EXEMPT` unchanged (min stop width
  still applies), `MAX_STOP_DIST_PCT` wide-stop reject, liquidity floor, ambient floor,
  topping-tail — all outside this diff.
- **The back-side gate still binds them** (`BACKSIDE_EXEMPT = {"dip_rip"}`, settled 8/5).
- **Their own lane conditions are untouched** — a kevseq fire still requires the full 8/16 Kev
  sequence; no detector threshold moved.
- **Capital is unchanged**: slot economy, `MAX_TRADE_DOLLARS`, position cap, slot refund on
  reject — all outside this diff.
- **Manual close** cannot fire without an authed POST, cannot double-sell (`_mclose_fired` before
  the sell), cannot fire on an unreachable dashboard (fail-CLOSED), cannot reach a later position
  in the same name (two independent guards), and cannot bypass the choke point.
- **Both changes are env-revertible with no deploy**: `LANE_REGISTRY_EXEMPT=0`, `MANUAL_CLOSE=0`.
- **Every newly-granted bypass logs `lane_exempt_applied(lane, gate, price)`** — Friday grades
  the real rows against the `chart_gate_blocked_trade` cohort they replace.

---

## DAY-ONE TRACES

### Trace A — a WFF-class `kevseq` fire that the chart gate would have blocked
1. Scan loop appends `(WFF, 5.039, b_level, "kevseq", {...})` to `breakouts` (`:8197`).
2. **Extension guard** `:9182`: `"kevseq" ∈ _ext_exempt_lanes()` → kept. If EMA90 data made it
   actually extended >25%, `lane_exempt_applied(lane=kevseq, gate=extension, ext_pct=…)` is
   logged. *(Previously: `extension_reject`, trade dead here.)*
3. Back-side gate `:9165`: `kevseq ∉ BREAKSIDE_LANES` → not evaluated (unchanged).
4. `_trade_worker(WFF, 5.039, …, entry_type="kevseq")`.
5. **Chart gate** `:12376` → `_chart_break_gate` `:3453`: `"kevseq" ∈ _chart_bypass_lanes()` →
   `lane_exempt_applied(lane=kevseq, gate=chart_break, price=5.039)` logged →
   returns `("allow","live_structure", break_level_as_evidence, "none")`.
   *(Previously: `("block","no_break_below_level")` → `chart_gate_blocked_trade` →
   `_slot_refund` → `return`. That is exactly what killed WFF at 11:17:44.)*
6. `_cg_verdict == "allow"` → **no** `chart_gate_blocked_trade`, no slot refund, no early return.
7. EMA90 stamp (data-only) → sizing `min(balance × MAX_POSITION_SIZE, MAX_TRADE_DOLLARS)`.
8. Stop from `extra` → wide-stop gate → `STOP_MAX_PCT` clamp → `stop >= entry` check →
   **min-stop-width gate still applies** (kevseq is NOT in `MIN_STOP_EXEMPT`).
9. Fill → `_save_open_trade_sync` → watchdog register → `monitor_trade`.
10. E3 management unchanged: resting bank ½ at +10%, trail 10% off run-high, intrabar stop first.
    Hand-trace in the kill-test: fill $5.0894, 98 sh = $500 at risk, stop $4.67, bank ½ at
    $5.5983 at 11:17:50, run high $6.38, trail exit $5.27 → **+$32.58**.
11. `_shadow_keep.add(WFF)` at `:13085` — the 10s anatomy persists for tonight's grade.

### Trace B — one manual Close press
1. Operator arms → confirms the two-step red button on the open-trade card (6s auto-disarm).
2. Browser `POST /api/close_position?key=…` → `_endpoint_authed()` passes (401 otherwise, before
   any mutation) → `_pending_closes["tk:WFF"] = {ticker, trade_id, at_utc}` — **merge-only**, any
   other queued name untouched. `close_requested` decision row written. 600s TTL starts.
3. Bot: `monitor_trade` while-loop reaches the manual block (after the 15:45 flatten, before the
   quote fetch). `MANUAL_CLOSE` true, `_mclose_fired` false.
4. `_manual_close_pending()` — ≥5s cached GET, 3s timeout. Any error/401/malformed → `[]`,
   **no close**.
5. `_manual_close_match()`: trade_id match beats ticker; `at_utc <= entry_ts_utc` → **ignored**;
   no timestamp → **ignored**.
6. Match → `_mclose_fired = True` (**before** the sell) → `_safety_close(remaining_shares)`:
   cancel sell ladder → cancel resting stop → `close_position` at market.
7. Best-effort ack POST clears the request (failure cannot cause a second sell — the loop has
   already `break`ed).
8. `break` → normal post-loop record path: `exit_reason = "manual_close (Marcos)"`,
   `_exit_layer = "manual"` (excluded from stop/eod statistics),
   `_clear_open_trade(ticker, trade_id=trade_id)` — trade_id-keyed, no ghost.
9. UI shows "closing…" until the position leaves `/api/open_trades`.
*Worst-case latency: ~5s cache + the monitor's own cadence. If no monitor owns the position, the
request expires harmlessly at 10 minutes — there is no broker-side flatten fallback.*

---

## ROLL CALL (all offices per ROSTER.txt; "clean" is named explicitly)

- **Blast Radius Auditor** — GREEN. Both commits disjoint, both env-revertible, restart semantics
  benign (F-2 fails safe). Findings F-1…F-8, none blocking.
- **Dashboard Curator** — the Close button ships WITH its mechanism (mechanism-plus-display law
  satisfied). Owed: no display yet for `lane_exempt_applied` rows; queue a chip.
- **Systems Quant** — the derived sets compute exactly what the registry claims; equality
  re-derived by hand (§1), not taken on the rig's word. Clean.
- **Pit Crew Chief** — two kill switches, no schema change, no restart required to revert.
  Import-time env reads mean a switch flip needs a restart — state it in the ship note. Clean.
- **Integrator** — parallel-logic registry updated: 5 sets now derived, 12 remain literal by
  documented decision (§6). F-8 recorded: momentum's single-source is rig-enforced, not
  code-path-derived.
- **Side Marshal** — back-side gate untouched; tape lanes still bind (settled 8/5). Clean.
- **Crown Steward** — `crown_seam` and `halt_ladder` are newly ungated at the chart gate; this
  delivers a crown privilege that the copy-paste had silently withheld. `halt_ladder` is the
  cohort's best performer (+$93.93/N=3). Endorsed.
- **Feed Engineer** — no vendor surface touched. Clean.
- **Webull Broker Desk** — the manual close issues a real market sell through `close_position`.
  The owed **$5 place+cancel test remains owed** and is now more adjacent, not less.
- **Quartermaster** — no data/bars/backup surface touched. Clean.
- **Kev Librarian** — `kevseq` is the Kev-sequence lane; this restores the corpus-derived lane to
  the class doctrine always assigned it. Endorsed.
- **First Hour** — the 7 lanes fire mostly in the 09:30-10:30 window; today's WFF specimen is
  11:17. Attribution rows now carry `lane_exempt_applied` for the daily $ split.
- **Opening Bell** — `prevwap` is a premarket lane and is newly ungated; premarket entries are a
  separate book (RTH-primacy law) and must be graded on their own line Friday.
- **Seam Scientist** — `crown_seam` ungated; seam evidence state unchanged (still shadow-graded).
- **Strength Ombudsman** — **this is a strength-refusal REMOVAL and belongs in the bias ledger.**
  The gate was refusing a +307% name. Record it; Friday's hearing grades the bypassed cohort.
- **Forward Architect** — registered hypotheses: (i) close `TAPE_PREBREAK_LANES` (S-1);
  (ii) resolve `_MOMENTUM_TAPE_HOLDOUT` (S-2); (iii) lane stamp on `extension_reject`; each needs
  a kill-test before it ships.
- **Momentum Operator** — `check_momentum` behavior byte-identical; nothing ships on noise here.
  Clean.
- **Trade Manager** — the new `"manual"` exit layer keeps operator exits out of stop/eod capture
  statistics. Correct. Clean.
- **Tape Veteran** — hypothesis only: the negative cohort is `grinder`-driven; a per-lane rather
  than blanket exemption may be the real answer. Unverified, not a recommendation.
- **Reclaim Architect** — `vwap_reclaim` untouched in every set. Clean.
- **Execution Surgeon** — the manual sell routes through the single #53 choke point;
  double-sell race closed by `_mclose_fired`-before-sell + `break`. F-5/F-6 logged. No RED.
- **Handicapper** — selection surface unchanged; the character book is untouched. Clean.
- **Rocket Rider** — `rocket_catcher` gains chart-gate bypass on paper but is `ROCKET_CATCHER=0`;
  inert. It nonetheless supplies −$108.65 of the counterfactual and must be excluded from any
  live read of that number.
- **Cartographer** — `_STALE_EXEMPT` change is observe-only; map quality untouched. Note: tape
  lanes now bypass `no_marked_level` entirely, so a sparse map no longer suppresses them — which
  is the settled intent (maps describe, never serve).
- **Wind Tunnel Engineer** — counterfactual is E3 live-parity ($500, +1% slip, bank ½ at +10%,
  trail 10% off run-high, intrabar stop first, −0.5% on market exits). Fidelity acceptable; the
  truncated 8/17 tape is the known defect and owes tonight's re-grade.
- **Statistician** — **the −$64.25 must reach RESULTS_LEDGER, not just the kill-test file.** F-1
  (extension delta unmeasured, N=0) and F-4 (the join is better grounded than claimed) both belong
  in the same entry. Manual exits must be excluded from lane expectancy — the `"manual"` layer
  makes that mechanical.
- **Convexity Trader** — judge the exempt cohort on mean-after-costs and tail shape, not the 31%
  win rate; the tail (WFF $1.61→$6.00) is the whole thesis and N=13 cannot resolve it.
- **Curl Mechanic** — `zone_flip` / reclaim fire-count acceptance unaffected. Clean.
- **Project Manager** — [VERIFIED] this turn: rig executed, sets hand-derived, source read,
  tree clean. [UNVERIFIED]: the full-day 8/17 re-grade (owed tonight).
- **Historian** — provenance recorded: 7/24 (live-structure ruling), 7/26 (no absolute
  never-trade + scalar purge), 7/30 (ignition chart bypass, measured), 8/5 (back-side gate binds
  tape), 8/17 (registry). The registry is the first *structural* enforcement of a doctrine that
  had been maintained by hand since 7/24.
- **Hidden Entry Architect** — `v2conv` is newly ungated; v2's convert path now reaches the
  ticket on unmapped names. Its −$17.20/N=2 is inside the noise. Watch it in the v2 shadow book.

---

## SHIP_CHECK
Pre-artifact run (this convening): **EXIT 1 — RED on section Q only**
(`HEAD 4cc24ea99420 not covered by data/audits/LATEST.md`), the designed interlock. 548 green,
sections AN and AO present AND executed. Post-commit rerun appended below.

**POST-COMMIT RERUN (this convening, after the artifact commit): `SHIP_CHECK=1` EXIT 0 —
ALL GREEN, 549 green checks. Section Q: `ship-check: HEAD a264b666e393 audited + tree clean`.**
