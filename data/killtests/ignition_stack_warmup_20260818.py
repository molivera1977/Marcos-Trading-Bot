#!/usr/bin/env python3
"""
IGNITION'S STACK GATE IS BLIND UNTIL 10:36 — THE WARM-UP FIX ON TRIAL (8/18)

Marcos: "what can be done about this?" -> "Do whatever is needed and correct."

THE DEFECT (verified 8/18 from the live code + the trade records, before this script)
  marcos_trading_bot.py:10313
      _ig_comp = aggregate_bars(cache[t].get("full_bars") or bars, SETUP_TF_MIN)[:-1]
      if len(_ig_comp) >= EMA20_PERIOD + 2:  _e9,_e20,_e90 = ...
      else:                                  _e9 = _e20 = _e90 = 0.0
  and the gate at :10389
      _ig_stack_bad = (IGNITION_STACK_GATE and _e9 > 0 and _e20 > 0 and _e9 < _e20)

  `_e9 > 0` is FALSE when the EMAs could not be computed, so the gate FAILS OPEN. And
  `full_bars` is stamped "RTH 1-min, TODAY-only" (:9281), so at SETUP_TF_MIN=3 and
  EMA20_PERIOD=20 the site needs 22 three-minute bars = 66 MINUTES OF RTH. From 09:30 that is
  10:36 ET. The stack gate is structurally unable to evaluate before ~10:36, every day, on every
  name. Ignition is a morning lane, so most fires land in the dead window.

  MEASURED on the live book (era 7/13+, 125 ignition fills, 114 carrying the ema stamp):
  79 of 114 = 69% fired with ema9 == ema20 == 0.0, i.e. with the stack gate inert.

  CONSEQUENCE FOR TONIGHT'S WORK, STATED PLAINLY: the 9/20-vs-9/90 comparison run earlier
  (ignition_stack_v2_20260818) computed EMAs from full tape and therefore ALWAYS evaluated. Its
  "+$2-3/trade, keep 9>=20" verdict describes a gate that binds on 100% of fires. The live gate
  binds on 31%. That verdict does not describe the shipped system and is re-run here.

ARMS (identical detector, stops, exits; ONLY the stack-gate input changes)
  LIVE_NOW     the gate exactly as shipped: 3-min EMAs off RTH-ONLY bars, unevaluable -> OPEN
  WARMED       3-min EMAs warmed from PREMARKET (S.FULL carries the whole day; 328 premarket
               1-min bars on the sample name-day), so the stack binds from the opening bell
  FAILCLOSED   as shipped, but REFUSE the fire when the stack cannot be evaluated
  NOSTACK      no stack condition at all                                        [control]
  WARMED_9x90  warmed, but the condition is 9 over 90 instead of 9 over 20      (Marcos's signal)

  All arms carry the SHIPPED admission stack otherwise: day-gain floor 3% (ignition's own),
  relvol >= 2.0x session, and the VWAP tolerance band (price >= vwap*(1-0.02)).

PRE-REGISTERED (written before the run)
  * WARMED replaces LIVE_NOW only if it beats it on hold-out $/day at N=6 AND N=8.
  * If WARMED merely refuses more fires without raising $/day, it is a LOSS, not a fix: the
    defect would be real and the correction still not worth shipping. Say so if so.
  * FAILCLOSED is expected to be expensive (it blanks the open hour). It is included so that
    expectation is MEASURED rather than asserted.
  * Report which arm the 9/20-vs-9/90 question resolves to UNDER THE FIX, since the earlier
    verdict is void for the shipped system.
  * Chronological split: first 44 dates train, last 19 unseen. Both reported, always.

LIMITS: detector-only; the live funnel (board membership, slots, capital, chart gate, crowns,
priority sort) sits upstream and is not modelled, so fire counts exceed live. Ignition's harness
parity is UNMEASURED — no number exists in harness_parity.json — so these are DETECTOR figures
and the comparison between arms is the finding, never the level. Nothing ships from this script.
"""
import importlib.util
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SETUP_TF_MIN = 3
EMA20_PERIOD = 20
NEED = EMA20_PERIOD + 2          # the live site's own threshold
RELVOL_MIN = 2.0
DAYGAIN_FLOOR = 3.0
VWAP_TOL = 0.02


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


def ema_last(v, n):
    k = 2.0 / (n + 1)
    e = None
    for x in v:
        e = x if e is None else (x - e) * k + e
    return e


def agg3_closes(bars10s, upto_idx):
    """Roll 10s bars into SETUP_TF_MIN-minute closes, dropping the still-forming bar
    (the live site's `[:-1]`). 18 x 10s = 3 min."""
    per = SETUP_TF_MIN * 6
    out = []
    a = 0
    while a + per <= upto_idx + 1:
        out.append(bars10s[a + per - 1]["c"])
        a += per
    return out[:-1] if out else out


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    W("=" * 104)
    W("IGNITION STACK GATE — BLIND UNTIL ~10:36 ET.  THE PREMARKET WARM-UP FIX ON TRIAL")
    W("=" * 104)
    W(f"universe {len(E.DAYS)} name-days / {len(dates)} dates.  "
      f"live evidence: 79/114 era ignition fills (69%) fired with ema9==ema20==0.0\n")

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
        full = S.FULL.get((sym, date)) or bars
        # index in `full` of the RTH-session start (bars[] is the RTH-only slice)
        t0 = bars[0]["t"]
        off = next((n for n, b in enumerate(full) if b["t"] >= t0), 0)
        cpv = cv = 0.0
        vw = []
        for b in bars:
            tp = (b["h"] + b["l"] + b["c"]) / 3.0
            cpv += tp * b["v"]; cv += b["v"]
            vw.append(cpv / cv if cv else b["c"])
        op = bars[0]["o"]
        for f in fs:
            i, px = f.get("i"), (f.get("px") or f.get("price"))
            st = f.get("stop") or f.get("zone_stop") or f.get("would_stop")
            if i is None or not px or not st:
                continue
            i = int(i)
            if i >= len(bars) - 2 or float(st) >= float(px):
                continue
            gain = (bars[i]["c"] / max(op, 1e-9) - 1) * 100.0
            if gain < DAYGAIN_FLOOR:
                continue
            v1 = sum(b["v"] for b in bars[max(0, i - 6):i + 1])
            span = max(i - 6, 1)
            v_avg = sum(b["v"] for b in bars[:max(i - 6, 1)]) / (span / 6.0) if i > 12 else 0.0
            rv = (v1 / v_avg) if v_avg > 0 else None
            if rv is not None and rv < RELVOL_MIN:
                continue
            if vw[i] > 0 and bars[i]["c"] < vw[i] * (1 - VWAP_TOL):
                continue

            # ---- the two stack readings ----
            rth_c = agg3_closes(bars, i)                       # AS SHIPPED: RTH-only
            live_ok = len(rth_c) >= NEED
            s_live = None
            if live_ok:
                s_live = ema_last(rth_c, 9) > ema_last(rth_c, 20)
            warm_c = agg3_closes(full, off + i)                # THE FIX: premarket-warmed
            warm_ok = len(warm_c) >= NEED
            s_warm = s_warm90 = None
            if warm_ok:
                e9 = ema_last(warm_c, 9)
                s_warm = e9 > ema_last(warm_c, 20)
                if len(warm_c) >= 92:
                    s_warm90 = e9 > ema_last(warm_c, 90)
            try:
                pnl, _ex, _xi = F.sim_var(bars, emas, gaps, i, float(px), float(st),
                                          "E3", "ignition", halt_rule=True)
            except Exception:
                errs["sim"] += 1
                continue
            fires.append({"sym": sym, "date": date, "i": i, "pnl": pnl,
                          "live_ok": live_ok, "s_live": s_live,
                          "warm_ok": warm_ok, "s_warm": s_warm, "s_warm90": s_warm90})

    W(f"ignition fires (post floor3+relvol2+vwap-band): {len(fires)}"
      f"   skipped: {dict(errs) or 'none'}")
    if not fires:
        W("NO FIRES — cannot report."); return 1
    blind = sum(1 for f in fires if not f["live_ok"])
    W(f"  stack UNEVALUABLE as shipped (RTH-only, <{NEED} 3-min bars): {blind} "
      f"= {100.0*blind/len(fires):.0f}%   [live book says 69%]")
    W(f"  stack evaluable once PREMARKET-WARMED: "
      f"{sum(1 for f in fires if f['warm_ok'])} = "
      f"{100.0*sum(1 for f in fires if f['warm_ok'])/len(fires):.0f}%\n")

    ARMS = {
        "LIVE_NOW (shipped)": lambda f: (f["s_live"] is not False),   # unevaluable -> OPEN
        "WARMED":             lambda f: (f["s_warm"] is not False),
        "FAILCLOSED":         lambda f: (f["s_live"] is True),
        "NOSTACK":            lambda f: True,
        "WARMED_9x90":        lambda f: (f["s_warm90"] is not False),
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

    def perday(rs, n):
        byday = defaultdict(list)
        for r in sorted([x for x in rs if x["date"] in ho], key=lambda z: (z["date"], z["i"])):
            byday[r["date"]].append(r)
        return sum(sum(x["pnl"] for x in v[:n]) for v in byday.values()) / max(len(ho), 1)

    for lbl, sel in (("FULL SAMPLE", None), (f"HOLD-OUT (unseen {len(ho)} dates)", ho)):
        W(lbl)
        for k, fn in ARMS.items():
            rs = [f for f in fires if fn(f) and (sel is None or f["date"] in sel)]
            s = stat(rs)
            if not s:
                W(f"  {k:20s} n=0"); continue
            W(f"  {k:20s} n={s['n']:5d}  total=${s['tot']:+10.2f}  $/tr={s['per']:+7.2f}  "
              f"win={s['win']:4.0f}%  green={s['green']:3.0f}%")
        W("")

    W("CAPACITY — hold-out $/day, first N fires per day")
    W(f"  {'arm':20s}" + "".join(f"{('N='+str(n)):>13s}" for n in (4, 6, 8)))
    pd_ = {}
    for k, fn in ARMS.items():
        rs = [f for f in fires if fn(f)]
        pd_[k] = {n: perday(rs, n) for n in (4, 6, 8)}
        W(f"  {k:20s}" + "".join(f"${pd_[k][n]:>12.2f}" for n in (4, 6, 8)))

    W("\n" + "=" * 104)
    W("PRE-REGISTERED VERDICT")
    W("=" * 104)
    L, Wm = pd_["LIVE_NOW (shipped)"], pd_["WARMED"]
    ok = Wm[6] > L[6] and Wm[8] > L[8]
    W(f"  WARMED ${Wm[6]:+.2f}/day vs LIVE_NOW ${L[6]:+.2f} at N=6 (Δ ${Wm[6]-L[6]:+.2f});  "
      f"N=8 ${Wm[8]:+.2f} vs ${L[8]:+.2f} (Δ ${Wm[8]-L[8]:+.2f})")
    W(f"  {'PASS' if ok else 'FAIL'}  the warm-up fix beats the shipped gate at N=6 AND N=8")
    nl, wl = stat([f for f in fires if ARMS['NOSTACK'](f) and f['date'] in ho]), \
             stat([f for f in fires if ARMS['WARMED'](f) and f['date'] in ho])
    if nl and wl:
        W(f"  stack-vs-no-stack UNDER THE FIX: WARMED ${wl['per']:+.2f}/tr (n={wl['n']}) vs "
          f"NOSTACK ${nl['per']:+.2f}/tr (n={nl['n']})  Δ ${wl['per']-nl['per']:+.2f}")
    w9 = pd_["WARMED_9x90"]
    W(f"  9/20 vs 9/90 UNDER THE FIX: WARMED ${Wm[6]:+.2f}/day vs WARMED_9x90 ${w9[6]:+.2f} at N=6")
    W(f"  FAILCLOSED (refuse when unevaluable): ${pd_['FAILCLOSED'][6]:+.2f}/day at N=6 "
      f"(Δ vs shipped ${pd_['FAILCLOSED'][6]-L[6]:+.2f})")
    W("")
    if not ok:
        W("  => THE WARM-UP FIX IS NOT SUPPORTED ON P&L. The BLINDNESS IS STILL A REAL DEFECT")
        W("     (a money gate that cannot evaluate 69% of the time is not a gate), but on this")
        W("     evidence the correction does not pay and must not be sold as an improvement.")
        W("     The honest ship is the OBSERVABILITY stamp, not a behaviour change.")
    else:
        W("  => THE WARM-UP FIX IS SUPPORTED on this bar. It still changes a live money gate:")
        W("     env kill switch + rig pin + gauntlet + Marcos's priced call before any ship.")
    W("\nLIMITS: detector-only, no funnel. Ignition harness parity UNMEASURED (no entry in")
    W("harness_parity.json) — read the ARMS against each other, never the absolute levels.")
    json.dump({"out": OUT}, open(HERE + "/ignition_stack_warmup_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
