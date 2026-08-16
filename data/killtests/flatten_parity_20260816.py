#!/usr/bin/env python3
"""FLATTEN PARITY 8/16 (X1 from EYES_MATRIX_20260816.md) — Wind Tunnel.
LIVE rule (marcos_trading_bot.py :513-517, :7190, :9495): no NEW entries at/after 15:30 ET;
ALL positions force-closed at/after 15:45 ET. The sim chain (F.sim_var) flattened grinder at
19:59Z (15:59 ET) and other lanes at the last RTH bar. This script re-runs the SAME chain
(G -> F -> C -> B -> engine, imported unchanged) with F.sim_var monkey-patched so EVERY lane
flattens on the first bar with t >= 19:44:50Z (the 10s bar completing at 15:45:00 ET; fill =
close x (1-0.5%)), and signals at/after 19:30:00Z (15:30 ET) are dropped as new entries.
OLD = original F.sim_var, same code path, run first and reconciled to round G to the cent.
Configs: (1) round F E3 baseline portfolio (grinder1030 + flat_top retest, 2-slot H1-H4),
(2) round G O-config (BA in-window + grinder re-attack<=3, 2-slot), (3) Sunday T5 ORB 15-min
ORL (solo + 2-slot, 62 dates), (4) grinder-1030 solo (36 dates). Analysis only.
"""
import importlib.util, io, os, contextlib, json, sys
HERE = os.path.dirname(os.path.abspath(__file__))
spec2 = importlib.util.spec_from_file_location("S", HERE + "/sunday_afternoon_studies_20260816.py")
S = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(S)
G = S.G; F = G.F; C = G.C; B = G.B; E = G.E   # ONE chain instance (S -> G -> F -> C -> B -> E)

FLAT_T = "19:44:50"      # 10s bar completing at 15:45:00 ET
CUTOFF_T = "19:30:00"    # no new entries at/after 15:30 ET
MKT = F.MKT
ORIG_SIM = F.sim_var
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

def sim_var_live(bars, emas, gaps, entry_i, sig_px, stop, v, det, halt_rule, log=None):
    """Identical to F.sim_var except: ALL lanes flatten at first bar >= FLAT_T (was grinder@19:59)."""
    p = F.VAR[v]
    entry_px = sig_px * (1 + F.ENTRY_SLIP)
    sh = E.POS / entry_px
    rem = sh; pnl = 0.0; scaled = False
    bank_sh = sh * p["bank"] if p["bank"] else 0.0
    target = entry_px * (1 + p["tgt"]) if p["tgt"] else None
    run_hi = entry_px
    e_s = E.secs(bars[entry_i])
    my_gaps = {post: pre for pre, post, g in gaps
               if halt_rule and entry_i <= pre and 0 <= E.secs(bars[pre]) - e_s <= 120}
    def L(m):
        if log is not None: log.append(m)
    for i in range(entry_i + 1, len(bars)):
        b = bars[i]; hh = E.hhmm_b(b)
        if hh >= FLAT_T:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} FLATTEN 15:45ET at {px:.4f}"); return pnl, "eod1545", i
        if i in my_gaps and b["o"] < stop:
            px = b["o"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} HALT-GAP exit at {px:.4f}"); return pnl, f"haltgap@{hh}", i
        if b["l"] <= stop:
            px = stop * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} STOP {stop:.4f} fill {px:.4f} (low {b['l']:.4f})")
            return pnl, f"stop@{hh}", i
        if target and not scaled and b["h"] >= target:
            pnl += bank_sh * (target - entry_px); rem -= bank_sh; scaled = True
            if p["be"] == "all" or (p["be"] == "grinder" and det == "grinder"):
                stop = max(stop, entry_px)
            L(f"{hh} BANK {p['bank']:.2f} at +{p['tgt']*100:.0f}% ({target:.4f})")
            continue
        run_hi = max(run_hi, b["h"])
        tr = p["trail"]
        hit = ((tr == "ema" and scaled and b["c"] < emas[i]) or
               (tr == "off10" and scaled and b["c"] < run_hi * 0.90) or
               (tr == "off10_entry" and b["c"] < run_hi * 0.90))
        if hit:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} TRAIL[{tr}] close {b['c']:.4f} fill {px:.4f}")
            return pnl, f"trail@{hh}", i
    b = bars[-1]
    px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
    L(f"{E.hhmm_b(b)} EOD exit at {px:.4f}"); return pnl, "eod", len(bars) - 1

def set_mode(live):
    F.sim_var = sim_var_live if live else ORIG_SIM

def cut(sigs):
    return [s for s in sigs if s["t"] < CUTOFF_T]

def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = fn(*a, **k)
    return r, buf.getvalue()

def solo_row(name, tr, dates):
    return S.stats(name, tr, dates, bar=True)

def port_row(name, res):
    h = res["h5"]; v = res["verdict"]
    ok = all(p for _, p in v.values())
    P(f"| {name} | {len(res['h4'])} | ${h['mean']:+.2f} | ${h['median']:+.2f} | {h['green']}/{h['n']} ({100*h['green']/h['n']:.0f}%) | "
      f"${h['half1d']:+.2f}/${h['half2d']:+.2f} | ${h['worst']:+.2f} | {'PASS' if ok else 'FAIL'} "
      f"[{','.join(k for k,(_,p) in v.items() if not p) or 'all 5'}] |")
    return {"N": len(res["h4"]), "mean": h["mean"], "median": h["median"], "green": h["green"], "n": h["n"],
            "h1": h["half1d"], "h2": h["half2d"], "worst": h["worst"], "pass": ok,
            "fails": [k for k, (_, p) in v.items() if not p], "nskip": h["nskip"]}

def open_at_1545(tr_old):
    """Trades whose OLD exit bar is at/after FLAT_T = were open at 15:45 (the affected cohort)."""
    out = []
    for x in tr_old:
        bars = E.DAYS[(x["sym"], x["date"])][0]
        if E.hhmm_b(bars[min(x["xi"], len(bars) - 1)]) >= FLAT_T: out.append(x)
    return out

def cohort_report(name, tr_old, tr_new):
    old_open = open_at_1545(tr_old)
    newmap = {(x["sym"], x["date"], x["t"]): x for x in tr_new}
    old_p = sum(x["pnl"] for x in old_open)
    new_p = 0.0; matched = 0; missing = 0
    for x in old_open:
        y = newmap.get((x["sym"], x["date"], x["t"]))
        if y is None: missing += 1; continue
        matched += 1; new_p += y["pnl"]
    late = sum(1 for x in tr_old if x["t"] >= CUTOFF_T)
    P(f"  {name}: open@15:45 cohort N={len(old_open)} (of {len(tr_old)}); OLD ${old_p:+.2f} -> NEW ${new_p:+.2f} "
      f"(delta ${new_p-old_p:+.2f}; {matched} matched, {missing} not in NEW set e.g. dropped by 15:30 cutoff/slot walk); "
      f"OLD trades entered >=15:30 ET: {late}")
    return {"n_open": len(old_open), "old": old_p, "new": new_p, "late": late, "missing": missing}

PORT_HDR = "| config | N | day mean | day median | green | halves $/d | worst | verdict [fails] |"
PORT_SEP = "|---|---|---|---|---|---|---|---|"

def build_36():
    (nfiles, dates, allsig), _ = quiet(B.gen_signals)
    gsig = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in C.det_grinder_1030(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            gsig.append({"sym": sym, "date": date, "det": "grinder", "i": t["i"],
                         "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    gsig.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    fsig = [s for s in allsig if s["det"] == "flat_top"]
    fbrk = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in G.det_flat_top_break(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            if not ("13:30:00" <= hh <= "14:30:00"): continue
            fbrk.append({"sym": sym, "date": date, "det": "flat_top", "i": t["i"],
                         "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    fbrk.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    return dates, gsig, fsig, fbrk

def reattack(gsig):
    """G TEST N re-attack set (<=3/name/day, 15-min cooldown) under the CURRENT F.sim_var."""
    by = {}
    for s in gsig: by.setdefault((s["sym"], s["date"]), []).append(s)
    kept = []
    for k in sorted(by):
        ss = sorted(by[k], key=lambda s: s["t"])
        taken = 0; next_ok = None
        for s in ss:
            if taken >= 3: break
            if next_ok is not None and s["t"] < next_ok: continue
            bars, emas, gaps = E.DAYS[k]
            pnl, exx, xi = F.sim_var(bars, emas, gaps, s["i"], s["entry"], s["stop"], "E3", "grinder", True)
            taken += 1
            next_ok = G.hhs(B.tsec(E.hhmm_b(bars[xi])) + 900)
            kept.append({**s, "attack": taken, "pnl": pnl, "exit": exx, "xi": xi,
                         "fill_t": s["t"], "fill_key": s["key"]})
    return kept

def main():
    P("# FLATTEN PARITY 8/16 — X1: sim 15:59/last-bar flatten vs LIVE 15:45 flatten + 15:30 entry cutoff")
    P(f"LIVE rule read this run: marcos_trading_bot.py :513-517 VWAP_ENTRY_TIMEOUT=15:30 (no new entries, :7190/:11145/:12416-12448), TRADE_WINDOW_END=15:45 (force close all, :9495). Sim NEW = flatten first bar >= {FLAT_T}Z close, drop signals >= {CUTOFF_T}Z.")
    dates, gsig, fsig, fbrk = build_36()
    P(f"36-date universe: {len(dates)} dates {dates[0]}..{dates[-1]}; signals grinder1030={len(gsig)} flat_top_retest={len(fsig)} BA={len(fbrk)}")
    P(f"signals at/after 15:30 ET (dropped in NEW): grinder {sum(1 for s in gsig if s['t']>=CUTOFF_T)}, retest {sum(1 for s in fsig if s['t']>=CUTOFF_T)}, BA {sum(1 for s in fbrk if s['t']>=CUTOFF_T)}")
    R = {}

    # ---- solo lanes (36 dates) OLD vs NEW ----
    P("\n## Solo lanes, 36 dates (dedup, no capacity) — E3")
    P(S.HDR); P(S.SEP)
    solo = {}
    for nm, sigs in (("grinder1030", gsig), ("flat_top retest", fsig), ("flat_top BREAK-attack", fbrk)):
        set_mode(False); tro = S.run(sigs)
        set_mode(True); trn = S.run(cut(sigs))
        ro = solo_row(f"OLD {nm}", tro, dates); rn = solo_row(f"NEW {nm}", trn, dates)
        solo[nm] = (ro, rn, tro, trn)
    P("reconcile: OLD grinder1030 must be N=239 +$5,483.15; OLD BA N=384 +$9,220.01; OLD retest N=208 +$1,279.62")
    P("affected cohorts:")
    for nm, (ro, rn, tro, trn) in solo.items():
        R["solo_" + nm] = {"old": ro, "new": rn, "cohort": cohort_report(nm, tro, trn)}

    # ---- portfolios (36 dates) ----
    P("\n## Portfolios, 36 dates, 2-slot H1-H4 (B.pipeline)")
    P(PORT_HDR); P(PORT_SEP)
    # (1) round F E3 baseline
    base_comb = sorted(gsig + fsig, key=lambda s: (s["key"], s["sym"], s["det"]))
    set_mode(False); resBo, _ = quiet(B.pipeline, base_comb, dates, G.exec_e3, "base OLD")
    set_mode(True); resBn, _ = quiet(B.pipeline, cut(base_comb), dates, G.exec_e3, "base NEW")
    R["baseF"] = {"old": port_row("OLD round-F E3 baseline (grinder1030+retest)", resBo),
                  "new": port_row("NEW round-F E3 baseline (15:45 flat, 15:30 cut)", resBn)}
    # (2) O-config: BA + grinder re-attack, both E3 full-clip
    set_mode(False); kept_o = reattack(gsig)
    set_mode(True); kept_n = reattack(cut(gsig))
    strip = lambda kept: [{kk: s[kk] for kk in ("sym","date","det","i","t","key","entry","stop")} for s in kept]
    combO = sorted(strip(kept_o) + fbrk, key=lambda s: (s["key"], s["sym"], s["det"]))
    combN = sorted(strip(kept_n) + cut(fbrk), key=lambda s: (s["key"], s["sym"], s["det"]))
    set_mode(False); resOo, _ = quiet(B.pipeline, combO, dates, G.exec_e3, "O OLD")
    set_mode(True); resOn, _ = quiet(B.pipeline, combN, dates, G.exec_e3, "O NEW")
    R["O"] = {"old": port_row("OLD round-G O-config (BA+grinder re-attack)", resOo),
              "new": port_row("NEW round-G O-config (15:45 flat, 15:30 cut)", resOn)}
    P("reconcile: OLD O-config must be N=156 mean +$156.64 median +$134.44 green 32/36 worst -$109.55; OLD baseline N=238 mean +$94.96 median +$62.09")
    P("portfolio affected cohorts (H4 trades open at 15:45 in OLD):")
    R["baseF"]["cohort"] = cohort_report("round-F baseline H4", resBo["h4"], resBn["h4"])
    R["O"]["cohort"] = cohort_report("O-config H4", resOo["h4"], resOn["h4"])
    # per-lane split inside O
    for det in ("flat_top", "grinder"):
        oo = [x for x in resOo["h4"] if x["det"] == det]; nn = [x for x in resOn["h4"] if x["det"] == det]
        P(f"  O-config {det}: OLD N={len(oo)} ${sum(x['pnl'] for x in oo):+.2f} -> NEW N={len(nn)} ${sum(x['pnl'] for x in nn):+.2f}")

    # ---- (3) ORB 15-min ORL, 62 dates (Sunday full cache) ----
    P("\n## ORB 15-min ORL (Sunday T5), full cache")
    E.DAYS.clear()
    (nf, nd, dates62), _ = quiet(S.load_all)
    P(f"full cache: {nf} files, {nd} day-files, {len(dates62)} dates {dates62[0]}..{dates62[-1]}")
    # rebuild Sunday's orb() closure logic (verbatim copy of T5 signal gen)
    def orb(minutes, stop_mode):
        sigs = []
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
                    stop = orl if stop_mode == "orl" else (orh + orl) / 2
                    if stop < m["c"]:
                        sigs.append(S.mk(k[0], k[1], "orb", m["i"], m["c"], stop))
                    break
        return sigs
    osig = orb(15, "orl")
    P(S.HDR); P(S.SEP)
    set_mode(False); tro = S.run(osig)
    set_mode(True); trn = S.run(cut(osig))
    ro = solo_row("OLD ORB 15-min ORL solo", tro, dates62); rn = solo_row("NEW ORB 15-min ORL solo", trn, dates62)
    P("reconcile: OLD ORB 15-min ORL solo must be N=371 +$12,114.57 mean +$195.40 median +$145.30")
    R["orb_solo"] = {"old": ro, "new": rn, "cohort": cohort_report("ORB15 solo", tro, trn)}
    def ex_orb(s, halt_rule):
        bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
        pnl, exx, xi = F.sim_var(bars, emas, gaps, s["i"], s["entry"], s["stop"], "E3", "orb", halt_rule)
        return True, pnl, exx, xi, s["i"]
    P(PORT_HDR); P(PORT_SEP)
    set_mode(False); rpo, _ = quiet(B.pipeline, sorted(osig, key=lambda s: (s["key"], s["sym"])), dates62, ex_orb, "orb OLD")
    set_mode(True); rpn, _ = quiet(B.pipeline, sorted(cut(osig), key=lambda s: (s["key"], s["sym"])), dates62, ex_orb, "orb NEW")
    R["orb_port"] = {"old": port_row("OLD ORB 15-min ORL 2-slot", rpo), "new": port_row("NEW ORB 15-min ORL 2-slot", rpn)}
    P("reconcile: OLD ORB 15-min 2-slot must be N=180 mean +$114.59 median +$125.57 green 46/62 worst -$174.35")
    R["orb_port"]["cohort"] = cohort_report("ORB15 2-slot H4", rpo["h4"], rpn["h4"])

    # hand-trace: largest |delta| trade in the O-config affected cohort
    E.DAYS.clear(); quiet(B.gen_signals)
    P("\n## Hand-trace (largest |old-new| among O-config H4 trades open at 15:45)")
    newmap = {(x["sym"], x["date"], x["t"]): x for x in resOn["h4"]}
    cand = []
    for x in open_at_1545(resOo["h4"]):
        y = newmap.get((x["sym"], x["date"], x["t"]))
        if y: cand.append((abs(x["pnl"] - y["pnl"]), x, y))
    if cand:
        _, x, y = max(cand, key=lambda z: z[0])
        bars, emas, gaps = E.DAYS[(x["sym"], x["date"])]
        lo = []; ORIG_SIM(bars, emas, gaps, x["i"], x["entry"], x["stop"], "E3", x["det"], True, lo)
        ln = []; sim_var_live(bars, emas, gaps, x["i"], x["entry"], x["stop"], "E3", x["det"], True, ln)
        P(f"{x['sym']} {x['date']} {x['det']} entry-bar {x['t']}Z sig {x['entry']:.4f} stop {x['stop']:.4f}: OLD ${x['pnl']:+.2f} {x['exit']} | NEW ${y['pnl']:+.2f} {y['exit']}")
        for m in lo: P("   OLD " + m)
        for m in ln: P("   NEW " + m)
    set_mode(False)
    json.dump(R, open(HERE + "/flatten_parity_20260816_out.json", "w"), indent=1, default=str)
    open(HERE + "/flatten_parity_20260816_run.txt", "w").write("\n".join(OUT) + "\n")

if __name__ == "__main__":
    main()
