#!/usr/bin/env python3
"""SEQUENCE-MINING PILOT 8/17 — first proof of the SEQUENCING doctrine on the CHAMPION
lanes (not just kevseq).  Marcos: "one element by itself doesn't signal anything; it's the
ORDER they appear."

Universe = FULL bars10s cache (729 name-days) via S.load_all().  Engine chain imported
UNCHANGED (S -> G -> F -> C -> B -> E, the same objects flatten_parity_20260816.py uses).
Every fire is an E3 live-parity exit: F.sim_var(...,"E3",det,halt_rule=True).

Lanes:
  * flat_top BREAK-ATTACK  : G.det_flat_top_break, window 09:30-10:30 ET (13:30:00-14:30:00Z)
  * GRINDER                : C.det_grinder_1030 (post-10:30 built in)
  * V2 flush               : B.det_v2_cal (calibrated champion v2)
  * MA_PULLBACK            : NO faithful universe-replay detector exists in this engine chain
                             (the live detect_ma_pullback runs on 1-min completed bars with
                             warmup seeds + Kev levels; not portable to the 10s universe
                             replay without inventing a detector).  Reported NEEDS-DATA, not
                             fabricated.

Event alphabet (kev_rosetta_20260816.py, verbatim method): P push local high, B break session
high, T test session high, F flush>=2%, W wick@VWAP/9EMA bought back, H level hold, R retest,
L halt resumption, Q compression, D lower low.  String = the 10 minutes (60 x 10s bars) ending
at the fire bar.  SUFFIX mining is on the STRUCTURAL string (F/D removed, consecutive dups
collapsed — rosetta STEP 3b convention).

WIN = E3 pnl > 0  OR  reached +1R (entry + (entry-stop)) before the stop bar.  $/trade = E3 $.
Analysis only.  No bot edits.  Read-only replay.
"""
import importlib.util, os, math, json, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("S", HERE + "/sunday_afternoon_studies_20260816.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
G = S.G; F = S.F; C = S.C; B = S.B; E = S.E

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

# ---------------- per-day vwap / 9EMA / halt attach ----------------
def enrich(bars, gaps):
    """attach b['vwap'] (session VWAP) and b['e9'] (9-period EMA of close); return halt idx set."""
    cpv = cv = 0.0; e9 = None; k9 = 2.0 / (9 + 1)
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
        b["vwap"] = cpv / cv if cv else b["c"]
        e9 = b["c"] if e9 is None else (b["c"] - e9) * k9 + e9
        b["e9"] = e9
    return {post for pre, post, g in gaps}

# ---------------- level-hold + event string (rosetta parity) ----------------
def is_level_hold(bars, i):
    b = bars[i]; step = 1.0 if b["c"] >= 1 else 0.10
    for j in range(i - 6, i - 2):
        if j < 1: continue
        x, p = bars[j], bars[j - 1]
        for L in (math.floor(x["c"] / step) * step, math.floor(x["c"] / (step / 2)) * (step / 2)):
            if L > 0 and p["c"] <= L < x["c"] and all(bars[k]["l"] >= L for k in range(j + 1, i)) and b["l"] >= L:
                return L
    return None

def event_string(bars, i, halt_idx, lookback=60):
    ev = []; hs = halt_idx
    if i - lookback < 1:
        lo = 1
    else:
        lo = i - lookback
    sess_hi = max(x["h"] for x in bars[:max(1, i - lookback)])
    q_run = 0
    for k in range(max(1, i - lookback), i + 1):
        b = bars[k]; p = bars[k - 1]; e = []
        if k in hs: e.append("L")
        loc_hi = max(x["h"] for x in bars[max(0, k - 30):k])
        if b["h"] > sess_hi: e.append("B"); sess_hi = b["h"]
        elif b["h"] >= sess_hi * 0.997: e.append("T")
        elif b["h"] > loc_hi: e.append("P")
        h3 = max(x["h"] for x in bars[max(0, k - 3):k + 1])
        if b["l"] <= h3 * 0.98: e.append("F")
        conf = max(b["vwap"], b["e9"])
        if b["l"] <= conf * 1.005 and b["c"] > conf and b["c"] > b["o"] and b["h"] < loc_hi:
            e.append("W")
        elif is_level_hold(bars, k) is not None:
            e.append("H")
        else:
            step = 1.0 if b["c"] >= 1 else 0.10; got = False
            for L in (math.floor(b["c"] / step) * step, math.floor(b["c"] / (step / 2)) * (step / 2)):
                if L <= 0: continue
                if abs(b["l"] - L) / L <= 0.003 and b["c"] > L and any(
                        bars[j - 1]["c"] <= L < bars[j]["c"] for j in range(max(1, k - 30), k - 1)):
                    got = True; break
            if got: e.append("R")
        if "W" not in e and "H" not in e and b["l"] < min(x["l"] for x in bars[max(0, k - 6):k]):
            e.append("D")
        w = bars[max(0, k - 5):k + 1]
        if len(w) == 6 and max(x["h"] for x in w) / min(x["l"] for x in w) - 1 <= 0.01:
            q_run += 1
        else:
            if q_run >= 1 and (not ev or ev[-1] != "Q"): ev.append("Q")
            q_run = 0
        for x in e:
            if not ev or ev[-1] != x: ev.append(x)
    if q_run >= 1 and (not ev or ev[-1] != "Q"): ev.append("Q")
    return ev

def structural(ev):
    s = [e for e in ev if e not in ("F", "D")]
    return [e for i, e in enumerate(s) if i == 0 or s[i - 1] != e]

# ---------------- 1R-before-stop ----------------
def one_r_before_stop(bars, i, entry, stop):
    risk = entry - stop
    if risk <= 0: return False
    tgt = entry + risk
    for x in bars[i + 1:]:
        if x["l"] <= stop: return False
        if x["h"] >= tgt: return True
    return False

# ---------------- fire generation per lane ----------------
def gen_lane(which):
    fires = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        if which == "break_attack":
            dets = G.det_flat_top_break(bars, emas, gaps)
            dets = [t for t in dets if "13:30:00" <= E.hhmm_b(bars[t["i"]]) <= "14:30:00"]
            det = "flat_top"
        elif which == "grinder":
            dets = C.det_grinder_1030(bars, emas, gaps); det = "grinder"
        elif which == "v2":
            dets = B.det_v2_cal(bars, emas, gaps); det = "v2"
        else:
            continue
        for t in dets:
            fires.append(S.mk(sym, date, det, t["i"], t["entry"], t["stop"]))
    fires.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    return fires

def grade(fires):
    """E3 exit + dedup + event string + win label per surviving fire."""
    tr = S.run(fires)                       # E3 pnl, dedup same-name<=5min (round-F parity)
    rows = []
    for x in tr:
        bars, emas, gaps = E.DAYS[(x["sym"], x["date"])]
        halt_idx = enrich(bars, gaps)
        ev = event_string(bars, x["i"], halt_idx)
        st = structural(ev)
        win = (x["pnl"] > 0) or one_r_before_stop(bars, x["i"], x["entry"], x["stop"])
        rows.append({**x, "ev": ev, "st": st, "win": win})
    return rows

# ---------------- suffix mining ----------------
def suffix_table(rows, k):
    base_n = len(rows)
    base_win = 100 * sum(1 for r in rows if r["win"]) / base_n if base_n else 0
    base_dtr = sum(r["pnl"] for r in rows) / base_n if base_n else 0
    buckets = defaultdict(list)
    for r in rows:
        if len(r["st"]) >= k:
            buckets[tuple(r["st"][-k:])].append(r)
    out = []
    for suf, sub in buckets.items():
        has = sub; hasnt = [r for r in rows if r not in set_id(sub, rows)]
        n = len(has)
        hw = 100 * sum(1 for r in has if r["win"]) / n
        hd = sum(r["pnl"] for r in has) / n
        no = [r for r in rows if id(r) not in {id(z) for z in has}]
        nw = 100 * sum(1 for r in no if r["win"]) / len(no) if no else 0
        nd = sum(r["pnl"] for r in no) / len(no) if no else 0
        out.append({"suf": " ".join(suf), "n": n, "hw": hw, "hd": hd, "nw": nw, "nd": nd,
                    "lift_w": hw - base_win, "lift_d": hd - base_dtr})
    out.sort(key=lambda z: (-z["hd"], -z["n"]))
    return base_n, base_win, base_dtr, out

def set_id(sub, rows):
    ids = {id(z) for z in sub}
    return [r for r in rows if id(r) in ids]

# ---------------- day stats over a fixed date set ----------------
def daystats(rows, dates):
    d = {dt: 0.0 for dt in dates}
    for r in rows: d[r["date"]] += r["pnl"]
    vals = [d[k] for k in dates]; n = len(vals)
    sv = sorted(vals); med = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
    N = len(rows); tot = sum(r["pnl"] for r in rows)
    mid = dates[n // 2]
    h1 = sum(d[k] for k in dates if k < mid); h2 = sum(d[k] for k in dates if k >= mid)
    green = sum(1 for v in vals if v > 0)
    return dict(N=N, tot=tot, win=100 * sum(1 for r in rows if r["win"]) / N if N else 0,
                dtr=tot / N if N else 0, dmean=sum(vals) / n, dmed=med, worst=min(vals),
                green=100 * green / n, h1=h1, h2=h2, ndays=n)

def row_md(nm, s):
    return (f"| {nm} | {s['N']} | {s['win']:.0f}% | ${s['tot']:+.2f} | ${s['dtr']:+.2f} | "
            f"${s['dmean']:+.2f} | ${s['dmed']:+.2f} | {s['green']:.0f}% | ${s['h1']:+.0f}/${s['h2']:+.0f} | ${s['worst']:+.2f} |")

DAYHDR = "| cohort | N | win | total | $/tr | day mean | day med | green% | halves | worst day |"
DAYSEP = "|---|---|---|---|---|---|---|---|---|---|"

# ---------------- main ----------------
def main():
    P("# SEQUENCE-MINING PILOT — 8/17 (champion lanes; sequencing doctrine first proof beyond kevseq)")
    nf, nd, dates = S.load_all()
    P(f"Universe: {nf} files, {nd} name-days loaded, {len(dates)} dates {dates[0]}..{dates[-1]}.")
    P("Engine: S->G->F->C->B->E unchanged (flatten_parity chain). Exit=E3 (F.sim_var,halt_rule=True).")
    P("WIN = E3 $>0 OR +1R before stop. Suffix = STRUCTURAL string (F/D out, dups collapsed).\n")

    lanes = {}
    for key, nm in (("break_attack", "flat_top BREAK-ATTACK (9:30-10:30)"),
                    ("grinder", "GRINDER (post-10:30)"),
                    ("v2", "V2 flush")):
        rows = grade(gen_lane(key))
        lanes[key] = {"nm": nm, "rows": rows,
                      "dates": sorted({r["date"] for r in rows})}
        P(f"## LANE: {nm}  — N={len(rows)} fires over {len(lanes[key]['dates'])} active dates")
        s = daystats(rows, lanes[key]["dates"])
        P(DAYHDR); P(DAYSEP); P(row_md("UNGATED lane", s)); P("")

        # MATERIAL-N threshold: a gate must retain a real slice of the lane, not an overfit sliver
        MATN = max(20, int(0.08 * len(rows)))
        best = None            # best MATERIAL-N gate (N>=MATN, positive $/tr lift)
        sliver = None          # best small-N positive suffix (for transparency only)
        alltabs = {}
        for k in (2, 3):
            bn, bw, bd, tab = suffix_table(rows, k)
            alltabs[k] = (bn, bw, bd, tab)
            P(f"### last-{k} structural suffixes (base: N={bn} win={bw:.0f}% $/tr=${bd:+.2f}) — all N>=15")
            P("| suffix | N has | win% has | $/tr has | win% hasnt | $/tr hasnt | win lift | $/tr lift |")
            P("|---|---|---|---|---|---|---|---|")
            for z in [z for z in tab if z["n"] >= 15][:10]:
                P(f"| {z['suf']} | {z['n']} | {z['hw']:.0f}% | ${z['hd']:+.2f} | {z['nw']:.0f}% | "
                  f"${z['nd']:+.2f} | {z['lift_w']:+.0f}pp | ${z['lift_d']:+.2f} |")
            P("")
            mat = [z for z in tab if z["n"] >= MATN and z["hd"] > 0 and z["lift_d"] > 0]
            mat.sort(key=lambda z: (-(z["lift_d"]), -z["n"]))
            if mat and (best is None or mat[0]["lift_d"] > best["lift_d"]):
                best = {**mat[0], "k": k}
            sl = [z for z in tab if 8 <= z["n"] < MATN and z["hd"] > 0]
            sl.sort(key=lambda z: (-(z["hd"]), -z["n"]))
            if sl and (sliver is None or sl[0]["hd"] > sliver["hd"]):
                sliver = {**sl[0], "k": k}
        P(f"### MATERIAL-N gate threshold for this lane: N >= {MATN} (8% of {len(rows)} fires, floor 20)")
        if sliver:
            P(f"best SUB-material sliver (transparency, NOT a gate candidate): `{sliver['suf']}` "
              f"N={sliver['n']} win {sliver['hw']:.0f}% $/tr ${sliver['hd']:+.2f}")
        P("")
        lanes[key]["best"] = best; lanes[key]["sliver"] = sliver; lanes[key]["MATN"] = MATN
        if best:
            has = [r for r in rows if len(r["st"]) >= best["k"] and tuple(r["st"][-best["k"]:]) == tuple(best["suf"].split())]
            gd = sorted({r["date"] for r in has})
            sg = daystats(has, lanes[key]["dates"])
            keep_pct = 100 * sg["N"] / len(rows)
            P(f"### GATE TEST — keep ONLY fires ending in MATERIAL-N suffix `{best['suf']}` (last-{best['k']} structural)")
            P(DAYHDR); P(DAYSEP)
            P(row_md("UNGATED", daystats(rows, lanes[key]["dates"])))
            P(row_md(f"GATED [{best['suf']}]", sg))
            P(f"gate retains {sg['N']}/{len(rows)} fires ({keep_pct:.0f}%); "
              f"$/tr ${daystats(rows, lanes[key]['dates'])['dtr']:+.2f} -> ${sg['dtr']:+.2f}; "
              f"total ${daystats(rows, lanes[key]['dates'])['tot']:+.0f} -> ${sg['tot']:+.0f}\n")
        else:
            P("### GATE TEST — NO material-N (>= threshold) suffix beat the lane's base $/tr.")
            P("The lane's already-strong base is not improved by any sequence gate that retains a")
            P("real slice of fires; only sub-material slivers turn positive-per-trade (overfit-prone).\n")

    # MA_PULLBACK
    P("## LANE: MA_PULLBACK — NEEDS-DATA")
    P("No faithful universe-replay detector exists in the flatten_parity engine chain. The live")
    P("detect_ma_pullback (marcos_trading_bot.py:4641) fires off completed 1-min bars with warmup")
    P("seeds + Kev levels; porting it to the 10s universe replay would invent a detector, not")
    P("replay the champion. Flagged NEEDS-DATA: owed a dedicated 1-min universe port before a")
    P("sequence gate can be graded on it.\n")

    # hand traces: one clean WIN-with-suffix, one LOSS-without, one gate flip, from break_attack + v2
    P("## HAND-TRACES (three)")
    def trace(r, note):
        bars = E.DAYS[(r["sym"], r["date"])][0]
        P(f"- {note}: {r['sym']} {r['date']} {r['det']} fire {r['t']}Z entry {r['entry']:.4f} stop {r['stop']:.4f} "
          f"E3 ${r['pnl']:+.2f} {r['exit']} win={r['win']}")
        P(f"    full string : {' '.join(r['ev'])}")
        P(f"    structural  : {' '.join(r['st'])}")
    gr = lanes["grinder"]; best_gr = gr["best"] or gr["sliver"]
    if best_gr:
        suf = tuple(best_gr["suf"].split()); k = best_gr["k"]
        has = lambda r: len(r["st"]) >= k and tuple(r["st"][-k:]) == suf
        won = [r for r in gr["rows"] if has(r) and r["win"]]
        lost_no = [r for r in gr["rows"] if not has(r) and not r["win"]]
        if won: trace(max(won, key=lambda r: r["pnl"]), f"grinder WIN carrying the material suffix `{best_gr['suf']}`")
        if lost_no: trace(min(lost_no, key=lambda r: r["pnl"]), f"grinder LOSS lacking the suffix (gated out)")
    v2 = lanes["v2"]; best_v2 = v2["best"] or v2["sliver"]
    if best_v2:
        suf = tuple(best_v2["suf"].split()); k = best_v2["k"]
        won = [r for r in v2["rows"] if len(r["st"]) >= k and tuple(r["st"][-k:]) == suf and r["win"]]
        if won: trace(max(won, key=lambda r: r["pnl"]), f"v2 specimen carrying `{best_v2['suf']}` (only-positive sliver)")

    json.dump({k: {"nm": v["nm"], "N": len(v["rows"]), "best": v.get("best")}
               for k, v in lanes.items()},
              open(HERE + "/sequence_mining_pilot_20260817_out.json", "w"), indent=1, default=str)
    open(HERE + "/sequence_mining_pilot_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    return lanes

if __name__ == "__main__":
    main()
