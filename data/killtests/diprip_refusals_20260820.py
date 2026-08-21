#!/usr/bin/env python3
"""
DIP_RIP — GRADING ALL 83 REFUSALS IN DOLLARS (8/20 night, Marcos: "lets look at dip_rip" -> "build it")

WHAT THE CENSUS FOUND (live archive, 7/28-8/20, run tonight): the lane is NOT short of setups.
252 arms -> 121 tags -> 83 triggers -> 1 fill. Eighty-two triggers died at the door:
  minstop 25 (30%) · momentum/illiquid 14 (17%) · unknown 13 · runway 12 (14%) · spread 7
  · freshness 5 · chart_gate 4 · restricted/outranked 2 · FILL 1
Stop width at trigger: median 4.44%, n=83; only 10 are under 1%, but 34 are under 4% — and the
min-stop floor WAS 4% for that whole history and became 1% today (Addendum 14). So the lane's
single biggest killer was retired hours ago and nobody has re-measured it.

Also on the docket entry for this lane: "dip_rip blocked on MAP ARCHIVING". It is NOT blocked
for THIS question. The trigger row carries its own `level`, `price` and `stop` — the map is
already stamped on the evidence, so the counterfactual needs no historical map store.

THE QUESTION: with the trade the lane WANTED to take, walked on the real tape at real costs
under TODAY's config — what is each refusing gate actually worth, in dollars?

METHOD
  Cohort      every triggered_dip_rip row 7/28-8/20 (83), each tagged with the gate that killed
              it (the first kill-status row for that ticker at/after the trigger).
  Entry/stop  AS THE LANE STAMPED THEM. No re-derivation — the row is the lane's own intent.
  Bars        built from the Alpaca trades tape (the bars endpoint has no sub-minute timeframe;
              probed 8/20 -> HTTP 400), 10s buckets, trigger -> 15:50 ET.
  Exits       E3: +10% tier trims half and moves stop to entry, 10% give-back off the running
              high, 15:45 flat. Same engine as the halt run tonight.
  Costs       real median NBBO spread of the trigger minute; entry and stop/market exits pay
              half, limit tiers free.
  Config      TODAY's shipped gates applied as filters: MIN_STOP 1% and the k=1 spread guard.
              Rows failing those are reported SEPARATELY as "still refused today" — they are
              not counted in the money, because the live bot would not take them either.
  Sizing      $30 risk, 70%/$1000 clamp, capital-aware, no per-day cap; $3,000 and $5,000.
  Verdict     TOTAL DOLLARS per gate cohort (the 8/20 law); $/trade diagnostic only.

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  1. A gate is EXPENSIVE iff the trades it refused total POSITIVE dollars that survive dropping
     the single best trade. A gate is EARNING ITS KEEP iff its refused set is negative.
  2. The min-stop cohort is split at the OLD 4% floor vs the NEW 1% floor: the money sitting
     between 1% and 4% is what today's ruling already unlocked, and is reported on its own line.
  3. Nothing ships from this file. It writes JSON and prints.

LIMITS: entry at the trigger bar's stamped price + half spread (the lane's own fill assumption,
not a modelled queue); no crown/slot contention re-simulated beyond capital; the 13 "unknown"
kills are graded as their own cohort and must not be read as any one gate's fault; n per cohort
is small — the per-trade dump is printed so single-trade cohorts are visible as such.
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
MIN_STOP_PCT, SPREAD_K = 1.0, 1.0        # shipped today / tonight

sp = importlib.util.spec_from_file_location("HF", os.path.join(HERE, "halt_arm_feed_20260820.py"))
HF = importlib.util.module_from_spec(sp)
sp.loader.exec_module(HF)                 # reuse trades(), bars(), spread_at(), hm_k()

KILL = ("runway_reject", "minstop_reject", "chart_gate_blocked_trade", "lane_outranked",
        "momentum_reject", "spread_reject", "daygain_reject", "backside_reject",
        "lane_restricted", "retest_reject", "freshness_breach", "bad_stop_skip",
        "cap_reject", "dup_reject", "volume_reject", "liquidity_reject")
FILLED = ("entry_filled", "trade_opened", "position_opened", "filled")


def cohort():
    out = []
    for i in range(0, 25):
        d = (dt.date(2026, 8, 20) - dt.timedelta(days=i)).isoformat()
        try:
            rows = json.load(urllib.request.urlopen(
                f"{BOARD}/api/decisions_archive?date={d}&limit=50000&key=marcos2026",
                timeout=45)).get("rows") or []
        except Exception:
            continue
        for t in [r for r in rows if r.get("status") == "triggered_dip_rip"]:
            tk, ts = t.get("ticker"), str(t.get("recorded_at") or "")
            px, st = t.get("price"), t.get("stop")
            if not (tk and ts and px and st) or float(px) <= float(st):
                continue
            near = [r for r in rows if r.get("ticker") == tk
                    and str(r.get("recorded_at") or "") >= ts][:8]
            gate = "unknown"
            for r in near:
                s = r.get("status")
                if s in FILLED:
                    gate = "FILL"
                    break
                if s in KILL:
                    gate = s
                    break
            out.append({"d": d, "tk": tk, "ts": ts[11:19], "px": float(px),
                        "stop": float(st), "level": t.get("level"), "gate": gate})
    return out


def main():
    co = cohort()
    print(f"triggers graded: {len(co)}  days 7/28-8/20\n")
    for c in co:
        c["w"] = (c["px"] - c["stop"]) / c["px"] * 100
    res = []
    for i, c in enumerate(co, 1):
        t0 = dt.datetime.fromisoformat(f"{c['d']}T{c['ts']}")
        hi = dt.datetime.fromisoformat(f"{c['d']}T15:50:00")
        if hi <= t0:
            continue
        tr = HF.trades(c["tk"], c["d"], t0.strftime("%H:%M:%S"), hi.strftime("%H:%M:%S"))
        print(f"  [{i}/{len(co)}] {c['d']} {c['tk']} w={c['w']:.2f}% gate={c['gate']} "
              f"trades={len(tr)}", flush=True)
        if len(tr) < 50:
            c["skip"] = "no_tape"
            continue
        b10 = HF.bars(tr, 10)
        ks = sorted(b10)
        if not ks:
            c["skip"] = "no_bars"
            continue
        spr = HF.spread_at(c["tk"], c["d"], c["ts"][:5])
        c["spr"] = spr
        c["today_ok"] = (c["w"] >= MIN_STOP_PCT
                         and not (SPREAD_K > 0 and spr and (c["px"] - c["stop"]) < SPREAD_K * spr))
        r = HF.walk(b10, ks[0], c["px"], c["stop"], spr, max(BOOKS))
        if r is None:
            c["skip"] = "unwalkable"
            continue
        c["pnl"], c["n"], c["tx"], c["ti"] = r[0], r[1], r[2], ks[0]
        res.append(c)
    print(f"\nquote queries {HF._qgap[1]} | gaps {HF._qgap[0]}")

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

    live = [c for c in res if c.get("today_ok")]
    dead = [c for c in res if not c.get("today_ok")]
    print(f"\nWALKED {len(res)} | takeable under TODAY's gates {len(live)} | "
          f"still refused today (1% floor / k=1) {len(dead)}")

    print(f"\n{'gate that killed it':>26s} {'n':>4s} {'$5,000':>10s} {'$/tr':>8s} "
          f"{'w/o best':>9s} {'median w%':>9s}")
    by = collections.defaultdict(list)
    for c in live:
        by[c["gate"]].append(c)
    rowsout = {}
    for g, l in sorted(by.items(), key=lambda x: -sum(y["pnl"] for y in x[1])):
        t5, n5 = book(l, 5000.0)
        p = sorted((x["pnl"] for x in l), reverse=True)
        ws = sorted(x["w"] for x in l)
        rowsout[g] = {"n": len(l), "t5": t5, "wo_best": t5 - (p[0] if p else 0)}
        print(f"{g:>26s} {len(l):4d} {t5:+10.2f} {(t5/n5 if n5 else 0):+8.2f} "
              f"{t5 - (p[0] if p else 0):+9.2f} {ws[len(ws)//2]:8.2f}%")
    t5, n5 = book(live, 5000.0)
    t3, n3 = book(live, 3000.0)
    print(f"{'ALL TAKEABLE':>26s} {len(live):4d} {t5:+10.2f} "
          f"{(t5/n5 if n5 else 0):+8.2f}   (at $3,000: {t3:+.2f} / {n3} taken)")

    ms = [c for c in res if c["gate"] == "minstop_reject"]
    band = [c for c in ms if 1.0 <= c["w"] < 4.0]
    tb, nb = book(band, 5000.0)
    pb = sorted((x["pnl"] for x in band), reverse=True)
    print(f"\nTHE FLOOR RULING'S OWN LINE — min-stop refusals with width in [1%, 4%): "
          f"n={len(band)} taken={nb} {tb:+.2f} @ $5,000, without best {tb-(pb[0] if pb else 0):+.2f}")
    print(f"  (still refused at the new 1% floor: {sum(1 for c in ms if c['w'] < 1.0)} of {len(ms)})")

    print(f"\n{'date':>10s} {'tkr':>6s} {'time':>9s} {'w%':>6s} {'spread':>7s} "
          f"{'P&L':>9s}  gate")
    for c in sorted(live, key=lambda x: -abs(x["pnl"]))[:15]:
        print(f"{c['d']:>10s} {c['tk']:>6s} {c['ts']:>9s} {c['w']:6.2f} "
              f"{(c['spr'] or 0):7.4f} {c['pnl']:+9.2f}  {c['gate']}")

    json.dump({"gates": rowsout, "rows": res},
              open(os.path.join(HERE, "diprip_refusals_20260820_out.json"), "w"), default=str)
    print("\nPRE-REGISTERED: a gate is EXPENSIVE iff its refused set totals positive dollars that")
    print("survive dropping the best trade; EARNING ITS KEEP iff negative. Nothing ships here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
