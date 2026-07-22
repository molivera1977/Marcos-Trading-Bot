"""Rocket-catcher tests (Fable-approved). Detector (velocity>=T=25%/5min) + full wiring touchpoint pins.
Integrator discipline: pins prove EVERY site is wired AND this test actually runs (single sys.exit)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
bot = load_bot()
SRC = (pathlib.Path(__file__).resolve().parent.parent / "marcos_trading_bot.py").read_text()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + (f" — {d}" if d and not cond else ""))
def bars(closes, lows=None):
    lows = lows or [c * 0.99 for c in closes]
    return [{"close": c, "low": l, "open": c, "high": c * 1.01, "volume": 1000} for c, l in zip(closes, lows)]

# ── ships DISABLED by default (safe until 6-tape replay); rig enables to exercise the detector ──
check("T0 ACTIVE by default in DRY_RUN (Fable shadow verdict 7/21; env ROCKET_CATCHER=0 is the kill-switch)", bot.ROCKET_CATCHER is True)

# ── detector ──
r = bot.detect_rocket(bars([1.00, 1.00, 1.05, 1.12, 1.22, 1.30]), 1.30)
check("T1 fires on +30%/5-bar velocity", r is not None and r["vel"] >= 25, f"got {r}")
check("T2 silent on flat tape", bot.detect_rocket(bars([1.0] * 6), 1.0) is None)
check("T3 silent at +20% (below T=25)", bot.detect_rocket(bars([1.00, 1.00, 1.05, 1.10, 1.15, 1.20]), 1.20) is None)
r4 = bot.detect_rocket(bars([1.00, 1.00, 1.05, 1.12, 1.22, 1.30], [0.5] * 6), 1.30)
check("T4 stop bounds risk <=25%", r4 and r4["stop"] >= 1.30 * 0.75 - 1e-9, f"got {r4}")
check("T5 config T=25 / cap 3 / 5 bars", bot.ROCKET_VEL_PCT == 25 and bot.ROCKET_DAILY_CAP == 3 and bot.ROCKET_VEL_BARS == 5)
check("T6 kill-switch ROCKET_CATCHER exists", hasattr(bot, "ROCKET_CATCHER"))
check("T7 too-few-bars -> None", bot.detect_rocket(bars([1.0, 1.3]), 1.3) is None)

# ── wiring touchpoints (Integrator: every site the machine must hit) ──
check("T8 touchpoint: entry allowlist has rocket_catcher", '"zone_flip", "rocket_catcher"' in SRC)
check("T9 touchpoint: EXEMPT from extension guard", 'b[3] == "rocket_catcher"' in SRC and "catches extension by design" in SRC)
check("T10 touchpoint: KEV-SPEC 3-phase entry wired (arm/touch/curl)",
      "rocket_armed" in SRC and "rocket_touched" in SRC and "rocket_plow" in SRC
      and "triggered_rocket" in SRC and "detect_rocket(_rs1" in SRC)
check("T10b curl condition + pullback-low stop present",
      "_cl > _bar_high(_pb)" in SRC and 'cache[t].get("rocket_plow")' in SRC)
check("T11 touchpoint: monitor_trade %-tier branch", 'entry_type="flat_top")' in SRC and 'entry_type == "rocket_catcher"' in SRC and "entry_price * 1.50" in SRC and "entry_price * 2.00" in SRC)
check("T12 touchpoint: call site threads entry_type", "entry_type=entry_type," in SRC)
check("T13 touchpoint: daily cap + reset wired", "_rocket_day" in SRC and "rocket_capped" in SRC)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("RED:", ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
