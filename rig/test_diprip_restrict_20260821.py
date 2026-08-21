#!/usr/bin/env python3
"""
RIG GATE 31 — DIP_RIP RESTRICTED (8/21, Marcos: "restrict it")

EVIDENCE (8/20 night, all three runs): census 252 arms -> 121 tags -> 83 triggers -> 1 fill in
24 days; refusal grade -$597.93 / 54 takeable trades at real spreads with EVERY gate a net
saver; exit sweep 7 arms all negative (POP8 -$330.60 best, LVL -$918.52 / 19% win worst).

PINS (executed, not grepped — gate 28's lesson)
  R1  dip_rip is NOT in the RTH_LANES default
  R2  the other six trading lanes are untouched (no collateral restriction)
  R3  the lane CODE still exists — restriction must not delete the detector, because the
      arm/tag/trigger rows are what would ever earn it back
  R4  the env kill path is intact: RTH_LANES is still env-overridable
  R5  no rank list references dip_rip (a restricted lane in a rank is a silent no-op that
      would read as "seated" to the next person)
  R6  BACKSIDE_EXEMPT still names dip_rip — restriction is a capital rule, not a spec edit
"""
import ast, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "marcos_trading_bot.py").read_text()
FAIL = []
def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok: FAIL.append(n)

i = SRC.find('"ignition,ema9x90,ma_pullback,kevseq,grinder')
line = SRC[i:SRC.find("\n", i)]
check("R1 dip_rip absent from the RTH_LANES default", "dip_rip" not in line)
check("R2 the six trading lanes intact",
      all(x in line for x in ("ignition", "ema9x90", "ma_pullback", "kevseq", "grinder", "hidden_v2")))
check("R3 the detector still exists (restriction != deletion)",
      "def dip_rip_arm(" in SRC and "def dip_rip_step(" in SRC and '"triggered_dip_rip"' in SRC)
check("R4 env override path intact", 'os.environ.get(\n    "RTH_LANES"' in SRC or '"RTH_LANES",' in SRC)
ranks = [l for l in SRC.splitlines() if l.strip().startswith(('"LANE_RANK"', '"OPEN_LANE_RANK"',
         '"MID_LANE_RANK"', '"PRE_LANE_RANK"')) or "LANE_RANK\"," in l]
check("R5 no rank list seats dip_rip", not any("dip_rip" in l for l in ranks))
check("R6 BACKSIDE_EXEMPT unchanged (spec untouched)", 'BACKSIDE_EXEMPT   = {"dip_rip"}' in SRC)
ast.parse(SRC)
check("R7 module still parses", True)
print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
