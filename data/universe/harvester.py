#!/usr/bin/env python3
"""RUNNER-UNIVERSE HARVESTER v1 (8/14, Marcos: "do the universe harvester now")
Phase 1: sweep daily bars for ALL active US equities (NASDAQ/NYSE/AMEX) over the window,
         find runner-days: prev_close $0.30-$30, intraday gain (high vs prev close) >= 40%,
         dollar volume >= $2M. Top 12 per day -> manifest.json
Phase 2: for each runner-day (newest first, cap via MAX_TICK_DAYS), pull raw SIP ticks
         (paged) 04:00-20:00 ET and aggregate to 10s bars -> bars10s/DATE_TICKER.json
Resumable: existing files skipped. Read-only REST. Throttled ~5 req/s.
"""
import json, os, sys, time, urllib.request, urllib.parse, datetime as dt
ROOT = os.path.dirname(os.path.abspath(__file__))
AK, AS_ = os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"]
H = {"APCA-API-KEY-ID": AK, "APCA-API-SECRET-KEY": AS_}
START, END = "2026-05-15", "2026-08-13"
MAX_TICK_DAYS = int(os.environ.get("MAX_TICK_DAYS", "150"))
def get(u, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(u, headers=H)
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:
            if i == tries-1: raise
            time.sleep(3*(i+1))
def log(m): print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)

# ---------- phase 1 ----------
mpath = os.path.join(ROOT, "manifest.json")
if not os.path.exists(mpath):
    log("phase1: fetching asset universe...")
    assets = []
    a = get("https://paper-api.alpaca.markets/v2/assets?status=active&asset_class=us_equity")
    for x in a:
        if x.get("exchange") in ("NASDAQ","NYSE","AMEX") and x.get("tradable"):
            assets.append(x["symbol"])
    log(f"phase1: {len(assets)} tradable symbols")
    runners = {}   # date -> list of {sym, gain, prev_c, dvol}
    CH = 200
    for ci in range(0, len(assets), CH):
        chunk = assets[ci:ci+CH]
        syms = ",".join(chunk)
        url = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={urllib.parse.quote(syms)}"
               f"&timeframe=1Day&start={START}&end={END}&feed=sip&limit=10000&adjustment=raw")
        page = None
        prev_close = {}
        while True:
            u = url + (f"&page_token={page}" if page else "")
            try: r = get(u)
            except Exception as e:
                log(f"  chunk {ci} error {e}"); break
            for sym, bars in (r.get("bars") or {}).items():
                for b in bars:
                    d = str(b["t"])[:10]; pc = prev_close.get(sym)
                    if pc and 0.30 <= pc <= 30.0:
                        gain = (float(b["h"]) - pc)/pc*100.0
                        dvol = float(b["v"])*float(b["c"])
                        if gain >= 40.0 and dvol >= 2_000_000:
                            runners.setdefault(d, []).append(
                                {"sym": sym, "gain": round(gain,1), "prev_c": pc,
                                 "close": float(b["c"]), "dvol": round(dvol)})
                    prev_close[sym] = float(b["c"])
            page = r.get("next_page_token")
            if not page: break
        if (ci//CH) % 10 == 0: log(f"phase1: {ci}/{len(assets)} symbols swept, {sum(len(v) for v in runners.values())} runner-days so far")
        time.sleep(0.25)
    manifest = {d: sorted(v, key=lambda x:-x["gain"])[:12] for d,v in runners.items()}
    json.dump(manifest, open(mpath,"w"), indent=1)
    log(f"phase1 DONE: {sum(len(v) for v in manifest.values())} runner-days across {len(manifest)} dates -> manifest.json")
else:
    manifest = json.load(open(mpath))
    log(f"phase1: manifest exists ({sum(len(v) for v in manifest.values())} runner-days) — skipping")

# ---------- phase 2 ----------
todo = []
for d in sorted(manifest, reverse=True):
    for r in manifest[d]:
        todo.append((d, r["sym"]))
done = 0
for d, sym in todo:
    if done >= MAX_TICK_DAYS: break
    out = os.path.join(ROOT, "bars10s", f"{d}_{sym}.json")
    if os.path.exists(out): continue
    s_utc = f"{d}T08:00:00Z"; e_utc = f"{d}T24:00:00Z".replace("T24","T23:59:59".join([""]*0) or "T23:59:59")
    e_utc = f"{d}T23:59:59Z"
    agg = {}   # bucket_ts -> [o,h,l,c,v]
    page = None; n_ticks = 0
    try:
        while True:
            u = (f"https://data.alpaca.markets/v2/stocks/{sym}/trades?start={s_utc}&end={e_utc}"
                 f"&limit=10000&feed=sip" + (f"&page_token={page}" if page else ""))
            r = get(u)
            for t in (r.get("trades") or []):
                ts = str(t["t"]); px = float(t["p"]); szv = float(t.get("s") or 0)
                sec = ts[:18] + ("0" if ts[18] < "5" else "5") if False else ts[:18]+"0"
                # 10s bucket: zero the last digit of seconds
                b = agg.get(sec)
                if b is None: agg[sec] = [px, px, px, px, szv]
                else:
                    b[1]=max(b[1],px); b[2]=min(b[2],px); b[3]=px; b[4]+=szv
                n_ticks += 1
            page = r.get("next_page_token")
            if not page: break
            time.sleep(0.15)
        bars = [{"time": k+"Z", "open": v[0], "high": v[1], "low": v[2], "close": v[3], "volume": v[4]}
                for k, v in sorted(agg.items())]
        json.dump({"sym": sym, "date": d, "n_ticks": n_ticks, "bars": bars}, open(out,"w"))
        done += 1
        log(f"phase2 [{done}/{MAX_TICK_DAYS}] {d} {sym}: {n_ticks} ticks -> {len(bars)} 10s bars")
    except Exception as e:
        log(f"phase2 {d} {sym} FAILED: {e}")
    time.sleep(0.2)
log(f"harvester run complete: {done} new runner-days cached; resumable (rerun to continue)")
