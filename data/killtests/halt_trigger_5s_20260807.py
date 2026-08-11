"""5s HALT TRIGGER (8/7 intraday, analysis-only). Today's halts on 5s tape vs fast controls.
Features over the final 60s before each event (all live-computable from 5s bars):
  upratio  = fraction of 5s bars closing >= prior close (one-sided tape)
  maxpull  = deepest peak-to-trough retrace % within the 60s (halt ladders don't breathe)
  volslope = last-30s volume / prior-30s volume (acceleration)
  prox5    = LULD proximity with 5s-resolution ref (mean px of trailing 5 min)
Controls: same names, vel1m>=4% moments >=6 min from any halt."""
import json,urllib.request,urllib.parse,statistics as st
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u,timeout=60))
def bars5(tk):
    try: r=get(f"{U}/api/bars?date=2026-08-07&ticker={urllib.parse.quote(tk)}~ALP5S").get("bars") or []
    except Exception: return []
    out=[]
    for x in r:
        try:
            ts=str(x.get("time"))[11:19]
            sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
            out.append((sec,float(x["high"]),float(x["low"]),float(x["close"]),float(x.get("volume") or 0)))
        except Exception: continue
    return out
def halts(B):
    out=[]
    for i in range(1,len(B)):
        if B[i][0]-B[i-1][0]>=270 and 13*3600+30*60<=B[i-1][0]<=20*3600:
            out.append(i)
    return out
def feats(B,i):
    w=[b for b in B[:i+1] if b[0]>=B[i][0]-60]
    if len(w)<8: return None
    ups=sum(1 for a,b in zip(w,w[1:]) if b[3]>=a[3])/max(len(w)-1,1)
    peak=w[0][3]; mp=0
    for b in w:
        peak=max(peak,b[3]); mp=max(mp,(peak-b[3])/peak*100 if peak else 0)
    half=B[i][0]-30
    v2=sum(b[4] for b in w if b[0]>=half); v1=sum(b[4] for b in w if b[0]<half) or 1
    w5=[b for b in B[:i+1] if b[0]>=B[i][0]-300]
    ref=st.mean(b[3] for b in w5); px=B[i][3]
    band=0.10 if px>=3 else (0.20 if px>=0.75 else 0.75)
    return dict(upratio=round(ups,2),maxpull=round(mp,1),volslope=round(v2/v1,1),
                prox5=round((px/ref-1)/band,2))
names=["MB","ZYBT","YJ","DSY","NAMI","CELZ","VATE","AIXI","SPHL","KXIN","PETZ","FVN","STG","LGHL"]
H=[];C=[]
for tk in names:
    B=bars5(tk)
    if len(B)<200: continue
    hs=halts(B)
    hsecs={B[i-1][0] for i in hs}
    for i in hs:
        f=feats(B,i-1)
        if f: H.append((tk,f))
    for j in range(100,len(B),36):
        s=B[j][0]
        if not (13*3600+30*60<=s<=20*3600): continue
        if any(abs(h-s)<=360 for h in hsecs): continue
        w1=[b for b in B[:j+1] if b[0]>=s-60]
        if len(w1)>6 and w1[0][3] and (B[j][3]/w1[0][3]-1)*100>=4:
            f=feats(B,j)
            if f: C.append((tk,f))
def summ(name,X):
    if not X: print(name,"none"); return
    fs=[x[1] for x in X]
    print(f"{name}: n={len(fs)} upratio {st.median(f['upratio'] for f in fs):.2f} "
          f"maxpull {st.median(f['maxpull'] for f in fs):.1f}% volslope {st.median(f['volslope'] for f in fs):.1f} "
          f"prox5 {st.median(f['prox5'] for f in fs):.2f}")
print("today's up-halts found:",len(H))
for tk,f in H: print("  ",tk,f)
summ("HALT-60s", H); summ("CONTROL ", C)
