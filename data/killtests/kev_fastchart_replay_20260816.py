#!/usr/bin/env python3
"""KEV FAST-CHART REPLAY — Kev's rocket entries (A confluence wick / B level hold / C halt double-bottom)
coded exactly as spec'd in kev_fast_chart_method_20260816.md, run at 10s (his glass) AND 5s (Marcos's
hypothesis) on IDENTICAL ticks (SIP full-day trades -> 5s and 10s), plus the dashboard 1s capture
(1s -> 5s and 1s -> 10s) as the live-fidelity twin, plus the universe bars10s cache as the 10s-at-scale arm.
Analysis only. Nothing ships.

Exits: KEV-native (stop ratchets to prior-bar low each bar once a bar closes >= entry+1R; failed-breakout
= close back below the entry level; topping tail = upper wick >=60% range on >=2x vol; halt-gap; 15:45),
E3, E4W, F-control (hold to 15:45, -7% catastrophe stop). $500 clip, +1% chase, -0.5% market exits.
"""
import os, sys, json, gzip, math, statistics as st, datetime as dt, glob, bisect
ROOT = "/Users/marcosolivera/Desktop/Marcos-Trading-Bot"; KT = ROOT + "/data/killtests"
TK = ROOT + "/data/universe/ticks_precursor/trades"; B10 = ROOT + "/data/universe/bars10s"
SCR = "/private/tmp/claude-501/-Users-marcosolivera-Desktop-website-data/add2ac85-fd80-47f7-b583-bda802f0544d/scratchpad"
POS = 500.0; SLIP = 0.01; MKT = 0.005
RTH0 = 13 * 3600 + 1800; CUT = 19 * 3600 + 1800; FLAT = 19 * 3600 + 45 * 60; RTH1 = 20 * 3600
MANIFEST = json.load(open(ROOT + "/data/universe/manifest.json"))
CALM_X = 89.9  # joint_door 8/16 p30 calm threshold (bps, median 1-min range/close 09:00-09:30 ET)

def et(s): s -= 4 * 3600; return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"

# ---------------- data ----------------
def prev_close(date, sym):
    for r in MANIFEST.get(date, []):
        if r["sym"] == sym: return r.get("prev_c")
    fn = f"{SCR}/crown/pc_{date}_{sym}.json"
    if os.path.exists(fn): return json.load(open(fn))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("P", KT + "/precursor_multires_pull_20260816.py"); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
        d0 = (dt.date.fromisoformat(date) - dt.timedelta(days=7)).isoformat()
        r = P.S.get(f"https://data.alpaca.markets/v2/stocks/{sym}/bars", headers=P.H, params={"timeframe": "1Day", "start": d0, "end": date, "feed": "sip", "limit": 10, "adjustment": "raw"}, timeout=60)
        bars = [b for b in (r.json().get("bars") or []) if b["t"][:10] < date] if r.status_code == 200 else []
        pc = bars[-1]["c"] if bars else None
    except Exception as e:
        pc = None
    json.dump(pc, open(fn, "w")); return pc

def load_ticks(date, sym):
    fs = sorted(glob.glob(f"{TK}/{date}_{sym}_110000_200000.json.gz")) or sorted(glob.glob(f"{TK}/{date}_{sym}_132500_200000.json.gz"))
    if not fs: return None
    with gzip.open(fs[0], "rt") as f: tr = json.load(f)
    out = []
    for t in tr:
        c = t.get("c") or []
        if any(x in c for x in ("C", "G", "H", "I", "M", "N", "P", "Q", "R", "T", "U", "V", "W", "Z", "4", "7", "9")): continue
        ts = t["t"]; s = int(ts[11:13]) * 3600 + int(ts[14:16]) * 60 + float(ts[17:ts.index("Z")])
        out.append((s, float(t["p"]), int(t["s"])))
    out.sort(); return out

def bars_from_ticks(tr, sec):
    bars = {}
    for s, p, v in tr:
        k = int(s // sec) * sec; b = bars.get(k)
        if b is None: bars[k] = [k, p, p, p, p, v]
        else: b[2] = max(b[2], p); b[3] = min(b[3], p); b[4] = p; b[5] += v
    return [{"t": k, "o": b[1], "h": b[2], "l": b[3], "c": b[4], "v": b[5]} for k, b in sorted(bars.items())]

def load_cache10(date, sym):
    fn = f"{B10}/{date}_{sym}.json"
    if not os.path.exists(fn): return None
    out = []
    for b in json.load(open(fn))["bars"]:
        if not b.get("volume"): continue
        ts = b["time"]; s = int(ts[11:13]) * 3600 + int(ts[14:16]) * 60 + int(ts[17:19])
        out.append({"t": s, "o": b["open"], "h": b["high"], "l": b["low"], "c": b["close"], "v": b["volume"]})
    return out

def load_cap1s(date, sym):
    fn = f"{SCR}/cap/{date}_{sym}_ALP1S.json"
    if not os.path.exists(fn): return None
    raw = json.load(open(fn))
    if len(raw) < 100: return None
    out = []
    for b in raw:
        ts = b["time"]; s = int(ts[11:13]) * 3600 + int(ts[14:16]) * 60 + int(ts[17:19])
        out.append({"t": s, "o": float(b["open"]), "h": float(b["high"]), "l": float(b["low"]), "c": float(b["close"]), "v": float(b["volume"])})
    out.sort(key=lambda b: b["t"]); return out

def rebar(bars, sec):
    """aggregate finer bars into sec buckets (open=first, high=max, low=min, close=last, vol=sum)."""
    out = {}
    for b in bars:
        k = int(b["t"] // sec) * sec; x = out.get(k)
        if x is None: out[k] = {"t": k, "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b["v"]}
        else: x["h"] = max(x["h"], b["h"]); x["l"] = min(x["l"], b["l"]); x["c"] = b["c"]; x["v"] += b["v"]
    return [out[k] for k in sorted(out)]

def premarket_seed(date, sym, t_start):
    """cumulative pv, v from the bars10s cache before t_start (VWAP anchor = premarket, settled)."""
    c = load_cache10(date, sym)
    if not c: return 0.0, 0.0, None
    pv = v = 0.0; calm = None
    onemin = {}
    for b in c:
        if b["t"] < t_start: pv += (b["h"] + b["l"] + b["c"]) / 3 * b["v"]; v += b["v"]
        if 13 * 3600 <= b["t"] < RTH0:
            k = int(b["t"] // 60); x = onemin.setdefault(k, [b["h"], b["l"], b["c"]])
            x[0] = max(x[0], b["h"]); x[1] = min(x[1], b["l"]); x[2] = b["c"]
    if len(onemin) >= 5:
        calm = st.median([(h - l) / c * 1e4 for h, l, c in onemin.values() if c > 0])
    return pv, v, calm

def calm_from_bars(bars):
    onemin = {}
    for b in bars:
        if 13 * 3600 <= b["t"] < RTH0:
            k = int(b["t"] // 60); x = onemin.setdefault(k, [b["h"], b["l"], b["c"]])
            x[0] = max(x[0], b["h"]); x[1] = min(x[1], b["l"]); x[2] = b["c"]
    if len(onemin) >= 5: return st.median([(h - l) / c * 1e4 for h, l, c in onemin.values() if c > 0])
    return None

# ---------------- indicators + context ----------------
def enrich(bars, pv0=0.0, v0=0.0):
    pv, v = pv0, v0; e9 = e20 = None; k9, k20 = 2 / 10, 2 / 21
    for b in bars:
        pv += (b["h"] + b["l"] + b["c"]) / 3 * b["v"]; v += b["v"]
        b["vwap"] = pv / v if v else b["c"]
        e9 = b["c"] if e9 is None else e9 + k9 * (b["c"] - e9)
        e20 = b["c"] if e20 is None else e20 + k20 * (b["c"] - e20)
        b["e9"], b["e20"] = e9, e20
    return bars

def halts(bars):
    out = []
    for i in range(1, len(bars)):
        if bars[i]["t"] - bars[i - 1]["t"] >= 240 and bars[i - 1]["t"] >= RTH0: out.append(i)
    return out  # first post-resumption bar indices

class Ctx:
    """session high / legs / topping-tail cluster / front-side. Walk bars in order."""
    def __init__(self, bars, sec, pc):
        self.b = bars; self.sec = sec; self.pc = pc
        self.sess_hi = -1; self.sess_hi_t = None; self.leg = 0; self.pulled = True; self.leg_hi = -1
        self.win = 300 // sec  # 5 min of bars
    def step(self, i):
        b = self.b[i]
        if b["h"] > self.sess_hi:
            if self.pulled: self.leg += 1; self.pulled = False
            self.sess_hi = b["h"]; self.sess_hi_t = b["t"]; self.leg_hi = b["h"]
        elif b["l"] < self.sess_hi * 0.97: self.pulled = True
    def gain(self, px): return px / self.pc - 1 if self.pc else None
    def topping_cluster(self, i):
        n = 0
        for k in range(max(0, i - self.win), i):
            b = self.b[k]; r = b["h"] - b["l"]
            if r > 0 and (b["h"] - max(b["o"], b["c"])) / r >= 0.60: n += 1
        return n >= 2
    def room_ok(self, i, px):
        if self.sess_hi <= px: return True                          # blue sky
        over = self.sess_hi / px - 1
        if over <= 0.03 and (self.b[i]["t"] - self.sess_hi_t) > 300: return False   # stale high overhead
        return True
    def front_side(self, i):
        b = self.b[i]; return b["c"] > b["vwap"] and b["e9"] > b["e20"]

def gates(ctx, i, px, mover):
    b = ctx.b[i]
    if not (RTH0 <= b["t"] < CUT): return "hours"
    if not mover: return "not_mover"
    if not ctx.front_side(i): return "backside"
    if not ctx.room_ok(i, px): return "no_room"
    if ctx.topping_cluster(i): return "topping_cluster"
    return None

# ---------------- detectors ----------------
def det_A(bars, ctx, i):
    """bar i is a confluence-wick bar: low tests VWAP/9EMA confluence, closes back above both, is a pullback bar.
    Signal -> entry on bar i+1 if it trades through bars[i].h; stop = bars[i].l."""
    b = bars[i]; v, e = b["vwap"], b["e9"]
    if abs(v - e) / b["c"] > 0.01: return None
    top = max(v, e)
    if not (b["l"] <= top * 1.005 and b["c"] > top): return None
    if b["h"] >= ctx.leg_hi: return None                                   # must be a pullback bar
    if b["l"] >= top: return None                                          # the wick must actually touch/undercut
    return {"trig": b["h"], "stop": b["l"], "sig_i": i}

def levels_for(px):
    step = 1.0 if px >= 1.0 else 0.10
    return step

def det_B_scan(bars, ctx_hod, i):
    """returns level L if bar i is a break bar (prev close <= L < close) of a whole-dollar (or 10c sub-$1) or the
    stale session HOD; the caller then checks bars i+1..i+3 lows >= L and enters at i+4 open."""
    b, p = bars[i], bars[i - 1]
    out = []
    step = levels_for(b["c"])
    L = math.floor(b["c"] / step) * step
    if p["c"] <= L < b["c"] and L > 0: out.append(("dollar", L))
    if ctx_hod is not None and p["c"] <= ctx_hod < b["c"] and abs(ctx_hod - L) / b["c"] > 0.002: out.append(("hod", ctx_hod))
    return out

def det_C(bars, r, i):
    """after resumption index r: double bottom (two lows within 0.5%, >=3 bars apart) inside [r, i], and bar i
    breaks the intervening high. Returns (H, stop) or None."""
    lows = [(bars[k]["l"], k) for k in range(r, i)]
    if len(lows) < 5: return None
    # candidate second-low j: a local low; first-low m earlier
    best = None
    for j in range(r + 3, i):
        lj = bars[j]["l"]
        if lj > min(bars[k]["l"] for k in range(max(r, j - 2), min(i, j + 3))): continue
        for m in range(r, j - 2):
            lm = bars[m]["l"]
            if abs(lm - lj) / lm <= 0.005:
                H = max(bars[k]["h"] for k in range(m, j + 1))
                if H > max(lm, lj) * 1.01 and bars[i]["h"] > H and bars[i - 1]["h"] <= H:
                    best = (H, min(lm, lj), m, j)
    return best

# ---------------- exits ----------------
def sim(bars, i, entry, stop, mode, level, halt_set):
    """entry filled at bar i (already slipped). Walk k>i. Returns (pnl$, reason, k_exit)."""
    sh = POS / entry; rem = sh; pnl = 0.0; risk = entry - stop; armed = False; run_hi = entry; scaled = False
    if mode == "F": stop = entry * 0.93
    for k in range(i + 1, len(bars)):
        b = bars[k]
        if b["t"] >= FLAT: px = b["o"] * (1 - MKT); return pnl + rem * (px - entry), "flat1545", k
        if k in halt_set and b["o"] < stop: px = b["o"] * (1 - MKT); return pnl + rem * (px - entry), "haltgap", k
        if b["l"] <= stop: px = stop * (1 - MKT); return pnl + rem * (px - entry), "stop", k
        if mode == "KEV":
            if armed: stop = max(stop, bars[k - 1]["l"])
            if not armed and b["c"] >= entry + risk: armed = True
            if b["c"] < level: px = b["c"] * (1 - MKT); return pnl + rem * (px - entry), "failed_bo", k
            r = b["h"] - b["l"]; pv = [bars[j]["v"] for j in range(max(0, k - 10), k)]
            if r > 0 and (b["h"] - max(b["o"], b["c"])) / r >= 0.60 and pv and b["v"] >= 2 * st.mean(pv):
                px = b["c"] * (1 - MKT); return pnl + rem * (px - entry), "topping_tail", k
        elif mode in ("E3", "E4W"):
            if mode == "E3" and not scaled and b["h"] >= entry * 1.10:
                pnl += rem * 0.5 * (entry * 0.10); rem *= 0.5; scaled = True; stop = max(stop, entry); continue
            run_hi = max(run_hi, b["h"]); tr = 0.10 if mode == "E3" else 0.20
            if (mode == "E4W" or scaled) and b["c"] < run_hi * (1 - tr):
                px = b["c"] * (1 - MKT); return pnl + rem * (px - entry), "trail", k
    b = bars[-1]; px = b["c"] * (1 - MKT); return pnl + rem * (px - entry), "eod", len(bars) - 1

# ---------------- the run on one bar series ----------------
def run_series(bars, sec, pc, halt_idx, tag, res, quiet=None):
    """returns list of trade rows. bars must be enriched. Entries 09:30-15:30 ET, no overlap per name, <=3 per leg per detector."""
    ctx = Ctx(bars, sec, pc); rows = []; halt_set = set(halt_idx)
    busy_until = -1; per_leg = {}
    pendA = None; pendB = []; hod_stale = None; last_hi_leg = None
    n = len(bars)
    for i in range(1, n):
        ctx.step(i); b = bars[i]
        if b["t"] < RTH0 - 1800: continue
        mover = (ctx.gain(b["c"]) is not None and ctx.gain(b["c"]) >= 0.20)
        fires = []
        # ---- A: pending trigger from prior signal bar
        if pendA is not None:
            if b["h"] > pendA["trig"] and pendA["sig_i"] == i - 1:
                fires.append(("A", pendA["trig"], pendA["stop"], pendA["trig"]))
            pendA = None
        sig = det_A(bars, ctx, i)
        if sig: pendA = sig
        # ---- B: level breaks -> hold three -> enter 4th open
        newB = []
        for kind, L in det_B_scan(bars, hod_stale, i) if i >= 1 else []:
            newB.append({"L": L, "brk": i, "kind": kind})
        keep = []
        for pb in pendB:
            j = i - pb["brk"]
            if j <= 3:
                if b["l"] >= pb["L"]: keep.append(pb)
            elif j == 4:
                fires.append(("B", b["o"], pb["L"], pb["L"]))
        pendB = keep + newB
        # stale HOD = session high older than 5 min and above price
        hod_stale = ctx.sess_hi if (ctx.sess_hi_t is not None and b["t"] - ctx.sess_hi_t > 300 and ctx.sess_hi > b["c"]) else None
        # ---- C: after resumption within 15 min
        for r in halt_idx:
            if r < i and b["t"] - bars[r]["t"] <= 900:
                d = det_C(bars, r, i)
                if d: fires.append(("C", d[0], d[1], d[0]))
        for det, trig, stop, level in fires:
            if b["t"] < busy_until: continue
            g = gates(ctx, i, b["c"], mover)
            key = (det, ctx.leg)
            if g is None and per_leg.get(key, 0) >= 3: g = "leg_ration"
            if quiet is not None and quiet is False: g = g or "not_quiet"
            entry = trig * (1 + SLIP) if det != "B" else b["o"] * (1 + SLIP)
            if entry <= stop: continue
            row = {"tag": tag, "res": res, "det": det, "t": b["t"], "et": et(b["t"]), "entry": round(entry, 4), "stop": round(stop, 4),
                   "stop_pct": round((entry - stop) / entry * 100, 2), "gate": g, "leg": ctx.leg, "gain_at": round(ctx.gain(b["c"]) * 100, 1) if pc else None}
            if g is None:
                per_leg[key] = per_leg.get(key, 0) + 1
                for mode in ("KEV", "E3", "E4W", "F"):
                    p, why, k = sim(bars, i, entry, stop, mode, level, halt_set)
                    row[mode] = round(p, 2); row[mode + "_why"] = why; row[mode + "_bars"] = k - i
                    if mode == "KEV": busy_until = bars[k]["t"]
                row["ff3"] = row["KEV_why"] == "stop" and row["KEV_bars"] <= 3
                row["ff30s"] = row["KEV_why"] == "stop" and row["KEV_bars"] * sec <= 30
            rows.append(row)
    return rows

# ---------------- cohorts ----------------
def tick_cohort():
    nd = set()
    for f in os.listdir(TK):
        if f.endswith("_110000_200000.json.gz") or f.endswith("_132500_200000.json.gz"):
            d, s = f.split("_")[0], f.split("_")[1]; nd.add((d, s))
    return sorted(nd)

def crown_roster():
    return {"2026-08-12": ["BOXL", "OFAL", "RMCF", "BAOS", "VBIO", "DOGZ", "BIVI", "BQ", "HXHX", "SCKT", "WCT", "BANL", "ZYBT"],
            "2026-08-13": ["IVDA", "FGI", "OFAL", "YXT", "DFSC", "BNRG", "XHG", "PSQH", "HCTI", "INHD"],
            "2026-08-14": ["WETO", "LBGJ", "CGTL", "HHS", "ONFO", "MF", "AKAN", "HAO", "AEHL", "BANL", "LFS", "GIPR", "STKH", "SXTC"]}

def run_ticks(date, sym, quiet_gate=False):
    tr = load_ticks(date, sym)
    if not tr or len(tr) < 200: return [], None
    pc = prev_close(date, sym)
    pv0, v0, calm = premarket_seed(date, sym, tr[0][0])
    out = []
    for sec in (10, 5):
        bars = enrich(bars_from_ticks(tr, sec), pv0, v0)
        if calm is None: calm = calm_from_bars(bars)
        q = None if not quiet_gate else (calm is not None and calm <= CALM_X)
        out += run_series(bars, sec, pc, halts(bars), f"TICK", f"{sec}s", quiet=q)
    for r in out: r.update({"date": date, "sym": sym, "calm": None if calm is None else round(calm, 1), "pc": pc})
    return out, calm

def run_cap(date, sym):
    c1 = load_cap1s(date, sym)
    if not c1: return []
    pc = prev_close(date, sym); out = []
    for sec in (10, 5):
        bars = enrich(rebar(c1, sec))
        out += run_series(bars, sec, pc, halts(bars), "CAP1S", f"{sec}s")
    for r in out: r.update({"date": date, "sym": sym, "pc": pc})
    return out

def run_cache10(date, sym):
    c = load_cache10(date, sym)
    if not c or len(c) < 100: return [], None
    pc = prev_close(date, sym); bars = enrich(c); calm = calm_from_bars(bars)
    rows = run_series(bars, 10, pc, halts(bars), "CACHE10", "10s")
    for r in rows: r.update({"date": date, "sym": sym, "pc": pc, "calm": None if calm is None else round(calm, 1)})
    return rows, calm

# ---------------- reporting ----------------
def summ(rows, mode):
    ok = [r for r in rows if r["gate"] is None]
    if not ok: return {"N": 0}
    p = [r[mode] for r in ok]
    return {"N": len(ok), "sum": round(sum(p), 2), "mean": round(st.mean(p), 2), "med": round(st.median(p), 2),
            "win": round(sum(1 for x in p if x > 0) / len(p) * 100), "HR250": sum(1 for x in p if x >= 250),
            "worst": round(min(p), 2), "best": round(max(p), 2),
            "ff3": round(sum(1 for r in ok if r["ff3"]) / len(ok) * 100), "ff30s": round(sum(1 for r in ok if r["ff30s"]) / len(ok) * 100),
            "stop_pct": round(st.median(r["stop_pct"] for r in ok), 2)}

def match_twin(rows):
    """pair 5s fires with 10s fires: same name-day, detector, |dt|<=60s. Returns pairs list."""
    by = {}
    for r in rows:
        if r["gate"] is None: by.setdefault((r["date"], r["sym"], r["det"], r["res"]), []).append(r)
    pairs = []
    for (d, s, det, res), l10 in by.items():
        if res != "10s": continue
        l5 = by.get((d, s, det, "5s"), [])
        for a in l10:
            c = [b for b in l5 if abs(b["t"] - a["t"]) <= 60]
            if c:
                b = min(c, key=lambda x: abs(x["t"] - a["t"]))
                pairs.append({"date": d, "sym": s, "det": det, "t10": a["et"], "t5": b["et"], "dt": b["t"] - a["t"], "e10": a["entry"], "e5": b["entry"],
                              "dpx": round((b["entry"] / a["entry"] - 1) * 100, 2), "kev10": a["KEV"], "kev5": b["KEV"], "f10": a["F"], "f5": b["F"]})
    return pairs

if __name__ == "__main__":
    print("run", dt.datetime.now(), flush=True)
    allrows = []; calms = {}
    coh = tick_cohort(); print("tick cohort", len(coh))
    for d, s in coh:
        rows, calm = run_ticks(d, s, quiet_gate=False); allrows += rows; calms[(d, s)] = calm
    print("tick rows", len(allrows), flush=True)
    # quiet-tape variant of A: re-run rows filtered by calm at report time (gate is a name-day stamp; identical fires)
    caprows = []
    for d, syms in crown_roster().items():
        for s in syms: caprows += run_cap(d, s)
    print("cap rows", len(caprows), flush=True)
    c10 = []
    for f in sorted(os.listdir(B10)):
        d, s = f[:10], f[11:-5]
        rows, calm = run_cache10(d, s); c10 += rows
        if (d, s) not in calms or calms[(d, s)] is None: calms[(d, s)] = calm
    print("cache10 rows", len(c10), flush=True)
    json.dump({"tick": allrows, "cap": caprows, "cache10": c10, "calms": {f"{d}|{s}": v for (d, s), v in calms.items()},
               "pairs": match_twin(allrows), "cap_pairs": match_twin(caprows)},
              open(KT + "/kev_fastchart_replay_20260816_rows.json", "w"))
    print("saved")
