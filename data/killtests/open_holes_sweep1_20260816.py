#!/usr/bin/env python3
"""OPEN-HOLES SWEEP #1 (8/16) — three standing holes on the 62-date universe, live-parity E3.
Chain: FP (flatten_parity_20260816.py) -> S -> G -> F -> C -> B -> E, imported unchanged;
FP.set_mode(True) = live parity (15:30 cutoff, 15:45 flatten, +1% chase, 0.5% mkt, $500 clip,
E3 = bank 1/2 at +10%, 10%-off-high trail after the bank, halt-gap rule on).
HOLE A  day-2/3 continuation (manifest census + reload entry + BA/grinder split by day-1 vs repeat)
HOLE B  seam H2 micro-pullback on 10s bars (5s not in cache), 9:30-9:40, vs BA in the same window
HOLE C  hidden v1 exact trigger (bot hidden_entry_step :5662) re-graded under E3 exits
Analysis only. Writes open_holes_sweep1_20260816_run.txt + _out.json.
"""
import importlib.util, io, os, contextlib, json
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("FP", HERE + "/flatten_parity_20260816.py")
FP = importlib.util.module_from_spec(spec); spec.loader.exec_module(FP)
S = FP.S; G = FP.G; F = FP.F; C = FP.C; B = FP.B; E = FP.E
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)
def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = fn(*a, **k)
    return r, buf.getvalue()

W1, W2 = "13:30:00", "14:30:00"     # 9:30-10:30 ET
def in_win(hh, a=W1, b=W2): return a <= hh < b

def run_live(sigs):
    """E3, live parity, dedup <=5min same name (S.run), 15:30 entry cutoff."""
    FP.set_mode(True)
    return S.run(FP.cut(sigs))

def row(name, tr, dates):
    return S.stats(name, tr, dates, bar=True)

def split_dates(dates, tr):
    d = S.daily(tr, dates); return d

# ------------------------------------------------------------------ HOLE A
def census(manifest, dates):
    md = sorted(manifest)
    idx = {d: i for i, d in enumerate(md)}
    prior = {}   # (sym,date) -> list of prior-run days (1..3 trading days back in the manifest)
    for d in md:
        i = idx[d]
        back = md[max(0, i - 3):i]
        prev = {r["sym"]: pd for pd in back for r in manifest[pd]}   # last appearance wins
        prevs = {}
        for pd in back:
            for r in manifest[pd]: prevs.setdefault(r["sym"], []).append(pd)
        for r in manifest[d]:
            prior[(r["sym"], d)] = prevs.get(r["sym"], [])
    return prior

def det_reload(bars, emas, gaps, vw):
    """Kev reload (simple form): 9:30-10:30 ET, >=5% push from RTH open, then >=3% dip from the
    run high, first 10s bar with a HIGHER LOW (l > prev l) that closes above VWAP -> enter at
    close, stop = dip low. One fire per name-day."""
    if not bars: return []
    o = bars[0]["o"]; run_hi = o; dip_lo = None; pushed = False
    for i in range(1, len(bars)):
        b = bars[i]; hh = E.hhmm_b(b)
        if hh >= W2: break
        run_hi = max(run_hi, b["h"])
        if not pushed:
            if run_hi >= o * 1.05: pushed = True; dip_lo = b["l"]
            continue
        dip_lo = b["l"] if dip_lo is None else min(dip_lo, b["l"])
        if dip_lo <= run_hi * 0.97:
            if b["l"] > bars[i-1]["l"] and b["c"] > vw[i] and b["c"] > dip_lo:
                return [{"i": i, "entry": b["c"], "stop": dip_lo}]
    return []

def hole_a(dates, manifest):
    P("\n# HOLE A — DAY-2/3 CONTINUATION")
    prior = census(manifest, dates)
    keys = sorted(E.DAYS)
    rep = [k for k in keys if prior.get(k)]
    d1 = [k for k in keys if not prior.get(k)]
    P(f"census: {len(keys)} name-days with RTH bars; REPEAT (appeared as a runner on 1-3 prior trading days) = {len(rep)} "
      f"({100*len(rep)/len(keys):.1f}%); day-1 = {len(d1)}")
    # depth: how many prior days
    from collections import Counter
    cnt = Counter(len(prior[k]) for k in rep)
    P(f"repeat depth (prior appearances within 3 days): {dict(sorted(cnt.items()))}")
    P("repeat name-days (first 40): " + ", ".join(f"{s}@{d}" for s, d in rep[:40]))
    R = {"n_all": len(keys), "n_repeat": len(rep), "n_day1": len(d1), "depth": dict(cnt)}
    # signals
    reload_sig, ba_sig, gr_sig = [], [], []
    for k in keys:
        bars, emas, gaps = E.DAYS[k]; vw = S.vwap_series(bars)
        for t in det_reload(bars, emas, gaps, vw):
            reload_sig.append(S.mk(k[0], k[1], "reload", t["i"], t["entry"], t["stop"]))
        for t in G.det_flat_top_break(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            if in_win(hh): ba_sig.append(S.mk(k[0], k[1], "flat_top", t["i"], t["entry"], t["stop"]))
        for t in C.det_grinder_1030(bars, emas, gaps):
            gr_sig.append(S.mk(k[0], k[1], "grinder", t["i"], t["entry"], t["stop"]))
    is_rep = lambda s: bool(prior.get((s["sym"], s["date"])))
    P("\n## Lanes split day-1 vs repeat (solo, dedup, live parity, 62 dates)")
    P(S.HDR); P(S.SEP)
    R["lanes"] = {}
    for nm, sigs in (("reload", reload_sig), ("break-attack 9:30-10:30", ba_sig), ("grinder1030", gr_sig)):
        tr_all = run_live(sigs)
        tr_rep = [x for x in tr_all if is_rep(x)]; tr_d1 = [x for x in tr_all if not is_rep(x)]
        R["lanes"][nm] = {"all": row(f"{nm} ALL", tr_all, dates),
                          "day1": row(f"{nm} DAY-1", tr_d1, dates),
                          "repeat": row(f"{nm} REPEAT", tr_rep, dates)}
        # per-trade view
        for lab, tr in (("day1", tr_d1), ("repeat", tr_rep)):
            n = len(tr)
            if n:
                w = sum(1 for x in tr if x["pnl"] > 0); m = sum(x["pnl"] for x in tr) / n
                P(f"  {nm} {lab}: N={n} win {100*w/n:.0f}% mean/tr ${m:+.2f} total ${sum(x['pnl'] for x in tr):+.2f} "
                  f"best ${max(x['pnl'] for x in tr):+.2f} worst ${min(x['pnl'] for x in tr):+.2f}")
        # active-day view (62-date day-median is a denominator artifact for a 17% cohort)
        import statistics as _st
        for lab, tr in (("day1", tr_d1), ("repeat", tr_rep)):
            act = sorted({x["date"] for x in tr})
            if act:
                dd = S.daily(tr, act); vals = [dd[k] for k in act]
                se = (_st.pstdev([x["pnl"] for x in tr]) / len(tr) ** 0.5) if len(tr) > 1 else 0.0
                P(f"  {nm} {lab} ACTIVE-DAYS: {len(act)} days, day mean ${sum(vals)/len(vals):+.2f} median ${_st.median(vals):+.2f} "
                  f"green {100*sum(1 for v in vals if v>0)/len(vals):.0f}%; per-trade mean SE ${se:.2f}")
                R["lanes"][nm][lab + "_active"] = {"days": len(act), "dmean": sum(vals)/len(vals), "dmed": _st.median(vals), "se": se}
        R["lanes"][nm]["trades_repeat"] = [{k2: x[k2] for k2 in ("sym","date","t","entry","stop","pnl","exit")} for x in tr_rep]
        R["lanes"][nm]["trades_day1_n"] = len(tr_d1)
    # 2-slot portfolio comparison: O-config-like (BA + reload) restricted to repeat vs day1? keep solo. Also
    # reload as an add-on lane to O-config is out of scope (would need slot walk) — noted.
    # hand-trace: largest |pnl| reload trade
    tr = run_live(reload_sig)
    if tr:
        x = max(tr, key=lambda z: abs(z["pnl"]))
        bars, emas, gaps = E.DAYS[(x["sym"], x["date"])]
        lg = []; F.sim_var(bars, emas, gaps, x["i"], x["entry"], x["stop"], "E3", "reload", True, lg)
        P(f"\n## Hand-trace A: {x['sym']} {x['date']} reload entry-bar {x['t']}Z sig {x['entry']:.4f} stop {x['stop']:.4f} "
          f"repeat={is_rep(x)} prior={prior.get((x['sym'],x['date']))} -> ${x['pnl']:+.2f} {x['exit']}")
        P(f"   RTH open {bars[0]['o']:.4f}; fill = sig x1.01 = {x['entry']*1.01:.4f}; shares {500/(x['entry']*1.01):.1f}")
        for m in lg: P("   " + m)
        R["trace"] = {"sym": x["sym"], "date": x["date"], "t": x["t"], "pnl": x["pnl"], "exit": x["exit"], "log": lg}
    return R

# ------------------------------------------------------------------ HOLE B
def det_seam(bars):
    """9:30-9:40 ET: a single 10s bar surging >=4% (close vs prior close), then within the next 3
    bars the first bar with a HIGHER LOW than the previous bar -> enter at its close, stop = its low.
    One fire per name-day."""
    for i in range(1, len(bars)):
        b = bars[i]; hh = E.hhmm_b(b)
        if hh >= "13:40:00": break
        pc = bars[i-1]["c"]
        if pc > 0 and (b["c"] - pc) / pc >= 0.04:
            for j in range(i + 1, min(i + 4, len(bars))):
                if bars[j]["l"] > bars[j-1]["l"] and bars[j]["l"] < bars[j]["c"]:
                    return [{"i": j, "entry": bars[j]["c"], "stop": bars[j]["l"], "surge_i": i}]
            # surge without a higher low inside 3 bars -> keep scanning for the next surge
    return []

def hole_b(dates):
    P("\n# HOLE B — SEAM H2 micro-pullback (10s resolution; 5s bars are NOT in the universe cache)")
    P("resolution limit: the 5s program (task #38) is graded here on 10s bars — a 4% single-10s-bar surge is a coarser event "
      "than the 5s seam; sub-10s micro-pullbacks are invisible. Verdict applies to the 10s form only.")
    seam, ba = [], []
    for k in sorted(E.DAYS):
        bars, emas, gaps = E.DAYS[k]
        for t in det_seam(bars):
            seam.append(S.mk(k[0], k[1], "seam", t["i"], t["entry"], t["stop"], surge_i=t["surge_i"]))
        for t in G.det_flat_top_break(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            if in_win(hh, "13:30:00", "13:40:00"): ba.append(S.mk(k[0], k[1], "flat_top", t["i"], t["entry"], t["stop"]))
    P(f"signals: seam {len(seam)} name-days; break-attack 9:30-9:40 {len(ba)}")
    P(S.HDR); P(S.SEP)
    tr_s = run_live(seam); tr_b = run_live(ba)
    R = {"seam": row("seam 10s (9:30-9:40)", tr_s, dates), "ba_0940": row("break-attack 9:30-9:40", tr_b, dates)}
    # stop-width + risk stats
    sw = [ (x["entry"]-x["stop"])/x["entry"]*100 for x in tr_s ]
    if sw:
        sw.sort(); P(f"seam stop width %: median {sw[len(sw)//2]:.2f} min {sw[0]:.2f} max {sw[-1]:.2f}; "
                     f"win {R['seam']['win']:.0f}%; per-trade mean ${R['seam']['mean_tr']:+.2f}")
    # overlap
    sk = {(x["sym"], x["date"]) for x in tr_s}; bk = {(x["sym"], x["date"]) for x in tr_b}
    both = sk & bk
    P(f"overlap: seam name-days {len(sk)}, BA name-days {len(bk)}, both {len(both)}")
    if both:
        ps = sum(x["pnl"] for x in tr_s if (x["sym"], x["date"]) in both)
        pb = sum(x["pnl"] for x in tr_b if (x["sym"], x["date"]) in both)
        P(f"  on the overlap: seam ${ps:+.2f} vs BA ${pb:+.2f}")
    only_s = [x for x in tr_s if (x["sym"], x["date"]) not in bk]
    P(f"  seam-only name-days: N={len(only_s)} ${sum(x['pnl'] for x in only_s):+.2f}")
    R["overlap"] = {"both": len(both), "seam_only_n": len(only_s), "seam_only_pnl": sum(x["pnl"] for x in only_s)}
    # combined marginal: BA + seam-only
    comb = tr_b + only_s
    R["ba_plus_seamonly"] = row("BA 9:30-9:40 + seam-only add", comb, dates)
    # exits breakdown
    from collections import Counter
    P("seam exits: " + str(dict(Counter(x["exit"].split("@")[0] for x in tr_s))))
    if tr_s:
        x = max(tr_s, key=lambda z: abs(z["pnl"]))
        bars, emas, gaps = E.DAYS[(x["sym"], x["date"])]
        lg = []; F.sim_var(bars, emas, gaps, x["i"], x["entry"], x["stop"], "E3", "seam", True, lg)
        si = x["surge_i"]
        P(f"\n## Hand-trace B: {x['sym']} {x['date']} surge bar {E.hhmm_b(bars[si])}Z {bars[si-1]['c']:.4f}->{bars[si]['c']:.4f} "
          f"(+{(bars[si]['c']/bars[si-1]['c']-1)*100:.1f}%), entry bar {x['t']}Z low {x['stop']:.4f} > prev low {bars[x['i']-1]['l']:.4f}, "
          f"sig {x['entry']:.4f} fill {x['entry']*1.01:.4f} -> ${x['pnl']:+.2f} {x['exit']}")
        for m in lg: P("   " + m)
        R["trace"] = {"sym": x["sym"], "date": x["date"], "t": x["t"], "pnl": x["pnl"], "exit": x["exit"], "log": lg}
    return R

# ------------------------------------------------------------------ HOLE C
HV_PCT, HV_BARS, MIN_BARS = 25.0, 30, 90
def det_hidden_v1(full, rth):
    """Exact port of hidden_entry_step (marcos_trading_bot.py :5662-5722), fed the FULL-day 10s bars
    (premarket-anchored VWAP + 10s 90EMA warmed from the first bar, like the live deep pass):
      ARM: trailing 30-bar close velocity >= 25% (stays armed).
      FIRE: l <= anchor=max(e90,vwap), c >= anchor, c >= vwap, (c-l)/(h-l) >= 0.5, c > o*0.995,
            nbars >= 90 (anchor-maturity gate).  stop = min(l-0.01, c*0.95).
    Returns fires mapped to RTH bar indices (RTH-only entries), with ext_vwap stamped."""
    closes = []; e90 = None; armed = False; nbars = 0; cv = cpv = 0.0
    tidx = {b["t"]: i for i, b in enumerate(rth)}
    out = []
    for b in full:
        o, h, l, c, v = b["o"], b["h"], b["l"], b["c"], b["v"]
        nbars += 1
        e90 = c if e90 is None else c * (2.0/91.0) + e90 * (89.0/91.0)
        tp = (h + l + c) / 3.0; cv += v; cpv += tp * v
        vwap = cpv / cv if cv else c
        closes.append(c)
        if len(closes) > HV_BARS + 1: closes.pop(0)
        if not armed:
            if len(closes) > HV_BARS:
                ca = closes[0]
                if ca > 0 and (c - ca) / ca * 100.0 >= HV_PCT: armed = True
            continue
        anchor = max(e90, vwap); rng = h - l
        if (l <= anchor and c >= anchor and c >= vwap and rng > 0 and (c - l) / rng >= 0.5 and c > o * 0.995):
            if nbars < MIN_BARS: continue
            i = tidx.get(b["t"])
            if i is None: continue           # premarket fire: PRE book, not graded here
            stop = min(l - 0.01, c * 0.95)
            out.append({"i": i, "entry": c, "stop": stop, "ext": (c - vwap) / vwap * 100.0, "anchor": anchor})
    return out

def hole_c(dates):
    P("\n# HOLE C — EX-HIDDEN v1 ENTRIES RE-GRADED UNDER E3 EXITS")
    P("trigger read this run: marcos_trading_bot.py :5662 hidden_entry_step — ARM 25%/30 bars; FIRE wick-reclaim of max(EMA90,VWAP), "
      "close>=anchor & >=VWAP, close top-half, body > -0.5%; nbars>=90; stop=min(low-0.01, 5%). Fed FULL-day bars (premarket VWAP anchor).")
    sigs = []
    for k in sorted(E.DAYS):
        rth = E.DAYS[k][0]; full = S.FULL[k]
        for t in det_hidden_v1(full, rth):
            sigs.append(S.mk(k[0], k[1], "hidden", t["i"], t["entry"], t["stop"], ext=t["ext"]))
    P(f"raw RTH fires: {len(sigs)} across {len({(s['sym'],s['date']) for s in sigs})} name-days")
    R = {"raw_fires": len(sigs)}
    from collections import Counter
    P(S.HDR); P(S.SEP)
    variants = {}
    win_s = [s for s in sigs if in_win(s["t"])]
    variants["all-day, all fires (dedup 5min)"] = sigs
    variants["9:30-10:30 window"] = win_s
    # live gates: ext gate 3-10% ; name cap 2 (first 2 fires per name-day) ; both
    ext = lambda ss: [s for s in ss if 3.0 <= s["ext"] < 10.0]
    def cap2(ss):
        c = Counter(); o = []
        for s in sorted(ss, key=lambda z: (z["date"], z["sym"], z["t"])):
            k = (s["sym"], s["date"])
            if c[k] >= 2: continue
            c[k] += 1; o.append(s)
        return o
    variants["all-day + ext gate 3-10%"] = ext(sigs)
    variants["all-day + name cap 2"] = cap2(sigs)
    variants["all-day + ext gate + cap 2 (live-ish)"] = cap2(ext(sigs))
    variants["9:30-10:30 + ext gate + cap 2"] = cap2(ext(win_s))
    first = {}
    for s in sorted(sigs, key=lambda z: (z["date"], z["sym"], z["t"])):
        first.setdefault((s["sym"], s["date"]), s)
    variants["first fire per name-day only"] = list(first.values())
    R["variants"] = {}
    trs = {}
    for nm, ss in variants.items():
        tr = run_live(ss); trs[nm] = tr
        R["variants"][nm] = row(f"hidden v1 {nm}", tr, dates)
        R["variants"][nm]["exits"] = dict(Counter(x["exit"].split("@")[0] for x in tr))
    # by hour-window
    P("\nby window (all fires, dedup):")
    tr = trs["all-day, all fires (dedup 5min)"]
    byw = {}
    for x in tr: byw.setdefault(S.win_of(x["t"]), []).append(x)
    for w in sorted(byw):
        xs = byw[w]; P(f"  {w}: N={len(xs)} total ${sum(x['pnl'] for x in xs):+.2f} mean ${sum(x['pnl'] for x in xs)/len(xs):+.2f} "
                       f"win {100*sum(1 for x in xs if x['pnl']>0)/len(xs):.0f}%")
    R["by_window"] = {w: {"n": len(xs), "total": sum(x["pnl"] for x in xs)} for w, xs in byw.items()}
    P("exits (all-day dedup): " + str(R["variants"]["all-day, all fires (dedup 5min)"]["exits"]))
    # per-day list of the in-window live-ish variant
    if tr:
        x = max(tr, key=lambda z: abs(z["pnl"]))
        bars, emas, gaps = E.DAYS[(x["sym"], x["date"])]
        lg = []; F.sim_var(bars, emas, gaps, x["i"], x["entry"], x["stop"], "E3", "hidden", True, lg)
        b = bars[x["i"]]
        P(f"\n## Hand-trace C: {x['sym']} {x['date']} hidden fire {x['t']}Z bar o {b['o']:.4f} h {b['h']:.4f} l {b['l']:.4f} c {b['c']:.4f} "
          f"ext_vwap {x['ext']:+.2f}% stop {x['stop']:.4f} ({(x['entry']-x['stop'])/x['entry']*100:.1f}% risk) fill {x['entry']*1.01:.4f} -> ${x['pnl']:+.2f} {x['exit']}")
        for m in lg: P("   " + m)
        R["trace"] = {"sym": x["sym"], "date": x["date"], "t": x["t"], "pnl": x["pnl"], "exit": x["exit"], "log": lg}
    return R

def main():
    P("# OPEN-HOLES SWEEP #1 — 8/16 (analysis only; live-parity E3 via flatten_parity chain)")
    (nf, nd, dates), _ = quiet(S.load_all)
    P(f"universe: {nf} files, {nd} name-days with >=60 RTH bars, {len(dates)} dates {dates[0]}..{dates[-1]}; "
      f"E3 = +1% chase, 0.5% mkt, $500 clip, bank 1/2 at +10%, 10%-off-high trail, halt-gap rule, 15:30 cutoff, 15:45 flatten")
    manifest = json.load(open(os.path.dirname(E.BARS_DIR) + "/manifest.json"))
    R = {"A": hole_a(dates, manifest), "B": hole_b(dates), "C": hole_c(dates)}
    FP.set_mode(False)
    json.dump(R, open(HERE + "/open_holes_sweep1_20260816_out.json", "w"), indent=1, default=str)
    open(HERE + "/open_holes_sweep1_20260816_run.txt", "w").write("\n".join(OUT) + "\n")

if __name__ == "__main__":
    main()
