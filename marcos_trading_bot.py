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
SCALE_TIERS        = [(1, 0.50), (2, 0.75), (3.5, 0.90)]   # (R-multiple, cumulative fraction sold); None = old supply grid
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
        try:
            self.client.subscribe(new, "US_STOCK", ["SNAPSHOT"])
            with self._sub_lock:
                self.subscribed.update(new)
        except Exception as e:
            print(f"⚠️  Stream subscribe error {new}: {e}")

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
                    float_shares = float(info.get("floatShares") or info.get("sharesOutstanding") or 0)
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
            elif float_shares <= 20_000_000:   # Kev gospel: float < 20M (was 50M)
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
    return results


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

def _log_decision(ticker, status, **fields):
    # Wrapped so observability can NEVER throw into the trading hot path (this is called for every
    # candidate every cycle). A logging bug must not be able to stop the bot from trading.
    try:
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
        for sym in list(movers)[:80]:                    # bound the batch
            try:
                bars = get_intraday_bars(sym, count=960, executor=_aux_executor,
                                         sessions=["RTH", "PRE", "ATH"])   # full extended day incl pre/after-market
                if bars:
                    r = requests.post(f"{url}/api/bars", json={"date": date, "ticker": sym, "bars": bars},
                                      headers={"X-Dashboard-Secret": DASHBOARD_SECRET}, timeout=20)
                    if r.status_code == 200:
                        saved += 1
            except Exception:
                errs += 1
                if errs >= 5:                            # back off — never hammer the token
                    print("⚠️  winner_sweep: 5 fetch errors — backing off, stopping."); break
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
    while True:
        try:
            now = datetime.now(EASTERN)
            today = now.strftime("%Y-%m-%d")
            if now.weekday() < 5:
                if now.hour == 16 and now.minute >= 2 and last_rth != today:   # 16:02 (was :10) — RTH bars are final at 16:00; earlier sweep = earlier scorecard on days Marcos is watching
                    print("🏁 EOD winner sweep (RTH snapshot for the scorecard)...")
                    winner_sweep(); last_rth = today
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
    pnl = sum((float(p[1]) - entry) * float(p[0])
              for p in partials if isinstance(p, (list, tuple)) and len(p) >= 2)
    pnl += (px - entry) * remaining
    _cost = entry * initial
    pnl_pct = (pnl / _cost * 100) if _cost > 0 else 0   # blended (7/11 A6)
    print(f"🛟 WATCHDOG recording {ticker}: entry ${entry:.2f} → ${px:.2f} ({pnl_pct:+.1f}%, ${pnl:+.2f})")
    _rec_ok = post_trade_record_reliably({
        "date": ctx.get("entry_date") or datetime.now(EASTERN).strftime("%Y-%m-%d"),
        "ticker": ticker, "entry_type": ctx.get("entry_type", ""),
        "entry": entry, "exit": round(px, 4), "shares": initial,
        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
        "exit_reason": "RECOVERED — monitor froze (watchdog)",
        "confidence": ctx.get("confidence", ""), "float_shares": "",
        "position_size": ctx.get("position_size", 0),
        "account_balance": (SIM_ACCOUNT_BALANCE if DRY_RUN else get_account_balance()), "trade_id": ctx.get("trade_id"),   # F3
        "partial_fills": partials, "highest": ctx.get("highest"),
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
            for ticker, m in list(_active_monitors.items()):
                stale = now - m.get("heartbeat", now)
                if stale >= WATCHDOG_RECOVER_SECS:
                    print(f"🛟 WATCHDOG: {ticker} heartbeat stale {stale:.0f}s — force-recording + aborting")
                    _monitor_abort.add(ticker)
                    _active_monitors.pop(ticker, None)
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
                "ticker":          ticker, "entry_type": o.get("entry_type", ""),
                "entry":           entry, "exit": round(px, 4), "shares": initial,
                "pnl":             round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
                "exit_reason":     "RECOVERED after restart",
                "confidence":      o.get("confidence", ""), "float_shares": "",
                "position_size":   o.get("position_size", 0),
                "account_balance": (SIM_ACCOUNT_BALANCE if DRY_RUN else get_account_balance()),   # F3
                "trade_id":        o.get("trade_id"),
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
            _bump("timeouts")
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

        last   = float(d.get("close")     or d.get("last_price")   or d.get("lastPrice")   or d.get("c") or 0)
        bid    = float(d.get("bid_price")  or d.get("bidPrice")     or d.get("bid")         or 0)
        ask    = float(d.get("ask_price")  or d.get("askPrice")     or d.get("ask")         or 0)
        vol    = float(d.get("volume")     or d.get("v")            or 0)
        pclose = float(d.get("pre_close")  or d.get("preClose")     or last                 or 0)
        chg_r  = float(d.get("change_ratio")  or d.get("changeRatio")   or 0)
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
            "pre_market_change_pct": round(pre_r, 2),
            "vwap":                  vwap,
        }
    except Exception as e:
        print(f"⚠️  Webull quote error for {ticker}: {e}")
        _bump("api_err")
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
        full = get_intraday_bars(ticker, count=390)
        sess = _latest_session(full) if full else []
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
            details["reason"] = f"illiquid — avg vol {int(avg_vol):,}/bar < {MOMENTUM_MIN_AVG_VOL:,} floor, skip"
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
        dc = _get_data_client()
        if not dc:
            return None
        resp = None
        for _attempt in range(3):          # retry on 429 — daily is fetched for ~15 names; bursts rate-limit
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
        return {"m20": _sma(20), "m50": _sma(50), "m200": _sma(200),
                "reaction_highs": reaction,
                "prior_day_high": _pdh}
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


def detect_vwap_reclaim(completed, price, vwap):
    """Kev's VWAP RECLAIM: price LOST VWAP (traded below), then a candle CLOSES back above VWAP green on
    returning volume = buyers reclaimed the line → enter, risk below the reclaim low / VWAP. A distinct
    long trigger from the front-side pullback (this reclaims FROM BELOW) — carries its own volume
    confirmation, so it bypasses the front-side momentum gate. Any error → None."""
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
        sess = _latest_session(bars)
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
VWAP_SESSION_COUNT      = 800   # bars ≥ full pre-market(330) + RTH(390) + margin — 600 lost the pre-market anchor
                                # late-day on heavy-premarket names (7/11 audit A7); _latest_session() trims prior days
VWAP_SESSION_CACHE_SECS = 90    # session VWAP moves slowly — refresh less often than the 30s bar cache to limit API load
# Feature flags — DEFAULT OFF so the deployed default == current live/validated behavior. Flip only after re-validation.
HEALTH_VWAP_SESSION     = True  # exit health-fold: session VWAP (Webull-matching) — validated +19.2R/0-worse across 8 archived days (7/10)
ENTRY_VWAP_PREMARKET    = False # entry/dashboard VWAP: True → pre+RTH session VWAP instead of RTH-only

# ── 7/10 ENTRY-GATE + WIDE-STOP FIX STACK (all DEFAULT OFF until the 9-day completion grade ranks them) ──
# check_momentum BUNDLES three gates; the reversal exemption (vwap_reclaim/ignition/bounce) was meant only for the
# momentum gate but silently skipped the UNIVERSAL rules too (the 7/10 audit: flagged fills −$14.95 vs clean +$19.65).
ENTRY_GATE_TOPPING_TAIL = False  # un-bundled Kev rule: NO entry into a candle rejected at the high — ALL entry types
ENTRY_GATE_LIQUIDITY    = False  # un-bundled liquidity floor (MOMENTUM_MIN_AVG_VOL) — ALL entry types (⚠️ KUST won 7/10; grade first)
# Wide-stop fixes — THREE contenders, ranked head-to-head in the harness (the −7% was a MADE-UP number; do not inherit it):
STOP_MAX_PCT            = 0.0    # A: clamp the structural stop to entry×(1−X) for ALL types. 0=off; calibrate from data, don't assume 7%
MAX_STOP_DIST_PCT       = 0.0    # C: Kev tight-setup gate — SKIP entries whose structural stop is >X% away (wide base ≠ Kev setup). 0=off

# ── REALISTIC-SIZING DRY_RUN (7/11, user-directed): trade the INTENDED live amounts on paper so every number is
# real-scale. Kev short-003 sizing: max loss ≤1% of account; shares = max_loss ÷ risk-per-share; size down = smaller
# risk. Changes SIZE only — never WHICH trades fire (gates/exits untouched) → the learning stream continues unimpeded.
RISK_BASED_SIZING       = True   # shares = RISK_PER_TRADE ÷ (entry−stop), capped by notional + volume guards
RISK_PER_TRADE          = 30.0   # 1% of the intended $3,000 account — every trade risks exactly this
SIM_ACCOUNT_BALANCE     = 3000.0 # DRY_RUN virtual account (the intended go-live funding of the margin acct …9AGA)
MAX_POS_VOL_PCT         = 0.05   # share cap = 5% of the avg recent 1-min volume (KUST lesson: the formula wanted
                                 # 750 shares of a 3k-shares/min tape = unfillable; size must fit the market)

INTRADAY_RESCAN_INTERVAL = 3 * 60   # 7/3: 5→3 min — catch intraday runners sooner (they were seen too late)


def wait_for_flat_top_entry(candidates: list, stream: WebullStream,
                             rescan_callback=None, traded_tickers: set = None,
                             reentry: dict = None):
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
            _daily_ok.append(t)
            _log_decision(t, "daily_loaded")
        else:
            _daily_miss.append(t)
            _log_decision(t, "daily_missing")   # gate FAILS OPEN for this name — record it so we can SEE it
        time.sleep(0.5)   # de-burst the daily endpoint — gentle, pre-open, no rush
    print(f"📅 Daily levels pre-loaded: {len(_daily_ok)}/{len(candidates)} OK"
          + (f" | ⚠️  FAILED → daily gate fails OPEN for: {', '.join(_daily_miss)}"
             if _daily_miss else " (full daily-gate coverage)"))

    while True:
        now = datetime.now(EASTERN)

        # No time-of-day entry wall: a bot doesn't fatigue, so it trades the SETUP, not the clock.
        # (The old 11:00am cutoff was a human-discipline guard + a DRY_RUN/live parity gap — removed.
        # The setup itself is gated by room/spread/momentum; new entries still stop at the 3:30pm
        # boundary in main() ahead of the 3:45pm forced flat. Kev's setups trigger all day, e.g. the
        # 2pm base-breakouts on SDOT/IVF that this used to block live.)

        if now.hour < 9 or (now.hour == 9 and now.minute < 30):
            mins = (9 * 60 + 30) - (now.hour * 60 + now.minute)
            print(f"⏳ Market opens in ~{mins} min...")
            time.sleep(30)
            continue

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

        # Refresh bars for each ticker every 30s
        for t in candidates:
            if time.time() - cache[t]["fetched"] >= VWAP_BAR_CACHE_SECS:
                fresh = get_intraday_bars(t, count=max(EMA_BOUNCE_LOOKBACK + EMA20_PERIOD + 5, 50))
                if fresh:
                    cache[t]["bars"] = fresh
                full_bars = get_intraday_bars(t, count=390)
                if full_bars:
                    cache[t]["full_bars"] = full_bars   # RTH 1-min (count backfills prior days) — room + 3-min agg (UNCHANGED)
                    if not ENTRY_VWAP_PREMARKET:
                        # LIVE DEFAULT (validated): RTH session VWAP from full_bars.
                        calc_vwap = calculate_vwap(_latest_session(full_bars))   # SESSION VWAP — never across the day boundary
                        if calc_vwap > 0:
                            cache[t]["vwap"] = calc_vwap
                        else:
                            print(f"⚠️  {t} VWAP=0 — Webull bars had no volume data")
                    elif time.time() - cache[t].get("vwap_fetched", 0) >= VWAP_SESSION_CACHE_SECS:
                        # Chart-matching = session-anchored INCLUDING pre-market. Dedicated pre+RTH fetch (slower TTL to
                        # limit API load); keep full_bars RTH-only so room/3-min setups don't move.
                        _vwb  = get_intraday_bars(t, count=VWAP_SESSION_COUNT, sessions=["PRE", "RTH"])
                        _sess = _latest_session(_vwb) if _vwb else _latest_session(full_bars)
                        _fullvw = calculate_vwap(_sess)
                        _rthvw  = calculate_vwap([b for b in _sess if b.get("trading_session") == "RTH"]) or _fullvw
                        if _fullvw > 0:
                            cache[t]["vwap"]     = _fullvw   # pre+RTH session VWAP (chart-matching) — shown in status line
                            cache[t]["vwap_rth"] = _rthvw    # RTH-only (old) — dual-log to see the pre-market gap
                            cache[t]["vwap_fetched"] = time.time()
                            if _rthvw > 0 and abs(_fullvw - _rthvw) / _rthvw >= 0.03:
                                print(f"   🔍 {t} VWAP pre+RTH ${_fullvw:.3f} vs RTH-only ${_rthvw:.3f} "
                                      f"({(_fullvw - _rthvw) / _rthvw * 100:+.0f}% pre-market gap)")
                        else:
                            print(f"⚠️  {t} VWAP=0 — Webull bars had no volume data")
                else:
                    print(f"⚠️  {t} VWAP unavailable — no Webull bars returned")
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

            if not bars or price <= 0:
                status_parts.append(f"{t}:no data")
                continue

            # ── Entry type: IGNITION (7/4) — runs FIRST, BEFORE the 3-min-EMA warmup guard below, because it
            #    reads 1-MIN SESSION bars + the volume-acceleration surge and does NOT need the 3-min EMAs
            #    (not warm in the ignition window). The ONE entry NOT gated on above-VWAP (quiet base sits below
            #    VWAP). Surge breaking the quiet base = the trigger; tight stop at base low. Fires ONCE per ticker. ──
            if IGNITION_ENABLED and not cache[t].get("ignition_fired"):
                _sess1 = _latest_session(cache[t].get("full_bars") or bars)
                ign = detect_ignition(_sess1, price)
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
                        cache[t]["ignition_fired"] = True     # bad daily = no trade (Kev)
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
                        _log_decision(t, "triggered_ignition", price=price, room_rr=rr,
                                      volx=ign["volx"], base_hi=ign["base_hi"], ext_pct=ign["ext_pct"], front_side=_front)
                        cache[t]["ignition_fired"] = True
                        continue                              # ignition captured (in `breakouts`) — skip other detectors for t

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

            # ── Entry type 1: Flat top breakout ──────────────────────
            # The intraday BASE must be TODAY's 3-min bars — `completed` spans prior days (for the EMAs),
            # so slice to the current session or the first ~12 min of RTH would read a base across the
            # overnight gap (prior-day consolidation) and fire a spurious open-gap "breakout".
            _sess3 = _latest_session(completed)
            if len(_sess3) >= FLAT_TOP_WINDOW:
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
                            if price <= _pb["level"] * (1 + PULLBACK_TOL):
                                _pb["dipped"] = True                    # pulled back to the level
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
                            print(f"🚫 {t}: DAILY BAD — ${price:.2f} below daily 20/50 MA "
                                  f"({_daily.get('m20')}/{_daily.get('m50')}) — skip (Kev: bad daily = no trade)")
                            _log_decision(t, "broke_daily_bad", price=price)
                            continue
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
            if (not found_entry and vwap > 0 and price > vwap
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
                            if price <= _po["level"] * (1 + PULLBACK_TOL):
                                _po["dipped"] = True
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
                                _log_decision(t, "orb_daily_bad", price=price, room_rr=rr, orb_high=orb_hi)
                                cache[t]["orb_fired"] = True   # daily bad — don't chase later re-breaks
                                cache[t]["pb_orb"] = None
                            else:
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
                        print(f"🚫 {t} {ma_pb['ma_name']} pullback — DAILY BAD (below daily 20/50 MA) — skip")
                        _log_decision(t, "ma_daily_bad", price=price, room_rr=rr_room)
                    else:
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

            # ── Entry type 5: VWAP RECLAIM (Kev) — price lost VWAP then reclaimed it green on volume. A
            #    distinct long trigger (reclaim from below); managed on 3-min, risk below the reclaim/VWAP. ──
            if not found_entry and vwap > 0:
                vr = detect_vwap_reclaim(completed, price, vwap)
                if vr:
                    vr_stop = vr["stop"]
                    if "daily" not in cache[t]:
                        cache[t]["daily"] = get_daily_levels(t)
                    _daily = cache[t]["daily"]
                    room = compute_room(price, vr_stop, cache[t].get("full_bars") or bars,
                                        daily=_daily, prior_day_high=(_daily or {}).get("prior_day_high"))
                    _vfront = ema9 > ema20 > 0
                    print(f"\n🔵 {t} VWAP RECLAIM! ${price:.2f} back above VWAP ${vwap:.2f} — stop ${vr_stop:.2f}")
                    breakouts.append((t, price, vwap, "vwap_reclaim", {
                        "zone_stop": vr_stop, "room": room, "ema90": round(ema90, 4),
                        "front_side": _vfront, "ema9": round(ema9, 4), "ema20": round(ema20, 4),
                    }))
                    _log_decision(t, "triggered_vwap_reclaim", price=price, vwap=vwap)
                    found_entry = True

            if not found_entry and t not in [s.split(":")[0] for s in status_parts]:
                status_parts.append(f"{t}:${price:.2f} EMA9:${ema9:.2f}{vwap_tag}")
                _log_decision(t, "watching", price=price, vwap=vwap)

        # bounce = observe-only (dropped; its backtest read was clearly −0.40, needs reversal-regime data).
        # Others active per BREAKOUT_ENTRIES: True → full bag; False → pullback + VWAP-reclaim only.
        breakouts = [b for b in breakouts
                     if b[3] != "bounce" and (BREAKOUT_ENTRIES or b[3] in ("ma_pullback", "vwap_reclaim", "ignition"))]
        # EXTENSION GUARD — don't chase a name too far above its 90-EMA (7/3 data; Kev "don't chase extended").
        if EXTENSION_MAX_PCT and EXTENSION_MAX_PCT < 9:
            _kept = []
            for b in breakouts:
                _e90 = (b[4].get("ema90") or 0)
                if _e90 > 0 and (b[1] - _e90) / _e90 > EXTENSION_MAX_PCT:
                    _log_decision(b[0], "extension_reject", price=b[1], ext_pct=round((b[1] - _e90) / _e90 * 100, 1))
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
                        cache[t] = {"bars": [], "vwap": 0.0, "fetched": 0.0}
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

def _vride_defer(ticker, tier_idx):
    """VELOCITY-AWARE RIDE: True if the move is still accelerating hard → defer this scale (ride the vertical).
    Fail-CLOSED — any error or VELOCITY_RIDE off → False → normal scaling (exact baseline). Streaming makes
    this velocity read fast/clean live; it uses the same 1-min bars monitor_trade already fetches."""
    if not VELOCITY_RIDE:
        return False
    try:
        rb = get_intraday_bars(ticker, count=VELO_BARS + 2)
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

def monitor_trade(ticker, total_shares, entry_price, target_price, stop_loss,
                  stream: WebullStream, stop_order_id, vwap=0, next_supply=None):
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
    _status_px         = 0.0           # throttle the 💰 status print (streaming's 0.5s loop floods it otherwise)
    _status_t          = 0.0           # print only on a ≥0.3% move OR every ≥STATUS_PRINT_SECS — keeps real events visible

    initial_shares = total_shares
    tier_idx = 0
    # ── Kev's R-based exits (SUPPLY_EXIT_DESIGN.md): R = entry − initial stop. Sell HALF at +1R
    # (risk-free → stop to break-even), trim to a ~1/4 runner at the next supply (or +2R if open room),
    # then the 1/4 runner trails the PREVIOUS-BAR LOW. Replaces the made-up +8/12/20% tiers + TRAIL_PCT. ──
    R = max(entry_price - stop_loss, 0.01)
    if SCALE_TIERS:                                    # reimagined R-grid scale-out (7/5 exit study — beats supply grid)
        kev_tiers = [(round(entry_price + rm * R, 4), cum) for rm, cum in SCALE_TIERS]
    else:
        _scale2 = next_supply if (next_supply and next_supply > entry_price + R) else entry_price + 2 * R
        kev_tiers = [(round(entry_price + R, 4), 0.50),    # +1R  → sell 50%, stop to break-even (risk-free)
                     (round(_scale2, 4), 0.75)]             # supply/+2R → sell 25% (down to a 1/4 runner)
    print(f"   Kev exits: R=${R:.2f} | tiers " + " → ".join(f"{int(c*100)}%@${p:.2f}" for p, c in kev_tiers)
          + " → runner trails (health-trail)")
    last_ema_check     = 0.0           # epoch of last EMA9 bar fetch

    result = {"exit_price": entry_price, "exit_reason": "Unknown",
              "profit_loss": 0, "profit_loss_pct": 0}

    while True:
        now = datetime.now(EASTERN)

        # ── Watchdog took over (this monitor had stalled, then thawed) — bail without re-recording.
        if ticker in _monitor_abort:
            _monitor_abort.discard(ticker)
            print(f"🛟 {ticker}: watchdog already recorded this trade — monitor exiting")
            result["exit_reason"] = "WATCHDOG_ABORT"
            return result

        # WATCHDOG heartbeat — set UNCONDITIONALLY at the top of every iteration so it means
        # "this loop is alive", independent of feed/price/persist. (If placed lower it would be
        # skipped during a dead-feed `continue`, falsely looking frozen — audit catch.)
        _hb = _active_monitors.get(ticker)
        if _hb is not None:
            _hb["heartbeat"] = time.time()

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

        # ── Runner protection after the first partial: the intrabar hard stop stays at BREAK-EVEN
        # (set when the partial fired). Kev's "risk off the previous bar low" is a CLOSE-based
        # structure rule (a 1-min bar low is far too tight as an intrabar stop — it would snipe the
        # runner on every normal pullback / can sit above live price), so the prev-bar-low TRAIL is
        # enforced as a bar-close exit in the EMA section below, NOT through current_stop. (audit fix) ─

        # Throttled status print — only on a ≥0.3% move or every ≥6s (streaming's 0.5s loop otherwise floods the
        # logs with identical lines, risking Railway's rate cap + burying real events). Dashboard still gets every tick.
        if (_status_px <= 0 or abs(current_price - _status_px) / _status_px >= 0.003
                or time.time() - _status_t >= 6):
            print(f"💰 {ticker}: ${current_price:.2f} ({profit_pct:+.1f}%) | Stop: ${current_stop:.2f} | Shares: {remaining_shares}")
            _status_px = current_price; _status_t = time.time()
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
            # Static plan fields for the dashboard's tale-of-the-tape (constant per trade)
            "tiers": [[p, c] for p, c in kev_tiers], "risk_ps": round(R, 4),
        })
        # Refresh the watchdog's recordable context (heartbeat itself is set at the loop top).
        _m = _active_monitors.get(ticker)
        if _m is not None:
            _m["ctx"].update({"remaining_shares": remaining_shares, "partial_fills": partial_fills,
                              "tier_idx": tier_idx, "highest": round(highest_price, 4),
                              "stop": round(current_stop, 4), "last_price": round(current_price, 4)})

        # ── Kev R-based scale-outs: 50% @ +1R (→ risk-free), 25% @ supply/+2R (→ a 1/4 runner) ──
        if tier_idx < len(kev_tiers) and remaining_shares > 0:
            tier_price, tier_cumulative = kev_tiers[tier_idx]
            if current_price >= tier_price and not _vride_defer(ticker, tier_idx):
                if tier_cumulative >= 1.0:
                    sell_qty = remaining_shares
                else:
                    sold_so_far = initial_shares - remaining_shares
                    target_sold = int(initial_shares * tier_cumulative)
                    sell_qty = max(1, target_sold - sold_so_far)
                    sell_qty = min(sell_qty, remaining_shares)

                tier_label = f"Scale {tier_idx+1}/{len(kev_tiers)}"
                print(f"💰 {tier_label}: selling {sell_qty} of {remaining_shares} shares "
                      f"at ${current_price:.2f} (+{profit_pct:.1f}%) — {'+1R risk-free' if tier_idx == 0 else 'trim to runner'}")
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

                # After the first scale, the intrabar hard stop = BREAK-EVEN (risk-free). The prev-bar-low
                # trail then ratchets the runner up on a CLOSE basis (bar-close exit in the EMA section).
                current_stop     = entry_price
                placed_stop_id    = place_stop_order(ticker, remaining_shares, current_stop)
                placed_stop_price = current_stop
                placed_stop_qty   = remaining_shares
                print(f"📈 Floor at entry ${entry_price:.2f}, trail stop ${current_stop:.2f} "
                      f"— {remaining_shares} shares remaining")
                send_partial_exit_alert(ticker, sell_qty, partial_price, entry_price,
                                        remaining_shares, current_stop, profit_pct)

        # ── Structure-based exits: fetch recent bars for the Kev close-based exits below ──────
        if remaining_shares > 0 and time.time() - last_ema_check >= EMA_CHECK_INTERVAL:
            bars = get_intraday_bars(ticker, count=(EMA_PERIOD + 6) * SETUP_TF_MIN if EXITS_ON_3MIN else EMA_PERIOD + 5)
            _cbars = aggregate_bars(bars, SETUP_TF_MIN) if (EXITS_ON_3MIN and bars) else bars
            if _cbars and len(_cbars) >= (3 if EXITS_ON_3MIN else EMA_PERIOD + 2):
                completed = _cbars[:-1]   # 3-MIN completed bars = manage on Kev's chart (EXITS_ON_3MIN), else 1-min

                # ── 3-MIN close-based STOP: exit only when a completed 3-min bar CLOSES at/below the stop. A
                #    wick through it that closes back above is normal volatility, not a failure — this is what
                #    holds the winners. The intrabar −7% catastrophe cap (below) is the only sub-minute stop. ──
                if EXITS_ON_3MIN and remaining_shares > 0:
                    _c3 = float(completed[-1].get("close") or completed[-1].get("c") or 0)
                    if 0 < _c3 <= current_stop:
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
                            _svb = get_intraday_bars(ticker, count=VWAP_SESSION_COUNT, sessions=["PRE", "RTH"])
                            _vw  = calculate_vwap(_latest_session(_svb)) if _svb else _vw_roll
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

    # ── Blended P&L (sum across all tier fills + remaining) ──
    if partial_fills:
        pnl = sum((px - entry_price) * qty for qty, px in partial_fills)
        pnl += (result["exit_price"] - entry_price) * remaining_shares
        result["profit_loss"] = pnl
    else:
        result["profit_loss"] = (result["exit_price"] - entry_price) * total_shares

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

    _open_trade.pop(ticker, None)
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
    if DRY_RUN:
        # REALISTIC-SIZING SIM (7/11): size and ledger against the INTENDED go-live funding, not the real
        # cash-account balance — so paper P&L, risk, and capital collisions are all true-scale.
        print(f"💰 Real balance ${balance:.2f} → DRY_RUN sizing frame: ${SIM_ACCOUNT_BALANCE:.2f} sim account")
        balance = SIM_ACCOUNT_BALANCE
    else:
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
            with reentry["lock"]:                       # RE-ENTRY FIX (7/9): exclude only held+givenup, not all traded
                _reexcl = reentry["held"] | reentry["givenup"]
            remaining_candidates = [g["symbol"] for g in fresh_gappers
                                    if g.get("symbol") and g["symbol"] not in _reexcl]
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
            traded_tickers=traded_tickers,
            reentry=reentry,
        )

        if not breakouts:
            print(f"⏰ No entry detected ({', '.join(remaining_candidates)}). Cash preserved.")
            break

        # Mark all breakout tickers as traded before threads start
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
                with trade_lock:
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return
            # A: stop clamp — cap the structural stop at entry×(1−X). Number must come from the grade, not the old -7% guess.
            if STOP_MAX_PCT and _stop_dist > STOP_MAX_PCT:
                stop_loss = round(entry_price * (1 - STOP_MAX_PCT), 4)
                print(f"   🔧 {ticker} stop clamped {_stop_dist*100:.1f}% → {STOP_MAX_PCT*100:.0f}% (${stop_loss:.2f})")
            # Degenerate stop (stale EMA / bad tick puts the stop AT/ABOVE entry): unsizeable, skip + log —
            # never fall through to full-notional sizing with a meaningless stop (7/11 review finding 4).
            if RISK_BASED_SIZING and stop_loss >= entry_price:
                print(f"⚠️ {ticker} stop ${stop_loss:.2f} ≥ entry ${entry_price:.2f} — unsizeable, skipping")
                _log_decision(ticker, "bad_stop_skip", price=entry_price, stop=round(stop_loss, 4))
                with trade_lock:
                    reentry["held"].discard(ticker)   # pre-reservation: nothing to refund
                return
            # B: Kev short-003 sizing (LIVE 7/11) — shares = max-loss ÷ risk-per-share; notional-capped. Wide stop →
            # fewer shares, tight stop → more; every full stop-out costs the same RISK_PER_TRADE.
            if RISK_BASED_SIZING and entry_price > stop_loss:
                shares = max(1, min(int(RISK_PER_TRADE / (entry_price - stop_loss)), int(pos_size / entry_price)))
            else:
                shares = max(1, int(pos_size / entry_price))

            # ── VOLUME GUARD (7/11, the KUST lesson): size must fit the tape. Cap shares at MAX_POS_VOL_PCT of the
            # avg recent 1-min volume — the risk formula on a tight-stop illiquid name demands size the market
            # can't fill without becoming the market. ──
            _vol_cap = None
            if MAX_POS_VOL_PCT:
                try:
                    _vgb = _latest_session(get_intraday_bars(ticker, count=6))
                    _vcomp = _vgb[:-1] if len(_vgb) >= 2 else _vgb
                    _vav = (sum(float(b.get("volume") or b.get("v") or 0) for b in _vcomp[-3:]) / min(3, len(_vcomp))) if _vcomp else 0
                    if _vav > 0:
                        _vol_cap = max(1, int(_vav * MAX_POS_VOL_PCT))
                        if shares > _vol_cap:
                            print(f"   💧 {ticker} volume guard: {shares} → {_vol_cap} shares "
                                  f"({MAX_POS_VOL_PCT*100:.0f}% of {int(_vav):,}/min avg tape)")
                            shares = _vol_cap
                except Exception:
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
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                    return
                settled_remaining -= _reserved
                _reservations[ticker] = _reserved   # registry: pop() releases exactly once (leak-proof, 7/11)

            if entry_price > current_balance:
                print(f"⚠️ {ticker} @ ${entry_price:.2f} exceeds balance — skipping")
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
                with trade_lock:
                    settled_remaining += _reservations.pop(ticker, 0)   # exactly-once release
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return

            l2_ok, l2_details = check_level2(ticker, entry_price)
            if not l2_ok:
                print(f"⚠️ {ticker} L2 rejected: {l2_details.get('reason','')} — skipping")
                _log_decision(ticker, "l2_reject", price=entry_price, reason=str(l2_details.get('reason', ''))[:80])
                with trade_lock:
                    settled_remaining += _reservations.pop(ticker, 0)   # exactly-once release
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return

            # Reversal setups (VWAP reclaim / bounce) reclaim from BELOW → low peak-relative volume by nature;
            # they carry their OWN volume confirmation in the detector, so they bypass the front-side momentum gate.
            if entry_type in ("vwap_reclaim", "bounce", "ignition"):
                mom_ok, mom_details = True, {"exempt": entry_type}
                # ── UNIVERSAL GATES (7/10 un-bundle): topping-tail + liquidity are NOT momentum rules — they were
                # only skipped here because they live inside check_momentum (a bundling accident; KUST/ZCMD). When
                # flagged on, exempt types get the SAME universal checks the other entries get via check_momentum. ──
                if ENTRY_GATE_TOPPING_TAIL or ENTRY_GATE_LIQUIDITY:
                    _gb = _latest_session(get_intraday_bars(ticker, count=30))
                    if ENTRY_GATE_TOPPING_TAIL and len(_gb) >= 2 and is_topping_tail(_gb[-2]):
                        mom_ok, mom_details = False, {"reason": "topping tail on last bar (universal gate) — rejection at the high, skip"}
                    elif ENTRY_GATE_LIQUIDITY and len(_gb) >= 3:
                        _g3 = _gb[-4:-1]
                        _gav = sum(float(b.get("volume") or b.get("v") or 0) for b in _g3) / max(len(_g3), 1)
                        if _gav < MOMENTUM_MIN_AVG_VOL:
                            mom_ok, mom_details = False, {"reason": f"illiquid — avg vol {int(_gav):,}/bar < {MOMENTUM_MIN_AVG_VOL:,} floor (universal gate)"}
            else:
                mom_ok, mom_details = check_momentum(ticker)
            if not mom_ok:
                print(f"⚠️ {ticker} momentum rejected: {mom_details.get('reason','')} — skipping")
                _log_decision(ticker, "momentum_reject", price=entry_price, reason=str(mom_details.get('reason', ''))[:80])
                with trade_lock:
                    settled_remaining += _reservations.pop(ticker, 0)   # exactly-once release
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return

            order_id, stop_order_id, actual_fill = execute_trade(
                ticker, shares, entry_price, stop_loss, target_price
            )
            if not order_id:
                print(f"⚠️ Order failed for {ticker}")
                _log_decision(ticker, "order_failed", price=entry_price)
                with trade_lock:
                    settled_remaining += _reservations.pop(ticker, 0)   # exactly-once release
                    reentry["held"].discard(ticker)   # pre-trade reject (no fill): release held-lock (#2)
                return
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
                # Re-size on the real fill with the SAME risk formula (7/11) — not the old notional formula.
                if RISK_BASED_SIZING and entry_price > stop_loss:
                    shares = max(1, min(int(RISK_PER_TRADE / (entry_price - stop_loss)), int(pos_size / entry_price)))
                else:
                    shares = max(1, int(pos_size / entry_price))
                if _vol_cap:
                    shares = min(shares, _vol_cap)
                # ledger note: reservation stays at the pre-fill notional (fill deltas are pennies; released as reserved)

            with trade_lock:   # guard the _open_trade write (the SIGTERM handler reads it from the main thread)
                _open_trade[ticker] = {"active": True, "ticker": ticker,
                                       "entry_price": entry_price, "shares": shares,
                                       "stop_loss": stop_loss, "target": target_price}
            _post_watching_to_screener([ticker], status="trading")
            send_entry_alert(ticker, shares, entry_price,
                             stop_loss, target_price, vwap, _reserved)
            # Persist the static context SYNCHRONOUSLY (confirmed) BEFORE monitoring, so a
            # crash anywhere after this still records a proper exit. trade_id = idempotency key.
            trade_id = uuid.uuid4().hex
            _save_open_trade_sync({
                "ticker": ticker, "trade_id": trade_id, "entry_price": round(entry_price, 4),
                "target": round(target_price, 4), "stop": round(stop_loss, 4),
                "initial_shares": shares, "remaining_shares": shares, "tier_idx": 0,
                "partial_fills": [], "entry_type": entry_type, "confidence": confidence,
                "position_size": _reserved, "vwap": round(vwap, 4) if vwap else 0,
                "entry_date": datetime.now(EASTERN).strftime("%Y-%m-%d"),
                "entry_time": datetime.now(EASTERN).strftime("%I:%M %p"),
                "risk_per_share": round(entry_price - stop_loss, 4),
                "planned_risk": round(shares * (entry_price - stop_loss), 2),
            })
            # Register with the stale-trade watchdog (full ctx so it can record if the monitor freezes).
            _monitor_abort.discard(ticker)   # 7/11 audit A8: a stale abort flag from a never-thawed prior
                                             # monitor would insta-kill THIS trade's monitor on iteration 1
            _active_monitors[ticker] = {"heartbeat": time.time(), "alerted": False, "ctx": {
                "ticker": ticker, "trade_id": trade_id, "entry_price": round(entry_price, 4),
                "stop": round(stop_loss, 4), "initial_shares": shares, "remaining_shares": shares,
                "tier_idx": 0, "partial_fills": [], "entry_type": entry_type, "confidence": confidence,
                "position_size": _reserved, "entry_date": datetime.now(EASTERN).strftime("%Y-%m-%d"),
                "last_price": round(entry_price, 4)}}
            _note_positions(len(_active_monitors))   # track peak concurrent positions (capacity signal)

            trade_result = monitor_trade(
                ticker, shares, entry_price, target_price, stop_loss,
                stream, stop_order_id, vwap=vwap,
                next_supply=((extra or {}).get("room") or {}).get("next_supply"),
            )
            _active_monitors.pop(ticker, None)   # monitor returned — deregister from watchdog

            # DRY_RUN: skip the real-balance fetch entirely — the sim frame tracks its own balance, and the
            # fetch's side-post was flip-flopping the dashboard between $3,000(sim) and the real cash figure.
            _bal = 0.0 if DRY_RUN else get_account_balance()   # blocking Webull HTTP — fetch BEFORE the lock so we
                                           # don't serialize every other worker on the network call (audit HIGH-3)
            with trade_lock:
                _open_trade.pop(ticker, None)
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
                reentry["consec_loss"][ticker] = (
                    0 if pnl > 0 else reentry["consec_loss"].get(ticker, 0) + 1)
                _reentry_giveup = (exit_reason in REENTRY_GIVEUP_REASONS) or \
                                  (reentry["consec_loss"][ticker] >= REENTRY_MAX_CONSEC_LOSS)
                if _reentry_giveup:
                    reentry["givenup"].add(ticker); reentry["eligible"].discard(ticker)
                else:
                    reentry["eligible"].add(ticker)

            # ── RE-ENTRY (#2) observability — make the decision VISIBLE in the decision log so we can
            #    grade death-by-cuts vs Kev-style continuation in DRY_RUN. ──
            _att = reentry["count"].get(ticker, 0); _cl = reentry["consec_loss"].get(ticker, 0)
            print(f"🔁 {ticker} re-entry: "
                  f"{'GIVEN UP — ' + exit_reason if _reentry_giveup else 'ELIGIBLE for a fresh gated re-entry'} "
                  f"| attempts={_att} consec_loss={_cl}")
            _log_decision(ticker, "reentry_givenup" if _reentry_giveup else "reentry_eligible",
                          exit_reason=str(exit_reason), attempts=_att, consec_loss=_cl, pnl=round(pnl, 2))

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
                "est_slippage":    round(shares * float(l2_details.get("spread") or 0), 2),  # shares × L1 spread @ entry
                "entry_ema90":        round(entry_ema90, 4) if entry_ema90 > 0 else None,
                "entry_vs_ema90_pct": entry_vs_ema90_pct,
                "trade_id":           trade_id,
                # L1 order-book at entry (study: do adverse book conditions predict losers?)
                "entry_l1_ratio":     l2_details.get("ratio"),
                "entry_ask_size":     l2_details.get("ask_size"),
                "entry_bid_size":     l2_details.get("bid_size"),
                "entry_l1_spread":    l2_details.get("spread"),
                # Room to next supply at entry (Kev's master filter — taken trades should be ≥2:1)
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
            })
            if exit_reason != "WATCHDOG_ABORT":   # watchdog already recorded it (trade_id dedups)
                send_summary_email(analysis, trade_result, display_balance,
                                   csv_log_line=csv_row, traded_ticker=ticker)
            if _rec_ok:
                _clear_open_trade(ticker)   # recorded exit reached — drop durable recovery state
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
                    _open_trade.pop(_tkr, None)

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

    # Stale-trade watchdog — catches a monitor that freezes while the process stays alive.
    threading.Thread(target=_monitor_watchdog_loop, daemon=True, name="watchdog").start()
    print("🛟 Stale-trade watchdog thread started")

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
