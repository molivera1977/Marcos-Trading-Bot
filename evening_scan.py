"""
evening_scan.py — Marcos Evening Watchlist Scanner
Runs at 7pm ET weekdays via Railway cron: 0 23 * * 1-5

1. Scans today's top movers + unusual volume stocks
2. Fetches float, news, day stats for each
3. MARCO analyzes: which are worth watching TOMORROW?
4. Posts watchlist to screener app (morning bot reads it)
5. Sends "Tonight's Watchlist" email
"""

import os, sys, time, json, pathlib
from datetime import datetime
import pytz
import requests

# ── Config ─────────────────────────────────────────────────────────────────
EASTERN            = pytz.timezone("America/New_York")
WEBULL_APP_KEY     = os.environ.get("WEBULL_APP_KEY", "")
WEBULL_APP_SECRET  = os.environ.get("WEBULL_APP_SECRET", "")
WEBULL_ACCESS_TOKEN= os.environ.get("WEBULL_ACCESS_TOKEN", "")
TRADING_HOST       = "api.webull.com"
WEBULL_TOKEN_DIR   = "/tmp/webull_token_evening"
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
RESEND_API_KEY     = os.environ.get("RESEND_API_KEY", "")
SUMMARY_EMAIL      = os.environ.get("SUMMARY_EMAIL", "molivera1977@gmail.com")
SCREENER_URL       = os.environ.get("SCREENER_URL", "").rstrip("/")
DASHBOARD_SECRET   = os.environ.get("DASHBOARD_SECRET", "marcos2026")

# ── Webull client ───────────────────────────────────────────────────────────
def _pre_populate_token():
    if not WEBULL_ACCESS_TOKEN:
        return
    try:
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
    try:
        from webull.core.client import ApiClient
        from webull.data.data_client import DataClient as WebullDataClient
        import logging
        logging.getLogger("webull").setLevel(logging.CRITICAL)
        _pre_populate_token()
        api_client = ApiClient(WEBULL_APP_KEY, WEBULL_APP_SECRET, "us",
                               token_check_duration_seconds=60,
                               token_check_interval_seconds=5)
        api_client.set_token_dir(WEBULL_TOKEN_DIR)
        api_client.add_endpoint("us", TRADING_HOST)
        return WebullDataClient(api_client)
    except Exception as e:
        print(f"⚠️  DataClient error: {e}")
        return None

# ── News fetch ──────────────────────────────────────────────────────────────
def get_news(ticker: str) -> list:
    try:
        import yfinance as yf
        news = yf.Ticker(ticker).news or []
        lines = []
        for item in news[:4]:
            title = item.get("title", "")
            ts    = item.get("providerPublishTime", 0)
            if ts:
                age_h = (time.time() - ts) / 3600
                tag   = f"{age_h:.0f}h ago" if age_h < 48 else f"{age_h//24:.0f}d ago"
            else:
                tag = "recent"
            if title:
                lines.append(f"[{tag}] {title}")
        return lines if lines else ["No recent news"]
    except Exception:
        return ["News unavailable"]

# ── Evening scan ─────────────────────────────────────────────────────────────
def scan_today_movers() -> list:
    print("🔍 Scanning today's movers...")
    data_client = _make_data_client()
    candidates = {}

    if not data_client:
        print("⚠️  No data client — cannot scan")
        return []

    # Today's top % gainers (final close-of-day rankings)
    try:
        res = data_client.screener.get_gainers_losers(
            rank_type="CHANGE_RATIO",
            category="US_STOCK",
            sort_by="CHANGE_RATIO",
            direction="DESC",
            page_size=100,
        )
        if res.status_code == 200:
            raw   = res.json()
            items = raw if isinstance(raw, list) else raw.get("data", raw.get("items", []))
            for item in (items or []):
                sym   = item.get("symbol", "")
                chg   = float(item.get("change_ratio") or 0) * 100
                price = float(item.get("price") or item.get("close") or 0)
                vol   = float(item.get("volume") or 0)
                mktcap= float(item.get("market_value") or 0)
                if not sym or price < 0.50 or price > 30 or chg < 10:
                    continue
                candidates[sym] = {
                    "symbol": sym, "change_pct": round(chg, 2),
                    "price": round(price, 2), "volume": int(vol),
                    "market_cap": mktcap, "source": "today_gainer",
                }
            print(f"   Gainers: {len(candidates)} above 10% threshold")
    except Exception as e:
        print(f"⚠️  Gainers error: {e}")

    # High relative volume — catches stocks with unusual activity even below 10% change
    try:
        res = data_client.screener.get_most_active(
            category="US_STOCK",
            rank_type="RELATIVE_VOLUME_10D",
            sort_by="RELATIVE_VOLUME_10D",
            direction="DESC",
            page_size=50,
        )
        if res.status_code == 200:
            raw   = res.json()
            items = raw if isinstance(raw, list) else raw.get("data", raw.get("items", []))
            added = 0
            for item in (items or []):
                sym     = item.get("symbol", "")
                chg     = float(item.get("change_ratio") or 0) * 100
                price   = float(item.get("price") or item.get("close") or 0)
                rel_vol = float(item.get("relative_volume_10d") or 0)
                vol     = float(item.get("volume") or 0)
                if not sym or price < 0.50 or price > 30 or rel_vol < 3:
                    continue
                if sym in candidates:
                    candidates[sym]["relative_volume"] = round(rel_vol, 1)
                elif chg >= 5:
                    candidates[sym] = {
                        "symbol": sym, "change_pct": round(chg, 2),
                        "price": round(price, 2), "volume": int(vol),
                        "market_cap": 0, "relative_volume": round(rel_vol, 1),
                        "source": "unusual_volume",
                    }
                    added += 1
            print(f"   Unusual volume adds: {added} more")
    except Exception as e:
        print(f"⚠️  Volume error: {e}")

    # Enrich with float, news, day stats via yfinance
    import yfinance as yf
    results = []
    print(f"   Checking float + news for {len(candidates)} candidates...")
    for sym, g in candidates.items():
        try:
            info     = yf.Ticker(sym).info or {}
            float_sh = info.get("floatShares") or info.get("sharesOutstanding") or 0
            float_m  = float_sh / 1_000_000
            if float_sh > 100_000_000:       # skip large float
                continue
            g["float_shares"]   = float_sh
            g["float_m"]        = round(float_m, 2) if float_sh else 0
            g["float_label"]    = f"{float_m:.1f}M" if float_sh else "N/A"
            g["short_interest"] = round((info.get("shortPercentOfFloat") or 0) * 100, 1)
            g["day_high"]       = info.get("dayHigh") or 0
            g["day_low"]        = info.get("dayLow") or 0
            g["day_open"]       = info.get("open") or 0
            g["prev_close"]     = info.get("previousClose") or 0
            g["news"]           = get_news(sym)
            results.append(g)
            time.sleep(0.4)
        except Exception:
            g["float_shares"] = 0
            g["float_label"]  = "N/A"
            g["news"]         = ["News unavailable"]
            results.append(g)

    def _score(g):
        f = g.get("float_shares") or 0
        float_m = f / 1_000_000 if f > 0 else 25
        return g["change_pct"] / max(float_m, 0.1)

    results = sorted(results, key=_score, reverse=True)[:20]
    print(f"✅ Evening scan: {len(results)} candidates after float filter")
    return results

# ── MARCO evening analysis ──────────────────────────────────────────────────
def analyze_evening(candidates: list, kev_email: str = "") -> dict | None:
    if not candidates:
        print("⚠️  No candidates to analyze")
        return None

    today = datetime.now(EASTERN).strftime("%Y-%m-%d")
    day   = datetime.now(EASTERN).strftime("%A")

    # Build candidate block
    lines = []
    for g in candidates:
        news_str = " | ".join(g.get("news", [])) if isinstance(g.get("news"), list) else str(g.get("news", ""))
        lines.append(
            f"  {g['symbol']}: +{g['change_pct']}% today | "
            f"Close ${g['price']} | Float {g['float_label']} | "
            f"Short {g.get('short_interest', 0)}% | "
            f"Open ${g.get('day_open', 0)} High ${g.get('day_high', 0)} Low ${g.get('day_low', 0)} | "
            f"Vol {g.get('volume', 0):,} | "
            f"News: {news_str}"
        )
    candidates_text = "\n".join(lines)

    kev_section = f"\nKEV'S WATCHLIST (if any):\n{kev_email}\n" if kev_email.strip() else ""

    prompt = f"""You are MARCO — a seasoned small-cap momentum trader with 15 years of experience.

It's 7pm ET on {day}, {today}. The market closed hours ago. Your job right now is NOT to trade —
it's to PREPARE. You're building tomorrow's watchlist for Marcos Olivera.

TODAY'S MOVERS (what actually moved today):
{candidates_text}
{kev_section}

YOUR EVENING JOB:

For each candidate, assess these questions:
1. CATALYST FRESHNESS — Is the driver behind today's move fresh or played out?
   Fresh = PR dropped today, FDA decision, earnings beat, halt+resume on news.
   Played out = stock has been running 3-5 days, no new catalyst, extension play only.

2. SETUP QUALITY FOR TOMORROW — Did it hold well or does it look exhausted?
   Healthy: Closed near the high, held above open, volume dried up into close (consolidating).
   Exhausted: Huge spike then sold off hard, closed near lows, gap-and-crap pattern.

3. KEY LEVEL TOMORROW — What price level matters at the open?
   Usually: today's high (breakout), VWAP (reclaim play), or day's open (failed follow-through).
   Be specific. "Watch $2.50" is useful. "Watch for momentum" is not.

4. FLOAT + SQUEEZE POTENTIAL — Small float + short interest + catalyst = squeeze.
   Flag any stock where all three align.

5. RISK — What kills this play? (Already extended, dilution risk, sector rotating out, etc.)

CRITICAL RULE: Only put a stock on tomorrow's watchlist if you genuinely believe there is a
realistic scenario where it moves another 15-30%+ tomorrow. Don't pad the list. 3 real
setups beat 10 lukewarm ones. If today was a one-day wonder with no follow-through potential,
say so and skip it.

SUB-$1 PLAYS: If a stock closed near $1 with catalyst and tiny float, it can absolutely
break out through $1 tomorrow. Don't auto-skip sub-dollar stocks.

Respond in this EXACT JSON format:
{{
  "watchlist_date": "{today}",
  "for_trading_date": "tomorrow's date",
  "market_summary": "2-3 sentences on today's overall tape and what it means for tomorrow",
  "top_picks": [
    {{
      "ticker": "SYMBOL",
      "thesis": "Why this plays tomorrow — specific and direct",
      "catalyst_fresh": true or false,
      "setup_quality": "STRONG / MODERATE / WEAK",
      "key_level": 0.00,
      "key_level_note": "What happens at this level (e.g. break above = entry, hold = base)",
      "entry_trigger": "Specific condition to enter (e.g. VWAP reclaim with volume at open)",
      "target": 0.00,
      "stop": 0.00,
      "float_label": "xM",
      "short_squeeze_risk": true or false,
      "risk_note": "Main thing that kills this play",
      "confidence": "HIGH / MEDIUM / LOW"
    }}
  ],
  "skip_list": [
    {{
      "ticker": "SYMBOL",
      "reason": "Why this is NOT on the watchlist"
    }}
  ],
  "plain_english_summary": "Text Marcos tonight. Tell him your top 1-2 picks for tomorrow, what level to watch, and what the plan is. Be direct. He needs to know what to look for at 9:30am."
}}
"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print("🧠 MARCO analyzing tonight's candidates...")
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            message = stream.get_final_message()

        raw = ""
        for block in message.content:
            if block.type == "text":
                raw = block.text.strip()
                break

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        result = json.loads(raw)
        print(f"✅ MARCO evening analysis complete — {len(result.get('top_picks', []))} picks")
        return result

    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}\nRaw (first 300): {raw[:300]}")
        return None
    except Exception as e:
        print(f"❌ Claude API error: {e}")
        return None

# ── Post watchlist to screener app ──────────────────────────────────────────
def post_watchlist(analysis: dict):
    if not SCREENER_URL:
        print("⚠️  SCREENER_URL not set — skipping dashboard post")
        return
    try:
        r = requests.post(
            f"{SCREENER_URL}/api/evening_watchlist",
            json=analysis,
            headers={"X-Dashboard-Secret": DASHBOARD_SECRET},
            timeout=10,
        )
        if r.status_code == 200:
            print(f"📊 Watchlist posted to dashboard")
        else:
            print(f"⚠️  Dashboard post failed: {r.status_code}")
    except Exception as e:
        print(f"⚠️  Dashboard post error: {e}")

# ── Send watchlist email ────────────────────────────────────────────────────
def send_watchlist_email(analysis: dict, candidates: list):
    if not RESEND_API_KEY:
        print("⚠️  No RESEND_API_KEY — skipping email")
        return

    picks    = analysis.get("top_picks", [])
    skips    = analysis.get("skip_list", [])
    summary  = analysis.get("market_summary", "")
    plain    = analysis.get("plain_english_summary", "")
    for_date = analysis.get("for_trading_date", "tomorrow")

    def conf_color(c):
        return {"HIGH": "#3fb950", "MEDIUM": "#d29922", "LOW": "#8b949e"}.get(c, "#8b949e")

    picks_html = ""
    for p in picks:
        color = conf_color(p.get("confidence", ""))
        squeeze = " 🔥 SQUEEZE CANDIDATE" if p.get("short_squeeze_risk") else ""
        picks_html += f"""
        <tr>
          <td style="padding:14px 16px;border-bottom:1px solid #21262d">
            <div style="font-size:16px;font-weight:700;color:#58a6ff">{p['ticker']}{squeeze}</div>
            <div style="font-size:12px;color:#8b949e;margin-top:2px">Float: {p.get('float_label','N/A')} | Stop: ${p.get('stop',0):.2f} → Target: ${p.get('target',0):.2f}</div>
          </td>
          <td style="padding:14px 16px;border-bottom:1px solid #21262d">
            <span style="background:#1a3a2a;color:{color};padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600">{p.get('confidence','')}</span>
          </td>
          <td style="padding:14px 16px;border-bottom:1px solid #21262d;color:#e6edf3;font-size:13px">{p.get('thesis','')}</td>
          <td style="padding:14px 16px;border-bottom:1px solid #21262d;color:#3fb950;font-weight:700;font-size:14px">${p.get('key_level',0):.2f}</td>
          <td style="padding:14px 16px;border-bottom:1px solid #21262d;color:#8b949e;font-size:12px">{p.get('entry_trigger','')}</td>
          <td style="padding:14px 16px;border-bottom:1px solid #21262d;color:#f85149;font-size:12px">{p.get('risk_note','')}</td>
        </tr>"""

    skip_html = ""
    for s in skips[:5]:
        skip_html += f'<li style="color:#8b949e;margin-bottom:4px"><b style="color:#484f58">{s["ticker"]}</b> — {s.get("reason","")}</li>'

    html = f"""
    <div style="font-family:Inter,sans-serif;background:#0d1117;color:#e6edf3;max-width:900px;margin:0 auto;border-radius:12px;overflow:hidden">
      <div style="background:#161b22;border-bottom:1px solid #21262d;padding:20px 28px;display:flex;align-items:center;gap:12px">
        <div style="font-size:28px">🌙</div>
        <div>
          <div style="font-size:18px;font-weight:700">Tonight's Watchlist</div>
          <div style="font-size:12px;color:#8b949e">MARCO's picks for {for_date} · Marcos Trading Bot</div>
        </div>
      </div>

      <div style="padding:20px 28px;background:#0e2a1a;border-bottom:1px solid #21262d">
        <div style="font-size:13px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">MARCO's Read on Today's Tape</div>
        <div style="font-size:15px;line-height:1.6">{summary}</div>
      </div>

      <div style="padding:20px 28px;background:#1a3a2a;border-bottom:1px solid #21262d">
        <div style="font-size:13px;color:#3fb950;font-weight:600;margin-bottom:6px">📲 MARCO SAYS</div>
        <div style="font-size:15px;line-height:1.6;font-style:italic">{plain}</div>
      </div>

      <div style="padding:20px 28px">
        <div style="font-size:13px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px">Tomorrow's Setups ({len(picks)} picks)</div>
        <table style="width:100%;border-collapse:collapse;background:#161b22;border-radius:10px;overflow:hidden;border:1px solid #21262d">
          <thead>
            <tr style="background:#0d1117">
              <th style="padding:10px 16px;text-align:left;font-size:11px;color:#8b949e;font-weight:500;text-transform:uppercase;letter-spacing:.4px">Ticker</th>
              <th style="padding:10px 16px;text-align:left;font-size:11px;color:#8b949e;font-weight:500;text-transform:uppercase;letter-spacing:.4px">Conf</th>
              <th style="padding:10px 16px;text-align:left;font-size:11px;color:#8b949e;font-weight:500;text-transform:uppercase;letter-spacing:.4px">Thesis</th>
              <th style="padding:10px 16px;text-align:left;font-size:11px;color:#8b949e;font-weight:500;text-transform:uppercase;letter-spacing:.4px">Watch Level</th>
              <th style="padding:10px 16px;text-align:left;font-size:11px;color:#8b949e;font-weight:500;text-transform:uppercase;letter-spacing:.4px">Entry Trigger</th>
              <th style="padding:10px 16px;text-align:left;font-size:11px;color:#8b949e;font-weight:500;text-transform:uppercase;letter-spacing:.4px">Risk</th>
            </tr>
          </thead>
          <tbody>{picks_html}</tbody>
        </table>
      </div>

      {"<div style='padding:0 28px 20px'><div style='font-size:12px;color:#484f58;margin-bottom:8px;text-transform:uppercase;letter-spacing:.4px'>Skipped (not worth watching tomorrow)</div><ul style='margin:0;padding-left:18px'>" + skip_html + "</ul></div>" if skip_html else ""}

      <div style="padding:16px 28px;background:#161b22;border-top:1px solid #21262d;font-size:11px;color:#484f58;text-align:center">
        Bot will read this watchlist at 8:45am and prioritize these picks at open.
      </div>
    </div>"""

    try:
        import resend
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from":    "MARCO <onboarding@resend.dev>",
            "to":      [SUMMARY_EMAIL],
            "subject": f"🌙 Tonight's Watchlist — {len(picks)} picks for {for_date}",
            "html":    html,
        })
        print(f"✅ Watchlist email sent to {SUMMARY_EMAIL}")
    except Exception as e:
        print(f"❌ Email error: {e}")

# ── Main ────────────────────────────────────────────────────────────────────
def main():
    now = datetime.now(EASTERN)
    print(f"\n{'='*60}")
    print(f"🌙 MARCOS EVENING SCAN")
    print(f"📅 {now.strftime('%A, %B %d, %Y at %I:%M %p ET')}")
    print(f"{'='*60}\n")

    if now.weekday() >= 5:
        print("📅 Weekend — no evening scan.")
        return

    candidates = scan_today_movers()
    if not candidates:
        print("⚠️  No candidates found — market may have been quiet today.")
        return

    analysis = analyze_evening(candidates)
    if not analysis:
        print("❌ MARCO analysis failed — no watchlist tonight.")
        return

    post_watchlist(analysis)
    send_watchlist_email(analysis, candidates)

    picks = analysis.get("top_picks", [])
    print(f"\n{'='*60}")
    print(f"🌙 EVENING SCAN COMPLETE")
    print(f"   {len(picks)} picks for tomorrow:")
    for p in picks:
        print(f"   {p['ticker']:6s} | Watch ${p.get('key_level',0):.2f} | {p.get('confidence','')} | {p.get('thesis','')[:60]}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
