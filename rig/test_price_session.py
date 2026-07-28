"""Rig: P0 fix A — session-aware price (7/28 morning ship, Fable-amended).

Marcos found it on the live dashboard: premarket prices were yesterday's closes (DFNS 13.10 vs a
real 16.02). Fix A serves the RAW premarket field premarket, or NO PRICE — never the stale close.
The trap this rig exists to pin: the legacy `pre_market_price` output DEFAULTS to yesterday's
close when the payload has no real field — a fix reading it would pass tests and stay stale live.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

bot = load_bot()
fails = []

def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)

# quote dicts as the parser emits them
LIVE_PM   = {"last_price": 13.10, "pre_market_price": 16.02, "pre_market_price_raw": 16.02}
NO_PM     = {"last_price": 13.10, "pre_market_price": 13.10, "pre_market_price_raw": None}
RTH_Q     = {"last_price": 16.44, "pre_market_price": 16.02, "pre_market_price_raw": 16.02}

print("== the DFNS case (yesterday's real numbers) ==")
check("premarket + live field -> serves 16.02 (NOT the 13.10 close)",
      bot._session_price(LIVE_PM, hm="06:45") == 16.02)
check("premarket + NO real field -> NO PRICE (0), never yesterday's close  <- THE TRAP",
      bot._session_price(NO_PM, hm="06:45") == 0.0,
      f"got {bot._session_price(NO_PM, hm='06:45')}")
check("legacy pre_market_price field would have lied (defaults to close) — raw field does not",
      NO_PM["pre_market_price"] == 13.10 and NO_PM["pre_market_price_raw"] is None)

print("== RTH is byte-identical ==")
check("09:30 exactly -> last_price", bot._session_price(RTH_Q, hm="09:30") == 16.44)
check("mid-session -> last_price", bot._session_price(RTH_Q, hm="13:00") == 16.44)
check("RTH ignores the premarket field entirely",
      bot._session_price({"last_price": 5.0, "pre_market_price_raw": 99.0}, hm="11:00") == 5.0)

print("== boundaries + degenerates ==")
check("09:29 is premarket", bot._session_price(LIVE_PM, hm="09:29") == 16.02)
check("04:00 is premarket", bot._session_price(LIVE_PM, hm="04:00") == 16.02)
check("raw field 0 -> no price", bot._session_price({"last_price": 2.0, "pre_market_price_raw": 0}, hm="05:00") == 0.0)
check("raw field negative -> no price", bot._session_price({"last_price": 2.0, "pre_market_price_raw": -1}, hm="05:00") == 0.0)
check("empty quote -> 0 everywhere", bot._session_price({}, hm="05:00") == 0.0 and bot._session_price({}, hm="12:00") == 0.0)

print("== kill switch ==")
_sv = bot.PRICE_SESSION_AWARE
bot.PRICE_SESSION_AWARE = False
check("PRICE_SESSION_AWARE=0 -> legacy last_price even premarket",
      bot._session_price(LIVE_PM, hm="06:45") == 13.10)
bot.PRICE_SESSION_AWARE = _sv

print("== wiring ==")
src = pathlib.Path(bot.__file__).read_text()
check("_get_price_rest serves _session_price", "px = _session_price(q)" in src)
check("substitution canary present", "SESSION PRICE" in src)
check("premarket payload logger present (fix-B evidence)", "PM-PAYLOAD" in src)
check("raw-field extraction guards absent/zero/garbage", "_raw_pre = None" in src)
i_reg = src.find('_price_registry[t] = {"p": px, "t": time.time()}')
i_srv = src.find("px = _session_price(q)")
check("registry write-back receives the SESSION price (lens inherits the fix)", 0 < i_srv < i_reg)

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — fix A: premarket serves live-or-nothing, RTH untouched, trap pinned, lens inherits")
