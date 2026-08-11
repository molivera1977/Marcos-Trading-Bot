"""CROWN BREAKSIDE REPLAY (8/7 ~11:3x, Marcos: "run the crown breakside replay now").
Q: the crown bypasses the ext-VWAP band (earned by +$641.87/26 refused-crown study) but NOT the
breakside gate — YJ 8/7 (11 rereads, still unbuyable while +449%) is the specimen. Replay EVERY
logged breakside_reject (gate live 8/5+): was the name CROWNED (leader_armed earlier that day)?
Price the refused entry through the frozen engine (entry=fire price, stop=row's stop; half at +1R,
6-bar 10s trail). SHIP-CANDIDATE for HIDDEN_BREAKSIDE_CROWN_BYPASS iff crowned subgroup >= +$75
total AND n >= 5 AND no single trade worse than −$40. Uncrowned subgroup = control (expect flat/neg).
"""
import json,urllib.request,urllib.parse,datetime
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u,timeout=60))
_b={}
def bars10(tk,d):
    if (tk,d) in _b: return _b[(tk,d)]
    try: r=get(f"{U}/api/bars?date={d}&ticker={urllib.parse.quote(tk)}~ALP10S").get("bars") or []
    except Exception: r=[]
    out=[]
    for x in r:
        try:
            ts=str(x.get("time"))[11:19]
            sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
            out.append((sec,float(x["high"]),float(x["low"]),float(x["close"])))
        except Exception: continue
    _b[(tk,d)]=out; return out
def sim(B,i,e,stop):
    r1=e-stop;pnl=0.0;rem=1.0;sc=False;lows=[]
    for j in range(i,len(B)):
        s,h,l,c=B[j]
        if not sc and h>=e+r1: pnl+=0.5*r1;rem=0.5;sc=True;stop=e
        if sc:
            lows.append(l)
            if len(lows)>6: lows.pop(0)
            if len(lows)==6: stop=max(stop,min(lows))
        if l<=stop: return pnl+rem*(max(stop,l)-e)
    return pnl+rem*(B[-1][3]-e)
def tsec(t):   # '10:25:13 AM' ET -> UTC sec
    hh,mm,ss=int(t[0:2]),int(t[3:5]),int(t[6:8])
    if t.endswith('PM') and hh!=12: hh+=12
    if t.endswith('AM') and hh==12: hh=0
    return (hh+4)*3600+mm*60+ss
crown_tot=0.0;cn=0;cw=0;worst=0.0
un_tot=0.0;un=0
rows_out=[]
for d in ("2026-08-05","2026-08-06","2026-08-07"):
    rows=get(f"{U}/api/decisions_archive?date={d}")
    rows=rows.get('decisions') or rows.get('rows') or rows
    crowns={}
    for r in rows:
        if r.get('status')=='leader_armed':
            crowns.setdefault(r['ticker'],tsec(r['time']))
    for r in rows:
        if r.get('status')!='breakside_reject': continue
        tk=r['ticker'];e=float(r.get('price') or 0);st=float(r.get('stop') or 0)
        if not (e>0 and 0<st<e): continue
        s=tsec(r['time'])
        B=bars10(tk,d)
        i=next((j for j,x in enumerate(B) if x[0]>=s),None)
        if i is None or len(B)-i<12: continue
        sh=int(1000//e)
        if not sh: continue
        pnl=sim(B,i,e,st)*sh
        is_cr = tk in crowns and crowns[tk]<=s
        rows_out.append((d,r['time'],tk,'CROWN' if is_cr else 'plain',round(e,3),round(pnl,2)))
        if is_cr:
            crown_tot+=pnl;cn+=1;cw+=(1 if pnl>0 else 0);worst=min(worst,pnl)
        else:
            un_tot+=pnl;un+=1
for x in rows_out: print(" ",x)
print(f"\nCROWNED refused-breakside: n={cn} total ${crown_tot:+.2f} winners {cw}/{cn} worst ${worst:.2f}")
ok = crown_tot>=75 and cn>=5 and worst>=-40
print(f"uncrowned control:         n={un} total ${un_tot:+.2f}")
print("VERDICT:", "SHIP-CANDIDATE (crown breakside bypass)" if ok else "NOT MET — evidence only")
