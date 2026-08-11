"""RIDE SEAMS ON 5s (8/7, analysis-only; Marcos: "I wanted to be IN the stocks that got halted on
the way up... This is where I want the 5s tape to see where we can jump in.")
SEAM (all 5s-computable, frozen before run): during an up-phase (px above VWAP-proxy = trailing
3-min mean), a micro-pullback of >=1.5% from the running peak, followed by a 5s bar CLOSING above
the highest high of the pullback bars (micro-reclaim). ENTER that close; STOP = pullback low;
scale half at +1R; trail rest on 6-bar 5s lows. $1000 clip. Walk each of today's halted runners
through their full session. Overlaps skipped (one position at a time per name)."""
import json,urllib.request,urllib.parse
U="https://zestful-intuition-production-b16a.up.railway.app"
def bars5(tk):
    r=json.load(urllib.request.urlopen(f"{U}/api/bars?date=2026-08-07&ticker={urllib.parse.quote(tk)}~ALP5S",timeout=60)).get("bars") or []
    out=[]
    for x in r:
        ts=str(x.get("time"))[11:19]
        sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
        out.append((sec,float(x["high"]),float(x["low"]),float(x["close"]),float(x.get("volume") or 0)))
    return out
def hhmm(s): return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
def sim(B,i,e,stop):
    r1=e-stop
    pnl=0.0;rem=1.0;sc=False;lows=[]
    for j in range(i,len(B)):
        s,h,l,c,_=B[j]
        if j>i and s-B[j-1][0]>=270:   # halt while holding: fill at post-halt close (honest: resumption)
            pass
        if not sc and h>=e+r1: pnl+=0.5*r1;rem=0.5;sc=True;stop=e
        if sc:
            lows.append(l)
            if len(lows)>12: lows.pop(0)
            if len(lows)==12: stop=max(stop,min(lows))
        if l<=stop: return pnl+rem*(max(stop,l)-e), j
    return pnl+rem*(B[-1][3]-e), len(B)-1
for tk in ("YJ","MB","ZYBT","NAMI"):
    B=bars5(tk)
    if len(B)<100: print(tk,"no 5s"); continue
    total=0.0;trades=[];j_busy=-1
    for i in range(40,len(B)):
        if i<=j_busy: continue
        s=B[i][0]
        if not (13*3600+30*60<=s<=20*3600): continue
        w3=[b for b in B[:i] if b[0]>=s-180]
        if len(w3)<10: continue
        ma=sum(b[3] for b in w3)/len(w3)
        if B[i][3]<=ma: continue                      # up-phase only
        # find pullback: running peak in last 2 min, retrace >=1.5%, then this bar reclaims pullback high
        w2=[b for b in B[:i] if b[0]>=s-120]
        peak=max(b[1] for b in w2)
        trough=min(b[2] for b in w2 if b[2]>0)
        if peak<=0 or (peak-trough)/peak*100<1.5: continue
        pb=[b for b in w2 if b[2]<=trough*1.002]
        if not pb: continue
        pb_hi=max(b[1] for b in pb)
        if B[i][3]>pb_hi and B[i-1][3]<=pb_hi:        # the reclaim close
            e=B[i][3];stop=trough
            if e-stop<=0 or (e-stop)/e<0.005: continue
            sh=int(1000//e)
            if not sh: continue
            pnl,jend=sim(B,i+1,e,stop)
            total+=pnl*sh
            trades.append((hhmm(s),round(e,2),round(stop,2),round(pnl*sh,2)))
            j_busy=jend
    print(f"{tk}: seams entered {len(trades)}, total ${total:+.2f}")
    for t in trades: print("   ",t)
