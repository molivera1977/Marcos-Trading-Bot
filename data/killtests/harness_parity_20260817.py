#!/usr/bin/env python3
"""HARNESS PARITY PROOF — 2026-08-17.

The deliverable that decides whether live_harness.py is trustworthy: take TODAY's LIVE
decision rows (the bot's actual fires, with their prices and stops) and re-run the same
names/day through the harness, which drives the BOT'S OWN detector functions.

Per lane: N live fires, N harness fires, exact matches (same bar-time window, same price,
same stop), mismatches with reasons.

METHOD (stated so the number can be attacked)
  tape   : data/killtests/bars10s_0817_full/<T>.json  (SIP 10s bars, whole day, with pv)
  rows   : data/killtests/exit_params_our_fires_20260817_arch.json (the day's decisions
           archive, pulled 8/17 16:03)
  cadence: batch_secs=60 — the live 60s rescan. Every detector returns AT MOST ONE fire per
           call, so bar-by-bar replay would over-produce. This is the honest cadence.
  ctx    : taken FROM THE LIVE ROWS (front_side/day_gain/top3/blue_sky as the bot stamped
           them), forward-filled from the nearest prior kevseq row. Before the first stamp
           the ctx is supplied EXPLICITLY as unknown (front_side=None -> the detector
           refuses), never defaulted. This is the context contract in action.
  vwap   : live-stamped session VWAP forward-filled from the day's rows where available,
           else the running SIP VWAP. The vwap source is the largest known parity risk on
           vwap-gated lanes and is reported per lane.
  match  : exact price AND exact stop (4dp, as the row stamps them) AND |dt| <= 300s.
           Greedy nearest-in-time. Anything else is a mismatch and is itemised.

NOT TUNED TO MATCH. Where the rate is poor the diagnosis is written down instead.
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
OUT = os.path.join(HERE, "harness_parity_20260817_out.json")

LANE_STATUS = {
    "kevseq":   "kevseq_shadow_fire",
    "grinder":  "grinder_shadow_fire",
    "bandpass": "bandpass_shadow_fire",
    "prevwap":  "prevwap_shadow_fire",
    "v2":       "v2_shadow_fire",
}
TOL_S = int(os.environ.get("PARITY_TOL_S", "300"))


def et_secs(iso_s):
    """'2026-08-17T11:06:49.5-04:00' -> ET seconds-of-day."""
    t = str(iso_s)[11:19]
    return int(t[0:2]) * 3600 + int(t[3:5]) * 60 + int(t[6:8])


def bar_et_secs(k):
    return (k % 86400) - 4 * 3600          # EDT = UTC-4


def main():
    rows = json.load(open(ARCH))["rows"]
    by_status = collections.defaultdict(list)
    for r in rows:
        by_status[r.get("status")].append(r)

    # ── ctx + vwap timelines straight off the live record ──
    ks_ctx = collections.defaultdict(list)     # ticker -> [(et_s, ctx)]
    for r in by_status["kevseq_shadow_fire"] + by_status["kevseq_reject"]:
        ks_ctx[r["ticker"]].append((et_secs(r["recorded_at"]), {
            "front_side": r.get("front_side"),
            "day_gain": r.get("day_gain"),
            "top3": bool(r.get("top3")),
            "blue_sky": bool(r.get("blue_sky")),
        }))
    for v in ks_ctx.values():
        v.sort()

    vw = collections.defaultdict(list)         # ticker -> [(et_s, vwap)]
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

    report = {"day": DAY, "cadence_secs": 60, "match_tol_s": TOL_S, "lanes": {}}

    for lane, status in LANE_STATUS.items():
        live = [r for r in by_status[status] if r.get("price")]
        tick = sorted({r["ticker"] for r in live})
        L = {"live_fires": len(live), "live_names": len(tick),
             "no_tape_names": [], "harness_fires": 0, "exact": 0,
             "live_unmatched": [], "harness_extra": 0, "harness_extra_sample": [],
             "vwap_src": {"live_stamped": 0, "running_sip": 0}}
        hf_all = []
        for t in tick:
            raw = bars(t)
            if raw is None:
                L["no_tape_names"].append(t)
                continue
            B = H.norm_bars(raw, day=DAY)
            run = H.running_vwap(raw)
            vseries = vw.get(t, [])
            cseries = ks_ctx.get(t, [])

            def vprov(sym, i, b, ln, _B=B, _run=run, _vs=vseries, _L=L):
                s = bar_et_secs(_B[i][0])
                v = ff(_vs, s)
                if v is None:
                    _L["vwap_src"]["running_sip"] += 1
                    return _run[i]
                _L["vwap_src"]["live_stamped"] += 1
                return v

            def cprov(sym, i, b, ln, _B=B, _cs=cseries):
                s = bar_et_secs(_B[i][0])
                # CONTEXT CONTRACT: every key supplied explicitly. Before the first live
                # stamp the honest value is "unknown", which the detector refuses on.
                return ff(_cs, s, {"front_side": None, "day_gain": None,
                                   "top3": False, "blue_sky": False})

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                fires = H.replay(t, raw, [lane], day=DAY, batch_secs=60,
                                 vwap_provider=vprov,
                                 ctx_provider=cprov if H.LANES[lane]["ctx_required"] else None)
            for f in fires:
                if lane == "kevseq" and not f.get("ok"):
                    continue                      # rejects are not fires
                hf_all.append((t, bar_et_secs(f["bar"][0]), round(float(f["px"]), 4),
                               round(float(f.get("would_stop") or 0), 4)))
        L["harness_fires"] = len(hf_all)

        used = set()
        for r in live:
            lp = round(float(r["price"]), 4)
            lstop = round(float(r.get("would_stop") or 0), 4)
            ls = et_secs(r["recorded_at"])
            best, bestd = None, None
            for j, (t, hs, hp, hstop) in enumerate(hf_all):
                if j in used or t != r["ticker"]:
                    continue
                if hp != lp or hstop != lstop:
                    continue
                d = abs(hs - ls)
                if d <= TOL_S and (bestd is None or d < bestd):
                    best, bestd = j, d
            if best is not None:
                used.add(best)
                L["exact"] += 1
            else:
                # diagnose
                same_px = [(t, hs, hp, hstop) for (t, hs, hp, hstop) in hf_all
                           if t == r["ticker"] and hp == lp]
                near_t = [(t, hs, hp, hstop) for (t, hs, hp, hstop) in hf_all
                          if t == r["ticker"] and abs(hs - ls) <= TOL_S]
                if r["ticker"] in L["no_tape_names"]:
                    why = "no_tape"
                elif same_px and not near_t:
                    why = "same_price_wrong_time"
                elif near_t:
                    why = "near_time_diff_price_or_stop:" + json.dumps(near_t[:2])
                else:
                    why = "no_harness_fire_for_name"
                L["live_unmatched"].append({"ticker": r["ticker"], "t": r.get("time"),
                                            "px": lp, "stop": lstop, "why": why})
        L["harness_extra"] = len(hf_all) - len(used)
        L["harness_extra_sample"] = [hf_all[j] for j in range(len(hf_all))
                                     if j not in used][:8]
        L["match_rate_pct"] = round(100.0 * L["exact"] / max(L["live_fires"], 1), 1)
        report["lanes"][lane] = L

    report["isolability"] = H.isolability_report()
    json.dump(report, open(OUT, "w"), indent=1, default=str)

    print(f"HARNESS PARITY {DAY} — cadence 60s, tol {TOL_S}s, exact price+stop\n")
    print(f"{'lane':<10}{'live':>6}{'harness':>9}{'exact':>7}{'rate%':>8}{'extra':>7}  notes")
    for lane, L in report["lanes"].items():
        note = ""
        if L["no_tape_names"]:
            note += f"no tape: {','.join(L['no_tape_names'])}"
        print(f"{lane:<10}{L['live_fires']:>6}{L['harness_fires']:>9}{L['exact']:>7}"
              f"{L['match_rate_pct']:>8}{L['harness_extra']:>7}  {note}")
    print("\nUNMATCHED LIVE FIRES (reasons):")
    for lane, L in report["lanes"].items():
        c = collections.Counter(u["why"].split(":")[0] for u in L["live_unmatched"])
        if c:
            print(f"  {lane}: {dict(c)}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
