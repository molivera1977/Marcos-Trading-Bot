#!/usr/bin/env python3
"""
RUNWAY ON BIG RUNNERS — three arms (8/19, Marcos: "what can be done regarding runway for big
runners" -> "run it")

THE FAILURE THIS TARGETS: on a name in price discovery the map's ink sits BEHIND the tape.
TNON 8/19 09:35 fired $12.36 with the next marked level at $12.75 (3% overhead) on a +107% day
making fresh highs; runway computed 0.21R and refused; the tape ran to $17.00. The arithmetic
was right and the CEILING was fiction. Distinct from SKK 10:29 (real ceiling, held, -35% avoided)
— the live gate cannot tell them apart. `above_all_levels` already exists as a bimodal pass for
entries above ALL ink; these arms ask whether the NEAR-MISS case should resolve there too.

ARMS (all replay the SAME refused fires; live = refuse everything = $0 by construction):
  LIVE  refuse all runway_reject rows.                                  baseline $0
  A     STALE-RUNG DEMOTION: take the fire only if the overhead target is <= A_NEAR% above
        entry AND the name is at/near its session high at the fire (>= A_HIGH x session high
        from the tape) — i.e. the only thing overhead is a rung the tape is actively taking out,
        the same logic the 8/8 WALL already applies to rungs price has ALREADY traded through.
  B     RUNNER EXEMPTION: take the fire only if tape-derived day-run >= B_GAIN% (price vs the
        session's first cached bar) — the blunt strength carve-out.

PRE-REGISTERED READING (written before the run): an arm WINS only if
  (1) its E3 total > $0 (beats live refuse-all), AND
  (2) it does NOT take the SKK-class saves — defined as: every fire whose LIVE-replay E3 is
      <= -$20 must remain REFUSED by the arm. One such take = disqualified, reported not hidden.
Both must hold. A positive total achieved by also swallowing the big losers is not a win.

EXITS/SIZING: the shared E3 walker (bank 1/2 @ +10%, BE, 10%-off-runhigh trail, stop-first
intrabar, -1%/-0.5% slips), $29.50 risk / $500 notional / 5%-bar-volume cap, min 1 share.
Stop = the row's own recorded stop (all 63+ rows carry it since the 8/19 instrumentation fix).

LIMITS: window 2026-08-12..2026-08-19 SPANS CONFIG EPOCHS (kevseq shipped 8/17, session map
8/19, relvol disarmed 8/19) — the refused COHORT therefore mixes machines; this measures the
gate's counterfactual on the fires that actually occurred, not a stable-population edge.
Day-run is a tape proxy (first cached bar of the session), not the bot's prior-close day_gain.
Session high is computed from the same 10s cache. n is small; a single fire can flip an arm.
Nothing ships from this file.
"""
import json
import os
import sys
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
D = "https://zestful-intuition-production-b16a.up.railway.app"
H = {"X-Dashboard-Secret": "marcos2026"}
DATES = ["2026-08-12", "2026-08-13", "2026-08-14", "2026-08-17", "2026-08-18", "2026-08-19"]
A_NEAR, A_HIGH = 5.0, 0.995     # target within 5% overhead AND price >= 99.5% of session high
B_GAIN = 50.0                   # tape-derived day-run threshold for the blunt arm
SAVE_CUT = -20.0                # SKK-class: an arm must not take fires this bad

_rr = open(os.path.join(HERE, "runway_refusal_replay_20260819.py")).read().split("def main()")[0]
ns = {"__file__": os.path.join(HERE, "runway_refusal_replay_20260819.py")}
exec(_rr, ns)
bars_for, e3, hms = ns["bars_for"], ns["e3"], ns["hms"]


def main():
    rej = []
    for d in DATES:
        r = urllib.request.Request(f"{D}/api/decisions_archive?date={d}&limit=50000", headers=H)
        for x in (json.load(urllib.request.urlopen(r, timeout=180)).get("rows") or []):
            if x.get("status") == "runway_reject" and x.get("price") and x.get("stop"):
                rej.append((d, x))
    print("=" * 100)
    print("RUNWAY ON BIG RUNNERS — LIVE (refuse-all) vs A (stale-rung demotion) vs B (runner exemption)")
    print("=" * 100)
    print(f"runway_reject rows with price+stop: {len(rej)} over {len(DATES)} sessions\n")

    cache, rows = {}, []
    for d, x in rej:
        sym, t = x["ticker"], str(x.get("time"))[:8]
        px, stop = float(x["price"]), float(x["stop"])
        tgt = float(x.get("target") or 0)
        if stop >= px:
            continue
        key = (sym, d)
        if key not in cache:
            cache[key] = bars_for(sym, d)
        b = cache[key]
        if not b:
            continue
        i0 = next((i for i, y in enumerate(b) if hms(y["t"]) >= t), None)
        if i0 is None or i0 >= len(b) - 2:
            continue
        sess_hi = max(y["h"] for y in b[:i0 + 1])
        first = b[0]["c"] or px
        day_run = (px / first - 1) * 100.0 if first > 0 else 0.0
        near_pct = ((tgt / px - 1) * 100.0) if tgt > px else 0.0
        r = e3(b, i0, px, stop)
        if not r:
            continue
        rows.append({"d": d, "sym": sym, "t": t, "px": px, "tgt": tgt, "rr": x.get("runway_rr"),
                     "cls": x.get("road_cls"), "machine": x.get("machine"), "pnl": round(r[0], 2),
                     "near_pct": round(near_pct, 2), "at_high": px >= sess_hi * A_HIGH,
                     "day_run": round(day_run, 1)})
    print(f"graded: {len(rows)}\n")

    def arm(label, pred):
        take = [r for r in rows if pred(r)]
        tot = sum(r["pnl"] for r in take)
        bad = [r for r in take if r["pnl"] <= SAVE_CUT]
        green = sum(1 for r in take if r["pnl"] > 0)
        print(f"{label:34s} takes {len(take):3d}/{len(rows)}  total ${tot:+8.2f}  "
              f"{('$%+.2f/tr' % (tot/len(take))) if take else '   -    '}  "
              f"green {green}/{len(take)}  SKK-class taken: {len(bad)}")
        for r in sorted(take, key=lambda z: -abs(z["pnl"]))[:4]:
            print(f"      {r['d']} {r['sym']:6s} {r['t']} {str(r['machine']):11s} "
                  f"rr={r['rr']} near={r['near_pct']}% run={r['day_run']}% -> ${r['pnl']:+.2f}")
        return tot, len(bad), len(take)

    print("LIVE (refuse all)                  takes   0/%d  total $   +0.00   (baseline)\n" % len(rows))
    ta, bada, na = arm("A stale-rung demotion", lambda r: r["at_high"] and 0 < r["near_pct"] <= A_NEAR)
    print()
    tb, badb, nb = arm("B runner exemption (>=%.0f%% run)" % B_GAIN, lambda r: r["day_run"] >= B_GAIN)
    print()
    print("=" * 100)
    print("PRE-REGISTERED VERDICT (win = total > $0 AND zero SKK-class takes):")
    for lab, tot, bad, n in (("A", ta, bada, na), ("B", tb, badb, nb)):
        ok = tot > 0 and bad == 0
        why = "WINS" if ok else ("total <= 0" if tot <= 0 else f"took {bad} SKK-class loser(s)")
        print(f"  {lab}: ${tot:+8.2f}  n={n:3d}  -> {'WIN' if ok else 'NO'}  ({why})")
    print("\nLIMITS: see the module docstring — mixed config epochs, tape-proxy day-run, small n.")
    json.dump(rows, open(os.path.join(HERE, "runway_runner_arms_20260819_out.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
