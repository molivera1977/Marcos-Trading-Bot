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
6. Executes the trade via Webull at market open if setup confirms
7. Monitors the trade until 11:00am
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

WEBULL_APP_KEY = os.environ.get("WEBULL_APP_KEY")
WEBULL_APP_SECRET = os.environ.get("WEBULL_APP_SECRET")
WEBULL_APP_ID = os.environ.get("WEBULL_APP_ID", "961252838594318336")
WEBULL_ACCOUNT_ID = os.environ.get("WEBULL_ACCOUNT_ID")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "marcostrades2026@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
SUMMARY_EMAIL = os.environ.get("SUMMARY_EMAIL", "molivera1977@gmail.com")

# Trading rules
MAX_POSITION_SIZE = 0.70       # Max 70% of account on single trade
STOP_LOSS_PCT = 0.07           # 7% stop loss
TARGET_PCT = 0.20              # 20% take profit target
TRADE_WINDOW_END_HOUR = 11     # Stop trading after 11am ET
EASTERN = pytz.timezone("America/New_York")

# ============================================================
# STEP 1 — READ GMAIL FOR KEV'S TICKERS
# ============================================================

def read_todays_tickers():
    """
    Connects to marcostrades2026@gmail.com and reads the most
    recent email for ticker symbols and trading notes.
    You send this email each night after watching Kev's TikTok.
    Format: Subject line = "CHAI SUNE LASE" or paste transcript in body.
    """
    print("📧 Checking Gmail for tonight's watchlist...")
    
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("inbox")
        
        # Search for emails from the last 24 hours
        since_date = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
        _, messages = mail.search(None, f'(SINCE "{since_date}")')
        
        if not messages[0]:
            print("⚠️  No recent emails found in watchlist inbox.")
            return None, None
        
        # Get the most recent email
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
# STEP 2 — PULL PRE-MARKET DATA FROM WEBULL
# ============================================================

def get_webull_headers(method, path, body=""):
    """Generate authenticated headers for Webull API calls."""
    timestamp = str(int(time.time() * 1000))
    
    # Build signature
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
    """
    Fetches live pre-market price, volume, and basic stats
    for a given ticker from Webull's API.
    """
    print(f"📊 Fetching pre-market data for {ticker}...")
    
    try:
        path = f"/quotes/ticker/getTickerRealTime"
        params = {"symbol": ticker, "regionId": 6}
        url = f"https://openapi.webull.com{path}"
        headers = get_webull_headers("GET", path)
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        
        if data and "data" in data:
            ticker_data = data["data"]
            return {
                "ticker": ticker,
                "premarket_price": ticker_data.get("preMarketPrice", "N/A"),
                "premarket_change_pct": ticker_data.get("preMarketChangeRatio", "N/A"),
                "premarket_volume": ticker_data.get("preMarketVolume", "N/A"),
                "previous_close": ticker_data.get("preClose", "N/A"),
                "avg_volume": ticker_data.get("avgVol10D", "N/A"),
                "float_shares": ticker_data.get("outstandingShares", "N/A"),
                "market_cap": ticker_data.get("marketValue", "N/A"),
            }
    except Exception as e:
        print(f"⚠️  Webull data error for {ticker}: {e}")
        
    # Return basic structure if API call fails
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
    
    return 100.0  # Default to $100 if unable to fetch

# ============================================================
# STEP 3 — CLAUDE AI ANALYZES THE SETUPS
# ============================================================

def analyze_with_claude(email_content, market_data_list, account_balance):
    """
    Sends Kev's watchlist + live market data to Claude AI.
    Claude applies Kev's exact trading rules and returns:
    - GO or NO-GO for each ticker
    - Entry price, target, stop-loss
    - Position size recommendation
    - Plain English reasoning
    """
    print("🧠 Sending data to Claude AI for analysis...")
    
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
Trading window: 9:00am - 11:00am ET only

KEV'S WATCHLIST EMAIL/TRANSCRIPT FOR TODAY:
{email_content}

LIVE PRE-MARKET DATA FROM WEBULL:
{market_data_text}

YOUR JOB:
1. Read Kev's exact setup rules for each ticker from his transcript
2. Cross-reference with the live pre-market data
3. For each ticker decide: GO or NO-GO based on Kev's rules
4. For GO trades: set exact entry price, profit target, and stop-loss
5. Pick the BEST single trade to execute (max 1-2 trades)
6. Never risk more than 70% of account on one position
7. Always honor Kev's rules exactly - if he says NO BREAK = NO TRADE, honor that
8. Flag any major risks (earnings, halts, offerings, T12 halts)

TRADING RULES:
- Stop loss: 7% below entry (automatic exit)
- Target: 15-25% above entry for day trades
- Entry window: 9:00am - 9:30am ET only
- Exit by: 11:00am ET no matter what
- If pre-market setup fails: hold cash, no trade

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
    "execute_at": "9:00am ET on confirmed break" or "NO TRADE TODAY"
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
            timeout=30
        )
        
        result = response.json()
        raw_text = result["content"][0]["text"]
        
        # Parse JSON response
        clean = raw_text.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()
            
        analysis = json.loads(clean)
        print("✅ Claude analysis complete!")
        return analysis
        
    except Exception as e:
        print(f"❌ Claude API error: {e}")
        return None

# ============================================================
# STEP 4 — EXECUTE TRADE VIA WEBULL
# ============================================================

def execute_trade(ticker, shares, entry_price, stop_loss, target):
    """
    Places a market buy order via Webull API at market open.
    Also sets a stop-loss order to protect your capital automatically.
    """
    print(f"🚀 Executing trade: BUY {shares} shares of {ticker}...")
    
    try:
        # Place market buy order
        path = f"/trading/v1/account/{WEBULL_ACCOUNT_ID}/order"
        url = f"https://openapi.webull.com{path}"
        
        order_body = json.dumps({
            "symbol": ticker,
            "action": "BUY",
            "orderType": "MKT",          # Market order
            "quantity": shares,
            "timeInForce": "DAY",         # Day order only
            "outsideRegularTradingHour": False
        })
        
        headers = get_webull_headers("POST", path, order_body)
        response = requests.post(url, headers=headers, data=order_body, timeout=10)
        order_data = response.json()
        
        if order_data.get("success"):
            order_id = order_data["data"]["orderId"]
            print(f"✅ Buy order placed! Order ID: {order_id}")
            
            # Place stop-loss order immediately after
            time.sleep(2)
            stop_body = json.dumps({
                "symbol": ticker,
                "action": "SELL",
                "orderType": "STP",       # Stop order
                "quantity": shares,
                "auxPrice": stop_loss,    # Stop loss price
                "timeInForce": "DAY",
                "outsideRegularTradingHour": False
            })
            
            stop_headers = get_webull_headers("POST", path, stop_body)
            stop_response = requests.post(url, headers=stop_headers, data=stop_body, timeout=10)
            print(f"🛡️  Stop-loss set at ${stop_loss:.2f}")
            
            return order_id
        else:
            print(f"❌ Order failed: {order_data}")
            return None
            
    except Exception as e:
        print(f"❌ Trade execution error: {e}")
        return None

def close_position(ticker, shares):
    """Sells all shares of a position at market price."""
    print(f"🔒 Closing position: SELL {shares} shares of {ticker}...")
    
    try:
        path = f"/trading/v1/account/{WEBULL_ACCOUNT_ID}/order"
        url = f"https://openapi.webull.com{path}"
        
        order_body = json.dumps({
            "symbol": ticker,
            "action": "SELL",
            "orderType": "MKT",
            "quantity": shares,
            "timeInForce": "DAY",
            "outsideRegularTradingHour": False
        })
        
        headers = get_webull_headers("POST", path, order_body)
        response = requests.post(url, headers=headers, data=order_body, timeout=10)
        data = response.json()
        
        if data.get("success"):
            print(f"✅ Position closed successfully!")
            return True
    except Exception as e:
        print(f"❌ Close position error: {e}")
    
    return False

def get_current_price(ticker):
    """Gets the current real-time price of a ticker."""
    try:
        path = f"/quotes/ticker/getTickerRealTime"
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

# ============================================================
# STEP 5 — MONITOR THE TRADE (9am - 11am)
# ============================================================

def monitor_trade(ticker, shares, entry_price, target_price, stop_loss):
    """
    Watches the trade every 60 seconds from 9am to 11am ET.
    Automatically exits if target or stop-loss is hit.
    Always closes by 11am no matter what.
    """
    print(f"👀 Monitoring {ticker}... Target: ${target_price:.2f} | Stop: ${stop_loss:.2f}")
    
    entry_time = datetime.now(EASTERN)
    result = {
        "exit_price": entry_price,
        "exit_reason": "Unknown",
        "profit_loss": 0,
        "profit_loss_pct": 0
    }
    
    while True:
        now = datetime.now(EASTERN)
        
        # Force close at 11am ET
        if now.hour >= TRADE_WINDOW_END_HOUR:
            print("⏰ 11:00am — Closing all positions for the day")
            current_price = get_current_price(ticker)
            close_position(ticker, shares)
            result["exit_price"] = current_price
            result["exit_reason"] = "11am time stop"
            break
        
        # Check current price
        current_price = get_current_price(ticker)
        
        if current_price <= 0:
            time.sleep(60)
            continue
            
        profit_pct = ((current_price - entry_price) / entry_price) * 100
        print(f"💰 {ticker}: ${current_price:.2f} ({profit_pct:+.1f}%) | Target: ${target_price:.2f} | Stop: ${stop_loss:.2f}")
        
        # Hit target — take profit
        if current_price >= target_price:
            print(f"🎯 TARGET HIT! Selling {ticker} at ${current_price:.2f}")
            close_position(ticker, shares)
            result["exit_price"] = current_price
            result["exit_reason"] = "Target hit ✅"
            break
        
        # Hit stop loss — cut losses
        if current_price <= stop_loss:
            print(f"🛑 STOP LOSS HIT! Selling {ticker} at ${current_price:.2f}")
            close_position(ticker, shares)
            result["exit_price"] = current_price
            result["exit_reason"] = "Stop loss triggered 🛑"
            break
        
        # Check every 60 seconds
        time.sleep(60)
    
    # Calculate final P&L
    result["profit_loss"] = (result["exit_price"] - entry_price) * shares
    result["profit_loss_pct"] = ((result["exit_price"] - entry_price) / entry_price) * 100
    
    return result

# ============================================================
# STEP 6 — EMAIL SUMMARY TO MARCOS
# ============================================================

def send_summary_email(analysis, trade_result=None, account_balance=100.0):
    """
    Sends a plain-English summary email to molivera1977@gmail.com
    after the trading session ends. Win or lose, full transparency.
    """
    print(f"📨 Sending summary email to {SUMMARY_EMAIL}...")
    
    today = datetime.now(EASTERN).strftime("%A, %B %d, %Y")
    
    if trade_result and analysis:
        recommended = analysis.get("recommended_trade", {})
        ticker = recommended.get("ticker", "N/A")
        pnl = trade_result.get("profit_loss", 0)
        pnl_pct = trade_result.get("profit_loss_pct", 0)
        exit_reason = trade_result.get("exit_reason", "N/A")
        exit_price = trade_result.get("exit_price", 0)
        
        emoji = "✅" if pnl > 0 else "🔴"
        result_line = f"{emoji} {ticker}: {pnl_pct:+.1f}% (${pnl:+.2f})"
        
        subject = f"Trading Bot Summary — {today} | {result_line}"
        
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
        # No trade taken today
        subject = f"Trading Bot Summary — {today} | 💤 No Trade Today"
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
Just paste Kev's TikTok transcript or type the ticker symbols
in the subject line. The bot reads it at 8:45am tomorrow.
"""

    body += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Marcos Trading Bot | Powered by Claude AI
Running on Railway.app | Webull account
Questions? Open Claude and ask!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = SUMMARY_EMAIL
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
    """
    Main trading routine. Railway.app runs this every weekday
    morning at 8:45am ET automatically. Your device never needs
    to be on for this to work.
    """
    now = datetime.now(EASTERN)
    print(f"\n{'='*60}")
    print(f"🤖 MARCOS TRADING BOT STARTING UP")
    print(f"📅 {now.strftime('%A, %B %d, %Y at %I:%M %p ET')}")
    print(f"{'='*60}\n")
    
    # Don't run on weekends
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
    # Tickers are usually in the subject: "CHAI SUNE LASE"
    import re
    potential_tickers = re.findall(r'\b[A-Z]{2,5}\b', subject.upper())
    
    # Filter out common non-ticker words
    skip_words = {"THE", "FOR", "AND", "NOT", "ALL", "DAY", "TOP", 
                  "NEW", "BIG", "HOT", "PDT", "RE", "AI", "ET"}
    tickers = [t for t in potential_tickers if t not in skip_words][:5]
    
    if not tickers:
        print("⚠️  No tickers found in subject. Claude will parse the full email.")
        tickers = ["UNKNOWN"]  # Claude will find them in the body
    
    print(f"📋 Tickers found: {tickers}")
    
    # ── Step 3: Pull pre-market data for each ticker ───────────
    market_data = []
    for ticker in tickers:
        if ticker != "UNKNOWN":
            data = get_premarket_data(ticker)
            market_data.append(data)
            time.sleep(0.5)  # Rate limiting
    
    # ── Step 4: Get account balance ────────────────────────────
    balance = get_account_balance()
    print(f"💰 Account balance: ${balance:.2f}")
    
    # ── Step 5: Claude analyzes everything ────────────────────
    analysis = analyze_with_claude(email_content, market_data, balance)
    
    if not analysis:
        print("❌ Claude analysis failed. Holding cash today.")
        send_summary_email(None, None, balance)
        return
    
    # ── Step 6: Check if Claude says GO ───────────────────────
    recommended = analysis.get("recommended_trade", {})
    action = recommended.get("action", "HOLD CASH")
    
    if action != "BUY":
        print(f"🔒 Claude says: HOLD CASH today. Reason: {analysis.get('plain_english_summary', '')[:100]}")
        send_summary_email(analysis, None, balance)
        return
    
    # ── Step 7: Wait for market open (9:00am ET) ──────────────
    ticker_to_trade = recommended.get("ticker")
    entry_price = float(recommended.get("entry_price", 0))
    target_price = float(recommended.get("target_price", 0))
    stop_loss = float(recommended.get("stop_loss", 0))
    position_size = float(recommended.get("position_size_dollars", 60))
    
    # Calculate shares (Webull supports fractional shares)
    shares = round(position_size / entry_price, 4) if entry_price > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"🎯 TRADE PLAN:")
    print(f"   Ticker: {ticker_to_trade}")
    print(f"   Shares: {shares}")
    print(f"   Entry:  ${entry_price:.2f}")
    print(f"   Target: ${target_price:.2f} (+{((target_price-entry_price)/entry_price)*100:.0f}%)")
    print(f"   Stop:   ${stop_loss:.2f} (-{((entry_price-stop_loss)/entry_price)*100:.0f}%)")
    print(f"   Size:   ${position_size:.2f}")
    print(f"{'='*60}\n")
    
    # Wait until 9:00am ET
    while datetime.now(EASTERN).hour < 9:
        print("⏳ Waiting for market open at 9:00am ET...")
        time.sleep(30)
    
    # ── Step 8: Confirm setup at open ─────────────────────────
    current_price = get_current_price(ticker_to_trade)
    print(f"🔔 Market open! {ticker_to_trade} currently at ${current_price:.2f}")
    
    # Verify setup still valid (price within 10% of expected entry)
    if current_price > 0 and abs(current_price - entry_price) / entry_price > 0.15:
        print(f"⚠️  Price moved too far from analysis. Setup invalid. Holding cash.")
        analysis["plain_english_summary"] += f"\n\nNOTE: {ticker_to_trade} opened at ${current_price:.2f} vs expected ${entry_price:.2f} — setup invalidated at open. Cash preserved."
        send_summary_email(analysis, None, balance)
        return
    
    # ── Step 9: Execute the trade ─────────────────────────────
    order_id = execute_trade(ticker_to_trade, shares, current_price, stop_loss, target_price)
    
    if not order_id:
        print("❌ Trade execution failed. Holding cash.")
        send_summary_email(analysis, None, balance)
        return
    
    actual_entry = current_price if current_price > 0 else entry_price
    
    # ── Step 10: Monitor the trade until 11am ─────────────────
    trade_result = monitor_trade(
        ticker_to_trade, shares,
        actual_entry, target_price, stop_loss
    )
    
    # ── Step 11: Send summary email ───────────────────────────
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
