"""
╔══════════════════════════════════════════════════════════════╗
║           MARCOS TRADING BOT — Powered by Claude AI          ║
║           Built for Kev's Momentum Watchlist System          ║
║           Runs daily 8:45am ET on Railway.app                ║
╚══════════════════════════════════════════════════════════════╝

HOW IT WORKS:
1. Every weekday at 8:45am ET this script wakes up automatically
2. Reads your Gmail (marcostrades2026@gmail.com) for Kev's tickers
3. Pulls live pre-market data from Webull API
4. Sends everything to Claude AI for analysis
5. Claude picks the best setup and sets entry/target/stop-loss
6. Waits for VWAP reclaim after market open (9:30am) before entering
7. Monitors with trailing stop + partial exits until 11:00am
8. Emails you a full summary at molivera1977@gmail.com

SETUP INSTRUCTIONS:
- Set the following environment variables in Railway.app:
  WEBULL_APP_KEY        = your Webull App Key
  WEBULL_APP_SECRET     = your Webull App Secret
  WEBULL_APP_ID         = 961252838594318336
  WEBULL_ACCOUNT_ID     = your Webull account ID
  GMAIL_ADDRESS         = marcostrades2026@gmail.com
  GMAIL_APP_PASSWORD    = your Gmail app password
  ANTHROPIC_API_KEY     = your Claude API key
  SUMMARY_EMAIL         = molivera1977@gmail.com
"""

import os
import re
import imaplib
import email
import smtplib
import json
import time
import hmac
import hashlib
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz

# ============================================================
# CONFIGURATION — All values come from Railway environment vars
# ============================================================

WEBULL_APP_KEY    = os.environ.get("WEBULL_APP_KEY")
WEBULL_APP_SECRET = os.environ.get("WEBULL_APP_SECRET")
WEBULL_APP_ID     = os.environ.get("WEBULL_APP_ID", "961252838594318336")
WEBULL_ACCOUNT_ID = os.environ.get("WEBULL_ACCOUNT_ID")
GMAIL_ADDRESS     = os.environ.get("GMAIL_ADDRESS", "marcostrades2026@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
SUMMARY_EMAIL     = os.environ.get("SUMMARY_EMAIL", "molivera1977@gmail.com")

# Trading rules
MAX_POSITION_SIZE    = 0.70   # Max 70% of account on single trade
STOP_LOSS_PCT        = 0.07   # 7% initial stop loss
TARGET_PCT           = 0.20   # 20% full profit target
PARTIAL_EXIT_PCT     = 0.15   # Sell half position at 15% gain
BREAKEVEN_TRIGGER    = 0.10   # Move stop to breakeven at 10% gain
TRAIL_PCT            = 0.05   # Trail 5% below highest price after partial exit
VWAP_ENTRY_TIMEOUT   = 10     # Stop looking for VWAP entry after 10am ET
TRADE_WINDOW_END_HOUR = 11    # Force close all positions by 11am ET
MONITOR_INTERVAL     = 30     # Check price every 30 seconds
EASTERN = pytz.timezone("America/New_York")

# ============================================================
# STEP 1 — READ GMAIL FOR KEV'S TICKERS
# ============================================================

def read_todays_tickers():
    """
    Connects to marcostrades2026@gmail.com and reads the most
    recent email for ticker symbols and trading notes.
    You send this email each night after watching Kev's TikTok.
    Format: Subject line = ticker symbols, body = full transcript.
    """
    print("📧 Checking Gmail for tonight's watchlist...")

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        since_date = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
        _, messages = mail.search(None, f'(SINCE "{since_date}")')

        if not messages[0]:
            print("⚠️  No recent emails found in watchlist inbox.")
            return None, None

        latest = messages[0].split()[-1]
        _, msg_data = mail.fetch(latest, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        subject = msg["subject"] or ""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = msg.get_payload(decode=True).decode()

        full_content = f"Subject: {subject}\n\nBody: {body}"
        print(f"✅ Found watchlist email: {subject}")
        mail.logout()
        return subject, full_content

    except Exception as e:
        print(f"❌ Gmail error: {e}")
        return None, None

# ============================================================
# STEP 2 — WEBULL API HELPERS
# ============================================================

def get_webull_headers(method, path, body=""):
    """Generate authenticated headers for Webull API calls."""
    timestamp = str(int(time.time() * 1000))
    sign_str = f"{method}\n{path}\n{body}\n{timestamp}"
    signature = hmac.new(
        WEBULL_APP_SECRET.encode(),
        sign_str.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "Content-Type": "application/json",
        "App-Key": WEBULL_APP_KEY,
        "Timestamp": timestamp,
        "Sign": signature,
        "App-Id": WEBULL_APP_ID,
    }

def get_premarket_data(ticker):
    """Fetches live pre-market price, volume, and basic stats."""
    print(f"📊 Fetching pre-market data for {ticker}...")

    try:
        path = "/quotes/ticker/getTickerRealTime"
        params = {"symbol": ticker, "regionId": 6}
        url = f"https://openapi.webull.com{path}"
        headers = get_webull_headers("GET", path)
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()

        if data and "data" in data:
            d = data["data"]
            return {
                "ticker": ticker,
                "premarket_price": d.get("preMarketPrice", "N/A"),
                "premarket_change_pct": d.get("preMarketChangeRatio", "N/A"),
                "premarket_volume": d.get("preMarketVolume", "N/A"),
                "previous_close": d.get("preClose", "N/A"),
                "avg_volume": d.get("avgVol10D", "N/A"),
                "float_shares": d.get("outstandingShares", "N/A"),
                "market_cap": d.get("marketValue", "N/A"),
            }
    except Exception as e:
        print(f"⚠️  Webull data error for {ticker}: {e}")

    return {
        "ticker": ticker,
        "premarket_price": "Unable to fetch",
        "premarket_change_pct": "N/A",
        "premarket_volume": "N/A",
        "previous_close": "N/A",
        "avg_volume": "N/A",
        "float_shares": "N/A",
        "market_cap": "N/A",
    }

def get_account_balance():
    """Gets your current Webull account cash balance."""
    try:
        path = f"/paper/trading/v2/account/{WEBULL_ACCOUNT_ID}/positions"
        url = f"https://openapi.webull.com{path}"
        headers = get_webull_headers("GET", path)
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        if data and "data" in data:
            return float(data["data"].get("cashBalance", 100.0))
    except Exception as e:
        print(f"⚠️  Balance fetch error: {e}")

    return 100.0

def get_current_price(ticker):
    """Gets the current real-time price of a ticker."""
    try:
        path = "/quotes/ticker/getTickerRealTime"
        params = {"symbol": ticker, "regionId": 6}
        url = f"https://openapi.webull.com{path}"
        headers = get_webull_headers("GET", path)
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()

        if data and "data" in data:
            return float(data["data"].get("close", 0))
    except:
        pass
    return 0

def get_intraday_bars(ticker, count=30):
    """Gets 1-minute intraday bars for VWAP calculation."""
    try:
        path = "/quotes/ticker/getTickerChart"
        params = {"symbol": ticker, "type": "m1", "count": count, "regionId": 6}
        url = f"https://openapi.webull.com{path}"
        headers = get_webull_headers("GET", path)
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()

        if data and "data" in data:
            return data["data"]
    except Exception as e:
        print(f"⚠️  Intraday bars error for {ticker}: {e}")
    return []

def calculate_vwap(bars):
    """Calculates VWAP from 1-minute bars: sum(typical_price * volume) / sum(volume)."""
    total_pv = 0
    total_vol = 0
    for bar in bars:
        high  = float(bar.get("high", 0))
        low   = float(bar.get("low", 0))
        close = float(bar.get("close", 0))
        vol   = float(bar.get("volume", 0))
        typical = (high + low + close) / 3
        total_pv  += typical * vol
        total_vol += vol
    return total_pv / total_vol if total_vol > 0 else 0

# ============================================================
# STEP 3 — CLAUDE AI ANALYZES THE SETUPS
# ============================================================

def analyze_with_claude(email_content, market_data_list, account_balance):
    """
    Sends Kev's watchlist + live market data to Claude Opus AI.
    Claude applies Kev's exact trading rules and returns a GO/NO-GO
    decision with entry price, target, stop-loss, and reasoning.
    """
    print("🧠 Sending data to Claude Opus AI for analysis...")

    market_data_text = "\n".join([
        f"""
        Ticker: {d['ticker']}
        Pre-market Price: ${d['premarket_price']}
        Pre-market Change: {d['premarket_change_pct']}%
        Pre-market Volume: {d['premarket_volume']}
        Previous Close: ${d['previous_close']}
        10-Day Avg Volume: {d['avg_volume']}
        Market Cap: ${d['market_cap']}
        """ for d in market_data_list
    ])

    prompt = f"""
You are an AI trading assistant for Marcos Olivera, a retail trader
using Kev's Momentum trading system (TradeMomentum.org).

Today's date: {datetime.now(EASTERN).strftime("%A, %B %d, %Y")}
Account balance: ${account_balance:.2f}
Market open: 9:30am ET
Entry strategy: Wait for VWAP reclaim after open (not a blind market order)
Trading window: 9:30am - 10:00am ET for entry, hold until 11:00am max

KEV'S WATCHLIST EMAIL/TRANSCRIPT FOR TODAY:
{email_content}

LIVE PRE-MARKET DATA FROM WEBULL:
{market_data_text}

YOUR JOB:
1. Read Kev's exact setup rules for each ticker from his transcript
2. Cross-reference with the live pre-market data
3. For each ticker decide: GO or NO-GO based on Kev's rules
4. For GO trades: set exact entry price (expected VWAP level), profit target, and stop-loss
5. Pick the BEST single trade to execute (max 1 trade)
6. Never risk more than 70% of account on one position
7. Always honor Kev's rules exactly — if he says NO BREAK = NO TRADE, honor that
8. Flag any major risks (earnings, halts, offerings, T12 halts)

TRADING RULES:
- Entry: Only enter on confirmed VWAP reclaim with volume (bot waits for this automatically)
- Stop loss: 7% below actual entry price
- Partial exit: Sell half at 15% gain, trail remaining with 5% trailing stop
- Full target: 20% above entry
- Exit by: 11:00am ET no matter what
- If VWAP never reclaimed by 10:00am: hold cash, no trade

Respond in this EXACT JSON format:
{{
  "analysis_date": "YYYY-MM-DD",
  "market_summary": "2-3 sentence overview of today's setup",
  "tickers": [
    {{
      "ticker": "SYMBOL",
      "verdict": "GO" or "NO-GO",
      "reason": "Plain English explanation of why",
      "setup_confirmed": true or false,
      "entry_price": 0.00,
      "target_price": 0.00,
      "stop_loss": 0.00,
      "position_size_dollars": 0.00,
      "vwap_level": 0.00,
      "risk_flags": ["list any risks"],
      "kev_rule_check": "Did pre-market confirm Kev's exact rule? Yes/No and why"
    }}
  ],
  "recommended_trade": {{
    "ticker": "BEST TICKER or NONE",
    "action": "BUY" or "HOLD CASH",
    "entry_price": 0.00,
    "target_price": 0.00,
    "stop_loss": 0.00,
    "position_size_dollars": 0.00,
    "shares_to_buy": 0,
    "confidence": "HIGH/MEDIUM/LOW",
    "vwap_level": 0.00,
    "execute_at": "On VWAP reclaim after 9:30am open" or "NO TRADE TODAY"
  }},
  "plain_english_summary": "Write this like you're texting Marcos at 8:55am. Tell him exactly what to expect today, what the bot is doing, and why. Keep it friendly and clear."
}}
"""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-opus-4-8",
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )

        result = response.json()
        raw_text = result["content"][0]["text"]

        clean = raw_text.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()

        analysis = json.loads(clean)
        print("✅ Claude Opus analysis complete!")
        return analysis

    except Exception as e:
        print(f"❌ Claude API error: {e}")
        return None

# ============================================================
# STEP 4 — WAIT FOR VWAP ENTRY (responsive, not time-based)
# ============================================================

def wait_for_vwap_entry(ticker):
    """
    After market open (9:30am ET), watches price vs VWAP every 30 seconds.
    Enters when price reclaims VWAP with volume confirmation.
    Gives up if no reclaim by 10:00am ET — holds cash instead.
    Returns (entry_price, vwap) on success, or (None, None) on timeout.
    """
    print(f"\n⏳ Waiting for {ticker} to reclaim VWAP after open...")

    while True:
        now = datetime.now(EASTERN)

        # Timeout — don't chase after 10am
        if now.hour >= VWAP_ENTRY_TIMEOUT:
            print(f"⏰ {ticker} never reclaimed VWAP by 10am. Holding cash.")
            return None, None

        # Wait for regular market open at 9:30am
        if now.hour < 9 or (now.hour == 9 and now.minute < 30):
            mins_left = (9 * 60 + 30) - (now.hour * 60 + now.minute)
            print(f"⏳ Market opens in ~{mins_left} min...")
            time.sleep(30)
            continue

        # Fetch intraday bars and calculate VWAP
        bars = get_intraday_bars(ticker)
        current_price = get_current_price(ticker)

        if not bars or current_price <= 0:
            time.sleep(MONITOR_INTERVAL)
            continue

        vwap = calculate_vwap(bars)
        if vwap <= 0:
            time.sleep(MONITOR_INTERVAL)
            continue

        pct_vs_vwap = ((current_price - vwap) / vwap) * 100
        print(f"📊 {ticker}: ${current_price:.2f} | VWAP: ${vwap:.2f} ({pct_vs_vwap:+.1f}% vs VWAP)")

        # VWAP reclaim: price is above VWAP with reasonable volume
        if current_price > vwap:
            last_vol = float(bars[-1].get("volume", 0)) if bars else 0
            avg_vol  = sum(float(b.get("volume", 0)) for b in bars) / len(bars) if bars else 0

            if last_vol >= avg_vol * 0.75:
                print(f"✅ VWAP reclaim confirmed! ${current_price:.2f} above VWAP ${vwap:.2f} with volume")
                return current_price, vwap
            else:
                print(f"⚠️  Price above VWAP but volume weak ({last_vol:.0f} vs avg {avg_vol:.0f}). Waiting...")

        time.sleep(MONITOR_INTERVAL)

# ============================================================
# STEP 5 — EXECUTE TRADE VIA WEBULL
# ============================================================

def execute_trade(ticker, shares, entry_price, stop_loss, target):
    """Places a market buy order and immediately sets a stop-loss order."""
    print(f"🚀 Executing trade: BUY {shares} shares of {ticker}...")

    try:
        path = f"/trading/v1/account/{WEBULL_ACCOUNT_ID}/order"
        url  = f"https://openapi.webull.com{path}"

        order_body = json.dumps({
            "symbol": ticker,
            "action": "BUY",
            "orderType": "MKT",
            "quantity": shares,
            "timeInForce": "DAY",
            "outsideRegularTradingHour": False
        })

        headers  = get_webull_headers("POST", path, order_body)
        response = requests.post(url, headers=headers, data=order_body, timeout=10)
        order_data = response.json()

        if order_data.get("success"):
            order_id = order_data["data"]["orderId"]
            print(f"✅ Buy order placed! Order ID: {order_id}")

            time.sleep(2)
            stop_body = json.dumps({
                "symbol": ticker,
                "action": "SELL",
                "orderType": "STP",
                "quantity": shares,
                "auxPrice": stop_loss,
                "timeInForce": "DAY",
                "outsideRegularTradingHour": False
            })

            stop_headers = get_webull_headers("POST", path, stop_body)
            requests.post(url, headers=stop_headers, data=stop_body, timeout=10)
            print(f"🛡️  Stop-loss set at ${stop_loss:.2f}")

            return order_id
        else:
            print(f"❌ Order failed: {order_data}")
            return None

    except Exception as e:
        print(f"❌ Trade execution error: {e}")
        return None

def close_position(ticker, shares):
    """Sells shares of a position at market price."""
    print(f"🔒 Closing: SELL {shares} shares of {ticker}...")

    try:
        path = f"/trading/v1/account/{WEBULL_ACCOUNT_ID}/order"
        url  = f"https://openapi.webull.com{path}"

        order_body = json.dumps({
            "symbol": ticker,
            "action": "SELL",
            "orderType": "MKT",
            "quantity": shares,
            "timeInForce": "DAY",
            "outsideRegularTradingHour": False
        })

        headers  = get_webull_headers("POST", path, order_body)
        response = requests.post(url, headers=headers, data=order_body, timeout=10)
        data = response.json()

        if data.get("success"):
            print(f"✅ Position closed successfully!")
            return True
    except Exception as e:
        print(f"❌ Close position error: {e}")

    return False

# ============================================================
# STEP 6 — MONITOR WITH TRAILING STOP + PARTIAL EXITS
# ============================================================

def monitor_trade(ticker, total_shares, entry_price, target_price, stop_loss):
    """
    Watches the trade every 30 seconds with:
    - Breakeven stop at +10%
    - Partial exit (sell half) at +15%
    - 5% trailing stop on remaining shares after partial exit
    - Full target exit at +20%
    - Hard close at 11am ET no matter what
    """
    print(f"\n👀 Monitoring {ticker}")
    print(f"   Entry: ${entry_price:.2f} | Target: ${target_price:.2f} | Stop: ${stop_loss:.2f}")

    current_stop    = stop_loss
    highest_price   = entry_price
    remaining_shares = total_shares
    partial_taken   = False
    partial_price   = 0.0

    result = {
        "exit_price": entry_price,
        "exit_reason": "Unknown",
        "profit_loss": 0,
        "profit_loss_pct": 0
    }

    while True:
        now = datetime.now(EASTERN)

        # ── Hard close at 11am ──────────────────────────────────
        if now.hour >= TRADE_WINDOW_END_HOUR:
            print("⏰ 11:00am — Closing all positions for the day")
            current_price = get_current_price(ticker)
            if remaining_shares > 0:
                close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "11am time stop"
            break

        current_price = get_current_price(ticker)
        if current_price <= 0:
            time.sleep(MONITOR_INTERVAL)
            continue

        profit_pct = ((current_price - entry_price) / entry_price) * 100

        # Track highest price for trailing stop
        if current_price > highest_price:
            highest_price = current_price

        # ── Trailing stop logic ──────────────────────────────────
        if not partial_taken:
            # Move stop to breakeven at +10%
            if profit_pct >= BREAKEVEN_TRIGGER * 100 and current_stop < entry_price:
                current_stop = entry_price
                print(f"🔒 Stop moved to breakeven: ${current_stop:.2f}")
        else:
            # Trail 5% below highest after partial exit
            trail_stop = highest_price * (1 - TRAIL_PCT)
            if trail_stop > current_stop:
                current_stop = trail_stop
                print(f"📈 Trailing stop updated: ${current_stop:.2f}")

        print(f"💰 {ticker}: ${current_price:.2f} ({profit_pct:+.1f}%) | Stop: ${current_stop:.2f} | Shares: {remaining_shares}")

        # ── Partial exit at +15% ─────────────────────────────────
        if not partial_taken and profit_pct >= PARTIAL_EXIT_PCT * 100:
            half = round(remaining_shares / 2, 4)
            print(f"💰 PARTIAL EXIT: Selling {half} shares at ${current_price:.2f} (+{profit_pct:.1f}%)")
            close_position(ticker, half)
            partial_price    = current_price
            partial_taken    = True
            remaining_shares = round(remaining_shares - half, 4)
            current_stop     = highest_price * (1 - TRAIL_PCT)
            print(f"📈 Trailing stop set at ${current_stop:.2f} — letting rest run")

        # ── Full target hit ──────────────────────────────────────
        if current_price >= target_price and remaining_shares > 0:
            print(f"🎯 TARGET HIT! Selling {remaining_shares} shares at ${current_price:.2f}")
            close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "Target hit ✅"
            remaining_shares = 0
            break

        # ── Stop loss hit ────────────────────────────────────────
        if current_price <= current_stop and remaining_shares > 0:
            label = "Trailing stop triggered 📉" if partial_taken else "Stop loss triggered 🛑"
            print(f"🛑 {label}! Selling {remaining_shares} shares at ${current_price:.2f}")
            close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = label
            remaining_shares = 0
            break

        time.sleep(MONITOR_INTERVAL)

    # ── Blended P&L calculation ──────────────────────────────────
    if partial_taken:
        half     = total_shares / 2
        rest     = total_shares - half
        pnl      = (partial_price - entry_price) * half + (result["exit_price"] - entry_price) * rest
    else:
        pnl = (result["exit_price"] - entry_price) * total_shares

    result["profit_loss"]     = pnl
    result["profit_loss_pct"] = ((result["exit_price"] - entry_price) / entry_price) * 100
    return result

# ============================================================
# STEP 7 — EMAIL SUMMARY TO MARCOS
# ============================================================

def send_summary_email(analysis, trade_result=None, account_balance=100.0):
    """Sends a plain-English summary email after the trading session ends."""
    print(f"📨 Sending summary email to {SUMMARY_EMAIL}...")

    today = datetime.now(EASTERN).strftime("%A, %B %d, %Y")

    if trade_result and analysis:
        recommended = analysis.get("recommended_trade", {})
        ticker      = recommended.get("ticker", "N/A")
        pnl         = trade_result.get("profit_loss", 0)
        pnl_pct     = trade_result.get("profit_loss_pct", 0)
        exit_reason = trade_result.get("exit_reason", "N/A")
        exit_price  = trade_result.get("exit_price", 0)

        emoji       = "✅" if pnl > 0 else "🔴"
        result_line = f"{emoji} {ticker}: {pnl_pct:+.1f}% (${pnl:+.2f})"
        subject     = f"Trading Bot Summary — {today} | {result_line}"

        body = f"""
Good morning Marcos! Here's your trading summary for {today}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRADE RESULT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{result_line}
Exit reason: {exit_reason}
Exit price: ${exit_price:.2f}
New account balance: ~${account_balance + pnl:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLAUDE'S ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{analysis.get('plain_english_summary', 'No summary available.')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALL TICKERS REVIEWED TODAY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        for t in analysis.get("tickers", []):
            verdict_emoji = "✅" if t["verdict"] == "GO" else "❌"
            body += f"""
{verdict_emoji} {t['ticker']} — {t['verdict']}
   Reason: {t['reason']}
   Kev's Rule Check: {t['kev_rule_check']}
"""
    else:
        subject      = f"Trading Bot Summary — {today} | 💤 No Trade Today"
        plain_summary = analysis.get("plain_english_summary", "") if analysis else "No watchlist email found in inbox."
        body = f"""
Good morning Marcos! Here's your trading summary for {today}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NO TRADE TAKEN TODAY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cash preserved: ${account_balance:.2f}

{plain_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REMINDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Send tonight's tickers to: marcostrades2026@gmail.com
Paste Kev's TikTok transcript in the body.
The bot reads it at 8:45am tomorrow.
"""

    body += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Marcos Trading Bot | Powered by Claude Opus AI
Running on Railway.app | Webull account
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    try:
        msg = MIMEMultipart()
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = SUMMARY_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        print(f"✅ Summary email sent to {SUMMARY_EMAIL}!")

    except Exception as e:
        print(f"❌ Email send error: {e}")

# ============================================================
# MAIN — THE BRAIN THAT RUNS EVERYTHING
# ============================================================

def main():
    now = datetime.now(EASTERN)
    print(f"\n{'='*60}")
    print(f"🤖 MARCOS TRADING BOT STARTING UP")
    print(f"📅 {now.strftime('%A, %B %d, %Y at %I:%M %p ET')}")
    print(f"{'='*60}\n")

    if now.weekday() >= 5:
        print("📅 Weekend — markets closed. Bot going back to sleep.")
        return

    # ── Step 1: Read Gmail for Kev's tickers ──────────────────
    subject, email_content = read_todays_tickers()

    if not email_content:
        print("⚠️  No watchlist found. Sending reminder email...")
        send_summary_email(None, None)
        return

    # ── Step 2: Extract tickers from subject line ──────────────
    skip_words = {"THE", "FOR", "AND", "NOT", "ALL", "DAY", "TOP",
                  "NEW", "BIG", "HOT", "PDT", "RE", "AI", "ET"}
    potential  = re.findall(r'\b[A-Z]{2,5}\b', subject.upper())
    tickers    = [t for t in potential if t not in skip_words][:5]

    if not tickers:
        print("⚠️  No tickers found in subject. Claude will parse the full email.")
        tickers = ["UNKNOWN"]

    print(f"📋 Tickers found: {tickers}")

    # ── Step 3: Pull pre-market data ──────────────────────────
    market_data = []
    for ticker in tickers:
        if ticker != "UNKNOWN":
            market_data.append(get_premarket_data(ticker))
            time.sleep(0.5)

    # ── Step 4: Get account balance ────────────────────────────
    balance = get_account_balance()
    print(f"💰 Account balance: ${balance:.2f}")

    # ── Step 5: Claude Opus analyzes everything ────────────────
    analysis = analyze_with_claude(email_content, market_data, balance)

    if not analysis:
        print("❌ Claude analysis failed. Holding cash today.")
        send_summary_email(None, None, balance)
        return

    # ── Step 6: Check if Claude says GO ───────────────────────
    recommended = analysis.get("recommended_trade", {})
    action      = recommended.get("action", "HOLD CASH")

    if action != "BUY":
        print(f"🔒 Claude says: HOLD CASH today.")
        send_summary_email(analysis, None, balance)
        return

    # ── Step 7: Wait for VWAP entry (responsive, not 8:45am) ──
    ticker_to_trade = recommended.get("ticker")
    position_size   = float(recommended.get("position_size_dollars", balance * MAX_POSITION_SIZE))

    entry_price, vwap = wait_for_vwap_entry(ticker_to_trade)

    if not entry_price:
        note = f"\n\nNOTE: {ticker_to_trade} never reclaimed VWAP by 10am. Cash preserved."
        analysis["plain_english_summary"] += note
        send_summary_email(analysis, None, balance)
        return

    # Recalculate stop and target based on actual VWAP entry price
    stop_loss   = round(entry_price * (1 - STOP_LOSS_PCT), 4)
    target_price = round(entry_price * (1 + TARGET_PCT), 4)
    shares      = round(position_size / entry_price, 4) if entry_price > 0 else 0

    print(f"\n{'='*60}")
    print(f"🎯 TRADE PLAN (VWAP entry confirmed):")
    print(f"   Ticker: {ticker_to_trade}")
    print(f"   VWAP:   ${vwap:.2f}")
    print(f"   Entry:  ${entry_price:.2f}")
    print(f"   Shares: {shares}")
    print(f"   Target: ${target_price:.2f} (+{TARGET_PCT*100:.0f}%)")
    print(f"   Stop:   ${stop_loss:.2f} (-{STOP_LOSS_PCT*100:.0f}%)")
    print(f"   Size:   ${position_size:.2f}")
    print(f"{'='*60}\n")

    # ── Step 8: Execute the trade ─────────────────────────────
    order_id = execute_trade(ticker_to_trade, shares, entry_price, stop_loss, target_price)

    if not order_id:
        print("❌ Trade execution failed. Holding cash.")
        send_summary_email(analysis, None, balance)
        return

    # ── Step 9: Monitor with trailing stop + partial exits ─────
    trade_result = monitor_trade(
        ticker_to_trade, shares,
        entry_price, target_price, stop_loss
    )

    # ── Step 10: Send summary email ───────────────────────────
    new_balance = get_account_balance()
    send_summary_email(analysis, trade_result, new_balance)

    pnl = trade_result.get("profit_loss", 0)
    print(f"\n{'='*60}")
    print(f"✅ TRADING SESSION COMPLETE")
    print(f"   Result: ${pnl:+.2f} ({trade_result.get('profit_loss_pct', 0):+.1f}%)")
    print(f"   Reason: {trade_result.get('exit_reason', 'N/A')}")
    print(f"   New Balance: ${new_balance:.2f}")
    print(f"{'='*60}\n")

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
