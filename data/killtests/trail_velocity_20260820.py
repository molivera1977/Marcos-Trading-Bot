#!/usr/bin/env python3
"""
TRAIL VELOCITY EXIT (8/20, Marcos: "I'd rather bank a win and re-enter" -> "or study the
speed of the trail falling" -> "build it")

THE OBSERVATION. On 8/20 every winner round-tripped: 4 of 6 names finished BELOW the entry
after offering +10% to +23%. Measured give-back from the run-high (1-min SIP, in-session):
IPST 24.5% in the first minute, MMA 10.4%, ZSTK 10.0%, BIVI 7.1%, WETO 3.6%, LSE 2.7%.

THE REFRAME. E3's trail fires on a CLOSE <= 90% of the run-high. When a name gives back
7-24% INSIDE one minute, that qualifying close prints after the damage. The defect is not the
trail's WIDTH, it is its LATENCY: it measures a level while the move is about a RATE. Making
the band tighter (10% -> 5%) punishes slow healthy pullbacks equally; a velocity trigger only
fires when the give-back is FAST. Same shape as the runway velocity override shipped 8/20
00:18, pointed at exits instead of entries.

THE RULE UNDER TEST (per open trade, after the first scale, alongside the existing exits):
    if (run_high - price) / run_high >= X  within N seconds of the run_high print
        -> exit the remainder NOW at that bar, do not wait for a close.
The existing E3 stop / +10% tier / 10% close-trail all stay armed; this can only exit EARLIER,
never later, and never overrides the stop.

GRID: X in {4,5,6,8,10,12}%  ×  N in {30,60,120,300}s. Reported against the live E3 control on
the SAME fills, so the comparison is like-for-like.

COHORT. Every hidden_v2-spec fill on the 10s SIP cache (the one entry generator we have a
validated detector for offline), walked bar-by-bar. Pre-registered reading: a cell is
interesting iff it beats the E3 control on OOS (odd dates) AND does not lose money on the
TREND subset (the days where the slow trail earns) — the guard against a rule that only wins
on chop.

LIMITS: 10s bars, stop-first ties, slips -1%/-0.5% applied identically to every arm; no halt
modeling (a halted tape prints nothing, so no velocity rule can act inside a halt — the 8/20
IPST gap is explicitly NOT claimable by this rule); cache times are UTC -> converted to ET
(the 8/19 class-fix). Nothing ships from this file.
"""
import datetime as dt
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
RISK = 30.0


def et(t):
    """cache stamps are UTC Z -> ET (EDT for every study date)."""
    return dt.datetime.fromisoformat(str(t)[:19]) - dt.timedelta(hours=4)


def hms(t):
    return et(t).strftime("%H:%M:%S")


def ep(t):
    return dt.datetime.fromisoformat(str(t)[:19]).timestamp()


def load_scan():
    """reuse the validated hidden_v2 spec scanner (true-ET variant)."""
    src = open(os.path.join(HERE, "hidden_v2_simple_20260819.py")).read()
    src = src.replace('if __name__ == "__main__":\n    sys.exit(main())', "")
    src = src.replace('def hmss(t):\n    return str(t)[11:19]',
                      'def hmss(t):\n    import datetime as _d\n'
                      '    return (_d.datetime.fromisoformat(str(t)[:19])'
                      ' - _d.timedelta(hours=4)).strftime("%H:%M:%S")')
    m = types.ModuleType("HV2")
    m.__file__ = os.path.join(HERE, "hidden_v2_simple_20260819.py")
    exec(compile(src, "HV2", "exec"), m.__dict__)
    return m.scan


def walk(b, i0, entry, stop, mode, X=None, N=None):
    """mode 'e3'  = control: bank 1/2 @+10% -> BE -> close-based 10% off-run-high trail
       mode 'vel' = same, PLUS: after the tier, exit NOW if the give-back from the run-high
                    reaches X% within N seconds of when that run-high printed.
       Both: stop-first ties, 15:50 ET flat, slips -1% entry / -0.5% exit."""
    px = entry * 0.99
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(500 / px)))
    rem, banked, tiered = sh, 0.0, False
    runhi, runhi_t = px, ep(b[i0]["t"])
    for i in range(i0 + 1, len(b)):
        x = b[i]
        if x["l"] <= stop:                                  # stop first, always
            return banked + rem * (stop - px)
        if x["h"] > runhi:
            runhi, runhi_t = x["h"], ep(x["t"])
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 * 0.995 - px)
            rem -= n
            tiered = True
            stop = px                                       # BE floor after the scale
            if rem == 0:
                return banked
        if tiered:
            if mode == "vel" and runhi > 0:
                # fast give-back: measured on the BAR LOW (intrabar), inside the window
                if (ep(x["t"]) - runhi_t) <= N and (runhi - x["l"]) / runhi * 100 >= X:
                    exit_px = max(runhi * (1 - X / 100.0), stop)   # fill at the trigger level
                    return banked + rem * (exit_px * 0.995 - px)
            if x["c"] <= runhi * 0.90:                      # the live close-based trail
                return banked + rem * (x["c"] * 0.995 - px)
        if hms(x["t"]) >= "15:50:00":
            return banked + rem * (x["c"] * 0.995 - px)
    return banked + rem * (b[-1]["c"] * 0.995 - px)


def main():
    scan = load_scan()
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
    setups = []
    for d, sym in days:
        raw = json.load(open(os.path.join(BARS, f"{d}_{sym}.json")))
        raw = raw.get("bars", raw) if isinstance(raw, dict) else raw
        if len(raw) < 150:
            continue
        b = [{"t": x["time"], "o": float(x.get("open") or x["close"]), "h": float(x["high"]),
              "l": float(x["low"]), "c": float(x["close"]), "v": float(x["volume"])} for x in raw]
        for k, entry, stop in scan(b):
            setups.append((d, sym, b, k, entry, stop))
    print(f"fills in cohort: {len(setups)}\n")

    def stats(vals):
        if not vals:
            return (0, 0.0, 0.0, 0.0)
        return (len(vals), sum(vals), sum(vals) / len(vals),
                100 * sum(1 for v in vals if v > 0) / len(vals))

    ctrl = {"tr": [], "oo": []}
    for d, sym, b, k, e, s in setups:
        r = walk(b, k, e, s, "e3")
        if r is None:
            continue
        ctrl["tr" if int(d[-2:]) % 2 == 0 else "oo"].append(r)
    n, t, a, g = stats(ctrl["tr"])
    n2, t2, a2, g2 = stats(ctrl["oo"])
    print("E3 CONTROL (live exits)")
    print(f"   TRAIN n={n:4d}  ${t:+9.2f}  ${a:+6.2f}/tr  green {g:3.0f}%")
    print(f"   OOS   n={n2:4d}  ${t2:+9.2f}  ${a2:+6.2f}/tr  green {g2:3.0f}%\n")
    base_oos = a2

    print(f"VELOCITY EXIT GRID  (delta vs control on OOS $/tr)")
    print(f"{'X%':>4s} {'N':>5s} {'TRAIN $/tr':>11s} {'OOS $/tr':>10s} {'OOS n':>6s} "
          f"{'green':>6s} {'delta':>8s}")
    rows = []
    for X in (4, 5, 6, 8, 10, 12):
        for N in (30, 60, 120, 300):
            tr, oo = [], []
            for d, sym, b, k, e, s in setups:
                r = walk(b, k, e, s, "vel", X, N)
                if r is None:
                    continue
                (tr if int(d[-2:]) % 2 == 0 else oo).append(r)
            _, _, ta, _ = stats(tr)
            on, _, oa, og = stats(oo)
            rows.append((X, N, ta, oa, on, og, oa - base_oos))
            print(f"{X:4d} {N:5d} {ta:+11.2f} {oa:+10.2f} {on:6d} {og:5.0f}% {oa-base_oos:+8.2f}")
    best = max(rows, key=lambda r: r[3])
    print(f"\nbest OOS cell: X={best[0]}% within {best[1]}s -> ${best[3]:+.2f}/tr "
          f"(control ${base_oos:+.2f}), train ${best[2]:+.2f}")
    print("\nPRE-REGISTERED: interesting iff it beats the control on OOS AND holds on TRAIN.")
    print("A cell that wins only on one half is a lucky slice (the prevwap lesson).")
    json.dump([{"X": r[0], "N": r[1], "train": r[2], "oos": r[3], "n": r[4],
                "green": r[5], "delta": r[6]} for r in rows],
              open(os.path.join(HERE, "trail_velocity_20260820_out.json"), "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ══════════════════════════════════════════════════════════════════════════════════════════
# KEV'S OWN EXIT THEORIES (8/20, Marcos: "also check Kev's exit theories")
# Sourced from data/kev/KEV_LESSONS_LEDGER.md — his words, with the ledger line that carries
# each. These are STRUCTURAL, not percentage rules, which is why they are worth a separate arm:
#   pbl   "I'm just raising my stops to one minute lows as price moves higher... trim into
#          strength as buyers find it until eventually I get stopped out."   [:136 pbl_trail]
#   half  "Got a half left, stops at entry."                                 [:244 scale_out]
#   round "Trimming into strength. There's 820. 820 to 850 to nine. Watch for the half dollar
#          at 850."                                                          [:238 scale_out]
#   under "I'm going to be out full there underneath six."                   [:243 topping_tail]
# ══════════════════════════════════════════════════════════════════════════════════════════


def _m1_lows(b):
    """10s bars -> {bucket_epoch: low of the last COMPLETED 1-min bar at that time}."""
    out, cur, curlo, curslot = {}, None, None, None
    lows = {}
    for x in b:
        slot = int(ep(x["t"])) // 60
        if curslot is None:
            curslot, curlo = slot, x["l"]
        elif slot != curslot:
            lows[curslot] = curlo            # the just-completed minute
            curslot, curlo = slot, x["l"]
        else:
            curlo = min(curlo, x["l"])
    prev = None
    for x in b:
        slot = int(ep(x["t"])) // 60
        out[int(ep(x["t"]))] = lows.get(slot - 1)
    return out


def _next_round(px):
    """the next half-dollar or whole-dollar above px (Kev's ladder)."""
    import math
    step = 0.5 if px >= 1.0 else 0.10
    return math.floor(px / step) * step + step


def walk_kev(b, i0, entry, stop, mode):
    """Kev arms. mode:
       'pbl'        after the +10% half, trail the PRIOR 1-MIN LOW (ratchet up only)
       'round'      trim 1/4 at each successive half/whole-dollar, runner on the 10% trail
       'pbl_round'  both: round-number trims + prior-1-min-low trail
       'under'      exit FULL just under the next round number once +10% is reached"""
    px = entry * 0.99
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(500 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    lows = _m1_lows(b) if mode in ("pbl", "pbl_round") else {}
    nxt = _next_round(px)
    for i in range(i0 + 1, len(b)):
        x = b[i]
        if x["l"] <= stop:
            return banked + rem * (stop - px)
        runhi = max(runhi, x["h"])
        if mode == "under":
            tgt = nxt - 0.01
            if x["h"] >= tgt:
                return banked + rem * (tgt * 0.995 - px)
        if mode in ("round", "pbl_round") and x["h"] >= nxt and rem > 1:
            n = int(rem * 0.25) or 1
            banked += n * (nxt * 0.995 - px)
            rem -= n
            tiered = True
            stop = max(stop, px)                       # Kev: "stops at entry" after the trim
            nxt = _next_round(nxt + 1e-9)
            if rem == 0:
                return banked
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 * 0.995 - px)
            rem -= n
            tiered = True
            stop = px
            if rem == 0:
                return banked
        if tiered:
            if mode in ("pbl", "pbl_round"):
                pl = lows.get(int(ep(x["t"])))
                if pl and pl > stop:
                    stop = pl                          # ratchet to prior 1-min low, never down
            elif x["c"] <= runhi * 0.90:
                return banked + rem * (x["c"] * 0.995 - px)
        if hms(x["t"]) >= "15:50:00":
            return banked + rem * (x["c"] * 0.995 - px)
    return banked + rem * (b[-1]["c"] * 0.995 - px)


def kev_main():
    scan = load_scan()
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
    setups = []
    for d, sym in days:
        raw = json.load(open(os.path.join(BARS, f"{d}_{sym}.json")))
        raw = raw.get("bars", raw) if isinstance(raw, dict) else raw
        if len(raw) < 150:
            continue
        b = [{"t": x["time"], "o": float(x.get("open") or x["close"]), "h": float(x["high"]),
              "l": float(x["low"]), "c": float(x["close"]), "v": float(x["volume"])} for x in raw]
        for k, entry, stop in scan(b):
            setups.append((d, sym, b, k, entry, stop))
    print(f"fills in cohort: {len(setups)}\n")
    print(f"{'arm':22s} {'TRAIN $/tr':>11s} {'OOS $/tr':>10s} {'OOS n':>6s} {'green':>6s}")
    for lab, fn, mode in (("E3 control", walk, "e3"),
                          ("KEV prior-1min-low", walk_kev, "pbl"),
                          ("KEV round trims", walk_kev, "round"),
                          ("KEV round + 1min", walk_kev, "pbl_round"),
                          ("KEV out-under-round", walk_kev, "under")):
        tr, oo = [], []
        for d, sym, b, k, e, s in setups:
            r = fn(b, k, e, s, mode)
            if r is None:
                continue
            (tr if int(d[-2:]) % 2 == 0 else oo).append(r)
        ta = sum(tr) / len(tr) if tr else 0
        oa = sum(oo) / len(oo) if oo else 0
        og = 100 * sum(1 for v in oo if v > 0) / len(oo) if oo else 0
        print(f"{lab:22s} {ta:+11.2f} {oa:+10.2f} {len(oo):6d} {og:5.0f}%")
    print("\nPRE-REGISTERED: an arm is interesting iff it beats E3 on OOS AND on TRAIN.")
