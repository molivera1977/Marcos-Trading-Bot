"""
evening_scan.py — Marcos Evening Watchlist Scanner
Runs at 7pm ET weekdays via Railway cron: 0 23 * * 1-5

1. Scans today's top movers + unusual volume stocks
2. Fetches float, news, day stats for each
3. MARCO analyzes: which are worth watching TOMORROW?
4. Posts watchlist to screener app (morning bot reads it)
5. Sends "Tonight's Watchlist" email
"""

import os, sys, time, json, pathlib, imaplib, email, re, socket
from datetime import datetime, timedelta
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
EMAIL_ADDRESS      = os.environ.get("EMAIL_ADDRESS", "molivera1977@icloud.com")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "")
IMAP_SERVER        = "imap.mail.me.com"
IMAP_PORT          = 993

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

# ── Read Kev's evening email/transcript ────────────────────────────────────
def read_kev_evening_email() -> str:
    """
    Read Kev's latest watchlist email from iCloud inbox.
    Looks for emails received today or yesterday — scores by subject keywords.
    Returns the email body text, or empty string if nothing found.
    """
    if not EMAIL_APP_PASSWORD:
        print("⚠️  No EMAIL_APP_PASSWORD — cannot read Kev's email")
        return ""
    print("📧 Checking iCloud email for Kev's evening watchlist...")
    try:
        socket.setdefaulttimeout(20)
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        mail.select("inbox")

        since_date = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
        _, all_msgs = mail.search(None, f'(SINCE "{since_date}")')
        all_ids = all_msgs[0].split() if all_msgs[0] else []
        if not all_ids:
            print("⚠️  No recent emails found in iCloud")
            mail.logout()
            return ""

        today_et     = datetime.now(EASTERN).date()
        yesterday_et = today_et - timedelta(days=1)
        skip_words   = {"THE","FOR","AND","NOT","ALL","DAY","TOP","NEW","BIG","HOT",
                        "RE","AI","ET","FW","FWD","TO","IN","UP","AM","PM"}

        best_id, best_score, best_subject = None, -1, ""
        for msg_id in all_ids:
            try:
                _, hdr_data = mail.fetch(msg_id,
                    "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
                raw_h = next((p[1] for p in hdr_data if isinstance(p, tuple)), b"")
                hdr   = email.message_from_bytes(raw_h)
                subj  = hdr.get("subject", "") or ""
                date_str = hdr.get("date", "") or ""

                recency = 0
                try:
                    from email.utils import parsedate_to_datetime
                    sent_date = parsedate_to_datetime(date_str).astimezone(EASTERN).date()
                    if sent_date == today_et:
                        recency = 20
                    elif sent_date == yesterday_et:
                        recency = 10
                except Exception:
                    pass

                subj_up = subj.upper()
                score = (len(re.findall(r'\$[A-Z]{2,5}\b', subj_up)) * 5
                       + len(re.findall(r'\bWATCHLIST\b|\bPICK\b|\bSETUP\b|\bPLAY\b', subj_up)) * 3
                       + min(len([t for t in re.findall(r'\b[A-Z]{2,5}\b', subj_up)
                                  if t not in skip_words]), 10)
                       + recency)
                if score > best_score:
                    best_score, best_subject, best_id = score, subj, msg_id
            except Exception:
                pass

        if best_id is None:
            mail.logout()
            return ""

        _, body_data = mail.fetch(best_id, "(RFC822)")
        raw_b = next((p[1] for p in body_data if isinstance(p, tuple)), b"")
        msg_b = email.message_from_bytes(raw_b)
        body  = ""
        if msg_b.is_multipart():
            for part in msg_b.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    body = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else ""
                    break
        else:
            payload = msg_b.get_payload(decode=True)
            body = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload or "")

        mail.logout()
        if body:
            print(f"✅ Kev's email found (score={best_score}): {best_subject[:70]!r}")
            return f"{best_subject}\n\n{body}"
        return ""
    except Exception as e:
        print(f"⚠️  Email read error: {e}")
        return ""

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

# ── MARCO independent analysis (no Kev input) ──────────────────────────────
def analyze_evening(candidates: list) -> dict | None:
    """
    MARCO analyzes today's movers with ZERO knowledge of Kev's picks.
    This is the independent test — we compare his output to Kev afterward.
    """
    if not candidates:
        print("⚠️  No candidates to analyze")
        return None

    now   = datetime.now(EASTERN)
    today = now.strftime("%Y-%m-%d")
    day   = now.strftime("%A")

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

    prompt = f"""You are MARCO — a seasoned small-cap momentum trader with 15 years of experience.

It's 9:30pm ET on {day}, {today}. Market closed hours ago. Your job: build tomorrow's watchlist
for Marcos Olivera using ONLY the market data below. No outside input. Your own read.

TODAY'S MOVERS:
{candidates_text}

For each candidate assess:
1. CATALYST FRESHNESS — Fresh (PR today, FDA, earnings) or played out (been running 3-5 days)?
2. SETUP QUALITY — Healthy (closed near high, volume dried up) or exhausted (gap-and-crap, closed at lows)?
3. KEY LEVEL TOMORROW — Be specific. "Watch $2.50" not "watch for momentum."
4. SQUEEZE POTENTIAL — Tiny float + short interest + fresh catalyst = flag it.
5. WHAT KILLS IT — Be honest about the risk.

Only put a stock on the list if you genuinely see a path to +15-30% tomorrow.
3 real picks beat 10 lukewarm ones. Sub-$1 stocks with tiny floats and fresh catalysts are valid.

Respond in EXACT JSON:
{{
  "watchlist_date": "{today}",
  "for_trading_date": "{(now + timedelta(days=1)).strftime('%Y-%m-%d')}",
  "market_summary": "2-3 sentences on today's tape and what it means for tomorrow",
  "top_picks": [
    {{
      "ticker": "SYMBOL",
      "thesis": "Why this plays tomorrow",
      "catalyst_fresh": true or false,
      "setup_quality": "STRONG / MODERATE / WEAK",
      "key_level": 0.00,
      "key_level_note": "What happens at this level",
      "entry_trigger": "Specific entry condition",
      "target": 0.00,
      "stop": 0.00,
      "float_label": "xM",
      "short_squeeze_risk": true or false,
      "risk_note": "Main thing that kills this play",
      "confidence": "HIGH / MEDIUM / LOW"
    }}
  ],
  "skip_list": [
    {{"ticker": "SYMBOL", "reason": "Why skipped"}}
  ],
  "plain_english_summary": "MARCO's own read — top 1-2 picks, levels, plan. Direct and specific."
}}
"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print("🧠 MARCO building independent watchlist (no Kev input)...")
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
        print(f"✅ MARCO independent analysis: {len(result.get('top_picks', []))} picks")
        return result

    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}\nRaw (first 300): {raw[:300]}")
        return None
    except Exception as e:
        print(f"❌ Claude API error: {e}")
        return None


# ── Extract Kev's tickers from his email ───────────────────────────────────
def extract_kev_tickers(kev_email: str) -> list:
    """Pull ticker symbols out of Kev's email/transcript."""
    if not kev_email:
        return []
    skip = {"THE","FOR","AND","NOT","ALL","DAY","TOP","NEW","BIG","HOT","PDT",
            "RE","AI","ET","AM","PM","VWAP","MACD","HIGH","HOLD","BUY","SELL"}
    text = kev_email.upper()
    # $TICKER format first (most reliable)
    tickers = re.findall(r'\$([A-Z]{2,5})\b', text)
    if not tickers:
        # bare caps fallback
        tickers = [t for t in re.findall(r'\b[A-Z]{2,5}\b', text) if t not in skip]
    # deduplicate preserving order
    seen, result = set(), []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result[:10]


# ── Compare MARCO vs Kev ────────────────────────────────────────────────────
def compare_picks(marco_analysis: dict, kev_tickers: list) -> dict:
    """
    Side-by-side comparison: where do MARCO and Kev agree?
    Agreement = highest conviction for tomorrow.
    """
    marco_tickers = [p["ticker"] for p in marco_analysis.get("top_picks", [])]
    overlap   = [t for t in marco_tickers if t in kev_tickers]
    marco_only = [t for t in marco_tickers if t not in kev_tickers]
    kev_only   = [t for t in kev_tickers  if t not in marco_tickers]

    print(f"\n📊 CALIBRATION REPORT")
    print(f"   MARCO picked:  {marco_tickers}")
    print(f"   Kev picked:    {kev_tickers}")
    print(f"   ✅ Overlap:    {overlap}  ← highest conviction")
    print(f"   🔵 MARCO only: {marco_only}")
    print(f"   🟡 Kev only:   {kev_only}  ← MARCO missed these")

    return {
        "marco_picks":  marco_tickers,
        "kev_picks":    kev_tickers,
        "overlap":      overlap,
        "marco_only":   marco_only,
        "kev_only":     kev_only,
        "score": f"{len(overlap)}/{len(kev_tickers)} of Kev's picks matched" if kev_tickers else "No Kev picks to compare",
    }

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

# ── Calibration HTML block ─────────────────────────────────────────────────
def _calibration_html(comparison: dict, kev_email: str) -> str:
    if not comparison.get("kev_picks") and not comparison.get("marco_picks"):
        return ""

    marco_picks = comparison.get("marco_picks", [])
    kev_picks   = comparison.get("kev_picks", [])
    overlap     = comparison.get("overlap", [])
    marco_only  = comparison.get("marco_only", [])
    kev_only    = comparison.get("kev_only", [])
    score       = comparison.get("score", "")

    def badge(ticker, bg, fg):
        return (f'<span style="display:inline-block;margin:3px;padding:4px 12px;'
                f'background:{bg};color:{fg};border-radius:20px;font-size:13px;font-weight:700">'
                f'{ticker}</span>')

    overlap_badges  = "".join(badge(t, "#1a3a2a", "#3fb950") for t in overlap)  or "<em style='color:#484f58'>None</em>"
    m_only_badges   = "".join(badge(t, "#0d2a4a", "#58a6ff") for t in marco_only) or "<em style='color:#484f58'>None</em>"
    kev_only_badges = "".join(badge(t, "#3a2a0a", "#d29922") for t in kev_only)   or "<em style='color:#484f58'>None</em>"

    kev_snippet = ""
    if kev_email:
        first_400 = kev_email[:400].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        kev_snippet = f"""
      <div style="margin-top:16px;padding:12px;background:#0d1117;border-radius:8px;border:1px solid #21262d">
        <div style="font-size:11px;color:#484f58;text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px">Kev's Email Preview</div>
        <div style="font-size:12px;color:#8b949e;line-height:1.5">{first_400}…</div>
      </div>"""

    return f"""
      <div style="padding:20px 28px;border-top:1px solid #21262d">
        <div style="font-size:13px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:16px">
          📊 CALIBRATION — MARCO vs Kev · {score}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
          <div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px">
            <div style="font-size:11px;color:#58a6ff;text-transform:uppercase;letter-spacing:.4px;margin-bottom:8px">🔵 MARCO Picked</div>
            <div>{"".join(badge(t, "#0d2a4a", "#58a6ff") for t in marco_picks) or "<em style='color:#484f58'>None</em>"}</div>
          </div>
          <div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px">
            <div style="font-size:11px;color:#d29922;text-transform:uppercase;letter-spacing:.4px;margin-bottom:8px">🟡 Kev Picked</div>
            <div>{"".join(badge(t, "#3a2a0a", "#d29922") for t in kev_picks) or "<em style='color:#484f58'>None</em>"}</div>
          </div>
        </div>
        <div style="background:#0e2a1a;border:1px solid #1a3a2a;border-radius:8px;padding:14px;margin-bottom:12px">
          <div style="font-size:11px;color:#3fb950;text-transform:uppercase;letter-spacing:.4px;margin-bottom:8px">✅ OVERLAP — Highest Conviction</div>
          <div>{overlap_badges}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px">
            <div style="font-size:11px;color:#484f58;text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px">MARCO only (Kev skipped)</div>
            <div>{m_only_badges}</div>
          </div>
          <div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px">
            <div style="font-size:11px;color:#f85149;text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px">🔴 MARCO missed (Kev found)</div>
            <div>{kev_only_badges}</div>
          </div>
        </div>
        {kev_snippet}
      </div>"""


# ── Send watchlist email ────────────────────────────────────────────────────
def send_watchlist_email(analysis: dict, comparison: dict, kev_email: str):
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

      {_calibration_html(comparison, kev_email)}

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

    # Step 1: Scan market data independently
    candidates = scan_today_movers()
    if not candidates:
        print("⚠️  No candidates found — market may have been quiet today.")
        return

    # Step 2: MARCO analyzes with ZERO Kev input — pure independent read
    analysis = analyze_evening(candidates)
    if not analysis:
        print("❌ MARCO analysis failed — no watchlist tonight.")
        return

    # Step 3: NOW read Kev's email (after MARCO has committed to his picks)
    kev_email = read_kev_evening_email()
    if kev_email:
        print(f"✅ Kev's watchlist loaded ({len(kev_email)} chars)")
    else:
        print("⚠️  No Kev email found tonight — calibration skipped")

    # Step 4: Compare and produce calibration report
    kev_tickers = extract_kev_tickers(kev_email)
    comparison  = compare_picks(analysis, kev_tickers)

    # Step 5: Post and email
    post_watchlist(analysis)
    send_watchlist_email(analysis, comparison, kev_email)

    picks = analysis.get("top_picks", [])
    print(f"\n{'='*60}")
    print(f"🌙 EVENING SCAN COMPLETE")
    print(f"   MARCO's {len(picks)} picks for tomorrow:")
    for p in picks:
        overlap_tag = " ✅ OVERLAP WITH KEV" if p["ticker"] in comparison.get("overlap", []) else ""
        print(f"   {p['ticker']:6s} | Watch ${p.get('key_level',0):.2f} | {p.get('confidence','')} | {p.get('thesis','')[:60]}{overlap_tag}")
    if comparison.get("kev_only"):
        print(f"\n   🟡 Kev picked but MARCO missed: {comparison['kev_only']}")
    print(f"   Calibration: {comparison.get('score','')}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
