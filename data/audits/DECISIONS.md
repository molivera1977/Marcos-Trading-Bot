# DECISIONS REGISTRY — settled rulings as MACHINE-CHECKABLE expectations

**GATE 7, built 8/17.** A settled ruling that lives only in prose drifts silently. Every row
here is a decision Marcos actually settled, restated as a state the code or the live config
must be in, plus the exact command that proves it. `data/audits/reconcile_decisions.py` runs
every command nightly and names the DRIFTED rows.

Seeded from the ones that **actually drifted** — each of these was settled, then quietly
stopped being true, and the drift was discovered by accident (mostly on 8/17) rather than by a
check. That is the whole point: these are not hypothetical.

## Format

    | id | decision | expected state | check |

* `id` — stable slug. Never reuse, never renumber.
* `check` — a shell command run from the repo root. **Exit 0 = HOLDS. Non-zero = DRIFTED.**
  Backticks around the command; pipes and `test` are fine. Keep it read-only.
* A check that cannot reach its evidence (network down, service asleep) must exit **3**, which
  the reconciler reports as `UNKNOWN` rather than silently passing or falsely alarming.

## Rows

| id | decision | expected state | check |
|---|---|---|---|
| `our_numbers_primacy_0812` | 8/12 (reaffirmed 8/17): Kev's picks, OUR map numbers ruling — but the gates must actually READ `kev_shadow`. It was written to the store on 8/12 and read NOWHERE until 8/17; WETO's $20 target sat invisible while the runway refused the trade on a stale vision ceiling. | `_kev_shadow_overlay` exists AND is applied on BOTH `_freshest_rec` return paths (>=3 mentions: the def plus two returns). | `test $(grep -c '_kev_shadow_overlay' marcos_trading_bot.py) -ge 3` |
| `live_structure_chart_exempt_0724` | 7/24 (Marcos: "switch the reclaim and zone flip"): live-structure/tape lanes trade live 10s structure, so the chart-break gate must not veto them. The bypass list was a COPY-PASTED tuple, went stale, and killed WFF at $5.04 on a name that ran to $6.00 — kevseq was simply absent from it. | The bypass set is DERIVED from the lane registry, not hardcoded, and the registry is on by default. | `grep -q 'def _chart_bypass_lanes' marcos_trading_bot.py && grep -q 'LANE_REGISTRY_EXEMPT", "1"' marcos_trading_bot.py` |
| `refuted_scalars_no_veto_0726` | 7/26: every setup-quality scalar (room, day-gain, momentum, extension) was REFUTED; do-not-trade blocks CHART lanes only — tape lanes trade through by design. Violated 8/17: the momentum scalar vetoed kevseq's WETO entry one second after chart_gate_allow. | The tape-lane scalar exemption is present and defaults ON, and the momentum exempt set is derived from the registry rather than a second hardcoded list. | `grep -q 'TAPE_LANE_SCALAR_EXEMPT", "1"' marcos_trading_bot.py && grep -q 'def _momentum_exempt_lanes' marcos_trading_bot.py` |
| `reread_on_stale_reject_57` | Task #57 — reread-on-stale-reject. Approved, then sat in the queue unshipped while stale maps drove the 8/17 runway refusals; "shipped" was asserted before it was true. | `REREAD_ON_REJECT` exists and defaults to on. | `grep -q 'REREAD_ON_REJECT", "1"' marcos_trading_bot.py` |
| `pre_entries_live_0700` | 8/10: PRE entries are LIVE 07:00–09:25 ET with a 09:25 flatten (superseding the 7/27 premarket blackout). The PRE session must be a real entry window, not a shadow. | The PRE conversion path exists (a lane can append a `session="PRE"` breakout) and the 09:25 flatten is documented in the same mechanism. | `grep -q '"session": "PRE"' marcos_trading_bot.py && grep -q '09:25' marcos_trading_bot.py` |
| `e3_exits_live` | E3 exits (bank 1/2 at +10%, trail the rest 10% off the run high) are the proving-week exit config — the +$134-median exit edge is measured with them on. | `E3_EXITS` defaults to on. | `grep -q 'E3_EXITS", "1"' marcos_trading_bot.py` |
| `bell_boundary_handoff_0817` | 8/17: at 09:30:00 the session set flipped to RTH-only while zero completed RTH bars existed, blinding 23 of 26 names for the first five minutes. PRE tape must stay visible across the bell. | `RTH_HANDOFF_MIN` exists with a non-zero default and `_live_sessions` returns `["PRE","RTH"]` inside the handoff. | `grep -q 'RTH_HANDOFF_MIN", "5"' marcos_trading_bot.py && grep -q 'bell-boundary hand-off' marcos_trading_bot.py` |
| `cap_spent_by_trade_not_attempt` | 7/29 (Marcos: "a session slot is spent by a TRADE, not an ATTEMPT"), extended 8/17 to the conversion lanes after five non-fill triggers ate the entire V2 daily cap by 04:35 AM. | `V2_CAP_ON_FILLS` defaults to on and the conversion lanes route through `_slot_refund`. | `grep -q 'V2_CAP_ON_FILLS", "1"' marcos_trading_bot.py && grep -q '"v2conv", "grinder", "bandpass"' marcos_trading_bot.py` |
| `scalar_exempt_affirmed_0818` | 8/18, Marcos reviewed the tape-lane scalar exemption on MEASURED scope and affirmed it stays ON. Scope measured across 14 sessions: 95 `momentum_reject` rows, of which only SEVEN carry the "no momentum build" reason the exemption bypasses (PFSA, WETO, MSGY, LZMH, ZCMD, SCYX, FCHL) — 88 of 95 refusals keep their veto. Already live in production since 8/17 12:01 (the WFF `scalar_veto_bypassed` row), so leaving it on is the status quo and turning it off would have been the change. Affirmed because turning it off destroys the only gradable population: OFF yields refusals with no outcome, ON yields the trade plus a counterfactual row. The +$25.14 N=1 kill-test is NOT the basis and must never be cited as evidence. | The exemption defaults ON, still bypasses ONLY the "no momentum build" scalar (liquidity/ambient/topping-tail keep their veto), logs a counterfactual row on every bypass, and refusal rows name their lane so it stays gradable. | `grep -q 'TAPE_LANE_SCALAR_EXEMPT", "1"' marcos_trading_bot.py && grep -q 'startswith("no momentum build")' marcos_trading_bot.py && grep -q '"scalar_veto_bypassed"' marcos_trading_bot.py && python3 rig/test_refusal_attribution_20260818.py >/dev/null 2>&1` |
| `dry_run_proving_week` | THE PROVING WEEK (8/17–8/21): the machine runs in DRY_RUN. No real money moves until the Friday go/no-go. This is the one row whose truth lives in the DEPLOYED env, not the source. | The live bot's boot config reports `dry_run` true. | `python3 data/audits/reconcile_decisions.py --probe-live dry_run` |

## Adding a row

Only for rulings **Marcos actually settled**. Write the check FIRST and watch it fail against a
tree where the decision is violated — a check that has never been seen to fail is decoration.
Never edit a row's meaning in place; add a new row and mark the old one superseded, so the
record of what drifted survives.
