#!/usr/bin/env python3
"""
FLAT_TOP AT REAL COSTS — the oldest lane, graded for the first time (8/21, Marcos: "grade the
fires at real costs")

CONTEXT. flat_top is the lane the bot was originally built around and the one with the least
evidence behind it. Live census (22 days, archive, 8/21): 1,213 fires -> 25 fills (~2%).
Restricted since 8/19 on a note that called it a CODE DEFECT ("bought the break print in a
retest costume") — and TEST L then found buying the break print BEATS the retest (61%/37%,
+$9,220 vs +$1,280, edge_stresstest_G_20260815.md). That was PAPER. Nothing here has ever been
charged a real spread.

TWO CORRECTIONS THIS FILE CARRIES (both mine, both found this morning):
  * The "41% of fires die silently" figure was a MEASUREMENT ARTIFACT — my matcher ignored
    flat_top_observe_only, which IS a disposition. True figure 229/1,213 (19%), and it clusters
    at 01:00-05:00 ET, hours before the entry window opens. Inside the attack window the
    decision tree is 96% complete.
  * "flat_top is not in the harness LANES registry" — FALSE. It has an entry AND a dedicated
    driver (replay_flat_top). No registry work was needed; the debt was imaginary.

METHOD
  Detector   the BOT'S OWN flat_top_step via live_harness.replay_flat_top — 10s tape -> 1-min
             -> aggregate_bars(SETUP_TF_MIN) -> drop incomplete -> _latest_session(). Real
             function objects, not a transcription.
  ctx        armed=False (the driver's documented bound: measures the BREAK-ATTACK cell on the
             assumption no out-of-window arm was live), ma_first=False, ma_only_window=False,
             time_hm from the bar's ET clock. DISCLOSED: with armed=False this over-counts any
             name whose earlier break already armed a retest.
  Entry/stop AS THE LANE SPECIFIES: entry = the fire price, stop = _ft_attack_stop(w_low) =
             base low EXACT (no buffer). Both come out of the detector's own decision dict.
  Costs      real median NBBO spread of the fire minute; entry + stop/market exits pay half,
             resting limit tiers free. k=1 spread guard + 1% width floor (both shipped).
  Exits      E3 (house). Sizing $30 risk, 70%/$1000 clamp, capital-aware, $3,000 and $5,000.
  Verdict    TOTAL DOLLARS (the 8/20 law); $/fill diagnostic.

THE FOUR QUESTIONS, each a cut (the external-AI audit's table, tested rather than argued)
  Q1 IS IT ANY GOOD AT REAL COSTS? overall + by block.
  Q2 IS 10:30 A REAL BOUNDARY OR A SUPERSTITION? break-attack graded by HOUR BUCKET, all day.
     TEST L only ever tested the 09:30-10:30 cell; the clock split is a hypothesis.
  Q3 IS 12% THE RIGHT BASE WIDTH? sweep 6/8/10/12/15/20% (FLAT_TOP_MAX_RANGE is a self-declared
     "not a Kev number" — the 'approved number, unexamined measure' class).
  Q4 DOES THE BARE STOP GET SHAKEN OUT? stop = base low EXACT vs base_low-0.5xspread vs -1%.
     Other lanes carry ZONE_STOP_BUFFER; this one does not.

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  P1 The lane earns a RESTRICTION RETRIAL iff some cut is positive in TOTAL DOLLARS at BOTH
     books, BOTH halves (even/odd dates), AND drop-best. Same bar every other lane faced.
  P2 The 10:30 boundary is REAL iff in-window hours beat out-of-window hours on both halves.
     If out-of-window grades as well or better, the boundary is a superstition and TEST L
     measured a cell, not an edge.
  P3 A parameter change is justified only if it wins on BOTH halves AND is broadly monotone
     toward the winner — a lone winning cell with red neighbours is a lucky slice.
  P4 Nothing ships from this file. It writes JSON and prints.

POSITIVE CONTROL (run 8/21 before this study): XOS 8/18 — all 7 LIVE logged fires reproduced
with an EXACTLY matching base high (3.99/4.36/4.74/4.65/4.48) within 0-3 min (cadence phase).
MEASURED DENSITY BOUND: the replay fired 75x vs live's 7 on that name-day (armed=False + the
60s cadence). Per-fill expectancy is the trustworthy figure; TOTAL dollars are inflated by
roughly an order of magnitude and must NOT be read as revenue.

LIMITS: cache universe (curated movers — absolute dollars are universe-flattered, same caveat
every run this week carries); detector proxies fire denser than live; median-of-minute spreads;
the retest/arm path is NOT modelled (documented harness bound) — this grades the BREAK ATTACK.
"""
import collections
import datetime as dt
import importlib.util
import json
import os
import sys

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
sq.loader.exec_module(HF)


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


def book(fl, bal, key="pnl"):
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
            tot += f[key]
            n += 1
    return tot, n


def line(fl, key="pnl"):
    t5, n5 = book(fl, 5000.0, key)
    t3, _ = book(fl, 3000.0, key)
    tr_ = sum(r[key] for r in fl if int(r["d"][-2:]) % 2 == 0)
    oo = sum(r[key] for r in fl if int(r["d"][-2:]) % 2 == 1)
    p = sorted((r[key] for r in fl), reverse=True)
    win = 100 * sum(1 for x in p if x > 0) / len(p) if p else 0
    return t5, t3, n5, tr_, oo, t5 - (p[0] if p else 0), win


def main():
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
    raws = []
    print(f"name-days: {len(days)}")
    for n_, (d, sym) in enumerate(days, 1):
        raw = json.load(open(os.path.join(BARS, f"{d}_{sym}.json")))
        raw = raw.get("bars", raw) if isinstance(raw, dict) else raw
        if len(raw) < 150:
            continue
        b = [{"t": x["time"], "o": float(x.get("open") or x["close"]), "h": float(x["high"]),
              "l": float(x["low"]), "c": float(x["close"]), "v": float(x["volume"])} for x in raw]
        try:
            vw = H.running_vwap(raw, day=d)
            fires = H.replay_flat_top(
                sym, raw, d,
                vwap_provider=lambda s, i, bar, l: vw[i],
                ctx_provider=lambda s, i, bar, l: {"armed": False, "ma_first": False,
                                                   "ma_only_window": False,
                                                   "time_hm": H.et_hm(bar[0])},
                cadence_secs=60)
        except Exception as e:
            if n_ < 5:
                print(f"   [{sym} {d}] replay failed: {type(e).__name__}: {e}")
            continue
        if n_ % 150 == 0:
            print(f"  [{n_}/{len(days)}] ...", flush=True)
        for f in fires:
            i = f.get("i")
            if i is None or f.get("w_low") in (None, 0) or f.get("w_high") in (None, 0):
                continue
            raws.append({"d": d, "sym": sym, "i": i, "px": float(f["price"]),
                         "w_low": float(f["w_low"]), "w_high": float(f["w_high"]),
                         "rng": f.get("rng"), "action": f.get("action"),
                         "ok": bool(f.get("ok")), "why": ",".join(f.get("why") or []),
                         "t": et_hm(b[i]["t"]), "bars": b})
    print(f"\nraw detector fires: {len(raws)}")

    def grade(rows, max_range=None, stop_mode="exact", hours=None):
        out = []
        for r in rows:
            if max_range is not None:
                if r["rng"] is None or r["rng"] > max_range:
                    continue
            if hours is not None and int(r["t"][:2]) not in hours:
                continue
            b = r["bars"]
            spr = HF.spread_at(r["sym"], r["d"], r["t"])
            stop = r["w_low"]
            if stop_mode == "half_spread" and spr:
                stop = r["w_low"] - spr / 2
            elif stop_mode == "pct1":
                stop = r["w_low"] * 0.99
            e = r["px"]
            if e <= stop:
                continue
            if (e - stop) / e * 100 < MIN_STOP_PCT:
                continue
            if SPREAD_K > 0 and spr and (e - stop) < SPREAD_K * spr:
                continue
            pre = r["t"] < "09:30"
            if pre and not ("07:00" <= r["t"] <= "09:20"):
                continue
            if not pre and not ("09:30" <= r["t"] < "15:30"):
                continue
            w = walk(b, r["i"], e, stop, pre, spr)
            if w is None:
                continue
            out.append({"d": r["d"], "sym": r["sym"], "t": r["t"], "pnl": w[0], "n": w[1],
                        "ti": dt.datetime.fromisoformat(str(b[r["i"]]["t"])[:19]).timestamp(),
                        "tx": dt.datetime.fromisoformat(str(b[w[2]]["t"])[:19]).timestamp()})
        return out

    hdr = (f"{'cut':>26s} {'n':>5s} {'$5,000':>11s} {'$3,000':>11s} {'$/fill':>8s} "
           f"{'TRAIN':>10s} {'OOS':>10s} {'w/o best':>10s} {'win%':>5s}")

    def show(lab, fl):
        if not fl:
            print(f"{lab:>26s}     0  (no fills)")
            return
        t5, t3, n5, tr_, oo, wb, win = line(fl)
        print(f"{lab:>26s} {n5:5d} {t5:+11.2f} {t3:+11.2f} {(t5/n5 if n5 else 0):+8.2f} "
              f"{tr_:+10.2f} {oo:+10.2f} {wb:+10.2f} {win:4.0f}%")

    print("\n=== Q1: THE LANE AT REAL COSTS (shipped params: 12% base, stop=base low) ===")
    print(hdr)
    base = grade(raws)
    show("ALL FIRES", base)
    show("PRE 07:00-09:20", [f for f in base if f["t"] < "09:30"])
    show("OPEN 09:30-10:30", [f for f in base if "09:30" <= f["t"] < "10:30"])
    show("MID 10:30-15:30", [f for f in base if f["t"] >= "10:30"])

    print("\n=== Q2: IS 10:30 A REAL BOUNDARY? break-attack graded BY HOUR ===")
    print(hdr)
    for h in range(7, 16):
        show(f"{h:02d}:00-{h:02d}:59", [f for f in base if int(f["t"][:2]) == h])
    show("IN-WINDOW 09-10", [f for f in base if int(f["t"][:2]) in (9, 10)])
    show("OUT-OF-WINDOW 11-15", [f for f in base if int(f["t"][:2]) >= 11])

    print("\n=== Q3: BASE WIDTH SWEEP (shipped 12%) ===")
    print(hdr)
    for mr in (0.06, 0.08, 0.10, 0.12, 0.15, 0.20):
        show(f"max_range {mr:.0%}", grade(raws, max_range=mr))

    print("\n=== Q4: STOP BUFFER (shipped = base low EXACT) ===")
    print(hdr)
    for mode, lab in (("exact", "base low EXACT"), ("half_spread", "base low - 0.5x spread"),
                      ("pct1", "base low - 1%")):
        show(lab, grade(raws, stop_mode=mode))

    print(f"\nquotes {HF._qgap[1]} gaps {HF._qgap[0]}")
    json.dump({"n_raw": len(raws)}, open(os.path.join(HERE, "flattop_realcost_20260821_out.json"), "w"))
    print("\nPRE-REGISTERED: P1 retrial needs both books + both halves + drop-best. P2 the 10:30")
    print("boundary is real only if in-window beats out-of-window on BOTH halves. P3 a parameter")
    print("wins only both-halves AND broadly monotone. P4 nothing ships from this file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
