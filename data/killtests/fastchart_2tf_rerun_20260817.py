#!/usr/bin/env python3
"""TWO-TIMEFRAME FAST-CHART RE-RUN (8/17) — the corrected Kev logic.

The 8/16 replay (kev_fastchart_replay_20260816) collapsed CONTEXT and ENTRY onto ONE chart:
`front_side = close>vwap AND e9>e20` was read on the SAME fast bars the detector fires on.
On a 10s pullback deep enough to test VWAP+9MA (the exact bar Kev buys) the fast 9EMA has usually
already crossed 20EMA down -> the "front side" gate REFUSED Kev's entry by construction (§9 caveat).

FIX (what Kev actually does): read FRONT SIDE on the SLOW chart (1-min, and a 3-min variant) and
ENTER on the FAST chart (10s / 5s). Two timeframes. The fast-chart front-side gate is removed;
every other gate (mover, room, topping-cluster, hours, leg-ration) and every detector/exit is unchanged.

Variants per (detector, resolution): FAST (orig, control) / 1MIN context / 3MIN context.
Reuses detectors, exits, Ctx, enrich, cohorts from the 8/16 module verbatim.
Analysis only. Nothing ships.
"""
import os, json, statistics as st, datetime as dt, importlib.util
ROOT = "/Users/marcosolivera/Desktop/Marcos-Trading-Bot"; KT = ROOT + "/data/killtests"
spec = importlib.util.spec_from_file_location("R", KT + "/kev_fastchart_replay_20260816.py")
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
B10 = R.B10; RTH0 = R.RTH0; CUT = R.CUT; SLIP = R.SLIP

# ---------------- slow-chart front-side context ----------------
class SlowFront:
    """Build a slow (60s or 180s) aggregate from the fast bars, enrich it with the SAME premarket VWAP
    seed, and expose front_side(t) = state of the last CLOSED slow bar as-of wall-time t.
    front_side = e9 > e20 (uptrend intact on the slow chart) AND close > vwap."""
    def __init__(self, fast_bars, slow_sec, pv0, v0):
        slow = R.enrich(R.rebar(fast_bars, slow_sec), pv0, v0)
        self.sec = slow_sec
        self.close_t = [b["t"] + slow_sec for b in slow]     # bar covering [t, t+sec) closes at t+sec
        self.fs = [(b["e9"] > b["e20"] and b["c"] > b["vwap"]) for b in slow]
        import bisect; self._bisect = bisect
    def front_side(self, t):
        # last slow bar that has CLOSED at or before t
        j = self._bisect.bisect_right(self.close_t, t) - 1
        if j < 0: return False        # no closed slow bar yet -> not confirmed front side
        return self.fs[j]

def gates2(ctx, i, px, mover, slow):
    """same gate stack as the module EXCEPT front-side is read on the slow chart (or None = fast-chart, orig)."""
    b = ctx.b[i]
    if not (RTH0 <= b["t"] < CUT): return "hours"
    if not mover: return "not_mover"
    fs = ctx.front_side(i) if slow is None else slow.front_side(b["t"])
    if not fs: return "backside"
    if not ctx.room_ok(i, px): return "no_room"
    if ctx.topping_cluster(i): return "topping_cluster"
    return None

def run_series2(bars, sec, pc, halt_idx, tag, res, slow, ctxlabel):
    """clone of R.run_series but gate uses slow-chart front-side (slow=None -> original fast-chart)."""
    ctx = R.Ctx(bars, sec, pc); rows = []; halt_set = set(halt_idx)
    busy_until = -1; per_leg = {}; pendA = None; pendB = []; hod_stale = None
    for i in range(1, len(bars)):
        ctx.step(i); b = bars[i]
        if b["t"] < RTH0 - 1800: continue
        mover = (ctx.gain(b["c"]) is not None and ctx.gain(b["c"]) >= 0.20)
        fires = []
        if pendA is not None:
            if b["h"] > pendA["trig"] and pendA["sig_i"] == i - 1:
                fires.append(("A", pendA["trig"], pendA["stop"], pendA["trig"]))
            pendA = None
        sig = R.det_A(bars, ctx, i)
        if sig: pendA = sig
        newB = [{"L": L, "brk": i, "kind": kind} for kind, L in R.det_B_scan(bars, hod_stale, i)]
        keep = []
        for pb in pendB:
            j = i - pb["brk"]
            if j <= 3:
                if b["l"] >= pb["L"]: keep.append(pb)
            elif j == 4:
                fires.append(("B", b["o"], pb["L"], pb["L"]))
        pendB = keep + newB
        hod_stale = ctx.sess_hi if (ctx.sess_hi_t is not None and b["t"] - ctx.sess_hi_t > 300 and ctx.sess_hi > b["c"]) else None
        for r in halt_idx:
            if r < i and b["t"] - bars[r]["t"] <= 900:
                d = R.det_C(bars, r, i)
                if d: fires.append(("C", d[0], d[1], d[0]))
        for det, trig, stop, level in fires:
            if b["t"] < busy_until: continue
            g = gates2(ctx, i, b["c"], mover, slow)
            key = (det, ctx.leg)
            if g is None and per_leg.get(key, 0) >= 3: g = "leg_ration"
            entry = trig * (1 + SLIP) if det != "B" else b["o"] * (1 + SLIP)
            if entry <= stop: continue
            row = {"tag": tag, "res": res, "ctx": ctxlabel, "det": det, "t": b["t"], "et": R.et(b["t"]),
                   "entry": round(entry, 4), "stop": round(stop, 4),
                   "stop_pct": round((entry - stop) / entry * 100, 2), "gate": g, "leg": ctx.leg,
                   "gain_at": round(ctx.gain(b["c"]) * 100, 1) if pc else None}
            if g is None:
                per_leg[key] = per_leg.get(key, 0) + 1
                for mode in ("KEV", "E3", "E4W", "F"):
                    p, why, k = R.sim(bars, i, entry, stop, mode, level, halt_set)
                    row[mode] = round(p, 2); row[mode + "_why"] = why; row[mode + "_bars"] = k - i
                    if mode == "KEV": busy_until = bars[k]["t"]
                row["ff3"] = row["KEV_why"] == "stop" and row["KEV_bars"] <= 3
                row["ff30s"] = row["KEV_why"] == "stop" and row["KEV_bars"] * sec <= 30
            rows.append(row)
    return rows

# ---------------- per name-day driver: all three contexts, both resolutions ----------------
def run_ticks_2tf(date, sym):
    tr = R.load_ticks(date, sym)
    if not tr or len(tr) < 200: return []
    pc = R.prev_close(date, sym)
    pv0, v0, calm = R.premarket_seed(date, sym, tr[0][0])
    out = []
    for sec in (10, 5):
        bars = R.enrich(R.bars_from_ticks(tr, sec), pv0, v0)
        h = R.halts(bars)
        slow1 = SlowFront(bars, 60, pv0, v0)
        slow3 = SlowFront(bars, 180, pv0, v0)
        out += run_series2(bars, sec, pc, h, "TICK", f"{sec}s", None,  "FAST")
        out += run_series2(bars, sec, pc, h, "TICK", f"{sec}s", slow1, "1MIN")
        out += run_series2(bars, sec, pc, h, "TICK", f"{sec}s", slow3, "3MIN")
    for r in out: r.update({"date": date, "sym": sym, "pc": pc, "calm": None if calm is None else round(calm, 1)})
    return out

def run_cache10_2tf(date, sym):
    c = R.load_cache10(date, sym)
    if not c or len(c) < 100: return []
    pc = R.prev_close(date, sym); bars = R.enrich(c); h = R.halts(bars)
    slow1 = SlowFront(bars, 60, 0.0, 0.0)
    slow3 = SlowFront(bars, 180, 0.0, 0.0)
    out = []
    out += run_series2(bars, 10, pc, h, "CACHE10", "10s", None,  "FAST")
    out += run_series2(bars, 10, pc, h, "CACHE10", "10s", slow1, "1MIN")
    out += run_series2(bars, 10, pc, h, "CACHE10", "10s", slow3, "3MIN")
    for r in out: r.update({"date": date, "sym": sym, "pc": pc})
    return out

# ---------------- reporting ----------------
def summ(rows):
    ok = [r for r in rows if r["gate"] is None]
    if not ok: return {"N": 0}
    d = {"N": len(ok)}
    for m in ("KEV", "E3", "E4W", "F"):
        p = [r[m] for r in ok]
        d[m + "_sum"] = round(sum(p), 2); d[m + "_mean"] = round(st.mean(p), 2); d[m + "_med"] = round(st.median(p), 2)
    kev = [r["KEV"] for r in ok]
    d["win"] = round(sum(1 for x in kev if x > 0) / len(kev) * 100)
    d["HR250"] = sum(1 for x in kev if x >= 250)
    d["worst"] = round(min(kev), 2); d["best"] = round(max(kev), 2)
    d["ff3"] = round(sum(1 for r in ok if r["ff3"]) / len(ok) * 100)
    d["ff30s"] = round(sum(1 for r in ok if r["ff30s"]) / len(ok) * 100)
    d["stop_pct"] = round(st.median(r["stop_pct"] for r in ok), 2)
    return d

def day_level(rows):
    """per name-day KEV sums -> mean/median/green%/worst + first-half/second-half split by date order."""
    ok = [r for r in rows if r["gate"] is None]
    if not ok: return {}
    days = {}
    for r in ok: days.setdefault((r["date"], r["sym"]), 0.0)
    for r in ok: days[(r["date"], r["sym"])] += r["KEV"]
    vals = list(days.values())
    bydate = sorted(days.items(), key=lambda kv: kv[0][0])
    half = len(bydate) // 2
    h1 = [v for _, v in bydate[:half]]; h2 = [v for _, v in bydate[half:]]
    return {"days": len(vals), "mean": round(st.mean(vals), 2), "med": round(st.median(vals), 2),
            "green": round(sum(1 for v in vals if v > 0) / len(vals) * 100),
            "worst": round(min(vals), 2), "best": round(max(vals), 2),
            "h1_sum": round(sum(h1), 2), "h1_days": len(h1), "h1_green": round(sum(1 for v in h1 if v > 0) / max(1, len(h1)) * 100),
            "h2_sum": round(sum(h2), 2), "h2_days": len(h2), "h2_green": round(sum(1 for v in h2 if v > 0) / max(1, len(h2)) * 100)}

def sel(rows, det=None, res=None, ctx=None):
    return [r for r in rows if (det is None or r["det"] == det) and (res is None or r["res"] == res) and (ctx is None or r["ctx"] == ctx)]

if __name__ == "__main__":
    print("run", dt.datetime.now(), flush=True)
    tick = []
    coh = R.tick_cohort(); print("tick cohort", len(coh), flush=True)
    for n, (d, s) in enumerate(coh):
        tick += run_ticks_2tf(d, s)
        if n % 40 == 0: print(" tick", n, len(tick), flush=True)
    print("tick rows", len(tick), flush=True)
    cache = []
    files = sorted(os.listdir(B10))
    for n, f in enumerate(files):
        d, s = f[:10], f[11:-5]
        cache += run_cache10_2tf(d, s)
        if n % 120 == 0: print(" cache", n, len(cache), flush=True)
    print("cache rows", len(cache), flush=True)
    json.dump({"tick": tick, "cache": cache}, open(KT + "/fastchart_2tf_rerun_20260817_rows.json", "w"))

    # build the report tables
    L = []
    def emit(s): L.append(s); print(s)
    for cohort, rows, resll in (("SIP TICK TWIN (197 nd)", tick, ("10s", "5s")), ("CACHE10 @ SCALE (719 nd)", cache, ("10s",))):
        emit(f"\n===== {cohort} =====")
        for det in ("A", "B", "C"):
            for res in resll:
                emit(f"\n--- det {det} @ {res} ---")
                emit(f"{'ctx':6} {'N':>4} {'KEV_sum':>9} {'KEV_mn':>7} {'E3_mn':>7} {'E4W_mn':>7} {'F_sum':>9} {'F_mn':>7} {'win':>4} {'HR':>3} {'ff30s':>5} {'stop%':>5} {'worst':>7} {'best':>7}")
                for ctx in ("FAST", "1MIN", "3MIN"):
                    r = sel(rows, det, res, ctx); su = summ(r)
                    if su["N"] == 0: emit(f"{ctx:6} {0:>4}"); continue
                    emit(f"{ctx:6} {su['N']:>4} {su['KEV_sum']:>9} {su['KEV_mean']:>7} {su['E3_mean']:>7} {su['E4W_mean']:>7} {su['F_sum']:>9} {su['F_mean']:>7} {su['win']:>4} {su['HR250']:>3} {su['ff30s']:>5} {su['stop_pct']:>5} {su['worst']:>7} {su['best']:>7}")
                    dl = day_level(r)
                    if dl: emit(f"       day: n={dl['days']} mean={dl['mean']} med={dl['med']} green={dl['green']}% worst={dl['worst']} | H1 sum={dl['h1_sum']}({dl['h1_days']}d {dl['h1_green']}%g) H2 sum={dl['h2_sum']}({dl['h2_days']}d {dl['h2_green']}%g)")
        # detector-agnostic totals per ctx
        emit(f"\n--- ALL DETECTORS combined, {cohort} ---")
        for res in resll:
            for ctx in ("FAST", "1MIN", "3MIN"):
                su = summ(sel(rows, None, res, ctx))
                if su.get("N"): emit(f"  {res} {ctx:5} N={su['N']} KEV_sum={su['KEV_sum']} KEV_mn={su['KEV_mean']} E3={su['E3_mean']} E4W={su['E4W_mean']} F_sum={su['F_sum']} win={su['win']}%")
    open(KT + "/fastchart_2tf_rerun_20260817_tables.txt", "w").write("\n".join(L))
    print("\nsaved rows + tables")
