#!/usr/bin/env python3
"""
Webull Deep Historical Backtest — v10 (Kev's Complete System)
==============================================================
v8 confirmed leader: 78 trades, 31% WR, 3.49:1 W/L, +$0.74 EV. v9 result unknown.

Applies every teachable lesson from @momentum.official (Kev's TikTok — 40+ videos):

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ENTRY FILTERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. START_TIME 09:45 — "let things settle" (Kev never trades the open spike)
  2. TIME_CUTOFF 11:00 — Kev's community session ends at 11am; afternoon = trap
  3. Above VWAP — VWAP is the line of control; below it = do not trade
  4. EMA9 > EMA20 — A+ Setup requires bullish EMA stack (confirmed from checklist video)
  5. Price < $20 — Kev's hard filter (small-cap focus)
  6. GAP 15–30% — qualifying gap-up day filter

  FLAT TOP BREAKOUT (Entry Type 1 — "No Break No Trade"):
  7. 8-bar consolidation window with <5% range — the flat top at resistance
  8. Breakout bar volume > 1.5x window average — confirms genuine break, not fake-out
     (This was a TODO comment in v9 that was never actually coded — now fixed)
  9. Last bar of window within 3% of window high — price near resistance, not fading
 10. Window second half avg high >= first half avg high — no descending highs pattern
     (Kev: "lower highs = bad pullback = do NOT enter")

  EMA PULLBACK BOUNCE (Entry Type 2 — "Catching the Bottom"):
 11. Previous bar touched EMA9 (within 0.5%) — the pullback reached the fast EMA
 12. Current bar bounces above EMA9 — buyers stepped in at the EMA
 13. Prior high exists above current price (2%+ higher) — a real run-up preceded the pullback
 14. Bounce bar volume > 1.2x the bars immediately before — buyer volume on bounce

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EXIT SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 15. Trailing stop — "a smidge below" (1.5%) each NEW HIGH bar's low; only moves up.
     Floor rule: stop never drops below entry price. (Kev's #1 lesson from CTNT video)
 16. EMA bounce initial stop — EMA9 at entry × (1 - 2.5%) for pullback entries.
     Kev: "less than 5 cents of risk" on a $2 stock = ~2.5% below EMA.
 17. Overextension exit — price > EMA9 × 1.08 → sell remaining.
     Arms after 3 bars so we don't exit a legitimate initial breakout.
     (Approximates red DOWN arrows Kev calls "the one signal")
 18. Partial exit — sell 25% ("a quarter") at first target. Kev is explicit: "Quarter, 25%, 1/4"
     Flat top: target = +10% from entry.
     EMA bounce: target = prior high before the pullback (Kev: "the past high").
 19. Time stop — 15:30 ET; Kev's window is 9:00–11:00 AM; afternoon halts are traps

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NOT IMPLEMENTABLE (data constraints):
    - Float < 20M (no float data in Webull bar API; universe pre-filtered to small-cap)
    - Halt-up continuation (halt candles appear as gaps; no halt feed available)
    - News catalyst filter (no real-time news in historical bar data)
    - Daily P&L stop (not applicable to per-trade backtest)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import time
import pathlib
import json
from datetime import datetime, date, timezone

import pytz
import pandas as pd

ET = pytz.timezone("America/New_York")

# ── Credentials ───────────────────────────────────────────────────────────────
WEBULL_APP_KEY      = os.environ.get("WEBULL_APP_KEY", "")
WEBULL_APP_SECRET   = os.environ.get("WEBULL_APP_SECRET", "")
WEBULL_ACCESS_TOKEN = os.environ.get("WEBULL_ACCESS_TOKEN", "")
WEBULL_TOKEN_DIR    = "/tmp/webull_token"
TRADING_HOST        = "api.webull.com"

if not WEBULL_APP_KEY or not WEBULL_ACCESS_TOKEN:
    print("❌  Missing credentials. Set WEBULL_APP_KEY + WEBULL_APP_SECRET + WEBULL_ACCESS_TOKEN")
    sys.exit(1)

expires_ms = int(time.time() * 1000) + (15 * 24 * 3600 * 1000)
token_dir  = pathlib.Path(WEBULL_TOKEN_DIR)
token_dir.mkdir(parents=True, exist_ok=True)
(token_dir / "token.txt").write_text(f"{WEBULL_ACCESS_TOKEN}\n{expires_ms}\nNORMAL\n")

try:
    from webull.core.client import ApiClient
    from webull.data.data_client import DataClient as WebullDataClient
except ImportError:
    print("❌  webull SDK not installed. Run: pip install webull-openapi-python-sdk")
    sys.exit(1)

def _make_dc():
    api = ApiClient(WEBULL_APP_KEY, WEBULL_APP_SECRET, "us",
                    token_check_duration_seconds=60,
                    token_check_interval_seconds=5)
    api.set_token_dir(WEBULL_TOKEN_DIR)
    api.add_endpoint("us", TRADING_HOST)
    return WebullDataClient(api)

dc = _make_dc()
print("✅  Webull DataClient initialized")


# ── Strategy constants ────────────────────────────────────────────────────────

# Timing (lesson 1 & 2)
START_TIME         = "09:45"
TIME_CUTOFF        = "11:00"

# Stock filters (lessons 3–6)
MIN_PRICE          = 1.50
MAX_PRICE          = 20.0       # Kev's explicit filter
MIN_GAP_PCT        = 0.15
MAX_GAP_PCT        = 0.30
VWAP_REQUIRED      = True

# EMA periods — confirmed from A+ checklist video (lessons 4)
EMA_SHORT          = 9
EMA_LONG           = 20

# Flat top breakout (lessons 7–10)
FLAT_TOP_WINDOW    = 8
FLAT_TOP_MAX_RANGE = 0.050      # <5% range in consolidation window
VOL_SPIKE_MULT     = 1.5        # breakout bar must be 1.5x window avg volume (lesson 8)
WINDOW_TOP_GATE    = 0.03       # last bar within 3% of window high (lesson 9)

# EMA pullback bounce (lessons 11–14)
EMA_BOUNCE_LOOKBACK = 20        # bars to look back for prior high
EMA_BOUNCE_TOUCH    = 0.005     # within 0.5% of EMA9 counts as "touched" (lesson 11)
EMA_BOUNCE_VOL_MULT = 1.2       # bounce bar must be 1.2x prior 3 bars avg (lesson 14)
EMA_STOP_BUFFER     = 0.025     # initial stop = EMA9 × (1 - 2.5%) for pullback entries (lesson 16)

# Exit system (lessons 15–19)
TRAIL_BUFFER_PCT   = 0.015      # stop trails 1.5% below each new high bar's low (lesson 15)
OVEREXT_MULT       = 1.08       # exit when price > EMA9 × 1.08 (lesson 17)
OVEREXT_MIN_BARS   = 3          # overextension check only arms after 3 bars (lesson 17)
PARTIAL_PCT        = 0.25       # sell 25% at first target — "a quarter" (lesson 18)
TARGET_PCT         = 0.10       # flat top partial target: +10% (lesson 18)

# Simulation
MIN_ABS_VOL        = 10_000
POSITION_DOLLARS   = 100.00
MAX_TRADES_PER_DAY = 2
DAILY_BAR_LOOKBACK = 400
RATE_LIMIT_SLEEP   = 0.3
DEBUG_ONLY         = os.environ.get("DEBUG_ONLY", "0") in ("1", "true", "yes")
DEBUG_MAX_TICKERS  = 5


# ── Ticker universe ───────────────────────────────────────────────────────────
UNIVERSE = [
    # Active small-cap/micro-cap momentum stocks
    "TLRY","SNDL","NKLA","CENN","MULN","IDEX","FFIE","BTBT","SONN",
    "HYMC","OCUP","OPFI","ROIV","RCKT","QBTS","PYPL","SUPN","STEM",
    "SKYX","SUNW","SURF","SDIG","LTBR","ORPH","PLRX","PGEN","PHVS",
    "RNAZ","RPID","RBBN","RPRX","RSLS","RUBY","RZLT",
    # From Kev's videos
    "MTEK","CREG","GXAI","MDJH","MGOL","MEGI","BFRI","KTTA",
    "ACST","ATNF","BIOR","BZFD","CIFS","CRKN","DARE","DPRO","EPAZ",
    "IMPP","IPDN","KAVL","LGMK","LKCO","MITI","MKUL","MNPR",
    "NCPL","NKGN","NOVV","NVNI","NXGL","OXBR","PBLA","PESI",
    "PRPH","PRVB","PULM","RZLT","SAMA","SCNX","SGLB","SGLY",
    "SIGL","SING","SISI","SOBR","SPRB","SPRC","SPRO","SRTX",
    "STAF","STGS","STIX","STOK","STRM","SUMR","SUNL","SURG",
    "SWAG","SXTC","SYRA","SYTA","TCON","TGLS","TPVG","TRDA",
    "TRIB","TSHA","TTAM","TVTX","TWST","TXMD","TYRA",
    # Known small-cap gap runners
    "SOUN","GFAI","RCAT","HITI","APWC","PAVS","BRTX","SBEV","RLAY",
    "DBGI","ADTX","WHLR","CLRB","CMND","GOVX","PHGE","IINN","ZJYL",
    "LPRO","HCWB","TDTH","AHMA","RGNT","CAST","GRNQ","MNTS",
    "ATPC","LASE","CDT","ARTL","TPET","STAK","BIAF","MNDR",
    "GLXG","PPCB","WTO","SER",
    # Added from June 2026 Kev videos
    "CRVO","CTNT","TNT","ALAR",
]
UNIVERSE = list(dict.fromkeys(UNIVERSE))


# ── Webull bar helpers ────────────────────────────────────────────────────────

_debug_printed = False

def _parse_bars(resp) -> list:
    global _debug_printed
    if resp.status_code != 200:
        return []
    raw = resp.json()
    bars = None
    if isinstance(raw, list):
        bars = raw
    elif isinstance(raw, dict):
        data = raw.get("data", raw)
        if isinstance(data, list):
            bars = data
        elif isinstance(data, dict):
            bars = data.get("items", data.get("list", data.get("bars", [])))
    if bars is None:
        bars = []
    if bars and not _debug_printed:
        _debug_printed = True
        print(f"\n  [DEBUG] Raw bar keys: {list(bars[0].keys())}")
        print(f"  [DEBUG] Sample bar:   {bars[0]}\n")
    return bars


def _bar_val(bar: dict, *keys):
    for k in keys:
        v = bar.get(k)
        if v is not None:
            try:
                f = float(v)
                if f != 0:
                    return f
            except (TypeError, ValueError):
                pass
    return 0.0


def _bar_ts_ms(bar: dict):
    for k in ("timestamp", "time", "t", "ts", "beginTime", "begin_time",
              "open_time", "openTime", "startTime", "start_time"):
        v = bar.get(k)
        if v is None:
            continue
        try:
            return int(v)
        except (TypeError, ValueError):
            pass
        if isinstance(v, str):
            try:
                from datetime import datetime as _dt
                s = v.replace("+0000", "+00:00").replace("-0000", "+00:00")
                fmt = "%Y-%m-%dT%H:%M:%S.%f%z" if "." in s else "%Y-%m-%dT%H:%M:%S%z"
                return int(_dt.strptime(s, fmt).timestamp() * 1000)
            except (ValueError, ImportError):
                pass
    return None


def _ms_to_et(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(ET)


def _day_start_ms(d: date) -> int:
    dt = ET.localize(datetime(d.year, d.month, d.day, 9, 30, 0))
    return int(dt.timestamp() * 1000)


def _day_end_ms(d: date) -> int:
    dt = ET.localize(datetime(d.year, d.month, d.day, 16, 0, 0))
    return int(dt.timestamp() * 1000)


# ── Phase 1: daily bars ───────────────────────────────────────────────────────

def fetch_daily_bars(ticker: str) -> list:
    try:
        resp = dc.market_data.get_history_bar(
            symbol=ticker, category="US_STOCK",
            timespan="D", count=str(DAILY_BAR_LOOKBACK),
        )
        return _parse_bars(resp)
    except Exception as e:
        print(f"    ⚠  daily bars error for {ticker}: {e}")
        return []


def find_gap_days(ticker: str, bars: list) -> list:
    results = []
    if len(bars) < 2:
        return results
    ts_first = _bar_ts_ms(bars[0])
    ts_last  = _bar_ts_ms(bars[-1])
    if ts_first and ts_last and ts_first > ts_last:
        bars = list(reversed(bars))
    for i in range(1, len(bars)):
        cur, prev = bars[i], bars[i - 1]
        open_p  = _bar_val(cur,  "open", "o", "opening")
        close_p = _bar_val(prev, "close", "c", "closing")
        if open_p <= 0 or close_p <= 0:
            continue
        gap = (open_p - close_p) / close_p
        if gap < MIN_GAP_PCT or gap > MAX_GAP_PCT:
            continue
        ts = _bar_ts_ms(cur)
        if ts:
            bar_date = _ms_to_et(ts).date()
        else:
            d_raw = cur.get("date") or cur.get("trade_date") or cur.get("tradeDate")
            if not d_raw:
                continue
            try:
                bar_date = date.fromisoformat(str(d_raw)[:10])
            except ValueError:
                continue
        results.append((bar_date, open_p, close_p, gap))
    return results


# ── Phase 2: 1-min bars ───────────────────────────────────────────────────────

def fetch_minute_bars(ticker: str, day: date) -> pd.DataFrame:
    try:
        resp = dc.market_data.get_history_bar(
            symbol=ticker, category="US_STOCK",
            timespan="M1", count="500",
            start_time=_day_start_ms(day),
            end_time=_day_end_ms(day),
        )
        bars = _parse_bars(resp)
        if not bars:
            return pd.DataFrame()
        rows = []
        for b in bars:
            ts = _bar_ts_ms(b)
            if not ts:
                continue
            rows.append({
                "datetime": _ms_to_et(ts),
                "Open":  _bar_val(b, "open",   "o"),
                "High":  _bar_val(b, "high",   "h"),
                "Low":   _bar_val(b, "low",    "l"),
                "Close": _bar_val(b, "close",  "c"),
                "Volume":_bar_val(b, "volume", "v"),
            })
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).set_index("datetime")
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)
        return df.between_time("09:30", "15:59")
    except Exception as e:
        print(f"    ⚠  minute bars error {ticker} {day}: {e}")
        return pd.DataFrame()


# ── Phase 3: indicators ───────────────────────────────────────────────────────

def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["tp"]    = (df["High"] + df["Low"] + df["Close"]) / 3
    df["vwap"]  = (df["tp"] * df["Volume"]).cumsum() / df["Volume"].cumsum()
    df["ema9"]  = df["Close"].ewm(span=EMA_SHORT, adjust=False).mean()
    df["ema20"] = df["Close"].ewm(span=EMA_LONG,  adjust=False).mean()
    return df


# ── Entry type 1: Flat Top Breakout ──────────────────────────────────────────

def _detect_flat_top(df: pd.DataFrame, i: int) -> bool:
    """
    "No Break No Trade" — price consolidates at resistance, then breaks above with volume.
    Returns True if bar i is a valid flat top breakout.
    """
    if i < FLAT_TOP_WINDOW:
        return False

    t_str = df.index[i].strftime("%H:%M")
    if t_str < START_TIME or t_str >= TIME_CUTOFF:
        return False

    price = float(df["Close"].iloc[i])
    vwap  = float(df["vwap"].iloc[i])
    ema9  = float(df["ema9"].iloc[i])
    ema20 = float(df["ema20"].iloc[i])
    vol   = float(df["Volume"].iloc[i])

    # Basic filters (lessons 3, 4, 5)
    if price < MIN_PRICE or price > MAX_PRICE:
        return False
    if VWAP_REQUIRED and price <= vwap:
        return False
    if ema9 <= ema20:
        return False
    if vol < MIN_ABS_VOL:
        return False

    window = df.iloc[i - FLAT_TOP_WINDOW : i]
    w_high = float(window["High"].max())
    w_low  = float(window["Low"].min())

    if w_low <= 0:
        return False

    # Flat top range check (lesson 7)
    if (w_high - w_low) / w_low > FLAT_TOP_MAX_RANGE:
        return False

    # Price must break above the window's high (lesson 7)
    if price <= w_high:
        return False

    # Lesson 8: breakout bar volume must be 1.5x the consolidation window average.
    # (confirms genuine break — not thin-volume fake-out)
    window_avg_vol = float(window["Volume"].mean())
    if window_avg_vol > 0 and vol < window_avg_vol * VOL_SPIKE_MULT:
        return False

    # Lesson 9: last bar in window must still be near the top of the range.
    # If price faded significantly before the "breakout", it's a bad setup.
    last_high = float(window["High"].iloc[-1])
    if last_high < w_high * (1 - WINDOW_TOP_GATE):
        return False

    # Lesson 10: no descending highs pattern in the window (bad pullback filter).
    # Split window in half — second half avg high must be >= first half avg high.
    # "Lower highs = bad pullback = do NOT enter" — Kev
    half = FLAT_TOP_WINDOW // 2
    first_half_avg  = float(window["High"].iloc[:half].mean())
    second_half_avg = float(window["High"].iloc[half:].mean())
    if second_half_avg < first_half_avg * 0.99:
        return False

    return True


# ── Entry type 2: EMA Pullback Bounce ────────────────────────────────────────

def _detect_ema_bounce(df: pd.DataFrame, i: int) -> tuple[bool, float]:
    """
    "Catching the Bottom" — price pulled back to EMA9 and is now bouncing.
    Returns (True, prior_high) if bar i is a valid EMA bounce entry.
    prior_high is used as the partial exit target.
    """
    if i < EMA_BOUNCE_LOOKBACK + 1:
        return False, 0.0

    t_str = df.index[i].strftime("%H:%M")
    if t_str < START_TIME or t_str >= TIME_CUTOFF:
        return False, 0.0

    price      = float(df["Close"].iloc[i])
    ema9       = float(df["ema9"].iloc[i])
    ema20      = float(df["ema20"].iloc[i])
    vwap       = float(df["vwap"].iloc[i])
    vol        = float(df["Volume"].iloc[i])
    prev_close = float(df["Close"].iloc[i - 1])
    prev_ema9  = float(df["ema9"].iloc[i - 1])

    # Basic filters (lessons 3, 4, 5)
    if price < MIN_PRICE or price > MAX_PRICE:
        return False, 0.0
    if VWAP_REQUIRED and price <= vwap:
        return False, 0.0
    if ema9 <= ema20:
        return False, 0.0
    if vol < MIN_ABS_VOL:
        return False, 0.0

    # Lesson 11: previous bar touched or crossed EMA9 (the pullback reached the EMA)
    if prev_close > prev_ema9 * (1 + EMA_BOUNCE_TOUCH):
        return False, 0.0

    # Lesson 12: current bar is now above EMA9 (the bounce)
    if price <= ema9:
        return False, 0.0

    # Lesson 13: there was a meaningful prior high (a real run-up preceded this pullback)
    lookback   = df.iloc[i - EMA_BOUNCE_LOOKBACK : i]
    prior_high = float(lookback["High"].max())
    if prior_high < price * 1.02:
        return False, 0.0

    # Also confirm: price was genuinely above EMA9 during the run-up
    # (price spent time above EMA9 before pulling back — not just always below)
    ema9_lookback  = lookback["ema9"]
    highs_lookback = lookback["High"]
    had_run_above  = any(
        float(highs_lookback.iloc[k]) > float(ema9_lookback.iloc[k]) * 1.02
        for k in range(len(lookback))
    )
    if not had_run_above:
        return False, 0.0

    # Lesson 14: bounce bar volume > 1.2x the average of the 3 bars before it
    # (confirms buyers stepping in at EMA, not just quiet drift back above)
    pre_bounce_vol = df["Volume"].iloc[i - 3 : i].mean()
    if pre_bounce_vol > 0 and vol < pre_bounce_vol * EMA_BOUNCE_VOL_MULT:
        return False, 0.0

    return True, prior_high


# ── Simulate a trade ─────────────────────────────────────────────────────────

def _simulate(
    df: pd.DataFrame,
    entry_i: int,
    entry_price: float,
    initial_stop: float,
    target: float,
    entry_type: str,
) -> dict | None:
    """
    Run the trade forward bar by bar.
    initial_stop: starting stop level (entry_price for flat top; EMA9-buffer for bounce)
    target: price for 25% partial exit
    """
    shares       = POSITION_DOLLARS / entry_price
    partial_done = False
    partial_price= 0.0
    partial_sold = shares * PARTIAL_PCT     # 25% sold at target
    remaining    = shares                   # drops to 75% after partial

    # Trailing stop starts at initial_stop; floor = entry_price once in profit
    trail_stop   = initial_stop
    highest_high = entry_price              # tracks new highs to know when to trail

    for j in range(entry_i + 1, len(df)):
        row   = df.iloc[j]
        price = float(row["Close"])
        high  = float(row["High"])
        low   = float(row["Low"])
        ema9  = float(row["ema9"])
        t_str = df.index[j].strftime("%H:%M")
        last  = (j == len(df) - 1) or t_str >= "15:30"

        if last:
            pnl = _calc_pnl(entry_price, partial_price, price,
                            partial_done, partial_sold, remaining)
            return _make_result(df, entry_i, entry_price, price, "TIME",
                                pnl, partial_done, partial_price, entry_type)

        # Lesson 18: partial exit — sell 25% at target
        if not partial_done and price >= target:
            partial_price = price
            partial_done  = True
            remaining     = shares - partial_sold
            # After partial profit: stop floor rises to entry_price (break-even rule)
            trail_stop = max(trail_stop, entry_price)

        # Lesson 17: overextension exit — price extended too far above EMA9
        # Only arms after OVEREXT_MIN_BARS bars to avoid exiting a legitimate breakout
        bars_in = j - entry_i
        if bars_in >= OVEREXT_MIN_BARS and ema9 > 0 and price > ema9 * OVEREXT_MULT:
            pnl = _calc_pnl(entry_price, partial_price, price,
                            partial_done, partial_sold, remaining)
            return _make_result(df, entry_i, entry_price, price, "OVEREXT",
                                pnl, partial_done, partial_price, entry_type)

        # Lesson 15: trailing stop — only moves up when a new high candle forms.
        # "Place stop a smidge below each new candle's low" — Kev (CTNT video)
        if high > highest_high:
            highest_high = high
            candidate    = low * (1 - TRAIL_BUFFER_PCT)
            # Floor: once profitable (partial done), stop can't drop below entry
            floor        = entry_price if partial_done else initial_stop
            trail_stop   = max(trail_stop, candidate, floor)

        # Exit when close crosses below the trailing stop
        if price <= trail_stop:
            next_open = float(df.iloc[j + 1]["Open"]) if j + 1 < len(df) else price
            pnl = _calc_pnl(entry_price, partial_price, next_open,
                            partial_done, partial_sold, remaining)
            return _make_result(df, entry_i, entry_price, next_open, "TRAIL STOP",
                                pnl, partial_done, partial_price, entry_type)

    return None


def _calc_pnl(entry, partial_price, exit_price, partial_done, partial_sold, remaining):
    p = 0.0
    if partial_done:
        p += (partial_price - entry) * partial_sold
    p += (exit_price - entry) * remaining
    return p


def _make_result(df, entry_i, entry_price, exit_price, reason,
                 pnl, partial_done, partial_price, entry_type):
    partial_str = f" (25%@${partial_price:.2f})" if partial_done else ""
    return {
        "entry_time":  df.index[entry_i].strftime("%H:%M"),
        "entry":       entry_price,
        "exit":        exit_price,
        "exit_reason": reason,
        "entry_type":  entry_type,
        "pnl":         round(pnl, 2),
        "gain_pct":    round((exit_price - entry_price) / entry_price * 100, 2),
        "partial":     partial_str,
    }


# ── Run one gap day ───────────────────────────────────────────────────────────

def run_day(ticker: str, day: date, gap_pct: float) -> dict:
    df = fetch_minute_bars(ticker, day)
    if df is None or len(df) < max(FLAT_TOP_WINDOW, EMA_BOUNCE_LOOKBACK) + 3:
        return {"ticker": ticker, "day": day, "note": "insufficient 1-min data", "trades": []}

    df     = _add_indicators(df)
    trades = []
    count  = 0
    last_i = -1

    for i in range(max(FLAT_TOP_WINDOW, EMA_BOUNCE_LOOKBACK + 1), len(df)):
        if count >= MAX_TRADES_PER_DAY:
            break
        if i <= last_i + 3:
            continue

        # Try flat top breakout first (higher-conviction setup)
        if _detect_flat_top(df, i):
            ep = float(df["Close"].iloc[i])
            result = _simulate(
                df, i, ep,
                initial_stop=ep,                    # floor from entry (trail starts here)
                target=ep * (1 + TARGET_PCT),       # +10% partial target
                entry_type="FLAT_TOP",
            )
            if result:
                trades.append(result)
                count  += 1
                last_i  = i
            continue

        # Try EMA pullback bounce
        is_bounce, prior_high = _detect_ema_bounce(df, i)
        if is_bounce:
            ep   = float(df["Close"].iloc[i])
            ema9 = float(df["ema9"].iloc[i])
            # Initial stop = EMA9 at entry × (1 - 2.5%) — "less than 5 cents risk on $2 stock"
            initial_stop = ema9 * (1 - EMA_STOP_BUFFER)
            # Target = prior high before the pullback (Kev: "the past high")
            target = prior_high if prior_high > ep * 1.02 else ep * (1 + TARGET_PCT)
            result = _simulate(
                df, i, ep,
                initial_stop=initial_stop,
                target=target,
                entry_type="EMA_BOUNCE",
            )
            if result:
                trades.append(result)
                count  += 1
                last_i  = i

    open_p  = float(df["Open"].iloc[0])
    high_p  = float(df["High"].max())
    close_p = float(df["Close"].iloc[-1])
    return {
        "ticker":  ticker,
        "day":     day,
        "gap_pct": round(gap_pct * 100, 1),
        "open":    open_p,
        "high":    high_p,
        "close":   close_p,
        "change":  round((close_p - open_p) / open_p * 100, 1),
        "trades":  trades,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*70}")
    print(f"  WEBULL DEEP BACKTEST v10 — Kev's Complete System")
    print(f"  Universe: {len(UNIVERSE)} tickers | Daily lookback: {DAILY_BAR_LOOKBACK} bars")
    print(f"  Entry window: {START_TIME}–{TIME_CUTOFF} | Gap: {MIN_GAP_PCT*100:.0f}%–{MAX_GAP_PCT*100:.0f}%")
    print(f"  Flat top: {FLAT_TOP_WINDOW}-bar <{FLAT_TOP_MAX_RANGE*100:.0f}% | Vol spike: >{VOL_SPIKE_MULT}x window avg")
    print(f"  EMA bounce: {EMA_BOUNCE_LOOKBACK}-bar lookback | Touch: {EMA_BOUNCE_TOUCH*100:.1f}%")
    print(f"  Exit: trail {TRAIL_BUFFER_PCT*100:.1f}%/new-high | overext EMA9×{OVEREXT_MULT} (>{OVEREXT_MIN_BARS}bars) | 25% partial")
    print(f"{'='*70}\n")

    # Phase 1: scan daily bars
    all_gaps = []
    seen     = set()
    print("Phase 1 — scanning daily bars for gap-up days...\n")

    for i, ticker in enumerate(UNIVERSE, 1):
        if DEBUG_ONLY and i > DEBUG_MAX_TICKERS:
            print(f"\n  [DEBUG_ONLY] Stopping after {DEBUG_MAX_TICKERS} tickers.")
            break

        daily = fetch_daily_bars(ticker)
        if not daily:
            print(f"  [{i:3d}/{len(UNIVERSE)}] {ticker:8s}  no daily data")
            time.sleep(RATE_LIMIT_SLEEP)
            continue

        gaps = find_gap_days(ticker, daily)
        for (day, open_p, prior_close, gap_pct) in gaps:
            key = (ticker, day)
            if key not in seen:
                seen.add(key)
                all_gaps.append((ticker, day, gap_pct))

        if gaps:
            oldest = min(g[0] for g in gaps)
            newest = max(g[0] for g in gaps)
            print(f"  [{i:3d}/{len(UNIVERSE)}] {ticker:8s}  {len(daily):4d} daily bars "
                  f"({oldest} → {newest})  {len(gaps):3d} gap days")
        else:
            print(f"  [{i:3d}/{len(UNIVERSE)}] {ticker:8s}  {len(daily):4d} daily bars  0 gap days")

        time.sleep(RATE_LIMIT_SLEEP)

    all_gaps.sort(key=lambda x: x[1])
    print(f"\n{'─'*70}")
    print(f"Total qualifying gap days: {len(all_gaps)}")
    if all_gaps:
        print(f"Date range: {all_gaps[0][1]} → {all_gaps[-1][1]}")
    print(f"{'─'*70}\n")

    if not all_gaps:
        print("No gap days found. Check credentials and ticker list.")
        return

    # Phase 2 & 3: run strategy
    print("Phase 2 — running strategy on each gap day...\n")
    all_results = []

    for j, (ticker, day, gap_pct) in enumerate(all_gaps, 1):
        result = run_day(ticker, day, gap_pct)
        all_results.append(result)

        n_trades = len(result.get("trades", []))
        note     = result.get("note", "")
        flag     = "✅" if n_trades > 0 else "  "
        print(f"  [{j:4d}/{len(all_gaps)}] {flag} {ticker:8s} {day}  "
              f"gap={gap_pct:+.0f}%  "
              f"{'→ ' + str(n_trades) + ' trade(s)' if n_trades else '(no signal)' if not note else note}")

        time.sleep(RATE_LIMIT_SLEEP)

    print_report(all_results, all_gaps)
    save_results(all_results)


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_report(results, all_gaps):
    all_trades = []
    for r in results:
        for t in r.get("trades", []):
            y = r["day"].year if isinstance(r["day"], date) else int(str(r["day"])[:4])
            all_trades.append({
                **t,
                "ticker":  r["ticker"],
                "day":     r["day"],
                "gap_pct": r.get("gap_pct", 0),
                "year":    str(y),
            })

    n_gap_days = len(all_gaps)
    n_signal   = len([r for r in results if r.get("trades")])

    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY — v10 (Kev's Complete System)")
    print(f"{'='*70}")
    if n_gap_days:
        print(f"  Gap-up days scanned   : {n_gap_days}")
        print(f"  Days with signal      : {n_signal}  ({n_signal/n_gap_days*100:.0f}%)")
        print(f"  Days with no signal   : {n_gap_days - n_signal}")
    print(f"  Total trades          : {len(all_trades)}")

    if not all_trades:
        print("\n  No trades triggered. Consider relaxing parameters.")
        return

    wins   = [t for t in all_trades if t["pnl"] > 0]
    losses = [t for t in all_trades if t["pnl"] <= 0]
    total  = sum(t["pnl"] for t in all_trades)
    wr     = len(wins) / len(all_trades) * 100
    ev     = total / len(all_trades)
    avg_win  = sum(t["pnl"] for t in wins)  / len(wins)   if wins   else 0
    avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
    rr       = abs(avg_win / avg_loss) if avg_loss else float("inf")

    print(f"  Win rate              : {wr:.0f}%  ({len(wins)}W / {len(losses)}L)")
    print(f"  Total P&L             : ${total:+.2f}  (on ${POSITION_DOLLARS:.0f}/trade)")
    print(f"  Avg winner            : ${avg_win:+.2f}")
    print(f"  Avg loser             : ${avg_loss:+.2f}")
    print(f"  Win/loss ratio        : {rr:.2f}:1")
    print(f"  Expected value/trade  : ${ev:+.2f}")
    if all_gaps:
        dates = [g[1] for g in all_gaps]
        span  = (max(dates) - min(dates)).days
        print(f"  Date range            : {min(dates)} → {max(dates)}  ({span} days)")

    # By entry type
    print(f"\n  ── By entry type ──────────────────────────────────────────")
    for etype in ("FLAT_TOP", "EMA_BOUNCE"):
        et = [t for t in all_trades if t.get("entry_type") == etype]
        if et:
            ew = [t for t in et if t["pnl"] > 0]
            aw = sum(t["pnl"] for t in ew)  / len(ew)  if ew  else 0
            al_list = [t for t in et if t["pnl"] <= 0]
            al = sum(t["pnl"] for t in al_list) / len(al_list) if al_list else 0
            rr_et = abs(aw / al) if al else float("inf")
            print(f"    {etype:12s}  {len(et):3d} trades  "
                  f"{len(ew)/len(et)*100:.0f}% WR  "
                  f"W/L {rr_et:.2f}  "
                  f"${sum(t['pnl'] for t in et):+.2f}")

    # By exit reason
    print(f"\n  ── By exit reason ──────────────────────────────────────────")
    by_reason = {}
    for t in all_trades:
        by_reason.setdefault(t["exit_reason"], []).append(t)
    for reason, ts in sorted(by_reason.items()):
        w = len([t for t in ts if t["pnl"] > 0])
        print(f"    {reason:14s}  {len(ts):3d} trades  {w/len(ts)*100:.0f}% WR  "
              f"${sum(t['pnl'] for t in ts):+.2f}")

    # By year
    print(f"\n  ── By year ─────────────────────────────────────────────────")
    by_year = {}
    for t in all_trades:
        by_year.setdefault(t["year"], []).append(t)
    for y in sorted(by_year):
        ts = by_year[y]
        w  = len([t for t in ts if t["pnl"] > 0])
        print(f"    {y}  {len(ts):3d} trades  {w/len(ts)*100:.0f}% WR  "
              f"${sum(t['pnl'] for t in ts):+.2f}")

    # By entry time bucket
    print(f"\n  ── By entry time ───────────────────────────────────────────")
    for h_s, h_e in [("09:45","10:00"),("10:00","10:15"),
                     ("10:15","10:30"),("10:30","10:45"),("10:45","11:00")]:
        bucket = [t for t in all_trades
                  if h_s <= t.get("entry_time", "00:00") < h_e]
        if bucket:
            bw = [t for t in bucket if t["pnl"] > 0]
            print(f"    {h_s}–{h_e}  {len(bucket):3d} trades  "
                  f"{len(bw)/len(bucket)*100:.0f}% WR  "
                  f"${sum(t['pnl'] for t in bucket):+.2f}")

    # By gap bucket
    print(f"\n  ── By gap % ────────────────────────────────────────────────")
    for lo, hi in [(15, 20), (20, 25), (25, 30)]:
        bucket = [t for t in all_trades if lo <= t["gap_pct"] < hi]
        if bucket:
            bw = [t for t in bucket if t["pnl"] > 0]
            print(f"    {lo}–{hi}%  {len(bucket):3d} trades  "
                  f"{len(bw)/len(bucket)*100:.0f}% WR  "
                  f"${sum(t['pnl'] for t in bucket):+.2f}")

    # Partial exit stats
    partials = [t for t in all_trades if t.get("partial")]
    print(f"\n  Partial exit (25%) fired : {len(partials)}/{len(all_trades)} trades "
          f"({len(partials)/len(all_trades)*100:.0f}%)")

    # Top winners / losers
    print(f"\n  ── Top 10 winners ──────────────────────────────────────────")
    for t in sorted(wins, key=lambda x: -x["pnl"])[:10]:
        print(f"    {t['day']}  {t['ticker']:<8} [{t.get('entry_type','?'):10}] "
              f"gap={t['gap_pct']:>4.0f}%  "
              f"@${t.get('entry',0):.2f}  {t.get('gain_pct',0):>+.2f}%  "
              f"${t['pnl']:+.2f}  {t.get('exit_reason','?')}  {t.get('partial','')}")

    print(f"\n  ── Top 10 losers ───────────────────────────────────────────")
    for t in sorted(losses, key=lambda x: x["pnl"])[:10]:
        print(f"    {t['day']}  {t['ticker']:<8} [{t.get('entry_type','?'):10}] "
              f"gap={t['gap_pct']:>4.0f}%  "
              f"@${t.get('entry',0):.2f}  {t.get('gain_pct',0):>+.2f}%  "
              f"${t['pnl']:+.2f}  {t.get('exit_reason','?')}")

    print(f"\n{'='*70}")
    print(f"  BASELINE: v8 confirmed leader — 78 trades, 31% WR, 3.49:1 W/L, +$0.74 EV")
    print(f"{'='*70}")


def save_results(results):
    out = "/tmp/webull_backtest_v10_results.json"
    with open(out, "w") as f:
        json.dump([{
            "ticker":  r["ticker"],
            "day":     str(r.get("day", "")),
            "gap_pct": r.get("gap_pct", 0),
            "trades":  r.get("trades", []),
            "note":    r.get("note", ""),
        } for r in results], f, indent=2)
    print(f"\n  Raw results saved → {out}")
    print(f"  v10: Kev's complete system | 19 lessons applied | 2 entry types")


if __name__ == "__main__":
    main()
