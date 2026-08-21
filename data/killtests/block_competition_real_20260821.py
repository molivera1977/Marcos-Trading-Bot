#!/usr/bin/env python3
"""
THE BLOCK COMPETITION, RE-RUN AT REAL COSTS — PRE + RTH (8/21, Marcos: "rerun the block
competition for both pre and rth")

WHY: the 8/20 competition that set OPEN_LANE_RANK / MID_LANE_RANK / the PRE roster ran on the
harness walker with FLAT PAPER SLIPS. The spread study that ran three hours later proved real
NBBO costs cut paper results roughly in half (+$8.65 -> +$4.41/fill on its cohort), and
tonight's reclaim forensics showed a paper #2 dissolving entirely at real costs. The seated
rosters have never been ranked in the currency Friday's go/no-go will be judged in. Same
universe as the 8/20 competition (the 10s cache), same harness detectors, same E3 exits —
ONLY the costs change. Apples to apples on everything except the currency.

LANES: every harness-replayable lane that holds or contests a seat —
  ignition10s (ignition) · v2 (v2conv) · kevseq · grinder · ema9x90 · hidden_v2 · reclaim
  (benched; graded for the record) · prevwap (benched; PRE only by construction).
  NOT here: ma_pullback (its two-timeframe driver is a separate rig; the harness LANES
  registry cannot replay it — DISCLOSED, same gap as 8/20's first pass) and dip_rip
  (restricted tonight, Addendum 19, and needs historical maps regardless).

BLOCKS: PRE 07:00-09:20 (09:25 flatten) · OPEN 09:30-10:30 · MID 10:30-15:30 (15:45 flat).

COSTS/CONFIG: real median NBBO spread of the fire minute (entry + stop/market exits pay half,
limit tiers free), 1% width floor (PRE and RTH — both shipped), k=1 spread guard, $30 risk,
70%/$1000 clamp, capital-aware books at $3,000 and $5,000, one shared capital pool per day
ACROSS lanes (they compete for the same dollars, as live).

VERDICT: TOTAL DOLLARS per lane per block (the 8/20 law), $/fill diagnostic, TRAIN/OOS halves.

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  R1 The shipped roster orders stand unless an inversion is BOTH-HALVES consistent (an order
     flip that appears in only one half is noise, not a re-rank).
  R2 A seated lane loses its seat argument iff its block total is NEGATIVE in both halves at
     real costs. A benched lane earns nothing here regardless of score (evidence files, Marcos
     rules).
  R3 The paper-vs-real haircut is reported per lane (this run vs the 8/20 numbers) — the
     spread physics says tight-stop lanes take the bigger haircut; that prediction is testable
     here and is stated BEFORE seeing the result.
  R4 Nothing ships from this file.

LIMITS: cache universe = curated movers (the SAME selection the 8/20 competition used — this
is deliberate for comparability, and it means absolute dollars are still universe-flattered);
detector proxies fire denser than live (~55/day vs ~14 live, the 8/20 caveat, unchanged);
kevseq runs neutral ctx; hidden_v2 via its spec scan. Median-of-minute spreads.
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
RISK = 30.0
BOOKS = (3000.0, 5000.0)
MIN_STOP_PCT, SPREAD_K = 1.0, 1.0

sp = importlib.util.spec_from_file_location("H", os.path.join(HERE, "live_harness.py"))
H = importlib.util.module_from_spec(sp)
sp.loader.exec_module(H)
sq = importlib.util.spec_from_file_location("HF", os.path.join(HERE, "halt_arm_feed_20260820.py"))
HF = importlib.util.module_from_spec(sq)
sq.loader.exec_module(HF)          # spread_at + hm_k reused (one quote cache)


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


def walk(b, i0, entry, stop, pre, spr):
    px = entry + (spr / 2 if spr else entry * 0.005)
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(max(BOOKS) * 0.70 / px), int(1000 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    half = (spr / 2 if spr else px * 0.0025)
    flat = "09:25" if pre else "15:45"
    for i in range(i0 + 1, len(b)):
        x = b[i]
        t = et_hm(x["t"])
        if t >= flat:
            return banked + rem * ((x["c"] - half) - px), sh * px, i
        if x["l"] <= stop:
            return banked + rem * ((stop - half) - px), sh * px, i
        runhi = max(runhi, x["h"])
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 - px)
            rem -= n
            tiered, stop = True, px
            if rem == 0:
                return banked, sh * px, i
        if tiered and x["c"] <= runhi * 0.90:
            return banked + rem * ((x["c"] - half) - px), sh * px, i
    return banked + rem * ((b[-1]["c"] - half) - px), sh * px, len(b) - 1


def main():
    hv2 = load_hv2()
    KCTX = {"front_side": None, "day_gain": None, "top3": False, "blue_sky": False}
    LANES = [("ignition", "ignition10s", {}), ("v2conv", "v2", {}), ("kevseq", "kevseq", KCTX),
             ("grinder", "grinder", {}), ("ema9x90", "ema9x90", {}),
             ("reclaim", "reclaim", {}), ("prevwap", "prevwap", {})]
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
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
        if n_ % 100 == 0:
            print(f"  [{n_}/{len(days)}] ...", flush=True)
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
            w = (e - s_) / e * 100
            if w < MIN_STOP_PCT:
                continue
            spr = HF.spread_at(sym, d, t)
            if SPREAD_K > 0 and spr and (e - s_) < SPREAD_K * spr:
                continue
            r = walk(b, i, e, s_, pre, spr)
            if r is None:
                continue
            fills.append({"lane": lane, "blk": blk, "d": d, "sym": sym, "t": t,
                          "pnl": r[0], "n": r[1],
                          "ti": dt.datetime.fromisoformat(str(b[i]["t"])[:19]).timestamp(),
                          "tx": dt.datetime.fromisoformat(str(b[r[2]]["t"])[:19]).timestamp()})
    print(f"\nfills {len(fills)} | quotes {HF._qgap[1]} gaps {HF._qgap[0]}")

    def book(fl, bal):
        """One shared pool per day across ALL lanes in the block — they compete, as live."""
        byday = collections.defaultdict(list)
        for f in fl:
            byday[f["d"]].append(f)
        taken = []
        for d, l in byday.items():
            op = []
            for f in sorted(l, key=lambda x: x["ti"]):
                op = [o for o in op if o[0] > f["ti"]]
                if f["n"] > bal - sum(o[1] for o in op):
                    continue
                op.append((f["tx"], f["n"]))
                taken.append(f)
        return taken

    PAPER = {"OPEN": {"ema9x90": 35.77, "ma_pullback": 21.87, "ignition": 18.65,
                      "reclaim": 17.20, "v2conv": 12.90, "kevseq": 12.31, "hidden_v2": 10.88},
             "MID": {"grinder": 34.98, "ignition": 21.83, "ma_pullback": 15.30,
                     "ema9x90": 10.80, "hidden_v2": 10.29, "kevseq": 8.70, "v2conv": 2.20},
             "PRE": {"ignition": 7.87, "v2conv": 7.76, "reclaim": 4.94}}
    out = {}
    for blk in ("PRE", "OPEN", "MID"):
        bf = [f for f in fills if f["blk"] == blk]
        taken5 = book(bf, 5000.0)
        taken3 = book(bf, 3000.0)
        print(f"\n=== {blk} (fills {len(bf)}, taken@5k {len(taken5)}, taken@3k {len(taken3)}) ===")
        print(f"{'lane':>10s} {'n':>5s} {'$5,000':>10s} {'$/fill':>8s} {'TRAIN':>9s} "
              f"{'OOS':>9s} {'paper$/fill':>11s} {'haircut':>8s}")
        rows = []
        for lane in sorted({f["lane"] for f in taken5}):
            l = [f for f in taken5 if f["lane"] == lane]
            tot = sum(f["pnl"] for f in l)
            tr_ = sum(f["pnl"] for f in l if int(f["d"][-2:]) % 2 == 0)
            oo = sum(f["pnl"] for f in l if int(f["d"][-2:]) % 2 == 1)
            pf = PAPER.get(blk, {}).get(lane)
            rows.append((lane, len(l), tot, tot / len(l), tr_, oo, pf))
        for lane, n, tot, per, tr_, oo, pf in sorted(rows, key=lambda x: -x[2]):
            hc = f"{(1 - per / pf) * 100:+.0f}%" if (pf and pf > 0) else "  -"
            print(f"{lane:>10s} {n:5d} {tot:+10.2f} {per:+8.2f} {tr_:+9.2f} {oo:+9.2f} "
                  f"{(f'{pf:+11.2f}' if pf else '          -')} {hc:>8s}")
        out[blk] = rows
    json.dump({"fills": fills, "blocks": {k: v for k, v in out.items()}},
              open(os.path.join(HERE, "block_competition_real_20260821_out.json"), "w"),
              default=str)
    print("\nPRE-REGISTERED: R1 rosters re-order only on BOTH-HALVES-consistent inversions.")
    print("R2 a seated lane loses its seat argument iff negative in both halves. R3 the")
    print("haircut should be largest for tight-stop lanes. R4 nothing ships from this file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
