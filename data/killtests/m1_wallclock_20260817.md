# M1 WALL-CLOCK WINDOW CLASS — 8/17 — BUILD+RIG ONLY (no deploy; ship after convene on Marcos's standing authorization)

Mechanism proven in `data/killtests/kevseq_frontside_tf_20260817.md` (commits b78a3ef/1fd978f):
the Alpaca/Webull M1 REST returns **TRADED minutes only**, so a fixed-count fetch spans
**wall-clock hours on thin tape** (RBNE 48 bars = 243 min; UUU 49 bars = 584 min = 9.7h).
Every consumer computing "recent" time-based context from such a list silently evaluates a
different window than intended — only on thin names, which is why liquid-name tests never caught
it. 31/31 kevseq disagree canary rows reproduced by this mechanism.

## 0. FAILURE CONDITION (written FIRST)
This work is WRONG if:
1. a **LIQUID-name decision changes** — on a dense list (span ≈ count) the window must keep every
   bar, byte-equivalent (rig M1W-a asserts it);
2. a **thin-name consumer computes on fewer bars than its own minimum** — insufficient-after-window
   must route to the consumer's EXISTING insufficient-data path (kevseq: `len < EMA20_PERIOD+2`
   → front_side stays None → self fallback → fail-closed unknown refusal; rig M1W-c);
3. `M1_WALLCLOCK=0` does not restore today's raw lists (rig M1W-d/e);
4. any consumer beyond the censused kevseq caller gets silently windowed in this ship (rig M1W-j
   pins exactly ONE call site);
5. the boot_config row does not stamp `m1_wallclock` + `ks_fs_wallclock_min` (rig M1W-f).

## 1. CENSUS (three-rings: every fixed-count M1 fetch + every consumer, READ not guessed)
| site (line, pre-edit) | consumer | window-sensitive? | action | why |
|---|---|---|---|---|
| :8067 `count=max(EMA_BOUNCE_LOOKBACK+EMA20_PERIOD+5,50)` → `cache[t]["bars"]` | kevseq ctx front-side `_ks_1m` EMA9/20 (:8421) | **YES — the proven defect (31/31)** | **WINDOWED, 50 wall-min** | fetch intent = "last ~50 minutes of 1-min chart" for a 20-period EMA; 50 wall-min keeps a dense 50-bar list (49-min span) intact |
| same list | fallback in `cache[t].get("full_bars") or bars` (compute_room, 3-min aggregate, `_latest_session`, pullback confirms) | session-scoped intent | not touched | engaged only when the adjacent count=390 fetch failed; those consumers want today-session structure, and `bars` ⊂ session |
| same list | `if not bars` presence guard; rolling references | no | not touched | presence only |
| :8071 `count=390` → `full_bars` | 3-min setup EMAs (`completed`), room, base, session VWAP | session-intent | count-fine | `_fresh_session` trims to TODAY; 390 ≥ a full RTH session, so "all of today" is exactly what arrives; the 3-min aggregate is timestamp-bucketed (clock-aligned grid), not index-based |
| :8098 / :11268 `count=VWAP_SESSION_COUNT`, PRE+RTH | session VWAP | no | count-fine | VWAP is defined over all traded bars; traded-minute grid is CORRECT here |
| :3256 read-list probe `count=MOMENTUM_BARS+3` | avg-vol liquidity floor for the reader roster | no | count-fine | a liquidity probe WANTS traded bars; `_fresh_session`'s 900s staleness already refuses dead tape (the DCOY/DBGI/TGL path) |
| :4199 `check_momentum` `count=390` | vol-accel + topping tail + liquidity floor over last MOMENTUM_BARS **traded** bars | **partly YES** (accel intends "recent minutes") | **FLAGGED, not touched** | its insufficient-data path is FAIL-OPEN ("passing by default"); windowing thin names would route them there → the entry gate gets MORE permissive on exactly the thin names it refuses today. Loosening a money gate = Marcos's call, not an auditor's. |
| :9930 `_vride_defer` `count=VELO_BARS+2` | velocity (close now vs VELO_BARS bars ago) | **YES** (velocity is a time rate; on thin tape N traded bars = a longer window → understated velocity → fewer defers) | **FLAGGED — separate ship** | position-open scale-management path; task rail: never modify monitor/scale paths with NIVF possibly live |
| :11087 `monitor_trade` bars (EMA_PERIOD-scaled count) | EMA/3-min close exits, rolling-45 VWAP (:11258), off-tape guard | **YES in part** (EMA exit context is time-based) | **FLAGGED — separate ship** | monitor with a position open; explicitly out of scope per the task |
| :13113 volume guard `count=6` | "avg recent 1-min volume" sizing cap | **YES** (a per-minute RATE; on thin tape 3 traded bars ≠ 3 minutes → cap too generous) | **FLAGGED, not touched** | its fail path is NO CAP (fail-open) → windowing would REMOVE a wrong-but-restraining cap and size thin names BIGGER. Needs a rate fix (volume ÷ wall-minutes), a behavior change to price for Marcos |
| :13201 universal gates `count=30` | topping tail (newest completed bar) + liquidity avg (last 3 bars) | mostly no | count-fine (note) | liquidity wants traded bars; topping tail reads only the newest bar (staleness ≤900s via `_fresh_session`); noted for the flagged-gate review |
| :2624/:2678/:2698 archive/winner_sweep `count=960` | data warehouse POST | no | count-fine | archive wants EVERYTHING |
| :2763 shadow cmp `count=4` | B12 stream-vs-REST bar compare | no | count-fine | matches by timestamp key |
| :11481 SPY probe `count=2` | preopen health | no | count-fine | reachability check |

## 2. THE FIX (minimal, central)
- `_wallclock_window(bars, minutes)` (marcos_trading_bot.py, beside `_fresh_session`): filters to
  bars within the last N wall-clock minutes anchored on the NEWEST bar's own timestamp (staleness
  stays `_fresh_session`'s job — every windowed consumer already routes through it, which also
  covers the session boundary: `_fresh_session` has already trimmed to TODAY before the window
  runs, so the window can never straddle a day). Fail-safes: unparseable anchor → list unchanged;
  unparseable inner bar → dropped (fail-closed toward the consumer's existing min-bars path).
- Applied ONLY at the kevseq caller front-side: `_ks_1m` now =
  `_wallclock_window(bars, KS_FS_WALLCLOCK_MIN)[:-1]` under `M1_WALLCLOCK=1`.
  **Window choice: 50 wall-clock minutes** (env `KS_FS_WALLCLOCK_MIN`) — the fetch's own intent
  (count=50 "1-min" bars for EMA20 context, which wants ~45–60 wall-min); a dense 50-bar list
  spans 49 min, so liquid names are byte-equivalent.
- Existing minimum unchanged: `len(_ks_1m) >= EMA20_PERIOD + 2` still gates; short-after-window →
  front_side None → `KEVSEQ_SELF_FRONTSIDE` fallback → unknown → fail-closed refusal (today's path).
- Kill switch: `M1_WALLCLOCK=0` restores raw lists (one switch for the class). No new per-row logs;
  boot_config stamps `m1_wallclock` + `ks_fs_wallclock_min`.
- Rig TF-c pin updated to require the WINDOWED form (the spec changed with this fix); all other
  TF pins (stamps, canary, precedence, fail-closed) untouched and still green.

## 3. WHAT WAS NOT TOUCHED, AND WHY
- **10s-bar paths / champion lanes' 10s logic / `kevseq_feed_1m` self-aggregate** — already
  wall-clock by construction; out of scope by mandate.
- **monitor_trade (:11087) and `_vride_defer` (:9930)** — window-sensitive, FLAGGED for a separate
  ship: position-open paths, never modified intraday with NIVF possibly live.
- **check_momentum (:4199), volume guard (:13113), universal liquidity (:13201)** — windowing
  routes thin names into FAIL-OPEN insufficient-data paths (momentum pass-by-default; no volume
  cap), i.e. LOOSER money behavior on thin names. Auditor cannot authorize behavior
  ([[feedback_auditor_cannot_authorize_behavior]]); priced for Marcos at the convene.
- **kevseq precedence (caller vs self)** — unchanged, per the 8/17 doc: money decision, Marcos's
  call. This fix makes the caller honest; it does not re-rank the sources.

## 4. RIG
Section **M1W** (10 pins) in `rig/test_shipset_20260804.py`: dense byte-equivalence; thin 4-hour
fixture → stale bars excluded; insufficient-after-window → existing len() refusal; kill-switch +
boot stamps structural; helper fail-safes executed; span-collapse assertion (243+ min → ≤50 min);
exactly ONE call site (census guard). Full rig exit code required 0 — result recorded below.

## 5. SPEC TENSION FOR MARCOS (unresolved)
The task said "apply the wall-clock window to each WINDOW-SENSITIVE consumer", but rail (i)
(insufficient-after-window → existing path) makes three of them (momentum / volume guard /
universal liquidity) MORE permissive on thin names, and two live in position-open paths. Only the
kevseq caller satisfies both rails today. Decision needed: (a) accept the flagged set as a
follow-on ship with per-gate fail-closed semantics designed first, or (b) leave them on the
traded-minute grid deliberately (liquidity/tape gates arguably WANT traded bars).

## RIG RESULT
Full rig `python3 rig/test_shipset_20260804.py` 8/17 intraday: **ALL GREEN, exit 0** (M1W 10/10;
FS/TF sections green with FS-c/TF-c updated to pin the WINDOWED call form). Judged by EXIT CODE.
