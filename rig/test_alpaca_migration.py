"""#97 Alpaca migration rig (Fable review §8: A1 hot endpoint, A2 stop-path pin, A3 backfill,
T2 curl choke-point, T3 1-min parity, T6 daily). FUNCTIONAL tests — synthetic data through the
real functions (no-feature-ships-unexercised), plus Integrator source pins. Single sys.exit."""
import sys, json, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
ROOT = pathlib.Path(__file__).resolve().parent.parent
from loader import load_bot
bot = load_bot()
sys.path.insert(0, str(ROOT))
import alpaca_capture as cap

SRC  = (ROOT / "marcos_trading_bot.py").read_text()
CSRC = (ROOT / "alpaca_capture.py").read_text()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

# ═══ CAPTURE SIDE (A1 + A3) ═══════════════════════════════════════════════════
# M1: hot_snapshot — closed buckets only, bounded n, full-day retention tail, vwap
now10 = int(time.time()) // 10 * 10
with cap._lock:
    cap._bars["TESTA"] = {now10 - 10 * i: {"o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05, "v": 100 + i}
                          for i in range(1, 6)}                 # 5 CLOSED buckets
    cap._bars["TESTA"][now10] = {"o": 9, "h": 9, "l": 9, "c": 9, "v": 9}   # still-forming
    cap._vwap["TESTA"] = {"num": 210.0, "den": 200.0, "series": []}
snap = cap.hot_snapshot("TESTA", 3)
check("M1 hot_snapshot: last-3 tail of CLOSED buckets only (forming bucket excluded)",
      len(snap["bars"]) == 3 and all(b[0] != now10 for b in snap["bars"])
      and snap["day_bars"] == 6, f"got {len(snap['bars'])} bars, day={snap['day_bars']}")
check("M1b hot_snapshot: vwap = num/den", abs(snap["vwap"] - 1.05) < 1e-9, f"got {snap['vwap']}")
check("M1c hot_snapshot: n hard-bounded at HOT_MAX_N (PCC no-expensive-query condition)",
      len(cap.hot_snapshot("TESTA", 99999)["bars"]) <= cap.HOT_MAX_N)

# M2: pure router — auth, validation, routes
check("M2 route: bad secret -> 401 (never data)", cap._hot_route("/hot", {"sym": "TESTA"}, False)[0] == 401)
check("M2b route: bad sym -> 400", cap._hot_route("/hot", {"sym": "x;rm"}, True)[0] == 400)
check("M2c route: /health 200 + /hot 200 + unknown 404",
      cap._hot_route("/health", {}, True)[0] == 200
      and cap._hot_route("/hot", {"sym": "TESTA", "n": "2"}, True)[0] == 200
      and cap._hot_route("/nope", {}, True)[0] == 404)

# M3: A3 VWAP seed math — vw-weighted, close fallback, zero-vol skipped
num, den = cap._vwap_seed_from_rest_bars([{"vw": 2.0, "v": 100}, {"c": 3.0, "v": 50}, {"vw": 9.0, "v": 0}])
check("M3 A3 seed: sum(vw*v) w/ close fallback, zero-vol skipped",
      abs(num - 350.0) < 1e-9 and abs(den - 150.0) < 1e-9, f"got {num}/{den}")
check("M3b A3 wired: sync_roster seeds every NEW symbol; _reset_day clears _seeded",
      "_backfill_new_symbol(s)" in CSRC and "_seeded.clear()" in CSRC)
check("M3c A1 wired: main() CALLS _start_hot_server (indented call, not just the def)",
      "\n    _start_hot_server()" in CSRC
      and CSRC.index("\n    _start_hot_server()") > CSRC.index("def main"))

# ═══ BOT SIDE ═════════════════════════════════════════════════════════════════
import requests as _real_requests
class _FakeResp:
    def __init__(self, code, payload): self.status_code, self._p = code, payload
    def json(self): return self._p

# M4: hot-payload conversion — v1-v0 MUST equal true per-bar volume (fail-without-fix:
# a v0==v1 conversion zeroes volume and the reclaim 2x-vol gate can never pass = silent #89 rerun)
hot_payload = {"bars": [[now10 - 30, 1.0, 1.1, 0.9, 1.05, 777], [now10 - 20, 1.05, 1.2, 1.0, 1.15, 888]]}
bot.ALP_CAPTURE_URL = "http://fake-capture"
def _fake_get_hot(url, **kw):
    if "fake-capture" in url: return _FakeResp(200, hot_payload)
    raise RuntimeError("unexpected url " + url)
_orig_get = bot.requests.get
try:
    bot.requests.get = _fake_get_hot
    d, src = bot._alp10_bars("TESTB", 90)
    check("M4 conversion: shadow shape + (v1-v0)==true per-bar volume",
          src == "alp-hot" and len(d) == 2
          and d[now10 - 30]["v1"] - d[now10 - 30]["v0"] == 777
          and d[now10 - 20]["v1"] - d[now10 - 20]["v0"] == 888
          and d[now10 - 30]["o"] == 1.0 and d[now10 - 20]["h"] == 1.2, f"src={src} d={d}")

    # M5: fallback — hot endpoint dead -> dashboard read (the rig-EXERCISED fallback, Integrator)
    import os as _os
    _os.environ["SCREENER_URL"] = "http://fake-dash"
    def _fake_get_fb(url, **kw):
        if "fake-capture" in url: raise RuntimeError("capture down")
        if "fake-dash" in url:
            return _FakeResp(200, {"bars": [{"time": "2026-07-23T15:00:00.000+0000", "open": "2",
                                             "high": "2.2", "low": "1.9", "close": "2.1", "volume": "555"}]})
        raise RuntimeError("unexpected " + url)
    bot.requests.get = _fake_get_fb
    d2, src2 = bot._alp10_bars("TESTB", 90)
    _k = list(d2)[0] if d2 else 0
    check("M5 fallback: capture down -> dashboard ~ALP10S (volume intact)",
          src2 == "alp-dash" and len(d2) == 1 and d2[_k]["v1"] == 555.0, f"src={src2} d={d2}")

    # M6: _curl_feed source switch honors CURL_SOURCE
    with bot._shadow_lock:
        bot._shadow_bars[10]["TESTC"] = {now10 - 20: {"o": 1, "h": 1, "l": 1, "c": 1, "v0": 10, "v1": 40}}
    bot.CURL_SOURCE = "webull"
    dw, sw = bot._curl_feed("TESTC")
    bot.CURL_SOURCE = "alpaca"
    bot.requests.get = _fake_get_hot
    da, sa = bot._curl_feed("TESTC")
    check("M6 _curl_feed: webull -> _shadow_bars; alpaca -> hot endpoint (one choke-point)",
          sw == "webull-shadow" and len(dw) == 1 and sa == "alp-hot" and len(da) == 2,
          f"{sw}/{len(dw)} {sa}/{len(da)}")

    # M7 FLAGSHIP E2E: Alpaca-fed tape FIRES the real reclaim machine (the #89 acceptance, in-rig).
    # Tape vs line=1.00: cross on 2x vol -> extend >=1% -> retest wick (>=50% lower-wick) -> curl over wick-high.
    tape = [[now10 - 60, 0.98, 0.99, 0.97, 0.98, 100],
            [now10 - 50, 0.99, 1.02, 0.98, 1.005, 300],
            [now10 - 40, 1.005, 1.015, 1.004, 1.012, 150],
            [now10 - 30, 1.006, 1.010, 1.004, 1.008, 120],
            [now10 - 20, 1.009, 1.02, 1.008, 1.015, 200]]
    hot_payload = {"bars": tape}
    d3, s3 = bot._curl_feed("TESTD")
    nb = [(b["o"], b["h"], b["l"], b["c"], max(b["v1"] - b["v0"], 0)) for _, b in sorted(d3.items())]
    fire = bot.kev_reclaim_step("TESTD", nb, 1.00)
    check("M7 E2E: Alpaca-sourced bars FIRE kev_reclaim_step (stop/wick_low returned)",
          s3 == "alp-hot" and fire is not None and fire.get("wick_low") == 1.004,
          f"src={s3} fire={fire}")
    # fail-without-fix proof: same tape with volumes ZEROED (a broken conversion) must NOT fire
    hot_payload = {"bars": [[k, o, h, l, c, 0] for k, o, h, l, c, v in tape]}
    d4, _ = bot._curl_feed("TESTE")
    nb0 = [(b["o"], b["h"], b["l"], b["c"], max(b["v1"] - b["v0"], 0)) for _, b in sorted(d4.items())]
    check("M7b fail-without-fix: zero-volume conversion cannot fire (2x-vol gate holds)",
          bot.kev_reclaim_step("TESTE", nb0, 1.00) is None)

    # M8: T3 parity — Alpaca REST 1-min -> EXACT Webull shape, RTH filter, chronological, count slice
    def _fake_rest(url, params, timeout=8):
        return {"bars": [
            {"t": "2026-07-23T12:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 10},    # 8:00 ET premarket
            {"t": "2026-07-23T13:30:00Z", "o": 2, "h": 2.2, "l": 1.9, "c": 2.1, "v": 20},
            {"t": "2026-07-23T13:31:00Z", "o": 2.1, "h": 2.3, "l": 2.0, "c": 2.2, "v": 30},
            {"t": "2026-07-23T20:05:00Z", "o": 3, "h": 3, "l": 3, "c": 3, "v": 40}]}   # 16:05 ET AH
    _orig_rest = bot._alpaca_rest_get
    bot._alpaca_rest_get = lambda url, params, timeout=8: _fake_rest(url, params)
    ab = bot._alpaca_intraday_bars("TESTF", count=30, sessions=None)
    check("M8 T3 parity: RTH-only filter + Webull keys + chronological + str values",
          len(ab) == 2 and ab[0]["time"] == "2026-07-23T13:30:00.000+0000"
          and ab[0]["close"] == "2.1" and ab[1]["volume"] == "30"
          and set(ab[0]) == {"time", "open", "high", "low", "close", "volume"}, f"got {ab}")
    ab2 = bot._alpaca_intraday_bars("TESTF", count=1, sessions=["RTH", "PRE"])
    check("M8b T3: sessions incl. PRE keeps extended bars; count slices the tail",
          len(ab2) == 1 and ab2[0]["time"].startswith("2026-07-23T20:05"), f"got {ab2}")

    # M9: T6 daily via the real get_daily_levels (DAILY_SOURCE=alpaca) — prior close correct
    _today = bot.datetime.now(bot.EASTERN).strftime("%Y-%m-%d")
    _days = [{"high": 1.0 + i * 0.01, "close": 1.0 + i * 0.01, "time": f"2026-06-{i:02d}"} for i in range(1, 26)]
    _days += [{"high": 5.55, "close": 5.5, "time": "2026-07-22"}, {"high": 6.0, "close": 6.2, "time": _today}]
    bot.DAILY_SOURCE = "alpaca"
    _orig_daily = bot._alpaca_daily_items
    bot._alpaca_daily_items = lambda tk: list(_days)
    lv = bot.get_daily_levels("TESTG")
    check("M9 T6: get_daily_levels on Alpaca items — prior_day_close = last date < today",
          lv is not None and lv["prior_day_close"] == 5.5 and lv["prior_day_high"] == 5.55, f"got {lv}")
    bot._alpaca_daily_items = _orig_daily
    bot._alpaca_rest_get = _orig_rest
finally:
    bot.requests.get = _orig_get
    bot.CURL_SOURCE = "webull"; bot.DAILY_SOURCE = "webull"; bot.ALP_CAPTURE_URL = ""

# ═══ SOURCE PINS (Integrator) ═════════════════════════════════════════════════
check("P1 defaults: all three switches default webull (deploy flips per-line via env)",
      'os.environ.get("CURL_SOURCE", "webull")' in SRC
      and 'os.environ.get("BARS_SOURCE", "webull")' in SRC
      and 'os.environ.get("DAILY_SOURCE", "webull")' in SRC)
check("P2 A2 pin: NO source switch on the stop/price path (get_price/_get_price_rest untouched)",
      "PRICE_SOURCE" not in SRC and "STOP_SOURCE" not in SRC
      and "stops never read" in SRC)
check("P3 ALL THREE consumers via choke-point (step x2 + zone floor); one direct read left = inside _curl_feed itself",
      SRC.count("_curl_feed(t)") == 2
      and "_curl_feed(sym, n=720)" in SRC
      and SRC.count("dict(_shadow_bars[10].get(") == 1)
check("P4 fed-bar-age canary present (Curl Mechanic: stale vs absent must be visible)",
      "last_bar_age" in SRC and "_curl_canary_t" in SRC)
check("P5 boot line states every source (deploy acceptance reads the log, never assumes env)",
      "DATA SOURCES: curl=" in SRC)
check("P6 T3 falls through to Webull on empty (per-line degrade, never blind)",
      'if BARS_SOURCE == "alpaca":' in SRC and '_bump("alp_bars_miss")' in SRC)
check("P7 429 evidence counters on Alpaca REST (Feed Engineer: headroom measured, not asserted)",
      '_bump("alp_429")' in SRC and '_bump("alp_rest_err")' in SRC)
check("P8 capture: GET-only hot server, secret header, bounded, silent request log",
      "do_GET" in CSRC and "do_POST" not in CSRC and "X-Hot-Secret" in CSRC
      and "HOT_MAX_N" in CSRC and "log_message" in CSRC)

print(f"\n{'='*60}\n#97 MIGRATION RIG: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", *FAIL, sep="\n  ")
sys.exit(1 if FAIL else 0)
