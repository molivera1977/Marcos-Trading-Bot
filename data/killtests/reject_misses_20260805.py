"""REJECT MISS AUDIT 8/5 (Marcos: "any misses?"). Replays every gate reject today at its
reject price with its STAMPED stop through the live-exit engine (half at +1R, stop->BE,
prev-minute-low trail off 10s bars). Sizing = the standard width-band risk convention from
runway_graded_20260804 ($20/<5%, $25/5-6%, $30/>=6%). Ceiling rejects have no stamped stop
-> skipped unless stop present. Repeated rejects of the same ticker+lane are all shown but
only the FIRST would have traded (slot)."""
import json, urllib.request, urllib.parse
U = "https://zestful-intuition-production-b16a.up.railway.app"
D = "2026-08-05"
def get(u): return json.load(urllib.request.urlopen(u, timeout=60))
rows = get(U + f"/api/decisions_archive?date={D}&status=minstop_reject,runway_reject,breakside_reject,ceiling_reject&limit=50000")
rows = rows.get("decisions") or rows.get("rows") or []
_b = {}
def bars10(tk):
    if tk in _b: return _b[tk]
    try:
        r = get(f"{U}/api/bars?date={D}&ticker={urllib.parse.quote(tk)}~ALP10S").get("bars") or []
    except Exception:
        r = []
    out = []
    for x in r:
        try:
            ts = str(x.get("time"))[11:19]
            sec = int(ts[:2])*3600 + int(ts[3:5])*60 + int(ts[6:8])
            out.append((sec, float(x.get("high") or 0), float(x.get("low") or 0), float(x.get("close") or 0)))
        except Exception: continue
    _b[tk] = out
    return out
def sim(bs, i0, e, s):
    pnl=0.0; rem=1.0; sc=False; stop=s; lows=[]
    for j in range(i0, len(bs)):
        _,h,l,c = bs[j]
        if not sc and h >= e + (e-s):
            pnl += 0.5*(e-s); rem=0.5; sc=True; stop=e; continue
        if sc:
            lows.append(l)
            if len(lows) > 6: lows.pop(0)
            if len(lows) == 6: stop = max(stop, min(lows))
        if l <= stop:
            return pnl + rem*(max(stop,l)-e), max((b[1] for b in bs[j:]), default=0)
    return pnl + (rem*(bs[-1][3]-e) if bs else 0), (bs[-1][3] if bs else 0)
out=[]
for r in rows:
    e=float(r.get("price") or 0); s=float(r.get("stop") or 0); tk=r["ticker"]
    if not (e>s>0):
        out.append((r["time"],tk,r["status"],e,None,None,None,"no stamped stop")); continue
    ts=str(r["recorded_at"])[11:19]
    esec=(int(ts[:2])+4)*3600+int(ts[3:5])*60+int(ts[6:8])
    bs=bars10(tk)
    i0=next((j for j,x in enumerate(bs) if x[0]>=esec), None)
    if i0 is None or len(bs)<30:
        out.append((r["time"],tk,r["status"],e,None,None,None,"no 10s bars")); continue
    w=100*(e-s)/e; risk=20 if w<5 else (25 if w<6 else 30); sh=risk/(e-s)
    pnl,hi_after = sim(bs,i0,e,s)
    mfe=100*(max((b[1] for b in bs[i0:]),default=e)/e-1)
    out.append((r["time"],tk,r["status"],e,round(pnl*sh,2),round(mfe,1),int(sh),""))
print(f"{'time':<12}{'tk':<7}{'gate':<18}{'px':>7}{'cf_pnl':>9}{'maxup%':>8}  note")
tot=0
for t,tk,st,e,p,m,sh,note in sorted(out):
    if p is not None: tot+=p
    print(f"{t:<12}{tk:<7}{st:<18}{e:>7.2f}{('%+.2f'%p) if p is not None else '—':>9}{(str(m)) if m is not None else '—':>8}  {note}")
print(f"\nTOTAL (all rows, incl. duplicates that couldn't all have traded): ${tot:+.2f}")
json.dump(out, open(__file__.replace(".py","_rows.json"),"w"), indent=1)
