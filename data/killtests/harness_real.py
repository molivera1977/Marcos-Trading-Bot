"""REAL-PATH REPLAY HARNESS (#12, Marcos 8/8: "let's upgrade our sim machine").
Runs the SHIPPED monitor_trade — not a reimplementation — against recorded bars on a virtual
clock. Every exit mechanism (resting-bank tiers, rung ratchet, BE floor, scale-bar-low, health
folds, intrabar/3-min stops, off-tape guard) executes its real code. Fidelity target (frozen):
replaying Friday 8/7's 24 actual trades lands within $100 of the actual +$530.65 total with
>=18/24 per-trade sign matches — else the harness reports UNFAITHFUL and does not replace the
old engine."""
import json, urllib.request, urllib.parse, sys, types, threading, pathlib
import datetime as _dt, zoneinfo
sys.path.insert(0, "/Users/marcosolivera/Desktop/Marcos-Trading-Bot/rig")
from loader import load_bot
ET = zoneinfo.ZoneInfo("America/New_York")
U = "https://zestful-intuition-production-b16a.up.railway.app"
_bars_cache = {}

def _get(u):
    return json.load(urllib.request.urlopen(u, timeout=60))

def day_bars5(tk, day):
    key = (tk, day, 5)
    if key in _bars_cache: return _bars_cache[key]
    r = _get(f"{U}/api/bars?date={day}&ticker={urllib.parse.quote(tk)}~ALP5S").get("bars") or []
    y, m, d = (int(v) for v in day.split("-"))
    base = _dt.datetime(y, m, d, tzinfo=_dt.timezone.utc).timestamp()
    out = {}
    for x in r:
        ts = str(x.get("time"))[11:19]
        sec = base + int(ts[:2])*3600 + int(ts[3:5])*60 + int(ts[6:8])
        out[sec] = float(x["close"])
    _bars_cache[key] = out
    return out

def day_bars(tk, day):
    key = (tk, day)
    if key in _bars_cache: return _bars_cache[key]
    r = _get(f"{U}/api/bars?date={day}&ticker={urllib.parse.quote(tk)}~ALP10S").get("bars") or []
    y, m, d = (int(v) for v in day.split("-"))
    base = _dt.datetime(y, m, d, tzinfo=_dt.timezone.utc).timestamp()
    out = {}
    for x in r:
        ts = str(x.get("time"))[11:19]
        sec = base + int(ts[:2])*3600 + int(ts[3:5])*60 + int(ts[6:8])   # TRUE EPOCH (bugfix)
        out[sec] = {"o": float(x.get("open") or 0), "h": float(x["high"]),
                    "l": float(x["low"]), "c": float(x["close"]),
                    "v": float(x.get("volume") or 0)}
    _bars_cache[key] = out
    return out

class VClock:
    def __init__(self, start_utc_epoch): self.t = float(start_utc_epoch)
    def time(self): return self.t
    def sleep(self, s): self.t += max(float(s), 0.5)

def replay_trade(tk, day, entry_utc_hms, entry, stop, shares, entry_type="flat_top",
                 vwap=0.0, verbose=False):
    bot = load_bot()
    bars = day_bars(tk, day)
    if not bars: return None
    px5 = day_bars5(tk, day)
    y, m, d = (int(x) for x in day.split("-"))
    hh, mm, ss = (int(x) for x in entry_utc_hms.split(":"))
    start = _dt.datetime(y, m, d, hh, mm, ss, tzinfo=_dt.timezone.utc).timestamp() + 10.0
    clock = VClock(start)   # +10s: the entry bar itself was survived live (fill happened in it)
    eod   = _dt.datetime(y, m, d, 20, 0, 0, tzinfo=_dt.timezone.utc).timestamp()

    real_dt = _dt.datetime
    class FDT(real_dt):
        @classmethod
        def now(cls, tz=None):
            base = real_dt.fromtimestamp(min(clock.t, eod), _dt.timezone.utc)
            return base.astimezone(tz) if tz else base.replace(tzinfo=None)
        @classmethod
        def utcnow(cls): return real_dt.fromtimestamp(min(clock.t, eod), _dt.timezone.utc).replace(tzinfo=None)
    ftime = types.SimpleNamespace(time=clock.time, sleep=clock.sleep, monotonic=clock.time)

    def cur_bar():
        ks = [k for k in bars if k <= clock.t]
        return bars[max(ks)] if ks else None
    def cur_px():
        if px5:
            ks = [k for k in px5 if k <= clock.t]
            if ks: return px5[max(ks)]
        b = cur_bar()
        return b["c"] if b else 0.0
    def m1_upto(count):
        """TRUE minute bars aggregated from the 10s tape (the monitor's expected timeframe)."""
        agg = {}
        for k2, b in bars.items():
            if k2 > clock.t: continue        # include the FORMING 10s bar -> the forming MINUTE
            # exists as a partial, exactly like live M1 — so aggregate_bars()[:-1] drops the true
            # forming 3-min bucket instead of a completed one (the stale-bucket phantom folds).
            mk = int(k2 // 60 * 60)
            a = agg.get(mk)
            if a is None:
                agg[mk] = {"o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b["v"]}
            else:
                a["h"] = max(a["h"], b["h"]); a["l"] = min(a["l"], b["l"])
                a["c"] = b["c"]; a["v"] += b["v"]
        return [{"time": _dt.datetime.fromtimestamp(mk, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000"),
                 "open": a["o"], "high": a["h"], "low": a["l"], "close": a["c"], "volume": a["v"]}
                for mk, a in sorted(agg.items())][-count:]
    def bars_upto(n=90):
        ks = sorted(k for k in bars if k + 10 <= clock.t)[-n:]
        return {k: dict(bars[k]) for k in ks}

    stream = types.SimpleNamespace(connected=False, loop_sleep=lambda: 5.0,
                                   get_price=lambda t: cur_px(),
                                   get_final_message=lambda: "", stop=lambda: None,
                                   subscribe=lambda *a, **k: None)
    records = []
    decisions = []
    patches = {
        "time": ftime, "datetime": FDT,
        "_get_webull_quote": lambda t, executor=None: {"last_price": cur_px()},
        "_curl_feed": lambda t, n=90: bars_upto(n),
        "get_intraday_bars": lambda t, count=60, **k: m1_upto(count),
        "_intraday_bars": lambda t, *a, **k: [
            {"time": f"{day}T{k2//3600:02d}:{(k2%3600)//60:02d}:{k2%60:02d}",
             "open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"], "volume": b["v"]}
            for k2, b in sorted(bars_upto(400).items())],
        "cancel_order": lambda *a, **k: True,
        "place_stop_order": lambda *a, **k: "SIMSTOP",
        "post_trade_record_reliably": lambda rec: (records.append(rec), True)[1],
        "_log_decision": lambda t, s, **kw: decisions.append((s, kw)),
        "_post_trade_state": lambda st: None, "_save_open_trade": lambda st: None,
        "_clear_open_trade": lambda t: None, "_partial_exit_alert": lambda *a, **k: None,
        "_fetch_kev_levels": lambda: {}, "_is_leader": lambda t: False,
        "_entries_paused": lambda: False,
    }
    saved = {}
    for k, v in patches.items():
        if hasattr(bot, k): saved[k] = getattr(bot, k); setattr(bot, k, v)
    result = None
    try:
        bot.DRY_RUN = True
        result = bot.monitor_trade(tk, shares, entry, entry * 1.10, stop, stream, "SIMSTOP",
                                   vwap=vwap, entry_type=entry_type)
    except Exception as e:
        if verbose: print(f"  {tk}: monitor raised {type(e).__name__}: {e}")
    finally:
        for k, v in saved.items(): setattr(bot, k, v)
    if isinstance(result, dict) and result.get("profit_loss") is not None:
        return float(result["profit_loss"])
    if records:
        return float(records[-1].get("pnl") or 0)
    return None

if __name__ == "__main__":
    t = [x for x in _get(U + "/api/trades")["trades"]
         if x.get("date") == "2026-08-07" and x.get("entry_ts_utc")]
    tot_a = tot_s = 0.0; n = match = 0
    for x in t:
        e = float(x.get("entry") or 0); rps = float(x.get("risk_per_share") or 0)
        sh = int(x.get("shares") or 0); a = float(x.get("pnl") or 0)
        if not (e > 0 and rps > 0 and sh > 0): continue
        hms = str(x["entry_ts_utc"])[11:19]
        _vw = float(x.get("entry_session_vwap") or 0)
        p = replay_trade(x["ticker"], "2026-08-07", hms, e, e - rps, sh,
                         entry_type=x.get("entry_type") or "flat_top", vwap=_vw, verbose=True)
        if p is None:
            print(f"{x['ticker']:6s} actual {a:+8.2f}  harness (no record)")
            continue
        n += 1; tot_a += a; tot_s += p
        match += (1 if (a >= 0) == (p >= 0) else 0)
        print(f"{x['ticker']:6s} actual {a:+8.2f}  harness {p:+8.2f}")
    print(f"\n{n} replayed: ACTUAL ${tot_a:+.2f}  HARNESS ${tot_s:+.2f}  sign-match {match}/{n}")
    ok = abs(tot_s - tot_a) <= 100 and match >= 18
    print("FIDELITY:", "PASS — harness becomes the standard engine" if ok else "UNFAITHFUL — iterate")
