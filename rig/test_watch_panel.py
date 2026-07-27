"""#101 live watch-panel rig (Marcos 7/24: "I want the panel to constantly be updated —
that is what I can watch when away from my laptop"). FUNCTIONAL: real _post_watching_to_screener
posts the roster; SOURCE PINS: the watch loop re-posts on roster change + 120s heartbeat, and the
dashboard handler's replace-snapshot/union-history semantics (safe to repeat) are unchanged."""
import sys, os, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
ROOT = pathlib.Path(__file__).resolve().parent.parent
from loader import load_bot
bot = load_bot()
BOT = (ROOT / "marcos_trading_bot.py").read_text()
DASH = (ROOT / "screener_app.py").read_text()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

# ═══ FUNCTIONAL: the poster sends the roster ══════════════════════════════════
os.environ["SCREENER_URL"] = "http://fake-dash"
_captured = {}
def _fake_post(url, json=None, headers=None, timeout=None):
    _captured["url"] = url; _captured["payload"] = json
    class R: status_code = 200
    return R()
_orig = bot.requests.post
try:
    bot.requests.post = _fake_post
    bot._post_watching_to_screener(["LVWR", "CJMB", "PN"], quiet=True)
    check("F1 posts to /api/watching", _captured.get("url", "").endswith("/api/watching"))
    check("F2 payload carries the full roster", _captured.get("payload", {}).get("tickers") == ["LVWR", "CJMB", "PN"])
    check("F3 status defaults to watching", _captured.get("payload", {}).get("status") == "watching")
finally:
    bot.requests.post = _orig

# ═══ SOURCE PINS: loop wiring ═════════════════════════════════════════════════
_loop = BOT[BOT.index("_wl_posted: set = set()"):]
check("P1 heartbeat block INSIDE the watch loop, before the bar refresh",
      "while True:" in _loop.split("# Refresh bars")[0]
      and "_wl_now = set(candidates)" in _loop.split("# Refresh bars")[0])
check("P2 re-posts on roster CHANGE or 120s heartbeat",
      "_wl_now != _wl_posted or time.time() - _wl_posted_ts >= 120" in BOT)
check("P3 posts the CURRENT roster, sorted + quiet",
      "_post_watching_to_screener(sorted(_wl_now), quiet=True)" in BOT)
check("P4 boot-time full post unchanged (session start still announces)",
      "_post_watching_to_screener(gapper_syms)" in BOT)

# ═══ DASHBOARD SEMANTICS (why repeating is safe — must not regress) ═══════════
check("D1 POST replaces only the live snapshot (roster semantics)", "_watching = {" in DASH)
check("D2 history is a UNION across the session — repeats can never shrink it (7/26: insertion-ordered, append-only)",
      "if u and u not in _seen:" in DASH and "_seen.add(u); _prev.append(u)" in DASH
      and "_watch_hist[_today] = _prev" in DASH)
check("D2b union is FIRST-SEEN ordered, not alphabetical (7/26 F2: alphabet no longer decides cap-150 evictions)",
      "FIRST-SEEN ORDER" in DASH and "sorted(prev | {str(t).upper().strip()" not in DASH)


# ── 7/26 dashboard display fixes (review #9) ──
check("V1 P&L correction merges AT RENDER (store untouched): loader + _cpnl + corrected serve",
      "_PNL_CORR" in DASH and "def _cpnl(t):" in DASH and '"pnl_corrected"' in DASH
      and "pnl_runner_leg_correction_20260726.json" in DASH)
check("V2 premarket exit story ABOVE the eod matcher (9:25 flatten no longer narrates as end-of-day)",
      DASH.index("/premarket time stop/i") < DASH.index("/eod|close|time/i"))
check("V3 strategy card = current truth (retired gates named, hidden entry + PRE regime + floor 15 present)",
      "Retired 7/26" in DASH and "hidden entry" in DASH and "Day-gain floor" in DASH
      and "Momentum: HARD gate" not in DASH and "ROCKET CATCHER (vel" not in DASH)
check("V4 BOT badge mirrors 30M + float-N/A-kept (both sites)",
      DASH.count("(r.float_shares<=0)||(r.float_shares<30000000)") == 2
      and "float_shares<20000000" not in DASH)
check("V5 day2 filters ZZ* sentinels from the observations table",
      "startsWith('ZZ')" in DASH)
check("V6 premarket board shows REAL PRE conversions + PRE ledger + health line",
      '"_converted"' in DASH and "CONVERTED — real PRE trade" in DASH
      and "Premarket trades <span>— the PRE ledger" in DASH and "ZZREADERBEAT" in DASH
      and "PREMARKET REGIME LIVE" in DASH)

print(f"\n{'='*60}\n#101 WATCH-PANEL RIG: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", *FAIL, sep="\n  ")
sys.exit(1 if FAIL else 0)
