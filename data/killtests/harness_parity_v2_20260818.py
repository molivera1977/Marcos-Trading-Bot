#!/usr/bin/env python3
"""HARNESS PARITY v2 — EXACT-FED-STREAM EQUIVALENCE (built 8/17, first usable 8/18).

WHY v2 EXISTS
-------------
harness_parity_20260817 measured 9% grinder / 30% kevseq / 51% v2 / 100% prevwap. Those
numbers are NOT interpretable as "the detector disagrees", because the two sides were not
fed the same bars: the harness replayed a reconstructed stream on a nominal 60s cadence
while the live machine fed whatever its cursor happened to hold on a jittered 48-72s
rescan. A miss could not be attributed between the DETECTOR and the FEED.

The A2 provenance stamps (shipped 2026-08-17: fire_k, fed_k0, fed_k1, fed_n on every 10s
shadow-fire and triggered row) remove that ambiguity. This script reads them and replays the
EXACT slice sequence the live bot fed, via live_harness.replay(fed_slices=...). Same bars,
same calls, same order -> any remaining disagreement is the detector, full stop.

It also de-duplicates the live side by (lane, ticker, fire_k) before grading. Before the A1
high-water-mark fix, a restart replayed already-consumed buckets and re-emitted historical
fires (8/17: 5 boots, 13 duplicate grinder rows, 14 v2, 1 bandpass), which inflated the live
denominator and therefore DEPRESSED every parity rate ever measured.

GATE 2 COMPLIANCE: this script hand-rolls nothing. Every detector is the bot's own function
object, obtained through live_harness.

USAGE
    python3 data/killtests/harness_parity_v2_20260818.py [YYYY-MM-DD] [arch.json] [tape_dir]

EXIT CODES: 0 = ran; 2 = the requested day's rows carry no provenance stamps (refuses to
produce an equivalence number it cannot support — see LIMITS in the .md).
"""
import collections
import contextlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import live_harness as H            # noqa: E402  (GATE 2: the bot's own detectors)

LANE_STATUS = {
    "kevseq":   ("kevseq_shadow_fire", "triggered_kevseq"),
    "grinder":  ("grinder_shadow_fire", "triggered_grinder"),
    "bandpass": ("bandpass_shadow_fire", "triggered_bandpass"),
    "prevwap":  ("prevwap_shadow_fire", "triggered_prevwap"),
    "v2":       ("v2_shadow_fire", "triggered_v2conv"),
}
PARITY_JSON = os.path.join(HERE, "harness_parity.json")


def et_secs(iso_s):
    t = str(iso_s)[11:19]
    return int(t[0:2]) * 3600 + int(t[3:5]) * 60 + int(t[6:8])


def stamped(r):
    """True iff the row carries the full A2 provenance quartet."""
    return all(r.get(k) for k in ("fire_k", "fed_k0", "fed_k1")) and r.get("fed_n") is not None


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else "2026-08-18"
    arch = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        HERE, "exit_params_our_fires_%s_arch.json" % day.replace("-", ""))
    tape = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "bars10s_%s_full" % day[5:].replace("-", ""))

    if not os.path.exists(arch):
        print("no archive at %s" % arch)
        return 2
    raw = json.load(open(arch))
    rows = raw["rows"] if isinstance(raw, dict) else raw

    by_lane = collections.defaultdict(list)
    for r in rows:
        for lane, statuses in LANE_STATUS.items():
            if r.get("status") == statuses[0]:      # the SHADOW row is the fire of record
                by_lane[lane].append(r)

    n_stamped = sum(1 for v in by_lane.values() for r in v if stamped(r))
    n_rows = sum(len(v) for v in by_lane.values())
    print("HARNESS PARITY v2 — %s\n  fire rows: %d   with A2 provenance stamps: %d"
          % (day, n_rows, n_stamped))
    if n_rows and not n_stamped:
        print("\nREFUSING to grade: not one row on %s carries fed_k0/fed_k1/fire_k.\n"
              "  The stamps shipped 2026-08-17 night, so 2026-08-18 is the FIRST day whose\n"
              "  rows support true equivalence testing. For earlier days use\n"
              "  harness_parity_20260817.py (batch_secs=60), whose output is a time-and-price\n"
              "  APPROXIMATION and must be labelled as one." % day)
        return 2

    report = {"day": day, "mode": "exact_fed_stream", "lanes": {}}
    tapes = {}

    def bars(t):
        if t not in tapes:
            p = os.path.join(tape, t + ".json")
            tapes[t] = json.load(open(p)) if os.path.exists(p) else None
        return tapes[t]

    for lane, live_rows in sorted(by_lane.items()):
        live_rows = [r for r in live_rows if stamped(r)]
        # A1: collapse restart replays — one live fire per (ticker, fire_k)
        seen, uniq = set(), []
        for r in sorted(live_rows, key=lambda x: et_secs(x.get("recorded_at", ""))):
            key = (r["ticker"], r["fire_k"])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(r)
        L = {"live_rows": len(live_rows), "live_distinct": len(uniq),
             "restart_replays": len(live_rows) - len(uniq),
             "harness_fires": 0, "exact": 0, "no_tape_names": [], "unmatched": []}

        for t in sorted({r["ticker"] for r in uniq}):
            tr = [r for r in uniq if r["ticker"] == t]
            b = bars(t)
            if b is None:
                L["no_tape_names"].append(t)
                continue
            B = H.norm_bars(b, day=day)
            run = H.running_vwap(b)
            vmap = {r["fire_k"]: r.get("vwap") for r in tr if r.get("vwap")}
            slices = [(r["fed_k0"], r["fed_k1"]) for r in tr]

            def vprov(sym, i, bar, ln, _B=B, _run=run, _v=vmap):
                return float(_v.get(_B[i][0]) or _run[i])

            def cprov(sym, i, bar, ln, _tr=tr):
                # CONTEXT CONTRACT: keys supplied explicitly, never defaulted silently.
                near = min(_tr, key=lambda r: abs(r["fire_k"] - bar[0]))
                return {"front_side": near.get("front_side"), "day_gain": near.get("day_gain"),
                        "top3": bool(near.get("top3")), "blue_sky": bool(near.get("blue_sky"))}

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                fires = H.replay(t, b, [lane], day=day, fed_slices=slices,
                                 vwap_provider=vprov,
                                 ctx_provider=cprov if H.LANES[lane]["ctx_required"] else None)
            hk = {int(f["k"]) for f in fires if f.get("k") and (f.get("ok", True))}
            L["harness_fires"] += len(hk)
            for r in tr:
                if int(r["fire_k"]) in hk:
                    L["exact"] += 1
                else:
                    L["unmatched"].append({"ticker": t, "fire_k": r["fire_k"],
                                           "fed": [r["fed_k0"], r["fed_k1"], r["fed_n"]],
                                           "px": r.get("price"),
                                           "why": "harness fed the identical slice and did NOT fire"})
        L["parity_pct"] = round(100.0 * L["exact"] / max(L["live_distinct"], 1), 1)
        report["lanes"][lane] = L

    print("\n%-10s%>0s" % ("lane", "") if False else
          "\n%-10s%8s%10s%9s%10s%9s" % ("lane", "rows", "distinct", "replays", "harness", "parity%"))
    for lane, L in report["lanes"].items():
        print("%-10s%8d%10d%9d%10d%9.1f" % (lane, L["live_rows"], L["live_distinct"],
                                            L["restart_replays"], L["harness_fires"],
                                            L["parity_pct"]))
    out = os.path.join(HERE, "harness_parity_v2_%s_out.json" % day.replace("-", ""))
    json.dump(report, open(out, "w"), indent=1, default=str)
    print("\nwrote %s" % out)

    # update the machine-read parity store the EG2b threshold gate consults
    try:
        store = json.load(open(PARITY_JSON))
        for lane, L in report["lanes"].items():
            store["lanes"].setdefault(lane, {})
            store["lanes"][lane].update({"parity_pct": L["parity_pct"], "measured_on": day,
                                         "method": "exact_fed_stream",
                                         "source": os.path.basename(out)})
        json.dump(store, open(PARITY_JSON, "w"), indent=1)
        print("updated %s" % PARITY_JSON)
    except Exception as e:                                              # noqa: BLE001
        print("parity store NOT updated: %s: %s" % (type(e).__name__, e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
