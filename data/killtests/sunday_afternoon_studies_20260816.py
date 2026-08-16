#!/usr/bin/env python3
"""SUNDAY AFTERNOON STUDIES 8/16 (agenda item 3 + registry quick-checks), PRE-REGISTERED.
Imports edge_stresstest_G_20260815.py (-> F -> C -> B -> engine of record) UNCHANGED.
Universe = FULL bars10s cache (every file, every date). All exits = E3 via F.sim_var
(bank 1/2 at +10%, trail rest 10%-off-high closes-through, stop-first, -1% chase entry,
-0.5% market-exit slip; grinder lane keeps its 19:59Z flatten, other lanes exit at the
last RTH bar). Times below are UTC strings from the bars ("Z"); ET = UTC-4 all summer.
  T1 power-hour join / new-high-after-15:00 test
  T2 halt-resumption retest (KT1b) at full cache, up vs down halts
  T3 flat_top break-attack UNWINDOWED per window + survivor precondition (13:00-15:00 cell)
  T4 afternoon VWAP reclaim (band-pass) 12:00-14:30 leaders-only cell (+chop excl, +2-bars-below)
  T5 ORB fair re-run, 5-min and 15-min ranges, separate tests
  T6 registry quick-checks: (a) failed-break exit (b) no-progress 15-min rule (c) volume clause
Analysis only. Day-gain reference = first bar of the file (premarket 08:00Z open) — the
cache carries no prior close; disclosed as a caveat.
"""
import importlib.util, json, os, glob, statistics
from bisect import bisect_left
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("G", HERE + "/edge_stresstest_G_20260815.py")
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
F = G.F; C = G.C; B = G.B; E = G.E
MKT = 0.005; SLIP = 0.01
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

# ---------------- load full cache ----------------
REF = {}     # (sym,date) -> first-bar open of the whole file (premarket ref)
FULL = {}    # (sym,date) -> full-day bars
def load_all():
    files = sorted(glob.glob(E.BARS_DIR + "/*.json"))
    n = 0
    for f in files:
        sym, date, bars = E.load(f)
        if not bars: continue
        FULL[(sym, date)] = bars
        REF[(sym, date)] = bars[0]["o"]
        rb = E.rth(bars)
        if len(rb) < 60: continue
        emas = E.ema_series([b["c"] for b in rb], 90)
        gaps = E.find_gaps(rb)
        E.DAYS[(sym, date)] = (rb, emas, gaps); n += 1
    dates = sorted({d for _, d in E.DAYS})
    return len(files), n, dates

def vwap_series(bars):
    cv = cpv = 0.0; out = []
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cv += b["v"]; cpv += tp * b["v"]
        out.append(cpv / cv if cv else b["c"])
    return out

# ---------------- stats helpers ----------------
def daily(trades, dates):
    d = {dt: 0.0 for dt in dates}
    for x in trades: d[x["date"]] += x["pnl"]
    return d

def stats(name, trades, dates, bar=False):
    d = daily(trades, dates); vals = [d[k] for k in dates]; n = len(vals)
    sv = sorted(vals); med = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
    N = len(trades); tot = sum(x["pnl"] for x in trades)
    mid = dates[n // 2]
    h1 = sum(d[k] for k in dates if k < mid); h2 = sum(d[k] for k in dates if k >= mid)
    green = sum(1 for v in vals if v > 0)
    row = dict(N=N, win=(100 * sum(1 for x in trades if x["pnl"] > 0) / N) if N else 0.0,
               total=tot, mean_tr=(tot / N) if N else 0.0, dmean=sum(vals) / n, dmed=med,
               worst=min(vals), green=100 * green / n, h1=h1, h2=h2)
    line = (f"| {name} | {N} | {row['win']:.0f}% | ${tot:+.2f} | ${row['mean_tr']:+.2f} | "
            f"${row['dmean']:+.2f} | ${row['dmed']:+.2f} | ${row['worst']:+.2f} |")
    if bar:
        ok = (row["dmean"] > 50 and row["dmed"] > 50 and green / n >= 0.55 and h1 > 0 and h2 > 0 and min(vals) > -300)
        line += f" green {row['green']:.0f}% halves ${h1:+.0f}/${h2:+.0f} -> {'PASS' if ok else 'FAIL'} |"
        row["bar"] = ok
    P(line); return row

HDR = "| cohort | N | win | total | mean/tr | day mean | day median | worst day |"
SEP = "|---|---|---|---|---|---|---|---|"

def e3(sym, date, i, entry, stop, det, log=None):
    bars, emas, gaps = E.DAYS[(sym, date)]
    return F.sim_var(bars, emas, gaps, i, entry, stop, "E3", det, True, log)

def run(sigs, det_override=None):
    """E3 every signal, dedup same-name<=5min like round F, return trades."""
    tr = []
    for s in sigs:
        det = det_override or s["det"]
        pnl, exx, xi = e3(s["sym"], s["date"], s["i"], s["entry"], s["stop"], det)
        tr.append({**s, "pnl": pnl, "exit": exx, "xi": xi, "fill_t": s["t"], "fill_key": s["key"]})
    return F.dedup(tr)

def mk(sym, date, det, i, entry, stop, **kw):
    bars = E.DAYS[(sym, date)][0]; hh = E.hhmm_b(bars[i])
    return {"sym": sym, "date": date, "det": det, "i": i, "t": hh, "key": date + "T" + hh,
            "entry": entry, "stop": stop, **kw}

WINDOWS = [("09:30-10:30", "13:30:00", "14:30:00"), ("10:30-12:00", "14:30:00", "16:00:00"),
           ("12:00-13:00", "16:00:00", "17:00:00"), ("13:00-15:00", "17:00:00", "19:00:00"),
           ("15:00-16:00", "19:00:00", "20:00:01")]
def win_of(hh):
    for nm, a, b in WINDOWS:
        if a <= hh < b: return nm
    return "other"

# ---------------- detectors with extra annotation ----------------
def det_flat_top_break_lvl(bars, emas, gaps):
    """G.det_flat_top_break logic verbatim + returns level (base high) & signal-bar index."""
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
            if b["c"] > level:
                if E.secs(b) < cooldown_until:
                    state = "seek"; level = None; base_lo = None; continue
                entry = b["c"]; stop = base_lo
                if stop < entry:
                    pnl, ex, xi = E.base_sim(bars, emas, gaps, i, entry, stop, "flat_top")
                    trades.append({"i": i, "entry": entry, "stop": stop, "level": level})
                    open_until = xi
                    cooldown_until = E.secs(b) + 900
                state = "seek"; level = None; base_lo = None
    return trades

def det_vwap_ann(bars, emas, gaps):
    """E.det_vwap logic verbatim + annotations: bars_below (consecutive closes <= vwap
    before this episode) and crosses20 (VWAP side flips in prior 120 bars)."""
    trades = []
    cpv = 0.0; cv = 0.0; streak = 0; hold_low = None; hold_high = None
    prev_above = None; open_until = -1; rej_open_until = -1; episode_fired = False
    below_run = 0; ep_below = 0; sides = []
    for i, b in enumerate(bars):
        cpv += b["c"] * b["v"]; cv += b["v"]
        if cv <= 0: continue
        vwap = cpv / cv
        above = b["c"] > vwap
        sides.append(above)
        if above:
            if not prev_above:
                streak = 1; hold_low = b["l"]; hold_high = b["h"]; episode_fired = False
                ep_below = below_run; below_run = 0
            else:
                if (not episode_fired) and streak >= 1 and b["h"] > hold_high:
                    entry = b["c"]; stop = hold_low
                    if stop < entry:
                        if 12 <= streak <= 30 and i > open_until:
                            episode_fired = True
                            pnl, ex, xi = E.base_sim(bars, emas, gaps, i, entry, stop, "vwap")
                            w = sides[max(0, len(sides) - 121):-1]
                            crosses = sum(1 for k in range(1, len(w)) if w[k] != w[k - 1])
                            trades.append({"i": i, "entry": entry, "stop": stop,
                                           "bars_below": ep_below, "crosses20": crosses})
                            open_until = xi
                        elif streak < 12 and i > rej_open_until:
                            episode_fired = True
                            pnl, ex, xi = E.base_sim(bars, emas, gaps, i, entry, stop, "vwap")
                            rej_open_until = xi
                streak += 1
                hold_low = min(hold_low, b["l"]); hold_high = max(hold_high, b["h"])
        else:
            streak = 0; hold_low = None; hold_high = None; below_run += 1
        prev_above = above
    return trades

# ---------------- E3 with forced-exit rules (T6) ----------------
def sim_e3_rule(bars, emas, gaps, entry_i, sig_px, stop, det, rule=None, level=None, log=None):
    """F.sim_var E3 semantics + optional rule:
       'failed_break': first COMPLETED 3-min bar starting after the entry bar closes < level -> market exit at that bar's last 10s close
       'noprog15': if by 900s after entry run_hi < entry_px + 1R -> market exit at first bar >= 900s"""
    entry_px = sig_px * (1 + SLIP); sh = E.POS / entry_px; rem = sh; pnl = 0.0; scaled = False
    bank_sh = sh * 0.5; target = entry_px * 1.10; run_hi = entry_px
    flatten = (det == "grinder"); e_s = E.secs(bars[entry_i])
    my_gaps = {post: pre for pre, post, g in gaps if entry_i <= pre and 0 <= E.secs(bars[pre]) - e_s <= 120}
    R = entry_px - stop
    force_i = None
    if rule == "failed_break":
        m3 = E.agg3min(bars)
        et = bars[entry_i]["t"]
        for x in m3:
            if x["t"] > et:            # first 3-min bar that STARTS after the entry bar
                if x["c"] < level:
                    # index of that bar's last 10s bar
                    force_i = next(k for k in range(entry_i + 1, len(bars)) if bars[k]["t"] == x["end_t"])
                break
    def L(m):
        if log is not None: log.append(m)
    for i in range(entry_i + 1, len(bars)):
        b = bars[i]; hh = E.hhmm_b(b)
        if flatten and hh >= "19:59:00":
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px); L(f"{hh} FLATTEN"); return pnl, "eod", i
        if i in my_gaps and b["o"] < stop:
            px = b["o"] * (1 - MKT); pnl += rem * (px - entry_px); L(f"{hh} HALT-GAP {px:.4f}"); return pnl, f"haltgap@{hh}", i
        if b["l"] <= stop:
            px = stop * (1 - MKT); pnl += rem * (px - entry_px); L(f"{hh} STOP {stop:.4f} fill {px:.4f}"); return pnl, f"stop@{hh}", i
        if not scaled and b["h"] >= target:
            pnl += bank_sh * (target - entry_px); rem -= bank_sh; scaled = True; L(f"{hh} BANK 1/2 at {target:.4f}"); continue
        run_hi = max(run_hi, b["h"])
        if rule == "failed_break" and force_i is not None and i >= force_i:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} FAILED-BREAK exit close {b['c']:.4f} < level {level:.4f} fill {px:.4f}"); return pnl, f"fbexit@{hh}", i
        if rule == "noprog15" and E.secs(b) - e_s >= 900 and run_hi < entry_px + R and not scaled:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{hh} NO-PROGRESS exit (runhi {run_hi:.4f} < +1R {entry_px + R:.4f}) fill {px:.4f}"); return pnl, f"npexit@{hh}", i
        if scaled and b["c"] < run_hi * 0.90:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px); L(f"{hh} TRAIL close {b['c']:.4f} runhi {run_hi:.4f} fill {px:.4f}"); return pnl, f"trail@{hh}", i
    b = bars[-1]; px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px); L(f"{E.hhmm_b(b)} EOD {px:.4f}")
    return pnl, "eod", len(bars) - 1

# ================= MAIN =================
def main():
    nfiles, nday, dates = load_all()
    P(f"# Sunday afternoon studies 2026-08-16 — engine chain G->F->C->B->E, E3 exits, FULL cache")
    P(f"FILES: {nfiles} in data/universe/bars10s; usable RTH days (>=60 bars): {nday}; DATES: {len(dates)} {dates[0]}..{dates[-1]}")
    P(f"day-gain reference = first bar open of each file (premarket ~08:00Z); no prior close in cache (CAVEAT)")
    P("")
    # ---- generate all lanes' signals unwindowed ----
    lanes = {"grinder": [], "flat_top_break": [], "band_pass": [], "v2cal": []}
    for (sym, date), (bars, emas, gaps) in sorted(E.DAYS.items()):
        for t in C.det_grinder_1030(bars, emas, gaps):
            lanes["grinder"].append(mk(sym, date, "grinder", t["i"], t["entry"], t["stop"]))
        for t in det_flat_top_break_lvl(bars, emas, gaps):
            lanes["flat_top_break"].append(mk(sym, date, "flat_top", t["i"], t["entry"], t["stop"], level=t["level"]))
        for t in det_vwap_ann(bars, emas, gaps):
            lanes["band_pass"].append(mk(sym, date, "vwap", t["i"], t["entry"], t["stop"],
                                          bars_below=t["bars_below"], crosses20=t["crosses20"]))
        for t in B.det_v2_cal(bars, emas, gaps):
            lanes["v2cal"].append(mk(sym, date, "v2", t["i"], t["entry"], t["stop"]))
    # sanity: annotated detectors reproduce the engine's signal sets
    nb = sum(len(E.det_vwap(*E.DAYS[k])) for k in E.DAYS); nf = sum(len(G.det_flat_top_break(*E.DAYS[k])) for k in E.DAYS)
    P(f"detector parity: band_pass ann={len(lanes['band_pass'])} vs engine={nb}; flat_top_break ann={len(lanes['flat_top_break'])} vs G={nf}")

    # ================= T1 =================
    P("\n## T1 — POWER-HOUR JOIN (every lane, unwindowed signals, bucketed by SIGNAL time ET, E3 exits, dedup same-name<=5min)")
    P("(grinder lane fires only post-10:30 by spec and flattens 15:59; per-lane tables, no capacity)")
    tr_by_lane = {}
    for ln, sigs in lanes.items():
        tr = run(sigs); tr_by_lane[ln] = tr
        P(f"\n### {ln}  (N={len(tr)})"); P(HDR); P(SEP)
        for nm, a, b in WINDOWS:
            sub = [x for x in tr if a <= x["t"] < b]
            if sub: stats(nm, sub, dates)
            else: P(f"| {nm} | 0 | - | - | - | - | - | - |")
        stats("ALL", tr, dates)
    # article claim: new session high after 15:00 ET (19:00Z)?
    P("\n### 'No new high after 15:00' claim — direct test on the cache")
    def nh_stats(label, keys):
        n = 0; nh = 0; nh_pm = 0
        for k in keys:
            bars = E.DAYS[k][0]
            pre = [b["h"] for b in bars if E.hhmm_b(b) < "19:00:00"]; post = [b["h"] for b in bars if E.hhmm_b(b) >= "19:00:00"]
            if not pre or not post: continue
            n += 1
            if max(post) > max(pre): nh += 1
            fpre = max(b["h"] for b in FULL[k] if E.hhmm_b(b) < "19:00:00")
            if max(post) > fpre: nh_pm += 1
        P(f"| {label} | {n} | {nh} | {100*nh/n:.1f}% | {nh_pm} | {100*nh_pm/n:.1f}% |")
    P("| cohort | days | new RTH high after 15:00 | % | new high incl. premarket | % |"); P("|---|---|---|---|---|---|")
    allk = sorted(E.DAYS)
    nh_stats("all universe days", allk)
    run20 = [k for k in allk if max(b["h"] for b in E.DAYS[k][0]) / REF[k] - 1 >= 0.20]
    nh_stats("runner-days (RTH high >= +20% vs file-open ref)", run20)
    run50 = [k for k in allk if max(b["h"] for b in E.DAYS[k][0]) / REF[k] - 1 >= 0.50]
    nh_stats("runner-days (>= +50%)", run50)
    strong = [k for k in allk if E.DAYS[k][0][-1]["c"] / REF[k] - 1 >= 0.20]
    nh_stats("closed >= +20% (strong close)", strong)
    # T1 hand-trace: one 15:00-16:00 grinder trade
    ph = [x for x in tr_by_lane["grinder"] if x["t"] >= "19:00:00"]
    if ph:
        x = max(ph, key=lambda z: abs(z["pnl"])); log = []
        e3(x["sym"], x["date"], x["i"], x["entry"], x["stop"], "grinder", log)
        P(f"\nT1 hand-trace (largest |pnl| power-hour grinder): {x['sym']} {x['date']} sig {x['t']}Z entry {x['entry']:.4f} stop {x['stop']:.4f} -> ${x['pnl']:+.2f} {x['exit']}")
        for m in log: P("    " + m)

    # ================= T2 =================
    P("\n## T2 — HALT-RESUMPTION RETEST (KT1b) at full cache, E3 exits")
    P("halt = zero-trade gap >= 240s in RTH (pre-bar 13:30-19:45Z) with pre AND post bar volume >= 5x day median 10s volume (KT1 definition); up-halt = resumption close > pre-halt close")
    res = {"b": [], "a": [], "c": []}; nh = 0
    for k, (bars, emas, gaps) in sorted(E.DAYS.items()):
        med = statistics.median(b["v"] for b in bars) or 1.0
        for i in range(1, len(bars)):
            pre, post = bars[i - 1], bars[i]
            if not ("13:30:00" <= E.hhmm_b(pre) < "19:45:00"): continue
            if E.secs(post) - E.secs(pre) < 240: continue
            if not (pre["v"] >= 5 * med and post["v"] >= 5 * med): continue
            nh += 1
            up = post["c"] > pre["c"]
            base = dict(sym=k[0], date=k[1], up=up)
            if post["l"] < post["c"]:
                pnl, ex, xi = e3(k[0], k[1], i, post["c"], post["l"], "halt")
                res["c"].append({**base, "pnl": pnl, "t": E.hhmm_b(post)})
            if post["c"] > post["o"] and post["c"] > pre["c"] and post["l"] < post["c"]:
                pnl, ex, xi = e3(k[0], k[1], i, post["c"], post["l"], "halt")
                res["a"].append({**base, "pnl": pnl, "t": E.hhmm_b(post)})
            r_open = post["o"]; dip_low = None; prev = post
            for j in range(i + 1, min(i + 60, len(bars))):
                b = bars[j]
                if b["l"] < r_open: break
                if b["l"] < prev["l"]:
                    dip_low = b["l"] if dip_low is None else min(dip_low, b["l"])
                elif dip_low is not None and b["c"] > prev["h"]:
                    log = []
                    pnl, ex, xi = e3(k[0], k[1], j, b["c"], dip_low, "halt", log)
                    res["b"].append({**base, "pnl": pnl, "t": E.hhmm_b(b), "i": j, "entry": b["c"], "stop": dip_low,
                                     "exit": ex, "log": log, "resume_t": E.hhmm_b(post), "r_open": r_open, "prev_h": prev["h"]})
                    break
                prev = b
    P(f"halts detected: {nh}; retest entries: {len(res['b'])} (up {sum(1 for x in res['b'] if x['up'])} / down {sum(1 for x in res['b'] if not x['up'])})")
    P(HDR); P(SEP)
    rb = stats("(b) resumption retest ALL", res["b"], dates, bar=True)
    stats("(b) up-halts", [x for x in res["b"] if x["up"]], dates)
    stats("(b) down-halts", [x for x in res["b"] if not x["up"]], dates)
    stats("(a) gap-up-go (reference)", res["a"], dates)
    stats("(c) control every resumption (reference)", res["c"], dates)
    if res["b"]:
        x = max(res["b"], key=lambda z: abs(z["pnl"]))
        P(f"\nT2 hand-trace: {x['sym']} {x['date']} resumption {x['resume_t']}Z open {x['r_open']:.4f}; reclaim bar {x['t']}Z close {x['entry']:.4f} > prior high {x['prev_h']:.4f}; stop {x['stop']:.4f} -> ${x['pnl']:+.2f} {x['exit']}")
        for m in x["log"]: P("    " + m)

    # ================= T3 =================
    P("\n## T3 — MIDDAY RANGE BREAKOUT: flat_top break-attack UNWINDOWED, per window (E3)")
    ftb = tr_by_lane["flat_top_break"]
    P(HDR); P(SEP)
    for nm, a, b in WINDOWS:
        sub = [x for x in ftb if a <= x["t"] < b]
        if sub: stats(nm, sub, dates)
    stats("ALL windows", ftb, dates, bar=True)
    # survivor precondition on 13:00-15:00 cell (needs 11:30-13:00 window complete)
    def survivor(x, frac=1.0):
        bars = E.DAYS[(x["sym"], x["date"])][0]; vw = vwap_series(bars)
        w = [(b, v) for b, v in zip(bars, vw) if "15:30:00" <= E.hhmm_b(b) < "17:00:00"]
        if not w: return False
        held = sum(1 for b, v in w if b["c"] > v) / len(w) >= frac
        gain = x["entry"] / REF[(x["sym"], x["date"])] - 1 >= 0.20
        return held and gain
    cell = [x for x in ftb if "17:00:00" <= x["t"] < "19:00:00"]
    surv = [x for x in cell if survivor(x)]; nons = [x for x in cell if not survivor(x)]
    surv90 = [x for x in cell if survivor(x, 0.90)]
    P("\n### 13:00-15:00 lunch-consolidation cell: survivor precondition (held above VWAP 11:30-13:00 AND >= +20% day gain at signal)")
    P(HDR); P(SEP)
    stats("cell, no precondition", cell, dates, bar=True)
    stats("SURVIVOR (100% closes > VWAP 11:30-13:00, gain>=+20%)", surv, dates, bar=True)
    stats("survivor loose (>=90% closes > VWAP)", surv90, dates)
    stats("NON-survivor", nons, dates)
    surv_all = [x for x in ftb if x["t"] >= "17:00:00" and survivor(x)]
    stats("survivor, all signals >= 13:00", surv_all, dates)
    if cell:
        x = max(cell, key=lambda z: z["pnl"]); log = []
        e3(x["sym"], x["date"], x["i"], x["entry"], x["stop"], "flat_top", log)
        P(f"\nT3 hand-trace (best 13:00-15:00 break-attack): {x['sym']} {x['date']} sig {x['t']}Z level {x['level']:.4f} entry {x['entry']:.4f} stop {x['stop']:.4f} survivor={survivor(x)} -> ${x['pnl']:+.2f} {x['exit']}")
        for m in log: P("    " + m)

    # ================= T4 =================
    P("\n## T4 — AFTERNOON VWAP RECLAIM (band-pass 12-30 bars) 12:00-14:30 ET, leaders-only cell (E3)")
    P("leader = >= +40% at 10:30 ET (14:30Z close vs file-open ref) OR top-3 gain-at-10:30 among that date's files; chop = >=3 VWAP side-flips in the prior 120 bars (20 min) -> skip; two-bars-below = >=2 consecutive closes below VWAP before the reclaim episode")
    gain1030 = {}
    for k, (bars, emas, gaps) in E.DAYS.items():
        j = bisect_left([E.secs(b) for b in bars], 14 * 3600 + 30 * 60)
        j = min(max(j - 1, 0), len(bars) - 1)
        gain1030[k] = bars[j]["c"] / REF[k] - 1
    top3 = set()
    for d in dates:
        ks = sorted([k for k in E.DAYS if k[1] == d], key=lambda k: -gain1030[k])[:3]
        top3.update(ks)
    aft = [x for x in tr_by_lane["band_pass"] if "16:00:00" <= x["t"] < "18:30:00"]
    def is_leader(x):
        k = (x["sym"], x["date"]); return gain1030[k] >= 0.40 or k in top3
    lead = [x for x in aft if is_leader(x)]
    lead_chop = [x for x in lead if x["crosses20"] < 3]
    lead_chop_2b = [x for x in lead_chop if x["bars_below"] >= 2]
    unres_chop_2b = [x for x in aft if x["crosses20"] < 3 and x["bars_below"] >= 2]
    P(HDR); P(SEP)
    stats("unrestricted afternoon reclaim 12:00-14:30", aft, dates, bar=True)
    stats("leaders-only", lead, dates, bar=True)
    stats("leaders + chop exclusion", lead_chop, dates, bar=True)
    stats("leaders + chop excl + two-bars-below", lead_chop_2b, dates, bar=True)
    stats("unrestricted + chop excl + two-bars-below", unres_chop_2b, dates)
    stats("non-leaders", [x for x in aft if not is_leader(x)], dates)
    P(f"leader days: {sum(1 for k in E.DAYS if gain1030[k] >= 0.40 or k in top3)} of {len(E.DAYS)} name-days")
    if lead_chop_2b:
        x = max(lead_chop_2b, key=lambda z: abs(z["pnl"])); log = []
        e3(x["sym"], x["date"], x["i"], x["entry"], x["stop"], "vwap", log)
        P(f"\nT4 hand-trace: {x['sym']} {x['date']} sig {x['t']}Z entry {x['entry']:.4f} stop {x['stop']:.4f} gain@10:30 {gain1030[(x['sym'],x['date'])]*100:+.0f}% crosses20={x['crosses20']} bars_below={x['bars_below']} -> ${x['pnl']:+.2f} {x['exit']}")
        for m in log: P("    " + m)

    # ================= T5 =================
    P("\n## T5 — ORB FAIR RE-RUN (5-min and 15-min ranges, SEPARATE tests, E3, window 9:35/9:45-10:30 ET)")
    P("trigger = first completed 1-min bar (6x10s, minute-keyed) closing > ORH with 1-min volume >= 1.5x OR per-minute avg volume AND close > RTH VWAP; stop = ORL (also mid-range variant); one attempt/name/day")
    def orb(minutes, stop_mode):
        sigs = []
        endt = 13 * 3600 + 30 * 60 + minutes * 60
        for k, (bars, emas, gaps) in sorted(E.DAYS.items()):
            vw = vwap_series(bars)
            orb_bars = [b for b in bars if E.secs(b) < endt]
            if not orb_bars: continue
            orh = max(b["h"] for b in orb_bars); orl = min(b["l"] for b in orb_bars)
            avgv = sum(b["v"] for b in orb_bars) / minutes
            # minute aggregation after OR end through 14:30Z
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
                        sigs.append(mk(k[0], k[1], "orb", m["i"], m["c"], stop))
                    break
        return sigs
    P(HDR); P(SEP)
    orb_res = {}
    for minutes in (5, 15):
        for sm in ("orl", "mid"):
            sigs = orb(minutes, sm); tr = run(sigs)
            orb_res[(minutes, sm)] = tr
            stats(f"ORB {minutes}-min, stop={sm.upper()}", tr, dates, bar=True)
    # capacity check: 2-slot H1-H4 walk (B.pipeline) for the two ORL arms, chased E3
    def ex_orb(s, halt_rule):
        bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
        pnl, exx, xi = F.sim_var(bars, emas, gaps, s["i"], s["entry"], s["stop"], "E3", "orb", halt_rule)
        return True, pnl, exx, xi, s["i"]
    import io, contextlib
    for minutes in (5, 15):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = B.pipeline(sorted(orb(minutes, "orl"), key=lambda s: (s["key"], s["sym"])), dates, ex_orb, f"ORB {minutes}-min ORL portfolio")
        h = r["h5"]; v = r["verdict"]
        P(f"ORB {minutes}-min ORL, 2-slot H1-H4 portfolio: N={len(r['h4'])} mean=${h['mean']:+.2f} median=${h['median']:+.2f} green={h['green']}/{h['n']} halves ${h['half1d']:+.2f}/${h['half2d']:+.2f}/d worst=${h['worst']:+.2f} slot-skipped={h['nskip']} -> {'PASS' if all(p for _,p in v.values()) else 'FAIL'}")
    x = max(orb_res[(5, "orl")], key=lambda z: abs(z["pnl"])); log = []
    e3(x["sym"], x["date"], x["i"], x["entry"], x["stop"], "orb", log)
    P(f"\nT5 hand-trace (5-min ORL, largest |pnl|): {x['sym']} {x['date']} trigger-minute close {x['t']}Z entry {x['entry']:.4f} stop {x['stop']:.4f} -> ${x['pnl']:+.2f} {x['exit']}")
    for m in log: P("    " + m)

    # ================= T6 =================
    P("\n## T6 — REGISTRY QUICK-CHECKS on champion signals (grinder-1030 + flat_top break-attack IN-WINDOW 9:30-10:30 ET, as round G)")
    fbrk = [x for x in lanes["flat_top_break"] if "13:30:00" <= x["t"] <= "14:30:00"]
    gsig = lanes["grinder"]
    def run_rule(sigs, det, rule):
        tr = []
        for s in sigs:
            bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
            pnl, exx, xi = sim_e3_rule(bars, emas, gaps, s["i"], s["entry"], s["stop"], det, rule, s.get("level"))
            tr.append({**s, "pnl": pnl, "exit": exx, "xi": xi, "fill_t": s["t"], "fill_key": s["key"]})
        return F.dedup(tr)
    P("\n### (a) failed-break exit — break-attack: first completed 3-min bar after entry closes back below base high -> exit vs E3 default")
    P(HDR); P(SEP)
    d0 = run_rule(fbrk, "flat_top", None); d1 = run_rule(fbrk, "flat_top", "failed_break")
    stats("break-attack E3 default", d0, dates); stats("break-attack + failed-break exit", d1, dates)
    fired = [x for x in d1 if x["exit"].startswith("fbexit")]
    P(f"failed-break rule fired on {len(fired)}/{len(d1)} trades; those trades: rule ${sum(x['pnl'] for x in fired):+.2f} vs default ${sum(y['pnl'] for y in d0 if (y['sym'],y['date'],y['i']) in {(x['sym'],x['date'],x['i']) for x in fired}):+.2f}")
    # sanity: rule=None reproduces F.sim_var
    chk = sum(abs(a["pnl"] - b["pnl"]) for a, b in zip(d0, run(fbrk)))
    P(f"sanity: sim_e3_rule(None) vs F.sim_var E3 abs diff = {chk:.6f}")
    P("\n### (b) no-progress rule — grinder + break trades not reaching +1R (1x stop distance) within 15 min -> exit at 15 vs default")
    P(HDR); P(SEP)
    for nm, sigs, det in (("grinder", gsig, "grinder"), ("break-attack", fbrk, "flat_top")):
        a0 = run_rule(sigs, det, None); a1 = run_rule(sigs, det, "noprog15")
        stats(f"{nm} E3 default", a0, dates); stats(f"{nm} + no-progress-15", a1, dates)
        f1 = [x for x in a1 if x["exit"].startswith("npexit")]
        ids = {(x["sym"], x["date"], x["i"]) for x in f1}
        P(f"{nm}: rule fired {len(f1)}/{len(a1)}; those trades rule ${sum(x['pnl'] for x in f1):+.2f} vs default ${sum(y['pnl'] for y in a0 if (y['sym'],y['date'],y['i']) in ids):+.2f}")
    P("\n### (c) break-attack volume clause — signal-bar dollar volume vs prior-10-bar median dollar volume")
    P(HDR); P(SEP)
    hi = []; lo = []
    for x in d0:
        bars = E.DAYS[(x["sym"], x["date"])][0]; i = x["i"]
        prior = [b["c"] * b["v"] for b in bars[max(0, i - 10):i]]
        med = statistics.median(prior) if prior else 0.0
        sv = bars[i]["c"] * bars[i]["v"]
        (hi if med > 0 and sv >= 1.5 * med else lo).append(x)
    stats(">=1.5x prior-10 median $vol", hi, dates); stats("<1.5x", lo, dates)
    # T6 hand-trace: one failed-break firing
    if fired:
        x = fired[0]; bars, emas, gaps = E.DAYS[(x["sym"], x["date"])]; log = []
        sim_e3_rule(bars, emas, gaps, x["i"], x["entry"], x["stop"], "flat_top", "failed_break", x["level"], log)
        y = next(y for y in d0 if (y["sym"], y["date"], y["i"]) == (x["sym"], x["date"], x["i"]))
        P(f"\nT6 hand-trace (first failed-break firing): {x['sym']} {x['date']} sig {x['t']}Z level {x['level']:.4f} entry {x['entry']:.4f} stop {x['stop']:.4f} -> rule ${x['pnl']:+.2f} {x['exit']} vs default ${y['pnl']:+.2f} {y['exit']}")
        for m in log: P("    " + m)

    open(HERE + "/sunday_afternoon_studies_20260816_run.txt", "w").write("\n".join(OUT))

if __name__ == "__main__":
    main()
