#!/usr/bin/env python3
"""GATE 5 NEGATIVE CONTROLS — proof that rig/spec_gate.py can actually go RED.

A gate that cannot fail is worse than no gate (Marcos, 8/17).  This builds THROWAWAY git
repos in a temp dir (never the real repo, never the live tree) and drives spec_gate through
every branch, asserting each verdict.

Control (a) THE KEY ONE — the 8/17 phantom-defect replay.  A commit changes
marcos_trading_bot.py and names an acceptance test that ALREADY PASSES on the parent code.
That is the shape of "the caller feeds kevseq a 3-minute front side": the assertion would
have been true of the OLD code too, proving the defect never existed.  The gate MUST go RED
with a verdict naming the premise as false.

Control (b) the honest case — a test that FAILS at the parent and PASSES at the commit.  GREEN.
Control (c) a behaviour-changing commit with NO Acceptance trailer.  RED.
Control (d) a comment/docstring/logging-only commit.  EXEMPT + GREEN (the classifier must not
            demand tests for prose — otherwise it gets routed around within a week).
Control (e) a test that fails at BOTH ends (the fix does not work).  RED.

Run: python3 rig/spec_gate_selftest.py     (exit 0 = all controls behaved)
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec_gate  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(("    ✅ " if cond else "    ❌ ") + name + (("  [%s]" % detail) if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def _sh(repo, *a):
    subprocess.run(["git", "-C", repo] + list(a), check=True, capture_output=True, text=True)


# The acceptance-test stub honours the spec_gate CLI contract: `python3 <file> SPEC_<name>`,
# exit 0 when the named spec passes.  It asserts something about marcos_trading_bot.py.
TEST_STUB = '''#!/usr/bin/env python3
import sys, os
src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "marcos_trading_bot.py")).read()
SPECS = {"SPEC_demo": lambda: %(assertion)r in src}
name = sys.argv[1]
sys.exit(0 if SPECS[name]() else 1)
'''


def _mkrepo(parent_bot, child_bot, assertion, message, test_at_child=True):
    """Build a 2-commit repo. Returns (repo_path, child_sha)."""
    repo = tempfile.mkdtemp(prefix="specgate_ctl_")
    _sh(repo, "init", "-q", "-b", "main")
    _sh(repo, "config", "user.email", "rig@local")
    _sh(repo, "config", "user.name", "rig")
    os.makedirs(os.path.join(repo, "rig"), exist_ok=True)
    open(os.path.join(repo, "marcos_trading_bot.py"), "w").write(parent_bot)
    _sh(repo, "add", "-A")
    _sh(repo, "commit", "-q", "-m", "parent")
    open(os.path.join(repo, "marcos_trading_bot.py"), "w").write(child_bot)
    if test_at_child:
        p = os.path.join(repo, "rig", "test_x.py")
        open(p, "w").write(TEST_STUB % {"assertion": assertion})
        os.chmod(p, 0o755)
    _sh(repo, "add", "-A")
    _sh(repo, "commit", "-q", "-m", message)
    sha = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    return repo, sha


TRAILER = "\n\nAcceptance: rig/test_x.py::SPEC_demo"


def main():
    print("GATE 5 NEGATIVE CONTROLS (rig/spec_gate.py)")

    # ── (a) THE KEY CONTROL: the assertion is TRUE at the parent already ──────
    print("  (a) phantom-defect replay — acceptance test PASSES at the parent")
    repo, sha = _mkrepo(
        parent_bot="X = 1\nFRONT_SIDE_TF = 1   # already 1-minute\n",
        child_bot="X = 2\nFRONT_SIDE_TF = 1   # already 1-minute\n",
        assertion="FRONT_SIDE_TF = 1",
        message="phantom fix: force 1-min front side" + TRAILER)
    try:
        r = spec_gate.check_commit(repo, sha)
        check("(a) gate is RED", r["ok"] is False, r["status"])
        v = (r["specs"][0]["verdict"] if r["specs"] else "")
        check("(a) verdict names the parent pass", "PASSES AT THE PARENT" in v, v[:120])
        check("(a) verdict says unnecessary / premise false",
              "UNNECESSARY" in v and "PREMISE IS FALSE" in v, v[:160])
        check("(a) parent half exited 0 (the test really did pass there)",
              r["specs"][0].get("parent_rc") == 0, str(r["specs"][0].get("parent_rc")))
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    # ── (b) the honest case ──────────────────────────────────────────────────
    print("  (b) honest fix — fails at parent, passes at commit")
    repo, sha = _mkrepo(
        parent_bot="X = 1\n",
        child_bot="X = 1\nWALLCLOCK_WINDOW = 50\n",
        assertion="WALLCLOCK_WINDOW = 50",
        message="real fix: wall-clock window" + TRAILER)
    try:
        r = spec_gate.check_commit(repo, sha)
        check("(b) gate is GREEN", r["ok"] is True, r["status"])
        check("(b) verdict is PROVEN", "PROVEN" in r["specs"][0]["verdict"], r["specs"][0]["verdict"][:120])
        check("(b) parent half really failed", r["specs"][0].get("parent_rc") not in (0, 124, 127),
              str(r["specs"][0].get("parent_rc")))
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    # ── (c) behaviour change with no trailer ─────────────────────────────────
    print("  (c) behaviour-changing commit with NO Acceptance trailer")
    repo, sha = _mkrepo(parent_bot="X = 1\n", child_bot="X = 2\n",
                        assertion="X = 2", message="silent behaviour change", test_at_child=False)
    try:
        r = spec_gate.check_commit(repo, sha)
        check("(c) gate is RED", r["ok"] is False, r["status"])
        check("(c) status NO_ACCEPTANCE_TEST", r["status"] == "NO_ACCEPTANCE_TEST", r["status"])
        check("(c) reason quotes the trailer convention", "Acceptance:" in r["reason"])
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    # ── (d) comments / docstrings / pure logging only ────────────────────────
    print("  (d) comment + docstring + logging-only commit is EXEMPT")
    repo, sha = _mkrepo(
        parent_bot='"""old doc."""\n# a comment\ndef f(x):\n    """inner."""\n    return x + 1\n',
        child_bot=('"""NEW doc, rewritten at length.\n\nmulti-line.\n"""\n'
                   '# a different comment\ndef f(x):\n    """inner, reworded."""\n'
                   '    print("f called", x)\n    _log_decision("t", "f", x=x)\n    return x + 1\n'),
        assertion="x + 1", message="docs + logging only", test_at_child=False)
    try:
        r = spec_gate.check_commit(repo, sha)
        check("(d) gate is GREEN", r["ok"] is True, r["status"])
        check("(d) status EXEMPT", r["status"] == "EXEMPT", r["status"])
        check("(d) reason names the exemption",
              "comments/docstrings/pure-logging" in r["reason"], r["reason"])
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    # ── (d2) the exemption must NOT swallow a real change hidden beside docs ──
    print("  (d2) a REAL change riding along with a doc rewrite is NOT exempt")
    repo, sha = _mkrepo(
        parent_bot='"""old doc."""\ndef f(x):\n    return x + 1\n',
        child_bot='"""a completely new docstring."""\ndef f(x):\n    print("hi")\n    return x + 2\n',
        assertion="x + 2", message="doc rewrite + a quiet constant change", test_at_child=False)
    try:
        r = spec_gate.check_commit(repo, sha)
        check("(d2) gate is RED", r["ok"] is False, r["status"])
        check("(d2) classified behaviour-changing",
              "code semantics changed" in r["reason"], r["reason"])
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    # ── (e) the fix does not actually work ───────────────────────────────────
    print("  (e) spec fails at BOTH ends — the fix does not do what it claims")
    repo, sha = _mkrepo(
        parent_bot="X = 1\n", child_bot="X = 3\n",
        assertion="X = 99", message="claims to set X=99, sets 3" + TRAILER)
    try:
        r = spec_gate.check_commit(repo, sha)
        check("(e) gate is RED", r["ok"] is False, r["status"])
        check("(e) verdict names the commit-half failure",
              "FAILS AT THE COMMIT" in r["specs"][0]["verdict"], r["specs"][0]["verdict"][:120])
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    # ── (f) malformed trailer ────────────────────────────────────────────────
    print("  (f) malformed trailer (missing SPEC_ prefix)")
    repo, sha = _mkrepo(parent_bot="X = 1\n", child_bot="X = 5\n", assertion="X = 5",
                        message="change\n\nAcceptance: rig/test_x.py::demo")
    try:
        r = spec_gate.check_commit(repo, sha)
        check("(f) gate is RED", r["ok"] is False, r["status"])
        check("(f) verdict says MALFORMED", "MALFORMED" in r["specs"][0]["verdict"],
              r["specs"][0]["verdict"][:120])
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    print("GATE 5 CONTROLS: " + ("ALL BEHAVED" if not FAILS else "RED: " + ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
