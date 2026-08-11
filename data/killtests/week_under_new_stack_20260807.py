"""WEEK 8/3-8/6 UNDER TONIGHT'S FULL STACK (run 8/7 ~00:1x, rules frozen before run).
Mechanisms replayed per real trade, in real gate order:
  1. AMBIENT 15x floor (med $vol prior-10 1-min >= $15k) — from ambient_liquidity rows.
  2. BACKSIDE gate applied to 8/3-8/4 (live 8/5+ already): entry 15-30% below a >=20-min-stale
     session high -> blocked (dip_rip exempt).
  3. RETEST 1% on flat_top/ignition/orb (RTH): re-simmed with the frozen killtest engine.
  4. CROWN ext bypass ADD: PN 8/6 11:55:02 (first crown ext reject) entered, same engine.
NOT REPLAYABLE (listed, not scored): mapless block (no per-trade map-state history), freshest
gates (CELZ ~$150 8/6 est stands), rehydrate/priority-queue latency, deploy-freeze (WYHG kill
already counted at real $0 vs +$1.81 real-engine counterfactual), blue-sky (trading OFF = no change).
"""
import json, urllib.request, urllib.parse, datetime
U="https://zestful-intuition-production-b16a.up.railway.app"
KT='/Users/marcosolivera/Desktop/Marcos-Trading-Bot/data/killtests/'
WK=('2026-08-03','2026-08-04','2026-08-05','2026-08-06')
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
            out.append((sec,float(x.get("high") or 0),float(x.get("low") or 0),float(x.get("close") or 0)))
        except Exception: continue
    _b[(tk,d)]=out; return out
def sim(B,i0,e,stop0,r1):
    pnl=0.0;rem=1.0;sc=False;stop=stop0;lows=[]
    for j in range(i0,len(B)):
        _,h,l,c=B[j]
        if not sc and h>=e+r1:
            pnl+=0.5*r1;rem=0.5;sc=True;stop=e;continue
        if sc:
            lows.append(l)
            if len(lows)>6: lows.pop(0)
            if len(lows)==6: stop=max(stop,min(lows))
        if l<=stop: return pnl+rem*(max(stop,l)-e)
    return pnl+(rem*(B[-1][3]-e) if B else 0)

trades=[t for t in get(U+"/api/trades")["trades"] if t.get("date") in WK]
amb={(r['d'],r['tk'],round(r['pnl'],2)):r['med_dvol'] for r in json.load(open(KT+'ambient_liquidity_rows_20260806.json')) if r['d'] in WK}

def esec(t):
    dt_=datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z","+00:00"))
    return dt_.hour*3600+dt_.minute*60+dt_.second

def backside_blocked(t):
    if t["date"] not in ("2026-08-03","2026-08-04"): return False
    if str(t.get("entry_type"))=="dip_rip": return False
    if not t.get("entry_ts_utc"): return False
    B=bars10(t["ticker"],t["date"])
    if len(B)<30: return False
    es=esec(t); hi=0.0; hi_t=None
    for s,h,l,c in B:
        if s>=es: break
        if h>hi: hi,hi_t=h,s
    if not hi or hi_t is None: return False
    e=float(t.get("entry") or 0)
    below=(hi-e)/hi*100
    return 15.0<=below<=30.0 and (es-hi_t)>=1200

RL=("flat_top","ignition","orb")
adj=[]; total_delta=0.0
for t in trades:
    d,tk=t["date"],t["ticker"]; a=float(t.get("pnl") or 0)
    key=(d,tk,round(a,2))
    if key in amb and amb[key]<15000:
        adj.append((d,tk,a,"AMBIENT-BLOCKED",0.0)); total_delta+=-a; continue
    if backside_blocked(t):
        adj.append((d,tk,a,"BACKSIDE-BLOCKED",0.0)); total_delta+=-a; continue
    if str(t.get("entry_type")) in RL and t.get("entry_session")!="PRE" and t.get("entry_ts_utc"):
        e=float(t.get("entry") or 0);rps=float(t.get("risk_per_share") or 0);sh=int(t.get("shares") or 0)
        if e>0 and rps>0 and sh>0:
            B=bars10(tk,d)
            es=esec(t); i0=next((j for j,x in enumerate(B) if x[0]>=es),None)
            if i0 is not None and len(B)>=30:
                lvl=e*0.99
                ir=next((j for j in range(i0,len(B)) if B[j][0]<=es+900 and B[j][2]<=lvl),None)
                if ir is None:
                    adj.append((d,tk,a,"RETEST-MISSED",0.0)); total_delta+=-a; continue
                p=sim(B,ir,lvl,e-rps,rps)*sh
                if abs(p-a)>0.005:
                    adj.append((d,tk,a,"RETEST-1%%",p)); total_delta+=p-a
                continue
# CROWN ADD: PN 8/6, first ext reject 11:55:02 fire 11.385 stop 10.8585? use that row's own stop 10.8157? first row 11:55:02 fire_px 11.385 stop 10.8157
B=bars10("PN","2026-08-06")
es=15*3600+55*60+2  # 11:55:02 ET = 15:55:02 UTC
i0=next((j for j,x in enumerate(B) if x[0]>=es),None)
pn_add=0.0
if i0 is not None:
    e,st=11.385,10.8157
    sh=int(1000//e)  # $1000 cap sizing chain approximation, flagged
    pn_add=sim(B,i0,e,st,e-st)*sh
    adj.append(("2026-08-06","PN",0.0,"CROWN-EXT-ADD",pn_add)); total_delta+=pn_add

byd={d:{"A":0.0,"C":0.0} for d in WK}
for t in trades: byd[t["date"]]["A"]+=float(t.get("pnl") or 0)
for d in WK: byd[d]["C"]=byd[d]["A"]
for (d,tk,a,why,p) in adj: byd[d]["C"]+=p-a
print("per-trade adjustments:")
for (d,tk,a,why,p) in adj:
    print(f"  {d} {tk:6s} {why:16s} ${a:+8.2f} -> ${p:+8.2f}  (Δ ${p-a:+7.2f})")
print("\nday        ACTUAL      WITH-TONIGHT'S-STACK")
wa=wc=0.0
for d in WK:
    print(f"{d}  ${byd[d]['A']:+9.2f}   ${byd[d]['C']:+9.2f}")
    wa+=byd[d]['A']; wc+=byd[d]['C']
print(f"WEEK       ${wa:+9.2f}   ${wc:+9.2f}   (Δ ${wc-wa:+.2f})")
