#!/usr/bin/env python3
"""EDGE STRESS-TEST 8/15 — pre-registered haircut waterfall H0..H4 + H5 robustness.
Four entries: v2 flush, flat_top real-retest (>=1% depth + 15min cooldown),
vwap band-pass (12-30), vertical grinder breakout (KT2a).
Engines ported unchanged from rebuild_bt.py / flattop_v2.py / missing_regimes.py.
Laws: bars in order, no lookahead, stop-first ties against the trade.
"""
import json, glob, os
from datetime import datetime, timezone

BARS_DIR = "/Users/marcosolivera/Desktop/Marcos-Trading-Bot/data/universe/bars10s"
POS = 500.0

def load(f):
    d = json.load(open(f))
    bars = [{"t": b["time"], "o": float(b["open"]), "h": float(b["high"]),
             "l": float(b["low"]), "c": float(b["close"]), "v": float(b["volume"])}
            for b in d["bars"]]
    bars.sort(key=lambda x: x["t"])
    return d["sym"], d["date"], bars

def hhmm_b(b): return b["t"][11:19]
def rth(bars): return [b for b in bars if "13:30:00" <= hhmm_b(b) <= "20:00:00"]
def secs(b):
    h, m, s = hhmm_b(b).split(":"); return int(h)*3600+int(m)*60+int(s)
def epoch(date, b):  # absolute ordering key
    return date + "T" + hhmm_b(b)

def ema_series(closes, period=90):
    out = []; k = 2/(period+1); e = None; s = 0.0
    for i, c in enumerate(closes):
        if i < period: s += c; e = s/(i+1)
        else: e = c*k + e*(1-k)
        out.append(e)
    return out

def find_gaps(bars):
    """(pre_i, post_i, gap_s) for zero-trade gaps >= 4 min between consecutive RTH bars."""
    out = []
    for i in range(1, len(bars)):
        g = secs(bars[i]) - secs(bars[i-1])
        if g >= 240: out.append((i-1, i, g))
    return out

def sim(bars, emas, gaps, entry_i, sig_px, stop, *, breakeven, flatten_1959,
        entry_slip=0.0, mkt_slip=0.0, halt_rule=False, log=None):
    """Unified exit engine. Entry fill = sig_px*(1+entry_slip). Stop/EOD/trail are
    market exits (fill*(1-mkt_slip)); +4% tier is a resting limit (exact).
    halt_rule: entry within 2 min before a >=4-min gap -> if resumption open gapped
    through the stop, exit at resumption open (market)."""
    entry_px = sig_px*(1+entry_slip)
    sh = POS/entry_px; half = sh/2.0; target = entry_px*1.04
    scaled = False; pnl = 0.0; rem = sh
    e_s = secs(bars[entry_i])
    my_gaps = {post: pre for pre, post, g in gaps
               if halt_rule and entry_i <= pre and 0 <= secs(bars[pre]) - e_s <= 120}
    for i in range(entry_i+1, len(bars)):
        b = bars[i]
        if flatten_1959 and hhmm_b(b) >= "19:59:00":
            px = b["c"]*(1-mkt_slip); pnl += rem*(px - entry_px)
            if log is not None: log.append(f"{hhmm_b(b)} FLATTEN 15:59 at {px:.4f}")
            return pnl, "eod", i
        if i in my_gaps and b["o"] < stop:  # gapped through the stop across a halt
            px = b["o"]*(1-mkt_slip); pnl += rem*(px - entry_px)
            if log is not None: log.append(f"{hhmm_b(b)} HALT-GAP exit at resumption open {px:.4f} (stop was {stop:.4f})")
            return pnl, f"haltgap@{hhmm_b(b)}", i
        if b["l"] <= stop:  # stop first — tie goes against the trade
            px = stop*(1-mkt_slip); pnl += rem*(px - entry_px)
            if log is not None: log.append(f"{hhmm_b(b)} STOP {stop:.4f} fill {px:.4f} (low {b['l']:.4f})")
            return pnl, f"stop@{hhmm_b(b)}", i
        if not scaled and b["h"] >= target:
            pnl += half*(target - entry_px); rem -= half; scaled = True
            if breakeven: stop = max(stop, entry_px)
            if log is not None: log.append(f"{hhmm_b(b)} SCALE half at +4% ({target:.4f})")
            continue
        if scaled and b["c"] < emas[i]:
            px = b["c"]*(1-mkt_slip); pnl += rem*(px - entry_px)
            if log is not None: log.append(f"{hhmm_b(b)} TRAIL exit close {b['c']:.4f} < EMA90 {emas[i]:.4f} fill {px:.4f}")
            return pnl, f"trail@{hhmm_b(b)}", i
    b = bars[-1]
    px = b["c"]*(1-mkt_slip); pnl += rem*(px - entry_px)
    if log is not None: log.append(f"{hhmm_b(b)} EOD exit at {px:.4f}")
    return pnl, "eod", len(bars)-1

def agg3min(bars):
    out = []; cur_key = None; cur = None
    for b in bars:
        hh, mm, ss = hhmm_b(b).split(":")
        key = (hh, int(mm)//3)
        if key != cur_key:
            if cur: out.append(cur)
            cur_key = key
            cur = {"t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "end_t": b["t"]}
        else:
            cur["h"] = max(cur["h"], b["h"]); cur["l"] = min(cur["l"], b["l"])
            cur["c"] = b["c"]; cur["end_t"] = b["t"]
    if cur: out.append(cur)
    return out

def base_sim(bars, emas, gaps, i, px, stop, det):
    return sim(bars, emas, gaps, i, px, stop,
               breakeven=(det == "grinder"), flatten_1959=(det == "grinder"))

# ---- detectors (sequencing via baseline engine, unchanged from source scripts) ----
def det_flat_top(bars, emas, gaps):
    trades = []; m3 = agg3min(bars)
    state = "seek"; level = None; pull_low = None
    open_until = -1; cooldown_until = -1
    for i, b in enumerate(bars):
        if i <= open_until: continue
        done = [x for x in m3 if x["end_t"] < b["t"]]
        if state == "seek":
            if len(done) >= 4:
                w = done[-4:]
                hi = max(x["h"] for x in w); lo = min(x["l"] for x in w)
                if lo > 0 and (hi-lo)/lo <= 0.12: level = hi; state = "armed"
        if state == "armed":
            if len(done) >= 4:
                w = done[-4:]
                hi = max(x["h"] for x in w); lo = min(x["l"] for x in w)
                if lo > 0 and (hi-lo)/lo <= 0.12: level = hi
            if b["c"] > level: state = "broke"; continue
        elif state == "broke":
            if b["l"] <= level: state = "pulled"; pull_low = b["l"]; continue
        elif state == "pulled":
            if b["l"] < pull_low: pull_low = b["l"]
            if b["c"] > level:
                depth = (level - pull_low)/level if level > 0 else 0.0
                if depth < 0.01 or secs(b) < cooldown_until:
                    state = "seek"; level = None; pull_low = None; continue
                entry = b["c"]; stop = pull_low
                if stop < entry:
                    pnl, ex, xi = base_sim(bars, emas, gaps, i, entry, stop, "flat_top")
                    trades.append({"i": i, "entry": entry, "stop": stop})
                    open_until = xi
                    cooldown_until = secs(b) + 900
                state = "seek"; level = None; pull_low = None
    return trades

def det_vwap(bars, emas, gaps):
    trades = []
    cpv = 0.0; cv = 0.0; streak = 0; hold_low = None; hold_high = None
    prev_above = None; open_until = -1; rej_open_until = -1; episode_fired = False
    for i, b in enumerate(bars):
        cpv += b["c"]*b["v"]; cv += b["v"]
        if cv <= 0: continue
        vwap = cpv/cv
        above = b["c"] > vwap
        if above:
            if not prev_above:
                streak = 1; hold_low = b["l"]; hold_high = b["h"]; episode_fired = False
            else:
                if (not episode_fired) and streak >= 1 and b["h"] > hold_high:
                    entry = b["c"]; stop = hold_low
                    if stop < entry:
                        if 12 <= streak <= 30 and i > open_until:
                            episode_fired = True
                            pnl, ex, xi = base_sim(bars, emas, gaps, i, entry, stop, "vwap")
                            trades.append({"i": i, "entry": entry, "stop": stop})
                            open_until = xi
                        elif streak < 12 and i > rej_open_until:
                            episode_fired = True  # rejected fire occupies rej slot (as in source)
                            pnl, ex, xi = base_sim(bars, emas, gaps, i, entry, stop, "vwap")
                            rej_open_until = xi
                streak += 1
                hold_low = min(hold_low, b["l"]); hold_high = max(hold_high, b["h"])
        else:
            streak = 0; hold_low = None; hold_high = None
        prev_above = above
    return trades

def det_v2(bars, emas, gaps):
    trades = []; n = len(bars)
    cpv = 0.0; cv = 0.0; vwaps = []
    for b in bars:
        cpv += b["c"]*b["v"]; cv += b["v"]
        vwaps.append(cpv/cv if cv > 0 else b["c"])
    m3 = agg3min(bars)
    open_until = -1; state = "seek"; flush_low = None; flush_i = None
    for i in range(1, n):
        if i <= open_until: continue
        b = bars[i]
        if state == "seek":
            j0 = max(0, i-12)
            loc_hi = max(x["h"] for x in bars[max(0, i-30):i+1])
            recent_hi = max(x["h"] for x in bars[j0:i+1])
            if recent_hi > 0 and (recent_hi - b["l"])/recent_hi >= 0.03 and abs(recent_hi-loc_hi)/loc_hi < 1e-9:
                anchors = [vwaps[i]]
                done = [x for x in m3 if x["end_t"] < b["t"]]
                for k in range(len(done)-3):
                    w = done[k:k+4]
                    hi = max(x["h"] for x in w); lo = min(x["l"] for x in w)
                    if lo > 0 and (hi-lo)/lo <= 0.12: anchors.append(hi)
                if any(a > 0 and abs(b["l"]-a)/a <= 0.02 for a in anchors):
                    state = "flushed"; flush_low = b["l"]; flush_i = i
        elif state == "flushed":
            if b["l"] < flush_low: flush_low = b["l"]
            if i - flush_i > 18: state = "seek"; continue
            p = bars[i-1]
            if b["l"] > p["l"] and b["c"] > p["h"]:
                entry = b["c"]; stop = flush_low
                if stop < entry:
                    pnl, ex, xi = base_sim(bars, emas, gaps, i, entry, stop, "v2")
                    trades.append({"i": i, "entry": entry, "stop": stop})
                    open_until = xi
                state = "seek"
    return trades

def det_grinder(bars, emas, gaps):
    """KT2(a) breakout, ported to UTC strings (9:30ET=13:30Z, 11:00ET=15:00Z)."""
    trades = []
    cv = cpv = 0.0; sess_hi = None; last_entry_s = None
    for i, b in enumerate(bars):
        tp = (b["h"]+b["l"]+b["c"])/3.0
        cv += b["v"]; cpv += tp*b["v"]
        vw = cpv/cv if cv else b["c"]
        new_hi = sess_hi is None or b["h"] > sess_hi
        prev_hi = sess_hi
        sess_hi = b["h"] if new_hi else sess_hi
        if hhmm_b(b) < "15:00:00": continue  # post-11:00 ET only
        if new_hi and prev_hi is not None:
            s = secs(b)
            w30 = [x for x in bars[:i+1] if secs(x) >= s-1800]
            w15 = [x for x in w30 if secs(x) >= s-900]
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
                    pnl, ex, xi = base_sim(bars, emas, gaps, i, b["c"], lo15, "grinder")
                    trades.append({"i": i, "entry": b["c"], "stop": lo15})
                    last_entry_s = s
    return trades

def stage_pnl(sig, stage):
    """Recompute a signal's P&L/exit under a stage config. Stages cumulative."""
    bars, emas, gaps = DAYS[(sig["sym"], sig["date"])]
    kw = {}
    if stage >= 1: kw.update(entry_slip=0.01, mkt_slip=0.005)
    if stage >= 2: kw.update(halt_rule=True)
    return sim(bars, emas, gaps, sig["i"], sig["entry"], sig["stop"],
               breakeven=(sig["det"] == "grinder"), flatten_1959=(sig["det"] == "grinder"), **kw)

DAYS = {}

def main():
    files = sorted(glob.glob(BARS_DIR + "/*.json"))
    dates = sorted({os.path.basename(f)[:10] for f in files})
    print(f"FILES: {len(files)}  DATES: {len(dates)}  {dates[0]}..{dates[-1]}")
    signals = []
    for f in files:
        sym, date, bars = load(f)
        bars = rth(bars)
        if len(bars) < 60: continue
        emas = ema_series([b["c"] for b in bars], 90)
        gaps = find_gaps(bars)
        DAYS[(sym, date)] = (bars, emas, gaps)
        for det, fn, win in (("v2", det_v2, True), ("flat_top", det_flat_top, True),
                             ("vwap", det_vwap, True), ("grinder", det_grinder, False)):
            for t in fn(bars, emas, gaps):
                hh = hhmm_b(bars[t["i"]])
                if win and not ("13:30:00" <= hh <= "14:30:00"): continue
                signals.append({"sym": sym, "date": date, "det": det, "i": t["i"],
                                "t": hh, "key": date+"T"+hh, "entry": t["entry"], "stop": t["stop"]})
    signals.sort(key=lambda s: (s["key"], s["sym"], s["det"]))
    print(f"in-scope signals: {len(signals)}  by det:",
          {d: sum(1 for s in signals if s["det"] == d) for d in ("v2", "flat_top", "vwap", "grinder")})

    def daily_of(trades):
        d = {dt: 0.0 for dt in dates}
        for x in trades: d[x["date"]] += x["pnl"]
        return d

    def report(name, trades):
        d = daily_of(trades)
        vals = list(d.values())
        tot = sum(vals)
        print(f"{name}: N={len(trades)} total=${tot:+.2f} dailymean=${tot/len(vals):+.2f} worst=${min(vals):+.2f}")
        return d

    waterfall = {}
    # H0
    h0 = [{**s, "pnl": stage_pnl(s, 0)[0]} for s in signals]
    waterfall["H0"] = report("H0 baseline", h0)
    # H1
    h1 = []
    for s in signals:
        pnl, ex, xi = stage_pnl(s, 1)
        h1.append({**s, "pnl": pnl, "exit": ex, "xi": xi})
    waterfall["H1"] = report("H1 frictions", h1)
    # H2
    h2 = []
    n_halt_forced = 0
    for s in signals:
        pnl, ex, xi = stage_pnl(s, 2)
        if ex.startswith("haltgap"): n_halt_forced += 1
        h2.append({**s, "pnl": pnl, "exit": ex, "xi": xi})
    waterfall["H2"] = report("H2 halt-excl", h2)
    print(f"  halt-gap forced exits: {n_halt_forced}")
    # H3 dedup (chronological, same name within 5 min across detectors, first wins)
    h3 = []; last_kept = {}; deduped = []
    for s in sorted(h2, key=lambda x: (x["key"], x["det"])):
        k = (s["sym"], s["date"])
        ls = last_kept.get(k)
        ssec = int(s["t"][:2])*3600+int(s["t"][3:6].replace(":", ""))*60+int(s["t"][6:8])
        if ls is not None and ssec - ls <= 300:
            deduped.append(s); continue
        last_kept[k] = ssec
        h3.append(s)
    waterfall["H3"] = report("H3 dedup", h3)
    print(f"  deduped signals dropped: {len(deduped)}")
    # H4 capacity: max 2 concurrent, chronological walk
    h4 = []; skipped = []; open_pos = []
    for s in h3:  # already chronological
        bars, _, _ = DAYS[(s["sym"], s["date"])]
        open_pos = [p for p in open_pos if p >= s["key"]]  # exit at same second = slot still occupied (against the portfolio)
        if len(open_pos) >= 2:
            skipped.append(s); continue
        exit_key = s["date"]+"T"+hhmm_b(bars[min(s["xi"], len(bars)-1)])
        open_pos.append(exit_key)
        h4.append(s)
    waterfall["H4"] = report("H4 capacity", h4)
    print(f"  slot-skipped signals: {len(skipped)}")

    # H5 robustness on post-H4
    d = daily_of(h4); vals = [d[k] for k in dates]
    sv = sorted(vals); n = len(sv)
    median = sv[n//2] if n % 2 else (sv[n//2-1]+sv[n//2])/2
    mid = dates[n//2]
    half1 = sum(d[k] for k in dates if k < mid); half2 = sum(d[k] for k in dates if k >= mid)
    n1 = sum(1 for k in dates if k < mid); n2 = n-n1
    green = sum(1 for v in vals if v > 0)
    best_day = max(dates, key=lambda k: d[k])
    exbest = (sum(vals)-d[best_day])/(n-1)
    contrib = {det: sum(x["pnl"] for x in h4 if x["det"] == det) for det in ("v2", "flat_top", "vwap", "grinder")}
    ncontrib = {det: sum(1 for x in h4 if x["det"] == det) for det in ("v2", "flat_top", "vwap", "grinder")}
    print("\nH5 ROBUSTNESS (post-H4):")
    print(f" days={n} mean=${sum(vals)/n:+.2f} median=${median:+.2f} worst=${min(vals):+.2f} ({min(d,key=d.get)})")
    print(f" green {green}/{n} = {100*green/n:.0f}%")
    print(f" half1 ({dates[0]}..<{mid}, {n1}d) ${half1:+.2f} (${half1/n1:+.2f}/d) | half2 ({n2}d) ${half2:+.2f} (${half2/n2:+.2f}/d)")
    print(f" best day {best_day} ${d[best_day]:+.2f}; ex-best mean ${exbest:+.2f}")
    print(f" per-entry contribution: " + ", ".join(f"{k}: N={ncontrib[k]} ${v:+.2f}" for k, v in contrib.items()))
    print(" daily:", {k: round(v, 2) for k, v in d.items()})

    json.dump({"dates": dates, "n_files": len(files),
               "h4_trades": [{k: v for k, v in x.items() if k != "xi"} for x in h4],
               "h2_trades_n": len(h2), "deduped": [{k: v for k, v in x.items() if k != "xi"} for x in deduped],
               "skipped": [{k: v for k, v in x.items() if k != "xi"} for x in skipped],
               "daily_h4": d},
              open(os.path.dirname(os.path.abspath(__file__))+"/stress_out.json", "w"), indent=1, default=str)

    # hand-trace helper: find a date with both a dedup drop and a slot skip
    dd_dates = {(x["date"]) for x in deduped}; sk_dates = {(x["date"]) for x in skipped}
    both = sorted(dd_dates & sk_dates)
    print("\ndates with BOTH a dedup drop and a slot skip:", both[:5])

if __name__ == "__main__":
    main()
