"""BREAKSIDE TOLERANCE RE-GRADE (8/8, Ombudsman hearing #1; frozen rules pre-run).
Every logged breakside_reject 8/5-8/7 re-priced through the frozen engine (entry=fire px,
stop=row stop). Group by the row's gap_pct. For tolerance T in {0 (status quo), 1, 2, 3, 5}:
rejects with gap <= T become ENTRIES; sum their P&L. SHIP-CANDIDATE iff some T beats T=0 by
>= $150 era-wide AND its admitted cohort is positive AND worst admitted trade >= -$60.
(The YJ $1.70 fire sits at gap +0.6% — the $464 exhibit. The 8/7 crown-bypass replay already
proved BLANKET bypass fails (−$2.34); this tests the narrow remedy instead.)"""
import json,urllib.request,urllib.parse
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
def tsec(t):
    hh,mm,ss=int(t[0:2]),int(t[3:5]),int(t[6:8])
    if t.endswith('PM') and hh!=12: hh+=12
    if t.endswith('AM') and hh==12: hh=0
    return (hh+4)*3600+mm*60+ss
rows=[]
for d in ("2026-08-05","2026-08-06","2026-08-07"):
    rs=get(f"{U}/api/decisions_archive?date={d}&status=breakside_reject&limit=50000")
    rs=rs.get('decisions') or rs.get('rows') or rs
    for r in rs:
        if r.get('status')!='breakside_reject': continue
        e=float(r.get('price') or 0);st=float(r.get('stop') or 0);g=r.get('gap_pct')
        if g is None:
            _bl=float(r.get('break_level') or 0)
            g=((e-_bl)/_bl*100) if _bl>0 else None
        if not (e>0 and 0<st<e and g is not None): continue
        B=bars10(r['ticker'],d)
        i=next((j for j,x in enumerate(B) if x[0]>=tsec(r['time'])),None)
        if i is None or len(B)-i<12: continue
        sh=int(1000//e)
        if not sh: continue
        rows.append((d,r['ticker'],float(g),round(sim(B,i,e,st)*sh,2)))
print(f"priced rejects: {len(rows)}")
for T in (0,1,2,3,5):
    adm=[x for x in rows if x[2]<=T]
    tot=sum(x[3] for x in adm)
    w=sum(1 for x in adm if x[3]>0)
    worst=min([x[3] for x in adm],default=0)
    ok = tot>=150 and tot>0 and worst>=-60 and T>0
    print(f"tol {T}%: admits {len(adm):2d} rejects  ${tot:+8.2f}  winners {w}/{len(adm)}  worst ${worst:.2f}"
          f"  {'SHIP-CANDIDATE' if ok else ''}")
for x in sorted(rows,key=lambda y:-abs(y[3]))[:6]: print("  ",x)
