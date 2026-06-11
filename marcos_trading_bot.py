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
import imaplib
import email
import json
import time
import uuid
import threading
import requests
import anthropic
import resend
import yfinance as yf
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import pytz

# Official Webull OpenAPI Python SDK
try:
    from webull.core.client import ApiClient
    from webull.trade.trade_client import TradeClient
    from webull.data.data_client import DataClient as WebullDataClient
    WEBULL_SDK_AVAILABLE = True
except ImportError:
    WEBULL_SDK_AVAILABLE = False
    WebullDataClient = None
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

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
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
                data.get("last_price") or
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
# STEP 1 — READ ICLOUD EMAIL FOR KEV'S TICKERS
# ============================================================

def read_todays_tickers():
    print("📧 Checking iCloud email for tonight's watchlist...")
    try:
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

        # ── Pass 1: score by SUBJECT HEADER ONLY (fast, reliable on iCloud) ──
        for msg_id in candidates:
            try:
                _, hdr_data = mail.fetch(msg_id,
                    "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
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

                skip_score = {"THE","FOR","AND","NOT","ALL","DAY","TOP","NEW","BIG",
                              "HOT","PDT","RE","AI","ET","FW","FWD","TO","IN","UP",
                              "AM","PM","BODY","SUBJECT","FROM","DATE"}
                subj_upper = subj_c.upper()
                dollar_hits   = len(re.findall(r'\$[A-Z]{2,5}\b', subj_upper))
                watchlist_hits = len(re.findall(
                    r'\bWATCHLIST\b|\bPICK\b|\bTICKER\b|\bSETUP\b|\bPLAY\b', subj_upper))
                caps_hits = len([t for t in re.findall(r'\b[A-Z]{2,5}\b', subj_upper)
                                 if t not in skip_score])
                score = dollar_hits * 5 + watchlist_hits * 3 + min(caps_hits, 10)
                print(f"   [{msg_id.decode() if isinstance(msg_id,bytes) else msg_id}] "
                      f"score={score:2d}  subj={subj_c[:60]!r}")

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

def get_premarket_data(ticker):
    """
    Fetch pre-market quote for ticker via Yahoo Finance (yfinance).
    Free, no API key, includes pre-market price, volume, and fundamentals.
    """
    print(f"📊 Fetching pre-market data for {ticker}...")
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info  = stock.info or {}

        # Pre-market price (available before 9:30am ET)
        pre_price  = info.get("preMarketPrice") or info.get("regularMarketPrice") or "N/A"
        pre_change = info.get("preMarketChangePercent")
        if pre_change is not None:
            pre_change = round(pre_change * 100, 2) if abs(pre_change) < 1 else round(pre_change, 2)

        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose") or "N/A"
        avg_vol    = info.get("averageVolume10days") or info.get("averageVolume") or "N/A"
        mkt_cap    = info.get("marketCap") or "N/A"
        float_sh   = info.get("floatShares") or info.get("sharesOutstanding") or "N/A"

        # Today's intraday volume (pre-market volume estimate)
        pre_vol = info.get("preMarketVolume") or info.get("regularMarketVolume") or "N/A"

        result = {
            "ticker":               ticker,
            "premarket_price":      pre_price,
            "premarket_change_pct": pre_change if pre_change is not None else "N/A",
            "premarket_volume":     pre_vol,
            "previous_close":       prev_close,
            "avg_volume":           avg_vol,
            "float_shares":         float_sh,
            "market_cap":           mkt_cap,
        }
        print(f"   {ticker}: pre=${pre_price}  prev_close=${prev_close}  chg={pre_change}%")
        return result

    except Exception as e:
        print(f"⚠️  Yahoo Finance error for {ticker}: {e}")
    return {
        "ticker": ticker,
        "premarket_price": "N/A", "premarket_change_pct": "N/A",
        "premarket_volume": "N/A", "previous_close": "N/A",
        "avg_volume": "N/A", "float_shares": "N/A", "market_cap": "N/A",
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
    """REST fallback for current price when MQTT is unavailable."""
    try:
        path   = "/openapi/market-data/stock/quotes"
        params = {"symbol": ticker, "category": "US_STOCK"}
        resp   = _get(path, query_params=params, host=MARKET_HOST)
        resp.raise_for_status()
        raw  = resp.json()
        data = raw.get("data", {})
        if isinstance(data, dict):
            items = data.get("items", [])
            d = items[0] if items else data
        elif isinstance(data, list):
            d = data[0] if data else {}
        else:
            d = {}
        price = (d.get("last_price") or d.get("lastPrice") or
                 d.get("close")      or d.get("c") or 0)
        return float(price) if price else 0
    except Exception:
        pass
    return 0


def get_intraday_bars(ticker, count=30):
    """Fetch 1-minute intraday bars for VWAP calculation."""
    try:
        path   = "/openapi/market-data/stock/bars"
        params = {
            "symbol":           ticker,
            "category":         "US_STOCK",
            "timespan":         "m1",
            "count":            str(count),
            "trading_sessions": "REGULAR,PRE_MARKET",
        }
        resp = _get(path, query_params=params, host=MARKET_HOST)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        if isinstance(data, dict):
            return data.get("items", [])
        elif isinstance(data, list):
            return data
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

def analyze_with_claude(email_content, market_data_list, account_balance, gappers=None):
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

    if gappers:
        gapper_lines = []
        for g in gappers:
            rel       = f"{g['relative_volume']:.1f}x avg vol" if g.get("relative_volume") else "rel vol N/A"
            float_lbl = g.get("float_label", "float N/A")
            gapper_lines.append(
                f"  {g['symbol']}: +{g['change_pct']}% pre-mkt | ${g['price']:.2f} | "
                f"{float_lbl} | {rel} | source: {g['source']}"
            )
        gapper_section = "WEBULL MORNING GAPPER SCAN (small-float pre-market movers):\n" + "\n".join(gapper_lines)
    else:
        gapper_section = "WEBULL MORNING GAPPER SCAN: unavailable (screener did not return data)"

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

LIVE PRE-MARKET DATA FROM WEBULL (Kev's picks):
{market_text}

{gapper_section}

YOUR JOB:
1. Read Kev's exact setup rules for each ticker from his transcript
2. Cross-reference with the live pre-market data
3. For each ticker decide: GO or NO-GO based on Kev's rules
4. ALSO evaluate the Webull morning gappers — these are stocks NOT in Kev's list
   but showing strong pre-market momentum RIGHT NOW. If any gapper looks better
   than Kev's picks (stronger gap %, higher relative volume, clean chart setup),
   include it as an additional candidate and consider it for the trade.
5. For GO trades: set exact expected VWAP entry price, profit target, stop-loss
6. Pick the BEST single trade (max 1 trade) — could be from Kev's list OR a gapper
7. Never risk more than 70% of account on one position
8. Honor Kev's rules exactly — if he says NO BREAK = NO TRADE, honor that
9. Flag any major risks (earnings, halts, offerings, T12 halts)

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
            last_vol = float(cached_bars[-1].get("volume") or
                             cached_bars[-1].get("v") or 0)
            avg_vol  = sum(float(b.get("volume") or b.get("v") or 0)
                          for b in cached_bars) / len(cached_bars)
            if last_vol >= avg_vol * 0.75:
                print(f"✅ VWAP reclaim confirmed! ${current_price:.2f} > VWAP ${cached_vwap:.2f} with volume")
                return current_price, cached_vwap
            else:
                print(f"⚠️  Above VWAP but volume light. Waiting for confirmation...")

        time.sleep(stream.loop_sleep())

# ============================================================
# STEP 5 — EXECUTE TRADE VIA WEBULL OPENAPI v2
# ============================================================
#
# All orders use the new /openapi/trade/stock/order/place endpoint.
# Orders are identified by our own client_order_id (UUID hex), not
# Webull's internal orderId — that's what cancel/replace uses too.

def _place_order(ticker, shares, side, order_type,
                 stop_price=None, client_order_id=None):
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
    Places the buy market order then immediately places a real stop order on Webull.
    Returns (buy_client_order_id, stop_client_order_id) — both needed to manage the trade.
    Returns (None, None) on failure.
    """
    shares = max(1, int(shares))   # Webull requires whole shares
    print(f"🚀 Executing: BUY {shares} shares of {ticker} @ ~${entry_price:.2f}...")

    buy_id = _place_order(ticker, shares, "BUY", "MKT")
    if not buy_id:
        print(f"❌ Buy order failed for {ticker}")
        return None, None

    print(f"✅ Buy order placed! Client ID: {buy_id}")
    time.sleep(2)   # Let fill confirm before placing stop

    stop_id = place_stop_order(ticker, shares, stop_loss)
    return buy_id, stop_id


def close_position(ticker, shares):
    """Sell shares at market price."""
    shares = max(1, int(shares))
    print(f"🔒 Closing: SELL {shares} shares of {ticker}...")
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
                  stream: WebullStream, stop_order_id):
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
# STEP 7 — ALERT EMAILS (fired in real-time during the session)
# ============================================================

def send_alert_email(subject, body):
    """Sends email via Resend API over HTTPS — bypasses Railway's SMTP block."""
    print(f"📲 Sending alert to {SUMMARY_EMAIL}: {subject}")
    try:
        resend.api_key = RESEND_API_KEY
        footer = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nMarcos Trading Bot | Railway.app"
        r = resend.Emails.send({
            "from":    "Marcos Trading Bot <onboarding@resend.dev>",
            "to":      [SUMMARY_EMAIL],
            "subject": subject,
            "text":    body + footer,
        })
        print(f"✅ Alert sent! Resend id={getattr(r, 'id', r)}")
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
Marcos Trading Bot | Claude Opus AI + Webull OpenAPI v2
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

    # ── Credential check ───────────────────────────────────
    tok = WEBULL_ACCESS_TOKEN
    key = WEBULL_APP_KEY
    print(f"🔑 APP_KEY   : {key[:6]}...{key[-4:] if len(key)>10 else '(short)'}")
    print(f"🔑 TOKEN     : {tok[:6]}...{tok[-4:] if len(tok)>10 else '(short/missing)'} (len={len(tok)})")
    print(f"🔑 ACCOUNT_ID: {WEBULL_ACCOUNT_ID}")

    if now.weekday() >= 5:
        print("📅 Weekend — markets closed.")
        return

    # ── Step 1: Read iCloud email ──────────────────────────
    subject, email_content = read_todays_tickers()
    if not email_content:
        send_summary_email(None, None)
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

    # ── Step 3: Pre-market data + Webull gapper scan ──────
    market_data = []
    for t in tickers:
        if t != "UNKNOWN":
            market_data.append(get_premarket_data(t))
            time.sleep(0.5)

    # Scan Webull screener for morning gappers (~8:50am — before analysis)
    gappers = scan_morning_gappers()

    # ── Step 4: Account balance ────────────────────────────
    balance = get_account_balance()
    print(f"💰 Balance: ${balance:.2f}")

    # ── Step 5: Claude Opus analysis ───────────────────────
    analysis = analyze_with_claude(email_content, market_data, balance, gappers=gappers)
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
    position_size   = float(recommended.get("position_size_dollars",
                                            balance * MAX_POSITION_SIZE))

    # ── Step 6: Open real-time MQTT stream ─────────────────
    # Include gapper tickers in the stream so we can trade them if Claude picks one
    gapper_syms = [g["symbol"] for g in gappers] if gappers else []
    stream_tickers = list(dict.fromkeys(tickers + gapper_syms))  # deduped, order preserved
    stream = WebullStream(stream_tickers)

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
    shares       = max(1, int(position_size / entry_price))

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
    order_id, stop_order_id = execute_trade(
        ticker_to_trade, shares, entry_price, stop_loss, target_price
    )
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
