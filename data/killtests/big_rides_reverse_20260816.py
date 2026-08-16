#!/usr/bin/env python3
"""BIG RIDES REVERSE-ENGINEER 8/16 — start from the WINNERS, not from entry ideas. Analysis only.
Chain reused unchanged: flatten_parity_20260816 (FP, LIVE parity 15:30 cutoff / 15:45 flatten)
-> S -> G -> F -> C -> B -> E. E3/E4 exits via FP.sim_var_live, entry slip +1%, exit MKT 0.5%,
$500 position, halt_rule on. RTH bars only (official book = RTH; PRE separate).
STEP 0 (Marcos, hypothesis-free): uniform neutral fingerprints of 30 min before + 10 min into each
big ride, k-means clustered, contrast = 60 random non-big-ride name-days.
STEP 1 ride = max close->later close gain within RTH whose closes never retraced >15% off the
running (close) high along the way. Top 60 = big rides.
STEP 2 doorways = existing detectors run unchanged (v2, BA=flat_top_break, VWAP band-pass, grinder
1030, ORB 15-min ORL, PRE reclaim = det_vwap on 07:00-09:25 ET premarket bars) inside first 20% of the
leg (price-wise) and between ride start and peak. STEP 3 capture E3 vs E4 vs full ride from entry.
STEP 4 (g)-cluster spec. STEP 5 false-positive population.
"""
import importlib.util, os, io, contextlib, json, glob, random, math, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("FP", HERE + "/flatten_parity_20260816.py")
FP = importlib.util.module_from_spec(spec); spec.loader.exec_module(FP)
S = FP.S; G = FP.G; F = FP.F; C = FP.C; E = FP.E; B = FP.B
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)
def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = fn(*a, **k)
    return r
MAN = json.load(open(HERE + "/../universe/manifest.json"))
PREV_C = {(r["sym"], d): r["prev_c"] for d, rows in MAN.items() for r in rows}
def day2(sym, date):
    d0 = dt.date.fromisoformat(date)
    return any(0 < (d0 - dt.date.fromisoformat(d)).days <= 5 and any(r["sym"] == sym for r in rows)
               for d, rows in MAN.items())
def et(hh):  # "13:30:00"Z -> "09:30" ET (summer)
    h = int(hh[:2]) - 4; return f"{h:02d}:{hh[3:5]}"

nfiles, nday, DATES = quiet(S.load_all)
P(f"# BIG RIDES REVERSE-ENGINEER 8/16 — files {nfiles}, RTH name-days {nday}, dates {len(DATES)} ({DATES[0]}..{DATES[-1]})")

# ---------------- STEP 1: rides ----------------
def best_ride(bars, tol=0.15):
    c = np.array([b["c"] for b in bars]); n = len(c); best = (0.0, 0, 0)
    for s in range(n - 1):
        seg = c[s:]; rm = np.maximum.accumulate(seg)
        brk = np.argmax(seg < rm * (1 - tol)) if (seg < rm * (1 - tol)).any() else len(seg)
        if brk == 0: continue
        pk = int(np.argmax(seg[:brk])); g = seg[pk] / c[s] - 1
        if g > best[0]: best = (float(g), s, s + pk)
    return best
RIDES = []
for (sym, date), (bars, emas, gaps) in E.DAYS.items():
    g, s, e = best_ride(bars)
    lo = min(b["l"] for b in bars); hi_i = int(np.argmax([b["h"] for b in bars]))
    lo_i = int(np.argmin([b["l"] for b in bars]))
    l2h = max(b["h"] for b in bars[lo_i:]) / lo - 1 if lo > 0 else 0
    RIDES.append(dict(sym=sym, date=date, ride=g, s=s, e=e, l2h=l2h,
                      start_px=bars[s]["c"], peak_px=bars[e]["c"], t0=E.hhmm_b(bars[s]), t1=E.hhmm_b(bars[e]),
                      halt_in=any(s <= pre and post <= e for pre, post, gg in gaps)))
RIDES.sort(key=lambda r: -r["ride"])
TOP = RIDES[:60]; TOPKEY = {(r["sym"], r["date"]) for r in TOP}
CUT = TOP[-1]["ride"]

# ---------------- STEP 0: fingerprints ----------------
def vwap_arr(bars): return np.array(S.vwap_series(bars))
def fingerprint(bars, s, gaps, sym, date):
    """neutral per-minute features for 30 min before ride start s and 10 min after; returns (vec, rows)."""
    vw = vwap_arr(bars); c = np.array([b["c"] for b in bars]); h = np.array([b["h"] for b in bars])
    l = np.array([b["l"] for b in bars]); v = np.array([b["v"] for b in bars]); sec = np.array([E.secs(b) for b in bars])
    s0 = sec[s]; prev_c = PREV_C.get((sym, date))
    m3 = E.agg3min(bars)
    rows = []
    for m in range(-30, 10):
        idx = np.where((sec >= s0 + m * 60) & (sec < s0 + (m + 1) * 60))[0]
        if len(idx) == 0: rows.append(None); continue
        i = idx[-1]; j = idx[0]
        px = c[i]; sess_hi = h[:i + 1].max(); sess_lo = l[:i + 1].min()
        above = float(px > vw[i]); cross = float((c[j - 1] > vw[j - 1]) != (px > vw[i])) if j > 0 else 0.0
        w20 = slice(max(0, j - 20), j)
        rng = (h[idx].max() - l[idx].min()) / px
        avg_rng = np.mean((h[w20] - l[w20]) / c[w20]) * 6 if j >= 5 else rng   # 20 bars -> per-minute equiv
        vol = v[idx].sum(); avg_vol = v[w20].mean() * 6 if j >= 5 else vol
        done = [x for x in m3 if x["end_t"] <= bars[i]["t"]]
        cons = None
        for k in range(len(done) - 3):
            w = done[k:k + 4]; hh = max(x["h"] for x in w); ll = min(x["l"] for x in w)
            if ll > 0 and (hh - ll) / ll <= 0.12:
                d = abs(px - hh) / hh
                cons = d if cons is None else min(cons, d)
        # higher-low / lower-low vs previous minute
        pidx = np.where((sec >= s0 + (m - 1) * 60) & (sec < s0 + m * 60))[0]
        hl = 0.0
        if len(pidx): hl = 1.0 if l[idx].min() > l[pidx].min() else (-1.0 if l[idx].min() < l[pidx].min() else 0.0)
        rows.append(dict(m=m, px=px, above=above, cross=cross,
                         from_hi=(px / sess_hi - 1) * 100, from_lo=(px / sess_lo - 1) * 100,
                         cons=(cons * 100 if cons is not None else 99.0), rng_r=rng / avg_rng if avg_rng > 0 else 1.0,
                         vol_r=vol / avg_vol if avg_vol > 0 else 1.0, hl=hl,
                         gap=((px / prev_c - 1) * 100 if prev_c else 0.0), min_open=(sec[i] - 13 * 3600 - 1800) / 60,
                         halt=float(any(sec[pre] <= s0 + (m + 1) * 60 and sec[post] >= s0 + m * 60 for pre, post, g in gaps))))
    return rows
FEAT = ["above", "from_hi", "from_lo", "cons", "rng_r", "vol_r", "hl", "halt"]
def vec(rows, sym, date, s_sec):
    """summary vector: pre30 means, pre10 means, post10 means for FEAT + gap, min_open, day2, halt_pre, halt_post."""
    def agg(rs):
        rs = [r for r in rs if r]
        if not rs: return [np.nan] * len(FEAT)
        return [float(np.mean([min(r[f], 30) if f in ("cons", "rng_r", "vol_r") else r[f] for r in rs])) for f in FEAT]
    pre30 = agg(rows[:30]); pre10 = agg(rows[20:30]); post = agg(rows[30:])
    r0 = next((r for r in rows[30:] if r), None) or next((r for r in reversed(rows[:30]) if r), None)
    extra = [r0["gap"] if r0 else 0.0, (s_sec - 13 * 3600 - 1800) / 60, float(day2(sym, date)),
             float(any(r and r["halt"] for r in rows[:30])), float(any(r and r["halt"] for r in rows[30:]))]
    return np.array(pre30 + pre10 + post + extra, dtype=float)
VNAMES = [f"pre30_{f}" for f in FEAT] + [f"pre10_{f}" for f in FEAT] + [f"post10_{f}" for f in FEAT] + \
         ["gap%", "min_since_open", "day2", "halt_pre30", "halt_post10"]

def kmeans(X, k, seed=7, it=100):
    rng = np.random.default_rng(seed); mu = X[rng.choice(len(X), k, replace=False)].copy()
    for _ in range(it):
        d = ((X[:, None, :] - mu[None]) ** 2).sum(-1); lab = d.argmin(1)
        new = np.array([X[lab == j].mean(0) if (lab == j).any() else mu[j] for j in range(k)])
        if np.allclose(new, mu): break
        mu = new
    d = ((X[:, None, :] - mu[None]) ** 2).sum(-1); lab = d.argmin(1)
    return lab, mu, float(d.min(1).sum())

FP_TOP = []
def fp_full(r):
    """fingerprint on the FULL-day bars (premarket included, VWAP anchored at premarket = settled doctrine) so a
    09:30 ride start still has a real 30-min 'before' (the premarket tape)."""
    rb = E.DAYS[(r["sym"], r["date"])][0]; full = S.FULL[(r["sym"], r["date"])]
    t = rb[r["s"]]["t"]; sf = next(i for i, b in enumerate(full) if b["t"] == t)
    gaps_f = E.find_gaps(full)
    rows = fingerprint(full, sf, gaps_f, r["sym"], r["date"])
    r["fp_rows"] = rows; r["vec"] = vec(rows, r["sym"], r["date"], E.secs(full[sf]))
for r in TOP: fp_full(r)
random.seed(816)
NON = [r for r in RIDES if (r["sym"], r["date"]) not in TOPKEY]
CONTRAST = random.sample(NON, 60)
for r in CONTRAST: fp_full(r)  # contrast anchor = the SAME construct (their own best ride start), so pre-30 is comparable

X = np.array([r["vec"] for r in TOP]); Xc = np.array([r["vec"] for r in CONTRAST])
mu_all = np.nanmean(np.vstack([X, Xc]), 0); sd_all = np.nanstd(np.vstack([X, Xc]), 0) + 1e-9
def z(A):
    A = np.where(np.isnan(A), mu_all, A); return (A - mu_all) / sd_all
Z = z(X)
P("\n## STEP 0 — HYPOTHESIS-FREE FINGERPRINTS (30 min before ride start, first 10 min of ride) — the CLUSTERS are the finding")
P("Features per minute (neutral): above-VWAP, % from session high, % from session low, distance to nearest prior 4x3min "
  "consolidation top (<=12% deep), bar range vs prior-20-bar avg, volume vs prior-20-bar avg, higher-low(+1)/lower-low(-1), halt flag; "
  "plus gap% vs prev close, minutes since open, day-2. Computed on FULL-day bars (premarket included; VWAP anchored premarket; session hi/lo incl. premarket) so 09:30 starts have a real before-window. Vector = pre30 mean, pre10 mean, post10 mean of each + extras. z-scored on TOP+CONTRAST.")
P("\n### Base rate: TOP-60 vs 60 random non-big name-days (mean, and z-gap = (top-contrast)/pooled sd)")
P("| feature | TOP-60 mean | CONTRAST mean | z-gap |"); P("|---|---|---|---|")
Xc_f = np.where(np.isnan(Xc), mu_all, Xc); X_f = np.where(np.isnan(X), mu_all, X)
gaps_z = (X_f.mean(0) - Xc_f.mean(0)) / sd_all
for name, a, b, gz in sorted(zip(VNAMES, X_f.mean(0), Xc_f.mean(0), gaps_z), key=lambda t: -abs(t[3])):
    P(f"| {name} | {a:.2f} | {b:.2f} | {gz:+.2f} |")

best = None
for k in (3, 4, 5):
    for seed in range(8):
        lab, mu, inertia = kmeans(Z, k, seed)
        if best is None or (k == best[0] and inertia < best[3]) or (k != best[0] and best is None): pass
        if best is None or k > best[0] or (k == best[0] and inertia < best[3]): cand = (k, lab, mu, inertia)
    if k == 4: best = cand  # report k=4 as the primary; also print k=3 and k=5 sizes
    P(f"k={k}: sizes {sorted(np.bincount(cand[1]).tolist(), reverse=True)} inertia {cand[3]:.1f}")
K, LAB, MU, _ = best
for r, lb in zip(TOP, LAB): r["cluster"] = int(lb)
# contrast assignment to nearest centroid
Zc = z(Xc); LABc = ((Zc[:, None, :] - MU[None]) ** 2).sum(-1).argmin(1)
for r, lb in zip(CONTRAST, LABc): r["cluster"] = int(lb)
P(f"\n### k={K} clusters of the TOP-60 pre-ride fingerprints (contrast set assigned to nearest centroid)")
for j in range(K):
    mem = [r for r in TOP if r["cluster"] == j]; nc = sum(1 for r in CONTRAST if r["cluster"] == j)
    Zj = Z[LAB == j]; dev = Zj.mean(0)
    top_f = sorted(zip(VNAMES, dev, X_f[LAB == j].mean(0)), key=lambda t: -abs(t[1]))[:7]
    P(f"\n#### Cluster {j}: {len(mem)} big rides / {nc} contrast name-days land here (ratio {len(mem)/max(nc,1):.1f}:1)")
    P("defining features (z vs pool, raw mean): " + "; ".join(f"{n} {d:+.1f}z ({m:.2f})" for n, d, m in top_f))
    P("members: " + ", ".join(f"{r['sym']} {r['date'][5:]} {et(r['t0'])} +{r['ride']*100:.0f}%" for r in mem))
    # plain-words summary computed from raw means
    raw = X_f[LAB == j].mean(0); d = dict(zip(VNAMES, raw))
    words = []
    words.append("mostly ABOVE VWAP before the ride" if d["pre30_above"] > 0.6 else ("mostly BELOW VWAP before" if d["pre30_above"] < 0.4 else "mixed VWAP side before"))
    words.append(f"start {abs(d['pre10_from_hi']):.0f}% off session high" + (" (AT the high = blue sky)" if d["pre10_from_hi"] > -3 else (" (deep pullback/backside)" if d["pre10_from_hi"] < -20 else "")))
    words.append(f"{d['pre10_from_lo']:.0f}% above session low")
    words.append(f"nearest base top {d['pre10_cons']:.0f}% away" if d["pre10_cons"] < 30 else "no prior 4x3min base")
    words.append(f"pre-10 volume {d['pre10_vol_r']:.1f}x / range {d['pre10_rng_r']:.1f}x prior-20 avg; post-10 vol {d['post10_vol_r']:.1f}x range {d['post10_rng_r']:.1f}x")
    words.append(f"start {d['min_since_open']:.0f} min after open; gap {d['gap%']:+.0f}%; day-2 {d['day2']*100:.0f}%; halt pre {d['halt_pre30']*100:.0f}% / post {d['halt_post10']*100:.0f}%")
    P("in words: " + "; ".join(words))

# ---------------- STEP 2: doorways ----------------
def det_orb15(bars, emas, gaps):
    vw = S.vwap_series(bars); endt = 13 * 3600 + 30 * 60 + 15 * 60
    ob = [b for b in bars if E.secs(b) < endt]
    if not ob: return []
    orh = max(b["h"] for b in ob); orl = min(b["l"] for b in ob); avgv = sum(b["v"] for b in ob) / 15
    mins = {}
    for i, b in enumerate(bars):
        s = E.secs(b)
        if s < endt or s >= 14 * 3600 + 30 * 60: continue
        m = mins.setdefault(s // 60, {"c": b["c"], "v": 0.0, "i": i}); m["c"] = b["c"]; m["v"] += b["v"]; m["i"] = i
    for key in sorted(mins):
        m = mins[key]
        if m["c"] > orh and m["v"] >= 1.5 * avgv and m["c"] > vw[m["i"]] and orl < m["c"]:
            return [{"i": m["i"], "entry": m["c"], "stop": orl}]
    return []
def det_pre_reclaim(sym, date):
    """det_vwap band-pass run on the premarket 07:00-09:25 ET (11:00-13:25Z) bars; returns list of ET times + entry."""
    full = S.FULL[(sym, date)]
    pre = [b for b in full if "11:00:00" <= E.hhmm_b(b) <= "13:25:00"]
    if len(pre) < 30: return []
    emas = E.ema_series([b["c"] for b in pre], 90); gaps = E.find_gaps(pre)
    tr = E.det_vwap(pre, emas, gaps)
    return [{"t": E.hhmm_b(pre[x["i"]]), "entry": x["entry"], "stop": x["stop"]} for x in tr]
DETS = {"v2_flush": E.det_v2, "BA_break": G.det_flat_top_break, "vwap_bandpass": E.det_vwap,
        "grinder1030": C.det_grinder_1030, "orb15": det_orb15}
SIG = {}   # (sym,date) -> det -> list of sigs (RTH index)
PRE = {}
for k, (bars, emas, gaps) in E.DAYS.items():
    SIG[k] = {d: quiet(fn, bars, emas, gaps) for d, fn in DETS.items()}
    PRE[k] = det_pre_reclaim(*k)

def doorways(r):
    bars = E.DAYS[(r["sym"], r["date"])][0]
    thr = r["start_px"] * (1 + 0.20 * r["ride"])
    out = {}
    for d, sigs in SIG[(r["sym"], r["date"])].items():
        hits = [x for x in sigs if r["s"] <= x["i"] <= r["e"] and x["entry"] <= thr]
        if hits: out[d] = hits[0]
    # premarket reclaim counts as a doorway only if the ride starts within the first 15 min of RTH (the PRE position could still be held? no — 9:25 flatten). Record separately as context.
    return out
def describe_none(r):
    bars, emas, gaps = E.DAYS[(r["sym"], r["date"])]; s = r["s"]; b = bars[s]
    vw = S.vwap_series(bars); sec = E.secs(b); open_s = 13 * 3600 + 1800
    sess_hi = max(x["h"] for x in bars[:s + 1]); sess_lo = min(x["l"] for x in bars[:s + 1])
    tags = []
    if sec - open_s <= 300: tags.append("first-5min-of-open")
    elif sec - open_s <= 1800: tags.append("first-30min")
    post_halt = any(post <= s and sec - E.secs(bars[post]) <= 300 for pre, post, g in gaps)
    if post_halt: tags.append("post-halt-resumption(<=5min)")
    if b["c"] >= sess_hi * 0.97: tags.append("at-session-high(blue-sky)")
    elif b["c"] <= sess_lo * 1.03: tags.append("at-session-low(bottom-fish)")
    else: tags.append(f"mid-range({(b['c']/sess_hi-1)*100:.0f}%off-hi)")
    tags.append("above-VWAP" if b["c"] > vw[s] else "below-VWAP")
    j = max(0, s - 18); rng_pre = (max(x["h"] for x in bars[j:s + 1]) - min(x["l"] for x in bars[j:s + 1])) / b["c"]
    tags.append(f"pre3min-range{rng_pre*100:.1f}%")
    v20 = np.mean([x["v"] for x in bars[max(0, s - 20):s]]) if s > 0 else 0
    v_post = np.mean([x["v"] for x in bars[s + 1:s + 7]]) if s + 1 < len(bars) else 0
    tags.append(f"post-vol{(v_post / v20 if v20 else 0):.1f}x")
    return tags

P("\n## STEP 1 — THE BIG RIDES (ride = close->close leg, closes never >15% off running high; RTH only)")
P(f"Universe {nday} RTH name-days. Top-60 cutoff = +{CUT*100:.1f}%. Median ride over the universe = +{np.median([r['ride'] for r in RIDES])*100:.1f}%.")
P("\n### Top-60 table (start/peak times ET; doorway = which of OUR detectors fired inside first 20% of the leg; capture = E3 $ / full-ride $ from that entry)")
P("| # | name | date | ride % | start ET | peak ET | day-gain@start | VWAP@start | day2 | halt-in-ride | cluster | doorways | E3 $ | E4 $ | full $ | E3 cap | E4 cap |")
P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
CENSUS = {d: 0 for d in DETS}; CENSUS["NONE"] = 0; CENSUS["pre_reclaim(ctx)"] = 0
CAP = {"E3": [], "E4": []}; PER_DOOR_CAP = {}
NONE_ROWS = []
def sim_both(sym, date, i, entry, stop, det):
    bars, emas, gaps = E.DAYS[(sym, date)]
    e3 = FP.sim_var_live(bars, emas, gaps, i, entry, stop, "E3", det, True)
    e4 = FP.sim_var_live(bars, emas, gaps, i, entry, stop, "E4", det, True)
    return e3, e4
for n, r in enumerate(TOP, 1):
    bars = E.DAYS[(r["sym"], r["date"])][0]; vw = S.vwap_series(bars)
    dw = doorways(r); r["doors"] = dw
    pc = PREV_C.get((r["sym"], r["date"])); dg = (r["start_px"] / pc - 1) * 100 if pc else float("nan")
    pre = PRE[(r["sym"], r["date"])]
    if pre: CENSUS["pre_reclaim(ctx)"] += 1
    if not dw: CENSUS["NONE"] += 1; r["none_tags"] = describe_none(r); NONE_ROWS.append(r)
    for d in dw: CENSUS[d] += 1
    e3s = e4s = fulls = []; caps = []
    cells = []
    for d, x in dw.items():
        e3, e4 = sim_both(r["sym"], r["date"], x["i"], x["entry"], x["stop"], "grinder" if d == "grinder1030" else d)
        ent = x["entry"] * 1.01; full = E.POS * (r["peak_px"] / ent - 1)
        c3 = e3[0] / full if full > 0 else float("nan"); c4 = e4[0] / full if full > 0 else float("nan")
        CAP["E3"].append(c3); CAP["E4"].append(c4)
        PER_DOOR_CAP.setdefault(d, []).append((e3[0], e4[0], full))
        cells.append((d, E.hhmm_b(bars[x["i"]]), e3[0], e4[0], full, c3, c4))
    r["cells"] = cells
    dstr = ", ".join(f"{d}@{et(t)}" for d, t, *_ in cells) or ("NONE [" + " ".join(r["none_tags"]) + "]")
    if cells:
        e3t = "/".join(f"{c[2]:+.0f}" for c in cells); e4t = "/".join(f"{c[3]:+.0f}" for c in cells)
        ft = "/".join(f"{c[4]:+.0f}" for c in cells); c3t = "/".join(f"{c[5]:.2f}" for c in cells); c4t = "/".join(f"{c[6]:.2f}" for c in cells)
    else: e3t = e4t = ft = c3t = c4t = "-"
    P(f"| {n} | {r['sym']} | {r['date']} | +{r['ride']*100:.0f}% | {et(r['t0'])} | {et(r['t1'])} | {dg:+.0f}% | "
      f"{'above' if r['start_px'] > vw[r['s']] else 'below'} | {'Y' if day2(r['sym'], r['date']) else 'N'} | {'Y' if r['halt_in'] else 'N'} | C{r['cluster']} | {dstr} | {e3t} | {e4t} | {ft} | {c3t} | {c4t} |")

P("\n### Top-20 by pure RTH low -> later high")
P("| # | name | date | low->high % | ride % (15%-tol leg) |"); P("|---|---|---|---|---|")
for n, r in enumerate(sorted(RIDES, key=lambda r: -r["l2h"])[:20], 1):
    P(f"| {n} | {r['sym']} | {r['date']} | +{r['l2h']*100:.0f}% | +{r['ride']*100:.0f}% |")

P("\n## STEP 2 — DOORWAY CENSUS over the top-60 (detector fired between ride start and peak, entry <= start + 20% of the leg)")
P("| doorway | big rides with it | % of 60 |"); P("|---|---|---|")
for d, c in CENSUS.items(): P(f"| {d} | {c} | {100*c/60:.0f}% |")
P(f"any of ours (RTH doors): {60-CENSUS['NONE']} / 60 = {100*(60-CENSUS['NONE'])/60:.0f}%; NONE = {CENSUS['NONE']} ({100*CENSUS['NONE']/60:.0f}%). "
  f"pre_reclaim(ctx) = a PRE band-pass fired somewhere 07:00-09:25 that day (context, not an RTH doorway; 9:25 flatten).")
P("\n### Cluster x doorway (secondary to the clusters)")
P("| cluster | n | " + " | ".join(DETS) + " | NONE |"); P("|---|---|" + "---|" * (len(DETS) + 1))
for j in range(K):
    mem = [r for r in TOP if r["cluster"] == j]
    P(f"| C{j} | {len(mem)} | " + " | ".join(str(sum(1 for r in mem if d in r['doors'])) for d in DETS) + f" | {sum(1 for r in mem if not r['doors'])} |")

P("\n## STEP 3 — THE RIDE: capture ratio (E3 $ or E4 $) / (full ride $ from the doorway fill to the ride peak), $500, +1% slip, 0.5% mkt exit, 15:45 flatten")
def dist(a):
    a = np.array([x for x in a if not math.isnan(x)])
    if not len(a): return "n=0"
    return f"n={len(a)} mean {a.mean():.2f} median {np.median(a):.2f} p25 {np.percentile(a,25):.2f} p75 {np.percentile(a,75):.2f} min {a.min():.2f} max {a.max():.2f} share<0 {np.mean(a<0)*100:.0f}% share>=0.5 {np.mean(a>=0.5)*100:.0f}%"
P(f"E3 capture: {dist(CAP['E3'])}"); P(f"E4 capture: {dist(CAP['E4'])}")
P("\n| doorway | n | E3 $ total | E4 $ total | full $ total | E3 cap (sum) | E4 cap (sum) |"); P("|---|---|---|---|---|---|---|")
for d, L in PER_DOOR_CAP.items():
    a = sum(x[0] for x in L); b = sum(x[1] for x in L); f = sum(x[2] for x in L)
    P(f"| {d} | {len(L)} | ${a:+.0f} | ${b:+.0f} | ${f:+.0f} | {a/f:.2f} | {b/f:.2f} |")
tot3 = sum(x[0] for L in PER_DOOR_CAP.values() for x in L); tot4 = sum(x[1] for L in PER_DOOR_CAP.values() for x in L)
totf = sum(x[2] for L in PER_DOOR_CAP.values() for x in L)
BEST_EXIT = "E4" if tot4 > tot3 else "E3"
P(f"ALL doors in big rides: E3 ${tot3:+.0f} vs E4 ${tot4:+.0f} vs full ${totf:+.0f} -> best-capture exit on big rides = {BEST_EXIT} ({max(tot3,tot4)/totf:.2f} of full).")

# ---------------- STEP 4: missing door ----------------
P("\n## STEP 4 — THE MISSING DOOR: the (g) rides none of our detectors entered")
from collections import Counter
tagc = Counter(t for r in NONE_ROWS for t in r["none_tags"] if not t.startswith("pre3min") and not t.startswith("post-vol"))
P(f"N = {len(NONE_ROWS)}. Tag counts: " + ", ".join(f"{t} {c}" for t, c in tagc.most_common()))
P("| name | date | ride | start ET | cluster | tags |"); P("|---|---|---|---|---|---|")
for r in NONE_ROWS: P(f"| {r['sym']} | {r['date']} | +{r['ride']*100:.0f}% | {et(r['t0'])} | C{r['cluster']} | {' '.join(r['none_tags'])} |")
cc = Counter(r["cluster"] for r in NONE_ROWS)
P(f"cluster distribution of (g): {dict(cc)}")

# ---------------- STEP 5: false positives ----------------
P("\n## STEP 5 — INVERSE CHECK: where do the same doorways fire when it is NOT a big ride?")
P("For every detector: total fires over the universe (unchanged sequencing), fires that land inside a top-60 ride's first-20% window (TRUE), "
  "fires on top-60 name-days but outside the window, fires on non-top-60 name-days (FALSE-POP), name-days with >=1 fire.")
P("| doorway | fires total | in-window (big) | big-day, off-window | non-big-day fires | non-big name-days w/ fire | precision in-window/total | fires per big-ride hit |")
P("|---|---|---|---|---|---|---|---|")
FP_RATIO = {}
for d in DETS:
    tot = inw = offw = nb = 0; nbdays = set()
    for k, dd in SIG.items():
        sigs = dd[d]; tot += len(sigs)
        if k in TOPKEY:
            r = next(x for x in TOP if (x["sym"], x["date"]) == k)
            thr = r["start_px"] * (1 + 0.20 * r["ride"])
            for x in sigs:
                if r["s"] <= x["i"] <= r["e"] and x["entry"] <= thr: inw += 1
                else: offw += 1
        else:
            nb += len(sigs)
            if sigs: nbdays.add(k)
    FP_RATIO[d] = (tot, inw, nb, len(nbdays))
    P(f"| {d} | {tot} | {inw} | {offw} | {nb} | {len(nbdays)} | {inw/tot if tot else 0:.3f} | {tot/max(CENSUS[d],1):.1f} |")
# also: what do those non-big fires earn under E3? (honesty: is the door itself net + or -?)
P("\n### The false-positive population under E3 (does the door pay for itself outside the big rides?)")
P("| doorway | non-big fires | E3 $ | mean/tr | big-window fires E3 $ |"); P("|---|---|---|---|---|")
for d in DETS:
    pn = []; pb = []
    for k, dd in SIG.items():
        bars, emas, gaps = E.DAYS[k]
        for x in dd[d]:
            pnl = FP.sim_var_live(bars, emas, gaps, x["i"], x["entry"], x["stop"], "E3", "grinder" if d == "grinder1030" else d, True)[0]
            if k in TOPKEY:
                r = next(y for y in TOP if (y["sym"], y["date"]) == k)
                if r["s"] <= x["i"] <= r["e"] and x["entry"] <= r["start_px"] * (1 + 0.2 * r["ride"]): pb.append(pnl); continue
            pn.append(pnl)
    P(f"| {d} | {len(pn)} | ${sum(pn):+.0f} | ${(sum(pn)/len(pn) if pn else 0):+.2f} | ${sum(pb):+.0f} (n={len(pb)}) |")

# ---------------- hand traces ----------------
P("\n## HAND-TRACES — the three biggest rides, bar-by-bar around the start (10s bars, ET; VWAP = session tp-VWAP)")
for r in TOP[:3]:
    bars, emas, gaps = E.DAYS[(r["sym"], r["date"])]; vw = S.vwap_series(bars); s = r["s"]
    P(f"\n### {r['sym']} {r['date']} ride +{r['ride']*100:.0f}% start {et(r['t0'])} @{r['start_px']:.3f} -> peak {et(r['t1'])} @{r['peak_px']:.3f}; "
      f"doorways: {', '.join(f'{d}@{et(t)} E3 ${e3:+.0f} E4 ${e4:+.0f} full ${f:+.0f}' for d,t,e3,e4,f,_,_ in r['cells']) or 'NONE ' + ' '.join(r['none_tags'])}; cluster C{r['cluster']}")
    door_i = [x["i"] for x in r["doors"].values()]
    P("| ET | o | h | l | c | vol | vs VWAP | note |"); P("|---|---|---|---|---|---|---|---|")
    lo = max(0, s - 18); hi = min(len(bars) - 1, s + 30)
    for i in range(lo, hi + 1):
        b = bars[i]; note = []
        if i == s: note.append("<< RIDE START")
        for d, x in r["doors"].items():
            if x["i"] == i: note.append(f"<< {d} entry {x['entry']:.3f} stop {x['stop']:.3f}")
        if any(post == i for pre, post, g in gaps): note.append("halt-resume")
        P(f"| {et(E.hhmm_b(b))}:{E.hhmm_b(b)[6:]} | {b['o']:.3f} | {b['h']:.3f} | {b['l']:.3f} | {b['c']:.3f} | {b['v']:.0f} | {'+' if b['c']>vw[i] else '-'}{abs(b['c']/vw[i]-1)*100:.1f}% | {' '.join(note)} |")
    for d, x in r["doors"].items():
        if x["i"] > hi:
            b = bars[x["i"]]; P(f"(later) {d} entry at {et(E.hhmm_b(b))}:{E.hhmm_b(b)[6:]} px {x['entry']:.3f} stop {x['stop']:.3f}")
    # 1-min view of the pre-30 fingerprint
    P("pre-ride minute fingerprint (m = minutes vs start): m | px | VWAP side | %fromHi | %fromLo | base-dist% | rng x | vol x | HL")
    for row in r["fp_rows"][::3]:
        if row: P(f"  {row['m']:+d} | {row['px']:.3f} | {'A' if row['above'] else 'B'} | {row['from_hi']:.1f} | {row['from_lo']:.1f} | {min(row['cons'],99):.1f} | {row['rng_r']:.1f} | {row['vol_r']:.1f} | {row['hl']:+.0f}")

json.dump({"top": [{k: v for k, v in r.items() if k not in ("fp_rows", "vec", "doors", "cells")} | {"vec": r["vec"].tolist(), "doors": list(r["doors"])} for r in TOP],
           "contrast": [{"sym": r["sym"], "date": r["date"], "ride": r["ride"], "cluster": r["cluster"], "vec": r["vec"].tolist()} for r in CONTRAST],
           "vnames": VNAMES, "census": CENSUS, "fp_ratio": FP_RATIO}, open(HERE + "/big_rides_reverse_20260816.json", "w"), indent=1)
open(HERE + "/big_rides_reverse_20260816_out.md", "w").write("\n".join(OUT))
