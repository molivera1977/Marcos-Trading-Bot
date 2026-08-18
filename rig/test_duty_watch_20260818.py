#!/usr/bin/env python3
"""
GATE 12 — THE DUTY WATCH MUST BE SERVER-SIDE AND MUST ACTUALLY FIRE (8/18)

WHY THIS GATE EXISTS
  Marcos: "are they actually going to do something." The intraday watch was supposed to run
  as laptop scheduled tasks. Checked, and the honest answer was no:
    • `bot-preopen-health-check` — "RETIRED 8/4 — Laptop scheduler silently dead since 7/27"
    • `kev-sweep-night`          — "RETIRED 8/4 — Laptop scheduler was silently dead since 7/26"
    • `postah-bars-backfill`     — "RETIRED 8/4 — Laptop scheduler silently dead since 7/26"
    • `kev-daily-scorecard`      — ENABLED, weekdays 16:22, lastRunAt 2026-08-14. It silently
                                   missed Monday 8/17.
  Three tombstones and a live miss. A watch that needs a laptop awake is not a watch, and
  Marcos returns to work 8/20.

  So this gate pins the migration: DETECTION lives in the bot process (like kev_sweep and
  preopen_health after 8/4), where it runs whether or not anyone's laptop is open.
  Interpretation still needs a session; the RECORD no longer does.

  The irony is the point: the thing most likely to die quietly is the watchman. This gate is
  the watchman's watchman.

Exit 0 = green.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()

FAILS = []


def check(label, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {label}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)
    return ok


def main():
    print("=" * 78)
    print("GATE 12) SERVER-SIDE DUTY WATCH (Marcos: \"are they actually going to do something\")")
    print("=" * 78)

    # (a) it exists, and it is STARTED — a defined-but-never-started thread is the exact
    #     silent-death mode this replaces
    check("12.1 the watch loop is defined", "def _duty_watch_loop():" in SRC)
    check("12.2 the thread is actually STARTED (not just defined)",
          "threading.Thread(target=_duty_watch_loop, daemon=True, name=\"duty_watch\").start()" in SRC)
    check("12.3 boot announces it, so a missing watch is visible in the boot log",
          "Duty-watch thread started" in SRC)

    # (b) it must emit a DURABLE row. A watch whose only output is a print dies with the log.
    check("12.4 emits a durable watch_check decision row",
          '_log_decision("_WATCH", "watch_check"' in SRC)
    check("12.5 a FAILED check still emits a row (silence is never the report)",
          '"watch_check_failed"' in SRC)

    # (c) THE MARCOS CHECK — fires vs fills, and the gate NAMED
    check("12.6 compares fires to fills per lane",
          "filled.get(lane, 0) == 0" in SRC and "starved.append(" in SRC and "starved=starved" in SRC)
    check("12.7 NAMES the top blocking gate (the whole point of the check)", '"top_gate"' in SRC)
    check("12.8 an uninstrumented death is called out, not silently blank",
          "NO refusal row logged at all" in SRC)

    # (d) it must not be able to touch trading
    tree = ast.parse(SRC)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_duty_watch_loop"), None)
    check("12.9 the watch function parses", fn is not None)
    if fn:
        body = ast.dump(fn)
        for forbidden, why in [("execute_trade", "must never enter a trade"),
                               ("_slot_refund", "must never touch the counter economy"),
                               ("place_order", "must never place an order"),
                               ("monitor_trade", "must never manage a position")]:
            check(f"12.10 read-only: does not call {forbidden} ({why})", forbidden not in body)
        # it must be wrapped so it can never take the process down
        has_try = any(isinstance(n, ast.Try) for n in ast.walk(fn))
        check("12.11 fail-soft: the loop body is wrapped in try/except", has_try)
        # and it must sleep, or it would spin the CPU
        sleeps = [n for n in ast.walk(fn)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == "sleep"]
        check("12.12 the loop sleeps (no busy-spin)", len(sleeps) >= 2,
              f"time.sleep call sites in the loop: {len(sleeps)}")

    # (e) kill switch + configurability, per the standing kill-switch law
    check("12.13 kill switch exists and defaults ON", 'DUTY_WATCH = os.environ.get("DUTY_WATCH", "1")' in SRC)
    check("12.14 checkpoint times are configurable, with the four defaults",
          '"07:12,09:42,12:48,15:52"' in SRC)
    check("12.15 the starved threshold is configurable (one unfilled fire is noise)",
          "DUTY_WATCH_MIN_FIRES" in SRC)

    # (f) idempotence — one row per checkpoint per ET day, and weekends excluded
    check("12.16 one row per (day, checkpoint): a restart cannot double-log",
          "if not cp or (day, cp) in fired:" in SRC)
    check("12.17 weekends skipped", "if now.weekday() >= 5:" in SRC)

    # (g) THE DEPENDENCY THAT MAKES IT POSSIBLE. The Marcos check needs refusal rows to carry a
    #     lane — that only became true with gate 11 tonight. If refusal attribution regresses,
    #     this watch degrades to "something was refused" with no lane, which is what it replaces.
    check("12.18 depends on gate 11 (refusal rows name their lane) — that gate must be green",
          os.path.exists(os.path.join(ROOT, "rig", "test_refusal_attribution_20260818.py")))
    check("12.19 the watch reads the lane field gate 11 populates",
          'r.get("lane") or r.get("machine") or r.get("entry_type")' in SRC)

    print()
    if FAILS:
        print("RED: " + ", ".join(FAILS))
        return 1
    print("GATE 12 GREEN — the watch is server-side, durable, read-only, and cannot die quietly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
