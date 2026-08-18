#!/usr/bin/env python3
"""
HIDDEN — AFTER-THE-DETECTION SWEEP + THE 9/20 SWITCH (8/18)

Marcos: "Hidden is something that will help us, we need to break the after-the-detection part.
I am not willing to throw it away. It sees things that others don't."  And, repeatedly:
"the 9 crossing over the 20 is the big switch and we ignore it."

The wall (hidden_wall_20260818) killed hidden as-configured: 6,105 fires, hold-out -$10.21/tr,
69% stopped out. But that graded ONE construction — the detector's own stop, E3 exits. It does
NOT separate "the eyes are bad" from "what we do after the eyes is bad."

This script holds the DETECTIONS FIXED (the same fires, the bot's own hidden_entry_step via
live_harness) and sweeps everything downstream:

  STOP CONSTRUCTION (the prime suspect — 69% stop rate says the stop is inside the noise)
    s_det      the detector's own stop                              [BASELINE = the wall]
    s_1.5x     widen the risk 1.5x from entry
    s_2x       widen the risk 2x
    s_vwap     stop at session VWAP (Kev: lose VWAP = lose the trade)
    s_e20      stop at the 20-EMA of the 10s series

  EXIT CONSTRUCTION
    E3         bank 1/2 at +10%, trail 10%-off-high      [BASELINE]
    E1         bank 1/2 at +4%, trail EMA90
    E4         no bank, pure 10%-off-high trail from entry

  THE 9/20 SWITCH (Marcos's standing claim, never tested on this lane)
    f_none     take every fire                                      [BASELINE]
    f_9over20  ONLY fires where EMA9 > EMA20 at the fire bar
    f_cross    ONLY fires within 30 bars (5 min) AFTER a fresh 9-over-20 cross
    f_9o20_v   EMA9 > EMA20 AND price at/above session VWAP (Kev's two rules together)

Sizing is $1 per share-unit (per-share P&L x shares from the engine's own POS), identical
across arms, so every comparison is like-for-like. Entry slip -1%, market-exit slip -0.5%,
stop-first intrabar — the honest model throughout.

PRE-REGISTERED (written before the run):
  * A construction is a CANDIDATE only if hold-out $/trade > 0 AND hold-out N >= 100.
  * The 9/20 switch is CONFIRMED as an edge on this lane only if f_9over20 (or f_cross)
    lifts hold-out $/trade vs f_none by >= $3.00 AND keeps N >= 100.
  * If NO construction clears, hidden is dead on this tape and the answer is not the exits.
  * Chronological split: earliest 44 dates train (context), last 19 unseen hold-out.

No recommendation. Numbers only.
"""
import importlib.util
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


P = _load("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
H = _load("H", HERE + "/live_harness.py")
S, E, F = P.S, P.E, P.F

MKT = 0.005
ENTRY_SLIP = 0.01
OUT = []


def W(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def ema(vals, n):
    k = 2.0 / (n + 1)
    out = []
    e = None
    for v in vals:
        e = v if e is None else (v - e) * k + e
        out.append(e)
    return out


def vwap_series(bars):
    cpv = cv = 0.0
    out = []
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
        out.append(cpv / cv if cv else b["c"])
    return out


def sim(bars, i0, entry_px, stop, mode):
    """E1/E3/E4 on 10s bars. stop-first intrabar, no lookahead."""
    if stop >= entry_px:
        return None
    cfg = {"E3": (0.50, 0.10, "off10"), "E1": (0.50, 0.04, "ema90"),
           "E4": (None, None, "off10_entry")}[mode]
    bank, tgt, trail = cfg
    rem = 1.0
    pnl = 0.0
    scaled = False
    bank_sh = bank or 0.0
    target = entry_px * (1 + tgt) if tgt else None
    run_hi = entry_px
    e90 = EMA90_CACHE
    for i in range(i0 + 1, len(bars)):
        b = bars[i]
        if b["l"] <= stop:
            px = stop * (1 - MKT); pnl += rem * (px - entry_px)
            return pnl, "stop"
        if target and not scaled and b["h"] >= target:
            pnl += bank_sh * (target - entry_px); rem -= bank_sh; scaled = True
            continue
        run_hi = max(run_hi, b["h"])
        hit = ((trail == "off10" and scaled and b["c"] < run_hi * 0.90) or
               (trail == "off10_entry" and b["c"] < run_hi * 0.90) or
               (trail == "ema90" and scaled and b["c"] < e90[i]))
        if hit:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            return pnl, "trail"
    b = bars[-1]
    px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
    return pnl, "eod"


EMA90_CACHE = []

STOPS = ["s_det", "s_1.5x", "s_2x", "s_vwap", "s_e20"]
EXITS = ["E3", "E1", "E4"]
FILTS = ["f_none", "f_9over20", "f_cross", "f_9o20_v"]


def main():
    global EMA90_CACHE
    S.load_all()
    days = sorted(E.DAYS.items(), key=lambda kv: (kv[0][1], kv[0][0]))
    dates = sorted({d for (_, d) in E.DAYS})
    W("=" * 104)
    W("HIDDEN — AFTER-THE-DETECTION SWEEP + THE 9/20 SWITCH")
    W("=" * 104)
    W(f"universe: {len(days)} name-days / {len(dates)} dates. Detections held FIXED "
      f"(bot's own hidden_entry_step); everything downstream swept.\n")

    fires = []
    for (sym, date), (bars, emas, gaps) in days:
        raw = [{"time": b["t"], "open": b["o"], "high": b["h"],
                "low": b["l"], "close": b["c"], "volume": b["v"]} for b in bars]
        vw = vwap_series(bars)
        try:
            fs = H.replay(sym, raw, ["hidden"],
                          vwap_provider=lambda s, i, b, l, _v=vw: _v[min(i, len(_v) - 1)],
                          day=date, batch_secs=60)
        except Exception:
            continue
        if not fs:
            continue
        closes = [b["c"] for b in bars]
        e9, e20 = ema(closes, 9), ema(closes, 20)
        for f in fs:
            i = f.get("i")
            px = f.get("px") or f.get("price")
            st = f.get("stop") or f.get("would_stop")
            if i is None or not px or not st:
                continue
            i = int(i)
            if i >= len(bars) - 2:
                continue
            # fresh 9-over-20 cross within the last 30 bars (5 min)?
            cross = False
            for j in range(max(1, i - 30), i + 1):
                if e9[j - 1] <= e20[j - 1] and e9[j] > e20[j]:
                    cross = True; break
            fires.append({"sym": sym, "date": date, "i": i, "px": float(px), "stop": float(st),
                          "e9": e9[i], "e20": e20[i], "vwap": vw[i], "cross": cross})
    W(f"detections captured: {len(fires)}\n")
    if not fires:
        W("no fires"); return 1

    by_day = defaultdict(list)
    for f in fires:
        by_day[(f["sym"], f["date"])].append(f)

    tr, ho = set(dates[:44]), set(dates[44:])
    results = {}
    for sm in STOPS:
        for xm in EXITS:
            rows = []
            for key, fl in by_day.items():
                bars, emas, gaps = E.DAYS[key]
                EMA90_CACHE = emas if len(emas) == len(bars) else ema([b["c"] for b in bars], 90)
                vw = vwap_series(bars)
                for f in fl:
                    ep = f["px"] * (1 + ENTRY_SLIP)
                    risk = ep - f["stop"]
                    if risk <= 0:
                        continue
                    stop = {"s_det": f["stop"], "s_1.5x": ep - risk * 1.5,
                            "s_2x": ep - risk * 2.0, "s_vwap": min(f["vwap"], ep * 0.999),
                            "s_e20": min(f["e20"], ep * 0.999)}[sm]
                    if stop >= ep:
                        continue
                    r = sim(bars, f["i"], ep, stop, xm)
                    if not r:
                        continue
                    shares = E.POS / ep
                    rows.append({"date": f["date"], "pnl": r[0] * shares, "why": r[1],
                                 "e9": f["e9"], "e20": f["e20"], "vwap": f["vwap"],
                                 "px": ep, "cross": f["cross"]})
            results[(sm, xm)] = rows

    def sel(rows, filt):
        if filt == "f_none":
            return rows
        if filt == "f_9over20":
            return [r for r in rows if r["e9"] > r["e20"]]
        if filt == "f_cross":
            return [r for r in rows if r["cross"]]
        return [r for r in rows if r["e9"] > r["e20"] and r["px"] >= r["vwap"] * 0.999]

    def stat(rows):
        h = [r for r in rows if r["date"] in ho]
        if not h:
            return None
        p = [r["pnl"] for r in h]
        return {"n": len(p), "tot": sum(p), "per": sum(p) / len(p),
                "win": 100.0 * sum(1 for x in p if x > 0) / len(p)}

    W("HOLD-OUT (unseen 19 dates) — $/trade by construction. BASELINE = s_det / E3 / f_none\n")
    W(f"  {'stop':8s} {'exit':4s} | " + " | ".join(f"{f:>22s}" for f in FILTS))
    base = None
    best = []
    for sm in STOPS:
        for xm in EXITS:
            cells = []
            for fl in FILTS:
                s = stat(sel(results[(sm, xm)], fl))
                if s is None:
                    cells.append(f"{'-':>22s}"); continue
                if sm == "s_det" and xm == "E3" and fl == "f_none":
                    base = s
                cells.append(f"${s['per']:+7.2f} n={s['n']:5d} w{s['win']:3.0f}%")
                if s["per"] > 0 and s["n"] >= 100:
                    best.append((s["per"], sm, xm, fl, s))
            W(f"  {sm:8s} {xm:4s} | " + " | ".join(cells))

    W("\n" + "=" * 104)
    W("PRE-REGISTERED CHECKS")
    W("=" * 104)
    if base:
        W(f"  baseline (the wall): ${base['per']:+.2f}/tr  n={base['n']}  win {base['win']:.0f}%")
    best.sort(reverse=True)
    if not best:
        W("  NO construction clears (hold-out $/tr > 0 AND n >= 100).")
        W("  => Hidden is dead on this tape. The problem is NOT the exits or the 9/20 switch.")
    else:
        W(f"  {len(best)} construction(s) clear hold-out $/tr > 0 with n >= 100:")
        for per, sm, xm, fl, s in best[:8]:
            W(f"    {sm:8s} {xm:4s} {fl:10s}  ${per:+7.2f}/tr  n={s['n']:5d}  "
              f"win {s['win']:3.0f}%  total ${s['tot']:+9.2f}")
    # the 9/20 question, isolated
    W("\n  THE 9/20 SWITCH, isolated (baseline stop+exit, filter varied):")
    for fl in FILTS:
        s = stat(sel(results[("s_det", "E3")], fl))
        if s:
            d = f"  Δ vs f_none {s['per'] - base['per']:+7.2f}" if base and fl != "f_none" else ""
            W(f"    {fl:10s} ${s['per']:+7.2f}/tr  n={s['n']:5d}  win {s['win']:3.0f}%{d}")
    s9 = stat(sel(results[("s_det", "E3")], "f_9over20"))
    if s9 and base:
        lift = s9["per"] - base["per"]
        W(f"\n    9/20 CONFIRMED as an edge on this lane? "
          f"{'YES' if (lift >= 3.0 and s9['n'] >= 100) else 'NO'} "
          f"(bar: lift >= $3.00 and n >= 100; measured lift ${lift:+.2f}, n={s9['n']})")
    W("\nLIMITS: detector-only (no funnel); RTH bars; hidden parity 86.3%; sizing is the")
    W("engine's fixed POS per fire, so totals scale with fire count — read $/trade.")
    json.dump({"out": OUT}, open(HERE + "/hidden_construction_sweep_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
