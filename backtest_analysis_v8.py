#!/usr/bin/env python3
"""
Backtest v8 — Extended Analysis
Loads /tmp/webull_backtest_v8_results.json and prints per-year diagnostics.
Run this on Railway with START_APP=backtest_analysis_v8.py.
"""

import json
import sys
from collections import defaultdict

RESULTS_FILE = "/tmp/webull_backtest_v8_results.json"

try:
    with open(RESULTS_FILE) as f:
        results = json.load(f)
    print(f"✅  Loaded {len(results)} records from {RESULTS_FILE}")
except FileNotFoundError:
    print(f"❌  {RESULTS_FILE} not found — re-run webull_backtest_v8.py first")
    sys.exit(1)

all_trades = []
for r in results:
    for t in r.get("trades", []):
        year = str(r["day"])[:4]
        all_trades.append({
            **t,
            "ticker":  r["ticker"],
            "day":     r["day"],
            "gap_pct": r.get("gap_pct", 0),
            "year":    year,
        })

print(f"Total trades: {len(all_trades)}\n")

by_year = defaultdict(list)
for t in all_trades:
    by_year[t["year"]].append(t)

SEP = "=" * 80

# ── Per-year detailed breakdown ───────────────────────────────────────────────
print(SEP)
print("  PER-YEAR DETAILED STATS")
print(SEP)
hdr = f"{'Year':<6} {'N':>4} {'WR%':>5} {'AvgWin':>8} {'AvgLoss':>9} {'W/L':>6} {'Total':>8} {'AvgGap%':>8} {'AvgEntry':>9}"
print(hdr)
print("-" * len(hdr))

for year in sorted(by_year):
    ts     = by_year[year]
    wins   = [t for t in ts if t["pnl"] > 0]
    losses = [t for t in ts if t["pnl"] <= 0]
    aw     = sum(t["pnl"] for t in wins)   / len(wins)   if wins   else 0
    al     = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
    wl     = abs(aw / al) if al else 0
    total  = sum(t["pnl"] for t in ts)
    wr     = len(wins) / len(ts) * 100
    avg_gap   = sum(t["gap_pct"] for t in ts) / len(ts)
    avg_entry = sum(t.get("entry", 0) for t in ts) / len(ts)
    print(f"{year:<6} {len(ts):>4} {wr:>5.0f}% {aw:>+8.2f} {al:>+9.2f} {wl:>6.2f} {total:>+8.2f} {avg_gap:>8.1f}% {avg_entry:>9.2f}")

# ── Per-year exit reason breakdown ────────────────────────────────────────────
print(f"\n{SEP}")
print("  EXIT REASON BY YEAR")
print(SEP)

for year in sorted(by_year):
    ts = by_year[year]
    by_reason = defaultdict(list)
    for t in ts:
        by_reason[t.get("exit_reason", "?")].append(t)
    line_parts = []
    for reason, rts in sorted(by_reason.items()):
        w = len([t for t in rts if t["pnl"] > 0])
        line_parts.append(f"{reason}: {len(rts)} trades {w/len(rts)*100:.0f}%WR ${sum(t['pnl'] for t in rts):+.2f}")
    print(f"  {year}: " + " | ".join(line_parts))

# ── Per-year avg gain% for wins vs losses ─────────────────────────────────────
print(f"\n{SEP}")
print("  AVG GAIN% (move from entry to exit price) BY YEAR")
print(SEP)
print(f"{'Year':<6} {'WinGain%':>9} {'LossGain%':>10} {'Diff':>8}")
print("-" * 38)

for year in sorted(by_year):
    ts   = by_year[year]
    wins = [t for t in ts if t["pnl"] > 0]
    loss = [t for t in ts if t["pnl"] <= 0]
    awg  = sum(t.get("gain_pct", 0) for t in wins) / len(wins) if wins else 0
    alg  = sum(t.get("gain_pct", 0) for t in loss) / len(loss) if loss else 0
    print(f"{year:<6} {awg:>+9.2f}% {alg:>+10.2f}% {awg-alg:>+8.2f}%")

# ── 2026 individual trades ────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  2026 INDIVIDUAL TRADES")
print(SEP)
trades_2026 = sorted(by_year.get("2026", []), key=lambda t: t["day"])
print(f"{'Date':<12} {'Ticker':<8} {'Gap%':>5} {'Entry':>7} {'Exit':>7} {'Gain%':>7} {'PnL':>7} {'Reason':<16} {'Partial'}")
print("-" * 85)
for t in trades_2026:
    win_flag = "✅" if t["pnl"] > 0 else "❌"
    print(f"{win_flag} {t['day']:<10} {t['ticker']:<8} {t['gap_pct']:>4.0f}% "
          f"${t.get('entry', 0):>6.2f} ${t.get('exit', 0):>6.2f} "
          f"{t.get('gain_pct', 0):>+7.2f}% ${t['pnl']:>+6.2f}  "
          f"{t.get('exit_reason','?'):<16} {t.get('partial','')}")

# ── Top winners overall (regardless of year) ─────────────────────────────────
print(f"\n{SEP}")
print("  TOP 10 WINNERS (ALL YEARS)")
print(SEP)
sorted_wins = sorted([t for t in all_trades if t["pnl"] > 0], key=lambda t: -t["pnl"])
for t in sorted_wins[:10]:
    print(f"  {t['day']}  {t['ticker']:<8} gap={t['gap_pct']:>4.0f}%  "
          f"entry=${t.get('entry',0):.2f}  gain={t.get('gain_pct',0):>+.2f}%  "
          f"pnl=${t['pnl']:+.2f}  {t.get('exit_reason','?')}  {t.get('partial','')}")

print(f"\n{SEP}")
print("  TOP 10 LOSERS (ALL YEARS)")
print(SEP)
sorted_loss = sorted([t for t in all_trades if t["pnl"] <= 0], key=lambda t: t["pnl"])
for t in sorted_loss[:10]:
    print(f"  {t['day']}  {t['ticker']:<8} gap={t['gap_pct']:>4.0f}%  "
          f"entry=${t.get('entry',0):.2f}  gain={t.get('gain_pct',0):>+.2f}%  "
          f"pnl=${t['pnl']:+.2f}  {t.get('exit_reason','?')}")

print(f"\n{SEP}")
print(f"  Done — analysis complete")
print(SEP)
