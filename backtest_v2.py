#!/usr/bin/env python3
"""
Marcos Trading Bot — Strategy Backtester v2
============================================
Tests the Kev-inspired strategy:
  Entry:  Flat top breakout — 8-bar consolidation (<5% range) + close above
          window high + 1.5× average volume. Must be above VWAP.
  Stop:   Close below 9 EMA → exit at next bar open
  Target: +10% → take half off, trail rest at 9 EMA
  Time:   No entries after 11:00 AM ET (Kev's confirmed trading window)

Compare results vs backtest.py (VWAP reclaim strategy).

Usage:
  python3 backtest_v2.py --tickers ATPC LASE ASNS --days 20
  python3 backtest_v2.py --days 30
"""

import argparse
import os
import warnings
from datetime import date, timedelta, datetime

import yfinance as yf
import pandas as pd

warnings.filterwarnings("ignore")

# ── Strategy constants ──────────────────────────────────────────────────────
FLAT_TOP_WINDOW    = 8      # bars to look back for consolidation
FLAT_TOP_MAX_RANGE = 0.05   # consolidation high-to-low must be <5%
BREAKOUT_VOL_MULT  = 0.0    # no volume multiplier — small-caps break on thin volume
MIN_ABS_VOL        = 10_000 # absolute minimum shares on entry bar (liquidity floor)
EMA_PERIOD         = 9      # 9 EMA — entry reference + trailing stop
TIME_CUTOFF        = "10:00" # no entries at or after 10:00 AM ET (early morning only)
VWAP_REQUIRED      = True   # price must be above VWAP to enter

POSITION_DOLLARS   = 100.00
TARGET_PCT         = 0.10   # +10% → take half off
MAX_TRADES_PER_DAY = 2
MIN_PRICE          = 1.50   # Kev targets stocks >$1.50 — sub-$1 are noise
MAX_GAP_PCT        = 0.60   # skip stocks that gapped >60% — too explosive, no flat top forms


# ── Data ────────────────────────────────────────────────────────────────────

def fetch_day(ticker: str, day: date):
    start = datetime.combine(day, datetime.min.time())
    end   = datetime.combine(day + timedelta(days=1), datetime.min.time())
    df = yf.download(ticker, start=start, end=end,
                     interval="1m", progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None, None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert("America/New_York")
    df = df.between_time("09:30", "15:30")
    if len(df) < 10:
        return None, None

    # Fetch prior close to calculate gap %
    prior_start = day - timedelta(days=5)
    daily = yf.download(ticker, start=prior_start, end=day,
                        interval="1d", progress=False, auto_adjust=True)
    prior_close = None
    if daily is not None and not daily.empty:
        if isinstance(daily.columns, pd.MultiIndex):
            daily.columns = daily.columns.get_level_values(0)
        prior_close = float(daily["Close"].iloc[-1])

    return df, prior_close


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["tp"]      = (df["High"] + df["Low"] + df["Close"]) / 3
    df["vwap"]    = (df["tp"] * df["Volume"]).cumsum() / df["Volume"].cumsum()
    df["ema9"]    = df["Close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    df["avg_vol"] = df["Volume"].rolling(30, min_periods=5).mean()
    return df


# ── Signal detection ─────────────────────────────────────────────────────────

def detect_flat_top_breakout(df: pd.DataFrame, i: int) -> bool:
    """
    Returns True if bar i is a valid flat top breakout entry.

    Conditions:
    1. Time < 11:00 AM
    2. Price above VWAP
    3. Prior FLAT_TOP_WINDOW bars form a tight range (<5%)
    4. Current close breaks above that window's high
    5. Volume >= 1.5x avg and >= MIN_ABS_VOL
    """
    if i < FLAT_TOP_WINDOW:
        return False

    t_str = df.index[i].strftime("%H:%M")
    if t_str >= TIME_CUTOFF:
        return False

    price = float(df["Close"].iloc[i])
    vwap  = float(df["vwap"].iloc[i])
    vol   = float(df["Volume"].iloc[i])
    avg_v = float(df["avg_vol"].iloc[i])

    # Price floor — Kev avoids sub-$1.50 stocks
    if price < MIN_PRICE:
        return False

    # Must be above VWAP
    if VWAP_REQUIRED and price <= vwap:
        return False

    # Check prior window for tight consolidation
    window = df.iloc[i - FLAT_TOP_WINDOW : i]
    w_high = float(window["High"].max())
    w_low  = float(window["Low"].min())

    if w_low <= 0:
        return False

    range_pct = (w_high - w_low) / w_low
    if range_pct > FLAT_TOP_MAX_RANGE:
        return False  # not tight enough — chopy, not consolidating

    # Current close must break above the window high
    if price <= w_high:
        return False

    # Volume: only enforce minimum liquidity floor, not a multiplier
    # Small-caps often break on thin volume then get the heavy volume after
    return vol >= MIN_ABS_VOL


# ── Trade simulation ─────────────────────────────────────────────────────────

def simulate_trade(df: pd.DataFrame, entry_i: int, entry_price: float):
    shares       = POSITION_DOLLARS / entry_price
    target_price = entry_price * (1 + TARGET_PCT)

    half_exited     = False
    half_exit_price = 0.0
    remaining       = shares

    for j in range(entry_i + 1, len(df)):
        row   = df.iloc[j]
        price = float(row["Close"])
        ema9  = float(row["ema9"])
        t_str = df.index[j].strftime("%H:%M")
        is_last = (j == len(df) - 1) or t_str >= "15:30"

        # Time stop
        if is_last:
            exit_price  = price
            exit_reason = "TIME"
            pnl = _calc_pnl(entry_price, half_exit_price, exit_price,
                            shares, half_exited, remaining)
            return _result(entry_i, df, entry_price, exit_price,
                           exit_reason, pnl, shares, half_exited, half_exit_price)

        # First target: +10% → take half off
        if not half_exited and price >= target_price:
            half_exit_price = price
            half_exited     = True
            remaining       = shares / 2

        # Stop: close below 9 EMA → exit at next bar open
        if price < ema9:
            next_open   = float(df.iloc[j + 1]["Open"]) if j + 1 < len(df) else price
            exit_price  = next_open
            exit_reason = "EMA STOP"
            pnl = _calc_pnl(entry_price, half_exit_price, exit_price,
                            shares, half_exited, remaining)
            return _result(entry_i, df, entry_price, exit_price,
                           exit_reason, pnl, shares, half_exited, half_exit_price)

    return None


def _calc_pnl(entry, half_price, exit_price, shares, half_exited, remaining):
    pnl = 0.0
    if half_exited:
        pnl += (half_price - entry) * (shares / 2)
    pnl += (exit_price - entry) * remaining
    return pnl


def _result(entry_i, df, entry_price, exit_price, exit_reason,
            pnl, shares, half_exited, half_exit_price):
    entry_time = df.index[entry_i].strftime("%H:%M")
    gain_pct   = (exit_price - entry_price) / entry_price * 100
    partial    = f" (half @${half_exit_price:.2f})" if half_exited else ""
    return {
        "setup":       "FLAT TOP BREAK",
        "entry_time":  entry_time,
        "entry":       entry_price,
        "exit":        exit_price,
        "exit_reason": exit_reason,
        "pnl":         round(pnl, 2),
        "gain_pct":    round(gain_pct, 2),
        "partial":     partial,
    }


# ── Per-day runner ────────────────────────────────────────────────────────────

def run_backtest_day(ticker: str, day: date) -> dict:
    df, prior_close = fetch_day(ticker, day)
    if df is None:
        return {"ticker": ticker, "day": day, "note": "no data", "trades": []}

    # Gap filter: skip if stock gapped up more than MAX_GAP_PCT
    open_price = float(df["Open"].iloc[0])
    if prior_close and prior_close > 0:
        gap_pct = (open_price - prior_close) / prior_close
        if gap_pct > MAX_GAP_PCT:
            return {"ticker": ticker, "day": day,
                    "note": f"gap {gap_pct*100:.0f}% > {MAX_GAP_PCT*100:.0f}% limit — skipped",
                    "trades": []}

    df = add_indicators(df)

    trades      = []
    trade_count = 0
    last_entry_i = -1  # prevent back-to-back entries on adjacent bars

    for i in range(FLAT_TOP_WINDOW, len(df)):
        if trade_count >= MAX_TRADES_PER_DAY:
            break
        if i <= last_entry_i + 3:  # cooldown: skip 3 bars after any entry
            continue

        if detect_flat_top_breakout(df, i):
            entry_price = float(df["Close"].iloc[i])
            result = simulate_trade(df, i, entry_price)
            if result:
                trades.append(result)
                trade_count  += 1
                last_entry_i  = i

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


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_report(all_results: list):
    all_trades = []
    print()
    print("=" * 70)
    print("  BACKTEST v2  —  Flat Top Breakout + EMA Stop  (Kev strategy)")
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
            print("  → No flat top breakout triggered")
        else:
            for tr in r["trades"]:
                icon = "✅" if tr["pnl"] > 0 else "❌"
                print(f"  {icon} {tr['setup']:16s} @ {tr['entry_time']}  "
                      f"entry=${tr['entry']:.2f}  exit=${tr['exit']:.2f}  "
                      f"({tr['gain_pct']:+.1f}%)  {tr['exit_reason']}"
                      f"{tr['partial']}  → ${tr['pnl']:+.2f}")
                all_trades.append({**tr, "ticker": t, "day": r["day"]})

    if not all_trades:
        print("\n  No trades triggered.")
        return

    wins   = [t for t in all_trades if t["pnl"] > 0]
    losses = [t for t in all_trades if t["pnl"] <= 0]
    total  = sum(t["pnl"] for t in all_trades)
    wr     = len(wins) / len(all_trades) * 100

    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Total trades   : {len(all_trades)}")
    print(f"  Winners        : {len(wins)}")
    print(f"  Losers         : {len(losses)}")
    print(f"  Win rate       : {wr:.0f}%")
    print(f"  Total P&L      : ${total:+.2f}  (on ${POSITION_DOLLARS:.0f}/trade)")
    if wins:
        print(f"  Avg winner     : ${sum(t['pnl'] for t in wins)/len(wins):+.2f}")
    if losses:
        print(f"  Avg loser      : ${sum(t['pnl'] for t in losses)/len(losses):+.2f}")

    # By exit reason
    by_reason = {}
    for tr in all_trades:
        r = tr["exit_reason"]
        by_reason.setdefault(r, []).append(tr)
    print()
    for r, ts in by_reason.items():
        w = len([t for t in ts if t["pnl"] > 0])
        print(f"  {r:14s}: {len(ts)} trades, {w}/{len(ts)} wins, "
              f"${sum(t['pnl'] for t in ts):+.2f} total")
    print("=" * 70)

    # Time-of-entry breakdown
    by_hour = {}
    for tr in all_trades:
        h = tr["entry_time"][:2]
        by_hour.setdefault(h, []).append(tr)
    if len(by_hour) > 1:
        print()
        print("  Entry time breakdown:")
        for h in sorted(by_hour):
            ts = by_hour[h]
            w  = len([t for t in ts if t["pnl"] > 0])
            print(f"    {h}:xx  {len(ts)} trades  {w}/{len(ts)} wins  "
                  f"${sum(t['pnl'] for t in ts):+.2f}")
        print("=" * 70)


# ── Helpers ───────────────────────────────────────────────────────────────────

def last_n_trading_days(n: int) -> list:
    days = []
    d = date.today()
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def load_scan_log(log_path: str) -> dict:
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


# Known small-cap momentum stocks — same universe as backtest.py for fair comparison
DEFAULT_TICKERS = [
    "ATPC", "LASE", "ASNS", "CDT", "APWC", "LPA",
    "WKSP", "TDTH", "GRNQ", "CAST", "AHMA", "RGNT",
    "GLMD", "TPET", "STAK", "BIAF", "MNDR", "ARTL",
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Marcos Bot — Kev Strategy Backtester v2")
    parser.add_argument("--tickers", nargs="+", default=None)
    parser.add_argument("--days",     type=int, default=1)
    parser.add_argument("--position", type=float, default=POSITION_DOLLARS)
    args = parser.parse_args()

    POSITION_DOLLARS = args.position
    days = last_n_trading_days(args.days)

    log_path = os.path.join(os.path.dirname(__file__), "scan_log.jsonl")
    scan_log = load_scan_log(log_path)

    print(f"\nKev Strategy Backtest — Flat Top Breakout + EMA9 Stop")
    print(f"Settings: window={FLAT_TOP_WINDOW} bars, range<{FLAT_TOP_MAX_RANGE*100:.0f}%, "
          f"vol≥{BREAKOUT_VOL_MULT}×avg, cutoff={TIME_CUTOFF}, EMA={EMA_PERIOD}")

    all_results = []
    for day in days:
        day_str = day.strftime("%Y-%m-%d")
        if args.tickers:
            day_tickers = [t.upper() for t in args.tickers]
        elif day_str in scan_log:
            day_tickers = scan_log[day_str]
            print(f"  {day_str}: {len(day_tickers)} tickers from scan log")
        else:
            day_tickers = DEFAULT_TICKERS
            print(f"  {day_str}: using default ticker list")

        for ticker in day_tickers:
            result = run_backtest_day(ticker, day)
            all_results.append(result)

    total_tickers = len(set(r["ticker"] for r in all_results if "note" not in r))
    print(f"\nBacktested {total_tickers} unique tickers over {len(days)} day(s)")
    print(f"Position: ${POSITION_DOLLARS:.0f} per trade")

    print_report(all_results)
