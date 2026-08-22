#!/usr/bin/env python3
"""
BLOCK COMPETITION v2 — POST-BOUNDARY ONLY, CORRECTED WALKER (8/21 night, Fable session)

THE THREE RULINGS THIS ENCODES (all Marcos, 8/21):
  1. "We started REALLY designing this system last Thursday. Anything from before should be
     forgotten as useless data." -> ERA BOUNDARY 2026-08-14. Only name-days >= the boundary.
  2. "Our bars are good, but our data and accounting should all be suspect." -> lane DESIGNS
     replayed against VENDOR BARS; nothing derived from our own records enters the cohort.
  3. The opening hour is the mission ("Kev's best hour, the money hour"). The OPEN cut is the
     headline; PRE and MID are context lines.

vs v1 (block_competition_real_20260821):
  * DAYS: >= 2026-08-14 only (v1 spanned the whole cache; its numbers now describe a
    pre-design era and are retired for ranking purposes).
  * WALKER: walker_v2 — gap-through-stop fills at min(stop, bar_open) (the one flaw the 8/21
    accounting audit found, measured at 5.1% of bars gapping >=1%). Self-tested at import.
  * BOOKING: ONE shared capital pool over the whole cohort (the v1 flat_top study's D1 lesson:
    per-cut pools flatter small cuts). Cuts are slices of the single book.
  * Same detectors (the bot's own functions via the harness), same real fire-minute NBBO
    spreads, same 1% floor + k=1 guard, $30 risk, $5,000 book.

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  B1 Lane ranking = TOTAL DOLLARS in the OPEN window on the shared book. A lane is seat-worthy
     in the hour iff positive there on BOTH halves (even/odd dates) AND after drop-best. With
     ~6 trading days, halves are ~3 days each — every verdict is PROVISIONAL by construction
     and says so. n and day-count print on every line.
  B2 The 09:30-09:45 bucket is reported separately (the live-vs-replay dispute from tonight).
  B3 This file writes JSON + prints. NOTHING ships. The seat verdict is a separate Fable
     decision with Blast Radius, not a side effect of a study completing.
LIMITS: <=6 post-boundary days; cache universe = names the bot watched (selection toward
movers); detector density > live density; median-of-minute spreads.
"""
import collections
import datetime as dt
import importlib.util
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
BOUNDARY = "2026-08-14"
RISK, BAL = 30.0, 5000.0
MIN_STOP_PCT, SPREAD_K = 1.0, 1.0

sp = importlib.util.spec_from_file_location("H", os.path.join(HERE, "live_harness.py"))
H = importlib.util.module_from_spec(sp)
sp.loader.exec_module(H)
sq = importlib.util.spec_from_file_location("HF", os.path.join(HERE, "halt_arm_feed_20260820.py"))
HF = importlib.util.module_from_spec(sq)
sq.loader.exec_module(HF)
sw = importlib.util.spec_from_file_location("W2", os.path.join(HERE, "walker_v2.py"))
W2 = importlib.util.module_from_spec(sw)
sw.loader.exec_module(W2)          # selftest runs at import; a wrong correction dies here


def load_hv2():
    src = open(os.path.join(HERE, "hidden_v2_simple_20260819.py")).read()
    src = src.replace('if __name__ == "__main__":\n    sys.exit(main())', "")
    src = src.replace('def hmss(t):\n    return str(t)[11:19]',
                      'def hmss(t):\n    import datetime as _d\n'
                      '    return (_d.datetime.fromisoformat(str(t)[:19])'
                      ' - _d.timedelta(hours=4)).strftime("%H:%M:%S")')
    m = types.ModuleType("HV2")
    m.__file__ = os.path.join(HERE, "hidden_v2_simple_20260819.py")
    exec(compile(src, "HV2", "exec"), m.__dict__)
    return m.scan


def et_hm(t):
    return (dt.datetime.fromisoformat(str(t)[:19]) - dt.timedelta(hours=4)).strftime("%H:%M")


def main():
    hv2 = load_hv2()
    KCTX = {"front_side": None, "day_gain": None, "top3": False, "blue_sky": False}
    LANES = [("ignition", "ignition10s", {}), ("v2conv", "v2", {}), ("kevseq", "kevseq", KCTX),
             ("grinder", "grinder", {}), ("ema9x90", "ema9x90", {}),
             ("reclaim", "reclaim", {}), ("prevwap", "prevwap", {})]
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS)
                   if f.endswith(".json") and f[:10] >= BOUNDARY})
    daylist = sorted({d for d, _ in days})
    print(f"POST-BOUNDARY name-days: {len(days)} across {len(daylist)} days: {daylist}", flush=True)
    fills = []
    for n_, (d, sym) in enumerate(days, 1):
        raw = json.load(open(os.path.join(BARS, f"{d}_{sym}.json")))
        raw = raw.get("bars", raw) if isinstance(raw, dict) else raw
        if len(raw) < 150:
            continue
        b = [{"t": x["time"], "o": float(x.get("open") or x["close"]), "h": float(x["high"]),
              "l": float(x["low"]), "c": float(x["close"]), "v": float(x["volume"])} for x in raw]
        cand = []
        try:
            vw = H.running_vwap(raw, day=d)
            for lane, hname, ctx in LANES:
                f = H.replay(sym, raw, [hname], day=d, batch_secs=60,
                             vwap_provider=lambda s, i, bar, l: vw[i],
                             ctx_provider=lambda s, i, bar, l: dict(ctx))
                for x in f:
                    i = x.get("i")
                    st = x.get("would_stop") or x.get("stop")
                    px = x.get("px") or (b[i]["c"] if i is not None else None)
                    if i is None or not st or not px or float(px) <= float(st):
                        continue
                    cand.append((lane, i, float(px), float(st)))
        except Exception:
            pass
        for k, e, s_ in hv2(b):
            cand.append(("hidden_v2", k, e, s_))
        if n_ % 60 == 0:
            print(f"  [{n_}/{len(days)}] fills so far {len(fills)}", flush=True)
        for lane, i, e, s_ in cand:
            t = et_hm(b[i]["t"])
            if "07:00" <= t <= "09:20":
                blk, pre = "PRE", True
            elif "09:30" <= t < "10:30":
                blk, pre = "OPEN", False
            elif "10:30" <= t < "15:30":
                blk, pre = "MID", False
            else:
                continue
            if (e - s_) / e * 100 < MIN_STOP_PCT:
                continue
            spr = HF.spread_at(sym, d, t)
            if SPREAD_K > 0 and spr and (e - s_) < SPREAD_K * spr:
                continue
            r = W2.walk(b, i, e, s_, pre, spr, bal=BAL)
            if r is None:
                continue
            fills.append({"lane": lane, "blk": blk, "d": d, "sym": sym, "t": t,
                          "pnl": r[0], "n": r[1],
                          "ti": dt.datetime.fromisoformat(str(b[i]["t"])[:19]).timestamp(),
                          "tx": dt.datetime.fromisoformat(str(b[r[2]]["t"])[:19]).timestamp()})
    print(f"\nfills {len(fills)} | quotes {HF._qgap[1]} gaps {HF._qgap[0]}", flush=True)
    json.dump(fills, open(os.path.join(HERE, "block_competition_v2_20260821_out.json"), "w"),
              default=str)

    # ONE shared book (D1 discipline)
    byday = collections.defaultdict(list)
    for f in fills:
        byday[f["d"]].append(f)
    TAKEN = []
    for d, l in byday.items():
        op = []
        for f in sorted(l, key=lambda x: x["ti"]):
            op = [o for o in op if o[0] > f["ti"]]
            if f["n"] > BAL - sum(o[1] for o in op):
                continue
            op.append((f["tx"], f["n"]))
            TAKEN.append(f)
    print(f"ONE SHARED BOOK: taken {len(TAKEN)} of {len(fills)}")

    def st(fl):
        if not fl:
            return None
        t = sum(f["pnl"] for f in fl)
        tr = sum(f["pnl"] for f in fl if int(f["d"][-2:]) % 2 == 0)
        oo = sum(f["pnl"] for f in fl if int(f["d"][-2:]) % 2 == 1)
        p = sorted((f["pnl"] for f in fl), reverse=True)
        nd = len({f["d"] for f in fl})
        return dict(n=len(fl), tot=t, per=t / len(fl), tr=tr, oo=oo, wo=t - p[0],
                    win=100 * sum(1 for x in p if x > 0) / len(p), days=nd)

    def line(lab, fl):
        s = st(fl)
        if not s:
            print(f"{lab:>14s}     0  (none)")
            return
        print(f"{lab:>14s} {s['n']:5d} {s['tot']:+11.2f} {s['per']:+8.2f} {s['tr']:+10.2f} "
              f"{s['oo']:+10.2f} {s['wo']:+10.2f} {s['win']:4.0f}%  ({s['days']}d)")

    HDRL = (f"{'lane':>14s} {'n':>5s} {'total$':>11s} {'$/fill':>8s} {'TRAIN':>10s} "
            f"{'OOS':>10s} {'w/o best':>10s} {'win%':>5s}")
    for blk in ("OPEN", "PRE", "MID"):
        sub = [f for f in TAKEN if f["blk"] == blk]
        print(f"\n=== {blk} (post-{BOUNDARY}, walker v2, shared book) ===")
        print(HDRL)
        by = collections.defaultdict(list)
        for f in sub:
            by[f["lane"]].append(f)
        for k, l in sorted(by.items(), key=lambda x: -sum(f["pnl"] for f in x[1])):
            line(k, l)
        line("BLOCK TOTAL", sub)
        if blk == "OPEN":
            line("  09:30-09:45", [f for f in sub if f["t"] < "09:45"])
            line("  09:45-10:30", [f for f in sub if f["t"] >= "09:45"])

    print("\nPRE-REGISTERED: B1 seat-worthy in the hour iff positive OPEN on both halves AND")
    print("drop-best — ALL verdicts PROVISIONAL at <=6 days. B2 09:30-09:45 reported. B3 nothing")
    print("ships; the seat verdict is a separate Fable decision with Blast Radius.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
