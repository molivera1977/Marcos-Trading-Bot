#!/usr/bin/env python3
"""FEED-GAP DIAGNOSTIC CENSUS (8/14, Marcos: "how much money have these feed gaps cost us")
[SOLO - unconvened diagnostic. FREQUENCY/MAGNITUDE ONLY - NO DOLLAR CLAIMS.]
For every era trade (7/24+) with entry_ts_utc: compare recorded `highest` (monitor's eye)
vs SIP 10s-tape max high from entry to (exit_ts if stamped else +45min cap).
Window caveat: without exit_ts the window may overshoot the real hold -> tape_high can
exceed what the monitor COULD have seen. Rows are stamped windowed=capped for those.
Dollar attribution deliberately NOT computed here (sequencing engine required - v4 ext)."""
import json, urllib.request, time, sys
BASE="https://zestful-intuition-production-b16a.up.railway.app"
def get(u):
    for _ in range(3):
        try:
            return json.load(urllib.request.urlopen(u, timeout=30))
        except Exception:
            time.sleep(2)
    return {}
trades=[t for t in (get(BASE+"/api/trades").get("trades") or [])
        if (t.get("date") or "") >= "2026-07-24" and t.get("entry_ts_utc")]
print(f"era trades with entry_ts: {len(trades)}", flush=True)
rows=[]
for i,t in enumerate(trades):
    tk=t.get("ticker"); day=t.get("date"); ets=str(t.get("entry_ts_utc"))[:19].replace("Z","")
    rec_hi=float(t.get("highest") or 0)
    if not tk or rec_hi<=0: continue
    xts=str(t.get("exit_ts_utc") or "")[:19].replace("Z","")
    if not xts:
        # cap 45min after entry
        import datetime as dt
        e=dt.datetime.fromisoformat(ets); xts=(e+dt.timedelta(minutes=45)).isoformat()[:19]
        capped=True
    else:
        capped=False
    bars=(get(f"{BASE}/api/bars?date={day}&ticker={tk}~ALP10S").get("bars")) or []
    post=[float(b["high"]) for b in bars if ets <= str(b["time"])[:19] <= xts]
    if not post: 
        rows.append({"tk":tk,"day":day,"status":"NO_BARS","lane":t.get("entry_type")}); continue
    tape_hi=max(post)
    gap_pct=round((tape_hi-rec_hi)/rec_hi*100,2)
    rows.append({"tk":tk,"day":day,"lane":t.get("entry_type"),"rec_hi":rec_hi,
                 "tape_hi":tape_hi,"gap_pct":gap_pct,"capped":capped,
                 "pnl":t.get("pnl"),"n_fills":len(t.get("partial_fills") or [])})
    if i%25==0: print(f"...{i}/{len(trades)}", flush=True)
ok=[r for r in rows if "gap_pct" in r]
blind=[r for r in ok if r["gap_pct"]>1.0]   # tape printed >1% above what monitor saw
print(f"\nchecked {len(ok)} | NO_BARS {len(rows)-len(ok)}")
print(f"gap>1%: {len(blind)} trades ({round(100*len(blind)/max(1,len(ok)))}%)")
for r in sorted(blind, key=lambda r:-r["gap_pct"])[:15]:
    print(f"  {r['day']} {r['tk']:6s} {r['lane'] or '?':13s} rec_hi {r['rec_hi']:<8} tape_hi {r['tape_hi']:<8} gap {r['gap_pct']}% fills={r['n_fills']} pnl={r['pnl']}{' [win-capped]' if r['capped'] else ''}")
json.dump(rows, open(__file__.replace(".py","_RESULTS.json"),"w"), indent=1)
print("\nsaved RESULTS.json — dollar attribution deferred to the v4 extension (sequenced), per the sequencing law.")
