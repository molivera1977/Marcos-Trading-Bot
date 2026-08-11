"""SEAM REPLAY, WEEK 8/3-8/6, 10s RESOLUTION (lower bound — true seams are 5s-native; 5s data
begins 8/7). Same frozen rules as ride_seams_5s: up-phase (>3-min mean), FRONT SIDE (>=90% of
session high so far), pullback >=1.5% peak->trough in trailing 2 min, enter the 10s bar closing
back above the pullback high, stop=trough, half at +1R, 6-bar 10s-low trail, $1k clips, RTH,
one position per name at a time. Universe per day: every ticker in that day's decisions with a
leader_armed / triggered_* / *_reject row (the movers the system actually engaged)."""
import json,urllib.request,urllib.parse
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u,timeout=60))
def bars10(tk,d):
    try: r=get(f"{U}/api/bars?date={d}&ticker={urllib.parse.quote(tk)}~ALP10S").get("bars") or []
    except Exception: return []
    out=[]
    for x in r:
        try:
            ts=str(x.get("time"))[11:19]
            sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
            out.append((sec,float(x["high"]),float(x["low"]),float(x["close"])))
        except Exception: continue
    return out
def sim(B,i,e,stop):
    r1=e-stop;pnl=0.0;rem=1.0;sc=False;lows=[]
    for j in range(i,len(B)):
        s,h,l,c=B[j]
        if not sc and h>=e+r1: pnl+=0.5*r1;rem=0.5;sc=True;stop=e
        if sc:
            lows.append(l)
            if len(lows)>6: lows.pop(0)
            if len(lows)==6: stop=max(stop,min(lows))
        if l<=stop: return pnl+rem*(max(stop,l)-e), j
    return pnl+rem*(B[-1][3]-e), len(B)-1
gtot=0.0;gn=0;gw=0
for d in ("2026-08-03","2026-08-04","2026-08-05","2026-08-06"):
    rows=get(f"{U}/api/decisions_archive?date={d}")
    rows=rows.get('decisions') or rows.get('rows') or rows
    tks={r['ticker'] for r in rows if r.get('ticker') and r['ticker']!='_BOOT'
         and (str(r.get('status','')).startswith('triggered') or r.get('status')=='leader_armed'
              or str(r.get('status','')).endswith('_reject'))}
    dtot=0.0;dn=0;dw=0
    for tk in tks:
        B=bars10(tk,d)
        if len(B)<60: continue
        j_busy=-1;sess_hi=0
        for i in range(40,len(B)):
            sess_hi=max(sess_hi,B[i][1])
            if i<=j_busy: continue
            s=B[i][0]
            if not (13*3600+30*60<=s<=20*3600): continue
            if B[i][3]<sess_hi*0.90: continue
            w3=[b for b in B[:i] if b[0]>=s-180]
            if len(w3)<10: continue
            if B[i][3]<=sum(b[3] for b in w3)/len(w3): continue
            w2=[b for b in B[:i] if b[0]>=s-120]
            peak=max(b[1] for b in w2);trough=min(b[2] for b in w2 if b[2]>0)
            if peak<=0 or (peak-trough)/peak*100<1.5: continue
            pb=[b for b in w2 if b[2]<=trough*1.002]
            if not pb: continue
            pb_hi=max(b[1] for b in pb)
            if B[i][3]>pb_hi and B[i-1][3]<=pb_hi:
                e=B[i][3];stop=trough
                if e-stop<=0 or (e-stop)/e<0.005: continue
                sh=int(1000//e)
                if not sh: continue
                pnl,jend=sim(B,i+1,e,stop)
                dtot+=pnl*sh;dn+=1;dw+=(1 if pnl>0 else 0);j_busy=jend
    print(f"{d}: {dn} seams  ${dtot:+8.2f}  winners {dw}/{dn}")
    gtot+=dtot;gn+=dn;gw+=dw
print(f"WEEK (10s lower-bound): {gn} seams  ${gtot:+.2f}  winners {gw}/{gn} ({100*gw/max(gn,1):.0f}%)")
