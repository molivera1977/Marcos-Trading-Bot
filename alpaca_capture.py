"""
Alpaca Parallel Capture — PHASE 0 of the vendor bake-off (built 2026-07-22, standalone).

WHY: Marcos 7/22 — "the evidence clearly shows we need to separate the two services."
vendor_desk_comparison.md is the evidence file: Webull kicks the recorder at ~40 subs under
RTH message rates (RTH_SUB_CAP=40, measured 7/16; 38 kicks on 7/20 = ~32% of RTH deaf) and
the 7/20 completeness canary measured median 0.52 capture. Alpaca claims unlimited symbols
on one websocket. Phase 0 = FREE-tier (IEX) plumbing + the symbol-cap probe: run the same
10s-bar + premarket-anchored-VWAP capture in PARALLEL with the Webull recorder so
vendor_test_grade.py can compare both feeds against official daily volume. Phase 1 = the
SIP completeness test when Marcos subscribes ($99/mo) — same code, ALPACA_FEED=sip.

ISOLATION (absolute): never imports marcos_trading_bot; zero trading logic; writes ONLY
TICKER~ALP10S / TICKER~ALPVWAP series so test data can never collide with the production
~10S/~VWAP series the bot gates on. A bug here can never touch the trading path.

DESIGN NOTES vs recorder.py (deliberately mirrored / deliberately different):
  mirrored : 10s bucketing, premarket-anchored VWAP, ~90s persist cadence, watermarks
             committed only on HTTP 200 (7/16 lesson: build-time advance loses windows on
             a dashboard blip), 60s VWAP snapshots (audit S3), session gate + supervisor
             backoff, SIGTERM final flush.
  different: Alpaca delivers PER-TRADE prints ({"T":"t","p":px,"s":size}) — real volume
             per trade, so bars sum sizes directly. No cumulative-counter carry (the whole
             F1 class of v0/v1 re-baseline bugs on recorder can't exist here), and VWAP is
             exact Σ(p*s)/Σ(s), no midpoint approximation needed.

Runs on its own Railway service (railway.alpacacap.toml). DO NOT point any bot code at
these series — Phase 0 is capture + grading only.
"""
import os, sys, time, json, signal, threading, gzip, re
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    EASTERN = ZoneInfo("America/New_York")
except Exception:
    EASTERN = timezone(timedelta(hours=-4))  # EDT fallback (mirrors recorder.py)

import requests

try:
    import websocket    # websocket-client (NOT the alpaca-py SDK — one tiny proven dep)
except Exception:       # requirements.txt doesn't carry it (checked 7/22); the service toml
    websocket = None    # pip-installs it at boot — see ALPACA_CAPTURE_REQUIREMENTS_NOTE.md

# ── config (env) ─────────────────────────────────────────────────────────────
ALPACA_KEY    = os.environ.get("ALPACA_KEY", "")
ALPACA_SECRET = os.environ.get("ALPACA_SECRET", "")
ALPACA_FEED   = os.environ.get("ALPACA_FEED", "iex")        # "iex" free tier; "sip" = Phase 1 paid test
SYMBOL_CAP    = int(os.environ.get("SYMBOL_CAP", "150"))    # deliberately ABOVE Webull's 40 — the probe point
_cap_eff      = [SYMBOL_CAP]  # EFFECTIVE cap — a 405 symbol-limit frame trims this instead of
                              # reconnect-looping (Phase 0 on the free tier burned cycles that way);
                              # SIP never 405s, so on Phase 1+ this stays == SYMBOL_CAP
SILENCE_SECS  = 90 if ALPACA_FEED == "sip" else 180   # feed-aware zombie fuse: SIP with a full book
                              # quiet 90s IS a dead socket; IEX premarket is honestly thin — err wide
SYMBOL_PROBE  = os.environ.get("SYMBOL_PROBE", "0") == "1"  # 1 → pad roster with top actives to SYMBOL_CAP
DASH_URL      = os.environ.get("SCREENER_URL", "").rstrip("/")
DASH_SECRET   = os.environ.get("DASHBOARD_SECRET", "marcos2026")

WS_URL        = "wss://stream.data.alpaca.markets/v2/" + ALPACA_FEED
PERSIST_SECS  = 90        # same cadence the recorder settled on 7/16 (freshness vs egress)
ROSTER_SECS   = 300       # roster mirror every 5 min (watching + kev union)
HEALTH_SECS   = 300       # MANDATORY kick-evidence line every 5 min
SNAP_SECS     = 60        # VWAP series point cadence (audit S3: 5-min was too coarse to certify)
SESSION_START_ET = (4, 0)   # Alpaca has no 3:25 warmup need — trades only exist from the 4:00 open
SESSION_END_ET   = (20, 0)

def et_now(): return datetime.now(EASTERN)
def log(m):   print("[%s ALP] %s" % (et_now().strftime("%H:%M:%S"), m), flush=True)

# ── shared state ─────────────────────────────────────────────────────────────
_lock = threading.Lock()
_bars = {}          # sym -> {bucket_epoch: {o,h,l,c,v}}   (10s only — the comparison unit)
_vwap = {}          # sym -> {"num":Σp*s, "den":Σs, "series":[(ts,vwap)]} — anchored at the 4:00
                    # premarket open by construction: state resets at day roll, every trade counts
_subscribed = set()
_stop = threading.Event()

# kick-test evidence counters (the POINT of Phase 0 — count them, don't vibe them)
_disconnects = [0]          # every socket death since boot
_disc_t0     = [0.0]        # when the current outage began (0 = connected)
_msg_n       = [0]          # frames since last health line
_last_trade  = [0.0]        # tick-liveness stamp (silent-zombie fuse, recorder 7/16 lesson)

def _t_epoch(tstr):
    """Alpaca RFC-3339 trade stamp ('2026-07-22T13:35:01.123456789Z') → epoch seconds.
    Bucket on the EXCHANGE stamp, not arrival time — comparison vs Webull bars must not
    smear trades across buckets by transit delay. Falls back to now() on parse failure."""
    try:
        base = datetime.strptime(tstr[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
        m = re.match(r"\.(\d+)", tstr[19:])
        return base + (float("0." + m.group(1)) if m else 0.0)
    except Exception:
        return time.time()

def ingest(sym, price, size, ts):
    try:
        _last_trade[0] = time.time()
        k = int(ts) // 10 * 10                     # identical bucketing to recorder/B12
        with _lock:
            d = _bars.setdefault(sym, {})
            b = d.get(k)
            if b is None:
                d[k] = {"o": price, "h": price, "l": price, "c": price, "v": size}
            else:
                if price > b["h"]: b["h"] = price
                if price < b["l"]: b["l"] = price
                b["c"] = price
                b["v"] += size
            # exact trade-weighted VWAP — every print carries its own size (no counter math)
            v = _vwap.setdefault(sym, {"num": 0.0, "den": 0.0, "series": []})
            v["num"] += price * size
            v["den"] += size
    except Exception:
        pass                                       # a bad print never breaks the feed

# ── roster mirror (watching ∪ kev picks, + top actives in probe mode) ────────
def _get_json(path, timeout=10):
    try:
        r = requests.get(DASH_URL + path, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def roster_targets():
    """Union of the bot's live watchlist + Kev's picks for today, capped at SYMBOL_CAP.
    Order matters under the cap: Kev picks FIRST (the names we owe complete tape on —
    same priority the recorder's carryover_seed settled 7/16), then the bot's watchlist,
    then (probe mode) today's top actives to fill the cap."""
    today = et_now().strftime("%Y-%m-%d")
    out, seen = [], set()
    def add(names):
        for n in names or []:
            u = str(n).upper().strip()
            if u and u not in seen and not u.startswith("ZZ"):   # never the ZZ* sentinels (7/17 lesson)
                seen.add(u); out.append(u)
    d = _get_json("/api/kev_watchlist?date=" + today)
    if isinstance(d, dict): add(d.get("tickers"))
    d = _get_json("/api/watching?date=" + today)
    if isinstance(d, dict): add(d.get("tickers"))
    if SYMBOL_PROBE:
        add(_actives["names"])                     # cached ranking; refreshed in background
    return out[:_cap_eff[0]]

_actives = {"ts": 0.0, "names": [], "busy": False}
def _refresh_actives_bg():
    """PROBE mode: rank today's archived ~10S names by summed volume and cache them (30-min
    TTL). Runs in a background thread — up to ~100 series fetches at 0.15s pace must never
    starve the websocket recv loop. This padding is what pushes subs toward SYMBOL_CAP so
    RTH message rates directly test Alpaca's 'unlimited symbols' claim vs Webull's ~40 kick."""
    if _actives["busy"] or time.time() - _actives["ts"] < 1800:
        return
    _actives["busy"] = True
    def _work():
        try:
            today = et_now().strftime("%Y-%m-%d")
            d = _get_json("/api/bars", timeout=20) or {}
            names = [n for n in (d.get("archived", {}).get(today) or [])
                     if isinstance(n, str) and n.upper().endswith("~10S")
                     and not n.upper().startswith("ZZ") and "~ALP" not in n.upper()]
            ranked = []
            for n in names[:120]:                  # bounded: gentle on the dashboard
                if _stop.is_set(): return
                b = _get_json("/api/bars?date=%s&ticker=%s" % (today, n), timeout=15)
                try:
                    vol = sum(float(x.get("volume") or 0) for x in (b or {}).get("bars", []))
                except Exception:
                    vol = 0.0
                ranked.append((vol, n[:-4].upper()))
                time.sleep(0.15)
            ranked.sort(reverse=True)
            _actives["names"] = [s for _, s in ranked]
            _actives["ts"] = time.time()
            log("PROBE actives refreshed: %d names ranked by archived volume (top: %s)"
                % (len(ranked), [s for _, s in ranked[:5]]))
        except Exception as e:
            log("PROBE actives refresh failed: %s" % e)
        finally:
            _actives["busy"] = False
    threading.Thread(target=_work, daemon=True).start()

def sync_roster(ws):
    """Diff target vs current subs; subscribe/unsubscribe only the delta (Alpaca applies
    deltas server-side; re-sending the world is wasted frames)."""
    target = set(roster_targets())
    if not target and not _subscribed:
        return
    new  = sorted(target - _subscribed)
    gone = sorted(_subscribed - target)
    try:
        if new:
            ws.send(json.dumps({"action": "subscribe", "trades": new}))
            _subscribed.update(new)
        if gone:
            ws.send(json.dumps({"action": "unsubscribe", "trades": gone}))
            _subscribed.difference_update(gone)
        if new or gone:
            log("roster: +%d -%d (total %d/%d%s)" % (len(new), len(gone), len(_subscribed),
                SYMBOL_CAP, ", PROBE" if SYMBOL_PROBE else ""))
    except Exception as e:
        log("roster sync send failed: %s" % e)
        raise                                      # a dead socket must reach the supervisor

# ── persistence (mirrors recorder.persist: gzip bars_bulk, watermark-on-200) ─
_shipped    = {}    # sym -> last bar bucket persisted
_vw_shipped = {}    # sym -> last vwap-series ts persisted

def build_payload(final=False):
    """Incremental: only CLOSED buckets newer than the last shipped one (recorder 7/16:
    whole-day re-sends blew ~2GB/day egress). Watermarks are RETURNED, not advanced here —
    persist() commits them only on HTTP 200 so a dashboard blip never skips a window.
    No BUCKET_FLOOR here: the comparison needs EVERY name, thin tape included."""
    cutoff = time.time() if final else (int(time.time()) // 10 * 10)
    series, marks10, marksvw = {}, {}, {}
    with _lock:
        snap10 = {}
        for t, bk in _bars.items():
            lo = _shipped.get(t, -1)
            items = sorted((k, b) for k, b in bk.items() if k > lo and (final or k + 10 <= cutoff))
            if items:
                snap10[t] = items
                marks10[t] = items[-1][0]
        vwseries = {}
        for t, v in _vwap.items():
            lo = _vw_shipped.get(t, -1.0)
            pts = [(ts, vw) for ts, vw in v["series"] if ts > lo]
            if pts:
                vwseries[t] = pts
                marksvw[t] = pts[-1][0]
    for t, items in snap10.items():
        # ~ALP10S / ~ALPVWAP ONLY — never bare ticker, never the production ~10S/~VWAP names
        series["%s~ALP10S" % t] = [
            {"time": datetime.fromtimestamp(k, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
             "open": str(b["o"]), "high": str(b["h"]), "low": str(b["l"]), "close": str(b["c"]),
             "volume": str(int(b["v"]))}
            for k, b in items]
    for t, ser in vwseries.items():
        series["%s~ALPVWAP" % t] = [
            {"time": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
             "close": str(round(vw, 6)), "open": str(round(vw, 6)), "high": str(round(vw, 6)),
             "low": str(round(vw, 6)), "volume": "0"}
            for ts, vw in ser]
    return {"date": et_now().strftime("%Y-%m-%d"), "series": series,
            "source": "alpaca_capture"}, (marks10, marksvw)

def persist(reason="periodic", final=False):
    try:
        if not DASH_URL: return False
        pl, marks = build_payload(final=final)
        if not pl["series"]: return False
        pl["reason"] = reason
        body = gzip.compress(json.dumps(pl).encode(), compresslevel=1)
        r = requests.post(DASH_URL + "/api/bars_bulk", data=body, timeout=15,
                          headers={"X-Dashboard-Secret": DASH_SECRET, "Content-Encoding": "gzip",
                                   "Content-Type": "application/json"})
        ok = r.status_code == 200
        if ok:
            with _lock:               # commit watermarks only on confirmed store write
                _shipped.update(marks[0])
                _vw_shipped.update(marks[1])
        log("persist(%s): %d series -> %d" % (reason, len(pl["series"]), r.status_code))
        return ok
    except Exception as e:
        log("persist failed: %s" % e)
        return False

def snapshot_vwap():
    ts = time.time()
    with _lock:
        for sym, v in _vwap.items():
            if v["den"] > 0:
                v["series"].append((ts, v["num"] / v["den"]))

def health_line():
    """MANDATORY 5-min kick-evidence line — this counter IS the Phase-0 deliverable:
    does Alpaca survive RTH message rates at >40 symbols where Webull kicked?"""
    mins = HEALTH_SECS / 60.0
    log("ALP-health: %d disconnects, %d msgs/min, %d symbols (feed=%s, cap=%d%s)"
        % (_disconnects[0], int(_msg_n[0] / mins), len(_subscribed), ALPACA_FEED,
           SYMBOL_CAP, ", PROBE" if SYMBOL_PROBE else ""))
    _msg_n[0] = 0

# ── websocket (websocket-client, synchronous — one loop, no callback threads) ─
def connect_and_auth():
    """Connect + handshake. Alpaca sends [{"T":"success","msg":"connected"}] first, we send
    {"action":"auth",...}, then expect [{"T":"success","msg":"authenticated"}]. Error frames
    ({"T":"error","code":...}) abort — 402 bad creds, 406 connection limit (one live socket
    per key!), 409 insufficient subscription. NEVER log the key/secret themselves."""
    ws = websocket.create_connection(WS_URL, timeout=15)
    try:
        deadline = time.time() + 20
        sent_auth, authed = False, False
        while time.time() < deadline and not authed:
            frames = json.loads(ws.recv())
            for f in (frames if isinstance(frames, list) else [frames]):
                T = f.get("T")
                if T == "error":
                    raise RuntimeError("alpaca error %s: %s" % (f.get("code"), f.get("msg")))
                if T == "success" and f.get("msg") == "connected" and not sent_auth:
                    ws.send(json.dumps({"action": "auth", "key": ALPACA_KEY, "secret": ALPACA_SECRET}))
                    sent_auth = True
                elif T == "success" and f.get("msg") == "authenticated":
                    authed = True
        if not authed:
            raise RuntimeError("auth handshake timed out")
    except Exception:
        try: ws.close()
        except Exception: pass
        raise
    ws.settimeout(5)          # recv doubles as the chore heartbeat — 5s beats between chores
    if _disc_t0[0]:
        log("reconnected after %.0fs down (disconnect #%d)" % (time.time() - _disc_t0[0], _disconnects[0]))
        _disc_t0[0] = 0.0
    log("stream connected + authenticated (feed=%s)" % ALPACA_FEED)
    return ws

def handle_frames(raw):
    try:
        frames = json.loads(raw)
    except Exception:
        return
    for f in (frames if isinstance(frames, list) else [frames]):
        _msg_n[0] += 1
        T = f.get("T")
        if T == "t":                                     # trade print — the whole point
            try:
                sym = str(f.get("S", "")).upper()
                p, s = float(f.get("p") or 0), float(f.get("s") or 0)
                if sym and p > 0 and s > 0:
                    ingest(sym, p, s, _t_epoch(str(f.get("t") or "")))
            except Exception:
                pass
        elif T == "subscription":                        # server-truth sub count (probe evidence)
            _truth = {str(s).upper() for s in (f.get("trades") or [])}
            log("server ack: %d trade subs" % len(_truth))
            # reconcile: our set is updated optimistically at send time; a rejected subscribe
            # (405) leaves it inflated. Server ack is truth — next sync_roster diffs off THIS.
            _subscribed.clear(); _subscribed.update(_truth)
        elif T == "error":
            # mid-session error frame (e.g. 405 symbol limit, 406 conn limit) = probe FINDING
            log("ALPACA ERROR frame: code=%s msg=%s" % (f.get("code"), f.get("msg")))
            if str(f.get("code")) == "405" and _cap_eff[0] > 25:
                # symbol limit: trim the effective cap below what we just tried and keep the
                # session — reconnect-looping on 405 re-hits the same wall (Phase 0 evidence)
                _cap_eff[0] = max(25, min(_cap_eff[0], len(_subscribed) if _subscribed else _cap_eff[0]) - 5)
                log("405 symbol-limit: effective cap trimmed to %d — no reconnect" % _cap_eff[0])
            else:
                raise RuntimeError("alpaca error frame %s" % f.get("code"))

def in_session(now=None):
    now = now or et_now()
    return (now.weekday() < 5
            and SESSION_START_ET <= (now.hour, now.minute) < SESSION_END_ET)

# ── lifecycle ────────────────────────────────────────────────────────────────
def run_session():
    """One capture stretch: connect → roster → recv/chore loop → flush. Errors bubble to
    the supervisor (backoff + disconnect counting). Mirrors recorder.run_session shape."""
    ws = connect_and_auth()
    try:
        if SYMBOL_PROBE: _refresh_actives_bg()
        sync_roster(ws)
        _last_trade[0] = time.time()
        last_roster = time.time()
        last_persist = last_snap = last_health = 0.0
        while not _stop.is_set():
            if not in_session():
                log("session end — final flush")
                snapshot_vwap(); persist("session_end", final=True)
                break
            try:
                handle_frames(ws.recv())
            except websocket.WebSocketTimeoutException:
                pass                                     # quiet 5s — chores below still run
            t = time.time()
            # silent-zombie fuse (recorder 7/16: stream died silently at the open, 45-min zombie).
            # Feed-aware (SILENCE_SECS): SIP 90s, IEX 180s — IEX premarket tape is honestly thin.
            if _last_trade[0] and _subscribed and t - _last_trade[0] > SILENCE_SECS:
                log("TICK SILENCE %.0fs with %d subs (fuse %ds, feed=%s) — presuming dead socket, forcing reconnect"
                    % (t - _last_trade[0], len(_subscribed), SILENCE_SECS, ALPACA_FEED))
                snapshot_vwap(); persist("silence_flush")
                raise RuntimeError("tick silence >%ds" % SILENCE_SECS)
            if t - last_roster >= ROSTER_SECS:
                if SYMBOL_PROBE: _refresh_actives_bg()
                try: sync_roster(ws)
                except Exception: raise
                last_roster = t
            if t - last_snap >= SNAP_SECS:
                snapshot_vwap(); last_snap = t
            if t - last_persist >= PERSIST_SECS:
                snapshot_vwap(); persist("periodic"); last_persist = t
            if t - last_health >= HEALTH_SECS:
                health_line(); last_health = t
    finally:
        try: ws.close()                                  # no half-dead sockets left behind
        except Exception: pass

def _reset_day():
    with _lock:
        _bars.clear(); _vwap.clear(); _shipped.clear(); _vw_shipped.clear()
    _subscribed.clear()
    _actives["ts"] = 0.0; _actives["names"] = []

def _on_sigterm(signum, frame):
    log("SIGTERM — final flush")
    try: snapshot_vwap(); persist("sigterm", final=True)
    except Exception: pass
    _stop.set()
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    os.kill(os.getpid(), signal.SIGTERM)

def main():
    # HARD-FAIL on missing plumbing (recorder pattern): capture that can't stream or persist
    # is silent worthlessness. Names only in the log — never the values.
    missing = [n for n, v in (("ALPACA_KEY", ALPACA_KEY), ("ALPACA_SECRET", ALPACA_SECRET),
                              ("SCREENER_URL", DASH_URL)) if not v]
    if missing:
        log("FATAL: missing env %s — refusing to run a capture that can't stream+persist" % missing)
        sys.exit(1)
    if websocket is None:
        log("FATAL: websocket-client not installed (pip install websocket-client==1.8.0; "
            "see ALPACA_CAPTURE_REQUIREMENTS_NOTE.md)")
        sys.exit(1)
    try: signal.signal(signal.SIGTERM, _on_sigterm)
    except Exception: pass
    log("alpaca_capture up — gate %02d:%02d-%02d:%02d ET weekdays, feed=%s cap=%d probe=%s"
        % (SESSION_START_ET[0], SESSION_START_ET[1], SESSION_END_ET[0], SESSION_END_ET[1],
           ALPACA_FEED, SYMBOL_CAP, SYMBOL_PROBE))
    backoff = 10
    while not _stop.is_set():
        if in_session():
            try:
                run_session()                            # returns at 20:00 (or raises)
                backoff = 10
                _reset_day()
                log("day complete — state reset, sleeping until next gate")
            except Exception as e:
                # EVERY socket death is Phase-0 evidence: count it, stamp the outage start,
                # persist what we hold, and come back with bounded backoff. Compare this
                # counter against Webull's kick log for the same day (grader reminds you).
                _disconnects[0] += 1
                if not _disc_t0[0]: _disc_t0[0] = time.time()
                log("DISCONNECT #%d: %s — reconnect in %ds" % (_disconnects[0], e, backoff))
                snapshot_vwap(); persist("error_flush")
                _stop.wait(backoff)
                backoff = min(backoff * 2, 60)
        else:
            _stop.wait(60)                               # outside the gate: idle cheaply
    log("alpaca_capture stopped")

if __name__ == "__main__":
    main()
