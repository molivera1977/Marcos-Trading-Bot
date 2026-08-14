#!/usr/bin/env python3
"""EDGE STRESS-TEST D (SIZING TEST, PRE-REGISTERED FRESH) — run 8/14 eve, filed 20260815.
Imports edge_stresstest_C_20260815.py (-> B -> engine of record). Detectors, sim,
limit mechanics, H2-H4 machinery UNCHANGED. Same 36-date window, same cache, same bar
(bar does NOT scale with size): mean AND median > +$50/day, green >= 55%,
both halves positive, worst > -$300.

TEST G — the F configuration (grinder chased post-11:00 + flat_top limit-in
  9:30-10:30 + vwap band-pass chased in-window) at $1,000/position, 2 slots, with
  an honest LIQUIDITY GUARD on the signal bar's dollar volume (close*volume):
    >= $20,000 -> $1,000 clip (<=5% of the 10s bar's traded dollars)
    >= $10,000 -> $500 half clip
    <  $10,000 -> skipped-for-size (counted per lane)
  Slippage scaling: chase entry slip -1% at $500, -1.5% at $1,000.
  [CALIBRATION UNKNOWN - needs live $1k fills to verify] — the -1.5% figure is an
  assumption, not a measurement. Limit-in fills (flat_top) at signal px both sizes;
  market-exit slip -0.5% both sizes (also unverified at $1k).
TEST H — salvage: grinder-from-10:30 SOLO (C's det_grinder_1030) at flat $500 chase
  and at the sized model.
"""
import importlib.util, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("C", HERE + "/edge_stresstest_C_20260815.py")
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
B = C.B; E = C.E

FULL_MIN = 20000.0   # bar dollar-vol for $1,000 clip (clip <= 5% of bar dollars)
HALF_MIN = 10000.0   # bar dollar-vol for $500 half clip
FULL_POS = 1000.0
HALF_POS = 500.0
FULL_SLIP = 0.015    # [CALIBRATION UNKNOWN] chase entry slip at $1,000
HALF_SLIP = 0.01     # chase entry slip at $500 (engine of record's figure)

def stamp_size(signals):
    for s in signals:
        bars, _, _ = E.DAYS[(s["sym"], s["date"])]
        b = bars[s["i"]]
        dv = b["c"] * b["v"]
        s["dv"] = dv
        s["size"] = FULL_POS if dv >= FULL_MIN else (HALF_POS if dv >= HALF_MIN else None)
    return signals

def exec_sized(s, halt_rule):
    """F's execution mix (flat_top limit-in, others chase) under the sized model."""
    if s["size"] is None:
        return False, 0.0, "size_skip", None, None
    old = E.POS; E.POS = s["size"]
    try:
        if s["det"] in C.LIMIT_DETS:
            return B.sim_limit(s, halt_rule)   # entry at signal px exactly, both sizes
        bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
        slip = FULL_SLIP if s["size"] == FULL_POS else HALF_SLIP
        pnl, ex, xi = E.sim(bars, emas, gaps, s["i"], s["entry"], s["stop"],
                            breakeven=(s["det"] == "grinder"),
                            flatten_1959=(s["det"] == "grinder"),
                            entry_slip=slip, mkt_slip=B.MKT_SLIP, halt_rule=halt_rule)
        return True, pnl, ex, xi, s["i"]
    finally:
        E.POS = old

def size_census(name, signals, h4):
    dets = sorted({s["det"] for s in signals})
    print(f"  {name} SIZE CENSUS (signal level): ", end="")
    out = {}
    for d in dets:
        ss = [s for s in signals if s["det"] == d]
        full = sum(1 for s in ss if s["size"] == FULL_POS)
        half = sum(1 for s in ss if s["size"] == HALF_POS)
        skip = sum(1 for s in ss if s["size"] is None)
        out[d] = {"full_1000": full, "half_500": half, "size_skip": skip}
        print(f"{d}: full={full} half={half} skip={skip}  ", end="")
    print()
    print("  post-H4 fills by size: ", {d: {
        "full": sum(1 for x in h4 if x["det"] == d and x["size"] == FULL_POS),
        "half": sum(1 for x in h4 if x["det"] == d and x["size"] == HALF_POS)}
        for d in dets})
    return out

def main():
    nfiles, dates, allsig = B.gen_signals()
    print(f"FILES: {nfiles}  DATES: {len(dates)}  {dates[0]}..{dates[-1]}")
    base = [s for s in allsig if s["det"] != "v2cal"]
    surv = [s for s in base if s["det"] in ("flat_top", "grinder")]
    vwap = [s for s in base if s["det"] == "vwap"]
    print("survivor signals:", len(surv),
          {d: sum(1 for s in surv if s["det"] == d) for d in ("flat_top", "grinder")},
          " vwap:", len(vwap))

    # TEST G — F configuration, sized model
    gsig = sorted(surv + vwap, key=lambda s: (s["key"], s["sym"], s["det"]))
    stamp_size(gsig)
    resG = B.pipeline(gsig, dates, exec_sized, "TEST G — F config SIZED ($1k/$500/skip)")
    censusG = size_census("G", gsig, resG["h4"])

    # TEST H — grinder-from-10:30 SOLO
    hsig = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in C.det_grinder_1030(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            hsig.append({"sym": sym, "date": date, "det": "grinder", "i": t["i"],
                         "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    hsig.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    stamp_size(hsig)
    print("\nTEST H grinder-1030 solo signals:", len(hsig))
    resH500 = B.pipeline(hsig, dates, B.sim_chase, "TEST H(i) — grinder-1030 SOLO, $500 chase")
    resHsz = B.pipeline(hsig, dates, exec_sized, "TEST H(ii) — grinder-1030 SOLO, SIZED")
    censusH = size_census("H", hsig, resHsz["h4"])

    json.dump({k: {"daily": r["daily"], "h5": r["h5"],
                   "verdict": {c: p for c, (v, p) in r["verdict"].items()}}
               for k, r in (("G", resG), ("H500", resH500), ("Hsized", resHsz))}
              | {"censusG": censusG, "censusH": censusH},
              open(HERE + "/stress_D_out.json", "w"), indent=1, default=str)
    print("\nwrote stress_D_out.json")

if __name__ == "__main__":
    main()
