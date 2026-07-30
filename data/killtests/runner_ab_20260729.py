"""RUNNER A/B (pre-registered): arm A = 3-min-low ratchet trail (live) vs arm B = health-fold hold
(3-min close < EMA9 AND < session VWAP after >=1 partial). Same entries, stops, sizing, slippage.
VALIDATION first: arm B must roughly reproduce the REAL health-fold exits we have timestamps for.
Decision rule (written first): arm B wins if it adds total dollars without raising the loss side
(losses are stop-governed and shouldn't change materially)."""
import json, urllib.request
from datetime import datetime, timedelta, timezone
import harness
ET=timezone(timedelta(hours=-4))
rows=[r for r in (json.load(urllib.request.urlopen(f"{harness.U}/api/trades")).get("trades") or []) if isinstance(r,dict)]
def hm(r):
    try: return datetime.fromisoformat(str(r.get("entry_ts_utc")).replace("Z","+00:00")).astimezone(ET).strftime("%H:%M:%S")
    except Exception: return None
EXCL={("NCRA","09:31"),("AMIX","09:32"),("AMIX","10:05"),("STFS","09:39"),("YYGH","10:38"),
      ("NCRA","08:04"),("NCRA","08:18"),("NCRA","08:20")}
print("── VALIDATION: real HEALTH FOLD exits reproduced by arm B?")
for r in rows:
    if "HEALTH FOLD" in str(r.get("exit_reason") or "") and hm(r):
        rep=harness.replay(r["ticker"],str(r["date"]),r["entry"],r["stop_loss"],entry_hm=hm(r),
                           shares=r["shares"],runner="health")
        if rep: print(f"  {r['date'][5:]} {r['ticker']:6} booked {r['pnl']:+8.2f}  armB {rep['pnl']:+8.2f}")
print("\n── A/B on clean 7/28-7/29 trades (recorded entry/stop, sized via real chain)")
res=[]
for r in rows:
    d=str(r.get("date")); t=hm(r)
    if d not in ("2026-07-28","2026-07-29") or not t: continue
    if (r.get("ticker"),t[:5]) in EXCL: continue
    e,s=r.get("entry"),r.get("stop_loss")
    if not (e and s and e>s): continue
    A=harness.replay(r["ticker"],d,e,s,entry_hm=t,runner="trail")
    B=harness.replay(r["ticker"],d,e,s,entry_hm=t,runner="health")
    if A and B and not A.get("refused") and not B.get("refused"):
        res.append((d[5:],r["ticker"],t[:5],A["pnl"],B["pnl"]))
print(f"{'date':6}{'tkr':7}{'time':6}{'A trail':>9}{'B health':>10}{'B-A':>8}")
for d,tk,t,a,b in sorted(res,key=lambda x:x[4]-x[3]):
    print(f"{d:6}{tk:7}{t:6}{a:9.2f}{b:10.2f}{b-a:8.2f}")
sa=sum(x[3] for x in res); sb=sum(x[4] for x in res)
print(f"\nn={len(res)}   ARM A (trail) ${sa:+.2f}   ARM B (health) ${sb:+.2f}   diff ${sb-sa:+.2f}")
print("\n── A/B on the 28-fire day-gain ignition cohort (detector stops, from tonight's grade)")
import sys,pathlib
sys.path.insert(0,str(pathlib.Path("../../rig").resolve()))
from loader import load_bot
bot=load_bot(); bot.CURL_FIRE_MAX_AGE_SECS=10**9
resg=[]
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
                dtt=abs((datetime.strptime(bar[6],"%H:%M:%S")-datetime.strptime(t0,"%H:%M:%S")).total_seconds())
                if best is None or dtt<best[0]: best=(dtt,i,f)
        if not best or best[0]>180: continue
        _,i0,f=best
        A=harness.replay(tk,day,f["px"],f["stop"],i0=i0,runner="trail")
        B=harness.replay(tk,day,f["px"],f["stop"],i0=i0,runner="health")
        if A and B and not A.get("refused"): resg.append((A["pnl"],B["pnl"]))
ga=sum(x[0] for x in resg); gb=sum(x[1] for x in resg)
print(f"n={len(resg)}   ARM A ${ga:+.2f}   ARM B ${gb:+.2f}   diff ${gb-ga:+.2f}")
