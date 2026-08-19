#!/usr/bin/env python3
"""
RIG GATE 22 — "PULLBACK SHOULD BE ITS OWN GATE" (Marcos ruling, 8/19 ~13:0x)

ma_pullback v2 is a three-beat sequence whose grammar already answers the downstream questions
(above VWAP, <=2% depth, quiet dip, flag stop, INTERNAL runway >=0.5R — measured as a unit on the
19-date hold-out). The specimens: v2 fired 3 since shipping, converted 0 — AZI refused
"no_break_below_level" (a continuation entry can never show a fresh break), RCON blocked mapless,
TNON runway_reject at 0.09R off a 20.6% flag stop. This gate pins the two authorized grants and
their reversibility:

  F1 MAPB_PATTERN_GATE=1 (default): ma_pullback IS in the chart-bypass set
  F2 kill switch: MAPB_PATTERN_GATE=0 removes it (both external gates restored)
  F3 the external runway pass is conditioned on NOT (pattern-gate AND ma_pullback)
  F4 the INTERNAL runway requirement (MAPB_REQUIRE_RUNWAY) is untouched and still consulted
     in the detector — the lane is NOT runway-free, it is runway-self-governed
  F5 legacy fallback intact: LANE_REGISTRY_EXEMPT=0 returns the pre-8/17 literal
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
os.environ.setdefault("DRY_RUN", "true")
from loader import load_bot
bot = load_bot()
SRC = pathlib.Path(bot.__file__).read_text()
FAIL = []


def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok:
        FAIL.append(n)


bot.LANE_REGISTRY_EXEMPT = True
bot.MAPB_PATTERN_GATE = True
check("F1 pattern-gate ON: ma_pullback bypasses the chart gate",
      "ma_pullback" in bot._chart_bypass_lanes())
bot.MAPB_PATTERN_GATE = False
check("F2 kill switch: ma_pullback back under the chart gate",
      "ma_pullback" not in bot._chart_bypass_lanes())
bot.MAPB_PATTERN_GATE = True

check("F3 external runway pass skips the lane (source pin)",
      'MIN_RUNWAY_RR > 0 and not (MAPB_PATTERN_GATE and entry_type == "ma_pullback")' in SRC)
check("F4 internal runway UNTOUCHED: MAPB_REQUIRE_RUNWAY still gates the fire",
      "MAPB_REQUIRE_RUNWAY" in SRC and bot.MAPB_REQUIRE_RUNWAY is True
      and "no_runway" in SRC)
bot.LANE_REGISTRY_EXEMPT = False
check("F5 legacy fallback: registry off -> pre-8/17 literal (no ma_pullback)",
      "ma_pullback" not in bot._chart_bypass_lanes())
bot.LANE_REGISTRY_EXEMPT = True

print("=" * 70)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
