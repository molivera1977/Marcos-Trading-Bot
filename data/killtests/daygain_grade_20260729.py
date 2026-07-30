"""DAY-GAIN FLOOR GRADE on ignition (7/27-7/29), HONEST HARNESS: real detector stops (replay the
actual ignition_10s_step over archived tape), real sizing chain, calibrated slippage. Pre-registered
decision rule: lane-scope the floor (drop for ignition) only if the blocked cohort is POSITIVE in
dollars here."""
import json, urllib.request, sys, pathlib
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent/"rig"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
import harness
bot=load_bot()
bot.CURL_FIRE_MAX_AGE_SECS = 10**9        # replay: archived bars are always 'stale' to the guard
ET=timezone(timedelta(hours=-4)); U=harness.U
res=[]; miss=0
for day in ("2026-07-27","2026-07-28","2026-07-29"):
    rows=(json.load(urllib.request.urlopen(f"{U}/api/decisions_archive?date={day}&limit=50000",timeout=30)).get("rows") or [])
    rej=[r for r in rows if r.get("status")=="daygain_reject" and r.get("machine")=="ignition"]
    for r in rej:
        tk=r.get("ticker"); t0=str(r.get("recorded_at"))[11:19]
        b=harness.bars(tk,day)
        if not b: miss+=1; continue
        bot._ig10_st.pop(tk,None); best=None
        for i,bar in enumerate(b):
            f=bot.ignition_10s_step(tk,[bar[:6]])
            if f:
                dt=abs((datetime.strptime(bar[6],"%H:%M:%S")-datetime.strptime(t0,"%H:%M:%S")).total_seconds())
                if best is None or dt<best[0]: best=(dt,i,f)
        if not best or best[0]>180: miss+=1; continue
        _,i0,f=best
        rep=harness.replay(tk,day,f["px"],f["stop"],i0=i0)
        if rep is None: miss+=1; continue
        res.append((day[5:],tk,r.get("day_gain"),f["px"],f["stop"],rep))
print("blocked-cohort fires graded:",len(res)," ungradeable:",miss)
ok=[x for x in res if not x[5]["refused"]]
print(f"{'date':6}{'tkr':6}{'daygn':>6}{'entry':>8}{'width':>7}{'sh':>5}{'clamp':>13}{'P&L':>9}")
for d,tk,dg,e,s,rep in sorted(res,key=lambda x:-(x[5]['pnl'])):
    w=100*(e-s)/e
    print(f"{d:6}{tk:6}{dg:5.1f}%{e:8.3f}{w:6.2f}%{rep['shares']:5}{rep['clamp']:>13}{rep['pnl']:9.2f}")
W=[x[5]["pnl"] for x in ok if x[5]["pnl"]>0]; L=[x[5]["pnl"] for x in ok if x[5]["pnl"]<=0]
tot=sum(x[5]["pnl"] for x in ok)
print(f"\ntradeable {len(ok)} (refused-by-sizing {len(res)-len(ok)})  wins {len(W)} ({100*len(W)/max(len(ok),1):.0f}%)")
print(f"TOTAL ${tot:+.2f}   $/fire ${tot/max(len(ok),1):+.2f}"
      + (f"   avgW ${sum(W)/len(W):.2f} avgL ${sum(L)/len(L):.2f} payoff {abs((sum(W)/len(W))/(sum(L)/len(L))):.2f}" if W and L else ""))
print("gate's actual result: $0.00 (all refused). Slip model 1.477%; volume guard modeled.")
