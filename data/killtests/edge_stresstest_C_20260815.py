#!/usr/bin/env python3
"""EDGE STRESS-TEST C (MEDIAN ATTACK, PRE-REGISTERED FRESH) — run 8/14 eve, filed 20260815.
Imports edge_stresstest_B_20260815.py (which imports the engine of record
edge_stresstest_20260815.py). Same 36-date window 6/25-8/14, same laws, same bar:
mean AND median > +$50/day, green >= 55%, both halves positive, worst > -$300.

TEST D — per-lane execution mix: grinder CHASED (-1% entry, -0.5% mkt exits),
  flat_top LIMIT-IN (round B mechanics: bid at signal px, fill on trade-through
  <= bid-$0.01 within 180s, fill-bar stop check).
TEST E — pre-registered widening ONLY (no sweep): grinder post-10:30 ET (14:30Z,
  was 15:00Z) + flat_top window 9:30-11:00 ET (13:30-15:00Z, was 13:30-14:30Z).
  D's execution mix. Marginal cohort (added trades) graded on its own dollars.
TEST F — portfolio of D + vwap band-pass chased, in-window (its B numbers were
  small-positive under chase).
"""
import importlib.util, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("B", HERE + "/edge_stresstest_B_20260815.py")
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
E = B.E

# ---- execution mix: pullback entries rest a bid; breakout/strength entries chase ----
LIMIT_DETS = {"flat_top"}          # pullback-class -> limit-in
def exec_mix(s, halt_rule):
    fn = B.sim_limit if s["det"] in LIMIT_DETS else B.sim_chase
    return fn(s, halt_rule)

# ---- TEST E detector variant: grinder from 10:30 ET (14:30Z) ----
def det_grinder_1030(bars, emas, gaps):
    trades = []
    cv = cpv = 0.0; sess_hi = None; last_entry_s = None
    for i, b in enumerate(bars):
        tp = (b["h"]+b["l"]+b["c"])/3.0
        cv += b["v"]; cpv += tp*b["v"]
        vw = cpv/cv if cv else b["c"]
        new_hi = sess_hi is None or b["h"] > sess_hi
        prev_hi = sess_hi
        sess_hi = b["h"] if new_hi else sess_hi
        if E.hhmm_b(b) < "14:30:00": continue  # post-10:30 ET (was 15:00:00Z)
        if new_hi and prev_hi is not None:
            s = E.secs(b)
            w30 = [x for x in bars[:i+1] if E.secs(x) >= s-1800]
            w15 = [x for x in w30 if E.secs(x) >= s-900]
            if len(w30) < 2 or len(w15) < 2: continue
            net_up = b["c"] > w30[0]["c"]
            above_vwap = b["c"] > vw
            run_hi = w15[0]["h"]; max_dd = 0.0
            for x in w15:
                run_hi = max(run_hi, x["h"])
                max_dd = max(max_dd, (run_hi-x["l"])/run_hi)
            if net_up and above_vwap and max_dd < 0.03:
                lo15 = min(x["l"] for x in w15)
                if (last_entry_s is None or s-last_entry_s > 900) and lo15 < b["c"]:
                    E.base_sim(bars, emas, gaps, i, b["c"], lo15, "grinder")
                    trades.append({"i": i, "entry": b["c"], "stop": lo15})
                    last_entry_s = s
    return trades

def main():
    nfiles, dates, allsig = B.gen_signals()   # populates E.DAYS; window-restricted files
    print(f"FILES: {nfiles}  DATES: {len(dates)}  {dates[0]}..{dates[-1]}")
    base = [s for s in allsig if s["det"] != "v2cal"]
    surv = [s for s in base if s["det"] in ("flat_top", "grinder")]
    vwap = [s for s in base if s["det"] == "vwap"]
    print("survivor signals:", len(surv),
          {d: sum(1 for s in surv if s["det"] == d) for d in ("flat_top", "grinder")},
          " vwap:", len(vwap))

    # TEST D
    resD = B.pipeline(surv, dates, exec_mix, "TEST D — grinder CHASE + flat_top LIMIT-IN")

    # TEST E — widened windows, same mix. Rebuild both lanes from E.DAYS.
    wide = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in E.det_flat_top(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            if not ("13:30:00" <= hh <= "15:00:00"): continue   # 9:30-11:00 ET
            wide.append({"sym": sym, "date": date, "det": "flat_top", "i": t["i"],
                         "t": hh, "key": date+"T"+hh, "entry": t["entry"], "stop": t["stop"],
                         "marginal": hh > "14:30:00"})
        for t in det_grinder_1030(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            wide.append({"sym": sym, "date": date, "det": "grinder", "i": t["i"],
                         "t": hh, "key": date+"T"+hh, "entry": t["entry"], "stop": t["stop"],
                         "marginal": hh < "15:00:00"})
    wide.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    print("\nTEST E widened signals:", len(wide),
          {d: sum(1 for s in wide if s["det"] == d) for d in ("flat_top", "grinder")},
          "marginal-window signals:", sum(1 for s in wide if s["marginal"]))
    resE = B.pipeline(wide, dates, exec_mix, "TEST E — WIDENED windows, D's mix")
    marg = [x for x in resE["h4"] if x.get("marginal")]
    core = [x for x in resE["h4"] if not x.get("marginal")]
    def cohort(name, tr):
        tot = sum(x["pnl"] for x in tr)
        g = sum(1 for x in tr if x["pnl"] > 0)
        by = {d: (sum(1 for x in tr if x["det"] == d), sum(x["pnl"] for x in tr if x["det"] == d))
              for d in ("flat_top", "grinder")}
        print(f"  {name}: N={len(tr)} total=${tot:+.2f} "
              f"per-trade=${(tot/len(tr) if tr else 0):+.2f} winners={g} "
              + str({k: f"N={a} ${b:+.2f}" for k, (a, b) in by.items()}))
    print("E MARGINAL-COHORT GRADE (post-H4 trades in the ADDED windows):")
    cohort("marginal (added)", marg)
    cohort("core (orig windows)", core)

    # TEST F — D + vwap chased in-window
    fsig = sorted(surv + vwap, key=lambda s: (s["key"], s["sym"], s["det"]))
    resF = B.pipeline(fsig, dates, exec_mix, "TEST F — D + vwap band-pass (chased)")

    json.dump({k: {"daily": r["daily"], "h5": r["h5"],
                   "verdict": {c: p for c, (v, p) in r["verdict"].items()}}
               for k, r in (("D", resD), ("E", resE), ("F", resF))},
              open(HERE + "/stress_C_out.json", "w"), indent=1, default=str)
    print("\nwrote stress_C_out.json")

if __name__ == "__main__":
    main()
