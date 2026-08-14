#!/usr/bin/env python3
"""Quartermaster ferry 8/14: fill 2026-08-14 (all movers) + 2026-07-27 stragglers
(STAK, MTNB, NXTC). MERGE-ONLY manifest update: adds keys/entries, never removes.
Aggregation copied verbatim from harvester.py phase 2 (10s bucket = zero last sec digit).
AFTER-STATE: manifest.json gains a '2026-08-14' key + up to 3 appended 2026-07-27 rows;
bars10s/ gains new DATE_TICKER.json files. Nothing is deleted or overwritten.
"""
import json, os, time, urllib.request, urllib.parse, datetime as dt
ROOT = os.path.dirname(os.path.abspath(__file__))
AK, AS_ = os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"]
H = {"APCA-API-KEY-ID": AK, "APCA-API-SECRET-KEY": AS_}
def get(u, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(u, headers=H)
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception:
            if i == tries-1: raise
            time.sleep(3*(i+1))
def log(m): print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)

TARGETS = {
    "2026-08-14": ["MF","WETO","LBGJ","AKAN","BOXL","XHG","DFSC","HAO","GIPR","LEXX","TMS","BANL"],
    "2026-07-27": ["STAK","MTNB","NXTC"],
}
PREV = {"2026-08-14": "2026-08-13", "2026-07-27": "2026-07-24"}

mpath = os.path.join(ROOT, "manifest.json")
manifest = json.load(open(mpath))

# ---- manifest entries from daily bars (same fields as harvester phase 1) ----
for d, syms in TARGETS.items():
    have = {r["sym"] for r in manifest.get(d, [])}
    need = [s for s in syms if s not in have]
    if not need:
        log(f"{d}: manifest already has all targets"); continue
    q = urllib.parse.quote(",".join(need))
    url = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={q}"
           f"&timeframe=1Day&start={PREV[d]}&end={d}&feed=sip&limit=10000&adjustment=raw")
    r = get(url)
    rows = []
    for sym, bars in (r.get("bars") or {}).items():
        by = {str(b["t"])[:10]: b for b in bars}
        b, pb = by.get(d), by.get(PREV[d])
        if not b:
            log(f"{d} {sym}: NO daily bar — skipped from manifest"); continue
        pc = float(pb["c"]) if pb else None
        gain = round((float(b["h"])-pc)/pc*100.0, 1) if pc else None
        rows.append({"sym": sym, "gain": gain, "prev_c": pc,
                     "close": float(b["c"]), "dvol": round(float(b["v"])*float(b["c"]))})
    got = {x["sym"] for x in rows}
    for s in need:
        if s not in got: log(f"{d} {s}: no data returned")
    manifest.setdefault(d, []).extend(sorted(rows, key=lambda x: -(x["gain"] or 0)))
    log(f"{d}: appended {len(rows)} manifest rows")
json.dump(manifest, open(mpath, "w"), indent=1)
log("manifest merged + written")

# ---- phase 2: ticks -> 10s bars (verbatim harvester aggregation) ----
for d, syms in TARGETS.items():
    for sym in dict.fromkeys(syms):
        out = os.path.join(ROOT, "bars10s", f"{d}_{sym}.json")
        if os.path.exists(out): continue
        s_utc = f"{d}T08:00:00Z"; e_utc = f"{d}T23:59:59Z"
        agg = {}; page = None; n_ticks = 0
        try:
            while True:
                u = (f"https://data.alpaca.markets/v2/stocks/{sym}/trades?start={s_utc}&end={e_utc}"
                     f"&limit=10000&feed=sip" + (f"&page_token={page}" if page else ""))
                r = get(u)
                for t in (r.get("trades") or []):
                    ts = str(t["t"]); px = float(t["p"]); szv = float(t.get("s") or 0)
                    sec = ts[:18]+"0"
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
            json.dump({"sym": sym, "date": d, "n_ticks": n_ticks, "bars": bars}, open(out, "w"))
            log(f"{d} {sym}: {n_ticks} ticks -> {len(bars)} 10s bars")
        except Exception as e:
            log(f"{d} {sym} FAILED: {e}")
        time.sleep(0.2)
log("ferry complete")
