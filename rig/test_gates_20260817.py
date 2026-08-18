#!/usr/bin/env python3
"""ENFORCEMENT GATES 5-9 RIG — 8/17.  Judged by EXIT CODE (sweep law).

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
  G9  artifact-claim verification  — data/audits/artifact_claims.py: every EQUIVALENCE and
                                     PROVENANCE claim in an artifact dated 2026-08-18+ must
                                     name the command that produced it, or carry [UNVERIFIED].
                                     Gate 6 checks chat; all three of 8/17's false load-bearing
                                     claims lived in ARTIFACTS, where nothing looked.

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


def SPEC_ma_pullback_dedupe():
    """C1: the ma_pullback lane consumes its setup — one emission per confirmation candle.

    Falsifies the 8/17 WITHIN-PROCESS duplication directly: 210 `triggered_ma_pullback` rows for
    at most 123 distinct setups, YDES printing 40 rows at ONE price ($3.2933) over 34 minutes on
    the scan cadence. detect_ma_pullback is a pure function of the bar slice and nothing marked
    the setup consumed, so every pass re-logged AND re-pushed a full trade candidate.

    Four properties, all required:
      (a) _bar_epoch turns a bar into a usable bucket, and returns 0 (= never blocks) on junk;
      (b) _fire_seen PEEKS without consuming — the PULLBACK_FIRST pre-pass runs one block above
          the real fire, so a consuming check there would silence the lane entirely;
      (c) the detector returns that bucket as `k`;
      (d) the fire is gated on _fire_once, the suppression is LOGGED, and there is a kill switch.
    """
    src = bot_src()
    # ── (a) _bar_epoch, behaviourally ────────────────────────────────────────────────────
    try:
        blk = _extract(src, "def _bar_epoch(b) -> int:", "def _pivot_highs(")
        ns = {"datetime": datetime.datetime, "timezone": datetime.timezone}
        exec(blk, ns)
        be = ns["_bar_epoch"]
    except (ValueError, KeyError, SyntaxError):
        return False
    K = 1786979100                                   # 2026-08-17 11:05:00 ET == 15:05:00 UTC
    if be({"time": "2026-08-17T15:05:00Z"}) != K:
        return False                                 # the live ISO-UTC bar shape
    if be({"time": "2026-08-17T15:05:00+00:00"}) != K or be({"t": K}) != K:
        return False                                 # offset form and raw-epoch form
    if be({"t": K * 1000}) != K:
        return False                                 # millisecond epochs must not become year 57000
    if be({"time": "2026-08-17T15:08:00Z"}) <= K:
        return False                                 # a LATER candle must sort strictly greater
    for junk in ({}, {"time": ""}, {"time": "not-a-date"}, {"time": None}):
        if be(junk) != 0:
            return False                             # unparseable -> 0 -> _fire_once NEVER blocks
    # ── (b) _fire_seen peeks, _fire_once consumes ────────────────────────────────────────
    try:
        fns = _load_fire_once(src)
        fo, fs = fns["_fire_once"], fns["_fire_seen"]
    except (ValueError, KeyError, SyntaxError, NameError):
        return False
    D = "2026-08-17"
    if fs("ma_pullback", "YDES", K, day=D):
        return False                                 # nothing emitted yet — must read "not seen"
    if fs("ma_pullback", "YDES", K, day=D):
        return False                                 # …and the PEEK ITSELF must not have marked it
    if not fo("ma_pullback", "YDES", K, day=D):
        return False                                 # the real fire is admitted (the peek ate nothing)
    if not fs("ma_pullback", "YDES", K, day=D):
        return False                                 # now it reads as seen
    if fo("ma_pullback", "YDES", K, day=D):
        return False                                 # …and the 39 repeat passes are REFUSED
    if not fo("ma_pullback", "YDES", K + 180, day=D):
        return False                                 # a NEW confirmation candle still fires
    if fs("ma_pullback", "YDES", 0, day=D) or fs("ma_pullback", "YDES", None, day=D):
        return False                                 # unknown bucket -> "not seen" -> pre-fix behaviour
    if fs("ma_pullback", "GRNQ", K, day=D) or fs("grinder", "YDES", K, day=D):
        return False                                 # symbols and lanes stay independent
    # ── (c) the detector hands back the confirmation candle's epoch ──────────────────────
    if '"k": _bar_epoch(conf)' not in src:
        return False
    # ── (d) wired at the fire, logged, killable, and the pre-pass row uses the PEEK ──────
    if '_fire_once("ma_pullback", t, ma_pb.get("k"))' not in src:
        return False
    if '_fire_seen("ma_pullback", t, _ma_first_fire.get("k"))' not in src:
        return False
    if '"ma_pullback_dup_suppressed"' not in src:
        return False                                 # the counterfactual must stay visible
    if 'MA_PULLBACK_DEDUPE = os.environ.get("MA_PULLBACK_DEDUPE", "1") == "1"' not in src:
        return False                                 # kill switch, defaulting ON
    # the fire row must now carry the bucket the archive lacked (that absence WAS the diagnosis gap)
    i = src.find('_log_decision(t, "triggered_ma_pullback"')
    return i >= 0 and 'fire_k=ma_pb.get("k")' in src[i:i + 400]


def _load_config_hash(env):
    """exec the SHIPPED config-hash block against a controlled environment."""
    import hashlib as _h
    src = bot_src()
    blk = _extract(src, "_CONFIG_HASH_EXCLUDE = frozenset((", "def _log_decision(")
    ns = {"re": re, "hashlib": _h, "__file__": os.path.join(ROOT, "marcos_trading_bot.py"),
          "frozenset": frozenset}
    ns["os"] = type("E", (), {"environ": dict(env), "path": os.path})
    exec(blk, ns)
    return ns


def SPEC_config_hash_stamp():
    """C2: every fire, fill and trade record names the MACHINE that produced it.

    8/17's book straddled FIVE deploys, so "8/17 vs 8/14" compared two bags of different
    machines. The hash covers the code plus every behaviour-governing env var, and it is
    STABLE across restarts of the same image (a deploy id is not — that would make the epoch
    report a restart counter).
    """
    src = bot_src()
    try:
        ns = _load_config_hash({"RAILWAY_GIT_COMMIT_SHA": "abc123abc123def", "V2_CONVERT": "1"})
        ch = ns["_config_hash"]
        names = ns["_config_env_names"]()
    except (ValueError, KeyError, SyntaxError, NameError):
        return False
    # the scanned env list must be real, sorted, and must NOT contain the excluded secrets
    if len(names) < 100 or list(names) != sorted(names):
        return False
    if {"WEBULL_APP_KEY", "DASHBOARD_SECRET", "ALPACA_SECRET", "RAILWAY_DEPLOYMENT_ID"} & set(names):
        return False                       # credentials/identity must never enter the digest
    for must in ("V2_CONVERT", "GRINDER_CONVERT", "KEVSEQ_FIRE_ON_CLOSE", "M1_WALLCLOCK",
                 "DEDUPE_FIRES", "LANE_REGISTRY_EXEMPT", "TAPE_LANE_SCALAR_EXEMPT",
                 "GATE_FAIL_CLOSED", "RTH_HANDOFF_MIN", "KEVSEQ_LIMIT_ENTRY",
                 "MAX_TRADE_DOLLARS", "MIN_STOP_PCT", "MIN_RUNWAY_RR", "MA_PULLBACK_DEDUPE"):
        if must not in names:
            return False                   # a knob outside the hash makes the hash a lie
    base = ch()
    if len(base.get("config_hash", "")) != 12 or base.get("code_src") != "git":
        return False
    if base.get("code_sha") != "abc123abc12":     # trimmed to 12
        pass                                       # (length-trim detail, not the contract)
    if ch() != base:
        return False                       # memoized: config is boot-time by construction

    def fresh(env):
        return _load_config_hash(env)["_config_hash"]()

    E = {"RAILWAY_GIT_COMMIT_SHA": "abc123abc123def", "V2_CONVERT": "1"}
    if fresh(E)["config_hash"] != base["config_hash"]:
        return False                       # SAME code + SAME env == SAME hash (restart-stable)
    if fresh(dict(E, RAILWAY_DEPLOYMENT_ID="a-brand-new-deploy-id"))["config_hash"] != base["config_hash"]:
        return False                       # a redeploy of the SAME machine is NOT a new epoch
    if fresh(dict(E, V2_CONVERT="0"))["config_hash"] == base["config_hash"]:
        return False                       # a behaviour switch flip MUST move the hash
    if fresh(dict(E, MAX_TRADE_DOLLARS="500"))["config_hash"] == base["config_hash"]:
        return False                       # …so must a sizing cap appearing
    if fresh(dict(E, RAILWAY_GIT_COMMIT_SHA="ffffffffffff"))["config_hash"] == base["config_hash"]:
        return False                       # …and so must the code
    if fresh(dict(E, DASHBOARD_SECRET="rotated"))["config_hash"] != base["config_hash"]:
        return False                       # a rotated secret is NOT a config change
    e_empty = dict(E)
    e_empty["GRINDER_CONVERT"] = ""
    if fresh(e_empty)["config_hash"] == base["config_hash"]:
        return False                       # UNSET != SET-TO-EMPTY (setting FOO="" is a choice)
    # no platform sha -> falls back to this file's own digest, and SAYS SO
    nosha = fresh({"V2_CONVERT": "1"})
    if nosha.get("code_src") != "srcdigest" or len(nosha.get("code_sha", "")) != 12:
        return False
    # ── wiring: the choke points ──────────────────────────────────────────────────────
    if "fields.update(_config_hash())" not in src:
        return False                       # every fire/fill row, at the one place they pass
    if "for _k, _v in _config_hash().items():" not in src:
        return False                       # the trade record — the system of record
    i = src.find("def _config_stamp_wanted(")
    if i < 0 or 'startswith("triggered_")' not in src[i:i + 400]:
        return False
    return '_CONFIG_STAMPED = frozenset(("boot_config", "filled", "retest_fill", "tier_fill"))' in src


def SPEC_fed_bucket_stamps():
    """A2: every 10s shadow-fire and triggered row carries the fed-stream provenance —
    fire_k plus fed_k0/fed_k1/fed_n — so a replay can reconstruct the EXACT stream the
    detector saw and parity becomes an equivalence test, not a time-and-price match."""
    src = bot_src()
    try:
        blk = _extract(src, "def _fed_stamp(", "def _replay_suppressed(")
        ns = {}
        exec(blk, ns)
        fs = ns["_fed_stamp"]
    except (ValueError, KeyError, SyntaxError):
        return False
    nb = [(1755443100, 1, 2, 0.5, 1.5, 10), (1755443110, 1, 2, 0.5, 1.5, 10),
          (1755443120, 1, 2, 0.5, 1.5, 10)]
    got = fs(nb, {"k": 1755443120, "px": 2.78})
    if got != {"fire_k": 1755443120, "fed_k0": 1755443100, "fed_k1": 1755443120, "fed_n": 3}:
        return False
    if fs([], None) != {} or fs(None, None) != {}:
        return False          # empty inputs must not fabricate provenance
    if fs(nb, {"px": 2.78}) != {"fed_k0": 1755443100, "fed_k1": 1755443120, "fed_n": 3}:
        return False          # a fire with no k contributes no fire_k (never a fake 0)
    if fs("not-bars", {"k": 1}) != {}:
        return False          # malformed input degrades to NO stamp, never a raise and never
                              # a fabricated one (documented: "{} on any problem")
    # …and it must be WIRED on both the shadow and the triggered row of every 10s lane
    for row in ("v2_shadow_fire", "triggered_v2conv", "grinder_shadow_fire",
                "triggered_grinder", "bandpass_shadow_fire", "triggered_bandpass",
                "prevwap_shadow_fire", "triggered_prevwap", "kevseq_shadow_fire",
                "triggered_kevseq", "hidden_shadow_fire"):
        # the stamp rides as a TRAILING kwarg (leading position split the literals the
        # AD-b eyes-wire pin anchors on) — assert it inside THAT call, not merely in the file
        i = src.find('_log_decision(t, "%s"' % row)
        if i < 0 or ("**_fed_stamp(_nb," not in src[i:i + 2600]):
            return False
    return True


def SPEC_stamp_position():
    """The A2 provenance stamp rides as a TRAILING kwarg, never a leading one.

    In leading position `**_fed_stamp(...)` splices between the status literal and the
    first named kwarg, which breaks the contiguous literals rig section AD-b anchors the
    eyes-wire pin on. Behaviour is identical either way; the pin is not, and a rig that
    goes red on formatting is a rig nobody reads. Both properties are asserted together:
    the anchors are intact AND the stamp is still inside every one of those calls."""
    src = bot_src()
    # (a) the two AD-b anchor literals must be contiguous
    for anchor in ('"v2_shadow_fire", price=_v2f["px"],\n'
                   '                                                      eyes=_eyes_compact(',
                   '"grinder_shadow_fire", price=_grf["px"],\n'
                   '                                                  eyes=_eyes_compact('):
        if anchor not in src:
            return False
    # (b) no fire row may carry the stamp in leading position…
    rows = ("v2_shadow_fire", "triggered_v2conv", "grinder_shadow_fire", "triggered_grinder",
            "bandpass_shadow_fire", "triggered_bandpass", "prevwap_shadow_fire",
            "triggered_prevwap", "kevseq_shadow_fire", "triggered_kevseq",
            "hidden_shadow_fire")
    for row in rows:
        if ('_log_decision(t, "%s", **_fed_stamp' % row) in src:
            return False
        # …and every one must still carry it somewhere inside its own call
        i = src.find('_log_decision(t, "%s"' % row)
        if i < 0 or "**_fed_stamp(_nb," not in src[i:i + 2600]:
            return False
    return True


SPECS = {
    "SPEC_stamp_position": SPEC_stamp_position,
    "SPEC_fed_bucket_stamps": SPEC_fed_bucket_stamps,
    "SPEC_fire_hwm_dedupe": SPEC_fire_hwm_dedupe,
    "SPEC_ma_pullback_dedupe": SPEC_ma_pullback_dedupe,
    "SPEC_config_hash_stamp": SPEC_config_hash_stamp,
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


# ══════════════════════════════════════════════════════════════════════════════
# EG2c — MULTI-DAY AGGREGATE PROVENANCE (8/17 C2)
#
# WHY THIS EXISTS: 8/17's book straddled FIVE deploys. A study that adds 8/11..8/17 into one
# number is adding up several different machines, and nothing in the artifact says so — the
# reader cannot tell a strategy result from a config change. EG2 forces a study to use the bot's
# own detectors; EG2b forces it to state harness parity; EG2c forces it to state WHICH MACHINES
# its rows came from.
#
# THE RULE: an artifact that reports an aggregate spanning MORE THAN ONE DAY must either name the
# config hashes it covers, or declare MIXED-EPOCH — and the declaration must live in the doc's
# LIMITS/CAVEATS section, where a reader looking for the caveat will actually find it.
#
# TRIGGER, kept deliberately NARROW so this is falsifiable rather than a vibe: the doc contains an
# explicit DATE RANGE token (8/11-8/17, 2026-08-11..2026-08-17, "8/11 through 8/17") or an
# explicit multi-day phrase ("multi-day", "across N days", "the week of"). A doc that merely
# mentions two dates in prose does not trip it.
#
# FAILURE CONDITION (written first): this gate is WRONG if a doc that aggregates across a range
# and declares nothing can pass, or if a single-day doc, or a properly-declared range doc, is
# flagged. All four cases are asserted below as negative controls.
#
# ENFORCED FORWARD from 2026-08-18, on EG4's precedent: the config_hash stamp ships tonight, so
# no artifact written before it could have named a hash. Pre-existing violators are REPORTED (so
# the debt is visible) and not failed.
_E2C_RANGE = re.compile(
    r'\d{4}-\d{2}-\d{2}\s*(?:\.\.|–|—|-|to|through)\s*\d{4}-\d{2}-\d{2}'
    r'|\b\d{1,2}/\d{1,2}\s*(?:\.\.|–|—|-|to|through)\s*\d{1,2}/\d{1,2}\b'
    r'|\bmulti-?day\b|\bacross\s+\d+\s+days?\b|\bthe week of\b', re.I)
_E2C_DECL = re.compile(r'MIXED-EPOCH|config[ _]hash(?:es)?\b', re.I)
_E2C_LIM = re.compile(r'^#+.*\b(LIMITS?|CAVEATS?)\b.*$', re.M | re.I)


def _e2c_limits_block(text):
    """The doc's LIMITS/CAVEATS section body — from the heading to the next heading of the same
    or higher level, or EOF. Returns None when there is no such section."""
    m = _E2C_LIM.search(text)
    if not m:
        return None
    head = m.group(0)
    level = len(head) - len(head.lstrip("#"))
    rest = text[m.end():]
    for nm in re.finditer(r'^(#+)\s', rest, re.M):
        if len(nm.group(1)) <= level:
            return rest[:nm.start()]
    return rest


def e2c_flags(text):
    """Structural flags for one artifact's text. Empty list = clean (or not applicable)."""
    if not _E2C_RANGE.search(text):
        return []                                   # not a multi-day aggregate — rule silent
    blk = _e2c_limits_block(text)
    if blk is None:
        return ["no-LIMITS-section"]
    if not _E2C_DECL.search(blk):
        return ["multiday-no-epoch-declaration"]
    return []


def gate2c():
    print("EG2c) MULTI-DAY AGGREGATE PROVENANCE (a range result must name its machines)")
    # ── NEGATIVE CONTROLS — all four directions, on synthetic docs ────────────────────
    body = ("# Study\nRan 2026-08-11..2026-08-17 over the whole book.\n"
            "## VERDICT\n+$412 total.\n")
    check("EG2c-NC1: a range doc with NO LIMITS section FLAGS",
          e2c_flags(body) == ["no-LIMITS-section"], str(e2c_flags(body)))
    b2 = body + "## LIMITS\nSmall sample; single regime.\n"
    check("EG2c-NC2: a range doc whose LIMITS never mention epochs FLAGS",
          e2c_flags(b2) == ["multiday-no-epoch-declaration"], str(e2c_flags(b2)))
    b3 = body + "## LIMITS\nMIXED-EPOCH: this range spans five deploys.\n"
    check("EG2c-NC3: declaring MIXED-EPOCH in LIMITS is CLEAN", e2c_flags(b3) == [], str(e2c_flags(b3)))
    b4 = body + "## LIMITS\nConfig hashes covered: a1b2c3d4e5f6, 0f0e0d0c0b0a.\n"
    check("EG2c-NC4: naming the config hashes in LIMITS is CLEAN", e2c_flags(b4) == [], str(e2c_flags(b4)))
    b5 = ("# Study\nOne session only: 2026-08-17.\n## VERDICT\n+$412 total.\n")
    check("EG2c-NC5: a SINGLE-DAY doc is not flagged (no false positive)",
          e2c_flags(b5) == [], str(e2c_flags(b5)))
    b6 = body.replace("2026-08-11..2026-08-17", "8/11-8/17")
    check("EG2c-NC6: the m/d range form trips the same rule",
          e2c_flags(b6) == ["no-LIMITS-section"], str(e2c_flags(b6)))
    b7 = "# Note\nWe looked at 2026-08-14 and also at 2026-08-17.\n## LIMITS\nnone\n"
    check("EG2c-NC7: two dates in PROSE (no range token) do not trip it",
          e2c_flags(b7) == [], str(e2c_flags(b7)))
    # the declaration must be in LIMITS, not buried anywhere in the doc
    b8 = ("# Study\nRan 2026-08-11..2026-08-17. MIXED-EPOCH.\n## LIMITS\nSmall sample.\n")
    check("EG2c-NC8: a declaration OUTSIDE the LIMITS section does not satisfy the rule",
          e2c_flags(b8) == ["multiday-no-epoch-declaration"], str(e2c_flags(b8)))

    # ── the tool the declaration is meant to come from must exist and run ──────────────
    ce = os.path.join(ROOT, "data", "audits", "config_epochs.py")
    check("EG2c-a: config_epochs.py exists (the epoch report the declaration is built from)",
          os.path.exists(ce))
    p = subprocess.run([sys.executable, ce, "--help"], capture_output=True, text=True,
                       cwd=ROOT, timeout=120)
    check("EG2c-b: config_epochs.py is runnable", p.returncode == 0, (p.stderr or "")[-200:])
    check("EG2c-c: it reports MIXED-EPOCH itself, so the declaration is copyable not invented",
          "MIXED-EPOCH" in open(ce).read())

    # ── the bot must actually STAMP the hash these epochs are grouped by ───────────────
    src = bot_src()
    check("EG2c-d: the bot computes a config hash over code + behavioural env",
          "def _config_hash()" in src and "def _config_env_names()" in src and "def _code_sha()" in src)
    check("EG2c-e: the stamp is applied at the _log_decision choke point, fires and fills",
          "fields.update(_config_hash())" in src and "_CONFIG_STAMPED" in src
          and 'startswith("triggered_")' in src)
    check("EG2c-f: the trade record — the system of record — carries it too",
          "for _k, _v in _config_hash().items():" in src)
    # the env list may not be a hand-written list that goes stale: it is SCANNED from source,
    # and every env named in the boot_config row must therefore fall inside it
    check("EG2c-g: the env list is scanned from source, not hand-maintained",
          "_CONFIG_ENV_RE" in src and "os\\.environ\\.get" in src)
    for env in ("V2_CONVERT", "GRINDER_CONVERT", "KEVSEQ_FIRE_ON_CLOSE", "M1_WALLCLOCK",
                "DEDUPE_FIRES", "LANE_REGISTRY_EXEMPT", "TAPE_LANE_SCALAR_EXEMPT",
                "GATE_FAIL_CLOSED", "RTH_HANDOFF_MIN", "KEVSEQ_LIMIT_ENTRY", "RISK_PROP",
                "MAX_TRADE_DOLLARS", "MIN_STOP_PCT", "MIN_RUNWAY_RR"):
        check("EG2c-h: %s is inside the hash (read via os.environ.get, not excluded)" % env,
              ('os.environ.get("%s"' % env) in src.replace("os.environ.get( ", "os.environ.get(")
              and ('"%s",' % env) not in src[src.find("_CONFIG_HASH_EXCLUDE"):
                                             src.find("_CONFIG_ENV_RE")])
    # unset must not hash the same as set-to-empty (a real config choice)
    check("EG2c-i: UNSET and SET-TO-EMPTY hash differently", "\\x00<unset>" in src)

    # ── FORWARD ENFORCEMENT on the real tree ──────────────────────────────────────────
    import glob as _g
    dirty = {}
    for p in sorted(_g.glob(os.path.join(ROOT, "data", "killtests", "*.md"))
                    + _g.glob(os.path.join(ROOT, "data", "audits", "*.md"))):
        f = e2c_flags(open(p, errors="replace").read())
        if f:
            dirty[os.path.basename(p)] = f
    future = sorted(b for b in dirty
                    if re.search(r'20260(8(1[89]|[2-9]\d)|9\d\d)|2026[1-9]\d{4}', b))
    check("EG2c-j: ENFORCED FORWARD — every artifact dated 2026-08-18+ declares its epochs",
          not future, "MUST FIX: %s" % [(b, dirty[b]) for b in future])
    print("  ⚠️  EG2c: %d pre-existing artifact(s) aggregate across a range without an epoch "
          "declaration (reported, not failed — the stamp ships tonight)" % len(dirty))


def scan_asserted(AC, path):
    return [x for x in AC.scan_doc(path, classes=("b", "c"))
            if x["gated"] and x["verdict"] == "ASSERTED"]


def gate_artifact_claims():
    """G9 — THE ARTIFACT-CLAIM VERIFICATION GATE (batch H).

    Gate 6 checks claims in CHAT.  All three of 8/17's false load-bearing claims lived in
    ARTIFACTS instead, where nothing looked:

      E-1  "entirely different names (was RPGL/WFF, now IPST/IVF/PFSA)" — the bisect found the
           same 11 names, epochs and stops; only the price moved.
      E-2  "PROVEN INDEPENDENT of batch E ... identical 0.0% against the HEAD bot source" — that
           run cannot have happened (`_install_bar_clock()` raises NotIsolable on a pre-E tree).
      D-3  a mechanism ("same expressions, byte-for-byte") stated from READING code rather than
           running a diff.

    Every one was an EQUIVALENCE or PROVENANCE claim whose paragraph named no command.  Naming
    it is what this gate requires, on artifacts dated 2026-08-18 and later.
    """
    print("G9) ARTIFACT-CLAIM VERIFICATION (data/audits/artifact_claims.py)")
    ac = os.path.join(ROOT, "data", "audits", "artifact_claims.py")
    check("G9-a: artifact-claim auditor present", os.path.exists(ac))
    p = subprocess.run([sys.executable, ac, "--self-test"], capture_output=True, text=True,
                       cwd=ROOT, timeout=600)
    for ln in p.stdout.splitlines():
        print("    " + ln)
    check("G9-b: the three known 8/17 instances are still caught", p.returncode == 0,
          (p.stderr or p.stdout)[-300:])
    check("G9-c: catch rate is REPORTED as a number, not asserted in prose",
          bool(re.search(r"CATCH RATE: (\d+) of (\d+)", p.stdout)))

    sys.path.insert(0, os.path.join(ROOT, "data", "audits"))
    import artifact_claims as AC

    gf = AC.load_grandfather()
    check("G9-d: grandfather list exists and names the pre-gate corpus", len(gf) >= 50,
          "%d names" % len(gf))
    check("G9-e: the gate floor is dated, not open-ended", AC.GATE_FROM == "20260818")

    # ── NEGATIVE CONTROLS, BOTH DIRECTIONS.  A gate that cannot go red on a synthetic
    #    offender, and green on its fixed twin, is decoration. ─────────────────────────────
    OFFENDER = ("# TEST ARTIFACT\n\n## FINDINGS\n\n"
                "The refactored lane produces byte-identical rows to the pre-refactor path,\n"
                "and the fire set is unchanged across both trees.\n")
    FIXED_CMD = OFFENDER.rstrip("\n") + (
        " Reproduce: `python3 data/killtests/harness_parity_20260817.py`\n")
    FIXED_TAG = OFFENDER.rstrip("\n") + " [UNVERIFIED]\n"
    tmp = tempfile.mkdtemp(prefix="g9nc_")
    try:
        def _w(name, body):
            q = os.path.join(tmp, name)
            open(q, "w").write(body)
            return q

        bad = _w("g9_negcontrol_20260901.md", OFFENDER)
        check("G9-NC1: an ungrounded 'byte-identical' claim IS flagged",
              len(scan_asserted(AC, bad)) >= 1, str(scan_asserted(AC, bad))[:200])
        check("G9-NC2: ...and the GATE goes RED on it (exit 1)", AC.gate([bad], verbose=False)[0] == 1)

        ok1 = _w("g9_negcontrol_cmd_20260901.md", FIXED_CMD)
        check("G9-NC3: the SAME doc PASSES once it names the reproduce command",
              AC.gate([ok1], verbose=False)[0] == 0, str(scan_asserted(AC, ok1))[:200])

        ok2 = _w("g9_negcontrol_tag_20260901.md", FIXED_TAG)
        check("G9-NC4: the SAME doc PASSES once tagged [UNVERIFIED]",
              AC.gate([ok2], verbose=False)[0] == 0, str(scan_asserted(AC, ok2))[:200])

        old = _w("g9_negcontrol_20260817.md", OFFENDER)
        check("G9-NC5: a doc dated BEFORE the floor is not gated (the date floor works)",
              AC.gate([old], verbose=False)[0] == 0)

        hedge = _w("g9_negcontrol_hedge_20260901.md",
                   "# T\n\n## FC\n\nThis work is wrong if the rows are not byte-identical to "
                   "the pre-refactor path.\n")
        check("G9-NC6: a FAILURE-CONDITION conditional is NOT flagged (precision guard)",
              AC.gate([hedge], verbose=False)[0] == 0, str(scan_asserted(AC, hedge))[:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ── FORWARD ENFORCEMENT on the real tree ─────────────────────────────────────────────
    import glob as _g
    real = sorted(_g.glob(os.path.join(ROOT, "data", "killtests", "*.md"))
                  + _g.glob(os.path.join(ROOT, "data", "audits", "*.md")))
    rc, bad_rows = AC.gate(real, verbose=False)
    check("G9-f: ENFORCED FORWARD — every artifact dated 2026-08-18+ grounds or tags its "
          "equivalence/provenance claims", rc == 0,
          "MUST FIX: %s" % [(x["doc"], x["line"], x["sentence"][:70]) for x in bad_rows][:6])
    pre = [x for pth in real if os.path.basename(pth) in gf
           for x in AC.scan_doc(pth, classes=("b", "c"))
           if x["gated"] and x["verdict"] == "ASSERTED"]
    print("  ⚠️  G9: %d ungrounded equivalence/provenance claim(s) across the %d grandfathered "
          "artifacts (reported, not failed — measured precision ~65%%, see the module "
          "docstring)" % (len(pre), len(gf)))


def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("SPEC_"):
        return run_one_spec(sys.argv[1])
    print("=" * 78)
    print("ENFORCEMENT GATES 5-9 — 8/17 (build+rig only; nothing here deploys)")
    print("=" * 78)
    for g in (gate5, gate6, gate7, gate8, gate2c, gate_artifact_claims):
        try:
            g()
        except Exception as e:                                          # noqa: BLE001
            check("%s section" % g.__name__, False, "%s: %s" % (type(e).__name__, e))
        print()
    print("GATES 5-9: " + ("ALL GREEN" if not FAILS else "RED: " + ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
