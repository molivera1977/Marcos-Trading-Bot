#!/usr/bin/env python3
"""LIVE-CODE STUDY HARNESS (built 8/17, Marcos's order) — research-only.

THE PROBLEM IT EXISTS TO KILL
-----------------------------
Every kill-test script so far RE-IMPLEMENTED the lane detectors instead of calling the
bot's.  The replicas drift, and always in the flattering direction.  Proof (8/17):
data/killtests/kevseq_frontside_tf_20260817.md found that entry_drift_20260817,
burst_saturation_20260817, kevseq_floor_sweep_20260817 and kevseq_reconciliation_20260817
applied NO front-side clause at all while the live kevseq lane requires it — four studies
grading a machine that is not ours.  Same species as the fill-model drift (studies assumed
entry at the signal price; live entered 5-60% higher) and the fictional-fill accounting.

THE FIX
-------
Run the BOT'S OWN function objects over historical 10s bars, so study == live BY
CONSTRUCTION.  Nothing here is copied from the bot: every detector below is the literal
`def` block lifted out of marcos_trading_bot.py by the AST loader and exec'd into an
isolated namespace.  Change the bot, the harness changes with it (or fails loudly).

DIRECTION OF DEPENDENCY IS ONE-WAY AND MUST STAY THAT WAY
---------------------------------------------------------
harness -> reads marcos_trading_bot.py source.  The bot NEVER imports this module.
Rig section BH pins that (guard pin: no 'live_harness' token in the bot).

WHY NOT `import marcos_trading_bot`
------------------------------------
Importing it executes module-level side effects: env reads, broker/Alpaca client
construction, thread starts, file writes.  That is a live trading path.  The AST loader
below takes ONLY the named `def`/constant nodes and their transitive module-level
dependencies, compiles them, and execs them into a private dict.  No side effects, no
network, no threads.  Same technique the rig already uses (rig/test_shipset_20260804.py
sections AB/AH/AL/M1W).

THE CONTEXT CONTRACT (the whole point)
--------------------------------------
Each lane declares REQUIRED ctx keys.  The harness REFUSES to run a detector whose ctx is
missing a key — `MissingContext` names the field.  It does NOT default.  Silent defaulting
is the exact bug that made four studies front-side-free.  A ctx value may legitimately be
None (kevseq treats front_side=None as "unknown -> refuse"), but the KEY must be supplied
deliberately by the caller.

See harness_parity_20260817.md for the today-parity numbers and the "how to write a study
with this" section.
"""
from __future__ import annotations

import ast
import datetime as _dt
import json
import os
import pathlib
import time as _time
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOT = ROOT / "marcos_trading_bot.py"
EASTERN = ZoneInfo("America/New_York")


# ───────────────────────── errors ─────────────────────────
class HarnessError(Exception):
    pass


class MissingContext(HarnessError):
    """Raised when a study fails to supply a ctx field a detector's gates depend on."""


class NotIsolable(HarnessError):
    """Raised when a requested bot symbol cannot be lifted without live side effects."""


# ─────────────────── frozen clock (replay day) ───────────────────
class _FrozenDT(_dt.datetime):
    """datetime shim injected into the isolated namespace.

    The detectors call datetime.now(EASTERN) ONLY to build their per-day state key
    (`st["day"]`).  Replaying a past day with the real clock would key every machine to
    today and silently reset state.  now() returns the REPLAY day's date; everything else
    (fromtimestamp / strptime / arithmetic) is stock datetime, so the bar-clock logic that
    grinder / bandpass / zone_flip use (datetime.fromtimestamp(k, EASTERN)) is untouched.
    """
    _replay_day = None   # "YYYY-MM-DD"

    @classmethod
    def now(cls, tz=None):
        if cls._replay_day is None:
            return _dt.datetime.now(tz)
        y, m, d = (int(x) for x in cls._replay_day.split("-"))
        return _dt.datetime(y, m, d, 12, 0, 0, tzinfo=tz or EASTERN)


def set_replay_day(day: str):
    """Freeze the harness clock to `day` ('YYYY-MM-DD'). Call before any replay."""
    _FrozenDT._replay_day = day


# ─────────────────── the AST loader ───────────────────
_SRC = None
_TREE = None
_FUNCS: dict = {}
_ASSIGNS: dict = {}          # name -> (order_index, node)
_ORDER: list = []


def _parse():
    global _SRC, _TREE
    if _TREE is not None:
        return
    _SRC = BOT.read_text()
    _TREE = ast.parse(_SRC)
    for i, node in enumerate(_TREE.body):
        if isinstance(node, ast.FunctionDef):
            _FUNCS[node.name] = node
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    _ASSIGNS[t.id] = (i, node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            _ASSIGNS[node.target.id] = (i, node)


# Names the harness itself provides in the namespace — the resolver stops here instead of
# chasing them into the bot.  Everything else must be liftable or the load FAILS LOUD.
_PROVIDED = {
    "os", "json", "time", "math", "datetime", "timedelta", "timezone", "date",
    "ZoneInfo", "EASTERN", "print", "random", "statistics", "collections", "re",
    # transitively reached by lifted defs. threading/atexit are inert until CALLED (the only
    # module-level use is Lock() construction). `requests` is deliberately replaced by a
    # POISONED stub in ns(): if any lifted code path ever tries to hit the network during a
    # replay, the study dies loudly instead of quietly phoning a broker.
    "threading", "atexit", "requests", "concurrent",
    # bound by module-level try/except IMPORT blocks (not top-level Assign nodes, so the
    # resolver cannot see them). Provided INERT: the broker SDK is never constructed here.
    # Nothing the harness exposes reads them — they are reached only as dead references
    # inside transitively-lifted fetch helpers, which studies replace with fixtures.
    "ApiClient", "WebullDataClient", "WEBULL_SDK_AVAILABLE",
    # 8/17 C2: the config-hash block is reached transitively from _log_decision. It digests the
    # bot's own source (hashlib) and locates it via __file__ — both are supplied REAL in ns(),
    # pointed at the actual bot file, so the isolated namespace computes the same hash the live
    # process would. Neither touches the network or the broker.
    "hashlib", "__file__",
}


class _NoNetwork:
    """Poisoned stand-in for `requests` inside the isolated namespace."""
    def __getattr__(self, k):
        def _boom(*a, **kw):
            raise HarnessError(
                f"NETWORK BLOCKED: lifted bot code called requests.{k}() during a replay. "
                "A study must never hit the live path — supply a fixture instead.")
        return _boom
_BUILTINS = set(dir(__builtins__)) if isinstance(__builtins__, dict) is False else set(__builtins__)
try:  # __builtins__ is a dict under exec, a module at top level
    _BUILTINS = set(__builtins__.keys())   # type: ignore[union-attr]
except AttributeError:
    _BUILTINS = set(dir(__builtins__))


def _free_names(node):
    """Module-level names a node reads (crude but conservative: every Name/Attribute root
    in Load context, plus decorator/default names). Over-collecting is safe — it only makes
    the resolver pull MORE real bot code."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            out.add(n.id)
    return out


def _bound_names(node):
    """Names bound inside a function (args, locals, comprehension vars) — not module deps."""
    out = set()
    if isinstance(node, ast.FunctionDef):
        a = node.args
        for arg in list(a.args) + list(a.posonlyargs) + list(a.kwonlyargs):
            out.add(arg.arg)
        if a.vararg:
            out.add(a.vararg.arg)
        if a.kwarg:
            out.add(a.kwarg.arg)
        out.add(node.name)
    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not node:
            out.add(n.name)
        if isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
            a = n.args
            for arg in list(a.args) + list(a.posonlyargs) + list(a.kwonlyargs):
                out.add(arg.arg)
            if a.vararg:
                out.add(a.vararg.arg)
            if a.kwarg:
                out.add(a.kwarg.arg)
        elif isinstance(n, ast.comprehension):
            for t in ast.walk(n.target):
                if isinstance(t, ast.Name):
                    out.add(t.id)
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for al in n.names:
                out.add((al.asname or al.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.Global):
            out.update(n.names)
    return out


def resolve(names, _seen=None):
    """Transitively resolve bot symbols. Returns (assign_nodes_in_source_order, func_nodes,
    unresolved_names). Unresolved != fatal by itself — the caller decides."""
    _parse()
    seen = set(_seen or ())
    need_a, need_f, unresolved = {}, {}, set()
    stack = list(names)
    while stack:
        nm = stack.pop()
        if nm in seen or nm in _PROVIDED or nm in _BUILTINS:
            continue
        seen.add(nm)
        if nm in _FUNCS:
            node = _FUNCS[nm]
            need_f[nm] = node
            stack.extend(_free_names(node) - _bound_names(node))
        elif nm in _ASSIGNS:
            i, node = _ASSIGNS[nm]
            need_a[nm] = (i, node)
            stack.extend(_free_names(node) - _bound_names(node))
        else:
            unresolved.add(nm)
    assigns = [n for _, (i, n) in sorted(need_a.items(), key=lambda kv: kv[1][0])]
    return assigns, list(need_f.values()), unresolved


_NS: dict | None = None


def ns():
    """The isolated namespace holding the bot's REAL function objects. Built once."""
    global _NS
    if _NS is not None:
        return _NS
    _parse()
    import collections as _c
    import math as _m
    import random as _r
    import re as _re
    import statistics as _s
    import threading as _th
    import atexit as _ax
    import hashlib as _hl
    n = {
        # 8/17 C2: real, and pointed at the real bot file — the isolated namespace must compute
        # the SAME config hash the live process does, not a different one.
        "hashlib": _hl, "__file__": str(BOT),
        "threading": _th, "atexit": _ax, "requests": _NoNetwork(),
        "concurrent": __import__("concurrent.futures").futures and __import__("concurrent"),
        "ApiClient": None, "WebullDataClient": None, "WEBULL_SDK_AVAILABLE": False,
        "__builtins__": __builtins__,
        "os": os, "json": json, "time": _time, "math": _m, "random": _r,
        "statistics": _s, "collections": _c, "re": _re,
        "datetime": _FrozenDT, "timedelta": _dt.timedelta,
        "timezone": _dt.timezone, "date": _dt.date,
        "ZoneInfo": ZoneInfo, "EASTERN": EASTERN,
    }
    assigns, funcs, unres = resolve(ALL_SYMBOLS)
    if unres:
        raise NotIsolable("unresolvable bot symbols: " + ", ".join(sorted(unres)))
    mod = ast.Module(body=assigns + funcs, type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, str(BOT), "exec"), n)
    _NS = n
    return n


def fn(name):
    """The bot's REAL function object for `name`."""
    f = ns().get(name)
    if f is None:
        raise NotIsolable(f"{name} not present in the isolated namespace")
    return f


def const(name):
    return ns()[name]


# ─────────────────── what is isolable, and what is not ───────────────────
# Every symbol below is lifted from the bot verbatim.  If any becomes un-liftable (a new
# dependency on a client / thread / file), ns() raises NotIsolable and the rig goes red —
# which is the point: drift becomes a build break, not a silent flattering number.
ALL_SYMBOLS = [
    # kevseq lane
    "kevseq_step", "kevseq_feed_1m", "kevseq_front_side",
    # other 10s lanes
    "grinder_shadow_step", "bandpass_step", "v2_pullback_step", "v2_trailing_calm",
    "hidden_entry_step", "ignition_10s_step", "detect_ignition",
    # 8/17 B2: the shared fire-age suppressor the detector lanes now call (and its env
    # parser).  Disarmed by default, so lifting it changes no harness result — but it must
    # LIFT, or kevseq_step/grinder_shadow_step/bandpass_step/v2_pullback_step cannot.
    "_parse_lane_age_guard", "_lane_fire_stale", "_LANE_AGE_GUARD", "LANE_FIRE_AGE_GUARD",
    "_bucket_fresh", "_log_stale_fire", "_halted_secs_since",
    # 8/17 batch E: zone_flip + the runway. Both were NOT_ISOLABLE until the bot grew explicit
    # injection points (E1 clock hook, E2 pm_floor arg, E3 lvd/wall_high args).
    # 8/18: the 9/90 lane shipped 12:43 today and was NOT in this list, so it could not be
    # lifted, exercised, or parity-measured at all. Added with its state + config.
    # ── 8/18: FIVE DETECTORS THE LIVE LOOP CALLS THAT WERE NEVER REGISTERED ──
    # Found by censusing the scan loop against this list (rig gate 17). Two of them TRADED on
    # 8/18 while being impossible to lift, replay or parity-measure:
    #   detect_ma_pullback  2 fills (-$26.76, +$48.76) — and it is the lane that bought CDTG
    #                       66% above VWAP at 14:16:43, the open extension defect
    #   dip_rip_step        1 fill (-$34.67 PFSA)
    # The other three are live-callable but did not fire today. ema9x90 shipped 12:43 the same
    # way and ran a full session with a wall-clock bug nothing could test.
    "detect_ma_pullback", "_detect_ma_pullback", "MA_PULLBACK_LEVELS", "MA_PULLBACK_TOUCH_TOL",
    "MA_PULLBACK_STOP_BUFFER", "MA_PULLBACK_DEDUPE", "MA_WARMUP_SEED", "_calc_ema", "_extract_closes",
    "dip_rip_step", "_dr_st", "DIPRIP_ZONE", "DIPRIP_WINDOW_S",
    "detect_bounce", "BOUNCE_MIN_RUN", "BOUNCE_MIN_DD",
    "detect_rocket", "_rocket_day", "ROCKET_CATCHER", "ROCKET_VEL_PCT", "ROCKET_VEL_BARS",
    "ROCKET_DAILY_CAP",
    "detect_gate",
    # kev_reclaim_step: it HAS a LANES entry ("reclaim") pointing at a symbol that was never
    # extracted — so replay("reclaim") raised NotIsolable and every study reported the lane as
    # "0 fires" instead of "could not run". The premarket bake-off printed reclaim n=0 in a
    # results table; vwap_reclaim is the -$648.24 line, the largest single loss in the PRE book,
    # and it has been UNMEASURABLE the whole time. Caught by gate 17 on its first run.
    "kev_reclaim_step", "_reclaim_st", "_reclaim_cursor", "RECLAIM_KEV",
    "RECLAIM_LIVE", "RECLAIM_LIVE_START", "RECLAIM_LIVE_END", "RECLAIM_FIREVOL",
    # 8/18: the VWAP adjudication chain, so the CDTG 7.11 class is testable at all.
    "_tick_vwap_ok", "_vwap_coverage_min", "_vwap_bar_trusted",
    "VWAP_COVERAGE_GUARD", "VWAP_MIN_SPAN_MIN",
    "ema9x90_step", "_x90_st", "EMA9X90", "EMA9X90_CONVERT", "EMA9X90_HALF_SIZE",
    "EMA9X90_SWING_BARS", "EMA9X90_MAX_STOP", "EMA9X90_VWAP_EXIT", "EMA9X90_OPEN",
    "EMA9X90_CLOSE", "EMA9X90_WARMUP",
    "kev_zoneflip_step", "_zf_st", "ZONEFLIP_BAND", "ZONEFLIP_FLUSH",
    "_zf_pm_floor", "_zf_zone",
    "_marked_runway",
    # flat_top / BREAK-ATTACK lane (8/17 batch D extraction). Previously the one lane the
    # harness could not lift at all — it lived inline in wait_for_flat_top_entry behind a
    # WebullStream. Now a pure bar-driven core, called BY the live loop, replayed here.
    "flat_top_step", "_ft_window_stats", "_ft_vwap_veto", "_ft_attack_window",
    "_ft_attack_stop", "_latest_session",
    "FLAT_TOP_WINDOW", "FLAT_TOP_MAX_RANGE", "FLATTOP_BREAK_ATTACK", "SETUP_TF_MIN",
    # shared machinery studies keep re-implementing
    "_seq_events", "_wallclock_window", "_scaled_risk", "aggregate_bars",
    "calculate_ema9", "calculate_ema20", "calculate_ema90",
    "_bar_high", "_bar_low", "_bar_open", "_bar_close", "_bar_vol",
    # INJECTABLE (lifts cleanly, but its INPUT is a live fetch — see check_momentum_on())
    "check_momentum",
    # the per-name machine-state dicts (live: module-level, survive rescans; harness:
    # reset_state() clears them per name-day) + the constants sizing_chain() reads
    "_ks_st", "_ks_1m_agg", "_gr_st", "_bp_st", "_pv_st", "_v2_st", "_v2_hist", "_he_st",
    "_ig10_st", "V2_QUIET_LOOK",
    "SIM_ACCOUNT_BALANCE", "MAX_POSITION_SIZE", "MAX_TRADE_DOLLARS", "MAX_POS_VOL_PCT",
    "RISK_PER_TRADE", "RISK_PROP", "RISK_PROP_REF",
]


# ─────────────── the bar clock (batch E1) ───────────────
# `_bucket_fresh` is the shared stale-fire suppressor EVERY 10s lane calls before it may fire.
# It compares the bar bucket to time.time(); in replay every bar is hours old, so before E1 it
# ate 100% of replayed fires (IVF: hidden armed correctly, 78 suppressions, 0 fires) and made
# hidden + zone_flip's fire paths structurally unreachable.  The bot now carries a module hook
# `_BUCKET_NOW`, None in the live process (so the live expression collapses to the old
# time.time() call verbatim).  replay() drives it to each fed slice's LAST bar epoch — the value
# the live clock read when it saw that bar.
_BAR_NOW = {"k": None}


def _install_bar_clock():
    """Point the bot's _BUCKET_NOW hook at the replay bar clock. Idempotent."""
    N = ns()
    if "_BUCKET_NOW" not in N:
        raise NotIsolable(
            "_BUCKET_NOW hook missing from the bot — batch E1 was reverted; the fire path of "
            "every 10s lane is unreplayable again. Refusing to run a flattering replay.")
    N["_BUCKET_NOW"] = lambda: (_BAR_NOW["k"] if _BAR_NOW["k"] is not None else _time.time())


def set_bar_now(k):
    """Set the replay 'now' to bucket epoch k (None restores the wall clock)."""
    _BAR_NOW["k"] = None if k is None else float(k)


def check_momentum_on(ticker, m1_bars, session_bars=None):
    """Run the bot's REAL check_momentum against a supplied 1-min bar fixture.

    check_momentum's BODY is pure; only its input is live (`get_intraday_bars(ticker, ...)`).
    So it IS liftable — but a replay must hand it the bars, and it routes them through
    _fresh_session(), which keeps TODAY's bars only.  Two consequences a study must respect:
      * m1_bars must carry the same ISO 'time' shape the broker returns;
      * replaying a PAST day yields an empty session -> check_momentum's own
        insufficient-data path, NOT a real read.  Use only for same-day work, or state the
        bound in the doc.  This is disclosed, never silently defaulted.

    8/17 batch E4 LIFTS THAT BOUND.  check_momentum now accepts `session_bars`: an
    ALREADY-SESSIONISED 1-min list that bypasses both the fetch and _fresh_session's
    today-only filter.  Pass session_bars=<the past day's session> to replay a PAST day for
    real.  The live call passes neither argument and is byte-identical (rig SPEC_momentum_default).
    Precedence: session_bars wins; m1_bars alone keeps the old today-only semantics.
    """
    N = ns()
    if session_bars is not None:
        return N["check_momentum"](ticker, session_bars=list(session_bars))
    prev = N.get("get_intraday_bars")
    N["get_intraday_bars"] = lambda t, count=None, sessions=None, **kw: list(m1_bars)
    try:
        return N["check_momentum"](ticker)
    finally:
        if prev is not None:
            N["get_intraday_bars"] = prev


def pm_floor_from_tape(sym, bars, day):
    """Compute the zone_flip premarket floor by running the BOT'S OWN _zf_pm_floor over a
    TAPE FIXTURE instead of the live premarket store (batch E2).

    _zf_pm_floor's body is pure arithmetic over 10s buckets; its ONE live dependency is
    _curl_feed(sym, n=720), which is swapped here for the day's captured tape in the feed's
    own dict shape.  So the zone a study uses is the bot's computation, not a study's replica
    — and it can be cross-checked against the `zone`/`zone_src` the live rows stamped, which
    is exactly how the batch-E parity run validated it.

    Returns the {"zone","src","open930"} dict (or None), ready to hand to the lane's
    REQUIRED `pm_floor` ctx field.  Requires premarket bars in the fixture: without 09:00-09:29
    coverage the honest answer is None, not a guess.
    """
    set_replay_day(day)
    B = norm_bars(bars, day=day)
    feed = {int(k): {"o": o, "h": h, "l": l, "c": c, "v": v} for k, o, h, l, c, v in B}
    N = ns()
    N.setdefault("_zf_zone", {})
    N["_zf_zone"].pop((day, sym), None)          # never serve another run's cached verdict
    prev = N.get("_curl_feed")
    N["_curl_feed"] = lambda t, n=90: (feed, "harness_tape")
    try:
        return N["_zf_pm_floor"](sym)
    finally:
        if prev is not None:
            N["_curl_feed"] = prev


def marked_runway_on(ticker, entry_price, stop_loss, level_map, wall_high=None):
    """Run the bot's REAL _marked_runway against an INJECTED map + wall high (batch E3).

    level_map  the effective map dict the gates saw: {break, targets, next_supply, zone,
               kev_road_max, ...}.  MANDATORY — the harness will not invent one.
    wall_high  today's session high at decision time (the RUNWAY_WALL input).  None means
               "let the wall gate fall back to the live feed", which a replay must never do,
               so None is REFUSED here; pass 0.0 to study the wall-disabled case explicitly.

    HISTORICAL BOUND — READ IT: this makes runway replayable WHEN A MAP SNAPSHOT EXISTS.  For
    every day up to and including 2026-08-17 NO SNAPSHOT WAS EVER RECORDED (the level-map store
    is mutated all day and is unrecoverable after the fact), so historical runway replay remains
    IMPOSSIBLE and no amount of injection fixes it.  The bot began stamping map_break /
    map_targets / map_next_supply / map_zone / map_age_min / map_src on every triggered row on
    2026-08-17 (batch E3b); 2026-08-18 is the first day reconstructable from the archive.
    """
    if not isinstance(level_map, dict):
        raise MissingContext(
            "marked_runway_on requires an explicit level_map (the map the gates saw). "
            "No snapshot exists for days <= 2026-08-17 — the honest answer there is "
            "'un-replayable', not a map the study made up.")
    if wall_high is None:
        raise MissingContext(
            "marked_runway_on requires wall_high (today's session high at decision time). "
            "Omitting it would let RUNWAY_WALL fall through to the live recorder feed.")
    return fn("_marked_runway")(ticker, float(entry_price), float(stop_loss),
                                lvd=dict(level_map), wall_high=float(wall_high))

# NOT ISOLABLE — each with its concrete blocker.  Do NOT hand-roll these in a study; if a
# study needs one, the honest move is to say so in the doc and bound the claim.
NOT_ISOLABLE = {
    "_marked_runway (INJECTABLE; HISTORICALLY UN-REPLAYABLE — the one real wall)":
        "batch E3 made the FUNCTION replayable: marked_runway_on(ticker, entry, stop, level_map, "
        "wall_high) passes the map and the session high straight in, so neither _effective_map's "
        "live store nor _curl_feed's recorder fetch is touched. What injection CANNOT fix: no map "
        "snapshot was ever recorded. The level-map store is mutated all day (night sheet -> vision "
        "re-reads -> auto-map overlay on a freshness breach), so the map a past row was decided "
        "under is unrecoverable — every day <= 2026-08-17 stays un-replayable for runway, "
        "permanently. Batch E3b started the recording (map_break/map_targets/map_next_supply/"
        "map_zone/map_age_min/map_src on every triggered row); 2026-08-18 is the first day the "
        "archive can reconstruct.",
    "_zf_pm_floor (the zone_flip lane itself IS lifted — batch E2)":
        "the premarket-zone computation still reads the live premarket store via _curl_feed. A "
        "study supplies the floor explicitly through the zone_flip lane's REQUIRED ctx field "
        "'pm_floor' ({zone, src, open930}); the harness refuses to run the lane without it rather "
        "than defaulting to a zone it invented.",
    "flat_top RETEST arm/reclaim (the break-attack DETECTION is now lifted — batch D 8/17)":
        "the break/arm/attack verdict, the base stats and the VWAP gate were extracted 8/17 into "
        "flat_top_step/_ft_window_stats/_ft_vwap_veto/_ft_attack_window/_ft_attack_stop, which "
        "the live loop CALLS — replay them with replay_flat_top(). What did NOT move, and cannot "
        "without faking the stream: the retest state machine (arm ts + PULLBACK_TIMEOUT_SECS on "
        "time.time(), _recent_low_dip/_confirm_reclaim on the live 1-min tape), which is why "
        "`armed` is a REQUIRED ctx field a study must supply rather than a thing the harness "
        "reconstructs. Also still live-only (both OBSERVE-ONLY today, neither can block a "
        "break-attack fire): get_daily_levels/daily_first_ok and compute_room.",
    "sizing chain (full)":
        "PARTIAL. _scaled_risk IS lifted (real). The rest of the chain (risk shares vs notional "
        "shares, VWAP-side halving, MAX_POS_VOL_PCT volume cap) is INLINE in execute_trade's "
        "body, not a function, and its volume cap re-fetches 1-min bars. sizing_chain() below "
        "calls the REAL _scaled_risk and the REAL constants; the clamp arithmetic is mirrored "
        "and PINNED by rig section BH against the bot's own source lines.",
}


# ─────────────────── bars normalisation ───────────────────
def norm_bars(raw, day=None):
    """Normalise a name-day's 10s bars to the live feed's tuple shape [(k,o,h,l,c,v),...],
    k = EPOCH SECONDS (what the live detectors receive).  Accepts:
      * data/killtests/bars10s_0817_full/*.json  {"bars":[{utc,open,high,low,close,volume,pv}]}
        (utc = seconds past UTC midnight -> `day` required)
      * data/killtests/bars10s_0817/*.json       {"bars":[{time:"...Z",open,...}]}
      * already-tuple lists (passed through)
    """
    out = []
    if not raw:
        return out
    if isinstance(raw, dict):
        raw = raw.get("bars") or []
    if raw and isinstance(raw[0], (list, tuple)):
        return [tuple(b) for b in raw]
    base = None
    if day:
        y, m, d = (int(x) for x in day.split("-"))
        base = _dt.datetime(y, m, d, tzinfo=_dt.timezone.utc).timestamp()
    for b in raw:
        if "utc" in b:
            if base is None:
                raise HarnessError("bars carry 'utc' seconds-of-day: pass day='YYYY-MM-DD'")
            k = int(base + int(b["utc"]))
        elif "time" in b:
            k = int(_dt.datetime.strptime(str(b["time"])[:19], "%Y-%m-%dT%H:%M:%S")
                    .replace(tzinfo=_dt.timezone.utc).timestamp())
        elif "k" in b:
            k = int(b["k"])
        else:
            raise HarnessError("bar has no utc/time/k field: " + repr(b)[:120])
        out.append((k,
                    float(b.get("open") or b.get("o") or 0),
                    float(b.get("high") or b.get("h") or 0),
                    float(b.get("low") or b.get("l") or 0),
                    float(b.get("close") or b.get("c") or 0),
                    float(b.get("volume") or b.get("v") or 0)))
    out.sort(key=lambda x: x[0])
    return out


def running_vwap(raw, day=None):
    """Session-anchored running VWAP per bar index, from pv when the file carries it (exact)
    else typical-price x volume (approximate).  Returns list aligned to norm_bars() output.

    PARITY CAVEAT — read this before trusting a vwap-gated lane:
    live passes ONE vwap SCALAR per rescan (`_vr_sv` = the recorder's tick-VWAP when sane,
    else the bar line) applied to the WHOLE batch of new bars.  This is a per-bar running
    line from a different source.  On vwap-gated lanes (bandpass/prevwap/v2/grinder/hidden)
    that is the largest single parity risk, and the parity doc quantifies it.
    """
    if isinstance(raw, dict):
        raw = raw.get("bars") or []
    if not raw or isinstance(raw[0], (list, tuple)):
        raise HarnessError("running_vwap needs dict bars (needs volume/pv)")
    out, num, den = [], 0.0, 0.0
    for b in raw:
        v = float(b.get("volume") or b.get("v") or 0)
        pv = b.get("pv")
        if pv is None:
            h = float(b.get("high") or b.get("h") or 0)
            l = float(b.get("low") or b.get("l") or 0)
            c = float(b.get("close") or b.get("c") or 0)
            pv = ((h + l + c) / 3.0) * v
        num += float(pv); den += v
        out.append(round(num / den, 4) if den > 0 else 0.0)
    return out


# ─────────────────── the lane registry + ctx contract ───────────────────
# ctx_required : keys the caller MUST supply (value may be None; the KEY may not be absent)
# needs_vwap   : the detector is vwap-gated -> a vwap_provider is MANDATORY
LANES = {
    "kevseq": {
        "fn": "kevseq_step", "needs_vwap": True,
        "ctx_required": ("front_side", "day_gain", "top3", "blue_sky"),
        "state": ("_ks_st", "_ks_1m_agg"),
        "call": lambda F, sym, nb, vwap, ctx: F(sym, nb, vwap, ctx),
    },
    "grinder": {
        "fn": "grinder_shadow_step", "needs_vwap": True, "ctx_required": (),
        "state": ("_gr_st",),
        "call": lambda F, sym, nb, vwap, ctx: F(sym, nb, vwap),
    },
    "bandpass": {          # RTH lane: 09:30-16:00 ET window, exactly the live call
        "fn": "bandpass_step", "needs_vwap": True, "ctx_required": (),
        "state": ("_bp_st",), "window": (570, 960), "st_map": "_bp_st",
        "call": None,
    },
    "prevwap": {           # Kev's 8AM PRE lane: 07:00-09:25 ET
        "fn": "bandpass_step", "needs_vwap": True, "ctx_required": (),
        "state": ("_pv_st",), "window": (420, 565), "st_map": "_pv_st",
        "call": None,
    },
    "v2": {
        "fn": "v2_pullback_step", "needs_vwap": True, "ctx_required": (),
        "state": ("_v2_st", "_v2_hist"),
        "call": lambda F, sym, nb, vwap, ctx: F(sym, nb, vwap),
    },
    "reclaim": {           # 8/18: kev_reclaim_step (the 3-gate VWAP-reclaim grammar). Same
                           # (sym, new_bars, vwap) shape as grinder/v2/hidden; returns
                           # {'px','stop','wick_low','seq','k'} on the curl, so unlike hidden
                           # it DOES emit a detector price (the fire bar close) and can be
                           # graded on price+stop without borrowing the live quote.
        "fn": "kev_reclaim_step", "needs_vwap": True, "ctx_required": (),
        "state": ("_reclaim_st",),
        "call": lambda F, sym, nb, vwap, ctx: F(sym, nb, vwap),
    },
    "hidden": {
        "fn": "hidden_entry_step", "needs_vwap": True, "ctx_required": (),
        "state": ("_he_st",),
        "call": lambda F, sym, nb, vwap, ctx: F(sym, nb, vwap),
        # WAS BLOCKED (8/17 morning): the detector lifted and ARMED correctly, but every fire was
        # eaten by the _bucket_fresh(k) wall-clock stale-guard (IVF: 78 suppressions, 0 fires).
        # UNBLOCKED by batch E1 — replay() now drives the bot's own _BUCKET_NOW hook to the fed
        # slice's bar epoch, so the guard measures the same age the live machine measured.
    },
    "zone_flip": {          # 8/17 batch E2 — the Z1/Z2/Z3 premarket-zone flip
        "fn": "kev_zoneflip_step", "needs_vwap": False,
        # pm_floor is REQUIRED and never defaulted: it is the live premarket store's output
        # ({"zone": float, "src": str, "open930": float}). None means "no zone" -> the detector
        # returns None on every bar, which is a legitimate (and honest) study result.
        "ctx_required": ("pm_floor",),
        "state": ("_zf_st",),
        "call": lambda F, sym, nb, vwap, ctx: F(sym, nb, pm_floor=ctx["pm_floor"]),
    },
    "flat_top": {
        # 8/17 batch D. NOT driven by replay(): this lane is 3-MIN-bar driven (Kev's setup
        # timeframe) and needs the WHOLE session's base, not the new-bar slice every 10s lane
        # takes. Use replay_flat_top() — replay() refuses it by name so nobody silently feeds
        # it 10s tuples and reports the number.
        "fn": "flat_top_step", "needs_vwap": True,
        "ctx_required": ("armed", "time_hm", "ma_first", "ma_only_window"),
        "state": (), "call": None,
        "driver": "replay_flat_top",
    },
    "ignition10s": {
        "fn": "ignition_10s_step", "needs_vwap": False, "ctx_required": (),
        "state": ("_ig10_st",),
        "call": lambda F, sym, nb, vwap, ctx: F(sym, nb),
    },
}


def reset_state(lane=None, sym=None):
    """Clear the module-level per-name machine dicts the way a fresh name-day does live.
    ALWAYS call between name-days — the live bot gets a new process/day-key; a replay does
    not, and stale state is a silent parity killer."""
    N = ns()
    lanes = [lane] if lane else list(LANES)
    for ln in lanes:
        for d in LANES[ln]["state"]:
            m = N.get(d)
            if isinstance(m, dict):
                m.pop(sym, None) if sym else m.clear()


def _check_ctx(lane, ctx):
    req = LANES[lane]["ctx_required"]
    if not req:
        return {}
    if ctx is None:
        raise MissingContext(
            f"lane '{lane}' requires ctx {list(req)} — got None. The harness will NOT default; "
            "supply the fields explicitly (this is the front-side hole, encoded).")
    missing = [k for k in req if k not in ctx]
    if missing:
        raise MissingContext(
            f"lane '{lane}': missing ctx field(s) {missing} (supplied: {sorted(ctx)}). "
            "A value of None is allowed and means 'unknown'; ABSENCE is not.")
    return {k: ctx[k] for k in req}


# ─────────────────── the replay entry point ───────────────────
def replay(sym, bars, lanes, ctx_provider=None, vwap_provider=None, day=None,
           batch_secs=None, reset=True, allow_blocked=False, fed_slices=None):
    """Drive the BOT'S OWN detectors over one name-day's 10s bars.

    sym            ticker (the detectors key their state on it)
    bars           raw bar list/dict (see norm_bars) or normalised tuples
    lanes          list of LANES keys
    ctx_provider   f(sym, i, bar, lane) -> dict.  MANDATORY for any lane with ctx_required.
                   Must contain every required key; MissingContext otherwise.
    vwap_provider  f(sym, i, bar, lane) -> float.  MANDATORY for vwap-gated lanes.
    day            'YYYY-MM-DD' (needed for 'utc' bars and to freeze the replay clock)
    batch_secs     None  = one bar per detector call (max resolution; >= live fire count)
                   60    = mimic the live 60s rescan cadence.  MATTERS: every detector
                          returns AT MOST ONE fire per call, so batching SUPPRESSES fires.
                          Live cadence is the 60s rescan -> use 60 for parity work.
    fed_slices     [(k0, k1), ...] — the EXACT bucket-epoch ranges the live bot fed, taken
                   from the A2 provenance stamps (fed_k0/fed_k1 on every fire row, shipped
                   2026-08-17). Supplying this makes the replay a TRUE EQUIVALENCE TEST: the
                   detector sees the same bars, in the same calls, in the same order the live
                   machine saw them, so a disagreement can only be the detector. Overrides
                   batch_secs. Ranges are inclusive of both ends and are fed in the order
                   given; a range that selects no bars is fed as an EMPTY call (live does not
                   call the detector at all on an empty slice, so those are skipped).
                   ONLY days whose rows carry the stamps (2026-08-18 onward) support this;
                   for earlier days the honest tool is batch_secs=60 and the result is an
                   approximation, not an equivalence.
    Returns list of fire dicts with the live decision-row fields plus harness stamps
    (lane, sym, i, bar, ctx, vwap).
    """
    if day:
        set_replay_day(day)
    B = norm_bars(bars, day=day)
    N = ns()
    for ln in lanes:
        if ln not in LANES:
            raise HarnessError(f"unknown lane '{ln}' (have {sorted(LANES)})")
        if LANES[ln].get("driver"):
            raise HarnessError(
                f"lane '{ln}' has its own driver: call {LANES[ln]['driver']}(). replay() feeds "
                "10s new-bar slices; this lane is 3-min-bar/whole-session driven and would be "
                "silently wrong here.")
        if LANES[ln].get("blocked") and not allow_blocked:
            raise HarnessError(
                f"lane '{ln}' is NOT REPLAYABLE: {LANES[ln]['blocked']}. Pass "
                "allow_blocked=True only to study the pre-fire state, and never report its "
                "fire counts as live-comparable.")
        if LANES[ln]["needs_vwap"] and vwap_provider is None:
            raise MissingContext(
                f"lane '{ln}' is VWAP-gated: a vwap_provider is mandatory (live passes the "
                "session line into the detector; a replay that omits it silently changes the gate)")
        if LANES[ln]["ctx_required"] and ctx_provider is None:
            raise MissingContext(
                f"lane '{ln}' requires ctx {list(LANES[ln]['ctx_required'])} but no ctx_provider "
                "was given — refusing to run rather than defaulting.")
        if reset:
            reset_state(ln, sym)

    out = []
    # build the call batches
    batches = []
    if fed_slices:
        # EXACT fed stream from the live provenance stamps — one call per live call.
        for k0, k1 in fed_slices:
            sel = [i for i, b in enumerate(B) if k0 <= b[0] <= k1]
            if sel:
                batches.append(sel)
    elif not batch_secs:
        batches = [[i] for i in range(len(B))]
    else:
        cur, cur_k = [], None
        for i, b in enumerate(B):
            slot = b[0] // batch_secs
            if cur_k is None or slot == cur_k:
                cur.append(i); cur_k = slot
            else:
                batches.append(cur); cur, cur_k = [i], slot
        if cur:
            batches.append(cur)

    # batch E1: drive the bot's own stale-fire clock off the tape instead of the wall.
    # THE VALUE, and why: live, `_bucket_fresh` measures (time.time() - k) at the moment the
    # rescan hands the slice over — which is at the earliest the instant the newest bucket
    # CLOSED, i.e. k_last + 10.  That is the tightest defensible reconstruction and the one
    # most FAVOURABLE to the guard's own limit being met, so it can only over-count fires
    # relative to a live cycle that arrived later; the parity doc states that direction.
    # It is exact in relative terms for every OLDER bar in the same slice, which is what the
    # 90s ceiling (60s PRE) actually discriminates on.
    _install_bar_clock()

    for batch in batches:
        i_last = batch[-1]
        nb = [B[i] for i in batch]
        set_bar_now(B[i_last][0] + 10)
        for ln in lanes:
            L = LANES[ln]
            F = fn(L["fn"])
            bar = B[i_last]
            vwap = float(vwap_provider(sym, i_last, bar, ln)) if L["needs_vwap"] else 0.0
            ctx = _check_ctx(ln, ctx_provider(sym, i_last, bar, ln) if ctx_provider else None)
            if ln == "v2":
                # live keeps _v2_hist fed by the caller (bot :8285) so v2_trailing_calm has a
                # causal buffer; mirror that feed EXACTLY here, before stepping.
                h = N["_v2_hist"].setdefault(sym, [])
                h.extend(nb)
                del h[:-max(200, int(N["V2_QUIET_LOOK"]) * 4)]
            if L.get("call"):
                r = L["call"](F, sym, nb, vwap, ctx)
            else:                                      # bandpass/prevwap: st_map + window
                lo, hi = L["window"]
                r = F(sym, nb, vwap, N[L["st_map"]], lo, hi)
            if r:
                r = dict(r)
                r.update({"lane": ln, "sym": sym, "i": i_last, "bar": bar,
                          "vwap": round(vwap, 4), "ctx": ctx})
                out.append(r)
    set_bar_now(None)
    return out


# ─────────────── flat_top / break-attack driver (8/17 batch D) ───────────────
def bars10s_to_m1(B):
    """Roll normalised 10s tuples [(k,o,h,l,c,v)] into the 1-min DICT bars the flat-top path
    reads (ISO-UTC 'time' + full-name OHLCV) — the shape get_intraday_bars returns, which is
    what aggregate_bars()/_latest_session() key off. Bars are stamped at the minute's START,
    exactly like the broker's M1."""
    out, key, cur = [], None, None
    for k, o, h, l, c, v in B:
        slot = int(k) // 60
        if slot != key:
            if cur:
                out.append(cur)
            key = slot
            cur = {"time": _dt.datetime.fromtimestamp(slot * 60, _dt.timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "open": o, "high": h, "low": l, "close": c, "volume": v}
        else:
            cur["high"] = max(cur["high"], h)
            if l > 0:
                cur["low"] = min(cur["low"], l) if cur["low"] > 0 else l
            cur["close"] = c
            cur["volume"] += v
    if cur:
        out.append(cur)
    return out


def replay_flat_top(sym, bars, day, vwap_provider, ctx_provider, cadence_secs=60,
                    every_bar=False):
    """Drive the BOT'S OWN flat_top_step over one name-day.

    Mirrors the live pipeline exactly: 10s tape -> 1-min bars -> aggregate_bars(SETUP_TF_MIN)
    -> drop the incomplete last bar -> _latest_session() -> flat_top_step(). Every one of
    those steps is the bot's real function object (bars10s_to_m1 is the only harness-side
    roll, and it is the broker's own minute bucketing, pinned by rig section BD).

    ctx_provider  f(sym, i, bar) -> dict with ALL FOUR required keys. MANDATORY — no
                  defaulting (see the contract note at the top of this module).
    cadence_secs  60 = the live rescan cadence (one decision per minute). every_bar=True
                  evaluates on each 10s bar (upper bound on fires, not live-comparable).

    Returns every decision dict flat_top_step produced whose action != 'none', stamped with
    the bar index / epoch / vwap / ctx.

    BOUND, stated not hidden: `armed` (the retest arm) is NOT reconstructed here — the arm
    state machine is wall-clock + 1-min-tape driven and stayed inline (see NOT_ISOLABLE).
    A study must supply it; supplying armed=False measures the break-attack cell on the
    assumption no out-of-window arm was live for the name, which is the 09:30-10:30 case
    whenever the name's first break of the session happens inside the window."""
    set_replay_day(day)
    B = norm_bars(bars, day=day)
    N = ns()
    F = fn("flat_top_step")
    step = 1 if every_bar else max(1, int(cadence_secs // 10))
    out = []
    for i in range(len(B)):
        if not every_bar and (i + 1) % step:
            continue
        m1 = bars10s_to_m1(B[:i + 1])
        completed = N["aggregate_bars"](m1, N["SETUP_TF_MIN"])[:-1]
        sess3 = N["_latest_session"](completed)
        if len(sess3) < N["FLAT_TOP_WINDOW"]:
            continue
        bar = B[i]
        price = float(bar[4])
        vwap = float(vwap_provider(sym, i, bar, "flat_top"))
        ctx = _check_ctx("flat_top", ctx_provider(sym, i, bar, "flat_top"))
        d = F(sym, sess3, price, vwap, ctx)
        if d and d["action"] != "none":
            d = dict(d)
            d.update({"lane": "flat_top", "sym": sym, "i": i, "bar": bar,
                      "vwap": round(vwap, 4), "ctx": ctx})
            out.append(d)
    return out


def et_hm(k):
    """'HH:MM' ET for an epoch-second bucket — what flat_top_step's time_hm ctx wants."""
    return _dt.datetime.fromtimestamp(int(k), EASTERN).strftime("%H:%M")


# ─────────────────── sizing chain (partial-isolable; see NOT_ISOLABLE) ───────────────────
def sizing_chain(entry_price, stop_loss, balance=None, vwap=0.0, is_leader=False,
                 avg_1m_vol=None):
    """The bot's ticket-sizing chain in DOLLARS.

    REAL (lifted): _scaled_risk, RISK_PER_TRADE, RISK_PROP, RISK_PROP_REF,
                   MAX_TRADE_DOLLARS, MAX_POSITION_SIZE, MAX_POS_VOL_PCT,
                   SIM_ACCOUNT_BALANCE, VWAP_SIDE_SIZING default.
    MIRRORED     : the clamp arithmetic, because it is inline in execute_trade, not a
                   function.  Rig BH pins these lines against the bot's own source.
    Returns dict(shares, notional, risk_dollars, clamp).
    """
    N = ns()
    bal = balance if balance is not None else N["SIM_ACCOUNT_BALANCE"]
    pos_size = min(bal * N["MAX_POSITION_SIZE"], N["MAX_TRADE_DOLLARS"])
    if entry_price <= stop_loss:
        raise HarnessError("degenerate ticket: entry <= stop (the bot refuses these upstream)")
    risk_i = N["_scaled_risk"](entry_price, stop_loss)          # REAL bot function
    sh_risk = int(risk_i / (entry_price - stop_loss))
    sh_notional = int(pos_size / entry_price)
    shares = max(1, min(sh_risk, sh_notional))
    clamp = ("min_1_share" if min(sh_risk, sh_notional) < 1
             else ("risk" if sh_risk <= sh_notional else "notional"))
    vss = float(os.environ.get("VWAP_SIDE_SIZING", "0.5"))
    if vss < 1.0 and vwap and vwap > 0 and entry_price >= vwap and not is_leader:
        shares = max(1, int(shares * vss)); clamp += "+vwap_side"
    if N["MAX_POS_VOL_PCT"] and avg_1m_vol:
        cap = max(1, int(avg_1m_vol * N["MAX_POS_VOL_PCT"]))
        if shares > cap:
            shares = cap; clamp = "volume"
    return {"shares": shares, "notional": round(shares * entry_price, 2),
            "risk_dollars": round(shares * (entry_price - stop_loss), 2),
            "scaled_risk": round(risk_i, 2), "clamp": clamp}


def isolability_report():
    """What lifts and what does not — machine-checked, so the doc can never go stale."""
    rep = {"isolable": {}, "not_isolable": dict(NOT_ISOLABLE)}
    for s in ALL_SYMBOLS:
        try:
            rep["isolable"][s] = type(fn(s)).__name__
        except Exception as e:            # pragma: no cover — a red rig, by design
            rep["isolable"][s] = f"FAILED: {e}"
    return rep


if __name__ == "__main__":
    print(json.dumps(isolability_report(), indent=2))
