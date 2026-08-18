#!/usr/bin/env python3
"""
THE 9/90 UNDER VWAP — TWO RESCUES TESTED (8/18)

Marcos, after the below-VWAP cohort was killed (1,492 fires, 13% win, and distance / slope /
9-20 stack / velocity / volume all FAILED to separate winners from losers, velocity INVERTED):

  "either test the vwap reclaim or this idea under vwap just for crowns"

Both are tested here, on the same cache and the same construction as the wall.

  ARM R — THE RECLAIM (XOS 8/18 is the specimen he sent: the 9 crossed the 90 near $4.26 with
  VWAP at ~$4.45, and the name then RECLAIMED VWAP and ran to $4.54).
    trigger: a 1-min 9/90 up-cross that happens BELOW vwap, and then within RECLAIM_MAX_MIN
             the price CLOSES back above vwap. Entry at the reclaim bar, not at the cross.
    This takes the below-VWAP crosses that EARN their way back and discards the 87% that
    never do — which is exactly the discrimination nothing else could provide.

  ARM C — CROWNS ONLY (the leader-meritocracy rule, "to the winners go the extra bullets").
    The live crown is a runtime object; on the tape it is approximated by the same conditions
    the bot crowns on: day gain >= CROWN_GAIN from the session open AND the name at/near fresh
    session highs at the cross. Below-VWAP crosses on crowned names only.
    APPROXIMATION IS DISCLOSED: this is a tape stand-in for a live registry, so a positive
    result here is a REASON TO INSTRUMENT, not a reason to ship.

  Controls carried from the wall so the comparison is honest:
    ABOVE-vwap cross (the shipped lane) and RAW below-vwap (the population being rescued).

Stop: 5-min swing low. Exit: lose-VWAP (the measured winner) — except ARM R, where losing VWAP
IS the entry condition's mirror, so it uses the same rule from the reclaim forward.

PRE-REGISTERED (before the run):
  An arm RESCUES the below-VWAP population only if $/trade > 0 AND n >= 100 AND green days
  >= 40%. Anything else: the below-VWAP cohort stays dead and the lane keeps its VWAP condition.
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
S, E = P.S, P.E
MKT, SLIP = 0.005, 0.01
RECLAIM_MAX_MIN = 30
CROWN_GAIN = 0.40
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


def sim(bars, vw, i, stop):
    """enter at bar i, stop-first intrabar, exit on a 1-min close below vwap, else EOD."""
    entry = bars[i]["c"] * (1 + SLIP)
    if stop >= entry:
        return None
    sh = E.POS / entry
    for k in range(i + 1, len(bars)):
        if bars[k]["l"] <= stop:
            return sh * (stop * (1 - MKT) - entry)
        if (k - i) % 6 == 0 and bars[k]["c"] < vw[k]:
            return sh * (bars[k]["c"] * (1 - MKT) - entry)
    return sh * (bars[-1]["c"] * (1 - MKT) - entry)


def run_day(bars):
    c1, i1 = [], []
    for a in range(0, len(bars) - 6 + 1, 6):
        c1.append(bars[a + 5]["c"]); i1.append(a + 5)
    e9, e90 = ema(c1, 9), ema(c1, 90)
    cpv = cv = 0.0
    vw = []
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
        vw.append(cpv / cv if cv else b["c"])
    op = bars[0]["o"]
    out = []
    busy = -1
    for a in range(1, len(i1)):
        i = i1[a]
        if i <= busy or i < 95 or i >= len(bars) - 3:
            continue
        if not (e9[a - 1] <= e90[a - 1] and e9[a] > e90[a]):
            continue
        if not ("13:30:00" <= E.hhmm_b(bars[i]) < "20:00:00"):
            continue
        above = bars[i]["c"] >= vw[i]
        stop_x = min(b["l"] for b in bars[max(0, i - 30):i + 1])
        gain = bars[i]["c"] / max(op, 1e-9) - 1
        sess_hi = max(b["h"] for b in bars[:i + 1])
        crown = (gain >= CROWN_GAIN) and (bars[i]["c"] >= sess_hi * 0.97)
        rec = {"i": i, "above": above, "crown": crown}
        rec["ABOVE"] = sim(bars, vw, i, stop_x) if above else None
        rec["BELOW_raw"] = sim(bars, vw, i, stop_x) if not above else None
        rec["BELOW_crown"] = sim(bars, vw, i, stop_x) if (not above and crown) else None
        # ARM R — the reclaim
        rec["RECLAIM"] = None
        if not above:
            lim = i + RECLAIM_MAX_MIN * 6
            for k in range(i + 1, min(lim, len(bars) - 3)):
                if (k - i) % 6 != 0:
                    continue
                if bars[k]["l"] <= stop_x:
                    break                       # died before it could reclaim
                if bars[k]["c"] >= vw[k]:
                    st_r = min(b["l"] for b in bars[max(0, k - 30):k + 1])
                    rec["RECLAIM"] = sim(bars, vw, k, st_r)
                    break
        busy = len(bars)
        out.append(rec)
    return out


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    rows = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        for r in run_day(bars):
            r["sym"], r["date"] = sym, date
            rows.append(r)
    W("=" * 96)
    W("THE 9/90 UNDER VWAP — RECLAIM vs CROWNS-ONLY")
    W("=" * 96)
    W(f"{len(E.DAYS)} name-days / {len(dates)} dates. crosses: {len(rows)} "
      f"({sum(1 for r in rows if r['above'])} above vwap, "
      f"{sum(1 for r in rows if not r['above'])} below)\n")

    def stat(arm, rs=None):
        rs = rs if rs is not None else rows
        v = [(r["date"], r[arm]) for r in rs if r.get(arm) is not None]
        if not v:
            return None
        d = defaultdict(float)
        for dt, x in v:
            d[dt] += x
        p = [x for _, x in v]
        return {"n": len(p), "tot": sum(p), "per": sum(p) / len(p),
                "win": 100.0 * sum(1 for x in p if x > 0) / len(p),
                "green": 100.0 * sum(1 for x in d.values() if x > 0) / max(len(d), 1)}

    def line(lbl, s):
        if not s:
            W(f"  {lbl:34s} n=0"); return
        W(f"  {lbl:34s} n={s['n']:5d}  total=${s['tot']:+10.2f}  $/tr={s['per']:+7.2f}  "
          f"win={s['win']:4.0f}%  green={s['green']:3.0f}%")

    W("CONTROLS")
    line("ABOVE vwap (the shipped lane)", stat("ABOVE"))
    line("BELOW vwap, raw (the dead pop)", stat("BELOW_raw"))
    W("\nTHE TWO RESCUES")
    line(f"ARM R — reclaim within {RECLAIM_MAX_MIN}m", stat("RECLAIM"))
    line(f"ARM C — below vwap, CROWNS only", stat("BELOW_crown"))

    ho = set(dates[44:])
    W("\nHOLD-OUT (unseen 19 dates)")
    hor = [r for r in rows if r["date"] in ho]
    line("ABOVE vwap", stat("ABOVE", hor))
    line("ARM R — reclaim", stat("RECLAIM", hor))
    line("ARM C — crowns only", stat("BELOW_crown", hor))

    W("\n" + "=" * 96)
    W("PRE-REGISTERED BAR  ($/tr > 0, n >= 100, green >= 40%)")
    W("=" * 96)
    for nm, arm in (("ARM R (reclaim)", "RECLAIM"), ("ARM C (crowns)", "BELOW_crown")):
        s = stat(arm)
        if not s:
            W(f"  FAIL  {nm:20s} no fires"); continue
        ok = s["per"] > 0 and s["n"] >= 100 and s["green"] >= 40
        W(f"  {'PASS' if ok else 'FAIL'}  {nm:20s} ${s['per']:+7.2f}/tr  n={s['n']:4d}  "
          f"green={s['green']:3.0f}%")
    W("\nLIMITS: ARM C's crown is a TAPE APPROXIMATION of a live runtime registry (day gain >= "
      f"{CROWN_GAIN:.0%} + within 3% of session high). A positive result is a reason to")
    W("instrument the real crown flag on fires, NOT a reason to ship. Detector-only, no funnel.")
    json.dump({"out": OUT}, open(HERE + "/ema9x90_reclaim_crown_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
