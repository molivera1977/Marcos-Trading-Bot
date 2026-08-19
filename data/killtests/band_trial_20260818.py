#!/usr/bin/env python3
"""
IGNITION vs THE 9/90 LANE — WHO SHOULD GET THE CAPITAL WHEN BOTH FIRE? (8/18)

Marcos: "are they two separate entries, ignition and 9/90?" then "run the test."

WHAT WE ALREADY KNOW (ignition_vs_x9 overlap census, same cache):
  both fired on 327 name-days · ignition-only 272 · 9/90-only 41
  when both fire, the nearest pair is a median 23.7 min apart; only 25% land within 5 minutes.
So they are SEPARATE ENTRIES that share names. The question this script answers is narrower and
is about MONEY, not taxonomy:

  1. On the days both fire, which lane's fires actually pay?
  2. In the TIGHT window (<= TIGHT_MIN minutes apart) — the same event seen twice — which side
     should win? Today ignition wins by CODE POSITION: it runs `continue` after firing, which
     skips every other detector for that ticker in that scan cycle. That is an arbitrary
     tiebreak, and it applies to ~25% of both-fired days.
  3. Does taking BOTH (they are different moments 75% of the time) beat taking either alone,
     at realistic capacity?

ARMS (identical detector, stop and exits across all of them — only ADMISSION differs)
  IGN_only    ignition fires only
  X9_only     9/90 fires only
  BOTH_all    every fire from both lanes
  BOTH_dedup  every fire, but when two land within TIGHT_MIN minutes on the same name, keep ONE:
              IGN_first  -> ignition wins (today's de-facto behaviour, via the `continue`)
              X9_first   -> the 9/90 fire wins
              EARLIER    -> whichever fired first in clock time

MEASURED THE WAY THAT MATTERS: dollars per day at capacity N (first N fires per day,
chronological — no lookahead, no ranking the future), plus $/trade and green-day rate.
Exits: E3 live-parity via F.sim_var, stop-first intrabar, -1% entry slip, -0.5% exit slip.
Stops: each lane's own (ignition's detector stop; 9/90's 5-min swing low).

PRE-REGISTERED (before the run):
  * "Both" is only better if it beats the best single lane on $/day at N=6 AND N=8.
  * The tight-window tiebreak is only DECIDED if one side beats the other by >= $15/day at N=6;
    otherwise it is a coin-flip and the `continue` stays until something better is measured.
  * Chronological split, last 19 dates unseen. Full sample AND hold-out reported, always.

LIMITS: detector-only. No funnel, no chart gate, no capital reservation, no priority sort —
so absolute levels overstate what the live bot can take. Read the COMPARISON between arms.
Nothing ships from this script.
"""
import importlib.util
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TIGHT_MIN = 5.0


def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


P = _load("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
H = _load("H", HERE + "/live_harness.py")
S, E, F = P.S, P.E, P.F
OUT = []


def W(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def ema(v, n):
    k = 2.0 / (n + 1)
    e = None
    o = []
    for x in v:
        e = x if e is None else (x - e) * k + e
        o.append(e)
    return o


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    fires = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        raw = [{"time": b["t"], "open": b["o"], "high": b["h"],
                "low": b["l"], "close": b["c"], "volume": b["v"]} for b in bars]
        cpv = cv = 0.0
        vw = []
        for b in bars:
            tp = (b["h"] + b["l"] + b["c"]) / 3.0
            cpv += tp * b["v"]; cv += b["v"]
            vw.append(cpv / cv if cv else b["c"])
        # ignition
        try:
            ig = H.replay(sym, raw, ["ignition10s"], day=date, batch_secs=60)
        except Exception:
            ig = []
        for f in ig:
            i, px = f.get("i"), (f.get("px") or f.get("price"))
            st = f.get("stop") or f.get("zone_stop") or f.get("would_stop")
            if i is None or not px or not st or float(st) >= float(px):
                continue
            i = int(i)
            if i >= len(bars) - 2:
                continue
            try:
                pnl, _, _ = F.sim_var(bars, emas, gaps, i, float(px), float(st),
                                      "E3", "ignition", halt_rule=True)
            except Exception:
                continue
            _g = (bars[i]["c"] / max(bars[0]["o"], 1e-9) - 1) * 100.0
            fires.append({"sym": sym, "date": date, "i": i, "lane": "IGN", "pnl": pnl, "gain": _g})
        # 9/90
        c1, i1 = [], []
        for a in range(0, len(bars) - 5, 6):
            c1.append(bars[a + 5]["c"]); i1.append(a + 5)
        e9, e90 = ema(c1, 9), ema(c1, 90)
        for a in range(1, len(i1)):
            i = i1[a]
            if i < 95 or i >= len(bars) - 3:
                continue
            if not (e9[a - 1] <= e90[a - 1] and e9[a] > e90[a] and bars[i]["c"] >= vw[i]):
                continue
            stop = min(b["l"] for b in bars[max(0, i - 30):i + 1])
            entry = bars[i]["c"] * 1.01
            if stop >= entry:
                continue
            sh = E.POS / entry
            pnl = None
            for k in range(i + 1, len(bars)):
                if bars[k]["l"] <= stop:
                    pnl = sh * (stop * 0.995 - entry); break
                if (k - i) % 6 == 0 and bars[k]["c"] < vw[k]:
                    pnl = sh * (bars[k]["c"] * 0.995 - entry); break
            if pnl is None:
                pnl = sh * (bars[-1]["c"] * 0.995 - entry)
            _g = (bars[i]["c"] / max(bars[0]["o"], 1e-9) - 1) * 100.0
            fires.append({"sym": sym, "date": date, "i": i, "lane": "X9", "pnl": pnl, "gain": _g})

    W("=" * 100)
    W("IGNITION vs THE 9/90 LANE — capital arbitration when both fire")
    W("=" * 100)
    n_ig = sum(1 for f in fires if f["lane"] == "IGN")
    n_x9 = sum(1 for f in fires if f["lane"] == "X9")
    W(f"fires graded: ignition {n_ig}   9/90 {n_x9}   ({len(dates)} dates)\n")

    def dedup(rs, rule):
        by = defaultdict(list)
        for r in rs:
            by[(r["sym"], r["date"])].append(r)
        out = []
        for k, v in by.items():
            v = sorted(v, key=lambda z: z["i"])
            kept = []
            for r in v:
                clash = [q for q in kept if abs(q["i"] - r["i"]) * 10 / 60.0 <= TIGHT_MIN]
                if not clash:
                    kept.append(r); continue
                q = clash[0]
                if rule == "EARLIER":
                    continue                      # q fired first, keep it
                if rule == "IGN_first":
                    if r["lane"] == "IGN" and q["lane"] == "X9":
                        kept.remove(q); kept.append(r)
                elif rule == "X9_first":
                    if r["lane"] == "X9" and q["lane"] == "IGN":
                        kept.remove(q); kept.append(r)
            out += kept
        return out

    ARMS = {
        "IGN_only":            [f for f in fires if f["lane"] == "IGN"],
        "X9_only":             [f for f in fires if f["lane"] == "X9"],
        "BOTH_all":            fires,
        "BOTH_dedup IGNwins":  dedup(fires, "IGN_first"),
        "BOTH_dedup X9wins":   dedup(fires, "X9_first"),
        "BOTH_dedup EARLIER":  dedup(fires, "EARLIER"),
    }
    ho = set(dates[44:])

    def stat(rs):
        if not rs:
            return None
        p = [r["pnl"] for r in rs]
        d = defaultdict(float)
        for r in rs:
            d[r["date"]] += r["pnl"]
        return {"n": len(p), "tot": sum(p), "per": sum(p) / len(p),
                "win": 100.0 * sum(1 for x in p if x > 0) / len(p),
                "green": 100.0 * sum(1 for x in d.values() if x > 0) / max(len(d), 1)}

    W("HOLD-OUT (unseen 19 dates)")
    for k, v in ARMS.items():
        s = stat([r for r in v if r["date"] in ho])
        if s:
            W(f"  {k:22s} n={s['n']:5d}  total=${s['tot']:+10.2f}  $/tr={s['per']:+7.2f}  "
              f"win={s['win']:4.0f}%  green={s['green']:3.0f}%")

    # ── 8/18 (Marcos: "run it with priority sort"). The chronological version was unfair:
    # the 9/90 lane cannot fire before ~11:00 ET (it needs 90 one-minute bars to arm), so
    # ignition filled every early slot by EXISTING EARLIER rather than by being better.
    # This allocates the day's N slots the way the LIVE bot now does, as shipped 8/18:
    #     expectancy band (measured lanes first) -> Move % desc -> expectancy -> tier
    # LANE_EXPECTANCY as shipped: ignition = None (unmeasured, band 1); ema9x90 = +22.33 (band 0).
    # So the 9/90 fires outrank ignition fires, and within a band the bigger mover wins.
    # ── 8/18 (Marcos: "test the band"). The expectancy BAND shipped at 12:45 today on a
    # reasoning argument — "proven lanes get capital before unproven ones" — and has never been
    # measured. Five allocation rules, same fires, same exits. If the band is real it should
    # beat plain Move% and plain clock order. If it is not, it comes out tonight.
    EXP = {"IGN": None, "X9": 22.33}
    def _band(r):
        e = EXP.get(r["lane"])
        return 1 if e is None else (0 if e > 0 else 2)
    RULES = {
        "BAND->move% (SHIPPED)": lambda r: (_band(r), -r.get("gain", 0.0), r["i"]),
        "move% only":            lambda r: (-r.get("gain", 0.0), r["i"]),
        "clock only":            lambda r: (r["i"],),
        "BAND->clock":           lambda r: (_band(r), r["i"]),
        "move%->BAND":           lambda r: (-r.get("gain", 0.0), _band(r), r["i"]),
    }
    W("\n" + "=" * 100)
    W("THE BAND ON TRIAL — same fires, five allocation rules, dollars/day at N=6 (hold-out)")
    W("=" * 100)
    W(f"  {'allocation rule':24s}" + "".join(f"{a:>22s}" for a in ("IGN_only", "X9_only", "BOTH_all")))
    for rn, rf in RULES.items():
        cells = []
        for an in ("IGN_only", "X9_only", "BOTH_all"):
            byday = defaultdict(list)
            for r in [r for r in ARMS[an] if r["date"] in ho]:
                byday[r["date"]].append(r)
            tot = sum(sum(x["pnl"] for x in sorted(vv, key=rf)[:6]) for vv in byday.values())
            cells.append(f"${tot/max(len(ho),1):+10.2f}")
        W(f"  {rn:24s}" + "".join(f"{c:>22s}" for c in cells))
    W("\n  Read the BOTH_all column: that is the only one where the band can matter, because it")
    W("  is the only arm holding fires from more than one lane.")

    def prio(r):
        e = EXP.get(r["lane"])
        band = 1 if e is None else (0 if e > 0 else 2)
        return (band, -r.get("gain", 0.0), -(e or 0.0), r["i"])

    W("\nCAPACITY — dollars per day, N slots allocated by the LIVE PRIORITY SORT (hold-out)")
    W(f"  {'arm':22s}" + "".join(f"{('N='+str(n)):>13s}" for n in (4, 6, 8)) + f"{'fires/day':>11s}")
    pri = {}
    for k, v in ARMS.items():
        byday = defaultdict(list)
        for r in [r for r in v if r["date"] in ho]:
            byday[r["date"]].append(r)
        cells, vals = [], {}
        for n in (4, 6, 8):
            tot = sum(sum(x["pnl"] for x in sorted(vv, key=prio)[:n]) for vv in byday.values())
            vals[n] = tot / max(len(ho), 1)
            cells.append(f"${vals[n]:+10.2f}")
        pri[k] = vals
        fpd = sum(len(vv) for vv in byday.values()) / max(len(ho), 1)
        W(f"  {k:22s}" + "".join(f"{c:>13s}" for c in cells) + f"{fpd:>11.1f}")

    W("\nCAPACITY — same, but CHRONOLOGICAL (the unfair proxy, kept for comparison)")
    W(f"  {'arm':22s}" + "".join(f"{('N='+str(n)):>13s}" for n in (4, 6, 8)) + f"{'fires/day':>11s}")
    perday = {}
    for k, v in ARMS.items():
        byday = defaultdict(list)
        for r in sorted([r for r in v if r["date"] in ho], key=lambda z: (z["date"], z["i"])):
            byday[r["date"]].append(r)
        cells, vals = [], {}
        for n in (4, 6, 8):
            tot = sum(sum(x["pnl"] for x in vv[:n]) for vv in byday.values())
            vals[n] = tot / max(len(ho), 1)
            cells.append(f"${vals[n]:+10.2f}")
        perday[k] = vals
        fpd = sum(len(vv) for vv in byday.values()) / max(len(ho), 1)
        W(f"  {k:22s}" + "".join(f"{c:>13s}" for c in cells) + f"{fpd:>11.1f}")

    W("\n" + "=" * 100)
    W("PRE-REGISTERED VERDICT")
    W("=" * 100)
    perday = pri     # judge on the PRIORITY-SORTED allocation, not the clock proxy
    best_single = max(perday["IGN_only"][6], perday["X9_only"][6])
    both_best = max(perday[k][6] for k in ARMS if k.startswith("BOTH"))
    both_best8 = max(perday[k][8] for k in ARMS if k.startswith("BOTH"))
    ok_both = both_best > best_single and both_best8 > max(perday["IGN_only"][8], perday["X9_only"][8])
    W(f"  best SINGLE lane @N=6: ${best_single:+.2f}/day   best BOTH arm @N=6: ${both_best:+.2f}/day")
    W(f"  {'PASS' if ok_both else 'FAIL'}  running BOTH lanes beats the best single lane at N=6 AND N=8")
    d = perday["BOTH_dedup IGNwins"][6] - perday["BOTH_dedup X9wins"][6]
    W(f"\n  tight-window ({TIGHT_MIN:.0f} min) tiebreak: IGNwins ${perday['BOTH_dedup IGNwins'][6]:+.2f}/day "
      f"vs X9wins ${perday['BOTH_dedup X9wins'][6]:+.2f}/day  (Δ ${d:+.2f})")
    if abs(d) >= 15:
        W(f"  => DECIDED: {'ignition' if d > 0 else 'the 9/90 lane'} should win the tight window.")
    else:
        W("  => NOT DECIDED (|Δ| < $15/day). The `continue` stays; neither side earned the tiebreak.")
    W("\nLIMITS: detector-only, no funnel/chart gate/capital reservation. Compare arms, not levels.")
    json.dump({"out": OUT}, open(HERE + "/ignition_vs_x9_overlap_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
