#!/usr/bin/env python3
"""
GATE 13 — A MONEY GATE THAT CANNOT SEE MUST SAY SO (8/18)

THE CLASS (per feedback_kill_the_class_not_instance — the pin goes on the class, not on CDTG):
  The ignition stack gate read
      _ig_stack_bad = (IGNITION_STACK_GATE and _e9 > 0 and _e20 > 0 and _e9 < _e20)
  where `_e9/_e20` were computed off RTH-ONLY bars needing 66 minutes of RTH. Before ~10:36 ET
  they were 0.0, `_e9 > 0` was False, and the gate FAILED OPEN — invisibly. It shipped 8/18
  11:22, was tuned all evening, and was measured that night to be worth EXACTLY NOTHING:
  LIVE_NOW $207.58/day @N=6 vs NOSTACK $207.58 — identical to the cent
  (data/killtests/ignition_stack_warmup_20260818.py). 69% of era ignition fills fired blind.

  The defect was not the threshold. It was that a gate could be unevaluable and NOTHING SAID SO
  — not the row, not the log, not the rig. This gate pins the fix so the class cannot return.

WHAT IS PINNED (all failures are hard)
  A. the kill switch exists (IGNITION_STACK_WARMUP) and defaults ON
  B. the warm-up seed is CACHED SEPARATELY and never mixed into full_bars/bars — every other
     detector must keep seeing today-RTH-only (this is what makes the change narrow)
  C. the seed feeds the EMA MATH only: `_ig_comp` is still built from full_bars, untouched
  D. every ignition decision row stamps `stack_src`, so a blind pass is never invisible again
  E. the three stack states are all reachable and named: warmed / rth_only / unevaluable
  F. the gate still FAILS OPEN when unevaluable (FAILCLOSED measured -$180.53/day: it blanks
     the open hour). This is a DELIBERATE, MEASURED choice — the pin stops it being changed by
     accident, not by decision.
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HERE, "..", "marcos_trading_bot.py")
SRC = open(BOT).read()
FAILS = []


def chk(ok, label, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"   {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


print("GATE 13 — a money gate that cannot see must say so")
print("=" * 78)

# A. kill switch, default on
m = re.search(r'IGNITION_STACK_WARMUP\s*=\s*os\.environ\.get\(\s*"IGNITION_STACK_WARMUP",\s*"(\d)"\s*\)', SRC)
chk(bool(m), "A1 IGNITION_STACK_WARMUP kill switch exists")
chk(bool(m) and m.group(1) == "1", "A2 warm-up defaults ON")

# B. the seed is cached separately, never merged into the shared bar caches
chk('cache[t]["ig_pm_closes"]' in SRC, "B1 seed cached under its own key (ig_pm_closes)")
bad = re.search(r'cache\[t\]\["(full_bars|bars)"\]\s*=\s*[^\n]*ig_pm_closes', SRC)
chk(not bad, "B2 seed NEVER assigned into full_bars/bars")
# the seed must be built from a PRE-inclusive source, and premarket bars only
seed_blk = SRC[SRC.find("IGNITION STACK WARM-UP"):][:1200]
chk('trading_session' in seed_blk and 'RTH' in seed_blk,
    "B3 seed built from the PRE+RTH fetch, premarket bars only")

# C. _ig_comp still comes from full_bars (the seed feeds EMA math only)
chk(re.search(r'_ig_comp\s*=\s*aggregate_bars\(cache\[t\]\.get\("full_bars"\)', SRC) is not None,
    "C1 _ig_comp still built from full_bars (untouched)")
chk("_ig_cl = _ig_seed + _extract_closes(_ig_comp)" in SRC,
    "C2 seed concatenated for the EMA math only")

# D. every ignition decision row stamps stack_src
n_stamp = SRC.count("stack_src=_ig_stack_src")
chk(n_stamp >= 3, "D1 stack_src stamped on all 3 ignition decision rows", f"found {n_stamp}")
chk("stack_seed_n=len(_ig_seed)" in SRC, "D2 seed length stamped (blindness is auditable)")

# E. all three states reachable and named
for st in ("warmed", "rth_only", "unevaluable"):
    chk(f'"{st}"' in SRC, f"E:{st} state is named in source")

# F. the gate still fails OPEN when unevaluable — `_e9 > 0` guard intact
g = re.search(r'_ig_stack_bad\s*=\s*\(IGNITION_STACK_GATE and _e9 > 0 and _e20 > 0\s*\n?\s*and _e9 < _e20\)', SRC)
chk(bool(g), "F1 gate still fails OPEN when the EMAs are unevaluable (measured choice)")

# structural: the file parses
try:
    ast.parse(SRC)
    chk(True, "G1 bot source parses")
except SyntaxError as e:
    chk(False, "G1 bot source parses", str(e))

print("=" * 78)
if FAILS:
    print(f"GATE 13 FAILED ({len(FAILS)}): " + "; ".join(FAILS))
    sys.exit(1)
print("GATE 13 PASSED")
sys.exit(0)
