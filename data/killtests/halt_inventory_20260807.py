"""HALT INVENTORY (8/7 intraday, ANALYSIS-ONLY; Marcos: "halts happen all around us and we just
watch"). Rules frozen before run: for era days 7/14+, scan every stored ~ALP10S series for LULD
signatures = a gap of >=4.5 min between consecutive bars during RTH (09:30-16:00) with real volume
bars on both sides. For each halt: pre-halt trend (5-min return into the halt), resumption jump
(first bar after vs last bar before), and the KEV-PLAY outcome: enter the last pre-halt pullback
(last 10s low in the 3 min before the halt), HALF size ($500), exit HALF at first resumption print,
trail rest with the frozen killtest engine. Dollars per halt. NO recommendation without this table.
"""
import json,urllib.request,urllib.parse,datetime,os
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u):
    return json.load(urllib.request.urlopen(u,timeout=60))
days=[]
d0=datetime.date(2026,7,14); today=datetime.date(2026,8,7)
while d0<=today:
    if d0.weekday()<5: days.append(d0.isoformat())
    d0+=datetime.timedelta(days=1)
def bars10(tk,d):
    try: r=get(f"{U}/api/bars?date={d}&ticker={urllib.parse.quote(tk)}~ALP10S").get("bars") or []
    except Exception: return []
    out=[]
    for x in r:
        try:
            ts=str(x.get("time"))[11:19]
            sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
            out.append((sec,float(x["high"]),float(x["low"]),float(x["close"]),float(x.get("volume") or 0)))
        except Exception: continue
    return out
def sim_trail(B,i0,e):
    rem=0.5;pnl=0.0;stop=e*0.9;lows=[]
    for j in range(i0,len(B)):
        _,h,l,c,_=B[j]
        lows.append(l)
        if len(lows)>6: lows.pop(0)
        if len(lows)==6: stop=max(stop,min(lows))
        if l<=stop: return pnl+rem*(max(stop,l)-e)
    return pnl+rem*(B[-1][3]-e)
results=[]
for d in days:
    try: tks=get(f"{U}/api/bars_index?date={d}").get("tickers")
    except Exception: tks=None
    if not tks:
        # fallback: use trades+known movers that day
        try: tks=list({t["ticker"] for t in get(U+"/api/trades")["trades"] if t.get("date")==d})
        except Exception: continue
    for tk in tks:
        if "~" in tk: continue
        B=bars10(tk,d)
        if len(B)<60: continue
        for i in range(1,len(B)):
            gap=B[i][0]-B[i-1][0]
            if gap>=270 and 34200<=B[i-1][0]<=57600:
                pre=[b for b in B[:i] if b[0]>=B[i-1][0]-300]
                if len(pre)<3: continue
                trend=(B[i-1][3]-pre[0][3])/pre[0][3]*100 if pre[0][3] else 0
                jump=(B[i][3]-B[i-1][3])/B[i-1][3]*100 if B[i-1][3] else 0
                pull=[b for b in B[:i] if b[0]>=B[i-1][0]-180]
                e=min(b[2] for b in pull if b[2]>0) if pull else 0
                pnl=None
                if e>0 and trend>0:
                    sh=int(500//e) or 0
                    if sh:
                        half=0.5*(B[i][3]-e)*sh
                        rest=sim_trail(B,i+1,e)*sh
                        pnl=round(half+rest,2)
                results.append({"d":d,"tk":tk,"t":B[i-1][0],"gap_min":round(gap/60,1),
                                "trend5":round(trend,1),"jump":round(jump,1),"kev_pnl":pnl})
json.dump(results,open("halt_inventory_rows_20260807.json","w"),indent=0)
ups=[r for r in results if r["trend5"]>0]
dn=[r for r in results if r["trend5"]<=0]
print(f"halts found: {len(results)} on {len(set(r['d'] for r in results))} days")
print(f"  up-into-halt: {len(ups)}  down-into-halt: {len(dn)}")
paid=[r for r in ups if r["kev_pnl"] is not None]
print(f"  KEV-PLAY priced (up-halts): n={len(paid)} total ${sum(r['kev_pnl'] for r in paid):+.2f} "
      f"winners {sum(1 for r in paid if r['kev_pnl']>0)}/{len(paid)}")
for r in sorted(paid,key=lambda x:-abs(x['kev_pnl']))[:10]:
    print(f"   {r['d']} {r['tk']:6s} gap {r['gap_min']}m trend {r['trend5']:+.1f}% jump {r['jump']:+.1f}% -> ${r['kev_pnl']:+.2f}")
