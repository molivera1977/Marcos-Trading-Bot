#!/usr/bin/env python3
"""HARNESS PARITY — BATCH E newly-lifted lanes (2026-08-17).

Measures the SAME WAY harness_parity_20260817.py measured the first cohort, so the numbers
are comparable: today's LIVE decision rows vs the harness driving the BOT'S OWN detectors
over today's 10s tape, 60s cadence, exact price + exact stop, |dt| <= 300s, greedy
nearest-in-time.

Lanes measured here:
  hidden     — was BLOCKED (the _bucket_fresh wall-clock guard ate 100% of replay fires).
               Unblocked by batch E1 (the _BUCKET_NOW hook).
  zone_flip  — was NOT_ISOLABLE (wall clock + the live premarket store). Unblocked by E1 +
               E2 (kev_zoneflip_step(pm_floor=...)), with the floor computed by the BOT'S OWN
               _zf_pm_floor over the tape (H.pm_floor_from_tape), never a replica.

ALSO PRINTED: the E1 counterfactual — the same hidden replay with the clock hook disarmed,
which is the before/after proof that the guard was the blocker.

NOT MEASURED HERE, and why:
  _marked_runway  — replayable only against a RECORDED map snapshot. None exists for any day
                    <= 2026-08-17. Recording started tonight (E3b). Un-replayable, stated.
  check_momentum  — a gate over 1-min bars, not a fire-emitting lane: it produces no rows to
                    match against. Its lift is proven by rig equivalence, not by a parity rate.
"""
import collections
import contextlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import live_harness as H            # noqa: E402

DAY = "2026-08-17"
ARCH = os.path.join(HERE, "exit_params_our_fires_20260817_arch.json")
TAPE = os.path.join(HERE, "bars10s_0817_full")
OUT = os.path.join(HERE, "harness_parity_batchE_20260817_out.json")
TOL_S = int(os.environ.get("PARITY_TOL_S", "300"))

LANE_STATUS = {"hidden": "hidden_shadow_fire", "zone_flip": "zoneflip_shadow_fire"}
# which live-row field carries the DETECTOR's fire price for each lane
LANE_PX = {"hidden": "price", "zone_flip": "fire_px"}


def et_secs(iso_s):
    t = str(iso_s)[11:19]
    return int(t[0:2]) * 3600 + int(t[3:5]) * 60 + int(t[6:8])


def bar_et_secs(k):
    return (k % 86400) - 4 * 3600          # EDT = UTC-4


def main():
    rows = json.load(open(ARCH))["rows"]
    by_status = collections.defaultdict(list)
    for r in rows:
        by_status[r.get("status")].append(r)
    # zone_flip's detector px lives on the CONVERT row (the fire row stamps the live price)
    zf_px = {}
    for r in by_status["zoneflip_shadow_convert"]:
        zf_px[(r["ticker"], r["recorded_at"])] = r

    vw = collections.defaultdict(list)
    for r in rows:
        if r.get("vwap") and r.get("ticker") and r.get("recorded_at"):
            try:
                vw[r["ticker"]].append((et_secs(r["recorded_at"]), float(r["vwap"])))
            except Exception:
                pass
    for v in vw.values():
        v.sort()

    def ff(series, s, default=None):
        got = default
        for ts, val in series:
            if ts <= s:
                got = val
            else:
                break
        return got

    tape = {}

    def bars(t):
        if t not in tape:
            p = os.path.join(TAPE, t + ".json")
            tape[t] = json.load(open(p)) if os.path.exists(p) else None
        return tape[t]

    report = {"day": DAY, "cadence_secs": 60, "match_tol_s": TOL_S,
              "method": "time_and_price_approximation", "lanes": {}}

    for lane, status in LANE_STATUS.items():
        live = []
        for r in by_status[status]:
            px = r.get(LANE_PX[lane])
            if px is None and lane == "zone_flip":
                c = zf_px.get((r["ticker"], r["recorded_at"]))
                px = c and c.get("fire_px")
            if px is not None:
                live.append((r, round(float(px), 4)))
        tick = sorted({r["ticker"] for r, _ in live})
        L = {"live_fires": len(live), "live_names": len(tick), "no_tape_names": [],
             "no_pm_floor_names": [], "harness_fires": 0, "exact": 0,
             "live_unmatched": [], "harness_extra": 0, "harness_extra_sample": [],
             "pm_floor_vs_live_zone": []}
        hf_all = []
        for t in tick:
            raw = bars(t)
            if raw is None:
                L["no_tape_names"].append(t)
                continue
            B = H.norm_bars(raw, day=DAY)
            run = H.running_vwap(raw)
            vseries = vw.get(t, [])

            def vprov(sym, i, b, ln, _B=B, _run=run, _vs=vseries):
                v = ff(_vs, bar_et_secs(_B[i][0]))
                return _run[i] if v is None else v

            pmf = None
            if lane == "zone_flip":
                pmf = H.pm_floor_from_tape(t, raw, DAY)
                if not pmf:
                    L["no_pm_floor_names"].append(t)
                    continue
                # EQUIVALENCE CHECK: the bot's own _zf_pm_floor over the tape vs the zone the
                # LIVE machine stamped on its rows. Same number = the injection is faithful.
                lz = next((r.get("zone") for r, _ in live if r["ticker"] == t), None)
                lsrc = next((r.get("zone_src") for r, _ in live if r["ticker"] == t), None)
                L["pm_floor_vs_live_zone"].append(
                    {"ticker": t, "tape_zone": pmf["zone"], "live_zone": lz,
                     "tape_src": pmf["src"], "live_src": lsrc,
                     "match": (lz is not None and abs(float(lz) - pmf["zone"]) < 1e-6
                               and lsrc == pmf["src"])})

            def cprov(sym, i, b, ln, _p=pmf):
                return {"pm_floor": _p}

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                fires = H.replay(t, raw, [lane], day=DAY, batch_secs=60,
                                 vwap_provider=vprov,
                                 ctx_provider=cprov if H.LANES[lane]["ctx_required"] else None)
            for f in fires:
                hf_all.append((t, bar_et_secs(f["bar"][0]), round(float(f["px"]), 4),
                               round(float(f.get("stop") or 0), 4)))
        L["harness_fires"] = len(hf_all)

        # MATCH KEY, and why it differs by lane — this is a fidelity point, not a convenience:
        # zoneflip's convert row stamps `fire_px` = the DETECTOR's px, so price+stop is a valid
        # key (same as the first cohort). hidden's row stamps `price` = the live QUOTE at log
        # time (bot :8931, `_hpx = price if price>0 else fire['px']`), which is NOT a detector
        # output and cannot be expected to equal a bar close. Matching hidden on it would
        # measure the quote feed, not the detector. hidden's only real detector outputs on the
        # row are `stop` and `seq`, so hidden is matched on EXACT STOP + time. Both numbers are
        # computed and reported; neither is hidden.
        key_px = (lane != "hidden")
        L["match_key"] = "price+stop+time" if key_px else "stop+time (row 'price' is the live quote, not the detector px)"
        used = set()
        for r, lp in live:
            lstop = round(float(r.get("stop") or 0), 4)
            ls = et_secs(r["recorded_at"])
            best, bestd = None, None
            for j, (t, hs, hp, hstop) in enumerate(hf_all):
                if j in used or t != r["ticker"] or hstop != lstop:
                    continue
                if key_px and hp != lp:
                    continue
                d = abs(hs - ls)
                if d <= TOL_S and (bestd is None or d < bestd):
                    best, bestd = j, d
            if best is not None:
                used.add(best); L["exact"] += 1
            else:
                same_px = [x for x in hf_all if x[0] == r["ticker"] and x[2] == lp]
                near_t = [x for x in hf_all if x[0] == r["ticker"] and abs(x[1] - ls) <= TOL_S]
                if r["ticker"] in L["no_tape_names"]:
                    why = "no_tape"
                elif r["ticker"] in L["no_pm_floor_names"]:
                    why = "no_pm_floor"
                elif same_px and not near_t:
                    why = "same_price_wrong_time"
                elif near_t:
                    why = "near_time_diff_price_or_stop:" + json.dumps(near_t[:2])
                else:
                    why = "no_harness_fire_for_name"
                L["live_unmatched"].append({"ticker": r["ticker"], "t": r.get("time"),
                                            "px": lp, "stop": lstop, "why": why})
        # the STRICTER price+stop rate too, for every lane, so the two keys sit side by side
        used_s, exact_s = set(), 0
        for r, lp in live:
            lstop = round(float(r.get("stop") or 0), 4)
            ls = et_secs(r["recorded_at"])
            best, bestd = None, None
            for j, (t, hs, hp, hstop) in enumerate(hf_all):
                if j in used_s or t != r["ticker"] or hp != lp or hstop != lstop:
                    continue
                d = abs(hs - ls)
                if d <= TOL_S and (bestd is None or d < bestd):
                    best, bestd = j, d
            if best is not None:
                used_s.add(best); exact_s += 1
        L["exact_price_and_stop"] = exact_s
        L["match_rate_price_and_stop_pct"] = round(100.0 * exact_s / max(len(live), 1), 1)
        L["harness_extra"] = len(hf_all) - len(used)
        L["harness_extra_sample"] = [hf_all[j] for j in range(len(hf_all)) if j not in used][:8]
        L["match_rate_pct"] = round(100.0 * L["exact"] / max(L["live_fires"], 1), 1)
        report["lanes"][lane] = L

    # ── the E1 before/after: hidden replay with the clock hook DISARMED ──
    cf = {"names": 0, "fires": 0}
    H.ns()["_BUCKET_NOW"] = None
    for t in sorted({r["ticker"] for r in by_status["hidden_shadow_fire"]}):
        raw = bars(t)
        if raw is None:
            continue
        B = H.norm_bars(raw, day=DAY)
        run = H.running_vwap(raw)
        vseries = vw.get(t, [])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            # replay() re-installs the hook, so call the detector directly on the same cadence
            H.reset_state("hidden", t)
            F = H.fn("hidden_entry_step")
            cur, cur_k, batches = [], None, []
            for i, b in enumerate(B):
                slot = b[0] // 60
                if cur_k is None or slot == cur_k:
                    cur.append(i); cur_k = slot
                else:
                    batches.append(cur); cur, cur_k = [i], slot
            if cur:
                batches.append(cur)
            for batch in batches:
                nb = [B[i] for i in batch]
                v = ff(vseries, bar_et_secs(B[batch[-1]][0]))
                r = F(t, nb, run[batch[-1]] if v is None else v)
                if r:
                    cf["fires"] += 1
        cf["names"] += 1
    report["e1_counterfactual_hidden_clock_disarmed"] = cf

    json.dump(report, open(OUT, "w"), indent=1, default=str)

    print(f"BATCH-E HARNESS PARITY {DAY} — cadence 60s, tol {TOL_S}s, exact price+stop\n")
    print(f"{'lane':<11}{'live':>6}{'harness':>9}{'exact':>7}{'rate%':>8}{'px+stop%':>10}{'extra':>7}  key")
    for lane, L in report["lanes"].items():
        print(f"{lane:<11}{L['live_fires']:>6}{L['harness_fires']:>9}{L['exact']:>7}"
              f"{L['match_rate_pct']:>8}{L['match_rate_price_and_stop_pct']:>10}"
              f"{L['harness_extra']:>7}  {L['match_key']}")
    print("\nUNMATCHED LIVE FIRES (reasons):")
    for lane, L in report["lanes"].items():
        c = collections.Counter(u["why"].split(":")[0] for u in L["live_unmatched"])
        print(f"  {lane}: {dict(c)}")
    zl = report["lanes"].get("zone_flip", {}).get("pm_floor_vs_live_zone", [])
    print("\nE2 pm_floor equivalence (bot's _zf_pm_floor over tape vs the live-stamped zone):")
    for z in zl:
        print(f"  {z['ticker']}: tape {z['tape_zone']}/{z['tape_src']} vs live "
              f"{z['live_zone']}/{z['live_src']} -> {'MATCH' if z['match'] else 'DIFFER'}")
    print(f"\nE1 counterfactual — hidden with the clock hook DISARMED: "
          f"{cf['fires']} fires across {cf['names']} names (was the blocker)")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
