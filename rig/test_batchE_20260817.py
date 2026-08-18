#!/usr/bin/env python3
"""FOUNDATION BATCH E — THE REMAINING LANES MADE TESTABLE (8/17). Gate-5 acceptance tests.

FAILURE CONDITION, WRITTEN FIRST
--------------------------------
This file is WRONG if it can go green while ANY of these is true:
  * a batch-E injection CHANGES THE LIVE PATH — i.e. calling the function the way the live
    process calls it (no new argument, hook unset) produces anything different from the
    pre-8/17 code. Every lane below carries a `_default` spec that drives the live call shape
    and asserts the old semantics, computed independently of the function under test;
  * `_bucket_fresh`'s live branch consults anything but `time.time()` (the hook must be None
    in the shipped source — a bot that SETS it anywhere has moved the live clock);
  * an injected argument silently becomes the DEFAULT (e.g. pm_floor=None quietly meaning
    "no zone" instead of "ask the live store");
  * the harness can run zone_flip without an explicit pm_floor, or runway without an explicit
    map + wall high — the whole point is refusal, not a flattering default;
  * `_map_snapshot` can fetch, compute, recurse into _log_decision, or throw;
  * the map stamp lands on rows that are not fires/fills (volume), or overwrites a field a
    caller passed explicitly.

Everything drives the SHIPPED function objects, lifted by data/killtests/live_harness.py's AST
loader — no import of the bot (that is a live trading path), no re-implementation.

Usage (spec_gate contract):
    python3 rig/test_batchE_20260817.py                 run every section (exit 0 = green)
    python3 rig/test_batchE_20260817.py SPEC_<name>     run one named spec
"""
import os
import re
import sys
import time

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


# ══════════════════════════════════════════════════════════════════════════════
# E1 — _bucket_fresh: the replay clock hook
# ══════════════════════════════════════════════════════════════════════════════
def SPEC_bucket_fresh_replay_clock():
    """A bar hours in the past must be judgeable FRESH when the clock is the bar's own epoch.
    This is the whole unblock: before it, every replayed fire on every 10s lane was eaten."""
    N = H().ns()
    bf = N["_bucket_fresh"]
    old = time.time() - 6 * 3600          # six hours stale by the wall clock
    if bf(old, hm="10:00"):
        return False                       # sanity: the guard must reject it on the wall clock
    if not bf(old, hm="10:00", now=old + 5):
        return False                       # ...and accept it on the bar clock
    # the module hook is the path replay() uses
    prev = N.get("_BUCKET_NOW")
    try:
        N["_BUCKET_NOW"] = lambda: old + 5
        if not bf(old, hm="10:00"):
            return False
        # and it still rejects a bar that is stale RELATIVE TO THE BAR CLOCK
        if bf(old - 3600, hm="10:00"):
            return False
    finally:
        N["_BUCKET_NOW"] = prev
    return True


def SPEC_bucket_fresh_live_default():
    """LIVE-EQUIVALENCE PIN. With the hook unset and no `now`, the verdict must equal the
    pre-8/17 formula (wall clock, ET-now PRE ceiling), computed here independently."""
    N = H().ns()
    bf, lim, pre = N["_bucket_fresh"], N["CURL_FIRE_MAX_AGE_SECS"], N["CURL_FIRE_MAX_AGE_PRE"]
    if N.get("_BUCKET_NOW") is not None:
        return False                       # the namespace must start with the hook DISARMED
    now = time.time()
    for age in (0, 5, 30, 89, 91, 300, 3600):
        for hm in ("09:00", "09:30", "12:00", None):
            k = now - age
            want_lim = lim
            _hm = hm
            if _hm is None:
                import datetime as _dt
                from zoneinfo import ZoneInfo
                _hm = _dt.datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M")
            if _hm < "09:30":
                want_lim = min(lim, pre)
            want = bool(k) and (time.time() - k) <= want_lim
            got = bf(k, hm=hm) if hm else bf(k)
            if got != want:
                return False
    if bf(0) or bf(None):
        return False                       # 0/None never fresh — unchanged
    return True


def SPEC_bucket_hook_unset_in_shipped_source():
    """The bot must never SET _BUCKET_NOW: it is declared None once and read nowhere else.
    A live process that assigns it has moved its own stale-fire clock."""
    src = bot_src()
    assigns = re.findall(r"^\s*_BUCKET_NOW\s*=\s*(.+)$", src, re.M)
    if assigns != ["None      # replay-only: callable() -> epoch seconds. LIVE LEAVES THIS None."]:
        return len(assigns) == 1 and assigns[0].strip().startswith("None")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# E2 — zone_flip: the premarket floor injected
# ══════════════════════════════════════════════════════════════════════════════
_ZF_DAY = "2026-08-17"


def _zf_bars(zone, open930, base_k):
    """A minimal Z1/Z2/Z3 sequence at 09:30-09:33 ET on the replay day."""
    out = []
    k = base_k
    # 9:30 open bar (sets nothing; the detector reads open930 from the floor dict)
    for i in range(8):                      # volume history so avgv exists
        out.append((k + i * 10, open930, open930, open930, open930, 100.0))
    k += 80
    flush = zone                            # Z1: deep flush into the zone on 2x volume
    out.append((k, open930, open930, flush, flush + 0.001, 5000.0))
    k += 10
    out.append((k, flush, zone * 1.004, flush, zone * 1.003, 300.0))     # Z2: bottoming wick
    k += 10
    out.append((k, zone * 1.003, zone * 1.02, zone * 1.002, zone * 1.015, 300.0))  # Z3: fire
    return out


def SPEC_zoneflip_pm_floor_injection():
    """kev_zoneflip_step must run to a FIRE off an injected floor, with no live store."""
    Hh = H()
    Hh.set_replay_day(_ZF_DAY)
    N = Hh.ns()
    N["_zf_st"].pop("ZZTEST", None)
    import datetime as _dt
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    base_k = int(_dt.datetime(2026, 8, 17, 9, 30, 0, tzinfo=et).timestamp())
    zone, open930 = 10.0, 11.0
    bars = _zf_bars(zone, open930, base_k)
    prev = N.get("_BUCKET_NOW")
    try:
        N["_BUCKET_NOW"] = lambda: bars[-1][0] + 10
        fired = None
        for b in bars:
            r = N["kev_zoneflip_step"]("ZZTEST", [b],
                                       pm_floor={"zone": zone, "src": "pm_shelf3",
                                                 "open930": open930})
            fired = r or fired
    finally:
        N["_BUCKET_NOW"] = prev
    return bool(fired and fired.get("zone") == zone and fired.get("zone_src") == "pm_shelf3"
                and fired.get("stop") and fired.get("k"))


def SPEC_zoneflip_default_asks_the_live_store():
    """LIVE-EQUIVALENCE PIN. pm_floor omitted (the live call shape) must call _zf_pm_floor —
    it must NOT quietly mean 'no zone'. Proven by observing the call, not by reading the code."""
    N = H().ns()
    seen = []
    prev = N["_zf_pm_floor"]
    try:
        N["_zf_pm_floor"] = lambda s: seen.append(s) or None
        N["kev_zoneflip_step"]("ZZTEST2", [(1, 1, 1, 1, 1, 1)])
    finally:
        N["_zf_pm_floor"] = prev
    if seen != ["ZZTEST2"]:
        return False
    # and the LIVE CALL SITE still passes no floor
    src = bot_src()
    return "kev_zoneflip_step(t, _zf_nb)" in src


def SPEC_harness_refuses_zoneflip_without_pm_floor():
    Hh = H()
    if "pm_floor" not in Hh.LANES["zone_flip"]["ctx_required"]:
        return False
    try:
        Hh.replay("ZZ", [(1, 1, 1, 1, 1, 1)], ["zone_flip"], day=_ZF_DAY,
                  ctx_provider=lambda *a: {})
        return False
    except Hh.MissingContext:
        pass
    try:
        Hh.replay("ZZ", [(1, 1, 1, 1, 1, 1)], ["zone_flip"], day=_ZF_DAY)
        return False
    except Hh.MissingContext:
        return True


# ══════════════════════════════════════════════════════════════════════════════
# E3 — _marked_runway: map + wall high injected
# ══════════════════════════════════════════════════════════════════════════════
_MAP = {"break": 9.0, "targets": [11.0, 13.0], "next_supply": 12.0}


def SPEC_runway_map_injection():
    """The road computes off an injected map + wall, touching neither store nor feed."""
    N = H().ns()
    boom = []
    p_em, p_cf = N["_effective_map"], N["_curl_feed"]
    try:
        N["_effective_map"] = lambda *a, **k: boom.append("map") or {}
        N["_curl_feed"] = lambda *a, **k: boom.append("feed") or ({}, "x")
        rr, tgt = N["_marked_runway"]("ZZ", 10.0, 9.0, lvd=_MAP, wall_high=0.0)
    finally:
        N["_effective_map"], N["_curl_feed"] = p_em, p_cf
    if boom:
        return False                        # a replay that reads the live path is worthless
    if (rr, tgt) != (1.0, 11.0):            # (11-10)/(10-9) = 1.0R to the first rung
        return False
    # the WALL: a session high of 11.5 spends the 11.0 rung and becomes the road's end
    rr2, tgt2 = N["_marked_runway"]("ZZ", 10.0, 9.0, lvd=_MAP, wall_high=11.5)
    return (rr2, tgt2) == (1.5, 11.5)


def SPEC_runway_default_reads_the_live_map():
    """LIVE-EQUIVALENCE PIN. No injected args (the live call shape) -> _effective_map and the
    wall feed are BOTH consulted, exactly as before 8/17."""
    N = H().ns()
    seen = []
    p_em, p_cf = N["_effective_map"], N["_curl_feed"]
    try:
        N["_effective_map"] = lambda t, px=0.0: (seen.append("map"), _MAP)[1]
        N["_curl_feed"] = lambda t, n=90: (seen.append("feed"), ({}, "x"))[1]
        rr, tgt = N["_marked_runway"]("ZZ", 10.0, 9.0)
    finally:
        N["_effective_map"], N["_curl_feed"] = p_em, p_cf
    return seen == ["map", "feed"] and (rr, tgt) == (1.0, 11.0)


def SPEC_harness_runway_refuses_invented_inputs():
    """No map -> refuse. No wall high -> refuse. Historical days have neither and must stay
    un-replayable rather than be graded against a map a study made up."""
    Hh = H()
    try:
        Hh.marked_runway_on("ZZ", 10.0, 9.0, None, 0.0)
        return False
    except Hh.MissingContext:
        pass
    try:
        Hh.marked_runway_on("ZZ", 10.0, 9.0, _MAP)
        return False
    except Hh.MissingContext:
        pass
    return Hh.marked_runway_on("ZZ", 10.0, 9.0, _MAP, 0.0) == (1.0, 11.0)


# ══════════════════════════════════════════════════════════════════════════════
# E3b — map snapshot recording (the durable half)
# ══════════════════════════════════════════════════════════════════════════════
def SPEC_map_stamp_on_triggered_rows():
    """Every triggered_* row (and fills) carries the map; ordinary watching rows do not."""
    N = H().ns()
    w = N["_map_stamp_wanted"]
    if not (w("triggered_flat_top") and w("triggered_ma_pullback") and w("filled")
            and w("retest_fill") and w("tier_fill")):
        return False
    if any(w(s) for s in ("watching", "consolidating", "kevseq_shadow_fire", "daily_loaded")):
        return False
    # a WARM effective-map cache is stamped, with the six named fields
    N["_effmap_cache"]["ZZ"] = (time.time() + 60, dict(_MAP, zone=8.5, _freshest_src="vision_shadow"))
    s = N["_map_snapshot"]("ZZ")
    for k in ("map_break", "map_targets", "map_next_supply", "map_zone", "map_age_min", "map_src"):
        if k not in s:
            return False
    N["_effmap_cache"].pop("ZZ", None)
    return (s["map_break"] == 9.0 and s["map_targets"] == [11.0, 13.0]
            and s["map_next_supply"] == 12.0 and s["map_zone"] == 8.5
            and s["map_src"] == "vision_shadow" and s["map_cache"] == "effmap_cache")


def SPEC_map_stamp_never_fetches_or_throws():
    """Cold caches -> map_src None and NOTHING else; no network, no _effective_map recursion,
    no exception. `requests` is POISONED in this namespace, so a fetch would raise loudly."""
    N = H().ns()
    N["_effmap_cache"].pop("ZZCOLD", None)
    N["_kev_levels_cache"].update({"date": None, "levels": {}, "ts": 0.0})
    boom = []
    prev = N["_effective_map"]
    try:
        N["_effective_map"] = lambda *a, **k: boom.append("map")
        s = N["_map_snapshot"]("ZZCOLD")
    finally:
        N["_effective_map"] = prev
    if boom or s != {"map_src": None}:
        return False
    # kill switch
    os.environ["MAP_STAMP"] = "0"
    try:
        N["_effmap_cache"]["ZZ"] = (time.time() + 60, dict(_MAP))
        off = N["_map_snapshot"]("ZZ")
    finally:
        os.environ.pop("MAP_STAMP", None)
        N["_effmap_cache"].pop("ZZ", None)
    return off == {}


# ══════════════════════════════════════════════════════════════════════════════
# E4 — check_momentum over supplied bars
# ══════════════════════════════════════════════════════════════════════════════
def _m1(n, day="2026-06-02", vol=1000.0, last_vol=None, base=10.0):
    out = []
    for i in range(n):
        v = vol if (last_vol is None or i < n - 1) else last_vol
        out.append({"time": f"{day}T14:{30 + i:02d}:00Z", "open": base, "high": base + 0.10,
                    "low": base - 0.02, "close": base + 0.08, "volume": v})
    return out


def SPEC_momentum_session_bars_replays_a_past_day():
    """A PAST day's session must reach the real read, not the insufficient-data branch.
    Proof: the same past-day bars through the OLD route (fetch + _fresh_session) fall into the
    'only 0 session bars' path; through session_bars they produce a real verdict."""
    N = H().ns()
    bars = _m1(12, day="2026-06-02", vol=1000.0, last_vol=9000.0)
    prev = N.get("get_intraday_bars")
    try:
        N["get_intraday_bars"] = lambda t, count=None, sessions=None, **kw: list(bars)
        ok_old, d_old = N["check_momentum"]("ZZ")
    finally:
        if prev is not None:
            N["get_intraday_bars"] = prev
    if "session bars available" not in str(d_old.get("reason")):
        return False                        # the bound this spec exists to lift
    ok_new, d_new = N["check_momentum"]("ZZ", session_bars=bars)
    if "session bars available" in str(d_new.get("reason")):
        return False                        # still stuck in the today-only path
    return isinstance(ok_new, bool) and d_new.get("session_peak_vol") is not None


def SPEC_momentum_default_still_fetches_and_freshens():
    """LIVE-EQUIVALENCE PIN. No session_bars (the live call shape) -> the fetch happens AND
    the result passes through _fresh_session, so a stale/past session still yields no read."""
    N = H().ns()
    seen = []
    bars = _m1(12, day="2026-06-02")
    prev = N.get("get_intraday_bars")
    try:
        N["get_intraday_bars"] = lambda t, count=None, sessions=None, **kw: (
            seen.append((count, sessions)), list(bars))[1]
        ok, d = N["check_momentum"]("ZZ")
    finally:
        if prev is not None:
            N["get_intraday_bars"] = prev
    return (len(seen) == 1 and seen[0][0] == 390
            and "session bars available" in str(d.get("reason")))


def SPEC_harness_momentum_on_supports_both_routes():
    Hh = H()
    bars = _m1(12, day="2026-06-02", vol=1000.0, last_vol=9000.0)
    ok_t, d_t = Hh.check_momentum_on("ZZ", bars)                       # today-only route
    ok_p, d_p = Hh.check_momentum_on("ZZ", bars, session_bars=bars)    # past-day route
    return ("session bars available" in str(d_t.get("reason"))
            and "session bars available" not in str(d_p.get("reason")))


# ══════════════════════════════════════════════════════════════════════════════
# harness registration + honesty of the isolability report
# ══════════════════════════════════════════════════════════════════════════════
def SPEC_harness_registers_the_lifted_lanes():
    Hh = H()
    if "zone_flip" not in Hh.LANES:
        return False
    if Hh.LANES["hidden"].get("blocked"):
        return False                        # E1 unblocked it; the flag must be gone
    rep = Hh.isolability_report()
    if any(str(v).startswith("FAILED") for v in rep["isolable"].values()):
        return False
    ni = " ".join(rep["not_isolable"])
    # runway must STILL be named as historically un-replayable — the honest half
    if "_marked_runway" not in ni:
        return False
    txt = rep["not_isolable"][[k for k in rep["not_isolable"] if "_marked_runway" in k][0]]
    return "2026-08-17" in txt and "un-replayable" in txt


SPECS = {
    "SPEC_bucket_fresh_replay_clock": SPEC_bucket_fresh_replay_clock,
    "SPEC_bucket_fresh_live_default": SPEC_bucket_fresh_live_default,
    "SPEC_bucket_hook_unset_in_shipped_source": SPEC_bucket_hook_unset_in_shipped_source,
    "SPEC_zoneflip_pm_floor_injection": SPEC_zoneflip_pm_floor_injection,
    "SPEC_zoneflip_default_asks_the_live_store": SPEC_zoneflip_default_asks_the_live_store,
    "SPEC_harness_refuses_zoneflip_without_pm_floor": SPEC_harness_refuses_zoneflip_without_pm_floor,
    "SPEC_runway_map_injection": SPEC_runway_map_injection,
    "SPEC_runway_default_reads_the_live_map": SPEC_runway_default_reads_the_live_map,
    "SPEC_harness_runway_refuses_invented_inputs": SPEC_harness_runway_refuses_invented_inputs,
    "SPEC_map_stamp_on_triggered_rows": SPEC_map_stamp_on_triggered_rows,
    "SPEC_map_stamp_never_fetches_or_throws": SPEC_map_stamp_never_fetches_or_throws,
    "SPEC_momentum_session_bars_replays_a_past_day": SPEC_momentum_session_bars_replays_a_past_day,
    "SPEC_momentum_default_still_fetches_and_freshens": SPEC_momentum_default_still_fetches_and_freshens,
    "SPEC_harness_momentum_on_supports_both_routes": SPEC_harness_momentum_on_supports_both_routes,
    "SPEC_harness_registers_the_lifted_lanes": SPEC_harness_registers_the_lifted_lanes,
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
    print("FOUNDATION BATCH E — remaining lanes made testable (8/17)")
    print("=" * 78)
    for n, f in SPECS.items():
        try:
            check(n, bool(f()))
        except Exception as e:                                          # noqa: BLE001
            check(n, False, "%s: %s" % (type(e).__name__, e))
    print("BATCH E: " + ("ALL GREEN" if not FAILS else "RED: " + ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
