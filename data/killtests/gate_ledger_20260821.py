#!/usr/bin/env python3
"""
THE GATE LEDGER — every refusal and shadow, 19 days, priced in dollars (8/21, Marcos: "launch it")

WHY THIS EXISTS. The nightly 16:37 grading answers one day. Tonight it produced a headline —
`pullback_first_suppress` SAVED $412.80 in premarket and COST $534.08 in RTH, the largest line
on both sides — off 199 rows from a single no-follow-through tape. That is a LEAD, not a
finding, and this project has been burned before by promoting a one-day anecdote (the 8/20
one-day spread ladder said k=3; at scale it was k=1). This file runs the same walk over the
whole archive so no single session can carry a verdict.

COHORT: every archive row 7/28-8/21 that (a) carries BOTH a price and a stop with price > stop,
and (b) is a refusal (`*_reject`, `*_skip`, `*_block*`, `*_restricted`, `*_observe_only`,
`*refus*`, `*suppress*`), a `triggered_*` fire, or a `*_shadow_fire`. Sized 8,088 rows across
19 trading days before this file was written. Entry and stop are AS THE LANE STAMPED THEM — no
hindsight re-derivation, the same discipline as the dip_rip and runway studies.

METHOD: real fire-minute NBBO spread charged (entry and stop/market exits pay half, resting
limit tiers free), 1% width floor and k=1 spread guard as shipped, E3 exits, $30 risk with the
70%/$1000 clamp, $5,000 book, TOTAL DOLLARS (the 8/20 law). Tape from the SIP trades feed
bucketed to 10s — the builder every run this week used, positive-controlled on 8/20 and 8/21.

READ THE SIGN CONVENTION CAREFULLY: a POSITIVE number means the refused trade WOULD HAVE MADE
money, i.e. the gate COST us. A NEGATIVE number means the gate SAVED us. Sorted ascending, the
best gates come first.

CUTS
  1 EVERY GATE, whole archive: total, $/row, both halves, drop-best, win%.
  2 SESSION SPLIT per gate: PRE vs RTH on separate lines (Marcos's standing doctrine, and the
    exact axis tonight's lead lives on).
  3 PER-DAY for the top movers: does the gate's sign FLIP day to day, or hold?
  4 `pullback_first_suppress` in full — the lane it suppresses, by session, by half.

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  G1 A gate is EXPENSIVE only if its refused set is POSITIVE in total dollars, on BOTH halves,
     AND survives dropping its single best trade. One-sided or tail-driven = NOT expensive.
  G2 A gate is SESSION-DEPENDENT only if PRE and RTH disagree in SIGN and each side holds on
     both halves. Tonight's pullback_first_suppress lead is exactly this claim, and this run
     either confirms it or retires it.
  G3 Ranking for the weekend edge-widening list is by TOTAL DOLLARS at stake (absolute value),
     not by $/row — a gate that costs $30/row on 4 rows is not a program.
  G4 Nothing ships from this file.

LIMITS: refused trades never competed for capital against the trades actually TAKEN, so these
books are optimistic about slot availability; median-of-minute spreads; no crown/slot
re-simulation; a `triggered_*` row that DID fill is graded too (it is the counterfactual of
itself and shows as the fill's own outcome) — the gate cuts are what matter here.
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
RISK, BAL = 30.0, 5000.0
MIN_STOP_PCT, SPREAD_K = 1.0, 1.0
REJ = ("reject", "skip", "block", "restrict", "observe_only", "refus", "suppress")

sq = importlib.util.spec_from_file_location("HF", os.path.join(HERE, "halt_arm_feed_20260820.py"))
HF = importlib.util.module_from_spec(sq)
sq.loader.exec_module(HF)


def rows():
    out = []
    for i in range(0, 26):
        d = (dt.date(2026, 8, 21) - dt.timedelta(days=i)).isoformat()
        try:
            rs = json.load(urllib.request.urlopen(
                f"{BOARD}/api/decisions_archive?date={d}&limit=50000&key=marcos2026",
                timeout=45)).get("rows") or []
        except Exception:
            continue
        for r in rs:
            s = str(r.get("status") or "")
            px, st = r.get("price"), r.get("stop")
            tk, ts = r.get("ticker"), str(r.get("recorded_at") or "")
            if not (tk and ts and px and st):
                continue
            try:
                px, st = float(px), float(st)
            except Exception:
                continue
            if px <= st or st <= 0:
                continue
            if not (any(w in s for w in REJ) or s.startswith("triggered_")
                    or "shadow_fire" in s):
                continue
            t = ts[11:16]
            out.append({"d": d, "tk": tk, "ts": ts[11:19], "t": t, "gate": s,
                        "px": px, "stop": st,
                        "lane": str(r.get("lane") or r.get("entry_type")
                                    or r.get("machine") or "?"),
                        "sess": "PRE" if t < "09:30" else "RTH"})
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
    sh = max(1, min(int(RISK / rps), int(BAL * 0.70 / px), int(1000 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    flat = "09:25" if pre else "15:45"
    for k in ks[1:]:
        x = b10[k]
        if HF.hm_k(k) >= flat:
            return banked + rem * ((x["c"] - half) - px)
        if x["l"] <= stop:
            return banked + rem * ((stop - half) - px)
        runhi = max(runhi, x["h"])
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 - px)
            rem -= n
            tiered, stop = True, px
            if rem == 0:
                return banked
        if tiered and x["c"] <= runhi * 0.90:
            return banked + rem * ((x["c"] - half) - px)
    return banked + rem * ((b10[ks[-1]]["c"] - half) - px)


def st_(fl):
    if not fl:
        return None
    tot = sum(f["pnl"] for f in fl)
    tr_ = sum(f["pnl"] for f in fl if int(f["d"][-2:]) % 2 == 0)
    oo = sum(f["pnl"] for f in fl if int(f["d"][-2:]) % 2 == 1)
    p = sorted((f["pnl"] for f in fl), reverse=True)
    return {"n": len(fl), "tot": tot, "per": tot / len(fl), "tr": tr_, "oos": oo,
            "wo": tot - p[0], "win": 100 * sum(1 for x in p if x > 0) / len(p)}


HDR = (f"{'gate':>32s} {'n':>5s} {'total$':>10s} {'$/row':>8s} {'TRAIN':>9s} {'OOS':>9s} "
       f"{'w/o best':>9s} {'win%':>5s}")


def line(lab, fl):
    s = st_(fl)
    if not s:
        print(f"{lab:>32s}     0   (empty)")
        return
    print(f"{lab:>32s} {s['n']:5d} {s['tot']:+10.2f} {s['per']:+8.2f} {s['tr']:+9.2f} "
          f"{s['oos']:+9.2f} {s['wo']:+9.2f} {s['win']:4.0f}%")


def main():
    rs = rows()
    print(f"rows to grade: {len(rs)}  ({min(r['d'] for r in rs)} -> {max(r['d'] for r in rs)})",
          flush=True)
    bynd = collections.defaultdict(list)
    for r in rs:
        bynd[(r["d"], r["tk"])].append(r)
    print(f"name-days to fetch: {len(bynd)}\n", flush=True)

    graded = []
    for i, ((d, tk), l) in enumerate(sorted(bynd.items()), 1):
        lo = min(x["ts"] for x in l)
        tr = HF.trades(tk, d, lo, "15:50:00")
        if i % 25 == 0:
            print(f"  [{i}/{len(bynd)}] graded so far {len(graded)}", flush=True)
        if len(tr) < 50:
            continue
        b10 = HF.bars(tr, 10)
        ks = sorted(b10)
        for r in l:
            if (r["px"] - r["stop"]) / r["px"] * 100 < MIN_STOP_PCT:
                continue
            spr = HF.spread_at(tk, d, r["t"])
            if SPREAD_K > 0 and spr and (r["px"] - r["stop"]) < SPREAD_K * spr:
                continue
            pre = r["sess"] == "PRE"
            if pre and not ("07:00" <= r["t"] <= "09:20"):
                continue
            if not pre and not ("09:30" <= r["t"] < "15:30"):
                continue
            ep = dt.datetime.fromisoformat(f"{d}T{r['ts']}+00:00").timestamp() + 4 * 3600
            k0 = min((x for x in ks if x >= ep), default=None)
            if k0 is None:
                continue
            p = walk(b10, k0, r["px"], r["stop"], spr, pre)
            if p is None:
                continue
            graded.append(dict(r, pnl=p))
    print(f"\nwalked {len(graded)} of {len(rs)} | quotes {HF._qgap[1]} gaps {HF._qgap[0]}\n")
    json.dump(graded, open(os.path.join(HERE, "gate_ledger_20260821_out.json"), "w"),
              default=str)

    bygate = collections.defaultdict(list)
    for g in graded:
        bygate[g["gate"]].append(g)

    print("=== CUT 1: EVERY GATE, 19 DAYS ===")
    print("NEGATIVE = the gate SAVED money.  POSITIVE = the gate COST money.")
    print(HDR)
    for gate, l in sorted(bygate.items(), key=lambda x: sum(f["pnl"] for f in x[1])):
        if len(l) < 5:
            continue
        line(gate, l)

    print("\n=== CUT 2: SESSION SPLIT (top 12 gates by dollars at stake) ===")
    print(HDR)
    rank = sorted(bygate.items(), key=lambda x: -abs(sum(f["pnl"] for f in x[1])))
    for gate, l in rank[:12]:
        line(gate, l)
        for sess in ("PRE", "RTH"):
            sub = [f for f in l if f["sess"] == sess]
            if sub:
                line(f"    {sess}", sub)

    print("\n=== CUT 4: pullback_first_suppress IN FULL (tonight's lead) ===")
    print(HDR)
    pfs = bygate.get("pullback_first_suppress", [])
    line("ALL", pfs)
    for sess in ("PRE", "RTH"):
        line(f"  {sess}", [f for f in pfs if f["sess"] == sess])
    byday = collections.Counter()
    for f in pfs:
        byday[f["d"]] += f["pnl"]
    print("   per-day:", " ".join(f"{d[5:]}:{v:+.0f}" for d, v in sorted(byday.items())))
    print(f"   days positive (gate COST): {sum(1 for v in byday.values() if v>0)}/{len(byday)}")

    print("\nPRE-REGISTERED: G1 expensive iff positive on BOTH halves AND drop-best. G2 session-")
    print("dependent iff PRE and RTH disagree in SIGN with each side holding both halves. G3 rank")
    print("by dollars at stake, not $/row. G4 nothing ships from this file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
