#!/usr/bin/env python3
"""ENTRY-DRIFT KILL-TEST 8/17 — the kevseq fire-price vs entry-price defect.

FAILURE CONDITION (pre-registered, written FIRST):
  This work is WRONG if, on the universe replay with the OOS split
  (MINE 2026-05-18..07-21 / HOLD-OUT 07-22..08-14, E3 live-parity, $500),
  the chosen fix does NOT raise HOLD-OUT $/trade over the today's-behaviour
  baseline, or raises it only by making N so small the result is noise
  (HOLD-OUT N < 20 => UNDERPOWERED, ship OFF by default).
  It is ALSO wrong if the drift the replay models is not the drift the live
  rows show: the replay's entry proxy is the FILL BAR CLOSE.  If the modelled
  kevseq drift distribution does not have a materially positive median while
  the sibling close-anchored lanes sit near zero, the model is not reproducing
  the live defect and every number below is void.

THE DEFECT (live rows, 2026-08-17 decisions archive):
  kevseq_step returns px = pd["hi"] — the H/W SETUP BAR'S HIGH, i.e. the trigger
  level, NOT the price of the bar that filled.  The caller
  (marcos_trading_bot.py :8195) then sets the entry to the LIVE QUOTE:
      _ks_px = price if price and price > 0 else _ksf["px"]
  while the stop stays at _ksf["would_stop"], the STRUCTURAL stop measured
  against the fire price.  Entry rises, stop does not, risk-per-share explodes.
  Live median kevseq drift +5.02% (N=7 unique fires, all 8/17), worst +28.87%
  (WFF 11:17:43 fire 3.91 -> entry 5.039, intended risk 5.9% -> actual 27.0%).
  Sibling lanes whose detectors return the bar CLOSE sit at ~0 drift.

ENGINE: imported UNCHANGED from sunday_afternoon_studies_20260816 (-> G -> F -> C
-> B -> E, engine of record).  All exits = E3 live-parity via F.sim_var, $500.
Analysis only.  No bot edits from this file.
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

# ── live kevseq constants, copied verbatim from marcos_trading_bot.py (8/17) ──
N_BARS = 18; HOLD_N = 3; BURST_PCT = 75; BURST_LOOK = 30; BURST_MINB = 10
MAX_TOUCH = 1; MAX_PULL = 2; LEG_PB = 0.03; LEG_MAX = 3; TOUCH_BAND = 0.005
GAIN_MIN = 20.0; ROOM_PCT = 0.03; ROOM_STALE = 300

MINE_LO, MINE_HI = "2026-05-18", "2026-07-21"
HOLD_LO, HOLD_HI = "2026-07-22", "2026-08-14"


def pctile(v, p):
    if not v: return None
    v = sorted(v); i = min(len(v) - 1, int(round((len(v) - 1) * p / 100.0)))
    return v[i]


def kevseq_replay(bars, vwaps, e9s, ref_open):
    """Faithful port of kevseq_step over one name-day's RTH 10s bars.

    Returns fires: dict(i=fill bar index, fire_px=pd["hi"] (WHAT THE LIVE DETECTOR
    RETURNS), fill_px=bars[i]["c"] (the replay's proxy for the live quote the caller
    reads), stop=would_stop, leg, leg_n, kind).
    Context: day_gain from the file's first bar (cache carries no prior close — the
    same disclosed caveat every study in this directory uses); front_side/top3/blue_sky
    are NOT reconstructible on the 10s cache, so the context clause is replaced by the
    day-gain floor alone.  Disclosed: this makes the replay cohort a SUPERSET of the
    live cohort; the drift mechanism under test is unaffected by which fires qualify.
    """
    fires = []
    st = {"sess_hi": None, "sess_hi_k": None, "leg": 0, "leg_n": 0, "leg_hi": None,
          "leg_lo": None, "pull_n": 0, "leg_lows": [], "b_i": None, "b_level": None,
          "hold_n": 0, "hold_hi": None, "armed": False, "pending": None}
    vols = []
    for i, b in enumerate(bars):
        o, h, l, c, v = b["o"], b["h"], b["l"], b["c"], b["v"]
        k = E.secs(b)
        p75 = pctile(vols[-BURST_LOOK:], BURST_PCT) if len(vols) >= BURST_MINB else None
        pd_ = st["pending"]
        if pd_ is not None:
            if l < pd_["stop"]:
                st["pending"] = None
            elif h > pd_["hi"]:
                st["pending"] = None
                px = float(pd_["hi"])
                burst = bool(p75 and p75 > 0 and v >= p75)
                gain = ((c - ref_open) / ref_open * 100.0) if ref_open else None
                room_block = (st["sess_hi"] is not None and st["sess_hi_k"] is not None
                              and px < st["sess_hi"] <= px * (1 + ROOM_PCT)
                              and (k - st["sess_hi_k"]) >= ROOM_STALE)
                ok = (burst and st["leg_n"] < LEG_MAX and pd_["stop"] < px
                      and not room_block and gain is not None and gain >= GAIN_MIN)
                if ok:
                    st["leg_n"] += 1
                    fires.append(dict(i=i, fire_px=round(px, 4), fill_px=round(c, 4),
                                      stop=round(pd_["stop"], 4), leg=st["leg"],
                                      leg_n=st["leg_n"], kind=pd_["kind"],
                                      bar_hi=round(h, 4), bar_lo=round(l, 4)))
        prev_hi = st["sess_hi"]
        if prev_hi is None:
            st["sess_hi"] = h; st["sess_hi_k"] = k
            st["leg"] = 1; st["leg_hi"] = h; st["leg_lo"] = l
        elif h > prev_hi:
            if (st["leg_lo"] is not None and st["leg_hi"] and st["leg_hi"] > 0
                    and (st["leg_hi"] - st["leg_lo"]) / st["leg_hi"] >= LEG_PB):
                st["leg"] += 1; st["leg_n"] = 0; st["pull_n"] = 0; st["leg_lows"] = []
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
    return fires


def e9_series(bars):
    out = []; e = None; kk = 2.0 / 10
    for b in bars:
        e = b["c"] if e is None else (b["c"] - e) * kk + e
        out.append(e)
    return out


def collect():
    nf, nd, dates = S.load_all()
    P(f"universe: {nf} files, {nd} graded name-days, {len(dates)} dates "
      f"({dates[0]} .. {dates[-1]})")
    all_fires = []
    for (sym, date), (rb, emas, gaps) in E.DAYS.items():
        vw = S.vwap_series(rb); e9 = e9_series(rb)
        ref = S.REF.get((sym, date)) or (rb[0]["o"] if rb else 0)
        for f in kevseq_replay(rb, vw, e9, ref):
            f.update(sym=sym, date=date)
            all_fires.append(f)
    return all_fires, dates


# ── candidate mechanisms ────────────────────────────────────────────────────
def sim_one(f, entry_px, stop):
    """E3 live-parity on one fire.  Returns pnl or None if degenerate."""
    if not (stop and 0 < stop < entry_px): return None
    rb, emas, gaps = E.DAYS[(f["sym"], f["date"])]
    if f["i"] >= len(rb) - 2: return None
    pnl, why, xi = F.sim_var(rb, emas, gaps, f["i"], entry_px, stop, "E3", "kevseq", True)
    return dict(pnl=pnl, why=why, xi=xi, sym=f["sym"], date=f["date"], t=f["i"],
                drift=f["drift"], entry=entry_px, stop=stop)


def arm_baseline(fires):
    """TODAY'S BEHAVIOUR: entry = the live quote proxy (fill bar close), stop = structural."""
    return [x for x in (sim_one(f, f["fill_px"], f["stop"]) for f in fires) if x]


def arm_F1(fires, thr):
    """DRIFT REFUSE: skip when drift > thr."""
    return [x for x in (sim_one(f, f["fill_px"], f["stop"]) for f in fires
                        if f["drift"] <= thr) if x]


def arm_F2(fires):
    """RE-ANCHOR STOP: preserve the INTENDED risk% at the drifted entry."""
    out = []
    for f in fires:
        ir = (f["fire_px"] - f["stop"]) / f["fire_px"]
        x = sim_one(f, f["fill_px"], round(f["fill_px"] * (1 - ir), 4))
        if x: out.append(x)
    return out


def arm_F3(fires, tol, nbars):
    """LIMIT-AT-FIRE: resting buy limit at fire_px*(1+tol).  Fill ONLY if the tape trades
    back at/below that limit within nbars 10s bars after the fire bar (bar LOW <= limit).
    Unfilled = no trade.  Entry price = the limit (a resting limit fills at its price)."""
    out = []
    for f in fires:
        lim = round(f["fire_px"] * (1 + tol), 4)
        rb = E.DAYS[(f["sym"], f["date"])][0]
        fi = None
        if f["bar_lo"] <= lim:
            fi = f["i"]                                  # the fire bar itself traded there
        else:
            for j in range(f["i"] + 1, min(f["i"] + 1 + nbars, len(rb))):
                if rb[j]["l"] <= lim: fi = j; break
                if rb[j]["l"] <= f["stop"]: break         # setup broke before the fill
        if fi is None: continue
        g = dict(f); g["i"] = fi
        x = sim_one(g, lim, f["stop"])
        if x: out.append(x)
    return out


def arm_F4(fires):
    """FRESHNESS AGE GUARD — NOT MEASURABLE ON THIS REPLAY.  In the replay every fire is
    evaluated on the bar it completes on, so the modelled fire age is always ~0s and every
    age threshold keeps 100% of fires.  The mechanism it defends against (a stale bar batch
    replayed after a restart/admission, the case CURL_FIRE_MAX_AGE_SECS exists for) has no
    representation in the cache.  Reported NEEDS-DATA, not fabricated."""
    return None


def block(name, trades, dates):
    if not trades:
        P(f"| {name} | 0 | — | — | — | — |"); return dict(N=0, tot=0, dtr=0, worst=0, win=0)
    tot = sum(x["pnl"] for x in trades); n = len(trades)
    win = 100.0 * sum(1 for x in trades if x["pnl"] > 0) / n
    worst = min(x["pnl"] for x in trades)
    P(f"| {name} | {n} | ${tot:+.2f} | ${tot/n:+.2f} | {win:.0f}% | ${worst:+.2f} |")
    return dict(N=n, tot=tot, dtr=tot / n, worst=worst, win=win)


def main():
    fires, dates = collect()
    for f in fires:
        f["drift"] = (f["fill_px"] - f["fire_px"]) / f["fire_px"]
    P(f"kevseq universe fires: {len(fires)}")

    # ── STEP 1a: the modelled drift distribution (the model-validity check) ──
    P("")
    P("### modelled drift (fill-bar close vs detector fire price)")
    ds = sorted(f["drift"] * 100 for f in fires)
    P(f"N={len(ds)} median {statistics.median(ds):+.2f}% p75 {pctile(ds,75):+.2f}% "
      f"p90 {pctile(ds,90):+.2f}% max {max(ds):+.2f}%")
    ir = [(f["fire_px"] - f["stop"]) / f["fire_px"] * 100 for f in fires if f["stop"] < f["fire_px"]]
    ar = [(f["fill_px"] - f["stop"]) / f["fill_px"] * 100 for f in fires if f["stop"] < f["fire_px"]]
    P(f"intended risk median {statistics.median(ir):.2f}%  actual risk median "
      f"{statistics.median(ar):.2f}%  inflation x{statistics.median(ar)/statistics.median(ir):.2f}")
    model_ok = statistics.median(ds) > 0.5
    P(f"MODEL VALIDITY (failure condition #2): median drift {statistics.median(ds):+.2f}% "
      f"-> {'REPRODUCES the live defect' if model_ok else 'DOES NOT reproduce — results VOID'}")

    # how many fires does the 6% min-stop floor refuse at the drifted entry but not at fire?
    dmg = sum(1 for f in fires
              if (f["fire_px"] - f["stop"]) / f["fire_px"] < 0.06 <= (f["fill_px"] - f["stop"]) / f["fill_px"])
    P(f"min-stop(6%) damage on the replay: {dmg} fires refused at the drifted entry that "
      f"the intended (fire-price) trade would have passed")

    mine = [f for f in fires if MINE_LO <= f["date"] <= MINE_HI]
    hold = [f for f in fires if HOLD_LO <= f["date"] <= HOLD_HI]
    P(f"OOS split: MINE {len(mine)} fires / HOLD-OUT {len(hold)} fires")

    res = {}
    for label, cohort in (("MINE", mine), ("HOLD-OUT", hold), ("ALL", fires)):
        P("")
        P(f"### {label}")
        P("| arm | N | total | $/tr | win | worst |")
        P("|---|---|---|---|---|---|")
        r = {}
        r["baseline (today)"] = block("baseline (today: quote entry, structural stop)", arm_baseline(cohort), dates)
        for thr in (0.005, 0.01, 0.02, 0.03, 0.05):
            r[f"F1 drift<={thr:.0%}"] = block(f"F1 DRIFT REFUSE <= {thr:.0%}", arm_F1(cohort, thr), dates)
        r["F2 re-anchor"] = block("F2 RE-ANCHOR STOP (intended risk% preserved)", arm_F2(cohort), dates)
        # tol 0.01 = the LIVE ENTRY_LIMIT_BUFFER the executor already applies (:9399),
        # so F3 needs NO new order type — it only changes which price is handed in.
        for tol in (0.005, 0.01):
            for nb in (0, 3, 6, 18):
                r[f"F3 limit +{tol:.1%} {nb}b"] = block(
                    f"F3 LIMIT-AT-FIRE +{tol:.1%}, {nb} bars ({nb*10}s)",
                    arm_F3(cohort, tol, nb), dates)
        res[label] = r
    P("")
    P("F4 FRESHNESS AGE GUARD: " + arm_F4.__doc__.split("\n")[0] + " (see docstring) — NEEDS-DATA.")

    json.dump({"res": res,
               "drift": {"N": len(ds), "median": statistics.median(ds), "p75": pctile(ds, 75),
                         "p90": pctile(ds, 90), "max": max(ds)},
               "minstop_damage": dmg, "model_ok": model_ok},
              open(HERE + "/entry_drift_20260817_out.json", "w"), indent=1)
    open(HERE + "/entry_drift_20260817_run.txt", "w").write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
