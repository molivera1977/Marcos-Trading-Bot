#!/usr/bin/env python3
"""EXIT x EYES JOIN (Part 3 of EYES_MATRIX_20260816) — read-only analysis.
Imports context_joins_20260815.py's chain (G -> F -> C -> B -> engine of record).
Same 36-date window (6/25-8/14), 421 files, E3 baseline (bank 1/2 at +10%, trail rest
10%-off-high closes-through, stop-first, -1% chase entry, -0.5% market-exit slip),
H2 halt rule + H3 dedup, NO capacity (N constant across variants — round F/G convention).
Champion lanes: grinder-1030 (C.det_grinder_1030) + flat_top BREAK-attack in-window
(G.det_flat_top_break, 13:30-14:30Z). Baseline must reconcile to context_joins:
grinder N=239 +$5,483.15, break N=384 +$9,220.01.

VARIANTS (exit-side eyes added to E3):
  V1 VWAP-loss AFTER BANK: once banked, exit remaining on first completed 10s close < session VWAP
     (VWAP = RTH-anchored typical-price cumulative, same sibling definition as context_joins).
  V2 VWAP-loss ANYTIME: from entry, exit ALL remaining on first completed 10s close < VWAP
     (bank still taken first if the +10% target prints before the VWAP loss).
  V3 HALT-DISTANCE TIGHTEN: LULD upper band proxy = 5-min (30-bar) mean close x (1+band),
     band 10% for ref>=$3.00, 20% for $0.75-$3, 75% below $0.75 (Tier 2 NMS, RTH; doubled
     13:30-13:45Z and 19:45-20:00Z). When close is within 3% of the upper band, the post-bank
     trail tightens from 10% to 5% off run-high (closes-through). Pre-bank behavior unchanged.
  V3b: same as V3 but tighten applies pre-bank too (exit all if close < 0.95*run_hi while near band).
"""
import importlib.util, os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("CJ", HERE + "/context_joins_20260815.py")
CJ = importlib.util.module_from_spec(spec); spec.loader.exec_module(CJ)
G, F, C, B, E = CJ.G, CJ.F, CJ.C, CJ.B, CJ.E
MKT = 0.005; SLIP = 0.01

def luld_pct(ref, hh):
    if ref >= 3.0: p = 0.10
    elif ref >= 0.75: p = 0.20
    else: p = 0.75
    if hh < "13:45:00" or hh >= "19:45:00": p *= 2
    return p

def sim(bars, emas, gaps, entry_i, sig_px, stop, det, vw, var, log=None):
    entry_px = sig_px * (1 + SLIP); sh = E.POS / entry_px; rem = sh; pnl = 0.0; scaled = False
    bank_sh = sh * 0.5; target = entry_px * 1.10; run_hi = entry_px
    flatten = (det == "grinder"); e_s = E.secs(bars[entry_i])
    my_gaps = {post: pre for pre, post, g in gaps if entry_i <= pre and 0 <= E.secs(bars[pre]) - e_s <= 120}
    def L(m):
        if log is not None: log.append(m)
    for i in range(entry_i + 1, len(bars)):
        b = bars[i]; hh = E.hhmm_b(b)
        if flatten and hh >= "19:59:00":
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px); L(f"{hh} FLATTEN {px:.4f}"); return pnl, "eod", i
        if i in my_gaps and b["o"] < stop:
            px = b["o"] * (1 - MKT); pnl += rem * (px - entry_px); L(f"{hh} HALT-GAP {px:.4f}"); return pnl, f"haltgap@{hh}", i
        if b["l"] <= stop:
            px = stop * (1 - MKT); pnl += rem * (px - entry_px); L(f"{hh} STOP {stop:.4f} fill {px:.4f}"); return pnl, f"stop@{hh}", i
        if not scaled and b["h"] >= target:
            pnl += bank_sh * (target - entry_px); rem -= bank_sh; scaled = True; L(f"{hh} BANK 1/2 at {target:.4f}"); continue
        run_hi = max(run_hi, b["h"])
        # --- eye: VWAP loss ---
        if var in ("V1", "V2") and (scaled or var == "V2") and b["c"] < vw[i]:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} VWAP-LOSS close {b['c']:.4f} < vwap {vw[i]:.4f} fill {px:.4f}"); return pnl, f"vwaploss@{hh}", i
        # --- eye: halt distance ---
        near = False
        if var in ("V3", "V3b"):
            j = max(0, i - 30); ref = sum(x["c"] for x in bars[j:i]) / max(1, i - j)
            ub = ref * (1 + luld_pct(ref, hh))
            near = b["c"] >= ub * 0.97
        trail_pct = 0.05 if near else 0.10
        if scaled and b["c"] < run_hi * (1 - trail_pct):
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} TRAIL{'-TIGHT' if near else ''} close {b['c']:.4f} runhi {run_hi:.4f} fill {px:.4f}"); return pnl, f"trail{'T' if near else ''}@{hh}", i
        if var == "V3b" and not scaled and near and b["c"] < run_hi * 0.95:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} PRE-BANK TIGHT close {b['c']:.4f} runhi {run_hi:.4f} fill {px:.4f}"); return pnl, f"trailTpre@{hh}", i
    b = bars[-1]; px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px); L(f"{E.hhmm_b(b)} EOD {px:.4f}")
    return pnl, "eod", len(bars) - 1

def run(signals, var):
    tr = []
    for s in signals:
        bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
        vw = CJ.VW[(s["sym"], s["date"])]
        pnl, exx, xi = sim(bars, emas, gaps, s["i"], s["entry"], s["stop"], s["det"], vw, var)
        ft = E.hhmm_b(bars[s["i"]])
        tr.append({**s, "pnl": pnl, "exit": exx, "xi": xi, "fill_t": ft, "fill_key": s["date"] + "T" + ft})
    return F.dedup(tr)

def stats(tr, dates):
    d = {dt: 0.0 for dt in dates}
    for x in tr: d[x["date"]] += x["pnl"]
    vals = [d[k] for k in dates]; sv = sorted(vals); n = len(vals)
    med = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
    N = len(tr); tot = sum(x["pnl"] for x in tr)
    return dict(N=N, win=100 * sum(1 for x in tr if x["pnl"] > 0) / N, total=tot, mean=tot / N,
                dmean=sum(vals) / n, dmed=med, worst=min(vals), green=100 * sum(1 for v in vals if v > 0) / n)

def main():
    nfiles, dates, allsig = B.gen_signals()
    print(f"FILES: {nfiles} DATES: {len(dates)} {dates[0]}..{dates[-1]}")
    for k in E.DAYS: CJ.build_vwap(*k)
    gsig = []; fbrk = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in C.det_grinder_1030(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            gsig.append({"sym": sym, "date": date, "det": "grinder", "i": t["i"], "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
        for t in G.det_flat_top_break(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            if not ("13:30:00" <= hh <= "14:30:00"): continue
            fbrk.append({"sym": sym, "date": date, "det": "flat_top", "i": t["i"], "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    for l in (gsig, fbrk): l.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    out = {}
    for name, sig in (("grinder1030", gsig), ("flat_top_break", fbrk)):
        base = run(sig, "E3"); bs = stats(base, dates)
        bmap = {(x["sym"], x["date"], x["i"]): x for x in base}
        print(f"\n== {name} E3 BASELINE: N={bs['N']} win={bs['win']:.0f}% total=${bs['total']:+.2f} mean/tr=${bs['mean']:+.2f} dmean=${bs['dmean']:+.2f} dmed=${bs['dmed']:+.2f} green={bs['green']:.0f}% worst=${bs['worst']:+.2f}")
        out[name] = {"E3": bs}
        for var in ("V1", "V2", "V3", "V3b"):
            tr = run(sig, var); st = stats(tr, dates)
            fired = [x for x in tr if x["exit"].startswith(("vwaploss", "trailT"))]
            fb = sum(bmap[(x["sym"], x["date"], x["i"])]["pnl"] for x in fired if (x["sym"], x["date"], x["i"]) in bmap)
            fv = sum(x["pnl"] for x in fired)
            same = st["N"] == bs["N"]
            print(f"  {var}: N={st['N']}{'' if same else '(!N)'} win={st['win']:.0f}% total=${st['total']:+.2f} (delta ${st['total']-bs['total']:+.2f}) mean/tr=${st['mean']:+.2f} dmean=${st['dmean']:+.2f} dmed=${st['dmed']:+.2f} green={st['green']:.0f}% worst=${st['worst']:+.2f} | rule fired {len(fired)}/{st['N']}: rule ${fv:+.2f} vs E3-on-same ${fb:+.2f}")
            out[name][var] = {**st, "fired": len(fired), "fired_rule": fv, "fired_base": fb, "delta": st["total"] - bs["total"]}
        # hand-trace: largest |delta| trade for V2 and V3
        for var in ("V2", "V3"):
            tr = run(sig, var); tm = {(x["sym"], x["date"], x["i"]): x for x in tr}
            best = max(tm, key=lambda k: abs(tm[k]["pnl"] - bmap[k]["pnl"]) if k in bmap else 0)
            x = tm[best]; b0 = bmap[best]; log = []
            bars, emas, gaps = E.DAYS[(x["sym"], x["date"])]
            sim(bars, emas, gaps, x["i"], x["entry"], x["stop"], x["det"], CJ.VW[(x["sym"], x["date"])], var, log)
            print(f"  hand-trace {var} {x['sym']} {x['date']} sig {x['t']} entry {x['entry']:.4f} stop {x['stop']:.4f}: {var} ${x['pnl']:+.2f} vs E3 ${b0['pnl']:+.2f} ({b0['exit']}) | " + " ; ".join(log))
    json.dump(out, open(HERE + "/exit_eyes_join_20260816_out.json", "w"), indent=1)

if __name__ == "__main__":
    main()
