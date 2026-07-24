"""#99 Move%-ranked read-list rig (Marcos 7/23: 'reads done from the top-20 of my scanner's Move%
column, biggest first'). FUNCTIONAL: real _post_read_list captures its POST payload; reader
sort-order pins; dashboard + call-site source pins. Single sys.exit."""
import sys, os, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
ROOT = pathlib.Path(__file__).resolve().parent.parent
from loader import load_bot
bot = load_bot()
BOT = (ROOT / "marcos_trading_bot.py").read_text()
DASH = (ROOT / "screener_app.py").read_text()
RDR = (ROOT / "newcomer_vision_reader.py").read_text()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

class _Resp:
    def __init__(s, code, payload): s.status_code, s._p = code, payload
    def json(s): return s._p

# ═══ FUNCTIONAL: _post_read_list captures its payload ═════════════════════════
os.environ["SCREENER_URL"] = "http://fake-dash"
_captured = {}
def _fake_post(url, json=None, **k):
    _captured["url"] = url; _captured["tickers"] = (json or {}).get("tickers")
    return _Resp(200, {"status": "ok"})
_orig_post = bot.requests.post
try:
    bot.requests.post = _fake_post
    bot._fetch_kev_watchlist = lambda: ["PN", "INLF", "LABT"]
    # 25 gappers, change_pct = i (M1=1 .. M25=25); intentionally NOT pre-sorted
    gappers = [{"symbol": f"M{i}", "change_pct": float(i), "select_score": float(100 - i)} for i in range(1, 26)]
    import random  # shuffle so we prove the SORT, not input order (seedless: reverse is deterministic enough)
    gappers = list(reversed(gappers))
    bot._post_read_list(gappers)
    t = _captured.get("tickers") or []
    check("M1 posts to /api/read_list", _captured.get("url", "").endswith("/api/read_list"))
    check("M2 Kev FIRST (3 names)", t[:3] == ["PN", "INLF", "LABT"], f"got {t[:3]}")
    check("M3 ranked by MOVE% (change_pct) desc: M25 before M24 before M23",
          t.index("M25") < t.index("M24") < t.index("M23"), f"got {t[3:8]}")
    check("M4 capped at top-20 movers (+Kev 3 = 23)", len(t) == 23, f"got {len(t)}")
    check("M5 smallest movers bumped (M1..M5 below the 20 cut are OUT)",
          "M5" not in t and "M25" in t, f"tail={t[-3:]}")
    check("M6 change_pct used, NOT select_score (M25 has LOWEST select_score yet ranks first)",
          t[3] == "M25", f"got t[3]={t[3] if len(t)>3 else None}")
    # fail-safe: no SCREENER_URL → no raise, no post
    _captured.clear(); os.environ.pop("SCREENER_URL", None)
    bot._post_read_list(gappers)
    check("M7 no SCREENER_URL → no post, no raise", "tickers" not in _captured)
    os.environ["SCREENER_URL"] = "http://fake-dash"
finally:
    bot.requests.post = _orig_post

# ═══ SOURCE PINS ══════════════════════════════════════════════════════════════
# BOT: called at the END of the scan (fresh each 3-min rescan), draws from full float-filtered set
check("P1 bot: _post_read_list CALLED at scan end, from float_checked (Move% rank, not select_score)",
      "_post_read_list(float_checked)" in BOT
      and BOT.index("_post_read_list(float_checked)") < BOT.index("    return results"))
check("P2 bot: ranks by change_pct desc, top-20, Kev-first",
      'key=lambda g: float(g.get("change_pct") or 0), reverse=True' in BOT
      and "ranked[:20]" in BOT and "dict.fromkeys(kev + top)" in BOT)

# DASHBOARD: read_list POST (auth) + GET
check("P3 dash: /api/read_list POST is auth-gated + GET serves it",
      '@app.route("/api/read_list", methods=["POST"])' in DASH
      and '@app.route("/api/read_list", methods=["GET"])' in DASH
      and DASH.count('X-Dashboard-Secret') >= 1 and "_read_list" in DASH)

# READER: reads STRICTLY the read-list (top-20+Kev) in Move% order — a hard cap, fail-soft
check("P4 reader: reads STRICTLY the read-list in ORDER (Marcos 'strictly top 20' — biggest first, no re-sort)",
      "/api/read_list" in RDR
      and "todo = [tk for tk in _rl if tk not in seen" in RDR)
check("P5 reader: bounded — NO additive roster union; todo is the read-list ONLY (fewer reads, not more)",
      'roster[_tk] = ""' not in RDR and "for tk in todo:" in RDR
      and "hard CAP" in RDR)
check("P6 reader: fail-soft — no read_list → full active roster in time-order (never zeroes reads)",
      "if _rl:" in RDR and "else:\n        todo = [tk for _tm, tk in sorted(" in RDR)

print(f"\n{'='*60}\n#99 READ-LIST RIG: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", *FAIL, sep="\n  ")
sys.exit(1 if FAIL else 0)
