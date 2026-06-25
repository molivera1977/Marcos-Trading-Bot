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
   - At +8% (AM) / +5% (PM): partial exit (half sold, floor at entry, trail rest)
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
import concurrent.futures
import logging
import requests
import anthropic
import resend
import yfinance as yf
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import pytz

# Silence noisy SDK loggers — they flood Railway's 500 logs/sec limit
logging.getLogger("webull").setLevel(logging.ERROR)
logging.getLogger("webull_openapi").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

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


_wb_fundamentals_logged: set = set()

def _get_webull_fundamentals(ticker: str) -> dict:
    """
    Fetch sector, easy_to_borrow, and shortable from Webull instrument + company_profile APIs.
    Float, avg_vol, and market_cap are NOT available in Webull SDK — those stay on yfinance.
    Returns dict; values are None when the field isn't available.
    """
    result: dict = {
        "float_shares":   None,
        "avg_volume":     None,
        "market_cap":     None,
        "sector":         None,
        "easy_to_borrow": None,   # True/False — short interest proxy
        "shortable":      None,   # True/False — borrow availability
    }
    dc = _get_data_client()
    if not dc:
        return result

    # ── instrument call — margin/trading metadata ──────────────────────────────
    # NOTE: Webull instrument API has NO float, avg_vol, or market_cap.
    # Useful fields: easy_to_borrow (short interest proxy), shortable.
    try:
        resp = dc.instrument.get_instrument(symbols=ticker)
        if resp and resp.status_code == 200:
            raw = resp.json()
            items = (raw if isinstance(raw, list)
                     else raw.get("data", raw.get("items", [raw] if isinstance(raw, dict) else [])))
            for item in items:
                if not isinstance(item, dict):
                    continue
                etb = item.get("easy_to_borrow")
                sht = item.get("shortable")
                if etb is not None:
                    result["easy_to_borrow"] = bool(etb)
                if sht is not None:
                    result["shortable"] = bool(sht)
                break
    except Exception as e:
        print(f"⚠️  Webull instrument error for {ticker}: {e}")

    # ── company_profile call — sector from industries list ─────────────────────
    try:
        resp = dc.instrument.get_company_profile(ticker)
        if resp and resp.status_code == 200:
            raw = resp.json()
            data = raw.get("data", raw) if isinstance(raw, dict) else {}
            # industries is a list like ["Technology", "Software"]
            industries = data.get("industries") or []
            if industries and isinstance(industries, list):
                result["sector"] = industries[0]
            else:
                sect = data.get("sector") or data.get("industry") or data.get("sic_industry") or None
                if sect:
                    result["sector"] = sect
    except Exception as e:
        print(f"⚠️  Webull company_profile error for {ticker}: {e}")

    return result


# Trading rules
MAX_TRADE_DOLLARS     = 100.00 # Hard cap per trade until system proves reliable
MAX_POSITION_SIZE     = 0.70   # Max 70% of account on single trade (HIGH confidence)
POSITION_SIZE_MEDIUM  = 0.50   # 50% for MEDIUM confidence
POSITION_SIZE_LOW     = 0.30   # 30% for LOW confidence
STOP_LOSS_PCT         = 0.07   # 7% emergency exchange stop (EMA9 fires first)
TARGET_PCT            = 0.20   # 20% full profit target
EXIT_TIERS_AM = [          # Morning (9-11am): scale out in 3 tiers
    (0.08, 0.25),          #   +8%  → sell 25%
    (0.12, 0.50),          #   +12% → sell 50%
    (0.20, 1.00),          #   +20% → sell remaining 25%
]
EXIT_TIERS_PM = [          # Afternoon (after 11am): scale out in 2 tiers
    (0.04, 0.50),          #   +4%  → sell 50%
    (0.06, 1.00),          #   +6%  → sell remaining 50%
]
TRAIL_PCT             = 0.05   # Trail 5% below highest after partial exit

# ── v10 Entry detection parameters ────────────────────────────
FLAT_TOP_WINDOW    = 4      # 4-bar consolidation window
FLAT_TOP_MAX_RANGE = 0.080  # <8% range tolerance
EMA_PERIOD         = 9      # EMA9 for stops + bounce detection
EMA20_PERIOD       = 20     # EMA20 for bullish stack confirmation
EMA90_PERIOD       = 90     # EMA90 — Kev's key pullback/liquidity level. DATA-ONLY for now:
#                             recorded at entry to study (does NOT affect entries). See [[project_kev_lessons]].
EMA_CONFIRM_BARS   = 2      # consecutive bars below EMA9 before stop fires
EMA_CHECK_INTERVAL = 60     # seconds between EMA9 bar fetches during trade monitoring
EMA_BOUNCE_TOUCH   = 0.015  # prev bar within 1.5% above EMA9 = "touched"
EMA_BOUNCE_LOOKBACK = 20    # bars to look back for prior high
EMA_BOUNCE_VOL_MULT = 1.2   # bounce bar volume > 1.2× prior 3-bar avg
EMA_STOP_BUFFER    = 0.025  # initial stop = EMA9 × (1 − 2.5%)
MIN_RR             = 2.0    # minimum reward:risk ratio for EMA bounce
ENTRY_CUTOFF_HOUR  = 11     # Kev's full 9:00-11:00 window
ENTRY_CUTOFF_MIN   = 0
VWAP_ENTRY_TIMEOUT     = 15    # No new entries after 3:30pm ET (not enough time to run)
VWAP_ENTRY_TIMEOUT_MIN = 30   # minute component of final cutoff
FIRST_TICKER_CUTOFF_MIN = 20  # Switch to backup ticker if #1 hasn't set up by 9:50am ET
TRADE_WINDOW_END_HOUR = 15     # Force close all positions by 3:45pm ET (before market close)
TRADE_WINDOW_END_MIN  = 45    # minute component of force close
ENTRY_LIMIT_BUFFER    = 0.01   # Limit buy 1% above VWAP reclaim — caps slippage on small floats
EARLY_FADE_SECS       = 120    # If price drops below VWAP within 2 min of entry, exit immediately
# Small-cap momentum plays are largely uncorrelated to SPY on catalyst days.
# -1% is a normal red morning — Kev trades ICCM day-2 regardless of SPY.
MAX_SPREAD_PCT        = 0.03   # Skip entry if bid-ask spread > 3% of ask price
VWAP_VOL_MULTIPLIER   = 2.0    # Require 2× average minute volume for VWAP reclaim confirmation
VWAP_CONFIRM_TICKS   = 3      # Price must hold above VWAP for this many consecutive polls before entry
MAX_VWAP_EXTENSION   = 0.08   # Don't enter if price is >8% above VWAP — chasing, not buying support
VWAP_PULLBACK_ZONE   = 0.03   # Within 3% of VWAP counts as "at VWAP" for pullback detection
VWAP_PULLBACK_MIN_RUN = 0.05  # High-water must be ≥5% above VWAP before pullback mode activates
MIN_ABS_VOL_ENTRY    = 15_000 # Bounce bar must have ≥15k shares — blocks thin afternoon noise
MOMENTUM_BARS        = 3      # Check last N bars for momentum
MOMENTUM_MIN_AVG_VOL = 10_000 # Avg volume over last N bars must exceed this
MOMENTUM_VOL_ACCEL   = 1.2    # Current bar vol must be ≥1.2× avg of prior bars
MOMENTUM_GREEN_BARS  = 2      # At least N of last 3 bars must close green (close > open)
# Watchdog: a price-quote SDK call has NO built-in timeout, so one hung call can freeze the
# monitor loop forever and leave a position stuck open (the BOXL incident, June 24). Hard-cap
# every quote call, and force-exit if the feed goes dead so a position can never sit blind.
QUOTE_TIMEOUT_SECS   = 8      # Max seconds to wait on a single Webull quote call
STALE_FEED_EXIT_SECS = 90     # If no valid price for this long mid-trade, force-close for safety
# Kev "topping tail / tail off the high" — a candle that spikes up then gets rejected,
# printing a long upper wick at the highs. He treats it as BOTH an entry-skip ("shouldn't
# have taken it, we had a tail off the high") AND his #1 exit ("topping tail off the high,
# I'm done with it"). Confirmed across all 6 daily recaps. See [[project_kev_lessons]].
TOPPING_TAIL_RATIO   = 0.55   # Upper wick ≥55% of the candle's range = rejection at the high
TOKEN_EXPIRY_WARN_DAYS = 7     # Email warning when Webull token expires within 7 days
LOG_FILE              = "/tmp/trade_log.csv"
DRY_RUN    = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
TEST_TRADE = os.environ.get("TEST_TRADE", "").strip().upper()  # e.g. "AAPL" — skips VWAP wait, buys 1 share
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

    # ── Static fundamentals: Webull primary, yfinance fallback ───────────────
    avg_vol   = "N/A"
    mkt_cap   = "N/A"
    float_sh  = "N/A"
    short_pct = "N/A"
    sector    = "N/A"

    wb_fund = _get_webull_fundamentals(ticker)
    if wb_fund["sector"]:
        sector = wb_fund["sector"]
    # easy_to_borrow is a real-time Webull field — use as short interest proxy
    if wb_fund["easy_to_borrow"] is not None:
        short_pct = "ETB" if wb_fund["easy_to_borrow"] else "HTB"   # Hard-To-Borrow = high SI

    # yfinance for float, avg_vol, market_cap — not available in Webull SDK
    try:
        info = yf.Ticker(ticker).info or {}
        if float_sh == "N/A":
            float_sh  = info.get("floatShares") or info.get("sharesOutstanding") or "N/A"
        if avg_vol == "N/A":
            avg_vol   = info.get("averageVolume10days") or info.get("averageVolume") or "N/A"
        if mkt_cap == "N/A":
            mkt_cap   = info.get("marketCap") or "N/A"
        if sector == "N/A":
            sector    = info.get("sector") or info.get("industry") or "N/A"
        # Supplement easy_to_borrow with numeric short% if Webull didn't provide it
        if short_pct == "N/A":
            raw_short = info.get("shortPercentOfFloat")
            if raw_short is not None:
                short_pct = f"{round(raw_short * 100 if raw_short < 1 else raw_short, 1)}%"
        # Price fallback — only if Webull returned nothing
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
    now_et  = datetime.now(EASTERN)
    market_open = now_et.hour > 9 or (now_et.hour == 9 and now_et.minute >= 30)

    # ── Gainers: pre-market screener before open, live market screener after ──
    # After 9:30am PRE_MARKET rankings go stale — switch to real-time movers.
    rank_type  = "CHANGE_RATIO" if market_open else "PRE_MARKET"
    min_chg    = 5 if market_open else 8   # lower bar intraday — moves develop slower
    scan_label = "Live market gainers" if market_open else "Pre-market gainers"
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
            for item in items:
                sym    = item.get("symbol", "")
                chg    = float(item.get("change_ratio") or 0) * 100
                price  = float(item.get("price") or item.get("close") or 0)
                mktcap = float(item.get("market_value") or 0)
                vol    = float(item.get("volume") or 0)
                if not sym or price <= 0:
                    continue
                if price < 0.50 or price > 30:
                    continue
                if chg < min_chg:
                    continue
                gappers[sym] = {
                    "symbol": sym, "change_pct": round(chg, 2),
                    "price": price, "market_cap": mktcap,
                    "premarket_volume": vol, "relative_volume": None,
                    "source": "live_gainer" if market_open else "pre_market_gainer",
                }
            print(f"   {scan_label}: {len(gappers)} candidates after filter")
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
            page_size=50,
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
                if price < 0.50 or price > 30:
                    continue
                if rel_vol < 2.0:   # at least 2× 10-day average volume
                    continue
                if sym in gappers:
                    gappers[sym]["relative_volume"] = rel_vol
                else:
                    if chg >= 3:    # catch early movers — MARCO judges the rest
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

    # ── Float check: Webull instrument primary, yfinance fallback ────────────
    # Small float (<50M) + big gap + volume = the real momentum setup.
    print(f"   Checking float for {len(gappers)} candidates...")
    float_checked = []
    for sym, g in gappers.items():
        try:
            float_shares: float = 0

            # Primary: Webull instrument API
            wb_fund = _get_webull_fundamentals(sym)
            if wb_fund["float_shares"]:
                float_shares = wb_fund["float_shares"]

            # Fallback: yfinance
            if not float_shares:
                try:
                    info = yf.Ticker(sym).info or {}
                    float_shares = float(info.get("floatShares") or info.get("sharesOutstanding") or 0)
                    time.sleep(0.2)   # light rate-limit avoidance
                except Exception:
                    pass

            g["float_shares"] = float_shares
            float_m = float_shares / 1_000_000 if float_shares else 0
            if not float_shares:
                g["float_label"] = "float N/A"
                float_checked.append(g)
            elif float_shares <= 50_000_000:
                g["float_label"] = f"{float_m:.1f}M float"
                float_checked.append(g)
                print(f"   ✅ {sym}: +{g['change_pct']}% | {g['float_label']} ← SMALL FLOAT")
            else:
                print(f"   ❌ {sym}: skipped — {float_m:.0f}M float (too large)")
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

    results = sorted(float_checked, key=_gapper_score, reverse=True)[:15]
    print(f"✅ Morning gapper scan complete — {len(results)} small-float candidates: "
          f"{[r['symbol'] for r in results]}")
    return results


def _mark_traded_today():
    """Tell screener_app a trade was completed today. Blocks second trade (GFV guard)."""
    screener_url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not screener_url:
        return
    try:
        requests.post(f"{screener_url}/api/traded_today",
                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=5)
        print("🔒 Marked traded_today — no second trade allowed (GFV guard)")
    except Exception as e:
        print(f"⚠️  Could not mark traded_today: {e}")


def _already_traded_today() -> bool:
    """Check if a trade was already completed today. Returns True = block new entry."""
    screener_url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not screener_url:
        return False
    try:
        r = requests.get(f"{screener_url}/api/traded_today", timeout=5)
        if r.status_code == 200:
            return r.json().get("traded_today", False)
    except Exception:
        pass
    return False


def _post_watching_to_screener(tickers: list, status: str = "watching"):
    """Push the live watch list to screener_app so the dashboard shows what the bot is monitoring."""
    screener_url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not screener_url:
        return
    try:
        requests.post(f"{screener_url}/api/watching",
                      json={"tickers": tickers, "status": status,
                            "started_at": datetime.now(EASTERN).isoformat()},
                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET},
                      timeout=5)
        print(f"📡 Watch list posted to dashboard: {tickers}")
    except Exception as e:
        print(f"⚠️  Could not post watch list to screener_app: {e}")


def _push_balance_to_screener(balance: float):
    """Push current balance to screener_app so the dashboard always shows live data."""
    screener_url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not screener_url or balance <= 0:
        return
    try:
        requests.post(f"{screener_url}/api/update_account",
                      json={"balance": round(balance, 2)},
                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET},
                      timeout=5)
        print(f"📡 Balance synced to screener_app: ${balance:.2f}")
    except Exception as e:
        print(f"⚠️  Could not sync balance to screener_app: {e}")


def _post_trade_state(state: dict):
    """FIRE-AND-FORGET live trade state to the dashboard. Submitted to the thread pool so the
    monitor loop NEVER waits on it — it cannot delay, block, or hang an exit check."""
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url:
        return
    def _send():
        try:
            requests.post(f"{url}/api/trade_state", json=state,
                          headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=4)
        except Exception:
            pass
    try:
        _aux_executor.submit(_send)
    except Exception:
        pass


# ── Durable open-trade state — persisted to the screener (which has a /data volume) so an
# open position SURVIVES a bot crash/restart/redeploy and still reaches a recorded exit. ──

def _save_open_trade(state: dict):
    """Fire-and-forget upsert of the open position to the screener (durable storage)."""
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url:
        return
    def _send():
        try:
            requests.post(f"{url}/api/open_trade", json=state,
                          headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=4)
        except Exception:
            pass
    try:
        _aux_executor.submit(_send)
    except Exception:
        pass


def _save_open_trade_sync(state: dict) -> bool:
    """BLOCKING, confirmed persist — used at ENTRY so the position is durably stored BEFORE
    monitor_trade runs (closes the crash-right-after-entry window and avoids POST reordering)."""
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url:
        return False
    try:
        r = requests.post(f"{url}/api/open_trade", json=state,
                          headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=6)
        return r.status_code == 200
    except Exception as e:
        print(f"⚠️  Entry persist failed for {state.get('ticker')}: {e}")
        return False


def _clear_open_trade(ticker: str):
    """Remove the open position from durable storage once it has a recorded exit. Blocking
    (must complete before the run ends) but bounded."""
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url:
        return
    try:
        requests.post(f"{url}/api/open_trade/clear", json={"ticker": ticker},
                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=5)
    except Exception:
        pass


def _load_open_trades_from_screener() -> list:
    """On startup, pull any positions that were left open by a prior (crashed) run."""
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url:
        return []
    try:
        r = requests.get(f"{url}/api/open_trades", timeout=8)
        if r.status_code == 200:
            return r.json().get("open_trades", [])
    except Exception:
        pass
    return []


def _recover_orphaned_trades():
    """THE safety net: on startup, close + RECORD any position a crashed prior run left open,
    so every entered trade reaches a recorded exit regardless of what killed the process.
    Records the remainder at the current price (the trade was interrupted)."""
    orphans = _load_open_trades_from_screener()
    if not orphans:
        return
    print(f"♻️  Recovering {len(orphans)} orphaned open trade(s) from a prior run...")
    for o in orphans:
        ticker = (o.get("ticker") or "").upper()
        try:
            if not ticker:
                continue
            entry     = float(o.get("entry_price") or 0)
            remaining = int(o.get("remaining_shares") or 0)
            initial   = int(o.get("initial_shares") or remaining or 1)
            partials  = o.get("partial_fills") or []   # [[qty, price], ...]
            q  = _get_webull_quote(ticker)
            px = float(q.get("last_price") or 0) or float(o.get("last_price") or entry)
            pnl = sum((float(p[1]) - entry) * float(p[0])
                      for p in partials if isinstance(p, (list, tuple)) and len(p) >= 2)
            pnl += (px - entry) * remaining
            pnl_pct = ((px - entry) / entry * 100) if entry > 0 else 0
            print(f"♻️  {ticker}: recording recovered exit — entry ${entry:.2f} → ${px:.2f} "
                  f"({pnl_pct:+.1f}%, ${pnl:+.2f})")
            post_to_dashboard({
                "date":            o.get("entry_date") or datetime.now(EASTERN).strftime("%Y-%m-%d"),
                "ticker":          ticker, "entry_type": o.get("entry_type", ""),
                "entry":           entry, "exit": round(px, 4), "shares": initial,
                "pnl":             round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
                "exit_reason":     "RECOVERED after restart",
                "confidence":      o.get("confidence", ""), "float_shares": "",
                "position_size":   o.get("position_size", 0),
                "account_balance": get_account_balance(),
                "trade_id":        o.get("trade_id"),
            })
            send_alert_email(f"♻️ Recovered trade: {ticker} {pnl_pct:+.1f}%",
                             f"{ticker} was still open when the bot restarted. Closed and recorded "
                             f"at ${px:.2f} (entry ${entry:.2f}) — P&L ${pnl:+.2f} ({pnl_pct:+.1f}%).")
            _clear_open_trade(ticker)
        except Exception as e:
            print(f"⚠️  Recovery error for {ticker or o}: {e}")
            _clear_open_trade(ticker)   # don't let a bad record loop forever


# ============================================================
# DAY-TWO OBSERVATION (observe-only — gather data on how hard day-1 gappers
# behave on day 2). Runs on an ISOLATED daemon thread — never touches the trade
# loop, positions, or orders. Pure read + POST. See [[project_market_observations]].
# ============================================================

def _seed_day2_from_gappers(gappers: list):
    """After the morning scan, carry today's hard gappers into tomorrow's day-2 watch list."""
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url or not gappers:
        return
    try:
        syms = [g.get("symbol") for g in gappers if g.get("symbol")]
        requests.post(f"{url}/api/gappers",
                      json={"date": datetime.now(EASTERN).strftime("%Y-%m-%d"),
                            "gappers": [{"symbol": g.get("symbol"),
                                         "change_pct": g.get("change_pct", 0),
                                         "float_label": g.get("float_label", "")} for g in gappers]},
                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=5)
        requests.post(f"{url}/api/day2_watch",
                      json={"tickers": syms, "mode": "add"},
                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=5)
        print(f"🔭 Day-2 carryover seeded: {syms}")
    except Exception as e:
        print(f"⚠️  Day-2 seed error: {e}")


def _record_day2_observations():
    """Snapshot day-2 behavior of the carried-over gappers. Observe-only; fully isolated."""
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url:
        return
    try:
        r = requests.get(f"{url}/api/day2", timeout=5)
        tickers = r.json().get("day2_watch", []) if r.status_code == 200 else []
    except Exception:
        return
    if not tickers:
        return
    tickers = tickers[-10:]   # cap load: only the 10 most-recent day-2 names per cycle
    recorded = 0
    for t in tickers:
        try:
            q = _get_webull_quote(t, executor=_aux_executor)   # off the trade pool
            price = float(q.get("last_price") or 0)
            if price <= 0:
                continue
            prev = float(q.get("prev_close") or 0)
            gap  = round((price - prev) / prev * 100, 2) if prev > 0 else None
            vwap = float(q.get("vwap") or 0)
            if vwap <= 0:
                bars = get_intraday_bars(t, count=390, executor=_aux_executor)
                vwap = calculate_vwap(bars) if bars else 0
                hi   = max((float(b.get("high") or b.get("h") or 0) for b in bars), default=price) if bars else price
            else:
                hi = price
            vsv = round((price - vwap) / vwap * 100, 2) if vwap > 0 else None
            requests.post(f"{url}/api/observe",
                          json={"ticker": t, "price": round(price, 4),
                                "prev_close": round(prev, 4) if prev else None, "gap_pct": gap,
                                "vwap": round(vwap, 4) if vwap else None, "pct_vs_vwap": vsv,
                                "high": round(hi, 4)},
                          headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=5)
            recorded += 1
        except Exception:
            continue
        time.sleep(0.5)   # de-burst — keep the shared SDK client/executor gentle
    if recorded:
        print(f"🔭 Day-2 observations recorded for {recorded}/{len(tickers)} ticker(s)")


def _day2_observer_loop():
    """Daemon thread: snapshot the day-2 watch list every 10 min during market hours.
    Completely isolated from trading — a crash here can never affect a position."""
    while True:
        try:
            now = datetime.now(EASTERN)
            if now.weekday() < 5 and (9 <= now.hour < 16 or (now.hour == 16 and now.minute == 0)):
                _record_day2_observations()
        except Exception as e:
            print(f"⚠️  Day-2 observer loop error: {e}")
        time.sleep(900)   # every 15 minutes (reduced load)


def get_account_balance():
    """
    Get SETTLED cash only — critical for cash accounts.
    Using unsettled proceeds to fund a new trade and selling before settlement
    triggers a Good Faith Violation (GFV). 3 GFVs = 90-day account restriction.
    Returns settled cash only, with total balance logged for reference.
    """
    _, trade_client = _make_webull_client()
    if trade_client:
        try:
            if not os.environ.get("WEBULL_ACCOUNT_ID", "").strip():
                res = trade_client.account_v2.get_account_list()
                if res.status_code == 200:
                    accounts = res.json()
                    if isinstance(accounts, list) and accounts:
                        global WEBULL_ACCOUNT_ID
                        WEBULL_ACCOUNT_ID = accounts[0].get("account_id", WEBULL_ACCOUNT_ID)
                        print(f"✅ Account ID (auto-discovered): {WEBULL_ACCOUNT_ID}")
                else:
                    print(f"⚠️  Account list error: {res.status_code} {res.text[:200]}")
            else:
                print(f"✅ Account ID (from env): {WEBULL_ACCOUNT_ID}")

            if WEBULL_ACCOUNT_ID:
                bal = trade_client.account_v2.get_account_balance(WEBULL_ACCOUNT_ID)
                if bal.status_code == 200:
                    data = bal.json()
                    if isinstance(data.get("data"), dict):
                        data = data["data"]

                    # Try to get settled cash specifically — cash accounts must only
                    # trade with settled funds to avoid Good Faith Violations
                    settled = float(data.get("settled_cash") or
                                    data.get("settled_funds") or
                                    data.get("cash_available_for_trading") or 0)
                    total   = float(data.get("total_cash_balance") or
                                    data.get("net_cash_balance") or 0)

                    # Always check per-currency assets — this is where Webull puts settled_cash
                    assets = data.get("account_currency_assets") or []
                    for asset in assets:
                        if asset.get("currency") == "USD":
                            settled = float(asset.get("settled_cash") or
                                            asset.get("settled_funds") or 0)
                            total   = float(asset.get("cash_balance") or
                                            asset.get("buying_power") or total or 0)
                            break

                    if settled > 0:
                        print(f"💰 Settled cash: ${settled:.2f} | Total balance: ${total:.2f}")
                        _push_balance_to_screener(settled)
                        return settled
                    if total > 0:
                        # Log all keys in the response so we can find the settled cash field
                        top_keys = list(data.keys())
                        asset_keys = []
                        for asset in (data.get("account_currency_assets") or []):
                            asset_keys = list(asset.keys())
                            break
                        print(f"⚠️  Could not read settled cash separately — using total: ${total:.2f}")
                        print(f"   Raw keys: {top_keys}")
                        if asset_keys:
                            print(f"   Asset keys: {asset_keys}")
                        _push_balance_to_screener(total)
                        return total

                    print("⚠️  Webull API returned $0 — using ACCOUNT_BALANCE env var")
                    print(f"   Raw response: {str(data)[:500]}")
                else:
                    print(f"⚠️  Balance endpoint error: {bal.status_code} {bal.text[:200]}")

        except Exception as e:
            print(f"⚠️  Balance SDK error: {e}")

    # Try screener_app — it persists the last known balance across sessions,
    # which beats the stale ACCOUNT_BALANCE env var after T+1 unsettled periods.
    screener = os.environ.get("SCREENER_URL", "").rstrip("/")
    if screener:
        try:
            r = requests.get(f"{screener}/api/account_balance", timeout=5)
            if r.status_code == 200:
                stored = float(r.json().get("balance") or 0)
                if stored > 0:
                    print(f"💰 Balance from screener_app: ${stored:.2f} (last updated: {r.json().get('updated','?')})")
                    return stored
        except Exception as e:
            print(f"⚠️  Could not read screener balance: {e}")

    manual = float(os.environ.get("ACCOUNT_BALANCE", "0"))
    if manual:
        print(f"💰 Using manual balance (env var): ${manual:.2f}")
        return manual
    print("⚠️  Could not read real balance — defaulting to $100")
    return 100.0


def _get_price_rest(ticker) -> float:
    """REST fallback for current price when MQTT is unavailable. Uses SDK."""
    q = _get_webull_quote(ticker)
    return q.get("last_price", 0) or 0


_quote_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4,
                                                        thread_name_prefix="wb_quote")
# Separate pool for NON-trade work (dashboard posts, durable-state persistence, day-2
# observer). Kept off _quote_executor so observation/posting load can never starve the
# exit-critical price feed (the contention the audit flagged + today's crash trigger).
_aux_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3,
                                                      thread_name_prefix="wb_aux")


def _get_webull_quote(ticker, executor=None) -> dict:
    """
    Fetch a live real-time quote via the official Webull SDK (properly authenticated).
    Falls back to empty dict on any error so callers can fall back to yfinance.

    The SDK's HTTP call has no timeout — a single hung call would freeze the whole monitor
    loop (the BOXL freeze, June 24). Run it on a worker with a hard QUOTE_TIMEOUT_SECS cap so
    it can never block; on timeout we return {} and the caller treats it as "no price".
    """
    try:
        dc = _get_data_client()
        if not dc:
            return {}

        future = (executor or _quote_executor).submit(
            dc.market_data.get_snapshot,
            symbols=ticker,
            category="US_STOCK",
            extend_hour_required=True,
        )
        try:
            resp = future.result(timeout=QUOTE_TIMEOUT_SECS)
        except concurrent.futures.TimeoutError:
            print(f"⚠️  Webull quote TIMEOUT for {ticker} (>{QUOTE_TIMEOUT_SECS}s) — treating as no price")
            return {}
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

        vwap_raw = (d.get("vwap") or d.get("vwap_price") or d.get("average_price") or
                    d.get("avgPrice") or d.get("dayAvgPrice") or d.get("avgVol") or 0)
        vwap = float(vwap_raw)
        if vwap <= 0:
            all_keys = [k for k in d.keys() if "avg" in k.lower() or "vwap" in k.lower() or "wap" in k.lower()]
            print(f"⚠️  VWAP=0 for {ticker} | candidate keys: {all_keys} | all keys: {list(d.keys())[:20]}")

        return {
            "last_price":            last,
            "bid":                   bid,
            "ask":                   ask,
            "volume":                vol,
            "prev_close":            pclose,
            "change_ratio":          round(chg_r * 100 if abs(chg_r) < 1 else chg_r, 2),
            "pre_market_price":      pre_p,
            "pre_market_change_pct": round(pre_r, 2),
            "vwap":                  vwap,
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
    Map the stock's sector to its ETF and fetch that ETF's pre-market direction via Webull.
    """
    etf = SECTOR_ETFS.get(sector)
    if not etf:
        return {"etf": None, "sector": sector, "change_pct": None, "sentiment": "UNKNOWN"}
    try:
        wb  = _get_webull_quote(etf)
        # pre_market_change_pct from _get_webull_quote is already in percent — don't normalize again
        chg = wb.get("pre_market_change_pct") or wb.get("change_pct") or 0
        if chg == 0:
            # Derive from price vs prev_close when change field is missing
            price = wb.get("pre_market_price") or wb.get("last_price") or 0
            prev  = wb.get("prev_close") or 0
            if price and prev:
                chg = (price - prev) / prev * 100
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


def check_level2(ticker, entry_price) -> tuple[bool, dict]:
    """
    Fetch Level 2 order book from Webull and check for sell walls above entry.
    Returns (ok, details) — ok=False means heavy resistance, skip entry.

    Checks:
    1. Sell wall: any single ask level with size > 3× the average ask size
       within 5% above entry = wall blocking upside
    2. Buy/sell imbalance: total bid volume vs total ask volume within 5% of price.
       If asks outweigh bids by > 2:1, sellers are in control
    3. Thin bids: if total bid support within 3% below entry is < 500 shares,
       there's no floor if it drops
    """
    details = {"wall_at": None, "bid_vol": 0, "ask_vol": 0, "ratio": 0, "reason": ""}
    try:
        dc = _get_data_client()
        if not dc:
            print(f"⚠️  {ticker}: no data client for L2 — skipping check")
            return True, details

        resp = dc.market_data.get_quotes(
            symbol=ticker,
            category="US_STOCK",
            depth=20,
        )
        if resp.status_code != 200:
            print(f"⚠️  {ticker}: L2 request failed ({resp.status_code}) — skipping check")
            return True, details

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

        asks_raw = d.get("asks", d.get("askList", d.get("ask_list", [])))
        bids_raw = d.get("bids", d.get("bidList", d.get("bid_list", [])))

        if not asks_raw and not bids_raw:
            all_keys = list(d.keys())[:25]
            print(f"⚠️  {ticker}: L2 no bid/ask arrays found | keys: {all_keys}")
            return True, details

        asks = []
        for a in asks_raw:
            price = float(a.get("price") or a.get("p") or 0)
            size  = float(a.get("volume") or a.get("size") or a.get("v") or a.get("s") or 0)
            if price > 0:
                asks.append((price, size))

        bids = []
        for b in bids_raw:
            price = float(b.get("price") or b.get("p") or 0)
            size  = float(b.get("volume") or b.get("size") or b.get("v") or b.get("s") or 0)
            if price > 0:
                bids.append((price, size))

        upper_bound = entry_price * 1.05
        lower_bound = entry_price * 0.97

        nearby_asks = [(p, s) for p, s in asks if p <= upper_bound]
        nearby_bids = [(p, s) for p, s in bids if p >= lower_bound]

        total_ask_vol = sum(s for _, s in nearby_asks)
        total_bid_vol = sum(s for _, s in nearby_bids)
        details["ask_vol"] = int(total_ask_vol)
        details["bid_vol"] = int(total_bid_vol)

        # Check 1: Sell wall — any single level with outsized volume
        if nearby_asks:
            avg_ask_size = total_ask_vol / len(nearby_asks)
            for price, size in nearby_asks:
                if avg_ask_size > 0 and size >= avg_ask_size * 3 and size >= 500:
                    details["wall_at"] = price
                    details["reason"] = f"sell wall {int(size)} shares @ ${price:.2f}"
                    print(f"🚫 {ticker} L2: SELL WALL — {int(size)} shares @ ${price:.2f} "
                          f"({size/avg_ask_size:.1f}× avg ask size)")
                    return False, details

        # Check 2: Buy/sell imbalance
        if total_bid_vol > 0:
            ratio = total_ask_vol / total_bid_vol
            details["ratio"] = round(ratio, 2)
            if ratio >= 2.0:
                details["reason"] = f"sellers dominate {ratio:.1f}:1 (ask {int(total_ask_vol)} vs bid {int(total_bid_vol)})"
                print(f"🚫 {ticker} L2: SELL PRESSURE — asks {int(total_ask_vol)} vs bids {int(total_bid_vol)} "
                      f"({ratio:.1f}:1 ratio)")
                return False, details
        elif total_ask_vol > 0:
            details["reason"] = "no bid support visible"
            print(f"🚫 {ticker} L2: NO BIDS — {int(total_ask_vol)} shares on ask, nothing on bid")
            return False, details

        # Check 3: Thin bids (no floor)
        close_bids = [(p, s) for p, s in bids if p >= entry_price * 0.97]
        close_bid_vol = sum(s for _, s in close_bids)
        if close_bid_vol < 500 and total_ask_vol > 1000:
            details["reason"] = f"thin bids ({int(close_bid_vol)} shares within 3%)"
            print(f"🚫 {ticker} L2: THIN BIDS — only {int(close_bid_vol)} shares within 3% below entry")
            return False, details

        ratio_str = f"{details['ratio']:.1f}:1" if total_bid_vol > 0 else "N/A"
        print(f"✅ {ticker} L2: bids {int(total_bid_vol)} vs asks {int(total_ask_vol)} ({ratio_str}) — OK")
        return True, details

    except Exception as e:
        print(f"⚠️  {ticker}: L2 error: {e} — skipping check")
        return True, details


def check_momentum(ticker) -> tuple[bool, dict]:
    """
    Fetch recent 1-min bars and verify Kev-style momentum:
    1. Average volume over last MOMENTUM_BARS bars ≥ MOMENTUM_MIN_AVG_VOL
    2. Current bar volume ≥ MOMENTUM_VOL_ACCEL × avg of prior bars (accelerating)
    3. At least MOMENTUM_GREEN_BARS of last 3 bars are green (close > open)
    Returns (ok, details_dict).
    """
    details = {"passed": False, "reason": ""}
    try:
        bars = get_intraday_bars(ticker, count=MOMENTUM_BARS + 1)
        if len(bars) < MOMENTUM_BARS:
            details["reason"] = f"only {len(bars)} bars available (need {MOMENTUM_BARS})"
            print(f"⚠️  {ticker} momentum: {details['reason']} — passing by default")
            return True, details

        recent = bars[-(MOMENTUM_BARS):]
        prior = bars[-(MOMENTUM_BARS + 1):-1] if len(bars) > MOMENTUM_BARS else recent[:-1]

        volumes = []
        for b in recent:
            v = float(b.get("volume") or b.get("v") or 0)
            volumes.append(v)
        avg_vol = sum(volumes) / len(volumes) if volumes else 0
        details["avg_vol"] = int(avg_vol)

        if avg_vol < MOMENTUM_MIN_AVG_VOL:
            details["reason"] = f"avg vol {int(avg_vol):,} < {MOMENTUM_MIN_AVG_VOL:,} min"
            print(f"❌ {ticker} momentum FAIL: {details['reason']}")
            return False, details

        prior_vols = [float(b.get("volume") or b.get("v") or 0) for b in prior]
        prior_avg = sum(prior_vols) / len(prior_vols) if prior_vols else 0
        current_vol = volumes[-1] if volumes else 0
        details["current_vol"] = int(current_vol)
        details["prior_avg_vol"] = int(prior_avg)

        if prior_avg > 0 and current_vol < prior_avg * MOMENTUM_VOL_ACCEL:
            details["reason"] = (f"vol fading: current {int(current_vol):,} < "
                                 f"{MOMENTUM_VOL_ACCEL}× prior avg {int(prior_avg):,}")
            print(f"❌ {ticker} momentum FAIL: {details['reason']}")
            return False, details

        green_count = 0
        check_bars = recent[-3:] if len(recent) >= 3 else recent
        for b in check_bars:
            o = float(b.get("open") or b.get("o") or 0)
            c = float(b.get("close") or b.get("c") or 0)
            h = float(b.get("high") or b.get("h") or c)
            l = float(b.get("low") or b.get("l") or c)
            bar_range = h - l
            if c > o and bar_range > 0 and (c - l) / bar_range >= 0.5:
                green_count += 1
        details["green_bars"] = green_count

        if green_count < MOMENTUM_GREEN_BARS:
            details["reason"] = f"only {green_count}/{len(check_bars)} green bars (need {MOMENTUM_GREEN_BARS})"
            print(f"❌ {ticker} momentum FAIL: {details['reason']}")
            return False, details

        # Kev "tail off the high" — don't enter into a candle that just got rejected at the
        # highs. Check the most recent COMPLETED bar (bars[-1] is the in-progress bar).
        if len(bars) >= 2 and is_topping_tail(bars[-2]):
            details["reason"] = "topping tail on last bar — rejection at the high, skip entry"
            print(f"❌ {ticker} momentum FAIL: {details['reason']}")
            return False, details

        details["passed"] = True
        print(f"✅ {ticker} momentum OK: avg vol {int(avg_vol):,}, "
              f"current {int(current_vol):,}, {green_count} green bars")
        return True, details

    except Exception as e:
        print(f"⚠️  {ticker}: momentum check error: {e} — passing by default")
        details["reason"] = str(e)
        return True, details


def get_intraday_bars(ticker, count=30, executor=None):
    """Fetch 1-minute intraday bars for VWAP calculation. Uses SDK.

    The SDK call has no timeout — used inside monitor_trade (EMA9 stop + topping-tail exit),
    so a hung call could freeze the loop (same class as the BOXL freeze). Run it on the shared
    worker with a hard QUOTE_TIMEOUT_SECS cap so it can never block the monitor loop.
    Pass executor=_aux_executor (e.g. the day-2 observer) to keep load OFF the trade pool."""
    try:
        dc = _get_data_client()
        if not dc:
            return []
        future = (executor or _quote_executor).submit(
            dc.market_data.get_history_bar,
            symbol=ticker,
            category="US_STOCK",
            timespan="M1",
            count=str(count),
        )
        try:
            resp = future.result(timeout=QUOTE_TIMEOUT_SECS)
        except concurrent.futures.TimeoutError:
            print(f"⚠️  Intraday bars TIMEOUT for {ticker} (>{QUOTE_TIMEOUT_SECS}s) — returning none")
            return []
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


def get_intraday_bars_full(ticker):
    """
    Fetch today's 1-minute bars INCLUDING pre-market via yfinance (prepost=True).
    Used ONLY for VWAP calculation so the bot's VWAP matches chart VWAP.
    For gap stocks with heavy pre-market volume, omitting pre-market bars produces
    a fake low VWAP that triggers false reclaim signals (e.g. CAST $9.23 vs real $11.21).
    Falls back to SDK bars if yfinance fails.
    """
    try:
        df = yf.download(ticker, period="1d", interval="1m", prepost=True,
                         progress=False, auto_adjust=False)
        if df is None or df.empty:
            return []
        if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        bars = []
        for _, row in df.iterrows():
            try:
                bars.append({
                    "high":   float(row["High"]),
                    "low":    float(row["Low"]),
                    "close":  float(row["Close"]),
                    "volume": float(row["Volume"]),
                })
            except (TypeError, ValueError):
                continue
        return bars
    except Exception as e:
        print(f"⚠️  Full-day bars (yfinance) error for {ticker}: {e}")
        return []


def calculate_90ma(bars) -> float:
    """90-period simple moving average of close prices (Kev's second entry filter alongside VWAP)."""
    if not bars:
        return 0.0
    closes = []
    for b in bars[-90:]:
        c = b.get("close") or b.get("c") or b.get("vwap") or 0
        try:
            closes.append(float(c))
        except (TypeError, ValueError):
            pass
    return sum(closes) / len(closes) if closes else 0.0

def _calc_ema(closes: list, period: int) -> float:
    if len(closes) < period:
        return 0.0
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for c in closes[period:]:
        ema = c * k + ema * (1 - k)
    return ema


def _extract_closes(bars) -> list:
    closes = []
    for b in bars:
        c = b.get("close") or b.get("c") or 0
        try:
            closes.append(float(c))
        except (TypeError, ValueError):
            pass
    return closes


def calculate_ema9(bars) -> float:
    return _calc_ema(_extract_closes(bars), EMA_PERIOD)


def calculate_ema20(bars) -> float:
    return _calc_ema(_extract_closes(bars), EMA20_PERIOD)


def calculate_ema90(bars) -> float:
    """EMA90 — Kev's key deeper-pullback level. DATA-ONLY: recorded at entry, not used to gate
    trades yet. Returns 0.0 if there aren't enough bars to be meaningful."""
    closes = _extract_closes(bars)
    if len(closes) < EMA90_PERIOD:
        return 0.0
    return _calc_ema(closes, EMA90_PERIOD)


def is_topping_tail(bar) -> bool:
    """Kev's 'topping tail / tail off the high' — a candle whose upper wick is ≥
    TOPPING_TAIL_RATIO of its full range = price spiked up and got rejected at the high.
    Used as an entry-skip (don't buy into rejection) and as an exit (momentum is done)."""
    try:
        o = float(bar.get("open")  or bar.get("o") or 0)
        c = float(bar.get("close") or bar.get("c") or 0)
        h = float(bar.get("high")  or bar.get("h") or 0)
        l = float(bar.get("low")   or bar.get("l") or 0)
    except (TypeError, ValueError):
        return False
    rng = h - l
    if rng <= 0:
        return False
    upper_wick = h - max(o, c)
    return (upper_wick / rng) >= TOPPING_TAIL_RATIO


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
                        gappers=None, market_context=None, evening_watchlist=None):
    print("🧠 Sending data to Claude Sonnet AI for analysis...")

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

    # Build evening watchlist section for MARCO
    if evening_watchlist and evening_watchlist.get("top_picks"):
        ew_picks = evening_watchlist["top_picks"]
        ew_lines = []
        for p in ew_picks:
            ew_lines.append(
                f"  {p['ticker']}: {p.get('thesis','')} | "
                f"Watch level: ${p.get('key_level',0):.2f} | "
                f"Entry trigger: {p.get('entry_trigger','')} | "
                f"Confidence: {p.get('confidence','')} | "
                f"Risk: {p.get('risk_note','')}"
            )
        evening_section = (
            "LAST NIGHT'S WATCHLIST (MARCO's pre-screened picks from yesterday evening):\n"
            + "\n".join(ew_lines)
            + "\n\nNOTE: These were pre-screened last night. Confirm they are still showing "
            "momentum this morning before treating as GO. If pre-market confirms the thesis, "
            "weight these picks HIGHER than cold gapper scan finds."
        )
    else:
        evening_section = "LAST NIGHT'S WATCHLIST: Not available (evening scan may not have run yet)"

    email_safe = _sanitize_for_prompt(email_content)

    prompt = f"""
You are MARCO — a seasoned small-cap momentum trader with 15 years of experience
specializing in gap-and-go plays on micro-float stocks. You trade for Marcos Olivera.

YOUR PERSONALITY AND EDGE:
- You are disciplined and skeptical before you are opportunistic
- You ask "what's the downside and why?" before "how much can I make?"
- You have seen every trap: the gap-and-crap, the halt, the fake breakout, the
  dilution dump. You do not get fooled twice.
- You recognize the difference between a catalyst-driven gap with real follow-through
  and a mystery volume gap that fades hard 10 minutes after open
- You pass on genuinely weak setups, but you are not paralyzed by the pursuit
  of perfection — a clean 2-signal setup is a trade, not a reason to hesitate
- When a setup is genuinely strong — tight float, real catalyst, accelerating volume,
  clean chart — you attack it with full conviction. No hesitation.
- You think in risk/reward. A 3:1 setup on a 0.5M float with a PR catalyst is your
  bread and butter. A 1.2:1 setup on a 10M float with no news is a skip.
- Your reputation is built on consistency and capital preservation, not on being
  right every day

Today's date: {datetime.now(EASTERN).strftime("%A, %B %d, %Y")}
Account balance: ${account_balance:.2f}
Market open: 9:30am ET
Entry: VWAP + 90MA reclaim — price must hold above BOTH for 3 consecutive polls (≈9s) with 1.5× volume
Trading window: Entry by 3:30pm ET, force close all positions by 3:45pm ET

{market_context_section}

{evening_section}

KEV'S WATCHLIST EMAIL/TRANSCRIPT:
{email_safe}

LIVE PRE-MARKET DATA FROM WEBULL (Kev's picks):
{market_text}

{gapper_section}

━━━ HOW TO SCORE EACH SETUP ━━━

Score each candidate on these DATA signals (+1 point each):
  ✦ Float < 10M shares                    → tight float, big moves possible
  ✦ Gap 8–50% pre-market, OR gap >50%     → real momentum (see volume rule below)
    with pre-market volume > 1× float
  ✦ Relative volume ≥ 2x                  → real buyers showing up
  ✦ Pre-mkt volume ACCELERATING           → buying is building, not fading
  ✦ Short interest > 15%                  → squeeze fuel
  ✦ Sector ETF is BULLISH                 → wind at its back
  ✦ Price $0.50–$15                       → tradeable size on this account
  ✦ News catalyst exists                  → real driver behind the move
  ✦ Kev specifically flagged it           → professional read + community awareness, +1 point
  ✦ Day-2 continuation (ran 20%+ previous → proven buyers exist, story still alive
    session and holding structure today)

VOLUME AS CATALYST: When pre-market volume exceeds 1× the float before open,
that volume IS the catalyst — someone is in this stock. A 112% gap with 56M
pre-market shares on a 16M float is not a mystery pump, it is institutional or
whale activity. Do NOT disqualify it on gap% alone. Score it and trade it.

━━━ POSITION SIZING — CATALYST DETERMINES SIZE ━━━

The score tells you WHAT to trade. The catalyst tells you HOW MUCH.

  CATALYST PRESENT (news, FDA, earnings, OR pre-mkt volume > 1× float):
    Score 5+  → $100 (HIGH — full size, attack it)
    Score 3–4 → $75  (MEDIUM)
    Score 1–2 → $50  (LOW)

  NO CATALYST, but Kev flagged it (day-2 continuation or his specific pick):
    Score 5+  → $75  (MEDIUM max — Kev's read is real but no confirmed news)
    Score 3–4 → $50  (LOW)
    Score 1–2 → $20  (MINIMUM)

  NO CATALYST, NOT flagged by Kev (pure technical play):
    Any score → $20  (MINIMUM — no story behind the move)

  Score 0   → NO-TRADE regardless of catalyst

This sizing rule exists because: every losing trade so far has been a
no-catalyst technical play entered at $75-$100. ATPC, LPA, ICCM, CLWT —
all had clean setups, all faded immediately. No story = no sustained buying.
Save full size for when there is a REASON buyers will keep showing up.

THE SCORE IS THE DECISION ON WHAT TO TRADE. THE CATALYST IS THE DECISION
ON SIZE. Do not use "no catalyst" to skip a trade entirely — use it to size
down. A $20 trade on a clean technical setup is fine. A $100 trade on a
no-catalyst gap is not.

━━━ HARD NO-GO (skip only for these) ━━━
  ✗ Active SEC halt or T12 restriction
  ✗ Stock price > full account balance (can't buy 1 share)
  ✗ Gap > 300% pre-market with no volume (halt trap)
  ✗ Active dilution/offering news in the headline
  ✗ Already confirmed gap-and-crap (trading below open immediately)

━━━ SUB-$1 PLAYS ━━━
  Stocks under $1 at scan time can be valid — CCTG opened at $0.91 and ran to $2.09.
  The pattern: tiny float + real catalyst + crosses $1 at open = explosive move.
  Score them normally. Extra scrutiny on spread and float quality, but don't auto-reject.

━━━ MARKET CONTEXT ━━━
  SPY < -2.5%: skip the day — genuine crash, momentum plays fail
  SPY -2.5% to 0%: normal red day — trade the setup, not the macro.
    Small-cap momentum is uncorrelated to SPY on catalyst-driven days.
  SPY > 0%: tailwind — full catalyst-based sizing applies

  Do NOT use a mildly red market to reduce size beyond the catalyst rule above.
  The catalyst rule already accounts for risk. SPY context is informational only
  unless it is a genuine crash day (-2.5%+).

━━━ KEV'S METHODOLOGY (internalize this — it's how the best setups are found) ━━━
  Kev is a professional small-cap momentum trader. His entry framework:

  DAY-2 CONTINUATION (Kev's bread and butter):
  A stock that ran 20%+ yesterday with buyers confirmed (closed in top half of range,
  held structure) is often a better setup than a fresh no-catalyst gapper. Proven
  buyers exist. The story is still alive. Kev trades day-2 plays more than anything
  else. If yesterday's big mover is gapping up again or showing pre-market strength,
  score it as day-2 continuation (+1 point) and treat it as a higher-conviction setup
  than a fresh mystery gapper. ICCM ran 200% one day — day-2 potential is real.
  CAST ran 35% one day — day-2 potential is real.

  ENTRY TRIGGER — VWAP + 90MA reclaim together:
  The bot watches for price to hold above BOTH VWAP and the 90-period MA for 3 ticks
  with 1.5× volume. This is Kev's exact setup — a single VWAP cross without 90MA
  confirmation is a false signal (what burned us on SUGP).

  PRE-MARKET HIGHS = RESISTANCE:
  If the stock tested VWAP in pre-market and got rejected twice, those rejection highs
  are now resistance. The play only works if price can reclaim AND hold above those highs.
  Flag this in your analysis: "pre-market VWAP rejections at $X.XX — needs to clear that."

  PSYCHOLOGICAL LEVELS ($1, $2, $3, $5, $10):
  Whole dollar levels are massive resistance. Kev's CCTG entry was specifically at
  $1.10 — he waited for buyers to step OVER $1.00 before entering. When a stock is
  approaching a whole dollar level, note it: "key psychological level at $X — entry is
  the BREAK and HOLD above it, not the approach."

  BOTTOMING TAILS ON PULLBACKS = RE-ENTRY:
  After the first squeeze, Kev looks for pullbacks to VWAP + 90MA with wicks off the
  low (buyers rejecting the dip). These are valid re-entries. Note in your plan if the
  setup has a second-leg potential after the first halt/squeeze.

  BACKSIDE AWARENESS:
  Once a stock makes its big move and fails to break the next whole-dollar level,
  the move is over. "Overtrading the backside" is how profits get given back.
  Flag the exit signal: rejection candle at key level = done, take full exit.

  KEV'S EMAIL:
  If Kev flagged it: real community awareness + professional read = +1 point (scored above).
  If Kev gave a specific break level → that IS the entry trigger, treat it as the psychological level.
  If his email is general commentary → context only.

━━━ CATALYST NOTE ━━━
  News = real signal that drives sustained moves. "No news found" ≠ no trade — small floats
  move on order flow, squeeze, and sector momentum. But confirmed catalyst (PR, FDA, earnings
  beat, halt+resume) dramatically increases conviction. Weight it heavily when present.

  IMPORTANT — Pre-market volume fading does NOT mean the play is dead:
  Community watchlist plays (like Kev's picks) often show fading pre-market volume because
  retail waits for the open. The real move comes AT and AFTER 9:30am. Do NOT reject a
  Kev-flagged catalyst play solely because pre-market volume is light. Judge it on float,
  gap, and catalyst strength instead.

  Only skip on confirmed BAD news (dilution, offering, halt, SEC investigation).

TRADING RULES (bot handles execution):
- Entry: VWAP + 90MA reclaim confirmed by 3 consecutive ticks above BOTH levels with 1.5× volume — no fakes
- Stop: 7% below entry
- +10%: stop to breakeven
- +8% AM / +5% PM: sell half, floor at entry, trail rest
- +20%: full exit
- Hard close: 3:45pm ET (force exit all positions before market close)

Respond in this EXACT JSON format:
{{
  "analysis_date": "YYYY-MM-DD",
  "market_summary": "2-3 sentence overview",
  "tickers": [
    {{
      "ticker": "SYMBOL",
      "verdict": "GO" or "NO-GO",
      "score": 0,
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
    "confidence": "HIGH/MEDIUM/LOW/MINIMUM",
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
            model="claude-sonnet-4-6",
            max_tokens=8000,
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
            print("✅ Claude Sonnet analysis complete!")
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

INTRADAY_RESCAN_INTERVAL = 5 * 60   # Rescan live market every 5 minutes while watching


def wait_for_flat_top_entry(candidates: list, stream: WebullStream,
                             rescan_callback=None, traded_tickers: set = None):
    """
    v10 entry detection: watches candidates for TWO entry types:
    1. Flat top breakout — 4-bar consolidation <8% range, price breaks window high
    2. EMA bounce — price pulled back to EMA9, bounces with 2:1 R:R to prior high
    Both require price > VWAP and EMA9 > EMA20 (bullish stack).
    No new entries after 11:00am ET.
    Returns list of (ticker, entry_price, vwap, entry_type, extra) where
    entry_type is "flat_top" or "ema_bounce" and extra has stop/target info.
    """
    if traded_tickers is None:
        traded_tickers = set()
    print(f"\n⏳ [v8] Watching {len(candidates)} candidate(s) for flat top breakout: {', '.join(candidates)}")

    cache = {t: {"bars": [], "vwap": 0.0, "fetched": 0.0} for t in candidates}
    last_rescan = time.time()

    while True:
        now = datetime.now(EASTERN)

        # Entry cutoff — skipped in DRY_RUN for maximum practice data
        if not DRY_RUN:
            past_entry_cutoff = (now.hour > ENTRY_CUTOFF_HOUR or
                                 (now.hour == ENTRY_CUTOFF_HOUR and now.minute >= ENTRY_CUTOFF_MIN))
            if past_entry_cutoff:
                print(f"⏰ 11:00am entry cutoff — no entry detected. Holding cash.")
                return []

        if now.hour < 9 or (now.hour == 9 and now.minute < 30):
            mins = (9 * 60 + 30) - (now.hour * 60 + now.minute)
            print(f"⏳ Market opens in ~{mins} min...")
            time.sleep(30)
            continue

        # Refresh bars for each ticker every 30s
        for t in candidates:
            if time.time() - cache[t]["fetched"] >= VWAP_BAR_CACHE_SECS:
                fresh = get_intraday_bars(t, count=max(EMA_BOUNCE_LOOKBACK + EMA20_PERIOD + 5, 50))
                if fresh:
                    cache[t]["bars"] = fresh
                full_bars = get_intraday_bars(t, count=390)
                if full_bars:
                    calc_vwap = calculate_vwap(full_bars)
                    if calc_vwap > 0:
                        cache[t]["vwap"] = calc_vwap
                        print(f"📊 {t} VWAP from Webull bars: ${calc_vwap:.2f}")
                    else:
                        print(f"⚠️  {t} VWAP=0 — Webull bars had no volume data")
                else:
                    print(f"⚠️  {t} VWAP unavailable — no Webull bars returned")
                cache[t]["fetched"] = time.time()

        # Check each ticker for flat top breakout OR EMA bounce
        status_parts = []
        breakouts = []
        for t in candidates:
            bars = cache[t]["bars"]
            vwap = cache[t]["vwap"]
            price = stream.get_price(t)

            if not bars or price <= 0:
                status_parts.append(f"{t}:no data")
                continue

            completed = bars[:-1]
            if len(completed) < EMA20_PERIOD + 2:
                status_parts.append(f"{t}:${price:.2f} (need more bars)")
                continue

            vwap_tag = f" VWAP:${vwap:.2f}" if vwap > 0 else ""
            ema9  = calculate_ema9(completed)
            ema20 = calculate_ema20(completed)
            ema90 = calculate_ema90(completed)   # DATA-ONLY — recorded at entry, not a filter
            found_entry = False

            # ── Entry type 1: Flat top breakout ──────────────────────
            if len(completed) >= FLAT_TOP_WINDOW:
                window = completed[-FLAT_TOP_WINDOW:]
                highs = [float(b.get("high") or b.get("h") or b.get("close") or b.get("c") or 0) for b in window]
                lows  = [float(b.get("low")  or b.get("l") or b.get("close") or b.get("c") or 0) for b in window]
                w_high = max(h for h in highs if h > 0)
                w_low  = min(l for l in lows  if l > 0)

                if w_low > 0:
                    rng = (w_high - w_low) / w_low
                    is_flat = rng <= FLAT_TOP_MAX_RANGE

                    if is_flat and price > w_high:
                        if vwap <= 0:
                            status_parts.append(f"{t}:${price:.2f} BREAK but no VWAP — skipped")
                            continue
                        if price < vwap:
                            status_parts.append(f"{t}:${price:.2f} BREAK but below VWAP{vwap_tag}")
                            continue
                        vwap_ext = (price - vwap) / vwap
                        if vwap_ext > MAX_VWAP_EXTENSION:
                            status_parts.append(f"{t}:${price:.2f} BREAK but {vwap_ext*100:.1f}% above VWAP — too extended")
                            continue
                        print(f"\n✅ {t} FLAT TOP BREAKOUT! ${price:.2f} > window high ${w_high:.2f} "
                              f"(range {rng*100:.1f}%, {FLAT_TOP_WINDOW}-bar window)"
                              + (f" VWAP:${vwap:.2f}" if vwap > 0 else ""))
                        breakouts.append((t, price, vwap, "flat_top", {"ema90": round(ema90, 4)}))
                        found_entry = True
                    elif is_flat:
                        gap_to_break = (w_high - price) / price * 100
                        status_parts.append(f"{t}:${price:.2f} flat({rng*100:.1f}%) hi:${w_high:.2f} -{gap_to_break:.1f}%{vwap_tag}")

            # ── Entry type 2: EMA bounce ─────────────────────────────
            if not found_entry and ema9 > 0 and ema20 > 0 and ema9 > ema20:
                prev_close = float(completed[-1].get("close") or completed[-1].get("c") or 0)
                prev_ema9  = _calc_ema(_extract_closes(completed[:-1]), EMA_PERIOD)

                touched = prev_close > 0 and prev_ema9 > 0 and prev_close <= prev_ema9 * (1 + EMA_BOUNCE_TOUCH)
                bounced = price > ema9
                above_vwap = vwap > 0 and price > vwap
                vwap_ext = (price - vwap) / vwap if vwap > 0 else 0
                not_extended = vwap_ext <= MAX_VWAP_EXTENSION

                if touched and bounced and above_vwap and not_extended:
                    lookback_bars = completed[-EMA_BOUNCE_LOOKBACK:]
                    prior_high = max(float(b.get("high") or b.get("h") or b.get("close") or b.get("c") or 0) for b in lookback_bars)

                    if prior_high >= price * 1.02:
                        ema_stop = ema9 * (1 - EMA_STOP_BUFFER)
                        risk = price - ema_stop
                        reward = prior_high - price
                        if risk > 0 and reward / risk >= MIN_RR:
                            vol_now = float(completed[-1].get("volume") or completed[-1].get("v") or 0)
                            vol_prior = sum(float(b.get("volume") or b.get("v") or 0) for b in completed[-4:-1]) / 3 if len(completed) >= 4 else 0
                            vol_ok = vol_prior <= 0 or vol_now >= vol_prior * EMA_BOUNCE_VOL_MULT

                            if vol_ok:
                                print(f"\n✅ {t} EMA BOUNCE! ${price:.2f} bounced off EMA9 ${ema9:.2f} "
                                      f"(R:R {reward/risk:.1f}:1, target ${prior_high:.2f}, stop ${ema_stop:.2f})"
                                      + (f" VWAP:${vwap:.2f}" if vwap > 0 else ""))
                                breakouts.append((t, price, vwap, "ema_bounce", {
                                    "ema_stop": round(ema_stop, 4),
                                    "prior_high": round(prior_high, 4),
                                    "ema90": round(ema90, 4),
                                }))
                                found_entry = True

            if not found_entry and t not in [s.split(":")[0] for s in status_parts]:
                status_parts.append(f"{t}:${price:.2f} EMA9:${ema9:.2f}{vwap_tag}")

        if breakouts:
            return breakouts

        if status_parts:
            print(f"📊 {' | '.join(status_parts)}")

        # 5-min live rescan
        if rescan_callback and time.time() - last_rescan >= INTRADAY_RESCAN_INTERVAL:
            print(f"🔄 5-min rescan — checking live market for new setups...")
            new_candidates = rescan_callback(exclude=traded_tickers | set(candidates))
            if new_candidates:
                for t in new_candidates:
                    if t not in candidates:
                        candidates.append(t)
                        cache[t] = {"bars": [], "vwap": 0.0, "fetched": 0.0}
                        print(f"   ➕ Added {t} to flat top watch list")
            last_rescan = time.time()

        time.sleep(VWAP_BAR_CACHE_SECS)


def wait_for_vwap_entry(candidates: list, stream: WebullStream,
                         rescan_callback=None, traded_tickers: set = None):
    """
    Watches ALL candidate tickers simultaneously every loop tick.
    Takes the first one that holds above VWAP for 3 consecutive polls with 1.5× volume confirmation.
    Priority order is preserved — if two trigger on the same tick, the
    higher-ranked one wins.
    Rescans the live market every 10 minutes to pick up new movers.
    Hard cutoff: 3:30pm ET.
    Returns (winner_ticker, entry_price, vwap) or (None, None, None).
    """
    if traded_tickers is None:
        traded_tickers = set()
    print(f"\n⏳ Watching {len(candidates)} candidate(s) for VWAP entry (reclaim or pullback bounce): {', '.join(candidates)}")

    # Per-ticker bar cache.
    # "bars" = regular-session SDK bars (volume comparison + 90MA)
    # "vwap" = computed from full-day yfinance bars (includes pre-market) so it
    #          matches the chart VWAP rather than a misleadingly low intraday figure.
    cache = {t: {"bars": [], "vwap": 0.0, "ma90": 0.0, "fetched": 0.0,
                 "ticks_above": 0, "high_water": 0.0, "pullback_mode": False}
             for t in candidates}

    # Seed high_water from today's intraday bars so the bot knows about
    # any run that happened before monitoring started (e.g. morning gap).
    # Without this, a stock that ran to $9 at open then pulled back looks
    # identical to one that never ran — and the pullback logic never fires.
    # Also drops candidates that have no valid setup path from here.
    print("📈 Seeding prior-run history from today's bars...")
    to_drop = []
    for t in list(candidates):
        try:
            seed_bars = get_intraday_bars(t, count=390)
            if not seed_bars:
                print(f"   {t}: no Webull intraday data — watching for fresh breakout")
                continue
            today_high = max(float(b.get("high") or b.get("h") or
                                   b.get("close") or b.get("c") or 0)
                             for b in seed_bars)
            seed_vwap  = calculate_vwap(seed_bars)
            if seed_vwap > 0:
                cache[t]["vwap"] = seed_vwap  # pre-populate so drop check works
            if seed_vwap > 0 and today_high >= seed_vwap * (1 + VWAP_PULLBACK_MIN_RUN):
                cache[t]["high_water"] = today_high
                print(f"   {t}: today's high ${today_high:.2f} vs VWAP ${seed_vwap:.2f} "
                      f"(+{(today_high/seed_vwap-1)*100:.1f}%) — pullback detection armed")
            else:
                # No meaningful prior run — check if current price is already too far
                # below VWAP to have any realistic setup. If so, drop immediately.
                current = stream.get_price(t)
                if current > 0 and seed_vwap > 0:
                    gap_pct = (current - seed_vwap) / seed_vwap
                    if gap_pct < -VWAP_PULLBACK_MIN_RUN:
                        print(f"   ⛔ {t}: ${current:.2f} is {gap_pct*100:.1f}% below VWAP "
                              f"${seed_vwap:.2f} with no prior run — no valid setup, dropping")
                        to_drop.append(t)
                        continue
                print(f"   {t}: no meaningful prior run above VWAP — watching for fresh breakout")
        except Exception as e:
            print(f"   {t}: seed error — {e}")
    if to_drop:
        for t in to_drop:
            candidates.remove(t)
            del cache[t]
        if not candidates:
            print("⚠️  All initial candidates dropped (no valid VWAP setup). "
                  "Entering watch loop — rescan will find new movers.")
        else:
            print(f"📋 Remaining candidates after VWAP filter: {', '.join(candidates)}")

    last_rescan = time.time()

    while True:
        now = datetime.now(EASTERN)

        if now.hour > VWAP_ENTRY_TIMEOUT or (now.hour == VWAP_ENTRY_TIMEOUT and now.minute >= VWAP_ENTRY_TIMEOUT_MIN):
            print(f"⏰ 3:30pm cutoff — no VWAP reclaim across any candidate. Holding cash.")
            return None, None, None

        if now.hour < 9 or (now.hour == 9 and now.minute < 30):
            mins = (9 * 60 + 30) - (now.hour * 60 + now.minute)
            print(f"⏳ Market opens in ~{mins} min...")
            time.sleep(30)
            continue

        # ── Refresh bars for each ticker on their own 30s cadence ──
        for t in candidates:
            if time.time() - cache[t]["fetched"] >= VWAP_BAR_CACHE_SECS:
                # Regular session bars: volume comparison + 90MA
                fresh = get_intraday_bars(t)
                if fresh:
                    cache[t]["bars"] = fresh
                    cache[t]["ma90"] = calculate_90ma(fresh)
                full_bars = get_intraday_bars(t, count=390)
                if full_bars:
                    calc_vwap = calculate_vwap(full_bars)
                    if calc_vwap > 0:
                        cache[t]["vwap"] = calc_vwap
                elif fresh:
                    cache[t]["vwap"] = calculate_vwap(fresh)
                cache[t]["fetched"] = time.time()

        # ── Check each ticker — take first confirmed reclaim ───────
        status_parts = []
        for t in candidates:
            bars  = cache[t]["bars"]
            vwap  = cache[t]["vwap"]
            ma90  = cache[t]["ma90"]
            price = stream.get_price(t)

            if not bars or price <= 0 or vwap <= 0:
                status_parts.append(f"{t}:no data")
                continue

            pct = ((price - vwap) / vwap) * 100
            ma90_tag = f" 90MA:${ma90:.2f}" if ma90 > 0 else ""
            status_parts.append(f"{t}:${price:.2f}({pct:+.1f}%){ma90_tag}")

            # Kev's entry: price must be above BOTH VWAP and the 90MA
            above_vwap = price > vwap
            above_90ma = ma90 <= 0 or price > ma90

            if above_vwap and above_90ma:
                extension = (price - vwap) / vwap
                if extension > MAX_VWAP_EXTENSION:
                    cache[t]["ticks_above"] = 0
                    status_parts[-1] += f" 🚫EXTENDED(+{extension*100:.0f}%>VWAP)"
                    continue

                # Track high-water mark above VWAP
                cache[t]["high_water"] = max(cache[t]["high_water"], price)

                # Pullback mode: entered when price pulled back to VWAP after a prior run.
                # Pullback bounce = faster entry (1 tick, 1.0x vol) vs fresh reclaim (3 ticks, 1.5x vol).
                in_pb = cache[t]["pullback_mode"]
                cache[t]["pullback_mode"] = False  # clear now that we're above VWAP

                cache[t]["ticks_above"] += 1
                ticks = cache[t]["ticks_above"]
                last_vol = float(bars[-1].get("volume") or bars[-1].get("v") or 0)
                avg_vol  = sum(float(b.get("volume") or b.get("v") or 0)
                               for b in bars) / max(len(bars), 1)
                req_ticks = 1 if in_pb else VWAP_CONFIRM_TICKS
                vol_mult  = 1.0 if in_pb else VWAP_VOL_MULTIPLIER
                vol_rel_ok = avg_vol == 0 or last_vol >= avg_vol * vol_mult
                vol_abs_ok = last_vol >= MIN_ABS_VOL_ENTRY
                vol_ok     = vol_rel_ok and vol_abs_ok
                label      = "PULLBACK↑" if in_pb else "RECLAIM"

                if ticks < req_ticks:
                    status_parts[-1] += f" ⏳{label}:{ticks}/{req_ticks}"
                elif vol_ok:
                    print(f"\n✅ {t} VWAP+90MA {label} confirmed! "
                          f"${price:.2f} > VWAP ${vwap:.2f} & 90MA ${ma90:.2f} "
                          f"held {ticks} tick(s) vol={last_vol/avg_vol if avg_vol else 0:.1f}x "
                          f"({int(last_vol):,} shares)")
                    return t, price, vwap
                elif not vol_abs_ok:
                    status_parts[-1] += f" ⏳{label}:vol{int(last_vol):,}<{MIN_ABS_VOL_ENTRY:,}abs"
                else:
                    # Re-arm pullback mode so next tick still gets fast entry
                    if in_pb:
                        cache[t]["pullback_mode"] = True
                    status_parts[-1] += f" ⏳{label}:vol{last_vol/avg_vol if avg_vol else 0:.1f}x"
            else:
                if cache[t]["ticks_above"] > 0:
                    reason = "VWAP" if not above_vwap else "90MA"
                    print(f"   {t} dropped below {reason} after {cache[t]['ticks_above']} tick(s)")
                cache[t]["ticks_above"] = 0

                # Detect pullback to VWAP after a meaningful prior run
                hw = cache[t]["high_water"]
                if hw >= vwap * (1 + VWAP_PULLBACK_MIN_RUN):
                    pct_from_vwap = (price - vwap) / vwap  # negative when below VWAP
                    if abs(pct_from_vwap) <= VWAP_PULLBACK_ZONE:
                        if not cache[t]["pullback_mode"]:
                            print(f"   {t} pullback to VWAP ${vwap:.2f} "
                                  f"(high ${hw:.2f}, now {pct_from_vwap*100:+.1f}%) — watching for bounce")
                        cache[t]["pullback_mode"] = True
                        status_parts[-1] += f" 🔄PB({pct_from_vwap*100:+.1f}%)"
                    elif price < vwap * (1 - VWAP_PULLBACK_ZONE * 2):
                        # Dropped too far — setup blown through, full reset
                        if cache[t]["pullback_mode"]:
                            print(f"   {t} failed pullback — dropped too far below VWAP, resetting")
                        cache[t]["pullback_mode"] = False
                        cache[t]["high_water"] = 0.0

                if above_vwap and not above_90ma:
                    status_parts[-1] += f" ⚠️below90MA"

        if status_parts:
            print(f"📊 {' | '.join(status_parts)}")
        else:
            print(f"📊 No candidates — waiting for rescan to find a setup...")

        # ── 10-minute live rescan — pick up new movers ─────────
        if rescan_callback and time.time() - last_rescan >= INTRADAY_RESCAN_INTERVAL:
            print(f"🔄 10-min rescan — checking live market for new setups...")
            new_candidates = rescan_callback(exclude=traded_tickers | set(candidates))
            if new_candidates:
                for t in new_candidates:
                    if t not in candidates:
                        candidates.append(t)
                        hw = 0.0
                        try:
                            sb = get_intraday_bars(t, count=390)
                            if sb:
                                th = max(float(b.get("high") or b.get("h") or
                                               b.get("close") or b.get("c") or 0) for b in sb)
                                sv = calculate_vwap(sb)
                                if sv > 0 and th >= sv * (1 + VWAP_PULLBACK_MIN_RUN):
                                    hw = th
                        except Exception:
                            pass
                        cache[t] = {"bars": [], "vwap": 0.0, "ma90": 0.0, "fetched": 0.0,
                                    "ticks_above": 0, "high_water": hw, "pullback_mode": False}
                        print(f"   ➕ Added {t} to watchlist"
                              + (f" (prior high ${hw:.2f})" if hw > 0 else ""))
            last_rescan = time.time()

        time.sleep(stream.loop_sleep())

# ============================================================
# STEP 5 — EXECUTE TRADE VIA WEBULL OPENAPI v2
# ============================================================
#
# All orders use the new /openapi/trade/stock/order/place endpoint.
# Orders are identified by our own client_order_id (UUID hex), not
# Webull's internal orderId — that's what cancel/replace uses too.

def _px(price) -> str:
    """Format price per Webull rules: 2 decimal places for >= $1, 4 for sub-dollar."""
    return f"{price:.2f}" if price >= 1.0 else f"{price:.4f}"


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
        order["aux_price"] = _px(stop_price)
    if limit_price is not None:
        order["limit_price"] = _px(limit_price)

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


def get_actual_fill_price(order_id, timeout_secs=8):
    """
    Poll Webull for the actual average fill price of a buy order.
    Returns the fill price, or None if it can't be read in time.
    """
    _, trade_client = _make_webull_client()
    if not trade_client:
        return None
    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        try:
            res = trade_client.order_v2.query_order_detail(WEBULL_ACCOUNT_ID, order_id)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data.get("data"), dict):
                    data = data["data"]
                status = str(data.get("status") or data.get("orderStatus") or "").upper()
                if "FILL" in status or "FILLED" in status:
                    price = float(
                        data.get("avgFilledPrice") or
                        data.get("avg_filled_price") or
                        data.get("filledPrice") or
                        data.get("filled_price") or
                        data.get("averagePrice") or
                        data.get("average_price") or 0
                    )
                    if price > 0:
                        print(f"✅ Actual fill price confirmed: ${price:.2f}")
                        return price
        except Exception as e:
            print(f"⚠️ Fill price check error: {e}")
        time.sleep(1)
    print("⚠️ Could not confirm fill price from Webull — using trigger price")
    return None


def execute_trade(ticker, shares, entry_price, stop_loss, target):
    """
    Places a limit buy order (1% above VWAP entry) then a stop order.
    Using LMT instead of MKT caps slippage on small-float fast-moving stocks.
    Retries the buy order once after 3s on transient API failures.
    Returns (buy_client_order_id, stop_client_order_id, actual_fill_price).
    actual_fill_price is the confirmed Webull fill — use it for stop/target/P&L.
    Returns (None, None, None) on failure.
    """
    if DRY_RUN:
        fake_id = uuid.uuid4().hex
        print(f"🧪 DRY RUN — simulating BUY {shares} shares of {ticker} @ ${entry_price:.2f}")
        print(f"   Stop: ${stop_loss:.2f}  Target: ${target:.2f}")
        return fake_id, uuid.uuid4().hex, entry_price

    shares      = max(1, int(shares))   # Webull requires whole shares
    decimals    = 2 if entry_price >= 1.0 else 4
    limit_price = round(entry_price * (1 + ENTRY_LIMIT_BUFFER), decimals)
    print(f"🚀 Executing: BUY {shares} shares of {ticker} "
          f"@ limit ${limit_price:.2f} (VWAP entry ${entry_price:.2f} +1%)...")

    buy_id = _place_order(ticker, shares, "BUY", "LIMIT", limit_price=limit_price)
    if not buy_id:
        print(f"⚠️  Buy order failed — retrying in 3s...")
        time.sleep(3)
        buy_id = _place_order(ticker, shares, "BUY", "LIMIT", limit_price=limit_price)
    if not buy_id:
        print(f"❌ Buy order failed after retry for {ticker}")
        return None, None, None

    print(f"✅ Buy order placed! Client ID: {buy_id}")

    # Read actual fill price before placing stop — stop must be based on real entry
    actual_fill = get_actual_fill_price(buy_id, timeout_secs=8) or entry_price
    if actual_fill != entry_price:
        print(f"📊 Fill slippage: trigger ${entry_price:.2f} → actual fill ${actual_fill:.2f} "
              f"({((actual_fill - entry_price) / entry_price * 100):+.2f}%)")

    stop_id = place_stop_order(ticker, shares, stop_loss)
    return buy_id, stop_id, actual_fill


def close_position(ticker, shares):
    """Sell shares at market price."""
    shares = max(1, int(shares))
    print(f"🔒 Closing: SELL {shares} shares of {ticker}...")
    if DRY_RUN:
        print(f"🧪 DRY RUN — simulating SELL {shares} shares of {ticker}")
        return True
    result = _place_order(ticker, shares, "SELL", "MARKET")
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
    Webull OpenAPI rejects all stop order types (STP, STP_LMT, STOP LOSS).
    Rely entirely on the software stop in monitor_trade() which fires a MARKET
    sell the moment price <= stop level. Returns None always.
    """
    shares = max(1, int(shares))
    if DRY_RUN:
        print(f"🧪 DRY RUN — software stop only: ${stop_price:.2f} × {shares} shares")
        return None
    print(f"🛡️  Software stop armed at ${stop_price:.2f} × {shares} shares (exchange stops unsupported)")
    return None


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
    partial_fills      = []
    entry_time         = time.time()   # for early fade window
    last_good_price    = entry_price   # last valid price seen (for stale-feed safety exit)
    last_good_price_t  = time.time()   # epoch of last valid price

    entry_hour = datetime.now(EASTERN).hour
    exit_tiers = EXIT_TIERS_AM if entry_hour < 11 else EXIT_TIERS_PM
    tier_idx = 0
    initial_shares = total_shares
    mode = "AM" if entry_hour < 11 else "PM"
    tier_desc = ", ".join(f"+{t[0]*100:.0f}%→{t[1]*100:.0f}%" for t in exit_tiers)
    print(f"   Exit tiers ({mode}): {tier_desc} | Floor at entry after first sell")
    last_ema_check     = 0.0           # epoch of last EMA9 bar fetch

    result = {"exit_price": entry_price, "exit_reason": "Unknown",
              "profit_loss": 0, "profit_loss_pct": 0}

    while True:
        now = datetime.now(EASTERN)

        # ── Hard close at 3:45pm ───────────────────────
        past_end = (now.hour > TRADE_WINDOW_END_HOUR or
                    (now.hour == TRADE_WINDOW_END_HOUR and now.minute >= TRADE_WINDOW_END_MIN))
        if past_end:
            print("⏰ 3:45pm — Force closing all positions")
            current_price = stream.get_price(ticker)
            if remaining_shares > 0:
                cancel_order(placed_stop_id)
                close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "3:45pm time stop"
            break

        current_price = stream.get_price(ticker)
        if current_price <= 0:
            # No valid price. If the feed has been dead too long, a position must NOT sit
            # blind/open (the BOXL freeze) — force-close at the last known price for safety.
            stale_secs = time.time() - last_good_price_t
            if remaining_shares > 0 and stale_secs > STALE_FEED_EXIT_SECS:
                print(f"🛑 {ticker} price feed dead {stale_secs:.0f}s (> {STALE_FEED_EXIT_SECS}s) — "
                      f"force-closing {remaining_shares} sh at last price ${last_good_price:.2f} for safety.")
                cancel_order(placed_stop_id)
                close_position(ticker, remaining_shares)
                result["exit_price"]  = last_good_price
                result["exit_reason"] = "STALE FEED SAFETY EXIT"
                remaining_shares = 0
                break
            time.sleep(sleep_secs)
            continue

        # Valid price — reset the stale-feed watchdog.
        last_good_price   = current_price
        last_good_price_t = time.time()

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

        # ── Trailing stop: ratchet up after partial exit (floor = entry price) ─
        if partial_taken:
            trail = max(highest_price * (1 - TRAIL_PCT), entry_price)
            if trail > current_stop:
                current_stop = trail
                print(f"📈 Trailing stop → ${current_stop:.2f}")
                # Only replace exchange order if stop moved >= $0.10
                if current_stop - placed_stop_price >= STOP_UPDATE_MIN_MOVE:
                    placed_stop_id    = update_stop_order(ticker, placed_stop_qty,
                                                          current_stop, placed_stop_id)
                    placed_stop_price = current_stop

        print(f"💰 {ticker}: ${current_price:.2f} ({profit_pct:+.1f}%) | Stop: ${current_stop:.2f} | Shares: {remaining_shares}")
        _post_trade_state({
            "ticker": ticker, "entry": round(entry_price, 4), "price": round(current_price, 4),
            "pnl_pct": round(profit_pct, 2), "stop": round(current_stop, 4),
            "target": round(target_price, 4), "remaining_shares": remaining_shares,
            "initial_shares": initial_shares, "partials": len(partial_fills),
            "highest": round(highest_price, 4), "vwap": round(vwap, 4) if vwap else None,
        })
        # Durable recovery state — survives a crash/restart so this trade still gets a recorded exit.
        _save_open_trade({
            "ticker": ticker, "entry_price": round(entry_price, 4), "target": round(target_price, 4),
            "stop": round(current_stop, 4), "remaining_shares": remaining_shares,
            "initial_shares": initial_shares, "highest": round(highest_price, 4),
            "tier_idx": tier_idx, "partial_fills": partial_fills, "vwap": round(vwap, 4) if vwap else 0,
            "last_price": round(current_price, 4),
        })

        # ── Tiered exits (AM: 25%@+8%, 50%@+12%, 25%@+20% | PM: 50%@+4%, 50%@+6%) ──
        if tier_idx < len(exit_tiers) and remaining_shares > 0:
            tier_pct, tier_cumulative = exit_tiers[tier_idx]
            if profit_pct >= tier_pct * 100:
                if tier_cumulative >= 1.0:
                    sell_qty = remaining_shares
                else:
                    sold_so_far = initial_shares - remaining_shares
                    target_sold = int(initial_shares * tier_cumulative)
                    sell_qty = max(1, target_sold - sold_so_far)
                    sell_qty = min(sell_qty, remaining_shares)

                tier_label = f"Tier {tier_idx+1}/{len(exit_tiers)}"
                print(f"💰 {tier_label}: selling {sell_qty} of {remaining_shares} shares "
                      f"at ${current_price:.2f} (+{profit_pct:.1f}%)")
                cancel_order(placed_stop_id)
                close_position(ticker, sell_qty)
                partial_price    = current_price
                partial_taken    = True
                partial_fills.append((sell_qty, current_price))
                remaining_shares -= sell_qty
                tier_idx += 1

                if remaining_shares <= 0:
                    result["exit_price"]  = current_price
                    result["exit_reason"] = f"Full exit ({tier_label}) ✅"
                    break

                trail_stop = highest_price * (1 - TRAIL_PCT)
                current_stop     = max(trail_stop, entry_price)
                placed_stop_id    = place_stop_order(ticker, remaining_shares, current_stop)
                placed_stop_price = current_stop
                placed_stop_qty   = remaining_shares
                print(f"📈 Floor at entry ${entry_price:.2f}, trail stop ${current_stop:.2f} "
                      f"— {remaining_shares} shares remaining")
                send_partial_exit_alert(ticker, sell_qty, partial_price, entry_price,
                                        remaining_shares, current_stop, profit_pct)

        # ── EMA9 2-bar confirm stop (v8 primary exit) ─────────────
        if remaining_shares > 0 and time.time() - last_ema_check >= EMA_CHECK_INTERVAL:
            bars = get_intraday_bars(ticker, count=EMA_PERIOD + 5)
            if bars and len(bars) >= EMA_PERIOD + 2:
                ema9 = calculate_ema9(bars)
                completed = bars[:-1]   # exclude in-progress bar
                if len(completed) >= 2 and ema9 > 0:
                    lc = float(completed[-1].get("close") or completed[-1].get("c") or 0)
                    pc = float(completed[-2].get("close") or completed[-2].get("c") or 0)
                    if lc > 0 and pc > 0 and lc < ema9 and pc < ema9:
                        print(f"📉 EMA9 2-bar stop: {ticker} last 2 bars below EMA9 ${ema9:.2f} "
                              f"(${pc:.2f}, ${lc:.2f}) — exiting at market.")
                        cancel_order(placed_stop_id)
                        close_position(ticker, remaining_shares)
                        result["exit_price"]  = stream.get_price(ticker)
                        result["exit_reason"] = "EMA STOP 2BAR"
                        remaining_shares = 0

                # Kev "topping tail off the high" — his #1 exit. If the last completed bar
                # made a fresh high then got rejected (long upper wick) AND we're in profit,
                # take the money. Only protects a winner — never exits a loser on a wick.
                if remaining_shares > 0 and current_price > entry_price:
                    last_high = float(completed[-1].get("high") or completed[-1].get("h") or 0)
                    if last_high >= highest_price * 0.99 and is_topping_tail(completed[-1]):
                        print(f"🔻 Topping tail off the high: {ticker} rejected at ${last_high:.2f} "
                              f"in profit — taking full exit (Kev exit).")
                        cancel_order(placed_stop_id)
                        close_position(ticker, remaining_shares)
                        result["exit_price"]  = current_price
                        result["exit_reason"] = "TOPPING TAIL"
                        remaining_shares = 0
            last_ema_check = time.time()

        if remaining_shares == 0:
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

    # ── Blended P&L (sum across all tier fills + remaining) ──
    if partial_fills:
        pnl = sum((px - entry_price) * qty for qty, px in partial_fills)
        pnl += (result["exit_price"] - entry_price) * remaining_shares
        result["profit_loss"] = pnl
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


def _fetch_kev_picks_from_screener() -> str:
    """
    Read Kev's transcript submitted via the screener web form today.
    Returns the full transcript text, or empty string if not found / not today's.
    """
    if not SCREENER_URL:
        return ""
    try:
        r = requests.get(f"{SCREENER_URL}/api/kev_picks", timeout=8)
        if r.status_code == 200:
            data = r.json()
            transcript = data.get("transcript", "")
            saved_at   = data.get("saved_at_display", "")
            if transcript:
                print(f"✅ Kev's picks loaded from screener (saved {saved_at}, {len(transcript)} chars)")
                return transcript
    except Exception as e:
        print(f"⚠️  Screener kev picks fetch error: {e}")
    return ""


def _fetch_evening_watchlist() -> dict:
    """
    Fetch last night's watchlist from the screener app.
    Returns empty dict if unavailable or from a different date.
    """
    if not SCREENER_URL:
        return {}
    try:
        r = requests.get(f"{SCREENER_URL}/api/evening_watchlist", timeout=8)
        if r.status_code != 200:
            return {}
        data = r.json()
        if not data or not data.get("top_picks"):
            return {}
        # Only use watchlist from last night (not days old)
        saved_at = data.get("saved_at", "")
        if saved_at:
            from datetime import timedelta
            saved_dt = datetime.fromisoformat(saved_at).astimezone(EASTERN)
            age_hours = (datetime.now(EASTERN) - saved_dt).total_seconds() / 3600
            if age_hours > 18:
                print(f"⚠️  Evening watchlist is {age_hours:.0f}h old — skipping")
                return {}
        return data
    except Exception as e:
        print(f"⚠️  Could not fetch evening watchlist: {e}")
        return {}


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
    """Alert 1 — Fired right after Claude finishes analysis (~8:55am or mid-day rescan)."""
    recommended = analysis.get("recommended_trade", {})
    action      = recommended.get("action", "HOLD CASH")
    ticker      = recommended.get("ticker", "N/A")
    now_et      = datetime.now(EASTERN)
    today       = now_et.strftime("%A, %B %d, %Y")
    hour        = now_et.hour
    greeting    = ("Good morning" if hour < 12 else
                   "Good afternoon" if hour < 17 else "Good evening")
    scan_label  = "morning analysis" if hour < 10 else "mid-day rescan"
    conf        = recommended.get("confidence", "N/A")
    conf_color  = {"HIGH": "#00c851", "MEDIUM": "#ffbb33", "LOW": "#ff6b35"}.get(conf, "#9090b0")

    if action == "BUY":
        subject = f"🤖 Bot Plan — {ticker} is the pick | {today}"
        plain = (f"{greeting} Marcos! Claude picked {ticker} ({scan_label}).\n\n"
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
            f'<div style="font-size:26px;font-weight:bold;color:#ffffff;">{greeting} Marcos! 👋</div>'
            f'<div style="font-size:16px;color:#9090b0;margin-top:6px;">Claude just finished the {scan_label} for {today}</div>'
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
        subject = f"🤖 Bot Plan — 💤 No trade | {today}"
        plain = f"No trade this {scan_label}. Cash: ${balance:.2f}\n\n{analysis.get('plain_english_summary','')}"
        html = _html_wrap(
            f'<tr><td style="padding:16px 20px 4px;">'
            f'<div style="font-size:26px;font-weight:bold;color:#ffffff;">{greeting} Marcos! 👋</div>'
            f'<div style="font-size:16px;color:#9090b0;margin-top:6px;">{scan_label.capitalize()} — {today}</div>'
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
        + _section(f"EXIT PLAN — {('AM' if datetime.now(EASTERN).hour < 11 else 'PM')} tiers", (
            "".join(
                _row(f"{'🎯 ' if frac >= 1.0 else '💰 '}Tier {i}: +{pct*100:.0f}% (${entry_price*(1+pct):.2f})",
                     ("Sell ALL — full exit" if frac >= 1.0 else f"Sell {frac*100:.0f}%"),
                     big=(frac >= 1.0))
                for i, (pct, frac) in enumerate(
                    (EXIT_TIERS_AM if datetime.now(EASTERN).hour < 11 else EXIT_TIERS_PM), 1)
            )
            + _row("🛟 After 1st partial", "Stop floor → entry (breakeven)")
            + _row("📈 Trailing stop",     "Ratchets up under the high")
            + _row("🛑 Hard Stop",          f"${stop_loss:.2f}")
            + _row("⏰ Hard Close",          "3:45pm ET")
        ), color="#ffbb33")
    )
    send_alert_email(subject, plain, html=html)


def send_partial_exit_alert(ticker, half_shares, partial_price, entry_price,
                            remaining_shares, new_stop, profit_pct):
    """Alert 3 — Fired when half the position is sold at +8% AM / +5% PM."""
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

def _send_morning_watchlist(top_gappers: list, balance: float):
    today = datetime.now(EASTERN).strftime("%A, %B %d, %Y")
    dry_tag = "[DRY RUN] " if DRY_RUN else ""

    if not top_gappers:
        return

    rows_html = ""
    for i, g in enumerate(top_gappers, 1):
        sym = g.get("symbol", "?")
        chg = g.get("change_pct", 0)
        price = g.get("price", 0)
        fl = g.get("float_label", "")
        rows_html += (
            f'<tr style="border-bottom:1px solid #2a2a40;">'
            f'<td style="padding:10px 16px;color:#ffffff;font-weight:bold;">{i}</td>'
            f'<td style="padding:10px 16px;color:#00e676;font-weight:bold;font-size:16px;">{sym}</td>'
            f'<td style="padding:10px 16px;color:#ffab40;">+{chg:.1f}%</td>'
            f'<td style="padding:10px 16px;color:#b0b0c0;">${price:.2f}</td>'
            f'<td style="padding:10px 16px;color:#7c7ca0;font-size:12px;">{fl}</td>'
            f'</tr>'
        )

    table = (
        f'<table style="width:100%;border-collapse:collapse;background:#12122a;border-radius:8px;">'
        f'<tr style="border-bottom:2px solid #6c63ff;">'
        f'<th style="padding:10px 16px;color:#6c63ff;text-align:left;">#</th>'
        f'<th style="padding:10px 16px;color:#6c63ff;text-align:left;">Ticker</th>'
        f'<th style="padding:10px 16px;color:#6c63ff;text-align:left;">Change</th>'
        f'<th style="padding:10px 16px;color:#6c63ff;text-align:left;">Price</th>'
        f'<th style="padding:10px 16px;color:#6c63ff;text-align:left;">Float</th>'
        f'</tr>'
        f'{rows_html}</table>'
    )

    html = _html_wrap(
        f'<tr><td style="padding:16px 20px 4px;">'
        f'<div style="font-size:26px;font-weight:bold;color:#ffffff;">Morning Watchlist — {today}</div>'
        f'<div style="font-size:14px;color:#7c7ca0;margin-top:4px;">'
        f'{"🧪 DRY RUN — simulated trades only" if DRY_RUN else "🔴 LIVE MODE"}'
        f'</div>'
        f'</td></tr>'
        + _section("TOP CANDIDATES", table, color="#00e676")
        + _section("ACCOUNT", (
            _row("Balance", f"${balance:.2f}")
            + _row("Per Trade", f"${MAX_TRADE_DOLLARS:.0f}")
            + _row("Entry Types", "Flat Top Breakout + EMA Bounce")
            + _row("Cutoff", "3:30pm (dry run)" if DRY_RUN else "11:00am")
        ))
    )

    subject = f"{dry_tag}Morning Watchlist — {len(top_gappers)} candidates | {today}"
    try:
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from": "Marcos Trading Bot <onboarding@resend.dev>",
            "to": [SUMMARY_EMAIL],
            "subject": subject,
            "html": html,
        })
        print(f"📧 Morning watchlist email sent — {len(top_gappers)} candidates")
    except Exception as e:
        print(f"⚠️  Morning email failed: {e}")


def send_summary_email(analysis, trade_result=None, account_balance=100.0, csv_log_line="", traded_ticker=None):
    print(f"📨 Sending summary email to {SUMMARY_EMAIL}...")
    today   = datetime.now(EASTERN).strftime("%A, %B %d, %Y")
    dry_tag = "[DRY RUN] " if DRY_RUN else ""

    if trade_result:
        ticker      = traded_ticker or "N/A"
        pnl         = trade_result.get("profit_loss", 0)
        pnl_pct     = trade_result.get("profit_loss_pct", 0)
        exit_reason = trade_result.get("exit_reason", "N/A")
        exit_price  = trade_result.get("exit_price", 0)
        win         = pnl >= 0
        result_line = f"{'✅' if win else '🔴'} {ticker}: {pnl_pct:+.1f}% (${pnl:+.2f})"
        subject     = f"{dry_tag}Trading Bot Summary — {today} | {result_line}"
        pnl_color   = "#00c851" if win else "#ff4444"

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
        html = _html_wrap(
            f'<tr><td style="padding:16px 20px 4px;">'
            f'<div style="font-size:26px;font-weight:bold;color:#ffffff;">Trading Summary — {today}</div>'
            f'</td></tr>'
            + _section("NO TRADE TAKEN TODAY", (
                _row("Cash Preserved", f"${account_balance:.2f}", big=True)
                + f'<div style="margin-top:12px;font-size:17px;line-height:1.7;color:#d0d0e8;">'
                  f'No flat top breakout detected. Pure technical scanner — watching RVOL + momentum candidates.</div>'
            ), color="#ffbb33")
        )
        plain = f"No trade today. Cash: ${account_balance:.2f}\nNo flat top breakout detected."

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



# ============================================================
# OPEN POSITION RESUME
# ============================================================

def get_open_position(retries=4, delay=8):
    """
    Query Webull for any open equity positions using the dedicated positions endpoint.
    Returns (ticker, shares, avg_cost) or (None, 0, 0) if confirmed flat.
    Raises RuntimeError if all retries fail — caller must NOT assume flat on error.
    """
    _, trade_client = _make_webull_client()
    if not trade_client:
        raise RuntimeError("Webull client unavailable — cannot confirm position status")

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            res = trade_client.account.get_account_position(WEBULL_ACCOUNT_ID, page_size=50)
            if res.status_code != 200:
                raise RuntimeError(f"HTTP {res.status_code}")
            data = res.json()
            # Log raw structure on first attempt to diagnose parsing misses
            if attempt == 1:
                top_keys = list(data.keys()) if isinstance(data, dict) else f"list[{len(data)}]"
                print(f"🔬 Position API raw top-level: {top_keys}")
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, (list, dict)):
                            print(f"   .{k} → {type(v).__name__}[{len(v)}]: {str(v)[:300]}")
            items = data if isinstance(data, list) else (
                    data.get("holdings") or data.get("data") or data.get("items") or
                    data.get("positions") or data.get("position_list") or data.get("positionList") or [])
            print(f"🔍 Position check (attempt {attempt}) — {len(items)} position(s) found")
            for pos in items:
                qty = int(float(pos.get("quantity") or pos.get("qty") or 0))
                if qty > 0:
                    ticker   = (pos.get("symbol") or pos.get("ticker_symbol") or
                                pos.get("tickerSymbol") or "").strip().upper()
                    avg_cost = float(pos.get("unit_cost") or pos.get("average_cost") or
                                     pos.get("avg_cost") or pos.get("cost_price") or
                                     pos.get("costPrice") or 0)
                    if ticker and avg_cost > 0:
                        print(f"⚡ Found open position: {ticker} × {qty} @ ${avg_cost:.2f}")
                        return ticker, qty, avg_cost
            return None, 0, 0  # confirmed flat
        except Exception as e:
            last_err = e
            print(f"⚠️  Position check attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(delay)

    raise RuntimeError(f"Position check failed after {retries} attempts: {last_err}")


def resume_monitoring_if_open():
    """
    If a position is already open (e.g. bot was redeployed mid-trade),
    skip the scan and go straight to monitoring with recalculated levels.
    Returns True if we resumed (caller should return after), False if confirmed flat.
    Sends an alert email and blocks if the position check is inconclusive.
    """
    try:
        ticker, shares, avg_cost = get_open_position()
    except RuntimeError as e:
        # Cannot confirm position status — do NOT start trading.
        # Send an alert and block until manually resolved.
        msg = (f"⚠️ Bot restarted but could not confirm position status.\n\n"
               f"Error: {e}\n\n"
               f"The bot will NOT trade until Webull confirms the account is flat.\n"
               f"Check your Webull app and restart the Railway service if no position is open.")
        print(f"\n🚨 POSITION CHECK FAILED — blocking bot until resolved.\n{msg}")
        try:
            resend.api_key = RESEND_API_KEY
            resend.Emails.send({
                "from":    "Trading Bot <onboarding@resend.dev>",
                "to":      [SUMMARY_EMAIL],
                "subject": "🚨 Bot blocked — position status unknown after restart",
                "text":    msg,
            })
        except Exception:
            pass
        # Block indefinitely — Railway will restart the service if it crashes,
        # so we sleep-loop to hold the process without crashing and spinning.
        while True:
            time.sleep(60)

    if not ticker or shares <= 0 or avg_cost <= 0:
        return False

    print(f"\n⚡ OPEN POSITION DETECTED: {ticker} × {shares} shares @ ${avg_cost:.2f}")
    print(f"   Resuming monitoring — skipping scan and analysis.\n")

    stop_loss    = round(avg_cost * (1 - STOP_LOSS_PCT), 2)
    target_price = round(avg_cost * (1 + TARGET_PCT), 2)

    print(f"   Stop:   ${stop_loss:.2f} (-{STOP_LOSS_PCT*100:.0f}%)")
    print(f"   Target: ${target_price:.2f} (+{TARGET_PCT*100:.0f}%)")

    try:
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from":    "Trading Bot <onboarding@resend.dev>",
            "to":      [SUMMARY_EMAIL],
            "subject": f"⚡ Bot resumed monitoring {ticker} after redeploy",
            "text":    (f"Railway redeployed while {ticker} was open.\n\n"
                        f"Resuming monitoring:\n"
                        f"  Entry (avg cost): ${avg_cost:.2f}\n"
                        f"  Shares: {shares}\n"
                        f"  Stop:   ${stop_loss:.2f}\n"
                        f"  Target: ${target_price:.2f}\n\n"
                        f"Software stop is active. Force close at 3:45pm ET."),
        })
    except Exception as e:
        print(f"⚠️  Resume alert email failed: {e}")

    stream = WebullStream([ticker])
    trade_result = monitor_trade(
        ticker, shares, avg_cost, target_price, stop_loss,
        stream, stop_order_id=None
    )

    _open_trade["active"] = False
    stream.stop()
    new_balance = get_account_balance()
    pnl = trade_result.get("profit_loss", 0)
    exit_reason = trade_result.get("exit_reason", "N/A")
    print(f"\n✅ RESUMED TRADE COMPLETE — {ticker} | P&L: ${pnl:+.2f} | {exit_reason}")
    send_summary_email({}, trade_result, new_balance)
    return True


# ============================================================
# MAIN
# ============================================================

def main():
    now = datetime.now(EASTERN)
    print(f"\n{'='*60}")
    print(f"🤖 MARCOS TRADING BOT — Pure Technical Scanner")
    print(f"📅 {now.strftime('%A, %B %d, %Y at %I:%M %p ET')}")
    print(f"{'='*60}\n")

    # ── Resume if position already open (e.g. redeployed mid-trade) ──
    _pre_populate_webull_token()
    if resume_monitoring_if_open():
        return

    # ── Startup ping ─────
    try:
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from":    "Marcos Trading Bot <onboarding@resend.dev>",
            "to":      [SUMMARY_EMAIL],
            "subject": f"🤖 Bot scanning — {now.strftime('%a %b %d %I:%M %p ET')}",
            "html":    f"<p>Bot started at <b>{now.strftime('%I:%M %p ET')}</b>. "
                       f"Scanning Webull screener for RVOL + momentum setups. "
                       f"Pure technicals — no picks, no AI analysis.</p>",
        })
        print(f"✅ Startup ping sent to {SUMMARY_EMAIL}")
    except Exception as e:
        print(f"⚠️  Startup ping failed: {e}")

    # ── TEST_TRADE fast-path ───────────────────────────────
    if TEST_TRADE:
        print(f"🧪 TEST_TRADE MODE — ticker: {TEST_TRADE}")
        _pre_populate_webull_token()
        check_token_expiry()
        check_webull_connection()

        _, tc = _make_webull_client()
        if tc:
            res = tc.account_v2.get_account_list()
            if res.status_code == 200:
                all_accounts = res.json()
                print(f"\n📋 ALL WEBULL ACCOUNTS ({len(all_accounts) if isinstance(all_accounts, list) else '?'}):")
                if isinstance(all_accounts, list):
                    for i, acct in enumerate(all_accounts):
                        print(f"   [{i}] account_id={acct.get('account_id')}  type={acct.get('account_type')}  status={acct.get('account_status')}  currency={acct.get('currency')}")
                else:
                    print(f"   Raw: {str(all_accounts)[:300]}")
            else:
                print(f"⚠️  Could not list accounts: {res.status_code} {res.text[:200]}")
        print(f"\n🔑 Currently using WEBULL_ACCOUNT_ID: {WEBULL_ACCOUNT_ID}\n")

        balance = get_account_balance()
        print(f"💰 Balance: ${balance:.2f}")
        stream = WebullStream([TEST_TRADE])
        snap = _get_webull_quote(TEST_TRADE)
        if not snap:
            print(f"❌ Could not get quote for {TEST_TRADE} — aborting test trade")
            stream.stop()
            return
        entry_price = float(snap.get("last_price") or snap.get("close") or 0)
        if entry_price <= 0:
            print(f"❌ Bad quote price ({entry_price}) — aborting test trade")
            stream.stop()
            return
        shares    = 1
        stop_loss = round(entry_price * (1 - STOP_LOSS_PCT), 4)
        target    = round(entry_price * (1 + TARGET_PCT), 4)
        print(f"\n{'='*60}")
        print(f"🎯 TEST TRADE:")
        print(f"   Ticker:  {TEST_TRADE}")
        print(f"   Entry:   ${entry_price:.2f}")
        print(f"   Shares:  {shares}")
        print(f"   Stop:    ${stop_loss:.2f} (-{STOP_LOSS_PCT*100:.0f}%)")
        print(f"   Target:  ${target:.2f} (+{TARGET_PCT*100:.0f}%)")
        print(f"{'='*60}\n")
        order_id, stop_order_id = execute_trade(TEST_TRADE, shares, entry_price, stop_loss, target)
        if not order_id:
            print("❌ TEST TRADE: buy order failed")
            stream.stop()
            return
        print("✅ TEST TRADE: buy + stop orders placed!")
        send_entry_alert(TEST_TRADE, shares, entry_price, stop_loss, target, entry_price, entry_price * shares)
        trade_result = monitor_trade(
            TEST_TRADE, shares, entry_price, target, stop_loss,
            stream, stop_order_id, vwap=entry_price
        )
        stream.stop()
        new_balance = get_account_balance()
        pnl         = trade_result.get("profit_loss", 0)
        print(f"\n✅ TEST TRADE COMPLETE — P&L: ${pnl:.2f} | New balance: ${new_balance:.2f}")
        return

    # Hard time gate — exit if outside 8:30am–3:30pm ET.
    # Allow mid-day restarts (e.g. Railway redeploy) to resume scanning until cutoff.
    minutes_et = now.hour * 60 + now.minute
    cutoff_min = VWAP_ENTRY_TIMEOUT * 60 + VWAP_ENTRY_TIMEOUT_MIN
    if not (8 * 60 + 30 <= minutes_et <= cutoff_min):
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

    # ── Step 1: Scan Webull screener for RVOL + momentum candidates ──
    gappers = scan_morning_gappers()

    if not gappers:
        print("📋 No candidates from screener — ending session.")
        return

    # ── Step 3: Account balance ────────────────────────────
    balance = get_account_balance()
    print(f"💰 Balance: ${balance:.2f}")
    post_balance_to_dashboard(balance)

    # ── Morning watchlist email ───────────────────────────
    _send_morning_watchlist(gappers[:8], balance)

    # ── Step 4: Log scan for future backtesting ────────────
    try:
        import json as _json
        log_entry = {
            "date":    datetime.now(EASTERN).strftime("%Y-%m-%d"),
            "gappers": [{"symbol": g["symbol"], "change_pct": g.get("change_pct", 0),
                         "price": g.get("price", 0), "float_label": g.get("float_label", "")}
                        for g in gappers],
        }
        log_path = os.path.join(os.path.dirname(__file__), "scan_log.jsonl")
        with open(log_path, "a") as _f:
            _f.write(_json.dumps(log_entry) + "\n")
        print(f"📝 Scan logged ({log_entry['date']})")
    except Exception as _e:
        print(f"⚠️  Scan log write failed: {_e}")

    confidence    = "TECHNICAL"
    position_size = min(balance * MAX_POSITION_SIZE, MAX_TRADE_DOLLARS)
    print(f"💼 Position size: ${position_size:.2f} (capped at ${MAX_TRADE_DOLLARS:.0f} max)")

    # ── Step 5: Build candidate list + open stream ─────────
    gapper_syms = [g["symbol"] for g in gappers if g.get("symbol")]
    print(f"📋 Watching {len(gapper_syms)} candidates: {' | '.join(gapper_syms)}")
    _post_watching_to_screener(gapper_syms)
    _seed_day2_from_gappers(gappers)   # carry today's hard gappers into tomorrow's day-2 observation

    stream_tickers = list(dict.fromkeys(gapper_syms))
    stream         = WebullStream(stream_tickers)
    analysis       = None

    # ── Steps 8-10: Trade loop ─────────────────────────────────────────────────
    remaining_candidates  = list(gapper_syms)
    traded_tickers        = set()
    trade_count           = 0
    session_pnl           = 0.0
    current_balance       = balance
    settled_remaining     = balance

    while True:
        now = datetime.now(EASTERN)
        if now.hour > VWAP_ENTRY_TIMEOUT or (now.hour == VWAP_ENTRY_TIMEOUT and now.minute >= VWAP_ENTRY_TIMEOUT_MIN):
            print("⏰ 3:30pm — entry cutoff reached, no more trades")
            break

        # GFV protection: each trade pulls $100 from the starting settled pool.
        # Stop when settled capital remaining < $100 (can't fund another trade).
        if not DRY_RUN and settled_remaining < MAX_TRADE_DOLLARS:
            print(f"🛑 Settled capital exhausted (${settled_remaining:.2f} left) — done for today")
            break

        # After first trade, rescan for fresh gap stocks — technicals only
        if trade_count > 0:
            print(f"\n🔄 Trade #{trade_count} done — rescanning live market for next setup...")
            fresh_gappers = scan_morning_gappers()
            remaining_candidates = [g["symbol"] for g in fresh_gappers
                                    if g.get("symbol") and g["symbol"] not in traded_tickers]
            for t in remaining_candidates:
                if t not in stream_tickers:
                    stream_tickers.append(t)
            print(f"📋 Fresh candidates: {' | '.join(remaining_candidates) or 'none'}")

        if not remaining_candidates:
            print("📋 No more candidates — session complete")
            break

        # ── Step 8: Watch all gappers — flat top breakout OR EMA bounce ────
        def _intraday_rescan(exclude=None):
            exclude = exclude or set()
            fresh = scan_morning_gappers()
            return [g["symbol"] for g in fresh
                    if g.get("symbol") and g["symbol"] not in exclude]

        breakouts = wait_for_flat_top_entry(
            remaining_candidates, stream,
            rescan_callback=_intraday_rescan,
            traded_tickers=traded_tickers
        )

        if not breakouts:
            print(f"⏰ No entry detected ({', '.join(remaining_candidates)}). Cash preserved.")
            break

        # Mark all breakout tickers as traded before threads start
        for entry in breakouts:
            _t = entry[0]
            traded_tickers.add(_t)
            if _t in remaining_candidates:
                remaining_candidates.remove(_t)

        # ── Steps 8-10: Execute + monitor all breakouts in parallel ────────────
        trade_lock = threading.Lock()

        def _trade_worker(ticker, entry_price, vwap, entry_type="flat_top", extra=None):
            nonlocal session_pnl, trade_count, settled_remaining, current_balance
            extra = extra or {}

            # DATA-ONLY: capture where price sat vs the 90 EMA at entry, so we can later study
            # whether a 90-EMA filter/entry would help. Does NOT affect this trade. See [[project_kev_lessons]].
            entry_ema90 = float(extra.get("ema90") or 0)
            entry_vs_ema90_pct = round((entry_price - entry_ema90) / entry_ema90 * 100, 2) if entry_ema90 > 0 else None
            if entry_vs_ema90_pct is not None:
                print(f"📐 {ticker} entry ${entry_price:.2f} is {entry_vs_ema90_pct:+.2f}% vs EMA90 ${entry_ema90:.2f} (data-only)")
            else:
                print(f"📐 {ticker} EMA90 not available at entry (too few bars) — recording null")

            with trade_lock:
                pos_size = min(current_balance * MAX_POSITION_SIZE, MAX_TRADE_DOLLARS)
                if not DRY_RUN and settled_remaining < MAX_TRADE_DOLLARS:
                    print(f"⛔ {ticker}: insufficient settled capital — skipping")
                    return
                settled_remaining -= MAX_TRADE_DOLLARS

            if entry_type == "ema_bounce" and "ema_stop" in extra:
                stop_loss = round(extra["ema_stop"], 4)
                target_price = round(extra.get("prior_high", entry_price * (1 + TARGET_PCT)), 4)
            else:
                stop_loss = round(entry_price * (1 - STOP_LOSS_PCT), 4)
                target_price = round(entry_price * (1 + TARGET_PCT), 4)
            shares = max(1, int(pos_size / entry_price))

            if entry_price > current_balance:
                print(f"⚠️ {ticker} @ ${entry_price:.2f} exceeds balance — skipping")
                with trade_lock:
                    settled_remaining += MAX_TRADE_DOLLARS
                return

            tag = "EMA BOUNCE" if entry_type == "ema_bounce" else "FLAT TOP"
            print(f"\n{'='*60}")
            print(f"🎯 ENTERING [{tag}]: {ticker}  entry=${entry_price:.2f}  "
                  f"target=${target_price:.2f}  stop=${stop_loss:.2f}  shares={shares}")
            print(f"{'='*60}\n")

            spread_ok, spread_pct = check_bid_ask_spread(ticker)
            if not spread_ok:
                print(f"⚠️ {ticker} spread {spread_pct*100:.2f}% too wide — skipping")
                with trade_lock:
                    settled_remaining += MAX_TRADE_DOLLARS
                return

            l2_ok, l2_details = check_level2(ticker, entry_price)
            if not l2_ok:
                print(f"⚠️ {ticker} L2 rejected: {l2_details.get('reason','')} — skipping")
                with trade_lock:
                    settled_remaining += MAX_TRADE_DOLLARS
                return

            mom_ok, mom_details = check_momentum(ticker)
            if not mom_ok:
                print(f"⚠️ {ticker} momentum rejected: {mom_details.get('reason','')} — skipping")
                with trade_lock:
                    settled_remaining += MAX_TRADE_DOLLARS
                return

            order_id, stop_order_id, actual_fill = execute_trade(
                ticker, shares, entry_price, stop_loss, target_price
            )
            if not order_id:
                print(f"⚠️ Order failed for {ticker}")
                with trade_lock:
                    settled_remaining += MAX_TRADE_DOLLARS
                return

            if actual_fill and actual_fill != entry_price:
                entry_price = actual_fill
                if entry_type == "ema_bounce" and "ema_stop" in extra:
                    stop_loss = round(extra["ema_stop"], 4)
                else:
                    stop_loss = round(entry_price * (1 - STOP_LOSS_PCT), 4)
                    target_price = round(entry_price * (1 + TARGET_PCT), 4)
                shares = max(1, int(pos_size / entry_price))

            _open_trade.update({"active": True, "ticker": ticker,
                                "entry_price": entry_price, "shares": shares,
                                "stop_loss": stop_loss, "target": target_price})
            _post_watching_to_screener([ticker], status="trading")
            send_entry_alert(ticker, shares, entry_price,
                             stop_loss, target_price, vwap, pos_size)
            # Persist the static context SYNCHRONOUSLY (confirmed) BEFORE monitoring, so a
            # crash anywhere after this still records a proper exit. trade_id = idempotency key.
            trade_id = uuid.uuid4().hex
            _save_open_trade_sync({
                "ticker": ticker, "trade_id": trade_id, "entry_price": round(entry_price, 4),
                "target": round(target_price, 4), "stop": round(stop_loss, 4),
                "initial_shares": shares, "remaining_shares": shares, "tier_idx": 0,
                "partial_fills": [], "entry_type": entry_type, "confidence": confidence,
                "position_size": pos_size, "vwap": round(vwap, 4) if vwap else 0,
                "entry_date": datetime.now(EASTERN).strftime("%Y-%m-%d"),
            })

            trade_result = monitor_trade(
                ticker, shares, entry_price, target_price, stop_loss,
                stream, stop_order_id, vwap=vwap
            )

            with trade_lock:
                _open_trade["active"] = False
                _mark_traded_today()
                pnl         = trade_result.get("profit_loss", 0)
                pnl_pct     = trade_result.get("profit_loss_pct", 0)
                exit_reason = trade_result.get("exit_reason", "N/A")
                session_pnl    += pnl
                trade_count    += 1
                current_balance = get_account_balance()
                display_balance = balance + session_pnl

            float_shares = next(
                (d.get("float_shares", "N/A") for d in market_data if d.get("ticker") == ticker),
                "N/A"
            )
            csv_row = log_trade_result(
                date         = datetime.now(EASTERN).strftime("%Y-%m-%d"),
                ticker       = ticker,
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
                "ticker":          ticker,
                "entry_type":      entry_type,
                "entry":           entry_price,
                "exit":            trade_result.get("exit_price", entry_price),
                "shares":          shares,
                "pnl":             pnl,
                "pnl_pct":         pnl_pct,
                "exit_reason":     exit_reason,
                "confidence":      confidence,
                "float_shares":    str(float_shares),
                "position_size":   pos_size,
                "account_balance": current_balance,
                "entry_ema90":        round(entry_ema90, 4) if entry_ema90 > 0 else None,
                "entry_vs_ema90_pct": entry_vs_ema90_pct,
                "trade_id":           trade_id,
            })
            send_summary_email(analysis, trade_result, display_balance,
                               csv_log_line=csv_row, traded_ticker=ticker)
            _clear_open_trade(ticker)   # recorded exit reached — drop durable recovery state

            tag = "EMA BOUNCE" if entry_type == "ema_bounce" else "FLAT TOP"
            print(f"\n{'='*60}")
            print(f"✅ COMPLETE [{tag}] — {ticker}  ${pnl:+.2f} ({pnl_pct:+.1f}%)  [{exit_reason}]")
            print(f"   Session P&L: ${session_pnl:+.2f}  |  Balance: ${current_balance:.2f}")
            print(f"{'='*60}\n")

        threads = [threading.Thread(target=_trade_worker, args=entry, daemon=True)
                   for entry in breakouts]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

    # ── Session wrap-up ────────────────────────────────────
    if trade_count == 0:
        send_summary_email(analysis, None, current_balance)

    stream.stop()

    # Persist the end-of-session balance to screener_app so tomorrow's startup
    # reads the correct number instead of the stale ACCOUNT_BALANCE env var.
    # Use display_balance (session start + P&L) — T+1 means Webull settled cash
    # won't reflect today's proceeds until tomorrow anyway.
    end_balance = balance + session_pnl
    screener_url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if screener_url:
        try:
            requests.post(
                f"{screener_url}/api/update_account",
                json={"balance": round(end_balance, 2)},
                headers={"X-Dashboard-Secret": DASHBOARD_SECRET},
                timeout=5,
            )
            print(f"💾 Saved end-of-session balance ${end_balance:.2f} to screener_app")
        except Exception as e:
            print(f"⚠️  Could not save balance to screener_app: {e}")

    print(f"\n{'='*60}")
    print(f"✅ SESSION COMPLETE — {trade_count} trade(s)")
    print(f"   Session P&L: ${session_pnl:+.2f}")
    print(f"   Balance:     ${end_balance:.2f}")
    print(f"{'='*60}\n")


def next_trading_open(now_et):
    """Return the next 8:45am ET weekday datetime from now."""
    candidate = now_et.replace(hour=8, minute=45, second=0, microsecond=0)
    if now_et >= candidate:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def in_trading_window(now_et):
    """True if we should be scanning/trading right now."""
    if now_et.weekday() >= 5:
        return False
    past_open  = (now_et.hour, now_et.minute) >= (8, 45)
    past_close = now_et.hour > VWAP_ENTRY_TIMEOUT or (
        now_et.hour == VWAP_ENTRY_TIMEOUT and now_et.minute >= VWAP_ENTRY_TIMEOUT_MIN
    )
    return past_open and not past_close


if __name__ == "__main__":
    RESCAN_INTERVAL_MINUTES = 30

    print("🤖 Marcos Trading Bot — always-on worker mode")

    # SAFETY NET: recover + record any trade a crashed prior run left open (the invariant —
    # every entered trade reaches a recorded exit, regardless of what killed the process).
    try:
        _recover_orphaned_trades()
    except Exception as e:
        print(f"⚠️  Orphan recovery failed: {e}")

    # Day-2 observation runs on its own isolated daemon thread (never touches trading).
    threading.Thread(target=_day2_observer_loop, daemon=True, name="day2_observer").start()
    print("🔭 Day-2 observer thread started (observe-only)")

    while True:
        now_et = datetime.now(EASTERN)

        if not in_trading_window(now_et):
            wake = next_trading_open(now_et)
            sleep_secs = (wake - now_et).total_seconds()
            print(f"💤 Outside trading hours — sleeping until {wake.strftime('%A %b %d at 8:45am ET')} ({sleep_secs/3600:.1f}h away)")
            time.sleep(sleep_secs)
            continue

        # In trading window — run a full scan/trade session
        main()

        now_et = datetime.now(EASTERN)
        if not in_trading_window(now_et):
            wake = next_trading_open(now_et)
            sleep_secs = (wake - now_et).total_seconds()
            print(f"⏰ Session complete — sleeping until {wake.strftime('%A %b %d at 8:45am ET')} ({sleep_secs/3600:.1f}h away)")
            time.sleep(sleep_secs)
        else:
            next_et_min = now_et.hour * 60 + now_et.minute + RESCAN_INTERVAL_MINUTES
            next_h, next_m = divmod(next_et_min, 60)
            print(f"\n🔄 Auto-rescan in {RESCAN_INTERVAL_MINUTES} min (~{next_h}:{next_m:02d} ET) — looking for new setups...")
            time.sleep(RESCAN_INTERVAL_MINUTES * 60)
