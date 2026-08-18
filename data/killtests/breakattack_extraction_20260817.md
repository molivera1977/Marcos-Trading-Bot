# BREAK-ATTACK EXTRACTION — making our best-validated lane testable (batch D, 2026-08-17)

## FAILURE CONDITION (written first)

**This work is wrong if any of these turns out to be true:**

1. **The live bot's behaviour changed.** Concretely: if any 8/18+ session produces a
   `break_attack` / `break_armed` / `broke_no_vwap` / `broke_below_vwap` / `triggered_flat_top`
   row that the pre-refactor code would not have produced, at a different level, or with a
   different stop. The differential grid (rig D3, 1,200 combinations) and the three 8/17
   fixtures (rig D2) are the checks; if a live row disagrees with a replay of the same base,
   the extraction is wrong and `git revert` of this commit restores the inline path exactly.
2. **The extraction is a second implementation.** If someone can change `flat_top_step` and
   see no change in what the bot does, the whole point is lost — that is the study-replica
   disease we are curing. Rig D1 pins that the live loop *calls* the core and that the inline
   duplicates are gone.
3. **The parity number is read as more than it is.** 3/3 on three fires is the absence of a
   disagreement, not evidence. If 8/18-8/21 break-attack fires do not keep reproducing, the
   100% was noise.
4. **A study grades the funnel using this.** The core decides `attack` on 29 names the live
   bot never traded on 8/17, because candidate selection / slots / already-traded suppression
   live upstream. Any flat_top study that reports those as "fires the bot missed" is wrong.

## WHY THIS WAS THE WORST FOUNDATION HOLE

break-attack (the flat_top lane's 09:30-10:30 variant, `FLATTOP_BREAK_ATTACK`) is one of the
two lanes that passed the weekend bar (O-config: break-attack + grinder + E3, mean +$157/day,
median +$134, 89% green — `edge_stresstest_G_20260815.md`). It was also the single lane the
live-code harness (`live_harness.py`, 83c33e1) explicitly could not lift. Its own
`NOT_ISOLABLE` entry said so:

> *"not a function: the flat-top consolidation tracker + FLATTOP_BREAK_ATTACK conversion live
> INSIDE `wait_for_flat_top_entry` (~1k lines), driven by a WebullStream object, a
> session_cache and rescan callbacks."*

So the lane we are betting the go-live on was the one nothing could independently verify.

## THE PRE-REFACTOR MAP (done BEFORE touching anything)

`wait_for_flat_top_entry` is ~1,000 lines and drives ~15 lanes. The break-attack path is a
~60-line island inside it. Mapped end to end:

| What the break-attack decision needs | Where it came from | Verdict |
|---|---|---|
| **Bar series** | `aggregate_bars(cache[t]["full_bars"], SETUP_TF_MIN)[:-1]` → 3-MIN bars, then `_latest_session(...)` → today only. Rolled from the 1-min feed. **Not 10s.** | pure, liftable |
| **Base window** | last `FLAT_TOP_WINDOW` (4) session 3-min bars → `w_high`, `w_low` | pure |
| **Flatness** | `rng = (w_high-w_low)/w_low <= FLAT_TOP_MAX_RANGE` (0.12) | pure |
| **Break trigger** | `is_flat and price > w_high and not _pb` | pure |
| **Cell** | `FLATTOP_BREAK_ATTACK and "09:30" <= ET < "10:30"` | pure (clock in, as ctx) |
| **VWAP gate** | `vwap <= 0` → `broke_no_vwap`; `price < vwap` → `broke_below_vwap` | pure |
| **Stop** | `round(w_low, 4)` — base low exact, **not** the `ZONE_STOP_BUFFER` zone stop the retest path uses | pure |
| **Retest arm state** (`cache[t]["pb"]`) | wall-clock `time.time()` vs `PULLBACK_TIMEOUT_SECS`, `_recent_low_dip` / `_confirm_reclaim` on the live 1-min tape | **NOT liftable** — but it only enters break-attack as one boolean (`not _pb`) |
| **ma_pullback preemption** | `_ma_first_fire` (PULLBACK_FIRST pre-pass) and `_ma_only_window` (MA_WARMUP_SEED) | one boolean each |
| **Daily levels** | `get_daily_levels(t)` → network | **observe-only since 7/26** — logs `broke_daily_bad`, does not block |
| **Room** | `compute_room(...)` → reads bars + daily | **soft since 7/2** — logs `low_room_soft`, does not block |
| **Session cache / rescan / stream** | the *caller's* concern: which names get scanned, when, and with what bars | outside the decision |

**The map's conclusion, reached before any edit:** the break-attack decision is genuinely
separable. Everything that can *block or price* a break-attack fire is a pure function of
(3-min session bars, price, vwap, clock, three booleans). Nothing that touches the network or
the stream can block it. The stream-dependence in the old `NOT_ISOLABLE` note was real for the
*retest* machinery and mistakenly attributed to the whole lane.

## WHAT MOVED, WHAT STAYED

**Moved out** (new pure functions, `marcos_trading_bot.py`, immediately above
`wait_for_flat_top_entry`):

- `_ft_window_stats(sess3)` → `(w_high, w_low, rng, is_flat)`; `None` when the base does not exist yet.
- `_ft_vwap_veto(price, vwap)` → `None` / `"broke_no_vwap"` / `"broke_below_vwap"`. **Shared by
  both the retest path and the break-attack path** — they can no longer diverge.
- `_ft_attack_window(time_hm)` → the tested cell + the `FLATTOP_BREAK_ATTACK` kill switch.
- `_ft_attack_stop(w_low)` → `round(w_low, 4)`.
- `flat_top_step(sym, sess3, price, vwap, ctx)` → the sibling of `grinder_shadow_step` /
  `kevseq_step` / `v2_pullback_step`. Returns `action` ∈ {`attack`, `arm`, `none`}, `ok`,
  `w_high/w_low/rng/is_flat/stop`, and `why` (the live decision-row status strings).
  ctx is **required, never defaulted**: `armed`, `time_hm`, `ma_first`, `ma_only_window`
  (`KeyError` on absence — the harness's contract, enforced inside the bot too).

**Stayed inline, on purpose** (all of it *downstream* of, or *upstream* of, the decision):

- the retest arm/dip/reclaim state machine (wall-clock + 1-min tape);
- the daily-level read and `daily_first_ok` (observe-only) and `compute_room` (soft);
- the arm side effect (`cache[t]["pb"] = {...}`), every `_log_decision` row, `status_parts`,
  the `_ft_extra` payload (`exit_mode="E3"`, `break_attack=True`), and the append to `breakouts`.

**The ordinary (non-break-attack) flat_top path — what changed and exactly how.** It was
touched, minimally, and here is the full list:

1. `w_high` / `w_low` / `rng` / `is_flat` now come from `_ft_window_stats` via `flat_top_step`
   instead of four inline expressions. **Same expressions, byte-for-byte** (they were moved,
   not rewritten).
2. The out-of-window **arm** branch is now selected by `_ftd["action"] == "arm"` instead of by
   the inline `else:`. Same condition, same body, same `continue`.
3. The shared VWAP gate now calls `_ft_vwap_veto` instead of two inline `if`s. Same order,
   same two decision rows.
4. `_pb = cache[t].get("pb")` is read a few lines earlier (before the `if w_low > 0:` fork
   instead of inside it). No side effect sits between the old and new read points.

Nothing else in that path was altered. No gate was added, removed, or re-tuned; no numeric
changed; no new env var exists. **The existing kill switch `FLATTOP_BREAK_ATTACK=0` still
reverts the cell**, now via `_ft_attack_window` (rig D4 pins it).

## EQUIVALENCE EVIDENCE

`rig/test_batchD_20260817.py` — all specs green, exit 0. It drives the **shipped function
objects** (AST-lifted by `live_harness`), never a copy.

**(a) The three real 8/17 triggers** (`SPEC_break_attack_live_fixtures_0817`). Prices and
levels taken verbatim from `/api/decisions_archive?date=2026-08-17&status=break_attack`:

| | live price | live w_high | live w_low | core verdict | core stop |
|---|---|---|---|---|---|
| IPST 09:30:45 | 8.155 | 8.09 | 7.46 | attack, ok | 7.46 |
| CDTG 09:30:47 | 2.17 | 2.09 | 2.0008 | attack, ok | 2.0008 |
| LBGJ 09:30:47 | 3.16 | 3.10 | 3.07 | attack, ok | 3.07 |

**(b) The differential** (`SPEC_break_attack_differential_vs_old_path`). The pre-refactor
inline logic is transcribed **verbatim** into the rig as `_old_path()` and run against the
extracted core over a 1,200-combination grid: 3 base lows × 5 base widths (straddling the
0.12 flatness boundary) × 4 price offsets (below / at / just-through / well-through the high)
× 4 VWAP values (0, negative, below price, above price) × armed/unarmed × 5 clock values
(09:29 / 09:30 / 10:29 / 10:30 / 13:05). All seven decision fields must agree on every
combination. **They do.**

This grid earned its keep on the first run: it caught the extraction setting `stop` on a
break-attack that the VWAP gate then vetoed, where the old path left it unset. Cosmetic (the
live loop `continue`s before reading it) but a real divergence, and it was fixed rather than
excused. That is the only disagreement the grid has ever reported.

**(c) The Gate 5 acceptance** is `rig/test_batchD_20260817.py::SPEC_break_attack_extracted_and_live_calls_it`
— it fails at the parent (no `flat_top_step` exists) and passes at the commit.

**(d) Rig `AB-c`** in `rig/test_shipset_20260804.py` — the standing behaviour pin for this lane
— was updated to follow the code to its new home, keeping every assertion in substance and
adding three new ones proving the live loop *consumes* the core's verdict. It is green.

**This is a real swap, not shadow-only.** The task allowed shipping shadow if equivalence
could not be proven; it could be, three ways, so the honest thing was the swap: a shadow would
have left two implementations, which is the disease.

## TODAY'S PARITY

`data/killtests/harness_parity_flattop_20260817.py` → `..._out.json`, recorded in
`harness_parity.json` under lane `flat_top`.

**flat_top parity on 2026-08-17: 100.0% (3 / 3 live fires reproduced), |dt| ≤ 37s.**

Read it with its bounds:

- **N=3.** The cell fired three times all day. 100% here is the absence of a disagreement.
- **Levels: w_high exact on 2/3, w_low on 1/3.** IPST's base reads 8.1399 / 7.49 off our 10s
  SIP roll vs 8.09 / 7.46 off the broker's M1 — a 3c stop difference. That is a **feed**
  difference, and 8/17 predates the A2 provenance stamps, so it cannot be attributed between
  detector and feed from this day. 8/18 onward supports `fed_slices` exact-stream parity and
  should be re-run then.
- **The denominator is LIVE fires only.** Replayed across all 56 captured names the core also
  attacks on **29 names the live bot never fired on**. That is the funnel — scanner board
  membership, slot limits, `found_entry` / already-traded suppression, an existing retest arm —
  all of which sits *upstream* of the detector and is deliberately not modelled. The harness
  grades the detector, never the funnel.

## WHAT REMAINS UN-EXTRACTABLE (stated plainly)

- **The retest arm / reclaim state machine.** `PULLBACK_TIMEOUT_SECS` against `time.time()`,
  `_recent_low_dip` and `_confirm_reclaim` against the live 1-min tape. It stayed inline, and
  this is why `armed` is a **required ctx field the study must supply** rather than something
  the harness reconstructs. Supplying `armed=False` measures the break-attack cell on the
  assumption no out-of-window arm was live for that name — true whenever the name's first
  break of the session happens inside 09:30-10:30, which is the ordinary case.
- **Daily levels and room.** Both network reads; both observe-only/soft today, so neither can
  block a fire. If either is ever made a hard gate again, this extraction becomes incomplete
  and the doc must be reopened.
- **The candidate funnel.** Which names reach the loop at all, in what order, with what bars
  (scanner board, the lens, re-entry, slots, rescan cadence). Not a detector property.
- **`replay()` cannot drive this lane** and refuses it by name: it feeds 10s new-bar slices,
  while flat_top is 3-min / whole-session. Use `replay_flat_top()` (rig D5 pins the refusal).

## FILES

| file | change |
|---|---|
| `marcos_trading_bot.py` | +5 pure functions; the flat_top block now calls them |
| `data/killtests/live_harness.py` | `flat_top` lane registered w/ ctx contract; `replay_flat_top()`, `bars10s_to_m1()`, `et_hm()`; `replay()` refuses driver-lanes; `NOT_ISOLABLE` entry rewritten |
| `rig/test_batchD_20260817.py` | new — 5 specs, Gate 5 acceptance |
| `rig/test_shipset_20260804.py` | `AB-c` pin follows the code |
| `data/killtests/harness_parity_flattop_20260817.py` | new — the parity measurement |
| `data/killtests/flattop_live_0817.json` | live truth: the 3 archive rows |
| `data/killtests/harness_parity.json` | `flat_top` lane recorded |

**Not done, on purpose:** no deploy, no push, no env change, no restart.
