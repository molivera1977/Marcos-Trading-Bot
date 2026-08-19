#!/usr/bin/env python3
"""
DIP_RIP RE-ANCHOR SWEEP (8/19, Marcos: "run the sweep now")

QUESTION: dip_rip's tag zone is anchored to a STATIC level; a halt ladder re-floors the stock
every rung, so the flush-to-level the lane waits for becomes unreachable (ZSTK 8/19: five rungs,
zero reachable; re-anchored, rung 5 tagged to the cent and paid +$35.14 through E3). Re-anchoring
is existing house doctrine (8/6 freshest-data; the auto-map; kevseq legs) — this sweep measures
whether applying it to dip_rip earns or loses across EVERY halt in the cache.

ARMS (both use dip_rip's spec verbatim: TAG = a post-resume bar's low enters [level, level*1.05]
with close >= level; CONFIRM/FIRE = a later up-close >= level (proxied c > prior c; the cache loader strips opens); retire on close < level*0.98 or
600s window; fire -> E3 with stop = level*0.99):
  A STATIC    — level frozen at the DAY'S FIRST halt's pre-gap close (proxy for the morning
                sheet ink; per-day historical sheet levels are not reconstructable — stated).
  B RE-ANCHOR — level = the last traded close before EACH halt's gap.

CENSUS (pre-registered secondary): classify every reopen —
  gap_and_go   : no bar low within the tag zone inside the window
  dip_and_hold : TAG occurs and price does not decisively break the level first
  flush_through: first zone contact is a close BELOW level*0.98
  ... and test the ZSTK observation that later rungs dip more than early rungs.

READING (pre-registered): B is the winner iff B's E3 total > A's AND B's per-fire $/tr > 0.
Halts = >=120s print gaps inside 09:30-16:00 on cached 10s tape (halt-suspect's own 120s rule);
premarket excluded (auction mechanics differ). One fire max per rung per arm.

LIMITS: gaps in a 10s SIP cache can be thin-tape silences, not LULD halts — names with < $50k
bar-volume around the gap are skipped to suppress that class; residual misclassification is
inherent and reported per-row, not hidden. Multi-day aggregate 2026-07-xx..2026-08-19 SPANS
CONFIG EPOCHS of the live bot, but this sweep executes NO live-bot code paths except the E3
walker convention (bank 1/2 @ +10%, BE, 10%-off-runhigh trail, slips -1%/-0.5%) — detector
logic is implemented here from the dip_rip spec, so epoch drift does not apply to the measured
arms. Sizing: $29.50 risk / $500 notional / 5% bar-volume cap, min 1 share. Nothing ships from
this file; the halt lane is Monday-config settled territory (Marcos rules on the artifact).
"""
import json
import os
import sys
import datetime as dt
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
ZONE, WIN, RETIRE = 0.05, 600, 0.98
_rr = open(os.path.join(HERE, "runway_refusal_replay_20260819.py")).read().split("def main()")[0]
ns = {"__file__": os.path.join(HERE, "runway_refusal_replay_20260819.py")}
exec(_rr, ns)
e3, hms, bars_for = ns["e3"], ns["hms"], ns["bars_for"]


def ep(t):
    return dt.datetime.fromisoformat(str(t)[:19]).timestamp()


def sweep_day(raw):
    """Return per-rung rows: (rung_idx, resume_hms, static_verdict, reanchor_verdict, pnls)."""
    out = []
    first_level = None
    rung = 0
    for i in range(1, len(raw)):
        gap = ep(raw[i]["t"]) - ep(raw[i - 1]["t"])
        if gap < 120 or not ("09:30:00" <= hms(raw[i]["t"]) < "15:45:00"):
            continue
        # thin-tape suppression: demand real dollar volume near the gap
        _near = raw[max(0, i - 6):i + 6]
        if sum(b["c"] * b["v"] for b in _near) < 50000:
            continue
        rung += 1
        lvl_re = raw[i - 1]["c"]
        if first_level is None:
            first_level = lvl_re
        row = {"rung": rung, "resume": hms(raw[i]["t"]), "gap_min": round(gap / 60, 1)}
        for arm, lvl in (("static", first_level), ("reanchor", lvl_re)):
            zone_hi = lvl * (1 + ZONE)
            t0 = ep(raw[i]["t"])
            tag = None
            kind, fire = "gap_and_go", None
            j = i
            while j < len(raw) and ep(raw[j]["t"]) - t0 <= WIN:
                b = raw[j]
                if b["c"] < lvl * RETIRE:
                    kind = "flush_through" if tag is None else kind
                    break
                if tag is None and b["l"] <= zone_hi and b["c"] >= lvl:
                    tag, kind = j, "dip_and_hold"
                elif tag is not None and b["c"] > raw[j - 1]["c"] and b["c"] >= lvl:  # up-close proxy: c > prior c (loader strips opens; stated)
                    r = e3(raw, j, b["c"], lvl * 0.99)
                    if r:
                        fire = {"t": hms(b["t"]), "px": b["c"], "pnl": round(r[0], 2), "exit": r[2]}
                    break
                j += 1
            row[arm] = {"level": round(lvl, 4), "kind": kind, "fire": fire}
        out.append(row)
    return out


def main():
    days = defaultdict(list)
    for f in sorted(os.listdir(BARS)):
        if f.endswith(".json"):
            d, sym = f[:10], f[11:-5]
            days[(d, sym)] = None
    print(f"cache name-days: {len(days)}")
    rows = []
    for (d, sym) in sorted(days):
        try:
            b = bars_for(sym, d)
        except Exception:
            continue
        if not b or len(b) < 60:
            continue
        for r in sweep_day(b):
            r["sym"], r["date"] = sym, d
            rows.append(r)
    print(f"halt-rungs found (RTH, dollar-volume-screened): {len(rows)} "
          f"on {len({(r['date'], r['sym']) for r in rows})} name-days\n")

    for arm in ("static", "reanchor"):
        k = Counter(r[arm]["kind"] for r in rows)
        fires = [r[arm]["fire"] for r in rows if r[arm]["fire"]]
        tot = sum(f["pnl"] for f in fires)
        green = sum(1 for f in fires if f["pnl"] > 0)
        print(f"ARM {arm.upper():9s} reopen census {dict(k)}")
        print(f"              fires n={len(fires)}  total ${tot:+9.2f}  "
              f"{'$%+.2f/tr' % (tot / len(fires)) if fires else '-'}  "
              f"green {green}/{len(fires)}")
    print()
    # the ZSTK ordering observation: do later rungs dip more?
    byr = defaultdict(Counter)
    for r in rows:
        byr[min(r["rung"], 4)][r["reanchor"]["kind"]] += 1
    print("reopen type by rung index (re-anchor arm; 4 = 4th-or-later):")
    for k in sorted(byr):
        tot = sum(byr[k].values())
        dip = byr[k]["dip_and_hold"]
        print(f"  rung {k}: n={tot:3d}  dip_and_hold {100*dip/tot:.0f}%  {dict(byr[k])}")
    out = os.path.join(HERE, "diprip_reanchor_sweep_20260819_out.json")
    json.dump(rows, open(out, "w"), indent=1)
    print(f"\nper-rung rows saved: {out}")
    print("READING per pre-registration: re-anchor wins iff B total > A total AND B $/tr > 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
