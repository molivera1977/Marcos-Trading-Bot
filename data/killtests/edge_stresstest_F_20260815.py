#!/usr/bin/env python3
"""EDGE STRESS-TEST F (THE EXIT SWEEP, PRE-REGISTERED FRESH) — run 8/14 eve, filed 20260815.
Imports edge_stresstest_C_20260815.py (-> B -> engine of record). Same 36-date
window 6/25-8/14, same 421-file cache, same dollar bar: mean AND median > +$50/day,
green >= 55%, both halves positive, worst > -$300.

FIXED ENTRIES (no entry changes, both CHASED at $500, -1% entry slip):
  grinder-solo post-10:30 (round D TEST H spec = C.det_grinder_1030)
  flat_top real-retest in-window 9:30-10:30 ET (engine det_flat_top, orig window)

EXIT VARIANTS (stop always live, stop-first ties, -0.5% on ALL market exits;
+4%/+10% bank tiers are resting limits, exact):
  E1 baseline: bank 1/2 at +4%, trail rest EMA90 (control — must reconcile w/ prior rounds;
     grinder keeps breakeven-after-bank + 19:59 flatten exactly as the engine of record)
  E2 runner-first: bank 1/4 at +4%, trail 3/4 EMA90 (grinder breakeven/flatten kept)
  E3 let-it-breathe: bank 1/2 at +10%, trail rest 10%-off-high (closes-through), no breakeven
  E4 no-bank pure trail: 100% on 10%-off-high trail from entry, EOD flatten, no breakeven
  E5 breakeven-runner: bank 1/2 at +4%, stop -> breakeven, hold rest to EOD (grinder 19:59)
Trail laws: run-high updated bar-by-bar from the entry price forward, NO lookahead;
10%-off-high exits on a CLOSE below 0.90*run_high (market, -0.5%); intrabar stop first.
Grinder 19:59 flatten kept in all variants (session rule of the lane, not an exit choice).
Per-entry tables are graded post-H2(halt)+H3(dedup), NO capacity — keeps N constant
across variants (holding longer changes slot occupancy, graded only in the portfolio).
Portfolio: grinder + flat_top combined, 2 slots, full H1-H4 walk per variant.
"""
import importlib.util, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("C", HERE + "/edge_stresstest_C_20260815.py")
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
B = C.B; E = C.E

MKT = 0.005; ENTRY_SLIP = 0.01
VAR = {
    "E1": dict(bank=0.50, tgt=0.04, trail="ema",   be="grinder"),
    "E2": dict(bank=0.25, tgt=0.04, trail="ema",   be="grinder"),
    "E3": dict(bank=0.50, tgt=0.10, trail="off10", be=None),
    "E4": dict(bank=None, tgt=None, trail="off10_entry", be=None),
    "E5": dict(bank=0.50, tgt=0.04, trail=None,    be="all"),
}

def sim_var(bars, emas, gaps, entry_i, sig_px, stop, v, det, halt_rule, log=None):
    p = VAR[v]
    entry_px = sig_px * (1 + ENTRY_SLIP)
    sh = E.POS / entry_px
    rem = sh; pnl = 0.0; scaled = False
    bank_sh = sh * p["bank"] if p["bank"] else 0.0
    target = entry_px * (1 + p["tgt"]) if p["tgt"] else None
    run_hi = entry_px
    flatten = (det == "grinder")
    e_s = E.secs(bars[entry_i])
    my_gaps = {post: pre for pre, post, g in gaps
               if halt_rule and entry_i <= pre and 0 <= E.secs(bars[pre]) - e_s <= 120}
    def L(m):
        if log is not None: log.append(m)
    for i in range(entry_i + 1, len(bars)):
        b = bars[i]; hh = E.hhmm_b(b)
        if flatten and hh >= "19:59:00":
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} FLATTEN 15:59ET at {px:.4f}"); return pnl, "eod", i
        if i in my_gaps and b["o"] < stop:
            px = b["o"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} HALT-GAP exit at {px:.4f}"); return pnl, f"haltgap@{hh}", i
        if b["l"] <= stop:  # stop first — tie against the trade
            px = stop * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} STOP {stop:.4f} fill {px:.4f} (low {b['l']:.4f})")
            return pnl, f"stop@{hh}", i
        if target and not scaled and b["h"] >= target:
            pnl += bank_sh * (target - entry_px); rem -= bank_sh; scaled = True
            if p["be"] == "all" or (p["be"] == "grinder" and det == "grinder"):
                stop = max(stop, entry_px)
            L(f"{hh} BANK {p['bank']:.2f} at +{p['tgt']*100:.0f}% ({target:.4f})"
              + ("; stop->BE" if stop == entry_px else ""))
            continue
        run_hi = max(run_hi, b["h"])
        tr = p["trail"]
        hit = ((tr == "ema" and scaled and b["c"] < emas[i]) or
               (tr == "off10" and scaled and b["c"] < run_hi * 0.90) or
               (tr == "off10_entry" and b["c"] < run_hi * 0.90))
        if hit:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} TRAIL[{tr}] close {b['c']:.4f} (runhi {run_hi:.4f}, ema {emas[i]:.4f}) fill {px:.4f}")
            return pnl, f"trail@{hh}", i
    b = bars[-1]
    px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
    L(f"{E.hhmm_b(b)} EOD exit at {px:.4f}"); return pnl, "eod", len(bars) - 1

def make_exec(v):
    def ex(s, halt_rule):
        bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
        pnl, exx, xi = sim_var(bars, emas, gaps, s["i"], s["entry"], s["stop"], v, s["det"], halt_rule)
        return True, pnl, exx, xi, s["i"]
    return ex

def dedup(tr):
    tr = sorted(tr, key=lambda x: (x["fill_key"], x["det"]))
    out = []; last = {}
    for s in tr:
        k = (s["sym"], s["date"]); ss = B.tsec(s["fill_t"])
        ls = last.get(k)
        if ls is not None and ss - ls <= 300: continue
        last[k] = ss; out.append(s)
    return out

def lane_row(signals, dates, v):
    ex = make_exec(v); tr = []
    for s in signals:
        _, pnl, exx, xi, fb = ex(s, True)  # halt rule on
        bars, _, _ = E.DAYS[(s["sym"], s["date"])]
        ft = E.hhmm_b(bars[fb])
        tr.append({**s, "pnl": pnl, "exit": exx, "xi": xi, "fill_t": ft,
                   "fill_key": s["date"] + "T" + ft})
    tr = dedup(tr)
    d = {dt: 0.0 for dt in dates}
    for x in tr: d[x["date"]] += x["pnl"]
    vals = [d[k] for k in dates]; n = len(vals); sv = sorted(vals)
    med = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
    best = max(tr, key=lambda x: x["pnl"])
    row = dict(N=len(tr), win=100 * sum(1 for x in tr if x["pnl"] > 0) / len(tr),
               total=sum(x["pnl"] for x in tr), mean_tr=sum(x["pnl"] for x in tr) / len(tr),
               dmean=sum(vals) / n, dmed=med, worst=min(vals),
               best_trade=best["pnl"], best_id=f"{best['sym']} {best['date']} {best['fill_t']} {best['exit']}")
    print(f"  {v}: N={row['N']} win={row['win']:.0f}% total=${row['total']:+.2f} "
          f"mean/tr=${row['mean_tr']:+.2f} dmean=${row['dmean']:+.2f} dmed=${row['dmed']:+.2f} "
          f"worst=${row['worst']:+.2f} besttrade=${row['best_trade']:+.2f} ({row['best_id']})")
    return row

def main():
    nfiles, dates, allsig = B.gen_signals()
    print(f"FILES: {nfiles}  DATES: {len(dates)}  {dates[0]}..{dates[-1]}")
    # entry 1: grinder-1030 solo (D TEST H spec)
    gsig = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in C.det_grinder_1030(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            gsig.append({"sym": sym, "date": date, "det": "grinder", "i": t["i"],
                         "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    gsig.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    # entry 2: flat_top in-window (orig 13:30-14:30Z), chased
    fsig = [s for s in allsig if s["det"] == "flat_top"]
    print(f"signals: grinder1030={len(gsig)}  flat_top(in-window)={len(fsig)}")

    # RECONCILE: grinder solo E1 through the FULL prior pipeline must match D TEST H(i)
    resRec = B.pipeline(gsig, dates, make_exec("E1"), "RECONCILE — grinder-1030 solo, E1, full H1-H4 (vs D H(i))")
    tot = sum(resRec["daily"].values())
    print(f"  RECONCILE CHECK: N={len(resRec['h4'])} total=${tot:+.2f}  (D H(i): N=143 total=+$1,707.20)")

    # per-entry x variant tables (post-H2+H3, no capacity — N constant)
    tables = {}
    for name, sig in (("grinder1030", gsig), ("flat_top", fsig)):
        print(f"\n== {name} x exit variants (H2 halt + H3 dedup, no capacity) ==")
        tables[name] = {v: lane_row(sig, dates, v) for v in VAR}

    # combined portfolio per variant: 2 slots, full walk
    combined = sorted(gsig + fsig, key=lambda s: (s["key"], s["sym"], s["det"]))
    port = {}
    for v in VAR:
        port[v] = B.pipeline(combined, dates, make_exec(v),
                             f"PORTFOLIO {v} — grinder1030 + flat_top, 2 slots, H1-H4")
    npass = {v: sum(1 for _, p in port[v]["verdict"].values() if p) for v in VAR}
    best_v = max(VAR, key=lambda v: (npass[v], port[v]["h5"]["median"], port[v]["h5"]["mean"]))
    print("\nPASS COUNTS:", npass, " BEST:", best_v,
          " ALL-5:", [v for v in VAR if npass[v] == 5] or "NONE")

    # hand-trace: YJ 8/07 grinder if it signals, else biggest E4 portfolio winner
    cand = [s for s in gsig if s["sym"] == "YJ" and s["date"] == "2026-08-07"]
    if cand:
        tsig = cand[0]; why = "YJ 2026-08-07 grinder (requested)"
    else:
        h4 = port["E4"]["h4"]
        big = max(h4, key=lambda x: x["pnl"])
        tsig = next(s for s in (gsig + fsig)
                    if (s["sym"], s["date"], s["i"], s["det"]) == (big["sym"], big["date"], big["i"], big["det"]))
        why = f"biggest E4 winner {big['sym']} {big['date']} ({big['det']})"
    print(f"\n== HAND-TRACE: {why} — sym={tsig['sym']} date={tsig['date']} t={tsig['t']} "
          f"sig_px={tsig['entry']:.4f} stop={tsig['stop']:.4f} det={tsig['det']} ==")
    bars, emas, gaps = E.DAYS[(tsig["sym"], tsig["date"])]
    trace = {}
    for v in VAR:
        log = []
        pnl, exx, xi = sim_var(bars, emas, gaps, tsig["i"], tsig["entry"], tsig["stop"],
                               v, tsig["det"], True, log)
        trace[v] = {"pnl": pnl, "exit": exx, "log": log}
        print(f"  {v}: pnl=${pnl:+.2f} exit={exx}")
        for m in log: print(f"     {m}")

    json.dump({"tables": tables,
               "portfolio": {v: {"daily": port[v]["daily"], "h5": port[v]["h5"],
                                 "verdict": {c: p for c, (val, p) in port[v]["verdict"].items()}}
                             for v in VAR},
               "npass": npass, "best": best_v, "trace_sig": {k: tsig[k] for k in ("sym", "date", "t", "det")},
               "trace": trace},
              open(HERE + "/stress_F_out.json", "w"), indent=1, default=str)
    print("\nwrote stress_F_out.json")

if __name__ == "__main__":
    main()
