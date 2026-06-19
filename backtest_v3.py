#!/usr/bin/env python3
"""
Marcos Trading Bot — Strategy Backtester v3
============================================
Full stress test of the Kev-inspired strategy using 5-minute bars,
which lets yfinance reach back 60 days instead of 30.

Strategy:
  Stock filter : gapped 15–60% on prior-close basis, open price ≥ $1.50
  Entry        : VWAP reclaim after morning dip — price consolidates
                 N bars in tight range near VWAP, then closes above window high
  Stop         : close below 9 EMA → exit at next bar open
  Target       : +10% → take half off, trail rest at 9 EMA
  Time         : entries ONLY in first 30 minutes (9:30–10:00 AM ET)

5-min bars: each "bar" = 5 minutes, so:
  FLAT_TOP_WINDOW = 4 bars = 20 minutes of consolidation check
  TIME_CUTOFF     = "10:00" = only 6 bars after open

Usage:
  python3 backtest_v3.py --days 60
  python3 backtest_v3.py --days 60 --tickers ATPC LASE CMND
"""

import argparse
import warnings
from datetime import date, timedelta, datetime

import yfinance as yf
import pandas as pd

warnings.filterwarnings("ignore")

# ── Strategy constants ──────────────────────────────────────────────────────
BAR_INTERVAL       = "5m"   # 5-min bars → 60-day lookback in yfinance
FLAT_TOP_WINDOW    = 3      # 3 × 5min = 15 min of consolidation
FLAT_TOP_MAX_RANGE = 0.08   # 8% range — 5-min bars naturally wider than 1-min
MIN_ABS_VOL        = 5_000  # min shares per bar (lower for 5-min bars)
EMA_PERIOD         = 9      # 9-bar EMA (~45 min lookback)
TIME_CUTOFF        = "10:30" # first 60 min after open
VWAP_REQUIRED      = True

POSITION_DOLLARS   = 100.00
TARGET_PCT         = 0.10
MAX_TRADES_PER_DAY = 2
MIN_PRICE          = 1.50   # skip sub-$1.50 stocks
MIN_GAP_PCT        = 0.15   # only real gap-up days (≥15%)
MAX_GAP_PCT        = 0.60   # skip extreme gappers (>60%) — move too fast


# ── Data ────────────────────────────────────────────────────────────────────

def fetch_daily(ticker: str, days_back: int) -> pd.DataFrame:
    """Daily OHLCV going back enough to spot gaps."""
    start = date.today() - timedelta(days=days_back + 10)
    df = yf.download(ticker, start=start, end=date.today() + timedelta(days=1),
                     interval="1d", progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def fetch_intraday(ticker: str, day: date) -> pd.DataFrame:
    """5-min intraday bars for a specific day (works up to 60 days back)."""
    start = datetime.combine(day, datetime.min.time())
    end   = datetime.combine(day + timedelta(days=1), datetime.min.time())
    df = yf.download(ticker, start=start, end=end,
                     interval=BAR_INTERVAL, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert("America/New_York")
    df = df.between_time("09:30", "15:30")
    return df if len(df) >= 6 else None


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["tp"]      = (df["High"] + df["Low"] + df["Close"]) / 3
    df["vwap"]    = (df["tp"] * df["Volume"]).cumsum() / df["Volume"].cumsum()
    df["ema9"]    = df["Close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    df["avg_vol"] = df["Volume"].rolling(10, min_periods=3).mean()
    return df


# ── Gap scanner ───────────────────────────────────────────────────────────────

def find_gap_days(ticker: str, days_back: int) -> list:
    """
    Returns list of (day, gap_pct, open_price) for days where
    the stock gapped MIN_GAP_PCT..MAX_GAP_PCT from prior close.
    """
    daily = fetch_daily(ticker, days_back)
    if daily is None or len(daily) < 2:
        return []

    cutoff = date.today() - timedelta(days=days_back)
    results = []
    closes = daily["Close"].values
    opens  = daily["Open"].values
    dates  = [d.date() for d in daily.index]

    for i in range(1, len(daily)):
        d = dates[i]
        if d < cutoff:
            continue
        if d.weekday() >= 5:
            continue
        prior_close = float(closes[i - 1])
        open_price  = float(opens[i])
        if prior_close <= 0:
            continue
        gap = (open_price - prior_close) / prior_close
        if MIN_GAP_PCT <= gap <= MAX_GAP_PCT and open_price >= MIN_PRICE:
            results.append((d, round(gap * 100, 1), open_price))

    return results


# ── Signal detection ─────────────────────────────────────────────────────────

def detect_breakout(df: pd.DataFrame, i: int) -> bool:
    """
    True if bar i is a valid morning breakout entry:
    1. Time before TIME_CUTOFF
    2. Price above VWAP
    3. Prior FLAT_TOP_WINDOW bars in tight range (<5%)
    4. Current close breaks above that window's high
    5. Minimum volume
    """
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
    if vol < MIN_ABS_VOL:
        return False

    window = df.iloc[i - FLAT_TOP_WINDOW : i]
    w_high = float(window["High"].max())
    w_low  = float(window["Low"].min())

    if w_low <= 0:
        return False

    range_pct = (w_high - w_low) / w_low
    if range_pct > FLAT_TOP_MAX_RANGE:
        return False  # not consolidating

    return price > w_high  # breakout above the flat top


# ── Trade simulation ─────────────────────────────────────────────────────────

def simulate_trade(df: pd.DataFrame, entry_i: int, entry_price: float) -> dict:
    shares       = POSITION_DOLLARS / entry_price
    target_price = entry_price * (1 + TARGET_PCT)
    half_exited     = False
    half_exit_price = 0.0
    remaining       = shares

    for j in range(entry_i + 1, len(df)):
        price = float(df["Close"].iloc[j])
        ema9  = float(df["ema9"].iloc[j])
        t_str = df.index[j].strftime("%H:%M")
        is_last = (j == len(df) - 1) or t_str >= "15:30"

        if is_last:
            pnl = _pnl(entry_price, half_exit_price, price, shares, half_exited, remaining)
            return _result(entry_i, df, entry_price, price, "TIME", pnl, shares,
                           half_exited, half_exit_price)

        if not half_exited and price >= target_price:
            half_exit_price = price
            half_exited     = True
            remaining       = shares / 2

        if price < ema9:
            nxt = float(df.iloc[j + 1]["Open"]) if j + 1 < len(df) else price
            pnl = _pnl(entry_price, half_exit_price, nxt, shares, half_exited, remaining)
            return _result(entry_i, df, entry_price, nxt, "EMA STOP", pnl, shares,
                           half_exited, half_exit_price)

    return None


def _pnl(entry, half_price, exit_price, shares, half_exited, remaining):
    pnl = (half_price - entry) * (shares / 2) if half_exited else 0
    pnl += (exit_price - entry) * remaining
    return pnl


def _result(entry_i, df, entry_price, exit_price, exit_reason,
            pnl, shares, half_exited, half_exit_price):
    entry_time = df.index[entry_i].strftime("%H:%M")
    gain_pct   = (exit_price - entry_price) / entry_price * 100
    partial    = f" (half @${half_exit_price:.2f})" if half_exited else ""
    return {
        "entry_time":  entry_time,
        "entry":       entry_price,
        "exit":        exit_price,
        "exit_reason": exit_reason,
        "pnl":         round(pnl, 2),
        "gain_pct":    round(gain_pct, 2),
        "partial":     partial,
    }


# ── Per-day runner ────────────────────────────────────────────────────────────

def run_day(ticker: str, day: date, gap_pct: float) -> dict:
    df = fetch_intraday(ticker, day)
    if df is None:
        return {"ticker": ticker, "day": day, "gap_pct": gap_pct, "note": "no intraday data", "trades": []}

    df = add_indicators(df)
    trades      = []
    trade_count = 0
    last_entry  = -1

    for i in range(FLAT_TOP_WINDOW, len(df)):
        if trade_count >= MAX_TRADES_PER_DAY:
            break
        if i <= last_entry + 2:
            continue
        if detect_breakout(df, i):
            ep = float(df["Close"].iloc[i])
            r  = simulate_trade(df, i, ep)
            if r:
                trades.append(r)
                trade_count += 1
                last_entry   = i

    open_p  = float(df["Open"].iloc[0])
    high_p  = float(df["High"].max())
    close_p = float(df["Close"].iloc[-1])
    change  = (close_p - open_p) / open_p * 100

    return {
        "ticker":   ticker,
        "day":      day,
        "gap_pct":  gap_pct,
        "open":     open_p,
        "high":     high_p,
        "close":    close_p,
        "change":   change,
        "trades":   trades,
    }


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_report(all_results: list):
    all_trades = []
    print()
    print("=" * 72)
    print("  BACKTEST v3 — Morning VWAP Reclaim on Gap-Up Stocks (5-min bars)")
    print(f"  Filters: gap {MIN_GAP_PCT*100:.0f}–{MAX_GAP_PCT*100:.0f}%  "
          f"price≥${MIN_PRICE}  entry before {TIME_CUTOFF}  EMA{EMA_PERIOD} stop")
    print("=" * 72)

    skipped = [r for r in all_results if "note" in r]
    valid   = [r for r in all_results if "note" not in r]

    for r in sorted(valid, key=lambda x: x["day"]):
        t   = r["ticker"]
        day = r["day"].strftime("%a %b %d")
        chg = f"{r['change']:+.1f}%"
        print(f"\n{'─'*70}")
        print(f"  {t}  {day}  gap={r['gap_pct']:+.0f}%  "
              f"open=${r['open']:.2f}  high=${r['high']:.2f}  close=${r['close']:.2f}  ({chg})")

        if not r["trades"]:
            print("  → No signal triggered")
        else:
            for tr in r["trades"]:
                icon = "✅" if tr["pnl"] > 0 else "❌"
                print(f"  {icon} @ {tr['entry_time']}  "
                      f"entry=${tr['entry']:.2f}  exit=${tr['exit']:.2f}  "
                      f"({tr['gain_pct']:+.1f}%)  {tr['exit_reason']}"
                      f"{tr['partial']}  → ${tr['pnl']:+.2f}")
                all_trades.append({**tr, "ticker": t, "day": r["day"], "gap_pct": r["gap_pct"]})

    print(f"\n  (skipped {len(skipped)} days — no intraday data available)")

    if not all_trades:
        print("\n  No trades triggered.")
        return

    wins   = [t for t in all_trades if t["pnl"] > 0]
    losses = [t for t in all_trades if t["pnl"] <= 0]
    total  = sum(t["pnl"] for t in all_trades)
    wr     = len(wins) / len(all_trades) * 100

    print()
    print("=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    print(f"  Gap days tested    : {len(valid)}")
    print(f"  Days with signal   : {len(set(t['day'] for t in all_trades))}")
    print(f"  Total trades       : {len(all_trades)}")
    print(f"  Winners            : {len(wins)}")
    print(f"  Losers             : {len(losses)}")
    print(f"  Win rate           : {wr:.0f}%")
    print(f"  Total P&L          : ${total:+.2f}  (on ${POSITION_DOLLARS:.0f}/trade)")
    if wins:
        avg_w = sum(t["pnl"] for t in wins) / len(wins)
        print(f"  Avg winner         : ${avg_w:+.2f}")
    if losses:
        avg_l = sum(t["pnl"] for t in losses) / len(losses)
        print(f"  Avg loser          : ${avg_l:+.2f}")
    if wins and losses:
        rr = abs(sum(t["pnl"] for t in wins) / len(wins)) / abs(sum(t["pnl"] for t in losses) / len(losses))
        ev = (wr/100) * (sum(t["pnl"] for t in wins)/len(wins)) + ((1-wr/100)) * (sum(t["pnl"] for t in losses)/len(losses))
        print(f"  Win/loss ratio     : {rr:.2f}:1")
        print(f"  Expected value/trade: ${ev:+.2f}")

    by_reason = {}
    for tr in all_trades:
        by_reason.setdefault(tr["exit_reason"], []).append(tr)
    print()
    for r, ts in by_reason.items():
        w = len([t for t in ts if t["pnl"] > 0])
        print(f"  {r:12s}: {len(ts)} trades, {w}/{len(ts)} wins, "
              f"${sum(t['pnl'] for t in ts):+.2f} total")

    # Gap% buckets
    buckets = [(15,30), (30,45), (45,60)]
    print()
    print("  By gap% bucket:")
    for lo, hi in buckets:
        ts = [t for t in all_trades if lo <= t["gap_pct"] < hi]
        if not ts:
            continue
        w = len([t for t in ts if t["pnl"] > 0])
        print(f"    {lo}–{hi}%: {len(ts)} trades  {w}/{len(ts)} wins  "
              f"${sum(t['pnl'] for t in ts):+.2f}")

    print("=" * 72)


# ── Universe ──────────────────────────────────────────────────────────────────

# Extended small-cap momentum universe — these are the type of stocks
# that end up on Kev's scanner. Add more as we discover them.
UNIVERSE = [
    # Known from previous sessions
    "ATPC", "LASE", "ASNS", "CDT", "ARTL", "TPET", "STAK", "BIAF",
    "MNDR", "GRNQ", "TDTH", "CAST", "AHMA", "RGNT", "CMND", "GOVX",
    "PHGE", "MNTS", "IINN", "ZJYL", "RCAT", "HCWB", "LPRO", "HITI",
    # Common small-cap momentum stocks
    "LKCO", "XTIA", "MDJH", "MGOL", "MEGI", "BSBR", "EBON", "BFRI",
    "NKLA", "CENN", "MULN", "IDEX", "ILUS", "PEGY", "RELI", "GMVD",
    "GPUS", "CLRB", "MFON", "EVTL", "AEYE", "CODA", "PRTY", "APWC",
    "MEGL", "KTTA", "HYMC", "GFAI", "PAVS", "BRTX", "SBEV", "RLAY",
    "DBGI", "HPNN", "ADTX", "WHLR", "ZJYL", "PHGE", "LPRO", "HITI",
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest v3 — 60-day stress test")
    parser.add_argument("--days",     type=int, default=60,
                        help="Days to look back for gap-up events (default 60)")
    parser.add_argument("--tickers",  nargs="+", default=None,
                        help="Limit to specific tickers (default: full universe)")
    parser.add_argument("--position", type=float, default=POSITION_DOLLARS)
    args = parser.parse_args()

    POSITION_DOLLARS = args.position
    universe = [t.upper() for t in args.tickers] if args.tickers else UNIVERSE

    print(f"\nScanning {len(universe)} tickers over {args.days} days for gap-up events...")
    print(f"Gap filter: {MIN_GAP_PCT*100:.0f}–{MAX_GAP_PCT*100:.0f}%  price≥${MIN_PRICE}  "
          f"bar={BAR_INTERVAL}  time<{TIME_CUTOFF}\n")

    # Step 1: find all gap-up days
    all_gap_days = []
    for ticker in universe:
        gaps = find_gap_days(ticker, args.days)
        for day, gap_pct, open_price in gaps:
            all_gap_days.append((ticker, day, gap_pct, open_price))

    all_gap_days.sort(key=lambda x: x[1])
    print(f"Found {len(all_gap_days)} gap-up days ({MIN_GAP_PCT*100:.0f}–{MAX_GAP_PCT*100:.0f}%) "
          f"across {len(set(x[0] for x in all_gap_days))} tickers\n")

    if not all_gap_days:
        print("No gap-up days found. Try a larger universe or wider gap filter.")
        exit(0)

    # Print what we found
    print("  Gap-up days to test:")
    for ticker, day, gap_pct, open_price in all_gap_days:
        print(f"    {ticker:6s}  {day}  gap={gap_pct:+.0f}%  open=${open_price:.2f}")

    # Step 2: run strategy on each gap day
    print(f"\nRunning strategy on {len(all_gap_days)} gap-up days...\n")
    results = []
    for ticker, day, gap_pct, open_price in all_gap_days:
        r = run_day(ticker, day, gap_pct)
        results.append(r)

    print_report(results)
