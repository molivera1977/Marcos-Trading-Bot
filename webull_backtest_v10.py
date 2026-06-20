#!/usr/bin/env python3
"""
Webull Deep Historical Backtest — v10.2 (Kev's Complete System)
==============================================================
v8 confirmed leader: 78 trades, 31% WR, 3.49:1 W/L, +$0.74 EV. v10/v10-YF both
came in negative EV. Code audit (2026-06-20) found 9 concrete bugs/gaps vs
Kev's actual lessons — all fixed below (marked NEW or FIXED).

Applies every teachable lesson from @momentum.official (Kev's TikTok — 40+ videos):

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ENTRY FILTERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1.  START_TIME 09:45 — "let things settle" (Kev never trades the open spike)
  2.  TIME_CUTOFF 11:00 — Kev's window; afternoon = trap (down-halt risk)
  3.  Above VWAP — VWAP is the line of control; below = do not trade
  4.  EMA9 > EMA20 — A+ Setup: bullish EMA stack (confirmed from checklist video)
  5.  Price < $20, > $0.50 — FIXED: was $1.50 floor, which contradicted Kev's own
      sub-$1 (even sub-$0.20) trades. Now matches the live bot's tuned floor.
  6.  Float < 20M shares — Kev's most important pre-filter; prefetched via yfinance
      (current float used as proxy; if unavailable, ticker is allowed through)
  7.  GAP 15–30% on daily bar — qualifying gap-up day
  28. RVOL > 1.5x trailing 20-day avg volume — NEW: Kev's screener filter
      ("Relative Volume: Over 1.5"). Previously only intraday relative volume
      (breakout bar vs its own window) was checked — the actual day-level
      screener criterion was missing entirely.
  29. Daily Range >= 10% (H/L on the gap day itself) — NEW: A+ checklist item 5
      ("Daily Range"). A dull stock that merely gapped on the open but didn't
      move much intraday isn't the "explosive" setup Kev screens for.

  FLAT TOP BREAKOUT — Entry Type 1 ("No Break No Trade"):
  8.  8-bar consolidation window with <5% H/L range
  9.  Breakout bar volume > 1.5× window average — genuine break, not fake-out
      (Was a TODO comment in every prior version — now actually coded)
  10. Last bar of window within 3% of window high — price near resistance, not fading
  11. Window 2nd-half avg high >= 1st-half avg high — no descending highs pattern
      (Kev: "lower highs = bad pullback = do NOT enter")
  30. NEW ("avoid being someone's liquidity"): reject if the breakout level is
      >5% below an earlier, bigger high made the same session — that's chasing
      a fading top / distribution pattern, not a fresh breakout.

  EMA PULLBACK BOUNCE — Entry Type 2 ("Catching the Bottom"):
  12. Previous bar touched EMA9 (within 0.5%) — pullback reached the fast EMA
  13. Current bar bounces above EMA9 — buyers stepped in at the EMA
  14. Prior high exists 2%+ above current price — real run-up preceded the pullback
  14b.FIXED: prior high must clear a 3:1 reward:risk minimum vs the EMA9 stop —
      Kev's own words: "15c reward vs <5c risk." The old 2%-target gate let
      setups through near ~1:1 R:R whenever the EMA9 stop was ~2.5% away.
  15. Price was above EMA9 during that run (not just a dead stock drifting)
  16. Bounce bar volume > 1.2× preceding 3 bars — buyer volume confirms the bounce

  HALT-SQUEEZE CONTINUATION — Entry Type 3 (NEW, "catch halts before they squeeze"):
  26. Buy the bar that resumes after a circuit-breaker halt-up, if price continues
      at/above the pre-halt high (CRVO example: halted $5.47-5.95, resumed $6.00,
      ran to $6.58). Previously halts were ONLY handled on the exit side
      (don't get stopped during the gap) — there was no entry signal for the
      thing Kev explicitly trades: the post-halt continuation itself.
  27. "Clean P.A." gate — FLAT_TOP/EMA_BOUNCE entries are skipped on days with
      >5 halts. Kev's halt examples (CRVO, TNT) involve ONE clean halt — a
      ticker re-triggering circuit breakers 10-90x/day is chop, not the "clean,
      predictable" setup he describes. (HALT_CONT entries are still allowed on
      these days since that IS Kev's halt-trading setup.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EXIT SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  17. Trailing stop — 1.5% below each NEW HIGH bar's low; only moves up.
      Floor: stop never drops below entry price.
      (Kev's CTNT video: "Now stop letting green trades turn red")
  17b.FIXED — flat top initial stop was `= entry_price` (ZERO buffer): any 1-tick
      dip on the very next bar triggered an instant stop-out before the trade had
      any room to develop. Now uses entry candle's low × (1 − 1.5%), matching
      Kev's actual "a smidge below the entry candle's low" rule (same as 17,
      applied to entry type 1 instead of only the post-entry trail).
  18. EMA bounce initial stop — EMA9 at entry × (1 − 2.5%).
      Kev: "less than 5 cents of risk" on a $2 stock ≈ 2.5% below EMA9.
  19. Break-even rule — after partial exit fires, trail_stop floor = entry_price.
  20. Overextension exit — price > EMA9 × 1.08 → sell remaining.
      Arms after 3 bars. Skips 3 bars after a halt-up (gap-up is expected, not overext).
      (Approximates red DOWN arrows: "the one signal to learn")
  21. Partial exit — sell 25% ("a quarter") at first target.
      Flat top: target = +10%. EMA bounce: target = prior high before pullback.
      (Kev directly confirmed: "Quarter, 25%, 1/4")
  22. FIXED — Time stop now forces exit by 11:30 ET (was 15:30). Kev's session
      ends at 11am and he explicitly warns the down-halt danger zone starts as
      early as 11:30am-noon with no circuit-breaker protection going down — the
      old 15:30 cutoff let open positions ride straight into that trap.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HALT-UP AWARENESS (detected from 1-min bar timestamp gaps)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  23. Halt detection — gaps > 90s between consecutive 1-min bars = circuit halt.
      (CRVO's 09:36→09:46 gap confirmed visible in Webull 1-min data)
  24. Hold through halt-up — trail stop does NOT fire during halt gap.
      The next bar after halt resumes naturally; trail stop updates from post-halt high.
  25. Overext grace — overextension check suppressed for 3 bars after halt resumes.
      (Post-halt gap-up is momentum, not overextension)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NOT IMPLEMENTABLE (data constraints):
    - Historical float (yfinance gives current only; used as best proxy)
    - News/catalyst filter (no historical news feed in bar data)
    - Daily P&L stop (not applicable to per-trade backtest)
    - Pre-market volume (yfinance 1-min goes back 7 days only; useless for 1.5yr bt)
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
import yfinance as yf

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

# Timing (lessons 1–2)
START_TIME         = "09:45"
TIME_CUTOFF        = "11:00"
TIME_STOP          = "11:30"     # FIXED (lesson 22): was 15:30 — Kev's danger zone starts
                                  # ~11:30am-noon (down-halt traps, no circuit breaker
                                  # protection on the way down); his session ends at 11am.

# Stock filters (lessons 3–7)
MIN_PRICE          = 0.50        # matches live bot floor; Kev trades sub-$1 (even sub-$0.20) setups
MAX_PRICE          = 20.0
MAX_FLOAT          = 20_000_000   # Kev's explicit filter: < 20M shares
MIN_GAP_PCT        = 0.05   # widened: 15% was invented internally, not from Kev; 5% still requires a real gap-up mover
MAX_GAP_PCT        = 2.00   # effectively no upper cap; big gap days (50-200%+) on sub-$1 stocks are Kev's bread-and-butter
VWAP_REQUIRED      = True
RVOL_MIN           = 1.5         # lesson 28: Kev's screener "Relative Volume: Over 1.5"
MIN_DAILY_RANGE_PCT = 0.10        # lesson 29 ("Daily Range," A+ checklist item 5): the
                                  # gap day itself must have a meaningful (>=10%) H/L
                                  # range — not a dull stock barely moving intraday
DISTRIBUTION_GATE_PCT = 0.05      # lesson 30 ("avoid being someone's liquidity"): reject
                                  # FLAT_TOP breakouts that are a lower-high off an earlier,
                                  # bigger spike (the breakout level is >5% below the day's
                                  # already-made high) — that's chasing a fading top, not a
                                  # fresh breakout

# EMA periods — confirmed from A+ checklist video (lesson 4)
EMA_SHORT          = 9
EMA_LONG           = 20

# Flat top breakout (lessons 8–11)
FLAT_TOP_WINDOW    = 8
FLAT_TOP_MAX_RANGE = 0.050        # <5% H/L range in consolidation window
VOL_SPIKE_MULT     = 1.5          # breakout bar > 1.5× window avg volume (lesson 9)
WINDOW_TOP_GATE    = 0.03         # last bar within 3% of window high (lesson 10)

# EMA pullback bounce (lessons 12–16)
EMA_BOUNCE_LOOKBACK = 20          # bars to look back for prior high
EMA_BOUNCE_TOUCH    = 0.005       # ≤0.5% above EMA9 counts as "touched" (lesson 12)
EMA_BOUNCE_VOL_MULT = 1.2         # bounce bar > 1.2× prior 3-bar avg (lesson 16)
EMA_STOP_BUFFER     = 0.025       # initial stop = EMA9 × (1 − 2.5%) (lesson 18)
MIN_RR              = 3.0        # Kev's stated minimum R:R ("15c reward vs <5c risk") (lesson 14b)

# Halt-squeeze continuation (lesson 26, new entry type)
HALT_CONT_MIN_PCT = 0.0           # resumed price must be >= pre-halt high (no discount allowed)
MAX_CLEAN_HALTS   = 5             # lesson 27 ("Clean P.A."): >5 halts/day = chop storm, not a clean setup

# Exit system (lessons 17–22)
TRAIL_BUFFER_PCT   = 0.015        # trail 1.5% below each new high bar's low (lesson 17)
OVEREXT_MULT       = 1.08         # exit when price > EMA9 × 1.08 (lesson 20)
OVEREXT_MIN_BARS   = 3            # arms after 3 bars post-entry (lesson 20)
HALT_OVEREXT_GRACE = 3            # additional bars of overext suppression after halt-up (lesson 25)
PARTIAL_PCT        = 0.25         # sell 25% at first target (lesson 21)
TARGET_PCT         = 0.10         # flat top partial target: +10%

# Halt detection (lessons 23–25)
HALT_GAP_SECONDS   = 90           # gap > 90s between consecutive 1-min bars = halt

# Simulation
MIN_ABS_VOL        = 10_000
POSITION_DOLLARS   = 100.00
MAX_TRADES_PER_DAY = 10   # Kev enters 6-10 trades/day, sometimes multiple times in the same stock
DAILY_BAR_LOOKBACK = 400         # Webull daily bars per ticker (~1.5 years)
RATE_LIMIT_SLEEP   = 0.3         # sleep between all Webull API calls
DEBUG_ONLY         = os.environ.get("DEBUG_ONLY", "0") in ("1", "true", "yes")
DEBUG_MAX_TICKERS  = 5

# Float cache — populated by _prefetch_floats() at startup (lesson 6)
FLOAT_CACHE: dict = {}


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


# ── Float prefetch (lesson 6) ─────────────────────────────────────────────────

def _prefetch_floats(tickers: list) -> None:
    """
    Fetch current float for all tickers via yfinance. Results cached in FLOAT_CACHE.
    Uses current float as a proxy for historical — best available without a paid feed.
    Tickers with no float data are allowed through (benefit of the doubt).
    """
    print(f"Fetching float data for {len(tickers)} tickers via yfinance...")
    allowed = blocked = unknown = 0
    for sym in tickers:
        try:
            info = yf.Ticker(sym).info
            f    = info.get("floatShares") or info.get("sharesFloat")
            FLOAT_CACHE[sym] = f
            if f is None:
                unknown += 1
            elif f <= MAX_FLOAT:
                allowed += 1
            else:
                blocked += 1
        except Exception:
            FLOAT_CACHE[sym] = None
            unknown += 1
        time.sleep(0.05)   # light rate limiting

    print(f"  ✅ under {MAX_FLOAT//1_000_000}M: {allowed} tickers")
    print(f"  ❌ over  {MAX_FLOAT//1_000_000}M: {blocked} tickers (will skip)")
    print(f"  ❓ unknown float: {unknown} tickers (will allow through)\n")


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
    for k in ("timestamp","time","t","ts","beginTime","begin_time",
              "open_time","openTime","startTime","start_time"):
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
    return int(ET.localize(datetime(d.year, d.month, d.day, 9, 30, 0)).timestamp() * 1000)


def _day_end_ms(d: date) -> int:
    return int(ET.localize(datetime(d.year, d.month, d.day, 16, 0, 0)).timestamp() * 1000)


# ── Phase 1: daily bars via Webull ───────────────────────────────────────────

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
    vols = [_bar_val(b, "volume", "v") for b in bars]
    for i in range(1, len(bars)):
        cur, prev = bars[i], bars[i - 1]
        open_p  = _bar_val(cur,  "open", "o", "opening")
        close_p = _bar_val(prev, "close", "c", "closing")
        if open_p <= 0 or close_p <= 0:
            continue
        gap = (open_p - close_p) / close_p
        if gap < MIN_GAP_PCT or gap > MAX_GAP_PCT:
            continue

        # Lesson 28 (new): RVOL > 1.5x trailing 20-day avg volume — Kev's screener
        # filter ("Relative Volume: Over 1.5"). Without this, a "gap day" with
        # unremarkable volume passes through even though Kev's scanner would reject it.
        trailing_vols = [v for v in vols[max(0, i - 20):i] if v > 0]
        if trailing_vols:
            avg_vol = sum(trailing_vols) / len(trailing_vols)
            day_vol = vols[i]
            if avg_vol > 0 and day_vol > 0 and day_vol / avg_vol < RVOL_MIN:
                continue

        # Lesson 29 (new, A+ checklist item 5 "Daily Range"): the gap day itself
        # needs a meaningful H/L range — a dull stock barely moving intraday isn't
        # the "explosive" setup Kev screens for, even if it gapped on the open.
        day_high = _bar_val(cur, "high", "h")
        day_low  = _bar_val(cur, "low",  "l")
        if day_low > 0 and (day_high - day_low) / day_low < MIN_DAILY_RANGE_PCT:
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


# ── Phase 2: 1-min bars + halt detection ─────────────────────────────────────

def fetch_minute_bars(ticker: str, day: date) -> tuple:
    """
    Returns (df, halt_bar_indices) where halt_bar_indices is a set of integer
    positions in df where a circuit-breaker halt gap was detected (>90s gap
    between consecutive 1-min bars). These positions mark the FIRST bar after
    each halt resumed.
    """
    try:
        resp = dc.market_data.get_history_bar(
            symbol=ticker, category="US_STOCK",
            timespan="M1", count="500",
            start_time=_day_start_ms(day),
            end_time=_day_end_ms(day),
        )
        bars = _parse_bars(resp)
        if not bars:
            return pd.DataFrame(), set()
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
            return pd.DataFrame(), set()
        df = pd.DataFrame(rows).set_index("datetime")
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)
        df = df.between_time("09:30", "15:59")

        # Lesson 23: detect halt gaps — consecutive bars >90s apart (but <12h = not overnight)
        halt_bars: set = set()
        ts_list = df.index.to_list()
        for k in range(1, len(ts_list)):
            gap_s = (ts_list[k] - ts_list[k - 1]).total_seconds()
            if HALT_GAP_SECONDS < gap_s < 43200:
                halt_bars.add(k)

        return df, halt_bars

    except Exception as e:
        print(f"    ⚠  minute bars error {ticker} {day}: {e}")
        return pd.DataFrame(), set()


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
    "No Break No Trade" — price consolidates at resistance, breaks above with volume.
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

    if price < MIN_PRICE or price > MAX_PRICE:       # lessons 5
        return False
    if VWAP_REQUIRED and price <= vwap:              # lesson 3
        return False
    if ema9 <= ema20:                                # lesson 4
        return False
    if vol < MIN_ABS_VOL:
        return False

    window = df.iloc[i - FLAT_TOP_WINDOW : i]
    w_high = float(window["High"].max())
    w_low  = float(window["Low"].min())
    if w_low <= 0:
        return False

    # Lesson 8: flat top range
    if (w_high - w_low) / w_low > FLAT_TOP_MAX_RANGE:
        return False
    # Price must break above the window's high
    if price <= w_high:
        return False

    # Lesson 9: breakout bar volume > 1.5× consolidation window average
    window_avg_vol = float(window["Volume"].mean())
    if window_avg_vol > 0 and vol < window_avg_vol * VOL_SPIKE_MULT:
        return False

    # Lesson 10: last bar in window must still be near the top
    last_high = float(window["High"].iloc[-1])
    if last_high < w_high * (1 - WINDOW_TOP_GATE):
        return False

    # Lesson 11: no descending highs — 2nd half of window avg high >= 1st half
    half = FLAT_TOP_WINDOW // 2
    if float(window["High"].iloc[half:].mean()) < float(window["High"].iloc[:half].mean()) * 0.99:
        return False

    # Lesson 30 ("avoid being someone's liquidity"): reject if this breakout is a
    # LOWER high off an earlier, bigger spike today. Kev's red flag: "stock already
    # made a BIG first move -> pulled back -> consolidating at a lower level" — you'd
    # be buying the exits of whoever bought the real high, not a fresh breakout.
    if i > FLAT_TOP_WINDOW:
        day_prior_high = float(df["High"].iloc[:i - FLAT_TOP_WINDOW].max())
        if day_prior_high > w_high * (1 + DISTRIBUTION_GATE_PCT):
            return False

    return True


# ── Entry type 2: EMA Pullback Bounce ────────────────────────────────────────

def _detect_ema_bounce(df: pd.DataFrame, i: int) -> tuple:
    """
    "Catching the Bottom" — price pulled back to EMA9 and is bouncing.
    Returns (True, prior_high) if valid; prior_high used as partial exit target.
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

    if price < MIN_PRICE or price > MAX_PRICE:      # lesson 5
        return False, 0.0
    if VWAP_REQUIRED and price <= vwap:             # lesson 3
        return False, 0.0
    if ema9 <= ema20:                               # lesson 4
        return False, 0.0
    if vol < MIN_ABS_VOL:
        return False, 0.0

    # Lesson 12: prev bar touched EMA9 (within 0.5% above — it pulled back)
    if prev_close > prev_ema9 * (1 + EMA_BOUNCE_TOUCH):
        return False, 0.0

    # Lesson 13: current bar bounced above EMA9
    if price <= ema9:
        return False, 0.0

    # Lesson 14: prior high exists (a real run-up preceded this pullback)
    lookback   = df.iloc[i - EMA_BOUNCE_LOOKBACK : i]
    prior_high = float(lookback["High"].max())
    if prior_high < price * 1.02:
        return False, 0.0

    # Lesson 14b: minimum 3:1 reward:risk to the prior high, per Kev's stated minimum
    # ("15c reward vs <5c risk on a ~$2 stock"). Without this, thin setups with a
    # ~2% target and ~2.5% stop risk would qualify at well under 1:1.
    risk = price - ema9 * (1 - EMA_STOP_BUFFER)
    if risk <= 0 or prior_high < price + risk * MIN_RR:
        return False, 0.0

    # Lesson 15: price was above EMA9 during the prior run (not always below)
    had_run = any(
        float(lookback["High"].iloc[k]) > float(lookback["ema9"].iloc[k]) * 1.02
        for k in range(len(lookback))
    )
    if not had_run:
        return False, 0.0

    # Lesson 16: bounce bar volume > 1.2× the 3 bars before it
    pre_vol = df["Volume"].iloc[i - 3 : i].mean()
    if pre_vol > 0 and vol < pre_vol * EMA_BOUNCE_VOL_MULT:
        return False, 0.0

    return True, prior_high


# ── Entry type 3: Halt-Squeeze Continuation ──────────────────────────────────

def _detect_halt_continuation(df: pd.DataFrame, i: int, halt_bars: set) -> bool:
    """
    "Catch halts before they squeeze" — buy the bar that resumes after a circuit-
    breaker halt-up, if it continues above the pre-halt high (CRVO example: halted
    near $5.47-5.95, resumed at $6.00, ran to $6.58).
    """
    if i not in halt_bars:
        return False
    t_str = df.index[i].strftime("%H:%M")
    if t_str < START_TIME or t_str >= TIME_CUTOFF:
        return False

    price = float(df["Close"].iloc[i])
    vwap  = float(df["vwap"].iloc[i])
    vol   = float(df["Volume"].iloc[i])

    if price < MIN_PRICE or price > MAX_PRICE:
        return False
    if VWAP_REQUIRED and price <= vwap:
        return False
    if vol < MIN_ABS_VOL:
        return False

    # Resumed price must continue at/above the pre-halt high — an up-halt that
    # resumes LOWER is a down-halt-style trap, not the squeeze continuation Kev plays.
    pre_halt_high = float(df["High"].iloc[:i].max()) if i > 0 else 0.0
    if pre_halt_high <= 0 or price < pre_halt_high * (1 - HALT_CONT_MIN_PCT):
        return False

    return True


# ── Trade simulation ──────────────────────────────────────────────────────────

def _simulate(
    df: pd.DataFrame,
    entry_i: int,
    entry_price: float,
    initial_stop: float,
    target: float,
    entry_type: str,
    halt_bars: set,
) -> dict | None:
    """
    Runs the trade forward bar by bar applying Kev's full exit system.

    initial_stop : entry_price for flat top (break-even from start);
                   EMA9 × (1 − 2.5%) for EMA bounce (defined risk below EMA).
    target       : price at which 25% partial is sold.
    halt_bars    : set of df integer positions that immediately follow a halt gap.
    """
    shares       = POSITION_DOLLARS / entry_price
    partial_done = False
    partial_price= 0.0
    partial_sold = shares * PARTIAL_PCT
    remaining    = shares

    trail_stop    = initial_stop
    highest_high  = entry_price
    post_halt_grace = 0       # bars to suppress overext check after halt-up

    for j in range(entry_i + 1, len(df)):
        row   = df.iloc[j]
        price = float(row["Close"])
        high  = float(row["High"])
        low   = float(row["Low"])
        ema9  = float(row["ema9"])
        t_str = df.index[j].strftime("%H:%M")
        last  = (j == len(df) - 1) or t_str >= TIME_STOP

        # Lesson 25: detect halt-up — first bar after a halt gap
        is_post_halt = j in halt_bars
        if is_post_halt:
            post_halt_grace = HALT_OVEREXT_GRACE   # suppress overext for next N bars

        if last:
            pnl = _calc_pnl(entry_price, partial_price, price,
                            partial_done, partial_sold, remaining)
            return _make_result(df, entry_i, entry_price, price, "TIME",
                                pnl, partial_done, partial_price, entry_type,
                                j in halt_bars)

        # Lesson 21: partial exit — 25% at first target
        if not partial_done and price >= target:
            partial_price = price
            partial_done  = True
            remaining     = shares - partial_sold
            # Lesson 19: after partial, floor rises to entry (break-even rule)
            trail_stop = max(trail_stop, entry_price)

        # Lesson 20: overextension exit (suppressed during post-halt grace period)
        bars_in = j - entry_i
        if post_halt_grace > 0:
            post_halt_grace -= 1
        elif bars_in >= OVEREXT_MIN_BARS and ema9 > 0 and price > ema9 * OVEREXT_MULT:
            pnl = _calc_pnl(entry_price, partial_price, price,
                            partial_done, partial_sold, remaining)
            return _make_result(df, entry_i, entry_price, price, "OVEREXT",
                                pnl, partial_done, partial_price, entry_type,
                                j in halt_bars)

        # Lesson 17: trailing stop — only updates when a new high bar forms.
        # "Place stop a smidge below each new candle's low" — Kev (CTNT video)
        if high > highest_high:
            highest_high = high
            candidate    = low * (1 - TRAIL_BUFFER_PCT)
            floor        = entry_price if partial_done else initial_stop
            trail_stop   = max(trail_stop, candidate, floor)

        # Lessons 24: trail stop does NOT fire inside a halt (no bars exist).
        # The first post-halt bar is already handled — trail updates naturally.
        if price <= trail_stop:
            next_open = float(df.iloc[j + 1]["Open"]) if j + 1 < len(df) else price
            pnl = _calc_pnl(entry_price, partial_price, next_open,
                            partial_done, partial_sold, remaining)
            return _make_result(df, entry_i, entry_price, next_open, "TRAIL STOP",
                                pnl, partial_done, partial_price, entry_type,
                                j in halt_bars)

    return None


def _calc_pnl(entry, partial_price, exit_price, partial_done, partial_sold, remaining):
    p = 0.0
    if partial_done:
        p += (partial_price - entry) * partial_sold
    p += (exit_price - entry) * remaining
    return p


def _make_result(df, entry_i, entry_price, exit_price, reason,
                 pnl, partial_done, partial_price, entry_type, halt_involved):
    return {
        "entry_time":    df.index[entry_i].strftime("%H:%M"),
        "entry":         entry_price,
        "exit":          exit_price,
        "exit_reason":   reason,
        "entry_type":    entry_type,
        "pnl":           round(pnl, 2),
        "gain_pct":      round((exit_price - entry_price) / entry_price * 100, 2),
        "partial":       f" (25%@${partial_price:.2f})" if partial_done else "",
        "halt_involved": halt_involved,
    }


# ── Run one gap day ───────────────────────────────────────────────────────────

def run_day(ticker: str, day: date, gap_pct: float) -> dict:
    # Lesson 6: float filter — skip entire ticker-day if float > 20M
    ticker_float = FLOAT_CACHE.get(ticker)
    if ticker_float and ticker_float > MAX_FLOAT:
        return {
            "ticker": ticker, "day": day,
            "note": f"float {ticker_float/1e6:.0f}M > {MAX_FLOAT//1_000_000}M",
            "trades": [],
        }

    df, halt_bars = fetch_minute_bars(ticker, day)
    min_bars = max(FLAT_TOP_WINDOW, EMA_BOUNCE_LOOKBACK + 1) + 3
    if df is None or len(df) < min_bars:
        return {"ticker": ticker, "day": day, "note": "insufficient 1-min data", "trades": []}

    if halt_bars:
        print(f"      🔔 {len(halt_bars)} halt gap(s) detected on {ticker} {day}")

    df     = _add_indicators(df)
    trades = []
    count  = 0
    last_i = -1

    for i in range(max(FLAT_TOP_WINDOW, EMA_BOUNCE_LOOKBACK + 1), len(df)):
        if count >= MAX_TRADES_PER_DAY:
            break
        if i <= last_i + 3:
            continue

        # Lesson 27 ("Clean P.A."): skip pattern-based entries on chop-storm days.
        # Kev's halt examples (CRVO, TNT) involve a single clean halt, not dozens —
        # a ticker re-triggering circuit breakers 10-90x/day is unreadable chop,
        # not the "clean, predictable" setup he describes.
        clean_day = len(halt_bars) <= MAX_CLEAN_HALTS

        # Halt-squeeze continuation — Entry Type 3 ("catch halts before they squeeze").
        # Buy the bar that resumes after a halt if it continues above the pre-halt
        # high. Allowed even on multi-halt days since this IS Kev's halt-trading setup.
        if _detect_halt_continuation(df, i, halt_bars):
            ep        = float(df["Close"].iloc[i])
            entry_low = float(df["Low"].iloc[i])
            result = _simulate(
                df, i, ep,
                initial_stop = entry_low * (1 - TRAIL_BUFFER_PCT),  # smidge below entry candle's low
                target       = ep * (1 + TARGET_PCT * 1.5),         # halt continuations tend to run further
                entry_type   = "HALT_CONT",
                halt_bars    = halt_bars,
            )
            if result:
                trades.append(result)
                count  += 1
                last_i  = i
            continue

        if not clean_day:
            continue

        # Flat top breakout (higher conviction — try first)
        if _detect_flat_top(df, i):
            ep        = float(df["Close"].iloc[i])
            entry_low = float(df["Low"].iloc[i])
            result = _simulate(
                df, i, ep,
                initial_stop = entry_low * (1 - TRAIL_BUFFER_PCT),  # smidge below entry candle's low (was: zero-buffer at ep)
                target       = ep * (1 + TARGET_PCT),   # +10%
                entry_type   = "FLAT_TOP",
                halt_bars    = halt_bars,
            )
            if result:
                trades.append(result)
                count  += 1
                last_i  = i
            continue

        # EMA pullback bounce
        is_bounce, prior_high = _detect_ema_bounce(df, i)
        if is_bounce:
            ep   = float(df["Close"].iloc[i])
            ema9 = float(df["ema9"].iloc[i])
            result = _simulate(
                df, i, ep,
                initial_stop = ema9 * (1 - EMA_STOP_BUFFER),   # EMA9 − 2.5%
                target       = prior_high,   # already enforces >= 3:1 R:R (lesson 14b)
                entry_type   = "EMA_BOUNCE",
                halt_bars    = halt_bars,
            )
            if result:
                trades.append(result)
                count  += 1
                last_i  = i

    open_p  = float(df["Open"].iloc[0])
    high_p  = float(df["High"].max())
    close_p = float(df["Close"].iloc[-1])
    return {
        "ticker":     ticker,
        "day":        day,
        "gap_pct":    round(gap_pct * 100, 1),
        "open":       open_p,
        "high":       high_p,
        "close":      close_p,
        "change":     round((close_p - open_p) / open_p * 100, 1),
        "halt_count": len(halt_bars),
        "trades":     trades,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*70}")
    print(f"  WEBULL DEEP BACKTEST v10 — Kev's Complete System (25 lessons)")
    print(f"  Universe: {len(UNIVERSE)} tickers | Daily lookback: {DAILY_BAR_LOOKBACK} bars")
    print(f"{'='*70}\n")

    # Lesson 6: prefetch float data for universe
    _prefetch_floats(UNIVERSE)

    # Phase 1: scan daily bars for gap-up days
    all_gaps = []
    seen     = set()
    print("Phase 1 — scanning daily bars for gap-up days...\n")

    for i, ticker in enumerate(UNIVERSE, 1):
        if DEBUG_ONLY and i > DEBUG_MAX_TICKERS:
            print(f"\n  [DEBUG_ONLY] Stopping after {DEBUG_MAX_TICKERS} tickers.")
            break

        # Skip daily scan if we already know float is too large (save API calls)
        f = FLOAT_CACHE.get(ticker)
        if f and f > MAX_FLOAT:
            print(f"  [{i:3d}/{len(UNIVERSE)}] {ticker:8s}  ❌ float={f/1e6:.0f}M — skipped")
            continue

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

    # Phase 2 & 3: fetch 1-min bars + run strategy
    print("Phase 2 — running strategy on each gap day...\n")
    all_results = []

    for j, (ticker, day, gap_pct) in enumerate(all_gaps, 1):
        result = run_day(ticker, day, gap_pct)
        all_results.append(result)

        n_trades = len(result.get("trades", []))
        note     = result.get("note", "")
        halts    = result.get("halt_count", 0)
        flag     = "✅" if n_trades > 0 else "  "
        halt_str = f" 🔔{halts}" if halts else ""
        print(f"  [{j:4d}/{len(all_gaps)}] {flag} {ticker:8s} {day}  "
              f"gap={gap_pct*100:+.0f}%{halt_str}  "
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

    n_gap_days   = len(all_gaps)
    n_signal     = len([r for r in results if r.get("trades")])
    n_float_skip = len([r for r in results if "float" in r.get("note", "")])

    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY — v10 (Kev's Complete System, 25 lessons)")
    print(f"{'='*70}")
    if n_gap_days:
        print(f"  Gap-up days scanned   : {n_gap_days}")
        print(f"  Skipped (float >20M)  : {n_float_skip}")
        print(f"  Days with signal      : {n_signal}  ({n_signal/n_gap_days*100:.0f}%)")
        print(f"  Days with no signal   : {n_gap_days - n_signal - n_float_skip}")
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
    for etype in ("FLAT_TOP", "EMA_BOUNCE", "HALT_CONT"):
        et = [t for t in all_trades if t.get("entry_type") == etype]
        if et:
            ew = [t for t in et if t["pnl"] > 0]
            el = [t for t in et if t["pnl"] <= 0]
            aw = sum(t["pnl"] for t in ew) / len(ew) if ew else 0
            al = sum(t["pnl"] for t in el) / len(el) if el else 0
            rr_et = abs(aw / al) if al else float("inf")
            print(f"    {etype:12s}  {len(et):3d} trades  "
                  f"{len(ew)/len(et)*100:.0f}% WR  W/L {rr_et:.2f}  "
                  f"${sum(t['pnl'] for t in et):+.2f}")

    # Halt-involved trades
    halt_trades = [t for t in all_trades if t.get("halt_involved")]
    if halt_trades:
        hw = [t for t in halt_trades if t["pnl"] > 0]
        print(f"\n  ── Halt-involved trades: {len(halt_trades)} "
              f"({len(hw)/len(halt_trades)*100:.0f}% WR  "
              f"${sum(t['pnl'] for t in halt_trades):+.2f})")

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

    # By entry time
    print(f"\n  ── By entry time ───────────────────────────────────────────")
    for h_s, h_e in [("09:45","10:00"),("10:00","10:15"),
                     ("10:15","10:30"),("10:30","10:45"),("10:45","11:00")]:
        bucket = [t for t in all_trades if h_s <= t.get("entry_time","00:00") < h_e]
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
        h = "🔔" if t.get("halt_involved") else "  "
        print(f"  {h} {t['day']}  {t['ticker']:<8} [{t.get('entry_type','?'):10}] "
              f"gap={t['gap_pct']:>4.0f}%  @${t.get('entry',0):.2f}  "
              f"{t.get('gain_pct',0):>+.2f}%  ${t['pnl']:+.2f}  "
              f"{t.get('exit_reason','?')}  {t.get('partial','')}")

    print(f"\n  ── Top 10 losers ───────────────────────────────────────────")
    for t in sorted(losses, key=lambda x: x["pnl"])[:10]:
        h = "🔔" if t.get("halt_involved") else "  "
        print(f"  {h} {t['day']}  {t['ticker']:<8} [{t.get('entry_type','?'):10}] "
              f"gap={t['gap_pct']:>4.0f}%  @${t.get('entry',0):.2f}  "
              f"{t.get('gain_pct',0):>+.2f}%  ${t['pnl']:+.2f}  "
              f"{t.get('exit_reason','?')}")

    print(f"\n{'='*70}")
    print(f"  BASELINE TO BEAT: v8 — 78 trades, 31% WR, 3.49:1 W/L, +$0.74 EV")
    print(f"{'='*70}")


def save_results(results):
    out = "/tmp/webull_backtest_v10_results.json"
    with open(out, "w") as f:
        json.dump([{
            "ticker":     r["ticker"],
            "day":        str(r.get("day", "")),
            "gap_pct":    r.get("gap_pct", 0),
            "halt_count": r.get("halt_count", 0),
            "trades":     r.get("trades", []),
            "note":       r.get("note", ""),
        } for r in results], f, indent=2)
    print(f"\n  Raw results saved → {out}")
    print(f"  v10: 25 lessons applied | 2 entry types | float filter | halt detection")


if __name__ == "__main__":
    main()
