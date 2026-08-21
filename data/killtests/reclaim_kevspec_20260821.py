#!/usr/bin/env python3
"""
THE PASTED VWAP-RECLAIM SPEC, WALKED (8/21 ~02:2x, Marcos pasted check_vwap_reclaim + params)

WHAT THIS IS: a byte-faithful port of the spec Marcos pasted, run over the same 10s cache /
real-NBBO-cost machinery every other lane faced tonight. It is NOT our vwap_reclaim lane —
the two differ structurally, and the pasted spec's two distinguishing choices are exactly what
tonight's runs never tested:
  * STOP: max($0.15, 2% x price) — on this universe the $0.15 floor dominates (7.5% on a $2
    name), the OPPOSITE of our lane's structural stops (median width 2.41%, measured tonight,
    the tight-stop disease).
  * EXIT: bank half at +1.5R, rest at +2.5R, stop to entry after T1 — fixed-R banking, not a
    runner engine. (Marcos's "I'd rather bank a win and re-enter", as an entry-spec property.)

FAITHFUL PORT (each line maps to the paste):
  lookback 10 bars (100s): >=2 bars with close < that bar's running VWAP
  dip_low = min low of those below-bars; depth (vwap - dip_low)/vwap >= 0.5%
  current close > vwap * 1.001
  volume: current >= 1.5 x mean of last 20 bars (INCLUDING current — pandas rolling semantics)
  spread guard: stop_dist < spread -> reject (k=1)
  entry = close; stop = close - stop_dist; shares = floor(30 / stop_dist)
DECLARED DEPARTURES (disclosed, not silent):
  * bid/ask per bar is not in the cache — spread = median NBBO of the fire minute (same
    source every run tonight used); entry pays half-spread, stop/market exits pay half.
  * the paste has no dedupe — bare, it re-fires on consecutive bars of one reclaim. Added:
    after a fire, the name re-arms only after a close back below VWAP (one trade per reclaim).
    Pre-registered here, before the run.
  * exits flatten 09:25 (PRE) / 15:45 (RTH); T2 rest also exits on stop-at-entry after T1.
  * 70%/$1000 notional clamp + capital-aware books, as everywhere tonight.

BLOCKS: PRE 07:00-09:20 · OPEN 09:30-10:30 · MID 10:30-15:30, books $3,000/$5,000.

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  K1 The spec earns further work iff some block is positive at BOTH books, BOTH halves
     (even/odd dates), AND drop-best positive — the same bar every lane faced tonight.
  K2 It is compared head-to-head against OUR reclaim's real-cost numbers (negative in all
     cuts) — if the pasted spec passes where ours failed, the difference is attributable to
     stop-width/exit design and THAT becomes the retool thesis; if it fails too, the VWAP-
     reclaim family is dead on this universe regardless of parameterization.
  K3 Nothing ships from this file.
"""
import collections
import datetime as dt
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
RISK = 30.0
BOOKS = (3000.0, 5000.0)

sp = importlib.util.spec_from_file_location("H", os.path.join(HERE, "live_harness.py"))
H = importlib.util.module_from_spec(sp)
sp.loader.exec_module(H)
sq = importlib.util.spec_from_file_location("HF", os.path.join(HERE, "halt_arm_feed_20260820.py"))
HF = importlib.util.module_from_spec(sq)
sq.loader.exec_module(HF)


def et_hm(t):
    return (dt.datetime.fromisoformat(str(t)[:19]) - dt.timedelta(hours=4)).strftime("%H:%M")


def detect(b, vw):
    """The pasted spec over the whole day. b = list of bar dicts, vw = running vwap list.
    Returns fires [(i, entry, stop_dist)] with the close-below-VWAP re-arm rule."""
    fires, armed = [], True
    for i in range(20, len(b)):
        c, v = b[i]["c"], b[i]["v"]
        vwap = vw[i]
        if not vwap or vwap <= 0:
            continue
        if c < vwap:
            armed = True                      # re-arm on a close back below VWAP
            continue
        if not armed:
            continue
        look = [(b[j], vw[j]) for j in range(max(0, i - 10), i)]
        below = [(x, w) for x, w in look if w and x["c"] < w]
        if len(below) < 2:
            continue
        dip_low = min(x["l"] for x, _ in below)
        if (vwap - dip_low) / vwap < 0.005:
            continue
        if c <= vwap * 1.001:
            continue
        avg20 = sum(b[j]["v"] for j in range(i - 19, i + 1)) / 20.0
        if v < avg20 * 1.5:
            continue
        stop_dist = max(0.15, 0.02 * c)
        fires.append((i, c, stop_dist))
        armed = False                          # one trade per reclaim
    return fires


def walk(b, i0, entry, stop_dist, pre, spr):
    px = entry + (spr / 2 if spr else entry * 0.005)
    stop = entry - stop_dist                   # per the paste: from close, not from fill
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / stop_dist), int(max(BOOKS) * 0.70 / px), int(1000 / px)))
    t1, t2 = px + 1.5 * rps, px + 2.5 * rps
    half = (spr / 2 if spr else px * 0.0025)
    rem, banked, t1done = sh, 0.0, False
    flat = "09:25" if pre else "15:45"
    for i in range(i0 + 1, len(b)):
        x = b[i]
        t = et_hm(x["t"])
        if t >= flat:
            return banked + rem * ((x["c"] - half) - px), sh * px, i
        if x["l"] <= stop:
            return banked + rem * ((stop - half) - px), sh * px, i
        if not t1done and x["h"] >= t1:
            n = rem // 2 or rem
            banked += n * (t1 - px)            # resting limit: no spread charge
            rem -= n
            t1done, stop = True, px            # stop to entry
            if rem == 0:
                return banked, sh * px, i
        if t1done and x["h"] >= t2:
            return banked + rem * (t2 - px), sh * px, i
    return banked + rem * ((b[-1]["c"] - half) - px), sh * px, len(b) - 1


def main():
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
    fills = []
    for n_, (d, sym) in enumerate(days, 1):
        raw = json.load(open(os.path.join(BARS, f"{d}_{sym}.json")))
        raw = raw.get("bars", raw) if isinstance(raw, dict) else raw
        if len(raw) < 150:
            continue
        b = [{"t": x["time"], "o": float(x.get("open") or x["close"]), "h": float(x["high"]),
              "l": float(x["low"]), "c": float(x["close"]), "v": float(x["volume"])} for x in raw]
        try:
            vw = H.running_vwap(raw, day=d)
        except Exception:
            continue
        if n_ % 150 == 0:
            print(f"  [{n_}/{len(days)}] ...", flush=True)
        for i, e, sd in detect(b, vw):
            t = et_hm(b[i]["t"])
            if "07:00" <= t <= "09:20":
                blk, pre = "PRE", True
            elif "09:30" <= t < "10:30":
                blk, pre = "OPEN", False
            elif "10:30" <= t < "15:30":
                blk, pre = "MID", False
            else:
                continue
            spr = HF.spread_at(sym, d, t)
            if spr and sd < spr:               # the paste's k=1 guard, verbatim
                continue
            r = walk(b, i, e, sd, pre, spr)
            if r is None:
                continue
            fills.append({"blk": blk, "d": d, "sym": sym, "t": t, "pnl": r[0], "n": r[1],
                          "stop_pct": sd / e * 100,
                          "ti": dt.datetime.fromisoformat(str(b[i]["t"])[:19]).timestamp(),
                          "tx": dt.datetime.fromisoformat(str(b[r[2]]["t"])[:19]).timestamp()})
    print(f"\nfills {len(fills)} | quotes {HF._qgap[1]} gaps {HF._qgap[0]}")

    def book(fl, bal):
        byday = collections.defaultdict(list)
        for f in fl:
            byday[f["d"]].append(f)
        tot = n = 0
        for d, l in byday.items():
            op = []
            for f in sorted(l, key=lambda x: x["ti"]):
                op = [o for o in op if o[0] > f["ti"]]
                if f["n"] > bal - sum(o[1] for o in op):
                    continue
                op.append((f["tx"], f["n"]))
                tot += f["pnl"]
                n += 1
        return tot, n

    print(f"\n{'block':>6s} {'n':>5s} {'$5,000':>10s} {'$3,000':>10s} {'$/fill':>8s} "
          f"{'TRAIN':>9s} {'OOS':>9s} {'w/o best':>9s} {'win%':>5s} {'med stop%':>9s}")
    for blk in ("PRE", "OPEN", "MID"):
        fl = [f for f in fills if f["blk"] == blk]
        if not fl:
            print(f"{blk:>6s}     0 (no fires)")
            continue
        t5, n5 = book(fl, 5000.0)
        t3, _ = book(fl, 3000.0)
        tr_ = sum(f["pnl"] for f in fl if int(f["d"][-2:]) % 2 == 0)
        oo = sum(f["pnl"] for f in fl if int(f["d"][-2:]) % 2 == 1)
        p = sorted((f["pnl"] for f in fl), reverse=True)
        sps = sorted(f["stop_pct"] for f in fl)
        print(f"{blk:>6s} {n5:5d} {t5:+10.2f} {t3:+10.2f} {(t5/n5 if n5 else 0):+8.2f} "
              f"{tr_:+9.2f} {oo:+9.2f} {t5-(p[0] if p else 0):+9.2f} "
              f"{100*sum(1 for x in p if x>0)/len(p):4.0f}% {sps[len(sps)//2]:8.2f}%")
    json.dump(fills, open(os.path.join(HERE, "reclaim_kevspec_20260821_out.json"), "w"),
              default=str)
    print("\nPRE-REGISTERED: K1 a block earns further work iff positive at BOTH books, BOTH")
    print("halves, AND drop-best. K2 head-to-head vs our reclaim's real-cost negatives — pass")
    print("here + fail there pins the retool thesis on stop-width/exit design. K3 nothing ships.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
