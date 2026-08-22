#!/usr/bin/env python3
"""
THE FERRY — build 10s bars into data/universe/bars10s (8/21, Marcos: "let's fucking ferry the
shit already... Isn't it automated????")

IT WAS NOT AUTOMATED. No script referenced bars10s outside killtests; the existing files were
built by hand (8/14's are stamped Aug 14 18:31). That is why the debt kept reappearing in every
session's docket. This file is the ferry, and it is idempotent — safe to re-run any day.

WHY THE CACHE IS THE BINDING CONSTRAINT: the 10s cache is the ONLY source a lane-design backtest
can read. Marcos's 8/21 ruling moved the era boundary to ~8/13-8/14 ("we started REALLY designing
this system last Thursday; anything before should be forgotten"). Post-boundary coverage before
this ferry: 8/14 = 12 name-files, 8/17 = 9, 8/18 = 210, and 8/19/8/20/8/21 = ZERO. So the
trustworthy sample was effectively one day plus scraps.

SOURCE: Alpaca /v2/stocks/{sym}/trades (SIP), bucketed to 10s — the same builder every
real-cost study this week used, and the same aggregation the live feeds perform. Bars are
stamped in UTC with a trailing Z, matching the existing cache exactly (the killtests convert
UTC->ET themselves; see the 8/19 class defect where string-comparing cache times to ET windows
shifted everything -4h).

UNIVERSE per day: every ticker that appears in that day's decision archive — i.e. every name the
bot actually watched. That is the honest universe: it is what the system saw, not a hand-picked
list. Names with fewer than MIN_TICKS prints are skipped and counted (dead tape helps nobody).

FORMAT written, byte-compatible with the existing files:
  {"sym": SYM, "date": "YYYY-MM-DD", "n_ticks": <trade count>, "bars": [
     {"time": "...Z", "open": f, "high": f, "low": f, "close": f, "volume": f}, ...]}

USAGE:  python3 ferry_bars10s.py 2026-08-19 2026-08-20 2026-08-21
        python3 ferry_bars10s.py            # defaults to the last 3 weekdays
Existing files are SKIPPED unless FERRY_OVERWRITE=1 (idempotent by design — a re-run must never
silently rewrite tape a study already used).
"""
import collections
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "universe", "bars10s")
BOARD = "https://zestful-intuition-production-b16a.up.railway.app"
CADENCE = 10
MIN_TICKS = 200
SESSION_FROM, SESSION_TO = "04:00:00", "20:00:00"   # full ET session incl. pre/post

AK = os.environ.get("AK", "")
AS = os.environ.get("AS", "")
if not AK:
    kv = subprocess.run(["railway", "variables", "--service", "Marcos-Trading-Bot", "--kv"],
                        capture_output=True, text=True).stdout
    for ln in kv.splitlines():
        if ln.startswith("ALPACA_KEY="):
            AK = ln.split("=", 1)[1].strip()
        if ln.startswith("ALPACA_SECRET="):
            AS = ln.split("=", 1)[1].strip()
HDR = {"APCA-API-KEY-ID": AK, "APCA-API-SECRET-KEY": AS}


def universe(day):
    """Every ticker the bot watched that day — the honest universe."""
    try:
        rows = json.load(urllib.request.urlopen(
            f"{BOARD}/api/decisions_archive?date={day}&limit=50000&key=marcos2026",
            timeout=60)).get("rows") or []
    except Exception as e:
        print(f"  archive fetch failed for {day}: {e}")
        return []
    return sorted({str(r.get("ticker")) for r in rows
                   if r.get("ticker") and str(r.get("ticker")) not in ("None", "_WATCH")})


def trades(sym, day):
    s = (dt.datetime.fromisoformat(f"{day}T{SESSION_FROM}") + dt.timedelta(hours=4)).isoformat() + "Z"
    e = (dt.datetime.fromisoformat(f"{day}T{SESSION_TO}") + dt.timedelta(hours=4)).isoformat() + "Z"
    out, page = [], None
    for _ in range(60):
        q = {"start": s, "end": e, "limit": 10000, "feed": "sip"}
        if page:
            q["page_token"] = page
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(
                f"https://data.alpaca.markets/v2/stocks/{sym}/trades?" + urllib.parse.urlencode(q),
                headers=HDR), timeout=60))
        except Exception:
            break
        for x in r.get("trades") or []:
            p = float(x.get("p") or 0)
            if p > 0:
                out.append((str(x["t"]), p, float(x.get("s") or 0)))
        page = r.get("next_page_token")
        if not page:
            break
    return out


def bucket(tr):
    """Aggregate the trades tape into 10s OHLCV, keyed by the bucket's UTC epoch."""
    b = {}
    for ts, p, sz in tr:
        ep = dt.datetime.fromisoformat(ts[:19] + "+00:00").timestamp()
        k = int(ep // CADENCE) * CADENCE
        d = b.get(k)
        if d is None:
            b[k] = {"open": p, "high": p, "low": p, "close": p, "volume": sz}
        else:
            d["high"] = max(d["high"], p)
            d["low"] = min(d["low"], p)
            d["close"] = p
            d["volume"] += sz
    return [dict(time=dt.datetime.utcfromtimestamp(k).strftime("%Y-%m-%dT%H:%M:%SZ"), **b[k])
            for k in sorted(b)]


def main(days):
    os.makedirs(OUT, exist_ok=True)
    ow = os.environ.get("FERRY_OVERWRITE") == "1"
    grand = collections.Counter()
    for day in days:
        syms = universe(day)
        print(f"\n=== {day}: {len(syms)} tickers watched ===", flush=True)
        if not syms:
            continue
        wrote = skipped = thin = 0
        for i, sym in enumerate(syms, 1):
            path = os.path.join(OUT, f"{day}_{sym}.json")
            if os.path.exists(path) and not ow:
                skipped += 1
                continue
            tr = trades(sym, day)
            if len(tr) < MIN_TICKS:
                thin += 1
                if i % 25 == 0:
                    print(f"  [{i}/{len(syms)}] wrote {wrote} thin {thin} skip {skipped}", flush=True)
                continue
            bars = bucket(tr)
            with open(path, "w") as f:
                json.dump({"sym": sym, "date": day, "n_ticks": len(tr), "bars": bars}, f)
            wrote += 1
            if i % 25 == 0:
                print(f"  [{i}/{len(syms)}] wrote {wrote} thin {thin} skip {skipped}", flush=True)
        print(f"  {day} DONE — wrote {wrote}, thin/skipped-for-tape {thin}, already-present {skipped}")
        grand["wrote"] += wrote
        grand["thin"] += thin
        grand["present"] += skipped
    print(f"\nFERRY COMPLETE — wrote {grand['wrote']} files, {grand['thin']} thin, "
          f"{grand['present']} already present")
    have = sorted({f[:10] for f in os.listdir(OUT) if f.endswith(".json")})
    print(f"cache now covers {len(have)} days; latest: {have[-6:]}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        d, args = dt.date(2026, 8, 21), []
        while len(args) < 3:
            if d.weekday() < 5:
                args.append(d.isoformat())
            d -= dt.timedelta(days=1)
        args = sorted(args)
    sys.exit(main(args))
