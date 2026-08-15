#!/usr/bin/env python3
"""CONTEXT JOINS (pre-registered 8/14 eve, filed 20260815) — VWAP-first + runway
counterfactuals. Read-only analysis; imports edge_stresstest_G (-> F -> C -> B ->
engine of record). All exits E3 (bank 1/2 +10%, trail 10%-off-high closes-through,
stop-first, -1% chase entry slip, -0.5% market-exit slip), H2 halt + H3 dedup,
no capacity (context grading, N kept constant — same convention as round F/G
per-entry tables).

JOIN 1 — VWAP-FIRST: grade every signal of the three lanes (grinder-1030,
flat_top BREAK-attack in-window, calibrated v2 in-window) by VWAP context at the
fire bar: side (above/below), |distance| band (0-1% / 1-3% / 3%+), and VWAP
slope over the prior 5 min (rising/flat/falling; flat = |dVWAP| < 0.1%).
VWAP = session typical-price cumulative over RTH bars (RTH-anchored — matches
the grinder detector's internal vwap; the live ~vwap is premarket-anchored,
disclosed as a caveat).

JOIN 2 — RUNWAY COUNTERFACTUALS: every runway_reject row 8/11-8/14 from the
dashboard decisions archive, replayed through E3 on that day's bars (universe
cache first; dashboard /api/bars archive for names the ferry never cached —
partial tapes flagged). Bands <0.3R / 0.3-0.7R / 0.7-1R on runway_rr.
Pre-registered failure condition (the room-gate precedent): the gate is
INVERTED if refused fires' counterfactual P&L is positive and larger than the
losses it prevented.
"""
import importlib.util, json, os, glob, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("G", HERE + "/edge_stresstest_G_20260815.py")
G = importlib.util.module_from_spec(spec)
_stdout = sys.stdout
sys.stdout = open(os.devnull, "w")  # G runs its main on import? (it does not; guard anyway)
spec.loader.exec_module(G)
sys.stdout = _stdout
F = G.F; C = G.C; B = G.B; E = G.E

SCRATCH = os.environ.get("CJ_SCRATCH",
    "/private/tmp/claude-501/-Users-marcosolivera-Desktop-website-data/"
    "add2ac85-fd80-47f7-b583-bda802f0544d/scratchpad")
DASH = "https://zestful-intuition-production-b16a.up.railway.app"
SECRET = {"X-Dashboard-Secret": "marcos2026"}

# ---------------- JOIN 1 ----------------
VW = {}   # (sym,date) -> vwap array aligned to E.DAYS bars

def build_vwap(sym, date):
    bars, _, _ = E.DAYS[(sym, date)]
    cv = cpv = 0.0; out = []
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cv += b["v"]; cpv += tp * b["v"]
        out.append(cpv / cv if cv else b["c"])
    VW[(sym, date)] = out

def ctx(s):
    bars, _, _ = E.DAYS[(s["sym"], s["date"])]
    vw = VW[(s["sym"], s["date"])]
    i = s["i"]; v = vw[i]; px = s["entry"]
    side = "above" if px >= v else "below"
    dist = abs(px - v) / v if v else 0.0
    band = "0-1%" if dist < 0.01 else ("1-3%" if dist < 0.03 else "3%+")
    j = max(0, i - 30)  # 5 min of 10s bars
    dv = (v - vw[j]) / vw[j] if vw[j] else 0.0
    slope = "rising" if dv > 0.001 else ("falling" if dv < -0.001 else "flat")
    return side, band, slope

def run_lane_e3(signals, dates):
    tr = []
    for s in signals:
        _, pnl, exx, xi, fb = G.exec_e3(s, True)
        bars, _, _ = E.DAYS[(s["sym"], s["date"])]
        ft = E.hhmm_b(bars[fb])
        tr.append({**s, "pnl": pnl, "exit": exx, "xi": xi, "fill_t": ft,
                   "fill_key": s["date"] + "T" + ft})
    return F.dedup(tr)

def cell_table(tr, keyfn):
    cells = {}
    for x in tr:
        k = keyfn(x)
        c = cells.setdefault(k, {"n": 0, "w": 0, "tot": 0.0})
        c["n"] += 1; c["w"] += 1 if x["pnl"] > 0 else 0; c["tot"] += x["pnl"]
    return cells

def join1():
    nfiles, dates, allsig = B.gen_signals()
    print(f"FILES: {nfiles}  DATES: {len(dates)}  {dates[0]}..{dates[-1]}")
    for k in E.DAYS: build_vwap(*k)
    # lanes
    gsig = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in C.det_grinder_1030(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            gsig.append({"sym": sym, "date": date, "det": "grinder", "i": t["i"],
                         "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    fbrk = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for t in G.det_flat_top_break(bars, emas, gaps):
            hh = E.hhmm_b(bars[t["i"]])
            if not ("13:30:00" <= hh <= "14:30:00"): continue
            fbrk.append({"sym": sym, "date": date, "det": "flat_top", "i": t["i"],
                         "t": hh, "key": date + "T" + hh, "entry": t["entry"], "stop": t["stop"]})
    v2c = [s for s in allsig if s["det"] == "v2cal"]
    for lane in (gsig, fbrk):
        lane.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    out = {}
    for name, sig in (("grinder1030", gsig), ("flat_top_break", fbrk), ("v2cal", v2c)):
        tr = run_lane_e3(sig, dates)
        for x in tr:
            x["side"], x["band"], x["slope"] = ctx(x)
        tot = sum(x["pnl"] for x in tr)
        print(f"\n== JOIN1 {name}: N={len(tr)} total=${tot:+.2f} ==")
        rows = {}
        rows["side"] = cell_table(tr, lambda x: x["side"])
        rows["side_band"] = cell_table(tr, lambda x: (x["side"], x["band"]))
        rows["slope"] = cell_table(tr, lambda x: x["slope"])
        rows["side_slope"] = cell_table(tr, lambda x: (x["side"], x["slope"]))
        for dim, cells in rows.items():
            for k in sorted(cells, key=str):
                c = cells[k]
                print(f"  {dim:10s} {str(k):24s} N={c['n']:4d} win={100*c['w']/c['n']:3.0f}% "
                      f"total=${c['tot']:+10.2f} mean/tr=${c['tot']/c['n']:+8.2f}")
        out[name] = {"N": len(tr), "total": tot,
                     "cells": {d: {str(k): v for k, v in cc.items()} for d, cc in rows.items()}}
    return out, dates

# ---------------- JOIN 2 ----------------
def fetch_bars(date, tkr):
    p = f"{SCRATCH}/cj_bars_{date}_{tkr}.json"
    if os.path.exists(p):
        j = json.load(open(p))
    else:
        req = urllib.request.Request(
            f"{DASH}/api/bars?date={date}&ticker={tkr}~ALP10S", headers=SECRET)
        j = json.load(urllib.request.urlopen(req, timeout=30))
        json.dump(j, open(p, "w"))
    bars = [{"t": b["time"][:19].replace(" ", "T"), "o": float(b["open"]),
             "h": float(b["high"]), "l": float(b["low"]), "c": float(b["close"]),
             "v": float(b["volume"])} for b in (j.get("bars") or [])]
    bars.sort(key=lambda x: x["t"])
    return E.rth(bars)

def band3(rr):
    if rr is None: return "?"
    return "<0.3R" if rr < 0.3 else ("0.3-0.7R" if rr < 0.7 else "0.7-1R")

def et_to_utc_hh(tstr):
    # "09:35:14 AM" ET (EDT, UTC-4 in Aug) -> "13:35:14"
    hh, mm, ss = tstr[:8].split(":")
    h = int(hh) % 12 + (12 if tstr[-2:] == "PM" else 0)
    return f"{(h+4)%24:02d}:{mm}:{ss}"

def join2():
    cache = {os.path.basename(f)[:-5] for f in glob.glob(E.BARS_DIR + "/*.json")}
    rows = []
    for d in ("2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14"):
        p = f"{SCRATCH}/runway_{d}.json"
        if os.path.exists(p):
            j = json.load(open(p))
        else:
            req = urllib.request.Request(
                f"{DASH}/api/decisions_archive?date={d}&status=runway_reject&limit=50000",
                headers=SECRET)
            j = json.load(urllib.request.urlopen(req, timeout=30))
        rows += j.get("rows") or []
    print(f"\n== JOIN2: {len(rows)} runway_reject rows 8/11-8/14 ==")
    results = []
    for r in rows:
        d, tkr = r["date"], r["ticker"]
        key = f"{d}_{tkr}"
        src = "cache" if key in cache else "dash"
        try:
            if (tkr, d) in E.DAYS:
                bars, emas, gaps = E.DAYS[(tkr, d)]
            elif src == "cache":
                sym, date, bars = E.load(f"{E.BARS_DIR}/{key}.json")
                bars = E.rth(bars)
                emas = E.ema_series([b["c"] for b in bars], 90)
                gaps = E.find_gaps(bars)
                E.DAYS[(tkr, d)] = (bars, emas, gaps)
            else:
                bars = fetch_bars(d, tkr)
                if len(bars) < 30:
                    results.append({**r, "cf": None, "note": f"no tape ({len(bars)} bars)"})
                    continue
                emas = E.ema_series([b["c"] for b in bars], 90)
                gaps = E.find_gaps(bars)
        except Exception as ex:
            results.append({**r, "cf": None, "note": f"load fail: {ex}"}); continue
        hh = et_to_utc_hh(r["time"])
        idx = next((i for i, b in enumerate(bars) if E.hhmm_b(b) >= hh), None)
        if idx is None or idx >= len(bars) - 1:
            results.append({**r, "cf": None, "note": "reject after tape end", "src": src})
            continue
        entry = float(r["price"]); stop = float(r["stop"])
        if not (0 < stop < entry):
            results.append({**r, "cf": None, "note": f"bad stop {stop} vs {entry}", "src": src})
            continue
        pnl, exx, xi = F.sim_var(bars, emas, gaps, idx, entry, stop, "E3", r["machine"], True)
        partial = (src == "dash" and exx == "eod" and E.hhmm_b(bars[-1]) < "19:30:00")
        results.append({**r, "cf": pnl, "exit": exx, "src": src,
                        "fill_hh": E.hhmm_b(bars[idx]),
                        "note": "PARTIAL-TAPE eod" if partial else ""})
    rep = [x for x in results if x["cf"] is not None]
    tot = sum(x["cf"] for x in rep)
    pos = sum(x["cf"] for x in rep if x["cf"] > 0)
    neg = sum(x["cf"] for x in rep if x["cf"] <= 0)
    print(f"replayed {len(rep)}/{len(results)}  counterfactual total ${tot:+.2f} "
          f"(winners would-be +${pos:.2f}, losers avoided ${neg:.2f})")
    for dim, keyfn in (("lane", lambda x: x["machine"]),
                       ("band", lambda x: band3(x.get("runway_rr"))),
                       ("date", lambda x: x["date"])):
        cells = {}
        for x in rep:
            c = cells.setdefault(keyfn(x), {"n": 0, "w": 0, "tot": 0.0})
            c["n"] += 1; c["w"] += 1 if x["cf"] > 0 else 0; c["tot"] += x["cf"]
        for k in sorted(cells, key=str):
            c = cells[k]
            print(f"  {dim:5s} {str(k):14s} N={c['n']:3d} win={100*c['w']/c['n']:3.0f}% "
                  f"cf_total=${c['tot']:+9.2f}")
    print("\n  per-row detail:")
    for x in sorted(results, key=lambda x: (x["date"], x["time"])):
        cf = f"${x['cf']:+8.2f}" if x["cf"] is not None else "   n/a  "
        print(f"  {x['date']} {x['time']:>11s} {x['ticker']:<5s} {x['machine']:<12s} "
              f"rr={x.get('runway_rr')} {cf} {x.get('exit','')} [{x.get('src','-')}] {x.get('note','')}")
    return results

if __name__ == "__main__":
    j1, dates = join1()
    j2 = join2()
    json.dump({"join1": j1, "join2": [{k: v for k, v in x.items()} for x in j2]},
              open(HERE + "/context_joins_out.json", "w"), indent=1, default=str)
    print("\nwrote context_joins_out.json")
