#!/usr/bin/env python3
"""Kill-tests: #37 halt-resumption lane, #48 vertical-regime (grinder) lane.
Data: tick-reconstructed 10s bars (bars exist only where trades printed).
Laws: bars in order, no lookahead, $500/position, uniform exits
(half at +4%, trail EMA90-of-10s-closes, stop-first on ties), flatten 15:59 ET.
"""
import json, glob, os, statistics
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DATA = "/Users/marcosolivera/Desktop/Marcos-Trading-Bot/data/universe/bars10s"
POS = 500.0

def load(fp):
    d = json.load(open(fp))
    bars = []
    for b in d["bars"]:
        t = datetime.fromisoformat(b["time"].replace("Z", "+00:00")).astimezone(ET)
        bars.append({"t": t, "o": float(b["open"]), "h": float(b["high"]),
                     "l": float(b["low"]), "c": float(b["close"]), "v": float(b["volume"])})
    bars.sort(key=lambda x: x["t"])
    return d["sym"], d["date"], bars

def ema_series(bars, span=90):
    k = 2.0 / (span + 1)
    out = []
    e = None
    for b in bars:
        e = b["c"] if e is None else b["c"] * k + e * (1 - k)
        out.append(e)
    return out

def simulate(bars, emas, i_entry, entry_px, stop_px, trace=None):
    """Uniform exit engine. Enter at close of bar i_entry. Returns $PnL on $500."""
    sh = POS / entry_px
    half = sh / 2.0
    rem = sh
    pnl = 0.0
    target = entry_px * 1.04
    half_done = False
    eod = None
    for i in range(i_entry + 1, len(bars)):
        b = bars[i]
        if b["t"].hour >= 16 or (b["t"].hour == 15 and b["t"].minute >= 59):
            eod = i; break
        # stop-first ties against the trade
        if b["l"] <= stop_px:
            pnl += rem * (stop_px - entry_px)
            if trace is not None: trace.append(f"  {b['t']:%H:%M:%S} STOP hit at {stop_px:.4f} (bar low {b['l']:.4f}) -> exit {rem/sh:.0%} of size")
            return pnl
        if not half_done and b["h"] >= target:
            pnl += half * (target - entry_px)
            rem -= half
            half_done = True
            stop_px = max(stop_px, entry_px)  # move stop to breakeven after half
            if trace is not None: trace.append(f"  {b['t']:%H:%M:%S} +4% TARGET {target:.4f} hit (bar high {b['h']:.4f}) -> half off, stop->breakeven")
        if half_done and b["c"] < emas[i]:
            pnl += rem * (b["c"] - entry_px)
            if trace is not None: trace.append(f"  {b['t']:%H:%M:%S} EMA90 trail break (close {b['c']:.4f} < ema {emas[i]:.4f}) -> runner out")
            return pnl
    j = eod if eod is not None else len(bars) - 1
    pnl += rem * (bars[j]["c"] - entry_px)
    if trace is not None: trace.append(f"  {bars[j]['t']:%H:%M:%S} flatten at close {bars[j]['c']:.4f}")
    return pnl

def rth(bars):
    return [i for i, b in enumerate(bars) if (b["t"].hour, b["t"].minute) >= (9, 30) and b["t"].hour < 16]

# ---------- KT1: halt-resumption ----------
def find_halts(bars, med_vol):
    halts, suspects = [], []
    for i in range(1, len(bars)):
        gap = (bars[i]["t"] - bars[i-1]["t"]).total_seconds()
        pre, post = bars[i-1], bars[i]
        # only gaps starting in RTH (9:30-15:45)
        if not ((pre["t"].hour, pre["t"].minute) >= (9, 30) and (pre["t"].hour, pre["t"].minute) < (15, 45)):
            continue
        heavy = pre["v"] >= 5 * med_vol and post["v"] >= 5 * med_vol
        if gap >= 240 and heavy:
            halts.append(i)
        elif 120 <= gap < 240 and heavy:
            suspects.append(i)
    return halts, suspects

def kt1(files):
    res = {v: [] for v in "abc"}
    n_halts = n_susp = 0
    traces = {}
    for fp in files:
        sym, date, bars = load(fp)
        if len(bars) < 100: continue
        emas = ema_series(bars)
        med_vol = statistics.median(b["v"] for b in bars) or 1.0
        halts, susp = find_halts(bars, med_vol)
        n_halts += len(halts); n_susp += len(susp)
        for i in halts:
            pre_px = bars[i-1]["c"]
            rb = bars[i]  # resumption bar
            up = rb["c"] > pre_px
            base = dict(sym=sym, date=date, t=rb["t"], up=up)
            # (c) control: every resumption, entry at resumption bar close
            tr = [] if ("c" not in traces) else None
            if rb["l"] < rb["c"]:
                pnl = simulate(bars, emas, i, rb["c"], rb["l"], tr)
                res["c"].append({**base, "pnl": pnl})
                if tr is not None:
                    traces["c"] = (f"{sym} {date}: halt gap ended {rb['t']:%H:%M:%S}, pre-halt {pre_px:.4f}, "
                                   f"resumption bar O{rb['o']:.4f} H{rb['h']:.4f} L{rb['l']:.4f} C{rb['c']:.4f}; "
                                   f"ENTER {POS/rb['c']:.1f}sh at {rb['c']:.4f}, stop {rb['l']:.4f}\n" + "\n".join(tr))
            # (a) gap-up-go: green resumption bar closing above pre-halt price
            if rb["c"] > rb["o"] and rb["c"] > pre_px and rb["l"] < rb["c"]:
                tr = [] if ("a" not in traces) else None
                pnl = simulate(bars, emas, i, rb["c"], rb["l"], tr)
                res["a"].append({**base, "pnl": pnl})
                if tr is not None:
                    traces["a"] = (f"{sym} {date}: green resumption {rb['t']:%H:%M:%S} close {rb['c']:.4f} > pre-halt {pre_px:.4f}; "
                                   f"ENTER at {rb['c']:.4f}, stop {rb['l']:.4f}\n" + "\n".join(tr))
            # (b) resumption retest: first pullback holding above resumption open, enter on reclaim
            r_open = rb["o"]
            dip_low = None; prev = rb; entered = False
            for j in range(i + 1, min(i + 60, len(bars))):  # 10-min window
                b = bars[j]
                if b["l"] < r_open: break  # pullback failed to hold
                if b["l"] < prev["l"]:
                    dip_low = b["l"] if dip_low is None else min(dip_low, b["l"])
                elif dip_low is not None and b["c"] > prev["h"]:
                    tr = [] if ("b" not in traces) else None
                    pnl = simulate(bars, emas, j, b["c"], dip_low, tr)
                    res["b"].append({**base, "t": b["t"], "pnl": pnl})
                    if tr is not None:
                        traces["b"] = (f"{sym} {date}: resumption {rb['t']:%H:%M:%S} open {r_open:.4f}; pullback low {dip_low:.4f} held; "
                                       f"reclaim bar {b['t']:%H:%M:%S} close {b['c']:.4f} > prior high {prev['h']:.4f}; "
                                       f"ENTER at {b['c']:.4f}, stop {dip_low:.4f}\n" + "\n".join(tr))
                    entered = True; break
                prev = b
    return res, n_halts, n_susp, traces

# ---------- KT2: vertical-regime grinder ----------
def kt2(files):
    res = {v: [] for v in "ab"}
    n_cand = 0
    traces = {}
    for fp in files:
        sym, date, bars = load(fp)
        if len(bars) < 100: continue
        emas = ema_series(bars)
        # session VWAP from 9:30
        vwap = [None] * len(bars); cv = cpv = 0.0
        sess_hi = None
        last_entry_t = {v: None for v in "ab"}
        pend_b = None  # (new_high_px, dip_low, prev_bar)
        for i, b in enumerate(bars):
            hm = (b["t"].hour, b["t"].minute)
            if hm < (9, 30) or b["t"].hour >= 16: continue
            tp = (b["h"] + b["l"] + b["c"]) / 3.0
            cv += b["v"]; cpv += tp * b["v"]
            vwap[i] = cpv / cv if cv else b["c"]
            new_hi = sess_hi is None or b["h"] > sess_hi
            prev_hi = sess_hi
            sess_hi = b["h"] if new_hi else sess_hi
            if b["t"].hour < 11: pend_b = None; continue
            # signature checks on new session high
            if new_hi and prev_hi is not None:
                w30 = [x for x in bars[:i+1] if x["t"] >= b["t"] - timedelta(minutes=30) and (x["t"].hour, x["t"].minute) >= (9,30)]
                w15 = [x for x in w30 if x["t"] >= b["t"] - timedelta(minutes=15)]
                if len(w30) < 2 or len(w15) < 2: continue
                net_up = b["c"] > w30[0]["c"]
                above_vwap = b["c"] > vwap[i]
                # no >=3% pullback in last 15 min: max drop from running high
                run_hi = w15[0]["h"]; max_dd = 0.0
                for x in w15:
                    run_hi = max(run_hi, x["h"])
                    max_dd = max(max_dd, (run_hi - x["l"]) / run_hi)
                if net_up and above_vwap and max_dd < 0.03:
                    n_cand += 1
                    lo15 = min(x["l"] for x in w15)
                    # (a) breakout entry at this bar close, 15-min cooldown
                    if (last_entry_t["a"] is None or b["t"] - last_entry_t["a"] > timedelta(minutes=15)) and lo15 < b["c"]:
                        tr = [] if ("a" not in traces) else None
                        pnl = simulate(bars, emas, i, b["c"], lo15, tr)
                        res["a"].append(dict(sym=sym, date=date, t=b["t"], pnl=pnl))
                        last_entry_t["a"] = b["t"]
                        if tr is not None:
                            traces["a"] = (f"{sym} {date}: new session high {b['h']:.4f} at {b['t']:%H:%M:%S} (prev {prev_hi:.4f}); "
                                           f"30m net-up, above VWAP {vwap[i]:.4f}, max 15m pullback {max_dd:.2%}; "
                                           f"ENTER at close {b['c']:.4f}, stop 15m-low {lo15:.4f}\n" + "\n".join(tr))
                    # arm (b)
                    pend_b = dict(hi=b["h"], dip=None, prev=b, t0=b["t"])
                    continue
            # (b) micro-dip tracking
            if pend_b is not None:
                dd = (pend_b["hi"] - b["l"]) / pend_b["hi"]
                if dd > 0.02 or b["t"] - pend_b["t0"] > timedelta(minutes=15):
                    pend_b = None
                elif b["l"] < pend_b["prev"]["l"] and dd >= 0.01:
                    pend_b["dip"] = b["l"] if pend_b["dip"] is None else min(pend_b["dip"], b["l"])
                    pend_b["prev"] = b
                elif pend_b["dip"] is not None and b["l"] > pend_b["prev"]["l"]:  # higher-low bar
                    if last_entry_t["b"] is None or b["t"] - last_entry_t["b"] > timedelta(minutes=15):
                        tr = [] if ("b" not in traces) else None
                        pnl = simulate(bars, emas, i, b["c"], pend_b["dip"], tr)
                        res["b"].append(dict(sym=sym, date=date, t=b["t"], pnl=pnl))
                        last_entry_t["b"] = b["t"]
                        if tr is not None:
                            traces["b"] = (f"{sym} {date}: new high {pend_b['hi']:.4f}, micro-dip to {pend_b['dip']:.4f} "
                                           f"({(pend_b['hi']-pend_b['dip'])/pend_b['hi']:.2%}); higher-low bar {b['t']:%H:%M:%S} "
                                           f"low {b['l']:.4f} > prior low {pend_b['prev']['l']:.4f}; ENTER at {b['c']:.4f}, stop {pend_b['dip']:.4f}\n" + "\n".join(tr))
                    pend_b = None
                else:
                    pend_b["prev"] = b
    return res, n_cand, traces

def table(trades, all_dates):
    if not trades:
        return "N=0 — no entries.\n", {}
    mid = sorted(all_dates)[len(all_dates)//2]
    def agg(rows):
        if not rows: return dict(n=0, win=0.0, tot=0.0, mean=0.0)
        w = sum(1 for r in rows if r["pnl"] > 0)
        t = sum(r["pnl"] for r in rows)
        return dict(n=len(rows), win=100.0*w/len(rows), tot=t, mean=t/len(rows))
    splits = {
        "ALL": trades,
        "09:30-10:30 ET": [r for r in trades if (9,30) <= (r["t"].hour, r["t"].minute) < (10,30)],
        "rest of day": [r for r in trades if not ((9,30) <= (r["t"].hour, r["t"].minute) < (10,30))],
        "first-half dates": [r for r in trades if r["date"] < mid],
        "second-half dates": [r for r in trades if r["date"] >= mid],
    }
    if "up" in trades[0]:
        splits["up-halts"] = [r for r in trades if r["up"]]
        splits["down-halts"] = [r for r in trades if not r["up"]]
    out = "| split | N | win% | total $ | mean $ |\n|---|---|---|---|---|\n"
    for k, rows in splits.items():
        a = agg(rows)
        out += f"| {k} | {a['n']} | {a['win']:.0f}% | {a['tot']:+.2f} | {a['mean']:+.2f} |\n"
    return out, {k: agg(v) for k, v in splits.items()}

if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(DATA, "*.json")))
    dates = sorted({os.path.basename(f).split("_")[0] for f in files})
    print(f"COVERAGE: {len(files)} files, {len(dates)} dates {dates[0]}..{dates[-1]}")
    r1, nh, ns, tr1 = kt1(files)
    print(f"\nKT1 halts found: {nh} (suspect 2-4min gaps excluded: {ns})")
    for v, name in [("a","gap-up-go"),("b","resumption retest"),("c","control all")]:
        t, _ = table(r1[v], dates)
        print(f"\n-- KT1 ({v}) {name} --\n{t}")
    for v in tr1: print(f"\nKT1({v}) HAND-TRACE:\n{tr1[v]}")
    r2, nc, tr2 = kt2(files)
    print(f"\nKT2 grinder candidates: {nc}")
    for v, name in [("a","breakout"),("b","micro-dip higher-low")]:
        t, _ = table(r2[v], dates)
        print(f"\n-- KT2 ({v}) {name} --\n{t}")
    for v in tr2: print(f"\nKT2({v}) HAND-TRACE:\n{tr2[v]}")
