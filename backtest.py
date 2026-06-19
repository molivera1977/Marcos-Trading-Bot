#!/usr/bin/env python3
"""
Marcos Trading Bot — Strategy Backtester
=========================================
Simulates the VWAP pullback bounce / reclaim strategy on historical
1-minute intraday data. No real money, no Railway, no Webull.

Usage:
  python3 backtest.py                        # default: today's tickers, today
  python3 backtest.py --tickers CAST ATPC    # specific tickers
  python3 backtest.py --days 5               # last 5 trading days
  python3 backtest.py --tickers ATPC CDT --days 10

Exit rules:
  - Stop:   close below VWAP at any tick  → exit immediately at next bar open
  - Target: +10% from entry               → exit half, trail rest at VWAP
  - Trail:  second half exits if VWAP lost after partial
  - Time:   any open position closed at 3:30 PM
"""

import argparse
import os
import warnings
import sys
from datetime import date, timedelta, datetime

import yfinance as yf
import pandas as pd

warnings.filterwarnings("ignore")

# ── Strategy constants (must match bot) ────────────────────────────────
VWAP_PULLBACK_MIN_RUN = 0.05    # prior run must be ≥5% above VWAP
VWAP_PULLBACK_ZONE    = 0.03    # within 3% of VWAP = pullback zone
VWAP_VOL_MULTIPLIER   = 2.0     # reclaim requires 2× avg minute volume
VWAP_CONFIRM_TICKS    = 3       # reclaim requires 3 consecutive ticks above VWAP+90MA
MIN_ABS_VOL           = 15_000  # absolute minimum shares on entry bar
MAX_EXTENSION         = 0.15    # don't enter if >15% above VWAP

POSITION_DOLLARS  = 100.00   # fixed sim position size per trade
TARGET_PCT        = 0.10     # 10% profit target → take half off
STOP_BUFFER       = 0.001    # exit on close 0.1% below VWAP (not just touching)
MAX_TRADES_PER_DAY = 2       # stop entering after 2 trades per ticker per day


# ── Data fetching ───────────────────────────────────────────────────────

def fetch_day(ticker: str, day: date):
    start = datetime.combine(day, datetime.min.time())
    end   = datetime.combine(day + timedelta(days=1), datetime.min.time())
    df = yf.download(ticker, start=start, end=end,
                     interval="1m", progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert("America/New_York")
    df = df.between_time("09:30", "15:30")
    return df if len(df) >= 10 else None


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["tp"]       = (df["High"] + df["Low"] + df["Close"]) / 3
    df["vwap"]     = (df["tp"] * df["Volume"]).cumsum() / df["Volume"].cumsum()
    df["ma90"]     = df["Close"].rolling(90, min_periods=1).mean()
    df["avg_vol"]  = df["Volume"].rolling(30, min_periods=1).mean()
    return df


# ── Trade simulation ────────────────────────────────────────────────────

def simulate_trade(df: pd.DataFrame, entry_i: int, entry_price: float, setup_type: str):
    """
    Walk forward from entry_i and apply exit rules.
    Returns a dict with outcome details.
    """
    shares = POSITION_DOLLARS / entry_price
    target_price = entry_price * (1 + TARGET_PCT)

    half_exited    = False
    half_exit_price = 0.0
    remaining       = shares

    for j in range(entry_i + 1, len(df)):
        row   = df.iloc[j]
        price = float(row["Close"])
        vwap  = float(row["vwap"])
        t_str = df.index[j].strftime("%H:%M")
        is_last_bar = (j == len(df) - 1)

        # Time stop at 3:30 PM
        if is_last_bar or t_str >= "15:30":
            exit_price  = price
            exit_reason = "TIME"
            pnl = (half_exit_price - entry_price) * (shares / 2) if half_exited else 0
            pnl += (exit_price - entry_price) * remaining
            return _result(setup_type, entry_i, df, entry_price, exit_price,
                           exit_reason, pnl, shares, half_exited, half_exit_price)

        # Target hit — take half off
        if not half_exited and price >= target_price:
            half_exit_price = price
            half_exited     = True
            remaining       = shares / 2

        # Stop: close below VWAP (with small buffer)
        if price < vwap * (1 - STOP_BUFFER):
            exit_price  = float(df.iloc[j + 1]["Open"]) if j + 1 < len(df) else price
            exit_reason = "VWAP STOP"
            pnl = (half_exit_price - entry_price) * (shares / 2) if half_exited else 0
            pnl += (exit_price - entry_price) * remaining
            return _result(setup_type, entry_i, df, entry_price, exit_price,
                           exit_reason, pnl, shares, half_exited, half_exit_price)

    # Fell through — shouldn't happen
    return None


def _result(setup_type, entry_i, df, entry_price, exit_price, exit_reason,
            pnl, shares, half_exited, half_exit_price):
    entry_time = df.index[entry_i].strftime("%H:%M")
    gain_pct   = (exit_price - entry_price) / entry_price * 100
    partial    = f" (half @${half_exit_price:.2f})" if half_exited else ""
    return {
        "setup":      setup_type,
        "entry_time": entry_time,
        "entry":      entry_price,
        "exit":       exit_price,
        "exit_reason": exit_reason,
        "pnl":        round(pnl, 2),
        "gain_pct":   round(gain_pct, 2),
        "partial":    partial,
    }


# ── Signal detection + simulation for one ticker on one day ─────────────

def run_backtest_day(ticker: str, day: date) -> dict:
    df = fetch_day(ticker, day)
    if df is None:
        return {"ticker": ticker, "day": day, "note": "no data", "trades": []}

    df = add_indicators(df)

    trades = []
    trade_count = 0
    in_trade    = False

    ticks_rec  = 0
    ticks_pb   = 0
    hw_live    = 0.0
    pb_armed   = False

    for i in range(len(df)):
        if trade_count >= MAX_TRADES_PER_DAY:
            break

        price = float(df["Close"].iloc[i])
        high  = float(df["High"].iloc[i])
        vwap  = float(df["vwap"].iloc[i])
        ma90  = float(df["ma90"].iloc[i])
        vol   = float(df["Volume"].iloc[i])
        avg_v = float(df["avg_vol"].iloc[i])

        if vwap <= 0:
            continue

        above_vwap = price > vwap
        above_90ma = price > ma90

        # Track high-water mark
        if above_vwap:
            pct_above = (price - vwap) / vwap
            if pct_above >= VWAP_PULLBACK_MIN_RUN:
                hw_live = max(hw_live, price)
            if pct_above <= MAX_EXTENSION:
                ticks_pb  += 1
                ticks_rec += 1
            else:
                ticks_pb  = 0
                ticks_rec = 0
        else:
            ticks_pb  = 0
            ticks_rec = 0
            if hw_live >= vwap * (1 + VWAP_PULLBACK_MIN_RUN):
                gap = (price - vwap) / vwap
                if abs(gap) <= VWAP_PULLBACK_ZONE:
                    pb_armed = True
                elif price < vwap * (1 - VWAP_PULLBACK_ZONE * 2):
                    pb_armed = False
                    hw_live  = 0.0

        if not above_vwap or not above_90ma:
            continue

        triggered = False
        setup_type = None

        # Pullback Bounce: 1 tick, 1× vol, armed
        if pb_armed and ticks_pb == 1 and vol >= MIN_ABS_VOL:
            triggered  = True
            setup_type = "PULLBACK BOUNCE"
            pb_armed   = False

        # Reclaim: 3 ticks, 2× vol
        elif ticks_rec == VWAP_CONFIRM_TICKS:
            vol_ok = (avg_v == 0 or vol >= avg_v * VWAP_VOL_MULTIPLIER) and vol >= MIN_ABS_VOL
            if vol_ok:
                triggered  = True
                # Tag whether a prior run existed — lets us split analysis later
                setup_type = "RECLAIM+RUN" if hw_live >= vwap * (1 + VWAP_PULLBACK_MIN_RUN) else "RECLAIM"
                ticks_rec  = 0

        if triggered:
            result = simulate_trade(df, i, price, setup_type)
            if result:
                trades.append(result)
                trade_count += 1

    open_p  = float(df["Open"].iloc[0])
    high_p  = float(df["High"].max())
    close_p = float(df["Close"].iloc[-1])
    change  = (close_p - open_p) / open_p * 100

    return {
        "ticker": ticker,
        "day":    day,
        "open":   open_p,
        "high":   high_p,
        "close":  close_p,
        "change": change,
        "trades": trades,
    }


# ── Reporting ────────────────────────────────────────────────────────────

def print_report(all_results: list):
    all_trades = []
    print()
    print("=" * 70)
    print("  BACKTEST RESULTS")
    print("=" * 70)

    for r in all_results:
        t   = r["ticker"]
        day = r["day"].strftime("%a %b %d")
        if "note" in r:
            print(f"\n  {t} {day}: {r['note']}")
            continue

        change_str = f"{r['change']:+.1f}%"
        print(f"\n{'─'*68}")
        print(f"  {t}  {day}  open=${r['open']:.2f}  high=${r['high']:.2f}  "
              f"close=${r['close']:.2f}  ({change_str})")

        if not r["trades"]:
            print("  → No valid entry triggered")
        else:
            for tr in r["trades"]:
                icon = "✅" if tr["pnl"] > 0 else "❌"
                print(f"  {icon} {tr['setup']:16s} @ {tr['entry_time']}  "
                      f"entry=${tr['entry']:.2f}  exit=${tr['exit']:.2f}  "
                      f"({tr['gain_pct']:+.1f}%)  {tr['exit_reason']}"
                      f"{tr['partial']}  → ${tr['pnl']:+.2f}")
                all_trades.append({**tr, "ticker": t, "day": r["day"]})

    # Summary
    if not all_trades:
        print("\n  No trades triggered across all sessions.")
        return

    wins   = [t for t in all_trades if t["pnl"] > 0]
    losses = [t for t in all_trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in all_trades)
    win_rate  = len(wins) / len(all_trades) * 100

    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Total trades   : {len(all_trades)}")
    print(f"  Winners        : {len(wins)}")
    print(f"  Losers         : {len(losses)}")
    print(f"  Win rate       : {win_rate:.0f}%")
    print(f"  Total P&L      : ${total_pnl:+.2f}  (on ${POSITION_DOLLARS:.0f}/trade)")
    if wins:
        avg_win = sum(t["pnl"] for t in wins) / len(wins)
        print(f"  Avg winner     : ${avg_win:+.2f}")
    if losses:
        avg_loss = sum(t["pnl"] for t in losses) / len(losses)
        print(f"  Avg loser      : ${avg_loss:+.2f}")

    by_setup = {}
    for tr in all_trades:
        s = tr["setup"]
        by_setup.setdefault(s, []).append(tr)
    print()
    for s, ts in by_setup.items():
        w = len([t for t in ts if t["pnl"] > 0])
        print(f"  {s:16s}: {len(ts)} trades, {w}/{len(ts)} wins, "
              f"${sum(t['pnl'] for t in ts):+.2f} total")
    print("=" * 70)


# ── Trading days helper ─────────────────────────────────────────────────

def last_n_trading_days(n: int) -> list[date]:
    days = []
    d = date.today()
    while len(days) < n:
        if d.weekday() < 5:  # Mon–Fri
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


# ── Main ────────────────────────────────────────────────────────────────

DEFAULT_TICKERS = [
    "CAST", "AHMA", "RGNT",                          # today's Kev picks
    "ATPC", "LNKS", "CDT", "APWC", "LPA",            # gappers
    "WKSP", "TDTH", "WPRT", "GRNQ", "PRTH",
]

def load_scan_log(log_path: str) -> dict:
    """
    Reads scan_log.jsonl written by the bot each morning.
    Returns {date_str: [ticker, ...]} so the backtest uses
    the real tickers that were in play on each day.
    """
    import json
    log = {}
    try:
        with open(log_path) as f:
            for line in f:
                entry = json.loads(line.strip())
                d = entry.get("date", "")
                tickers = list(dict.fromkeys(
                    [entry.get("claude_pick") or ""] +
                    [g["symbol"] for g in entry.get("gappers", [])] +
                    entry.get("kev_tickers", []) +
                    entry.get("all_tickers", [])
                ))
                log[d] = [t for t in tickers if t]
    except FileNotFoundError:
        pass
    return log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Marcos Bot Strategy Backtester")
    parser.add_argument("--tickers", nargs="+", default=None,
                        help="Tickers to test (default: use scan_log.jsonl if available, else today's list)")
    parser.add_argument("--days", type=int, default=1,
                        help="Number of trading days to test (default: 1 = today)")
    parser.add_argument("--position", type=float, default=POSITION_DOLLARS,
                        help=f"Simulated position size in dollars (default: ${POSITION_DOLLARS:.0f})")
    args = parser.parse_args()

    POSITION_DOLLARS = args.position
    days = last_n_trading_days(args.days)

    # Load scan log — use real per-day tickers when available
    log_path = os.path.join(os.path.dirname(__file__), "scan_log.jsonl")
    scan_log = load_scan_log(log_path)
    using_log = bool(scan_log)

    if using_log:
        print(f"\nUsing scan_log.jsonl — real tickers per day")
    else:
        print(f"\nNo scan_log.jsonl found — using fixed ticker list")
        print(f"  (Run the bot for a few days to build up real historical data)")

    # Collect all results, using per-day tickers from log where available
    all_results = []
    for day in days:
        day_str = day.strftime("%Y-%m-%d")
        if args.tickers:
            day_tickers = [t.upper() for t in args.tickers]
        elif day_str in scan_log:
            day_tickers = scan_log[day_str]
            print(f"  {day_str}: {len(day_tickers)} tickers from scan log: {', '.join(day_tickers[:6])}{'...' if len(day_tickers) > 6 else ''}")
        else:
            day_tickers = DEFAULT_TICKERS
            print(f"  {day_str}: no scan log entry — using default ticker list")

        for ticker in day_tickers:
            result = run_backtest_day(ticker, day)
            all_results.append(result)

    total_tickers = len(set(r["ticker"] for r in all_results if "note" not in r))
    print(f"\nBacktested {total_tickers} unique tickers over {len(days)} day(s)")
    print(f"Days    : {', '.join(d.strftime('%b %d') for d in days)}")
    print(f"Position: ${POSITION_DOLLARS:.0f} per trade")

    print_report(all_results)
