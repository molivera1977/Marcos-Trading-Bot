#!/usr/bin/env python3
"""DEFECT 1a KILL-TEST — kevseq BURST SATURATION on sustained runners.

Failure condition pre-registered in burst_saturation_20260817.md (written FIRST).
Engine imported UNCHANGED from sunday_afternoon_studies_20260816 (engine of record),
same as entry_drift_20260817.py.  Analysis only; no bot edits from this file.
"""
import importlib.util, os, json, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("S", HERE + "/sunday_afternoon_studies_20260816.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
G = S.G; F = S.F; C = S.C; B = S.B; E = S.E

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

N_BARS = 18; HOLD_N = 3; BURST_PCT = 75; BURST_LOOK = 30; BURST_MINB = 10
MAX_TOUCH = 1; MAX_PULL = 2; LEG_PB = 0.03; LEG_MAX = 3; TOUCH_BAND = 0.005
GAIN_MIN = 20.0; ROOM_PCT = 0.03; ROOM_STALE = 300
RUNNER_GAIN = 25.0

MINE_LO, MINE_HI = "2026-05-18", "2026-07-21"
HOLD_LO, HOLD_HI = "2026-07-22", "2026-08-14"


def pctile(v, p):
    if not v: return None
    v = sorted(v); i = min(len(v) - 1, int(round((len(v) - 1) * p / 100.0)))
    return v[i]


def e9_series(bars):
    out = []; e = None; kk = 2.0 / 10
    for b in bars:
        e = b["c"] if e is None else (b["c"] - e) * kk + e
        out.append(e)
    return out


def kevseq_scan(bars, vwaps, e9s, ref_open):
    """Port of kevseq_step, but burst is NOT a fire condition — every candidate fill is
    emitted with ALL the raw measurements each variant needs.  Every other clause
    (leg cap, degenerate stop, room, day-gain floor) is applied exactly as live, EXCEPT
    the leg cap, which is variant-dependent (a variant that fires more consumes the cap
    differently) and is therefore applied per-variant downstream."""
    cands = []
    st = {"sess_hi": None, "sess_hi_k": None, "leg": 0, "leg_hi": None,
          "leg_lo": None, "pull_n": 0, "leg_lows": [], "b_i": None, "b_level": None,
          "hold_n": 0, "hold_hi": None, "armed": False, "pending": None, "leg_start": 0}
    vols = []          # FULL history (V1 needs pre-leg windows)
    dvols = []         # dollar volume history
    for i, b in enumerate(bars):
        o, h, l, c, v = b["o"], b["h"], b["l"], b["c"], b["v"]
        k = E.secs(b)
        trail = vols[-BURST_LOOK:]
        p75 = pctile(trail, BURST_PCT) if len(trail) >= BURST_MINB else None
        dtrail = dvols[-BURST_LOOK:]
        dp75 = pctile(dtrail, BURST_PCT) if len(dtrail) >= BURST_MINB else None
        ls = st["leg_start"]
        pre = vols[max(0, ls - BURST_LOOK):ls]
        pre75 = pctile(pre, BURST_PCT) if len(pre) >= BURST_MINB else None
        smed = statistics.median(vols) if len(vols) >= BURST_MINB else None
        pd_ = st["pending"]
        if pd_ is not None:
            if l < pd_["stop"]:
                st["pending"] = None
            elif h > pd_["hi"]:
                st["pending"] = None
                px = float(pd_["hi"])
                gain = ((c - ref_open) / ref_open * 100.0) if ref_open else None
                room_block = (st["sess_hi"] is not None and st["sess_hi_k"] is not None
                              and px < st["sess_hi"] <= px * (1 + ROOM_PCT)
                              and (k - st["sess_hi_k"]) >= ROOM_STALE)
                ctx_ok = (pd_["stop"] < px and not room_block
                          and gain is not None and gain >= GAIN_MIN)
                if ctx_ok:
                    cands.append(dict(i=i, fire_px=round(px, 4), fill_px=round(c, 4),
                                      stop=round(pd_["stop"], 4), leg=st["leg"],
                                      kind=pd_["kind"], bar_hi=round(h, 4), bar_lo=round(l, 4),
                                      v=v, dv=v * c, p75=p75, dp75=dp75, pre75=pre75,
                                      smed=smed))
        prev_hi = st["sess_hi"]
        if prev_hi is None:
            st["sess_hi"] = h; st["sess_hi_k"] = k
            st["leg"] = 1; st["leg_hi"] = h; st["leg_lo"] = l; st["leg_start"] = i
        elif h > prev_hi:
            if (st["leg_lo"] is not None and st["leg_hi"] and st["leg_hi"] > 0
                    and (st["leg_hi"] - st["leg_lo"]) / st["leg_hi"] >= LEG_PB):
                st["leg"] += 1; st["pull_n"] = 0; st["leg_lows"] = []
                st["leg_start"] = i
            st["leg_hi"] = h; st["leg_lo"] = l
            level = prev_hi
            if o < c:
                wd = float(int(c))
                if o < wd <= c and wd > level: level = wd
            st["b_i"] = i; st["b_level"] = level; st["hold_n"] = 0; st["hold_hi"] = None
            st["armed"] = True; st["sess_hi"] = h; st["sess_hi_k"] = k
        else:
            st["leg_lo"] = l if st["leg_lo"] is None else min(st["leg_lo"], l)
            st["leg_hi"] = st["leg_hi"] or prev_hi
        if st["b_i"] is not None and st["armed"] and st["pending"] is None and i > st["b_i"]:
            if i - st["b_i"] > N_BARS:
                st["armed"] = False
            else:
                setup = None; lvl = st["b_level"]
                if lvl and l >= lvl:
                    st["hold_n"] += 1
                    st["hold_hi"] = h if st["hold_hi"] is None else max(st["hold_hi"], h)
                    if st["hold_n"] >= HOLD_N:
                        setup = {"kind": "H", "hi": st["hold_hi"], "stop": lvl}
                else:
                    st["hold_n"] = 0; st["hold_hi"] = None
                vw = vwaps[i]; e9 = e9s[i]
                if setup is None and vw and vw > 0 and e9:
                    lines = [x for x in (vw, e9) if l <= x * (1 + TOUCH_BAND)]
                    if lines and c > vw and c > e9 and l < h:
                        line = max(lines)
                        if l <= line * (1 + TOUCH_BAND):
                            setup = {"kind": "W", "hi": h, "stop": l}
                if setup is not None:
                    st["armed"] = False; st["pull_n"] += 1
                    stop = setup["stop"]
                    touch_n = (sum(1 for xi, x in st["leg_lows"]
                                   if xi < st["b_i"] and abs(x - stop) / stop <= TOUCH_BAND)
                               if stop > 0 else 0)
                    if not (st["pull_n"] > MAX_PULL or touch_n > MAX_TOUCH):
                        setup.update({"touch_n": touch_n})
                        st["pending"] = setup
        vols.append(v); dvols.append(v * c)
        st["leg_lows"].append((i, l))
        if len(st["leg_lows"]) > 360: st["leg_lows"].pop(0)
    return cands


# ── burst variants: candidate -> bool ───────────────────────────────────────
def V0(f):  return bool(f["p75"] and f["p75"] > 0 and f["v"] >= f["p75"])
def V1(f):  return bool(f["pre75"] and f["pre75"] > 0 and f["v"] >= f["pre75"])
def V3(f):  return bool(f["dp75"] and f["dp75"] > 0 and f["dv"] >= f["dp75"])
def V4(f):  return True
def V2(x):
    def g(f):
        return V0(f) or bool(f["smed"] and f["smed"] > 0 and f["v"] >= x * f["smed"])
    return g

VARIANTS = [("V0 baseline (trailing p75)", V0),
            ("V1 pre-run p75 (30 bars before leg)", V1),
            ("V2 OR session-median x1.5", V2(1.5)),
            ("V2 OR session-median x2", V2(2.0)),
            ("V2 OR session-median x3", V2(3.0)),
            ("V3 dollar-volume trailing p75", V3),
            ("V4 no burst clause", V4)]


def apply_variant(cands, fn):
    """Apply the burst test + the per-leg cap in bar order (the cap is consumed by the
    fires the variant actually takes — a more permissive variant burns it faster)."""
    out = []; used = defaultdict(int)
    for f in cands:
        if not fn(f): continue
        key = (f["sym"], f["date"], f["leg"])
        if used[key] >= LEG_MAX: continue
        used[key] += 1
        g = dict(f); g["leg_n"] = used[key]
        out.append(g)
    return out


def sim_one(f, entry_px, stop):
    if not (stop and 0 < stop < entry_px): return None
    rb, emas, gaps = E.DAYS[(f["sym"], f["date"])]
    if f["i"] >= len(rb) - 2: return None
    pnl, why, xi = F.sim_var(rb, emas, gaps, f["i"], entry_px, stop, "E3", "kevseq", True)
    return dict(pnl=pnl, sym=f["sym"], date=f["date"])


def sim_quote(fires):
    return [x for x in (sim_one(f, f["fill_px"], f["stop"]) for f in fires) if x]


def sim_limit(fires, tol=0.005):
    """F3 limit-at-fire, 0 extra bars (the arm entry_drift_20260817 chose)."""
    out = []
    for f in fires:
        lim = round(f["fire_px"] * (1 + tol), 4)
        if f["bar_lo"] > lim: continue
        x = sim_one(f, lim, f["stop"])
        if x: out.append(x)
    return out


def block(name, trades):
    if not trades:
        P(f"| {name} | 0 | — | — | — |"); return dict(N=0, tot=0.0, dtr=0.0, win=0.0)
    tot = sum(x["pnl"] for x in trades); n = len(trades)
    win = 100.0 * sum(1 for x in trades if x["pnl"] > 0) / n
    P(f"| {name} | {n} | ${tot:+.2f} | ${tot/n:+.2f} | {win:.0f}% |")
    return dict(N=n, tot=tot, dtr=tot / n, win=win)


def main():
    nf, nd, dates = S.load_all()
    P(f"universe: {nf} files, {nd} graded name-days, {len(dates)} dates "
      f"({dates[0]} .. {dates[-1]})")
    cands = []; runner = {}
    for (sym, date), (rb, emas, gaps) in E.DAYS.items():
        if not rb: continue
        vw = S.vwap_series(rb); e9 = e9_series(rb)
        ref = S.REF.get((sym, date)) or rb[0]["o"]
        mx = max(b["h"] for b in rb)
        dg = ((mx - ref) / ref * 100.0) if ref else 0.0
        runner[(sym, date)] = bool(dg >= RUNNER_GAIN)
        for f in kevseq_scan(rb, vw, e9, ref):
            f.update(sym=sym, date=date, runner=runner[(sym, date)], daygain=dg)
            cands.append(f)
    P(f"kevseq CANDIDATE fills (all clauses except burst+leg-cap): {len(cands)}")
    P(f"name-days in RUNNER cohort (max gain >= {RUNNER_GAIN:.0f}%): "
      f"{sum(1 for v in runner.values() if v)} / {len(runner)}")

    # ── failure condition #1: is burst actually saturating on runners? ──
    P("")
    P("### FAILURE CONDITION #1 — does burst refuse MORE on runners?")
    P("| cohort | candidates | pass V0 | no_burst rate |")
    P("|---|---|---|---|")
    sat = {}
    for lab, sel in (("RUNNER", True), ("REST", False)):
        cc = [f for f in cands if f["runner"] is sel]
        pv = sum(1 for f in cc if V0(f))
        rate = 100.0 * (1 - pv / len(cc)) if cc else 0.0
        sat[lab] = rate
        P(f"| {lab} | {len(cc)} | {pv} | {rate:.1f}% |")
    P("NOTE (honesty): this split is DEGENERATE — kevseq's own day-gain>=20% floor already")
    P("pre-selects runners, so REST is ~empty and the RUNNER/REST comparison carries no")
    P("information.  The real claim is about run INTENSITY, so it is tested by gain bucket:")
    P("")
    P("| name-day max gain | candidates | pass V0 | no_burst rate |")
    P("|---|---|---|---|")
    BUCKETS = [("20-50%", 0, 50), ("50-100%", 50, 100), ("100-200%", 100, 200),
               ("200%+", 200, 1e9)]
    sat_b = {}
    for lab, lo, hi in BUCKETS:
        cc = [f for f in cands if lo <= f["daygain"] < hi]
        pv = sum(1 for f in cc if V0(f))
        rate = 100.0 * (1 - pv / len(cc)) if cc else 0.0
        sat_b[lab] = dict(n=len(cc), rate=rate)
        P(f"| {lab} | {len(cc)} | {pv} | {rate:.1f}% |")
    _lo = sat_b["20-50%"]["rate"]; _hi = sat_b["200%+"]["rate"]
    fc1 = _hi > _lo
    P(f"FC#1 (intensity form): no_burst 20-50% cohort {_lo:.1f}% vs 200%+ cohort {_hi:.1f}% -> "
      f"{'SATURATION CONFIRMED (refusal rises with run intensity)' if fc1 else 'NOT CONFIRMED — the saturation story is REFUTED'}")
    sat["by_bucket"] = sat_b

    res = {}
    for entry_lab, simfn in (("QUOTE-ENTRY (today)", sim_quote),
                             ("LIMIT-AT-FIRE +0.5% (F3)", sim_limit)):
        for coh_lab, pred in (("ALL", lambda f: True),
                              ("MINE", lambda f: MINE_LO <= f["date"] <= MINE_HI),
                              ("HOLD-OUT", lambda f: HOLD_LO <= f["date"] <= HOLD_HI),
                              ("RUNNER", lambda f: f["runner"]),
                              ("REST", lambda f: not f["runner"]),
                              ("VERTICAL 100%+", lambda f: f["daygain"] >= 100),
                              ("VERTICAL 100%+/HOLD-OUT", lambda f: f["daygain"] >= 100 and HOLD_LO <= f["date"] <= HOLD_HI),
                              ("RUNNER/HOLD-OUT", lambda f: f["runner"] and HOLD_LO <= f["date"] <= HOLD_HI)):
            sub = [f for f in cands if pred(f)]
            P("")
            P(f"### {entry_lab} — {coh_lab}")
            P("| variant | N | total | $/tr | win |")
            P("|---|---|---|---|---|")
            for vlab, vfn in VARIANTS:
                r = block(vlab, simfn(apply_variant(sub, vfn)))
                res[f"{entry_lab}|{coh_lab}|{vlab}"] = r

    # ── verdict against the pre-registered failure conditions ──
    P("")
    P("### VERDICT vs pre-registered failure conditions")
    base_key = lambda e, c: res[f"{e}|{c}|V0 baseline (trailing p75)"]
    verdict = {}
    for entry_lab in ("QUOTE-ENTRY (today)", "LIMIT-AT-FIRE +0.5% (F3)"):
        bm = base_key(entry_lab, "MINE"); bh = base_key(entry_lab, "HOLD-OUT")
        for vlab, _ in VARIANTS[1:]:
            m = res[f"{entry_lab}|MINE|{vlab}"]; h = res[f"{entry_lab}|HOLD-OUT|{vlab}"]
            both = m["dtr"] > bm["dtr"] and h["dtr"] > bh["dtr"]
            powered = h["N"] >= 20
            verdict[f"{entry_lab}|{vlab}"] = dict(both_halves=both, powered=powered,
                                                  mine=m["dtr"], hold=h["dtr"],
                                                  base_mine=bm["dtr"], base_hold=bh["dtr"],
                                                  hold_n=h["N"])
            P(f"{entry_lab} | {vlab}: MINE {m['dtr']:+.2f} vs {bm['dtr']:+.2f}, "
              f"HOLD {h['dtr']:+.2f} vs {bh['dtr']:+.2f} (N={h['N']}) -> "
              f"{'PASSES both halves' if both else 'FAILS FC#2'}"
              f"{'' if powered else ' [UNDERPOWERED, FC#4]'}")

    json.dump({"saturation": sat, "fc1": fc1, "res": res, "verdict": verdict,
               "n_candidates": len(cands)},
              open(HERE + "/burst_saturation_20260817_out.json", "w"), indent=1)
    open(HERE + "/burst_saturation_20260817_run.txt", "w").write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
