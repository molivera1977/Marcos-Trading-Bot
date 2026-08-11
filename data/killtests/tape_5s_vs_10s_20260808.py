"""5s vs 10s — FRIDAY'S FIRES REPLAYED AT BOTH RESOLUTIONS (Marcos 8/6: "we can compare... both
10s and 5s and see who could have done better"). For every closed 8/7 trade: re-run the frozen
engine on 10s bars AND on 5s bars from the same entry moment/price. Differences isolate what
resolution alone changes: scale timing, trail tightness (6-bar 10s = 60s vs 12-bar 5s = 60s —
same wall-time window), stop-touch detection. Dollars per trade, both columns."""
import json,urllib.request,urllib.parse,datetime
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u,timeout=60))
def bars(tk,suf):
    r=get(f"{U}/api/bars?date=2026-08-07&ticker={urllib.parse.quote(tk)}~{suf}").get("bars") or []
    out=[]
    for x in r:
        ts=str(x.get("time"))[11:19]
        sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
        out.append((sec,float(x["high"]),float(x["low"]),float(x["close"])))
    return out
def sim(B,i,e,stop,trail_n):
    r1=e-stop
    if r1<=0: return None
    pnl=0.0;rem=1.0;sc=False;lows=[]
    for j in range(i,len(B)):
        s,h,l,c=B[j]
        if not sc and h>=e+r1: pnl+=0.5*r1;rem=0.5;sc=True;stop=e
        if sc:
            lows.append(l)
            if len(lows)>trail_n: lows.pop(0)
            if len(lows)==trail_n: stop=max(stop,min(lows))
        if l<=stop: return pnl+rem*(max(stop,l)-e)
    return pnl+rem*(B[-1][3]-e)
t=[x for x in get(U+"/api/trades")["trades"] if x.get("date")=="2026-08-07" and x.get("entry_ts_utc")]
t10=t5=act=0.0;n=0
print(f"{'tk':6s} {'actual':>8s} {'sim10s':>8s} {'sim5s':>8s}")
for x in t:
    tk=x["ticker"];e=float(x.get("entry") or 0);rps=float(x.get("risk_per_share") or 0)
    sh=int(x.get("shares") or 0);a=float(x.get("pnl") or 0)
    if not (e>0 and rps>0 and sh>0): continue
    dt=datetime.datetime.fromisoformat(str(x["entry_ts_utc"]).replace("Z","+00:00"))
    es=dt.hour*3600+dt.minute*60+dt.second
    B10=bars(tk,"ALP10S");B5=bars(tk,"ALP5S")
    i10=next((j for j,b in enumerate(B10) if b[0]>=es),None)
    i5=next((j for j,b in enumerate(B5) if b[0]>=es),None)
    if i10 is None or i5 is None or len(B10)-i10<10 or len(B5)-i5<20: continue
    p10=sim(B10,i10,e,e-rps,6);p5=sim(B5,i5,e,e-rps,12)
    if p10 is None or p5 is None: continue
    n+=1;act+=a;t10+=p10*sh;t5+=p5*sh
    print(f"{tk:6s} {a:+8.2f} {p10*sh:+8.2f} {p5*sh:+8.2f}")
print(f"\n{n} trades: ACTUAL ${act:+.2f}  ENGINE-10s ${t10:+.2f}  ENGINE-5s ${t5:+.2f}")
print("(same wall-time trail window: 6x10s vs 12x5s = 60s both)")
