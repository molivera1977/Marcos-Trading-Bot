"""#18 FIGHTING-THE-TAPE GRADE (frozen rules pre-run): every era RTH trade graded by its VWAP
relationship AT ENTRY, computed from the stored ~ALPVWAP series (not the null-prone record
fields). Cells: above/below VWAP x VWAP slope up/down (slope = vwap now vs 5 min prior).
Question (STAK 09:32 class): do below-VWAP or falling-VWAP entries pay? Dollars per cell."""
import json,urllib.request,urllib.parse,datetime
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u,timeout=60))
def vwap_series(tk,d):
    try: r=get(f"{U}/api/bars?date={d}&ticker={urllib.parse.quote(tk)}~ALPVWAP").get("bars") or []
    except Exception: return []
    out=[]
    for x in r:
        ts=str(x.get("time"))[11:19]
        sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
        try: out.append((sec,float(x.get("close") or x.get("c") or 0)))
        except Exception: continue
    return out
t=[x for x in get(U+"/api/trades")["trades"]
   if str(x.get("date") or "")>="2026-07-14" and x.get("entry_ts_utc") and x.get("entry_session")!="PRE"]
cells={}
n_ok=0
for x in t:
    e=float(x.get("entry") or 0); a=float(x.get("pnl") or 0)
    if not e: continue
    vs=vwap_series(x["ticker"],x["date"])
    if len(vs)<10: continue
    dt=datetime.datetime.fromisoformat(str(x["entry_ts_utc"]).replace("Z","+00:00"))
    es=dt.hour*3600+dt.minute*60+dt.second
    now=[v for s,v in vs if s<=es]
    prev=[v for s,v in vs if s<=es-300]
    if not now or not prev or now[-1]<=0: continue
    vw, vw5 = now[-1], prev[-1]
    side = "above" if e>=vw else "BELOW"
    slope = "rising" if vw>=vw5 else "FALLING"
    k=(side,slope)
    c=cells.setdefault(k,[0,0.0,0])
    c[0]+=1;c[1]+=a;c[2]+=(1 if a>0 else 0)
    n_ok+=1
print(f"graded {n_ok}/{len(t)} era RTH trades (VWAP series coverage)")
for k in sorted(cells):
    c=cells[k]
    print(f"  {k[0]:6s} VWAP, {k[1]:8s}: n={c[0]:3d}  ${c[1]:+9.2f}  win {c[2]}/{c[0]} ({100*c[2]/max(c[0],1):.0f}%)")
