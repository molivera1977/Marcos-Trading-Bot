#!/usr/bin/env python3
"""
MA_PULLBACK AT REAL COSTS — paying the harness debt (8/21 ~03:3x, Marcos: "finish any harness
issues too")

WHY: ma_pullback holds seats in all three rosters shipped tonight (PRE #2, OPEN #6, MID #6)
with NO real-cost score — the one lane the block competition could not replay (its two-timeframe
driver is not a harness LANES entry). This closes that: the 8/19 driver (selftest MANDATORY,
reproduces the two known live fires CDTG/PFSA 8/18 on the exact confirmation candle) swept over
the full 10s cache, fires walked by the SAME machinery as block_competition_real_20260821 —
real fire-minute NBBO spreads, E3 exits, 1% floor, k=1 guard, $30 risk, capital-aware books.

DISCLOSED LIMITS (the driver's own, restated): detector-only — no PULLBACK_FIRST, no vwap>0
gate, no chart/day-gain/momentum funnel, so fire counts EXCEED what the bot takes (same caveat
every proxy in the competition carried). No warm-up seed: needs >=25 completed 3-min bars, so
PRE fires only exist from ~08:15 and the PRE row here UNDERCOUNTS the live lane's morning.
PRE-REGISTERED: same bar as the field — a block's number is comparable iff both halves agree in
sign; the paper scores it must reconcile against are OPEN +$21.87/fill and MID +$15.30/fill
(Addendum 15). Nothing ships from this file.
"""
import collections, datetime as dt, importlib.util, json, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
sp=importlib.util.spec_from_file_location("D",os.path.join(HERE,"ma_pullback_driver.py"))
D=importlib.util.module_from_spec(sp); sp.loader.exec_module(D)
sq=importlib.util.spec_from_file_location("HF",os.path.join(HERE,"halt_arm_feed_20260820.py"))
HF=importlib.util.module_from_spec(sq); sq.loader.exec_module(HF)
BARS=os.path.join(HERE,"..","universe","bars10s")
RISK=30.0; BOOKS=(3000.0,5000.0); MIN_STOP_PCT=1.0; SPREAD_K=1.0
D.selftest(verbose=False)
print("selftest OK (mandated)")

def et_hm(t): return (dt.datetime.fromisoformat(str(t)[:19])-dt.timedelta(hours=4)).strftime("%H:%M")

def walk(b,i0,entry,stop,pre,spr):
    px=entry+(spr/2 if spr else entry*0.005); rps=px-stop
    if rps<=0: return None
    sh=max(1,min(int(RISK/rps),int(max(BOOKS)*0.70/px),int(1000/px)))
    rem,banked,tiered,runhi=sh,0.0,False,px
    half=(spr/2 if spr else px*0.0025); flat="09:25" if pre else "15:45"
    for i in range(i0+1,len(b)):
        x=b[i]; t=et_hm(x["t"])
        if t>=flat: return banked+rem*((x["c"]-half)-px),sh*px,i
        if x["l"]<=stop: return banked+rem*((stop-half)-px),sh*px,i
        runhi=max(runhi,x["h"])
        if not tiered and x["h"]>=px*1.10:
            n=rem//2 or rem; banked+=n*(px*1.10-px); rem-=n; tiered,stop=True,px
            if rem==0: return banked,sh*px,i
        if tiered and x["c"]<=runhi*0.90:
            return banked+rem*((x["c"]-half)-px),sh*px,i
    return banked+rem*((b[-1]["c"]-half)-px),sh*px,len(b)-1

days=sorted({(f[:10],f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
fills=[]
for n_,(d,sym) in enumerate(days,1):
    raw=json.load(open(os.path.join(BARS,f"{d}_{sym}.json")))
    raw=raw.get("bars",raw) if isinstance(raw,dict) else raw
    if len(raw)<150: continue
    if n_%150==0: print(f"  [{n_}/{len(days)}]",flush=True)
    try: fs=D.fires(sym,d,bars=raw,open_hms="07:00:00",close_hms="15:30:00")
    except Exception: continue
    b=[{"t":x["time"],"h":float(x["high"]),"l":float(x["low"]),"c":float(x["close"])} for x in raw]
    for f in fs:
        i=f["i"]; e=float(f["price"]); s_=float(f.get("stop") or 0)
        if not s_ or e<=s_: continue
        t=et_hm(b[i]["t"])
        if "07:00"<=t<="09:20": blk,pre="PRE",True
        elif "09:30"<=t<"10:30": blk,pre="OPEN",False
        elif "10:30"<=t<"15:30": blk,pre="MID",False
        else: continue
        if (e-s_)/e*100<MIN_STOP_PCT: continue
        spr=HF.spread_at(sym,d,t)
        if SPREAD_K>0 and spr and (e-s_)<SPREAD_K*spr: continue
        r=walk(b,i,e,s_,pre,spr)
        if r is None: continue
        fills.append({"blk":blk,"d":d,"pnl":r[0],"n":r[1],
                      "ti":dt.datetime.fromisoformat(str(b[i]["t"])[:19]).timestamp(),
                      "tx":dt.datetime.fromisoformat(str(b[r[2]]["t"])[:19]).timestamp()})
print(f"\nfills {len(fills)} | quotes {HF._qgap[1]} gaps {HF._qgap[0]}")
def book(fl,bal):
    byday=collections.defaultdict(list)
    for f in fl: byday[f["d"]].append(f)
    tot=n=0
    for d,l in byday.items():
        op=[]
        for f in sorted(l,key=lambda x:x["ti"]):
            op=[o for o in op if o[0]>f["ti"]]
            if f["n"]>bal-sum(o[1] for o in op): continue
            op.append((f["tx"],f["n"])); tot+=f["pnl"]; n+=1
    return tot,n
PAPER={"OPEN":21.87,"MID":15.30,"PRE":None}
print(f"{'block':>6s} {'n':>5s} {'$5,000':>10s} {'$3,000':>10s} {'$/fill':>8s} {'TRAIN':>9s} {'OOS':>9s} {'w/o best':>9s} {'paper':>7s}")
for blk in ("PRE","OPEN","MID"):
    fl=[f for f in fills if f["blk"]==blk]
    if not fl: print(f"{blk:>6s}     0"); continue
    t5,n5=book(fl,5000.0); t3,_=book(fl,3000.0)
    tr_=sum(f["pnl"] for f in fl if int(f["d"][-2:])%2==0)
    oo=sum(f["pnl"] for f in fl if int(f["d"][-2:])%2==1)
    p=sorted((f["pnl"] for f in fl),reverse=True)
    pf=PAPER[blk]
    print(f"{blk:>6s} {n5:5d} {t5:+10.2f} {t3:+10.2f} {(t5/n5 if n5 else 0):+8.2f} {tr_:+9.2f} {oo:+9.2f} {t5-(p[0] if p else 0):+9.2f} {(f'{pf:+7.2f}' if pf else '      -')}")
json.dump(fills,open(os.path.join(HERE,"mapb_realcost_20260821_out.json"),"w"),default=str)
print("\nPRE-REGISTERED: comparable iff both halves agree in sign; reconciles against paper")
print("OPEN +21.87 / MID +15.30. Detector-only proxy, no live funnel. Nothing ships here.")
