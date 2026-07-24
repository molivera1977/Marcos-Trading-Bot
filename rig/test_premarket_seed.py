"""#98 Premarket starter-seed rig (Marcos 7/23: 'seed top-25 yesterday's gappers + Kev, let the
feed add poppers; read list = top-20 by Move% at 8:50'). FUNCTIONAL (real _premarket_starter_set
through mocked HTTP) + Integrator source pins. Wind Tunnel: premarket seeds, RTH byte-identical.
Single sys.exit."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
ROOT = pathlib.Path(__file__).resolve().parent.parent
from loader import load_bot
bot = load_bot()
SRC = (ROOT / "marcos_trading_bot.py").read_text()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

class _Resp:
    def __init__(s, code, payload): s.status_code, s._p = code, payload
    def json(s): return s._p

# ═══ FUNCTIONAL: _premarket_starter_set ═══════════════════════════════════════
# most-recent day's gappers, ranked by change_pct DESC, top-N, Kev FIRST, dedup
_day2 = {"daily_gappers": {
    "2026-07-22": [{"symbol": "OLD", "change_pct": 999}],                       # older day — must be ignored
    "2026-07-23": [{"symbol": f"G{i}", "change_pct": float(i)} for i in range(1, 31)]  # 30 names, gain=i
}}
import os as _os
_os.environ["SCREENER_URL"] = "http://fake-dash"   # the `if url:` guard skips the fetch without this
_orig_get = bot.requests.get
try:
    bot.requests.get = lambda url, **k: _Resp(200, _day2) if "/api/day2" in url else _Resp(404, {})
    bot._fetch_kev_watchlist = lambda: ["PN", "INLF", "LABT"]
    out = bot._premarket_starter_set(25)
    check("M1 Kev-first: first 3 are Kev's names", out[:3] == ["PN", "INLF", "LABT"], f"got {out[:3]}")
    check("M1b ranked biggest→smallest: G30 before G29 before G28",
          out.index("G30") < out.index("G29") < out.index("G28"), f"got {out[3:8]}")
    check("M1c most-recent day only (no OLD from 7/22)", "OLD" not in out)
    check("M1d cap = Kev(3) + top-25 movers = 28", len(out) == 28, f"got {len(out)}")
    check("M1e smallest movers bumped (G1..G5 below the 25 cut are OUT)",
          "G5" not in out and "G30" in out, f"tail={out[-3:]}")

    # empty daily_gappers → Kev only (fail-safe)
    bot.requests.get = lambda url, **k: _Resp(200, {"daily_gappers": {}}) if "/api/day2" in url else _Resp(404, {})
    check("M2 empty gappers → Kev only", bot._premarket_starter_set(25) == ["PN", "INLF", "LABT"])

    # fetch failure → Kev only (never raises)
    def _boom(url, **k):
        raise RuntimeError("down")
    bot.requests.get = _boom
    check("M2b fetch failure → Kev only, no raise", bot._premarket_starter_set(25) == ["PN", "INLF", "LABT"])
finally:
    bot.requests.get = _orig_get

# ═══ SOURCE PINS (Integrator + Wind Tunnel) ═══════════════════════════════════
check("P1 seed default N=25 (Marcos 7/23)", bot.PREMARKET_STARTER_N == 25
      and 'os.environ.get("PREMARKET_STARTER_N", "25")' in SRC)
check("P2 seed is PREMARKET-GATED (<9:30) — RTH path never seeds",
      "if (_now_seed.hour * 60 + _now_seed.minute) < (9 * 60 + 30):" in SRC
      and "_premarket_starter_set()" in SRC)
check("P3 abort FIXED: seed runs BEFORE the empty-abort (session survives premarket)",
      SRC.index("Premarket starter seed") < SRC.index('No candidates from screener — ending session'))
check("P4 starter dicts tagged source=premarket_starter (for the day2 guard)",
      '"source": "premarket_starter"' in SRC)
check("P5 day2 guard: starter names filtered out before the day2 carry-over post",
      '[g for g in gappers if g.get("source") != "premarket_starter"]' in SRC
      and SRC.index('g.get("source") != "premarket_starter"') < SRC.index('/api/day2_watch'))
check("P6 Feed Engineer canary: warn when Webull price-stream subs > 40 (kick line)",
      "WEBULL-SUB CANARY" in SRC and "len(stream_tickers) > 40" in SRC)
check("P7 additive: seed APPENDS to gappers (feed still auto-adds via the 3-min rescan, untouched)",
      "gappers = gappers + [{" in SRC and "rescan_callback=_intraday_rescan" in SRC)
check("P8 ranked by change_pct (Move %) — Kev-first then movers desc, dedup order-stable",
      "reverse=True" in SRC and "dict.fromkeys(kev + starter)" in SRC)

print(f"\n{'='*60}\n#98 PREMARKET SEED RIG: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", *FAIL, sep="\n  ")
sys.exit(1 if FAIL else 0)
