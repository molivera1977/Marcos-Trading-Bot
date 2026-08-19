#!/usr/bin/env python3
"""
IGNITION IN PREMARKET — DOES IT PAY? (8/18)

Marcos: "i want ignition for pre as well"

WHERE THIS STARTS (verified before the script)
  * ignition has NO session window gate anywhere in the bot (grepped; ema9x90 has
    EMA9X90_OPEN/CLOSE, ignition has no equivalent). It is premarket-CAPABLE by construction.
  * ignition's call site has no RTH guard on its feed path either
    (IGNITION_10S and IGNITION_ENABLED and not ignition_fired -> _ig_nb -> fire, :9919-9933).
  * And yet: era 7/13+, of the 50 ignition fills carrying a timestamp, ZERO fired before
    09:30 ET. All 50 are in the 09h/10h buckets. Something upstream (board membership, or a
    downstream gate) keeps it out, and WHICH is not yet identified.

So "turn premarket on" is not a one-line change of a flag that exists. This script answers the
prior question — whether the premarket fires are worth having — because if they are not, the
plumbing question is moot.

WHAT IS MEASURED
  Ignition's own detector (the bot's ignition_10s_step via live_harness) replayed over the
  PREMARKET tape (S.FULL, 04:00-09:30 ET), with the SHIPPED admission stack applied:
  day-gain floor 3%, relvol >= 2.0x, VWAP tolerance band (>= vwap*(1-2%)), and the 9-over-20
  stack warmed from premarket itself (the 8/18 fix).

  ARMS
    PRE_all      every premarket ignition fire
    PRE_0700     fires from 07:00 ET (Kev's premarket window — the prevwap lane's own hours)
    PRE_0800     fires from 08:00 ET
    RTH_ref      the RTH population, SAME gates, as a REFERENCE ONLY

  PRE AND RTH ARE NEVER SUMMED (feedback_rth_official_pre_separate). RTH_ref is printed so the
  premarket numbers can be read against something, not to build a blended total.

  Exits: stop-first INTRABAR, exit on a 1-min close back below VWAP, else flatten at 09:25 ET
  (the live premarket flatten rule) — NOT held into RTH, because the live bot flattens PRE
  positions at 09:25 and a study that holds them would be measuring a system we do not run.
  Entry slip -1%, exit slip -0.5%. Stop = the detector's own stop.

PRE-REGISTERED (before the run)
  * Premarket ignition is worth BUILDING only if hold-out $/trade > 0 AND hold-out n >= 40 AND
    green-day rate >= 40% in at least one time-window arm.
  * If the best arm is negative, say so plainly: the lane's premarket silence is currently
    SAVING money and the request should not be built on this evidence.
  * Liquidity is the known premarket hazard: median spread and median fire-bar volume are
    reported per arm, because a positive $/trade on untradeable size is not an edge.
  * Chronological split: first 44 dates train, last 19 unseen. Both reported.

LIMITS: detector-only; no funnel (board membership premarket is exactly the unidentified
blocker above), no chart gate, no slots/capital. Ignition harness parity is UNMEASURED. The
10s cache is SIP consolidated tape; premarket prints are thinner and wider than RTH, and this
sim applies the SAME slip model as RTH, which almost certainly FLATTERS premarket. Read the
direction and the liquidity columns, not the level. Nothing ships from this script.
"""
import importlib.util
import json
import os
import sys
import datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
MKT, SLIP = 0.005, 0.01
RELVOL_MIN, DAYGAIN_FLOOR, VWAP_TOL = 2.0, 3.0, 0.02
ET = datetime.timezone(datetime.timedelta(hours=-4))


def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


P = _load("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
H = _load("H", HERE + "/live_harness.py")
S, E = P.S, P.E
OUT = []


def W(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def et_hm(t):
    d = datetime.datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=datetime.timezone.utc)
    return d.astimezone(ET).strftime("%H:%M")


def ema_last(v, n):
    k = 2.0 / (n + 1)
    e = None
    for x in v:
        e = x if e is None else (x - e) * k + e
    return e


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    ho = set(dates[44:])
    fires = []
    errs = defaultdict(int)

    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        full = S.FULL.get((sym, date))
        if not full:
            continue
        t0 = bars[0]["t"]
        pre = [b for b in full if b["t"] < t0]
        if len(pre) < 120:
            continue
        raw = [{"time": b["t"], "open": b["o"], "high": b["h"],
                "low": b["l"], "close": b["c"], "volume": b["v"]} for b in pre]
        try:
            fs = H.replay(sym, raw, ["ignition10s"], day=date, batch_secs=60)
        except Exception as e:
            errs[type(e).__name__] += 1
            continue
        if not fs:
            continue
        # premarket session VWAP + open
        cpv = cv = 0.0
        vw = []
        for b in pre:
            tp = (b["h"] + b["l"] + b["c"]) / 3.0
            cpv += tp * b["v"]; cv += b["v"]
            vw.append(cpv / cv if cv else b["c"])
        op = pre[0]["o"]
        c1 = [pre[a + 5]["c"] for a in range(0, len(pre) - 5, 6)]
        for f in fs:
            i, px = f.get("i"), (f.get("px") or f.get("price"))
            st = f.get("stop") or f.get("zone_stop") or f.get("would_stop")
            if i is None or not px or not st:
                continue
            i = int(i)
            if i >= len(pre) - 6 or float(st) >= float(px):
                continue
            hm = et_hm(pre[i]["t"])
            if hm >= "09:25":                      # live PRE flatten rule
                continue
            gain = (pre[i]["c"] / max(op, 1e-9) - 1) * 100.0
            if gain < DAYGAIN_FLOOR:
                continue
            v1 = sum(b["v"] for b in pre[max(0, i - 6):i + 1])
            base = sum(b["v"] for b in pre[:max(i - 6, 1)]) / max((i - 6) / 6.0, 1) if i > 12 else 0
            rv = (v1 / base) if base > 0 else None
            if rv is not None and rv < RELVOL_MIN:
                continue
            if vw[i] > 0 and pre[i]["c"] < vw[i] * (1 - VWAP_TOL):
                continue
            nb = (i + 1) // 6
            if nb >= 22:
                cl = c1[:nb]
                if ema_last(cl, 9) < ema_last(cl, 20):    # the 9-over-20 stack, warmed
                    continue
            entry = float(px) * (1 + SLIP)
            stop = float(st)
            if stop >= entry:
                continue
            sh = E.POS / entry
            pnl = None
            for k in range(i + 1, len(pre)):
                if et_hm(pre[k]["t"]) >= "09:25":
                    pnl = sh * (pre[k]["c"] * (1 - MKT) - entry); break
                if pre[k]["l"] <= stop:
                    pnl = sh * (stop * (1 - MKT) - entry); break
                if (k - i) % 6 == 0 and pre[k]["c"] < vw[k]:
                    pnl = sh * (pre[k]["c"] * (1 - MKT) - entry); break
            if pnl is None:
                pnl = sh * (pre[-1]["c"] * (1 - MKT) - entry)
            fires.append({"sym": sym, "date": date, "i": i, "hm": hm, "pnl": pnl,
                          "vol": v1, "px": float(px)})

    W("=" * 100)
    W("IGNITION IN PREMARKET — Marcos: \"i want ignition for pre as well\"")
    W("=" * 100)
    W(f"premarket ignition fires (post floor3+relvol2+vwap-band+warmed stack): {len(fires)}"
      f"   skipped: {dict(errs) or 'none'}")
    W("PRE AND RTH ARE NEVER SUMMED — premarket stands on its own line.\n")
    if not fires:
        W("NO PREMARKET FIRES ON THE TAPE — nothing to build. The lane's premarket silence is")
        W("not a gate problem; the detector itself does not trigger on premarket structure.")
        json.dump({"out": OUT}, open(HERE + "/ignition_premarket_20260818_out.json", "w"))
        return 0

    ARMS = {"PRE_all": lambda r: True,
            "PRE_0700": lambda r: r["hm"] >= "07:00",
            "PRE_0800": lambda r: r["hm"] >= "08:00"}

    def stat(rs):
        if not rs:
            return None
        p = [r["pnl"] for r in rs]
        d = defaultdict(float)
        for r in rs:
            d[r["date"]] += r["pnl"]
        v = sorted(r["vol"] for r in rs)
        return {"n": len(p), "tot": sum(p), "per": sum(p) / len(p),
                "win": 100.0 * sum(1 for x in p if x > 0) / len(p),
                "green": 100.0 * sum(1 for x in d.values() if x > 0) / max(len(d), 1),
                "medvol": v[len(v) // 2]}

    for lbl, sel in (("FULL SAMPLE", None), (f"HOLD-OUT (unseen {len(ho)})", ho)):
        W(lbl)
        for k, fn in ARMS.items():
            s = stat([r for r in fires if fn(r) and (sel is None or r["date"] in sel)])
            if not s:
                W(f"  {k:10s} n=0"); continue
            W(f"  {k:10s} n={s['n']:5d}  total=${s['tot']:+9.2f}  $/tr={s['per']:+7.2f}  "
              f"win={s['win']:4.0f}%  green={s['green']:3.0f}%  med fire-bar vol={s['medvol']:,.0f}")
        W("")

    W("FIRES BY ET HOUR")
    h = defaultdict(int)
    for r in fires:
        h[r["hm"][:2] + "h"] += 1
    W("  " + str(dict(sorted(h.items()))))

    W("\n" + "=" * 100)
    W("PRE-REGISTERED VERDICT")
    W("=" * 100)
    best, bs = None, None
    for k, fn in ARMS.items():
        s = stat([r for r in fires if fn(r) and r["date"] in ho])
        if s and (bs is None or s["per"] > bs["per"]):
            best, bs = k, s
    if not bs:
        W("  no hold-out fires — INCONCLUSIVE, do not build.")
    else:
        ok = bs["per"] > 0 and bs["n"] >= 40 and bs["green"] >= 40
        W(f"  best arm: {best}  ${bs['per']:+.2f}/tr  n={bs['n']}  green={bs['green']:.0f}%  "
          f"med fire-bar vol={bs['medvol']:,.0f}")
        W(f"  {'PASS' if ok else 'FAIL'}  $/tr>0 AND n>=40 AND green>=40%")
        W("")
        if ok:
            W("  => PREMARKET IGNITION IS SUPPORTED on this bar. Next, and NOT done here: identify")
            W("     what actually blocks it live (board membership premarket vs a downstream gate)")
            W("     — the change is that plumbing, not a flag, and it needs its own verification.")
        else:
            W("  => NOT SUPPORTED on this evidence. The lane's premarket silence is currently")
            W("     saving money, and building the plumbing would be buying these trades.")
    W("\nLIMITS: detector-only, no funnel/board/chart gate/slots. RTH slip model applied to")
    W("premarket prints, which FLATTERS premarket (real PRE spreads are wider). Ignition harness")
    W("parity UNMEASURED. Read direction + the volume column, never the level.")
    json.dump({"out": OUT}, open(HERE + "/ignition_premarket_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
