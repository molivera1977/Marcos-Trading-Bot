#!/usr/bin/env python3
"""
THE RUNWAY NEAR-MISS BAND — is there money in the 80-100%% refusals? (8/21, Marcos: "grade the
near miss band")

WHERE THIS CAME FROM. JUNS today: ema9x90 fired twice, runway refused both.
  09:34:23  entry 8.93   stop 7.78  rr 0.91 / need 1.0  vel60 -0.05  -> price fell to 7.66,
            the refusal SAVED -$29.90.
  09:59:44  entry 8.5961 stop 7.90  rr 0.82 / need 1.0  vel60 -0.16  -> price ran to 9.65 and
            HALTED, straight through the $9.17 MAJOR target the gate said there was not enough
            road to reach. The refusal COST +$41.24.
The velocity override (live 8/20) could not rescue either: it needs the last completed 60s at
>= +1%%, and both fires happened on a NEGATIVE minute. Measured over 12 days, ema9x90's runway
refusals have a vel60 median of -0.05%% with 56%% negative — a lane that fires on an EMA CROSS
does so on a quiet minute by construction, so a backward-looking feature is structurally blind
to it. That is a HYPOTHESIS (n=9); this file does not test it.

THE QUESTION THIS FILE DOES ANSWER: the gate refuses when runway_rr < need. A refusal at
rr/need = 0.82 is a different animal from one at 0.15 — the road was nearly there. Is the
near-miss band (rr/need >= 0.8) profitable at real costs, and is there a threshold where the
gate should stop refusing?

COHORT: every runway_reject row 8/03-8/21 (175 rows, ALL of them carrying price, stop,
runway_rr and need — verified before this file was written). These are the lane's OWN stamped
entry and stop, so no hindsight re-derivation.

METHOD: real fire-minute NBBO spread charged (entry + stop/market exits pay half, limit tiers
free), 1%% width floor and k=1 spread guard as shipped, E3 exits, $30 risk with the 70%%/$1000
clamp, capital-aware at $3,000 and $5,000, TOTAL DOLLARS as the verdict (8/20 law). Tape from
the SIP trades feed, bucketed to 10s — the same builder every run this week used.

CUTS
  1. THE BAND LADDER: rr/need >= {0.0, 0.5, 0.6, 0.7, 0.8, 0.9} — what the gate would have made
     had it let through everything at or above each ratio.
  2. THE COMPLEMENT: rr/need < 0.8 (the deep refusals) — the gate's core business. If this is
     strongly negative the gate is right in general and only wrong at its own edge.
  3. BY LANE, restricted to the near-miss band — a band that pays on one lane and bleeds on
     another is a per-lane threshold, not a global one.
  4. vel60 SPLIT inside the band — does the shipped override feature separate winners from
     losers where it matters, or is it noise there?

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  N1 The band is worth acting on iff it is positive in TOTAL DOLLARS at BOTH books, BOTH halves
     (even/odd dates), AND survives dropping its single best trade. Same bar as every lane.
  N2 The ladder must be broadly MONOTONE toward the winning threshold. A single profitable
     band cell with red neighbours is a lucky slice, not a boundary.
  N3 If the COMPLEMENT is also positive, the finding is not "the band" — it is "the runway gate
     is too tight in general", which is a much larger claim needing its own study.
  N4 Nothing ships from this file.

LIMITS: n=175 total and the band is a fraction of that — this is a SMALL-SAMPLE study and the
per-lane cut will be smaller still; every cell prints its n. Refused trades never competed for
capital against the trades actually taken, so the books here are optimistic about slot
availability. Median-of-minute spread. No crown/slot re-simulation.
"""
import collections
import datetime as dt
import importlib.util
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = "https://zestful-intuition-production-b16a.up.railway.app"
RISK, BOOKS = 30.0, (3000.0, 5000.0)
MIN_STOP_PCT, SPREAD_K = 1.0, 1.0

sq = importlib.util.spec_from_file_location("HF", os.path.join(HERE, "halt_arm_feed_20260820.py"))
HF = importlib.util.module_from_spec(sq)
sq.loader.exec_module(HF)


def rows():
    out = []
    for i in range(0, 30):
        d = (dt.date(2026, 8, 21) - dt.timedelta(days=i)).isoformat()
        try:
            rs = json.load(urllib.request.urlopen(
                f"{BOARD}/api/decisions_archive?date={d}&limit=50000&key=marcos2026",
                timeout=45)).get("rows") or []
        except Exception:
            continue
        for r in rs:
            if str(r.get("status")) != "runway_reject":
                continue
            px, st = r.get("price"), r.get("stop")
            rr, nd = r.get("runway_rr"), r.get("need")
            tk, ts = r.get("ticker"), str(r.get("recorded_at") or "")
            if not (tk and ts and px and st) or float(px) <= float(st):
                continue
            if not (isinstance(rr, (int, float)) and isinstance(nd, (int, float)) and nd > 0):
                continue
            out.append({"d": d, "tk": tk, "ts": ts[11:19], "hhmm": ts[11:16],
                        "px": float(px), "stop": float(st), "rr": float(rr), "need": float(nd),
                        "ratio": float(rr) / float(nd), "vel60": r.get("vel60"),
                        "lane": str(r.get("machine") or "?"),
                        "sess": "PRE" if ts[11:16] < "09:30" else "RTH"})
    return out


def walk(b10, k0, entry, stop, spr, pre):
    ks = [x for x in sorted(b10) if x >= k0]
    if len(ks) < 2:
        return None
    half = (spr / 2) if spr else entry * 0.0025
    px = entry + half
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(max(BOOKS) * 0.70 / px), int(1000 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    flat = "09:25" if pre else "15:45"
    for k in ks[1:]:
        x = b10[k]
        if HF.hm_k(k) >= flat:
            return banked + rem * ((x["c"] - half) - px), sh * px, k
        if x["l"] <= stop:
            return banked + rem * ((stop - half) - px), sh * px, k
        runhi = max(runhi, x["h"])
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 - px)
            rem -= n
            tiered, stop = True, px
            if rem == 0:
                return banked, sh * px, k
        if tiered and x["c"] <= runhi * 0.90:
            return banked + rem * ((x["c"] - half) - px), sh * px, k
    lk = ks[-1]
    return banked + rem * ((b10[lk]["c"] - half) - px), sh * px, lk


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


def line(lab, fl):
    if not fl:
        print(f"{lab:>28s}     0   (no fills)")
        return
    t5, n5 = book(fl, 5000.0)
    t3, _ = book(fl, 3000.0)
    tr_ = sum(f["pnl"] for f in fl if int(f["d"][-2:]) % 2 == 0)
    oo = sum(f["pnl"] for f in fl if int(f["d"][-2:]) % 2 == 1)
    p = sorted((f["pnl"] for f in fl), reverse=True)
    win = 100 * sum(1 for x in p if x > 0) / len(p)
    print(f"{lab:>28s} {n5:5d} {t5:+11.2f} {t3:+11.2f} {(t5/n5 if n5 else 0):+8.2f} "
          f"{tr_:+10.2f} {oo:+10.2f} {t5 - p[0]:+10.2f} {win:4.0f}%")


def main():
    rs = rows()
    print(f"runway_reject rows graded: {len(rs)}  ({min(r['d'] for r in rs)} -> "
          f"{max(r['d'] for r in rs)})")
    bynd = collections.defaultdict(list)
    for r in rs:
        bynd[(r["d"], r["tk"])].append(r)
    print(f"name-days to fetch: {len(bynd)}\n")

    graded = []
    for i, ((d, tk), l) in enumerate(sorted(bynd.items()), 1):
        lo = min(x["ts"] for x in l)
        tr = HF.trades(tk, d, lo, "15:50:00")
        print(f"  [{i}/{len(bynd)}] {d} {tk} refusals={len(l)} trades={len(tr)}", flush=True)
        if len(tr) < 50:
            continue
        b10 = HF.bars(tr, 10)
        ks = sorted(b10)
        for r in l:
            if (r["px"] - r["stop"]) / r["px"] * 100 < MIN_STOP_PCT:
                continue
            spr = HF.spread_at(tk, d, r["hhmm"])
            if SPREAD_K > 0 and spr and (r["px"] - r["stop"]) < SPREAD_K * spr:
                continue
            pre = r["sess"] == "PRE"
            if pre and not ("07:00" <= r["hhmm"] <= "09:20"):
                continue
            if not pre and not ("09:30" <= r["hhmm"] < "15:30"):
                continue
            ep = dt.datetime.fromisoformat(f"{d}T{r['ts']}+00:00").timestamp() + 4 * 3600
            k0 = min((x for x in ks if x >= ep), default=None)
            if k0 is None:
                continue
            w = walk(b10, k0, r["px"], r["stop"], spr, pre)
            if w is None:
                continue
            graded.append(dict(r, pnl=w[0], n=w[1], ti=k0, tx=w[2], spr=spr))
    print(f"\nwalked {len(graded)} of {len(rs)} | quotes {HF._qgap[1]} gaps {HF._qgap[0]}")

    hdr = (f"{'cut':>28s} {'n':>5s} {'$5,000':>11s} {'$3,000':>11s} {'$/tr':>8s} "
           f"{'TRAIN':>10s} {'OOS':>10s} {'w/o best':>10s} {'win%':>5s}")
    print("\n=== CUT 1: THE BAND LADDER (let through everything at ratio >= X) ===")
    print(hdr)
    for x in (0.0, 0.5, 0.6, 0.7, 0.8, 0.9):
        line(f"ratio >= {x:.2f}", [g for g in graded if g["ratio"] >= x])

    print("\n=== CUT 2: THE COMPLEMENT (the gate's core business) ===")
    print(hdr)
    line("ratio < 0.8 (deep refusals)", [g for g in graded if g["ratio"] < 0.8])
    line("ratio 0.8-1.0 (near miss)", [g for g in graded if g["ratio"] >= 0.8])

    print("\n=== CUT 3: NEAR-MISS BAND BY LANE ===")
    print(hdr)
    nm = [g for g in graded if g["ratio"] >= 0.8]
    for lane in sorted({g["lane"] for g in nm}):
        line(lane, [g for g in nm if g["lane"] == lane])

    print("\n=== CUT 4: DOES vel60 SEPARATE INSIDE THE BAND? ===")
    print(hdr)
    line("vel60 >= +1% (override'd)", [g for g in nm if isinstance(g["vel60"], (int, float)) and g["vel60"] >= 1])
    line("vel60 0 to +1%", [g for g in nm if isinstance(g["vel60"], (int, float)) and 0 <= g["vel60"] < 1])
    line("vel60 negative", [g for g in nm if isinstance(g["vel60"], (int, float)) and g["vel60"] < 0])
    line("vel60 not stamped", [g for g in nm if not isinstance(g["vel60"], (int, float))])

    print("\n=== SESSION SPLIT (doctrine: RTH headline, PRE its own line) ===")
    print(hdr)
    line("near-miss RTH", [g for g in nm if g["sess"] == "RTH"])
    line("near-miss PRE", [g for g in nm if g["sess"] == "PRE"])

    json.dump(graded, open(os.path.join(HERE, "runway_nearmiss_20260821_out.json"), "w"),
              default=str)
    print("\nPRE-REGISTERED: N1 the band acts only if positive at BOTH books, BOTH halves, AND")
    print("drop-best. N2 the ladder must be broadly monotone. N3 if the COMPLEMENT is also")
    print("positive the finding is 'runway is too tight in general', a bigger claim needing its")
    print("own study. N4 nothing ships from this file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
