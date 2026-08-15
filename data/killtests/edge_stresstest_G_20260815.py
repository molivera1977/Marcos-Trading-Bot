#!/usr/bin/env python3
"""EDGE STRESS-TEST G (KEV'S AGGRESSION, PRE-REGISTERED FRESH) — run 8/14 eve, filed 20260815.
Round seven. Imports edge_stresstest_F_20260815.py (-> C -> B -> engine of record).
Same 421 in-window files, 36 dates 2026-06-25..2026-08-14, same bar: mean AND
median > +$50/day, green >= 55%, both halves positive, worst > -$300.
ALL variants use E3 exits (bank 1/2 at +10%, trail rest 10%-off-high closes-through,
stop-first, -1% chase entry slip, -0.5% market-exit slip). This round tests ENTRY
AGGRESSION under the proven exit.

TEST L — BREAK-ATTACK:
  (a) flat_top: base detection UNCHANGED (4x3min range<=12% -> level), but enter AT
      the break print (first 10s close above the base high) instead of waiting for
      the retest. Stop = base low (low of the armed 4x3min window). In-window
      13:30-14:30Z, chased, head-to-head vs the retest version under identical E3.
  (b) grinder: current spec (new SESSION high print, post-14:30Z) vs a variant
      entering on the FIRST 10s close above the prior 15-min high (earlier attack),
      same quiet-pullback filters (net_up, above VWAP, 15-min max_dd<3%), same
      900s signal cooldown, stop = lo15.

TEST M — MULTI-CHUNK (grinder): 1/2 clip ($250) chased at signal; ADD 1/2 clip
  (chased at the confirm bar close) on first subsequent 10s bar making a high
  above the ENTRY bar's high within 5 min; no confirmation -> ride the half.
  Blended cost basis, E3 exits on the combined position (bank tier re-anchored to
  the blended basis), stop = would_stop from the signal throughout. vs full-clip.

TEST N — RE-ATTACK (grinder): up to 3 entries per name per day, each a fresh
  det_grinder_1030 signal fired >= 15 min AFTER the prior attack's E3 exit.
  Baseline = one-and-done (first signal per name/day). 2nd/3rd-attack cohort
  graded on its own dollars (the marginal grade) + the combined lane.

TEST O — KEV-AGGRESSION PORTFOLIO: best-of-L flat_top arm + M's better grinder
  arm + N's re-attack lane iff its marginal cohort is positive (else one-and-done
  fallback is NOT used — status-quo gsig stays, disclosed), 2 slots, full H1-H4
  walk, H5 + 5-criterion verdict vs E3's baseline pass (mean +$94.96 / median
  +$62.09 / green 81% / halves +$81.03,+$108.90 / worst -$115.00).

Laws unchanged: bars in order, no lookahead, stop-first ties against the trade,
run_high from entry forward. Hand-trace one multi-chunk trade + one re-attack seq.
"""
import importlib.util, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("F", HERE + "/edge_stresstest_F_20260815.py")
F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
C = F.C; B = F.B; E = F.E

MKT = 0.005; SLIP = 0.01

def hhs(sec):
    return f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d}"

# ---- TEST L(a) detector: flat_top BREAK-ATTACK (enter at the break print) ----
def det_flat_top_break(bars, emas, gaps):
    trades = []; m3 = E.agg3min(bars)
    state = "seek"; level = None; base_lo = None
    open_until = -1; cooldown_until = -1
    for i, b in enumerate(bars):
        if i <= open_until: continue
        done = [x for x in m3 if x["end_t"] < b["t"]]
        if state == "seek":
            if len(done) >= 4:
                w = done[-4:]
                hi = max(x["h"] for x in w); lo = min(x["l"] for x in w)
                if lo > 0 and (hi - lo) / lo <= 0.12:
                    level = hi; base_lo = lo; state = "armed"
        if state == "armed":
            if len(done) >= 4:
                w = done[-4:]
                hi = max(x["h"] for x in w); lo = min(x["l"] for x in w)
                if lo > 0 and (hi - lo) / lo <= 0.12:
                    level = hi; base_lo = lo
            if b["c"] > level:            # THE BREAK PRINT — enter here, no retest
                if E.secs(b) < cooldown_until:
                    state = "seek"; level = None; base_lo = None; continue
                entry = b["c"]; stop = base_lo
                if stop < entry:
                    pnl, ex, xi = E.base_sim(bars, emas, gaps, i, entry, stop, "flat_top")
                    trades.append({"i": i, "entry": entry, "stop": stop})
                    open_until = xi
                    cooldown_until = E.secs(b) + 900
                state = "seek"; level = None; base_lo = None
    return trades

# ---- TEST L(b) detector: grinder EARLY-ATTACK (close above prior 15-min high) ----
def det_grinder_early(bars, emas, gaps):
    trades = []
    cv = cpv = 0.0; last_entry_s = None
    for i, b in enumerate(bars):
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cv += b["v"]; cpv += tp * b["v"]
        vw = cpv / cv if cv else b["c"]
        if E.hhmm_b(b) < "14:30:00": continue
        s = E.secs(b)
        w30 = [x for x in bars[:i + 1] if E.secs(x) >= s - 1800]
        w15 = [x for x in w30 if E.secs(x) >= s - 900]
        prior15 = [x for x in bars[:i] if E.secs(x) >= s - 900]
        if len(w30) < 2 or len(w15) < 2 or not prior15: continue
        if b["c"] <= max(x["h"] for x in prior15): continue  # first close above prior 15-min high
        net_up = b["c"] > w30[0]["c"]
        above_vwap = b["c"] > vw
        run_hi = w15[0]["h"]; max_dd = 0.0
        for x in w15:
            run_hi = max(run_hi, x["h"])
            max_dd = max(max_dd, (run_hi - x["l"]) / run_hi)
        if net_up and above_vwap and max_dd < 0.03:
            lo15 = min(x["l"] for x in w15)
            if (last_entry_s is None or s - last_entry_s > 900) and lo15 < b["c"]:
                trades.append({"i": i, "entry": b["c"], "stop": lo15})
                last_entry_s = s
    return trades

# ---- TEST M sim: multi-chunk under E3 (blended basis, add-on-confirm) ----
def sim_multichunk(bars, emas, gaps, entry_i, sig_px, stop, log=None):
    """1/2 clip chased at signal; add 1/2 (chased at confirm close) on first bar
    with high > entry bar's high within 300s; E3 exits on blended basis; stop =
    signal would_stop always. Bar order mirrors sim_var: flatten -> haltgap ->
    stop -> add -> bank -> run_hi -> trail. Grinder lane: 19:59Z flatten."""
    def L(m):
        if log is not None: log.append(m)
    e1 = sig_px * (1 + SLIP)
    sh = (E.POS / 2.0) / e1
    basis = e1; rem = sh; pnl = 0.0; scaled = False; added = False
    entry_hi = bars[entry_i]["h"]
    run_hi = e1
    target = basis * 1.10
    e_s = E.secs(bars[entry_i])
    my_gaps = {post: pre for pre, post, g in gaps
               if entry_i <= pre and 0 <= E.secs(bars[pre]) - e_s <= 120}
    L(f"{E.hhmm_b(bars[entry_i])} ENTER 1/2 clip {sh:.2f}sh at {e1:.4f} (sig {sig_px:.4f}+1%), stop {stop:.4f}, entry-bar high {entry_hi:.4f}")
    for i in range(entry_i + 1, len(bars)):
        b = bars[i]; hh = E.hhmm_b(b)
        if hh >= "19:59:00":
            px = b["c"] * (1 - MKT); pnl += rem * (px - basis)
            L(f"{hh} FLATTEN 15:59ET at {px:.4f}"); return pnl, "eod", i, added
        if i in my_gaps and b["o"] < stop:
            px = b["o"] * (1 - MKT); pnl += rem * (px - basis)
            L(f"{hh} HALT-GAP exit at {px:.4f}"); return pnl, f"haltgap@{hh}", i, added
        if b["l"] <= stop:
            px = stop * (1 - MKT); pnl += rem * (px - basis)
            L(f"{hh} STOP {stop:.4f} fill {px:.4f} (low {b['l']:.4f})")
            return pnl, f"stop@{hh}", i, added
        if (not added) and (not scaled) and E.secs(b) - e_s <= 300 and b["h"] > entry_hi:
            e2 = b["c"] * (1 + SLIP); sh2 = (E.POS / 2.0) / e2
            basis = (rem * basis + sh2 * e2) / (rem + sh2)
            rem += sh2; added = True
            target = basis * 1.10
            L(f"{hh} ADD 1/2 clip {sh2:.2f}sh at {e2:.4f} (bar high {b['h']:.4f} > {entry_hi:.4f}); blended basis {basis:.4f}, bank tier {target:.4f}")
            continue
        if not scaled and b["h"] >= target:
            bank_sh = rem / 2.0
            pnl += bank_sh * (target - basis); rem -= bank_sh; scaled = True
            L(f"{hh} BANK 1/2 at +10% ({target:.4f})")
            continue
        run_hi = max(run_hi, b["h"])
        if scaled and b["c"] < run_hi * 0.90:
            px = b["c"] * (1 - MKT); pnl += rem * (px - basis)
            L(f"{hh} TRAIL[off10] close {b['c']:.4f} (runhi {run_hi:.4f}) fill {px:.4f}")
            return pnl, f"trail@{hh}", i, added
    b = bars[-1]
    px = b["c"] * (1 - MKT); pnl += rem * (px - basis)
    L(f"{E.hhmm_b(b)} EOD exit at {px:.4f}"); return pnl, "eod", len(bars) - 1, added

def exec_mc(s, halt_rule):  # halt rule always on inside sim_multichunk (gaps prefiltered by design)
    bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
    g = gaps if halt_rule else []
    pnl, exx, xi, added = sim_multichunk(bars, emas, gaps if halt_rule else [], s["i"], s["entry"], s["stop"])
    return True, pnl, exx, xi, s["i"]

def exec_e3(s, halt_rule):
    bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
    pnl, exx, xi = F.sim_var(bars, emas, gaps, s["i"], s["entry"], s["stop"], "E3", s["det"], halt_rule)
    return True, pnl, exx, xi, s["i"]

def lane_stats(name, trades, dates):
    d = {dt: 0.0 for dt in dates}
    for x in trades: d[x["date"]] += x["pnl"]
    vals = [d[k] for k in dates]; n = len(vals); sv = sorted(vals)
    med = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
    N = len(trades)
    row = dict(N=N, win=(100 * sum(1 for x in trades if x["pnl"] > 0) / N) if N else 0.0,
               total=sum(x["pnl"] for x in trades),
               mean_tr=(sum(x["pnl"] for x in trades) / N) if N else 0.0,
               dmean=sum(vals) / n, dmed=med, worst=min(vals))
    print(f"  {name}: N={row['N']} win={row['win']:.0f}% total=${row['total']:+.2f} "
          f"mean/tr=${row['mean_tr']:+.2f} dmean=${row['dmean']:+.2f} dmed=${row['dmed']:+.2f} worst=${row['worst']:+.2f}")
    return row

def run_lane(signals, dates, exec_fn, name):
    tr = []
    for s in signals:
        _, pnl, exx, xi, fb = exec_fn(s, True)
        bars, _, _ = E.DAYS[(s["sym"], s["date"])]
        ft = E.hhmm_b(bars[fb])
        tr.append({**s, "pnl": pnl, "exit": exx, "xi": xi, "fill_t": ft,
                   "fill_key": s["date"] + "T" + ft})
    tr = F.dedup(tr)
    return lane_stats(name, tr, dates), tr

def main():
    nfiles, dates, allsig = B.gen_signals()
    print(f"FILES: {nfiles}  DATES: {len(dates)}  {dates[0]}..{dates[-1]}")

    # rebuild lanes exactly as round F
    gsig = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in C.det_grinder_1030(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            gsig.append({"sym": sym, "date": date, "det": "grinder", "i": t["i"],
                         "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    gsig.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    fsig = [s for s in allsig if s["det"] == "flat_top"]

    # aggression lanes
    fbrk = []; gearly = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in det_flat_top_break(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            if not ("13:30:00" <= hh <= "14:30:00"): continue
            fbrk.append({"sym": sym, "date": date, "det": "flat_top", "i": t["i"],
                         "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
        for t in det_grinder_early(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            gearly.append({"sym": sym, "date": date, "det": "grinder", "i": t["i"],
                          "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    fbrk.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    gearly.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    print(f"signals: grinder1030={len(gsig)} flat_top_retest={len(fsig)} "
          f"flat_top_BREAK={len(fbrk)} grinder_EARLY={len(gearly)}")

    # RECONCILE: retest flat_top + grinder solo under E3 must match round F cells
    print("\n== RECONCILE vs round F (E3 solo rows) ==")
    rowF_g, _ = run_lane(gsig, dates, exec_e3, "grinder1030 E3 (F: N=239 total=+$5,483.15)")
    rowF_f, _ = run_lane(fsig, dates, exec_e3, "flat_top retest E3 (F: N=208 total=+$1,279.62)")

    # ---- TEST L ----
    print("\n== TEST L — BREAK-ATTACK vs RETEST (all E3 exits) ==")
    rowL_fb, trL_fb = run_lane(fbrk, dates, exec_e3, "flat_top BREAK-attack")
    rowL_ge, trL_ge = run_lane(gearly, dates, exec_e3, "grinder EARLY-attack")
    tableL = {"flat_top_retest": rowF_f, "flat_top_break": rowL_fb,
              "grinder_sessionhigh": rowF_g, "grinder_early": rowL_ge}

    # ---- TEST M ----
    print("\n== TEST M — MULTI-CHUNK vs FULL-CLIP (grinder, E3 exits) ==")
    rowM_mc, trM = run_lane(gsig, dates, exec_mc, "multi-chunk (1/2 + confirm add)")
    rowM_full = rowF_g
    nadd = 0
    for s in trM:
        bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
        _, _, _, added = sim_multichunk(bars, emas, gaps, s["i"], s["entry"], s["stop"])
        if added: nadd += 1
    print(f"  confirmation adds fired: {nadd}/{len(trM)} ({100*nadd/len(trM):.0f}%) — rest rode the half")
    tableM = {"multichunk": rowM_mc, "fullclip": rowM_full, "adds": nadd}

    # ---- TEST N ----
    print("\n== TEST N — RE-ATTACK (up to 3/name/day, 15-min post-exit cooldown, E3) ==")
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
            next_ok = hhs(B.tsec(E.hhmm_b(bars[xi])) + 900)
            kept.append({**s, "attack": taken, "pnl": pnl, "exit": exx, "xi": xi,
                         "fill_t": s["t"], "fill_key": s["key"]})
    one = [x for x in kept if x["attack"] == 1]
    marg = [x for x in kept if x["attack"] >= 2]
    rowN_1 = lane_stats("one-and-done (1st attacks)", one, dates)
    rowN_m = lane_stats("MARGINAL cohort (2nd/3rd attacks)", marg, dates)
    rowN_all = lane_stats("combined re-attack lane", kept, dates)
    n2 = sum(1 for x in kept if x["attack"] == 2); n3 = sum(1 for x in kept if x["attack"] == 3)
    print(f"  attacks: 1st={len(one)} 2nd={n2} 3rd={n3}; "
          f"marginal total=${sum(x['pnl'] for x in marg):+.2f}")
    tableN = {"one_and_done": rowN_1, "marginal": rowN_m, "combined": rowN_all,
              "n2": n2, "n3": n3}

    # ---- TEST O ----
    ft_break_wins = (rowL_fb["dmed"], rowL_fb["dmean"]) > (rowF_f["dmed"], rowF_f["dmean"])
    mc_wins = (rowM_mc["dmed"], rowM_mc["dmean"]) > (rowM_full["dmed"], rowM_full["dmean"])
    marg_pos = sum(x["pnl"] for x in marg) > 0
    ft_arm = fbrk if ft_break_wins else fsig
    g_arm_sig = [ {kk: s[kk] for kk in ("sym","date","det","i","t","key","entry","stop")} for s in kept ] if marg_pos else gsig
    g_exec = exec_mc if mc_wins else exec_e3
    print(f"\n== TEST O — KEV-AGGRESSION PORTFOLIO ==")
    print(f"  arms: flat_top={'BREAK' if ft_break_wins else 'RETEST'}, "
          f"grinder exec={'MULTI-CHUNK' if mc_wins else 'FULL-CLIP'}, "
          f"grinder set={'RE-ATTACK(<=3)' if marg_pos else 'status-quo gsig'}")
    def exec_O(s, halt_rule):
        if s["det"] == "grinder": return g_exec(s, halt_rule)
        return exec_e3(s, halt_rule)
    combined = sorted(g_arm_sig + ft_arm, key=lambda s: (s["key"], s["sym"], s["det"]))
    resO = B.pipeline(combined, dates, exec_O, "PORTFOLIO O — Kev aggression, 2 slots, H1-H4, E3 exits")
    # baseline E3 (round F) portfolio re-run for a same-code head-to-head
    base_comb = sorted(gsig + fsig, key=lambda s: (s["key"], s["sym"], s["det"]))
    resBase = B.pipeline(base_comb, dates, exec_e3, "BASELINE — round F E3 portfolio (reconcile)")

    # ---- hand-traces ----
    print("\n== HAND-TRACE 1: multi-chunk (biggest multichunk winner WITH an add) ==")
    cand = []
    for s in trM:
        bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
        pnl, exx, xi, added = sim_multichunk(bars, emas, gaps, s["i"], s["entry"], s["stop"])
        if added: cand.append((pnl, s))
    cand.sort(key=lambda x: -x[0])
    tp, ts = cand[0]
    bars, emas, gaps = E.DAYS[(ts["sym"], ts["date"])]
    log1 = []
    pnl1, ex1, xi1, add1 = sim_multichunk(bars, emas, gaps, ts["i"], ts["entry"], ts["stop"], log1)
    print(f"  {ts['sym']} {ts['date']} {ts['t']} sig={ts['entry']:.4f} stop={ts['stop']:.4f} -> pnl=${pnl1:+.2f} exit={ex1}")
    for m in log1: print(f"    {m}")
    pnl1f, ex1f, _ = F.sim_var(bars, emas, gaps, ts["i"], ts["entry"], ts["stop"], "E3", "grinder", True)
    print(f"  same signal FULL-CLIP E3: pnl=${pnl1f:+.2f} exit={ex1f}")

    print("\n== HAND-TRACE 2: re-attack sequence (a name/day with >=2 attacks) ==")
    seqs = {}
    for x in kept: seqs.setdefault((x["sym"], x["date"]), []).append(x)
    multi = {k: v for k, v in seqs.items() if len(v) >= 2}
    k2 = max(multi, key=lambda k: sum(x["pnl"] for x in multi[k]))
    bars, emas, gaps = E.DAYS[k2]
    for x in sorted(multi[k2], key=lambda x: x["attack"]):
        log2 = []
        pnl2, ex2, xi2 = F.sim_var(bars, emas, gaps, x["i"], x["entry"], x["stop"], "E3", "grinder", True, log2)
        print(f"  attack #{x['attack']}: {k2[0]} {k2[1]} sig {x['t']} entry {x['entry']:.4f} stop {x['stop']:.4f} -> ${pnl2:+.2f} {ex2} (exit bar {E.hhmm_b(bars[xi2])})")
        for m in log2: print(f"    {m}")
        print(f"    next attack eligible from {hhs(B.tsec(E.hhmm_b(bars[xi2])) + 900)}")

    json.dump({"L": tableL, "M": {k: v for k, v in tableM.items()},
               "N": {k: v for k, v in tableN.items()},
               "O": {"daily": resO["daily"], "h5": resO["h5"],
                     "verdict": {c: p for c, (v, p) in resO["verdict"].items()},
                     "arms": {"flat_top": "break" if ft_break_wins else "retest",
                              "grinder_exec": "multichunk" if mc_wins else "fullclip",
                              "reattack": marg_pos}},
               "baseline": {"h5": resBase["h5"],
                            "verdict": {c: p for c, (v, p) in resBase["verdict"].items()}},
               "trace_mc": {"sig": {kk: ts[kk] for kk in ("sym","date","t")}, "pnl": pnl1, "log": log1},
               "trace_reattack": {"key": list(k2)}},
              open(HERE + "/stress_G_out.json", "w"), indent=1, default=str)
    print("\nwrote stress_G_out.json")

if __name__ == "__main__":
    main()
