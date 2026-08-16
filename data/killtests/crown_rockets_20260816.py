#!/usr/bin/env python3
"""CROWN-ONLY ROCKET STUDY (Marcos 8/16: "how about study just the crowns"). Analysis only.

Cohort: every leader_armed (crown) name-day 8/5-8/14 from the dashboard decisions archive
(first leader_armed row per ticker per day = crown time). RTH-official: the study clock starts at
max(crown, 09:30 ET); premarket crowns are graded from the bell.

Data: Alpaca SIP trades (full RTH day, cached data/universe/ticks_precursor/trades — gitignored),
SIP NBBO quotes for 90s windows before each post-crown event + contrast windows, Alpaca daily bars
for prior close. 10s bars are BUILT from SIP ticks (complete tape; the dashboard ~ALP10S capture is
trade-sparse), so 10s and tick views are the same tape at two resolutions.

Exits ($500 clip, +1% entry slip, -0.5% market-exit slip, stop-first, tie against the trade — same
conventions as edge_stresstest_F): E3 = bank 1/2 at +10% then 10%-off-high closes-through trail;
E4 = 10%-off-high trail from entry; E4W = 20%-off-high trail; STRUCT = resumption-structure ratchet
(stop = higher of last completed 5-min higher-low and the latest halt-resumption bar low; never a %
trail), flatten 15:45.
"""
import os, sys, json, gzip, math, random, statistics as st, datetime as dt, importlib.util
import concurrent.futures as cf, subprocess, requests

ROOT = "/Users/marcosolivera/Desktop/Marcos-Trading-Bot"
KT = ROOT + "/data/killtests"
SCR = os.environ.get("CR_SCRATCH", "/private/tmp/claude-501/-Users-marcosolivera-Desktop-website-data/add2ac85-fd80-47f7-b583-bda802f0544d/scratchpad/crown")
os.makedirs(SCR, exist_ok=True)
spec = importlib.util.spec_from_file_location("P", KT + "/precursor_multires_pull_20260816.py")
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
fetch, iso, tsec = P.fetch, P.iso, P.tsec
DASH = "https://zestful-intuition-production-b16a.up.railway.app"; SEC = {"X-Dashboard-Secret": "marcos2026"}
DATES = ["2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14"]
POS = 500.0; ENTRY_SLIP = 0.01; MKT = 0.005
RTH0, RTH1 = 13 * 3600 + 1800, 20 * 3600          # 09:30-16:00 ET in UTC secs (EDT)
FLAT = 19 * 3600 + 45 * 60                         # 15:45 ET

def et(s):  # utc secs -> ET hh:mm:ss
    s -= 4 * 3600; return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"
def ampm_to_utc(t):
    h, m, s = t[:8].split(":"); h = int(h) % 12 + (12 if t.endswith("PM") else 0)
    return h * 3600 + int(m) * 60 + int(s) + 4 * 3600

# ---------------- 1. cohort + decisions + trades ----------------
def load_dec(d):
    fn = f"{SCR}/full_{d[5:7]}{d[8:10]}.json"
    if not os.path.exists(fn):
        r = requests.get(f"{DASH}/api/decisions_archive", params={"date": d, "limit": 50000}, headers=SEC, timeout=120)
        open(fn, "w").write(r.text)
    return json.load(open(fn))["rows"]

def load_trades():
    fn = f"{SCR}/trades.json"
    if not os.path.exists(fn):
        open(fn, "w").write(requests.get(f"{DASH}/api/trades", headers=SEC, timeout=120).text)
    j = json.load(open(fn)); return j if isinstance(j, list) else j.get("trades")

def prev_close(sym, date):
    fn = f"{SCR}/pc_{date}_{sym}.json"
    if os.path.exists(fn): return json.load(open(fn))
    d0 = (dt.date.fromisoformat(date) - dt.timedelta(days=7)).isoformat()
    r = P.S.get(f"https://data.alpaca.markets/v2/stocks/{sym}/bars", headers=P.H,
                params={"timeframe": "1Day", "start": d0, "end": date, "feed": "sip", "limit": 10, "adjustment": "raw"}, timeout=60)
    bars = (r.json().get("bars") or []) if r.status_code == 200 else []
    bars = [b for b in bars if b["t"][:10] < date]
    pc = bars[-1]["c"] if bars else None
    json.dump(pc, open(fn, "w")); return pc

def cohort():
    out = []
    for d in DATES:
        rows = load_dec(d); seen = set()
        for r in rows:
            if r.get("status") == "leader_armed" and r["ticker"] not in seen:
                seen.add(r["ticker"])
                out.append({"date": d, "sym": r["ticker"], "crown_utc": ampm_to_utc(r["time"]), "why": r.get("why")})
    return out

# ---------------- 2. tape ----------------
def trades_rth(sym, date):
    tr = fetch("trades", sym, iso(date, RTH0 - 300), iso(date, RTH1))
    out = []
    for t in tr:
        ts = t["t"]; hh, mm, ss = int(ts[11:13]), int(ts[14:16]), float(ts[17:ts.index("Z")] if "Z" in ts else ts[17:26])
        c = t.get("c") or []
        if any(x in c for x in ("C", "G", "H", "I", "M", "N", "P", "Q", "R", "T", "U", "V", "W", "Z", "4", "7", "9")):
            continue  # off-tape / odd-lot-excluded / late prints excluded from price formation
        out.append((hh * 3600 + mm * 60 + ss, float(t["p"]), int(t["s"])))
    out.sort(); return out

def bars10(tr):
    bars = {}
    for s, p, v in tr:
        k = int(s // 10) * 10
        b = bars.get(k)
        if b is None: bars[k] = [k, p, p, p, p, v]
        else:
            b[2] = max(b[2], p); b[3] = min(b[3], p); b[4] = p; b[5] += v
    ks = sorted(bars); out = []
    for k in ks:
        t, o, h, l, c, v = bars[k]; out.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
    return out

def halts(bars):
    """LULD signature: >=240s with no prints inside RTH, bracketed by trading. Returns list of
    (last_pre_idx, first_post_idx)."""
    out = []
    for i in range(1, len(bars)):
        if bars[i]["t"] - bars[i - 1]["t"] >= 240 and bars[i - 1]["t"] >= RTH0: out.append((i - 1, i))
    return out

def events(bars, i0):
    """post-crown legs (>=25% low->high within 300s) and pushes (>=10%). Greedy, non-overlapping,
    anchored at the trough bar. Returns list of dicts sorted by trough time."""
    ev = []; n = len(bars); i = i0
    while i < n:
        lo = bars[i]["l"]; best = 0.0; bj = i
        j = i + 1
        while j < n and bars[j]["t"] - bars[i]["t"] <= 300:
            g = bars[j]["h"] / lo - 1
            if g > best: best, bj = g, j
            j += 1
        if best >= 0.10:
            ev.append({"i": i, "t": bars[i]["t"], "lo": lo, "hi": bars[bj]["h"], "gain": best,
                       "kind": "leg" if best >= 0.25 else "push", "j": bj})
            i = bj + 1
        else: i += 1
    return ev

# ---------------- 3. tick read ----------------
def quotes_win(sym, date, t0, t1):
    q = fetch("quotes", sym, iso(date, t0), iso(date, t1)); out = []
    for x in q:
        ts = x["t"]; s = int(ts[11:13]) * 3600 + int(ts[14:16]) * 60 + float(ts[17:ts.index("Z")])
        out.append((s, float(x["bp"]), int(x["bs"]), float(x["ap"]), int(x["as"])))
    out.sort(); return out

def feats(tr, q, T):
    """features over the last 30s before T vs the prior 60s (T-90..T-30)."""
    import bisect
    def sl(a, lo, hi):
        i = bisect.bisect_left(a, (lo,)); j = bisect.bisect_left(a, (hi,)); return a[i:j]
    w1 = sl(tr, T - 30, T); w0 = sl(tr, T - 90, T - 30)
    q1 = sl(q, T - 30, T); q0 = sl(q, T - 90, T - 30)
    def aggr(ws, qs):
        if not ws or not qs: return None
        buy = sell = 0.0; qi = 0
        for s, p, v in ws:
            while qi + 1 < len(qs) and qs[qi + 1][0] <= s: qi += 1
            _, bp, bs, ap, asz = qs[qi]
            if p >= ap: buy += v
            elif p <= bp: sell += v
        tot = buy + sell
        return (buy - sell) / tot if tot else 0.0
    def spread(qs):
        v = [(a - b) / ((a + b) / 2) for _, b, _, a, _ in qs if a > 0 and b > 0 and a >= b]
        return st.median(v) if v else None
    def bidask(qs):
        v = [b / (b + a) for _, _, b, _, a in qs if a + b > 0]
        return st.mean(v) if v else None
    lows = []
    for k in range(6):  # 5s micro-lows inside last 30s
        seg = [p for s, p, v in w1 if T - 30 + 5 * k <= s < T - 25 + 5 * k]
        if seg: lows.append(min(seg))
    hl = sum(1 for a, b in zip(lows, lows[1:]) if b > a) / max(1, len(lows) - 1) if len(lows) >= 3 else None
    _i = bisect.bisect_left(tr, (T,)); last = tr[_i - 1][0] if _i > 0 else None
    _j = bisect.bisect_left(q, (T,)); prior_q = q[max(0, _j - 1):_j]
    return {
        "aggr30": aggr(w1, q1 or prior_q[-1:]), "aggr_prior": aggr(w0, q0 or prior_q[-1:]),
        "rate_accel": ((len(w1) / 30.0) / max(1e-9, len(w0) / 60.0)) if (w0 or w1) else None,
        "spread30": spread(q1), "spread_prior": spread(q0),
        "bidshare30": bidask(q1), "bidshare_prior": bidask(q0),
        "since_last": (T - last) if last is not None else None,
        "micro_hl": hl, "n30": len(w1), "n_prior": len(w0),
        "range30": ((max(p for _, p, _ in w1) / min(p for _, p, _ in w1) - 1) if w1 else None),
    }

# ---------------- 4. exits ----------------
def sim(bars, i, entry_px, stop, v, halt_idx, ratchet=None):
    """v in E3/E4/E4W/STRUCT. bars = 10s bars; entry at bars[i] close*(1+slip) already applied by caller.
    ratchet: for STRUCT, function(k)->stop level at bar k (structure)."""
    sh = POS / entry_px; rem = sh; pnl = 0.0; scaled = False; run_hi = entry_px
    bank_sh = sh * 0.5 if v == "E3" else 0.0
    trail = {"E3": 0.10, "E4": 0.10, "E4W": 0.20}.get(v)
    post = {p for _, p in halt_idx}
    for k in range(i + 1, len(bars)):
        b = bars[k]
        if b["t"] >= FLAT:
            px = b["o"] * (1 - MKT); pnl += rem * (px - entry_px); return pnl, "flat1545", k
        if v == "STRUCT" and ratchet is not None:
            r = ratchet(k)
            if r > stop:
                if r >= b["o"]:   # structure ratchet already above the tape: exit at this bar's open (no phantom fill)
                    px = b["o"] * (1 - MKT); pnl += rem * (px - entry_px); return pnl, "ratchet_above", k
                stop = r
        if k in post and b["o"] < stop:  # halt-resumption gap through the stop
            px = b["o"] * (1 - MKT); pnl += rem * (px - entry_px); return pnl, "haltgap", k
        if b["l"] <= stop:
            px = stop * (1 - MKT); pnl += rem * (px - entry_px); return pnl, "stop", k
        if v == "E3" and not scaled and b["h"] >= entry_px * 1.10:
            pnl += bank_sh * (entry_px * 1.10 - entry_px); rem -= bank_sh; scaled = True; continue
        run_hi = max(run_hi, b["h"])
        if trail and (v != "E3" or scaled) and b["c"] < run_hi * (1 - trail):
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px); return pnl, "trail", k
    b = bars[-1]; px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px); return pnl, "eod", len(bars) - 1

def struct_ratchet(bars, halt_idx, t_entry=0):
    """stop(k) = max(last completed 5-min bar low that is a higher low than the previous 5-min low,
    latest halt-resumption bar low before k). Monotone by construction of caller (max with prior)."""
    fives = {}
    for b in bars: fives.setdefault(int(b["t"] // 300) * 300, []).append(b["l"])
    keys = sorted(fives); lows = [min(fives[k]) for k in keys]
    post_lows = sorted((bars[p]["t"], bars[p]["l"]) for _, p in halt_idx)
    def f(k):
        t = bars[k]["t"]; cand = -1.0
        # completed 5-min bars strictly before this bar's bucket
        done = [j for j, kk in enumerate(keys) if kk + 300 <= t and kk >= t_entry - 300]
        for j in done[1:]:
            if lows[j] > lows[j - 1]: cand = max(cand, lows[j])
        for tt, l in post_lows:
            if t_entry <= tt <= t: cand = max(cand, l)
        return cand
    return f

# ---------------- 5. entries ----------------
def entry_b(bars, i0, hi_i=None):
    """plain 10s higher-low pullback (v2-style): after >=3 bars of pullback from a running high
    (>=3% off), a bar with low > previous bar low and close > previous bar high. Signal = that bar;
    fill at its close*(1+slip); stop = pullback low. Returns list of (i, stop) for every occurrence."""
    out = []; run_hi = bars[i0]["h"]; pb_lo = None; pb_n = 0
    for k in range(i0 + 1, len(bars)):
        b = bars[k]
        if b["h"] >= run_hi:
            run_hi = b["h"]; pb_lo = None; pb_n = 0; continue
        if b["h"] < run_hi * 0.97:
            pb_n += 1; pb_lo = b["l"] if pb_lo is None else min(pb_lo, b["l"])
        if pb_n >= 3 and pb_lo is not None and b["l"] > bars[k - 1]["l"] and b["c"] > bars[k - 1]["h"] and b["l"] > pb_lo:
            out.append((k, pb_lo)); run_hi = b["h"]; pb_lo = None; pb_n = 0
    return out

def entry_a(bars, i0, tr, q, thr_aggr, thr_rate):
    """mid-range pullback + tick buyer-arrival: price retraced >=1/3 of (post-crown high - post-crown
    low), then a 10s bar where the last-30s tick signature clears the thresholds found in step 2.
    Fill next bar open*(1+slip); stop = pullback low so far."""
    out = []; hi = bars[i0]["h"]; lo = bars[i0]["l"]; pb_lo = None; armed = False; last_fire = -10**9
    for k in range(i0 + 1, len(bars) - 1):
        b = bars[k]; hi = max(hi, b["h"]); lo = min(lo, b["l"])
        if b["l"] <= hi - (hi - lo) / 3.0 and hi > lo * 1.05:
            armed = True; pb_lo = b["l"] if pb_lo is None else min(pb_lo, b["l"])
        if b["h"] >= hi and armed and pb_lo is not None and hi > 0:
            armed = False; pb_lo = None
        if armed and b["t"] - last_fire >= 300:
            f = feats(tr, q, b["t"] + 10)
            if (f["aggr30"] is not None and f["aggr30"] >= thr_aggr and f["rate_accel"] is not None
                    and f["rate_accel"] >= thr_rate and f["n30"] >= 5):
                out.append((k + 1, pb_lo, "open")); last_fire = b["t"]; armed = False; pb_lo = None
    return out

# ---------------- main ----------------
def main():
    C = cohort(); TR = load_trades()
    print(f"crown name-days: {len(C)}")
    dec = {d: load_dec(d) for d in DATES}
    def prep(c):
        try:
            tr = trades_rth(c["sym"], c["date"]); pc = prev_close(c["sym"], c["date"])
            return c, tr, pc
        except Exception as e:
            return c, None, str(e)
    rows = []; legs_all = []; contrast_all = []; per_entry = {("a", v): [] for v in ("E3", "E4", "E4W", "STRUCT")}
    for e in ("b", "c"):
        for v in ("E3", "E4", "E4W", "STRUCT"): per_entry[(e, v)] = []
    random.seed(816)
    with cf.ThreadPoolExecutor(6) as ex: prepped = list(ex.map(prep, C))
    # ---- pass 1: timelines + legs + quotes windows ----
    tape = {}
    for c, tr, pc in prepped:
        if not tr: print("NO TAPE", c); continue
        bars = bars10([x for x in tr if x[0] >= RTH0])
        if len(bars) < 30: print("thin", c["sym"], c["date"], len(bars)); continue
        t0 = max(c["crown_utc"], RTH0)
        i0 = next((i for i, b in enumerate(bars) if b["t"] >= t0), None)
        if i0 is None or i0 >= len(bars) - 6: print("crown after tape end", c["sym"], c["date"]); continue
        c["crown_eff"] = t0; c["i0"] = i0; c["crown_px"] = bars[i0]["o"]; c["pc"] = pc
        hl = halts(bars); ev = events(bars, i0)
        c["halts_post"] = sum(1 for a, b in hl if bars[b]["t"] > t0); c["halts_pre"] = sum(1 for a, b in hl if bars[b]["t"] <= t0)
        c["max_ride"] = max(b["h"] for b in bars[i0:]) / c["crown_px"] - 1
        c["min_after"] = min(b["l"] for b in bars[i0:]) / c["crown_px"] - 1
        c["legs"] = [e for e in ev if e["kind"] == "leg"]; c["pushes"] = [e for e in ev if e["kind"] == "push"]
        # crown-time fingerprint
        c["day_gain"] = (c["crown_px"] / pc - 1) if pc else None
        c["min_since_open"] = (t0 - RTH0) / 60.0
        cv = cpv = 0.0
        for b in bars[:i0 + 1]:
            tp = (b["h"] + b["l"] + b["c"]) / 3; cv += b["v"]; cpv += tp * b["v"]
        c["vwap_dist"] = (c["crown_px"] / (cpv / cv) - 1) if cv else None
        c["gain_since_open"] = c["crown_px"] / bars[0]["o"] - 1
        # our lanes after crown
        drows = [r for r in dec[c["date"]] if r.get("ticker") == c["sym"] and ampm_to_utc(r["time"]) >= t0]
        c["fires"] = sum(1 for r in drows if str(r["status"]).startswith("triggered"))
        c["refusals"] = sum(1 for r in drows if str(r["status"]).endswith("_reject"))
        c["halt_arms"] = sum(1 for r in drows if r["status"] in ("halt_arm", "halt_early_arm"))
        mine = [t for t in TR if t.get("ticker") == c["sym"] and t.get("date") == c["date"]
                and t.get("entry_ts_utc") and tsec(t["entry_ts_utc"][11:19]) >= t0]
        c["our_trades"] = len(mine); c["our_pnl"] = sum(float(t.get("pnl") or 0) for t in mine)
        # events -> quotes windows (legs+pushes) and contrast
        allev = ev
        wins = [(e["t"] - 90, e["t"] + 10) for e in allev]
        n_con = 0; tries = 0; con_ts = []
        while n_con < max(1, len(allev)) and tries < 300:
            tries += 1; T = random.randint(t0 + 120, RTH1 - 900)
            if all(abs(T - e["t"]) >= 1200 for e in allev) and all(abs(T - bars[b]["t"]) >= 600 for _, b in hl):
                con_ts.append(T); n_con += 1
        wins += [(T - 90, T + 10) for T in con_ts]
        c["con_ts"] = con_ts; c["ev"] = allev
        tape[(c["sym"], c["date"])] = (bars, tr, hl, wins)
    def qpull(item):
        (sym, date), (bars, tr, hl, wins) = item; out = []
        for a, b in wins:
            try: out += quotes_win(sym, date, a, b)
            except Exception as e: print("Q ERR", sym, date, e)
        return (sym, date), sorted(set(out))
    with cf.ThreadPoolExecutor(6) as ex:
        Q = dict(ex.map(qpull, tape.items()))
    # ---- pass 2: features ----
    for c in C:
        k = (c["sym"], c["date"])
        if k not in tape: continue
        bars, tr, hl, _ = tape[k]; q = Q[k]
        for e in c["ev"]:
            f = feats(tr, q, e["t"]); f.update(sym=c["sym"], date=c["date"], t=et(e["t"]), gain=e["gain"], kind=e["kind"]); legs_all.append(f)
        for T in c["con_ts"]:
            f = feats(tr, q, T); f.update(sym=c["sym"], date=c["date"], t=et(T), kind="contrast"); contrast_all.append(f)
    def enrich(name, key, higher=True):
        a = [f[key] for f in legs_all if f["kind"] == "leg" and f[key] is not None]
        p = [f[key] for f in legs_all if f["kind"] == "push" and f[key] is not None]
        cn = [f[key] for f in contrast_all if f[key] is not None]
        if not a or not cn: return None
        med_c = st.median(cn)
        auc = sum(1 for x in a for y in cn if (x > y if higher else x < y)) / (len(a) * len(cn))
        return dict(feat=name, leg_med=st.median(a), push_med=st.median(p) if p else None, con_med=med_c,
                    leg_n=len(a), con_n=len(cn), auc=auc,
                    frac_leg_beyond=sum(1 for x in a if (x > med_c if higher else x < med_c)) / len(a))
    FE = [enrich("aggressor imbalance last30s (buy-sell)/tot", "aggr30"),
          enrich("tick-rate accel (last30 / prior60 rate)", "rate_accel"),
          enrich("prints in last 30s", "n30"),
          enrich("spread last30 (rel, lower=tighter)", "spread30", higher=False),
          enrich("bid-size share last30 (bid/(bid+ask))", "bidshare30"),
          enrich("seconds since last print", "since_last", higher=False),
          enrich("micro higher-lows share (5s lows rising)", "micro_hl"),
          enrich("30s range (hi/lo-1)", "range30")]
    # deltas: last30 vs prior60 within window
    def delta(fs, k1, k0):
        return [f[k1] - f[k0] for f in fs if f[k1] is not None and f[k0] is not None]
    D = {}
    for nm, k1, k0 in (("aggr delta", "aggr30", "aggr_prior"), ("spread delta", "spread30", "spread_prior"), ("bidshare delta", "bidshare30", "bidshare_prior")):
        D[nm] = (st.median(delta([f for f in legs_all if f["kind"] == "leg"], k1, k0) or [float("nan")]),
                 st.median(delta(contrast_all, k1, k0) or [float("nan")]))
    # thresholds for entry (a): median leg values of the two strongest features (aggr30, rate_accel)
    thr_aggr = st.median([f["aggr30"] for f in legs_all if f["kind"] == "leg" and f["aggr30"] is not None] or [0.3])
    thr_rate = st.median([f["rate_accel"] for f in legs_all if f["kind"] == "leg" and f["rate_accel"] is not None] or [1.5])
    # ---- pass 3: entries ----
    ceiling = []
    for c in C:
        k = (c["sym"], c["date"])
        if k not in tape: continue
        bars, tr, hl, _ = tape[k]; q = Q[k]; i0 = c["i0"]
        rat = None
        sigs_b = entry_b(bars, i0)
        # quotes for entry (a) need full-day coverage: use SIP quotes pulled for windows only -> pull day quotes lazily
        qday = q
        try:
            qday = quotes_win(c["sym"], c["date"], max(c["crown_eff"] - 100, RTH0), RTH1)
        except Exception as e: print("QDAY ERR", c["sym"], e)
        sigs_a = entry_a(bars, i0, tr, qday, thr_aggr, thr_rate)
        c["n_sig_a"] = len(sigs_a); c["n_sig_b"] = len(sigs_b)
        for tag, sigs in (("a", sigs_a), ("b", sigs_b)):
            for s in sigs[:6]:
                i, stop = s[0], s[1]
                px = (bars[i]["o"] if len(s) > 2 else bars[i]["c"]) * (1 + ENTRY_SLIP)
                if stop >= px or bars[i]["t"] >= FLAT: continue
                rat = struct_ratchet(bars, hl, bars[i]["t"])
                for v in ("E3", "E4", "E4W", "STRUCT"):
                    pnl, why, xi = sim(bars, i, px, stop, v, hl, rat)
                    per_entry[(tag, v)].append(dict(sym=c["sym"], date=c["date"], t=et(bars[i]["t"]), px=px, stop=stop, pnl=pnl, why=why, xt=et(bars[xi]["t"])))
        # (c) hold-a-core: FIRST pullback after crown (first entry_b signal), hold to 15:45 with each exit
        if sigs_b:
            i, stop = sigs_b[0]; px = bars[i]["c"] * (1 + ENTRY_SLIP)
            if stop < px and bars[i]["t"] < FLAT:
                rat = struct_ratchet(bars, hl, bars[i]["t"])
                for v in ("E3", "E4", "E4W", "STRUCT"):
                    pnl, why, xi = sim(bars, i, px, stop, v, hl, rat)
                    per_entry[("c", v)].append(dict(sym=c["sym"], date=c["date"], t=et(bars[i]["t"]), px=px, stop=stop, pnl=pnl, why=why, xt=et(bars[xi]["t"])))
                    if v == "E4W": c["ceiling_e4w"] = pnl
        c["ceiling_e4w"] = c.get("ceiling_e4w", 0.0)
        c["left_on_table"] = c["ceiling_e4w"] - c["our_pnl"]
    # ---- scorecards ----
    def score(tr):
        if not tr: return dict(N=0)
        by_day = {}
        for x in tr: by_day[x["date"]] = by_day.get(x["date"], 0.0) + x["pnl"]
        eq = 0.0; peak = 0.0; dd = 0.0; curve = []
        for d in DATES:
            eq += by_day.get(d, 0.0); peak = max(peak, eq); dd = min(dd, eq - peak); curve.append((d, round(eq, 2)))
        first = [x for x in tr if x["date"] <= "2026-08-10"]; second = [x for x in tr if x["date"] > "2026-08-10"]
        return dict(N=len(tr), total=sum(x["pnl"] for x in tr), per=sum(x["pnl"] for x in tr) / len(tr),
                    win=sum(1 for x in tr if x["pnl"] > 0) / len(tr), hr=sum(1 for x in tr if x["pnl"] >= 250),
                    worst=min(x["pnl"] for x in tr), best=max(x["pnl"] for x in tr), dd=dd,
                    h1=sum(x["pnl"] for x in first), h2=sum(x["pnl"] for x in second), curve=curve,
                    prem=sum(x["pnl"] for x in tr if x["pnl"] >= 250))
    SC = {f"{e}/{v}": score(t) for (e, v), t in per_entry.items()}
    out = dict(cohort=[{k: v for k, v in c.items() if k not in ("ev",)} for c in C], legs=legs_all, contrast=contrast_all,
               enrich=FE, deltas=D, thr=dict(aggr=thr_aggr, rate=thr_rate), scores=SC,
               trades={f"{e}/{v}": t for (e, v), t in per_entry.items()})
    for c in out["cohort"]:
        for kk in ("legs", "pushes"):
            c[kk] = [dict(t=et(e["t"]), gain=round(e["gain"], 3), lo=e["lo"], hi=e["hi"]) for e in c.get(kk, [])]
    json.dump(out, open(KT + "/crown_rockets_20260816_rows.json", "w"), indent=0, default=str)
    fh = [f for f in legs_all if f["kind"] == "leg"]
    print("LEGS", len(fh), "from-halt(since_last>=60s)", sum(1 for f in fh if (f["since_last"] or 0) >= 60), "with quotes", sum(1 for f in fh if f["aggr30"] is not None))
    print(json.dumps(FE, indent=1)); print("deltas", D); print("thr", thr_aggr, thr_rate)
    for k, s in SC.items(): print(k, {a: (round(b, 2) if isinstance(b, float) else b) for a, b in s.items() if a != "curve"})
    print("crown table left", sum(c.get("left_on_table", 0) for c in C), "our pnl", sum(c.get("our_pnl", 0) for c in C))

if __name__ == "__main__":
    main()
