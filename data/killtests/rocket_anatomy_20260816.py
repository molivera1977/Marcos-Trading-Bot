#!/usr/bin/env python3
"""ROCKET ANATOMY STUDY 8/16 — Rocket Rider + Hidden Entry Architect. Analysis only.
Chain reused unchanged: flatten_parity_20260816 (FP, LIVE parity 15:30 cutoff / 15:45 flatten)
-> S -> G -> F -> C -> B -> E. E3 exits (bank 50% @+10%, off10 trail after bank), entry slip +1%,
exit MKT 0.5%, $500 position, halt_rule on. RTH bars only (official book = RTH; PRE separate).
Leg = >=25% low->high within <=300s on >=3x prior-20-min avg per-10s-slot volume.
"""
import importlib.util, os, io, contextlib, json, glob, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("FP", HERE + "/flatten_parity_20260816.py")
FP = importlib.util.module_from_spec(spec); spec.loader.exec_module(FP)
S = FP.S; F = FP.F; E = FP.E; B = FP.B
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)
def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = fn(*a, **k)
    return r

MAN = json.load(open(HERE + "/../universe/manifest.json"))
def day1(sym, date):
    """True if the name did NOT appear in the manifest on a prior date within 5 calendar days."""
    import datetime as dt
    d0 = dt.date.fromisoformat(date)
    for d, rows in MAN.items():
        dd = dt.date.fromisoformat(d)
        if 0 < (d0 - dd).days <= 5 and any(r["sym"] == sym for r in rows): return False
    return True

# ---------------- PART 1: legs ----------------
def slot_vol_prior20(bars, i):
    """avg volume per 10s slot over the 20 min before bar i (time-based, sparse-safe)."""
    s0 = E.secs(bars[i]); v = 0.0; k = i - 1
    while k >= 0 and s0 - E.secs(bars[k]) <= 1200: v += bars[k]["v"]; k -= 1
    if i - 1 - k < 6: return None
    return v / 120.0

def find_legs(bars, gaps):
    legs = []; i = 0; n = len(bars); gap_pre = {pre for pre, post, g in gaps}
    while i < n:
        base = bars[i]["l"]; s0 = E.secs(bars[i]); pv = slot_vol_prior20(bars, i)
        if base <= 0 or pv is None or pv <= 0: i += 1; continue
        hi = base; hj = i; vol = 0.0; j = i; found = None
        while j < n and E.secs(bars[j]) - s0 <= 300:
            if j > i and bars[j]["l"] < base: break     # a lower low: that bar will be its own candidate
            vol += bars[j]["v"]
            if bars[j]["h"] > hi: hi = bars[j]["h"]; hj = j
            slots = max(1, (E.secs(bars[j]) - s0) // 10 + 1)
            if hi / base - 1 >= 0.25 and vol / slots >= 3 * pv:
                found = (j, hi, hj)   # first bar where it qualifies; keep extending for the top
            j += 1
        if found:
            # extend top within the same 300s window (hj already max within window w/o lower low)
            halt = None
            for pre, post, g in gaps:
                if hj <= pre and 0 <= E.secs(bars[pre]) - E.secs(bars[hj]) <= 600: halt = (pre, post, g); break
            legs.append({"i": i, "j": hj, "base": base, "hi": hi, "gain": hi / base - 1,
                         "t": E.hhmm_b(bars[i]), "t_hi": E.hhmm_b(bars[hj]),
                         "dur": E.secs(bars[hj]) - s0, "volx": vol / max(1, (E.secs(bars[hj]) - s0) // 10 + 1) / pv,
                         "halt": halt, "qual_i": found[0]})
            i = hj + 1
        else: i += 1
    return legs

# ---------------- PART 2: precursors on the 6 bars before liftoff ----------------
def precursors(bars, vw, i, sess_hi):
    """returns set of precursor labels for bar i (liftoff = bar i; window = bars i-6..i-1)."""
    if i < 6: return None
    w = bars[i - 6:i]
    if E.secs(w[-1]) - E.secs(w[0]) > 180: return None   # sparse tape: window not comparable
    if E.secs(bars[i]) - E.secs(w[-1]) > 60: return None    # liftoff bar follows a gap/halt: the "60s before" is a halt, not tape
    lo = min(b["l"] for b in w); hi = max(b["h"] for b in w)
    out = set()
    rng = hi / lo - 1 if lo > 0 else 9
    v3a = sum(b["v"] for b in w[:3]); v3b = sum(b["v"] for b in w[3:])
    if rng <= 0.015 and v3b < v3a: out.add("a_coil")
    lows = [b["l"] for b in w]
    if all(b["c"] > vw[i - 6 + k] for k, b in enumerate(w)) and all(lows[k] >= lows[k - 1] for k in range(1, 6)) and lows[-1] > lows[0]:
        out.add("b_vwap_hold")
    if sess_hi and hi <= sess_hi and hi >= sess_hi * 0.99: out.add("c_prior_high_test")
    if sess_hi and hi > sess_hi and w[-1]["c"] >= hi * 0.98: out.add("f_at_new_high")
    vs = [b["v"] for b in w[-3:]]; r3 = max(b["h"] for b in w[-3:]) / min(b["l"] for b in w[-3:]) - 1
    if vs[0] < vs[1] < vs[2] and r3 <= 0.01: out.add("d_vol_prelude")
    if not out: out.add("e_none")
    return out

LABELS = ["a_coil", "b_vwap_hold", "c_prior_high_test", "d_vol_prelude", "f_at_new_high", "e_none"]

# ---------------- PART 3 helpers ----------------
def sim(sym, date, i, entry, stop, det, log=None):
    bars, emas, gaps = E.DAYS[(sym, date)]
    return F.sim_var(bars, emas, gaps, i, entry, stop, "E3", det, True, log)

def grade(name, trades, dates):
    if not trades: P(f"| {name} | 0 | - | - | - | - | - | - |"); return
    d = {dt: 0.0 for dt in dates}
    for x in trades: d[x["date"]] += x["pnl"]
    n = len(dates); vals = [d[k] for k in dates]
    wins = sum(1 for x in trades if x["pnl"] > 0); tot = sum(x["pnl"] for x in trades)
    mid = dates[31] if len(dates) > 31 else dates[n // 2]
    a = [d[k] for k in dates if k < mid]; b = [d[k] for k in dates if k >= mid]
    tdays = sorted({x["date"] for x in trades}); green = sum(1 for k in tdays if d[k] > 0)
    P(f"| {name} | {len(trades)} | {wins} ({100*wins/len(trades):.0f}%) | ${tot:+.2f} | ${tot/len(trades):+.2f} | "
      f"${tot/n:+.2f} ({green}/{len(tdays)} trade-days green) | ${sum(a)/max(1,len(a)):+.2f} / ${sum(b)/max(1,len(b)):+.2f} | "
      f"${min(vals):+.2f} |")

def dedup(sigs, win=300):
    sigs = sorted(sigs, key=lambda s: (s["date"], s["t"], s["sym"])); last = {}; out = []
    for s in sigs:
        k = (s["sym"], s["date"]); ss = B.tsec(s["t"]); ls = last.get(k)
        if ls is not None and ss - ls <= win: continue
        last[k] = ss; out.append(s)
    return out

def run_sigs(sigs, det):
    tr = []
    for s in sigs:
        if s["t"] >= FP.CUTOFF_T: continue
        pnl, ex, xi = sim(s["sym"], s["date"], s["i"], s["entry"], s["stop"], det)
        tr.append({**s, "pnl": pnl, "exit": ex, "xi": xi})
    return tr

def port2(tr, dates, nslots=2):
    tr = sorted(tr, key=lambda x: (x["date"], x["t"])); h4 = []; open_pos = []
    for s in tr:
        bars = E.DAYS[(s["sym"], s["date"])][0]; key = s["date"] + "T" + s["t"]
        open_pos = [p for p in open_pos if p >= key]
        if len(open_pos) >= nslots: continue
        open_pos.append(s["date"] + "T" + E.hhmm_b(bars[min(s["xi"], len(bars) - 1)])); h4.append(s)
    return h4

def first_pullback(bars, leg, max_wait=180, dip=0.03):
    """first higher-low bar after a >=dip pullback from the leg high, within max_wait s of the leg-high bar."""
    j = leg["j"]; hi = leg["hi"]; s_hi = E.secs(bars[j]); dlow = None; dlow_i = None
    for k in range(j + 1, len(bars)):
        if E.secs(bars[k]) - s_hi > max_wait: return None
        b = bars[k]
        if b["h"] > hi: hi = b["h"]; s_hi = E.secs(b); dlow = None; continue   # leg still extending
        if dlow is None or b["l"] < dlow:
            if hi / b["l"] - 1 >= dip or dlow is not None:
                dlow = b["l"] if dlow is None or b["l"] < dlow else dlow; dlow_i = k
            continue
        # b.l >= dlow: higher-low bar (first non-lower low after the dip is established)
        if dlow is not None and b["l"] > dlow and b["c"] > b["o"]:
            return {"i": k, "entry": b["c"], "stop": dlow, "dip_i": dlow_i, "t": E.hhmm_b(b)}
    return None

def day2_reload(bars, vw):
    """9:30-10:30 ET: >=5% push off the RTH open, then a pullback whose low holds above VWAP,
    then the first higher-low bar (close>open) -> entry at close, stop = dip low."""
    o = bars[0]["o"]; hi = o; hi_i = 0; pushed = False; dlow = None; end = 14 * 3600 + 30 * 60
    for k, b in enumerate(bars):
        if E.secs(b) >= end: return None
        if b["h"] > hi:
            hi = b["h"]; hi_i = k; dlow = None
            if hi / o - 1 >= 0.05: pushed = True
            continue
        if not pushed: continue
        if dlow is None or b["l"] < dlow: dlow = b["l"]; continue
        if b["l"] > dlow and b["c"] > b["o"] and hi / dlow - 1 >= 0.02:
            if dlow > vw[k]:
                return {"i": k, "entry": b["c"], "stop": dlow, "t": E.hhmm_b(b), "push": hi / o - 1}
            dlow = None; pushed = pushed  # dip below VWAP: reset, wait for a new dip
    return None

def main():
    E.DAYS.clear(); nf, nd, dates = quiet(S.load_all); FP.set_mode(True)
    P("# ROCKET ANATOMY STUDY — 2026-08-16 (Rocket Rider + Hidden Entry Architect)")
    P(f"universe: {nf} files, {nd} RTH day-files (>=60 bars), {len(dates)} dates {dates[0]}..{dates[-1]}; RTH only; "
      f"chain FP->S->G->F->C->B->E unchanged, E3, +1% entry slip, 0.5% exit mkt, $500, LIVE flatten 15:45, halt_rule on")
    P("leg def: >=25% low->high within <=300s (30x10s) AND leg per-slot volume >= 3x prior-20-min per-slot avg; "
      "liftoff = earliest bar whose low is the base with no lower low inside the leg; one leg per top.")
    # PART 1
    LEGS = []; VW = {}
    for k, (bars, emas, gaps) in sorted(E.DAYS.items()):
        vw = S.vwap_series(bars); VW[k] = vw
        for lg in find_legs(bars, gaps):
            lg["sym"], lg["date"] = k; LEGS.append(lg)
    P(f"\n## PART 1 — CENSUS: {len(LEGS)} vertical legs on {len({(l['sym'],l['date']) for l in LEGS})} name-days "
      f"of {nd} ({100*len({(l['sym'],l['date']) for l in LEGS})/nd:.0f}%), across {len({l['date'] for l in LEGS})} of {len(dates)} dates")
    if LEGS:
        g = [l["gain"] for l in LEGS]; du = [l["dur"] for l in LEGS]
        P(f"leg size: median +{100*statistics.median(g):.0f}%, p90 +{100*sorted(g)[int(0.9*len(g))]:.0f}%, max +{100*max(g):.0f}%; "
          f"median duration {statistics.median(du):.0f}s; median vol-multiple {statistics.median([l['volx'] for l in LEGS]):.1f}x")
    per_day = {}
    for l in LEGS: per_day[l["date"]] = per_day.get(l["date"], 0) + 1
    P("\n### legs per date"); P("| date | legs | names |"); P("|---|---|---|")
    for d in dates:
        ls = [l for l in LEGS if l["date"] == d]
        if ls: P(f"| {d} | {len(ls)} | {', '.join(sorted({l['sym'] for l in ls}))} |")
    P("\n### legs per name (top 15)"); P("| name-day | legs | biggest | halted after |"); P("|---|---|---|---|")
    pn = {}
    for l in LEGS: pn.setdefault((l["sym"], l["date"]), []).append(l)
    for k, ls in sorted(pn.items(), key=lambda kv: -len(kv[1]))[:15]:
        P(f"| {k[0]} {k[1]} | {len(ls)} | +{100*max(l['gain'] for l in ls):.0f}% | {sum(1 for l in ls if l['halt'])} |")
    P("\n### time-of-day (ET)"); P("| window | legs | share |"); P("|---|---|---|")
    bins = [("09:30-09:45", "13:30:00", "13:45:00"), ("09:45-10:00", "13:45:00", "14:00:00"), ("10:00-10:30", "14:00:00", "14:30:00"),
            ("10:30-11:30", "14:30:00", "15:30:00"), ("11:30-13:00", "15:30:00", "17:00:00"), ("13:00-15:00", "17:00:00", "19:00:00"),
            ("15:00-16:00", "19:00:00", "20:00:01")]
    for nm, a, b in bins:
        c = sum(1 for l in LEGS if a <= l["t"] < b); P(f"| {nm} | {c} | {100*c/max(1,len(LEGS)):.0f}% |")
    d1 = [l for l in LEGS if day1(l["sym"], l["date"])]; d2 = [l for l in LEGS if not day1(l["sym"], l["date"])]
    nd1 = sum(1 for k in E.DAYS if day1(*k)); nd2 = nd - nd1
    P(f"\n### day-1 vs day-2+ (name in manifest on a prior date within 5 days)")
    P(f"day-1 name-days {nd1}: {len(d1)} legs ({len(d1)/max(1,nd1):.2f}/name-day) | day-2+ name-days {nd2}: {len(d2)} legs ({len(d2)/max(1,nd2):.2f}/name-day)")
    res = 0; inside = 0
    for l in LEGS:
        bars, emas, gaps = E.DAYS[(l["sym"], l["date"])]
        if l["i"] > 0 and E.secs(bars[l["i"]]) - E.secs(bars[l["i"] - 1]) >= 240: res += 1; l["resume"] = True
        if any(l["i"] <= pre < l["j"] for pre, post, g in gaps): inside += 1; l["gap_inside"] = True
    P(f"\n### halt-built legs: {res} of {len(LEGS)} legs START on a halt-resumption bar (prior bar >=4 min earlier); "
      f"{inside} legs contain a >=4-min gap INSIDE the leg (the 'instant squeeze' = mostly a halt gap-up); "
      f"{sum(1 for l in LEGS if not l.get('resume') and not l.get('gap_inside'))} legs are pure-tape (no gap at start or inside)")
    nh = sum(1 for l in LEGS if l["halt"])
    P(f"\n### halts: {nh} of {len(LEGS)} legs ({100*nh/max(1,len(LEGS)):.0f}%) followed by a >=4-min zero-trade gap within 10 min of the leg high")
    if LEGS:
        big = [l for l in LEGS if l["gain"] >= 0.5]
        P(f"of legs >=+50% ({len(big)}): {sum(1 for l in big if l['halt'])} halted ({100*sum(1 for l in big if l['halt'])/max(1,len(big)):.0f}%)")

    # PART 2
    P("\n## PART 2 — THE 60 SECONDS BEFORE (6 bars preceding liftoff) vs base rate over ALL comparable RTH bars")
    rock = {L: 0 for L in LABELS}; nrock = 0; nsparse = 0
    for l in LEGS:
        bars = E.DAYS[(l["sym"], l["date"])][0]; vw = VW[(l["sym"], l["date"])]
        sh = max((b["h"] for b in bars[:l["i"] - 6]), default=None)
        pr = precursors(bars, vw, l["i"], sh)
        l["pre"] = pr
        if pr is None: nsparse += 1; continue
        nrock += 1
        for L in pr: rock[L] += 1
    base = {L: 0 for L in LABELS}; nbase = 0; fwd = {L: [0, 0] for L in LABELS}   # fires, fires followed by a leg start within 300s
    LEGSTART = {}
    for l in LEGS: LEGSTART.setdefault((l["sym"], l["date"]), []).append(E.secs(E.DAYS[(l["sym"], l["date"])][0][l["i"]]))
    for k, (bars, emas, gaps) in E.DAYS.items():
        vw = VW[k]; sh = 0.0; starts = LEGSTART.get(k, [])
        for i in range(6, len(bars)):
            sh = max(sh, bars[i - 7]["h"]) if i > 6 else 0.0
            if slot_vol_prior20(bars, i) is None: continue
            pr = precursors(bars, vw, i, sh if sh else None)
            if pr is None: continue
            nbase += 1; s = E.secs(bars[i])
            hit = any(0 <= st - s <= 300 for st in starts)
            for L in pr:
                base[L] += 1; fwd[L][0] += 1; fwd[L][1] += int(hit)
    P(f"rockets with a comparable 6-bar window: {nrock} (sparse-tape/too-early excluded: {nsparse}); comparable base bars: {nbase}")
    P("| precursor | among rockets | base rate (all bars) | enrichment | fires -> leg starts within 5 min (precision) |")
    P("|---|---|---|---|---|")
    best = None
    for L in LABELS:
        pr_ = rock[L] / max(1, nrock); pb = base[L] / max(1, nbase); enr = pr_ / pb if pb else float("nan")
        prec = fwd[L][1] / max(1, fwd[L][0])
        P(f"| {L} | {rock[L]} ({100*pr_:.1f}%) | {base[L]} ({100*pb:.1f}%) | {enr:.2f}x | {fwd[L][1]}/{fwd[L][0]} ({100*prec:.2f}%) |")
        if L != "e_none" and (best is None or enr > best[1]): best = (L, enr, prec)
    P(f"best (by enrichment, e_none excluded): {best[0]} at {best[1]:.2f}x, precision {100*best[2]:.2f}%")

    # PART 3
    P("\n## PART 3 — THREE ENTRY PHILOSOPHIES (E3, +1% chase slip, LIVE flatten, halt_rule on, $500)")
    P("| philosophy | N | wins | total $ | $/trade | $/date (62 dates) | OOS $/date first-31 / last-31 | worst date |")
    P("|---|---|---|---|---|---|---|---|")
    # (i) anticipate: enter on every fire of the best precursor (population), dedup 5-min same-name
    bl = best[0]; asig = []
    for k, (bars, emas, gaps) in E.DAYS.items():
        vw = VW[k]; sh = 0.0
        for i in range(6, len(bars)):
            sh = max(sh, bars[i - 7]["h"]) if i > 6 else 0.0
            if slot_vol_prior20(bars, i) is None: continue
            pr = precursors(bars, vw, i, sh if sh else None)
            if pr and bl in pr:
                stop = min(b["l"] for b in bars[i - 6:i]); entry = bars[i - 1]["c"]
                if entry / stop - 1 < 0.005: stop = entry * 0.98   # degenerate coil: 2% stop floor
                asig.append({"sym": k[0], "date": k[1], "i": i - 1, "entry": entry, "stop": stop, "t": E.hhmm_b(bars[i - 1])})
    asig = dedup(asig); atr = run_sigs(asig, "anticipate")
    grade(f"(i) ANTICIPATE on {bl} (all fires)", atr, dates)
    # anticipate, rockets only (what it would have been with perfect foresight — reference, not tradeable)
    rk = {(l["sym"], l["date"], l["i"]) for l in LEGS}
    atr_r = [x for x in atr if any((x["sym"], x["date"], j) in rk for j in range(x["i"], x["i"] + 4))]
    grade(f"    ..of which fired at a real liftoff (foresight, NOT tradeable)", atr_r, dates)
    grade(f"    (i) 2-SLOT portfolio (first-fill-wins, capacity 2)", port2(atr, dates), dates)
    # (ii) first pullback
    psig = []; pmiss = 0
    for l in LEGS:
        bars = E.DAYS[(l["sym"], l["date"])][0]; fp = first_pullback(bars, l)
        if fp is None: pmiss += 1; continue
        l["pb"] = fp
        psig.append({"sym": l["sym"], "date": l["date"], "i": fp["i"], "entry": fp["entry"], "stop": fp["stop"], "t": fp["t"], "leg": l})
    ptr = run_sigs(dedup(psig), "pullback")
    for x in ptr: x["leg"]["pbtr"] = x
    grade("(ii) FIRST-PULLBACK after leg (>=3% dip, higher-low bar, <=3 min)", ptr, dates)
    grade(f"    (ii) 2-SLOT portfolio", port2(ptr, dates), dates)
    P(f"  pullback found on {len(psig)} of {len(LEGS)} legs ({pmiss} legs: no qualifying pullback within 3 min = kept running/halted/faded straight)")
    # (iii) day-2 reload
    import datetime as dt
    rdays = sorted({(l["sym"], l["date"]) for l in LEGS}); dsig = []; nod2 = 0; nosetup = 0
    for sym, d in rdays:
        d1_ = (dt.date.fromisoformat(d) + dt.timedelta(days=1))
        while d1_.weekday() >= 5: d1_ += dt.timedelta(days=1)
        k2 = (sym, d1_.isoformat())
        if k2 not in E.DAYS: nod2 += 1; continue
        bars = E.DAYS[k2][0]; r = day2_reload(bars, VW[k2])
        if r is None: nosetup += 1; continue
        dsig.append({"sym": sym, "date": k2[1], "i": r["i"], "entry": r["entry"], "stop": r["stop"], "t": r["t"], "push": r["push"]})
    dtr = run_sigs(dedup(dsig), "day2")
    grade("(iii) DAY-2 RELOAD (>=5% push, VWAP-holding pullback, 9:30-10:30)", dtr, dates)
    P(f"  rocket name-days {len(rdays)}: next-day bars in cache for {len(rdays)-nod2} (day-2 not in the runner universe: {nod2}); "
      f"setup found {len(dsig)}, no setup {nosetup}")
    # control: same day-2 template on ALL day-2+ name-days (not just post-rocket)
    csig = []
    for k, (bars, emas, gaps) in E.DAYS.items():
        if day1(*k): continue
        r = day2_reload(bars, VW[k])
        if r: csig.append({"sym": k[0], "date": k[1], "i": r["i"], "entry": r["entry"], "stop": r["stop"], "t": r["t"]})
    ctr = run_sigs(dedup(csig), "day2")
    grade("    control: same template on ALL day-2+ name-days", ctr, dates)

    # PART 4
    P("\n## PART 4 — HALT INTERACTION (first-pullback philosophy)")
    hl = [l for l in LEGS if l["halt"]]; ent = [l for l in hl if "pbtr" in l]
    trapped = []
    for l in ent:
        bars = E.DAYS[(l["sym"], l["date"])][0]; pre = l["halt"][0]
        if l["pbtr"]["i"] <= pre and l["pbtr"]["xi"] >= l["halt"][1]: trapped.append(l)   # in the trade across the gap
    P(f"legs followed by halt: {len(hl)}; pullback entry taken on {len(ent)}; entered BEFORE the halt and still in across it (trapped): {len(trapped)}")
    if ent:
        pe = [l["pbtr"]["pnl"] for l in ent]; P(f"pullback trades on halted legs: N={len(ent)} total ${sum(pe):+.2f}, mean ${sum(pe)/len(pe):+.2f}, wins {sum(1 for p in pe if p>0)}")
    if trapped:
        pt = [l["pbtr"]["pnl"] for l in trapped]; P(f"trapped-across-halt: N={len(trapped)} total ${sum(pt):+.2f}, mean ${sum(pt)/len(pt):+.2f}, wins {sum(1 for p in pt if p>0)}; "
          f"exits: {dict((e, sum(1 for l in trapped if l['pbtr']['exit'].split('@')[0]==e)) for e in {l['pbtr']['exit'].split('@')[0] for l in trapped})}")
    nh_ = [l for l in LEGS if not l["halt"] and "pbtr" in l]
    if nh_:
        pn_ = [l["pbtr"]["pnl"] for l in nh_]; P(f"pullback trades on NON-halted legs: N={len(nh_)} total ${sum(pn_):+.2f}, mean ${sum(pn_)/len(pn_):+.2f}, wins {sum(1 for p in pn_ if p>0)}")
    # serial halts: 2+ gaps on the day
    ser = [l for l in ent if sum(1 for g in E.DAYS[(l['sym'], l['date'])][2]) >= 2]
    if ser:
        ps = [l["pbtr"]["pnl"] for l in ser]; P(f"pullback trades on halted legs on SERIAL-halt days (>=2 gaps): N={len(ser)} total ${sum(ps):+.2f}, mean ${sum(ps)/len(ps):+.2f}")

    # HAND TRACES
    P("\n## HAND TRACES (one per philosophy; sim log verbatim)")
    def trace(x, det, title):
        bars = E.DAYS[(x["sym"], x["date"])][0]; log = []
        pnl, ex, xi = sim(x["sym"], x["date"], x["i"], x["entry"], x["stop"], det, log)
        P(f"\n### {title}: {x['sym']} {x['date']} entry bar {x['t']} sig {x['entry']:.4f} (fill {x['entry']*1.01:.4f}) stop {x['stop']:.4f} -> ${pnl:+.2f} [{ex}]")
        for m in log[:12]: P("  " + m)
    pick = [x for x in ptr if x["sym"] == "SCKT"] or sorted([x for x in ptr if x["leg"].get("pre")], key=lambda x: -x["leg"]["gain"])[:1]
    P(f"SCKT in cache: {[k for k in E.DAYS if k[0]=='SCKT']}; SCKT legs found: {sum(1 for l in LEGS if l['sym']=='SCKT')}; XHD in cache: {[k for k in E.DAYS if k[0]=='XHD']}")
    if pick:
        l = pick[0]["leg"]; bars = E.DAYS[(l["sym"], l["date"])][0]
        P(f"\nrocket: {l['sym']} {l['date']} liftoff {l['t']} base {l['base']:.4f} -> top {l['hi']:.4f} at {l['t_hi']} (+{100*l['gain']:.0f}% in {l['dur']}s, {l['volx']:.1f}x vol), halt after: {bool(l['halt'])}, precursors: {sorted(l.get('pre') or ['(sparse)'])}")
        P("  6 bars before liftoff (t o h l c v):")
        for b in bars[max(0, l["i"] - 6):l["i"] + 1]: P(f"    {E.hhmm_b(b)} {b['o']:.4f} {b['h']:.4f} {b['l']:.4f} {b['c']:.4f} {b['v']:.0f}")
        trace(pick[0], "pullback", "(ii) FIRST-PULLBACK")
    if atr:
        ax = [x for x in atr if x["sym"] == pick[0]["sym"] and x["date"] == pick[0]["date"]] if pick else []
        trace((ax or atr)[0], "anticipate", "(i) ANTICIPATE")
    if dtr: trace(max(dtr, key=lambda x: abs(x["pnl"])), "day2", "(iii) DAY-2 RELOAD")
    json.dump({"legs": [{k: v for k, v in l.items() if k in ("sym", "date", "t", "t_hi", "base", "hi", "gain", "dur", "volx")} | {"halt": bool(l["halt"]), "pre": sorted(l.get("pre") or [])} for l in LEGS],
               "anticipate": [{k: x[k] for k in ("sym", "date", "t", "entry", "stop", "pnl", "exit")} for x in atr],
               "pullback": [{k: x[k] for k in ("sym", "date", "t", "entry", "stop", "pnl", "exit")} for x in ptr],
               "day2": [{k: x[k] for k in ("sym", "date", "t", "entry", "stop", "pnl", "exit")} for x in dtr]},
              open(HERE + "/rocket_anatomy_20260816_rows.json", "w"), indent=0)
    open(HERE + "/rocket_anatomy_20260816_RESULTS.txt", "w").write("\n".join(OUT))

if __name__ == "__main__": main()
