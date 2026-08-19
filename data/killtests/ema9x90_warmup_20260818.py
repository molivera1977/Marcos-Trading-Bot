#!/usr/bin/env python3
"""
THE 9/90 LANE'S WARM-UP — WHAT DOES THE FIRST 90 MINUTES COST? (8/18)

Marcos: "cant pre-market warm it up"

THE SITUATION (measured before this script)
  ema9x90_step accumulates its own 1-min series in st["m1"] and refuses to evaluate until it
  holds 90 bars (marcos_trading_bot.py, `if len(st["m1"]) < 90`). Fed only from the opening
  bell, that is 90 minutes: the lane cannot cross before ~11:00 ET.

  MEASURED across 736 name-days (earliest 9/90 up-cross per name-day):
      RTH-only feed      n=624   earliest 10:59   median 12:42
      premarket-warmed   n=642   earliest 09:30   median 11:20
      extra crosses unlocked by the warm-up: 575

  NOT YET KNOWN, and this script does NOT settle it: whether the LIVE feed already carries
  premarket buckets. The call site has NO RTH gate on its feed path (RECLAIM_KEV -> _vr_sv ->
  _nb -> EMA9X90 at :9561), and the scan loop runs premarket, so st["m1"] may already warm
  before the bell — in which case there is nothing to fix. EMA9X90_OPEN gates FIRING, not
  accumulation. That is a LIVE question (the lane shipped 12:43 today, so there is no morning
  data yet) and it is deliberately left open here.

WHAT THIS SCRIPT ANSWERS: are the crosses the warm-up unlocks WORTH MONEY? 575 extra crosses
is a count, not a verdict — early-session crosses could be worse than the ones we already take.

ARMS (identical entry rule, stop, exit; ONLY the warm-up source changes)
  RTH_ONLY   the 90-bar series accumulates from 09:30 only (lane blind until ~11:00)
  WARMED     the series is seeded with the same day's PREMARKET 1-min closes, so the 90-EMA is
             live at the bell and crosses from 09:30 count
  WARMED_AM  the WARMED arm restricted to the crosses it ADDS (before the RTH-only arm could
             have evaluated) — this isolates exactly what the warm-up buys, which is the honest
             way to price a change rather than reading a blended total

Entry: 1-min EMA9 up-cross through EMA90, price >= session VWAP (the p=0.0005 condition from
ema9x90_wall_20260818 — not a tunable). Stop: 5-min swing low. Exit: lose-VWAP on a 1-min close,
else EOD. Entry slip -1%, exit slip -0.5%, stop-first intrabar. Same construction as the wall
that this lane shipped on, so the numbers are comparable to it.

PRE-REGISTERED (before the run)
  * The warm-up is worth building ONLY if WARMED beats RTH_ONLY on hold-out $/day at N=4 AND
    N=6, AND the added crosses (WARMED_AM) are themselves positive on hold-out $/trade.
  * If WARMED_AM is NEGATIVE, the warm-up ADDS LOSING TRADES and the 90-minute blackout is
    accidentally protective — say so plainly and do not build it.
  * Chronological split: first 44 dates train, last 19 unseen. Both reported.

LIMITS: detector-only; no funnel (board, slots, capital, chart gate, crowns, priority sort), so
absolute levels overstate live — read the ARMS against each other. One position per name-day at
a time. Nothing ships from this script.
"""
import importlib.util
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
MKT, SLIP = 0.005, 0.01
SWING = 30


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


def run(bars, warm):
    """Walk the lane's OWN state machine: 1-min closes from 10s bars, EMA9/EMA90, cross-up
    at/above VWAP. `warm` = premarket 10s bars prepended for EMA seeding only (no fires there)."""
    cpv = cv = 0.0
    vw = []
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
        vw.append(cpv / cv if cv else b["c"])
    seq = warm + bars
    nw = len(warm)
    e9 = e90 = None
    m1 = 0
    prev = None
    out = []
    busy = -1
    for idx, b in enumerate(seq):
        if idx % 6 != 5:
            continue
        c = b["c"]
        m1 += 1
        e9 = c if e9 is None else (c - e9) * (2 / 10.0) + e9
        e90 = c if e90 is None else (c - e90) * (2 / 91.0) + e90
        if m1 < 90:
            prev = e9 > e90
            continue
        ab = e9 > e90
        cross = (prev is False) and ab
        prev = ab
        if not cross or idx < nw:
            continue
        i = idx - nw                       # index into the RTH slice
        if i <= busy or i >= len(bars) - 3:
            continue
        if bars[i]["c"] < vw[i]:
            continue
        stop = min(x["l"] for x in bars[max(0, i - SWING):i + 1])
        entry = bars[i]["c"] * (1 + SLIP)
        if stop >= entry:
            continue
        sh = E.POS / entry
        pnl = None
        for k in range(i + 1, len(bars)):
            if bars[k]["l"] <= stop:
                pnl = sh * (stop * (1 - MKT) - entry); break
            if (k - i) % 6 == 0 and bars[k]["c"] < vw[k]:
                pnl = sh * (bars[k]["c"] * (1 - MKT) - entry); break
        if pnl is None:
            pnl = sh * (bars[-1]["c"] * (1 - MKT) - entry)
        busy = len(bars)
        out.append({"i": i, "pnl": pnl})
    return out


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    ho = set(dates[44:])
    rows = {"RTH_ONLY": [], "WARMED": [], "WARMED_AM": []}
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        full = S.FULL.get((sym, date)) or bars
        t0 = bars[0]["t"]
        warm = [b for b in full if b["t"] < t0]
        a = run(bars, [])
        b = run(bars, warm)
        # the RTH-only arm cannot evaluate before its 90th 1-min bar => bar index 540
        cut = 540
        for r in a:
            rows["RTH_ONLY"].append({**r, "sym": sym, "date": date})
        for r in b:
            rows["WARMED"].append({**r, "sym": sym, "date": date})
            if r["i"] < cut:
                rows["WARMED_AM"].append({**r, "sym": sym, "date": date})

    W("=" * 100)
    W("THE 9/90 WARM-UP — is the first 90 minutes worth having?")
    W("=" * 100)
    W(f"universe {len(E.DAYS)} name-days / {len(dates)} dates\n")

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

    def perday(rs, n):
        byday = defaultdict(list)
        for r in sorted([x for x in rs if x["date"] in ho], key=lambda z: (z["date"], z["i"])):
            byday[r["date"]].append(r)
        return sum(sum(x["pnl"] for x in v[:n]) for v in byday.values()) / max(len(ho), 1)

    for lbl, sel in (("FULL SAMPLE", None), (f"HOLD-OUT (unseen {len(ho)})", ho)):
        W(lbl)
        for k in ("RTH_ONLY", "WARMED", "WARMED_AM"):
            s = stat([r for r in rows[k] if sel is None or r["date"] in sel])
            if not s:
                W(f"  {k:12s} n=0"); continue
            W(f"  {k:12s} n={s['n']:5d}  total=${s['tot']:+10.2f}  $/tr={s['per']:+7.2f}  "
              f"win={s['win']:4.0f}%  green={s['green']:3.0f}%")
        W("")

    W("CAPACITY — hold-out $/day, first N fires per day")
    W(f"  {'arm':12s}" + "".join(f"{('N='+str(n)):>13s}" for n in (2, 4, 6)))
    pd_ = {}
    for k in ("RTH_ONLY", "WARMED"):
        pd_[k] = {n: perday(rows[k], n) for n in (2, 4, 6)}
        W(f"  {k:12s}" + "".join(f"${pd_[k][n]:>12.2f}" for n in (2, 4, 6)))

    W("\n" + "=" * 100)
    W("PRE-REGISTERED VERDICT")
    W("=" * 100)
    am = stat([r for r in rows["WARMED_AM"] if r["date"] in ho])
    beats = pd_["WARMED"][4] > pd_["RTH_ONLY"][4] and pd_["WARMED"][6] > pd_["RTH_ONLY"][6]
    W(f"  WARMED ${pd_['WARMED'][4]:+.2f}/day @N=4 vs RTH_ONLY ${pd_['RTH_ONLY'][4]:+.2f} "
      f"(Δ ${pd_['WARMED'][4]-pd_['RTH_ONLY'][4]:+.2f});  @N=6 ${pd_['WARMED'][6]:+.2f} vs "
      f"${pd_['RTH_ONLY'][6]:+.2f} (Δ ${pd_['WARMED'][6]-pd_['RTH_ONLY'][6]:+.2f})")
    W(f"  {'PASS' if beats else 'FAIL'}  WARMED beats RTH_ONLY at N=4 AND N=6")
    if am:
        W(f"  {'PASS' if am['per'] > 0 else 'FAIL'}  the ADDED early crosses pay on their own: "
          f"${am['per']:+.2f}/tr  n={am['n']}  win {am['win']:.0f}%  green {am['green']:.0f}%")
    W("")
    if beats and am and am["per"] > 0:
        W("  => WARMING THE LANE IS SUPPORTED. It is still a live-path change to a lane that")
        W("     shipped today: env kill switch + rig pin + gauntlet before anything moves.")
    else:
        W("  => NOT SUPPORTED. The 90-minute blackout is not costing money on this evidence —")
        W("     the crosses it hides are not ones we want. Do NOT build the warm-up.")
    W("\nSEPARATE AND STILL OPEN: whether the LIVE feed already carries premarket (no RTH gate")
    W("on the feed path at :9561). If it does, the lane is ALREADY warm and none of this is a")
    W("change — it is a confirmation. That is a live check, not a tape check.")
    W("\nLIMITS: detector-only, no funnel; levels overstate live, compare the arms.")
    json.dump({"out": OUT}, open(HERE + "/ema9x90_warmup_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
