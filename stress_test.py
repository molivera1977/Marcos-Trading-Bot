#!/usr/bin/env python3
"""
Strategy Stress Test — full 30-day universe scan
=================================================
Step 1: scan the full 535-ticker universe for ALL gap-up days in the past
        30 days where gap was 15–60% and open price >= $1.50
Step 2: run backtest_v2 strategy on every one of those (ticker, day) pairs
Step 3: full report with win rate, P&L, and breakdown by gap bucket

Usage:
  python3 stress_test.py
  python3 stress_test.py --days 30 --mingap 15 --maxgap 60
"""

import argparse
import warnings
from datetime import date, timedelta

import yfinance as yf
import pandas as pd

# Import the v2 strategy engine
from backtest_v2 import (
    fetch_day, add_indicators, detect_flat_top_breakout,
    simulate_trade, POSITION_DOLLARS, MAX_TRADES_PER_DAY,
    MIN_PRICE, TIME_CUTOFF, EMA_PERIOD, FLAT_TOP_WINDOW,
    FLAT_TOP_MAX_RANGE, MIN_ABS_VOL
)

warnings.filterwarnings("ignore")

# ── Expanded ticker universe ─────────────────────────────────────────────────
# These are the types of small-cap stocks that appear on Kev's scanner.
# Focus on stocks that trade $1.50-$20, low-float, prone to momentum gaps.

UNIVERSE = [
    # From our backtests
    "ATPC","LASE","ASNS","CDT","ARTL","TPET","STAK","BIAF","MNDR","GRNQ",
    "TDTH","CAST","AHMA","RGNT","CMND","GOVX","PHGE","MNTS","IINN","ZJYL",
    "RCAT","HCWB","LPRO","HITI","APWC","GFAI","PAVS","BRTX","SBEV","RLAY",
    "DBGI","ADTX","WHLR","CLRB","STAK",
    # Common small-cap momentum stocks from Kev's videos/scanner
    "MDJH","MGOL","MEGI","BFRI","NKLA","CENN","MULN","IDEX","ILUS","PEGY",
    "RELI","GMVD","GPUS","CLRB","MFON","EVTL","AEYE","CODA","PRTY","MEGL",
    "KTTA","HYMC","ACST","ATNF","BIOR","BTBT","BZFD","CIFS","CRKN","DARE",
    "DPRO","EPAZ","EVTV","FFIE","FORW","FTFT","GCBC","GFAI","GHSI","GXAI",
    "HLBZ","ILUS","IMPP","IPDN","JBDI","KAVL","LCNB","LGMK","LIXT","LKCO",
    "LTBR","MITI","MKUL","MNPR","MPVD","NBTX","NCPL","NKGN","NLSP","NOVV",
    "NPAB","NRBO","NRSN","NRXP","NSYS","NTRB","NVNI","NWIN","NXGL","NXTG",
    "OCUP","OFLX","OGCP","OHPA","OLIT","ONTF","OPFI","OPES","OPXS","ORPH",
    "OTLK","OVLY","OXBR","OXUS","PALT","PAVS","PAYO","PBLA","PEGY","PESI",
    "PGEN","PGSS","PHGE","PHVS","PLRX","PMTS","PPIH","PRLD","PRPB","PRPH",
    "PRST","PRTK","PRTS","PRTY","PRVB","PRZO","PSIG","PSNL","PTLO","PTPI",
    "PULM","PVBC","PVNC","PWFL","PWOD","PXLW","PXMD","PXSV","PYPD","QBTS",
    "RCAT","RCFA","RCKT","RDUS","RDZN","REFI","RELI","RETO","RFAC","RGLS",
    "RGND","RGNX","RLAY","RMBL","RMCF","RMGX","RNAZ","RNDB","RNLX","RNVA",
    "ROIV","ROLV","RPID","RPRX","RRAC","RRBI","RRGB","RSLS","RSSS","RSVR",
    "RTLX","RUBY","RVSB","RWOD","RXST","RXSV","RZLT","SAMA","SAMG","SATX",
    "SCNX","SCPX","SCVO","SDIG","SDSP","SDST","SEPA","SERA","SFIO","SFST",
    "SGLB","SGLY","SGRP","SHBI","SHFS","SHPW","SIGL","SING","SISI","SJIU",
    "SKAS","SKYX","SLGG","SLGL","SLHI","SLNA","SLNHP","SLNS","SLQT","SLRX",
    "SMFL","SMID","SMIT","SMLR","SMMF","SMSI","SMTK","SNPX","SNTI","SNWV",
    "SOBR","SONN","SONX","SPGX","SPLP","SPPI","SPRC","SPRO","SPRY","SPRB",
    "SRTX","SSBI","SSBK","SSNT","SSSS","SSYS","STAF","STEC","STEM","STEP",
    "STGS","STIX","STLY","STNT","STOK","STPC","STPK","STRM","STSS","STWO",
    "SUMR","SUNL","SUNW","SUPN","SURF","SURG","SURV","SVFD","SWAG","SWAV",
    "SWKH","SWRM","SXTC","SYBE","SYBT","SYRA","SYRS","SYTA","TCON","TDTH",
    "TETE","TGLS","THTX","TILS","TIRX","TISI","TLGA","TLGN","TLRY","TLSI",
    "TLSS","TMBR","TMDI","TMKR","TNFA","TNON","TOCA","TOGI","TPCO","TPET",
    "TPVG","TPWY","TRDA","TRIB","TRIL","TRIM","TRKA","TRNX","TROX","TRSA",
    "TRSO","TRST","TRVI","TRVN","TRWH","TRXA","TSHA","TSKB","TSLA","TSNS",
    "TSOI","TSPQ","TSSI","TSVT","TTAM","TTCF","TTGT","TTMI","TTOO","TTSH",
    "TUEM","TVTX","TWNK","TWOA","TWST","TXMD","TXSS","TYGO","TYRA","TZOO",
]

# De-duplicate
UNIVERSE = list(dict.fromkeys(UNIVERSE))


# ── Gap finder ────────────────────────────────────────────────────────────────

def find_gap_days(ticker: str, days_back: int, min_gap: float, max_gap: float) -> list:
    """Returns (day, gap_pct, open_price) for qualifying gap-up days."""
    start = date.today() - timedelta(days=days_back + 10)
    try:
        daily = yf.download(ticker, start=start, end=date.today() + timedelta(days=1),
                            interval="1d", progress=False, auto_adjust=True)
    except Exception:
        return []

    if daily is None or len(daily) < 2:
        return []
    if isinstance(daily.columns, pd.MultiIndex):
        daily.columns = daily.columns.get_level_values(0)

    cutoff = date.today() - timedelta(days=days_back)
    results = []
    close_col = daily["Close"]
    open_col  = daily["Open"]
    dates  = [d.date() for d in daily.index]

    for i in range(1, len(daily)):
        d = dates[i]
        if d < cutoff or d.weekday() >= 5:
            continue
        try:
            prior_close = float(close_col.iloc[i - 1])
            open_price  = float(open_col.iloc[i])
        except (TypeError, ValueError):
            continue
        if prior_close <= 0 or open_price < MIN_PRICE:
            continue
        gap = (open_price - prior_close) / prior_close
        if min_gap <= gap <= max_gap:
            results.append((d, round(gap * 100, 1), open_price))

    return results


# ── Per-day v2 runner ─────────────────────────────────────────────────────────

def run_backtest_day_v2(ticker: str, day: date, gap_pct: float) -> dict:
    df, _ = fetch_day(ticker, day)
    if df is None:
        return {"ticker": ticker, "day": day, "gap_pct": gap_pct, "note": "no data", "trades": []}

    df = add_indicators(df)
    trades, trade_count, last_entry = [], 0, -1

    for i in range(FLAT_TOP_WINDOW, len(df)):
        if trade_count >= MAX_TRADES_PER_DAY:
            break
        if i <= last_entry + 3:
            continue
        if detect_flat_top_breakout(df, i):
            ep = float(df["Close"].iloc[i])
            r  = simulate_trade(df, i, ep)
            if r:
                trades.append(r)
                trade_count += 1
                last_entry   = i

    open_p  = float(df["Open"].iloc[0])
    high_p  = float(df["High"].max())
    close_p = float(df["Close"].iloc[-1])

    return {
        "ticker": ticker,
        "day":    day,
        "gap_pct": gap_pct,
        "open":   open_p,
        "high":   high_p,
        "close":  close_p,
        "change": (close_p - open_p) / open_p * 100,
        "trades": trades,
    }


# ── Report ─────────────────────────────────────────────────────────────────────

def print_report(results: list):
    all_trades = []
    valid      = [r for r in results if "note" not in r]
    skipped    = [r for r in results if "note" in r]

    print()
    print("=" * 72)
    print("  STRESS TEST — Morning Flat Top Breakout on Real Gap-Up Stocks")
    print(f"  Params: window={FLAT_TOP_WINDOW} bars, range<{FLAT_TOP_MAX_RANGE*100:.0f}%, "
          f"min_vol={MIN_ABS_VOL:,}, cutoff={TIME_CUTOFF}, EMA{EMA_PERIOD}")
    print("=" * 72)

    for r in sorted(valid, key=lambda x: x["day"]):
        if not r["trades"]:
            continue  # only print days with signals
        t   = r["ticker"]
        day = r["day"].strftime("%a %b %d")
        print(f"\n{'─'*70}")
        print(f"  {t}  {day}  gap={r['gap_pct']:+.0f}%  "
              f"open=${r['open']:.2f}  high=${r['high']:.2f}  "
              f"close=${r['close']:.2f}  ({r['change']:+.1f}%)")
        for tr in r["trades"]:
            icon = "✅" if tr["pnl"] > 0 else "❌"
            print(f"  {icon} @ {tr['entry_time']}  "
                  f"entry=${tr['entry']:.2f}  exit=${tr['exit']:.2f}  "
                  f"({tr['gain_pct']:+.1f}%)  {tr['exit_reason']}"
                  f"{tr['partial']}  → ${tr['pnl']:+.2f}")
            all_trades.append({**tr, "ticker": t, "day": r["day"], "gap_pct": r["gap_pct"]})

    n_no_signal = len([r for r in valid if not r["trades"]])
    print(f"\n  {n_no_signal} gap-up days had no signal (stock moved before flat top formed)")

    if not all_trades:
        print("\n  No trades triggered across all gap days.")
        print("  → The flat top breakout rarely forms in morning on gap-up stocks.")
        return

    wins   = [t for t in all_trades if t["pnl"] > 0]
    losses = [t for t in all_trades if t["pnl"] <= 0]
    total  = sum(t["pnl"] for t in all_trades)
    wr     = len(wins) / len(all_trades) * 100

    print()
    print("=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    print(f"  Gap-up days in universe : {len(valid)}")
    print(f"  Days with no signal     : {n_no_signal}  ({n_no_signal/len(valid)*100:.0f}%)")
    print(f"  Days that triggered     : {len(set(t['day'] for t in all_trades))}")
    print(f"  Total trades            : {len(all_trades)}")
    print(f"  Winners                 : {len(wins)}")
    print(f"  Losers                  : {len(losses)}")
    print(f"  Win rate                : {wr:.0f}%")
    print(f"  Total P&L               : ${total:+.2f}  (on ${POSITION_DOLLARS:.0f}/trade)")
    if wins:
        aw = sum(t["pnl"] for t in wins) / len(wins)
        print(f"  Avg winner              : ${aw:+.2f}")
    if losses:
        al = sum(t["pnl"] for t in losses) / len(losses)
        print(f"  Avg loser               : ${al:+.2f}")
    if wins and losses:
        rr = abs(sum(t["pnl"] for t in wins)/len(wins)) / abs(sum(t["pnl"] for t in losses)/len(losses))
        ev = (wr/100)*(sum(t["pnl"] for t in wins)/len(wins)) + (1-wr/100)*(sum(t["pnl"] for t in losses)/len(losses))
        print(f"  Win/loss ratio          : {rr:.2f}:1")
        print(f"  Expected value / trade  : ${ev:+.2f}")

    by_reason = {}
    for tr in all_trades:
        by_reason.setdefault(tr["exit_reason"], []).append(tr)
    print()
    for r, ts in sorted(by_reason.items()):
        w = len([t for t in ts if t["pnl"] > 0])
        print(f"  {r:12s}: {len(ts)} trades  {w}/{len(ts)} wins  "
              f"${sum(t['pnl'] for t in ts):+.2f}")

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


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",   type=int,   default=30)
    parser.add_argument("--mingap", type=float, default=15.0)
    parser.add_argument("--maxgap", type=float, default=60.0)
    args = parser.parse_args()

    min_gap = args.mingap / 100
    max_gap = args.maxgap / 100

    print(f"\nScanning {len(UNIVERSE)} tickers over past {args.days} days...")
    print(f"Looking for gap-up days: {args.mingap:.0f}–{args.maxgap:.0f}%  price≥${MIN_PRICE}\n")

    # Step 1: find all gap-up days
    all_gaps = []
    for i, ticker in enumerate(UNIVERSE):
        gaps = find_gap_days(ticker, args.days, min_gap, max_gap)
        if gaps:
            for day, gap_pct, open_price in gaps:
                all_gaps.append((ticker, day, gap_pct, open_price))
        if (i + 1) % 50 == 0:
            print(f"  Scanned {i+1}/{len(UNIVERSE)} tickers — {len(all_gaps)} gap days found so far")

    # De-duplicate (same ticker+day may appear twice from universe dupes)
    seen = set()
    deduped = []
    for item in all_gaps:
        key = (item[0], item[1])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    all_gaps = sorted(deduped, key=lambda x: x[1])

    print(f"\nFound {len(all_gaps)} gap-up days across "
          f"{len(set(x[0] for x in all_gaps))} tickers\n")

    if not all_gaps:
        print("No qualifying gap days found.")
        exit(0)

    print("  All gap days:")
    for ticker, day, gap_pct, open_price in all_gaps:
        print(f"    {ticker:6s}  {day}  gap={gap_pct:+.0f}%  open=${open_price:.2f}")

    # Step 2: run v2 strategy on each
    print(f"\nRunning strategy on {len(all_gaps)} days...\n")
    results = []
    for ticker, day, gap_pct, open_price in all_gaps:
        r = run_backtest_day_v2(ticker, day, gap_pct)
        results.append(r)

    print_report(results)
