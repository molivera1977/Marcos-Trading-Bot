#!/usr/bin/env python3
"""
HIDDEN LANE — THE WALL (8/18)

Marcos: "we have the early detectors, you shut them down."  True. I killed hidden on 8/14
because its expectancy was UNMEASURED under the honest intrabar-stop model — right epistemics,
but I never priced what OFF costs. Today it printed: hidden detected PFSA at $10.81 and
vwap_reclaim triggered at $11.70; the name went to $15.93 with both lanes on observe_only.

The reason I could not measure it then is gone. Hidden is now the HIGHEST-PARITY lane in the
system (86.3%, 195/226 fires reproduced) after batch E1 fixed the _bucket_fresh clock. So it
gets the same trial that validated `T B` and `e_level`, on the same clean tape.

DETECTOR: the BOT'S OWN hidden_entry_step, AST-lifted and driven by live_harness.replay
(batch_secs=60, the live rescan cadence). Not a replica — the real function.

TAPE: universe 10s SIP cache, 63 dates 2026-05-18..2026-08-17, ~736 name-days. RTH bars
(E.DAYS), so the numbers are directly comparable to the break-attack sweep and the T B wall.

EXITS: E3 live-parity via F.sim_var(..., "E3", "hidden", halt_rule=True) — bank 1/2 at +10%,
trail the rest 10%-off-run-high on a close-through, stop-first INTRABAR, -1% chase entry slip,
-0.5% market-exit slip. The intrabar stop is the honest model that made hidden unmeasurable in
the first place; it is ON here.

PRE-REGISTERED BAR (written before the run, per Marcos's standing contract):
  The lane comes back ONLY if ALL of:
    (a) hold-out $/trade > 0
    (b) hold-out N >= 100
    (c) BOTH hold-out halves positive
    (d) hold-out total dollars > 0
  Anything less = the lane stays off, and "it sees things early" was survivorship.
  Split is CHRONOLOGICAL: earliest 44 dates train (context only — nothing is fitted here,
  hidden has no parameter being tuned), last 19 dates are the unseen hold-out.

NOTE ON WHAT THIS IS NOT: no funnel. The harness grades the DETECTOR; scanner-board
membership, slots, and cap limits sit upstream and are not modelled, so fire counts exceed
what the live bot would take. Read $/trade and direction, not absolute totals.

No recommendation is made by this script. Numbers only; Marcos decides.
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


def vwap_series(bars):
    cpv = cv = 0.0
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
        vw = vwap_series(bars)
        try:
            fires = H.replay(sym, raw, ["hidden"],
                             vwap_provider=lambda s, i, b, l, _v=vw: _v[min(i, len(_v) - 1)],
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
            rows.append({"sym": sym, "date": date, "pnl": pnl, "exit": ex,
                         "px": float(px), "stop": float(stop)})

    W(f"fires graded: {len(rows)}   skipped: {dict(errs) or 'none'}\n")
    if not rows:
        W("NO GRADABLE FIRES — cannot report a result.")
        return 1

    def summ(rs, label):
        if not rs:
            W(f"  {label:26s} n=0"); return None
        p = [r["pnl"] for r in rs]
        byday = defaultdict(float)
        for r in rs:
            byday[r["date"]] += r["pnl"]
        d = {"n": len(p), "total": sum(p), "per": sum(p) / len(p),
             "win": 100.0 * sum(1 for x in p if x > 0) / len(p),
             "green": 100.0 * sum(1 for v in byday.values() if v > 0) / len(byday),
             "worst": min(byday.values()), "days": len(byday)}
        W(f"  {label:26s} n={d['n']:5d}  total=${d['total']:+10.2f}  $/tr={d['per']:+7.2f}  "
          f"win={d['win']:4.0f}%  green={d['green']:3.0f}%  worst=${d['worst']:+8.2f}")
        return d

    W("FULL SAMPLE")
    full = summ(rows, "hidden, all 63 dates")

    tr, ho = set(dates[:44]), set(dates[44:])
    W(f"\nCHRONOLOGICAL SPLIT — train {min(tr)}..{max(tr)} ({len(tr)}) | "
      f"HOLD-OUT {min(ho)}..{max(ho)} ({len(ho)})")
    a = summ([r for r in rows if r["date"] in tr], "train (context only)")
    b = summ([r for r in rows if r["date"] in ho], "HOLD-OUT (unseen)")

    hor = sorted([r for r in rows if r["date"] in ho], key=lambda r: r["date"])
    mid = len(hor) // 2
    h1 = sum(r["pnl"] for r in hor[:mid])
    h2 = sum(r["pnl"] for r in hor[mid:])
    W(f"\n  hold-out halves: first ${h1:+.2f}   second ${h2:+.2f}")

    W("\n" + "=" * 96)
    W("PRE-REGISTERED BAR (written before the run)")
    W("=" * 96)
    if b:
        c1 = b["per"] > 0
        c2 = b["n"] >= 100
        c3 = h1 > 0 and h2 > 0
        c4 = b["total"] > 0
        for lbl, ok, val in [("(a) hold-out $/trade > 0", c1, f"${b['per']:+.2f}"),
                             ("(b) hold-out N >= 100", c2, f"n={b['n']}"),
                             ("(c) both hold-out halves positive", c3, f"${h1:+.2f} / ${h2:+.2f}"),
                             ("(d) hold-out total > 0", c4, f"${b['total']:+.2f}")]:
            W(f"  {'PASS' if ok else 'FAIL'}  {lbl:36s} {val}")
        W("")
        if c1 and c2 and c3 and c4:
            W("  VERDICT: ALL FOUR CONDITIONS MET — the pre-registered bar for reinstating the")
            W("           hidden lane is CLEARED. Marcos's call at convening; sizing separate.")
        else:
            W("  VERDICT: BAR NOT MET — hidden stays OFF. 'It sees things early' is not enough;")
            W("           early detection that does not survive honest intrabar stops is not edge.")

    ex = defaultdict(int)
    for r in rows:
        ex[str(r["exit"]).split("@")[0]] += 1
    W(f"\n  exits: {dict(ex)}")
    W("\nLIMITS")
    W("  * DETECTOR ONLY — no funnel (board membership, slots, caps sit upstream, unmodelled).")
    W("    Fire counts exceed what the live bot would take; read $/trade and direction.")
    W("  * hidden's harness parity is 86.3% (195/226, matched on stop+time — the row's `price`")
    W("    is the live quote, not a detector output). 13.7% of live fires are NOT reproduced.")
    W("  * RTH bars only; hidden also fires premarket live, which is not graded here.")
    W("  * E3 exits, not the ladder the live lane would use if reinstated today.")

    json.dump({"rows": rows, "out": OUT}, open(HERE + "/hidden_wall_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
