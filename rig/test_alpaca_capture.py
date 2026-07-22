"""Alpaca parallel-capture (Phase 0) source pins. Integrator discipline: prove isolation
(test series ONLY, no bot import), config surface, session gate, reconnect evidence
machinery, and no-secrets — and that this test actually runs (single sys.exit)."""
import sys, ast, re, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC   = (ROOT / "alpaca_capture.py").read_text()
GRADE = (ROOT / "vendor_test_grade.py").read_text()
TOML  = (ROOT / "railway.alpacacap.toml").read_text()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

# ── syntax: all three py files parse (grader + capture + this repo's contract) ──
try:
    ast.parse(SRC); ast.parse(GRADE); _syn = True
except SyntaxError as e:
    _syn = False; print("  syntax error: %s" % e)
check("A0 alpaca_capture.py + vendor_test_grade.py parse clean", _syn)

# ── env config surface (exact names Marcos sets on Railway) ──
check("A1 env names pinned", all(('"%s"' % k) in SRC for k in
      ("ALPACA_KEY", "ALPACA_SECRET", "ALPACA_FEED", "SYMBOL_CAP", "SYMBOL_PROBE",
       "DASHBOARD_SECRET", "SCREENER_URL")))
check("A2 defaults: feed iex, cap 150, probe off", '"iex"' in SRC and '"150"' in SRC and 'get("SYMBOL_PROBE", "0")' in SRC)

# ── SUFFIX ISOLATION: the one rule that protects production ──
check("A3 writes ~ALP10S + ~ALPVWAP", "~ALP10S" in SRC and "~ALPVWAP" in SRC)
check("A4 NEVER builds a production ~10S key (no formatted bare-10S construction)",
      re.search(r"%s~10S|\{[^}]*\}~10S", SRC) is None)
check("A5 NEVER builds a production ~VWAP key (no formatted bare-VWAP construction)",
      re.search(r"%s~VWAP|\{[^}]*\}~VWAP", SRC) is None)
check("A6 no bare-ticker series keys: every payload series[...]= line carries ~ALP",
      all("~ALP" in ln for ln in SRC.splitlines() if ln.strip().startswith("series[")))
check("A7 lowercase prod suffixes absent (recorder posts ~10s/~vwap — we must not)",
      "~10s" not in SRC and "~vwap" not in SRC)

# ── isolation from the trading path ──
_tree = ast.parse(SRC)
_imports = [a.name for n in ast.walk(_tree) if isinstance(n, ast.Import) for a in n.names] \
         + [n.module or "" for n in ast.walk(_tree) if isinstance(n, ast.ImportFrom)]
check("A8 never imports marcos_trading_bot (or recorder/screener/reader)",
      not any(("marcos_trading_bot" in i) or ("recorder" in i) or ("screener_app" in i)
              or ("newcomer_vision_reader" in i) for i in _imports)
      and re.search(r"^\s*(?:import|from)\s+[^\n]*marcos_trading_bot", SRC, re.M) is None)
check("A9 websocket-client, not the alpaca SDK", "import websocket" in SRC
      and "alpaca_trade_api" not in SRC and "from alpaca" not in SRC and "alpaca_py" not in SRC)

# ── protocol + persistence contract ──
check("A10 auth + subscribe message shapes", '"action": "auth"' in SRC
      and '"action": "subscribe"' in SRC and '"trades"' in SRC and '"unsubscribe"' in SRC)
check("A11 persists via gzip bars_bulk with secret header", "/api/bars_bulk" in SRC
      and "X-Dashboard-Secret" in SRC and "gzip.compress" in SRC)
check("A12 watermarks commit ONLY on HTTP 200 (7/16 lesson)",
      "status_code == 200" in SRC and "_shipped.update(marks[0])" in SRC
      and SRC.index("ok = r.status_code == 200") < SRC.index("_shipped.update(marks[0])"))
check("A13 roster mirror hits watching + kev_watchlist", "/api/watching?date=" in SRC
      and "/api/kev_watchlist?date=" in SRC)

# ── session gate + reconnect evidence (the kick probe) ──
check("A14 session gate 04:00-20:00 ET weekdays", "(4, 0)" in SRC and "(20, 0)" in SRC
      and "weekday() < 5" in SRC and "def in_session" in SRC)
check("A15 reconnect backoff present + bounded", "backoff = min(backoff * 2, 60)" in SRC)
check("A16 disconnect counter + duration logging", "_disconnects" in SRC
      and "DISCONNECT #" in SRC and "reconnected after" in SRC)
check("A17 5-min ALP-health line (mandatory kick evidence)", "ALP-health" in SRC
      and re.search(r"HEALTH_SECS\s*=\s*300", SRC) is not None)
check("A18 probe mode pads roster with top actives", "SYMBOL_PROBE" in SRC
      and "_refresh_actives_bg" in SRC and "_actives" in SRC)
check("A19 tick-silence fuse (no silent zombies, recorder 7/16)", "TICK SILENCE" in SRC)

# ── secrets hygiene ──
check("A20 no hardcoded key/secret literals",
      re.search(r'''["'](?:PK|AK|APCA)[A-Za-z0-9]{8,}["']''', SRC) is None)
check("A21 key/secret never interpolated into a log call",
      re.search(r'log\([^\n]*ALPACA_(KEY|SECRET)', SRC) is None
      and re.search(r'log\([^\n]*DASH_SECRET', SRC) is None)

# ── deploy config + grader pins ──
check("A22 toml: nixpacks + own watchPatterns + start + restart always",
      'builder = "nixpacks"' in TOML and '"alpaca_capture.py"' in TOML
      and '"railway.alpacacap.toml"' in TOML and "python alpaca_capture.py" in TOML
      and 'restartPolicyType = "always"' in TOML)
check("A23 grader compares both feeds vs /api/daily truth + 98% flag",
      "~ALP10S" in GRADE and "~10S" in GRADE and "/api/daily" in GRADE and "98.0" in GRADE
      and "statistics.median" in GRADE)
check("A24 grader verifies per-feed bar counts", "wb_bars" in GRADE and "alp_bars" in GRADE)

print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
    print("RED:", ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
