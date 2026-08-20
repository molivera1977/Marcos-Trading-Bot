#!/usr/bin/env python3
"""
RIG GATE 24 — ma_pullback day-gain floor 3% (Marcos ruling 8/19: "set it to 3% and we'll revisit")

The lane fired 4x since v2 shipped and converted ZERO — runway, chart gate (x2), then daygain.
Its geometry already answers "is this a leader" (above VWAP, <=2% below the session high,
front-side), which is what the 15% global floor proxies for. But geometry pins position WITHIN
the day, not the day's DIRECTION — 4 graded refusals were names DOWN on the day — so a floor
ABOVE ZERO stays rather than an exemption. 3% mirrors ignition's approved floor; it is REASONED,
NOT MEASURED (the only gradeable cohort was 26 rows, 25 of them v1-era with the no-pullback
defect). REVISIT at n>=30 v2 rows.

  F1 ma_pullback floor is 3.0, env-overridable via DAYGAIN_FLOOR_MAPB
  F2 ignition keeps its own 3.0 (unchanged)
  F3 every OTHER lane still gets the global 15.0 — no collateral loosening
  F4 the floor is still ENFORCED for the lane (ma_pullback remains in DAYGAIN_LEGACY);
     this is a lower bar, NOT an exemption — a red name still refuses
  F5 the refusal row stamps the per-lane floor it used (so a future study can tell which bar applied)
"""
import os, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
os.environ.setdefault("DRY_RUN", "true")
from loader import load_bot
bot = load_bot()
SRC = pathlib.Path(bot.__file__).read_text()
FAIL = []
def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok: FAIL.append(n)

check("F1 ma_pullback floor = 3.0 (env DAYGAIN_FLOOR_MAPB)",
      bot._daygain_floor_for("ma_pullback") == 3.0 and "DAYGAIN_FLOOR_MAPB" in SRC)
check("F2 ignition floor unchanged at 3.0", bot._daygain_floor_for("ignition") == 3.0)
check("F3 other lanes still on the global floor",
      all(bot._daygain_floor_for(l) == bot.DAYGAIN_FLOOR_PCT
          for l in ("kevseq", "grinder", "flat_top", "dip_rip", "orb", "hidden_entry")))
check("F4 LOWER BAR, NOT AN EXEMPTION — lane still gated (in DAYGAIN_LEGACY)",
      "ma_pullback" in bot.DAYGAIN_LEGACY)
check("F4b a RED name still refuses at the 3% bar", -9.6 < bot._daygain_floor_for("ma_pullback"))
m = re.search(r'"daygain_reject".{0,400}?floor=', SRC, re.S)
check("F5 refusal row stamps the per-lane floor used", bool(m))
print("=" * 66)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
