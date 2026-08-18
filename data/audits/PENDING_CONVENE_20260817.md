# PENDING CONVENING — 8/17 reads/maps + boundary batch (BUILT, NOT DEPLOYED)

Blast Radius Auditor convening REQUIRED before any deploy (convene-or-don't-ship law;
this build session deliberately did NOT convene — separate context mandated). Tree to audit:
HEAD after the final batch commit. Full rig exit 0 after every item and at close.

## Items the convening must cover

1. **item1 (c4550d8)** — kev_shadow read-side: veto propagation (KEV_VETO_READ), kev_road_max
   stamp, KEV_ROAD runway extension in `_marked_runway`. BEHAVIOR CHANGE (road extension can
   flip runway_reject -> pass; Marcos-approved direction from the WETO refusal, priced in the
   commit). Verify: overlay wired on BOTH _freshest_rec return paths; _effective_map auto-map
   overlay preserves kev_road_max/veto; no gate consumes kev_shadow structure anywhere.
2. **item2 (a4fc25c)** — reread_on_reject marker (REREAD_ON_REJECT, 10-min cap) + reader
   marker-set addition. Read-side spend only (vision reads); check reader cap interaction
   (_capped still governs; marker storms bounded by the bot-side 10-min dict which RESETS on
   restart — restart semantics: worst case one extra marker per ticker per restart).
3. **item3 (b1711f9)** — read_starvation observe-only row in reader (READ_STARVATION).
   Observe-only; check the SYSTEM ticker row doesn't confuse dashboard consumers.
4. **item4 (e2ef254)** — ignition G1 shadow stamps (IGNITION_G1_SHADOW): vwap_side,
   hi_dist_pct, g1_shadow on triggered_ignition rows + breakout extra. NO enforcement
   (rig-asserted). Check: extra-dict key collision downstream (record/eyes writers), and that
   vwap at the fire site is the session vwap the guidance means (twin: monitor's session-VWAP
   fetch uses ["PRE","RTH"]; the scan-loop `vwap` variable's provenance should be named).
5. **item5 (fb90194)** — BOUNDARY_CENSUS_20260817.md + rig AK. Rig/docs only; confirm the
   bare-call pin (==3) and frozen-clock matrix match the shipped tree.

## Twins / neighborhoods to sweep

- `_freshest_rec` twins: `_effective_map` cache (20s TTL) now caches overlay output — veto and
  kev_road_max ride the cache; confirm no consumer caches a PRE-overlay rec elsewhere.
- `_marked_runway` consumers: gate site :12200s, live card :9860s, record sites :12800s —
  all now able to return kev_road_max-based (rr, tgt); confirm record-side stamps stay coherent
  (runway_pass rows can now carry a Kev-ceiling target).
- Reader: new statuses in the marker loop — dedup key includes recorded_at (storm-safe), but
  the bot's 10-min cap is the real limiter; verify _rr_state["seen_markers"] growth is bounded.
- Ignition consume block: stamps computed only on the convert path (post-daily-veto else); the
  ignition_daily_bad / below_convert rows do NOT carry stamps — acceptable? (guidance asked for
  "every conversion/fire decision point"; today only the FIRE row is stamped).

## Restart semantics

- `_reread_reject_t`, `_auto_read_asked`, `_starv` window, `_effmap_cache` all in-memory:
  restart = caps reset (bounded extra rows/reads, no money path).
- No env defaults changed except NEW envs (KEV_VETO_READ=1, KEV_ROAD=1, REREAD_ON_REJECT=1,
  READ_STARVATION=1, IGNITION_G1_SHADOW=1). Kill switches exist for all five.

## Doctrine-inversion sweep

- **8/12 OUR-NUMBERS PRIMACY: REAFFIRMED, not inverted.** Marcos 8/17 mid-build, verbatim:
  "remember I want Kev's picks but I want OUR map numbers ruling." The original item-1 spec
  (freshest-timestamp-wins promotion of kev_shadow structure) was CORRECTED mid-build and was
  NOT built: kev_shadow break/confirm/targets are never promoted, even when newer. Shipped
  shape = veto + kev_road_max + rung-exhausted road extension only. The convening should
  confirm no residual promotion path and record the reaffirmation in the ledger.
- 8/6 freshest-data law now scoped: freshest WITHIN our own sources (primary vs vision_shadow);
  Kev's word stays freshest for VETO only. Flag for Marcos if any officer reads tension.
- Item 1's KEV_ROAD is the only money-behavior change in the batch — it goes to Marcos priced
  (auditor-cannot-authorize law); the commit carries the WETO hand-trace.

## BATCH 2 (appended same day — build-only, NO deploy; book flat rule holds for the ship)

6. **item A (173d8f1)** — TAPE-LANE SCALAR-VETO EXEMPTION. ENFORCES SETTLED 7/26 doctrine
   ("do-not-trade blocks CHART lanes only; tape lanes trade through by design"; momentum scalar
   REFUTED). Kill-test FIRST: era archive join found exactly ONE tape-lane setup-quality veto
   (WETO 8/17 kevseq — today's specimen), E3 counterfactual +$25.14 -> BUILD by pre-registered
   rule (N=1 thinness flagged honestly; doctrine carries the weight). Change: worker momentum
   else-branch bypasses ONLY 'no momentum build' for kevseq/v2conv/grinder/bandpass/prevwap;
   illiquid + ambient TRADEABILITY floors and topping-tail keep their veto; every bypass logs
   scalar_veto_bypassed. Kill: TAPE_LANE_SCALAR_EXEMPT=0. Rig AL. MONEY-BEHAVIOR CHANGE
   (a previously vetoed tape-lane entry now proceeds) — doctrine-mandated, goes to Marcos priced.
7. **item B (cdbe7d4)** — CROWN forensic + CROWN_FIX_0817. Repairs the 8/5 meritocracy PROMISE'S
   VISIBILITY, not its behavior: forensic PROVED WETO was crowned 09:47:07 (one cycle after the
   first post-halt print over +40%); leader_armed was always the crown row. Fix = explicit
   observe-only 'crowned' row at qualify. Kill: CROWN_FIX_0817=0. Rig AM. Convening: confirm
   the 'crowned' status collides with nothing (dashboard by_status, rehydrate query untouched).

### Batch-2 sweep notes
- Item A touches the single momentum call site; vel5 set is chart-only (rig-pinned); exempt
  tuple unchanged; check_momentum internals untouched.
- Item B: 'crowned' written once, never read (rig-pinned); rehydrate still keys on leader_armed.

## Spec tensions logged for Marcos (NOT resolved here)

- Item 2: ceiling_reject was ALREADY a reader marker + fires `_request_auto_read` (30-min
  throttle). A stale ceiling_reject now posts BOTH lanes — double read-request pathways with
  different throttles (10 vs 30 min). Built as specced; dedup decision is Marcos's.
- Item 4: "at every ignition conversion/fire decision point" — stamps ride the fire/convert
  path only (the row that proceeds); refused fires (daily_bad, below_convert) are unstamped.
- Item 3: roster = today's levels sheet (kev_watchlist levels), not the bot's watch roster —
  the reader has no view of the bot's roster; chosen as the nearest in-process truth.
- Batch2 item A: counterfactual N=1 (the WETO specimen itself) — the exemption ships on doctrine
  + one priced specimen; Friday grades scalar_veto_bypassed rows on real traffic.
- Batch2 item B: two prior-close sources disagree (kevseq day_gain 137.17 vs eyes dg 124.45) —
  pin one source (split-adjustment class); and 40%-crossed-INSIDE-a-halt structurally delays the
  crown to resumption+1 cycle — halt-time crowning = behavior change, Marcos's call.

---

## Batch-3 item C — MANUAL CLOSE-POSITION CONTROL (NEW MONEY-CAPABLE CONTROL)

**⚠️ This one CLOSES POSITIONS. It is not observe-only.** Per "Auditor Cannot Authorize Behavior"
(8/13) and "Convene or Don't Ship", it must not deploy before the convening. It is
**operator-initiated, never autonomous** — the bot never originates a close request; it only
obeys one an operator created through the authed dashboard endpoint.

**Why**: Marcos said "close it" on a live position (DFSC) and there was no mechanism. The only
options were (a) wait for the stop or (b) restart — and since the 8/9 painless-restart work a
restart RESUMES positions rather than closing them. Required go-live safety control.

**Layers built** (BUILD + RIG ONLY — no deploy, no push, no env changes, no restarts; market open
with one position live at build time):
- **Dashboard** `screener_app.py` `/api/close_position` (GET pending set / POST authed via
  `_endpoint_authed()`), modelled exactly on `/api/pause_entries`. Merge-only, 10-min auto-expiry,
  explicit clear/ack path, `close_requested` decision row.
- **Bot** `marcos_trading_bot.py` `_manual_close_pending/_match/_ack` + a call site inside
  `monitor_trade`'s while-loop, immediately after the 15:45 flatten. Exits through the SAME `#53`
  choke point (`_safety_close` -> ladder cancel -> stop cancel -> `close_position`);
  `exit_reason = "manual_close (Marcos)"`; new `_exit_layer` bucket `"manual"` so operator exits
  never contaminate stop/eod statistics. Kill: `MANUAL_CLOSE=0`.
- **UI**: two-step red "Close position" button on each open-trade card (arm -> confirm, 6s
  auto-disarm), "closing…" until the position leaves `/api/open_trades`.
- **Rig section AN** (+ Y-b funnel count 16 -> 17). Full rig exit 0, 506 green.
- **Failure condition written FIRST**: `data/killtests/manual_close_20260817.md`.

**Safety properties the convening must attack**:
1. TWO independent stale guards — server 10-min expiry AND `at_utc > entry_ts_utc`. Neither alone
   is trusted. Target: can a request still reach a LATER position in the same name?
2. FAIL-CLOSED poll (opposite polarity to `_entries_paused`, which fails open). Any error/timeout/
   401/malformed body -> empty list -> no close; the cache is cleared on failure, never replayed.
3. Idempotency: `_mclose_fired` set BEFORE the sell, then `break`. One request, one sell.
4. No parallel exit path (rig-pinned: no `close_position(`/`_place_order(`/`cancel_order(` inside
   the manual block).
5. Auth: POST 401s without the secret; GET is read-only.

**Officers with an obvious stake**: Pit Crew Chief (deploy safety / failure domains), Execution
Surgeon (the sell itself, double-sell race), Blast Radius Auditor (mandatory), Trade Manager
(exit accounting + the new "manual" layer), Dashboard Curator (the button), Webull Broker Desk
(the real market sell — the owed $5 place+cancel test is adjacent), Statistician (manual exits
must be excluded from lane expectancy).

### Spec tensions for Marcos (NOT resolved here)
- **Latency vs poll load**: the order specified a >=5s cached poll, so a "close it now" takes up
  to ~5s (plus the monitor's own 0.5s/15s cadence) to fire. An instant control would need a push
  channel or a 1s poll. Marcos's call on the tradeoff.
- **No monitor, no close**: if no monitor thread owns the position (crashed process, pre-monitor
  window, watchdog-recovered state), nothing consumes the request and it expires silently after
  10 minutes. There is no broker-side flatten fallback. Whether that fallback is required for
  go-live is Marcos's call.
- **Dashboard auth in the browser**: the dashboard page itself is not secret-gated, so the Close
  button takes the secret from `?key=` in the URL, else prompts once (memory only, never stored).
  That means anyone holding the dashboard URL *with* the key can close a position. Tightening the
  operator-auth model is a separate decision.
- **No "close everything" verb** — built per-position by design. If Marcos wants a single
  panic-flatten, that is a different (and much larger blast-radius) control.
- **Fail-CLOSED vs the pause channel's fail-OPEN** are deliberately opposite polarities in the
  same codebase. Defensible (a close is irreversible), but it is now two rules to remember.

---

## SCOPE: LANE CLASSIFICATION REGISTRY (8/17, Marcos "build it now") — **MONEY BEHAVIOR**

**Commit:** see `lane registry` commit on this tree. **Doc:** `data/killtests/lane_registry_20260817.md`
**Kill-test:** `data/killtests/lane_registry_20260817.py` (+ `_out.json`). **Rig:** section AO, 30 checks, full rig exit 0.

### What changed (money)
`kevseq` — and every other lane the registry classifies TAPE (`v2conv`, `grinder`, `bandpass`,
`prevwap`, `crown_seam`, `halt_ladder`, `rocket_catcher`(OFF)) — is **newly EXEMPT from the
chart-break gate and the 25%-over-EMA90 extension guard**. Those gates carried copy-pasted
hardcoded lane tuples; a lane born after a gate was written defaulted to the WRONG side. WFF
11:17:43 kevseq @ $5.039 died to `chart_gate_block` on a name that ran $1.61 → $6.00 (+307%).

Also rewired to the registry: `_STALE_EXEMPT` (observe-only branch, no money) and
`check_momentum`'s exempt tuple (hoisted to a named constant — **membership unchanged**).
Kill switch `LANE_REGISTRY_EXEMPT=0` restores every pre-8/17 literal exactly, rig-pinned.
Every newly-granted bypass logs `lane_exempt_applied(lane, gate, price)`.

### ⚠️ The counterfactual is NET NEGATIVE
**−$64.25 / N=13 / −$4.94 per trade / 31% win** (era 7/13+, E3 live-parity, $500). Excluding
`rocket_catcher` (default OFF): **+$44.40 / N=10**. `kevseq` alone **+$32.58** (WFF, hand-traced
in the doc). Today's rows are truncated at 11:34 ET and owe a full-day re-grade tonight.
**Marcos decides whether `LANE_REGISTRY_EXEMPT` stays on.**

### Officers to convene
Blast Radius Auditor (two live gates changed mid-session, kill switch, restart semantics),
Systems Quant (does the derived set compute what the registry claims), Side Marshal +
Strength Ombudsman (this is a strength-refusal removal — the bias ledger should record it),
Statistician (the negative counterfactual must reach the ledger, not just this file),
Hidden Entry Architect + Crown Steward (`v2conv`/`crown_seam`/`halt_ladder` newly ungated),
Integrator (parallel-logic registry: which lists are derived vs still literal),
Historian (the doctrine's provenance: 7/24, 7/26, 7/30, 8/17).

### Spec tensions for Marcos (NOT resolved here)
- **The number is negative.** Doctrine says exempt; the measured cohort says −$64.25. Settled
  doctrine won because he ordered the build — but this is exactly the kind of "coherent bad
  design" the review-both-sides law exists for. His call.
- **`TAPE_PREBREAK_LANES` is an OPEN HOLE the mirror-image way**: it gates only
  `hidden_entry,vwap_reclaim,zone_flip`, so the five new tape lanes escape the 8/3 dead-zone
  block. Closing it *removes* money, so it was left alone deliberately.
- **`_MOMENTUM_TAPE_HOLDOUT`** (`rocket_catcher`, `crown_seam`, `halt_ladder`) stay subject to the
  momentum scalar so `check_momentum` behavior is unchanged. Doctrine says they should be exempt.
- **`chart_gate_blocked_trade` / `extension_reject` rows carry NO lane stamp**, so the
  counterfactual's lane attribution is a ±20s ticker join. A stamp should be added.
- **Rig pins amended, not just added**: AF-l / AG-x / AH-x asserted these lanes were *absent* from
  `_STALE_EXEMPT` — those assertions encoded the defect and were rewritten. An auditor should
  confirm that rewrite is legitimate and not a green-washing of my own change.

---

## SCOPE ADD — ENTRY-DRIFT FIX (kevseq fire-price vs entry-price)

Doc: `data/killtests/entry_drift_20260817.md` · kill-test:
`data/killtests/entry_drift_20260817.py` · rig section **AP** (25 checks) · full rig 573 green,
exit 0.

### What changed
- **Always-on stamps** (observe-only, no behaviour change): `fire_age_s` (halt-aware),
  `drift_pct`, `quote_px`, `bar_lo` on every `kevseq_reject` / `kevseq_shadow_fire` /
  `triggered_kevseq` row; `intended_risk_pct` + `actual_risk_pct` on `triggered_kevseq`;
  `fire_age_s` + `drift_pct` on `triggered_v2conv` / `_grinder` / `_bandpass` / `_prevwap`.
  Closes the "`fire_age_s` is None on every kevseq row" hole (nothing ever computed it).
- **`kevseq_step`** returns `bar_lo` / `bar_hi` (additive keys only).
- **Four env switches, ALL DEFAULT OFF**: `KEVSEQ_LIMIT_ENTRY` (F3, winner),
  `KEVSEQ_ENTRY_TOL=0.005`, `KEVSEQ_MAX_DRIFT=0`, `KEVSEQ_FIRE_MAX_AGE_S=0`. Unsetting every
  one restores today's behaviour byte-for-byte (pinned AP-o).
- **Rig pin AG-vii AMENDED** (the conversion-guard literal now carries `not _ks_veto`). An
  auditor must confirm that rewrite is legitimate and not green-washing — same standard applied
  to the AF-l/AG-x/AH-x amendments above.

### Numbers
Live drift: kevseq median **+5.02%**, max **+28.87%** (WFF 8/17 fire $3.91 → entry $5.039,
intended risk 5.9% → **actual 27.0%**) vs every close-anchored lane at ~0%. Damage: **7 refused
trades** across all lanes where the fire-price trade would have passed the same R-gate
(kevseq's own: PFSA 10:22, RR 0.12 → **1.41**); on the universe replay **194 of 1,288 fires**
(15%) killed by the 6% min-stop floor at the drifted entry alone. Winner **F3 limit-at-fire
+0.5%**: MINE $−3.54 → **$−0.56**/tr, HOLD-OUT $−2.46 → **$−0.73**/tr, keeping 97–98% of N.

### Officers to convene
**Execution Surgeon** (planned-R = realized-R — this defect is the office's charter case; and
the real-money `ENTRY_LIMIT_BUFFER` tension below is his call), **Blast Radius Auditor** (four
new switches + an amended pin + a detector return-shape change), **Systems Quant** (does
`drift_pct` compute what its name claims on every row type), **Hidden Entry Architect** (kevseq
is the v2-era tape lane; F3 is "anticipation not chasing" in mechanism form), **Statistician**
(the replay numbers must reach RESULTS_LEDGER, not just this file), **Wind Tunnel Engineer**
(the fill-realism model: `bar_lo <= limit` — is that the honest fill rule?), **Strength
Ombudsman** (F3 refuses ~2–3% of fires outright — a refusal that needs its bias hearing),
**Dashboard Curator** (`kevseq_drift_reject` and the new stamps need a display),
**Feed Engineer** (quote-vs-bar-batch latency is the small half of the drift).

### Spec tensions for Marcos (NOT resolved here)
- **Nothing is defaulted ON.** Every arm is still net-negative on the superset cohort; F3 makes
  the lane lose less, not win. Recommended setting to price: `KEVSEQ_LIMIT_ENTRY=1`, tol 0.005.
- **Real money needs a lane-aware `ENTRY_LIMIT_BUFFER`.** The executor places a marketable LIMIT
  at `entry × 1.01` (`:615`, `:9399`); under F3 that lands up to **1.5% over the fire price**,
  and the kill-test says +1.0% tolerance **collapses** the arm ($−2.96/tr). DRY_RUN matches the
  kill-test exactly; real money does not. Deliberately not built — it touches the shared
  executor mid-session. **Owed before any real-money kevseq run.**
- **F3 means some fires produce no trade.** If the intent is that every kevseq fire becomes a
  position, F3 is the wrong shape and F2 (re-anchor the stop) is the alternative — at the cost of
  abandoning structural stop placement, i.e. a different strategy wearing the lane's name.
- **F4 (fire-age guard) is NEEDS-DATA, not refuted** — unfalsifiable on the cache (modelled age
  is always ~0s). Ships disabled; the new stamps start the distribution tonight.
- **Sibling lanes get stamps but no veto** (measured drift ~0.4% = quote latency, not the
  structural defect). If their stamped distributions come back looking like kevseq's, the same
  F3 mechanism ports directly.

---

## SCOPE ADDITION — TRIGGER-TO-FILL DEFECTS 1a / 1b / 2 / 3 (Marcos: "fix all four now")

Context: the seven top-ranked board runners on 8/17 (TRUG +57.8%, PFSA +36.4%, CDTG +34.9%,
SLE +29.5%, XPON +27.2%, MYSZ +23.7%, GRNQ +18.8%) produced **39 triggers and ZERO fills**.
The roster and the ranking are correct; the trigger-to-fill pipeline is what failed.
Four commits, full rig ALL GREEN (exit 0) after each. NOT deployed — market open, position live.

| # | commit | what changed | default |
|---|---|---|---|
| 1a | `edcb671` | **nothing** — burst saturation REFUTED as a money defect | n/a |
| 1b | `94550d4` | kevseq self-computes `front_side` from the 10s bars | `KEVSEQ_SELF_FRONTSIDE=1` |
| 2 | `a4ad672` | conversion cap tickets refunded when a trigger never fills | `V2_CAP_ON_FILLS=1` |
| 3 | `516e123` | per-cycle scan-loop timing rows (measurement only) | `SCAN_CYCLE_TIMING=1` |

Kill-test / forensic docs: `data/killtests/burst_saturation_20260817.md`,
`frontside_selfcompute_20260817.md`, `ghost_cap_20260817.md`, `scanloop_latency_20260817.md`.

### Officers this scope addition touches (standing room — every office is present)

- **Blast Radius Auditor** — three behaviour-adjacent switches; the `_slot_refund` change
  reaches ~13 existing call sites in `_trade_worker` by design. Restart semantics: all three
  new state stores (`_ks_1m_agg`, the refunded ledgers, `_cyc`) are in-memory and rebuild from
  live tape within one cycle; none is durable, none needs to be.
- **Systems Quant** — does `kevseq_front_side` compute what its name claims? It is EMA9 vs
  EMA20 on a 10s->1min fold; the `kevseq_frontside_disagree` canary is the standing check.
- **Statistician** — the burst-saturation numbers (2,251 candidates, OOS split, runner cohort)
  are in `_out.json` / `_run.txt` and owe a RESULTS_LEDGER line.
- **Strength Ombudsman** — 1b converts ~50 refusals/day of STRENGTH into evidence rows. This is
  the bias-ledger's best week of new data; the refused-strength hearing should re-run once the
  `front_side_src` distribution exists.
- **Hidden Entry Architect / Seam Scientist** — the 1a finding (kevseq's edge lives ONLY in the
  100%+ vertical cohort) is a cohort result the v2 rebuild should inherit, not rediscover.
- **Dashboard Curator** — three new row types need a display: `kevseq_frontside_disagree`,
  the widened `slot_refunded`, and `scan_cycle_timing` (a cycle-latency tile is the honest
  cockpit answer to "why did we miss it").
- **Feed Engineer + Webull Broker Desk** — defect 3's diagnosis is a vendor-round-trip budget
  problem: 4-5 blocking REST trips per name per cycle. The vendor-constraint ledger owns the
  per-call latency numbers the executor design will need.
- **Pit Crew Chief** — three env switches added; all three restore today's behaviour at `=0`.
- **First Hour / Opening Bell** — the cap ghost and the cycle tail both bite hardest 09:30-10:30.
  Both now have rows; the first-hour attribution should split by them tomorrow.
- **Historian** — 8/17 is the day the ranking was cleared and the pipeline was charged.
- **Quartermaster / Kev Librarian / Cartographer / Crown Steward / Side Marshal / Curl Mechanic /
  Trade Manager / Execution Surgeon / Handicapper / Rocket Rider / Integrator / Momentum Operator /
  Tape Veteran / Convexity Trader / Wind Tunnel Engineer / Reclaim Architect / Project Manager /
  Forward Architect** — **CLEAN**: no map, corpus, warehouse, crown, side, exit, sizing, or
  backtest-fidelity surface is touched by these four commits. Named so no officer is denied
  their say.

### Doctrine-inversion sweep
- `feedback_edge_over_mechanisms` — inverted? These are plumbing fixes, not edge. Held: 1a WAS
  graded on expectancy and refused on it, and the session's headline finding (the vertical cohort)
  is an edge result, not a mechanism claim.
- `feedback_auditor_cannot_authorize_behavior` — inverted? 2 changes what the bot does with money.
  Held only because "a slot is spent by a TRADE, not an ATTEMPT" is Marcos's own 7/29 instruction
  and the new lanes were never wired to it. **If he reads that as a new behaviour, `V2_CAP_ON_FILLS=0`
  is the one-character revert.**
- `feedback_no_lesser_fix` — inverted? Defect 3 ships the SMALLER fix (instrumentation) while a
  fuller one (executor fan-out) is describable. Held under permission: the brief explicitly said
  to build measurement rather than a risky mid-week refactor. Flagged so it is a choice, not a drift.
- `feedback_skepticism_needs_verification_too` — 1a is a REFUTED verdict, so it owed a named check
  run: the check is `burst_saturation_20260817.py`, 2,251 candidates, OOS split, executed, output
  committed.

### Spec tensions for Marcos (unresolved)
1. **kevseq's edge is cohort-bound.** At `KEVSEQ_GAIN_MIN=20` the lane is net-negative
   (HOLD-OUT $-0.73/tr). Restricted to 100%+ verticals it is **+$9.34/tr HOLD-OUT, N=174**.
   Raising the floor is a behaviour change and is his to price.
2. **`KEVSEQ_CONVERT` in the live env.** 1b defaults ON because kevseq is a SHADOW lane in code
   (`KEVSEQ_CONVERT` defaults 0). I did **not** read the live Railway env this turn — `[UNVERIFIED]`.
   If it is 1 live, 1b is a money-changing default and must be re-priced.
3. **Cap restart amnesia (found, NOT fixed).** `day_n` on today's 15 `triggered_v2conv` rows reads
   1..5, 1..5, 1..5 — the in-memory counter reset three times. The cap is simultaneously too tight
   (ghost triggers) and not binding (restarts re-grant it). Making it durable is a design change.
4. **"Cap on fills" removes any limit on ATTEMPTS.** If the original intent included limiting how
   often we go near a trigger, that intent is now gone and it wants a two-counter design.
5. **Defect 3 is a deferred architecture decision,** not a fix. One session of `scan_cycle_timing`
   rows should decide it.

---

## SCOPE ADD (8/17 afternoon) — KEVSEQ FRONT-SIDE SOURCE AUDIT
Doc: `data/killtests/kevseq_frontside_tf_20260817.md`. Script: `kevseq_frontside_sources_20260817.py`.
Rig section **TF** (16 pins), full rig exit 0. Files: `marcos_trading_bot.py` (stamps + corrected
spec header), `rig/test_shipset_20260804.py`.

- **The 3-MIN premise was FALSE.** The kevseq caller was always on M1 bars (`_ks_1m`, stamped
  `caller_1m`); `SETUP_TF_MIN` never appears in its ctx block. No timeframe defect, no timeframe
  cost, and the behaviour switch built under that premise was REMOVED before commit.
- **The real defect: two 1-MIN sources on different clocks.** caller = TRADED minutes only,
  capped at 50, RTH-only → on a thin name its 49-bar "1-min EMA20" spans **584 min (UUU, 9.7h)**,
  233–260 min (RBNE), 183 min (FXHO). self = contiguous wall-clock minute grid from the 10s stream
  (UUU held 155 buckets on a day with 54 traded minutes). Caller model reproduces 31/31 logged
  signs. On liquid names the clocks coincide and 27 of 31 disagreements sit inside |9−20| ≤ 0.25%.
- **PROPOSED, NOT SHIPPED (Marcos's call):** invert precedence — self primary, caller M1 fallback;
  or keep caller primary with a wall-clock STALENESS floor + a bigger fetch. Grade first: both
  values are now stamped on every row.
- **Feed Engineer ledger item:** "M1 REST returns traded minutes only and is count-capped" is a
  vendor-shape constraint that has now bitten a detector. Any other consumer of a fixed-count M1
  fetch inherits the same hours-wide window on thin tape — census owed.
- Artifact audit stands (unchanged by the correction): **no offline study replicated the live
  front-side gate** — entry_drift / burst_saturation / floor_sweep / reconciliation applied NO
  front-side clause; kev_rosetta used a 10s front side; fastchart_2tf benchmarked 1MIN vs 3MIN
  (1MIN −$382 vs 3MIN −$1,184). Every kevseq $ figure we hold is a front-side-free superset.
- Today's front-side-only refusals: **N=8** (IPST 04:05 $3.89, PFSA 09:45 $4.77 + 09:47 $4.98,
  WETO 09:50 $13.43 + 11:58 $17.60, CDTG 09:50 $2.6892 + 09:51 $2.73, STFS 10:02 $6.63); 7 of 8
  are the `unknown` class the 13:49 self-frontside fix already closes. Cost of the alleged
  timeframe defect: **$0 / N=0**.
- No other lane has a front-side spec/timeframe mismatch (census in §7 of the doc).

## M1 WALL-CLOCK WINDOW CLASS (built + rig-green 8/17 intraday; NO deploy — awaiting convene)
Doc: `data/killtests/m1_wallclock_20260817.md`. The fixed-count M1 defect class (traded-minute
grid spans hours on thin tape; 31/31 kevseq disagree rows reproduced) — census of ALL 14
fixed-count fetch sites + consumers. Shipped in code: `_wallclock_window()` helper + the kevseq
caller front-side windowed to 50 wall-clock minutes (`M1_WALLCLOCK=1` default, `=0` restores raw;
`KS_FS_WALLCLOCK_MIN=50`; boot_config stamps both; existing EMA20_PERIOD+2 minimum -> fail-closed
path unchanged; dense-list byte-equivalence rig-asserted). Rig section M1W (10 pins) + FS-c/TF-c
pins updated to the windowed form. FLAGGED, NOT touched (money/monitor decisions for the room):
monitor_trade :11087 EMA-exit bars and _vride_defer :9930 (position-open paths); check_momentum
:4199, volume guard :13113, universal liquidity :13201 (windowing routes thin names to their
FAIL-OPEN insufficient paths = looser gates -> priced for Marcos). Spec tension in doc §5.

## LIVE-CODE STUDY HARNESS (built + rig-green 8/17 evening; RESEARCH-ONLY — no deploy, no bot change)
Doc: `data/killtests/harness_parity_20260817.md`. Marcos's order after the front-side finding.
Kills the replica-drift class: studies now run the BOT'S OWN detector functions over historical
10s bars instead of re-implementing them (`kevseq_frontside_tf_20260817.md` — four studies with
NO front-side clause at all; same species as the fill-model drift).

**Scope of this ship (all under `data/killtests/` + rig):**
- `live_harness.py` — AST loader lifts 40 real bot symbols (kevseq_step / kevseq_feed_1m /
  kevseq_front_side / grinder_shadow_step / bandpass_step (RTH+PRE) / v2_pullback_step /
  v2_trailing_calm / ignition_10s_step / detect_ignition / _seq_events / _wallclock_window /
  _scaled_risk / aggregate_bars / EMAs / bar helpers / check_momentum) into an isolated
  namespace. NO `import marcos_trading_bot` (module-level side effects = a live path).
  Network poisoned, broker SDK inert, replay clock frozen.
- CONTEXT CONTRACT: a detector whose required ctx is missing is REFUSED by name
  (kevseq: front_side/day_gain/top3/blue_sky; every vwap-gated lane needs a vwap_provider).
  Explicit `None` = deliberate unknown, allowed. Absence = refused. This is the defect, encoded.
- `harness_parity_20260817.py` + `_out.json` / `_run.txt` — today-parity vs the live rows.
- Rig section **BH** (13 pins) incl. the GUARD PIN that `marcos_trading_bot.py` never imports
  the harness (one-way dependency), and a source-match pin on the mirrored sizing clamps.

**BOT UNCHANGED.** `marcos_trading_bot.py` was not modified at all — the AST loader made a
bot-side "make it importable" edit unnecessary. Full rig exit 0.

**TODAY-PARITY (reported, not tuned):** prevwap 3/3 = 100% · v2 84/164 = 51.2% ·
bandpass 4/9 = 44.4% · kevseq 7/23 = 30.4% · grinder 6/66 = 9.1% (exact price AND stop to 4dp,
|dt| <= 300s, 60s cadence). Detector fidelity is proven (exact 4dp price+stop hits are not
coincidence); the residual is INPUT fidelity — live eats the cursor-driven recorder feed and one
`_vr_sv` vwap scalar per rescan, the harness eats the complete SIP day. Ruled out by experiment:
timing (whole-day tolerance moves it <=5 pts) and feed-start window (grinder fire COUNT dials
19->44, exact matches stay 6-7).

**FOR THE ROOM — two items:**
1. **DUPLICATE LIVE FIRES (new finding, observe-only, no money change).** The 8/17 archive
   carries repeated identical fires: grinder 66 rows -> 53 distinct (ticker,px,stop), RBNE
   (2.78/2.76) logged 5x (11:06, 11:14, 12:01, 13:50, 13:59), GNPX 4x; v2 164 -> 143; bandpass
   9 -> 8. Something is re-feeding already-consumed buckets. Owner: Integrator / Feed Engineer.
2. **PROPOSED (not shipped): stamp the fed bucket epoch `k` on every shadow-fire row.** Every
   detector already returns `k`; it is simply not logged. That single logging field would let the
   harness replay the EXACT fed stream and turn parity into a true equivalence test. Observe-only,
   changes no money decision — but it is a behaviour change to an approved path, so it goes to
   Marcos priced rather than riding this research ship
   (`feedback_auditor_cannot_authorize_behavior`).

**Standing rule proposed:** until (2) exists, any study using the harness reports its lane's
harness-vs-live parity alongside its result. Hand-rolling a detector is no longer an option.

---

## EG1 DOCKET — LANE-COMPLETENESS PROPERTIES OPEN AT HEAD (added 2026-08-17, enforcement-gate build)

Rig section **EG1** (`rig/test_shipset_20260804.py`) grades every lane whose `*_CONVERT` env can
be set to 1 against seven properties. The items below are **KNOWN-OPEN at HEAD**: they are pinned
as `OPEN` in `_E1_PIN` so the rig WARNS rather than fails, and the pin itself is enforced — the
moment one of them becomes true without the pin being updated, EG1 goes RED. Each one is a change
to **what the bot does with money**, so per `feedback_auditor_cannot_authorize_behavior` it goes
to Marcos priced; it does NOT ride an auditor's ship.

### EG1-a — kevseq fires at a LEVEL, not a traded price  (ONE lane, still open)
`kevseq_step` returns `"px": round(px, 4)` where `px = float(pd["hi"])` — the setup bar's HIGH,
i.e. the trigger level. **Every other detector in the bot prices off the bar close `c`**
(`hidden_entry_step`, `v2_pullback_step`, `grinder_shadow_step`, `bandpass_step`,
`kev_zoneflip_step`, `kev_reclaim_step`, `dip_rip_step`, `ignition_10s_step` — verified by AST,
8/17). The 8/17 entry-drift ship added `bar_lo`/`bar_hi` + `drift_pct`/`fire_age_s` stamps and the
`KEVSEQ_LIMIT_ENTRY`/`KEVSEQ_MAX_DRIFT` guards (all env-OFF) so the drift is now *visible* — it did
not change the fire price, because that is a money-behaviour change.
**Decision owed from Marcos:** price `kevseq` at the fill bar's close (parity with every other
lane) vs keep the level with the drift guards. Evidence: `data/killtests/entry_drift_20260817.md`.

### EG1-b — no fire-age / staleness guard on five convertible lanes
`_log_stale_fire` (the `CURL_FIRE_MAX_AGE_SECS` suppressor) covers `vwap_reclaim`,
`hidden_entry`, `zone_flip`, `ignition10s`. It does **not** cover `v2conv`, `grinder`,
`bandpass`, `prevwap`, `flat_top`, `crown_seam`, `halt_ladder`. `kevseq` has a named guard
(`KEVSEQ_FIRE_MAX_AGE_S`, default 0 = disabled) — the mechanism exists, so EG1 scores it present.
Adding a suppressor to a lane REMOVES trades: money behaviour, Marcos prices it.

### EG1-c — no drift/age stamps on three lanes
`flat_top`, `crown_seam`, `halt_ladder` write no `drift_pct` / `fire_age_s` on their rows (they
have no fire dict of their own — the caller appends to `breakouts` inline). Observe-only to add,
but it is still a change to an approved path; queued rather than shipped tonight.

### EG4 — 64 of 87 killtest artifacts predate the caveat rule (grandfathered, not fixed)
Rig section **EG4** requires every `data/killtests/*.md` to carry a LIMITS/CAVEATS section, and
forbids a doc that discloses a limitation from stating a headline verdict that reads clean.
Snapshot frozen at `data/audits/EG4_GRANDFATHER_20260817.json`: **64 artifacts flag, 18 of them
with a BARE VERDICT over a disclosed limitation.** Rewriting 64 documents unreviewed tonight
would be worse than the disease, so they are pinned as they stand and the rule is
**ENFORCED FORWARD from 2026-08-18** — no artifact dated 8/18 or later may be grandfathered.
The pin has teeth in both directions: a newly-broken doc is RED, a cleaned doc must be removed
from the snapshot, and an old doc that gets WORSE is RED.
**Owed:** a pass over the 18 bare-verdict docs (they are the ones a reader can be misled by),
starting with `burst_saturation_20260817.md` — the doc whose disclosed UNDERPOWERED condition
was on the page while its headline was reported anyway.

---

# ENFORCEMENT GATES 5-8 — 8/17 (BUILT, NOT DEPLOYED) — scope for the same convening

Marcos: "add all of them." **BUILD + RIG ONLY** — nothing deployed, no env touched, no
restart, no push. Built in a separate file (`rig/test_gates_20260817.py`) from the concurrent
gates 1-4 work in `rig/test_shipset_20260804.py`, deliberately, so the two could not collide.
Full rig exit 0 on BOTH files at close. Commits: `4683a88` (G5), `220e7c6` (G6), `d8f7785`
(G7), `a17ab1c` (G8 + wiring).

**Blast radius, stated up front: none of this touches the money path.** No lane, gate, sizing
rule, exit or order behaviour was modified. `marcos_trading_bot.py` is UNCHANGED by all four
gates; the only non-rig edits are `ship.sh` (two added gate steps) and
`data/killtests/nightly_book_verify.py` (one appended read-only reporting block). That is the
Auditor-cannot-authorize-behavior line held: these gates close holes in the PROCESS, and every
one of them refuses at BUILD time, never at trade time.

## What the convening must cover

1. **GATE 5 (`4683a88`) — spec-as-failing-test.** `rig/spec_gate.py`. A behaviour-changing
   commit must carry `Acceptance: <path>::SPEC_<name>`; the gate proves the named test FAILS at
   the commit's parent and PASSES at the commit, in throwaway `git worktree`s (the live tree is
   never stashed or checked out — a concurrent agent was working). Behaviour-changing is decided
   by AST normalisation of the two watched files (comments/docstrings/pure-logging exempt);
   limits are documented in the module docstring and err toward DEMANDING a test.
   *Auditor should check:* the worktree cleanup path (`worktree remove --force` in a `finally`)
   cannot leak into the real repo; `SPEC_GATE_TIMEOUT_S` default 600 is sane for the rig;
   and that `ship.sh`'s new `spec_gate.py HEAD` step cannot block a legitimate bookkeeping ship
   (verified: doc/audit/killtest commits classify EXEMPT).
2. **GATE 6 (`220e7c6`) — claim-without-check detector.** `data/audits/claim_audit.py`.
   Read-only transcript scanner; runs nowhere near the bot. Reports, never gates a build.
   *Auditor should check:* the honesty of the documented catch rate (3 of 4, with two
   caveats written into the docstring — see the report below), and that `EXPECTED_CATCHES=3`
   is a regression floor rather than a claim of completeness.
3. **GATE 7 (`d8f7785`) — decision reconciler.** `data/audits/DECISIONS.md` (9 rows) +
   `reconcile_decisions.py`, appended to the EXISTING nightly job — **no launchd agent was
   created**. All checks are greps plus one GET against the decisions timeline.
   *Auditor should check:* the nightly append is genuinely non-fatal (it is wrapped and cannot
   change the book-verify exit code); the `UNKNOWN` state is never counted as HOLDS; and that
   the `dry_run_proving_week` row's live probe reads the boot_config DECISION ROW (there is no
   `/api/boot_config` route — assuming one existed was itself the failure these gates target).
4. **GATE 8 (`a17ab1c`) — regression corpus.** `rig/regression_fixtures/` (5 fixtures) +
   the G8 rig section. Every fixture carries a negative control proving it fails on the pre-fix
   path (kill switches for a-d; `git show fb92556^` for e).
   *Auditor should check:* fixture (a)'s timestamps are RECONSTRUCTED — the raw RBNE bar list
   was never archived, so the file reproduces the documented invariants (48 bars, 243 min,
   13:50 anchor) rather than the original bytes. That is disclosed in the fixture's own
   `_source` field and should stay disclosed.

## Open items this build deliberately did NOT do

- **No retro-application of Gate 5.** Nothing before 8/17 carries the trailer, and inventing
  acceptance tests after the fact is the story-first failure the gate exists to stop. Confirmed
  by running it read-only on `1a5e42f` (today's M1 wall-clock ship): `NO_ACCEPTANCE_TEST`, as
  designed. Forward-looking from now.
- **Gate 6 catches numbers, not meanings.** Two of 8/17's four false claims ("$604", "the
  runway gate is the villain") were misreadings of REAL tool output. No grounding detector
  reaches them; Gates 5 and 7 are the mechanisms for that class. Written into the docstring
  rather than papered over.
- **`KEVSEQ_LIMIT_ENTRY` stays default OFF.** Fixture (b) pins its ARITHMETIC only. Turning it
  on vetoes 16 of 25 kevseq fires and costs money on today's tape
  (`today_counterfactual_20260817.md`) — a money decision, Marcos's to price, not an auditor's.

---

# RELIABILITY BATCH B — LANE DETECTOR/GATE DEFECTS (8/17, BUILD + RIG ONLY)

Marcos: *"fix everything that will make things reliable."* **No deploy, no push, no env change,
no restart.** Commits: `2d0a6cb` (B1), `6ee3fe2` (B2), `be32e2e` (B4 + B5 acceptance/docs).
B5's bot edits were swept into `460dca5` — see the collision note below. Full rig exit 0 on
`rig/test_shipset_20260804.py`, `rig/test_gates_20260817.py` and the new
`rig/test_batchB_20260817.py` at close.

## Money-behaviour changes in this batch (Marcos prices these, not an auditor)

1. **B1 `KEVSEQ_FIRE_ON_CLOSE` (default ON)** — kevseq now prices its fire at the fill bar's
   close instead of the setup bar's high. **Changes sizing on every kevseq fire** and turns 2 of
   today's 23 into `degenerate_stop` refusals. Risk% on today's 23: median 2.60 → 3.34, mean
   3.56 → 9.28, max 12.94 → 41.46, >20% risk 0 → 3. The old column was fictitious, not smaller.
   Doc `data/killtests/kevseq_fire_price_20260817.md` (WFF 12:01 and WETO 13:50 hand-traced).
2. **B2 `LANE_FIRE_AGE_GUARD` (default `""` — ARMED ON NOTHING)** — the mechanism exists for
   v2conv/grinder/bandpass/prevwap; no lane suppresses anything until Marcos arms one.
   Recommended first: `grinder` (4 of its 5 stamped fires today were >90s, median 38 minutes),
   after one session of stamped rows. Doc `data/killtests/lane_fire_age_20260817.md`.
3. **B5 `GATE_FAIL_CLOSED` (default `""` — REFUSES NOTHING)** — momentum / volguard / ambient
   can each be armed to fail CLOSED. Cost unquantifiable today (see below), so all OFF.
   Doc `data/killtests/fail_open_gates_20260817.md`.

## EG1 matrix — pins changed

| pin | was | now | why |
|---|---|---|---|
| `kevseq.a` | OPEN (EG1-a) | **True** | B1 |
| `v2conv.b` `grinder.b` `bandpass.b` `prevwap.b` | OPEN (EG1-b) | **True** | B2 (mechanism present; armed on nothing — same scoring rule EG1 already applied to `KEVSEQ_FIRE_MAX_AGE_S`) |
| `flat_top.b/.c` `crown_seam.b/.c` `halt_ladder.b/.c` | OPEN | **STILL OPEN** | see "not built" |

Two EG1-support pins were also updated, deliberately and visibly:
- **`AP-w` INVERTED.** It asserted *"kevseq is the ONLY detector returning a SETUP-BAR HIGH"*.
  B1 closed that, so the check now asserts the opposite and additionally pins `level_px` and the
  kill switch — the old shape must be **gone**, not merely different.
- **`AG-i` repinned** from `px == 10.29` (the W setup high) to `px == 10.30` (the fill close)
  **plus** `level_px == 10.29`, so neither the price nor the level can drift unnoticed.
- **halt-aware site count 4 → 5** `_bucket_fresh(k, sym=)` sites (4 in-detector + the shared
  `_lane_fire_stale` helper). The EG1 property computer now recognises `_lane_fire_stale` as
  the shared form of the same mechanism.

## NOT BUILT — named, with reasons

- **B3 (drift/age stamps on flat_top, crown_seam, halt_ladder) — NOT SHIPPED.** These three have
  no separable detector, no fire dict and **no bucket epoch**: their fire price is the live
  quote, appended to `breakouts` inline by the caller. There is nothing to age or to drift
  against without first giving them a fire-bar identity. Doing that is a change to how three
  approved lanes report their entries and belongs in a scoped item, not a stamp.
- **B2 for those same three lanes — NOT SHIPPED**, for the same reason. Porting "the same
  mechanism" to a lane with no bar to measure would mean inventing a different mechanism and
  calling it the same one.
- **B4 — no detector change, by diagnosis.** Zero fires today had a stop at/above their own fire
  price. 17 of the 35 were the study's hand-rolled stop (`ma_pullback` logs no stop); 9 were the
  study comparing against the live quote instead of `fire_px`; 9 were the `hidden_shadow_fire`
  ROW pairing a live quote with a fire-bar stop. The last is a real defect **on the logging
  side**, which a concurrent agent owns — handed off, not edited from two directions.
  Doc `data/killtests/bad_stop_20260817.md`.

## What the convening must cover

1. **B1 blast radius.** `_ksf["px"]` feeds: the drift stamp (:8715), the `KEVSEQ_LIMIT_ENTRY`
   limit (`_ks_lim`), the `bar_lo > _ks_lim` unfillable-limit veto, `intended_risk_pct`, the
   conversion guard `_ksf["would_stop"] < _ksf["px"]`, and `breakouts.append`. All now see the
   honest price; confirm the F1/F3/F4 guard ladder still reads correctly against a close-based
   fire (their thresholds were calibrated against a LEVEL-based one — **the drift-guard
   tolerances may now be mis-scaled and should be re-graded, not assumed**).
2. **`level_px` is a NEW key on the kevseq fire dict.** Confirm no downstream consumer iterates
   the dict's keys.
3. **B2 restart semantics.** `_LANE_AGE_GUARD` is parsed lazily into a module-level dict and
   never re-read; an env change requires a restart to take effect. On a suppression the setup is
   consumed (`st["n"]`++ and cooldown), so a restart that replays buckets will re-arm the lane
   from scratch — the interaction with the A1 fired-bucket high-water mark should be checked by
   whoever owns A1.
4. **B5 `volguard` armed path** returns from inside `execute_trade`'s sizing block via the
   capital-skip shape. Confirm `_slot_refund` + `held`-lock release is the complete undo at that
   point (it is the same undo `no_capital_skip` performs three lines later).
5. **⚠️ GATE-5 COLLISION.** The concurrent agent commits with `git add -A` on the shared working
   tree and swept (a) this session's new rig file into `543888f` and (b) **this session's B5 bot
   edits into `460dca5`** — so a behaviour change landed without an `Acceptance:` trailer. Its
   acceptance test exists (`SPEC_fail_open_gates_observable_and_armable`, committed in
   `be32e2e`) and fails at `6ee3fe2`. **The convening must treat `460dca5` as carrying an
   unlabelled behaviour change**, and the two-agents-one-worktree pattern is itself a finding:
   B1/B2 were staged via synthesized blobs (`git update-index --cacheinfo`) specifically to
   avoid destroying the concurrent work, and that is not a mechanism that scales.
