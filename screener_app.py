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

app = Flask(__name__)

# ── Trade storage (in-memory + JSON file) ─────────────────────────────────────

_trades: list = []
_account: dict = {"balance": 0.0, "updated": ""}
_watching: dict = {}                   # Live watch list posted by bot each session
_trade_state: dict = {}                # Live state of the active trade (entry/price/pnl/stop/target)

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
    try:
        TRADES_FILE.write_text(json.dumps({"trades": _trades, "account": _account}, indent=2))
    except Exception as e:
        print(f"⚠️  Could not save trades: {e}")

def _compute_stats():
    if not _trades:
        return {
            "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0,
            "total_pnl": 0, "avg_gain": 0, "avg_loss": 0,
            "best_pnl": 0, "best_ticker": "—", "worst_pnl": 0, "worst_ticker": "—",
            "equity_curve": [],
        }
    wins   = [t for t in _trades if t.get("pnl", 0) > 0]
    losses = [t for t in _trades if t.get("pnl", 0) <= 0]
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
        "win_rate":     round(len(wins) / len(_trades) * 100, 1),
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
        OBS_FILE.write_text(json.dumps(_obs, indent=2))
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


def _make_data_client():
    if not WEBULL_SDK_AVAILABLE or not WebullDataClient:
        return None
    try:
        _pre_populate_token()
        api_client = ApiClient(WEBULL_APP_KEY, WEBULL_APP_SECRET, "us",
                               token_check_duration_seconds=60,
                               token_check_interval_seconds=5)
        api_client.set_token_dir(WEBULL_TOKEN_DIR)
        api_client.add_endpoint("us", TRADING_HOST)
        return WebullDataClient(api_client)
    except Exception as e:
        print(f"DataClient error: {e}")
        return None

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

def run_scan():
    """
    1. Webull screener → live gainers / pre-market / after-hours movers
    2. Filter: price $0.50–$30, move threshold varies by session
    3. yfinance float check → drop large floats (50M live, 100M evening)
    4. After hours: add short interest + day stats for tomorrow's watchlist
    5. Score by change% / float_millions, return top 15 (20 evening)
    """
    now_et, market_open, premarket, after_hours, _ = _market_state()
    rank_type   = "CHANGE_RATIO" if market_open else "PRE_MARKET"
    min_chg     = 5 if market_open else 8
    max_float   = 50_000_000
    top_n       = 15
    if after_hours:
        rank_type = "CHANGE_RATIO"
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
                    if not sym or price < 0.50 or price > 30 or chg < min_chg:
                        continue
                    candidates[sym] = {
                        "symbol": sym, "change_pct": round(chg, 2),
                        "price": round(price, 2), "market_cap": mktcap,
                        "premarket_volume": int(vol), "relative_volume": None,
                        "float_shares": 0, "float_label": "—", "source": source_label,
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
                    chg_min  = 5 if after_hours else 3
                    if not sym or price < 0.50 or price > 30 or rel_vol < rvol_min:
                        continue
                    if sym in candidates:
                        candidates[sym]["relative_volume"] = round(rel_vol, 1)
                    elif chg >= chg_min:
                        candidates[sym] = {
                            "symbol": sym, "change_pct": round(chg, 2),
                            "price": round(price, 2), "market_cap": mktcap,
                            "premarket_volume": int(vol), "relative_volume": round(rel_vol, 1),
                            "float_shares": 0, "float_label": "—", "source": "Unusual volume",
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
    return results, errors

# ── HTML template ──────────────────────────────────────────────────────────────

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

  .table-wrap{border-radius:10px;border:1px solid #21262d;overflow:hidden}
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
  tbody td{padding:12px 16px;color:#e6edf3}

  .ticker-cell{font-weight:600;font-size:14px;color:#58a6ff}
  .price-cell{font-variant-numeric:tabular-nums}
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
  .bot-pill{display:inline-block;background:#1a3a2a;border:1px solid #2d5a3d;
            color:#3fb950;font-size:10px;font-weight:600;padding:1px 6px;
            border-radius:4px;margin-left:6px;vertical-align:middle}
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
    if(on && row.dataset.bot==='0') row.style.display='none';
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
  var tbody=document.getElementById('tbody');
  tbody.innerHTML=sorted.map(function(r){
    var isBot=(r.relative_volume&&r.relative_volume>=1.5)||r.change_pct>=5;
    var gapClass=r.change_pct>=10?'gap-hot':'gap-warm';
    var floatClass=r.float_tier==='small'?'float-small':r.float_tier==='medium'?'float-med':'float-na';
    var relVol=r.relative_volume?r.relative_volume.toFixed(1)+'×':'—';
    var mktcap=r.market_cap?'$'+fmtM(r.market_cap):'—';
    var botBadge=isBot?'<span class="bot-pill">BOT</span>':'';
    var shortPct = r.short_interest ? r.short_interest.toFixed(1)+'%' : '—';
    var dayRange = r.day_range_pct ? r.day_range_pct.toFixed(1)+'%' : '—';
    var shortClass = r.short_interest >= 20 ? 'gap-hot' : r.short_interest >= 10 ? 'gap-warm' : '';
    var eveningStyle = _afterHours ? '' : 'display:none';
    return '<tr class="'+(isBot?'bot-candidate':'')+'" data-bot="'+(isBot?'1':'0')+'">'
      +'<td class="ticker-cell">'+r.symbol+botBadge+'</td>'
      +'<td class="price-cell">$'+r.price.toFixed(2)+'</td>'
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
  var botCount=rows.filter(function(r){return (r.relative_volume&&r.relative_volume>=1.5)||r.change_pct>=5;}).length;
  document.getElementById('s-bot-count').textContent=botCount?botCount+' bot candidates':'';
  renderRows(rows);

  // Errors
  if(errs.length){
    document.getElementById('errors-wrap').innerHTML=
      '<div class="errors">⚠ '+errs.join(' | ')+'</div>';
  }
}

// Auto-scan on load
runScan();

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
    return render_template_string(HTML)


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
        "recorded_at":   datetime.now(EASTERN).isoformat(),
    }
    _trades.append(trade)
    if data.get("account_balance"):
        _account["balance"] = round(float(data["account_balance"]), 2)
        _account["updated"] = datetime.now(EASTERN).strftime("%I:%M %p ET")
    _save_trades()
    print(f"📋 Trade recorded: {trade['ticker']} {trade['pnl']:+.2f}")
    return jsonify({"status": "ok", "total_trades": len(_trades)})


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


@app.route("/api/account_balance", methods=["GET"])
def get_account_balance_api():
    return jsonify({"balance": _account.get("balance", 0.0), "updated": _account.get("updated", "")})


@app.route("/api/trades")
def api_trades():
    return jsonify({"trades": _trades, "stats": _compute_stats(), "account": _account})

@app.route("/api/trades/clear", methods=["POST"])
def clear_trades():
    global _trades
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    _trades = []
    _save_trades()
    return jsonify({"status": "ok", "total_trades": 0})



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
    print(f"👀 Watch list updated: {_watching['tickers']} [{_watching['status']}]")
    return jsonify({"ok": True})

@app.route("/api/watching", methods=["GET"])
def get_watching():
    # include live trade state, but only if fresh (bot stops posting when the trade ends)
    ts = _trade_state
    fresh = bool(ts) and (time.time() - ts.get("_recv", 0) <= 90)
    return jsonify({**_watching, "trade_state": (ts if fresh else None)})


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
    try:
        OPEN_TRADES_FILE.write_text(json.dumps(_open_trades, indent=2))
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
    try:    ROOM_SKIPS_FILE.write_text(json.dumps(_room_skips[-500:], indent=2))
    except Exception as e: print(f"⚠️  Could not save room_skips: {e}")
    return jsonify({"status": "ok", "total": len(_room_skips)})

# ── Per-candidate DECISION log — the full "why did/didn't we trade X" timeline (observability) ──
# Every watched candidate's disposition each evaluation (throttled bot-side): below_vwap, consolidating,
# broke_not_flat (the SDOT/IVF detection gap), broke_below_vwap, broke_no_room, entered_*, spread_reject, etc.
DECISIONS_FILE = pathlib.Path("/data/decisions.json") if pathlib.Path("/data").exists() else pathlib.Path("/tmp/decisions.json")
_decisions: list = []
if DECISIONS_FILE.exists():
    try:    _decisions = json.loads(DECISIONS_FILE.read_text())
    except Exception: _decisions = []

@app.route("/api/decision", methods=["POST"])
def add_decision():
    if request.headers.get("X-Dashboard-Secret") != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    now = datetime.now(EASTERN)
    d["recorded_at"] = now.isoformat()
    d.setdefault("date", now.strftime("%Y-%m-%d"))
    d.setdefault("time", now.strftime("%I:%M:%S %p"))
    _decisions.append(d)
    try:    DECISIONS_FILE.write_text(json.dumps(_decisions[-8000:], indent=2))
    except Exception as e: print(f"⚠️  Could not save decisions: {e}")
    return jsonify({"status": "ok", "total": len(_decisions)})

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
    return render_template_string(DASHBOARD_HTML)


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
    return render_template_string(DAY2_HTML)


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
.table-wrap{background:#161b22;border:1px solid #21262d;border-radius:12px;overflow:hidden}
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
.panel-card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:16px 18px}
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

<div class="balance-banner" id="balanceBanner">
  <div class="balance-row">
    <div class="balance-main">
      <div class="balance-label">Account Balance</div>
      <div class="balance-value" id="balanceVal">—</div>
      <div id="balanceChange"></div>
    </div>
    <div style="display:flex;gap:32px;align-items:flex-end;padding-bottom:4px">
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
    </div>
  </div>
</div>

<div class="strategy-panel">
  <div class="panel-card">
    <div class="panel-title">v10 Strategy Parameters</div>
    <div class="param-grid">
      <div class="param-pill"><span>Qualify</span><strong>RVOL &gt;1.5× + 10% range</strong></div>
      <div class="param-pill"><span>Flat Top</span><strong>4 bars &lt;8% range</strong></div>
      <div class="param-pill"><span>Entry Cutoff</span><strong>11:00am ET</strong></div>
      <div class="param-pill"><span>Trail Stop</span><strong>5%</strong></div>
      <div class="param-pill"><span>Partial AM</span><strong>25%@+8%, 50%@+12%, 25%@+20%</strong></div>
      <div class="param-pill"><span>Partial PM</span><strong>50%@+4%, 50%@+6%</strong></div>
      <div class="param-pill"><span>VWAP Max Ext</span><strong>8%</strong></div>
      <div class="param-pill"><span>Min R:R</span><strong>2:1</strong></div>
      <div class="param-pill"><span>VWAP</span><strong>required</strong></div>
      <div class="param-pill"><span>Level 2</span><strong>required</strong></div>
      <div class="param-pill"><span>Momentum</span><strong>10k vol, 2/3 green</strong></div>
      <div class="param-pill"><span>Topping Tail</span><strong>skip + exit (Kev)</strong></div>
      <div class="param-pill"><span>90 EMA</span><strong>recording (data-only)</strong></div>
      <div class="param-pill"><span>Floor</span><strong>entry price after partial</strong></div>
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
  <div class="stat-card"><div class="stat-label">Avg Gain</div><div class="stat-value green" id="avgGain">—</div><div class="stat-sub">per winning trade</div></div>
  <div class="stat-card"><div class="stat-label">Avg Loss</div><div class="stat-value red" id="avgLoss">—</div><div class="stat-sub">per losing trade</div></div>
  <div class="stat-card"><div class="stat-label">Best Trade</div><div class="stat-value green" id="bestPnl">—</div><div class="stat-sub" id="bestTicker">—</div></div>
  <div class="stat-card"><div class="stat-label">Worst Trade</div><div class="stat-value red" id="worstPnl">—</div><div class="stat-sub" id="worstTicker">—</div></div>
  <div class="stat-card"><div class="stat-label">Wins</div><div class="stat-value green" id="wins">—</div><div class="stat-sub">profitable sessions</div></div>
  <div class="stat-card"><div class="stat-label">Losses</div><div class="stat-value red" id="losses">—</div><div class="stat-sub">stopped out sessions</div></div>
</div>

<div class="content">
  <div class="section-title">Equity Curve</div>
  <div class="chart-wrap">
    <canvas id="equityChart"></canvas>
  </div>

  <div class="section-title">Trade History</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Ticker</th>
          <th>Entry</th>
          <th>Exit</th>
          <th>Shares</th>
          <th>Size</th>
          <th>P&amp;L $</th>
          <th>P&amp;L %</th>
          <th>Exit Reason</th>
          <th>Float</th>
        </tr>
      </thead>
      <tbody id="tradeTable">
        <tr><td colspan="11"><div class="empty-state"><div class="icon">📊</div><p>Loading trade history...</p></div></td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
let chart = null;

function fmt$(n){ return n===null||n===undefined?'—':'$'+Math.abs(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtPct(n){ return n===null||n===undefined?'—':(n>=0?'+':'')+n.toFixed(1)+'%'; }
function fmtPnl$(n){ return (n>=0?'+':'')+fmt$(n); }

function loadData(){
  document.getElementById('lastUpdate').textContent = 'Refreshing...';
  fetch('/api/trades')
    .then(r=>r.json())
    .then(data=>{
      renderStats(data.stats, data.account);
      renderTable(data.trades);
      renderChart(data.stats.equity_curve);
      document.getElementById('lastUpdate').textContent =
        'Updated ' + new Date().toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});
    })
    .catch(()=>{ document.getElementById('lastUpdate').textContent = 'Error loading data'; });
}

function renderStats(s, acct){
  const bal = acct && acct.balance ? acct.balance : 0;
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

  if(bal>0 && pnl!==0){
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
    tbody.innerHTML = `<tr><td colspan="10"><div class="empty-state">
      <div class="icon">📊</div>
      <p>No trades recorded yet</p>
      <small>The bot will log results here automatically after each session</small>
    </div></td></tr>`;
    return;
  }
  const rows = [...trades].reverse().map(t=>{
    const pnlCls  = t.pnl>=0?'pnl-pos':'pnl-neg';
    const pnlSign = t.pnl>=0?'+':'';
    const pctSign = t.pnl_pct>=0?'+':'';
    const fl = t.float_shares ? String(t.float_shares).replace(/(\d)(?=(\d{3})+$)/g,'$1,') : '—';
    const sz = t.position_size ? fmt$(t.position_size) : '—';
    return `<tr>
      <td style="color:#8b949e">${t.date||'—'}</td>
      <td><a class="ticker-badge" href="https://www.tradingview.com/chart/?symbol=${t.ticker||''}" target="_blank" rel="noopener" title="Open chart">${t.ticker||'—'} ↗</a></td>
      <td>${t.entry?'$'+t.entry.toFixed(2):'—'}</td>
      <td>${t.exit?'$'+t.exit.toFixed(2):'—'}</td>
      <td style="color:#8b949e">${t.shares||'—'}</td>
      <td style="color:#8b949e">${sz}</td>
      <td class="${pnlCls}">${pnlSign}$${Math.abs(t.pnl).toFixed(2)}</td>
      <td class="${pnlCls}">${pctSign}${t.pnl_pct.toFixed(1)}%</td>
      <td class="exit-tag" title="${t.exit_reason||''}">${t.exit_reason||'—'}</td>
      <td style="color:#8b949e;font-size:12px">${fl}</td>
    </tr>`;
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
      <div class="cell"><div class="lbl">Stop</div><div class="val" style="color:#f85149">$${Number(ts.stop).toFixed(2)}</div></div>
      <div class="cell"><div class="lbl">Target</div><div class="val" style="color:#3fb950">$${Number(ts.target).toFixed(2)}</div></div>
    </div>
    <div class="tbar"><div class="fill" style="width:${prog.toFixed(0)}%"></div></div>
    <div class="tbar-lbls"><span>🛑 stop</span><span>${sold}${sold&&ts.vwap?' · ':''}${ts.vwap?'VWAP $'+Number(ts.vwap).toFixed(2):''}</span><span>🎯 target</span></div>
    <div class="tbar-lbls" style="margin-top:6px"><span>High $${Number(ts.highest||ts.price).toFixed(2)}</span><span>updated ${ts.updated||''}</span></div>
  </div>`;
}

function loadWatching(){
  fetch('/api/watching')
    .then(r=>r.json())
    .then(d=>{
      const statusEl  = document.getElementById('watchStatus');
      const tickersEl = document.getElementById('watchTickers');
      renderTradePanel(d && d.trade_state);
      if(!d || !d.tickers || d.tickers.length===0){
        statusEl.innerHTML = '<span class="status-dot idle"></span>Idle — outside market hours or no setup';
        tickersEl.innerHTML = '';
        return;
      }
      const st = d.status || 'watching';
      const cls = st === 'trading' ? 'trading' : 'watching';
      const label = st === 'trading' ? 'In trade' : 'Watching for flat top breakout';
      const since = d.started_at ? new Date(d.started_at).toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'}) : '';
      statusEl.innerHTML = `<span class="status-dot ${cls}"></span>${label}${since?' since '+since:''}`;
      tickersEl.innerHTML = d.tickers.map(t=>
        `<a class="watch-chip ${cls}" href="https://www.tradingview.com/chart/?symbol=${t}" target="_blank" rel="noopener" title="Open ${t} chart">${t} ↗</a>`
      ).join('');
    })
    .catch(()=>{});
}

// Auto-refresh every 60 seconds
loadData();
loadWatching();
setInterval(loadData, 60000);
setInterval(loadWatching, 30000);
</script>
</body>
</html>"""


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
