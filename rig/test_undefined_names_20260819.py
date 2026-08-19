#!/usr/bin/env python3
"""
RIG GATE 20 — UNDEFINED-NAME SWEEP (8/19: kill the class, not the instance)

THE CLASS THIS KILLS
  A name referenced outside its scope compiles fine, imports fine, and detonates only when the
  line RUNS — and if a try/except is nearby, it doesn't even detonate: the feature silently
  fail-opens forever. Both flavors shipped and both cost us:
    * `cache` in _trade_worker's record payload (8/18 build): NameError AFTER every exit, BEFORE
      the record post — VRAX 08:59:25 and CISS 09:58:51 both exited correctly and reached the
      book as ghosts. Every exit under that build died unrecorded.
    * `urllib` in the zone-stamp day-high fetch (8/3 build): swallowed by the inner except, so
      the tape pre-break gate (kill-tested +$82.72/+$72.36 on the worst sessions) and the
      retest-band gate were FAIL-OPEN DEAD FROM BIRTH — 16 days, invisible, because fail-open
      looks identical to working-and-passing.

  Syntax checks can't catch this. Import can't catch this. Only static name resolution can,
  which is exactly what pyflakes' undefined-name check is.

VERDICT: RED if pyflakes reports any undefined name in marcos_trading_bot.py or screener_app.py
beyond the pinned allowlist. The allowlist requires the guard to still be present — if the
guard is refactored away, the entry stops being exempt.

  ALLOW: `b4` at the ignition reject-row site — evaluated only behind an
         `isinstance(locals().get("b4"), dict)` guard, so it can never raise.
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = ["marcos_trading_bot.py", "screener_app.py"]
# name -> the guard text that must still exist in the file for the exemption to hold
ALLOW = {"b4": 'locals().get("b4")'}

FAIL = []
for f in FILES:
    p = ROOT / f
    if not p.exists():
        continue
    r = subprocess.run([sys.executable, "-m", "pyflakes", str(p)], capture_output=True, text=True)
    src = p.read_text()
    for line in (r.stdout or "").splitlines():
        m = re.search(r"undefined name '([^']+)'", line)
        if not m:
            continue
        name = m.group(1)
        guard = ALLOW.get(name)
        if guard and guard in src:
            print(f"  ok  {f}: '{name}' exempt (guard present: {guard})")
            continue
        print(f"  XX  {line.strip()}")
        FAIL.append(line.strip())

print("=" * 78)
if FAIL:
    print(f"RED — {len(FAIL)} undefined name(s). This is the VRAX/CISS ghost-exit class and the")
    print("dead-gate class. Fix the scope or import — do NOT allowlist without a proven guard.")
    sys.exit(1)
print("GREEN — no unguarded undefined names in the live services")
sys.exit(0)
