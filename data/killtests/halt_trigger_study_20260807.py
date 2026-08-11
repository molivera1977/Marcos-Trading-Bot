"""HALT TRIGGER STUDY (8/7, analysis-only; Marcos: "analyze the possible triggers. look at the bars").
For each HONEST up-halt (halt_inventory rows, LULD 4.5-20min, up-trend): compute at the pre-halt
pullback-close entry moment, from 10s bars only (all live-computable):
  band_prox  = (px / ref5min_low_anchor - 1) / band_width   [LULD physics: ref = 5-min rolling mean px;
               band = 10% (px>=3) else 20% (0.75-3) else 75%]
  wick_bb    = last 3 bars contain a bar whose low undercuts prior bar low AND closes in top half
  vel1m      = 1-min return %
  volx       = last-6-bar volume vs prior-30-bar avg
CONTROL: for the same (tk,d), sample every 3rd minute of RTH where vel1m>=3% and NO halt within
next 6 min; same features. Question: what separates halt-bound verticals from fades?
"""
import json,urllib.request,urllib.parse,statistics
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
def feats(B,i):
    """features at bar index i (the entry/decision bar)."""
    px=B[i][3]
    w5=[b for b in B[:i+1] if b[0]>=B[i][0]-300]
    if len(w5)<6: return None
    ref=statistics.mean(b[3] for b in w5)
    band=0.10 if px>=3 else (0.20 if px>=0.75 else 0.75)
    prox=(px/ref-1)/band if ref else 0
    w1=[b for b in B[:i+1] if b[0]>=B[i][0]-60]
    vel=(px/w1[0][3]-1)*100 if w1 and w1[0][3] else 0
    wick=False
    for j in range(max(1,i-2),i+1):
        rng=B[j][1]-B[j][2]
        if rng>0 and B[j][2]<B[j-1][2] and (B[j][3]-B[j][2])/rng>=0.5: wick=True
    v6=sum(b[4] for b in B[max(0,i-5):i+1])/6
    v30=sum(b[4] for b in B[max(0,i-35):max(1,i-5)])/max(len(B[max(0,i-35):max(1,i-5)]),1)
    volx=v6/v30 if v30 else 0
    return dict(prox=round(prox,2),vel1m=round(vel,1),wick=wick,volx=round(volx,1))
rows=[r for r in json.load(open("halt_inventory_rows_20260807.json"))
      if 4.5<=r["gap_min"]<=20 and r["trend5"]>0]
H=[];C=[]
seen=set()
for r in rows:
    B=bars10(r["tk"],r["d"])
    i=next((j for j in range(1,len(B)) if B[j-1][0]==r["t"]),None)
    if i is None: continue
    f=feats(B,i-1)
    if f: H.append(f)
    key=(r["tk"],r["d"])
    if key in seen: continue
    seen.add(key)
    halts={r2["t"] for r2 in rows if r2["tk"]==r["tk"] and r2["d"]==r["d"]}
    for j in range(30,len(B),18):
        s=B[j][0]
        if not (34200<=s<=57600): continue
        if any(0<=h-s<=360 for h in halts): continue
        f2=feats(B,j)
        if f2 and f2["vel1m"]>=3: C.append(f2)
import statistics as st
def summ(name,X):
    if not X: print(name,"none"); return
    print(f"{name}: n={len(X)} prox med {st.median(x['prox'] for x in X):.2f} "
          f"vel1m med {st.median(x['vel1m'] for x in X):.1f}% volx med {st.median(x['volx'] for x in X):.1f} "
          f"wick {sum(1 for x in X if x['wick'])}/{len(X)}")
summ("PRE-HALT ", H)
summ("CONTROL  ", C)
# threshold sweep on prox
for th in (0.5,0.6,0.7,0.8):
    hh=sum(1 for x in H if x["prox"]>=th); cc=sum(1 for x in C if x["prox"]>=th)
    print(f"prox>={th}: catches {hh}/{len(H)} halts, fires on {cc}/{len(C)} controls "
          f"(precision proxy {hh/max(hh+cc,1)*100:.0f}%)")
json.dump({"halt":H,"control":C},open("halt_trigger_feats_20260807.json","w"),indent=0)
