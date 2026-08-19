#!/usr/bin/env python3
"""
GATE 14 — PREMARKET IGNITION + THE 9/90 WARM-UP (8/18)

Marcos: "fine, ignition for both pre and RTH, have 9/90 running in pre but not trade until 9:30"

WHAT IS PINNED (all failures hard)
  A. IGNITION PREMARKET
     A1 kill switch IGNITION_PRE exists and defaults ON
     A2 the window is 07:00-09:25 by minute-of-day (420/565), matching the MEASURED arm:
        07:00 +$10.58/tr green 58% PASSES | 08:00 -$10.22/tr green 12% FAILS
     A3 the old unconditional `if m < 570` skip is GONE (it produced zero premarket fires on
        551 name-days) and the premarket branch is gated by IGNITION_PRE
     A4 the coverage floor exists and is applied on premarket bars only. The edge is entirely
        in dense tape: >=50% +$14.52/tr green 59% | <50% -$8.56/tr
     A5 the coverage ratio counts elapsed minutes INCLUSIVELY (+1). Without it the ratio
        exceeded 100% early (measured median 101%) and the floor was vacuous — caught by
        exercising the detector, not by reading it.
     A6 premarket uses its OWN open anchor; the RTH open is untouched

  B. THE 9/90
     B1 kill switch EMA9X90_WARMUP exists and defaults ON
     B2 the window is judged from the BAR's clock, never datetime.now(). Exercising the lane
        fired it 30x before 09:30 and again at 18h/19h under wall-clock — the same shape as the
        8/10 MTEN 18:59/19:59 fires the window was added to stop.
     B3 the gap-fill carries the last print through empty minutes (readiness 69% -> 93%, and
        the added fires measured BETTER: $/tr +$14.68 vs +$11.75, green 61% vs 56%)
     B4 premarket bars WARM but never fire: the EMA9X90_OPEN guard is still present
     B5 warm provenance is stamped (warm_pre / warm_src) so a cold fire is never invisible
     B6 the lane is registered in the harness namespace — it shipped 8/18 12:43 and was NOT
        liftable, so it could not be exercised or parity-measured at all
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "..", "marcos_trading_bot.py")).read()
HARN = open(os.path.join(HERE, "..", "data", "killtests", "live_harness.py")).read()
FAILS = []


def chk(ok, label, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"   {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


print("GATE 14 — premarket ignition + the 9/90 warm-up")
print("=" * 80)

m = re.search(r'IGNITION_PRE\s*=\s*os\.environ\.get\(\s*"IGNITION_PRE",\s*"(\d)"\s*\)', SRC)
chk(bool(m), "A1 IGNITION_PRE kill switch exists")
chk(bool(m) and m.group(1) == "1", "A2 IGNITION_PRE defaults ON")
o = re.search(r'IGNITION_PRE_OPEN_M\s*=\s*int\(os\.environ\.get\("IGNITION_PRE_OPEN_M",\s*"(\d+)"\)\)', SRC)
c = re.search(r'IGNITION_PRE_CLOSE_M\s*=\s*int\(os\.environ\.get\("IGNITION_PRE_CLOSE_M",\s*"(\d+)"\)\)', SRC)
chk(bool(o) and o.group(1) == "420", "A2b premarket opens 07:00 (420) — the measured arm",
    f"got {o.group(1) if o else None}")
chk(bool(c) and c.group(1) == "565", "A2c premarket closes 09:25 (565) — live PRE flatten",
    f"got {c.group(1) if c else None}")
chk("if m < 570 or c <= 0:" not in SRC, "A3 the unconditional premarket skip is GONE")
chk("if not (IGNITION_PRE and IGNITION_PRE_OPEN_M <= m < IGNITION_PRE_CLOSE_M):" in SRC,
    "A3b premarket branch is gated by IGNITION_PRE + the window")
chk("IGNITION_PRE_COVERAGE" in SRC and "st[\"pre_min\"]" in SRC,
    "A4 coverage floor exists and counts printed minutes")
chk("max(m - IGNITION_PRE_OPEN_M + 1, 1)" in SRC,
    "A5 coverage ratio counts elapsed minutes inclusively (no >100%)")
chk(SRC.count("max(m - IGNITION_PRE_OPEN_M, 1)") == 0,
    "A5b the off-by-one form is gone everywhere")
chk('st["openp_pre"]' in SRC and '_openp = st["openp_pre"] if _pre_bar else st["openp"]' in SRC,
    "A6 premarket has its own open anchor; RTH open untouched")
chk('ext_bar = (c - _openp) / _openp' in SRC,
    "A6b extension measured from the ACTIVE anchor")

w = re.search(r'EMA9X90_WARMUP\s*=\s*os\.environ\.get\(\s*"EMA9X90_WARMUP",\s*"(\d)"\s*\)', SRC)
chk(bool(w), "B1 EMA9X90_WARMUP kill switch exists")
chk(bool(w) and w.group(1) == "1", "B1b warm-up defaults ON")
chk('_hm_x9 = datetime.fromtimestamp(k, EASTERN).strftime("%H:%M")' in SRC,
    "B2 the 9/90 window is judged from the BAR clock")
chk('_hm_x9 = datetime.now(EASTERN)' not in SRC,
    "B2b wall-clock form is gone (it fired 30x pre-09:30 and at 18h/19h)")
chk('if EMA9X90_WARMUP and st["last_m"] is not None' in SRC,
    "B3 gap-fill carries the last print through empty minutes")
chk('if not (EMA9X90_OPEN <= _hm_x9 < EMA9X90_CLOSE):' in SRC,
    "B4 premarket bars WARM but never fire (the 09:30 guard stands)")
chk('"warm_pre": st["warm_pre"]' in SRC and '"warm_src"' in SRC,
    "B5 warm provenance stamped on every 9/90 fire")
chk('"ema9x90_step"' in HARN and '"_x90_st"' in HARN,
    "B6 the 9/90 is liftable by the harness (it was not, until 8/18)")

print("=" * 80)
if FAILS:
    print(f"GATE 14 FAILED ({len(FAILS)}): " + "; ".join(FAILS))
    sys.exit(1)
print("GATE 14 PASSED")
sys.exit(0)
