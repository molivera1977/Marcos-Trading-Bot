"""7/24 CURL CONVERT-AT-DETECTION rig (Marcos: "we see it triggered but now do nothing!!" /
"Get this fucker up and running the way it was SUPPOSED to be").
Reproduces today's failure classes: (A) fires dropped by the 3-min warmup continue before the
trade branch ran (26 RTH fires, 0 conversions), (B) premarket seed fires burning the daily live
slot. FUNCTIONAL on the real _curl_rth_slot + POSITIONAL source pins on the conversion block."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
ROOT = pathlib.Path(__file__).resolve().parent.parent
from loader import load_bot
bot = load_bot()
BOT = (ROOT / "marcos_trading_bot.py").read_text()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

# ═══ FUNCTIONAL: the RTH slot rule (fix for failure B) ════════════════════════
bot._curl_rth_n.clear()
check("S1 pre-ENTRY_OPEN fire never gets the slot (default 09:30)", bot.ENTRY_OPEN_ET == "09:30" and bot._curl_rth_slot("ADVB", "vr", "08:15") is False)
check("S2 premarket fire did NOT burn it (the #98-seed bug, dead)",
      bot._curl_rth_slot("ADVB", "vr", "09:32") is True)
check("S3 second RTH conversion refused (one live per lane per day)",
      bot._curl_rth_slot("ADVB", "vr", "09:40") is False)
check("S4 lanes independent (zf slot untouched by vr)",
      bot._curl_rth_slot("ADVB", "zf", "09:41") is True)
check("S5 symbols independent", bot._curl_rth_slot("PN", "vr", "09:59") is True)
check("S6 exactly 09:30 is RTH", bot._curl_rth_slot("JEM", "vr", "09:30") is True)
# 7/25 premarket-paper: with ENTRY_OPEN_ET=04:00 the slot opens premarket
bot.ENTRY_OPEN_ET = "04:00"
check("S7 ENTRY_OPEN_ET=04:00 -> premarket fire converts", bot._curl_rth_slot("PMKT", "vr", "07:15") is True)
check("S8 ...and pre-4:00 still never", bot._curl_rth_slot("PMKT2", "vr", "03:59") is False)
bot.ENTRY_OPEN_ET = "09:30"
bot._curl_rth_n.clear()

# ═══ POSITIONAL PINS: conversion sits ABOVE every legacy guard (fix for failure A) ═══
i_conv  = BOT.index("CONVERT-AT-DETECTION")
i_nodata = BOT.index('status_parts.append(f"{t}:no data")')
i_warm  = BOT.index("need more 3-min bars")
check("P1 conversion block ABOVE the no-data guard", i_conv < i_nodata)
check("P2 conversion block ABOVE the 3-min warmup guard (today's killer)", i_conv < i_warm)
check("P3 zone-flip queues a real entry at detection",
      '"reclaim_subtype": "zone_flip"' in BOT[i_conv:i_conv+6000]
      and 'breakouts.append((t, price, zf["zone"], "zone_flip"' in BOT[i_conv:i_conv+6000])
check("P4 reclaim queues a real entry at detection, in its 09:30-11:00 window",
      'RECLAIM_LIVE_START <= _hm_curl < RECLAIM_LIVE_END' in BOT[i_conv:i_conv+7000]
      and 'breakouts.append((t, price, _sv, "vwap_reclaim"' in BOT[i_conv:i_conv+7000])
check("P5 conversion consumes the slot ONLY when queueing (call sites inside conversion)",
      BOT.count("_curl_rth_slot(t,") == 2)
check("P6 old seq==0 consume logic is GONE (no double-trade path)",
      'if zf.get("seq", 0) == 0:' not in BOT
      and 'vr.get("seq", 0) == 0 and RECLAIM_LIVE_START' not in BOT)
check("P7 captured fire skips other detectors (ignition-capture pattern; window widened 7/26 for the premarket-reclaim comment block)",
      BOT[i_conv:i_conv+7000].count("continue                                   # captured") == 2)

# ═══ SAFETY PINS: nothing else regressed ══════════════════════════════════════
check("G1 chart-gate exemption for curl tags unchanged (7/24: + hidden_entry)",
      '_STALE_EXEMPT = ("rocket_catcher", "vwap_reclaim", "zone_flip", "hidden_entry")' in BOT)
check("G2 detection still shadow-logs every fire (evidence never lost)",
      BOT.count('_shadow_log_curl_leftovers(t, price, _zf_fire, None, 0.0, "detected")') == 1
      and BOT.count('_shadow_log_curl_leftovers(t, price, None, _vr_fire, _vr_sv, "detected")') == 1)
check("G3 detection itself still unconditional (above conversion)",
      BOT.index("CURL DETECTORS ALWAYS STEP") < i_conv)
check("G4 breakout whitelist still admits both curl tags",
      '"ma_pullback", "vwap_reclaim", "ignition", "zone_flip", "rocket_catcher"' in BOT)

print(f"\n{'='*60}\nCURL CONVERT-AT-DETECTION RIG: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", *FAIL, sep="\n  ")
sys.exit(1 if FAIL else 0)
