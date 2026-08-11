"""HIDDEN ARM-THRESHOLD BANDS (8/6 ~13:2x, rules frozen pre-run; Marcos: "run a replay").
Q: the hidden lane arms at 25%/5min (HOMEGROWN translation of Kev's "rocketing up"). Today's
whale bursts (WYHG +17.7, SUGP +16, PN +15.1 per-5min) flew UNDER it. Do 15-25%% bursts pay?
PROXY (stated plainly — this is NOT the full detector): for each watched name-day, find the
FIRST 10s bar completing a 5-min gain in each band [15-20), [20-25), [25+ control]; enter at
that bar's close; stop = min low of the prior 6 bars (wick proxy), floored at -6%%; engine =
half at +1R, stop->BE, rolling prev-minute-low trail; width-band sizing ($20/<5,25/5-6,30/>=6).
One entry per name-day-band. Cohort: each day's watched roster (daily_loaded tickers), 7/28+.
FROZEN VERDICT: a sub-25 band is ship-candidate for CROWNS iff total >= +$75 AND winners >=45%%
AND the 25+ control band is ALSO positive (sanity: if even the current band loses in this
proxy, the proxy is too blunt to ship anything -> Friday info only)."""
import json, urllib.request, urllib.parse, pathlib
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u):
    try: return json.load(urllib.request.urlopen(u,timeout=60))
    except Exception: return {}
DAYS=["2026-07-28","2026-07-29","2026-07-30","2026-07-31","2026-08-03","2026-08-04","2026-08-05","2026-08-06"]
def sim(B,i0,e,s):
    pnl=0.0; rem=1.0; sc=False; stop=s; lows=[]
    for j in range(i0,len(B)):
        _,h,l,c=B[j]
        if not sc and h>=e+(e-s): pnl+=0.5*(e-s); rem=0.5; sc=True; stop=e; continue
        if sc:
            lows.append(l)
            if len(lows)>6: lows.pop(0)
            if len(lows)==6: stop=max(stop,min(lows))
        if l<=stop: return pnl+rem*(max(stop,l)-e)
    return pnl+(rem*(B[-1][3]-e) if B else 0)
bands={"15-20":[], "20-25":[], "25+ (control)":[]}
for d in DAYS:
    r=get(f"{U}/api/decisions_archive?date={d}&status=daily_loaded&limit=50000")
    rows=r.get("rows") or r.get("decisions") or []
    names=sorted({x["ticker"] for x in rows if x.get("ticker") and not x["ticker"].startswith("_")})[:40]
    for tk in names:
        rr=get(f"{U}/api/bars?date={d}&ticker={urllib.parse.quote(tk)}~ALP10S").get("bars") or []
        B=[]
        for x in rr:
            ts=str(x.get("time"))[11:19]
            sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
            if sec>=13*3600+1800:   # RTH only (UTC)
                B.append((sec,float(x.get("high") or 0),float(x.get("low") or 0),float(x.get("close") or 0)))
        if len(B)<60: continue
        done=set()
        for j in range(len(B)):
            if len(done)==3: break
            base=None
            for i in range(j-1,-1,-1):
                if B[j][0]-B[i][0]>300: break
                base=B[i][3]
            if not base or base<=0: continue
            g=100*(B[j][3]/base-1)
            for lbl,lo,hi in (("15-20",15,20),("20-25",20,25),("25+ (control)",25,1e9)):
                if lbl in done or not (lo<=g<hi): continue
                done.add(lbl)
                e=B[j][3]; s=max(min(x[2] for x in B[max(0,j-6):j+1]), e*0.94)
                if e<=s: continue
                w=100*(e-s)/e; risk=20 if w<5 else (25 if w<6 else 30); sh=risk/(e-s)
                bands[lbl].append(round(sim(B,j+1,e,s)*sh,2))
for lbl,v in bands.items():
    if v:
        wins=sum(1 for p in v if p>0)
        print(f"{lbl:<14} n={len(v):>3} total ${sum(v):+9.2f} mean ${sum(v)/len(v):+6.2f} winners {wins}/{len(v)} ({100*wins/len(v):.0f}%)")
    else: print(f"{lbl:<14} n=0")