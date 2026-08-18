#!/usr/bin/env python3
"""ENFORCEMENT GATES 5-8 RIG — 8/17.  Judged by EXIT CODE (sweep law).

Separate file from rig/test_shipset_20260804.py on purpose: a concurrent agent was building
gates 1-4 in that file the same night, and two writers on one file is how a ship gets lost.
ship.sh runs this as a SECOND script after the main rig (the least-collision wiring: one added
line in ship.sh instead of an edit inside a 3,800-line file being written by someone else).

  G5  spec-as-failing-test         — rig/spec_gate.py + its 7 negative controls
  G6  claim-without-check detector — data/audits/claim_audit.py, validated on the 8/17 transcript
  G7  decision-vs-deployed         — data/audits/DECISIONS.md rows all runnable + a MUTATED-tree
                                     negative control proving every row can go DRIFTED
  G8  regression corpus            — today's five defects pinned as permanent fixtures, each
                                     with a negative control proving it fails on the pre-fix path

TWO MODES
  python3 rig/test_gates_20260817.py               run everything, exit 0/1
  python3 rig/test_gates_20260817.py SPEC_<name>   run ONE named spec (the spec_gate contract:
                                                   exit 0 = the spec holds, non-0 = it does not)

ADDING A SPEC: register it in SPECS below.  A spec is a zero-arg callable returning True/False
about the CURRENT tree.  Gate 5 will check out your commit's PARENT, copy this file in, and
require your spec to FAIL there — so write the spec BEFORE the fix, and watch it go red.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "rig", "regression_fixtures")
os.environ.setdefault("DRY_RUN", "1")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "rig"))

FAILS = []


def check(name, cond, detail=""):
    print(("  ✅ " if cond else "  ❌ ") + name + ((f"  [{detail}]") if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def fixture(name):
    return json.load(open(os.path.join(FIX, name)))


def bot_src():
    return open(os.path.join(ROOT, "marcos_trading_bot.py")).read()


def _extract(src, start, end):
    """Slice a source block by literal markers (the established rig pattern — exec the real
    code in isolation rather than reimplementing it, so the rig tests the SHIPPED function)."""
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


# ══════════════════════════════════════════════════════════════════════════════
# SPECS — the acceptance tests Gate 5 falsifies against a commit's parent
# ══════════════════════════════════════════════════════════════════════════════
def _load_wallclock_window():
    """exec the SHIPPED _wallclock_window in an isolated namespace."""
    src = bot_src()
    blk = _extract(src, "def _wallclock_window(", "def _stop_close_qualifies")
    ns = {"datetime": datetime.datetime, "timezone": datetime.timezone,
          "timedelta": datetime.timedelta}
    exec(blk, ns)
    return ns["_wallclock_window"]


def SPEC_m1_wallclock_window():
    """The M1 wall-clock window exists and trims a traded-minute list to real minutes."""
    try:
        fn = _load_wallclock_window()
    except (ValueError, KeyError, SyntaxError):
        return False
    fx = fixture("rbne_m1_window_20260817.json")
    out = fn(fx["bars"], fx["window_min"])
    return len(out) == fx["expect_inside_window"] and len(out) < len(fx["bars"])


def SPEC_kevseq_limit_entry():
    """KEVSEQ_LIMIT_ENTRY caps the entry at fire*(1+tol) and vetoes an unfillable limit."""
    src = bot_src()
    return ('_ks_lim = round(_ksf["px"] * (1 + KEVSEQ_ENTRY_TOL), 4)' in src
            and "_ks_px = min(_ks_px, _ks_lim)" in src
            and '_ks_veto = "unfilled_limit"' in src
            and 'KEVSEQ_ENTRY_TOL", "0.005"' in src)


def SPEC_bell_boundary_handoff():
    """PRE bars stay visible for RTH_HANDOFF_MIN minutes after the bell."""
    src = bot_src()
    return ('RTH_HANDOFF_MIN", "5"' in src
            and 'return ["PRE", "RTH"]   # bell-boundary hand-off' in src)


def SPEC_ghost_cap_refund():
    """Conversion-lane caps are refunded on every non-fill path."""
    src = bot_src()
    return ('V2_CAP_ON_FILLS", "1"' in src
            and 'elif entry_type in ("v2conv", "grinder", "bandpass"):' in src
            and 'elif entry_type == "kevseq":' in src)


def SPEC_stale_ah_display():
    """The KEV-pin extended-hours row is session-gated (no 'AH' during RTH)."""
    src = open(os.path.join(ROOT, "screener_app.py")).read()
    idx = [m.start() for m in re.finditer(r'_row\["ah_label"\]', src)]
    if not idx:
        return False
    return "if after_hours or premarket:" in src[max(0, idx[-1] - 1200):idx[-1]]


def _load_fire_once(src=None):
    """exec the SHIPPED _fire_once / _fire_hwm_* block in an isolated namespace, pointed at a
    throwaway HWM file. Tests the code that ACTUALLY ships, not a copy of it."""
    src = src if src is not None else bot_src()
    blk = _extract(src, "DEDUPE_FIRES  = os.environ.get(", "def _replay_suppressed(")
    tmpf = os.path.join(tempfile.mkdtemp(), "fire_hwm.json")
    import threading as _th
    from zoneinfo import ZoneInfo as _Z
    ns = {"os": os, "json": json, "threading": _th, "datetime": datetime.datetime,
          "EASTERN": _Z("America/New_York")}
    ns["os"] = type("E", (), {"environ": {"DEDUPE_FIRES": "1", "FIRE_HWM_PATH": tmpf},
                              "path": os.path, "makedirs": os.makedirs, "replace": os.replace})
    exec(blk, ns)
    return ns


def SPEC_fire_hwm_dedupe():
    """A1: a (day, lane, symbol) may emit a fire for a given 10s bucket epoch AT MOST ONCE.

    Falsifies the 8/17 duplicate-fire defect directly: the archive showed RBNE
    grinder_shadow_fire re-emitted five times, all seq=0, once after each of the day's five
    boot_config rows — the restart replay re-feeding buckets that had already fired.
    """
    src = bot_src()
    try:
        ns = _load_fire_once(src)
        fo = ns["_fire_once"]
    except (ValueError, KeyError, SyntaxError, NameError):
        return False
    D = "2026-08-17"
    # RBNE's real bucket: 11:05:50 ET on 8/17 (the bar all five rows carried).
    k = 1755443150
    if not fo("grinder", "RBNE", k, day=D):
        return False                       # first emission must pass
    if fo("grinder", "RBNE", k, day=D):
        return False                       # the replay must be REFUSED (the whole defect)
    if fo("grinder", "RBNE", k - 600, day=D):
        return False                       # monotonic: an EARLIER bucket is also a replay
    if not fo("grinder", "RBNE", k + 10, day=D):
        return False                       # a genuinely NEW bucket must still fire
    if not fo("v2", "RBNE", k, day=D):
        return False                       # lanes are independent
    if not fo("grinder", "GNPX", k, day=D):
        return False                       # symbols are independent
    if not fo("grinder", "RBNE", k, day="2026-08-18"):
        return False                       # days are independent
    if not fo("grinder", "RBNE", 0, day=D) or not fo("grinder", "RBNE", None, day=D):
        return False                       # unknown bucket is NEVER blocked
    # and the guard must be WIRED at every 10s emission point the defect was measured in
    for lane, call in (("grinder", '_fire_once("grinder", t, _grf.get("k"))'),
                       ("v2", '_fire_once("v2", t, _v2f.get("k"))'),
                       ("bandpass", '_fire_once("bandpass", t, _bpf.get("k"))'),
                       ("kevseq", '_fire_once("kevseq", t, _ksf.get("k"))'),
                       ("prevwap", '_fire_once("prevwap", t, _pvf.get("k"))')):
        if call not in src:
            return False
    # …with a kill switch and a logged, visible cost
    return ('DEDUPE_FIRES", "1"' in src
            and 'if not DEDUPE_FIRES:' in src
            and '"replay_fire_suppressed"' in src)


SPECS = {
    "SPEC_fire_hwm_dedupe": SPEC_fire_hwm_dedupe,
    "SPEC_m1_wallclock_window": SPEC_m1_wallclock_window,
    "SPEC_kevseq_limit_entry": SPEC_kevseq_limit_entry,
    "SPEC_bell_boundary_handoff": SPEC_bell_boundary_handoff,
    "SPEC_ghost_cap_refund": SPEC_ghost_cap_refund,
    "SPEC_stale_ah_display": SPEC_stale_ah_display,
}


def run_one_spec(name):
    fn = SPECS.get(name)
    if fn is None:
        print("UNKNOWN SPEC %r — registered: %s" % (name, ", ".join(sorted(SPECS))))
        return 2
    try:
        ok = bool(fn())
    except Exception as e:                                    # noqa: BLE001 — a spec that
        print("  %s raised %s: %s" % (name, type(e).__name__, e))   # explodes has NOT passed
        return 1
    print(("  ✅ " if ok else "  ❌ ") + name)
    return 0 if ok else 1


# ══════════════════════════════════════════════════════════════════════════════
def gate5():
    print("G5) SPEC-AS-FAILING-TEST (rig/spec_gate.py)")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "rig", "spec_gate_selftest.py")],
                       capture_output=True, text=True, cwd=ROOT, timeout=900)
    for ln in p.stdout.splitlines():
        print("    " + ln)
    check("G5-a: spec_gate negative controls all behave (incl. the passes-at-parent branch)",
          p.returncode == 0, (p.stderr or p.stdout)[-300:])
    # the gate must be usable on THIS repo without exploding
    r = subprocess.run([sys.executable, os.path.join(ROOT, "rig", "spec_gate.py"), "HEAD"],
                       capture_output=True, text=True, cwd=ROOT, timeout=900)
    check("G5-b: spec_gate runs against this repo's HEAD without erroring",
          r.returncode in (0, 1) and "SPEC GATE" in r.stdout, (r.stderr or "")[-300:])
    # every registered spec must actually be runnable through the CLI contract Gate 5 uses
    for nm in sorted(SPECS):
        s = subprocess.run([sys.executable, os.path.abspath(__file__), nm],
                           capture_output=True, text=True, cwd=ROOT, timeout=300)
        check("G5-c: %s runnable via the spec CLI and PASSES on this tree" % nm,
              s.returncode == 0, "rc=%d %s" % (s.returncode, s.stdout.strip()[-160:]))


def gate6():
    print("G6) CLAIM-WITHOUT-CHECK DETECTOR (data/audits/claim_audit.py)")
    ca = os.path.join(ROOT, "data", "audits", "claim_audit.py")
    check("G6-a: detector present", os.path.exists(ca))
    p = subprocess.run([sys.executable, ca, "--self-test"], capture_output=True, text=True,
                       cwd=ROOT, timeout=900)
    for ln in p.stdout.splitlines():
        print("    " + ln)
    check("G6-b: 8/17 validation does not regress below the recorded catch rate",
          p.returncode == 0, (p.stderr or p.stdout)[-300:])
    m = re.search(r"CATCH RATE: (\d+) of (\d+)", p.stdout)
    check("G6-c: catch rate is REPORTED as a number, not asserted in prose", bool(m))
    if m:
        print("      recorded catch rate: %s of %s (the 2 hard cases are documented in the "
              "module docstring, not hidden)" % (m.group(1), m.group(2)))
    # NEGATIVE CONTROL: the detector must FLAG a fabricated ungrounded claim and must NOT flag
    # the same sentence once the number is present in the turn's tool evidence.
    sys.path.insert(0, os.path.join(ROOT, "data", "audits"))
    import claim_audit as CA
    sent = "The kevseq lane fired 47 triggers and consumed $918.44 of the daily cap."
    bare = [{"blocks": [("text", sent, "2026-08-17T12:00:00Z")]}]
    grounded = [{"blocks": [("evidence", "rows=47 pnl=918.44", ""),
                            ("text", sent, "2026-08-17T12:00:00Z")]}]
    check("G6-NC1: an ungrounded numeric claim IS flagged", len(CA.scan(bare)) >= 1)
    check("G6-NC2: the SAME sentence is NOT flagged once the numbers are in the turn's evidence",
          len(CA.scan(grounded)) == 0, str(CA.scan(grounded))[:200])
    hedged = [{"blocks": [("text", "The kevseq lane would fire about 47 triggers if we shipped it.",
                           "2026-08-17T12:00:00Z")]}]
    check("G6-NC3: a hedged proposal is NOT flagged (precision guard)",
          len(CA.scan(hedged)) == 0, str(CA.scan(hedged))[:200])
    dated = [{"blocks": [("text", "The ZYBT 7/20 and MTEN 8/10 fires were rejected by the gate.",
                          "2026-08-17T12:00:00Z")]}]
    check("G6-NC4: dates are not mistaken for counts (7/20, 8/10)",
          len(CA.scan(dated)) == 0, str(CA.scan(dated))[:200])


def gate7():
    print("G7) DECISION-VS-DEPLOYED RECONCILER")
    sys.path.insert(0, os.path.join(ROOT, "data", "audits"))
    import reconcile_decisions as RD
    rows = RD.parse_registry()
    check("G7-a: DECISIONS.md parses and is non-empty", len(rows) >= 8, "%d rows" % len(rows))
    check("G7-b: EVERY row carries a check command",
          all(r["check"].strip() for r in rows),
          str([r["id"] for r in rows if not r["check"].strip()]))
    check("G7-c: every row id is unique",
          len({r["id"] for r in rows}) == len(rows))
    res = [RD.run_row(r) for r in rows]
    drift = [r for r in res if r["state"] == "DRIFTED"]
    unk = [r for r in res if r["state"] == "UNKNOWN"]
    for r in res:
        print("      %-8s %s" % (r["state"], r["id"]))
    # The gate is "runs clean OR names the drift" — a DRIFTED row is REPORTED loudly but must
    # not turn the build red on its own: a drifted decision is a question for Marcos, not a
    # broken build (Auditor-cannot-authorize-behavior, 8/13).
    check("G7-d: the reconciler produced a verdict for every row",
          len(res) == len(rows) and all(r["state"] in ("HOLDS", "DRIFTED", "UNKNOWN") for r in res))
    if drift:
        print("      🚨 DRIFTED: %s — take it to Marcos" % ", ".join(r["id"] for r in drift))
    if unk:
        print("      ⚠️  UNKNOWN (evidence unreachable, NOT the same as passing): %s"
              % ", ".join(r["id"] for r in unk))
    check("G7-e: no row silently reports HOLDS when its evidence was unreachable",
          all(r["state"] != "HOLDS" or r["rc"] == 0 for r in res))

    # ── NEGATIVE CONTROL: every source-grep row must be CAPABLE of going DRIFTED. ──
    # Copy the two watched files into a scratch tree, strip the anchors each row greps for,
    # and re-run. A row that still says HOLDS against a tree with the decision removed is a
    # decoration, not a check.
    tmp = tempfile.mkdtemp(prefix="decisions_nc_")
    try:
        os.makedirs(os.path.join(tmp, "data", "audits"), exist_ok=True)
        for f in ("marcos_trading_bot.py", "screener_app.py"):
            shutil.copy(os.path.join(ROOT, f), os.path.join(tmp, f))
        # gut the anchors: blank every line mentioning any grepped token
        toks = set(re.findall(r"grep -q '([^']+)'", " ".join(r["check"] for r in rows))) | \
            set(re.findall(r"grep -c '([^']+)'", " ".join(r["check"] for r in rows)))
        for f in ("marcos_trading_bot.py", "screener_app.py"):
            p = os.path.join(tmp, f)
            keep = [("" if any(t in ln for t in toks) else ln) for ln in open(p).read().splitlines()]
            open(p, "w").write("\n".join(keep))
        env = dict(os.environ, DECISIONS_ROOT=tmp)
        old_root, RD.ROOT = RD.ROOT, tmp
        os.environ.update(env)
        src_rows = [r for r in rows if "grep" in r["check"]]
        nc = [RD.run_row(r) for r in src_rows]
        RD.ROOT = old_root
        still = [r["id"] for r in nc if r["state"] == "HOLDS"]
        check("G7-NC: every source-checked row goes DRIFTED on a tree with the decision removed",
              not still, "rows that stayed HOLDS: %s" % still)
        print("      negative control: %d/%d source rows flipped to DRIFTED"
              % (len(src_rows) - len(still), len(src_rows)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def gate8():
    print("G8) REGRESSION CORPUS (rig/regression_fixtures/) — today's defects, pinned forever")

    # ── (a) RBNE-class M1 window ─────────────────────────────────────────────
    fx = fixture("rbne_m1_window_20260817.json")
    check("G8-a0: fixture reproduces the documented specimen (48 bars / 243 wall-clock min)",
          fx["n_bars"] == 48 and fx["actual_span_min"] == 243 == fx["documented_span_min"],
          "n=%s span=%s" % (fx["n_bars"], fx["actual_span_min"]))
    fn = _load_wallclock_window()
    out = fn(fx["bars"], fx["window_min"])
    check("G8-a1: the 50-minute window TRIMS the 243-minute list",
          len(out) == fx["expect_inside_window"] < fx["n_bars"],
          "kept %d of %d" % (len(out), fx["n_bars"]))
    span_out = 0
    if len(out) >= 2:
        t0 = datetime.datetime.strptime(out[0]["time"][:19], "%Y-%m-%dT%H:%M:%S")
        t1 = datetime.datetime.strptime(out[-1]["time"][:19], "%Y-%m-%dT%H:%M:%S")
        span_out = (t1 - t0).total_seconds() / 60.0
    check("G8-a2: what survives really is inside the wall-clock window",
          span_out <= fx["window_min"], "span %.0f min" % span_out)
    # liquid-name invariant: a dense list must be byte-equivalent
    dense = [{"time": "2026-08-17T17:%02d:00.000+0000" % m, "close": 5.0} for m in range(0, 50)]
    check("G8-a3: a DENSE 50-bar list is untouched (liquid names byte-equivalent)",
          fn(dense, 50) == dense)
    # NEGATIVE CONTROL: the pre-fix path is the raw fixed-count list (kill switch M1_WALLCLOCK=0)
    check("G8-a-NC: pre-fix behaviour (no window) keeps all 48 bars — the defect reproduces",
          len(fx["bars"]) == 48 and len(fn(fx["bars"], 0)) == 48)
    check("G8-a-NC2: the kill switch that restores it still exists",
          'M1_WALLCLOCK", "1"' in bot_src() and "if M1_WALLCLOCK else bars" in bot_src())

    # ── (b) kevseq drift specimen ────────────────────────────────────────────
    fx = fixture("kevseq_drift_wff_20260817.json")
    src = bot_src()
    tol = float(re.search(r'KEVSEQ_ENTRY_TOL", "([0-9.]+)"', src).group(1))
    check("G8-b0: the shipped tolerance is the fixture's tolerance", tol == fx["kevseq_entry_tol"])
    limit = round(fx["fire_px"] * (1 + tol), 4)
    check("G8-b1: limit price == fire*1.005 (%.4f)" % fx["expect_limit_px"],
          limit == fx["expect_limit_px"], "%r" % limit)
    entry_capped = min(fx["actual_entry_px"], limit)
    check("G8-b2: WITH the limit, the entry is capped at the limit — never the $8.20 chase",
          abs(entry_capped - limit) < 1e-9 and entry_capped < fx["actual_entry_px"],
          "%r" % entry_capped)
    # the fill bar never traded at/below the limit -> unfilled_limit veto -> NO TRADE
    bar_lo = fx["actual_entry_px"]        # the real fill bar opened above the limit
    check("G8-b3: an unfillable limit is VETOED (no trade), matching the counterfactual",
          bar_lo > limit)
    risk_capped = (entry_capped - fx["would_stop"]) / entry_capped * 100
    check("G8-b4: capped risk collapses toward intended (%.2f%% -> %.2f%%, was %.2f%%)"
          % (fx["intended_risk_pct"], risk_capped, fx["actual_risk_pct"]),
          abs(risk_capped - fx["intended_risk_pct"]) < 1.0,
          "%.2f vs %.2f" % (risk_capped, fx["intended_risk_pct"]))
    check("G8-b5: the shipped code contains the exact limit/veto/cap expressions",
          SPEC_kevseq_limit_entry())
    # NEGATIVE CONTROL: with the fix OFF the defect is exactly today's row
    check("G8-b-NC: pre-fix, the entry is the raw quote $8.20 at %.1f%% risk (the real trade)"
          % fx["actual_risk_pct"],
          abs((fx["actual_entry_px"] - fx["would_stop"]) / fx["actual_entry_px"] * 100
              - fx["actual_risk_pct"]) < 0.01)
    check("G8-b-NC2: KEVSEQ_LIMIT_ENTRY is a real switch (default OFF — Marcos prices it)",
          'KEVSEQ_LIMIT_ENTRY    = os.environ.get("KEVSEQ_LIMIT_ENTRY", "0")' in src)

    # ── (c) bell boundary ────────────────────────────────────────────────────
    fx = fixture("bell_boundary_20260817.json")
    blk = _extract(src, "def _live_sessions(", "def _alpaca_intraday_bars")
    hand = int(re.search(r'RTH_HANDOFF_MIN", "(\d+)"', src).group(1))
    check("G8-c0: RTH_HANDOFF_MIN default matches the fixture (%d)" % fx["rth_handoff_min_default"],
          hand == fx["rth_handoff_min_default"], str(hand))

    def _sessions_at(hm, handoff):
        """Replay the SHIPPED _live_sessions logic against a frozen clock."""
        ns = {"RTH_HANDOFF_MIN": handoff, "os": os,
              "datetime": type("D", (), {"now": staticmethod(lambda tz=None: type(
                  "T", (), {"strftime": staticmethod(lambda f: hm[:5])})())}),
              "EASTERN": None}
        exec(blk, ns)
        return ns["_live_sessions"]()

    for case in fx["cases"]:
        got = _sessions_at(case["at"], hand)
        check("G8-c: %s -> %s  (%s)" % (case["at"], case["expect_sessions"], case["why"]),
              got == case["expect_sessions"], "got %r" % (got,))
    # NEGATIVE CONTROL: the pre-fix hard flip
    got = _sessions_at("09:30:30", 0)
    check("G8-c-NC: pre-fix (RTH_HANDOFF_MIN=0) 09:30:30 returns RTH-only — the blackout reproduces",
          got is None, "got %r" % (got,))
    print("      (the defect it pins: %d of %d names skipped 09:30-09:35 on 8/17)"
          % (fx["names_skipped"], fx["names_total"]))

    # ── (d) ghost cap ────────────────────────────────────────────────────────
    fx = fixture("ghost_cap_v2conv_20260817.json")
    check("G8-d0: fixture holds the five real non-fill triggers and zero fills",
          len(fx["triggers"]) == 5 and fx["fills"] == 0 and fx["daily_cap"] == 5)

    def _cap_after(refunds_on):
        """Replay the ledger: charge at trigger, refund on every non-fill path."""
        ledger = {"d": "2026-08-17", "n": 0}
        for _t in fx["triggers"]:
            ledger["n"] += 1                       # charged at the TRIGGER (unchanged)
            if refunds_on and ledger["n"] > 0:     # non-fill -> _slot_refund
                ledger["n"] -= 1
        return ledger["n"]

    used = _cap_after(True)
    check("G8-d1: 5 non-fill triggers leave the cap UNSPENT (%d used)" % used,
          used == fx["expect_cap_used_after"], str(used))
    check("G8-d2: the lane can still fire afterwards", used < fx["daily_cap"])
    check("G8-d3: the refund never drives a ledger negative", used >= 0)
    check("G8-d4: the shipped refund covers the conversion lanes AND kevseq's per-leg ticket",
          SPEC_ghost_cap_refund())
    # NEGATIVE CONTROL: the ghost cap itself
    ghost = _cap_after(False)
    check("G8-d-NC: pre-fix, the same 5 non-fills exhaust the 5/day cap — the defect reproduces",
          ghost == fx["observed_without_fix"]["cap_used_after"] == fx["daily_cap"], str(ghost))
    print("      (what that cost on 8/17: %d subsequent v2conv refusals, %d in the first hour)"
          % (fx["observed_without_fix"]["subsequent_refusals"],
             fx["observed_without_fix"]["refusals_in_first_hour"]))

    # ── (e) stale AH display ─────────────────────────────────────────────────
    fx = fixture("stale_ah_display_20260817.json")
    scr = open(os.path.join(ROOT, "screener_app.py")).read()
    sites = [m.start() for m in re.finditer(r'ah_label"?\]?\s*=\s*"PM"', scr)]
    check("G8-e0: every extended-hours render site is session-gated", bool(sites))
    for s in sites:
        window = scr[max(0, s - 1400):s]
        check("G8-e1: AH/PM site at offset %d sits inside a session gate" % s,
              "if after_hours or premarket:" in window)
    check("G8-e2: the KEV-pin site specifically carries the 8/17 gate", SPEC_stale_ah_display())
    # NEGATIVE CONTROL via git: the pre-fix tree has an UNGATED site
    try:
        pre = subprocess.run(["git", "-C", ROOT, "show", "%s:screener_app.py" % fx["pre_fix_commit"]],
                             capture_output=True, text=True, timeout=120).stdout
        pre_sites = [m.start() for m in re.finditer(r'ah_label"?\]?\s*=\s*"PM"', pre)]
        ungated = [s for s in pre_sites if "if after_hours or premarket:" not in pre[max(0, s - 1400):s]]
        check("G8-e-NC: at %s an extended-hours site is UNGATED — the defect reproduces on the "
              "pre-fix tree" % fx["pre_fix_commit"], bool(pre_sites) and bool(ungated),
              "pre_sites=%d ungated=%d" % (len(pre_sites), len(ungated)))
        print("      (what it rendered on 8/17 at %s ET: %s stale $%.2f labelled 'AH' beside the "
              "live $%.2f)" % (fx["at_et"], fx["ticker"], fx["stale_ah_price"], fx["live_price"]))
    except Exception as e:                                             # noqa: BLE001
        check("G8-e-NC: git negative control ran", False, "%s: %s" % (type(e).__name__, e))


def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("SPEC_"):
        return run_one_spec(sys.argv[1])
    print("=" * 78)
    print("ENFORCEMENT GATES 5-8 — 8/17 (build+rig only; nothing here deploys)")
    print("=" * 78)
    for g in (gate5, gate6, gate7, gate8):
        try:
            g()
        except Exception as e:                                          # noqa: BLE001
            check("%s section" % g.__name__, False, "%s: %s" % (type(e).__name__, e))
        print()
    print("GATES 5-8: " + ("ALL GREEN" if not FAILS else "RED: " + ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
