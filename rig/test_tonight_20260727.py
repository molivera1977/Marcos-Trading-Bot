"""Replay rig — tonight's 7/27 change-set (HANDOFF_20260727_tonight.md).

Six items, each with a FUNCTIONAL test that fails without the fix:
  1. true intrabar stop + crater floor beneath it   (LGHL / JZXN craters, LVWR / DFNS shakeout cost)
  2. sessions=["PRE","RTH"] on live fetches + DST-correct session filter
  3. BE_FLOOR_AFTER_SCALE 2 -> 1
  4. hidden_entry R-based first trim               (VEEE 6.9R / LVWR 1.62R peaks, $0 banked)
  5. entry timestamp stamped on every trade record
  6. read-list liquidity floor

Run:  python3 rig/test_tonight_20260727.py     (exit code is the verdict)
"""
import sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.argv = ["rig"]
from loader import load_bot
bot = load_bot()
SRC = (HERE.parent / "marcos_trading_bot.py").read_text()

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok  " if cond else "  XX  ") + name + ((" — " + detail) if detail and not cond else ""))


# ══════════════════════════════════════════════════════════════════════════════
# monitor_trade harness — real function, stubbed I/O. Price walks a scripted path;
# bar fetches return [] so 3-min structural exits stay OUT of the way and each test
# measures exactly the mechanism it names.
# ══════════════════════════════════════════════════════════════════════════════
class _Stream:
    def __init__(self, path):
        self.path, self.i = list(path), 0
    def loop_sleep(self):  return 0
    def get_price(self, _t):
        px = self.path[min(self.i, len(self.path) - 1)]
        self.i += 1
        return px
    connected = True

_CLOCK = [0]

class _FrozenDT(bot.datetime):
    """Session clock for a replay: starts 10:30 ET on 7/27 (inside the window, so neither the 3:45pm
    flatten nor the 9:25 premarket flatten interferes) and advances 30s per read. The advance is what
    terminates a replay whose price path never hits an exit — it eventually reaches the 3:45 flatten,
    which is exactly what a held-to-close trade does live."""
    @classmethod
    def now(cls, tz=None):
        _CLOCK[0] += 1
        t = (bot.EASTERN.localize(bot.datetime(2026, 7, 27, 10, 30, 0))
             + bot.timedelta(seconds=30 * _CLOCK[0]))
        return t.astimezone(tz) if tz is not None else t.replace(tzinfo=None)

def replay(path, entry, stop, entry_type="flat_top", bars=None, **over):
    """Run the REAL monitor_trade over a scripted price path. Returns its result dict."""
    saved = {"datetime": bot.datetime}
    bot.datetime = _FrozenDT
    _CLOCK[0] = 0
    for n, v in [("close_position", lambda *a, **k: True), ("cancel_order", lambda *a, **k: True),
                 ("place_stop_order", lambda *a, **k: None), ("_post_trade_state", lambda *a, **k: None),
                 ("_save_open_trade", lambda *a, **k: None), ("send_partial_exit_alert", lambda *a, **k: None),
                 ("get_intraday_bars", lambda *a, **k: list(bars or [])),
                 ("_vride_defer", lambda *a, **k: False)]:
        saved[n] = getattr(bot, n, None); setattr(bot, n, v)
    for k, v in over.items():
        saved.setdefault(k, getattr(bot, k, None)); setattr(bot, k, v)
    bot._active_monitors.pop("T", None); bot._monitor_abort.discard("T")
    try:
        return bot.monitor_trade("T", 100, entry, entry * 2, stop, _Stream(path),
                                 None, vwap=0, entry_type=entry_type)
    finally:
        for n, v in saved.items():
            setattr(bot, n, v)

def realized_R(res, entry, stop):
    """Blended P&L in R — the only unit a stop claim may be graded in."""
    R = max(entry - stop, 0.01)
    return res["profit_loss"] / (R * 100)


# ══ ITEM 1 — TRUE INTRABAR STOP ═══════════════════════════════════════════════
print("\nITEM 1  true intrabar stop + crater floor")

# LGHL 2026-07-27 zone_flip, the worst row of the era: entry 1.975, stop 1.87,
# planned risk $29.92 on 285 sh; price cratered to 1.56 inside ONE 3-min candle.
LGHL_E, LGHL_S = 1.975, 1.87
lghl = replay([1.975, 1.95, 1.90, 1.86, 1.78, 1.70, 1.62, 1.56], LGHL_E, LGHL_S)
check("1a LGHL crater exits AT the stop, not below it",
      lghl["exit_price"] <= LGHL_S and lghl["exit_price"] >= 1.85,
      f"exit {lghl['exit_price']} reason {lghl['exit_reason']}")
check("1b LGHL realized loss is ~1R, not the live −3.3R",
      -1.15 <= realized_R(lghl, LGHL_E, LGHL_S) <= -0.85,
      f"got {realized_R(lghl, LGHL_E, LGHL_S):.2f}R")

# JZXN 2026-07-27 RTH: the second blow-through of the day (−2.17R live).
jzxn = replay([2.40, 2.36, 2.28, 2.10, 1.95], 2.40, 2.30)
check("1c JZXN blow-through capped at the stop", jzxn["exit_price"] <= 2.30 and realized_R(jzxn, 2.40, 2.30) >= -1.2,
      f"exit {jzxn['exit_price']} = {realized_R(jzxn, 2.40, 2.30):.2f}R")

# FAIL-WITHOUT-FIX: the same LGHL path with the intrabar stop off rides the crater down.
off = replay([1.975, 1.95, 1.90, 1.86, 1.78, 1.70, 1.62, 1.56, 1.56], LGHL_E, LGHL_S, INTRABAR_STOP=False)
check("1d fail-without-fix: INTRABAR_STOP=False rides well past the stop",
      off["exit_price"] < LGHL_S - 0.05, f"exit {off['exit_price']} reason {off['exit_reason']}")

# ACCEPTED COST (stated, not hidden): the wick-shakeout class. LVWR 7/24 and DFNS 7/27
# both dipped through their stop and recovered; live they exited ~flat (−$0.26 / −$2.29),
# with the intrabar stop they take ~−1R. Measured cost ≈ $57 vs $441 blow-through excess.
lvwr = replay([1.60, 1.55, 1.51, 1.50, 1.48, 1.62, 1.70], 1.60, 1.5019)
check("1e accepted cost: LVWR 7/24 wick-shakeout now stops at ~−1R",
      lvwr["exit_price"] <= 1.5019 and realized_R(lvwr, 1.60, 1.5019) >= -1.1,
      f"{realized_R(lvwr, 1.60, 1.5019):.2f}R")
dfns = replay([6.71, 6.55, 6.45, 6.43, 6.26, 6.90, 7.10], 6.71, 6.44)
check("1f accepted cost: DFNS 7/27 wick-shakeout now stops at ~−1R",
      dfns["exit_price"] <= 6.44 and realized_R(dfns, 6.71, 6.44) >= -1.1,
      f"{realized_R(dfns, 6.71, 6.44):.2f}R")

# THE STATED BOUNDARY, pinned so nobody later reads "intrabar stop" as "guaranteed −1R":
# the fill is the first print AT OR BELOW the stop. Tape that GAPS through still books worse
# than −1R. Capping that needs the resting broker stop — its own night, immediately after.
gap = replay([1.60, 1.55, 1.40, 1.30], 1.60, 1.5019)
check("1e2 boundary: a GAP through the stop still books worse than −1R (decision lag capped, gaps not)",
      realized_R(gap, 1.60, 1.5019) < -1.0 and gap["exit_price"] <= 1.5019,
      f"{realized_R(gap, 1.60, 1.5019):.2f}R")

# CRATER FLOOR — the failsafe BENEATH the stop, for when the stop was never actionable.
crater = replay([10.0, 9.0, 7.0, 5.0], 10.0, 9.0, INTRABAR_STOP=False)
check("1g crater floor fires with the intrabar stop disabled",
      crater["exit_reason"].startswith("CRATER FLOOR"), f"got {crater['exit_reason']}")
check("1h crater floor sits at 2R by default and is env-tunable",
      bot.CRATER_FLOOR_R == 2.0 and 'os.environ.get("CRATER_FLOOR_R"' in SRC)
check("1i intrabar stop has a kill switch, default ON",
      bot.INTRABAR_STOP is True and 'os.environ.get("INTRABAR_STOP", "1")' in SRC)
check("1i2 confirm dial exists and is INERT by default (0s = fire on the first print, as approved)",
      bot.INTRABAR_CONFIRM_SECS == 0 and 'os.environ.get("INTRABAR_CONFIRM_SECS", "0")' in SRC)
conf = replay([1.975, 1.95, 1.90, 1.86, 1.78, 1.70, 1.62, 1.56], LGHL_E, LGHL_S,
              INTRABAR_CONFIRM_SECS=3600)   # absurd confirm → the intrabar path must not fire at all
check("1i3 confirm dial actually gates the exit (huge confirm → no intrabar exit)",
      not conf["exit_reason"].startswith("Stop loss"), f"got {conf['exit_reason']}")
check("1i4 the 7/14 breach-mode refutation is recorded beside the mechanism it refutes",
      "breach-mode" in SRC and "−2.08R" in SRC and "YYGH-class winners" in SRC)
check("1j 3-min structural exits untouched above the stop",
      bot.EXITS_ON_3MIN is True and "_stop_close_qualifies(completed[-1], _entry_ts_utc)" in SRC)


# ══ ITEM 2 — sessions=["PRE","RTH"] + DST ═════════════════════════════════════
print("\nITEM 2  premarket sessions + DST")

check("2a DST: a 09:35 ET bar is RTH in July AND in January (EST)",
      bot._et_session_of_utc("2026-07-23T13:35:00") == "RTH"
      and bot._et_session_of_utc("2026-01-23T14:35:00") == "RTH")
check("2b DST: the OLD hardcoded window mislabels January — 14:35Z was 'RTH' by clock math in EDT only",
      bot._et_session_of_utc("2026-01-23T13:35:00") == "PRE",
      "08:35 ET in winter must be PRE, not RTH")
check("2c premarket 07:00 ET is PRE, after-hours 17:00 ET is ATH",
      bot._et_session_of_utc("2026-07-23T11:00:00") == "PRE"
      and bot._et_session_of_utc("2026-07-23T21:00:00") == "ATH")
check("2d overnight 02:00 ET is no session at all",
      bot._et_session_of_utc("2026-07-23T06:00:00") is None)

# The blackout itself: sessions=None must drop premarket bars (that IS the Webull contract),
# and sessions=["PRE","RTH"] must keep them. Fed through the real filter via a fake REST payload.
_raw = {"bars": [{"t": "2026-07-27T11:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 10},   # 07:00 ET PRE
                 {"t": "2026-07-27T14:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 10}]}  # 10:00 ET RTH
_orig = bot._alpaca_rest_get
try:
    bot._alpaca_rest_get = lambda *a, **k: _raw
    rth_only = bot._alpaca_intraday_bars("T", count=10, sessions=None)
    with_pre = bot._alpaca_intraday_bars("T", count=10, sessions=["PRE", "RTH"])
finally:
    bot._alpaca_rest_get = _orig
check("2e sessions=None still returns RTH only (unchanged live behavior)", len(rth_only) == 1)
check("2f sessions=['PRE','RTH'] returns the premarket bar — the blackout fix", len(with_pre) == 2,
      f"got {len(with_pre)} bars")

_orig2 = bot._alpaca_rest_get
try:
    bot._alpaca_rest_get = lambda *a, **k: _raw
    all3 = bot._alpaca_intraday_bars("T", count=30, sessions=["PRE", "RTH", "ATH"])
finally:
    bot._alpaca_rest_get = _orig2
check("2f2 F3-adjacent (review F6): a caller naming ALL THREE sessions still gets the whole extended "
      "day — honoring `sessions` must not silently shrink the bar ARCHIVE", len(all3) == 2,
      f"got {len(all3)}")

check("2g _live_sessions: PRE-stamped position asks for PRE bars, RTH position does not",
      bot._live_sessions(True) == ["PRE", "RTH"] and bot._live_sessions(False) is None)
check("2h monitor's bar fetch threads the session list",
      "sessions=_live_sessions(_entered_premkt or None)" in SRC)
check("2i scan/entry fetches thread it too (momentum, candidate bars, velocity, universal gates)",
      SRC.count("sessions=_live_sessions()") >= 6, f"got {SRC.count('sessions=_live_sessions()')}")
check("2j ENTRY_OPEN_ET NOT reverted tonight (04:00 only after this is rig-green live)",
      'ENTRY_OPEN_ET' in SRC and '"04:00"' not in SRC.split("ENTRY_OPEN_ET")[1][:120])


# ══ ITEM 3 — BE floor ═════════════════════════════════════════════════════════
print("\nITEM 3  BE floor after the FIRST partial")
check("3a kev25 profile floors at scale #1", bot.BE_FLOOR_AFTER_SCALE == 1)
# Functional: bank the first tier at +1R, then round-trip. The stop must be entry, not structure.
be = replay([10.0, 11.0, 10.6, 10.1, 9.99, 9.5], 10.0, 9.0)
check("3b banked-then-red is impossible: after the +1R trim the trade cannot finish red",
      be["profit_loss"] > 0 and len(be["partial_fills"]) >= 1,
      f"pnl {be['profit_loss']:.2f} partials {be['partial_fills']}")


# ══ ITEM 4 — hidden R-trim ════════════════════════════════════════════════════
print("\nITEM 4  hidden_entry R-based first trim")
check("4a HIDDEN_TRIM_R exists, defaults to 1.0R, env-tunable",
      bot.HIDDEN_TRIM_R == 1.0 and 'os.environ.get("HIDDEN_TRIM_R"' in SRC)

# VEEE 7/27: entry 17.30, high 23.29 (+6.9R), ZERO banked, closed −$25.33.
veee = replay([17.30, 18.0, 19.5, 21.0, 23.29, 20.0, 18.0, 17.2, 16.9],
              17.30, 16.43, entry_type="hidden_entry")
check("4b VEEE replay banks at least one trim (live it banked nothing)",
      len(veee["partial_fills"]) >= 1, f"partials {veee['partial_fills']}")
check("4c VEEE replay finishes GREEN instead of −$25.33",
      veee["profit_loss"] > 0, f"pnl {veee['profit_loss']:.2f}")

# LVWR 7/27 hidden_entry: peak +1.62R, zero banked, −$39.29.
lv = replay([2.00, 2.10, 2.25, 2.32, 2.10, 1.95, 1.88], 2.00, 1.80, entry_type="hidden_entry")
check("4d LVWR replay banks its first trim at +1R", len(lv["partial_fills"]) >= 1,
      f"partials {lv['partial_fills']}")

# FAIL-WITHOUT-FIX: the inherited x1.50 ladder is unreachable for both peaks.
lv_old = replay([2.00, 2.10, 2.25, 2.32, 2.10, 1.95, 1.88], 2.00, 1.80,
                entry_type="hidden_entry", HIDDEN_TRIM_R=99.0)
check("4e fail-without-fix: at the old x1.50-first ladder LVWR banks NOTHING",
      len(lv_old["partial_fills"]) == 0, f"partials {lv_old['partial_fills']}")
check("4f %-tiers retained above the R trim (x1.50 and x2.00 still in the ladder)",
      "entry_price * 1.50" in SRC and "entry_price * 2.00" in SRC)

# F5 (7/27 review): a stop wider than half the entry price reorders the ladder and used to leave
# two tiers sharing a cumulative — the second would sell max(1, 0) = ONE share (a real order with
# real slippage, and a burned tier slot). Degenerate tiers must be dropped, not sold.
wide = replay([1.00, 1.60, 2.10, 3.10, 4.10, 5.00], 1.00, 0.30, entry_type="hidden_entry")
check("4g degenerate ladder never emits a 1-share scale-out",
      all(q > 1 for q, _ in wide["partial_fills"]), f"fills {wide['partial_fills']}")


# ══ ITEM 5 — entry timestamp ══════════════════════════════════════════════════
print("\nITEM 5  entry timestamp on every trade record")
check("5a stamped once at the fill, in UTC ISO", "_entry_ts_iso = datetime.now(timezone.utc)" in SRC)
check("5b present on all three record paths (normal exit, watchdog, restart recovery)",
      SRC.count('"entry_ts_utc"') >= 4, f"got {SRC.count(chr(34) + 'entry_ts_utc' + chr(34))}")
check("5c carried through durable state so a restart keeps it",
      '"entry_ts_utc": _entry_ts_iso' in SRC and 'ctx.get("entry_ts_utc")' in SRC
      and 'o.get("entry_ts_utc")' in SRC)
DASH = (HERE.parent / "screener_app.py").read_text()
check("5d dashboard passes unknown keys through (the 7/22 whitelist-strip killer) so it actually lands",
      "trade.setdefault(_k, _v)" in DASH)


# ══ ITEM 6 — read-list liquidity floor ════════════════════════════════════════
print("\nITEM 6  read-list liquidity floor")

class _Resp:
    def __init__(s, code, payload): s.status_code, s._p = code, payload
    def json(s): return s._p

def _bars(vol, n=6):
    return [{"time": "2026-07-27T14:0%d:00.000+0000" % i, "open": "1", "high": "1",
             "low": "1", "close": "1", "volume": str(vol)} for i in range(n)]

import os
os.environ["SCREENER_URL"] = "http://fake-dash"
cap = {}
_op, _ob, _ofs, _okev = bot.requests.post, bot.get_intraday_bars, bot._fresh_session, bot._fetch_kev_watchlist
try:
    bot.requests.post = lambda url, json=None, **k: (cap.update(
        {"url": url, "tickers": (json or {}).get("tickers")}), _Resp(200, {}))[1]
    bot._fetch_kev_watchlist = lambda: []
    bot._fresh_session = lambda b, *a, **k: b
    # THIN is the DCOY/DBGI/TGL class: biggest mover on the board, ~20 traded minutes all day.
    bot.get_intraday_bars = lambda t, **k: _bars(50) if t == "THIN" else _bars(500_000)
    bot._read_liq_cache.clear()
    gappers = [{"symbol": "THIN", "change_pct": 99.0}] + \
              [{"symbol": "L%d" % i, "change_pct": float(50 - i)} for i in range(5)]
    bot._post_read_list(gappers)
    posted = cap.get("tickers") or []
    check("6a sub-floor name never reaches the posted read list", "THIN" not in posted, f"got {posted}")
    check("6b liquid movers still posted, in Move% order", posted[:2] == ["L0", "L1"], f"got {posted}")

    # F3 (7/27 review): THE case the floor exists for. DCOY/DBGI/TGL printed 20/6/7 bars in 30h,
    # so their newest bar is hours stale — _fresh_session blanks it. The first cut of this fix
    # routed that to fail-open, i.e. the three names it was written to exclude sailed through.
    bot._read_liq_cache.clear()
    bot._fresh_session = _ofs                      # the REAL staleness filter, not a pass-through
    stale = [{"time": "2026-07-27T09:17:00.000+0000", "open": "1", "high": "1",
              "low": "1", "close": "1", "volume": "50"}] * 6
    bot.get_intraday_bars = lambda t, **k: stale if t == "DCOY" else _bars(500_000)
    cap.clear()
    bot._post_read_list([{"symbol": "DCOY", "change_pct": 99.0}] +
                        [{"symbol": "L%d" % i, "change_pct": float(50 - i)} for i in range(5)])
    check("6a2 DCOY-shaped name (real bars, all stale) is EXCLUDED, not fail-opened",
          "DCOY" not in (cap.get("tickers") or []), f"got {cap.get('tickers')}")
    bot._fresh_session = lambda b, *a, **k: b

    # FAIL-OPEN: a data miss must never be read as illiquidity.
    bot._read_liq_cache.clear()
    bot.get_intraday_bars = lambda t, **k: []
    cap.clear(); bot._post_read_list(gappers)
    check("6c fail-open: no bars → name is kept, roster does not shrink",
          "THIN" in (cap.get("tickers") or []), f"got {cap.get('tickers')}")

    # An API error must fail open too, not empty the roster.
    bot._read_liq_cache.clear()
    def _boom(*a, **k): raise RuntimeError("429")
    bot.get_intraday_bars = _boom
    cap.clear(); bot._post_read_list(gappers)
    check("6d fail-open on error: roster intact", len(cap.get("tickers") or []) == 6,
          f"got {cap.get('tickers')}")
finally:
    bot.requests.post, bot.get_intraday_bars = _op, _ob
    bot._fresh_session, bot._fetch_kev_watchlist = _ofs, _okev

check("6e floor tracks the ENTRY gate's floor by default (one number, not a second homegrown one)",
      bot.READ_LIST_LIQ_FLOOR is None and "READ_LIST_LIQ_FLOOR or MOMENTUM_MIN_AVG_VOL" in SRC)
check("6f probes run on the AUX executor, never the trade pool", "executor=_aux_executor" in SRC.split("def _read_list_liquid_enough")[1][:900])
check("6g scanner's wide net deliberately unchanged (counterfactual log preserved)",
      "_post_read_list(float_checked)" in SRC)


print("\n" + "=" * 62)
print(f"TONIGHT 7/27 RIG: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", *FAIL, sep="\n  ")
sys.exit(1 if FAIL else 0)
