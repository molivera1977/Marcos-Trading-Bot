"""ARM EMPIRICAL CALIBRATION (8/10): today's real halts vs our prox math.
For every zero-print gap >=270s (dense tape) today, compute OUR arm inputs in the final 60s
before the halt: prox under (a) nominal band by price tier, (b) half-band, and ref as
(1) mean of trailing 5-min closes, (2) MIN of trailing 5-min closes (worst-case ref).
Question: what (band, ref, threshold) combination would have ARMED before today's halts?"""
import json, urllib.request, urllib.parse, statistics as st
U="https://zestful-intuition-production-b16a.up.railway.app"
def bars10(tk):
    try:
        r=json.load(urllib.request.urlopen(f"{U}/api/bars?date=2026-08-10&ticker={urllib.parse.quote(tk)}~ALP10S",timeout=30)).get("bars") or []
    except Exception: return []
    out=[]
    for x in r:
        try:
            ts=str(x.get("time"))[11:19]; sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
            out.append((sec,float(x["close"])))
        except Exception: continue
    return out
names=["SCKT","STKH","XHLD","WYHG","RDGT","LZMH","PCLA","VIVK","JWEL","TNON","AUUD","HUDI","ZJYL","INHD"]
rows=[]
for tk in names:
    B=bars10(tk)
    if len(B)<100: continue
    med=st.median(B[i][0]-B[i-1][0] for i in range(1,len(B)))
    if med>20: continue
    for i in range(30,len(B)):
        gap=B[i][0]-B[i-1][0]
        if gap>=270 and B[i][1]>B[i-1][1]:   # UP-halt
            s=B[i-1][0]; px=B[i-1][1]
            w5=[c for k,c in B[:i] if k>=s-300]
            if len(w5)<10: continue
            ref_mean=st.mean(w5); ref_min=min(w5)
            band=0.10 if px>=3 else 0.20
            w1=[c for k,c in B[:i] if k>=s-60]
            vel=(px/w1[0]-1)*100 if w1 and w1[0] else 0
            rows.append(dict(tk=tk,t=f"{s//3600-4:02d}:{s%3600//60:02d}",px=round(px,2),
                prox_mean=round((px/ref_mean-1)/band,2),
                prox_min=round((px/ref_min-1)/band,2),
                prox_mean_halfband=round((px/ref_mean-1)/(band/2),2),
                vel1m=round(vel,1)))
print(f"UP-halts found: {len(rows)}")
for r in rows: print("  ",r)
import collections
for key in ("prox_mean","prox_min","prox_mean_halfband"):
    vals=[r[key] for r in rows]
    if vals:
        caught=sum(1 for v in vals if v>=0.7)
        caught5=sum(1 for r in rows if r[key]>=0.5 and r["vel1m"]>=4)
        print(f"{key}: median {st.median(vals):.2f} | >=0.7 catches {caught}/{len(vals)} | >=0.5+vel4 catches {caught5}/{len(vals)}")
