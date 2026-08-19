#!/usr/bin/env python3
"""
PREMARKET IGNITION, SPLIT BY TAPE COVERAGE — IS THE EDGE REAL OR AN ARTIFACT OF THIN TAPE? (8/18)

Marcos: "this data is suspect anyway. We have always had problems with shadoes, wrong data,
wrong vwap" -> "run the split"

THE WORRY, STATED PRECISELY
  The 07:00-09:25 window holds at most 870 ten-second bars. Measured over 718 name-days:
      coverage vs a full window: median 60.2%, 25th pct 10.9%, 10th pct 1.4%
      largest print-free gap:    median 1.8 min, 90th pct 34.8 min
  A 10s "bar" exists only where a PRINT existed. On thin names the premarket VWAP and the
  "quiet base" that ignition breaks are computed from very few, lumpy prints — so a break of
  a 3-print base is not the same event as a break of a 300-print base, even though the code
  cannot tell them apart. If the measured premarket edge (+$10.89/tr hold-out,
  premarket_bakeoff_20260818) lives in the SPARSE cohort, it is an artifact of thin tape and
  must not be built.

WHAT THIS SPLITS
  Every premarket ignition fire from the bake-off construction, bucketed by the COVERAGE of its
  own name-day's 07:00-09:25 window (share of the 870 possible 10s bars that carry a print):
      Q1  < 25%      (thinnest)
      Q2  25-50%
      Q3  50-75%
      Q4  >= 75%     (densest — closest to RTH-like tape)
  and, separately, by the largest print-free GAP inside the window (<= 5 min vs > 5 min),
  because average coverage can hide a single long blackout.

PRE-REGISTERED (before the run)
  * The edge is REAL AND BUILDABLE only if the DENSE cohorts (Q3+Q4) are positive on hold-out
    $/trade with n >= 25 combined. Dense tape is the cohort we can actually trade.
  * If the edge lives ONLY in Q1/Q2 (thin tape) it is an ARTIFACT — say so and do not build.
  * If BOTH are positive, report the coverage floor that keeps the edge, because that floor
    becomes the lane's eligibility rule, not a number chosen for looking good.
  * A cohort with n < 15 on hold-out is reported but NOT used for a verdict (underpowered).

LIMITS: same as the bake-off — study reimplementation of the detector (the live one refuses
premarket at :7945), detector-only, no premarket board/chart gate/slots. RTH slip model applied
to premarket prints FLATTERS every cohort, and it flatters the THIN cohorts most, since those
are exactly where real spreads blow out. That biases this test TOWARD finding a fake edge in
Q1/Q2 — which is the safe direction for the question being asked. Nothing ships from this.
"""
import importlib.util
import json
import os
import sys
import datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ET = datetime.timezone(datetime.timedelta(hours=-4))
MKT, SLIP = 0.005, 0.01
OPEN_HM, CLOSE_HM = "07:00", "09:25"
SLOTS = 870                      # 145 min of 10s bars
VOL_MULT, MIN_ABS_VOL_10S, STRONG = 2.0, 5000 / 6.0, 0.5
BASE_10S, MIN_EXT, MAX_EXT, STOP_BUF = 24, -0.05, 0.15, 0.003
RELVOL_MIN, DAYGAIN_FLOOR, VWAP_TOL = 2.0, 3.0, 0.02


def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


P = _load("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
S, E = P.S, P.E
OUT = []


def W(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def hmd(t):
    return datetime.datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=datetime.timezone.utc).astimezone(ET)


def ema_last(v, n):
    k = 2.0 / (n + 1)
    e = None
    for x in v:
        e = x if e is None else (x - e) * k + e
    return e


def scan(pre, lo, hi, vw):
    openp = pre[lo]["o"]
    if openp <= 0:
        return None
    c3 = []
    for n in range(lo, hi + 1):
        if (n - lo + 1) % 18 == 0:
            c3.append(pre[n]["c"])
        base = pre[max(lo, n - BASE_10S):n]
        if len(base) < BASE_10S:
            continue
        b = pre[n]
        o, h, l, c, v = b["o"], b["h"], b["l"], b["c"], b["v"]
        if c <= 0:
            continue
        bh = max(x["c"] for x in base)
        lows = [x["l"] for x in base if x["l"] > 0]
        if not lows:
            continue
        bl = min(lows)
        bv = (sum(x["v"] for x in base) / len(base)) or 1
        rng = (h - l) or 1e-9
        ext = (c - openp) / openp
        if not (v >= VOL_MULT * bv and v >= MIN_ABS_VOL_10S and c > o
                and (c - l) / rng >= STRONG and c >= bh and MIN_EXT <= ext <= MAX_EXT):
            continue
        if (c / openp - 1) * 100.0 < DAYGAIN_FLOOR:
            continue
        v1 = sum(x["v"] for x in pre[max(lo, n - 5):n + 1])
        span = max(n - lo, 1)
        avg = sum(x["v"] for x in pre[lo:n]) / max(span / 6.0, 1) if span > 12 else 0
        if avg > 0 and (v1 / avg) < RELVOL_MIN:
            continue
        if vw[n] > 0 and c < vw[n] * (1 - VWAP_TOL):
            continue
        if len(c3) >= 22 and ema_last(c3, 9) < ema_last(c3, 20):
            continue
        stop = bl * (1 - STOP_BUF)
        entry = c * (1 + SLIP)
        if stop >= entry or stop <= 0:
            continue
        sh = E.POS / entry
        pnl = None
        for k in range(n + 1, hi + 1):
            if pre[k]["l"] <= stop:
                pnl = sh * (stop * (1 - MKT) - entry); break
            if (k - n) % 6 == 0 and pre[k]["c"] < vw.get(k, 0):
                pnl = sh * (pre[k]["c"] * (1 - MKT) - entry); break
        if pnl is None:
            pnl = sh * (pre[hi]["c"] * (1 - MKT) - entry)
        # how many DISTINCT prints built the base this fire broke?
        base_prints = sum(1 for x in base if x["v"] > 0)
        return {"i": n, "pnl": pnl, "dv": v * c, "base_prints": base_prints}
    return None


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    ho = set(dates[44:])
    fires = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        full = S.FULL.get((sym, date))
        if not full:
            continue
        t0 = bars[0]["t"]
        pre = [b for b in full if b["t"] < t0]
        if len(pre) < 150:
            continue
        idx = [n for n, b in enumerate(pre) if OPEN_HM <= hmd(b["t"]).strftime("%H:%M") < CLOSE_HM]
        if len(idx) <= 60:
            continue
        lo, hi = idx[0], idx[-1]
        cov = 100.0 * len(idx) / SLOTS
        ts = [int(hmd(pre[n]["t"]).timestamp()) for n in idx]
        mxgap = max((ts[i + 1] - ts[i] for i in range(len(ts) - 1)), default=0) / 60.0
        cpv = cv = 0.0
        vw = {}
        for n in range(lo, hi + 1):
            b = pre[n]
            tp = (b["h"] + b["l"] + b["c"]) / 3.0
            cpv += tp * b["v"]; cv += b["v"]
            vw[n] = cpv / cv if cv else b["c"]
        r = scan(pre, lo, hi, vw)
        if r:
            fires.append({**r, "sym": sym, "date": date, "cov": cov, "gap": mxgap})

    W("=" * 106)
    W("PREMARKET IGNITION SPLIT BY TAPE COVERAGE — is the edge real, or thin-tape fiction?")
    W("=" * 106)
    W(f"fires: {len(fires)}   window {OPEN_HM}-{CLOSE_HM} ET   coverage = share of {SLOTS} "
      f"possible 10s bars carrying a print\n")
    if not fires:
        W("no fires"); return 1

    def stat(rs):
        if not rs:
            return None
        p = [r["pnl"] for r in rs]
        d = defaultdict(float)
        for r in rs:
            d[r["date"]] += r["pnl"]
        bp = sorted(r["base_prints"] for r in rs)
        return {"n": len(p), "tot": sum(p), "per": sum(p) / len(p),
                "win": 100.0 * sum(1 for x in p if x > 0) / len(p),
                "green": 100.0 * sum(1 for x in d.values() if x > 0) / max(len(d), 1),
                "bp": bp[len(bp) // 2]}

    BUCKETS = [("Q1 <25%   (thinnest)", lambda r: r["cov"] < 25),
               ("Q2 25-50%", lambda r: 25 <= r["cov"] < 50),
               ("Q3 50-75%", lambda r: 50 <= r["cov"] < 75),
               ("Q4 >=75%  (densest)", lambda r: r["cov"] >= 75)]

    for lbl, sel in (("FULL SAMPLE", None), (f"HOLD-OUT (unseen {len(ho)})", ho)):
        W(lbl)
        for nm, fn in BUCKETS:
            s = stat([r for r in fires if fn(r) and (sel is None or r["date"] in sel)])
            if not s:
                W(f"  {nm:22s} n=0"); continue
            flag = "  << UNDERPOWERED" if (sel is not None and s["n"] < 15) else ""
            W(f"  {nm:22s} n={s['n']:4d}  total=${s['tot']:+9.2f}  $/tr={s['per']:+7.2f}  "
              f"win={s['win']:3.0f}%  green={s['green']:3.0f}%  med base prints={s['bp']:3d}{flag}")
        W("")

    W("BY LARGEST PRINT-FREE GAP (hold-out)")
    for nm, fn in (("gap <= 5 min", lambda r: r["gap"] <= 5),
                   ("gap  > 5 min", lambda r: r["gap"] > 5)):
        s = stat([r for r in fires if fn(r) and r["date"] in ho])
        if s:
            W(f"  {nm:14s} n={s['n']:4d}  $/tr={s['per']:+7.2f}  win={s['win']:3.0f}%  "
              f"green={s['green']:3.0f}%")

    W("\n" + "=" * 106)
    W("PRE-REGISTERED VERDICT")
    W("=" * 106)
    dense = stat([r for r in fires if r["cov"] >= 50 and r["date"] in ho])
    thin = stat([r for r in fires if r["cov"] < 50 and r["date"] in ho])
    W(f"  DENSE (Q3+Q4, >=50% coverage): " +
      (f"n={dense['n']}  ${dense['per']:+.2f}/tr  green={dense['green']:.0f}%" if dense else "n=0"))
    W(f"  THIN  (Q1+Q2, <50% coverage) : " +
      (f"n={thin['n']}  ${thin['per']:+.2f}/tr  green={thin['green']:.0f}%" if thin else "n=0"))
    ok = bool(dense and dense["per"] > 0 and dense["n"] >= 25)
    W(f"\n  {'PASS' if ok else 'FAIL'}  the edge survives in TRADEABLE (dense) tape: "
      f"$/tr>0 with n>=25")
    if dense and thin:
        if dense["per"] > 0 and thin["per"] <= 0:
            W("  => THE EDGE IS IN THE DENSE COHORT. Thin tape is noise (or worse). A coverage")
            W("     floor becomes the lane's ELIGIBILITY RULE, not a cosmetic filter.")
        elif dense["per"] <= 0 and thin["per"] > 0:
            W("  => THE EDGE LIVES ONLY IN THIN TAPE. That is an ARTIFACT — the slip model")
            W("     flatters exactly this cohort. DO NOT BUILD premarket ignition on it.")
        elif dense["per"] > 0 and thin["per"] > 0:
            W("  => BOTH cohorts positive. The edge is not a coverage artifact; a floor is still")
            W("     worth setting for execution reasons (real spreads), not for the P&L.")
        else:
            W("  => NEITHER cohort positive on hold-out. The bake-off number does not survive")
            W("     the split. DO NOT BUILD.")
    W("\nLIMITS: study reimplementation (live detector refuses premarket, :7945); detector-only,")
    W("no board/chart gate/slots. The RTH slip model FLATTERS THIN TAPE MOST — so this test is")
    W("biased toward finding a fake edge in Q1/Q2, which is the safe direction here.")
    json.dump({"out": OUT}, open(HERE + "/ignition_pre_coverage_split_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
