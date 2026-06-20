#!/usr/bin/env python3
"""
Webull Deep Historical Backtest — v10 (Kev's Full System)
==========================================================
v8 confirmed leader: 78 trades, 31% WR, 3.49:1 W/L, +$0.74 EV. v9 result unknown.

v10 applies every lesson learned from @momentum.official (Kev's TikTok):

  ENTRY FILTERS (new):
    1. START_TIME "09:45" — no entries in first 15 min (Kev: "let things settle")
    2. EMA9 > EMA20 required at entry — A+ Setup: bullish EMA stack
    3. Quality gate: last bar of window must be within 3% of window high
       (price consolidating near resistance, not fading from it = good pullback)

  EXIT SYSTEM (new):
    4. Trailing stop: stop trails "a smidge below" (1.5%) each new HIGH bar's low.
       Floor rule: stop never drops below entry price.
       Exit fires when close crosses below trail_stop. (replaces 2-bar EMA9 stop)
    5. Overextension exit: price > EMA9 * 1.08 → sell (approximates red down arrows).
       Only arms after 3 bars post-entry so we don't exit a legitimate breakout.
    6. Partial exit: 25% of position at +10% (was 50% in v9). Kev: "a quarter."
       Remaining 75% runs on trail stop or overextension.

  FILTERS UNCHANGED from v9:
    - Flat top breakout: 8-bar consolidation window, <5% range, price breaks above
    - Above VWAP at entry
    - Gap 15–30%
    - Min price $1.50
    - TIME_CUTOFF 11:00 AM

  NOT IMPLEMENTED (requires data not in Webull bar API):
    - Float < 20M filter (our universe is pre-filtered to small/micro-cap)
    - Halt detection (halted candles appear as gaps in 1-min data)
    - Circuit breaker halt-up setup (needs halt scanner feed)
"""

import os
import sys
import time
import pathlib
import json
from datetime import datetime, date, timedelta, timezone

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

# Entry timing
START_TIME         = "09:45"    # NEW: no entries before 9:45 AM (let things settle)
TIME_CUTOFF        = "11:00"    # no entries after 11:00 AM (Kev's window)

# EMA periods — confirmed from Kev's A+ checklist video
EMA_SHORT          = 9
EMA_LONG           = 20

# Flat top detection (unchanged from v9)
FLAT_TOP_WINDOW    = 8
FLAT_TOP_MAX_RANGE = 0.050      # <5.0% high-to-low range in consolidation window

# Quality gate: last bar of window must be within X% of window's max high
# Ensures price is still near resistance when breakout fires (not already fading)
WINDOW_TOP_GATE    = 0.03       # 3%

# Exit parameters
TRAIL_BUFFER_PCT   = 0.015      # stop = bar_low * (1 - 0.015) = "a smidge below"
OVEREXT_MULT       = 1.08       # price > ema9 * 1.08 → overextension exit (red arrows)
OVEREXT_MIN_BARS   = 3          # arms overextension check after this many bars post-entry
PARTIAL_PCT        = 0.25       # sell 25% of shares at first target (Kev: "a quarter")
TARGET_PCT         = 0.10       # +10% = first partial exit target

# Other filters
MIN_ABS_VOL        = 10_000
MIN_PRICE          = 1.50
MIN_GAP_PCT        = 0.15
MAX_GAP_PCT        = 0.30
POSITION_DOLLARS   = 100.00
VWAP_REQUIRED      = True
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


# ── Webull bar helpers (unchanged from v9) ────────────────────────────────────

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
                if "." in s:
                    fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
                else:
                    fmt = "%Y-%m-%dT%H:%M:%S%z"
                dt = _dt.strptime(s, fmt)
                return int(dt.timestamp() * 1000)
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
            symbol=ticker,
            category="US_STOCK",
            timespan="D",
            count=str(DAILY_BAR_LOOKBACK),
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
        cur  = bars[i]
        prev = bars[i - 1]
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
            if d_raw:
                try:
                    bar_date = date.fromisoformat(str(d_raw)[:10])
                except ValueError:
                    continue
            else:
                continue
        results.append((bar_date, open_p, close_p, gap))
    return results


# ── Phase 2: 1-min bars ───────────────────────────────────────────────────────

def fetch_minute_bars(ticker: str, day: date) -> pd.DataFrame:
    try:
        resp = dc.market_data.get_history_bar(
            symbol=ticker,
            category="US_STOCK",
            timespan="M1",
            count="500",
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
            dt = _ms_to_et(ts)
            rows.append({
                "datetime": dt,
                "Open":     _bar_val(b, "open",   "o"),
                "High":     _bar_val(b, "high",   "h"),
                "Low":      _bar_val(b, "low",    "l"),
                "Close":    _bar_val(b, "close",  "c"),
                "Volume":   _bar_val(b, "volume", "v"),
            })
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).set_index("datetime")
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)
        df = df.between_time("09:30", "15:59")
        return df
    except Exception as e:
        print(f"    ⚠  minute bars error {ticker} {day}: {e}")
        return pd.DataFrame()


# ── Phase 3: strategy ─────────────────────────────────────────────────────────

def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["tp"]    = (df["High"] + df["Low"] + df["Close"]) / 3
    df["vwap"]  = (df["tp"] * df["Volume"]).cumsum() / df["Volume"].cumsum()
    df["ema9"]  = df["Close"].ewm(span=EMA_SHORT, adjust=False).mean()  # fast
    df["ema20"] = df["Close"].ewm(span=EMA_LONG,  adjust=False).mean()  # slow
    return df


def _detect_flat_top(df: pd.DataFrame, i: int) -> bool:
    if i < FLAT_TOP_WINDOW:
        return False

    t_str = df.index[i].strftime("%H:%M")
    if t_str < START_TIME or t_str >= TIME_CUTOFF:  # NEW: enforce 09:45 start
        return False

    price = float(df["Close"].iloc[i])
    vwap  = float(df["vwap"].iloc[i])
    ema9  = float(df["ema9"].iloc[i])
    ema20 = float(df["ema20"].iloc[i])
    vol   = float(df["Volume"].iloc[i])

    if price < MIN_PRICE:
        return False
    if VWAP_REQUIRED and price <= vwap:
        return False
    if ema9 <= ema20:       # NEW: A+ Setup requires 9 EMA > 20 EMA (bullish stack)
        return False

    window = df.iloc[i - FLAT_TOP_WINDOW : i]
    w_high = float(window["High"].max())
    w_low  = float(window["Low"].min())

    if w_low <= 0:
        return False
    if (w_high - w_low) / w_low > FLAT_TOP_MAX_RANGE:
        return False
    if price <= w_high:
        return False
    if vol < MIN_ABS_VOL:
        return False

    # NEW: quality gate — last bar in window must be near the top of the range.
    # If price faded significantly before the "breakout", it's a bad setup.
    last_high = float(window["High"].iloc[-1])
    if last_high < w_high * (1 - WINDOW_TOP_GATE):
        return False

    return True


def _simulate(df: pd.DataFrame, entry_i: int, entry_price: float) -> dict | None:
    shares        = POSITION_DOLLARS / entry_price
    target        = entry_price * (1 + TARGET_PCT)
    partial_done  = False
    partial_price = 0.0
    partial_sold  = shares * PARTIAL_PCT   # 25% sold at target
    remaining     = shares                 # starts at 100%, drops to 75% after partial

    # Trailing stop: starts at entry price (floor rule — never below entry)
    trail_stop    = entry_price
    highest_high  = entry_price            # track new highs to know when to trail

    for j in range(entry_i + 1, len(df)):
        row   = df.iloc[j]
        price = float(row["Close"])
        high  = float(row["High"])
        low   = float(row["Low"])
        ema9  = float(row["ema9"])
        t_str = df.index[j].strftime("%H:%M")
        last  = (j == len(df) - 1) or t_str >= "15:30"

        if last:
            pnl = _calc_pnl(entry_price, partial_price, price, shares,
                            partial_done, partial_sold, remaining)
            return _make_result(df, entry_i, entry_price, price, "TIME",
                                pnl, shares, partial_done, partial_price)

        # Partial exit: sell 25% at +10%
        if not partial_done and price >= target:
            partial_price = price
            partial_done  = True
            remaining     = shares - partial_sold   # 75% left

        # Overextension exit: price extended too far above EMA9 (red down arrows)
        # Only arms after OVEREXT_MIN_BARS bars so we don't exit a legitimate breakout.
        bars_in = j - entry_i
        if bars_in >= OVEREXT_MIN_BARS and ema9 > 0 and price > ema9 * OVEREXT_MULT:
            pnl = _calc_pnl(entry_price, partial_price, price, shares,
                            partial_done, partial_sold, remaining)
            return _make_result(df, entry_i, entry_price, price, "OVEREXT",
                                pnl, shares, partial_done, partial_price)

        # Update trailing stop: trail below each NEW high bar's low (not every bar).
        # Floor: stop never goes below entry price.
        if high > highest_high:
            highest_high  = high
            new_stop = low * (1 - TRAIL_BUFFER_PCT)
            trail_stop = max(trail_stop, new_stop)

        # Exit when close crosses below the trailing stop
        if price <= trail_stop:
            next_open = float(df.iloc[j + 1]["Open"]) if j + 1 < len(df) else price
            pnl = _calc_pnl(entry_price, partial_price, next_open, shares,
                            partial_done, partial_sold, remaining)
            return _make_result(df, entry_i, entry_price, next_open, "TRAIL STOP",
                                pnl, shares, partial_done, partial_price)

    return None


def _calc_pnl(entry, partial_price, exit_price, shares,
              partial_done, partial_sold, remaining):
    p = 0.0
    if partial_done:
        p += (partial_price - entry) * partial_sold
    p += (exit_price - entry) * remaining
    return p


def _make_result(df, entry_i, entry_price, exit_price, reason,
                 pnl, shares, partial_done, partial_price):
    partial_str = f" (25%@${partial_price:.2f})" if partial_done else ""
    return {
        "entry_time":  df.index[entry_i].strftime("%H:%M"),
        "entry":       entry_price,
        "exit":        exit_price,
        "exit_reason": reason,
        "pnl":         round(pnl, 2),
        "gain_pct":    round((exit_price - entry_price) / entry_price * 100, 2),
        "partial":     partial_str,
    }


def run_day(ticker: str, day: date, gap_pct: float) -> dict:
    df = fetch_minute_bars(ticker, day)
    if df is None or len(df) < FLAT_TOP_WINDOW + 3:
        return {"ticker": ticker, "day": day, "note": "insufficient 1-min data", "trades": []}

    df     = _add_indicators(df)
    trades = []
    count  = 0
    last_i = -1

    for i in range(FLAT_TOP_WINDOW, len(df)):
        if count >= MAX_TRADES_PER_DAY:
            break
        if i <= last_i + 3:
            continue
        if _detect_flat_top(df, i):
            ep     = float(df["Close"].iloc[i])
            result = _simulate(df, i, ep)
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
    print(f"  WEBULL DEEP BACKTEST v10 — Kev's Full System")
    print(f"  Universe: {len(UNIVERSE)} tickers | Daily lookback: {DAILY_BAR_LOOKBACK} bars")
    print(f"  Entry: {START_TIME}–{TIME_CUTOFF} | Above VWAP | EMA9>EMA20 | Flat top <{FLAT_TOP_MAX_RANGE*100:.0f}% {FLAT_TOP_WINDOW}-bar")
    print(f"  Exit: Trail stop {TRAIL_BUFFER_PCT*100:.1f}%/new-high | Overext EMA9x{OVEREXT_MULT} (>{OVEREXT_MIN_BARS}bars)")
    print(f"  Partial: {int(PARTIAL_PCT*100)}% at +{TARGET_PCT*100:.0f}% | Gap {MIN_GAP_PCT*100:.0f}%–{MAX_GAP_PCT*100:.0f}%")
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


def print_report(results, all_gaps):
    all_trades = []
    for r in results:
        for t in r.get("trades", []):
            y = r["day"].year if isinstance(r["day"], date) else int(str(r["day"])[:4])
            all_trades.append({**t, "ticker": r["ticker"], "day": r["day"],
                                "gap_pct": r.get("gap_pct", 0), "year": str(y)})

    n_gap_days = len(all_gaps)
    n_signal   = len([r for r in results if r.get("trades")])

    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY — v10 (Kev's Full System)")
    print(f"{'='*70}")
    print(f"  Gap-up days scanned   : {n_gap_days}")
    print(f"  Days with signal      : {n_signal}  ({n_signal/n_gap_days*100:.0f}%)" if n_gap_days else "")
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

    # By exit reason
    print(f"\n  By exit reason:")
    by_reason = {}
    for t in all_trades:
        by_reason.setdefault(t["exit_reason"], []).append(t)
    for reason, ts in sorted(by_reason.items()):
        w = len([t for t in ts if t["pnl"] > 0])
        print(f"    {reason:14s}  {len(ts):3d} trades  {w/len(ts)*100:.0f}% WR  "
              f"${sum(t['pnl'] for t in ts):+.2f}")

    # By year
    print(f"\n  By year:")
    by_year = {}
    for t in all_trades:
        by_year.setdefault(t["year"], []).append(t)
    for y in sorted(by_year):
        ts = by_year[y]
        w  = len([t for t in ts if t["pnl"] > 0])
        print(f"    {y}  {len(ts):3d} trades  {w/len(ts)*100:.0f}% WR  "
              f"${sum(t['pnl'] for t in ts):+.2f}")

    # By gap bucket
    print(f"\n  By gap % bucket:")
    for lo, hi in [(15, 20), (20, 25), (25, 30)]:
        bucket = [t for t in all_trades if lo <= t["gap_pct"] < hi]
        if bucket:
            bw = [t for t in bucket if t["pnl"] > 0]
            print(f"    {lo}-{hi}%  {len(bucket):3d} trades  "
                  f"{len(bw)/len(bucket)*100:.0f}% WR  "
                  f"${sum(t['pnl'] for t in bucket):+.2f}")

    # Entry time distribution
    print(f"\n  By entry time bucket:")
    for h_start, h_end in [("09:45", "10:00"), ("10:00", "10:15"),
                             ("10:15", "10:30"), ("10:30", "10:45"),
                             ("10:45", "11:00")]:
        bucket = [t for t in all_trades
                  if h_start <= t.get("entry_time", "00:00") < h_end]
        if bucket:
            bw = [t for t in bucket if t["pnl"] > 0]
            print(f"    {h_start}–{h_end}  {len(bucket):3d} trades  "
                  f"{len(bw)/len(bucket)*100:.0f}% WR  "
                  f"${sum(t['pnl'] for t in bucket):+.2f}")

    # Partial exit stats
    partials = [t for t in all_trades if t.get("partial")]
    print(f"\n  Partial exit (25% at +10%) fired: {len(partials)}/{len(all_trades)} trades "
          f"({len(partials)/len(all_trades)*100:.0f}%)")

    # Top winners / losers
    print(f"\n  Top 10 winners:")
    for t in sorted(wins, key=lambda x: -x["pnl"])[:10]:
        print(f"    {t['day']}  {t['ticker']:<8} gap={t['gap_pct']:>4.0f}%  "
              f"entry=${t.get('entry',0):.2f}  gain={t.get('gain_pct',0):>+.2f}%  "
              f"pnl=${t['pnl']:+.2f}  {t.get('exit_reason','?')}  {t.get('partial','')}")
    print(f"\n  Top 10 losers:")
    for t in sorted(losses, key=lambda x: x["pnl"])[:10]:
        print(f"    {t['day']}  {t['ticker']:<8} gap={t['gap_pct']:>4.0f}%  "
              f"entry=${t.get('entry',0):.2f}  gain={t.get('gain_pct',0):>+.2f}%  "
              f"pnl=${t['pnl']:+.2f}  {t.get('exit_reason','?')}")

    print(f"\n{'='*70}")
    print(f"  v8 confirmed leader: 78 trades, 31% WR, 3.49:1 W/L, +$0.74 EV")
    print(f"  (v9 result unknown — v8 is the baseline to beat)")
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
    print(f"  (v10: Kev's full system — EMA9>20 gate, 09:45 start, trail stop, overext exit, 25% partial)")


if __name__ == "__main__":
    main()
