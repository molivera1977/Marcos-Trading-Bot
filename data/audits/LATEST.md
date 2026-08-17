covers: 6d66b86bcfbe
# BLAST RADIUS CONVENING — 8/17 BATCH 4 (trigger-to-fill defects 1a/1b/2/3 + entry-drift)
Auditor: Blast Radius Auditor (separate context). URGENT convening: market OPEN, ~2h of session
left, and Marcos has WAIVED the flat-book gate with a live position (NIVF) — verbatim
"fuck NIVF". The waiver is his to give; it is recorded here, not re-litigated. It does NOT
waive the audit, and it makes the resumed-position safety check the single most important
item in this artifact (§6).

Tree audited: `6d66b86` (tip). Prior tip `4cc24ea` was audited GREEN in the batch-3 convening
(commit `2d672ee`); that verdict stands and is not re-opened. Working tree CLEAN at audit time
(`git status --porcelain` empty, verified this turn).

Commits in scope (`git log --oneline 4cc24ea..HEAD`, run this turn):

| # | commit | what | money? |
|---|---|---|---|
| — | `07f0c6c` | ENTRY-DRIFT: kevseq fire-px vs entry-px — stamps ON, 4 guards env-OFF | **no** |
| — | `cde2acf` | kevseq 8/16-vs-8/17 reconciliation | doc only |
| — | `5ec278a` | hidden lane SIGNAL grade — detector refuted | doc only |
| — | `b72648f` | ledger: kevseq edge real, drift owned the sign | doc only |
| 1a | `edcb671` | **NOTHING SHIPPED** — burst saturation REFUTED | n/a |
| 1b | `94550d4` | kevseq self-computes `front_side` from 10s bars | shadow-only |
| 2 | `a4ad672` | conversion caps refunded on non-fill paths | **YES — grinder** |
| 3 | `516e123` | scan-loop cycle timing rows | **no** |
| — | `7ccd390` | convene scope doc | doc only |
| — | `6d66b86` | burst kill-test run artifacts | doc only |

Full rig EXECUTED this convening with `SHIP_CHECK=1`: **612 green, one RED — section Q only**
(`HEAD 6d66b86bcfbe not covered by data/audits/LATEST.md`), the designed interlock firing
because this artifact did not yet exist. Sections **FS (12), GC (14), SC (13), AP (25), AN, AO**
all present AND executed in the same run. Post-commit rerun appended at the bottom.

> **Rig-invocation correction (method note).** My first run used `python3 -m pytest`, which
> INTERNALERRORs — the rig is a SCRIPT with `sys.exit(1 if FAILS else 0)` at module scope, and
> the shell reported `tail`'s exit code, not the rig's. Per `feedback_rig_tests_spec_not_impl`
> ("sweeps judge by EXIT CODE"), that first run was VOID and is discarded. Every number in this
> artifact comes from `python3 rig/test_shipset_20260804.py`, exit code read directly.

## VERDICT: GREEN — no blocker. Deploy may proceed on Marcos's word.

No RED found in the code. Four things go to Marcos BEFORE the env is set — one of them is a
money-behaviour default that the shipping commit's own safety argument did not name (§3a).

---

## 1. DEFECT 1a (burst saturation) — REFUTED, NOTHING BUILT, NO DEFAULT TO GRADE

The convening brief anticipated a "burst-saturation commit". There is none. `edcb671` ships
**zero code** — no env knob, no detector change. There is therefore no default to defend and
the "if it defaults ON the evidence must be positive on the hold-out" test does not apply.
The auditor's job here reduces to: was the REFUTED verdict earned? Per
`feedback_skepticism_needs_verification_too` ("before writing REFUTED, name the check and run
it") — **yes**: `burst_saturation_20260817.py`, 2,251 candidates over 736 name-days / 63 dates,
pre-registered failure conditions, executed, output committed (`_out.json`, `_run.txt`).

**Numbers ($/trade, E3 live-parity $500, MINE 5/18–7/21 / HOLD-OUT 7/22–8/14):**

| variant | MINE | HOLD-OUT | MINE (F3) | HOLD (F3) |
|---|---|---|---|---|
| **V0 baseline (trailing p75)** | **−3.54** | **−2.46** | **−0.56** | **−0.73** |
| V1 pre-run p75 | −3.21 | −2.95 | −0.97 | −1.38 |
| V2 OR sess-median ×1.5 / ×2 / ×3 | −4.16 / −4.06 / −3.98 | −4.12 / −3.96 / −3.61 | −3.55 / −3.14 / −2.85 | −3.33 / −3.02 / −2.74 |
| V3 dollar-volume p75 | −3.57 | −3.17 | −0.94 | −1.34 |
| V4 no burst at all | −4.64 | −3.83 | −4.08 | −3.66 |

Zero variants beat baseline on both halves. Every loosening loses money.

**RUNNER-COHORT SPLIT (the brief's explicit ask), F3 limit entry:**

| cohort | V0 N | V0 $/tr | V4 (no burst) N | V4 $/tr |
|---|---|---|---|---|
| ALL | 1257 | −0.49 | 2190 | −3.83 |
| VERTICAL 100%+ | 628 | **+10.00** | 1182 | +2.52 |
| VERTICAL 100%+ / HOLD-OUT | 174 | **+9.34** | 320 | +3.58 |

**Auditor's read: the finding INVERTS the ticket.** Burst is not blocking the runners; burst is
what makes the runner cohort profitable — the strictest variant is the best variant out of
sample on a powered N=174. Loosening it there costs −$5.76/trade.

**Honesty credit, recorded:** the doc reports that the RUNNER(≥25%)/REST split *as specified*
is degenerate — kevseq's own `KEVSEQ_GAIN_MIN=20` floor pre-selects runners, leaving 1 candidate
of 2,251 in REST. It says so plainly and substitutes run-INTENSITY bands (no_burst rate rises
37.2% → 49.7% from the 50-100% band to the 200%+ band) rather than dressing up a dead split.
That is the `feedback_maps_describe_not_serve` standard met on a measurement.

**To Marcos (unresolved, NOT an auditor's call):** kevseq at `KEVSEQ_GAIN_MIN=20` is a
money-loser in aggregate (−$0.73/tr HOLD-OUT); restricted to 100%+ verticals it is **+$9.34/tr
HOLD-OUT on N=174**. Raising the floor is a behaviour change and is priced and waiting.

## 2. DEFECT 1b (front_side computed in-lane) — PINNED, all three tests PASS

Brief's three requirements, each checked against the shipped source:

**(a) CAUSAL — no future bars. PASS.** `kevseq_feed_1m` folds only the ALREADY-FED completed
10s bars (`_nb`) into minute buckets and returns `st["bars"]` — the list of **completed** minute
bars. The in-progress bucket lives in `st["cur"]` and is appended only when a LATER bar advances
the bucket, so it is never read while open. This is the same discipline as the caller path
(`_ks_1m = (bars or [])[:-1]` drops the live minute). No fetch, no lookahead, no reordering.

**(b) FAILS CLOSED ONLY ON GENUINE INSUFFICIENCY. PASS.** `kevseq_front_side` returns
`(None, n)` when `len(b1) < EMA20_PERIOD + 2` — the **identical** 22-bar threshold the caller
uses, so the self path is not a looser door wearing the same name. It also returns None when
`e9`/`e20` are falsy or `e20 <= 0`. `None` propagates as unknown and the detector keeps
refusing. Both helpers are wrapped `except Exception: return []` / `return None, 0` — a
malformed bar degrades to fail-closed, never raises into the scan loop.

**(c) NO BEHAVIOUR CHANGE WHEN ctx ALREADY SUPPLIES front_side. PASS — pinned.** The self value
is computed every call (deliberately, so the aggregate has no holes), but the assignment is
guarded: `if KEVSEQ_SELF_FRONTSIDE and _ks_ctx["front_side"] is None:`. When the caller's 1-min
path succeeded, `front_side` is left exactly as the caller set it. The only additional effect on
that branch is the `kevseq_frontside_disagree` canary row — a log write, no gate. Confirmed:
the caller's `bool(_ks_e9 > _ks_e20 > 0)` and the self path's `e20 > 0` guard + `bool(e9 > e20)`
are logically equivalent, so the canary compares like with like.

Rig FS-a..FS-l, 6 EXECUTED against the extracted block: rising tape → True/33 bars, falling →
False, 10-min tape → None (fail-closed), incremental 7-bar feed ≡ one-shot (idempotent bucket
advance), malformed bar never raises.

**Blast radius:** `_ks_1m_agg` is module-level and in-memory — a restart rebuilds it from live
tape within ~22 minutes, during which the lane fails closed exactly as it does today. Capped at
240 bars/symbol (no unbounded growth). Day-keyed, so it self-clears at the date roll.

## 3. DEFECT 2 (caps refunded on non-fill) — FULL CENSUS DONE; CORRECT, but see §3a

The brief's standard is the right one: *a cap that refunds on some paths but not others is
worse than today's bug.* I enumerated **every** `_slot_refund` call site (23 total, `grep -n`
run this turn) and read the context of each.

**Cap census — every cap touched:**

| lane | ledger | refunds now? | note |
|---|---|---|---|
| v2conv | `_v2_conv_day{"d","n"}` | YES | cap 5 |
| grinder | `_gr_conv_day{"d","n"}` | YES | cap 3 |
| bandpass | `_bp_conv_day{"d","n"}` | YES | cap 3 |
| kevseq | `_ks_st[sym]["leg_n"]` (per-LEG) | YES | cap `KEVSEQ_LEG_MAX=3` |
| prevwap | **none exists** | NO — correct | refunding it would decrement a sibling's counter |
| hidden / rocket / curl-slot (zf,vr,dr) | pre-existing | already correct | 7/29 |
| LEADER_IGNITION_CAP | — | unchanged | the 7/29 note's own named out-of-scope hole |

**Every non-fill exit fires the refund — verified site by site.** All 23 sites are pre-fill or
no-fill. Enumerated: `backside_reject` (:9467, pre-worker — the rejected breakout is never
appended to `_kept_bs`, so it cannot double-refund downstream), `premarket_shadow_entry` (:12646,
the site that ate today's cap), `entries_paused`, `chart_gate_blocked_trade`, `wide_stop_reject`,
`bad_stop_skip`, `minstop_reject`, `runway_reject`, `breakside_reject`, `mapless_reject`,
`retest_band_reject`, `standdown_active`, `ceiling_reject`, `prebreak_reject`,
`stop_coherence_refused`, `no_capital_skip`, `balance_skip`, `spread_reject`, `l2_reject`,
`momentum_reject`, `retest_expired`, `pre_capped_at_exec`, `order_failed`.

**The decisive check — no site fires after a fill.** The last refund (:13309) is inside
`if not order_id:` immediately after `execute_trade`; there is no `_slot_refund` call anywhere
below it. So the previously-no-op lanes cannot now over-refund a ticket a real trade spent.
This is the `#34` conservation invariant preserved, not merely asserted: mirror-checked against
the existing hidden/zf/vr arms, which sit on the identical set of sites.

**Over-refund is structurally impossible.** Day ledgers decrement only under
`_ledger.get("d") == day and _ledger.get("n",0) > 0`; the kevseq leg only under
`_kst.get("day") == day and _kst.get("leg_n",0) > 0`. Both floor at zero. Rig GC-k executes this
as failure-condition #1.

**Dead-code trap checked and CLEARED.** The kevseq branch guards on `_kst.get("day") == day`. I
verified `_ks_st[sym]` is actually initialised with a `"day"` key (`marcos_trading_bot.py:6552`,
read this turn). Had it not been, the kevseq refund would have been silently dead — the exact
"refunds on some paths but not others" failure the brief warned about. It is live.

Rig GC-a..GC-n, 7 EXECUTED against the real `_slot_refund` body: correct ledger per lane, floors
at 0, prevwap touches nothing, kill switch restores exactly, unknown symbol is a no-op.

### 3a. ⚠️ TO MARCOS — DEFECT 2 IS A MONEY-BEHAVIOUR CHANGE FOR `grinder`, TODAY, BY DEFAULT

The commit's safety argument is: *"this closes a hole in ALREADY-APPROVED behaviour rather than
inventing rationing policy"*, and it defends the 1b default by noting kevseq is a shadow lane.
**That argument does not cover grinder.** Read this turn:

- `GRINDER_CONVERT = os.environ.get("GRINDER_CONVERT", "1") == "1"` — **defaults ON** (:5993)
- `GRINDER_DAILY_CAP = 3` (:5994)
- v2conv (:6135), bandpass (:6327), prevwap (:6330), kevseq (:6430) all default CONVERT=**0**

So on deploy, with code defaults, **grinder can fill up to 3 actual TRADES per day instead of
being cut off after 3 TRIGGERS.** That is more real orders than yesterday. It is the direct,
intended consequence of Marcos's own 7/29 instruction ("a session slot is spent by a TRADE, not
an ATTEMPT") and I believe it is what he wants — but per
`feedback_auditor_cannot_authorize_behavior` ("any fix that changes what the bot DOES with money
goes back to Marcos priced"), **an auditor cannot wave this through on the commit's framing.**
It is named here so the decision is his and explicit. One-character revert: `V2_CAP_ON_FILLS=0`.

- **`V2_CONVERT` / `KEVSEQ_CONVERT` in the LIVE Railway env: `[UNVERIFIED]`.** `SCREENER_URL` is
  env-only (:102), there is no local `.env`, and this convening is forbidden env operations. Per
  `feedback_dropdead_verify_before_speak` I will not assert the live values. **If `V2_CONVERT=1`
  or `KEVSEQ_CONVERT=1` live, those lanes join grinder as money-changing and 1b becomes a
  money-changing default too** — the 1b commit flags this itself. Marcos should read the boot
  banner (it now prints `CAP_ON_FILLS=` and `KEVSEQ_SELF_FRONTSIDE=`) or the Railway env before
  setting anything.

### 3b. Non-blocking defect found (cosmetic while KEVSEQ_CONVERT=0)

The kevseq refund decrements `_ks_st[sym]["leg_n"]` for the CURRENT leg. If the leg advanced
between the fire and the downstream reject (`st["leg"] += 1; st["leg_n"] = 0`), the refund lands
on the NEW leg's counter, granting it one extra fire it did not earn. Bounded at 1, and inert
while kevseq does not convert. A leg-id stamp on the refund would close it. Logged, not fixed —
fixing it mid-session is out of an auditor's authority.

## 4. DEFECT 3 — MEASUREMENT ONLY. CONFIRMED. No behaviour changed.

Read the whole diff. Three helpers (`_cyc_name` / `_cyc_mark` / `_cyc_emit`), one dict literal at
the top of the loop, five call sites, one `_log_decision` row per cycle. **Nothing is moved,
capped, reordered, parallelised, skipped, or short-circuited.** Verified specifically:

- No executor / thread pool / `concurrent.futures` introduced (rig SC-f pins the absence).
- `CURL_FIRE_MAX_AGE_SECS` / PRE tolerances **unchanged** (rig SC-g) — no stale fire was
  quietly converted into a trade, which is the way a "measurement only" ship usually cheats.
- `VWAP_BAR_CACHE_SECS` sleep unchanged; the roster is not capped.
- All three helpers return immediately on `not SCAN_CYCLE_TIMING`, and every body is wrapped in
  `try/except: pass` — the instrumentation cannot kill the loop (rig SC-m executes garbage/None).
- `_cyc_name(cyc, None, None)` inside `_cyc_mark` closes the open name; `_cyc_emit` filters the
  `None` key out of `slowest` (`if s`). No `None`-key leak into the row.

The honest verdict in the commit — that the real fix is a bounded executor fan-out and that it is
NOT being shipped on a live-money week with a position open — is the right call and is exactly
what the brief asked for.

**Minor, flagged:** the row is written under the pseudo-ticker `_scan_cycle`. Same class as the
existing `SYSTEM` row; Dashboard Curator should confirm `by_status` consumers skip
underscore-prefixed tickers (the leader rehydrate already does: `if sym.startswith("_"): continue`).

## 5. DEFAULTS TABLE — every new env in the batch (read from source this turn)

| env | default | money? | restores today at |
|---|---|---|---|
| `KEVSEQ_LIMIT_ENTRY` | **0 / OFF** | — | already off |
| `KEVSEQ_ENTRY_TOL` | 0.005 | — | inert while LIMIT_ENTRY=0 |
| `KEVSEQ_MAX_DRIFT` | **0 = disabled** | — | already off |
| `KEVSEQ_FIRE_MAX_AGE_S` | **0 = disabled** | — | already off |
| `KEVSEQ_SELF_FRONTSIDE` | 1 / ON | shadow-only¹ | `=0` |
| `V2_CAP_ON_FILLS` | 1 / ON | **YES — grinder** | `=0` |
| `SCAN_CYCLE_TIMING` | 1 / ON | no (observe-only) | `=0` |

¹ shadow-only **iff** `KEVSEQ_CONVERT=0` in the live env — `[UNVERIFIED]`, see §3a.

**§5 confirms the brief's item 5: all four `07f0c6c` entry-drift switches default OFF/0.** That
commit changes **no** entry behaviour on deploy; its stamps (`fire_age_s`, `drift_pct`,
`quote_px`, `bar_lo`, `intended_risk_pct`, `actual_risk_pct`) are observe-only, and `kevseq_step`
gained only ADDITIVE return keys (`bar_lo`/`bar_hi`) — no existing key changed shape.

## 6. ⭐ THE MONEY STATEMENT + THE NIVF-RESUME SAFETY ANSWER

### 6a. What actually changes when this deploys

**Entry behaviour that CHANGES (real orders can differ):**
1. **`grinder` cap accounting** — a grinder trigger that dies at any downstream gate now gives
   its ticket back, so up to 3 grinder *trades* per day instead of 3 grinder *triggers*.
   **This is the only certain money change in the batch.** (§3a)
2. Conditional, `[UNVERIFIED]`: the same for `v2conv` / `bandpass` / `kevseq` **iff** their
   `*_CONVERT` env is 1 in live Railway. Code defaults say no.

**Observe-only — changes rows written, never a trade:**
- All entry-drift stamps + the four env-OFF guards (`07f0c6c`).
- `front_side` self-compute (`94550d4`) — shadow lane; converts ~50 refusals/day of STRENGTH
  into evidence rows for the bias ledger. Zero money while `KEVSEQ_CONVERT=0`.
- `scan_cycle_timing` + `kevseq_frontside_disagree` + widened `slot_refunded` rows.
- 1a: nothing at all.

### 6b. NIVF-RESUME SAFETY — the answer is NO, and it is PROVEN, not assumed

**Does anything in this batch touch `monitor_trade`, exits, stop handling, or the resume path?
NO. Nothing. Proven by hunk-range vs. function-boundary arithmetic, both run this turn.**

Every hunk in `marcos_trading_bot.py` across `4cc24ea..HEAD` (`git diff -U0 | grep '^@@'`) lands
in exactly four neighbourhoods: the `_bucket_fresh` module scope (~5077), `_slot_refund` (5605),
module-level env constants (6138/6444/6476), `kevseq_step` (6600), `wait_for_flat_top_entry`
(7963–9543), and `main()` (12292–12646). The diff jumps **9543 → 12292** with nothing in between.

Function boundaries (`grep -n "^def "`, run this turn) inside that gap:

| function | lines | in any hunk? |
|---|---|---|
| `_recover_orphaned_trades` | 2954 | **NO** (first hunk is 5077) |
| `_manual_close_pending/_match/_ack` | 5333–5400 | **NO** |
| `execute_trade` | 9647 | **NO** |
| `close_position` | 9722 | **NO** |
| `cancel_order` / `place_stop_order` | 9737 / 9759 | **NO** |
| `place_limit_sell` / `_place_sell_ladder` / `_cancel_sell_ladder` | 9784–9854 | **NO** |
| `update_stop_order` | 9855 | **NO** |
| `_exit_layer` | 10230 | **NO** |
| `_e3_eval` | 10532 | **NO** |
| **`monitor_trade`** | **10546–11396** | **NO** |
| **`resume_monitoring_if_open`** | **12013–12110** | **NO** |
| `get_open_position` | 11963 | **NO** |
| `_safety_close` (inside monitor_trade) | 10700 | **NO** |

**Conclusion for the live position:** the restart will resume NIVF through
`resume_monitoring_if_open` → `monitor_trade`, and **every line of that path is byte-identical to
the code currently running.** The stop, the E3 trail, the 15:45 flatten, the manual-close hook,
the `#53` `_safety_close` choke point, the ladder cancel, and the orphan recovery are all
untouched. The batch's entire surface is the *scan/entry* side; NIVF is on the *monitor/exit*
side. The one residual restart risk is the one that already existed and is unchanged: the
`_recover_orphaned_trades` force-close semantics (7/29 STFS/YYGH lesson) if the position is not
cleanly matched at boot — a pre-existing property Marcos has accepted, not something this batch
introduces.

Caveat stated honestly: this is a *static* proof that the resume code is unchanged. It is not a
live restart drill. Given market-open time pressure and the standing no-RTH-push law, a static
proof is the correct and available instrument.

## 7. Doctrine-inversion sweep

- **`feedback_auditor_cannot_authorize_behavior` — TENSION, SURFACED, NOT RESOLVED HERE.**
  DEFECT 2 changes what the bot does with money (grinder), and the shipping commit's safety
  argument did not name grinder. Held only because "a slot is spent by a TRADE, not an ATTEMPT"
  is Marcos's own 7/29 instruction. Escalated in §3a with a one-character revert. **This is the
  live doctrine tension of the batch.**
- **`feedback_skepticism_needs_verification_too` — HELD.** 1a is a REFUTED verdict and it owed a
  named, executed check. It has one: 2,251 candidates, pre-registered failure conditions, OOS
  split, output committed. No assertion-only refutation.
- **`feedback_edge_over_mechanisms` — HELD, not inverted.** These are plumbing fixes, but 1a was
  graded on expectancy and refused on it, and the session's headline (kevseq's edge is
  cohort-bound to 100%+ verticals, +$9.34/tr HOLD-OUT N=174) is an EDGE result, not a mechanism
  claim.
- **`feedback_no_lesser_fix` — HELD UNDER PERMISSION.** DEFECT 3 ships instrumentation while a
  fuller fix (executor fan-out) is describable. The brief explicitly ordered measurement over a
  mid-week refactor. Flagged so it stays a choice, not a drift.
- **`feedback_dollars_not_r` — HELD.** Every number in §1 is $/trade through the E3 live-parity
  $500 sizing chain, with WFF hand-traced in the drift doc ($3.91 fire → $5.039 entry, intended
  risk 5.9% → actual 27.0%).
- **`feedback_maps_describe_not_serve` — HELD, notably.** The runner split came back degenerate
  and was reported as degenerate rather than reshaped into a flattering cut.
- **`feedback_rig_tests_spec_not_impl` — ENFORCED against myself.** See the rig-invocation
  correction above; the pytest run was void and discarded.
- **`feedback_flat_book_verified_in_turn` — WAIVED BY MARCOS, RECORDED.** A position (NIVF) is
  open and he waived the gate explicitly. The waiver is his; §6b is the compensating control.
- **`feedback_no_rth_push` — STILL GOVERNS THE SHIP.** Market is open. An auditor does not
  authorise an RTH push; that is Marcos's standing call and he has made it.
- **AMENDED RIG PINS — legitimacy checked, not green-washed.** `AG-vii` was rewritten by
  `07f0c6c` (the conversion-guard literal now carries `not _ks_veto`). Same standard as the
  AF-l/AG-x/AH-x amendments in batch 3: the prior assertion encoded the pre-fix literal, so
  preserving it would have pinned the defect. The rewrite is legitimate. New sections FS/GC/SC
  are additive and 19 of their 39 checks EXECUTE against extracted source rather than
  string-matching it.

## 8. ROLL CALL — all 31 offices (ROSTER.txt), everyone present

- **Blast Radius Auditor** — this artifact. GREEN, one money default escalated (§3a).
- **Execution Surgeon** — planned-R = realized-R is this batch's charter case; the drift stamps
  are his instrument. **OWED before any real-money kevseq run:** a lane-aware
  `ENTRY_LIMIT_BUFFER` — the executor places a marketable limit at `entry × 1.01` (:615, :9399),
  and the kill-test says +1.0% tolerance COLLAPSES F3 (−$2.96/tr). DRY_RUN matches the test;
  real money does not.
- **Systems Quant** — `drift_pct` and `kevseq_front_side` compute what their names claim
  (§2, §4); the `kevseq_frontside_disagree` canary is the standing check.
- **Statistician** — the 1a numbers (2,251 candidates, OOS, runner cohort) and the −$64.25 lane
  registry counterfactual owe RESULTS_LEDGER lines, not just killtest files. Manual exits must
  stay out of lane expectancy.
- **Strength Ombudsman** — 1b converts ~50 refusals/day of STRENGTH into evidence rows: the
  bias ledger's best week of new data. The refused-strength hearing should re-run once the
  `front_side_src` distribution exists.
- **Hidden Entry Architect / Seam Scientist** — inherit the 1a cohort result (edge lives ONLY in
  the 100%+ vertical regime); the v2 rebuild should not rediscover it. Note `5ec278a` refutes the
  hidden DETECTOR, not just the body.
- **Pit Crew Chief** — 3 new switches this batch, all restore today's behaviour at `=0`; all new
  state (`_ks_1m_agg`, refunded ledgers, `_cyc`) is in-memory and rebuilds within one cycle.
- **Dashboard Curator** — three row types need a display: `kevseq_frontside_disagree`, widened
  `slot_refunded`, `scan_cycle_timing`. Confirm `_scan_cycle` is skipped by `by_status` (§4).
- **First Hour / Opening Bell** — the cap ghost (25 of 39 refusals in the 09:00/10:00 hours) and
  the cycle tail both bite hardest 09:30–10:30; both now have rows. Split tomorrow's attribution.
- **Feed Engineer + Webull Broker Desk** — DEFECT 3's diagnosis is a vendor round-trip budget
  problem (4–5 blocking REST trips/name/cycle); the vendor ledger owns the per-call latency the
  executor design will need. The $5 place+cancel test remains owed.
- **Trade Manager** — exits untouched (§6b); the "manual" exit layer from batch 3 is unchanged.
- **Historian** — 8/17 is the day the ranking was cleared and the trigger-to-fill pipeline was
  charged: 39 triggers, ZERO fills, on the seven top-ranked runners.
- **Integrator** — parallel-logic registry: `_slot_refund` is now the single refund choke point
  for 8 lanes; prevwap remains deliberately outside it.
- **Momentum Operator, Tape Veteran, Reclaim Architect, Handicapper, Rocket Rider, Cartographer,
  Wind Tunnel Engineer, Convexity Trader, Curl Mechanic, Side Marshal, Crown Steward,
  Quartermaster, Kev Librarian, Forward Architect, Project Manager** — **CLEAN**: no map, corpus,
  warehouse, crown, side, sizing, or backtest-fidelity surface is touched by this batch. Named so
  no office is denied its say.

## 9. Items for Marcos BEFORE the env is set

1. **`V2_CAP_ON_FILLS=1` makes grinder trade more.** Approve or set `=0`. (§3a)
2. **Read the live `V2_CONVERT` / `KEVSEQ_CONVERT`** — if either is 1, more lanes change and 1b
   becomes money-changing. `[UNVERIFIED]` from here.
3. **kevseq's day-gain floor** — 20% is a loser, 100%+ is +$9.34/tr HOLD-OUT (N=174). Priced,
   waiting.
4. **`ENTRY_LIMIT_BUFFER` is owed** before any real-money kevseq run (Execution Surgeon, §8).

---

## POST-COMMIT RIG RERUN (as promised above)

`SHIP_CHECK=1 python3 rig/test_shipset_20260804.py` after this artifact was committed:

```
Q) 8/12 CONVENE-OR-DON'T-SHIP interlock
  ✅ ship-check: HEAD 0fe8528d8e79 audited + tree clean

ALL GREEN
```

**613 green, 0 red, exit code 0.** Section Q is green. The interlock is satisfied.
