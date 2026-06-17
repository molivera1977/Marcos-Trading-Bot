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
TRADES_FILE         = pathlib.Path("/tmp/marcos_trades.json")
API_SECRET          = os.environ.get("DASHBOARD_SECRET", "marcos2026")

app = Flask(__name__)

# ── Trade storage (in-memory + JSON file) ─────────────────────────────────────

_trades: list = []
_account: dict = {"balance": 0.0, "updated": ""}
_evening_watchlist: dict = {}          # Latest watchlist from evening scan
_kev_picks: dict = {}                  # Kev's transcript submitted via web form
WATCHLIST_FILE = pathlib.Path("/tmp/marcos_evening_watchlist.json")
KEV_PICKS_FILE = pathlib.Path("/tmp/marcos_kev_picks.json")

def _load_watchlist():
    global _evening_watchlist
    if WATCHLIST_FILE.exists():
        try:
            _evening_watchlist = json.loads(WATCHLIST_FILE.read_text())
        except Exception:
            pass

def _save_watchlist():
    try:
        WATCHLIST_FILE.write_text(json.dumps(_evening_watchlist, indent=2))
    except Exception as e:
        print(f"⚠️  Could not save watchlist: {e}")

def _load_kev_picks():
    global _kev_picks
    if KEV_PICKS_FILE.exists():
        try:
            _kev_picks = json.loads(KEV_PICKS_FILE.read_text())
        except Exception:
            pass

def _save_kev_picks():
    try:
        KEV_PICKS_FILE.write_text(json.dumps(_kev_picks, indent=2))
    except Exception as e:
        print(f"⚠️  Could not save Kev picks: {e}")

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
_load_watchlist()
_load_kev_picks()

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

# ── Core scan logic ────────────────────────────────────────────────────────────

def run_scan():
    """
    1. Webull screener → live gainers (market hours) or pre-market gainers (before open)
    2. Filter: price $1–$30, gap >5% intraday / >8% pre-market, dedup
    3. yfinance float check → drop anything >50M shares
    4. Score by gap% / float_millions, return top 15
    """
    now_et      = datetime.now(EASTERN)
    market_open = now_et.hour > 9 or (now_et.hour == 9 and now_et.minute >= 30)
    after_hours = now_et.hour >= 16
    rank_type   = "CHANGE_RATIO" if market_open else "PRE_MARKET"
    min_chg     = 5 if market_open else 8
    if after_hours:
        rank_type = "CHANGE_RATIO"   # use day's final change after close
        min_chg   = 5
    source_label = "Live gainer" if market_open else "Pre-mkt gainer"

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
                    if not sym or price < 0.50 or price > 30 or rel_vol < 2:
                        continue
                    if sym in candidates:
                        candidates[sym]["relative_volume"] = round(rel_vol, 1)
                    elif chg >= 3:
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

    # Float check via yfinance
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
                results.append(g)
            elif float_sh <= 10_000_000:
                g["float_label"] = f"{float_m:.1f}M"
                g["float_tier"] = "small"
                results.append(g)
            elif float_sh <= 50_000_000:
                g["float_label"] = f"{float_m:.1f}M"
                g["float_tier"] = "medium"
                results.append(g)
            # >50M — drop
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

    results = sorted(results, key=score, reverse=True)[:15]
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
           border-bottom:1px solid #21262d}
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
      <sub id="scanner-sub">Small-float movers</sub>
    </div>
  </div>
  <div class="header-right">
    <span class="ts" id="ts">—</span>
    <button class="btn" id="scan-btn" onclick="runScan()">&#8635; Scan now</button>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="stat-label">Candidates</div><div class="stat-value" id="s-count">—</div></div>
  <div class="stat"><div class="stat-label">Avg gap</div><div class="stat-value green" id="s-gap">—</div></div>
  <div class="stat"><div class="stat-label">Smallest float</div><div class="stat-value green" id="s-float">—</div></div>
  <div class="stat"><div class="stat-label">Top rel vol</div><div class="stat-value" id="s-vol">—</div></div>
</div>

<div class="body">
  <div class="section-header">
    <span class="section-title" id="section-title">Small-float movers</span>
    <span class="live-dot" id="live-badge">Live</span>
  </div>

  <div class="loader" id="loader">
    <div class="spinner"></div>
    Scanning Webull screener + checking floats via yfinance…
  </div>

  <div class="table-wrap" id="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Ticker</th><th>Price</th><th>Gap %</th><th>Float</th>
          <th>Rel vol</th><th>Mkt cap</th><th>Source</th>
        </tr>
      </thead>
      <tbody id="tbody"><tr><td colspan="7" class="empty">Click "Scan now" to load.</td></tr></tbody>
    </table>
  </div>
  <div id="errors-wrap"></div>
</div>

<script>
function fmt(n){return n==null?'—':n.toLocaleString()}
function fmtM(n){if(!n||n===0)return'—';var m=n/1e6;return m<1?(m*1000).toFixed(0)+'K':m.toFixed(1)+'M'}

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
    premarket:   {sub:'Pre-market small-float gappers', title:'Small-float pre-market movers'},
    open:        {sub:'Live market small-float movers',  title:'Small-float live market movers'},
    after_hours: {sub:'After-hours small-float movers',  title:'Small-float after-hours movers'},
  };
  var lbl = stateLabels[d.market_state] || stateLabels['open'];
  document.getElementById('scanner-sub').textContent  = lbl.sub;
  document.getElementById('section-title').textContent = lbl.title;

  // Timestamp
  var now=new Date(d.updated);
  document.getElementById('ts').textContent='Updated '+now.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',timeZoneName:'short'});

  // Table
  var tbody=document.getElementById('tbody');
  if(!rows.length){
    tbody.innerHTML='<tr><td colspan="7" class="empty">No candidates found. Markets may be closed or pre-market data unavailable.</td></tr>';
    return;
  }

  tbody.innerHTML=rows.map(function(r){
    var gapClass=r.change_pct>=15?'gap-hot':'gap-warm';
    var floatClass=r.float_tier==='small'?'float-small':r.float_tier==='medium'?'float-med':'float-na';
    var relVol=r.relative_volume?r.relative_volume.toFixed(1)+'×':'—';
    var mktcap=r.market_cap?'$'+fmtM(r.market_cap):'—';
    return '<tr>'
      +'<td class="ticker-cell">'+r.symbol+'</td>'
      +'<td class="price-cell">$'+r.price.toFixed(2)+'</td>'
      +'<td><span class="gap-pill '+gapClass+'">+'+r.change_pct.toFixed(1)+'%</span></td>'
      +'<td class="'+floatClass+'">'+r.float_label+'</td>'
      +'<td>'+relVol+'</td>'
      +'<td>'+mktcap+'</td>'
      +'<td><span class="source-badge">'+r.source+'</span></td>'
      +'</tr>';
  }).join('');

  // Errors
  if(errs.length){
    document.getElementById('errors-wrap').innerHTML=
      '<div class="errors">⚠ '+errs.join(' | ')+'</div>';
  }
}

// Auto-scan on load
runScan();

// Auto-refresh every 5 minutes during market hours (4am–5pm ET)
setInterval(function(){
  var etHour = new Date().toLocaleString('en-US',{timeZone:'America/New_York',hour:'numeric',hour12:false});
  var h = parseInt(etHour);
  if(h>=4&&h<17){runScan();}
},5*60*1000);

// ── Kev's Picks modal ──────────────────────────────────────────────────────
function openKevModal(){
  document.getElementById('kev-modal').style.display='flex';
  document.getElementById('kev-textarea').focus();
  // Show saved status if already submitted today
  fetch('/api/kev_picks').then(r=>r.json()).then(function(d){
    if(d.transcript){
      document.getElementById('kev-status').textContent='Last saved: '+d.saved_at_display;
      document.getElementById('kev-textarea').value=d.transcript;
    }
  }).catch(function(){});
}
function closeKevModal(){
  document.getElementById('kev-modal').style.display='none';
}
function submitKevPicks(){
  var text=document.getElementById('kev-textarea').value.trim();
  if(!text){alert('Paste Kev\\'s transcript first.');return;}
  var btn=document.getElementById('kev-submit-btn');
  btn.disabled=true;btn.textContent='Saving…';
  fetch('/api/kev_picks',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({transcript:text})
  }).then(function(r){return r.json()}).then(function(d){
    if(d.status==='ok'){
      document.getElementById('kev-status').textContent='✅ Saved ('+d.chars+' chars) — evening scan will pick this up';
      btn.textContent='Saved!';
      setTimeout(function(){closeKevModal();btn.disabled=false;btn.textContent='Save Kev\\'s Picks';},1500);
    } else {
      btn.disabled=false;btn.textContent='Save Kev\\'s Picks';
      alert('Error: '+(d.error||'unknown'));
    }
  }).catch(function(e){
    btn.disabled=false;btn.textContent='Save Kev\\'s Picks';
    alert('Network error: '+e);
  });
}
</script>

<!-- Floating Kev button -->
<button onclick="openKevModal()" style="position:fixed;bottom:24px;right:24px;z-index:100;
  background:#1a3a2a;color:#3fb950;border:1px solid #2d5a3d;border-radius:50px;
  font-family:inherit;font-size:14px;font-weight:600;padding:12px 20px;cursor:pointer;
  box-shadow:0 4px 20px rgba(0,0,0,.4)">📝 Kev's Picks</button>

<!-- Modal overlay -->
<div id="kev-modal" style="display:none;position:fixed;inset:0;z-index:200;
  background:rgba(0,0,0,.75);align-items:center;justify-content:center;padding:16px">
  <div style="background:#161b22;border:1px solid #30363d;border-radius:14px;
    width:100%;max-width:540px;padding:24px;display:flex;flex-direction:column;gap:14px">
    <div style="display:flex;align-items:center;justify-content:space-between">
      <div>
        <div style="font-size:16px;font-weight:700">📝 Kev's Picks</div>
        <div style="font-size:12px;color:#8b949e;margin-top:2px">Paste tonight's full transcript</div>
      </div>
      <button onclick="closeKevModal()" style="background:none;border:none;color:#8b949e;
        font-size:22px;cursor:pointer;padding:4px 8px">×</button>
    </div>
    <textarea id="kev-textarea" placeholder="Paste Kev's full transcript here — tickers, levels, setup explanations, everything..." style="
      width:100%;height:220px;background:#0d1117;color:#e6edf3;border:1px solid #30363d;
      border-radius:8px;padding:12px;font-family:inherit;font-size:13px;line-height:1.6;
      resize:vertical;outline:none"></textarea>
    <div id="kev-status" style="font-size:12px;color:#8b949e;min-height:16px"></div>
    <div style="display:flex;gap:10px;justify-content:flex-end">
      <button onclick="closeKevModal()" style="padding:9px 18px;border-radius:8px;
        border:1px solid #30363d;background:transparent;color:#8b949e;font-family:inherit;
        font-size:13px;cursor:pointer">Cancel</button>
      <button id="kev-submit-btn" onclick="submitKevPicks()" style="padding:9px 20px;
        border-radius:8px;border:1px solid #2d5a3d;background:#1a3a2a;color:#3fb950;
        font-family:inherit;font-size:13px;font-weight:600;cursor:pointer">Save Kev's Picks</button>
    </div>
  </div>
</div>

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
    now_et      = datetime.now(EASTERN)
    market_open = now_et.hour > 9 or (now_et.hour == 9 and now_et.minute >= 30)
    after_hours = now_et.hour >= 16
    if after_hours:
        market_state = "after_hours"
    elif market_open:
        market_state = "open"
    else:
        market_state = "premarket"
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
    trade = {
        "date":          data.get("date", datetime.now(EASTERN).strftime("%Y-%m-%d")),
        "ticker":        data.get("ticker", "UNKNOWN"),
        "entry":         round(float(data.get("entry", 0)), 2),
        "exit":          round(float(data.get("exit", 0)), 2),
        "shares":        int(data.get("shares", 0)),
        "pnl":           round(float(data.get("pnl", 0)), 2),
        "pnl_pct":       round(float(data.get("pnl_pct", 0)), 2),
        "exit_reason":   data.get("exit_reason", ""),
        "confidence":    data.get("confidence", ""),
        "float_shares":  data.get("float_shares", ""),
        "position_size": round(float(data.get("position_size", 0)), 2),
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


@app.route("/api/trades")
def api_trades():
    return jsonify({"trades": _trades, "stats": _compute_stats(), "account": _account})


@app.route("/api/evening_watchlist", methods=["POST"])
def save_evening_watchlist():
    secret = request.headers.get("X-Dashboard-Secret", "")
    if secret != API_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    global _evening_watchlist
    _evening_watchlist = request.get_json(silent=True) or {}
    _evening_watchlist["saved_at"] = datetime.now(EASTERN).isoformat()
    _save_watchlist()
    picks = len(_evening_watchlist.get("top_picks", []))
    print(f"🌙 Evening watchlist saved — {picks} picks")
    return jsonify({"status": "ok", "picks": picks})


@app.route("/api/evening_watchlist", methods=["GET"])
def get_evening_watchlist():
    return jsonify(_evening_watchlist)


@app.route("/api/kev_picks", methods=["POST"])
def save_kev_picks():
    global _kev_picks
    data = request.get_json(silent=True) or {}
    transcript = (data.get("transcript") or "").strip()
    if not transcript:
        return jsonify({"error": "transcript required"}), 400
    now_et = datetime.now(EASTERN)
    _kev_picks = {
        "transcript": transcript,
        "date": now_et.strftime("%Y-%m-%d"),
        "saved_at": now_et.isoformat(),
        "saved_at_display": now_et.strftime("%I:%M %p ET"),
    }
    _save_kev_picks()
    print(f"📝 Kev's picks saved ({len(transcript)} chars)")
    return jsonify({"status": "ok", "chars": len(transcript)})


@app.route("/api/kev_picks", methods=["GET"])
def get_kev_picks():
    # Only return if saved today — don't let yesterday's picks bleed in
    today = datetime.now(EASTERN).strftime("%Y-%m-%d")
    if _kev_picks.get("date") == today:
        return jsonify(_kev_picks)
    return jsonify({})


@app.route("/dashboard")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


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
              border-radius:6px;padding:2px 8px;font-weight:600;font-size:12px;color:#e6edf3}
.conf-badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:500}
.conf-HIGH{background:#1a3a2a;color:#3fb950;border:1px solid #2d5a3d}
.conf-MEDIUM{background:#2a2a1a;color:#d29922;border:1px solid #5a4a1a}
.conf-LOW{background:#21262d;color:#8b949e;border:1px solid #30363d}
.pnl-pos{color:#3fb950;font-weight:600}
.pnl-neg{color:#f85149;font-weight:600}
.exit-tag{font-size:11px;color:#8b949e;max-width:160px;overflow:hidden;text-overflow:ellipsis}
.empty-state{text-align:center;padding:48px 24px;color:#8b949e}
.empty-state .icon{font-size:36px;margin-bottom:12px}
.empty-state p{font-size:14px}
.empty-state small{font-size:12px;display:block;margin-top:6px;color:#484f58}

/* ── No-trade days row ── */
.no-trade-row td{color:#484f58;font-style:italic}
</style>
</head>
<body>

<div class="header">
  <div class="logo">
    <div class="logo-icon">📈</div>
    <div>
      <h1>Marcos Trades Dashboard</h1>
      <sub>Powered by Claude Opus AI + Webull OpenAPI</sub>
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
          <th>Confidence</th>
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
    tbody.innerHTML = `<tr><td colspan="11"><div class="empty-state">
      <div class="icon">🤖</div>
      <p>No trades recorded yet</p>
      <small>The bot will log results here automatically after each session</small>
    </div></td></tr>`;
    return;
  }
  const rows = [...trades].reverse().map(t=>{
    const pnlCls  = t.pnl>=0?'pnl-pos':'pnl-neg';
    const confCls = 'conf-'+(t.confidence||'MEDIUM');
    const pnlSign = t.pnl>=0?'+':'';
    const pctSign = t.pnl_pct>=0?'+':'';
    const fl = t.float_shares ? String(t.float_shares).replace(/(\d)(?=(\d{3})+$)/g,'$1,') : '—';
    const sz = t.position_size ? fmt$(t.position_size) : '—';
    return `<tr>
      <td style="color:#8b949e">${t.date||'—'}</td>
      <td><span class="ticker-badge">${t.ticker||'—'}</span></td>
      <td>${t.entry?'$'+t.entry.toFixed(2):'—'}</td>
      <td>${t.exit?'$'+t.exit.toFixed(2):'—'}</td>
      <td style="color:#8b949e">${t.shares||'—'}</td>
      <td style="color:#8b949e">${sz}</td>
      <td class="${pnlCls}">${pnlSign}$${Math.abs(t.pnl).toFixed(2)}</td>
      <td class="${pnlCls}">${pctSign}${t.pnl_pct.toFixed(1)}%</td>
      <td class="exit-tag" title="${t.exit_reason||''}">${t.exit_reason||'—'}</td>
      <td><span class="conf-badge ${confCls}">${t.confidence||'—'}</span></td>
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

// Auto-refresh every 60 seconds
loadData();
setInterval(loadData, 60000);
</script>
</body>
</html>"""


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
