"""FUNCTIONAL premarket-gate tests — synthetic clocks through the REAL gate functions.
Born 7/23 after the mode shipped DOA behind source-grep pins. These tests CALL the code.
The chain: wake(in_trading_window) -> run(run_window_ok) -> detect(detect_gate)
-> detectors step (rocket rig T23) -> trades blocked pre-9:30 (rocket rig T24b)."""
import sys, pathlib
from datetime import datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
bot = load_bot()
PASS, FAIL = [], []
def check(n, cond):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n)
def T(h, m, wd=3):   # synthetic ET time; wd=3 => Thursday
    return datetime(2026, 7, 23 if wd == 3 else 25, h, m)

# link 1 — wake window (weekday)
check("P1 3:54 not in window; 3:55 IS (wake)", not bot.in_trading_window(T(3,54)) and bot.in_trading_window(T(3,55)))
check("P2 weekend never in window", not bot.in_trading_window(T(3,55,wd=5)))
# link 2 — main run gate (the day-1 killer: 3:55 must PASS now)
check("P3 run_window_ok TRUE at 3:55 (was the DOA gate)", bot.run_window_ok(T(3,55)))
check("P4 run_window_ok FALSE at 3:54 / TRUE 8:45+12:00 / FALSE 15:31",
      not bot.run_window_ok(T(3,54)) and bot.run_window_ok(T(8,45))
      and bot.run_window_ok(T(12,0)) and not bot.run_window_ok(T(15,31)))
# link 3 — watch-loop detect gate (the second DOA gate: 5:00 must DETECT now)
check("P5 detect_gate: idle 3:56, DETECT 4:00/5:00/9:00/9:29 (premarket shadow window)",
      bot.detect_gate(T(3,56)) == "idle" and bot.detect_gate(T(4,0)) == "detect"
      and bot.detect_gate(T(5,0)) == "detect" and bot.detect_gate(T(9,29)) == "detect")
check("P6 detect_gate: detect 9:30-15:29, closed 15:30 (RTH unchanged)",
      bot.detect_gate(T(9,30)) == "detect" and bot.detect_gate(T(15,29)) == "detect"
      and bot.detect_gate(T(15,30)) == "closed")
# link 4 — trades stay blocked premarket (choke gate constant)
check("P7 ENTRY_OPEN_ET=09:30 and '05:00' < it (string compare the gate uses)",
      bot.ENTRY_OPEN_ET == "09:30" and "05:00" < bot.ENTRY_OPEN_ET and not ("09:30" < bot.ENTRY_OPEN_ET))
# regression — the dead hardcoded gates must be GONE from source
SRC = (pathlib.Path(__file__).resolve().parent.parent / "marcos_trading_bot.py").read_text()
check("P8 hardcoded 8:30 floor GONE; hardcoded 9:30 watch-sleep GONE (fail-without-fix)",
      "8 * 60 + 30 <= minutes_et" not in SRC
      and "if now.hour < 9 or (now.hour == 9 and now.minute < 30):" not in SRC)
check("P9 both call sites wired to the pure functions",
      "if not run_window_ok(now):" in SRC and '_dg = detect_gate(now)' in SRC)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL: print("RED:", ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
