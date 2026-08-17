#!/usr/bin/env python3
"""KEV ROSETTA — reconstruct Kev's NAMED fills at tick level, compute the feature set at his bar, and rank
his bar against every same-surface look-alike bar on the same name-day he did NOT take.
Analysis only. Ticks cached under data/universe/ticks_kev_fills/ (gitignored).

Usage:
  python3 kev_rosetta_20260816.py pull      # resolve dates + pull SIP trades/quotes for each fill
  python3 kev_rosetta_20260816.py recon     # locate fill bars, features, look-alikes, outcomes -> rows json
  python3 kev_rosetta_20260816.py gen       # generalization test on the fastchart replay tick cohort
"""
import os, sys, json, gzip, math, statistics as st, datetime as dt, glob, importlib.util, subprocess, time
ROOT = "/Users/marcosolivera/Desktop/Marcos-Trading-Bot"; KT = ROOT + "/data/killtests"
CACHE = ROOT + "/data/universe/ticks_kev_fills"; os.makedirs(CACHE + "/trades", exist_ok=True); os.makedirs(CACHE + "/quotes", exist_ok=True)
SCR = "/private/tmp/claude-501/-Users-marcosolivera-Desktop-website-data/add2ac85-fd80-47f7-b583-bda802f0544d/scratchpad"
FILLS = KT + "/kev_rosetta_20260816_fills.json"
OUT = KT + "/kev_rosetta_20260816_rows.json"

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
R = _load("R", KT + "/kev_fastchart_replay_20260816.py")   # detectors, enrich, sim, Ctx, halts
RTH0, CUT, FLAT = R.RTH0, R.CUT, R.FLAT
et = R.et

# ---------------- alpaca ----------------
_KEY = _SEC = None
def keys():
    global _KEY, _SEC
    if _KEY: return _KEY, _SEC
    _KEY = os.environ.get("ALPACA_KEY"); _SEC = os.environ.get("ALPACA_SECRET")
    if not _KEY:
        kv = subprocess.run(["railway", "variables", "--service", "Marcos-Trading-Bot", "--kv"], capture_output=True, text=True, cwd=ROOT).stdout
        for ln in kv.splitlines():
            if ln.startswith("ALPACA_KEY="): _KEY = ln.split("=", 1)[1].strip()
            if ln.startswith("ALPACA_SECRET="): _SEC = ln.split("=", 1)[1].strip()
    return _KEY, _SEC
import requests
S = requests.Session()
def H():
    k, s = keys(); return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}
def fetch(kind, sym, start, end):
    fn = f"{CACHE}/{kind}/{start[:10]}_{sym}_{start[11:19].replace(':','')}_{end[11:19].replace(':','')}.json.gz"
    if os.path.exists(fn):
        with gzip.open(fn, "rt") as f: return json.load(f)
    out, tok = [], None
    while True:
        p = {"start": start, "end": end, "feed": "sip", "limit": 10000}
        if tok: p["page_token"] = tok
        for att in range(6):
            r = S.get(f"https://data.alpaca.markets/v2/stocks/{sym}/{kind}", headers=H(), params=p, timeout=60)
            if r.status_code == 429: time.sleep(2 + 3 * att); continue
            if r.status_code >= 500: time.sleep(1 + att); continue
            break
        if r.status_code != 200: print("ERR", sym, kind, start, r.status_code, r.text[:100], file=sys.stderr); return None
        j = r.json(); out += j.get(kind) or []; tok = j.get("next_page_token")
        if not tok: break
    with gzip.open(fn, "wt") as f: json.dump(out, f)
    return out
def daily(sym, d0, d1):
    fn = f"{CACHE}/daily_{sym}_{d0}_{d1}.json"
    if os.path.exists(fn): return json.load(open(fn))
    r = S.get(f"https://data.alpaca.markets/v2/stocks/{sym}/bars", headers=H(), params={"timeframe": "1Day", "start": d0, "end": d1, "feed": "sip", "limit": 1000, "adjustment": "raw"}, timeout=60)
    b = (r.json().get("bars") or []) if r.status_code == 200 else []
    json.dump(b, open(fn, "w")); return b

# ---------------- ticks -> bars ----------------
def clean_ticks(tr):
    out = []
    for t in tr:
        c = t.get("c") or []
        if any(x in c for x in ("C", "G", "H", "I", "M", "N", "P", "Q", "R", "T", "U", "V", "W", "Z", "4", "7", "9")): continue
        ts = t["t"]; s = int(ts[11:13]) * 3600 + int(ts[14:16]) * 60 + float(ts[17:ts.index("Z")])
        out.append((s, float(t["p"]), int(t["s"])))
    out.sort(); return out
def quotes_series(q):
    out = []
    for x in q or []:
        ts = x["t"]; s = int(ts[11:13]) * 3600 + int(ts[14:16]) * 60 + float(ts[17:ts.index("Z")])
        if x["bp"] > 0 and x["ap"] > 0 and x["ap"] >= x["bp"]: out.append((s, float(x["bp"]), float(x["ap"]), int(x["bs"]), int(x["as"])))
    out.sort(); return out

def enrich_full(bars):
    """R.enrich + 20-bar/90-bar SMA + 1-min VWAP-anchored premarket (VWAP is cumulative from first tick of the day 04:00 = premarket anchor)."""
    R.enrich(bars)
    cs = [b["c"] for b in bars]
    for i, b in enumerate(bars):
        b["ma90"] = st.mean(cs[max(0, i - 89):i + 1])
        b["ma20"] = st.mean(cs[max(0, i - 19):i + 1])
    return bars

# ---------------- feature set at bar i ----------------
import bisect
def features(bars, i, ticks, tsec_idx, quotes, halt_ts, pc, sess_open_idx):
    b = bars[i]; px = b["c"]; t = b["t"]
    f = {}
    f["t"] = t; f["et"] = et(t)
    f["min_since_open"] = round((t - RTH0) / 60, 1)
    f["day_gain_pct"] = round((px / pc - 1) * 100, 1) if pc else None
    # session (from 04:00) high/low up to i
    hi = max(x["h"] for x in bars[:i + 1]); lo = min(x["l"] for x in bars[:i + 1])
    hi_i = max(range(i + 1), key=lambda k: bars[k]["h"])
    f["dist_sess_hi_pct"] = round((hi / px - 1) * 100, 2); f["dist_sess_lo_pct"] = round((px / lo - 1) * 100, 2)
    f["min_since_sess_hi"] = round((t - bars[hi_i]["t"]) / 60, 1)
    # RTH-only high
    rth = [x for x in bars[:i + 1] if x["t"] >= RTH0]
    f["dist_rth_hi_pct"] = round((max(x["h"] for x in rth) / px - 1) * 100, 2) if rth else None
    # position within last 5 minutes range
    w5 = [x for x in bars[max(0, i - 30):i + 1]]
    h5 = max(x["h"] for x in w5); l5 = min(x["l"] for x in w5)
    f["pos_in_5m_range"] = round((px - l5) / (h5 - l5), 2) if h5 > l5 else None
    f["rng5m_pct"] = round((h5 / l5 - 1) * 100, 2)
    # indicators
    f["vwap_dist_pct"] = round((px / b["vwap"] - 1) * 100, 2)
    f["e9_dist_pct"] = round((px / b["e9"] - 1) * 100, 2)
    f["e20_dist_pct"] = round((px / b["e20"] - 1) * 100, 2)
    f["ma90_dist_pct"] = round((px / b["ma90"] - 1) * 100, 2)
    f["vwap_e9_gap_pct"] = round(abs(b["vwap"] - b["e9"]) / px * 100, 2)   # confluence tightness
    f["front_side"] = int(px > b["vwap"] and b["e9"] > b["e20"])
    # bar anatomy
    r = b["h"] - b["l"]
    f["bar_rng_pct"] = round(r / px * 100, 2)
    f["lower_wick_frac"] = round((min(b["o"], b["c"]) - b["l"]) / r, 2) if r > 0 else 0
    f["bar_green"] = int(b["c"] >= b["o"])
    # pullback anatomy: leg high = highest high since the last time price was >3% below a running high; depth/duration
    lh = b["h"]; lh_i = i
    k = i
    while k > 0 and bars[k]["l"] > hi * 0.97 or k == i:   # walk back inside the leg (until a >3% pullback from sess-hi)
        if bars[k]["h"] >= lh: lh = bars[k]["h"]; lh_i = k
        k -= 1
        if i - k > 720: break
    f["pb_depth_pct"] = round((lh / b["l"] - 1) * 100, 2)          # how deep this pullback (leg high -> bar low)
    f["pb_dur_bars"] = i - lh_i                                        # bars since leg high
    # touches: how many prior bars in the session came within 0.3% of this bar's low (retest count) - excluding last 3 bars
    lvl = b["l"]; f["prior_touches_at_low"] = sum(1 for x in bars[max(0, i - 360):i - 3] if x["l"] <= lvl * 1.003 and x["h"] >= lvl * 0.997)
    f["first_touch"] = int(f["prior_touches_at_low"] == 0)
    # pullbacks so far in this leg (count of prior bars in [k+1, i) that were 'reclaim' bars: low undercut prior low and close above open)
    n_pb = 0
    for j in range(max(1, k + 1), i):
        x = bars[j]; p = bars[j - 1]
        if x["l"] < p["l"] and x["c"] > x["o"] and x["c"] > p["c"]: n_pb += 1
    f["prior_pullbacks_in_leg"] = n_pb
    # consolidation before: consecutive prior bars whose range sits inside a 1.5% band
    n = 0; top = b["h"]; bot = b["l"]
    for j in range(i - 1, max(0, i - 120), -1):
        top = max(top, bars[j]["h"]); bot = min(bot, bars[j]["l"])
        if top / bot - 1 > 0.015: break
        n += 1
    f["consol_bars_before"] = n
    # whole/half dollar proximity
    step = 1.0 if px >= 1 else 0.10
    near = round(px / step) * step; f["dist_whole_pct"] = round(abs(px - near) / px * 100, 2)
    half = round(px / (step / 2)) * (step / 2); f["dist_half_pct"] = round(abs(px - half) / px * 100, 2)
    # halts
    prior_h = [h for h in halt_ts if h <= t]
    f["min_since_halt"] = round((t - prior_h[-1]) / 60, 1) if prior_h else None
    f["halts_so_far"] = len(prior_h)
    # tape: ticks in prior 30s, aggressor buy fraction (vs NBBO mid), spread bps at bar close, volume ratio
    j0 = bisect.bisect_left(tsec_idx, t + 10 - 30); j1 = bisect.bisect_left(tsec_idx, t + 10)
    win = ticks[j0:j1]; f["ticks_30s"] = len(win)
    f["vol_30s"] = sum(v for _, _, v in win)
    if quotes:
        qt = [q[0] for q in quotes]
        def nbbo(ts):
            k = bisect.bisect_right(qt, ts) - 1
            return quotes[k] if k >= 0 else None
        buy = sell = 0
        for s, p, v in win:
            q = nbbo(s)
            if not q: continue
            mid = (q[1] + q[2]) / 2
            if p > mid + 1e-9: buy += v
            elif p < mid - 1e-9: sell += v
        f["buy_frac_30s"] = round(buy / (buy + sell), 2) if buy + sell else None
        q = nbbo(t + 9.999)
        f["spread_bps"] = round((q[2] - q[1]) / ((q[1] + q[2]) / 2) * 1e4, 1) if q else None
        f["ask_bid_size_ratio"] = round(q[4] / q[3], 2) if q and q[3] else None
    else:
        f["buy_frac_30s"] = f["spread_bps"] = f["ask_bid_size_ratio"] = None
    pv = [bars[k]["v"] for k in range(max(0, i - 30), i)]
    f["vol_ratio_30"] = round(b["v"] / st.median(pv), 2) if pv and st.median(pv) > 0 else None
    # 1-min structure: is the current 1-min bar green so far, and how many 1-min higher lows in a row
    return f

# ---------------- look-alike definitions ----------------
def is_reclaim_bar(bars, i, ctx_hi):
    """surface pattern (Cue A/C family): a pullback bar whose low undercuts the prior bar's low OR touches VWAP/9EMA
    (within 0.5%), and closes green and back above the prior close. Must be a pullback (h < running high)."""
    b, p = bars[i], bars[i - 1]
    if b["h"] >= ctx_hi: return False
    touch = (b["l"] <= max(b["vwap"], b["e9"]) * 1.005 and b["c"] > max(b["vwap"], b["e9"])) or (b["l"] < p["l"] and b["c"] > p["c"])
    return touch and b["c"] > b["o"]
def is_level_hold(bars, i):
    """surface pattern (Cue B): whole/half-dollar (10c sub-$1) level broken within last 6 bars and lows of the last 3 bars >= L; bar i is the 4th."""
    b = bars[i]; step = 1.0 if b["c"] >= 1 else 0.10
    for j in range(i - 6, i - 2):
        if j < 1: continue
        x, p = bars[j], bars[j - 1]
        for L in (math.floor(x["c"] / step) * step, math.floor(x["c"] / (step / 2)) * (step / 2)):
            if L > 0 and p["c"] <= L < x["c"] and all(bars[k]["l"] >= L for k in range(j + 1, i)) and b["l"] >= L: return L
    return None


# ---------------- STEP 3b: sequence encoding ----------------
def event_string(bars, i, halt_idx, lookback=60):
    """ordered event alphabet over bars [i-lookback, i]: P push to new local(30-bar) high, B break of session high, T test of
    session high w/o break, F flush >=2% (3-bar high -> bar low), W wick at VWAP/9MA bought back, H hold above whole/half
    level >=3 bars after break, R retest of a level broken in last 5 min, L halt resumption, Q compression (>=6 bars, <=1%),
    D lower low (below prior 6-bar low, not W). Consecutive duplicates collapsed. Ends at bar i (his entry bar)."""
    ev = []; hs = set(halt_idx)
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
        if b["l"] <= conf * 1.005 and b["c"] > conf and b["c"] > b["o"] and b["h"] < loc_hi: e.append("W")
        elif is_level_hold(bars, k) is not None: e.append("H")
        else:
            # retest of a level broken (upward close) within last 30 bars: whole/half dollar
            step = 1.0 if b["c"] >= 1 else 0.10; got = False
            for L in (math.floor(b["c"] / step) * step, math.floor(b["c"] / (step/2)) * (step/2)):
                if L <= 0: continue
                if abs(b["l"] - L) / L <= 0.003 and b["c"] > L and any(bars[j-1]["c"] <= L < bars[j]["c"] for j in range(max(1, k - 30), k - 1)):
                    got = True; break
            if got: e.append("R")
        if "W" not in e and "H" not in e and b["l"] < min(x["l"] for x in bars[max(0, k - 6):k]): e.append("D")
        # compression
        w = bars[max(0, k - 5):k + 1]
        if len(w) == 6 and max(x["h"] for x in w) / min(x["l"] for x in w) - 1 <= 0.01: q_run += 1
        else:
            if q_run >= 1 and (not ev or ev[-1] != "Q"): ev.append("Q")
            q_run = 0
        for x in e:
            if not ev or ev[-1] != x: ev.append(x)
    if q_run >= 1 and (not ev or ev[-1] != "Q"): ev.append("Q")
    return " ".join(ev)

# ---------------- outcome sims ----------------
def outcomes(bars, i, entry, stop, halt_idx):
    out = {}
    hs = set(halt_idx)
    for mode in ("KEV", "E3", "E4W", "F"):
        p, why, k = R.sim(bars, i, entry, stop, mode, entry if mode == "KEV" else stop, hs)
        out[mode] = round(p, 2); out[mode + "_why"] = why; out[mode + "_bars"] = k - i
    # what did the tape do: max favourable in 5/15/60 min, and did it hit 2R
    risk = entry - stop
    for m in (5, 15, 60):
        seg = [x for x in bars[i + 1:] if x["t"] <= bars[i]["t"] + m * 60]
        out[f"mfe{m}m_pct"] = round((max(x["h"] for x in seg) / entry - 1) * 100, 2) if seg else None
        out[f"mae{m}m_pct"] = round((min(x["l"] for x in seg) / entry - 1) * 100, 2) if seg else None
    seg = bars[i + 1:]
    hit2r = None
    for x in seg:
        if x["l"] <= stop: hit2r = False; break
        if x["h"] >= entry + 2 * risk: hit2r = True; break
    out["hit_2R_before_stop"] = hit2r
    return out

# ---------------- main steps ----------------
def resolve_dates(fills):
    """for each fill: verify entry price sits inside the day's [low, high] on the stated date; else scan +-14 days
    of the manifest-run window for the nearest day whose range contains the price. Stamps date_resolved + basis."""
    for f in fills:
        sym = f["sym"]; px = f.get("entry")
        if px is None: f["date_resolved"] = None; f["resolve_note"] = "no entry price"; continue
        d = f.get("date")
        d0 = (dt.date.fromisoformat(d) - dt.timedelta(days=14)).isoformat() if d else "2026-05-01"
        d1 = (dt.date.fromisoformat(d) + dt.timedelta(days=14)).isoformat() if d else "2026-08-16"
        bars = daily(sym, d0, d1)
        ok = [b["t"][:10] for b in bars if b["l"] <= px * 1.02 and b["h"] >= px * 0.98]
        # note: 1Day SIP bars include extended hours? Alpaca daily = RTH only; premarket fills may fall outside -> tolerate 2%
        if d and d in ok: f["date_resolved"] = d; f["resolve_note"] = "stated date, price in range"
        elif d and any(b["t"][:10] == d for b in bars):
            db = [b for b in bars if b["t"][:10] == d][0]
            # premarket entries can be outside daily RTH range; accept if within 30% of range and session PRE
            if f.get("session") == "PRE" and db["l"] * 0.7 <= px <= db["h"] * 1.3: f["date_resolved"] = d; f["resolve_note"] = "stated date, PRE, price near range"
            elif ok:
                near = min(ok, key=lambda x: abs((dt.date.fromisoformat(x) - dt.date.fromisoformat(d)).days))
                f["date_resolved"] = near; f["resolve_note"] = f"stated {d} range {db['l']}-{db['h']} excludes {px}; nearest in-range day {near}"
            else: f["date_resolved"] = None; f["resolve_note"] = f"stated {d} range {db['l']}-{db['h']} excludes {px}; no in-range day +-14d"
        elif ok:
            f["date_resolved"] = ok[0] if len(ok) == 1 else ok[-1]; f["resolve_note"] = f"no/unknown date; in-range days {ok}"
        else: f["date_resolved"] = None; f["resolve_note"] = "no in-range day found"
    return fills

def pull(fills):
    for f in fills:
        d = f.get("date_resolved")
        if not d: continue
        tr = fetch("trades", f["sym"], f"{d}T08:00:00Z", f"{d}T20:00:00Z")
        f["n_ticks"] = len(tr) if tr is not None else None
        print(f["sym"], d, f["n_ticks"], flush=True)

def locate(bars, f, ticks):
    """candidate fill bar: window from session + approx_time; first 10s bar in window that trades through the entry
    price (l <= px <= h) AFTER price has been above px in the prior 3 min (i.e., a pullback into it), tolerance 0.4%.
    Fallback: first touch. Returns (index, method)."""
    px = f["entry"]; tol = 0.004
    if f.get("session") == "PRE": w0, w1 = 8 * 3600, RTH0
    elif f.get("session") == "RTH": w0, w1 = RTH0, 20 * 3600
    else: w0, w1 = 8 * 3600, 20 * 3600
    if f.get("approx_time"):
        try:
            hh, mm = f["approx_time"].split(":")[:2]; ts = int(hh) * 3600 + int(mm) * 60 + 4 * 3600
            w0, w1 = max(w0, ts - 1500), min(w1, ts + 1500)
        except Exception: pass
    cands = [i for i, b in enumerate(bars) if w0 <= b["t"] < w1 and b["l"] <= px * (1 + tol) and b["h"] >= px * (1 - tol)]
    note = ""
    if not cands:
        cands = [i for i, b in enumerate(bars) if 8 * 3600 <= b["t"] < 20 * 3600 and b["l"] <= px * (1 + tol) and b["h"] >= px * (1 - tol)]
        note = " [SESSION MISMATCH: no touch in stated window, whole day used]"
        if not cands:
            tol = 0.012
            cands = [i for i, b in enumerate(bars) if 8 * 3600 <= b["t"] < 20 * 3600 and b["l"] <= px * (1 + tol) and b["h"] >= px * (1 - tol)]
            note = " [SESSION MISMATCH + 1.2% tolerance]"
            if not cands: return None, "no touch anywhere"
    for i in cands:
        prior = bars[max(0, i - 18):i]
        if prior and max(x["h"] for x in prior) > px * 1.01 and bars[i]["c"] >= px * (1 - tol):
            return i, "first pullback-through in window" + note
    return cands[0], "first touch in window (no pullback context)" + note

def recon(fills):
    rows = []
    for f in fills:
        d = f.get("date_resolved")
        if not d: continue
        tr = fetch("trades", f["sym"], f"{d}T08:00:00Z", f"{d}T20:00:00Z")
        if not tr: continue
        ticks = clean_ticks(tr); tsi = [x[0] for x in ticks]
        bars = enrich_full(R.bars_from_ticks(ticks, 10))
        pc = R.prev_close(d, f["sym"])
        hidx = R.halts(bars); halt_ts = [bars[k]["t"] for k in hidx]
        i, method = locate(bars, f, ticks)
        if i is None: rows.append({"fill": f, "located": False, "note": method}); print("NOLOC", f["sym"], d, f["entry"], method); continue
        b = bars[i]
        # quotes for +-10 min around fill and for the whole day (needed for look-alikes) — pull whole RTH+PRE quotes once
        q = fetch("quotes", f["sym"], f"{d}T08:00:00Z", f"{d}T20:00:00Z")
        quotes = quotes_series(q)
        feat = features(bars, i, ticks, tsi, quotes, halt_ts, pc, None)
        stop = f.get("stop") or b["l"]
        entry = f["entry"]
        oc = outcomes(bars, i, entry, stop, hidx)
        # look-alikes: every reclaim bar + level-hold bar in the same session window (excluding +-2 bars of his)
        la = []
        run_hi = -1
        for k in range(1, len(bars)):
            run_hi = max(run_hi, bars[k - 1]["h"])
            if bars[k]["t"] < 8 * 3600 or bars[k]["t"] >= FLAT: continue
            kind = None
            if is_reclaim_bar(bars, k, run_hi): kind = "reclaim"
            elif is_level_hold(bars, k) is not None: kind = "level_hold"
            if kind is None: continue
            if abs(k - i) <= 2: continue
            fk = features(bars, k, ticks, tsi, quotes, halt_ts, pc, None)
            ok = outcomes(bars, k, bars[k]["c"], bars[k]["l"], hidx)
            la.append({"i": k, "kind": kind, "f": fk, "seq": event_string(bars, k, hidx), "o": {m: ok[m] for m in ("KEV", "E3", "E4W", "F", "mfe15m_pct", "hit_2R_before_stop")}})
        his_kind = "reclaim" if is_reclaim_bar(bars, i, max(x["h"] for x in bars[:i])) else ("level_hold" if is_level_hold(bars, i) is not None else "neither")
        rows.append({"fill": f, "located": True, "method": method, "i": i, "bar": {k: b[k] for k in ("t", "o", "h", "l", "c", "v")}, "his_kind": his_kind,
                     "f": feat, "o": oc, "seq": event_string(bars, i, hidx), "lookalikes": la, "n_lookalikes": len(la), "n_bars": len(bars)})
        print(f["sym"], d, f["entry"], "->", et(b["t"]), method, "kind", his_kind, "LA", len(la), "KEV", oc["KEV"], "E3", oc["E3"], "2R", oc["hit_2R_before_stop"], "|", rows[-1]["seq"], flush=True)
    json.dump(rows, open(OUT, "w"))
    return rows

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "recon"
    fills = json.load(open(FILLS))
    if cmd == "pull":
        fills = resolve_dates(fills); json.dump(fills, open(FILLS, "w"), indent=1)
        for f in fills: print(f["sym"], f.get("date"), "->", f.get("date_resolved"), "|", f.get("resolve_note"))
        pull(fills); json.dump(fills, open(FILLS, "w"), indent=1)
    elif cmd == "recon":
        recon(fills)

# ---------------- STEP 3 ranking + 3b suffixes ----------------
NUMERIC_SKIP = {"t", "et"}
def pct_rank(v, arr):
    arr = [a for a in arr if a is not None]
    if v is None or len(arr) < 5: return None
    lo = sum(1 for a in arr if a < v); eq = sum(1 for a in arr if a == v)
    return (lo + 0.5 * eq) / len(arr)
def rank_features(rows):
    per = {}   # feature -> list of (fill, pct)
    for r in rows:
        if not r.get("located") or not r["lookalikes"]: continue
        for k, v in r["f"].items():
            if k in NUMERIC_SKIP or not isinstance(v, (int, float)): continue
            p = pct_rank(v, [la["f"].get(k) for la in r["lookalikes"]])
            if p is not None: per.setdefault(k, []).append((r["fill"]["sym"] + " " + r["fill"]["date_resolved"], p, v))
    out = []
    for k, l in per.items():
        ps = [p for _, p, _ in l]; m = st.mean(ps)
        hi = sum(1 for p in ps if p >= 0.75) / len(ps); lo = sum(1 for p in ps if p <= 0.25) / len(ps)
        side = "HIGH" if m >= 0.5 else "LOW"; cons = hi if side == "HIGH" else lo
        out.append({"feature": k, "n": len(ps), "mean_pct": round(m, 3), "side": side, "consistency": round(cons, 2), "score": round(abs(m - 0.5) * cons, 3),
                    "his_values": [round(v, 2) for _, _, v in l], "pcts": [round(p, 2) for p in ps]})
    return sorted(out, key=lambda x: -x["score"])
def suffixes(rows, k=3, structural=False):
    def s(x):
        ev = x.split()
        if structural: ev = [e for e in ev if e not in ("F", "D")]; ev = [e for i, e in enumerate(ev) if i == 0 or ev[i-1] != e]
        return " ".join(ev[-k:])
    his = {}; la = {}
    for r in rows:
        if not r.get("located"): continue
        his[s(r["seq"])] = his.get(s(r["seq"]), 0) + 1
        for x in r["lookalikes"]:
            la[s(x["seq"])] = la.get(s(x["seq"]), 0) + 1
    nla = sum(la.values()) or 1
    return sorted([(sfx, n, round(n / max(1, sum(his.values())) * 100), la.get(sfx, 0), round(la.get(sfx, 0) / nla * 100, 1)) for sfx, n in his.items()], key=lambda x: -x[1])

# ---------------- STEP 5 generalization ----------------
def gen(clauses, seq_suffixes=None, seq_structural=False, k=3):
    """clauses: list of (feature, op, thr). Rerun the fastchart tick cohort at 10s (KEV-A/B/C fires), compute features
    at each fire bar, report before/after by detector. Returns dict."""
    coh = R.tick_cohort(); before = []; after = []; nd = 0
    for d, sym in coh:
        tr = R.load_ticks(d, sym)
        if not tr or len(tr) < 200: continue
        pc = R.prev_close(d, sym); pv0, v0, calm = R.premarket_seed(d, sym, tr[0][0])
        bars = R.enrich(R.bars_from_ticks(tr, 10), pv0, v0)
        cs = [b["c"] for b in bars]
        for i, b in enumerate(bars): b["ma90"] = st.mean(cs[max(0, i - 89):i + 1])
        hidx = R.halts(bars); halt_ts = [bars[k]["t"] for k in hidx]
        rows = R.run_series(bars, 10, pc, hidx, "TICK", "10s")
        tsi = [x[0] for x in tr]; tmap = {b["t"]: i for i, b in enumerate(bars)}; nd += 1
        for r in rows:
            if r["gate"] is not None: continue
            i = tmap[r["t"]]
            f = features(bars, i, tr, tsi, None, halt_ts, pc, None)
            r["seq"] = event_string(bars, i, hidx); r["date"] = d; r["sym"] = sym
            ok = all((f.get(feat) is not None) and ((f[feat] >= thr) if op == ">=" else (f[feat] <= thr)) for feat, op, thr in clauses)
            if seq_suffixes is not None:
                ev = r["seq"].split()
                if seq_structural:
                    ev = [e for e in ev if e not in ("F", "D")]; ev = [e for j, e in enumerate(ev) if j == 0 or ev[j-1] != e]
                ok = ok and (" ".join(ev[-k:]) in seq_suffixes)
            r["pass"] = ok; r["feat"] = f
            before.append(r)
            if ok: after.append(r)
    def summ(rs):
        o = {}
        for det in ("A", "B", "C", "ALL"):
            x = [r for r in rs if det == "ALL" or r["det"] == det]
            o[det] = {"N": len(x), **{m: round(sum(r[m] for r in x), 2) for m in ("KEV", "E3", "E4W", "F")}, "win_KEV": round(sum(1 for r in x if r["KEV"] > 0) / len(x) * 100) if x else None}
        return o
    return {"name_days": nd, "before": summ(before), "after": summ(after), "clauses": clauses, "rows_after": after}
