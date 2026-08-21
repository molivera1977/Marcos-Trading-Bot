#!/usr/bin/env python3
"""
SPREAD-RELATIVE STOP FLOOR — the multi-day ladder (8/20 night, Marcos: "does a lower min
stop affect spread?" -> the one-day answer flipped the day's headline -> "i want to see the
numbers before deciding")

THE ONE-DAY FINDING THIS TESTS AT SCALE. 8/20's new-config replay read +$64.94 with the
walker's flat ~1.5% slips; charged at REAL sampled NBBO spreads it read -$331.72. The
mechanism: risk-based sizing loads MORE shares onto tighter stops while spread cost is per
share — round-trip spread dollars ~= $60 x (spread / stop-width). A stop narrower than the
spread pays more than the whole risk unit (UUU specimen: 0.44% stop, 11.4% spread, RT
spread $114.60 = 382% of risk). A spread-RELATIVE floor (stop >= k x live spread) recovered
~$340 of the bleed on that day, best near k=3 — but n=41, one chop day.

THIS FILE: the same question over the whole 10s cache. Cohort = every fill the new config
admits (hidden_v2-spec + the harness-replayable lanes, 1%% width floor, PRE 07:00-09:20 with
09:25 flatten + RTH 09:30-15:30 with 15:45/15:50 flat), each fill priced with the MEDIAN
NBBO spread of its own fill minute from Alpaca historical quotes (SIP). Exits: E3; entries
pay half-spread, stop/market exits pay half-spread, resting-limit tiers pay none.

LADDER: k in {0,1,2,3,4,6} where the guard is stop_width >= k x spread. k=0 = the config as
shipped tonight. Split TRAIN (even dates) / OOS (odd dates). Verdict metric = TOTAL DOLLARS
(the 8/20 law), capital-aware at $3,000, no cap.

PRE-REGISTERED: the guard is justified iff some k>0 beats k=0 on OOS total AND the ordering
is broadly monotone toward the winner on BOTH halves (a single-k spike is a lucky slice).
Also reported: how much of the SHIPPED config's replay profit survives real costs at k=0 —
the DRY_RUN-fiction number the proving-week grading must correct for.

LIMITS: median-of-minute spread (no sub-minute dynamics, no queue position); entries modeled
at mid + half-spread; quote gaps fail-open to a 0.5%%-of-price spread estimate (counted and
reported); one quotes query per (sym, day, minute) — deduped. Nothing ships from this file.
"""
import datetime as dt
import json
import os
import sys
import types
import urllib.request
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
RISK = 30.0
BAL = 3000.0
AK, AS = os.environ.get("AK", ""), os.environ.get("AS", "")
sp = importlib.util.spec_from_file_location("H", os.path.join(HERE, "live_harness.py"))
H = importlib.util.module_from_spec(sp)
sp.loader.exec_module(H)


def et(t):
    return dt.datetime.fromisoformat(str(t)[:19]) - dt.timedelta(hours=4)


def hm(t):
    return et(t).strftime("%H:%M")


def load_hv2():
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


_qcache = {}
_qmiss = [0, 0]


def spread_at(sym, day, hhmm):
    key = (sym, day, hhmm)
    if key in _qcache:
        return _qcache[key]
    _qmiss[1] += 1
    h, mnt = int(hhmm[:2]) + 4, hhmm[3:5]
    url = (f"https://data.alpaca.markets/v2/stocks/{sym}/quotes"
           f"?start={day}T{h:02d}:{mnt}:00Z&limit=60&feed=sip")
    rq = urllib.request.Request(url, headers={"APCA-API-KEY-ID": AK, "APCA-API-SECRET-KEY": AS})
    v = None
    try:
        qs = json.load(urllib.request.urlopen(rq, timeout=15)).get("quotes") or []
        sps = sorted(x["ap"] - x["bp"] for x in qs
                     if x.get("ap", 0) > 0 and x.get("bp", 0) > 0 and x["ap"] > x["bp"])
        v = sps[len(sps) // 2] if sps else None
    except Exception:
        v = None
    if v is None:
        _qmiss[0] += 1
    _qcache[key] = v
    return v


def walk(b, i0, entry, stop, pre, spr):
    px = entry + (spr / 2 if spr else entry * 0.005)
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(500 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    half = (spr / 2 if spr else px * 0.0025)
    flat = "09:25" if pre else "15:45"
    for i in range(i0 + 1, len(b)):
        x = b[i]
        t = hm(x["t"])
        if t >= flat:
            return banked + rem * ((x["c"] - half) - px), sh * px, i
        if x["l"] <= stop:
            return banked + rem * ((stop - half) - px), sh * px, i
        runhi = max(runhi, x["h"])
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 - px)
            rem -= n
            tiered = True
            stop = px
            if rem == 0:
                return banked, sh * px, i
        if tiered and x["c"] <= runhi * 0.90:
            return banked + rem * ((x["c"] - half) - px), sh * px, i
    return banked + rem * ((b[-1]["c"] - half) - px), sh * px, len(b) - 1


def main():
    hv2 = load_hv2()
    KCTX = {"front_side": None, "day_gain": None, "top3": False, "blue_sky": False}
    LANES = [("v2", {}), ("ignition10s", {}), ("grinder", {}), ("kevseq", KCTX), ("ema9x90", {})]
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
    fills = []
    for d, sym in days:
        raw = json.load(open(os.path.join(BARS, f"{d}_{sym}.json")))
        raw = raw.get("bars", raw) if isinstance(raw, dict) else raw
        if len(raw) < 150:
            continue
        b = [{"t": x["time"], "o": float(x.get("open") or x["close"]), "h": float(x["high"]),
              "l": float(x["low"]), "c": float(x["close"]), "v": float(x["volume"])} for x in raw]
        cand = []
        try:
            vw = H.running_vwap(raw, day=d)
            for lane, ctx in LANES:
                f = H.replay(sym, raw, [lane], day=d, batch_secs=60,
                             vwap_provider=lambda s, i, bar, l: vw[i],
                             ctx_provider=lambda s, i, bar, l: dict(ctx))
                for x in f:
                    i = x.get("i")
                    st = x.get("would_stop") or x.get("stop")
                    px = x.get("px") or (b[i]["c"] if i is not None else None)
                    if i is None or not st or not px or float(px) <= float(st):
                        continue
                    cand.append((i, float(px), float(st)))
        except Exception:
            pass
        for k, e, s_ in hv2(b):
            cand.append((k, e, s_))
        for i, e, s_ in cand:
            t = hm(b[i]["t"])
            pre = t < "09:30"
            if pre and not ("07:00" <= t <= "09:20"):
                continue
            if not pre and not ("09:30" <= t < "15:30"):
                continue
            w = (e * 0.99 - s_) / (e * 0.99) * 100
            if w < 1.0:
                continue
            spr = spread_at(sym, d, t)
            r = walk(b, i, e, s_, pre, spr)
            if r is None:
                continue
            pnl, notional, xi = r
            fills.append({"d": d, "t": t, "pre": pre, "pnl": pnl, "n": notional,
                          "stopw": e - s_, "spr": spr,
                          "ti": dt.datetime.fromisoformat(str(b[i]["t"])[:19]).timestamp(),
                          "tx": dt.datetime.fromisoformat(str(b[xi]["t"])[:19]).timestamp()})
    print(f"fills: {len(fills)}  quote-queries {_qmiss[1]}  quote-gaps(fail-open est.) {_qmiss[0]}\n")

    def sim(K):
        byday = {}
        for f in fills:
            if K > 0 and f["spr"] is not None and f["stopw"] < K * f["spr"]:
                continue
            byday.setdefault(f["d"], []).append(f)
        tot = n = 0
        tr = oo = 0.0
        for d, fl in byday.items():
            fl = sorted(fl, key=lambda x: x["ti"])
            op = []
            for f in fl:
                op = [o for o in op if o[0] > f["ti"]]
                if f["n"] > BAL - sum(o[1] for o in op):
                    continue
                op.append((f["tx"], f["n"]))
                tot += f["pnl"]
                n += 1
                if int(d[-2:]) % 2 == 0:
                    tr += f["pnl"]
                else:
                    oo += f["pnl"]
        return tot, n, tr, oo

    print(f"{'k':>4s} {'fills':>6s} {'TOTAL $':>11s} {'TRAIN $':>10s} {'OOS $':>10s}")
    out = []
    for K in (0, 1, 2, 3, 4, 6):
        tot, n, tr, oo = sim(K)
        out.append({"k": K, "n": n, "total": tot, "train": tr, "oos": oo})
        print(f"{K:4d} {n:6d} {tot:+11.2f} {tr:+10.2f} {oo:+10.2f}")
    json.dump(out, open(os.path.join(HERE, "spread_floor_20260820_out.json"), "w"))
    print("\nPRE-REGISTERED: a k>0 is justified iff it beats k=0 on OOS total AND the ladder is")
    print("broadly monotone toward the winner on BOTH halves. Nothing ships from this file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
