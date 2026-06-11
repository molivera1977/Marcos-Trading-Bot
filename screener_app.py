"""
Marcos Scanner — Pre-market small-float gapper screener
Runs as a separate Railway web service alongside the trading bot.
Visit the deployed URL any morning to see live pre-market movers.
"""

import os
import time
import json
from datetime import datetime
from flask import Flask, jsonify, render_template_string
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

app = Flask(__name__)

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
    1. Webull screener → top pre-market gainers + unusual relative volume
    2. Filter: price $1–$30, gap >8%, dedup
    3. yfinance float check → drop anything >50M shares
    4. Score by gap% / float_millions, return top 15
    """
    data_client = _make_data_client()
    candidates = {}
    errors = []

    if data_client:
        # Pre-market top gainers
        try:
            res = data_client.screener.get_gainers_losers(
                rank_type="PRE_MARKET",
                category="US_STOCK",
                sort_by="CHANGE_RATIO",
                direction="DESC",
                page_size=40,
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
                    if not sym or price < 1 or price > 30 or chg < 8:
                        continue
                    candidates[sym] = {
                        "symbol": sym, "change_pct": round(chg, 2),
                        "price": round(price, 2), "market_cap": mktcap,
                        "premarket_volume": int(vol), "relative_volume": None,
                        "float_shares": 0, "float_label": "—", "source": "Pre-mkt gainer",
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
                page_size=40,
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
                    if not sym or price < 1 or price > 30 or rel_vol < 3:
                        continue
                    if sym in candidates:
                        candidates[sym]["relative_volume"] = round(rel_vol, 1)
                    elif chg >= 5:
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
      <sub>Pre-market small-float gappers</sub>
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
    <span class="section-title">Small-float pre-market movers</span>
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

// Auto-refresh every 5 minutes during market hours (6am–noon ET is pre-market/open)
setInterval(function(){
  var h=new Date().getHours();
  if(h>=6&&h<13){runScan();}
},5*60*1000);
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
    return jsonify({
        "results": results,
        "errors": errors,
        "updated": datetime.now(EASTERN).isoformat(),
        "count": len(results),
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now(EASTERN).isoformat()})


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
