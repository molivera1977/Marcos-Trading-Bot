"""SIZING 4-ARM (7/29 night, pre-registered): status-quo · refuse<3% · attempt-ladder · width-proportional.
EXACT method: arms change SIZE only (entries/exits/DRY_RUN paths unchanged), so each arm's P&L =
observed per-share P&L × the arm's share count. Slippage is embedded in the observed outcome.
Era 7/13+, excision list excluded. Decision rule (written first): an arm wins if it improves total
dollars AND per-trade dollars without cutting winner count >30%."""
import json, urllib.request, collections
from datetime import datetime, timedelta, timezone
ET=timezone(timedelta(hours=-4)); U="https://zestful-intuition-production-b16a.up.railway.app"
RISK, CAP, REF_W = 30.0, 1000.0, 0.06
EXCL={("NCRA","2026-07-29","09:31"),("AMIX","2026-07-29","09:32"),("AMIX","2026-07-29","10:05"),
      ("STFS","2026-07-29","09:39"),("YYGH","2026-07-29","10:38"),("YYGH","2026-07-29","10:49"),
      ("NCRA","2026-07-29","08:04"),("WBUY","2026-07-28","15:21")}
rows=[r for r in (json.load(urllib.request.urlopen(f"{U}/api/trades")).get("trades") or []) if isinstance(r,dict)]
def hm(r):
    try: return datetime.fromisoformat(str(r.get("entry_ts_utc")).replace("Z","+00:00")).astimezone(ET).strftime("%H:%M")
    except Exception: return "?"
T=[]
for r in sorted(rows,key=lambda x:str(x.get("recorded_at"))):
    d=str(r.get("date") or "")
    if d<"2026-07-13": continue
    e,s,sh,p=r.get("entry"),r.get("stop_loss"),r.get("shares"),r.get("pnl")
    if not (e and s and sh and p is not None and e>s and sh>0): continue
    if (r.get("ticker"),d,hm(r)) in EXCL: continue
    T.append({"tk":r.get("ticker"),"d":d,"w":(e-s)/e,"e":e,"sh":sh,"pps":p/sh,"p":p})
seq=collections.Counter()
for t in T:
    seq[(t["tk"],t["d"])]+=1; t["att"]=seq[(t["tk"],t["d"])]
def shares_for(t,risk):
    return int(min(risk/( t["e"]*t["w"] ), CAP/t["e"], t["sh"]*10))  # vol guard already inside observed sh? keep min with risk/notional
def arm(t,mode):
    if mode=="status": return t["sh"]
    if mode=="refuse": return 0 if t["w"]<0.03 else t["sh"]
    if mode=="ladder": risk=(RISK if t["att"]==1 else RISK/2 if t["att"]==2 else 0)
    elif mode=="prop": risk=RISK*min(1.0,t["w"]/REF_W)
    if risk<=0: return 0
    return min(t["sh"], int(risk/(t["e"]*t["w"])) or 0)   # never MORE shares than really traded (vol/cap already bound)
print(f"n={len(T)} era trades (excised, computable)")
print(f"{'arm':22}{'trades':>7}{'wins':>6}{'total $':>11}{'$/trade':>9}{'winners lost':>13}")
base_w=sum(1 for t in T if t["p"]>0)
for mode,label in [("status","STATUS QUO"),("refuse","REFUSE <3%"),("ladder","ATTEMPT LADDER 30/15/0"),("prop","WIDTH-PROPORTIONAL")]:
    tot=0; n=0; w=0
    for t in T:
        s2=arm(t,mode)
        if s2<=0: continue
        n+=1; pl=t["pps"]*s2; tot+=pl
        if pl>0: w+=1
    print(f"{label:22}{n:7}{w:6}{tot:11.2f}{tot/max(n,1):9.2f}{base_w-w:13}")
# combined: ladder + proportional stack
tot=0;n=0;w=0
for t in T:
    risk=(RISK if t["att"]==1 else RISK/2 if t["att"]==2 else 0)
    risk*=min(1.0,t["w"]/REF_W)
    s2=0 if risk<=0 else min(t["sh"],int(risk/(t["e"]*t["w"])) or 0)
    if s2<=0: continue
    n+=1; pl=t["pps"]*s2; tot+=pl
    if pl>0:w+=1
print(f"{'LADDER + PROPORTIONAL':22}{n:7}{w:6}{tot:11.2f}{tot/max(n,1):9.2f}{base_w-w:13}")
