# LIVE-CODE STUDY HARNESS + TODAY-PARITY PROOF — 2026-08-17

**Order:** Marcos, 8/17. Offline research infrastructure only. Nothing here deploys, pushes,
changes env, or restarts anything; the trading bot's runtime behaviour is **unchanged** and
`marcos_trading_bot.py` was **not modified** (see §6).

**Artifacts**
- `data/killtests/live_harness.py` — the harness
- `data/killtests/harness_parity_20260817.py` — the parity script
- `data/killtests/harness_parity_20260817_out.json` / `_run.txt` — its output
- rig section **BH** in `rig/test_shipset_20260804.py`

---

## 1. The defect this exists to kill

Every kill-test so far **re-implemented** the lane detectors instead of calling the bot's.
Replicas drift, and always in the flattering direction:

- `kevseq_frontside_tf_20260817.md` proved `entry_drift_20260817`,
  `burst_saturation_20260817`, `kevseq_floor_sweep_20260817` and
  `kevseq_reconciliation_20260817` applied **no front-side clause at all**, while the live
  kevseq lane requires it. Four studies grading a machine that is not ours.
- Same species: the fill-model drift (studies entered at the signal price; live entered
  5–60% higher) and the fictional-fill accounting.

The harness makes **study == live by construction**: it runs the bot's *own function
objects* over historical 10s bars.

## 2. How it loads bot code without touching the live path

`import marcos_trading_bot` is forbidden — module import executes env reads, broker/Alpaca
client construction, thread starts and file writes. Instead the harness **parses the bot
source with `ast`**, transitively resolves the requested `def`/constant nodes plus their
module-level dependencies, compiles only those nodes, and `exec`s them into a private dict
(the technique the rig already uses in sections AB/AH/AL/M1W).

Safety properties, all machine-enforced:

| property | mechanism |
|---|---|
| no side effects | only the named nodes are compiled; `def`s do not run at exec time |
| no network | `requests` in the namespace is a **poisoned stub** — any call raises `HarnessError` |
| no broker SDK | `ApiClient` / `WebullDataClient` / `WEBULL_SDK_AVAILABLE` provided **inert** |
| replay clock | `datetime.now()` is frozen to the replay day (the detectors use it only for their per-day state key); `fromtimestamp` is untouched, so the bar-clock logic is real |
| drift = build break | an unresolvable symbol raises `NotIsolable` and rig BH goes red — drift can no longer be silent |

**One-way dependency:** harness reads the bot's source. The bot never imports the harness.
Rig BH pins that (no `live_harness` token anywhere in `marcos_trading_bot.py`).

## 3. Isolable vs not

### Lifted verbatim (24 symbols, all green — `python3 data/killtests/live_harness.py`)

`kevseq_step` · `kevseq_feed_1m` · `kevseq_front_side` · `grinder_shadow_step` ·
`bandpass_step` (RTH **and** PRE lanes) · `v2_pullback_step` · `v2_trailing_calm` ·
`hidden_entry_step` · `ignition_10s_step` · `detect_ignition` · `_seq_events` ·
`_wallclock_window` · `_scaled_risk` · `aggregate_bars` · `calculate_ema9/20/90` ·
`_bar_high/_bar_low/_bar_open/_bar_close/_bar_vol` · `check_momentum` (injectable) ·
plus the per-name machine-state dicts and the sizing constants.

### Blocked, with the concrete blocker

| symbol | blocker |
|---|---|
| **flat_top / break-attack** | **Not a function.** The consolidation tracker + `FLATTOP_BREAK_ATTACK` conversion live *inside* `wait_for_flat_top_entry` (~1k lines), driven by a `WebullStream`, a session cache and rescan callbacks. Lifting it would mean faking the stream — i.e. building exactly the replica this harness exists to prevent. **Left un-lifted on purpose.** |
| **`_marked_runway`** | Live state + network: `_effective_map(ticker)` reads the running level-map store; `_curl_feed(ticker)` hits the recorder feed for the wall high. Replayable only with a recorded map snapshot, which the archive does not carry. |
| **`kev_zoneflip_step`** | Wall clock + live store: `_bucket_fresh(k)` compares the bucket to `time.time()` (every historical bar is "stale", so the fire path is unreachable), and `_zf_pm_floor(sym)` reads the premarket-zone store. |
| **`hidden` lane fires** | Detector lifts and **arms** correctly, but `_bucket_fresh` eats **100%** of replay fires (verified on IVF 8/17 — 78 suppressions, 0 fires). `replay()` refuses the lane unless `allow_blocked=True`, and its fire counts must never be reported as live-comparable. |
| **`check_momentum`** | **INJECTABLE, not free-running.** Body is pure; the input is a live fetch. Use `check_momentum_on(ticker, m1_bars)`. Bound: it routes through `_fresh_session()` (today-only), so past-day replays hit its insufficient-data path, not a real read. Disclosed, never defaulted. |
| **sizing chain (full)** | **PARTIAL.** `_scaled_risk` is the **real** function and the constants (`RISK_PER_TRADE`, `RISK_PROP`, `RISK_PROP_REF`, `MAX_TRADE_DOLLARS`, `MAX_POSITION_SIZE`, `MAX_POS_VOL_PCT`, `SIM_ACCOUNT_BALANCE`) are the **real** constants. The clamp arithmetic (risk-shares vs notional-shares, VWAP-side halving, volume cap) is **mirrored**, because it is inline in `execute_trade`'s body and its volume cap re-fetches 1-min bars. Rig BH pins the mirrored lines against the bot's own source, so a bot-side change breaks the build. |

## 4. THE CONTEXT CONTRACT

Each lane declares required ctx keys. The harness **refuses to run** a detector whose ctx is
missing a key, naming the field:

```
MissingContext: lane 'kevseq': missing ctx field(s) ['front_side'] (supplied: ['blue_sky',
'day_gain','top3']). A value of None is allowed and means 'unknown'; ABSENCE is not.
```

- `kevseq` requires **`front_side`, `day_gain`, `top3`, `blue_sky`** — the exact hole that
  made four studies front-side-free.
- Every VWAP-gated lane (`kevseq`/`grinder`/`bandpass`/`prevwap`/`v2`/`hidden`) requires a
  **`vwap_provider`**; omitting it raises rather than passing 0.
- `None` is a legal *value* (kevseq reads `front_side=None` as "unknown → refuse"). Absence
  of the *key* is never legal. Deliberate unknown ≠ silent default.

## 5. TODAY-PARITY (the number that matters)

Live rows: `exit_params_our_fires_20260817_arch.json` (the day's decisions archive, 15,253
rows). Tape: `bars10s_0817_full/` (SIP 10s, whole day). Cadence: `batch_secs=60` (the live
60s rescan — every detector returns at most one fire per call, so bar-by-bar would
over-produce). Match = **exact price AND exact stop (4dp) AND |Δt| ≤ 300 s**.

| lane | live fires | harness fires | exact | rate | harness extra |
|---|---|---|---|---|---|
| prevwap | 3 | 3 | **3** | **100.0%** | 0 |
| v2 | 164 | 124 | 84 | 51.2% | 40 |
| bandpass | 9 | 5 | 4 | 44.4% | 1 |
| kevseq | 23 | 11 | 7 | 30.4% | 4 |
| grinder | 66 | 19 | 6 | 9.1% | 13 |

**Honest reading — reported, not tuned.**

**(a) The detector code is right.** Matching a live fire requires the price *and* the stop
to agree to 4 decimal places on the same name within 5 minutes. prevwap 3/3 and v2 84/164
are not reachable by coincidence. Nothing was tuned to raise a number.

**(b) The residual is INPUT fidelity, not detector fidelity.** Three measured causes:

1. **Different tape.** Live detectors eat `_curl_feed` (recorder 10s buckets, cursor-driven,
   `n=90` on warm passes / deep on rehydrate); the harness eats the complete SIP day. On
   thin names the two disagree bar-for-bar, so `session_hi`, `w30`/`w15` windows, burst
   percentiles and `lo15` stops differ. Worked example: live grinder fired RBNE 11:06:49 at
   px 2.78 / stop 2.76; SIP's 11:06:50 bucket closes 2.75 — the live fire is a bucket the
   SIP grid does not carry at that timestamp.
2. **The vwap scalar.** Live passes **one** `_vr_sv` scalar per rescan (recorder tick-VWAP
   when sane, else the bar line) applied to the whole batch. The harness supplies a per-bar
   line (live-stamped forward-filled where the archive has it, else running SIP VWAP). This
   is the largest single risk on every vwap-gated lane and is why grinder/bandpass suffer
   more than kevseq.
3. **Duplicate live fires.** The archive contains repeated identical fires the harness
   cannot and should not reproduce: grinder 66 rows → **53** distinct `(ticker, px, stop)`,
   with RBNE `(2.78, 2.76)` logged **5×** (11:06, 11:14, 12:01, 13:50, 13:59) and GNPX 4×;
   v2 164 → 143 distinct; bandpass 9 → 8. **This is a live-side finding the harness
   surfaced**, not a harness defect — a mechanism is re-feeding already-consumed buckets.
   *(Owner: Integrator / Feed Engineer. Filed to the convene queue, observe-only.)*

Ruled out by experiment (so nobody re-litigates):
- **Timing is not the problem.** Widening the match window to the whole day moves the
  numbers by ≤ 5 points (kevseq 7→8, v2 84→89, grinder 6→7). The disagreements are on
  price/stop *values*, not on when.
- **Feed-start window is not the problem.** Restarting grinder's tape at the name's first
  archive row, at 09:30, or at 10:30 moves harness fire counts (19 → 23 → 44) but leaves
  exact matches flat at 6–7. Fire *count* can be dialled; fire *identity* cannot — which is
  precisely the evidence that the input tape, not the detector, is the gap.

**(c) What would close it.** The archive does not record the bars the bot actually fed.
Stamping the fed bucket epoch (`k`) on every shadow-fire row — grinder/bandpass/v2/kevseq
already have `k` inside the detector's return dict, it is simply not logged — would let the
harness replay the *exact* fed stream and turn this into a true equivalence test. That is a
**logging** change to an approved behaviour (observe-only, no money decision), so it is
proposed here and queued, not shipped in this ship
(`feedback_auditor_cannot_authorize_behavior`).

**(d) The standing rule.** Until the fed-bar stamp exists, a study using this harness must
report **harness-vs-live parity for the lane it is studying** alongside its result. A lane
at 100% (prevwap) carries a much stronger claim than a lane at 9% (grinder). Hand-rolling a
detector is no longer an option in either case.

## 6. What was touched in the trading bot

**Nothing.** `marcos_trading_bot.py` is byte-identical (`git diff --stat` shows no entry for
it in this ship). The AST loader made a bot-side change unnecessary — that was the whole
point of choosing it over "make the function importable".

## 7. HOW TO WRITE A STUDY WITH THIS (no more excuses)

```python
import sys; sys.path.insert(0, "data/killtests")
import live_harness as H
import json

raw = json.load(open("data/killtests/bars10s_0817_full/IVF.json"))
vwap_line = H.running_vwap(raw)          # or your own per-bar line

fires = H.replay(
    "IVF", raw, ["kevseq"],
    day="2026-08-17",
    batch_secs=60,                        # the live 60s rescan cadence
    vwap_provider=lambda s, i, b, ln: vwap_line[i],
    ctx_provider=lambda s, i, b, ln: {    # EVERY key, deliberately
        "front_side": my_front_side(s, i),   # None == "unknown" -> detector refuses
        "day_gain":   my_day_gain(s, i),
        "top3":       my_top3(s, i),
        "blue_sky":   my_blue_sky(s, i),
    },
)
# fires carry the live decision-row fields: px, would_stop, seq_str, burst, burst_ratio,
# leg, leg_n, fresh_touch_n, session_hi, b_level, ok/why  + harness stamps (lane, sym, i,
# bar, vwap, ctx).

size = H.sizing_chain(entry_price=fires[0]["px"], stop_loss=fires[0]["would_stop"],
                      vwap=fires[0]["vwap"])   # dollars, real _scaled_risk
```

Rules for a study author:

1. **Never hand-roll a detector.** If you need one that is not exposed, add it to
   `ALL_SYMBOLS` — or, if it is in the blocked table, say so in your doc and bound the claim.
2. **Call `H.reset_state(lane, sym)` between name-days.** `replay()` does it by default;
   custom loops must do it explicitly. Stale module state is a silent parity killer.
3. **Supply every ctx key deliberately.** If you do not know a field, pass `None` and say so
   in the doc. Do not invent a value to make the lane fire.
4. **Use `batch_secs=60`** for anything compared to live. Bar-by-bar over-produces fires.
5. **Report parity for your lane** (§5) next to your result.
6. **Dollars, not R** — run every ticket through `H.sizing_chain()` and trace one named
   trade end-to-end (`feedback_dollars_not_r`).

---

*Officers touched: Systems Quant (does the code compute what its name claims — the whole
premise), Wind Tunnel Engineer (backtest fidelity — §5b is his docket), Integrator (the
duplicate-fire finding, §5b-3), Blast Radius Auditor (one-way dependency pin, rig BH),
Statistician (parity numbers ledgered here), Feed Engineer (recorder-vs-SIP tape divergence).
Clean: Execution Surgeon, Trade Manager, Crown Steward — no money path touched.*
