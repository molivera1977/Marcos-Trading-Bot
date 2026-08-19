#!/usr/bin/env python3
"""
MA_PULLBACK DRIVER — the bot's own detector, driven correctly, with a SELF-TEST that proves it (8/19)

Marcos: "fix the driver."

WHY THIS EXISTS
  `detect_ma_pullback` became liftable on 8/18 (rig gate 17) after being unregistered — and
  therefore untestable — for its whole life. The first smoke test produced ZERO fires over 40
  name-days, which I flagged as "the signature of a bad harness call, not selectivity." It was.
  TWO bugs, both mine:
    1. I fed 1-MINUTE bars. The live call site (marcos_trading_bot.py:10790, :10819) builds
       `completed = aggregate_bars(cache[t]["full_bars"], SETUP_TF_MIN)[:-1]` — THREE-minute
       completed bars.
    2. I did not dedupe. The pure function deliberately returns the SAME fire on every scan pass
       while its confirmation candle is the last completed bar ("the caller dedupes on this key",
       source comment at the return). Undeduped it emitted 166 repeats on one name-day, which
       reads like noise.

THE SELF-TEST IS THE POINT
  A driver that runs is not a driver that works. `selftest()` asserts this driver reproduces the
  two KNOWN LIVE FIRES of 2026-08-18 on the SAME confirmation-candle epoch:
      CDTG 14:16:43  -> k=1787076720 (3-min candle ending 14:12:00), held ema9
      PFSA 14:38:49  -> k=1787077980 (3-min candle ending 14:33:00), held ema9
  The driver detects each ~60s EARLIER than the live bot because it evaluates every 10s bar while
  the live loop scans on a slower cadence. Same candle, same held MA (within 0.1% of the live
  entry_ema9 stamps: 5.5625 vs 5.5678, 14.8861 vs 14.8803) — a sampling difference, not a
  disagreement. Any study importing this MUST call selftest() first.

WHAT THIS DRIVER IS NOT
  Detector-only. It does NOT model the live funnel: PULLBACK_FIRST, `vwap > 0 and price > vwap`,
  the chart gate, day-gain/momentum checks, slots, capital, or MA_PULLBACK_DEDUPE. Fire counts
  here exceed what the bot can take. It answers "when did the DETECTOR say yes", nothing more.

  Warm-up seed: the live path passes prior-session 3-min closes (MA_WARMUP_SEED). This driver
  passes [] and requires >=25 completed bars instead, so it cannot speak to the first ~75 minutes
  of a session the way the live bot can. Stated, not hidden.

THE QUESTION THIS UNBLOCKS (deliberately NOT answered here)
  ma_pullback fires on vertical expansion bars with no pullback at all
  (data/audits/DEFECT_20260819_ma_pullback_no_pullback.md). CDTG bought $7.78 at +40% above the
  9-EMA and LOST $26.76; PFSA bought $17.55 at +18% above it and WON $48.76. So a naive extension
  ceiling would have killed the day's second-best trade to prevent its third-worst. Whether ANY
  separator splits winners from losers is now measurable. It is not measured yet, and no
  threshold may be proposed until it is.
"""
import datetime
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ET = datetime.timezone(datetime.timedelta(hours=-4))
_H = None


def _harness():
    global _H
    if _H is None:
        sp = importlib.util.spec_from_file_location("H", os.path.join(HERE, "live_harness.py"))
        _H = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(_H)
    return _H


def _et(t):
    return datetime.datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=datetime.timezone.utc).astimezone(ET)


def fires(sym, day, bars=None, open_hms="09:30:00", close_hms="16:00:00", min_bars=25):
    """Distinct ma_pullback fires for one name-day, deduped on the confirmation candle.

    Returns [{hms, price, k, ma_name, ma, stop}, ...] — one entry per confirmation candle, at the
    FIRST 10s bar on which the detector said yes."""
    H = _harness()
    mp, agg = H.fn("detect_ma_pullback"), H.fn("aggregate_bars")
    TF = H.const("SETUP_TF_MIN")
    if bars is None:
        p = os.path.join(HERE, "..", "universe", "bars10s", f"{day}_{sym}.json")
        if not os.path.exists(p):
            return []
        bars = json.load(open(p))["bars"]
    raw = [{"time": x["time"], "open": x["open"], "high": x["high"], "low": x["low"],
            "close": x["close"], "volume": x["volume"]} for x in bars]
    H.set_replay_day(day)
    # 8/19 PERF: the original rebuilt the WHOLE 3-min aggregate at every 10s bar — O(n^2), and
    # measured at ~16s/name-day = ~254 min over the 948-name-day cache. The aggregate only
    # changes once per TF (every 18 bars at TF=3), so it is computed ONCE here and sliced.
    # Identical inputs to the detector; selftest() is what proves that, and it still passes.
    full3 = agg(raw, TF)
    _ep = H.fn("_bar_epoch")
    _ends = [_ep(b) for b in full3]          # each 3-min bar's own epoch key

    def _completed_upto(ts):
        """the [:-1] slice the live site uses: bars whose period has fully closed by `ts`"""
        n = 0
        for e in _ends:
            if e <= ts:
                n += 1
            else:
                break
        return full3[:max(n - 1, 0)]

    seen, out = set(), []
    for i in range(60, len(raw)):
        hms = _et(raw[i]["time"]).strftime("%H:%M:%S")
        if not (open_hms <= hms < close_hms):
            continue
        comp = _completed_upto(int(_et(raw[i]["time"]).timestamp()))
        if len(comp) < min_bars:
            continue
        try:
            r = mp(comp, raw[i]["close"], [])
        except Exception:
            continue
        if not r or r.get("k") in seen:
            continue
        seen.add(r["k"])
        out.append({"hms": hms, "price": raw[i]["close"], "k": r["k"],
                    "ma_name": r.get("ma_name"), "ma": r.get("ma"), "stop": r.get("stop"),
                    "i": i})
    return out


KNOWN = [("CDTG", "2026-08-18", 1787076720, "ema9", 5.5678),
         ("PFSA", "2026-08-18", 1787077980, "ema9", 14.8803)]


def selftest(verbose=True):
    """Assert the driver reproduces the two known live fires on the SAME confirmation candle.
    Returns True/False. A study that skips this is grading its own bug."""
    ok = True
    for sym, day, want_k, want_ma, live_ema in KNOWN:
        f = fires(sym, day)
        hit = [x for x in f if x["k"] == want_k]
        good = bool(hit) and hit[0]["ma_name"] == want_ma
        drift = (abs(hit[0]["ma"] - live_ema) / live_ema * 100) if hit else None
        if verbose:
            if hit:
                print(f"  {sym} {day}: k={want_k} REPRODUCED at {hit[0]['hms']} "
                      f"${hit[0]['price']:.2f} held {hit[0]['ma_name']}@{hit[0]['ma']} "
                      f"(live stamp {live_ema}, {drift:.2f}% apart)  {'OK' if good else 'MA MISMATCH'}")
            else:
                print(f"  {sym} {day}: k={want_k} NOT REPRODUCED — driver is broken, "
                      f"{len(f)} other fires found")
        ok = ok and good and (drift is not None and drift < 1.0)
    return ok


if __name__ == "__main__":
    import sys
    print("MA_PULLBACK DRIVER SELF-TEST — must reproduce the 8/18 live fires")
    print("=" * 78)
    r = selftest()
    print("=" * 78)
    print("DRIVER OK — safe for studies" if r else "DRIVER BROKEN — do not grade anything with it")
    sys.exit(0 if r else 1)
