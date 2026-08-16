import importlib.util, io, contextlib, sys
spec = importlib.util.spec_from_file_location("K", "/Users/marcosolivera/Desktop/Marcos-Trading-Bot/data/killtests/rocket_sleeve_killtest_20260816.py")
K = importlib.util.module_from_spec(spec); spec.loader.exec_module(K)
K.E.DAYS.clear(); nf, nd, dates = K.quiet(K.S.load_all)
VW = {k: K.S.vwap_series(v[0]) for k, v in K.E.DAYS.items()}
def run(cap, exit_v, hm, gmin=1.0, post11=True):
    trades=[]
    for key,(bars,emas,gaps) in K.E.DAYS.items():
        sigs,R = K.find_entries(bars,gaps,VW[key],gmin,post11)
        last=None;n=0;busy=-1
        for s in sigs:
            if s["t"]>=K.CUTOFF_T or s["i"]<=busy: continue
            if last is not None and K.B.tsec(s["t"])-last<1200: continue
            if n>=cap: break
            r=K.sim_sleeve(bars,gaps,s["i"],s["entry"],s["stop"],exit_v,hm)
            trades.append(dict(sym=key[0],date=key[1],**s,**r,big=key in K.TOPKEY,risk=K.POS*(1-s["stop"]/(s["entry"]*1.01))))
            last=K.B.tsec(s["t"]);n+=1;busy=r["xi"]
    trades.sort(key=lambda x:(x["date"],x["t"]))
    sc=K.scorecard(trades,dates)
    print(f"cap={cap} {exit_v} {hm} post11={post11}: N={sc['n']} tot={sc['tot']:+.0f} halves {sc['a']:+.0f}/{sc['b']:+.0f} HR={sc['hr']} worst={sc['worst']:+.0f} mdd={sc['mdd']:.0f} prem={[round(p) for p in sc['prem']]} big {sc['big_n']}/{sc['big_pnl']:+.0f} nonbig {sc['nb_n']}/{sc['nb_pnl']:+.0f}")
    return trades
for cap in (2,4,99):
    for ev in ("E4","E4W","STRUCT"):
        for hm in ("exit","hold"):
            run(cap,ev,hm)
tr=run(99,"E4W","hold")
for x in tr:
    if x["sym"] in ("INHD","ZYBT","PAVS") and x["date"] in ("2026-06-08","2026-07-20","2026-06-09"): print(x["sym"],x["t"],round(x["entry"],3),x["exit"],round(x["pnl"]))
