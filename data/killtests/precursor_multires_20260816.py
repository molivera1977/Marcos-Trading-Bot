#!/usr/bin/env python3
"""STEP 2-4 — 1s/tick features before liftoff, hypothesis-free ranking, OOS combined score, Kev cohort.
Reads cache from precursor_multires_pull_20260816.py (imports its fetch()).
Output: data/killtests/precursor_multires_20260816_RESULTS.txt + _rows.json
"""
import os, sys, json, gzip, math, random, statistics as st, collections
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import precursor_multires_pull_20260816 as P
ROOT = P.ROOT; CACHE = P.CACHE
OUT = open(f"{ROOT}/data/killtests/precursor_multires_20260816_RESULTS.txt", "w")
def O(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.write(s + "\n"); OUT.flush()

def ts(s):  # ISO ns -> seconds since midnight UTC (float)
    return int(s[11:13])*3600 + int(s[14:16])*60 + float(s[17:-1])
def hms(x): x = int(x); return f"{x//3600:02d}:{x%3600//60:02d}:{x%60:02d}"

# ---------------- feature extraction ----------------
def align_quotes(qs):
    qt = np.array([ts(q["t"]) for q in qs]); bp = np.array([q["bp"] for q in qs], float); ap = np.array([q["ap"] for q in qs], float)
    bs = np.array([q["bs"] for q in qs], float); as_ = np.array([q["as"] for q in qs], float)
    return qt, bp, ap, bs, as_

def features(trades, quotes, T, sess_hi=None):
    """trades/quotes = raw lists covering [T-180, T+60). Returns dict of features on the pre-window."""
    tr = [t for t in trades if T-180 <= ts(t["t"]) < T]
    post = [t for t in trades if T <= ts(t["t"]) < T+60]
    F = {}
    if len(tr) < 5: return None
    tt = np.array([ts(t["t"]) for t in tr]); pp = np.array([t["p"] for t in tr], float); ss = np.array([t["s"] for t in tr], float)
    last = pp[-1]; med = np.median(ss)
    F["n_pre"] = len(tr)
    # quotes aligned to trades (last quote at or before each trade)
    qs = [q for q in quotes if T-181 <= ts(q["t"]) < T] if quotes else []
    have_q = len(qs) >= 3
    if have_q:
        qt, bp, ap, bs, as_ = align_quotes(qs)
        idx = np.searchsorted(qt, tt, side="right") - 1
        ok = idx >= 0
        b_at = np.where(ok, bp[np.clip(idx, 0, None)], np.nan); a_at = np.where(ok, ap[np.clip(idx, 0, None)], np.nan)
        side = np.zeros(len(tr))  # +1 buy (at/above ask), -1 sell (at/below bid), else tick rule
        side[pp >= a_at - 1e-9] = 1; side[pp <= b_at + 1e-9] = -1
        # tick rule for the rest
        for i in range(len(tr)):
            if side[i] == 0:
                j = i - 1
                while j >= 0 and pp[j] == pp[i]: j -= 1
                side[i] = 1 if (j >= 0 and pp[i] > pp[j]) else (-1 if j >= 0 else 0)
    else:
        side = np.zeros(len(tr))
        for i in range(1, len(tr)):
            side[i] = 1 if pp[i] > pp[i-1] else (-1 if pp[i] < pp[i-1] else side[i-1])
    for h in (60, 30, 10):
        m = tt >= T - h; n = int(m.sum())
        F[f"tick_rate_{h}"] = n / h
        F[f"avg_size_{h}"] = float(ss[m].mean()) if n else 0.0
        F[f"vol_{h}"] = float(ss[m].sum())
        F[f"n_large_{h}"] = int((ss[m] >= 5 * med).sum())
        bv = float(ss[m][side[m] > 0].sum()); sv = float(ss[m][side[m] < 0].sum())
        F[f"imb_{h}"] = (bv - sv) / (bv + sv) if bv + sv > 0 else 0.0
        F[f"buyfrac_n_{h}"] = float((side[m] > 0).mean()) if n else 0.5
        if n >= 2:
            F[f"ret_{h}"] = 1e4 * (last / pp[m][0] - 1)
            F[f"range_{h}"] = 1e4 * (pp[m].max() - pp[m].min()) / last
        else:
            F[f"ret_{h}"] = 0.0; F[f"range_{h}"] = 0.0
    base_rate = (tt < T - 60).sum() / 120.0
    F["tick_accel_60"] = (F["tick_rate_60"] + 1e-3) / (base_rate + 1e-3)
    F["tick_accel_10"] = (F["tick_rate_10"] + 1e-3) / ((tt[(tt >= T-60) & (tt < T-10)].size / 50.0) + 1e-3)
    F["tick_accel_30"] = (F["tick_rate_30"] + 1e-3) / ((tt[(tt >= T-180) & (tt < T-30)].size / 150.0) + 1e-3)
    F["vol_accel_60"] = (F["vol_60"] + 1) / (ss[tt < T-60].sum() + 1)
    F["size_ratio_30"] = (F["avg_size_30"] + 1) / (ss[tt < T-30].mean() + 1 if (tt < T-30).any() else med + 1)
    F["t_since_last_print"] = float(T - tt[-1])
    # consecutive upticks at end (strict), and net uptick count last 30 prints
    k = 0; i = len(pp) - 1
    while i > 0 and pp[i] >= pp[i-1]:
        if pp[i] > pp[i-1]: k += 1
        i -= 1
        if k >= 20: break
    F["consec_upticks"] = k
    d = np.sign(np.diff(pp[-31:])) if len(pp) > 2 else np.array([0.0])
    F["net_upticks_30p"] = float(d.sum())
    vw = float((pp * ss).sum() / ss.sum()) if ss.sum() > 0 else last
    F["px_vs_vwap180"] = 1e4 * (last / vw - 1)
    m1 = (tt >= T-30); m2 = (tt >= T-60) & (tt < T-30)
    F["higher_low_30"] = 1.0 if (m1.any() and m2.any() and pp[m1].min() > pp[m2].min()) else 0.0
    F["px_pos_180"] = (last - pp.min()) / (pp.max() - pp.min()) if pp.max() > pp.min() else 0.5
    F["range_compress"] = (F["range_10"] + 1) / (F["range_60"] + 1)
    w60 = np.concatenate([[T-60.0], tt[tt >= T-60], [float(T)]]); F["gap_max_60"] = float(np.diff(w60).max())  # includes leading/trailing silence (halt-resumption shows as ~60)
    if sess_hi and sess_hi > 0: F["dist_sess_hi"] = 1e4 * (sess_hi / last - 1)
    else: F["dist_sess_hi"] = 1e4 * (pp.max() / last - 1)
    # LULD approx: tier-2 bands by price of the 3-min ref (5-min ref unavailable in window; caveat)
    ref = float(pp.mean()); band = 0.20 if ref >= 3 else (0.20 if ref >= 0.75 else 0.75)
    if ref >= 3: band = 0.10
    up = ref * (1 + band); F["dist_luld_up"] = 1e4 * (up / last - 1)
    # NBBO features
    if have_q:
        spr = 1e4 * (ap - bp) / np.where((ap + bp) > 0, (ap + bp) / 2, np.nan)
        F["spread_last"] = float(spr[-1]) if np.isfinite(spr[-1]) else 0.0
        for h in (60, 30, 10):
            mq = qt >= T - h; nq = int(mq.sum())
            F[f"quote_rate_{h}"] = nq / h
            F[f"spread_{h}"] = float(np.nanmean(spr[mq])) if nq else F["spread_last"]
            si = (bs - as_) / np.where((bs + as_) > 0, bs + as_, np.nan)
            F[f"nbbo_imb_{h}"] = float(np.nanmean(si[mq])) if nq else 0.0
        F["nbbo_imb_last"] = float((bs[-1] - as_[-1]) / (bs[-1] + as_[-1])) if bs[-1] + as_[-1] > 0 else 0.0
        F["bid_size_ratio_30"] = (np.nanmean(bs[qt >= T-30]) + 1) / (np.nanmean(bs[qt < T-30]) + 1) if (qt < T-30).any() and (qt >= T-30).any() else 1.0
        F["ask_size_ratio_30"] = (np.nanmean(as_[qt >= T-30]) + 1) / (np.nanmean(as_[qt < T-30]) + 1) if (qt < T-30).any() and (qt >= T-30).any() else 1.0
        e = np.nanmean(spr[qt < T-60]) if (qt < T-60).any() else np.nan
        F["spread_trend_60"] = (F["spread_60"] + 0.1) / (e + 0.1) if np.isfinite(e) else 1.0
        e = np.nanmean(spr[qt < T-30]) if (qt < T-30).any() else np.nan
        F["spread_trend_30"] = (F["spread_30"] + 0.1) / (e + 0.1) if np.isfinite(e) else 1.0
        F["quote_accel_30"] = (F["quote_rate_30"] + 1e-3) / (((qt < T-30).sum() / 150.0) + 1e-3)
        F["nbbo_imb_trend_30"] = F["nbbo_imb_30"] - (float(np.nanmean(((bs - as_) / np.where((bs + as_) > 0, bs + as_, np.nan))[qt < T-30])) if (qt < T-30).any() else 0.0)
        # micro: last price vs mid, bid-side stacking (bid size / median bid size 180)
        mid = (ap[-1] + bp[-1]) / 2; F["px_vs_mid_bps"] = 1e4 * (last / mid - 1) if mid > 0 else 0.0
        F["bid_stack_last"] = bs[-1] / (np.median(bs) + 1)
        F["ask_thin_last"] = as_[-1] / (np.median(as_) + 1)
    # outcome (post 60s)
    if post:
        pq = np.array([t["p"] for t in post], float)
        F["_post_max_60"] = 1e4 * (pq.max() / last - 1); F["_post_last_60"] = 1e4 * (pq[-1] / last - 1)
        F["_post_n_60"] = len(post)
    else:
        F["_post_max_60"] = 0.0; F["_post_last_60"] = 0.0; F["_post_n_60"] = 0
    return F

FEATS_NOTE = {"ret_": "return into T (bps)", "range_": "hi-lo range (bps)", "imb_": "aggressor $-imbalance (+buy)", "spread_": "mean NBBO spread bps",
              "nbbo_imb": "(bid-ask size)/(sum)", "tick_accel": "trade-rate now / earlier", "quote_accel": "quote-rate now / earlier"}

# ---------------- stats ----------------
def auc(pos, neg):
    pos = [x for x in pos if x is not None and np.isfinite(x)]; neg = [x for x in neg if x is not None and np.isfinite(x)]
    if not pos or not neg: return 0.5
    allv = np.array(pos + neg); r = np.argsort(np.argsort(allv, kind="mergesort")).astype(float) + 1
    # ties: average ranks
    order = np.argsort(allv, kind="mergesort"); sv = allv[order]; ranks = np.empty(len(allv))
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j+1] == sv[i]: j += 1
        ranks[order[i:j+1]] = (i + j) / 2 + 1; i = j + 1
    rp = ranks[:len(pos)].sum()
    return (rp - len(pos)*(len(pos)+1)/2) / (len(pos)*len(neg))

def rank_features(P_, N_, label, top=12):
    keys = sorted({k for f in P_ + N_ for k in f if not k.startswith("_")})
    rows = []
    for k in keys:
        a = [f.get(k) for f in P_]; b = [f.get(k) for f in N_]
        a = [x for x in a if x is not None]; b = [x for x in b if x is not None]
        if len(a) < 5 or len(b) < 5: continue
        A = auc(a, b); dirn = 1 if A >= 0.5 else -1; A2 = max(A, 1 - A)
        # threshold at the contrast 90th (or 10th) percentile: enrichment = P(event>thr)/P(contrast>thr)
        thr = np.percentile(b, 90 if dirn > 0 else 10)
        pe = np.mean([(x > thr) if dirn > 0 else (x < thr) for x in a]); pc = np.mean([(x > thr) if dirn > 0 else (x < thr) for x in b])
        prec = pe / (pe + pc) if pe + pc > 0 else 0  # balanced-prior precision (equal cohort sizes)
        rows.append((A2, k, dirn, np.median(a), np.median(b), thr, pe, pc, prec))
    rows.sort(reverse=True)
    O(f"\n### {label}: N_event={len(P_)} N_contrast={len(N_)} — top {top} features by |AUC| (thr = contrast p90/p10; enrichment = event-fire-rate / contrast-fire-rate; precision assumes equal priors)")
    O("| feature | AUC | dir | med event | med contrast | thr | fire% event | fire% contrast | enrich | prec(1:1) |")
    O("|---|---|---|---|---|---|---|---|---|---|")
    for A2, k, d, me, mc, thr, pe, pc, prec in rows[:top]:
        O(f"| {k} | {A2:.3f} | {'high' if d>0 else 'low'} | {me:.3g} | {mc:.3g} | {thr:.3g} | {100*pe:.0f}% | {100*pc:.0f}% | {pe/max(pc,1e-9):.1f}x | {100*prec:.0f}% |")
    return rows

def logit_fit(X, y, l2=1.0, it=300):
    w = np.zeros(X.shape[1]); b = 0.0
    for _ in range(it):
        z = X @ w + b; p = 1 / (1 + np.exp(-z)); g = X.T @ (p - y) / len(y) + l2 * w / len(y); gb = (p - y).mean()
        w -= 0.5 * g; b -= 0.5 * gb
    return w, b
def combined(P_, N_, keys, label):
    """fit on first half (by date), test on second half. returns OOS AUC."""
    def mk(rows, lab): return [(r["_date"], [r.get(k, 0.0) for k in keys], lab) for r in rows]
    allr = sorted(mk(P_, 1) + mk(N_, 0), key=lambda r: r[0])
    dates = sorted({r[0] for r in allr}); cut = dates[len(dates)//2]
    tr = [r for r in allr if r[0] < cut]; te = [r for r in allr if r[0] >= cut]
    Xtr = np.array([r[1] for r in tr], float); ytr = np.array([r[2] for r in tr], float)
    Xte = np.array([r[1] for r in te], float); yte = np.array([r[2] for r in te], float)
    Xtr = np.nan_to_num(Xtr); Xte = np.nan_to_num(Xte)
    # robust standardize + clip
    mu = np.median(Xtr, 0); sd = np.percentile(Xtr, 75, 0) - np.percentile(Xtr, 25, 0) + 1e-9
    Ztr = np.clip((Xtr - mu) / sd, -5, 5); Zte = np.clip((Xte - mu) / sd, -5, 5)
    w, b = logit_fit(Ztr, ytr)
    sin = 1 / (1 + np.exp(-(Ztr @ w + b))); sout = 1 / (1 + np.exp(-(Zte @ w + b)))
    a_in = auc(list(sin[ytr == 1]), list(sin[ytr == 0])); a_out = auc(list(sout[yte == 1]), list(sout[yte == 0]))
    # additive z-score (sign from in-sample AUC)
    sg = np.array([1 if auc(list(Ztr[ytr == 1, j]), list(Ztr[ytr == 0, j])) >= 0.5 else -1 for j in range(len(keys))])
    zin = (Ztr * sg).sum(1); zout = (Zte * sg).sum(1)
    a_zin = auc(list(zin[ytr == 1]), list(zin[ytr == 0])); a_zout = auc(list(zout[yte == 1]), list(zout[yte == 0]))
    O(f"\n### COMBINED SCORE — {label}: {len(keys)} feats, train dates < {cut} (n={len(tr)}: {int(ytr.sum())} ev), test dates >= {cut} (n={len(te)}: {int(yte.sum())} ev)")
    O(f"logistic  IN-SAMPLE AUC {a_in:.3f} | OUT-OF-SAMPLE AUC {a_out:.3f}")
    O(f"additive-z IN-SAMPLE AUC {a_zin:.3f} | OUT-OF-SAMPLE AUC {a_zout:.3f}")
    # precision at OOS threshold = train p90 of contrast scores
    thr = np.percentile(sout[yte == 0], 90) if (yte == 0).any() else 1
    pe = (sout[yte == 1] > thr).mean() if (yte == 1).any() else 0
    O(f"OOS at contrast-p90 threshold: event fire-rate {100*pe:.0f}% vs contrast 10% -> enrichment {pe/0.1:.1f}x")
    top = sorted(zip(np.abs(w), keys, w), reverse=True)[:8]
    O("logistic weights (|w| top 8, standardized): " + ", ".join(f"{k}={ww:+.2f}" for _, k, ww in top))
    return a_out, a_zout, w, b, mu, sd

# ---------------- kev cohort: legs from ticks ----------------
def bars10_from_ticks(trades):
    B = {}
    for t in trades:
        s = ts(t["t"]); k = int(s // 10) * 10; p = t["p"]; v = t["s"]
        b = B.get(k)
        if b is None: B[k] = {"t": k, "o": p, "h": p, "l": p, "c": p, "v": v}
        else:
            b["h"] = max(b["h"], p); b["l"] = min(b["l"], p); b["c"] = p; b["v"] += v
    return [B[k] for k in sorted(B)]

def find_legs_ticks(bars, thr=0.25, volx=3.0):
    legs = []; i = 0; n = len(bars)
    while i < n:
        base = bars[i]["l"]; s0 = bars[i]["t"]
        v = 0.0; k = i - 1; cnt = 0
        while k >= 0 and s0 - bars[k]["t"] <= 1200: v += bars[k]["v"]; k -= 1; cnt += 1
        pv = v / 120.0 if cnt >= 6 else None
        if base <= 0 or not pv: i += 1; continue
        hi = base; hj = i; vol = 0.0; j = i; found = None
        while j < n and bars[j]["t"] - s0 <= 300:
            if j > i and bars[j]["l"] < base: break
            vol += bars[j]["v"]
            if bars[j]["h"] > hi: hi = bars[j]["h"]; hj = j
            slots = max(1, (bars[j]["t"] - s0) // 10 + 1)
            if hi / base - 1 >= thr and vol / slots >= volx * pv: found = j
            j += 1
        if found:
            legs.append({"i": i, "j": hj, "base": base, "hi": hi, "gain": hi / base - 1, "T": s0, "t": hms(s0), "t_hi": hms(bars[hj]["t"]), "dur": bars[hj]["t"] - s0}); i = hj + 1
        else: i += 1
    return legs

def main():
    random.seed(7)
    uw = json.load(open(f"{CACHE}/universe_windows.json"))
    O("# MULTI-RESOLUTION ROCKET PRECURSOR HUNT — 2026-08-16 (tick + NBBO level)")
    O("data: Alpaca SIP raw trades + NBBO quotes (v2/stocks/{sym}/trades|quotes, feed=sip); windows [T-180s, T+60s); T = liftoff bar start (UTC) from rocket_anatomy rows / tick-built legs")
    # ---------- Universe cohort ----------
    UP, UN = [], []
    def sess_hi_from_bars(date, sym, T):
        fn = f"{ROOT}/data/universe/bars10s/{date}_{sym}.json"
        if not os.path.exists(fn): return None
        bs = json.load(open(fn))["bars"]; h = None
        for b in bs:
            s = ts(b["time"])
            if s < 13.5*3600: continue
            if s >= T: break
            h = b["high"] if h is None else max(h, b["high"])
        return h
    for l in uw["top"]:
        T = P.tsec(l["t"]); tr, q = P.pull_window(l["date"], l["sym"], T-180, T+60)
        f = features(tr, q, T, sess_hi_from_bars(l["date"], l["sym"], T))
        if f: f["_date"] = l["date"]; f["_sym"] = l["sym"]; f["_t"] = l["t"]; f["_gain"] = l["gain"]; UP.append(f)
    for c in uw["contrast"]:
        T = P.tsec(c["t"]); tr, q = P.pull_window(c["date"], c["sym"], T-180, T+60)
        f = features(tr, q, T, sess_hi_from_bars(c["date"], c["sym"], T))
        if f: f["_date"] = c["date"]; f["_sym"] = c["sym"]; f["_t"] = c["t"]; UN.append(f)
    O(f"\n## PART A — UNIVERSE top-100 legs (by % gain) vs 100 random same-name-day windows: usable {len(UP)} legs / {len(UN)} contrast (windows with <5 pre-prints dropped)")
    O(f"liftoff windows: median pre-prints(180s) {np.median([f['n_pre'] for f in UP]):.0f}, post-60s max move median {np.median([f['_post_max_60'] for f in UP]):.0f} bps; contrast: pre-prints {np.median([f['n_pre'] for f in UN]):.0f}, post-60s max {np.median([f['_post_max_60'] for f in UN]):.0f} bps")
    for h, keys_h in (("ALL horizons", None), ("60s", ["_60", "accel_60", "trend_60"]), ("30s", ["_30", "accel_30", "trend_30", "higher_low_30", "net_upticks"]), ("10s", ["_10", "accel_10", "consec", "t_since", "gap_max", "compress"])):
        if keys_h is None: rowsU = rank_features(UP, UN, f"UNIVERSE — {h}", top=15)
        else:
            sub = lambda rows: [{k: v for k, v in f.items() if any(s in k for s in keys_h) or k.startswith("_")} for f in rows]
            rank_features(sub(UP), sub(UN), f"UNIVERSE — horizon {h}", top=8)
    topkeys = [r[1] for r in rowsU[:12]]
    nomom = [k for k in topkeys if not (k.startswith("ret_") or k.startswith("px_pos") or k.startswith("px_vs_vwap") or k.startswith("dist_sess"))]
    combined(UP, UN, topkeys, "UNIVERSE, top-12 by AUC (includes price-path feats)")
    combined(UP, UN, nomom or topkeys[:6], "UNIVERSE, top feats EXCLUDING pure price-path (tape/NBBO only)")
    combined(UP, UN, [k for k in sorted({k for f in UP for k in f}) if not k.startswith("_")], "UNIVERSE, ALL features")

    # ---------- Kev cohort ----------
    wl = json.load(open(f"{CACHE}/kev_watchlist.json"))
    kev = [(d, s) for d, syms in wl.items() if not d.startswith("_") for s in syms]
    KP, KPush, KN, stamps = [], [], [], []
    for d, s in kev:
        tr = P.fetch("trades", s, P.iso(d, 11*3600), P.iso(d, 20*3600))
        if not tr: stamps.append({"date": d, "sym": s, "n_trades": 0}); continue
        bars = bars10_from_ticks(tr)
        legs = find_legs_ticks(bars, 0.25, 3.0); pushes = [p for p in find_legs_ticks(bars, 0.10, 3.0) if p["gain"] < 0.25]
        # per-day stamp
        rth = [b for b in bars if b["t"] >= 13.5*3600]
        o = rth[0]["o"] if rth else None; hi = max(b["h"] for b in rth) if rth else None
        pre = [b for b in bars if b["t"] < 13.5*3600]
        stamps.append({"date": d, "sym": s, "n_trades": len(tr), "legs": len(legs), "pushes": len(pushes), "leg_times": [l["t"] for l in legs], "leg_gains": [round(l["gain"], 3) for l in legs],
                       "pre_legs": sum(1 for l in legs if l["T"] < 13.5*3600), "rth_open": o, "rth_high": hi, "pre_high": max(b["h"] for b in pre) if pre else None,
                       "pre_vol": sum(b["v"] for b in pre), "rth_vol": sum(b["v"] for b in rth)})
        # session high before T (from bars, RTH+PRE)
        def shi(T):
            h = None
            for b in bars:
                if b["t"] >= T: break
                h = b["h"] if h is None else max(h, b["h"])
            return h
        ev_times = [l["T"] for l in legs] + [p["T"] for p in pushes]
        for l in legs:
            T = l["T"]; q = P.fetch("quotes", s, P.iso(d, T-180), P.iso(d, T+60))
            f = features(tr, q, T, shi(T))
            if f: f.update({"_date": d, "_sym": s, "_t": l["t"], "_gain": l["gain"], "_pre": T < 13.5*3600}); KP.append(f)
        for p_ in random.sample(pushes, min(3, len(pushes))):
            T = p_["T"]; q = P.fetch("quotes", s, P.iso(d, T-180), P.iso(d, T+60))
            f = features(tr, q, T, shi(T))
            if f: f.update({"_date": d, "_sym": s, "_t": p_["t"], "_gain": p_["gain"], "_pre": T < 13.5*3600}); KPush.append(f)
        # contrast: 3 random windows >=20 min from any event, PRE+RTH, need tape
        got = 0; tries = 0
        while got < 3 and tries < 100:
            tries += 1; T = random.randint(11*3600 + 300, 20*3600 - 120)
            if any(abs(T - x) < 1200 for x in ev_times): continue
            q = P.fetch("quotes", s, P.iso(d, T-180), P.iso(d, T+60))
            f = features(tr, q, T, shi(T))
            if f: f.update({"_date": d, "_sym": s, "_t": hms(T), "_pre": T < 13.5*3600}); KN.append(f); got += 1
    json.dump({"kev_stamps": stamps, "U_pos": UP, "U_neg": UN, "K_legs": KP, "K_push": KPush, "K_neg": KN}, open(f"{ROOT}/data/killtests/precursor_multires_20260816_rows.json", "w"), default=float)
    O(f"\n\n## PART B — KEV'S OWN PICKS: {len(kev)} name-days ({len({d for d,_ in kev})} dates), full-day SIP ticks 07:00-16:00 ET; legs (>=25%/<=5min/3x vol) + pushes (10-25%) rebuilt from ticks at 10s")
    nd = [x for x in stamps if x["n_trades"] > 0]
    with_leg = [x for x in nd if x["legs"] > 0]
    O(f"tape present: {len(nd)}/{len(stamps)} name-days; produced >=1 vertical leg: {len(with_leg)} ({100*len(with_leg)/max(1,len(nd)):.0f}%); >=1 push(10-25%) or leg: {sum(1 for x in nd if x['legs']+x['pushes']>0)}; total legs {sum(x['legs'] for x in nd)}, pushes {sum(x['pushes'] for x in nd)}")
    tod = collections.Counter()
    for x in nd:
        for t in x["leg_times"]:
            hh = int(t[:2]) - 4  # ET
            tod[f"{hh:02d}"] += 1
    O("leg time-of-day (ET hour): " + ", ".join(f"{k}h:{v}" for k, v in sorted(tod.items())))
    O(f"premarket legs: {sum(x['pre_legs'] for x in nd)} of {sum(x['legs'] for x in nd)}; name-days whose FIRST leg is premarket: {sum(1 for x in nd if x['legs'] and x['leg_times'][0] < '13:30:00')}")
    O("\n### Kev pick-by-pick stamp (date, sym, legs, first leg ET, best leg gain, pre_high vs rth_high)")
    O("| date | sym | trades | legs | pushes | first leg (ET) | best leg | pre high | RTH high |")
    O("|---|---|---|---|---|---|---|---|---|")
    for x in stamps:
        if x["n_trades"] == 0: O(f"| {x['date']} | {x['sym']} | 0 | - | - | - | - | - | - |"); continue
        ft = x["leg_times"][0] if x["leg_times"] else "-"
        if ft != "-": ft = f"{int(ft[:2])-4:02d}{ft[2:]}"
        O(f"| {x['date']} | {x['sym']} | {x['n_trades']} | {x['legs']} | {x['pushes']} | {ft} | {('+%.0f%%' % (100*max(x['leg_gains']))) if x['leg_gains'] else '-'} | {x['pre_high']} | {x['rth_high']} |")
    O(f"\nusable feature rows: Kev legs {len(KP)} (pre {sum(1 for f in KP if f['_pre'])}), Kev pushes {len(KPush)}, Kev quiet-contrast {len(KN)}")
    rowsK = rank_features(KP, KN, "KEV LEGS vs KEV OWN QUIET WINDOWS", top=15)
    rank_features(KP + KPush, KN, "KEV LEGS+PUSHES vs KEV QUIET", top=10)
    rank_features(KP, UP, "KEV LEGS vs UNIVERSE LEGS (does his selection change the pre-liftoff tape?)", top=10)
    rank_features(KN, UN, "KEV QUIET vs UNIVERSE QUIET (baseline tape character of his names)", top=8)
    tk = [r[1] for r in rowsK[:12]]
    combined(KP, KN, tk, "KEV, top-12 by AUC")
    combined(KP, KN, [k for k in tk if not (k.startswith("ret_") or k.startswith("px_pos") or k.startswith("px_vs_vwap") or k.startswith("dist_sess"))] or tk[:6], "KEV, tape/NBBO only (no price-path)")
    combined(KP + KPush, KN, tk, "KEV legs+pushes, top-12")
    # cross-fit: universe-trained score applied to Kev
    allk = [k for k in sorted({k for f in UP for k in f}) if not k.startswith("_")]
    O("\n### CROSS: score fit on ALL universe rows, applied to Kev legs vs Kev quiet")
    X = np.nan_to_num(np.array([[f.get(k, 0.0) for k in allk] for f in UP + UN], float)); y = np.array([1]*len(UP) + [0]*len(UN), float)
    mu = np.median(X, 0); sd = np.percentile(X, 75, 0) - np.percentile(X, 25, 0) + 1e-9; Z = np.clip((X-mu)/sd, -5, 5); w, b = logit_fit(Z, y)
    XK = np.nan_to_num(np.array([[f.get(k, 0.0) for k in allk] for f in KP + KN], float)); ZK = np.clip((XK-mu)/sd, -5, 5); sK = 1/(1+np.exp(-(ZK@w+b)))
    O(f"universe-fit logistic on Kev: AUC {auc(list(sK[:len(KP)]), list(sK[len(KP):])):.3f}")

    # ---------- economics (STEP 4) ----------
    O("\n\n## PART C — ECONOMICS back-of-envelope: fire the best single tape feature + the OOS combined score")
    # fire rate per contrast window at threshold; contrast windows/day in the field ~ (390 min / 4 min) x names
    O("contrast windows are 4-min slices; a field of 20 names x 97 slices/day = ~1,940 windows/day. A 10% contrast fire-rate = ~194 false fires/day; 2% = ~39/day.")
    for label, pos, neg in (("UNIVERSE", UP, UN), ("KEV", KP, KN)):
        # +1% chase at T, outcome = post-60s last (bps) as proxy; and hold-to-60s max
        pm = [f["_post_last_60"] for f in pos]; nm = [f["_post_last_60"] for f in neg]
        O(f"{label}: at T (+1% chase = -100 bps), 60s-later mark: legs median {np.median(pm):.0f} bps (mean {np.mean(pm):.0f}), contrast median {np.median(nm):.0f} bps (mean {np.mean(nm):.0f}); leg 60s max median {np.median([f['_post_max_60'] for f in pos]):.0f} bps")
    OUT.close()

if __name__ == "__main__" and len(sys.argv) == 1:
    main()

# ---------------- PART D: ACTIVITY-MATCHED contrast (T sampled proportional to trade flow) ----------------
def part_d():
    global OUT
    OUT = open(f"{ROOT}/data/killtests/precursor_multires_20260816_RESULTS.txt", "a")
    random.seed(11)
    R = json.load(open(f"{ROOT}/data/killtests/precursor_multires_20260816_rows.json"))
    UP, KP, KPush = R["U_pos"], R["K_legs"], R["K_push"]
    uw = json.load(open(f"{CACHE}/universe_windows.json"))
    rows = json.load(open(f"{ROOT}/data/killtests/rocket_anatomy_20260816_rows.json"))["legs"]
    legs_by = {}
    for l in rows: legs_by.setdefault((l["date"], l["sym"]), []).append(P.tsec(l["t"]))
    O("\n\n## PART D — ACTIVITY-MATCHED CONTRAST: T sampled proportional to trade flow (busy tape, no liftoff), >=20 min from any leg/push. This removes 'the tape is busy' as the discriminator.")
    UN2 = []
    for l in uw["top"]:
        fn = f"{ROOT}/data/universe/bars10s/{l['date']}_{l['sym']}.json"
        if not os.path.exists(fn): continue
        bs = [b for b in json.load(open(fn))["bars"] if 13.5*3600+300 <= ts(b["time"]) <= 20*3600-120]
        w = np.array([b["volume"] for b in bs], float)
        cand = [i for i in range(len(bs)) if all(abs(ts(bs[i]["time"]) - x) >= 1200 for x in legs_by[(l["date"], l["sym"])])]
        if not cand: continue
        ww = w[cand]; 
        if ww.sum() <= 0: continue
        for _ in range(2):
            i = random.choices(cand, weights=ww)[0]; T = int(ts(bs[i]["time"]))
            tr, q = P.pull_window(l["date"], l["sym"], T-180, T+60)
            sh = None
            for b in json.load(open(fn))["bars"]:
                s = ts(b["time"]); 
                if s < 13.5*3600: continue
                if s >= T: break
                sh = b["high"] if sh is None else max(sh, b["high"])
            f = features(tr, q, T, sh)
            if f: f.update({"_date": l["date"], "_sym": l["sym"], "_t": hms(T)}); UN2.append(f)
    O(f"\nUNIVERSE: {len(UP)} legs vs {len(UN2)} activity-matched windows; median pre-prints legs {np.median([f['n_pre'] for f in UP]):.0f} vs matched {np.median([f['n_pre'] for f in UN2]):.0f}; matched post-60s max median {np.median([f['_post_max_60'] for f in UN2]):.0f} bps")
    rU = rank_features(UP, UN2, "UNIVERSE legs vs ACTIVITY-MATCHED", top=15)
    combined(UP, UN2, [r[1] for r in rU[:12]], "UNIVERSE vs matched, top-12")
    combined(UP, UN2, [r[1] for r in rU[:12] if not (r[1].startswith("ret_") or r[1].startswith("px_pos") or r[1].startswith("px_vs") or r[1].startswith("range") or r[1].startswith("dist_sess") or r[1].startswith("higher"))] or ["tick_accel_30"], "UNIVERSE vs matched, NO price-path/range feats (pure flow+NBBO)")
    combined(UP, UN2, [k for k in sorted({k for f in UP for k in f}) if not k.startswith("_")], "UNIVERSE vs matched, ALL features")
    # Kev
    wl = json.load(open(f"{CACHE}/kev_watchlist.json")); kev = [(d, s) for d, syms in wl.items() if not d.startswith("_") for s in syms]
    KN2 = []
    for d, s in kev:
        tr = P.fetch("trades", s, P.iso(d, 11*3600), P.iso(d, 20*3600))
        if len(tr) < 500: continue
        bars = bars10_from_ticks(tr)
        ev = [l["T"] for l in find_legs_ticks(bars, 0.10, 3.0)]
        tt = [ts(t["t"]) for t in tr]
        cand = [x for x in tt[::max(1, len(tt)//4000)] if 11*3600+300 <= x <= 20*3600-120 and all(abs(x - e) >= 1200 for e in ev)]
        if not cand: continue
        def shi(T):
            h = None
            for b in bars:
                if b["t"] >= T: break
                h = b["h"] if h is None else max(h, b["h"])
            return h
        for _ in range(4):
            T = int(random.choice(cand)); q = P.fetch("quotes", s, P.iso(d, T-180), P.iso(d, T+60))
            f = features(tr, q, T, shi(T))
            if f: f.update({"_date": d, "_sym": s, "_t": hms(T), "_pre": T < 13.5*3600}); KN2.append(f)
    O(f"\nKEV: {len(KP)} legs (+{len(KPush)} pushes) vs {len(KN2)} activity-matched windows; median pre-prints legs {np.median([f['n_pre'] for f in KP]):.0f} vs matched {np.median([f['n_pre'] for f in KN2]):.0f}; matched post-60s max median {np.median([f['_post_max_60'] for f in KN2]):.0f} bps")
    rK = rank_features(KP, KN2, "KEV legs vs KEV ACTIVITY-MATCHED", top=15)
    rank_features(KP + KPush, KN2, "KEV legs+pushes vs KEV ACTIVITY-MATCHED", top=10)
    combined(KP, KN2, [r[1] for r in rK[:12]], "KEV vs matched, top-12")
    combined(KP + KPush, KN2, [r[1] for r in rK[:12]], "KEV legs+pushes vs matched, top-12")
    combined(KP + KPush, KN2, [r[1] for r in rK[:12] if not (r[1].startswith("ret_") or r[1].startswith("px_pos") or r[1].startswith("px_vs") or r[1].startswith("range") or r[1].startswith("dist_sess") or r[1].startswith("higher"))] or ["tick_accel_30"], "KEV legs+pushes vs matched, NO price-path/range feats")
    # premarket-only Kev
    KPp = [f for f in KP if f["_pre"]]; KN2p = [f for f in KN2 if f["_pre"]]
    if len(KPp) >= 5 and len(KN2p) >= 5: rank_features(KPp, KN2p, "KEV PREMARKET legs vs premarket matched", top=8)
    R["U_neg_matched"] = UN2; R["K_neg_matched"] = KN2
    json.dump(R, open(f"{ROOT}/data/killtests/precursor_multires_20260816_rows.json", "w"), default=float)
    # hand traces at tick level: 3 Kev-class legs
    O("\n\n## PART E — HAND-TRACES at tick level (last 60s before T, 5s buckets: prints, vol, buy%, last px, spread bps, bid/ask size)")
    picks = []
    for want in ("INHD", "PAVS", "ZYBT", "UPC", "AZI", "STKH"):
        for f in UP + KP:
            if f["_sym"] == want and f not in picks: picks.append(f); break
    for f in picks[:4]:
        d, s, T = f["_date"], f["_sym"], P.tsec(f["_t"])
        tr = [t for t in (P.fetch("trades", s, P.iso(d, T-180), P.iso(d, T+60)) if f in UP else P.fetch("trades", s, P.iso(d, 11*3600), P.iso(d, 20*3600))) if T-60 <= ts(t["t"]) < T+30]
        qs = P.fetch("quotes", s, P.iso(d, T-180), P.iso(d, T+60))
        O(f"\n### {s} {d} liftoff T={f['_t']}Z (ET {hms(T-4*3600)}) leg +{100*f.get('_gain',0):.0f}% | pre-60s: ticks/s {f['tick_rate_60']:.1f}, ret_30 {f['ret_30']:+.0f}bps, range_30 {f['range_30']:.0f}bps, imb_30 {f['imb_30']:+.2f}, spread_30 {f.get('spread_30',float('nan')):.0f}bps, nbbo_imb_30 {f.get('nbbo_imb_30',float('nan')):+.2f}, quote/s {f.get('quote_rate_30',0):.1f}")
        O("| bucket | prints | vol | last px | hi-lo bps | spread bps | bid sz | ask sz |"); O("|---|---|---|---|---|---|---|---|")
        for b0 in range(-60, 30, 5):
            seg = [t for t in tr if T+b0 <= ts(t["t"]) < T+b0+5]
            qq = [q for q in qs if T+b0 <= ts(q["t"]) < T+b0+5]
            if not seg and not qq: O(f"| {b0:+d}s | 0 | 0 | - | - | - | - | - |"); continue
            px = [t["p"] for t in seg]; v = sum(t["s"] for t in seg)
            sp = f"{1e4*(qq[-1]['ap']-qq[-1]['bp'])/((qq[-1]['ap']+qq[-1]['bp'])/2):.0f}" if qq and qq[-1]["ap"]+qq[-1]["bp"] > 0 else "-"
            O(f"| {b0:+d}s | {len(seg)} | {v:.0f} | {px[-1] if px else '-'} | {(1e4*(max(px)-min(px))/px[-1]) if px else 0:.0f} | {sp} | {qq[-1]['bs'] if qq else '-'} | {qq[-1]['as'] if qq else '-'} |")
    OUT.close()

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "d":
    part_d()
