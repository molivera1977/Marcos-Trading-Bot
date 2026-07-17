"""
Tick Recorder — isolated always-early data-capture service (built 2026-07-15, Opus).

WHY: the trading bot boots at 8:45am and misses 4am–8:45 PREMARKET ticks, and its
in-memory 10s collection dies on every deploy. Morning-gapper VWAP is 84–89%
premarket-weighted, so accurate VWAP REQUIRES premarket ticks captured live.

WHAT: a separate Railway service (own process, isolated from the bot) that starts
~3:30am ET (warmup margin before the 4:00am premarket open), streams a broad,
continuously-refreshed universe of the day's movers, builds 10s/60s bars + a
running snapshot-VWAP, and ships everything to the dashboard's durable store every
few minutes + on shutdown. Runs to 8:00pm ET, then exits.

ISOLATION: no trading logic, READ-ONLY w.r.t. trades, fail-silent everywhere — a
bug here can never touch the trading bot. Reuses the bot's PROVEN streaming +
ingestion patterns (WebullStream / _shadow_ingest / scan_morning_gappers) as
standalone code so it does not import the trading module.

START_APP=recorder.py on its own Railway service, cron ~3:30am ET weekdays.
"""
import os, sys, time, json, signal, threading, pathlib, gzip
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    EASTERN = ZoneInfo("America/New_York")
except Exception:
    EASTERN = timezone(timedelta(hours=-4))  # EDT fallback

import requests

# ── config (env) ─────────────────────────────────────────────────────────────
APP_KEY   = os.environ.get("WEBULL_APP_KEY", "")
APP_SECRET= os.environ.get("WEBULL_APP_SECRET", "")
TOKEN     = os.environ.get("WEBULL_ACCESS_TOKEN", "")
DASH_URL  = os.environ.get("SCREENER_URL", "").rstrip("/")
DASH_SECRET = os.environ.get("DASHBOARD_SECRET", "marcos2026")
TOKEN_DIR = os.environ.get("RECORDER_TOKEN_DIR", "/tmp/recorder_webull_token")

# universe / timing
PRICE_MIN, PRICE_MAX = 0.30, 20.0        # Kev realm (a touch wider than the bot to over-capture)
MAX_SUBSCRIBE   = 98                      # Webull hard cap measured 7/16: 100/session
RTH_SUB_CAP     = 40                      # 7/16: Webull kicks session-2 repeatedly at RTH message rates with
                                          # ~98 subs (3 kicks: 9:31/10:31/10:46). Premarket (the irreplaceable
                                          # mission) runs full-width; RTH runs top-priority only — the bot's own
                                          # shadow covers its watched names during RTH anyway (merge unions).
RESCAN_SECS     = 180                     # add fresh movers every 3 min
PERSIST_SECS    = 90                      # ship to durable store every 90s (7/16: the BOT now gates on
                                          # the store's ~vwap points — at 300s cadence the newest point
                                          # averaged ~150-300s old and failed the bot's freshness guard
                                          # half the time; incremental payloads keep this cheap)
SESSION_END_ET  = (20, 0)                 # 8:00pm ET → exit
BUCKET_FLOOR    = 20                      # keep even lightly-streamed names (premarket is thin) — over-capture

def et_now(): return datetime.now(EASTERN)
def log(m):   print(f"[{et_now().strftime('%H:%M:%S')} REC] {m}", flush=True)

# ── shared state ─────────────────────────────────────────────────────────────
_PROC_T0 = time.time()          # process boot stamp — never-ticked dead-man arm (review F2)

class InvalidSessionError(RuntimeError):
    """Webull rejected our streaming session (417 INVALID_SESSION) — cycle the session NOW
    instead of burning 90s waiting for the tick-silence watchdog (review F3)."""

_lock = threading.Lock()
_bars = {10: {}, 60: {}}                  # span -> sym -> {bucket_epoch: {o,h,l,c,v0,v1}}
_vwap = {}                                # sym -> {"num":Σpx*Δvol, "den":Σvol, "last_cumvol":x, "series":[(ts,vwap)]}
_subscribed = set()
_stop = threading.Event()

# ── ingestion (mirrors the bot's proven _shadow_ingest + adds snapshot-VWAP) ──
_last_ingest = [0.0]    # tick-liveness stamp (7/16: stream died silently at 9:31 open — zombie 45 min)
_last_real_ingest = [0.0]  # 7/16: REAL-tick-only stamp — NOT reset on connect (unlike _last_ingest); powers the dead-man's switch
def ingest(sym, price, cumvol, ts):
    try:
        _last_ingest[0] = ts
        _last_real_ingest[0] = ts
        # 10s / 60s OHLC bars (identical bucketing to the bot's B12)
        for span in (10, 60):
            k = int(ts) // span * span
            with _lock:
                d = _bars[span].setdefault(sym, {})
                b = d.get(k)
                if b is None:
                    d[k] = {"o": price, "h": price, "l": price, "c": price, "v0": cumvol, "v1": cumvol}
                else:
                    if price > b["h"]: b["h"] = price
                    if price < b["l"]: b["l"] = price
                    b["c"] = price
                    if cumvol is not None: b["v1"] = cumvol
        # snapshot-VWAP: accumulate price × Δ(cumulative volume). Complete volume via cumvol,
        # frequent price via snapshots → far finer than 1-min bars, matches the chart's line.
        if cumvol is not None:
            with _lock:
                v = _vwap.setdefault(sym, {"num": 0.0, "den": 0.0, "last_cumvol": None, "series": []})
                lc = v["last_cumvol"]
                if lc is None:
                    v["last_cumvol"] = cumvol            # first snapshot: set baseline, no volume yet
                elif cumvol >= lc:
                    dvol = cumvol - lc
                    if dvol > 0:
                        v["num"] += price * dvol
                        v["den"] += dvol
                    v["last_cumvol"] = cumvol
                else:
                    # cumvol decreased = session/counter reset (e.g. PRE→RTH). Re-baseline, don't
                    # subtract. (Whether the chart treats PRE+RTH as one cumulative line validates
                    # tomorrow against a screenshot; capture is safe either way.)
                    v["last_cumvol"] = cumvol
    except Exception:
        pass                                            # a bad message never breaks the feed

def cur_vwap(sym):
    v = _vwap.get(sym)
    if v and v["den"] > 0: return v["num"] / v["den"]
    return None

# ── premarket / movers scan (standalone; mirrors scan_morning_gappers) ───────
_data_client = None
def data_client():
    global _data_client
    if _data_client is not None: return _data_client
    try:
        from webull.core.client import ApiClient
        from webull.data.data_client import DataClient
        td = pathlib.Path(TOKEN_DIR); td.mkdir(parents=True, exist_ok=True)
        if TOKEN:
            (td / "token.txt").write_text(TOKEN + "\n" + str(int(time.time()*1000)+14*24*3600*1000) + "\nNORMAL\n")
        api = ApiClient(APP_KEY, APP_SECRET, "us", token_check_duration_seconds=60, token_check_interval_seconds=5)
        api.set_token_dir(str(td)); api.add_endpoint("us", "api.webull.com")
        _data_client = DataClient(api)
    except Exception as e:
        log(f"data client init failed: {e}")
        _data_client = None
    return _data_client

def scan_movers():
    """Broad gapper/mover universe: premarket gainers pre-open, live gainers after. Returns symbol set."""
    dc = data_client()
    if not dc: return set()
    syms = set()
    now = et_now()
    market_open = now.hour > 9 or (now.hour == 9 and now.minute >= 30)
    rank = "DAY_1" if market_open else "PRE_MARKET"
    try:
        res = dc.screener.get_gainers_losers(rank_type=rank, category="US_STOCK",
                                             sort_by="CHANGE_RATIO", direction="DESC", page_size=100)
        if res.status_code == 200:
            raw = res.json(); items = raw if isinstance(raw, list) else raw.get("data", raw.get("items", []))
            for it in items:
                s = it.get("symbol", ""); p = float(it.get("price") or it.get("close") or 0)
                if s and PRICE_MIN <= p <= PRICE_MAX: syms.add(s.upper())
    except Exception as e:
        log(f"scan error: {e}")
    return syms

def carryover_seed():
    """PRIORITY-ORDERED seed for premarket tick-1 (order matters: chunked subscribes under a cap
    mean earlier = guaranteed). 7/16 design discussion with Marcos:
      1. Kev's overnight watchlist  — highest hit-rate, the names we owe complete tape on
      2. AFTER-HOURS gappers        — last evening's 4-8pm movers = the likeliest 4am movers
      3. yesterday's collected movers (~10s archive) — day-2 continuation candidates (Kev's core lane)
    Everything unknowable overnight is caught by the 3-min PRE_MARKET rescan from 4am.
    Self-feeding: the recorder's own 4-8pm capture lands in the ~10s archive, so from day 2 onward
    tier 3 automatically includes true AH movers measured by real volume, not screener rank."""
    seed, seen = [], set()
    def add(names):
        for n in names:
            u = str(n).upper()
            if u and u not in seen:
                seen.add(u); seed.append(u)
    try:   # tier 1 — kev_watchlist: {"YYYY-MM-DD": [tickers]} → newest date's list
        r = requests.get(f"{DASH_URL}/api/kev_watchlist", timeout=8)
        if r.status_code == 200:
            d = r.json()
            if isinstance(d, dict) and d:
                latest = max(k for k in d.keys() if isinstance(k, str))
                if isinstance(d.get(latest), list): add(d[latest])
    except Exception:
        pass
    try:   # tier 2 — last evening's after-hours gainers (screener AFTER_MARKET rank)
        dc = data_client()
        if dc:
            res = dc.screener.get_gainers_losers(rank_type="AFTER_MARKET", category="US_STOCK",
                                                 sort_by="CHANGE_RATIO", direction="DESC", page_size=50)
            if res.status_code == 200:
                raw = res.json(); items = raw if isinstance(raw, list) else raw.get("data", raw.get("items", []))
                add(it.get("symbol") for it in items
                    if it.get("symbol") and PRICE_MIN <= float(it.get("price") or it.get("close") or 0) <= PRICE_MAX)
    except Exception:
        pass
    try:   # tier 3 — yesterday's collected movers (~10s names in the archive)
        r = requests.get(f"{DASH_URL}/api/bars?list=1", timeout=10)
        if r.status_code == 200:
            arch = (r.json() or {}).get("archived", {})
            if arch:
                prev = max(arch.keys())
                # 7/17: EXCLUDE our own sentinel series (ZZRECBOOT / ZZRECVOL) — they live in the
                # ~10S archive but are NOT real tickers; seeding them made Webull 417 INVALID_SYMBOL
                # on the whole chunk, which latched _sub_cap_hit and silently killed every remaining
                # subscribe (Kev's picks went uncaptured on 7/17 premarket).
                add(n[:-4] for n in arch.get(prev, [])
                    if isinstance(n, str) and n.upper().endswith("~10S")
                    and not n.upper().startswith("ZZ"))
    except Exception:
        pass
    return seed

# ── stream (standalone; mirrors WebullStream._connect, proven in stream_dual_test) ──
_stream = None
def _teardown_stream():
    """Disconnect + stop the old client so its daemon thread AND its server-side Webull session
    die. Ghost sessions pile up on the account and every NEW session gets INVALID_SESSION until
    a process restart (7/16 root cause). Called from ALL paths that abandon a client: reconnect
    (connect_stream), day roll (_reset_day — review F1: it nulled without disconnecting, leaking
    a ghost overnight into the 3:25am boot), and SIGTERM (graceful server-side disconnect so a
    redeploy doesn't leave a ghost that 417s the next boot's first subscribe)."""
    global _stream
    s = _stream
    _stream = None
    if s is not None:
        try: s.disconnect()
        except Exception: pass
        try: s.loop_stop()
        except Exception: pass

def connect_stream():
    global _stream
    try:
        from webull.core.utils.common import get_uuid
        from webull.data.data_streaming_client import DataStreamingClient
        # 7/16 ROOT-CAUSE FIX: connect_stream() runs on EVERY reconnect. The old client's daemon
        # thread + Webull streaming session stay alive if not closed; ghosts pile up on the account
        # and Webull rejects new sessions with INVALID_SESSION until a full process restart kills
        # them — the ~40-min recurring stall. Tear the old client down first (mirrors bot l.927).
        _teardown_stream()
        td = pathlib.Path(TOKEN_DIR); td.mkdir(parents=True, exist_ok=True)
        if TOKEN:
            (td / "token.txt").write_text(TOKEN + "\n" + str(int(time.time()*1000)+14*24*3600*1000) + "\nNORMAL\n")
        c = DataStreamingClient(APP_KEY, APP_SECRET, "us", get_uuid())   # OWN uuid = independent session
        c._api_client.set_token_dir(str(td))
        if TOKEN: c._api_client.set_token(TOKEN)
        c.on_quotes_message = _on_msg
        c.on_quotes_subscribe = lambda *a, **k: None
        c.connect_and_loop_async(timeout=1, thread_daemon=True)
        time.sleep(3)
        _stream = c
        log("stream connected")
        return True
    except Exception as e:
        log(f"stream connect failed: {e}")
        _stream = None
        return False

_fields_logged = [False]
def _on_msg(_client, topic, payload):
    try:
        basic = getattr(payload, "basic", None)
        sym = getattr(basic, "symbol", None)
        px = getattr(payload, "price", None) or getattr(payload, "ext_price", None) or getattr(payload, "ovn_price", None)
        if sym and px:
            p = float(px)
            if 0 < p < 1e6:
                # 7/16 premarket discovery: extended-session snapshots carry volume in DIFFERENT
                # fields than RTH (all RTH-era code only ever saw `volume`). Try the ext family too.
                cv = None
                for _obj in (payload, basic):
                    if _obj is None: continue
                    for _f in ("volume", "ext_volume", "extVolume", "total_volume", "totalVolume",
                               "accumulate_volume", "ovn_volume"):
                        _v = getattr(_obj, _f, None)
                        if _v not in (None, 0, "0", ""):
                            try:
                                cv = float(_v); break
                            except Exception: pass
                    if cv is not None: break
                if not _fields_logged[0]:
                    _fields_logged[0] = True
                    try:
                        _pf = [a for a in dir(payload) if not a.startswith("_")]
                        _bf = [a for a in dir(basic) if not a.startswith("_")] if basic else []
                        log(f"FIELD-DUMP payload={_pf}")
                        log(f"FIELD-DUMP basic={_bf} | first cv={cv}")
                    except Exception: pass
                ingest(str(sym).upper(), p, cv, time.time())
    except Exception:
        pass

_sub_cap_hit = False
def subscribe(syms):
    """Chunked (20/chunk): partial success beats all-or-nothing, and the first failing chunk
    MEASURES Webull's real per-session cap instead of guessing it."""
    global _sub_cap_hit
    if not _stream or _sub_cap_hit: return
    _now = et_now()
    # 9:15 shoulder (audit S2): any subscribe within 15 min of the open must already respect the
    # RTH cap — otherwise the 9:30 flip inherits ~98 premarket subs (the cap only gates NEW adds)
    # and Webull kicks at 9:31 message rates, exactly the open we exist to capture.
    _rth = _now.weekday() < 5 and ((_now.hour, _now.minute) >= (9, 15)) and _now.hour < 16
    _cap = RTH_SUB_CAP if _rth else MAX_SUBSCRIBE
    new = [s for s in syms if s and s not in _subscribed]   # preserves caller's priority order
    new = new[:max(0, _cap - len(_subscribed))]
    added = 0
    for i in range(0, len(new), 20):
        chunk = new[i:i+20]
        try:
            _stream.subscribe(chunk, "US_STOCK", ["SNAPSHOT"])
            _subscribed.update(chunk); added += len(chunk)
        except Exception as e:
            if "INVALID_SESSION" in str(e):
                # F3: auth failure, NOT capacity — don't latch the cap and wait 90s for the
                # watchdog; cycle the session immediately (supervisor tears down + reconnects).
                log(f"subscribe INVALID_SESSION at {len(_subscribed)} subs — cycling session now")
                raise InvalidSessionError(str(e))
            if "INVALID_SYMBOL" in str(e):
                # 7/17: ONE bad ticker must not kill its chunk AND latch the cap (that silently
                # dropped every later subscribe — Kev's picks went uncaptured). Retry the chunk
                # one-by-one so the good names get through; skip only the offender.
                log(f"subscribe INVALID_SYMBOL in chunk — retrying {len(chunk)} names individually")
                for s in chunk:
                    try:
                        _stream.subscribe([s], "US_STOCK", ["SNAPSHOT"])
                        _subscribed.add(s); added += 1
                    except Exception as e2:
                        if "INVALID_SESSION" in str(e2): raise InvalidSessionError(str(e2))
                        log(f"  skip bad symbol {s}")
                continue
            log(f"subscribe cap/err at {len(_subscribed)} subs: {e} — holding here")
            _sub_cap_hit = True
            break
    if added: log(f"subscribed +{added} (total {len(_subscribed)})")
    if added:
        _new = [x for x in new if x in _subscribed and x not in _seeded]
        def _seed_bg(names, boot_ts):
            for _n in names:
                if _stop.is_set(): return
                _seed_vwap_from_bars(_n, boot_ts)
                time.sleep(0.25)
        threading.Thread(target=_seed_bg, args=(_new, time.time()), daemon=True).start()

# ── persistence (bars + vwap series → dashboard durable store, gzipped) ──────
_seeded = set()        # symbols whose pre-boot VWAP history has been seeded from bar history
_CKPT = pathlib.Path("/tmp/recorder_vwap_ckpt.json")   # ephemeral FS: survives in-place restarts of the
                                                        # same container only; cross-deploy recovery = bar-seed

def _seed_vwap_from_bars(sym, upto_ts):
    """7/16 (Marcos: 'why can't it be engineered today'): a restart must not cost the day's anchor.
    Seed the accumulator's missing pre-boot window from PRE+RTH 1-min bar history — the same inputs
    that measured −0.12% vs the chart this morning. Ticks carry it from boot onward (disjoint windows:
    bars strictly BEFORE the boot minute; ticks after)."""
    if sym in _seeded: return
    _seeded.add(sym)
    dc = data_client()
    if not dc: return
    try:
        r = dc.market_data.get_history_bar(symbol=sym, category="US_STOCK", timespan="M1",
                                           count="800", trading_sessions="PRE,RTH")
        raw = r.json(); bars = raw if isinstance(raw, list) else raw.get("data", {}).get("items", raw.get("data", []))
        today = et_now().strftime("%Y-%m-%d")
        cutoff_min = int(upto_ts) // 60 * 60
        pv = v = 0.0
        for b in bars or []:
            t = str(b.get("time", ""))
            if t[:10] != today: continue
            try:
                bts = datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
            except Exception:
                continue
            if bts >= cutoff_min: continue
            h = float(b.get("high") or 0); l = float(b.get("low") or 0)
            c = float(b.get("close") or 0); vol = float(b.get("volume") or 0)
            pv += (h + l + c) / 3 * vol; v += vol
        if v > 0:
            with _lock:
                acc = _vwap.setdefault(sym, {"num": 0.0, "den": 0.0, "last_cumvol": None, "series": []})
                acc["num"] += pv; acc["den"] += v
            log(f"vwap-seeded {sym}: +{v:,.0f} sh of pre-boot history")
    except Exception as e:
        log(f"seed {sym} failed: {e}")

def _ckpt_save():
    try:
        with _lock:
            d = {sym: {"num": v["num"], "den": v["den"], "last_cumvol": v["last_cumvol"]}
                 for sym, v in _vwap.items()}
        _CKPT.write_text(json.dumps({"date": et_now().strftime("%Y-%m-%d"), "acc": d}))
    except Exception:
        pass

def _ckpt_load():
    try:
        if not _CKPT.exists(): return 0
        d = json.loads(_CKPT.read_text())
        if d.get("date") != et_now().strftime("%Y-%m-%d"): return 0
        n = 0
        with _lock:
            for sym, a in (d.get("acc") or {}).items():
                acc = _vwap.setdefault(sym, {"num": 0.0, "den": 0.0, "last_cumvol": None, "series": []})
                if acc["den"] == 0:
                    acc["num"], acc["den"], acc["last_cumvol"] = a["num"], a["den"], a.get("last_cumvol")
                    _seeded.add(sym); n += 1
        return n
    except Exception:
        return 0

_shipped = {}          # sym -> last bucket epoch already persisted (incremental persists;
                       # dashboard merge-on-write makes increments safe + idempotent)
_vw_shipped = {}       # sym -> last vwap-series ts already persisted

def build_payload(min_buckets=BUCKET_FLOOR, final=False):
    """Incremental by default: only CLOSED buckets newer than the last shipped one (payloads stay
    ~5min-sized; the whole-day re-send blew ~2GB/day egress). final=True ships everything unshipped
    including the still-open bucket."""
    cutoff = time.time() if final else (int(time.time()) // 10 * 10)   # open-bucket boundary
    series = {}
    # 7/16 (overnight audit): watermarks used to advance HERE, at build time — so one failed POST
    # (dashboard blip) permanently skipped that window's points from every future increment. Now
    # the would-be marks are RETURNED and persist() commits them only on HTTP 200. Merge-on-write
    # unions by time key, so re-shipping the same points after a failure is idempotent.
    marks10, marksvw = {}, {}
    with _lock:
        snap10 = {}
        for t, bk in _bars[10].items():
            if len(bk) < min_buckets and not final:
                continue
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
        series[f"{t}~10s"] = [
            {"time": datetime.fromtimestamp(k, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
             "open": str(b["o"]), "high": str(b["h"]), "low": str(b["l"]), "close": str(b["c"]),
             "volume": str(max(0, (b["v1"] or 0) - (b["v0"] or 0)))}
            for k, b in items]
    for t, ser in vwseries.items():
        series[f"{t}~vwap"] = [
            {"time": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
             "close": str(round(vw, 6)), "open": str(round(vw, 6)), "high": str(round(vw, 6)),
             "low": str(round(vw, 6)), "volume": "0"}
            for ts, vw in ser]
    return {"date": et_now().strftime("%Y-%m-%d"), "series": series, "source": "recorder"}, (marks10, marksvw)

def persist(reason="periodic"):
    try:
        if not DASH_URL: return False
        pl, marks = build_payload()
        if not pl["series"]: return False
        pl["reason"] = reason
        body = gzip.compress(json.dumps(pl).encode(), compresslevel=1)
        r = requests.post(f"{DASH_URL}/api/bars_bulk", data=body, timeout=15,
                          headers={"X-Dashboard-Secret": DASH_SECRET, "Content-Encoding": "gzip",
                                   "Content-Type": "application/json"})
        ok = r.status_code == 200
        if ok:
            with _lock:                    # commit shipped watermarks only on confirmed store write
                _shipped.update(marks[0])
                _vw_shipped.update(marks[1])
        log(f"persist({reason}): {len(pl['series'])} series → {r.status_code}")
        return ok
    except Exception as e:
        log(f"persist failed: {e}")
        return False

def _first_light_report():
    """4:00–9:30 canary (audit S1; 7/16: prices flowed 4.5h while volumes read zero — the VWAP
    accumulated NOTHING and nobody knew until 8:15). Logs the count of symbols actually
    accumulating tick-VWAP and ships a ZZRECVOL~10s sentinel row (close/volume = that count,
    open = symbols ticking) so the failure is visible from the dashboard store anywhere, not
    just Railway logs. No exit: a restart can't fix a field-regime change — visibility is the fix."""
    with _lock:
        nvol = sum(1 for v in _vwap.values() if v["den"] > 0)
        ntick = len(_bars[10])
    if ntick > 0 and nvol == 0:
        log("🚨 FIRST-LIGHT FAILURE: ticks flowing but ZERO volume accumulating — tick-VWAP NOT BUILDING (volume field regime?)")
    else:
        log(f"first-light: {ntick} symbols ticking, {nvol} accumulating tick-VWAP")
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        pl = {"date": et_now().strftime("%Y-%m-%d"), "reason": "first-light",
              "series": {"ZZRECVOL~10s": [{"time": ts, "open": str(ntick), "high": str(ntick),
                                           "low": str(nvol), "close": str(nvol), "volume": str(nvol)}]}}
        requests.post(f"{DASH_URL}/api/bars_bulk", data=gzip.compress(json.dumps(pl).encode(), 1),
                      headers={"X-Dashboard-Secret": DASH_SECRET, "Content-Encoding": "gzip",
                               "Content-Type": "application/json"}, timeout=10)
    except Exception:
        pass

# snapshot the running VWAP into each symbol's series periodically (for the ~vwap time series)
def snapshot_vwap():
    ts = time.time()
    with _lock:
        for sym, v in _vwap.items():
            if v["den"] > 0:
                v["series"].append((ts, v["num"] / v["den"]))

# ── lifecycle ────────────────────────────────────────────────────────────────
def _on_sigterm(signum, frame):
    log("SIGTERM — final flush")
    try: snapshot_vwap(); persist("sigterm")
    except Exception: pass
    try: _teardown_stream()     # graceful server-side disconnect — no ghost for the next boot
    except Exception: pass
    _stop.set()
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    os.kill(os.getpid(), signal.SIGTERM)

SESSION_START_ET = (3, 25)     # capture gate opens 3:25am ET (35 min before the 4:00 premarket open)

def in_session(now=None):
    now = now or et_now()
    return (now.weekday() < 5
            and SESSION_START_ET <= (now.hour, now.minute) < SESSION_END_ET)

def run_session():
    """One capture day: connect → seed → rescan/persist loop → final flush at 8pm. Errors bubble
    to the supervisor, which reconnects with backoff. 7/16: a NEW stream session has NO server-side
    subscriptions — clear the client-side sets or resubscription is silently skipped; and re-baseline
    cumvol trackers so the silent-gap volume isn't lumped onto one reconnect price."""
    global _stream, _sub_cap_hit
    _subscribed.clear()
    _sub_cap_hit = False
    with _lock:
        for _v in _vwap.values():
            _v["last_cumvol"] = None      # re-baseline: exclude gap volume rather than distort VWAP
    if not connect_stream():
        raise RuntimeError("stream connect failed")
    _last_ingest[0] = time.time()
    _ck = _ckpt_load()
    if _ck: log(f"vwap checkpoint restored for {_ck} symbol(s)")
    subscribe(carryover_seed())        # known names captured from premarket tick-1
    last_scan = last_persist = last_snap = last_flight = 0.0
    while not _stop.is_set():
        if not in_session():
            log("session end — final flush")
            snapshot_vwap(); persist("session_end")
            break
        t = time.time()
        if _last_ingest[0] and t - _last_ingest[0] > 90:
            log(f"TICK SILENCE {t - _last_ingest[0]:.0f}s — stream presumed dead, forcing reconnect")
            snapshot_vwap(); persist("silence_flush")
            raise RuntimeError("tick silence >90s")
        # audit S2: controlled downshift — shed premarket-width subs BEFORE the open's message
        # rates arrive. One deliberate cycle at ~9:15 (reconnect resubscribes priority-first under
        # the 9:15-shoulder cap) beats an uncontrolled Webull kick at 9:31.
        _dn = et_now()
        if (_dn.weekday() < 5 and (9, 15) <= (_dn.hour, _dn.minute) < (16, 0)
                and len(_subscribed) > RTH_SUB_CAP):
            log(f"RTH downshift: {len(_subscribed)} subs > cap {RTH_SUB_CAP} — controlled cycle before the open")
            snapshot_vwap(); persist("downshift_flush")
            raise RuntimeError("controlled RTH downshift")
        # audit S1: first-light canary every 10 min through premarket
        if t - last_flight >= 600:
            if _dn.weekday() < 5 and (4, 0) <= (_dn.hour, _dn.minute) < (9, 30):
                _first_light_report()
            last_flight = t
        # audit S3: 60s tick-VWAP snapshots (5-min points were too coarse to certify vs the chart)
        if t - last_snap >= 60:
            snapshot_vwap(); last_snap = t
        if t - last_scan >= RESCAN_SECS:
            try: subscribe(scan_movers())
            except InvalidSessionError: raise          # F3: must escape to the supervisor
            except Exception as e: log(f"rescan err: {e}")
            last_scan = t
        if t - last_persist >= PERSIST_SECS:
            snapshot_vwap(); persist("periodic"); _ckpt_save(); last_persist = t
        _stop.wait(5)

def _reset_day():
    with _lock:
        _bars[10].clear(); _bars[60].clear(); _vwap.clear()
        _shipped.clear(); _vw_shipped.clear()
    _subscribed.clear()
    globals()["_sub_cap_hit"] = False
    _teardown_stream()          # F1: day roll must KILL the session, not orphan it overnight

def main():
    # HARD-FAIL: capture-without-persistence is silent worthlessness; no creds = no purpose.
    missing = [n for n, v in (("WEBULL_APP_KEY", APP_KEY), ("WEBULL_APP_SECRET", APP_SECRET),
                              ("WEBULL_ACCESS_TOKEN", TOKEN), ("SCREENER_URL", DASH_URL)) if not v]
    if missing:
        log(f"FATAL: missing env {missing} — refusing to run a recorder that can't stream+persist")
        sys.exit(1)
    try: signal.signal(signal.SIGTERM, _on_sigterm)
    except Exception: pass
    # BOOT ANNOUNCE: prove the full chain (process→env→dashboard persistence) over HTTP,
    # independent of Railway's log pipeline (7/15: new-service logs showed nothing for 10+ min).
    try:
        _ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        _pl = {"date": "1999-01-01", "reason": "recorder-boot",
               "series": {"ZZRECBOOT~10s": [{"time": _ts, "open": "1", "high": "1",
                                             "low": "1", "close": "1", "volume": "0"}]}}
        requests.post(f"{DASH_URL}/api/bars_bulk", data=gzip.compress(json.dumps(_pl).encode(), 1),
                      headers={"X-Dashboard-Secret": DASH_SECRET, "Content-Encoding": "gzip",
                               "Content-Type": "application/json"}, timeout=10)
        log("boot announce posted")
    except Exception as e:
        log(f"boot announce failed: {e}")
    log(f"recorder up — gate {SESSION_START_ET[0]:02d}:{SESSION_START_ET[1]:02d}–"
        f"{SESSION_END_ET[0]:02d}:{SESSION_END_ET[1]:02d} ET weekdays (always-on, self-cycling)")
    backoff = 30
    while not _stop.is_set():
        if in_session():
            try:
                run_session()               # returns at 8pm (or raises)
                backoff = 30
                _reset_day()
                log("day complete — store reset, sleeping until next gate")
            except Exception as e:
                log(f"session error: {e} — reconnect in {backoff}s")
                snapshot_vwap(); persist("error_flush")
                # 7/16 DEAD-MAN'S SWITCH (rev 2, review F2): a wedge that in-process reconnects
                # can't clear needs a fresh PROCESS (Railway restartPolicy=ALWAYS, verified applied).
                # rev 1 armed RTH-only — which disarmed it during the 4am premarket, the very hours
                # the recorder exists for. Now: RTH fuse 5min; premarket/AH fuse 15min (thin tape
                # tolerated); never-ticked arm covers a boot wedged from tick zero (e.g. an overnight
                # ghost, F1): zero ticks EVER + ≥20min past gate-open + ≥15min uptime → exit.
                _n = et_now()
                _rth = _n.weekday() < 5 and (9, 30) <= (_n.hour, _n.minute) < (16, 0)
                _fuse = 300 if _rth else 900
                _dead = time.time() - _last_real_ingest[0] if _last_real_ingest[0] else 0
                _gate_open = _n.replace(hour=SESSION_START_ET[0], minute=SESSION_START_ET[1],
                                        second=0, microsecond=0)
                _never = (_last_real_ingest[0] == 0
                          and (_n - _gate_open).total_seconds() > 1200
                          and time.time() - _PROC_T0 > 900)
                if in_session() and ((_last_real_ingest[0] and _dead > _fuse) or _never):
                    log(f"capture dead ({'never ticked' if _never else f'{_dead:.0f}s'}) despite "
                        f"reconnects — exit for clean Railway restart")
                    try: _ckpt_save()
                    except Exception: pass
                    sys.exit(1)
                _stop.wait(backoff)
                # 7/16: kicks are EXTERNAL (Webull), not retry storms — escalating backoff just
                # donates capture time. Cap at 60s; a fresh kick after a stable run resets to 30.
                backoff = min(backoff * 2, 60)
        else:
            _stop.wait(60)                  # outside the gate: idle cheaply, never exit
    log("recorder stopped")

if __name__ == "__main__":
    main()
