"""#73 kill-test: ORB pullback anchor — STATIC (current: wait for revisit of OR-high) vs
TRAILING (after OR-break, pullback to rising 1m 20-EMA + curl; stop = pullback low).
Order-dependent; kev25-ish exits in R (50%@+1R, 25%@+2R, runner 3-bar-low trail).
All 156 cached name-days; faders included (the trailing anchor must NOT buy every fader's pause)."""
import json, os, hashlib, urllib.parse, statistics as st
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u):
    k="mcache/"+hashlib.md5(u.encode()).hexdigest()+".json"
    return json.load(open(k)) if os.path.exists(k) else {}
def roster(d):
    names=set(get(f"{U}/api/watching?date={d}").get("tickers") or [])
    for r in (get(f"{U}/api/decisions_archive?date={d}&limit=12000").get("rows") or []): names.add((r.get("ticker") or "").upper())
    return sorted(n for n in names if n and n!="N/A")
def rth(t,d):
    b=[x for x in (get(f"{U}/api/minute_ext?ticker={urllib.parse.quote(t)}&count=1200").get("bars") or []) if str(x.get("time","")).startswith(d) and x.get("session")=="RTH"]
    b.sort(key=lambda x:str(x["time"])); return b
def kev25(entry, stop, c,h,l, s):
    risk=entry-stop
    if risk<=0: return None
    r1,r2=entry+risk,entry+2*risk; f1=f2=False; R=0.0; lows=[]
    for j in range(s,len(c)):
        if not f1 and l[j]<=stop: return -1.0
        if not f1 and h[j]>=r1: f1=True; R+=0.5
        if f1 and not f2 and h[j]>=r2: f2=True; R+=0.5
        if f1:
            fl=max(stop, entry if f2 else stop, *(lows[-3:] or [stop]))
            if l[j]<=fl:
                rem=0.25 if f2 else 0.5
                return R+rem*(fl-entry)/risk
        lows.append(l[j])
    rem=0.25 if f2 else (0.5 if f1 else 1.0)
    return R+rem*(c[-1]-entry)/risk
A=[];B=[];  # A static, B trailing; rows (name,day,move%,R)
for d in ["2026-07-20","2026-07-21"]:
    for t in roster(d):
        b=rth(t,d)
        if len(b)<25: continue
        c=[float(x["close"]) for x in b]; h=[float(x["high"]) for x in b]; l=[float(x["low"]) for x in b]
        tm=[str(x["time"])[11:16] for x in b]
        orb=[h[i] for i in range(len(b)) if "13:30"<=tm[i]<="13:35"]
        if not orb: continue
        orh=max(orb); o=c[0]; move=(max(h)-o)/o*100
        bi=next((i for i in range(len(b)) if tm[i]>"13:35" and c[i]>orh), None)
        if bi is None: continue
        ema=[]; e=c[0]
        for x in c: e=x*(2/21)+e*(1-2/21); ema.append(e)
        # A STATIC: pullback low touches OR-high, then curl (close>prior high) — the current machine's intent
        ei=None; touched=False; plow=c[bi]
        for j in range(bi+1,len(c)):
            plow=min(plow,l[j])
            if l[j]<=orh: touched=True
            if touched and c[j]>h[j-1]: ei=j; break
        if ei is not None:
            r=kev25(c[ei], min(plow,orh*0.995), c,h,l, ei+1)
            if r is not None: A.append((t,d,move,r))
        # B TRAILING: pullback low touches the rising 20-EMA, then curl; stop = pullback low
        ei=None; touched=False; plow=c[bi]
        for j in range(bi+1,len(c)):
            plow=min(plow,l[j])
            if l[j]<=ema[j]: touched=True
            if touched and c[j]>h[j-1]: ei=j; break
        if ei is not None:
            r=kev25(c[ei], plow, c,h,l, ei+1)
            if r is not None: B.append((t,d,move,r))
def rep(name,X):
    if not X: print(f"{name}: none"); return
    rs=[r for *_,r in X]
    movers=[(t,d,m,r) for t,d,m,r in X if m>=40]
    print(f"{name}: n={len(rs)}  meanR {sum(rs)/len(rs):+.2f}  medianR {st.median(rs):+.2f}  win% {100*sum(1 for r in rs if r>0)/len(rs):.0f}")
    print(f"   movers>=40%: n={len(movers)} meanR {sum(r for *_,r in movers)/len(movers):+.2f}" if movers else "   movers>=40%: none entered")
    for t,d,m,r in sorted(movers,key=lambda x:-x[2])[:6]: print(f"     {t}@{d[5:]} move {m:.0f}%  R {r:+.2f}")
rep("A STATIC (current)", A)
rep("B TRAILING (20-EMA)", B)
gmA=[r for t,d,m,r in A if t=="GMM"]; gmB=[r for t,d,m,r in B if t=="GMM"]
print(f"\nGMM check — static: {gmA or 'NO ENTRY (the bug)'} | trailing: {gmB or 'no entry'}")
fadeB=[r for t,d,m,r in B if m<=15]; fadeA=[r for t,d,m,r in A if m<=15]
print(f"fader safety — static: n={len(fadeA)} meanR {sum(fadeA)/len(fadeA):+.2f}" if fadeA else "fader safety — static: none")
print(f"fader safety — trailing: n={len(fadeB)} meanR {sum(fadeB)/len(fadeB):+.2f}" if fadeB else "fader safety — trailing: none")
