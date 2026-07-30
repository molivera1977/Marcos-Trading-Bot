"""SCALE-LESS TEST (pre-registered): does banking less at 1R/2R let winners become real?
A = live 50@1R+25@2R BE@2 | B = 33@1R+25@2R BE@2 | C = 33@1R only BE@1 | D = 25@1R only BE@1.
Decision rule (written first): an arm must beat A in TOTAL dollars on BOTH cohorts; else A stays."""
import json, urllib.request, sys, pathlib
from datetime import datetime, timedelta, timezone
import harness
ET=timezone(timedelta(hours=-4))
ARMS={"A live 50/25":dict(tiers=((1,.50),(2,.25)),be_after=2),
      "B 33/25":dict(tiers=((1,.33),(2,.25)),be_after=2),
      "C 33 only":dict(tiers=((1,.33),),be_after=1),
      "D 25 only":dict(tiers=((1,.25),),be_after=1)}
rows=[r for r in (json.load(urllib.request.urlopen(f"{harness.U}/api/trades")).get("trades") or []) if isinstance(r,dict)]
def hm(r):
    try: return datetime.fromisoformat(str(r.get("entry_ts_utc")).replace("Z","+00:00")).astimezone(ET).strftime("%H:%M:%S")
    except Exception: return None
EXCL={("NCRA","09:31"),("AMIX","09:32"),("AMIX","10:05"),("STFS","09:39"),("YYGH","10:38"),
      ("NCRA","08:04"),("NCRA","08:18"),("NCRA","08:20")}
clean=[]
for r in rows:
    d=str(r.get("date")); t=hm(r)
    if d not in ("2026-07-28","2026-07-29") or not t: continue
    if (r.get("ticker"),t[:5]) in EXCL: continue
    e,s=r.get("entry"),r.get("stop_loss")
    if e and s and e>s: clean.append((r["ticker"],d,e,s,t))
sys.path.insert(0,str(pathlib.Path("../../rig").resolve()))
from loader import load_bot
bot=load_bot(); bot.CURL_FIRE_MAX_AGE_SECS=10**9
dg=[]
for day in ("2026-07-27","2026-07-28","2026-07-29"):
    rws=(json.load(urllib.request.urlopen(f"{harness.U}/api/decisions_archive?date={day}&limit=50000",timeout=30)).get("rows") or [])
    for r in [x for x in rws if x.get("status")=="daygain_reject" and x.get("machine")=="ignition"]:
        tk=r.get("ticker"); t0=str(r.get("recorded_at"))[11:19]
        b=harness.bars(tk,day)
        if not b: continue
        bot._ig10_st.pop(tk,None); best=None
        for i,bar in enumerate(b):
            f=bot.ignition_10s_step(tk,[bar[:6]])
            if f:
                dt=abs((datetime.strptime(bar[6],"%H:%M:%S")-datetime.strptime(t0,"%H:%M:%S")).total_seconds())
                if best is None or dt<best[0]: best=(dt,i,f)
        if best and best[0]<=180: dg.append((tk,day,best[2]["px"],best[2]["stop"],best[1]))
print(f"cohorts: clean n={len(clean)}  daygain n={len(dg)}\n")
print(f"{'arm':16}{'clean $':>10}{'wins':>6}{'daygain $':>11}{'wins':>6}{'BOTH beat A?':>14}")
base={}
for name,kw in ARMS.items():
    tc=wc=0
    for tk,d,e,s,t in clean:
        rep=harness.replay(tk,d,e,s,entry_hm=t,**kw)
        if rep and not rep.get("refused"):
            tc+=rep["pnl"]; wc+= rep["pnl"]>0
    tg=wg=0
    for tk,d,e,s,i0 in dg:
        rep=harness.replay(tk,d,e,s,i0=i0,**kw)
        if rep and not rep.get("refused"):
            tg+=rep["pnl"]; wg+= rep["pnl"]>0
    if name.startswith("A"): base=( tc,tg )
    beats = "" if name.startswith("A") else ("YES" if tc>base[0] and tg>base[1] else "no")
    print(f"{name:16}{tc:10.2f}{wc:6d}{tg:11.2f}{wg:6d}{beats:>14}")
