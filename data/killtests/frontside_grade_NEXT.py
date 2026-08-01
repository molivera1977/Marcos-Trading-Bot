"""NEXT FRIDAY'S FRONT-SIDE GRADE (registered 7/31; run on/after 8/8 with a week of forward fires).
Uses the FROZEN v2 module (frontside_metrics.py). Population: first reclaim_shadow_fire per
(name, day). Verdict rules unchanged: an arm wins if mean>0 at n>=8 on the forward window."""
import sys, json, urllib.request, datetime
import harness, frontside_metrics as FM
DAYS = sys.argv[1:] or ["2026-08-04","2026-08-05","2026-08-06","2026-08-07"]
rows=[]
for d in DAYS:
    rr=json.load(urllib.request.urlopen(f"{harness.U}/api/decisions_archive?date={d}&limit=50000",timeout=60)).get("rows") or []
    seen=set()
    for r in rr:
        if r.get("status")!="reclaim_shadow_fire": continue
        tk=r.get("ticker")
        if tk in seen: continue
        seen.add(tk)
        e,s,hm=r.get("price"),r.get("stop"),(r.get("time_hm") or "")[:5]
        if not (e and s and e>s and hm): continue
        b=harness.bars(tk,d)
        v=FM.arm_verdicts(b,hm)
        rep=harness.replay(tk,d,e,s,entry_hm=hm+":00")
        if rep and rep.get("shares"):
            rows.append({"d":d,"tk":tk,"pnl":rep["pnl"],**{k:v[k] for k in ("A","B","C")}})
print(f"forward fires priced: {len(rows)}")
for arm in ("A","B","C"):
    g=[r for r in rows if r[arm]]
    n=len(g);p=sum(x["pnl"] for x in g)
    print(f"  ARM {arm}: n={n:>3} ${p:>9.2f} mean ${p/n if n else 0:>7.2f} "
          f"-> {'WINS' if (n>=8 and p>0) else ('n<8' if n<8 else 'negative')}")
u=[r for r in rows]
print(f"  ungated: n={len(u)} ${sum(x['pnl'] for x in u):.2f}")
