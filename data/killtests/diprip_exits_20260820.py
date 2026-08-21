#!/usr/bin/env python3
"""
DIP_RIP — IS IT THE LANE OR IS IT THE EXIT? (8/20 night, Marcos: "so is dip-rip a dead lane")

The refusal grade (diprip_refusals_20260820) priced the lane at -$597.93 / 54 trades under E3
and found EVERY gate earning its keep. But one alternative was never tested: E3 is a runner
engine (+10% tier, 10% give-back, 15:45 flat) and dip_rip's thesis is a RESUMPTION POP off a
marked level — a pop is not a runner. A lane can be sound and still lose under the wrong exit.
This sweeps the exit and leaves entry, gates, costs and sizing identical.

Marcos's own words from today, on a different chop-day question: "I'd rather bank a win and
re-enter." This is that hypothesis, applied where it is cheapest to test.

ARMS (same 80 triggers, same tape, same real NBBO spreads, same $30 risk / 1% floor / k=1)
  E3      the house engine (baseline; reproduces the -$597.93)
  POP5    take everything at +5%
  POP8    take everything at +8%
  HALF5   half at +5%, stop to entry, rest on E3's give-back
  T10     time stop: out at the close of 10 minutes, no target
  T20     time stop: 20 minutes
  LVL     stop stays at the level, no tier, ride to 15:45 (pure thesis test)
PRE-REGISTERED: an exit rescues the lane iff it turns the TOTAL POSITIVE at $5,000 AND holds
positive after dropping the single best trade. Anything else = the lane is dead as designed,
not merely mis-exited. Nothing ships from this file.
"""
import collections, datetime as dt, importlib.util, json, os, sys, urllib.request
HERE=os.path.dirname(os.path.abspath(__file__))
sp=importlib.util.spec_from_file_location("HF",os.path.join(HERE,"halt_arm_feed_20260820.py"))
HF=importlib.util.module_from_spec(sp); sp.loader.exec_module(HF)
RISK=30.0; BAL=5000.0; MIN_STOP_PCT=1.0; SPREAD_K=1.0
ROWS=json.load(open(os.path.join(HERE,"diprip_refusals_20260820_out.json")))["rows"]

def walk(b10,k0,entry,stop,spr,arm):
    ks=[x for x in sorted(b10) if x>=k0]
    if len(ks)<2: return None
    half=(spr/2) if spr else entry*0.0025
    px=entry+half; rps=px-stop
    if rps<=0: return None
    sh=max(1,min(int(RISK/rps),int(BAL*0.70/px),int(1000/px)))
    rem,banked,tiered,runhi=sh,0.0,False,px
    t0=ks[0]
    for k in ks[1:]:
        x=b10[k]
        if HF.hm_k(k)>="15:45": return banked+rem*((x["c"]-half)-px), sh*px, k
        if x["l"]<=stop: return banked+rem*((stop-half)-px), sh*px, k
        runhi=max(runhi,x["h"])
        if arm in ("POP5","POP8","HALF5"):
            tgt=1.05 if arm in ("POP5","HALF5") else 1.08
            if not tiered and x["h"]>=px*tgt:
                if arm in ("POP5","POP8"):
                    return banked+rem*(px*tgt-px), sh*px, k
                n=rem//2 or rem; banked+=n*(px*tgt-px); rem-=n; tiered=True; stop=px
                if rem==0: return banked, sh*px, k
        if arm=="E3" and not tiered and x["h"]>=px*1.10:
            n=rem//2 or rem; banked+=n*(px*1.10-px); rem-=n; tiered=True; stop=px
            if rem==0: return banked, sh*px, k
        if arm in ("T10","T20") and k-t0>=(600 if arm=="T10" else 1200):
            return banked+rem*((x["c"]-half)-px), sh*px, k
        if arm in ("E3","HALF5") and tiered and x["c"]<=runhi*0.90:
            return banked+rem*((x["c"]-half)-px), sh*px, k
    lk=ks[-1]; return banked+rem*((b10[lk]["c"]-half)-px), sh*px, lk

live=[r for r in ROWS if r.get("today_ok") and r.get("pnl") is not None]
print(f"cohort: {len(live)} takeable triggers\n")
tape={}
for i,c in enumerate(live,1):
    t0=dt.datetime.fromisoformat(f"{c['d']}T{c['ts']}"); hi=dt.datetime.fromisoformat(f"{c['d']}T15:50:00")
    tr=HF.trades(c["tk"],c["d"],t0.strftime("%H:%M:%S"),hi.strftime("%H:%M:%S"))
    print(f"  [{i}/{len(live)}] {c['d']} {c['tk']} trades={len(tr)}",flush=True)
    if len(tr)>=50: tape[(c["d"],c["tk"],c["ts"])]=HF.bars(tr,10)
ARMS=("E3","POP5","POP8","HALF5","T10","T20","LVL")
print(f"\n{'arm':>6s} {'n':>4s} {'$5,000':>10s} {'$/tr':>8s} {'w/o best':>10s} {'win%':>6s}")
out={}
for arm in ARMS:
    fl=[]
    for c in live:
        b=tape.get((c["d"],c["tk"],c["ts"]))
        if not b: continue
        ks=sorted(b)
        r=walk(b,ks[0],c["px"],c["stop"],c.get("spr"),arm)
        if r: fl.append({"d":c["d"],"pnl":r[0],"n":r[1],"ti":ks[0],"tx":r[2]})
    byday=collections.defaultdict(list)
    for f in fl: byday[f["d"]].append(f)
    tot=n=0
    for d,l in byday.items():
        op=[]
        for f in sorted(l,key=lambda x:x["ti"]):
            op=[o for o in op if o[0]>f["ti"]]
            if f["n"]>BAL-sum(o[1] for o in op): continue
            op.append((f["tx"],f["n"])); tot+=f["pnl"]; n+=1
    p=sorted((f["pnl"] for f in fl),reverse=True)
    w=100*sum(1 for x in p if x>0)/max(len(p),1)
    out[arm]={"n":n,"tot":tot,"wo_best":tot-(p[0] if p else 0),"win":w}
    print(f"{arm:>6s} {n:4d} {tot:+10.2f} {(tot/n if n else 0):+8.2f} {tot-(p[0] if p else 0):+10.2f} {w:5.0f}%")
json.dump(out,open(os.path.join(HERE,"diprip_exits_20260820_out.json"),"w"))
print("\nPRE-REGISTERED: an exit rescues the lane iff TOTAL turns positive AND survives")
print("drop-best. Otherwise the lane is dead as designed, not mis-exited. Nothing ships here.")
