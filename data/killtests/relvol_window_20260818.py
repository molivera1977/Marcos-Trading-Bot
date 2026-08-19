#!/usr/bin/env python3
"""
IGNITION: THE DAY-GAIN FLOOR ON TRIAL — 8/18

Marcos: "we need to try a different gate for ignition."

THE CONTRADICTION BEING TESTED
  `DAYGAIN_FLOOR = 15%` blocks ignition (and flat_top/ma_pullback/orb/ema_bounce) on any name
  not already up 15% on the day. Ignition's own definition is "volume surge off a QUIET BASE,
  breaking out, NOT YET EXTENDED" — it exists to catch the move BEFORE the gain exists. The
  floor therefore refuses the lane for doing its job.

  Measured on 8/18 (lane-attributed refusal rows, the stamps shipped that morning): 23 refusals
  carried lane=ignition and **14 of them (61%) were daygain_reject** — HAO at 1.72% day gain,
  AIFU 1.86%, FCUV 8.63%, FGI 9.91%, RCON 10.38%, OFAL 13.64%. Every one refused for being early.

ARMS (detector held FIXED — the bot's own ignition_10s_step via live_harness, batch_secs=60)
  A_floor15   day gain >= 15% at the fire        [CONTROL = today's live behavior]
  A_nofloor   no day-gain condition at all       (the lane's own gates only)
  A_floor5    day gain >= 5%                     (a softer floor, in case the idea is right
                                                  and only the number is wrong)
  A_relvol2   REPLACE the floor with RELATIVE VOLUME: the fire bar's 1-min volume >= 2x the
              name's own trailing 30-min average. This measures IGNITION rather than HISTORY —
              it asks "is this surge big for THIS name right now", which is the question the
              day-gain floor is a bad proxy for.
  A_relvol3   same at 3x

  Note: the harness detector already enforces ignition's own thesis (quiet base, volume
  acceleration, not-extended). These arms only vary the ADMISSION gate applied on top of it.

EXITS/SIZING: E3 live-parity (F.sim_var, halt_rule=True) — bank 1/2 at +10%, trail the rest
10%-off-run-high closes-through, stop-first INTRABAR, -1% chase entry, -0.5% market-exit slip.
Stop = the detector's own stop. Identical across arms, so the comparison isolates the gate.

PRE-REGISTERED (written before the run):
  * The floor is REFUTED for ignition only if a no-floor or replacement arm beats A_floor15 on
    HOLD-OUT $/trade AND carries hold-out N >= 60.
  * If A_floor15 wins, the floor STAYS and this document says so plainly.
  * Chronological split: earliest 44 dates train (context only — nothing is fitted), last 19
    unseen. Reported: full sample AND hold-out, both, always.
  * A gate that merely reduces N without improving $/trade is NOT an improvement.

LIMITS: detector-only. The live funnel (scanner board membership, slots, capital, the chart
gate, the 8/18 VWAP+9/20 conditions) sits upstream and is NOT modelled, so fire counts exceed
what the live bot takes. Read $/trade and direction. Nothing ships from this script.
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
OUT = []


def W(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    W("=" * 98)
    W("IGNITION — THE DAY-GAIN FLOOR ON TRIAL   (detector fixed, admission gate swapped)")
    W("=" * 98)
    W(f"universe {len(E.DAYS)} name-days / {len(dates)} dates  {dates[0]} .. {dates[-1]}\n")

    fires = []
    errs = defaultdict(int)
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        raw = [{"time": b["t"], "open": b["o"], "high": b["h"],
                "low": b["l"], "close": b["c"], "volume": b["v"]} for b in bars]
        try:
            fs = H.replay(sym, raw, ["ignition10s"], day=date, batch_secs=60)
        except Exception as e:
            errs[type(e).__name__] += 1
            continue
        if not fs:
            continue
        op = bars[0]["o"]
        for f in fs:
            i = f.get("i")
            px = f.get("px") or f.get("price")
            st = f.get("stop") or f.get("zone_stop") or f.get("would_stop")
            if i is None or not px or not st:
                errs["unusable"] += 1
                continue
            i = int(i)
            if i >= len(bars) - 2 or float(st) >= float(px):
                errs["bad_stop"] += 1
                continue
            gain = (bars[i]["c"] / max(op, 1e-9) - 1) * 100.0
            # 8/18 (Marcos: "which relvol number did we test" -> "test it"). The SCANNER's REL VOL
            # is a MULTI-DAY same-time-of-day baseline and is NOT computable here: only 152 of 738
            # name-days have even 2 prior dates for the same ticker (248 tickers appear once). So
            # the baseline WINDOW is swept instead — same numerator, four denominators — to learn
            # whether "unusual volume" is best measured over 30 min, an hour, or the session.
            v1 = sum(b["v"] for b in bars[max(0, i - 6):i + 1])
            def _rv(mins_back):
                nb = mins_back * 6
                lo = max(0, i - nb)
                span = (i - 6) - lo
                if span <= 0: return 0.0
                base = sum(b["v"] for b in bars[lo:i - 6]) / (span / 6.0)
                return (v1 / base) if base > 0 else 0.0
            rv = _rv(30)
            rv60, rv90 = _rv(60), _rv(90)
            _sess = bars[:max(1, i - 6)]
            _sb = (sum(b["v"] for b in _sess) / max(len(_sess) / 6.0, 1e-9)) if _sess else 0.0
            rvs = (v1 / _sb) if _sb > 0 else 0.0
            _op = bars[:min(len(bars), 180)]
            _ob = (sum(b["v"] for b in _op) / 30.0) if _op else 0.0
            rvo = (v1 / _ob) if _ob > 0 else 0.0
            try:
                pnl, ex, xi = F.sim_var(bars, emas, gaps, i, float(px), float(st),
                                        "E3", "ignition", halt_rule=True)
            except Exception:
                errs["sim"] += 1
                continue
            fires.append({"sym": sym, "date": date, "pnl": pnl, "gain": gain, "relvol": rv,
                          "rv60": rv60, "rv90": rv90, "rvs": rvs, "rvo": rvo})
    W(f"ignition fires graded: {len(fires)}   skipped: {dict(errs) or 'none'}\n")
    if not fires:
        W("NO FIRES — cannot report."); return 1

    # 8/18 (Marcos: "some floor is important but relvol is the real decider") — test the
    # COMBINATION. Hypothesis: a small day-gain floor filters out dead names, and relative
    # volume identifies which of the live ones are actually igniting. Neither alone was best.
    ARMS = {
        "floor15 (CONTROL)":    lambda r: r["gain"] >= 15.0,
        "floor5 only":          lambda r: r["gain"] >= 5.0,
        "relvol2 only":         lambda r: r["relvol"] >= 2.0,
        "relvol3 only":         lambda r: r["relvol"] >= 3.0,
        "floor3 + relvol2":     lambda r: r["gain"] >= 3.0 and r["relvol"] >= 2.0,
        "floor5 + relvol2":     lambda r: r["gain"] >= 5.0 and r["relvol"] >= 2.0,
        "floor5 + relvol3":     lambda r: r["gain"] >= 5.0 and r["relvol"] >= 3.0,
        "floor5 + relvol4":     lambda r: r["gain"] >= 5.0 and r["relvol"] >= 4.0,
        "floor8 + relvol3":     lambda r: r["gain"] >= 8.0 and r["relvol"] >= 3.0,
        "floor10 + relvol2":    lambda r: r["gain"] >= 10.0 and r["relvol"] >= 2.0,
        "floor3 + rv60 >=2":    lambda r: r["gain"] >= 3.0 and r["rv60"] >= 2.0,
        "floor3 + rv90 >=2":    lambda r: r["gain"] >= 3.0 and r["rv90"] >= 2.0,
        "floor3 + rvSESSION>=2": lambda r: r["gain"] >= 3.0 and r["rvs"] >= 2.0,
        "floor3 + rvOPEN30 >=2": lambda r: r["gain"] >= 3.0 and r["rvo"] >= 2.0,
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

    def line(lbl, s):
        if not s:
            W(f"  {lbl:22s} n=0"); return
        W(f"  {lbl:22s} n={s['n']:5d}  total=${s['tot']:+10.2f}  $/tr={s['per']:+7.2f}  "
          f"win={s['win']:4.0f}%  green={s['green']:3.0f}%")

    W("FULL SAMPLE")
    for k, fn in ARMS.items():
        line(k, stat([r for r in fires if fn(r)]))
    W(f"\nHOLD-OUT (unseen {len(ho)} dates)")
    res = {}
    for k, fn in ARMS.items():
        s = stat([r for r in fires if fn(r) and r["date"] in ho])
        res[k] = s
        line(k, s)

    # ── 8/18 CAPACITY TEST (Marcos: "look at the total dollars"). $/trade was the wrong metric:
    # the goal is $50/DAY on ~$3,000, not the best average trade. A gate that admits 1.6 fires a
    # day leaves the machine idle; one that admits 46 is capped by capital, not by the gate. So:
    # take the first N fires PER DAY under each gate (chronological — no lookahead, no ranking
    # the future) and report DOLLARS PER DAY at realistic capacity.
    W("\n" + "=" * 98)
    W("CAPACITY TEST — first N fires per day, chronological. DOLLARS PER DAY (hold-out)")
    W("=" * 98)
    W(f"  {'gate':22s}" + "".join(f"{('N='+str(n)):>13s}" for n in (4, 6, 8, 12)) + f"{'fires/day':>11s}")
    for k, fn in ARMS.items():
        byday = defaultdict(list)
        for r in sorted([r for r in fires if fn(r) and r["date"] in ho], key=lambda z: (z["date"], z["sym"])):
            byday[r["date"]].append(r)
        cells = []
        for n in (4, 6, 8, 12):
            tot = sum(sum(x["pnl"] for x in v[:n]) for v in byday.values())
            cells.append(f"${tot/max(len(ho),1):+10.2f}")
        fpd = sum(len(v) for v in byday.values()) / max(len(ho), 1)
        W(f"  {k:22s}" + "".join(f"{c:>13s}" for c in cells) + f"{fpd:>11.1f}")
    W("\n  (N = positions the book can hold. $3,000 with ~$500 clips ~= 6. Fires/day is what the")
    W("   gate OFFERS; anything above N is capped by capital, not by the gate.)")

    W("\n" + "=" * 98)
    W("PRE-REGISTERED VERDICT")
    W("=" * 98)
    ctl = res["A_floor15  (CONTROL)"]
    if not ctl:
        W("  control has no hold-out fires — inconclusive."); return 0
    W(f"  control (floor 15%): ${ctl['per']:+.2f}/tr  n={ctl['n']}")
    beats = [(k, s) for k, s in res.items()
             if k != "A_floor15  (CONTROL)" and s and s["per"] > ctl["per"] and s["n"] >= 60]
    if beats:
        beats.sort(key=lambda z: -z[1]["per"])
        W(f"\n  {len(beats)} arm(s) BEAT the floor on hold-out with n>=60:")
        for k, s in beats:
            W(f"    {k:22s} ${s['per']:+7.2f}/tr (Δ {s['per']-ctl['per']:+.2f})  n={s['n']:5d}  "
              f"win {s['win']:3.0f}%  green {s['green']:3.0f}%")
        W(f"\n  => THE DAY-GAIN FLOOR IS REFUTED FOR IGNITION. Best replacement: {beats[0][0].strip()}")
    else:
        W("\n  NO arm beat the floor with n>=60 on hold-out.")
        W("  => THE FLOOR STAYS. The contradiction is real in principle but the tape does not")
        W("     pay for removing it, and a principled argument is not a reason to ship.")
    W("\nLIMITS: detector-only, no funnel; fire counts exceed live. E3 exits, detector's own stop.")
    json.dump({"out": OUT}, open(HERE + "/ignition_gate_swap_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
