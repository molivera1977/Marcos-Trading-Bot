#!/usr/bin/env python3
"""KEVSEQ DAY-GAIN FLOOR SWEEP — 2026-08-17.  Analysis only; no bot edits.

Tests KEVSEQ_GAIN_MIN **as a rule** (not as a descriptive slice of existing fires).
Engine + fire generation imported UNCHANGED from the burst kill-test machinery
(sunday_afternoon_studies_20260816 = engine of record).
"""
import importlib.util, os, json, statistics, random, bisect
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
ROOM_PCT = 0.03; ROOM_STALE = 300
FLOORS = [20, 30, 40, 50, 60, 80, 100, 125, 150]

MINE_LO, MINE_HI = "2026-05-18", "2026-07-21"
HOLD_LO, HOLD_HI = "2026-07-22", "2026-08-14"
H1_LO, H1_HI = "2026-07-22", "2026-08-02"     # hold-out first half
H2_LO, H2_HI = "2026-08-03", "2026-08-14"     # hold-out second half


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
    """Port of kevseq_step with the LIVE burst clause (V0 trailing p75) applied as a
    fire condition, and the DAY-GAIN FLOOR *removed* (recorded instead).  The leg cap is
    applied per-arm downstream, because a different floor consumes the cap differently."""
    cands = []
    st = {"sess_hi": None, "sess_hi_k": None, "leg": 0, "leg_hi": None,
          "leg_lo": None, "pull_n": 0, "leg_lows": [], "b_i": None, "b_level": None,
          "hold_n": 0, "hold_hi": None, "armed": False, "pending": None, "leg_start": 0}
    vols = []
    for i, b in enumerate(bars):
        o, h, l, c, v = b["o"], b["h"], b["l"], b["c"], b["v"]
        k = E.secs(b)
        trail = vols[-BURST_LOOK:]
        p75 = pctile(trail, BURST_PCT) if len(trail) >= BURST_MINB else None
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
                burst_ok = bool(p75 and p75 > 0 and v >= p75)
                if pd_["stop"] < px and not room_block and burst_ok and gain is not None:
                    cands.append(dict(i=i, k=k, fire_px=round(px, 4), fill_px=round(c, 4),
                                      stop=round(pd_["stop"], 4), leg=st["leg"],
                                      kind=pd_["kind"], bar_hi=round(h, 4),
                                      bar_lo=round(l, 4), gain=gain))
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
        vols.append(v)
        st["leg_lows"].append((i, l))
        if len(st["leg_lows"]) > 360: st["leg_lows"].pop(0)
    return cands


# ── top-3 gainer replay (board proxy = the universe cache for that date) ──────
GAINTRACK = {}   # date -> {sym: (sorted ks, gains)}

def build_gaintrack(dates):
    byd = defaultdict(list)
    for (sym, date) in E.DAYS: byd[date].append(sym)
    for date, syms in byd.items():
        m = {}
        for sym in syms:
            rb = E.DAYS[(sym, date)][0]
            ref = S.REF.get((sym, date)) or (rb[0]["o"] if rb else 0)
            if not rb or not ref: continue
            ks = [E.secs(b) for b in rb]
            gs = [(b["c"] - ref) / ref * 100.0 for b in rb]
            m[sym] = (ks, gs)
        GAINTRACK[date] = m


def top3_at(date, k, sym):
    m = GAINTRACK.get(date) or {}
    scores = []
    for s, (ks, gs) in m.items():
        j = bisect.bisect_right(ks, k) - 1
        if j < 0: continue
        scores.append((gs[j], s))
    scores.sort(reverse=True)
    return sym in {s for _, s in scores[:3]}


def apply_arm(cands, floor, use_top3):
    out = []; used = defaultdict(int)
    for f in cands:
        ok = f["gain"] >= floor or (use_top3 and f["top3"])
        if not ok: continue
        key = (f["sym"], f["date"], f["leg"])
        if used[key] >= LEG_MAX: continue
        used[key] += 1
        out.append(f)
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
    out = []
    for f in fires:
        lim = round(f["fire_px"] * (1 + tol), 4)
        if f["bar_lo"] > lim: continue
        x = sim_one(f, lim, f["stop"])
        if x: out.append(x)
    return out


def stats(trades):
    if not trades:
        return dict(N=0, tot=0.0, dtr=0.0, win=0.0, worst=0.0, daymean=0.0,
                    daymed=0.0, green=0.0, ndays=0)
    n = len(trades); tot = sum(x["pnl"] for x in trades)
    win = 100.0 * sum(1 for x in trades if x["pnl"] > 0) / n
    worst = min(x["pnl"] for x in trades)
    byday = defaultdict(float)
    for x in trades: byday[x["date"]] += x["pnl"]
    dv = list(byday.values())
    return dict(N=n, tot=tot, dtr=tot / n, win=win, worst=worst,
                daymean=statistics.mean(dv), daymed=statistics.median(dv),
                green=100.0 * sum(1 for d in dv if d > 0) / len(dv), ndays=len(dv))


def row(lab, s):
    if s["N"] == 0:
        P(f"| {lab} | 0 | — | — | — | — | — | — | — |"); return
    P(f"| {lab} | {s['N']} | {s['win']:.0f}% | ${s['dtr']:+.2f} | ${s['tot']:+.2f} | "
      f"${s['worst']:+.2f} | ${s['daymean']:+.2f} | ${s['daymed']:+.2f} | {s['green']:.0f}% |")


HDR = ("| cell | N | win% | $/tr | total | worst | day mean | day med | green-day% |\n"
       "|---|---|---|---|---|---|---|---|---|")


def main():
    random.seed(20260817)
    nf, nd, dates = S.load_all()
    P(f"universe: {nf} files, {nd} graded name-days, {len(dates)} dates "
      f"({dates[0]} .. {dates[-1]})")
    build_gaintrack(dates)
    cands = []
    for (sym, date), (rb, emas, gaps) in E.DAYS.items():
        if not rb: continue
        vw = S.vwap_series(rb); e9 = e9_series(rb)
        ref = S.REF.get((sym, date)) or rb[0]["o"]
        mx = max(b["h"] for b in rb)
        dg = ((mx - ref) / ref * 100.0) if ref else 0.0
        for f in kevseq_scan(rb, vw, e9, ref):
            f.update(sym=sym, date=date, daygain_max=dg,
                     top3=top3_at(date, f["k"], sym))
            cands.append(f)
    P(f"FIRE-SET (all live clauses incl. burst, day-gain floor REMOVED, pre leg-cap): "
      f"{len(cands)}")
    P(f"  of which top-3-gainer at fire time: {sum(1 for f in cands if f['top3'])}")
    P(f"  MINE {sum(1 for f in cands if MINE_LO <= f['date'] <= MINE_HI)} / "
      f"HOLD-OUT {sum(1 for f in cands if HOLD_LO <= f['date'] <= HOLD_HI)}")
    all_dates = sorted({f["date"] for f in cands} | {d for _, d in E.DAYS})
    era_dates = [d for d in all_dates if MINE_LO <= d <= HOLD_HI]

    res = {}
    for entry_lab, simfn in (("QUOTE-ENTRY (today's pre-13:57 behaviour)", sim_quote),
                             ("F3 LIMIT-AT-FIRE +0.5% (production since 13:57 ET)", sim_limit)):
        for t3 in (True, False):
            arm = "WITH top3 escape (live rule)" if t3 else "NO top3 escape (floor only)"
            for floor in FLOORS:
                fires = apply_arm(cands, floor, t3)
                P("")
                P(f"### {entry_lab} — {arm} — floor {floor}%")
                P(HDR)
                for clab, pred in (("MINE", lambda f: MINE_LO <= f["date"] <= MINE_HI),
                                   ("HOLD-OUT", lambda f: HOLD_LO <= f["date"] <= HOLD_HI),
                                   ("HOLD H1 07-22..08-02", lambda f: H1_LO <= f["date"] <= H1_HI),
                                   ("HOLD H2 08-03..08-14", lambda f: H2_LO <= f["date"] <= H2_HI)):
                    s = stats(simfn([f for f in fires if pred(f)]))
                    res[f"{entry_lab}|{arm}|{floor}|{clab}"] = s
                    row(clab, s)
                # coverage
                fd = defaultdict(int)
                for f in fires:
                    if MINE_LO <= f["date"] <= HOLD_HI: fd[f["date"]] += 1
                cov = 100.0 * len(fd) / len(era_dates) if era_dates else 0
                med = statistics.median(list(fd.values())) if fd else 0
                res[f"{entry_lab}|{arm}|{floor}|COVERAGE"] = dict(
                    days_with_fire=len(fd), era_days=len(era_dates), pct=cov, median_fpd=med)
                P(f"coverage: {len(fd)}/{len(era_dates)} era days have >=1 fire ({cov:.0f}%), "
                  f"median fires/day (on firing days) {med}")

    # ── monotonicity curve (production path: F3 + live top3 rule, HOLD-OUT) ──
    ekey = "F3 LIMIT-AT-FIRE +0.5% (production since 13:57 ET)"
    P("")
    P("### MONOTONICITY — HOLD-OUT $/tr by floor")
    P("| floor | WITH top3 N | $/tr | NO top3 N | $/tr |")
    P("|---|---|---|---|---|")
    curve = {}
    for floor in FLOORS:
        a = res[f"{ekey}|WITH top3 escape (live rule)|{floor}|HOLD-OUT"]
        b = res[f"{ekey}|NO top3 escape (floor only)|{floor}|HOLD-OUT"]
        curve[floor] = dict(with_n=a["N"], with_dtr=a["dtr"], no_n=b["N"], no_dtr=b["dtr"])
        P(f"| {floor}% | {a['N']} | ${a['dtr']:+.2f} | {b['N']} | ${b['dtr']:+.2f} |")
    seq = [curve[f]["no_dtr"] for f in FLOORS]
    mono = all(seq[i + 1] >= seq[i] for i in range(len(seq) - 1))
    seq_w = [curve[f]["with_dtr"] for f in FLOORS]
    mono_w = all(seq_w[i + 1] >= seq_w[i] for i in range(len(seq_w) - 1))
    P(f"monotone (NO-top3 arm): {mono} | monotone (WITH-top3 arm): {mono_w}")

    # ── best MATERIAL cell (HOLD-OUT N >= 30) ──
    best = None
    for floor in FLOORS:
        for arm in ("WITH top3 escape (live rule)", "NO top3 escape (floor only)"):
            s = res[f"{ekey}|{arm}|{floor}|HOLD-OUT"]
            if s["N"] >= 30 and (best is None or s["dtr"] > best[2]["dtr"]):
                best = (floor, arm, s)
    P("")
    if best is None:
        P("NO material cell (every cell HOLD-OUT N<30) -> UNDERPOWERED")
        pval = None
    else:
        floor, arm, s = best
        P(f"BEST MATERIAL CELL (F3, HOLD-OUT N>=30): floor {floor}% / {arm} "
          f"-> N={s['N']} $/tr ${s['dtr']:+.2f} total ${s['tot']:+.2f} win {s['win']:.0f}%")
        # ── NULL: random subsets of the same size from the CURRENT-RULE hold-out fire-set
        base = simfn_pool = sim_limit([f for f in apply_arm(cands, 20, True)
                                       if HOLD_LO <= f["date"] <= HOLD_HI])
        pool = [x["pnl"] for x in base]
        P(f"null pool = current rule (floor 20 OR top3), F3, HOLD-OUT: N={len(pool)} "
          f"$/tr ${statistics.mean(pool):+.2f}")
        n = min(s["N"], len(pool)); hits = 0; NP = 5000
        for _ in range(NP):
            hits += 1 if statistics.mean(random.sample(pool, n)) >= s["dtr"] else 0
        pval = (hits + 1) / (NP + 1)
        P(f"permutation ({NP} shuffles, random {n}-subsets of the current-rule pool): "
          f"p = {pval:.4f}")

    json.dump({"n_fires": len(cands), "res": res, "curve": curve,
               "mono_no_top3": mono, "mono_with_top3": mono_w,
               "best": (None if best is None else dict(floor=best[0], arm=best[1], **best[2])),
               "p": pval},
              open(HERE + "/kevseq_floor_sweep_20260817_out.json", "w"), indent=1)
    open(HERE + "/kevseq_floor_sweep_20260817_run.txt", "w").write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
