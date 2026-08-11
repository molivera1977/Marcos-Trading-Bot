"""RECONCILED arm head-to-head (8/8 late). ONE sim convention for both feeds, live-like:
one open position per name at a time (no re-arm while in a trade), $500 clip, entry at arm
bar close, stop = prior-2-min low, half at +1R, 12x5s trail. Supersedes the two earlier
scripts whose conventions diverged (regrade: busy-until-exit; resolution: 60s re-arm)."""
import json,urllib.request,urllib.parse,statistics as st
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u,timeout=60))
def bars(tk,res):
    r=get(f"{U}/api/bars?date=2026-08-07&ticker={urllib.parse.quote(tk)}~ALP{res}").get("bars") or []
    out=[]
    for x in r:
        try:
            ts=str(x.get("time"))[11:19]; sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
            out.append((sec,float(x["high"]),float(x["low"]),float(x["close"]),float(x.get("volume") or 0)))
        except Exception: continue
    return out
def sim5(B5,s0,px):
    i=next((j for j in range(len(B5)) if B5[j][0]>=s0),None)
    if i is None or i+1>=len(B5): return None,None
    w2=[b for b in B5[:i] if b[0]>=s0-120]
    stop=min((b[2] for b in w2 if b[2]>0),default=0)
    if stop<=0 or stop>=px: return None,None
    sh=int(500//px) or 1
    r1=px-stop;pnl=0.0;rem=1.0;sc=False;lows=[]
    for j in range(i+1,len(B5)):
        _,h,l,c,_=B5[j]
        if not sc and h>=px+r1: pnl+=0.5*r1;rem=0.5;sc=True;stop=px
        if sc:
            lows.append(l)
            if len(lows)>12: lows.pop(0)
            if len(lows)==12: stop=max(stop,min(lows))
        if l<=stop: return (pnl+rem*(stop-px))*sh, B5[j][0]
    return (pnl+rem*(B5[-1][3]-px))*sh, B5[-1][0]
names=["MB","ZYBT","YJ","DSY","NAMI","CELZ","VATE","AIXI","FVN","LGHL"]
out={}
for res,minwin in (("10S",12),("5S",30)):
    tot=0;n=0;w=0;rows=[]
    for tk in names:
        Ba=bars(tk,res); B5=bars(tk,"5S")
        if len(Ba)<120 or len(B5)<200: continue
        med=st.median(B5[i][0]-B5[i-1][0] for i in range(1,len(B5)))
        if med>15: continue
        free=0   # no new arm before this sec (position open until exit)
        for i in range(60,len(Ba)):
            s=Ba[i][0]
            if s<free or not (13*3600+30*60<=s<=19*3600+30*60): continue
            px=Ba[i][3]
            w5=[b for b in Ba[:i+1] if b[0]>=s-300]
            if len(w5)<minwin: continue
            ref=st.mean(b[3] for b in w5)
            band=0.10 if px>=3 else (0.20 if px>=0.75 else 0.75)
            prox=(px/ref-1)/band if ref else 0
            w1=[b for b in Ba[:i+1] if b[0]>=s-60]
            vel=(px/w1[0][3]-1)*100 if w1 and w1[0][3] else 0
            if prox>=0.7 and vel>=5:
                p,endsec=sim5(B5,s,px)
                if p is None: free=s+60; continue
                tot+=p;n+=1;w+=(1 if p>0 else 0);free=endsec+60
                rows.append((tk,f"{s//3600-4:02d}:{s%3600//60:02d}",round(px,2),round(p,2)))
    out[res]=rows
    print(f"{res}-ARM (live-like): {n} arms  ${tot:+.2f}  winners {w}/{n}  mean ${tot/max(n,1):+.2f}")
    for r in sorted(rows,key=lambda x:x[1]): print("   ",r)
json.dump(out,open("data/killtests/arm_resolution_reconciled_rows_20260808.json","w"),indent=0)
