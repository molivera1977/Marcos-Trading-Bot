#!/usr/bin/env python3
"""
PREMARKET MIN-STOP LADDER (8/20, Marcos: "what if v2conv had no min and the others had your
new min number?" -> "run that right now")

WHY. On 8/20 the premarket dollar-volume floor shadowed 15 fires. Graded on tape with the
09:25 flatten: no floor +$40.93, floor on the TRUE session-dollar measure +$87.96 (cap-6
+$101.30), the live broken 15-min-window floor $0.00 (all shadowed). Adding min-stop 4% on
top flipped it to -$48.59 because the winners hug their structure: WETO +$127.30 on a 0.7%
stop, CDTG +$13.09 on 2.0%, IVF +$18.87 on 1.8%. Exempting ONLY v2conv scored WORSE
(-$34.00) than exempting everyone (+$101.30) — because that day's winner was an IGNITION
fire, not a v2conv one. n=7 fires with ONE trade carrying the whole result: unrulable.

THIS FILE asks the same question with real n: across the whole 10s cache, in the premarket
window, does a min-stop floor help or hurt — and does the answer differ by lane?

COHORT. Every v2-flush fill the bot's OWN detector produces (v2_pullback_step, lifted through
live_harness so the live calibration C1-C5 applies) in 07:00-09:20 ET, PLUS every hidden_v2-
spec fill in the same window as the non-v2 comparison arm. Exits = house E3 with the 09:25
PRE flatten, stop-first, slips -1%/-0.5%. Cache stamps are UTC -> ET (the 8/19 class-fix).

LADDER: min-stop floor in {0, 1, 2, 3, 4, 5, 6}% applied to the fill's own stop width, run
per-lane and pooled, split TRAIN (even dates) / OOS (odd dates).

PRE-REGISTERED READING: a floor is justified iff removing it LOSES money on OOS. If P&L is
flat or better with the floor OFF, the 4% floor is destroying premarket entries by design and
the ruling is Marcos's. A per-lane exemption is justified only if the lanes disagree in the
SAME direction on both halves.

LIMITS: 10s bars; no queue/halt modeling; PRE cap and one-per-ticker NOT applied (this
measures the GATE, not the day's portfolio); the dollar-volume floor is NOT applied here so
the two gates stay separable. Nothing ships from this file.
"""
import datetime as dt
import importlib.util
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
RISK = 30.0
sp = importlib.util.spec_from_file_location("H", os.path.join(HERE, "live_harness.py"))
H = importlib.util.module_from_spec(sp)
sp.loader.exec_module(H)


def et(t):
    return dt.datetime.fromisoformat(str(t)[:19]) - dt.timedelta(hours=4)


def hm(t):
    return et(t).strftime("%H:%M")


def load_hv2_scan():
    src = open(os.path.join(HERE, "hidden_v2_simple_20260819.py")).read()
    src = src.replace('if __name__ == "__main__":\n    sys.exit(main())', "")
    src = src.replace('def hmss(t):\n    return str(t)[11:19]',
                      'def hmss(t):\n    import datetime as _d\n'
                      '    return (_d.datetime.fromisoformat(str(t)[:19])'
                      ' - _d.timedelta(hours=4)).strftime("%H:%M:%S")')
    src = src.replace('"09:30:00" <= t <= "15:30:00"', '"07:00:00" <= t <= "09:20:00"')
    m = types.ModuleType("HV2")
    m.__file__ = os.path.join(HERE, "hidden_v2_simple_20260819.py")
    exec(compile(src, "HV2", "exec"), m.__dict__)
    return m.scan


def walk_pre(b, i0, entry, stop):
    """house E3 with the 09:25 PRE flatten."""
    px = entry * 0.99
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(500 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    for i in range(i0 + 1, len(b)):
        x = b[i]
        if hm(x["t"]) >= "09:25":
            return banked + rem * (x["c"] * 0.995 - px)
        if x["l"] <= stop:
            return banked + rem * (stop - px)
        runhi = max(runhi, x["h"])
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 * 0.995 - px)
            rem -= n
            tiered = True
            stop = px
            if rem == 0:
                return banked
        if tiered and x["c"] <= runhi * 0.90:
            return banked + rem * (x["c"] * 0.995 - px)
    return banked + rem * (b[-1]["c"] * 0.995 - px)


def main():
    hv2 = load_hv2_scan()
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
        if sum(1 for x in b if hm(x["t"]) < "09:30") < 30:
            continue
        # --- arm 1: the bot's OWN v2 detector via the harness (live calibration applies)
        try:
            vw = H.running_vwap(raw, day=d)
            fires = H.replay(sym, raw, ["v2"], day=d, batch_secs=60,
                             vwap_provider=lambda s, i, bar, lane: vw[i],
                             ctx_provider=lambda s, i, bar, lane: {})
        except Exception:
            fires = []
        for f in fires:
            i = f.get("i")
            if i is None or not ("07:00" <= hm(b[i]["t"]) <= "09:20"):
                continue
            st = f.get("would_stop") or f.get("stop")
            px = f.get("px") or b[i]["c"]
            if not st or float(st) <= 0 or px <= float(st):
                continue
            r = walk_pre(b, i, float(px), float(st))
            if r is not None:
                e = float(px) * 0.99
                fills.append({"d": d, "sym": sym, "lane": "v2conv",
                              "w": (e - float(st)) / e * 100, "p": r})
        # --- arm 2: hidden_v2-spec fills in the same window (the "others" comparison)
        for k, entry, stop in hv2(b):
            r = walk_pre(b, k, entry, stop)
            if r is not None:
                e = entry * 0.99
                fills.append({"d": d, "sym": sym, "lane": "other",
                              "w": (e - stop) / e * 100, "p": r})
    print(f"premarket fills graded: {len(fills)}  "
          f"(v2conv {sum(1 for f in fills if f['lane']=='v2conv')}, "
          f"other {sum(1 for f in fills if f['lane']=='other')})\n")

    def rep(sel):
        tr = [f["p"] for f in sel if int(f["d"][-2:]) % 2 == 0]
        oo = [f["p"] for f in sel if int(f["d"][-2:]) % 2 == 1]
        return (len(tr), sum(tr) / len(tr) if tr else 0.0,
                len(oo), sum(oo) / len(oo) if oo else 0.0, sum(oo))

    print(f"{'lane':8s} {'minstop':>8s} {'TRAIN n':>8s} {'TR $/tr':>8s} "
          f"{'OOS n':>6s} {'OOS $/tr':>9s} {'OOS total':>10s}")
    for lane in ("v2conv", "other", "ALL"):
        pool = [f for f in fills if lane == "ALL" or f["lane"] == lane]
        for ms in (0, 1, 2, 3, 4, 5, 6):
            sel = [f for f in pool if f["w"] >= ms]
            tn, ta, on, oa, ot = rep(sel)
            print(f"{lane:8s} {ms:7d}% {tn:8d} {ta:+8.2f} {on:6d} {oa:+9.2f} {ot:+10.2f}")
        print()
    json.dump(fills, open(os.path.join(HERE, "premkt_minstop_20260820_out.json"), "w"))
    print("PRE-REGISTERED: the floor is justified iff removing it LOSES money on OOS.")
    print("A per-lane exemption needs the lanes to disagree the SAME way on BOTH halves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
