#!/usr/bin/env python3
"""ORB-15 vs flat_top BREAK-ATTACK head-to-head 8/16 (PRE-REGISTERED). Analysis only.
Chain: flatten_parity_20260816.py (LIVE-parity F.sim_var: 15:30 no-entry, 15:45 flatten)
 -> sunday_afternoon_studies_20260816.py -> G -> F -> C -> B -> engine, imported UNCHANGED.
Universe = full bars10s cache (62 dates). Lanes:
  BA  = flat_top break-attack, in-window 13:30-14:30Z (round G champion trigger), E3
  ORB = 15-min ORB, ORL stop (Sunday T5 signal gen, verbatim copy via flatten_parity), E3
Tests: (1) overlap +-10 min on same name-day, cohort P&L; (2) 2-slot portfolios BA / ORB /
combined (B.pipeline H1-H4, first-signal-wins dedup); (3) 3-slot combined (local H4 walker,
reconciled to B.pipeline at 2 slots); (4) daily-P&L correlation.
"""
import importlib.util, os, io, contextlib, json, statistics, math
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("FP", HERE + "/flatten_parity_20260816.py")
FP = importlib.util.module_from_spec(spec); spec.loader.exec_module(FP)
S = FP.S; G = FP.G; F = G.F; C = G.C; B = G.B; E = G.E
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)
def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = fn(*a, **k)
    return r

def orb15():
    """verbatim Sunday T5 / flatten_parity signal gen (15-min, ORL)."""
    sigs = []; minutes = 15
    endt = 13 * 3600 + 30 * 60 + minutes * 60
    for k, (bars, emas, gaps) in sorted(E.DAYS.items()):
        vw = S.vwap_series(bars)
        orb_bars = [b for b in bars if E.secs(b) < endt]
        if not orb_bars: continue
        orh = max(b["h"] for b in orb_bars); orl = min(b["l"] for b in orb_bars)
        avgv = sum(b["v"] for b in orb_bars) / minutes
        mins = {}
        for i, b in enumerate(bars):
            s = E.secs(b)
            if s < endt or s >= 14 * 3600 + 30 * 60: continue
            key = s // 60
            m = mins.setdefault(key, {"c": b["c"], "v": 0.0, "i": i})
            m["c"] = b["c"]; m["v"] += b["v"]; m["i"] = i
        for key in sorted(mins):
            m = mins[key]
            if m["c"] > orh and m["v"] >= 1.5 * avgv and m["c"] > vw[m["i"]]:
                if orl < m["c"]:
                    sigs.append(S.mk(k[0], k[1], "orb", m["i"], m["c"], orl))
                break
    return sigs

def ba_inwindow():
    sigs = []
    for (sym, date), (bars, emas, gaps) in sorted(E.DAYS.items()):
        for t in S.det_flat_top_break_lvl(bars, emas, gaps):
            s = S.mk(sym, date, "flat_top", t["i"], t["entry"], t["stop"], level=t["level"])
            if "13:30:00" <= s["t"] <= "14:30:00": sigs.append(s)
    return sigs

def ex_any(s, halt_rule):
    bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
    pnl, exx, xi = F.sim_var(bars, emas, gaps, s["i"], s["entry"], s["stop"], "E3", s["det"], halt_rule)
    return True, pnl, exx, xi, s["i"]

def h5(h4, dates):
    d = {dt: 0.0 for dt in dates}
    for x in h4: d[x["date"]] += x["pnl"]
    vals = [d[k] for k in dates]; n = len(vals); sv = sorted(vals)
    med = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
    mid = dates[n // 2]; n1 = sum(1 for k in dates if k < mid); n2 = n - n1
    h1 = sum(d[k] for k in dates if k < mid); h2 = sum(d[k] for k in dates if k >= mid)
    green = sum(1 for v in vals if v > 0)
    ok = (sum(vals) / n > 50 and med > 50 and green / n >= 0.55 and h1 > 0 and h2 > 0 and min(vals) > -300)
    return dict(N=len(h4), mean=sum(vals) / n, median=med, green=green, n=n, h1=h1 / n1, h2=h2 / n2,
                worst=min(vals), ok=ok, daily=d)

def port_local(sigs, dates, nslots):
    """H1-H4 like B.pipeline (halt rule on, dedup same-name<=5min first-wins, capacity nslots)."""
    tr = []
    for s in sigs:
        _, pnl, ex, xi, fb = ex_any(s, True)
        bars = E.DAYS[(s["sym"], s["date"])][0]; ft = E.hhmm_b(bars[fb])
        tr.append({**s, "pnl": pnl, "exit": ex, "xi": xi, "fill_t": ft, "fill_key": s["date"] + "T" + ft})
    tr.sort(key=lambda x: (x["fill_key"], x["det"]))
    h3 = []; last = {}
    for s in tr:
        k = (s["sym"], s["date"]); ss = B.tsec(s["fill_t"]); ls = last.get(k)
        if ls is not None and ss - ls <= 300: continue
        last[k] = ss; h3.append(s)
    h4 = []; open_pos = []; nskip = 0
    for s in h3:
        bars = E.DAYS[(s["sym"], s["date"])][0]
        open_pos = [p for p in open_pos if p >= s["fill_key"]]
        if len(open_pos) >= nslots: nskip += 1; continue
        open_pos.append(s["date"] + "T" + E.hhmm_b(bars[min(s["xi"], len(bars) - 1)])); h4.append(s)
    r = h5(h4, dates); r["nskip"] = nskip; r["h4"] = h4; return r

HDR = "| portfolio | N | day mean | day median | green | halves $/d | worst | 5/5 bar |"
SEP = "|---|---|---|---|---|---|---|---|"
def row(name, r):
    P(f"| {name} | {r['N']} | ${r['mean']:+.2f} | ${r['median']:+.2f} | {r['green']}/{r['n']} ({100*r['green']/r['n']:.0f}%) | "
      f"${r['h1']:+.2f}/${r['h2']:+.2f} | ${r['worst']:+.2f} | {'PASS' if r['ok'] else 'FAIL'} |")

def pear(a, b):
    n = len(a); ma = sum(a) / n; mb = sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a)); sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else float("nan")

def main():
    E.DAYS.clear()
    nf, nd, dates = quiet(S.load_all)
    FP.set_mode(True)   # LIVE parity: 15:45 flatten
    P("# ORB-15 (ORL) vs flat_top BREAK-ATTACK head-to-head — 2026-08-16, LIVE-parity sim (15:30 no-entry, 15:45 flatten)")
    P(f"full cache: {nf} files, {nd} day-files, {len(dates)} dates {dates[0]}..{dates[-1]}; E3 exits; chain FP->S->G->F->C->B->E unchanged")
    osig = FP.cut(orb15()); bsig = FP.cut(ba_inwindow())
    P(f"signals: ORB15 {len(osig)}  BA in-window(13:30-14:30Z) {len(bsig)}  (post 15:30 cutoff; none expected dropped)")
    tro = S.run(osig); trb = S.run(bsig)
    P("\n## Solo lanes (dedup, no capacity)"); P(S.HDR); P(S.SEP)
    ro = S.stats("ORB15 ORL solo", tro, dates, bar=True); rb = S.stats("BA solo", trb, dates, bar=True)
    P("reconcile: NEW ORB15 solo from flatten_parity = N=371 (see flatten_parity run); BA 62-date solo is new here")

    # ---- T1 overlap ----
    P("\n## T1 — OVERLAP: ORB15 signal on a name-day where BA also fired within +-10 min")
    bmap = {}
    for x in trb: bmap.setdefault((x["sym"], x["date"]), []).append(x)
    ov = []; oo = []; b_ov_ids = set()
    for x in tro:
        near = [y for y in bmap.get((x["sym"], x["date"]), []) if abs(B.tsec(y["t"]) - B.tsec(x["t"])) <= 600]
        if near:
            ov.append(x); b_ov_ids.update((y["sym"], y["date"], y["i"]) for y in near)
        else: oo.append(x)
    b_ov = [y for y in trb if (y["sym"], y["date"], y["i"]) in b_ov_ids]
    b_only = [y for y in trb if (y["sym"], y["date"], y["i"]) not in b_ov_ids]
    same_nd = sum(1 for x in tro if (x["sym"], x["date"]) in bmap)
    P(f"ORB15 trades {len(tro)}: {len(ov)} ({100*len(ov)/len(tro):.0f}%) overlap BA within +-10min; {same_nd} ({100*same_nd/len(tro):.0f}%) share a name-day with any BA trade")
    lead = [B.tsec(x["t"]) - min(B.tsec(y["t"]) for y in bmap[(x["sym"], x["date"])] if abs(B.tsec(y["t"]) - B.tsec(x["t"])) <= 600) for x in ov]
    if lead: P(f"ORB minus BA signal time on overlaps: median {statistics.median(lead):+.0f}s, ORB later in {sum(1 for v in lead if v > 0)}/{len(lead)}")
    P(S.HDR); P(S.SEP)
    S.stats("ORB overlapping (BA within 10m)", ov, dates); S.stats("ORB-only (no BA within 10m)", oo, dates)
    S.stats("BA overlapping", b_ov, dates); S.stats("BA-only (no ORB within 10m)", b_only, dates)

    # ---- T2 2-slot portfolios ----
    P("\n## T2 — 2-SLOT PORTFOLIOS (B.pipeline H1-H4, first-signal-wins same-name dedup, E3)")
    P(HDR); P(SEP)
    key = lambda s: (s["key"], s["sym"], s["det"])
    R = {}
    for nm, sigs in (("BA-only 2-slot", bsig), ("ORB15-only 2-slot", osig), ("COMBINED BA+ORB15 2-slot", sorted(bsig + osig, key=key))):
        res = quiet(B.pipeline, sorted(sigs, key=key), dates, ex_any, nm)
        h = res["h5"]; v = res["verdict"]
        r = dict(N=len(res["h4"]), mean=h["mean"], median=h["median"], green=h["green"], n=h["n"], h1=h["half1d"], h2=h["half2d"],
                 worst=h["worst"], ok=all(p for _, p in v.values()), nskip=h["nskip"], daily=res["daily"], h4=res["h4"])
        R[nm] = r; row(nm, r)
        loc = port_local(sorted(sigs, key=key), dates, 2)
        assert abs(loc["mean"] - r["mean"]) < 1e-6 and loc["N"] == r["N"], (nm, loc["mean"], r["mean"])
    comb = R["COMBINED BA+ORB15 2-slot"]
    P(f"combined 2-slot per-lane: " + ", ".join(f"{d} N={sum(1 for x in comb['h4'] if x['det']==d)} ${sum(x['pnl'] for x in comb['h4'] if x['det']==d):+.2f}" for d in ("flat_top", "orb")) + f"; slot-skipped {comb['nskip']}")
    P("local 2-slot walker reconciled to B.pipeline on all three (asserted)")
    ba2 = R["BA-only 2-slot"]
    P(f"lift vs BA-only: mean ${comb['mean']-ba2['mean']:+.2f}/d, median ${comb['median']-ba2['median']:+.2f}/d")
    dd = [comb["daily"][k] - ba2["daily"][k] for k in dates]
    P(f"combined-minus-BA daily: {sum(1 for v in dd if v>0)} up / {sum(1 for v in dd if v<0)} down / {sum(1 for v in dd if v==0)} tie; worst delta ${min(dd):+.2f} best ${max(dd):+.2f}")

    # ---- T3 3-slot ----
    P("\n## T3 — 3-SLOT variant (local walker)")
    P(HDR); P(SEP)
    for nm, sigs in (("BA-only 3-slot", bsig), ("ORB15-only 3-slot", osig), ("COMBINED BA+ORB15 3-slot", sorted(bsig + osig, key=key))):
        r = port_local(sorted(sigs, key=key), dates, 3); R[nm] = r; row(nm, r)
    c3 = R["COMBINED BA+ORB15 3-slot"]
    P(f"combined 3-slot per-lane: " + ", ".join(f"{d} N={sum(1 for x in c3['h4'] if x['det']==d)} ${sum(x['pnl'] for x in c3['h4'] if x['det']==d):+.2f}" for d in ("flat_top", "orb")) + f"; slot-skipped {c3['nskip']}")

    # ---- T4 correlation ----
    P("\n## T4 — daily P&L correlation ORB15 vs BA")
    a = [S.daily(tro, dates)[k] for k in dates]; b = [S.daily(trb, dates)[k] for k in dates]
    P(f"solo lanes (no capacity): Pearson r = {pear(a, b):+.3f} over {len(dates)} days")
    a2 = [R['ORB15-only 2-slot']['daily'][k] for k in dates]; b2 = [ba2['daily'][k] for k in dates]
    P(f"2-slot portfolios: Pearson r = {pear(a2, b2):+.3f}; sign agreement {sum(1 for x,y in zip(a2,b2) if (x>0)==(y>0))}/{len(dates)}")
    P(f"BA-only red days: {sum(1 for v in b2 if v<=0)}; of those ORB green: {sum(1 for x,y in zip(a2,b2) if y<=0 and x>0)}")

    # ---- verdict ----
    P("\n## VERDICT (pre-registered: ADDITIVE = combined 2-slot beats BA-only on mean AND median)")
    add = comb["mean"] > ba2["mean"] and comb["median"] > ba2["median"]
    orb2 = R["ORB15-only 2-slot"]
    if add: v = "ADDITIVE"
    elif orb2["mean"] > ba2["mean"] and orb2["median"] > ba2["median"]: v = "SUBSTITUTE (ORB better alone)"
    else: v = "REDUNDANT"
    P(f"-> {v}: BA-only mean ${ba2['mean']:+.2f}/med ${ba2['median']:+.2f} | ORB-only ${orb2['mean']:+.2f}/${orb2['median']:+.2f} | combined ${comb['mean']:+.2f}/${comb['median']:+.2f} | combined 3-slot ${c3['mean']:+.2f}/${c3['median']:+.2f}")
    # hand-trace: one overlapping pair
    if ov:
        x = max(ov, key=lambda z: abs(z["pnl"])); y = min(bmap[(x["sym"], x["date"])], key=lambda z: abs(B.tsec(z["t"]) - B.tsec(x["t"])))
        P(f"\nhand-trace overlap pair: {x['sym']} {x['date']} ORB sig {x['t']}Z entry {x['entry']:.4f} stop {x['stop']:.4f} -> ${x['pnl']:+.2f} {x['exit']} | BA sig {y['t']}Z entry {y['entry']:.4f} stop {y['stop']:.4f} -> ${y['pnl']:+.2f} {y['exit']}")
        for det, z in (("orb", x), ("flat_top", y)):
            log = []; bars, emas, gaps = E.DAYS[(z["sym"], z["date"])]
            F.sim_var(bars, emas, gaps, z["i"], z["entry"], z["stop"], "E3", det, True, log)
            for m in log: P(f"    [{det}] " + m)
    FP.set_mode(False)
    json.dump({k: {kk: vv for kk, vv in r.items() if kk not in ("h4",)} for k, r in R.items()},
              open(HERE + "/orb_vs_ba_20260816_out.json", "w"), indent=1, default=str)
    open(HERE + "/orb_vs_ba_20260816_run.txt", "w").write("\n".join(OUT) + "\n")

if __name__ == "__main__":
    main()
