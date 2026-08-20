#!/usr/bin/env python3
"""
RIG GATE 27 — RUNWAY VELOCITY OVERRIDE (8/20 ~00:2x ET, Marcos: "it's all fake money....
wire the override at 1% with a kill switch" + "we will log all data and revisit nightly in
our lane reviews")

EVIDENCE (in-session 8/19->20): LGHL specimen (refused 0.18R to a stale $0.65 rung, tape ran
+31%, +$47.35 given up); ladder on all 56 cached archived runway refusals — let-go at
fire-minute >= +1% = +$7.55/tr 59% green, kept complement -$9.55/tr, negative-minute cohort
-$15.76/tr at 14% green. Threshold +1% pre-registered BEFORE the fine ladder; plateau
0.75-1.5% confirmed it. n=56: shipped early by owner ruling (DRY_RUN), nightly lane reviews
accumulate the verdict cohort — BOTH rows (override + reject) stamp vel60 for that grading.

PINS
  R1  env pair exists: RUNWAY_VEL_OVERRIDE default ON, RUNWAY_VEL_OVERRIDE_PCT default 1.0
  R2  the override runs ONLY when the runway verdict was sub-threshold (never widens a pass)
  R3  missing/short feed -> NO override (the exception needs positive evidence)
  R4  velocity definition = 7th-last to last COMPLETED 10s bucket (the ladder's definition:
      close-over-close across 60s, forming bucket excluded)
  R5  override logs its own row (runway_override) with vel60 + the full runway ticket
  R6  the runway_reject row now stamps vel60 too (nightly grading needs both sides)
  R7  the reject body is gated on `not _rw_ovr` — an override cannot half-refuse (no slot
      refund / return on the override path)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "marcos_trading_bot.py").read_text()
FAIL = []


def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok:
        FAIL.append(n)


check("R1 env pair, defaults ON / 1.0",
      'RUNWAY_VEL_OVERRIDE     = os.environ.get("RUNWAY_VEL_OVERRIDE", "1") == "1"' in SRC
      and 'RUNWAY_VEL_OVERRIDE_PCT = float(os.environ.get("RUNWAY_VEL_OVERRIDE_PCT", "1.0"))' in SRC)

i = SRC.find("_rw_ovr, _rw_vel60 = False, None")
blk = SRC[i:i + 2600] if i != -1 else ""
check("R2 override only evaluates on a sub-threshold runway verdict",
      "if (RUNWAY_VEL_OVERRIDE and isinstance(_rw_v, (int, float))\n"
      "                        and _rw_v < _rw_need):" in blk)
check("R3 short/missing feed cannot override (>=7 completed buckets required)",
      "if len(_vk) >= 7:" in blk and "_rw_vel60 = None" in blk
      and "_rw_vel60 is not None and _rw_vel60 >= RUNWAY_VEL_OVERRIDE_PCT" in blk)
check("R4 velocity = completed buckets only, 60s close-over-close",
      "k < int(time.time()) // 10 * 10" in blk
      and "_vd[_vk[-7]]" in blk and "_vd[_vk[-1]]" in blk)
check("R5 override row carries vel60 + the runway ticket",
      '"runway_override"' in blk and "vel60=_rw_vel60" in blk
      and "runway_rr=_rw_v, target=_rw_t, need=_rw_need" in blk)
# window scan, not paren-hunting — gate 23's twice-bitten lesson (inner `round(...)` parens
# break any [^)]* pattern; a pin that lies is worse than no pin)
_j = SRC.find('_log_decision(ticker, "runway_reject"')
check("R6 runway_reject stamps vel60 for the nightly grading",
      _j != -1 and "vel60=_rw_vel60" in SRC[_j:_j + 500])
check("R7 reject body gated on `not _rw_ovr`",
      "if isinstance(_rw_v, (int, float)) and _rw_v < _rw_need and not _rw_ovr:" in SRC)

print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
