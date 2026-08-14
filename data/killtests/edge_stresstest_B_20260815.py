#!/usr/bin/env python3
"""EDGE STRESS-TEST B (8/15 follow-up, PRE-REGISTERED FRESH) — limit-in execution,
survivors-only portfolio, calibrated-v2 cohort.
Reuses edge_stresstest_20260815.py engines UNCHANGED (import): same detectors,
same sim, same 419-file cache, same laws, same 36-day denominator.

TEST A: limit-in entries — bid AT signal price; fill only if a subsequent 10s bar
  (within 180s) trades low <= bid - $0.01 (trade-through, conservative); else MISS.
  Exits unchanged (market exits -0.5%, resting tiers exact). H2 halt, H3 dedup,
  H4 capacity applied identically. Fill rate per entry type reported.
TEST B: grinder + flat_top only, under (i) market-chase and (ii) limit-in.
TEST C: calibrated v2 (C1 anchor within 2% of VWAP, C2 confirm <=120s from push,
  C3 300s per-name cooldown, C4 push = 5-min high, C5 stop >= 0.5%), in-window,
  both execution models.
Bar (A and B(ii)): mean AND median > +$50/day, green >= 55%, both halves positive,
worst > -$300.
"""
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("E", HERE + "/edge_stresstest_20260815.py")
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)

MKT_SLIP = 0.005

def gen_signals():
    import glob
    # Pre-registered denominator: 36 dates 2026-06-25..2026-08-14. The live cache
    # grew to 448 files/39 dates during the evening ferry; restrict to the window.
    # 421 files fall in-window (2 more than tonight's 419 — ferry added 2 in-window
    # files after the committed run; exact 419 manifest not recoverable). Disclosed.
    files = sorted(f for f in glob.glob(E.BARS_DIR + "/*.json")
                   if "2026-06-25" <= os.path.basename(f)[:10] <= "2026-08-14")
    dates = sorted({os.path.basename(f)[:10] for f in files})
    signals = []
    for f in files:
        sym, date, bars = E.load(f)
        bars = E.rth(bars)
        if len(bars) < 60: continue
        emas = E.ema_series([b["c"] for b in bars], 90)
        gaps = E.find_gaps(bars)
        E.DAYS[(sym, date)] = (bars, emas, gaps)
        for det, fn, win in (("v2", E.det_v2, True), ("flat_top", E.det_flat_top, True),
                             ("vwap", E.det_vwap, True), ("grinder", E.det_grinder, False)):
            for t in fn(bars, emas, gaps):
                hh = E.hhmm_b(bars[t["i"]])
                if win and not ("13:30:00" <= hh <= "14:30:00"): continue
                signals.append({"sym": sym, "date": date, "det": det, "i": t["i"],
                                "t": hh, "key": date + "T" + hh,
                                "entry": t["entry"], "stop": t["stop"]})
        # calibrated v2 (Test C) on same day data
        for t in det_v2_cal(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            if not ("13:30:00" <= hh <= "14:30:00"): continue
            signals.append({"sym": sym, "date": date, "det": "v2cal", "i": t["i"],
                            "t": hh, "key": date + "T" + hh,
                            "entry": t["entry"], "stop": t["stop"]})
    signals.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    return len(files), dates, signals

# ---- TEST C detector: v2 with C1-C5 calibration gates ----
def det_v2_cal(bars, emas, gaps):
    trades = []; n = len(bars)
    cpv = 0.0; cv = 0.0; vwaps = []
    for b in bars:
        cpv += b["c"] * b["v"]; cv += b["v"]
        vwaps.append(cpv / cv if cv > 0 else b["c"])
    m3 = E.agg3min(bars)
    open_until = -1; cooldown_until = -1
    state = "seek"; flush_low = None; flush_i = None
    for i in range(1, n):
        if i <= open_until: continue
        b = bars[i]
        if state == "seek":
            if E.secs(b) < cooldown_until: continue  # C3: 300s per-name cooldown
            # C4: push = 5-min high (30 bars)
            push_hi = max(x["h"] for x in bars[max(0, i - 30):i + 1])
            if push_hi > 0 and (push_hi - b["l"]) / push_hi >= 0.03:
                vw = vwaps[i]
                anchors = [vw]
                done = [x for x in m3 if x["end_t"] < b["t"]]
                for k in range(len(done) - 3):
                    w = done[k:k + 4]
                    hi = max(x["h"] for x in w); lo = min(x["l"] for x in w)
                    if lo > 0 and (hi - lo) / lo <= 0.12: anchors.append(hi)
                # C1: anchor must be within 2% of VWAP
                anchors = [a for a in anchors if a > 0 and vw > 0 and abs(a - vw) / vw <= 0.02]
                if any(abs(b["l"] - a) / a <= 0.02 for a in anchors):
                    state = "flushed"; flush_low = b["l"]; flush_i = i
        elif state == "flushed":
            if b["l"] < flush_low: flush_low = b["l"]
            if i - flush_i > 12:  # C2: confirm <= 120s from push
                state = "seek"; continue
            p = bars[i - 1]
            if b["l"] > p["l"] and b["c"] > p["h"]:
                entry = b["c"]; stop = flush_low
                # C5: stop >= 0.5%
                if stop < entry and (entry - stop) / entry >= 0.005:
                    pnl, ex, xi = E.base_sim(bars, emas, gaps, i, entry, stop, "v2")
                    trades.append({"i": i, "entry": entry, "stop": stop})
                    open_until = xi
                    cooldown_until = E.secs(b) + 300
                state = "seek"
    return trades

# ---- limit-in execution ----
def limit_fill_bar(bars, i, sig_px):
    """First bar after i, within 180s of signal bar, whose low trades <= bid-$0.01."""
    s0 = E.secs(bars[i])
    for j in range(i + 1, len(bars)):
        if E.secs(bars[j]) - s0 > 180: return None
        if bars[j]["l"] <= sig_px - 0.01: return j
    return None

def sim_limit(sig, halt_rule):
    """Returns (filled, pnl, exit, xi, fill_bar). Entry fill = sig price exactly."""
    bars, emas, gaps = E.DAYS[(sig["sym"], sig["date"])]
    j = limit_fill_bar(bars, sig["i"], sig["entry"])
    if j is None: return False, 0.0, "miss", None, None
    entry_px = sig["entry"]; stop = sig["stop"]
    # fill-bar stop check (stop-first, tie against the trade): the bar that filled us
    # may also have traded through the stop.
    if bars[j]["l"] <= stop:
        sh = E.POS / entry_px
        pnl = sh * (stop * (1 - MKT_SLIP) - entry_px)
        return True, pnl, f"stop@{E.hhmm_b(bars[j])}(fillbar)", j, j
    pnl, ex, xi = E.sim(bars, emas, gaps, j, entry_px, stop,
                        breakeven=(sig["det"] == "grinder"),
                        flatten_1959=(sig["det"] == "grinder"),
                        entry_slip=0.0, mkt_slip=MKT_SLIP, halt_rule=halt_rule)
    return True, pnl, ex, xi, j

def sim_chase(sig, halt_rule):
    bars, emas, gaps = E.DAYS[(sig["sym"], sig["date"])]
    pnl, ex, xi = E.sim(bars, emas, gaps, sig["i"], sig["entry"], sig["stop"],
                        breakeven=(sig["det"] == "grinder"),
                        flatten_1959=(sig["det"] == "grinder"),
                        entry_slip=0.01, mkt_slip=MKT_SLIP, halt_rule=halt_rule)
    return True, pnl, ex, xi, sig["i"]

# ---- pipeline: given signals + execution model, run H1..H4 + H5 ----
def tsec(hh): return int(hh[:2]) * 3600 + int(hh[3:5]) * 60 + int(hh[6:8])

def pipeline(signals, dates, exec_fn, label):
    dets = sorted({s["det"] for s in signals})
    def daily_of(tr):
        d = {dt: 0.0 for dt in dates}
        for x in tr: d[x["date"]] += x["pnl"]
        return d
    def rep(name, tr):
        d = daily_of(tr); vals = list(d.values()); tot = sum(vals)
        print(f"  {name}: N={len(tr)} total=${tot:+.2f} dailymean=${tot/len(vals):+.2f} worst=${min(vals):+.2f}")
        return d, tot
    print(f"\n== {label} ==")
    # H1 (frictions under this exec model), misses counted per det
    h1 = []; misses = {d: 0 for d in dets}; placed = {d: 0 for d in dets}
    for s in signals:
        placed[s["det"]] += 1
        filled, pnl, ex, xi, fb = exec_fn(s, False)
        if not filled:
            misses[s["det"]] += 1; continue
        bars, _, _ = E.DAYS[(s["sym"], s["date"])]
        ft = E.hhmm_b(bars[fb])
        h1.append({**s, "pnl": pnl, "exit": ex, "xi": xi, "fill_t": ft,
                   "fill_key": s["date"] + "T" + ft})
    rep("H1 frictions", h1)
    fillrates = {d: (placed[d] - misses[d], placed[d]) for d in dets}
    print("  fill rates:", {d: f"{f}/{p} = {100*f/p:.0f}%" if p else "n/a" for d, (f, p) in fillrates.items()})
    # H2 halt rule
    h2 = []; nhalt = 0
    for s in signals:
        filled, pnl, ex, xi, fb = exec_fn(s, True)
        if not filled: continue
        if ex.startswith("haltgap"): nhalt += 1
        bars, _, _ = E.DAYS[(s["sym"], s["date"])]
        ft = E.hhmm_b(bars[fb])
        h2.append({**s, "pnl": pnl, "exit": ex, "xi": xi, "fill_t": ft,
                   "fill_key": s["date"] + "T" + ft})
    rep("H2 halt-excl", h2)
    print(f"  halt-gap forced exits: {nhalt}")
    # H3 dedup: same name <=5 min, first wins (keyed on fill time — the trade time)
    h2.sort(key=lambda x: (x["fill_key"], x["det"]))
    h3 = []; last_kept = {}; ndd = 0
    for s in h2:
        k = (s["sym"], s["date"]); ssec = tsec(s["fill_t"])
        ls = last_kept.get(k)
        if ls is not None and ssec - ls <= 300: ndd += 1; continue
        last_kept[k] = ssec; h3.append(s)
    rep("H3 dedup", h3)
    print(f"  deduped dropped: {ndd}")
    # H4 capacity: max 2 concurrent, chronological on fill time; tie = slot occupied
    h4 = []; nskip = 0; open_pos = []
    for s in h3:
        bars, _, _ = E.DAYS[(s["sym"], s["date"])]
        open_pos = [p for p in open_pos if p >= s["fill_key"]]
        if len(open_pos) >= 2: nskip += 1; continue
        open_pos.append(s["date"] + "T" + E.hhmm_b(bars[min(s["xi"], len(bars) - 1)]))
        h4.append(s)
    d4, tot4 = rep("H4 capacity", h4)
    print(f"  slot-skipped: {nskip}")
    # H5
    vals = [d4[k] for k in dates]; n = len(vals)
    sv = sorted(vals)
    median = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
    mid = dates[n // 2]
    half1 = sum(d4[k] for k in dates if k < mid); half2 = sum(d4[k] for k in dates if k >= mid)
    n1 = sum(1 for k in dates if k < mid); n2 = n - n1
    green = sum(1 for v in vals if v > 0)
    best = max(dates, key=lambda k: d4[k])
    contrib = {det: (sum(1 for x in h4 if x["det"] == det),
                     sum(x["pnl"] for x in h4 if x["det"] == det)) for det in dets}
    print(f"  H5: mean=${sum(vals)/n:+.2f} median=${median:+.2f} green={green}/{n}={100*green/n:.0f}% "
          f"half1=${half1/n1:+.2f}/d half2=${half2/n2:+.2f}/d worst=${min(vals):+.2f} ({min(d4,key=d4.get)}) "
          f"best {best} ${d4[best]:+.2f} exbest=${(sum(vals)-d4[best])/(n-1):+.2f}")
    print("  per-entry:", {k: f"N={a} ${b:+.2f}" for k, (a, b) in contrib.items()})
    print("  daily:", {k: round(v, 2) for k, v in d4.items()})
    verdict = {
        "mean": (sum(vals) / n, sum(vals) / n > 50),
        "median": (median, median > 50),
        "green_pct": (100 * green / n, green / n >= 0.55),
        "halves": ((half1 / n1, half2 / n2), half1 > 0 and half2 > 0),
        "worst": (min(vals), min(vals) > -300)}
    print("  VERDICT:", {k: ("PASS" if p else "FAIL") for k, (v, p) in verdict.items()},
          "OVERALL", "PASS" if all(p for _, p in verdict.values()) else
          f"FAIL {sum(1 for _,p in verdict.values() if p)}/5")
    return {"h4": h4, "daily": d4, "fillrates": fillrates, "verdict": verdict,
            "h5": {"mean": sum(vals)/n, "median": median, "green": green, "n": n,
                   "half1d": half1/n1, "half2d": half2/n2, "worst": min(vals),
                   "contrib": contrib, "nhalt": nhalt, "ndd": ndd, "nskip": nskip,
                   "misses": misses, "placed": placed}}

def main():
    nfiles, dates, allsig = gen_signals()
    print(f"FILES: {nfiles}  DATES: {len(dates)}  {dates[0]}..{dates[-1]}")
    base = [s for s in allsig if s["det"] != "v2cal"]
    cal = [s for s in allsig if s["det"] == "v2cal"]
    print("in-scope signals (4 lanes):", len(base),
          {d: sum(1 for s in base if s["det"] == d) for d in ("v2", "flat_top", "vwap", "grinder")})
    print("calibrated v2 signals:", len(cal))

    resA = pipeline(base, dates, sim_limit, "TEST A — all 4 lanes, LIMIT-IN")
    surv = [s for s in base if s["det"] in ("flat_top", "grinder")]
    resBi = pipeline(surv, dates, sim_chase, "TEST B(i) — survivors, MARKET-CHASE")
    resBii = pipeline(surv, dates, sim_limit, "TEST B(ii) — survivors, LIMIT-IN")

    # TEST C: calibrated cohort, gross + both friction models (per-trade economics)
    print("\n== TEST C — CALIBRATED v2 (C1-C5), in-window ==")
    for name, fn, kw in (("H0 gross", None, {}), ("market-chase", sim_chase, {}), ("limit-in", sim_limit, {})):
        pnls = []; miss = 0
        for s in cal:
            if fn is None:
                bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
                pnl, ex, xi = E.sim(bars, emas, gaps, s["i"], s["entry"], s["stop"],
                                    breakeven=False, flatten_1959=False)
                pnls.append(pnl)
            else:
                filled, pnl, ex, xi, fb = fn(s, True)
                if not filled: miss += 1; continue
                pnls.append(pnl)
        n = len(pnls)
        print(f"  {name}: N={n} total=${sum(pnls):+.2f} per-trade mean=${(sum(pnls)/n if n else 0):+.2f}"
              + (f"  (missed {miss}, fill {100*n/(n+miss):.0f}%)" if fn is sim_limit else ""))

    json.dump({"A": {"daily": resA["daily"], "h5": resA["h5"]},
               "Bi": {"daily": resBi["daily"], "h5": resBi["h5"]},
               "Bii": {"daily": resBii["daily"], "h5": resBii["h5"]}},
              open(HERE + "/stress_B_out.json", "w"), indent=1, default=str)

if __name__ == "__main__":
    main()
