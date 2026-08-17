#!/usr/bin/env python3
"""JOINT DOOR 8/16 add-on (robustness of the B_tape finding): which component carries the lift
(calm vs spread), threshold stability (X at p20/p30/p40), bucket character (price/volume/gain),
per-window B W2 BA/E3 KEV-only 2-slot vs O-config on 36 and 62 dates, and a date-shuffle null."""
import importlib.util, os, json, random, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("J", HERE + "/joint_door_20260816.py")
J = importlib.util.module_from_spec(spec); spec.loader.exec_module(J)
E = J.E; B = J.B; FP = J.FP
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)
J.load_all(); J.fingerprint_all()
dates = sorted({d for _, d in E.DAYS}); dates36 = [d for d in dates if "2026-06-25" <= d <= "2026-08-14"]
calmX, _ = J.calibrate_calm()
sigs = J.gen_entries()
allc = sorted(FP[k]["s930"]["win"]["calm"] for k in FP if FP[k]["s930"]["win"])
alls = sorted(FP[k]["s930"]["win"]["spread"] for k in FP if FP[k]["s930"]["win"])

def sel_fn(kind, X):
    def f(k):
        for st in ("s930", "s800"):
            w = FP[k][st]["win"]
            if not w: continue
            if kind == "calm" and w["calm"] <= X: return True
            if kind == "spread" and w["spread"] <= X: return True
            if kind == "both" and w["calm"] <= X and w["spread"] <= 80: return True
        return False
    return f

def cell(det, wn, f, v, want_in=True):
    ss = [s for s in sigs if s["det"] == det and J.in_win(s, wn) and f((s["sym"], s["date"])) == want_in]
    tr = J.run_cell(ss, v); g = J.grade(tr, dates); return g

P("# JOINT DOOR add-on: B_tape robustness")
P(f"calm X p30 = {calmX:.1f} bps; p20 = {allc[int(.2*len(allc))]:.1f}; p40 = {allc[int(.4*len(allc))]:.1f}; spread p30 = {alls[int(.3*len(alls))]:.1f}")
P("\n## Which component carries the lift? ($/trade E3, in vs out; W1 v2cal and W2 BA)")
P("| selector | universe pass | v2cal W1 IN N/$tr | OUT N/$tr | BA W2 IN N/$tr | OUT N/$tr |")
P("|---|---|---|---|---|---|")
for nm, f in (("B_tape (spread<=80 & calm<=p30)", sel_fn("both", calmX)),
              ("calm<=p30 only", sel_fn("calm", calmX)),
              ("spread<=80 only", sel_fn("spread", 80)),
              ("calm<=p20 & spread<=80", sel_fn("both", allc[int(.2*len(allc))])),
              ("calm<=p40 & spread<=80", sel_fn("both", allc[int(.4*len(allc))])),
              ("calm<=p50 & spread<=80", sel_fn("both", allc[int(.5*len(allc))]))):
    npass = sum(1 for k in FP if f(k))
    a = cell("v2cal", "W1 07:00-10:00", f, "E3"); b = cell("v2cal", "W1 07:00-10:00", f, "E3", False)
    c = cell("BA", "W2 09:30-10:30", f, "E3"); d = cell("BA", "W2 09:30-10:30", f, "E3", False)
    P(f"| {nm} | {npass}/729 | {a['N']} ${a['ptr']:+.2f} | {b['N']} ${b['ptr']:+.2f} | {c['N']} ${c['ptr']:+.2f} | {d['N']} ${d['ptr']:+.2f} |")

P("\n## Bucket character (B_tape IN vs OUT): medians at the 09:30 stamp")
fB = sel_fn("both", calmX)
def charac(ks):
    px = []; vol = []; gn = []; nb = []
    for k in ks:
        bars = J.FULL[k]
        pre = [b for b in bars if E.hhmm_b(b) < "13:30:00"]
        if not pre: continue
        px.append(pre[-1]["c"]); vol.append(sum(b["v"] for b in pre)); gn.append(pre[-1]["c"] / bars[0]["o"] - 1)
        w = FP[k]["s930"]["win"]; nb.append(w["nbars"] if w else 0)
    return f"median px ${statistics.median(px):.2f}, premarket vol {statistics.median(vol)/1e3:.0f}k, gain vs 04:00 {100*statistics.median(gn):+.0f}%, traded 10s bars 09:00-09:30 {statistics.median(nb):.0f}/180, n={len(px)}"
P("IN : " + charac([k for k in FP if fB(k)]))
P("OUT: " + charac([k for k in FP if not fB(k)]))
# in-bucket day outcome: fraction that made a +25% leg / top-60
big = json.load(open(HERE + "/big_rides_reverse_20260816.json"))["top"]; legs = json.load(open(HERE + "/rocket_anatomy_20260816_rows.json"))["legs"]
rock = {(x["sym"], x["date"]) for x in big} | {(x["sym"], x["date"]) for x in legs}
P(f"IN bucket rocket-day rate {sum(1 for k in FP if fB(k) and k in rock)}/{sum(1 for k in FP if fB(k))}; OUT {sum(1 for k in FP if not fB(k) and k in rock)}/{sum(1 for k in FP if not fB(k))}")

P("\n## Portfolio: B_tape KEV-only BA W2 under E3 (the O-config's own exit) and v2cal W1 E3, 2-slot live parity")
P("| config | dates | N | day mean | day median | green | halves $/d | worst | 5-crit | HR>=250 | worst tr | maxDD |")
P("|---|---|---|---|---|---|---|---|---|---|---|---|")
def port(det, wn, v, dl, dn, want_in=True):
    ss = sorted([s for s in sigs if s["det"] == det and J.in_win(s, wn) and fB((s["sym"], s["date"])) == want_in and s["date"] in set(dl)], key=lambda s: (s["key"], s["sym"]))
    def ex(s, halt_rule):
        pnl, exx, xi = J.sim_rth(s["sym"], s["date"], s["i"], s["entry"], s["stop"], v)
        return True, pnl, exx, xi, s["i"]
    r = J.quiet(B.pipeline, ss, dl, ex, "x"); h = r["h5"]; ok = all(p for _, p in r["verdict"].values()); g = J.grade(r["h4"], dl)
    P(f"| {det} {wn} {v} {'IN' if want_in else 'OUT'} | {dn} | {len(r['h4'])} | ${h['mean']:+.2f} | ${h['median']:+.2f} | {h['green']}/{h['n']} | ${h['half1d']:+.2f}/${h['half2d']:+.2f} | ${h['worst']:+.2f} | {'PASS' if ok else 'FAIL'} | {g['hr']} | ${g['wt']:+.0f} | ${g['dd']:+.0f} |")
    return r["h4"]
for det, wn in (("BA", "W2 09:30-10:30"), ("BA", "W1 07:00-10:00"), ("v2cal", "W1 07:00-10:00"), ("v2cal", "W2 09:30-10:30")):
    for v in ("E3", "E4W"):
        port(det, wn, v, dates, "62d"); port(det, wn, v, dates36, "36d")
port("BA", "W2 09:30-10:30", "E3", dates, "62d", False); port("BA", "W2 09:30-10:30", "E3", dates36, "36d", False)

P("\n## Null: shuffle the IN/OUT label across name-days (200 draws, same IN count) — where does the real v2cal-W1-E3 lift ($/tr IN minus OUT) sit?")
keys = sorted(FP); nin = sum(1 for k in keys if fB(k))
ss_all = [s for s in sigs if s["det"] == "v2cal" and J.in_win(s, "W1 07:00-10:00")]
tr_all = J.run_cell(ss_all, "E3")
real_in = [x["pnl"] for x in tr_all if fB((x["sym"], x["date"]))]; real_out = [x["pnl"] for x in tr_all if not fB((x["sym"], x["date"]))]
real = statistics.mean(real_in) - statistics.mean(real_out)
random.seed(816); nulls = []
for _ in range(200):
    lab = set(random.sample(keys, nin))
    a = [x["pnl"] for x in tr_all if (x["sym"], x["date"]) in lab]; b = [x["pnl"] for x in tr_all if (x["sym"], x["date"]) not in lab]
    if a and b: nulls.append(statistics.mean(a) - statistics.mean(b))
nulls.sort()
P(f"real lift ${real:+.2f}/tr; null p95 ${nulls[int(.95*len(nulls))]:+.2f}, p99 ${nulls[int(.99*len(nulls))]:+.2f}, max ${nulls[-1]:+.2f}; draws >= real: {sum(1 for x in nulls if x >= real)}/{len(nulls)}")
ss_all = [s for s in sigs if s["det"] == "BA" and J.in_win(s, "W2 09:30-10:30")]
tr_all = J.run_cell(ss_all, "E3")
real_in = [x["pnl"] for x in tr_all if fB((x["sym"], x["date"]))]; real_out = [x["pnl"] for x in tr_all if not fB((x["sym"], x["date"]))]
real = statistics.mean(real_in) - statistics.mean(real_out)
random.seed(817); nulls = []
for _ in range(200):
    lab = set(random.sample(keys, nin))
    a = [x["pnl"] for x in tr_all if (x["sym"], x["date"]) in lab]; b = [x["pnl"] for x in tr_all if (x["sym"], x["date"]) not in lab]
    if a and b: nulls.append(statistics.mean(a) - statistics.mean(b))
nulls.sort()
P(f"BA W2 E3: real lift ${real:+.2f}/tr; null p95 ${nulls[int(.95*len(nulls))]:+.2f}, p99 ${nulls[int(.99*len(nulls))]:+.2f}, max ${nulls[-1]:+.2f}; draws >= real: {sum(1 for x in nulls if x >= real)}/{len(nulls)}")
open(HERE + "/joint_door_20260816_b_run.txt", "w").write("\n".join(OUT) + "\n")
