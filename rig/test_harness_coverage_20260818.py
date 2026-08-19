#!/usr/bin/env python3
"""
GATE 17 — EVERY LIVE DETECTOR MUST BE LIFTABLE (8/18)

THE CLASS: `ema9x90_step` shipped 8/18 12:43 and traded a full session while being absent from
the harness namespace — it could not be lifted, exercised or parity-measured, and it carried a
wall-clock window bug that fired it at 18:59/19:59 on replay tape. Nothing could have caught it,
because nothing checked that a live detector is testable.

A census then found FIVE more unregistered detectors the scan loop calls, two of which traded on
8/18: `detect_ma_pullback` (2 fills; the lane that bought CDTG 66% above VWAP at 14:16:43) and
`dip_rip_step` (1 fill, -$34.67 PFSA).

This gate makes an unexercisable lane FAIL THE SHIP instead of trading unwatched.

GRANDFATHERING: none. Every detector the live loop calls must appear in the harness's extracted
namespace. If a new detector is genuinely un-liftable, the honest move is an explicit entry in
KNOWN_UNLIFTABLE below WITH the reason — the same discipline live_harness.isolability_report()
already applies to _marked_runway and _zf_pm_floor.
"""
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOT = open(os.path.join(HERE, "..", "marcos_trading_bot.py")).read()
HP = os.path.join(HERE, "..", "data", "killtests", "live_harness.py")
sp = importlib.util.spec_from_file_location("H", HP)
H = importlib.util.module_from_spec(sp); sp.loader.exec_module(H)
FAILS = []

# detectors that are live-callable but genuinely cannot be lifted — each needs a REASON.
KNOWN_UNLIFTABLE = {}


def chk(c, label, detail=""):
    print(f"  {'PASS' if c else 'FAIL'}  {label}" + (f"   {detail}" if detail and not c else ""))
    if not c:
        FAILS.append(label)


print("GATE 17 — every live detector must be liftable")
print("=" * 78)

called = sorted(set(re.findall(r'=\s*(\w+_step)\(', BOT)) |
                set(re.findall(r'=\s*(detect_\w+)\(', BOT)))
chk(len(called) >= 10, "A1 the census found the scan loop's detectors", f"found {len(called)}")

unlifted = []
for fn in called:
    if fn in KNOWN_UNLIFTABLE:
        continue
    try:
        H.fn(fn)
    except Exception:
        unlifted.append(fn)
chk(not unlifted, "B1 EVERY live detector lifts out of the harness namespace",
    f"NOT LIFTABLE: {unlifted}")

# a grandfathered entry must carry a reason, not just a name
for k, v in KNOWN_UNLIFTABLE.items():
    chk(bool(v and len(str(v)) > 40), f"C:{k} grandfathered WITH a stated reason")

# the LANES registry is a separate, weaker claim — report it, do not fail on it yet
lane_fns = {v.get("fn") for v in H.LANES.values() if v.get("fn")}
no_lane = [c for c in called if c not in lane_fns and c not in KNOWN_UNLIFTABLE]
print(f"\n  NOTE (not a failure): {len(no_lane)} liftable detector(s) have no LANES entry, so")
print(f"  they cannot be driven through replay() and need a hand-rolled driver:")
for c in no_lane:
    print(f"     - {c}")
print("  ema9x90_step is in this set: registering the SYMBOL made it testable, a LANES entry")
print("  would make it replayable like the others. Tracked, not gated.")

print("=" * 78)
if FAILS:
    print(f"GATE 17 FAILED ({len(FAILS)}): " + "; ".join(FAILS)); sys.exit(1)
print("GATE 17 PASSED"); sys.exit(0)
