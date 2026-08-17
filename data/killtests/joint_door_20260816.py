#!/usr/bin/env python3
"""JOINT DOOR TEST 8/16 — Kev fingerprint (FIELD FILTER on all 729 name-days) x his window
x pullback entries x runner exits, as ONE system. Analysis only.
Engine chain: X(flatten_parity, live-parity 15:45 flatten) -> S -> G -> F -> C -> B -> E, imported
UNCHANGED. Exits E3/E4/E4W/S5 implemented in ONE local sim (sim_x) that is reconciled to the
cent against X.sim_var_live for E3 on every RTH trade it runs (assert), so live-parity holds.
Fingerprint proxy (NBBO not cached for the stamp windows): median 10s bar range/close (bps) over
the prior 30 min = spread proxy (<=80 bps), median 1-min range/close (bps) = calm (X calibrated
to a ~30/70 split), plus day gain >= +20% (ref = first bar of the file, 04:00 ET open; the cache
carries no prior close — disclosed). Stamps: 09:30 ET (13:30Z) and 08:00 ET (12:00Z).
"""
import importlib.util, io, os, contextlib, json, glob, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("X", HERE + "/flatten_parity_20260816.py")
X = importlib.util.module_from_spec(spec); spec.loader.exec_module(X)
S = X.S; G = X.G; F = X.F; C = X.C; B = X.B; E = X.E
MKT = F.MKT; SLIP = F.ENTRY_SLIP; POS = E.POS
FLAT_RTH = X.FLAT_T            # 19:44:50Z = 15:45 ET
CUT_RTH = X.CUTOFF_T
FLAT_PRE = "13:24:50"          # 09:25 ET premarket flatten
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)
def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = fn(*a, **k)
    return r
def med(v): return statistics.median(v) if v else float("nan")

# ---------------- LOAD full cache (729 name-days) ----------------
FULL = {}
def load_all():
    files = sorted(glob.glob(E.BARS_DIR + "/*.json"))
    for f in files:
        sym, date, bars = E.load(f)
        if not bars: continue
        FULL[(sym, date)] = bars
        rb = E.rth(bars)
        if len(rb) < 60: continue
        E.DAYS[(sym, date)] = (rb, E.ema_series([b["c"] for b in rb], 90), E.find_gaps(rb))
    return len(files)

# ---------------- LAYER 1: fingerprint ----------------
def window_stats(bars, t0, t1):
    w = [b for b in bars if t0 <= E.hhmm_b(b) < t1 and b["v"] > 0 and b["c"] > 0]
    if len(w) < 10: return None
    spread = med([(b["h"] - b["l"]) / b["c"] * 1e4 for b in w])
    mins = {}
    for b in w:
        k = E.hhmm_b(b)[:5]
        m = mins.setdefault(k, [b["h"], b["l"], b["c"]])
        m[0] = max(m[0], b["h"]); m[1] = min(m[1], b["l"]); m[2] = b["c"]
    calm = med([(h - l) / c * 1e4 for h, l, c in mins.values()])
    return {"spread": spread, "calm": calm, "nbars": len(w), "nmin": len(mins)}

def stamp(bars, at, ref):
    """at = 'HH:MM:SS' Z. Prior 30 min window, gain = last close before `at` vs ref."""
    t0 = G.hhs(B.tsec(at) - 1800)
    ws = window_stats(bars, t0, at)
    prev = [b for b in bars if E.hhmm_b(b) < at]
    gain = (prev[-1]["c"] / ref - 1) if prev and ref > 0 else None
    return {"win": ws, "gain": gain}

FP = {}   # (sym,date) -> stamp dict
def fingerprint_all():
    for k, bars in FULL.items():
        ref = bars[0]["o"]
        FP[k] = {"s930": stamp(bars, "13:30:00", ref), "s800": stamp(bars, "12:00:00", ref), "ref": ref}

def calibrate_calm():
    v = [FP[k]["s930"]["win"]["calm"] for k in FP if FP[k]["s930"]["win"]]
    v.sort()
    return v[int(0.30 * len(v))], len(v)

DEFS = {"A_spec": "spread<=80 & calm<=X & gain>=20% (the pre-registered spec)",
        "B_tape": "spread<=80 & calm<=X, no gain clause (tape-character only, ~30% bucket)",
        "C_liquid_runner": "spread<=80 & gain>=20%, no calm clause"}
def passes(k, calmX, which, d="A_spec"):
    st = FP[k]["s930" if which == "930" else "s800"]
    w = st["win"]
    if not w or st["gain"] is None: return False
    sp = w["spread"] <= 80; cm = w["calm"] <= calmX; gn = st["gain"] >= 0.20
    return {"A_spec": sp and cm and gn, "B_tape": sp and cm, "C_liquid_runner": sp and gn}[d]

def kev_shaped(k, calmX, d="A_spec"): return passes(k, calmX, "930", d) or passes(k, calmX, "800", d)

# ---------------- ONE sim: E3 / E4 / E4W / S5, live-parity flatten ----------------
def sim_x(bars, emas, gaps, entry_i, sig_px, stop, v, flat_t, log=None):
    """E3: bank 1/2 @+10%, trail rest 10%-off-high (armed after bank).
       E4: never-bank, trail 10%-off-high from entry.  E4W: never-bank, 20%-off-high.
       S5: bank 1/2 @+10%; 20% leg trails 10%-off-high after bank; 30% runner trails 10%-off-high
           only after high >= +20% (stop-only until then). Halt-gap rule ON. Flatten at flat_t."""
    entry_px = sig_px * (1 + SLIP); sh = POS / entry_px
    legs = {"E3": [(0.5, "bank"), (0.5, "t10_after")],
            "E4": [(1.0, "t10")], "E4W": [(1.0, "t20")],
            "S5": [(0.5, "bank"), (0.2, "t10_after"), (0.3, "t10_arm20")]}[v]
    open_ = {j: sh * f for j, (f, _) in enumerate(legs)}
    kind = {j: kk for j, (_, kk) in enumerate(legs)}
    pnl = 0.0; banked = False; run_hi = entry_px; target = entry_px * 1.10
    e_s = E.secs(bars[entry_i])
    my_gaps = {post: pre for pre, post, g in gaps if entry_i <= pre and 0 <= E.secs(bars[pre]) - e_s <= 120}
    def L(m):
        if log is not None: log.append(m)
    def out_all(px, why, i):
        nonlocal pnl
        r = sum(open_.values()); pnl += r * (px - entry_px); open_.clear()
        L(f"{E.hhmm_b(bars[i])} {why} fill {px:.4f} ({r:.1f} sh)")
    for i in range(entry_i + 1, len(bars)):
        b = bars[i]; hh = E.hhmm_b(b)
        if hh >= flat_t:
            out_all(b["c"] * (1 - MKT), "FLATTEN", i); return pnl, "flat", i
        if i in my_gaps and b["o"] < stop:
            out_all(b["o"] * (1 - MKT), "HALT-GAP", i); return pnl, f"haltgap@{hh}", i
        if b["l"] <= stop:
            out_all(stop * (1 - MKT), f"STOP {stop:.4f} (low {b['l']:.4f})", i); return pnl, f"stop@{hh}", i
        if not banked and any(kind[j] == "bank" for j in open_) and b["h"] >= target:
            for j in list(open_):
                if kind[j] == "bank":
                    pnl += open_[j] * (target - entry_px); del open_[j]
            banked = True; L(f"{hh} BANK 1/2 at +10% ({target:.4f})"); continue
        run_hi = max(run_hi, b["h"])
        for j in list(open_):
            kk = kind[j]
            hit = ((kk == "t10" and b["c"] < run_hi * 0.90) or
                   (kk == "t20" and b["c"] < run_hi * 0.80) or
                   (kk == "t10_after" and banked and b["c"] < run_hi * 0.90) or
                   (kk == "t10_arm20" and run_hi >= entry_px * 1.20 and b["c"] < run_hi * 0.90))
            if hit:
                px = b["c"] * (1 - MKT); pnl += open_[j] * (px - entry_px)
                L(f"{hh} TRAIL[{kk}] close {b['c']:.4f} fill {px:.4f} hi {run_hi:.4f} ({open_[j]:.1f} sh)"); del open_[j]
        if not open_: return pnl, f"trail@{hh}", i
    b = bars[-1]; out_all(b["c"] * (1 - MKT), "EOD", len(bars) - 1); return pnl, "eod", len(bars) - 1

RECON = {"n": 0, "maxdiff": 0.0}
def sim_rth(sym, date, i, entry, stop, v, log=None):
    bars, emas, gaps = E.DAYS[(sym, date)]
    pnl, ex, xi = sim_x(bars, emas, gaps, i, entry, stop, v, FLAT_RTH, log)
    if v == "E3":   # reconcile against the chain's live-parity engine, to the cent
        p2, _, xi2 = X.sim_var_live(bars, emas, gaps, i, entry, stop, "E3", "x", True)
        RECON["n"] += 1; RECON["maxdiff"] = max(RECON["maxdiff"], abs(p2 - pnl))
        assert abs(p2 - pnl) < 0.005 and xi2 == xi, (sym, date, i, pnl, p2)
    return pnl, ex, xi

PRE = {}   # (sym,date) -> (bars 11:00-13:25Z, emas, gaps)
def pre_slice(k):
    if k not in PRE:
        bb = [b for b in FULL[k] if "11:00:00" <= E.hhmm_b(b) < "13:25:00"]
        PRE[k] = (bb, E.ema_series([b["c"] for b in bb], 90), E.find_gaps(bb))
    return PRE[k]

# ---------------- LAYER 3: entries ----------------
def gen_entries():
    """Signals per name-day: v2cal (B.det_v2_cal, C1-C5), bandpass (S.det_vwap_ann, bars_below>=2),
    pre_reclaim (same det on the 07:00-09:25 ET slice, VWAP anchored 07:00), BA (G.det_flat_top_break)."""
    sigs = []
    for k, (bars, emas, gaps) in E.DAYS.items():
        sym, date = k
        for t in B.det_v2_cal(bars, emas, gaps):
            sigs.append(dict(sym=sym, date=date, det="v2cal", i=t["i"], t=E.hhmm_b(bars[t["i"]]), entry=t["entry"], stop=t["stop"]))
        for t in S.det_vwap_ann(bars, emas, gaps):
            if t["bars_below"] >= 2:
                sigs.append(dict(sym=sym, date=date, det="bandpass", i=t["i"], t=E.hhmm_b(bars[t["i"]]), entry=t["entry"], stop=t["stop"]))
        for t in G.det_flat_top_break(bars, emas, gaps):
            sigs.append(dict(sym=sym, date=date, det="BA", i=t["i"], t=E.hhmm_b(bars[t["i"]]), entry=t["entry"], stop=t["stop"]))
    for k in FULL:
        pb, pe, pg = pre_slice(k)
        if len(pb) < 60: continue
        for t in S.det_vwap_ann(pb, pe, pg):
            if t["bars_below"] >= 2:
                sigs.append(dict(sym=k[0], date=k[1], det="pre_reclaim", i=t["i"], t=E.hhmm_b(pb[t["i"]]), entry=t["entry"], stop=t["stop"]))
    for s in sigs: s["key"] = s["date"] + "T" + s["t"]
    sigs.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    return sigs

WINDOWS = {"W1 07:00-10:00": ("11:00:00", "14:00:00"), "W2 09:30-10:30": ("13:30:00", "14:30:00")}
def in_win(s, wn):
    a, b = WINDOWS[wn]
    if s["det"] == "pre_reclaim": return wn.startswith("W1")
    return a <= s["t"] < b

def run_cell(sigs, v):
    tr = []
    for s in sigs:
        if s["det"] == "pre_reclaim":
            pb, pe, pg = pre_slice((s["sym"], s["date"]))
            pnl, ex, xi = sim_x(pb, pe, pg, s["i"], s["entry"], s["stop"], v, FLAT_PRE)
        else:
            pnl, ex, xi = sim_rth(s["sym"], s["date"], s["i"], s["entry"], s["stop"], v)
        tr.append({**s, "pnl": pnl, "exit": ex, "xi": xi, "fill_t": s["t"], "fill_key": s["key"]})
    return F.dedup(tr)

# ---------------- grading ----------------
def grade(tr, dates):
    d = {dt: 0.0 for dt in dates}
    for x in tr: d[x["date"]] += x["pnl"]
    vals = [d[k] for k in dates]; n = len(vals); N = len(tr)
    tot = sum(x["pnl"] for x in tr)
    mid = dates[n // 2]
    h1 = sum(d[k] for k in dates if k < mid); h2 = sum(d[k] for k in dates if k >= mid)
    green = sum(1 for x in vals if x > 0)
    dmed = med(vals); dmean = tot / n
    cum = 0.0; peak = 0.0; dd = 0.0
    for k in dates:
        cum += d[k]; peak = max(peak, cum); dd = max(dd, peak - cum)
    hr = [x["pnl"] for x in tr if x["pnl"] >= 250]
    wt = min([x["pnl"] for x in tr], default=0.0)
    cons = (dmean > 50 and dmed > 50 and green / n >= 0.55 and h1 > 0 and h2 > 0 and min(vals) > -300)
    conv = (h1 > 0 and h2 > 0 and len(hr) >= 5 and wt > -150 and dd < 1000)
    return dict(N=N, win=(100 * sum(1 for x in tr if x["pnl"] > 0) / N) if N else 0.0, tot=tot,
                ptr=(tot / N) if N else 0.0, dmean=dmean, dmed=dmed, green=green, n=n, h1=h1, h2=h2,
                worst=min(vals), wt=wt, hr=len(hr), prem=sum(hr), dd=dd, cons=cons, conv=conv)

CELL_HDR = "| cell | N | win% | $/trade | total | day mean | day med | green | halves | worst day | worst tr | HR>=250 | premium | maxDD | CONSIST | CONVEX |"
CELL_SEP = "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
def row(name, g):
    P(f"| {name} | {g['N']} | {g['win']:.0f}% | ${g['ptr']:+.2f} | ${g['tot']:+.0f} | ${g['dmean']:+.2f} | ${g['dmed']:+.2f} | "
      f"{g['green']}/{g['n']} ({100*g['green']/g['n']:.0f}%) | ${g['h1']:+.0f}/${g['h2']:+.0f} | ${g['worst']:+.0f} | ${g['wt']:+.0f} | "
      f"{g['hr']} | ${g['prem']:+.0f} | ${g['dd']:+.0f} | {'PASS' if g['cons'] else 'fail'} | {'PASS' if g['conv'] else 'fail'} |")

def main():
    P("# JOINT DOOR 8/16 — Kev fingerprint (field filter) x window x pullback entries x runner exits")
    nf = load_all()
    dates = sorted({d for _, d in E.DAYS})
    P(f"cache: {nf} files, {len(FULL)} name-days loaded, {len(E.DAYS)} with >=60 RTH bars, {len(dates)} dates {dates[0]}..{dates[-1]}")
    fingerprint_all()
    calmX, ncal = calibrate_calm()
    P(f"\n## LAYER 1 — fingerprint. calm X (30th pct of 1-min range/close at 09:30 stamp, n={ncal}) = {calmX:.1f} bps; spread proxy <= 80 bps; gain >= +20% (ref = 04:00 ET first-bar open)")
    st930 = [k for k in FP if FP[k]["s930"]["win"]]
    sp = [FP[k]["s930"]["win"]["spread"] for k in st930]; cm = [FP[k]["s930"]["win"]["calm"] for k in st930]
    gn = [FP[k]["s930"]["gain"] for k in st930]
    P(f"09:30 stamp available {len(st930)}/{len(FP)}; spread proxy median {med(sp):.0f} bps (<=80: {sum(1 for x in sp if x<=80)}), calm median {med(cm):.0f} bps, gain>=20%: {sum(1 for x in gn if x>=0.2)}")
    st800 = [k for k in FP if FP[k]["s800"]["win"]]
    P(f"08:00 stamp available {len(st800)}/{len(FP)} (>=10 traded bars 07:30-08:00 ET)")
    sigs = gen_entries()
    ALLRES = {}
    for D in DEFS:
        P(f"\n\n# ===== SELECTION DEFINITION {D}: {DEFS[D]} =====")
        q930 = {k for k in FP if passes(k, calmX, "930", D)}; q800 = {k for k in FP if passes(k, calmX, "800", D)}
        KEV = {k for k in FP if kev_shaped(k, calmX, D)}
        P(f"QUALIFY: 09:30 stamp {len(q930)} ({100*len(q930)/len(FP):.0f}%), 08:00 stamp {len(q800)} ({100*len(q800)/len(FP):.0f}%), either = KEV-SHAPED {len(KEV)}/{len(FP)} ({100*len(KEV)/len(FP):.0f}%)")
        # component-wise pass rates at 09:30
        for nm, fn in (("spread<=80", lambda k: FP[k]["s930"]["win"]["spread"] <= 80), ("calm<=X", lambda k: FP[k]["s930"]["win"]["calm"] <= calmX), ("gain>=20%", lambda k: (FP[k]["s930"]["gain"] or -1) >= 0.2)):
            P(f"  09:30 component {nm}: {sum(1 for k in st930 if fn(k))}/{len(st930)}")

        # honesty check: Kev's picks
        kw = json.load(open(E.BARS_DIR + "/../ticks_precursor/kev_watchlist.json"))
        picks = {(s, d) for d, ss in kw.items() for s in ss}
        pin = [k for k in picks if k in FP]
        P(f"\n### Honesty check — Kev's nightly picks: {len(picks)} pick name-days ({len(kw)} dates), {len(pin)} in the universe cache")
        kp = sum(1 for k in pin if k in KEV)
        P(f"Kev picks passing the fingerprint: {kp}/{len(pin)} ({100*kp/max(1,len(pin)):.0f}%) vs universe {100*len(KEV)/len(FP):.0f}% -> lift {(kp/max(1,len(pin)))/(len(KEV)/len(FP)):.2f}x")
        P("Kev picks fingerprint detail (spread/calm/gain at 09:30, 08:00 pass?):")
        for k in sorted(pin, key=lambda z: z[1]):
            w = FP[k]["s930"]["win"]; g = FP[k]["s930"]["gain"]
            P(f"  {k[1]} {k[0]}: " + (f"spread {w['spread']:.0f} calm {w['calm']:.0f} gain {100*g:+.0f}%" if w else "no 09:30 stamp") + f" | 930 {'Y' if k in q930 else 'n'} 800 {'Y' if k in q800 else 'n'} -> {'KEV-SHAPED' if k in KEV else '-'}")

        # census: rockets vs duds
        P("\n### CENSUS — does the fingerprint SEE the field's rockets? (name-day level)")
        big = json.load(open(HERE + "/big_rides_reverse_20260816.json"))["top"]
        legs = json.load(open(HERE + "/rocket_anatomy_20260816_rows.json"))["legs"]
        bigk = {(x["sym"], x["date"]) for x in big}
        legk = {(x["sym"], x["date"]) for x in legs}
        rock = (bigk | legk) & set(FP); duds = set(FP) - rock
        def cov(ks): return sum(1 for k in ks if k in KEV), len(ks)
        a, b_ = cov(bigk & set(FP)); P(f"top-60 big rides: {a}/{b_} name-days pass ({100*a/max(1,b_):.0f}%)")
        la = sum(1 for x in legs if (x["sym"], x["date"]) in KEV); P(f"724 vertical legs: {la}/{len(legs)} legs on passing name-days ({100*la/len(legs):.0f}%); leg name-days {cov(legk & set(FP))}")
        lpost = [x for x in legs if x["t"] >= "13:30:00"]; la2 = sum(1 for x in lpost if (x["sym"], x["date"]) in KEV)
        P(f"  legs at/after 09:30 ET only: {la2}/{len(lpost)} ({100*la2/max(1,len(lpost)):.0f}%)")
        lpre = [x for x in legs if x["t"] < "13:30:00" and x["t"] >= "12:00:00"]; la3 = sum(1 for x in lpre if (x["sym"], x["date"]) in q800)
        P(f"  legs 08:00-09:30 ET vs the 08:00 stamp only: {la3}/{len(lpre)} ({100*la3/max(1,len(lpre)):.0f}%)")
        r1, r2 = cov(rock); d1, d2 = cov(duds)
        P(f"ROCKET name-days (top-60 U leg-days): {r1}/{r2} pass ({100*r1/r2:.1f}%); DUD name-days (neither): {d1}/{d2} pass ({100*d1/d2:.1f}%)")
        P(f"**ENRICHMENT RATIO (rocket coverage / dud coverage) = {(r1/r2)/(d1/d2):.2f}x**; of all passing name-days {len(KEV)}, rockets = {r1} ({100*r1/len(KEV):.0f}%) vs base rate {100*r2/len(FP):.0f}%")
        # per component enrichment
        for nm, fn in (("gain>=20% @09:30 alone", lambda k: FP[k]["s930"]["win"] is not None and (FP[k]["s930"]["gain"] or -1) >= 0.2),
                       ("spread<=80 & calm alone (no gain)", lambda k: FP[k]["s930"]["win"] is not None and FP[k]["s930"]["win"]["spread"] <= 80 and FP[k]["s930"]["win"]["calm"] <= calmX)):
            rr = sum(1 for k in rock if fn(k)); dd_ = sum(1 for k in duds if fn(k))
            P(f"  component {nm}: rockets {rr}/{r2} ({100*rr/r2:.0f}%) duds {dd_}/{d2} ({100*dd_/d2:.0f}%) enrich {(rr/r2)/max(1e-9,dd_/d2):.2f}x")

        # ---------------- entries ----------------
        P(f"\n## LAYERS 2-4 — entries {len(sigs)} signals total: " + str({d: sum(1 for s in sigs if s['det']==d) for d in ('v2cal','bandpass','pre_reclaim','BA')}))
        dates36 = [d for d in dates if "2026-06-25" <= d <= "2026-08-14"]
        RES = {}
        lift_rows = []
        for wn in WINDOWS:
            P(f"\n### {wn}  (RTH part flattens 15:45 ET live-parity; pre_reclaim flattens 09:25 ET)")
            P(CELL_HDR); P(CELL_SEP)
            for det in ("v2cal", "bandpass", "pre_reclaim", "BA"):
                if det == "pre_reclaim" and not wn.startswith("W1"): continue
                ss = [s for s in sigs if s["det"] == det and in_win(s, wn)]
                for sel in ("KEV", "NOT"):
                    sub = [s for s in ss if ((s["sym"], s["date"]) in KEV) == (sel == "KEV")]
                    for v in ("E3", "E4", "E4W", "S5"):
                        tr = run_cell(sub, v); g = grade(tr, dates)
                        RES[(wn, det, sel, v)] = (tr, g)
                        row(f"{det} {sel} {v}", g)
                        if v == "E3": lift_rows.append((wn, det, sel, g))
        P(f"\n(E3 reconciled to X.sim_var_live on {RECON['n']} RTH trades, max |diff| ${RECON['maxdiff']:.4f})")

        # selection lift table
        P("\n## SELECTION LIFT — $/trade Kev-shaped vs NOT (E3, and best exit for the Kev cell)")
        P("| window | entry | KEV N | KEV $/tr (E3) | NOT N | NOT $/tr (E3) | lift $/tr | KEV best exit | KEV $/tr best | KEV day mean best |")
        P("|---|---|---|---|---|---|---|---|---|---|")
        for wn in WINDOWS:
            for det in ("v2cal", "bandpass", "pre_reclaim", "BA"):
                if (wn, det, "KEV", "E3") not in RES: continue
                gk = RES[(wn, det, "KEV", "E3")][1]; gn_ = RES[(wn, det, "NOT", "E3")][1]
                best = max(("E3", "E4", "E4W", "S5"), key=lambda v: RES[(wn, det, "KEV", v)][1]["ptr"])
                gb = RES[(wn, det, "KEV", best)][1]
                P(f"| {wn} | {det} | {gk['N']} | ${gk['ptr']:+.2f} | {gn_['N']} | ${gn_['ptr']:+.2f} | ${gk['ptr']-gn_['ptr']:+.2f} | {best} | ${gb['ptr']:+.2f} | ${gb['dmean']:+.2f} |")

        # v2 toll
        P("\n## THE v2 TOLL QUESTION — Kev-shaped names, Kev window (07:00-10:00 = RTH 09:30-10:00), calibrated v2 flush")
        for v in ("E3", "E4", "E4W", "S5"):
            g = RES[("W1 07:00-10:00", "v2cal", "KEV", v)][1]
            P(f"  {v}: N={g['N']} $/trade ${g['ptr']:+.2f} -> {'EXCEEDS' if g['ptr'] > 6 else 'DOES NOT EXCEED'} the ~$6 toll (win {g['win']:.0f}%, total ${g['tot']:+.0f})")
        g = RES[("W2 09:30-10:30", "v2cal", "KEV", "E3")][1]
        P(f"  (09:30-10:30 E3 for reference: N={g['N']} ${g['ptr']:+.2f}/trade)")

        # ---------------- PORTFOLIO ----------------
        P("\n## PORTFOLIO — best entry per window on Kev-shaped names, 2 slots, live parity (B.pipeline H1-H4)")
        def bestcell(wn):
            cands = [(det, v) for det in ("v2cal", "bandpass", "BA") for v in ("E3", "E4", "E4W", "S5") if (wn, det, "KEV", v) in RES]
            return max(cands, key=lambda c: (RES[(wn, c[0], "KEV", c[1])][1]["cons"], RES[(wn, c[0], "KEV", c[1])][1]["dmean"]))
        P("| config | dates | N | day mean | day median | green | halves $/d | worst | 5-crit | HR>=250 | worst tr | maxDD | vs O-config +$156.76/+$130.35 |")
        P("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        ports = {}
        for wn in WINDOWS:
            det, v = bestcell(wn)
            ss = sorted([s for s in sigs if s["det"] == det and in_win(s, wn) and (s["sym"], s["date"]) in KEV], key=lambda s: (s["key"], s["sym"]))
            def ex(s, halt_rule, v=v):
                pnl, exx, xi = sim_rth(s["sym"], s["date"], s["i"], s["entry"], s["stop"], v)
                return True, pnl, exx, xi, s["i"]
            for dl, dn in ((dates, "62d"), (dates36, "36d")):
                sub = [s for s in ss if s["date"] in set(dl)]
                r = quiet(B.pipeline, sub, dl, ex, f"{wn} {det} {v} {dn}")
                h = r["h5"]; ok = all(p for _, p in r["verdict"].values())
                g = grade(r["h4"], dl)
                beat = "BEATS" if (h["mean"] > 156.76 and h["median"] > 130.35) else "no"
                P(f"| {wn} best={det}/{v} KEV-only 2-slot | {dn} | {len(r['h4'])} | ${h['mean']:+.2f} | ${h['median']:+.2f} | {h['green']}/{h['n']} | ${h['half1d']:+.2f}/${h['half2d']:+.2f} | ${h['worst']:+.2f} | {'PASS' if ok else 'FAIL'} | {g['hr']} | ${g['wt']:+.0f} | ${g['dd']:+.0f} | {beat} |")
                ports[(wn, dn)] = (det, v, r["h4"], g)
            # same portfolio on NOT-Kev names (lift at portfolio level)
            ssn = sorted([s for s in sigs if s["det"] == det and in_win(s, wn) and (s["sym"], s["date"]) not in KEV], key=lambda s: (s["key"], s["sym"]))
            r = quiet(B.pipeline, ssn, dates, ex, "not")
            h = r["h5"]; ok = all(p for _, p in r["verdict"].values()); g = grade(r["h4"], dates)
            P(f"| {wn} same {det}/{v} NOT-Kev 2-slot | 62d | {len(r['h4'])} | ${h['mean']:+.2f} | ${h['median']:+.2f} | {h['green']}/{h['n']} | ${h['half1d']:+.2f}/${h['half2d']:+.2f} | ${h['worst']:+.2f} | {'PASS' if ok else 'FAIL'} | {g['hr']} | ${g['wt']:+.0f} | ${g['dd']:+.0f} | - |")
        # joint: W1 best + pre_reclaim + W2 best combined (all Kev-shaped), 2 slots
        (d1_, v1) = bestcell("W1 07:00-10:00"); (d2_, v2) = bestcell("W2 09:30-10:30")
        comb = [s for s in sigs if (s["sym"], s["date"]) in KEV and ((s["det"] == d1_ and in_win(s, "W1 07:00-10:00")) or (s["det"] == d2_ and in_win(s, "W2 09:30-10:30")) or s["det"] == "pre_reclaim")]
        comb.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
        vmap = {d1_: v1, d2_: v2, "pre_reclaim": "E3"}
        def exj(s, halt_rule):
            if s["det"] == "pre_reclaim":
                pb, pe, pg = pre_slice((s["sym"], s["date"]))
                pnl, exx, xi = sim_x(pb, pe, pg, s["i"], s["entry"], s["stop"], "E3", FLAT_PRE)
                return True, pnl, exx, xi, s["i"]
            pnl, exx, xi = sim_rth(s["sym"], s["date"], s["i"], s["entry"], s["stop"], vmap[s["det"]])
            return True, pnl, exx, xi, s["i"]
        # NOTE: pre_reclaim exits are timed on the premarket slice; xi indexes that slice. For slot
        # accounting B.pipeline reads E.DAYS bars[xi] -> wrong clock. Patch: give pre_reclaim its own
        # exit key by mapping xi to an RTH index that never blocks (pre trades are flat by 09:25 =
        # before any RTH fill), i.e. xi=0.
        def exj2(s, halt_rule):
            f, pnl, exx, xi, fb = exj(s, halt_rule)
            if s["det"] == "pre_reclaim":
                return f, pnl, exx, 0, 0
            return f, pnl, exx, xi, fb
        r = quiet(B.pipeline, comb, dates, exj2, "joint")
        h = r["h5"]; ok = all(p for _, p in r["verdict"].values()); g = grade(r["h4"], dates)
        P(f"| JOINT (pre_reclaim E3 + {d1_}/{v1} W1 + {d2_}/{v2} W2) KEV-only 2-slot | 62d | {len(r['h4'])} | ${h['mean']:+.2f} | ${h['median']:+.2f} | {h['green']}/{h['n']} | ${h['half1d']:+.2f}/${h['half2d']:+.2f} | ${h['worst']:+.2f} | {'PASS' if ok else 'FAIL'} | {g['hr']} | ${g['wt']:+.0f} | ${g['dd']:+.0f} | {'BEATS' if (h['mean']>156.76 and h['median']>130.35) else 'no'} |")
        P("  (pre_reclaim slot key set to fill-time; pre trades are flat by 09:25 ET so they never occupy an RTH slot — disclosed)")
        ports["joint"] = r["h4"]

        # ---------------- HAND TRACES: 3 Kev-pick name-days ----------------
        P("\n## HAND-TRACES — three Kev-pick name-days (fingerprint stamp + every in-window signal, E3 log)")
        trace_days = [k for k in sorted(pin, key=lambda z: (z not in KEV, z[1])) if any(s["sym"] == k[0] and s["date"] == k[1] and (in_win(s, "W1 07:00-10:00") or in_win(s, "W2 09:30-10:30")) for s in sigs)]
        done = 0
        for k in trace_days:
            if done >= 3: break
            w9 = FP[k]["s930"]["win"]; g9 = FP[k]["s930"]["gain"]; w8 = FP[k]["s800"]["win"]; g8 = FP[k]["s800"]["gain"]
            P(f"\n**{k[0]} {k[1]}** (Kev pick) ref {FP[k]['ref']:.4f}; 08:00 stamp: " + (f"spread {w8['spread']:.0f} calm {w8['calm']:.0f} gain {100*g8:+.0f}%" if w8 else "n/a") + f" -> {'PASS' if k in q800 else 'fail'}; 09:30 stamp: " + (f"spread {w9['spread']:.0f} calm {w9['calm']:.0f} gain {100*g9:+.0f}%" if w9 else "n/a") + f" -> {'PASS' if k in q930 else 'fail'} => {'KEV-SHAPED' if k in KEV else 'NOT kev-shaped'}")
            n = 0
            for s in sigs:
                if s["sym"] != k[0] or s["date"] != k[1]: continue
                if not (in_win(s, "W1 07:00-10:00") or in_win(s, "W2 09:30-10:30")): continue
                if n >= 4: P("   ..."); break
                lg = []
                if s["det"] == "pre_reclaim":
                    pb, pe, pg = pre_slice(k); pnl, ex_, xi = sim_x(pb, pe, pg, s["i"], s["entry"], s["stop"], "E3", FLAT_PRE, lg)
                else:
                    pnl, ex_, xi = sim_rth(k[0], k[1], s["i"], s["entry"], s["stop"], "E3", lg)
                P(f"   {s['det']} sig {s['t']}Z entry {s['entry']:.4f} (fill {s['entry']*1.01:.4f}) stop {s['stop']:.4f} -> E3 ${pnl:+.2f} {ex_}")
                for m in lg[:5]: P("      " + m)
                n += 1
            done += 1

        ALLRES[D] = {"|".join(k): g for k, (tr, g) in RES.items()}
    json.dump({"calmX": calmX, "cells": ALLRES,
               "recon": RECON}, open(HERE + "/joint_door_20260816_out.json", "w"), indent=1, default=str)
    open(HERE + "/joint_door_20260816_run.txt", "w").write("\n".join(OUT) + "\n")

if __name__ == "__main__":
    main()
