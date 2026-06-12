"""
╔══════════════════════════════════════════════════════════════╗
║           MARCOS TRADING BOT — Powered by Claude AI          ║
║           Built for Kev's Momentum Watchlist System          ║
║           Runs daily 8:45am ET on Railway.app                ║
╚══════════════════════════════════════════════════════════════╝

HOW IT WORKS:
1. Every weekday at 8:45am ET this script wakes up automatically
2. Reads your iCloud email (molivera1977@icloud.com) for Kev's tickers
3. Pulls live pre-market data from Webull OpenAPI v2
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
  WEBULL_ACCOUNT_ID     = your Webull account ID
  WEBULL_ACCESS_TOKEN   = your Webull access token (run webull_setup.py once to get this)
  EMAIL_ADDRESS         = molivera1977@icloud.com
  EMAIL_APP_PASSWORD    = your iCloud app-specific password
  ANTHROPIC_API_KEY     = your Claude API key
  RESEND_API_KEY        = your Resend.com API key
  SUMMARY_EMAIL         = molivera1977@gmail.com
"""

import os
import re
import csv
import sys
import signal
import imaplib
import email
import json
import time
import uuid
import hashlib
import hmac
import base64
import socket
import pathlib
import threading
import requests
import anthropic
import resend
import yfinance as yf
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import pytz

# Official Webull OpenAPI Python SDK
try:
    from webull.core.client import ApiClient
    from webull.trade.trade_client import TradeClient
    from webull.data.data_client import DataClient as WebullDataClient
    from webull.data.data_streaming_client import DataStreamingClient as WebullStreamingClient
    WEBULL_SDK_AVAILABLE = True
except ImportError:
    WEBULL_SDK_AVAILABLE = False
    WebullDataClient = None
    WebullStreamingClient = None
    print("⚠️  webull-openapi-python-sdk not installed — trading disabled")

# ============================================================
# CONFIGURATION
# ============================================================

WEBULL_APP_KEY      = os.environ.get("WEBULL_APP_KEY", "")
WEBULL_APP_SECRET   = os.environ.get("WEBULL_APP_SECRET", "")
WEBULL_ACCOUNT_ID   = os.environ.get("WEBULL_ACCOUNT_ID", "")
WEBULL_ACCESS_TOKEN = os.environ.get("WEBULL_ACCESS_TOKEN", "")

EMAIL_ADDRESS      = os.environ.get("EMAIL_ADDRESS", "molivera1977@icloud.com")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "")
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
RESEND_API_KEY     = os.environ.get("RESEND_API_KEY", "")
SUMMARY_EMAIL      = os.environ.get("SUMMARY_EMAIL", "molivera1977@gmail.com")
SCREENER_URL       = os.environ.get("SCREENER_URL", "").rstrip("/")
DASHBOARD_SECRET   = os.environ.get("DASHBOARD_SECRET", "marcos2026")

# iCloud IMAP (reading only — sending is via Resend API over HTTPS)
IMAP_SERVER = "imap.mail.me.com"
IMAP_PORT   = 993

# Webull production endpoints (from official SDK docs)
TRADING_HOST = "api.webull.com"
MARKET_HOST  = "api.webull.com"   # Server-to-Server market data also on api.webull.com

# SDK token file lives here — pre-populated from WEBULL_ACCESS_TOKEN env var each run
WEBULL_TOKEN_DIR = "/tmp/webull_token"

def _pre_populate_webull_token():
    """
    Write WEBULL_ACCESS_TOKEN from env into the SDK's token file BEFORE initializing
    the client.  When the SDK calls create_token(existing_token) the Webull server
    validates it and returns status=NORMAL immediately — no PENDING wait, no need
    to approve in the Webull app every morning.
    """
    if not WEBULL_ACCESS_TOKEN:
        return
    try:
        import pathlib
        token_dir = pathlib.Path(WEBULL_TOKEN_DIR)
        token_dir.mkdir(parents=True, exist_ok=True)
        token_file = token_dir / "token.txt"
        # Expires 14 days from now (ms) — SDK overwrites this after a successful init
        expires_ms = int(time.time() * 1000) + (14 * 24 * 3600 * 1000)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(WEBULL_ACCESS_TOKEN + "\n")
            f.write(str(expires_ms) + "\n")
            f.write("NORMAL\n")
        print(f"📝 Pre-loaded access token into SDK cache")
    except Exception as e:
        print(f"⚠️  Could not pre-load token file: {e}")

def _make_webull_client():
    """Initialize the official Webull SDK client, reusing the saved access token."""
    if not WEBULL_SDK_AVAILABLE:
        return None, None
    try:
        # Step 1: Write our existing token to file so SDK skips the PENDING flow
        _pre_populate_webull_token()

        # Step 2: Build client — set token dir BEFORE TradeClient triggers init_token()
        # token_check_duration_seconds=60 means we give up fast if somehow PENDING
        api_client = ApiClient(WEBULL_APP_KEY, WEBULL_APP_SECRET, "us",
                               token_check_duration_seconds=60,
                               token_check_interval_seconds=5)
        api_client.set_token_dir(WEBULL_TOKEN_DIR)  # must be before TradeClient()
        api_client.add_endpoint("us", TRADING_HOST)
        trade_client = TradeClient(api_client)       # triggers init_token() internally
        print("✅ Webull SDK client initialized")
        return api_client, trade_client
    except Exception as e:
        print(f"⚠️  Webull SDK init error: {e}")
        return None, None


def _make_data_client():
    """Initialize the Webull DataClient for market screening."""
    if not WEBULL_SDK_AVAILABLE or WebullDataClient is None:
        return None, None
    try:
        _pre_populate_webull_token()
        api_client = ApiClient(WEBULL_APP_KEY, WEBULL_APP_SECRET, "us",
                               token_check_duration_seconds=60,
                               token_check_interval_seconds=5)
        api_client.set_token_dir(WEBULL_TOKEN_DIR)
        api_client.add_endpoint("us", TRADING_HOST)
        data_client = WebullDataClient(api_client)
        print("✅ Webull DataClient initialized")
        return api_client, data_client
    except Exception as e:
        print(f"⚠️  Webull DataClient init error: {e}")
        return None, None

_cached_data_client = None   # reused across calls to avoid reinit overhead

def _get_data_client():
    """Return a cached DataClient, initializing once per process."""
    global _cached_data_client
    if _cached_data_client is None:
        _, _cached_data_client = _make_data_client()
    return _cached_data_client

# Trading rules
MAX_POSITION_SIZE     = 0.70   # Max 70% of account on single trade (HIGH confidence)
POSITION_SIZE_MEDIUM  = 0.50   # 50% for MEDIUM confidence
POSITION_SIZE_LOW     = 0.30   # 30% for LOW confidence
STOP_LOSS_PCT         = 0.07   # 7% initial stop loss
TARGET_PCT            = 0.20   # 20% full profit target
PARTIAL_EXIT_PCT      = 0.15   # Sell half at 15% gain
BREAKEVEN_TRIGGER_PCT = 0.10   # Move stop to breakeven at 10% gain
TRAIL_PCT             = 0.05   # Trail 5% below highest after partial exit
VWAP_ENTRY_TIMEOUT    = 10     # Give up on VWAP entry after 10:30am ET
VWAP_ENTRY_TIMEOUT_MIN = 30   # minute component of cutoff
TRADE_WINDOW_END_HOUR = 11     # Force close all positions by 11am ET
ENTRY_LIMIT_BUFFER    = 0.01   # Limit buy 1% above VWAP reclaim — caps slippage on small floats
EARLY_FADE_SECS       = 120    # If price drops below VWAP within 2 min of entry, exit immediately
SPY_BEAR_SKIP_PCT     = -1.0   # Skip the day entirely if SPY pre-market < -1%
MAX_SPREAD_PCT        = 0.015  # Skip entry if bid-ask spread > 1.5% of ask price
VWAP_VOL_MULTIPLIER   = 1.5    # Require 1.5× average minute volume for VWAP reclaim confirmation
TOKEN_EXPIRY_WARN_DAYS = 7     # Email warning when Webull token expires within 7 days
LOG_FILE              = "/tmp/trade_log.csv"
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
EASTERN = pytz.timezone("America/New_York")

# Sector → ETF mapping for sector-level market context
SECTOR_ETFS = {
    "Healthcare":              "XLV",
    "Biotechnology":           "XBI",
    "Technology":              "XLK",
    "Financial Services":      "XLF",
    "Financial":               "XLF",
    "Energy":                  "XLE",
    "Consumer Cyclical":       "XLY",
    "Consumer Defensive":      "XLP",
    "Industrials":             "XLI",
    "Basic Materials":         "XLB",
    "Real Estate":             "XLRE",
    "Utilities":               "XLU",
    "Communication Services":  "XLC",
}

# Global — populated when a trade is entered so SIGTERM handler can alert
_open_trade: dict = {}


def _sigterm_handler(signum, frame):
    """
    Called when Railway (or any process manager) sends SIGTERM.
    If a trade is open at the time, sends an emergency alert before exiting
    so the user knows to log into Webull and manage the position manually.
    """
    if _open_trade.get("active"):
        try:
            ticker = _open_trade.get("ticker", "UNKNOWN")
            subj   = f"🚨 BOT KILLED MID-TRADE — CHECK {ticker} POSITION NOW"
            body   = (
                f"Railway killed the trading bot while a position was open!\n\n"
                f"Ticker:  {ticker}\n"
                f"Entry:   ${_open_trade.get('entry_price', 0):.2f}\n"
                f"Shares:  {_open_trade.get('shares', 0)}\n"
                f"Stop:    ${_open_trade.get('stop_loss', 0):.2f}\n"
                f"Target:  ${_open_trade.get('target', 0):.2f}\n\n"
                f"A stop order was placed on Webull before the bot was killed.\n"
                f"Log into Webull immediately and verify it is still active."
            )
            resend.api_key = RESEND_API_KEY
            resend.Emails.send({
                "from":    "Marcos Trading Bot <onboarding@resend.dev>",
                "to":      [SUMMARY_EMAIL],
                "subject": subj,
                "text":    body,
            })
        except Exception:
            pass
    sys.exit(0)

signal.signal(signal.SIGTERM, _sigterm_handler)

# US market holidays 2025–2027 (NYSE schedule)
US_MARKET_HOLIDAYS = {
    # 2025
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    # 2026
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    # 2027
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26",
    "2027-05-31", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
}

# MQTT streaming — Webull pushes prices up to 3x/second
WEBULL_MQTT_HOST  = "stream.webull.com"
WEBULL_MQTT_PORT  = 443          # WebSocket over TLS
MQTT_LOOP_SLEEP   = 0.5          # When streaming: check every 0.5s
POLL_LOOP_SLEEP   = 3            # REST polling interval: check every 3s

# ============================================================
# WEBULL OPENAPI v2 — SIGNATURE & HEADERS
# ============================================================
#
# Signature algorithm (from Webull official open-source SDK):
#   sign_params = {x-app-key, x-timestamp, x-signature-version,
#                  x-signature-algorithm, x-signature-nonce, host}
#                 + any query params (all lowercased keys)
#   body_string = MD5_HEX(compact_json_body).upper()  [POST only]
#   string_to_sign = path + "&" + "&".join(sorted k=v) [+ "&" + body_md5]
#   string_to_sign = URL_encode(string_to_sign)
#   key            = (app_secret + "&").encode()
#   x-signature    = base64( HMAC-SHA1(key, string_to_sign) )
#
# x-app-secret is NOT sent as a header — it is only the HMAC key.

def _webull_headers(method, path, host, query_params=None, body_dict=None):
    """
    Build correct Webull OpenAPI v2 headers with the right signature algorithm.

    api.webull.com      → HMAC-SHA1,   body hashed with MD5
    data-api.webull.com → HMAC-SHA256, body hashed with SHA-256

    Signature construction (from official Webull open-source SDK):
      sign_params = {all signing headers + host} + query_params (lowercase keys)
      body_string = HASH_HEX(compact_json_body).upper()  [POST only]
      string_to_sign = path + "&" + "&".join(sorted k=v) [+ "&" + body_string]
      string_to_sign = URL_encode(string_to_sign, safe='')
      key            = (app_secret + "&").encode()
      x-signature    = base64( HMAC(key, string_to_sign) )
    """
    # Choose algorithm based on host
    _HMAC_SHA1_HOSTS = {"api.webull.com", "events-api.webull.com",
                        "api.webull.hk",  "events-api.webull.hk"}
    if host in _HMAC_SHA1_HOSTS:
        algo_name  = "HMAC-SHA1"
        hmac_algo  = hashlib.sha1
        body_hash  = lambda s: hashlib.md5(s.encode()).hexdigest().upper()
    else:
        algo_name  = "HMAC-SHA256"
        hmac_algo  = hashlib.sha256
        body_hash  = lambda s: hashlib.sha256(s.encode()).hexdigest().upper()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce     = str(uuid.uuid5(uuid.NAMESPACE_URL,
                               socket.gethostname() + str(uuid.uuid1())))

    headers = {
        "Content-Type":          "application/json",
        "x-app-key":             WEBULL_APP_KEY,
        "x-timestamp":           timestamp,
        "x-signature-version":   "1.0",
        "x-signature-algorithm": algo_name,
        "x-signature-nonce":     nonce,
        "x-version":             "v2",
    }
    if WEBULL_ACCESS_TOKEN:
        headers["x-access-token"] = WEBULL_ACCESS_TOKEN

    # Build sign_params: signing headers + host + query params (all lowercase)
    # x-access-token MUST be included in sign_params when present — Webull verifies it
    sign_params = {
        "x-app-key":             WEBULL_APP_KEY,
        "x-timestamp":           timestamp,
        "x-signature-version":   "1.0",
        "x-signature-algorithm": algo_name,
        "x-signature-nonce":     nonce,
        "host":                  host,
    }
    if WEBULL_ACCESS_TOKEN:
        sign_params["x-access-token"] = WEBULL_ACCESS_TOKEN
    if query_params:
        for k, v in query_params.items():
            sign_params[k.lower()] = str(v)

    # Body string: hash of compact JSON, uppercased (POST only)
    body_string = None
    if body_dict is not None:
        body_str    = json.dumps(body_dict, ensure_ascii=False, separators=(',', ':'))
        body_string = body_hash(body_str)

    # Assemble: path & sorted_kv [& body_hash]
    sorted_kv = "&".join(f"{k}={v}" for k, v in sorted(sign_params.items()))
    s2s       = f"{path}&{sorted_kv}"
    if body_string:
        s2s += f"&{body_string}"

    # Percent-encode everything (matches SDK: quote(safe=''))
    s2s = quote(s2s, safe='')

    # HMAC with (app_secret + "&") as key, base64-encoded
    key = (WEBULL_APP_SECRET + "&").encode()
    h   = hmac.new(key, s2s.encode(), hmac_algo)
    headers["x-signature"] = base64.b64encode(h.digest()).decode()

    return headers


def _post(path, body_dict, host=None):
    """POST to Webull trading API."""
    if host is None:
        host = TRADING_HOST
    url     = f"https://{host}{path}"
    headers = _webull_headers("POST", path, host, body_dict=body_dict)
    body    = json.dumps(body_dict, ensure_ascii=False, separators=(',', ':'))
    return requests.post(url, headers=headers, data=body, timeout=10)


def _get(path, query_params=None, host=None):
    """GET from Webull API."""
    if host is None:
        host = TRADING_HOST
    url     = f"https://{host}{path}"
    headers = _webull_headers("GET", path, host, query_params=query_params)
    return requests.get(url, headers=headers, params=query_params, timeout=10)


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
        """Streaming disabled — Webull streaming token stays PENDING (not enabled for this key).
        Using fast REST polling instead."""
        self.connected = False
        print(f"📊 Using {POLL_LOOP_SLEEP}s REST polling for price updates")

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
                self.client.disconnect()
            except Exception:
                pass

# ============================================================
# STEP 1 — READ ICLOUD EMAIL FOR KEV'S TICKERS
# ============================================================

def read_todays_tickers():
    print("📧 Checking iCloud email for tonight's watchlist...")
    try:
        import socket
        socket.setdefaulttimeout(20)   # 20s timeout on all socket ops including IMAP
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        mail.select("inbox")

        since_date = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")

        # Fetch ALL emails in last 48h — score every one, pick the best
        _, all_msgs = mail.search(None, f'(SINCE "{since_date}")')
        all_ids = all_msgs[0].split() if all_msgs[0] else []
        if not all_ids:
            print("⚠️  No recent emails found.")
            return None, None

        print(f"   Found {len(all_ids)} email(s) in last 48h — scoring all of them...")
        candidates = all_ids  # score every email, no cap

        best_subject, best_content = "", ""
        best_score = -1
        best_id    = None

        today_et    = datetime.now(EASTERN).date()
        yesterday_et = today_et - timedelta(days=1)

        # ── Pass 1: score by SUBJECT + DATE headers (fast, reliable on iCloud) ──
        for msg_id in candidates:
            try:
                _, hdr_data = mail.fetch(msg_id,
                    "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
                raw_h = None
                for part in hdr_data:
                    if isinstance(part, tuple):
                        raw_h = part[1]; break
                if raw_h is None:
                    raw_h = max((p for p in hdr_data if isinstance(p, bytes)),
                                key=len, default=b"")
                hdr_msg = email.message_from_bytes(raw_h)
                subj_c  = hdr_msg.get("subject", "") or ""
                from_c  = hdr_msg.get("from", "") or ""
                date_str = hdr_msg.get("date", "") or ""

                # Recency bonus: heavily prefer today's and yesterday's emails so
                # an old email with more tickers never outranks a fresh one.
                recency_bonus = 0
                try:
                    from email.utils import parsedate_to_datetime
                    sent_dt   = parsedate_to_datetime(date_str)
                    sent_date = sent_dt.astimezone(EASTERN).date()
                    if sent_date == today_et:
                        recency_bonus = 20   # today always wins
                    elif sent_date == yesterday_et:
                        recency_bonus = 10   # yesterday beats anything older
                except Exception:
                    pass

                skip_score = {"THE","FOR","AND","NOT","ALL","DAY","TOP","NEW","BIG",
                              "HOT","PDT","RE","AI","ET","FW","FWD","TO","IN","UP",
                              "AM","PM","BODY","SUBJECT","FROM","DATE"}
                subj_upper = subj_c.upper()
                dollar_hits   = len(re.findall(r'\$[A-Z]{2,5}\b', subj_upper))
                watchlist_hits = len(re.findall(
                    r'\bWATCHLIST\b|\bPICK\b|\bTICKER\b|\bSETUP\b|\bPLAY\b', subj_upper))
                caps_hits = len([t for t in re.findall(r'\b[A-Z]{2,5}\b', subj_upper)
                                 if t not in skip_score])
                score = dollar_hits * 5 + watchlist_hits * 3 + min(caps_hits, 10) + recency_bonus
                print(f"   [{msg_id.decode() if isinstance(msg_id,bytes) else msg_id}] "
                      f"score={score:2d} (recency+{recency_bonus})  subj={subj_c[:60]!r}")

                if score > best_score:
                    best_score   = score
                    best_subject = subj_c
                    best_id      = msg_id

            except Exception as ex_inner:
                print(f"   ⚠️  Header fetch failed for {msg_id}: {ex_inner}")

        # ── Pass 2: fetch full body ONLY for the winning email ────────────────
        if best_id is not None:
            try:
                _, body_data = mail.fetch(best_id, "(RFC822)")
                raw_b = None
                for part in body_data:
                    if isinstance(part, tuple):
                        raw_b = part[1]; break
                if raw_b is None:
                    raw_b = max((p for p in body_data if isinstance(p, bytes)),
                                key=len, default=b"")
                msg_b  = email.message_from_bytes(raw_b)
                body_c = ""
                if msg_b.is_multipart():
                    for part in msg_b.walk():
                        if part.get_content_type() == "text/plain":
                            payload = part.get_payload(decode=True)
                            if isinstance(payload, bytes):
                                body_c = payload.decode("utf-8", errors="ignore")
                            break
                else:
                    payload = msg_b.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body_c = payload.decode("utf-8", errors="ignore")
                    elif isinstance(payload, str):
                        body_c = payload
                best_content = f"{best_subject}\n\n{body_c}"
            except Exception as ex_body:
                print(f"   ⚠️  Full body fetch failed: {ex_body}")
                best_content = best_subject  # subject alone is enough for tickers

        if best_content:
            print(f"✅ Best watchlist email (score={best_score}): {best_subject[:80]!r}")
            mail.logout()
            return best_subject, best_content

        # Hard fallback: return absolute latest email raw
        print("⚠️  No scored email found — using absolute latest email")
        latest = all_ids[-1]
        _, msg_data = mail.fetch(latest, "(RFC822)")

        # iCloud returns a flat list of bytes; Gmail returns a list of tuples.
        raw_email = None
        for part in msg_data:
            if isinstance(part, tuple):
                raw_email = part[1]
                break
        if raw_email is None:
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
        print(f"✅ Found watchlist email (fallback): {subject}")
        mail.logout()
        return subject, full_content

    except Exception as e:
        print(f"❌ iCloud email error: {e}")
        return None, None

# ============================================================
# STEP 2 — WEBULL MARKET DATA + ACCOUNT
# ============================================================

def get_market_context():
    """
    Fetch SPY pre-market data to gauge overall market direction.
    Passed to Claude so it can be more cautious on bearish market days.
    """
    print("🌎 Checking SPY pre-market direction...")
    try:
        q = _get_webull_quote("SPY")
        pre_price  = q.get("pre_market_price") or q.get("last_price") or 0
        pre_change = q.get("pre_market_change_pct") or q.get("change_ratio") or 0
        prev_close = q.get("prev_close") or 0

        # Sanity check — SPY never moves more than 5% pre-market; yfinance ghost data
        if abs(pre_change) > 5:
            print(f"⚠️  SPY pre-market change {pre_change:+.1f}% looks wrong — clamping to 0")
            pre_change = 0

        pre_change = round(pre_change, 2)

        if pre_change >= 0.5:
            sentiment = "BULLISH"
        elif pre_change <= -0.5:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"

        print(f"   SPY: ${pre_price:.2f}  {pre_change:+.2f}%  → {sentiment}")
        return {
            "spy_price":      pre_price,
            "spy_change_pct": pre_change,
            "spy_prev_close": prev_close,
            "sentiment":      sentiment,
        }
    except Exception as e:
        print(f"⚠️  SPY market context error: {e}")
        return {"spy_price": "N/A", "spy_change_pct": 0,
                "sentiment": "UNKNOWN", "error": str(e)}


def get_news_catalyst(ticker):
    """
    Fetch the most recent news headlines for a ticker via yfinance.
    Claude uses these to judge whether a gap has a real catalyst behind it.
    """
    try:
        news  = yf.Ticker(ticker).news or []
        lines = []
        for item in news[:4]:
            title = item.get("title", "")
            ts    = item.get("providerPublishTime", 0)
            if ts:
                age = datetime.now() - datetime.fromtimestamp(ts)
                hrs = int(age.total_seconds() / 3600)
                tag = f"{hrs}h ago" if hrs < 24 else f"{hrs//24}d ago"
            else:
                tag = "recent"
            if title:
                lines.append(f"[{tag}] {title}")
        return lines if lines else ["No recent news found"]
    except Exception:
        return ["News unavailable"]


def get_premarket_data(ticker):
    """
    Fetch pre-market quote for ticker.
    Live price/change/volume from Webull REST (real-time, no delay).
    Float, avg-volume, market-cap from yfinance (static fundamentals — updated daily).
    """
    print(f"📊 Fetching pre-market data for {ticker}...")

    # ── Live quote from Webull (real-time) ───────────────────
    wb = _get_webull_quote(ticker)
    pre_price  = wb.get("pre_market_price") or wb.get("last_price") or "N/A"
    pre_change = wb.get("pre_market_change_pct", "N/A")
    pre_vol    = wb.get("volume", "N/A")
    prev_close = wb.get("prev_close", "N/A")
    source     = "Webull live"

    # ── Static fundamentals from yfinance (float, avg vol, mkt cap, short interest) ──
    avg_vol    = "N/A"
    mkt_cap    = "N/A"
    float_sh   = "N/A"
    short_pct  = "N/A"
    sector     = "N/A"
    try:
        info      = yf.Ticker(ticker).info or {}
        avg_vol   = info.get("averageVolume10days") or info.get("averageVolume") or "N/A"
        mkt_cap   = info.get("marketCap") or "N/A"
        float_sh  = info.get("floatShares") or info.get("sharesOutstanding") or "N/A"
        sector    = info.get("sector") or info.get("industry") or "N/A"
        raw_short = info.get("shortPercentOfFloat")
        if raw_short is not None:
            short_pct = f"{round(raw_short * 100 if raw_short < 1 else raw_short, 1)}%"
        # Fall back to yfinance price only if Webull returned nothing
        if pre_price == "N/A" or pre_price == 0:
            pre_price  = info.get("preMarketPrice") or info.get("regularMarketPrice") or "N/A"
            pre_change = info.get("preMarketChangePercent") or "N/A"
            if isinstance(pre_change, (int, float)) and pre_change != "N/A":
                pre_change = round(pre_change * 100 if abs(pre_change) < 1 else pre_change, 2)
            prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose") or "N/A"
            pre_vol    = info.get("preMarketVolume") or info.get("regularMarketVolume") or "N/A"
            source     = "yfinance fallback"
    except Exception as e:
        print(f"⚠️  yfinance fundamentals error for {ticker}: {e}")

    # ── Pre-market volume trend (Webull 15-min bars) ──────────
    vol_trend = get_premarket_volume_trend(ticker)

    # ── Sector ETF direction ───────────────────────────────────
    sector_etf = get_sector_etf_direction(sector)

    print(f"   {ticker} [{source}]: pre=${pre_price}  prev_close=${prev_close}  chg={pre_change}%  short={short_pct}")
    return {
        "ticker":               ticker,
        "premarket_price":      pre_price,
        "premarket_change_pct": pre_change,
        "premarket_volume":     pre_vol,
        "previous_close":       prev_close,
        "avg_volume":           avg_vol,
        "float_shares":         float_sh,
        "market_cap":           mkt_cap,
        "short_interest":       short_pct,
        "sector":               sector,
        "vol_trend":            vol_trend,
        "sector_etf":           sector_etf,
    }


def scan_morning_gappers():
    """
    Use Webull's screener to find pre-market top gainers and unusual-volume stocks.
    Returns a list of candidate dicts (symbol, change_pct, price, relative_volume, market_cap).
    Called at bot startup (~8:45am) so Claude can compare these against Kev's picks.
    """
    print("🔍 Scanning Webull screener for morning gappers...")
    _, data_client = _make_data_client()
    if not data_client:
        print("⚠️  DataClient unavailable — skipping gapper scan")
        return []

    gappers = {}   # symbol -> dict, deduplicated

    # ── Pre-market top gainers ────────────────────────────────────────────────
    try:
        res = data_client.screener.get_gainers_losers(
            rank_type="PRE_MARKET",
            category="US_STOCK",
            sort_by="CHANGE_RATIO",
            direction="DESC",
            page_size=30,
        )
        if res.status_code == 200:
            raw = res.json()
            items = raw if isinstance(raw, list) else raw.get("data", raw.get("items", []))
            for item in items:
                sym    = item.get("symbol", "")
                chg    = float(item.get("change_ratio") or 0) * 100   # decimal → pct
                price  = float(item.get("price") or item.get("close") or 0)
                mktcap = float(item.get("market_value") or 0)
                vol    = float(item.get("volume") or 0)
                if not sym or price <= 0:
                    continue
                # Momentum setup: price $1–$30, >8% pre-market gap, not tiny cap
                if price < 1 or price > 30:
                    continue
                if chg < 8:
                    continue
                gappers[sym] = {
                    "symbol": sym, "change_pct": round(chg, 2),
                    "price": price, "market_cap": mktcap,
                    "premarket_volume": vol, "relative_volume": None,
                    "source": "pre_market_gainer",
                }
            print(f"   Pre-market gainers: {len(gappers)} candidates after filter")
        else:
            print(f"⚠️  Gainers screener error: {res.status_code}")
    except Exception as e:
        print(f"⚠️  Gainers screener exception: {e}")

    # ── Unusual relative volume (10-day) — catches late gappers ──────────────
    try:
        res = data_client.screener.get_most_active(
            category="US_STOCK",
            rank_type="RELATIVE_VOLUME_10D",
            sort_by="RELATIVE_VOLUME_10D",
            direction="DESC",
            page_size=30,
        )
        if res.status_code == 200:
            raw = res.json()
            items = raw if isinstance(raw, list) else raw.get("data", raw.get("items", []))
            new_from_vol = 0
            for item in items:
                sym     = item.get("symbol", "")
                chg     = float(item.get("change_ratio") or 0) * 100
                price   = float(item.get("price") or item.get("close") or 0)
                mktcap  = float(item.get("market_value") or 0)
                rel_vol = float(item.get("relative_volume_10d") or 0)
                vol     = float(item.get("volume") or 0)
                if not sym or price <= 0:
                    continue
                if price < 1 or price > 30:
                    continue
                if rel_vol < 3.0:   # at least 3× 10-day average volume
                    continue
                if sym in gappers:
                    gappers[sym]["relative_volume"] = rel_vol
                else:
                    if chg >= 5:    # lower bar for volume-driven candidates
                        gappers[sym] = {
                            "symbol": sym, "change_pct": round(chg, 2),
                            "price": price, "market_cap": mktcap,
                            "premarket_volume": vol, "relative_volume": rel_vol,
                            "source": "unusual_volume",
                        }
                        new_from_vol += 1
            print(f"   Relative-volume adds: {new_from_vol} more candidates")
        else:
            print(f"⚠️  Volume screener error: {res.status_code}")
    except Exception as e:
        print(f"⚠️  Volume screener exception: {e}")

    # ── Float check via yfinance — filter out large-float stocks ─────────────
    # Webull screener doesn't return float, so we check each candidate separately.
    # Small float (<50M) + big gap + volume = the real momentum setup.
    print(f"   Checking float for {len(gappers)} candidates...")
    float_checked = []
    for sym, g in gappers.items():
        try:
            import yfinance as yf
            info = yf.Ticker(sym).info or {}
            float_shares = info.get("floatShares") or info.get("sharesOutstanding") or 0
            g["float_shares"] = float_shares
            float_m = float_shares / 1_000_000
            if float_shares == 0:
                # No float data — keep the candidate but note it
                g["float_label"] = "float N/A"
                float_checked.append(g)
            elif float_shares <= 50_000_000:
                g["float_label"] = f"{float_m:.1f}M float"
                float_checked.append(g)
                print(f"   ✅ {sym}: +{g['change_pct']}% | {g['float_label']} ← SMALL FLOAT")
            else:
                print(f"   ❌ {sym}: skipped — {float_m:.0f}M float (too large)")
            time.sleep(0.3)   # avoid yfinance rate-limit
        except Exception as e:
            g["float_shares"] = 0
            g["float_label"] = "float N/A"
            float_checked.append(g)
            print(f"   ⚠️  {sym}: float check failed ({e}) — keeping candidate")

    # Score: reward big gap % on tiny float
    # score = change_pct / float_in_millions  (higher = better)
    def _gapper_score(g):
        f = g.get("float_shares") or 0
        float_m = f / 1_000_000 if f > 0 else 25   # assume 25M if unknown
        return g["change_pct"] / max(float_m, 0.1)

    results = sorted(float_checked, key=_gapper_score, reverse=True)[:10]
    print(f"✅ Morning gapper scan complete — {len(results)} small-float candidates: "
          f"{[r['symbol'] for r in results]}")
    return results


def get_account_balance():
    """Get available cash using the official Webull SDK."""
    _, trade_client = _make_webull_client()
    if trade_client:
        try:
            # Step 1: account list gives us the account ID (not balance)
            res = trade_client.account_v2.get_account_list()
            if res.status_code == 200:
                accounts = res.json()
                if isinstance(accounts, list) and accounts:
                    global WEBULL_ACCOUNT_ID
                    WEBULL_ACCOUNT_ID = accounts[0].get("account_id", WEBULL_ACCOUNT_ID)
                    print(f"✅ Account ID: {WEBULL_ACCOUNT_ID}")
            else:
                print(f"⚠️  Account list error: {res.status_code} {res.text[:200]}")

            # Step 2: dedicated balance endpoint
            if WEBULL_ACCOUNT_ID:
                bal = trade_client.account_v2.get_account_balance(WEBULL_ACCOUNT_ID)
                if bal.status_code == 200:
                    data = bal.json()
                    # Unwrap nested "data" if present
                    if isinstance(data.get("data"), dict):
                        data = data["data"]
                    # Top-level field names confirmed from API response
                    cash = float(data.get("total_cash_balance") or 0)
                    # Fall through to per-currency assets if top-level is 0
                    if not cash:
                        assets = data.get("account_currency_assets") or []
                        for asset in assets:
                            if asset.get("currency") == "USD":
                                cash = float(asset.get("cash_balance") or 0)
                                break
                    if cash and cash > 0:
                        print(f"💰 Balance: ${cash:.2f}")
                        return cash
                    # API returned 0 — likely a permissions limitation
                    print("⚠️  Webull API returned $0 balance (permissions) — using ACCOUNT_BALANCE env var")
                else:
                    print(f"⚠️  Balance endpoint error: {bal.status_code} {bal.text[:200]}")

        except Exception as e:
            print(f"⚠️  Balance SDK error: {e}")

    # Fallback to manually set env var
    manual = float(os.environ.get("ACCOUNT_BALANCE", "0"))
    if manual:
        print(f"💰 Using manual balance: ${manual:.2f}")
        return manual
    print("⚠️  Could not read real balance — defaulting to $100")
    return 100.0


def _get_price_rest(ticker) -> float:
    """REST fallback for current price when MQTT is unavailable. Uses SDK."""
    q = _get_webull_quote(ticker)
    return q.get("last_price", 0) or 0


def _get_webull_quote(ticker) -> dict:
    """
    Fetch a live real-time quote via the official Webull SDK (properly authenticated).
    Falls back to empty dict on any error so callers can fall back to yfinance.
    """
    try:
        dc = _get_data_client()
        if not dc:
            return {}

        resp = dc.market_data.get_snapshot(
            symbols=ticker,
            category="US_STOCK",
            extend_hour_required=True,
        )
        if resp.status_code != 200:
            print(f"⚠️  Webull snapshot {resp.status_code} for {ticker}")
            return {}

        raw = resp.json()
        # SDK may return a list directly, a {"data": [...]}, or {"data": {"items": [...]}}
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

        last   = float(d.get("close")     or d.get("last_price")   or d.get("lastPrice")   or d.get("c") or 0)
        bid    = float(d.get("bid_price")  or d.get("bidPrice")     or d.get("bid")         or 0)
        ask    = float(d.get("ask_price")  or d.get("askPrice")     or d.get("ask")         or 0)
        vol    = float(d.get("volume")     or d.get("v")            or 0)
        pclose = float(d.get("pre_close")  or d.get("preClose")     or last                 or 0)
        chg_r  = float(d.get("change_ratio")  or d.get("changeRatio")   or 0)
        pre_p  = float(d.get("pre_market_price")        or d.get("preMarketPrice")        or last or 0)
        pre_r  = float(d.get("pre_market_change_ratio") or d.get("preMarketChangeRatio")  or chg_r or 0)

        if abs(pre_r) < 1 and pre_r != 0:
            pre_r = pre_r * 100

        return {
            "last_price":            last,
            "bid":                   bid,
            "ask":                   ask,
            "volume":                vol,
            "prev_close":            pclose,
            "change_ratio":          round(chg_r * 100 if abs(chg_r) < 1 else chg_r, 2),
            "pre_market_price":      pre_p,
            "pre_market_change_pct": round(pre_r, 2),
        }
    except Exception as e:
        print(f"⚠️  Webull quote error for {ticker}: {e}")
        return {}


def check_webull_connection() -> bool:
    """
    Quick health check — only meaningful during the trading window (8-10am ET).
    Outside that window, Webull's market-data endpoint returns errors normally
    (no active session), so we skip the check to avoid false-alarm emails.
    """
    et_now = datetime.now(pytz.timezone("America/New_York"))
    if not (8 <= et_now.hour < 13):
        print(f"🔗 Webull health check skipped (outside trading window — {et_now.strftime('%H:%M')} ET)")
        return True

    print("🔗 Checking Webull API connection...")
    try:
        q = _get_webull_quote("SPY")
        price = q.get("last_price", 0) if q else 0
        if price > 0:
            print(f"✅ Webull API healthy — SPY @ ${price:.2f}")
            return True
        print("⚠️  Webull API returned no data during trading window")
    except Exception as e:
        print(f"⚠️  Webull connection error: {e}")

    send_alert_email(
        "⚠️ Webull API health check failed — bot may not trade today",
        "The bot could not reach the Webull API at startup.\n\n"
        "Possible causes:\n"
        "- Access token expired (check Railway env vars)\n"
        "- Webull API outage\n"
        "- Network issue on Railway\n\n"
        "The bot will continue running but order placement may fail. "
        "Check your Webull credentials and redeploy if needed."
    )
    return False


def get_premarket_volume_trend(ticker) -> dict:
    """
    Fetch 15-minute pre-market bars via the Webull SDK and determine if volume is
    accelerating (picking up into the open) or fading (dying off).
    Returns a dict with trend label and ratio vs earlier bars.
    """
    try:
        dc = _get_data_client()
        if not dc:
            return {"trend": "N/A", "ratio": None}

        resp = dc.market_data.get_history_bar(
            symbol=ticker,
            category="US_STOCK",
            timespan="M15",
            count="12",
            trading_sessions="PRE",
        )
        if resp.status_code != 200:
            return {"trend": "N/A", "ratio": None}

        raw  = resp.json()
        if isinstance(raw, list):
            bars = raw
        else:
            data = raw.get("data", {}) if isinstance(raw, dict) else {}
            bars = data.get("items", data) if isinstance(data, dict) else data
        if not isinstance(bars, list) or len(bars) < 3:
            return {"trend": "N/A", "ratio": None}

        vols = [float(b.get("volume") or b.get("v") or 0) for b in bars]
        early_avg = sum(vols[:len(vols)//2]) / max(len(vols)//2, 1)
        late_avg  = sum(vols[len(vols)//2:]) / max(len(vols) - len(vols)//2, 1)

        if early_avg == 0:
            return {"trend": "N/A", "ratio": None}

        ratio = late_avg / early_avg
        if ratio >= 1.3:
            trend = "ACCELERATING"
        elif ratio <= 0.7:
            trend = "FADING"
        else:
            trend = "FLAT"

        print(f"   {ticker} pre-mkt volume trend: {trend} ({ratio:.1f}× early pace)")
        return {"trend": trend, "ratio": round(ratio, 2)}
    except Exception as e:
        print(f"⚠️  Volume trend error for {ticker}: {e}")
        return {"trend": "N/A", "ratio": None}


def get_sector_etf_direction(sector: str) -> dict:
    """
    Map the stock's sector to its ETF and fetch that ETF's pre-market direction.
    Returns dict with etf ticker, change%, and sentiment.
    ETFs are liquid — yfinance direction signal is reliable even with delay.
    """
    etf = SECTOR_ETFS.get(sector)
    if not etf:
        return {"etf": None, "sector": sector, "change_pct": None, "sentiment": "UNKNOWN"}
    try:
        info     = yf.Ticker(etf).info or {}
        chg      = info.get("preMarketChangePercent") or info.get("regularMarketChangePercent") or 0
        if isinstance(chg, (int, float)) and abs(chg) < 1:
            chg = chg * 100
        chg = round(chg, 2)
        sentiment = "BULLISH" if chg >= 0.3 else "BEARISH" if chg <= -0.3 else "NEUTRAL"
        print(f"   Sector ETF {etf} ({sector}): {chg:+.2f}% → {sentiment}")
        return {"etf": etf, "sector": sector, "change_pct": chg, "sentiment": sentiment}
    except Exception as e:
        print(f"⚠️  Sector ETF error for {etf}: {e}")
        return {"etf": etf, "sector": sector, "change_pct": None, "sentiment": "UNKNOWN"}


def check_bid_ask_spread(ticker) -> tuple[bool, float]:
    """
    Fetch live bid/ask from Webull and check if the spread is tradeable.
    Returns (ok, spread_pct) — ok=False means spread too wide, skip entry.
    """
    q = _get_webull_quote(ticker)
    bid = q.get("bid", 0)
    ask = q.get("ask", 0)
    if bid <= 0 or ask <= 0:
        print(f"⚠️  {ticker}: could not get bid/ask — assuming spread OK")
        return True, 0.0
    spread_pct = (ask - bid) / ask
    ok = spread_pct <= MAX_SPREAD_PCT
    if ok:
        print(f"✅ {ticker} spread: ${bid:.2f}/${ask:.2f} ({spread_pct*100:.2f}%) — OK")
    else:
        print(f"🚫 {ticker} spread too wide: ${bid:.2f}/${ask:.2f} ({spread_pct*100:.2f}%) > {MAX_SPREAD_PCT*100:.1f}% limit")
    return ok, spread_pct


def get_intraday_bars(ticker, count=30):
    """Fetch 1-minute intraday bars for VWAP calculation. Uses SDK."""
    try:
        dc = _get_data_client()
        if not dc:
            return []
        resp = dc.market_data.get_history_bar(
            symbol=ticker,
            category="US_STOCK",
            timespan="M1",
            count=str(count),
        )
        if resp.status_code != 200:
            print(f"⚠️  Intraday bars {resp.status_code} for {ticker}")
            return []
        raw = resp.json()
        if isinstance(raw, list):
            return raw
        data = raw.get("data", {}) if isinstance(raw, dict) else {}
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items", [])
    except Exception as e:
        print(f"⚠️  Intraday bars error for {ticker}: {e}")
    return []


def calculate_vwap(bars) -> float:
    """Calculate VWAP from 1-minute bars. Handles camelCase and snake_case field names."""
    total_pv, total_vol = 0, 0
    for bar in bars:
        high  = float(bar.get("high")   or bar.get("h") or 0)
        low   = float(bar.get("low")    or bar.get("l") or 0)
        close = float(bar.get("close")  or bar.get("c") or 0)
        vol   = float(bar.get("volume") or bar.get("v") or 0)
        total_pv  += ((high + low + close) / 3) * vol
        total_vol += vol
    return total_pv / total_vol if total_vol > 0 else 0

# ============================================================
# STEP 3 — CLAUDE OPUS ANALYZES THE SETUPS
# ============================================================

def _sanitize_for_prompt(text: str) -> str:
    """Strip characters that cause JSON parse errors when Claude quotes them back."""
    if not text:
        return ""
    # Remove control characters (except tab/newline which are fine in prompts)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Replace backslashes (confuse JSON string escaping)
    text = text.replace('\\', '/')
    # Replace curly quotes and other smart-quote variants with plain apostrophe
    text = text.replace('“', "'").replace('”', "'")
    text = text.replace('‘', "'").replace('’', "'")
    # Collapse excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _repair_json(raw: str) -> dict | None:
    """Try to salvage a truncated or slightly malformed JSON response from Claude."""
    # Already valid?
    try:
        return json.loads(raw)
    except Exception:
        pass
    # Truncated response — find the last complete top-level field and close the object
    # Strategy: find the last '}' before the unterminated field and close cleanly
    try:
        # Find the last well-formed key: up to "plain_english_summary"
        for end_marker in ['"plain_english_summary"', '"recommended_trade"', '"tickers"']:
            idx = raw.rfind(end_marker)
            if idx == -1:
                continue
            # Find the colon after the key
            colon = raw.find(':', idx)
            if colon == -1:
                continue
            # Truncate just before this field and close the JSON
            truncated = raw[:idx].rstrip().rstrip(',') + '\n  "plain_english_summary": "Analysis truncated — check Railway logs."\n}'
            try:
                return json.loads(truncated)
            except Exception:
                continue
    except Exception:
        pass
    return None


def analyze_with_claude(email_content, market_data_list, account_balance,
                        gappers=None, market_context=None):
    print("🧠 Sending data to Claude Opus AI for analysis...")

    def _sector_line(d):
        se = d.get("sector_etf") or {}
        if se.get("etf") and se.get("change_pct") is not None:
            return (f"Sector: {d.get('sector','N/A')} | "
                    f"Sector ETF {se['etf']}: {se['change_pct']:+.2f}% ({se['sentiment']})")
        return f"Sector: {d.get('sector','N/A')}"

    def _vol_trend_line(d):
        vt = d.get("vol_trend") or {}
        if vt.get("trend") and vt["trend"] != "N/A":
            ratio = f" ({vt['ratio']}× early pace)" if vt.get("ratio") else ""
            return f"Pre-mkt Volume Trend: {vt['trend']}{ratio}"
        return "Pre-mkt Volume Trend: N/A"

    market_text = "\n".join([
        f"Ticker: {d['ticker']}\n"
        f"Pre-market Price: ${d['premarket_price']}\n"
        f"Pre-market Change: {d['premarket_change_pct']}%\n"
        f"Pre-market Volume: {d['premarket_volume']}\n"
        f"{_vol_trend_line(d)}\n"
        f"Previous Close: ${d['previous_close']}\n"
        f"10-Day Avg Volume: {d['avg_volume']}\n"
        f"Market Cap: ${d['market_cap']}\n"
        f"Float: {d.get('float_shares', 'N/A')}\n"
        f"Short Interest: {d.get('short_interest', 'N/A')}\n"
        f"{_sector_line(d)}\n"
        f"News/Catalyst:\n" +
        "\n".join(f"  - {h}" for h in d.get('news', ['No news data'])) + "\n"
        for d in market_data_list
    ])

    if gappers:
        gapper_lines = []
        for g in gappers:
            rel       = f"{g['relative_volume']:.1f}x avg vol" if g.get("relative_volume") else "rel vol N/A"
            float_lbl = g.get("float_label", "float N/A")
            news_lines = "\n".join(f"    - {h}" for h in g.get("news", []))
            gapper_lines.append(
                f"  {g['symbol']}: +{g['change_pct']}% pre-mkt | ${g['price']:.2f} | "
                f"{float_lbl} | {rel} | source: {g['source']}"
                + (f"\n  News:\n{news_lines}" if news_lines else "")
            )
        gapper_section = "WEBULL MORNING GAPPER SCAN (small-float pre-market movers):\n" + "\n".join(gapper_lines)
    else:
        gapper_section = "WEBULL MORNING GAPPER SCAN: unavailable (screener did not return data)"

    if market_context:
        spy_chg  = market_context.get("spy_change_pct", 0)
        spy_sent = market_context.get("sentiment", "UNKNOWN")
        spy_line = (f"SPY pre-market: {spy_chg:+.2f}% — market is {spy_sent}. "
                    + ("Be more selective today — market headwinds increase risk on long plays."
                       if spy_sent == "BEARISH" else
                       "Market tailwind — momentum plays have higher follow-through probability."
                       if spy_sent == "BULLISH" else
                       "Market neutral — evaluate each setup on its own merits."))
        market_context_section = f"OVERALL MARKET CONTEXT:\n{spy_line}"
    else:
        market_context_section = "OVERALL MARKET CONTEXT: SPY data unavailable"

    email_safe = _sanitize_for_prompt(email_content)

    prompt = f"""
You are a smart, data-driven, opportunistic momentum trading bot for Marcos Olivera.
Your edge is reading live data fast and acting when the numbers line up.
You are not reckless — but you are not timid either. When the data says go, you go.

Today's date: {datetime.now(EASTERN).strftime("%A, %B %d, %Y")}
Account balance: ${account_balance:.2f}
Market open: 9:30am ET
Entry: VWAP reclaim with volume after open
Trading window: Entry by 10:30am ET, hold until 11:00am max

{market_context_section}

KEV'S WATCHLIST EMAIL/TRANSCRIPT:
{email_safe}

LIVE PRE-MARKET DATA FROM WEBULL (Kev's picks):
{market_text}

{gapper_section}

━━━ HOW TO SCORE EACH SETUP ━━━

Score each candidate on these DATA signals (+1 point each):
  ✦ Float < 10M shares          → tight float, big moves possible
  ✦ Gap 8–50% pre-market        → real momentum, not noise
  ✦ Relative volume ≥ 2x        → real buyers showing up
  ✦ Pre-mkt volume ACCELERATING → buying is building, not fading
  ✦ Short interest > 15%        → squeeze fuel
  ✦ Sector ETF is BULLISH       → wind at its back
  ✦ Price $0.50–$15             → tradeable size on this account
  ✦ News catalyst exists        → bonus conviction (not required)
  ✦ Kev specifically flagged it → expert endorsement

Score 5+ = HIGH confidence → 70% size (${account_balance * 0.70:.2f})
Score 3–4 = MEDIUM confidence → 50% size (${account_balance * 0.50:.2f})
Score 1–2 = LOW confidence → 30% size (${account_balance * 0.30:.2f})

Pick the highest-scoring candidate. If it scores ≥ 1 and clears the hard
NO-GO filters below, TAKE THE TRADE. Do not wait for a perfect score.

━━━ HARD NO-GO (skip only for these) ━━━
  ✗ Active SEC halt or T12 restriction
  ✗ Stock price > full account balance (can't buy 1 share)
  ✗ Gap > 300% pre-market with no volume (halt trap)
  ✗ Active dilution/offering news in the headline
  ✗ Already confirmed gap-and-crap (trading below open immediately)

━━━ MARKET CONTEXT ━━━
  SPY < -1%: take the top-scoring setup at LOW size (30%) — don't skip entirely
  SPY -1% to +1%: MEDIUM sizing on your best setup
  SPY > +1%: full confidence sizing — momentum market, attack it

━━━ KEV'S EMAIL ━━━
  If Kev gave specific break levels → honor them as a bonus signal (+1 to score)
  If his email is commentary/educational → use it as context, not a gate
  The gapper scan is always a valid trade source independent of Kev's email

━━━ CATALYST NOTE ━━━
  News = bonus signal, NOT a requirement. Small-float stocks move on order
  flow, short squeeze, and sector momentum. "No news found" ≠ no trade.
  Only skip on confirmed BAD news (dilution, halt, investigation).

TRADING RULES (bot handles execution):
- Entry: VWAP reclaim with 1.5x volume confirmation
- Stop: 7% below entry
- +10%: stop to breakeven
- +15%: sell half, trail rest
- +20%: full exit
- Hard close: 11:00am ET

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
      "kev_rule_check": "Kev's rule applied or N/A if gapper-only pick"
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
  "plain_english_summary": "Text Marcos. Tell him the pick, why, and what to expect. Be direct and confident."
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

        analysis = _repair_json(raw)
        if analysis:
            print("✅ Claude Opus analysis complete!")
            return analysis

        print(f"❌ Claude JSON parse failed. Raw response (first 500 chars):\n{raw[:500]}")
        return None
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

        if now.hour > VWAP_ENTRY_TIMEOUT or (now.hour == VWAP_ENTRY_TIMEOUT and now.minute >= VWAP_ENTRY_TIMEOUT_MIN):
            print(f"⏰ {ticker} never reclaimed VWAP by 10:30am. Holding cash.")
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
            last_vol = float(cached_bars[-1].get("volume") or
                             cached_bars[-1].get("v") or 0)
            avg_vol  = sum(float(b.get("volume") or b.get("v") or 0)
                          for b in cached_bars) / len(cached_bars)
            if last_vol >= avg_vol * VWAP_VOL_MULTIPLIER:
                print(f"✅ VWAP reclaim confirmed! ${current_price:.2f} > VWAP ${cached_vwap:.2f} "
                      f"with {last_vol/avg_vol:.1f}× avg volume")
                return current_price, cached_vwap
            else:
                print(f"⚠️  Above VWAP but volume light ({last_vol/avg_vol:.1f}× avg — need {VWAP_VOL_MULTIPLIER}×). Waiting...")

        time.sleep(stream.loop_sleep())

# ============================================================
# STEP 5 — EXECUTE TRADE VIA WEBULL OPENAPI v2
# ============================================================
#
# All orders use the new /openapi/trade/stock/order/place endpoint.
# Orders are identified by our own client_order_id (UUID hex), not
# Webull's internal orderId — that's what cancel/replace uses too.

def _place_order(ticker, shares, side, order_type,
                 stop_price=None, limit_price=None, client_order_id=None):
    """
    Low-level order placement via official Webull SDK.
    Returns client_order_id on success, None on failure.
    """
    if client_order_id is None:
        client_order_id = uuid.uuid4().hex

    _, trade_client = _make_webull_client()
    if not trade_client:
        print("⚠️  Webull SDK not available — cannot place order")
        return None

    order = {
        "combo_type":              "NORMAL",
        "client_order_id":         client_order_id,
        "symbol":                  ticker,
        "instrument_type":         "EQUITY",
        "market":                  "US",
        "order_type":              order_type,   # MKT or STP
        "quantity":                str(int(shares)),
        "side":                    side,         # BUY or SELL
        "time_in_force":           "DAY",
        "support_trading_session": "CORE",
        "entrust_type":            "QTY",
    }
    if stop_price is not None:
        order["aux_price"] = f"{stop_price:.4f}"
    if limit_price is not None:
        order["limit_price"] = f"{limit_price:.4f}"

    try:
        res = trade_client.order_v2.place_order(WEBULL_ACCOUNT_ID, [order])
        if res.status_code == 200:
            print(f"✅ Order placed via SDK: {client_order_id[:8]}...")
            return client_order_id
        else:
            print(f"⚠️  Order failed ({res.status_code}): {res.text[:200]}")
    except Exception as e:
        print(f"⚠️  Order SDK error: {e}")
    return None


def execute_trade(ticker, shares, entry_price, stop_loss, target):
    """
    Places a limit buy order (1% above VWAP entry) then a stop order.
    Using LMT instead of MKT caps slippage on small-float fast-moving stocks.
    Retries the buy order once after 3s on transient API failures.
    Returns (buy_client_order_id, stop_client_order_id) — both needed to manage the trade.
    Returns (None, None) on failure.
    """
    if DRY_RUN:
        fake_id = uuid.uuid4().hex
        print(f"🧪 DRY RUN — simulating BUY {shares} shares of {ticker} @ ${entry_price:.2f}")
        print(f"   Stop: ${stop_loss:.2f}  Target: ${target:.2f}")
        return fake_id, uuid.uuid4().hex

    shares      = max(1, int(shares))   # Webull requires whole shares
    limit_price = round(entry_price * (1 + ENTRY_LIMIT_BUFFER), 4)
    print(f"🚀 Executing: BUY {shares} shares of {ticker} "
          f"@ limit ${limit_price:.2f} (VWAP entry ${entry_price:.2f} +1%)...")

    buy_id = _place_order(ticker, shares, "BUY", "LMT", limit_price=limit_price)
    if not buy_id:
        print(f"⚠️  Buy order failed — retrying in 3s...")
        time.sleep(3)
        buy_id = _place_order(ticker, shares, "BUY", "LMT", limit_price=limit_price)
    if not buy_id:
        print(f"❌ Buy order failed after retry for {ticker}")
        return None, None

    print(f"✅ Buy order placed! Client ID: {buy_id}")
    time.sleep(2)   # Let fill confirm before placing stop

    stop_id = place_stop_order(ticker, shares, stop_loss)
    return buy_id, stop_id


def close_position(ticker, shares):
    """Sell shares at market price."""
    shares = max(1, int(shares))
    print(f"🔒 Closing: SELL {shares} shares of {ticker}...")
    if DRY_RUN:
        print(f"🧪 DRY RUN — simulating SELL {shares} shares of {ticker}")
        return True
    result = _place_order(ticker, shares, "SELL", "MKT")
    if result:
        print("✅ Position closed!")
        return True
    print(f"❌ Close position failed for {ticker}")
    return False


def cancel_order(client_order_id):
    """Cancel an open order by client_order_id via official Webull SDK."""
    if not client_order_id:
        return False
    if DRY_RUN:
        print(f"🧪 DRY RUN — simulating cancel {client_order_id[:8]}...")
        return True
    _, trade_client = _make_webull_client()
    if not trade_client:
        return False
    try:
        res = trade_client.order_v2.cancel_order(WEBULL_ACCOUNT_ID, client_order_id)
        if res.status_code == 200:
            print(f"✅ Order {client_order_id[:8]}... cancelled")
            return True
        else:
            print(f"⚠️  Cancel failed ({res.status_code}): {res.text[:200]}")
    except Exception as e:
        print(f"⚠️  Cancel order error: {e}")
    return False


def place_stop_order(ticker, shares, stop_price):
    """
    Place a live stop-loss sell order on Webull.
    Returns the client_order_id, or None if it fails.
    """
    shares = max(1, int(shares))
    if DRY_RUN:
        fake_id = uuid.uuid4().hex
        print(f"🧪 DRY RUN — simulating stop order: ${stop_price:.2f} × {shares} shares")
        return fake_id
    result = _place_order(ticker, shares, "SELL", "STP", stop_price=stop_price)
    if result:
        print(f"🛡️  Stop order placed: ${stop_price:.2f} × {shares} shares")
    else:
        print(f"⚠️  Stop order failed for {ticker} @ ${stop_price:.2f}")
    return result


def update_stop_order(ticker, shares, new_price, old_client_order_id):
    """
    Cancel the existing exchange stop order and place a new one.
    Returns the new client_order_id (or None if replacement fails).
    """
    print(f"🔄 Moving stop order → ${new_price:.2f} ({int(shares)} shares)...")
    cancel_order(old_client_order_id)
    time.sleep(0.5)   # Let the cancel settle
    new_id = place_stop_order(ticker, shares, new_price)
    if not new_id:
        print(f"❌ WARNING: Stop order replacement failed! Position has no exchange-level stop.")
    return new_id

# ============================================================
# STEP 6 — MONITOR WITH TRAILING STOP + PARTIAL EXITS
# ============================================================

STOP_UPDATE_MIN_MOVE = 0.10   # Only replace exchange stop order if it moves >= $0.10

def monitor_trade(ticker, total_shares, entry_price, target_price, stop_loss,
                  stream: WebullStream, stop_order_id, vwap=0):
    """
    Monitors the trade using the real-time stream.
    All stop levels are kept as live orders on Webull — not just in memory.
    If Railway restarts mid-trade, Webull enforces the last placed stop.

    - MQTT connected: checks every 0.5 seconds
    - Fallback polling: checks every 15 seconds
    """
    total_shares = max(1, int(total_shares))
    sleep_secs   = stream.loop_sleep()
    mode         = "real-time MQTT" if stream.connected else "15s polling fallback"
    print(f"\n👀 Monitoring {ticker} via {mode}")
    print(f"   Entry: ${entry_price:.2f} | Target: ${target_price:.2f} | Stop: ${stop_loss:.2f}")

    current_stop       = stop_loss
    placed_stop_price  = stop_loss
    placed_stop_qty    = total_shares
    placed_stop_id     = stop_order_id
    highest_price      = entry_price
    remaining_shares   = total_shares
    partial_taken      = False
    partial_price      = 0.0
    entry_time         = time.time()   # for early fade window

    result = {"exit_price": entry_price, "exit_reason": "Unknown",
              "profit_loss": 0, "profit_loss_pct": 0}

    while True:
        now = datetime.now(EASTERN)

        # ── Hard close at 11am ──────────────────────────
        if now.hour >= TRADE_WINDOW_END_HOUR:
            print("⏰ 11:00am — Force closing all positions")
            current_price = stream.get_price(ticker)
            if remaining_shares > 0:
                cancel_order(placed_stop_id)
                close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "11am time stop"
            break

        current_price = stream.get_price(ticker)
        if current_price <= 0:
            time.sleep(sleep_secs)
            continue

        # ── Early fade: if price drops back below VWAP within 2 min, cut immediately ──
        elapsed = time.time() - entry_time
        if vwap > 0 and elapsed <= EARLY_FADE_SECS and current_price < vwap:
            print(f"⚡ Early fade — {ticker} dropped below VWAP (${vwap:.2f}) "
                  f"within {elapsed:.0f}s of entry. Cutting loss now.")
            cancel_order(placed_stop_id)
            close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "Early VWAP fade ⚡"
            remaining_shares = 0
            break

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
                # Only replace exchange order if stop moved >= $0.10
                if current_stop - placed_stop_price >= STOP_UPDATE_MIN_MOVE:
                    placed_stop_id    = update_stop_order(ticker, placed_stop_qty,
                                                          current_stop, placed_stop_id)
                    placed_stop_price = current_stop

        print(f"💰 {ticker}: ${current_price:.2f} ({profit_pct:+.1f}%) | Stop: ${current_stop:.2f} | Shares: {remaining_shares}")

        # ── Partial exit at +15% ────────────────────────
        if not partial_taken and profit_pct >= PARTIAL_EXIT_PCT * 100:
            half = remaining_shares // 2
            if half < 1:
                half = 1
            print(f"💰 PARTIAL EXIT: selling {half} shares at ${current_price:.2f} (+{profit_pct:.1f}%)")
            cancel_order(placed_stop_id)
            close_position(ticker, half)
            partial_price    = current_price
            partial_taken    = True
            remaining_shares = remaining_shares - half
            current_stop     = highest_price * (1 - TRAIL_PCT)
            placed_stop_id    = place_stop_order(ticker, remaining_shares, current_stop)
            placed_stop_price = current_stop
            placed_stop_qty   = remaining_shares
            print(f"📈 Trailing stop set at ${current_stop:.2f} — letting rest run")
            send_partial_exit_alert(ticker, half, partial_price, entry_price,
                                    remaining_shares, current_stop, profit_pct)

        # ── Full target hit ─────────────────────────────
        if current_price >= target_price and remaining_shares > 0:
            print(f"🎯 TARGET HIT! Selling {remaining_shares} shares at ${current_price:.2f}")
            cancel_order(placed_stop_id)
            close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "Target hit ✅"
            remaining_shares = 0
            break

        # ── Software stop detection (backup to exchange stop) ──
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
        half = total_shares // 2
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
# TOKEN EXPIRY CHECK
# ============================================================

def check_token_expiry():
    """
    Read expiry timestamp from the Webull token file.
    Sends a warning email if the token expires within TOKEN_EXPIRY_WARN_DAYS days.
    """
    try:
        token_file = pathlib.Path(WEBULL_TOKEN_DIR) / "token.txt"
        if not token_file.exists():
            _pre_populate_webull_token()
        lines = token_file.read_text().strip().splitlines()
        if len(lines) < 2:
            return
        expires_ms  = int(lines[1])
        expires_dt  = datetime.fromtimestamp(expires_ms / 1000, tz=EASTERN)
        days_left   = (expires_dt - datetime.now(EASTERN)).days
        print(f"🔑 Webull token expires: {expires_dt.strftime('%B %d, %Y')} ({days_left} days)")
        if days_left <= TOKEN_EXPIRY_WARN_DAYS:
            subject = f"⚠️ ACTION REQUIRED — Webull Token Expires in {days_left} Days"
            body = f"""Your Webull API access token is expiring soon!

Token expires: {expires_dt.strftime('%A, %B %d, %Y at %I:%M %p ET')}
Days remaining: {days_left}

To renew it:
1. Run webull_setup.py on your machine
2. Copy the new WEBULL_ACCESS_TOKEN value
3. Update the Railway environment variable
4. Redeploy the bot service

If you don't renew before {expires_dt.strftime('%B %d')}, the bot will silently fail to place trades.
"""
            send_alert_email(subject, body)
    except Exception as e:
        print(f"⚠️  Token expiry check error: {e}")


# ============================================================
# TRADE RESULT LOGGING
# ============================================================

def log_trade_result(date, ticker, entry, exit_price, shares, pnl, pnl_pct,
                     exit_reason, confidence, float_shares):
    """
    Append one row to /tmp/trade_log.csv for in-session record keeping.
    Returns the CSV row as a string so it can be embedded in the summary email.
    """
    row = [
        date, ticker,
        f"{entry:.2f}", f"{exit_price:.2f}", str(shares),
        f"{pnl:+.2f}", f"{pnl_pct:+.1f}%",
        exit_reason, confidence, str(float_shares),
    ]
    try:
        log_path  = pathlib.Path(LOG_FILE)
        write_hdr = not log_path.exists()
        with open(log_path, "a", newline="") as f:
            w = csv.writer(f)
            if write_hdr:
                w.writerow(["Date", "Ticker", "Entry", "Exit", "Shares",
                            "P&L$", "P&L%", "Exit Reason", "Confidence", "Float"])
            w.writerow(row)
        print(f"📋 Trade logged to {LOG_FILE}")
    except Exception as e:
        print(f"⚠️  Trade log write error: {e}")
    return ",".join(row)


def post_to_dashboard(trade_payload: dict):
    """
    POST a completed trade record to the screener app's dashboard endpoint.
    Non-blocking — failure here never interrupts the main flow.
    """
    if not SCREENER_URL:
        return
    try:
        resp = requests.post(
            f"{SCREENER_URL}/api/record_trade",
            json=trade_payload,
            headers={"X-Dashboard-Secret": DASHBOARD_SECRET},
            timeout=8,
        )
        if resp.status_code == 200:
            print(f"📊 Trade posted to dashboard ({SCREENER_URL}/dashboard)")
        else:
            print(f"⚠️  Dashboard post failed: {resp.status_code}")
    except Exception as e:
        print(f"⚠️  Dashboard post error: {e}")


def post_balance_to_dashboard(balance: float):
    """POST the current account balance to the dashboard."""
    if not SCREENER_URL:
        return
    try:
        requests.post(
            f"{SCREENER_URL}/api/update_account",
            json={"balance": balance},
            headers={"X-Dashboard-Secret": DASHBOARD_SECRET},
            timeout=8,
        )
    except Exception:
        pass


# ============================================================
# STEP 7 — ALERT EMAILS (fired in real-time during the session)
# ============================================================

def _html_wrap(sections_html: str) -> str:
    """Wrap email content in a clean, large-font HTML shell."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#0f0f1a;font-family:Arial,sans-serif;font-size:17px;color:#e8e8f0;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:0 auto;">
<tr><td style="padding:24px 20px 8px;">
  <div style="font-size:13px;color:#7c7ca0;letter-spacing:1px;">MARCOS TRADING BOT &nbsp;·&nbsp; RAILWAY.APP</div>
</td></tr>
{sections_html}
<tr><td style="padding:16px 20px 32px;">
  <div style="font-size:13px;color:#555570;border-top:1px solid #2a2a3e;padding-top:12px;">
    Claude Opus AI + Webull OpenAPI v2 &nbsp;·&nbsp; Railway.app
  </div>
</td></tr>
</table></body></html>"""


def _section(title: str, rows_html: str, color: str = "#6c63ff") -> str:
    """A titled card section for HTML emails."""
    return f"""
<tr><td style="padding:8px 20px;">
  <div style="background:#1a1a2e;border-radius:10px;border-left:4px solid {color};padding:18px 20px;">
    <div style="font-size:13px;font-weight:bold;color:{color};letter-spacing:1.5px;margin-bottom:12px;">{title}</div>
    {rows_html}
  </div>
</td></tr>"""


def _row(label: str, value: str, big: bool = False) -> str:
    size = "20px" if big else "17px"
    return (f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
            f'border-bottom:1px solid #2a2a3e;">'
            f'<span style="color:#9090b0;font-size:15px;">{label}</span>'
            f'<span style="font-weight:bold;font-size:{size};color:#e8e8f0;">{value}</span>'
            f'</div>')


def send_alert_email(subject, body, html=None):
    """Sends email via Resend API. Accepts optional html for rich formatting."""
    if DRY_RUN:
        subject = f"[DRY RUN] {subject}"
    print(f"📲 Sending alert to {SUMMARY_EMAIL}: {subject}")
    try:
        resend.api_key = RESEND_API_KEY
        payload = {
            "from":    "Marcos Trading Bot <onboarding@resend.dev>",
            "to":      [SUMMARY_EMAIL],
            "subject": subject,
            "text":    body,
        }
        if html:
            payload["html"] = html
        r = resend.Emails.send(payload)
        print(f"✅ Alert sent! Resend id={getattr(r, 'id', r)}")
    except Exception as e:
        print(f"❌ Alert email error: {e}")


def send_plan_alert(analysis, balance):
    """Alert 1 — Fired right after Claude finishes analysis (~8:55am)."""
    recommended = analysis.get("recommended_trade", {})
    action      = recommended.get("action", "HOLD CASH")
    ticker      = recommended.get("ticker", "N/A")
    today       = datetime.now(EASTERN).strftime("%A, %B %d, %Y")
    conf        = recommended.get("confidence", "N/A")
    conf_color  = {"HIGH": "#00c851", "MEDIUM": "#ffbb33", "LOW": "#ff6b35"}.get(conf, "#9090b0")

    if action == "BUY":
        subject = f"🤖 Bot Plan — {ticker} is the pick | {today}"
        plain = (f"Good morning Marcos! Claude picked {ticker}.\n\n"
                 f"Entry: ~${recommended.get('entry_price',0):.2f} | "
                 f"Target: ${recommended.get('target_price',0):.2f} | "
                 f"Stop: ${recommended.get('stop_loss',0):.2f}\n\n"
                 f"{analysis.get('plain_english_summary','')}")

        ticker_rows = ""
        for t in analysis.get("tickers", []):
            go   = t["verdict"] == "GO"
            icon = "✅" if go else "❌"
            clr  = "#00c851" if go else "#ff4444"
            ticker_rows += (f'<div style="padding:8px 0;border-bottom:1px solid #2a2a3e;">'
                            f'<span style="font-size:16px;">{icon} <strong style="color:{clr};">{t["ticker"]}</strong>'
                            f' — {t["verdict"]}</span>'
                            f'<div style="color:#9090b0;font-size:15px;margin-top:4px;">{t["reason"]}</div>'
                            f'</div>')

        html = _html_wrap(
            f'<tr><td style="padding:16px 20px 4px;">'
            f'<div style="font-size:26px;font-weight:bold;color:#ffffff;">Good morning Marcos! 👋</div>'
            f'<div style="font-size:16px;color:#9090b0;margin-top:6px;">Claude just finished the pre-market analysis for {today}</div>'
            f'</td></tr>'
            + _section("TODAY'S PLAN", (
                _row("Ticker", f'<span style="font-size:24px;color:#6c63ff;">{ticker}</span>', big=True)
                + _row("Action", "Watching for VWAP reclaim after 9:30am")
                + _row("Entry", f"~${recommended.get('entry_price',0):.2f}")
                + _row("Target", f"${recommended.get('target_price',0):.2f} (+20%)", big=True)
                + _row("Stop Loss", f"${recommended.get('stop_loss',0):.2f} (-7%)")
                + _row("Position Size", f"${recommended.get('position_size_dollars',0):.2f}")
                + _row("Confidence", f'<span style="color:{conf_color};">{conf}</span>')
                + _row("Account", f"${balance:.2f}")
            ), color="#6c63ff")
            + _section("CLAUDE SAYS", f'<div style="font-size:17px;line-height:1.7;color:#d0d0e8;">{analysis.get("plain_english_summary","")}</div>', color="#00c851")
            + _section("ALL TICKERS REVIEWED", ticker_rows, color="#ffbb33")
            + f'<tr><td style="padding:12px 20px;">'
            f'<div style="background:#1a2a1a;border-radius:8px;padding:14px 18px;color:#00c851;font-size:16px;">'
            f'🔍 Bot is now watching for the VWAP reclaim. You\'ll get another email the moment it enters.</div></td></tr>'
        )
    else:
        subject = f"🤖 Bot Plan — 💤 No trade today | {today}"
        plain = f"No trade today. Cash: ${balance:.2f}\n\n{analysis.get('plain_english_summary','')}"
        html = _html_wrap(
            f'<tr><td style="padding:16px 20px 4px;">'
            f'<div style="font-size:26px;font-weight:bold;color:#ffffff;">Good morning Marcos! 👋</div>'
            f'<div style="font-size:16px;color:#9090b0;margin-top:6px;">{today}</div>'
            f'</td></tr>'
            + _section("NO TRADE TODAY",
                f'<div style="font-size:17px;line-height:1.7;color:#d0d0e8;">{analysis.get("plain_english_summary","")}</div>'
                + f'<div style="margin-top:14px;">' + _row("Cash Preserved", f"${balance:.2f}", big=True) + '</div>',
                color="#ffbb33")
        )

    send_alert_email(subject, plain, html=html)


def send_entry_alert(ticker, shares, entry_price, stop_loss, target_price, vwap, position_size):
    """Alert 2 — Fired the moment the buy order is placed."""
    now_str = datetime.now(EASTERN).strftime("%I:%M:%S %p ET")
    subject = f"🚀 TRADE ENTERED — {ticker} @ ${entry_price:.2f} | {now_str}"
    plain = (f"TRADE ENTERED: {ticker} @ ${entry_price:.2f} | {shares} shares | ${position_size:.2f}\n"
             f"Target: ${target_price:.2f} | Stop: ${stop_loss:.2f} | VWAP: ${vwap:.2f}")
    html = _html_wrap(
        f'<tr><td style="padding:16px 20px 4px;">'
        f'<div style="font-size:28px;font-weight:bold;color:#00c851;">🚀 TRADE ENTERED!</div>'
        f'<div style="font-size:16px;color:#9090b0;margin-top:6px;">{now_str}</div>'
        f'</td></tr>'
        + _section("FILL DETAILS", (
            _row("Ticker",    f'<span style="font-size:24px;color:#6c63ff;">{ticker}</span>', big=True)
            + _row("Filled At",  f"${entry_price:.2f}")
            + _row("Shares",     str(shares))
            + _row("Position",   f"${position_size:.2f}")
            + _row("VWAP",       f"${vwap:.2f} ✅")
        ), color="#00c851")
        + _section("LEVELS TO WATCH", (
            _row("🎯 Target (+20%)",      f"${target_price:.2f}", big=True)
            + _row("💰 Partial exit (+15%)", "Sell half, trail rest")
            + _row("⚡ Breakeven (+10%)",    "Stop moves to entry")
            + _row("🛑 Stop Loss (-7%)",     f"${stop_loss:.2f}")
            + _row("⏰ Hard Close",           "11:00am ET")
        ), color="#ffbb33")
    )
    send_alert_email(subject, plain, html=html)


def send_partial_exit_alert(ticker, half_shares, partial_price, entry_price,
                            remaining_shares, new_stop, profit_pct):
    """Alert 3 — Fired when half the position is sold at +15%."""
    now_str = datetime.now(EASTERN).strftime("%I:%M:%S %p ET")
    profit  = (partial_price - entry_price) * half_shares
    subject = f"💰 PARTIAL EXIT — {ticker} +{profit_pct:.1f}% at {now_str}"
    plain = (f"Sold half at +{profit_pct:.1f}% (${profit:+.2f}). "
             f"{remaining_shares} shares remain. Trailing stop: ${new_stop:.2f}")
    html = _html_wrap(
        f'<tr><td style="padding:16px 20px 4px;">'
        f'<div style="font-size:28px;font-weight:bold;color:#00c851;">💰 PARTIAL EXIT!</div>'
        f'<div style="font-size:16px;color:#9090b0;margin-top:6px;">{now_str}</div>'
        f'</td></tr>'
        + _section("SOLD", (
            _row("Ticker",      ticker)
            + _row("Sold",      f"{half_shares} shares @ ${partial_price:.2f}")
            + _row("Gain",      f'+{profit_pct:.1f}% (${profit:+.2f})', big=True)
        ), color="#00c851")
        + _section("STILL IN TRADE", (
            _row("Remaining Shares", str(remaining_shares))
            + _row("Trailing Stop",  f"${new_stop:.2f} (5% below high)")
            + _row("Full Exit",      "+20% target")
        ), color="#6c63ff")
    )
    send_alert_email(subject, plain, html=html)


# ============================================================
# STEP 8 — FINAL SUMMARY EMAIL
# ============================================================

def send_summary_email(analysis, trade_result=None, account_balance=100.0, csv_log_line=""):
    print(f"📨 Sending summary email to {SUMMARY_EMAIL}...")
    today   = datetime.now(EASTERN).strftime("%A, %B %d, %Y")
    dry_tag = "[DRY RUN] " if DRY_RUN else ""

    if trade_result and analysis:
        recommended = analysis.get("recommended_trade", {})
        ticker      = recommended.get("ticker", "N/A")
        pnl         = trade_result.get("profit_loss", 0)
        pnl_pct     = trade_result.get("profit_loss_pct", 0)
        exit_reason = trade_result.get("exit_reason", "N/A")
        exit_price  = trade_result.get("exit_price", 0)
        win         = pnl >= 0
        result_line = f"{'✅' if win else '🔴'} {ticker}: {pnl_pct:+.1f}% (${pnl:+.2f})"
        subject     = f"{dry_tag}Trading Bot Summary — {today} | {result_line}"
        pnl_color   = "#00c851" if win else "#ff4444"

        ticker_rows = ""
        for t in (analysis.get("tickers") or []):
            go = t["verdict"] == "GO"
            ticker_rows += (f'<div style="padding:8px 0;border-bottom:1px solid #2a2a3e;">'
                            f'<span style="font-size:16px;">{"✅" if go else "❌"} '
                            f'<strong style="color:{"#00c851" if go else "#ff4444"};">{t["ticker"]}</strong> — {t["verdict"]}</span>'
                            f'<div style="color:#9090b0;font-size:15px;margin-top:3px;">{t["reason"]}</div>'
                            f'</div>')

        html = _html_wrap(
            f'<tr><td style="padding:16px 20px 4px;">'
            f'<div style="font-size:26px;font-weight:bold;color:#ffffff;">Trading Summary — {today}</div>'
            f'</td></tr>'
            + _section("TRADE RESULT", (
                _row("Ticker",      ticker)
                + _row("P&L",       f'<span style="color:{pnl_color};font-size:22px;">{pnl_pct:+.1f}% (${pnl:+.2f})</span>', big=True)
                + _row("Exit",      f"${exit_price:.2f} — {exit_reason}")
                + _row("New Balance", f"${account_balance + pnl:.2f}", big=True)
            ), color=pnl_color)
            + _section("CLAUDE'S ANALYSIS", f'<div style="font-size:17px;line-height:1.7;color:#d0d0e8;">{analysis.get("plain_english_summary","")}</div>', color="#6c63ff")
            + _section("ALL TICKERS REVIEWED", ticker_rows, color="#ffbb33")
            + (f'<tr><td style="padding:8px 20px;">'
               f'<div style="background:#1a1a2e;border-radius:8px;padding:14px 18px;">'
               f'<div style="font-size:13px;color:#7c7ca0;margin-bottom:6px;">TRADE LOG</div>'
               f'<pre style="font-size:13px;color:#9090b0;margin:0;white-space:pre-wrap;">'
               f'Date,Ticker,Entry,Exit,Shares,P&L$,P&L%,Exit Reason,Confidence,Float\n{csv_log_line}</pre>'
               f'</div></td></tr>' if csv_log_line else "")
        )
        plain = f"{result_line}\nExit: ${exit_price:.2f} — {exit_reason}\nBalance: ~${account_balance+pnl:.2f}"
    else:
        subject = f"{dry_tag}Trading Bot Summary — {today} | 💤 No Trade Today"
        plain_summary = analysis.get("plain_english_summary", "") if analysis else "No watchlist email found."
        html = _html_wrap(
            f'<tr><td style="padding:16px 20px 4px;">'
            f'<div style="font-size:26px;font-weight:bold;color:#ffffff;">Trading Summary — {today}</div>'
            f'</td></tr>'
            + _section("NO TRADE TAKEN TODAY", (
                _row("Cash Preserved", f"${account_balance:.2f}", big=True)
                + f'<div style="margin-top:12px;font-size:17px;line-height:1.7;color:#d0d0e8;">{plain_summary}</div>'
            ), color="#ffbb33")
            + _section("REMINDER", (
                f'<div style="font-size:16px;color:#d0d0e8;line-height:1.8;">'
                f'Send tonight\'s tickers to: <strong>molivera1977@icloud.com</strong><br>'
                f'Paste Kev\'s TikTok transcript in the body.<br>'
                f'The bot reads it at 8:45am tomorrow.</div>'
            ), color="#6c63ff")
        )
        plain = f"No trade today. Cash: ${account_balance:.2f}\n\n{plain_summary}"

    try:
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from":    "Marcos Trading Bot <onboarding@resend.dev>",
            "to":      [SUMMARY_EMAIL],
            "subject": subject,
            "text":    plain,
            "html":    html,
        })
        print(f"✅ Summary email sent!")
    except Exception as e:
        print(f"❌ Email error: {e}")

# ============================================================
# RESCAN HELPER
# ============================================================

def run_rescan(email_content, market_data, balance, current_analysis,
               scan_number, market_context=None):
    """
    Re-runs the full gapper scan + Claude analysis.
    Returns the new analysis. If Claude switches tickers, sends an update email.
    """
    now = datetime.now(EASTERN)
    print(f"\n{'─'*55}")
    print(f"🔄 RE-SCAN #{scan_number} — {now.strftime('%I:%M %p ET')}")
    print(f"{'─'*55}")

    gappers = scan_morning_gappers()
    for g in gappers:
        g["news"] = get_news_catalyst(g["symbol"])
        time.sleep(0.3)

    # Always fetch fresh SPY — it can move significantly between rescans
    ctx = get_market_context()
    spy_chg = ctx.get("spy_change_pct", 0)
    if isinstance(spy_chg, (int, float)) and spy_chg <= SPY_BEAR_SKIP_PCT:
        print(f"🚫 Rescan #{scan_number}: SPY now {spy_chg:+.2f}% — below threshold. Aborting.")
        current_analysis["plain_english_summary"] += (
            f"\n\nNOTE: Market deteriorated to SPY {spy_chg:+.2f}% during rescan #{scan_number}. "
            f"Holding cash — momentum plays not viable in this environment."
        )
        return current_analysis

    new_analysis = analyze_with_claude(email_content, market_data, balance,
                                       gappers=gappers, market_context=ctx)
    if not new_analysis:
        print("⚠️  Re-scan Claude call failed — keeping current pick")
        return current_analysis

    old_rec = (current_analysis.get("recommended_trade") or {})
    new_rec = (new_analysis.get("recommended_trade") or {})
    old_t   = old_rec.get("ticker", "NONE")
    new_t   = new_rec.get("ticker", "NONE")

    if new_t and new_t != old_t:
        print(f"🔄 Claude switched pick: {old_t} → {new_t}")
        send_alert_email(
            f"🔄 Bot updated pick: {new_t} (was {old_t}) | Re-scan #{scan_number}",
            f"Re-scan #{scan_number} at {now.strftime('%I:%M %p ET')} found a stronger setup.\n\n"
            f"{new_analysis.get('plain_english_summary', '')}"
        )
    else:
        print(f"✅ Re-scan #{scan_number} confirms: {new_t} still the pick")

    return new_analysis


# ============================================================
# MAIN
# ============================================================

def main():
    now = datetime.now(EASTERN)
    print(f"\n{'='*60}")
    print(f"🤖 MARCOS TRADING BOT STARTING UP")
    print(f"📅 {now.strftime('%A, %B %d, %Y at %I:%M %p ET')}")
    print(f"{'='*60}\n")

    # Hard time gate — exit immediately if outside the 8:30–10:30am ET window.
    minutes_et = now.hour * 60 + now.minute
    if not (8 * 60 + 30 <= minutes_et <= 10 * 60 + 30):
        print(f"⏰ Outside trading window ({now.strftime('%H:%M')} ET) — exiting.")
        return

    # ── Credential check ───────────────────────────────────
    tok = WEBULL_ACCESS_TOKEN
    key = WEBULL_APP_KEY
    print(f"🔑 APP_KEY   : {key[:6]}...{key[-4:] if len(key)>10 else '(short)'}")
    print(f"🔑 TOKEN     : {tok[:6]}...{tok[-4:] if len(tok)>10 else '(short/missing)'} (len={len(tok)})")
    print(f"🔑 ACCOUNT_ID: {WEBULL_ACCOUNT_ID}")

    # ── Token expiry warning + API health check ────────────
    print("🔄 Step: pre-populating token...")
    _pre_populate_webull_token()
    print("🔄 Step: checking token expiry...")
    check_token_expiry()
    print("🔄 Step: checking Webull connection...")
    check_webull_connection()
    print("🔄 Step: market/holiday check...")

    if now.weekday() >= 5:
        print("📅 Weekend — markets closed.")
        return

    today_str = now.strftime("%Y-%m-%d")
    if today_str in US_MARKET_HOLIDAYS:
        print(f"📅 {today_str} is a US market holiday — markets closed.")
        return

    if DRY_RUN:
        print("🧪 DRY RUN MODE — all trades will be simulated, no real orders placed")

    # ── Step 1: Read iCloud email ──────────────────────────
    print("🔄 Step: reading iCloud email...")
    subject, email_content = read_todays_tickers()
    if not email_content:
        send_summary_email(None, None, get_account_balance())
        return

    # ── Step 2: Extract tickers ────────────────────────────
    # Strip reply/forward prefixes before parsing
    clean_subject = re.sub(r'^(FW|FWD|RE):\s*', '', subject.strip(), flags=re.IGNORECASE)
    # Generic words that are NOT stock tickers — UK/US excluded since they ARE tickers Kev uses
    skip = {"THE", "FOR", "AND", "NOT", "ALL", "DAY", "TOP",
            "NEW", "BIG", "HOT", "PDT", "RE", "AI", "ET", "FW", "FWD",
            "TO", "IN", "UP", "AM", "PM", "IS", "IT", "ON", "MY",
            "AT", "BY", "OR", "NO", "IF", "SO", "DO", "BE", "GO",
            "EST", "EDT", "PST", "HOLD", "BUY", "SELL", "LONG", "SHORT",
            "PLAY", "OVER", "BACK", "FROM", "WITH", "THAT", "THIS",
            "THEN", "NEXT", "LAST", "ALSO", "JUST", "WILL", "HAVE",
            "VWAP", "MACD", "HIGH", "LOWS", "MOVE", "LOOK", "WANT",
            "GIVE", "MAKE", "PUTS", "GETS", "THAN",
            "BODY", "SUBJECT", "DATE", "MIME", "CONTENT", "TYPE"}

    # Step 1: extract $TICKER from subject (most reliable — Kev writes $NVDA $TSLA)
    dollar_in_subject = re.findall(r'\$([A-Z]{1,5})\b', clean_subject.upper())
    tickers = [t for t in dollar_in_subject if t not in skip][:5]

    # Step 2: bare uppercase words in subject if no $ tickers found
    if not tickers:
        tickers = [t for t in re.findall(r'\b[A-Z]{2,5}\b', clean_subject.upper())
                   if t not in skip][:5]

    # Step 3: scan email body — $TICKER format first, then bare caps
    if not tickers and email_content:
        body_text = email_content.upper()
        dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', body_text)
        tickers = [t for t in dollar_tickers if t not in skip][:5]

        if not tickers:
            tickers = [t for t in re.findall(r'\b[A-Z]{2,5}\b', body_text)
                       if t not in skip][:5]

    if not tickers:
        tickers = ["UNKNOWN"]
    print(f"📋 Tickers: {tickers}  (subject='{clean_subject[:80]}')")

    # ── Step 3: Market context + pre-market data + gapper scan ──
    market_context = get_market_context()

    # ── SPY hard filter: skip the day if market is too bearish ──
    spy_chg = market_context.get("spy_change_pct", 0)
    if isinstance(spy_chg, (int, float)) and spy_chg <= SPY_BEAR_SKIP_PCT:
        msg = (f"SPY is down {spy_chg:+.2f}% pre-market — below the {SPY_BEAR_SKIP_PCT}% threshold. "
               f"Holding cash. Small-cap gap plays have very low success rates on strong red market days.")
        print(f"🚫 {msg}")
        subject = f"🚫 Bot skipping today — SPY {spy_chg:+.2f}% (market too bearish)"
        send_alert_email(subject, f"Good morning Marcos!\n\n{msg}\n\nCash preserved: ${get_account_balance():.2f}")
        return

    market_data = []
    for t in tickers:
        if t != "UNKNOWN":
            data = get_premarket_data(t)
            data["news"] = get_news_catalyst(t)
            market_data.append(data)
            time.sleep(0.5)

    # Scan Webull screener for morning gappers (~8:50am — before analysis)
    gappers = scan_morning_gappers()

    # Fetch news for each gapper too
    for g in gappers:
        g["news"] = get_news_catalyst(g["symbol"])
        time.sleep(0.3)

    # ── Step 4: Account balance ────────────────────────────
    balance = get_account_balance()
    print(f"💰 Balance: ${balance:.2f}")
    post_balance_to_dashboard(balance)

    # ── Step 5: Claude Opus analysis ───────────────────────
    analysis = analyze_with_claude(email_content, market_data, balance,
                                   gappers=gappers, market_context=market_context)
    if not analysis:
        send_summary_email(None, None, balance)
        return

    # ── Alert 1: Send the plan email right now (~8:55am) ──────
    send_plan_alert(analysis, balance)

    recommended = analysis.get("recommended_trade", {})
    if recommended.get("action") != "BUY":
        print("🔒 Claude says: HOLD CASH today.")
        return

    ticker_to_trade = recommended.get("ticker")

    # Dynamic position sizing based on Claude's confidence rating
    confidence = recommended.get("confidence", "MEDIUM").upper()
    if confidence == "HIGH":
        size_pct = MAX_POSITION_SIZE       # 70%
    elif confidence == "LOW":
        size_pct = POSITION_SIZE_LOW       # 30%
    else:
        size_pct = POSITION_SIZE_MEDIUM    # 50%
    position_size = min(
        float(recommended.get("position_size_dollars", balance * size_pct)),
        balance * size_pct
    )
    print(f"💼 Position size: ${position_size:.2f} ({confidence} confidence → {size_pct*100:.0f}% of account)")

    # ── Rescan every 20 min until 9:45am ET ────────────────
    #
    # Pre-market rescans (before 9:30am): run in main thread.
    # The bot is idle during this window anyway — might as well keep checking.
    #
    # Post-open rescan (9:45am): fires via background Timer while VWAP watch runs.
    # If Claude switches the pick before a trade is entered, we honor the switch.
    # Once a trade is entered (trade_entered event), the background rescan is a no-op.

    RESCAN_CUTOFF_HOUR, RESCAN_CUTOFF_MIN = 9, 45   # stop rescanning at 9:45am
    RESCAN_INTERVAL_SECS = 20 * 60                   # 20 minutes

    trade_entered = threading.Event()   # set when buy order is placed
    scan_state    = {"analysis": analysis, "ticker": ticker_to_trade,
                     "position_size": position_size}

    def _background_rescan_at_945(n):
        """Fires once at 9:45am via threading.Timer while VWAP wait is active."""
        if trade_entered.is_set():
            print("⏭️  9:45am rescan skipped — trade already entered")
            return
        updated = run_rescan(email_content, market_data, balance,
                             scan_state["analysis"], n, market_context=market_context)
        if trade_entered.is_set():
            return
        scan_state["analysis"] = updated
        rec = updated.get("recommended_trade") or {}
        if rec.get("action") == "BUY" and rec.get("ticker"):
            scan_state["ticker"]        = rec["ticker"]
            scan_state["position_size"] = float(rec.get("position_size_dollars",
                                                        balance * MAX_POSITION_SIZE))

    scan_number = 1
    while True:
        now          = datetime.now(EASTERN)
        cutoff_today = now.replace(hour=RESCAN_CUTOFF_HOUR,
                                   minute=RESCAN_CUTOFF_MIN, second=0, microsecond=0)
        next_scan_dt = now + timedelta(seconds=RESCAN_INTERVAL_SECS)

        market_open = now.hour > 9 or (now.hour == 9 and now.minute >= 30)

        if market_open or next_scan_dt >= cutoff_today:
            # Schedule the 9:45am rescan in background if we haven't passed it yet
            secs_to_945 = (cutoff_today - now).total_seconds()
            if secs_to_945 > 0:
                t = threading.Timer(secs_to_945, _background_rescan_at_945,
                                    args=[scan_number])
                t.daemon = True
                t.start()
                print(f"⏳ 9:45am background re-scan scheduled "
                      f"(in {secs_to_945/60:.0f} min)")
            break

        # Sleep until next 20-min mark
        sleep_secs = (next_scan_dt - now).total_seconds()
        print(f"⏳ Next re-scan #{scan_number} in {sleep_secs/60:.0f} min "
              f"({next_scan_dt.strftime('%I:%M %p ET')})...")
        time.sleep(sleep_secs)

        now = datetime.now(EASTERN)
        if now.hour > 9 or (now.hour == 9 and now.minute >= 30):
            break

        analysis = run_rescan(email_content, market_data, balance,
                              analysis, scan_number, market_context=market_context)
        scan_state["analysis"] = analysis
        scan_number += 1

        rec = analysis.get("recommended_trade") or {}
        if rec.get("action") != "BUY":
            print("🔒 Re-scan says HOLD CASH — aborting")
            send_summary_email(analysis, None, balance)
            return
        ticker_to_trade           = rec.get("ticker", ticker_to_trade)
        position_size             = float(rec.get("position_size_dollars",
                                                  balance * MAX_POSITION_SIZE))
        scan_state["ticker"]        = ticker_to_trade
        scan_state["position_size"] = position_size

    # Use the latest pick from scan_state (may have been updated by 9:45 timer)
    ticker_to_trade = scan_state["ticker"]
    position_size   = scan_state["position_size"]
    analysis        = scan_state["analysis"]

    # ── Step 6: Open real-time MQTT stream ─────────────────
    gapper_syms    = [g["symbol"] for g in gappers] if gappers else []
    stream_tickers = list(dict.fromkeys([ticker_to_trade] + tickers + gapper_syms))
    stream         = WebullStream(stream_tickers)

    # ── Step 7: Wait for VWAP entry ────────────────────────
    entry_price, vwap = wait_for_vwap_entry(scan_state["ticker"], stream)

    if not entry_price:
        note = f"\n\nNOTE: {ticker_to_trade} never reclaimed VWAP by 2:00pm. Cash preserved."
        analysis["plain_english_summary"] += note
        send_summary_email(analysis, None, balance)
        stream.stop()
        return

    # Recalculate stop/target from actual VWAP entry
    stop_loss    = round(entry_price * (1 - STOP_LOSS_PCT), 4)
    target_price = round(entry_price * (1 + TARGET_PCT), 4)
    shares       = max(1, int(position_size / entry_price))

    # Hard guard: if 1 share costs more than the full account, skip (e.g. high-priced IPO)
    if entry_price > balance:
        note = (f"\n\n⚠️ {ticker_to_trade} priced at ${entry_price:.2f} — exceeds full account "
                f"(${balance:.2f}). Holding cash.")
        analysis["plain_english_summary"] += note
        send_summary_email(analysis, None, balance)
        stream.stop()
        return

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

    # ── Step 8a: Bid-ask spread check ─────────────────────
    spread_ok, spread_pct = check_bid_ask_spread(ticker_to_trade)
    if not spread_ok:
        note = (f"\n\nNOTE: {ticker_to_trade} spread was {spread_pct*100:.2f}% — "
                f"above the {MAX_SPREAD_PCT*100:.1f}% limit. Entry skipped to avoid bad fill.")
        analysis["plain_english_summary"] += note
        send_summary_email(analysis, None, balance)
        stream.stop()
        return

    # ── Step 8b: Execute ───────────────────────────────────
    order_id, stop_order_id = execute_trade(
        ticker_to_trade, shares, entry_price, stop_loss, target_price
    )
    if not order_id:
        send_summary_email(analysis, None, balance)
        stream.stop()
        return

    trade_entered.set()   # stop the 9:45am background rescan from switching ticker

    # Register open position so SIGTERM handler can alert if bot is killed mid-trade
    _open_trade.update({
        "active":      True,
        "ticker":      ticker_to_trade,
        "entry_price": entry_price,
        "shares":      shares,
        "stop_loss":   stop_loss,
        "target":      target_price,
    })

    # ── Alert 2: Trade entered! ────────────────────────────
    send_entry_alert(ticker_to_trade, shares, entry_price,
                     stop_loss, target_price, vwap, position_size)

    # ── Step 9: Monitor with real-time stream ──────────────
    trade_result = monitor_trade(
        ticker_to_trade, shares,
        entry_price, target_price, stop_loss,
        stream, stop_order_id, vwap=vwap
    )

    # ── Step 10: Log result, send summary + cleanup ────────
    _open_trade["active"] = False   # disarm SIGTERM emergency alert
    stream.stop()
    new_balance = get_account_balance()
    pnl         = trade_result.get("profit_loss", 0)
    pnl_pct     = trade_result.get("profit_loss_pct", 0)
    exit_reason = trade_result.get("exit_reason", "N/A")

    float_shares = next(
        (d.get("float_shares", "N/A") for d in market_data if d.get("ticker") == ticker_to_trade),
        "N/A"
    )
    csv_row = log_trade_result(
        date         = datetime.now(EASTERN).strftime("%Y-%m-%d"),
        ticker       = ticker_to_trade,
        entry        = entry_price,
        exit_price   = trade_result.get("exit_price", entry_price),
        shares       = shares,
        pnl          = pnl,
        pnl_pct      = pnl_pct,
        exit_reason  = exit_reason,
        confidence   = confidence,
        float_shares = float_shares,
    )

    post_to_dashboard({
        "date":            datetime.now(EASTERN).strftime("%Y-%m-%d"),
        "ticker":          ticker_to_trade,
        "entry":           entry_price,
        "exit":            trade_result.get("exit_price", entry_price),
        "shares":          shares,
        "pnl":             pnl,
        "pnl_pct":         pnl_pct,
        "exit_reason":     exit_reason,
        "confidence":      confidence,
        "float_shares":    str(float_shares),
        "position_size":   position_size,
        "account_balance": new_balance,
    })

    send_summary_email(analysis, trade_result, new_balance, csv_log_line=csv_row)

    print(f"\n{'='*60}")
    print(f"✅ SESSION COMPLETE")
    print(f"   Result:  ${pnl:+.2f} ({pnl_pct:+.1f}%)")
    print(f"   Reason:  {exit_reason}")
    print(f"   Balance: ${new_balance:.2f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
