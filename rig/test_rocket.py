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

# ── PATH-1 decouple pin (#67): reclaim bars no longer gated on tick-VWAP sanity ──
check("T15 entry_vel5 instrumentation (LOG-ONLY, no gate)",
      '"entry_vel5"' in SRC and 'b[4]["entry_vel5"]' in SRC
      and "vel5>=0 floor" in SRC and "NOT" in SRC)   # candidate rule documented, not enforced

check("T16 vel5 floor: hard gate on legacy machines, curl-machines exempt, fails open on None",
      "vel5_reject" in SRC and '"ignition", "flat_top", "ma_pullback", "orb", "ema_bounce"' in SRC
      and "_v5 is not None and _v5 < 0" in SRC)

check("T17 read-staleness: OBSERVE-ONLY (hard skip REFUTED by 7/20 killtest: would block ZYBT/BIYA winners)",
      "read_exhausted_observed" in SRC and 'return ("skip", "read_exhausted"' not in SRC
      and "_chart_break_gate(ticker, entry_price, entry_type)" in SRC)

check("T18 wick-aware dip (#73): helper exists + wired at BOTH parallel sites (flat-top + ORB)",
      "_recent_low_dip" in SRC and SRC.count("_recent_low_dip(cache[t]") == 2)

check("T19 day-gain floor config: T=30 default, legacy-machine scope exact, env kill-switch",
      bot.DAYGAIN_FLOOR_PCT == 30.0
      and bot.DAYGAIN_LEGACY == ("ignition", "flat_top", "ma_pullback", "orb", "ema_bounce")
      and 'os.environ.get("DAYGAIN_FLOOR"' in SRC and "if DAYGAIN_FLOOR_PCT > 0:" in SRC)
check("T19b floor wired: reject row + threshold compare + KEV-SHEET exemption call",
      "daygain_reject" in SRC and "_dg < DAYGAIN_FLOOR_PCT" in SRC
      and "not _kev_sheet_name(b[0])" in SRC)
check("T19c exemptions structural: curl lanes NOT in the legacy scope",
      "rocket_catcher" not in bot.DAYGAIN_LEGACY and "vwap_reclaim" not in bot.DAYGAIN_LEGACY
      and "zone_flip" not in bot.DAYGAIN_LEGACY and "bounce" not in bot.DAYGAIN_LEGACY)
check("T19d stamped on each decision: candidate extra + chart-gate row + vel5-reject row + trade record",
      '"day_gain"' in SRC and SRC.count('day_gain=b[4].get("day_gain")') >= 1
      and 'day_gain=extra.get("day_gain")' in SRC and '"day_gain_at_entry"' in SRC
      and '"prior_day_close"' in SRC)
check("T19e sheet-exemption helper: vision reads NOT exempt, fail-closed",
      'lv.get("src") or "") != "vision"' in SRC and "def _kev_sheet_name" in SRC)

check("T20 #81 amnesia fix: session_cache param + setdefault preserve + main-loop wiring",
      "session_cache: dict = None" in SRC and "cache = session_cache" in SRC
      and 'cache.setdefault(t, {"bars": [], "vwap": 0.0, "fetched": 0.0})' in SRC
      and "session_cache=_session_cache" in SRC and "_session_cache = {}" in SRC)
check("T20b #81 rescan rate budget (240s) + empty-rescan session-end guard",
      "_last_full_scan[0] < 240" in SRC and "keeping prior candidate roster" in SRC)
SSRC = (pathlib.Path(__file__).resolve().parent.parent / "screener_app.py").read_text()
check("T20c whitelist-strip class killer: record_trade passes unknown fields through",
      "trade.setdefault(_k, _v)" in SSRC and "WHITELIST-STRIP CLASS KILLER" in SSRC)

check("T14 path-1: reclaim VWAP degrades gracefully (tick if sane else bar), not a kill-switch",
      "_sv = _tickv if (_tickv and _tick_vwap_ok(_tickv, vwap, price)) else vwap" in SRC
      and "if _sv and _tick_vwap_ok(_sv, vwap, price):\n                    _day_k" not in SRC)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("RED:", ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
