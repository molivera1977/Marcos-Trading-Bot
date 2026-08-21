#!/usr/bin/env python3
"""
FLAT_TOP v2 — THE RETRIAL EVIDENCE (8/21, Marcos: "launch it now")

v1 (flattop_realcost_20260821) graded the lane at real costs for the first time and it PASSED
its pre-registration: ALL FIRES +$9.88/fill, OPEN 09:30-10:30 +$29.23/fill at 67% win, both
halves, drop-best intact. This file answers everything v1 could not, in ONE pass, because v1
dumped only a row count and every follow-up question needed a 75-minute re-run.

THREE DEFECTS IN v1 THIS FILE FIXES
  D1 PER-CUT CAPITAL GATING. v1 booked every cut against its own fresh $5,000 pool, so cuts with
     fewer candidates faced less contention and took proportionally more of them. Proof from v1's
     own table: hour07 (991) + hour08 (940) = 1,931 taken, but the PRE block that contains both
     reports 1,806. Sub-cuts did not sum, and the hourly column was systematically optimistic
     against the block column. FIX: book ONCE over the whole cohort, then slice the taken set.
     Every cut below is a slice of one shared-capital book.
  D2 NO PER-FILL DUMP. v1 wrote {"n_raw": N}. Any new question (drop-best-name, concentration,
     regime split) meant re-running the tape. FIX: full per-fill JSON.
  D3 NO FILL-MODEL SENSITIVITY. v1 assumed the break print fills at mid+half-spread. FIX: the
     +1 TICK cut re-prices every fill with one extra spread of adverse entry.

THE EXTERNAL AUDIT'S QUESTIONS, TESTED (its suggestions 1-4, 6; two of its claims were checked
against the code and REFUTED first — recorded here so the record carries both):
  * "the 09:00 hour is the premarket 09:00-09:30 cell" — FALSE. v1's window filter passes PRE
    only to 09:20 and RTH from 09:30, so bucket 09 is a MIX. Split explicitly below (CUT 3).
  * "run flat_top on today's tape" — not from the cache: the ferry stops at 2026-08-18. Needs
    the trades path; out of scope here and named as debt.

CUTS
  1 BASELINE, one shared book: all / PRE / OPEN / MID.
  2 FILL-MODEL SENSITIVITY: +1 tick adverse entry on every fill. The audit predicted OPEN
    survives easily, MID halves, PRE dies. Tested, not assumed.
  3 HOUR x SESSION, unmixed: 09:00-09:20 PRE vs 09:30-09:59 RTH, then hourly to 15:59.
  4 CONCENTRATION: drop-best-NAME, top-5 name share of P&L. The audit's bar: top-5 under ~25%
    or the lane is a hot-name artifact of one 22-day regime.
  5 EXITS BY HOUR: E3 (house) vs POP8 (bank at +8%) vs T20 (20-min time stop), per block. A
    67%-win morning and a 45%-win midday should not share one engine by assumption.
  6 CAPACITY-REALISTIC RE-BOOK: top-N fires per day by base tightness (the audit's suggestion
    that Q3's monotone width result is also the ranking signal), N in {2,4,6,10,all}. Live takes
    ~14 trades/day TOTAL across all lanes, so N<=6 is the honest range for one lane.
  7 REGIME: per-day P&L table, worst days named. 22 days is ONE August tape and the gauntlet
    must weight the worst cells, not the average.

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  V1 The OPEN cell survives the retrial iff it stays positive at BOTH books, BOTH halves,
     drop-best AND drop-best-NAME, at +1 tick, in the top-6/day re-book. Anything less and the
     unrestriction case is not made.
  V2 A cell whose top-5 names supply >40% of its P&L is reported as REGIME-DEPENDENT regardless
     of totals.
  V3 An exit only replaces E3 for a block if it wins that block on BOTH halves.
  V4 Nothing ships from this file. Restriction lift requires the hostile-tape gauntlet and a
     Blast Radius pass afterwards.

STANDING DENSITY BOUND (v1 positive control, XOS 8/18): the replay fired 75x vs live's 7 on
that name-day; across the cohort 29,057 raw fires vs 1,213 live-logged in the same period ~ 24x.
TOTAL dollars are inflated by roughly that factor and are NOT revenue. Per-fill expectancy and
the top-N re-book are the trustworthy columns.
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


def walk(b, i0, entry, stop, pre, spr, arm="E3", extra_tick=0.0):
    px = entry + (spr / 2 if spr else entry * 0.005) + extra_tick
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(max(BOOKS) * 0.70 / px), int(1000 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    half = (spr / 2 if spr else px * 0.0025)
    flat = "09:25" if pre else "15:45"
    t0 = None
    for i in range(i0 + 1, len(b)):
        x = b[i]
        t = et_hm(x["t"])
        if t0 is None:
            t0 = i
        if t >= flat:
            return banked + rem * ((x["c"] - half) - px), sh * px, i
        if x["l"] <= stop:
            return banked + rem * ((stop - half) - px), sh * px, i
        runhi = max(runhi, x["h"])
        if arm == "POP8":
            if x["h"] >= px * 1.08:
                return banked + rem * (px * 1.08 - px), sh * px, i
        else:
            if not tiered and x["h"] >= px * 1.10:
                n = rem // 2 or rem
                banked += n * (px * 1.10 - px)
                rem -= n
                tiered, stop = True, px
                if rem == 0:
                    return banked, sh * px, i
        if arm == "T20" and (i - i0) >= 120:      # 120 x 10s = 20 min
            return banked + rem * ((x["c"] - half) - px), sh * px, i
        if arm == "E3" and tiered and x["c"] <= runhi * 0.90:
            return banked + rem * ((x["c"] - half) - px), sh * px, i
    return banked + rem * ((b[-1]["c"] - half) - px), sh * px, len(b) - 1


def book_once(fills, bal, key="pnl", cap_per_day=None, rank=None):
    """ONE shared-capital book over the WHOLE cohort (D1 fix). Returns the TAKEN fills so every
    cut downstream is a slice of the same book, not its own privileged pool."""
    byday = collections.defaultdict(list)
    for f in fills:
        byday[f["d"]].append(f)
    taken = []
    for d, l in byday.items():
        l = sorted(l, key=lambda x: x["ti"])
        if cap_per_day:
            keep = sorted(l, key=rank)[:cap_per_day] if rank else l[:cap_per_day]
            l = sorted(keep, key=lambda x: x["ti"])
        op, n = [], 0
        for f in l:
            op = [o for o in op if o[0] > f["ti"]]
            if f["n"] > bal - sum(o[1] for o in op):
                continue
            op.append((f["tx"], f["n"]))
            taken.append(f)
    return taken


def stat(fl, key="pnl"):
    if not fl:
        return None
    tot = sum(f[key] for f in fl)
    tr_ = sum(f[key] for f in fl if int(f["d"][-2:]) % 2 == 0)
    oo = sum(f[key] for f in fl if int(f["d"][-2:]) % 2 == 1)
    p = sorted((f[key] for f in fl), reverse=True)
    byname = collections.Counter()
    for f in fl:
        byname[f["sym"]] += f[key]
    best_name = byname.most_common(1)[0] if byname else ("-", 0)
    top5 = sum(v for _, v in byname.most_common(5))
    return {"n": len(fl), "tot": tot, "per": tot / len(fl), "tr": tr_, "oos": oo,
            "wo_best": tot - p[0], "wo_name": tot - best_name[1], "best_name": best_name[0],
            "top5_share": (100 * top5 / tot) if tot else 0,
            "win": 100 * sum(1 for x in p if x > 0) / len(p)}


HDR = (f"{'cut':>26s} {'n':>5s} {'total$':>11s} {'$/fill':>8s} {'TRAIN':>10s} {'OOS':>10s} "
       f"{'w/o best':>10s} {'w/o name':>10s} {'top5%':>6s} {'win%':>5s}")


def show(lab, fl, key="pnl"):
    s = stat(fl, key)
    if not s:
        print(f"{lab:>26s}     0   (empty)")
        return
    print(f"{lab:>26s} {s['n']:5d} {s['tot']:+11.2f} {s['per']:+8.2f} {s['tr']:+10.2f} "
          f"{s['oos']:+10.2f} {s['wo_best']:+10.2f} {s['wo_name']:+10.2f} "
          f"{s['top5_share']:5.0f}% {s['win']:4.0f}%")


def main():
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
    fills = []
    print(f"name-days: {len(days)}", flush=True)
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
        except Exception:
            continue
        if n_ % 150 == 0:
            print(f"  [{n_}/{len(days)}] fires so far {len(fills)}", flush=True)
        for f in fires:
            i = f.get("i")
            if i is None or not f.get("w_low") or not f.get("w_high"):
                continue
            t = et_hm(b[i]["t"])
            pre = t < "09:30"
            if pre and not ("07:00" <= t <= "09:20"):
                continue
            if not pre and not ("09:30" <= t < "15:30"):
                continue
            e, stop = float(f["price"]), float(f["w_low"])
            if e <= stop or (e - stop) / e * 100 < MIN_STOP_PCT:
                continue
            spr = HF.spread_at(sym, d, t)
            if SPREAD_K > 0 and spr and (e - stop) < SPREAD_K * spr:
                continue
            row = {"d": d, "sym": sym, "t": t, "hh": int(t[:2]), "pre": pre,
                   "px": e, "stop": stop, "rng": f.get("rng"), "spr": spr,
                   "ti": dt.datetime.fromisoformat(str(b[i]["t"])[:19]).timestamp()}
            for arm in ("E3", "POP8", "T20"):
                w = walk(b, i, e, stop, pre, spr, arm)
                if w:
                    row[f"pnl_{arm}"] = w[0]
                    if arm == "E3":
                        row["n"], row["tx"] = w[1], dt.datetime.fromisoformat(
                            str(b[w[2]]["t"])[:19]).timestamp()
            w1 = walk(b, i, e, stop, pre, spr, "E3", extra_tick=(spr or e * 0.005))
            if w1:
                row["pnl_tick"] = w1[0]
            if "pnl_E3" in row:
                fills.append(row)
    print(f"\ngradeable fills: {len(fills)} | quotes {HF._qgap[1]} gaps {HF._qgap[0]}", flush=True)
    json.dump(fills, open(os.path.join(HERE, "flattop_v2_20260821_out.json"), "w"), default=str)

    TAKEN = book_once(fills, 5000.0)
    T3 = book_once(fills, 3000.0)
    print(f"\nONE SHARED BOOK: taken@5k {len(TAKEN)} | taken@3k {len(T3)}  "
          f"(v1 booked each cut separately — that is D1, fixed here)")

    print("\n=== CUT 1: BASELINE (one shared book, E3) ===")
    print(HDR)
    show("ALL", TAKEN)
    show("PRE 07:00-09:20", [f for f in TAKEN if f["pre"]])
    show("OPEN 09:30-10:30", [f for f in TAKEN if not f["pre"] and f["t"] < "10:30"])
    show("MID 10:30-15:30", [f for f in TAKEN if not f["pre"] and f["t"] >= "10:30"])
    s3 = stat(T3)
    print(f"{'ALL @ $3,000':>26s} {s3['n']:5d} {s3['tot']:+11.2f} {s3['per']:+8.2f}")

    print("\n=== CUT 2: FILL-MODEL SENSITIVITY (+1 tick adverse entry) ===")
    print(HDR)
    tk = [f for f in TAKEN if "pnl_tick" in f]
    show("ALL +1 tick", tk, "pnl_tick")
    show("PRE +1 tick", [f for f in tk if f["pre"]], "pnl_tick")
    show("OPEN +1 tick", [f for f in tk if not f["pre"] and f["t"] < "10:30"], "pnl_tick")
    show("MID +1 tick", [f for f in tk if not f["pre"] and f["t"] >= "10:30"], "pnl_tick")

    print("\n=== CUT 3: HOUR x SESSION, UNMIXED (the audit's 09:00 claim, settled) ===")
    print(HDR)
    show("09:00-09:20 PRE", [f for f in TAKEN if f["pre"] and f["hh"] == 9])
    show("09:30-09:59 RTH", [f for f in TAKEN if not f["pre"] and f["hh"] == 9])
    for h in (7, 8, 10, 11, 12, 13, 14, 15):
        show(f"{h:02d}:00-{h:02d}:59", [f for f in TAKEN if f["hh"] == h])

    print("\n=== CUT 5: EXITS BY BLOCK (E3 vs POP8 vs T20) ===")
    print(HDR)
    for lab, sel in (("PRE", lambda f: f["pre"]),
                     ("OPEN", lambda f: not f["pre"] and f["t"] < "10:30"),
                     ("MID", lambda f: not f["pre"] and f["t"] >= "10:30")):
        for arm in ("E3", "POP8", "T20"):
            show(f"{lab} {arm}", [f for f in TAKEN if sel(f) and f"pnl_{arm}" in f], f"pnl_{arm}")

    print("\n=== CUT 6: CAPACITY-REALISTIC RE-BOOK (top-N/day by TIGHTEST base) ===")
    print(HDR)
    for N in (2, 4, 6, 10, None):
        sub = book_once(fills, 5000.0, cap_per_day=N, rank=lambda x: (x["rng"] is None, x["rng"]))
        show(f"top-{N or 'all'}/day", sub)
        show(f"  of which OPEN", [f for f in sub if not f["pre"] and f["t"] < "10:30"])

    print("\n=== CUT 7: REGIME — per-day P&L (E3, shared book) ===")
    byday = collections.Counter()
    for f in TAKEN:
        byday[f["d"]] += f["pnl_E3"]
    for d in sorted(byday):
        print(f"   {d} {byday[d]:+10.2f}")
    worst = sorted(byday.items(), key=lambda x: x[1])[:3]
    print(f"   WORST DAYS: {worst}")
    print(f"   green {sum(1 for v in byday.values() if v>0)}/{len(byday)}")

    print("\nPRE-REGISTERED: V1 OPEN survives only if positive at both books, both halves,")
    print("drop-best AND drop-best-NAME, at +1 tick, in the top-6/day re-book. V2 top-5 names")
    print(">40% = REGIME-DEPENDENT. V3 an exit replaces E3 only on both halves. V4 nothing ships.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
