#!/usr/bin/env python3
"""
Webull Deep Historical Backtest — v6
=====================================
v5 results: 27 trades, 33% WR (9W/18L), 2.50:1 W/L, EV = +$0.37/trade.
First positive EV version. Two issues to address:
  1. +10% partial target NEVER triggered across 67+ trades — avg winner ~5.5%
     so +10% is too far; lower to +5% so partial exit actually fires
  2. Flat top window 8 bars may be too loose; tighten to 12 bars for stronger
     consolidation level (more proven resistance = higher-quality breakout)

Two changes from v5:
  1. TARGET_PCT: 0.10 → 0.05  (partial exit at +5% instead of +10%)
  2. FLAT_TOP_WINDOW: 8 → 12   (tighter consolidation = stronger signal)

How it works:
  1. Fetch daily bars (up to 400 = ~1.5 years) per ticker
  2. Find all gap-up days (15-30%) in that history
  3. For each qualifying gap day, fetch 1-min bars via start_time/end_time
  4. Run flat top breakout + EMA9 stop strategy on each day
  5. Report full results with statistical breakdown
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

# ── Credentials (from env, same as the bot) ──────────────────────────────────
WEBULL_APP_KEY      = os.environ.get("WEBULL_APP_KEY", "")
WEBULL_APP_SECRET   = os.environ.get("WEBULL_APP_SECRET", "")
WEBULL_ACCESS_TOKEN = os.environ.get("WEBULL_ACCESS_TOKEN", "")
WEBULL_TOKEN_DIR    = "/tmp/webull_token"
TRADING_HOST        = "api.webull.com"

if not WEBULL_APP_KEY or not WEBULL_ACCESS_TOKEN:
    print("❌  Missing credentials. Set WEBULL_APP_KEY + WEBULL_APP_SECRET + WEBULL_ACCESS_TOKEN")
    sys.exit(1)

# Write token file the same way the bot does
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
FLAT_TOP_WINDOW    = 12
FLAT_TOP_MAX_RANGE = 0.050  # <5.0% high-to-low range (v1=5%, v3=3.5%)
EMA_CONFIRM_BARS   = 2      # bars below EMA9 required before stop fires
MIN_ABS_VOL        = 10_000
EMA_PERIOD         = 9
TIME_CUTOFF        = "10:00"
MIN_PRICE          = 1.50
MIN_GAP_PCT        = 0.15
MAX_GAP_PCT        = 0.30   # was 0.60 — 30-60% bucket had 0% WR in v1
POSITION_DOLLARS   = 100.00
TARGET_PCT         = 0.05
VWAP_REQUIRED      = True
MAX_TRADES_PER_DAY = 2
DAILY_BAR_LOOKBACK = 400     # trading days to scan; 400 ≈ 1.5 years
RATE_LIMIT_SLEEP   = 0.3     # seconds between API calls to avoid throttling
DEBUG_ONLY         = os.environ.get("DEBUG_ONLY", "0") in ("1", "true", "yes")
DEBUG_MAX_TICKERS  = 5       # when DEBUG_ONLY=1, stop after this many tickers


# ── Ticker universe (same as stress_test.py) ─────────────────────────────────
UNIVERSE = [
    # Active small-cap/micro-cap momentum stocks (verified tradeable)
    # These are real names that Webull knows about
    "TLRY","SNDL","NKLA","CENN","MULN","IDEX","FFIE","BTBT","SONN",
    "HYMC","OCUP","OPFI","ROIV","RCKT","QBTS","PYPL","SUPN","STEM",
    "SKYX","SUNW","SURF","SDIG","LTBR","ORPH","PLRX","PGEN","PHVS",
    "RNAZ","RPID","RBBN","RPRX","RSLS","RUBY","RZLT",
    # From Kev's videos — may be delisted but worth trying
    "MTEK","CREG","GXAI","MDJH","MGOL","MEGI","BFRI","KTTA",
    "ACST","ATNF","BIOR","BZFD","CIFS","CRKN","DARE","DPRO","EPAZ",
    "IMPP","IPDN","KAVL","LGMK","LKCO","MITI","MKUL","MNPR",
    "NCPL","NKGN","NOVV","NVNI","NXGL","OXBR","PBLA","PESI",
    "PRPH","PRVB","PULM","RZLT","SAMA","SCNX","SGLB","SGLY",
    "SIGL","SING","SISI","SOBR","SPRB","SPRC","SPRO","SRTX",
    "STAF","STGS","STIX","STOK","STRM","SUMR","SUNL","SURG",
    "SWAG","SXTC","SYRA","SYTA","TCON","TGLS","TPVG","TRDA",
    "TRIB","TSHA","TTAM","TVTX","TWST","TXMD","TYRA",
    # Known active small-cap gap runners
    "SOUN","GFAI","RCAT","HITI","APWC","PAVS","BRTX","SBEV","RLAY",
    "DBGI","ADTX","WHLR","CLRB","CMND","GOVX","PHGE","IINN","ZJYL",
    "LPRO","HCWB","TDTH","AHMA","RGNT","CAST","GRNQ","MNTS",
    "ATPC","LASE","CDT","ARTL","TPET","STAK","BIAF","MNDR",
    "GLXG","PPCB","WTO","SER",
]
UNIVERSE = list(dict.fromkeys(UNIVERSE))  # deduplicate


# ── Webull bar helpers ────────────────────────────────────────────────────────

_debug_printed = False

def _parse_bars(resp) -> list:
    """Extract list of bars from a Webull API response."""
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

    # First time we get bars, dump one so we can see the actual field names
    if bars and not _debug_printed:
        _debug_printed = True
        print(f"\n  [DEBUG] Raw bar keys: {list(bars[0].keys())}")
        print(f"  [DEBUG] Sample bar:   {bars[0]}\n")

    return bars


def _bar_val(bar: dict, *keys):
    """Get first non-None, non-zero value from bar dict trying each key."""
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
    """Extract the bar's timestamp in milliseconds. Handles both int-ms and ISO strings."""
    for k in ("timestamp", "time", "t", "ts", "beginTime", "begin_time",
              "open_time", "openTime", "startTime", "start_time"):
        v = bar.get(k)
        if v is None:
            continue
        # Try integer milliseconds first
        try:
            return int(v)
        except (TypeError, ValueError):
            pass
        # Try ISO string e.g. '2026-06-18T04:00:00.000+0000'
        if isinstance(v, str):
            try:
                from datetime import datetime as _dt
                # Normalize +0000 → +00:00 for fromisoformat
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
    """Convert milliseconds UTC timestamp to ET datetime."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(ET)


def _day_start_ms(d: date) -> int:
    """9:30 AM ET on date d in milliseconds UTC."""
    dt = ET.localize(datetime(d.year, d.month, d.day, 9, 30, 0))
    return int(dt.timestamp() * 1000)


def _day_end_ms(d: date) -> int:
    """4:00 PM ET on date d in milliseconds UTC."""
    dt = ET.localize(datetime(d.year, d.month, d.day, 16, 0, 0))
    return int(dt.timestamp() * 1000)


# ── Phase 1: fetch daily bars ─────────────────────────────────────────────────

def fetch_daily_bars(ticker: str) -> list:
    """Return list of daily OHLCV bars ordered oldest→newest."""
    try:
        resp = dc.market_data.get_history_bar(
            symbol=ticker,
            category="US_STOCK",
            timespan="D",
            count=str(DAILY_BAR_LOOKBACK),
        )
        bars = _parse_bars(resp)
        return bars
    except Exception as e:
        print(f"    ⚠  daily bars error for {ticker}: {e}")
        return []


def find_gap_days(ticker: str, bars: list) -> list:
    """
    Given daily bars, find all (date, gap_pct) where open gapped up 15–60%
    vs prior close.  Returns list of (date, open_price, prior_close, gap_pct).
    """
    results = []
    if len(bars) < 2:
        return results

    # Detect bar ordering — some APIs return newest-first
    ts_first = _bar_ts_ms(bars[0])
    ts_last  = _bar_ts_ms(bars[-1])
    if ts_first and ts_last and ts_first > ts_last:
        bars = list(reversed(bars))  # ensure oldest→newest

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

        # Determine the date of this bar
        ts = _bar_ts_ms(cur)
        if ts:
            bar_date = _ms_to_et(ts).date()
        else:
            # Try a "date" field directly
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


# ── Phase 2: fetch 1-min bars for a specific day ──────────────────────────────

def fetch_minute_bars(ticker: str, day: date) -> pd.DataFrame:
    """Fetch 1-min RTH bars for ticker on day. Returns a DataFrame."""
    try:
        resp = dc.market_data.get_history_bar(
            symbol=ticker,
            category="US_STOCK",
            timespan="M1",
            count="500",          # 390 bars = 1 full trading day, 500 gives headroom
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

        # Keep only regular trading hours
        df = df.between_time("09:30", "15:59")
        return df

    except Exception as e:
        print(f"    ⚠  minute bars error {ticker} {day}: {e}")
        return pd.DataFrame()


# ── Phase 3: strategy logic (mirrors backtest_v2.py exactly) ─────────────────

def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["tp"]   = (df["High"] + df["Low"] + df["Close"]) / 3
    df["vwap"] = (df["tp"] * df["Volume"]).cumsum() / df["Volume"].cumsum()
    df["ema9"] = df["Close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    return df


def _detect_flat_top(df: pd.DataFrame, i: int) -> bool:
    if i < FLAT_TOP_WINDOW:
        return False
    t_str = df.index[i].strftime("%H:%M")
    if t_str >= TIME_CUTOFF:
        return False
    price = float(df["Close"].iloc[i])
    vwap  = float(df["vwap"].iloc[i])
    vol   = float(df["Volume"].iloc[i])
    if price < MIN_PRICE:
        return False
    if VWAP_REQUIRED and price <= vwap:
        return False
    window  = df.iloc[i - FLAT_TOP_WINDOW : i]
    w_high  = float(window["High"].max())
    w_low   = float(window["Low"].min())
    if w_low <= 0:
        return False
    if (w_high - w_low) / w_low > FLAT_TOP_MAX_RANGE:
        return False
    if price <= w_high:
        return False
    if vol < MIN_ABS_VOL:
        return False
    # Volume spike: breakout bar must be busier than the consolidation avg
    return True


def _simulate(df: pd.DataFrame, entry_i: int, entry_price: float):
    shares         = POSITION_DOLLARS / entry_price
    target         = entry_price * (1 + TARGET_PCT)
    half_done      = False
    half_price     = 0.0
    remaining      = shares
    bars_below_ema = 0

    for j in range(entry_i + 1, len(df)):
        row   = df.iloc[j]
        price = float(row["Close"])
        ema9  = float(row["ema9"])
        t_str = df.index[j].strftime("%H:%M")
        last  = (j == len(df) - 1) or t_str >= "15:30"

        if last:
            pnl = _pnl(entry_price, half_price, price, shares, half_done, remaining)
            return _result(df, entry_i, entry_price, price, "TIME", pnl, shares, half_done, half_price)

        if not half_done and price >= target:
            half_price = price
            half_done  = True
            remaining  = shares / 2

        if price < ema9:
            bars_below_ema += 1
        else:
            bars_below_ema = 0

        if bars_below_ema >= EMA_CONFIRM_BARS:
            next_open = float(df.iloc[j + 1]["Open"]) if j + 1 < len(df) else price
            pnl = _pnl(entry_price, half_price, next_open, shares, half_done, remaining)
            return _result(df, entry_i, entry_price, next_open, "EMA STOP 2BAR", pnl, shares, half_done, half_price)

    return None


def _pnl(entry, half_price, exit_price, shares, half_done, remaining):
    p = 0.0
    if half_done:
        p += (half_price - entry) * (shares / 2)
    p += (exit_price - entry) * remaining
    return p


def _result(df, entry_i, entry_price, exit_price, reason, pnl, shares, half_done, half_price):
    partial = f" (half @${half_price:.2f})" if half_done else ""
    return {
        "entry_time":  df.index[entry_i].strftime("%H:%M"),
        "entry":       entry_price,
        "exit":        exit_price,
        "exit_reason": reason,
        "pnl":         round(pnl, 2),
        "gain_pct":    round((exit_price - entry_price) / entry_price * 100, 2),
        "partial":     partial,
    }


def run_day(ticker: str, day: date, gap_pct: float) -> dict:
    df = fetch_minute_bars(ticker, day)
    if df is None or len(df) < FLAT_TOP_WINDOW + 3:
        return {"ticker": ticker, "day": day, "note": "insufficient 1-min data", "trades": []}

    df = _add_indicators(df)
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
        "ticker":   ticker,
        "day":      day,
        "gap_pct":  round(gap_pct * 100, 1),
        "open":     open_p,
        "high":     high_p,
        "close":    close_p,
        "change":   round((close_p - open_p) / open_p * 100, 1),
        "trades":   trades,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*70}")
    print(f"  WEBULL DEEP BACKTEST v6 — Flat Top Breakout + EMA9 Stop (2-bar confirm)")
    print(f"  Universe: {len(UNIVERSE)} tickers | Daily lookback: {DAILY_BAR_LOOKBACK} bars")
    print(f"  Gap filter: {MIN_GAP_PCT*100:.0f}%–{MAX_GAP_PCT*100:.0f}% | "
          f"Flat top: {FLAT_TOP_WINDOW} bars <{FLAT_TOP_MAX_RANGE*100:.1f}% | "
          f"No vol filter | EMA stop: {EMA_CONFIRM_BARS}-bar confirm | Partial exit: +{TARGET_PCT*100:.0f}%")
    print(f"{'='*70}\n")

    # ── Phase 1: scan daily bars for all gap days ─────────────────────────────
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
                  f"({oldest} → {newest})  {len(gaps):3d} gap days found")
        else:
            print(f"  [{i:3d}/{len(UNIVERSE)}] {ticker:8s}  {len(daily):4d} daily bars  "
                  f"0 gap days")

        time.sleep(RATE_LIMIT_SLEEP)

    all_gaps.sort(key=lambda x: x[1])   # sort by date

    print(f"\n{'─'*70}")
    print(f"Total qualifying gap days: {len(all_gaps)}")
    if all_gaps:
        print(f"Date range: {all_gaps[0][1]} → {all_gaps[-1][1]}")
    print(f"{'─'*70}\n")

    if not all_gaps:
        print("No gap days found. Check credentials and ticker list.")
        return

    # ── Phase 2 & 3: fetch 1-min bars + run strategy ──────────────────────────
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

    # ── Reporting ─────────────────────────────────────────────────────────────
    print_report(all_results, all_gaps)
    save_results(all_results)


def print_report(results, all_gaps):
    all_trades = []
    for r in results:
        for t in r.get("trades", []):
            all_trades.append({**t, "ticker": r["ticker"], "day": r["day"],
                                "gap_pct": r.get("gap_pct", 0)})

    n_gap_days = len(all_gaps)
    n_signal   = len([r for r in results if r.get("trades")])
    no_signal  = n_gap_days - n_signal

    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"  Gap-up days scanned   : {n_gap_days}")
    print(f"  Days with signal      : {n_signal}  ({n_signal/n_gap_days*100:.0f}%)")
    print(f"  Days with no signal   : {no_signal}  ({no_signal/n_gap_days*100:.0f}%)")
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

    # By gap bucket
    print(f"\n  By gap % bucket:")
    for lo, hi in [(15, 30), (30, 45), (45, 60)]:
        bucket = [t for t in all_trades if lo <= t["gap_pct"] < hi]
        if bucket:
            bw = [t for t in bucket if t["pnl"] > 0]
            print(f"    {lo}-{hi}%  {len(bucket):3d} trades  "
                  f"{len(bw)/len(bucket)*100:.0f}% WR  "
                  f"${sum(t['pnl'] for t in bucket):+.2f}")

    # By exit reason
    print(f"\n  By exit reason:")
    by_reason = {}
    for t in all_trades:
        by_reason.setdefault(t["exit_reason"], []).append(t)
    for r, ts in sorted(by_reason.items()):
        w = len([t for t in ts if t["pnl"] > 0])
        print(f"    {r:14s}  {len(ts):3d} trades  {w/len(ts)*100:.0f}% WR  "
              f"${sum(t['pnl'] for t in ts):+.2f}")

    # By year
    print(f"\n  By year:")
    by_year = {}
    for t in all_trades:
        y = str(t["day"].year) if isinstance(t["day"], date) else str(t["day"])[:4]
        by_year.setdefault(y, []).append(t)
    for y in sorted(by_year):
        ts = by_year[y]
        w  = len([t for t in ts if t["pnl"] > 0])
        print(f"    {y}  {len(ts):3d} trades  {w/len(ts)*100:.0f}% WR  "
              f"${sum(t['pnl'] for t in ts):+.2f}")

    print(f"{'='*70}")


def save_results(results):
    out = "/tmp/webull_backtest_v6_results.json"
    with open(out, "w") as f:
        json.dump([{
            "ticker":   r["ticker"],
            "day":      str(r.get("day", "")),
            "gap_pct":  r.get("gap_pct", 0),
            "trades":   r.get("trades", []),
            "note":     r.get("note", ""),
        } for r in results], f, indent=2)
    print(f"\n  Raw results saved → {out}")
    print(f"  (v6: flat top <5.0% 12-bar window, gap 15-30%, no vol filter, EMA9 {EMA_CONFIRM_BARS}-bar confirm, partial +{TARGET_PCT*100:.0f}%)")


if __name__ == "__main__":
    main()
