#!/usr/bin/env python3
"""STEP 1 — pull raw SIP ticks + NBBO quotes for precursor windows.
Cohorts:
  U  = top-100 universe legs by gain (rocket_anatomy rows): [t-180s, t+60s]
  UC = 100 random contrast windows on same name-days, >=20 min from any leg
  K  = Kev picks (kev_watchlist API): FULL-DAY trades 11:00Z-20:00Z, then quotes only around
       detected events (legs >=25%/<=5min, pushes >=10%/<=5min) + contrast windows.
Cache: data/universe/ticks_precursor/{trades|quotes}/{date}_{sym}_{startZ}_{endZ}.json.gz
Times in rows JSON are UTC.
"""
import os, sys, json, gzip, time, random, datetime as dt, subprocess, concurrent.futures as cf
import requests
ROOT = "/Users/marcosolivera/Desktop/Marcos-Trading-Bot"
CACHE = f"{ROOT}/data/universe/ticks_precursor"
os.makedirs(f"{CACHE}/trades", exist_ok=True); os.makedirs(f"{CACHE}/quotes", exist_ok=True)
KEY = os.environ.get("ALPACA_KEY"); SEC = os.environ.get("ALPACA_SECRET")
if not KEY:
    kv = subprocess.run(["railway", "variables", "--service", "Marcos-Trading-Bot", "--kv"], capture_output=True, text=True, cwd=ROOT).stdout
    for ln in kv.splitlines():
        if ln.startswith("ALPACA_KEY="): KEY = ln.split("=", 1)[1].strip()
        if ln.startswith("ALPACA_SECRET="): SEC = ln.split("=", 1)[1].strip()
H = {"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SEC}
S = requests.Session()

def fetch(kind, sym, start, end):
    """kind='trades'|'quotes'; start/end ISO Z strings. Cached. Returns list."""
    fn = f"{CACHE}/{kind}/{start[:10]}_{sym}_{start[11:19].replace(':','')}_{end[11:19].replace(':','')}.json.gz"
    if os.path.exists(fn):
        with gzip.open(fn, "rt") as f: return json.load(f)
    out, tok = [], None
    while True:
        p = {"start": start, "end": end, "feed": "sip", "limit": 10000}
        if tok: p["page_token"] = tok
        for att in range(6):
            r = S.get(f"https://data.alpaca.markets/v2/stocks/{sym}/{kind}", headers=H, params=p, timeout=60)
            if r.status_code == 429: time.sleep(2 + 3 * att); continue
            if r.status_code >= 500: time.sleep(1 + att); continue
            break
        if r.status_code != 200:
            print("ERR", sym, kind, start, r.status_code, r.text[:120], file=sys.stderr); break
        j = r.json(); out += j.get(kind) or []; tok = j.get("next_page_token")
        if not tok: break
    with gzip.open(fn, "wt") as f: json.dump(out, f)
    return out

def iso(date, secs):
    return f"{date}T{secs//3600:02d}:{secs%3600//60:02d}:{secs%60:02d}Z"
def tsec(s):
    h, m, x = s.split(":"); return int(h)*3600 + int(m)*60 + int(x)

def pull_window(date, sym, t0, t1, quotes=True):
    tr = fetch("trades", sym, iso(date, t0), iso(date, t1))
    q = fetch("quotes", sym, iso(date, t0), iso(date, t1)) if quotes else None
    return tr, q

if __name__ == "__main__":
    rows = json.load(open(f"{ROOT}/data/killtests/rocket_anatomy_20260816_rows.json"))["legs"]
    top = sorted(rows, key=lambda l: -l["gain"])[:100]
    random.seed(16)
    # contrast windows: same name-day, RTH, >=20 min from any leg on that name-day
    legs_by = {}
    for l in rows: legs_by.setdefault((l["date"], l["sym"]), []).append(tsec(l["t"]))
    contrast = []
    for l in top:
        k = (l["date"], l["sym"]); ok = False
        for _ in range(200):
            t = random.randint(13*3600+30*60+300, 20*3600-600)
            if all(abs(t - x) >= 1200 for x in legs_by[k]): ok = True; break
        if ok: contrast.append({"date": l["date"], "sym": l["sym"], "t": iso(l["date"], t)[11:19]})
    jobs = [("U", l["date"], l["sym"], tsec(l["t"]) - 180, tsec(l["t"]) + 60) for l in top]
    jobs += [("UC", c["date"], c["sym"], tsec(c["t"]) - 180, tsec(c["t"]) + 60) for c in contrast]
    json.dump({"top": top, "contrast": contrast}, open(f"{CACHE}/universe_windows.json", "w"), indent=0)
    # Kev picks: full-day trades
    wl = json.load(open(f"{CACHE}/kev_watchlist.json")) if os.path.exists(f"{CACHE}/kev_watchlist.json") else None
    if wl is None:
        r = requests.get("https://zestful-intuition-production-b16a.up.railway.app/api/kev_watchlist", headers={"X-Dashboard-Secret": "marcos2026"}, timeout=60)
        wl = r.json(); json.dump(wl, open(f"{CACHE}/kev_watchlist.json", "w"))
    kev = [(d, s) for d, syms in wl.items() if not d.startswith("_") for s in syms]
    kjobs = [("K", d, s, 11*3600, 20*3600) for d, s in kev]
    def run(j):
        tag, d, s, a, b = j
        try:
            if tag == "K": fetch("trades", s, iso(d, a), iso(d, b)); return (tag, d, s, "ok")
            pull_window(d, s, a, b); return (tag, d, s, "ok")
        except Exception as e: return (tag, d, s, f"ERR {e}")
    with cf.ThreadPoolExecutor(8) as ex:
        for i, res in enumerate(ex.map(run, jobs + kjobs)):
            if i % 25 == 0 or res[3] != "ok": print(i, res, flush=True)
    print("done step-1a; kev name-days:", len(kev))
