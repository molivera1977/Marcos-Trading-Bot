# CONVENING ARTIFACT — 8/18 FOUNDATION REBUILD SHIP

covers: b4a0c2559ec3 — the audited tree, plus the 8/18 post-ship additions: gate 10 (extension blindness), gate 11 (refusal attribution) and gate 12 (server-side duty watch).
commit, and the rig AN update that pins the corrected close_position auth spec).

Audit run in a SEPARATE CONTEXT per `persona_blast_radius_auditor`. Verdict: **SHIP-WITH-CONDITIONS**.
No blocker survived verification. Every candidate blocker the auditor raised was chased to source
and **refuted by execution**, listed below so the refutations reach the ledger rather than dying in
a transcript (`feedback_refutation_must_reach_ledger`).

---

## 1. Refuted blockers (each chased, each dead)

| candidate | how it died |
|---|---|
| `_vol_cap` NameError on the fail-closed volguard path | `_vol_cap = None` initialized at :14107, before the try; `None == 0` is False, so :14156 is inert by default |
| `_hl_src` used before definition in the halt_ladder stamps | defined :9678, used :9712/:9733 |
| `_bucket_fresh`'s new 4th param breaking positional callers | all 6 call sites are keyword-only |
| boot crash on missing/corrupt `fire_hwm.json` | full module exec under a temp path: `BOOT_OK`; missing → `_fire_once` True; corrupt JSON → True (degrades open) |
| signature changes (`check_momentum`, `bandpass_step`, `kev_zoneflip_step`, `_marked_runway`) | all defaulted; every call site grepped; none broken |
| twins (resumed vs fresh monitor path) | `monitor_trade` is ONE function; the resumed path (:3179) calls it, so MANUAL_CLOSE covers resumed positions |
| logging able to gate | `_gate_blind` → `_log_decision` try/except-wrapped at both levels; no recursion path; `_map_snapshot` TTL-checks before any network |

## 2. Findings FIXED in this commit (all exercised, not just written)

1. **Fire-HWM did not survive a redeploy.** The 8/17 restart-replay fix persisted marks to the
   bot's local `data/fire_hwm.json` — but the bot has no `/data` volume (`screener_app.py:1362`
   states this outright for open positions). An in-place restart kept the file; a **redeploy wiped
   it**, and the deploy shipping the fix is itself a redeploy. The duplicate-fire defect was
   therefore fixed for only half its cases. Marks now live on the **dashboard volume** via a new
   authed `GET/POST /api/fire_hwm` with a **monotonic merge** (a lower mark can never un-suppress a
   bucket that already fired) and same-day-only keys (no cross-day suppression, bounded file).
   *Proof:* a live in-process dashboard + a simulated redeploy on an empty filesystem — the
   duplicate is suppressed, a genuinely new bucket still fires, and a dead dashboard degrades OPEN.
2. **The volume push sat inside the fire path** — up to 5s of network between signal and order on a
   momentum entry. Now async on a daemon thread; the boot pull moved out of the lock-held path into
   `_fire_hwm_rehydrate()`, called beside `_leader_rehydrate()`.
3. **`/api/close_position` GET was unauthenticated** on a public URL, exposing pending-close intent
   on a *selling* endpoint. Both verbs authed. A 401 lands in the bot's except branch → `[]` →
   **fail-closed**: an auth break can never cause a sale.
4. **`_mclose_cache` was unguarded shared state** across every monitor thread, on the sell path.
   Non-blocking lock: the winner fetches, everyone else takes the cached value — no monitor thread
   ever queues behind a 3s urlopen.
5. **`MANUAL_CLOSE_POLL_S` 5 → 15.** 5s × 6–8 position threads was ~1.6 req/s at the screener, and
   a hung dashboard could stall a monitor loop 3s per window. A manual close is a human action.
6. **`_blind_lane` was set and never cleared** — later blind rows inherited the previous fire's
   lane. Now time-stamped, 30s TTL. A blank attribution beats a wrong one, since the whole point of
   the field is to say which fire paid.
7. **volguard-closed refuse path** released the held-lock without `trade_lock`, unlike every sibling
   refuse path. Locked (mirrors minstop).

## 3. BEHAVIOR CHANGES — MARCOS'S CALL, NOT THE AUDITOR'S

Per `feedback_auditor_cannot_authorize_behavior`, the auditor closed holes in approved behavior and
**cleared none of these**. Ten defaults in this batch change money decisions. Priced against what
actually converts today (`GRINDER_CONVERT=1`, `SEAM_CONVERT=1`, `FLATTOP_BREAK_ATTACK=1`; kevseq /
v2 / bandpass / prevwap / halt-lane all 0):

| # | flag (default) | what it changes | converting lanes hit |
|---|---|---|---|
| 1 | `LANE_REGISTRY_EXEMPT=1` | chart_break_gate bypass 3 lanes → 12 | **grinder, crown_seam** |
| 2 | `LANE_REGISTRY_EXEMPT=1` | extension-guard exempt 7 → 14 | **grinder, crown_seam** |
| 3 | `TAPE_LANE_SCALAR_EXEMPT=1` | momentum veto bypassed for 5 lanes; kill-test cited is **N=1, +$25.14** | **grinder** |
| 4 | `V2_CAP_ON_FILLS=1` | daily cap counts fills, not attempts → strictly more trades/day | **grinder** |
| 5 | `DEDUPE_FIRES=1`, `MA_PULLBACK_DEDUPE=1` | **removes** trades (a fired bucket can't re-fire) | grinder, ma_pullback |
| 6 | `RTH_HANDOFF_MIN=5` | 09:30–09:34 fetches `[PRE,RTH]`, not RTH-only | all |
| 7 | `KEV_ROAD=1` | `_marked_runway` may return RR off `kev_road_max` | all |
| 8 | `KEVSEQ_FIRE_ON_CLOSE=1` | fires at bar close, not setup high | shadow only |
| 9 | `KEVSEQ_SELF_FRONTSIDE=1`, `M1_WALLCLOCK=1` | ~50 of 97 daily `front_side_unknown` refusals become fireable | shadow only |
| 10 | `MANUAL_CLOSE=1` | a **new exit path that sells** (fail-closed, TTL + entry-ts double guard) | all |

**Verified NOT money (observability only):** `MAP_STAMP`, `IGNITION_G1_SHADOW`, `CROWN_FIX_0817`,
`SCAN_CYCLE_TIMING`, `GATE_BLIND_ROWS_MAX`, `REREAD_ON_REJECT`, `FIRE_HWM_PATH`, and — after tracing
its only consumer at :3650, which logs `veto_noted_not_gating` and gates nothing — `KEV_VETO_READ`.
**Verified default-OFF:** `GATE_FAIL_CLOSED`, `LANE_FIRE_AGE_GUARD`, `KEVSEQ_LIMIT_ENTRY`,
`KEVSEQ_MAX_DRIFT`, `KEVSEQ_FIRE_MAX_AGE_S`.

**Flagged for the day it arms:** `LANE_FIRE_AGE_GUARD` measures against `CURL_FIRE_MAX_AGE_SECS=90`,
calibrated for 10s buckets. flat_top's bar is **180s** wide, so its age sweeps 0→180s. A bare
`LANE_FIRE_AGE_GUARD=flat_top` would eat every fire landing past 90s into a bar. It must be
`flat_top:300`+ from a measured distribution. This is why the stamps ship ON and the guards OFF.

### DECISIONS RENDERED 8/18 — ALL TEN (Marcos, walking them one at a time)

**Outcome: every default stands.** Three needed no sign-off (formal no-ops or already-settled
doctrine); seven Marcos affirmed after seeing the measured scope. NOTHING was changed as a
result of this review — but two defects the audit missed were opened and pinned (gate 10:
extension-guard blindness on 7 lanes; gate 11: 28 of 45 refusal statuses unattributable).

| # | flag | outcome | basis |
|---|---|---|---|
| 1 | `LANE_REGISTRY_EXEMPT` (chart gate) | **ON** | Mechanism is right (registry beats copy-paste; it was the WFF killer). Scope unpriced, so the counterfactual now ships on ALL 11 tape lanes — `shadow_gate` / `would_have_blocked` / `grant` — making it gradable Friday instead of arguable. |
| 2 | `LANE_REGISTRY_EXEMPT` (extension gate) | **NO SIGN-OFF NEEDED — formal no-op** | Measured: `extension_reject` = ZERO across 15 sessions. AST census: the 7 lanes it newly exempts are EXACTLY the 7 that never stamp `ema90`, so the guard already failed open on them. The audit's "grinder and crown_seam now un-capped" was wrong — they were never capped. Separate defect opened + gate 10. |
| 3 | `TAPE_LANE_SCALAR_EXEMPT` | **ON (affirmed)** | Already live since 8/17 12:01 (WFF row), so ON is the status quo and OFF was the change. Scope measured: 7 of 95 refusals over 14 sessions; 88 keep their veto. OFF would destroy the only gradable population. Ledger row `scalar_exempt_affirmed_0818`. The +$25.14 N=1 is explicitly NOT the basis. |
| 4 | `V2_CAP_ON_FILLS` | **ON (reaffirmed)** | Not a new policy — it enforces the SETTLED 7/29 ruling "a slot is spent by a TRADE, not an ATTEMPT" on three lanes never wired to `_slot_refund`. Measured 8/17: 46 `premarket_shadow_entry` non-trades consumed the caps; 47 `v2conv_capped` + 51 `grinder_capped` refusals followed, 16 of them in the 09:00 hour. Ledger row `cap_spent_by_trade_not_attempt` HOLDS. |

| 5 | `DEDUPE_FIRES` + `MA_PULLBACK_DEDUPE` | **ON** | "Removes trades" is misleading. Measured 8/17: 210 `triggered_ma_pullback` rows over 123 distinct (ticker,price) setups — 87 rows (41%) are RE-EMISSIONS of an already-fired setup (YDES $3.2933 x40, GRNQ $8.94 x33). The mark is a MONOTONIC high-water per (day,lane,symbol) on the 10s bucket, so a genuinely new setup carries a later bucket and still fires; only re-detections of the SAME setup bar collapse. `DEDUPE_FIRES` covers the restart class — 8/17 had 5 `boot_config` rows and each boot replayed state over bars up to 6,960s old. |

| 6 | `RTH_HANDOFF_MIN=5` | **ON** | Fix for the defect Marcos watched live 8/17: at 09:30:00 the session set flipped to RTH-only while ZERO completed RTH bars existed, so `_fresh_session` consumers got `[]` and 23/26 names were skipped 09:30–09:35 (WETO/FIEE/DFSC included) while their SIP PRE bars were seconds old. Widens WHICH of today's bars are visible, never HOW stale they may be. Ledger `bell_boundary_handoff_0817` HOLDS. NOTE: row counts in the bell window are NOT evidence for this defect — the failure was in the bar fetch, not in row emission. |
| 7 | `KEV_ROAD` | **ON** | The ONLY item of the ten that can make the bot MORE selective. Converts "no marked target above entry → `above_all_levels` → automatic pass" into a measured RR against Kev's shadow ceiling, which can newly REJECT when that road is short. Serves `our_numbers_primacy_0812` (Kev answers "is there road beyond our map?", never replaces our levels). Scope: `runway_reject` 11–22/day all lanes; KEV_ROAD engages only where our map has no target and Kev's does. UNBACKTESTABLE for days ≤8/17 — no map snapshots. |
| 8 | `KEVSEQ_FIRE_ON_CLOSE` | **ON** | `KEVSEQ_CONVERT=0` — verified, the lane does not trade, so this cannot change a fill. Fixes a level being reported as a traded price: WFF level $5.1329 vs traded $8.20 against a $4.80 stop = 6.49% stated risk vs 41.46% real, a 6.4× understatement. |
| 9 | `KEVSEQ_SELF_FRONTSIDE` + `M1_WALLCLOCK` | **ON** | Also dark (`KEVSEQ_CONVERT=0`); `M1_WALLCLOCK`'s only consumer is the kevseq ctx block at :9391 — verified it does not leak to converting lanes. `count=50` bars was read as "50 minutes" but spanned 243 min on RBNE and 584 min on UUU. ~50 of 97 daily `front_side_unknown` refusals become fireable. |
| 10 | `MANUAL_CLOSE` | **ON** | The only NEW machinery. Operator-initiated only; the bot never originates a request. 23 rig checks green (section AN): unreachable dashboard → NO close (fails CLOSED, opposite polarity to `_entries_paused`), 10-min TTL, request must post-date the position's entry, trade_id beats ticker, `_mclose_fired` set BEFORE the sell, exits through the SAME choke point as stop/flatten. Hardened tonight: poll 5s→15s, non-blocking cache lock, GET authed. |

**OWED — #10 is UNEXERCISED.** `manual_close` has fired ZERO times in production (checked 8/17,
8/14, 8/13). Everything above is rig-green against lifted code and a test client, not a real exit.
Per `feedback_no_feature_ships_unexercised`, use it once on purpose tomorrow: open a position,
close it from the dashboard, confirm the row and the fill.

**Watch item carried from #4 (not a prediction, a thing to look at):** with caps counting fills,
more triggers reach the order path, so the binding constraint moves from the cap ledger to
CAPITAL on $3,000. Expect `no_capital_skip` to become the visible limiter instead of `*_capped`.
That is a different failure mode than 8/17 showed; it should be watched, not forecast.

## 4. DAY-ONE WALKTHROUGH — first specimen, end to end

**Mechanism traced: the durable fire-HWM, through tomorrow's 03:55 boot.**
Boot prints the config banner → `_leader_rehydrate()` → `_fire_hwm_rehydrate()` GETs
`/api/fire_hwm`; on a fresh trading day the volume holds no `2026-08-18|…` keys, so it prints
`0 durable mark(s) restored` and proceeds — **the empty case is the expected first outing, not a
failure.** First grinder fire of the session: `_fire_once("grinder", SYM, k)` finds no mark →
returns True → the entry proceeds → `_fire_hwm_save()` writes locally and pushes async. Within ~1s
the dashboard volume holds `2026-08-18|grinder|SYM`. If the bot restarts *or is redeployed* later
that day, the boot pull restores the mark and that bucket cannot fire twice.
**What would stop it:** `SCREENER_URL` unset, or the dashboard unreachable at boot — in which case
the banner prints the explicit `⚠️ fire-HWM rehydrate failed … running on the local belt only`
warning. That warning line is the day-one check; the duty watch reads it at 07:12.
**Second specimen — MANUAL_CLOSE at the new 15s cadence:** a close posted at T is picked up within
15s, matched by trade_id (or ticker) with the entry-ts guard, and exits the full remaining position
through the same choke point as the stop. The observable is one `manual_close` row.

## 5. DOCTRINE-INVERSION SWEEP

**Doctrine touched: yes** — `LANE_REGISTRY_EXEMPT` inverts *who is exempt from the chart gate* from
a hand-written literal to a registry-derived set, and `V2_CAP_ON_FILLS` inverts *what a daily cap
counts* from attempts to fills. Both are enumerated in §3 as Marcos's call, un-cleared.
Sweep of places encoding the OLD doctrine: the legacy literal `_MOMENTUM_LEGACY_EXEMPT` still
exists and is still consulted (`:14246`) — it is now the *filter* that keeps `check_momentum`
byte-for-byte identical, i.e. deliberately retained, not stale. `TAPE_SCALAR_EXEMPT_LANES` is the
separate path for tape lanes. No third copy of the exempt set exists (grepped). The old hard-09:30
session flip survives only as the `RTH_HANDOFF_MIN=0` kill switch. **No orphaned encodings of a
repealed premise found** — the 8/5 skip-if-kev-levels class does not recur here.

## 6. ROLL CALL — every office on ROSTER.txt

- **Blast Radius Auditor** — TOUCHED. Ran the audit; 7 findings fixed, 10 behavior changes escalated to Marcos rather than cleared. Refused to authorize any default.
- **Dashboard Curator** — TOUCHED. Two new endpoints (`/api/fire_hwm` GET/POST) and an auth change on `/api/close_position` GET; dashboard JS already sends `?key=`, so no cockpit regression. Verified by test client.
- **Systems Quant** — TOUCHED. Harness parity is the open number: grinder 9%, kevseq ungradable, v2 51%; only prevwap/zone_flip/flat_top (N=3) and hidden (86%) approach the 90% bar. No backtest re-run is authorized on this parity.
- **Pit Crew Chief** — TOUCHED. Hot-loop cost measured, not estimated: ~25ms/cycle on a 25-name roster; no file I/O, network, or O(n²) added inside the scan loop. The 85–195s latency is untouched and remains open.
- **Integrator** — TOUCHED. Branches G/H/I merged, one real conflict in the shipset exec namespace resolved by taking G's superset. `agent/J` empty. All 8 rigs re-run post-merge.
- **Side Marshal** — CLEAN. No front/back-side gate semantics changed; `KEVSEQ_SELF_FRONTSIDE` alters the kevseq front-side *computation* but the lane does not convert.
- **Crown Steward** — CLEAN. `CROWN_FIX_0817` verified observability-only. Crown privileges unchanged.
- **Feed Engineer** — TOUCHED. `RTH_HANDOFF_MIN=5` changes which bars the first five minutes see; that is the bell-boundary fix and is listed as a behavior change (§3 #6).
- **Webull Broker Desk** — CLEAN. No broker, token, or BP path touched. Token re-mint ~8/23 unaffected.
- **Quartermaster** — TOUCHED, and this convening is where the office earned its keep: the fire-HWM durability hole is precisely a *storage-survives-a-deploy* question. Volume-vs-ephemeral now explicit in code comments. Restore drill still owed (task #50).
- **Kev Librarian** — CLEAN. Corpus, sweep, and vision pipeline untouched; `KEV_VETO_READ` traced and found inert.
- **First Hour** — TOUCHED. The 09:30–09:34 handoff window is a first-hour change; attribution rows now carry lane labels that expire rather than mislead.
- **Opening Bell** — TOUCHED. Same handoff seam; frozen-clock coverage at the boundary is pinned in the regression corpus (I4).
- **Seam Scientist** — CLEAN. crown_seam gains stamps only; the seam research program is unaffected. Note: crown_seam converts and is hit by §3 #1/#2.
- **Strength Ombudsman** — TOUCHED and *supportive*: items §3 #1–#4 all widen rather than narrow. The office's standing complaint is refusing strength; this batch errs the other way, which is why it needs Marcos's price, not a veto.
- **Forward Architect** — TOUCHED. Flagged the 90s-vs-180s threshold mismatch before it could arm (§3 note) — an improvement nobody asked for, caught pre-ship.
- **Momentum Operator** — TOUCHED. `TAPE_LANE_SCALAR_EXEMPT` bypasses the momentum veto for grinder on an **N=1** kill-test. Standing objection recorded: N=1 is not evidence.
- **Trade Manager** — TOUCHED. MANUAL_CLOSE is a new selling path; double-guarded (10-min TTL + entry-ts), fail-closed, and now polled at 15s.
- **Tape Veteran** — CLEAN. No tape-reading semantics changed.
- **Reclaim Architect** — CLEAN. prevwap gains stamps; the lane does not convert.
- **Execution Surgeon** — TOUCHED. Removed up to 5s of network from the fire path (§2 #2) — the office's core concern, signal-to-order latency.
- **Handicapper** — CLEAN. No sizing or ranking math changed. Sizing chain (risk → 70%/$1000 → 5%-of-volume) untouched.
- **Rocket Rider** — CLEAN. hidden/rocket lanes gain a price stamp only; `hidden_shadow_fire`'s `price` field deliberately unchanged so today's archive stays comparable.
- **Cartographer** — TOUCHED. `KEV_ROAD=1` may return runway RR off `kev_road_max` where it previously returned `above_all_levels`/None — a map-consuming change, escalated (§3 #7).
- **Wind Tunnel Engineer** — TOUCHED. 8 rig files exit 0; regression corpus now 13 fixtures, each with a negative control proving the fixture would have caught its defect.
- **Statistician** — TOUCHED. Standing objection: `TAPE_LANE_SCALAR_EXEMPT`'s N=1 and the `T B` wall's modest hold-out N (18/27) are both real but underpowered; neither licenses a size increase.
- **Convexity Trader** — CLEAN. No exit-tier or runner math changed; E3 exits untouched.
- **Curl Mechanic** — CLEAN. `LEADER_CURL_SLOTS=3` semantics (fire slots, not positions) unchanged.
- **Project Manager** — TOUCHED. Aug 20 deadline is 2 days out; this ship is foundation, not edge. Entries work begins after.
- **Historian** — TOUCHED. Recorded: F's ship landed with the standing rig broken (`9797563` put `threading.local()` and `_gate_blind()` inside three AST-lifted spans, exiting the shipset 1). That is the second AST-lift fragility incident (BH-c class) and per `feedback_kill_the_class_not_instance` the class — not the instance — now needs a census of every `exec()`-lifted span in the rig.
- **Hidden Entry Architect** — TOUCHED. `hidden_shadow_fire` gains `fire_px`/`fire_k`/`fire_age_s`; measured that the old price key was scoring the quote feed (median 1.02% off the fired bar close, exactly equal in only 13 of 195). Real post-fix parity arrives with 8/18 rows.

## 6b. POST-SHIP ADDITION — THE DUTY WATCH IS NOW SERVER-SIDE (8/18 01:35)

Marcos asked whether the laptop watch crons "are actually going to do something." Checked: no.
Three tasks in that scheduler are tombstoned "Laptop scheduler silently dead since 7/26/7/27",
and `kev-daily-scorecard` (enabled, weekdays) last ran 8/14 — it silently missed Monday 8/17.
A watch that needs a laptop awake is not a watch, and Marcos returns to work 8/20.

`_duty_watch_loop` moves DETECTION into the bot process, the same migration kev_sweep and
preopen_health made on 8/4. Checkpoints 07:12/09:42/12:48/15:52 ET, one row per
(day, checkpoint), reads only the durable archive + trades. Gate 12 proves by AST that it
cannot call `execute_trade` / `place_order` / `monitor_trade` / `_slot_refund`.

It answers THE MARCOS CHECK — "lanes fired, no fill → name the gate" — which was impossible
before tonight, because refusal rows carried no lane until gate 11. Gate 12 pins that
dependency so the watch cannot degrade back to "something was refused" with no lane.

## 7. Conditions carried into the ship

1. Items §3 #1–#10 are **not cleared**. Marcos signs off by name, or the four widening defaults
   (`LANE_REGISTRY_EXEMPT`, `TAPE_LANE_SCALAR_EXEMPT`, `V2_CAP_ON_FILLS`, `KEV_ROAD`) go to 0 for
   night one and only the observability half ships.
2. Stated plainly: harness parity is **not** at a level that licenses re-running the 62-day
   backtests. That waits on 8/18 stamped rows.
3. `ship.sh` gate 1c (`spec_gate.py HEAD`) passes **vacuously** on a merge commit — the
   spec-as-failing-test gate this batch shipped does not evaluate this batch. Known, not hidden.
4. Open and unfixed: scan-loop latency 85–195s; the fill model has never been validated against a
   real fill; `_marked_runway` is permanently un-replayable for days ≤ 8/17.
