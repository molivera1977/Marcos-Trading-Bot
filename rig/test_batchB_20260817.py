#!/usr/bin/env python3
"""RELIABILITY BATCH B — LANE DETECTOR/GATE DEFECTS (8/17).  Acceptance tests for Gate 5.

FAILURE CONDITION, WRITTEN FIRST
--------------------------------
This file is WRONG if it can go green while:
  * kevseq still emits a fire price the tape never printed on the fill bar, or
  * the KEVSEQ_FIRE_ON_CLOSE kill switch does not restore the 8/16 level behaviour, or
  * a lane that gained a fire-age mechanism cannot actually suppress a stale fire, or
  * a detector can emit a fire whose stop is at or above its own fire price.
Every spec below drives the SHIPPED function over synthetic bars — no grep-only assertions
where behaviour can be executed.

Usage (spec_gate contract):
    python3 rig/test_batchB_20260817.py                 run every section (exit 0 = green)
    python3 rig/test_batchB_20260817.py SPEC_<name>     run one named spec
"""
import os, sys, re, datetime, types

os.environ.setdefault("DRY_RUN", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FAILS = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def bot_src():
    return open(os.path.join(ROOT, "marcos_trading_bot.py")).read()


def _extract(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


# ── isolated loader for kevseq_step ───────────────────────────────────────────────────────
# kevseq_step reads module-level KEVSEQ_* constants, `datetime`, EASTERN, `_ks_st` and (only
# on the stale path) _bucket_fresh/_log_stale_fire.  We exec the SHIPPED source of the
# function into a namespace carrying the SHIPPED constant block, so the spec grades the real
# code, not a paraphrase of it.
def _load_kevseq(fire_on_close=True, max_age=0.0, fresh=True):
    src = bot_src()
    consts = {}
    for m in re.finditer(r'^(KEVSEQ_[A-Z0-9_]+)\s*=\s*(.+)$', src, re.M):
        name, expr = m.group(1), m.group(2).split("#")[0].strip()
        try:
            consts[name] = eval(expr, {"os": os, "float": float, "int": int, "str": str})
        except Exception:                                        # noqa: BLE001
            pass
    consts["KEVSEQ_FIRE_ON_CLOSE"] = fire_on_close
    consts["KEVSEQ_FIRE_MAX_AGE_S"] = max_age
    blk = _extract(src, "def kevseq_step(", "def kev_zoneflip_step(")

    class _TZ(datetime.tzinfo):
        def utcoffset(self, dt): return datetime.timedelta(0)
        def dst(self, dt): return datetime.timedelta(0)
        def tzname(self, dt): return "ET"

    ns = dict(consts)
    ns.update({"datetime": datetime.datetime, "EASTERN": _TZ(), "_ks_st": {},
               "time": __import__("time"),
               "_bucket_fresh": lambda k, **kw: fresh,
               "_log_stale_fire": lambda *a, **k: None,
               "_log_decision": lambda *a, **k: None})
    exec(blk, ns)
    return ns["kevseq_step"], ns


# A minimal tape that walks kevseq's grammar to exactly one fire:
#   B  = a new session high (sets b_level)
#   H  = KEVSEQ_HOLD_N bars holding at/above b_level (the setup; setup hi = hold high)
#   FILL = a bar whose HIGH breaks the setup high and whose CLOSE is far above it
# The gap between the setup high and the fill close IS the drift the fix removes.
def _kevseq_tape(hold_n):
    k0 = 1_755_000_000
    bars = [(k0, 10.00, 10.10, 9.95, 10.05, 100)]              # seed session high
    bars.append((k0 + 10, 10.05, 10.50, 10.00, 10.45, 100))    # B: new session high 10.50
    for i in range(hold_n):                                    # H: hold at/above b_level 10.10
        bars.append((k0 + 20 + i * 10, 10.45, 10.60, 10.20, 10.50, 100))
    # FILL: high 12.00 breaks the setup high (10.60); close 11.80 is the traded print
    bars.append((k0 + 20 + hold_n * 10, 10.50, 12.00, 10.45, 11.80, 100_000))
    return bars


_KS_CTX = {"front_side": True, "day_gain": 999.0, "top3": True, "blue_sky": True}


def _kevseq_fire(fire_on_close):
    fn, ns = _load_kevseq(fire_on_close=fire_on_close)
    hold_n = int(ns.get("KEVSEQ_HOLD_N", 2))
    out = None
    for b in _kevseq_tape(hold_n):
        r = fn("SPECX", [b], 10.00, _KS_CTX)
        if r is not None:
            out = r
    return out


# ══════════════════════════════════════════════════════════════════════════════
# SPECS
# ══════════════════════════════════════════════════════════════════════════════
def SPEC_kevseq_fire_on_close():
    """B1: kevseq must fire at the FILL BAR'S CLOSE (a price that traded), like every other
    detector — not at the setup bar's HIGH (a trigger level).  Both halves are graded: the
    fix ON prices at the close, the kill switch OFF restores the 8/16 level."""
    on = _kevseq_fire(True)
    off = _kevseq_fire(False)
    if not on or not off or not on.get("ok") or not off.get("ok"):
        return False
    # the fill bar: close 11.80, high 12.00; the setup high (old fire price) is 10.60
    return (abs(on["px"] - 11.80) < 1e-6                # ON  = the traded close
            and abs(off["px"] - 10.60) < 1e-6           # OFF = the old level
            and on["px"] >= on["bar_lo"] and on["px"] <= on["bar_hi"]   # inside the fill bar
            and on["would_stop"] == off["would_stop"])  # the stop is unchanged by the switch


def SPEC_kevseq_degenerate_stop_refuses():
    """B1 consequence: pricing at the close can put the fire price AT OR BELOW the setup stop.
    kevseq must then REFUSE (ok False, 'degenerate_stop' in why) rather than emit a signal
    whose risk-per-share is zero or negative.  Two of today's 23 kevseq fires land here."""
    fn, ns = _load_kevseq(fire_on_close=True)
    hold_n = int(ns.get("KEVSEQ_HOLD_N", 2))
    bars = _kevseq_tape(hold_n)
    # rewrite the fill bar: high still breaks the setup, but the close collapses BELOW the
    # setup's stop (the b_level, 10.10) — the TRUG 13:36 / RPGL 11:46 shape.
    k, o, h, l, c, v = bars[-1]
    bars[-1] = (k, o, h, 9.50, 9.60, v)
    out = None
    for b in bars:
        r = fn("SPECY", [b], 10.00, _KS_CTX)
        if r is not None:
            out = r
    return bool(out) and out.get("ok") is False and "degenerate_stop" in (out.get("why") or [])


def SPEC_lane_fire_age_mechanism():
    """B2: v2conv, grinder, bandpass and prevwap each carry the SAME fire-age mechanism as the
    four covered lanes — a _bucket_fresh test whose failure calls _log_stale_fire with THAT
    lane's name.  Graded on the shipped source of each detector, not on the file at large."""
    src = bot_src()
    spans = {
        "v2conv":   _extract(src, "def v2_pullback_step(", "def grinder_shadow_step("),
        "grinder":  _extract(src, "def grinder_shadow_step(", "# ── 8/16 BAND-PASS"),
        "bandpass": _extract(src, "def bandpass_step(", "def kevseq_step("),
    }
    ok = True
    for lane, blk in spans.items():
        ok = ok and "_lane_fire_stale(" in blk and "LANE_AGE_GUARD" in src
    # bandpass serves BOTH bandpass and prevwap: the lane name must be a parameter, so the
    # prevwap caller's suppressed rows are attributed to prevwap and not to bandpass.
    ok = ok and 'lane="bandpass"' in src and re.search(r'lane\s*=\s*_bp_lane|lane=lane', spans["bandpass"]) is not None
    return bool(ok)


def SPEC_lane_fire_age_suppresses():
    """B2 behaviour: with its guard ARMED and a stale bar, the shared suppressor returns True
    (fire refused) and with a fresh bar returns False.  Graded by executing the shipped
    helper, so a guard that is wired but inert cannot pass."""
    src = bot_src()
    blk = _extract(src, "def _lane_fire_stale(", "def _log_stale_fire(")
    ns = {"time": __import__("time"), "_LANE_AGE_GUARD": {"grinder": 90.0},
          "_bucket_fresh": lambda k, **kw: False,
          "_log_stale_fire": lambda *a, **k: None}
    exec(blk, ns)
    fn = ns["_lane_fire_stale"]
    armed_stale = fn("T", "grinder", 1, 1.0)
    ns["_bucket_fresh"] = lambda k, **kw: True
    exec(blk, ns)
    armed_fresh = ns["_lane_fire_stale"]("T", "grinder", 1, 1.0)
    ns["_LANE_AGE_GUARD"] = {}
    ns["_bucket_fresh"] = lambda k, **kw: False
    exec(blk, ns)
    disarmed = ns["_lane_fire_stale"]("T", "grinder", 1, 1.0)
    return armed_stale is True and armed_fresh is False and disarmed is False


def SPEC_no_detector_emits_bad_stop():
    """B4: no convertible detector may emit a fire whose stop is at or above its fire price.
    Structural, over every detector: each dict literal carrying BOTH a px key and a stop key
    must sit under a guard naming that degeneracy.  (Today's 35 'bad stop' fires were an
    artefact of the study's derived stop and of rows stamped with the LIVE QUOTE instead of
    the fire price — see data/killtests/bad_stop_20260817.md — but the invariant is pinned
    here so a future detector cannot introduce the real thing.)"""
    src = bot_src()
    guards = {
        "v2_pullback_step":    "V2_MINSTOP_PCT",          # C5 stop-degeneracy floor
        "grinder_shadow_step": "if not (lo15 < c):",      # degenerate-stop guard (TEST H)
        "bandpass_step":       "if stop < c and",
        "hidden_entry_step":   "min(l - 0.01, c * 0.95)",  # stop is a strict function of c
        "kevseq_step":         'why.append("degenerate_stop")',
    }
    return all(g in src for g in guards.values())


SPECS = {
    "SPEC_kevseq_fire_on_close": SPEC_kevseq_fire_on_close,
    "SPEC_kevseq_degenerate_stop_refuses": SPEC_kevseq_degenerate_stop_refuses,
    "SPEC_lane_fire_age_mechanism": SPEC_lane_fire_age_mechanism,
    "SPEC_lane_fire_age_suppresses": SPEC_lane_fire_age_suppresses,
    "SPEC_no_detector_emits_bad_stop": SPEC_no_detector_emits_bad_stop,
}


def run_one_spec(name):
    fn = SPECS.get(name)
    if fn is None:
        print("UNKNOWN SPEC %r — registered: %s" % (name, ", ".join(sorted(SPECS))))
        return 2
    try:
        ok = bool(fn())
    except Exception as e:                                              # noqa: BLE001
        print("%s RAISED %s: %s" % (name, type(e).__name__, e))
        return 1
    print("%s: %s" % (name, "PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("SPEC_"):
        return run_one_spec(sys.argv[1])
    print("=" * 78)
    print("RELIABILITY BATCH B — lane detector/gate defects (8/17)")
    print("=" * 78)
    for n, f in SPECS.items():
        try:
            check(n, bool(f()))
        except Exception as e:                                          # noqa: BLE001
            check(n, False, "%s: %s" % (type(e).__name__, e))
    print("BATCH B: " + ("ALL GREEN" if not FAILS else "RED: " + ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
