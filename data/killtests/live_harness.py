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
    n = {
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


def check_momentum_on(ticker, m1_bars):
    """Run the bot's REAL check_momentum against a supplied 1-min bar fixture.

    check_momentum's BODY is pure; only its input is live (`get_intraday_bars(ticker, ...)`).
    So it IS liftable — but a replay must hand it the bars, and it routes them through
    _fresh_session(), which keeps TODAY's bars only.  Two consequences a study must respect:
      * m1_bars must carry the same ISO 'time' shape the broker returns;
      * replaying a PAST day yields an empty session -> check_momentum's own
        insufficient-data path, NOT a real read.  Use only for same-day work, or state the
        bound in the doc.  This is disclosed, never silently defaulted.
    """
    N = ns()
    prev = N.get("get_intraday_bars")
    N["get_intraday_bars"] = lambda t, count=None, sessions=None, **kw: list(m1_bars)
    try:
        return N["check_momentum"](ticker)
    finally:
        if prev is not None:
            N["get_intraday_bars"] = prev

# NOT ISOLABLE — each with its concrete blocker.  Do NOT hand-roll these in a study; if a
# study needs one, the honest move is to say so in the doc and bound the claim.
NOT_ISOLABLE = {
    "check_momentum (INJECTABLE, not free-running)":
        "the BODY lifts and is pure; the INPUT is a live broker fetch (get_intraday_bars). Use "
        "check_momentum_on(ticker, m1_bars) with a fixture. Bound: it routes through "
        "_fresh_session() (today-only), so past-day replays hit its insufficient-data path "
        "rather than a real read — disclosed, never defaulted.",
    "_marked_runway":
        "live state + network: _effective_map(ticker) reads the running level-map store and "
        "_curl_feed(ticker) hits the recorder feed for the wall high. Replayable ONLY with a "
        "recorded map snapshot + tape; not available from the decisions archive.",
    "kev_zoneflip_step":
        "wall-clock + live store: _bucket_fresh(k) compares the bar bucket to time.time() "
        "(every historical bar is 'stale' -> the fire path is unreachable in replay), and "
        "_zf_pm_floor(sym) reads the premarket-zone store built during the live premarket.",
    "flat_top / break-attack":
        "not a function: the flat-top consolidation tracker + FLATTOP_BREAK_ATTACK conversion "
        "live INSIDE wait_for_flat_top_entry (~1k lines), driven by a WebullStream object, a "
        "session_cache and rescan callbacks. Lifting it would require faking the stream — i.e. "
        "exactly the replica-drift this harness exists to prevent. Left un-lifted ON PURPOSE.",
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
    "hidden": {
        "fn": "hidden_entry_step", "needs_vwap": True, "ctx_required": (),
        "state": ("_he_st",),
        "call": lambda F, sym, nb, vwap, ctx: F(sym, nb, vwap),
        # PROVEN 8/17 on IVF: the detector lifts and ARMS correctly, but every fire is eaten by
        # the _bucket_fresh(k) wall-clock stale-guard (bar age vs time.time()), so the fire path
        # is structurally unreachable in replay. Opt in ONLY to study the ARM/setup side, and
        # never report "hidden fires" from it.
        "blocked": "_bucket_fresh wall-clock stale-guard suppresses 100% of replay fires",
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
           batch_secs=None, reset=True, allow_blocked=False):
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
    if not batch_secs:
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

    for batch in batches:
        i_last = batch[-1]
        nb = [B[i] for i in batch]
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
    return out


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
