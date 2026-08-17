#!/usr/bin/env python3
"""Counterfactual replay of 2026-08-17 with all 8/17 fixes running from 07:00.
E3 live-parity: $500 clip, +1% entry slip (market lanes), bank 1/2 at +10%, trail 10% off
run-high on CLOSES after scale, intrabar stop FIRST, -0.5% on market exits, EOD flatten.
Tape: SIP 10s bars rebuilt from /v2/stocks/trades (feed=sip), 11:00-20:05Z."""
import json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
B10 = os.path.join(HERE, "bars10s_0817")
POS, SLIP, MKT = 500.0, 0.01, 0.005
SLOTS = 2
MIN_STOP_PCT = 0.04
MIN_STOP_EXEMPT = {"flat_top", "hidden_entry", "zone_flip"}
TAPE_LANES = {"kevseq","v2conv","grinder","bandpass","prevwap","crown_seam","halt_ladder",
              "hidden_entry","vwap_reclaim","zone_flip"}
ENTRY_OPEN = 7*3600           # 07:00 ET
ENTRY_CLOSE = 15*3600+55*60
EOD = 16*3600

_bars = {}
def bars(t):
    if t not in _bars:
        p = os.path.join(B10, t + ".json")
        _bars[t] = json.load(open(p))["bars"] if os.path.exists(p) else []
    return _bars[t]

def bsec(b):   # UTC -> ET seconds (EDT = UTC-4)
    return (int(b["time"][11:13])-4)*3600 + int(b["time"][14:16])*60 + int(b["time"][17:19])

def idx_at(t, s):
    B = bars(t)
    lo, hi = 0, len(B)-1; r = None
    while lo <= hi:
        m = (lo+hi)//2
        if bsec(B[m]) <= s: r = m; lo = m+1
        else: hi = m-1
    return r

def sim_e3(t, i0, entry_px, stop):
    B = bars(t)
    sh = POS/entry_px; rem = sh; pnl = 0.0; scaled = False
    bank = sh*0.5; target = entry_px*1.10; run_hi = entry_px
    for i in range(i0+1, len(B)):
        b = B[i]
        if bsec(b) >= EOD: break
        if b["low"] <= stop:
            px = stop*(1-MKT); pnl += rem*(px-entry_px)
            return pnl, "stop", bsec(b), px
        if not scaled and b["high"] >= target:
            pnl += bank*(target-entry_px); rem -= bank; scaled = True; continue
        run_hi = max(run_hi, b["high"])
        if scaled and b["close"] < run_hi*0.90:
            px = b["close"]*(1-MKT); pnl += rem*(px-entry_px)
            return pnl, "trail", bsec(b), px
    last = None
    for b in B:
        if bsec(b) < EOD: last = b
    if last is None: return 0.0, "no_tape", EOD, entry_px
    px = last["close"]*(1-MKT); pnl += rem*(px-entry_px)
    return pnl, "eod", EOD, px

# ---------- 1-min aggregate + EMA front_side (the shipped self-compute) ----------
def front_side_self(t, s):
    B = [b for b in bars(t) if bsec(b) < s]
    if not B: return None, 0
    m = collections.OrderedDict()
    for b in B:
        k = bsec(b)//60
        c = m.get(k)
        if c is None: m[k] = dict(b)
        else:
            c["high"]=max(c["high"],b["high"]); c["low"]=min(c["low"],b["low"]); c["close"]=b["close"]
    mb = list(m.values())
    if len(mb) < 22: return None, len(mb)
    def ema(vals, n):
        k = 2.0/(n+1); e = vals[0]
        for v in vals[1:]: e = v*k + e*(1-k)
        return e
    cl = [x["close"] for x in mb]
    return (ema(cl,9) > ema(cl,20)), len(mb)

# ---------- backside gate ----------
def backside_block(t, s, px):
    B = [b for b in bars(t) if bsec(b) <= s]
    if not B: return False
    hi = max(b["high"] for b in B)
    hs = max(bsec(b) for b in B if b["high"] == hi)
    dd = (hi - px)/hi*100.0
    return (15.0 <= dd <= 30.0) and ((s - hs)/60.0 >= 20.0)

def stop_from_tape(t, s, entry):
    B = [b for b in bars(t) if s-60 <= bsec(b) <= s]
    if B:
        lo = min(b["low"] for b in B)
        if 0 < lo < entry: return lo
    return entry*0.94

# ---------- load archive ----------
rows = json.load(open(os.path.join(HERE,"arch.json")))["rows"]
rows = [r for r in rows if r.get("recorded_at")]
rows.sort(key=lambda r: r["recorded_at"])
def rsec(r):
    x = r["recorded_at"]
    return int(x[11:13])*3600 + int(x[14:16])*60 + int(x[17:19])

byt = collections.defaultdict(list)
for r in rows: byt[r.get("ticker")].append(r)

def infer_lane(r):
    t, s = r.get("ticker"), rsec(r)
    best, bd = None, 21
    for o in byt[t]:
        d = abs(rsec(o)-s)
        if d <= 20 and o.get("status","").startswith("triggered_"):
            if d < bd: best, bd = o["status"][10:], d
    return best or (r.get("machine") or r.get("entry_type"))

# ---------- candidate assembly ----------
cands = []   # (sec, ticker, lane, sig_px, stop, fix, note)
seen_fs = {}
for r in rows:
    st, t, s = r.get("status"), r.get("ticker"), rsec(r)
    if not t or t.startswith("_"): continue
    if st == "v2conv_capped":
        cands.append([s, t, "v2conv", r.get("price"), None, "FIX5_caps", "cap refunded"])
    elif st == "grinder_capped":
        cands.append([s, t, "grinder", r.get("price"), None, "FIX5_caps", "cap refunded"])
    elif st == "chart_gate_blocked_trade":
        lane = infer_lane(r)
        if lane in TAPE_LANES:
            cands.append([s, t, lane, r.get("entry"), None, "FIX3_lane_registry", f"lane={lane}"])
    elif st == "momentum_reject":
        lane = infer_lane(r)
        if lane in TAPE_LANES:
            cands.append([s, t, lane, r.get("price"), None, "FIX2_tape_momentum", f"lane={lane}"])
    elif st == "kevseq_reject":
        why = set((r.get("why") or "").split(","))
        if why == {"front_side_unknown"}:
            fs, n = front_side_self(t, s)
            seen_fs[(t,s)] = (fs, n)
            if fs is True:
                cands.append([s, t, "kevseq", r.get("price"), r.get("would_stop"),
                              "FIX4_frontside", f"self front_side=True n={n}"])

# kevseq fires that DID convert -> LIMIT_ENTRY reprice (FIX6)
ks_fires = [r for r in rows if r.get("status") == "triggered_kevseq"]

# ---------- gate walk ----------
def walk(c):
    s, t, lane, px, stop, fix, note = c
    if not px or px <= 0: return None, "no_price"
    if not bars(t): return None, "no_tape"
    if s < ENTRY_OPEN: return None, "pre_open_blackout(<07:00)"
    if s > ENTRY_CLOSE: return None, "past_entry_close"
    i0 = idx_at(t, s)
    if i0 is None: return None, "no_tape_at_fire"
    if stop is None: stop = stop_from_tape(t, s, px)
    if stop >= px: return None, "degenerate_stop"
    if lane not in MIN_STOP_EXEMPT and (px-stop)/px < MIN_STOP_PCT:
        stop = px*(1-MIN_STOP_PCT)      # min-stop widens (live behaviour), not a refusal
    if backside_block(t, s, px): return None, "backside_gate"
    if lane == "kevseq":
        lim = round(px*1.005, 4)
        b = bars(t)[i0]
        if b["low"] > lim: return None, "unfilled_limit(FIX6)"
        entry = min(px, lim)
    else:
        entry = px*(1+SLIP)
    if (entry-stop)/entry < 0.005: return None, "risk_too_tight"
    return (s, t, lane, entry, stop, fix, note, i0), None

ok, refused = [], []
for c in cands:
    a, why = walk(c)
    (ok.append(a) if a else refused.append((c, why)))

# LIMIT_ENTRY on the kevseq fires that already converted / would have
for r in ks_fires:
    s, t = rsec(r), r["ticker"]
    fp, stop, q = r.get("fire_px"), r.get("stop"), r.get("price")
    if not fp or not stop or s < ENTRY_OPEN: continue
    if not bars(t): continue
    i0 = idx_at(t, s)
    if i0 is None: continue
    lim = round(fp*1.005, 4)
    b = bars(t)[i0]
    if b["low"] > lim:
        refused.append((( s,t,"kevseq",q,stop,"FIX6_limit_entry","already-fired"), "unfilled_limit(FIX6)"))
        continue
    entry = min(q or lim, lim)
    if stop >= entry: continue
    if (entry-stop)/entry < MIN_STOP_PCT: stop = entry*(1-MIN_STOP_PCT)
    if backside_block(t, s, entry):
        refused.append(((s,t,"kevseq",q,stop,"FIX6_limit_entry","already-fired"), "backside_gate")); continue
    ok.append((s, t, "kevseq", entry, stop, "FIX6_limit_entry", "converted fire, repriced to limit", i0))


# ---- the four ACTUAL fills (unaffected by fixes except WFF kevseq -> FIX6) ----
ACTUAL = [(9*3600+38*60+42,"FIEE","ignition",5.6962,5.3438),
          (9*3600+41*60+1 ,"DFSC","ignition",2.90,2.6819),
          (11*3600+58*60+39,"NIVF","grinder",0.6757,0.6256)]
for (s_,t_,l_,e_,st_) in ACTUAL:
    i_ = idx_at(t_, s_)
    if i_ is not None:
        ok.append((s_, t_, l_, e_, st_, "ACTUAL", "actual fill (no fix changed it)", i_))
ok.sort(key=lambda x: x[0])

# ---------- chronological slot/capital engine ----------
def run(slots):
    open_pos = []   # (exit_sec, ticker)
    fills = []; skipped = []
    held = set()
    for (s, t, lane, entry, stop, fix, note, i0) in ok:
        open_pos = [p for p in open_pos if p[0] > s]
        held = {p[1] for p in open_pos}
        if t in held: skipped.append((s,t,lane,fix,"already_in_name")); continue
        if len(open_pos) >= slots: skipped.append((s,t,lane,fix,"no_free_slot")); continue
        pnl, why, xs, xpx = sim_e3(t, i0, entry, stop)
        open_pos.append((xs, t))
        fills.append(dict(sec=s, ticker=t, lane=lane, fix=fix, note=note, entry=round(entry,4),
                          stop=round(stop,4), exit_px=round(xpx,4), exit_reason=why,
                          exit_sec=xs, pnl=round(pnl,2)))
    return fills, skipped

def hhmm(s): return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

out = {}
for sl in (2,1):
    f, sk = run(sl)
    out[sl] = (f, sk)

f2, sk2 = out[2]
print(f"CANDIDATES {len(cands)}  passed-stack {len(ok)}  refused {len(refused)}")
print(f"FILLS(2-slot) {len(f2)}  total ${sum(x['pnl'] for x in f2):.2f}")
rth = [x for x in f2 if x['sec'] >= 9*3600+30*60]
pre = [x for x in f2 if x['sec'] <  9*3600+30*60]
print(f"  RTH n={len(rth)} ${sum(x['pnl'] for x in rth):.2f} | PRE n={len(pre)} ${sum(x['pnl'] for x in pre):.2f}")
print()
for x in f2:
    print(f"{hhmm(x['sec'])} {x['ticker']:6s} {x['lane']:8s} {x['fix']:20s} in {x['entry']:9.4f} stop {x['stop']:9.4f} out {x['exit_px']:9.4f} {x['exit_reason']:5s} @{hhmm(x['exit_sec'])} ${x['pnl']:8.2f}")
print()
print("--- skipped by slot contention, per fix ---")
import collections as _c
sk=_c.Counter((x[3],x[4]) for x in sk2)
for k,v in sk.most_common(20): print("  ",k,v)
print()
print("--- UNCONSTRAINED cohort grade (no slot/capital limit) ---")
ag=_c.defaultdict(lambda:[0,0.0])
for (s_,t_,l_,e_,st_,fx,nt,i_) in ok:
    p,w,xs,xp = sim_e3(t_,i_,e_,st_)
    ag[fx][0]+=1; ag[fx][1]+=p
for k,(n,p) in sorted(ag.items(), key=lambda kv:-kv[1][1]): print(f"  {k:22s} n={n:3d}  ${p:9.2f}  (${p/max(n,1):.2f}/trade)")
print()
print("--- per-fix attribution (2-slot) ---")
agg = collections.defaultdict(lambda: [0,0.0])
for x in f2:
    agg[x['fix']][0]+=1; agg[x['fix']][1]+=x['pnl']
for k,(n,p) in sorted(agg.items(), key=lambda kv:-kv[1][1]): print(f"  {k:22s} n={n:3d}  ${p:8.2f}")
print()
print("--- surviving refusals ---")
rc = collections.Counter(w for _,w in refused)
for k,v in rc.most_common(): print(f"  {k:32s} {v}")
print()
f1, sk1 = out[1]
print(f"SENSITIVITY 1-slot (real balance $604.16): n={len(f1)} ${sum(x['pnl'] for x in f1):.2f}")
print(f"skipped-no-slot 2slot={sum(1 for x in sk2 if x[4]=='no_free_slot')} 1slot={sum(1 for x in sk1 if x[4]=='no_free_slot')}")
print()
print("--- worst / best single ---")
if f2:
    print("  worst", min(f2,key=lambda x:x['pnl']))
    print("  best ", max(f2,key=lambda x:x['pnl']))
json.dump({"fills_2slot":f2,"fills_1slot":f1,
           "refused":[[c[:7],w] for c,w in refused],
           "skipped_2slot":sk2}, open(os.path.join(HERE,"cf_out.json"),"w"), indent=1)
