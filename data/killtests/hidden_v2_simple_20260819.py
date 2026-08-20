#!/usr/bin/env python3
"""
HIDDEN v2 — SIMPLE VERSION (Marcos 8/19: "try this easier version")

  ARM:     day_gain 25-60% + RVOL>=3 + price > session VWAP
  TRIGGER: 10s break of the pullback high; pullback retraces <= 50% of the leg
  STOP:    pullback low minus 1% buffer
  SCALE 1: +1.5R sell 40%, stop -> breakeven
  TIME:    5 min no new high -> exit runner
  FLAT:    15:50

IMPLEMENTATION (compact, one pass per name-day on the 10s cache):
  leg      = rise from the rolling 5-min low to the running session high
  pullback = consecutive down-ish bars off that high; depth <= 50% of the leg
  trigger  = a bar whose HIGH breaks the pullback high within 6 bars of the pullback low print
  runner   = rides on the breakeven stop until the 5-min-no-new-high time stop or 15:50
  cool-off = 30 bars per name after any fire (no restacking one zone)

SUBSTITUTIONS (declared): RVOL>=3 -> cache membership (every cached name-day is a calibrated-
scanner mover); day_gain vs prior close -> gain vs the 4am first print (EXCLUDES the gap, so
25-60% on tape is a TIGHTER true window); spread -> slips -1%/-0.5%.

READING (pre-registered): reported on TRAIN (even dates) and OOS (odd dates) separately; the
spec is interesting iff OOS $/tr > 0 with n>=30. Also reported against the SAME entries run
through plain E3, so the new exit engine's contribution is visible. Nothing ships from this file.
"""
import json
import os
import sys
import datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
RISK = 30.0


def hmss(t):
    return str(t)[11:19]


def ep(t):
    return dt.datetime.fromisoformat(str(t)[:19]).timestamp()


def walk_spec(b, i0, entry, stop):
    """Marcos's simple exits: 40% @1.5R -> BE, 5-min-no-new-high time stop, 15:50 flat."""
    px = entry * 0.99
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(500 / px)))
    rem, banked, scaled = sh, 0.0, False
    hi_since = px
    t_ref = ep(b[i0]["t"])
    for i in range(i0 + 1, len(b)):
        x = b[i]
        if x["l"] <= stop:
            return banked + rem * (stop - px), sh
        if x["h"] > hi_since:
            hi_since = x["h"]; t_ref = ep(x["t"])
        if not scaled and (x["h"] - px) / rps >= 1.5:
            n = int(rem * 0.4) or 1
            banked += n * ((px + 1.5 * rps) * 0.995 - px)
            rem -= n; scaled = True; stop = px
            if rem == 0:
                return banked, sh
        if ep(x["t"]) - t_ref >= 300:                     # 5 min without a new high
            return banked + rem * (x["c"] * 0.995 - px), sh
        if hmss(x["t"]) >= "15:50:00":
            return banked + rem * (x["c"] * 0.995 - px), sh
    return banked + rem * (b[-1]["c"] * 0.995 - px), sh


def walk_e3(b, i0, entry, stop):
    """control: the house E3 (bank 1/2 @+10%, BE, 10% trail off run-high)."""
    px = entry * 0.99
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(500 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    for i in range(i0 + 1, len(b)):
        x = b[i]
        if x["l"] <= stop:
            return banked + rem * (stop - px), sh
        runhi = max(runhi, x["h"])
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 * 0.995 - px)
            rem -= n; tiered = True; stop = px
            if rem == 0:
                return banked, sh
        if tiered and x["c"] <= runhi * 0.90:
            return banked + rem * (x["c"] * 0.995 - px), sh
        if hmss(x["t"]) >= "15:50:00":
            return banked + rem * (x["c"] * 0.995 - px), sh
    return banked + rem * (b[-1]["c"] * 0.995 - px), sh


def setups(b):
    """one pass: yield (i_trigger, entry, pb_lo) per the simple spec."""
    n = len(b)
    first = b[0]["c"]
    pv = vv = 0.0
    run_hi = 0.0
    lows5 = []                       # rolling 5-min (30-bar) lows
    out = []
    i = 30
    cool = 0
    pb_hi = pb_lo = None
    pb_from_hi = None
    while i < n - 2:
        x = b[i]
        # incremental series
        for j in range(len(out2 := []), 0):
            pass
        i += 1
    return out


def scan(b):
    n = len(b)
    first = b[0]["c"]
    if first <= 0:
        return []
    pv = vv = 0.0
    vwap = 0.0
    run_hi = 0.0
    out = []
    cool_until = 0
    i = 0
    lows = []
    while i < n:
        x = b[i]
        tp = (x["h"] + x["l"] + x["c"]) / 3.0
        pv += tp * x["v"]; vv += x["v"]
        vwap = pv / vv if vv else x["c"]
        run_hi = max(run_hi, x["h"])
        lows.append(x["l"])
        t = hmss(x["t"])
        if i < cool_until or not ("09:30:00" <= t <= "15:30:00"):
            i += 1; continue
        gain = x["c"] / first - 1
        if not (0.25 <= gain <= 0.60) or x["c"] <= vwap:
            i += 1; continue
        # is a pullback ending here? find the leg: rolling 5-min low -> running high
        leg_lo = min(lows[max(0, i - 30):i + 1])
        leg = run_hi - leg_lo
        if leg <= 0:
            i += 1; continue
        # pullback: consecutive lower bars off run_hi ending at i
        j = i
        pb_hi_px = x["h"]; pb_lo_px = x["l"]; bars_dn = 0
        while j > 0 and b[j]["c"] <= b[j]["o"] * 1.001 and bars_dn < 12:
            pb_hi_px = max(pb_hi_px, b[j]["h"]); pb_lo_px = min(pb_lo_px, b[j]["l"])
            bars_dn += 1; j -= 1
        if bars_dn < 1 or (run_hi - pb_lo_px) > 0.50 * leg or run_hi - pb_lo_px <= 0:
            i += 1; continue
        # trigger: within the next 6 bars a HIGH breaks the pullback high
        for k in range(i + 1, min(i + 7, n)):
            if b[k]["h"] > pb_hi_px:
                out.append((k, pb_hi_px + 0.01, pb_lo_px * 0.99))
                cool_until = k + 30
                break
        i += 1
    return out


def main():
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
    fills = []
    for d, sym in days:
        p = os.path.join(BARS, f"{d}_{sym}.json")
        raw = json.load(open(p))
        raw = raw.get("bars", raw) if isinstance(raw, dict) else raw
        if len(raw) < 150:
            continue
        b = [{"t": x["time"], "o": float(x.get("open") or x["close"]), "h": float(x["high"]),
              "l": float(x["low"]), "c": float(x["close"]), "v": float(x["volume"])} for x in raw]
        for k, entry, stop in scan(b):
            r1 = walk_spec(b, k, entry, stop)
            r2 = walk_e3(b, k, entry, stop)
            if r1 and r2:
                fills.append({"d": d, "sym": sym, "t": hmss(b[k]["t"]),
                              "spec": round(r1[0], 2), "e3": round(r2[0], 2)})
    print(f"name-days scanned: {len(days)}   fills: {len(fills)} "
          f"on {len({(f['d'], f['sym']) for f in fills})} name-days\n")

    def rep(lab, sel, key):
        if not sel:
            print(f"  {lab:26s} none"); return
        v = [f[key] for f in sel]
        tot = sum(v)
        print(f"  {lab:26s} n={len(v):4d}  total ${tot:+9.2f}  ${tot/len(v):+6.2f}/tr  "
              f"green {100*sum(1 for x in v if x>0)/len(v):3.0f}%")
    tr = [f for f in fills if int(f["d"][-2:]) % 2 == 0]
    oo = [f for f in fills if int(f["d"][-2:]) % 2 == 1]
    print("SPEC EXITS (40%@1.5R->BE, 5-min time stop, 15:50):")
    rep("TRAIN (even dates)", tr, "spec")
    rep("OOS   (odd dates)", oo, "spec")
    print("\nSAME ENTRIES through house E3 (control):")
    rep("TRAIN", tr, "e3")
    rep("OOS", oo, "e3")
    print("\nPRE-REGISTERED: interesting iff OOS spec $/tr > 0 with n>=30.")
    if oo:
        ok = len(oo) >= 30 and sum(f["spec"] for f in oo) / len(oo) > 0
        print(f"  -> {'YES' if ok else 'NO'}")
    json.dump(fills, open(os.path.join(HERE, "hidden_v2_simple_20260819_out.json"), "w"))
    print("\nsaved per-fill rows. LIMITS: RVOL/catalyst substituted by cache membership; day-gain")
    print("vs 4am print (tighter true window); no queue/halt modeling. Nothing ships from this file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
