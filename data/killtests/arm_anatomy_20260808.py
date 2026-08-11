"""ARM ANATOMY (8/8 night): Friday's 18 canonical 5s-arm fires, winners vs losers.
What separates YJ 09:54 (+$399) from YJ 12:28 (-$106)? Candidate features (all live-computable):
halt cadence (prior halts today, mins since last halt), position in day's structure (fresh high?
% off high, run-up 30m), time of day, volume regime. One-day findings = REGISTERED HYPOTHESES."""
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
rows=json.load(open("data/killtests/arm_resolution_reconciled_rows_20260808.json"))["5S"]
feats=[]
for tk,tstr,px,pnl in rows:
    hh,mm=int(tstr[:2]),int(tstr[3:5]); s0=(hh+4)*3600+mm*60
    B=bars5(tk)
    prior=[i for i in range(1,len(B)) if B[i][0]-B[i-1][0]>=270 and B[i][0]<=s0 and B[i][0]>=13.5*3600]
    since=min((s0-B[i][0] for i in prior), default=None)
    pre=[b for b in B if b[0]<=s0]
    dayhi=max(b[1] for b in pre) if pre else px
    offhi=(dayhi-px)/dayhi*100
    w30=[b for b in pre if b[0]>=s0-1800]
    run30=(px/w30[0][3]-1)*100 if w30 and w30[0][3] else 0
    nhalts=len(prior)
    feats.append(dict(tk=tk,t=tstr,pnl=pnl,win=pnl>0,nhalts=nhalts,
                      since_halt_min=round(since/60,1) if since is not None else None,
                      off_hi_pct=round(offhi,2),run30=round(run30,1),hour=hh+mm/60))
W=[f for f in feats if f["win"]]; L=[f for f in feats if not f["win"]]
def med(xs): xs=[x for x in xs if x is not None]; return round(st.median(xs),2) if xs else None
print(f"{'feature':18s} {'WINNERS(9)':>12s} {'LOSERS(9)':>12s}")
for k in ("nhalts","since_halt_min","off_hi_pct","run30","hour"):
    print(f"{k:18s} {str(med([f[k] for f in W])):>12s} {str(med([f[k] for f in L])):>12s}")
print("\nfresh high (arm within 0.5% of day high): winners",
      sum(1 for f in W if f["off_hi_pct"]<=0.5),"/9  losers",sum(1 for f in L if f["off_hi_pct"]<=0.5),"/9")
print("first-or-second arm-with-halt-history (nhalts<=2): winners",
      sum(1 for f in W if f["nhalts"]<=2),"/9  losers",sum(1 for f in L if f["nhalts"]<=2),"/9")
print("morning (<11:00): winners",sum(1 for f in W if f["hour"]<11),"/9  losers",sum(1 for f in L if f["hour"]<11),"/9")
print()
for f in sorted(feats,key=lambda x:-x["pnl"]):
    print("  ",f)
