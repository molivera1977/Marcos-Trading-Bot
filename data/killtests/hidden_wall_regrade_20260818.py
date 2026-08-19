#!/usr/bin/env python3
"""
HIDDEN'S WALL, REGRADED ON THE LIVE VWAP ANCHOR (8/18)

Marcos: "regrade hidden's wall with the correct vwap"

WHAT THE CHECK FOUND FIRST — and it corrects something I claimed:
  The original wall (hidden_wall_20260818.py) does NOT read live rows at all (grep for
  api/trades / entry_session_vwap / dashboard returns 0). It builds its own VWAP from tape. So
  the 60 bad stamped VWAPs the watchdog found NEVER entered it, and my roll-call flag that
  "hidden's wall verdict is SUSPECT" was WRONG — asserted without checking the study's source.

WHAT IS ACTUALLY WRONG, and is regraded here:
  the original accumulates VWAP over E.DAYS bars = RTH-ONLY, anchored 09:30. The live bot runs
  ENTRY_VWAP_PREMARKET=True and anchors at 04:00 (PRE+RTH). Hidden's gate is VWAP-relative, so
  the study has been gating on a DIFFERENT LINE than the bot it claims to model. On CDTG 8/18
  the two anchors differ by 2.4% ($4.7850 RTH-only vs $4.6719 PRE+RTH).

ARMS (identical detector, stops, exits — only the VWAP LINE fed to the detector changes)
  RTH_ANCHOR   VWAP accumulated from 09:30            [what the wall used]
  PRE_ANCHOR   VWAP accumulated from 04:00 premarket  [what the LIVE bot uses]

PRE-REGISTERED: hidden's FAILED verdict is overturned only if PRE_ANCHOR turns the hold-out
$/trade POSITIVE. A smaller loss is still a loss and the lane stays dead. Chronological split,
last 19 dates unseen, same as the original wall.

LIMITS: detector-only, no funnel. Hidden's harness parity is 86.3% (below the 90% threshold) —
stated because a hidden verdict may not be quoted without it. Nothing ships from this script.
"""
import importlib.util
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
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


def vwap_series(bars, warm=None):
    """RTH-anchored when warm is None; PRE-anchored (the LIVE line) when the premarket bars are
    passed in — the accumulator is seeded with them, exactly as a 04:00-anchored session VWAP."""
    cpv = cv = 0.0
    for b in (warm or []):
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
    out = []
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
        out.append(cpv / cv if cv else b["c"])
    return out


def main():
    S.load_all()
    days = sorted(E.DAYS.items(), key=lambda kv: (kv[0][1], kv[0][0]))
    dates = sorted({d for (_, d) in E.DAYS})
    W("=" * 96)
    W("HIDDEN LANE — THE WALL   (bot's own hidden_entry_step via live_harness; E3 exits)")
    W("=" * 96)
    W(f"universe: {len(days)} name-days over {len(dates)} dates  {dates[0]} .. {dates[-1]}")

    rows = []
    errs = defaultdict(int)
    for (sym, date), (bars, emas, gaps) in days:
        raw = [{"time": b["t"], "open": b["o"], "high": b["h"],
                "low": b["l"], "close": b["c"], "volume": b["v"]} for b in bars]
        _full = S.FULL.get((sym, date)) or bars
        _t0 = bars[0]["t"]
        _warm = [b for b in _full if b["t"] < _t0]
        for _arm, _vw in (("RTH_ANCHOR", vwap_series(bars)),
                          ("PRE_ANCHOR", vwap_series(bars, _warm))):
          H.reset_state("hidden", sym)
          try:
            fires = H.replay(sym, raw, ["hidden"],
                             vwap_provider=lambda s, i, b, l, _v=_vw: _v[min(i, len(_v) - 1)],
                             day=date, batch_secs=60)
          except Exception as e:
            errs[type(e).__name__] += 1
            continue
          for f in fires:
              i = f.get("i")
              px = f.get("px") or f.get("price")
              stop = f.get("stop") or f.get("would_stop")
              if i is None or not px or not stop or stop >= px:
                  errs["unusable_fire"] += 1
                  continue
              try:
                  pnl, ex, xi = F.sim_var(bars, emas, gaps, int(i), float(px), float(stop),
                                          "E3", "hidden", halt_rule=True)
              except Exception:
                  errs["sim_fail"] += 1
                  continue
              rows.append({"sym": sym, "date": date, "pnl": pnl, "exit": ex, "arm": _arm,
                           "px": float(px), "stop": float(stop)})

    W(f"fires graded: {len(rows)}   skipped: {dict(errs) or 'none'}")
    ho = set(dates[44:])

    def stat(rs):
        if not rs:
            return None
        pl = [r["pnl"] for r in rs]
        d = defaultdict(float)
        for r in rs:
            d[r["date"]] += r["pnl"]
        return {"n": len(pl), "tot": sum(pl), "per": sum(pl) / len(pl),
                "win": 100.0 * sum(1 for x in pl if x > 0) / len(pl),
                "green": 100.0 * sum(1 for x in d.values() if x > 0) / max(len(d), 1)}

    for lbl, sel in (("FULL SAMPLE", None), (f"HOLD-OUT (unseen {len(ho)} dates)", ho)):
        W("\n" + lbl)
        for arm in ("RTH_ANCHOR", "PRE_ANCHOR"):
            st = stat([r for r in rows if r["arm"] == arm and (sel is None or r["date"] in sel)])
            if not st:
                W(f"  {arm:12s} n=0"); continue
            W(f"  {arm:12s} n={st['n']:5d}  total=${st['tot']:+10.2f}  $/tr={st['per']:+7.2f}  "
              f"win={st['win']:4.0f}%  green={st['green']:3.0f}%")

    W("\n" + "=" * 96)
    W("PRE-REGISTERED VERDICT")
    W("=" * 96)
    a = stat([r for r in rows if r["arm"] == "RTH_ANCHOR" and r["date"] in ho])
    b = stat([r for r in rows if r["arm"] == "PRE_ANCHOR" and r["date"] in ho])
    if a and b:
        W(f"  wall as run (RTH anchor): ${a['per']:+.2f}/tr  n={a['n']}")
        W(f"  LIVE anchor (PRE+RTH)   : ${b['per']:+.2f}/tr  n={b['n']}   (delta ${b['per']-a['per']:+.2f})")
        if b["per"] > 0:
            W("\n  => OVERTURNED. On the line the bot actually uses, hidden's hold-out $/trade is")
            W("     POSITIVE. The failed verdict was measured against a VWAP the live bot never saw.")
        else:
            W("\n  => VERDICT STANDS. The anchor was wrong, and correcting it does not save the lane:")
            W("     hold-out $/trade is still negative on the live line. A smaller loss is a loss.")
    W("\nLIMITS: detector-only, no funnel. Hidden harness parity 86.3% (below the 90% threshold).")
    json.dump({"out": OUT}, open(HERE + "/hidden_wall_regrade_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
