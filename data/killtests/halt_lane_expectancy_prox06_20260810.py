"""HALT LANE FULL EXPECTANCY (8/8, #37 pre-build kill-test; rules frozen).
ARM = 10s band-prox >= 0.7 AND vel1m >= 5% (from halt_trigger_study features). For EVERY arm
moment era-wide (halt-bound AND control alike, discovered fresh here): enter at the arm bar's
CLOSE, HALF size ($500), stop = min low of the prior 2 min, half out at +1R, 6-bar 10s trail.
(The Kev resumption-trim for actual halts is a REFINEMENT; this baseline prices the raw trigger.)
VERDICT: lane BUILDS iff total >= +$300 era-wide AND mean/arm > 0 AND worst arm day > −$150.
"""
import json,urllib.request,urllib.parse,datetime,statistics as st
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
            out.append((sec,float(x["high"]),float(x["low"]),float(x["close"]),float(x.get("volume") or 0)))
        except Exception: continue
    _b[(tk,d)]=out; return out
def sim(B,i,e,stop):
    r1=e-stop
    if r1<=0: return None,None
    pnl=0.0;rem=1.0;sc=False;lows=[]
    for j in range(i+1,len(B)):
        s,h,l,c,_=B[j]
        if j>i+1 and s-B[j-1][0]>=270:      # halted while in: next print = resumption; sim continues
            pass
        if not sc and h>=e+r1: pnl+=0.5*r1;rem=0.5;sc=True;stop=e
        if sc:
            lows.append(l)
            if len(lows)>6: lows.pop(0)
            if len(lows)==6: stop=max(stop,min(lows))
        if l<=stop: return pnl+rem*(max(stop,l)-e), j
    return pnl+rem*(B[-1][3]-e), len(B)-1
rows=json.load(open("halt_inventory_rows_20260807.json"))
universe=sorted({(r["d"],r["tk"]) for r in rows})           # names that ever halted = the hot set
tot=0.0;n=0;w=0;byday={}
arms=[]
for d,tk in universe:
    B=bars10(tk,d)
    if len(B)<80: continue
    busy=-1
    for i in range(40,len(B)):
        if i<=busy: continue
        s=B[i][0]
        if not (13*3600+30*60<=s<=19*3600+30*60): continue
        px=B[i][3]
        w5=[b for b in B[:i+1] if b[0]>=s-300]
        if len(w5)<12: continue
        ref=st.mean(b[3] for b in w5)
        band=0.10 if px>=3 else (0.20 if px>=0.75 else 0.75)
        prox=(px/ref-1)/band if ref else 0
        w1=[b for b in B[:i+1] if b[0]>=s-60]
        vel=(px/w1[0][3]-1)*100 if w1 and w1[0][3] else 0
        if prox>=0.6 and vel>=5:
            w2=[b for b in B[:i] if b[0]>=s-120]
            stop=min((b[2] for b in w2 if b[2]>0), default=0)
            if stop<=0 or stop>=px: continue
            sh=int(500//px)
            if not sh: continue
            r=sim(B,i,px,stop)
            if r[0] is None: continue
            pnl=r[0]*sh; busy=r[1]
            tot+=pnl;n+=1;w+=(1 if pnl>0 else 0)
            byday[d]=byday.get(d,0)+pnl
            arms.append((d,tk,round(px,2),round(pnl,2)))
print(f"arms fired: {n}  total ${tot:+.2f}  winners {w}/{n}  mean ${tot/max(n,1):+.2f}")
worst_day=min(byday.values()) if byday else 0
print(f"worst day ${worst_day:+.2f}   days {len(byday)}")
ok = tot>=300 and (tot/max(n,1))>0 and worst_day>-150
print("VERDICT:", "BUILD" if ok else "NOT MET — evidence only")
for x in sorted(arms,key=lambda y:-abs(y[3]))[:8]: print("  ",x)
json.dump(arms,open("halt_lane_arms_prox06_20260810.json","w"),indent=0)
