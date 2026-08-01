"""GRADE 3A: flat_top's 444 era fires by FRONT-SIDE flag — forward mark-outs (no stops stamped,
so this grades DIRECTION, not a trade sim). Pre-registered question: does the back-side edge
(+$159.99 on n=6 converted) hold at fire level, n=444?"""
import json, urllib.request, collections, datetime, statistics
import harness
U=harness.U
DAYS=["2026-07-%02d"%d for d in (13,14,15,16,17,20,21,22,23,24,27,28,29,30,31)]
fires=[]
for d in DAYS:
    try: rows=json.load(urllib.request.urlopen(f"{U}/api/decisions_archive?date={d}&limit=50000",timeout=60)).get("rows") or []
    except Exception: continue
    for r in rows:
        if r.get("status")!="triggered_flat_top": continue
        fs=r.get("front_side")
        if fs is None: continue
        tm=r.get("time")
        try: hm=datetime.datetime.strptime(tm,"%I:%M:%S %p").strftime("%H:%M:%S")
        except Exception: continue
        fires.append({"d":d,"tk":r.get("ticker"),"hm":hm,"px":r.get("price"),"fs":bool(fs)})
print(f"fires with stamp: {len(fires)}  (front {sum(1 for f in fires if f['fs'])} / back {sum(1 for f in fires if not f['fs'])})")
out=collections.defaultdict(lambda: collections.defaultdict(list))
cov=0
for f in fires:
    b=harness.bars(f["tk"],f["d"])
    if not b or not f["px"]: continue
    i0=next((i for i,x in enumerate(b) if x[6]>=f["hm"]),None)
    if i0 is None: continue
    cov+=1
    for lab,nb in (("15m",90),("30m",180),("60m",360)):
        j=min(i0+nb,len(b)-1)
        out[f["fs"]][lab].append((b[j][4]-f["px"])/f["px"]*100)
print(f"priced: {cov}")
for fs in (True,False):
    print(f"\n{'FRONT-side' if fs else 'BACK-side'} fires:")
    for lab in ("15m","30m","60m"):
        v=out[fs][lab]
        if not v: continue
        print(f"  +{lab}: n={len(v):>3}  median {statistics.median(v):+6.2f}%  mean {sum(v)/len(v):+6.2f}%  "
              f"positive {100*sum(1 for x in v if x>0)/len(v):>4.0f}%")
