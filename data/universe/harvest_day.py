#!/usr/bin/env python3
"""HARVEST ONE DAY — the missing nightly step (8/18)

WHY THIS EXISTS
  `harvester.py` is a ONE-SHOT BACKFILL: START/END are hardcoded 2026-05-15..2026-08-13 and it
  short-circuits phase 1 whenever manifest.json exists. Nothing maintains data/universe/bars10s
  after that window. Verified 8/18: the cache holds 738 name-days ending 2026-08-17 and ZERO
  files for 2026-08-18, with the newest files' mtimes stuck at Aug 17 11:33.

  That is not cosmetic. Every kill-test, wall and counterfactual in data/killtests reads this
  cache, so a cache that silently stops advancing means the studies quietly stop seeing recent
  tape while still reporting confident hold-out numbers. It also BLOCKS the open CDTG defect:
  adjudicating the 52% session_vwap disagreement (kevseq 7.11 vs ma_pullback 4.6719, same
  ticker, same second) needs 2026-08-18_CDTG.json, which does not exist.

WHAT IT DOES
  Pulls raw SIP trades 08:00-23:59 UTC for the given date and symbols, aggregates to 10s bars,
  and writes bars10s/DATE_SYM.json in the EXACT schema harvester.py phase 2 writes
  ({"sym","date","n_ticks","bars":[{time,open,high,low,close,volume}]}) so every existing
  reader works unchanged. Existing files are skipped — resumable, same as the harvester.

USAGE
  railway run python3 data/universe/harvest_day.py 2026-08-18 CDTG EJH SXTC ...
  (railway run injects ALPACA_KEY/ALPACA_SECRET from the service; no secret is printed here.)

  With no symbols it harvests the day's TRADED names from the dashboard book, which is the set
  a post-mortem actually needs.

LIMITS: read-only REST, throttled. This does NOT replace a scheduled nightly harvest — it is the
manual tool for the day you need. The scheduling gap is logged as an open item, not fixed here.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(ROOT, "bars10s")
try:
    AK, AS_ = os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"]
except KeyError:
    sys.exit("ALPACA_KEY/ALPACA_SECRET not in env — run under `railway run` so the service "
             "supplies them (never paste them on a command line).")
H = {"APCA-API-KEY-ID": AK, "APCA-API-SECRET-KEY": AS_}


def log(m):
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def get(u, tries=4):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def traded_symbols(date):
    """The names the bot actually touched that day — the post-mortem set."""
    req = urllib.request.Request(
        f"https://zestful-intuition-production-b16a.up.railway.app/api/trades?date={date}",
        headers={"X-Dashboard-Secret": os.environ.get("DASHBOARD_SECRET", "marcos2026")})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    rows = d if isinstance(d, list) else (d.get("trades") or d.get("data") or [])
    return sorted({r.get("ticker") for r in rows if r.get("ticker")})


def harvest(date, sym):
    out = os.path.join(OUTDIR, f"{date}_{sym}.json")
    if os.path.exists(out):
        log(f"{date} {sym}: exists, skip")
        return False
    agg, page, n = {}, None, 0
    while True:
        u = (f"https://data.alpaca.markets/v2/stocks/{sym}/trades"
             f"?start={date}T08:00:00Z&end={date}T23:59:59Z&limit=10000&feed=sip"
             + (f"&page_token={page}" if page else ""))
        r = get(u)
        for t in (r.get("trades") or []):
            ts = str(t["t"])
            sec = ts[:18] + "0"                      # 10s bucket, same rule as harvester.py
            px, szv = float(t["p"]), float(t.get("s") or 0)
            b = agg.get(sec)
            if b is None:
                agg[sec] = [px, px, px, px, szv]
            else:
                b[1] = max(b[1], px); b[2] = min(b[2], px); b[3] = px; b[4] += szv
            n += 1
        page = r.get("next_page_token")
        if not page:
            break
        time.sleep(0.15)
    bars = [{"time": k + "Z", "open": v[0], "high": v[1], "low": v[2], "close": v[3], "volume": v[4]}
            for k, v in sorted(agg.items())]
    os.makedirs(OUTDIR, exist_ok=True)
    json.dump({"sym": sym, "date": date, "n_ticks": n, "bars": bars}, open(out, "w"))
    log(f"{date} {sym}: {n} ticks -> {len(bars)} 10s bars")
    return True


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: harvest_day.py YYYY-MM-DD [SYM ...]")
    date = sys.argv[1]
    syms = sys.argv[2:] or traded_symbols(date)
    log(f"harvesting {len(syms)} symbol(s) for {date}: {', '.join(syms)}")
    made = 0
    for s in syms:
        try:
            made += bool(harvest(date, s))
        except Exception as e:
            log(f"{date} {s} FAILED: {e}")
        time.sleep(0.2)
    log(f"done: {made} new file(s) in {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
