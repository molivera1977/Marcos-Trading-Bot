#!/usr/bin/env python3
"""FOUNDATION BATCH D — BREAK-ATTACK MADE TESTABLE (8/17). Acceptance tests for Gate 5.

FAILURE CONDITION, WRITTEN FIRST
--------------------------------
This file is WRONG if it can go green while ANY of these is true:
  * the live loop does not actually CALL the extracted core (i.e. the extraction is a second
    implementation sitting beside the live one — the study-replica disease, again);
  * flat_top_step disagrees with the PRE-REFACTOR inline logic on any (base, price, vwap,
    armed, clock) combination — the differential grid below is the check, and it replays the
    old expressions verbatim, not a paraphrase of them;
  * the three REAL break-attack triggers of 2026-08-17 (IPST/CDTG/LBGJ, 09:30) do not
    reproduce as action='attack', ok=True, stop=base low;
  * the out-of-window / kill-switch / below-VWAP / already-armed paths change verdict;
  * the harness can be handed the flat_top lane without a ctx, or through replay() (which
    feeds 10s new-bar slices this 3-min lane must never be graded on).

Everything below drives the SHIPPED function objects, lifted by data/killtests/live_harness.py's
AST loader — no import of the bot (that is a live trading path), no re-implementation.

Usage (spec_gate contract):
    python3 rig/test_batchD_20260817.py                 run every section (exit 0 = green)
    python3 rig/test_batchD_20260817.py SPEC_<name>     run one named spec
"""
import ast
import os
import sys

os.environ.setdefault("DRY_RUN", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "data", "killtests"))
FAILS = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def bot_src():
    return open(os.path.join(ROOT, "marcos_trading_bot.py")).read()


def H():
    import live_harness
    return live_harness


def _step():
    return H().fn("flat_top_step")


def _base(w_high, w_low, n=None):
    """A synthetic flat-top base: n completed 3-min session bars whose max high is w_high and
    min low is w_low (the only two statistics the base contributes)."""
    n = n or int(H().const("FLAT_TOP_WINDOW"))
    mid = (w_high + w_low) / 2.0
    bars = [{"time": "2026-08-17T13:%02d:00Z" % (30 + i * 3),
             "open": mid, "high": mid, "low": mid, "close": mid, "volume": 1000}
            for i in range(n)]
    bars[0]["high"] = w_high
    bars[-1]["low"] = w_low
    return bars


CTX0 = {"armed": False, "time_hm": "09:45", "ma_first": False, "ma_only_window": False}


def _ctx(**kw):
    c = dict(CTX0)
    c.update(kw)
    return c


# ── the PRE-REFACTOR inline logic, transcribed verbatim from the parent commit's
#    wait_for_flat_top_entry (lines "window = _sess3[-FLAT_TOP_WINDOW:]" ... the VWAP gate and
#    the attack stop).  This is the differential control: it must never be "cleaned up".
def _old_path(N, sess3, price, vwap, pb, hm):
    FLAT_TOP_WINDOW = N["FLAT_TOP_WINDOW"]
    FLAT_TOP_MAX_RANGE = N["FLAT_TOP_MAX_RANGE"]
    FLATTOP_BREAK_ATTACK = N["FLATTOP_BREAK_ATTACK"]
    if len(sess3) < FLAT_TOP_WINDOW:
        return None
    window = sess3[-FLAT_TOP_WINDOW:]
    highs = [float(b.get("high") or b.get("h") or b.get("close") or b.get("c") or 0) for b in window]
    lows = [float(b.get("low") or b.get("l") or b.get("close") or b.get("c") or 0) for b in window]
    w_high = max(h for h in highs if h > 0)
    w_low = min(l for l in lows if l > 0)
    out = {"w_high": w_high, "w_low": w_low, "rng": None, "is_flat": None,
           "action": "none", "ok": False, "stop": None}
    if w_low > 0:
        rng = (w_high - w_low) / w_low
        is_flat = rng <= FLAT_TOP_MAX_RANGE
        out["rng"], out["is_flat"] = rng, is_flat
        _ft_attack = False
        if is_flat and price > w_high and not pb:
            if FLATTOP_BREAK_ATTACK and "09:30" <= hm < "10:30":
                _ft_attack = True
                out["action"] = "attack"
            else:
                out["action"] = "arm"
                return out
        if _ft_attack:
            if vwap <= 0:
                return out
            if price < vwap:
                return out
            out["stop"] = round(w_low, 4)
            out["ok"] = True
    return out


# ══════════════════════════════════════════════════════════════════════════════
# SPECS
# ══════════════════════════════════════════════════════════════════════════════
def SPEC_break_attack_extracted_and_live_calls_it():
    """D1: the break-attack decision core exists as a pure, callable, bar-driven function AND
    the live loop calls it. Both halves matter: a pure core the live path ignores is a
    replica, which is the exact disease this batch exists to cure."""
    ok = True
    fn = _step()
    ok &= callable(fn)
    check("D1 flat_top_step lifts as a real function object", callable(fn))

    tree = ast.parse(bot_src())
    wf = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "wait_for_flat_top_entry"), None)
    called = {c.func.id for c in ast.walk(wf) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)} if wf else set()
    for name in ("flat_top_step", "_ft_vwap_veto", "_ft_attack_stop"):
        hit = name in called
        ok &= hit
        check(f"D1 live loop CALLS {name}", hit)

    # and the inline duplicates are GONE (one implementation, not two)
    src = bot_src()
    body = src[src.index("def wait_for_flat_top_entry("):]
    for dead in ('if FLATTOP_BREAK_ATTACK and "09:30" <= _hm_ft < "10:30":',
                 "w_high = max(h for h in highs if h > 0)"):
        gone = dead not in body
        ok &= gone
        check(f"D1 inline duplicate removed: {dead[:44]!r}", gone)
    return ok


def SPEC_break_attack_live_fixtures_0817():
    """D2: the three REAL break-attack triggers of 2026-08-17, replayed through the extracted
    core from the archive's own prices/levels (decisions_archive status=break_attack:
    IPST 09:30:45, CDTG 09:30:47, LBGJ 09:30:47). Same verdict, same stop, or RED."""
    fn = _step()
    LIVE = [  # ticker, price, w_high, w_low  (verbatim from the 8/17 archive rows)
        ("IPST", 8.155, 8.09, 7.46),
        ("CDTG", 2.17, 2.09, 2.0008),
        ("LBGJ", 3.16, 3.10, 3.07),
    ]
    ok = True
    for sym, px, wh, wl in LIVE:
        d = fn(sym, _base(wh, wl), px, wl * 0.9,      # live fired => price was >= VWAP
               _ctx(time_hm="09:30"))
        good = (d and d["action"] == "attack" and d["ok"] is True
                and d["break_attack"] is True
                and abs(d["w_high"] - wh) < 1e-9 and abs(d["w_low"] - wl) < 1e-9
                and d["stop"] == round(wl, 4))
        ok &= bool(good)
        check(f"D2 {sym} reproduces the live break-attack (stop={round(wl, 4)})", bool(good),
              repr(d))
    return ok


def SPEC_break_attack_differential_vs_old_path():
    """D3: differential — extracted core vs the PRE-REFACTOR inline logic, over a synthetic
    grid spanning flat/not-flat bases, break/no-break prices, both sides of VWAP, missing
    VWAP, armed/unarmed, and in/out of the 09:30-10:30 cell. Any single disagreement = RED."""
    fn = _step()
    N = H().ns()
    n_cmp = 0
    ok = True
    for wl in (2.0008, 7.46, 10.0):
        for spread in (0.001, 0.05, 0.11, 0.13, 0.30):     # straddles FLAT_TOP_MAX_RANGE=0.12
            wh = round(wl * (1 + spread), 4)
            sess3 = _base(wh, wl)
            for pxm in (0.98, 1.0, 1.0001, 1.02):
                price = round(wh * pxm, 4)
                for vwap in (0.0, -1.0, price * 0.99, price * 1.01):
                    for pb in (None, {"level": wh, "zone": wl}):
                        for hm in ("09:29", "09:30", "10:29", "10:30", "13:05"):
                            old = _old_path(N, sess3, price, vwap, pb, hm)
                            new = fn("SPECD", sess3, price, vwap,
                                     _ctx(armed=bool(pb), time_hm=hm))
                            n_cmp += 1
                            same = (old is None) == (new is None)
                            if same and old is not None:
                                same = all(
                                    (old[k] == new[k]) or
                                    (isinstance(old[k], float) and isinstance(new[k], float)
                                     and abs(old[k] - new[k]) < 1e-12)
                                    for k in ("w_high", "w_low", "rng", "is_flat",
                                              "action", "ok", "stop"))
                            if not same:
                                ok = False
                                check("D3 differential", False,
                                      f"wl={wl} wh={wh} px={price} vwap={vwap} "
                                      f"armed={bool(pb)} hm={hm} old={old} new={new}")
                                return False
    check(f"D3 extracted core == pre-refactor inline logic on {n_cmp} combinations", ok)
    return ok


def SPEC_break_attack_gates_unchanged():
    """D4: the cell boundaries and vetoes still bite exactly as the shipped comment claims —
    out-of-window arms instead of attacking, the kill switch reverts to arming, below-VWAP
    refuses the fire, an already-armed name never attacks, and a non-flat base never breaks."""
    fn = _step()
    wh, wl = 8.09, 7.46
    b = _base(wh, wl)
    ok = True

    d = fn("X", b, 8.155, 7.0, _ctx(time_hm="10:30"))
    ok &= d["action"] == "arm"
    check("D4 10:30 is OUTSIDE the cell -> arm, not attack", d["action"] == "arm", repr(d))

    d = fn("X", b, 8.155, 7.0, _ctx(time_hm="09:29"))
    ok &= d["action"] == "arm"
    check("D4 09:29 is OUTSIDE the cell -> arm, not attack", d["action"] == "arm", repr(d))

    d = fn("X", b, 8.155, 9.99, _ctx(time_hm="09:30"))
    ok &= (d["action"] == "attack" and d["ok"] is False and "broke_below_vwap" in d["why"])
    check("D4 below VWAP refuses the fire", d["ok"] is False and "broke_below_vwap" in d["why"], repr(d))

    d = fn("X", b, 8.155, 0.0, _ctx(time_hm="09:30"))
    ok &= (d["ok"] is False and "broke_no_vwap" in d["why"])
    check("D4 no VWAP refuses the fire", d["ok"] is False and "broke_no_vwap" in d["why"], repr(d))

    d = fn("X", b, 8.155, 7.0, _ctx(time_hm="09:30", armed=True))
    ok &= d["action"] == "none"
    check("D4 an already-ARMED name never attacks (retest owns it)", d["action"] == "none", repr(d))

    d = fn("X", _base(10.0, 7.46), 10.5, 7.0, _ctx(time_hm="09:30"))
    ok &= (d["action"] == "none" and "broke_not_flat" in d["why"])
    check("D4 a non-flat base is not a flat-top break", d["action"] == "none", repr(d))

    d = fn("X", b, 8.00, 7.0, _ctx(time_hm="09:30"))
    ok &= (d["action"] == "none" and "consolidating" in d["why"])
    check("D4 price under the base high = consolidating", d["action"] == "none", repr(d))

    ok &= fn("X", b[:1], 8.155, 7.0, _ctx(time_hm="09:30")) is None
    check("D4 no base yet -> None (no decision, never a default)",
          fn("X", b[:1], 8.155, 7.0, _ctx(time_hm="09:30")) is None)

    kill = not H().fn("_ft_attack_window")("09:45") if not H().const("FLATTOP_BREAK_ATTACK") else True
    ok &= kill
    check("D4 FLATTOP_BREAK_ATTACK=0 kills the cell (env kill switch intact)", kill)
    return ok


def SPEC_harness_flat_top_contract():
    """D5: the harness registers the lane, enforces its ctx contract (no silent defaulting —
    the four-studies front-side hole, encoded), and REFUSES to grade it through replay(),
    which feeds 10s new-bar slices this 3-min lane must never be judged on."""
    h = H()
    ok = True
    reg = "flat_top" in h.LANES
    ok &= reg
    check("D5 lane registered", reg)
    if reg:
        req = set(h.LANES["flat_top"]["ctx_required"])
        want = {"armed", "time_hm", "ma_first", "ma_only_window"}
        ok &= req == want
        check("D5 ctx contract = " + str(sorted(want)), req == want, str(sorted(req)))
        ok &= h.LANES["flat_top"].get("driver") == "replay_flat_top"
        check("D5 declares its own driver", h.LANES["flat_top"].get("driver") == "replay_flat_top")

    try:
        h.replay("X", [], ["flat_top"], vwap_provider=lambda *a: 1.0,
                 ctx_provider=lambda *a: CTX0)
        ok = False
        check("D5 replay() refuses the flat_top lane", False, "it did NOT refuse")
    except h.HarnessError:
        check("D5 replay() refuses the flat_top lane", True)

    try:
        h._check_ctx("flat_top", {"armed": False, "time_hm": "09:30"})
        ok = False
        check("D5 missing ctx field is refused, never defaulted", False, "it defaulted")
    except h.MissingContext:
        check("D5 missing ctx field is refused, never defaulted", True)

    try:
        _step()("X", _base(8.09, 7.46), 8.155, 7.0, {"armed": False})
        ok = False
        check("D5 flat_top_step itself refuses a partial ctx", False, "it defaulted")
    except KeyError:
        check("D5 flat_top_step itself refuses a partial ctx", True)
    return ok


SPECS = {
    "SPEC_break_attack_extracted_and_live_calls_it": SPEC_break_attack_extracted_and_live_calls_it,
    "SPEC_break_attack_live_fixtures_0817": SPEC_break_attack_live_fixtures_0817,
    "SPEC_break_attack_differential_vs_old_path": SPEC_break_attack_differential_vs_old_path,
    "SPEC_break_attack_gates_unchanged": SPEC_break_attack_gates_unchanged,
    "SPEC_harness_flat_top_contract": SPEC_harness_flat_top_contract,
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
    print("FOUNDATION BATCH D — break-attack extraction (8/17)")
    print("=" * 78)
    for n, f in SPECS.items():
        try:
            check(n, bool(f()))
        except Exception as e:                                          # noqa: BLE001
            check(n, False, "%s: %s" % (type(e).__name__, e))
    print("BATCH D: " + ("ALL GREEN" if not FAILS else "RED: " + ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
