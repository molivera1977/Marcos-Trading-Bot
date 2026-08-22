#!/usr/bin/env python3
"""
IGNITION Q2 + Q3 — the two DETECTOR-LEVEL improvements from the external critique (8/21 night)

WHY A SEPARATE RUNNER: Q4/Q5 were exit- and threshold-level and ride the main competition's
fills. Q2 and Q3 change what the DETECTOR fires on, so they need their own replay of the
ignition machine against the same cache.

Q2 — THE EMA STACK IS AN ORDERING TEST, NOT A DISTANCE TEST.
Live gate (marcos_trading_bot.py:11371): refuse iff ema9 < ema20, ZERO tolerance — one live
specimen was refused by $0.0068 while its sibling VWAP arm carries a 2% band. The external
AI's point: a percent tolerance on an ORDERING boundary is a category error; the principled
form of grace is PERSISTENCE — the stack counts as established if 9>20 held on N of the last M
evaluations, so a flat tape crossing by a hair does not veto a regime that has been intact.
ARMS: strict (live) · N/M persistence in {2/3, 3/5, 4/5, 2/5} · off (no stack gate at all,
the upper bound on what the gate costs).

Q3 — PREMARKET IGNITION: STRICTER BAR, OR JUST THE 09:00-09:20 TAIL?
Live premarket fires 07:00-09:20 and grades +$3.09/fill (v1, curated) — a third of OPEN's rate.
Its two cheap upgrades: (a) require a STRONGER surge in thin tape — vol multiple 2.0x -> 2.5x /
3.0x / 3.5x; (b) check whether the block's money concentrates in 09:00-09:20, i.e. premarket
ignition is really just "OPEN, early". Both are reported as cuts of the same replay.

METHOD: the bot's OWN ignition_10s_step over the ferried full-universe cache (19 days,
7/28-8/21 — the honest universe; curated days are excluded, not averaged in). Real fire-minute
NBBO spreads, 1% floor, k=1 guard, walker with the gap-through-stop correction, $30 risk,
$5,000 shared book. EMA9/EMA20 are recomputed from the same 10s bars the detector reads, so the
persistence arms are evaluated on exactly the series the live gate would have seen.

PRE-REGISTERED
  Q2A A persistence arm replaces strict iff it beats strict in TOTAL DOLLARS on BOTH halves AND
      survives drop-best. "off" is reported as the ceiling — if off <= strict, the gate is
      earning its keep and no grace is warranted at any N/M.
  Q2B The arms must be broadly monotone in permissiveness; a lone winning cell between two
      losers is a lucky slice, not a rule.
  Q3A The vol-multiple ladder must be monotone toward its winner on both halves.
  Q3B If 09:00-09:20 carries >=70% of premarket dollars, the finding is "restrict the window",
      not "raise the bar" — and both are reported, never merged.
  Q4  Nothing ships. Detector changes need the NEW LANE CHECKLIST diff + Blast Radius + Marcos.
LIMITS: 19 days, one season; detector density > live (measured 15.6 live OPEN fires/day vs
~168 designed); median-of-minute spreads; premarket spreads are the widest in the book so the
k=1 guard does the most work exactly where Q3 is measured.
"""
import collections, datetime as dt, importlib.util, json, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
BARS=os.path.join(HERE,"..","universe","bars10s")
BOUNDARY="2026-07-28"          # full-universe era only
RISK,BAL=30.0,5000.0
MIN_STOP_PCT,SPREAD_K=1.0,1.0
sp=importlib.util.spec_from_file_location("H",os.path.join(HERE,"live_harness.py"))
H=importlib.util.module_from_spec(sp); sp.loader.exec_module(H)
sq=importlib.util.spec_from_file_location("HF",os.path.join(HERE,"halt_arm_feed_20260820.py"))
HF=importlib.util.module_from_spec(sq); sq.loader.exec_module(HF)
sw=importlib.util.spec_from_file_location("W2",os.path.join(HERE,"walker_v2.py"))
W2=importlib.util.module_from_spec(sw); sw.loader.exec_module(W2)

def et_hm(t): return (dt.datetime.fromisoformat(str(t)[:19])-dt.timedelta(hours=4)).strftime("%H:%M")

def emas(b, span_fast=9, span_slow=20):
    """EMA9/EMA20 over the 10s closes, evaluated at every bar (the series the gate reads)."""
    kf,ks=2/(span_fast+1),2/(span_slow+1)
    e9=e20=None; out=[]
    for x in b:
        c=x["c"]
        e9=c if e9 is None else c*kf+e9*(1-kf)
        e20=c if e20 is None else c*ks+e20*(1-ks)
        out.append((e9,e20))
    return out

def main():
    days=sorted({(f[:10],f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json") and f[:10]>=BOUNDARY})
    print(f"full-universe name-days: {len(days)} across {len({d for d,_ in days})} days",flush=True)
    fires=[]
    for n_,(d,sym) in enumerate(days,1):
        raw=json.load(open(os.path.join(BARS,f"{d}_{sym}.json")))
        raw=raw.get("bars",raw) if isinstance(raw,dict) else raw
        if len(raw)<150: continue
        b=[{"t":x["time"],"o":float(x.get("open") or x["close"]),"h":float(x["high"]),
            "l":float(x["low"]),"c":float(x["close"]),"v":float(x["volume"])} for x in raw]
        E=emas(b)
        try:
            f=H.replay(sym,raw,["ignition10s"],day=d,batch_secs=60,
                       vwap_provider=lambda s,i,bar,l: H.running_vwap(raw,day=d)[i],
                       ctx_provider=lambda s,i,bar,l: {})
        except Exception:
            continue
        if n_%150==0: print(f"  [{n_}/{len(days)}] fires {len(fires)}",flush=True)
        for x in f:
            i=x.get("i"); st=x.get("would_stop") or x.get("stop")
            px=x.get("px") or (b[i]["c"] if i is not None else None)
            if i is None or not st or not px or float(px)<=float(st): continue
            e,s_=float(px),float(st)
            t=et_hm(b[i]["t"])
            if "07:00"<=t<="09:20": blk,pre="PRE",True
            elif "09:30"<=t<"15:30": blk,pre=("OPEN" if t<"10:30" else "MID"),False
            else: continue
            if (e-s_)/e*100<MIN_STOP_PCT: continue
            spr=HF.spread_at(sym,d,t)
            if SPREAD_K>0 and spr and (e-s_)<SPREAD_K*spr: continue
            r=W2.walk(b,i,e,s_,pre,spr,bal=BAL)
            if r is None: continue
            # Q2 inputs: stack state now and over the last 5 evaluations (1 eval = 6 bars = 60s)
            hist=[]
            for k in range(5):
                j=i-6*k
                if j>=0: hist.append(E[j][0]>E[j][1])
            # Q3 input: the fire bar's volume multiple over its 4-min base (the detector's own ref)
            base=[y["v"] for y in b[max(0,i-24):i]]
            volx=(b[i]["v"]/(sum(base)/len(base))) if base and sum(base)>0 else None
            fires.append({"d":d,"sym":sym,"t":t,"blk":blk,"pnl":r[0],"n":r[1],
                          "stack_now":bool(hist[0]) if hist else None,
                          "stack_hist":hist,"volx":volx,
                          "ti":dt.datetime.fromisoformat(str(b[i]["t"])[:19]).timestamp(),
                          "tx":dt.datetime.fromisoformat(str(b[r[2]]["t"])[:19]).timestamp()})
    print(f"\nignition fires graded: {len(fires)} | quotes {HF._qgap[1]} gaps {HF._qgap[0]}",flush=True)
    json.dump(fires,open(os.path.join(HERE,"ignition_q2q3_20260821_out.json"),"w"),default=str)

    def book(fl):
        byd=collections.defaultdict(list)
        for f in fl: byd[f["d"]].append(f)
        out=[]
        for d,l in byd.items():
            op=[]
            for f in sorted(l,key=lambda x:x["ti"]):
                op=[o for o in op if o[0]>f["ti"]]
                if f["n"]>BAL-sum(o[1] for o in op): continue
                op.append((f["tx"],f["n"])); out.append(f)
        return out
    def st(fl):
        if not fl: return None
        t=sum(f["pnl"] for f in fl); tr=sum(f["pnl"] for f in fl if int(f["d"][-2:])%2==0)
        p=sorted((f["pnl"] for f in fl),reverse=True)
        return dict(n=len(fl),tot=t,per=t/len(fl),tr=tr,oo=t-tr,wo=t-p[0],
                    win=100*sum(1 for x in p if x>0)/len(p))
    HDR=f"{'arm':>26s} {'n':>5s} {'total$':>11s} {'$/fill':>8s} {'TRAIN':>10s} {'OOS':>10s} {'w/o best':>10s} {'win%':>5s}"
    def line(lab,fl):
        s=st(fl)
        if not s: print(f"{lab:>26s}     0 (none)"); return
        print(f"{lab:>26s} {s['n']:5d} {s['tot']:+11.2f} {s['per']:+8.2f} {s['tr']:+10.2f} {s['oo']:+10.2f} {s['wo']:+10.2f} {s['win']:4.0f}%")

    def passes(f,mode):
        h=f["stack_hist"] or []
        if not h: return True                      # unevaluable fails OPEN, as live
        if mode=="strict": return h[0]
        if mode=="off": return True
        n,m=mode
        return sum(1 for x in h[:m] if x)>=n
    print("\n=== Q2: EMA STACK — strict vs PERSISTENCE vs off (RTH fires) ===")
    print(HDR)
    rth=[f for f in fires if f["blk"] in ("OPEN","MID")]
    for lab,mode in (("strict (live)","strict"),("persist 2/3",(2,3)),("persist 3/5",(3,5)),
                     ("persist 4/5",(4,5)),("persist 2/5",(2,5)),("off (ceiling)","off")):
        line(lab,book([f for f in rth if passes(f,mode)]))
    print("\n   OPEN-only view")
    print(HDR)
    opn=[f for f in fires if f["blk"]=="OPEN"]
    for lab,mode in (("strict (live)","strict"),("persist 3/5",(3,5)),("off (ceiling)","off")):
        line(lab,book([f for f in opn if passes(f,mode)]))

    print("\n=== Q3a: PREMARKET vol-multiple ladder ===")
    print(HDR)
    pre=[f for f in fires if f["blk"]=="PRE"]
    for mult in (2.0,2.5,3.0,3.5):
        line(f"PRE volx >= {mult}",book([f for f in pre if (f["volx"] or 0)>=mult]))
    print("\n=== Q3b: does 09:00-09:20 carry premarket? ===")
    print(HDR)
    tk=book(pre); tot=sum(f["pnl"] for f in tk) or 1
    late=[f for f in tk if f["t"]>="09:00"]
    line("PRE 07:00-08:59",[f for f in tk if f["t"]<"09:00"])
    line("PRE 09:00-09:20",late)
    print(f"   09:00-09:20 share of premarket dollars: {100*sum(f['pnl'] for f in late)/tot:.0f}%"
          f"  (>=70% => 'restrict the window', per Q3B)")
    print("\nPRE-REGISTERED: Q2A persistence replaces strict only on BOTH halves + drop-best;")
    print("'off' is the ceiling. Q2B/Q3A monotone or it's a lucky slice. Q3B >=70% late share =>")
    print("restrict the window, not raise the bar. Q4 nothing ships.")
    return 0

if __name__=="__main__": sys.exit(main())
