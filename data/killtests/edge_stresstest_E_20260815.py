#!/usr/bin/env python3
"""EDGE STRESS-TEST E (FAIR CAPACITY + THE PRE STREAM, PRE-REGISTERED FRESH) —
run 8/14 eve, filed 20260815. Imports edge_stresstest_D_20260815.py
(-> C -> B -> engine of record). Detectors, sim, limit mechanics, H2-H4
machinery UNCHANGED. Same 36-date window, same cache, same bar:
mean AND median > +$50/day, green >= 55%, both halves positive, worst > -$300.

TEST I — FAIR CAPACITY GUARD: re-run D's TEST G (F config, $1,000 clips) and
  grinder-1030 SOLO sized, with a ROLLING-60s guard: sum of dollar volume over
  the 6 bars STARTING AT the signal bar (i..i+5):
    >= $40,000 -> $1,000 full clip (clip <= 2.5% of the minute's dollars)
    >= $20,000 -> $500 half clip
    else       -> skipped-for-size.
  Slippage schedule = round D's: chase -1% at $500, -1.5% at $1,000
  [CALIBRATION UNKNOWN]. NOTE (disclosed): the guard reads bars i+1..i+5, which
  are in the signal bar's FUTURE — legitimate for a capacity/tradability
  assessment (would the minute have absorbed us), but it is NOT a tradeable
  live filter as written; a live version must use trailing volume.

TEST J — THE PRE STREAM: flat_top + vwap band-pass detectors on the
  07:00-09:25 ET (11:00-13:25Z, EDT window) premarket bars. Entries chased -1%,
  exits = uniform model on the truncated bar array, so the final-bar EOD exit
  IS the 09:25 flatten (bot's PRE rule). $500 flat. Premarket coverage
  verified + disclosed per file (aggregates here, per-file in
  stress_E_coverage.json).

TEST K — grinder-1030 SOLO ($500 chase, D's exact spec) + PRE stream combined,
  2 slots, H4 capacity walk, full H5 + 5-criterion verdict.
"""
import importlib.util, json, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("D", HERE + "/edge_stresstest_D_20260815.py")
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
C = D.C; B = D.B; E = D.E

FULL60 = 40000.0   # rolling-60s dollar-vol for $1,000 clip (<=2.5% of minute)
HALF60 = 20000.0   # for $500 half clip

def stamp_size60(signals):
    for s in signals:
        bars, _, _ = E.DAYS[(s["sym"], s["date"])]
        dv60 = sum(b["c"] * b["v"] for b in bars[s["i"]:s["i"] + 6])
        s["dv60"] = dv60
        s["size"] = (D.FULL_POS if dv60 >= FULL60 else
                     (D.HALF_POS if dv60 >= HALF60 else None))
    return signals

# ---- TEST J: PRE stream ----
PRE_LO, PRE_HI = "11:00:00", "13:25:00"   # 07:00-09:25 ET (EDT)

def build_pre(files):
    cov = []; presig = []
    for f in files:
        sym, date, bars = E.load(f)
        first_t = bars[0]["t"][11:19] if bars else None
        pre_all = [b for b in bars if E.hhmm_b(b) < "13:30:00"]
        win = [b for b in pre_all if PRE_LO <= E.hhmm_b(b) <= PRE_HI]
        cov.append({"file": os.path.basename(f), "sym": sym, "date": date,
                    "first_bar": first_t, "n_pre_bars": len(pre_all),
                    "n_window_bars": len(win)})
        if len(win) < 60: continue   # same 60-bar minimum as the RTH engine
        emas = E.ema_series([b["c"] for b in win], 90)
        gaps = E.find_gaps(win)
        E.DAYS[("PRE:" + sym, date)] = (win, emas, gaps)
        for det, fn in (("pre_flat_top", E.det_flat_top), ("pre_vwap", E.det_vwap)):
            for t in fn(win, emas, gaps):
                hh = E.hhmm_b(win[t["i"]])
                presig.append({"sym": "PRE:" + sym, "date": date, "det": det,
                               "i": t["i"], "t": hh, "key": date + "T" + hh,
                               "entry": t["entry"], "stop": t["stop"]})
    presig.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    return cov, presig

def exec_pre(s, halt_rule, log=None):
    """$500 chase -1% entry; sim on the truncated PRE array -> final-bar EOD
    exit = the 09:25 flatten, at -0.5% mkt slip."""
    bars, emas, gaps = E.DAYS[(s["sym"], s["date"])]
    pnl, ex, xi = E.sim(bars, emas, gaps, s["i"], s["entry"], s["stop"],
                        breakeven=False, flatten_1959=False,
                        entry_slip=0.01, mkt_slip=B.MKT_SLIP,
                        halt_rule=halt_rule, log=log)
    return True, pnl, ex, xi, s["i"]

def exec_K(s, halt_rule):
    return exec_pre(s, halt_rule) if s["sym"].startswith("PRE:") else B.sim_chase(s, halt_rule)

def main():
    nfiles, dates, allsig = B.gen_signals()   # populates E.DAYS (RTH); 36-date window
    print(f"FILES: {nfiles}  DATES: {len(dates)}  {dates[0]}..{dates[-1]}")
    base = [s for s in allsig if s["det"] != "v2cal"]
    surv = [s for s in base if s["det"] in ("flat_top", "grinder")]
    vwap = [s for s in base if s["det"] == "vwap"]
    print("survivor signals:", len(surv),
          {d: sum(1 for s in surv if s["det"] == d) for d in ("flat_top", "grinder")},
          " vwap:", len(vwap))

    # ---- TEST I(i): F config, sized, ROLLING-60s guard ----
    isig = sorted(surv + vwap, key=lambda s: (s["key"], s["sym"], s["det"]))
    stamp_size60(isig)
    resIi = B.pipeline(isig, dates, D.exec_sized, "TEST I(i) — F config SIZED, ROLLING-60s guard")
    cenIi = D.size_census("I(i)", isig, resIi["h4"])

    # grinder-1030 solo signal set (D's exact construction)
    hsig = []
    for (sym, date), (bars, emas, gaps) in list(E.DAYS.items()):
        if sym.startswith("PRE:"): continue
        for t in C.det_grinder_1030(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            hsig.append({"sym": sym, "date": date, "det": "grinder", "i": t["i"],
                         "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    hsig.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    print("\ngrinder-1030 solo signals:", len(hsig))

    # ---- TEST I(ii): grinder-1030 solo, sized, ROLLING-60s guard ----
    stamp_size60(hsig)
    resIii = B.pipeline(hsig, dates, D.exec_sized, "TEST I(ii) — grinder-1030 SOLO SIZED, ROLLING-60s guard")
    cenIii = D.size_census("I(ii)", hsig, resIii["h4"])

    # ---- TEST J: PRE stream ----
    files = sorted(f for f in glob.glob(E.BARS_DIR + "/*.json")
                   if "2026-06-25" <= os.path.basename(f)[:10] <= "2026-08-14")
    cov, presig = build_pre(files)
    n_any_pre = sum(1 for c in cov if c["n_pre_bars"] > 0)
    n_win60 = sum(1 for c in cov if c["n_window_bars"] >= 60)
    firsts = sorted(c["first_bar"] for c in cov if c["first_bar"])
    import statistics as st
    wb = [c["n_window_bars"] for c in cov]
    print(f"\nPRE COVERAGE: files={len(cov)}  with>=1 premkt bar={n_any_pre}  "
          f"with>=60 window bars={n_win60}")
    print(f"  first-bar time: min={firsts[0]} median={firsts[len(firsts)//2]} max={firsts[-1]}")
    print(f"  window-bar count (of max 872): min={min(wb)} median={st.median(wb)} mean={st.mean(wb):.0f} max={max(wb)}")
    print(f"  files with first bar at 08:00:xx Z (04:00 ET): "
          f"{sum(1 for t in firsts if t.startswith('08:0'))}")
    print("PRE signals:", len(presig),
          {d: sum(1 for s in presig if s["det"] == d) for d in ("pre_flat_top", "pre_vwap")})
    resJ = B.pipeline(presig, dates, exec_pre, "TEST J — PRE STREAM solo ($500 chase, 09:25 flatten)")
    jw = sum(1 for x in resJ["h4"] if x["pnl"] > 0)
    print(f"  J post-H4: N={len(resJ['h4'])} winners={jw} win%={100*jw/len(resJ['h4']):.0f}%"
          if resJ["h4"] else "  J post-H4: N=0")

    # ---- TEST K: grinder-1030 solo $500 chase + PRE stream, 2 slots ----
    ksig = sorted(hsig + presig, key=lambda s: (s["key"], s["sym"], s["det"]))
    resK = B.pipeline(ksig, dates, exec_K, "TEST K — grinder-1030 SOLO + PRE STREAM, 2 slots")

    # ---- hand-traces ----
    if resK["h4"]:
        pre_trades = [x for x in resK["h4"] if x["sym"].startswith("PRE:")]
        if pre_trades:
            tr = pre_trades[0]; log = []
            exec_pre(tr, True, log=log)
            print(f"\nHAND-TRACE PRE: {tr['sym']} {tr['date']} {tr['t']} {tr['det']} "
                  f"entry_sig={tr['entry']:.4f} stop={tr['stop']:.4f} pnl=${tr['pnl']:+.4f}")
            for l in log: print("   ", l)
        kd = max(set(x["date"] for x in resK["h4"]),
                 key=lambda d: sum(1 for x in resK["h4"] if x["date"] == d))
        print(f"\nHAND-TRACE K DAY {kd}:")
        tot = 0.0
        for x in resK["h4"]:
            if x["date"] == kd:
                tot += x["pnl"]
                print(f"    {x['fill_t']} {x['sym']:>12} {x['det']:<12} pnl=${x['pnl']:+.2f} exit={x['exit']}")
        print(f"    sum=${tot:+.2f}  vs daily table ${resK['daily'][kd]:+.2f}")

    json.dump({k: {"daily": r["daily"], "h5": r["h5"],
                   "verdict": {c: p for c, (v, p) in r["verdict"].items()}}
               for k, r in (("Ii", resIi), ("Iii", resIii), ("J", resJ), ("K", resK))}
              | {"censusIi": cenIi, "censusIii": cenIii},
              open(HERE + "/stress_E_out.json", "w"), indent=1, default=str)
    json.dump(cov, open(HERE + "/stress_E_coverage.json", "w"), indent=1)
    print("\nwrote stress_E_out.json + stress_E_coverage.json")

if __name__ == "__main__":
    main()
