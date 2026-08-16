#!/usr/bin/env python3
"""RUNNER SLICE 8/16 — pre-registered. Marcos: "i want the consistency but we have to hit
home runs every once in a while to help add insurance."  Analysis only.
Chain: flatten_parity_20260816.py (LIVE parity: -1% chase entry, -0.5% market-exit slip, no new
entries >= 15:30 ET, ALL flat at the 15:45 ET bar) -> S -> G -> F -> C -> B -> engine, imported
UNCHANGED. Entries = O-config (flat_top BREAK-attack 13:30-14:30Z + grinder-1030 re-attack<=3),
2-slot H1-H4 pipeline, 36 dates (pre-registered universe) AND the 62-date full cache.
EXIT variants on identical entries ($500 clip):
  S0  E3 baseline: bank 50% @ +10%, trail 50% at 10%-off-high closes-through (activates after bank).
  S1  70/30: bank 50% @ +10%, 20% on the E3 trail, 30% RUNNER on an E4 trail (never banks,
      10%-off-high from entry, closes-through), everything flat 15:45.
  S2  80/20 (bank 50 / E3-trail 30 / runner 20).   S3  60/40 (bank 50 / E3-trail 10 / runner 40).
  S4  70/30, runner trail 15%-off-high.
  S5  70/30, runner trail (10%-off-high) only ACTIVATES once high >= entry*1.20; before that the
      runner is protected only by the original stop.
Stop / halt-gap exits close every remaining leg. The slot stays occupied until the LAST leg exits
(the runner holds the slot = a real capacity cost, priced through H4).
Slice contribution per trade = trade $ under the variant minus S0 $ on the same entry (only the runner
leg differs, so this is exactly the runner's marginal $). NOTE: after the +10% bank, E3's un-banked half
already trails 10%-off-high, i.e. it IS an E4 runner; S1-S3 therefore differ from S0 only when the runner
is shaken out BEFORE the bank (E4 trail is live from entry). S4/S5 are the only variants that change the ride.
"""
import importlib.util, io, os, contextlib, json, sys, statistics
TRACE_SIGS = []
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("X", HERE + "/flatten_parity_20260816.py")
X = importlib.util.module_from_spec(spec); spec.loader.exec_module(X)
S = X.S; G = X.G; F = X.F; C = X.C; B = X.B; E = X.E
FLAT_T = X.FLAT_T; MKT = F.MKT
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

VARS = {
    "S0": dict(bank=0.50, e3=0.50, run=0.00, roff=0.10, ract=0.0),
    "S1": dict(bank=0.50, e3=0.20, run=0.30, roff=0.10, ract=0.0),
    "S2": dict(bank=0.50, e3=0.30, run=0.20, roff=0.10, ract=0.0),
    "S3": dict(bank=0.50, e3=0.10, run=0.40, roff=0.10, ract=0.0),
    "S4": dict(bank=0.50, e3=0.20, run=0.30, roff=0.15, ract=0.0),
    "S5": dict(bank=0.50, e3=0.20, run=0.30, roff=0.10, ract=0.20),
}
DESC = {"S0": "E3 baseline (bank 1/2 @+10%, trail 1/2 10%-off-high)",
        "S1": "70/30 slice, runner E4 10%-off-high", "S2": "80/20 slice", "S3": "60/40 slice",
        "S4": "70/30, runner trail 15%-off-high", "S5": "70/30, runner trail arms only after +20%"}

def sim_slice(bars, emas, gaps, entry_i, sig_px, stop, v, det, halt_rule, log=None):
    """Live-parity E3 (identical to X.sim_var_live for S0) + optional runner leg. Returns
    (pnl, exit_label, last_exit_i, runner_pnl)."""
    p = VARS[v]
    entry_px = sig_px * (1 + F.ENTRY_SLIP)
    sh = E.POS / entry_px
    bank_sh = sh * p["bank"]; e3_sh = sh * p["e3"]; run_sh = sh * p["run"]
    banked = False; e3_open = True; run_open = run_sh > 0
    target = entry_px * 1.10
    run_hi = entry_px; run_pnl = 0.0; pnl = 0.0
    e_s = E.secs(bars[entry_i])
    my_gaps = {post: pre for pre, post, g in gaps
               if halt_rule and entry_i <= pre and 0 <= E.secs(bars[pre]) - e_s <= 120}
    labels = []
    def L(m):
        if log is not None: log.append(m)
    def rem_sh():
        return (0 if banked else bank_sh) + (e3_sh if e3_open else 0) + (run_sh if run_open else 0)
    for i in range(entry_i + 1, len(bars)):
        b = bars[i]; hh = E.hhmm_b(b)
        if hh >= FLAT_T:
            px = b["c"] * (1 - MKT); r = rem_sh(); pnl += r * (px - entry_px)
            if run_open: run_pnl += run_sh * (px - entry_px)
            L(f"{hh} FLATTEN 15:45ET at {px:.4f} ({r:.1f} sh)"); return pnl, "eod1545", i, run_pnl
        if i in my_gaps and b["o"] < stop:
            px = b["o"] * (1 - MKT); r = rem_sh(); pnl += r * (px - entry_px)
            if run_open: run_pnl += run_sh * (px - entry_px)
            L(f"{hh} HALT-GAP exit at {px:.4f} ({r:.1f} sh)"); return pnl, f"haltgap@{hh}", i, run_pnl
        if b["l"] <= stop:
            px = stop * (1 - MKT); r = rem_sh(); pnl += r * (px - entry_px)
            if run_open: run_pnl += run_sh * (px - entry_px)
            L(f"{hh} STOP {stop:.4f} fill {px:.4f} (low {b['l']:.4f}) ({r:.1f} sh)")
            return pnl, f"stop@{hh}", i, run_pnl
        if not banked and b["h"] >= target:
            pnl += bank_sh * (target - entry_px); banked = True
            L(f"{hh} BANK {p['bank']:.2f} at +10% ({target:.4f})")
            continue        # same bar-skip as F.sim_var / X.sim_var_live
        run_hi = max(run_hi, b["h"])
        # E3 trail leg (only after bank)
        if e3_open and banked and b["c"] < run_hi * 0.90:
            px = b["c"] * (1 - MKT); pnl += e3_sh * (px - entry_px); e3_open = False
            L(f"{hh} TRAIL[e3 off10] close {b['c']:.4f} fill {px:.4f} ({e3_sh:.1f} sh)")
            labels.append(f"trail@{hh}")
        # runner leg
        if run_open:
            armed = run_hi >= entry_px * (1 + p["ract"]) if p["ract"] else True
            if armed and b["c"] < run_hi * (1 - p["roff"]):
                px = b["c"] * (1 - MKT); pnl += run_sh * (px - entry_px); run_pnl += run_sh * (px - entry_px)
                run_open = False
                L(f"{hh} RUNNER-TRAIL[off{int(p['roff']*100)}] close {b['c']:.4f} fill {px:.4f} hi {run_hi:.4f} ({run_sh:.1f} sh)")
                labels.append(f"rtrail@{hh}")
        if rem_sh() <= 1e-9:
            return pnl, labels[-1] if labels else f"trail@{hh}", i, run_pnl
    b = bars[-1]
    px = b["c"] * (1 - MKT); r = rem_sh(); pnl += r * (px - entry_px)
    if run_open: run_pnl += run_sh * (px - entry_px)
    L(f"{E.hhmm_b(b)} EOD exit at {px:.4f}"); return pnl, "eod", len(bars) - 1, run_pnl

def make_exec(v):
    def ex(s, halt_rule):
        bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
        pnl, exx, xi, rp = sim_slice(bars, emas, gaps, s["i"], s["entry"], s["stop"], v, s["det"], halt_rule)
        s["_run_pnl"] = rp   # stashed; pipeline copies **s into rows
        return True, pnl, exx, xi, s["i"]
    return ex

def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = fn(*a, **k)
    return r, buf.getvalue()

def s0_map(sigs):
    m = {}
    for s in sigs:
        bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
        pnl, exx, xi, _ = sim_slice(bars, emas, gaps, s["i"], s["entry"], s["stop"], "S0", s["det"], True)
        m[(s["sym"], s["date"], s["t"], s["det"])] = pnl
    return m

def bleed_streak(daily_slice, dates):
    best = cur = 0
    for d in dates:
        if daily_slice[d] < 0: cur += 1; best = max(best, cur)
        else: cur = 0
    return best

HDR = "| variant | N | day mean | day MEDIAN | green | halves $/d | worst | 5-crit | HR>=100/250/500 | slice total | premium (median vs S0) | HR$/median$ | max bleed streak |"
SEP = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"

def run_universe(tag, comb, dates):
    P(f"\n## {tag}: {len(dates)} dates {dates[0]}..{dates[-1]}, O-config signals N={len(comb)}")
    P(HDR); P(SEP)
    s0m = s0_map(comb)
    rows = {}; res_all = {}
    for v in VARS:
        p = VARS[v]
        res, _ = quiet(B.pipeline, [dict(s) for s in comb], dates, make_exec(v), f"{tag} {v}")
        h = res["h5"]; vd = res["verdict"]; ok = all(pp for _, pp in vd.values())
        h4 = res["h4"]
        # slice contribution per trade
        contribs = []; dslice = {d: 0.0 for d in dates}
        for x in h4:
            pnl0 = s0m[(x["sym"], x["date"], x["t"], x["det"])]
            c = x["pnl"] - pnl0        # slice contribution = whole-trade delta vs S0 (only the runner leg differs)
            x["_slice"] = c; x["_pnl0"] = pnl0
            contribs.append(c); dslice[x["date"]] += c
        hr = [sum(1 for c in contribs if c >= th) for th in (100, 250, 500)]
        hrd = sum(c for c in contribs if c >= 250)
        stot = sum(contribs)
        prem = rows["S0"]["median"] - h["median"] if v != "S0" else 0.0
        ratio = (hrd / prem) if prem > 0 else float("inf") if hrd > 0 else 0.0
        streak = bleed_streak(dslice, dates) if p["run"] else 0
        rows[v] = {"N": len(h4), "mean": h["mean"], "median": h["median"], "green": h["green"], "n": h["n"],
                   "h1": h["half1d"], "h2": h["half2d"], "worst": h["worst"], "pass": ok,
                   "fails": [k for k, (_, pp) in vd.items() if not pp], "hr": hr, "hr_dollars_250": hrd,
                   "slice_total": stot, "premium": prem, "ratio": ratio, "bleed_streak": streak,
                   "slice_days_neg": sum(1 for d in dates if dslice[d] < 0),
                   "slice_days_pos": sum(1 for d in dates if dslice[d] > 0),
                   "top_slices": sorted([(round(x["_slice"], 2), x["sym"], x["date"], x["t"], x["det"], round(x["pnl"], 2), round(x["_pnl0"], 2)) for x in h4], reverse=True)[:8]}
        res_all[v] = res
        rs = "inf" if ratio == float("inf") else f"{ratio:.2f}"
        P(f"| {v} {DESC[v]} | {len(h4)} | ${h['mean']:+.2f} | ${h['median']:+.2f} | {h['green']}/{h['n']} ({100*h['green']/h['n']:.0f}%) | "
          f"${h['half1d']:+.2f}/${h['half2d']:+.2f} | ${h['worst']:+.2f} | {'PASS' if ok else 'FAIL '+','.join(rows[v]['fails'])} | "
          f"{hr[0]}/{hr[1]}/{hr[2]} | ${stot:+.2f} | ${prem:+.2f}/d | {rs} | {streak}d ({rows[v]['slice_days_neg']} neg / {rows[v]['slice_days_pos']} pos days) |")
    for v in VARS:
        if v == "S0": continue
        P(f"  {v} top slice contributions (slice$, sym, date, t, det, trade$, S0$): {rows[v]['top_slices'][:5]}")
    return rows, res_all

def trace(res_all, sym, date, v):
    h4 = res_all[v]["h4"]
    xs = [x for x in h4 if x["sym"] == sym and x["date"] == date]
    if not xs:
        cand = [s for s in TRACE_SIGS if s["sym"] == sym and s["date"] == date]
        if not cand:
            P(f"  {v}: {sym} {date} has no O-config signal at all"); return None
        x = cand[0]; P(f"  ({v}: {sym} {date} not in H4 set — standalone trace of its {x['det']} signal, {len(cand)} signal(s) that day, first taken)")
    else: x = xs[0]
    bars, emas, gaps = E.DAYS[(sym, date)]
    lg = []
    pnl, exx, xi, rp = sim_slice(bars, emas, gaps, x["i"], x["entry"], x["stop"], v, x["det"], True, lg)
    entry_px = x["entry"] * (1 + F.ENTRY_SLIP); sh = E.POS / entry_px
    P(f"  {v}: {sym} {date} {x['det']} sig-bar {x['t']}Z sig {x['entry']:.4f} fill {entry_px:.4f} ({sh:.1f} sh) stop {x['stop']:.4f} -> ${pnl:+.2f} [{exx}] runner-leg ${rp:+.2f}")
    for m in lg: P("     " + m)
    return pnl

def main():
    P("# RUNNER SLICE 8/16 — exit-only variants on O-config entries (live parity: -1% chase, 15:30 cutoff, 15:45 flatten)")
    P("Reconcile target (flatten_parity NEW O-config, 36 dates): N=154 mean +$156.76 median +$130.35 green 33/36 worst -$109.55 PASS.")
    # ---- 36-date universe (same build as flatten_parity) ----
    dates, gsig, fsig, fbrk = X.build_36()
    X.set_mode(True)
    kept = X.reattack(X.cut(gsig))     # re-attack timing under S0 live-parity E3 (entries frozen across variants)
    strip = lambda kept: [{kk: s[kk] for kk in ("sym","date","det","i","t","key","entry","stop")} for s in kept]
    comb36 = sorted(strip(kept) + X.cut(fbrk), key=lambda s: (s["key"], s["sym"], s["det"]))
    R = {}
    global TRACE_SIGS; TRACE_SIGS = comb36
    R["u36"], res36 = run_universe("36-DATE UNIVERSE (pre-registered)", comb36, dates)
    s0 = R["u36"]["S0"]
    P(f"reconcile S0: N={s0['N']} mean {s0['mean']:+.2f} median {s0['median']:+.2f} green {s0['green']}/{s0['n']} worst {s0['worst']:+.2f} -> "
      f"{'OK' if (s0['N']==154 and abs(s0['mean']-156.76)<0.01 and abs(s0['median']-130.35)<0.01) else 'MISMATCH'}")
    # ---- YJ 8/07 hand-trace ----
    P("\n## Hand-trace YJ 2026-08-07 (S0 vs each slice)")
    yj = [s for s in comb36 if s["sym"] == "YJ" and s["date"] == "2026-08-07"]
    P(f"  YJ 2026-08-07 O-config signals: {[(s['det'], s['t'], round(s['entry'],4), round(s['stop'],4)) for s in yj]}; in S0 H4: {[ (x['det'],x['t']) for x in res36['S0']['h4'] if x['sym']=='YJ' and x['date']=='2026-08-07']}")
    if not yj:
        # fall back: the round-F flat_top RETEST signal (the +$1,102 trade in the F/G ledgers) — not an O-config entry, disclosed
        yj = [s for s in fsig if s["sym"] == "YJ" and s["date"] == "2026-08-07"]
        P(f"  no O-config signal -> tracing the flat_top RETEST signal(s) instead (not an O-config entry): {[(s['t'],round(s['entry'],4),round(s['stop'],4)) for s in yj]}")
        TRACE_SIGS = yj
    for v in VARS: trace(res36, "YJ", "2026-08-07", v)
    # ---- 62-date universe ----
    E.DAYS.clear()
    (nf, nd, dates62), _ = quiet(S.load_all)
    gsig62 = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in C.det_grinder_1030(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            gsig62.append({"sym": sym, "date": date, "det": "grinder", "i": t["i"], "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    fbrk62 = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in G.det_flat_top_break(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            if not ("13:30:00" <= hh <= "14:30:00"): continue
            fbrk62.append({"sym": sym, "date": date, "det": "flat_top", "i": t["i"], "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    gsig62.sort(key=lambda s: (s["key"], s["sym"], s["det"])); fbrk62.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    kept62 = X.reattack(X.cut(gsig62))
    comb62 = sorted(strip(kept62) + X.cut(fbrk62), key=lambda s: (s["key"], s["sym"], s["det"]))
    P(f"\nfull cache: {nf} files, {nd} day-files; grinder1030 sigs {len(gsig62)} (re-attack kept {len(kept62)}), BA sigs {len(fbrk62)}")
    R["u62"], res62 = run_universe("62-DATE FULL CACHE", comb62, dates62)
    X.set_mode(False)
    json.dump(R, open(HERE + "/runner_slice_20260816_out.json", "w"), indent=1, default=str)
    open(HERE + "/runner_slice_20260816_run.txt", "w").write("\n".join(OUT) + "\n")

if __name__ == "__main__":
    main()
