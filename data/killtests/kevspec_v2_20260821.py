#!/usr/bin/env python3
"""
KEVSPEC v2 — the external AI's reclaim design, THE FULL VERIFICATION LADDER (8/21 night)

THE CANDIDATE (external AI, 8/21 early AM, ported byte-faithfully in reclaim_kevspec_20260821):
dip >=0.5% below VWAP with >=2 of last 10 bars below · reclaim close > VWAP*1.001 · vol >=1.5x
20-bar mean · stop = max($0.15, 2% x price) from the close · k=1 spread guard · bank half at
+1.5R (stop->entry), rest at +2.5R · one trade per reclaim (re-arm on a close below VWAP).
FIRST WALK: PRE +$9,929.42 / OPEN +$12,293.12 (both halves, drop-best intact), MID failed K1.

WHY IT MUST BE RE-RUN, not just extended (the 8/21 night findings):
  * THE UNIVERSE. The first walk's cache was ~84% CURATED days (top-12 movers/day, selected by
    ">=40% intraday gain"). Our own reclaim died on exactly this gap (+$9.86/fill on cache names,
    -$11.27 on live-only names, 3:1 junk ratio). The ferries have since rebuilt 8/11-8/21 (and
    are extending to 7/28) with the FULL watched universe. Verdicts here lead with the
    FULL-UNIVERSE days; curated days are reported as the labelled upper bound.
  * THE WALKER. First walk assumed stop fills at the stop. walker-v2's gap-through-stop rule
    (fill = min(stop, bar open)) is applied to this spec's engine too.
  * TOUCH SENSITIVITY (the external AI's own #1 concern): T1/T2 are resting limits assumed
    filled on a touch. STRICT arm requires the bar's HIGH to EXCEED the limit by one spread
    (a touch-only bar = no fill). Both reported.
  * CAPACITY (its #2): the first walk took 83 trades/day. Live takes ~a dozen across ALL lanes.
    Top-N/day re-book at N in {2,4,6}, ranked by earliest fire time (no look-ahead ranking).
  * DEAD-TAPE CUT (Marcos: "september can't be any more dead than this month"): per-day P&L +
    a hot/dead split — a day is DEAD iff its cache universe contains <3 names whose day high
    >=50% over the day's first bar (computable from bars alone, no records).

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  K1 The spec keeps its candidacy iff PRE or OPEN stays positive at $5,000, BOTH halves,
     drop-best, ON THE FULL-UNIVERSE DAYS, in the top-6/day re-book, under STRICT fills.
  K2 If it fails full-universe while passing curated, the verdict is "needs a mover gate"
     (the same wall our reclaim hit), not "dead" — but candidacy pauses either way.
  K3 Dead-day behaviour is reported; a spec negative on dead days is sized-down, not killed.
  K4 Nothing ships. NEW LANE CHECKLIST + Blast Radius + Marcos's word stand between any pass
     and a live seat.
"""
import collections, datetime as dt, importlib.util, json, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
BARS=os.path.join(HERE,"..","universe","bars10s")
RISK,BAL=30.0,5000.0
sp=importlib.util.spec_from_file_location("H",os.path.join(HERE,"live_harness.py"))
H=importlib.util.module_from_spec(sp); sp.loader.exec_module(H)
sq=importlib.util.spec_from_file_location("HF",os.path.join(HERE,"halt_arm_feed_20260820.py"))
HF=importlib.util.module_from_spec(sq); sq.loader.exec_module(HF)
sk=importlib.util.spec_from_file_location("K",os.path.join(HERE,"reclaim_kevspec_20260821.py"))
K=importlib.util.module_from_spec(sk); sk.loader.exec_module(K)   # detect() reused verbatim

CURATED_MAX=20   # a day with <=20 files is a curated (top-12-ish) day; ferried days have 100+

def walk(b,i0,entry,stop_dist,pre,spr,strict):
    px=entry+(spr/2 if spr else entry*0.005)
    stop=entry-stop_dist
    rps=px-stop
    if rps<=0: return None
    sh=max(1,min(int(RISK/stop_dist),int(BAL*0.70/px),int(1000/px)))
    t1,t2=px+1.5*rps,px+2.5*rps
    half=(spr/2 if spr else px*0.0025)
    tickup=(spr if spr else px*0.005) if strict else 0.0
    rem,banked,t1done=sh,0.0,False
    flat="09:25" if pre else "15:45"
    for i in range(i0+1,len(b)):
        x=b[i]; t=K.et_hm(x["t"])
        if t>=flat: return banked+rem*((x["c"]-half)-px),sh*px,i
        if x["l"]<=stop:
            o=float(x.get("o") or x["c"])
            fill=min(stop,o)                          # walker-v2 gap rule
            return banked+rem*((fill-half)-px),sh*px,i
        if not t1done and x["h"]>=t1+tickup:
            n=rem//2 or rem; banked+=n*(t1-px); rem-=n; t1done,stop=True,px
            if rem==0: return banked,sh*px,i
        if t1done and x["h"]>=t2+tickup:
            return banked+rem*(t2-px),sh*px,i
    return banked+rem*((b[-1]["c"]-half)-px),sh*px,len(b)-1

def main():
    files=sorted(f for f in os.listdir(BARS) if f.endswith(".json"))
    byday=collections.Counter(f[:10] for f in files)
    FULL={d for d,n in byday.items() if n>CURATED_MAX}
    print(f"days {len(byday)} | FULL-UNIVERSE days {len(FULL)}: {sorted(FULL)}",flush=True)
    fires=[]; hotness={}
    for n_,f in enumerate(files,1):
        d,sym=f[:10],f[11:-5]
        raw=json.load(open(os.path.join(BARS,f))); raw=raw.get("bars",raw) if isinstance(raw,dict) else raw
        if len(raw)<150: continue
        b=[{"t":x["time"],"o":float(x.get("open") or x["close"]),"h":float(x["high"]),
            "l":float(x["low"]),"c":float(x["close"]),"v":float(x["volume"])} for x in raw]
        # hot/dead ingredient: did this name run >=50% off its first bar?
        f0=b[0]["o"] or b[0]["c"]
        if f0>0: hotness.setdefault(d,0); hotness[d]+= (1 if max(x["h"] for x in b)/f0>=1.5 else 0)
        try: vw=H.running_vwap(raw,day=d)
        except Exception: continue
        if n_%200==0: print(f"  [{n_}/{len(files)}] fires {len(fires)}",flush=True)
        for i,e,sd in K.detect(b,vw):
            t=K.et_hm(b[i]["t"])
            if "07:00"<=t<="09:20": blk,pre="PRE",True
            elif "09:30"<=t<"10:30": blk,pre="OPEN",False
            elif "10:30"<=t<"15:30": blk,pre="MID",False
            else: continue
            spr=HF.spread_at(sym,d,t)
            if spr and sd<spr: continue               # the spec's own k=1 guard
            row={"d":d,"sym":sym,"t":t,"blk":blk,"full":d in FULL,
                 "ti":dt.datetime.fromisoformat(str(b[i]["t"])[:19]).timestamp()}
            for lab,strict in (("pnl",False),("pnl_strict",True)):
                r=walk(b,i,e,sd,pre,spr,strict)
                if r: row[lab]=r[0]; row["n"]=r[1]; row["tx"]=dt.datetime.fromisoformat(str(b[r[2]]["t"])[:19]).timestamp()
            if "pnl" in row: fires.append(row)
    print(f"\nfires {len(fires)} | quotes {HF._qgap[1]} gaps {HF._qgap[0]}",flush=True)
    json.dump({"fires":fires,"hotness":hotness},open(os.path.join(HERE,"kevspec_v2_20260821_out.json"),"w"),default=str)

    def book(fl,cap=None,key="pnl"):
        byd=collections.defaultdict(list)
        for f in fl:
            if key in f: byd[f["d"]].append(f)
        taken=[]
        for d,l in byd.items():
            l=sorted(l,key=lambda x:x["ti"])
            if cap: l=l[:cap]
            op=[]
            for f in l:
                op=[o for o in op if o[0]>f["ti"]]
                if f["n"]>BAL-sum(o[1] for o in op): continue
                op.append((f["tx"],f["n"])); taken.append(f)
        return taken
    def st(fl,key="pnl"):
        fl=[f for f in fl if key in f]
        if not fl: return None
        t=sum(f[key] for f in fl); tr=sum(f[key] for f in fl if int(f["d"][-2:])%2==0)
        p=sorted((f[key] for f in fl),reverse=True)
        return dict(n=len(fl),tot=t,per=t/len(fl),tr=tr,oo=t-tr,wo=t-p[0],
                    win=100*sum(1 for x in p if x>0)/len(p),days=len({f["d"] for f in fl}))
    def line(lab,fl,key="pnl"):
        s=st(fl,key)
        if not s: print(f"{lab:>30s}    0 (none)"); return
        print(f"{lab:>30s} {s['n']:5d} {s['tot']:+11.2f} {s['per']:+7.2f} {s['tr']:+10.2f} {s['oo']:+10.2f} {s['wo']:+10.2f} {s['win']:4.0f}% ({s['days']}d)")

    HDR=f"{'cut':>30s} {'n':>5s} {'total$':>11s} {'$/fill':>7s} {'TRAIN':>10s} {'OOS':>10s} {'w/o best':>10s} {'win%':>5s}"
    for uni,lab in ((True,"FULL-UNIVERSE DAYS (the verdict cohort)"),(False,"CURATED DAYS (upper bound, labelled)")):
        sub=[f for f in fires if f["full"]==uni]
        print(f"\n==================== {lab} ====================")
        print(HDR)
        for cap,cl in ((None,"uncapped"),(6,"top-6/day"),(4,"top-4/day"),(2,"top-2/day")):
            tk=book(sub,cap)
            for blk in ("PRE","OPEN","MID"):
                line(f"{cl} {blk}",[f for f in tk if f["blk"]==blk])
            if cap==6:
                tk6=tk
                for blk in ("PRE","OPEN"):
                    line(f"top-6 {blk} STRICT",[f for f in book(sub,6,key='pnl_strict') if f['blk']==blk],"pnl_strict")
    # dead/hot cut on full-universe days
    hot={d for d,c in hotness.items() if c>=3}
    subf=[f for f in fires if f["full"]]
    print("\n==================== DEAD vs HOT (full-universe days) ====================")
    print(HDR)
    line("HOT days (>=3 names +50%)",[f for f in book(subf,6) if f["d"] in hot])
    line("DEAD days (<3 names +50%)",[f for f in book(subf,6) if f["d"] not in hot])
    print("\nPRE-REGISTERED: K1 candidacy holds iff PRE or OPEN positive on FULL-UNIVERSE days,")
    print("both halves + drop-best, top-6/day, STRICT fills. K2 curated-only pass = 'needs a")
    print("mover gate', candidacy paused. K3 dead-day negative = size down, not kill. K4 nothing")
    print("ships — NEW LANE CHECKLIST + Blast Radius + Marcos's word before any seat.")
    return 0

if __name__=="__main__": sys.exit(main())
