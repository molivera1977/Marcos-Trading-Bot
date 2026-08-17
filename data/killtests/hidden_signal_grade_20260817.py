#!/usr/bin/env python3
"""HIDDEN SIGNAL GRADE (8/17/26) — is the hidden_entry DETECTOR worth rebuilding a body around?

Analysis only.  Read-only replay.  No bot edits, no deploy, no live path touched.

Chain imported UNCHANGED: FP (flatten_parity_20260816) -> S -> G -> F -> C -> B -> E.
FP.set_mode(True) = E3 LIVE PARITY: $500 clip, +1% entry chase, -0.5% market-exit slip,
stop-first, bank 1/2 at +10% then 10%-off-high trail, halt-gap rule, no new entries >=15:30 ET,
ALL lanes flattened 15:45 ET.  Same engine the sequence_mining_pilot_20260817 study used.

PART 1  archive cohort: hidden_shadow_fire / hidden_observe_only rows 8/13 onward.
PART 2  universe replay of the SAME detector (exact port of hidden_entry_step) + E3 grade.
PART 3  entry-construction variants A / B / C / C2.
PART 4  runner split (day-gain at fire) and dollar-volume sizeability.
PART 5  the control question: detector or body?
"""
import importlib.util, os, json, glob, statistics
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("FP", HERE + "/flatten_parity_20260816.py")
FP = importlib.util.module_from_spec(spec); spec.loader.exec_module(FP)
S = FP.S; G = FP.G; F = FP.F; C = FP.C; B = FP.B; E = FP.E

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

R = {}

# ================================================================= PART 1 — archive cohort
ARCH_DIR = os.environ.get("ARCH_DIR", "/private/tmp/claude-501/-Users-marcosolivera-Desktop-website-data/add2ac85-fd80-47f7-b583-bda802f0544d/scratchpad")
def load_archive():
    rows = []
    for f in sorted(glob.glob(ARCH_DIR + "/arch_*.json")):
        d = json.load(open(f))
        for r in d.get("rows", []):
            if r.get("status") in ("hidden_shadow_fire", "hidden_observe_only"):
                r["_date"] = d["date"]; rows.append(r)
    return rows

# ================================================================= PART 2 — the detector
HV_PCT, HV_BARS, MIN_BARS = 25.0, 30, 90
def det_hidden_v1(full, rth):
    """EXACT port of hidden_entry_step (marcos_trading_bot.py :5662-5722), fed the FULL-day 10s
    bars (premarket-anchored VWAP + 10s 90EMA warmed from the first bar = the live deep pass).
      ARM  : trailing 30-bar close velocity >= 25% (latches, stays armed)
      FIRE : l <= anchor=max(e90,vwap) AND c >= anchor AND c >= vwap AND (c-l)/(h-l) >= 0.5
             AND c > o*0.995 AND nbars >= 90
      stop = min(l-0.01, c*0.95)
    Port provenance: byte-identical to det_hidden_v1 in open_holes_sweep1_20260816.py, which
    states it was read off the bot at :5662 on 8/16.  Re-verified against the bot this run.
    Returns RTH-index fires only (PRE is its own book), with anchor + context stamped."""
    closes = []; e90 = None; armed = False; nbars = 0; cv = cpv = 0.0
    tidx = {b["t"]: i for i, b in enumerate(rth)}
    ref = full[0]["o"] if full else 0.0
    dv = 0.0
    out = []
    for b in full:
        o, h, l, c, v = b["o"], b["h"], b["l"], b["c"], b["v"]
        nbars += 1
        e90 = c if e90 is None else c * (2.0/91.0) + e90 * (89.0/91.0)
        tp = (h + l + c) / 3.0; cv += v; cpv += tp * v
        dv += tp * v
        vwap = cpv / cv if cv else c
        closes.append(c)
        if len(closes) > HV_BARS + 1: closes.pop(0)
        if not armed:
            if len(closes) > HV_BARS:
                ca = closes[0]
                if ca > 0 and (c - ca) / ca * 100.0 >= HV_PCT: armed = True
            continue
        anchor = max(e90, vwap); rng = h - l
        if (l <= anchor and c >= anchor and c >= vwap and rng > 0 and (c - l) / rng >= 0.5 and c > o * 0.995):
            if nbars < MIN_BARS: continue
            i = tidx.get(b["t"])
            if i is None: continue
            stop = min(l - 0.01, c * 0.95)
            out.append({"i": i, "entry": c, "stop": stop,
                        "ext": (c - vwap) / vwap * 100.0, "anchor": anchor,
                        "dgain": ((c - ref) / ref * 100.0) if ref else 0.0,
                        "cum_dvol": dv, "bar_dvol": tp * v})
    return out

# ---------------- entry-construction variants ----------------
PB_WINDOW = 30      # 5 minutes of 10s bars to get a limit filled; unfilled = NO TRADE

def build_sigs(arm):
    """arm in {A, B, C, C2}.  Returns S.mk signals.
       A  : enter at the FIRE price (fire-bar close).  What v1 did / what Hole C graded.
       B  : resting limit at the ANCHOR; fills only when a later bar's LOW <= anchor
            (within PB_WINDOW bars).  Unfilled = no trade.
       C  : resting limit at fire_px * 1.005 (kevseq ARM-F3 parity); fills only when a later
            bar's LOW <= that level.  NOTE the semantic caveat in the .md — for hidden the
            fire price is a TRADED CLOSE, not a trigger high, so this level sits ABOVE the
            fire and fills almost immediately.  Reported for mandate parity.
       C2 : resting limit at fire_px * 0.995 — the true no-fictional-fill analogue for a
            close-anchored lane (you must be GIVEN a better price than the fire)."""
    sigs = []
    for k in sorted(E.DAYS):
        rth = E.DAYS[k][0]; full = S.FULL[k]
        for t in det_hidden_v1(full, rth):
            i0 = t["i"]; base = dict(ext=t["ext"], anchor=t["anchor"], dgain=t["dgain"],
                                     cum_dvol=t["cum_dvol"], bar_dvol=t["bar_dvol"],
                                     fire_px=t["entry"], fire_i=i0)
            if arm == "A":
                sigs.append(S.mk(k[0], k[1], "hidden", i0, t["entry"], t["stop"], **base))
                continue
            lim = (t["anchor"] if arm == "B" else
                   t["entry"] * 1.005 if arm == "C" else t["entry"] * 0.995)
            stop = t["stop"]
            if not (stop < lim): continue          # degenerate — cannot construct the trade
            fi = None
            for j in range(i0 + 1, min(i0 + 1 + PB_WINDOW, len(rth))):
                if rth[j]["l"] <= lim: fi = j; break
            if fi is None: continue                # UNFILLED = NO TRADE
            sigs.append(S.mk(k[0], k[1], "hidden", fi, lim, stop, **base))
    return sigs

def run_live(sigs):
    FP.set_mode(True)
    return S.run(FP.cut(sigs))

def halves(tr, dates):
    mid = dates[len(dates)//2]
    return (sum(x["pnl"] for x in tr if x["date"] < mid),
            sum(x["pnl"] for x in tr if x["date"] >= mid), mid)

def row(name, tr, dates):
    st = S.stats(name, tr, dates, bar=True)
    st["worst_trade"] = min((x["pnl"] for x in tr), default=0.0)
    st["exits"] = dict(Counter(x["exit"].split("@")[0] for x in tr))
    return st

def cell(name, tr, dates):
    """compact cell for splits (no bar verdict)."""
    if not tr:
        P(f"| {name} | 0 | - | $0.00 | - | - |"); return {"N": 0}
    tot = sum(x["pnl"] for x in tr); n = len(tr)
    win = 100*sum(1 for x in tr if x["pnl"] > 0)/n
    h1, h2, mid = halves(tr, dates)
    d = defaultdict(float)
    for x in tr: d[x["date"]] += x["pnl"]
    green = 100*sum(1 for v in d.values() if v > 0)/len(d)
    P(f"| {name} | {n} | {win:.0f}% | ${tot:+.2f} | ${tot/n:+.2f} | ${h1:+.0f}/${h2:+.0f} | {green:.0f}% |")
    return {"N": n, "win": win, "total": tot, "mean_tr": tot/n, "h1": h1, "h2": h2, "green": green}

# ================================================================= MAIN
def main():
    nf, nd, dates = S.load_all()
    P("# HIDDEN SIGNAL GRADE — 8/17/26 (analysis only)")
    P(f"cache: {nf} files -> {nd} graded name-days, {len(dates)} dates {dates[0]}..{dates[-1]}")
    R["cache"] = {"files": nf, "name_days": nd, "dates": len(dates), "first": dates[0], "last": dates[-1]}

    # ---------------- PART 1
    P("\n## PART 1 — ARCHIVE COHORT (hidden_shadow_fire / hidden_observe_only)")
    arows = load_archive()
    per = Counter((r["_date"], r["status"]) for r in arows)
    P("| date | shadow_fire | observe_only | total |")
    P("|---|---|---|---|")
    tot_s = tot_o = 0
    for d in sorted({r["_date"] for r in arows}):
        s = per[(d, "hidden_shadow_fire")]; o = per[(d, "hidden_observe_only")]
        tot_s += s; tot_o += o
        P(f"| {d} | {s} | {o} | {s+o} |")
    P(f"| **TOTAL** | **{tot_s}** | **{tot_o}** | **{tot_s+tot_o}** |")
    R["archive"] = {"shadow_fire": tot_s, "observe_only": tot_o, "total": len(arows),
                    "per_day": {f"{d}|{s}": c for (d, s), c in per.items()}}
    # names
    tk = Counter(r["ticker"] for r in arows)
    P("\ntop names by fires: " + ", ".join(f"{t}:{c}" for t, c in tk.most_common(12)))
    R["archive"]["top_names"] = dict(tk.most_common(12))
    # drift check on the observe_only rows that carry BOTH fire_px and price
    dr = [(r["price"] - r["fire_px"]) / r["fire_px"] * 100.0
          for r in arows if r.get("fire_px") and r.get("price") and r["fire_px"] > 0]
    if dr:
        dr.sort()
        P(f"\nDRIFT (observe_only rows carrying both fire_px and live price): n={len(dr)} "
          f"median {statistics.median(dr):+.3f}%  mean {statistics.mean(dr):+.3f}%  "
          f"p10 {dr[int(.1*len(dr))]:+.2f}%  p90 {dr[int(.9*len(dr))]:+.2f}%  "
          f"min {dr[0]:+.2f}%  max {dr[-1]:+.2f}%")
        P(f"stamped: {len(dr)}/{tot_o} observe_only rows carry fire_px "
          f"({100*len(dr)/max(tot_o,1):.0f}%)")
        R["archive"]["drift"] = {"n": len(dr), "median": statistics.median(dr),
                                 "mean": statistics.mean(dr), "p90": dr[int(.9*len(dr))],
                                 "min": dr[0], "max": dr[-1], "stamped_pct": 100*len(dr)/max(tot_o,1)}
    # archive-cohort cache overlap
    have = {(k[0], k[1]) for k in E.DAYS}
    ak = {(r["ticker"], r["_date"]) for r in arows}
    ov = ak & have
    P(f"\narchive name-days {len(ak)}; present in the 10s cache {len(ov)} ({100*len(ov)/len(ak):.0f}%) "
      f"-> the archive cohort alone CANNOT be dollar-graded at useful N; the universe replay below "
      f"is the load-bearing arm.")
    R["archive"]["namedays"] = len(ak); R["archive"]["namedays_in_cache"] = len(ov)

    # ---------------- PART 2/3 — arms
    P("\n## PART 2/3 — UNIVERSE REPLAY, E3 LIVE PARITY, FOUR ENTRY CONSTRUCTIONS")
    P(S.HDR); P(S.SEP)
    arms = {}
    trs = {}
    for arm, label in (("A", "ARM-A enter at FIRE price"),
                       ("B", "ARM-B limit at ANCHOR (pullback; unfilled=no trade)"),
                       ("C", "ARM-C limit fire+0.5% (kevseq parity)"),
                       ("C2", "ARM-C2 limit fire-0.5% (true no-fictional-fill)")):
        sg = build_sigs(arm)
        tr = run_live(sg); trs[arm] = tr
        arms[arm] = row(label, tr, dates)
        arms[arm]["raw_fires"] = len(sg)
    R["arms"] = arms
    P("\nraw fires before dedup/cutoff: " + ", ".join(f"{a}={arms[a]['raw_fires']}" for a in arms))
    for a in arms:
        P(f"  {a}: worst single trade ${arms[a]['worst_trade']:+.2f}  exits {arms[a]['exits']}")

    # ---------------- PART 4 — runner split + sizeability
    P("\n## PART 4 — THE RUNNER SPLIT (day-gain at fire) and SIZEABILITY")
    P("day-gain proxy = (fire close / first cached bar open of the name-day) - 1.  This is an")
    P("intraday-from-first-cached-bar gain, NOT a prev-close gain (the 10s cache carries no")
    P("prior close).  It UNDERSTATES gap-up names, so the >=25% cell is a conservative subset.")
    P("\n| cell | N | win | total | $/tr | halves | green% |")
    P("|---|---|---|---|---|---|---|")
    split = {}
    for a in ("A", "B", "C2"):
        tr = trs[a]
        hi = [x for x in tr if x.get("dgain", 0) >= 25.0]
        lo = [x for x in tr if x.get("dgain", 0) < 25.0]
        split[a] = {"runner_ge25": cell(f"{a} day-gain >=25%", hi, dates),
                    "sub25": cell(f"{a} day-gain <25%", lo, dates)}
    # dollar-volume sizeability on ARM-A
    tr = trs["A"]
    bd = sorted(x.get("bar_dvol", 0.0) for x in tr)
    cd = sorted(x.get("cum_dvol", 0.0) for x in tr)
    if bd:
        P(f"\nfire-bar dollar volume: median ${statistics.median(bd):,.0f}  p10 ${bd[int(.1*len(bd))]:,.0f}  "
          f"p90 ${bd[int(.9*len(bd))]:,.0f}")
        P(f"cumulative session dollar volume at fire: median ${statistics.median(cd):,.0f}  "
          f"p10 ${cd[int(.1*len(cd))]:,.0f}")
        thin = sum(1 for v in bd if v < 5000.0)
        P(f"fires whose OWN 10s bar traded < $5,000 (a $500 clip = >10% of that bar): "
          f"{thin}/{len(bd)} ({100*thin/len(bd):.0f}%)")
        R["sizeability"] = {"bar_dvol_median": statistics.median(bd),
                            "cum_dvol_median": statistics.median(cd),
                            "thin_pct": 100*thin/len(bd)}
        P("\n| cell | N | win | total | $/tr | halves | green% |")
        P("|---|---|---|---|---|---|---|")
        med = statistics.median(bd)
        R["dvol_split"] = {
            "above_median_bar_dvol": cell("A fire-bar $vol >= median", [x for x in tr if x.get("bar_dvol", 0) >= med], dates),
            "below_median_bar_dvol": cell("A fire-bar $vol <  median", [x for x in tr if x.get("bar_dvol", 0) < med], dates)}
    R["runner_split"] = split

    # runner split x arm-B on the >=25% cell, both halves explicitly
    P("\nBEST-CASE HUNT — the two cells with any positive $/tr, re-checked on BOTH halves:")
    for a in ("A", "B", "C2"):
        c = split[a]["runner_ge25"]
        if c.get("N") and c.get("mean_tr", -1) > 0:
            P(f"  {a} runner cell: N={c['N']} $/tr ${c['mean_tr']:+.2f} halves ${c['h1']:+.0f}/${c['h2']:+.0f} "
              f"-> {'HOLDS BOTH HALVES' if c['h1'] > 0 and c['h2'] > 0 else 'FAILS a half'}")
        else:
            P(f"  {a} runner cell: $/tr ${c.get('mean_tr', 0):+.2f} — not positive, nothing to defend")

    # ---------------- named trace (mandate: dollars + one trade end to end)
    tr = trs["A"]
    if tr:
        x = max(tr, key=lambda z: z["pnl"])
        bars, emas, gaps = E.DAYS[(x["sym"], x["date"])]
        lg = []; F.sim_var(bars, emas, gaps, x["i"], x["entry"], x["stop"], "E3", "hidden", True, lg)
        b = bars[x["i"]]
        P(f"\n## NAMED TRACE (best ARM-A fire): {x['sym']} {x['date']} {x['t']}Z  bar o {b['o']:.4f} "
          f"h {b['h']:.4f} l {b['l']:.4f} c {b['c']:.4f}  anchor {x['anchor']:.4f}  stop {x['stop']:.4f} "
          f"({(x['entry']-x['stop'])/x['entry']*100:.1f}% risk)  fill {x['entry']*1.01:.4f} "
          f"({E.POS/(x['entry']*1.01):.1f} sh on a $500 clip) -> ${x['pnl']:+.2f} {x['exit']}")
        for m in lg: P("   " + m)
        R["trace_best"] = {"sym": x["sym"], "date": x["date"], "t": x["t"], "pnl": x["pnl"], "log": lg}
        y = min(tr, key=lambda z: z["pnl"])
        P(f"## NAMED TRACE (worst ARM-A fire): {y['sym']} {y['date']} {y['t']}Z stop {y['stop']:.4f} "
          f"-> ${y['pnl']:+.2f} {y['exit']}")
        R["trace_worst"] = {"sym": y["sym"], "date": y["date"], "t": y["t"], "pnl": y["pnl"]}

    json.dump(R, open(HERE + "/hidden_signal_grade_20260817_out.json", "w"), indent=1)
    open(HERE + "/hidden_signal_grade_20260817_run.txt", "w").write("\n".join(OUT) + "\n")

if __name__ == "__main__":
    main()
