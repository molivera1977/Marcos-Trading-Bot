"""ARM RESOLUTION QUALIFIER (8/8 night, Marcos: "do the work to qualify arm on 5s").
Same day (8/7 full 5s session), same names, same exit sim. ONLY the arm detector differs:
  10s-ARM: prox/vel computed on 10s bars (the shipped live path, ~ALP10S)
  5s-ARM : prox/vel computed on 5s bars (~ALP5S)
Both enter on the ARM bar close, stop = 2-min prior low, half at +1R, 12x5s-bar trail.
Question: does 5s resolution find real, PAYING arms the 10s path misses — or just noise?"""
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
def arms_at(B,minwin):
    """arm moments (sec, close) using this feed's own bars."""
    out=[];busy=-1
    for i in range(60,len(B)):
        s=B[i][0]
        if s<=busy or not (13*3600+30*60<=s<=19*3600+30*60): continue
        px=B[i][3]
        w5=[b for b in B[:i+1] if b[0]>=s-300]
        if len(w5)<minwin: continue
        ref=st.mean(b[3] for b in w5)
        band=0.10 if px>=3 else (0.20 if px>=0.75 else 0.75)
        prox=(px/ref-1)/band if ref else 0
        w1=[b for b in B[:i+1] if b[0]>=s-60]
        vel=(px/w1[0][3]-1)*100 if w1 and w1[0][3] else 0
        if prox>=0.7 and vel>=5:
            out.append((s,px)); busy=s+60   # 60s re-arm throttle = live cadence
    return out
def sim5(B5,s0,px):
    i=next((j for j in range(len(B5)) if B5[j][0]>=s0),None)
    if i is None or i+1>=len(B5): return None
    w2=[b for b in B5[:i] if b[0]>=s0-120]
    stop=min((b[2] for b in w2 if b[2]>0),default=0)
    if stop<=0 or stop>=px: return None
    sh=int(500//px) or 1
    r1=px-stop;pnl=0.0;rem=1.0;sc=False;lows=[]
    for j in range(i+1,len(B5)):
        _,h,l,c,_=B5[j]
        if not sc and h>=px+r1: pnl+=0.5*r1;rem=0.5;sc=True;stop=px
        if sc:
            lows.append(l)
            if len(lows)>12: lows.pop(0)
            if len(lows)==12: stop=max(stop,min(lows))
        if l<=stop: return (pnl+rem*(stop-px))*sh
    return (pnl+rem*(B5[-1][3]-px))*sh
names=["MB","ZYBT","YJ","DSY","NAMI","CELZ","VATE","AIXI","FVN","LGHL"]
for res,minwin in (("10S",12),("5S",30)):
    tot=0;n=0;w=0;rows=[]
    for tk in names:
        Ba=bars(tk,res); B5=bars(tk,"5S")
        if len(Ba)<120 or len(B5)<200: continue
        med=st.median(B5[i][0]-B5[i-1][0] for i in range(1,len(B5)))
        if med>15: continue
        for s0,px in arms_at(Ba,minwin):
            p=sim5(B5,s0,px)
            if p is None: continue
            tot+=p;n+=1;w+=(1 if p>0 else 0);rows.append((tk,f"{s0//3600-4:02d}:{s0%3600//60:02d}",round(px,2),round(p,2)))
    print(f"{res}-ARM: {n} arms  ${tot:+.2f}  winners {w}/{n}  mean ${tot/max(n,1):+.2f}")
    for r in sorted(rows,key=lambda x:x[1]): print("   ",r)
