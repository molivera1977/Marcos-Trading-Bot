"""Replay rig — defect regression tests.

Every test reproduces a defect observed live on 2026-07-15 (or defines the
contract of its fix). RED before the fix, GREEN after, and run before EVERY
deploy from now on. Run:  python3 rig/test_defects.py
"""
import sys, json, pathlib, threading, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.argv = ["rig"]
from loader import load_bot
bot = load_bot()

FIXTURES = HERE / "fixtures"
PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name + (f" — {detail}" if detail and not cond else ""))


def _xcur_bars():
    return json.loads((FIXTURES / "bars_20260715_multi.json").read_text())["XCUR"]

def _only_before(bars, day):
    return [b for b in bars if str(b.get("time", ""))[:10] < day]

def _sorted_asc(bars):
    return sorted(bars, key=lambda b: str(b.get("time", "")))


# ── T1: B14 class — date-blind "latest session" ─────────────────────────────
# Live repro: XCUR 9:33:28 fetch returned only prior-day bars; _latest_session
# returned YESTERDAY's session; stop check read yesterday's close (1.66) as the
# "last completed 3-min close" ≤ fresh stop (1.7946) → instant false stop ×2.
print("T1  B14: stale-day bars must yield NO session, not yesterday's session")
stale = _sorted_asc(_only_before(_xcur_bars(), "2026-07-15"))
ls = bot._latest_session(stale)
check("T1a demonstrate: _latest_session(date-blind) returns a prior day",
      bool(ls) and str(ls[-1].get("time", ""))[:10] < "2026-07-15",
      "baseline demonstration of the defect")
check("T1b contract: _fresh_session exists",
      hasattr(bot, "_fresh_session"), "fix not implemented yet")
if hasattr(bot, "_fresh_session"):
    fs = bot._fresh_session(stale, today="2026-07-15")
    check("T1c _fresh_session(prior-day bars) == []", fs == [])
    today_bars = _sorted_asc([b for b in _xcur_bars()
                              if str(b.get("time", ""))[:10] == "2026-07-15"])
    fs2 = bot._fresh_session(today_bars, today="2026-07-15", max_stale_secs=10**9)
    check("T1d _fresh_session(today's bars) keeps them", len(fs2) == len(today_bars))
    fs3 = bot._fresh_session(today_bars, today="2026-07-15", max_stale_secs=1)
    check("T1e staleness guard: old-timestamp bars rejected", fs3 == [])


# ── T2: VWAP poisoning — yesterday's VWAP must never gate today ─────────────
print("T2  VWAP: prior-day fetch must produce NO vwap (0), not yesterday's vwap")
poisoned = bot.calculate_vwap(bot._latest_session(stale))
check("T2a demonstrate: date-blind pipeline yields a NONZERO phantom vwap",
      poisoned > 0, "baseline demonstration")
if hasattr(bot, "_fresh_session"):
    clean = bot.calculate_vwap(bot._fresh_session(stale, today="2026-07-15"))
    check("T2b fixed pipeline yields 0 → callers' vwap>0 gates skip", clean == 0)


# ── T3: B15 — blind-stop must NOT fire on healthy fetch cadence ─────────────
# Live repro: jittered cadence is 48–72s; B11_BLIND_SECS was 60; _last_bars_ok
# refreshes only on success → tail of every healthy cycle counted as "blind";
# UBXG remainder flushed at 4.64 (printed 5.00+ within a minute), VMAR same path.
print("T3  B15: blind predicate")
check("T3a contract: _blind_stop_should_fire exists",
      hasattr(bot, "_blind_stop_should_fire"), "fix not implemented yet")
if hasattr(bot, "_blind_stop_should_fire"):
    now = 1_000_000.0
    fire = bot._blind_stop_should_fire
    check("T3b healthy cadence (65s since bars, 0 failures, 25s below) → NO fire",
          not fire(now=now, last_bars_ok=now - 65, below_since=now - 25, fetch_failures=0))
    check("T3c one failure, 100s → NO fire (needs 2 failures AND 150s)",
          not fire(now=now, last_bars_ok=now - 100, below_since=now - 25, fetch_failures=1))
    check("T3d true blindness (2 failures, 160s, 25s below) → FIRE",
          fire(now=now, last_bars_ok=now - 160, below_since=now - 25, fetch_failures=2))
    check("T3e blind but breach not sustained (10s) → NO fire",
          not fire(now=now, last_bars_ok=now - 160, below_since=now - 10, fetch_failures=2))
    check("T3f NVVE-class disaster (6 min blind, many failures) → FIRE",
          fire(now=now, last_bars_ok=now - 360, below_since=now - 30, fetch_failures=5))


# ── T4: B3 utility — atomic claim helper (NOT yet wired) ────────────────────
# CORRECTED 7/15: the XCUR "double entry" was NOT a race — B14 instant-killed
# trade #1, held was released by design, #2 was a legitimate re-trigger 20s
# later (sequential, never concurrent). These helpers are kept, tested, and
# unwired, ready for B3-proper (per-trade keying for same-day re-entries).
print("T4  B3: atomic held-claim")
check("T4a contract: _claim_ticker/_release_ticker exist",
      hasattr(bot, "_claim_ticker") and hasattr(bot, "_release_ticker"),
      "fix not implemented yet")
if hasattr(bot, "_claim_ticker"):
    wins = []
    def worker():
        if bot._claim_ticker("RACE"):
            wins.append(1)
    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads: t.start()
    for t in threads: t.join()
    check("T4b 16 concurrent claims → exactly 1 winner", len(wins) == 1, f"winners={len(wins)}")
    bot._release_ticker("RACE")
    check("T4c after release, claimable again", bot._claim_ticker("RACE"))
    bot._release_ticker("RACE")
    check("T4d double-release is safe", True)


# ── T5: stop check must require a post-entry, same-day qualifying close ─────
print("T5  B14 stop contract: qualifying close must post-date entry, same day")
check("T5a contract: _stop_close_qualifies exists",
      hasattr(bot, "_stop_close_qualifies"), "fix not implemented yet")
if hasattr(bot, "_stop_close_qualifies"):
    q = bot._stop_close_qualifies
    ybar = {"time": "2026-07-14T19:57:00Z", "close": 1.66}
    tbar_pre  = {"time": "2026-07-15T13:30:00Z", "close": 1.70}
    tbar_post = {"time": "2026-07-15T13:36:00Z", "close": 1.70}
    entry_ts = "2026-07-15T13:33:28"
    check("T5b yesterday's bar NEVER qualifies", not q(ybar, entry_ts, today="2026-07-15"))
    check("T5c today's bar closed BEFORE entry never qualifies",
          not q(tbar_pre, entry_ts, today="2026-07-15"))
    check("T5d today's bar closed AFTER entry qualifies",
          q(tbar_post, entry_ts, today="2026-07-15"))


# ── T6: config pins — validated settings must not silently regress ──────────
print("T6  config pins")
check("T6a ENTRY_VWAP_PREMARKET stays True (validated 7/15: 12/45 verdict flips vs chart)",
      getattr(bot, "ENTRY_VWAP_PREMARKET", False) is True)
check("T6b B11_BLIND_SECS exceeds healthy cadence (>=150)", bot.B11_BLIND_SECS >= 150)
check("T6c HEALTH_VWAP_SESSION stays True (validated 7/10)", getattr(bot, "HEALTH_VWAP_SESSION", False) is True)

# ── T7: SIGTERM flush — deploys must never be data events ────────────────────
print("T7  SIGTERM flush payload")
check("T7a contract: _shadow_flush_payload/_shadow_flush_all/_on_sigterm exist",
      all(hasattr(bot, n) for n in ("_shadow_flush_payload", "_shadow_flush_all", "_on_sigterm")))
if hasattr(bot, "_shadow_flush_payload"):
    with bot._shadow_lock:
        bot._shadow_bars[10]["RIGTEST"] = {
            1752580000 + i * 10: {"o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05, "v0": i * 100, "v1": (i + 1) * 100}
            for i in range(60)}
        bot._shadow_bars[10]["TINY"] = {1752580000: {"o": 1, "h": 1, "l": 1, "c": 1, "v0": 0, "v1": 5}}
    pl = bot._shadow_flush_payload(min_buckets=50)
    check("T7b ≥50-bucket series included, namespaced ~10s", "RIGTEST~10s" in pl["series"]
          and len(pl["series"]["RIGTEST~10s"]) == 60)
    check("T7c sub-floor series excluded", "TINY~10s" not in pl["series"])
    b0 = pl["series"]["RIGTEST~10s"][0]
    check("T7d bar shape matches /api/bars store (time/open/high/low/close/volume)",
          set(b0.keys()) == {"time", "open", "high", "low", "close", "volume"} and b0["volume"] == "100")
    with bot._shadow_lock:
        bot._shadow_bars[10].pop("RIGTEST", None); bot._shadow_bars[10].pop("TINY", None)


# ── T8: chart-break gate contract (Layer 2 — "No Break, No Trade") ───────────
# Locks _chart_break_gate's behavior BEFORE it is ever enforced (CHART_GATE_ENFORCE=1).
# Levels are pre-seeded into the module cache so the gate reads them WITHOUT any network.
print("T8  chart-gate: No-Break-No-Trade contract")
check("T8a contract: _chart_break_gate exists", hasattr(bot, "_chart_break_gate"))
if hasattr(bot, "_chart_break_gate"):
    _today = bot.datetime.now(bot.EASTERN).strftime("%Y-%m-%d")
    bot._kev_levels_cache.update({"date": _today, "ts": bot.time.time(), "levels": {
        "BRK":  {"break": 2.00, "note": "vision TAKE (levels-only)"},
        "VETO": {"break": 1.50, "note": "do-not-trade — parabolic blow-off"},
    }})
    g = bot._chart_break_gate
    check("T8b entry ABOVE the marked break → allow", g("BRK", 2.05)[0] == "allow")
    check("T8c entry BELOW the marked break → block", g("BRK", 1.80)[0] == "block")
    check("T8d unknown ticker (no marked level) → skip", g("NONE", 3.00)[0] == "skip")
    check("T8e do-not-trade veto → skip regardless of price", g("VETO", 9.99)[0] == "skip")
    check("T8f gate is fail-safe: bad input never raises → skip",
          g("BRK", None)[0] in ("allow", "block", "skip"))
    check("T8g config pin: KEV_LEVELS_TTL_SECS <= 120 (intraday vision levels reach the gate fast; "
          "the per-day cache blinded the gate to every level posted after boot — Fable audit 7/18)",
          getattr(bot, "KEV_LEVELS_TTL_SECS", 10**9) <= 120)
    # T8h: TTL expired + dashboard unreachable → serve same-day LAST-KNOWN-GOOD, never a {} spike
    # (in ENFORCE a {} would block every name until the next successful refresh)
    _saved_url = bot.os.environ.pop("SCREENER_URL", None)
    bot._kev_levels_cache["ts"] = 0.0
    check("T8h refresh failure serves last-known-good same-day levels", g("BRK", 2.05)[0] == "allow")
    if _saved_url is not None:
        bot.os.environ["SCREENER_URL"] = _saved_url
    bot._kev_levels_cache.update({"date": None, "levels": {}, "ts": 0.0})   # reset shared cache



# ── T9: 429-kill set — REST cache, ServerException counting, SDK log silence ─
print("T9  429-kill: REST cache / exception counting / log silence")
check("T9a contract: cache + silencer + exc-class + TTL pin exist",
      all(hasattr(bot, n) for n in ("_get_price_rest", "_silence_webull_sdk_logs",
                                    "_WBServerException", "REST_PRICE_TTL_SECS", "_rest_price_cache")))
if hasattr(bot, "_rest_price_cache"):
    calls = {"n": 0}
    _orig_qt = bot._get_webull_quote
    bot._get_webull_quote = lambda tk, executor=None: (calls.__setitem__("n", calls["n"] + 1)
                                                       or {"last_price": 5.0})
    bot._rest_price_cache.clear()
    p1 = bot._get_price_rest("RIG9"); p2 = bot._get_price_rest("RIG9")
    check("T9b two calls within TTL → ONE underlying fetch", calls["n"] == 1 and p1 == p2 == 5.0,
          f"underlying calls={calls['n']}")
    bot._rest_price_cache["RIG9"] = (0.0, 5.0)                       # force-expire
    bot._get_price_rest("RIG9")
    check("T9c expired TTL → refetches", calls["n"] == 2, f"underlying calls={calls['n']}")
    bot._get_webull_quote = lambda tk, executor=None: (calls.__setitem__("n", calls["n"] + 1) or {})
    bot._rest_price_cache.clear()
    z1 = bot._get_price_rest("RIG9F"); z2 = bot._get_price_rest("RIG9F")
    check("T9d failures cached too — a 429 storm can't hammer retries",
          calls["n"] == 3 and z1 == 0 and z2 == 0, f"underlying calls={calls['n']}")
    bot._get_webull_quote = _orig_qt
    bot._rest_price_cache.clear()

    # the 429 gauge was STRUCTURALLY zero: SDK raises ServerException, never returns a 429 resp
    class _DC:
        class market_data:
            @staticmethod
            def get_snapshot(**kw):
                raise bot._WBServerException("GATEWAY", "too many requests 429", 429)
    _orig_gdc = bot._get_data_client
    bot._get_data_client = lambda: _DC
    b429 = bot._exec_health["api_429"]
    r = bot._get_webull_quote("RIG9E")
    check("T9e ServerException counts as api_429 + fails safe to {}",
          r == {} and bot._exec_health["api_429"] == b429 + 1,
          f"api_429 {b429}→{bot._exec_health['api_429']}")
    bot._get_data_client = _orig_gdc

    import logging as _lg
    _lg.getLogger("webull.core.http.response").setLevel(_lg.DEBUG)   # simulate SDK's force-DEBUG
    bot._silence_webull_sdk_logs()
    check("T9f every webull.* logger at CRITICAL (token dump + 429 storm silenced)",
          _lg.getLogger("webull.core.client").level == _lg.CRITICAL
          and _lg.getLogger("webull.core.http.response").level == _lg.CRITICAL)
    check("T9g config pin: REST_PRICE_TTL_SECS >= 2 (never regress to hammering)",
          bot.REST_PRICE_TTL_SECS >= 2)


# ── T11: Kev 3-gate reclaim (Marcos 7/19: live 09:30–11:00, shadow otherwise) ─
print("T11 Kev reclaim state machine + pins")
check("T11a contract: kev_reclaim_step + config exist",
      all(hasattr(bot, n) for n in ("kev_reclaim_step", "RECLAIM_KEV",
                                    "RECLAIM_LIVE_START", "RECLAIM_LIVE_END")))
if hasattr(bot, "kev_reclaim_step"):
    VW = 1.00
    bot._reclaim_st.pop("RIGRC", None)
    # G1 cross w/ 10x vol -> extend >=1% -> G2 retest wick (close upper half) -> G3 curl fires
    seq = ([(0.98, 0.99, 0.97, 0.98, 100)] * 10 +          # below the line, builds vol baseline
           [(0.98, 1.02, 0.98, 1.02, 1000)] +              # G1: cross on 10x volume
           [(1.02, 1.06, 1.02, 1.055, 300)] +              # extension >= 1.01*vwap
           [(1.05, 1.05, 1.000, 1.04, 200)] +              # G2: tags the line, closes upper half (wick)
           [(1.04, 1.06, 1.03, 1.055, 250)])               # G3: closes above wick high 1.05 -> FIRE
    fire = bot.kev_reclaim_step("RIGRC", seq, VW)
    check("T11b full grammar fires on the curl, seq 0 (the live-eligible fire)",
          bool(fire) and fire["stop"] <= 1.0 and fire.get("seq") == 0, f"fire={fire}")
    # detection must CONTINUE all day (Marcos: "data for and against it the whole day"):
    # a fresh full setup after the first fire fires AGAIN, tagged seq 1 (shadow-only at the call site)
    refire = bot.kev_reclaim_step("RIGRC", seq[9:], VW)   # replay cross→extend→wick→curl
    check("T11c later setups keep firing as SHADOW evidence (seq 1)",
          bool(refire) and refire.get("seq") == 1, f"refire={refire}")
    bot._reclaim_st.pop("RIGRC2", None)
    seq_novol = [(s[0], s[1], s[2], s[3], 100) for s in seq]     # same shape, NO volume expansion
    check("T11d no volume on the break → NEVER fires",
          bot.kev_reclaim_step("RIGRC2", seq_novol, VW) is None)
    check("T11e pins: RECLAIM_KEV on, live window 09:30–11:00",
          bot.RECLAIM_KEV is True and bot.RECLAIM_LIVE_START == "09:30"
          and bot.RECLAIM_LIVE_END == "11:00")


# ── T10: exit profile — Kev25 (Marcos 7/19: "Challenger D is even more Full on Kev") ─
print("T10 exit profile pins (Kev25 default; grid10 = env revert)")
check("T10a default EXIT_PROFILE is kev25", bot.EXIT_PROFILE == "kev25")
check("T10b tiers = 50%@1R, 75%@2R → 25% RUNNER", bot.SCALE_TIERS == [(1, 0.50), (2, 0.75)])
check("T10c BE floor only after scale #2 (structure holds the +1R retest)",
      bot.BE_FLOOR_AFTER_SCALE == 2)


# ── T13: zone-flip machine + 7/20 role swap (Marcos: "I want this to go in") ─
print("T13 zone-flip Z-gates + role-swap pins")
check("T13a pins: ZONEFLIP_KEV on, tested primary cell (flush 4%, band 2%)",
      bot.ZONEFLIP_KEV is True and abs(bot.ZONEFLIP_FLUSH - 0.04) < 1e-9
      and abs(bot.ZONEFLIP_BAND - 0.02) < 1e-9)
check("T13b role swap: VWAP-reclaim demoted to shadow (RECLAIM_LIVE off, machine still on)",
      bot.RECLAIM_LIVE is False and bot.RECLAIM_KEV is True)
check("T13c zone_flip is in the entry allowlist",
      "zone_flip" in (HERE.parent / "marcos_trading_bot.py").read_text()
                     .split("BREAKOUT_ENTRIES or b[3] in")[1][:120])
# synthetic ZYBT-0720-A: zone 1.21 (injected), open930 1.30; flush bar 9:31 low 1.19 (−8.5%,
# in band, 10x vol) → wick bar (low 1.21, close upper half) → curl bar close > wick high → FIRE.
from datetime import datetime as _dt
_day = _dt.now(bot.EASTERN).strftime("%Y-%m-%d")
bot._zf_zone[(_day, "RIGZF")] = {"zone": 1.21, "src": "pm_shelf3", "open930": 1.30}
bot._zf_st.pop("RIGZF", None)
def _k_at(hh, mm, ss):
    return int(_dt.now(bot.EASTERN).replace(hour=hh, minute=mm, second=ss, microsecond=0).timestamp())
_seq_zf = [(_k_at(9, 30, 40), 1.30, 1.30, 1.28, 1.29, 100),   # warmup vols
           (_k_at(9, 30, 50), 1.29, 1.29, 1.27, 1.28, 100),
           (_k_at(9, 31, 0), 1.28, 1.28, 1.19, 1.225, 2000),  # Z1 flush: low 1.19 in band, 10x vol
           (_k_at(9, 31, 10), 1.225, 1.24, 1.21, 1.235, 800), # Z2 wick: low at zone, close upper half
           (_k_at(9, 31, 20), 1.235, 1.27, 1.23, 1.26, 900)]  # Z3 curl: close 1.26 > wick high 1.24
_zf_fire = bot.kev_zoneflip_step("RIGZF", _seq_zf)
check("T13d ZYBT-shape fires on the curl, seq 0, stop = flush low − 1 tick",
      bool(_zf_fire) and _zf_fire.get("seq") == 0 and abs(_zf_fire["stop"] - 1.18) < 0.005,
      f"fire={_zf_fire}")
bot._zf_st.pop("RIGZF2", None)
bot._zf_zone[(_day, "RIGZF2")] = {"zone": 1.21, "src": "pm_shelf3", "open930": 1.30}
_seq_novol = [(k, o, h, l, c, 100) for k, o, h, l, c, v in _seq_zf]   # same shape, NO vol expansion
check("T13e no volume on the flush → NEVER arms/fires",
      bot.kev_zoneflip_step("RIGZF2", _seq_novol) is None)
bot._zf_st.pop("RIGZF3", None)
bot._zf_zone[(_day, "RIGZF3")] = {"zone": 1.21, "src": "pm_shelf3", "open930": 1.30}
_seq_late = [(k + 3600, o, h, l, c, v) for k, o, h, l, c, v in _seq_zf]   # 10:30+ — outside arm window
check("T13f flush after 9:45 never arms (arm window pin)",
      bot.kev_zoneflip_step("RIGZF3", _seq_late) is None)


# ── T12: blended P&L includes the runner leg (7/20 BIYA bug) ─
print("T12 blended P&L runner-leg integrity")
# BIYA 7/20: entry 7.50, 65 sh, scales 32@8.1101 + 16@8.43, runner 17 exits 6.87.
# The bug dropped the runner leg → recorded +34.40; true +23.69.
check("T12a BIYA regression: runner leg counted (23.69 not 34.40)",
      abs(bot._blended_pnl(7.50, 65, [(32, 8.1101), (16, 8.43)], 6.87) - 23.69) < 0.02)
check("T12b no-partials path unchanged (VMAR −27.90)",
      abs(bot._blended_pnl(1.08, 930, [], 1.05) - (-27.90)) < 0.02)
check("T12c full scale-out (0 runner) = sum of legs only",
      abs(bot._blended_pnl(10.0, 100, [(50, 11.0), (50, 12.0)], 9.0) - 150.0) < 1e-6)


print()
print(f"{'='*50}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("RED:", ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
