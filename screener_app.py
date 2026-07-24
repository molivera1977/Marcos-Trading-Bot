"""
Marcos Scanner — Pre-market small-float gapper screener
Runs as a separate Railway web service alongside the trading bot.
Visit the deployed URL any morning to see live pre-market movers.
"""

import os
import time
import json
import pathlib
from datetime import datetime
from flask import Flask, jsonify, render_template_string, request
import pytz

# Webull SDK
try:
    from webull.core.client import ApiClient
    from webull.data.data_client import DataClient as WebullDataClient
    WEBULL_SDK_AVAILABLE = True
except ImportError:
    WEBULL_SDK_AVAILABLE = False
    WebullDataClient = None

import yfinance as yf

# ── Config ────────────────────────────────────────────────────────────────────

WEBULL_APP_KEY      = os.environ.get("WEBULL_APP_KEY", "")
WEBULL_APP_SECRET   = os.environ.get("WEBULL_APP_SECRET", "")
WEBULL_ACCESS_TOKEN = os.environ.get("WEBULL_ACCESS_TOKEN", "")
TRADING_HOST        = "api.webull.com"
WEBULL_TOKEN_DIR    = "/tmp/webull_token_screener"
EASTERN             = pytz.timezone("America/New_York")
TRADES_FILE         = pathlib.Path("/data/marcos_trades.json") if pathlib.Path("/data").exists() else pathlib.Path("/tmp/marcos_trades.json")
API_SECRET          = os.environ.get("DASHBOARD_SECRET", "marcos2026")

def _endpoint_authed():
    """7/11 audit A3: these token/compute endpoints were PUBLIC on a public URL. Accept the secret via
    header (scripts) or ?key= (browser)."""
    return (request.headers.get("X-Dashboard-Secret", "") == API_SECRET
            or request.args.get("key", "") == API_SECRET)


app = Flask(__name__)

# ── Trade storage (in-memory + JSON file) ─────────────────────────────────────

_trades: list = []
_account: dict = {"balance": 0.0, "updated": ""}
_MARKET_FILE = pathlib.Path("/data/market_strip.json") if pathlib.Path("/data").exists() else pathlib.Path("/tmp/market_strip.json")
_market: dict = {"indices": [], "news": [], "updated": ""}   # market strip (S&P/Dow/Nasdaq) — pushed by the bot via Webull
try:                                                          # 7/14: persist across deploys — 5 deploys on 7/13
    if _MARKET_FILE.exists():                                 # left the strip empty all day (memory-only store)
        _market.update(json.loads(_MARKET_FILE.read_text()))
except Exception:
    pass
_watching: dict = {}                   # Live watch list posted by bot each session
_trade_state: dict = {}                # Live state of the active trade (entry/price/pnl/stop/target)

# ── 7/11 audit A2: durability. One store lock (Flask threads mutate these concurrently) + atomic writes
# (tmp + os.replace) so a mid-write kill can never truncate a store; the old bare write_text could corrupt
# trades.json and the swallowing loader would then overwrite the history with empty state.
import threading as _threading, os as _os, tempfile as _tempfile
_store_lock = _threading.RLock()

def _atomic_write_text(path, text):
    tmp = f"{path}.{_os.getpid()}.{_threading.get_ident()}.tmp"   # unique per thread — no tmp-fd interleave
    with open(tmp, "w") as _f:
        _f.write(text)
        _f.flush()
        _os.fsync(_f.fileno())
    _os.replace(tmp, str(path))

def _load_trades():
    global _trades, _account
    if TRADES_FILE.exists():
        try:
            data    = json.loads(TRADES_FILE.read_text())
            _trades = data.get("trades", [])
            _account.update(data.get("account", {}))
        except Exception:
            pass

def _save_trades():
    with _store_lock:
        try:
            _atomic_write_text(TRADES_FILE, json.dumps({"trades": _trades, "account": _account}, indent=2))
        except Exception as e:
            print(f"⚠️  Could not save trades: {e}")

def _compute_stats():
    if not _trades:
        return {
            "total_trades": 0, "wins": 0, "losses": 0, "breakeven": 0, "win_rate": 0,
            "total_pnl": 0, "avg_gain": 0, "avg_loss": 0,
            "best_pnl": 0, "best_ticker": "—", "worst_pnl": 0, "worst_ticker": "—",
            "equity_curve": [],
        }
    wins      = [t for t in _trades if t.get("pnl", 0) > 0]
    losses    = [t for t in _trades if t.get("pnl", 0) < 0]
    breakeven = [t for t in _trades if t.get("pnl", 0) == 0]   # $0 scratches are their OWN bucket, not losses
    total_pnl = sum(t.get("pnl", 0) for t in _trades)
    best  = max(_trades, key=lambda t: t.get("pnl", 0))
    worst = min(_trades, key=lambda t: t.get("pnl", 0))
    running, curve = 0.0, []
    for t in sorted(_trades, key=lambda t: t.get("date", "")):
        running += t.get("pnl", 0)
        curve.append({"date": t["date"], "equity": round(running, 2)})
    return {
        "total_trades": len(_trades),
        "wins":         len(wins),
        "losses":       len(losses),
        "breakeven":    len(breakeven),
        "win_rate":     round(len(wins) / max(len(wins) + len(losses), 1) * 100, 1),   # BE excluded — scratches don't count against WR
        "total_pnl":    round(total_pnl, 2),
        "avg_gain":     round(sum(t.get("pnl_pct", 0) for t in wins)  / max(len(wins), 1), 1),
        "avg_loss":     round(sum(t.get("pnl_pct", 0) for t in losses) / max(len(losses), 1), 1),
        "best_pnl":     round(best.get("pnl", 0), 2),
        "best_ticker":  best.get("ticker", "—"),
        "worst_pnl":    round(worst.get("pnl", 0), 2),
        "worst_ticker": worst.get("ticker", "—"),
        "equity_curve": curve,
    }

_load_trades()

# ── Day-Two Observation store (observe-only — how hard day-1 gappers behave on day 2) ──
OBS_FILE = pathlib.Path("/data/observations.json") if pathlib.Path("/data").exists() else pathlib.Path("/tmp/observations.json")
# day2_watch: tickers to observe (auto from each day's gappers + manual seeds).
# observations: time-series snapshots of those tickers' day-2 behavior.
_obs: dict = {"day2_watch": [], "observations": [], "daily_gappers": {}}

def _load_obs():
    global _obs
    if OBS_FILE.exists():
        try:
            _obs.update(json.loads(OBS_FILE.read_text()))
        except Exception:
            pass

def _save_obs():
    try:
        _obs["observations"] = _obs.get("observations", [])[-5000:]   # keep file bounded
        with _store_lock: _atomic_write_text(OBS_FILE, json.dumps(_obs, indent=2))
    except Exception as e:
        print(f"⚠️  Could not save observations: {e}")

_load_obs()

# ── Webull helpers ─────────────────────────────────────────────────────────────

def _pre_populate_token():
    if not WEBULL_ACCESS_TOKEN:
        return
    try:
        import pathlib
        d = pathlib.Path(WEBULL_TOKEN_DIR)
        d.mkdir(parents=True, exist_ok=True)
        expires_ms = int(time.time() * 1000) + (14 * 24 * 3600 * 1000)
        with open(d / "token.txt", "w") as f:
            f.write(WEBULL_ACCESS_TOKEN + "\n")
            f.write(str(expires_ms) + "\n")
            f.write("NORMAL\n")
    except Exception:
        pass


def _silence_webull_sdk_logs():
    """429-kill (7/18): the SDK logs every ServerException at ERROR with the FULL SIGNED REQUEST
    (x-access-token included) to stdout, and response.py force-DEBUGs its own logger. Every
    webull.* logger → CRITICAL, each individually (a child's explicit level beats any parent)."""
    import logging
    names = {"webull", "webull.core", "webull.core.client", "webull.core.http.response"}
    names.update(n for n in logging.root.manager.loggerDict if n.startswith("webull"))
    for n in names:
        logging.getLogger(n).setLevel(logging.CRITICAL)

# ── #102 (Marcos 7/24): reuse ONE Webull client instead of rebuilding it — and re-verifying the
# token with Webull's server — on EVERY request. That per-request re-verify was the 429 root: this
# week's read volume (read-list + seed, 20-28 lookups/cycle) turned it into a storm that rate-limited
# the scanner AND starved the bot's scan. The token was always cached on disk (14d valid); we just
# stopped throwing away the verified CLIENT. Singleton + freshness TTL + thread lock.
# WEBULL_CLIENT_SINGLETON=0 = instant revert to the original build-every-call behavior. ──
_DC_SINGLETON = _os.environ.get("WEBULL_CLIENT_SINGLETON", "1") == "1"
_DC_TTL_SECS  = int(_os.environ.get("WEBULL_CLIENT_TTL_SECS", "120"))   # rebuild (refresh) at most this often
_dc_cache     = {"client": None, "built": 0.0, "next_try": 0.0}
_dc_lock      = _threading.Lock()

def _build_data_client():
    """The expensive path: construct a fresh Webull client = ONE token re-verify with Webull."""
    if not WEBULL_SDK_AVAILABLE or not WebullDataClient:
        return None
    try:
        _pre_populate_token()
        api_client = ApiClient(WEBULL_APP_KEY, WEBULL_APP_SECRET, "us",
                               token_check_duration_seconds=60,
                               token_check_interval_seconds=5)
        api_client.set_token_dir(WEBULL_TOKEN_DIR)
        api_client.add_endpoint("us", TRADING_HOST)
        client = WebullDataClient(api_client)
        _silence_webull_sdk_logs()   # client init (re)configures SDK loggers — silence after
        return client
    except Exception as e:
        print(f"DataClient error: {e}")
        return None

def _make_data_client():
    """#102: return a REUSED Webull client (built once, refreshed every _DC_TTL_SECS) instead of a
    fresh build + token-reverify on every request. Thread-safe. On a build failure, keep serving any
    still-good client (its token is valid 14d) and back off before retrying, so a Webull outage can
    never re-create the per-request rebuild storm. Same signature — call sites are unchanged."""
    if not _DC_SINGLETON:
        return _build_data_client()                       # instant-revert = original behavior
    c = _dc_cache
    now = time.time()
    # fast path: a fresh cached client — NO rebuild, NO token re-verify (this is the 429 fix)
    if c["client"] is not None and (now - c["built"]) < _DC_TTL_SECS:
        return c["client"]
    with _dc_lock:
        now = time.time()
        if c["client"] is not None and (now - c["built"]) < _DC_TTL_SECS:
            return c["client"]                            # another thread just (re)built it
        if now < c["next_try"]:
            return c["client"]                            # in build-failure backoff: serve what we have (may be None)
        client = _build_data_client()
        if client is not None:
            c["client"], c["built"], c["next_try"] = client, now, 0.0
        elif c["client"] is not None:
            c["built"] = now                              # refresh failed, but old token valid 14d — keep serving, recheck in TTL
        else:
            c["next_try"] = now + 20                      # no client yet + build failing → back off, don't storm rebuilds
        return c["client"]

# ── Market state ───────────────────────────────────────────────────────────────

def _market_state():
    now_et = datetime.now(EASTERN)
    is_weekend = now_et.weekday() >= 5
    market_open = (not is_weekend
                   and (now_et.hour > 9 or (now_et.hour == 9 and now_et.minute >= 30))
                   and now_et.hour < 16)
    premarket = not is_weekend and 4 <= now_et.hour and not market_open and now_et.hour < 10
    after_hours = not market_open and not premarket
    if after_hours:
        state = "after_hours"
    elif market_open:
        state = "open"
    else:
        state = "premarket"
    return now_et, market_open, premarket, after_hours, state

# ── Core scan logic ────────────────────────────────────────────────────────────

def _chart_url(symbol, exchange):
    """Webull chart URL (webull.com/quote/<exchange>-<ticker>) — the user's platform. Falls back to TradingView
    when the exchange is unknown so a link always opens something."""
    slug_map = {"NSDQ": "nasdaq", "NAS": "nasdaq", "NASDAQ": "nasdaq", "NYSE": "nyse", "NYS": "nyse",
                "AMEX": "amex", "ASE": "amex", "ARCA": "nyse", "BATS": "nasdaq", "PACIFIC": "nyse"}
    ex = (exchange or "").upper().strip()
    slug = slug_map.get(ex) or (ex.lower() if ex.isalpha() else "")
    sym = (symbol or "").lower()
    if slug and sym:
        return f"https://www.webull.com/quote/{slug}-{sym}"
    return f"https://www.tradingview.com/chart/?symbol={symbol}"


def _webull_ah_price(dc, symbol):
    """Extended-hours price (post-market now / pre-market early AM) via the Webull snapshot — the SAME feed
    the bot trades on, and more reliable than yfinance for thin small-caps. extend_hour_required=True pulls the
    extended session. Returns 0 if unavailable → caller falls back to showing just the regular close."""
    try:
        resp = dc.market_data.get_snapshot(symbols=symbol, category="US_STOCK", extend_hour_required=True)
        if getattr(resp, "status_code", 0) != 200:
            return 0
        raw = resp.json()
        if isinstance(raw, list):
            d = raw[0] if raw else {}
        else:
            data = raw.get("data", {}) if isinstance(raw, dict) else {}
            if isinstance(data, list):
                d = data[0] if data else {}
            elif isinstance(data, dict):
                items = data.get("items", [])
                d = items[0] if items else data
            else:
                d = {}
        # Webull's actual extended-hours field is 'extend_hour_last_price' (confirmed via /api/quote_debug).
        # This field holds whichever extended session is live — post-market in the evening, PRE-MARKET in the
        # early AM. No close fallback: if there's no extended print, return 0 so the row shows just the close.
        ah = (d.get("extend_hour_last_price") or d.get("extendHourLastPrice") or
              d.get("pre_market_price") or d.get("preMarketPrice") or 0)
        ah = round(float(ah or 0), 2)
        # Webull's own extended-session % change (vs the prior regular close) — correct for BOTH AH and PM.
        pct = d.get("extend_hour_change_ratio")
        if pct in (None, 0):
            base = float(d.get("close") or 0)
            pct = ((ah - base) / base) if (base > 0 and ah > 0) else 0
        pct = round(float(pct or 0) * 100, 1)
        return ah, pct
    except Exception:
        return 0, 0


def run_scan():
    """
    1. Webull screener → live gainers / pre-market / after-hours movers
    2. Filter: price $0.50–$30, move threshold varies by session
    3. yfinance float check → drop large floats (50M live, 100M evening)
    4. After hours: add short interest + day stats for tomorrow's watchlist
    5. Score by change% / float_millions, return top 15 (20 evening)
    """
    now_et, market_open, premarket, after_hours, _ = _market_state()
    # rank_type for get_gainers_losers is a TIME PERIOD, not a metric. "CHANGE_RATIO" is a sort_by
    # value → it returned 200+EMPTY, silently killing the gainers feed. DAY_1 = today's gainers.
    rank_type   = "DAY_1" if market_open else "PRE_MARKET"
    min_chg     = 5 if market_open else 8
    max_float   = 50_000_000
    top_n       = 20   # 7/3: 15→20 (wider net — parity with the bot scanner)
    if after_hours:
        rank_type = "DAY_1"   # evening "tomorrow's watchlist" = today's full-day gainers
        min_chg   = 10
        max_float = 100_000_000
        top_n     = 20
    source_label = "Live gainer" if market_open else ("Today's mover" if after_hours else "Pre-mkt gainer")

    data_client = _make_data_client()
    candidates = {}
    errors = []

    if data_client:
        # Top gainers — live intraday or pre-market depending on time
        try:
            res = data_client.screener.get_gainers_losers(
                rank_type=rank_type,
                category="US_STOCK",
                sort_by="CHANGE_RATIO",
                direction="DESC",
                page_size=100,
            )
            if res.status_code == 200:
                raw = res.json()
                items = raw if isinstance(raw, list) else raw.get("data", raw.get("items", []))
                for item in (items or []):
                    sym   = item.get("symbol", "")
                    chg   = float(item.get("change_ratio") or 0) * 100
                    price = float(item.get("price") or item.get("close") or 0)
                    mktcap = float(item.get("market_value") or 0)
                    vol   = float(item.get("volume") or 0)
                    if not sym or price < 0.50 or price > 20 or chg < min_chg:
                        continue
                    candidates[sym] = {
                        "symbol": sym, "change_pct": round(chg, 2),
                        "price": round(price, 2), "market_cap": mktcap,
                        "premarket_volume": int(vol), "relative_volume": None,
                        "float_shares": 0, "float_label": "—", "source": source_label,
                        "exchange": item.get("exchange_code") or item.get("disExchangeCode") or item.get("exchangeCode") or "",
                    }
            else:
                errors.append(f"Gainers: HTTP {res.status_code}")
        except Exception as e:
            errors.append(f"Gainers error: {e}")

        # Unusual relative volume
        try:
            res = data_client.screener.get_most_active(
                category="US_STOCK",
                rank_type="RELATIVE_VOLUME_10D",
                sort_by="RELATIVE_VOLUME_10D",
                direction="DESC",
                page_size=50,
            )
            if res.status_code == 200:
                raw = res.json()
                items = raw if isinstance(raw, list) else raw.get("data", raw.get("items", []))
                for item in (items or []):
                    sym     = item.get("symbol", "")
                    chg     = float(item.get("change_ratio") or 0) * 100
                    price   = float(item.get("price") or item.get("close") or 0)
                    mktcap  = float(item.get("market_value") or 0)
                    rel_vol = float(item.get("relative_volume_10d") or 0)
                    vol     = float(item.get("volume") or 0)
                    rvol_min = 3 if after_hours else 2
                    chg_min  = 5 if after_hours else 0   # 7/3 ANTICIPATORY: intraday, add a 2× RVOL name even
                                                         # while price is still FLAT (volume precedes price — Kev).
                    if not sym or price < 0.50 or price > 20 or rel_vol < rvol_min:
                        continue
                    if sym in candidates:
                        candidates[sym]["relative_volume"] = round(rel_vol, 1)
                    elif chg >= chg_min:
                        candidates[sym] = {
                            "symbol": sym, "change_pct": round(chg, 2),
                            "price": round(price, 2), "market_cap": mktcap,
                            "premarket_volume": int(vol), "relative_volume": round(rel_vol, 1),
                            "float_shares": 0, "float_label": "—", "source": "Unusual volume",
                            "exchange": item.get("exchange_code") or item.get("disExchangeCode") or item.get("exchangeCode") or "",
                        }
            else:
                errors.append(f"Volume: HTTP {res.status_code}")
        except Exception as e:
            errors.append(f"Volume error: {e}")
    else:
        errors.append("Webull SDK not available — check env vars")

    # Float check + enrichment via yfinance
    results = []
    for sym, g in candidates.items():
        g["chart_url"] = _chart_url(sym, g.get("exchange", ""))
        try:
            info = yf.Ticker(sym).info or {}
            float_sh = info.get("floatShares") or info.get("sharesOutstanding") or 0
            g["float_shares"] = float_sh
            float_m = float_sh / 1_000_000
            if float_sh == 0:
                g["float_label"] = "N/A"
                g["float_tier"] = "unknown"
            elif float_sh <= 10_000_000:
                g["float_label"] = f"{float_m:.1f}M"
                g["float_tier"] = "small"
            elif float_sh <= max_float:
                g["float_label"] = f"{float_m:.1f}M"
                g["float_tier"] = "medium"
            else:
                time.sleep(0.3)
                continue
            if after_hours or premarket:
                # Extended price via WEBULL (same feed the bot trades on): post-market in the evening,
                # PRE-MARKET in the early AM — the field auto-switches. Label follows the live session.
                g["ah_price"], g["ah_pct"] = _webull_ah_price(data_client, sym) if data_client else (0, 0)
                g["ah_label"] = "PM" if premarket else "AH"
                time.sleep(0.15)   # gentle on the token
            if after_hours:
                g["short_interest"] = round((info.get("shortPercentOfFloat") or 0) * 100, 1)
                g["day_high"] = info.get("dayHigh") or 0
                g["day_low"] = info.get("dayLow") or 0
                g["day_open"] = info.get("open") or 0
                day_range = 0
                if g["day_open"] and g["day_high"] and g["day_low"]:
                    day_range = round((g["day_high"] - g["day_low"]) / g["day_open"] * 100, 1)
                g["day_range_pct"] = day_range
            results.append(g)
            time.sleep(0.3)
        except Exception:
            g["float_shares"] = 0
            g["float_label"] = "N/A"
            g["float_tier"] = "unknown"
            results.append(g)

    def score(g):
        f = g.get("float_shares") or 0
        float_m = f / 1_000_000 if f > 0 else 25
        return g["change_pct"] / max(float_m, 0.1)

    results = sorted(results, key=score, reverse=True)[:top_n]

    # ── KEV PIN (7/16, Marcos: "regardless if they are in the top 20 I want his tickers on the list").
    #    Same invariant as the bot's force-add and the recorder's tier-1 seed, applied to the scanner:
    #    Kev's picks ALWAYS render. In-rank rows get kev=True; missing picks get a snapshot-backed row. ──
    try:
        _dates = [k for k in _kev_wl.keys() if isinstance(k, str) and k.startswith("20")]
        _kev_syms = [str(t).upper() for t in (_kev_wl.get(max(_dates)) or [])] if _dates else []
        _have = {r.get("symbol") for r in results}
        for r in results:
            r["kev"] = r.get("symbol") in _kev_syms
        for _sym in _kev_syms:
            if _sym in _have:
                continue
            _row = {"symbol": _sym, "change_pct": 0.0, "price": 0.0, "market_cap": 0,
                    "premarket_volume": 0, "relative_volume": None, "float_shares": 0,
                    "float_label": "—", "float_tier": "na", "source": "KEV pick",
                    "exchange": "", "kev": True}
            try:
                if data_client:
                    _resp = data_client.market_data.get_snapshot(
                        symbols=_sym, category="US_STOCK", extend_hour_required=True)
                    if getattr(_resp, "status_code", 0) == 200:
                        _raw = _resp.json()
                        if isinstance(_raw, list):
                            _d = _raw[0] if _raw else {}
                        else:
                            _dd = _raw.get("data", {}) if isinstance(_raw, dict) else {}
                            _d = (_dd[0] if _dd else {}) if isinstance(_dd, list) else                                  ((_dd.get("items") or [{}])[0] if isinstance(_dd, dict) and _dd.get("items") else _dd)
                        _cl = float(_d.get("close") or 0)
                        _pc = float(_d.get("pre_close") or _d.get("preClose") or 0)
                        _row["price"] = round(_cl, 2)
                        if _pc > 0 and _cl > 0:
                            _row["change_pct"] = round((_cl - _pc) / _pc * 100, 2)
                        _row["market_cap"] = float(_d.get("market_value") or _d.get("marketValue") or 0)
                    _ah = _webull_ah_price(data_client, _sym)
                    if isinstance(_ah, tuple) and _ah[0]:
                        _row["ah_price"], _row["ah_pct"] = _ah
                        _row["ah_label"] = "AH"
            except Exception:
                pass
            results.append(_row)
    except Exception as _e:
        errors.append(f"Kev pin: {_e}")
    return results, errors

# ── HTML template ──────────────────────────────────────────────────────────────

# ── Light/dark toggle (Marcos 7/20 night: "hard to read in bright sunlight"). One snippet,
# injected into every page's <head> at render time. Light mode = smart inversion (keeps the
# green/red semantics via hue-rotate); choice persists per device via localStorage. ──
THEME_SNIPPET = """
<style>
html[data-theme=light]{filter:invert(.93) hue-rotate(180deg);background:#ececea}
html[data-theme=light] img,html[data-theme=light] .no-invert{filter:invert(1) hue-rotate(180deg)}
#themeBtn{position:fixed;bottom:14px;right:14px;z-index:9999;width:44px;height:44px;border-radius:50%;
border:1px solid #30363d;background:#161b22;color:#e6edf3;font-size:19px;line-height:1;cursor:pointer;
opacity:.9;box-shadow:0 2px 8px rgba(0,0,0,.35)}
#themeBtn:hover{opacity:1}
</style>
<script>
(function(){
  document.documentElement.setAttribute('data-theme', localStorage.getItem('mtheme') || 'dark');
  function addBtn(){
    var b=document.createElement('button'); b.id='themeBtn'; b.title='Light / dark';
    b.textContent='\\u25D1';
    b.onclick=function(){
      var n=document.documentElement.getAttribute('data-theme')==='dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', n); localStorage.setItem('mtheme', n);
    };
    document.body.appendChild(b);
  }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', addBtn); } else { addBtn(); }
})();
</script>
"""

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Marcos Scanner</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Inter',system-ui,sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}

  .header{display:flex;align-items:center;justify-content:space-between;padding:16px 24px;
          background:#161b22;border-bottom:1px solid #21262d}
  .logo{display:flex;align-items:center;gap:10px}
  .logo-icon{width:34px;height:34px;border-radius:8px;background:#1a3a2a;
             display:flex;align-items:center;justify-content:center;font-size:18px}
  .logo h1{font-size:16px;font-weight:600;color:#e6edf3}
  .logo sub{font-size:11px;color:#8b949e;display:block;margin-top:1px;font-weight:400}
  .header-right{display:flex;align-items:center;gap:12px}
  .ts{font-size:12px;color:#8b949e}
  .btn{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-family:inherit;
       padding:7px 14px;border-radius:8px;border:1px solid #30363d;background:transparent;
       color:#e6edf3;cursor:pointer;transition:background .15s}
  .btn:hover{background:#21262d}
  .btn:disabled{opacity:.5;cursor:not-allowed}

  .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:20px 24px 0}
  .stat{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:14px 18px}
  .stat-label{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
  .stat-value{font-size:24px;font-weight:600}
  .green{color:#3fb950}
  .yellow{color:#d29922}
  .gray{color:#8b949e}

  .body{padding:20px 24px}
  .section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
  .section-title{font-size:14px;font-weight:500;color:#e6edf3}
  .live-dot{display:inline-flex;align-items:center;gap:5px;font-size:11px;
            background:#1a3a2a;color:#3fb950;padding:3px 10px;border-radius:20px}
  .live-dot::before{content:'';width:6px;height:6px;border-radius:50%;background:#3fb950}

  .table-wrap{border-radius:10px;border:1px solid #21262d;overflow-x:auto;-webkit-overflow-scrolling:touch}
  table{width:100%;border-collapse:collapse;font-size:13px}
  thead th{padding:10px 16px;text-align:left;font-size:11px;font-weight:500;color:#8b949e;
           text-transform:uppercase;letter-spacing:.4px;background:#161b22;
           border-bottom:1px solid #21262d;cursor:pointer;user-select:none;white-space:nowrap}
  thead th:hover{color:#e6edf3;background:#1c2128}
  thead th.sort-asc::after{content:' ▲';font-size:9px}
  thead th.sort-desc::after{content:' ▼';font-size:9px}
  tbody tr{border-bottom:1px solid #161b22;transition:background .1s}
  tbody tr:last-child{border-bottom:none}
  tbody tr:hover{background:#161b22}
  tbody td{padding:12px 16px;color:#e6edf3;white-space:nowrap}

  .ticker-cell{font-weight:600;font-size:14px;color:#58a6ff}
  .tk-link{color:inherit;text-decoration:none;cursor:pointer}
  .tk-link:hover{text-decoration:underline}
  .tk-arrow{font-size:10px;opacity:.45;margin-left:3px}
  .price-cell{font-variant-numeric:tabular-nums}
  .ah{font-size:11px;font-weight:600;margin-left:6px;opacity:.9}
  .ah-up{color:#3ddc84}.ah-dn{color:#ff6b6b}
  .gap-pill{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600}
  .gap-hot{background:#1a3a2a;color:#3fb950}
  .gap-warm{background:#2d2a14;color:#d29922}
  .float-small{color:#3fb950;font-weight:600}
  .float-med{color:#d29922}
  .float-na{color:#8b949e}
  .source-badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;
               background:#161b22;border:1px solid #30363d;color:#8b949e}

  .loader{display:none;text-align:center;padding:48px;color:#8b949e;font-size:14px}
  .loader.active{display:block}
  .spinner{width:28px;height:28px;border:2px solid #21262d;border-top-color:#3fb950;
           border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 12px}
  @keyframes spin{to{transform:rotate(360deg)}}

  .errors{background:#1e1419;border:1px solid #3a1f1f;border-radius:8px;
          padding:12px 16px;margin-top:16px;font-size:12px;color:#f85149}
  .empty{text-align:center;padding:48px;color:#8b949e;font-size:14px}

  /* ── Bot candidate highlighting ── */
  tr.bot-candidate{background:#0d1f14}
  tr.bot-candidate:hover{background:#112b1a}
  tr.bot-candidate td.ticker-cell{font-weight:700;color:#3fb950}
  .tale-link{margin-left:6px;text-decoration:none;font-size:12px;opacity:.8}
  .tale-link:hover{opacity:1}
  .bot-pill{display:inline-block;background:#1a3a2a;border:1px solid #2d5a3d;
            color:#3fb950;font-size:10px;font-weight:600;padding:1px 6px;
            border-radius:4px;margin-left:6px;vertical-align:middle}
  .kev-pill{display:inline-block;background:#3a2f14;border:1px solid #6b5518;
            color:#e3b341;font-size:10px;font-weight:700;padding:1px 6px;
            border-radius:4px;margin-left:6px;vertical-align:middle}
  tr.kev-row td{background:rgba(227,179,65,0.06)}
  .filter-btn{font-size:12px;font-family:inherit;padding:5px 12px;border-radius:8px;
              border:1px solid #2d5a3d;background:#1a3a2a;color:#3fb950;cursor:pointer;white-space:nowrap}
  .filter-btn.off{background:transparent;border-color:#30363d;color:#8b949e}
  .stat-sub{font-size:11px;color:#8b949e;margin-top:2px}

  @media(max-width:700px){
    .stats{grid-template-columns:repeat(2,1fr)}
    thead th:nth-child(6),tbody td:nth-child(6){display:none}
  }
</style>
</head>
<body>
<div class="header">
  <div class="logo">
    <div class="logo-icon">📈</div>
    <div>
      <h1>Marcos Scanner</h1>
      <sub id="scanner-sub">RVOL + momentum candidates</sub>
    </div>
  </div>
  <div class="header-right">
    <span class="ts" id="ts">—</span>
    <button class="btn" id="scan-btn" onclick="runScan()">&#8635; Scan now</button>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="stat-label">Candidates</div><div class="stat-value" id="s-count">—</div><div class="stat-sub" id="s-bot-count"></div></div>
  <div class="stat"><div class="stat-label">Avg move</div><div class="stat-value green" id="s-gap">—</div></div>
  <div class="stat"><div class="stat-label">Smallest float</div><div class="stat-value green" id="s-float">—</div></div>
  <div class="stat"><div class="stat-label">Top rel vol</div><div class="stat-value" id="s-vol">—</div></div>
</div>

<div class="body">
  <div class="section-header">
    <span class="section-title" id="section-title">RVOL + momentum candidates</span>
    <div style="display:flex;align-items:center;gap:10px">
      <button class="filter-btn" id="filter-btn" onclick="toggleFilter()">🤖 Bot candidates only</button>
      <span class="live-dot" id="live-badge">Live</span>
    </div>
  </div>

  <div class="loader" id="loader">
    <div class="spinner"></div>
    Scanning Webull screener…
  </div>

  <div class="table-wrap" id="table-wrap">
    <table>
      <thead>
        <tr>
          <th onclick="sortBy('symbol')">Ticker</th>
          <th onclick="sortBy('price')">Price</th>
          <th onclick="sortBy('change_pct')" class="sort-desc">Move %</th>
          <th onclick="sortBy('float_shares')">Float</th>
          <th onclick="sortBy('relative_volume')">Rel vol</th>
          <th class="evening-col" style="display:none" onclick="sortBy('short_interest')">Short %</th>
          <th class="evening-col" style="display:none" onclick="sortBy('day_range_pct')">Day range</th>
          <th onclick="sortBy('market_cap')">Mkt cap</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody id="tbody"><tr><td colspan="9" class="empty">Click "Scan now" to load.</td></tr></tbody>
    </table>
  </div>
  <div id="errors-wrap"></div>
</div>

<script>
function fmt(n){return n==null?'—':n.toLocaleString()}
function fmtM(n){if(!n||n===0)return'—';var m=n/1e6;return m<1?(m*1000).toFixed(0)+'K':m.toFixed(1)+'M'}

var _scanData = [];
var _sortCol = 'change_pct';
var _sortAsc = false;
var _afterHours = false;

function sortBy(col){
  if(_sortCol===col){ _sortAsc=!_sortAsc; }
  else { _sortCol=col; _sortAsc=(col==='symbol'); }
  // Update header classes
  document.querySelectorAll('thead th').forEach(function(th){
    th.classList.remove('sort-asc','sort-desc');
  });
  var ths=document.querySelectorAll('thead th');
  var colMap={symbol:0,price:1,change_pct:2,float_shares:3,relative_volume:4,market_cap:5};
  var idx=colMap[col];
  if(idx!=null) ths[idx].classList.add(_sortAsc?'sort-asc':'sort-desc');
  renderRows(_scanData);
}

var _filterOn = false;
function applyFilter(on){
  var rows = document.querySelectorAll('#tbody tr');
  rows.forEach(function(row){
    if(on && row.dataset.bot==='0' && row.dataset.kev!=='1') row.style.display='none';
    else row.style.display='';
  });
}
function toggleFilter(){
  _filterOn = !_filterOn;
  var btn = document.getElementById('filter-btn');
  if(_filterOn){ btn.classList.remove('off'); applyFilter(true); }
  else { btn.classList.add('off'); applyFilter(false); }
}

function renderRows(rows){
  var sorted=rows.slice().sort(function(a,b){
    var av=a[_sortCol], bv=b[_sortCol];
    if(av==null||av===undefined) av=_sortAsc?'￿':-Infinity;
    if(bv==null||bv===undefined) bv=_sortAsc?'￿':-Infinity;
    if(typeof av==='string') return _sortAsc?av.localeCompare(bv):bv.localeCompare(av);
    return _sortAsc?av-bv:bv-av;
  });
  sorted.sort(function(a,b){var ka=(a.kev===true||_kevSet.has((a.symbol||'').toUpperCase()))?1:0,
    kb=(b.kev===true||_kevSet.has((b.symbol||'').toUpperCase()))?1:0; return kb-ka});   // stable: Kev pins top
  var tbody=document.getElementById('tbody');
  tbody.innerHTML=sorted.map(function(r){
    var isBot=(r.price<=20)&&(r.float_shares>0)&&(r.float_shares<20000000);  // mirrors the BOT: price<$20 + known float<20M
    var gapClass=r.change_pct>=10?'gap-hot':'gap-warm';
    var floatClass=r.float_tier==='small'?'float-small':r.float_tier==='medium'?'float-med':'float-na';
    var relVol=r.relative_volume?r.relative_volume.toFixed(1)+'×':'—';
    var mktcap=r.market_cap?'$'+fmtM(r.market_cap):'—';
    var botBadge=isBot?'<span class="bot-pill">BOT</span>':'';
    var _sym=(r.symbol||'').toUpperCase();
    var isKev=_kevSet.has(_sym)||r.kev===true;
    var kevBadge=isKev?'<span class="kev-pill" title="'+(_kevLevels[_sym]||'Kev pick')+'">\u2605 KEV</span>':'';
    var shortPct = r.short_interest ? r.short_interest.toFixed(1)+'%' : '—';
    var dayRange = r.day_range_pct ? r.day_range_pct.toFixed(1)+'%' : '—';
    var shortClass = r.short_interest >= 20 ? 'gap-hot' : r.short_interest >= 10 ? 'gap-warm' : '';
    var eveningStyle = _afterHours ? '' : 'display:none';
    var ahLbl = r.ah_label || 'AH';
    // Prefer the move vs the close shown in this row (always visually consistent: down price => negative).
    // Fall back to Webull's own extended % only when the row's price already equals the extended price
    // (pre-market, where the price column IS the extended print) — otherwise Webull's different close
    // baseline can show e.g. +0.7% next to a visibly lower AH price.
    var closePct = (r.ah_price && r.price) ? ((r.ah_price - r.price) / r.price * 100) : 0;
    var ahPct = (Math.abs(closePct) >= 0.05) ? closePct : ((typeof r.ah_pct === 'number') ? r.ah_pct : 0);
    var ahShow = r.ah_price > 0 && Math.abs(ahPct) >= 0.05;
    var ahP = ahShow ? ' <span class="ah '+(ahPct>=0?'ah-up':'ah-dn')+'">'+ahLbl+' $'+r.ah_price.toFixed(2)+' ('+(ahPct>=0?'+':'')+ahPct.toFixed(1)+'%)</span>' : '';
    return '<tr class="'+(isBot?'bot-candidate ':'')+(isKev?'kev-row':'')+'" data-bot="'+(isBot?'1':'0')+'" data-kev="'+(isKev?'1':'0')+'">'
      +'<td class="ticker-cell"><a class="tk-link" href="'+(r.chart_url||('https://www.tradingview.com/chart/?symbol='+r.symbol))+'" target="_blank" rel="noopener" title="Open '+r.symbol+' chart (Webull)">'+r.symbol+'<span class="tk-arrow">↗</span></a>'+'<a class="tale-link" href="/tale/'+r.symbol+'" title="Tale of the Ticker — chart read, levels, gate status">📜</a>'+kevBadge+botBadge+'</td>'
      +'<td class="price-cell">$'+r.price.toFixed(2)+ahP+'</td>'
      +'<td><span class="gap-pill '+gapClass+'">+'+r.change_pct.toFixed(1)+'%</span></td>'
      +'<td class="'+floatClass+'">'+r.float_label+'</td>'
      +'<td>'+relVol+'</td>'
      +'<td class="evening-col" style="'+eveningStyle+'"><span class="'+(shortClass?'gap-pill '+shortClass:'')+'">'+shortPct+'</span></td>'
      +'<td class="evening-col" style="'+eveningStyle+'">'+dayRange+'</td>'
      +'<td>'+mktcap+'</td>'
      +'<td><span class="source-badge">'+r.source+'</span></td>'
      +'</tr>';
  }).join('');
  if(_filterOn) applyFilter(true);
}

function runScan(){
  var btn=document.getElementById('scan-btn');
  var loader=document.getElementById('loader');
  var wrap=document.getElementById('table-wrap');
  btn.disabled=true;btn.textContent='Scanning…';
  loader.classList.add('active');wrap.style.display='none';
  document.getElementById('errors-wrap').innerHTML='';

  fetch('/api/scan')
    .then(function(r){return r.json()})
    .then(function(d){renderResults(d)})
    .catch(function(e){
      document.getElementById('errors-wrap').innerHTML=
        '<div class="errors">Scan failed: '+e+'</div>';
    })
    .finally(function(){
      btn.disabled=false;btn.innerHTML='&#8635; Scan now';
      loader.classList.remove('active');wrap.style.display='';
    });
}

function renderResults(d){
  var rows=d.results||[];
  var errs=d.errors||[];

  // Stats
  document.getElementById('s-count').textContent=rows.length||'0';
  if(rows.length){
    var gaps=rows.map(function(r){return r.change_pct});
    var avg=(gaps.reduce(function(a,b){return a+b},0)/gaps.length).toFixed(1);
    document.getElementById('s-gap').textContent='+'+avg+'%';

    var floats=rows.filter(function(r){return r.float_shares>0}).map(function(r){return r.float_shares});
    if(floats.length){
      var minF=Math.min.apply(null,floats);
      document.getElementById('s-float').textContent=fmtM(minF);
    }

    var vols=rows.filter(function(r){return r.relative_volume}).map(function(r){return r.relative_volume});
    if(vols.length){
      document.getElementById('s-vol').textContent=Math.max.apply(null,vols).toFixed(1)+'×';
    }
  }

  // Market state label
  var stateLabels = {
    premarket:   {sub:'Pre-market RVOL + momentum',     title:'RVOL + momentum — pre-market'},
    open:        {sub:'Live RVOL + momentum candidates', title:'RVOL + momentum — live market'},
    after_hours: {sub:"Tomorrow's watchlist candidates",  title:"Tomorrow's Watchlist — after hours"},
  };
  var lbl = stateLabels[d.market_state] || stateLabels['open'];
  document.getElementById('scanner-sub').textContent  = lbl.sub;
  document.getElementById('section-title').textContent = lbl.title;

  // After-hours badge
  var liveBadge = document.getElementById('live-badge');
  if(d.market_state==='after_hours'){
    liveBadge.textContent='Evening';
    liveBadge.style.background='#2d1f00';liveBadge.style.color='#d29922';
  } else {
    liveBadge.textContent='Live';
    liveBadge.style.background='#1a3a2a';liveBadge.style.color='#3fb950';
  }

  // Toggle evening-only columns
  _afterHours = d.market_state==='after_hours';
  document.querySelectorAll('.evening-col').forEach(function(el){
    el.style.display = _afterHours ? '' : 'none';
  });

  // Timestamp
  var now=new Date(d.updated);
  document.getElementById('ts').textContent='Updated '+now.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',timeZoneName:'short'});

  // Cache and render table
  _scanData = rows;
  _sortCol = 'change_pct'; _sortAsc = false;
  var tbody=document.getElementById('tbody');
  var colSpan = _afterHours ? 9 : 7;
  if(!rows.length){
    tbody.innerHTML='<tr><td colspan="'+colSpan+'" class="empty">No candidates found. Markets may be closed or pre-market data unavailable.</td></tr>';
    return;
  }
  var botCount=rows.filter(function(r){return (r.price<=20)&&(r.float_shares>0)&&(r.float_shares<20000000);}).length;
  document.getElementById('s-bot-count').textContent=botCount?botCount+' bot candidates':'';
  renderRows(rows);

  // Errors
  if(errs.length){
    document.getElementById('errors-wrap').innerHTML=
      '<div class="errors">⚠ '+errs.join(' | ')+'</div>';
  }
}

// Kev's picks — highest-signal names, marked distinctly (backed by his stored levels)
var _kevSet=new Set(), _kevLevels={};
function loadKev(){
  return fetch('/api/kev_watchlist').then(function(r){return r.json()}).then(function(d){
    if(!d||typeof d!=='object') return;
    var dates=Object.keys(d).filter(function(k){return /^\d{4}-\d{2}-\d{2}$/.test(k)});
    if(!dates.length) return;
    var latest=dates.sort()[dates.length-1];
    (d[latest]||[]).forEach(function(t){_kevSet.add(String(t).toUpperCase())});
    var lv=(d._levels&&d._levels[latest])||{};
    Object.keys(lv).forEach(function(t){
      var x=lv[t]||{}, parts=[];
      if(x.break) parts.push('break '+x.break);
      if(x.confirm) parts.push('confirm '+x.confirm);
      if(x.targets&&x.targets.length) parts.push('targets '+x.targets.join(', '));
      _kevLevels[String(t).toUpperCase()]='KEV — '+(parts.join(' / ')||'watchlist pick');
    });
  }).catch(function(){});
}

// Auto-scan on load (load Kev's list first so his picks render marked)
loadKev().then(runScan);

// Auto-refresh: 5 min during market hours, 15 min after hours
setInterval(function(){
  var etHour = new Date().toLocaleString('en-US',{timeZone:'America/New_York',hour:'numeric',hour12:false});
  var h = parseInt(etHour);
  if(h>=4&&h<17){ runScan(); }
}, 5*60*1000);
setInterval(function(){
  var etHour = new Date().toLocaleString('en-US',{timeZone:'America/New_York',hour:'numeric',hour12:false});
  var h = parseInt(etHour);
  if(h>=17||h<4){ runScan(); }
}, 15*60*1000);


</script>

</body>
</html>
"""

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML.replace("</head>", THEME_SNIPPET + "</head>"))


@app.route("/api/scan")
def api_scan():
    results, errors = run_scan()
    now_et, _, _, _, market_state = _market_state()
    return jsonify({
        "results":      results,
        "errors":       errors,
        "updated":      now_et.isoformat(),
        "count":        len(results),
        "market_state": market_state,
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now(EASTERN).isoformat()})




# ── Trades Dashboard API ───────────────────────────────────────────────────────

@app.route("/api/record_trade", methods=["POST"])
def record_trade():
    """Called by the bot after each completed trade session."""
    secret = request.headers.get("X-Dashboard-Secret", "")
    if secret != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    # Idempotency: if this trade_id was already recorded (e.g. normal exit logged, then a
    # failed clear caused recovery to re-post it), skip the duplicate.
    tid = data.get("trade_id")
    _store_lock.acquire()   # 7/11 A2: dedup-check→append→save is atomic (concurrent watchdog+worker posts raced)
    try:
        if tid and any(t.get("trade_id") == tid for t in _trades):
            return jsonify({"status": "ok", "deduped": True, "total_trades": len(_trades)})
        trade = {
        "date":          data.get("date", datetime.now(EASTERN).strftime("%Y-%m-%d")),
        "ticker":        data.get("ticker", "UNKNOWN"),
        "trade_id":      tid,
        "entry":         round(float(data.get("entry", 0)), 2),
        "exit":          round(float(data.get("exit", 0)), 2),
        "shares":        int(data.get("shares", 0)),
        "pnl":           round(float(data.get("pnl", 0)), 2),
        "pnl_pct":       round(float(data.get("pnl_pct", 0)), 2),
        "exit_reason":   data.get("exit_reason", ""),
        "confidence":    data.get("confidence", ""),
        "float_shares":  data.get("float_shares", ""),
        "position_size": round(float(data.get("position_size", 0)), 2),
        # Realistic-sizing calibration fields (7/11): initial stop, per-trade risk, and spread-based slippage estimate
        "stop_loss":      data.get("stop_loss"),
        "risk_per_share": data.get("risk_per_share"),
        "planned_risk":   data.get("planned_risk"),
        "est_slippage":   data.get("est_slippage"),
        # DATA-ONLY: 90 EMA study — where entry sat vs the 90 EMA. Not used for anything yet.
        "entry_ema90":        data.get("entry_ema90"),
        "entry_vs_ema90_pct": data.get("entry_vs_ema90_pct"),
        # DATA-ONLY: L1 order-book at entry — study whether adverse book conditions predict
        # losers (the evidence that would justify paying for TotalView depth). Not gating anything.
        "entry_l1_ratio":     data.get("entry_l1_ratio"),
        "entry_ask_size":     data.get("entry_ask_size"),
        "entry_bid_size":     data.get("entry_bid_size"),
        "entry_l1_spread":    data.get("entry_l1_spread"),
        # Room to next supply at entry (Kev's master filter)
        "entry_room_rr":      data.get("entry_room_rr"),
        "entry_room_pct":     data.get("entry_room_pct"),
        "entry_next_supply":  data.get("entry_next_supply"),
        "entry_supply_src":   data.get("entry_supply_src"),
        # Story fields (7/13) — entry signal, scale-outs, and peak for the plain-English trade story
        "entry_type":         data.get("entry_type", ""),
        "reclaim_subtype":            data.get("reclaim_subtype"),
        "entry_vs_session_vwap_pct":  data.get("entry_vs_session_vwap_pct"),
        # Kev-level anchoring study (7/13): his stated level + our entry's distance from it
        "kev_level":                  data.get("kev_level"),
        "entry_vs_kev_level_pct":     data.get("entry_vs_kev_level_pct"),
        "partial_fills":      data.get("partial_fills") or [],
        "highest":            data.get("highest"),
        "entry_front_side":   data.get("entry_front_side"),
        "entry_ema9":         data.get("entry_ema9"),
        "entry_ema20":        data.get("entry_ema20"),
        "recorded_at":   datetime.now(EASTERN).isoformat(),
        }
        # ── WHITELIST-STRIP CLASS KILLER (7/22, 3rd occurrence of this bug family): the explicit
        # dict above silently DROPPED any field the bot added later — entry_vel5 (shipped 7/21)
        # and day_gain_at_entry (shipped 7/22) posted on every trade and never landed once (all
        # None on 7/22's six records while the decision rows carried the values). Same disease as
        # the #77 post_level ledger stripping. Unknown keys now pass through; the typed/rounded
        # known fields above keep precedence via setdefault. Payload source is our own bot behind
        # the dashboard secret — pass-through is safe here.
        for _k, _v in (data or {}).items():
            if _k != "account_balance":
                trade.setdefault(_k, _v)
        _trades.append(trade)
        if data.get("account_balance"):
            _account["balance"] = round(float(data["account_balance"]), 2)
            _account["updated"] = datetime.now(EASTERN).strftime("%I:%M %p ET")
        _save_trades()
        print(f"📋 Trade recorded: {trade['ticker']} {trade['pnl']:+.2f}")
        return jsonify({"status": "ok", "total_trades": len(_trades)})
    finally:
        _store_lock.release()


@app.route("/api/update_account", methods=["POST"])
def update_account():
    """Called by the bot to update the current account balance."""
    secret = request.headers.get("X-Dashboard-Secret", "")
    if secret != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    _account["balance"] = round(float(data.get("balance", _account.get("balance", 0))), 2)
    _account["updated"] = datetime.now(EASTERN).strftime("%I:%M %p ET")
    _save_trades()
    return jsonify({"status": "ok", "balance": _account["balance"]})


@app.route("/api/market", methods=["GET", "POST"])
def market_data_api():
    """GET → serve the cached market snapshot for the dashboard strip. POST (bot, Webull-sourced) → update it.
    indices = [{"label":"S&P 500","chg":0.42,"price":6050.1}, ...]; news = [{"title":..,"src":..}] (future)."""
    global _market
    if request.method == "POST":
        if request.headers.get("X-Dashboard-Secret", "") != API_SECRET:
            return jsonify({"error": "unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        if isinstance(data.get("indices"), list):
            _market["indices"] = data["indices"]
        if isinstance(data.get("news"), list):
            _market["news"] = data["news"]
        _market["updated"] = datetime.now(EASTERN).strftime("%I:%M %p ET")
        try:    _MARKET_FILE.write_text(json.dumps(_market))
        except Exception: pass
        return jsonify({"status": "ok"})
    return jsonify(_market)


@app.route("/api/account_balance", methods=["GET"])
def get_account_balance_api():
    return jsonify({"balance": _account.get("balance", 0.0), "updated": _account.get("updated", "")})


@app.route("/api/trades")
def api_trades():
    return jsonify({"trades": _trades, "stats": _compute_stats(), "account": _account})

@app.route("/api/trades/clear", methods=["POST"])
def clear_trades():
    # 7/11 F3: mutate under the store lock (an in-flight record_trade raced the rebind)
    global _trades
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    with _store_lock:
        _trades = []
    _save_trades()
    return jsonify({"status": "ok", "total_trades": 0})



# Dated watchlist history — persist each day's watched tickers so the daily scorecard can reliably look up
# "what did the bot watch on date X" (the live _watching snapshot below is overwritten + cleared at session end).
WATCH_HIST_FILE = pathlib.Path("/data/watch_history.json") if pathlib.Path("/data").exists() else pathlib.Path("/tmp/watch_history.json")
_watch_hist = {}
if WATCH_HIST_FILE.exists():
    try:    _watch_hist = json.loads(WATCH_HIST_FILE.read_text())
    except Exception: _watch_hist = {}

@app.route("/api/watching", methods=["POST"])
def save_watching():
    global _watching
    data = request.get_json(silent=True) or {}
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    _watching = {
        "tickers":    data.get("tickers", []),
        "status":     data.get("status", "watching"),
        "started_at": data.get("started_at", datetime.now(EASTERN).isoformat()),
        "updated":    datetime.now(EASTERN).isoformat(),
    }
    # persist the day's watched tickers as a UNION across the session (the list grows via 5-min rescans)
    try:
        _today = datetime.now(EASTERN).strftime("%Y-%m-%d")
        prev = set(_watch_hist.get(_today, []))
        _watch_hist[_today] = sorted(prev | {str(t).upper().strip() for t in (_watching["tickers"] or []) if str(t).strip()})
        with _store_lock: _atomic_write_text(WATCH_HIST_FILE, json.dumps(_watch_hist, indent=2))
    except Exception as e:
        print(f"⚠️  watch-history persist skipped: {e}")
    print(f"👀 Watch list updated: {_watching['tickers']} [{_watching['status']}]")
    return jsonify({"ok": True})

@app.route("/api/watching", methods=["GET"])
def get_watching():
    # ?date=YYYY-MM-DD → that day's persisted watchlist (for the daily scorecard); else the live snapshot.
    date = (request.args.get("date") or "").strip()
    if date:
        return jsonify({"date": date, "tickers": _watch_hist.get(date, [])})
    # include live trade state, but only if fresh (bot stops posting when the trade ends)
    ts = _trade_state
    fresh = bool(ts) and (time.time() - ts.get("_recv", 0) <= 90)
    return jsonify({**_watching, "trade_state": (ts if fresh else None)})


# ── #99 READ LIST — the bot posts its Move%-ranked top-20 gappers (+Kev, first) each scan; the
#    newcomer reader consumes this IN ORDER so the biggest movers get read first (Marcos 7/23). ──
_read_list = {"tickers": [], "updated": None}

@app.route("/api/read_list", methods=["POST"])
def set_read_list():
    global _read_list
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    _read_list = {"tickers": [str(t).upper().strip() for t in (data.get("tickers") or []) if str(t).strip()],
                  "updated": datetime.now(EASTERN).isoformat()}
    return jsonify({"status": "ok", "n": len(_read_list["tickers"])})

@app.route("/api/read_list", methods=["GET"])
def get_read_list():
    return jsonify(_read_list)


@app.route("/api/trade_state", methods=["POST"])
def set_trade_state():
    """Live state of the active trade, posted fire-and-forget by the bot each monitor loop."""
    global _trade_state
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    data["_recv"] = time.time()
    data["updated"] = datetime.now(EASTERN).strftime("%I:%M:%S %p ET")
    _trade_state = data
    return jsonify({"status": "ok"})


# ── Durable open-trade state (survives a bot crash/restart/redeploy) ──
# The bot has no /data volume of its own, so it persists open positions HERE.
# On startup the bot pulls these back so an interrupted trade still reaches a recorded exit.
OPEN_TRADES_FILE = pathlib.Path("/data/open_trades.json") if pathlib.Path("/data").exists() else pathlib.Path("/tmp/open_trades.json")
_open_trades: dict = {}

def _load_open_trades():
    global _open_trades
    if OPEN_TRADES_FILE.exists():
        try:
            _open_trades = json.loads(OPEN_TRADES_FILE.read_text())
        except Exception:
            _open_trades = {}

def _save_open_trades_file():
    with _store_lock:
      try:
        _atomic_write_text(OPEN_TRADES_FILE, json.dumps(_open_trades, indent=2))
      except Exception as e:
        print(f"⚠️  Could not save open trades: {e}")

_load_open_trades()


@app.route("/api/open_trade", methods=["POST"])
def upsert_open_trade():
    """Bot persists/updates an open position here each monitor loop (durable recovery state)."""
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    tk = (data.get("ticker") or "").upper()
    if not tk:
        return jsonify({"error": "no ticker"}), 400
    data["updated"] = datetime.now(EASTERN).isoformat()
    # MERGE: entry posts static context (entry_type, confidence, size...), monitor posts
    # dynamic state (remaining, partials, stop, highest, tier) — together = full record.
    _open_trades.setdefault(tk, {}).update(data)
    _save_open_trades_file()
    return jsonify({"status": "ok"})


@app.route("/api/open_trade/clear", methods=["POST"])
def clear_open_trade():
    """Bot removes a position here once it has reached a recorded exit."""
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    tk = (request.get_json(silent=True) or {}).get("ticker", "").upper()
    if tk in _open_trades:
        del _open_trades[tk]
        _save_open_trades_file()
    return jsonify({"status": "ok", "remaining": list(_open_trades.keys())})


@app.route("/api/open_trades", methods=["GET"])
def get_open_trades():
    return jsonify({"open_trades": list(_open_trades.values())})


# ── Room gate: rejections (entries blocked for <2:1 room) — to AUDIT the supply detection ──
ROOM_SKIPS_FILE = pathlib.Path("/data/room_skips.json") if pathlib.Path("/data").exists() else pathlib.Path("/tmp/room_skips.json")
_room_skips: list = []
if ROOM_SKIPS_FILE.exists():
    try:    _room_skips = json.loads(ROOM_SKIPS_FILE.read_text())
    except Exception: _room_skips = []

@app.route("/api/room_skip", methods=["POST"])
def add_room_skip():
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    d["recorded_at"] = datetime.now(EASTERN).isoformat()
    _room_skips.append(d)
    try:
        with _store_lock:
            _atomic_write_text(ROOM_SKIPS_FILE, json.dumps(_room_skips[-500:], indent=2))
    except Exception as e: print(f"⚠️  Could not save room_skips: {e}")
    return jsonify({"status": "ok", "total": len(_room_skips)})

# ── Per-candidate DECISION log — the full "why did/didn't we trade X" timeline (observability) ──
# Every watched candidate's disposition each evaluation (throttled bot-side): below_vwap, consolidating,
# broke_not_flat (the SDOT/IVF detection gap), broke_below_vwap, broke_no_room, entered_*, spread_reject, etc.
DECISIONS_FILE = pathlib.Path("/data/decisions.json") if pathlib.Path("/data").exists() else pathlib.Path("/tmp/decisions.json")
DECISIONS_DIR  = DECISIONS_FILE.parent   # per-day append-only JSONL archive lives here = the DURABLE record
_decisions_snapshot_last = 0.0           # last time the recent-N snapshot json was rewritten (throttled to ~60s)
_decisions: list = []
if DECISIONS_FILE.exists():
    try:    _decisions = json.loads(DECISIONS_FILE.read_text())
    except Exception: _decisions = []

def _persist_decisions(records):
    """Durably store decision records: (1) append-only per-day JSONL on /data (never trimmed = the real
    archive), (2) the in-memory rolling cache + a recent-N json snapshot for fast /api/decisions queries."""
    now = datetime.now(EASTERN); by_day = {}
    for d in records:
        if not isinstance(d, dict):
            continue
        d.setdefault("recorded_at", now.isoformat())
        d.setdefault("date", now.strftime("%Y-%m-%d"))
        d.setdefault("time", now.strftime("%I:%M:%S %p"))
        _decisions.append(d)
        by_day.setdefault(d["date"], []).append(d)
    for day, recs in by_day.items():                      # the DURABLE archive — append-only, per day
        try:
            with open(DECISIONS_DIR / f"decisions-{day}.jsonl", "a") as f:
                for d in recs:
                    f.write(json.dumps(d) + "\n")
        except Exception as e:
            print(f"⚠️  decisions JSONL append failed: {e}")
    # recent-N snapshot for GET-cache recovery — THROTTLED to ~60s (the per-day JSONL above is the durable
    # record; no need to rewrite the whole 8k-record snapshot on every 5s batch — wasteful I/O).
    global _decisions_snapshot_last
    if time.time() - _decisions_snapshot_last >= 60:
        try:
            with _store_lock: _atomic_write_text(DECISIONS_FILE, json.dumps(_decisions[-8000:], indent=2))
            _decisions_snapshot_last = time.time()
        except Exception as e:
            print(f"⚠️  Could not save decisions snapshot: {e}")
    if len(_decisions) > 8000:
        del _decisions[:len(_decisions) - 8000]

@app.route("/api/decision", methods=["POST"])
def add_decision():
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    _persist_decisions([request.get_json(silent=True) or {}])
    return jsonify({"status": "ok", "total": len(_decisions)})

@app.route("/api/decisions/batch", methods=["POST"])
def add_decisions_batch():
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    recs = (request.get_json(silent=True) or {}).get("records", [])
    if not isinstance(recs, list):
        return jsonify({"error": "records must be a list"}), 400
    _persist_decisions(recs)
    return jsonify({"status": "ok", "received": len(recs), "total": len(_decisions)})

@app.route("/api/decisions", methods=["GET"])
def get_decisions():
    """Query the decision timeline. ?ticker=SDOT &date=2026-06-26 &status=broke_not_flat &limit=200"""
    tk     = (request.args.get("ticker") or "").upper()
    date   = request.args.get("date")
    status = request.args.get("status")
    limit  = int(request.args.get("limit", 300))
    rows = _decisions
    if tk:     rows = [r for r in rows if (r.get("ticker") or "").upper() == tk]
    if date:   rows = [r for r in rows if r.get("date") == date]
    if status: rows = [r for r in rows if r.get("status") == status]
    by_status = {}
    for r in rows:
        by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1
    return jsonify({"total_all": len(_decisions), "matched": len(rows),
                    "by_status": by_status, "rows": rows[-limit:]})

@app.route("/api/decisions_archive", methods=["GET"])
def get_decisions_archive():
    """Read the DURABLE per-day JSONL archive on /data (survives dashboard redeploys, unlike the in-memory
    cache /api/decisions reads). ?date=YYYY-MM-DD [&status=triggered_flat_top] [&limit=5000]. Returns the
    day's records + a status histogram + a time-of-day histogram of 'triggered_*' entries (the prime-window check)."""
    date   = request.args.get("date")
    status = request.args.get("status")
    limit  = int(request.args.get("limit", 5000))
    if not date:
        return jsonify({"error": "need ?date=YYYY-MM-DD"}), 400
    fp = DECISIONS_DIR / f"decisions-{date}.jsonl"
    if not fp.exists():
        try: avail = sorted(p.name for p in DECISIONS_DIR.glob("decisions-*.jsonl"))
        except Exception: avail = []
        return jsonify({"error": f"no archive for {date}", "available": avail})
    rows = []
    try:
        with open(fp) as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try: rows.append(json.loads(line))
                except Exception: pass
    except Exception as e:
        return jsonify({"error": str(e)})
    if status:
        rows = [r for r in rows if r.get("status") == status]
    by_status, trig_hour = {}, {}
    for r in rows:
        by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1
        if str(r.get("status", "")).startswith("triggered"):
            hm = str(r.get("time", ""))            # "%I:%M:%S %p" e.g. "09:47:12 AM"
            key = hm[:2] + hm[-3:] if len(hm) >= 5 else hm  # coarse hour+AM/PM bucket
            trig_hour[key] = trig_hour.get(key, 0) + 1
    return jsonify({"date": date, "total": len(rows), "by_status": by_status,
                    "triggered_by_hour": trig_hour, "rows": rows[-limit:]})

# ── DATA WAREHOUSE: per-day/per-ticker 1-min bar archive on /data — the permanent dataset the harness
# backtests against (so we're not re-fetching from a 7-day API). POST to save, GET to retrieve/list. ──
BARS_DIR = (pathlib.Path("/data") if pathlib.Path("/data").exists() else pathlib.Path("/tmp")) / "bars"

def _merge_series(existing, incoming):
    """7/15 recorder audit (Fable): suffixed series ('~10s', '~vwap') have TWO writers — the bot's
    B12 dumps (RTH-only subset) and the recorder (premarket-inclusive). File overwrite = last writer
    wins = the bot's dump can ERASE recorder premarket data. Union by bar 'time' instead: incoming
    wins on the same timestamp, everything else is kept. Order-independent, idempotent, and enables
    the recorder's incremental persists (tiny payloads instead of whole-day re-sends)."""
    by_t = {str(b.get("time")): b for b in existing if isinstance(b, dict) and b.get("time")}
    for b in incoming:
        if isinstance(b, dict) and b.get("time"):
            by_t[str(b["time"])] = b
    return [by_t[k] for k in sorted(by_t)]

def _save_bars_file(daydir, ticker, bars):
    """Shared save with merge semantics for multi-writer suffixed series; plain overwrite otherwise."""
    path = daydir / f"{ticker}.json"
    if "~" in ticker and path.exists():
        try:
            bars = _merge_series(json.loads(path.read_text()), bars)
        except Exception:
            pass   # unreadable existing file → fall through to plain write
    path.write_text(json.dumps(bars))
    return len(bars)

@app.route("/api/bars", methods=["POST"])
def save_bars():
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    date = d.get("date"); ticker = (d.get("ticker") or "").upper(); bars = d.get("bars")
    if not (date and ticker and isinstance(bars, list)):
        return jsonify({"error": "need date, ticker, bars[]"}), 400
    try:
        daydir = BARS_DIR / date; daydir.mkdir(parents=True, exist_ok=True)
        n = _save_bars_file(daydir, ticker, bars)
        return jsonify({"status": "ok", "ticker": ticker, "bars": n})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/bars_bulk", methods=["POST"])
def save_bars_bulk():
    """7/15 SIGTERM-flush receiver: ONE gzipped POST carrying every in-memory 10s series from a dying
    bot process (deploys/restarts must never vaporize collection — the bot container has no volume).
    Body (gzip JSON): {date, reason, series: {ticker: [bars...]}}. Writes each ticker via the same
    per-file layout as /api/bars; idempotent (POST overwrites)."""
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    try:
        raw = request.get_data()
        if request.headers.get("Content-Encoding") == "gzip" or (raw[:2] == b"\x1f\x8b"):
            import gzip as _gz
            raw = _gz.decompress(raw)
        d = json.loads(raw)
        date = d.get("date"); series = d.get("series") or {}
        if not (date and isinstance(series, dict)):
            return jsonify({"error": "need date, series{}"}), 400
        daydir = BARS_DIR / date; daydir.mkdir(parents=True, exist_ok=True)
        saved = 0
        for ticker, bars in series.items():
            if not (ticker and isinstance(bars, list) and bars):
                continue
            _save_bars_file(daydir, ticker.upper(), bars)   # merge for suffixed multi-writer series
            saved += 1
        print(f"🛟 bars_bulk: {saved} series saved for {date} (reason={d.get('reason')})")
        return jsonify({"status": "ok", "saved": saved})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/bars_backfill")
def bars_backfill():
    if not _endpoint_authed():
        return jsonify({"error": "unauthorized — pass X-Dashboard-Secret header or ?key="}), 401
    """Re-fetch archived names WITH extended hours (trading_sessions=RTH,PRE,ATH) and overwrite the RTH-only
    files, so the past week's archive gains premarket/after-hours bars (within the ~7-day API window).
    ?date=YYYY-MM-DD [&ticker=X] [&commit=1] [&count=7000]. Dry-run (report coverage) unless commit=1."""
    import datetime as dtm
    date = request.args.get("date")
    only = (request.args.get("ticker") or "").upper().strip()
    commit = request.args.get("commit", "0") == "1"
    count = min(int(request.args.get("count", "1650")), 1650)   # API caps count at 1650
    et_fmt = request.args.get("et_fmt", "ms")                    # end_time format probe: ms | s | iso
    if not date:
        return jsonify({"error": "need ?date=YYYY-MM-DD"})
    dc = _make_data_client()
    if not dc:
        return jsonify({"error": "no data client"})
    ET = dtm.timezone(dtm.timedelta(hours=-4))
    # anchor the 1650-bar window to END just after the target date (so 6/29 sits inside the window, not off the back)
    _end_dt = dtm.datetime.strptime(date, "%Y-%m-%d").replace(hour=20, minute=1, tzinfo=ET) + dtm.timedelta(days=0)
    end_time = (int(_end_dt.timestamp() * 1000) if et_fmt == "ms"
                else int(_end_dt.timestamp()) if et_fmt == "s"
                else _end_dt.strftime("%Y-%m-%dT%H:%M:%S%z"))
    daydir = BARS_DIR / date
    if only:
        tickers = [only]
    elif daydir.exists():
        tickers = sorted(p.stem for p in daydir.glob("*.json"))
    else:
        return jsonify({"error": f"no archive dir for {date}"})
    results = []; enriched = 0
    for tk in tickers:
        try:
            resp = dc.market_data.get_history_bar(symbol=tk, category="US_STOCK", timespan="M1",
                                                  count=str(count), trading_sessions=["RTH", "PRE", "ATH"],
                                                  end_time=end_time)
            if getattr(resp, "status_code", 0) != 200:
                results.append({"tk": tk, "err": f"HTTP {getattr(resp,'status_code',None)}"}); continue
            raw = resp.json()
            items = raw if isinstance(raw, list) else (raw.get("data", {}) if isinstance(raw, dict) else {})
            if isinstance(items, dict):
                items = items.get("items", items)
            dayitems = []; pre = rth = ath = 0
            for b in (items or []):
                t = b.get("time") or b.get("timeStamp") or ""
                try:
                    d = dtm.datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dtm.timezone.utc).astimezone(ET)
                except Exception:
                    continue
                if str(d.date()) != date:
                    continue
                dayitems.append(b)
                if d.time() < dtm.time(9, 30): pre += 1
                elif d.time() <= dtm.time(16, 0): rth += 1
                else: ath += 1
            info = {"tk": tk, "day_bars": len(dayitems), "pre": pre, "rth": rth, "ath": ath}
            if commit and dayitems:                      # store the FULL extended window in a SEPARATE _ext file
                daydir.mkdir(parents=True, exist_ok=True)  # (leaves the RTH archive the backtests use untouched)
                (daydir / f"{tk}__ext.json").write_text(json.dumps(items))
                enriched += 1; info["written"] = True
            results.append(info)
            time.sleep(0.12)                              # gentle on the token
        except Exception as e:
            results.append({"tk": tk, "err": str(e)})
    got_pre = [r for r in results if r.get("pre", 0) > 0]
    return jsonify({"date": date, "commit": commit, "tickers": len(tickers),
                    "with_premarket": len(got_pre), "enriched": enriched, "results": results})

@app.route("/api/bars", methods=["GET"])
def get_bars():
    date = request.args.get("date"); ticker = (request.args.get("ticker") or "").upper()
    _sfx = "__ext" if request.args.get("ext") else ""   # ext=1 → the extended-hours backfill file
    if date and ticker:
        f = BARS_DIR / date / f"{ticker}{_sfx}.json"
        if f.exists():
            return jsonify({"date": date, "ticker": ticker, "bars": json.loads(f.read_text())})
        return jsonify({"error": "not found"}), 404
    out = {}                              # no args → list what's archived
    if BARS_DIR.exists():
        for dd in sorted(BARS_DIR.iterdir()):
            if dd.is_dir():
                out[dd.name] = sorted(f.stem for f in dd.glob("*.json"))
    return jsonify({"days": len(out), "archived": out})

@app.route("/api/daily", methods=["GET"])
def api_daily():
    """Webull DAILY bars for an ARBITRARY ticker — covers the small-caps free yfinance drops (delisted/absent).
    Read-only market data (no archive; hits the Webull SDK live). ?ticker=X [&count=250]. Used to grade Kev's
    picks (did they run?) with real coverage. Gentle: one ticker per call — the client paces itself."""
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker:
        return jsonify({"error": "need ?ticker="}), 400
    try:
        count = min(int(request.args.get("count", "250")), 800)
    except ValueError:
        count = 250
    dc = _make_data_client()
    if not dc:
        return jsonify({"error": "no data client"}), 503
    try:
        resp = dc.market_data.get_history_bar(symbol=ticker, category="US_STOCK", timespan="D", count=str(count))
        if getattr(resp, "status_code", 0) != 200:
            return jsonify({"error": f"HTTP {getattr(resp, 'status_code', None)}", "ticker": ticker}), 502
        raw = resp.json()
        items = raw if isinstance(raw, list) else (raw.get("data", {}) if isinstance(raw, dict) else {})
        if isinstance(items, dict):
            items = items.get("items", items)
        bars = []
        for b in (items or []):
            t = b.get("time") or b.get("timeStamp") or b.get("tradeTime") or ""
            bars.append({"date": str(t)[:10], "open": b.get("open"), "high": b.get("high"),
                         "low": b.get("low"), "close": b.get("close"), "volume": b.get("volume")})
        return jsonify({"ticker": ticker, "count": len(bars), "bars": bars})
    except Exception as e:
        return jsonify({"error": str(e), "ticker": ticker}), 500

@app.route("/api/minute_ext", methods=["GET"])
def api_minute_ext():
    """Webull M1 bars INCLUDING extended hours for one ticker — the reader's gap-awareness feed
    (7/20: reads were AH/PM-blind; Kev exam 0/3 within-2% — BXBL's 14.75 lived only in Sunday AH).
    Bars carry trading_session (PRE/RTH/ATH) so the client can slice sessions. ?ticker=X [&count=1200].
    Same gentle contract as /api/daily: one ticker per call, client paces."""
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker:
        return jsonify({"error": "need ?ticker="}), 400
    try:
        count = min(int(request.args.get("count", "1200")), 1200)
    except ValueError:
        count = 1200
    dc = _make_data_client()
    if not dc:
        return jsonify({"error": "no data client"}), 503
    try:
        resp = dc.market_data.get_history_bar(symbol=ticker, category="US_STOCK", timespan="M1",
                                              count=str(count),
                                              trading_sessions=["RTH", "PRE", "ATH"])
        if getattr(resp, "status_code", 0) != 200:
            return jsonify({"error": f"HTTP {getattr(resp, 'status_code', None)}", "ticker": ticker}), 502
        raw = resp.json()
        items = raw if isinstance(raw, list) else (raw.get("data", {}) if isinstance(raw, dict) else {})
        if isinstance(items, dict):
            items = items.get("items", items)
        bars = []
        for b in (items or []):
            bars.append({"time": b.get("time") or b.get("timeStamp") or b.get("tradeTime") or "",
                         "open": b.get("open"), "high": b.get("high"), "low": b.get("low"),
                         "close": b.get("close"), "volume": b.get("volume"),
                         "session": b.get("trading_session") or b.get("tradingSession") or ""})
        return jsonify({"ticker": ticker, "count": len(bars), "bars": bars,
                        "v": "ext2"})   # deploy marker: absent ⇒ stale build running
    except Exception as e:
        return jsonify({"error": str(e), "ticker": ticker, "v": "ext2"}), 500

@app.route("/api/stream_check", methods=["GET"])
def api_stream_check():
    if not _endpoint_authed():
        return jsonify({"error": "unauthorized — pass X-Dashboard-Secret header or ?key="}), 401
    """DIAGNOSTIC (7/5): confirm the OpenAPI real-time STREAMING actually works with our creds + the free
    Nasdaq Basic entitlement. Connects the official DataStreamingClient, subscribes to a symbol, reports:
    connected? subscribe accepted? messages received? Read-only (no orders). Market-closed → connect+subscribe
    still confirm the entitlement is wired; live ticks only flow during market hours. ?ticker=AAPL&secs=6."""
    ticker = (request.args.get("ticker") or "AAPL").upper().strip()
    try:
        secs = min(int(request.args.get("secs", "6")), 20)
    except ValueError:
        secs = 6
    res = {"ticker": ticker, "token_ok": None, "token_err": None, "connected": None,
           "subscribed": None, "messages": 0, "sample": None, "error": None}
    client = None
    try:
        from webull.data.data_streaming_client import DataStreamingClient
        from webull.data.quotes.subscribe.payload_type import PAYLOAD_TYPE_QUOTE
        from webull.core.utils.common import get_uuid
        # 1) Use the EXISTING stored token DIRECTLY — do NOT refresh/verify (that re-triggers 2FA, which
        #    is what failed last time). This is the same token the data API uses successfully.
        import pathlib as _pl
        # Prefer the FRESH minted token in token.txt (?token= overrides); do NOT _pre_populate (that clobbers it).
        _token = (request.args.get("token") or "").strip()
        if not _token:
            try:
                _token = (_pl.Path(WEBULL_TOKEN_DIR) / "token.txt").read_text().splitlines()[0].strip()
            except Exception:
                pass
        if not _token:
            _token = os.environ.get("WEBULL_ACCESS_TOKEN", "")
        res["token_ok"] = bool(_token)
        # Streaming client — point it at the token dir (so connect-time init loads the FRESH NORMAL token +
        # verifies it, which now SUCCEEDS without 2FA) and also set it directly.
        client = DataStreamingClient(WEBULL_APP_KEY, WEBULL_APP_SECRET, "us", get_uuid())
        try:
            client._api_client.set_token_dir(WEBULL_TOKEN_DIR)
            if _token:
                client._api_client.set_token(_token)
        except Exception as ie:
            res["error"] = f"token-inject: {ie}"
        _flags = {"sub": False}
        _msgs = {"n": 0, "last": None}
        def _on_msg(_c, topic, payload):
            _msgs["n"] += 1
            # MIRROR THE BOT's WebullStream._on_msg parse EXACTLY: SnapshotResult.basic.symbol + .price
            try:
                basic = getattr(payload, "basic", None)
                sym = getattr(basic, "symbol", None)
                px = getattr(payload, "price", None) or getattr(payload, "ext_price", None) or getattr(payload, "ovn_price", None)
                if _msgs["last"] is None:
                    _msgs["last"] = {"topic": str(topic)[:40], "symbol": str(sym), "price": str(px),
                                     "parsed_ok": bool(sym and px), "raw": str(payload)[:160]}
            except Exception as pe:
                if _msgs["last"] is None:
                    _msgs["last"] = {"parse_err": str(pe), "raw": str(payload)[:160]}
        client.on_quotes_message = _on_msg
        client.on_quotes_subscribe = lambda *a, **k: None    # THE bot's 7/6 crash fix — SDK REQUIRES this be set
        client.on_subscribe_success = lambda *a: _flags.__setitem__("sub", True)   # fires only on subscribe HTTP 200
        client.connect_and_loop_async(timeout=1, thread_daemon=True)
        time.sleep(5)                                        # let the MQTT connect settle
        res["connected"] = bool(client.get_connect_success())
        _sub = (request.args.get("sub") or "SNAPSHOT").upper()   # bot uses SNAPSHOT (.price); ?sub=QUOTE to compare
        res["sub_type"] = _sub
        client.subscribe([ticker], "US_STOCK", [_sub])
        time.sleep(max(3, secs))                             # collect any pushes
        res["subscribed"] = _flags["sub"] or bool(client.get_subscribe_success())
        res["messages"] = _msgs["n"]
        res["sample"] = _msgs["last"]
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {e}"
    finally:
        try:
            if client:
                client.disconnect(); client.loop_stop()
        except Exception:
            pass
    res["read"] = ("entitlement WIRED (connect+subscribe OK)" if (res["connected"] and res["subscribed"])
                   else "NOT confirmed — see error / flags")
    res["note"] = "live ticks (messages>0) only flow during market hours; connect+subscribe confirm the entitlement anytime"
    return jsonify(res)

@app.route("/api/mint_token", methods=["GET"])
def api_mint_token():
    if not _endpoint_authed():
        return jsonify({"error": "unauthorized — pass X-Dashboard-Secret header or ?key="}), 401
    """Mint a FRESH 2FA-verified Webull token server-side (the webull_setup.py flow). Uses only the app
    key/secret (already in env) — NO password. Creates a pending token → the USER approves the login
    notification in the Webull APP → we poll until NORMAL → write it to the token file so the running app
    uses it immediately. ⚠️ Also set it as WEBULL_ACCESS_TOKEN in Railway to survive redeploys."""
    import hmac, hashlib, base64, uuid, socket, requests, pathlib as _pl
    from urllib.parse import quote
    from datetime import datetime as _dt
    HOST = "api.webull.com"; BASE = f"https://{HOST}"
    def _hdrs(path, body_dict=None):
        ts = _dt.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        nonce = str(uuid.uuid5(uuid.NAMESPACE_URL, socket.gethostname() + str(uuid.uuid1())))
        h = {"Content-Type": "application/json", "x-app-key": WEBULL_APP_KEY, "x-timestamp": ts,
             "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1",
             "x-signature-nonce": nonce, "x-version": "v2"}
        sp = {"x-app-key": WEBULL_APP_KEY, "x-timestamp": ts, "x-signature-version": "1.0",
              "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "host": HOST}
        bs = None
        if body_dict is not None:
            bs = hashlib.md5(json.dumps(body_dict, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest().upper()
        s2s = f"{path}&" + "&".join(f"{k}={v}" for k, v in sorted(sp.items())) + (f"&{bs}" if bs else "")
        s2s = quote(s2s, safe='')
        h["x-signature"] = base64.b64encode(hmac.new((WEBULL_APP_SECRET + "&").encode(), s2s.encode(), hashlib.sha1).digest()).decode()
        return h
    res = {}
    if not (WEBULL_APP_KEY and WEBULL_APP_SECRET):
        return jsonify({"error": "app key/secret not set in env"}), 503
    try:
        # 1) create pending token → this triggers the login notification in the user's Webull app
        p = "/openapi/auth/token/create"; body = {}
        r = requests.post(f"{BASE}{p}", headers=_hdrs(p, body),
                          data=json.dumps(body, ensure_ascii=False, separators=(',', ':')), timeout=15)
        d = r.json()
        tok = (d.get("data") or {}).get("token") if isinstance(d.get("data"), dict) else \
              (d.get("data") if isinstance(d.get("data"), str) else d.get("token"))
        res["create_http"] = r.status_code; res["token"] = tok
        if not tok:
            res["error"] = "no token from create"; res["raw"] = d; return jsonify(res)
        res["action"] = "APPROVE the login notification in your Webull APP now (polling ~80s)"
        # 2) poll check until NORMAL (user approves in-app during this window)
        pc = "/openapi/auth/token/check"; bc = {"token": tok}; status = None
        for _ in range(16):
            rr = requests.post(f"{BASE}{pc}", headers=_hdrs(pc, bc),
                               data=json.dumps(bc, ensure_ascii=False, separators=(',', ':')), timeout=15)
            dd = rr.json(); status = dd.get("status") or (dd.get("data") or {}).get("status")
            if status in ("NORMAL", "INVALID", "EXPIRED"):
                break
            time.sleep(5)
        res["status"] = status
        if status == "NORMAL":
            d2 = _pl.Path(WEBULL_TOKEN_DIR); d2.mkdir(parents=True, exist_ok=True)
            exp = int(time.time() * 1000) + 14 * 24 * 3600 * 1000
            (d2 / "token.txt").write_text(f"{tok}\n{exp}\nNORMAL\n")
            res["stored"] = "token.txt updated (live now). ALSO set WEBULL_ACCESS_TOKEN in Railway to persist across redeploys."
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {e}"
    return jsonify(res)

@app.route("/api/refresh_token", methods=["GET"])
def api_refresh_token():
    if not _endpoint_authed():
        return jsonify({"error": "unauthorized — pass X-Dashboard-Secret header or ?key="}), 401
    """Refresh the Webull token PROGRAMMATICALLY (NO 2FA) via /openapi/auth/token/refresh. The 2FA create flow
    is ONE-TIME; this renews the session forever on a schedule. INVALID_SESSION on streaming = a stale session
    nobody refreshed — this is the fix. Returns + persists the new token. ?token= overrides the current one."""
    import hmac, hashlib, base64, uuid, socket, requests, pathlib as _pl
    from urllib.parse import quote
    from datetime import datetime as _dt
    HOST = "api.webull.com"; BASE = f"https://{HOST}"
    def _hdrs(path, body_dict=None):
        ts = _dt.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        nonce = str(uuid.uuid5(uuid.NAMESPACE_URL, socket.gethostname() + str(uuid.uuid1())))
        h = {"Content-Type": "application/json", "x-app-key": WEBULL_APP_KEY, "x-timestamp": ts,
             "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1",
             "x-signature-nonce": nonce, "x-version": "v2"}
        sp = {"x-app-key": WEBULL_APP_KEY, "x-timestamp": ts, "x-signature-version": "1.0",
              "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "host": HOST}
        bs = None
        if body_dict is not None:
            bs = hashlib.md5(json.dumps(body_dict, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest().upper()
        s2s = f"{path}&" + "&".join(f"{k}={v}" for k, v in sorted(sp.items())) + (f"&{bs}" if bs else "")
        s2s = quote(s2s, safe='')
        h["x-signature"] = base64.b64encode(hmac.new((WEBULL_APP_SECRET + "&").encode(), s2s.encode(), hashlib.sha1).digest()).decode()
        return h
    res = {}
    if not (WEBULL_APP_KEY and WEBULL_APP_SECRET):
        return jsonify({"error": "app key/secret not set in env"}), 503
    cur = (request.args.get("token") or "").strip()
    if not cur:
        try: cur = (_pl.Path(WEBULL_TOKEN_DIR) / "token.txt").read_text().splitlines()[0].strip()
        except Exception: pass
    if not cur:
        cur = os.environ.get("WEBULL_ACCESS_TOKEN", "")
    res["had_token"] = bool(cur)
    if not cur:
        return jsonify({"error": "no current token to refresh"}), 400
    try:
        p = "/openapi/auth/token/refresh"; body = {"token": cur}
        r = requests.post(f"{BASE}{p}", headers=_hdrs(p, body),
                          data=json.dumps(body, ensure_ascii=False, separators=(',', ':')), timeout=15)
        res["http"] = r.status_code
        d = r.json()
        newtok = (d.get("data") or {}).get("token") if isinstance(d.get("data"), dict) else \
                 (d.get("data") if isinstance(d.get("data"), str) else d.get("token"))
        if newtok:
            d2 = _pl.Path(WEBULL_TOKEN_DIR); d2.mkdir(parents=True, exist_ok=True)
            exp = int(time.time() * 1000) + 14 * 24 * 3600 * 1000
            (d2 / "token.txt").write_text(f"{newtok}\n{exp}\nNORMAL\n")
            res["new_token"] = newtok
            res["stored"] = "token.txt updated. Set WEBULL_ACCESS_TOKEN in Railway to persist across redeploys."
        else:
            res["error"] = "no token from refresh"; res["raw"] = d
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {e}"
    return jsonify(res)

# ── KEV'S DAILY FLAGGED TICKERS — the names Kev calls out to watch each day. Recorded here so the
# end-of-day bar archiver also banks bars for HIS picks (even ones our bot never watched), letting us
# benchmark our selection/processes against his. POST {date, tickers}; GET ?date= (or all). ──
KEV_WL_FILE = pathlib.Path("/data/kev_watchlist.json") if pathlib.Path("/data").exists() else pathlib.Path("/tmp/kev_watchlist.json")
_kev_wl = {}
if KEV_WL_FILE.exists():
    try:    _kev_wl = json.loads(KEV_WL_FILE.read_text())
    except Exception: _kev_wl = {}

def _merge_kev_levels(existing, incoming, remove=None):
    """7/24 (Marcos, after the 09:25 open-window wipe): the levels store is MERGE-ONLY.
    A write can never delete a name it doesn't mention — deletion ONLY via the explicit
    `remove` list. Per-ticker: incoming replaces that ticker's entry, EXCEPT an existing
    src='kev' entry (Kev's own posted level = the Bible) which a non-kev write can never
    clobber — the non-kev read is tucked under its 'vision_shadow' instead, exactly the
    post_shadow contract, enforced server-side for EVERY writer. A src='kev' incoming
    (morning-update ritual / Marcos) replaces freely, kev-over-kev included."""
    merged = dict(existing or {})
    for tk in (remove or []):
        merged.pop(str(tk).upper().strip(), None)
    for tk, inc in (incoming or {}).items():
        tk = str(tk).upper().strip()
        if not isinstance(inc, dict):
            continue
        ex = merged.get(tk)
        if isinstance(ex, dict) and ex.get("src") == "kev" and inc.get("src") != "kev":
            kept = dict(ex)
            shadow = {k: v for k, v in inc.items() if k != "vision_shadow"}
            if shadow:
                kept["vision_shadow"] = shadow
            merged[tk] = kept
        else:
            merged[tk] = inc
    return merged


@app.route("/api/kev_watchlist", methods=["POST"])
def set_kev_watchlist():
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    date = d.get("date") or datetime.now(EASTERN).strftime("%Y-%m-%d")
    tickers = sorted({str(t).upper().strip() for t in (d.get("tickers") or []) if str(t).strip()})
    _kev_wl[date] = tickers
    # 7/13 Kev-level anchoring: carry his STATED levels per ticker ({T: {break, confirm, targets}})
    # so the bot can record each pick-trade's entry distance from his level (study: 3/3 days,
    # closest-to-level = best outcome). Stored under a reserved "_levels" key.
    # 7/24 MERGE-ONLY (the 09:25 wipe): a POST updates only the tickers it mentions and can
    # never drop the rest; explicit deletions via "levels_remove"; src='kev' entries are
    # clobber-protected (see _merge_kev_levels).
    if isinstance(d.get("levels"), dict) or d.get("levels_remove"):
        cur = _kev_wl.setdefault("_levels", {}).get(date) or {}
        _kev_wl["_levels"][date] = _merge_kev_levels(cur, d.get("levels") or {},
                                                     remove=d.get("levels_remove") or [])
    try:    KEV_WL_FILE.write_text(json.dumps(_kev_wl, indent=2))
    except Exception as e: print(f"⚠️  Could not save kev_watchlist: {e}")
    return jsonify({"status": "ok", "date": date, "tickers": tickers,
                    "levels": (_kev_wl.get("_levels", {}).get(date) or None)})

@app.route("/api/kev_watchlist", methods=["GET"])
def get_kev_watchlist():
    date = request.args.get("date")
    if date:
        return jsonify({"date": date, "tickers": _kev_wl.get(date, []),
                        "levels": _kev_wl.get("_levels", {}).get(date, {})})
    return jsonify(_kev_wl)


@app.route("/tale/<ticker>")
def tale_of_the_ticker(ticker):
    """TALE OF THE TICKER (Marcos 7/18): the bot's chart read for one name, human-readable —
    the marked levels and EXACTLY what the gate will do before any entry. Reads the same
    _levels store the gate uses; ?date= for history (default today). Store-only: zero Webull."""
    tk = (ticker or "").upper().strip()
    date = request.args.get("date") or datetime.now(EASTERN).strftime("%Y-%m-%d")
    d = (_kev_wl.get("_levels", {}).get(date) or {}).get(tk) or {}
    sh = d.get("vision_shadow") or {}

    def fmt(x):
        try: return "$%.2f" % float(x)
        except (TypeError, ValueError): return "—"

    note = str(d.get("note") or "")
    brk = d.get("break")
    veto = bool(d.get("veto")) or "do-not-trade" in note.lower() or "do not trade" in note.lower()
    if not d:
        gate_color, gate_line = "#8b949e", ("NOT READ YET — No Read, No Trade: the bot will NOT enter "
                                            + tk + " until a chart read posts a level.")
    elif veto:
        gate_color, gate_line = "#f85149", "DO-NOT-TRADE — vetoed by the read. The bot will never enter " + tk + " today."
    elif not brk:
        gate_color, gate_line = "#f85149", "No numeric break level — the gate BLOCKS all entries."
    else:
        gate_color, gate_line = "#3fb950", ("ARMED — entries ALLOWED at/above " + fmt(brk) +
                                            " (the break). Below it: BLOCKED. No break, no trade.")

    rows = ""
    if d:
        for label, key in [("Break — the trigger", "break"), ("Confirm", "confirm"),
                           ("Next supply — room ceiling", "next_supply"), ("Stop", "stop")]:
            rows += "<tr><td>" + label + "</td><td>" + fmt(d.get(key)) + "</td></tr>"
        tg = d.get("targets") or []
        rows += ("<tr><td>Targets</td><td>" + (", ".join(fmt(t) for t in tg) if tg else "—") + "</td></tr>")
        rr = d.get("room_rr")
        rows += "<tr><td>Room (R:R)</td><td>" + (str(rr) if rr not in (None, "") else "—") + "</td></tr>"
        rows += "<tr><td>Setup</td><td>" + str(d.get("setup") or "—") + "</td></tr>"
        rows += "<tr><td>Confidence</td><td>" + str(d.get("confidence") or "—") + "</td></tr>"
        rows += ("<tr><td>Source</td><td>" + ("🤖 vision read" if d.get("src") == "vision" else "📋 Kev night sheet") + "</td></tr>")

    shadow_html = ""
    if sh:
        shadow_html = ("<h3>Our shadow read (exam only — never trades)</h3><table>"
                       + "<tr><td>Our break</td><td>" + fmt(sh.get("break")) + " vs Kev " + fmt(brk) + "</td></tr>"
                       + "<tr><td>Our setup / verdict</td><td>" + str(sh.get("setup") or "—") + " / " + str(sh.get("verdict") or "—") + "</td></tr>"
                       + "<tr><td>Read at</td><td>" + str(sh.get("read_at") or "—") + " by " + str(sh.get("model") or "—") + "</td></tr>"
                       + "<tr><td>Its words</td><td>" + str(sh.get("reason") or "—") + "</td></tr></table>")

    return ("<!doctype html><html><head><meta charset='utf-8'><meta http-equiv='refresh' content='60'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Tale of " + tk + "</title><style>"
            "body{background:#0d1117;color:#e6edf3;font-family:-apple-system,Segoe UI,sans-serif;max-width:640px;margin:24px auto;padding:0 16px}"
            "h1{font-size:26px;margin:6px 0} h3{color:#8b949e;font-size:13px;text-transform:uppercase;letter-spacing:1px;margin:22px 0 6px}"
            ".gate{border-left:4px solid " + gate_color + ";background:#161b22;padding:12px 14px;border-radius:6px;font-weight:600}"
            "table{width:100%;border-collapse:collapse;background:#161b22;border-radius:6px}"
            "td{padding:8px 12px;border-bottom:1px solid #21262d;font-size:14px} td:first-child{color:#8b949e;width:46%}"
            ".note{background:#161b22;padding:12px 14px;border-radius:6px;font-size:14px;line-height:1.5;color:#c9d1d9}"
            "a{color:#58a6ff;text-decoration:none} .top{font-size:13px;color:#8b949e}"
            "</style>" + THEME_SNIPPET + "</head><body>"
            "<div class='top'><a href='/'>← scanner</a> &nbsp;·&nbsp; " + date + " &nbsp;·&nbsp; auto-refreshes 60s</div>"
            "<h1>📜 Tale of " + tk + "</h1>"
            + (("<div class='top' style='margin:2px 0 8px'>🗺️ map v" + str(d.get("read_version"))
                + " · re-read " + str(d.get("read_at") or "?") + " (" + str(d.get("trigger") or "?") + ")"
                + ((" · prior break " + fmt((d.get("history") or [{}])[-1].get("break")))
                   if (d.get("history") or [{}])[-1].get("break") else "")
                + "</div>") if d.get("read_version") and int(d.get("read_version") or 1) >= 2 else "")
            + "<div class='gate'>" + gate_line + "</div>"
            "<h3>The chart report — what the bot is watching</h3>"
            + ("<table>" + rows + "</table>" if rows else "<div class='note'>No read stored for " + tk + " on " + date +
               ". Newcomers are read within ~2 minutes of joining the scanner (8:50 ET onward).</div>")
            + ("<h3>The read's words</h3><div class='note'>" + note + "</div>" if note else "")
            + shadow_html +
            "<h3>Links</h3><div class='note'><a target='_blank' rel='noopener' href='https://www.tradingview.com/chart/?symbol="
            + tk + "'>chart ↗</a></div>"
            "</body></html>")

@app.route("/premarket")
def premarket_dashboard():
    """PREMARKET — TALE OF THE TAPES (Marcos 7/23: 'can we add a pre-market dashboard with tale
    of the tapes'). One page for the 3:55-9:30 shadow session: every watched name's latest tape
    read, the shadow fires as they land, Kev's levels, and a Tale link per name. Read-only,
    renders from in-process stores, auto-refreshes every 30s."""
    now = datetime.now(EASTERN)
    today = now.strftime("%Y-%m-%d")
    hm = now.strftime("%H:%M:%S")
    # roster = Kev sheet ∪ today's persisted watch union ∪ live snapshot
    kev = [str(t).upper() for t in _kev_wl.get(today, [])]
    lv = _kev_wl.get("_levels", {}).get(today, {}) or {}
    names = sorted({*kev, *(_watch_hist.get(today, []) or []),
                    *(str(t).upper() for t in (_watching.get("tickers") or []))})
    # today's decisions, newest last in store — index per ticker + collect shadow fires
    SHADOW = ("premarket_shadow_entry", "reclaim_shadow_fire", "zoneflip_shadow_fire")
    last_row, fire_count, fires = {}, {}, []
    for r in _decisions:
        if r.get("date") != today:
            continue
        t = str(r.get("ticker") or "").upper()
        if t:
            last_row[t] = r
        st = r.get("status") or ""
        if st in SHADOW:
            fires.append(r)
            fire_count[t] = fire_count.get(t, 0) + 1
    fires = fires[-60:][::-1]

    def esc(x):
        return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def fmt(x):
        try: return "$%.2f" % float(x)
        except (TypeError, ValueError): return "—"

    entries_open = now.strftime("%H:%M") >= "09:30"
    banner = ("ENTRIES OPEN — live trading" if entries_open
              else "SHADOW SESSION — watching + logging, entries open 09:30")
    bcol = "#3fb950" if entries_open else "#d29922"
    rows_html = []
    for t in names:
        r = last_row.get(t) or {}
        d = lv.get(t) or {}
        kevcell = (fmt(d.get("break")) + (" <span class='muted'>→</span> " + "/".join(fmt(x) for x in d.get("targets", [])) if d.get("targets") else "")) if d else "—"
        seen = esc(r.get("time") or (str(r.get("recorded_at") or "")[11:19]) or "—")
        rows_html.append(
            "<tr><td><a class='tk' href='/tale/" + esc(t) + "'>" + esc(t) + "</a>"
            + (" <span class='kev-badge'>★ KEV</span>" if t in kev else "") + "</td>"
            "<td class='num'>" + fmt(r.get("price")) + "</td>"
            "<td class='muted'>" + esc(r.get("status") or "no rows yet") + "</td>"
            "<td class='muted num'>" + seen + "</td>"
            "<td class='num'>" + kevcell + "</td>"
            "<td class='num'>" + (("<b class='yellow'>" + str(fire_count.get(t, 0)) + "</b>") if fire_count.get(t) else "<span class='muted'>0</span>") + "</td></tr>")
    fires_html = []
    for r in fires:
        st = r.get("status")
        lane_cls = "yellow" if st == "premarket_shadow_entry" else "purple"
        fires_html.append(
            "<tr><td class='num'>" + esc(r.get("time_hm") or r.get("time") or str(r.get("recorded_at") or "")[11:16]) + "</td>"
            "<td><a class='tk' href='/tale/" + esc(r.get("ticker")) + "'>" + esc(r.get("ticker")) + "</a></td>"
            "<td class='" + lane_cls + "'>" + esc(r.get("entry_type") or st) + "</td>"
            "<td class='num'>" + fmt(r.get("price")) + "</td>"
            "<td class='num'>" + fmt(r.get("stop")) + "</td>"
            "<td class='muted'>" + esc(st) + "</td></tr>")
    kev_n = sum(1 for t in names if t in kev)
    state_cls = "green" if entries_open else "yellow"
    # Dashboard-styled shell (Marcos 7/24: match the scanner/dashboard look + its dark/light
    # switch) — same Inter face, header bar, stat cards, card tables, and THEME_SNIPPET button.
    html = ("<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
            "<title>Premarket — Tale of the Tapes</title>"
            "<meta http-equiv='refresh' content='30'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<link rel='preconnect' href='https://fonts.googleapis.com'>"
            "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap' rel='stylesheet'>"
            "<style>"
            "*{box-sizing:border-box;margin:0;padding:0}"
            "body{font-family:'Inter',system-ui,sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}"
            ".header{display:flex;align-items:center;justify-content:space-between;padding:16px 24px;"
            "background:#161b22;border-bottom:1px solid #21262d;flex-wrap:wrap;gap:8px}"
            ".logo{display:flex;align-items:center;gap:10px}"
            ".logo-icon{width:34px;height:34px;border-radius:8px;background:#3a2e1a;"
            "display:flex;align-items:center;justify-content:center;font-size:18px}"
            ".logo h1{font-size:16px;font-weight:600;color:#e6edf3}"
            ".logo sub{font-size:11px;color:#8b949e;display:block;margin-top:1px;font-weight:400}"
            ".ts{font-size:12px;color:#8b949e}"
            ".stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:20px 24px 0}"
            ".stat{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:14px 18px}"
            ".stat-label{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}"
            ".stat-value{font-size:22px;font-weight:600}"
            ".green{color:#3fb950}.yellow{color:#d29922}.purple{color:#a371f7}.muted{color:#8b949e}"
            ".section{padding:20px 24px 0}"
            ".card{background:#161b22;border:1px solid #21262d;border-radius:10px;overflow:hidden}"
            ".card h2{font-size:13px;font-weight:600;color:#e6edf3;padding:12px 18px;border-bottom:1px solid #21262d}"
            ".card h2 span{color:#8b949e;font-weight:400}"
            ".tw{overflow-x:auto;-webkit-overflow-scrolling:touch}"
            "table{border-collapse:collapse;width:100%;font-size:13px;min-width:560px}"
            "td,th{border-bottom:1px solid #21262d;padding:9px 18px;text-align:left;white-space:nowrap}"
            "tr:last-child td{border-bottom:none}"
            "th{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:.5px;font-weight:500}"
            "tr:hover td{background:#1c2129}"
            ".num{font-variant-numeric:tabular-nums}"
            ".tk{color:#58a6ff;text-decoration:none;font-weight:600}.tk:hover{text-decoration:underline}"
            ".kev-badge{font-size:10px;color:#d29922;border:1px solid #d2992255;border-radius:6px;"
            "padding:1px 6px;margin-left:6px;vertical-align:1px}"
            ".footer{padding:16px 24px;color:#484f58;font-size:11px}"
            "@media (max-width:700px){.stats{grid-template-columns:repeat(2,1fr);padding:14px 12px 0}"
            ".section{padding:14px 12px 0}.header{padding:12px}table{font-size:12px}td,th{padding:8px 12px}}"
            "</style></head><body>"
            "<div class='header'><div class='logo'><div class='logo-icon'>🌅</div>"
            "<div><h1>Premarket — Tale of the Tapes</h1><sub>" + banner + "</sub></div></div>"
            "<div class='ts'>" + today + " " + hm + " ET · auto-refresh 30s</div></div>"
            "<div class='stats'>"
            "<div class='stat'><div class='stat-label'>Session</div><div class='stat-value " + state_cls + "'>"
            + ("LIVE" if entries_open else "SHADOW") + "</div></div>"
            "<div class='stat'><div class='stat-label'>Shadow fires today</div><div class='stat-value "
            + ("yellow" if fires else "muted") + "'>" + str(len(fires)) + "</div></div>"
            "<div class='stat'><div class='stat-label'>Names watched</div><div class='stat-value'>" + str(len(names)) + "</div></div>"
            "<div class='stat'><div class='stat-label'>Kev sheet</div><div class='stat-value yellow'>" + str(kev_n) + "</div></div>"
            "</div>"
            "<div class='section'><div class='card'>"
            "<h2>Shadow fires <span>— the scorecard rows</span></h2>"
            "<div class='tw'><table><tr><th>time</th><th>ticker</th><th>lane</th><th>price</th><th>stop</th><th>row</th></tr>"
            + ("".join(fires_html) or "<tr><td colspan=6 class='muted'>none yet — machines watching</td></tr>")
            + "</table></div></div></div>"
            "<div class='section'><div class='card'>"
            "<h2>The tapes <span>— ★ = Kev sheet · click a ticker for its full Tale</span></h2>"
            "<div class='tw'><table><tr><th>ticker</th><th>last px</th><th>latest read</th><th>at</th><th>Kev level → tgts</th><th>fires</th></tr>"
            + ("".join(rows_html) or "<tr><td colspan=6 class='muted'>roster empty — bot not awake yet</td></tr>")
            + "</table></div></div></div>"
            "<div class='footer'>Entries hard-gated until 09:30 · shadow rows land here as the machines fire</div>"
            "</body></html>")
    # plain string return (NOT render_template_string — this HTML is dynamically built from
    # decision rows; no Jinja pass wanted over data-derived text)
    return html.replace("</head>", THEME_SNIPPET + "</head>"), 200, {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}


@app.route("/api/room_stats", methods=["GET"])
def get_room_stats():
    """Audit view: trades taken (with their room) vs entries the gate rejected, by supply source."""
    taken = [t for t in _trades if t.get("entry_room_rr") is not None]
    by_src = {}
    for r in _room_skips:
        by_src[r.get("supply_src", "?")] = by_src.get(r.get("supply_src", "?"), 0) + 1
    return jsonify({
        "trades_taken_with_room": len(taken),
        "rejections_total": len(_room_skips),
        "rejections_by_supply_src": by_src,
        "recent_rejections": _room_skips[-25:],
        "taken": [{"ticker": t.get("ticker"), "rr": t.get("entry_room_rr"),
                   "supply": t.get("entry_next_supply"), "src": t.get("entry_supply_src"),
                   "pnl": t.get("pnl")} for t in taken[-25:]],
    })


# ── Day-Two Observation endpoints (observe-only) ──
@app.route("/api/day2_watch", methods=["POST"])
def set_day2_watch():
    """Set/extend the day-two observation list. {"tickers": [...], "mode": "set"|"add"}."""
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    tickers = [t.upper() for t in data.get("tickers", []) if t]
    if data.get("mode") == "add":
        merged = list(dict.fromkeys(_obs.get("day2_watch", []) + tickers))
        _obs["day2_watch"] = merged
    else:
        _obs["day2_watch"] = list(dict.fromkeys(tickers))
    _save_obs()
    print(f"🔭 Day-2 watch set: {_obs['day2_watch']}")
    return jsonify({"status": "ok", "day2_watch": _obs["day2_watch"]})


@app.route("/api/observe", methods=["POST"])
def observe():
    """Append a day-two observation snapshot from the bot. Observe-only — no trading."""
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    rec = {
        "date":        data.get("date", datetime.now(EASTERN).strftime("%Y-%m-%d")),
        "time":        datetime.now(EASTERN).strftime("%I:%M %p ET"),
        "ts":          datetime.now(EASTERN).isoformat(),
        "ticker":      (data.get("ticker") or "—").upper(),
        "price":       data.get("price"),
        "prev_close":  data.get("prev_close"),
        "gap_pct":     data.get("gap_pct"),        # vs prev close (the day-2 gap)
        "vwap":        data.get("vwap"),
        "pct_vs_vwap": data.get("pct_vs_vwap"),
        "high":        data.get("high"),
        "day1_move":   data.get("day1_move"),      # how hard it gapped on day 1
        "day1_date":   data.get("day1_date"),
        "note":        data.get("note", ""),
    }
    _obs.setdefault("observations", []).append(rec)
    _save_obs()
    return jsonify({"status": "ok", "count": len(_obs["observations"])})


@app.route("/api/gappers", methods=["POST"])
def log_gappers():
    """Record a day's hard gappers (for day-2 carryover). {"date","gappers":[{symbol,change_pct,...}]}."""
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    date = data.get("date", datetime.now(EASTERN).strftime("%Y-%m-%d"))
    _obs.setdefault("daily_gappers", {})[date] = data.get("gappers", [])
    _save_obs()
    return jsonify({"status": "ok", "date": date, "n": len(data.get("gappers", []))})


@app.route("/api/day2", methods=["GET"])
def get_day2():
    return jsonify({"day2_watch": _obs.get("day2_watch", []),
                    "observations": _obs.get("observations", [])[-500:],
                    "daily_gappers": _obs.get("daily_gappers", {})})



@app.route("/dashboard")
def dashboard():
    # no-cache: the page's static HTML (strategy card etc.) changes when the bot changes; without this
    # the browser serves a stale cached copy and the dashboard's AJAX "Refresh" only updates the data,
    # not the template — so the strategy params looked stale even after a deploy. Force fresh HTML.
    return render_template_string(DASHBOARD_HTML.replace("</head>", THEME_SNIPPET + "</head>")), 200, {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


DAY2_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Day-Two Tracker</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#0d1117;color:#e6edf3;font-family:Inter,system-ui,sans-serif;margin:0;padding:24px}
h1{font-size:20px;margin:0 0 4px}.sub{color:#8b949e;font-size:13px;margin-bottom:20px}
.watch{margin:12px 0 24px}.chip{display:inline-block;background:#161b22;border:1px solid #30363d;border-radius:8px;
 padding:6px 12px;margin:4px;font-weight:600}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #21262d}
th{color:#8b949e;font-weight:600}.pos{color:#3fb950}.neg{color:#f85149}.tk{font-weight:700;color:#58a6ff}
.empty{color:#8b949e;padding:40px;text-align:center}
</style></head><body>
<h1>🔭 Day-Two Tracker <span class="sub">observe-only — how hard day-1 gappers behave on day 2</span></h1>
<div id="watch" class="watch"></div>
<table><thead><tr><th>Date</th><th>Time</th><th>Ticker</th><th>Day-1 move</th><th>Price</th>
<th>Gap vs prev close</th><th>VWAP</th><th>vs VWAP</th><th>Day-2 high</th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
function pct(n){return n==null?'—':(n>=0?'+':'')+Number(n).toFixed(1)+'%';}
function cls(n){return n==null?'':n>=0?'pos':'neg';}
function money(n){return n==null?'—':'$'+Number(n).toFixed(3);}
fetch('/api/day2').then(r=>r.json()).then(d=>{
  document.getElementById('watch').innerHTML = '<b>Watching for day-2:</b> ' +
    ((d.day2_watch||[]).map(t=>'<span class="chip">'+t+'</span>').join('') || '<span class="sub">none seeded yet</span>');
  const obs=(d.observations||[]).slice().reverse();
  const tb=document.getElementById('rows');
  if(!obs.length){tb.innerHTML='<tr><td colspan="9"><div class="empty">No day-2 observations yet — they\\'ll appear here during market hours.</div></td></tr>';return;}
  tb.innerHTML=obs.map(o=>`<tr>
    <td>${o.date||'—'}</td><td>${o.time||'—'}</td><td class="tk"><a href="https://www.tradingview.com/chart/?symbol=${o.ticker}" target="_blank" rel="noopener" style="color:#58a6ff;text-decoration:none">${o.ticker} ↗</a></td>
    <td class="${cls(o.day1_move)}">${pct(o.day1_move)}</td>
    <td>${money(o.price)}</td>
    <td class="${cls(o.gap_pct)}">${pct(o.gap_pct)}</td>
    <td>${money(o.vwap)}</td>
    <td class="${cls(o.pct_vs_vwap)}">${pct(o.pct_vs_vwap)}</td>
    <td>${money(o.high)}</td></tr>`).join('');
});
</script></body></html>"""


@app.route("/day2")
def day2_view():
    return render_template_string(DAY2_HTML.replace("</head>", THEME_SNIPPET + "</head>"))


# ── Dashboard HTML ─────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Marcos Trades Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',system-ui,sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}

/* ── Header ── */
.header{display:flex;align-items:center;justify-content:space-between;
        padding:16px 28px;background:#161b22;border-bottom:1px solid #21262d;position:sticky;top:0;z-index:10}
.logo{display:flex;align-items:center;gap:12px}
.logo-icon{width:38px;height:38px;border-radius:10px;background:linear-gradient(135deg,#1a3a2a,#0e2a1a);
           display:flex;align-items:center;justify-content:center;font-size:20px;border:1px solid #2d5a3d}
.logo h1{font-size:17px;font-weight:700;color:#e6edf3;letter-spacing:-.2px}
.logo sub{font-size:11px;color:#8b949e;display:block;margin-top:1px;font-weight:400}
.header-right{display:flex;align-items:center;gap:14px}
.live-badge{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:500;
            background:#1a3a2a;color:#3fb950;padding:4px 10px;border-radius:20px;border:1px solid #2d5a3d}
.live-badge::before{content:'';width:6px;height:6px;border-radius:50%;background:#3fb950;
                    animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.last-updated{font-size:11px;color:#8b949e}
.refresh-btn{font-size:12px;font-family:inherit;padding:6px 14px;border-radius:8px;
             border:1px solid #30363d;background:transparent;color:#e6edf3;cursor:pointer}
.refresh-btn:hover{background:#21262d}

/* ── Balance Banner ── */
.market-strip{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;
  padding:9px 28px;background:#0d1117;border-bottom:1px solid #21262d}
.market-inner{display:flex;gap:26px;flex-wrap:wrap;align-items:center}
.mkt-idx{display:flex;flex-direction:column;gap:1px;line-height:1.15}
.mkt-idx .mkt-name{font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:.6px}
.mkt-idx .mkt-chg{font-size:15px;font-weight:700}
.mkt-idx .mkt-px{font-size:10.5px;color:#8b949e}
.market-loading{font-size:12px;color:#8b949e}
.market-updated{font-size:11px;color:#6e7681}
.balance-banner{background:linear-gradient(135deg,#0e2a1a 0%,#161b22 100%);
                border-bottom:1px solid #21262d;padding:24px 28px}
.balance-row{display:flex;align-items:flex-end;gap:24px;flex-wrap:wrap}
.balance-main{flex:1}
.balance-label{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px}
.balance-value{font-size:42px;font-weight:700;color:#e6edf3;letter-spacing:-1px}
.balance-change{display:inline-flex;align-items:center;gap:6px;margin-top:8px;
                font-size:14px;font-weight:600;padding:4px 12px;border-radius:6px}
.balance-change.up{background:#1a3a2a;color:#3fb950}
.balance-change.down{background:#3a1a1a;color:#f85149}
.balance-change.flat{background:#21262d;color:#8b949e}

/* ── Stat Cards ── */
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;padding:20px 28px 0}
.stat-card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:16px 18px}
.stat-label{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}
.stat-value{font-size:22px;font-weight:700;line-height:1}
.stat-sub{font-size:11px;color:#8b949e;margin-top:5px}
.green{color:#3fb950} .red{color:#f85149} .yellow{color:#d29922} .gray{color:#8b949e} .white{color:#e6edf3}

/* ── Chart + Table section ── */
.content{padding:20px 28px}
.section-title{font-size:13px;font-weight:600;color:#8b949e;text-transform:uppercase;
               letter-spacing:.6px;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.section-title::after{content:'';flex:1;height:1px;background:#21262d}

.chart-wrap{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:20px;margin-bottom:20px;height:220px}

/* ── Trade Table ── */
.table-wrap{background:#161b22;border:1px solid #21262d;border-radius:12px;overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:13px}
thead th{padding:11px 14px;text-align:left;font-size:11px;font-weight:600;
         color:#8b949e;text-transform:uppercase;letter-spacing:.5px;
         background:#0d1117;border-bottom:1px solid #21262d;white-space:nowrap}
tbody tr{border-bottom:1px solid #21262d;transition:background .1s}
tbody tr:last-child{border-bottom:none}
tbody tr:hover{background:#1c2128}
tbody td{padding:11px 14px;vertical-align:middle;white-space:nowrap}
.ticker-badge{display:inline-block;background:#1c2128;border:1px solid #30363d;
              border-radius:6px;padding:2px 8px;font-weight:600;font-size:12px;color:#e6edf3;
              text-decoration:none;cursor:pointer}
.ticker-badge:hover{border-color:#58a6ff}
a.watch-chip{text-decoration:none;cursor:pointer}
a.watch-chip:hover{filter:brightness(1.25)}
.pnl-pos{color:#3fb950;font-weight:600}
.pnl-neg{color:#f85149;font-weight:600}
.pnl-flat{color:#8b949e;font-weight:600}
.exit-tag{font-size:11px;color:#8b949e;max-width:160px;overflow:hidden;text-overflow:ellipsis}
.empty-state{text-align:center;padding:48px 24px;color:#8b949e}
.empty-state .icon{font-size:36px;margin-bottom:12px}
.empty-state p{font-size:14px}
.empty-state small{font-size:12px;display:block;margin-top:6px;color:#484f58}

/* ── No-trade days row ── */
.no-trade-row td{color:#484f58;font-style:italic}

/* ── Strategy + Watch panel ── */
.strategy-panel{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px 28px}
@media(max-width:700px){.strategy-panel{grid-template-columns:1fr}}
@media(max-width:640px){
  /* Phone layout: the ENTRY/NOW/STOP/TARGET row was 4 cramped columns — reflow to a readable 2×2 */
  .trade-grid{grid-template-columns:repeat(2,1fr);gap:8px}
  .trade-grid .val{font-size:16px}
  /* claw back the wide 28px side padding that squeezes content on a narrow screen */
  .stats-grid,.strategy-panel,.balance-banner{padding-left:14px;padding-right:14px}
  .trade-panel{padding:14px}
  .tally-tiles{gap:14px 22px}
  .tally-tiles>div:nth-child(4){border-left:none;padding-left:0}   /* drop the Today divider once tiles wrap */
  .balance-value{font-size:34px}
  .trade-panel .tk{font-size:18px} .trade-panel .pnl{font-size:20px}
}
.panel-card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:16px 18px}
.cal-wrap{max-width:660px;margin:0 auto 8px}
.cal-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.cal-nav{background:#21262d;border:1px solid #30363d;color:#e6edf3;border-radius:6px;padding:2px 12px;cursor:pointer;font-size:20px;line-height:1.2}
.cal-nav:hover{background:#30363d}
.cal-titlewrap{text-align:center;display:flex;flex-direction:column;gap:2px}
.cal-title{font-size:15px;font-weight:700}
.cal-month-pnl{font-size:15px;font-weight:800}
.cal-month-sub{font-size:11px;color:#8b949e}
.cal-dow{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin-bottom:6px}
.cal-dow>div{text-align:center;font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:.05em}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}
.cal-cell{min-height:58px;border-radius:8px;border:1px solid #21262d;background:#0d1117;padding:5px 7px;display:flex;flex-direction:column;justify-content:space-between}
.cal-cell.empty{background:transparent;border-color:transparent}
.cal-cell.win{background:rgba(63,185,80,.13);border-color:rgba(63,185,80,.38)}
.cal-cell.loss{background:rgba(248,81,73,.13);border-color:rgba(248,81,73,.38)}
.cal-cell.flat{background:rgba(139,148,158,.10)}
.cal-cell.today{outline:2px solid #58a6ff;outline-offset:-2px}
.cal-daynum{font-size:11px;color:#8b949e;font-weight:600}
.cal-pnl{font-size:13px;font-weight:800;line-height:1.1}
.cal-r{font-size:10px;font-weight:800;margin-top:1px}
.cal-ct{font-size:9px;color:#8b949e}
@media(max-width:640px){
  .cal-cell{min-height:46px;padding:3px 4px}
  .cal-pnl{font-size:10px} .cal-daynum{font-size:9px} .cal-ct{display:none}
  .cal-dow>div{font-size:8px} .cal-grid{gap:4px} .cal-dow{gap:4px}
}
.panel-title{font-size:11px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px}
.param-grid{display:flex;flex-wrap:wrap;gap:8px}
.param-pill{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:5px 10px;font-size:12px}
.param-pill span{color:#8b949e;margin-right:4px}
.param-pill strong{color:#e6edf3}
.watch-tickers{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.trade-panel{margin-top:16px;background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:16px}
.trade-panel .hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.trade-panel .tk{font-size:20px;font-weight:800;color:#58a6ff;text-decoration:none}
.trade-panel .pnl{font-size:22px;font-weight:800}
.trade-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.trade-grid .cell{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:8px 10px}
.trade-grid .lbl{color:#8b949e;font-size:11px;text-transform:uppercase}
.trade-grid .val{font-weight:700;font-size:15px;margin-top:2px}
.tbar{height:8px;background:#161b22;border-radius:4px;margin-top:12px;overflow:hidden;position:relative}
.tbar .fill{height:100%;background:linear-gradient(90deg,#f85149,#d29922,#3fb950)}
.tbar-lbls{display:flex;justify-content:space-between;color:#8b949e;font-size:11px;margin-top:4px}
.tape-btn{margin-top:10px;width:100%;background:#161b22;border:1px solid #21262d;border-radius:8px;
          color:#8b949e;font-size:12px;font-weight:600;padding:7px 10px;cursor:pointer;text-align:center}
.tape-btn:hover{border-color:#58a6ff;color:#c9d1d9}
.tape{display:none;margin-top:10px;background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 14px}
.tape.show{display:block}
.tape .verdict{font-size:14px;font-weight:800;margin-bottom:8px}
.tape .verdict.locked{color:#3fb950}
.tape .verdict.risk{color:#d29922}
.tape ul{margin:0;padding-left:18px;color:#c9d1d9;font-size:13px;line-height:1.65}
.tape li b{color:#e6edf3}
.tape .nums{color:#8b949e;font-size:11px;margin-top:8px}
.cap-strip{background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:10px 14px;margin-bottom:12px}
.cap-lbl{font-size:12px;color:#8b949e}
.cap-lbl b{color:#e6edf3}
.cap-bar{height:8px;background:#161b22;border-radius:4px;margin-top:8px;overflow:hidden}
.cap-fill{height:100%;background:linear-gradient(90deg,#3fb950,#d29922);border-radius:4px}
.watch-chip{background:#1a3a2a;border:1px solid #2d5a3d;color:#3fb950;
            border-radius:6px;padding:4px 10px;font-size:13px;font-weight:600}
.watch-chip.trading{background:#2a1a3a;border-color:#5a3d8a;color:#c084fc}
.watch-status{font-size:12px;color:#8b949e;margin-bottom:10px}
.status-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle}
.status-dot.watching{background:#d29922;animation:pulse 2s infinite}
.status-dot.trading{background:#c084fc;animation:pulse 1s infinite}
.status-dot.idle{background:#484f58}
.idle-msg{color:#484f58;font-size:13px;font-style:italic}
</style>
</head>
<body>

<div class="header">
  <div class="logo">
    <div class="logo-icon">📈</div>
    <div>
      <h1>Marcos Trades Dashboard</h1>
      <sub>v10 Pure Technical Scanner — Webull OpenAPI</sub>
    </div>
  </div>
  <div class="header-right">
    <span class="live-badge">LIVE</span>
    <span class="last-updated" id="lastUpdate">Loading...</span>
    <button class="refresh-btn" onclick="loadData()">↻ Refresh</button>
  </div>
</div>

<div class="market-strip" id="marketStrip">
  <div class="market-inner" id="marketInner"><span class="market-loading">Loading market…</span></div>
  <div class="market-updated" id="marketUpdated"></div>
</div>

<div class="balance-banner" id="balanceBanner">
  <div class="balance-row">
    <div class="balance-main">
      <div class="balance-label">Account Balance</div>
      <div class="balance-value" id="balanceVal">—</div>
      <div id="balanceChange"></div>
    </div>
    <div class="tally-tiles" style="display:flex;flex-wrap:wrap;gap:18px 28px;align-items:flex-end;padding-bottom:4px">
      <div>
        <div class="balance-label">Total P&amp;L</div>
        <div style="font-size:24px;font-weight:700" id="totalPnl">—</div>
      </div>
      <div>
        <div class="balance-label">Win Rate</div>
        <div style="font-size:24px;font-weight:700" id="winRate">—</div>
      </div>
      <div>
        <div class="balance-label">Total Trades</div>
        <div style="font-size:24px;font-weight:700;color:#e6edf3" id="totalTrades">—</div>
      </div>
      <div style="border-left:1px solid #30363d;padding-left:28px">
        <div class="balance-label">Today P&amp;L</div>
        <div style="font-size:24px;font-weight:700" id="todayPnl">—</div>
      </div>
      <div>
        <div class="balance-label">Today WR</div>
        <div style="font-size:24px;font-weight:700" id="todayWr">—</div>
      </div>
      <div>
        <div class="balance-label" title="Cumulative R today (all trades, P&amp;L ÷ planned risk). Daily goal: +1.67R–+2.0R = $50–$60 on the $3k frame.">Today R 🎯1.67+</div>
        <div style="font-size:24px;font-weight:700" id="todayR">—</div>
      </div>
      <div>
        <div class="balance-label" title="Average R per WINNING trade today (pnl ÷ planned risk). THE capture target: ≥ +0.85R makes a ~60% win rate profitable. Small number = ex-best (without the day's biggest winner — the fragility check).">Avg Win 🎯0.85R</div>
        <div style="font-size:24px;font-weight:700" id="avgWinR">—</div>
        <div style="font-size:11px;color:#8b949e" id="avgWinRx"></div>
      </div>
    </div>
  </div>
</div>

<div class="strategy-panel">
  <div class="panel-card">
    <div class="panel-title">v10 Strategy Parameters</div>
    <div class="param-grid">
      <div class="param-pill"><span>Qualify</span><strong>price &lt;$20 · float &lt;20M · gap÷float rank · volume-ignition (2× RVOL, flat OK)</strong></div>
      <div class="param-pill"><span>Setup TF</span><strong>3-min chart — setups AND trade management</strong></div>
      <div class="param-pill"><span>Entries</span><strong>ignition (1-min) · flat-top · ORB · MA-pullback · VWAP-reclaim 3-gate (10s) · zone-flip (10s) · 🚀 ROCKET CATCHER (vel ≥25%/5min → 20-EMA pullback → curl, cap 3/day)</strong></div>
      <div class="param-pill"><span>Chart Gate</span><strong>ENFORCE — no break of the vision read's level, no trade · exhausted maps auto RE-READ intraday (v2+ maps)</strong></div>
      <div class="param-pill"><span>Vel5 Floor</span><strong>no legacy breakout entry on NEGATIVE 5-min velocity (knife-catch guard) · curl machines exempt</strong></div>
      <div class="param-pill"><span>Base</span><strong>≤12% chase-guard (room:risk is the real filter)</strong></div>
      <div class="param-pill"><span>Daily-first</span><strong>above daily 20/50 MA + has room, else no trade</strong></div>
      <div class="param-pill"><span>Room gate</span><strong>≥2:1 to next DAILY significant level</strong></div>
      <div class="param-pill"><span>VWAP</span><strong>above VWAP (front-side); reversal setups reclaim it from below</strong></div>
      <div class="param-pill"><span>Front-side</span><strong>9&gt;20 EMA — gated on pullback, observed on breakout</strong></div>
      <div class="param-pill"><span>Momentum</span><strong>HARD gate — building vol + ≥30% of peak · reversal setups exempt · topping-tail = hard skip</strong></div>
      <div class="param-pill"><span>Stop</span><strong>structural at the level (base/OR/MA low) · NO −7% · managed on the 3-min close</strong></div>
      <div class="param-pill"><span>Exits</span><strong>kev25 on the 3-MIN CLOSE — 50%@+1R→BE · 25%@+2R · runner health-trail (VWAP/9-EMA) · 3:45 time stop · rockets: ⅓@+50% · ⅓@+100% · runner trails</strong></div>
      <div class="param-pill"><span>Re-entry</span><strong>after exit → re-gated · topping-tail / consec-loss give-up</strong></div>
      <div class="param-pill"><span>Entry Cutoff</span><strong>3:30pm ET</strong></div>
      <div class="param-pill"><span>Quality logs</span><strong>entry_vel5 · read-confidence · L1 book · vol-trajectory — logged (study)</strong></div>
    </div>
  </div>
  <div class="panel-card">
    <div class="panel-title">Currently Watching</div>
    <div class="watch-status" id="watchStatus"><span class="status-dot idle"></span>Loading...</div>
    <div class="watch-tickers" id="watchTickers"></div>
    <div id="tradePanel"></div>
  </div>
</div>

<div class="stats-grid" id="statsGrid">
  <div class="stat-card"><div class="stat-label">Expectancy /trade 🎯+0.10R</div><div class="stat-value green" id="avgGain">—</div><div class="stat-sub">per winning trade</div></div>
  <div class="stat-card"><div class="stat-label">Avg Loss (R) plan −1.0</div><div class="stat-value red" id="avgLoss">—</div><div class="stat-sub">per losing trade</div></div>
  <div class="stat-card"><div class="stat-label">Best Trade</div><div class="stat-value green" id="bestPnl">—</div><div class="stat-sub" id="bestTicker">—</div></div>
  <div class="stat-card"><div class="stat-label">Worst Trade</div><div class="stat-value red" id="worstPnl">—</div><div class="stat-sub" id="worstTicker">—</div></div>
  <div class="stat-card"><div class="stat-label">Wins</div><div class="stat-value green" id="wins">—</div><div class="stat-sub">profitable sessions</div></div>
  <div class="stat-card"><div class="stat-label">Losses</div><div class="stat-value red" id="losses">—</div><div class="stat-sub">closed in the red</div></div>
  <div class="stat-card"><div class="stat-label">Break Even</div><div class="stat-value" id="breakeven" style="color:#8b949e">—</div><div class="stat-sub">scratched at $0</div></div>
</div>

<div class="content">
  <div class="section-title">Equity Curve</div>
  <div class="chart-wrap">
    <canvas id="equityChart"></canvas>
  </div>

  <div class="section-title">P&amp;L Calendar</div>
  <div id="pnlCalendar" class="cal-wrap"></div>

  <div class="section-title">Trade History</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Time</th>
          <th>Ticker</th>
          <th>Entry</th>
          <th>Exit</th>
          <th>Shares</th>
          <th>Size</th>
          <th>P&amp;L $</th>
          <th>P&amp;L %</th>
          <th title="R-multiple: P&amp;L ÷ planned risk ($30 = 1R). Winners: target avg ≥ +0.85R. Losers: planned −1R; deeper = stop overshoot.">R</th>
          <th>Exit Reason</th>
          <th>Float</th>
        </tr>
      </thead>
      <tbody id="tradeTable">
        <tr><td colspan="12"><div class="empty-state"><div class="icon">📊</div><p>Loading trade history...</p></div></td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
let chart = null;

function fmt$(n){ return n===null||n===undefined?'—':'$'+Math.abs(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtPct(n){ return n===null||n===undefined?'—':(n>=0?'+':'')+n.toFixed(1)+'%'; }
function fmtPnl$(n){ return (n>=0?'+':'')+fmt$(n); }
function fmtTime(iso){ if(!iso) return '—'; const m=String(iso).match(/T(\d{2}):(\d{2})/); if(!m) return '—'; let h=+m[1]; const ap=h>=12?'PM':'AM'; h=h%12||12; return h+':'+m[2]+' '+ap; }

function loadData(){
  document.getElementById('lastUpdate').textContent = 'Refreshing...';
  fetch('/api/trades')
    .then(r=>r.json())
    .then(data=>{
      renderStats(data.stats, data.account, data.trades);
      renderTodayStats(data.trades);
      renderTable(data.trades);
      renderCalendar(data.trades);
      renderChart(data.stats.equity_curve);
      document.getElementById('lastUpdate').textContent =
        'Updated ' + new Date().toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});
    })
    .catch(()=>{ document.getElementById('lastUpdate').textContent = 'Error loading data'; });
}

function renderTodayStats(trades){
  // Today's P&L + win rate, computed client-side from the trade log (ET calendar day).
  const todayET = new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'});  // YYYY-MM-DD
  const todayAll = (trades||[]).filter(t=>String(t.date||'').slice(0,10)===todayET);
  // Same rule as the era stats: bookkeeping prints (forced recovery closes) count in MONEY, never in QUALITY.
  const today = todayAll.filter(t=>!/RECOVER/i.test(String(t.exit_reason||'')));
  const pEl = document.getElementById('todayPnl'), wEl = document.getElementById('todayWr');
  if(!todayAll.length){
    pEl.textContent='—'; pEl.className='white'; wEl.textContent='—'; wEl.className='gray';
    // 7/16 fix: a long-lived tab crosses midnight — reset ALL today-tiles, not just two, or
    // yesterday's R/avg-win linger as ghosts (Marcos caught −2.7R at 9:31 with zero trades today).
    const g=id=>document.getElementById(id);
    if(g('todayR')){ g('todayR').textContent='—'; g('todayR').className='gray'; }
    if(g('avgWinR')){ g('avgWinR').textContent='—'; g('avgWinR').className='gray'; }
    if(g('avgWinRx')){ g('avgWinRx').textContent=''; }
    return; }
  const p = todayAll.reduce((a,t)=>a+(parseFloat(t.pnl)||0),0);   // money ledger: ALL prints
  const w = today.filter(t=>(parseFloat(t.pnl)||0)>0).length;
  const l = today.filter(t=>(parseFloat(t.pnl)||0)<0).length;
  const dec = w + l;   // decided trades — $0 scratches excluded from the win rate
  const wr = dec ? Math.round(w/dec*100) : 0;
  pEl.textContent = (p>=0?'+':'')+fmt$(p); pEl.className = p>0?'green':p<0?'red':'white';
  wEl.textContent = dec ? (wr+'% ('+w+'/'+dec+')') : '—'; wEl.className = dec ? (wr>=50?'green':wr>0?'yellow':'gray') : 'gray';
  // THE capture target (7/13): average R per winning trade, vs the 0.85R goal. Ex-best = without
  // the day's biggest winner (a mean carried by one monster is fragile — show both).
  const tR=document.getElementById('todayR');
  if(tR){
    const rs=today.filter(t=>parseFloat(t.planned_risk)>0.5).map(t=>(parseFloat(t.pnl)||0)/parseFloat(t.planned_risk));
    if(!rs.length){ tR.textContent='—'; tR.className='gray'; }
    else{ const sum=rs.reduce((a,b)=>a+b,0);
      tR.textContent=(sum>=0?'+':'−')+Math.abs(sum).toFixed(1)+'R';
      tR.className=sum>=1.67?'green':sum>=0?'yellow':'red'; }
  }
  const rEl=document.getElementById('avgWinR'), rxEl=document.getElementById('avgWinRx');
  if(rEl){
    const winRs=today.filter(t=>(parseFloat(t.pnl)||0)>0 && parseFloat(t.planned_risk)>0.5)
                      .map(t=>parseFloat(t.pnl)/parseFloat(t.planned_risk));
    if(!winRs.length){ rEl.textContent='—'; rEl.className='gray'; rxEl.textContent=''; }
    else{
      const mean=winRs.reduce((a,b)=>a+b,0)/winRs.length;
      const exb=winRs.length>1?(winRs.reduce((a,b)=>a+b,0)-Math.max(...winRs))/(winRs.length-1):mean;
      rEl.textContent='+'+mean.toFixed(2)+'R';
      rEl.className=mean>=0.85?'green':mean>=0.65?'yellow':'red';
      rxEl.textContent='ex-best +'+exb.toFixed(2)+'R';
    }
  }
}

let calYear=null, calMonth=null;
function renderCalendar(trades){
  // P&L per ET calendar day, laid out as a month grid. Navigate months with the ‹ › buttons.
  window._calTrades = trades || [];
  const byDay={};
  (trades||[]).forEach(function(t){
    const d=String(t.date||'').slice(0,10); if(d.length!==10) return;
    const o=byDay[d]||(byDay[d]={pnl:0,ct:0,w:0,r:0,rn:0});
    const p=parseFloat(t.pnl)||0; o.pnl+=p; o.ct++; if(p>0)o.w++;
    const pr=parseFloat(t.planned_risk); if(pr>0.5){ o.r+=p/pr; o.rn++; }
  });
  const nowET=new Date(new Date().toLocaleString('en-US',{timeZone:'America/New_York'}));
  if(calYear===null){ calYear=nowET.getFullYear(); calMonth=nowET.getMonth(); }
  const pad=function(n){return String(n).padStart(2,'0');};
  const key=function(d){return calYear+'-'+pad(calMonth+1)+'-'+pad(d);};
  const dim=new Date(calYear,calMonth+1,0).getDate();
  const startDow=new Date(calYear,calMonth,1).getDay();
  const todayStr=nowET.toLocaleDateString('en-CA');
  const cell=function(v){return (v>=0?'+':'-')+'$'+Math.abs(Math.round(v)).toLocaleString('en-US');};
  const money2=function(v){return (v>=0?'+':'-')+'$'+Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});};
  let mp=0,mc=0,mw=0,mr=0,mrn=0;
  for(let d=1;d<=dim;d++){ const o=byDay[key(d)]; if(o){mp+=o.pnl;mc+=o.ct;mw+=o.w;mr+=o.r;mrn+=o.rn;} }
  const mName=new Date(calYear,calMonth,1).toLocaleString('en-US',{month:'long'});
  let h='<div class="cal-head">'
    +'<button class="cal-nav" onclick="calNav(-1)">&lsaquo;</button>'
    +'<div class="cal-titlewrap"><span class="cal-title">'+mName+' '+calYear+'</span>'
    +(mc?'<span class="cal-month-pnl '+(mp>0?'green':mp<0?'red':'white')+'">'+money2(mp)+'</span><span class="cal-month-sub">'+mc+' trade'+(mc!==1?'s':'')+' · '+Math.round(mw/mc*100)+'% WR'+(mrn?(' · '+(mr>=0?'+':'−')+Math.abs(mr).toFixed(1)+'R'):'')+'</span>':'<span class="cal-month-sub">no trades</span>')
    +'</div>'
    +'<button class="cal-nav" onclick="calNav(1)">&rsaquo;</button></div>';
  h+='<div class="cal-dow"><div>Sun</div><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div></div>';
  h+='<div class="cal-grid">';
  for(let i=0;i<startDow;i++) h+='<div class="cal-cell empty"></div>';
  for(let d=1;d<=dim;d++){
    const o=byDay[key(d)];
    let cls='cal-cell', inner='';
    if(o){ cls+=(o.pnl>0?' win':o.pnl<0?' loss':' flat');
      const rLine=o.rn?'<div class="cal-r '+(o.r>=1.67?'green':o.r>=0?'yellow':'red')+'">'+(o.r>=0?'+':'−')+Math.abs(o.r).toFixed(1)+'R</div>':'';
      inner='<div class="cal-pnl '+(o.pnl>0?'green':o.pnl<0?'red':'white')+'">'+cell(o.pnl)+'</div><div class="cal-ct">'+o.ct+' trade'+(o.ct!==1?'s':'')+'</div>'+rLine;
    }
    if(key(d)===todayStr) cls+=' today';
    h+='<div class="'+cls+'"><div class="cal-daynum">'+d+'</div>'+inner+'</div>';
  }
  h+='</div>';
  const el=document.getElementById('pnlCalendar'); if(el) el.innerHTML=h;
}
function calNav(delta){
  calMonth+=delta;
  if(calMonth<0){calMonth=11;calYear--;}
  else if(calMonth>11){calMonth=0;calYear++;}
  renderCalendar(window._calTrades||[]);
}
const ERA_START='2026-07-13';   // realistic-sizing era ($3k frame, $30 R) — headline stats scope
function renderStats(s, acct, trades){
  // Era-true overrides: the server stats span ALL history (mixed $100-buy + $30-R eras) and the
  // balance is a DAILY frame ($3,000 + today) — mixing them made a fictional "return since inception".
  if(trades && trades.length){
    const era=trades.filter(t=>String(t.date||'')>=ERA_START);
    if(era.length){
      const isBook=t=>/RECOVER/i.test(String(t.exit_reason||''));   // bookkeeping prints ≠ strategy trades
      const graded=era.filter(t=>!isBook(t));
      const pnl=era.reduce((a,t)=>a+(parseFloat(t.pnl)||0),0);      // money is money — ALL prints
      const w=graded.filter(t=>(parseFloat(t.pnl)||0)>0).length, l=graded.filter(t=>(parseFloat(t.pnl)||0)<0).length;
      s=Object.assign({},s,{total_pnl:Math.round(pnl*100)/100, total_trades:graded.length,
                            win_rate:(w+l)?Math.round(w/(w+l)*100):0});
      const frict=era.reduce((a,t)=>a+(parseFloat(t.est_slippage)||0),0);
      const fmid=frict*0.6;                       // MIDDLE estimate: taker entries (~half spread) + mixed
      const net=pnl-frict, netMid=pnl-fmid;       // exits (tier sells are makers ≈ free, stops cross) ≈ 60%
      const money=(v)=>(v>=0?'+':'−')+'$'+Math.abs(v).toFixed(0);
      const back=document.getElementById('balanceChange');
      if(back) back.innerHTML='era account value (compounded) · sizing frame resets to $3,000/day (R=$30 constant) · gross '+money(pnl)
        +' · friction −$'+frict.toFixed(0)+' <span title="Conservative model: full quoted spread per trade. Middle: ~60% (taker entries, maker tier-exits, stops cross). True slippage gets measured at go-live.">(mid −$'+fmid.toFixed(0)+')</span>'
        +' → <b>net '+money(net)+' <span style="color:#d29922">(mid ≈ '+money(netMid)+')</span></b>'
        +(era.length>graded.length?' · '+(era.length-graded.length)+' bookkeeping print(s) excluded from WR':'');
      // honest R pair: expectancy + avg loss (graded, planned_risk era only)
      const rs=graded.filter(t=>parseFloat(t.planned_risk)>0.5).map(t=>(parseFloat(t.pnl)||0)/parseFloat(t.planned_risk));
      const lrs=rs.filter(r=>r<0);
      const expEl=document.getElementById('avgGain'), alEl=document.getElementById('avgLoss');
      if(expEl&&rs.length){ const ex=rs.reduce((a,b)=>a+b,0)/rs.length;
        expEl.textContent=(ex>=0?'+':'−')+Math.abs(ex).toFixed(2)+'R';
        expEl.className=ex>=0.10?'green':ex>=0?'yellow':'red'; }
      if(alEl&&lrs.length){ const al=lrs.reduce((a,b)=>a+b,0)/lrs.length;
        alEl.textContent=al.toFixed(2)+'R'+(al<-1.15?' ⚠️':'');
        alEl.className=al<-1.15?'red':'white'; }
      window._eraStatsApplied=true;
    }
  }
  // DRY-RUN balance is LEDGER-DERIVED (7/14): the bot's posted balance is $3,000 + its own process's
  // session P&L — it forgets everything before the last restart (today it missed the whole morning).
  // Trust the trade store instead: $3,000 frame + today's complete prints. Go-live replaces this with
  // real Webull equity posted by the bot.
  let bal = acct && acct.balance ? acct.balance : 0;
  if(trades && trades.length){
    // HEADLINE = the ERA ACCOUNT VALUE: what a real $3,000 account funded at era start would hold now
    // (every print, compounded). The SIZING frame still resets to $3,000 daily by design (R constant at
    // $30 for clean calibration stats) — that lives in the subline, and the capital meter uses the frame.
    const eraPnl=trades.filter(t=>String(t.date||'')>=ERA_START)
                       .reduce((a,t)=>a+(parseFloat(t.pnl)||0),0);
    bal = 3000 + eraPnl;
    const todayET=new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'});
    const tp=trades.filter(t=>String(t.date||'').slice(0,10)===todayET)
                   .reduce((a,t)=>a+(parseFloat(t.pnl)||0),0);
    window._acctBal = 3000 + tp;   // capital meter budget = the daily sizing frame
  } else {
    window._acctBal = bal;
  }
  document.getElementById('balanceVal').textContent = bal ? fmt$(bal) : '—';

  const pnl = s.total_pnl;
  const pnlEl = document.getElementById('totalPnl');
  pnlEl.textContent = pnl!==0 ? (pnl>=0?'+':'')+fmt$(pnl) : '—';
  pnlEl.className = pnl>0?'green':pnl<0?'red':'white';

  const wrEl = document.getElementById('winRate');
  wrEl.textContent = s.total_trades>0 ? s.win_rate+'%' : '—';
  wrEl.className = s.win_rate>=50?'green':s.win_rate>0?'yellow':'gray';

  document.getElementById('totalTrades').textContent = s.total_trades || '0';

  document.getElementById('avgGain').textContent  = s.total_trades>0 ? '+'+s.avg_gain+'%' : '—';
  document.getElementById('avgLoss').textContent  = s.total_trades>0 ? s.avg_loss+'%'   : '—';
  document.getElementById('bestPnl').textContent  = s.total_trades>0 ? (s.best_pnl>=0?'+':'')+fmt$(s.best_pnl)  : '—';
  document.getElementById('bestTicker').textContent  = s.best_ticker  || '—';
  document.getElementById('worstPnl').textContent = s.total_trades>0 ? (s.worst_pnl>=0?'+':'')+fmt$(s.worst_pnl) : '—';
  document.getElementById('worstTicker').textContent = s.worst_ticker || '—';
  document.getElementById('wins').textContent    = s.wins   ?? '—';
  document.getElementById('losses').textContent  = s.losses ?? '—';
  document.getElementById('breakeven').textContent = s.breakeven ?? '—';

  if(bal>0 && pnl!==0 && !window._eraStatsApplied){
    const startBal = bal - pnl;
    const retPct = (pnl/startBal*100).toFixed(1);
    const cls = pnl>=0?'up':'down';
    document.getElementById('balanceChange').innerHTML =
      `<span class="balance-change ${cls}">${pnl>=0?'▲':'▼'} ${Math.abs(retPct)}% total return since inception</span>`;
  }
}

function renderTable(trades){
  const tbody = document.getElementById('tradeTable');
  if(!trades || trades.length===0){
    tbody.innerHTML = `<tr><td colspan="12"><div class="empty-state">
      <div class="icon">📊</div>
      <p>No trades recorded yet</p>
      <small>The bot will log results here automatically after each session</small>
    </div></td></tr>`;
    return;
  }
  window._allTrades = trades;
  const rows = trades.map((t,i)=>({t,i})).reverse().map(o=>{
    const t=o.t;
    const key = t.trade_id || (t.ticker+'|'+t.date+'|'+o.i);
    const isOpen = window._storyOpen.has(key);
    const isBookRow=/RECOVER/i.test(String(t.exit_reason||''));
    const pnlCls  = isBookRow?'pnl-flat':(t.pnl>0?'pnl-pos':t.pnl<0?'pnl-neg':'pnl-flat');   // bookkeeping = muted
    const pnlSign = t.pnl>0?'+':'';
    const pctSign = t.pnl_pct>0?'+':'';
    const fl = t.float_shares ? String(t.float_shares).replace(/(\d)(?=(\d{3})+$)/g,'$1,') : '—';
    const pr = parseFloat(t.planned_risk);
    const rMul = (pr>0.5) ? (t.pnl/pr) : null;
    const rTxt = rMul===null ? '<span style="color:#484f58">—</span>'
               : (rMul>=0?'+':'−')+Math.abs(rMul).toFixed(2)+'R'
                 + (rMul>=2?' 🚀':(rMul<=-1.15?' ⚠️':''));
    const sz = t.position_size ? fmt$(t.position_size) : '—';
    return `<tr onclick="toggleStory('${key}', event)" style="cursor:pointer" title="Click for the story of this trade">
      <td style="color:#8b949e">${t.date||'—'}</td>
      <td style="color:#8b949e">${fmtTime(t.recorded_at)}</td>
      <td><a class="ticker-badge" href="https://www.tradingview.com/chart/?symbol=${t.ticker||''}" target="_blank" rel="noopener" title="Open chart">${t.ticker||'—'} ↗</a></td>
      <td>${t.entry?'$'+t.entry.toFixed(2):'—'}</td>
      <td>${t.exit?'$'+t.exit.toFixed(2):'—'}</td>
      <td style="color:#8b949e">${t.shares||'—'}</td>
      <td style="color:#8b949e">${sz}</td>
      <td class="${pnlCls}">${pnlSign}$${Math.abs(t.pnl).toFixed(2)}</td>
      <td class="${pnlCls}">${pctSign}${t.pnl_pct.toFixed(1)}%</td>
      <td class="${pnlCls}" style="font-weight:700">${rTxt}</td>
      <td class="exit-tag" title="${t.exit_reason||''}">${isBookRow?'📋 ':''}${t.exit_reason||'—'}</td>
      <td style="color:#8b949e;font-size:12px">${fl}</td>
    </tr>`
    + (isOpen?`<tr class="story-tr"><td colspan="12"><div class="tape show">${storyClosedHTML(t)}</div></td></tr>`:'');
  }).join('');
  tbody.innerHTML = rows;
}

function renderChart(curve){
  const canvas = document.getElementById('equityChart');
  const ctx    = canvas.getContext('2d');
  if(chart){ chart.destroy(); }
  if(!curve || curve.length===0){
    ctx.fillStyle='#484f58';ctx.font='13px Inter';ctx.textAlign='center';
    ctx.fillText('No trade data yet — equity curve will appear after the first trade',canvas.width/2,canvas.height/2);
    return;
  }
  const labels = curve.map(p=>p.date);
  const values = curve.map(p=>p.equity);
  const pos    = values[values.length-1]>=0;
  const color  = pos?'#3fb950':'#f85149';
  chart = new Chart(ctx,{
    type:'line',
    data:{
      labels,
      datasets:[{
        label:'Cumulative P&L ($)',
        data:values,
        borderColor:color,
        backgroundColor:color+'18',
        borderWidth:2,
        fill:true,
        tension:.35,
        pointRadius:values.length>20?0:4,
        pointBackgroundColor:color,
      }]
    },
    options:{
      responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{
        backgroundColor:'#161b22',borderColor:'#30363d',borderWidth:1,
        titleColor:'#8b949e',bodyColor:'#e6edf3',
        callbacks:{label:ctx=>'P&L: '+(ctx.parsed.y>=0?'+':'')+fmt$(ctx.parsed.y)}
      }},
      scales:{
        x:{grid:{color:'#21262d'},ticks:{color:'#8b949e',font:{size:11}}},
        y:{grid:{color:'#21262d'},ticks:{color:'#8b949e',font:{size:11},
             callback:v=>(v>=0?'+':'')+fmt$(v)}}
      }
    }
  });
}

function renderTradePanel(ts){
  const el = document.getElementById('tradePanel');
  if(!ts || !ts.ticker){ el.innerHTML=''; return; }
  const pnl = Number(ts.pnl_pct||0);
  const pnlCls = pnl>=0?'green':'red';
  // progress from stop (0%) through entry to target (100%)
  const lo=Number(ts.stop||0), hi=Number(ts.target||0), px=Number(ts.price||0);
  let prog = (hi>lo) ? ((px-lo)/(hi-lo))*100 : 0; prog=Math.max(0,Math.min(100,prog));
  const sold = (ts.initial_shares&&ts.remaining_shares!=null)
    ? `${ts.initial_shares-ts.remaining_shares}/${ts.initial_shares} sold` : '';
  el.innerHTML = `<div class="trade-panel">
    <div class="hdr">
      <a class="tk" href="https://www.tradingview.com/chart/?symbol=${ts.ticker}" target="_blank" rel="noopener">${ts.ticker} ↗</a>
      <div class="pnl ${pnlCls}">${pnl>=0?'+':''}${pnl.toFixed(1)}%</div>
    </div>
    <div class="trade-grid">
      <div class="cell"><div class="lbl">Entry</div><div class="val">$${Number(ts.entry).toFixed(2)}</div></div>
      <div class="cell"><div class="lbl">Now</div><div class="val">$${Number(ts.price).toFixed(2)}</div></div>
      <div class="cell"><div class="lbl" title="Trigger, not the fill — sells on a 3-min CLOSE below this level, so the actual exit can be a bit lower (wick-snipe protection)">Stop ▾</div><div class="val" style="color:#f85149">$${Number(ts.stop).toFixed(2)}</div></div>
      <div class="cell"><div class="lbl">Target</div><div class="val" style="color:#3fb950">$${Number(ts.target).toFixed(2)}</div></div>
    </div>
    <div class="tbar"><div class="fill" style="width:${prog.toFixed(0)}%"></div></div>
    <div class="tbar-lbls"><span>🛑 stop</span><span>${sold}${sold&&ts.vwap?' · ':''}${ts.vwap?'VWAP $'+Number(ts.vwap).toFixed(2):''}</span><span>🎯 target</span></div>
    <div class="tbar-lbls" style="margin-top:6px"><span>High $${Number(ts.highest||ts.price).toFixed(2)}</span><span>updated ${ts.updated||''}</span></div>
  </div>`;
}

// ── Tale of the Tape: plain-English trade stories (live + booked) ──
function bankedFromFills(entry, pf){
  let banked=0, sold=0; const lines=[];
  (pf||[]).forEach(f=>{ const q=Number(f[0])||0, p=Number(f[1])||0, amt=(p-entry)*q;
    banked+=amt; sold+=q;
    lines.push(`Sold <b>${q}</b> shares at <b>$${p.toFixed(2)}</b> → banked <b>${amt>=0?'+':'−'}$${Math.abs(amt).toFixed(2)}</b>.`); });
  return {banked, sold, lines};
}

const EXIT_STORIES=[
 [/trailing stop/i,'Rode the move up, then sold when price slipped back off its high — a trailing stop protecting profit.'],
 [/stop loss/i,'The safety net did its job — price broke the stop, so the bot took the planned small loss and moved on. No hoping, no averaging down.'],
 [/health fold/i,'The move lost its pulse — price fell below VWAP and the trend line at the same time, so the bot folded early instead of riding it back down.'],
 [/vwap fade/i,'It faded below VWAP right after entry — the bot cut it fast, before a small loss could grow into a real one.'],
 [/topping tail/i,'Rejected hard at the high (a topping tail) — the "this one is done" signal. Sold, and the ticker is benched for the day.'],
 [/target/i,'Hit the full profit target. 🎯'],
 [/recovered|watchdog/i,'Bookkeeping exit — the bot restarted (or a monitor froze), so the trade was closed at the last known price to keep the books honest.'],
 [/eod|close|time/i,'Closed at end of day — the bot never holds positions overnight.'],
];
function exitStory(r){ for(const [re,s] of EXIT_STORIES){ if(re.test(r||'')) return s; } return r||'—'; }

// Live position story: what we're in for, what's banked, the sell-half point, what to look for.
function taleLiveHTML(t){
  const entry=Number(t.entry_price??t.entry??0), price=Number(t.last_price??t.price??entry);
  const stop=Number(t.stop||0), init=Number(t.initial_shares||0), rem=Number(t.remaining_shares||0);
  const b=bankedFromFills(entry, t.partial_fills);
  const dollarsIn=Number(t.position_size||entry*init);
  const tiers=t.tiers||[], tierIdx=Number(t.tier_idx||0);
  const openPnl=(price-entry)*rem;
  const worst=b.banked+(stop-entry)*rem;      // if the stop hits from here (≈ — stop is close-based)
  const high=Math.max(Number(t.highest||0), price);
  let vCls='risk', vTxt;
  if(worst>0.5)      { vCls='locked'; vTxt=`🔒 LOCKED WINNER — if the stop fills at its level, we walk away with ≈ +$${worst.toFixed(2)}. (DRY-RUN floor is simulated — a fast gap can slip it.)`; }
  else if(worst>=-0.5 && (b.banked>0.5 || stop>=entry-0.004))
                     { vCls='locked'; vTxt=`🛡️ BREAKEVEN-PROTECTED — stop at breakeven${b.banked>0.5?` and +$${b.banked.toFixed(2)} is already banked`:''}.`; }
  else               { vTxt=`🎯 WORKING — risking ≈ $${Math.abs(worst).toFixed(2)} to find out if this one runs.`; }
  const li=[];
  li.push(`We're in for <b>$${dollarsIn.toFixed(0)}</b> — ${init} shares at <b>$${entry.toFixed(2)}</b>${t.entry_time?` (${t.entry_time})`:''}${t.entry_type?`, entry signal: <b>${t.entry_type}</b>`:''}.`);
  if(b.lines.length) b.lines.forEach(x=>li.push(x));
  else li.push(`Nothing sold yet — the full position is still working.`);
  if(tierIdx===0 && tiers.length)
    li.push(`<b>Sell-half point: $${Number(tiers[0][0]).toFixed(2)}</b> — there the bot banks half (+1R, ≈ +$${(Number(t.risk_ps||0)*init*0.5).toFixed(0)}) and moves the stop to breakeven, making the trade free.`);
  else if(tierIdx===1 && tiers.length>1)
    li.push(`Half is banked. <b>Next sell: $${Number(tiers[1][0]).toFixed(2)}</b> — a quarter comes off there; the rest becomes a runner.`);
  else if(tiers.length && tierIdx>=tiers.length)
    li.push(`<b>Runner mode</b> — profit-taking is done; the last ${rem} shares ride until the trend breaks.`);
  if(stop>entry+0.004)           li.push(`The stop has climbed to <b>$${stop.toFixed(2)}</b> — locking in gains as it goes.`);
  else if(Math.abs(stop-entry)<=0.004) li.push(`The stop sits at <b>breakeven</b> ($${stop.toFixed(2)}) — the remaining ${rem} shares can't lose money.`);
  else                           li.push(`Safety net: a close below <b>$${stop.toFixed(2)}</b> ends it for ≈ −$${Math.abs((stop-entry)*rem).toFixed(2)} — the planned ~1%-of-account risk.`);
  li.push(`<b>What to look for:</b> higher lows, holding above VWAP${t.vwap?` ($${Number(t.vwap).toFixed(2)})`:''}. High so far $${high.toFixed(2)}${entry>0?` (+${((high-entry)/entry*100).toFixed(1)}%)`:''}. Right now: ${openPnl>=0?'+':'−'}$${Math.abs(openPnl).toFixed(2)} open${b.banked>0.5?` on top of the $${b.banked.toFixed(2)} banked`:''}.`);
  return `<div class="verdict ${vCls}">${vTxt}</div><ul>${li.map(x=>`<li>${x}</li>`).join('')}</ul>`;
}

// Booked trade story: same tale, told in retrospect.
function storyClosedHTML(t){
  const entry=Number(t.entry||0), exit=Number(t.exit||0), shares=Number(t.shares||0);
  const pnl=Number(t.pnl||0), pct=Number(t.pnl_pct||0);
  const risk=Number(t.planned_risk||0) || (t.stop_loss?shares*(entry-Number(t.stop_loss)):0);
  const rMult=risk>0.5?pnl/risk:null;
  const b=bankedFromFills(entry, t.partial_fills);
  const high=Number(t.highest||0);
  const inFor=Number(t.position_size||entry*shares);
  let vCls='', vTxt;
  if(pnl>0.005){ vCls='locked'; vTxt=`✅ WINNER: +$${pnl.toFixed(2)} (+${pct.toFixed(1)}%)${rMult!==null?` — <b>+${rMult.toFixed(1)}R</b> on the ≈$${risk.toFixed(0)} we risked`:''}.`; }
  else if(pnl<-0.005){ vCls='risk'; vTxt=`❌ LOSER: −$${Math.abs(pnl).toFixed(2)} (${pct.toFixed(1)}%)${rMult!==null?` — <b>${rMult.toFixed(1)}R</b>. ${rMult>=-1.2?'Right around the planned risk — exactly what a loss is supposed to look like.':'Bigger than the planned risk — worth a closer look.'}`:''}`; }
  else vTxt=`➖ SCRATCH — in and out around breakeven. No harm done.`;
  const li=[];
  li.push(`Was in for <b>$${inFor.toFixed(0)}</b> — ${shares} shares at <b>$${entry.toFixed(2)}</b>${t.entry_type?`, entry signal: <b>${t.entry_type}</b>`:''}${t.stop_loss?`, safety net at $${Number(t.stop_loss).toFixed(2)} (≈$${risk.toFixed(0)} at risk)`:''}.`);
  if(b.lines.length){ b.lines.forEach(x=>li.push(x)); li.push(`The last ${Math.max(0,shares-b.sold)} shares went out at <b>$${exit.toFixed(2)}</b>.`); }
  else li.push(`Sold everything at <b>$${exit.toFixed(2)}</b> in one piece.`);
  li.push(`<b>Why it ended:</b> ${exitStory(t.exit_reason)}`);
  if(high>entry){
    const peakPct=((high-entry)/entry*100).toFixed(1);
    if(exit>entry){ const cap=Math.max(0,Math.min(100,(exit-entry)/(high-entry)*100));
      li.push(`It peaked at <b>$${high.toFixed(2)}</b> (+${peakPct}%) — we captured ${cap.toFixed(0)}% of that run.`); }
    else li.push(`It DID go our way first — peaked at $${high.toFixed(2)} (+${peakPct}%) before turning.`);
  }
  if(t.est_slippage) li.push(`Real-world toll if this were live money: ≈ $${Number(t.est_slippage).toFixed(2)} lost to the bid/ask spread.`);
  // Same-day context: swings on this name + is another entry brewing?
  const todayET=new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'});
  if(String(t.date||'').slice(0,10)===todayET){
    const sib=(window._allTrades||[]).filter(x=>x.ticker===t.ticker&&String(x.date||'').slice(0,10)===todayET);
    const k=sib.indexOf(t)+1;
    if(sib.length>1&&k>0) li.push(`This was swing <b>#${k} of ${sib.length}</b> in ${t.ticker} today.`);
    let consec=0; for(let i=sib.length-1;i>=0;i--){ if(Number(sib[i].pnl)<0)consec++; else break; }
    const isLast=sib.length&&sib[sib.length-1]===t;
    if((window._openTickersNow||[]).includes(t.ticker))
      li.push(`🔴 <b>LIVE right now:</b> the bot is back IN ${t.ticker} as we speak — see the live card at the top of the page.`);
    else if(isLast&&/topping tail/i.test(t.exit_reason||''))
      li.push(`🚫 <b>Benched:</b> a topping-tail exit means "done with this one today" — no re-entry.`);
    else if(isLast&&consec>=3)
      li.push(`🚫 <b>Benched:</b> ${consec} straight losses on ${t.ticker} — the bot leaves it alone for the rest of the day.`);
    else if(isLast)
      li.push(`👀 <b>Heads up:</b> ${t.ticker} is back on the re-entry list — if it sets up cleanly again (a fresh pullback that holds), the bot can take another swing.`);
  }
  return `<div class="verdict ${vCls}">${vTxt}</div><ul>${li.map(x=>`<li>${x}</li>`).join('')}</ul>`;
}

window._tapeOpen=window._tapeOpen||new Set();
function toggleTape(tk){
  if(window._tapeOpen.has(tk)) window._tapeOpen.delete(tk); else window._tapeOpen.add(tk);
  renderAllTrades(window._openTradesList||[]);
}
window._storyOpen=window._storyOpen||new Set();
function toggleStory(key, ev){
  if(ev&&ev.target&&ev.target.closest('a')) return;   // let the chart link work normally
  if(window._storyOpen.has(key)) window._storyOpen.delete(key); else window._storyOpen.add(key);
  renderTable(window._allTrades||[]);
}

// Render ONE open-position card. Normalizes /api/open_trades fields (entry_price/last_price)
// so ALL concurrent positions show — the single-slot trade_state card only ever showed one.
function tradeCardHTML(t){
  const entry = Number(t.entry_price ?? t.entry ?? 0);
  const price = Number(t.last_price ?? t.price ?? 0);
  const pnl   = entry>0 ? (price-entry)/entry*100 : Number(t.pnl_pct||0);
  const pnlCls= pnl>=0?'green':'red';
  const lo=Number(t.stop||0), hi=Number(t.target||0);
  let prog=(hi>lo)?((price-lo)/(hi-lo))*100:0; prog=Math.max(0,Math.min(100,prog));
  const sold=(t.initial_shares&&t.remaining_shares!=null)
    ? `${t.initial_shares-t.remaining_shares}/${t.initial_shares} sold` : '';
  const et = t.entry_type ? String(t.entry_type) : '';
  let upd = t.updated || '';
  if(upd && String(upd).length>12){ try{ upd=new Date(upd).toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',second:'2-digit'})+' ET'; }catch(e){} }
  return `<div class="trade-panel" style="margin-bottom:12px">
    <div class="hdr">
      <a class="tk" href="https://www.tradingview.com/chart/?symbol=${t.ticker}" target="_blank" rel="noopener">${t.ticker} ↗</a>
      <div class="pnl ${pnlCls}">${pnl>=0?'+':''}${pnl.toFixed(1)}%</div>
    </div>
    <div class="trade-grid">
      <div class="cell"><div class="lbl">Entry</div><div class="val">$${entry.toFixed(2)}</div></div>
      <div class="cell"><div class="lbl">Now</div><div class="val">$${price.toFixed(2)}</div></div>
      <div class="cell"><div class="lbl" title="Trigger, not the fill — sells on a 3-min CLOSE below this level, so the actual exit can be a bit lower (wick-snipe protection)">Stop ▾</div><div class="val" style="color:#f85149">$${Number(t.stop||0).toFixed(2)}</div></div>
      <div class="cell"><div class="lbl">Target</div><div class="val" style="color:#3fb950">$${Number(t.target||0).toFixed(2)}</div></div>
    </div>
    <div class="tbar"><div class="fill" style="width:${prog.toFixed(0)}%"></div></div>
    <div class="tbar-lbls"><span>🛑 stop</span><span>${sold}${(sold&&(t.vwap||et))?' · ':''}${t.vwap?'VWAP $'+Number(t.vwap).toFixed(2):''}${et?(t.vwap?' · ':'')+et:''}</span><span>🎯 target</span></div>
    <div class="tbar-lbls" style="margin-top:6px"><span>High $${Number(t.highest||price).toFixed(2)}</span><span>updated ${upd}</span></div>
    <button class="tape-btn" onclick="toggleTape('${t.ticker}')">${window._tapeOpen.has(t.ticker)?'▲ Hide the tale':'📖 Tale of the tape — what\\'s the plan here?'}</button>
    <div class="tape ${window._tapeOpen.has(t.ticker)?'show':''}">${window._tapeOpen.has(t.ticker)?taleLiveHTML(t):''}</div>
  </div>`;
}

function renderAllTrades(list){
  window._openTradesList=list||[];
  window._openTickersNow=(list||[]).map(t=>t.ticker);
  const el=document.getElementById('tradePanel');
  if(!list||!list.length){ el.innerHTML=''; return; }
  const used=list.reduce((a,t)=>a+Number(t.position_size||(Number(t.entry_price||0)*Number(t.initial_shares||0))),0);
  const budget=Number(window._acctBal)||3000;
  const free=Math.max(0,budget-used);
  const pct=Math.max(0,Math.min(100,budget>0?used/budget*100:0));
  const money=v=>'$'+Math.round(v).toLocaleString('en-US');
  el.innerHTML = `<div class="cap-strip">
      <div class="cap-lbl">💵 In trades: <b>${money(used)}</b> of ${money(budget)} (${pct.toFixed(0)}%) · <b>${money(free)}</b> free for the next setup</div>
      <div class="cap-bar"><div class="cap-fill" style="width:${pct.toFixed(0)}%"></div></div>
    </div>`
    + `<div style="font-size:12px;color:#8b949e;margin-bottom:8px">${list.length} open position${list.length>1?'s':''}</div>`
    + list.map(tradeCardHTML).join('');
}

function loadWatching(){
  // Open positions are the SOURCE OF TRUTH. /api/watching's "tickers" field goes STALE during trades — the bot
  // overwrites it with the single last-entered ticker, which lingers after that ticker closes while OTHER positions
  // live on (the "ghost KIDZ chip" bug). So: during trades show the position CARDS + an "In N trades" status and
  // suppress the chips; only show watchlist chips when FLAT, where the tickers field is reliable.
  fetch('/api/open_trades')
    .then(r=>r.json())
    .then(od=>{
      const open = (od && od.open_trades) || [];
      renderAllTrades(open);
      const statusEl  = document.getElementById('watchStatus');
      const tickersEl = document.getElementById('watchTickers');
      return fetch('/api/watching').then(r=>r.json()).then(d=>{
        if(open.length){                                   // IN A TRADE — cards are the truth, chips suppressed
          const since = (d && d.started_at) ? new Date(d.started_at).toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'}) : '';
          statusEl.innerHTML = `<span class="status-dot trading"></span>In ${open.length} trade${open.length>1?'s':''}${since?' since '+since:''}`;
          tickersEl.innerHTML = '';
          return;
        }
        const tk = (d && d.tickers) || [];                 // FLAT — the tickers field IS the reliable watchlist
        if(!tk.length){
          statusEl.innerHTML = '<span class="status-dot idle"></span>Idle — outside market hours or no setup';
          tickersEl.innerHTML = ''; return;
        }
        statusEl.innerHTML = '<span class="status-dot watching"></span>Watching for setup (flat-top · ORB · pullback)';
        tickersEl.innerHTML = tk.map(t=>
          `<a class="watch-chip watching" href="https://www.tradingview.com/chart/?symbol=${t}" target="_blank" rel="noopener" title="Open ${t} chart">${t} ↗</a>`
        ).join('');
      });
    })
    .catch(()=>{});
}

// Auto-refresh every 60 seconds
function loadMarket(){
  fetch('/api/market').then(function(r){return r.json();}).then(function(m){
    var el=document.getElementById('marketInner');
    var idx=(m&&m.indices)||[];
    if(!idx.length){ el.innerHTML='<span class="market-loading">Market data unavailable</span>'; }
    else {
      var want=['S&P 500','Dow Jones','Nasdaq'];
      var have=idx.map(function(i){return i.label;});
      want.forEach(function(w){ if(have.indexOf(w)<0) idx.push({label:w,chg:null,price:null}); });
      idx.sort(function(a,b){return want.indexOf(a.label)-want.indexOf(b.label);});
      el.innerHTML = idx.map(function(i){
        if(i.chg===null||i.chg===undefined) return '<div class="mkt-idx"><span class="mkt-name">'+i.label+'</span><span class="mkt-chg white">—</span></div>';
        var chg=parseFloat(i.chg)||0, cls=chg>0?'green':chg<0?'red':'white', arrow=chg>0?'▲':chg<0?'▼':'';
        var px=(i.price!=null&&i.price!=='')?'<span class="mkt-px">'+Number(i.price).toLocaleString(undefined,{maximumFractionDigits:2})+'</span>':'';
        return '<div class="mkt-idx"><span class="mkt-name">'+i.label+'</span>'+
               '<span class="mkt-chg '+cls+'">'+arrow+' '+(chg>=0?'+':'')+chg.toFixed(2)+'%</span>'+px+'</div>';
      }).join('');
    }
    document.getElementById('marketUpdated').textContent=(m&&m.updated)?('as of '+m.updated):'';
  }).catch(function(){ document.getElementById('marketInner').innerHTML='<span class="market-loading">Market data unavailable</span>'; });
}

loadData();
loadWatching();
loadMarket();
setInterval(loadData, 60000);
setInterval(loadWatching, 30000);
setInterval(loadMarket, 60000);
</script>
</body>
</html>"""


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)

# build-trigger 7/20-night: ship 9dcf223 (minute_ext trading_sessions) — the redeploy reused the stale image
