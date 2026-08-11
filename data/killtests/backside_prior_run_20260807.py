"""BACKSIDE BAND vs PRIOR-RUN CREDENTIAL (8/7 00:3x, rules frozen pre-run; ADGM 8/4 specimen).
Q: in-band entries (15-30% below a >=20min-stale session high, dip_rip exempt) split by whether
the name ALREADY RAN today: credential = session high >= K x session first-close (K=1.40 A, 1.25 B).
SHIP-CANDIDATE iff credentialed in-band subgroup >= +$75 total AND n>=8. Era 7/13+, RTH entries.
"""
import json,urllib.request,urllib.parse,datetime
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
            out.append((sec,float(x["high"]),float(x["low"]),float(x["close"])))
        except Exception: continue
    _b[(tk,d)]=out; return out
trades=[t for t in get(U+"/api/trades")["trades"]
        if str(t.get("date") or "")>="2026-07-14" and t.get("entry_ts_utc")
        and t.get("entry_session")!="PRE" and str(t.get("entry_type"))!="dip_rip"]
groups={}
nband=0
for t in trades:
    tk,d=t["ticker"],t["date"]
    B=bars10(tk,d)
    if len(B)<30: continue
    dt_=datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z","+00:00"))
    es=dt_.hour*3600+dt_.minute*60+dt_.second
    hi=0.0;hi_t=None
    for s,h,l,c in B:
        if s>=es: break
        if h>hi: hi,hi_t=h,s
    if not hi or hi_t is None: continue
    e=float(t.get("entry") or 0)
    if not e: continue
    below=(hi-e)/hi*100
    inband=15.0<=below<=30.0 and (es-hi_t)>=1200
    if not inband: continue
    nband+=1
    o=B[0][3]
    runx=hi/o if o else 0
    a=float(t.get("pnl") or 0)
    for name,k in (("A_run40",1.40),("B_run25",1.25)):
        key=(name, runx>=k)
        g=groups.setdefault(key,[0,0.0,0])
        g[0]+=1;g[1]+=a;g[2]+=(1 if a>0 else 0)
    groups.setdefault(("all",True),[0,0.0,0])
    g=groups[("all",True)];g[0]+=1;g[1]+=a;g[2]+=(1 if a>0 else 0)
print(f"era RTH non-dip_rip trades in 15-30%%/stale band: {nband}\n")
g=groups[("all",True)]
print(f"ALL in-band:              n={g[0]:3d} total ${g[1]:+8.2f} winners {g[2]}/{g[0]}")
for name in ("A_run40","B_run25"):
    for cred in (True,False):
        g=groups.get((name,cred),[0,0.0,0])
        tag="CREDENTIALED" if cred else "no-credential"
        ship=""
        if cred: ship="  SHIP-CANDIDATE" if (g[1]>=75 and g[0]>=8) else "  NOT MET"
        print(f"{name} {tag:14s} n={g[0]:3d} total ${g[1]:+8.2f} winners {g[2]}/{max(g[0],1)}{ship}")
