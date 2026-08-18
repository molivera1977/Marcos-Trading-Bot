#!/usr/bin/env python3
"""FOUNDATION BATCH F — FAIL-OPEN GATE OBSERVABILITY (8/17).  Acceptance tests for GATE 5.

FAILURE CONDITION, WRITTEN FIRST (this file is WRONG if it can go green while):
  * a gate can pass on insufficient data without leaving a row that names the TICKER, or
  * two blind passes on the same name inside the 120s decision heartbeat collapse into one
    row (which is what makes every derived count a floor rather than a number), or
  * a blind row cannot say WHAT WAS MISSING (sample size) and WHAT WAS DECIDED, or
  * the daily row cap can truncate the day SILENTLY, with no capped marker, or
  * the cap, once hit, drops the remaining events entirely instead of degrading to the old
    60s-throttled counter.

Every spec below EXECUTES the shipped functions over synthetic inputs with a captured
_log_decision.  No spec passes on a grep alone.

Usage (spec_gate contract):
    python3 rig/test_batchF_20260817.py                 run every section (exit 0 = green)
    python3 rig/test_batchF_20260817.py SPEC_<name>     run one named spec
"""
import os, sys, re, types, datetime

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
    return src[i:src.index(end, i)]


# ── isolated loader ───────────────────────────────────────────────────────────────────────
# The blind-row machinery (_gate_blind / _blind_lane / _fail_closed / the cap block) is
# exec'd from the SHIPPED SOURCE into a namespace with a capturing _log_decision, so these
# specs grade the real code rather than a paraphrase of it.  Importing the whole bot module
# is not an option (it opens sockets and threads at import).
class _ET(datetime.tzinfo):
    def utcoffset(self, dt): return datetime.timedelta(hours=-4)
    def dst(self, dt): return datetime.timedelta(0)
    def tzname(self, dt): return "ET"


def load_blind(fail_closed="", cap=None, day="2026-08-17"):
    """-> (namespace, rows list).  rows gets every _log_decision(ticker, status, **fields)."""
    src = bot_src()
    rows = []
    ns = {
        "os": os, "sys": sys, "time": __import__("time"),
        "threading": __import__("threading"), "datetime": _FrozenDT(day),
        "EASTERN": _ET(),
        "_log_decision": lambda t, s, **f: rows.append(dict(f, ticker=t, status=s)),
        "GATE_FAIL_CLOSED": fail_closed,
    }
    # _fail_closed + the F1 blind block, straight out of the shipped file
    exec(compile(_extract(src, "def _fail_closed(gate):", "def _ambient_dvol_ok("),
                 "<bot:_fail_closed>", "exec"), ns)
    # the 60s-throttled fallback the cap degrades to (defined FIRST — _gate_blind calls it)
    exec(compile(_extract(src, "_gate_fo_t = {}", "\n\n# ── 8/17 F1"),
                 "<bot:_gate_failopen>", "exec"), ns)
    # NB anchor on the ASSIGNMENT, not the bare name: the name also appears in the comment
    # block above it, and starting there yields a fragment of prose that will not compile.
    blk = _extract(src, "\nGATE_BLIND_ROWS_MAX = int(", "def _entries_paused():")
    exec(compile(blk, "<bot:_gate_blind>", "exec"), ns)
    if cap is not None:
        ns["GATE_BLIND_ROWS_MAX"] = cap
    return ns, rows


class _FrozenDT:
    """Stands in for the bot's `datetime` CLASS (it does `from datetime import datetime`),
    with a now() whose ET day this rig controls — the cap resets on the ET date change."""
    def __init__(self, day):
        self._day = day

    def set_day(self, day):
        self._day = day

    def now(self, _tz=None):
        y, m, d = (int(x) for x in self._day.split("-"))
        return datetime.datetime(y, m, d, 10, 30, tzinfo=_ET())


# ══ SPECS ═════════════════════════════════════════════════════════════════════════════════

def SPEC_gate_blind_row_is_attributable():
    """A blind pass names the ticker, the lane, what was missing, and what was decided.

    The 8/17 archive's six gate_fail_open rows carried a "_GATE" pseudo-ticker and no lane,
    so not one could be attached to a fire.  That is the defect this forbids."""
    ns, rows = load_blind()
    ns["_blind_lane"]("kevseq")
    ns["_gate_blind"]("momentum", "ABCD", missing="2<5 session bars",
                      decision="pass_open", bars_have=2, bars_need=5)
    if len(rows) != 1:
        print("  expected exactly 1 row, got %d" % len(rows)); return False
    r = rows[0]
    need = {"ticker": "ABCD", "status": "gate_blind_momentum", "gate": "momentum",
            "lane": "kevseq", "decision": "pass_open", "bars_have": 2, "bars_need": 5}
    for k, v in need.items():
        if r.get(k) != v:
            print("  field %s: expected %r, got %r" % (k, v, r.get(k))); return False
    if "missing" not in r or "5" not in str(r["missing"]):
        print("  row does not say what was missing: %r" % r.get("missing")); return False
    if r.get("armed") is not False:
        print("  row must record the ARMED state, got %r" % r.get("armed")); return False
    return True


def SPEC_gate_blind_is_per_fire_not_throttled():
    """Repeated blind passes on ONE ticker inside the heartbeat each get their own row.

    _gate_failopen throttles 1 row/gate/60s and _log_decision collapses (ticker,status) for
    120s.  Under either, N blind passes report as 1 and every count built on them is a floor.
    This spec drives the SAME ticker+gate five times back-to-back and demands five rows."""
    ns, rows = load_blind()
    for _ in range(5):
        ns["_gate_blind"]("ambient", "SAME", missing="<5 completed bars")
    if len(rows) != 5:
        print("  5 blind passes produced %d rows — throttled/deduped" % len(rows)); return False
    if [r.get("seq") for r in rows] != [1, 2, 3, 4, 5]:
        print("  rows are not sequenced per event: %r" % [r.get("seq") for r in rows]); return False
    # and the bypass must be OPT-IN: the shipped call must pass _nodedup, and _log_decision
    # must honour it rather than the flag being decorative.
    src = bot_src()
    if "_nodedup=True" not in _extract(src, "def _gate_blind(", "def _entries_paused():"):
        print("  _gate_blind does not request the de-dupe bypass"); return False
    ld = _extract(src, "def _log_decision(ticker, status, **fields):", "def _ensure_decision_flusher")
    if 'fields.pop("_nodedup"' not in ld or "and not _nodedup" not in ld:
        print("  _log_decision does not honour _nodedup"); return False
    return True


def SPEC_gate_blind_cap_is_bounded_and_loud():
    """The daily cap bounds volume, announces itself once, and degrades — never silently drops.

    An unbounded per-event row on a hot path is a real risk; a SILENT truncation is worse than
    the throttle it replaced, because the resulting count looks complete."""
    ns, rows = load_blind(cap=3)
    for i in range(8):
        ns["_gate_blind"]("volguard", "T%d" % i, missing="no avg 1-min volume")
    blind = [r for r in rows if r["status"] == "gate_blind_volguard"]
    capped = [r for r in rows if r["status"] == "gate_blind_capped"]
    fallback = [r for r in rows if r["status"] == "gate_fail_open"]
    if len(blind) != 3:
        print("  cap=3 admitted %d blind rows" % len(blind)); return False
    if len(capped) != 1:
        print("  expected exactly ONE gate_blind_capped marker, got %d" % len(capped)); return False
    if capped[0].get("cap") != 3:
        print("  capped marker does not name the cap: %r" % capped[0]); return False
    if not fallback:
        print("  past the cap the events VANISH — must degrade to the 60s counter"); return False
    return True


def SPEC_gate_blind_cap_resets_daily():
    """A new ET day restores the full budget (and re-arms the capped marker)."""
    ns, rows = load_blind(cap=2)
    for i in range(4):
        ns["_gate_blind"]("ambient", "A%d" % i)
    day1 = len([r for r in rows if r["status"] == "gate_blind_ambient"])
    ns["datetime"].set_day("2026-08-18")
    for i in range(4):
        ns["_gate_blind"]("ambient", "B%d" % i)
    day2 = len([r for r in rows if r["status"] == "gate_blind_ambient"]) - day1
    if day1 != 2 or day2 != 2:
        print("  day1=%d day2=%d (cap=2) — the budget does not reset" % (day1, day2)); return False
    if len([r for r in rows if r["status"] == "gate_blind_capped"]) != 2:
        print("  the capped marker did not re-arm on the new day"); return False
    return True


def SPEC_gate_blind_records_armed_decision():
    """When a gate IS armed fail-closed, the row says refuse_closed and armed=True.

    Observability that cannot distinguish 'passed on ignorance' from 'refused on ignorance'
    cannot price the B5 conversion, which is the entire reason these rows exist."""
    ns, rows = load_blind(fail_closed="momentum,volguard")
    ns["_gate_blind"]("momentum", "ARMD", missing="1<5 session bars", decision="refuse_closed")
    ns["_gate_blind"]("ambient", "OPEN", missing="<5 completed bars", decision="pass_open")
    a, b = rows[0], rows[1]
    if not (a.get("armed") is True and a.get("decision") == "refuse_closed"):
        print("  armed gate row wrong: %r" % a); return False
    if not (b.get("armed") is False and b.get("decision") == "pass_open"):
        print("  unarmed gate row wrong: %r" % b); return False
    return True


def SPEC_all_three_failopen_gates_write_blind_rows():
    """All THREE fail-open gates are wired — including both exception paths.

    On 8/17 only `ambient` reached the archive at all; check_momentum and the volume-sizing
    guard used in-memory `_bump` counters that die with the process.  Structural, because the
    wiring is what is being asserted."""
    src = bot_src()
    amb = _extract(src, "def _ambient_dvol_ok(", "def check_momentum(")
    mom = _extract(src, "def check_momentum(", "def is_topping_tail(") \
        if "def is_topping_tail(" in src[src.index("def check_momentum("):] \
        else _extract(src, "def check_momentum(", "\ndef ")
    vol = _extract(src, "# ── VOLUME GUARD (7/11, the KUST lesson)", "# ── DOLLAR-TRACKED CAPITAL")
    checks = {
        "ambient <5 bars":  '_gate_blind("ambient"' in amb,
        "ambient exception": amb.count('_gate_blind("ambient"') >= 2,
        "momentum":         '_gate_blind("momentum"' in mom,
        "volguard no-tape": '_gate_blind("volguard"' in vol,
        "volguard except":  vol.count('_gate_blind("volguard"') >= 2,
        # the lane must actually be supplied at the entry path, or every row reads lane=""
        "lane wired":       "_blind_lane(entry_type)" in src,
    }
    ok = True
    for k, v in checks.items():
        if not v:
            print("  NOT WIRED: %s" % k); ok = False
    return ok


def SPEC_batchB_work_not_duplicated():
    """Batch B's GATE_FAIL_CLOSED arming and volguard_closed_skip survive F1 untouched.

    F1 adds observability; it must not re-implement or disturb B5's refusal path."""
    src = bot_src()
    need = ['GATE_FAIL_CLOSED", ""', "def _fail_closed(gate):",
            'if _fail_closed("momentum"):', 'if _fail_closed("volguard"):',
            '_log_decision(ticker, "volguard_closed_skip"']
    for n in need:
        if n not in src:
            print("  batch-B artifact MISSING (F1 disturbed it): %s" % n); return False
    # exactly one definition of each — no shadow copy introduced by F1
    if src.count("def _fail_closed(gate):") != 1 or src.count("def _gate_blind(") != 1:
        print("  duplicated definition"); return False
    return True


SPECS = {
    "SPEC_gate_blind_row_is_attributable": SPEC_gate_blind_row_is_attributable,
    "SPEC_gate_blind_is_per_fire_not_throttled": SPEC_gate_blind_is_per_fire_not_throttled,
    "SPEC_gate_blind_cap_is_bounded_and_loud": SPEC_gate_blind_cap_is_bounded_and_loud,
    "SPEC_gate_blind_cap_resets_daily": SPEC_gate_blind_cap_resets_daily,
    "SPEC_gate_blind_records_armed_decision": SPEC_gate_blind_records_armed_decision,
    "SPEC_all_three_failopen_gates_write_blind_rows": SPEC_all_three_failopen_gates_write_blind_rows,
    "SPEC_batchB_work_not_duplicated": SPEC_batchB_work_not_duplicated,
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
    print("FOUNDATION BATCH F — fail-open gate observability (8/17)")
    print("=" * 78)
    for n, f in SPECS.items():
        try:
            check(n, bool(f()))
        except Exception as e:                                          # noqa: BLE001
            check(n, False, "%s: %s" % (type(e).__name__, e))
    print("BATCH F: " + ("ALL GREEN" if not FAILS else "RED: " + ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
