"""VWAP-SIDE SIZING KILL-TEST (8/8, Marcos: "kill test this now"; rules FROZEN before run).
ARMS (P&L linear in shares -> scaling is exact for identical entries/exits):
  A = actual (full size everywhere)                 B = HALF size ABOVE VWAP (the candidate)
  C = half size BELOW (inverse control: must lose)  D = QUARTER above (dose response)
SHIP-CANDIDATE iff: B-A >= +$300 era-wide AND B>=A in BOTH era halves AND C<A AND no calendar
week where B trails A by >$100. Side from stored ~ALPVWAP at entry (146/146 coverage, 8/8)."""
import json,urllib.request,urllib.parse,datetime,collections
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u,timeout=60))
_vc={}
def vwap_at(tk,d,es):
    key=(tk,d)
    if key not in _vc:
        try: _vc[key]=get(f"{U}/api/bars?date={d}&ticker={urllib.parse.quote(tk)}~ALPVWAP").get("bars") or []
        except Exception: _vc[key]=[]
    v=0
    for x in _vc[key]:
        ts=str(x.get("time"))[11:19]
        sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
        if sec<=es:
            try: v=float(x.get("close") or 0)
            except Exception: pass
    return v
t=[x for x in get(U+"/api/trades")["trades"]
   if str(x.get("date") or "")>="2026-07-14" and x.get("entry_ts_utc") and x.get("entry_session")!="PRE"]
rows=[]
for x in t:
    e=float(x.get("entry") or 0); a=float(x.get("pnl") or 0)
    if not e: continue
    dt=datetime.datetime.fromisoformat(str(x["entry_ts_utc"]).replace("Z","+00:00"))
    es=dt.hour*3600+dt.minute*60+dt.second
    vw=vwap_at(x["ticker"],x["date"],es)
    if vw<=0: continue
    rows.append((x["date"],"below" if e<vw else "above",a))
A=sum(a for _,_,a in rows)
B=sum(a*(0.5 if s=="above" else 1.0) for _,s,a in rows)
C=sum(a*(0.5 if s=="below" else 1.0) for _,s,a in rows)
D=sum(a*(0.25 if s=="above" else 1.0) for _,s,a in rows)
print(f"n={len(rows)}  A(actual) ${A:+.2f}   B(half-above) ${B:+.2f}   C(inverse) ${C:+.2f}   D(quarter-above) ${D:+.2f}")
mid="2026-07-28"
for tag,cond in (("era-1st-half",lambda d:d<mid),("era-2nd-half",lambda d:d>=mid)):
    a1=sum(a for d,_,a in rows if cond(d)); b1=sum(a*(0.5 if s=="above" else 1) for d,s,a in rows if cond(d))
    print(f"  {tag}: A ${a1:+.2f}  B ${b1:+.2f}  {'B>=A' if b1>=a1 else 'B<A ✗'}")
wk=collections.defaultdict(lambda:[0,0])
for d,s,a in rows:
    w=datetime.date.fromisoformat(d).isocalendar()[1]
    wk[w][0]+=a; wk[w][1]+=a*(0.5 if s=="above" else 1)
bad=[(w,round(v[1]-v[0],2)) for w,v in wk.items() if v[1]-v[0]<-100]
print("  weekly B-A:", {w:round(v[1]-v[0],1) for w,v in sorted(wk.items())}, " fails:",bad)
ok = (B-A)>=300 and C<A and not bad and all(
     sum(a*(0.5 if s=="above" else 1) for d,s,a in rows if c(d))>=sum(a for d,_,a in rows if c(d))
     for c in (lambda d:d<mid, lambda d:d>=mid))
print("VERDICT:", "SHIP-CANDIDATE (half-size above VWAP)" if ok else "NOT MET — evidence only")
