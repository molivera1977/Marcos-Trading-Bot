"""FULL-DAY 5s RE-GRADE of the halt-lane confirm (8/8 night, pre-Monday).
Friday 8/7 = complete 5s session. Replay the LIVE arm logic (prox>=0.7 + vel1m>=5%)
at 5s resolution over the day's ladder names; at each arm, grade three confirm arms:
  STRICT (shipped): upratio>=0.8 & maxpull<=1%   LOOSE: up>=0.6 & pull<=5%   NONE: take all
Exit sim = lane spec: stop at trailing 2-min low, half off at +1R, 12-bar 5s trail on rest.
$500 clip. Dollars per arm, per variant. Decision input for Marcos's Monday config call."""
import json,urllib.request,urllib.parse,statistics as st
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u,timeout=60))
def bars5(tk):
    r=get(f"{U}/api/bars?date=2026-08-07&ticker={urllib.parse.quote(tk)}~ALP5S").get("bars") or []
    out=[]
    for x in r:
        try:
            ts=str(x.get("time"))[11:19]; sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
            out.append((sec,float(x["high"]),float(x["low"]),float(x["close"]),float(x.get("volume") or 0)))
        except Exception: continue
    return out
def sim(B,i,px,stop):
    half=0; shares=2; pnl=0.0; hi=px; scaled=False; trail=stop
    for j in range(i+1,len(B)):
        s,h,l,c,_=B[j]
        if s-B[j-1][0]>=270:   # halt: hold through (monitor doctrine), resume at next bar
            pass
        if not scaled and h>=px+(px-stop):
            pnl+=(px-stop); scaled=True   # half off at +1R (1 of 2 shares)
        w=[b for b in B[max(0,j-12):j]]
        trail=max(trail, min(b[2] for b in w if b[2]>0) if scaled and w else trail)
        eff = trail if scaled else stop
        if l<=eff:
            pnl+=(eff-px)*(1 if scaled else 2)
            return pnl,j
        hi=max(hi,h)
    pnl+=(B[-1][3]-px)*(1 if scaled else 2)
    return pnl,len(B)-1
names=["MB","ZYBT","YJ","DSY","NAMI","CELZ","VATE","AIXI","SPHL","KXIN","PETZ","FVN","STG","LGHL"]
res={"STRICT":[0.0,0,0],"LOOSE":[0.0,0,0],"NONE":[0.0,0,0]}
detail=[]
for tk in names:
    B=bars5(tk)
    if len(B)<200: continue
    dense=st.median(B[i][0]-B[i-1][0] for i in range(1,len(B)))
    if dense>15: continue   # illiquid names out (SPHL/PETZ class: gaps are no-trades, not halts)
    busy=-1
    for i in range(60,len(B)):
        if i<=busy: continue
        s=B[i][0]
        if not (13*3600+30*60<=s<=19*3600+30*60): continue
        px=B[i][3]
        w5=[b for b in B[:i+1] if b[0]>=s-300]
        if len(w5)<30: continue
        ref=st.mean(b[3] for b in w5)
        band=0.10 if px>=3 else (0.20 if px>=0.75 else 0.75)
        prox=(px/ref-1)/band if ref else 0
        w1=[b for b in B[:i+1] if b[0]>=s-60]
        vel=(px/w1[0][3]-1)*100 if w1 and w1[0][3] else 0
        if prox>=0.7 and vel>=5:
            w2=[b for b in B[:i] if b[0]>=s-120]
            stop=min((b[2] for b in w2 if b[2]>0), default=0)
            if stop<=0 or stop>=px: continue
            wc=[b for b in B[:i+1] if b[0]>=s-60]
            ups=sum(1 for a,b in zip(wc,wc[1:]) if b[3]>=a[3])/max(len(wc)-1,1)
            peak=wc[0][3]; mp=0
            for b in wc:
                peak=max(peak,b[3]); mp=max(mp,(peak-b[3])/peak*100 if peak else 0)
            sh=int(500//px) or 1
            unit,endj=sim(B,i,px,stop)
            pnl=unit*sh/2
            busy=endj
            row=dict(tk=tk,t=f"{s//3600-4:02d}:{s%3600//60:02d}",px=round(px,2),up=round(ups,2),
                     pull=round(mp,1),pnl=round(pnl,2))
            detail.append(row)
            for name,ok in (("STRICT",ups>=0.8 and mp<=1.0),("LOOSE",ups>=0.6 and mp<=5.0),("NONE",True)):
                if ok:
                    res[name][0]+=pnl; res[name][1]+=1; res[name][2]+=(1 if pnl>0 else 0)
for k,(t,n,w) in res.items():
    print(f"{k:7s}: {n} entries  ${t:+.2f}  winners {w}/{n}  mean ${t/max(n,1):+.2f}")
print("\nper-arm detail:")
for r in sorted(detail,key=lambda x:x["t"]): print("  ",r)
json.dump(detail,open("data/killtests/halt_confirm_regrade_rows_20260808.json","w"),indent=0)
