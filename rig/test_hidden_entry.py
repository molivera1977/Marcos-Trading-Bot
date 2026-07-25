"""HIDDEN ENTRY rig (7/24 night, Marcos: "I want winners"). Kev's 10s rocket playbook,
expert fidelity-audited (k27fptelI8Y + XFSPUI5YJsE + 3UboKEl7-Oc). FUNCTIONAL tests on the
real hidden_entry_step machine + POSITIONAL pins on every wiring touchpoint."""
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

B = lambda o,h,l,c,v=1000: (o,h,l,c,v)
VWAP = 2.00

# ── M1: machine arms on +25%/5min then fires on the Kev wick ──
bot._he_st.clear()
flat = [B(2.5,2.52,2.48,2.50)]*31                       # 31 flat bars: no arm
r = bot.hidden_entry_step("AAA", flat, VWAP)
check("M1 no arm on flat tape", r is None and not bot._he_st["AAA"]["armed"])
rocket = [B(2.5+i*0.045, 2.56+i*0.045, 2.46+i*0.045, 2.55+i*0.045) for i in range(31)]  # +~55%/31 bars
r = bot.hidden_entry_step("BBB", rocket, VWAP)
check("M2 arms on velocity", bot._he_st["BBB"]["armed"] and r is None)     # no wick at anchor yet
# wick: e90 lags ~ well below price; drop a bar whose low tags anchor and closes top-half above vwap
e90 = bot._he_st["BBB"]["e90"]; anchor = max(e90, VWAP)
wick = B(anchor*1.02, anchor*1.10, anchor*0.995, anchor*1.09)               # low tags, closes high
r = bot.hidden_entry_step("BBB", [wick], VWAP)
check("M3 fires on wick at anchor from above", r is not None)
check("M4 stop = wick low floored 5%", r and abs(r["stop"] - round(min(wick[2]-0.01, wick[3]*0.95), 4)) < 1e-3)
check("M5 ext_vwap stamped", r and isinstance(r["ext_vwap"], float))
check("M8 stays armed post-fire (Kev re-enters)", bot._he_st["BBB"]["armed"] is True)

# ── M6: refuses fire when close is BELOW VWAP (box #1 — fader knife) ──
bot._he_st.clear()
bot.hidden_entry_step("CCC", rocket, VWAP)
e90c = bot._he_st["CCC"]["e90"]
under = B(e90c*0.99, e90c*1.001, e90c*0.97, e90c*1.0005)                    # tags anchor but close < vwap
r = bot.hidden_entry_step("CCC", [under], vwap=e90c*1.5)                    # vwap far above close
check("M6 refuses below-VWAP fire (box #1)", r is None)

# ── M7: refuses a topping bar (close bottom-half = no bottoming wick) ──
bot._he_st.clear()
bot.hidden_entry_step("DDD", rocket, VWAP)
e90d = bot._he_st["DDD"]["e90"]; anc = max(e90d, VWAP)
top = B(anc*1.12, anc*1.14, anc*0.999, anc*1.02)                            # closes in bottom half
r = bot.hidden_entry_step("DDD", [top], VWAP)
check("M7 refuses non-wick bar", r is None)


# ── W: wiring pins (positional source checks) ──
check("W1 ROCKET_CATCHER default OFF (superseded)", 'os.environ.get("ROCKET_CATCHER", "0")' in BOT)
check("W2 HIDDEN_ENTRY default ON", bot.HIDDEN_ENTRY is True and 'os.environ.get("HIDDEN_ENTRY", "1")' in BOT)
check("W3 chart-gate bypass (hidden)", bot._chart_break_gate("ZZZZ", 9.99, "hidden_entry")[0] == "allow")
check("W3b bypass extends to reclaim (Marcos 7/24)", bot._chart_break_gate("ZZZZ", 9.99, "vwap_reclaim")[0] == "allow")
check("W3c bypass extends to zone_flip", bot._chart_break_gate("ZZZZ", 9.99, "zone_flip")[0] == "allow")
check("W3d legacy flat_top STILL gated on no-map", bot._chart_break_gate("ZZZZ", 9.99, "flat_top")[0] == "skip")
check("W15 float cap = 30M (Marcos 7/24, OMH+margin; env-tunable)", abs(bot.BOT_MAX_FLOAT - 30_000_000) < 1 and 'BOT_MAX_FLOAT_M' in BOT)
check("W16 OMH-class (21.3M float) now bot-eligible", 21_300_000 <= bot.BOT_MAX_FLOAT)
check("W4 stale-exempt includes hidden_entry", '"zone_flip", "hidden_entry")' in BOT)
check("W5 allowed-types includes hidden_entry", '"rocket_catcher", "hidden_entry")' in BOT.split("BREAKOUT_ENTRIES or b[3] in ")[1][:120])
check("W6 extension-guard exempt", '("rocket_catcher", "hidden_entry"):\n                    _kept.append(b)' in BOT)
check("W7 monitor ladder covers hidden_entry", 'entry_type in ("rocket_catcher", "hidden_entry"):   # ROCKET scale-out ladder' in BOT)
check("W8 momentum reversal exemption", '("vwap_reclaim", "bounce", "ignition", "hidden_entry")' in BOT)
check("W9 conversion branch exists + capped", 'triggered_hidden_entry' in BOT and 'hidden_capped' in BOT)
check("W10 detection evidence logged", 'hidden_shadow_fire' in BOT)
check("W11 conversion floored at ENTRY_OPEN_ET", "_he_fire and HIDDEN_ENTRY and _hm_curl >= ENTRY_OPEN_ET" in BOT)
check("W17 premarket profile: PRE_LANES = 10s live-structure only", bot.PRE_LANES == {"hidden_entry", "vwap_reclaim"})
check("W18 premarket cap 4 + $250k dvol floor (7/25 calibration)", bot.PRE_MAX_TRADES == 4 and abs(bot.PRE_MIN_DVOL - 250000) < 1)
check("W19 premkt gate v2 reasons", "lane_not_premkt" in BOT and "premkt_capped" in BOT and "premkt_thin" in BOT)
check("W20 entry_session stamped on records", '"entry_session":' in BOT)
check("W12 2R counterfactual stamped", 'two_r_level' in BOT)
check("W13 premarket shadow un-counts hidden", '_pe == "hidden_entry"' in BOT)
check("W14 vel5/daygain legacy lists exclude hidden (passes)", '"hidden_entry"' not in BOT.split('b[3] in ("ignition", "flat_top", "ma_pullback", "orb", "ema_bounce")')[0][-200:])

print(f"\n{'GREEN' if not FAIL else 'RED'} — {len(PASS)} pass / {len(FAIL)} fail")
sys.exit(1 if FAIL else 0)
