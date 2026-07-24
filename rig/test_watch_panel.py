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
check("D2 history is a UNION across the session — repeats can never shrink it",
      "prev | {str(t).upper().strip()" in DASH)

print(f"\n{'='*60}\n#101 WATCH-PANEL RIG: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", *FAIL, sep="\n  ")
sys.exit(1 if FAIL else 0)
