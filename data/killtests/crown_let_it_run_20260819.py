#!/usr/bin/env python3
"""
LETTING CROWNED NAMES RUN — trail width on the crown cohort (8/19, Marcos: "how about something
basic like letting crown names go")

THE OBSERVATION THIS TESTS: all day the exits, not the entries, have been the binding constraint
— TNON banked +$60.42 while the tape ran to a $17.84 run-high; GDC trailed out twice and kept
going; the ZSTK dip_rip counterfactual took +$35.14 out of a move to $12.40. Marcos on hidden:
"it finds the entries but can't hold it." The crown doctrine already grants EXTRA BULLETS on the
entry side (ignition x3, curl slots x3, hidden uncapped). This asks whether it should also grant
a LONGER LEASH on the exit side.

COHORTS: every era (>=2026-07-13) trade with 10s tape cached, split by the crown stamp at entry
(entry_crown / entry_context.crown.crowned). The NON-CROWNED cohort is the control that decides
whether any effect is CROWN-SPECIFIC or just a general exit change wearing a crown.

ARMS (identical entry, identical initial stop, identical +10% half-bank; ONLY the trail differs):
  T10  current E3 — trail 10% off the run-high            (control)
  T15  trail 15% off the run-high
  T20  trail 20% off the run-high
  T30  trail 30% off the run-high
  NONE no trail at all — structural stop or the 15:45 flatten only ("let it go")

PRE-REGISTERED READING (written before the run):
  * A wider trail WINS on a cohort only if BOTH its TOTAL and its MEDIAN beat T10 on that cohort.
    Total-only is a tail artifact; median-only is noise on the winners that matter.
  * The crown claim is supported ONLY if the best arm's improvement over T10 is LARGER on the
    crowned cohort than on the non-crowned control. Equal or smaller = not a crown property,
    and any change would belong to the exit engine generally, NOT to the crown doctrine.
  * Give-back is reported explicitly: mean $ surrendered from the run-high per arm.

METHOD: entry = the booked entry price at the trade's own entry_ts_utc bar; stop = the booked
stop_loss; slips -1% entry / -0.5% non-stop exits; stop-first intrabar; bank 1/2 at +10% then
stop to breakeven (documented E3). Sizing uses the BOOKED share count so P&L is comparable to
the live ledger.

LIMITS: 2026-07-13..2026-08-18 aggregate SPANS CONFIG EPOCHS (lane set, gates, sizing all moved);
this measures EXIT arithmetic on a fixed set of historical entries, so entry-side epoch drift is
not in the measured difference — but the COHORT COMPOSITION is epoch-dependent (79% of crowned
trades are hidden_entry, a lane Marcos has ruled "numbers are fake" pending exit rework, and
whose live figures are UNVERIFIED). Crowned n=76 is small and hidden-dominated; read the per-lane
split before generalizing. Nothing ships from this file.
"""
import json
import os
import sys
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
D = "https://zestful-intuition-production-b16a.up.railway.app"
H = {"X-Dashboard-Secret": "marcos2026"}
ARMS = [("T10", 0.10), ("T15", 0.15), ("T20", 0.20), ("T30", 0.30), ("NONE", None)]

_rr = open(os.path.join(HERE, "runway_refusal_replay_20260819.py")).read().split("def main()")[0]
ns = {"__file__": os.path.join(HERE, "runway_refusal_replay_20260819.py")}
exec(_rr, ns)
bars_for, hms = ns["bars_for"], ns["hms"]


def walk(bars, i0, entry, stop, shares, trail):
    """E3 with a parameterised trail. Returns (pnl, runhigh, exit_reason)."""
    px = entry * 0.99
    rem, banked, runhi, tiered = shares, 0.0, px, False
    for i in range(i0 + 1, len(bars)):
        b = bars[i]
        t = hms(b["t"])
        if b["l"] <= stop:
            return banked + rem * (stop - px), runhi, "stop"
        runhi = max(runhi, b["h"])
        if not tiered and b["h"] >= px * 1.10:
            half = rem // 2 or rem
            banked += half * (px * 1.10 * 0.995 - px)
            rem -= half
            tiered = True
            stop = px
            if rem == 0:
                return banked, runhi, "tier_out"
        if tiered and trail is not None and b["c"] <= runhi * (1 - trail):
            return banked + rem * (b["c"] * 0.995 - px), runhi, "trail"
        if t >= "15:45:00":
            return banked + rem * (b["c"] * 0.995 - px), runhi, "flat_1545"
    b = bars[-1]
    return banked + rem * (b["c"] * 0.995 - px), runhi, "eod"


def main():
    tr = json.load(urllib.request.urlopen(urllib.request.Request(
        f"{D}/api/trades", headers=H), timeout=180)).get("trades") or []
    era = [r for r in tr if (r.get("date") or "") >= "2026-07-13"]

    def crowned(r):
        if r.get("entry_crown"):
            return True
        return bool(((r.get("entry_context") or {}).get("crown") or {}).get("crowned"))

    cache, rows = {}, []
    for r in era:
        sym, d = r.get("ticker"), r.get("date")
        ts, stop, sh = r.get("entry_ts_utc"), r.get("stop_loss"), r.get("shares")
        px = r.get("entry")
        if not (sym and d and ts and stop and sh and px) or float(stop) >= float(px):
            continue
        key = (sym, d)
        if key not in cache:
            cache[key] = bars_for(sym, d)
        b = cache[key]
        if not b:
            continue
        t = hms(ts)
        i0 = next((i for i, y in enumerate(b) if hms(y["t"]) >= t), None)
        if i0 is None or i0 >= len(b) - 2:
            continue
        rec = {"sym": sym, "d": d, "lane": r.get("entry_type"), "crown": crowned(r),
               "booked": round(float(r.get("pnl") or 0), 2)}
        for lab, tw in ARMS:
            pnl, runhi, why = walk(b, i0, float(px), float(stop), int(sh), tw)
            rec[lab] = round(pnl, 2)
            if lab == "T10":
                rec["runhi_$"] = round((runhi - float(px) * 0.99) * int(sh), 2)
        rows.append(rec)

    print("=" * 104)
    print("LETTING CROWNED NAMES RUN — trail width, crowned vs non-crowned control")
    print("=" * 104)
    print(f"replayed: {len(rows)}  (crowned {sum(1 for r in rows if r['crown'])} / "
          f"non-crowned {sum(1 for r in rows if not r['crown'])})\n")

    import statistics as st
    res = {}
    for cohort, sel in (("CROWNED", [r for r in rows if r["crown"]]),
                        ("NON-CROWNED (control)", [r for r in rows if not r["crown"]])):
        if not sel:
            continue
        print(f"--- {cohort}  n={len(sel)} ---")
        print(f"{'arm':6s} {'total':>10s} {'$/tr':>8s} {'median':>8s} {'green':>7s} "
              f"{'mean give-back from run-high':>30s}")
        for lab, _ in ARMS:
            v = [r[lab] for r in sel]
            gb = st.mean([max(r["runhi_$"] - r[lab], 0) for r in sel])
            print(f"{lab:6s} {sum(v):10.2f} {sum(v)/len(v):8.2f} {st.median(v):8.2f} "
                  f"{100*sum(1 for x in v if x>0)/len(v):6.0f}% {gb:30.2f}")
        res[cohort] = {lab: (sum(r[lab] for r in sel), st.median([r[lab] for r in sel]))
                       for lab, _ in ARMS}
        print()

    print("=" * 104)
    print("PRE-REGISTERED VERDICT")
    print("=" * 104)
    for cohort in res:
        base_t, base_m = res[cohort]["T10"]
        wins = [lab for lab, _ in ARMS if lab != "T10"
                and res[cohort][lab][0] > base_t and res[cohort][lab][1] > base_m]
        print(f"  {cohort:24s} arms beating T10 on BOTH total and median: {wins or 'NONE'}")
    if "CROWNED" in res and "NON-CROWNED (control)" in res:
        print("\n  CROWN-SPECIFICITY (improvement over T10, total $):")
        for lab, _ in ARMS:
            if lab == "T10":
                continue
            dc = res["CROWNED"][lab][0] - res["CROWNED"]["T10"][0]
            dn = res["NON-CROWNED (control)"][lab][0] - res["NON-CROWNED (control)"]["T10"][0]
            print(f"    {lab:5s} crowned {dc:+9.2f}   non-crowned {dn:+9.2f}   "
                  f"{'CROWN-SPECIFIC' if dc > dn else 'not crown-specific'}")

    byl = defaultdict(list)
    for r in rows:
        if r["crown"]:
            byl[r["lane"]].append(r)
    print("\n  crowned cohort by lane (T10 -> best wider arm):")
    for lane, sel in sorted(byl.items(), key=lambda z: -len(z[1])):
        if len(sel) < 3:
            continue
        b10 = sum(r["T10"] for r in sel)
        best = max(((lab, sum(r[lab] for r in sel)) for lab, _ in ARMS if lab != "T10"),
                   key=lambda z: z[1])
        print(f"    {lane:13s} n={len(sel):3d}  T10 ${b10:+8.2f}  best {best[0]} ${best[1]:+8.2f}")
    print("\nLIMITS: see docstring — hidden_entry dominates the crowned cohort and its live")
    print("figures are UNVERIFIED per Marcos. Mixed epochs. Nothing ships from this file.")
    json.dump(rows, open(os.path.join(HERE, "crown_let_it_run_20260819_out.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
