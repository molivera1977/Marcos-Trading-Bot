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
4. Sends everything to Claude Opus AI for deep analysis
5. Claude picks the best setup with entry/target/stop-loss
6. Opens a real-time MQTT stream from Webull (falls back to polling if unavailable)
7. Waits for VWAP reclaim after 9:30am open before entering
8. Monitors with trailing stop + partial exits in near real-time
9. Sends 4 emails throughout the day:
   - ~8:55am: Claude's plan (what it picked and why)
   - On entry: trade filled (price, shares, levels)
   - At +15%: partial exit alert (half sold, rest riding)
   - At close: full summary with P&L

SETUP INSTRUCTIONS:
- Set the following environment variables in Railway.app:
  WEBULL_APP_KEY        = your Webull App Key
  WEBULL_APP_SECRET     = your Webull App Secret
  WEBULL_APP_ID         = 961252838594318336
  WEBULL_ACCOUNT_ID     = your Webull account ID
  EMAIL_ADDRESS         = marcostrades2026@gmail.com
  EMAIL_APP_PASSWORD    = your Gmail app password
  ANTHROPIC_API_KEY     = your Claude API key
  SUMMARY_EMAIL         = molivera1977@gmail.com
"""

import os
import re
import imaplib
import email
import json
import time
import hmac
import hashlib
import threading
import requests
import anthropic
import resend
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz

# ============================================================
# CONFIGURATION
# ============================================================

WEBULL_APP_KEY     = os.environ.get("WEBULL_APP_KEY")
WEBULL_APP_SECRET  = os.environ.get("WEBULL_APP_SECRET")
WEBULL_APP_ID      = os.environ.get("WEBULL_APP_ID", "961252838594318336")
WEBULL_ACCOUNT_ID  = os.environ.get("WEBULL_ACCOUNT_ID")
EMAIL_ADDRESS      = os.environ.get("EMAIL_ADDRESS", "molivera1977@icloud.com")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY")
RESEND_API_KEY     = os.environ.get("RESEND_API_KEY")
SUMMARY_EMAIL      = os.environ.get("SUMMARY_EMAIL", "molivera1977@gmail.com")

# iCloud IMAP (reading only — sending is via Resend API over HTTPS)
IMAP_SERVER = "imap.mail.me.com"
IMAP_PORT   = 993

# Trading rules
MAX_POSITION_SIZE     = 0.70   # Max 70% of account on single trade
STOP_LOSS_PCT         = 0.07   # 7% initial stop loss
TARGET_PCT            = 0.20   # 20% full profit target
PARTIAL_EXIT_PCT      = 0.15   # Sell half at 15% gain
BREAKEVEN_TRIGGER_PCT = 0.10   # Move stop to breakeven at 10% gain
TRAIL_PCT             = 0.05   # Trail 5% below highest after partial exit
VWAP_ENTRY_TIMEOUT    = 10     # Give up on VWAP entry after 10am ET
TRADE_WINDOW_END_HOUR = 11     # Force close all positions by 11am ET
EASTERN = pytz.timezone("America/New_York")

# MQTT streaming — Webull pushes prices up to 3x/second
WEBULL_MQTT_HOST  = "stream.webull.com"
WEBULL_MQTT_PORT  = 443          # WebSocket over TLS
MQTT_LOOP_SLEEP   = 0.5          # When streaming: check every 0.5s
POLL_LOOP_SLEEP   = 15           # Fallback polling: check every 15s

# ============================================================
# REAL-TIME PRICE STREAM (MQTT)
# ============================================================

# Shared price registry — updated by MQTT callbacks from a background thread
_price_registry: dict = {}
_price_lock = threading.Lock()


class WebullStream:
    """
    Connects to Webull's MQTT stream for real-time price pushes.
    Webull pushes up to 3 price updates per second per ticker.
    Falls back to REST polling automatically if MQTT is unavailable.
    """

    def __init__(self, tickers: list):
        self.tickers   = tickers if isinstance(tickers, list) else [tickers]
        self.client    = None
        self.connected = False
        self._connect()

    def _connect(self):
        try:
            self.client = mqtt.Client(transport="websockets")
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.username_pw_set(WEBULL_APP_KEY, WEBULL_APP_SECRET)
            self.client.tls_set()
            self.client.connect(WEBULL_MQTT_HOST, WEBULL_MQTT_PORT, keepalive=30)
            self.client.loop_start()
            time.sleep(3)  # Allow time to handshake
            if self.connected:
                print(f"📡 MQTT stream connected — real-time prices active")
            else:
                print(f"⚠️  MQTT stream unavailable — using 15s polling fallback")
        except Exception as e:
            print(f"⚠️  MQTT connection error: {e} — using 15s polling fallback")
            self.connected = False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            for ticker in self.tickers:
                topic = f"quote/ticker/{ticker}"
                client.subscribe(topic, qos=0)
                print(f"   ✅ Subscribed: {ticker}")
        else:
            print(f"⚠️  MQTT rejected (rc={rc})")

    def _on_message(self, client, userdata, msg):
        try:
            data   = json.loads(msg.payload.decode())
            ticker = msg.topic.split("/")[-1].upper()
            price  = float(
                data.get("close") or
                data.get("lastPrice") or
                data.get("price") or 0
            )
            if price > 0:
                with _price_lock:
                    _price_registry[ticker] = price
        except Exception:
            pass

    def get_price(self, ticker: str) -> float:
        """
        Returns the latest price for ticker.
        If MQTT is live, reads from the in-memory registry (sub-second fresh).
        If MQTT failed, falls back to a REST call.
        """
        if self.connected:
            with _price_lock:
                return _price_registry.get(ticker.upper(), 0)
        return _get_price_rest(ticker)

    def loop_sleep(self) -> float:
        """How long to sleep between price checks in the monitoring loop."""
        return MQTT_LOOP_SLEEP if self.connected else POLL_LOOP_SLEEP

    def stop(self):
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass

# ============================================================
# STEP 1 — READ GMAIL FOR KEV'S TICKERS
# ============================================================

def read_todays_tickers():
    print("📧 Checking Gmail for tonight's watchlist...")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        mail.select("inbox")

        since_date = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
        _, messages = mail.search(None, f'(SINCE "{since_date}")')

        if not messages[0]:
            print("⚠️  No recent emails found.")
            return None, None

        latest = messages[0].split()[-1]
        _, msg_data = mail.fetch(latest, "(RFC822)")

        # iCloud returns a flat list of bytes; Gmail returns a list of tuples.
        # Handle both formats robustly.
        raw_email = None
        for part in msg_data:
            if isinstance(part, tuple):
                raw_email = part[1]   # Gmail-style: (header_bytes, email_bytes)
                break
        if raw_email is None:
            # iCloud-style: flat list — find the largest bytes chunk (the actual email)
            raw_email = max(
                (p for p in msg_data if isinstance(p, bytes)),
                key=len, default=None
            )
        if not raw_email:
            raise ValueError(f"Could not parse email from IMAP response: {msg_data}")

        msg = email.message_from_bytes(raw_email)

        subject = msg["subject"] or ""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body = payload.decode("utf-8", errors="ignore")
                    break
        else:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode("utf-8", errors="ignore")
            elif isinstance(payload, str):
                body = payload

        full_content = f"Subject: {subject}\n\nBody: {body}"
        print(f"✅ Found watchlist email: {subject}")
        mail.logout()
        return subject, full_content

    except Exception as e:
        print(f"❌ Gmail error: {e}")
        return None, None

# ============================================================
# STEP 2 — WEBULL REST HELPERS
# ============================================================

def _webull_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign_str  = f"{method}\n{path}\n{body}\n{timestamp}"
    signature = hmac.new(
        WEBULL_APP_SECRET.encode(),
        sign_str.encode(),
        hashlib.sha256
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "App-Key":      WEBULL_APP_KEY,
        "Timestamp":    timestamp,
        "Sign":         signature,
        "App-Id":       WEBULL_APP_ID,
    }

def get_premarket_data(ticker):
    print(f"📊 Fetching pre-market data for {ticker}...")
    try:
        path    = "/quotes/ticker/getTickerRealTime"
        params  = {"symbol": ticker, "regionId": 6}
        url     = f"https://api.webull.com{path}"
        headers = _webull_headers("GET", path)
        resp    = requests.get(url, headers=headers, params=params, timeout=10)
        d       = resp.json().get("data", {})
        return {
            "ticker":               ticker,
            "premarket_price":      d.get("preMarketPrice", "N/A"),
            "premarket_change_pct": d.get("preMarketChangeRatio", "N/A"),
            "premarket_volume":     d.get("preMarketVolume", "N/A"),
            "previous_close":       d.get("preClose", "N/A"),
            "avg_volume":           d.get("avgVol10D", "N/A"),
            "float_shares":         d.get("outstandingShares", "N/A"),
            "market_cap":           d.get("marketValue", "N/A"),
        }
    except Exception as e:
        print(f"⚠️  Webull data error for {ticker}: {e}")
    return {"ticker": ticker, "premarket_price": "N/A", "premarket_change_pct": "N/A",
            "premarket_volume": "N/A", "previous_close": "N/A",
            "avg_volume": "N/A", "float_shares": "N/A", "market_cap": "N/A"}

def get_account_balance():
    try:
        path    = f"/paper/trading/v2/account/{WEBULL_ACCOUNT_ID}/positions"
        url     = f"https://api.webull.com{path}"
        headers = _webull_headers("GET", path)
        resp    = requests.get(url, headers=headers, timeout=10)
        data    = resp.json()
        if data and "data" in data:
            return float(data["data"].get("cashBalance", 100.0))
    except Exception as e:
        print(f"⚠️  Balance fetch error: {e}")
    return 100.0

def _get_price_rest(ticker) -> float:
    """REST fallback for current price when MQTT is unavailable."""
    try:
        path    = "/quotes/ticker/getTickerRealTime"
        params  = {"symbol": ticker, "regionId": 6}
        url     = f"https://api.webull.com{path}"
        headers = _webull_headers("GET", path)
        resp    = requests.get(url, headers=headers, params=params, timeout=10)
        data    = resp.json()
        if data and "data" in data:
            return float(data["data"].get("close", 0))
    except Exception:
        pass
    return 0

def get_intraday_bars(ticker, count=30):
    try:
        path    = "/quotes/ticker/getTickerChart"
        params  = {"symbol": ticker, "type": "m1", "count": count, "regionId": 6}
        url     = f"https://api.webull.com{path}"
        headers = _webull_headers("GET", path)
        resp    = requests.get(url, headers=headers, params=params, timeout=10)
        data    = resp.json()
        if data and "data" in data:
            return data["data"]
    except Exception as e:
        print(f"⚠️  Intraday bars error for {ticker}: {e}")
    return []

def calculate_vwap(bars) -> float:
    total_pv, total_vol = 0, 0
    for bar in bars:
        high  = float(bar.get("high", 0))
        low   = float(bar.get("low", 0))
        close = float(bar.get("close", 0))
        vol   = float(bar.get("volume", 0))
        total_pv  += ((high + low + close) / 3) * vol
        total_vol += vol
    return total_pv / total_vol if total_vol > 0 else 0

# ============================================================
# STEP 3 — CLAUDE OPUS ANALYZES THE SETUPS
# ============================================================

def analyze_with_claude(email_content, market_data_list, account_balance):
    print("🧠 Sending data to Claude Opus AI for analysis...")

    market_text = "\n".join([
        f"Ticker: {d['ticker']}\n"
        f"Pre-market Price: ${d['premarket_price']}\n"
        f"Pre-market Change: {d['premarket_change_pct']}%\n"
        f"Pre-market Volume: {d['premarket_volume']}\n"
        f"Previous Close: ${d['previous_close']}\n"
        f"10-Day Avg Volume: {d['avg_volume']}\n"
        f"Market Cap: ${d['market_cap']}\n"
        for d in market_data_list
    ])

    prompt = f"""
You are an AI trading assistant for Marcos Olivera, a retail trader
using Kev's Momentum trading system (TradeMomentum.org).

Today's date: {datetime.now(EASTERN).strftime("%A, %B %d, %Y")}
Account balance: ${account_balance:.2f}
Market open: 9:30am ET
Entry strategy: Wait for confirmed VWAP reclaim with volume after open
Trading window: Entry by 10:00am ET, hold until 11:00am max

KEV'S WATCHLIST EMAIL/TRANSCRIPT:
{email_content}

LIVE PRE-MARKET DATA FROM WEBULL:
{market_text}

YOUR JOB:
1. Read Kev's exact setup rules for each ticker from his transcript
2. Cross-reference with the live pre-market data
3. For each ticker decide: GO or NO-GO based on Kev's rules
4. For GO trades: set exact expected VWAP entry price, profit target, stop-loss
5. Pick the BEST single trade (max 1 trade)
6. Never risk more than 70% of account on one position
7. Honor Kev's rules exactly — if he says NO BREAK = NO TRADE, honor that
8. Flag any major risks (earnings, halts, offerings, T12 halts)

TRADING RULES:
- Entry: Only on confirmed VWAP reclaim with volume (bot handles this automatically)
- Stop loss: 7% below actual entry (recalculated at VWAP entry)
- At +10%: stop moves to breakeven automatically
- At +15%: sells half, sets 5% trailing stop on remainder
- At +20%: full exit
- Hard close: 11:00am ET
- If no VWAP reclaim by 10:00am: hold cash

Respond in this EXACT JSON format:
{{
  "analysis_date": "YYYY-MM-DD",
  "market_summary": "2-3 sentence overview",
  "tickers": [
    {{
      "ticker": "SYMBOL",
      "verdict": "GO" or "NO-GO",
      "reason": "Plain English explanation",
      "setup_confirmed": true or false,
      "entry_price": 0.00,
      "target_price": 0.00,
      "stop_loss": 0.00,
      "position_size_dollars": 0.00,
      "vwap_level": 0.00,
      "risk_flags": [],
      "kev_rule_check": "Did pre-market confirm Kev's rule? Yes/No and why"
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
    "execute_at": "On VWAP reclaim after 9:30am" or "NO TRADE TODAY"
  }},
  "plain_english_summary": "Text Marcos at 8:55am. Tell him what the bot is doing and why. Friendly and clear."
}}
"""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        # Stream the response — analysis can be long and we don't want request timeouts
        with client.messages.stream(
            model="claude-opus-4-8",
            max_tokens=4000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            message = stream.get_final_message()

        # Extract text from the response (skip thinking blocks)
        raw = ""
        for block in message.content:
            if block.type == "text":
                raw = block.text.strip()
                break

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        analysis = json.loads(raw)
        print("✅ Claude Opus analysis complete!")
        return analysis
    except Exception as e:
        print(f"❌ Claude API error: {e}")
        return None

# ============================================================
# STEP 4 — WAIT FOR VWAP ENTRY
# ============================================================

VWAP_BAR_CACHE_SECS = 30   # Refresh intraday bars every 30s — VWAP doesn't change faster

def wait_for_vwap_entry(ticker, stream: WebullStream):
    """
    After 9:30am open, watches price vs VWAP using the real-time stream.
    Price is checked at stream frequency (0.5s MQTT / 15s polling).
    Intraday bars are refreshed every 30s — VWAP is stable enough for this.
    Times out at 10am — holds cash if no reclaim.
    Returns (entry_price, vwap) or (None, None).
    """
    print(f"\n⏳ Waiting for {ticker} VWAP reclaim after open...")

    cached_bars      = []
    last_bar_fetch   = 0.0   # epoch seconds of last bars API call
    cached_vwap      = 0.0

    while True:
        now = datetime.now(EASTERN)

        if now.hour >= VWAP_ENTRY_TIMEOUT:
            print(f"⏰ {ticker} never reclaimed VWAP by 10am. Holding cash.")
            return None, None

        if now.hour < 9 or (now.hour == 9 and now.minute < 30):
            mins = (9 * 60 + 30) - (now.hour * 60 + now.minute)
            print(f"⏳ Market opens in ~{mins} min...")
            time.sleep(30)
            continue

        # ── Refresh bars every 30s, use cache in between ────
        if time.time() - last_bar_fetch >= VWAP_BAR_CACHE_SECS:
            fresh = get_intraday_bars(ticker)
            if fresh:
                cached_bars    = fresh
                cached_vwap    = calculate_vwap(cached_bars)
                last_bar_fetch = time.time()

        current_price = stream.get_price(ticker)

        if not cached_bars or current_price <= 0 or cached_vwap <= 0:
            time.sleep(stream.loop_sleep())
            continue

        pct_vs_vwap = ((current_price - cached_vwap) / cached_vwap) * 100
        print(f"📊 {ticker}: ${current_price:.2f} | VWAP: ${cached_vwap:.2f} ({pct_vs_vwap:+.1f}%)")

        if current_price > cached_vwap:
            last_vol = float(cached_bars[-1].get("volume", 0))
            avg_vol  = sum(float(b.get("volume", 0)) for b in cached_bars) / len(cached_bars)
            if last_vol >= avg_vol * 0.75:
                print(f"✅ VWAP reclaim confirmed! ${current_price:.2f} > VWAP ${cached_vwap:.2f} with volume")
                return current_price, cached_vwap
            else:
                print(f"⚠️  Above VWAP but volume light. Waiting for confirmation...")

        time.sleep(stream.loop_sleep())

# ============================================================
# STEP 5 — EXECUTE TRADE VIA WEBULL
# ============================================================

def execute_trade(ticker, shares, entry_price, stop_loss, target):
    """
    Places the buy order then immediately places a real stop order on Webull.
    Returns (buy_order_id, stop_order_id) — both needed to manage the trade.
    Returns (None, None) on failure.
    """
    print(f"🚀 Executing: BUY {shares} shares of {ticker} @ ${entry_price:.2f}...")
    try:
        path = f"/trading/v1/account/{WEBULL_ACCOUNT_ID}/order"
        url  = f"https://api.webull.com{path}"

        buy_body = json.dumps({
            "symbol": ticker, "action": "BUY",
            "orderType": "MKT", "quantity": shares,
            "timeInForce": "DAY", "outsideRegularTradingHour": False
        })
        headers    = _webull_headers("POST", path, buy_body)
        resp       = requests.post(url, headers=headers, data=buy_body, timeout=10)
        order_data = resp.json()

        if order_data.get("success"):
            buy_id = order_data["data"]["orderId"]
            print(f"✅ Buy order placed! Order ID: {buy_id}")

            time.sleep(2)   # Let fill confirm before placing stop
            stop_id = place_stop_order(ticker, shares, stop_loss)
            return buy_id, stop_id
        else:
            print(f"❌ Order failed: {order_data}")
    except Exception as e:
        print(f"❌ Trade execution error: {e}")
    return None, None

def close_position(ticker, shares):
    print(f"🔒 Closing: SELL {shares} shares of {ticker}...")
    try:
        path = f"/trading/v1/account/{WEBULL_ACCOUNT_ID}/order"
        url  = f"https://api.webull.com{path}"
        body = json.dumps({
            "symbol": ticker, "action": "SELL",
            "orderType": "MKT", "quantity": shares,
            "timeInForce": "DAY", "outsideRegularTradingHour": False
        })
        headers = _webull_headers("POST", path, body)
        resp    = requests.post(url, headers=headers, data=body, timeout=10)
        if resp.json().get("success"):
            print("✅ Position closed!")
            return True
    except Exception as e:
        print(f"❌ Close error: {e}")
    return False

def cancel_order(order_id):
    """Cancel an open order by ID. Used when moving/replacing stop orders."""
    if not order_id:
        return False
    try:
        path    = f"/trading/v1/account/{WEBULL_ACCOUNT_ID}/order/{order_id}/cancel"
        url     = f"https://api.webull.com{path}"
        headers = _webull_headers("DELETE", path)
        resp    = requests.delete(url, headers=headers, timeout=10)
        if resp.json().get("success"):
            print(f"✅ Order {order_id} cancelled")
            return True
        else:
            print(f"⚠️  Cancel failed for {order_id}: {resp.json()}")
    except Exception as e:
        print(f"⚠️  Cancel order error: {e}")
    return False

def place_stop_order(ticker, shares, stop_price):
    """
    Place a live stop-loss sell order on Webull.
    Returns the new order ID, or None if it fails.
    """
    try:
        path = f"/trading/v1/account/{WEBULL_ACCOUNT_ID}/order"
        url  = f"https://api.webull.com{path}"
        body = json.dumps({
            "symbol": ticker, "action": "SELL",
            "orderType": "STP", "quantity": shares,
            "auxPrice": stop_price,
            "timeInForce": "DAY", "outsideRegularTradingHour": False
        })
        headers = _webull_headers("POST", path, body)
        resp    = requests.post(url, headers=headers, data=body, timeout=10)
        data    = resp.json()
        if data.get("success"):
            new_id = data["data"]["orderId"]
            print(f"🛡️  Stop order placed: ${stop_price:.2f} × {shares} shares (ID: {new_id})")
            return new_id
        else:
            print(f"⚠️  Stop order failed: {data}")
    except Exception as e:
        print(f"⚠️  Stop order error: {e}")
    return None

def update_stop_order(ticker, shares, new_price, old_order_id):
    """
    Cancel the existing exchange stop order and place a new one at the updated price/quantity.
    Returns the new order ID (or None if the replacement fails — logs a warning).
    """
    print(f"🔄 Moving stop order → ${new_price:.2f} ({shares} shares)...")
    cancel_order(old_order_id)
    time.sleep(0.5)   # Let the cancel settle before placing new order
    new_id = place_stop_order(ticker, shares, new_price)
    if not new_id:
        print(f"❌ WARNING: Stop order replacement failed! Position has no exchange-level stop.")
    return new_id

# ============================================================
# STEP 6 — MONITOR WITH TRAILING STOP + PARTIAL EXITS
# ============================================================

STOP_UPDATE_MIN_MOVE = 0.10   # Only replace exchange stop order if it moves >= $0.10

def monitor_trade(ticker, total_shares, entry_price, target_price, stop_loss,
                  stream: WebullStream, stop_order_id):
    """
    Monitors the trade using the real-time stream.
    All stop levels are kept as live orders on Webull — not just in memory.
    If Railway restarts mid-trade, Webull enforces the last placed stop.

    - MQTT connected: checks every 0.5 seconds
    - Fallback polling: checks every 15 seconds

    Stop order lifecycle:
    - Entry:        hard stop at -7% placed by execute_trade
    - At +10%:      cancel & replace stop at breakeven (entry price)
    - At +15%:      partial exit; cancel & replace stop for remaining shares at trail
    - Trailing:     cancel & replace stop as trail moves up (only if moved >= $0.10)
    - Target/time:  cancel stop, close with market order
    """
    sleep_secs = stream.loop_sleep()
    mode = "real-time MQTT" if stream.connected else "15s polling fallback"
    print(f"\n👀 Monitoring {ticker} via {mode}")
    print(f"   Entry: ${entry_price:.2f} | Target: ${target_price:.2f} | Stop: ${stop_loss:.2f}")

    current_stop       = stop_loss
    placed_stop_price  = stop_loss        # price of the live Webull stop order
    placed_stop_qty    = total_shares     # quantity of the live Webull stop order
    placed_stop_id     = stop_order_id   # order ID of the live Webull stop order
    highest_price      = entry_price
    remaining_shares   = total_shares
    partial_taken      = False
    partial_price      = 0.0

    result = {"exit_price": entry_price, "exit_reason": "Unknown",
              "profit_loss": 0, "profit_loss_pct": 0}

    while True:
        now = datetime.now(EASTERN)

        # ── Hard close at 11am ──────────────────────────
        if now.hour >= TRADE_WINDOW_END_HOUR:
            print("⏰ 11:00am — Force closing all positions")
            current_price = stream.get_price(ticker)
            if remaining_shares > 0:
                cancel_order(placed_stop_id)   # Remove stop before market sell
                close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "11am time stop"
            break

        current_price = stream.get_price(ticker)
        if current_price <= 0:
            time.sleep(sleep_secs)
            continue

        profit_pct = ((current_price - entry_price) / entry_price) * 100

        if current_price > highest_price:
            highest_price = current_price

        # ── Breakeven stop: move to entry at +10% ───────
        if not partial_taken and profit_pct >= BREAKEVEN_TRIGGER_PCT * 100 \
                and current_stop < entry_price:
            current_stop = entry_price
            print(f"🔒 Stop → breakeven ${current_stop:.2f}")
            placed_stop_id    = update_stop_order(ticker, placed_stop_qty,
                                                  current_stop, placed_stop_id)
            placed_stop_price = current_stop

        # ── Trailing stop: ratchet up after partial exit ─
        if partial_taken:
            trail = highest_price * (1 - TRAIL_PCT)
            if trail > current_stop:
                current_stop = trail
                print(f"📈 Trailing stop → ${current_stop:.2f}")
                # Only replace exchange order if stop moved >= $0.10 (avoids order spam)
                if current_stop - placed_stop_price >= STOP_UPDATE_MIN_MOVE:
                    placed_stop_id    = update_stop_order(ticker, placed_stop_qty,
                                                          current_stop, placed_stop_id)
                    placed_stop_price = current_stop

        print(f"💰 {ticker}: ${current_price:.2f} ({profit_pct:+.1f}%) | Stop: ${current_stop:.2f} | Shares: {remaining_shares}")

        # ── Partial exit at +15% ────────────────────────
        if not partial_taken and profit_pct >= PARTIAL_EXIT_PCT * 100:
            half = round(remaining_shares / 2, 4)
            print(f"💰 PARTIAL EXIT: selling {half} shares at ${current_price:.2f} (+{profit_pct:.1f}%)")
            # Cancel old full-size stop before selling half
            cancel_order(placed_stop_id)
            close_position(ticker, half)
            partial_price    = current_price
            partial_taken    = True
            remaining_shares = round(remaining_shares - half, 4)
            current_stop     = highest_price * (1 - TRAIL_PCT)
            # Place new stop for remaining shares only at trail level
            placed_stop_id    = place_stop_order(ticker, remaining_shares, current_stop)
            placed_stop_price = current_stop
            placed_stop_qty   = remaining_shares
            print(f"📈 Trailing stop set at ${current_stop:.2f} — letting rest run")
            # ── Alert 3: Partial exit notification ──────────
            send_partial_exit_alert(ticker, half, partial_price, entry_price,
                                    remaining_shares, current_stop, profit_pct)

        # ── Full target hit ─────────────────────────────
        if current_price >= target_price and remaining_shares > 0:
            print(f"🎯 TARGET HIT! Selling {remaining_shares} shares at ${current_price:.2f}")
            cancel_order(placed_stop_id)   # Remove stop before market sell
            close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "Target hit ✅"
            remaining_shares = 0
            break

        # ── Software stop detection (backup to exchange stop) ──
        # Exchange stop handles most cases; this catches any gap/lag
        if current_price <= current_stop and remaining_shares > 0:
            label = "Trailing stop 📉" if partial_taken else "Stop loss 🛑"
            print(f"🛑 {label} hit! Selling {remaining_shares} shares at ${current_price:.2f}")
            cancel_order(placed_stop_id)
            close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = label
            remaining_shares = 0
            break

        time.sleep(sleep_secs)

    # ── Blended P&L ─────────────────────────────────────
    if partial_taken:
        half = total_shares / 2
        rest = total_shares - half
        result["profit_loss"] = (
            (partial_price - entry_price) * half +
            (result["exit_price"] - entry_price) * rest
        )
    else:
        result["profit_loss"] = (result["exit_price"] - entry_price) * total_shares

    result["profit_loss_pct"] = ((result["exit_price"] - entry_price) / entry_price) * 100
    return result

# ============================================================
# STEP 7 — ALERT EMAILS (fired in real-time during the session)
# ============================================================

def send_alert_email(subject, body):
    """
    Sends email via Resend API over HTTPS — bypasses Railway's SMTP block.
    """
    print(f"📲 Sending alert: {subject}")
    try:
        resend.api_key = RESEND_API_KEY
        footer = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nMarcos Trading Bot | Railway.app"
        resend.Emails.send({
            "from":    "Marcos Trading Bot <onboarding@resend.dev>",
            "to":      [SUMMARY_EMAIL],
            "subject": subject,
            "text":    body + footer,
        })
        print(f"✅ Alert sent!")
    except Exception as e:
        print(f"❌ Alert email error: {e}")


def send_plan_alert(analysis, balance):
    """Alert 1 — Fired right after Claude finishes analysis (~8:55am)."""
    recommended = analysis.get("recommended_trade", {})
    action      = recommended.get("action", "HOLD CASH")
    ticker      = recommended.get("ticker", "N/A")
    today       = datetime.now(EASTERN).strftime("%A, %B %d, %Y")

    if action == "BUY":
        subject = f"🤖 Bot Plan — {ticker} is the pick | {today}"
        body = f"""Good morning Marcos! Claude just finished the pre-market analysis.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TODAY'S PLAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticker:      {ticker}
Action:      Watching for VWAP reclaim after 9:30am
Entry:       ~${recommended.get('entry_price', 0):.2f} (on VWAP reclaim)
Target:      ${recommended.get('target_price', 0):.2f} (+20%)
Stop loss:   ${recommended.get('stop_loss', 0):.2f} (-7%)
Size:        ${recommended.get('position_size_dollars', 0):.2f}
Confidence:  {recommended.get('confidence', 'N/A')}
Account:     ${balance:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLAUDE SAYS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{analysis.get('plain_english_summary', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALL TICKERS REVIEWED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        for t in analysis.get("tickers", []):
            e = "✅" if t["verdict"] == "GO" else "❌"
            body += f"\n{e} {t['ticker']} — {t['verdict']}: {t['reason']}"
        body += "\n\nThe bot is now watching for the VWAP reclaim. You'll get another email the moment it enters."
    else:
        subject = f"🤖 Bot Plan — 💤 No trade today | {today}"
        body = f"""Good morning Marcos! Claude finished the analysis.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NO TRADE TODAY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{analysis.get('plain_english_summary', '')}

Cash staying put: ${balance:.2f}"""

    send_alert_email(subject, body)


def send_entry_alert(ticker, shares, entry_price, stop_loss, target_price, vwap, position_size):
    """Alert 2 — Fired the moment the buy order is placed."""
    today   = datetime.now(EASTERN).strftime("%A, %B %d, %Y")
    now_str = datetime.now(EASTERN).strftime("%I:%M:%S %p ET")
    subject = f"🚀 TRADE ENTERED — {ticker} @ ${entry_price:.2f} | {now_str}"
    body = f"""The bot just entered a trade!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRADE ENTERED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticker:      {ticker}
Filled at:   ${entry_price:.2f}
Shares:      {shares}
Position:    ${position_size:.2f}
VWAP:        ${vwap:.2f} ✅ reclaimed with volume

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LEVELS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Target:   ${target_price:.2f} (+20%)
⚠️  Breakeven move triggers at: +10%
💰 Partial exit (half) at: +15%
🛑 Stop loss: ${stop_loss:.2f} (-7%)
⏰ Hard close: 11:00am ET

You'll get an email at partial exit (+15%) and again when the trade closes."""
    send_alert_email(subject, body)


def send_partial_exit_alert(ticker, half_shares, partial_price, entry_price,
                            remaining_shares, new_stop, profit_pct):
    """Alert 3 — Fired when half the position is sold at +15%."""
    now_str = datetime.now(EASTERN).strftime("%I:%M:%S %p ET")
    profit  = (partial_price - entry_price) * half_shares
    subject = f"💰 PARTIAL EXIT — {ticker} +{profit_pct:.1f}% at {now_str}"
    body = f"""The bot just sold half the position at +{profit_pct:.1f}%!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARTIAL EXIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticker:       {ticker}
Sold:         {half_shares} shares @ ${partial_price:.2f}
Gain so far:  +{profit_pct:.1f}% (${profit:+.2f})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STILL IN TRADE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Remaining:    {remaining_shares} shares
Trailing stop now at: ${new_stop:.2f} (5% below high)
Target still: +20% full exit

The bot is letting the rest ride with a trailing stop. You'll get a final email when it closes."""
    send_alert_email(subject, body)


# ============================================================
# STEP 8 — FINAL SUMMARY EMAIL
# ============================================================

def send_summary_email(analysis, trade_result=None, account_balance=100.0):
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
Exit reason:  {exit_reason}
Exit price:   ${exit_price:.2f}
New balance:  ~${account_balance + pnl:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLAUDE'S ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{analysis.get('plain_english_summary', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALL TICKERS REVIEWED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        for t in analysis.get("tickers", []):
            e = "✅" if t["verdict"] == "GO" else "❌"
            body += f"\n{e} {t['ticker']} — {t['verdict']}\n   {t['reason']}\n   Kev check: {t['kev_rule_check']}\n"
    else:
        subject      = f"Trading Bot Summary — {today} | 💤 No Trade Today"
        plain        = analysis.get("plain_english_summary", "") if analysis else "No watchlist email found."
        body = f"""
Good morning Marcos! Here's your trading summary for {today}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NO TRADE TAKEN TODAY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cash preserved: ${account_balance:.2f}

{plain}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REMINDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Send tonight's tickers to: molivera1977@icloud.com
Paste Kev's TikTok transcript in the body.
The bot reads it at 8:45am tomorrow.
"""

    body += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Marcos Trading Bot | Claude Opus AI + Webull MQTT Stream
Railway.app
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    try:
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from":    "Marcos Trading Bot <onboarding@resend.dev>",
            "to":      [SUMMARY_EMAIL],
            "subject": subject,
            "text":    body,
        })
        print(f"✅ Summary email sent!")
    except Exception as e:
        print(f"❌ Email error: {e}")

# ============================================================
# MAIN
# ============================================================

def main():
    now = datetime.now(EASTERN)
    print(f"\n{'='*60}")
    print(f"🤖 MARCOS TRADING BOT STARTING UP")
    print(f"📅 {now.strftime('%A, %B %d, %Y at %I:%M %p ET')}")
    print(f"{'='*60}\n")

    if now.weekday() >= 5:
        print("📅 Weekend — markets closed.")
        return

    # ── Step 1: Read Gmail ─────────────────────────────────
    subject, email_content = read_todays_tickers()
    if not email_content:
        send_summary_email(None, None)
        return

    # ── Step 2: Extract tickers ────────────────────────────
    # Strip reply/forward prefixes before parsing
    clean_subject = re.sub(r'^(FW|FWD|RE):\s*', '', subject.strip(), flags=re.IGNORECASE)
    skip = {"THE", "FOR", "AND", "NOT", "ALL", "DAY", "TOP",
            "NEW", "BIG", "HOT", "PDT", "RE", "AI", "ET", "FW", "FWD"}
    tickers = [t for t in re.findall(r'\b[A-Z]{2,5}\b', clean_subject.upper())
               if t not in skip][:5]
    if not tickers:
        tickers = ["UNKNOWN"]
    print(f"📋 Tickers: {tickers}")

    # ── Step 3: Pre-market data ────────────────────────────
    market_data = []
    for t in tickers:
        if t != "UNKNOWN":
            market_data.append(get_premarket_data(t))
            time.sleep(0.5)

    # ── Step 4: Account balance ────────────────────────────
    balance = get_account_balance()
    print(f"💰 Balance: ${balance:.2f}")

    # ── Step 5: Claude Opus analysis ───────────────────────
    analysis = analyze_with_claude(email_content, market_data, balance)
    if not analysis:
        send_summary_email(None, None, balance)
        return

    # ── Alert 1: Send the plan email right now (~8:55am) ──────
    send_plan_alert(analysis, balance)

    recommended = analysis.get("recommended_trade", {})
    if recommended.get("action") != "BUY":
        print("🔒 Claude says: HOLD CASH today.")
        return  # Plan alert already sent above — no need for a second email

    ticker_to_trade = recommended.get("ticker")
    position_size   = float(recommended.get("position_size_dollars", balance * MAX_POSITION_SIZE))

    # ── Step 6: Open real-time MQTT stream ─────────────────
    stream = WebullStream(tickers)

    # ── Step 7: Wait for VWAP entry ────────────────────────
    entry_price, vwap = wait_for_vwap_entry(ticker_to_trade, stream)

    if not entry_price:
        note = f"\n\nNOTE: {ticker_to_trade} never reclaimed VWAP by 10am. Cash preserved."
        analysis["plain_english_summary"] += note
        send_summary_email(analysis, None, balance)
        stream.stop()
        return

    # Recalculate stop/target from actual VWAP entry
    stop_loss    = round(entry_price * (1 - STOP_LOSS_PCT), 4)
    target_price = round(entry_price * (1 + TARGET_PCT), 4)
    shares       = round(position_size / entry_price, 4) if entry_price > 0 else 0

    print(f"\n{'='*60}")
    print(f"🎯 TRADE PLAN:")
    print(f"   Ticker:  {ticker_to_trade}")
    print(f"   VWAP:    ${vwap:.2f}")
    print(f"   Entry:   ${entry_price:.2f}")
    print(f"   Shares:  {shares}")
    print(f"   Target:  ${target_price:.2f} (+{TARGET_PCT*100:.0f}%)")
    print(f"   Stop:    ${stop_loss:.2f} (-{STOP_LOSS_PCT*100:.0f}%)")
    print(f"   Size:    ${position_size:.2f}")
    print(f"{'='*60}\n")

    # ── Step 8: Execute ────────────────────────────────────
    order_id, stop_order_id = execute_trade(ticker_to_trade, shares, entry_price, stop_loss, target_price)
    if not order_id:
        send_summary_email(analysis, None, balance)
        stream.stop()
        return

    # ── Alert 2: Trade entered! ────────────────────────────
    send_entry_alert(ticker_to_trade, shares, entry_price,
                     stop_loss, target_price, vwap, position_size)

    # ── Step 9: Monitor with real-time stream ──────────────
    trade_result = monitor_trade(
        ticker_to_trade, shares,
        entry_price, target_price, stop_loss,
        stream, stop_order_id
    )

    # ── Step 10: Send summary + cleanup ───────────────────
    stream.stop()
    new_balance = get_account_balance()
    send_summary_email(analysis, trade_result, new_balance)

    pnl = trade_result.get("profit_loss", 0)
    print(f"\n{'='*60}")
    print(f"✅ SESSION COMPLETE")
    print(f"   Result:  ${pnl:+.2f} ({trade_result.get('profit_loss_pct', 0):+.1f}%)")
    print(f"   Reason:  {trade_result.get('exit_reason')}")
    print(f"   Balance: ${new_balance:.2f}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
