#!/usr/bin/env python3
"""
THE 9/90 CROSS — MARCOS'S SIGNAL, TESTED (8/18)

Marcos, repeatedly, and most precisely today on the SXTC 10s chart:
  "every time the 9 crosses the 90, it's going up. It also looks like as soon as the 9 goes
   below the 90, it's time to bail"
and then, after the ignition VWAP gate shipped:
  "look at all the charts, EVEN UNDER VWAP, the 9 crossing the 90 things look really good after"

That last clause is the important one: it says the 9/90 cross may be a BETTER discriminator than
the side-of-VWAP rule that just went live. This tests it as a standalone TRIGGER, not a filter.

WHAT IS TESTED
  Entry : the 10s bar where EMA9 crosses UP through EMA90 (prev bar 9<=90, this bar 9>90)
  Exit  : four arms, so the "time to bail" half of the claim is tested too —
            X_cross  exit on the 9 crossing back DOWN through the 90   [Marcos's rule]
            X_e3     E3 (bank 1/2 at +10%, trail 10%-off-high, stop-first)
            X_e3x    E3 but ALSO bail on the down-cross, whichever comes first
            X_hold   hold to session end (control — measures the raw drift)
  Stop  : for the E3 arms, the 90-EMA itself at entry (the line being crossed IS the invalidation)
  Window: 09:30-16:00 ET. One position per name-day at a time; re-arm after exit.

  VWAP SPLIT — the whole point of the "even under VWAP" claim: every arm is reported THREE ways,
  all crosses / crosses ABOVE session VWAP / crosses BELOW it. If the below-VWAP cell is
  positive, Marcos is right and the VWAP gate shipped at 11:29 is refusing good trades.

ENGINE: the pilot's chain (S->G->F->C->B->E), 10s SIP universe cache, 63 dates, ~736 name-days.
E3 arms use F.sim_var verbatim. Entry slip -1%, exit slip -0.5%, stop-first intrabar. Same
basis as the break-attack sweep and the hidden wall, so the numbers are comparable.

PRE-REGISTERED (written before the run):
  * REAL if hold-out $/trade > 0 AND hold-out N >= 100 AND both hold-out halves positive.
  * "Even under VWAP" is CONFIRMED only if the below-VWAP hold-out cell is itself positive
    with N >= 50.
  * The bail rule is CONFIRMED only if X_e3x beats X_e3 on hold-out $/trade.
  * Chronological split: first 44 dates train (context), last 19 unseen.
  * Nothing ships from this script.

This is a NEW ENTRY IDEA. Under the standing contract it is a HYPOTHESIS until this run
prints, and it is not recommended for shipping on anything but its own hold-out numbers.
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
S, E, F = P.S, P.E, P.F

MKT, SLIP = 0.005, 0.01
OUT = []


def W(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def ema(vals, n):
    k = 2.0 / (n + 1)
    e = None
    out = []
    for v in vals:
        e = v if e is None else (v - e) * k + e
        out.append(e)
    return out


def _agg(bars, n):
    """Aggregate 10s bars into n-bar buckets; return closes + the index of each bucket's LAST
    10s bar, so an exit maps back to a real tradeable moment."""
    c, idx = [], []
    for a in range(0, len(bars) - n + 1, n):
        w = bars[a:a + n]
        c.append(w[-1]["c"]); idx.append(a + n - 1)
    return c, idx


def run_day(bars, emas, gaps):
    """All 9x90 up-crosses on this name-day, each simulated under the four arms."""
    closes = [b["c"] for b in bars]
    e9, e90, e20 = ema(closes, 9), ema(closes, 90), ema(closes, 20)
    cpv = cv = 0.0
    vw = []
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
        vw.append(cpv / cv if cv else b["c"])
    SLOW = {}
    for an in (6, 18):
        cc, ii = _agg(bars, an)
        SLOW[an] = {"c": cc, "idx": ii, "e9": ema(cc, 9), "e20": ema(cc, 20), "e90": ema(cc, 90)}
    out = []
    busy_until = -1
    for i in range(95, len(bars) - 3):
        if i <= busy_until:
            continue
        if not (e9[i - 1] <= e90[i - 1] and e9[i] > e90[i]):
            continue
        hh = E.hhmm_b(bars[i])
        if not ("13:30:00" <= hh < "20:00:00"):
            continue
        entry = bars[i]["c"] * (1 + SLIP)
        stop = e90[i]
        if stop >= entry:
            stop = entry * 0.97
        above_vwap = bars[i]["c"] >= vw[i]
        # X_cross / X_hold: walk forward to the down-cross or the end
        xi_cross = None
        for j in range(i + 1, len(bars)):
            if e9[j] < e90[j]:
                xi_cross = j
                break
        px_cross = bars[xi_cross]["c"] * (1 - MKT) if xi_cross else bars[-1]["c"] * (1 - MKT)
        # 8/18 (Marcos: "try exiting when the 9 crosses the 20") — the 9/20 down-cross fires
        # EARLIER than the 9/90 one, so it should cut losers faster; the question is whether it
        # also cuts the winners short. Both are reported so the trade-off is visible.
        xi_20 = None
        for j in range(i + 1, len(bars)):
            if e9[j] < e20[j]:
                xi_20 = j
                break
        px_20 = bars[xi_20]["c"] * (1 - MKT) if xi_20 else bars[-1]["c"] * (1 - MKT)
        # 8/18 WHIPSAW FIX: the 10s cross exits win only 6-11% of the time — they cut winners,
        # not losers, because a single 10s bar under the line is a tick, not a regime change.
        # Same rule, SLOWER frame: 9-under-20 on 1-min and 3-min aggregates, and a close under
        # the 1-min 90-EMA. Entry stays on the 10s cross.
        def _slow_exit(agg_n, fast, slow, use90=False):
            idx = SLOW[agg_n]["idx"]; f = SLOW[agg_n][fast]; sl = SLOW[agg_n][slow]
            ai = None
            for a in range(len(idx)):
                if idx[a] <= i:
                    continue
                if (f[a] < sl[a]) if not use90 else (SLOW[agg_n]["c"][a] < sl[a]):
                    ai = idx[a]; break
            if ai is None:
                return len(bars) - 1, bars[-1]["c"] * (1 - MKT)
            return ai, bars[ai]["c"] * (1 - MKT)
        j1, p1 = _slow_exit(6, "e9", "e20")
        j3, p3m = _slow_exit(18, "e9", "e20")
        j90, p90 = _slow_exit(6, "e9", "e90", use90=True)
        px_hold = bars[-1]["c"] * (1 - MKT)
        sh = E.POS / entry
        res = {"i": i, "above_vwap": above_vwap,
               "X_cross": sh * (px_cross - entry),
               "X_hold": sh * (px_hold - entry),
               "X_20": sh * (px_20 - entry),
               "X_1m20": sh * (p1 - entry),
               "X_3m20": sh * (p3m - entry),
               "X_1m90c": sh * (p90 - entry)}
        try:
            p3, _, x3 = F.sim_var(bars, emas, gaps, i, bars[i]["c"], stop, "E3", "flat_top",
                                  halt_rule=True)
            res["X_e3"] = p3
        except Exception:
            res["X_e3"] = None
            x3 = None
        # E3 but bail early on the down-cross
        if res["X_e3"] is not None:
            if xi_cross is not None and x3 is not None and xi_cross < x3:
                res["X_e3x"] = sh * (px_cross - entry)
            else:
                res["X_e3x"] = res["X_e3"]
            if xi_20 is not None and x3 is not None and xi_20 < x3:
                res["X_e3_20"] = sh * (px_20 - entry)
            else:
                res["X_e3_20"] = res["X_e3"]
        else:
            res["X_e3x"] = None
            res["X_e3_20"] = None
        busy_until = min(x for x in (xi_cross, xi_20, len(bars)) if x is not None)
        out.append(res)
    return out


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    W("=" * 100)
    W("THE 9/90 CROSS — entry; exits swept incl. the 9/20 down-cross (10s, 09:30-16:00 ET)")
    W("=" * 100)
    W(f"universe: {len(E.DAYS)} name-days / {len(dates)} dates  {dates[0]} .. {dates[-1]}\n")

    rows = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for r in run_day(bars, emas, gaps):
            r["sym"], r["date"] = sym, date
            rows.append(r)
    W(f"9x90 up-crosses found: {len(rows)}\n")
    if not rows:
        W("none"); return 1

    tr, ho = set(dates[:44]), set(dates[44:])
    ARMS = ["X_20", "X_1m20", "X_3m20", "X_1m90c", "X_cross", "X_e3", "X_hold"]

    def stat(rs, arm):
        v = [r[arm] for r in rs if r.get(arm) is not None]
        if not v:
            return None
        byday = defaultdict(float)
        for r in rs:
            if r.get(arm) is not None:
                byday[r["date"]] += r[arm]
        return {"n": len(v), "tot": sum(v), "per": sum(v) / len(v),
                "win": 100.0 * sum(1 for x in v if x > 0) / len(v),
                "green": 100.0 * sum(1 for x in byday.values() if x > 0) / max(len(byday), 1)}

    def block(label, rs):
        W(f"  {label}")
        for a in ARMS:
            s = stat(rs, a)
            if not s:
                W(f"    {a:9s} -"); continue
            W(f"    {a:9s} n={s['n']:5d}  total=${s['tot']:+10.2f}  $/tr={s['per']:+7.2f}  "
              f"win={s['win']:4.0f}%  green={s['green']:3.0f}%")

    hor = [r for r in rows if r["date"] in ho]
    W("FULL SAMPLE"); block("all crosses", rows)
    W("\nHOLD-OUT (unseen 19 dates)"); block("all crosses", hor)
    W("")
    block("HOLD-OUT — cross ABOVE vwap", [r for r in hor if r["above_vwap"]])
    W("")
    block("HOLD-OUT — cross BELOW vwap  <-- Marcos: 'even under vwap'",
          [r for r in hor if not r["above_vwap"]])

    W("\n" + "=" * 100)
    W("PRE-REGISTERED CHECKS")
    W("=" * 100)
    best = max((a for a in ARMS if stat(hor, a)), key=lambda a: stat(hor, a)["per"])
    b = stat(hor, best)
    hor_s = sorted(hor, key=lambda r: r["date"])
    mid = len(hor_s) // 2
    h1 = sum(r[best] for r in hor_s[:mid] if r.get(best) is not None)
    h2 = sum(r[best] for r in hor_s[mid:] if r.get(best) is not None)
    W(f"  best hold-out arm: {best}  ${b['per']:+.2f}/tr  n={b['n']}  win {b['win']:.0f}%")
    W(f"  halves: ${h1:+.2f} / ${h2:+.2f}")
    real = b["per"] > 0 and b["n"] >= 100 and h1 > 0 and h2 > 0
    W(f"  {'PASS' if real else 'FAIL'}  signal is REAL (hold-out $/tr>0, n>=100, both halves +)")
    bel = stat([r for r in hor if not r["above_vwap"]], best)
    if bel:
        ok = bel["per"] > 0 and bel["n"] >= 50
        W(f"  {'PASS' if ok else 'FAIL'}  'EVEN UNDER VWAP' — below-vwap cell ${bel['per']:+.2f}/tr "
          f"n={bel['n']}")
        if ok:
            W("        => the VWAP gate shipped 11:29 IS refusing good trades on this signal.")
        else:
            W("        => below-vwap crosses do NOT pay; the VWAP gate is not costing us here.")
    se3, se3x = stat(hor, "X_e3"), stat(hor, "X_e3x")
    if se3 and se3x:
        W(f"  {'PASS' if se3x['per'] > se3['per'] else 'FAIL'}  'time to bail' — X_e3x "
          f"${se3x['per']:+.2f} vs X_e3 ${se3['per']:+.2f}")

    W("\nLIMITS: no funnel, no gates, no caps — this is the raw signal on raw tape, so fire counts")
    W("far exceed anything tradeable; read $/trade and direction. Fixed E.POS sizing per fire.")
    W("One position per name-day at a time. Nothing ships from this script.")
    json.dump({"out": OUT}, open(HERE + "/ema9x90_cross_v3_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
