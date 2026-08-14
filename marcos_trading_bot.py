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
import atexit
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

# Silence noisy SDK loggers — they flood Railway's 500 logs/sec limit (drops real errors).
logging.getLogger("webull").setLevel(logging.ERROR)
logging.getLogger("webull_openapi").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
# The Webull SDK RE-RAISES its own child loggers to INFO on every client init, overriding the
# setLevel calls above — so the token-init storm leaks through and hits Railway's log cap. A
# global disable below ERROR is the one gate the SDK's per-logger setLevel can't override.
# The bot's own output is all print()-based, so this muffles only library noise, never our logs.
logging.disable(logging.WARNING)

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

# 7/14 MID-DAY LOAD RELIEF: the SDK's ERROR logs dump full request objects (~30 lines each); during a
# 429/reset storm that blows Railway's 500 logs/sec cap and DROPS our own prints (45K lost 7/14).
# One line per error is plenty — our except-paths already print concise warnings.
import logging as _logging
_logging.getLogger("webull").setLevel(_logging.CRITICAL)

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

# ── 429-KILL set (7/18, Marcos: "whatever is needed to eliminate the 429 spam do it") ────────
# The SDK logs every ServerException at ERROR with the FULL SIGNED REQUEST — x-access-token
# included — to stdout (client.py:360-362; data_client's default set_stream_logger), and
# response.py force-sets its own logger to DEBUG with a private StreamHandler. On a 429 burst
# that's the 500 logs/sec Railway storm that dropped 45K of our own prints (7/14) AND the token
# leak. Fix: every webull.* logger → CRITICAL (each individually — a child's explicit level
# beats any parent setting). Our own _exec_health counters/prints stay the observability.
# NOTE: the already-leaked token still needs ROTATION — silencing stops NEW leaks only.
try:
    from webull.core.exception.exceptions import ServerException as _WBServerException
    if not (isinstance(_WBServerException, type) and issubclass(_WBServerException, BaseException)):
        raise ImportError("stubbed module")
except Exception:
    class _WBServerException(Exception):   # rig/stub fallback — keeps `except` clauses valid
        http_status = None

def _silence_webull_sdk_logs():
    import logging
    names = {"webull", "webull.core", "webull.core.client", "webull.core.http.response"}
    names.update(n for n in logging.root.manager.loggerDict if n.startswith("webull"))
    for n in names:
        logging.getLogger(n).setLevel(logging.CRITICAL)

_silence_webull_sdk_logs()   # pre-import: pins the known names before the SDK loads

def _get_data_client():
    """Return a cached DataClient, initializing once per process."""
    global _cached_data_client
    if _cached_data_client is None:
        _, _cached_data_client = _make_data_client()
        _silence_webull_sdk_logs()   # client init (re)configures SDK loggers — re-silence after
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
MAX_TRADE_DOLLARS     = 1000.00 # Notional cap per trade (~33% of the $3k sim account; tight Kev setups bump it — 7/11)
MAX_POSITION_SIZE     = 0.70   # Max 70% of account on single trade (HIGH confidence)
POSITION_SIZE_MEDIUM  = 0.50   # 50% for MEDIUM confidence
POSITION_SIZE_LOW     = 0.30   # 30% for LOW confidence
STOP_LOSS_PCT         = 0.07   # -7% CATASTROPHE backstop ONLY (caps risk); the real stop is structural
ZONE_STOP_BUFFER      = 0.003  # Kev "<5c below the level": stop sits just below the demand-zone (base) low
TARGET_PCT            = 0.20   # 20% full profit target (fallback target only)
# Exit sizing/tiers/trail are now Kev R-based inside monitor_trade (SUPPLY_EXIT_DESIGN.md), NOT fixed
# percentages — the old EXIT_TIERS_AM/PM (+8/12/20%, +4/6%) and TRAIL_PCT (5%) were made-up and are removed.

# ── Selection-weighting parameters (Kev's pick criteria — [[project_kev_lessons]]) ──
# Marcos 7/24 (#108): bot float eligibility raised to the scanner's 50M Kev-watch band —
# OMH (21.3M, Kev's best 7/24 trade, textbook curl) was blocked by the old 20M line. The 20M
# "Kev gospel" number stays the RANKING tilt (gap%/float); 20-50M band trades get graded live.
BOT_MAX_FLOAT = float(os.environ.get("BOT_MAX_FLOAT_M", "30")) * 1_000_000  # Marcos 7/24: 30M — covers every documented Kev exception (OMH 21.3M) w/ margin; ZERO corpus receipts for 30-50M; scanner still SHOWS to 50M so a missed 30-50M ripper = logged counterfactual to revisit
# Base rank = gap% / float_m (big gap on a small float). These tilt it toward Kev's other
# selection signals that the scan already fetches but used to discard:
HTB_SQUEEZE_MULT   = 1.5    # Hard-to-borrow = heavy short interest = squeeze fuel (Kev, FCHL "97% short → squeeze")
RVOL_BOOST_CAP     = 5.0    # cap the relative-volume tilt (×1.5 max) so volume can't drown out gap/float

# ── v10 Entry detection parameters ────────────────────────────
SETUP_TF_MIN       = 3      # Kev's SETUPS come from the 3-MIN chart ("it all has to start with the
                            # three minute... no ifs ands or buts" #215); 1-min = entry timing + risk only.
                            # (5-min is his accepted substitute; Webull has no M3 so we roll it from M1.)
EXITS_ON_3MIN      = True   # ⚠️ 7/2 THE TIMEFRAME FIX: manage the TRADE on the 3-min chart too (not just the
                            # setup). Stop/trail/topping-tail exit on a 3-MIN CLOSE, not 1-min/sub-minute noise.
                            # Winner test: 1-min mgmt −0.4R vs 3-min mgmt +4.4R on the 35 winners (they hold &
                            # capture instead of getting wick-sniped). Only the −7% catastrophe cap stays intrabar.
                            # Disables the sub-minute failed-breakout + early-VWAP-fade cuts. [[project_kev_grounding]]
# ── TRUE INTRABAR STOP (7/27, Marcos 3× reaffirmed "tired of −3R, −2R, −1.5R"). EXITS_ON_3MIN left
#    the stop evaluable ONLY on a 3-min close, and the docstring's "resting broker stop" does not
#    exist (place_stop_order always returns None — Webull rejects stop types), so a healthy-feed
#    crater rode free: LGHL 7/27 −3.3R on a −1R plan; 36/51 era stop-exits (71%) exited BELOW their
#    stop, $441.54 beyond plan. Measured cost of the fix = the wick-shakeout class, n=2 ≈ $57
#    (LVWR 7/24 −$0.26, DFNS 7/27 −$2.29 → both become ~−1R), resolution-limited to 1-min.
#    BOUNDARY (stated, not claimed away): this caps DECISION lag, not gaps/slippage — fast tape can
#    still print −1.1..−1.2R. Exact −1R needs the resting broker stop = its own night.
#    ⚠️ ONE PRIOR REFUTATION ON RECORD, and it is of THIS mechanism: the accidental "breach-mode"
#    live 7/14 (B11 firing intrabar on a 20s-sustained stream breach) cost −2.08R net and the note at
#    _blind_stop_should_fire says hair-trigger stops "kill the YYGH-class winners". That refutation is
#    in the CODE but never made the ledger, so the 7/27 verdict was rendered without it. Tonight ships
#    with ZERO confirm (Marcos 3× reaffirmed, and the 7/27 numbers are the newer evidence: $441.54
#    blow-through excess over 36 trades vs ≈$57 measured shakeout cost) — but the dial below exists so
#    the answer to a shakeout day is one env var, not a redeploy of new logic.
INTRABAR_STOP      = os.environ.get("INTRABAR_STOP", "1") == "1"   # kill switch → back to close-only
RESTING_STOP       = os.environ.get("RESTING_STOP", "1") == "1"    # exchange STOP_LOSS order at the broker
                            # (fixed 8/2: order_type=STOP_LOSS + stop_price; June tried STP/aux_price).
                            # Inert under DRY_RUN. 0 → software stop only, no redeploy needed.
INTRABAR_CONFIRM_SECS = float(os.environ.get("INTRABAR_CONFIRM_SECS", "0"))  # 0 = exit on the FIRST print
                            # at/below the stop (as approved). Raise it (e.g. 3) to require the breach to
                            # persist that long — filters single bad prints at the cost of that much lag.
CRATER_FLOOR_R     = float(os.environ.get("CRATER_FLOOR_R", "2.0"))  # backstop at this many R of loss.
                            # ⚠️ HONEST SCOPE (7/27 review F2): the floor sits BENEATH the stop by
                            # construction — entry−2R is always below both the structure stop (entry−R)
                            # and the BE stop (entry) — and the intrabar branch is checked first. So with
                            # INTRABAR_STOP=1 this is UNREACHABLE. It is the backstop for the intrabar
                            # stop being OFF or killed, NOT a broken-feed failsafe: every feed condition
                            # that blanks one blanks the other (both read the same `current_price`).
                            # A real feed-independent failsafe would key off last_good_price age or a
                            # REST quote — not built tonight, not claimed. 0 disables.
RUNNER_HEALTH_EXIT = True   # 7/3 PULLBACK HEALTH-TRAIL (the day's find — [[persona_trade_manager]]). Replaces the
                            # twitchy soft exits (instant-exit / prev-bar-low / topping-tail) with a STRUCTURE read:
                            # HOLD the runner while price is above VWAP OR the 9-EMA (healthy pullback), FOLD only
                            # when a 3-min bar CLOSES below BOTH (structure gone). Breakeven stop = the hard floor.
                            # Data: healthy pullbacks hold VWAP 84%/EMA 67% vs dying 30%/26% (vol-on-pullback = noise).
                            # Backtest (4 days, n=52): baseline −4.3R → +1.7R, beats baseline ALL 4 days. DRY_RUN,
                            # validating forward. Backtests: scratchpad/health_robust.py + trade_cracks.py.
BREAKOUT_ENTRIES   = True   # 7/2: KEV'S FULL BAG. The 4-day backtest is too noisy to reliably rank entries
                            # (same pullback scored +0.30 and −0.08 across two valid harnesses) → build Kev's
                            # real setups to spec, instrument them, and let LIVE data rank them (not a fragile
                            # backtest). True = flat-top/ORB breakouts ON alongside pullback + VWAP-reclaim (all
                            # 3-min managed). Bounce stays observe-only (its one backtest read was clearly −0.40).
FLAT_TOP_WINDOW    = 4      # consolidation window (in 3-min bars now → ~12 min base). Kev gives NO bar
                            # count; this is a homegrown translation of "a base that held". [revisit w/ data]
# ── 7/31 ONE-DAY EXPERIMENT (Marcos 7/30 night: "for one day let's reverse the order and just
# see. Either way we have the data."). PULLBACK_FIRST=1: when the MA-pullback detector fires on a
# scan pass, it OUTRANKS flat_top on that name — the flat-top block (arming included) is skipped
# and the original ma_pullback block converts. Era context for the record: ma_pullback +$160.82
# (70.6% win, best lane) vs flat_top front-side −$148.73 (36.4%); LINE ORDER alone gave flat_top
# priority on the same names. Suppressions log `pullback_first_suppress` so the counterfactual is
# exact. Friday grades it next to the 444-fire front-side study. PULLBACK_FIRST=0 reverts.
PULLBACK_FIRST     = os.environ.get("PULLBACK_FIRST", "1") == "1"
FLAT_TOP_MAX_RANGE = 0.12   # base-width chase-GUARD, not a Kev number. Kev quantifies no % range ("tighter
                            # is better" = tighter stop = better R:R). The ROOM GATE already filters width via
                            # R:R = (supply−entry)/(entry−base_low); a wide base = far stop = poor R:R = rejected
                            # for the RIGHT reason. So this is a loose guard against vertical 20%+ chases only;
                            # widened 8%→12% to catch the non-flat/rally-base bases (median ~10%) the rigid cap
                            # missed (they were only logged as broke_not_flat). [translation — revisit w/ data]
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
# 90-EMA-as-a-signal — Kev enters off WHICHEVER rising MA the pullback holds (9 = the EMA-bounce above)
MA_PULLBACK_LEVELS      = [9, 20, 50, 90]  # all of Kev's pullback MAs — fire off the deepest the low held
MA_PULLBACK_TOUCH_TOL   = 0.005   # low within 0.5% of the MA = "pulled back to it"
BOTTOM_TAIL_RATIO       = 0.40    # lower wick ≥40% of range = wicked off the low (a buyer stepped in)
MA_PULLBACK_STOP_BUFFER = 0.01    # stop just below the MA the pullback held
BOUNCE_MIN_RUN          = 0.15    # Kev #28 mean-reversion bounce: name must have RUN ≥15% earlier (a former
BOUNCE_MIN_DD           = 0.10    # runner) then ROUND-TRIPPED ≥10% off the high before the reclaim. Homegrown → revisit.
MA_RISING_LOOKBACK      = 5       # the MA must be rising over this many bars (uptrend)
EXTENSION_MAX_PCT       = 0.25    # 7/3 EXTENSION GUARD: skip an entry whose price is >25% above the 90-EMA (chasing
                                  # extended = Kev "don't chase"; L2 R11). Data (52 trades): losers +42% ext vs winners
                                  # +13%; gated in the bot → avgR +0.03→+0.25, totalR +1.7→+9.6/4d. Fail-open (no 90-EMA).
# ── IGNITION ENTRY (7/4) — the fast-vertical catch. Reverse-engineered from the 8 fast verticals (6/29–7/2).
#    QUIET early base → a VOLUME-ACCEL bar breaks it while NOT-yet-extended (+3–15%) → vertical. 1-min bars,
#    NOT gated on above-VWAP (quiet base sits below VWAP); the surge IS the trigger. Tight stop = base low.
IGNITION_ENABLED       = True
# ⚡ LOOSENED 7/5 (aggressive combined config) — the robustness sweep + decomposition showed the shipped
#    values were CONSERVATIVE-by-default: looser scored higher on 4 days AND the added trades were BROADLY
#    positive (marginal 20 trades, +27.4R, 18/20 won — NOT one fat trade; concentration DROPPED). Nearly 2× the
#    trades (28→48) + 2× R (+36→+70), catches 5/8 fast verticals. Serves the DRY_RUN goal (more trades to learn,
#    don't add limiters). MAX_EXT kept tight (the one mechanism gate). Watch EXEC HEALTH (429s/peak positions) —
#    this is untested at ~2× volume; the backtest assumes flawless execution the live bot may not deliver.
IGNITION_WINDOW_MIN    = 90      # fire through the first 90 min (was 45). Sweep: +35.9→+46R; spreads trades (gentler concurrency)
IGNITION_BASE_MIN      = 1       # min base bars before a break (1 catches immediate igniters)
IGNITION_BASE_LOOKBACK = 4       # base = the last N 1-min bars before the break (was 6; sweep +35.9→+43R, 4/4 marginal won)
IGNITION_VOL_MULT      = 2.0     # ignition bar vol ≥ 2.0× base avg (was 2.5; looser surge bar, sweep-favored)
# ── 7/30 FABLE SHIP + Marcos "ship it and shadow the alternative": DETECT at 2.0× (shadow keeps
# accumulating the old cohort), CONVERT only at ≥ IGNITION_CONVERT_MULT. Fine sweep E1 with a
# pre-registered OOS split: 2.0× = worst tested value ≥ it (+1.60/+1.98 $/fire), 4.0–6.0 = a
# contiguous plateau, 4.5× halves nearly identical (+5.51/+5.61). Fires with volx below the
# convert bar log `ignition_below_convert` — that IS the shadowed 2.0× alternative, graded Friday.
# FAILURE CONDITION (pre-registered): wrong if the shadowed 2.0×-gated cohort out-earns live.
IGNITION_CONVERT_MULT  = float(os.environ.get("IGNITION_CONVERT_MULT", "4.5"))
# E3/E4: chart gate measured INVERTED on ignition (gate-ON −$19.80 n=5 vs gate-OFF +$482.51 at
# 4.5×; the gate admits only fires past Kev's level = a LATENESS detector on a surge-off-base
# lane). Marcos 7/30: ship the bypass, shadow the alternative — every fire still stamps the
# gate's verdict so the gated counterfactual accrues. Kill switch: IGNITION_CHART_BYPASS=0.
IGNITION_CHART_BYPASS  = os.environ.get("IGNITION_CHART_BYPASS", "1") == "1"
IGNITION_MIN_ABS_VOL   = 5000    # abs-volume floor (was 10k; sweep +35.9→+47R, 7/9 marginal won; $100 pos = negligible slippage)
IGNITION_MAX_EXT       = 0.15    # ignition close ≤ +15% from open (NOT-yet-extended). KEPT TIGHT — the one mechanism gate
                                 # (loosening = chasing extended, contradicts the entry thesis; do NOT widen).
IGNITION_MIN_EXT       = -0.05   # ignition close ≥ −5% from open (was −0.03; the sweep's mild cliff — softened for margin).
                                 # Still cuts the deep dump-bounces (BTCT −14.9%, CWD −11.4%); break UP from near the open.
IGNITION_STRONG        = 0.5     # ignition bar closes in the top ≥50% of its range (buyers won the bar)
IGNITION_DAILY_VETO    = False   # ignition is EXEMPT from Kev's daily-first veto — DATA-DECIDED (7/5, real
                                 # split-adjusted daily-veto backtest): the fast verticals are beaten-down
                                 # low-float squeezers BELOW their daily MAs (ZCMD/CCTG ignited under their d20);
                                 # the veto (a proxy for "dead name, no range") misfires on this archetype and
                                 # rejects the winners. Exempt = +29.8R vs +16.1R w/ veto over 4 days, catches
                                 # ZCMD+CCTG the veto killed. Other entries KEEP the veto. Revisit w/ DRY_RUN data.
# ── SCALE-OUT GRID (7/5 exit study) — progressive scale-out as R-multiples of the entry risk. ⚠️ NOT Kev's
#    exact numbers: Kev sells "quarters into levels" (supply / round-$ / halt-band) but QUANTIFIES NONE of it,
#    so this is a REIMAGINED translation of his "sell into strength" shape into concrete, testable levels.
#    Reverse-engineered from the exit forensics + backtested on real bars: 50%@+1R / 25%@+2R / 15%@+3.5R /
#    10% health-trailed runner BEATS the old "25%@supply-or-+2R" (supply fires too low — room calc is de-inverted).
#    Full-population 4-day faithful backtest: +25.8R → +32.2R (helps ignition +5.8R + ma_pullback +0.5R, neutral
#    on flat_top/vwap_reclaim, hurts none; median R +0.65→+1.16). Over-scaling (a 4th tranche) was WORSE — rejected.
#    Homegrown levels → calibrate w/ DRY_RUN data; the real fix is better supply levels (round-$), a later build.
# ── EXIT PROFILE (7/19, Marcos: "Challenger D is even more Full on Kev" — and it IS Kev's canonical
# legs: half at +1R, quarter into strength, QUARTER RIDES, stop stays at STRUCTURE through the +1R
# retest). Kill-tested 3-0 vs the old grid: +$11.09 (single-entry sim), +$212.50 (refire sim),
# +$115.68 (real survivors resim — Monday's runners +$213.09 vs +$69.86). The old grid becomes the
# EOD SHADOW comparison. EXIT_PROFILE=grid10 env = instant revert (flip only when FLAT — restart).
EXIT_PROFILE = os.environ.get("EXIT_PROFILE", "kev25")
if EXIT_PROFILE == "grid10":
    SCALE_TIERS          = [(1, 0.50), (2, 0.75), (3.5, 0.90)]  # the 7/5 grid: 10% runner
    BE_FLOOR_AFTER_SCALE = 1                                    # BE after the FIRST partial
else:
    SCALE_TIERS          = [(1, 0.50), (2, 0.75)]               # Kev legs: 25% RUNNER
    BE_FLOOR_AFTER_SCALE = int(os.environ.get("BE_FLOOR_AFTER_SCALE", "2"))   # 7/28 REVERTED to 2 (Marcos,
                            # pre-open — "the new change hasn't run yet"): BE@1 had governed ZERO trades, BE@2
                            # is the 7/19 KILL-TESTED setting, and with BE@2 live the BE@1 counterfactual is
                            # EXACT (contained inside every observed trade; the reverse needs simulated exits).
                            # Friday grades BE@1 vs BE@2 in dollars; the law ships permanently if it's cheap.
                            # Marcos's law is "once you've banked, the trade cannot go red." Holding STRUCTURE
                            # through scale #2 was coherent-but-wrong: measured harm 4 banked-then-red trades,
                            # −$7.98 (the previously-circulated $63.75 was not reproduced). Cost is small; the
                            # law is the reason. Revert = 2, and it is now an ENV var so the revert costs a
                            # restart, not a deploy.
                            # ⚠️ COMPOUNDING RISK, UNMEASURED (7/27 review F1): this was measured while the BE
                            # stop was only evaluable on a 3-MIN CLOSE. Item 1 makes that same stop tick-level,
                            # so after the first partial ANY wick touching entry now ends the trade — which is
                            # the behavior the 7/19 kill-test refuted (12 BE-scratches → 0 when the floor moved
                            # to scale #2). The PRODUCT of the two changes was never replayed; era replay needs
                            # the entry timestamps that only start accruing tonight. BE_FLOOR_AFTER_SCALE=2 for
                            # one session isolates item 1 at zero code cost.
# ── VELOCITY-AWARE RIDE (7/5) — don't sell into strength. At each scale tier, if the move is STILL accelerating
#    hard (gained >=VELO_RIDE_PCT over the last VELO_BARS 1-min bars — the "ff3" 3-bar-follow-through signature
#    that separated verticals from chop in the feature study), DEFER the scale and let the full position ride;
#    resume banking when it stalls. Chop never trips the gate → scales per the normal grid (exact baseline).
#    Backtest (33 ignition fires, 4 days): +11.1R→+19.4R, fast-vertical capture 22%→47%, WR held 67%. Every
#    param cell beat baseline (robust mechanism), BUT ~68% of the gain is one trade (ZCMD) + the reverse-after-
#    defer downside is under-sampled — shipped to DRY_RUN to validate live. Kill-switch: VELOCITY_RIDE=False. ──
VELOCITY_RIDE   = True     # DRY_RUN experiment (7/5) — defer scaling while accelerating; flip False to revert
VELO_RIDE_PCT   = 0.12    # defer the scale if price gained >= this over the last VELO_BARS 1-min bars
VELO_BARS       = 3       # rolling velocity window (1-min bars) — matches the ff3 finding (3-bar follow-through)
# 7/30 FABLE RULING Q4: vride suppressed EVERY hidden scale (1 of 11 trades ever banked; WLDS had
# 11 closes above 1R and banked nothing) while measuring mildly POSITIVE on ignition (+$43.89 at
# 4.5×). Scoped exemption, not a global kill — lanes listed here never defer. Env-overridable.
VRIDE_EXEMPT    = set(filter(None, (s.strip() for s in os.environ.get(
    "VRIDE_EXEMPT", "hidden_entry").split(","))))
# ── 7/30 RESTING BANK (Marcos: "all of our banking numbers should be limit orders waiting" +
# "It's stupid to wait"). DRY_RUN bookkeeping of the resting-limit design: a tier is FILLED when
# the tape has printed AT/THROUGH it (_tape_hi) or the stream price sits at/above it, and the fill
# books AT TIER PRICE (a resting limit fills at its limit — conservative, never better). While ON,
# vride is NOT consulted for tier fills: a resting order at the broker cannot defer. At go-live the
# same scaffold swaps simulated fills for real broker limits. Kill switch: RESTING_BANK=0.
# FAILURE CONDITION (pre-registered): wrong if wick-trimmed runners cost more than banked-at-number
# gains — gradeable from the fill-source stamp on every partial.
RESTING_BANK    = os.environ.get("RESTING_BANK", "1") == "1"
MIN_RR             = 2.0    # minimum reward:risk ratio for EMA bounce
VWAP_ENTRY_TIMEOUT     = 15    # No new entries after 3:30pm ET (not enough time to run)
VWAP_ENTRY_TIMEOUT_MIN = 30   # minute component of final cutoff
FIRST_TICKER_CUTOFF_MIN = 20  # Switch to backup ticker if #1 hasn't set up by 9:50am ET
TRADE_WINDOW_END_HOUR = 15     # Force close all positions by 3:45pm ET (before market close)
TRADE_WINDOW_END_MIN  = 45    # minute component of force close
ENTRY_LIMIT_BUFFER    = 0.01   # Limit buy 1% above VWAP reclaim — caps slippage on small floats
EARLY_FADE_SECS       = 120    # If price drops below VWAP within 2 min of entry, exit immediately
# Kev "instant resolution or cut": if a breakout never confirms and fades back to entry, cut at break-even
FAILED_BREAKOUT_SECS    = 75     # window for the breakout to resolve before the cut disarms
FAILED_BREAKOUT_CONFIRM = 0.015  # +1.5% = "it resolved" (rule disarms); else a fade to ≤entry = instant cut
FAILED_BREAKOUT_MIN_SECS = 30    # ⚠️ THE 0s-CUT FIX (7/2): a fill marks at the BID (a tick below the ask we
                                 # entered at), so at t=0 "current_price <= entry_price" is trivially true and
                                 # the failed-breakout cut fired INSTANTLY on EVERY trade — turning every entry
                                 # into a 0s breakeven and hiding all real behavior (a full week of it). The cut
                                 # cannot arm until the break has had ~30s to confirm. The −7% structural stop
                                 # still protects a genuine crater in that window. [[feedback_test_push_parity]]
PULLBACK_TIMEOUT_SECS   = 240    # after a flat-top break, wait up to this long for the RETEST; else disarm.
PULLBACK_TOL            = 0.01   # price within 1% of the broken level = "pulled back to it". Enter the
                                 # RECLAIM after the dip (Kev buys the pullback, not the break spike) — faithful-
                                 # harness validated +0.26R vs −0.17R break-tick on identical setups (7/2).
# Small-cap momentum plays are largely uncorrelated to SPY on catalyst days.
# -1% is a normal red morning — Kev trades ICCM day-2 regardless of SPY.
MAX_SPREAD_PCT        = 0.06   # Skip entry if bid-ask spread > this % of ask. HOMEGROWN (Kev only says
                              # ">$10 gets spready", no hard cap). Widened 3%→6% on LIVE 7/1 data: RNAZ
                              # (3.89%) + WSHP (3.88%) both broke out with good room but got spread-rejected
                              # at 3% — small-float HTB gappers naturally run 3-4% spreads and Kev trades
                              # them. 6% catches that class, still blocks untradeable. [revisit w/ data]
MOMENTUM_BARS        = 3      # Check last N bars for momentum
MOMENTUM_MIN_AVG_VOL = 10_000 # Avg volume over last N bars must exceed this
EXPANSION_MIN        = 1.5    # HARD GATE (7/2 momentum-BUILDING): break-bar vol ÷ base avg = contraction→
                              # expansion (Kev "volume expands on the break"). Measured on 80 breaks: <1.5×
                              # base won 32% vs 1.5–3× won 62%, 3–6× won 53%. Homegrown-calibrated → REVISIT.
PEAK_REL_MIN         = 0.30   # HARD GATE (7/2 dead-duck fix): break-bar vol must be ≥30% of the session's
                              # peak-so-far 1-min vol. Measured on 83 breaks: <30% of peak won ~8%, ≥30% won
                              # ~27–36%. Homegrown-CALIBRATED (not a Kev number) → REVISIT as data accrues.
MOMENTUM_VOL_ACCEL   = 2.0    # (recorded as break_accel; the hard gate is now building+peak-relative, not this)
                              # volume surge. Was 1.2 & OBSERVE-only; 3-day backtest showed instant-cut trades
                              # had 1.9× accel vs 6.1× for winners → hard-gating at 2× (+ de-inverting room)
                              # flipped avg-R −0.20 → +0.26. Momentum is now the PRIMARY entry filter.
MOMENTUM_GREEN_BARS  = 2      # At least N of last 3 bars must close green (close > open)
# Watchdog: a price-quote SDK call has NO built-in timeout, so one hung call can freeze the
# monitor loop forever and leave a position stuck open (the BOXL incident, June 24). Hard-cap
# every quote call, and force-exit if the feed goes dead so a position can never sit blind.
QUOTE_TIMEOUT_SECS   = 8      # Max seconds to wait on a single Webull quote call
STALE_FEED_EXIT_SECS = 90     # If no valid price for this long mid-trade, force-close for safety
BARPX_MAX_AGE = float(os.environ.get("BARPX_MAX_AGE", "60"))   # 7/29: quote-dead monitor may ride 10s bar closes this fresh

# ── HALT AWARENESS (7/28, docket #1 — evidence: DFNS 7/27) ────────────────────────────────────
# DFNS ran +194% and printed: 15:35:40 (vol 3,243) -> ZERO BARS for 5 MINUTES -> 15:40:40 (vol
# 115,361). A multi-minute zero-trade gap bracketed by heavy volume is the LULD volatility-halt
# signature. The bot held straight through it and could not distinguish "halted" from "quiet".
# We do NOT have a confirmed vendor halt field (the RTH payload dump above exists to answer that).
# So this detector is VENDOR-INDEPENDENT: it reads the 10s tape we already collect.
# LOG-ONLY by construction — it must never gate an entry or force an exit until graded. A halt
# resolves UP as often as down (DFNS resumed +10% in 20s); acting on suspicion is an untested bet.
HALT_GAP_SECS   = float(os.environ.get("HALT_GAP_SECS", "120"))   # zero-trade gap that looks like a halt
_halt_state: dict = {}        # (day, sym) -> last logged gap start, so one halt logs once
# Module-level mirror of the session's held names — the session loop's `reentry["held"]` and
# `_reservations` are FUNCTION-LOCAL, unreachable from _curl_feed. The watch loop refreshes this
# set each cycle; the halt logger reads it. A stale mirror mislabels `held` on one row, never trades.
_halt_held_mirror: set = set()


def _halt_suspect(sym, d10):
    """Vendor-independent halt suspicion from the 10s tape. Returns (suspect, gap_secs, last_ts).
    A gap only counts DURING RTH (premarket is legitimately sparse — that is not a halt).
    Never raises: a detector bug must not touch the trade path."""
    try:
        if not d10:
            return False, 0.0, None
        hm = datetime.now(EASTERN).strftime("%H:%M")
        if hm < "09:30" or hm >= "16:00":
            return False, 0.0, None
        last_k = max(d10)
        gap = time.time() - (last_k + 10)          # +10: the bucket itself spans 10s
        return (gap >= HALT_GAP_SECS), round(gap, 1), last_k
    except Exception:
        return False, 0.0, None


def _log_halt_suspect(sym, gap, last_k, held=False):
    """One row per halt episode per name per day (not per poll)."""
    try:
        day = datetime.now(EASTERN).strftime("%Y-%m-%d")
        key = (day, sym)
        if _halt_state.get(key) == last_k:
            return                                  # same episode, already logged
        _halt_state[key] = last_k
        print(f"⏸️  {sym} HALT-SUSPECT: no 10s prints for {gap:.0f}s (>{HALT_GAP_SECS:.0f}s)"
              f"{' — POSITION OPEN' if held else ''}")
        _log_decision(sym, "halt_suspect", gap_secs=gap, held=bool(held),
                      last_bar_ts=int(last_k) if last_k else None)
    except Exception:
        pass
# ── DIP AND RIP (7/30, Marcos: "go ahead and build it" / "Test it before you ship it") ──
# Kev's 9-year halt strategy (uxdFKpYQC2o + Pj8fKT4lsaU), spec'd from his own AMIX 7/29 narration:
# halt UP on a SHEET name -> never chase into the halt -> on resumption wait for the FLUSH to tag
# the zone just over his marked level ("that 529 level... I watch for a dip over that level and see
# if it holds") -> enter on the CONFIRM bar back up, stop just below the level ("<5c below").
# 7/29 ground truth: our halt detector flagged AMIX 09:39:38; resumption flush bar 09:40:40
# (o5.96 l5.50); level 5.29 was on our sheet; Kev bought 5.49 -> 7.25. Every ingredient existed —
# this lane is the wiring. WRONG WHEN: the halt was the top and the level-bounce is a dead cat —
# bounded by stop-below-level + width-proportional sizing; expired/broken watches log why.
# Kill switch: DIP_RIP=0. TAG-then-CONFIRM (the flush knife bar itself is never bought).
DIP_RIP         = os.environ.get("DIP_RIP", "1") == "1"
DIPRIP_ZONE     = float(os.environ.get("DIPRIP_ZONE", "0.05"))      # tag zone: level .. level*(1+5%)
DIPRIP_WINDOW_S = float(os.environ.get("DIPRIP_WINDOW_S", "600"))   # watch expires 10 min post-resume
_dr_st: dict = {}     # sym -> {day, armed_k, level, r_k, tag, done, why}


def dip_rip_arm(sym, last_k, level):
    """Arm a resumption watch when a halt is suspected on a sheet name trading ABOVE its level."""
    try:
        day = datetime.now(EASTERN).strftime("%Y-%m-%d")
        st = _dr_st.get(sym)
        if st and st.get("day") == day and (st.get("done") or st.get("armed_k")):
            return                                     # one watch per name per day
        _dr_st[sym] = {"day": day, "armed_k": float(last_k or 0), "level": float(level),
                       "r_k": None, "tag": None, "done": False, "why": None}
        print(f"🪂 {sym} DIP-RIP ARMED — halt over sheet level ${level:.2f}; watching the resumption flush")
        _log_decision(sym, "diprip_armed", level=round(float(level), 4))
    except Exception:
        pass


def dip_rip_step(sym, new_bars, price_hint=0.0):
    """Advance the resumption watch over NEW completed 10s bars [(k,o,h,l,c,v),...].
    TAG: a post-resumption bar whose low enters [level, level*(1+DIPRIP_ZONE)] and closes >= level.
    CONFIRM (the entry): a later bar closing up (c>o) and >= level -> fire, stop just under the
    level. A decisive close below the level, or window expiry, retires the watch (logged)."""
    try:
        st = _dr_st.get(sym)
        day = datetime.now(EASTERN).strftime("%Y-%m-%d")
        if not st or st.get("day") != day or st.get("done") or not st.get("armed_k"):
            return None
        lvl = st["level"]
        for k, o, h, l, c, v in new_bars:
            if k <= st["armed_k"]:
                continue
            if st["r_k"] is None:
                st["r_k"] = k                          # first print after the gap = resumption
            if (k - st["r_k"]) - _halted_secs_since(sym, st["r_k"]) > DIPRIP_WINDOW_S:
                st["done"] = True; st["why"] = "window_expired"   # 8/5 halt-aware window
                _log_decision(sym, "diprip_expired", level=round(lvl, 4))
                return None
            if c < lvl * 0.99:                         # decisive break below the level: thesis dead
                st["done"] = True; st["why"] = "level_lost"
                _log_decision(sym, "diprip_level_lost", level=round(lvl, 4), close=round(c, 4))
                return None
            if st["tag"] is None:
                if l <= lvl * (1 + DIPRIP_ZONE) and c >= lvl:
                    st["tag"] = {"low": l, "k": k}
                    _log_decision(sym, "diprip_tag", level=round(lvl, 4), tag_low=round(l, 4))
            else:
                if c > o and c >= lvl:                 # CONFIRM — the entry bar
                    st["done"] = True; st["why"] = "fired"
                    return {"px": round(c, 4), "stop": round(lvl * (1 - 0.003), 4),
                            "level": lvl, "tag_low": st["tag"]["low"], "k": k}
        return None
    except Exception:
        return None


# Kev "topping tail / tail off the high" — a candle that spikes up then gets rejected,
# printing a long upper wick at the highs. He treats it as BOTH an entry-skip ("shouldn't
# have taken it, we had a tail off the high") AND his #1 exit ("topping tail off the high,
# I'm done with it"). Confirmed across all 6 daily recaps. See [[project_kev_lessons]].
TOPPING_TAIL_RATIO   = 0.55   # Upper wick ≥55% of the candle's range = rejection at the high
# ── RE-ENTRY (#2). Kev re-enters the SAME name on each fresh reclaim/pullback as long as it keeps
#    working (3–6 wins/name documented — 021/009/027), each reclaim an INDEPENDENT entry (a losing one
#    doesn't block the next — 027). He gives up STRUCTURALLY: topping tail off the high = "that's when
#    I'm done with it" (011/027). The corpus states NO numeric retry cap — so the consec-loss cap below
#    is a HOMEGROWN death-by-cuts rail for DRY_RUN learning, NOT a Kev number; calibrate from live data. ──
REENTRY_ENABLED         = True
REENTRY_GIVEUP_REASONS  = {"TOPPING TAIL"}   # Kev's exact "done with it" — front-side rejection at the high
REENTRY_MAX_CONSEC_LOSS = 3      # HOMEGROWN rail: after N CONSECUTIVE losing (re)entries on a name, leave it
                                 # alone. A win resets it (his 6-win trend days keep going). #022 "third try".
# ── 8/5 (Marcos: "losses that small should not count as three losses... These crown names are the
#    whales we are living to find and milk"): CROWNED names ban on consecutive-loss DOLLARS, not
#    transaction count — three $5 shakeouts != three $30 full stops. Era evidence 5-for-5 (all four
#    legitimate bans had bled $93-$124; YXT 8/5 was banned over $14.37 and then ran +144%). $75 =
#    2.5 full-risk units, Marcos-accepted risk level. 0 = kill switch back to count-based on crowns. ──
REENTRY_CROWN_LOSS_DOLLARS = float(os.environ.get("REENTRY_CROWN_LOSS_DOLLARS", "75"))
# ── Room-to-next-supply (Kev: enter only with ≥2:1 room to the next overhead supply) ──
PIVOT_WINDOW         = 3      # a swing high = bar whose high tops the 3 bars on each side
SUPPLY_CLUSTER_PCT   = 0.01   # merge supply levels within 1% into one zone
SUPPLY_MIN_DIST_PCT  = 0.003  # ignore "supply" within 0.3% of price (that's current price, not overhead)
MIN_ROOM_RR          = 2.0    # Kev's stated minimum reward:risk to the next supply
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

# Global — KEYED BY TICKER (multi-position): {ticker: {active, entry_price, shares, stop_loss, target}}
# so the SIGTERM handler can alert about every open position when killed mid-trade.
_open_trade: dict = {}


def _sigterm_handler(signum, frame):
    """
    Called when Railway (or any process manager) sends SIGTERM.
    If a trade is open at the time, sends an emergency alert before exiting
    so the user knows to log into Webull and manage the position manually.
    """
    # _open_trade is keyed by ticker (multi-position). Alert about EVERY open position.
    # Snapshot with list(...) (one GIL-atomic op) so a worker popping/inserting can't trip
    # "dict changed size during iteration" and silently swallow the kill alert.
    open_positions = [ot for ot in list(_open_trade.values()) if ot.get("active")]
    if open_positions:
        try:
            tickers = ", ".join(ot.get("ticker", "?") for ot in open_positions)
            subj    = f"🚨 BOT KILLED MID-TRADE — CHECK {tickers} POSITION(S) NOW"
            lines   = [f"Railway killed the trading bot while {len(open_positions)} position(s) were open!\n"]
            for ot in open_positions:
                lines.append(
                    f"Ticker {ot.get('ticker','?')}:  Entry ${ot.get('entry_price',0):.2f}  "
                    f"Shares {ot.get('shares',0)}  Stop ${ot.get('stop_loss',0):.2f}  "
                    f"Target ${ot.get('target',0):.2f}"
                )
            lines.append("\nStop orders were placed on Webull before the bot was killed.\n"
                         "Log into Webull immediately and verify they are still active.")
            resend.api_key = RESEND_API_KEY
            resend.Emails.send({
                "from":    "Marcos Trading Bot <onboarding@resend.dev>",
                "to":      [SUMMARY_EMAIL],
                "subject": subj,
                "text":    "\n".join(lines),
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
# ── REAL-TIME STREAMING (7/5) — the official Webull OpenAPI SNAPSHOT stream, now working with the fresh
#    2FA-verified token. Moves price reads OFF the 300/min REST cap onto the unlimited push stream (the
#    capacity fix for the ~2× ignition volume). SAFE-BY-DESIGN: a streamed price is used ONLY when it's
#    fresh (≤STREAM_FRESH_SECS) + sane; otherwise get_price transparently falls back to REST. Worst case =
#    today's polling behavior. Kill-switch: STREAMING_ENABLED=False → pure polling. ──
STREAMING_ENABLED = True    # 7/6: RE-ENABLED — streaming PROVEN live once the token session is refreshed
                            # (_refresh_webull_token in _connect). SNAPSHOT delivered 17 ticks/12s, parsed OK.
STREAM_FRESH_SECS = 20           # a streamed price is trusted only if it arrived within this many seconds; else REST

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


def _refresh_webull_token():
    """Refresh the Webull token PROGRAMMATICALLY (NO 2FA) via POST /openapi/auth/token/refresh. This
    RE-ACTIVATES the session so STREAMING works — INVALID_SESSION means a stale session nobody refreshed
    (the token VALUE can stay the same; refresh resets the session server-side). Proven live 7/6: after one
    refresh, SNAPSHOT streaming went from INVALID_SESSION → live ticks. Call before connecting the stream.
    Returns the refreshed token (persisted to token.txt), or None on failure (caller falls back to REST)."""
    try:
        cur = WEBULL_ACCESS_TOKEN
        if not cur:
            try: cur = (pathlib.Path(WEBULL_TOKEN_DIR) / "token.txt").read_text().splitlines()[0].strip()
            except Exception: cur = ""
        if not cur:
            return None
        # Sign WITHOUT x-access-token — the refresh endpoint is authed by the app-key signature + the body
        # token; including the STALE x-access-token = HTTP 401 (why _post/_webull_headers failed live 7/6).
        # This mirrors the dashboard /api/refresh_token signing, which returns 200 + re-activates streaming.
        host = "api.webull.com"; path = "/openapi/auth/token/refresh"
        body_str = json.dumps({"token": cur}, ensure_ascii=False, separators=(',', ':'))
        ts    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        nonce = str(uuid.uuid5(uuid.NAMESPACE_URL, socket.gethostname() + str(uuid.uuid1())))
        hdrs = {"Content-Type": "application/json", "x-app-key": WEBULL_APP_KEY, "x-timestamp": ts,
                "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1",
                "x-signature-nonce": nonce, "x-version": "v2"}
        sp = {"x-app-key": WEBULL_APP_KEY, "x-timestamp": ts, "x-signature-version": "1.0",
              "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "host": host}
        bs  = hashlib.md5(body_str.encode()).hexdigest().upper()
        s2s = quote(f"{path}&" + "&".join(f"{k}={v}" for k, v in sorted(sp.items())) + f"&{bs}", safe='')
        hdrs["x-signature"] = base64.b64encode(
            hmac.new((WEBULL_APP_SECRET + "&").encode(), s2s.encode(), hashlib.sha1).digest()).decode()
        resp = requests.post(f"https://{host}{path}", headers=hdrs, data=body_str, timeout=10)
        d = resp.json() if resp.content else {}
        newtok = ((d.get("data") or {}).get("token") if isinstance(d.get("data"), dict)
                  else (d.get("data") if isinstance(d.get("data"), str) else d.get("token"))) or cur
        if resp.status_code == 200:
            try:
                td = pathlib.Path(WEBULL_TOKEN_DIR); td.mkdir(parents=True, exist_ok=True)
                exp = int(time.time() * 1000) + 14 * 24 * 3600 * 1000
                (td / "token.txt").write_text(f"{newtok}\n{exp}\nNORMAL\n")
            except Exception:
                pass
            print(f"🔄 Webull token refreshed (session re-activated) — HTTP {resp.status_code}")
            return newtok
        print(f"⚠️  token refresh HTTP {resp.status_code}: {str(d)[:120]} — streaming falls back to REST")
        return None
    except Exception as e:
        print(f"⚠️  token refresh failed ({e}) — streaming will fall back to REST")
        return None


# ============================================================
# REAL-TIME PRICE STREAM (MQTT)
# ============================================================

# Shared price registry — updated by MQTT callbacks from a background thread
_price_registry: dict = {}
_price_lock = threading.Lock()


# ── B12 PHASE 1 (7/14, SHADOW-ONLY): build 10-second + 1-minute bars from the tick stream.
# WHY: the REST bar API is the bot's only chart today (429-throttleable, M1 floor); Kev's LGHL entry
# (hidden-entries short) lives on the 10-SECOND chart our data can't see. Phase 1 is OBSERVATION only — no consumer
# reads these for decisions. Divergence vs REST bars is logged; 10s bars for active names dump to the
# dashboard at EOD (the design dataset for the 10s-pullback entry). Everything fail-silent.
_shadow_lock = threading.Lock()
_shadow_keep: set = set()     # tickers whose 10s bars MUST persist at EOD: everything traded (Phase-3b
                              # stop anatomies) + extension-rejected verticals (Phase-3 specimens)
_shadow_bars = {10: {}, 60: {}}          # span → ticker → {bucket_epoch: {o,h,l,c,v0,v1}}
def _shadow_ingest(sym, price, cumvol, ts):
    try:
        for span in (10, 60):
            k = int(ts) // span * span
            with _shadow_lock:
                d = _shadow_bars[span].setdefault(sym, {})
                b = d.get(k)
                if b is None:
                    d[k] = {"o": price, "h": price, "l": price, "c": price,
                            "v0": cumvol, "v1": cumvol}
                else:
                    if price > b["h"]: b["h"] = price
                    if price < b["l"]: b["l"] = price
                    b["c"] = price
                    if cumvol is not None: b["v1"] = cumvol
    except Exception:
        pass

# ── #97 ALPACA MIGRATION (7/23, Fable review §8 of ALPACA_MIGRATION_PLAN.md) ─────────────
# Per-line source switches, ALL defaulting to today's behavior (webull) — the deploy flips
# them one at a time via Railway env, and any single line reverts without touching the rest.
# A2 (Fable): the STOP/monitor price path is deliberately NOT switchable — stops never read
# a 90s-stale trades-only feed; get_price/_get_price_rest stay Webull until the Alpaca
# quote-headroom check runs.
CURL_SOURCE     = os.environ.get("CURL_SOURCE", "webull")       # T2: curl-lane 10s feed
BARS_SOURCE     = os.environ.get("BARS_SOURCE", "webull")       # T3: 1-min intraday bars
DAILY_SOURCE    = os.environ.get("DAILY_SOURCE", "webull")      # T6: daily levels / prior close
ALP_CAPTURE_URL = os.environ.get("ALP_CAPTURE_URL", "").rstrip("/")   # A1 hot endpoint (unset → dashboard fallback)
ALP_HOT_SECRET  = os.environ.get("ALP_HOT_SECRET", os.environ.get("DASHBOARD_SECRET", "marcos2026"))
_ALP_KEY        = os.environ.get("ALPACA_KEY", "")
_ALP_SECRET     = os.environ.get("ALPACA_SECRET", "")
_ALP_FEED       = os.environ.get("ALPACA_FEED", "sip")

def _alpaca_rest_get(url, params, timeout=8):
    """Alpaca REST with rate-limit evidence (Feed Engineer condition: headroom is UNVERIFIED —
    count 429s so live measures it instead of anyone asserting it). Returns parsed JSON or None."""
    try:
        r = requests.get(url, params=params, timeout=timeout,
                         headers={"APCA-API-KEY-ID": _ALP_KEY, "APCA-API-SECRET-KEY": _ALP_SECRET})
        if r.status_code == 429:
            _bump("alp_429")
            return None
        if r.status_code != 200:
            _bump("alp_rest_err")
            return None
        return r.json()
    except Exception:
        _bump("alp_rest_err")
        return None

def _alp10_bars(t, n=90):
    """A1 choke-point fetch for Alpaca 10s bars (Integrator: consumers NEVER know the source).
    Priority: capture hot endpoint (fresh to the last closed bucket) → dashboard ~ALP10S
    (0–90s persist staleness — today's behavior, and the rig-exercised fallback).
    Returns (dict in _shadow_bars shape {bucket:{o,h,l,c,v0,v1}}, source_str)."""
    # hot path
    if ALP_CAPTURE_URL:
        try:
            r = requests.get(ALP_CAPTURE_URL + "/hot", params={"sym": t, "n": n},
                             headers={"X-Hot-Secret": ALP_HOT_SECRET}, timeout=2.5)
            if r.status_code == 200:
                d = {}
                for k, o, h, l, c, v in (r.json().get("bars") or []):
                    # v0=0/v1=v → consumers' (v1-v0) yields the true per-bar volume
                    d[int(k)] = {"o": float(o), "h": float(h), "l": float(l), "c": float(c),
                                 "v0": 0, "v1": float(v)}
                return d, "alp-hot"
            _bump("alp_hot_err")
        except Exception:
            _bump("alp_hot_err")
    # dashboard fallback (archive read — stale up to persist cadence, but never blind)
    try:
        url = os.environ.get("SCREENER_URL", "").rstrip("/")
        if url:
            r = requests.get(f"{url}/api/bars", params={"ticker": f"{t}~ALP10S",
                             "date": datetime.now(EASTERN).strftime("%Y-%m-%d")}, timeout=5)
            if r.status_code == 200:
                d = {}
                for b in (r.json().get("bars") or [])[-n:]:
                    try:
                        ts = datetime.strptime(str(b["time"])[:19], "%Y-%m-%dT%H:%M:%S")
                        k = int(ts.replace(tzinfo=timezone.utc).timestamp())
                        d[k] = {"o": float(b["open"]), "h": float(b["high"]), "l": float(b["low"]),
                                "c": float(b["close"]), "v0": 0, "v1": float(b["volume"])}
                    except Exception:
                        continue
                return d, "alp-dash"
    except Exception:
        pass
    return {}, "alp-none"

_curl_canary_t = {}   # ticker -> last canary log ts (throttle)

# 8/6 DETECTOR REHYDRATE (Marcos: "why can't we rehydrate the 10s lanes?" — the ENSC 9:40
# blindness): a name's FIRST detector pass after boot fetches a DEEP backfill so state
# machines (hidden 90-bar anchor, ignition bases, reclaim sequences) wake up already mature.
# Subsequent passes use the cheap 15-min default as before. Kill: REHYDRATE_BARS=90.
REHYDRATE_BARS = int(os.environ.get("REHYDRATE_BARS", "240"))

_bf_done: set = set()   # 8/10: one backfill per name per process

def _archive10_backfill(t, n=240):
    """8/10 FULL-WARM (Marcos: rehydration is mandatory): the hot feed only knows bars since
    SUBSCRIPTION — a name adopted mid-session has its real history in the dashboard archive.
    The archive lags ~90s (why it must never drive triggers) but history IS the past — for
    warm-up it is exactly right. Returns {sec: {o,h,l,c}} of today's ~ALP10S bars. Fail-soft {}."""
    try:
        import urllib.request as _ur
        d = json.load(_ur.urlopen(f"{SCREENER_URL}/api/bars?date="
                                  f"{datetime.now(EASTERN).strftime('%Y-%m-%d')}&ticker={t}~ALP10S",
                                  timeout=6))
        out = {}
        for b in (d.get("bars") or [])[-n:]:
            try:
                # archive stamps are ET wall-clock strings; hot-feed keys are EPOCH seconds.
                # Convert via an aware datetime so the two key-spaces actually merge.
                _dt = datetime.strptime(str(b.get("time"))[:19], "%Y-%m-%dT%H:%M:%S")
                _epoch = int(_dt.replace(tzinfo=timezone.utc).timestamp())   # auditor F1: archive stamps are UTC (alpaca_capture writes fromtimestamp(tz=utc)) — ET here shifted every bar 4h into the future
                out[_epoch] = {"o": float(b.get("open") or b["close"]), "h": float(b["high"]),
                               "l": float(b["low"]), "c": float(b["close"]),
                               "v0": 0, "v1": float(b.get("volume") or 0)}
            except Exception:
                continue
        return out
    except Exception:
        return {}

def _curl_feed(t, n=90):
    """T2 choke-point: the ONE place the curl lanes get their 10s bars. CURL_SOURCE=webull →
    bot's own _shadow_bars (today's behavior); =alpaca → _alp10_bars. Canary logs fed-bar
    AGE per name (Curl Mechanic condition: 'stale' vs 'absent' must be visible in the log —
    never again a week of guessing which starved the lanes). n: zone computation passes 720
    (2h — the hot bound) to reach the 9:00–9:29 window; step consumers use the 15-min default."""
    if CURL_SOURCE == "alpaca":
        d10, src = _alp10_bars(t, n)
    else:
        with _shadow_lock:
            d10 = dict(_shadow_bars[10].get(t) or {})
        src = "webull-shadow"
    # 8/10 FULL-WARM: a DEEP request answered thin = an adopted/rebooted name whose history
    # lives in the archive, not the hot feed. Backfill the past (lag-safe by definition);
    # hot bars win every overlapping key. One-shot per name per session via _bf_done.
    if n >= 180 and len(d10) < n // 2 and t not in _bf_done:
        _bf_done.add(t)
        _arch = _archive10_backfill(t, n=n)
        if _arch:
            _merged = dict(_arch); _merged.update(d10)
            print(f"🌊 {t}: warm-boot backfill {len(_arch)} archive bars under {len(d10)} hot bars")
            d10 = _merged
    now = time.time()
    if now - _curl_canary_t.get(t, 0) >= 120:
        _curl_canary_t[t] = now
        age = (now - max(d10)) if d10 else -1
        print(f"🧵 curl-feed {t}: src={src} bars={len(d10)} last_bar_age={age:.0f}s")
    # 7/28 HALT AWARENESS (docket #1): the tape is already in hand here — read it for the
    # zero-trade-gap signature. LOG-ONLY, one row per episode. `held` marks the severe case
    # (we are IN the name while it goes quiet) — the DFNS 7/27 situation.
    try:
        _susp, _gap, _lastk = _halt_suspect(t, d10)
        try:
            _lh_c = d10[max(d10)]["c"] if d10 else 0
            _leader_high_probe(t, float(_lh_c or 0))          # 8/5 leader ammo: fresh-high tracking
            # 8/5 halt-aware clocks: note completed >120s inter-bar gaps as halt credit
            _ks = sorted(d10.keys())[-8:]
            for _i in range(1, len(_ks)):
                if _ks[_i] - _ks[_i-1] > 120:
                    _seen = _halt_credit.get(t, [])
                    if not any(abs(end - _ks[_i]) < 1 for end, _ in _seen):
                        _halt_credit_note(t, _ks[_i-1], _ks[_i])
        except Exception:
            pass
        if _susp:
            _leader_violence(t, "halt")                        # 8/5 leader ammo: halt = violence proven
            _log_halt_suspect(t, _gap, _lastk, held=(t in _halt_held_mirror))
            # DIP-RIP arm (7/30): a halt on a SHEET name trading over its marked level arms the
            # resumption watch. Sheet-only + above-level = the false-positive guard (thin-tape
            # halt suspects on quiet names never arm — 325 suspects fired 7/29, ~5 were real).
            if DIP_RIP:
                try:
                    _lv_dr = (_fetch_kev_levels() or {}).get(t) or {}
                    _lvl_dr = float(_lv_dr.get("break") or 0)
                    _lc_dr = d10[max(d10)]["c"] if d10 else 0
                    if _lvl_dr > 0 and _lc_dr and float(_lc_dr) > _lvl_dr:
                        dip_rip_arm(t, _lastk, _lvl_dr)
                except Exception:
                    pass
    except Exception:
        pass
    return d10, src

def _et_session_of_utc(ts_utc: str):
    """Which US-equity session a UTC bar stamp ("2026-07-23T13:30:00") falls in, in EASTERN local
    time: PRE 04:00–09:30 · RTH 09:30–16:00 · ATH 16:00–20:00 · None outside. Converts through the
    tz database instead of the old hardcoded "13:30<=hm<20:00" UTC window, which is EDT-only and
    silently shifts an hour at the November DST change (7/27 fix queue item 2)."""
    try:
        et = datetime.strptime(ts_utc[:19], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc).astimezone(EASTERN)
    except Exception:
        return None
    hm = et.strftime("%H:%M")
    if "04:00" <= hm < "09:30":
        return "PRE"
    if "09:30" <= hm < "16:00":
        return "RTH"
    if "16:00" <= hm < "20:00":
        return "ATH"
    return None

EXIT_PX_TAPE_TOL = float(os.environ.get("EXIT_PX_TAPE_TOL", "5")) / 100.0   # 0 = guard off

def _verify_exit_px(px, tape_lo, tape_hi, tol=EXIT_PX_TAPE_TOL):
    """OFF-TAPE EXIT GUARD (7/27). Returns (booked_px, raw_px, ok, why).

    7/27 forensics: all 5 premarket BLIND-STOP exits booked prices BELOW the day's low on BOTH
    independent 10s feeds — BIYA 1.93 vs low 2.42 · LGHL 0.91 vs 0.95 · VEEE 12.97 vs 13.70 ·
    MTNB 0.24 vs 0.311 · JZXN 1.19 vs 1.22 — totalling exactly −$624.50, i.e. the whole incident
    was booked at prices that never traded. All 17 RTH exits that day were on-tape.

    Same defect class the ENTRY path already solved (`stale_price_fix`, :5324/:5431 — a stream
    quote 2%+ off the fire bar is discarded in favour of the bar). This is that idea at the exit.

    Policy: a print outside the tape this monitor has actually SEEN, by more than `tol`, cannot be
    verified — so book the nearest price we can PROVE traded and keep the raw print for the record.
    Never silently: the caller logs it and stamps `exit_px_unverified` + `exit_px_raw` on the trade.
    Deliberately does NOT veto the exit itself — a blind, alive position must still be closed (the
    BOXL freeze). It vetoes booking FICTION, not the decision to get out."""
    if not tol or not px or px <= 0:
        return px, px, True, None
    if not tape_lo or tape_lo <= 0:
        # FABLE F1 (7/27 review): NO tape seen at all = the TRUE blind scenario — the monitor's bars
        # came back empty every cycle (exactly the 7/27 incident conditions; the seen-tape check
        # above only helps a PARTIAL feed hole). We hold no proven price, so inventing one would
        # fabricate in the other direction: book the RAW print but REFUSE the verified label. The
        # analysis layer quarantines on the flag, as it should have been able to do on 7/27.
        return px, px, False, "no_tape_seen"
    if px < tape_lo * (1 - tol):
        return round(tape_lo, 4), px, False, "below_tape"
    if tape_hi and tape_hi > 0 and px > tape_hi * (1 + tol):
        return round(tape_hi, 4), px, False, "above_tape"
    return px, px, True, None


def _live_sessions(is_premkt=None):
    """Session list for a LIVE bar fetch (monitor/scan). Before 09:30 ET — or for a position stamped
    PRE — the RTH-only default returns [] (7/27 blackout: every premarket monitor went blind and the
    5 PRE trades blind-stopped for −$624.50). Returns None (= RTH-only, unchanged behavior) once the
    bell has rung on an RTH position, so nothing about the RTH path moves."""
    if is_premkt is None:
        is_premkt = datetime.now(EASTERN).strftime("%H:%M") < "09:30"
    return ["PRE", "RTH"] if is_premkt else None

def _alpaca_intraday_bars(ticker, count=30, sessions=None):
    """T3: Alpaca REST 1-min bars in the EXACT Webull shape get_intraday_bars returns
    (chronological dicts w/ UTC 'time' strings — the :1942 sampler contract). sessions=None →
    RTH-only filter (Webull default semantics); pass e.g. ["RTH","PRE"] to include extended.
    Full-day fetch then tail-slice, so intraday adds get complete history (Fable A3 for 1-min)."""
    # 7/27 OPEN-BLINDNESS FIX (proven on 7/23-24 rows: first legacy-lane row 10:37/10:56 — the
    # today-only fetch starved the 3-min EMA warmup ~66 min; Webull's multi-day semantics are the
    # contract this shim was supposed to mirror). 7 calendar days ≈ 5 trading days ≈ 4,800 1-min
    # bars incl. extended — single page (limit 10000), no pagination. RTH filter below unchanged.
    day0 = (datetime.now(EASTERN) - timedelta(days=7)).replace(hour=4, minute=0, second=0, microsecond=0)
    j = _alpaca_rest_get(f"https://data.alpaca.markets/v2/stocks/{ticker}/bars",
                         {"timeframe": "1Min", "start": day0.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "limit": 10000, "feed": "sip" if _ALP_FEED == "sip" else "iex",
                          "adjustment": "raw"})
    if not j:
        return []
    out = []
    for b in j.get("bars") or []:
        try:
            ts = str(b["t"])[:19]                  # "2026-07-23T13:30:00" UTC
            _sess = _et_session_of_utc(ts)         # DST-correct, via the tz database
            if sessions is None:                   # RTH-only (Webull default semantics)
                if _sess != "RTH":
                    continue
            elif {str(s).upper() for s in sessions} >= {"PRE", "RTH", "ATH"}:
                pass                               # "the whole extended day" — archive callers, unfiltered
            elif _sess not in {str(s).upper() for s in sessions}:
                continue                           # honor the requested session set (PRE/RTH/ATH)
            out.append({"time": ts + ".000+0000", "open": str(b["o"]), "high": str(b["h"]),
                        "low": str(b["l"]), "close": str(b["c"]), "volume": str(b["v"])})
        except Exception:
            continue
    return out[-count:] if count else out

def _alpaca_daily_items(ticker):
    """T6: Alpaca REST daily bars → the Webull items shape get_daily_levels parses
    ({'high','close','time'}). None → caller falls through to Webull (per-line degrade)."""
    # 7/28 P0-2 (Marcos's 8357% DFNS day-gain): 400 calendar days ≈ 276 TRADING days, and Alpaca
    # returns OLDEST-FIRST with `limit` capping the page — limit 250 cut the NEWEST ~26 bars for
    # any name with a long history, so prior_day_close was ~a month stale (LVWR base 1.06 = its
    # mid-June close → day_gain +146% on a +7% morning; every day-gain floor/exemption decision on
    # long-history runners was computed against ancient bases). limit 10000 = the whole window in
    # one page. get_daily_levels adds the staleness guard for any future vendor gap.
    j = _alpaca_rest_get(f"https://data.alpaca.markets/v2/stocks/{ticker}/bars",
                         {"timeframe": "1Day", "limit": 10000,
                          "start": (datetime.now(EASTERN) - timedelta(days=400)).strftime("%Y-%m-%dT00:00:00Z"),
                          "feed": "sip" if _ALP_FEED == "sip" else "iex", "adjustment": "raw"})
    if not j or not j.get("bars"):
        return None
    return [{"high": b.get("h"), "close": b.get("c"), "time": str(b.get("t"))[:10]}
            for b in j["bars"]]

def _shadow_flush_payload(min_buckets=50):
    """Build the SIGTERM bulk-flush payload from the in-memory 10s store (pure; rig-tested).
    Lower bucket floor than EOD (50 vs 200): a mid-day flush should keep almost everything —
    filtering is for analysis time, not collection time."""
    with _shadow_lock:
        snap = {t: sorted(bk.items()) for t, bk in _shadow_bars[10].items() if len(bk) >= min_buckets}
    series = {}
    for t, items in snap.items():
        series[f"{t}~10s"] = [
            {"time": datetime.fromtimestamp(k, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
             "open": str(b["o"]), "high": str(b["h"]), "low": str(b["l"]), "close": str(b["c"]),
             "volume": str(max(0, (b["v1"] or 0) - (b["v0"] or 0)))}
            for k, b in items]
    return {"date": datetime.now(EASTERN).strftime("%Y-%m-%d"), "series": series}


def _shadow_flush_all(reason="sigterm"):
    """7/15: deploys/restarts must never vaporize the day's 10s collection (Marcos: 'this nonsense of
    losing data with redeploys is ridiculous'). ONE gzipped POST inside Railway's SIGTERM grace window
    (~1-3s for a full day of 30-50 names) to the dashboard's volume-backed /api/bars_bulk. The hourly
    keep-set crash-guard still covers hard kills where no signal arrives."""
    try:
        url = os.environ.get("SCREENER_URL", "").rstrip("/")
        if not url:
            return False
        payload = _shadow_flush_payload()
        if not payload["series"]:
            return False
        payload["reason"] = reason
        import gzip as _gz
        body = _gz.compress(json.dumps(payload).encode(), compresslevel=1)
        r = requests.post(f"{url}/api/bars_bulk", data=body, timeout=8,
                          headers={"X-Dashboard-Secret": DASHBOARD_SECRET,
                                   "Content-Encoding": "gzip",
                                   "Content-Type": "application/json"})
        print(f"🛟 SIGTERM flush: {len(payload['series'])} series → {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"🛟 SIGTERM flush failed: {e}")
        return False


_prev_sigterm = None
def _on_sigterm(signum, frame):
    _shadow_flush_all("sigterm")
    if callable(_prev_sigterm):
        _prev_sigterm(signum, frame)
    else:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGTERM)


def _shadow_dump_eod(keep_only=False):
    """Post 10s bars to the dashboard (namespaced ~10s; POST overwrites → idempotent). keep_only=True is
    the HOURLY incremental crash-guard for the guaranteed names (traded + extension-rejected) — a mid-day
    process death must never vaporize the day's 10s history (unrecoverable: REST floor is M1). Full dump
    (top-25 incl. activity fillers) runs at 16:02."""
    try:
        url = os.environ.get("SCREENER_URL", "").rstrip("/")
        if not url: return
        with _shadow_lock:
            _all = sorted(((t, len(bk)) for t, bk in _shadow_bars[10].items()), key=lambda x: -x[1])
        _kept = [(t, n) for t, n in _all if t in _shadow_keep]
        _rest = [(t, n) for t, n in _all if t not in _shadow_keep]
        # EOD saves EVERYTHING watched (≥200 buckets filters dead subscriptions only). Filtering is
        # reversible at analysis time, irreversible at collection time — the entry-design dataset needs
        # the FAILED setups on quiet names as much as the winners (collection-layer survivorship trap).
        counts = _kept if keep_only else (_kept + _rest)
        date = datetime.now(EASTERN).strftime("%Y-%m-%d")
        sent = 0
        for t, n in counts:
            if n < 200: continue                    # skip barely-streamed names
            with _shadow_lock:
                items = sorted(_shadow_bars[10][t].items())
            bars = [{"time": datetime.fromtimestamp(k, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
                     "open": str(b["o"]), "high": str(b["h"]), "low": str(b["l"]), "close": str(b["c"]),
                     "volume": str(max(0, (b["v1"] or 0) - (b["v0"] or 0)))}
                    for k, b in items]
            try:
                r = requests.post(f"{url}/api/bars", json={"date": date, "ticker": f"{t}~10s", "bars": bars},
                                  headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=25)
                if r.status_code == 200: sent += 1
            except Exception:
                pass
        print(f"🔬 B12 shadow: dumped 10s bars for {sent} name(s){' (hourly crash-guard)' if keep_only else ''}")
    except Exception as e:
        print(f"⚠️  B12 shadow dump error (non-fatal): {e}")

class WebullStream:
    """
    Real-time price feed via the official Webull OpenAPI SNAPSHOT stream (7/5 — working with the fresh
    2FA-verified token). Prices are PUSHED to _price_registry; get_price reads the registry when the value
    is FRESH + sane, else falls back to a REST quote. Any connect/subscribe failure → connected=False →
    pure REST polling. Streaming can only reduce API load; it never feeds a stale/bad price (fallback).
    """

    def __init__(self, tickers: list):
        self.tickers    = tickers if isinstance(tickers, list) else [tickers]
        self.client     = None
        self.connected  = False
        self.subscribed = set()
        self._attempted = set()      # symbols we've tried to subscribe (avoids a retry storm on a failing sub)
        self._last_tick_ts = 0.0     # wall-clock of the last VALID tick — gates the fast loop cadence
        self._sub_lock  = threading.Lock()
        self._last_reconnect = 0.0   # #86 ghost-session rebuild rate-limit (one attempt / 300s)
        self._connect()

    def _connect(self):
        if not STREAMING_ENABLED:
            self.connected = False
            print(f"📊 Streaming off (kill-switch) — {POLL_LOOP_SLEEP}s REST polling")
            return
        try:
            from webull.core.utils.common import get_uuid
            _pre_populate_webull_token()
            _tok = _refresh_webull_token() or WEBULL_ACCESS_TOKEN   # RE-ACTIVATE the session (fixes INVALID_SESSION)
            if not _tok:
                try:
                    _tok = (pathlib.Path(WEBULL_TOKEN_DIR) / "token.txt").read_text().splitlines()[0].strip()
                except Exception:
                    _tok = ""
            if not (WebullStreamingClient and _tok):
                raise RuntimeError("streaming client or token unavailable")
            client = WebullStreamingClient(WEBULL_APP_KEY, WEBULL_APP_SECRET, "us", get_uuid())
            client._api_client.set_token_dir(WEBULL_TOKEN_DIR)   # connect-time init verifies the FRESH token
            client._api_client.set_token(_tok)
            client.on_quotes_message = self._on_msg
            client.on_quotes_subscribe = lambda *a, **k: None    # SDK REQUIRES this be set (7/6 thread crash) — no-op ok
            client.connect_and_loop_async(timeout=1, thread_daemon=True)
            time.sleep(3)                                        # let the MQTT connect settle
            self.client = client
            self._subscribe(self.tickers)
            self.connected = True
            print(f"📡 Real-time STREAMING connected (SNAPSHOT) — {len(self.subscribed)} tickers subscribed")
        except Exception as e:
            self.connected = False
            self.client = None
            print(f"⚠️  Streaming connect failed ({e}) — falling back to {POLL_LOOP_SLEEP}s REST polling")

    def _subscribe(self, tickers):
        """Subscribe SNAPSHOT for any not-yet-subscribed tickers (idempotent). Errors are non-fatal (REST covers)."""
        if not self.client:
            return
        new = [t.upper() for t in tickers if t and t.upper() not in self._attempted]
        if not new:
            return
        with self._sub_lock:
            self._attempted.update(new)                          # mark attempted BEFORE the call → tried once, no storm
        # 7/26 (discovery review F2): CHUNKED subscribe with per-symbol isolation — the recorder's
        # proven 7/17-FGMC fix, finally propagated to the bot (the parallel-logic-registry class:
        # one bad hand-typed Kev symbol used to zero the ENTIRE batch, permanently). One rotten
        # name now costs exactly one name.
        try:
            for _i in range(0, len(new), 20):
                _chunk = new[_i:_i + 20]
                try:
                    self.client.subscribe(_chunk, "US_STOCK", ["SNAPSHOT"])
                    with self._sub_lock:
                        self.subscribed.update(_chunk)
                except Exception as _ce:
                    # ORDER MATTERS: the 7/17 FGMC error string was "417 INVALID_SYMBOL" — symbol-class
                    # must be recognized BEFORE the "417" session check or the bad-symbol path would
                    # trigger endless session rebuilds on the same poisoned book (the old bug, renamed).
                    if "INVALID_SYMBOL" not in str(_ce) and ("INVALID_SESSION" in str(_ce) or "417" in str(_ce)):
                        raise                                    # true session-class → outer handler rebuilds
                    print(f"⚠️  subscribe chunk error ({_ce}) — retrying {len(_chunk)} names individually")
                    for _s in _chunk:
                        try:
                            self.client.subscribe([_s], "US_STOCK", ["SNAPSHOT"])
                            with self._sub_lock:
                                self.subscribed.add(_s)
                        except Exception as _se:
                            if "INVALID_SYMBOL" not in str(_se) and ("INVALID_SESSION" in str(_se) or "417" in str(_se)):
                                raise
                            print(f"   ⛔ skip bad symbol {_s}: {_se}")
        except Exception as e:
            print(f"⚠️  Stream subscribe error {new}: {e}")
            # #86 (7/22): the server can drop our session MID-DAY (live ~12:27 — every new subscribe
            # 417/INVALID_SESSION after) and the attempted-set made that permanent for those names.
            # Same ghost-session class the recorder fixed with teardown+rebuild. Un-attempt the names
            # so they retry once the session is rebuilt, and rebuild in the background (never blocks
            # the trading loop; get_price falls back to REST meanwhile).
            if "INVALID_SESSION" in str(e) or "417" in str(e):
                with self._sub_lock:
                    self._attempted.difference_update(new)
                threading.Thread(target=self._reconnect,
                                 args=(f"INVALID_SESSION on {new[:3]}",), daemon=True).start()

    def _reconnect(self, reason=""):
        """#86 ghost-session rebuild: full teardown (the recorder's missing-teardown lesson) → token
        refresh → fresh client → re-subscribe the whole book. Rate-limited to one attempt / 300s so a
        hard Webull outage degrades to plain REST polling instead of a reconnect storm."""
        with self._sub_lock:
            now = time.time()
            if now - self._last_reconnect < 300:
                return False
            self._last_reconnect = now
        print(f"🔄 Stream session rebuild ({reason}) — teardown + token refresh + resubscribe")
        try:
            self.connected = False                    # get_price → REST while we rebuild
            if self.client:
                try:
                    self.client.disconnect(); self.client.loop_stop()
                except Exception:
                    pass
            with self._sub_lock:
                book = sorted(self.subscribed | {t.upper() for t in self.tickers if t})
                self.subscribed = set()
                self._attempted = set()
            self.tickers = book
            self.client = None
            self._connect()
            return self.connected
        except Exception as e:
            print(f"⚠️  Stream rebuild failed ({e}) — REST covers until the next trigger")
            return False

    def _on_msg(self, _client, topic, payload):
        """SNAPSHOT push → update the price registry with the last-trade price (+ ext/overnight if RTH is None)."""
        try:
            basic = getattr(payload, "basic", None)
            sym = getattr(basic, "symbol", None)
            px = getattr(payload, "price", None) or getattr(payload, "ext_price", None) or getattr(payload, "ovn_price", None)
            if sym and px:
                p = float(px)
                if 0 < p < 1e6:                                 # basic sanity band
                    now = time.time()
                    self._last_tick_ts = now                     # proof ticks are flowing → allows fast loop cadence
                    with _price_lock:
                        _price_registry[str(sym).upper()] = {"p": p, "t": now}
                    # 7/21 FIX (#67): extended-session snapshots carry cumulative volume in
                    # NON-`volume` fields (recorder discovered 7/16 — see recorder._on_msg). This
                    # RTH-era callback only read `.volume`, so the bot's 10s shadow bars were
                    # volume-less → the reclaim/zone-flip seek gates (v>=2*avgv) NEVER tripped →
                    # 0 fires all day. Mirror the recorder's proven 6-field extraction exactly.
                    _cv = None
                    for _obj in (payload, basic):
                        if _obj is None:
                            continue
                        for _f in ("volume", "ext_volume", "extVolume", "total_volume",
                                   "totalVolume", "accumulate_volume", "ovn_volume"):
                            _v = getattr(_obj, _f, None)
                            if _v not in (None, 0, "0", ""):
                                try:
                                    _cv = float(_v); break
                                except Exception:
                                    pass
                        if _cv is not None:
                            break
                    _shadow_ingest(str(sym).upper(), p, _cv, now)   # B12 shadow — cannot raise
        except Exception:
            pass                                                # a bad message never breaks the feed

    def get_price(self, ticker: str) -> float:
        """Fresh streamed price if we have one, else a REST quote. Never returns a stale streamed value."""
        t = ticker.upper()
        if self.connected:
            self._subscribe([t])                                # lazily subscribe names added mid-session
            with _price_lock:
                rec = _price_registry.get(t)
            if isinstance(rec, dict) and rec["p"] > 0 and (time.time() - rec["t"]) <= STREAM_FRESH_SECS:
                return rec["p"]
        return _get_price_rest(ticker)                          # not connected / no fresh tick → REST

    def loop_sleep(self) -> float:
        # Fast 0.5s cadence ONLY when ticks are actually arriving; if the stream is connected but silent
        # (wrong entitlement / off-hours / parse mismatch) get_price falls back to REST, so use the slower
        # cadence — this guarantees streaming can never poll REST harder than plain 3s polling would.
        if self.connected and (time.time() - self._last_tick_ts) <= STREAM_FRESH_SECS:
            return MQTT_LOOP_SLEEP
        return POLL_LOOP_SLEEP

    def stop(self):
        if self.client:
            try:
                self.client.disconnect(); self.client.loop_stop()
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
            _pf_fs = float(info.get("floatShares") or 0); _pf_so = float(info.get("sharesOutstanding") or 0)
            if _pf_fs and _pf_so and _pf_fs > _pf_so * 1.05:
                _pf_fs = _pf_so   # 8/10 STKH: stale pre-split float capped at outstanding (mini-audit 1b)
            float_sh  = _pf_fs or _pf_so or "N/A"
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


# ── RE-ENGAGEMENT (NEW-A) — instrumented DRY_RUN experiment ────────────────────────────────────────────────
# Validated 7/8: ~2 addressable dropped-then-ran second legs/day; second-leg replay showed a re-engaged bot would
# capture 6/10 for +5.8R/5d (gates still filter the weak ones). Mechanism: a faded-then-reset name (e.g. TVRD +38%
# afternoon) re-ranks at a MODERATE score and gets crowded out of the fresh top-20, so the post-trade rebuild discards
# it and it's never re-hunted. Fix at the single source (scan_morning_gappers): re-admit up to N previously-surfaced
# ("engaged") names that are STILL valid gappers ranked just below the cut, so the normal entry gates get a second look.
# Re-SELECTION, not re-entry — the gates still decide. TARGETED at RESET names: re-admit a below-cut name only if its score
# is RECOVERING vs the prior scan (a reset/second-leg build), NOT merely "was seen" (that fills slots with dying names).
# Instrumented with the 🔁 log so tomorrow we can SEE it fire. v1 for DRY_RUN observation; tune thresholds from live data.
_REENGAGE_LAST: dict = {}     # symbol -> its score last scan (session-scoped; empty on restart) — to detect a RECOVERING score
REENGAGE_MAX = 5              # cap on re-admitted names per scan
REENGAGE_BAND = 40            # only consider ranks 21..BAND (still-live gappers crowded out, not deep-dead names)
REENGAGE_RECOVER = 1.15       # re-admit only if current score >= 1.15× last scan's (score climbing back = a reset leg)


BOARD_FUNNEL = os.environ.get("BOARD_FUNNEL", "1") == "1"
_board_last = {"t": 0, "out": None}   # auditor F14: last-good board cache   # 8/10 Marcos: THE BOARD IS THE UNIVERSE

def _board_candidates():
    """8/10 (Marcos: "Our scanner is already calibrated... The scanner has been created
    specifically to the standards set by Kev... the board is the universe"): candidate
    discovery = the dashboard scanner's board + Kev-sheet names, PERIOD. Returns the same
    shape scan_morning_gappers() produced so every consumer downstream is untouched.
    Fail-soft to the legacy internal scan ONLY on total board failure (never blank discovery)."""
    try:
        import urllib.request as _ur
        d = json.load(_ur.urlopen(f"{SCREENER_URL}/api/scan", timeout=8))   # auditor F14: don't stall the loop
        res = d.get("results") or []
        out = []
        for r in res:
            sym = (r.get("symbol") or "").upper()
            if not sym:
                continue
            # LEGACY SHAPE (the internal scan's contract — downstream reads symbol/change_pct/
            # float_shares/float_label/relative_volume/easy_to_borrow): emit exactly those keys.
            out.append({
                "symbol": sym,
                "change_pct": float(r.get("change_pct") or 0),
                "price": float(r.get("price") or 0),
                "float_shares": float(r.get("float_shares") or 0) or None,
                "float_label": r.get("float_label") or "",
                "relative_volume": r.get("relative_volume"),
                "easy_to_borrow": r.get("easy_to_borrow"),
                "market_cap": r.get("market_cap"),
                "kev": bool(r.get("kev")),
                "source": r.get("source") or "board",
            })
        if out:
            # auditor F6: the internal scan ALSO fed the reader's roster + the Move% ranking —
            # without these the reader goes Kev-only (non-Kev names get NO maps -> chart-gate
            # blocks them) and entry priority degrades to day_gain. The funnel feeds both.
            try:
                _post_read_list(out)
            except Exception as _prl:
                print(f"⚠️ funnel: read-list post failed ({_prl})")
            try:
                _move_pct.update({c["symbol"]: float(c.get("change_pct") or 0)
                                  for c in out if c.get("symbol")})
            except Exception:
                pass
            _board_last["t"] = time.time(); _board_last["out"] = out
            print(f"🧭 BOARD FUNNEL: {len(out)} candidates from the dashboard scanner "
                  f"(internal scan retired — Marcos 8/10)")
            return out
        print("⚠️ BOARD FUNNEL: board empty — falling back to legacy internal scan (loudly)")
        _log_decision("_BOARD", "board_funnel_fallback")
    except Exception as _bfe:
        if _board_last["out"] and time.time() - _board_last["t"] < 900:
            print(f"⚠️ BOARD FUNNEL: board unreachable ({_bfe}) — serving last-good board "
                  f"({int(time.time()-_board_last['t'])}s old)")
            return _board_last["out"]
        print(f"⚠️ BOARD FUNNEL: board unreachable ({_bfe}) — legacy internal scan (loudly)")
        try:
            _log_decision("_BOARD", "board_funnel_fallback")
        except Exception:
            pass
    return scan_morning_gappers()

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
    # rank_type for get_gainers_losers is a TIME PERIOD (DAY_1/PRE_MARKET/AFTER_MARKET/...), NOT a metric.
    # We were passing "CHANGE_RATIO" (a sort_by value) → API returns 200 with EMPTY data → the gainers
    # feed was silently dead, leaving the scan on the RVOL feed alone. DAY_1 = today's gainers (proven).
    rank_type  = "DAY_1" if market_open else "PRE_MARKET"
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
                if price < 0.50 or price > 20:   # Kev gospel: price < $20 (was $30)
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
                if price < 0.50 or price > 20:   # Kev gospel: price < $20 (was $30)
                    continue
                if rel_vol < 2.0:   # at least 2× 10-day average volume
                    continue
                if sym in gappers:
                    gappers[sym]["relative_volume"] = rel_vol
                else:
                    if chg >= 0:    # ANTICIPATORY (7/3, volume precedes price — Kev): a name with a 2× volume
                                    # surge while price is still FLAT is the ignition FORMING, before the gap
                                    # shows. Was chg≥3 = only AFTER it moved = reactive (36/36 winners seen
                                    # late). Now we watch the volume surge itself. [[feedback_reverse_engineer_winners]]
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
    # Small float (<20M, Kev gospel) + big gap + volume = the real momentum setup.
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
                    _fs = float(info.get("floatShares") or 0)
                    _so = float(info.get("sharesOutstanding") or 0)
                    # 8/10 STKH lesson: yfinance can serve PRE-reverse-split float beside
                    # post-split outstanding (3.86B float vs 592K outstanding). Float can never
                    # exceed shares outstanding — cap it, loudly.
                    if _fs and _so and _fs > _so * 1.05:
                        print(f"   ⚠️ {sym}: float {_fs/1e6:.1f}M > outstanding {_so/1e6:.2f}M — "
                              f"stale-split data, using outstanding (so-capped)")
                        _fs = _so
                    float_shares = _fs or _so or 0
                    time.sleep(0.2)   # light rate-limit avoidance
                except Exception:
                    pass

            g["float_shares"] = float_shares
            # Borrow status for the squeeze tilt: False = hard-to-borrow = high short interest (Kev's squeeze fuel).
            # None = unknown (no tilt). Webull already returned this in wb_fund — was being discarded.
            g["easy_to_borrow"] = wb_fund.get("easy_to_borrow")
            float_m = float_shares / 1_000_000 if float_shares else 0
            if not float_shares:
                g["float_label"] = "float N/A"
                float_checked.append(g)
            elif float_shares <= BOT_MAX_FLOAT:   # Marcos 7/24: 50M = the scanner's Kev-watch band (OMH 21.3M receipt; was 20M "Kev gospel" core) — #108 grades the 20-50M band live
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

    # Kev-weighted selection score (rank only — the room gate + setup detectors still decide entries):
    #   base   = gap% / float_m            → big gap on a small float          (Kev: the core gapper setup)
    #   × HTB  = short-squeeze fuel         → hard-to-borrow = heavy short int   (Kev, FCHL "97% short → squeeze")
    #   × RVOL = the move is real           → heavy relative volume confirms it  (Kev: unusual volume = genuine interest)
    def _gapper_score(g):
        f = g.get("float_shares") or 0
        float_m = f / 1_000_000 if f > 0 else 25   # assume 25M if unknown
        base = g["change_pct"] / max(float_m, 0.1)
        htb_mult = HTB_SQUEEZE_MULT if g.get("easy_to_borrow") is False else 1.0
        rvol = g.get("relative_volume") or 1.0
        rvol_mult = 1.0 + min(max(rvol - 1.0, 0.0), RVOL_BOOST_CAP) / 10.0
        g["select_score"] = round(base * htb_mult * rvol_mult, 2)
        return g["select_score"]

    scored  = sorted(float_checked, key=_gapper_score, reverse=True)
    results = scored[:20]   # 7/3: 15→20 (wider net — fewer missed movers)
    # RE-ENGAGEMENT (NEW-A): a faded-then-RESET mover re-ranks below the top-20 and gets discarded by the post-trade rebuild,
    # so its second leg is never re-hunted (TVRD 7/8 +44% unwatched). Re-admit up to N below-cut names (ranks 21..BAND) whose
    # score is RECOVERING vs the last scan (>= REENGAGE_RECOVER×) — that's a reset building, not a name still dying. Gates decide.
    _top = {r["symbol"] for r in results}
    _readmit = [r for r in scored[20:REENGAGE_BAND]
                if r["symbol"] not in _top
                and r["symbol"] in _REENGAGE_LAST
                and r.get("select_score", 0) >= _REENGAGE_LAST[r["symbol"]] * REENGAGE_RECOVER][:REENGAGE_MAX]
    if _readmit:
        print(f"   🔁 Re-engagement: re-admitting {len(_readmit)} reset name(s) crowded below top-20 (score recovering): "
              f"{', '.join(r['symbol'] for r in _readmit)}")
        results = results + _readmit
    for r in scored:      # remember every scored name's score so we can detect recovery next scan
        _REENGAGE_LAST[r["symbol"]] = r.get("select_score", 0)
    print(f"✅ Morning gapper scan — top {len(results)} by Kev-weighted score:")
    for r in results:
        tags = []
        if r.get("easy_to_borrow") is False:                 tags.append("HTB🔥")
        if (r.get("relative_volume") or 1.0) >= 2.0:          tags.append(f"{r['relative_volume']:.0f}×vol")
        print(f"   {r['select_score']:>7.1f}  {r['symbol']:<6} +{r['change_pct']:.0f}% | "
              f"{r.get('float_label','float N/A')}{'  ' + ' '.join(tags) if tags else ''}")
    # #99: hand the reader its Move%-ranked roster (top-20 by change_pct + Kev). Drawn from the FULL
    # Kev-filtered candidate set (float_checked), ranked by Move% — not the select_score order above.
    _post_read_list(float_checked)
    # CAPITAL-PRIORITY (7/26): refresh the Move% map from the SAME rows the scanner column shows —
    # every scanned candidate, not just the returned top slice (a below-cut name can still fire a lane).
    try:
        _move_pct.update({c["symbol"]: float(c.get("change_pct") or 0)
                          for c in (float_checked or []) if c.get("symbol")})
    except Exception:
        pass
    return results


def _post_watching_to_screener(tickers: list, status: str = "watching", quiet: bool = False):
    """Push the live watch list to screener_app so the dashboard shows what the bot is monitoring.
    quiet=True → one short log line (used by the intraday roster heartbeat, #101 — a 110-name
    list every couple of minutes would drown the log)."""
    screener_url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not screener_url:
        return
    try:
        requests.post(f"{screener_url}/api/watching",
                      json={"tickers": tickers, "status": status,
                            "started_at": datetime.now(EASTERN).isoformat()},
                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET},
                      timeout=5)
        if quiet:
            print(f"📡 Watch roster → dashboard: {len(tickers)} names")
        else:
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


# S&P 500 / Dow / Nasdaq via Webull ETF proxies (SPY/DIA/QQQ track the indices to ~1bp — the % change is what
# "how's the market" needs; no yfinance). Pushed to the dashboard market strip.
_MARKET_PROXIES = [("SPY", "S&P 500"), ("DIA", "Dow Jones"), ("QQQ", "Nasdaq")]

def _push_market_context():
    """Fetch the index proxies + push to the dashboard /api/market strip. Fully non-fatal (never blocks the loop)."""
    screener_url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not screener_url:
        return
    try:
        indices = []
        for sym, label in _MARKET_PROXIES:
            q = _get_webull_quote(sym) or {}
            chg = q.get("change_ratio")
            if chg is None:
                continue
            indices.append({"label": label, "chg": round(float(chg), 2)})
        if not indices:
            return
        requests.post(f"{screener_url}/api/market",
                      json={"indices": indices},
                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET},
                      timeout=5)
    except Exception as e:
        print(f"⚠️  Could not push market context (non-fatal): {e}")


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


def _clear_open_trade(ticker: str, trade_id=None):   # auditor F3: id-precise clears — a
    # ticker-wide clear with two same-name positions wipes the SIBLING's recovery row.
    """Remove the open position from durable storage once it has a recorded exit. Blocking
    (must complete before the run ends) but bounded.
    7/29 P1-F: VERIFIED clear — the old fire-and-forget version swallowed failures silently, which
    left a ghost STFS row (all-null fields) behind the 7/29 midday restart. Now: check the status
    code, re-read the store, retry once, and log LOUDLY if the row survives — a silent failure here
    means the next boot's orphan recovery acts on a corpse."""
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url:
        return
    for _attempt in (1, 2):
        try:
            r = requests.post(f"{url}/api/open_trade/clear", json={"ticker": ticker, "trade_id": trade_id},
                              headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=5)
            if r.status_code == 200:
                try:
                    _rows = (requests.get(f"{url}/api/open_trades", timeout=5)
                             .json().get("open_trades") or [])
                    still_tk  = [o.get("ticker") for o in _rows]
                    still_ids = [o.get("trade_id") for o in _rows if o.get("trade_id")]
                except Exception:
                    # auditor note 4 (8/12): a FAILED verify-read must NOT read as "verified
                    # gone" — poison sentinels force the retry/give-up path instead.
                    still_tk, still_ids = [ticker], [trade_id]
                # 8/12 W3 FIX (auditor: the old check compared a trade_id against a TICKER list —
                # vacuously true, so id-bearing clears never actually verified; that silence is
                # how 8/11's 8 ghosts accumulated unseen).
                if (trade_id and trade_id not in still_ids) or (not trade_id and ticker not in still_tk):
                    return                                     # verified gone
            print(f"🧹 {ticker}: open-trade clear attempt {_attempt} NOT verified "
                  f"(HTTP {r.status_code}) — {'retrying' if _attempt == 1 else 'GIVING UP'}")
        except Exception as e:
            print(f"🧹 {ticker}: open-trade clear attempt {_attempt} error {e} — "
                  f"{'retrying' if _attempt == 1 else 'GIVING UP'}")
    print(f"🚨 {ticker}: open-trade row may SURVIVE in the dashboard store — "
          f"next boot's orphan recovery will see it. Manual: POST /api/open_trade/clear")


def _load_open_trades_from_screener():
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
    return None   # auditor F5: outage must be DISTINGUISHABLE from "no positions" — None, never []


def _log_room_skip(ticker, price, entry_type, room):
    """Record an entry the ROOM gate rejected (no ≥2:1 room to next supply). Logged so we can AUDIT
    that the supply detection is reading live charts correctly (per feedback_kev_is_the_bible:
    verify our implementation, not Kev's rule)."""
    rec = {"ticker": ticker, "date": datetime.now(EASTERN).strftime("%Y-%m-%d"),
           "time": datetime.now(EASTERN).strftime("%I:%M:%S %p"), "entry_type": entry_type,
           "price": round(price, 4), "next_supply": room.get("next_supply"),
           "supply_src": room.get("supply_src"), "room_pct": room.get("room_pct"),
           "rr_to_supply": room.get("rr_to_supply")}
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url:
        return
    def _send():
        try:
            requests.post(f"{url}/api/room_skip", json=rec,
                          headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=4)
        except Exception:
            pass
    try:
        _aux_executor.submit(_send)
    except Exception:
        pass


# ── Per-candidate DECISION log (observability) — persist WHY we did/didn't trade each name, to the
# screener /data (survives; logs don't). Throttled: POST only when a ticker's status CHANGES or every
# DECISION_HEARTBEAT_SECS, so the timeline is reconstructable without flooding (the 6/26 blackout). ──
DECISION_HEARTBEAT_SECS = 120
_decision_last: dict = {}   # ticker -> (status, last_post_ts)

# ── Durable write path (so we NEVER lose a decision message — the 6/26 blackout was Railway dropping
# logs). Records are QUEUED, then a background flusher BATCHES them to the screener every few seconds
# and RETRIES failed batches (put back on the queue) so a screener blip can't drop them. The screener
# appends each batch to a per-day JSONL on its /data volume = the durable archive. ──
DECISION_FLUSH_SECS  = 5      # flush cadence
DECISION_BATCH_MAX   = 200    # records per POST
DECISION_QUEUE_MAX   = 8000   # bound the in-memory queue (hours of backlog headroom; only fills if screener is down)
_decision_queue: list = []
_decision_queue_lock = threading.Lock()
_decision_flusher_started = False

_side_memo = {}   # ticker -> (expires, side) — 8/8: one tape read per 20s per name
_SIDE_STAMPED = ("_reject", "_capped", "_skip")   # every refusal row carries its story position

def _log_decision(ticker, status, **fields):
    # Wrapped so observability can NEVER throw into the trading hot path (this is called for every
    # candidate every cycle). A logging bug must not be able to stop the bot from trading.
    try:
        # 8/8 (Marcos: "make sure the machinery is giving us the details we need"): REJECTS carry
        # the SIDE stamp too — refusal grading needs to know if we refused front-side strength or
        # back-side chop. Memoized 20s/name; fills+heartbeats already stamp at their sites.
        if "side" not in fields and (any(str(status).endswith(sfx) for sfx in _SIDE_STAMPED)
                                     or status in ("halt_arm", "halt_early_arm", "seam_shadow_fire")):
            _m = _side_memo.get(ticker)
            if _m and _m[0] > time.time():
                fields["side"] = _m[1]
            else:
                _sv = _side_state(ticker)
                _side_memo[ticker] = (time.time() + 20, _sv)
                fields["side"] = _sv
        prev = _decision_last.get(ticker)
        now = time.time()
        if prev and prev[0] == status and (now - prev[1]) < DECISION_HEARTBEAT_SECS:
            return   # same status, within heartbeat window — skip to bound volume
        _decision_last[ticker] = (status, now)
        if not os.environ.get("SCREENER_URL", "").rstrip("/"):
            return
        rec = {"ticker": ticker, "status": status,
               "date": datetime.now(EASTERN).strftime("%Y-%m-%d"),
               "time": datetime.now(EASTERN).strftime("%I:%M:%S %p")}
        rec.update({k: (round(v, 4) if isinstance(v, float) else v) for k, v in fields.items()})
        with _decision_queue_lock:
            _decision_queue.append(rec)
            if len(_decision_queue) > DECISION_QUEUE_MAX:   # drop OLDEST only on extreme overrun (screener long-down)
                del _decision_queue[:len(_decision_queue) - DECISION_QUEUE_MAX]
        _ensure_decision_flusher()
    except Exception:
        pass

def _ensure_decision_flusher():
    global _decision_flusher_started
    if _decision_flusher_started:
        return
    _decision_flusher_started = True
    threading.Thread(target=_decision_flush_loop, daemon=True).start()
    atexit.register(_flush_decisions_now)   # drain whatever's left when the cron session exits

def _post_decisions_batch(batch) -> bool:
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url or not batch:
        return True
    try:
        r = requests.post(f"{url}/api/decisions/batch", json={"records": batch},
                          headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=8)
        return r.status_code == 200
    except Exception:
        return False

def _flush_decisions_now():
    # Drain the queue in batches. If a batch POST FAILS, put it back at the FRONT (order preserved) and
    # stop this pass — the next cycle retries. Bounded passes so a huge backlog can't block forever.
    for _ in range(64):
        with _decision_queue_lock:
            if not _decision_queue:
                return
            batch = _decision_queue[:DECISION_BATCH_MAX]
            del _decision_queue[:len(batch)]
        if not _post_decisions_batch(batch):
            with _decision_queue_lock:
                _decision_queue[:0] = batch   # requeue at front for retry (records NOT lost)
            return

def _decision_flush_loop():
    while True:
        time.sleep(DECISION_FLUSH_SECS)
        try:
            _flush_decisions_now()
        except Exception:
            pass


# ── DATA WAREHOUSE: at END OF SESSION, archive the day's full 1-min bars for every watched ticker to
# the screener /data volume — a PERMANENT, growing dataset for future backtests + learning (bars age
# out of every API). Runs ONCE after trading is done; fully fail-safe so it can NEVER affect a trade. ──
def _archive_watchlist_bars(tickers):
    try:
        url = os.environ.get("SCREENER_URL", "").rstrip("/")
        tickers = list(dict.fromkeys(t for t in (tickers or []) if t))
        date = datetime.now(EASTERN).strftime("%Y-%m-%d")
        # Also archive KEV's flagged tickers for today — benchmark our selection vs his, even names our
        # bot never watched. Fail-safe: if the fetch fails, just archive our own list.
        try:
            if url:
                r = requests.get(f"{url}/api/kev_watchlist", params={"date": date}, timeout=10)
                if r.status_code == 200:
                    kev = [str(t).upper().strip() for t in (r.json().get("tickers") or []) if str(t).strip()]
                    if kev:
                        tickers = list(dict.fromkeys(tickers + kev))
                        print(f"🗄️  Including {len(kev)} of Kev's flagged tickers in today's archive.")
        except Exception:
            pass
        if not url or not tickers:
            return
        saved = 0
        for t in tickers:
            try:
                bars = get_intraday_bars(t, count=960, executor=_aux_executor,
                                         sessions=["RTH", "PRE", "ATH"])   # full extended day incl pre/after-market
                if not bars:
                    continue
                r = requests.post(f"{url}/api/bars", json={"date": date, "ticker": t, "bars": bars},
                                  headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=20)
                if r.status_code == 200:
                    saved += 1
            except Exception:
                pass
            time.sleep(0.3)
        print(f"🗄️  Data warehouse: archived bars for {saved}/{len(tickers)} watched tickers ({date}).")
    except Exception as e:
        print(f"⚠️  Bar archival failed (non-fatal): {e}")


# ── EOD MARKET-WIDE WINNER SWEEP ─────────────────────────────────────────────────────
# Closes the reverse-engineering BLIND SPOT (user 7/3): /api/bars only held names the bot WATCHED (~18/day),
# so we could only ever study winners we already caught. This archives the day's TOP MOVERS market-wide (the
# ones our top-15/float filter dropped or never saw), so the archive holds the COMPLETE winner set for the
# SEE/CATCH/RIDE analysis. Read-only Webull data (the same get_gainers_losers the scanner uses) + the existing
# bar-archive POST; throttled + back-off; a crash here can NEVER touch trading. [[feedback_reverse_engineer_winners]]
def winner_sweep():
    try:
        url = os.environ.get("SCREENER_URL", "").rstrip("/")
        if not url:
            return
        _, dc = _make_data_client()
        if not dc:
            print("⚠️  winner_sweep: no data client"); return
        date = datetime.now(EASTERN).strftime("%Y-%m-%d")
        movers = {}
        try:
            res = dc.screener.get_gainers_losers(rank_type="DAY_1", category="US_STOCK",
                                                 sort_by="CHANGE_RATIO", direction="DESC", page_size=100)
            if res.status_code == 200:
                raw = res.json()
                items = raw if isinstance(raw, list) else raw.get("data", raw.get("items", []))
                for it in items:
                    sym = it.get("symbol", ""); chg = float(it.get("change_ratio") or 0) * 100
                    price = float(it.get("price") or it.get("close") or 0)
                    if sym and 0.50 <= price <= 20 and chg >= 8:   # the day's small-cap movers, market-wide
                        movers[sym] = round(chg, 1)
            else:
                print(f"⚠️  winner_sweep gainers error: {res.status_code}")
        except Exception as e:
            print(f"⚠️  winner_sweep gainers exception: {e}")
        if not movers:
            print("🏁 winner_sweep: no movers found"); return
        saved = errs = 0
        failed = []                                      # 7/13: AGEN+SRXH archive posts died silently in a
                                                         # deploy-window collision — track + retry + REPORT
        for sym in list(movers)[:80]:                    # bound the batch
            try:
                bars = get_intraday_bars(sym, count=960, executor=_aux_executor,
                                         sessions=["RTH", "PRE", "ATH"])   # full extended day incl pre/after-market
                if bars:
                    r = requests.post(f"{url}/api/bars", json={"date": date, "ticker": sym, "bars": bars},
                                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=20)
                    if r.status_code == 200:
                        saved += 1
                    else:
                        failed.append(sym)
                else:
                    failed.append(sym)
            except Exception:
                errs += 1; failed.append(sym)
                if errs >= 5:                            # back off — never hammer the token
                    print("⚠️  winner_sweep: 5 fetch errors — backing off, stopping."); break
        if failed:                                       # one retry pass after a settle pause (dashboard may
            time.sleep(20)                               # have been mid-restart on the first attempt)
            still = []
            for sym in failed:
                try:
                    bars = get_intraday_bars(sym, count=960, executor=_aux_executor,
                                             sessions=["RTH", "PRE", "ATH"])
                    r = requests.post(f"{url}/api/bars", json={"date": date, "ticker": sym, "bars": bars},
                                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=20) if bars else None
                    if r is not None and r.status_code == 200:
                        saved += 1
                    else:
                        still.append(sym)
                except Exception:
                    still.append(sym)
            if still:
                print(f"🚨 winner_sweep: {len(still)} name(s) FAILED both passes — archive incomplete: {' '.join(still)}")
            time.sleep(0.5)                              # gentle, read-only, off-market
        print(f"🏁 winner_sweep {date}: archived {saved}/{len(movers)} market-wide movers (≥8%, <$20). "
              f"The reverse-engineering dataset now sees the winners we DIDN'T catch.")
    except Exception as e:
        print(f"⚠️  winner_sweep failed (non-fatal): {e}")


def _winner_sweep_loop():
    """Daemon: capture market-wide movers' bars SERVER-SIDE (runs on Railway regardless of any app being open).
    TWO passes per trading day: (1) ~16:10 ET = RTH snapshot for the 4:30pm scorecard; (2) ~20:05 ET = full
    pre+RTH+AFTER-HOURS capture once the 4-8pm session has closed (the 16:10 pass only catches ~10 min of AH).
    Replaces the fragile app-dependent 8:18pm Claude backfill task with a server-side pass. Isolated — cannot touch trading."""
    last_rth = last_ah = None
    _last_mkt = 0.0
    _last_shadow_cmp = 0.0
    _shadow_dumped = None
    _shadow_day = None
    while True:
        try:
            now = datetime.now(EASTERN)
            today = now.strftime("%Y-%m-%d")
            # 7/14: keep the dashboard market strip fresh all day from this always-on loop — the
            # startup-only push raced the co-deploying dashboard on 7/13 and the strip sat empty.
            if now.weekday() < 5 and 7 <= now.hour < 20 and time.time() - _last_mkt >= 900:
                _last_mkt = time.time()
                _push_market_context()
            # B12 shadow: reset the in-memory bar store at day change (bounded memory).
            # 7/15 (Marcos: "wouldn't we also lose the after hours bars?"): FLUSH BEFORE EVERY CLEAR —
            # the 16:02 dump can't cover bars collected after it (e.g. a post-deploy restart's AH
            # session, whose daily dump already fired before the process existed). Banking to the
            # dashboard before wiping means no bar can ever die in memory at a day boundary.
            if _shadow_day != today:
                if _shadow_day is not None:
                    try:
                        _shadow_flush_all("day-change")
                    except Exception:
                        pass
                _shadow_day = today
                with _shadow_lock:
                    _shadow_bars[10].clear(); _shadow_bars[60].clear()
                _shadow_keep.clear()
            # B12 shadow: hourly divergence sample during RTH (stream-bar vs REST-bar, top name by ticks)
            if now.weekday() < 5 and 10 <= now.hour < 16 and time.time() - _last_shadow_cmp >= 3600:
                _last_shadow_cmp = time.time()
                try:
                    _shadow_dump_eod(keep_only=True)   # crash-guard: persist traded/rejected names' 10s so far
                except Exception:
                    pass
                try:
                    with _shadow_lock:
                        _cand = sorted(((t, len(bk)) for t, bk in _shadow_bars[60].items()), key=lambda x: -x[1])[:1]
                    if _cand:
                        _t = _cand[0][0]
                        _rb = _fresh_session(get_intraday_bars(_t, count=4, executor=_aux_executor))   # B16
                        with _shadow_lock:
                            _sb = sorted(_shadow_bars[60].get(_t, {}).items())
                        if _rb and len(_rb) >= 2 and _sb:
                            _rc = float(_rb[-2].get("close") or 0)
                            _rk = None
                            try:
                                _rt = datetime.strptime(str(_rb[-2].get("time"))[:19], "%Y-%m-%dT%H:%M:%S")
                                _rk = int(_rt.replace(tzinfo=timezone.utc).timestamp())
                            except Exception:
                                pass
                            _match = dict(_sb).get(_rk) if _rk else None
                            if _match and _rc > 0:
                                _dv = (_match["c"] - _rc) / _rc * 100
                                print(f"🔬 B12 shadow vs REST [{_t}]: 1m close {_match['c']:.4g} vs {_rc:.4g} ({_dv:+.2f}%)")
                            else:
                                print(f"🔬 B12 shadow: no matching bucket for {_t} (rk={_rk}) — check bucket alignment")
                except Exception:
                    pass
            if now.weekday() < 5:
                if now.hour == 16 and now.minute >= 2 and last_rth != today:   # 16:02 (was :10) — RTH bars are final at 16:00; earlier sweep = earlier scorecard on days Marcos is watching
                    print("🏁 EOD winner sweep (RTH snapshot for the scorecard)...")
                    winner_sweep(); last_rth = today
                    if _shadow_dumped != today:
                        _shadow_dumped = today
                        _shadow_dump_eod()
                if now.hour == 20 and now.minute >= 5 and last_ah != today:
                    print("🌙 After-hours backfill sweep (full pre+RTH+ATH now that AH has closed)...")
                    winner_sweep(); last_ah = today
        except Exception as e:
            print(f"⚠️  winner_sweep loop error: {e}")
        time.sleep(120)


# ── STALE-TRADE WATCHDOG ─────────────────────────────────────────────────────────────
# Recovery is startup-only; a monitor that FREEZES while the process stays alive (IQST, 6/25)
# is invisible to it. This watchdog watches a LOCAL in-memory heartbeat each monitor writes
# every loop — independent of any network/persist — so a failing persist keeps the heartbeat
# fresh and CANNOT trip it; only a genuinely frozen loop does. Conservative thresholds.
WATCHDOG_CHECK_SECS   = 30
WATCHDOG_ALERT_SECS   = 90     # heartbeat stale this long → alert (a human can look)
WATCHDOG_RECOVER_SECS = 300    # stale this long → force-record + abort (generous; no false trips)
_active_monitors: dict = {}    # ticker -> {"heartbeat": ts, "ctx": {full record}, "alerted": bool}
_monitor_abort: set = set()    # tickers the watchdog force-closed; a thawing monitor checks + bails

# ── EXECUTION-HEALTH INSTRUMENTATION (7/5) — the looser ignition config fires ~2× the trades (many
#    concurrent in hour 1); the backtest assumes flawless execution the live bot may not deliver at that
#    volume. Count the two signals that show whether it CHOKED: Webull 429 rate-limits + peak concurrent
#    positions. Behavior-neutral (counters only). Emitted in the scan-loop status + logged each cycle. ──
_exec_health = {"api_429": 0, "api_err": 0, "timeouts": 0, "fail_open": 0, "peak_positions": 0, "cur_positions": 0}
_exec_health_lock = threading.Lock()
def _bump(key, n=1):
    with _exec_health_lock:
        _exec_health[key] = _exec_health.get(key, 0) + n
def _note_positions(cur):
    with _exec_health_lock:
        _exec_health["cur_positions"] = cur
        if cur > _exec_health["peak_positions"]:
            _exec_health["peak_positions"] = cur

def _post_resume_record(o: dict, result) -> None:
    """8/10 C2: the resumed monitor's exit reaches the books (today's XHLD original recorded
    NOTHING). Entry/partials/shares come from the SAVED state; exit price/reason from the
    monitor result. Posts through post_trade_record_reliably; trade_id dedups re-posts."""
    try:
        tk = (o.get("ticker") or "").upper()
        entry = float(o.get("entry_price") or 0)
        if not tk or entry <= 0:
            return
        res = result if isinstance(result, dict) else {}
        exit_px = float(res.get("exit_price") or o.get("last_price") or entry)
        partials = o.get("partial_fills") or []
        remaining = int(o.get("remaining_shares") or 0)
        initial = int(o.get("initial_shares") or remaining or 1)
        pnl = sum((float(p[1]) - entry) * float(p[0])
                  for p in partials if isinstance(p, (list, tuple)) and len(p) >= 2)
        pnl += (exit_px - entry) * remaining
        cost = entry * initial
        _rec_ok = post_trade_record_reliably({
            "date": datetime.now(EASTERN).strftime("%Y-%m-%d"),
            "ticker": tk, "trade_id": o.get("trade_id"),
            "entry_type": o.get("entry_type") or "flat_top",
            "entry": entry, "exit": round(exit_px, 4), "shares": initial,
            "pnl": round(pnl, 2), "pnl_pct": round(pnl / cost * 100, 2) if cost else 0,
            "exit_reason": (res.get("exit_reason") or "RESUMED-EXIT"),
            "partial_fills": partials, "position_size": round(cost, 2),
            "entry_session": o.get("entry_session") or "RTH",
            "entry_crown": o.get("entry_crown"),
        })
        if _rec_ok:
            _clear_open_trade(tk, trade_id=o.get("trade_id"))
        else:
            print(f"🛟 {tk}: resume record NOT persisted — durable state kept (restart re-posts; trade_id dedups)")
    except Exception as _pre:
        print(f"⚠️  resume-record post failed for {o.get('ticker')}: {_pre}")

def _watchdog_force_record(ctx: dict):
    """Record a frozen-monitor trade at the current price (intraday) — same record-on-recovery
    semantics as startup recovery, but triggered live by the watchdog. trade_id dedups."""
    ticker = (ctx.get("ticker") or "").upper()
    if not ticker:
        return
    entry     = float(ctx.get("entry_price") or 0)
    remaining = int(ctx.get("remaining_shares") or 0)
    initial   = int(ctx.get("initial_shares") or remaining or 1)
    partials  = ctx.get("partial_fills") or []
    q  = _get_webull_quote(ticker)
    px = float(q.get("last_price") or 0) or float(ctx.get("last_price") or entry)
    # FABLE F2 (7/27 review): the watchdog books a stream/quote print too — same phantom class as
    # the blind-stop incident, and it was bypassing the off-tape guard entirely. The monitor now
    # shares its seen tape via ctx; verify here exactly like the main exit choke point.
    _wd_bk, _wd_raw, _wd_ok, _wd_why = _verify_exit_px(px, ctx.get("tape_lo"), ctx.get("tape_hi"))
    if not _wd_ok:
        print(f"🚩 WATCHDOG {ticker}: exit print ${_wd_raw:.4f} unverified ({_wd_why}) — booking ${_wd_bk:.4f}")
        try:
            _log_decision(ticker, "off_tape_exit", raw_px=round(float(_wd_raw), 4), booked_px=_wd_bk,
                          tape_lo=ctx.get("tape_lo"), tape_hi=ctx.get("tape_hi"), why=_wd_why,
                          exit_reason="WATCHDOG")
        except Exception:
            pass
        px = _wd_bk
    pnl = sum((float(p[1]) - entry) * float(p[0])
              for p in partials if isinstance(p, (list, tuple)) and len(p) >= 2)
    pnl += (px - entry) * remaining
    _cost = entry * initial
    pnl_pct = (pnl / _cost * 100) if _cost > 0 else 0   # blended (7/11 A6)
    print(f"🛟 WATCHDOG recording {ticker}: entry ${entry:.2f} → ${px:.2f} ({pnl_pct:+.1f}%, ${pnl:+.2f})")
    _rec_ok = post_trade_record_reliably({
        "entry_crown":     ctx.get("entry_crown"),
        "date": ctx.get("entry_date") or datetime.now(EASTERN).strftime("%Y-%m-%d"),
        "ticker": ticker, "entry_type": ctx.get("entry_type", ""),
        "entry": entry, "exit": round(px, 4), "shares": initial,
        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
        "exit_reason": "RECOVERED — monitor froze (watchdog)",
        "confidence": ctx.get("confidence", ""), "float_shares": "",
        "position_size": ctx.get("position_size", 0),
        "account_balance": (SIM_ACCOUNT_BALANCE if DRY_RUN else get_account_balance()), "trade_id": ctx.get("trade_id"),   # F3
        "partial_fills": partials, "highest": ctx.get("highest"),
        "entry_ts_utc": ctx.get("entry_ts_utc"),   # 7/27: the watchdog path stamps it too
        "exit_px_unverified": (not _wd_ok) or None,               # F2: same honesty columns as
        "exit_px_raw": (round(float(_wd_raw), 4) if not _wd_ok else None),   # the main exit path
    })
    send_alert_email(f"🛟 Watchdog recovered: {ticker} {pnl_pct:+.1f}%",
                     f"{ticker}'s monitor froze (heartbeat stalled). Force-recorded at ${px:.2f} "
                     f"(entry ${entry:.2f}) — P&L ${pnl:+.2f} ({pnl_pct:+.1f}%).")
    if _rec_ok:
        _clear_open_trade(ticker)
    else:
        print(f"🛟 {ticker}: record not persisted — keeping durable state for restart re-post (trade_id dedups)")

def _monitor_watchdog_loop():
    """Daemon: every WATCHDOG_CHECK_SECS, flag any active monitor whose heartbeat has stalled."""
    while True:
        try:
            now = time.time()
            for _wkey, m in list(_active_monitors.items()):
                # 8/10: registry keyed by trade_id — the human-facing name lives in ctx.
                ticker = (m.get("ctx") or {}).get("ticker") or _wkey
                stale = now - m.get("heartbeat", now)
                if stale >= WATCHDOG_RECOVER_SECS:
                    print(f"🛟 WATCHDOG: {ticker} heartbeat stale {stale:.0f}s — force-recording + aborting")
                    _monitor_abort.add(_wkey)
                    if not (m.get("ctx") or {}).get("trade_id"):
                        _monitor_abort.add(ticker)   # legacy id-less rows only (auditor F4)
                    _active_monitors.pop(_wkey, None)
                    try:
                        _watchdog_force_record(m.get("ctx", {"ticker": ticker}))
                    except Exception as e:
                        print(f"⚠️  watchdog record error for {ticker}: {e}")
                elif stale >= WATCHDOG_ALERT_SECS and not m.get("alerted"):
                    m["alerted"] = True
                    print(f"⚠️  WATCHDOG: {ticker} heartbeat stale {stale:.0f}s — alerting (force-record at {WATCHDOG_RECOVER_SECS}s)")
                    try:
                        send_alert_email(f"⚠️ Monitor stalled: {ticker}",
                                         f"{ticker}'s monitor heartbeat hasn't advanced in {stale:.0f}s. "
                                         f"Watchdog force-records at {WATCHDOG_RECOVER_SECS}s if it stays frozen.")
                    except Exception:
                        pass
        except Exception as e:
            print(f"⚠️  watchdog loop error: {e}")
        time.sleep(WATCHDOG_CHECK_SECS)


_BOOT_TS = time.time()               # 8/10: process birth (informational)
_RECOVERY_DONE_TS = [None]           # auditor F4: race window anchors HERE, not at import
_recovery_done = threading.Event()   # 8/10 BOOT BARRIER (the XHLD double-entry): entries wait
# for orphan recovery to finish re-registering positions; 90s fail-open so a hung recovery can
# never dead-lock trading (worst case = today's behavior, loudly).

def _recover_orphaned_trades():
    """THE safety net: on startup, close + RECORD any position a crashed prior run left open,
    so every entered trade reaches a recorded exit regardless of what killed the process.
    Records the remainder at the current price (the trade was interrupted)."""
    orphans = _load_open_trades_from_screener()
    if orphans is None:
        print("🚨 orphan recovery: durable store UNREACHABLE — cannot verify open positions "
              "(recovery skipped; dupe guard stays fail-closed in the race window)")
        _log_decision("_BOOT", "recovery_store_unreachable")
        return
    if not orphans:
        return
    print(f"♻️  Recovering {len(orphans)} orphaned open trade(s) from a prior run...")
    # ── 8/8 (#35): SAME-DAY orphans during market hours RESUME monitoring with full saved
    # context instead of being force-closed (the 7/29 STFS/YYGH class: close+record was the
    # only path). Overnight/weekend orphans still close — day trades must not roll over.
    # Kill: RESUME_OPEN_TRADES=0 restores close-only.
    if os.environ.get("RESUME_OPEN_TRADES", "1") == "1":
        _now_et = datetime.now(EASTERN)
        _today = _now_et.strftime("%Y-%m-%d")
        _mkt_open = _now_et.weekday() < 5 and "04:00" <= _now_et.strftime("%H:%M") < "15:40"
        _resumed = []
        for o in list(orphans):
            _tk = (o.get("ticker") or "").upper()
            if (_mkt_open and o.get("entry_date") == _today and _tk
                    and float(o.get("entry_price") or 0) > 0
                    and int(o.get("remaining_shares") or 0) > 0):
                try:
                    _rs_stream = WebullStream([_tk])
                    # auditor #2: register with the WATCHDOG before the thread starts — an
                    # unregistered resumed monitor is a frozen-invisible position (7/28 class)
                    if not o.get("trade_id"):
                        o["trade_id"] = uuid.uuid4().hex   # auditor F9: id-less orphan gets an id
                        try: _save_open_trade_sync(o)      # persist so dedup + clears work
                        except Exception: pass
                    _rs_key = o["trade_id"]
                    _active_monitors[_rs_key] = {"heartbeat": time.time(), "alerted": False, "ctx": {
                        "entry_crown": o.get("entry_crown"),       # mini-audit 3c
                        "ticker": _tk, "trade_id": o.get("trade_id"),
                        "entry_price": float(o["entry_price"]),
                        "stop": float(o.get("stop") or 0),
                        "initial_shares": int(o.get("initial_shares") or 0),
                        "remaining_shares": int(o.get("remaining_shares") or 0),
                        "tier_idx": int(o.get("tier_idx") or 0),
                        "partial_fills": o.get("partial_fills") or [],
                        "entry_type": o.get("entry_type") or "flat_top",
                        "entry_date": o.get("entry_date"),
                        "last_price": float(o.get("last_price") or o["entry_price"])}}
                    def _rs_run(_o=o, _t=_tk, _st=_rs_stream):
                        # auditor #4: crash fallback — a dead resume thread must never strand a
                        # position (neither monitored nor closed); fall back to close+record.
                        try:
                            _rs_result = monitor_trade(_t, int(_o.get("remaining_shares") or 0),
                                          float(_o["entry_price"]),
                                          float(_o.get("target") or float(_o["entry_price"]) * 1.10),
                                          float(_o.get("stop") or float(_o["entry_price"]) * 0.93),
                                          _st, None,
                                          vwap=float(_o.get("vwap") or 0),
                                          entry_type=_o.get("entry_type") or "flat_top",
                                          entered_premkt=(_o.get("entry_session") == "PRE") or None,
                                          resume_state=_o,
                                          trade_id=_o.get("trade_id"))
                            # 8/10 C2 (the unrecorded XHLD original): a resumed monitor's result
                            # reaches the books like every other exit — entry/partials from the
                            # SAVED state, exit from the monitor. trade_id dedups on the store.
                            _post_resume_record(_o, _rs_result)
                        except Exception as _mre:
                            print(f"🚨 {_t}: RESUMED MONITOR CRASHED ({_mre}) — closing + recording")
                            try:
                                _rs_ctx = (_active_monitors.pop(_o.get("trade_id") or _t, {}) or {}).get("ctx") or _o
                                _watchdog_force_record(_rs_ctx)   # auditor F10: id-keyed lookup + pop
                            except Exception as _fe:
                                print(f"🚨 {_t}: fallback close ALSO failed: {_fe}")
                    _rs_th = threading.Thread(target=_rs_run, daemon=True, name=f"resume-{_tk}")
                    _rs_th.start()
                    _resumed.append(_tk)
                    print(f"♻️  {_tk}: RESUMED (not closed) — monitor thread live with saved context")
                except Exception as _re:
                    print(f"⚠️ {_tk}: resume failed ({_re}) — falling back to close+record")
        orphans = [o for o in orphans if (o.get("ticker") or "").upper() not in _resumed]
        if _resumed and not orphans:
            return
    for o in orphans:
        ticker = (o.get("ticker") or "").upper()
        try:
            if not ticker:
                continue
            # 7/29 P1-F: HOLLOW-ROW GUARD — a row with NO entry price, NO entry date and NO trade_id
            # is a half-written corpse (the ghost STFS row my midday restart left behind), not a
            # position. "Recovering" it would book garbage. Discard loudly; a REAL position always
            # carries at least an entry price (Fable: discard only when ALL identifiers are null).
            if not (o.get("entry_price") or o.get("entry_date") or o.get("trade_id")):
                print(f"🚨 {ticker}: orphan row has no entry/date/trade_id — HOLLOW, discarding "
                      f"(not a position). Raw: {json.dumps(o, default=str)[:200]}")
                _log_decision(ticker, "orphan_row_invalid")
                _clear_open_trade(ticker)
                continue
            entry     = float(o.get("entry_price") or 0)
            remaining = int(o.get("remaining_shares") or 0)
            initial   = int(o.get("initial_shares") or remaining or 1)
            partials  = o.get("partial_fills") or []   # [[qty, price], ...]
            # For an OVERNIGHT/stale orphan, the persisted last-known price reflects the trade far
            # better than a fresh next-morning quote (which can gap). Fresh quote only for same-day.
            if o.get("entry_date") == datetime.now(EASTERN).strftime("%Y-%m-%d"):
                q  = _get_webull_quote(ticker)
                px = float(q.get("last_price") or 0) or float(o.get("last_price") or entry)
            else:
                px = float(o.get("last_price") or entry)
            pnl = sum((float(p[1]) - entry) * float(p[0])
                      for p in partials if isinstance(p, (list, tuple)) and len(p) >= 2)
            pnl += (px - entry) * remaining
            _init = int(o.get("initial_shares") or remaining or 1)
            _cost = entry * _init
            pnl_pct = (pnl / _cost * 100) if _cost > 0 else 0   # blended (7/11 A6)
            print(f"♻️  {ticker}: recording recovered exit — entry ${entry:.2f} → ${px:.2f} "
                  f"({pnl_pct:+.1f}%, ${pnl:+.2f})")
            _rec_ok = post_trade_record_reliably({
                "date":            o.get("entry_date") or datetime.now(EASTERN).strftime("%Y-%m-%d"),
                "entry_session":   o.get("entry_session") or "RTH",   # 8/8 auditor #5: rebuild reads this
                "ticker":          ticker, "entry_type": o.get("entry_type", ""),
                "entry":           entry, "exit": round(px, 4), "shares": initial,
                "pnl":             round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
                "exit_reason":     "RECOVERED after restart",
                "confidence":      o.get("confidence", ""), "float_shares": "",
                "position_size":   o.get("position_size", 0),
                "account_balance": (SIM_ACCOUNT_BALANCE if DRY_RUN else get_account_balance()),   # F3
                "trade_id":        o.get("trade_id"),
                "entry_ts_utc":    o.get("entry_ts_utc"),   # 7/27: carried through durable state
                "partial_fills":   partials, "highest": o.get("highest"),
            })
            send_alert_email(f"♻️ Recovered trade: {ticker} {pnl_pct:+.1f}%",
                             f"{ticker} was still open when the bot restarted. Closed and recorded "
                             f"at ${px:.2f} (entry ${entry:.2f}) — P&L ${pnl:+.2f} ({pnl_pct:+.1f}%).")
            if _rec_ok:
                _clear_open_trade(ticker)
        except Exception as e:
            print(f"⚠️  Recovery error for {ticker or o}: {e}")
            _clear_open_trade(ticker)   # don't let a bad record loop forever


# ============================================================
# DAY-TWO OBSERVATION (observe-only — gather data on how hard day-1 gappers
# behave on day 2). Runs on an ISOLATED daemon thread — never touches the trade
# loop, positions, or orders. Pure read + POST. See [[project_market_observations]].
# ============================================================

_auto_read_asked: dict = {}   # ticker -> epoch of last auto-read request (30-min throttle)

def _request_auto_read(ticker):
    """8/13 #54 Build 3 (Marcos: "don't just wait for them to pop" + the twice-in-one-day manual
    census): a FIRE on a mapless name is the strongest possible read request — POST the name onto
    the reader's list NOW instead of waiting for the next scan ranking. Observe-only side effects
    (a read), throttled 1/name/30min. Kill: AUTOREAD_ON_MAPLESS=0. Never raises."""
    try:
        if os.environ.get("AUTOREAD_ON_MAPLESS", "1") != "1":
            return
        now = time.time()
        if now - _auto_read_asked.get(ticker, 0) < 1800:
            return
        _auto_read_asked[ticker] = now
        url = SCREENER_URL
        if not url:
            return
        # MERGE-ONLY (the 7/24 wipe law — this endpoint REPLACES): GET current, POST the union.
        try:
            _cur = requests.get(f"{url}/api/read_list", timeout=5).json().get("tickers") or []
        except Exception:
            return                                   # can't read = don't blind-post (never wipe)
        if ticker in _cur:
            return
        requests.post(f"{url}/api/read_list", json={"tickers": list(dict.fromkeys(_cur + [ticker]))},
                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=5)
        _log_decision(ticker, "read_requested", why="mapless_fire_autoread")
        print(f"📖 {ticker} AUTO-READ requested (fired mapless) — reader picks it up next cycle")
    except Exception:
        pass

def _fetch_kev_watchlist():
    """Kev's explicitly-flagged tickers for today (from the screener /api/kev_watchlist).
    These are FORCE-watched regardless of the morning-scan top-15 score cut — the selection
    score can't be trusted to surface even names that should rank high (6/29: ILLR & AZI, both
    Kev picks, fell out of the scan entirely; ILLR backtested a real +7.3% missed win). "Kev is
    the bible" at the watch layer. The entry gates (VWAP reclaim / flat-top / room / spread /
    momentum) still apply, so this only widens *what we watch*, never *what we'll buy blindly*.
    Fail-safe: returns [] on any error so a screener hiccup can't break the morning."""
    try:
        url = os.environ.get("SCREENER_URL", "").rstrip("/")
        if not url:
            return []
        date = datetime.now(EASTERN).strftime("%Y-%m-%d")
        r = requests.get(f"{url}/api/kev_watchlist", params={"date": date}, timeout=10)
        if r.status_code == 200:
            return [str(t).upper().strip() for t in (r.json().get("tickers") or []) if str(t).strip()]
    except Exception as e:
        print(f"⚠️  Kev watchlist fetch failed (non-fatal): {e}")
    return []


PREMARKET_STARTER_N = int(os.environ.get("PREMARKET_STARTER_N", "25"))

def _premarket_starter_set(n=PREMARKET_STARTER_N):
    """#98 PREMARKET STARTER NAMES. At the 4:00 wake the live screener is near-empty (nothing has
    cleared the +8% premarket bar yet), so the candidate pool comes up empty and the session aborts
    before it starts (main() ~'No candidates from screener'). Seed it: the top-n of the most-recent
    completed session's gappers (ranked by that day's change_pct) UNION Kev's flagged names — so
    premarket detection has a backbone, and scan_morning_gappers auto-adds fresh gappers on top as
    the morning develops (same as intraday). Ranked+capped by design (Handicapper: no 350-name dump;
    Feed Engineer: stay inside the sub budget). Kev names first so a cap never strands them. Returns
    [] on any error (fail-safe — a seed hiccup must never break the morning)."""
    starter = []
    try:
        url = os.environ.get("SCREENER_URL", "").rstrip("/")
        if url:
            r = requests.get(f"{url}/api/day2", timeout=8)
            if r.status_code == 200:
                dg = (r.json() or {}).get("daily_gappers") or {}
                if dg:
                    rows = [x for x in (dg[max(dg.keys())] or []) if x.get("symbol")]   # most-recent day
                    rows.sort(key=lambda x: float(x.get("change_pct") or 0), reverse=True)
                    starter = [str(x["symbol"]).upper().strip() for x in rows[:max(0, int(n))]]
    except Exception as e:
        print(f"⚠️  Premarket starter fetch failed (non-fatal): {e}")
    kev = [str(k).upper().strip() for k in _fetch_kev_watchlist()]
    return list(dict.fromkeys(kev + starter))   # Kev first, dedup, order-stable


READ_LIST_LIQ_FLOOR = float(os.environ.get("READ_LIST_LIQ_FLOOR", "0")) or None  # None → track MOMENTUM_MIN_AVG_VOL
READ_LIST_PROBE_CAP = int(os.environ.get("READ_LIST_PROBE_CAP", "40"))  # most names we'll probe to fill 20 slots
_read_liq_cache = {}   # sym → (bucket_key, verdict) — one probe per name per 3-min scan cycle

def _read_list_liquid_enough(sym):
    """Does `sym` clear the same avg-volume floor the entry path enforces (MOMENTUM_MIN_AVG_VOL,
    completed bars only)? FAIL-OPEN: no bars / any error → True, because a data miss must never be
    read as illiquidity (that's how a fail-closed gate quietly empties a roster). Cached per name per
    3-min bucket so a rescan doesn't re-probe. Runs on the AUX executor — never the trade pool."""
    floor = READ_LIST_LIQ_FLOOR or MOMENTUM_MIN_AVG_VOL
    try:
        _n = datetime.now(EASTERN)
        bucket = (_n.date(), _n.hour, _n.minute - _n.minute % 3)
        hit = _read_liq_cache.get(sym)
        if hit and hit[0] == bucket:
            return hit[1]
        raw = get_intraday_bars(sym, count=MOMENTUM_BARS + 3, executor=_aux_executor,
                                sessions=_live_sessions())
        if not raw:
            # The FETCH told us nothing (miss, 429 cooldown, error) → fail-open, and say so, because
            # a silent fail-open during a 429 storm is indistinguishable from "everything is liquid".
            print(f"   ⚪ read-list: {sym} liquidity unknown (no bar data) — keeping (fail-open)")
            return True
        bars = _fresh_session(raw)
        if not bars:
            # The fetch SUCCEEDED and still produced no fresh session bars: the name has not printed
            # recently. That is the DCOY/DBGI/TGL signature (20/6/7 traded minutes in 30h) and it is
            # the strongest evidence of thinness there is — routing it to fail-open, as the first cut
            # of this fix did, would have let through exactly the names the fix exists to exclude.
            # Same staleness standard the ENTRY path applies via _fresh_session, so nothing is
            # refused here that would have been allowed to trade.
            print(f"   🚫 read-list: {sym} skipped — no fresh bars (last print stale; entry would refuse it too)")
            _read_liq_cache[sym] = (bucket, False)
            return False
        if len(bars) < MOMENTUM_BARS + 1:
            return True                                   # too few to average — no evidence either way
        vols = [float(b.get("volume") or b.get("v") or 0) for b in bars[:-1]][-MOMENTUM_BARS:]
        avg = sum(vols) / len(vols) if vols else 0
        ok = avg >= floor
        _read_liq_cache[sym] = (bucket, ok)
        if not ok:
            print(f"   🚫 read-list: {sym} skipped — {int(avg):,}/bar < {int(floor):,} floor (entry would refuse it)")
        return ok
    except Exception:
        return True                                       # fail-open on any error

def _post_read_list(gappers):
    """#99 (Marcos 7/23): post the READER's roster — top-20 by MOVE % (change_pct, the exact
    dashboard column — NOT the internal select_score) + Kev's names FIRST — so the newcomer reader
    reads biggest-movers-first and, if it runs out of time before 9:30, still got the top movers.
    Called at the END of every scan (session start + each 3-min rescan) so it's fresh at 8:50.
    Never raises — a read-list hiccup must not break the scan."""
    try:
        url = os.environ.get("SCREENER_URL", "").rstrip("/")
        if not url:
            return
        ranked = sorted([g for g in (gappers or []) if g.get("symbol")],
                        key=lambda g: float(g.get("change_pct") or 0), reverse=True)
        # 7/27 READ-LIST LIQUIDITY FLOOR (Marcos: "make sure that fix is high priority"). Move% alone
        # put names the UNIVERSAL LIQUIDITY GATE will refuse at entry onto the reader's roster — we
        # paid an API call plus 15–50s of reader cycle to chart stock we can never buy (7/27: DCOY /
        # DBGI / TGL had 20 / 6 / 7 traded minutes in 30h and ate 3 of ~78 morning reads). Same floor
        # here as at entry. The SCANNER's wide net is deliberately unchanged — that's the counterfactual
        # log. Fail-OPEN on missing bars (a data miss must never silently shrink the roster), and Kev's
        # own names are never filtered ("Kev is the bible" at the watch layer).
        top = []
        for g in ranked[:READ_LIST_PROBE_CAP]:
            if len(top) >= 20:
                break
            sym = str(g["symbol"]).upper().strip()
            if _read_list_liquid_enough(sym):
                top.append(sym)
        kev = [str(k).upper().strip() for k in _fetch_kev_watchlist()]
        tickers = list(dict.fromkeys(kev + top))   # Kev FIRST, then Move%-desc, dedup order-stable
        requests.post(f"{url}/api/read_list", json={"tickers": tickers},
                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=5)
    except Exception as e:
        print(f"⚠️  read-list post failed (non-fatal): {e}")


_kev_levels_cache = {"date": None, "levels": {}, "ts": 0.0}
KEV_LEVELS_TTL_SECS = int(os.environ.get("KEV_LEVELS_TTL_SECS", "90"))

def _fetch_kev_levels():
    """Marked levels for today ({TICKER: {"break": x, ...}}) — night sheet + intraday vision reads.
    Cached with a ~90s TTL: the old PER-DAY cache froze the first fetch of the morning, so levels
    posted intraday (newcomer vision reads) were INVISIBLE to the chart gate all day — in ENFORCE
    that silently blocked every newcomer (Fable audit 7/18). On refresh failure serve the SAME-DAY
    last-known-good (never a fail-closed {} spike); a different-day cache is never served (date-blind
    levels are the B14 bug class). Fail-safe {} before the first successful fetch."""
    c = _kev_levels_cache
    try:
        date = datetime.now(EASTERN).strftime("%Y-%m-%d")
        now = time.time()
        if c["date"] == date and now - c["ts"] < KEV_LEVELS_TTL_SECS:
            return c["levels"]
        url = os.environ.get("SCREENER_URL", "").rstrip("/")
        if url:
            r = requests.get(f"{url}/api/kev_watchlist", params={"date": date}, timeout=10)
            if r.status_code == 200:
                lv = r.json().get("levels") or {}
                c.update({"date": date, "levels": lv, "ts": now})
                return lv
    except Exception:
        pass
    try:
        if c["date"] == datetime.now(EASTERN).strftime("%Y-%m-%d"):
            c["ts"] = time.time()          # back off one TTL before retrying the failed refresh
            return c["levels"]
    except Exception:
        pass
    return {}


# ============================================================
# LAYER 2 — "NO BREAK, NO TRADE" chart-level gate  (SHADOW by default)
# ------------------------------------------------------------
# Kev's core rule (Marcos, 7/17): enter ONLY when price has broken the MARKED level from the
# chart read. The bot historically had NO "wait for the break" concept — it fired ignition on any
# intraday base pop regardless of where price sat vs the level (7/17: 9/20 entries had NO break;
# no-break entries netted -1.68R vs +0.75R for break entries; TGHL bought 1.40 vs a 1.95 break).
#
# Marked level source (v1): the night sheet's per-ticker levels via _fetch_kev_levels()
#   → {ticker: {"break": x, "confirm": y, "targets": [...], "note": "..."}}.
#   Newcomers with no sheet entry have no marked level yet (the visual read isn't wired into the
#   bot yet — that's the Layer-2b follow-on: post newcomer reads to the store, look them up here).
#
# Enforcement: SHADOW by default (CHART_GATE_ENFORCE unset/0) — logs the verdict beside every trade
#   but changes NOTHING. Set CHART_GATE_ENFORCE=1 ONLY after the shadow log proves the gate on live
#   tape. Verdicts: 'allow' (price broke the level), 'block' (entered BELOW the level = no break),
#   'skip' (no marked level, or a do-not-trade veto on the sheet).
# ============================================================
CHART_GATE_ENFORCE = os.environ.get("CHART_GATE_ENFORCE", "0") == "1"
# #109 BAND (Marcos-approved 7/24 night): entries within CHART_GATE_BAND below the marked break
# level are ALLOWED — Kev buys confirmed pullbacks UNDER the level to ride through the break
# (EHGO 3.81/3.95 under the highs, VIVK 2.22). Kill-test band_killtest.py on all 70 blocked
# under-level entries 7/22-7/24 replayed w/ capped-loss exit: 0-2% below = +0.66R/trade (n=16,
# 50% win) vs 2-5% = -0.31, >10% = -0.69 (gate RIGHT to block deep). Monotonic depth gradient.
# CHART_GATE_BAND=0 restores the hard no-break-no-trade gate. Band allows log reason
# "band_below_level" so live grading is free.
CHART_GATE_BAND = float(os.environ.get("CHART_GATE_BAND", "0.02"))

def _blended_pnl(entry_price, total_shares, partial_fills, exit_price):
    """Whole-trade P&L: every scale-out leg plus the runner leg. The runner quantity is
    derived from what was never scaled out (total − sum of partials) — NEVER from the
    monitor loop's `remaining_shares`, which exit branches zero for bookkeeping before
    this math runs (7/20: that erased BIYA's −$10.71 runner leg → recorded +$34.40,
    true +$23.69; inflates losses dropped, understates runner wins equally)."""
    if partial_fills:
        pnl = sum((px - entry_price) * qty for qty, px in partial_fills)
        runner_qty = total_shares - sum(qty for qty, _px in partial_fills)
        return pnl + (exit_price - entry_price) * runner_qty
    return (exit_price - entry_price) * total_shares


_move_pct: dict = {}   # sym -> the scanner's Move % (vendor change_ratio x100) — refreshed each gapper scan

def _entry_priority(b):
    """CAPITAL-PRIORITY key (Marcos 7/26: "I want Kev's list and the ranked movers list in the
    scanner to determine level of priority" ... "not the internal scoring, but the actual column
    labeled move %" ... "I want to run after the big boys — those names are always the ones more
    in play"). Sort ascending: (tier, -rank) →
      tier 0 = Kev-sheet names (src != vision; same helper as the day-gain exemption),
      tier 1 = everyone else, ranked by the SCANNER'S Move % column — the vendor change_ratio the
               board displays (same field, same number), refreshed each gapper scan. Fallback for
               names not on the scan (e.g. intraday Kev adds): the internal day_gain stamp.
               Nothing known sinks below everything unknown (-999 sentinel)."""
    _mv = _move_pct.get(b[0])
    if _mv is None:
        _mv = b[4].get("day_gain")
    return (0 if _kev_sheet_name(b[0]) else 1, -(_mv if _mv is not None else -999.0))


def _kev_sheet_name(ticker):
    """DAY-GAIN FLOOR exemption (7/22): True when today's levels carry a NON-vision (sheet/manual)
    entry for this ticker — Kev's explicit picks trade his LEVELS and may sit flat/red at pick time
    (OMH −34% AH was still 'over 0.65'); a homegrown filter must never override the Bible.
    Fail-closed (floor applies) — if the levels fetch is down, the ENFORCE chart gate blocks the
    entry anyway (no_marked_level), so this can't strand a Kev entry."""
    try:
        lv = (_fetch_kev_levels() or {}).get(ticker) or {}
        # 8/12 primacy flip (auditor blocker 1): a flipped row is src="vision" but STILL Kev's
        # pick — kev_name carries the provenance; without this, all Kev exemptions (daygain
        # floor, tier-0 sort, *KEV label) silently die at the first 07:00 read.
        return bool(lv) and (bool(lv.get("kev_name")) or str(lv.get("src") or "") != "vision")
    except Exception:
        return False


def _chart_break_gate(ticker, entry_price, entry_type=None):
    """No Break, No Trade. Returns (verdict, reason, level, source) and NEVER raises (fail-safe →
    a gate bug must never crash the trade path). verdict ∈ {'allow','block','skip'}.

    READ-STALENESS (7/21 Cartographer, task #77 part 1): a map whose targets are EXHAUSTED must
    stop issuing verdicts — CPHI's 8:50 map (break 1.07) issued 16 meaningless ALLOWs at $5–14.60.
    For LEGACY breakout machines only: price beyond the read's LAST target → skip 'read_exhausted'
    (doubles as the re-read request marker for the reader). Curl-entry machines (rocket_catcher /
    vwap_reclaim / zone_flip) are EXEMPT — they trade live structure, not the stale level, and the
    CPHI dip-buy at $5+ must not be blocked by a $1 map. Classifier replayed on all 96 priced 7/21
    gate rows: flips exactly the 19 stale allows (all ma_pullback), touches none of the day's trades."""
    _STALE_EXEMPT = ("rocket_catcher", "vwap_reclaim", "zone_flip", "hidden_entry")
    # 7/30 (Fable ship, Marcos "ship it and shadow the alternative"): ignition joins the
    # live-structure bypass — it fires on a volume surge off a quiet base, i.e. BELOW Kev's marked
    # level, so "price broke the level" was a LATENESS detector for this lane (gate-ON −$19.80 n=5
    # vs gate-OFF +$482.51 at 4.5×, E3/E4). The gated alternative still accrues: every ignition
    # fire stamps the legacy verdict via the "_shadow_legacy" probe below. Kill: IGNITION_CHART_BYPASS=0.
    _bypass = ("hidden_entry", "vwap_reclaim", "zone_flip") + (("ignition",) if IGNITION_CHART_BYPASS else ())
    if entry_type in _bypass:
        # LIVE-STRUCTURE lanes (Marcos 7/24: "switch the reclaim and zone flip"): these trade
        # live 10s structure (VWAP/90MA wick, session VWAP 3-gate, premarket shelf) — a reader
        # map is irrelevant and unmapped intraday adds must not die on no_marked_level (#72:
        # DFNS/NIPG/JZXN rockets gate-skipped all day 7/22). Legacy lanes stay gated (13
        # no-map blocks graded −0.17R/tr this week — the gate is RIGHT for them).
        # 7/27: carry the marked level in the allow row (was None) — LGHL/DFNS/VEEE entered below
        # fresh marked breaks invisibly; the level rides along as EVIDENCE, still never a veto here.
        try:
            _blv = float((_effective_map(ticker, entry_price) or {}).get("break") or 0) or None   # 8/7 auditor #4
        except Exception:
            _blv = None
        return ("allow", "live_structure", _blv, "none")
    try:
        lv = _effective_map(ticker, entry_price) or {}   # 8/7 auditor #4: the ENFORCE gate was
        # reading the RAWEST map — never got 8/6 freshest nor the contract; missed twin.
        note = str(lv.get("note") or "").lower()
        if lv.get("veto") or "do-not-trade" in note or "do not trade" in note or "pass" == note.strip():
            # 8/12 MARCOS DOCTRINE ("the chart and tape decide. No one has veto power") +
            # re-grade: this branch fired ZERO times since enforcement began (era-wide row
            # census, n=0) — removal encodes the law at zero measured cost. Veto/stand-down
            # language stays RECORDED (row below + kev_shadow) for the Friday A/B and magnet
            # grading; it gates nothing, anywhere, for anyone.
            _log_decision(ticker, "veto_noted_not_gating", price=round(float(entry_price), 4),
                          machine=entry_type)
        brk = lv.get("break")
        try:
            brk = float(brk)
        except (TypeError, ValueError):
            brk = 0.0
        if brk <= 0:
            return ("skip", "no_marked_level", None, "none")                 # no read → no trade
        if entry_type not in _STALE_EXEMPT:
            try:
                _tgts = lv.get("targets") or []
                _lastT = float(_tgts[-1]) if _tgts else 0.0
            except (TypeError, ValueError, IndexError):
                _lastT = 0.0
            if _lastT > 0 and float(entry_price) > _lastT:
                # 7/21 late KILL-TEST REFUTED the hard skip (read_staleness_killtest.py, BOTH enforce
                # days): on 7/20 past-map = MOMENTUM — the skip would have blocked ZYBT +$164.79 and
                # BIYA +$34.40 to avoid SKYQ −$41 (net ≈ −$160). Room-gate-inversion class. So:
                # OBSERVE-ONLY — log the exhausted state (evidence + future re-read trigger), never block.
                try:
                    _log_decision(ticker, "read_exhausted_observed", entry=round(float(entry_price), 4),
                                  last_target=_lastT, break_level=brk, machine=entry_type)
                except Exception:
                    pass
        if float(entry_price) >= brk:
            return ("allow", "broke_level", brk, "sheet")                    # price broke the mark
        if CHART_GATE_BAND > 0 and float(entry_price) >= brk * (1.0 - CHART_GATE_BAND):
            # #109: pullback-under-the-level entry (Kev's own class) — within the tested band
            return ("allow", "band_below_level", brk, "sheet")
        return ("block", "no_break_below_level", brk, "sheet")               # entered under the mark
    except Exception:
        return ("skip", "gate_error", None, "none")


def _seed_day2_from_gappers(gappers: list):
    """After the morning scan, carry today's hard gappers into tomorrow's day-2 watch list."""
    url = os.environ.get("SCREENER_URL", "").rstrip("/")
    if not url or not gappers:
        return
    try:
        # #98: never re-carry the premarket STARTER seed as if it were a fresh day-1 gapper
        # (they carry change_pct=0 and are already in day2 from their real gap day).
        gappers = [g for g in gappers if g.get("source") != "premarket_starter"]
        if not gappers:
            return
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
                bars = _fresh_session(get_intraday_bars(t, count=390, executor=_aux_executor))   # B16
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


_rest_price_cache = {}                  # {TICKER: (attempt_ts, price)} — see _get_price_rest
_rest_price_lock = threading.Lock()
REST_PRICE_TTL_SECS = float(os.environ.get("REST_PRICE_TTL_SECS", "3"))
# ── 7/28 P0 FIX A (Marcos found it live: "the prices showing are the end of day prices... not the
#    current live pre-market price"; DFNS 13.10 vs actual 16.02). Premarket, the snapshot's `close`
#    is the PRIOR session's official close, and the parser takes it first — so every premarket
#    price the loop saw was a day old. Session-aware serving: premarket → the RAW premarket field
#    or NO PRICE (Fable ruling, B16: a wrong price fires detectors, a missing price skips a cycle
#    — never fall back to yesterday's close). RTH path byte-identical. PRICE_SESSION_AWARE=0 kills.
PRICE_SESSION_AWARE = os.environ.get("PRICE_SESSION_AWARE", "1") == "1"
# 7/29 FIX B (spec P0-C): accept `extend_hour_last_price` as the live premarket quote when its own
# trade-time is fresh. PM_EXT_QUOTE=0 kills; the age cap keeps a halted name honest (trade_time
# stops advancing → ages out → NO-PRICE again).
PM_EXT_QUOTE           = os.environ.get("PM_EXT_QUOTE", "1") == "1"
PM_EXT_QUOTE_MAX_AGE_S = float(os.environ.get("PM_EXT_QUOTE_MAX_AGE_S", "120"))
_px_canary_t = 0.0
_pm_payload_t = 0.0

def _session_price(q, hm=None):
    """The price the trading loop should act on, by session. Premarket: the RAW premarket field
    (None-safe) or 0 = no price. RTH and everything else: last_price, unchanged. `hm` injectable
    for the rig; live callers omit it."""
    if not PRICE_SESSION_AWARE:
        return float(q.get("last_price") or 0)
    try:
        if (hm or datetime.now(EASTERN).strftime("%H:%M")) < "09:30":
            raw = q.get("pre_market_price_raw")
            return float(raw) if raw and raw > 0 else 0.0
    except Exception:
        pass
    return float(q.get("last_price") or 0)

def _get_price_rest(ticker) -> float:
    """REST fallback for current price when MQTT is unavailable. Uses SDK.
    CACHED ~3s per ticker (attempts AND results — 429-kill set 7/18): loop_sleep's single GLOBAL
    tick stamp means one hot name keeps the whole loop at 0.5s, REST-hammering every quiet name
    2×/sec (~20 calls/sec — the 7/17-verified flood). This cache enforces the loop's own documented
    invariant ("streaming can never poll REST harder than plain 3s polling") PER NAME, regardless
    of loop cadence. Failures cache too (0 already means "no price" to callers) so a 429 storm
    can't hammer retries. A healthy stream bypasses this entirely (get_price serves fresh ticks)."""
    t = str(ticker).upper()
    now = time.time()
    with _rest_price_lock:
        rec = _rest_price_cache.get(t)
        if rec and now - rec[0] < REST_PRICE_TTL_SECS:
            return rec[1]
    q = _get_webull_quote(ticker)
    px = _session_price(q)                       # 7/28 P0 fix A — premarket serves the LIVE field or nothing
    _lp = float(q.get("last_price") or 0)
    global _px_canary_t
    if px != _lp and time.time() - _px_canary_t > 120:   # substitution canary (wk-1 audit trail)
        _px_canary_t = time.time()
        print(f"🕐 SESSION PRICE {t}: serving {px if px else 'NO-PRICE (no live premarket field)'} "
              f"instead of stale last {_lp} [premarket]")
    with _rest_price_lock:
        _rest_price_cache[t] = (time.time(), px)
    # 7/28 lens stage-1 review fix: the registry's ONLY writer was the streaming tick handler
    # (:1241), so with a silent stream the lens went DARK (no price → nothing in focus) exactly
    # in degraded mode. REST prices the loop already paid for now feed the registry too — the
    # lens rides existing acquisition, still zero calls of its own. Real prices only (px>0).
    if px and px > 0:
        with _price_lock:
            _price_registry[t] = {"p": px, "t": time.time()}
    return px


_quote_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4,
                                                        thread_name_prefix="wb_quote")
_quote_wedge = {"n": 0}   # auditor F11: consecutive-timeout wedge detector
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
    global _quote_executor
    try:
        # 8/10 RESTART-PROOF (Marcos: zero effect, ever): EVERYTHING that can touch the network
        # — including SDK client init/auth, which was running UNCAPPED on the monitor thread and
        # is the prime suspect for the frozen-resumed-monitor class — runs under the hard timeout.
        def _snap():
            _dc = _get_data_client()
            if not _dc:
                return None
            return _dc.market_data.get_snapshot(symbols=ticker, category="US_STOCK",
                                                extend_hour_required=True)
        try:
            future = (executor or _quote_executor).submit(_snap)
        except RuntimeError as _dead:
            # 8/10 SELF-HEALING PLUMBING ("cannot schedule new futures after shutdown"): a dead
            # pool is rebuilt on the spot — a monitor must never ride bar-fallback forever
            # because an executor object died.
            print(f"🔧 quote executor dead ({_dead}) — rebuilding pool")
            _quote_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4,
                                                                    thread_name_prefix="wb_quote")
            future = _quote_executor.submit(_snap)
        try:
            resp = future.result(timeout=QUOTE_TIMEOUT_SECS)
            _quote_wedge["n"] = 0   # any success resets the wedge counter
            if resp is None:
                return {}
        except concurrent.futures.TimeoutError:
            print(f"⚠️  Webull quote TIMEOUT for {ticker} (>{QUOTE_TIMEOUT_SECS}s) — treating as no price")
            _bump("timeouts")
            # auditor F11: hung _snap workers saturate the pool with NO RuntimeError — after 6
            # consecutive timeouts, abandon the wedged pool and rebuild (workers are daemons).
            _qt = _quote_wedge
            _qt["n"] += 1
            if _qt["n"] >= 6:
                _qt["n"] = 0
                print("🔧 quote pool wedged (6 consecutive timeouts) — abandoning + rebuilding")
                _quote_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4,
                                                                        thread_name_prefix="wb_quote")
            return {}
        if resp.status_code != 200:
            print(f"⚠️  Webull snapshot {resp.status_code} for {ticker}")
            _bump("api_429" if resp.status_code == 429 else "api_err")
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

        # 7/28 P0 PAYLOAD LOGGER (Fable B-evidence): premarket, dump one raw payload every ~10 min
        # so tonight's stream-field decision (fix B) runs on DATA, not inference. Throttled global.
        global _pm_payload_t
        try:
            # 7/28: extended into RTH (was premarket-only). Halt awareness (docket #1) needs to know
            # whether this payload carries a trading-status field AT ALL — that question can only be
            # answered by an RTH sample. Same 10-min throttle, one global.
            if time.time() - _pm_payload_t > 600:
                _pm_payload_t = time.time()
                _sess = "PM" if datetime.now(EASTERN).strftime("%H:%M") < "09:30" else "RTH"
                print(f"🔬 {_sess}-PAYLOAD {ticker}: {json.dumps({k: d.get(k) for k in sorted(d)}, default=str)[:700]}")
        except Exception:
            pass
        last   = float(d.get("close")     or d.get("last_price")   or d.get("lastPrice")   or d.get("c") or 0)
        bid    = float(d.get("bid_price")  or d.get("bidPrice")     or d.get("bid")         or 0)
        ask    = float(d.get("ask_price")  or d.get("askPrice")     or d.get("ask")         or 0)
        vol    = float(d.get("volume")     or d.get("v")            or 0)
        pclose = float(d.get("pre_close")  or d.get("preClose")     or last                 or 0)
        chg_r  = float(d.get("change_ratio")  or d.get("changeRatio")   or 0)
        # 7/28 P0 (Fable amendment): RAW premarket field — present vs defaulted MUST be
        # distinguishable. The legacy pre_p below defaults to `last` (yesterday's close premarket),
        # which is exactly the trap that would let a naive session-price fix pass the rig and stay
        # stale in production. pre_market_price_raw is None when the payload has no real field.
        _raw_pre = d.get("pre_market_price") or d.get("preMarketPrice")
        try:
            _raw_pre = float(_raw_pre) if _raw_pre not in (None, "", 0, "0") else None
            if _raw_pre is not None and _raw_pre <= 0:
                _raw_pre = None
        except (TypeError, ValueError):
            _raw_pre = None
        # ── 7/29 FIX B (Fable-approved spec P0-C): Webull carries the LIVE premarket quote as
        # `extend_hour_last_price` + `extend_hour_last_trade_time` (epoch ms) — `pre_market_price`
        # is simply absent from these payloads (captured AMIX/INBS/TOPS dumps, 7/29 logs), which is
        # why premarket served NO-PRICE all week. Accept the field ONLY when its own trade-time is
        # fresh (≤ PM_EXT_QUOTE_MAX_AGE_S): a halted/dead name's trade_time stops advancing, ages
        # out, and correctly returns to NO-PRICE. Never `close` (yesterday — the known trap).
        # Kill switch: PM_EXT_QUOTE=0.
        if _raw_pre is None and PM_EXT_QUOTE:
            try:
                _ehp = float(d.get("extend_hour_last_price") or 0)
                _eht = float(d.get("extend_hour_last_trade_time") or 0) / 1000.0
                if _ehp > 0 and _eht > 0 and (time.time() - _eht) <= PM_EXT_QUOTE_MAX_AGE_S:
                    _raw_pre = _ehp
            except (TypeError, ValueError):
                pass
        pre_p  = float(d.get("pre_market_price")        or d.get("preMarketPrice")        or last or 0)
        pre_r  = float(d.get("pre_market_change_ratio") or d.get("preMarketChangeRatio")  or chg_r or 0)

        # 7/11 audit A10: the SDK ratio fields are FRACTIONS (proven — every scanner path multiplies
        # unconditionally). The old `×100 only if |x|<1` heuristic reported a +150% mover as "+1.5%" —
        # exactly our target regime mis-read. Always ×100.
        pre_r = pre_r * 100

        # NOTE: the Webull snapshot does NOT carry a VWAP field — VWAP is computed from intraday bars.
        # So this is expected to be 0 here; do NOT warn (it fired per-ticker per-cycle = thousands of
        # dropped log messages, the 6/26 observability blackout). avgVol REMOVED from the chain (7/11
        # audit A11): it is a VOLUME — one payload change away from a 2,000,000 "vwap".
        vwap_raw = (d.get("vwap") or d.get("vwap_price") or d.get("average_price") or
                    d.get("avgPrice") or d.get("dayAvgPrice") or 0)
        vwap = float(vwap_raw)

        return {
            "last_price":            last,
            "bid":                   bid,
            "ask":                   ask,
            "volume":                vol,
            "prev_close":            pclose,
            "change_ratio":          round(chg_r * 100, 2),   # fraction → percent, unconditional (7/11 A10)
            "pre_market_price":      pre_p,
            "pre_market_price_raw":  _raw_pre,   # 7/28 P0: None when the payload has NO real field
            "pre_market_change_pct": round(pre_r, 2),
            "vwap":                  vwap,
        }
    except _WBServerException as e:
        # 7/17: the SDK RAISES on HTTP errors, so the resp.status_code==429 check above is dead code
        # and the 429 gauge read zero through entire rate-limit storms. Count from the exception.
        _st = getattr(e, "http_status", None)
        _bump("api_429" if _st == 429 or "429" in str(e) else "api_err")
        global _last_srvexc_print
        if time.time() - _last_srvexc_print > 30:   # per-call prints at flood rate were their own storm
            _last_srvexc_print = time.time()
            print(f"⚠️  Webull ServerException (status {_st}) for {ticker} — counting quietly, next print ≥30s")
        return {}
    except Exception as e:
        print(f"⚠️  Webull quote error for {ticker}: {e}")
        _bump("api_err")
        return {}

_last_srvexc_print = 0.0   # throttle for the ServerException print above


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

        bars = _to_chronological(bars)   # SDK is newest-first; we need oldest→newest for early vs late
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
        _bump("fail_open")
        return True, 0.0
    spread_pct = (ask - bid) / ask
    ok = spread_pct <= MAX_SPREAD_PCT
    if ok:
        print(f"✅ {ticker} spread: ${bid:.2f}/${ask:.2f} ({spread_pct*100:.2f}%) — OK")
    else:
        print(f"🚫 {ticker} spread too wide: ${bid:.2f}/${ask:.2f} ({spread_pct*100:.2f}%) > {MAX_SPREAD_PCT*100:.1f}% limit")
    return ok, spread_pct


# ── L1 (top-of-book) order-book guard + instrumentation ──
# Webull REST market data caps at depth=1 (multi-level = paid Nasdaq TotalView, US$135/mo
# non-display — see memory project_l2_data_cost). So real overhead-wall detection isn't
# available for free. Instead we use the inside quote we CAN get and:
#   • BLOCK only the unambiguous danger case — a real ask with no bid to sell into,
#   • LOG the inside bid/ask imbalance on EVERY entry (details below flow into the trade
#     record) so we can later MEASURE whether adverse book conditions correlate with losers.
#     That data is what would justify (or not) paying for TotalView. No more silent fail-open.
# NOTE: with only 1 level, inside SIZE is just the top lot and far too noisy to gate on (e.g.
# TSLA prints a 33-share inside bid yet is deeply liquid). So we LOG size/imbalance and only
# BLOCK the unambiguous case — an ask with literally no bid in the book.

def check_level2(ticker, entry_price) -> tuple[bool, dict]:
    """L1 top-of-book guard. Returns (ok, details); details always carries the inside book
    for instrumentation. ok=False only on no-bid-support (clear danger)."""
    details = {"ask_size": 0, "bid_size": 0, "ratio": None, "spread": None,
               "inside_bid": None, "inside_ask": None, "reason": "", "source": "L1"}
    try:
        dc = _get_data_client()
        if not dc:
            details["reason"] = "no data client"
            _bump("fail_open")
            return True, details                      # infra error → don't block (but recorded)
        try:
            resp = _quote_executor.submit(
                dc.market_data.get_quotes, symbol=ticker, category="US_STOCK", depth=1
            ).result(timeout=QUOTE_TIMEOUT_SECS)
        except Exception as e:
            details["reason"] = f"L1 fetch error: {str(e)[:60]}"
            _bump("api_err"); _bump("fail_open")
            return True, details
        if getattr(resp, "status_code", 200) != 200:
            details["reason"] = f"L1 status {resp.status_code}"
            _bump("api_429" if getattr(resp, "status_code", 0) == 429 else "api_err"); _bump("fail_open")
            return True, details

        raw = resp.json()
        d = raw[0] if isinstance(raw, list) and raw else (raw if isinstance(raw, dict) else {})
        asks_raw = d.get("asks", d.get("askList", d.get("ask_list", []))) or []
        bids_raw = d.get("bids", d.get("bidList", d.get("bid_list", []))) or []

        def _first(arr):
            if not arr:
                return 0.0, 0.0
            a = arr[0]
            return (float(a.get("price") or a.get("p") or 0),
                    float(a.get("size") or a.get("volume") or a.get("v") or a.get("s") or 0))
        ask_p, ask_s = _first(asks_raw)
        bid_p, bid_s = _first(bids_raw)

        details["inside_ask"] = round(ask_p, 4) if ask_p else None
        details["inside_bid"] = round(bid_p, 4) if bid_p else None
        details["ask_size"]   = int(ask_s)
        details["bid_size"]   = int(bid_s)
        if ask_p and bid_p:
            details["spread"] = round(ask_p - bid_p, 4)
        details["ratio"] = round(ask_s / bid_s, 2) if bid_s > 0 else None

        # BLOCK only the unambiguous case: an ask exists but the bid side is EMPTY — nothing
        # to sell into. Inside size is noise (see note above), so it's logged, not gated.
        if ask_p > 0 and bid_p <= 0:
            details["reason"] = "no bid in book (nothing to sell into)"
            print(f"🚫 {ticker} L1: NO BID IN BOOK — ask {int(ask_s)}@${ask_p:.2f}, no bid")
            return False, details

        rstr = f"{details['ratio']}:1" if details["ratio"] is not None else "n/a"
        print(f"📖 {ticker} L1: bid {int(bid_s)}@${bid_p:.2f} | ask {int(ask_s)}@${ask_p:.2f} "
              f"| ask/bid {rstr} (logged for study)")
        return True, details

    except Exception as e:
        details["reason"] = f"L1 error: {str(e)[:60]}"
        _bump("api_err"); _bump("fail_open")   # F2 (7/11): the 4th fail-open path, now counted
        return True, details


# ── 8/6 AMBIENT LIQUIDITY FLOOR (Marcos: "this volume gate ignorance must be fixed" + "same
#    story here" — FVN 810/bar and SUGP 2.4k/bar both entered through spike-measured floors).
#    Both old floors measure the FIRE: ignition's 5k floor checks the spike bar itself, and the
#    universal 10k AVG gets dragged over the line by that same spike (plus ignition carved out
#    entirely). This floor measures the RESTING tape: MEDIAN dollar-volume of the last 10
#    completed 1-min bars (median = spike-proof) must cover AMBIENT_DVOL_MULT x the position
#    cap — you must be able to LEAVE inside a minute without being the whole tape. Execution-
#    safety rationale, not edge (the 8/6 kill test showed era paper P&L can't see slippage;
#    data/killtests/ambient_liquidity_20260806.py). Applies to ALL lanes incl. ignition (the
#    quiet-base carve-out confused quiet with illiquid). Kill: AMBIENT_DVOL_MULT=0. ──
# MULT calibration (8/6): 5x was participation-rate practice (exit <=20%% of a median minute)
# but passes FVN ($14.6k/min — thin shares, $15 stock). 10x blocks BOTH 8/6 specimens and the
# era cohort under it is 23 trades / -$47.93 on paper (before live slippage, which paper
# understates). Homegrown -> translation registry; Friday re-grades from mapless/ambient stamps.
# 15x FINAL (8/6, Marcos: "these low volume losers are a fucking waste of time. We need to be
# big game hunting"): $15k/min blocks BOTH 8/6 specimens (FVN $14.6k incl.) at ZERO additional
# winner cost vs 10x (same 13 forgone scratches, +$187 paper, all sub-$40 dead-tape trades that
# live slippage mostly eats). Era cohort under the floor: 25 trades, -$66.95 net.
AMBIENT_DVOL_MULT = float(os.environ.get("AMBIENT_DVOL_MULT", "15.0"))

def _ambient_dvol_ok(bars):
    """(ok, median_dvol, need). Median $ volume of the last 10 COMPLETED bars vs the floor.
    Fail-OPEN on missing data (<5 completed bars) — a data gap is not evidence of thin tape;
    the read-list floor and PRE_MIN_DVOL own the sparse-tape cases."""
    try:
        if not AMBIENT_DVOL_MULT:
            return True, 0.0, 0.0
        comp = bars[:-1] if len(bars) > 1 else bars
        dv = sorted(float(b.get("volume") or b.get("v") or 0) * float(b.get("close") or b.get("c") or 0)
                    for b in comp[-10:])
        if len(dv) < 5:
            _gate_failopen("ambient", why="<5 bars")   # 8/8 #33: counted, still open by design
            return True, 0.0, 0.0
        med = dv[len(dv) // 2]
        need = AMBIENT_DVOL_MULT * MAX_TRADE_DOLLARS
        return med >= need, med, need
    except Exception:
        _gate_failopen("ambient", why="exception")
        return True, 0.0, 0.0

def check_momentum(ticker) -> tuple[bool, dict]:
    """
    Fetch recent 1-min bars and read momentum at execution time. Kev's concept = "volume on the break".
    HARD rejects (ok=False): (1) VOLUME SURGE — the break bar's volume must be ≥ MOMENTUM_VOL_ACCEL× the
    prior completed bars' avg; a break with no volume behind it isn't a real move (7/2 — this is now the
    PRIMARY entry filter, replacing the de-inverted room gate; see MOMENTUM_VOL_ACCEL note); (2) TOPPING
    TAIL on the last completed bar (Kev "don't enter into a candle rejected at the high"). The volume-FLOOR
    and green-count thresholds stay OBSERVE-only (soft, logged 'momentum_soft'). Returns (ok, details).
    """
    details = {"passed": False, "reason": ""}
    try:
        full = get_intraday_bars(ticker, count=390, sessions=_live_sessions())
        sess = _fresh_session(full) if full else []   # B16: decision gate — today-only
        if len(sess) < MOMENTUM_BARS:
            details["reason"] = f"only {len(sess)} session bars available (need {MOMENTUM_BARS})"
            print(f"⚠️  {ticker} momentum: {details['reason']} — passing by default")
            _bump("fail_open")
            return True, details
        bars = sess[-(MOMENTUM_BARS + 2):]
        # session peak 1-min volume SO FAR (completed bars) — denominator for the peak-relative gate
        _sess_comp = sess[:-1] if len(sess) > 1 else sess
        session_peak_vol = max((float(b.get("volume") or b.get("v") or 0) for b in _sess_comp), default=0)
        details["session_peak_vol"] = int(session_peak_vol)

        recent = bars[-(MOMENTUM_BARS):]
        prior = bars[-(MOMENTUM_BARS + 1):-1] if len(bars) > MOMENTUM_BARS else recent[:-1]

        volumes = []
        for b in recent:
            v = float(b.get("volume") or b.get("v") or 0)
            volumes.append(v)
        # 7/11 audit A9: the HARD liquidity floor must average COMPLETED bars only — bars[-1] is in-progress
        # (this function's own topping-tail check says so), and its partial volume right after a minute roll
        # deflated the avg up to ~33% → nondeterministic false illiquid-rejects on liquid names. Unifies with
        # the universal-gate twin (already completed-only).
        _comp_vols = [float(b.get("volume") or b.get("v") or 0)
                      for b in (bars[:-1] if len(bars) > MOMENTUM_BARS else bars)][-MOMENTUM_BARS:]
        avg_vol = sum(_comp_vols) / len(_comp_vols) if _comp_vols else 0
        details["avg_vol"] = int(avg_vol)

        # ── HOMEGROWN thresholds (Kev's concept is "volume on the break", not these exact values). The accel /
        #    green-count flags stay OBSERVE-only (soft) per [[feedback_dry_run_learning]]. The LIQUIDITY FLOOR,
        #    however, GRADUATED to a HARD reject (7/7, observe-then-gate [[feedback_widen_within_kev_realm]]):
        #    the soft experiment ran and today's ONLY two low-avg-vol entries (INTS 2,015/bar, NXPL 1,811/bar)
        #    were BOTH dead-money losers (−$2.40 / −$1.17, time-stopped scratches) while ZERO of the 7 winners
        #    were low-vol-flagged. A thin stock isn't tradeable — Kev trades VOLUME, never sub-liquidity.
        #    [[feedback_grade_gates_vs_outcomes]] Tunable: lower MOMENTUM_MIN_AVG_VOL if it ever blocks a mover. ──
        soft = []
        if avg_vol < MOMENTUM_MIN_AVG_VOL:                          # LIQUIDITY FLOOR — HARD (thin stock = skip)
            # 8/6 SUPERSESSION (Marcos "build the share floor"; the PN 11:29 miss): shares are
            # price-blind — 5,748/bar of a $9.74 name is $56k/min of REAL liquidity, while 2,400
            # of SUGP was $5k. The ambient DOLLAR floor is the correct measure; when it passes,
            # the share floor is waived. When ambient data is missing both floors stand.
            _sf_ok, _sf_med, _sf_need = _ambient_dvol_ok(bars)
            if _sf_ok and _sf_med >= _sf_need > 0:
                print(f"💵 {ticker} share floor waived — ambient ${int(_sf_med):,}/min >= ${int(_sf_need):,} (dollar floor supersedes)")
            else:
                details["reason"] = f"illiquid — avg vol {int(avg_vol):,}/bar < {MOMENTUM_MIN_AVG_VOL:,} floor, skip"
                print(f"❌ {ticker} momentum FAIL: {details['reason']}")
                return False, details
        _am_ok, _am_med, _am_need = _ambient_dvol_ok(bars)           # 8/6 ambient floor (spike-proof)
        if not _am_ok:
            details["reason"] = (f"thin ambient tape — median ${int(_am_med):,}/min over prior 10 bars "
                                 f"< ${int(_am_need):,} exit floor ({AMBIENT_DVOL_MULT:g}x position cap)")
            print(f"❌ {ticker} momentum FAIL: {details['reason']}")
            return False, details

        prior_vols = [float(b.get("volume") or b.get("v") or 0) for b in prior]
        prior_avg = sum(prior_vols) / len(prior_vols) if prior_vols else 0
        current_vol = volumes[-1] if volumes else 0
        details["current_vol"] = int(current_vol)
        details["prior_avg_vol"] = int(prior_avg)
        # ── HARD volume gate (7/2 Kev-faithful REBUILD): the break must carry REAL, BUILDING volume — not
        #    "2× a fading local average" (which passed dead ducks: entries fired at a median 4% of the day's
        #    peak volume). Two parts, both on COMPLETED bars (never the partial in-progress bar[-1]):
        #      (a) BUILDING — break bar is a new local volume high vs the prior bars (Kev "successive candles
        #          closing strong on BUILDING volume", #024) = buyers stepping in.
        #      (b) PEAK-RELATIVE — break-bar vol ≥ PEAK_REL_MIN of the session's peak-so-far. A break on a
        #          fraction of the stock's OWN volume is the tired late continuation. Measured (83 breaks):
        #          <30% of peak won ~8%, ≥30% won ~27–36%; building won 27% vs 10%. Threshold homegrown-
        #          calibrated → tag revisit. [[feedback_grade_gates_vs_outcomes]] [[feedback_dry_run_learning]]
        comp = bars[:-1] if len(bars) > MOMENTUM_BARS + 1 else bars
        if len(comp) >= 2:
            brk_vol = float(comp[-1].get("volume") or comp[-1].get("v") or 0)
            pvs = [float(b.get("volume") or b.get("v") or 0) for b in comp[-(MOMENTUM_BARS + 1):-1]]
            pav = sum(pvs) / len(pvs) if pvs else 0
            expansion = (brk_vol / pav) if pav > 0 else 999.0        # contraction→EXPANSION (pop ÷ base)
            peak_rel  = (brk_vol / session_peak_vol) if session_peak_vol > 0 else 1.0
            # ── momentum as a TRAJECTORY, not a point (7/2). The break bar being big is a snapshot; Kev keys
            #    on momentum BUILDING. Measured (80 breaks): the pop-vs-base EXPANSION band is the real signal
            #    (<1.5× won 32% vs 1.5–3× 62%); "all building" (rising vol + higher-lows + ≥2× expansion) hit
            #    67% / +10.5% median run. HARD gate = expansion≥EXPANSION_MIN + peak-relative floor (both
            #    data-backed); the finer trajectory flags are OBSERVED (thin n=9) for conviction/sizing later. ──
            _vl = [float(b.get("volume") or b.get("v") or 0) for b in comp[-3:]]
            vol_rising  = len(_vl) >= 3 and _vl[-1] >= _vl[-2] >= _vl[-3]
            _lows = [float(b.get("low") or b.get("l") or 0) for b in comp[-(MOMENTUM_BARS + 1):]]
            higher_lows = len(_lows) >= 3 and _lows[-1] >= _lows[0]
            all_building = vol_rising and higher_lows and expansion >= 2.0
            details["break_accel"]  = round(expansion, 2)
            details["peak_rel_vol"] = round(peak_rel, 3)
            details["vol_rising"]   = vol_rising
            details["higher_lows"]  = higher_lows
            details["all_building"] = all_building
            if pvs and not (expansion >= EXPANSION_MIN and peak_rel >= PEAK_REL_MIN):
                details["reason"] = (f"no momentum build — {expansion:.1f}× base (<{EXPANSION_MIN}×) / "
                                     f"{peak_rel*100:.0f}% of peak (<{PEAK_REL_MIN*100:.0f}%) — volume not expanding, skip")
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
            soft.append(f"{green_count}/{len(check_bars)} green")

        # Kev "tail off the high" — do NOT enter into a candle that just got rejected at the highs. This is
        # a real Kev entry-avoidance rule (40+ videos) → the ONLY hard reject. (bars[-1] = in-progress.)
        if len(bars) >= 2 and is_topping_tail(bars[-2]):
            details["reason"] = "topping tail on last bar — rejection at the high, skip entry"
            print(f"❌ {ticker} momentum FAIL: {details['reason']}")
            return False, details

        details["passed"] = True
        details["soft_momentum"] = "; ".join(soft) or None
        if soft:
            print(f"⚠️  {ticker} soft momentum (OBSERVING, not blocking): {'; '.join(soft)}")
            _log_decision(ticker, "momentum_soft", note="; ".join(soft)[:120])
        else:
            print(f"✅ {ticker} momentum OK: avg vol {int(avg_vol):,}, "
                  f"current {int(current_vol):,}, {green_count} green bars")
        return True, details

    except Exception as e:
        print(f"⚠️  {ticker}: momentum check error: {e} — passing by default")
        _bump("fail_open")
        details["reason"] = str(e)
        return True, details


def _to_chronological(bars):
    """Return bars OLDEST-FIRST (chronological). The Webull SDK's get_history_bar delivers bars
    NEWEST-FIRST, but ALL downstream logic assumes oldest-first — i.e. bars[-1] is the most recent
    / in-progress bar (flat-top window = completed[-FLAT_TOP_WINDOW:], monitor_trade prev-bar exits
    = completed[-1]/[-2], EMA series, compute_room). That mismatch made the flat-top window read the
    OLDEST bars and the exits compare the open's bars (the 6/29 'open artifact' was the visible tip).
    Normalizing here fixes every caller at once and matches the backtest harness (which sorts ascending).
    Sort by the ISO-UTC 'time' string (lexically chronological); fall back to reversing the SDK order."""
    if not bars or not isinstance(bars, list):
        return bars
    try:
        if all(isinstance(b, dict) and b.get("time") for b in bars):
            return sorted(bars, key=lambda b: str(b.get("time")))
    except Exception:
        pass
    return list(reversed(bars))


def get_intraday_bars(ticker, count=30, executor=None, sessions=None):
    """Fetch 1-minute intraday bars for VWAP calculation. Uses SDK.

    The SDK call has no timeout — used inside monitor_trade (structure-based exits: prev-bar-low trail + topping-tail),
    so a hung call could freeze the loop (same class as the BOXL freeze). Run it on the shared
    worker with a hard QUOTE_TIMEOUT_SECS cap so it can never block the monitor loop.
    Pass executor=_aux_executor (e.g. the day-2 observer) to keep load OFF the trade pool."""
    try:
        if executor is _aux_executor and time.time() < _rest_cool[0]:
            return []   # 429 cooldown: optional consumers (day-2/sweep/session-vwap refresh) yield to monitors
        if BARS_SOURCE == "alpaca":               # #97 T3: same shape, full-day REST (A3 for 1-min)
            _ab = _alpaca_intraday_bars(ticker, count, sessions)
            if _ab:
                return _ab
            _bump("alp_bars_miss")                # empty → fall through to Webull (per-line degrade)
        dc = _get_data_client()
        if not dc:
            return []
        # sessions=None → RTH only (default, unchanged live behavior). Pass ["RTH","PRE","ATH"] to include
        # extended hours (pre/after-market) — used ONLY for the bar ARCHIVE (analysis), never the live VWAP/EMA path.
        _kw = {"symbol": ticker, "category": "US_STOCK", "timespan": "M1", "count": str(count)}
        if sessions:
            _kw["trading_sessions"] = sessions
        future = (executor or _quote_executor).submit(dc.market_data.get_history_bar, **_kw)
        try:
            resp = future.result(timeout=QUOTE_TIMEOUT_SECS)
        except concurrent.futures.TimeoutError:
            print(f"⚠️  Intraday bars TIMEOUT for {ticker} (>{QUOTE_TIMEOUT_SECS}s) — returning none")
            _bump("timeouts")
            return []
        if resp.status_code != 200:
            print(f"⚠️  Intraday bars {resp.status_code} for {ticker}")
            _bump("api_429" if resp.status_code == 429 else "api_err")
            if resp.status_code == 429:   # 7/14: back off instead of hammering — shed AUX load first
                _rest_cool[0] = min(max(_rest_cool[0], time.time()) + 30, time.time() + 120)
            return []
        raw = resp.json()
        if isinstance(raw, list):
            bars = raw
        else:
            data = raw.get("data", {}) if isinstance(raw, dict) else {}
            if isinstance(data, list):
                bars = data
            elif isinstance(data, dict):
                bars = data.get("items", [])
            else:
                bars = []
        return _to_chronological(bars)
    except Exception as e:
        print(f"⚠️  Intraday bars error for {ticker}: {e}")
        _bump("api_err"); _bump("fail_open")   # 7/14: connection-resets landed here UNCOUNTED during an active fail-open
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


def _latest_session(bars):
    """Keep only the LATEST trading day's bars (by the ISO-UTC 'time' date). The SDK's count-based M1
    fetch BACKFILLS prior days once the current session is incomplete (verified: count=390 spans ~2 days
    for most of the session, count=800 spans 3), so session stats like VWAP must NOT run across the day
    boundary — otherwise the 'above VWAP' entry gate is computed on a multi-day average (a real bug)."""
    if not bars:
        return bars
    last_day = str(bars[-1].get("time") or "")[:10]
    if not last_day:
        return bars
    same = [b for b in bars if str(b.get("time") or "").startswith(last_day)]
    return same or bars


def _today_utc_date() -> str:
    """Today's date (YYYY-MM-DD) in UTC — bar 'time' fields are ISO-UTC, so the day key must be too.
    (An ET session always lives inside one UTC date: 9:30am–8pm ET = 13:30–24:00 UTC.)"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _fresh_session(bars, today=None, max_stale_secs=900):
    """B14/B16 choke point (7/15): _latest_session is DATE-BLIND — in the first minutes of RTH a
    count-based fetch can return ONLY prior-day bars (verified live: XCUR 9:33), and 'latest session'
    silently becomes YESTERDAY. Yesterday's closes then hit fresh stops (B14 false instant stop ×2)
    and yesterday's VWAP gates today's entries (B16 phantom VWAP). This wrapper requires the latest
    session to BE TODAY and the newest bar to be recent; otherwise it returns [] — and every caller
    must treat no-data as NO DECISION, never as a decision on stale data."""
    sess = _latest_session(bars)
    if not sess:
        return []
    if str(sess[-1].get("time") or "")[:10] != (today or _today_utc_date()):
        return []
    if max_stale_secs is not None:
        try:
            # SDK time formats vary ('...Z', '...+0000', '....000+0000') — the first 19 chars
            # are always 'YYYY-MM-DDTHH:MM:SS' in UTC, so parse exactly that and attach UTC.
            newest = datetime.strptime(str(sess[-1].get("time") or "")[:19],
                                       "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - newest).total_seconds() > max_stale_secs:
                return []
        except (ValueError, TypeError):
            return []
    return sess


def _stop_close_qualifies(bar, entry_ts, today=None) -> bool:
    """B14 contract: a completed-bar close may only trigger the stop if the bar is from TODAY and
    closed AFTER the entry existed. A close that predates the entry is pre-breakout history — on any
    fresh breakout it sits below the new stop BY CONSTRUCTION (the base is below the stop)."""
    t = str(bar.get("time") or "")
    if t[:10] != (today or _today_utc_date()):
        return False
    return t[:19] > str(entry_ts)[:19]


def _blind_stop_should_fire(now, last_bars_ok, below_since, fetch_failures,
                            blind_secs=None, below_secs=None) -> bool:
    """B11 predicate, fixed for B15 (7/15): 'blind' must mean fetches are FAILING, not 'a fetch isn't
    due yet'. The healthy jittered cadence is 48–72s, so a pure-time threshold of 60s made the tail of
    every healthy cycle 'blind' and B11 fired intrabar on any 20s-sustained breach (accidental
    breach-mode — refuted 7/14, −2.08R net). Requires BOTH ≥2 consecutive fetch failures AND ≥150s
    since bars were last seen (NVVE's real blindness was ~360s — still caught 2.4× sooner)."""
    _blind = B11_BLIND_SECS if blind_secs is None else blind_secs
    _below = B11_BELOW_SECS if below_secs is None else below_secs
    return (fetch_failures >= 2
            and now - last_bars_ok >= _blind
            and below_since > 0
            and now - below_since >= _below)


_held_claim_lock = threading.Lock()
_held_claims: set = set()

def _claim_ticker(ticker) -> bool:
    """B3 utility — NOT YET WIRED (7/15). The XCUR 9:33 "double entry" was NOT a lock race:
    reading the actual flow, trade #1 was instant-killed by B14 (yesterday's close ≤ fresh stop),
    completed, and released held per the by-design re-entry rules; #2 was a legitimate re-trigger
    20s later. Sequential, never concurrent — the single-threaded scan loop marks held under
    trade_lock before workers spawn, so no claim race exists today. Kept (tested, rig T4) for
    B3-proper: per-trade keying when same-day re-entries share the (date,ticker) open-trade key."""
    with _held_claim_lock:
        if ticker in _held_claims:
            return False
        _held_claims.add(ticker)
        return True

def _release_ticker(ticker):
    with _held_claim_lock:
        _held_claims.discard(ticker)


def aggregate_bars(bars, minutes=SETUP_TF_MIN):
    """Roll 1-min bars (oldest-first, each with an ISO-UTC 'time') into N-minute OHLCV bars, clock-aligned
    to the N-min grid. Kev's SETUPS come from the 3-min chart (#215); the 1-min is only entry timing + risk.
    Webull has no M3 timespan, so we roll our own from the M1 we already fetch (no extra API call). Output
    bars carry full-name OHLCV keys + 'time' so every existing reader (b.get('high') or b.get('h')) works.
    Buckets are keyed by DATE + grid-slot, so the overnight gap never merges two days into one bar."""
    def _f(b, *keys):
        for k in keys:
            v = b.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        return 0.0
    def _bucket(b):
        t = str(b.get("time") or "")
        try:
            total = int(t[11:13]) * 60 + int(t[14:16])   # minute-of-day from ISO 'YYYY-MM-DDTHH:MM...'
            return t[:10] + "#" + str(total // minutes)
        except (ValueError, IndexError):
            return None
    out, key, cur = [], None, None
    for b in bars or []:
        k = _bucket(b)
        if k is None:
            continue
        o, h, l, c, v = _f(b, "open", "o"), _f(b, "high", "h"), _f(b, "low", "l"), _f(b, "close", "c"), _f(b, "volume", "v")
        if k != key:
            if cur:
                out.append(cur)
            key, cur = k, {"time": b.get("time"), "open": o, "high": h, "low": l, "close": c, "volume": v}
        else:
            cur["high"] = max(cur["high"], h)
            if l > 0:
                cur["low"] = min(cur["low"], l) if cur["low"] > 0 else l
            cur["close"] = c
            cur["volume"] += v
    if cur:
        out.append(cur)
    return out


def _bar_et_min(bar):
    """ET minute-of-day (0–1439) for a bar's ISO-UTC 'time'; None on parse failure. Anchors the
    opening-range window (9:30–9:35 ET = 570–575) correctly regardless of the UTC offset / DST."""
    t = str(bar.get("time") or "")
    try:
        iso = t.replace("Z", "+00:00")
        if len(iso) >= 6 and iso[-5] in "+-" and iso[-3] != ":":   # '+0000' → '+00:00' (fromisoformat <3.11)
            iso = iso[:-2] + ":" + iso[-2:]
        et = datetime.fromisoformat(iso).astimezone(EASTERN)
        return et.hour * 60 + et.minute
    except Exception:
        return None


def opening_range(session_bars):
    """Kev's OPENING RANGE = the high/low of the first 5 min of RTH (9:30–9:35 ET), the base for his
    5-min opening-range-breakout (#275/#064). Returns (hi, lo) or None if that window isn't present yet.
    Anchored to 9:30 ET so premarket bars (if any) never leak into the range."""
    ors = []
    for b in session_bars or []:
        m = _bar_et_min(b)
        if m is not None and 570 <= m < 575:   # 9:30:00 – 9:34:59 ET
            ors.append(b)
    if not ors:
        return None
    hi = max(float(b.get("high") or b.get("h") or 0) for b in ors)
    los = [float(b.get("low") or b.get("l") or 0) for b in ors]
    los = [x for x in los if x > 0]
    lo = min(los) if los else 0
    return (hi, lo) if hi > 0 and lo > 0 else None


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


# ── Room-to-next-supply primitive (Kev is the bible: enter only with ≥2:1 room) ───────────
def _bar_high(b):  return float(b.get("high")  or b.get("h") or b.get("close") or b.get("c") or 0)
def _bar_low(b):   return float(b.get("low")   or b.get("l") or b.get("close") or b.get("c") or 0)
def _bar_open(b):  return float(b.get("open")  or b.get("o") or b.get("close") or b.get("c") or 0)
def _bar_close(b): return float(b.get("close") or b.get("c") or 0)

def _pivot_highs(bars, window=PIVOT_WINDOW):
    """Swing highs = a bar whose high tops the `window` bars on each side (a real local peak =
    a level where price topped and reversed = supply). What Kev marks by eye."""
    highs = [_bar_high(b) for b in bars]
    peaks = []
    for i in range(window, len(highs) - window):
        h = highs[i]
        if h <= 0:
            continue
        if h == max(highs[i - window:i + window + 1]) and h > highs[i - 1] and h > highs[i + 1]:
            peaks.append(h)
    return peaks

def _topping_tail_highs(bars):
    """Highs of topping-tail candles — where a big upper wick shows sellers rejected the high (supply).
    Uses the canonical is_topping_tail() (defined below; resolved at call time)."""
    out = []
    for b in bars:
        if is_topping_tail(b):
            out.append(_bar_high(b))
    return out

def _round_levels_above(price, n=8):
    """Whole + half-dollar levels above price — Kev treats round numbers ($1, $1.50, $3...) as resistance."""
    out = []
    x = int(price * 2) / 2 + 0.5          # next half-dollar (int() = floor for positive prices)
    for _ in range(n):
        if x > price:
            out.append(round(x, 2))
        x += 0.5
    return out

def get_daily_levels(ticker):
    """Kev's room/daily-first reference levels come from the DAILY chart, not intraday minute bars
    ("all you do to find range is use these past highs on the daily chart" #057). Fetch ~200 daily bars
    (timespan='D') ONCE per ticker per session (daily data is static intraday) → daily 20/50/200 SMA,
    daily swing-(reaction)-highs, prior-day high. Returns None on any failure → caller FAILS OPEN
    (a data hiccup must never block a trade — [[feedback_kev_is_the_bible]] verify code, never halt on a bug)."""
    try:
        items = None
        if DAILY_SOURCE == "alpaca":       # #97 T6: Alpaca daily; None → Webull fallthrough (per-line degrade)
            items = _alpaca_daily_items(ticker)
        if items is None:
            dc = _get_data_client()
            if not dc:
                return None
            resp = None
            for _attempt in range(3):      # retry on 429 — daily is fetched for ~15 names; bursts rate-limit
                resp = dc.market_data.get_history_bar(symbol=ticker, category="US_STOCK", timespan="D", count="200")
                if resp.status_code == 200:
                    break
                if resp.status_code == 429:
                    _bump("api_429")
                    time.sleep(0.6 * (_attempt + 1))
                    continue
                return None
            if not resp or resp.status_code != 200:
                return None
            raw = resp.json()
            # Webull get_history_bar returns {"data": {"items": [...]}} OR {"data": [...]} OR a top-level
            # list — match the two existing parsers in this file (M15 ~1787, M1 ~2059) so the daily feed
            # can't silently parse to [] and disable the gate.
            if isinstance(raw, list):
                items = raw
            else:
                data = raw.get("data", {}) if isinstance(raw, dict) else {}
                items = data.get("items", data) if isinstance(data, dict) else data
        bars = []
        for b in (items or []):
            try:
                bars.append({"h": float(b.get("high")), "c": float(b.get("close")),
                             "t": str(b.get("time") or b.get("tradeTime") or "")[:10]})
            except (TypeError, ValueError):
                continue
        if len(bars) < 20:
            return None
        bars.sort(key=lambda z: z["t"])
        closes = [b["c"] for b in bars]
        def _sma(n):
            return (sum(closes[-n:]) / n) if len(closes) >= n else None
        hs = [b["h"] for b in bars]
        reaction = [hs[i] for i in range(3, len(hs) - 3)
                    if hs[i] == max(hs[i - 3:i + 4]) and hs[i] > hs[i - 1] and hs[i] > hs[i + 1]]
        # Prior-day high = last COMPLETED trading day (date strictly < today). bars[-2] is only "yesterday"
        # when the fetch INCLUDES today's forming daily bar; if the SDK returns completed days only, bars[-2]
        # is the day-BEFORE-yesterday = off by one. Picking the last bar dated < today gives yesterday either way.
        _today = datetime.now(EASTERN).strftime("%Y-%m-%d")
        _prior = [b for b in bars if b["t"] and b["t"] < _today]
        _pdh = _prior[-1]["h"] if _prior else (bars[-2]["h"] if len(bars) >= 2 else None)
        _pdc = _prior[-1]["c"] if _prior else (bars[-2]["c"] if len(bars) >= 2 else None)
        # 7/28 P0-2 STALENESS GUARD: a "prior day" older than 5 calendar days is a vendor gap
        # (the truncation class, or a future one) — a stale base makes day_gain FICTION (DFNS
        # 8357%). No data beats wrong data (B16): drop the prior-day refs, keep the SMAs/highs.
        if _prior:
            _age = (datetime.strptime(_today, "%Y-%m-%d") - datetime.strptime(_prior[-1]["t"], "%Y-%m-%d")).days
            if _age > 5:
                print(f"⚠️  {ticker} daily series STALE — last completed day {_prior[-1]['t']} "
                      f"({_age}d old): prior-day close/high dropped (day_gain will not stamp)")
                _pdh = _pdc = None
        return {"m20": _sma(20), "m50": _sma(50), "m200": _sma(200),
                "reaction_highs": reaction,
                "prior_day_high": _pdh,
                "prior_day_close": _pdc}   # DAY-GAIN FLOOR reference (7/22): gain vs last completed day
    except Exception as e:
        print(f"⚠️  daily-levels error {ticker}: {e} — failing open (room gate degraded for this name)")
        return None

def daily_first_ok(price, daily):
    """Kev's daily-first veto (#067, verbatim): 'If the daily is bad, I will not take the trade... You're
    right here beneath the 20 and 50 moving average. Don't play this.' → price must be ABOVE the daily 20
    AND 50 MA. None/insufficient daily data → True (fail open — never block on a data error)."""
    if not daily:
        return True
    m20, m50 = daily.get("m20"), daily.get("m50")
    if m20 and m50:
        return price > m20 and price > m50
    return True

def find_next_supply(bars, current_price, daily=None, premarket_high=None, prior_day_high=None):
    """Kev's 'next supply' = the nearest SIGNIFICANT level on the DAILY chart: prior daily reaction highs,
    the daily 20/50/200 MA, whole/half-dollar levels, the premarket high, the prior-day high — NOT the
    intraday HOD or 1-minute swing pivots. (The old intraday-pivot version WAS the bug: it called the level
    price was *breaking* the "supply" and rejected every continuation into new highs — 84% false on CUPR
    6/30. Grounded to Kev #057/#068/#027/#021; see [[project_kev_grounding]].) Returns (level, source), or
    NOTE: a round-number level is almost always present above (Kev steps through whole/half dollars as
    resistance — #023 'I don't buy beneath the whole dollar, I wait for the break'), so (None,'open') =
    rr-999 open room is RARE and only fires when literally nothing is overhead."""
    if current_price <= 0:
        return None, "unknown"
    floor = current_price * (1 + SUPPLY_MIN_DIST_PCT)   # ignore levels basically AT price
    levels = []
    if premarket_high and premarket_high >= floor: levels.append((float(premarket_high), "pm_high"))
    if prior_day_high and prior_day_high >= floor: levels.append((float(prior_day_high), "pd_high"))
    if daily:
        for h in daily.get("reaction_highs", []):
            if h >= floor: levels.append((float(h), "daily_high"))
        for key, src in (("m20", "d20MA"), ("m50", "d50MA"), ("m200", "d200MA")):
            v = daily.get(key)
            if v and v >= floor: levels.append((float(v), src))
        pdh = daily.get("prior_day_high")
        if pdh and pdh >= floor: levels.append((float(pdh), "pd_high"))
    for lvl in _round_levels_above(current_price):
        if lvl >= floor: levels.append((lvl, "level"))
    if not levels:
        return None, "open"                              # nothing overhead at all (rare) = open room
    levels.sort(key=lambda x: x[0])
    return round(levels[0][0], 4), levels[0][1]          # nearest SIGNIFICANT level overhead   # nearest overhead = the cap on the trade

def compute_room(entry_price, stop_loss, bars, daily=None, premarket_high=None, prior_day_high=None):
    """Kev's gate: room to the next SIGNIFICANT supply (daily levels / round numbers) ÷ risk to support.
    rr=999 (open room) only when nothing at all is overhead — rare. ANY failure returns rr=None so the caller FAILS OPEN — a code glitch
    in the detector must never halt trading (per feedback_kev_is_the_bible: verify our code, never block on a bug)."""
    try:
        risk = entry_price - stop_loss
        supply, src = find_next_supply(bars, entry_price, daily, premarket_high, prior_day_high)
        if src == "unknown":
            return {"next_supply": None, "supply_src": "unknown", "room_pct": None, "rr_to_supply": None, "risk": round(risk, 4)}
        if supply is None:                              # nothing overhead (rare) → open room (JSON-safe sentinel)
            return {"next_supply": None, "supply_src": "open", "room_pct": None, "rr_to_supply": 999.0, "risk": round(risk, 4)}
        room = supply - entry_price
        rr = (room / risk) if risk > 0 else 0.0
        return {"next_supply": supply, "supply_src": src,
                "room_pct": round(room / entry_price * 100, 2),
                "rr_to_supply": round(rr, 2), "risk": round(risk, 4)}
    except Exception as e:
        print(f"⚠️  compute_room error ({e}) — failing OPEN (room unknown)")
        return {"next_supply": None, "supply_src": "unknown", "room_pct": None, "rr_to_supply": None, "risk": 0}


def _bar_vol(b): return float(b.get("volume") or b.get("v") or 0)

def detect_ma_pullback(completed, price):
    """Kev's pullback entry off WHICHEVER rising MA the pullback holds (9/20/50/90). Faithful to the
    bible: uptrend (the MA stack) → price dips to a rising MA → a candle WICKS OFF THE LOW and CLOSES
    BACK ABOVE that MA ("a buyer stepped in") → weak pullback, buyers return, price continuing up.
    Risk off the DEEPEST support the low actually reached and held. Returns {ma_name, ma, stop} or None.
    Any error returns None (no entry) — a detector bug must never crash the scan loop."""
    try:
        return _detect_ma_pullback(completed, price)
    except Exception as e:
        print(f"⚠️  detect_ma_pullback error ({e}) — no entry this pass")
        return None

def _detect_ma_pullback(completed, price):
    closes = _extract_closes(completed)
    if len(closes) < 25:
        return None
    ema9 = _calc_ema(closes, EMA_PERIOD)
    ema20 = _calc_ema(closes, EMA20_PERIOD)
    if not (ema9 > ema20 > 0):           # uptrend = the MA STACK (fast above slow). NOT price>ema20 —
        return None                      # a deep pullback to the 50/90 IS below the 20. VWAP is the floor (wiring).
    conf = completed[-1]
    chi, clo, cop, ccl = _bar_high(conf), _bar_low(conf), _bar_open(conf), _bar_close(conf)
    rng = chi - clo
    if rng <= 0:
        return None
    # BROADENED (7/2): confirmation = a bottoming WICK ≥ ratio (a buyer stepped in) OR a GREEN reclaim (close >
    # open = buyers back). Was wick-ONLY (fired ~3×/4 days — too strict); the winners' pullbacks reclaim support
    # green without always printing a 40% wick. The held-MA check below still requires closing back above a RISING MA.
    _wick_ok = (min(cop, ccl) - clo) / rng >= BOTTOM_TAIL_RATIO
    _green   = ccl > cop
    if not (_wick_ok or _green):
        return None
    if price <= ccl:                                      # must be continuing UP off the confirmation candle
        return None
    vol_conf = _bar_vol(conf)
    vol_prior = sum(_bar_vol(b) for b in completed[-4:-1]) / 3 if len(completed) >= 4 else 0
    if vol_prior > 0 and vol_conf < vol_prior * EMA_BOUNCE_VOL_MULT:   # buyers must return > the weak pullback
        return None
    # The support held = every rising MA whose level the low REACHED and the candle CLOSED back above.
    # Risk off the DEEPEST of them (lowest value = where the buyer actually stepped in / the wick low),
    # so the stop sits below the wick, not inside it.
    held = []
    for period in MA_PULLBACK_LEVELS:                     # 9, 20, 50, 90
        ma = _calc_ema(closes, period)
        if ma <= 0:
            continue
        ma_prev = _calc_ema(closes[:-MA_RISING_LOOKBACK], period) if len(closes) > period + MA_RISING_LOOKBACK else 0
        rising = ma_prev <= 0 or ma > ma_prev
        if clo <= ma * (1 + MA_PULLBACK_TOUCH_TOL) and ccl > ma and rising:   # low reached it, closed above, rising
            held.append((ma, period))
    if not held:
        return None
    ma, period = min(held, key=lambda x: x[0])           # deepest support the low reached and held
    # Risk off the LOW where the buyer stepped in: just below the lower of the MA and the wick low,
    # so the stop is never inside the wick (Kev risks off the candle low / the level held).
    return {"ma_name": f"ema{period}", "ma": round(ma, 4),
            "stop": round(min(ma, clo) * (1 - MA_PULLBACK_STOP_BUFFER), 4)}


def detect_bounce(completed, price):
    """Kev #28 MEAN-REVERSION BOUNCE: an overextended-to-the-DOWNSIDE former runner (ran big, round-tripped)
    reclaims a demand level — a double-bottom / the 20 EMA — on a bottoming-wick + green + returning volume →
    buyers stepped back in → enter, RISK THE LOW, target the prior HOD. Distinct from the front-side pullback:
    this is a REVERSAL off a dump (NOT gated on above-VWAP). Any error → None (never crash the scan)."""
    try:
        closes = _extract_closes(completed)
        if len(closes) < 25:
            return None
        highs = [_bar_high(b) for b in completed]
        lows  = [_bar_low(b)  for b in completed]
        hod = max(highs) if highs else 0
        base0 = _bar_close(completed[0]) or (closes[0] if closes else 0)
        if hod <= 0 or base0 <= 0:
            return None
        ran = (hod - base0) / base0                          # ran big earlier (a former runner)
        cur = _bar_close(completed[-1])
        drawdown = (hod - cur) / hod if hod > 0 else 0        # round-tripped off the high
        if ran < BOUNCE_MIN_RUN or drawdown < BOUNCE_MIN_DD:
            return None
        conf = completed[-1]
        chi, clo, cop, ccl = _bar_high(conf), _bar_low(conf), _bar_open(conf), _bar_close(conf)
        rng = chi - clo
        if rng <= 0:
            return None
        if (min(cop, ccl) - clo) / rng < BOTTOM_TAIL_RATIO or ccl <= cop:   # bottoming wick + green reclaim
            return None
        if price <= ccl:                                     # continuing up off the bounce candle
            return None
        vol_conf  = _bar_vol(conf)
        vol_prior = sum(_bar_vol(b) for b in completed[-4:-1]) / 3 if len(completed) >= 4 else 0
        if vol_prior > 0 and vol_conf < vol_prior * EMA_BOUNCE_VOL_MULT:     # volume must RETURN on the bounce
            return None
        # demand level: a DOUBLE-BOTTOM (bounce low near a RECENT swing low — NOT the day's absolute low) OR the 20 EMA
        recent_lows = [l for l in lows[-10:-2] if l > 0]     # the recent bottom the dump made, for the double-bottom
        dbl = any(abs(clo - pl) / pl < 0.03 for pl in recent_lows)
        ema20 = _calc_ema(closes, EMA20_PERIOD)
        near20 = ema20 > 0 and abs(clo - ema20) / ema20 < 0.03
        if not (dbl or near20):
            return None
        return {"stop": round(clo * 0.99, 4), "target": round(hod, 4),   # risk the low, target prior HOD
                "kind": "double_bottom" if dbl else "ema20"}
    except Exception:
        return None


# ── KEV 3-GATE RECLAIM (7/19, Marcos: "This entry requires volume and the most consistent time of
# day that provides that volume is early in the trading day. I want this installed for only
# 9:30-11:00 and shadow it the rest of the trading day.")
# Ported VERBATIM from the kill-tested detector (3 days of 10s tape: the 09:30–11:00 window scored
# +$84.09/21 fires 62% WR; post-11:00 −$62.50/10 → LIVE window + all-day shadow logging).
# Grammar (canon rAPtKlH4Oh0 / zlEn-4uD82k): G1 close crosses ABOVE the session line on ≥2× rolling
# 10s volume then EXTENDS ≥1% over it; G2 pullback low tags the line (≤+0.5%) WITHOUT losing it
# (close ≥ vwap×0.99) and prints a BOTTOMING WICK (close in the bar's upper half); G3 next close
# ABOVE the wick bar's high = entry, risk = min(wick low, vwap), 7% cap. ONE fire per name per day.
# Inputs = the kill-test's exact inputs: the bot's in-process 10s stream bars (B12 Phase 1) + the
# recorder session VWAP (premarket-anchored, midpoint-repaired). RECLAIM_KEV=0 disables reclaim
# entries entirely — the naive 1-gate detector below is RETIRED (era class: −$228.81 / 32 trades).
RECLAIM_KEV        = os.environ.get("RECLAIM_KEV", "1") == "1"
RECLAIM_LIVE_START = os.environ.get("RECLAIM_LIVE_START", "09:30")
RECLAIM_LIVE_END   = os.environ.get("RECLAIM_LIVE_END", "11:00")
_reclaim_st: dict = {}        # sym -> state machine (daily-keyed inside)
_reclaim_cursor: dict = {}    # (day, sym) -> last processed 10s bucket epoch
# ── STALE-FIRE GUARD (7/28, Fable-ruled after the LVWR 07:27 trace): a restart (ours or
#    RAILWAY'S) or a newly-admitted ticker replays up to 15 min of 10s bars into the curl
#    machines. Replay is GOOD — the state machines need history to find in-progress setups —
#    but FIRING on an old bar converts a finished event into a live entry at a price the setup
#    no longer supports (LVWR: fired 07:27 on a ~15-min-old reclaim, logged 2.79 vs a 2.92
#    signal). Rule: detect on any bar, FIRE only on a fresh one. 90s (not 60) — the scan cycle
#    itself runs 48–72s jittered (B15), so 60 could suppress legit fires in a slow cycle.
#    Suppressions are consumed (state resets exactly as a fire would) + LOGGED — the guard's
#    cost must be visible from day one. Cursor seeding was considered and REJECTED (it would
#    skip state-building and lose in-progress setups for every newcomer).
CURL_FIRE_MAX_AGE_SECS = float(os.environ.get("CURL_FIRE_MAX_AGE_SECS", "90"))

# ── 7/29 P0-B (Fable-approved): the stale-price swap (a4fe777) is REBUILT. The old rule —
# stream-vs-fire-bar divergence >2% ⇒ "stream is stale" ⇒ trade the bar price — is FALSE in RTH,
# where that divergence is MOMENTUM (7/29: NCRA entered 2.3% and AMIX 8.2% above the live tape;
# MSS swapped DOWNWARD −4.4% — it injects noise both ways). Divergence is not staleness.
# New rule: substitution is allowed ONLY when (a) session is PREMARKET (RTH quote infrastructure
# is live — get_price serves a fresh tick or a synchronous REST quote, both trustworthy), AND
# (b) our OWN last stream tick for the symbol is old/absent (local arrival age — no vendor
# timestamp trust), AND (c) the fire bar itself is fresh. SWAP_MODE=off disables all substitution;
# =legacy restores the old divergence rule (rollback only). Independent of every lane flag —
# verified 7/29: the swap block sits ABOVE the lane gates, so lane flags never disarm it.
SWAP_MODE       = os.environ.get("SWAP_MODE", "pm_stale").strip().lower()   # off | pm_stale | legacy
QUOTE_MAX_AGE_S = float(os.environ.get("QUOTE_MAX_AGE_S", "15"))
# 8/4 DXST surgery knobs (see _swap_price_ok / _bucket_fresh): cross-source agreement required
# before any price substitution; PRE fire-age ceiling tighter than RTH.
SWAP_XSRC_MAX_PCT     = float(os.environ.get("SWAP_XSRC_MAX_PCT", "3.0"))
CURL_FIRE_MAX_AGE_PRE = float(os.environ.get("CURL_FIRE_MAX_AGE_PRE", "60"))

def _stream_tick_age(sym):
    """Seconds since the last stream tick we RECEIVED for sym (local arrival clock).
    None = no tick ever arrived. Never raises."""
    try:
        with _price_lock:
            rec = _price_registry.get(str(sym).upper())
        if isinstance(rec, dict) and rec.get("t"):
            return time.time() - float(rec["t"])
    except Exception:
        pass
    return None

def _swap_price_ok(sym, stream_px, bar_px, bar_k, hm=None):
    """May the conversion substitute bar_px for stream_px? Returns (allowed, reason).
    The caller logs either way — every substitution AND every refusal leaves a row."""
    try:
        if SWAP_MODE == "off":
            return False, "swap_off"
        if not (bar_px and bar_px > 0):
            return False, "no_bar_px"
        if SWAP_MODE == "legacy":
            return True, "legacy"
        _hm = hm or datetime.now(EASTERN).strftime("%H:%M")
        if _hm >= "09:30":
            return False, "rth_quote_trusted"
        age = _stream_tick_age(sym)
        if age is not None and age <= QUOTE_MAX_AGE_S:
            return False, "tick_fresh"
        if not _bucket_fresh(bar_k):
            return False, "bar_stale_too"
        # ── 8/4 DXST SURGERY part 1: SWAP-PROOF cross-source check. DXST 04:14 −$39.68: the
        # swap replaced a stale stream quote (3.03) with a STALER bar (3.34) and the drift
        # guard then compared the entry against ITSELF (drift=0 by construction). Rule: the
        # substitute must agree with the OTHER source within SWAP_XSRC_MAX_PCT — a stale tick
        # is still evidence about the price's neighborhood; a 10% disagreement means one of
        # them is lying, and we don't trade on a liar either way.
        try:
            with _price_lock:
                _rec = _price_registry.get(str(sym).upper())
            _tick_px = float(_rec.get("p") or 0) if isinstance(_rec, dict) else 0.0
        except Exception:
            _tick_px = 0.0
        if _tick_px > 0 and abs(bar_px - _tick_px) / _tick_px * 100.0 > SWAP_XSRC_MAX_PCT:
            return False, f"xsrc_divergence({bar_px}vs{_tick_px})"
        return True, "pm_quote_stale"
    except Exception:
        return False, "swap_guard_error"

# ── 8/5 HALT-AWARE CLOCKS (dip_rip autopsy: YXT's resumption watch expired MID-HALT twice;
# a mid-ladder fire was killed at "240.6s old" when 200+ of those seconds were a halt).
# Halted time doesn't count against staleness: _halt_credit[sym] accumulates completed
# >120s inter-bar gaps (minus the normal 10s cadence), fed from the curl feed. Effective
# age = wall age − credit accrued since the fire. No gate is bypassed — the clocks just
# stop while the exchange has the stock frozen. ──
_halt_credit: dict = {}    # sym -> [(gap_end_epoch, gap_secs), ...] today

def _halt_credit_note(sym, prev_k, new_k):
    try:
        gap = float(new_k) - float(prev_k)
        if gap > 120:
            _halt_credit.setdefault(sym, []).append((float(new_k), gap - 10.0))
            if len(_halt_credit[sym]) > 40: _halt_credit[sym] = _halt_credit[sym][-40:]
    except Exception:
        pass

def _halted_secs_since(sym, k):
    try:
        return sum(g for end, g in _halt_credit.get(sym, []) if end > float(k))
    except Exception:
        return 0.0

_vwap_warned: dict = {}   # 8/5: dedupe "VWAP unavailable" spam — one line per name per 30min
def _vwap_warn_ok(sym):
    try:
        now = time.time()
        if now - _vwap_warned.get(sym, 0) > 1800:
            _vwap_warned[sym] = now
            return True
        return False
    except Exception:
        return True

def _bucket_fresh(k, hm=None, sym=None):
    """True when 10s bucket epoch `k` is recent enough to ACT on (fire). 0/None never fresh.
    8/4 DXST SURGERY part 2: PRE gets its OWN, tighter ceiling (CURL_FIRE_MAX_AGE_PRE).
    8/5 HALT-AWARE: when sym is given, halted seconds since k don't count against the age."""
    try:
        _lim = CURL_FIRE_MAX_AGE_SECS
        _hm = hm or datetime.now(EASTERN).strftime("%H:%M")
        if _hm < "09:30":
            _lim = min(_lim, CURL_FIRE_MAX_AGE_PRE)
        _age = time.time() - float(k)
        if sym:
            _age -= _halted_secs_since(sym, k)
        return bool(k) and _age <= _lim
    except Exception:
        return False

def _log_stale_fire(sym, lane, k, px):
    """Visible-cost canary for every suppressed stale fire. Never raises."""
    try:
        _age = round(time.time() - float(k), 1) if k else None
        print(f"⏳ {sym} {lane} fire SUPPRESSED — bar {_age}s old > {CURL_FIRE_MAX_AGE_SECS:.0f}s "
              f"(replay after restart/admission); setup consumed, not traded")
        _log_decision(sym, "stale_fire_suppressed", lane=lane, bar_age_s=_age, px=px)
    except Exception:
        pass

# ── 7/24 CURL LIVE-SLOT FIX (Marcos: "we were shadowing for premarket NOT RTH") ──
# The old rule was seq==0 = the day's first fire gets the live slot — but the premarket seed (#98)
# started the machines at 4am, so premarket fires BURNED the slot before trades could even open
# (the code's own "KNOWN LIMITATION"). New rule: the live slot belongs to the FIRST fire AT/AFTER
# 09:30, consumed only when a trade is actually QUEUED. Premarket fires are evidence, never burners.
_curl_rth_n: dict = {}        # (day, sym, lane) -> live conversions taken

# ── 8/5 LEADER AMMO ("meritocracy — to the winners go the extra bullets", Marcos, after
# YXT 6->16 and JLHL 7.66->15 ran on spent ammo; counterfactual leader_ammo 27 starved setups
# = +$634.96, formula-v2 backlabel armed 26/27 = +$624.96). A name that has PROVEN itself today
# — day gain >= LEADER_GAIN_MIN and violence (halt today, or >=3 fresh-high minutes in a
# rolling 10) — is a LEADER for the rest of the session (sticky). Leaders earn: curl-lane
# session slots 1 -> LEADER_CURL_SLOTS, hidden cap bypass, ignition refires up to
# LEADER_IGNITION_CAP. The FIELD keeps every cap (cap-merit 8/3: blanket relief = 0/24 −$543).
# Every relief use is stamped leader_ammo=True. Kill switch: LEADER_AMMO=0.
LEADER_AMMO         = os.environ.get("LEADER_AMMO", "1") == "1"
LEADER_GAIN_MIN     = float(os.environ.get("LEADER_GAIN_MIN", "40"))
LEADER_IGNITION_CAP = int(os.environ.get("LEADER_IGNITION_CAP", "3"))
LEADER_CURL_SLOTS   = int(os.environ.get("LEADER_CURL_SLOTS", "3"))
_leader_day: dict = {}     # (day, sym) -> {"gain": bool, "viol": str|None, "since": "HH:MM"}

def _leader_rec(sym):
    day = datetime.now(EASTERN).strftime("%Y-%m-%d")
    return _leader_day.setdefault((day, sym), {"gain": False, "viol": None, "since": None,
                                               "hi": 0.0, "hi_marks": []})

def _leader_qualify(sym, rec):
    if rec["since"] is None and rec["gain"] and rec["viol"]:
        rec["since"] = datetime.now(EASTERN).strftime("%H:%M")
        print(f"👑 {sym} qualifies as LEADER ({rec['viol']}, gain-proven) — extra bullets earned "
              f"(ignition x{LEADER_IGNITION_CAP}, curl slots x{LEADER_CURL_SLOTS}, hidden uncapped)")
        try:
            _log_decision(sym, "leader_armed", why=rec["viol"])
        except Exception:
            pass

def _leader_gain(sym, gain_pct):
    """Called wherever a day gain is computed. Sticky."""
    try:
        if not LEADER_AMMO or gain_pct is None: return
        rec = _leader_rec(sym)
        if gain_pct >= LEADER_GAIN_MIN and not rec["gain"]:
            rec["gain"] = True
        _leader_qualify(sym, rec)
    except Exception:
        pass

def _leader_violence(sym, why):
    """Called on halt-suspect episodes."""
    try:
        if not LEADER_AMMO: return
        rec = _leader_rec(sym)
        if rec["viol"] is None: rec["viol"] = why
        _leader_qualify(sym, rec)
    except Exception:
        pass

_pdc_map: dict = {}   # sym -> prior day close (fed at daily preload; crowns-from-tape 8/5)

def _leader_high_probe(sym, last_close):
    """Fresh-high persistence: >=3 minutes in a rolling 10 printing a new session high.
    8/5: also computes day gain vs prior close (from _pdc_map) so a name CROWNS from the
    tape itself — no longer waiting for its first conversion attempt to compute gain."""
    try:
        if not LEADER_AMMO or not last_close: return
        _pdc = _pdc_map.get(sym) or 0
        if _pdc > 0:
            _leader_gain(sym, 100.0 * (float(last_close) / _pdc - 1.0))
        rec = _leader_rec(sym)
        nowm = datetime.now(EASTERN).hour * 60 + datetime.now(EASTERN).minute
        if last_close > rec["hi"]:
            rec["hi"] = last_close
            if not rec["hi_marks"] or rec["hi_marks"][-1] != nowm:
                rec["hi_marks"].append(nowm)
                rec["hi_marks"] = rec["hi_marks"][-12:]
        # 8/5: RTH-only high + its timestamp for the BACK-SIDE gate — the kill-test measured
        # drawdown from the RTH session high; a premarket spike must not mark a name back-side.
        if nowm >= 570 and last_close > rec.get("rth_hi", 0):
            rec["rth_hi"] = last_close
            rec["rth_hi_m"] = nowm
        if rec["viol"] is None and sum(1 for m in rec["hi_marks"] if nowm - 10 <= m <= nowm) >= 3:
            rec["viol"] = "fresh_highs"
        _leader_qualify(sym, rec)
    except Exception:
        pass

# ── 8/6 DEPLOY-FREEZE client (the 12:28 WYHG entry orphan-closed by the 12:31 deploy boot):
#    before ANY conversion the bot consults the dashboard's pause flag. Set by the deploy
#    procedure BEFORE uploading; CLEARED by this bot on boot (new image live = trading resumes).
#    Fail-OPEN: dashboard unreachable -> trade normally (a monitoring outage must never strand
#    the bot; the deploy procedure verifies the flag took before uploading). Kill:
#    PAUSE_ENTRIES_RESPECT=0. Cached 10s so the hot path adds ~zero latency. ──
# ── 8/6 RETEST ENTRY (Marcos: "build retest entry tonight"; kill test data/killtests/
#    break_vs_retest_20260806.py — break-print cohort -$395.09 over 56 era trades, the 1.0%%
#    retest arm -$252.60 = +$142 better, 12%% missed, SHIP-CANDIDATE by pre-registered rule):
#    breakout lanes no longer market-buy the break print. After ALL gates pass, the worker
#    waits up to RETEST_EXPIRY_S for a 10s bar LOW to touch fire_px*(1-DEPTH) and enters
#    THERE; no touch -> retest_expired, slot refunded, no trade (the measured 12%% cost of
#    patience). Stop stays the stamped structural stop. Kill: RETEST_ENTRY=0. ──
RETEST_ENTRY     = os.environ.get("RETEST_ENTRY", "1") == "1"
RETEST_DEPTH_PCT = float(os.environ.get("RETEST_DEPTH_PCT", "1.0"))
RETEST_EXPIRY_S  = int(os.environ.get("RETEST_EXPIRY_S", "900"))
RETEST_LANES     = set((os.environ.get("RETEST_LANES", "flat_top,ignition,orb")).split(","))

PAUSE_ENTRIES_RESPECT = os.environ.get("PAUSE_ENTRIES_RESPECT", "1") == "1"
_pause_cache = {"t": 0.0, "paused": False}


# ── 8/8 (#33) GATE FAIL-OPEN COUNTER: a gate that passes because its DATA failed is now a
# measured event, not a silent one (the exec paths had _exec_health since 7/11; the ENTRY gates
# were mute). One decision row per (gate, 60s); daily visibility via the decisions archive. ──
_gate_fo_t = {}
def _gate_failopen(gate, ticker="_GATE", why=""):
    try:
        now = time.time()
        if now - _gate_fo_t.get(gate, 0) >= 60:
            _gate_fo_t[gate] = now
            _log_decision(ticker, "gate_fail_open", gate=gate, why=str(why)[:60])
    except Exception:
        pass

def _entries_paused():
    if not PAUSE_ENTRIES_RESPECT or not SCREENER_URL:
        return False
    now = time.time()
    if now - _pause_cache["t"] < 10:
        return _pause_cache["paused"]
    try:
        import urllib.request as _ur
        with _ur.urlopen(SCREENER_URL + "/api/pause_entries", timeout=3) as r:
            _pause_cache["paused"] = bool(json.load(r).get("paused"))
        _pause_cache["ok_t"] = now
    except Exception:
        # 8/8 (#33): the deploy-safety tool must not vanish the moment the dashboard hiccups.
        # KEEP the last-known state for up to 10 min of API failure; only then fail open (and
        # say so). A frozen bot stays frozen through a dashboard blip mid-deploy.
        if now - _pause_cache.get("ok_t", 0) > 600:
            if _pause_cache["paused"]:
                print("⚠️ pause-state unknown >10min — failing OPEN (freeze lost)")
            _pause_cache["paused"] = False
            _gate_failopen("entries_paused", why="api>10min")
        else:
            _gate_failopen("entries_paused", why="api err, last-known kept")
    _pause_cache["t"] = now
    return _pause_cache["paused"]


_rebuilt_day = {"d": None}   # 8/8 auditor #3: once-per-day sentinel
def _rebuild_counters_from_today():
    """8/8 (#35 PAINLESS RESTARTS part A): rebuild the in-memory counter economy from the day's
    own DURABLE records (trades + open positions) so a mid-day restart resumes with honest
    ledgers instead of zeroes. Event-sourced: the records are the truth; no second store.
    Rebuilds: PRE tickets (_pre_day), hidden day/name caps (_he_day/_he_name), curl lane slots
    (_curl_rth_n), held set. Crown rehydrate already exists separately (8/5). Fail-soft: any
    error leaves the fresh-boot zeroes (pre-8/8 behavior). Kill: REBUILD_COUNTERS=0."""
    if os.environ.get("REBUILD_COUNTERS", "1") != "1":
        return
    try:
        day = datetime.now(EASTERN).strftime("%Y-%m-%d")
        # auditor #3: main() re-runs every rescan — rebuild ONCE per day per process, and zero
        # the target ledgers before summing (idempotent even if the sentinel is ever bypassed).
        if _rebuilt_day.get("d") == day:
            return
        _rebuilt_day["d"] = day
        _he_day.clear(); _he_name.clear(); _curl_rth_n.clear()
        # 8/10 CRASH FIX (13 boots: clear() strips the "d" key; with no hidden fills to replay,
        # the dict stays EMPTY and _he_day["d"] at the fire site KeyErrors -> process death loop):
        _he_day.update({"d": None, "PRE": 0, "RTH": 0})
        _closed = []
        try:
            r = requests.get(f"{SCREENER_URL}/api/trades", timeout=10)
            _closed = [t for t in (r.json().get("trades") or []) if t.get("date") == day]
        except Exception:
            pass
        _open = []
        try:
            _open = [o for o in _load_open_trades_from_screener()
                     if o.get("entry_date") == day or o.get("date") == day]
        except Exception:
            pass
        _lane_map = {"zone_flip": "zf", "vwap_reclaim": "vr", "dip_rip": "dr"}
        n_pre = 0
        _seen_tid = set()
        for t in _closed + _open:
            _tid = t.get("trade_id")
            if _tid and _tid in _seen_tid:
                continue   # auditor #5: a record posted whose open-row clear failed = one trade, once
            if _tid: _seen_tid.add(_tid)
            tk = str(t.get("ticker") or "").upper()
            et = str(t.get("entry_type") or "")
            sess = "PRE" if (t.get("entry_session") == "PRE") else "RTH"
            if not tk:
                continue
            if t.get("entry_session") == "PRE":
                n_pre += 1
            if et == "hidden_entry":
                if _he_day.get("d") != day:
                    _he_day["d"] = day; _he_day["PRE"] = 0; _he_day["RTH"] = 0
                _he_day[sess] = _he_day.get(sess, 0) + 1
                _k = (day, tk, sess)
                _he_name[_k] = _he_name.get(_k, 0) + 1
            lane = _lane_map.get(et)
            if lane:
                _k = (day, tk, lane, sess)
                _curl_rth_n[_k] = _curl_rth_n.get(_k, 0) + 1
        _pre_day["d"] = day
        _pre_day["n"] = n_pre
        for o in _open:
            tk = str(o.get("ticker") or "").upper()
            if tk:
                reentry["held"].add(tk)
        print(f"🧮 counters rebuilt from today's records: PRE {n_pre}, hidden "
              f"{_he_day.get('PRE',0)}P/{_he_day.get('RTH',0)}R, curl slots {len(_curl_rth_n)}, "
              f"held {sorted(reentry['held']) or '[]'}")
        _log_decision("_BOOT", "counters_rebuilt", pre_n=n_pre,
                      hidden_pre=_he_day.get("PRE", 0), hidden_rth=_he_day.get("RTH", 0),
                      curl_keys=len(_curl_rth_n), held=len(reentry["held"]))
    except Exception as e:
        print(f"⚠️ counter rebuild failed (fresh-boot zeroes kept): {e}")

def _clear_entries_pause():
    """Boot: the new image is live — lift the deploy freeze."""
    try:
        import urllib.request as _ur
        req = _ur.Request(SCREENER_URL + "/api/pause_entries",
                          data=json.dumps({"paused": False, "note": "cleared by bot boot"}).encode(),
                          headers={"Content-Type": "application/json",
                                   "X-Dashboard-Secret": os.environ.get("DASHBOARD_SECRET", "marcos2026")},
                          method="POST")
        _ur.urlopen(req, timeout=5)
        print("🧊 deploy-freeze flag cleared (new image live)")
    except Exception as e:
        print(f"⚠️  could not clear pause flag ({e}) — clear manually if a freeze was set")

def _reentry_rail_giveup(ticker, pnl, reentry, crowned):
    """Death-by-cuts rail, one decision per closed trade. Updates BOTH counters (count + dollars;
    a winning trade resets both — Kev's 6-win trend days keep going), then bans on the counter
    that governs this name: CROWNED = consecutive-loss DOLLARS >= REENTRY_CROWN_LOSS_DOLLARS
    (8/5 Marcos: whales are banned on real damage, never on paper-cut count); uncrowned (or
    dollar rail killed via env 0) = the original count-of-N."""
    reentry["consec_loss"][ticker] = 0 if pnl > 0 else reentry["consec_loss"].get(ticker, 0) + 1
    _u = reentry.setdefault("consec_loss_usd", {})
    _u[ticker] = 0.0 if pnl > 0 else _u.get(ticker, 0.0) + abs(min(float(pnl), 0.0))
    if crowned and REENTRY_CROWN_LOSS_DOLLARS > 0:
        return _u[ticker] >= REENTRY_CROWN_LOSS_DOLLARS
    return reentry["consec_loss"][ticker] >= REENTRY_MAX_CONSEC_LOSS

def _is_leader(sym):
    if not LEADER_AMMO: return False
    day = datetime.now(EASTERN).strftime("%Y-%m-%d")
    rec = _leader_day.get((day, sym))
    return bool(rec and rec["since"] is not None)

_leader_rehydrated = {"day": None}
def _leader_rehydrate():
    """8/5 (Marcos: "so it would have to reprove the violence"): leader status is EARNED and
    must survive a restart — the proof already lives in durable decision rows. On session start,
    replay today's leader_armed rows (full requalification) and halt_suspect rows (violence
    half re-armed; gain re-proves from live tape within minutes). Fail-soft: no dashboard, no
    rehydrate, detector just re-earns from tape like before."""
    day = datetime.now(EASTERN).strftime("%Y-%m-%d")
    if not LEADER_AMMO or _leader_rehydrated["day"] == day:
        return
    _leader_rehydrated["day"] = day
    try:
        import urllib.request as _lr_ureq
        req = _lr_ureq.Request(f"{SCREENER_URL}/api/decisions_archive?date={day}"
                               f"&status=leader_armed,halt_suspect&limit=50000")
        rows = json.load(_lr_ureq.urlopen(req, timeout=20)).get("rows") or []
        n_l = n_h = 0
        for r in rows:
            sym = str(r.get("ticker") or "").upper()
            if not sym or sym.startswith("_"): continue
            rec = _leader_rec(sym)
            if r.get("status") == "leader_armed" and rec["since"] is None:
                rec["gain"] = True; rec["viol"] = r.get("why") or "rehydrated"
                rec["since"] = str(r.get("time") or "")[:5] or "00:00"; n_l += 1
            elif r.get("status") == "halt_suspect" and rec["viol"] is None:
                rec["viol"] = "halt"; n_h += 1
        if n_l or n_h:
            print(f"👑 leader rehydrate: {n_l} leaders restored, {n_h} halt-violence flags re-armed")
        # 8/5 AMMO-LEDGER REHYDRATE (restart amnesty fix): rebuild spent-ticket counts from
        # today's recorded trades so a restart never re-rations names that already spent tickets.
        try:
            import urllib.request as _ar_ureq
            _tr = json.load(_ar_ureq.urlopen(f"{SCREENER_URL}/api/trades", timeout=20)).get("trades") or []
            _n_seed = 0
            for _t in _tr:
                if _t.get("date") != day: continue
                _sym = str(_t.get("ticker") or "").upper(); _lane = _t.get("entry_type")
                _sess = "RTH"
                try:
                    _ets = str(_t.get("entry_ts_utc") or "")
                    if _ets:
                        _h = int(_ets[11:13]) - 4
                        _sess = "PRE" if _h * 60 + int(_ets[14:16]) < 570 else "RTH"
                except Exception:
                    pass
                _ln = {"zone_flip": "zf", "vwap_reclaim": "vr", "dip_rip": "dr"}.get(_lane)
                if _ln:
                    _kk = (day, _sym, _ln, _sess)
                    _curl_rth_n[_kk] = _curl_rth_n.get(_kk, 0) + 1; _n_seed += 1
                elif _lane == "hidden_entry":
                    if _he_day.get("d") != day:
                        _he_day["d"] = day; _he_day["PRE"] = 0; _he_day["RTH"] = 0
                    _he_day[_sess] = _he_day.get(_sess, 0) + 1
                    _kh = (day, _sym, _sess)
                    _he_name[_kh] = _he_name.get(_kh, 0) + 1; _n_seed += 1
            if _n_seed:
                print(f"♻️  ammo rehydrate: {_n_seed} spent ticket(s) restored from today's trades")
        except Exception as _ae:
            print(f"   ⚠️ ammo rehydrate skipped ({_ae})")
    except Exception as _e:
        print(f"   ⚠️ leader rehydrate skipped ({_e}) — detector re-earns from live tape")

def _curl_rth_slot(sym, lane, hm):
    """True exactly once per (day, sym, lane, SESSION): first converting fire per session.
    SESSION SPLIT 7/26 (Marcos "ship all 4" — was the code's own 'KNOWN LIMITATION, weekend fix
    queued'): with ENTRY_OPEN_ET=04:00 (premarket paper), a 5am practice fire was consuming the
    name's ONLY RTH slot — the 9:45 real flush-reclaim then couldn't convert. Premarket practice
    now spends PRE tickets; the real session spends RTH tickets. Earlier-than-floor fires never
    consume."""
    if hm < ENTRY_OPEN_ET:
        return False
    sess = "PRE" if hm < "09:30" else "RTH"
    day = datetime.now(EASTERN).strftime("%Y-%m-%d")
    k = (day, sym, lane, sess)
    _lim = LEADER_CURL_SLOTS if _is_leader(sym) else 1   # 8/5 leader ammo
    if _curl_rth_n.get(k, 0) >= _lim:
        return False
    _curl_rth_n[k] = _curl_rth_n.get(k, 0) + 1
    return True

def _slot_refund(sym, entry_type):
    """7/29 (Marcos: "we have to move fast and not be clipped every morning like today"):
    a session slot is spent by a TRADE, not an ATTEMPT. The 7/29 AMIX clip: the 09:32 ticket
    consumed reclaim's RTH slot, died at the sizing guards, and the REAL flush entry 8 minutes
    later — Kev's dip-and-rip moment, 5.49 -> 7.25 — had no slot left to convert. Every refusal
    path between conversion and BUY now refunds the lane slot so the detector's next fire can
    convert. (Ignition's once-per-ticker cache flag is out of this scope — queued.)"""
    try:
        now = datetime.now(EASTERN)
        day, hm = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
        sess = "PRE" if hm < "09:30" else "RTH"
        lane = {"zone_flip": "zf", "vwap_reclaim": "vr", "dip_rip": "dr"}.get(entry_type)
        if lane:
            # 8/5 leader ammo: refund ONE ticket, not the whole ledger — a leader that spent
            # 2 of 3 slots and dies at a gate gets back to 1 used, not 0.
            _k_cr = (day, sym, lane, sess)
            if _curl_rth_n.get(_k_cr, 0) > 1:
                _curl_rth_n[_k_cr] -= 1
            else:
                _curl_rth_n.pop(_k_cr, None)
        elif entry_type == "hidden_entry":
            if _he_day.get("d") == day and _he_day.get(sess, 0) > 0:
                _he_day[sess] -= 1
            _k = (day, sym, sess)
            if _he_name.get(_k, 0) > 0:
                _he_name[_k] -= 1
        else:
            return
        _log_decision(sym, "slot_refunded", machine=entry_type)
        print(f"   ♻️ {sym} {entry_type}: session slot REFUNDED — an attempt is not a trade; the lane can re-fire")
    except Exception:
        pass


def _level_gap(ticker, price):
    """BALLPARK STAMP (7/27, Marcos: tape lanes 'deserve some structure from the charts' — measured
    first, gated never tonight). Signed distance from the day's marked break (+above/−below) and the
    ±10% ballpark verdict. 135-fire study (killtest_overhead_level.py): inside ±10% wins 54%, outside
    29% — but the far-above cell is the momentum class the 7/21 staleness test refuted blocking, so
    this STAMPS ONLY. Friday 7/31 dollar-grades it. Fail-open: no level / any error → (None, None)."""
    try:
        lv = (_fetch_kev_levels() or {}).get(ticker) or {}
        brk = float(lv.get("break") or 0)
        if brk <= 0 or not price or price <= 0:
            return None, None
        gap = round((float(price) - brk) / brk * 100.0, 1)
        return gap, ("in" if abs(gap) <= 10.0 else "out")
    except Exception:
        return None, None


# ── THE LEVEL LENS, STAGE 1 (7/28 pre-open; Marcos: "the bot is blind to where it is... arm the
#    bot with this information not as a gate but as a lens from which to find its target").
#    v1 = ATTENTION ONLY: a name whose price is near ANY of its marked prices (confirm / break /
#    targets) is IN FOCUS — it moves to the FRONT of every watch cycle, and focus transitions are
#    decision-logged. The lens never blocks, never resizes, never vetoes — it decides where the bot
#    LOOKS first, nothing else. Stage 2 (detectors anchored to zones) is Friday-8/1-gated:
#    LEVEL_AWARENESS_DESIGN.md. Focus band ±15% — deliberately wider than the ±10% outcome ballpark
#    (attention should arrive BEFORE the outcome zone). LENS_FOCUS_PCT=0 disables.
LENS_FOCUS_PCT = float(os.environ.get("LENS_FOCUS_PCT", "15"))   # percent; 0 = lens off
_lens_state = {}   # ticker -> last in_focus bool (transition logging only)
_lens_dark_t = 0.0   # last darkness-canary print (curl-feed lesson: absent-vs-stale must be VISIBLE)

def _level_lens(ticker, price):
    """(in_focus, nearest_zone_name, zone_px, dist_pct) vs the day's marked prices. Compare on the
    ROUNDED distance (the minstop boundary lesson: raw float division rejects exact boundaries).
    Fail-open: no levels / no price / any error → (False, None, None, None) — an unmapped name is
    simply never in focus; it is NOT excluded from anything."""
    try:
        if not LENS_FOCUS_PCT or not price or price <= 0:
            return False, None, None, None
        lv = (_fetch_kev_levels() or {}).get(ticker) or {}
        zones = []
        for name in ("confirm", "break"):
            try:
                z = float(lv.get(name) or 0)
                if z > 0:
                    zones.append((name, z))
            except (TypeError, ValueError):
                pass
        for i, tgt in enumerate(lv.get("targets") or []):
            try:
                z = float(tgt)
                if z > 0:
                    zones.append((f"target{i+1}", z))
            except (TypeError, ValueError):
                pass
        if not zones:
            return False, None, None, None
        name, z = min(zones, key=lambda nz: abs(price - nz[1]))
        dist_pct = round((price - z) / z * 100.0, 1)
        return abs(dist_pct) <= LENS_FOCUS_PCT, name, z, dist_pct
    except Exception:
        return False, None, None, None


def _lens_px(ticker):
    """FREE price read for the lens — cached stream tick only, NEVER REST. get_price() falls back
    to a REST quote when the stream is stale, and the lens polls every candidate every cycle: in
    degraded mode (premarket / silent stream — exactly when 429s bite) that would roughly DOUBLE
    quote traffic. Attention must cost nothing: stale-tolerant registry peek (120s — fine for a
    ±15% band), else 0 → the name simply isn't in focus this cycle (fail-open)."""
    try:
        with _price_lock:
            rec = _price_registry.get(ticker.upper())
        if isinstance(rec, dict) and rec.get("p", 0) > 0 and (time.time() - rec.get("t", 0)) <= 120:
            return rec["p"]
    except Exception:
        pass
    return 0


def _lens_pass(candidates, stream):
    """One watch cycle through the lens: compute focus per name from the CACHED stream price, log
    transitions, return candidates FOCUS-FIRST (sorted() is stable — scanner rank is preserved as
    the tiebreak inside each group). Pure attention: every name still runs every cycle; a lens
    error must never break the scan (fail-open to the incoming order); a lens read must never
    leave process memory except the one shared 90s-TTL levels cache refresh."""
    try:
        focus = {}
        for t in candidates:
            try:
                infocus, zn, zpx, dist = _level_lens(t, _lens_px(t))
            except Exception:
                infocus = False; zn = zpx = dist = None
            focus[t] = infocus
            prev = _lens_state.get(t)
            if (prev is not None and prev != infocus) or (prev is None and infocus):
                _log_decision(t, "lens_focus" if infocus else "lens_unfocus",
                              zone=zn, zone_px=zpx, dist_pct=dist)
                if infocus:
                    print(f"🔎 {t} IN FOCUS — {dist:+.1f}% from {zn} {zpx} (lens: front of the cycle)")
            _lens_state[t] = infocus
        # DARKNESS CANARY (7/28 review): if the lens can see levels but NO candidate has a price
        # (registry unfed — stream silent AND rest not yet cycled), say so every ~5 min instead of
        # silently doing nothing. Absent-vs-stale must be visible — the curl-feed lesson.
        global _lens_dark_t
        if candidates and LENS_FOCUS_PCT and not any(_lens_px(t) > 0 for t in candidates):
            if time.time() - _lens_dark_t >= 300:
                _lens_dark_t = time.time()
                print(f"🕶️  LENS DARK — no cached price for any of {len(candidates)} candidates "
                      f"(stream silent + REST not yet cycled); focus ordering inactive this stretch")
                _log_decision("__LENS__", "lens_dark", n=len(candidates))
        return sorted(candidates, key=lambda s: 0 if focus.get(s) else 1)
    except Exception:
        return candidates


def _shadow_log_curl_leftovers(t, price, zf_fire, vr_fire, sv, why):
    """#89: a curl-machine fire that lost entry priority (or hit a loop `continue`) is still
    EVIDENCE — shadow-log it, never drop it. Called at every early-exit site in the watch loop."""
    if not (zf_fire or vr_fire):
        return
    # 7/28: a no-price cycle (session-aware quote returned 0) must not log a 0.0-price fire row —
    # the fire's own bar price is the honest value (it came from real 10s bars).
    if not price or price <= 0:
        price = (zf_fire or {}).get("px") or (vr_fire or {}).get("px") or 0
        if not price:
            return
    _hm = datetime.now(EASTERN).strftime("%H:%M")
    try:
        _gap, _bp = _level_gap(t, price)   # 7/27 ballpark stamp — Friday's dollar-grade column
        if zf_fire:
            _log_decision(t, "zoneflip_shadow_fire", price=price, zone=zf_fire.get("zone"),
                          zone_src=zf_fire.get("zone_src"), stop=zf_fire.get("stop"),
                          time_hm=_hm, seq=zf_fire.get("seq", 0), why=why,
                          level_gap_pct=_gap, ballpark=_bp)
        if vr_fire:
            _log_decision(t, "reclaim_shadow_fire", price=price, vwap=sv,
                          stop=vr_fire.get("stop"), time_hm=_hm,
                          seq=vr_fire.get("seq", 0), why=why,
                          level_gap_pct=_gap, ballpark=_bp)
    except Exception:
        pass


def kev_reclaim_step(sym, new_bars, vwap):
    """Advance sym's 3-gate machine over NEW completed 10s bars [(k,o,h,l,c,vol),...] against the
    current session line (k = 10s bucket epoch — 7/28 stale-fire guard). Returns {'stop','wick_low'}
    exactly ONCE (on the curl), else None. A fire on a bar older than CURL_FIRE_MAX_AGE_SECS is
    SUPPRESSED-and-consumed: detection replays history freely, action never does."""
    day = datetime.now(EASTERN).strftime("%Y-%m-%d")
    st = _reclaim_st.get(sym)
    if not st or st.get("day") != day:
        st = {"day": day, "phase": "seek", "ext": False, "wick": None, "vols": [], "n": 0, "prev_c": None}
        _reclaim_st[sym] = st
    if not vwap or vwap <= 0:
        return None
    prev_c = st["prev_c"]
    fired = None
    for k, o, h, l, c, v in new_bars:
        st["vols"].append(v)
        if len(st["vols"]) > 30: st["vols"].pop(0)
        avgv = (sum(st["vols"][:-1]) / max(len(st["vols"]) - 1, 1)) if len(st["vols"]) > 1 else 0
        if st["phase"] == "seek":
            if prev_c is not None and prev_c <= vwap and c > vwap and avgv > 0 and v >= 2.0 * avgv:
                st["phase"] = "extend"; st["ext"] = False
        elif st["phase"] == "extend":
            if c >= vwap * 1.01: st["ext"] = True
            if st["ext"] and l <= vwap * 1.005:
                st["phase"] = "retest"; st["wick"] = None
            elif c < vwap * 0.99:
                st["phase"] = "seek"; st["ext"] = False
        if st["phase"] == "retest" and fired is None:
            if c < vwap * 0.99:
                st["phase"] = "seek"; st["ext"] = False; st["wick"] = None
            else:
                rng = h - l
                if rng > 0 and l <= vwap * 1.005 and (c - l) / rng >= 0.5:
                    st["wick"] = (h, l)
                elif st["wick"] and c > st["wick"][0]:
                    # fire — then RESET to seek so later setups keep getting DETECTED all day
                    # (Marcos 7/19: "data for and against it the whole day"). seq 0 = the day's
                    # first fire (the only live-eligible one); seq 1+ = shadow evidence.
                    # 7/28 stale-fire guard: an OLD bar consumes the setup but never fires.
                    if not _bucket_fresh(k, sym=sym):   # 8/5 halt-aware
                        _log_stale_fire(sym, "vwap_reclaim", k, round(c, 4))
                        st["n"] += 1
                        st["phase"] = "seek"; st["ext"] = False; st["wick"] = None
                        prev_c = c
                        continue
                    fired = {"stop": round(max(min(st["wick"][1], vwap), c * 0.93), 4),
                             "wick_low": st["wick"][1], "seq": st["n"], "px": round(c, 4), "k": k,
                             # 7/30: the fire bar's own participation, stamped for the conversion-
                             # time re-check (RECLAIM_FIREVOL). Recording only — no branch changed.
                             "volmult": (round(v / avgv, 2) if avgv > 0 else None)}
                    st["n"] += 1
                    st["phase"] = "seek"; st["ext"] = False; st["wick"] = None
        prev_c = c
    st["prev_c"] = prev_c
    return fired


# ── ZONE-FLIP pullback machine (7/20, Reclaim Architect — Marcos: "I want this to go in and let
# the other of what we have be the shadow"). Kev's ZYBT 7/20 entry class: open flush into the
# late-premarket shelf → absorption wick → curl. Phase-1 kill-test PASSED (17 fires/10 sessions,
# model B +0.440R/fire, 71% +1R-first, ZYBT specimen caught 1.285 vs Kev 1.28 — scratchpad
# zone_flip_killtest_results.txt). Zone rule is BYTE-FAITHFUL to the tested pm_floor(): 1-minute
# lows 9:00–9:29 (10s bars folded to 1m first — parity with the tested granularity), chained-merge
# shelves within 1%, shelf FLOOR, ≥3 touches then ≥2, else 9:15–9:29 min-low; zone must sit below
# the 9:30 open. ZONEFLIP_KEV=0 kill switch. RECLAIM_LIVE=0 (default) demotes the VWAP-reclaim
# machine to shadow — 7/20 role swap; flip to 1 to restore it.
ZONEFLIP_KEV   = os.environ.get("ZONEFLIP_KEV", "1") == "1"
# ── 7/30 FABLE G1 (Marcos yes): zone_flip to SHADOW. Worst per-trade lane on the board (era 6
# trades / 1 win / −$223.48; 7/30 0-for-2 −$57.46) and unmeasurable at ~3 fires/day: the 8-cell
# arm-window sweep loses in EVERY cell with win rate pinned 31–36%. The DETECTOR stays fully live
# (ZONEFLIP_KEV) so evidence keeps accruing free — only the conversion is off. RE-ARM CONDITION
# (pre-registered): replay the accumulated fires through the front-side gate once Friday's
# head-to-head picks it; if the gated lane resurrects, it comes back GATED. ZONEFLIP_CONVERT=1
# restores today's behavior exactly.
ZONEFLIP_CONVERT = os.environ.get("ZONEFLIP_CONVERT", "0") == "1"
ZONEFLIP_FLUSH = float(os.environ.get("ZONEFLIP_FLUSH_PCT", "0.04"))   # tested primary cell
ZONEFLIP_BAND  = float(os.environ.get("ZONEFLIP_BAND", "0.02"))        # tested primary cell
# 7/20 FINAL CONFIG (Marcos: "put in both... VWAP reclaim in the morning like we had it...
# but I want the zone flip all day live"): BOTH machines live — zone-flip = first fire per
# name, ALL DAY (arm window is structurally 9:30–9:45, so fires cluster at the open; a rare
# late curl off an early arm is the only new territory); VWAP-reclaim = first fire inside
# 09:30–11:00 (its head-to-head-verified window: +0.289R/fire in-window vs −0.38R after),
# shadow the rest of the day. Head-to-head evidence: scratchpad zone_flip_killtest_results.txt.
RECLAIM_LIVE   = os.environ.get("RECLAIM_LIVE", "1") == "1"
# ── 7/30 FIRE-BAR RE-CHECK (Marcos: "ship the 2.0"). The lane demands 2× participation at the
# CROSS but never re-checks at the FIRE — entry can land 90s later on a 100-share bar (all five
# of 7/30's live reclaim losers fired below 2×: 0.1/0.8/1.8/1.5/0.1×; YHC bought 150 sh = $296).
# Same threshold the lane already believes in, applied at the moment we actually buy. CONVERSION
# ONLY — detection/shadow untouched, so Friday's three-arm replay sample is unaffected. Sweep
# (pre-registered split, control reproduced): TEST −$6.28 → −$5.47/fire, tail kept 80.7%; NOT a
# profitability fix — a bleed reducer while G2 keeps the lane live for Friday's sample.
# FAILURE CONDITION (pre-registered): wrong if the refused fires' forward counterfactual
# (`reclaim_firevol_reject` rows) outperforms the accepted cohort. Kill: RECLAIM_FIREVOL=0.
RECLAIM_FIREVOL = float(os.environ.get("RECLAIM_FIREVOL", "2.0"))
_zf_st: dict = {}      # sym -> daily state machine
_zf_cursor: dict = {}  # (day, sym) -> last processed 10s bucket epoch
_zf_zone: dict = {}    # (day, sym) -> {"zone","src","open930"} or "none" (computed, no zone)

def _zf_pm_floor(sym):
    """Mechanical late-premarket floor, verbatim from the kill-test's pm_floor(). Computed once
    per (day, sym) after the 9:30 bar exists; returns None (retry) until data is complete."""
    day = datetime.now(EASTERN).strftime("%Y-%m-%d")
    key = (day, sym)
    cached = _zf_zone.get(key)
    if cached is not None:
        return None if cached == "none" else cached
    # #97: rig P3 caught this third consumer — on Alpaca mode an empty Webull store would leave
    # the zone-flip permanently ZONELESS (same #89 starvation, one level deeper). n=720 (the hot
    # bound, 2h) reaches 9:00–9:29 from any compute before ~11:00; later adds behave as today
    # (no zone → machine idles), which the open-native zone-flip never needs anyway.
    d10, _zf_feed_src = _curl_feed(sym, n=720)
    if not d10:
        return None                              # no bars yet — retry next loop
    mins, open930 = {}, None
    for k in sorted(d10):
        b = d10[k]
        _t = datetime.fromtimestamp(k, EASTERN)
        hm = _t.hour * 60 + _t.minute
        if 540 <= hm <= 569:                     # 9:00–9:29 window, folded to 1m lows
            m = k // 60 * 60
            lo = mins.get(m)
            mins[m] = b["l"] if lo is None else min(lo, b["l"])
        elif hm >= 570 and open930 is None:
            open930 = b["o"]
    if open930 is None:
        return None                              # 9:30 bar not seen yet — retry
    lows = sorted(v for v in mins.values() if v > 0)
    zone = src = None
    if lows:
        shelves, cur = [], [lows[0]]
        for x in lows[1:]:
            if x <= cur[-1] * 1.01:
                cur.append(x)
            else:
                shelves.append((cur[0], len(cur))); cur = [x]
        shelves.append((cur[0], len(cur)))
        for min_touch in (3, 2):
            cands = [p for p, n in shelves if n >= min_touch and p < open930]
            if cands:
                zone, src = max(cands), f"pm_shelf{min_touch}"
                break
    if zone is None:
        late = [v for m, v in mins.items()
                if 555 <= (datetime.fromtimestamp(m, EASTERN).hour * 60
                           + datetime.fromtimestamp(m, EASTERN).minute) <= 569 and v > 0]
        if late and min(late) < open930:
            zone, src = min(late), "pm_minlow"
    if zone is None:
        _zf_zone[key] = "none"                   # computed on complete data: genuinely no zone
        return None
    z = {"zone": zone, "src": src, "open930": open930}
    _zf_zone[key] = z
    return z

# ── HIDDEN ENTRY (7/24 night, Marcos: "I want winners... enough timid"). Kev's 10-second rocket
# playbook, expert fidelity-audited against his own words (shorts k27fptelI8Y + XFSPUI5YJsE +
# ZCMD checklist 3UboKEl7-Oc):
#   KEV-VERBATIM: 10s timeframe ("I use the 10-second time frame to find pullback entries that
#     nobody else sees"); price above VWAP (checklist box #1); pullback tests VWAP+90MA and
#     "wicks off the low to confirm"; entry at wick-confirm, "risking these wick lows".
#   KEV-TRANSLATED (registry): anchor = max(10s-90EMA, session VWAP) [his confluence]; wick =
#     close in top half of range; ARM vel 25%/5min [his "rocketing up", our number].
#   OURS (governance): caps 3/day + 2/name, 5% min-risk floor, HIDDEN_ENTRY=0 kill switch.
# REPLACES the 1-min rocket_catcher (default flipped OFF below): the 1-min 20-EMA anchor is
# structurally untouchable by a true parabola (STAK 7/24 + ZCMD 7/22 armed-never-fired) and
# adversely selected. Exit v1 = the tested rocket %-ladder; weak-resumption exit = week-2
# change-set; 2:1-bank + weak-resumption counterfactuals gradeable from stamped records.
HIDDEN_ENTRY      = os.environ.get("HIDDEN_ENTRY", "1") == "1"
HIDDEN_VEL_PCT    = float(os.environ.get("HIDDEN_VEL_PCT", "25"))   # ARM: trailing 5-min velocity
HIDDEN_VEL_BARS   = int(os.environ.get("HIDDEN_VEL_BARS", "30"))    # 30 x 10s = 5 min
HIDDEN_TRIM_R     = float(os.environ.get("HIDDEN_TRIM_R", "1.0"))   # 7/27: R-based FIRST trim on the hidden
                            # ladder (the inherited ×1.50 trigger sat above both closed peaks = unreachable).
HIDDEN_DAILY_CAP  = int(os.environ.get("HIDDEN_DAILY_CAP", "3"))
# ── 7/30 A1 (Fable ship, Marcos yes): extension-above-VWAP at entry is BIMODAL on 190 fires —
# 0–3% = the clean dip-buy, 10%+ = the deep wick inside a genuine vertical (+$1,472, the entire
# lane), 3–10% = no-man's-land (−$1,942/69 fires, survives BOTH exit configs = an entry property).
# Refuse the dead band EXACTLY (3–10, no pad — padding eats the paying 10%+ cell; boundary fires
# 9–12% are stamped for forward observation). Kill: HIDDEN_EXT_GATE=0.
# FAILURE CONDITION (pre-registered): wrong if refused 3–10% fires' forward counterfactual turns
# positive — every refusal logs `hidden_ext_reject` with the full fire so that grade stays runnable.
HIDDEN_EXT_GATE   = os.environ.get("HIDDEN_EXT_GATE", "1") == "1"
HIDDEN_EXT_LO     = float(os.environ.get("HIDDEN_EXT_LO", "3.0"))    # percent, inclusive
HIDDEN_EXT_HI     = float(os.environ.get("HIDDEN_EXT_HI", "10.0"))   # percent, exclusive
# 8/6: crowned names bypass the band (see gate comment; refused-crown forward +$641.87/26 vs
# non-crown refusals negative). 0 = flat band for everyone (pre-8/6 behavior).
HIDDEN_EXT_CROWN_BYPASS = os.environ.get("HIDDEN_EXT_CROWN_BYPASS", "1") == "1"
# 8/6 (Marcos: "why are we trading anything without a map????") — tape-lane conversions on
# names with ZERO levels are fail-closed; see mapless_reject site. 0 restores the fail-open.
MAPLESS_BLOCK = os.environ.get("MAPLESS_BLOCK", "1") == "1"
# 7/30 A2-F: post-scale stop ratchets to the scale-bar low (hidden only). Kill switch:
HIDDEN_SCALEBAR_STOP = os.environ.get("HIDDEN_SCALEBAR_STOP", "1") == "1"
# 7/29 ANCHOR-MATURITY GATE (gauntleted): the lane is Kev's wick off the VWAP+90MA CONFLUENCE, but
# the detector's 10s-EMA90 is seeded from its first bar — on fresh gappers it is an unconverged
# echo of recent closes, so `anchor=max(e90,vwap)` degenerates to plain VWAP. Every one of the
# lane's 9 lifetime trades (0 wins, −$282) fired in that degenerate state (entry_vs_ema90_pct null
# on ALL). Fire only after >= HIDDEN_ANCHOR_MIN_BARS 10s bars so the 90MA is real. WRONG WHEN: a
# genuine wick forms on <15 min of tape — refused fires log `hidden_anchor_immature` shadow rows so
# that cost is MEASURED. Kill switch: HIDDEN_ANCHOR_REQ=0.
HIDDEN_ANCHOR_REQ      = os.environ.get("HIDDEN_ANCHOR_REQ", "1") == "1"
HIDDEN_ANCHOR_MIN_BARS = int(os.environ.get("HIDDEN_ANCHOR_MIN_BARS", "90"))
HIDDEN_NAME_CAP   = int(os.environ.get("HIDDEN_NAME_CAP", "2"))
_he_st: dict = {}                 # sym -> machine state (module-level: survives rescans, no #81 amnesia)
_he_day = {"d": None, "PRE": 0, "RTH": 0}   # SESSION-KEYED 7/26 (mirror of the _curl_rth_slot fix):
_he_name: dict = {}                          # (day, sym, sess) -> conversions. Premarket practice must
                                             # never exhaust the RTH caps (3 pre-9:30 paper trades used
                                             # to zero out the lane for the whole real session).

def hidden_entry_step(sym, new_bars, vwap):
    """Advance sym's HIDDEN-ENTRY machine over NEW completed 10s bars [(o,h,l,c,vol),...].
    ARM on trailing 5-min velocity >= HIDDEN_VEL_PCT; FIRE on the Kev wick: bar low tags
    max(10s-90EMA, VWAP) FROM ABOVE (close holds >= anchor and >= VWAP), bottoming wick
    (close in top half), green-ish body. Returns fire dict once per qualifying bar, else None.
    Stays armed after a fire — Kev re-enters fresh structure; caps enforced at conversion."""
    day = datetime.now(EASTERN).strftime("%Y-%m-%d")
    st = _he_st.get(sym)
    if not st or st.get("day") != day:
        st = {"day": day, "closes": [], "e90": None, "armed": False, "n": 0, "nbars": 0}
        _he_st[sym] = st
        # 8/10 FULL-WARM (Marcos: "No warming should be needed. Rehydration is mandatory."):
        # a fresh machine fed a deep first pass matures instantly — nbars counts BARS SEEN,
        # and history bars are bars. Nothing else needed here; the deep pass below does it.
        # (STKH 8/10: mid-session add stayed immature because its first pass wasn't deep —
        # fixed by the roster-add deep-pass below, not by faking maturity.)
    if not vwap or vwap <= 0:
        return None
    fired = None
    for k, o, h, l, c, v in new_bars:   # 7/28: k = bucket epoch (stale-fire guard)
        st["nbars"] = st.get("nbars", 0) + 1
        st["e90"] = c if st["e90"] is None else c * (2.0 / 91.0) + st["e90"] * (89.0 / 91.0)
        st["closes"].append(c)
        if len(st["closes"]) > HIDDEN_VEL_BARS + 1:
            st["closes"].pop(0)
        if not st["armed"]:
            if len(st["closes"]) > HIDDEN_VEL_BARS:
                _ca = st["closes"][0]
                if _ca > 0 and (c - _ca) / _ca * 100.0 >= HIDDEN_VEL_PCT:
                    st["armed"] = True
            continue
        anchor = max(st["e90"], vwap)
        rng = h - l
        if (fired is None and l <= anchor and c >= anchor and c >= vwap
                and rng > 0 and (c - l) / rng >= 0.5 and c > o * 0.995):
            # 7/29 ANCHOR-MATURITY GATE: without >=90 bars the "90MA" is fiction and this is a bare
            # VWAP-touch buy — the shape that went 0-for-9. Shadow-log the refusal (measured cost).
            if HIDDEN_ANCHOR_REQ and st.get("nbars", 0) < HIDDEN_ANCHOR_MIN_BARS:
                try:
                    _log_decision(sym, "hidden_anchor_immature", price=round(c, 4),
                                  nbars=st.get("nbars", 0), anchor=round(anchor, 4))
                except Exception:
                    pass
                st["n"] += 1                             # consumed, not traded
                continue
            if not _bucket_fresh(k, sym=sym):              # 7/28 stale-fire guard (8/5 halt-aware)
                _log_stale_fire(sym, "hidden_entry", k, round(c, 4))
                st["n"] += 1                             # consumed (mirror of a fire's seq advance)
                continue
            stop = min(l - 0.01, c * 0.95)               # wick low, floored at 5% risk (fake-risk guard)
            fired = {"stop": round(stop, 4), "wick": l, "anchor": round(anchor, 4),
                     "ext_vwap": round((c - vwap) / vwap * 100.0, 2), "seq": st["n"], "px": round(c, 4), "k": k}
            st["n"] += 1
    return fired


def kev_zoneflip_step(sym, new_bars):
    """Advance sym's Z1–Z3 machine over NEW completed 10s bars [(k,o,h,l,c,vol),...].
    Z1 arm: 9:30–9:45 flush ≥ZONEFLIP_FLUSH from the 9:30 open, low inside zone±band, vol ≥2×
    rolling avg. Z2: bottoming wick in the band. Z3 (fire): close > wick high — the live 10s
    analog of the tested model-B break-fill. Fires at most once per call; resets to re-arm so
    later setups keep getting DETECTED all day (seq 1+ = shadow evidence, mirror of reclaim)."""
    z = _zf_pm_floor(sym)
    if not z:
        return None
    zone, open930 = z["zone"], z["open930"]
    day = datetime.now(EASTERN).strftime("%Y-%m-%d")
    st = _zf_st.get(sym)
    if not st or st.get("day") != day:
        st = {"day": day, "armed": False, "wick": None, "flush_low": None, "vols": [], "n": 0}
        _zf_st[sym] = st
    zlo, zhi = zone * (1 - ZONEFLIP_BAND), zone * (1 + ZONEFLIP_BAND)
    fired = None
    for k, o, h, l, c, v in new_bars:
        st["vols"].append(v)
        if len(st["vols"]) > 60: st["vols"].pop(0)    # rolling ~10 min of 10s bars (tested: prior-10 1m)
        avgv = (sum(st["vols"][:-1]) / max(len(st["vols"]) - 1, 1)) if len(st["vols"]) > 1 else 0
        _t = datetime.fromtimestamp(k, EASTERN)
        hm = _t.hour * 60 + _t.minute
        if hm < 570:
            continue
        if st["armed"] and c < zone * (1 - ZONEFLIP_BAND):
            st["armed"] = False; st["wick"] = None; st["flush_low"] = None   # clean zone loss → disarm
        if 570 <= hm <= 585 and not st["armed"]:
            if (open930 > 0 and (open930 - l) / open930 >= ZONEFLIP_FLUSH
                    and zlo <= l <= zhi and avgv > 0 and v >= 2.0 * avgv):
                st["armed"] = True; st["wick"] = None; st["flush_low"] = l
        if not st["armed"]:
            continue
        st["flush_low"] = min(st["flush_low"], l) if st["flush_low"] else l
        if st["wick"] and c > st["wick"][0] and fired is None:
            if not _bucket_fresh(k, sym=sym):              # 7/28 stale-fire guard (8/5 halt-aware)
                _log_stale_fire(sym, "zone_flip", k, round(c, 4))
                st["n"] += 1
                st["armed"] = False; st["wick"] = None; st["flush_low"] = None
                continue
            # stop = flush low − 1 tick (tested), floored at c×0.93 (7% cap, reclaim-style)
            fired = {"stop": round(max(st["flush_low"] - 0.01, c * 0.93), 4),
                     "wick_high": st["wick"][0], "flush_low": st["flush_low"],
                     "zone": zone, "zone_src": z["src"], "seq": st["n"], "px": round(c, 4), "k": k}
            st["n"] += 1
            st["armed"] = False; st["wick"] = None; st["flush_low"] = None
            continue
        rng = h - l
        if rng > 0 and zlo <= l <= zhi and (c - l) / rng >= 0.5 and c >= zone * (1 - ZONEFLIP_BAND):
            st["wick"] = (h, l)
    return fired


def detect_vwap_reclaim(completed, price, vwap):
    """RETIRED 7/19 (kept for reference only — no callers). The naive 1-gate reclaim: era record
    −$228.81 across 32 trades. Replaced by kev_reclaim_step (3-gate grammar) above."""
    try:
        if vwap <= 0 or len(completed) < 5:
            return None
        conf = completed[-1]
        chi, clo, cop, ccl = _bar_high(conf), _bar_low(conf), _bar_open(conf), _bar_close(conf)
        prior_below = any(_bar_close(b) < vwap for b in completed[-4:-1])   # was under VWAP (lost it)
        reclaim = ccl > vwap and ccl > cop and clo <= vwap * 1.005          # closed back above, green, dipped to it
        if not (prior_below and reclaim) or price <= ccl:
            return None
        vc = _bar_vol(conf)
        vp = sum(_bar_vol(b) for b in completed[-4:-1]) / 3 if len(completed) >= 4 else 0
        if vp > 0 and vc < vp * EMA_BOUNCE_VOL_MULT:                        # volume must return on the reclaim
            return None
        return {"stop": round(min(clo, vwap) * 0.99, 4)}                    # risk below the reclaim low / VWAP
    except Exception:
        return None


# ── ROCKET CATCHER (7/21, Rocket Rider — FABLE-APPROVED corrected design) — the mid-day parabola catch.
#    DETECTOR = trailing ROCKET_VEL_BARS-min VELOCITY ≥ ROCKET_VEL_PCT (the "plowing through the levels"
#    signal — velocity, NOT volume; RVOL was REFUTED, fades spike volume too). Validated 7/21
#    (scratchpad/rocket_expand.py, 156 name-days): T=25 → 5/6 rockets, 0/95 fades = 100% precision;
#    6 live fires over 2 days, EVERY one a ≥58% mover. Fires ALL DAY (mid-day rockets launch late —
#    NO early-session window, unlike ignition). EXIT = SCALE-OUT ladder (to be built in monitor_trade,
#    NOT trail20 — Fable: detection+trail20 = +1.5% noise, detection+scale-out = +32%). rocket_catcher
#    is EXEMPT from the extension guard by design (it deliberately catches extension); NO blanket
#    gate-inversion for the legacy machines. See [[project_rocket_catcher_package.md]] Fable verdict.
ROCKET_CATCHER   = os.environ.get("ROCKET_CATCHER", "0") == "1"    # SUPERSEDED 7/24 by HIDDEN_ENTRY (10s Kev spec): 1-min 20-EMA anchor structurally untouchable by true parabolas (STAK+ZCMD armed-never-fired) + adverse selection. env=1 resurrects.
# ── DAY-GAIN FLOOR (7/22, Marcos: "if a stock isn't jumping 30% or more, we shouldn't be wasting
#    time" — Kev's own hunting ground is the top of the gainers board). Kill-test daygain_floor_killtest
#    (124 matched trades): floor on LEGACY machines improves −$94.16 → +$70.79 (+$164.95), sweep-robust
#    T∈[10,40], improvement intact ex-ZYBT. EXEMPT: curl/reversal lanes (their winners live at ugly
#    day-gains — SOBR +$93.56 reclaim was DOWN 23% at entry) and KEV-SHEET names (his explicit levels
#    outrank this homegrown filter — AEHL "over 1.00" must fire regardless of day-gain). T=30 is a
#    HOMEGROWN number (Kev never quantifies) → translation registry; recalibrate from the stamped
#    day_gain column as live n accrues. env DAYGAIN_FLOOR=0 = kill-switch.
#    30→15 (Marcos 7/26, DRY_RUN-learning doctrine): 7/26 corrected-P&L re-sweep kept the floor's
#    EDGE (every T∈[15,40] positive) but the forward blocked-cohort (n=17, 7/22-24) showed blocked
#    fires ≈ kept fires (1.51R vs 1.30R median MFE) — the 15-30 band needs REAL trade outcomes, not
#    canaries: "we need to test this fucker and can't if we don't collect real data." Floor 15 =
#    bottom of the corrected sweep's positive plateau (+$92.56). Revisit Friday 7/31 w/ forward n. ──
DAYGAIN_FLOOR_PCT = float(os.environ.get("DAYGAIN_FLOOR", "15"))
DAYGAIN_LEGACY    = ("ignition", "flat_top", "ma_pullback", "orb", "ema_bounce")

# ── IGNITION-10S (7/26, Marcos: "Move it to 10 second bars. The idea of knowingly being blind is dumb.")
#    Same detector thesis as detect_ignition (quiet base → volume-accel bar breaks it, not-yet-extended),
#    ported to the 10s stream. Two-arm kill-test (n=26 paired fires 7/23-24, RESULTS_LEDGER 7/26): the 10s
#    surge-bar entry beats the 1-min fill 17/26, medMFE 0.90→1.06R, ≥2R 5→9, at the SAME price (−0.05%)
#    — the 1-min close is a median 49s late and 96% of fills land after the intraminute peak. Downstream
#    is UNCHANGED: fires feed the same "ignition" lane (vel5 floor, day-gain floor, extension guard,
#    chart gate, momentum, sizing all still apply — this changes the EYES, not the gates).
#    env IGNITION_10S=0 falls back to the 1-min detector (detect_ignition stays intact below).
IGNITION_10S      = os.environ.get("IGNITION_10S", "1") == "1"
_IG10_BASE_BARS   = IGNITION_BASE_LOOKBACK * 6     # base window: the same 4 minutes, in 10s bars
_IG10_MIN_ABS_VOL = IGNITION_MIN_ABS_VOL / 6.0     # per-10s-bar translation of the 1-min liquidity floor
_ig_cursor: dict = {}   # (day, sym) -> last processed 10s bucket epoch (ignition feed)
_ig10_st:   dict = {}   # sym -> {"d": date, "bars": [(epoch,o,h,l,c,v)...], "openp": session open}

def ignition_10s_step(sym, new_bars):
    """Step the 10s ignition machine with newly COMPLETED 10s bars [(epoch,o,h,l,c,v),...].
    Mirrors detect_ignition condition-for-condition on the finer series: RTH-only state, session
    open = first RTH 10s bar's open, base = prior 4 min of 10s bars (max CLOSE = wick-robust ref),
    candidate = just-closed bar with vol ≥ IGNITION_VOL_MULT × base avg + green + strong close +
    close over base_hi + ext within [−5%,+15%] of the open. The live-price no-chase re-check and
    the once-per-ticker cap live at the CONSUME branch (they need the stream price / cache).
    Returns {stop, base_hi, base_lo, volx, ext_pct, px, openp, bar_epoch} or None. Never raises."""
    try:
        if not new_bars:
            return None
        today = datetime.now(EASTERN).strftime("%Y-%m-%d")
        st = _ig10_st.get(sym)
        if st is None or st["d"] != today:
            st = {"d": today, "bars": [], "openp": 0.0}
            _ig10_st[sym] = st
        fire = None
        for k, o, h, l, c, v in new_bars:
            et = datetime.fromtimestamp(k, EASTERN)
            m = et.hour * 60 + et.minute
            if m < 570 or c <= 0:
                continue                                   # premarket / bad bar: not this machine's regime
            if st["openp"] <= 0 and o > 0:
                st["openp"] = o                            # first RTH 10s bar's open = session open
            base = st["bars"][-_IG10_BASE_BARS:]
            st["bars"].append((k, o, h, l, c, v))
            if len(st["bars"]) > _IG10_BASE_BARS * 3:
                st["bars"] = st["bars"][-_IG10_BASE_BARS * 2:]
            if m > 570 + IGNITION_WINDOW_MIN:
                continue                                   # same 90-min envelope as the 1-min detector
            if len(base) < IGNITION_BASE_MIN * 6 or st["openp"] <= 0:
                continue
            base_hi_c = max(b[4] for b in base)            # max CLOSE = wick-robust breakout reference
            _lows = [b[3] for b in base if b[3] > 0]
            if not _lows:
                continue
            base_lo  = min(_lows)
            base_vol = (sum(b[5] for b in base) / len(base)) or 1
            rng = (h - l) or 1e-9
            strong = (c - l) / rng
            ext_bar = (c - st["openp"]) / st["openp"]
            if (v >= IGNITION_VOL_MULT * base_vol          # volume ACCELERATION — the tell
                    and v >= _IG10_MIN_ABS_VOL             # liquidity floor (per-bar scaled)
                    and c > o                              # green ignition bar
                    and strong >= IGNITION_STRONG          # strong close (buyers won the bar)
                    and c >= base_hi_c                     # breaks the quiet base (by close)
                    and IGNITION_MIN_EXT <= ext_bar <= IGNITION_MAX_EXT):
                if not _bucket_fresh(k, sym=sym):            # 7/28 stale-fire guard (8/5 halt-aware)
                    _log_stale_fire(sym, "ignition10s", k, round(c, 4))
                    continue
                fire = {"stop": round(base_lo * (1 - ZONE_STOP_BUFFER), 4),
                        "base_hi": round(base_hi_c, 4), "base_lo": round(base_lo, 4),
                        "volx": round(v / base_vol, 1), "ext_pct": round(ext_bar * 100, 1),
                        "px": round(c, 4), "openp": round(st["openp"], 4), "bar_epoch": k}
        return fire                                        # latest qualifying bar in the fed batch
    except Exception as e:
        print(f"⚠️  ignition_10s_step error ({e}) — no entry this pass")
        return None

ROCKET_VEL_PCT   = float(os.environ.get("ROCKET_VEL_PCT", "25"))    # % over the window (Fable T=25 = 0 false-pos/95 fades)
ROCKET_VEL_BARS  = int(os.environ.get("ROCKET_VEL_BARS", "5"))      # trailing 1-min bars = a 5-minute velocity window
ROCKET_DAILY_CAP = int(os.environ.get("ROCKET_DAILY_CAP", "3"))     # max rocket entries/day (Fable: cap 2-3)
_rocket_day      = {"d": None, "n": 0}                              # daily rocket-entry counter (resets per ET date)

def detect_rocket(session_bars, price):
    """ROCKET CATCHER detector — fires when trailing ROCKET_VEL_BARS-min velocity ≥ ROCKET_VEL_PCT%.
    Returns {vel, stop} on a fire, else None. Stop = low of the velocity window (natural invalidation
    of the spike), floored at price*0.75 so sizing risk is bounded (≤25%) on a violent name. Pure;
    any error → None (never crash the scan). Exit is scale-out, handled in monitor_trade — NOT here."""
    try:
        if not ROCKET_CATCHER or not session_bars or len(session_bars) < ROCKET_VEL_BARS + 1:
            return None
        c_now = _bar_close(session_bars[-1]); c_ago = _bar_close(session_bars[-1 - ROCKET_VEL_BARS])
        if c_now <= 0 or c_ago <= 0 or price <= 0:
            return None
        vel = (c_now - c_ago) / c_ago * 100.0
        if vel < ROCKET_VEL_PCT:
            return None
        win = session_bars[-1 - ROCKET_VEL_BARS:]
        lows = [_bar_low(b) for b in win if _bar_low(b) > 0]
        stop = max(min(lows) if lows else price * 0.75, price * 0.75)   # bound risk ≤25% on a violent mover
        return {"vel": round(vel, 1), "stop": round(stop, 4)}
    except Exception:
        return None


def _recent_low_dip(bars_, level, n=3):
    """Wick-aware dip detection (7/22 #73 kill-test + hand-trace): the polled-price check misses
    one-bar WICK touches between scan cycles — DFNS 7/21 wicked its OR-high (4.50) and GMM 7/20
    dipped to 2.60 one bar after breaking, while dipped stayed False all day and both timed out.
    Checks the last n COMPLETED 1m bar lows against the level. Kill-test (orb_anchor_killtest.py,
    156 name-days): bar-low dip + confirm-curl = +0.51R mean, 58% win; movers>=40% = +1.09R
    (GMM +1.27, DFNS +1.11). Trailing-anchor variant REFUTED (worse: +0.38R, adds faders)."""
    try:
        _s = _latest_session(bars_)
        lows = [_bar_low(b) for b in _s[-1 - n:-1] if _bar_low(b) > 0]
        return any(lo <= level * (1 + PULLBACK_TOL) for lo in lows)
    except Exception:
        return False


def detect_ignition(session_bars, price):
    """IGNITION entry (7/4) — the fast-vertical catch. Reverse-engineered from the 8 fast verticals
    (ZCMD/JEM/AZI/CCTG, 6/29–7/2). Shape = QUIET early base (low vol, choppy, often BELOW VWAP) → a
    VOLUME-ACCELERATION bar breaks the base while NOT-yet-extended (+3–15%) → vertical. Operates on
    1-MIN SESSION bars and is the ONE entry NOT gated on above-VWAP. The just-closed bar is the ignition
    candidate; base = the prior N 1-min bars; base_hi = their max CLOSE (wick-robust). Re-checks the LIVE
    price is still not-extended (no chase). Tight stop = base low. Returns {stop, base_hi, base_lo, volx,
    ext_pct} or None. Any error → None (never crash the scan)."""
    try:
        if not IGNITION_ENABLED or not session_bars or len(session_bars) < IGNITION_BASE_MIN + 1:
            return None
        openp = _bar_open(session_bars[0]) or _bar_close(session_bars[0])
        if openp <= 0 or price <= 0:
            return None
        ig = session_bars[-1]                                  # the just-closed bar = ignition candidate
        m = _bar_et_min(ig)
        if m is None or m < 570 or m > 570 + IGNITION_WINDOW_MIN:
            return None                                        # early-session only (9:30 → +window)
        base = session_bars[-1 - IGNITION_BASE_LOOKBACK:-1]
        if len(base) < IGNITION_BASE_MIN:
            return None
        base_hi_c = max(_bar_close(b) for b in base)           # max CLOSE = wick-robust breakout reference
        base_lo   = min(_bar_low(b) for b in base if _bar_low(b) > 0)
        base_vol  = (sum(_bar_vol(b) for b in base) / len(base)) or 1
        v, o, c, h, l = _bar_vol(ig), _bar_open(ig), _bar_close(ig), _bar_high(ig), _bar_low(ig)
        rng = (h - l) or 1e-9
        strong = (c - l) / rng                                 # close position in the bar's range
        ext_bar = (c - openp) / openp
        ext_live = (price - openp) / openp                     # don't enter if it already ran past the cap live
        if (v >= IGNITION_VOL_MULT * base_vol                  # volume ACCELERATION — the tell
                and v >= IGNITION_MIN_ABS_VOL                  # liquidity floor
                and c > o                                      # green ignition bar
                and strong >= IGNITION_STRONG                  # strong close (buyers won the bar)
                and c >= base_hi_c                             # breaks the quiet base (by close)
                and ext_bar >= IGNITION_MIN_EXT               # breaking UP from near the open (not a dump-bounce)
                and ext_bar <= IGNITION_MAX_EXT               # bar close not-yet-extended
                and ext_live <= IGNITION_MAX_EXT):            # live price still not extended (no chase)
            return {"stop": round(base_lo * (1 - ZONE_STOP_BUFFER), 4),
                    "base_hi": round(base_hi_c, 4), "base_lo": round(base_lo, 4),
                    "volx": round(v / base_vol, 1), "ext_pct": round(ext_bar * 100, 1)}
        return None
    except Exception as e:
        print(f"⚠️  detect_ignition error ({e}) — no entry this pass")
        return None


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


def _confirm_reclaim(bars, level) -> bool:
    """Kev's pullback CONFIRMATION (#024/#025/#027): don't take the bare tick reclaim of a broken level —
    wait for the bought-back confirmation CANDLE. The most recent COMPLETED 1-min bar must CLOSE back above
    the level AND show buyers stepping in = a green close OR a bottoming-tail wick off the low. Permissive
    (green OR wick, either confirms) so it filters the fake pokes without over-restricting.
    NOTE: our 3-day refine test suggested a green-close filter HURT (small sample, n≈24) — this is built to
    the corpus per [[feedback_kev_is_the_bible]] and needs live-data grading; that tension is logged."""
    try:
        sess = _fresh_session(bars)   # B16: today-only — a prior-day 'confirm candle' must never fire
        comp = sess[:-1] if len(sess) >= 2 else sess     # drop the in-progress bar
        if not comp:
            return False
        b = comp[-1]
        o = float(b.get("open")  or b.get("o") or 0)
        c = float(b.get("close") or b.get("c") or 0)
        h = float(b.get("high")  or b.get("h") or c)
        l = float(b.get("low")   or b.get("l") or c)
        if c <= level:                                   # must CLOSE back above the reclaimed level
            return False
        rng = h - l
        green = c > o
        wick_off_low = rng > 0 and (min(o, c) - l) / rng >= BOTTOM_TAIL_RATIO
        return bool(green or wick_off_low)
    except (TypeError, ValueError):
        return False


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

# VWAP must be SESSION-ANCHORED (from the open) and INCLUDE pre-market, to match Webull's chart. Two bugs it fixes:
#   (1) entry/dashboard VWAP fetched RTH-only (no pre-market) → ~2-4% low on gappers;
#   (2) the health-fold EXIT computed VWAP over only the last ~45 M1 bars (the EMA window) = a ROLLING window that
#       runs 10-22% HIGH on a runner → folds winners early. Fetch a full pre+RTH session set for VWAP everywhere.
B11_BLIND_SECS  = 150    # B15 fix (7/15): must EXCEED the healthy 48–72s jittered fetch cadence by 2+ cycles.
                         # 60s was INSIDE the cadence → "blind" every healthy cycle tail → intrabar misfires
                         # (UBXG/VMAR). NVVE's real outage was ~360s — 150s still catches it 2.4× sooner.
B11_BELOW_SECS  = 20     # stream must print below the stop SUSTAINED this long (one bad tick must not fire it)
_rest_cool = [0.0]       # 7/14: global 429 cooldown epoch — AUX fetchers shed load first, monitors keep cadence
VWAP_SESSION_COUNT      = 800   # bars ≥ full pre-market(330) + RTH(390) + margin — 600 lost the pre-market anchor
_svwap_cache: dict = {}          # 7/14: {ticker: (3min-bucket, session_vwap)} — kills the per-minute 800-bar refetch
                                # late-day on heavy-premarket names (7/11 audit A7); _latest_session() trims prior days
VWAP_SESSION_CACHE_SECS = 90    # session VWAP moves slowly — refresh less often than the 30s bar cache to limit API load
# Feature flags — DEFAULT OFF so the deployed default == current live/validated behavior. Flip only after re-validation.
HEALTH_VWAP_SESSION     = True  # exit health-fold: session VWAP (Webull-matching) — validated +19.2R/0-worse across 8 archived days (7/10)
ENTRY_VWAP_PREMARKET    = True  # 7/15 VALIDATED (Marcos called it: "Kev trades the Webull VWAP, PM included").
                                # Replay of 45 era entries vs the ext mirror: RTH-only vs pre+RTH VWAP gap ≥3%
                                # on 14/45, ABOVE/BELOW VERDICT FLIPPED on 12/45 (27%) — incl. BJDX 7/14 (bot
                                # said front-side at 1.49 vs its 1.426; chart VWAP was 1.592 → back-side, −$36).
                                # RTH-only reads LOW on gappers (PM volume anchors higher) → systematically
                                # passed back-side entries. Entry VWAP must be the line on Kev's screen.

# ── RECORDER TICK-VWAP (7/16, Marcos: "the data is already contaminated — no reason to wait") ──
# The bar-rebuilt VWAP carries a measured +0.2–1% high bias that SCALES with volatility (4-ticker
# ground truth vs live charts). The recorder's tick-VWAP (price×Δcumvol, premarket-anchored) is the
# structural fix. Default ON; env RECORDER_VWAP=0 is the kill switch. Guards make worst-case = the
# bar-line status quo: freshness ≤180s, price catastrophe band, ≤5% divergence clamp vs bar line.
RECORDER_VWAP            = os.environ.get("RECORDER_VWAP", "1") == "1"
RECORDER_VWAP_STALE_SECS = 240   # recorder snapshots 60s + persists 90s → typical point age ≤150s;
                                 # 240 tolerates one missed persist. Older = recorder gap → bar line
                                 # holds (B17 doctrine). Live-tested 7/16: 196s-old point at 300s
                                 # persist cadence was correctly rejected — hence the cadence fix.
# ── #87 ALP-PRIMARY (7/22, Marcos: "We already know the issues of Webull. We have been hurt by the
# issues of Webull... throw Alpaca into the deep end."): the tick-VWAP line prefers the Alpaca SIP
# capture (~ALPVWAP: exact trade-weighted, premarket-anchored, no counter math — the F1 leak class
# can't exist there) and falls back to the Webull recorder (~vwap), then to the callers' bar line.
# Same point format, same staleness gate, same _tick_vwap_ok sanity clamps on whichever wins.
# DATA_PRIMARY=webull is the one-env instant revert.
DATA_PRIMARY = os.environ.get("DATA_PRIMARY", "alpaca").strip().lower()
_TICKVWAP_SUFFIXES = ("~ALPVWAP", "~vwap") if DATA_PRIMARY != "webull" else ("~vwap", "~ALPVWAP")
_tick_vwap_cache: dict = {}      # ticker -> (fetched_epoch, value_or_None)

def _fetch_series_last_vwap(series_name, now):
    """Newest fresh point of one dashboard series (value in 'close'), else None."""
    try:
        url = os.environ.get("SCREENER_URL", "").rstrip("/")
        if not url:
            return None
        day = datetime.now(EASTERN).strftime("%Y-%m-%d")
        r = requests.get(f"{url}/api/bars", params={"date": day, "ticker": series_name}, timeout=6)
        if r.status_code == 200:
            pts = (r.json() or {}).get("bars") or []
            if pts:
                last = pts[-1]
                ts = datetime.strptime(str(last.get("time", ""))[:19],
                                       "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
                if now - ts <= RECORDER_VWAP_STALE_SECS:
                    v = float(last.get("close") or 0)
                    return v if v > 0 else None
    except Exception:
        pass
    return None

def _recorder_tick_vwap(ticker):
    """Latest tick-VWAP for ticker — vendors tried in DATA_PRIMARY preference order (#87:
    ~ALPVWAP first by default, Webull ~vwap fallback). Returns None when both are missing or
    stale — callers hold the bar line (no behavior change)."""
    now = time.time()
    c = _tick_vwap_cache.get(ticker)
    if c and now - c[0] < 45:
        return c[1]
    val = None
    for _sfx in _TICKVWAP_SUFFIXES:
        val = _fetch_series_last_vwap(f"{ticker}{_sfx}", now)
        if val:
            break
    _tick_vwap_cache[ticker] = (now, val)
    return val

def _tick_vwap_ok(tick, bar, price):
    """Sanity gate before the tick line may replace the bar line. Catastrophe band vs price kills
    unit-scale bugs (the 2,000,000-'vwap' class); the 5% divergence clamp vs the bar line allows
    the real ~1% correction but never a wild swap. Bar missing (B17) → price band alone decides."""
    if not tick or tick <= 0:
        return False
    if price and price > 0 and not (0.5 * price <= tick <= 2.0 * price):
        return False
    if bar and bar > 0 and abs(tick - bar) / bar > 0.05:
        return False
    return True

# ── 7/10 ENTRY-GATE + WIDE-STOP FIX STACK (all DEFAULT OFF until the 9-day completion grade ranks them) ──
# check_momentum BUNDLES three gates; the reversal exemption (vwap_reclaim/ignition/bounce) was meant only for the
# momentum gate but silently skipped the UNIVERSAL rules too (the 7/10 audit: flagged fills −$14.95 vs clean +$19.65).
# ── 7/26 (Marcos "ship all 4"): BOTH FLAGS ON. The 7/26 momentum retirement silently removed these
#    from the slow lanes (they were bundled inside check_momentum — the exact accident the 7/10
#    un-bundle anticipated; the flags were just never flipped). With every live lane momentum-exempt,
#    these flags are now the ONLY liquidity/topping-tail protection. Topping tail = Kev verbatim
#    ("don't enter into a candle rejected at the high"); liquidity floor validated 7/7 (thin n=2 —
#    both dead money, zero winners flagged). Carve-out: ignition skips the LIQUIDITY window only —
#    it measures the 3 completed 1-min bars = ignition's QUIET BASE (quiet by design); the machine
#    already floors volume on the SURGE bar itself (_IG10_MIN_ABS_VOL), the bar that matters. ──
ENTRY_GATE_TOPPING_TAIL = os.environ.get("ENTRY_GATE_TOPPING_TAIL", "1") == "1"
ENTRY_GATE_LIQUIDITY    = os.environ.get("ENTRY_GATE_LIQUIDITY", "1") == "1"
# Wide-stop fixes — THREE contenders, ranked head-to-head in the harness (the −7% was a MADE-UP number; do not inherit it):
STOP_MAX_PCT            = 0.0    # A: clamp the structural stop to entry×(1−X) for ALL types. 0=off; calibrate from data, don't assume 7%
MAX_STOP_DIST_PCT       = 0.0    # C: Kev tight-setup gate — SKIP entries whose structural stop is >X% away (wide base ≠ Kev setup). 0=off
# ── MINIMUM STOP WIDTH (7/27, Marcos's management call) — the mirror of the wide-stop gate: a stop
#    <X% of entry on these names sits inside normal wiggle → the risk definition is fiction and
#    risk-sizing inflates the share count until noise = −2R (KIDZ: 1.5% stop → 1,854 sh → −$36.71).
#    Era evidence: permutation p=0.0047, out-of-sample +$385.16, 15/15 thresholds help the unseen
#    half, 8/2 days (killtest_minstop.py + RESULTS_LEDGER 7/27). Set at 6% (the era optimum) BY
#    MARCOS'S DECISION over the pre-registered 5%; every reject is decision-logged with its width
#    band so the 4–5% and 5–6% rejects are a live shadow cohort (graded Friday 7/31 vs real bars).
#    MIN_STOP_PCT=0 env = kill switch.
# 8/1 (Marcos: "let's go for 4% and see where the data takes us") — floor 6->4. The cliff is
# ARITHMETIC (slip 1.477%/entry = 0.37R at 4%, 0.74R at 2%; G7 n=784 monotone) and the shadow
# bands graded 4-6% rejects as forfeited winners (~$65/4 days, n=6 — thin, hence the week of
# finer-band data below). Live cells 4-5/5-6 from kept trades' stop_width_pct; death zone <4
# stays shadow-graded via the refined reject bands. Friday 8/8 sets the floor where the edge is.
MIN_STOP_DIST_PCT       = float(os.environ.get("MIN_STOP_PCT", "4.0")) / 100.0
# ── 8/13 STOP-COHERENCE FLOOR (Marcos: "ship the 0.5% floor tonight... revisit Friday") ──
# NOT a setup-quality gate — a does-the-trade-still-exist check (family: liquidity floor).
# The BQ 8/12 12:46 specimen: hidden fire at $1.42 (stop $1.349, sane 5%) executed 239s later
# at $1.351 — 0.07% above its own stop → planned risk $0.74, −11.7R blow-through. ALL lanes,
# no exemptions (min-stop exemptions don't apply; a stop 0.07% wide isn't structural, it's dead).
# Era census 8/13 (killtests/stop_coherence_census): <0.5% = 3 trades net −$17.50 (pure);
# 1% would refuse 4 winners (−$51.54). Kill switch: STOP_COHERENCE_MIN_PCT=0. Friday re-grade.
STOP_COHERENCE_MIN_PCT  = float(os.environ.get("STOP_COHERENCE_MIN_PCT", "0.5")) / 100.0
# ── 8/13 #54: blue-sky map TTL — a blue-sky map is only as good as its freshness; older than
#    this it counts as ABSENT for the mapless gate (fail-closed). Kill: huge value.
BLUESKY_TTL_SECS        = int(os.environ.get("BLUESKY_TTL_SECS", "600"))
# 7/31 MINIMUM MARKED RUNWAY (Marcos): refuse a trade whose road to the next MARKED level is under
# this many R. Risking a full R to reach 0.1R of reward is a bad bet regardless of setup quality.
# 0 = gate off. Fail-open: only a NUMERIC runway can block (see the gate site for the evidence).
MIN_RUNWAY_RR           = float(os.environ.get("MIN_RUNWAY_RR", "1.0"))
# ── 8/4 CLASS-AWARE RUNWAY (Marcos: "scale points are not walls but they are levels of
# resistance until crossed"; kill-test runway_graded_20260804: RUNG>=0.5R +$91.01 plateau,
# MAJORs all-taken −$148.67, majors-at-1R correct). MAJOR = break/next_supply match or a
# whole/half-dollar within ~1c; everything else = RUNG (intermediate target). The gate needs
# RUNWAY_MIN_RR_MAJOR of road to a MAJOR but only RUNWAY_MIN_RR_RUNG to a RUNG. MIN_RUNWAY_RR=0
# remains the master kill switch. Continuous road_rr + class + fine band stamped on EVERY
# conversion and reject so Friday can replay ANY threshold (flat T=0.3 was the sweep's own
# ship-candidate at +$117.65 — graded head-to-head from the stamps, Marcos's call 8/4).
RUNWAY_MIN_RR_RUNG      = float(os.environ.get("RUNWAY_MIN_RR_RUNG", "0.5"))
RUNWAY_MIN_RR_MAJOR     = float(os.environ.get("RUNWAY_MIN_RR_MAJOR", "1.0"))
# ── 8/5 BACK-SIDE GATE (Marcos: "this will allow the bot to see that the ticker is on a
# downtrend"; kill-test backside_20260805: entries 15-30% below a >=20-min-stale session high
# lost ~-$147 era-wide at a -$8/trade mean with ~no winners forfeited in-band, while front-side
# entries were the only profitable cohort). A pullback SHAPE is identical on the way up and the
# way down — this gate reads WHERE IN THE MOVE'S LIFE the entry sits. Band-block: 15-30% off a
# stale high = the distribution zone. >30% = capitulation-flush territory (n=4, held up) stays
# open, as does dip_rip (flush-buying is its design). Session high tracked close-based from the
# curl feed (resets on restart -> gate fails open until it re-learns; deliberate).
# Kill switch: BACKSIDE_GATE=0. Band edges re-graded Friday from the dd/stale stamps.
BACKSIDE_GATE     = os.environ.get("BACKSIDE_GATE", "1") == "1"
BACKSIDE_DD_LO    = float(os.environ.get("BACKSIDE_DD_LO", "15"))
BACKSIDE_DD_HI    = float(os.environ.get("BACKSIDE_DD_HI", "30"))
BACKSIDE_STALE_MIN= float(os.environ.get("BACKSIDE_STALE_MIN", "20"))
BACKSIDE_EXEMPT   = {"dip_rip"}

def _backside_check(sym, price):
    """Returns (dd_pct, stale_min, block) from the leader tracker's session-high state.
    Fail-open on any missing data."""
    try:
        day = datetime.now(EASTERN).strftime("%Y-%m-%d")
        rec = _leader_day.get((day, sym))
        if not rec or not rec.get("rth_hi") or not price:
            return None, None, False   # 8/5: RTH-only high (matches the kill-tested definition)
        dd = 100.0 * (rec["rth_hi"] - price) / rec["rth_hi"]
        nowm = datetime.now(EASTERN).hour * 60 + datetime.now(EASTERN).minute
        stale = nowm - rec.get("rth_hi_m", nowm)
        block = (BACKSIDE_GATE and BACKSIDE_DD_LO <= dd < BACKSIDE_DD_HI
                 and stale >= BACKSIDE_STALE_MIN)
        return round(dd, 1), stale, block
    except Exception:
        _gate_failopen("backside")
        return None, None, False

# 8/4 RUNG RATCHET (Marcos override #4; engine-H replay level_exits_20260804: 92% wins/ties,
# worst give-back $5.24 vs A). Runner hard floor = highest map rung cleared by a 1-min close.
RUNG_RATCHET            = os.environ.get("RUNG_RATCHET", "1") == "1"

def _runway_level_class(ticker, tgt, rec=None):
    """MAJOR = the sheet's break/next_supply (±0.5%) or a whole/half-dollar within 1.1c; else RUNG.
    8/7 auditor #5: caller may pass the EFFECTIVE rec so an auto-map break classes MAJOR."""
    try:
        if tgt is None:
            return None
        tgt = float(tgt)
        lvd = rec if isinstance(rec, dict) else ((_fetch_kev_levels() or {}).get(ticker) or {})
        for k in ("break", "next_supply"):
            v = lvd.get(k)
            if v is not None and float(v) > 0 and abs(float(v) - tgt) / tgt < 0.005:
                return "MAJOR"
        frac = tgt - int(tgt)
        if min(abs(frac), abs(frac - 0.5), abs(frac - 1.0)) < 0.011:
            return "MAJOR"
        return "RUNG"
    except Exception:
        return "RUNG"

def _road_band(rr):
    """Fine road bands for Friday's threshold curves (mirror of the min-stop fine bands)."""
    if not isinstance(rr, (int, float)):
        return str(rr) if rr else None
    for hi, lab in ((0.2, "<0.2"), (0.3, "0.2-0.3"), (0.4, "0.3-0.4"), (0.5, "0.4-0.5"),
                    (0.75, "0.5-0.75"), (1.0, "0.75-1")):
        if rr < hi:
            return lab
    return ">=1"
# ── 7/31 BREAK-SIDE GATE (Marcos: "I want our findings to get a real test on Monday and you can
# shadow the opposite" → "yes, definitely"). Joint grade n=56 (7/29-31): entries ABOVE the marked
# break lose EVEN WITH ROAD OPEN (−$13.73/e, 33% win, n=12) while at/below wins (+$12.67/e, 64%,
# n=25). 4th independent confirmation of buy-below-the-level. STATIC break BY MEASUREMENT: the
# dynamic swing-re-anchor FAILED its pre-registered kill-test (breakside_dynamic_20260731.py —
# TOL=0 identical to static; TOL=2% degrades PASS to −$1.23/e; the retest-chase zone lost −$216.86
# on 11 trades). Freshness rides the LIVE RE-READ pipeline (10 v2+ maps 7/31, median 5.7 min
# exhaustion→new map, latency now stamped, cap raised to 3).
# SCOPE: vwap_reclaim, hidden_entry, ignition. dip_rip EXCLUDED — its thesis is buying resumption
# OVER the level (AMIX +$39.46 at +2.5% above). Chart lanes EXCLUDED — their No-Break-No-Trade
# gate requires above-break; flipping a settled gate is a separate Fable question.
# KNOWN COST, on the record: blocks the MGRX-10:54 class (+$29.99 at +28.6% with road open) and is
# dark on a name post-breakout until a re-read posts a fresh level or price returns to the map.
# FAIL-OPEN like runway: no marked break -> PASS (ignorance never blocks; only evidence does).
# Kill: BREAKSIDE_GATE=0.
# WRONG WHEN (pre-registered): the blocked cohort's forward counterfactual (`breakside_reject`
# rows, full ticket) out-earns the allowed cohort.
BREAKSIDE_GATE          = os.environ.get("BREAKSIDE_GATE", "1") == "1"
BREAKSIDE_MAX_PCT = float(os.environ.get("BREAKSIDE_MAX_PCT", "1.0"))
# 8/8 (Ombudsman hearing #1, breakside_tolerance_20260808, frozen rule pre-run): tol 1% admits
# 4 era rejects for +$581.70 (worst −$48.19) vs $0 at tol 0 — SHIP-CANDIDATE met. CAVEAT on the
# ledger: 2 of 4 admits = YJ 8/7 (same name/day). At-the-line entries (<=1% over the break) are
# now entries; the chase-refusal (>1%) stands. Was 0.0 since 7/31.
BREAKSIDE_LANES         = set(filter(None, (s.strip() for s in os.environ.get(
    "BREAKSIDE_LANES", "vwap_reclaim,hidden_entry,ignition,ma_pullback,ema_bounce").split(","))))
# 8/8: ma_pullback/ema_bounce added on the YJ 8/7 specimen (bought $10.95 = +32% over the map's
# break through this exact hole, against our own SKIP read; the era side-door evidence is thin
# beyond it — one-day specimen, flagged honestly). Same 6% tolerance; kill via env override.

# 8/3 dead-zone kill-test verdict (deadzone_20260803.py, frozen rules): TAPE lanes below a
# never-broken-today break bleed (n=12, -$143.89); chart/ignition pre-break measured POSITIVE
# and stamp only. Gate is fail-open on unknown day-high (uncaptured names) and env-revertible.
TAPE_PREBREAK_GATE = os.environ.get("TAPE_PREBREAK_GATE", "1") == "1"
TAPE_PREBREAK_LANES = set(filter(None, (s.strip() for s in os.environ.get(
    "TAPE_PREBREAK_LANES", "hidden_entry,vwap_reclaim,zone_flip").split(","))))
# 8/3 CHART CEILING GATE (Marcos override, recorded: cohort n=5 -$50.75 mean -$10.15, UNDER the
# frozen n>=8 bar; his call after FUSE -$64 — "ship the chart lane block, shadow the alternative").
# CHART lanes only: entry ABOVE the map's last target = the map says the road is SPENT. With
# re-reads live (#25) a fresh map lifts the block naturally (new targets -> in_range) — this is
# the #28 stand-down in its narrow, self-releasing form. Tape lanes untouched (blue-sky cohort
# bimodal: ZYBT-class tape winners live up there). Fail-open: no break on sheet -> no zone read.
CHART_CEILING_GATE = os.environ.get("CHART_CEILING_GATE", "1") == "1"
CHART_CEILING_LANES = set(filter(None, (s.strip() for s in os.environ.get(
    "CHART_CEILING_LANES", "flat_top,ma_pullback,orb,ema_bounce,dip_rip").split(","))))
# 8/8 (#28, promoted by the freshness acceptance: at fresh highs the auto-map opens breakside,
# so the BLOW-OFF guard must be the READ made STICKY — YJ 8/7: ceiling stood it down 11:44,
# the same lane bought the top 11:51 on the same unchanged read). A ceiling stand-down now
# BINDS the ticker's chart lanes until a FRESH read (map _ts changes) arrives. In-memory;
# derivable after one ceiling fire post-restart (8/7 restart law: degradation, not loss).
# Kill: STANDDOWN_STICKY=0.
STANDDOWN_STICKY = os.environ.get("STANDDOWN_STICKY", "1") == "1"
# ── 8/8 (#37) HALT-LADDER LANE — SHADOW-FIRST. Two-stage trigger from the 8/7-8/8 studies:
# ARM (10s, era-proven: 110 arms +$840.93, mean +$7.64, worst day −$145): LULD band-proximity
# (px/ref5min−1)/band >= HALT_ARM_PROX and 1-min vel >= HALT_ARM_VEL, CROWNS ONLY (the live
# universe standing in for the replay's halting set — flagged in the ledger). CONFIRM (5s,
# n=5 specimens — accumulating): trailing-60s uptick-ratio >= 0.8 AND max-retrace <= 1%
# ("the tape stops breathing"). This is the bot's FIRST 5s consumer — the record-only doctrine
# is CONSCIOUSLY retired for this one read (rig pin updated same commit). Detect logs halt_arm
# rows always; conversion only when HALT_LANE_CONVERT=1 (DEFAULT 0 — Monday runs shadow).
HALT_LANE          = os.environ.get("HALT_LANE", "1") == "1"
HALT_LANE_CONVERT  = os.environ.get("HALT_LANE_CONVERT", "0") == "1"
HALT_ARM_PROX      = float(os.environ.get("HALT_ARM_PROX", "0.7"))
HALT_ARM_5S        = os.environ.get("HALT_ARM_5S", "1") == "1"   # 8/8: arm on 5s feed (10s fallback)
HALT_CONFIRM_GATE  = os.environ.get("HALT_CONFIRM_GATE", "0") == "1"   # 8/8: confirm = stamp only (refuted as gate)
HALT_ARM_VEL       = float(os.environ.get("HALT_ARM_VEL", "5.0"))
_halt_arm_t = {}   # ticker -> last arm log (cadence)
_halt_early_t = {}  # 8/8: early-arm shadow cadence

_seam_shadow_t = {}   # 8/8 #38 fire cadence
SEAM_CONVERT = os.environ.get("SEAM_CONVERT", "1") == "1"   # Marcos 8/8: paper book -> live test

def _seam5_check(t):
    """#38 shadow: on 5s bars — front side (>=90%% of session-window high), up-phase, pullback
    >=1.5%% from running peak, and the LAST 5s bar closes back above the pullback's high.
    Returns the would-be ticket dict or None. Frozen rules = ride_seams_5s_20260807."""
    try:
        # 8/10: through the _alp5_feed choke point (hot5 primary) — the seam detector spent its
        # first shadow week reading the lagged archive; zero fires 8/10 = the lag, not the tape.
        _f5 = _alp5_feed(t, n=720)
        if len(_f5) < 60:
            return None
        _ks5 = sorted(_f5)
        cl = [_f5[k]["c"] for k in _ks5]
        hi = [_f5[k]["h"] for k in _ks5]
        lo = [_f5[k]["l"] for k in _ks5]
        px = cl[-1]
        sess_hi = max(hi)
        if px < sess_hi * 0.90:
            return None
        w3 = cl[-36:]
        if px <= sum(w3) / len(w3):
            return None
        w2h, w2l = hi[-24:-1], lo[-24:-1]
        peak = max(w2h); trough = min(x for x in w2l if x > 0)
        if peak <= 0 or (peak - trough) / peak * 100 < 1.5:
            return None
        pb_hi = max(h for h, l in zip(w2h, w2l) if l <= trough * 1.002)
        if px > pb_hi and cl[-2] <= pb_hi:
            return {"price": round(px, 4), "stop": round(trough, 4),
                    "pull_pct": round((peak - trough) / peak * 100, 1),
                    "peak": round(peak, 4),
                    "hi_window": "60m"}   # audit F1: the 90% gate measures a 1-HOUR high, not session — stamped so grading knows
        return None
    except Exception:
        return None

def _alp5_feed(t, n=360):
    """5s bars as {sec: {"c","l","h"}} — the arm/seam fine clock.
    8/10 REWIRED (the lagged-store lesson): PRIMARY = capture /hot5 (in-memory, fresh to the
    last closed 5s bucket); FALLBACK = dashboard archive ~ALP5S (90-180s persist lag — fine for
    HISTORY, marked so consumers can tell). Fail-soft {}. Max-age doctrine: callers get
    ("_src","hot5"/"arch") and "_age" stamped under key -1 is avoided — instead the freshest
    key speaks for itself; triggers must check recency."""
    # hot path (audit F3: per-symbol backoff — a dead capture must not stack 2.5s timeouts
    # into every 10s cycle for every crown; skip hot for 60s after a failure)
    if ALP_CAPTURE_URL and time.time() - _hot5_backoff.get(t, 0) > 60:
        try:
            r = requests.get(ALP_CAPTURE_URL + "/hot5", params={"sym": t, "n": n},
                             headers={"X-Hot-Secret": ALP_HOT_SECRET}, timeout=2.5)
            if r.status_code == 200:
                out = {}
                for k, o, h, l, c, v in (r.json().get("bars") or []):
                    out[int(k)] = {"c": float(c), "l": float(l), "h": float(h)}
                if out:
                    return out
            _hot5_backoff[t] = time.time()
        except Exception:
            _hot5_backoff[t] = time.time()
    # archive fallback (historical truth, lagged present — loud once per name per 10 min)
    try:
        import urllib.request as _ur
        d = json.load(_ur.urlopen(f"{SCREENER_URL}/api/bars?date="
                                  f"{datetime.now(EASTERN).strftime('%Y-%m-%d')}&ticker={t}~ALP5S",
                                  timeout=4))
        out = {}
        for b in (d.get("bars") or [])[-n:]:
            try:
                _dt = datetime.strptime(str(b.get("time"))[:19], "%Y-%m-%dT%H:%M:%S")
                sec = int(_dt.replace(tzinfo=timezone.utc).timestamp())
                out[sec] = {"c": float(b["close"]), "l": float(b["low"]), "h": float(b["high"])}
            except Exception:
                continue
        if out and time.time() - _alp5_lag_warn.get(t, 0) > 600:
            _alp5_lag_warn[t] = time.time()
            print(f"⚠️ {t}: 5s feed on ARCHIVE fallback (up to ~3min lag) — hot5 unavailable")
        return out
    except Exception:
        return {}

_alp5_lag_warn: dict = {}
_hot5_backoff: dict = {}   # audit F3: per-symbol hot-path backoff

def _halt5_confirm(t):
    """5s confirm: trailing 60s uptick-ratio + max retrace from the running peak. (ok, up, pull).
    Fail-CLOSED (no 5s tape -> not confirmed): the confirm exists to say 'no breathing' — absence
    of evidence is not that."""
    try:
        # 8/10: through the _alp5_feed choke point (hot5 primary) — the confirm was reading the
        # lagged archive directly, grading minute-old tape as "the final 60s".
        _f5 = _alp5_feed(t, n=14)
        if len(_f5) < 8:
            return False, None, None
        cl = [_f5[k]["c"] for k in sorted(_f5)][-14:]
        ups = sum(1 for a, b in zip(cl, cl[1:]) if b >= a) / max(len(cl) - 1, 1)
        peak = cl[0]; mp = 0.0
        for c in cl:
            peak = max(peak, c); mp = max(mp, (peak - c) / peak * 100 if peak else 0)
        return (ups >= 0.8 and mp <= 1.0), round(ups, 2), round(mp, 2)
    except Exception:
        return False, None, None
_standdown = {}   # ticker -> map _ts at stand-down; cleared when the map's _ts moves
# 8/4 ~01:15 RETEST DEPTH BAND (Marcos override #3: "set the retest level to 5%-12% and shadow
# the lanes both above and below"). SIP-complete reclassification (zone_reclass_audit_20260803):
# retest entries <=5% under an already-touched break = the BATTLE ZONE, -$13.66/t 31% win n=13
# (buying under the sell wall before it clears — the break-side trap from below); >12% = mixed
# curl-class, net -$8.26 n=6 but 67% win (CYCU +29.89 lives here — KNOWN COST, his call).
# FINAL SPEC at ship (Marcos: "only block the 1,2,3, and 4% levels to make it a meaningful
# retest but obviously keep tabs and data on all the bands"): a retest under 5% deep is INSIDE
# the battle zone around the fired break (-$13.66/t, 31% win, n=13 on SIP-complete data —
# buying under the sell wall before it clears); 5%+ = meaningful pullback, passes (keeps the
# CYCU curl class). EVERY retest — allowed or blocked — stamps a FINE DEPTH BAND
# (<1,1-2,2-3,3-4,4-5,5-8,8-12,>12) so Friday grades the whole curve, minstop-style.
# Shallow rejects carry FULL-TICKET shadows (retest_band_reject). ALL lanes. Env-revertible.
RETEST_BAND_GATE = os.environ.get("RETEST_BAND_GATE", "1") == "1"
RETEST_BAND_LO = float(os.environ.get("RETEST_BAND_LO", "5"))
RETEST_BAND_HI = float(os.environ.get("RETEST_BAND_HI", "999"))

def _retest_depth_band(d):
    """Fine band label for a retest depth pct (the 8/4 curve — graded Friday like the minstop bands)."""
    for hi, lab in ((1, "<1"), (2, "1-2"), (3, "2-3"), (4, "3-4"), (5, "4-5"), (8, "5-8"), (12, "8-12")):
        if d < hi: return lab
    return ">12"
# 7/27 LANE AGREEMENT (Marcos, settled after the lane/design pass): the floor governs lanes whose
# tight stop is an ACCIDENT of a noisy base — ignition (1-min base low; 43 era rejects −$276.73) and
# vwap_reclaim (−$180.56) — plus ma_pullback/orb where it never binds. EXEMPT = lanes where tight
# risk IS the thesis or measured positive: zone_flip + hidden_entry (10s structure; Kev's canonical
# ZYBT-0720-A specimen is a 5.5% stop — a 6% floor refuses the lane's own founding trade) and
# flat_top (3-min 4-bar base; its sub-6% era cohort is +$98.75 — the floor was taxing winners).
# Env-overridable: MIN_STOP_EXEMPT="zone_flip,hidden_entry,flat_top" (empty string = nothing exempt).
MIN_STOP_EXEMPT = set(filter(None, (s.strip() for s in os.environ.get(
    "MIN_STOP_EXEMPT", "zone_flip,hidden_entry,flat_top").split(","))))

def _min_stop_verdict(entry_price, stop_loss, entry_type=None):
    """Pure predicate for the minimum-stop-width gate (rig-tested). Returns (reject, width_pct, band):
    band buckets the SHADOW cohorts — '<4', '4-5', '5-6' are rejected under the 6% floor and graded
    forward as counterfactuals; '>=6' passes. Exempt lanes (MIN_STOP_EXEMPT) NEVER reject but still
    return width+band so their records carry the same shadow columns. Fail-open on degenerate inputs
    (the bad-stop skip upstream owns those)."""
    if not MIN_STOP_DIST_PCT or not entry_price or entry_price <= 0 or stop_loss is None:
        return False, None, None
    # Round FIRST, then compare — raw float division rejects an exactly-6% stop
    # ((10−9.40)/10 → 5.999999999999998 < 6.0; the rig's boundary case caught it).
    w = round((entry_price - stop_loss) / entry_price * 100.0, 2)
    # 8/1 FINE BANDS (Marcos: "gather data on 2,3,4,5,6 for the next week") — the death zone
    # under the 4% floor gets counterfactual cells; 4-6 are LIVE cells under the new floor.
    band = ("<2" if w < 2.0 else ("2-3" if w < 3.0 else ("3-4" if w < 4.0 else
            ("4-5" if w < 5.0 else ("5-6" if w < 6.0 else ">=6")))))
    if entry_type in MIN_STOP_EXEMPT:
        return False, w, band
    return w < MIN_STOP_DIST_PCT * 100.0, w, band

# ── REALISTIC-SIZING DRY_RUN (7/11, user-directed): trade the INTENDED live amounts on paper so every number is
# real-scale. Kev short-003 sizing: max loss ≤1% of account; shares = max_loss ÷ risk-per-share; size down = smaller
# risk. Changes SIZE only — never WHICH trades fire (gates/exits untouched) → the learning stream continues unimpeded.
RISK_BASED_SIZING       = True   # shares = risk ÷ (entry−stop), capped by notional + volume guards
RISK_PER_TRADE          = 30.0   # 1% of the intended $3,000 account — the CEILING, not a target
# ── 7/29 WIDTH-PROPORTIONAL RISK (Marcos's design; Fable-ruled; shipped same night) ──
# Kev's 1% is a ceiling he trades UNDER on choppy tape; ours was a target hit on every trade.
# Marcos: "Why risk $30 and give only 3 cents of wiggle room?" — the tight structural stop IS the
# chart reporting chop, so the bet scales to the wiggle room: risk = $30 × min(1, width/6%).
# Slippage calibration (7/29, 59 clean era stop fills: median slip ≈1.477% of entry, ~constant
# across widths) makes it decisive: expected slip tax = slip%×risk/width — $7.40 at 6% width but
# $44 at 1% (more than the whole plan); proportional risk caps the tax ~constant by construction.
# Era counterfactual (exact method, 182 trades, defects excised): −$1,007.55 → −$678.84, ZERO
# winners forfeited. Property: below REF width, notional collapses to a constant ~$500 — the
# $1,000-cap collision class is eliminated, not patched. WRONG WHEN a tight-stop setup carried
# real edge deserving full size — every scaled entry logs `risk_scaled` so that cost is MEASURED
# (forfeited-winner ledger = the kill trigger). Kill switch: RISK_PROP=0 (flat $30 exactly).
RISK_PROP     = os.environ.get("RISK_PROP", "1") == "1"
RISK_PROP_REF = float(os.environ.get("RISK_PROP_REF", "0.06"))     # stop width earning full risk

def _scaled_risk(entry_price, stop_loss):
    """Dollar risk for this ticket: full RISK_PER_TRADE at/above RISK_PROP_REF stop width,
    linearly less below. Never more than RISK_PER_TRADE. Invalid tickets are refused upstream
    (P0-A); this returns the ceiling for them so it can never widen anything."""
    if not RISK_PROP:
        return RISK_PER_TRADE
    try:
        w = (entry_price - stop_loss) / entry_price
        if w <= 0:
            return RISK_PER_TRADE
        return RISK_PER_TRADE * min(1.0, w / RISK_PROP_REF)
    except Exception:
        return RISK_PER_TRADE
SIM_ACCOUNT_BALANCE     = 3000.0 # DRY_RUN virtual account (the intended go-live funding of the margin acct …9AGA)
MAX_POS_VOL_PCT         = 0.05   # share cap = 5% of the avg recent 1-min volume (KUST lesson: the formula wanted
                                 # 750 shares of a 3k-shares/min tape = unfillable; size must fit the market)

INTRADAY_RESCAN_INTERVAL = int(os.environ.get("RESCAN_SECS", "60"))   # 8/10 latency doctrine:
# discovery floor 3min -> 60s. Affordable because the board funnel made a rescan ONE cached
# HTTP read (the old internal scan burned ~60s of sequential float checks per pass). The
# board's own server cache (30s TTL) means browser + bot never double-spend Webull budget.


def wait_for_flat_top_entry(candidates: list, stream: WebullStream,
                             rescan_callback=None, traded_tickers: set = None,
                             reentry: dict = None, session_cache: dict = None):
    """
    v10 entry detection: watches candidates for TWO entry types:
    1. Flat top breakout — 4-bar consolidation <8% range, price breaks window high
    2. EMA bounce — price pulled back to EMA9, bounces with 2:1 R:R to prior high
    Both require price > VWAP and EMA9 > EMA20 (bullish stack).
    No new entries after 11:00am ET.
    Returns list of (ticker, entry_price, vwap, entry_type, extra) where
    entry_type is "flat_top" or "ma_pullback" and extra has stop/target info.
    """
    if traded_tickers is None:
        traded_tickers = set()
    print(f"\n⏳ [v8] Watching {len(candidates)} candidate(s) for flat top breakout: {', '.join(candidates)}")

    # #81 RESCAN AMNESIA FIX (7/22): the cache is the machines' MEMORY — rocket arms, pullback
    # states, once-per-day flags, daily levels, session bars. Rebuilding it fresh on every
    # trade-done rescan rebirthed every detector with amnesia mid-session (ZCMD 7/22: +714% high,
    # rocket ARMED NINE TIMES, zero entries — arm state wiped each cycle). When the caller passes
    # session_cache, state PERSISTS across watch-loop invocations; new names get fresh entries.
    if session_cache is not None:
        cache = session_cache
        for t in candidates:
            cache.setdefault(t, {"bars": [], "vwap": 0.0, "fetched": 0.0})
    else:
        cache = {t: {"bars": [], "vwap": 0.0, "fetched": 0.0} for t in candidates}
    last_rescan = time.time()

    # ── DAILY-LEVEL HOMEWORK, done UP FRONT (follow-up #1). Kev sets his daily levels BEFORE the
    #    open, not reactively mid-breakout. Daily data is static intraday, so one spaced pass here
    #    (a) avoids a rate-limit BURST when several names trigger entries in the same minute, and
    #    (b) LOGS daily-gate coverage per name, so a 429 fail-open is VISIBLE — never silent (the
    #    exact trap that hid a degraded run). The lazy fetch at each entry site stays as a fallback
    #    for names the rescan adds mid-session. ──
    _daily_ok, _daily_miss = [], []
    for t in candidates:
        cache[t]["daily"] = get_daily_levels(t)
        if cache[t]["daily"]:
            try:   # 8/5: feed the crown's gain probe (crowns from the TAPE, not the first fire)
                _pdc_map[t] = float(cache[t]["daily"].get("prior_day_close") or 0)
            except Exception:
                pass
            _daily_ok.append(t)
            _log_decision(t, "daily_loaded")
        else:
            _daily_miss.append(t)
            _log_decision(t, "daily_missing")   # gate FAILS OPEN for this name — record it so we can SEE it
        time.sleep(0.5)   # de-burst the daily endpoint — gentle, pre-open, no rush
    print(f"📅 Daily levels pre-loaded: {len(_daily_ok)}/{len(candidates)} OK"
          + (f" | ⚠️  FAILED → daily gate fails OPEN for: {', '.join(_daily_miss)}"
             if _daily_miss else " (full daily-gate coverage)"))

    # #101 (Marcos 7/24: "I want the panel to constantly be updated — that is what I can watch
    # when away from my laptop"): keep the dashboard's CURRENTLY WATCHING panel identical to this
    # loop's LIVE roster. Re-post on every roster change and on a 120s heartbeat. Safe to repeat:
    # the dashboard POST replaces only the live snapshot and UNIONS into the day's history.
    _wl_posted: set = set()
    _wl_posted_ts: float = 0.0

    while True:
        now = datetime.now(EASTERN)

        _wl_now = set(candidates)
        if _wl_now != _wl_posted or time.time() - _wl_posted_ts >= 120:
            _post_watching_to_screener(sorted(_wl_now), quiet=True)
            _wl_posted, _wl_posted_ts = _wl_now, time.time()

        # No time-of-day entry wall: a bot doesn't fatigue, so it trades the SETUP, not the clock.
        # (The old 11:00am cutoff was a human-discipline guard + a DRY_RUN/live parity gap — removed.
        # The setup itself is gated by room/spread/momentum; new entries still stop at the 3:30pm
        # boundary in main() ahead of the 3:45pm forced flat. Kev's setups trigger all day, e.g. the
        # 2pm base-breakouts on SDOT/IVF that this used to block live.)

        _dg = detect_gate(now)
        if _dg == "idle":
            mins = 4 * 60 - (now.hour * 60 + now.minute)
            print(f"⏳ Premarket opens in ~{mins} min — machines idle...")
            time.sleep(30)
            continue
        # 'detect' → fall through: detection + shadow logging run from 4:00; the ENTRY_OPEN_ET
        # choke gate (premarket_shadow_entry) is what blocks trades before 9:30.

        # Session entry cutoff (ALL modes) — after 3:30pm ET, hand control back to main() so the
        # session can END and run end-of-day archival. Without this the loop spins forever on a
        # no-late-breakout day (DRY_RUN never had a non-breakout exit), and the bar-archival —
        # which runs after the loop — never fires (the 6/29 warehouse-empty bug). main() still does
        # the 3:45 forced-flat; this just stops NEW entries + guarantees the loop returns.
        if now.hour > VWAP_ENTRY_TIMEOUT or (now.hour == VWAP_ENTRY_TIMEOUT and now.minute >= VWAP_ENTRY_TIMEOUT_MIN):
            print(f"⏰ 3:30pm ET — watch-loop entry cutoff; returning to end the session.")
            return []

        # ── RE-ENTRY (#2): re-admit names that EXITED and re-qualified, EVERY cycle (~30s) so we catch
        #    the prompt reclaim (Kev re-enters the NEXT pullback after the stop). The full gate
        #    (room≥2:1 + daily-first + above-VWAP + fresh pullback) re-evaluates them; 'givenup' names
        #    (topping-tail / over-cap) never come back. ──
        # 7/28 halt-awareness mirror: expose this cycle's held set at module level so the
        # curl-feed halt logger (which cannot see the session-local `reentry`) can label rows.
        try:
            if reentry is not None:
                with reentry["lock"]:
                    _halt_held_mirror.clear()
                    _halt_held_mirror.update(reentry["held"])
        except Exception:
            pass
        if REENTRY_ENABLED and reentry is not None:
            with reentry["lock"]:
                _back = [t for t in reentry["eligible"]
                         if t not in reentry["held"] and t not in reentry["givenup"]]
                reentry["eligible"].clear()
            for t in _back:
                if t not in candidates:
                    candidates.append(t)
                    cache.setdefault(t, {"bars": [], "vwap": 0.0, "fetched": 0.0})
                    print(f"   🔁 Re-admitted {t} for re-entry (Kev: fresh reclaim/pullback) "
                          f"— attempt #{reentry['count'].get(t, 0) + 1}")

        # ── THE LENS (stage 1, 7/28): names near their marked levels go to the FRONT of the cycle.
        #    Attention only — same names, same checks, focus-first order. LENS_FOCUS_PCT=0 = off.
        candidates = _lens_pass(candidates, stream)

        # Refresh bars for each ticker every 30s
        for t in candidates:
            if time.time() - cache[t]["fetched"] >= VWAP_BAR_CACHE_SECS:
                # B16 (7/15): filter BOTH acquisitions at the source — every downstream entry
                # detector (EMA9/20/90, base, ignition, room, triggers, VWAP) then sees only
                # TODAY's fresh bars. Prior-day/stale fetches (first minutes of RTH, thin names)
                # leave the cache un-refreshed → detectors skip → NO entry decisions on stale data.
                fresh = _fresh_session(get_intraday_bars(t, count=max(EMA_BOUNCE_LOOKBACK + EMA20_PERIOD + 5, 50),
                                                        sessions=_live_sessions()))
                if fresh:
                    cache[t]["bars"] = fresh
                full_bars = _fresh_session(get_intraday_bars(t, count=390, sessions=_live_sessions()))
                if full_bars:
                    cache[t]["full_bars"] = full_bars   # RTH 1-min, TODAY-only — room + 3-min agg
                    if not ENTRY_VWAP_PREMARKET:
                        # LIVE DEFAULT (validated): RTH session VWAP from full_bars (already fresh-filtered).
                        calc_vwap = calculate_vwap(full_bars)   # SESSION VWAP — never across the day boundary
                        if calc_vwap > 0:
                            cache[t]["vwap"] = calc_vwap
                        else:
                            print(f"⚠️  {t} VWAP=0 — bars had no volume ({BARS_SOURCE} primary + webull fallback)")
                    elif time.time() - cache[t].get("vwap_fetched", 0) >= VWAP_SESSION_CACHE_SECS:
                        # Chart-matching = session-anchored INCLUDING pre-market. Dedicated pre+RTH fetch (slower TTL to
                        # limit API load); keep full_bars RTH-only so room/3-min setups don't move.
                        _vwb  = get_intraday_bars(t, count=VWAP_SESSION_COUNT, sessions=["PRE", "RTH"])
                        _sess = _fresh_session(_vwb) if _vwb else []
                        # B17 (7/16): when the PM fetch fails, NEVER silently substitute the RTH-only
                        # line (23% wrong on heavy-PM gappers — TGHL 7/15). Hold the last-good PM VWAP
                        # if it's fresh (≤10 min); otherwise mark VWAP unavailable so vwap>0 gates SKIP
                        # (no decision on a known-wrong line — same doctrine as B16's no-data-no-decision).
                        if not _sess:
                            _b17_age = time.time() - cache[t].get("vwap_fetched", 0)
                            if not (cache[t].get("vwap", 0) > 0 and _b17_age <= 600):
                                cache[t]["vwap"] = 0.0
                                print(f"⚠️  {t} PM-VWAP fetch failed, no recent value — VWAP unavailable (B17), gates skip")
                            _fullvw = 0.0
                        else:
                            _fullvw = calculate_vwap(_sess)
                        _rthvw  = (calculate_vwap([b for b in _sess if b.get("trading_session") == "RTH"]) or _fullvw) if _sess else 0.0
                        if _fullvw > 0:
                            cache[t]["vwap"]     = _fullvw   # pre+RTH session VWAP (chart-matching) — shown in status line
                            cache[t]["vwap_rth"] = _rthvw    # RTH-only (old) — dual-log to see the pre-market gap
                            cache[t]["vwap_fetched"] = time.time()
                            if _rthvw > 0 and abs(_fullvw - _rthvw) / _rthvw >= 0.03:
                                print(f"   🔍 {t} VWAP pre+RTH ${_fullvw:.3f} vs RTH-only ${_rthvw:.3f} "
                                      f"({(_fullvw - _rthvw) / _rthvw * 100:+.0f}% pre-market gap)")
                        else:
                            print(f"⚠️  {t} VWAP=0 — bars had no volume ({BARS_SOURCE} primary + webull fallback)")
                        # RECORDER TICK-VWAP overlay (7/16): when fresh + sane, the tick line IS the
                        # gate value; the bar line above remains fallback + divergence reference. Every
                        # replacement is dual-logged — that log is the tick-vs-bar comparison record.
                        if RECORDER_VWAP:
                            _tick = _recorder_tick_vwap(t)
                            _px_now = stream.get_price(t) or 0
                            if _tick and _tick_vwap_ok(_tick, _fullvw, _px_now):
                                if _fullvw > 0 and abs(_tick - _fullvw) / _fullvw >= 0.003:
                                    print(f"   🎯 {t} tick-VWAP ${_tick:.4f} vs bar ${_fullvw:.4f} "
                                          f"({(_tick - _fullvw) / _fullvw * 100:+.2f}%) — gating on tick")
                                cache[t]["vwap"]         = _tick
                                cache[t]["vwap_src"]     = "tick"
                                cache[t]["vwap_fetched"] = time.time()
                            elif _tick:
                                print(f"   ⚠️ {t} tick-VWAP ${_tick:.4f} REJECTED by sanity "
                                      f"(bar ${_fullvw:.4f}, px ${_px_now}) — bar line holds")
                else:
                    if _vwap_warn_ok(t):
                        print(f"⚠️  {t} VWAP unavailable — no bars ({BARS_SOURCE} primary + webull fallback both empty) [deduped 30m]")
                cache[t]["fetched"] = time.time()

        # Check each ticker for flat top breakout OR EMA bounce
        status_parts = []
        breakouts = []
        for t in candidates:
            if reentry is not None and (t in reentry["held"] or t in reentry["givenup"]):
                continue   # held = don't double-enter; givenup = topping-tail/over-cap, leave it alone (#2)
            bars = cache[t]["bars"]
            vwap = cache[t]["vwap"]
            price = stream.get_price(t)

            # ── #89 FIX (7/23): CURL DETECTORS ALWAYS STEP — ABOVE the no-data guard (7/23 am:
            # premarket has NO 1-min bars, so the guard starved the curls of their 10s data;
            # the machines need only the stream's shadow bars + the ALP/recorder VWAP line). The pullback arm-wait `continue`s below
            # starved zone-flip/reclaim of bars on every armed pass — and movers are perpetually armed
            # (813 arms 7/22), so 31 replay fires produced ZERO live rows ever. Integrator law:
            # DETECTION is unconditional (the rocket-detector pattern); entry SELECTION below stays
            # priority-ordered. Machines step HERE; fires are stashed; the branches below consume
            # them; a fire that loses priority is shadow-logged via _shadow_log_curl_leftovers. ──
            _zf_fire = None
            _vr_fire = None
            _he_fire = None
            _dr_fire = None
            _vr_sv = 0.0
            if ZONEFLIP_KEV:
                _zf_nb = []
                _cur_z = (datetime.now(EASTERN).strftime("%Y-%m-%d"), t)
                _last_z = _zf_cursor.get(_cur_z, 0)
                _cut_z = int(time.time()) // 10 * 10           # exclude the still-forming bucket
                _d10z, _zf_src = _curl_feed(t)                 # #97 choke-point (CURL_SOURCE env)
                for _k in sorted(_d10z):
                    if _last_z < _k < _cut_z:
                        _b = _d10z[_k]
                        _zf_nb.append((_k, _b["o"], _b["h"], _b["l"], _b["c"],
                                       max((_b.get("v1") or 0) - (_b.get("v0") or 0), 0)))
                        _zf_cursor[_cur_z] = _k
                if _zf_nb:
                    _zf_fire = kev_zoneflip_step(t, _zf_nb)
                    if _zf_fire:
                        # evidence logged AT DETECTION — no downstream `continue` can ever drop it
                        _shadow_log_curl_leftovers(t, price, _zf_fire, None, 0.0, "detected")
            if RECLAIM_KEV:
                # PATH-1 (#67) preserved: line = tick-VWAP when sane, else the bar line.
                _tickv = _recorder_tick_vwap(t)
                _vr_sv = _tickv if (_tickv and _tick_vwap_ok(_tickv, vwap, price)) else vwap
                if _vr_sv and _vr_sv > 0:
                    _nb = []
                    _cur_key = (datetime.now(EASTERN).strftime("%Y-%m-%d"), t)
                    _last_k = _reclaim_cursor.get(_cur_key, 0)
                    _now_cut = int(time.time()) // 10 * 10     # exclude the still-forming bucket
                    _d10, _vr_src = _curl_feed(t, n=(REHYDRATE_BARS if not _last_k else 90))   # 8/6 rehydrate: deep first pass
                    _fed_k = 0
                    for _k in sorted(_d10):
                        if _last_k < _k < _now_cut:
                            _b = _d10[_k]
                            _nb.append((_k, _b["o"], _b["h"], _b["l"], _b["c"],
                                        max((_b.get("v1") or 0) - (_b.get("v0") or 0), 0)))
                            _fed_k = _k
                    if _nb:
                        _vr_fire = kev_reclaim_step(t, _nb, _vr_sv)
                        _reclaim_cursor[_cur_key] = _fed_k     # cursor advances ONLY on bars actually FED
                                                               # (old code advanced it even when _sv<=0 dropped them)
                        if _vr_fire:
                            _shadow_log_curl_leftovers(t, price, None, _vr_fire, _vr_sv, "detected")
                        # HIDDEN ENTRY rides the same fed 10s bars + session line (evidence AT detection)
                        if HIDDEN_ENTRY:
                            _he_fire = hidden_entry_step(t, _nb, _vr_sv)
                            if _he_fire:
                                try:
                                    _hpx = price if price and price > 0 else _he_fire.get("px") or 0
                                    _hg, _hbp = _level_gap(t, _hpx)   # 7/27 ballpark stamp
                                    _log_decision(t, "hidden_shadow_fire", price=_hpx,
                                                  stop=_he_fire["stop"], anchor=_he_fire["anchor"],
                                                  ext_vwap=_he_fire["ext_vwap"], seq=_he_fire["seq"],
                                                  time_hm=datetime.now(EASTERN).strftime("%H:%M"),
                                                  level_gap_pct=_hg, ballpark=_hbp)
                                except Exception:
                                    pass

            # ── IGNITION-10S feed (7/26): VWAP-INDEPENDENT (the quiet base sits below VWAP by thesis),
            #    so it must NOT live inside the reclaim block's _vr_sv>0 gate. Own cursor; fire is
            #    consumed by the legacy ignition branch below (keeps ALL its gates — this is eyes-only). ──
            _ig_fire = None
            if IGNITION_10S and IGNITION_ENABLED and (not cache[t].get("ignition_fired")
                    or (_is_leader(t) and cache[t].get("ignition_n", 1) < LEADER_IGNITION_CAP)):
                _ig_nb = []
                _cur_i = (datetime.now(EASTERN).strftime("%Y-%m-%d"), t)
                _last_i = _ig_cursor.get(_cur_i, 0)
                _cut_i = int(time.time()) // 10 * 10       # exclude the still-forming bucket
                _d10i, _ig_src = _curl_feed(t, n=(REHYDRATE_BARS if not _last_i else 90))   # 8/6 rehydrate: deep first pass
                for _k in sorted(_d10i):
                    if _last_i < _k < _cut_i:
                        _b = _d10i[_k]
                        _ig_nb.append((_k, _b["o"], _b["h"], _b["l"], _b["c"],
                                       max((_b.get("v1") or 0) - (_b.get("v0") or 0), 0)))
                        _ig_cursor[_cur_i] = _k
                if _ig_nb:
                    _ig_fire = ignition_10s_step(t, _ig_nb)

            # ── DIP-RIP feed (7/30): only runs while a halt-armed watch exists for t (rare), so the
            #    extra _curl_feed call costs nothing in the common case. Own cursor via armed_k/r_k
            #    inside the state — bars are re-scanned from the halt bar, fed monotonically. ──
            if DIP_RIP and _dr_st.get(t) and not _dr_st[t].get("done"):
                _d10r, _ = _curl_feed(t)
                _cut_r = int(time.time()) // 10 * 10
                _nb_r = [( _k, _d10r[_k]["o"], _d10r[_k]["h"], _d10r[_k]["l"], _d10r[_k]["c"],
                           max((_d10r[_k].get("v1") or 0) - (_d10r[_k].get("v0") or 0), 0))
                         for _k in sorted(_d10r) if _k < _cut_r]
                if _nb_r:
                    _dr_fire = dip_rip_step(t, _nb_r)

            # ── 7/24 CONVERT-AT-DETECTION (Marcos: "we see it triggered but now do nothing!!").
            # The consume branches used to sit BELOW the 3-min-EMA warmup guard + 8 other `continue`s,
            # so a curl fire was detected, shadow-logged, then DROPPED before the trade branch ever ran
            # (7/24: 26 RTH fires, zero conversions, zero 🔵/🟣 prints all day). The 10s curl machines
            # need NONE of that machinery — convert eligible fires to entries RIGHT HERE, before any
            # legacy guard can eat them. EMAs are best-effort informational (ignition's own pattern). ──
            if (_zf_fire or _vr_fire or _he_fire or _dr_fire) and price and price > 0:
                _hm_curl = datetime.now(EASTERN).strftime("%H:%M")
                _fire_px = None
                for _f in (_zf_fire, _vr_fire, _he_fire, _dr_fire):
                    if _f and _f.get("px"):
                        _fire_px = _f["px"]; break
                if _fire_px and _fire_px > 0 and abs(price - _fire_px) / _fire_px > 0.02:
                    _fk = next((_f.get("k") for _f in (_zf_fire, _vr_fire, _he_fire)
                                if _f and _f.get("px") == _fire_px), None)
                    _ok, _why = _swap_price_ok(t, price, _fire_px, _fk, hm=_hm_curl)
                    if _ok:
                        _log_decision(t, "stale_price_fix", stream_px=round(price, 4), bar_px=_fire_px,
                                      time_hm=_hm_curl, why=_why,
                                      tick_age_s=(round(_stream_tick_age(t), 1) if _stream_tick_age(t) is not None else None))
                        print(f"   🩹 {t}: quote dead ({_why}) — using fire-bar ${_fire_px:.2f} over ${price:.2f}")
                        price = _fire_px
                    else:
                        _log_decision(t, "stale_swap_refused", stream_px=round(price, 4), bar_px=_fire_px,
                                      time_hm=_hm_curl, why=_why)
                _cc = aggregate_bars(cache[t].get("full_bars") or bars or [], SETUP_TF_MIN)[:-1]
                if len(_cc) >= EMA20_PERIOD + 2:
                    _ce9, _ce20, _ce90 = calculate_ema9(_cc), calculate_ema20(_cc), calculate_ema90(_cc)
                else:
                    _ce9 = _ce20 = _ce90 = 0.0
                # DIP-RIP first (7/30): rarest and most specific — a halt-resumption confirm over
                # Kev's own level. RTH only (halts only flag in RTH), one watch per name per day.
                if _dr_fire and DIP_RIP and _hm_curl >= "09:30" and _curl_rth_slot(t, "dr", _hm_curl):
                    dr = _dr_fire
                    _dr_fire = None                            # consumed
                    if "daily" not in cache[t]:
                        cache[t]["daily"] = get_daily_levels(t)
                    _daily = cache[t]["daily"]
                    room = compute_room(price, dr["stop"], cache[t].get("full_bars") or bars,
                                        daily=_daily, prior_day_high=(_daily or {}).get("prior_day_high"))
                    print(f"\n🪂 {t} DIP AND RIP! ${price:.2f} — halt-resumption flush held Kev's "
                          f"${dr['level']:.2f} (tag low ${dr['tag_low']:.2f}) — stop ${dr['stop']:.2f}")
                    breakouts.append((t, price, dr["level"], "dip_rip", {
                        "zone_stop": dr["stop"], "room": room, "ema90": round(_ce90, 4),
                        "front_side": _ce9 > _ce20 > 0, "ema9": round(_ce9, 4), "ema20": round(_ce20, 4),
                        "dr_level": dr["level"], "dr_tag_low": dr["tag_low"],
                    }))
                    _log_decision(t, "triggered_dip_rip", price=price, level=dr["level"],
                                  tag_low=dr["tag_low"], stop=dr["stop"],
                                  fire_px=dr.get("px"), fire_age_s=(round(time.time() - dr["k"], 1) if dr.get("k") else None))
                    continue                                   # captured — skip other detectors for t
                # ZONE-FLIP first (its original priority) — live all RTH (Marcos 7/20).
                if _zf_fire and not ZONEFLIP_CONVERT:
                    # G1 SHADOW: the fire is consumed and fully logged (stop included, so the
                    # forward replay stays runnable) but never trades and never spends a slot.
                    _zfs = _zf_fire
                    _zf_fire = None
                    _log_decision(t, "zoneflip_shadow_convert", price=price, stop=_zfs["stop"],
                                  fire_px=_zfs.get("px"), seq=_zfs["seq"], zone=_zfs.get("zone"),
                                  zone_src=_zfs.get("zone_src"), flush_low=_zfs.get("flush_low"))
                elif _zf_fire and _curl_rth_slot(t, "zf", _hm_curl):
                    zf = _zf_fire
                    _zf_fire = None                            # consumed
                    if "daily" not in cache[t]:
                        cache[t]["daily"] = get_daily_levels(t)
                    _daily = cache[t]["daily"]
                    room = compute_room(price, zf["stop"], cache[t].get("full_bars") or bars,
                                        daily=_daily, prior_day_high=(_daily or {}).get("prior_day_high"))
                    print(f"\n🟣 {t} ZONE-FLIP (Kev pm-shelf)! ${price:.2f} curl off "
                          f"{zf['zone_src']} ${zf['zone']:.2f} — stop ${zf['stop']:.2f}")
                    breakouts.append((t, price, zf["zone"], "zone_flip", {
                        "zone_stop": zf["stop"], "room": room, "ema90": round(_ce90, 4),
                        "front_side": _ce9 > _ce20 > 0, "ema9": round(_ce9, 4), "ema20": round(_ce20, 4),
                        "reclaim_subtype": "zone_flip",
                        "zf_zone": zf["zone"], "zf_zone_src": zf["zone_src"],
                        "zf_flush_low": zf["flush_low"],
                    }))
                    _log_decision(t, "triggered_zone_flip", price=price, zone=zf["zone"],
                                  fire_px=zf.get("px"), fire_age_s=(round(time.time() - zf["k"], 1) if zf.get("k") else None),
                                  drift_pct=(round((price - zf["px"]) / zf["px"] * 100, 2) if zf.get("px") else None),
                                  zone_src=zf["zone_src"], stop=zf["stop"])
                    continue                                   # captured — skip other detectors for t
                # KEV RECLAIM — live in its verified 09:30-11:00 window.
                # 7/30 fire-bar re-check: computed BEFORE the slot so a refused fire never spends
                # it. None-volmult fires (pre-deploy state, restart edge) pass through = fail-safe
                # to the old behavior.
                _vr_fv = (_vr_fire or {}).get("volmult")
                _vr_fv_bad = (RECLAIM_FIREVOL > 0 and _vr_fv is not None and _vr_fv < RECLAIM_FIREVOL)
                _vr_win = (RECLAIM_LIVE_START <= _hm_curl < RECLAIM_LIVE_END
                           or (ENTRY_OPEN_ET <= _hm_curl < "09:30" and "vwap_reclaim" in PRE_LANES))
                if _vr_fire and RECLAIM_LIVE and _vr_win and _vr_fv_bad:
                    _vrr = _vr_fire
                    _vr_fire = None                            # consumed — no retry-spam, no slot spent
                    _log_decision(t, "reclaim_firevol_reject", price=price, volmult=_vrr["volmult"],
                                  need=RECLAIM_FIREVOL, stop=_vrr["stop"], fire_px=_vrr.get("px"),
                                  seq=_vrr["seq"])
                elif (_vr_fire and RECLAIM_LIVE
                        and (RECLAIM_LIVE_START <= _hm_curl < RECLAIM_LIVE_END
                             # PREMARKET FIX 7/26 ("ship all 4"): PRE_LANES promised premarket reclaim
                             # but this window (09:30+) killed every premarket fire BEFORE the premkt
                             # gate could see it — the regime could only ever trade hidden_entry.
                             # Premarket fires now pass through; premarket gate v2 (PRE_LANES/cap/
                             # dvol/9:25 flatten) governs them downstream.
                             or (ENTRY_OPEN_ET <= _hm_curl < "09:30" and "vwap_reclaim" in PRE_LANES))
                        and _curl_rth_slot(t, "vr", _hm_curl)):
                    vr = _vr_fire
                    _vr_fire = None                            # consumed
                    _sv = _vr_sv
                    if "daily" not in cache[t]:
                        cache[t]["daily"] = get_daily_levels(t)
                    _daily = cache[t]["daily"]
                    room = compute_room(price, vr["stop"], cache[t].get("full_bars") or bars,
                                        daily=_daily, prior_day_high=(_daily or {}).get("prior_day_high"))
                    print(f"\n🔵 {t} KEV RECLAIM (3-gate)! ${price:.2f} wick-confirmed off session "
                          f"VWAP ${_sv:.2f} — stop ${vr['stop']:.2f}")
                    breakouts.append((t, price, _sv, "vwap_reclaim", {
                        "zone_stop": vr["stop"], "room": room, "ema90": round(_ce90, 4),
                        "front_side": _ce9 > _ce20 > 0, "ema9": round(_ce9, 4), "ema20": round(_ce20, 4),
                        "reclaim_subtype": "kev3gate",
                        "entry_vs_session_vwap_pct": round((price - _sv) / _sv * 100, 2),
                    }))
                    _log_decision(t, "triggered_vwap_reclaim_kev3gate", price=price, vwap=_sv,
                                  fire_px=vr.get("px"), fire_age_s=(round(time.time() - vr["k"], 1) if vr.get("k") else None),
                                  drift_pct=(round((price - vr["px"]) / vr["px"] * 100, 2) if vr.get("px") else None))
                    continue                                   # captured — skip other detectors for t
                # ── 8/8 (#38) CROWN-SEAM lane — 5s micro-pullback reclaims, CROWNS ONLY.
                # Marcos (three calls, same minute): "we are playing with fake money. I want a
                # real live test" / "shadow the alternative if you wish" / "this is just for
                # crowns for now." Paper book = live conversion IS the kill-test. Converts by
                # default (SEAM_CONVERT=0 restores shadow). Every fire logs seam_shadow_fire
                # regardless, so the evidence ledger rides along either way. ──
                if HALT_LANE and _is_leader(t) and _hm_curl >= "09:30" \
                        and time.time() - _seam_shadow_t.get(t, 0) >= 45:
                    try:
                        # 8/13 #49 rider — SEAM LIVENESS HEARTBEAT: 3 days of ZERO seam rows of
                        # any status made dead-vs-quiet indistinguishable. One observe row/hour
                        # proves the detector is REACHED and evaluating (feed length included so
                        # a starved 5s feed is visible too). Data-only.
                        global _seam_beat_t
                        if time.time() - globals().get("_seam_beat_t", 0) > 3600:
                            globals()["_seam_beat_t"] = time.time()
                            try:
                                _log_decision("ZZSEAMBEAT", "seam_beat", ticker_checked=t,
                                              feed_len=len(_alp5_feed(t, n=720)))
                            except Exception:
                                pass
                        _ss = _seam5_check(t)
                        if _ss:
                            _seam_shadow_t[t] = time.time()
                            _log_decision(t, "seam_shadow_fire", convert=SEAM_CONVERT, **_ss)
                            print(f"🧵 {t} SEAM: entry ${_ss['price']} stop ${_ss['stop']} "
                                  f"(pull {_ss['pull_pct']}%){' -> CONVERT' if SEAM_CONVERT else ' (shadow)'}")
                            if SEAM_CONVERT and float(_ss['stop']) < float(_ss['price']):
                                breakouts.append((t, float(_ss['price']), 0, "crown_seam", {
                                    "zone_stop": float(_ss['stop']),
                                    "seam_pull_pct": _ss['pull_pct']}))
                                continue
                    except Exception:
                        pass
                # ── 8/8 (#37) HALT-LADDER detector (crowns only; shadow unless HALT_LANE_CONVERT) ──
                if HALT_LANE and _is_leader(t) and _hm_curl >= "09:30":
                    try:
                        # 8/8 night: _curl_feed returns (bars, src) — the unpack was missing, so
                        # sorted() threw into the except and the detector NEVER armed (caught in
                        # the pre-Monday exec check, not by the pattern pins — three-rings lesson).
                        # 8/8 (Marcos: "go with 1"): arm on the 5s feed when available — Friday
                        # full-day head-to-head (arm_resolution_reconciled_20260808): 10s −$13.91
                        # vs 5s +$216.35 on identical exits. 10s fallback fail-open; HALT_ARM_5S=0 kill.
                        # n = 30 min of bars: arm math only reads the last 5 min, but the
                        # mins_since_halt stamp (HALT-H1) needs to see resumptions up to 30 min back.
                        _hl_d10, _hl_src = _curl_feed(t, n=180)
                        _hl_min = 12
                        if HALT_ARM_5S:
                            _hl_d5 = _alp5_feed(t, n=360)
                            if len(_hl_d5) >= 24:
                                _hl_d10, _hl_src, _hl_min = _hl_d5, "alp5s", 24
                        _hl_ks = sorted(_hl_d10)
                        if len(_hl_ks) >= _hl_min:
                            _hl_px = float(_hl_d10[_hl_ks[-1]].get("c") or 0)
                            _hl_w5 = [_hl_d10[k] for k in _hl_ks if k >= _hl_ks[-1] - 300]
                            _hl_ref = sum(float(b.get("c") or 0) for b in _hl_w5) / max(len(_hl_w5), 1)
                            _hl_band = 0.10 if _hl_px >= 3 else (0.20 if _hl_px >= 0.75 else 0.75)
                            _hl_prox = (_hl_px / _hl_ref - 1) / _hl_band if _hl_ref else 0
                            _hl_w1 = [_hl_d10[k] for k in _hl_ks if k >= _hl_ks[-1] - 60]
                            _hl_v0 = float(_hl_w1[0].get("c") or 0) if _hl_w1 else 0
                            _hl_vel = (_hl_px / _hl_v0 - 1) * 100 if _hl_v0 else 0
                            if 0.4 <= _hl_prox < HALT_ARM_PROX and _hl_vel >= HALT_ARM_VEL \
                                    and time.time() - _halt_early_t.get(t, 0) >= 120:
                                _halt_early_t[t] = time.time()
                                _log_decision(t, "halt_early_arm", price=round(_hl_px, 4),
                                              prox=round(_hl_prox, 2), vel1m=round(_hl_vel, 1))
                                # 8/8 (Marcos: get in BEFORE... from the beginning) — shadow meter
                                # of the EARLIER boarding point; weekend grades the prox bands.
                            if _hl_prox >= HALT_ARM_PROX and _hl_vel >= HALT_ARM_VEL                                     and time.time() - _halt_arm_t.get(t, 0) >= 60:
                                _halt_arm_t[t] = time.time()
                                _hl_ok, _hl_up, _hl_pull = _halt5_confirm(t)
                                _hl_stop = min((float(_hl_d10[k].get("l") or 0) for k in _hl_ks
                                                if k >= _hl_ks[-1] - 120 and float(_hl_d10[k].get("l") or 0) > 0),
                                               default=0)
                                # 8/8 anatomy (arm_anatomy_20260808): Friday's 4 worst losers armed
                                # 2-10 min after a resumption; winners 10-35+ min. HALT-H1 cooldown
                                # hypothesis — STAMP ONLY, grades on unseen rows before any gating.
                                _hl_gaps = [_hl_ks[_gi] for _gi in range(1, len(_hl_ks))
                                            if _hl_ks[_gi] - _hl_ks[_gi-1] >= 270]
                                _hl_shalt = round((_hl_ks[-1] - _hl_gaps[-1]) / 60, 1) if _hl_gaps else None
                                _log_decision(t, "halt_arm", mins_since_halt=_hl_shalt,
                                              price=round(_hl_px, 4),
                                              prox=round(_hl_prox, 2), vel1m=round(_hl_vel, 1),
                                              confirm5s=_hl_ok, upratio=_hl_up, maxpull=_hl_pull,
                                              stop=round(_hl_stop, 4) if _hl_stop else None,
                                              convert=bool(HALT_LANE_CONVERT and (_hl_ok or not HALT_CONFIRM_GATE)))
                                # 8/8 (Marcos: "Fix the confirm"): confirm REFUTED as a gate on the
                                # full 5s day (its only pass lost; it refused YJ +$399 — "breathless
                                # tape" = exhaustion as often as halt-bound). Demoted to a DATA STAMP:
                                # logs ok/up/pull on every arm row, converts nothing, earns gate
                                # status only on unseen-day evidence. HALT_CONFIRM_GATE=1 re-arms.
                                _hl_go = _hl_ok or not HALT_CONFIRM_GATE
                                print(f"🪜 {t} HALT-LADDER ARM ${_hl_px:.2f} prox {_hl_prox:.2f} "
                                      f"vel {_hl_vel:.1f}%/m 5s-confirm={_hl_ok}"
                                      f"{' -> CONVERT' if HALT_LANE_CONVERT and _hl_go else ' (shadow)'}")
                                if HALT_LANE_CONVERT and _hl_go and _hl_stop and _hl_stop < _hl_px:
                                    breakouts.append((t, _hl_px, 0, "halt_ladder", {
                                        "zone_stop": _hl_stop, "half_size": True,
                                        "luld_prox": round(_hl_prox, 2)}))
                                    continue
                    except Exception:
                        pass
                # HIDDEN ENTRY (Kev 10s rocket wick) — live all RTH, own caps, replaces rocket_catcher.
                if _he_fire and HIDDEN_ENTRY and _hm_curl >= ENTRY_OPEN_ET:
                    _heday = datetime.now(EASTERN).strftime("%Y-%m-%d")
                    _sess_he = "PRE" if _hm_curl < "09:30" else "RTH"
                    if _he_day.get("d") != _heday:   # 8/10: defensive — never crash the loop on a counter
                        _he_day["d"] = _heday; _he_day["PRE"] = 0; _he_day["RTH"] = 0
                    _k_he = (_heday, t)
                    _k_he = _k_he + (_sess_he,)
                    if ((_he_day[_sess_he] >= HIDDEN_DAILY_CAP or _he_name.get(_k_he, 0) >= HIDDEN_NAME_CAP)
                            and not _is_leader(t)):   # 8/5 leader ammo: winners bypass the ration
                        _log_decision(t, "hidden_capped", price=price, day_n=_he_day[_sess_he],
                                      name_n=_he_name.get(_k_he, 0), sess=_sess_he)
                    elif (HIDDEN_EXT_GATE and HIDDEN_EXT_LO <= float(_he_fire.get("ext_vwap") or 0) < HIDDEN_EXT_HI
                            # 8/6 CROWN-SCOPED (Marcos: "build the crown-scoped ext gate now"): the
                            # A1 no-man's-land held forward for ordinary names but on CROWNED names
                            # the 3-10% band IS the coil — refused crown fires replayed +$641.87/26
                            # (AZI's seven base fires alone +$459 before its 70% leg) while non-crown
                            # refusals stayed correctly negative. Crowns bypass the band; everyone
                            # else keeps July's protection. Kill: HIDDEN_EXT_CROWN_BYPASS=0 restores
                            # the flat band. Bypassed crown fires stamp ext_vwap on the trade record
                            # (already do) so Friday grades the reopened band from live fills.
                            and not (HIDDEN_EXT_CROWN_BYPASS and _is_leader(t))):
                        # A1: the 3–10% no-man's-land — too late for the dip, too early for the
                        # vertical. Consume the fire (no retry-spam) and log EVERYTHING needed to
                        # grade the refusal forward.
                        _her = _he_fire
                        _he_fire = None
                        _log_decision(t, "hidden_ext_reject", price=price, ext_vwap=_her["ext_vwap"],
                                      stop=_her["stop"], anchor=_her["anchor"], seq=_her["seq"],
                                      fire_px=_her.get("px"), band=f"{HIDDEN_EXT_LO}-{HIDDEN_EXT_HI}")
                    else:
                        he = _he_fire
                        _he_fire = None                        # consumed
                        print(f"\n🫥 {t} HIDDEN ENTRY! ${price:.2f} — Kev 10s wick off "
                              f"${he['anchor']:.2f} (VWAP+90MA), stop ${he['stop']:.2f} (wick low) "
                              f"[#{_he_day[_sess_he] + 1}/{HIDDEN_DAILY_CAP} {_sess_he}]")
                        if _he_day[_sess_he] >= 3 and not _is_leader(t):
                            # 8/12 CAP RAISE stamp (Marcos: hidden 5; kill-test cap_cost_20260812
                            # +$257 era offer, YXT-tail): non-crown slots 4-5 = the marginal
                            # cohort, rowed for Friday's isolated grade.
                            _log_decision(t, "cap_raise_slot", price=price, cap="hidden5",
                                          slot=_he_day[_sess_he] + 1, sess=_sess_he)
                        breakouts.append((t, price, he["anchor"], "hidden_entry", {
                            "zone_stop": he["stop"], "wick": he["wick"], "anchor": he["anchor"],
                            "ext_vwap": he["ext_vwap"], "he_seq": he["seq"],
                            "ema90": round(_ce90, 4), "front_side": _ce9 > _ce20 > 0,
                            "ema9": round(_ce9, 4), "ema20": round(_ce20, 4),
                            "two_r_level": round(price + 2.0 * (price - he["stop"]), 4),
                        }))
                        _log_decision(t, "triggered_hidden_entry", price=price, stop=he["stop"],
                                      fire_px=he.get("px"), fire_age_s=(round(time.time() - he["k"], 1) if he.get("k") else None),
                                      drift_pct=(round((price - he["px"]) / he["px"] * 100, 2) if he.get("px") else None),
                                      anchor=he["anchor"], ext_vwap=he["ext_vwap"], seq=he["seq"])
                        _he_day[_sess_he] += 1
                        _he_name[_k_he] = _he_name.get(_k_he, 0) + 1
                        continue                               # captured — skip other detectors for t

            if not bars or price <= 0:
                status_parts.append(f"{t}:no data")
                continue

            # ── Entry type: IGNITION (7/4) — runs FIRST, BEFORE the 3-min-EMA warmup guard below, because it
            #    reads 1-MIN SESSION bars + the volume-acceleration surge and does NOT need the 3-min EMAs
            #    (not warm in the ignition window). The ONE entry NOT gated on above-VWAP (quiet base sits below
            #    VWAP). Surge breaking the quiet base = the trigger; tight stop at base low. Fires ONCE per ticker. ──
            if IGNITION_ENABLED and (not cache[t].get("ignition_fired")
                    or (_is_leader(t) and cache[t].get("ignition_n", 1) < LEADER_IGNITION_CAP)):
                if IGNITION_10S:
                    # 10s machine's fire (7/26) — same dict shape; re-apply the 1-min detector's two
                    # consume-time clauses here: the live-price no-chase cap + the stale-price fix (a4fe777).
                    ign = _ig_fire
                    if ign and ign.get("openp", 0) > 0 and price > 0 \
                            and (price - ign["openp"]) / ign["openp"] > IGNITION_MAX_EXT:
                        _log_decision(t, "ignition_ext_live_skip", price=price,
                                      ext_pct=ign["ext_pct"], openp=ign["openp"])
                        ign = None
                    elif ign and ign.get("px") and price > 0 and abs(price - ign["px"]) / ign["px"] > 0.02:
                        _ok, _why = _swap_price_ok(t, price, ign["px"], ign.get("bar_epoch"))
                        if _ok:
                            print(f"   🩹 {t}: quote dead ({_why}) — using ignition 10s bar "
                                  f"${ign['px']:.2f} over ${price:.2f}")
                            _log_decision(t, "stale_price_fix", stream_px=round(price, 4), bar_px=ign["px"], why=_why)
                            price = ign["px"]
                        else:
                            _log_decision(t, "stale_swap_refused", stream_px=round(price, 4),
                                          bar_px=ign["px"], why=_why)
                else:
                    _sess1 = _latest_session(cache[t].get("full_bars") or bars)
                    ign = detect_ignition(_sess1, price)
                # 7/30 SHIP+SHADOW: detector still fires at 2.0× (IGNITION_VOL_MULT unchanged) so
                # the old cohort keeps accruing as shadow rows; CONVERSION demands the plateau
                # value. Below-convert fires do NOT burn the once-per-ticker slot — the E2 cap
                # protects against repeat CONVERSIONS, and the first ≥4.5× fire must still be able
                # to trade after an earlier 2.3× one was refused.
                if ign and float(ign.get("volx") or 0) < IGNITION_CONVERT_MULT:
                    _log_decision(t, "ignition_below_convert", price=price, volx=ign["volx"],
                                  need=IGNITION_CONVERT_MULT, base_hi=ign["base_hi"],
                                  ext_pct=ign["ext_pct"], stop=ign["stop"])
                    ign = None
                if ign:
                    _istop = ign["stop"]
                    if "daily" not in cache[t]:
                        cache[t]["daily"] = get_daily_levels(t)
                    _daily = cache[t]["daily"]
                    room = compute_room(price, _istop, cache[t].get("full_bars") or bars,
                                        daily=_daily, prior_day_high=(_daily or {}).get("prior_day_high"))
                    rr = room["rr_to_supply"]
                    if IGNITION_DAILY_VETO and bool(_daily) and not daily_first_ok(price, _daily):
                        _log_decision(t, "ignition_daily_bad", price=price, room_rr=rr)
                        cache[t]["ignition_fired"] = True; cache[t]["ignition_n"] = cache[t].get("ignition_n", 0) + 1     # bad daily = no trade (Kev)
                    else:
                        if rr is not None and rr < MIN_ROOM_RR:   # room DE-INVERTED — observe (base+volume is the filter)
                            _log_decision(t, "ignition_low_room_soft", price=price, room_rr=rr)
                        _ig_comp = aggregate_bars(cache[t].get("full_bars") or bars, SETUP_TF_MIN)[:-1]
                        if len(_ig_comp) >= EMA20_PERIOD + 2:
                            _e9, _e20, _e90 = calculate_ema9(_ig_comp), calculate_ema20(_ig_comp), calculate_ema90(_ig_comp)
                        else:
                            _e9 = _e20 = _e90 = 0.0
                        _front = _e9 > _e20 > 0
                        print(f"\n🚀 {t} IGNITION! ${price:.2f} vol-surge {ign['volx']}× broke base "
                              f"${ign['base_hi']:.2f} (+{ign['ext_pct']}% from open, NOT extended) — "
                              f"stop ${_istop:.2f} | room {rr}:1 to ${room['next_supply']} ({room['supply_src']})")
                        breakouts.append((t, price, vwap, "ignition",
                                          {"zone_stop": _istop, "room": room, "base_hi": ign["base_hi"],
                                           "base_lo": ign["base_lo"], "volx": ign["volx"], "ext_pct": ign["ext_pct"],
                                           "ema90": round(_e90, 4), "front_side": _front,
                                           "ema9": round(_e9, 4), "ema20": round(_e20, 4)}))
                        # 7/30 shadow stamp: what the OLD config's gate would have said. The
                        # "_shadow_legacy" probe walks the exact legacy path (not stale-exempt,
                        # not bypassed) — the gated alternative's counterfactual, graded Friday.
                        try:
                            _sgv, _sgr, _sgl, _ = _chart_break_gate(t, price, "_shadow_legacy")
                        except Exception:
                            _sgv, _sgr, _sgl = None, None, None
                        _log_decision(t, "triggered_ignition", price=price, room_rr=rr,
                                      volx=ign["volx"], base_hi=ign["base_hi"], ext_pct=ign["ext_pct"], front_side=_front,
                                      src=("10s" if IGNITION_10S else "1min"),
                                      shadow_gate=_sgv, shadow_gate_reason=_sgr, shadow_gate_level=_sgl)
                        cache[t]["ignition_fired"] = True; cache[t]["ignition_n"] = cache[t].get("ignition_n", 0) + 1
                        continue                              # ignition captured (in `breakouts`) — skip other detectors for t

            # ── ROCKET CATCHER (7/21 KEV-SPEC, video XFSPUI5YJsE: "wait for the pullback to draw down
            #    off the 20 EMA... these were the BEST entries") — three phases, NOT a chase:
            #    1) ARM: velocity ≥25%/5min fires (detect_rocket) → rocket alarm, no entry (chase REFUTED
            #       by order-dependent replay: median-negative).
            #    2) WAIT: track the pullback low; require a touch of the 1m 20-EMA (Kev's anchor).
            #    3) CURL: just-closed 1m bar closes above the prior bar's high → ENTER; stop = pullback low.
            #    Exit = scale-out ladder in monitor_trade (entry_type rocket_catcher). Kill-tested n=5:
            #    mean +50%, median +21%, win 60% (kev_anchor_dipbuy.py). Extension-guard EXEMPT; capped/day.
            if ROCKET_CATCHER and not cache[t].get("rocket_fired"):
                _rs1 = _latest_session(cache[t].get("full_bars") or bars)
                if not cache[t].get("rocket_armed"):
                    _rk = detect_rocket(_rs1, price)
                    if _rk:
                        cache[t]["rocket_armed"] = True
                        cache[t]["rocket_vel"] = _rk["vel"]
                        cache[t]["rocket_plow"] = price          # pullback low starts at the alarm print
                        cache[t]["rocket_touched"] = False
                        print(f"\n🚀 {t} ROCKET ARMED +{_rk['vel']}%/{ROCKET_VEL_BARS}min — waiting for "
                              f"20-EMA pullback + curl (Kev spec), NOT chasing")
                        _log_decision(t, "rocket_armed", price=price, vel=_rk["vel"])
                elif len(_rs1) >= 2:
                    _lb, _pb = _rs1[-1], _rs1[-2]                 # just-closed bar + the one before it
                    _lo, _cl = _bar_low(_lb), _bar_close(_lb)
                    if _lo > 0:
                        cache[t]["rocket_plow"] = min(cache[t].get("rocket_plow") or _lo, _lo)
                    _closes = [_bar_close(b) for b in _rs1 if _bar_close(b) > 0]
                    _e20r = 0.0
                    if len(_closes) >= 3:
                        _e20r = _closes[0]
                        for _c in _closes[1:]:
                            _e20r = _c * (2 / 21) + _e20r * (1 - 2 / 21)
                    if _e20r > 0 and _lo <= _e20r:
                        cache[t]["rocket_touched"] = True         # Kev: pullback reached the 20 EMA
                    if cache[t].get("rocket_touched") and _cl > _bar_high(_pb) and _cl > 0:
                        _rkday = datetime.now(EASTERN).strftime("%Y-%m-%d")
                        if _rocket_day["d"] != _rkday:
                            _rocket_day["d"] = _rkday; _rocket_day["n"] = 0
                        if _rocket_day["n"] >= ROCKET_DAILY_CAP:
                            _log_decision(t, "rocket_capped", price=price, vel=cache[t].get("rocket_vel"))
                            cache[t]["rocket_fired"] = True
                        else:
                            _rstop = cache[t].get("rocket_plow") or price * 0.75
                            _rk_comp = aggregate_bars(cache[t].get("full_bars") or bars, SETUP_TF_MIN)[:-1]
                            if len(_rk_comp) >= EMA20_PERIOD + 2:
                                _re9, _re20, _re90 = calculate_ema9(_rk_comp), calculate_ema20(_rk_comp), calculate_ema90(_rk_comp)
                            else:
                                _re9 = _re20 = _re90 = 0.0
                            print(f"\n🚀🚀 {t} ROCKET DIP-BUY! ${price:.2f} — 20-EMA pullback held, curl over "
                                  f"${_bar_high(_pb):.2f}; stop ${_rstop:.2f} (pullback low) "
                                  f"[#{_rocket_day['n'] + 1}/{ROCKET_DAILY_CAP} today]")
                            breakouts.append((t, price, price, "rocket_catcher",
                                              {"zone_stop": _rstop, "vel": cache[t].get("rocket_vel"),
                                               "ema90": round(_re90, 4), "front_side": _re9 > _re20 > 0,
                                               "ema9": round(_re9, 4), "ema20": round(_re20, 4)}))
                            _log_decision(t, "triggered_rocket", price=price, vel=cache[t].get("rocket_vel"),
                                          stop=_rstop, curl_over=round(_bar_high(_pb), 4))
                            _rocket_day["n"] += 1
                            cache[t]["rocket_fired"] = True
                            continue                              # rocket captured — skip other detectors for t

            # ── Kev's SETUPS come from the 3-MIN chart (#215); the 1-min is only entry timing + risk.
            #    Aggregate the multi-day 1-min series → 3-min so the flat-top base, the 9/20/90 EMAs
            #    (front-side / MA-pullback levels) all read the timeframe Kev actually trades. VWAP,
            #    the live price, room, and the stop/trail/instant-exit stay on the 1-min. ──
            completed = aggregate_bars(cache[t].get("full_bars") or bars, SETUP_TF_MIN)[:-1]
            if len(completed) < EMA20_PERIOD + 2:
                status_parts.append(f"{t}:${price:.2f} (need more 3-min bars)")
                continue

            vwap_tag = f" VWAP:${vwap:.2f}" if vwap > 0 else ""
            ema9  = calculate_ema9(completed)
            ema20 = calculate_ema20(completed)
            ema90 = calculate_ema90(completed)   # DATA-ONLY — recorded at entry, not a filter
            found_entry = False

            # (Topping-tail entry-skip is handled by check_momentum at execution time, on freshly-fetched
            # bars — see is_topping_tail() in check_momentum. No scan-time duplicate needed.)

            # ── 7/31 PULLBACK_FIRST pre-pass: if the pullback detector fires NOW, it wins the name —
            # flat_top is skipped below and the ORIGINAL ma_pullback block (entry type 2) re-detects
            # the same pure function and converts through the existing path. No duplicated logic.
            _ma_first_fire = None
            if PULLBACK_FIRST and not found_entry and vwap > 0 and price > vwap:
                _ma_first_fire = detect_ma_pullback(completed, price)
                if _ma_first_fire:
                    _log_decision(t, "pullback_first_suppress", price=price,
                                  ma=_ma_first_fire["ma_name"], stop=_ma_first_fire["stop"])

            # ── Entry type 1: Flat top breakout ──────────────────────
            # The intraday BASE must be TODAY's 3-min bars — `completed` spans prior days (for the EMAs),
            # so slice to the current session or the first ~12 min of RTH would read a base across the
            # overnight gap (prior-day consolidation) and fire a spurious open-gap "breakout".
            _sess3 = _latest_session(completed)
            if len(_sess3) >= FLAT_TOP_WINDOW and not _ma_first_fire:
                window = _sess3[-FLAT_TOP_WINDOW:]
                highs = [float(b.get("high") or b.get("h") or b.get("close") or b.get("c") or 0) for b in window]
                lows  = [float(b.get("low")  or b.get("l") or b.get("close") or b.get("c") or 0) for b in window]
                w_high = max(h for h in highs if h > 0)
                w_low  = min(l for l in lows  if l > 0)

                if w_low > 0:
                    rng = (w_high - w_low) / w_low
                    is_flat = rng <= FLAT_TOP_MAX_RANGE

                    # ── PULLBACK-ENTRY STATE MACHINE (7/2): arm on the break, ENTER only on the retest+reclaim
                    #    of the level (Kev buys the pullback, not the spike). P0-crude was the winner — every
                    #    added filter (green-close, front-side, wick) HURT it. Dead-duck data: break bars carry
                    #    a median 4% of the day's peak volume, so chasing the tick buys the exhaustion top. ──
                    _pb = cache[t].get("pb")
                    if is_flat and price > w_high and not _pb:
                        cache[t]["pb"] = {"level": w_high, "zone": w_low, "ts": time.time(), "dipped": False}
                        _log_decision(t, "break_armed", price=price, w_high=w_high)
                        status_parts.append(f"{t}:${price:.2f} broke ${w_high:.2f} → waiting for pullback")
                        continue
                    _pb_enter = False
                    if _pb:
                        if time.time() - _pb["ts"] > PULLBACK_TIMEOUT_SECS:
                            cache[t]["pb"] = None                       # stale — let a fresh break re-arm
                            _log_decision(t, "pullback_timeout", price=price, level=_pb["level"])
                        else:
                            if price <= _pb["level"] * (1 + PULLBACK_TOL) or _recent_low_dip(cache[t].get("full_bars") or bars, _pb["level"]):
                                _pb["dipped"] = True                    # pulled back to the level (wick-aware, #73)
                            if (_pb["dipped"] and price > _pb["level"]
                                    and _confirm_reclaim(cache[t].get("full_bars") or bars, _pb["level"])):
                                _pb_enter = True                        # reclaimed + CONFIRMED = Kev's entry
                                w_high, w_low = _pb["level"], _pb["zone"]  # stop/logging off the broken level
                            else:
                                _rc = "reclaimed, awaiting confirm candle" if (_pb["dipped"] and price > _pb["level"]) else f"pullback to ${_pb['level']:.2f}"
                                status_parts.append(f"{t}:${price:.2f} armed → {_rc} (dipped={_pb['dipped']})")
                                continue

                    if _pb_enter:
                        if vwap <= 0:
                            status_parts.append(f"{t}:${price:.2f} BREAK but no VWAP — skipped")
                            _log_decision(t, "broke_no_vwap", price=price, w_high=w_high)
                            continue
                        if price < vwap:
                            status_parts.append(f"{t}:${price:.2f} BREAK but below VWAP{vwap_tag}")
                            _log_decision(t, "broke_below_vwap", price=price, vwap=vwap, w_high=w_high)
                            continue
                        # ── Kev's ROOM gate is the anti-chase filter (replaced the untested 4% VWAP-
                        # extension cap — Kev uses ROOM to the next supply, NOT a fixed % above VWAP. A
                        # clean breakout to new highs is fine "extended" (open room); an into-supply
                        # breakout isn't (no room). The cap would have rejected Kev's COODX +4.5% winner). ──
                        # Kev (SUPPLY_EXIT_DESIGN step 1): stop = bottom of the demand zone = the
                        # flat-top base low, a few cents below it. R is measured off THIS — never the
                        # made-up -7%, which is now only a catastrophe cap (max risk). One structural
                        # stop, used consistently for the room gate, R, and the broker stop.
                        _zone = round(w_low * (1 - ZONE_STOP_BUFFER), 4)
                        _stop = max(_zone, round(price * (1 - STOP_LOSS_PCT), 4))
                        # ── Kev DAILY-FIRST veto (#067 "if the daily is bad I will not take the trade")
                        #    + room to the next SIGNIFICANT level on the DAILY chart (#057). Daily levels
                        #    fetched once per ticker per session and cached. ──
                        if "daily" not in cache[t]:
                            cache[t]["daily"] = get_daily_levels(t)
                        _daily = cache[t]["daily"]
                        if _daily and not daily_first_ok(price, _daily):
                            # OBSERVE-MODE 7/26 (Marcos: "exempt it on the slow lanes despite being contrary to
                            # Kev. The data at the end of the week will decide") — row kept, block removed.
                            # Era cohort n=285: blocked ≈ kept (0.98R vs 1.30R), non-discriminating (ledger 7/26).
                            print(f"📎 {t}: DAILY BAD (observed, not blocked) — ${price:.2f} below daily 20/50 MA")
                            _log_decision(t, "broke_daily_bad", price=price, enforced=False)
                        room = compute_room(price, _stop, cache[t].get("full_bars") or bars,
                                            daily=_daily, prior_day_high=(_daily or {}).get("prior_day_high"))
                        rr = room["rr_to_supply"]
                        # ROOM DE-INVERTED (7/2): the hard room≥2:1 reject was INVERTED — it rejected the
                        # MOVERS (a stock breaking THROUGH its nearest level has tiny "room") and passed the
                        # QUIET names (far from the next level = lots of "room"). Proven on 3 days: names it
                        # passed averaged +13% first-hour move vs +15% for the ones it rejected; corr(room,
                        # move) = −0.12; every +40–180% mover FAILED it. Volume-surge momentum (check_momentum)
                        # is now the primary entry filter; room is kept only as data + the exit target/tier2.
                        # 3-day backtest: −0.20 → +0.26 avg-R. [[feedback_grade_gates_vs_outcomes]]
                        if rr is not None and rr < MIN_ROOM_RR:
                            _log_decision(t, "low_room_soft", price=price, room_rr=rr,
                                          next_supply=room.get("next_supply"), supply_src=room.get("supply_src"))
                        print(f"\n✅ {t} FLAT TOP BREAKOUT! ${price:.2f} > window high ${w_high:.2f} "
                              f"(range {rng*100:.1f}%, {FLAT_TOP_WINDOW}-bar window) | "
                              f"room {room['rr_to_supply']}:1 to ${room['next_supply']} ({room['supply_src']})"
                              + (f" VWAP:${vwap:.2f}" if vwap > 0 else ""))
                        # front-side = 9>20 EMA (Kev #006). OBSERVE-not-gate on the flat-top breakout: log it +
                        # carry it to the exit record so we can learn from DATA whether back-side (9<20) breakouts
                        # underperform, THEN decide whether to hard-gate. [revisit — feedback_widen_within_kev_realm]
                        _front = ema9 > ema20 > 0
                        breakouts.append((t, price, vwap, "flat_top",
                                          {"ema90": round(ema90, 4), "room": room, "zone_stop": _stop,
                                           "front_side": _front, "ema9": round(ema9, 4), "ema20": round(ema20, 4)}))
                        _log_decision(t, "triggered_flat_top", price=price, room_rr=rr, w_high=w_high, front_side=_front)
                        cache[t]["pb"] = None          # armed pullback consumed by the entry
                        found_entry = True
                    elif is_flat:
                        gap_to_break = (w_high - price) / price * 100
                        status_parts.append(f"{t}:${price:.2f} flat({rng*100:.1f}%) hi:${w_high:.2f} -{gap_to_break:.1f}%{vwap_tag}")
                        _log_decision(t, "consolidating", price=price, vwap=vwap, w_high=w_high, rng_pct=round(rng*100, 1))
                    elif price > w_high:
                        # NEW HIGH but the base wasn't "flat" (range > FLAT_TOP_MAX_RANGE) — THE detection gap:
                        # SDOT/IVF/ILLR/ZDAI were clean base-breaks the 4-bar/8% flat-top never classifies. This
                        # record is what lets us SEE that (and size the rally-base-rally build).
                        status_parts.append(f"{t}:${price:.2f} NEW HIGH but base not flat (rng {rng*100:.0f}%) hi:${w_high:.2f}{vwap_tag}")
                        _log_decision(t, "broke_not_flat", price=price, w_high=w_high, rng_pct=round(rng*100, 1), vwap=vwap)

            # ── Entry type 3: OPENING-RANGE BREAKOUT (Kev's 5-min ORB, #275/#064). The OR (9:30–9:35
            #    high) is a base the rigid flat-top can miss when a gapper opens wide. After the OR window
            #    closes (9:35 ET), the FIRST break above the OR high with room = entry — same gates as the
            #    other setups (above VWAP + room≥2:1 + daily-first + front-side observed). Fires ONCE per
            #    ticker; later re-breaks of the same level are continuations handled by flat-top/re-entry.
            #    [widen within Kev's realm — feedback_widen_within_kev_realm] ──
            if (not found_entry and not _ma_first_fire            # 7/31 PULLBACK_FIRST outranks ORB too
                    and vwap > 0 and price > vwap
                    and (now.hour * 60 + now.minute) >= 575 and not cache[t].get("orb_fired")):
                if "orb" not in cache[t]:
                    cache[t]["orb"] = opening_range(_latest_session(cache[t].get("full_bars") or bars))
                _orb = cache[t]["orb"]
                if _orb:
                    orb_hi, orb_lo = _orb
                    # ── PULLBACK-ENTRY for the ORB (7/2): arm on the OR-high break, ENTER only on the
                    #    retest+reclaim+CONFIRMATION — same discipline as the flat-top (don't buy the raw tick;
                    #    the CMMB-style ORB chase is the exact mistake). Distinct cache key "pb_orb". ──
                    _po = cache[t].get("pb_orb")
                    if price > orb_hi and not _po:
                        cache[t]["pb_orb"] = {"level": orb_hi, "zone": orb_lo, "ts": time.time(), "dipped": False}
                        _log_decision(t, "orb_break_armed", price=price, orb_high=orb_hi)
                        status_parts.append(f"{t}:${price:.2f} broke OR-high ${orb_hi:.2f} → waiting for pullback")
                    elif _po:
                        _oenter = False
                        if time.time() - _po["ts"] > PULLBACK_TIMEOUT_SECS:
                            cache[t]["pb_orb"] = None
                            _log_decision(t, "orb_pullback_timeout", price=price, level=_po["level"])
                        else:
                            if price <= _po["level"] * (1 + PULLBACK_TOL) or _recent_low_dip(cache[t].get("full_bars") or bars, _po["level"]):
                                _po["dipped"] = True                    # wick-aware (#73)
                            if (_po["dipped"] and price > _po["level"]
                                    and _confirm_reclaim(cache[t].get("full_bars") or bars, _po["level"])):
                                _oenter = True
                            else:
                                _orc = "reclaimed, awaiting confirm candle" if (_po["dipped"] and price > _po["level"]) else f"pullback to ${_po['level']:.2f}"
                                status_parts.append(f"{t}:${price:.2f} ORB armed → {_orc} (dipped={_po['dipped']})")
                        if _oenter:
                            _ostop = max(round(orb_lo * (1 - ZONE_STOP_BUFFER), 4), round(price * (1 - STOP_LOSS_PCT), 4))
                            if "daily" not in cache[t]:
                                cache[t]["daily"] = get_daily_levels(t)
                            _daily = cache[t]["daily"]
                            room = compute_room(price, _ostop, cache[t].get("full_bars") or bars,
                                                daily=_daily, prior_day_high=(_daily or {}).get("prior_day_high"))
                            rr = room["rr_to_supply"]
                            _daily_bad = bool(_daily) and not daily_first_ok(price, _daily)
                            if _daily_bad:
                                # OBSERVE-MODE 7/26 — row kept, block removed (see broke_daily_bad note).
                                _log_decision(t, "orb_daily_bad", price=price, room_rr=rr, orb_high=orb_hi,
                                              enforced=False)
                            if True:
                                if rr is not None and rr < MIN_ROOM_RR:   # room DE-INVERTED — observe only (momentum gates)
                                    _log_decision(t, "orb_low_room_soft", price=price, room_rr=rr, orb_high=orb_hi)
                                _front = ema9 > ema20 > 0
                                print(f"\n✅ {t} ORB BREAKOUT (confirmed retest)! ${price:.2f} > OR-high ${orb_hi:.2f} "
                                      f"(OR {orb_lo:.2f}–{orb_hi:.2f}) | room {rr}:1 to ${room['next_supply']} "
                                      f"({room['supply_src']}) VWAP:${vwap:.2f}")
                                breakouts.append((t, price, vwap, "orb",
                                                  {"ema90": round(ema90, 4), "room": room, "zone_stop": _ostop,
                                                   "front_side": _front, "ema9": round(ema9, 4), "ema20": round(ema20, 4),
                                                   "orb_high": orb_hi}))
                                _log_decision(t, "triggered_orb", price=price, room_rr=rr, orb_high=orb_hi, front_side=_front)
                                cache[t]["orb_fired"] = True
                                cache[t]["pb_orb"] = None
                                found_entry = True

            # ── Entry type 2: MA pullback (Kev — 9/20/50/90, whichever rising MA the pullback HOLDS) ──
            # Unified pullback entry (replaced the old narrower EMA9-bounce): one wick-off-low + room logic
            # across all of Kev's MAs.
            if not found_entry and vwap > 0 and price > vwap:   # above VWAP (don't fight below it)
                ma_pb = detect_ma_pullback(completed, price)
                if ma_pb:
                    ma_stop = ma_pb["stop"]
                    if "daily" not in cache[t]:
                        cache[t]["daily"] = get_daily_levels(t)
                    _daily = cache[t]["daily"]
                    room = compute_room(price, ma_stop, cache[t].get("full_bars") or bars,
                                        daily=_daily, prior_day_high=(_daily or {}).get("prior_day_high"))
                    rr_room = room["rr_to_supply"]
                    _daily_bad = bool(_daily) and not daily_first_ok(price, _daily)
                    if _daily_bad:
                        # OBSERVE-MODE 7/26 — row kept, block removed (see broke_daily_bad note).
                        print(f"📎 {t} {ma_pb['ma_name']} pullback — DAILY BAD (observed, not blocked)")
                        _log_decision(t, "ma_daily_bad", price=price, room_rr=rr_room, enforced=False)
                    if True:
                        if rr_room is not None and rr_room < MIN_ROOM_RR:   # room DE-INVERTED — observe only (momentum gates)
                            _log_decision(t, "ma_low_room_soft", price=price, room_rr=rr_room)
                        target = room.get("next_supply") or round(price * (1 + TARGET_PCT), 4)
                        print(f"\n✅ {t} {ma_pb['ma_name'].upper()} PULLBACK! ${price:.2f} held ${ma_pb['ma']:.2f} "
                              f"(wick-off-low, stop ${ma_stop:.2f}) | room {rr_room}:1 to ${target} "
                              f"({room['supply_src']}) VWAP:${vwap:.2f}")
                        breakouts.append((t, price, vwap, "ma_pullback", {
                            "ema_stop": ma_stop, "prior_high": target,
                            "ema90": round(ema90, 4), "room": room, "ma_held": ma_pb["ma_name"],
                            "front_side": True, "ema9": round(ema9, 4), "ema20": round(ema20, 4),   # pullback is 9>20-gated
                        }))
                        _log_decision(t, "triggered_ma_pullback", price=price, ma=ma_pb["ma_name"])
                        found_entry = True

            # ── Entry type 4: MEAN-REVERSION BOUNCE (Kev #28) — a dumped former runner reclaims a demand
            #    level (double-bottom / 20 EMA). NOT gated on above-VWAP (it reclaims from below). Managed on
            #    the 3-min chart like the pullback; risk the low, target the prior HOD. ──
            if not found_entry:
                bnc = detect_bounce(completed, price)
                if bnc:
                    b_stop = bnc["stop"]
                    if "daily" not in cache[t]:
                        cache[t]["daily"] = get_daily_levels(t)
                    _daily = cache[t]["daily"]
                    room = compute_room(price, b_stop, cache[t].get("full_bars") or bars,
                                        daily=_daily, prior_day_high=(_daily or {}).get("prior_day_high"))
                    _bfront = ema9 > ema20 > 0
                    print(f"\n🔄 {t} BOUNCE ({bnc['kind']})! ${price:.2f} reclaim — stop ${b_stop:.2f}, "
                          f"target prior HOD ${bnc['target']:.2f}{vwap_tag}")
                    breakouts.append((t, price, vwap, "bounce", {
                        "zone_stop": b_stop, "room": room, "prior_high": bnc["target"],
                        "ema90": round(ema90, 4), "front_side": _bfront,
                        "ema9": round(ema9, 4), "ema20": round(ema20, 4),
                    }))
                    _log_decision(t, "triggered_bounce", price=price, kind=bnc["kind"])
                    found_entry = True

            # ── CURL LANES (zone-flip + Kev reclaim): converted AT DETECTION since 7/24 — see the
            #    CONVERT-AT-DETECTION block at the top of this loop. The old consume branches lived
            #    here, BELOW the 3-min warmup guard, so fires were detected then dropped before the
            #    trade branch ever ran (7/24: 26 RTH fires, 0 conversions). Non-converted fires are
            #    already shadow-logged at detection; nothing to do here. ──

            if not found_entry and t not in [s.split(":")[0] for s in status_parts]:
                status_parts.append(f"{t}:${price:.2f} EMA9:${ema9:.2f}{vwap_tag}")
                _log_decision(t, "watching", price=price, vwap=vwap)

        # bounce = observe-only (dropped; its backtest read was clearly −0.40, needs reversal-regime data).
        # Others active per BREAKOUT_ENTRIES: True → full bag; False → pullback + VWAP-reclaim only.
        breakouts = [b for b in breakouts
                     if b[3] != "bounce" and (BREAKOUT_ENTRIES or b[3] in ("ma_pullback", "vwap_reclaim", "ignition", "zone_flip", "rocket_catcher", "hidden_entry"))]
        # EXTENSION GUARD — don't chase a name too far above its 90-EMA (7/3 data; Kev "don't chase extended").
        # ── ENTRY-VELOCITY INSTRUMENTATION (7/21 #49-class, LOG-ONLY per sim-integrity/n=8) —
        # kill-test found both 7/21 big losers (IQMX/CJMB) entered with NEGATIVE trailing 5-min
        # velocity (buying a break while the tape falls). Candidate rule = vel5>=0 floor; NOT
        # gated until real n accrues. Stamp entry_vel5 on every breakout for the column-read later.
        for b in breakouts:
            try:
                _vb = _latest_session(cache.get(b[0], {}).get("full_bars") or bars)
                if _vb and len(_vb) > ROCKET_VEL_BARS:
                    _c0, _c1 = _bar_close(_vb[-1 - ROCKET_VEL_BARS]), _bar_close(_vb[-1])
                    if _c0 > 0 and _c1 > 0:
                        b[4]["entry_vel5"] = round((_c1 - _c0) / _c0 * 100, 2)
            except Exception:
                pass
        # ── DAY-GAIN STAMP (7/22, Marcos: "make sure it gets stamped on each decision") — computed for
        # EVERY breakout candidate before any gate touches it, so kept entries carry it into the chart-
        # gate row + trade record and blocked ones carry it in their reject row. Prior close = daily-bar
        # last completed day (cached per ticker/session). Fails open (no stamp) on missing daily data. ──
        for b in breakouts:
            try:
                if "daily" not in cache.setdefault(b[0], {}):
                    cache[b[0]]["daily"] = get_daily_levels(b[0])
                _pdc = ((cache[b[0]].get("daily") or {}).get("prior_day_close") or 0)
                if _pdc > 0:
                    b[4]["day_gain"] = round((b[1] - _pdc) / _pdc * 100, 2)
                    _leader_gain(b[0], b[4]["day_gain"])       # 8/5 leader ammo: gain-proven probe
            except Exception:
                pass
        # ── VEL5 FLOOR (7/21 kill-test, n=56 real trades 7/13-7/21): entries with NEGATIVE trailing
        # 5-min velocity ran ~30% win / −$173 total; >=0 ran +$60. Natural sign boundary (tape falling
        # = knife-catch, Kev waits for the curl), sweep-robust F∈[0,1]. HARD gate on legacy BREAKOUT
        # machines only; curl-entry machines (rocket_catcher / vwap_reclaim / zone_flip) are exempt —
        # their entries are definitionally rising. entry_vel5 None (unmeasured) fails OPEN.
        _kept_v = []
        for b in breakouts:
            _v5 = b[4].get("entry_vel5")
            if (b[3] in ("flat_top", "ma_pullback", "orb", "ema_bounce")
                    # ignition removed 7/26: its 10s fire is definitionally rising (green+strong+break)
                    # but the 1-MIN vel5 window often hasn't printed the surge yet — resolution mismatch
                    # (era n=2 rejects incl. BYRN 7/24, fire graded 1.06-1.38R). Same rationale as the
                    # curl-machine exemption below. Slow lanes stay gated (VINDICATED: blocked = 0.41R).
                    and _v5 is not None and _v5 < 0):
                _log_decision(b[0], "vel5_reject", price=b[1], entry_vel5=_v5, machine=b[3],
                              day_gain=b[4].get("day_gain"))
                print(f"   ⛔ VEL5 FLOOR blocked {b[0]} {b[3]} entry (vel5 {_v5:+.1f}% < 0 — falling tape)")
            else:
                _kept_v.append(b)
        breakouts = _kept_v
        # ── DAY-GAIN FLOOR (7/22 kill-test: +$164.95 on 124 matched trades, sweep-robust, intact
        # ex-ZYBT): LEGACY machines only trade names actually MOVING today (Kev hunts the board's
        # leaders — SKYQ-class +8-24% grinders were the bleed). Curl lanes + Kev-sheet names exempt;
        # fails open when day_gain unmeasured. ──
        if DAYGAIN_FLOOR_PCT > 0:
            _kept_g = []
            for b in breakouts:
                _dg = b[4].get("day_gain")
                if (b[3] in DAYGAIN_LEGACY and _dg is not None and _dg < DAYGAIN_FLOOR_PCT
                        and not _kev_sheet_name(b[0])):
                    _log_decision(b[0], "daygain_reject", price=b[1], day_gain=_dg,
                                  machine=b[3], floor=DAYGAIN_FLOOR_PCT)
                    print(f"   ⛔ DAY-GAIN FLOOR blocked {b[0]} {b[3]} (day gain {_dg:+.1f}% < "
                          f"{DAYGAIN_FLOOR_PCT:.0f}% — not a board leader)")
                else:
                    _kept_g.append(b)
            breakouts = _kept_g
        # 8/8 (Marcos: "add the crown stamp"): crown status AT ENTRY on every candidate — crowns
        # change intraday, and the Friday what-if had to rebuild the set from leader_armed rows.
        for b in breakouts:
            try:
                b[4]["entry_crown"] = bool(_is_leader(b[0]))
            except Exception:
                b[4]["entry_crown"] = None
        # ── 8/5 BACK-SIDE GATE: block the distribution band (see constants block) ──
        if BACKSIDE_GATE:
            _kept_bs = []
            for b in breakouts:
                _dd, _st, _blk = _backside_check(b[0], b[1])
                b[4]["entry_dd_pct"] = _dd
                b[4]["entry_high_stale_min"] = _st
                if _blk and b[3] not in BACKSIDE_EXEMPT:
                    _log_decision(b[0], "backside_reject", price=b[1], dd_pct=_dd,
                                  stale_min=_st, machine=b[3],
                                  band=f"{BACKSIDE_DD_LO}-{BACKSIDE_DD_HI}")
                    print(f"   ⛔ BACK-SIDE gate blocked {b[0]} {b[3]} (entry {_dd}% below a "
                          f"{_st}m-stale high — distribution zone, not a builder)")
                    _slot_refund(b[0], b[3])
                else:
                    _kept_bs.append(b)
            breakouts = _kept_bs
        if EXTENSION_MAX_PCT and EXTENSION_MAX_PCT < 9:
            _kept = []
            for b in breakouts:
                _e90 = (b[4].get("ema90") or 0)
                if b[3] in ("rocket_catcher", "hidden_entry", "flat_top", "orb", "ma_pullback",
                            "vwap_reclaim", "zone_flip"):   # curls added 7/26: fire AT vwap/shelf — same
                                                            # structurally-non-extended claim as hidden (era hits: 0)
                    _kept.append(b)   # rocket-class EXEMPT — catches extension by design (Fable 7/21); hidden entry fires AT the anchor (structurally non-extended, ext logged per fire).
                                      # SLOW RETEST LANES exempt 7/26 (Marcos: "turn off the guard for the slow entries"): the 90-EMA
                                      # anchors in YESTERDAY's prices on gappers, so the guard + day-gain floor squeezed from both
                                      # sides ("must be a mover, can't look extended"). Kill-test: the 17 gradeable extension-rejected
                                      # slow triggers ran 1.69R medMFE / 65% >=1R — ABOVE the kept benchmark (RESULTS_LEDGER 7/26).
                                      # A confirmed retest at a level is not a chase; chart gate still owns level sanity.
                elif _e90 > 0 and (b[1] - _e90) / _e90 > EXTENSION_MAX_PCT:
                    _shadow_keep.add(b[0]); _log_decision(b[0], "extension_reject", price=b[1], ext_pct=round((b[1] - _e90) / _e90 * 100, 1))
                else:
                    _kept.append(b)   # fail-open when there's no 90-EMA to measure
            breakouts = _kept
        if breakouts:
            return breakouts

        if status_parts:
            print(f"📊 {' | '.join(status_parts)}")

        # ── EXEC HEALTH — the loosened config's capacity read: did we choke on 429s / how many positions at once? ──
        # WRAPPED (7/6 crash fix): instrumentation must NEVER crash the trading loop. The live crash was a bad
        # _log_decision arg-binding here (missing the required `status` positional) — a TypeError raised at CALL
        # BINDING, before _log_decision's own try/except could catch it. Correct the call + belt-and-suspenders wrap.
        try:
            with _exec_health_lock:
                _eh = dict(_exec_health)
            print(f"⚙️  EXEC HEALTH: 429={_eh['api_429']} api_err={_eh['api_err']} timeouts={_eh['timeouts']} "
                  f"fail_open={_eh.get('fail_open', 0)} "
                  f"| positions now {len(_active_monitors)} (peak {_eh['peak_positions']})")
            _log_decision("_exec_health", "ok", api_429=_eh["api_429"], api_err=_eh["api_err"],
                          timeouts=_eh["timeouts"], peak_positions=_eh["peak_positions"])
        except Exception as _eh_err:
            print(f"⚠️  exec-health log skipped (non-fatal): {_eh_err}")

        # 5-min live rescan
        if rescan_callback and time.time() - last_rescan >= INTRADAY_RESCAN_INTERVAL:
            print(f"🔄 5-min rescan — checking live market for new setups...")
            _push_market_context()   # refresh the dashboard's S&P/Dow/Nasdaq strip each cycle
            # RE-ENTRY FIX (7/9, JLHL): re-watch is gated on HELD∪GIVENUP, NOT all traded_tickers. A traded-but-
            # ELIGIBLE name (JLHL: caught the ignition, scratched, then ran +112% UNWATCHED) must stay watchable so
            # the normal gates can re-enter it. `traded_tickers` was a PERMANENT lock-out — the root of the JLHL miss.
            if reentry is not None:
                with reentry["lock"]:
                    _reexcl = reentry["held"] | reentry["givenup"]
            else:
                _reexcl = traded_tickers
            new_candidates = rescan_callback(exclude=_reexcl | set(candidates))
            if new_candidates:
                for t in new_candidates:
                    if t not in candidates:
                        candidates.append(t)
                        cache.setdefault(t, {"bars": [], "vwap": 0.0, "fetched": 0.0})   # audit F7: re-add must not wipe prior machine state (#81 class)
                        if t in traded_tickers:   # a previously-traded, now-eligible name coming back for re-entry
                            print(f"   ♻️  Re-watching traded-but-eligible {t} for re-entry (was locked out pre-fix)")
                        print(f"   ➕ Added {t} to flat top watch list")
            last_rescan = time.time()

        time.sleep(VWAP_BAR_CACHE_SECS)


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
        # Webull v2 field is stop_price — aux_price draws OAUTH_OPENAPI_PARAM_ERR
        # (probed 8/2: preview_order 200 with stop_price, 417 with aux_price)
        order["stop_price"] = _px(stop_price)
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


# 8/8 PERIMETER WALL part 1 (the YJ side-door class): execute_trade now DEMANDS a perimeter
# token — set only at the end of the worker's gate chain (the perimeter_stamp site) — so no
# code path can reach a live order without passing every gate. Per-thread; consumed on use.
# Startup self-test path passes explicitly. Kill: PERIMETER_ENFORCE=0 (logs, doesn't refuse).
PERIMETER_ENFORCE = os.environ.get("PERIMETER_ENFORCE", "1") == "1"
_peri_token = threading.local()

def _grant_perimeter():
    _peri_token.ok = True

def execute_trade(ticker, shares, entry_price, stop_loss, target):
    """
    Places a limit buy order (1% above VWAP entry) then a stop order.
    Using LMT instead of MKT caps slippage on small-float fast-moving stocks.
    Retries the buy order once after 3s on transient API failures.
    Returns (buy_client_order_id, stop_client_order_id, actual_fill_price).
    actual_fill_price is the confirmed Webull fill — use it for stop/target/P&L.
    Returns (None, None, None) on failure.
    """
    _tok = getattr(_peri_token, "ok", False)
    _peri_token.ok = False                     # consumed FIRST (auditor F1: a reject below must not leak a blessed token)
    if not _recovery_done.wait(timeout=90):
        print(f"⚠️  BOOT BARRIER: recovery still running after 90s — proceeding fail-open ({ticker})")
        _log_decision(ticker, "barrier_failopen")   # auditor F8: fail-open must be durable, not a log line
    # 8/10 belt+suspenders (the 140-share XHLD dupe): refuse a NEW entry in a ticker the durable
    # store still holds open — the live-state guard can't see positions recovery hasn't
    # re-registered yet. Fail-open on store weather (never blank trading on an API hiccup).
    # auditor F4: the race window runs 300s from RECOVERY COMPLETION, not process birth —
    # a slow recovery must not outlive its own protection.
    _win = (not _recovery_done.is_set()) or (time.time() - (_RECOVERY_DONE_TS[0] or time.time()) < 300)
    if _win:
        try:
            _dupes = _load_open_trades_from_screener()
            if _dupes is None:
                raise RuntimeError("store probe returned None")
            if any((o.get("ticker") == ticker) for o in _dupes):
                print(f"🚫 DUPLICATE-ENTRY GUARD: {ticker} already open in the durable store — refusing second position")
                _log_decision(ticker, "dup_entry_reject", price=entry_price)
                return None, None, None
        except Exception as _dge:
            # auditor F2: inside the race window a FAILED probe is not a clean answer — with real
            # money, unknown store state + possible in-flight recovery = REJECT, loudly. (Fail-open
            # resumes automatically once the window closes.)
            print(f"🚫 DUP-PROBE FAILED in race window ({_dge}) — refusing {ticker} entry (fail-closed)")
            _log_decision(ticker, "dup_probe_failed", price=entry_price)
            return None, None, None
    if not _tok:
        _log_decision(ticker, "perimeter_refused", price=entry_price, shares=shares)
        print(f"🚧 {ticker} PERIMETER: order without a gate-chain token — "
              f"{'REFUSED' if PERIMETER_ENFORCE else 'logged (enforce off)'}")
        if PERIMETER_ENFORCE:
            return None, None, None
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
    Resting exchange stop via Webull OpenAPI v2: order_type=STOP_LOSS + stop_price.
    June's "rejects all stop types" was two param defects at once — "STP"/"STOP LOSS"
    spellings AND aux_price — refuted 8/2 by preview_order probe (HTTP 200, cost
    estimate returned). The software stop in monitor_trade() stays armed regardless;
    this is the crash/freeze backstop, not a replacement.
    RESTING_STOP=0 kills exchange stops (back to software-only) without a redeploy.
    """
    shares = max(1, int(shares))
    if DRY_RUN:
        print(f"🧪 DRY RUN — simulated resting stop: ${stop_price:.2f} × {shares} shares")
        return f"DRY-STOP-{uuid.uuid4().hex[:8]}"   # 8/8 auditor C: fake id -> sync path fully
        # exercisable on paper (was None -> one sync then self-disable = test-push parity gap)
    if not RESTING_STOP:
        print(f"🛡️  Software stop only (RESTING_STOP=0): ${stop_price:.2f} × {shares} shares")
        return None
    result = _place_order(ticker, shares, "SELL", "STOP_LOSS", stop_price=stop_price)
    if result:
        print(f"🛡️  Resting exchange stop placed: ${stop_price:.2f} × {shares} shares")
    else:
        print(f"⚠️  Exchange stop REJECTED — software stop is the only protection on {ticker}")
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

def _vride_defer(ticker, tier_idx, entry_type=None):
    """VELOCITY-AWARE RIDE: True if the move is still accelerating hard → defer this scale (ride the vertical).
    Fail-CLOSED — any error or VELOCITY_RIDE off → False → normal scaling (exact baseline). Streaming makes
    this velocity read fast/clean live; it uses the same 1-min bars monitor_trade already fetches.
    7/30 Q4: lanes in VRIDE_EXEMPT never defer — on hidden the defer fired exactly when the tier was
    reached (a hidden entry IS a ≥25%/5min rocket), suppressing 10 of 11 scale-outs."""
    if not VELOCITY_RIDE:
        return False
    if entry_type in VRIDE_EXEMPT:
        return False
    try:
        rb = _fresh_session(get_intraday_bars(ticker, count=VELO_BARS + 2, sessions=_live_sessions()))   # B16
        if not rb or len(rb) <= VELO_BARS:
            return False
        c_now = float(rb[-1].get("close") or rb[-1].get("c") or 0)
        c_ago = float(rb[-1 - VELO_BARS].get("close") or rb[-1 - VELO_BARS].get("c") or 0)
        if c_ago > 0 and (c_now - c_ago) / c_ago >= VELO_RIDE_PCT:
            print(f"🚀 {ticker}: still accelerating (+{(c_now - c_ago) / c_ago * 100:.0f}% over {VELO_BARS} "
                  f"bars) — deferring scale {tier_idx + 1}, riding the vertical.")
            return True
    except Exception:
        return False
    return False

def _scale_bar_low(ticker):
    """The low of the current/latest 10s bucket at scale time — config F's 'scale-bar low'
    (7/30). Reads the same 10s feed the curl lanes use; hidden IS a 10s lane so the feed is warm.
    Returns None on any failure → caller keeps the existing stop (fail-safe, never widens)."""
    try:
        d10, _src = _curl_feed(ticker, n=6)
        if not d10:
            return None
        lo = d10[max(d10)].get("l")
        return float(lo) if lo and lo > 0 else None
    except Exception:
        return None



def _freshest_rec(ticker):
    """8/6 FRESHEST-DATA (Marcos: "I always believe the most current data, whether it be map
    or KEV. The freshest data must rule."): the record the GATES should see. Kev's slot is
    never altered in storage; but when its vision_shadow (a newer read the server tucked
    alongside) carries a newer timestamp, the gates read the shadow's structure. Timestamps
    are server-stamped (_ts) on every write; shadow read_at is the fallback comparator.
    Fail-safe: any doubt -> Kev's record unchanged (pre-8/6 behavior)."""
    try:
        rec = (_fetch_kev_levels() or {}).get(ticker) or {}
        sh = rec.get("vision_shadow")
        if not isinstance(sh, dict):
            return rec
        rts = str(rec.get("_ts") or "")
        sts = str(sh.get("_ts") or "")
        if sts and (not rts or sts > rts):
            eff = dict(rec)
            for k in ("break", "confirm", "targets", "stop", "next_supply", "blue_sky", "read_at"):
                if sh.get(k) is not None:
                    eff[k] = sh[k]
            eff["_freshest_src"] = "vision_shadow"
            return eff
        return rec
    except Exception:
        return (_fetch_kev_levels() or {}).get(ticker) or {}

# ── 8/7 THE FRESHNESS CONTRACT (Marcos: "we have fixed this a million different times... fucking
# do it!!!" — after the 8th staleness recurrence; YJ +545% ran on maps one-full-map behind).
# CONTRACT: a CROWNED name's effective map is never > FRESH_MAX_MIN old AND never has price
# > FRESH_MAX_DIST% beyond its break. Enforcement: when breached, the gates read an AUTO-MAP
# computed from the live tape (session-window high = wall/break, defended shelf = confirm,
# surviving kev targets above — the NAMI 8/7 arithmetic). Storage is NEVER altered (source
# protection law); only the gates' effective view changes, flagged auto_map. Every breach logs
# a freshness_breach row (120s cadence per name) so violations surface in-day, not in
# screenshots. Kill switch: FRESHNESS_CONTRACT=0. Scope: crowns only (resolution-for-winners).
FRESHNESS_CONTRACT = os.environ.get("FRESHNESS_CONTRACT", "1") == "1"
FRESH_MAX_MIN  = float(os.environ.get("FRESH_MAX_MIN", "10"))    # map age ceiling, minutes
FRESH_MAX_DIST = float(os.environ.get("FRESH_MAX_DIST", "15"))   # px beyond break ceiling, %
_fresh_breach_t = {}   # ticker -> last breach-row time (log cadence only; restart just re-logs)


def _side_state(ticker, px=0.0):
    """8/8 (Side Marshal charter — Marcos: "the bot must always know where a ticker is in
    relation to what's been going on"): the unified SIDE variable, computed from the live tape.
      front_side      — at/near fresh highs, structure building (hh within 5 min OR px >=97% of hi)
      back_side       — >=10% below a >=15-min-stale high (the move is being sold)
      basing          — off-highs but compressed (last-3-min range < 1.5%): coiling, not bleeding
      reclaim_attempt — off-highs, pushing back up (px above the 3-min mean)
    DATA-ONLY v1: stamped on rows (perimeter/heartbeat), consumed by NOTHING until a week of
    stamps grades side-vs-outcome in dollars (the Marshal's law). Fail-soft: unknown on thin tape."""
    try:
        d10, _ = _curl_feed(ticker, n=360)   # 8/8 night: missing unpack made every stamp "unknown"
        if not d10 or len(d10) < 18:
            return "unknown"
        ks = sorted(d10)
        if not px:
            px = float(d10[ks[-1]].get("c") or 0)
        hi = 0.0; hi_k = ks[0]
        for k in ks:
            h = float(d10[k].get("h") or 0)
            if h > hi: hi, hi_k = h, k
        if hi <= 0 or px <= 0:
            return "unknown"
        stale_min = (ks[-1] - hi_k) / 60.0
        dd = (hi - px) / hi * 100.0
        if dd <= 3.0 or stale_min <= 5:
            return "front_side"
        if dd >= 10.0 and stale_min >= 15:
            return "back_side"
        w3 = [d10[k] for k in ks if k >= ks[-1] - 180]
        w3h = max(float(b.get("h") or 0) for b in w3); w3l = min(float(b.get("l") or 0) for b in w3 if float(b.get("l") or 0) > 0)
        if w3l > 0 and (w3h - w3l) / w3l * 100 < 1.5:
            return "basing"
        m3 = sum(float(b.get("c") or 0) for b in w3) / max(len(w3), 1)
        return "reclaim_attempt" if px > m3 else "back_side"
    except Exception:
        return "unknown"

def _map_freshness(rec, live_px):
    """(age_min, dist_pct) of a map vs now/price. age from _ts (fallback read_at, ISO, ET);
    dist = how far price has run BEYOND the map's break (0 when break is overhead/absent).
    Unparseable timestamp -> age None (treated as stale by the contract, never as fresh)."""
    age = None
    try:
        ts = str(rec.get("_ts") or rec.get("read_at") or "")
        if ts:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=EASTERN.utcoffset(datetime.now()) and datetime.now(EASTERN).tzinfo)
            age = (datetime.now(EASTERN) - dt).total_seconds() / 60.0
    except Exception:
        age = None
    dist = 0.0
    try:
        brk = float(rec.get("break") or 0)
        if brk > 0 and live_px > brk:
            dist = (live_px - brk) / brk * 100.0
    except Exception:
        pass
    return age, dist

def _auto_map(ticker, live_px):
    """Tape-computed structural map (maps-describe law: every number a REAL computed anchor).
    Window = _curl_feed(n=720) (2h of 10s bars — the feed's hot bound; anchors are RECENT
    structure by design). break = window high; confirm = defended shelf (highest 10s low
    touched >=3x within 0.25% in the last 3 min; fallback last-3-min low); targets = the
    stored map's targets that survive ABOVE the window high. None if tape too thin (<30 bars)."""
    try:
        d10 = _curl_feed(ticker, n=720)
        if not d10 or len(d10) < 30:
            return None
        ks = sorted(d10)
        hi = max(float(d10[k].get("h") or 0) for k in ks)
        last3 = [d10[k] for k in ks if k >= ks[-1] - 180]
        lows = sorted(float(b.get("l") or 0) for b in last3 if float(b.get("l") or 0) > 0)
        shelf = 0.0
        for lv in reversed(lows):
            if sum(1 for x in lows if abs(x - lv) / lv <= 0.0025) >= 3:
                shelf = lv
                break
        if not shelf and lows:
            shelf = lows[0]
        if hi <= 0:
            return None
        stored = (_fetch_kev_levels() or {}).get(ticker) or {}
        surv = sorted(float(x) for x in (stored.get("targets") or []) if float(x) > hi)
        return {"break": round(hi, 4), "confirm": round(shelf, 4) or None,
                "targets": surv, "auto_map": True,
                "_ts": datetime.now(EASTERN).isoformat()}
    except Exception:
        return None

_effmap_cache = {}   # ticker -> (expires_epoch, rec)  — 8/7 auditor #6: up to 4 gate reads/fire
def _effective_map(ticker, live_px=0.0):
    """THE gates' map view. Fresh (or non-crown, or contract off) -> _freshest_rec unchanged.
    Crowned + contract breached -> auto-map overlay (break/confirm/targets swapped, rest kept),
    breach row logged. Auto-map unavailable -> stale rec unchanged + breach row still logged
    (the meter must never go dark just because the fallback failed)."""
    _c = _effmap_cache.get(ticker)
    if _c and _c[0] > time.time():
        return _c[1]
    rec = _freshest_rec(ticker)
    if not FRESHNESS_CONTRACT or not _is_leader(ticker):
        _effmap_cache[ticker] = (time.time() + 20, rec)
        return rec
    age, dist = _map_freshness(rec or {}, float(live_px or 0))
    stale = (age is None) or (age > FRESH_MAX_MIN) or (dist > FRESH_MAX_DIST)
    if not stale:
        _effmap_cache[ticker] = (time.time() + 20, rec)
        return rec
    am = _auto_map(ticker, float(live_px or 0))
    now = time.time()
    if now - _fresh_breach_t.get(ticker, 0) >= 120:
        _fresh_breach_t[ticker] = now
        _log_decision(ticker, "freshness_breach", price=round(float(live_px or 0), 4),
                      map_age_min=(round(age, 1) if age is not None else None),
                      map_dist_pct=round(dist, 1), auto_map_used=bool(am),
                      old_break=(rec or {}).get("break"),
                      new_break=(am or {}).get("break"))
        print(f"⏱️  {ticker} FRESHNESS BREACH: map age={age if age is None else round(age,1)}m "
              f"dist={dist:.1f}% -> {'AUTO-MAP break $%s' % (am or {}).get('break') if am else 'no tape fallback — stale map kept, breach logged'}")
    if not am:
        return rec
    eff = dict(rec or {})
    for k in ("break", "confirm", "targets"):
        eff[k] = am.get(k)
    eff["auto_map"] = True
    eff["_freshest_src"] = "auto_map"
    # 8/13 20th-convening fix #1 (MARCOS: "I just want the latest data so the bot can make the
    # proper call from it"): the overlay's levels are seconds-old TAPE — carry a fresh timestamp
    # with them, or the blue-sky TTL reads the OLD map's birth certificate off the new map and
    # expires a crowned name holding current structure (the FGI-at-1pm leak, fail-closed but
    # wrong). Freshest-data law: the stamp travels with the data it describes.
    eff["_ts"] = datetime.now(EASTERN).isoformat()
    _effmap_cache[ticker] = (time.time() + 20, eff)
    return eff

def _marked_runway(ticker, entry_price, stop_loss):
    """MARKED RUNWAY (Marcos's thesis): R-multiples of room from entry to the sheet's first target
    above (fallback next_supply). Fully knowable at entry. Returns (rr|'above_all_levels'|None, tgt).
    7/29: extracted so the LIVE card shows the road DURING the trade, not only in the post-mortem —
    identical inputs at entry and at record time, so the two stamps always agree."""
    try:
        _lvd = _effective_map(ticker, entry_price)   # 8/7 freshness contract (was _freshest_rec)
        _rps = entry_price - stop_loss
        if _rps <= 0:
            return None, None
        _tgts = sorted(float(x) for x in (_lvd.get("targets") or []) if float(x) > entry_price)
        _ns = float(_lvd.get("next_supply") or 0)
        # ── 8/8 (#27 completion, Marcos 8/4 directive; 8/7 ROAD fictions = the specimens):
        # THE WALL. The runway must respect what today's tape already did: (a) a rung the price
        # has ALREADY traded above today is SPENT — skip it; (b) if the session high stands
        # between entry and the target, the honest road ends AT THE WALL, not at the ink.
        # (MB 8/7: "150.1R" to a $19.75 ghost while the wall sat 4% up.) Kill: RUNWAY_WALL=0.
        if os.environ.get("RUNWAY_WALL", "1") == "1":
            try:
                _wb = _curl_feed(ticker, n=720)
                _whi = max((float(b.get("h") or 0) for b in _wb.values()), default=0.0) if _wb else 0.0
            except Exception:
                _whi = 0.0
            if _whi > 0:
                _tgts = [x for x in _tgts if x > _whi]          # spent rungs demoted
                if _whi > entry_price * 1.005:
                    _tgts = sorted(_tgts + [round(_whi, 4)])    # the wall IS the nearest road end
                if _ns and _ns <= _whi:
                    _ns = 0.0
        _tgt = (_tgts[0] if _tgts else (_ns if _ns > entry_price else None))
        if _tgt:
            return round((_tgt - entry_price) / _rps, 2), _tgt
        if _lvd.get("targets") or _ns:
            return "above_all_levels", None
    except Exception:
        _gate_failopen("runway", why="exception")   # 8/8 #33
    return None, None


def monitor_trade(ticker, total_shares, entry_price, target_price, stop_loss,
                  stream: WebullStream, stop_order_id, vwap=0, next_supply=None, entry_type="flat_top",
                  entered_premkt=None, runway=None, resume_state=None, trade_id=None):
    _mon_key = trade_id or ticker   # 8/10 per-trade-id books: registry key (XHLD collision fix)
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
    _ratchet_floor     = 0.0   # 8/4 RUNG RATCHET: highest map rung cleared by a 1-min close (0 = none yet)
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
    _status_px         = 0.0           # throttle the 💰 status print (streaming's 0.5s loop floods it otherwise)
    _status_t          = 0.0           # print only on a ≥0.3% move OR every ≥STATUS_PRINT_SECS — keeps real events visible
    _hb_t              = 0.0           # custody heartbeat throttle (7/28) — first row fires on the first loop pass
    _rest_lvl          = stop_loss     # 8/8 RESTING-STOP SYNC: level of the resting order at broker
    _rest_sync_t       = 0.0           # (MB 8/7: fill 50c through a RATCHETED stop the resting order
                                       # never learned about; YJ 91c on the halt reopen — same class)
    _barpx_t           = 0.0           # 7/29 NCRA fix: throttle for quote-dead bar-price lookups
    _barpx             = 0.0           # last bar-close fallback price
    _barpx_on          = False         # currently riding bar closes? (one-line canary on switch)
    _entry_hm          = datetime.now(EASTERN).strftime("%H:%M:%S")  # monitor start ≈ fill time (card display)

    _tape_lo = _tape_hi = None     # 7/27 off-tape guard: the price range this monitor has SEEN in bars
    _last_bars_ok  = time.time()   # B11: when the stop logic last actually SAW a completed bar
    _below_since   = None          # B11: first moment the stream printed below the current stop
    _ib_below_since = None         # intrabar-confirm ledger: first print AT OR BELOW the stop (<=, not <)
    _fetch_fail_n  = 0             # B15: consecutive bar-fetch failures — blindness requires FAILURES, not idle time
    _entry_ts_utc  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")  # B14: stop closes must post-date entry

    initial_shares = total_shares
    # ── 8/8 (#35 PAINLESS RESTARTS): a redeploy mid-trade RESUMES the monitor with its full
    # saved context (partials, tier index, highest, ratcheted stop) instead of restarting
    # blind or force-closing. resume_state = the durable _save_open_trade dict. ──
    if isinstance(resume_state, dict):
        try:
            partial_fills    = [list(p) for p in (resume_state.get("partial_fills") or [])]
            tier_idx         = int(resume_state.get("tier_idx") or 0)
            highest_price    = float(resume_state.get("highest") or entry_price)
            remaining_shares = int(resume_state.get("remaining_shares") or total_shares)
            initial_shares   = int(resume_state.get("initial_shares") or total_shares)
            partial_taken    = bool(partial_fills)
            _rs_stop         = float(resume_state.get("stop") or 0)
            if _rs_stop > 0:
                stop_loss = max(stop_loss, _rs_stop)   # never resume BELOW the ratcheted stop
            print(f"♻️  {ticker} RESUMED mid-trade: rem {remaining_shares}/{initial_shares}, "
                  f"{len(partial_fills)} partial(s), tier {tier_idx}, stop ${stop_loss:.4f}")
            _log_decision(ticker, "trade_resumed", price=entry_price, stop=round(stop_loss, 4),
                          remaining=remaining_shares, partials=len(partial_fills), tier_idx=tier_idx)
        except Exception as _rse:
            print(f"⚠️ {ticker} resume-state restore failed ({_rse}) — monitoring fresh")
    if not isinstance(resume_state, dict):
        tier_idx = 0        # fresh trade default; a resume keeps its restored index (auditor #1)
    # ── Kev's R-based exits (SUPPLY_EXIT_DESIGN.md): R = entry − initial stop. Sell HALF at +1R
    # (risk-free → stop to break-even), trim to a ~1/4 runner at the next supply (or +2R if open room),
    # then the 1/4 runner trails the PREVIOUS-BAR LOW. Replaces the made-up +8/12/20% tiers + TRAIL_PCT. ──
    # F1b (7/26): PRE-ness comes from the CONVERSION stamp when provided — a worker that crosses
    # 09:30 between fill and monitor start must not let a PRE trade escape the 9:25... next-day flatten.
    _entered_premkt = (entered_premkt if entered_premkt is not None
                       else datetime.now(EASTERN).strftime("%H:%M") < "09:30")
    R = max(entry_price - stop_loss, 0.01)
    if isinstance(resume_state, dict) and float(resume_state.get("risk_ps") or 0) > 0:
        R = float(resume_state["risk_ps"])   # auditor #1: R from the ORIGINAL risk, never the
        # ratcheted stop — else tiers collapse onto entry and already-sold tiers re-fire
    if entry_type in ("rocket_catcher", "hidden_entry"):   # ROCKET scale-out ladder (Fable 7/21): %-of-entry, NOT R —
        # a parabola round-trips, so bank 1/3 @ +50%, 1/3 @ +100% on the way up; runner health-trails.
        # Fable evidence: detection-entry + scale-out = +32% mean vs trail20 = +1.5% noise. Runner trail
        # kept as health-trail (hold-above-9EMA) for v1; trail30 vs health-trail = a replay calibration.
        # 7/27 R-TRIM (Fable verdict #3, reversed and reinstated): the inherited ×1.50 first trigger is
        # UNREACHABLE for what this lane actually catches — hidden's closed record is 2/2 peaked-then-red
        # with $0 banked (VEEE 6.9R peak → −$25.33; LVWR 1.62R → −$39.29). Add an R-based FIRST trim
        # beneath the %-ladder; the % tiers are retained above it, runner still ~25%.
        kev_tiers = [(round(entry_price + HIDDEN_TRIM_R * R, 4), 0.33),
                     (round(entry_price * 1.50, 4), 0.55),
                     (round(entry_price * 2.00, 4), 0.75)]
        # Monotonic by construction check: a very wide stop could push the R trim above the ×1.50 tier.
        # Sort by price and keep cumulative non-decreasing so the ladder can never sell out of order.
        _ordered, _cum = [], 0.0
        for _p, _c in sorted(kev_tiers, key=lambda t: t[0]):
            if _c <= _cum:
                continue          # no incremental share to sell — a 1-share order, not a scale-out
            _cum = _c
            _ordered.append((_p, _cum))
        kev_tiers = _ordered
    elif SCALE_TIERS:                                  # reimagined R-grid scale-out (7/5 exit study — beats supply grid)
        kev_tiers = [(round(entry_price + rm * R, 4), cum) for rm, cum in SCALE_TIERS]
    else:
        _scale2 = next_supply if (next_supply and next_supply > entry_price + R) else entry_price + 2 * R
        kev_tiers = [(round(entry_price + R, 4), 0.50),    # +1R  → sell 50%, stop to break-even (risk-free)
                     (round(_scale2, 4), 0.75)]             # supply/+2R → sell 25% (down to a 1/4 runner)
    print(f"   Kev exits: R=${R:.2f} | tiers " + " → ".join(f"{int(c*100)}%@${p:.2f}" for p, c in kev_tiers)
          + " → runner trails (health-trail)")
    # 7/30 RESTING BANK: the full exit scaffold, logged AT ENTRY — the order book we would hand
    # the broker at go-live (stop + a limit at every rung). One durable row per trade; forward
    # fill-quality evidence accrues from the tier_fill rows that reference it.
    if RESTING_BANK:
        _log_decision(ticker, "exit_scaffold", price=round(entry_price, 4),
                      stop=round(stop_loss, 4), entry_type=entry_type,
                      rungs=[[p, c] for p, c in kev_tiers], shares=total_shares)
    last_ema_check     = 0.0           # epoch of last EMA9 bar fetch

    result = {"exit_price": entry_price, "exit_reason": "Unknown",
              "profit_loss": 0, "profit_loss_pct": 0}

    while True:
        now = datetime.now(EASTERN)

        # ── Watchdog took over (this monitor had stalled, then thawed) — bail without re-recording.
        if _mon_key in _monitor_abort or ticker in _monitor_abort:
            _monitor_abort.discard(ticker); _monitor_abort.discard(_mon_key)
            print(f"🛟 {ticker}: watchdog already recorded this trade — monitor exiting")
            result["exit_reason"] = "WATCHDOG_ABORT"
            return result

        # WATCHDOG heartbeat — set UNCONDITIONALLY at the top of every iteration so it means
        # "this loop is alive", independent of feed/price/persist. (If placed lower it would be
        # skipped during a dead-feed `continue`, falsely looking frozen — audit catch.)
        _hb = _active_monitors.get(_mon_key)
        if _hb is not None:
            _hb["heartbeat"] = time.time()

        # ── PREMARKET 9:25 FLATTEN (Marcos 7/25: "time stop the premarket trades at 9:25 —
        # I don't want it affecting RTH"): any trade ENTERED before 09:30 is force-closed at
        # PRE_FLAT_HHMM so premarket practice never carries a position into the open. ──
        if _entered_premkt and now.strftime("%H:%M") >= PRE_FLAT_HHMM and now.strftime("%H:%M") < "10:00":
            print(f"⏰ {PRE_FLAT_HHMM} — premarket flatten: closing {ticker} before the open")
            current_price = stream.get_price(ticker)
            if not current_price or current_price <= 0:
                current_price = last_good_price   # F3 (7/26): a dead quote at flatten must not book the runner as a $0 total loss
            if remaining_shares > 0:
                cancel_order(placed_stop_id)
                close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = f"{PRE_FLAT_HHMM} premarket time stop"
            break

        # ── Hard close at 3:45pm ───────────────────────
        past_end = (now.hour > TRADE_WINDOW_END_HOUR or
                    (now.hour == TRADE_WINDOW_END_HOUR and now.minute >= TRADE_WINDOW_END_MIN))
        if past_end:
            print("⏰ 3:45pm — Force closing all positions")
            current_price = stream.get_price(ticker)
            if not current_price or current_price <= 0:
                current_price = last_good_price   # F3 (7/26): same guard as the premarket flatten
            if remaining_shares > 0:
                cancel_order(placed_stop_id)
                close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "3:45pm time stop"
            break

        current_price = stream.get_price(ticker)
        if current_price <= 0:
            # ── 7/29 NCRA FIX: quote-dead is NOT feed-dead. Premarket has no reliable quote field
            # (session-aware pricing correctly serves NO-PRICE), but the 10s bar tape flows — NCRA
            # was force-closed −$18 mid-flush at 08:06 with `bars=90 last_bar_age=17s` in the same
            # log, then printed +1.05R four minutes later; its structural stop was NEVER touched.
            # Fall back to the freshest 10s bar close (<= BARPX_MAX_AGE) so the STRUCTURAL stop
            # keeps deciding exits. Throttled: one feed lookup per ~5s only while quote-dead.
            if time.time() - _barpx_t >= 5.0:
                _barpx_t = time.time()
                _barpx = 0.0
                try:
                    _d10f, _ = _curl_feed(ticker)
                    if _d10f:
                        _kf = max(_d10f)
                        if time.time() - _kf <= BARPX_MAX_AGE:
                            _barpx = float(_d10f[_kf].get("c") or 0)
                except Exception:
                    _barpx = 0.0
            if _barpx > 0:
                if not _barpx_on:
                    _barpx_on = True
                    print(f"🩹 {ticker} monitor: quote dead — riding 10s BAR closes (${_barpx:.2f}) "
                          f"until the quote returns")
                current_price = _barpx
            else:
                _barpx_on = False
        if current_price <= 0:
            # No valid price FROM EITHER SOURCE. If the feed has been dead too long, a position
            # must NOT sit blind/open (the BOXL freeze) — force-close at last known for safety.
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

        # ── Failed breakout (Kev: "instant resolution or cut") — if the breakout never confirmed
        # (+1.5%) and price has faded back to/below entry within the first ~75s, cut at break-even NOW
        # instead of riding to the −7% stop. Tighter/faster than the VWAP early-fade below. Disarms once
        # it confirms (+1.5%) or after the window — then tiers/trail/stop manage it. ──
        elapsed = time.time() - entry_time
        if (not EXITS_ON_3MIN                                   # 3-min mgmt replaces the sub-minute cut
                and FAILED_BREAKOUT_MIN_SECS <= elapsed <= FAILED_BREAKOUT_SECS
                and highest_price < entry_price * (1 + FAILED_BREAKOUT_CONFIRM)
                and current_price <= entry_price):
            print(f"✂️  Failed breakout — {ticker} faded to ${current_price:.2f} (≤ entry ${entry_price:.2f}) "
                  f"without confirming, {elapsed:.0f}s in. Instant cut (Kev's rule).")
            cancel_order(placed_stop_id)
            close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "Failed breakout ✂️"
            remaining_shares = 0
            break

        # ── Early fade: if price drops back below VWAP within 2 min, cut immediately ──
        if vwap > 0 and not EXITS_ON_3MIN and elapsed <= EARLY_FADE_SECS and current_price < vwap:
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

        # ── Runner protection: the intrabar hard stop = current_stop (STRUCTURE until scale
        # #BE_FLOOR_AFTER_SCALE, then BREAK-EVEN — kev25 floors at the 2nd scale, grid10 at the 1st;
        # see the 7/19 structure-hold change). Close-based structure exits (health-trail while
        # RUNNER_HEALTH_EXIT, else prev-bar-low/topping-tail) run in the EMA section below,
        # NOT through current_stop. ─

        # Throttled status print — only on a ≥0.3% move or every ≥6s (streaming's 0.5s loop otherwise floods the
        # logs with identical lines, risking Railway's rate cap + burying real events). Dashboard still gets every tick.
        if (_status_px <= 0 or abs(current_price - _status_px) / _status_px >= 0.003
                or time.time() - _status_t >= 6):
            print(f"💰 {ticker}: ${current_price:.2f} ({profit_pct:+.1f}%) | Stop: ${current_stop:.2f} | Shares: {remaining_shares}")
            _status_px = current_price; _status_t = time.time()
        # ── CUSTODY HEARTBEAT (7/28, Fable-ordered after the VEEE autopsy dead-ended on vanished
        # console logs). One DURABLE decision row per minute while holding: what the monitor sees
        # (price + its age), what it holds, where its stop/tier is. Turns the next "why didn't it
        # scale" from an autopsy into a query. Non-fatal by construction; ~1 row/min/position.
        # ── 8/8 RESTING-STOP SYNC (auditor A: OUT of the heartbeat throttle — its own 20s
        # cadence; auditor B: PLACE-THEN-CANCEL so a broker rejection never strips protection,
        # and a failed sync retries next pass instead of disabling forever). Never lowers.
        # Kill: RESTING_STOP_SYNC=0. (MB 50c / YJ 91c through-the-stop specimens.) ──
        if (os.environ.get("RESTING_STOP_SYNC", "1") == "1"
                and remaining_shares > 0 and placed_stop_id
                and current_stop > _rest_lvl * 1.0025
                and time.time() - _rest_sync_t >= 20):
            try:
                _new_stop_id = place_stop_order(ticker, remaining_shares, current_stop)
                if _new_stop_id:
                    cancel_order(placed_stop_id)      # old order dies only AFTER the new one lives
                    placed_stop_id = _new_stop_id
                    _rest_lvl = current_stop
                    print(f"🧷 {ticker} resting stop SYNCED to ${current_stop:.4f} "
                          f"({remaining_shares} sh)")
                else:
                    print(f"⚠️ {ticker} resting-stop sync: place rejected — old stop KEPT, retrying")
                _rest_sync_t = time.time()
            except Exception as _rse:
                print(f"⚠️ {ticker} resting-stop sync failed (old stop stands): {_rse}")
                _rest_sync_t = time.time()
        if time.time() - _hb_t >= 60:
            _hb_t = time.time()
            try:
                _log_decision(ticker, "custody_heartbeat",
                              side=_side_state(ticker, current_price),
                              price=round(current_price, 4),
                              price_age_s=round(time.time() - last_good_price_t, 1),
                              rem=remaining_shares, stop=round(current_stop, 4),
                              tier_idx=tier_idx, partials=len(partial_fills),
                              highest=round(highest_price, 4),
                              next_tier=(round(kev_tiers[tier_idx][0], 4)
                                         if tier_idx < len(kev_tiers) else None))
            except Exception:
                pass
        _post_trade_state({
            "ticker": ticker, "entry": round(entry_price, 4), "price": round(current_price, 4),
            "pnl_pct": round(profit_pct, 2), "stop": round(current_stop, 4),
            "target": round(target_price, 4), "remaining_shares": remaining_shares,
            "initial_shares": initial_shares, "partials": len(partial_fills),
            "highest": round(highest_price, 4), "vwap": round(vwap, 4) if vwap else None,
            "entry_hm": _entry_hm,   # 7/28 (Marcos: "i dont see entry time") — fill time on the card
            "entry_session": ("PRE" if _entered_premkt else "RTH"),   # 8/7 (#17; auditor #9: clock-fallback var)
            "runway": runway,        # 7/29 (Marcos: "can it be read on the tale of the tape") — road at entry, live
        })
        # Durable recovery state — survives a crash/restart so this trade still gets a recorded exit.
        # 8/11 GHOST FIX: trade_id was MISSING here, so this recurring post upserted a SECOND,
        # ticker-keyed row beside the entry's id-keyed row; exit cleared only the id row and the
        # ticker row lived forever (8 ghosts on 8/11). One key = one row = one clear.
        _save_open_trade({
            "trade_id": trade_id,
            "ticker": ticker, "entry_price": round(entry_price, 4), "target": round(target_price, 4),
            "stop": round(current_stop, 4), "remaining_shares": remaining_shares,
            "initial_shares": initial_shares, "highest": round(highest_price, 4),
            "tier_idx": tier_idx, "partial_fills": partial_fills, "vwap": round(vwap, 4) if vwap else 0,
            "last_price": round(current_price, 4),
            # Static plan fields for the dashboard's tale-of-the-tape (constant per trade)
            "tiers": [[p, c] for p, c in kev_tiers], "risk_ps": round(R, 4),
            "entry_session": ("PRE" if _entered_premkt else "RTH"),   # 8/7 (#17; auditor #9)
        })
        # Refresh the watchdog's recordable context (heartbeat itself is set at the loop top).
        _m = _active_monitors.get(_mon_key)
        if _m is not None:
            _m["ctx"].update({"remaining_shares": remaining_shares, "partial_fills": partial_fills,
                              "tier_idx": tier_idx, "highest": round(highest_price, 4),
                              "stop": round(current_stop, 4), "last_price": round(current_price, 4),
                              "tape_lo": _tape_lo, "tape_hi": _tape_hi})   # F2: watchdog books through the guard too

        # ── Kev R-based scale-outs: 50% @ +1R (→ risk-free), 25% @ supply/+2R (→ a 1/4 runner) ──
        if tier_idx < len(kev_tiers) and remaining_shares > 0:
            tier_price, tier_cumulative = kev_tiers[tier_idx]
            # 7/30 RESTING BANK: the tier is a resting limit, not a poll — it fills when the TAPE
            # has printed at/through it (_tape_hi, cumulative since entry = exactly the semantics
            # of an order resting since entry) OR the stream sits at/above it. Fill books AT the
            # tier price (a limit fills at its limit, never better — conservative). vride is not
            # consulted while on: a resting order at the broker cannot defer.
            # Tape-only fills demand a STRICT print through the level (not a bare touch) — the
            # no-fiction rule: a touched limit with size ahead may not fill; a traded-through one did.
            _rb_tape = RESTING_BANK and _tape_hi is not None and _tape_hi > tier_price
            if RESTING_BANK:
                _tier_hit = _rb_tape or current_price >= tier_price
                _fill_px = tier_price          # a limit fills at its limit, never better than booked
            else:
                _tier_hit = current_price >= tier_price and not _vride_defer(ticker, tier_idx, entry_type)
                _fill_px = current_price
            if _fill_px <= 0:
                _fill_px = current_price
            if _tier_hit:
                if tier_cumulative >= 1.0:
                    sell_qty = remaining_shares
                else:
                    sold_so_far = initial_shares - remaining_shares
                    target_sold = int(initial_shares * tier_cumulative)
                    sell_qty = max(1, target_sold - sold_so_far)
                    sell_qty = min(sell_qty, remaining_shares)

                tier_label = f"Scale {tier_idx+1}/{len(kev_tiers)}"
                _fill_src = ("resting_tape" if (RESTING_BANK and _rb_tape and current_price < tier_price)
                             else ("resting_stream" if RESTING_BANK else "poll"))
                print(f"💰 {tier_label}: selling {sell_qty} of {remaining_shares} shares "
                      f"at ${_fill_px:.2f} [{_fill_src}] (+{profit_pct:.1f}%) — {'+1R risk-free' if tier_idx == 0 else 'trim to runner'}")
                cancel_order(placed_stop_id)
                close_position(ticker, sell_qty)
                partial_price    = _fill_px
                partial_taken    = True
                partial_fills.append((sell_qty, _fill_px))
                _log_decision(ticker, "tier_fill", price=round(_fill_px, 4), tier=tier_idx + 1,
                              src=_fill_src, qty=sell_qty, stream_px=round(current_price, 4),
                              tape_hi=(round(_tape_hi, 4) if _tape_hi is not None else None))
                remaining_shares -= sell_qty
                tier_idx += 1

                if remaining_shares <= 0:
                    result["exit_price"]  = _fill_px
                    result["exit_reason"] = f"Full exit ({tier_label}) ✅"
                    break

                # Kev structure-hold (7/19): the BE floor arrives only after scale #BE_FLOOR_AFTER_SCALE.
                # Until then the stop stays at STRUCTURE — snapping to entry after the first partial was
                # donating healthy +1R retests back at breakeven (12 BE-scratches → 0 in the kill-test).
                # The prev-bar-low trail still ratchets the runner on a CLOSE basis (EMA section).
                if tier_idx >= BE_FLOOR_AFTER_SCALE:
                    current_stop = entry_price
                # 7/30 A2-F (hidden only, config F of hidden_exit_configs: −$96.04 best of six,
                # walked bar-by-bar): after ANY scale the stop ratchets to the SCALE-BAR LOW — the
                # level the market just defended — never down. Beat breakeven (B) and every offset;
                # NUWE +4.25R→−0.25R is the rig pin this must prevent. Kill: HIDDEN_SCALEBAR_STOP=0.
                if HIDDEN_SCALEBAR_STOP and entry_type == "hidden_entry":
                    _sb_lo = _scale_bar_low(ticker)
                    if _sb_lo and _sb_lo > current_stop:
                        print(f"🪜 {ticker}: stop ratchets to scale-bar low ${_sb_lo:.2f} (was ${current_stop:.2f})")
                        current_stop = _sb_lo
                placed_stop_id    = place_stop_order(ticker, remaining_shares, current_stop)
                _rest_lvl         = current_stop   # 8/8 sync tracker
                placed_stop_price = current_stop
                placed_stop_qty   = remaining_shares
                _floor_lbl = "floored at ENTRY (risk-free)" if current_stop == entry_price else "holding STRUCTURE"
                print(f"📈 Stop {_floor_lbl} ${current_stop:.2f} — {remaining_shares} shares remaining")
                send_partial_exit_alert(ticker, sell_qty, partial_price, entry_price,
                                        remaining_shares, current_stop, profit_pct)

        # ── Structure-based exits: fetch recent bars for the Kev close-based exits below ──────
        # 7/14: jitter the cadence per ticker (±12s) — 7+ monitors born minutes apart tick in sync
        # otherwise, and the synchronized REST burst is what trips Webull's limiter.
        _ema_iv = EMA_CHECK_INTERVAL + (hash(ticker) % 25) - 12
        if remaining_shares > 0 and time.time() - last_ema_check >= _ema_iv:
            # 7/27 BLACKOUT FIX: a PRE position (or any fetch before the bell) must ask for PRE bars —
            # the RTH-only default returns [] premarket, which is exactly how 5 trades went unmonitored.
            bars = get_intraday_bars(ticker, count=(EMA_PERIOD + 6) * SETUP_TF_MIN if EXITS_ON_3MIN else EMA_PERIOD + 5,
                                     sessions=_live_sessions(_entered_premkt or None))
            # B14/B16 (7/15): route EVERYTHING through the fresh-session choke point. In the first
            # minutes of RTH a fetch can return ONLY prior-day bars (XCUR 9:33 — yesterday's close
            # instantly "hit" a fresh stop ×2). Stale/prior-day data → NO exit decision this cycle,
            # and it counts as a SIGHT FAILURE for the B11 blindness ledger.
            bars = _fresh_session(bars)
            # OFF-TAPE EXIT GUARD (7/27): remember the tape this monitor has actually SEEN, from the
            # bars it already fetches — no extra API call. This is the evidence the exit price is
            # checked against at the bottom of the loop.
            for _tb in (bars or []):
                try:
                    _tl = float(_tb.get("low") or _tb.get("l") or 0)
                    _th = float(_tb.get("high") or _tb.get("h") or 0)
                    if _tl > 0:
                        _tape_lo = _tl if _tape_lo is None else min(_tape_lo, _tl)
                    if _th > 0:
                        _tape_hi = _th if _tape_hi is None else max(_tape_hi, _th)
                except Exception:
                    pass
            if not bars:
                _fetch_fail_n += 1
            _cbars = aggregate_bars(bars, SETUP_TF_MIN) if (EXITS_ON_3MIN and bars) else bars
            if _cbars and len(_cbars) >= (3 if EXITS_ON_3MIN else EMA_PERIOD + 2):
                _last_bars_ok = time.time()   # B11: the stop logic has sight
                _fetch_fail_n = 0
                completed = _cbars[:-1]   # 3-MIN completed bars = manage on Kev's chart (EXITS_ON_3MIN), else 1-min

                # ── 3-MIN close-based STOP: exit only when a completed 3-min bar CLOSES at/below the stop. A
                #    wick through it that closes back above is normal volatility, not a failure — this is what
                #    holds the winners. The intrabar −7% catastrophe cap (below) is the only sub-minute stop.
                #    B14: the qualifying close must be from TODAY and must POST-DATE the entry — a close that
                #    predates the entry is pre-breakout history and sits below the stop by construction. ──
                if EXITS_ON_3MIN and remaining_shares > 0:
                    _c3 = float(completed[-1].get("close") or completed[-1].get("c") or 0)
                    if 0 < _c3 <= current_stop and _stop_close_qualifies(completed[-1], _entry_ts_utc):
                        # 7/14 STUDY (observe-only): breach volume ratio — live 13-event sample separated
                        # quiet(shakeout)/loud(death) 12/13, but the harness population did NOT replicate.
                        # Log every real breach; n≥30 live events decides. NO behavior change here.
                        try:
                            _bvols = [_bar_vol(b) for b in completed[-6:-1]]
                            _bbase = (sum(_bvols) / len(_bvols)) if _bvols else 0
                            _bvolx = (_bar_vol(completed[-1]) / _bbase) if _bbase > 0 else -1
                            print(f"🔬 {ticker} breach-volx: {_bvolx:.2f}x (close ${_c3:.2f} vs stop ${current_stop:.2f})")
                        except Exception:
                            pass
                        _lbl = "Trailing stop 📉" if partial_taken else "Stop loss 🛑"
                        print(f"🛑 {_lbl} — 3-min close ${_c3:.2f} ≤ stop ${current_stop:.2f}")
                        cancel_order(placed_stop_id)
                        close_position(ticker, remaining_shares)
                        result["exit_price"]  = current_price
                        result["exit_reason"] = _lbl
                        remaining_shares = 0

                # ── Kev's INSTANT EXIT: a candle makes a NEW high then CLOSES back below the prior bar's
                # high = a major reversal → full exit. ONLY armed AFTER the first scale (partial_taken):
                # real-bar backtest (6/26 Webull bars) showed firing it pre-scale on 1-min noise cut runners
                # for tiny gains (SDOT +1.1% vs the +60% move). Post-scale ~tripled SDOT/BDRX. ──
                if (not RUNNER_HEALTH_EXIT) and remaining_shares > 0 and partial_taken and len(completed) >= 2:
                    _lh  = float(completed[-1].get("high")  or completed[-1].get("h") or 0)
                    _lcl = float(completed[-1].get("close") or completed[-1].get("c") or 0)
                    _ph  = float(completed[-2].get("high")  or completed[-2].get("h") or 0)
                    if _lh > _ph > 0 and 0 < _lcl < _ph:
                        print(f"🚫 {ticker}: new high ${_lh:.2f} rejected back below prior-bar high ${_ph:.2f} "
                              f"(close ${_lcl:.2f}) — Kev INSTANT EXIT.")
                        cancel_order(placed_stop_id)
                        close_position(ticker, remaining_shares)
                        result["exit_price"]  = current_price
                        result["exit_reason"] = "INSTANT EXIT (failed new high)"
                        remaining_shares = 0

                # ── Kev's prev-bar-low TRAIL (close-based — the runner's structural trail after we've
                # scaled). A completed bar CLOSING below the PRIOR bar's low = the up-structure broke →
                # exit the runner. Close-based (not intrabar) so normal pullbacks don't snipe it. ──
                if (not RUNNER_HEALTH_EXIT) and remaining_shares > 0 and partial_taken and len(completed) >= 2:
                    _pl   = float(completed[-2].get("low")   or completed[-2].get("l") or 0)
                    _lcl2 = float(completed[-1].get("close") or completed[-1].get("c") or 0)
                    if _pl > 0 and 0 < _lcl2 < _pl:
                        print(f"📉 {ticker}: bar closed ${_lcl2:.2f} below prior-bar low ${_pl:.2f} "
                              f"— prev-bar-low trail exit (runner).")
                        cancel_order(placed_stop_id)
                        close_position(ticker, remaining_shares)
                        result["exit_price"]  = current_price
                        result["exit_reason"] = "PREV-BAR-LOW TRAIL"
                        remaining_shares = 0

                # (REMOVED 6/29) The EMA9 2-bar stop was the tight moving-average stop Kev explicitly
                # warns against ("stop BELOW the demand zone, not a tight MA/wick — or you get sniped
                # every trade"). On real 6/29 bars it whipsawed the day to break-even. Pre-scale risk is
                # now the STRUCTURAL zone stop (current_stop = zone-low, intrabar); post-scale is
                # break-even + prev-bar-low trail + instant-exit + topping-tail. See [[feedback_fix_root_first]].

                # Kev "topping tail off the high" — his #1 exit. If the last completed bar
                # made a fresh high then got rejected (long upper wick) AND we're in profit,
                # take the money. Only protects a winner — never exits a loser on a wick.
                if (not RUNNER_HEALTH_EXIT) and remaining_shares > 0 and current_price > entry_price:
                    last_high = float(completed[-1].get("high") or completed[-1].get("h") or 0)
                    if last_high >= highest_price * 0.99 and is_topping_tail(completed[-1]):
                        print(f"🔻 Topping tail off the high: {ticker} rejected at ${last_high:.2f} "
                              f"in profit — taking full exit (Kev exit).")
                        cancel_order(placed_stop_id)
                        close_position(ticker, remaining_shares)
                        result["exit_price"]  = current_price
                        result["exit_reason"] = "TOPPING TAIL"
                        remaining_shares = 0

                # ── HEALTH TRAIL (7/3 [[persona_trade_manager]]) — replaces the twitchy soft exits above. HOLD the
                # runner through a pullback while it stays above VWAP OR the 9-EMA (healthy structure); FOLD only when
                # a 3-min bar CLOSES below BOTH (structure gone). Breakeven stop (above) is the hard floor. Data-derived
                # (healthy pullbacks hold VWAP 84%/EMA 67% vs dying 30%/26%); +6R over baseline across 4 days. ──
                # ── 8/4 RUNG RATCHET (Marcos override #4: "we need that new ratchet exit" + AMIX
                # 8/4 six-halt ladder giving back $75+ against a BE-only floor; engine-H replay
                # level_exits_20260804: 92% wins/ties, worst give-back $5.24). Doctrine: a level is
                # resistance until CROSSED (a completed 1-min close above it), support after — so the
                # runner's hard floor climbs to the HIGHEST CLEARED map rung and never comes back
                # down. Complements (never replaces) the health fold: whichever says exit first
                # wins. Map refreshes ride the ~90s _fetch_kev_levels TTL, so a fresh re-read's
                # rungs join the ladder mid-trade (held-name uncapped re-reads, same batch).
                # Kill switch: RUNG_RATCHET=0.
                if RUNG_RATCHET and remaining_shares > 0 and partial_taken and len(completed) >= 1:
                    try:
                        _rl = (_fetch_kev_levels() or {}).get(ticker) or {}
                        _rungs = sorted(set(float(x) for x in (_rl.get("targets") or []) if float(x) > entry_price))
                        _ns_r = float(_rl.get("next_supply") or 0)
                        if _ns_r > entry_price:
                            _rungs = sorted(set(_rungs + [_ns_r]))
                        # 8/4 HB variant (replayed same night, frozen verdict passed: +$10.59 vs H
                        # across 45 trades, worst give-up $4.59): the BREAK level joins the ladder —
                        # a crossed break is the canonical resistance-turned-support (Kev's flip).
                        _bk_r = float(_rl.get("break") or 0)
                        if _bk_r > entry_price:
                            _rungs = sorted(set(_rungs + [_bk_r]))
                        _lc = float(completed[-1].get("close") or completed[-1].get("c") or 0)
                        if _lc > 0:
                            for _r_ in _rungs:
                                if _lc > _r_ and _r_ > _ratchet_floor:
                                    _ratchet_floor = _r_
                                    print(f"🪜 {ticker}: 1-min close ${_lc:.2f} cleared rung ${_r_} — "
                                          f"runner floor ratchets to ${_ratchet_floor:.2f}")
                        if _ratchet_floor > 0 and current_price <= _ratchet_floor:
                            print(f"🪜 {ticker}: ${current_price:.2f} back at/below the highest cleared rung "
                                  f"${_ratchet_floor:.2f} — RUNG RATCHET exit (crossed resistance = support; "
                                  f"defend it, don't watch it go).")
                            cancel_order(placed_stop_id)
                            close_position(ticker, remaining_shares)
                            result["exit_price"]  = current_price
                            result["exit_reason"] = f"RUNG RATCHET (floor ${_ratchet_floor:.2f})"
                            remaining_shares = 0
                    except Exception as _rex:
                        print(f"   ⚠️ {ticker} ratchet check error (non-fatal): {_rex}")

                if RUNNER_HEALTH_EXIT and remaining_shares > 0 and partial_taken and len(completed) >= 2:
                    _hc = float(completed[-1].get("close") or completed[-1].get("c") or 0)
                    _e9 = calculate_ema9(completed)
                    # VWAP for the health read. LIVE DEFAULT (HEALTH_VWAP_SESSION=False) = the shipped/validated
                    # behavior: calculate_vwap over `bars` (the last ~45 M1 EMA window) = a ROLLING VWAP. When the flag
                    # is on, use a full pre+RTH SESSION VWAP (matches Webull's chart). Flag default OFF so nothing changes
                    # until the re-validation clears the switch. _vw_roll always computed for the dual-log comparison.
                    _vw_roll = 0.0
                    try:
                        _vw_roll = calculate_vwap(_latest_session(bars))   # rolling-45 (shipped/validated)
                        if HEALTH_VWAP_SESSION:
                            # 7/14 LOAD RELIEF: the health fold reads session VWAP at 3-MIN closes, but this
                            # 800-bar fetch ran EVERY minute PER POSITION (7 positions = the 429 storm's main
                            # driver). Cache per ticker per 3-min bucket — same value at every decision point.
                            _now3 = datetime.now(EASTERN)
                            _bk = (_now3.date(), _now3.hour, _now3.minute - _now3.minute % 3)
                            _hit = _svwap_cache.get(ticker)
                            if _hit and _hit[0] == _bk and _hit[1] > 0:
                                _vw = _hit[1]
                            else:
                                _svb = get_intraday_bars(ticker, count=VWAP_SESSION_COUNT, sessions=["PRE", "RTH"])
                                _vw  = calculate_vwap(_fresh_session(_svb)) if _svb else _vw_roll
                                if _svb:
                                    _svwap_cache[ticker] = (_bk, _vw)
                        else:
                            _vw  = _vw_roll
                    except Exception:
                        _vw = 0.0
                    if HEALTH_VWAP_SESSION and _vw > 0 and _vw_roll > 0 and abs(_vw_roll - _vw) / _vw >= 0.03:
                        print(f"   🔍 {ticker} VWAP session ${_vw:.3f} vs old rolling-45 ${_vw_roll:.3f} "
                              f"({(_vw_roll - _vw) / _vw * 100:+.0f}%) — health read now uses SESSION VWAP")
                    if _hc > 0 and _e9 > 0 and _vw > 0 and _hc < _e9 and _hc < _vw:
                        print(f"🩺 {ticker}: 3-min close ${_hc:.2f} below EMA9 ${_e9:.2f} AND session-VWAP ${_vw:.2f} "
                              f"(rolling-45 was ${_vw_roll:.2f}) — pullback structure gone, fold the runner.")
                        cancel_order(placed_stop_id)
                        close_position(ticker, remaining_shares)
                        result["exit_price"]  = current_price
                        result["exit_reason"] = "HEALTH FOLD (lost VWAP+EMA)"
                        remaining_shares = 0
            last_ema_check = time.time()

        if remaining_shares == 0:
            break

        # ── B11 DATA-OUTAGE FAILSAFE (7/14, shipped after NVVE went 6 min blind below its stop in a
        #    429 storm and ELWT leaked under its simulated BE floor). Alive-but-blind must not free-fall:
        #    if bars have been unfetchable > B11_BLIND_SECS AND the stream has printed below the CURRENT
        #    stop (initial, BE, or ratcheted) sustained > B11_BELOW_SECS, exit on the stream price.
        #    Fires ONLY when sightless — a healthy flush through the stop with bars flowing is untouched
        #    (the breach-mode replay on real trades showed hair-trigger stops kill the YYGH-class winners). ──
        if remaining_shares > 0 and current_price > 0:
            if current_price < current_stop:
                if _below_since is None:
                    _below_since = time.time()
            else:
                _below_since = None
            # B15 (7/15): blindness = consecutive FETCH FAILURES + elapsed time, via the tested
            # predicate. The old pure-time check (60s) was inside the healthy 48–72s jittered
            # cadence → fired intrabar on healthy tape (UBXG flushed at 4.64, printed 5.00+ a
            # minute later = the refuted breach-mode, accidentally live).
            if _blind_stop_should_fire(now=time.time(), last_bars_ok=_last_bars_ok,
                                       below_since=(_below_since or 0),
                                       fetch_failures=_fetch_fail_n):
                print(f"🛟 {ticker} BLIND-STOP FAILSAFE: no bars for {time.time()-_last_bars_ok:.0f}s "
                      f"({_fetch_fail_n} consecutive fetch failures) and stream ${current_price:.2f} < "
                      f"stop ${current_stop:.2f} for {time.time()-_below_since:.0f}s — exiting on stream.")
                cancel_order(placed_stop_id)
                close_position(ticker, remaining_shares)
                result["exit_price"]  = current_price
                result["exit_reason"] = "BLIND-STOP FAILSAFE 🛟"
                remaining_shares = 0
                break

        # ── TRUE INTRABAR STOP (7/27) — the stream/10s price TOUCHING the stop exits NOW, at the stop
        #    level, instead of waiting for a 3-min close that may print 2–4R lower. Runs on every
        #    iteration (0.5s streaming / 15s polling). Structural 3-min exits above are untouched: they
        #    still govern trailing/health/topping decisions ABOVE the stop. Beneath it sits the crater
        #    floor, which fires even if the stop itself was never actionable. ──
        if remaining_shares > 0 and current_price > 0 and current_price <= current_stop:
            if _ib_below_since is None:
                _ib_below_since = time.time()
        else:
            _ib_below_since = None

        if (INTRABAR_STOP and remaining_shares > 0 and current_price > 0
                and current_price <= current_stop
                # _below_since is maintained by the blind-stop ledger just above: the first moment the
                # stream printed below this stop. At the default 0s this is a no-op (fires on the first
                # print); raise INTRABAR_CONFIRM_SECS to demand the breach persist.
                and (INTRABAR_CONFIRM_SECS <= 0
                     or (_ib_below_since and time.time() - _ib_below_since >= INTRABAR_CONFIRM_SECS))):
            label = "Trailing stop 📉" if partial_taken else "Stop loss 🛑"
            print(f"🛑 INTRABAR {label} — {ticker} traded ${current_price:.2f} ≤ stop ${current_stop:.2f}; "
                  f"selling {remaining_shares} sh now (no 3-min-close wait).")
            cancel_order(placed_stop_id)
            close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = label
            remaining_shares = 0
            break

        if (CRATER_FLOOR_R > 0 and remaining_shares > 0 and current_price > 0
                and current_price <= entry_price - CRATER_FLOOR_R * R):
            print(f"🕳️  {ticker} CRATER FLOOR: ${current_price:.2f} ≤ entry ${entry_price:.2f} − "
                  f"{CRATER_FLOOR_R:.1f}R (${CRATER_FLOOR_R * R:.2f}) — force exit (stop was not actionable).")
            cancel_order(placed_stop_id)
            close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = "CRATER FLOOR 🕳️"
            remaining_shares = 0
            break

        # ── Software stop detection. When EXITS_ON_3MIN there is NO intrabar %-stop — the exit is the 3-min
        #    CLOSE below the structural stop (above); a fixed −7% is non-Kev and just snipes the trade before
        #    the candle closes. Live crater protection is the resting broker stop at the structural level. ──
        if (not EXITS_ON_3MIN) and current_price <= current_stop and remaining_shares > 0:
            label = "Trailing stop 📉" if partial_taken else "Stop loss 🛑"
            print(f"🛑 {label} hit! Selling {remaining_shares} shares at ${current_price:.2f}")
            cancel_order(placed_stop_id)
            close_position(ticker, remaining_shares)
            result["exit_price"]  = current_price
            result["exit_reason"] = label
            remaining_shares = 0
            break

        time.sleep(sleep_secs)

    # ── OFF-TAPE EXIT GUARD (7/27) — the single choke point every one of the 15 exit paths funnels
    #    through, so no exit can book a price this monitor never saw trade. See _verify_exit_px:
    #    all 5 premarket blind-stops on 7/27 booked below the day's low on both 10s feeds (−$624.50).
    #    Booking is corrected to the nearest PROVEN price; the raw print is preserved on the record.
    _bk_px, _raw_px, _px_ok, _px_why = _verify_exit_px(result["exit_price"], _tape_lo, _tape_hi)
    result["exit_px_unverified"] = (not _px_ok) or None
    result["exit_px_raw"] = (round(float(_raw_px), 4) if not _px_ok else None)
    if not _px_ok:
        _tape_str = (f"seen tape ${_tape_lo:.4f}–${(_tape_hi or 0):.4f}" if _tape_lo
                     else "NO tape seen this trade — total feed blindness (F1)")
        print(f"🚩 {ticker} UNVERIFIED EXIT PRICE: ${_raw_px:.4f} is {_px_why.replace('_', ' ')} "
              f"({_tape_str}) — booking ${_bk_px:.4f}. Raw print kept on the record. "
              f"[{result.get('exit_reason')}]")
        try:
            _log_decision(ticker, "off_tape_exit", raw_px=round(float(_raw_px), 4), booked_px=_bk_px,
                          tape_lo=_tape_lo, tape_hi=_tape_hi, why=_px_why,
                          exit_reason=str(result.get("exit_reason"))[:40])
        except Exception:
            pass
        result["exit_price"] = _bk_px

    # ── Blended P&L (sum across all tier fills + remaining) ──
    result["profit_loss"] = _blended_pnl(entry_price, total_shares, partial_fills,
                                         result["exit_price"])

    # 7/11 audit A6: pct must be BLENDED (pnl ÷ initial cost), not the runner's last print — the old
    # formula showed ~0% on a trade that banked +1R on half and runner-exited at breakeven.
    _cost = entry_price * total_shares
    result["profit_loss_pct"] = (result["profit_loss"] / _cost * 100) if _cost > 0 else 0.0
    # Story fields for the dashboard's tale-of-the-tape (banked scale-outs + peak)
    result["partial_fills"] = [[int(q), round(float(p), 4)] for q, p in partial_fills]
    result["highest"] = round(highest_price, 4)
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

    # ── 7/11 audit A4: the TTL above is unreliable (pre-populate fabricates it; the SDK re-rolls it on every
    # init), so the ≤7-day warning can never fire ahead of a real expiry. The only trustworthy check is a LIVE
    # probe: one real market-data call. If it fails, the token/entitlement is dead RIGHT NOW — alert loudly. ──
    try:
        _probe = get_intraday_bars("SPY", count=2)
        if _probe:
            print("🔑 Token LIVE-PROBE: OK (SPY bars returned)")
        elif datetime.now(EASTERN).weekday() >= 5:
            print("⚠️ Token LIVE-PROBE empty — weekend (no alert; data may legitimately be unavailable)")
        else:
            print("🚨 Token LIVE-PROBE FAILED — Webull returned no data for SPY")
            send_alert_email("🚨 Webull token/API FAILING — bot cannot see the market",
                             "The live token probe (1-bar SPY fetch) returned nothing. The bot will silently "
                             "fail to scan/trade until this is fixed.\n\n"
                             "Fix: re-mint the token (webull_setup.py or /api/mint_token with the dashboard "
                             "secret), update WEBULL_ACCESS_TOKEN on Railway, redeploy.")
    except Exception as e:
        print(f"🚨 Token LIVE-PROBE error: {e}")
        send_alert_email("🚨 Webull token/API probe ERROR", f"Live probe raised: {e}")


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


def post_to_dashboard(trade_payload: dict) -> bool:
    """
    POST a completed trade record to the screener app's dashboard endpoint.
    Returns True on confirmed 200 — callers guarding the durable-state clear MUST check it (7/11 audit A1:
    a silently-lost exit record violates the every-trade-reaches-a-recorded-exit invariant).
    """
    if not SCREENER_URL:
        return False
    try:
        resp = requests.post(
            f"{SCREENER_URL}/api/record_trade",
            json=trade_payload,
            headers={"X-Dashboard-Secret": DASHBOARD_SECRET},
            timeout=8,
        )
        if resp.status_code == 200:
            print(f"📊 Trade posted to dashboard ({SCREENER_URL}/dashboard)")
            return True
        print(f"⚠️  Dashboard post failed: {resp.status_code}")
    except Exception as e:
        print(f"⚠️  Dashboard post error: {e}")
    return False


def post_trade_record_reliably(trade_payload: dict, attempts: int = 3, wait_secs: float = 5.0) -> bool:
    """A1: the trade record is the system of record — retry before giving up. Returns True on success."""
    for i in range(attempts):
        if post_to_dashboard(trade_payload):
            return True
        if i < attempts - 1:
            time.sleep(wait_secs)
    print("🚨 trade record NOT persisted after retries — durable recovery state kept for restart re-post")
    return False


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


def _email_trade_tier() -> bool:
    """8/12 EMAIL TIERING (Marcos: 80% of the 100/day Resend quota burned by NOON on per-trade
    emails — and a full quota would SILENCE the critical tier: token failing, watchdog, stalls).
    Trade-tier emails (plan/entry/partial/exit-summary) default OFF in DRY_RUN — the dashboard
    + Duty Officer are the trade feed. EMAIL_TRADE_ALERTS=1 forces on (go-live real fills);
    =0 forces off anywhere. Critical-tier send_alert_email callers are untouched."""
    v = os.environ.get("EMAIL_TRADE_ALERTS")
    if v is not None:
        return v == "1"
    return not DRY_RUN


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
    if not _email_trade_tier():
        print("📪 trade-tier email suppressed (plan) — quota reserved for critical tier"); return
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
    if not _email_trade_tier():
        print(f"📪 trade-tier email suppressed (entry {ticker})"); return
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
        + _section("EXIT PLAN — Kev R-based (SUPPLY_EXIT_DESIGN.md)", (
            _row("R (risk)",                    f"${entry_price - stop_loss:.2f} = entry − stop")
            + _row("💰 +1R → sell 50%",          f"${entry_price + (entry_price - stop_loss):.2f} (risk-free)")
            + _row("💰 supply / +2R → sell 25%", f"~${entry_price + 2*(entry_price - stop_loss):.2f} (to a 1/4 runner)")
            + _row("📈 1/4 runner trails",        "the previous-bar low")
            + _row("🚫 Instant exit",             "new high closes below prior-bar high")
            + _row("🛟 After 1st scale",          "stop → break-even")
            + _row("🛑 Hard Stop",                f"${stop_loss:.2f}")
            + _row("⏰ Hard Close",                "3:45pm ET")
        ), color="#ffbb33")
    )
    send_alert_email(subject, plain, html=html)


def send_partial_exit_alert(ticker, half_shares, partial_price, entry_price,
                            remaining_shares, new_stop, profit_pct):
    """Alert 3 — Fired when half the position is sold at +8% AM / +5% PM."""
    if not _email_trade_tier():
        print(f"📪 trade-tier email suppressed (partial {ticker})"); return
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
    if not _email_trade_tier():
        print("📪 trade-tier email suppressed (per-exit summary)"); return
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

    # Recover the STRUCTURAL stop + target from durable state — NOT a made-up -7%. On a redeploy the
    # in-memory zone_stop is gone, but monitor_trade persisted the real stop ("stop") to the screener.
    # Recomputing -7% here would silently reintroduce the made-up-R bug on every restart (and redeploys
    # are routine for this bot). Fall back to the -7% catastrophe stop ONLY if no saved record exists.
    # [[feedback_fix_root_first]]
    _saved = None
    try:
        for _t in _load_open_trades_from_screener():
            if (_t.get("ticker") or "").upper() == (ticker or "").upper():
                _saved = _t
                break
    except Exception:
        _saved = None
    if _saved and _saved.get("stop"):
        stop_loss    = round(float(_saved["stop"]), 4)
        target_price = round(float(_saved.get("target") or avg_cost * (1 + TARGET_PCT)), 4)
        print(f"   Stop:   ${stop_loss:.4f} (recovered structural stop from saved state)")
        print(f"   Target: ${target_price:.4f}")
    else:
        stop_loss    = round(avg_cost * (1 - STOP_LOSS_PCT), 4)
        target_price = round(avg_cost * (1 + TARGET_PCT), 4)
        print(f"   ⚠️  No saved stop in durable state — using -7% catastrophe fallback: ${stop_loss:.4f}")

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

    _open_trade.pop(ticker, None)   # legacy test-path (ticker-keyed row, if any)
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
        _grant_perimeter()   # 8/8: explicit bless for the startup self-test path
        order_id, stop_order_id, _tt_fill = execute_trade(TEST_TRADE, shares, entry_price, stop_loss, target)  # 8/8: was a 2-name unpack of a 3-tuple (dormant crash)
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

    # Hard time gate — exit if outside WAKE_ET–3:30pm ET (was a hardcoded 8:30 floor that
    # killed premarket day 1). Mid-day restarts (e.g. Railway redeploy) resume until cutoff.
    if not run_window_ok(now):
        print(f"⏰ Outside trading window ({now.strftime('%H:%M')} ET, wake {WAKE_ET}) — exiting.")
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
    gappers = _board_candidates() if BOARD_FUNNEL else scan_morning_gappers()

    # ── #98 PREMARKET STARTER SEED (premarket ONLY — RTH path byte-identical) ──
    # The 4am screener is near-empty (nothing's cleared +8% yet), so without a seed the abort
    # below ends the premarket session before it starts (the 7/22+7/23 blind window). Seed the
    # pool with today's ranked movers + Kev so the machines have names to watch from 4:00.
    _now_seed = datetime.now(EASTERN)
    if (_now_seed.hour * 60 + _now_seed.minute) < (9 * 60 + 30):   # strictly premarket
        _starter = _premarket_starter_set()
        _have = {g.get("symbol") for g in gappers}
        _added = [s for s in _starter if s and s not in _have]
        gappers = gappers + [{"symbol": s, "change_pct": 0.0, "price": 0.0,
                              "source": "premarket_starter"} for s in _added]
        print(f"🌅 Premarket starter seed: +{len(_added)} names "
              f"({len(_have)} from live screener) → {len(gappers)} watching")

    if not gappers:
        print("📋 No candidates from screener — ending session.")
        return

    # ── Step 3: Account balance ────────────────────────────
    balance = get_account_balance()
    if DRY_RUN:
        # REALISTIC-SIZING SIM (7/11): size and ledger against the INTENDED go-live funding, not the real
        # cash-account balance — so paper P&L, risk, and capital collisions are all true-scale.
        print(f"💰 Real balance ${balance:.2f} → DRY_RUN sizing frame: ${SIM_ACCOUNT_BALANCE:.2f} sim account")
        balance = SIM_ACCOUNT_BALANCE
    else:
        print(f"💰 Balance: ${balance:.2f}")
    # 7/29 P2-G: LANE/GUARD STATE BANNER — every boot self-documents its own configuration, so a
    # restart's behavior is readable from one log line instead of inferred from env vars + absences
    # (the 7/29 midday disarm had to be verified by inference).
    print("🎛️  BOOT CONFIG: "
          f"HIDDEN_ENTRY={int(HIDDEN_ENTRY)} RECLAIM_LIVE={int(RECLAIM_LIVE)} "
          f"ZONEFLIP_KEV={int(ZONEFLIP_KEV)} IGNITION_10S={int(IGNITION_10S)} | "
          f"SWAP_MODE={SWAP_MODE} PM_EXT_QUOTE={int(PM_EXT_QUOTE)} DIP_RIP={int(DIP_RIP)} | "
          f"MIN_STOP_PCT={MIN_STOP_DIST_PCT} EXEMPT={sorted(MIN_STOP_EXEMPT)} | "
          f"ENTRY_OPEN_ET={ENTRY_OPEN_ET} INTRABAR_STOP={int(INTRABAR_STOP)} "
          f"BE_FLOOR_AFTER_SCALE={BE_FLOOR_AFTER_SCALE} | "
          # 7/30 change-set switches — every one independently revertible by env:
          f"HIDDEN_EXT_GATE={int(HIDDEN_EXT_GATE)}({HIDDEN_EXT_LO}-{HIDDEN_EXT_HI}) "
          f"HIDDEN_SCALEBAR_STOP={int(HIDDEN_SCALEBAR_STOP)} VRIDE_EXEMPT={sorted(VRIDE_EXEMPT)} "
          f"RESTING_BANK={int(RESTING_BANK)} IGNITION_CONVERT_MULT={IGNITION_CONVERT_MULT} "
          f"IGNITION_CHART_BYPASS={int(IGNITION_CHART_BYPASS)} ZONEFLIP_CONVERT={int(ZONEFLIP_CONVERT)} "
          f"RECLAIM_FIREVOL={RECLAIM_FIREVOL} MIN_RUNWAY_RR={MIN_RUNWAY_RR} "
          f"BREAKSIDE_GATE={int(BREAKSIDE_GATE)}({sorted(BREAKSIDE_LANES)})")
    # 8/3 (#26): the SAME config, as a DURABLE decision row — Railway's CLI log window is ~500
    # lines, so the printed banner is unreadable hours later ("was the floor really 4% at boot"
    # took env+code inference on 8/3 instead of one query). One row per boot, queryable forever.
    try:
        _log_decision("_BOOT", "boot_config",
                      dry_run=bool(DRY_RUN), min_stop_pct=MIN_STOP_DIST_PCT,
                      min_stop_exempt=sorted(MIN_STOP_EXEMPT), min_runway_rr=MIN_RUNWAY_RR,
                      runway_rr_rung=RUNWAY_MIN_RR_RUNG, runway_rr_major=RUNWAY_MIN_RR_MAJOR,
                      rung_ratchet=RUNG_RATCHET,
                      leader_ammo=LEADER_AMMO, leader_gain_min=LEADER_GAIN_MIN,
                      leader_ignition_cap=LEADER_IGNITION_CAP, leader_curl_slots=LEADER_CURL_SLOTS,
                      reentry_crown_usd=REENTRY_CROWN_LOSS_DOLLARS,
                      hidden_ext_crown_bypass=int(HIDDEN_EXT_CROWN_BYPASS), mapless_block=int(MAPLESS_BLOCK),
                      ambient_dvol_mult=AMBIENT_DVOL_MULT,
                      deploy_id=os.environ.get("RAILWAY_DEPLOYMENT_ID", "")[:12],
                      backside_gate=BACKSIDE_GATE, backside_band=f"{BACKSIDE_DD_LO}-{BACKSIDE_DD_HI}", backside_stale=BACKSIDE_STALE_MIN,
                      breakside_gate=int(BREAKSIDE_GATE), breakside_lanes=sorted(BREAKSIDE_LANES),
                      entry_open_et=ENTRY_OPEN_ET, intrabar_stop=int(INTRABAR_STOP),
                      resting_stop=int(RESTING_STOP), be_floor_after_scale=BE_FLOOR_AFTER_SCALE,
                      hidden=int(HIDDEN_ENTRY), reclaim=int(RECLAIM_LIVE),
                      zoneflip_convert=int(ZONEFLIP_CONVERT), ignition_convert=IGNITION_CONVERT_MULT,
                      ignition_bypass=int(IGNITION_CHART_BYPASS), reclaim_firevol=RECLAIM_FIREVOL,
                      swap_mode=SWAP_MODE, crater_floor_r=CRATER_FLOOR_R,
                      tape_prebreak=int(TAPE_PREBREAK_GATE), chart_ceiling=int(CHART_CEILING_GATE),
                      retest_band=(f"{RETEST_BAND_LO}-{RETEST_BAND_HI}" if RETEST_BAND_GATE else "off"))
        _leader_rehydrate()   # 8/5: earned leader status survives restarts
    except Exception as _bc_e:
        print(f"⚠️  boot_config row failed (banner above still printed): {_bc_e}")

    _clear_entries_pause()   # 8/6 deploy-freeze: new image live -> lift the freeze
    _rebuild_counters_from_today()   # 8/8 (#35): honest ledgers after a mid-day restart
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
    # ★ Force-include Kev's flagged tickers, bypassing the top-15 score cut. Selection alone
    #   can't be trusted to surface even qualifiers (6/29: ILLR & AZI both fell out; ILLR was a
    #   real +7.3% miss). If Kev names it, we watch it — entry gates still decide the buy.
    kev_forced = [t for t in _fetch_kev_watchlist() if t not in gapper_syms]
    if kev_forced:
        gapper_syms = gapper_syms + kev_forced
        print(f"⭐ Force-added {len(kev_forced)} of Kev's flagged ticker(s) (bypass top-15): {' | '.join(kev_forced)}")
    print(f"📋 Watching {len(gapper_syms)} candidates: {' | '.join(gapper_syms)}")
    _post_watching_to_screener(gapper_syms)
    _push_market_context()   # populate the dashboard market strip at startup
    _seed_day2_from_gappers(gappers)   # carry today's hard gappers into tomorrow's day-2 observation

    stream_tickers = list(dict.fromkeys(gapper_syms))
    if len(stream_tickers) > 40:   # #98 Feed Engineer canary: Webull PRICE stream (T1 stops, A2) kicks
        print(f"⚠️  WEBULL-SUB CANARY: {len(stream_tickers)} names on the price stream (>40 kick line) "
              f"— get_price will lean on REST for the overflow. Watch for kick/429s; trim seed if chronic.")
    stream         = WebullStream(stream_tickers)
    analysis       = None

    # End-of-day bar archival must ALWAYS run — even if the trade loop exits abnormally or the
    # process winds down before reaching SESSION COMPLETE (the 6/29 warehouse-empty bug). Register
    # it via atexit as a belt-and-suspenders to the layer-(a) 3:30 watch-loop return. Guarded so it
    # runs exactly once (whichever fires first — the explicit end-of-session call or atexit).
    _archived = {"done": False}
    def _do_archive_once():
        if _archived["done"]:
            return
        _archived["done"] = True
        _archive_watchlist_bars(stream_tickers)
    atexit.register(_do_archive_once)

    # ── Steps 8-10: Trade loop ─────────────────────────────────────────────────
    remaining_candidates  = list(gapper_syms)
    traded_tickers        = set()
    trade_count           = 0
    session_pnl           = 0.0
    current_balance       = balance
    settled_remaining     = balance
    trade_lock            = threading.Lock()   # ONE session lock — guards session_pnl/trade_count/
                                               # settled_remaining/current_balance/_open_trade across ALL concurrent workers
    open_threads          = []                 # background trade monitors; joined ONCE at session end (no in-loop join)
    # ── RE-ENTRY (#2) shared state (guarded by trade_lock). Kev re-enters the SAME name on each fresh
    #    reclaim/pullback while it keeps working; gives up STRUCTURALLY (topping tail = "done with it").
    #    held=in a position now (don't double-enter); eligible=exited, may re-qualify through the SAME
    #    gate; givenup=topping-tail/over-cap, leave alone; count/consec_loss for the rail + observability. ──
    reentry = {"held": set(), "eligible": set(), "givenup": set(),
               "count": {}, "consec_loss": {}, "lock": trade_lock}
    _reservations = {}   # ticker → reserved notional (guard: trade_lock). pop() = exactly-once release; the
                         # worker safety-wrapper repairs any leak if a worker thread dies mid-trade (7/11 review).
    _session_cache = {}  # #81 (7/22): per-name machine state that SURVIVES trade-done rescans —
                         # rocket arms, pullback states, once-flags, daily levels, session bars.
    _last_full_scan = [time.time()]   # #81: rescan rate budget (>=240s between full screener sweeps)

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
        # #81 (7/22) RATE BUDGET: the trade-done full rescan was unbudgeted — every completed trade
        # slammed the screener (DataClient init 429s measured all afternoon 7/22). Full rescans now
        # pace at >=240s apart; inside the window the prior candidate list carries forward.
        if trade_count > 0:
            with reentry["lock"]:                       # RE-ENTRY FIX (7/9): exclude only held+givenup, not all traded
                _reexcl = reentry["held"] | reentry["givenup"]
            if time.time() - _last_full_scan[0] < 240:
                print(f"\n🔄 Trade #{trade_count} done — rescan inside 240s budget, carrying prior roster forward")
                remaining_candidates = [t for t in remaining_candidates if t not in _reexcl]
                fresh_gappers = None
            else:
                print(f"\n🔄 Trade #{trade_count} done — rescanning live market for next setup...")
                fresh_gappers = _board_candidates() if BOARD_FUNNEL else scan_morning_gappers()
                _last_full_scan[0] = time.time()
            if fresh_gappers is not None and fresh_gappers:
                remaining_candidates = [g["symbol"] for g in fresh_gappers
                                        if g.get("symbol") and g["symbol"] not in _reexcl]
            elif fresh_gappers is not None:
                # #81 GUARD: a failed/empty rescan (429 etc.) must NOT empty the pool — an empty
                # remaining_candidates below ends the SESSION ("No more candidates"). Keep prior.
                print("⚠️  Rescan returned nothing (throttled?) — keeping prior candidate roster")
                remaining_candidates = [t for t in remaining_candidates if t not in _reexcl]
            # 7/13 B10: the rescan rebuilt the pool from RANK ONLY, silently evicting Kev's
            # force-watched names after the first completed trade (GMM 7/13: decisions stopped
            # 9:56am, then it made a new HOD at 3:15pm unwatched). Re-apply the force-add every
            # rescan — the session-start guarantee "if Kev names it, we watch it" must hold all day.
            _kev_re = [t for t in _fetch_kev_watchlist()
                       if t not in remaining_candidates and t not in _reexcl]
            if _kev_re:
                remaining_candidates += _kev_re
                print(f"⭐ Re-added Kev's flagged (rescan eviction guard): {' | '.join(_kev_re)}")
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
            fresh = _board_candidates() if BOARD_FUNNEL else scan_morning_gappers()
            return [g["symbol"] for g in fresh
                    if g.get("symbol") and g["symbol"] not in exclude]

        breakouts = wait_for_flat_top_entry(
            remaining_candidates, stream,
            rescan_callback=_intraday_rescan,
            traded_tickers=traded_tickers,
            reentry=reentry,
            session_cache=_session_cache,   # #81: machine memory persists across rescans
        )

        if not breakouts:
            print(f"⏰ No entry detected ({', '.join(remaining_candidates)}). Cash preserved.")
            break

        # ── PREMARKET GATE v2 (7/25 Marcos: "Pre-market should be treated DIFFERENTLY than RTH"):
        # before ENTRY_OPEN_ET nothing converts (unchanged). Between ENTRY_OPEN_ET and 09:30 —
        # the PREMARKET PAPER window — ONLY the 10s live-structure lanes (PRE_LANES: hidden_entry,
        # vwap_reclaim — Kev's own premarket classes, STAK 7/17 ran entirely premarket on wick
        # pullbacks) convert, capped at PRE_MAX_TRADES for the whole premarket; the legacy 3-min
        # machines stay SHADOW premarket (thin 5am tape has no 3-min structure worth trusting).
        # Every conversion carries entry_session=PRE → separate ledger, separate grading.
        # ── CAPITAL-PRIORITY ORDER (Marcos 7/26): Kev-sheet names first, then the day's ranked
        # movers (the scanner's Move % column). MOVED ABOVE the premarket gate 7/26 ("ship all 4"):
        # the premarket 6-cap used to keep the FIRST six in arrival order — premarket is exactly
        # where the big boys gap, so the cap must keep the BEST six. Workers later spawn in this
        # order too, so capital reservations follow it all day (near-priority, no preemption). ──
        breakouts.sort(key=_entry_priority)
        if len(breakouts) > 1:
            print("🎖️ entry priority: " + "  >  ".join(
                f"{b[0]}{'*KEV' if _kev_sheet_name(b[0]) else ''}(mv {_move_pct.get(b[0], b[4].get('day_gain'))})"
                for b in breakouts))
        _hm_pm = datetime.now(EASTERN).strftime("%H:%M")
        _in_premkt = ENTRY_OPEN_ET <= _hm_pm < "09:30"
        if _in_premkt:
            _pmday = datetime.now(EASTERN).strftime("%Y-%m-%d")
            if _pre_day["d"] != _pmday:
                _pre_day["d"] = _pmday; _pre_day["n"] = 0
            _kept_pm = []
            _shadow_pm = []
            for entry in breakouts:
                _pm_dvol = 0.0
                try:                                   # cum session $vol from the bot's own 10s store
                    _d10pm, _src_pm = _curl_feed(entry[0])
                    _pm_dvol = sum((b.get("c") or 0) * max((b.get("v1") or 0) - (b.get("v0") or 0), 0)
                                   for b in _d10pm.values())
                except Exception:
                    pass
                if (entry[3] in PRE_LANES
                        and (_pre_day["n"] < PRE_MAX_TRADES or _is_leader(entry[0]))
                        and _pm_dvol >= PRE_MIN_DVOL and _hm_pm < PRE_FLAT_HHMM):
                    # 8/12 CROWN EXEMPTION (Marcos: "if a name gets crowned, it doesn't count
                    # against the 10"): meritocracy extended to the SESSION cap — crowns pass it
                    # AND don't consume slots (see worker recheck); the cap rations the unproven.
                    if _is_leader(entry[0]) and _pre_day["n"] >= PRE_MAX_TRADES:
                        _log_decision(entry[0], "crown_pre_exempt", price=entry[1],
                                      slots_used=_pre_day["n"])
                    # 8/12 CAP RAISE (Marcos verdict: hidden 5 + PRE 8; era kill-test cap_cost_
                    # 20260812): slots beyond the OLD caps get their own row so Friday grades
                    # the marginal cohort in isolation. Busy window = 8:30-9:25 (Marcos's read,
                    # rows-verified: 11/12 conversions 08:52-09:22).
                    if _pre_day["n"] >= 6 and not _is_leader(entry[0]):
                        # auditor note 2 (10th): crowns consume no slot — stamping them would
                        # pollute the marginal cohort Friday grades
                        _log_decision(entry[0], "cap_raise_slot", price=entry[1],
                                      cap="pre8", slot=_pre_day["n"] + 1)
                    # F1a (7/26 exit review): NO conversions in [PRE_FLAT_HHMM, 09:30) — a 9:26 fire
                    # would convert and be flattened on the monitor's FIRST iteration (minted spread-
                    # loss + burned PRE ticket/cap slot). Fires in the dead window shadow instead.
                    # 8/7 (#34 ROOT FIX — the ticket siphon that killed PRE on 8/7): the ticket
                    # is now charged AT EXECUTION (worker, point of no return), so no reject of
                    # any kind (mapless/runway/ambient/retest-expiry/freeze) can ever burn one.
                    # The cap CHECK stays here for selection; the worker re-checks under lock.
                    entry[4]["_pre_convert"] = True   # F1b: PRE-ness decided AT CONVERSION, not by
                    _kept_pm.append(entry)            # the monitor/record wall-clock (worker latency
                                                      # across 09:30 must not turn a PRE trade RTH).
                else:
                    entry[4]["_pm_why"] = ("lane_not_premkt" if entry[3] not in PRE_LANES
                                           else ("premkt_thin" if _pm_dvol < PRE_MIN_DVOL
                                                 else ("premkt_flatten_window" if _hm_pm >= PRE_FLAT_HHMM
                                                       else "premkt_capped")))
                    entry[4]["_pm_dvol"] = round(_pm_dvol)
                    _shadow_pm.append(entry)
                    if entry[4]["_pm_why"] == "premkt_capped":
                        # 8/12: the PRE cap refusal gets its OWN queryable status — the 8/12-am
                        # "never fired" claim was wrong precisely because this lived only in a
                        # shadow-row field no census query could see. Never again.
                        _log_decision(entry[0], "premkt_capped", price=entry[1],
                                      machine=entry[3], pm_dvol=round(_pm_dvol))
            breakouts = _kept_pm
            if _shadow_pm:
                for entry in _shadow_pm:
                    _pt, _pp, _pe = entry[0], entry[1], entry[3]
                    _px2 = entry[4] if len(entry) > 4 else {}
                    _why_pm = (_px2 or {}).get("_pm_why") or "premkt"
                    # stop stamp lane-proof (8/3): each lane names its stop differently — without
                    # this, ma_pullback/ema_bounce shadows were unpriceable (28/70 rows in the 8/3 study)
                    _pm_stop = ((_px2 or {}).get("zone_stop") or (_px2 or {}).get("ema_stop")
                                or (_px2 or {}).get("stop"))
                    _log_decision(_pt, "premarket_shadow_entry", price=_pp, entry_type=_pe,
                                  stop=_pm_stop, time_hm=_hm_pm, why=_why_pm,
                                  dvol=(_px2 or {}).get("_pm_dvol"),
                                  day_gain=(_px2 or {}).get("day_gain"))
                    print(f"👥 {_pt} {_pe} fired {_hm_pm} — premarket SHADOW ({_why_pm})")
                    if _pe == "ignition":
                        _session_cache.get(_pt, {}).pop("ignition_fired", None)
                    elif _pe == "rocket_catcher":
                        _session_cache.get(_pt, {}).pop("rocket_fired", None)
                        _rocket_day["n"] = max(0, _rocket_day["n"] - 1)
                    elif _pe == "hidden_entry":
                        _he_day["PRE"] = max(0, _he_day.get("PRE", 0) - 1)
                        _k_he = (_pmday, _pt, "PRE")
                        _he_name[_k_he] = max(0, _he_name.get(_k_he, 0) - 1)
                    elif _pe == "vwap_reclaim":
                        # 7/26 review finding: a shadowed premarket conversion must REFUND its PRE
                        # ticket, or a thin 5am fire permanently blocks the name's thick 8am reclaim.
                        _curl_rth_n.pop((_pmday, _pt, "vr", "PRE"), None)
                    elif _pe == "zone_flip":
                        _curl_rth_n.pop((_pmday, _pt, "zf", "PRE"), None)
            if not breakouts:
                continue
        if _hm_pm < ENTRY_OPEN_ET:
            for entry in breakouts:
                _pt, _pp, _pe = entry[0], entry[1], entry[3]
                _px2 = entry[4] if len(entry) > 4 else {}
                _log_decision(_pt, "premarket_shadow_entry", price=_pp, entry_type=_pe,
                              stop=((_px2 or {}).get("zone_stop") or (_px2 or {}).get("ema_stop")
                                    or (_px2 or {}).get("stop")), time_hm=_hm_pm,
                              day_gain=(_px2 or {}).get("day_gain"))
                print(f"👥 {_pt} {_pe} fired {_hm_pm} — PREMARKET SHADOW logged, entries open {ENTRY_OPEN_ET}")
                if _pe == "ignition":
                    _session_cache.get(_pt, {}).pop("ignition_fired", None)
                elif _pe == "rocket_catcher":
                    _session_cache.get(_pt, {}).pop("rocket_fired", None)
                    _rocket_day["n"] = max(0, _rocket_day["n"] - 1)
                elif _pe == "hidden_entry":
                    _he_day["PRE"] = max(0, _he_day.get("PRE", 0) - 1)
                    _k_he = (datetime.now(EASTERN).strftime("%Y-%m-%d"), _pt, "PRE")
                    _he_name[_k_he] = max(0, _he_name.get(_k_he, 0) - 1)
                # (7/26: session-keyed tickets stop practice fires spending RTH slots, and shadowed
                # premarket reclaim/zone-flip conversions refund their PRE ticket — see the block above.)
            continue

        # Mark all breakout tickers as traded before threads start
        _fetch_kev_levels()   # pre-warm the chart-gate levels cache ONCE in the main thread, so the
                              # per-worker gate check hits a warm cache instead of N parallel cold
                              # GETs (≤10s each) on the trade path (Fable interaction audit 7/18)
        for entry in breakouts:
            _t = entry[0]
            traded_tickers.add(_t)
            with trade_lock:                       # mark held + count this (re-)entry (#2)
                reentry["held"].add(_t)
                reentry["count"][_t] = reentry["count"].get(_t, 0) + 1
                reentry["eligible"].discard(_t)
            if _t in remaining_candidates:
                remaining_candidates.remove(_t)

        # ── Steps 8-10: Execute + monitor all breakouts as BACKGROUND threads ──────
        # (trade_lock + open_threads are session-scoped — defined once before the loop)

        def _trade_worker(ticker, entry_price, vwap, entry_type="flat_top", extra=None):
            nonlocal session_pnl, trade_count, settled_remaining, current_balance
            extra = extra or {}

            # ── 8/6 DEPLOY-FREEZE: a build is in flight — refuse NEW entries (exits/custody
            #    unaffected; they run in their own monitors). Slot refunded, held released. ──
            if _entries_paused():
                print(f"🧊 {ticker} entry refused — deploy freeze active ({entry_type})")
                _log_decision(ticker, "entries_paused", price=round(float(entry_price), 4),
                              machine=entry_type)
                _slot_refund(ticker, entry_type)
                with trade_lock:
                    reentry["held"].discard(ticker)
                return

            # ── LAYER 2: "No Break, No Trade" chart-level gate — SHADOW unless CHART_GATE_ENFORCE=1 ──
            # Logs the verdict beside EVERY trade so we can validate against real tape before enforcing.
            # Default = shadow: records only, changes nothing. Enforce = block non-'allow' entries.
            _cg_verdict, _cg_reason, _cg_level, _cg_src = _chart_break_gate(ticker, entry_price, entry_type)
            _log_decision(ticker, "chart_gate_" + _cg_verdict,
                          entry=round(float(entry_price), 4), break_level=_cg_level,
                          reason=_cg_reason, src=_cg_src, entry_type=entry_type,
                          enforced=CHART_GATE_ENFORCE, day_gain=extra.get("day_gain"))
            print(f"   📐 CHART-GATE [{'ENFORCE' if CHART_GATE_ENFORCE else 'SHADOW'}] {ticker}: "
                  f"{_cg_verdict.upper()} ({_cg_reason}) — entry ${float(entry_price):.4f} vs level "
                  f"{('$%.4f' % _cg_level) if _cg_level else 'none'}")
            if CHART_GATE_ENFORCE and _cg_verdict != "allow":
                _log_decision(ticker, "chart_gate_blocked_trade",
                              entry=round(float(entry_price), 4), break_level=_cg_level, reason=_cg_reason)
                print(f"   ⛔ CHART-GATE BLOCKED {ticker} entry (no break of marked level) — no trade")
                _slot_refund(ticker, entry_type)
                with trade_lock:
                    reentry["held"].discard(ticker)   # 8/7 (#34 invariant catch): held was leaking here
                return   # ENFORCE mode only: Kev's No-Break-No-Trade blocks this entry

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

            if "ema_stop" in extra:
                stop_loss = round(extra["ema_stop"], 4)
                target_price = round(extra.get("prior_high", entry_price * (1 + TARGET_PCT)), 4)
            else:
                # Flat-top: structural zone stop (Kev), -7% only as fallback if zone is missing
                stop_loss = round((extra.get("zone_stop") or entry_price * (1 - STOP_LOSS_PCT)), 4)
                target_price = round(entry_price * (1 + TARGET_PCT), 4)

            # ── WIDE-STOP FIX STACK (7/10, all default-off; ranked in the 9-day harness before any flip) ──
            _stop_dist = (entry_price - stop_loss) / entry_price if entry_price > 0 else 0
            # C: Kev tight-setup gate — a structural stop >X% away means the base is sloppy, not a Kev setup. Skip.
            if MAX_STOP_DIST_PCT and _stop_dist > MAX_STOP_DIST_PCT:
                print(f"⚠️ {ticker} stop {_stop_dist*100:.1f}% away > {MAX_STOP_DIST_PCT*100:.0f}% tight-setup gate — skipping")
                _log_decision(ticker, "wide_stop_reject", price=entry_price, stop_dist_pct=round(_stop_dist * 100, 1))
                _slot_refund(ticker, entry_type)   # 8/7 (#34 invariant catch): slot was leaking here
                with trade_lock:
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return
            # A: stop clamp — cap the structural stop at entry×(1−X). Number must come from the grade, not the old -7% guess.
            if STOP_MAX_PCT and _stop_dist > STOP_MAX_PCT:
                stop_loss = round(entry_price * (1 - STOP_MAX_PCT), 4)
                print(f"   🔧 {ticker} stop clamped {_stop_dist*100:.1f}% → {STOP_MAX_PCT*100:.0f}% (${stop_loss:.2f})")
            # Degenerate stop (stale EMA / bad tick puts the stop AT/ABOVE entry): unsizeable, skip + log —
            # never fall through to full-notional sizing with a meaningless stop (7/11 review finding 4).
            # 7/29 P0-A (Fable): UNCONDITIONAL — a long ticket whose stop is at/above entry is never
            # valid under ANY sizing mode (AMIX 7/29 09:32 fired with stop 4.6512 > price 4.62; only
            # the now-fixed price swap made it look sizeable).
            if stop_loss >= entry_price:
                print(f"⚠️ {ticker} stop ${stop_loss:.2f} ≥ entry ${entry_price:.2f} — unsizeable, skipping")
                _log_decision(ticker, "bad_stop_skip", price=entry_price, stop=round(stop_loss, 4))
                _slot_refund(ticker, entry_type)
                with trade_lock:
                    reentry["held"].discard(ticker)   # pre-reservation: nothing to refund
                return
            # ── MINIMUM STOP WIDTH gate (7/27, Marcos) — reject when the structural stop is closer than
            # MIN_STOP_DIST_PCT to entry: a stop inside the name's own noise is not a risk definition,
            # and risk-sizing turns it into an outsized share count. Runs on the FINAL stop (after any
            # STOP_MAX_PCT clamp), pre-fill only (the post-fill re-derivation owns a position and cannot
            # skip — F1). The reject row IS the shadow log: width + band ('<4','4-5','5-6') let Friday
            # grade the 4–5%/5–6% cohorts as counterfactuals against real bars.
            _ms_rej, _ms_w, _ms_band = _min_stop_verdict(entry_price, stop_loss, entry_type)
            if _ms_rej:
                print(f"📏 {ticker} stop {_ms_w:.2f}% of entry < {MIN_STOP_DIST_PCT*100:.0f}% minimum "
                      f"(band {_ms_band}) — stop is inside the noise, skipping [minstop gate]")
                _log_decision(ticker, "minstop_reject", price=entry_price, stop=round(stop_loss, 4),
                              stop_width_pct=_ms_w, band=_ms_band, machine=entry_type)
                _slot_refund(ticker, entry_type)
                with trade_lock:
                    reentry["held"].discard(ticker)   # pre-reservation: nothing to refund (mirror bad_stop_skip)
                return
            # ── MINIMUM MARKED RUNWAY gate (7/31, Marcos: "why risk $30 for minimal reward???" +
            # "Not enough runway, we should block"). A TRADEABILITY floor, same class as the min-stop
            # width and liquidity floors — NOT a setup-quality scalar. Distance from entry to the
            # NEXT MARKED LEVEL (Kev's sheet, human-read, known before the trade), expressed in R.
            # NOT the refuted 7/2 room gate: that measured MECHANICAL supply and inverted (it rejected
            # the movers). This reads the marked map.
            # EVIDENCE (pre-registered split, in-session): TRAIN 7/29 <1R n=2 −$70.20 (0% win) vs
            # >=1R n=12 −$136.13. TEST 7/30+7/31 <1R n=12 −$270.04 (17% win) vs >=1R n=22 +$213.02
            # (64%). Blocking sub-1R on TEST forfeits $18.51 of winners to avoid $288.55 of losses.
            # Specimens: AEMD 0.03R (entry 0.72 = the level itself) −$31.35 · MGRX 0.07R −$30.16 ·
            # PN 0.28R/0.67R −$78.00 · TGHL 0.38R −$32.47.
            # FAIL-OPEN BY DESIGN: only a NUMERIC runway blocks. None (no marked level) and
            # 'above_all_levels' (infinite runway) both PASS — never repeat the 7/22 no_marked_level
            # starvation. Kill switch: MIN_RUNWAY_RR=0.
            # FAILURE CONDITION (pre-registered): wrong if the blocked cohort's forward counterfactual
            # (`runway_reject` rows) out-earns the trades that were allowed.
            if MIN_RUNWAY_RR > 0:
                _rw_v, _rw_t = _marked_runway(ticker, entry_price, stop_loss)
                if isinstance(extra, dict):
                    extra["_rw_gate"] = (_rw_v, _rw_t)   # 8/8 auditor E: one runway truth per trade
                # 8/4 class-aware: the threshold depends on WHAT stands overhead — a RUNG
                # (intermediate target, scale point) needs RUNWAY_MIN_RR_RUNG; a MAJOR
                # (break/next_supply/whole-half-dollar, real resistance) needs RUNWAY_MIN_RR_MAJOR.
                _rw_cls  = _runway_level_class(ticker, _rw_t, _effective_map(ticker, entry_price))
                _rw_need = RUNWAY_MIN_RR_MAJOR if _rw_cls == "MAJOR" else RUNWAY_MIN_RR_RUNG
                _rw_band = _road_band(_rw_v)
                if isinstance(_rw_v, (int, float)) and _rw_v < _rw_need:
                    print(f"🛣️  {ticker} runway {_rw_v:.2f}R to {_rw_cls} ${_rw_t} < {_rw_need}R minimum "
                          f"— risking a full R for {_rw_v:.2f}R of road, skipping [runway gate]")
                    _log_decision(ticker, "runway_reject", price=entry_price, stop=round(stop_loss, 4),
                                  runway_rr=_rw_v, target=_rw_t, need=_rw_need, machine=entry_type,
                                  road_cls=_rw_cls, road_band=_rw_band)
                    _slot_refund(ticker, entry_type)
                    with trade_lock:
                        reentry["held"].discard(ticker)
                    return
                if isinstance(_rw_v, (int, float)):
                    # passed with a numeric road — stamp the measurement on a decision row too,
                    # so Friday's threshold curves see the TAKEN side, not only the refused side
                    _log_decision(ticker, "runway_pass", price=entry_price, stop=round(stop_loss, 4),
                                  runway_rr=_rw_v, target=_rw_t, need=_rw_need, machine=entry_type,
                                  road_cls=_rw_cls, road_band=_rw_band)
            # ── BREAK-SIDE gate (7/31, tape lanes only — see the constants block for the full
            # evidence + known costs). At/below the marked break passes; a chase above it blocks
            # and logs its full ticket so Monday's shadow prices the opposite. FAIL-OPEN: no
            # break on the sheet -> pass.
            if BREAKSIDE_GATE and entry_type in BREAKSIDE_LANES:
                try:
                    _bs_rec = _effective_map(ticker, entry_price) or {}   # 8/7 freshness contract
                    _bs_brk = float(_bs_rec.get("break") or 0)
                except Exception:
                    _bs_rec, _bs_brk = {}, 0.0
                if _bs_brk > 0:
                    _bs_gap = (entry_price - _bs_brk) / _bs_brk * 100.0
                    if _bs_gap > BREAKSIDE_MAX_PCT:
                        print(f"📐 {ticker} entry ${entry_price:.2f} is {_bs_gap:+.1f}% ABOVE the marked "
                              f"break ${_bs_brk} — chasing past the level, skipping [break-side gate]")
                        _bs_age, _bs_dist = _map_freshness(_bs_rec, entry_price)   # 8/7 meter stamp
                        _log_decision(ticker, "breakside_reject", price=entry_price,
                                      stop=round(stop_loss, 4), break_level=_bs_brk,
                                      gap_pct=round(_bs_gap, 2), machine=entry_type,
                                      map_age_min=(round(_bs_age, 1) if _bs_age is not None else None),
                                      map_dist_pct=round(_bs_dist, 1),
                                      auto_map=bool(_bs_rec.get("auto_map")))
                        _slot_refund(ticker, entry_type)
                        with trade_lock:
                            reentry["held"].discard(ticker)
                        return
                else:
                    # 8/6 FAIL-CLOSED (Marcos: "close the fail opens for these mapless trades.
                    # And why are we trading anything without a map????") — the FVN specimen:
                    # no map -> breakside/runway had nothing to measure -> ungated_entry walked
                    # into a back-side chase at 0.25:1 room. Ignorance no longer buys permission:
                    # a name with NO levels at all (no break/confirm/targets from Kev or vision)
                    # does not convert on ANY tape lane. Partial maps (confirm/targets, no break)
                    # keep the 7/31 visibility row and proceed — runway can still measure those.
                    # Kill: MAPLESS_BLOCK=0 restores the fail-open. Every refusal logs the full
                    # ticket so the refused cohort stays gradeable forward, same as every gate.
                    try:
                        _ml_rec = _effective_map(ticker, entry_price) or {}   # 8/7 freshness contract:
                        # a CROWNED mapless name gets the auto-map tape floor instead of a blindfold
                        # (Marcos 8/7, the NAMI doctrine); non-crowns unchanged (fail-closed).
                    except Exception:
                        _ml_rec = {}
                    _ml_has_map = bool(_ml_rec.get("break") or _ml_rec.get("confirm") or _ml_rec.get("targets"))
                    # 8/13 #54 Build 1 TTL: a BLUE-SKY map is only as good as its freshness — past
                    # BLUESKY_TTL_SECS it counts as ABSENT (fail-closed back to caged). The FGI
                    # 9:31 fire into the halt-down dies exactly here: its 8am-class map is stale.
                    if _ml_has_map and _ml_rec.get("blue_sky"):
                        try:
                            _bs_ts = datetime.fromisoformat(str(_ml_rec.get("_ts")))
                            _bs_age = (datetime.now(EASTERN) - _bs_ts).total_seconds()
                        except Exception:
                            _bs_age = 1e9                       # unstampable = stale (fail-closed)
                        if _bs_age > BLUESKY_TTL_SECS:
                            _ml_has_map = False
                            _log_decision(ticker, "bluesky_ttl_expired", price=entry_price,
                                          age_s=round(_bs_age), machine=entry_type)
                    if MAPLESS_BLOCK and not _ml_has_map:
                        print(f"🗺️  {ticker} NO MAP (no break/confirm/targets on the sheet) — "
                              f"mapless conversions are CLOSED [8/6] — skipping {entry_type}")
                        _log_decision(ticker, "mapless_reject", price=entry_price,
                                      stop=round(stop_loss, 4), machine=entry_type)
                        _request_auto_read(ticker)              # 8/13 #54 Build 3: fire+no-map -> read NOW
                        _slot_refund(ticker, entry_type)
                        with trade_lock:
                            reentry["held"].discard(ticker)
                        return
                    _log_decision(ticker, "ungated_entry", price=entry_price,
                                  machine=entry_type, gates="breakside,runway")
            # ── ZONE STAMP + TAPE PRE-BREAK GATE (8/3 evening; Marcos: "I refuse to let trades go
            #    forth blind"). EVERY conversion logs WHERE it stands on the day's map: zone, break,
            #    last target, day-high-so-far, retest depth. Dead-zone kill-test (deadzone_20260803):
            #    only ONE cell met the frozen block bar — TAPE lanes below a never-broken-today break
            #    (n=12, −$143.89, NCRA/STAK/BOOM class). Chart pre-break (+$126) and ignition
            #    pre-break (+$67 — CYCU's curl lives there) measured POSITIVE, so they stamp only.
            #    Gauntlet (worst sessions): 7/29 net +$82.72 saved · 7/30 +$72.36 · 8/3 −$8.14 cost.
            #    FAIL-OPEN: no break, or day-high UNKNOWN (name not in the capture archive) → pass.
            #    Kill switch: TAPE_PREBREAK_GATE=0. FAILURE CONDITION (pre-registered): wrong if
            #    prebreak_reject rows' forward counterfactual out-earns the blocked cohort's −$12/t.
            _z_zone, _z_brk, _z_lastT, _z_dayhi, _z_depth = "no_map", 0.0, None, None, None
            try:
                _z_rec = _effective_map(ticker, entry_price)   # 8/7 freshness contract (was _freshest_rec)
                _z_brk = float(_z_rec.get("break") or 0)
                _z_tg = [float(x) for x in (_z_rec.get("targets") or []) if float(x) > 0]
                _z_lastT = max(_z_tg) if _z_tg else None
                if _z_brk > 0:
                    try:
                        _z_req = urllib.request.urlopen(
                            f"{SCREENER_URL}/api/bars?date={datetime.now(EASTERN).strftime('%Y-%m-%d')}"
                            f"&ticker={ticker}~ALP10S", timeout=3)
                        _z_bars = (json.load(_z_req) or {}).get("bars") or []
                        if not _z_bars:   # 8/4: late-join names carry ~ALP1M (join backfill)
                            _z_req2 = urllib.request.urlopen(
                                f"{SCREENER_URL}/api/bars?date={datetime.now(EASTERN).strftime('%Y-%m-%d')}"
                                f"&ticker={ticker}~ALP1M", timeout=3)
                            _z_bars = (json.load(_z_req2) or {}).get("bars") or []
                        _z_his = [float(b.get("high") or b.get("h") or 0) for b in _z_bars]
                        _z_dayhi = max(_z_his) if _z_his else None
                    except Exception:
                        _z_dayhi = None
                    if entry_price < _z_brk:
                        if _z_dayhi is not None and _z_dayhi >= _z_brk:
                            _z_zone = "retest"
                            _z_depth = round((_z_brk - entry_price) / _z_brk * 100.0, 2)
                        elif _z_dayhi is None:
                            _z_zone = "pre_break_unverified"
                        else:
                            _z_zone = "pre_break"
                    elif _z_lastT is not None and entry_price > _z_lastT:
                        _z_zone = "past_targets"
                    else:
                        _z_zone = "in_range"
            except Exception:
                pass
            _log_decision(ticker, "entry_zone", price=entry_price, zone=_z_zone,
                          break_level=(_z_brk or None), last_target=_z_lastT,
                          day_high=_z_dayhi, retest_depth_pct=_z_depth,
                          depth_band=(_retest_depth_band(_z_depth) if _z_depth is not None else None),
                          machine=entry_type)
            if (RETEST_BAND_GATE and _z_zone == "retest" and _z_depth is not None
                    and not (RETEST_BAND_LO <= _z_depth <= RETEST_BAND_HI)):
                _side = "shallow" if _z_depth < RETEST_BAND_LO else "deep"
                print(f"🎯 {ticker} retest at {_z_depth:.1f}% below the fired break ${_z_brk} is "
                      f"outside the {RETEST_BAND_LO:.0f}-{RETEST_BAND_HI:.0f}% band ({_side}) — "
                      f"skipping [retest band gate]")
                _log_decision(ticker, "retest_band_reject", price=entry_price,
                              stop=round(stop_loss, 4), break_level=_z_brk,
                              retest_depth_pct=_z_depth, depth_band=_retest_depth_band(_z_depth),
                              side=_side, machine=entry_type)
                _slot_refund(ticker, entry_type)
                with trade_lock:
                    reentry["held"].discard(ticker)
                return
            if (STANDDOWN_STICKY and entry_type in CHART_CEILING_LANES
                    and ticker in _standdown):
                _sd_ts = str((_z_rec or {}).get("_ts") or "")
                _sd_bound, _sd_at = _standdown[ticker]
                if (_sd_ts and _sd_ts != _sd_bound) or (not _sd_ts and time.time() - _sd_at > 1800):
                    _standdown.pop(ticker, None)   # fresh read arrived (or ts unknown 30 min) -> lifts
                    print(f"🟢 {ticker} stand-down LIFTED — {'fresh read' if _sd_ts else 'ts-unknown timeout'}")
                else:
                    print(f"🛑 {ticker} STAND-DOWN active (read unchanged since ceiling) — no chart-lane trade")
                    _log_decision(ticker, "standdown_active", price=entry_price,
                                  machine=entry_type, since_ts=str(_sd_bound)[-19:])
                    _slot_refund(ticker, entry_type)
                    with trade_lock:
                        reentry["held"].discard(ticker)
                    return
            if (CHART_CEILING_GATE and _z_zone == "past_targets"
                    and entry_type in CHART_CEILING_LANES
                    and not (_z_rec or {}).get("blue_sky")):
                # 8/13 #54: blue-sky maps' targets are ADVISORY (historical support, above all
                # known levels by definition) — being "past" them is the map's whole message,
                # never a ceiling. Cures today's manual-map side effect (INHD/LEXX class:
                # session-high targets became stand-down ceilings on continuations).
                print(f"🏔️ {ticker} entry ${entry_price:.2f} is ABOVE the map's last target "
                      f"${_z_lastT} — the road is spent until a fresh read; skipping [chart ceiling gate]")
                _log_decision(ticker, "ceiling_reject", price=entry_price,
                              stop=round(stop_loss, 4), last_target=_z_lastT,
                              break_level=_z_brk, machine=entry_type)
                if STANDDOWN_STICKY and str((_z_rec or {}).get("_ts") or ""):
                    _standdown[ticker] = (str(_z_rec["_ts"]), time.time())   # 8/8 #28: binds
                    # auditor #6: never bind on a ts-less map (unliftable forever-hold)
                _slot_refund(ticker, entry_type)
                with trade_lock:
                    reentry["held"].discard(ticker)
                return
            if (TAPE_PREBREAK_GATE and _z_zone == "pre_break"
                    and entry_type in TAPE_PREBREAK_LANES):
                print(f"🧭 {ticker} entry ${entry_price:.2f} is BELOW the unbroken break ${_z_brk} "
                      f"(day high {_z_dayhi}) — front-running a level that hasn't fired, "
                      f"skipping [tape pre-break gate]")
                _log_decision(ticker, "prebreak_reject", price=entry_price,
                              stop=round(stop_loss, 4), break_level=_z_brk,
                              day_high=_z_dayhi, machine=entry_type)
                _slot_refund(ticker, entry_type)
                with trade_lock:
                    reentry["held"].discard(ticker)
                return
            # ── 8/13 STOP-COHERENCE FLOOR (see STOP_COHERENCE_MIN_PCT def) — execution-moment
            # check: fire-time stop + drifted entry can leave the entry ON TOP of the stop
            # (BQ 8/12: entry $1.351, stop $1.349). A trade entered at its own stop has no
            # thesis left. All lanes; refuse + refund; Friday re-grades the rows.
            if STOP_COHERENCE_MIN_PCT > 0 and entry_price > 0 and stop_loss > 0:
                _coh_w = (entry_price - stop_loss) / entry_price
                if _coh_w < STOP_COHERENCE_MIN_PCT:
                    print(f"🚧 {ticker} STOP-COHERENCE refuse: entry ${entry_price:.4f} is "
                          f"{_coh_w*100:.3f}% above stop ${stop_loss:.4f} (< "
                          f"{STOP_COHERENCE_MIN_PCT*100:.1f}%) — trade thesis gone [{entry_type}]")
                    _log_decision(ticker, "stop_coherence_refused", price=round(float(entry_price), 4),
                                  stop=round(float(stop_loss), 4), width_pct=round(_coh_w * 100, 3),
                                  machine=entry_type)
                    _slot_refund(ticker, entry_type)
                    with trade_lock:
                        reentry["held"].discard(ticker)
                    return
            # B: Kev short-003 sizing (LIVE 7/11) — shares = max-loss ÷ risk-per-share; notional-capped. Wide stop →
            # fewer shares, tight stop → more; every full stop-out costs the same RISK_PER_TRADE.
            _clamp = "none"   # CLAMP-CHAIN LOGGING (7/26, log-only — the 7/25 exec-expert rec, built at
                              # last): WHICH constraint decided the size, so Friday reads binders off the
                              # record instead of inferring them from planned_risk arithmetic.
            if RISK_BASED_SIZING and entry_price > stop_loss:
                _risk_i = _scaled_risk(entry_price, stop_loss)     # 7/29 width-proportional
                if _risk_i < RISK_PER_TRADE - 0.005:
                    _w_pct = (entry_price - stop_loss) / entry_price * 100.0
                    print(f"   ⚖️ {ticker} width-prop risk: stop {_w_pct:.2f}% < "
                          f"{RISK_PROP_REF*100:.0f}% → risking ${_risk_i:.2f} (not ${RISK_PER_TRADE:.0f})")
                    _log_decision(ticker, "risk_scaled", price=entry_price, stop=round(stop_loss, 4),
                                  width_pct=round(_w_pct, 2), risk=round(_risk_i, 2))
                _sh_risk = int(_risk_i / (entry_price - stop_loss))
                _sh_notional = int(pos_size / entry_price)
                shares = max(1, min(_sh_risk, _sh_notional))
                _clamp = ("min_1_share" if min(_sh_risk, _sh_notional) < 1
                          else ("risk" if _sh_risk <= _sh_notional else "notional"))
            else:
                shares = max(1, int(pos_size / entry_price))
                _clamp = "notional"

            # ── 8/8 VWAP-SIDE SIZING (Marcos: "Go with B", CROWN-EXEMPT per the Steward split —
            # kill-test vwap_sizing_20260808: half-above B +$912 vs actual +$393, inverse control
            # −$323; crown split: above/CROWN −$90 (flat) vs above/field −$948 (THE bleed). FIELD
            # entries above session VWAP take HALF size; crowns keep every bullet. Fail-open to
            # full size when VWAP unknown. Kill: VWAP_SIDE_SIZING=1.0. 2-wk evidence, graded live
            # by the SIDE stamp + gate rows.) ──
            _vss = float(os.environ.get("VWAP_SIDE_SIZING", "0.5"))
            if _vss < 1.0 and vwap and vwap > 0 and entry_price >= vwap and not _is_leader(ticker):
                _sh_old = shares
                shares = max(1, int(shares * _vss))
                _clamp = _clamp + "+vwap_side"
                print(f"   ⚖️ {ticker} above session VWAP (${vwap:.2f}) non-crown — field size "
                      f"x{_vss:g}: {_sh_old} -> {shares} sh")
                _log_decision(ticker, "vwap_side_sized", price=entry_price, vwap=round(vwap, 4),
                              factor=_vss, shares_from=_sh_old, shares_to=shares)

            # ── VOLUME GUARD (7/11, the KUST lesson): size must fit the tape. Cap shares at MAX_POS_VOL_PCT of the
            # avg recent 1-min volume — the risk formula on a tight-stop illiquid name demands size the market
            # can't fill without becoming the market. ──
            _vol_cap = None
            if MAX_POS_VOL_PCT:
                try:
                    _vgb = _fresh_session(get_intraday_bars(ticker, count=6, sessions=_live_sessions()))   # B16
                    _vcomp = _vgb[:-1] if len(_vgb) >= 2 else _vgb
                    _vav = (sum(float(b.get("volume") or b.get("v") or 0) for b in _vcomp[-3:]) / min(3, len(_vcomp))) if _vcomp else 0
                    if _vav > 0:
                        _vol_cap = max(1, int(_vav * MAX_POS_VOL_PCT))
                        if shares > _vol_cap:
                            print(f"   💧 {ticker} volume guard: {shares} → {_vol_cap} shares "
                                  f"({MAX_POS_VOL_PCT*100:.0f}% of {int(_vav):,}/min avg tape)")
                            shares = _vol_cap
                            _clamp = "volume"          # tape, not risk, decided this size
                except Exception:
                    _clamp = _clamp + "+volguard_failopen"   # F4 witness: the guard was BLIND here
                    pass   # guard is best-effort; never blocks an entry on a data hiccup

            # ── DOLLAR-TRACKED CAPITAL (7/11): reserve the ACTUAL notional against the sim account (margin
            # semantics — released on exit). Replaces the old flat-$100 reservation. When free capital can't
            # fund the position, SKIP and LOG it — the no_capital_skip stream calibrates whether capital
            # collisions are a real tax (the 3-slot replay showed FCFS would have skipped SUNE on 7/10). ──
            _reserved = round(shares * entry_price, 2)
            with trade_lock:
                if settled_remaining < _reserved:
                    print(f"⛔ {ticker}: needs ${_reserved:.2f}, only ${settled_remaining:.2f} free — capital skip")
                    _log_decision(ticker, "no_capital_skip", price=entry_price,
                                  needed=_reserved, free=round(settled_remaining, 2), entry_type=entry_type)
                    _slot_refund(ticker, entry_type)   # 8/7 (#34 invariant catch): slot was leaking here
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                    return
                settled_remaining -= _reserved
                _reservations[ticker] = _reserved   # registry: pop() releases exactly once (leak-proof, 7/11)

            if entry_price > current_balance:
                print(f"⚠️ {ticker} @ ${entry_price:.2f} exceeds balance — skipping")
                _log_decision(ticker, "balance_skip", price=entry_price)   # 8/7 auditor #3: was silent
                _slot_refund(ticker, entry_type)                           # 8/7 auditor #3: slot leaked
                with trade_lock:
                    settled_remaining += _reservations.pop(ticker, 0)   # exactly-once release
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return

            tag = {"ema_bounce": "EMA BOUNCE", "ma_pullback": "MA PULLBACK", "orb": "OPENING RANGE", "ignition": "IGNITION"}.get(entry_type, "FLAT TOP")
            print(f"\n{'='*60}")
            print(f"🎯 ENTERING [{tag}]: {ticker}  entry=${entry_price:.2f}  "
                  f"target=${target_price:.2f}  stop=${stop_loss:.2f}  shares={shares}")
            print(f"{'='*60}\n")

            spread_ok, spread_pct = check_bid_ask_spread(ticker)
            if not spread_ok:
                print(f"⚠️ {ticker} spread {spread_pct*100:.2f}% too wide — skipping")
                _log_decision(ticker, "spread_reject", price=entry_price, spread_pct=round(spread_pct*100, 2))
                _slot_refund(ticker, entry_type)
                with trade_lock:
                    settled_remaining += _reservations.pop(ticker, 0)   # exactly-once release
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return

            l2_ok, l2_details = check_level2(ticker, entry_price)
            if not l2_ok:
                print(f"⚠️ {ticker} L2 rejected: {l2_details.get('reason','')} — skipping")
                _log_decision(ticker, "l2_reject", price=entry_price, reason=str(l2_details.get('reason', ''))[:80])
                _slot_refund(ticker, entry_type)   # 8/7 auditor #3: slot leaked here too
                with trade_lock:
                    settled_remaining += _reservations.pop(ticker, 0)   # exactly-once release
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return

            # Reversal setups (VWAP reclaim / bounce) reclaim from BELOW → low peak-relative volume by nature;
            # they carry their OWN volume confirmation in the detector, so they bypass the front-side momentum gate.
            # ORB added 7/26 (Marcos: "momentum gate was an added feature but MISTAKENLY added to ORB") — its
            # confirmed-retest trigger IS its confirmation, and the gate had strangled the lane to 0 fills ever
            # (33 era triggers; the 14 measurable momentum-rejected ones = 2.76R medMFE / 43% stopped, the best
            # cohort of the 7/26 forensics). Universal gates (topping tail + liquidity) still apply below.
            # flat_top + ma_pullback added same day (Marcos: "exempt all of the slow entries from momentum")
            # — same inversion on the same metric: rejected 0.81R/1.06R medMFE beats filled 0.56R/0.65R.
            # Third chase-tuned gate found inverted on retest entries (room 7/2, day-gain 7/26, momentum 7/26).
            # zone_flip added 7/26 (Marcos: "No point keeping it for one and not the others") — its Z1 arm
            # already requires flush vol >=2x rolling avg + Z2 bottoming wick + Z3 curl-over-wick; and the
            # peak-relative gate is anti-matched post-flush (the flush IS the session peak, so every valid
            # curl reads "5% of peak"). Front-side momentum gate now guards only a resurrected rocket_catcher.
            if entry_type in ("vwap_reclaim", "bounce", "ignition", "hidden_entry", "orb",
                              "flat_top", "ma_pullback", "zone_flip"):
                mom_ok, mom_details = True, {"exempt": entry_type}
                # ── UNIVERSAL GATES (7/10 un-bundle): topping-tail + liquidity are NOT momentum rules — they were
                # only skipped here because they live inside check_momentum (a bundling accident; KUST/ZCMD). When
                # flagged on, exempt types get the SAME universal checks the other entries get via check_momentum. ──
                if ENTRY_GATE_TOPPING_TAIL or ENTRY_GATE_LIQUIDITY:
                    _gb = _fresh_session(get_intraday_bars(ticker, count=30, sessions=_live_sessions()))   # B16
                    if ENTRY_GATE_TOPPING_TAIL and len(_gb) >= 2 and is_topping_tail(_gb[-2]):
                        mom_ok, mom_details = False, {"reason": "topping tail on last bar (universal gate) — rejection at the high, skip"}
                    elif (ENTRY_GATE_LIQUIDITY and entry_type != "ignition" and len(_gb) >= 3
                          and datetime.now(EASTERN).strftime("%H:%M") >= "09:30"):
                        # (ignition carve-out 7/26: the 3-bar window IS its quiet base — see flag note)
                        # (premarket carve-out 7/26: pre-9:30 tape is thin per-minute BY NATURE even on
                        #  names the regime approved — PRE_MIN_DVOL ($250k cumulative) owns premarket
                        #  liquidity; this 10k/bar floor is RTH-calibrated and applies RTH only.)
                        _g3 = _gb[-4:-1]
                        _gav = sum(float(b.get("volume") or b.get("v") or 0) for b in _g3) / max(len(_g3), 1)
                        if _gav < MOMENTUM_MIN_AVG_VOL:
                            # 8/6 supersession — see check_momentum twin: dollar floor outranks shares
                            _sf_ok, _sf_med, _sf_need = _ambient_dvol_ok(_gb)
                            if _sf_ok and _sf_med >= _sf_need > 0:
                                print(f"💵 {ticker} share floor waived — ambient ${int(_sf_med):,}/min (universal gate)")
                            else:
                                mom_ok, mom_details = False, {"reason": f"illiquid — avg vol {int(_gav):,}/bar < {MOMENTUM_MIN_AVG_VOL:,} floor (universal gate)"}
                    # 8/6 AMBIENT floor — ALL tape lanes INCLUDING ignition (the quiet-base carve-out
                    # above is why FVN/SUGP converted on 810/2.4k-share tape: it confused quiet with
                    # illiquid; the MEDIAN of 10 is spike-proof so a liquid quiet base still passes).
                    if mom_ok and ENTRY_GATE_LIQUIDITY and len(_gb) >= 6 \
                            and datetime.now(EASTERN).strftime("%H:%M") >= "09:30":
                        _am_ok, _am_med, _am_need = _ambient_dvol_ok(_gb)
                        if not _am_ok:
                            mom_ok, mom_details = False, {"reason": (
                                f"thin ambient tape — median ${int(_am_med):,}/min over prior 10 bars "
                                f"< ${int(_am_need):,} exit floor (universal gate)")}
            else:
                mom_ok, mom_details = check_momentum(ticker)
            if not mom_ok:
                print(f"⚠️ {ticker} momentum rejected: {mom_details.get('reason','')} — skipping")
                _log_decision(ticker, "momentum_reject", price=entry_price, reason=str(mom_details.get('reason', ''))[:80])
                _slot_refund(ticker, entry_type)   # 8/7 (#34): was the ONLY worker reject path
                # without a refund — survived the 7/29 "every refusal refunds" sweep; the 8/6
                # ambient floor routed new traffic through it (leader-ammo drain risk, flagged 8/7 AM).
                with trade_lock:
                    settled_remaining += _reservations.pop(ticker, 0)   # exactly-once release
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return

            # ── 8/6 RETEST ENTRY: wait for the pullback instead of buying the print ──
            if RETEST_ENTRY and entry_type in RETEST_LANES:
                _rt_lvl = round(entry_price * (1 - RETEST_DEPTH_PCT / 100.0), 4)
                _log_decision(ticker, "retest_wait", price=entry_price, retest_level=_rt_lvl,
                              machine=entry_type, expiry_s=RETEST_EXPIRY_S)
                print(f"⏳ {ticker} retest-entry armed: fire ${entry_price:.4f} -> waiting for "
                      f"${_rt_lvl:.4f} (-{RETEST_DEPTH_PCT:g}%, {RETEST_EXPIRY_S}s window)")
                _rt_t0 = time.time(); _rt_hit = False
                while time.time() - _rt_t0 < RETEST_EXPIRY_S:
                    if _entries_paused():
                        break                                    # deploy freeze also cancels waits
                    try:
                        _rd10, _ = _curl_feed(ticker, n=2)
                        if _rd10:
                            _rl = float((_rd10[max(_rd10)] or {}).get("l") or 0)
                            if 0 < _rl <= _rt_lvl:
                                _rt_hit = True
                                break
                    except Exception:
                        pass
                    time.sleep(5)
                if not _rt_hit:
                    print(f"⌛ {ticker} retest never came (or freeze) — no trade [retest expiry]")
                    _log_decision(ticker, "retest_expired", price=entry_price, retest_level=_rt_lvl,
                                  machine=entry_type)
                    _slot_refund(ticker, entry_type)
                    with trade_lock:
                        settled_remaining += _reservations.pop(ticker, 0)
                        reentry["held"].discard(ticker)
                    return
                entry_price = _rt_lvl                            # enter AT the retest level
                _log_decision(ticker, "retest_fill", price=entry_price, machine=entry_type,
                              waited_s=round(time.time() - _rt_t0, 1))
                print(f"🎯 {ticker} retest touched — entering at ${entry_price:.4f}")

            if (extra or {}).get("_pre_convert"):
                # 8/7 (#34): PRE ticket charged HERE, under lock, with a race re-check — two
                # near-simultaneous PRE fires must not overshoot the cap (pre-written failure
                # clause; rig proves the race). Cap full at execution -> full-refund reject.
                with trade_lock:
                    _pt_day = datetime.now(EASTERN).strftime("%Y-%m-%d")
                    if _pre_day.get("d") != _pt_day:
                        _pre_day["d"] = _pt_day; _pre_day["n"] = 0
                    if _is_leader(ticker):
                        _pre_ok = True        # 8/12 crown exemption: passes cap, consumes NO slot
                    elif _pre_day["n"] >= PRE_MAX_TRADES:
                        _pre_ok = False
                    else:
                        _pre_day["n"] += 1; _pre_ok = True
                        extra["_pre_slot_charged"] = True   # auditor blocker (10th): only a trade
                        # that CHARGED a slot may refund one — a failed CROWN order must not
                        # decrement a slot some non-crown trade paid for
                if not _pre_ok:
                    print(f"🎫 {ticker} PRE cap reached at execution (race) — refunding, no trade")
                    _log_decision(ticker, "pre_capped_at_exec", price=entry_price)
                    _slot_refund(ticker, entry_type)
                    with trade_lock:
                        settled_remaining += _reservations.pop(ticker, 0)
                        reentry["held"].discard(ticker)
                    return
            _grant_perimeter()   # 8/8: end of the gate chain — the ONE place orders are blessed.
            # (auditor #7: sits AFTER the last reject so the invariant never depends on
            # threads-not-pooled; if workers ever move to an executor this stays airtight.)
            order_id, stop_order_id, actual_fill = execute_trade(
                ticker, shares, entry_price, stop_loss, target_price
            )
            if not order_id:
                print(f"⚠️ Order failed for {ticker}")
                _log_decision(ticker, "order_failed", price=entry_price)
                _slot_refund(ticker, entry_type)   # 8/7 (#34): failed order refunds the lane slot
                with trade_lock:
                    if (extra or {}).get("_pre_slot_charged") and _pre_day.get("n", 0) > 0:
                        _pre_day["n"] -= 1        # 8/7 (#34): and the PRE ticket — no fill, no
                        # charge. 8/12 auditor blocker: gated on _pre_slot_charged (crowns never
                        # charge, so they never refund — the non-crown ration stays honest)
                    settled_remaining += _reservations.pop(ticker, 0)   # exactly-once release
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return
            # 8/8 PERIMETER METER (observability before the wall — the YJ ma_pullback side-door):
            # every fill records which lane-gated checks covered THIS lane, so an ungated lane
            # is visible in the row the moment it trades, not in a post-mortem. The one-wall
            # refactor lands this weekend; this meter also verifies it after it ships.
            try:
                _peri = {"breakside": entry_type in BREAKSIDE_LANES,
                         "ceiling": entry_type in CHART_CEILING_LANES,
                         "prebreak": entry_type in TAPE_PREBREAK_LANES,
                         "retest_wait": entry_type in RETEST_LANES,
                         "minstop": entry_type not in MIN_STOP_EXEMPT if 'MIN_STOP_EXEMPT' in globals() else None,
                         "standdown": entry_type in CHART_CEILING_LANES}
                _uncov = [k for k, v in _peri.items() if v is False]
                _log_decision(ticker, "perimeter_stamp", machine=entry_type,
                              covered=[k for k, v in _peri.items() if v],
                              uncovered=_uncov, side=_side_state(ticker, entry_price))
                if len(_uncov) >= 4:
                    print(f"🚧 {ticker} PERIMETER WARNING: lane '{entry_type}' outside most gates ({_uncov})")
            except Exception:
                pass
            _log_decision(ticker, "filled", price=actual_fill or entry_price, entry_type=entry_type)

            if actual_fill and actual_fill != entry_price:
                entry_price = actual_fill
                if "ema_stop" in extra:
                    stop_loss = round(extra["ema_stop"], 4)
                else:
                    stop_loss = round((extra.get("zone_stop") or entry_price * (1 - STOP_LOSS_PCT)), 4)
                    target_price = round(entry_price * (1 + TARGET_PCT), 4)
                # F1 (7/11 verification audit): the position is OWNED at this point — a fill at/below the
                # structural stop can't be "skipped", but it must not proceed with a stop AT/ABOVE entry
                # (the bad-stop hazard resurfacing post-fill). Floor the stop below the fill, loudly.
                if stop_loss >= entry_price:
                    stop_loss = round(entry_price * (1 - STOP_LOSS_PCT), 4)
                    print(f"🚨 {ticker}: fill ${entry_price:.2f} at/below the structural stop — "
                          f"stop floored to ${stop_loss:.2f} ({STOP_LOSS_PCT*100:.0f}% below fill)")
                elif (STOP_COHERENCE_MIN_PCT > 0
                      and (entry_price - stop_loss) / entry_price < STOP_COHERENCE_MIN_PCT):
                    # 8/13 ~01:15 MARCOS RULING ("keep how we have it and just fix the coherence
                    # floor" + "no widening to 7%"): the earlier auditor-suggested widen-to-7%
                    # remedy is DEAD — it changed behavior beyond his approved 0.5% refuse rule
                    # (a widened stop can lose MORE dollars) and shipped without consultation.
                    # Post-fill the stop is NEVER touched; this row is observability only, so
                    # Friday's re-grade can still see every post-fill incoherence occurrence.
                    print(f"🚧 {ticker}: fill ${entry_price:.4f} only "
                          f"{(entry_price - stop_loss) / entry_price * 100:.3f}% above stop ${stop_loss:.4f} "
                          f"(< {STOP_COHERENCE_MIN_PCT*100:.1f}% coherence floor) — OBSERVED, not acted on "
                          f"(remedy = Marcos's Friday call)")
                    _log_decision(ticker, "stop_coherence_observed", price=round(float(entry_price), 4),
                                  stop=round(float(stop_loss), 4),
                                  width_pct=round((entry_price - stop_loss) / entry_price * 100, 3),
                                  machine=entry_type, enforced=False)
                # Re-size on the real fill with the SAME risk formula (7/11) — not the old notional formula.
                # 7/29: SAME includes width-proportional — without it a tight-stop trade would re-inflate here.
                if RISK_BASED_SIZING and entry_price > stop_loss:
                    shares = max(1, min(int(_scaled_risk(entry_price, stop_loss) / (entry_price - stop_loss)),
                                        int(pos_size / entry_price)))
                else:
                    shares = max(1, int(pos_size / entry_price))
                if _vol_cap:
                    shares = min(shares, _vol_cap)
                # ledger note: reservation stays at the pre-fill notional (fill deltas are pennies; released as reserved)

            trade_id = uuid.uuid4().hex   # 8/10: minted BEFORE any keyed state exists
            with trade_lock:   # guard the _open_trade write (the SIGTERM handler reads it from the main thread)
                _open_trade[trade_id] = {"active": True, "ticker": ticker, "trade_id": trade_id,
                                         "entry_price": entry_price, "shares": shares,
                                         "stop_loss": stop_loss, "target": target_price}
            _post_watching_to_screener([ticker], status="trading")
            send_entry_alert(ticker, shares, entry_price,
                             stop_loss, target_price, vwap, _reserved)
            # Persist the static context SYNCHRONOUSLY (confirmed) BEFORE monitoring, so a
            # crash anywhere after this still records a proper exit. trade_id = idempotency key.
            # 7/27: the trade store had NO entry timestamp on any of 149 era rows (`recorded_at` is the
            # EXIT time), which blocked every bar-replay query outside the 5-day decision-log window.
            # Stamped once here, at the fill, and carried through the durable state, the watchdog ctx,
            # and the exit record so all three paths agree.
            _entry_ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            _shadow_keep.add(ticker)   # B12: this trade's 10s anatomy persists tonight no matter its tick rank
            _save_open_trade_sync({
                "entry_crown": (extra or {}).get("entry_crown"),   # mini-audit 3b
                "ticker": ticker, "trade_id": trade_id, "entry_price": round(entry_price, 4),
                "target": round(target_price, 4), "stop": round(stop_loss, 4),
                "initial_shares": shares, "remaining_shares": shares, "tier_idx": 0,
                "partial_fills": [], "entry_type": entry_type, "confidence": confidence,
                "position_size": _reserved, "vwap": round(vwap, 4) if vwap else 0,
                "entry_date": datetime.now(EASTERN).strftime("%Y-%m-%d"),
                "entry_time": datetime.now(EASTERN).strftime("%I:%M %p"),
                "entry_ts_utc": _entry_ts_iso,
                "risk_per_share": round(entry_price - stop_loss, 4),
                "planned_risk": round(shares * (entry_price - stop_loss), 2),
            })
            # Register with the stale-trade watchdog (full ctx so it can record if the monitor freezes).
            _monitor_abort.discard(ticker)   # 7/11 audit A8: a stale abort flag from a never-thawed prior
                                             # monitor would insta-kill THIS trade's monitor on iteration 1
            _active_monitors[trade_id] = {"heartbeat": time.time(), "alerted": False, "ctx": {
                "entry_crown": (extra or {}).get("entry_crown"),   # mini-audit 3a
                "ticker": ticker, "trade_id": trade_id, "entry_price": round(entry_price, 4),
                "stop": round(stop_loss, 4), "initial_shares": shares, "remaining_shares": shares,
                "tier_idx": 0, "partial_fills": [], "entry_type": entry_type, "confidence": confidence,
                "position_size": _reserved, "entry_date": datetime.now(EASTERN).strftime("%Y-%m-%d"),
                "entry_ts_utc": _entry_ts_iso, "last_price": round(entry_price, 4)}}
            _note_positions(len(_active_monitors))   # track peak concurrent positions (capacity signal)

            _rw_rr, _rw_tgt = (extra or {}).get("_rw_gate") or _marked_runway(ticker, entry_price, stop_loss)   # 8/8 auditor E: gate-time value reused
            trade_result = monitor_trade(
                ticker, shares, entry_price, target_price, stop_loss,
                stream, stop_order_id, trade_id=trade_id, vwap=vwap,
                next_supply=((extra or {}).get("room") or {}).get("next_supply"),
                entry_type=entry_type,               # rocket_catcher → %-based scale-out ladder in monitor_trade
                entered_premkt=(True if (extra or {}).get("_pre_convert") else None),   # F1b: None → clock fallback
                runway=_rw_rr,
            )
            _active_monitors.pop(trade_id, None)   # monitor returned — deregister from watchdog

            # DRY_RUN: skip the real-balance fetch entirely — the sim frame tracks its own balance, and the
            # fetch's side-post was flip-flopping the dashboard between $3,000(sim) and the real cash figure.
            _bal = 0.0 if DRY_RUN else get_account_balance()   # blocking Webull HTTP — fetch BEFORE the lock so we
                                           # don't serialize every other worker on the network call (audit HIGH-3)
            with trade_lock:
                _open_trade.pop(trade_id, None)
                pnl         = trade_result.get("profit_loss", 0)
                pnl_pct     = trade_result.get("profit_loss_pct", 0)
                exit_reason = trade_result.get("exit_reason", "N/A")
                session_pnl    += pnl
                trade_count    += 1
                # DRY_RUN: current_balance tracks the SIM account (else the real $578 cash balance would
                # silently shrink the sizing frame after the first trade). Live keeps the broker's number.
                current_balance = (SIM_ACCOUNT_BALANCE + session_pnl) if DRY_RUN else _bal
                display_balance = balance + session_pnl
                # MARGIN-SIM capital release (7/11): the exited position's notional recycles same-day —
                # matching the post-PDT margin account we'll actually trade. Live cash-mode: pop WITHOUT
                # refunding (proceeds unsettled same-day) until go-live points at the margin account.
                _amt = _reservations.pop(ticker, 0)   # exactly-once
                if DRY_RUN:
                    settled_remaining += _amt
                # ── RE-ENTRY (#2): release the name for a fresh GATED re-entry UNLESS it gave a
                #    structural "done" signal. Topping tail = Kev's "that's when I'm done with it" →
                #    leave it alone. Consec losing (re)entries ≥ cap = HOMEGROWN death-by-cuts rail. ──
                reentry["held"].discard(ticker)
                _crowned_now = _is_leader(ticker)
                _reentry_giveup = (exit_reason in REENTRY_GIVEUP_REASONS) or \
                                  _reentry_rail_giveup(ticker, pnl, reentry, _crowned_now)
                if _reentry_giveup:
                    reentry["givenup"].add(ticker); reentry["eligible"].discard(ticker)
                else:
                    reentry["eligible"].add(ticker)

            # ── RE-ENTRY (#2) observability — make the decision VISIBLE in the decision log so we can
            #    grade death-by-cuts vs Kev-style continuation in DRY_RUN. ──
            _att = reentry["count"].get(ticker, 0); _cl = reentry["consec_loss"].get(ticker, 0)
            print(f"🔁 {ticker} re-entry: "
                  f"{'GIVEN UP — ' + exit_reason if _reentry_giveup else 'ELIGIBLE for a fresh gated re-entry'} "
                  f"| attempts={_att} consec_loss={_cl} "
                  f"consec_loss_usd=${reentry.get('consec_loss_usd', {}).get(ticker, 0.0):.2f}")
            _cl_usd = reentry.get("consec_loss_usd", {}).get(ticker, 0.0)
            _log_decision(ticker, "reentry_givenup" if _reentry_giveup else "reentry_eligible",
                          exit_reason=str(exit_reason), attempts=_att, consec_loss=_cl,
                          consec_loss_usd=round(_cl_usd, 2), crowned=bool(_is_leader(ticker)),
                          pnl=round(pnl, 2))

            # float is for the trade log only (cosmetic); source it from the in-scope extra dict.
            # The old code referenced an undefined `market_data`, which raised NameError AFTER the
            # exit was recorded but BEFORE post_to_dashboard / _clear_open_trade — breaking the
            # "every entered trade reaches a recorded exit" invariant. Never let a log field crash this.
            float_shares = (extra or {}).get("float_shares", "N/A")
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
            _kev_lv = None
            _runway_rr, _runway_tgt = (extra or {}).get("_rw_gate") or _marked_runway(ticker, entry_price, stop_loss)   # 8/8 auditor E
            try:
                _lvd = (_fetch_kev_levels() or {}).get(ticker) or {}
                _kev_lv = float(_lvd.get("break") or 0) or None
                # MARKED RUNWAY now lives in _marked_runway() (7/29) — computed at entry for the
                # live card AND here for the record, from identical inputs (history + doctrine,
                # incl. the bimodal 'above_all_levels' stamp, documented on the helper).
            except Exception:
                _kev_lv = None
            _rec_ok = post_trade_record_reliably({
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
                "position_size":   _reserved,   # ACTUAL notional (7/11) — not the cap
                "account_balance": current_balance,
                # ── REALISTIC-SIZING calibration fields (7/11) ──
                "stop_loss":       round(stop_loss, 4),                              # initial structural stop
                "risk_per_share":  round(entry_price - stop_loss, 4),
                "planned_risk":    round(shares * (entry_price - stop_loss), 2),     # ≈ RISK_PER_TRADE unless capped
                "stop_width_pct":  (round((entry_price - stop_loss) / entry_price * 100, 2)
                                    if entry_price > 0 else None),   # 7/27 minstop gate — kept-side column for the Friday grade
                # 7/30 D-gap fix: the two fields that define hidden entry quality now PERSIST on
                # the trade record (were decision-row-only, which blocked the A1 grade for a day).
                "ext_vwap":        (extra or {}).get("ext_vwap"),
                "anchor":          (extra or {}).get("anchor"),
                # 7/27 off-tape guard: set only when the exit print could not be verified against
                # the tape this monitor saw. exit_px_raw = what the stream claimed; `exit` = booked.
                "exit_px_unverified": trade_result.get("exit_px_unverified"),
                "exit_px_raw":        trade_result.get("exit_px_raw"),
                "est_slippage":    round(shares * float(l2_details.get("spread") or 0), 2),  # shares × L1 spread @ entry
                "entry_ema90":        round(entry_ema90, 4) if entry_ema90 > 0 else None,
                "entry_vs_ema90_pct": entry_vs_ema90_pct,
                "trade_id":           trade_id,
                "entry_ts_utc":       _entry_ts_iso,   # 7/27: fill time (UTC ISO) — recorded_at is the EXIT time
                "size_clamp":         _clamp,   # 7/26 log-only: which constraint bound the size (risk/notional/volume/min_1_share; +volguard_failopen = guard was blind)
                # L1 order-book at entry (study: do adverse book conditions predict losers?)
                "entry_l1_ratio":     l2_details.get("ratio"),
                "entry_ask_size":     l2_details.get("ask_size"),
                "entry_bid_size":     l2_details.get("bid_size"),
                "entry_l1_spread":    l2_details.get("spread"),
                # Room to next supply at entry (Kev's master filter — taken trades should be ≥2:1)
                "entry_vel5":         extra.get("entry_vel5"),   # trailing 5-min velocity at entry (LOG-ONLY candidate gate)
                "entry_session":      ("PRE" if ((extra or {}).get("_pre_convert")
                                                or datetime.now(EASTERN).strftime("%H:%M") < "09:30")
                                        else "RTH"),  # 7/25 premarket-paper; F1b 7/26: conversion stamp wins over the clock
                "day_gain_at_entry":  extra.get("day_gain"),     # DAY-GAIN FLOOR column (7/22): % vs prior close at entry
                "entry_crown":        extra.get("entry_crown"),  # 8/8: crown at entry (sticky-crown state, not re-derived)
                # 7/28 MARKED RUNWAY (sheet-level room, distinct from mechanical entry_room_rr below):
                # RR from fill to the sheet's first target above entry; 0.0 = entered above ALL marked
                # levels (EGG 7/28); None = no sheet levels for the name. LOG-ONLY, Friday grades.
                "marked_runway_rr":   _runway_rr,
                "marked_runway_tgt":  _runway_tgt,
                # 8/4 class-aware runway: what KIND of level stood overhead at entry (RUNG =
                # intermediate target/scale point; MAJOR = break/next_supply/whole-half-dollar
                # = real resistance) + the fine road band — the tale shows it, Friday grades it.
                "marked_runway_cls":  _runway_level_class(ticker, _runway_tgt),
                "marked_runway_band": _road_band(_runway_rr),
                # 8/5 back-side gate: where in the move's life the entry sat (Friday grades bands)
                "entry_dd_pct":       (extra or {}).get("entry_dd_pct"),
                "entry_high_stale_min": (extra or {}).get("entry_high_stale_min"),
                "entry_room_rr":      (extra.get("room") or {}).get("rr_to_supply"),
                "entry_room_pct":     (extra.get("room") or {}).get("room_pct"),
                "entry_next_supply":  (extra.get("room") or {}).get("next_supply"),
                "entry_supply_src":   (extra.get("room") or {}).get("supply_src"),
                # Front-side (9>20 on the 3-min) recorded at entry — OBSERVE whether back-side breakouts
                # underperform before gating (Kev #006). [revisit — feedback_widen_within_kev_realm]
                "entry_front_side":   extra.get("front_side"),
                "entry_ema9":         extra.get("ema9"),
                "entry_ema20":        extra.get("ema20"),
                # Story fields (7/13) — power the dashboard's plain-English trade story
                "partial_fills":      trade_result.get("partial_fills") or [],
                "highest":            trade_result.get("highest"),
                # Reclaim label split (7/13) — true from-below reclaim vs momentum continuation
                "reclaim_subtype":            extra.get("reclaim_subtype"),
                # 7/15: ALL entry types now record distance vs the session VWAP the bot acted on
                # (pre-registered below-VWAP gate study + ongoing chart-vs-bot VWAP verification:
                # Marcos can spot-check any trade's recorded VWAP against the Webull chart line).
                "entry_vs_session_vwap_pct":  (extra.get("entry_vs_session_vwap_pct")
                                               if extra.get("entry_vs_session_vwap_pct") is not None
                                               else (round((entry_price - vwap) / vwap * 100, 2)
                                                     if vwap and vwap > 0 else None)),
                "entry_session_vwap":         round(vwap, 4) if vwap and vwap > 0 else None,
                # Kev-level anchoring (7/13): distance from his stated break level (study: closest = best)
                "kev_level":                  _kev_lv,
                "entry_vs_kev_level_pct":     (round((entry_price - _kev_lv) / _kev_lv * 100, 2)
                                               if _kev_lv else None),
            })
            if exit_reason != "WATCHDOG_ABORT":   # watchdog already recorded it (trade_id dedups)
                send_summary_email(analysis, trade_result, display_balance,
                                   csv_log_line=csv_row, traded_ticker=ticker)
            if _rec_ok:
                _clear_open_trade(ticker, trade_id=trade_id)   # recorded exit reached — drop durable recovery state
            else:
                print(f"🚨 {ticker}: exit record unconfirmed — durable state KEPT (restart will re-post; trade_id dedups)")

            tag = {"ema_bounce": "EMA BOUNCE", "ma_pullback": "MA PULLBACK", "orb": "OPENING RANGE", "ignition": "IGNITION"}.get(entry_type, "FLAT TOP")
            print(f"\n{'='*60}")
            print(f"✅ COMPLETE [{tag}] — {ticker}  ${pnl:+.2f} ({pnl_pct:+.1f}%)  [{exit_reason}]")
            print(f"   Session P&L: ${session_pnl:+.2f}  |  Balance: ${current_balance:.2f}")
            print(f"{'='*60}\n")

        def _trade_worker_safe(*wargs):
            """Leak-proof wrapper (7/11 review BLOCKER): if a worker thread dies on an uncaught exception,
            repair the capital ledger (refund any un-released reservation in DRY_RUN), release the re-entry
            held-lock, and drop the phantom _open_trade entry — else one crash starves the $3k sim pool and
            locks the ticker out for the day. Normal completions already released; pop() makes this a no-op."""
            nonlocal settled_remaining
            _tkr = wargs[0]
            try:
                _trade_worker(*wargs)
            except Exception as e:
                import traceback
                print(f"💥 worker {_tkr} died: {e}\n{traceback.format_exc()}")
            finally:
                with trade_lock:
                    _amt = _reservations.pop(_tkr, 0)
                    if _amt:
                        if DRY_RUN:
                            settled_remaining += _amt
                            print(f"🧯 {_tkr}: repaired ${_amt:.2f} orphaned reservation (worker died mid-trade)")
                        else:
                            print(f"🧯 {_tkr}: ${_amt:.2f} reservation orphaned by worker death (live: NOT refunded)")
                    reentry["held"].discard(_tkr)
                    for _k_ot, _v_ot in list(_open_trade.items()):
                        if (_v_ot.get("ticker") or "").upper() == _tkr:
                            _open_trade.pop(_k_ot, None)

        # Launch each breakout as a BACKGROUND daemon and KEEP GOING — do NOT join here.
        # This kills the blindspot: the scan loop keeps watching the rest of the market (and lets
        # multiple positions run at once) while each trade monitors itself in its own thread.
        for entry in breakouts:
            th = threading.Thread(target=_trade_worker_safe, args=entry, daemon=True)
            th.start()
            open_threads.append(th)

    # ── Entry phase over (3:30 / budget / no candidates). Wait for ALL background trades to finish
    #    (each self-exits by the 3:45 force-flat) before wrapping up + archiving the day. ──
    _alive = sum(1 for th in open_threads if th.is_alive())
    if _alive:
        print(f"⏳ Entry phase over — waiting on {_alive} open trade(s) to close before wrap-up...")
    for th in open_threads:
        th.join(timeout=600)   # bounded — the watchdog self-terminates a wedged monitor; never hang wrap-up
        if th.is_alive():
            print("⚠️  A trade monitor did not finish within 600s — proceeding to wrap-up (watchdog owns it).")

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

    # Archive the day's watched-ticker bars to the data warehouse (after all trading; fail-safe).
    # Routed through the guarded once-only helper so it can't double-run with the atexit fallback.
    _do_archive_once()


# ── PREMARKET OPERATING MODE (7/23, Marcos: "shadow trade 4:00-9:30... in the least we warm up
# all the systems... like warming up the car"): the bot's day starts at WAKE_ET (default 03:55 —
# at the desk for the 4:00 premarket bell). Entries are HARD-GATED until ENTRY_OPEN_ET (09:30):
# every premarket would-be entry logs as premarket_shadow_entry (the scorecard for the
# expand-trading-hours decision) and one-shot ammunition is restored so RTH keeps its full bag.
# WAKE_ET=08:45 reverts to the old day in one env change.
WAKE_ET = os.environ.get("WAKE_ET", "03:55").strip()
try:
    WAKE_H, WAKE_M = (int(x) for x in WAKE_ET.split(":"))
except Exception:
    WAKE_H, WAKE_M = 3, 55
ENTRY_OPEN_ET = os.environ.get("ENTRY_OPEN_ET", "09:30").strip()
# 7/25 premarket-paper profile (Marcos: premarket != RTH): only 10s live-structure lanes, tiny cap.
PRE_LANES = set((os.environ.get("PRE_LANES", "hidden_entry,vwap_reclaim")).split(","))
# 7/25 calibrated on Friday's 27 premarket fires: the 2 thinnest (NEUP $12k, LGCL $131k cum
# $vol) were the untradeable ones; every real candidate cleared $200k+. Floor does the quality
# gating -> cap loosened 2->4. Homegrown numbers (n=1 day) — registry, recalibrate weekly.
PRE_MAX_TRADES = int(os.environ.get("PRE_MAX_TRADES", "6"))   # Marcos 7/25: 6
PRE_MIN_DVOL = float(os.environ.get("PRE_MIN_DVOL", "250000"))   # cum session $ volume floor
PRE_FLAT_HHMM = os.environ.get("PRE_FLAT_HHMM", "09:25")             # Marcos 7/25: flatten PRE trades before the open
_pre_day = {"d": None, "n": 0}


def run_window_ok(now_et):
    """Gate 2 (main): may the session run right now? Keyed to WAKE_ET (was a hardcoded 8:30
    floor — the gate that killed premarket day 1). Pure function: testable with synthetic times."""
    minutes_et = now_et.hour * 60 + now_et.minute
    cutoff_min = VWAP_ENTRY_TIMEOUT * 60 + VWAP_ENTRY_TIMEOUT_MIN
    return (WAKE_H * 60 + WAKE_M) <= minutes_et <= cutoff_min


def detect_gate(now_et):
    """Gate 3 (watch loop): 'idle' before the 4:00 premarket bell (nothing prints), 'detect'
    from 4:00 until the 3:30 cutoff (detection + shadow logging; the ENTRY_OPEN_ET choke gate
    separately blocks trades before 9:30), 'closed' after. Was a hardcoded sleep-to-9:30.
    Pure function: testable with synthetic times."""
    m = now_et.hour * 60 + now_et.minute
    if m < 4 * 60:
        return "idle"
    if m >= VWAP_ENTRY_TIMEOUT * 60 + VWAP_ENTRY_TIMEOUT_MIN:
        return "closed"
    return "detect"


def next_trading_open(now_et):
    """Return the next WAKE_ET weekday datetime from now (premarket operating mode)."""
    candidate = now_et.replace(hour=WAKE_H, minute=WAKE_M, second=0, microsecond=0)
    if now_et >= candidate:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def in_trading_window(now_et):
    """True if we should be scanning/trading right now."""
    if now_et.weekday() >= 5:
        return False
    past_open  = (now_et.hour, now_et.minute) >= (WAKE_H, WAKE_M)
    past_close = now_et.hour > VWAP_ENTRY_TIMEOUT or (
        now_et.hour == VWAP_ENTRY_TIMEOUT and now_et.minute >= VWAP_ENTRY_TIMEOUT_MIN
    )
    return past_open and not past_close


if __name__ == "__main__":
    RESCAN_INTERVAL_MINUTES = 30

    try:
        sys.stdout.reconfigure(line_buffering=True)   # 7/16: Railway logs in real time (was block-buffered)
    except Exception:
        pass
    print("🤖 Marcos Trading Bot — always-on worker mode")
    # #97: one boot line states every data-source switch — the deploy acceptance reads THIS,
    # never assumes an env stuck. (stops/monitor price path: webull by design — Fable A2)
    print(f"🔀 DATA SOURCES: curl={CURL_SOURCE} bars={BARS_SOURCE} daily={DAILY_SOURCE} "
          f"vwap={DATA_PRIMARY} capture_hot={'SET' if ALP_CAPTURE_URL else 'unset(dash-fallback)'} "
          f"alp_keys={'yes' if (_ALP_KEY and _ALP_SECRET) else 'NO'}")

    # 7/15: SIGTERM → bulk-flush the in-memory 10s collection before Railway swaps the container.
    # Deploys must never be data events. (Main thread only — signal module requirement.)
    try:
        _prev_sigterm = signal.signal(signal.SIGTERM, _on_sigterm)
        print("🛟 SIGTERM flush handler armed (10s collection survives redeploys)")
    except Exception as e:
        print(f"⚠️  SIGTERM handler not armed: {e}")

    # SAFETY NET: recover + record any trade a crashed prior run left open (the invariant —
    # every entered trade reaches a recorded exit, regardless of what killed the process).
    try:
        _recover_orphaned_trades()
    except Exception as e:
        print(f"⚠️  Orphan recovery failed: {e}")
    finally:
        _RECOVERY_DONE_TS[0] = time.time()
        _recovery_done.set()   # 8/10: entries were racing recovery at boot (XHLD 140-sh dupe)

    # Stale-trade watchdog — catches a monitor that freezes while the process stays alive.
    threading.Thread(target=_monitor_watchdog_loop, daemon=True, name="watchdog").start()
    print("🛟 Stale-trade watchdog thread started")

    # 8/4 (#29): PRE-OPEN HEALTH CHECK — bot-side, replaces the laptop scheduled task that
    # silently died 7/27 (the 9:05 sheet-freshness check is load-bearing: an empty Kev sheet
    # means the day trades mapless). One durable decision row + a LOUD print at ~09:05 ET.
    def _preopen_health_loop():
        done_day = None
        while True:
            try:
                now = datetime.now(EASTERN)
                if now.strftime("%H:%M") >= "09:05" and now.strftime("%H:%M") < "09:25"                         and done_day != now.strftime("%Y-%m-%d") and now.weekday() < 5:
                    done_day = now.strftime("%Y-%m-%d")
                    lv = _fetch_kev_levels() or {}
                    kev_n = sum(1 for v in lv.values() if isinstance(v, dict) and v.get("src") == "kev")
                    vis_n = sum(1 for v in lv.values() if isinstance(v, dict) and v.get("src") == "vision")
                    ok = kev_n >= 1 and vis_n >= 3
                    _log_decision("_HEALTH", "preopen_health", kev_levels=kev_n, vision_levels=vis_n,
                                  total_levels=len(lv), sheet_ok=ok)
                    if ok:
                        print(f"🩺 preopen health: sheet OK — {kev_n} kev + {vis_n} vision maps")
                    else:
                        print(f"🚨🚨 PREOPEN HEALTH: SHEET LOOKS STALE — kev={kev_n} vision={vis_n} "
                              f"(expected >=1 kev, >=3 vision). Trading proceeds FAIL-OPEN but "
                              f"today may be running MAPLESS — check the sweep + reader NOW.")
            except Exception as _ph_e:
                print(f"preopen health check error: {_ph_e}")
            time.sleep(60)
    threading.Thread(target=_preopen_health_loop, daemon=True, name="preopen_health").start()
    print("🩺 Pre-open health thread started (09:05 ET sheet-freshness row)")

    # Day-2 observation runs on its own isolated daemon thread (never touches trading).
    threading.Thread(target=_day2_observer_loop, daemon=True, name="day2_observer").start()
    print("🔭 Day-2 observer thread started (observe-only)")
    threading.Thread(target=_winner_sweep_loop, daemon=True, name="winner_sweep").start()
    print("🏁 EOD winner-sweep thread started (market-wide winner capture, ~16:10 ET)")

    while True:
        now_et = datetime.now(EASTERN)

        if not in_trading_window(now_et):
            wake = next_trading_open(now_et)
            sleep_secs = (wake - now_et).total_seconds()
            print(f"💤 Outside trading hours — sleeping until {wake.strftime('%A %b %d')} at {WAKE_ET} ET ({sleep_secs/3600:.1f}h away)")
            time.sleep(sleep_secs)
            continue

        # In trading window — run a full scan/trade session
        main()

        now_et = datetime.now(EASTERN)
        if not in_trading_window(now_et):
            wake = next_trading_open(now_et)
            sleep_secs = (wake - now_et).total_seconds()
            print(f"⏰ Session complete — sleeping until {wake.strftime('%A %b %d')} at {WAKE_ET} ET ({sleep_secs/3600:.1f}h away)")
            time.sleep(sleep_secs)
        else:
            next_et_min = now_et.hour * 60 + now_et.minute + RESCAN_INTERVAL_MINUTES
            next_h, next_m = divmod(next_et_min, 60)
            print(f"\n🔄 Auto-rescan in {RESCAN_INTERVAL_MINUTES} min (~{next_h}:{next_m:02d} ET) — looking for new setups...")
            time.sleep(RESCAN_INTERVAL_MINUTES * 60)
