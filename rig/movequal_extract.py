"""Move-quality metric extraction (Saturday prep, started 7/15 in Opus).
STEP 1 here: entry inventory + bar-coverage diagnostics — verify joins/sources
BEFORE computing metrics (multi-source join = where this week's bugs hid).

Sources:
  7/13, 7/14 entries -> 1-min bars from iCloud mirror (_ext preferred)
  7/15 entries       -> 1-min + 10s bars from dashboard (~10s namespace)
Fill times          -> decisions_archive status=filled, matched ticker+price (<2%)
NO conclusions — Sunday's Fable session judges the table.
"""
import json, urllib.request, pathlib
from datetime import datetime

BASE="https://zestful-intuition-production-b16a.up.railway.app"
IC=pathlib.Path("/Users/marcosolivera/Library/Mobile Documents/com~apple~CloudDocs/TradingBot/bars_1min")
def get(u): return json.load(urllib.request.urlopen(BASE+u,timeout=30))

DAYS=("2026-07-13","2026-07-14","2026-07-15")

# ---- entries with outcome R ----
trades=[t for t in get("/api/trades").get("trades",[]) if t.get("date") in DAYS and t.get("planned_risk")]
# ---- fills per day ----
fills={}
for d in DAYS:
    for r in get(f"/api/decisions_archive?date={d}&status=filled&limit=1000").get("rows",[]):
        if r.get("price"):
            fills.setdefault((d,r.get("ticker")),[]).append((r.get("time"),float(r["price"])))

# ---- bar availability ----
def mirror_has(d,tk):
    return (IC/f"{d}_{tk}__ext.json").exists() or (IC/f"{d}_{tk}.json").exists()
def dash_1min(d,tk):
    try:
        j=get(f"/api/bars?date={d}&ticker={tk}")
        bs=j.get("bars",j) if isinstance(j,dict) else j
        return len(bs) if isinstance(bs,list) else 0
    except Exception: return 0
def dash_10s(d,tk):
    try:
        j=get(f"/api/bars?date={d}&ticker={tk}~10s")
        bs=j.get("bars",j) if isinstance(j,dict) else j
        return len(bs) if isinstance(bs,list) else 0
    except Exception: return 0

rows=[]; nofill=0
for t in trades:
    d,tk,e=t["date"],t["ticker"],float(t["entry"])
    cand=[f for f in fills.get((d,tk),[]) if abs(f[1]-e)/e<0.02]
    ft=cand[0][0] if cand else None
    if not ft: nofill+=1
    R=t["pnl"]/t["planned_risk"]
    if d=="2026-07-15":
        b1=dash_1min(d,tk); b10=dash_10s(d,tk); src="dash"
    else:
        b1=mirror_has(d,tk); b10=0; src="mirror"
    rows.append(dict(date=d,ticker=tk,etype=t.get("entry_type",""),fill=ft,R=round(R,2),
                     bars1=b1,bars10=b10,src=src))

by_day={d:[r for r in rows if r["date"]==d] for d in DAYS}
print(f"ENTRY INVENTORY: {len(rows)} entries, {nofill} without a matched fill\n")
for d in DAYS:
    rs=by_day[d]
    with1=sum(1 for r in rs if r["bars1"])
    with10=sum(1 for r in rs if r["bars10"])
    print(f"{d}: {len(rs)} entries | 1-min bars {with1}/{len(rs)} ({rs[0]['src'] if rs else '-'}) | 10s bars {with10}/{len(rs)}")
print()
for r in rows:
    flag="" if (r["fill"] and r["bars1"]) else "  <-- GAP"
    print(f"  {r['date'][5:]} {r['ticker']:6} {r['etype'][:16]:16} fill={str(r['fill'])[:8]:8} R={r['R']:+.2f} 1m={r['bars1']} 10s={r['bars10']}{flag}")
