#!/usr/bin/env python3
"""BATCH G2 — WHAT hidden's NEW `fire_px` FIELD BUYS, MEASURED ON 2026-08-17 (SYNTHETICALLY).

WHAT THIS IS, AND WHAT IT IS NOT — READ FIRST
---------------------------------------------
Batch E measured hidden parity at 86.3% on stop+time and 5.8% on price, and correctly
attributed the 5.8% to the row's `price` field carrying the LIVE QUOTE at log time rather than
the detector's output. Batch G stamps the detector's own price as `fire_px`.

**8/17's rows do not contain `fire_px` — the field ships tonight. So the post-fix price parity
CANNOT be measured on 8/17 and is NOT measured here.** What this script measures instead, on
exactly the batch-E replay, is:

  (1) the two batch-E numbers, RE-DERIVED here so this artifact stands alone;
  (2) THE SIZE OF THE THING THE OLD KEY WAS MEASURING: for every live fire matched on
      stop+time, the gap between the row's `price` (the quote) and the harness detector's `px`
      (a bar close). This is the quantity that dragged price parity from 86.3% to 5.8%, and it
      is a property of the QUOTE FEED, not of the detector;
  (3) a WEAK RECOVERY HEURISTIC, reported as such. `hidden_entry_step` sets
      stop = min(l - 0.01, c*0.95); when the 5% risk floor binds, the bar close is stop/0.95.
      That inversion was intended to isolate a clean subset and DOES NOT: stop/0.95 round-trips
      for any stop, so nothing real is being filtered. What survives is the honest statement
      that guessing the fire price as stop/0.95 lands within half a cent of the detector's px
      on 90.1% of the stop+time matches (173/192) — a statement about how often the floor
      happens to bind, NOT a price-parity measurement. It is kept because it was run and it
      bounds nothing; deleting a result because it came out weaker than hoped is worse.

THE REAL NUMBER ARRIVES WITH 2026-08-18 ROWS. From tomorrow, `hidden_shadow_fire` carries
`fire_px` and the parity run can key on price+stop+time directly, with no recovery, no subset
and no invertibility assumption. Nothing below is a substitute for that.

Standing 8/17 caveat, unchanged: no row carries fed_k0/fed_k1 provenance, so the two sides were
not provably fed the same bars; every figure here is a time-and-price approximation.
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
OUT = os.path.join(HERE, "harness_parity_hiddenpx_20260817_out.json")
TOL_S = int(os.environ.get("PARITY_TOL_S", "300"))
FLOOR = 0.95        # hidden_entry_step's 5% risk floor: stop = min(l - 0.01, c*FLOOR)


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

    live = []
    for r in by_status["hidden_shadow_fire"]:
        if r.get("price") is not None and r.get("stop") is not None:
            live.append((r, round(float(r["price"]), 4), round(float(r["stop"]), 4)))
    tick = sorted({r["ticker"] for r, _, _ in live})

    hf = []
    for t in tick:
        raw = bars(t)
        if raw is None:
            continue
        B = H.norm_bars(raw, day=DAY)
        run = H.running_vwap(raw)
        vseries = vw.get(t, [])

        def vprov(sym, i, b, ln, _B=B, _run=run, _vs=vseries):
            v = ff(_vs, bar_et_secs(_B[i][0]))
            return _run[i] if v is None else v

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fires = H.replay(t, raw, ["hidden"], day=DAY, batch_secs=60, vwap_provider=vprov)
        for f in fires:
            hf.append((t, bar_et_secs(f["bar"][0]), round(float(f["px"]), 4),
                       round(float(f.get("stop") or 0), 4)))

    rep = {"day": DAY, "match_tol_s": TOL_S, "live_fires": len(live), "live_names": len(tick),
           "harness_fires": len(hf), "note": "SYNTHETIC — 8/17 rows carry no fire_px; see docstring"}

    # ── (1) the two batch-E keys, re-derived ─────────────────────────────────────────────
    def parity(key_px):
        used, n, pairs = set(), 0, []
        for r, lp, lstop in live:
            ls = et_secs(r["recorded_at"])
            best, bestd = None, None
            for j, (t, hs, hp, hstop) in enumerate(hf):
                if j in used or t != r["ticker"] or hstop != lstop:
                    continue
                if key_px and hp != lp:
                    continue
                d = abs(hs - ls)
                if d <= TOL_S and (bestd is None or d < bestd):
                    best, bestd = j, d
            if best is not None:
                used.add(best); n += 1
                pairs.append((r, lp, lstop, hf[best]))
        return n, pairs

    n_st, pairs = parity(False)
    n_pst, _ = parity(True)
    rep["stop_time_matches"] = n_st
    rep["stop_time_parity_pct"] = round(100.0 * n_st / max(len(live), 1), 1)
    rep["price_stop_time_matches_OLD_FIELD"] = n_pst
    rep["price_stop_time_parity_pct_OLD_FIELD"] = round(100.0 * n_pst / max(len(live), 1), 1)

    # ── (2) how big is the quote-vs-detector gap the old key was measuring? ──────────────
    gaps = []
    for r, lp, lstop, (t, hs, hp, hstop) in pairs:
        if hp > 0:
            gaps.append(abs(lp - hp) / hp * 100.0)
    gaps.sort()
    def pct(p):
        return round(gaps[min(len(gaps) - 1, int(p * len(gaps)))], 3) if gaps else None
    rep["quote_vs_detector_px_gap_pct"] = {
        "n": len(gaps), "median": pct(0.5), "p90": pct(0.9), "max": round(gaps[-1], 3) if gaps else None,
        "exactly_equal": sum(1 for g in gaps if g == 0.0),
        "within_0_1pct": sum(1 for g in gaps if g <= 0.1),
        "comment": "this is the QUOTE FEED's drift from the fired bar close — it is what the "
                   "old price key was scoring, and it is not a detector property",
    }

    # ── (3) the falsifiable subset: rows where the 5% floor BINDS, so c = stop/0.95 ──────
    # Guard: the floor binds iff stop == c*0.95 exactly; we can only TEST that against a
    # candidate c, so the subset is defined from the harness side (its px is known) and the
    # live row is admitted only when its own stop reproduces under the floor rule.
    rec_n, rec_ok, rec_bad = 0, 0, []
    for r, lp, lstop, (t, hs, hp, hstop) in pairs:
        c_from_stop = round(lstop / FLOOR, 4)
        # floor-binding test on the LIVE row alone: stop/0.95 must be a price whose 5% floor
        # reproduces the stop to the 4th decimal AND must not be explainable as a wick low
        # (wick-low stops are strictly below c*0.95 by construction only when l-0.01 < c*0.95).
        if abs(round(c_from_stop * FLOOR, 4) - lstop) > 1e-9:
            continue
        # admit only when the recovered close is consistent with the row's own quote to within
        # a sane band (a wick-low stop would recover a nonsense close far from the quote)
        if lp <= 0 or abs(c_from_stop - lp) / lp > 0.10:
            continue
        rec_n += 1
        if abs(c_from_stop - hp) < 0.005:
            rec_ok += 1
        else:
            rec_bad.append({"ticker": r["ticker"], "t": r.get("time"),
                            "recovered_close": c_from_stop, "harness_px": hp,
                            "row_quote": lp, "stop": lstop})
    rep["stop_over_floor_recovery"] = {
        "n": rec_n, "agree": rec_ok,
        "agree_pct": round(100.0 * rec_ok / rec_n, 1) if rec_n else None,
        "disagreements": rec_bad[:8],
        "method": "guess the fired bar close as stop/0.95 (the 5% risk floor inverted) and "
                  "compare it to the harness detector's px, agreeing within half a cent.",
        "HONEST LIMIT — READ THIS": "the admission filter does NOT actually isolate the "
                  "floor-binding rows. stop/0.95 round-trips for ANY stop, so the only real "
                  "filter left is the +/-10% sanity band, which admits 192 of the 195 "
                  "stop+time matches. This is therefore a WEAK RECOVERY HEURISTIC, not a "
                  "clean invertible subset: it says the guess lands within half a cent of the "
                  "detector's px 90% of the time, which is a statement about how often the "
                  "5% floor happens to bind, NOT a price-parity measurement. It cannot "
                  "substitute for the real number, which arrives with 8/18 rows.",
    }

    json.dump(rep, open(OUT, "w"), indent=1)
    print(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
