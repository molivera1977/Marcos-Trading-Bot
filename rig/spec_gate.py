#!/usr/bin/env python3
"""GATE 5 — SPEC-AS-FAILING-TEST (built 8/17; Marcos: "guaranteed that something is built
AND built as specified").

THE PROBLEM IT SOLVES
---------------------
8/17 produced a phantom defect: "the caller feeds kevseq a 3-MINUTE front side against a
1-MINUTE spec".  It was asserted from a grep, believed, and a fix was scoped for it.  The
defect did not exist (see the REFUTED block at marcos_trading_bot.py ~:6549).  Prose rules
("verify before speak") did not stop it.  A program can.

If, before writing the fix, the author had been REQUIRED to write the acceptance test
("assert the kevseq caller reads the SETUP_TF_MIN aggregate") and REQUIRED to watch it FAIL
on the pre-fix code, the test would have PASSED at the parent -- proving the premise false and
refusing the build.  That is exactly what this gate mechanises.

THE CONTRACT
------------
A behaviour-changing commit MUST carry a trailer line in its commit message:

    Acceptance: rig/test_gates_20260817.py::SPEC_<name>

 * `Acceptance:` at the start of a line (case-insensitive), one per commit (extras are run too).
 * The path is repo-relative and MUST be a python file runnable as
   `python3 <path> <SPEC_NAME>`, exiting 0 when the named spec PASSES and non-0 when it FAILS.
   (rig/test_gates_20260817.py implements that CLI; any file may, as long as it honours it.)
 * `SPEC_<name>` is the spec's id.  The `SPEC_` prefix is required so specs are greppable and
   can never be confused with the rig's ordinary always-on sections.

Both halves are then verified against real git trees:

  (1) PARENT half -- the commit's parent is checked out into a throwaway `git worktree`, the
      acceptance test file is COPIED IN from the commit (it does not exist at the parent --
      that is the whole point), and the named spec is run.  It MUST FAIL.
      If it PASSES, the gate goes RED with an explicit verdict:
          the change was unnecessary, or the premise is false.
      THIS IS THE BRANCH THAT WOULD HAVE CAUGHT THE 8/17 PHANTOM DEFECT.

  (2) COMMIT half -- the commit itself is checked out into a second throwaway worktree and the
      same spec is run.  It MUST PASS.

The live working tree is NEVER touched: no `git stash`, no checkout, no index writes.  Only
`git worktree add --detach` into a temp dir, removed on exit.  (8/17: a concurrent agent was
editing the same repo -- stashing would have destroyed its work.  Worktrees are the law here.)

"BEHAVIOUR-CHANGING" -- HOW IT IS DECIDED
-----------------------------------------
A commit is behaviour-changing iff it touches `marcos_trading_bot.py` or `screener_app.py`
in a way that survives this normalisation (applied to the FULL file at parent and at commit):

    parse with `ast`  ->  drop every docstring / bare string-expression statement
                      ->  drop every statement that is only a call to print() / _log_decision()
                      ->  ast.dump()

Comments never reach the AST at all, so they are exempt by construction.  If the two dumps are
byte-identical the commit is EXEMPT (docs / comments / pure-logging only).  Files other than
those two (data/, rig/, killtests, audits, docs, ledger) are always exempt.

LIMITS, STATED PLAINLY (the classifier is conservative -- it errs toward DEMANDING a test):
  * A file that does not parse (syntax error at either end) -> treated as BEHAVIOUR-CHANGING.
  * Renaming a local variable, reordering independent statements, or changing a constant's
    formatting all survive normalisation -> classified behaviour-changing though they may not
    be.  That is the safe direction: the cost is writing a test you might not have needed.
  * "Pure logging" is recognised ONLY for statement-level `print(...)` and `_log_decision(...)`
    calls.  A logging call nested inside a NEW `if` still counts as behaviour-changing,
    because the `if` is control flow.
  * It classifies a COMMIT, not a merge.  Merge commits (2+ parents) are EXEMPT and reported
    as such -- there is no single parent tree to falsify against.
  * Env-var DEFAULT changes ARE behaviour-changing and are caught (they are AST constants).

FORWARD-LOOKING ONLY.  Historical commits are NOT gated and MUST NOT be retro-run: nothing
before 8/17 carries the trailer, and inventing acceptance tests after the fact is precisely
the story-first failure this gate exists to stop.

HOW TO RUN IT ON A CANDIDATE COMMIT BEFORE PUSHING
--------------------------------------------------
    python3 rig/spec_gate.py HEAD            # the commit you just wrote
    python3 rig/spec_gate.py <sha>           # any specific commit
    python3 rig/spec_gate.py HEAD --repo /path/to/repo
    python3 rig/spec_gate.py HEAD --verbose  # show the test output from both halves

Exit 0 = GREEN (exempt, or both halves proven).  Exit 1 = RED, with the reason.
Import it (`from spec_gate import check_commit`) to get the structured verdict.
"""
import argparse
import ast
import os
import shutil
import subprocess
import sys
import tempfile

WATCHED = ("marcos_trading_bot.py", "screener_app.py")
LOG_FUNCS = {"print", "_log_decision"}
TRAILER = "acceptance:"
TEST_TIMEOUT_S = int(os.environ.get("SPEC_GATE_TIMEOUT_S", "600"))


# ── git plumbing ──────────────────────────────────────────────────────────────
def _git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", repo] + list(args),
                       capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), (p.stderr or p.stdout).strip()))
    return p.stdout


def _blob(repo, rev, path):
    """File content at <rev>:<path>, or None when the path does not exist there."""
    p = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (rev, path)],
                       capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


# ── behaviour classification ──────────────────────────────────────────────────
class _Strip(ast.NodeTransformer):
    """Remove docstrings / bare string statements and statement-level logging calls."""

    def _clean_body(self, node):
        out = []
        for st in node.body:
            if isinstance(st, ast.Expr):
                v = st.value
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    continue                                  # docstring / bare string
                if isinstance(v, ast.Call):
                    f = v.func
                    name = getattr(f, "id", None) or getattr(f, "attr", None)
                    if name in LOG_FUNCS:
                        continue                              # pure-logging statement
            out.append(st)
        node.body = out or [ast.Pass()]
        return node

    def visit_Module(self, node):
        self.generic_visit(node)
        return self._clean_body(node)

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        return self._clean_body(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        return self._clean_body(node)


def normalize(src):
    """AST dump with comments/docstrings/pure-logging removed. None when unparseable."""
    if src is None:
        return None
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    return ast.dump(_Strip().visit(tree))


def classify(repo, sha):
    """-> (is_behavior_changing: bool, reason: str, touched: list[str])"""
    parents = _git(repo, "rev-list", "--parents", "-n", "1", sha).split()
    if len(parents) > 2:
        return False, "merge commit (%d parents) — no single parent tree to falsify against" % (len(parents) - 1), []
    if len(parents) < 2:
        return True, "root commit (no parent) — cannot be proven against a parent tree", []
    parent = parents[1]
    files = [f for f in _git(repo, "diff", "--name-only", "%s..%s" % (parent, sha)).split() if f]
    touched = [f for f in files if os.path.basename(f) in WATCHED]
    if not touched:
        return False, "touches no watched file (%s)" % ", ".join(WATCHED), []
    changed = []
    for f in touched:
        a, b = normalize(_blob(repo, parent, f)), normalize(_blob(repo, sha, f))
        if a is None or b is None:
            return True, "%s did not parse at one end — classified behaviour-changing (conservative)" % f, touched
        if a != b:
            changed.append(f)
    if not changed:
        return False, "watched files changed in comments/docstrings/pure-logging only", touched
    return True, "code semantics changed in: %s" % ", ".join(changed), touched


# ── trailer ───────────────────────────────────────────────────────────────────
def acceptance_trailers(repo, sha):
    msg = _git(repo, "log", "-1", "--format=%B", sha)
    out = []
    for line in msg.splitlines():
        s = line.strip()
        if s.lower().startswith(TRAILER):
            val = s[len(TRAILER):].strip()
            if "::" not in val:
                out.append((val, None, "malformed — expected <path>::SPEC_<name>"))
                continue
            path, name = val.split("::", 1)
            path, name = path.strip(), name.strip()
            if not name.startswith("SPEC_"):
                out.append((path, name, "spec id must start with SPEC_"))
                continue
            out.append((path, name, None))
    return out


# ── worktrees ─────────────────────────────────────────────────────────────────
def _run_spec(repo, rev, test_path, spec_name, inject_from=None, verbose=False):
    """Check <rev> into a throwaway worktree and run `python3 <test_path> <spec_name>`.

    inject_from: a rev to copy the test file in FROM (used for the parent half, where the
    acceptance test does not exist yet). Returns (exit_code, combined_output)."""
    tmp = tempfile.mkdtemp(prefix="specgate_")
    wt = os.path.join(tmp, "wt")
    try:
        _git(repo, "worktree", "add", "--detach", "--quiet", wt, rev)
        if inject_from:
            content = _blob(repo, inject_from, test_path)
            if content is None:
                return 127, "acceptance test %s does not exist at %s" % (test_path, inject_from)
            dest = os.path.join(wt, test_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w") as fh:
                fh.write(content)
        target = os.path.join(wt, test_path)
        if not os.path.exists(target):
            return 127, "acceptance test %s not present in the %s tree" % (test_path, rev)
        env = dict(os.environ, DRY_RUN="1", SPEC_GATE_CHILD="1")
        env.pop("SHIP_CHECK", None)
        try:
            p = subprocess.run([sys.executable, target, spec_name], cwd=wt, env=env,
                               capture_output=True, text=True, timeout=TEST_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return 124, "acceptance test timed out after %ds" % TEST_TIMEOUT_S
        out = (p.stdout or "") + (p.stderr or "")
        if verbose:
            print("      ── %s output ──\n%s" % (rev[:12], "\n".join("      " + l for l in out.splitlines()[-40:])))
        return p.returncode, out
    finally:
        subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt],
                       capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)


# ── the gate ──────────────────────────────────────────────────────────────────
def check_commit(repo, sha, verbose=False):
    """-> dict(ok=bool, status=str, reason=str, specs=[...])"""
    sha = _git(repo, "rev-parse", sha).strip()
    behav, why, touched = classify(repo, sha)
    if not behav:
        return {"ok": True, "sha": sha, "status": "EXEMPT", "reason": why, "specs": []}

    trailers = acceptance_trailers(repo, sha)
    if not trailers:
        return {"ok": False, "sha": sha, "status": "NO_ACCEPTANCE_TEST",
                "reason": ("behaviour-changing (%s) but the commit message names no acceptance "
                           "test.  Add a trailer:  Acceptance: rig/test_gates_20260817.py::SPEC_<name>"
                           % why), "specs": []}

    parent = _git(repo, "rev-parse", sha + "^").strip()
    results, ok = [], True
    for path, name, err in trailers:
        if err:
            ok = False
            results.append({"spec": "%s::%s" % (path, name), "ok": False, "verdict": "MALFORMED: " + err})
            continue
        p_rc, p_out = _run_spec(repo, parent, path, name, inject_from=sha, verbose=verbose)
        if p_rc == 0:
            ok = False
            results.append({"spec": "%s::%s" % (path, name), "ok": False, "parent_rc": 0,
                            "verdict": ("PASSES AT THE PARENT — the change was UNNECESSARY, or the "
                                        "PREMISE IS FALSE.  The behaviour you claim to be adding is "
                                        "already there at %s.  Do not build it: go re-check the claim "
                                        "that motivated this commit." % parent[:12])})
            continue
        if p_rc in (124, 127):
            ok = False
            results.append({"spec": "%s::%s" % (path, name), "ok": False, "parent_rc": p_rc,
                            "verdict": "PARENT HALF INCONCLUSIVE (rc=%d): %s" % (p_rc, p_out[-400:].strip())})
            continue
        c_rc, c_out = _run_spec(repo, sha, path, name, verbose=verbose)
        if c_rc != 0:
            ok = False
            results.append({"spec": "%s::%s" % (path, name), "ok": False, "parent_rc": p_rc, "commit_rc": c_rc,
                            "verdict": ("FAILS AT THE COMMIT — the spec is not satisfied by the code you "
                                        "wrote (rc=%d): %s" % (c_rc, c_out[-400:].strip()))})
            continue
        results.append({"spec": "%s::%s" % (path, name), "ok": True, "parent_rc": p_rc, "commit_rc": 0,
                        "verdict": "PROVEN — fails at parent (rc=%d), passes at commit" % p_rc})
    return {"ok": ok, "sha": sha, "status": "PROVEN" if ok else "RED", "reason": why, "specs": results}


def main():
    ap = argparse.ArgumentParser(description="GATE 5 — spec-as-failing-test")
    ap.add_argument("commit", nargs="?", default="HEAD")
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    r = check_commit(a.repo, a.commit, verbose=a.verbose)
    print("SPEC GATE  %s  %s" % (r["sha"][:12], r["status"]))
    print("  classification: %s" % r["reason"])
    for s in r["specs"]:
        print(("  %s %s\n      %s") % ("✅" if s["ok"] else "❌", s["spec"], s["verdict"]))
    if r["status"] == "NO_ACCEPTANCE_TEST":
        print("  ❌ %s" % r["reason"])
    print("  => %s" % ("GREEN" if r["ok"] else "RED"))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
