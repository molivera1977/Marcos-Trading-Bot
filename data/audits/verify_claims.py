#!/usr/bin/env python3
"""CLAIMS LEDGER VERIFIER — re-runs every claim's command and grades it.

Marcos 8/17: prose rules are advisory; a program is not.  data/audits/CLAIMS.md holds one row
per verified fact about the machine, each carrying the exact command that reproduces it.  This
script re-runs them all and prints PASS / CHANGED / FAILED / NO-COMMAND per row.

  PASS        command ran, stdout == expected
  CHANGED     command ran, stdout != expected  -> the machine moved; APPEND a new row (never
              edit the old one) or fix the code
  FAILED      command errored / timed out
  NO-COMMAND  the row has no command  -> the claim is prose, which is what this file exists
              to abolish

Exit code: 0 iff every row PASSes.  Rig section EG3 pins that, and this script is appended to
the nightly run so a drifted fact surfaces the night it drifts, not the next time I misquote it.

Read-only: every seeded command is a grep/read.  Nothing here writes, deploys, or touches the
broker.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "data", "audits", "CLAIMS.md")
TIMEOUT = 60


def _unescape(cell):
    """{PIPE} -> | and {NL} -> newline.  Markdown tables cannot carry a raw pipe, so the ledger
    writes the placeholder and the verifier puts it back before running/comparing."""
    return cell.replace("{PIPE}", "|").replace("{NL}", "\n")


def parse(path=LEDGER):
    """Yield (lineno, date, claim, command, expected) for every data row of the ledger table."""
    rows = []
    for i, ln in enumerate(open(path, errors="replace").read().splitlines(), 1):
        s = ln.strip()
        if not s.startswith("|") or not s.endswith("|"):
            continue
        cells = [c.strip() for c in s[1:-1].split("|")]
        # a row's cells may themselves contain {PIPE}; splitting on the literal | is therefore
        # safe by construction (that is why the placeholder exists).
        if len(cells) != 4:
            continue
        date, claim, cmd, exp = cells
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            continue                      # header / separator / format-doc rows
        cmd = _unescape(cmd.strip("`").strip())
        exp = _unescape(exp.strip("`").strip())
        rows.append((i, date, claim, cmd, exp))
    return rows


def run_row(cmd):
    try:
        p = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True,
                           timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return "FAILED", f"timed out after {TIMEOUT}s"
    if p.returncode != 0 and not p.stdout.strip():
        return "FAILED", (p.stderr.strip() or f"exit {p.returncode}")[:300]
    return None, p.stdout.strip()


def verify(path=LEDGER, quiet=False):
    rows = parse(path)
    results = []
    for lineno, date, claim, cmd, exp in rows:
        if not cmd:
            results.append(("NO-COMMAND", lineno, date, claim, "", exp))
            continue
        # 8/21: the ledger's APPEND-ONLY rule says a changed fact gets a NEW row while the old
        # one is marked "SUPERSEDED by <date>". The verifier never implemented that half, so the
        # first time the protocol was actually used (SIM_ACCOUNT_BALANCE 3000 -> 5000) the
        # superseded row graded CHANGED and took EG3 — and therefore every ship — RED. A
        # superseded row is EXPECTED to no longer reproduce; that is what superseded means. It
        # is reported (never silently dropped) and does not fail the gate.
        if "SUPERSEDED" in claim.upper():
            results.append(("SUPERSEDED", lineno, date, claim, "", exp))
            continue
        status, out = run_row(cmd)
        if status == "FAILED":
            results.append(("FAILED", lineno, date, claim, out, exp))
        elif out == exp:
            results.append(("PASS", lineno, date, claim, out, exp))
        else:
            results.append(("CHANGED", lineno, date, claim, out, exp))
    if not quiet:
        ICON = {"PASS": "✅", "CHANGED": "⚠️ ", "FAILED": "❌", "NO-COMMAND": "❌", "SUPERSEDED": "🕓"}
        print(f"CLAIMS LEDGER — {len(results)} rows  ({LEDGER})")
        for st, lineno, date, claim, got, exp in results:
            print(f"  {ICON[st]} {st:<10} L{lineno:<4} {date}  {claim[:88]}")
            if st in ("CHANGED", "FAILED"):
                print(f"      expected: {exp!r}")
                print(f"      got     : {got!r}")
        bad = [r for r in results if r[0] not in ("PASS", "SUPERSEDED")]   # 8/21: superseded rows are history, not failures
        print(f"\n{'ALL CLAIMS VERIFIED' if not bad else 'CLAIMS NOT VERIFIED: %d row(s)' % len(bad)}")
    return results


if __name__ == "__main__":
    res = verify(quiet="--quiet" in sys.argv)
    sys.exit(0 if all(r[0] == "PASS" for r in res) else 1)
