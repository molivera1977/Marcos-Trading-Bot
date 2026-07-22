import json, os, hashlib, urllib.parse, urllib.request, time, statistics as st
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u):
    k="mcache/"+hashlib.md5(u.encode()).hexdigest()+".json"
    if os.path.exists(k):
        try: return json.load(open(k))
        except: pass
    for _ in range(3):
        try:
            time.sleep(0.7); r=json.load(urllib.request.urlopen(u,timeout=45)); json.dump(r,open(k,"w")); return r
        except Exception: time.sleep(2)
    return {}
ts=get(f"{U}/api/trades?date=2026-07-21"); ts=ts if isinstance(ts,list) else ts.get('trades',[])
DATES=sorted({t.get("date") for t in ts if t.get("date")})
def bars(t,d):
    b=[x for x in (get(f"{U}/api/minute_ext?ticker={urllib.parse.quote(t)}&count=1200").get("bars") or []) if str(x.get("time","")).startswith(d) and x.get("session")=="RTH"]
    b.sort(key=lambda x:str(x["time"])); return b
rows=[]; unmeasured=0; nojoin=0
for d in DATES:
    dec=get(f"{U}/api/decisions_archive?date={d}&limit=12000").get("rows") or []
    trig={}
    for r in dec:
        if str(r.get("status","")).startswith("triggered"):
            tk=(r.get("ticker") or "").upper(); ra=str(r.get("recorded_at") or "")
            if len(ra)>=16: trig.setdefault(tk,[]).append(ra[11:16])
    for t in ts:
        if t.get("date")!=d: continue
        tk=(t.get("ticker") or "").upper(); p=t.get("pnl")
        if p is None: continue
        if tk not in trig: nojoin+=1; continue
        et=sorted(trig[tk])[0]; hh,mm=int(et[:2]),int(et[3:5]); utc=f"{hh+4:02d}:{mm:02d}"
        b=bars(tk,d)
        c=[float(x["close"]) for x in b]; tm=[str(x["time"])[11:16] for x in b]
        ei=next((i for i in range(len(tm)) if tm[i]>=utc), None) if b else None
        if ei is None or ei<5 or ei>=len(c): unmeasured+=1; continue
        vel=(c[ei]-c[ei-5])/c[ei-5]*100
        rows.append((d,tk,et,vel,float(p)))
print(f"trades in window: {sum(1 for t in ts if t.get('pnl') is not None)} | joined+measured: {len(rows)} | no-decision-join: {nojoin} | unmeasured(early/sparse): {unmeasured}")
print(f"\n{'date':<12}{'tkr':<7}{'ET':>6}{'vel5%':>8}{'P&L$':>9}")
for d,tk,et,v,p in sorted(rows): print(f"{d:<12}{tk:<7}{et:>6}{v:>7.1f}%{p:>9.2f}")
print(f"\n{'bucket':<12}{'n':>4}{'win%':>6}{'avg$':>8}{'total$':>9}")
for lo,hi,lab in [(-99,-1,"<-1%"),(-1,0,"-1-0%"),(0,1,"0-1%"),(1,3,"1-3%"),(3,8,"3-8%"),(8,999,">=8%")]:
    s=[(v,p) for _,_,_,v,p in rows if lo<=v<hi]
    if s:
        n=len(s); w=sum(1 for _,p in s if p>0)
        print(f"{lab:<12}{n:>4}{100*w/n:>5.0f}%{sum(p for _,p in s)/n:>8.2f}{sum(p for _,p in s):>9.1f}")
print("\nFLOOR SWEEP (trades cut if vel5 < F):")
for F in [-1,0,0.5,1]:
    cut=[p for *_,v,p in rows if v<F]
    keep=[p for *_,v,p in rows if v>=F]
    if cut: print(f"  F={F}: cuts {len(cut)} (${sum(cut):+.1f}) keeps {len(keep)} (${sum(keep):+.1f})  {'CUTS LOSSES ✅' if sum(cut)<0 else 'CUTS GAINS ❌'}")
