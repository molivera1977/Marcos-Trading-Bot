#!/usr/bin/env python3
"""
Historical Gapper Scanner
=========================
Scans a broad universe of small-cap / micro-cap momentum stocks for the
past N trading days, finds the biggest single-day gap-ups (>15%, open<$20,
volume>500k), then runs the full VWAP strategy backtest on those days.

Goal: Learn which setups actually work on the kinds of stocks we trade.

Usage:
  python3 gapper_scanner.py                   # past 20 trading days
  python3 gapper_scanner.py --days 10
  python3 gapper_scanner.py --top 15          # top 15 gappers (default 20)
  python3 gapper_scanner.py --min-gap 20      # 20%+ gap-up only
  python3 gapper_scanner.py --backtest        # run strategy backtest on results
  python3 gapper_scanner.py --days 20 --backtest --top 20
"""

import argparse
import os
import sys
import warnings
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ── Universe — small-cap / micro-cap momentum stocks ─────────────────────────
# These are the types of stocks Kev scans: low float, under $20, with catalysts.
# Mix of known recent movers + established momentum names in the space.
UNIVERSE = [
    # Recent scan-list stocks
    "CAST", "AHMA", "RGNT", "ATPC", "LNKS", "CDT", "APWC", "LPA",
    "WKSP", "TDTH", "WPRT", "GRNQ", "PRTH", "NUVL", "MGRX",

    # Micro-cap biotech/biotech-adjacent frequent flyers
    "ACST", "ACXP", "ADTX", "AEZS", "ALPP", "AMMO", "ANAB",
    "ATNX", "ATXI", "AVCT", "AVTE", "AYRO", "AZRX",
    "BFRI", "BGXX", "BIMI", "BLNK", "BLTX", "BNMV",
    "BNOX", "BNTC", "BOXL", "BRTX",
    "CALT", "CANF", "CASI", "CBAT", "CCTL", "CELZ", "CETX",
    "CFRX", "CGNX", "CLBT", "CLFD", "CLPS", "CLRB", "CLSK",
    "CMND", "CNEY", "CNXA", "COCP", "CODA", "COIN",
    "COMS", "COSG", "COSM", "COWI", "CRKN", "CRMD",
    "CRXT", "CTXR", "CVKD", "CYCC",
    "DARE", "DBGI", "DCGO", "DCRB", "DPRO",
    "EDSA", "EDTK", "EFHT", "ELEV", "ELLO", "ENSC",
    "EVFM", "EVGO", "EVTL", "EVVL", "EWLL",
    "FFIE", "FGEN", "FHTX", "FKWL", "FLGC",
    "FRGT", "FRTX", "FSNB", "FTFT", "FULC",
    "GALT", "GFAI", "GGR", "GLBS", "GLMD",
    "GMET", "GNLN", "GNUS", "GOVX", "GPMT",
    "GREE", "GRIN", "GXII",
    "HALO", "HAPP", "HCDI", "HCWB", "HIHO", "HITI",
    "HMPT", "HOOK", "HPNN", "HPVW", "HRTX", "HTCR",
    "HYMC", "HYPR",
    "IDEX", "IFBD", "IINN", "IMAQ", "IMMP", "IMPP",
    "INBS", "INDO", "INFI", "INFU", "INPX", "INTU",
    "IPIX", "IPSC", "ISIG", "ISPC", "ISPR", "ISCO",
    "ISUN", "ITCI", "IULN", "IXHL",
    "JAGX", "JFBR", "JNVR", "JOVR",
    "KAVL", "KBLB", "KEQU", "KERN", "KGEI", "KGEI",
    "KINDL", "KTTA", "KVUE",
    "LABP", "LAFW", "LAZR", "LCID", "LCTX", "LEAT",
    "LGVN", "LIDR", "LIFW", "LIPO", "LKCO", "LMND",
    "LNTH", "LODE", "LPRO", "LQDA", "LRFC",
    "MACI", "MARA", "MBRX", "MCVT", "MDAI", "MDJH",
    "MDRX", "MEIP", "MGOL", "MGTI", "MICS",
    "MIRO", "MLAC", "MMAT", "MNMD", "MNTS",
    "MOBV", "MODD", "MOGO", "MRIN", "MRKR",
    "MRNA", "MRNS", "MRZM", "MSRT",
    "NCNC", "NKLA", "NLSP", "NMRD", "NMTR",
    "NNVC", "NOEL", "NRSN", "NRXP", "NSTG",
    "NTBL", "NTGR", "NTRB", "NURO", "NVAX",
    "NVCR", "NVNI", "NWBO",
    "OCGN", "OCUP", "OFED", "OHPA", "OIIM",
    "ONDS", "ONVO", "OPCH", "OPOF", "OPTT",
    "ORLA", "ORPH", "OSBC", "OTIC", "OVID",
    "PASG", "PAVS", "PBAX", "PBHC", "PBTS",
    "PCMG", "PDSB", "PETE", "PHGE", "PHIO",
    "PHVS", "PIXY", "PJET", "PKOH", "PLAB",
    "PLUR", "PMVP", "PNTM", "POCI", "PPSI",
    "PRLD", "PRTK", "PRTX", "PRTY", "PSCR",
    "PSLV", "PSQH", "PTPI", "PUCK", "PVBC",
    "RAIL", "RCAT", "RCON", "RDHL", "RDVT",
    "RELI", "REVB", "REZI", "RFIL", "RGEN",
    "RGNX", "RIBT", "RIDE", "RIVN", "RKLY",
    "RLAY", "RLMD", "RMED", "RMNI", "RNER",
    "RNLX", "RQHTF", "RSSS", "RTLR",
    "SBFG", "SBET", "SBEV", "SBIG", "SBOT",
    "SCKT", "SEEL", "SEER", "SESN", "SFOR",
    "SGBX", "SGLY", "SGMO", "SGMT", "SIEB",
    "SING", "SINT", "SIOX", "SISI", "SITO",
    "SKIL", "SKIN", "SKLZ", "SLDB", "SLGL",
    "SLHG", "SLND", "SLNX", "SLRN", "SLXN",
    "SMFL", "SMIT", "SMLR", "SMRT", "SNAP",
    "SNPX", "SNTX", "SOFI", "SOPA", "SOWG",
    "SPGX", "SPHL", "SPKL", "SPNT", "SQNS",
    "SRTS", "SSSS", "STAB", "STAF", "STBZ",
    "STCB", "STEP", "STIX", "STOK", "STPK",
    "STRM", "SVFD", "SVMH", "SVRA", "SVRE",
    "SVST", "SWAG", "SWIR", "SXTC", "SYNA",
    "TAOP", "TARA", "TBLT", "TCBP", "TCMD",
    "TDUP", "TELA", "TENK", "TENS", "TGAA",
    "TGLS", "THAR", "THCP", "THCX", "THMO",
    "THTX", "TILS", "TLGA", "TLRS", "TMDI",
    "TMVW", "TNXP", "TPVG", "TPST", "TPTW",
    "TRAQ", "TRHC", "TRIL", "TRIP", "TRMK",
    "TRMR", "TRRS", "TRST", "TRVI", "TRWH",
    "TSBK", "TSLA", "TTNP", "TTSH", "TVTX",
    "TWOU", "TYME", "TYRA",
    "UBXN", "UGRO", "UHAL", "ULBI", "ULCC",
    "UNFI", "UNMD", "UONE", "UPLD", "UPWK",
    "URA", "URGN", "USAS", "USEG", "USEI",
    "USIO", "USLM", "USPH", "USWS", "UTME",
    "UUUU", "UVSP",
    "VACC", "VAPO", "VCNX", "VCSY", "VECT",
    "VERB", "VERO", "VERY", "VFRM", "VGLS",
    "VICP", "VIOT", "VISL", "VIVE", "VLDR",
    "VLON", "VNRX", "VPPR", "VRCA", "VRME",
    "VRNA", "VRPX", "VSBLTY", "VSTO", "VTGN",
    "VVOS", "VYNT",
    "WATT", "WBEV", "WHLM", "WHLR", "WINC",
    "WISA", "WNEB", "WORX", "WRTC", "WSBF",
    "WSFS", "WSTG", "WTER",
    "XBIO", "XCUR", "XELA", "XELB", "XENE",
    "XENT", "XERS", "XFOR", "XGTI", "XOMA",
    "XPON", "XPOF", "XPON", "XTLB", "XTND",
    "YELL", "YGMZ", "YGTY", "YMAB", "YRCW",
    "YSAC", "YTEN", "YTRA",
    "ZARA", "ZCAR", "ZCNX", "ZEPP", "ZEST",
    "ZETA", "ZIMV", "ZIVO", "ZJYL", "ZKIN",
    "ZKZNG", "ZLAB", "ZMCO", "ZNRG", "ZNTE",
    "ZNTL", "ZSAN", "ZTNO", "ZVIA", "ZVRA",

    # Additional well-known momentum names
    "MULN", "HOLO", "AGRI", "SURG", "AIXI",
    "GFAI", "BURU", "BIVI", "MFON", "EAST",
    "EZFL", "LASE", "CLEU", "CJET", "SRM",
    "FRST", "AEYE", "GFAI", "SIDU", "HTCR",
    "TPVG", "BVNK", "AEAC", "PRPB", "NXU",
    "GREE", "DPSI", "KTTA", "VVPR", "SMFL",
    "HIMS", "NKLA", "LCID", "FSR", "RIDE",
    "HYLN", "XPEV", "LI", "NIO", "BLNK",
    "EVGO", "CHPT", "PTRA", "WKHS",
    "EBON", "MARA", "RIOT", "BTBT", "HUT",
    "CIFR", "BITF", "CLSK", "IREN",
]

# Deduplicate
UNIVERSE = list(dict.fromkeys(UNIVERSE))


# ── Constants matching the bot's strategy ────────────────────────────────────
MIN_GAP_PCT      = 15.0   # minimum gap-up from prev close to qualify
MAX_OPEN_PRICE   = 20.0   # only stocks that opened under $20 (small-cap)
MIN_DAY_VOLUME   = 500_000  # minimum total volume on gap day

# ── Helpers ───────────────────────────────────────────────────────────────────

def last_n_trading_days(n: int) -> list:
    days = []
    d = date.today() - timedelta(days=1)  # start from yesterday
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def batch_daily(tickers: list, start: date, end: date) -> pd.DataFrame:
    """Download daily OHLCV for a list of tickers in one yfinance call."""
    s = start.strftime("%Y-%m-%d")
    e = (end + timedelta(days=1)).strftime("%Y-%m-%d")
    df = yf.download(tickers, start=s, end=e,
                     interval="1d", progress=False, auto_adjust=True,
                     group_by="ticker", threads=True)
    return df


def find_gappers(tickers: list, days: list,
                 min_gap: float, max_open: float, min_vol: int) -> list:
    """
    Scan universe for big gap-up days.
    Returns list of dicts sorted by gap_pct desc.
    """
    print(f"\nDownloading daily data for {len(tickers)} tickers "
          f"({days[0]} → {days[-1]})...")

    # Need one extra day before the window to compute prev_close
    start = days[0] - timedelta(days=5)
    end   = days[-1]

    # Batch in chunks of 100 to avoid yfinance limits
    chunk_size = 100
    all_gaps = []

    for chunk_start in range(0, len(tickers), chunk_size):
        chunk = tickers[chunk_start: chunk_start + chunk_size]
        try:
            raw = yf.download(chunk, start=start.strftime("%Y-%m-%d"),
                              end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
                              interval="1d", progress=False, auto_adjust=True,
                              group_by="ticker", threads=True)
        except Exception as e:
            print(f"  [chunk {chunk_start//chunk_size + 1}] download error: {e}")
            continue

        if raw is None or raw.empty:
            continue

        # Normalize to MultiIndex if single ticker
        if not isinstance(raw.columns, pd.MultiIndex):
            raw = pd.concat({chunk[0]: raw}, axis=1)

        for ticker in chunk:
            try:
                tk_df = raw[ticker].dropna(how="all")
            except KeyError:
                continue
            if tk_df.empty or len(tk_df) < 2:
                continue

            for i in range(1, len(tk_df)):
                row_date = tk_df.index[i].date()
                if row_date not in days:
                    continue

                open_p    = float(tk_df["Open"].iloc[i])
                prev_close = float(tk_df["Close"].iloc[i - 1])
                volume    = float(tk_df["Volume"].iloc[i])
                high_p    = float(tk_df["High"].iloc[i])
                close_p   = float(tk_df["Close"].iloc[i])

                if prev_close <= 0 or open_p <= 0:
                    continue
                if open_p > max_open:
                    continue
                if volume < min_vol:
                    continue

                gap_pct = (open_p - prev_close) / prev_close * 100
                if gap_pct < min_gap:
                    continue

                day_range_pct = (high_p - open_p) / open_p * 100

                all_gaps.append({
                    "ticker":    ticker,
                    "date":      row_date,
                    "prev_close": round(prev_close, 2),
                    "open":      round(open_p, 2),
                    "high":      round(high_p, 2),
                    "close":     round(close_p, 2),
                    "gap_pct":   round(gap_pct, 1),
                    "day_range": round(day_range_pct, 1),
                    "volume":    int(volume),
                })

        print(f"  chunk {chunk_start//chunk_size + 1}/{(len(tickers)-1)//chunk_size + 1} done "
              f"({chunk_start + len(chunk)}/{len(tickers)} tickers)", end="\r")

    print()
    return sorted(all_gaps, key=lambda x: x["gap_pct"], reverse=True)


# ── Backtest (mirrors backtest.py logic) ─────────────────────────────────────

VWAP_PULLBACK_MIN_RUN = 0.05
VWAP_PULLBACK_ZONE    = 0.03
VWAP_VOL_MULTIPLIER   = 2.0
VWAP_CONFIRM_TICKS    = 3
MIN_ABS_VOL           = 15_000
MAX_EXTENSION         = 0.15
POSITION_DOLLARS      = 100.0
TARGET_PCT            = 0.10
STOP_BUFFER           = 0.001
MAX_TRADES_PER_DAY    = 2


def fetch_intraday(ticker: str, day: date):
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
    df["tp"]      = (df["High"] + df["Low"] + df["Close"]) / 3
    df["vwap"]    = (df["tp"] * df["Volume"]).cumsum() / df["Volume"].cumsum()
    df["ma90"]    = df["Close"].rolling(90, min_periods=1).mean()
    df["avg_vol"] = df["Volume"].rolling(30, min_periods=1).mean()
    return df


def simulate_trade(df, entry_i, entry_price, setup_type):
    shares = POSITION_DOLLARS / entry_price
    target = entry_price * (1 + TARGET_PCT)
    half_exited = False
    half_px = 0.0
    remaining = shares

    for j in range(entry_i + 1, len(df)):
        price = float(df["Close"].iloc[j])
        vwap  = float(df["vwap"].iloc[j])
        t_str = df.index[j].strftime("%H:%M")
        is_last = (j == len(df) - 1)

        if is_last or t_str >= "15:30":
            pnl  = (half_px - entry_price) * (shares / 2) if half_exited else 0
            pnl += (price - entry_price) * remaining
            return {"setup": setup_type,
                    "entry_time": df.index[entry_i].strftime("%H:%M"),
                    "entry": entry_price, "exit": price, "exit_reason": "TIME",
                    "pnl": round(pnl, 2),
                    "gain_pct": round((price - entry_price) / entry_price * 100, 2),
                    "partial": f" (half @${half_px:.2f})" if half_exited else ""}

        if not half_exited and price >= target:
            half_px = price
            half_exited = True
            remaining = shares / 2

        if price < vwap * (1 - STOP_BUFFER):
            exit_px = float(df["Open"].iloc[j + 1]) if j + 1 < len(df) else price
            pnl  = (half_px - entry_price) * (shares / 2) if half_exited else 0
            pnl += (exit_px - entry_price) * remaining
            return {"setup": setup_type,
                    "entry_time": df.index[entry_i].strftime("%H:%M"),
                    "entry": entry_price, "exit": exit_px, "exit_reason": "VWAP STOP",
                    "pnl": round(pnl, 2),
                    "gain_pct": round((exit_px - entry_price) / entry_price * 100, 2),
                    "partial": f" (half @${half_px:.2f})" if half_exited else ""}
    return None


def run_strategy(ticker: str, day: date) -> dict:
    df = fetch_intraday(ticker, day)
    if df is None:
        return {"ticker": ticker, "day": day, "note": "no intraday data", "trades": []}

    df = add_indicators(df)
    trades = []
    trade_count = 0
    hw_live = 0.0
    pb_armed = False
    ticks_rec = 0
    ticks_pb = 0

    for i in range(len(df)):
        if trade_count >= MAX_TRADES_PER_DAY:
            break

        price = float(df["Close"].iloc[i])
        vwap  = float(df["vwap"].iloc[i])
        ma90  = float(df["ma90"].iloc[i])
        vol   = float(df["Volume"].iloc[i])
        avg_v = float(df["avg_vol"].iloc[i])

        if vwap <= 0:
            continue

        above_vwap = price > vwap
        pct_above  = (price - vwap) / vwap if above_vwap else 0

        if above_vwap:
            if pct_above >= VWAP_PULLBACK_MIN_RUN:
                hw_live = max(hw_live, price)
            if pct_above <= MAX_EXTENSION:
                ticks_pb += 1
                ticks_rec += 1
            else:
                ticks_pb = 0
                ticks_rec = 0
        else:
            ticks_pb = 0
            ticks_rec = 0
            if hw_live >= vwap * (1 + VWAP_PULLBACK_MIN_RUN):
                gap = (price - vwap) / vwap
                if abs(gap) <= VWAP_PULLBACK_ZONE:
                    pb_armed = True
                elif price < vwap * (1 - VWAP_PULLBACK_ZONE * 2):
                    pb_armed = False
                    hw_live = 0.0

        if not above_vwap or price <= ma90:
            continue

        triggered = False
        setup_type = None

        if pb_armed and ticks_pb == 1 and vol >= MIN_ABS_VOL:
            triggered = True
            setup_type = "PULLBACK BOUNCE"
            pb_armed = False

        elif ticks_rec == VWAP_CONFIRM_TICKS:
            vol_ok = (avg_v == 0 or vol >= avg_v * VWAP_VOL_MULTIPLIER) and vol >= MIN_ABS_VOL
            if vol_ok:
                triggered = True
                setup_type = "RECLAIM+RUN" if hw_live >= vwap * (1 + VWAP_PULLBACK_MIN_RUN) else "RECLAIM"
                ticks_rec = 0

        if triggered:
            result = simulate_trade(df, i, price, setup_type)
            if result:
                trades.append(result)
                trade_count += 1

    open_p  = float(df["Open"].iloc[0])
    close_p = float(df["Close"].iloc[-1])
    high_p  = float(df["High"].max())

    return {
        "ticker": ticker,
        "day":    day,
        "open":   open_p,
        "high":   high_p,
        "close":  close_p,
        "change": (close_p - open_p) / open_p * 100,
        "trades": trades,
    }


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_gapper_table(gaps: list, top_n: int):
    print(f"\n{'='*72}")
    print(f"  TOP {min(top_n, len(gaps))} GAP-UPS  (past scan window)")
    print(f"{'='*72}")
    print(f"  {'#':>2}  {'TICKER':6}  {'DATE':10}  {'GAP%':>6}  {'OPEN':>6}  "
          f"{'HIGH':>6}  {'CLOSE':>6}  {'RANGE':>6}  {'VOLUME':>10}")
    print(f"  {'─'*66}")
    for idx, g in enumerate(gaps[:top_n], 1):
        print(f"  {idx:>2}  {g['ticker']:6}  {g['date']}  "
              f"{g['gap_pct']:>+5.1f}%  ${g['open']:>5.2f}  "
              f"${g['high']:>5.2f}  ${g['close']:>5.2f}  "
              f"{g['day_range']:>+5.1f}%  {g['volume']:>10,}")
    print(f"{'='*72}\n")


def print_backtest_summary(all_results: list):
    all_trades = []

    print(f"\n{'='*72}")
    print("  STRATEGY BACKTEST ON GAP-UP DAYS")
    print(f"{'='*72}")

    for r in all_results:
        t   = r["ticker"]
        day = r["day"].strftime("%a %b %d")
        if "note" in r:
            print(f"\n  {t} {day}: {r['note']}")
            continue

        chg = f"{r['change']:+.1f}%"
        print(f"\n  {'─'*66}")
        print(f"  {t}  {day}  open=${r['open']:.2f}  "
              f"high=${r['high']:.2f}  close=${r['close']:.2f}  ({chg})")

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

    if not all_trades:
        print("\n  No entries triggered on any gap-up day.")
        return

    wins   = [t for t in all_trades if t["pnl"] > 0]
    losses = [t for t in all_trades if t["pnl"] <= 0]
    total  = sum(t["pnl"] for t in all_trades)
    wr     = len(wins) / len(all_trades) * 100

    print(f"\n{'='*72}")
    print("  SUMMARY")
    print(f"{'='*72}")
    print(f"  Trades   : {len(all_trades)}  |  Wins: {len(wins)}  |  Losses: {len(losses)}")
    print(f"  Win rate : {wr:.0f}%")
    print(f"  Total P&L: ${total:+.2f}  (on ${POSITION_DOLLARS:.0f}/trade)")
    if wins:
        print(f"  Avg win  : ${sum(t['pnl'] for t in wins)/len(wins):+.2f}")
    if losses:
        print(f"  Avg loss : ${sum(t['pnl'] for t in losses)/len(losses):+.2f}")

    by_setup = {}
    for tr in all_trades:
        by_setup.setdefault(tr["setup"], []).append(tr)
    print()
    for s, ts in sorted(by_setup.items()):
        w = len([t for t in ts if t["pnl"] > 0])
        print(f"  {s:16s}: {len(ts)} trades  {w}/{len(ts)} wins  "
              f"${sum(t['pnl'] for t in ts):+.2f}")

    # By ticker
    by_ticker = {}
    for tr in all_trades:
        by_ticker.setdefault(tr["ticker"], []).append(tr)
    print()
    print("  By ticker (sorted by P&L):")
    for t, ts in sorted(by_ticker.items(), key=lambda x: sum(t["pnl"] for t in x[1]), reverse=True):
        w = len([tr for tr in ts if tr["pnl"] > 0])
        print(f"    {t:6s}: {len(ts)} trades  {w}/{len(ts)} wins  "
              f"${sum(tr['pnl'] for tr in ts):+.2f}")
    print(f"{'='*72}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Historical Gapper Scanner + Backtest")
    parser.add_argument("--days",      type=int,   default=20,
                        help="Look-back window in trading days (default: 20 = ~1 month)")
    parser.add_argument("--top",       type=int,   default=20,
                        help="Number of top gappers to display (default: 20)")
    parser.add_argument("--min-gap",   type=float, default=MIN_GAP_PCT,
                        help=f"Minimum gap-up %% to qualify (default: {MIN_GAP_PCT})")
    parser.add_argument("--max-open",  type=float, default=MAX_OPEN_PRICE,
                        help=f"Max open price (default: ${MAX_OPEN_PRICE})")
    parser.add_argument("--min-vol",   type=int,   default=MIN_DAY_VOLUME,
                        help=f"Min daily volume (default: {MIN_DAY_VOLUME:,})")
    parser.add_argument("--backtest",  action="store_true",
                        help="Run strategy backtest on top gap-up days")
    parser.add_argument("--tickers",   nargs="+", default=None,
                        help="Override universe with specific tickers")
    args = parser.parse_args()

    universe = [t.upper() for t in args.tickers] if args.tickers else UNIVERSE
    days     = last_n_trading_days(args.days)

    print(f"\nScanning {len(universe)} tickers | {args.days} trading days "
          f"({days[0]} → {days[-1]})")
    print(f"Filters: gap ≥{args.min_gap}%  open<${args.max_open}  vol>{args.min_vol:,}")

    gaps = find_gappers(
        universe, days,
        min_gap=args.min_gap,
        max_open=args.max_open,
        min_vol=args.min_vol,
    )

    if not gaps:
        print("\nNo gappers found matching your criteria.")
        sys.exit(0)

    print(f"\nFound {len(gaps)} gap-up days across {len(set(g['ticker'] for g in gaps))} tickers")
    print_gapper_table(gaps, args.top)

    if args.backtest:
        top_gaps = gaps[:args.top]
        print(f"Running intraday strategy backtest on top {len(top_gaps)} gap days...")
        results = []
        for idx, g in enumerate(top_gaps, 1):
            print(f"  [{idx}/{len(top_gaps)}] {g['ticker']} {g['date']}  "
                  f"(gap: {g['gap_pct']:+.1f}%)", end="\r")
            r = run_strategy(g["ticker"], g["date"])
            results.append(r)
        print()
        print_backtest_summary(results)
    else:
        print("Run with --backtest to simulate the VWAP strategy on these gap days.")
        print(f"Example: python3 gapper_scanner.py --days {args.days} --backtest --top {args.top}")
