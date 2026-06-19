#!/usr/bin/env python3
"""
Webull Deep Historical Backtest
================================
Stress-tests the Kev flat top breakout strategy using Webull's own
API instead of yfinance (which is capped at 30 days of 1-min data).

How it works:
  1. Fetch daily bars (up to 1200 days = ~5 years) per ticker
  2. Find all gap-up days (15–60%) in that history
  3. For each qualifying gap day, fetch 1-min bars via start_time/end_time
  4. Run flat top breakout + EMA9 stop strategy on each day
  5. Report full results with statistical breakdown

Usage:
  Set env vars from Railway dashboard, then run:
    WEBULL_APP_KEY=xxx WEBULL_APP_SECRET=xxx WEBULL_ACCESS_TOKEN=xxx \\
    python3 webull_backtest.py

  Or on Railway: set START_APP=webull_backtest.py and deploy.
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
FLAT_TOP_WINDOW    = 8
FLAT_TOP_MAX_RANGE = 0.05   # <5% high-to-low range in consolidation window
MIN_ABS_VOL        = 10_000
EMA_PERIOD         = 9
TIME_CUTOFF        = "10:00"
MIN_PRICE          = 1.50
MIN_GAP_PCT        = 0.15
MAX_GAP_PCT        = 0.60
POSITION_DOLLARS   = 100.00
TARGET_PCT         = 0.10
VWAP_REQUIRED      = True
MAX_TRADES_PER_DAY = 2
DAILY_BAR_LOOKBACK = 400     # trading days to scan; 400 ≈ 1.5 years
RATE_LIMIT_SLEEP   = 0.3     # seconds between API calls to avoid throttling


# ── Ticker universe (same as stress_test.py) ─────────────────────────────────
UNIVERSE = [
    # From previous backtests — known momentum names
    "ATPC","LASE","ASNS","CDT","ARTL","TPET","STAK","BIAF","MNDR","GRNQ",
    "TDTH","CAST","AHMA","RGNT","CMND","GOVX","PHGE","MNTS","IINN","ZJYL",
    "RCAT","HCWB","LPRO","HITI","APWC","GFAI","PAVS","BRTX","SBEV","RLAY",
    "DBGI","ADTX","WHLR","CLRB",
    # Common small-cap momentum names
    "MDJH","MGOL","MEGI","BFRI","NKLA","CENN","MULN","IDEX","PEGY",
    "RELI","GMVD","GPUS","MFON","AEYE","CODA","PRTY","MEGL",
    "KTTA","HYMC","ACST","ATNF","BIOR","BTBT","BZFD","CIFS","CRKN","DARE",
    "DPRO","EPAZ","EVTV","FFIE","FORW","FTFT","GHSI","GXAI",
    "HLBZ","IMPP","IPDN","JBDI","KAVL","LGMK","LIXT","LKCO",
    "LTBR","MITI","MKUL","MNPR","NBTX","NCPL","NKGN","NLSP","NOVV",
    "NRSN","NRXP","NSYS","NTRB","NVNI","NXGL",
    "OCUP","OPFI","ORPH","OTLK","OXBR",
    "PALT","PAYO","PBLA","PESI","PGEN","PHVS","PLRX","PRPH","PRST","PRVB",
    "PULM","PYPL","QBTS",
    "RCKT","RDZN","RELI","RETO","RGLS","RNAZ","ROIV","RPID","RPRX","RSLS",
    "RUBY","RZLT","SAMA","SATX","SCNX","SDIG","SERA","SGLB","SGLY","SHPW",
    "SIGL","SING","SISI","SJIU","SKYX","SLGG","SLRX","SOBR","SONN","SONX",
    "SPRB","SPRC","SPRO","SRTX","SSSS","SSYS","STAF","STEM","STGS","STIX",
    "STOK","STRM","SUMR","SUNL","SUNW","SUPN","SURF","SURG","SWAG","SWAV",
    "SXTC","SYRA","SYTA",
    "TCON","TGLS","THTX","TILS","TISI","TLGA","TLRY","TLSS","TMBR","TMDI",
    "TNON","TOCA","TOGI","TPCO","TPVG","TRDA","TRIB","TRIL","TRIM","TRKA",
    "TRNX","TRSA","TSHA","TSNS","TSVT","TTAM","TTCF","TTOO","TTSH",
    "TUEM","TVTX","TWNK","TWST","TXMD","TYRA",
    # Kev's specific stocks from videos
    "GLXG","PPCB","WTO","SER","TNT","NVF","MTEK","MNDR","CREG","GXAI",
]
UNIVERSE = list(dict.fromkeys(UNIVERSE))  # deduplicate


# ── Webull bar helpers ────────────────────────────────────────────────────────

def _parse_bars(resp) -> list:
    """Extract list of bars from a Webull API response."""
    if resp.status_code != 200:
        return []
    raw = resp.json()
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        data = raw.get("data", raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items", data.get("list", []))
    return []


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
    """Extract the bar's timestamp in milliseconds."""
    for k in ("timestamp", "time", "t", "ts", "beginTime", "begin_time",
              "open_time", "openTime", "startTime", "start_time"):
        v = bar.get(k)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
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
    return vol >= MIN_ABS_VOL


def _simulate(df: pd.DataFrame, entry_i: int, entry_price: float):
    shares      = POSITION_DOLLARS / entry_price
    target      = entry_price * (1 + TARGET_PCT)
    half_done   = False
    half_price  = 0.0
    remaining   = shares

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
            next_open = float(df.iloc[j + 1]["Open"]) if j + 1 < len(df) else price
            pnl = _pnl(entry_price, half_price, next_open, shares, half_done, remaining)
            return _result(df, entry_i, entry_price, next_open, "EMA STOP", pnl, shares, half_done, half_price)

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
    print(f"  WEBULL DEEP BACKTEST — Flat Top Breakout + EMA9 Stop")
    print(f"  Universe: {len(UNIVERSE)} tickers | Daily lookback: {DAILY_BAR_LOOKBACK} bars")
    print(f"  Gap filter: {MIN_GAP_PCT*100:.0f}%–{MAX_GAP_PCT*100:.0f}% | "
          f"Flat top: {FLAT_TOP_WINDOW} bars <{FLAT_TOP_MAX_RANGE*100:.0f}%")
    print(f"{'='*70}\n")

    # ── Phase 1: scan daily bars for all gap days ─────────────────────────────
    all_gaps = []
    seen     = set()
    print("Phase 1 — scanning daily bars for gap-up days...\n")

    for i, ticker in enumerate(UNIVERSE, 1):
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
    out = "/tmp/webull_backtest_results.json"
    with open(out, "w") as f:
        json.dump([{
            "ticker":   r["ticker"],
            "day":      str(r.get("day", "")),
            "gap_pct":  r.get("gap_pct", 0),
            "trades":   r.get("trades", []),
            "note":     r.get("note", ""),
        } for r in results], f, indent=2)
    print(f"\n  Raw results saved → {out}")


if __name__ == "__main__":
    main()
