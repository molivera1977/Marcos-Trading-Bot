"""FAST-LANE GATE FIXES rig (7/26, Marcos: "ship all 4 and make sure they are live").
Pins the four ships from the fast-lane contradiction review:
  1. session-keyed curl slots (premarket practice can't spend RTH tickets)
  2. universal gates ON (topping tail + liquidity) w/ ignition liquidity carve-out
  3. ignition exempt from the vel5 floor (10s fire vs 1-min velocity mismatch)
  4. curl lanes exempt from the extension guard (fire AT the anchor)"""
import sys, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
bot = load_bot()
SRC = (pathlib.Path(__file__).resolve().parent.parent / "marcos_trading_bot.py").read_text()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

# ── 1. session-keyed slots: FUNCTIONAL on the real function ──
bot._curl_rth_n.clear()
_floor = bot.ENTRY_OPEN_ET
bot.ENTRY_OPEN_ET = "04:00"                       # mirror the Railway env (premarket paper floor)
check("S1 premarket fire consumes a PRE ticket", bot._curl_rth_slot("AAA", "zf", "05:00") is True)
check("S2 the SAME name's RTH fire still converts (the 7/26 fix — was False before)",
      bot._curl_rth_slot("AAA", "zf", "09:45") is True)
check("S3 second RTH fire same name/lane blocked (once per session preserved)",
      bot._curl_rth_slot("AAA", "zf", "10:15") is False)
check("S4 second PRE fire same name/lane blocked", bot._curl_rth_slot("AAA", "zf", "05:30") is False)
check("S5 other lane unaffected", bot._curl_rth_slot("AAA", "vr", "09:50") is True)
check("S6 pre-floor fires never consume", bot._curl_rth_slot("BBB", "zf", "03:59") is False
      and bot._curl_rth_slot("BBB", "zf", "09:31") is True)
bot.ENTRY_OPEN_ET = _floor; bot._curl_rth_n.clear()

# ── 2. universal gates ON + carve-out ──
check("U1 both universal-gate flags ON by default (env kill-switches)",
      bot.ENTRY_GATE_TOPPING_TAIL is True and bot.ENTRY_GATE_LIQUIDITY is True
      and 'os.environ.get("ENTRY_GATE_TOPPING_TAIL", "1")' in SRC
      and 'os.environ.get("ENTRY_GATE_LIQUIDITY", "1")' in SRC)
check("U2 ignition carve-out on the LIQUIDITY window only (quiet base = its design)",
      'ENTRY_GATE_LIQUIDITY and entry_type != "ignition"' in SRC)
check("U3 topping-tail has NO ignition carve-out (applies to all)",
      'ENTRY_GATE_TOPPING_TAIL and len(_gb) >= 2' in SRC)

# ── 3. vel5: ignition exempt ──
check("V1 vel5 legacy tuple excludes ignition (slow lanes stay gated — VINDICATED cohort 0.41R)",
      '("flat_top", "ma_pullback", "orb", "ema_bounce")' in SRC)
check("V2 daygain scope UNCHANGED — ignition still day-gain-floored (separate ruling, data-collection)",
      "ignition" in bot.DAYGAIN_LEGACY)

# ── 4. extension guard: curls exempt ──
check("X1 extension exempt tuple includes vwap_reclaim + zone_flip",
      '"vwap_reclaim", "zone_flip"' in SRC.split("catches extension by design")[0][-400:])
check("X2 ignition is now the ONLY lane the extension guard gates",
      '"ignition"' not in SRC.split("EXTENSION_MAX_PCT and EXTENSION_MAX_PCT < 9")[1][:900])

print(f"\n{'GREEN' if not FAIL else 'RED'} — {len(PASS)} pass / {len(FAIL)} fail")
sys.exit(1 if FAIL else 0)
