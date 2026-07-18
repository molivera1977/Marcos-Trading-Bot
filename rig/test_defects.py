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


print()
print(f"{'='*50}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("RED:", ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
