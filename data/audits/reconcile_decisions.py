#!/usr/bin/env python3
"""GATE 7 — DECISION-VS-DEPLOYED RECONCILER (built 8/17).

A settled ruling that lives only in prose drifts silently.  8/17 found four of them at once:
kev_shadow written since 8/12 and read nowhere; the chart-gate bypass list copy-pasted and
stale (kevseq absent, WFF killed at $5.04); the refuted momentum scalar still vetoing a tape
lane; task #57 asserted shipped while sitting in the queue.  None of these were caught by a
check, because no check existed — the decisions were sentences.

This turns every settled ruling in data/audits/DECISIONS.md into a command that is run against
the CURRENT tree and the LIVE service, nightly, and reports the DRIFTED rows.

    HOLDS    exit 0   — the decision is still true of the code/config
    DRIFTED  non-0    — the decision was settled and the machine no longer honours it
    UNKNOWN  exit 3   — the check could not reach its evidence (offline service, missing file).
                        Never counted as HOLDS. Never counted as DRIFTED. Reported as its own
                        state, because "I couldn't check" and "it's fine" are different facts.

USAGE
    python3 data/audits/reconcile_decisions.py              # run every row, print the report
    python3 data/audits/reconcile_decisions.py --json out.json
    python3 data/audits/reconcile_decisions.py --strict     # exit 1 if anything DRIFTED
    python3 data/audits/reconcile_decisions.py --probe-live dry_run   # live-env probe helper

Exit 0 normally (it REPORTS; the nightly must not die on it).  --strict makes it a gate.
Wired into the existing nightly job (data/killtests/nightly_book_verify.py) — no new launchd
agent was created; that needs Marcos's say-so.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.environ.get("DECISIONS_ROOT") or \
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# DECISIONS_ROOT / DECISIONS_REGISTRY exist so the rig's negative control can point the same
# checks at a MUTATED copy of the tree and prove each row is capable of going DRIFTED.
REGISTRY = os.environ.get("DECISIONS_REGISTRY") or \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "DECISIONS.md")
DASH = "https://zestful-intuition-production-b16a.up.railway.app"
UNKNOWN_RC = 3

ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|(.+?)\|(.+?)\|\s*`(.+?)`\s*\|\s*$")


def parse_registry(path=REGISTRY):
    """-> [ {id, decision, expected, check} ] from the markdown table."""
    rows = []
    if not os.path.exists(path):
        return rows
    for line in open(path):
        m = ROW.match(line.rstrip("\n"))
        if not m:
            continue
        rid, dec, exp, chk = (g.strip() for g in m.groups())
        rows.append({"id": rid, "decision": dec, "expected": exp, "check": chk})
    return rows


def run_row(row, timeout=120):
    try:
        p = subprocess.run(["/bin/zsh", "-c", row["check"]], cwd=ROOT,
                           capture_output=True, text=True, timeout=timeout)
        rc, out = p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        rc, out = UNKNOWN_RC, "check timed out after %ds" % timeout
    state = "HOLDS" if rc == 0 else ("UNKNOWN" if rc == UNKNOWN_RC else "DRIFTED")
    return dict(row, rc=rc, state=state, output=out[:400])


# ── live-env probes (the rows whose truth is in the DEPLOYED service, not the source) ──────
def live_boot_config():
    """The LATEST boot_config decision row the running bot published, or None if unreachable.
    (There is no /api/boot_config route — boot_config is a decision STATUS on the timeline;
    asserting the route existed was exactly the kind of unverified claim these gates exist for.)"""
    try:
        url = DASH + "/api/decisions?status=boot_config&limit=5"
        with urllib.request.urlopen(url, timeout=25) as r:
            rows = (json.load(r) or {}).get("rows") or []
    except Exception as e:
        print("  UNKNOWN: cannot reach the decisions timeline (%s)" % type(e).__name__)
        return None
    if not rows:
        print("  UNKNOWN: no boot_config row on the timeline (bot not booted since last redeploy?)")
        return None
    return rows[-1]


# field -> (predicate, human description). Truth for these lives in the DEPLOYED service.
LIVE_PROBES = {
    "dry_run": (lambda v: str(v).strip().lower() in ("1", "true", "yes", "on"),
                "dry_run must be TRUE for the whole proving week"),
    "e3_exits": (lambda v: str(v).strip() in ("1", "True", "true"), "E3 exits on"),
    "entry_open_et": (lambda v: str(v).strip() == "07:00", "PRE entries open at 07:00 ET"),
}


def probe_live(name):
    """Exit 0 = holds, 1 = drifted, 3 = could not reach the evidence."""
    if name not in LIVE_PROBES:
        print("  UNKNOWN: no probe named %r" % name)
        return UNKNOWN_RC
    cfg = live_boot_config()
    if cfg is None:
        return UNKNOWN_RC
    pred, desc = LIVE_PROBES[name]
    if name not in cfg:
        print("  UNKNOWN: boot_config carries no %r field" % name)
        return UNKNOWN_RC
    v = cfg[name]
    ok = pred(v)
    print("  live %s = %r  (booted %s, deploy %s) — %s"
          % (name, v, cfg.get("recorded_at", "?")[:19], cfg.get("deploy_id", "?"), desc))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="GATE 7 — decision-vs-deployed reconciler")
    ap.add_argument("--json")
    ap.add_argument("--strict", action="store_true", help="exit 1 when any row has DRIFTED")
    ap.add_argument("--probe-live", help="internal: run a live-service probe and exit")
    a = ap.parse_args()

    if a.probe_live:
        return probe_live(a.probe_live)

    rows = parse_registry()
    if not rows:
        print("DECISION RECONCILER — ❌ registry empty or unreadable: %s" % REGISTRY)
        return 1
    results = [run_row(r) for r in rows]
    drift = [r for r in results if r["state"] == "DRIFTED"]
    unk = [r for r in results if r["state"] == "UNKNOWN"]
    print("DECISION RECONCILER — %d rows: %d HOLDS, %d DRIFTED, %d UNKNOWN"
          % (len(results), len(results) - len(drift) - len(unk), len(drift), len(unk)))
    for r in results:
        mark = {"HOLDS": "✅", "DRIFTED": "🚨", "UNKNOWN": "⚠️ "}[r["state"]]
        print("  %s %-32s %s" % (mark, r["id"], r["state"]))
        if r["state"] != "HOLDS":
            print("      expected: %s" % r["expected"][:160])
            print("      check   : %s  (rc=%s)" % (r["check"][:140], r["rc"]))
            if r["output"]:
                print("      output  : %s" % r["output"].splitlines()[0][:160])
    if drift:
        print("\n🚨 %d SETTLED DECISION(S) HAVE DRIFTED: %s"
              % (len(drift), ", ".join(r["id"] for r in drift)))
        print("   These were decided and are no longer true. Restore the behaviour or take a "
              "NEW decision to Marcos — never let the row quietly rot.")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(results, fh, indent=1)
        print("  wrote %s" % a.json)
    return 1 if (a.strict and drift) else 0


if __name__ == "__main__":
    sys.exit(main())
